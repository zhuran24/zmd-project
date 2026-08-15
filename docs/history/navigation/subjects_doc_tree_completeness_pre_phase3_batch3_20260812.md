# 文档树完整性语义

旧 `docs/DOC_TREE_COMPLETENESS.json` 是一次性路径快照，已由可执行 inventory 取代。现在的完整性检查分为两部分：

- `data/knowledge/dossiers.json` 覆盖配置中的一级 research/artifact 包；新增包未登记或 tracked 包消失会 fail closed。
- `docs/CURRENT.md` 与 `docs/CATALOG.md` 必须与机器源和账本逐字一致，否则 checker 报 drift。

完整性仍不等于 soundness、owner 关门或 production certification。检查命令见 [`../../data/knowledge/README.md`](../../data/knowledge/README.md)。旧 inventory 的原文保存在 [`../history/subjects/pre_knowledge_spine_20260811/`](../history/subjects/pre_knowledge_spine_20260811/)。
