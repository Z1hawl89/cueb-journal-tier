#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_fork.py — 从本地已安装的 easyScholar 生成带首经贸等级功能的本地分支

改动共四处（全部由本脚本自动完成，官方升级后重跑即可）：
  1. show_ranking/ranking/utils.js  公共入口 o(e,a) 插入 104 字符钩子，
     暴露 {paperID: 期刊名} 到 window.__cuebNames
  2. 新增 cueb_data.js   首经贸目录数据（1122 刊名 + 987 ISSN）+ 共享匹配逻辑，
     内容脚本与 service worker 共用
  3. 新增 cueb_inject.js 徽章注入 + 右键查询结果 toast
  4. 新增/追加 service worker：右键菜单注册与查询处理（append 到官方 SW 末尾），
     manifest 加 contextMenus 权限

仅供个人本地使用，请勿分发 dist/（内含对方专有代码）。
"""
import glob, json, os, re, shutil, subprocess, sys, unicodedata, hashlib

SRC_GLOB = (r"C:/Users/lizih/AppData/Local/Microsoft/Edge/User Data/Default"
            r"/Extensions/bpepicgagmdchlkjjeeiekpoafehpagm/*/manifest.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
FORK_PATCH = 10   # 分支补丁号：官方 15.4 → 15.4.10（manifest 只允许点分整数）
# 数据集解析：仓库 data/ 目录优先（发布用），本机 workspace 后备（本地开发用）。
# 缺失的数据集自动跳过对应标签（build_data 内部已做 os.path.exists 检查）。
_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIRS = [
    os.path.join(_HERE, "..", "data"),                                    # 仓库布局
    os.path.join(_HERE, "data"),                                          # 同目录 data/
    r"C:/Users/lizih/.zcode/workspace/default",                          # 本机 workspace
]

def _find_data(filename):
    for d in _DATA_DIRS:
        p = os.path.normpath(os.path.join(d, filename))
        if os.path.exists(p):
            return p
    return os.path.normpath(os.path.join(_DATA_DIRS[0], filename))       # 不存在也返回首选路径（构建时按缺失处理）

DEFAULT_CATALOG = _find_data("cueb_journal_catalog_2024.json")
DEFAULT_CSSCI = _find_data("cssci_2025_2026.json")
DEFAULT_CSCD = _find_data("cscd_2025_2026.json")
DEFAULT_UTD24 = _find_data("utd24.json")
DEFAULT_FT50 = _find_data("ft50.json")
DEFAULT_AJG = _find_data("ajg_2024.json")
DEFAULT_SSCI = _find_data("ssci_2026.json")
DEFAULT_JCR = _find_data("jcr_2026.json")

# UTD24 官方写法与通行写法的异名（右侧通行名也纳入匹配键）
WEBLIST_ALIASES = {
    "Journal on Computing": ["INFORMS Journal on Computing"],
}

HOOK = ("try{window.__cuebNames=Object.assign(window.__cuebNames||{},"
        "(a&&a.publicationName)||{})}catch(__cuebE){}")

DATA_TEMPLATE = r"""/* cueb_data.js — 首经贸期刊目录数据 + 共享匹配逻辑（build_fork.py 生成） */
self.__CUEB_TIERS__ = %DATA%;
self.__cuebMakeLookup = function () {
  "use strict";
  var D = self.__CUEB_TIERS__;
  function norm(s) {
    try { s = String(s).normalize("NFKC"); } catch (e) {}
    return String(s || "").toLowerCase().replace(/[^0-9a-z\u4e00-\u9fff]/g, "");
  }
  function lev(a, b) {                    /* 编辑距离相似度 */
    if (a === b) return 1;
    var m = a.length, n = b.length;
    if (!m || !n) return 0;
    var prev = new Array(n + 1), cur = new Array(n + 1), i, j;
    for (j = 0; j <= n; j++) prev[j] = j;
    for (i = 1; i <= m; i++) {
      cur[0] = i;
      for (j = 1; j <= n; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1,
                          prev[j - 1] + (a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1));
      }
      var t = prev; prev = cur; cur = t;
    }
    return 1 - prev[n] / Math.max(m, n);
  }
  function lookup(name) {
    var n = norm(name);
    if (!n) return null;
    var t = D.byName[n];
    if (!t && n.indexOf("the") === 0) t = D.byName[n.slice(3)];   /* The Accounting Review ↔ Accounting Review */
    if (!t) t = D.byName["the" + n];
    if (t) return t;
    if (/^[a-z\d]{7}[\dx]$/.test(n)) {           /* 输入恰为ISSN数字串 */
      var iss = n.toUpperCase();                   /* 数据键尾位X为大写 */
      if (D.byIssn[iss]) return D.byIssn[iss];
    }
    return null;
  }
  function candidates(name, limit) {       /* 只做候选，不自动确认 */
    var n = norm(name), out = [];
    if (!n) return out;
    var keys = Object.keys(D.byName);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i], score = 0;
      if (n === k) continue;
      if (n.length >= 4 && (n.indexOf(k) >= 0 || k.indexOf(n) >= 0)) score = 0.9;
      else {
        var r = lev(n, k);
        if (r >= 0.80) score = r;
      }
      if (score) out.push({ score: score, name: k, level: D.byName[k] });
    }
    out.sort(function (a, b) { return b.score - a.score; });
    return out.slice(0, limit || 5).map(function (c) {
      return { name: (D.disp && D.disp[c.name]) || c.name, level: c.level };
    });
  }
  return { norm: norm, lookup: lookup, candidates: candidates };
};
"""

INJECT_TEMPLATE = r"""/* cueb_inject.js — 首经贸等级徽章 + 右键查询 toast（build_fork.py 生成） */
(function () {
  "use strict";
  if (!self.__CUEB_TIERS__ || !self.__cuebMakeLookup) return;
  var L = self.__cuebMakeLookup();
  var SHOW_MISS = false;          /* 徽章：未收录时是否显示灰色提示 */
  var AJG_RANK = { "4*": 5, "4": 4, "3": 3, "2": 2, "1": 1 };
  var AJG_MIN = 3;                /* ABS 标签最低显示档位（默认只标 3 及以上，改小则全显） */

  var COLORS = {
    "A+": ["#b8860b", "#ffffff"], "A1": ["#1a6dd4", "#ffffff"],
    "A2": ["#2e8b57", "#ffffff"], "B1": ["#5f6b7a", "#ffffff"],
    "B2": ["#6b5b95", "#ffffff"]
  };
  function chipStyle(bg, fg) {
    return "display:inline-block;margin:0 4px;padding:0 6px;border-radius:3px;" +
      "font-size:11px;line-height:17px;vertical-align:middle;white-space:nowrap;" +
      "font-weight:600;background:" + bg + ";color:" + fg + ";";
  }
  function tierSource(journal) {          /* 该等级的数据来源：cssci=按校规B2折算 */
    var D = self.__CUEB_TIERS__;
    return (D.src && D.src[L.norm(journal)]) || "";
  }
  function sourceNote(via) {
    if (via === "cssci") return "｜依据：CSSCI来源期刊目录（2025-2026）→ 校规中文B2";
    if (via === "cscd") return "｜依据：CSCD核心库（2025-2026）→ 校规中文B2";
    if (via === "ssci") return "｜依据：SSCI期刊列表（Clarivate 2026-08）→ 校规国际B2";
    return "";
  }
  function innerChip(text, style, title) {
    var s = document.createElement("span");
    s.className = "cueb-chip";
    s.textContent = text;
    s.setAttribute("style", style);
    if (title) s.title = title;
    return s;
  }
  function buildChips(tier, journal) {    /* 多标签：等级 + CSSCI/CSCD/UTD24/FT50 收录 */
    var D = self.__CUEB_TIERS__;
    var n = L.norm(journal);
    var wrap = document.createElement("span");
    wrap.className = "cueb-flag";
    if (tier) {
      var c = COLORS[tier.slice(-2)] || COLORS["A1"];
      var mainTitle = "首都经济贸易大学期刊目录（2024年版）：" + tier +
        sourceNote(tierSource(journal)) + (journal ? "｜" + journal : "");
      wrap.appendChild(innerChip("首经贸 " + tier, chipStyle(c[0], c[1]), mainTitle));
    }
    if (D.inCssci && D.inCssci[n]) {
      var st = tier === "中文B2" ? "（校规计为中文B2）" : "";
      wrap.appendChild(innerChip("CSSCI", chipStyle("#0e7490", "#ffffff"),
        "CSSCI来源期刊目录（2025-2026）收录" + st + (journal ? "｜" + journal : "")));
    }
    if (D.inCscd && D.inCscd[n]) {
      var sc = tier === "中文B2" ? "（校规计为中文B2）" : "";
      wrap.appendChild(innerChip("CSCD核心", chipStyle("#475569", "#ffffff"),
        "CSCD核心库（2025-2026）收录" + sc + (journal ? "｜" + journal : "")));
    }
    if (D.inSsci && D.inSsci[n]) {
      var sb = tier === "国际B2" ? "（校规计为国际B2）" : "";
      wrap.appendChild(innerChip("SSCI", chipStyle("#166534", "#ffffff"),
        "SSCI（社会科学引文索引，Clarivate）收录" + sb + (journal ? "｜" + journal : "")));
    }
    if (D.inJcr && D.inJcr[n]) {
      var jq = D.inJcr[n];
      wrap.appendChild(innerChip("JCR " + jq, chipStyle(jq === "Q1" ? "#4c1d95" : "#7c3aed", "#ffffff"),
        "JCR 2025 学科分区 " + jq +
        ((D.inJcrCat && D.inJcrCat[n]) ? "｜" + D.inJcrCat[n] : "") +
        (journal ? "｜" + journal : "")));
    }
    if (D.inUtd24 && D.inUtd24[n]) {
      wrap.appendChild(innerChip("UTD24", chipStyle("#7f1d1d", "#ffffff"),
        "UTD24：UT Dallas 24种商科顶级期刊收录" + (journal ? "｜" + journal : "")));
    }
    if (D.inFt50 && D.inFt50[n]) {
      wrap.appendChild(innerChip("FT50", chipStyle("#be185d", "#ffffff"),
        "FT50：金融时报50种商科期刊（2026版）收录" + (journal ? "｜" + journal : "")));
    }
    if (D.inAjg && D.inAjg[n] && AJG_RANK[D.inAjg[n]] >= AJG_MIN) {
      var ag = D.inAjg[n];
      wrap.appendChild(innerChip("ABS " + ag, chipStyle("#1e3a8a", "#ffffff"),
        "AJG 2024（英国商学院协会期刊指南，原ABS榜）评级 " + ag +
        (journal ? "｜" + journal : "")));
    }
    return wrap;
  }

  /* ---- 徽章：挂在 easyScholarPaperFlag 旁边 ---- */
  function stamp() {
    var names = window.__cuebNames || {};
    var flags = document.querySelectorAll("span.easyScholarPaperFlag[paperID]");
    for (var i = 0; i < flags.length; i++) {
      var el = flags[i];
      if (el.querySelector(".cueb-flag")) continue;
      var name = names[el.getAttribute("paperID")];
      if (!name) continue;
      var D = self.__CUEB_TIERS__, n = L.norm(name);
      var tier = L.lookup(name);
      var gAbs = D.inAjg && D.inAjg[n];
      var memberOnly = !tier && ((D.inUtd24 && D.inUtd24[n]) || (D.inFt50 && D.inFt50[n]) ||
        (gAbs && AJG_RANK[gAbs] >= AJG_MIN) || (D.inJcr && D.inJcr[n]));
      if (tier || memberOnly) {           /* 校目录无等级但有收录/分区标签 → 只亮收录标签 */
        el.appendChild(buildChips(tier, name));
      } else if (SHOW_MISS) {
        var miss = document.createElement("span");
        miss.className = "cueb-flag";
        miss.textContent = "首经贸 未收录";
        miss.setAttribute("style", chipStyle("#cccccc", "#444444"));
        miss.title = "未列入首经贸2024目录枚举清单（可能属于B2/C规则级别）";
        el.appendChild(miss);
      }
    }
  }
  var t = null;
  try {
    new MutationObserver(function () {
      if (t) clearTimeout(t);
      t = setTimeout(stamp, 250);
    }).observe(document.documentElement, { childList: true, subtree: true });
  } catch (e) {}
  setInterval(stamp, 2000);

  /* ---- 右键查询结果 toast ---- */
  var TOAST_COLORS = { "符合": "#2e8b57", "待核实": "#8a6d3b" };
  function showToast(msg) {
    var box = document.createElement("div");
    box.className = "cueb-toast";
    var inner = "<div style=\"font-weight:700;margin-bottom:4px;\">首经贸期刊等级查询</div>" +
      "<div style=\"font-size:12px;opacity:.85;margin-bottom:6px;\">" +
      escapeHtml(msg.query) + "</div>";
    if (msg.tier) {
      var c = COLORS[msg.tier.slice(-2)] || COLORS["A1"];
      var D = self.__CUEB_TIERS__, n = L.norm(msg.query), tags = [];
      if (D.inCssci && D.inCssci[n]) tags.push("CSSCI");
      if (D.inCscd && D.inCscd[n]) tags.push("CSCD核心");
      if (D.inSsci && D.inSsci[n]) tags.push("SSCI");
      if (D.inUtd24 && D.inUtd24[n]) tags.push("UTD24");
      if (D.inFt50 && D.inFt50[n]) tags.push("FT50");
      if (D.inAjg && D.inAjg[n] && AJG_RANK[D.inAjg[n]] >= AJG_MIN) tags.push("ABS " + D.inAjg[n]);
      if (D.inJcr && D.inJcr[n]) tags.push("JCR " + D.inJcr[n]);
      var sub = msg.tier === "国际B2" ? "SSCI收录（校规计为国际B2）"
        : msg.tier.slice(-2) === "B2"
          ? (tags.length ? tags.join("＋") + "收录（校规计为中文B2）" : "校规B2来源")
          : (tags.length ? "校目录等级｜另收录：" + tags.join("＋") : "校目录清单等级");
      inner += "<span style=\"" + chipStyle(c[0], c[1]) + "\">" + msg.tier + "</span>" +
        "<span style=\"font-size:11px;opacity:.7;margin-left:6px;\">" + sub + "</span>";
    } else {
      var D2 = self.__CUEB_TIERS__, n2 = L.norm(msg.query), mtags = [];
      if (D2.inUtd24 && D2.inUtd24[n2]) mtags.push("UTD24");
      if (D2.inFt50 && D2.inFt50[n2]) mtags.push("FT50");
      if (D2.inAjg && D2.inAjg[n2] && AJG_RANK[D2.inAjg[n2]] >= AJG_MIN) mtags.push("ABS " + D2.inAjg[n2]);
      if (D2.inJcr && D2.inJcr[n2]) mtags.push("JCR " + D2.inJcr[n2]);
      if (mtags.length) {
        var mcolor = { "UTD24": "#7f1d1d", "FT50": "#be185d", "JCR Q1": "#4c1d95", "JCR Q2": "#7c3aed" };
        var chipsHtml = "";
        for (var mi = 0; mi < mtags.length; mi++) {
          chipsHtml += "<span style=\"" +
            chipStyle(mcolor[mtags[mi]] || "#1e3a8a", "#ffffff") + "\">" +
            escapeHtml(mtags[mi]) + "</span>";
        }
        inner += "<div>" + chipsHtml +
          "<span style=\"font-size:11px;opacity:.7;margin-left:6px;\">国际权威榜单收录（首经贸校目录未枚举）</span></div>";
      } else {
        inner += "<span style=\"font-size:12px;color:#e8c268;\">未列入目录枚举清单（待核实：可能属B2/C规则级别或刊名异写）</span>";
      }
      if (msg.candidates && msg.candidates.length) {
        inner += "<div style=\"font-size:11px;opacity:.8;margin-top:5px;\">近似：" +
          msg.candidates.map(function (c) {
            return escapeHtml(c.name ? c.name + "（" + c.level + "）" : c.level);
          }).join("、") + "</div>";
      }
    }
    box.innerHTML = inner;
    box.setAttribute("style",
      "position:fixed;top:12%;left:50%;transform:translateX(-50%);z-index:2147483647;" +
      "background:rgba(23,32,42,.94);color:#fff;padding:10px 16px;border-radius:8px;" +
      "font-size:13px;font-family:system-ui,'Microsoft YaHei',sans-serif;" +
      "box-shadow:0 6px 24px rgba(0,0,0,.35);max-width:70vw;");
    document.documentElement.appendChild(box);
    setTimeout(function () {
      box.style.transition = "opacity .4s";
      box.style.opacity = "0";
      setTimeout(function () { box.remove(); }, 450);
    }, 4200);
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  try {
    chrome.runtime.onMessage.addListener(function (msg) {
      if (msg && msg.type === "__cueb_result") { showToast(msg); }
    });
  } catch (e) {}

  window.__CUEB_LOOKUP__ = L.lookup;   /* 控制台可调试 */
  console.log("[CUEB] 首经贸等级徽章已加载 v" + self.__CUEB_TIERS__.version +
              " 条目 " + Object.keys(self.__CUEB_TIERS__.byName).length);
})();
"""

BG_TEMPLATE = r"""/* ---- cueb 后台追加：右键菜单查询（build_fork.py 生成） ---- */
(function () {
  "use strict";
  if (!self.__cuebMakeLookup || !chrome.contextMenus) return;
  var L = self.__cuebMakeLookup();
  var MID = "cueb-selection-lookup";
  chrome.contextMenus.removeAll(function () {
    chrome.contextMenus.create({
      id: MID,
      title: "首经贸期刊等级查询：「%s」",
      contexts: ["selection"]
    });
  });
  chrome.contextMenus.onClicked.addListener(function (info, tab) {
    if (info.menuItemId !== MID || !info.selectionText) return;
    var q = String(info.selectionText).trim();
    var tier = L.lookup(q);
    var payload = { type: "__cueb_result", query: q, tier: tier,
                    candidates: tier ? [] : L.candidates(q, 3) };
    if (tab && typeof tab.id === "number" && tab.id >= 0) {
      chrome.tabs.sendMessage(tab.id, payload, function () {
        if (chrome.runtime.lastError) {   /* 页面无内容脚本（PDF/受限页）→ 工具栏徽标 */
          void chrome.runtime.lastError;
          chrome.action.setBadgeBackgroundColor({ color: tier ? "#2e8b57" : "#8a6d3b" });
          chrome.action.setBadgeText({ text: tier ? tier.replace(/^(中文|国际)/, "") : "未收录" });
          chrome.action.setTitle({ title: "首经贸「" + q + "」：" + (tier || "未列入枚举清单，待核实") });
          setTimeout(function () { chrome.action.setBadgeText({ text: "" }); }, 8000);
        }
      });
    }
  });
})();
"""


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", s)


def norm_issn(s):
    s = re.sub(r"[^0-9xX]", "", str(s or "")).upper()
    return s if re.fullmatch(r"\d{7}[\dX]", s) else ""


def member_keys(name, aliases=()):
    """收录名单（UTD24/FT50）匹配键扩展：官方写法与站点显示写法不一时也能命中
    —— the-前缀差异（The Accounting Review vs Accounting Review）、
       & 与 and 差异（Manufacturing & Service Operations Management）、
       官方异名（Journal on Computing = INFORMS Journal on Computing）"""
    keys = set()
    for v in [str(name or "")] + list(aliases):
        k = norm(v)
        if not k:
            continue
        keys.add(k)
        if k.startswith("the") and len(k) > 4:
            keys.add(k[3:])
        else:
            keys.add("the" + k)
        # & 与 and 双向补齐（FT50 官方用 &，UTD24 官方用 and，站点显示两种都有）
        if "&" in v or re.search(r"\band\b", v, re.I):
            keys.add(norm(v.replace("&", " and ")))
            keys.add(norm(re.sub(r"\band\b", "&", v, flags=re.I)))
    return keys


def build_data(catalog_path, cssci_path, cscd_path, utd24_path=None, ft50_path=None,
               ajg_path=None, ssci_path=None, jcr_path=None):
    if not catalog_path or not os.path.exists(catalog_path):
        sys.exit("缺少必需的校目录数据 cueb_journal_catalog_2024.json——把它放到仓库 data/ 目录"
                 "（来源见 data/README.md）后重跑。其余数据集缺失只会少对应标签。")
    with open(catalog_path, encoding="utf-8") as f:
        cat = json.load(f)
    sha = hashlib.sha256(open(catalog_path, "rb").read()).hexdigest()[:12]
    by_name, by_issn, conflicts = {}, {}, []
    disp, src = {}, {}
    cssci_meta = cscd_meta = utd24_meta = ft50_meta = ajg_meta = ssci_meta = jcr_meta = None
    in_cssci, in_cscd = {}, {}          # 收录事实（与等级优先级解耦，供多标签展示）
    in_utd24, in_ft50 = {}, {}          # 英文商科顶刊收录事实（不参与校等级折算）
    in_ajg = {}                          # AJG/ABS 2024 分档（值=档位，仅收录标签）
    in_ssci = {}                         # SSCI 收录（新刊按校规计为国际B2）
    in_jcr, in_jcr_cat = {}, {}          # JCR 2025 最优学科分区（仅 Q1/Q2）+ 学科悬停串

    def put(name, tier, via=None):
        k = norm(name)
        if by_name.get(k, tier) != tier:
            conflicts.append((k, by_name[k], tier))
        by_name[k] = tier
        disp.setdefault(k, str(name))
        if via:
            src.setdefault(k, via)

    for level in cat["international"]["levels_order"]:
        lv = cat["international"]["levels"][level]
        for disc, d in (lv.get("disciplines") or {}).items():
            for j in d["journals"]:
                by_issn.setdefault(norm_issn(j["issn"]), f"国际{level}")
                put(j["name"], f"国际{level}")
    for level in cat["chinese"]["levels_order"]:
        for name in cat["chinese"]["levels"][level].get("journals", []):
            put(name, f"中文{level}")
    put("求是", "中文A2")
    # CSSCI 来源期刊（2025-2026）：校目录枚举清单优先，其余按校规计为中文B2
    n_cssci = n_cssci_new = 0
    if cssci_path and os.path.exists(cssci_path):
        with open(cssci_path, encoding="utf-8") as f:
            cssci = json.load(f)
        cssci_meta = cssci.get("meta", {})
        for e in cssci.get("journals", []):
            k = norm(e["name"])
            n_cssci += 1
            in_cssci[k] = 1
            if k not in by_name:
                put(e["name"], "中文B2", "cssci")
                n_cssci_new += 1
    # CSCD 核心库（2025-2026）：同上；ISSN 仅在无既有映射时补充
    n_cscd = n_cscd_new = 0
    if cscd_path and os.path.exists(cscd_path):
        with open(cscd_path, encoding="utf-8") as f:
            cscd = json.load(f)
        cscd_meta = cscd.get("meta", {})
        for e in cscd.get("journals", []):
            k = norm(e["name"])
            n_cscd += 1
            in_cscd[k] = 1
            if k not in by_name:
                put(e["name"], "中文B2", "cscd")
                n_cscd_new += 1
            iss = norm_issn(e.get("issn"))
            if iss:
                by_issn.setdefault(iss, "中文B2")
    # UTD24 / FT50：仅作收录标签，不产生校等级
    n_utd = n_ft = 0
    if utd24_path and os.path.exists(utd24_path):
        with open(utd24_path, encoding="utf-8") as f:
            utd = json.load(f)
        utd24_meta = utd.get("meta", {})
        for e in utd.get("journals", []):
            n_utd += 1
            for k in member_keys(e["name"], WEBLIST_ALIASES.get(str(e["name"]).strip(), ())):
                in_utd24[k] = 1
    if ft50_path and os.path.exists(ft50_path):
        with open(ft50_path, encoding="utf-8") as f:
            ft = json.load(f)
        ft50_meta = ft.get("meta", {})
        for e in ft.get("journals", []):
            n_ft += 1
            for k in member_keys(e["name"]):
                in_ft50[k] = 1
    # AJG 2024（原ABS榜）：值为档位 4*/4/3/2/1，仅作收录标签，不产生校等级
    n_ajg = 0
    if ajg_path and os.path.exists(ajg_path):
        with open(ajg_path, encoding="utf-8") as f:
            ajg = json.load(f)
        ajg_meta = ajg.get("meta", {})
        for e in ajg.get("journals", []):
            n_ajg += 1
            for k in member_keys(e["name"]):
                in_ajg[k] = str(e["rating"]).strip()
    # SSCI（2026-08 官方快照）：校目录枚举优先，新刊按校规折算为国际B2；
    # 与 CSSCI/CSCD 的中文B2 同一套"枚举缺失→规则级别"逻辑
    n_ssci = n_ssci_new = 0
    if ssci_path and os.path.exists(ssci_path):
        with open(ssci_path, encoding="utf-8") as f:
            ssci = json.load(f)
        ssci_meta = ssci.get("meta", {})
        for e in ssci.get("journals", []):
            k = norm(e["name"])
            n_ssci += 1
            in_ssci[k] = 1
            # the-变体碰撞：SSCI 写法常无 The（ACCOUNTING REVIEW），校目录可能写
            # The Accounting Review——直接查/the 回退能命中的不折算为国际B2（防降级）
            alt = k[3:] if k.startswith("the") and len(k) > 4 else "the" + k
            if k not in by_name and alt not in by_name:
                put(e["name"], "国际B2", "ssci")
                n_ssci_new += 1
            for iss in (norm_issn(e.get("issn")), norm_issn(e.get("eissn"))):
                if iss:
                    by_issn.setdefault(iss, "国际B2")
    # JCR 2025 学科分区：仅收录标签（值=Q1/Q2，数据集已按用户设定只留这两档）
    n_jcr = 0
    if jcr_path and os.path.exists(jcr_path):
        with open(jcr_path, encoding="utf-8") as f:
            jcr = json.load(f)
        jcr_meta = jcr.get("meta", {})
        for e in jcr.get("journals", []):
            n_jcr += 1
            k0 = norm(e["name"])
            for k in member_keys(e["name"]):
                in_jcr[k] = str(e["best"]).strip()
            hover = str(e.get("index") or "")
            cats = e.get("cats") or []
            if cats:
                hover = (hover + "｜" if hover else "") + "｜".join(cats)
            if hover:
                in_jcr_cat[k0] = hover
    if conflicts:
        print("WARN 同名不同级:", conflicts)
    return {
        "version": cat["meta"]["effective_date"] + "/" + sha,
        "source": "首经贸学术〔2024〕1号",
        "cssci": {"version": cssci_meta.get("title", ""), "total": n_cssci} if cssci_meta else None,
        "cscd": {"version": cscd_meta.get("title", ""), "total": n_cscd} if cscd_meta else None,
        "utd24": {"total": n_utd} if utd24_meta else None,
        "ft50": {"total": n_ft} if ft50_meta else None,
        "ajg": {"total": n_ajg} if ajg_meta else None,
        "ssci": {"total": n_ssci} if ssci_meta else None,
        "byName": by_name,
        "byIssn": by_issn,
        "disp": disp,
        "src": src,
        "inCssci": in_cssci,
        "inCscd": in_cscd,
        "inUtd24": in_utd24,
        "inFt50": in_ft50,
        "inAjg": in_ajg,
        "inSsci": in_ssci,
        "inJcr": in_jcr,
        "inJcrCat": in_jcr_cat,
    }, len(by_name), len(by_issn), conflicts, n_cssci, n_cssci_new, n_cscd, n_cscd_new, \
        n_utd, n_ft, n_ajg, n_ssci, n_ssci_new, n_jcr


def node_check(path):
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"JS 语法校验失败 {path}:\n{r.stderr}")
        print(f"  node --check OK: {os.path.basename(path)}")


def main():
    manifests = sorted(glob.glob(SRC_GLOB))
    if not manifests:
        sys.exit("未找到已安装的 easyScholar")
    src_dir = os.path.dirname(manifests[-1])
    with open(manifests[-1], encoding="utf-8-sig") as f:
        manifest = json.load(f)
    print(f"源: easyScholar {manifest.get('version')} @ {src_dir}")

    data, n_name, n_issn, conflicts, n_cssci, n_cssci_new, n_cscd, n_cscd_new, \
        n_utd, n_ft, n_ajg, n_ssci, n_ssci_new, n_jcr = build_data(
        DEFAULT_CATALOG, DEFAULT_CSSCI, DEFAULT_CSCD, DEFAULT_UTD24, DEFAULT_FT50,
        DEFAULT_AJG, DEFAULT_SSCI, DEFAULT_JCR)
    print(f"目录数据: byName {n_name} / byIssn {n_issn} / 同名不同级 {len(conflicts)}")
    print(f"CSSCI: 收录 {n_cssci}，其中新增为中文B2 {n_cssci_new}（其余保持校目录更高级别）")
    print(f"CSCD核心库: 收录 {n_cscd}，其中新增为中文B2 {n_cscd_new}（其余保持更高级别）")
    print(f"SSCI: 收录 {n_ssci}，其中新增为国际B2 {n_ssci_new}（其余保持更高级别）")
    print(f"UTD24: {n_utd} 种｜FT50: {n_ft} 种｜AJG2024: {n_ajg} 种｜JCR Q1/Q2: {n_jcr} 种"
          f"（键数 inJcr={len(data['inJcr'])}）")

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(src_dir, OUT)

    # 1) utils.js 钩子
    utils_path = os.path.join(OUT, "show_ranking", "ranking", "utils.js")
    src_js = open(utils_path, encoding="utf-8").read()
    anchor = "function o(e,a){"
    if src_js.count(anchor) != 1:
        sys.exit(f"锚点异常: 'function o(e,a){{' 出现 {src_js.count(anchor)} 次，官方代码结构可能已变化")
    open(utils_path, "w", encoding="utf-8").write(src_js.replace(anchor, anchor + HOOK, 1))
    print(f"  钩子已插入 utils.js（+{len(HOOK)} 字符）")
    node_check(utils_path)

    # 2) cueb_data.js（共享数据+匹配逻辑）
    data_js = os.path.join(OUT, "cueb_data.js")
    open(data_js, "w", encoding="utf-8").write(
        DATA_TEMPLATE.replace("%DATA%", json.dumps(data, ensure_ascii=False)))
    node_check(data_js)

    # 3) cueb_inject.js（徽章+toast）
    inject = os.path.join(OUT, "cueb_inject.js")
    open(inject, "w", encoding="utf-8").write(INJECT_TEMPLATE)
    node_check(inject)

    # 4) service worker：importScripts 数据 + 追加右键菜单逻辑
    sw_path = os.path.join(OUT, "show_ranking", "ranking", "service_worker.js")
    sw = open(sw_path, encoding="utf-8").read()
    if "cueb-selection-lookup" not in sw:
        sw += "\n" + BG_TEMPLATE.replace(
            "(function () {", "importScripts('/cueb_data.js');\n(function () {", 1)
        open(sw_path, "w", encoding="utf-8").write(sw)
    print("  service_worker 已追加右键菜单逻辑")
    node_check(sw_path)

    # 5) manifest：content_scripts 追加两个文件 + contextMenus 权限 + 版本标记
    for block in manifest.get("content_scripts", []):
        block.setdefault("js", []).extend(["cueb_data.js", "cueb_inject.js"])
    perms = manifest.setdefault("permissions", [])
    if "contextMenus" not in perms:
        perms.append("contextMenus")
    if manifest.pop("update_url", None):
        print("  manifest: 已移除 update_url（切断商店自动更新关联）")
    upstream = manifest["version"]
    manifest["version"] = f"{upstream}.{FORK_PATCH}"          # 只允许点分整数
    manifest["version_name"] = f"{upstream}-cueb.{FORK_PATCH}"  # 显示用，可含字母
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("  manifest: content_scripts 已追加 cueb_data.js/cueb_inject.js，permissions +contextMenus")
    print(f"\n完成 → {OUT}\n加载/更新: edge://extensions → 开发人员模式 → 加载解压缩的扩展选 dist"
          f"（或对已加载分支点重新加载）")


if __name__ == "__main__":
    main()
