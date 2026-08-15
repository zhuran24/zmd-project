# 旧文档完整性主题兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../../data/repository_governance/document_system/entrypoints.json)。

目录覆盖、当前职责和语义回填已分别由机器投影承担。

## 当前入口

- [当前文档职责](../GUIDANCE_INDEX.md)：有效 policy 的当前职责和分区投影。
- [知识回填覆盖](../BACKFILL_LEDGER.md)：semantic review、availability review 与 inventory triage。
- [知识与证据目录](../CATALOG.md)：claim、decision 和 dossier inventory。

## 维护边界

- 完整性检查不等于 soundness、owner closure 或 certification。
- 退出当前职责前的正文见 [历史快照](../history/navigation/subjects_doc_tree_completeness_pre_phase3_batch3_20260812.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
