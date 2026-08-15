# 文档入口与知识层

这里不维护第二份“当前状态”。先按任务进入 [START_HERE](START_HERE.md)，需要现态只看 [CURRENT](CURRENT.md)，按稳定分区进入看 [SECTION_INDEX](SECTION_INDEX.md)，需要知道哪些页面仍承担职责时看 [GUIDANCE_INDEX](GUIDANCE_INDEX.md)。

## 主要查询面

| 入口 | 回答的问题 |
|---|---|
| [CURRENT](CURRENT.md) | 当前机器状态、owner gate、研究账本与 durable exact 边界 |
| [SECTION_INDEX](SECTION_INDEX.md) | 稳定 section、局部前门和当前成员 |
| [OPEN_QUESTIONS](OPEN_QUESTIONS.md) | 全部仍为 `status=open` 的稳定 claim |
| [CATALOG](CATALOG.md) | claim、decision、dossier、review 与 evidence 坐标 |
| [REASONING_LEDGER](REASONING_LEDGER.md) | 推理类型、数学依赖、分离机制与语义回填 |
| [VALIDITY_LEDGER](VALIDITY_LEDGER.md) | 反例、失效、修复、重验与 supersession |
| [BACKFILL_LEDGER](BACKFILL_LEDGER.md) | semantic review、availability review 与 inventory triage |
| [TOPIC_INDEX](TOPIC_INDEX.md) / [TERMINOLOGY](TERMINOLOGY.md) | 稳定主题、规范术语与别名 |

这些页面中的生成投影禁止手工修改。`CURRENT` 也不是新的最高权威：certified 边界回到 [`PROJECT_LOCK`](../PROJECT_LOCK.md)，游戏语义回到 `rules/`，机器义务和 owner gate 回到 `data/`，研究结论回到结构化知识账本。

## 生命周期

- `项目说明/`：现行手册、规范、future-only `ROADMAP`、append-only `HISTORY` 与兼容入口。
- `research/`：按时间保存的研究和外审证据，不因文件仍在而自动成为当前结论。
- [history/](history/README.md)：退出当前职责的字节保真快照。
- `specs/`：规范族；每份规范的状态由自身元数据和上级 authority 决定。

## 修改文档

```bash
.venv/bin/python devtools/docctl.py context <path> --intent <edit|create|move|delete>
.venv/bin/python devtools/docctl.py check --changed
```

固定自举入口是 `.docsystem/manifest.json`。完整概念见 [ARCHITECTURE](governance/document-system/ARCHITECTURE.md)，安全改变框架的方法见 [MAINTAINING](governance/document-system/MAINTAINING.md)，详细 agent 操作见 [AGENT_OPERATIONS](AGENT_OPERATIONS.md)。
