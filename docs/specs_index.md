# Specs 目录索引

`specs/` 下 23 份编号 spec + `ecosystem_notes/` 子目录 (9 份). 这份索引一句话讲每份 spec 的 scope, 方便定位.

**Spec 跟代码的关系**: spec 是设计契约, 代码是 spec 的实现. 改 spec **需要** PROJECT_LOCK 同步 update; 改代码不改 spec, OK; 跨 spec 改 schema 要把 lock / spec / test 三者同步.

---

## 编号 spec (按主题分组)

### 1. 问题定义 + 数学基础

| Spec | 主题 |
|---|---|
| `01_problem_statement.md` | 项目要解的优化问题: 70×70 grid + 266 mandatory facility + 最大化空矩形 (max_lex(area, min_side)) |
| `02_global_notation_and_units.md` | 全局数学符号 / 单位 / 命名规范 (所有 spec 共用的术语表) |

### 2. 规则规范化 + 数据预处理

| Spec | 主题 |
|---|---|
| `03_rule_canonicalization.md` | 把上游 endfield-calc 178 items / 260 recipes 规范化到 17 recipes 投影的策略 |
| `04_recipe_and_demand_expansion.md` | recipe 展开 + 需求传播 (commodity demand → instance count) |
| `05_facility_instance_definition.md` | mandatory_exact_instances 数据结构定义 (266 个) |
| `18_preprocess_context_contract.md` | 冻结预处理上下文契约 (PreprocessContext v0.2.0) |
| `19_phase3_frozen_compatible_preprocess_regeneration.md` | Phase 3 冻结兼容预处理重生策略 |
| `20_canonical_rules_consolidation.md` | canonical_rules.json schema + 合并策略 |

### 3. 求解模型核心

| Spec | 主题 |
|---|---|
| `06_candidate_placement_enumeration.md` | candidate_placements 池子枚举 + pose 定义 |
| `07_master_placement_model.md` | **master CP-SAT 模型** (src/models/master_model.py 的 spec) |
| `08_topological_flow_subproblem.md` | 流网络子问题 (诊断用) |
| `09_exact_grid_routing_subproblem.md` | 路由子问题 (网格 Dijkstra) |
| `10_benders_decomposition_and_cut_design.md` | **Benders 分解架构** (src/search/benders_loop.py + src/models/cut_manager.py 的 spec) |
| `11_pipeline_orchestration.md` | 求解 pipeline 编排 (outer search + benders + subproblems) |

### 4. 输出 + 交付

| Spec | 主题 |
|---|---|
| `12_output_blueprint_schema.md` | blueprint v2 schema (src/io/output_schema.py 的 spec) |
| `21_frontier_probe_and_campaign_telemetry.md` | 前沿探针 + campaign 遥测 |

### 5. 生态适配契约 (跟 src/adapters/ 对接)

| Spec | 主题 |
|---|---|
| `13_ecosystem_borrowing_and_compatibility_plan.md` | 借用上游组件总策略 (concept-only, 无 runtime dep) |
| `14_normalized_catalog_contract.md` | NormalizedCatalog 类型契约 |
| `15_target_export_and_compatibility_manifest.md` | target export + compatibility manifest schema |
| `16_industrial_planner_export_contract.md` | IP v2 导出契约 |
| `17_endfield_calc_ingest_contract.md` | endfield-calc 摄取契约 |
| `22_industrial_planner_precision_export_and_validator_spec.md` | IP v2 精确导出 + validator spec (refinement 16) |
| `23_industrial_planner_outer_base_planning_representation.md` | 外部多 base 部署表示 (future_scope) |

---

## `ecosystem_notes/` 子目录 (9 份)

上游项目 + 兼容性的 informal notes, 非正式 spec.

| File | 关于 |
|---|---|
| `aslappyslashy_modeling_vocabulary_notes.md` | aslappyslashy (上游) 建模词汇 |
| `dige_product_surface_patterns.md` | dige viewer 产品 surface 模式 |
| `endfield_base_report_notes.md` | endfield base report 数据 |
| `endfield_calc_catalog_inventory.md` | endfield-calc catalog 清单 |
| `endfield_calc_current_repository_semantic_alignment.md` | endfield-calc 仓库语义对齐 |
| `endfield_calc_snapshot_ingest_mapping.md` | endfield-calc 摄取映射 |
| `exploratory_layout_inspirations.md` | 探索性布局思路 (非 active) |
| `industrial_planner_blueprint_contract_notes.md` | IP v2 蓝图契约 notes |
| `industrial_planner_frontend_inventory.md` | IP v2 前端清单 |

---

## 怎么用

- 改 `src/models/master_model.py` 的约束类型 → 看 `07_master_placement_model.md`
- 改 Benders cut 结构 → 看 `10_benders_decomposition_and_cut_design.md`
- 改 blueprint 输出格式 → 看 `12_output_blueprint_schema.md`
- 改 canonical_rules.json → 看 `20_canonical_rules_consolidation.md` + PROJECT_LOCK gate
- 加新 adapter → 看 `13` (总策略) + 看具体 contract spec

---

## Spec 跟 code 不同步的情况

实操中 spec 一般落后代码几个版本 (因为代码先写, spec 后追上). 重大改动 (改 schema / 改 lex 定义 / 加 new mode) **必须** spec 跟 commit 同步.

如果 spec 跟 code 看起来冲突, 默认**信代码**, 但要立 issue 让 spec 更新.

---

## Memory 链

- [[project_endfield_solver]] — 项目总览
