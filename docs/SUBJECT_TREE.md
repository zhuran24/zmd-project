# 主题说明兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../data/repository_governance/document_system/entrypoints.json)。

旧 subject/projection 机制不再承担当前同步职责。

## 当前入口

- [稳定主题索引](TOPIC_INDEX.md)：按主题连接 claim、术语、dossier label 与开放问题。
- [主题阅读辅助](subjects/README.md)：人工维护的轻量阅读入口。
- [唯一当前状态](CURRENT.md)：当前机器与知识状态。

## 维护边界

- 旧 subject 文件不能覆盖结构化 topic 或 CURRENT。
- 退出当前职责前的正文见 [历史快照](history/subjects/pre_knowledge_spine_20260811/SUBJECT_TREE.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
