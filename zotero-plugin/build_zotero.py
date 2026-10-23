#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_zotero.py — 生成"首经贸期刊等级助手" Zotero 7 插件（.xpi）

功能：在 Zotero 条目列表加一列「首经贸等级」，显示校目录等级 + SSCI/JCR Q +
UTD24/FT50/ABS 收录标签（如：国际A+｜SSCI｜Q1｜UTD24｜FT50｜ABS 4*）。
数据与浏览器独立版完全同源（build_fork.build_data）。

产物：zotero/cueb-journal-tier-<版本>.xpi
安装：Zotero → 工具 → 插件 → 右上角齿轮 → Install Plugin From File
列显示：条目列表表头右键 → 勾选「首经贸等级」
"""
import hashlib, json, os, shutil, subprocess, sys, zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.normpath(os.path.join(_HERE, '..', 'browser'))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from build_fork import (build_data, DEFAULT_CATALOG, DEFAULT_CSSCI, DEFAULT_CSCD,
                        DEFAULT_UTD24, DEFAULT_FT50, DEFAULT_AJG, DEFAULT_SSCI,
                        DEFAULT_JCR, LOOKUP_FACTORY, node_check)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "zotero")
VERSION = "1.0.10"
PLUGIN_ID = "cueb-tier-column@example.com"
UPDATE_URL = "https://raw.githubusercontent.com/Z1hawl89/cueb-journal-tier/master/zotero-plugin/update.json"
XPI = os.path.join(OUT, f"cueb-tier-column-{VERSION}.xpi")

MANIFEST = {
    "manifest_version": 2,
    "name": "首经贸期刊等级助手",
    "version": VERSION,
    "author": "lizih",
    "description": "条目列表显示期刊的首经贸校目录等级及 SSCI/JCR/UTD24/FT50/AJG 收录标签。数据内置，完全本地。",
    "homepage_url": "https://github.com/Z1hawl89/cueb-journal-tier",
    "icons": {
        "48": "icons/48.png",
        "96": "icons/96.png"
    },
    "applications": {
        "zotero": {
            "id": PLUGIN_ID,
            # Zotero 安装器要求 id/update_url/strict_max_version 三项均存在。
            "update_url": UPDATE_URL,
            "strict_min_version": "7.0.11",
            "strict_max_version": "10.0.*"
        }
    }
}

BOOTSTRAP = r"""/* bootstrap.js — 首经贸期刊等级助手（Zotero 7+ 列插件） */
var VERSION = "__VERSION__";
var PLUGIN_ID = "__PLUGIN_ID__";
var DATA = null;
var DATA_ERROR = "";
var registeredKey = null;
var LOOKUP = null;
var makeLookup = __LOOKUP_FACTORY__;
var AJG_RANK = { "4*": 5, "4": 4, "3": 3, "2": 2, "1": 1 };
var AJG_MIN = 3;   /* ABS 标签最低显示档位，与浏览器独立版一致 */

function log(msg) {
    try { Zotero.debug("[CUEB-Tier] " + msg); } catch (e) {}
}
/* 错误级日志：不开调试模式也会出现在 Error Console */
function logAlways(msg) {
    log(msg);
    try { Zotero.logError("[CUEB-Tier] " + msg); } catch (e) {}
}

/* 条目类型可能不含某字段（如会议论文无 issn），getField 会抛 Invalid field——逐字段容错 */
function safeField(item, field) {
    try { return item.getField(field, false, true) || ""; } catch (e) { return ""; }
}

/* 与浏览器共用：ISSN 优先，刊名和别名兜底。 */
function lookupTier(pub, issn) {
    return LOOKUP ? LOOKUP.resolve(pub, issn).tier : "";
}

function computeTier(item) {
    try {
        if (DATA_ERROR) return "⚠" + DATA_ERROR;
        if (!DATA) return "⚠数据未加载";
        var pub = safeField(item, "publicationTitle");
        var issn = safeField(item, "ISSN");
        var resolved = LOOKUP.resolve(pub, issn);
        var t = resolved.tier, n = resolved.key;
        var mem = (set) => LOOKUP.get(set, n);
        var D = DATA, parts = [];
        if (t) parts.push(t);
        if (mem(D.inCssci)) parts.push("CSSCI");
        if (mem(D.inCscd)) parts.push("CSCD");
        if (mem(D.inUtd24)) parts.push("UTD24");
        if (mem(D.inFt50)) parts.push("FT50");
        var g = mem(D.inAjg);
        if (g && AJG_RANK[g] >= AJG_MIN) parts.push("ABS " + g);
        var q = mem(D.inJcr);
        if (q) parts.push("JCR " + q);
        if (mem(D.inSsci)) parts.push("SSCI");
        return parts.join("｜");
    } catch (e) {
        log("computeTier 异常: " + e);
        return "";
    }
}

