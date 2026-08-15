# 文档树完整性兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../data/repository_governance/document_system/entrypoints.json)。

旧的一次性完整性快照已由 dossier inventory、policy coverage 和自动 checker 取代。

## 当前入口

- [知识与 dossier 目录](CATALOG.md)：research 与 artifact 一级包 inventory。
- [当前文档职责](GUIDANCE_INDEX.md)：有效 policy 所声明的当前维护面。
- [按问题导航](START_HERE.md)：从任务而不是目录进入。

## 维护边界

- inventory coverage 不等于 semantic review。
- checker PASS 不授予 soundness、owner close 或 production CERTIFIED。
- 退出当前职责前的正文见 [历史快照](history/subjects/pre_knowledge_spine_20260811/DOC_TREE_COMPLETENESS.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
