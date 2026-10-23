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
import json, os, shutil, subprocess, sys, zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.normpath(os.path.join(_HERE, '..', 'browser'))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from build_fork import (build_data, DEFAULT_CATALOG, DEFAULT_CSSCI, DEFAULT_CSCD,
                        DEFAULT_UTD24, DEFAULT_FT50, DEFAULT_AJG, DEFAULT_SSCI,
                        DEFAULT_JCR, node_check)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "zotero")
VERSION = "1.0.8"
PLUGIN_ID = "cueb-tier-column@example.com"
XPI = os.path.join(OUT, f"cueb-tier-column-{VERSION}.xpi")

MANIFEST = {
    "manifest_version": 2,
    "name": "首经贸期刊等级助手",
    "version": VERSION,
    "author": "lizih",
    "description": "条目列表显示期刊的首经贸校目录等级及 SSCI/JCR/UTD24/FT50/AJG 收录标签。数据内置，完全本地。",
    "homepage_url": "https://github.com/lizih/cueb-journal-tier",
    "icons": {
        "48": "icons/48.png",
        "96": "icons/96.png"
    },
    "applications": {
        "zotero": {
            "id": PLUGIN_ID,
            "update_url": "https://example.com/cueb-journal-tier/update.json",
            # 对齐已验证可安装的插件：min/max 都显式声明（Zotero 8 起缺 strict_max 拒装）
            "strict_min_version": "8.0.1",
            "strict_max_version": "10.*"
        }
    }
}

BOOTSTRAP = r"""/* bootstrap.js — 首经贸期刊等级助手（Zotero 7+ 列插件） */
var VERSION = "__VERSION__";
var PLUGIN_ID = "__PLUGIN_ID__";
var DATA = null;
var DATA_ERROR = "";
var registered = false;
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

function norm(s) {
    try { s = String(s).normalize("NFKC"); } catch (e) {}
    return String(s || "").toLowerCase().replace(/[^0-9a-z\u4e00-\u9fff]/g, "");
}

/* 条目类型可能不含某字段（如会议论文无 issn），getField 会抛 Invalid field——逐字段容错 */
function safeField(item, field) {
    try { return item.getField(field, false, true) || ""; } catch (e) { return ""; }
}

/* 与浏览器版 lookup 一致：刊名精确 → the-回退 → ISSN */
function lookupTier(pub, issn) {
    var D = DATA;
    var n = norm(pub);
    var t = "";
    if (n) {
        t = D.byName[n] || "";
        if (!t && n.length > 3 && n.indexOf("the") === 0) t = D.byName[n.slice(3)] || "";
        if (!t) t = D.byName["the" + n] || "";
    }
    if (!t && issn) {
        var m = String(issn).replace(/[^0-9xX]/g, "").toUpperCase();
        if (/^[0-9]{7}[0-9X]$/.test(m) && D.byIssn[m]) t = D.byIssn[m];
    }
    return t;
}

function computeTier(item) {
    try {
        if (DATA_ERROR) return "⚠" + DATA_ERROR;
        if (!DATA) return "⚠数据未加载";
        var pub = safeField(item, "publicationTitle");
        var issn = safeField(item, "issn");
        var t = lookupTier(pub, issn);
        var n = norm(pub);
        /* the-回退：收录集里 SSCI/CSSCI/CSCD 只有原始键，"The X" 写法查不到，
           统一用双键探测（与浏览器版 member_keys 构建时扩展等效） */
        var alt = (n.indexOf("the") === 0 && n.length > 4) ? n.slice(3) : "the" + n;
        var mem = (set) => set && (set[n] || set[alt]);
        var D = DATA, parts = [];
        if (t) parts.push(t);
        if (mem(D.inCssci)) parts.push("CSSCI");
        if (mem(D.inCscd)) parts.push("CSCD");
        if (mem(D.inUtd24)) parts.push("UTD24");
        if (mem(D.inFt50)) parts.push("FT50");
        var g = D.inAjg && (D.inAjg[n] || D.inAjg[alt]);
        if (g && AJG_RANK[g] >= AJG_MIN) parts.push("ABS " + g);
        var q = D.inJcr && (D.inJcr[n] || D.inJcr[alt]);
        if (q) parts.push("JCR " + q);
        if (mem(D.inSsci)) parts.push("SSCI");
        return parts.join("｜");
    } catch (e) {
        log("computeTier 异常: " + e);
        return "";
    }
}

async function startup({ rootURI, id, version } = {}) {
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
        await Zotero.ItemTreeManager.registerColumn({
            pluginID: PLUGIN_ID,
            dataKey: "cuebTier",
            label: "首经贸等级",
            dataProvider: (item) => computeTier(item)
        });
        registered = true;
        logAlways("列注册成功");
    } catch (e) {
        DATA_ERROR = "插件启动失败: " + e;
        logAlways("启动失败: " + (e.stack || e));
    }
}

function shutdown() {
    if (registered) {
        try {
            Zotero.ItemTreeManager.unregisterColumn("cuebTier", "cueb-journal-tier@example.com");
        } catch (e) {
            try { Zotero.ItemTreeManager.unregisterColumn("cuebTier"); } catch (e2) {}
        }
        registered = false;
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

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    # 数据以 JS 字面量内嵌进 bootstrap（ensure_ascii=True 保证字面量安全），启动零文件读取
    open(os.path.join(OUT, "bootstrap.js"), "w", encoding="utf-8").write(
        BOOTSTRAP.replace("__VERSION__", VERSION).replace("__PLUGIN_ID__", PLUGIN_ID)
        + "\nvar DATA_EMBEDDED = " + json.dumps(data, ensure_ascii=True) + ";\n")
    node_check(os.path.join(OUT, "bootstrap.js"))
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
            z.write(os.path.join(OUT, name), name)
    print(f"完成 → {XPI} ({os.path.getsize(XPI)//1024} KB)")
    print("安装: Zotero → 工具 → 插件 → 右上角齿轮 → Install Plugin From File → 选本 xpi")
    print("显示: 条目列表表头右键 → 勾选「首经贸等级」")


if __name__ == "__main__":
    main()
