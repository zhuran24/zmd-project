# `docs/项目说明/` 项目手册入口

本目录只保留显式分类的当前手册、稳定规范、future-only 计划、append-only 编年史和少量兼容入口。目录位置本身不再授予 `living` 身份；分区关系见 [SECTION_INDEX](../SECTION_INDEX.md)，当前职责清单见 [GUIDANCE_INDEX](../GUIDANCE_INDEX.md)。

## 先读

1. [唯一当前状态](../CURRENT.md)
2. [当前开放问题](../OPEN_QUESTIONS.md)
3. [按问题导航](../START_HERE.md)
4. [文档分区](../SECTION_INDEX.md)
5. [知识与证据目录](../CATALOG.md)
6. [规范术语](../TERMINOLOGY.md)
7. [坑册与 SOP](28_pitfalls_and_sop.md)

## 当前手册与规范

- 命题、数学与不变量：[01_overview.md](01_overview.md)、[02_mathematical_foundations.md](02_mathematical_foundations.md)、[04_design_invariants.md](04_design_invariants.md)
- 规则、cut 与资产治理：[23_rule_cut_evolution_protocol.md](23_rule_cut_evolution_protocol.md)、[24_repository_asset_governance.md](24_repository_asset_governance.md)、[26_rules_handbook.md](26_rules_handbook.md)
- 研究方向、立项判据与当前押注：[30_research_charter.md](30_research_charter.md)
- 依赖图：[11_dependency_graph.md](11_dependency_graph.md)
- 测试、review、telemetry 与环境：[15_workflow_testing.md](15_workflow_testing.md)、[16_workflow_review.md](16_workflow_review.md)、[17_workflow_telemetry.md](17_workflow_telemetry.md)、[18_workflow_env_config.md](18_workflow_env_config.md)、[19_implementation_rhythm.md](19_implementation_rhythm.md)
- 风险、操作与 GO / close 判读：[14_risk_rollout.md](14_risk_rollout.md)、[28_pitfalls_and_sop.md](28_pitfalls_and_sop.md)、[12_go_criteria.md](12_go_criteria.md)

## 未来、方法与历史

- [ROADMAP.md](ROADMAP.md)：只写未来工作、依赖与退出证据，不复制当前状态。
- [REASONING_METHOD.md](REASONING_METHOD.md)：保存仍有效的推理与管线设计方法。
- [29_solving_methodology_skill.md](29_solving_methodology_skill.md)：求解面「知识×计算」分解方法论的项目级 skill tracked 真本。
- [HISTORY.md](HISTORY.md)：只按日期追加编年史与迁移坐标。
- [../history/status/](../history/status/)：退出当前职责的字节保真快照。

`00_master_roadmap.md`、`05_open_questions.md`、`06_current_status.md`、`21_glossary.md` 与 `27_status_dashboard.md` 只保留兼容跳转。旧阶段计划、旧排期和历史分析由 policy 标为 historical，不再追随现态更新。

会变化的 gate、上下界、开关、hash 和测试数只能进入机器源或 `data/knowledge/`，再由 [CURRENT](../CURRENT.md) 等生成页投影；不要在本目录重新维护副本。
