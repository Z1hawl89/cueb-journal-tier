/* test_zotero.js — Zotero 插件烟雾测试：桩 Zotero → 真实跑 startup + dataProvider
 * 用法: node test_zotero.js
 */
"use strict";
const fs = require("fs");
const path = require("path");

const DIR = path.join(__dirname, "zotero");
let captured = null;                       /* registerColumn 收到的配置 */
const debugLines = [];
global.Zotero = {
  debug: (m) => debugLines.push(m),
  File: { getContentsAsync: async (p) => fs.readFileSync(p.replace(/^file:\/\/\//, ""), "utf-8") },
  ItemTreeManager: {
    registerColumn: async (opt) => { captured = opt; },
    unregisterColumn: async (...a) => { global.Zotero._unreg = a; },
  },
};

/* 加载 bootstrap.js（顶层函数声明 → 包一层拿引用） */
const src = fs.readFileSync(path.join(DIR, "bootstrap.js"), "utf-8");
const api = new Function("Zotero", "VERSION", src + "\nreturn { startup, shutdown, computeTier, lookupTier };")(
  global.Zotero, "1.0.0");

const rootURI = "file:///" + DIR.replace(/\\/g, "/") + "/";
let pass = 0, fail = 0;
function ok(cond, label) {
  if (cond) { pass++; console.log("  PASS", label); }
  else { fail++; console.log("  FAIL", label); }
}

(async () => {
  await api.startup({ rootURI }, "startup");
  ok(typeof captured === "object" && captured.dataKey === "cuebTier",
     "registerColumn 已注册 dataKey=cuebTier");
  ok(captured.label === "首经贸等级", "列名 = 首经贸等级");

  const item = (pub, issn) => ({ getField: (f) => (f === "publicationTitle" ? pub : f === "issn" ? issn : "") });
  const T = (pub, issn) => captured.dataProvider(item(pub, issn));

  ok(T("Management Science", "") === "国际A+｜UTD24｜FT50｜ABS 4*｜JCR Q1｜SSCI",
     "Management Science → 国际A+｜UTD24｜FT50｜ABS 4*｜JCR Q1｜SSCI（实际: " + T("Management Science", "") + "）");
  ok(T("Journal of Business Ethics", "") === "国际A2｜ABS 3｜JCR Q1｜SSCI",
     "JBE → 国际A2｜SSCI｜Q1｜ABS 3（实际: " + T("Journal of Business Ethics", "") + "）");
  ok(T("经济研究", "") === "中文A1｜CSSCI",
     "经济研究 → 中文A1｜CSSCI（实际: " + T("经济研究", "") + "）");
  ok(T("aBIOTECH", "") === "中文B2｜CSCD｜JCR Q1",
     "aBIOTECH → 中文B2｜CSCD｜Q1（实际: " + T("aBIOTECH", "") + "）");
  ok(T("Accounting, Organizations and Society", "").indexOf("国际B2") === 0,
     "AOS → 国际B2 折算列首（实际: " + T("Accounting, Organizations and Society", "") + "）");
  ok(T("The Accounting Review", "") === T("Accounting Review", "") && T("The Accounting Review", "").indexOf("国际A+") === 0,
     "the-回退: The Accounting Review 与 Accounting Review 同列（实际: " + T("The Accounting Review", "") + "）");
  ok(T("", "0025-1909").indexOf("国际A+") === 0,
     "ISSN 优先: 空刊名 + 0025-1909 → 国际A+（实际: " + T("", "0025-1909") + "）");
  ok(T("这是根本不存在的期刊XYZ", "") === "", "未收录 → 空串");
  ok(T("", "") === "", "书籍条目（无刊名无ISSN）→ 空串");

  /* ISSN 尾位 X 小写也要能匹配 */
  ok(T("Accounting, Organizations and Society", "0361-3682") === T("Accounting, Organizations and Society", ""),
     "ISSN 与刊名命中同一行");

  await api.shutdown();
  ok(Array.isArray(global.Zotero._unreg), "shutdown 正常注销列");

  console.log(fail === 0 ? `\n全部通过 (${pass}/${pass + fail})` : `\n失败 ${fail}/${pass + fail} 项`);
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error("测试异常:", e); process.exit(1); });
