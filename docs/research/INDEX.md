# 旧 research INDEX 兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../../data/repository_governance/document_system/entrypoints.json)。

该路径曾只覆盖 2026-05-07/08 Phase 3C agent transcript，却容易被误读为全研究目录。

## 当前入口

- [研究档案入口](README.md)：研究 dossier、知识晋升与历史边界。
- [Phase 3C transcript 历史索引](../history/navigation/research_phase3c_agent_transcript_index_20260507_08.md)：旧 INDEX 的字节保真、明确命名历史载荷。
- [全部 dossier 目录](../CATALOG.md)：由结构化 dossier registry 生成的全量目录。

## 维护边界

- 本页不得再次宣称自己是 docs/research 的 master index。
- inventory coverage 与 semantic review coverage 必须继续分离。
- 退出当前职责前的正文见 [历史快照](../history/navigation/research_phase3c_agent_transcript_index_20260507_08.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
