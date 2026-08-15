# ZMD certified-exact 最大空矩形求解器

这是《明日方舟：终末地》IndustrialPlanner 基地布局问题的 certified-exact 求解与验证仓库。候选、结构检查、supervisor seal、owner gate 与 durable `CERTIFIED` 属于不同权限层，不能互相代替。

## 进入项目

| 需要回答的问题 | 唯一入口 |
|---|---|
| 现在的机器状态、gate、义务与 durable 结果是什么 | [CURRENT](docs/CURRENT.md) |
| 应从哪类知识、规范、历史或操作页面进入 | [START_HERE](docs/START_HERE.md) |
| 文档按哪些稳定分区组织、各分区从哪里进入 | [SECTION_INDEX](docs/SECTION_INDEX.md) |
| 哪些页面仍承担当前职责 | [GUIDANCE_INDEX](docs/GUIDANCE_INDEX.md) |
| certified exactness 与发布边界是什么 | [PROJECT_LOCK](PROJECT_LOCK.md) |
| agent 操作与文档维护入口 | [AGENT_OPERATIONS](docs/AGENT_OPERATIONS.md) |
| claim、decision、dossier 与证据在哪里 | [CATALOG](docs/CATALOG.md) |

`CURRENT`、知识账本页面和职责索引都是投影，不是新的最高权威。当前值只从对应机器源或生成页读取；不要在 README、操作手册或历史材料中复制 gate、上下界、hash、测试数量和开关状态。

外部 review 计数仍是 `owner-maintained outside the repo`；仓库只记录 owner 已作出的治理结果，不自行推导或累加该计数。

## 最小操作面

项目命令统一使用 `.venv/bin/python`。修改文档前先解析目标路径，完成后检查本次 diff：

```bash
.venv/bin/python devtools/docctl.py context <path> --intent edit
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/docctl.py gate --profile changed
.venv/bin/python scripts/preflight_gate.py --full
```

详细运行、测试、冻结与发布流程见 [Agent 操作手册](docs/AGENT_OPERATIONS.md)。文档治理 gate 验收文档框架且保证检查前后 Git-visible 状态不变；production preflight 验收另一套运行与认证边界。checker 或 preflight 通过只证明其声明的检查面，不自动授予数学 soundness、owner close 或 production certification。

## 代码与规范

- [代码地图](NAV_MAP.md)
- [问题陈述](specs/01_problem_statement.md)
- [canonical rules](rules/canonical_rules.json)
- [proof obligations](data/proof_obligations/p1_2_proof_obligations.json)
- [owner phase gate](data/review_gates/phase_1_2_spike_close.json)
- [工程历史](CHANGELOG.md)

旧版根入口保存在 [历史快照](docs/history/status/root_README_pre_knowledge_spine_20260811.md)，只用于追溯当时叙述。
