# 首经贸期刊等级助手 / CUEB Journal Tier Assistant

在浏览器和 Zotero 里显示期刊的「首都经济贸易大学」等级及国际权威榜单标签。
数据全部内置、完全本地运行，不需要任何在线服务、账号或会员。

为首都经济贸易大学（CUEB）师生制作（UTD24/FT50/AJG/JCR 标签与学校无关）。

## 两个插件

| | 浏览器独立版 | Zotero 版 |
|---|---|---|
| 形态 | Edge/Chrome 扩展（解包加载） | Zotero 7+ 插件（.xpi） |
| 功能 | 8 站自动徽章 + 任意网页右键框选查询 | 条目列表新增「首经贸等级」列 |
| 版本 | 1.6.2 | 1.0.8 |

标签示例（同一套数据，两个插件同源）：

```
Management Science              首经贸 国际A+ | UTD24 | FT50 | ABS 4* | JCR Q1 | SSCI
经济研究                         首经贸 中文A1 | CSSCI
aBIOTECH                        首经贸 中文B2 | CSCD | JCR Q1
International Journal of ...    首经贸 国际B1 | SSCI | JCR Q1 | ABS 3
```

标签顺序（Zotero 列与浏览器徽章一致为：等级 → UTD24 → FT50 → ABS → JCR → SSCI；
中文刊的 CSSCI/CSCD 紧跟等级）。AJG/ABS 默认只显示 3 档及以上（`AJG_MIN` 可调）。

## 浏览器版

### 安装

1. 构建（见下文）或将本仓库 clone 到本机
2. Edge：`edge://extensions` → 开发人员模式 → 加载解压缩的扩展 → 选 `browser/standalone/`
   （Chrome：`chrome://extensions`，步骤一致）

### 功能

- **自动徽章**（9 站）：
  - 百度学术、知网（检索结果/详情/高级检索期刊导航）、万方、ScienceDirect、Springer、PubMed、Web of Science
  - Google Scholar 官方及各国域名 + 国内镜像（`*.lanfanshu.cn`、`sc.panda321.com`、`scholar.ustc.cf`、`dailyheadlines.cc`），
    兼容 2025 新版引文行格式（`.gs_fmaa`）
- **右键查询**：任意网页框选期刊名或 ISSN → 右键「首经贸期刊等级查询」→ 页面顶部弹结果；
  未命中给最多 3 个近似候选；无内容脚本的页面降级为工具栏图标徽标

### 徽章颜色

等级 A+/A1/A2/B1/B2 = 金/蓝/绿/灰蓝/紫；CSSCI 青、CSCD 灰蓝、SSCI 深绿、
JCR Q1/Q2 深紫/紫、UTD24 深红、FT50 玫红、ABS 藏青。悬停可见数据依据。

## Zotero 版

1. 构建（见下文）得到 `zotero-plugin/zotero/cueb-tier-column-<版本>.xpi`
2. Zotero → 工具 → 插件 → 齿轮 → Install Plugin From File → 选 .xpi → 按提示重启
3. 条目列表表头右键 → 勾选「首经贸等级」（选项在菜单**最底部**；列出现在最右侧，可拖动）

匹配：ISSN 优先（最可靠），刊名归一化 + The 前缀回退兜底；未收录条目显示空白。
排序为文字排序（同等级排在一起）。需要 Zotero 7+。

## 数据体系

| 数据 | 内容 | 校规折算 | 许可 |
|---|---|---|---|
| 首经贸期刊目录 2024 | 校方红头文件（首经贸学术〔2024〕1号），国际 987 + 中文 134 | — | 学校内部文件，仅供本校师生使用 |
| CSSCI 2025-2026 | 来源期刊 674 种 | 中文B2 | 南京大学 CSSCI 目录 |
| CSCD 核心库 2025-2026 | 1120 种（扩展库按校规排除） | 中文B2 | 中科院国家科学图书馆 |
| SSCI（2026-08 快照） | 3536 种 | 国际B2 | Clarivate MJL，**不在仓库内，自行获取** |
| JCR 2025 学科分区 | Q1/Q2 共 10416 种 | 不折算，仅标签 | Clarivate 商业数据，**不在仓库内，自行获取** |
| UTD24 / FT50 / AJG 2024 | 24 / 50（2026-04 版）/ 1823 种 | 不折算，仅标签 | 名单为公开事实 |

仓库 `data/` 目录只包含可公开分发的事实性名单（校目录、CSSCI、CSCD、UTD24、FT50、AJG）。
SSCI 与 JCR 属 Clarivate 授权数据，未包含在仓库中；获取方式见 `data/README.md`，
放入 `data/` 后重新构建即可启用对应标签（`SSCI`/`JCR Q1/Q2` 及"SSCI→国际B2"折算）。
缺少任何可选数据集都不影响构建，只是少对应标签；校目录为必需。

## 构建

依赖：Python 3.8+（仅标准库）、Node.js（语法校验用，可选）。

```bash
# 浏览器版 → browser/standalone/
cd browser && python build_standalone.py

# Zotero 版 → zotero-plugin/zotero/*.xpi
cd zotero-plugin && python build_zotero.py
```

测试：`node browser/test_sa_web8.js`（11 例）、`node zotero-plugin/test_zotero.js`（13 例）。

注意：`browser/build_fork.py` 是共享数据管线（`build_data`、别名归一、数据模板），
被两个构建脚本 import；其 `main()` 是历史遗留的 easyScholar 分支构建入口，已废弃，勿运行。

### 数据更新

更换/新增 `data/` 里的 JSON 后重跑两个构建脚本、重新加载插件即可。
各数据集格式见文件内 `meta` 字段。

## 已知边界

- 浏览器徽章只覆盖上列 9 站，其余站点用右键查询兜底（任意网页可用）
- Google Scholar 引文行被截断（含 …）的条目跳过不标（防错配）
- WOS 中无 JCR 组件（无影响因子）的条目不标
- 国际B2 的 SCIE/A&HCI 部分未折算（避免理科刊大面积亮标）；中文 C（北大核心）、来源集刊未覆盖
- Zotero 列为文字排序

## 许可

- 代码：MIT（见 LICENSE）
- 数据：版权归各机构所有（见上表），本仓库仅收录公开事实性名单用于学术参考；
  校目录为学校内部文件，插件仅供本校师生个人使用
- 本项目与首都经济贸易大学官方无关，等级折算逻辑为对校规的理解实现，以学校正式文件为准
