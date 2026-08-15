# 00：总路线图兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../../data/repository_governance/document_system/entrypoints.json)。

旧混合路线图已按当前、未来和历史三种职责拆分。

## 当前入口

- [唯一当前状态](../CURRENT.md)：现在已经成立什么。
- [未来路线图](ROADMAP.md)：接下来做什么、依赖什么、用什么证据退出。
- [项目编年史](HISTORY.md)：过去何时发生过什么。

## 维护边界

- 本页不能重新混合当前状态、未来计划和历史正文。
- 退出当前职责前的正文见 [历史快照](../history/status/00_master_roadmap_pre_phase3_20260812.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
