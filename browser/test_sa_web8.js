/* test_sa_web8.js — 独立版站点扩展测试：WOS（列表/详情/中文回退）+ 谷歌学术镜像
 * 用法: node test_sa_web8.js  （跑在 standalone/ 上）
 */
"use strict";
const path = require("path");
const fs = require("fs");
const vm = require("vm");
const SA = path.join(__dirname, "standalone");

let n = 0;
global.setInterval = fn => { global.setInterval.callbacks.push(fn); return ++n; };
global.setInterval.callbacks = [];
global.clearInterval = function () {};
global.setTimeout = function () { return 0; };
global.clearTimeout = function () {};

function el(tag) {
  return {
    _t: "", _tag: tag || "span", attrs: {}, children: [], className: "",
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k] !== undefined ? this.attrs[k] : null; },
    appendChild(c) { this.children.push(c); return c; },
    insertAdjacentElement(pos, c) { this._adj = c; return c; },
    querySelector() { return null; },
    closest() { return null; },
    get textContent() { return this._t || this.children.map(c => c.textContent).join(""); },
    set textContent(v) { this._t = v; },
    get title() { return this.attrs.title || ""; },
    set title(v) { this.attrs.title = v; },
    get style() { return this.attrs.style || ""; },
    set style(v) { this.attrs.style = v; },
    remove() {},
  };
}
function withQ(e, map) {
  e.querySelector = s => (map[s] !== undefined ? map[s] : null);
  return e;
}

global.self = global;
global.window = global;
global.chrome = { runtime: {
  onMessage: { addListener() {} },
  sendMessage(msg, cb) { cb(global.__CUEB_TIERS__); }
} };
global.MutationObserver = function () { return { observe() {} }; };
global.location = { hostname: "www.webofscience.com" };
let dispatch = {};                       /* selector → 元素列表 */
global.document = {
  createElement: t => el(t),
  documentElement: el("html"),
  querySelectorAll: s => dispatch[s] || [],
  querySelector: s => dispatch[s] || null,
};

require(path.join(SA, "cueb_data.js"));
require(path.join(SA, "content.js"));

let pass = 0, fail = 0;
function ok(cond, label) {
  if (cond) { pass++; console.log("  PASS", label); }
  else { fail++; console.log("  FAIL", label); }
}
function tick() { global.setInterval.callbacks.forEach(f => f()); }
function chipTexts(anchor) {
  return (anchor._adj && anchor._adj.children || []).map(c => c._t);
}
function expectedIntl() {
  const tags = ["首经贸 国际A+", "UTD24", "FT50", "ABS 4*"];
  if (Object.keys(global.__CUEB_TIERS__.inJcr).length) tags.push("JCR Q1");
  if (global.__CUEB_TIERS__.ssci) tags.push("SSCI");
  return tags;
}
function sameTags(actual, expected) { return JSON.stringify(actual) === JSON.stringify(expected); }

/* ---- 1. WOS 搜索结果行：JCR 组件取英文刊名，锚到标题链接 ---- */
console.log("WOS:");
{
  const span = el("span"); span._t = "MANAGEMENT SCIENCE  arrow_drop_down";
  const sn = withQ(el("app-jcr-sidenav"), { "span[lang='en']": span });
  const title = el("a");
  const row = withQ(el("app-record"), { "a[data-ta*='title']": title });
  sn.closest = sel => (sel === "app-record" ? row : null);
  dispatch = { "app-jcr-sidenav": [sn] };
  global.location.hostname = "www.webofscience.com";
  tick();
  const chips = chipTexts(title);
  ok(sameTags(chips, expectedIntl()),
     "WOS 列表行 MANAGEMENT SCIENCE → 标题旁 [首经贸 国际A+ | UTD24 | FT50 | ABS 4*]（实际: " + chips.join(" | ") + "）");
  ok(title.attrs["data-cueb-sa"] === "1", "标题锚点已打去重标记");
}

/* ---- 2. WOS 详情页：无行容器 → 锚在 JCR 组件本身 ---- */
{
  const span = el("span"); span._t = "JOURNAL OF FINANCE";
  const sn = withQ(el("app-jcr-sidenav"), { "span[lang='en']": span });
  dispatch = { "app-jcr-sidenav": [sn] };
  global.location.hostname = "www.webofscience.com";
  tick();
  const chips = chipTexts(sn);
  ok(sameTags(chips, expectedIntl()),
     "WOS 详情页 JOURNAL OF FINANCE → 组件旁 4 标签（实际: " + chips.join(" | ") + "）");
}

/* ---- 3. WOS 中文界面回退：span[lang='zh-cn'] ---- */
{
  const zh = el("span"); zh._t = "管理世界 arrow_drop_down";
  const sn = withQ(el("app-jcr-sidenav"), { "span[lang='zh-cn']": zh });
  dispatch = { "app-jcr-sidenav": [sn] };
  tick();
  const chips = chipTexts(sn);
  ok(chips.length === 2 && chips[0] === "首经贸 中文A1" && chips[1] === "CSSCI",
     "WOS 中文回退 管理世界 → [首经贸 中文A1 | CSSCI]（实际: " + chips.join(" | ") + "）");
}

