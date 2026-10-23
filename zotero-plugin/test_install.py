"""在隔离配置/数据目录启动真实 Zotero 10.0.6，通过本机调试协议验收安装。

不读取或修改日常 Zotero 配置/论文库。仅 Windows 启动方式经过验证。
--check-update 在同一验收配置上检查已发布的真实更新清单。
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import zipfile


class Debugger:
    def __init__(self, sock):
        self.sock = sock
        self.stream = sock.makefile("rb")
        self.receive()

    def receive(self):
        header = bytearray()
        while True:
            char = self.stream.read(1)
            if not char:
                raise EOFError("调试连接已关闭")
            if char == b":":
                break
            header.extend(char)
        size = int(header)
        payload = self.stream.read(size)
        return json.loads(payload)

    def request(self, actor, kind, **params):
        payload = json.dumps(dict(to=actor, type=kind, **params)).encode("utf-8")
        self.sock.sendall(str(len(payload)).encode("ascii") + b":" + payload)
        while True:
            response = self.receive()
            if response.get("from") == actor and response.get("type") != "evaluationResult":
                if response.get("error"):
                    raise RuntimeError(response)
                return response

    def console_actor(self):
        response = self.request("root", "getProcess", id=0)
        descriptor = response.get("processDescriptor") or response.get("form") or response
        if descriptor.get("consoleActor"):
            return descriptor["consoleActor"]
        response = self.request(descriptor["actor"], "getTarget")
        target = response.get("process") or response.get("form") or response.get("target") or response
        return target["consoleActor"]

    def evaluate(self, actor, text):
        response = self.request(actor, "evaluateJSAsync", text=text, eager=False)
        result_id = response["resultID"]
        while True:
            response = self.receive()
            if response.get("type") == "evaluationResult" and response.get("resultID") == result_id:
                if response.get("exception") or response.get("exceptionMessage") or response.get("topLevelAwaitRejected"):
                    raise RuntimeError(response)
                return response.get("result")


def run_phase(args, profile, data, port, phase):
    env = os.environ.copy()
    env["MOZ_HEADLESS"] = "1"
    options = {}
    if os.name == "nt":
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = subprocess.SW_HIDE
        options.update(startupinfo=info, creationflags=subprocess.CREATE_NO_WINDOW)
    command = [str(args.zotero_exe), "-no-remote", "-profile", str(profile),
               "-datadir", str(data), "-headless", "-debugger", "-ZoteroDebugText", "-ZoteroSkipBundledFiles"]
    log_path = args.work_dir / (phase + ".log")
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, **options)
        client = None
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    sock = socket.create_connection(("127.0.0.1", port), timeout=1)
                    sock.settimeout(90)
                    client = Debugger(sock)
                    break
                except (OSError, EOFError):
                    if process.poll() is not None:
                        raise RuntimeError("Zotero 启动退出，查看 " + str(log_path))
                    time.sleep(0.2)
            if not client:
                raise TimeoutError("未连接到隔离 Zotero，查看 " + str(log_path))
            actor = client.console_actor()
            with zipfile.ZipFile(args.xpi) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            config = dict(phase=phase, profile=str(profile), dataDir=str(data),
                          pluginID=manifest["applications"]["zotero"]["id"], version=manifest["version"],
                          xpi=str(args.xpi), rejectedXpi=str(args.rejected_xpi) if args.rejected_xpi else None)
            code = Path(__file__).with_suffix(".js").read_text(encoding="utf-8").replace("__CONFIG__", json.dumps(config))
            # 原始调试协议不替控制台前端重写顶层 await；用 Promise 回调回传结果。
            client.evaluate(actor, "globalThis.__CUEB_INSTALL_RESULT = null;\n" + code +
                            ".then(value => { globalThis.__CUEB_INSTALL_RESULT = value; }, "
                            "error => { globalThis.__CUEB_INSTALL_RESULT = JSON.stringify({error:String(error),stack:error.stack}); }); 'started';")
            deadline = time.monotonic() + 90
            result = None
            while time.monotonic() < deadline:
                result = client.evaluate(actor, "globalThis.__CUEB_INSTALL_RESULT")
                if isinstance(result, str):
                    break
                time.sleep(0.2)
            if not isinstance(result, str):
                raise TimeoutError("未收到验收JSON字符串，查看 " + str(log_path))
            receipt = json.loads(result)
            if receipt.get("error"):
                raise RuntimeError(receipt)
            (args.work_dir / (phase + "-receipt.json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(receipt, ensure_ascii=False), flush=True)
            try:
                client.request(actor, "evaluateJSAsync", text="Services.startup.quit(Services.startup.eAttemptQuit);", eager=False)
            except (EOFError, OSError):
                pass
            process.wait(timeout=20)
        finally:
            if client:
                client.stream.close()
                client.sock.close()
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zotero-exe", type=Path, required=True)
    parser.add_argument("--xpi", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--rejected-xpi", type=Path)
    parser.add_argument("--check-update", action="store_true")
    args = parser.parse_args()
    args.work_dir = args.work_dir.resolve()
    args.xpi = args.xpi.resolve(strict=True)
    args.zotero_exe = args.zotero_exe.resolve(strict=True)
    if args.rejected_xpi:
        args.rejected_xpi = args.rejected_xpi.resolve(strict=True)
    profile, data = args.work_dir / "profile", args.work_dir / "data"
    if not args.check_update:
        args.work_dir.mkdir(parents=True, exist_ok=False)
        profile.mkdir()
        data.mkdir()
    else:
        assert (args.work_dir / "restart-receipt.json").is_file(), "必须先完成同一配置的安装/重启验收"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    prefs = {
        "devtools.debugger.remote-enabled": True,
        "devtools.chrome.enabled": True,
        "devtools.debugger.prompt-connection": False,
        "devtools.debugger.force-local": True,
        "devtools.debugger.remote-port": port,
        "extensions.zotero.useDataDir": True,
        "extensions.zotero.dataDir": str(data),
        "extensions.zotero.firstRun2": False,
        "extensions.update.enabled": False,
        "app.update.auto": False,
    }
    (profile / "user.js").write_text("\n".join("user_pref("+json.dumps(k)+", "+json.dumps(v)+");" for k, v in prefs.items()), encoding="utf-8")
    for phase in (["update"] if args.check_update else ["install", "restart"]):
        run_phase(args, profile, data, port, phase)


if __name__ == "__main__":
    main()
