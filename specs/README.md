# `specs/` 规范入口

本目录保存当前编号规范。规范只在自身作用域内定义稳定契约；当前 gate、上下界、hash、测试数量和 owner 决定统一回到 [`docs/CURRENT.md`](../docs/CURRENT.md) 与对应机器源。certified exactness 的最高仓内边界仍是 [`PROJECT_LOCK.md`](../PROJECT_LOCK.md)。

## 建议阅读顺序

| 层次 | 规范 | 负责什么 |
|---|---|---|
| 问题与语义 | [01](01_problem_statement.md)、[02](02_global_notation_and_units.md)、[03](03_rule_canonicalization.md) | 命题、记号、单位与 canonical rule 解释 |
| 输入展开 | [04](04_recipe_and_demand_expansion.md)、[05](05_facility_instance_definition.md) | recipe、需求与 facility instance |
| 候选与 master | [06](06_candidate_placement_enumeration.md)、[07](07_master_placement_model.md) | 候选枚举与 master placement model |
| 路由与 cut | [08](08_topological_flow_subproblem.md)、[09](09_exact_grid_routing_subproblem.md)、[10](10_benders_decomposition_and_cut_design.md) | 诊断流、exact grid routing 与 cut 设计 |
| 管线与输出 | [11](11_pipeline_orchestration.md)、[12](12_output_blueprint_schema.md) | orchestration、义务边界与输出 schema |
| 兼容与导出 | [13](13_ecosystem_borrowing_and_compatibility_plan.md)、[14](14_normalized_catalog_contract.md)、[15](15_target_export_and_compatibility_manifest.md)、[16](16_industrial_planner_export_contract.md)、[17](17_endfield_calc_ingest_contract.md)、[18](18_preprocess_context_contract.md)、[19](19_phase3_frozen_compatible_preprocess_regeneration.md)、[20](20_canonical_rules_consolidation.md) | 借用边界、catalog、export、ingest 与 canonical consolidation |
| campaign telemetry | [21](21_frontier_probe_and_campaign_telemetry.md) | probe、campaign 与 telemetry 契约 |
| IndustrialPlanner 外层 | [22](22_industrial_planner_precision_export_and_validator_spec.md)、[23](23_industrial_planner_outer_base_planning_representation.md) | adapter precision、validator 与外层表示 |

[11_pipeline_orchestration.md](11_pipeline_orchestration.md) 是管线总契约，但不复制现行 phase 值。需要按任务寻找规范、操作或历史入口时看 [`docs/SECTION_INDEX.md`](../docs/SECTION_INDEX.md)。

## 权威与生命周期

- `01`–`23` 是 `normative_input`，不自动高于 `PROJECT_LOCK.md`、canonical rules、proof obligations 或 owner gate。
- 修改规范前运行 `docctl context <path> --intent edit`；语义变化应同时检查相关实现、测试、claim 与 decision。
- 旧实现状态、实验数字和 release 快照不得回写到规范正文作为“当前事实”。
- 规范被替代时保留显式 successor、历史快照或兼容入口，不静默改写旧证据。

## 生态注记

[`ecosystem_notes/`](ecosystem_notes/README.md) 保存外部仓库 inventory、借用词汇和兼容研究。它们是 explanatory input，不是 certified semantics、owner authority 或生产证明。

## 相关入口

- [当前状态](../docs/CURRENT.md)
- [项目手册](../docs/项目说明/README.md)
- [运行与维护](../docs/OPERATIONS.md)
- [兼容矩阵](../docs/compatibility_matrix.md)
- [文档分区](../docs/SECTION_INDEX.md)
