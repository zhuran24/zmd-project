# 06：当前状态兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](../../data/repository_governance/document_system/entrypoints.json)。

本路径不再维护独立状态正文。

## 当前入口

- [唯一当前状态](../CURRENT.md)：机器状态、claim 与 owner decision 的当前投影。
- [按问题导航](../START_HERE.md)：选择规范、知识、历史或操作入口。
- [知识与证据目录](../CATALOG.md)：稳定 ID、证据和 supersession。
- [规则与 cut 演化协议](23_rule_cut_evolution_protocol.md)：局部协议状态由其规范自身维护，本页不复制。

## 维护边界

- 局部协议状态由其机器源或规范自身维护，不能回流成本页现态副本。
- 退出当前职责前的正文见 [历史快照](../history/status/06_current_status_20260803.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
