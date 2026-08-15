# 旧 specs 索引兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../data/repository_governance/document_system/entrypoints.json)。

编号规范的现行分区入口已经迁到 specs/README.md；本路径不再维护第二份规格地图。

## 当前入口

- [规范分区入口](../specs/README.md)：编号规范的阅读顺序、职责边界和生态注记分流。
- [当前文档职责](GUIDANCE_INDEX.md)：按有效 policy 查询当前规范与入口。

## 维护边界

- 不得在旧路径重新维护规范分组或当前实现状态。
- 生态注记不是认证 authority；其边界见 specs/ecosystem_notes/README.md。
- 退出当前职责前的正文见 [历史快照](history/navigation/docs_specs_index_pre_phase3_batch3_20260812.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
