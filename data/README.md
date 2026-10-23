# 数据目录

构建必需：`cueb_journal_catalog_2024.json`（校目录，本校师生从学校发布渠道获取）。
其余为可选——缺失只少对应标签，不影响构建。

## 已包含（公开事实性名单）

| 文件 | 内容 | 来源 |
|---|---|---|
| `utd24.json` | UTD24 24 种 | https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals |
| `ft50.json` | FT50 50 种（2026-04-29 版） | https://www.ft.com/ft50-journals |
| `ajg_2024.json` | AJG/ABS 2024 全 1823 种分档 | https://charteredabs.org/academic-journal-guide（免费注册下载） |
| `cssci_2025_2026.json` | CSSCI 来源期刊 674 种 | 南京大学 CSSCI 官方发布 |
| `cscd_2025_2026.json` | CSCD 核心库 1120 种 | https://sciencechina.cn |
| `cueb_journal_catalog_2024.json` | 首经贸期刊目录（校方文件） | 学校发布渠道 |

## 未包含（Clarivate 授权数据，自行获取后放入本目录）

| 文件 | 内容 | 获取方式 |
|---|---|---|
| `ssci_2026.json` | SSCI 期刊名单 3536 种 | Clarivate Master Journal List → Collection List Downloads（https://mjl.clarivate.com/collection-list-downloads，需注册/订阅） |
| `jcr_2026.json` | JCR 2025 学科分区 Q1/Q2 | 学校图书馆的 JCR 入口导出，或自行整理；格式见下 |

也可显式设置环境变量 `CUEB_DATA_DIR` 为授权数据所在目录的绝对路径（仓库文件优先），不会自动搜索个人工作目录。额外数据会内嵌到构建产物中。

放入或设置目录后重跑 `browser/build_standalone.py` 与 `zotero-plugin/build_zotero.py` 即启用
`SSCI` / `JCR Q1/Q2` 标签与「SSCI → 国际B2」折算。

## JSON 格式

所有数据集结构一致，构建脚本按 `meta` + `journals` 数组读取：

```json
{
  "meta": { "title": "...", "total": 123, "source_url": "..." },
  "journals": [
    { "name": "Journal Name", "issn": "0000-0000" }
  ]
}
```

字段要求：
- `name`：必需（CSSCI/CSCD/SSCI/JCR 还可带 `issn`/`eissn` 增强匹配；JCR 需 `best`: "Q1"|"Q2" 与可选 `cats`）
- 具体可参照已包含文件的字段
