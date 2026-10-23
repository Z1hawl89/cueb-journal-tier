# 首经贸期刊等级助手 / CUEB Journal Tier Assistant

在浏览器和 Zotero 里显示期刊的「首都经济贸易大学」等级及国际权威榜单标签。
期刊查询使用内置数据，在本地运行，不需要账号或会员；Zotero 插件检查更新时会访问 GitHub。

为首都经济贸易大学（CUEB）师生制作（UTD24/FT50/AJG/JCR 标签与学校无关）。

## 两个插件

| | 浏览器独立版 | Zotero 版 |
|---|---|---|
| 形态 | Edge/Chrome 扩展（解包加载） | Zotero 7.0.11–10.0.x 插件（.xpi） |
| 功能 | 9 站自动徽章 + 任意网页右键框选查询 | 条目列表新增「首经贸等级」列 |
| 版本 | 1.6.3 | 1.0.10 |

标签示例（同一套数据，两个插件同源）：

```
Management Science              首经贸 国际A+ | UTD24 | FT50 | ABS 4* | JCR Q1 | SSCI
经济研究                         首经贸 中文A1 | CSSCI
aBIOTECH                        首经贸 中文B2 | CSCD | JCR Q1
International Journal of ...    首经贸 国际B1 | ABS 3 | JCR Q1 | SSCI
```

标签顺序（Zotero 列与浏览器徽章一致为：等级 → UTD24 → FT50 → ABS → JCR → SSCI；
中文刊的 CSSCI/CSCD 紧跟等级）。AJG/ABS 默认只显示 3 档及以上（`AJG_MIN` 可调）。

## 浏览器版

### 安装

1. 将本仓库 clone 到本机，再按下文执行浏览器版构建
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

匹配：已知 ISSN 优先（刊名冲突时以 ISSN 为准），刊名归一化及 The、&/and 别名兜底；等级与榜单标签均按匹配到的期刊身份查询；未收录条目显示空白。
排序为文字排序（同等级排在一起）。安装清单范围为 Zotero 7.0.11–10.0.x；已在真实 Zotero 10.0.6 的隔离配置中验证安装、激活、重启、禁用/重新启用及等级显示，其余版本未逐版实测。

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

依赖：Python 3.8+（仅标准库）、Node.js（构建语法校验用，可选；运行测试时必需）。以下命令均在仓库根目录执行；macOS/Linux 若无 `python` 命令，请使用 `python3`。

```bash
# 浏览器版 → browser/standalone/
python browser/build_standalone.py

# Zotero 版 → zotero-plugin/zotero/*.xpi
python zotero-plugin/build_zotero.py
```

测试：`node browser/test_sa_web8.js`、`node zotero-plugin/test_zotero.js`。先重新构建，再运行测试；两组测试均支持缺少 SSCI/JCR 的正常降级，并包含边界回归测试。数据管线另可执行 `python -m unittest discover -s browser -p "test_build_data.py"`。

注意：`browser/build_fork.py` 是共享数据管线（`build_data`、别名归一、数据模板），
被两个构建脚本 import；其 `main()` 是历史遗留的 easyScholar 分支构建入口，已废弃，勿运行。

### 数据更新

更换/新增 `data/` 里的 JSON 后重跑两个构建脚本、重新加载插件即可。
各数据集格式见文件内 `meta` 字段。

默认只搜索仓库根目录 `data/` 和 `browser/data/`，不会自动读取个人工作目录。
需要附加本地授权数据时，显式设置环境变量 `CUEB_DATA_DIR` 为该目录的绝对路径，再执行两个构建命令；仓库内同名文件仍优先。
构建会打印实际使用的数据文件路径。显式加载的额外数据会内嵌到两个产物中，分发前应核对其授权范围。

浏览器扩展仍匹配 HTTP/HTTPS 页面，以接收任意网页右键查询；非目标学术站点只运行轻量消息监听器，收到查询后才加载期刊数据，不启动 DOM 观察和定时扫描。
Zotero 插件的真实更新清单为 [`zotero-plugin/update.json`](https://raw.githubusercontent.com/Z1hawl89/cueb-journal-tier/master/zotero-plugin/update.json)，指向公开 Release 的 XPI，并提供 SHA-256 校验。
1.0.9 缺少安装器必填字段且版本上限过低；请手动安装 1.0.10，之后可由 Zotero 检查后续更新。

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


## Zotero 发布与实机验收

仅使用仓库数据构建时，`build_zotero.py` 会在产物目录生成 `update.json`。准备 Release 时，将它同步到仓库 `zotero-plugin/update.json`，与源码一起提交；上传哈希一致的 XPI 到清单指定的 `zotero-v<版本>` Release。含 SSCI/JCR 数据的构建不会生成公共更新清单。构建固定压缩包时间戳、文件顺序和换行，避免重建后哈希失配。

真实安装验收使用本机 Zotero 10.0.6，在全新工作目录中创建独立配置和空论文库，不使用日常 Zotero 配置。Windows 示例（替换路径，工作目录须尚不存在）：

```powershell
python zotero-plugin/test_install.py --zotero-exe "D:/Zotero/zotero.exe" --xpi "zotero-plugin/zotero/cueb-tier-column-1.0.10.xpi" --work-dir "C:/Temp/cueb-install-test"
```

脚本隐藏启动真实程序，通过仅监听本机的调试端口调用安装器，验证激活、自定义列、真实条目值和重启，并保存 JSON 验收回执。Release 发布后，用相同参数追加 `--check-update`，验证真实 Zotero 能读取线上更新清单。验收仅终止其自行启动的进程。
