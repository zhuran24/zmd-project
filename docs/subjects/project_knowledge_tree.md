# 旧项目知识树主题兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../../data/repository_governance/document_system/entrypoints.json)。

项目知识对象和写入方式已经由知识层指南、CATALOG 与 topic projection 统一表达。

## 当前入口

- [结构化知识维护](../../data/knowledge/README.md)：claim、decision、dossier、review、topic 与 terminology 的写入协议。
- [知识与证据目录](../CATALOG.md)：稳定知识身份与证据坐标。
- [主题入口](../TOPIC_INDEX.md)：跨目录主题与开放问题入口。

## 维护边界

- 聊天记录和个人记忆不会自动成为项目知识。
- 退出当前职责前的正文见 [历史快照](../history/navigation/subjects_project_knowledge_tree_pre_phase3_batch3_20260812.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
