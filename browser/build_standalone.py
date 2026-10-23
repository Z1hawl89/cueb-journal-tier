#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_standalone.py — 生成"首经贸期刊等级助手"独立扩展（不依赖 easyScholar）

与分支（fork）的关系：二选一使用。分支功能全（157站徽章+收藏等），独立版只做
两件事且完全离线：①右键框选查等级（任意网页）②在少数常用学术站点自行识别
期刊并加徽章（选择器移植自 easyScholar 实战代码）。
数据由 build_fork.build_data 生成，与分支完全同源。
"""
import json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_fork import (build_data, DEFAULT_CATALOG, DEFAULT_CSSCI,
                        DEFAULT_CSCD, DEFAULT_UTD24, DEFAULT_FT50, DEFAULT_AJG,
                        DEFAULT_SSCI, DEFAULT_JCR, node_check)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "standalone")

MANIFEST = {
    "manifest_version": 3,
    "name": "首经贸期刊等级助手",
    "version": "1.6.2",
    "description": "首都经济贸易大学期刊目录（2024版，含CSSCI/CSCD折算中文B2、SSCI折算国际B2）+ UTD24/FT50/AJG/JCR分区收录标签：右键框选查等级；百度学术/谷歌学术（含国内镜像）/知网/万方/ScienceDirect/Springer/PubMed/Web of Science 自动徽章。完全本地运行。",
    "permissions": ["contextMenus"],
    "background": {"service_worker": "background.js"},
    "action": {},
    "icons": {},
    "content_scripts": [{
        "matches": ["https://*/*", "http://*/*"],
        "js": ["cueb_data.js", "content.js"],
        "run_at": "document_end"
    }]
}

BACKGROUND = r"""/* background.js — 右键菜单（独立版，仅本地数据） */
importScripts('/cueb_data.js');
(function () {
  "use strict";
  if (!self.__cuebMakeLookup || !chrome.contextMenus) return;
  var L = self.__cuebMakeLookup();
  var MID = "cueb-sa-selection-lookup";
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
        if (chrome.runtime.lastError) {
          void chrome.runtime.lastError;
          chrome.action.setBadgeBackgroundColor({ color: tier ? "#2e8b57" : "#8a6d3b" });
          chrome.action.setBadgeText({ text: tier ? tier.replace(/^(中文|国际)/, "") : "未收录" });
          chrome.action.setTitle({ title: "首经贸「" + q + "」：" + (tier || "未列入清单，待核实") });
          setTimeout(function () { chrome.action.setBadgeText({ text: "" }); }, 8000);
        }
      });
    }
  });
})();
"""

CONTENT = r"""/* content.js — 独立版：右键结果 toast + 常用站点徽章（选择器移植自 easyScholar） */
(function () {
  "use strict";
  if (!self.__CUEB_TIERS__ || !self.__cuebMakeLookup) return;
  var L = self.__cuebMakeLookup();
  var COLORS = {
    "A+": ["#b8860b", "#ffffff"], "A1": ["#1a6dd4", "#ffffff"],
    "A2": ["#2e8b57", "#ffffff"], "B1": ["#5f6b7a", "#ffffff"],
    "B2": ["#6b5b95", "#ffffff"]
  };
  var AJG_RANK = { "4*": 5, "4": 4, "3": 3, "2": 2, "1": 1 };
  var AJG_MIN = 3;                /* ABS 标签最低显示档位（默认只标 3 及以上，改小则全显） */
  function chipStyle(bg, fg) {
    return "display:inline-block;margin:0 4px;padding:0 6px;border-radius:3px;" +
      "font-size:11px;line-height:17px;vertical-align:middle;white-space:nowrap;" +
      "font-weight:600;background:" + bg + ";color:" + fg + ";";
  }
  function tierSource(journal) {
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
  function clean(s) {
    return String(s || "").replace(/[《》\s]+/g, " ").trim();
  }
  /* 期刊导航链接（navi.cnki.net/knavi/detail）：知网高级检索页的选刊链接、
     期刊导航站的条目都指向期刊详情。链接文字即刊名。
     跳过结果表格/详情标题（已有专门处理）；data-cueb-scan 防未命中条目反复重扫 */
  function knaviLinks() {
    var out = [];
    var links = document.querySelectorAll('a[href*="knavi/detail"]');
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      if (a.getAttribute("data-cueb-sa") === "1") continue;
      if (a.getAttribute("data-cueb-scan") === "1") continue;
      if (a.closest && (a.closest(".result-table-list") || a.closest(".wx-tit"))) continue;
      var j = clean(a.textContent);
      if (!j) continue;
      a.setAttribute("data-cueb-scan", "1");
      out.push({ anchor: a, journal: j });
    }
    return out;
  }

  /* ---------------- 站点抓取表（选择器移植自 easyScholar v15.4） ---------------- */
  function rowCollect(sel, fn) {
    var out = [];
    var rows = document.querySelectorAll(sel);
    for (var i = 0; i < rows.length; i++) {
      var r = fn(rows[i]);
      if (r) out.push(r);
    }
    return out;
  }
  function txt(el) { return el ? el.textContent.trim() : ""; }

  var SITES = [
    { host: "xueshu.baidu.com",
      find: function () {
        return rowCollect("div.result", function (row) {
          var t = row.querySelector("h3.paper-title");
          if (!t || t.querySelector(".cueb-flag")) return null;
          var j = txt(row.querySelector(".paper-info a[href*='data/journal']"));
          if (!j) {
            var spans = row.querySelectorAll(".paper-info span");
            for (var i = 0; i < spans.length; i++) {
              if (spans[i].textContent.indexOf("《") >= 0 && spans[i].textContent.indexOf("》") >= 0) {
                j = spans[i].textContent; break;
              }
            }
          }
          j = clean(j);
          return j ? { anchor: t, journal: j } : null;
        });
      } },
    { host: "scholar.google.com",
      match: function (h) {          /* 谷歌学术各国域名 + 国内镜像（整站克隆，选择器通用） */
        return h.indexOf("scholar.google") >= 0 ||
          h.indexOf("lanfanshu.cn") >= 0 ||
          h === "sc.panda321.com" || h === "panda321.com" || h.endsWith(".panda321.com") ||
          h === "scholar.ustc.cf" ||
          h === "dailyheadlines.cc" || h.endsWith(".dailyheadlines.cc");
      },
      find: function () {
        /* 2025 谷歌学术改版后新旧两代引文行并存，且外层容器类名不稳定——
           统一以 div.gs_a 引文行为锚，不依赖外层结构：
           新版 .gs_fma_p：作者在 .gs_fmaa 子块里，期刊名+年份是其后的裸文本
                          （"Journal Name, 2025"），gs_pdot • 后是出版社；
           旧版 .gs_fma_s：行内文本 "作者 - 期刊, 年份 - 出版社"。 */
        var out = [];
        var metas = document.querySelectorAll("div.gs_a");
        for (var i = 0; i < metas.length; i++) {
          var m = metas[i];
          if (m.getAttribute("data-cueb-sa") === "1") continue;
          var j = "";
          var authors = m.querySelector(".gs_fmaa");
          if (authors) {
            var t = m.textContent || "";
            var at = authors.textContent || "";
            var p = t.indexOf(at);
            var tail = p >= 0 ? t.slice(p + at.length) : t;
            var mm = tail.match(/^(.*),\s*\d{4}/);
            if (mm) j = mm[1];
          } else {
            var r = (m.textContent || "").match(/- (.*)(?=, \d{4})/);
            if (r) j = r[1];
          }
          j = clean(j);
          if (!j || j.indexOf("…") >= 0) continue;   /* 期刊名被谷歌截断的不硬匹配 */
          out.push({ anchor: m, journal: j });
        }
        return out;
      } },
    { host: "kns.cnki.net",
      find: function () {
        var out = rowCollect("table.result-table-list tbody tr", function (tr) {
          var src = tr.querySelector("td.source"), t = tr.querySelector("td.name");
          if (!src || !t || t.querySelector(".cueb-flag")) return null;
          var j = txt(src.querySelector("a")) || txt(src);
          return j ? { anchor: t, journal: clean(j) } : null;
        });
        var h1 = document.querySelector(".wx-tit h1");
        if (h1 && !h1.querySelector(".cueb-flag") && !h1.getAttribute("data-cueb-sa")) {
          var j = txt(document.querySelector(".doc-top .top-tip a"));
          if (j) out.push({ anchor: h1, journal: clean(j) });
        }
        /* 高级检索页选刊链接、其他期刊导航链接 */
        return out.concat(knaviLinks());
      } },
    { host: "navi.cnki.net",
      find: function () { return knaviLinks(); } },
    { host: "www.wanfangdata.com.cn",
      find: function () {
        var out = [];
        var t = document.querySelector("div.detailTitle div.detailTitleCN");
        if (t && !t.querySelector(".cueb-flag") && !t.getAttribute("data-cueb-sa")) {
          var j = txt(document.querySelector("div.periodicalInformation div.periodicalName a"));
          if (j) { t.setAttribute("data-cueb-sa", "1"); out.push({ anchor: t, journal: clean(j) }); }
        }
        out = out.concat(rowCollect("tbody.paperInfoItem tr", function (tr) {
          var tt = tr.querySelector("td span");
          var ja = tr.querySelector("a[href*='sns.wanfangdata.com.cn/perio']");
          if (!tt || !ja || tt.querySelector(".cueb-flag")) return null;
          return ja.textContent.trim() ? { anchor: tt, journal: clean(ja.textContent) } : null;
        }));
        return out;
      } },
    { host: "www.sciencedirect.com",
      find: function () {
        return rowCollect("li.ResultItem", function (row) {
          var t = row.querySelector("h2 span");
          if (!t || t.querySelector(".cueb-flag")) return null;
          var j = txt(row.querySelector("a[data-aa-name*='srp-srctitle-']"));
          return j ? { anchor: t, journal: clean(j) } : null;
        });
      } },
    { host: "link.springer.com",
      find: function () {
        return rowCollect("ol.u-list-reset > li", function (li) {
          var t = li.querySelector("h3");
          var j = txt(li.querySelector("em[data-test='journal-title']"));
          if (!t || !j || t.querySelector(".cueb-flag")) return null;
          return { anchor: t, journal: clean(j) };
        });
      } },
    { host: "pubmed.ncbi.nlm.nih.gov",
      find: function () {
        return rowCollect("article.full-docsum, article.article-overview", function (art) {
          var t = art.querySelector("a.docsum-title");
          if (!t || t.querySelector(".cueb-flag")) return null;
          var j = txt(art.querySelector("span.full-journal-citation span.abbr-title"));
          if (!j) {
            var c = txt(art.querySelector(".docsum-journal-citation"));
            var d = c.indexOf(".");
            j = d > 0 ? c.slice(0, d) : "";
          }
          return j ? { anchor: t, journal: clean(j) } : null;
        });
      } },
    { host: "webofscience.com",
      match: function (h) {          /* 新旧域名 + clarivate 托管入口 */
        return h.indexOf("webofscience") >= 0 || h.indexOf("webofknowledge") >= 0 ||
          h.indexOf("clarivate") >= 0;
      },
      find: function () {
        /* 移植自 easyScholar：WOS 每行结果/详情页右栏的 JCR 小组件（app-jcr-sidenav）
           内含期刊名（英文优先，去 arrow_drop_down 残留）；无 JCR 数据的行没有该组件 */
        return rowCollect("app-jcr-sidenav", function (sn) {
          if (sn.querySelector(".cueb-flag")) return null;
          var name = "";
          var cand = sn.querySelector("span[lang='en']") || sn.querySelector("a[lang='en']");
          if (!cand) cand = sn.querySelector("span[lang='zh-cn']") || sn.querySelector("a[lang='zh-cn']");
          name = clean(cand ? cand.textContent.replace(/arrow_drop_down/g, "") : "");
          if (!name) return null;
          var row = sn.closest && (sn.closest("app-record") || sn.closest("tr"));
          var t = row && (row.querySelector("a[data-ta*='title']") ||
                          row.querySelector(".search-results-title a") || row.querySelector("h3 a") ||
                          row.querySelector("h1"));
          return { anchor: t || sn, journal: name };
        });
      } }
  ];

  function stamp() {
    var host = location.hostname;
    for (var i = 0; i < SITES.length; i++) {
      var site = SITES[i];
      var hitHost = site.match ? site.match(host)
        : (host === site.host || host.endsWith("." + site.host));
      if (!hitHost) continue;
      var hits;
      try { hits = SITES[i].find(); } catch (e) { continue; }
      for (var k = 0; k < hits.length; k++) {
        var h = hits[k];
        if (h.anchor.getAttribute && h.anchor.getAttribute("data-cueb-sa") === "1") continue;
        var tier = L.lookup(h.journal);
        var D0 = self.__CUEB_TIERS__, n0 = L.norm(h.journal);
        var g0 = D0.inAjg && D0.inAjg[n0];
        var memberOnly = !tier && ((D0.inUtd24 && D0.inUtd24[n0]) || (D0.inFt50 && D0.inFt50[n0]) ||
          (g0 && AJG_RANK[g0] >= AJG_MIN) || (D0.inJcr && D0.inJcr[n0]));
        if (!tier && !memberOnly) continue;        /* 无等级且无收录标签不加徽章 */
        var group = buildChips(tier, h.journal);
        h.anchor.setAttribute("data-cueb-sa", "1");
        if (h.anchor.nextSibling && h.anchor.nextSibling.nodeType === 1 &&
            h.anchor.nextSibling.className === "cueb-flag") continue;
        h.anchor.insertAdjacentElement("afterend", group);
      }
    }
  }
  var t = null;
  try {
    new MutationObserver(function () {
      if (t) clearTimeout(t);
      t = setTimeout(stamp, 300);
    }).observe(document.documentElement, { childList: true, subtree: true });
  } catch (e) {}
  setInterval(stamp, 3000);

  /* ---------------- 右键查询结果 toast（与分支一致） ---------------- */
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function showToast(msg) {
    var box = document.createElement("div");
    box.className = "cueb-toast";
    var inner = "<div style=\"font-weight:700;margin-bottom:4px;\">首经贸期刊等级查询</div>" +
      "<div style=\"font-size:12px;opacity:.85;margin-bottom:6px;\">" + escapeHtml(msg.query) + "</div>";
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
        inner += "<span style=\"font-size:12px;color:#e8c268;\">未列入清单（待核实：可能属规则级别或刊名异写）</span>";
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
  try {
    chrome.runtime.onMessage.addListener(function (msg) {
      if (msg && msg.type === "__cueb_result") showToast(msg);
    });
  } catch (e) {}
  window.__CUEB_LOOKUP__ = L.lookup;
  console.log("[CUEB-SA] 首经贸独立助手已加载 v" + self.__CUEB_TIERS__.version +
              " 条目 " + Object.keys(self.__CUEB_TIERS__.byName).length);
})();
"""


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    data, n_name, n_issn, conflicts, n_cssci, n_cssci_new, n_cscd, n_cscd_new,         n_utd, n_ft, n_ajg, n_ssci, n_ssci_new, n_jcr = build_data(
        DEFAULT_CATALOG, DEFAULT_CSSCI, DEFAULT_CSCD, DEFAULT_UTD24, DEFAULT_FT50,
        DEFAULT_AJG, DEFAULT_SSCI, DEFAULT_JCR)
    print(f"数据: byName {n_name} / byIssn {n_issn} | CSSCI+B2 {n_cssci_new} | CSCD+B2 {n_cscd_new}"
          f" | SSCI→国际B2 {n_ssci_new} | UTD24 {n_utd} | FT50 {n_ft} | AJG {n_ajg} | JCR Q1/Q2 {n_jcr}")

    # cueb_data.js 与分支同源（DATA_TEMPLATE + 同一份 build_data 产物）
    from build_fork import DATA_TEMPLATE
    open(os.path.join(OUT, "cueb_data.js"), "w", encoding="utf-8").write(
        DATA_TEMPLATE.replace("%DATA%", json.dumps(data, ensure_ascii=False)))
    node_check(os.path.join(OUT, "cueb_data.js"))

    open(os.path.join(OUT, "background.js"), "w", encoding="utf-8").write(BACKGROUND)
    node_check(os.path.join(OUT, "background.js"))
    open(os.path.join(OUT, "content.js"), "w", encoding="utf-8").write(CONTENT)
    node_check(os.path.join(OUT, "content.js"))

    man = dict(MANIFEST)
    man["version_name"] = man["version"] + " (standalone)"
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print(f"完成 → {OUT}\n用法: edge://extensions → 开发人员模式 → 加载解压缩的扩展 → 选 standalone 目录"
          f"\n注意: 与分支(fork)二选一启用，避免受支持站点上出现双重徽章")


if __name__ == "__main__":
    main()
