/* test_zotero.js — Zotero 插件烟雾测试：桩 Zotero → 真实跑 startup + dataProvider
 * 用法: node test_zotero.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const DIR = path.join(__dirname, "zotero");
const builtData = JSON.parse(fs.readFileSync(path.join(DIR, "data.json"), "utf8"));
const hasSsci = !!builtData.ssci;
const hasJcr = Object.keys(builtData.inJcr).length > 0;
let captured = null;                       /* registerColumn 收到的配置 */
const debugLines = [];
const columns = new Map();
let registerCalls = 0;
global.Zotero = {
  debug: (m) => debugLines.push(m),
  File: { getContentsAsync: async (p) => fs.readFileSync(p.replace(/^file:\/\/\//, ""), "utf-8") },
  ItemTreeManager: {
    registerColumn: async (opt) => {
      captured = opt;
      registerCalls++;
      const key = "cueb-tier-column-example-com-" + opt.dataKey;
      columns.set(key, opt);
      return key;
    },
    unregisterColumn: async (key) => columns.delete(key),
  },
};

/* 加载 bootstrap.js（顶层函数声明 → 包一层拿引用） */
const src = fs.readFileSync(path.join(DIR, "bootstrap.js"), "utf-8");
const api = new Function("Zotero", "VERSION", src + "\nreturn { startup, shutdown, computeTier, lookupTier };")(
  global.Zotero, "1.0.0");

const rootURI = "file:///" + DIR.replace(/\\/g, "/") + "/";
function withOptional(parts, ssci = true) {
  const result = parts.slice();
  if (hasJcr) result.push("JCR Q1");
  if (hasSsci && ssci) result.push("SSCI");
  return result.join("｜");
}
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

  const item = (pub, issn) => ({ getField: (f) => {
    if (f === "publicationTitle") return pub;
    if (f === "ISSN") return issn;
    throw new Error("Invalid field: " + f);
  } });
  const T = (pub, issn) => captured.dataProvider(item(pub, issn));

  ok(T("Management Science", "") === withOptional(["国际A+", "UTD24", "FT50", "ABS 4*"]),
     "Management Science → 国际A+｜UTD24｜FT50｜ABS 4*｜JCR Q1｜SSCI（实际: " + T("Management Science", "") + "）");
  ok(T("Journal of Business Ethics", "") === withOptional(["国际A2", "ABS 3"]),
     "JBE → 国际A2｜SSCI｜Q1｜ABS 3（实际: " + T("Journal of Business Ethics", "") + "）");
  ok(T("经济研究", "") === "中文A1｜CSSCI",
     "经济研究 → 中文A1｜CSSCI（实际: " + T("经济研究", "") + "）");
  ok(T("aBIOTECH", "") === withOptional(["中文B2", "CSCD"], false),
     "aBIOTECH → 中文B2｜CSCD｜Q1（实际: " + T("aBIOTECH", "") + "）");
  ok(T("Accounting, Organizations and Society", "") === withOptional(
       ["国际A1", "FT50", "ABS 4*"]),
     "AOS → 通过 ISSN 关联校目录单数 Organization 写法，保留国际A1（实际: " + T("Accounting, Organizations and Society", "") + "）");
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
  ok(columns.size === 0, "shutdown 使用注册返回的 key，确实移除列");

  /* 回归：重新启动、身份冲突、ISSN 继承等级、原型属性、字段异常。 */
  await api.startup({ rootURI });
  await api.startup({ rootURI });
  ok(registerCalls === 2 && columns.size === 1, "重复 startup 不重复注册；shutdown 后可重启");
  ok(T("Journal of Business Ethics", "0025-1909") === T("Management Science", ""),
     "ISSN 优先于冲突刊名，等级和全部标签均来自 Management Science");
  ok(T("", "1526-5501") === T("Management Science", ""),
     "电子 ISSN 继承国际A+及全部标签，不降为国际B2");
  ok(T("", "1007-9807") === T("管理科学学报", "") && T("", "1007-9807") === "中文A2｜CSSCI｜CSCD",
     "中文 ISSN 查询保留校目录A2和CSCD标签");
  ok(T("constructor", "") === "", "constructor 不会产生等级或伪造榜单标签");
  ok(T("Ｍａｎａｇｅｍｅｎｔ Ｓｃｉｅｎｃｅ", "") === T("Management Science", ""),
     "全角英文归一化后等级与标签一致");
  ok(T("Management Science", "bad-issn") === T("Management Science", ""),
     "无效 ISSN 回退刊名");
  ok(captured.dataProvider({ getField() { throw new Error("Invalid field"); } }) === "",
     "缺少期刊字段的条目安全返回空白");
  await api.shutdown();
  await api.shutdown();
  ok(columns.size === 0, "重复 shutdown 安全");

  const manifest = JSON.parse(fs.readFileSync(path.join(DIR, "manifest.json"), "utf8"));
  ok(manifest.applications.zotero.strict_min_version === "7.0.11" &&
     manifest.applications.zotero.strict_max_version === "10.0.*" &&
     manifest.applications.zotero.id === captured.pluginID &&
     manifest.applications.zotero.update_url === "https://raw.githubusercontent.com/Z1hawl89/cueb-journal-tier/master/zotero-plugin/update.json",
     "安装器必填项齐全，范围包含10.0.6，更新清单使用真实仓库地址");
  if (!hasSsci && !hasJcr) {
    const update = JSON.parse(fs.readFileSync(path.join(DIR, "update.json"), "utf8"));
    const entry = update.addons[manifest.applications.zotero.id].updates[0];
    const file = `cueb-tier-column-${manifest.version}.xpi`;
    const hash = crypto.createHash("sha256").update(fs.readFileSync(path.join(DIR, file))).digest("hex");
    ok(entry.version === manifest.version && entry.update_hash === "sha256:" + hash &&
       entry.update_link === `https://github.com/Z1hawl89/cueb-journal-tier/releases/download/zotero-v${manifest.version}/${file}` &&
       entry.applications.zotero.strict_max_version === manifest.applications.zotero.strict_max_version,
       "公开更新清单的插件ID、版本、下载地址、兼容范围和XPI哈希一致");
    const published = JSON.parse(fs.readFileSync(path.join(__dirname, "update.json"), "utf8"));
    ok(JSON.stringify(published) === JSON.stringify(update), "仓库线上更新清单与本次公开构建一致");
  } else {
    ok(!fs.existsSync(path.join(DIR, "update.json")), "包含授权数据的构建不会生成公共更新清单");
  }

  console.log(fail === 0 ? `\n全部通过 (${pass}/${pass + fail})` : `\n失败 ${fail}/${pass + fail} 项`);
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error("测试异常:", e); process.exit(1); });