/* ---- 4. 谷歌学术：旧版/新版引文行 + 镜像（lanfanshu 整站克隆）---- */
console.log("谷歌学术:");
{
  /* 旧版格式：行内文本 "作者 - 期刊, 年份 - 出版社"，徽章锚在引文行 gs_a */
  const gsA = el("div"); gsA._t = "J. Smith - JOURNAL OF FINANCE, 2020 - Wiley";
  dispatch = { "div.gs_a": [gsA] };
  global.location.hostname = "scholar.google.com";
  tick();
  const chips = chipTexts(gsA);
  ok(sameTags(chips, expectedIntl()),
     "旧版行 scholar.google.com → 引文行旁 6 标签（实际: " + chips.join(" | ") + "）");
}
{
  /* 2025 新版格式（gs_fma_p）：作者在 .gs_fmaa 子块，期刊名+年份为其后裸文本 */
  const authors = el("div"); authors._t = "M Mansoor, TI Khan, FA Jam, M Alasmari";
  const gsA = withQ(el("div"), { ".gs_fmaa": authors });
  Object.defineProperty(gsA, "textContent", {
    get: () => "M Mansoor, TI Khan, FA Jam, M AlasmariInternational Journal of Contemporary Hospitality Management, 2025•emerald.com",
    configurable: true
  });
  dispatch = { "div.gs_a": [gsA] };
  tick();
  const chips = chipTexts(gsA);
  ok(chips.length >= 1 && chips[0] === "首经贸 国际B1",
     "新版行（gs_fmaa 粘连格式）→ 解析出期刊并打标（实际: " + chips.join(" | ") + "）★");
}
{
  /* 新版但期刊名被截断/无期刊信息 → 不打标不报错 */
  const authors = el("div"); authors._t = "A B";
  const gsA = withQ(el("div"), { ".gs_fmaa": authors });
  Object.defineProperty(gsA, "textContent", {
    get: () => "A BProceedings of the 2025 Conference on Marketing, 2025•acm.org",
    configurable: true
  });
  dispatch = { "div.gs_a": [gsA] };
  tick();
  ok(!gsA._adj && !gsA.attrs["data-cueb-sa"], "未收录会议出版物安全跳过");
}
{
  /* 镜像站走同一套解析 */
  const gsA = el("div"); gsA._t = "J. Smith - JOURNAL OF FINANCE, 2020 - Wiley";
  dispatch = { "div.gs_a": [gsA] };
  global.location.hostname = "xueshu.lanfanshu.cn";
  tick();
  ok(sameTags(chipTexts(gsA), expectedIntl()), "xueshu.lanfanshu.cn 同样命中");
}
{
  const gsA = el("div"); gsA._t = "J. Smith - JOURNAL OF FINANCE, 2020 - Wiley";
  dispatch = { "div.gs_a": [gsA] };
  global.location.hostname = "sc.panda321.com";
  tick();
  ok(sameTags(chipTexts(gsA), expectedIntl()), "sc.panda321.com 同样命中");
}

/* ---- 5. 未知站点不动作 ---- */
{
  const h3 = el("h3");
  const gsA = el("div"); gsA._t = "J. Smith - JOURNAL OF FINANCE, 2020 - Wiley";
  const row = withQ(el("div"), { "h3.gs_rt": h3, "div.gs_a": gsA });
  dispatch = { "div.gs_ri": [row], "app-jcr-sidenav": [] };
  global.location.hostname = "www.example.org";
  tick();
  ok(!h3._adj, "example.org 不注入任何徽章");
}

/* ---- 6. WOS 无 JCR 组件的行（无影响因子）→ 拿不到刊名，跳过 ---- */
{
  const sn = el("app-jcr-sidenav");          /* 没有任何 lang span */
  dispatch = { "app-jcr-sidenav": [sn] };
  global.location.hostname = "www.webofscience.com";
  tick();
  ok(!sn._adj && !sn.attrs["data-cueb-sa"], "无刊名的 JCR 组件被安全跳过");
}

/* ---- 回归：万方详情、ISSN 等级、对象属性边界 ---- */
{
  const title = el("h1"), journal = el("a"); journal._t = "经济研究";
  dispatch = { "div.detailTitle div.detailTitleCN": title,
               "div.periodicalInformation div.periodicalName a": journal };
  global.location.hostname = "www.wanfangdata.com.cn";
  tick();
  ok(sameTags(chipTexts(title), ["首经贸 中文A1", "CSSCI"]), "万方详情首次扫描即插入徽章");
  const first = title._adj;
  tick();
  ok(title._adj === first, "万方详情再次扫描不重复插入");
  const L = global.__cuebMakeLookup();
  ok(L.lookup("constructor") === null, "constructor 不会命中继承属性");
  ok(L.lookup("1007-9807") === "中文A2", "管理科学学报 ISSN 保留 A2，不降为 B2");
  ok(L.resolve("Journal of Business Ethics", "0025-1909").name === "Management Science",
     "刊名与 ISSN 冲突时解析为 ISSN 对应身份");
  ok(L.lookup("Ｍａｎａｇｅｍｅｎｔ Ｓｃｉｅｎｃｅ") === "国际A+", "全角英文 NFKC 归一化");
}