async function startup({ rootURI, id, version } = {}) {
    if (registeredKey) return;
    DATA_ERROR = "";
    logAlways("startup v" + VERSION + " 开始，rootURI=" + (rootURI || "(无)"));
    try {
        // 数据来源优先级：内嵌字面量 → 包内 data.json
        if (typeof DATA_EMBEDDED !== "undefined" && DATA_EMBEDDED) {
            DATA = DATA_EMBEDDED;
            logAlways("数据来源=内嵌，byName " + Object.keys(DATA.byName).length + " 条");
        } else {
            const text = await Zotero.File.getContentsAsync(rootURI + "data.json");
            DATA = JSON.parse(text);
            logAlways("数据来源=data.json，byName " + Object.keys(DATA.byName).length + " 条");
        }
        LOOKUP = makeLookup(DATA);
        registeredKey = await Zotero.ItemTreeManager.registerColumn({
            pluginID: PLUGIN_ID,
            dataKey: "cuebTier",
            label: "首经贸等级",
            dataProvider: (item) => computeTier(item)
        });
        if (!registeredKey) throw new Error("registerColumn 未返回注册 key");
        logAlways("列注册成功");
    } catch (e) {
        DATA_ERROR = "插件启动失败: " + e;
        logAlways("启动失败: " + (e.stack || e));
    }
}

async function shutdown() {
    if (registeredKey) {
        try {
            await Zotero.ItemTreeManager.unregisterColumn(registeredKey);
        } catch (e) {
            logAlways("注销列失败: " + e);
        }
        registeredKey = null;
    }
}

function install() {}
function uninstall() {}
function onMainWindowLoad() {}
"""


def main():
    data, n_name, n_issn, conflicts, *_ = build_data(
        DEFAULT_CATALOG, DEFAULT_CSSCI, DEFAULT_CSCD, DEFAULT_UTD24,
        DEFAULT_FT50, DEFAULT_AJG, DEFAULT_SSCI, DEFAULT_JCR)
    # 列上用不到悬停学科明细，去掉以减半体积
    data.pop("inJcrCat", None)
    print(f"数据: byName {n_name} / byIssn {n_issn} / 同名不同级 {len(conflicts)}")

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False)
    # 数据以 JS 字面量内嵌进 bootstrap（ensure_ascii=True 保证字面量安全），启动零文件读取
    open(os.path.join(OUT, "bootstrap.js"), "w", encoding="utf-8", newline="\n").write(
        BOOTSTRAP.replace("__VERSION__", VERSION).replace("__PLUGIN_ID__", PLUGIN_ID)
        .replace("__LOOKUP_FACTORY__", LOOKUP_FACTORY)
        + "\nvar DATA_EMBEDDED = " + json.dumps(data, ensure_ascii=True) + ";\n")
    node_check(os.path.join(OUT, "bootstrap.js"))

    # 生成图标（深蓝方块，构建时流水生成，无需外部文件）
    import struct, zlib

    def make_png(size, rgb):
        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
        raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw))
                + chunk(b"IEND", b""))

    icon_dir = os.path.join(OUT, "icons")
    os.makedirs(icon_dir, exist_ok=True)
    open(os.path.join(icon_dir, "48.png"), "wb").write(make_png(48, (30, 58, 138)))
    open(os.path.join(icon_dir, "96.png"), "wb").write(make_png(96, (30, 58, 138)))

    with zipfile.ZipFile(XPI, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in ("manifest.json", "bootstrap.js", "data.json", "icons/48.png", "icons/96.png"):
            # 固定 ZIP 元数据，让独立构建得到相同 SHA-256，更新清单才能稳定校验。
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            with open(os.path.join(OUT, name), "rb") as f:
                z.writestr(info, f.read(), compresslevel=9)
    if not data["inSsci"] and not data["inJcr"]:
        with open(XPI, "rb") as f:
            xpi_hash = hashlib.sha256(f.read()).hexdigest()
        update = {
            "addons": {PLUGIN_ID: {"updates": [{
                "version": VERSION,
                "update_link": f"https://github.com/Z1hawl89/cueb-journal-tier/releases/download/zotero-v{VERSION}/cueb-tier-column-{VERSION}.xpi",
                "update_hash": "sha256:" + xpi_hash,
                "applications": {"zotero": dict(
                    (k, MANIFEST["applications"]["zotero"][k])
                    for k in ("strict_min_version", "strict_max_version"))}
            }]}}
        }
        with open(os.path.join(OUT, "update.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(update, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("公开数据更新清单 →", os.path.join(OUT, "update.json"))
    else:
        print("检测到 SSCI/JCR 额外数据：不生成公共更新清单")
    print(f"完成 → {XPI} ({os.path.getsize(XPI)//1024} KB)")
    print("安装: Zotero → 工具 → 插件 → 右上角齿轮 → Install Plugin From File → 选本 xpi")
    print("显示: 条目列表表头右键 → 勾选「首经贸等级」")


if __name__ == "__main__":
    main()
