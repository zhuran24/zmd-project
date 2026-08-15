# FILE_STATUS.md 兼容入口

> 本页由文档系统的前门注册表自动生成；禁止手工修改。
> 真源：[`data/repository_governance/document_system/entrypoints.json`](data/repository_governance/document_system/entrypoints.json)。

本路径不再维护独立的文件状态表，只保留到现行查询面的稳定跳转。

## 当前入口

- [唯一当前状态](docs/CURRENT.md)：机器状态、owner gate、研究账本和开放边界。
- [按问题导航](docs/START_HERE.md)：从当前问题选择知识、规范、历史或操作入口。
- [知识与证据目录](docs/CATALOG.md)：claim、decision、dossier 与 evidence 坐标。
- [当前文档职责](docs/GUIDANCE_INDEX.md)：现行 living、normative、generated 与 framework surface。
- [代码地图](NAV_MAP.md)：模块与代码职责入口。
- [工程变更账本](CHANGELOG.md)：append-only 工程历史。
- [frontier probe 规范](specs/21_frontier_probe_and_campaign_telemetry.md)：保留旧 FILE_STATUS 使用者依赖的规范入口。

## 维护边界

- 不得在本页复制 gate、phase、上下界、hash、测试数量或开关值。
- 规范状态由规范自身元数据和上级 authority 决定。
- 退出当前职责前的正文见 [历史快照](docs/history/status/FILE_STATUS_20260803.md)；它只保留当时叙述。

需要改变本页时，修改前门注册表后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
```