/* ---- 非学术页面按需读取数据；右键查询仍返回完整标签 ---- */
{
  let listener, requests = 0, intervals = 0, observers = 0;
  const page = {
    location: { hostname: "www.example.org" },
    document: { createElement: () => el("div"), documentElement: el("html") },
    chrome: { runtime: {
      onMessage: { addListener(fn) { listener = fn; } },
      sendMessage(msg, cb) { requests++; cb(JSON.parse(JSON.stringify(global.__CUEB_TIERS__))); }
    } },
    MutationObserver: function () { observers++; return { observe() {} }; },
    setInterval() { intervals++; }, setTimeout() {}, clearTimeout() {}, console
  };
  page.self = page.window = page;
  vm.runInNewContext(fs.readFileSync(path.join(SA, "content.js"), "utf8"), page);
  ok(requests === 0 && intervals === 0 && observers === 0 && !page.__CUEB_TIERS__,
     "非学术页面不读期刊数据、不观察或定时扫描 DOM");
  let response;
  listener({ type: "__cueb_result", query: "1007-9807", tier: "中文A2", candidates: [] }, {}, r => { response = r; });
  const toast = page.document.documentElement.children[0];
  ok(requests === 1 && response.ok && toast.innerHTML.includes("中文A2") && toast.innerHTML.includes("CSCD"),
     "任意网页右键 ISSN 查询按需读取数据并显示身份对应标签");
  ok(intervals === 0 && observers === 0, "右键查询不会在非学术页启动后台扫描");
}

/* ---- 串联真实后台脚本与内容脚本，覆盖查询消息往返和无接收者降级 ---- */
{
  let dataListener, pageListener, select, messageCount = 0;
  let badge = "", allowData = true, pageAvailable = true;
  const action = {
    setBadgeBackgroundColor() {}, setBadgeText(o) { badge = o.text; }, setTitle() {}
  };
  const worker = { console, setTimeout() {}, chrome: {
    runtime: { id: "test-extension", onMessage: { addListener(fn) { dataListener = fn; } } },
    contextMenus: { removeAll(cb) { cb(); }, create() {}, onClicked: { addListener(fn) { select = fn; } } },
    tabs: { sendMessage(id, msg, cb) {
      if (pageAvailable) pageListener(msg, { id: "test-extension" }, cb);
      else cb(undefined);
    } }, action
  } };
  worker.self = worker;
  const workerContext = vm.createContext(worker);
  worker.importScripts = () => vm.runInContext(fs.readFileSync(path.join(SA, "cueb_data.js"), "utf8"), workerContext);
  vm.runInContext(fs.readFileSync(path.join(SA, "background.js"), "utf8"), workerContext);
  const page = { console, location: { hostname: "example.org" }, setTimeout() {},
    document: { createElement: () => el("div"), documentElement: el("html") },
    chrome: { runtime: {
      onMessage: { addListener(fn) { pageListener = fn; } },
      sendMessage(msg, cb) {
        messageCount++;
        if (allowData) dataListener(msg, { id: "test-extension" }, data => cb(JSON.parse(JSON.stringify(data))));
        else cb(undefined);
      }
    } }
  };
  page.self = page.window = page;
  vm.runInNewContext(fs.readFileSync(path.join(SA, "content.js"), "utf8"), page);
  allowData = false;
  select({ menuItemId: "cueb-sa-selection-lookup", selectionText: "1007-9807" }, { id: 1 });
  ok(badge === "A2" && !page.document.documentElement.children.length,
     "数据加载失败会回应后台，降级工具栏徽标");
  allowData = true; badge = "";
  select({ menuItemId: "cueb-sa-selection-lookup", selectionText: "1007-9807" }, { id: 1 });
  const toast = page.document.documentElement.children[0];
  ok(messageCount === 2 && toast.innerHTML.includes("中文A2") && toast.innerHTML.includes("CSCD") && badge === "",
     "后台右键 → 内容脚本按需读取 → 返回标签，全链路成功且失败后可重试");
  pageAvailable = false;
  select({ menuItemId: "cueb-sa-selection-lookup", selectionText: "0025-1909" }, { id: 1 });
  ok(badge === "A+", "无内容脚本的页面保留工具栏查询兜底");
}

console.log(fail === 0 ? `\n全部通过 (${pass}/${pass + fail})` : `\n失败 ${fail}/${pass + fail} 项`);
process.exit(fail === 0 ? 0 : 1);
