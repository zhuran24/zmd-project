# 当前文档分区索引

> 本页由 section registry 与有效 `DOC_POLICY.json` 自动生成；禁止手工修改。
> 文档系统版本：`2.6.0`；分区摘要：`sha256:b2bdeef3f5e18bb753d5876cc3ba52645ab6e88c3a800c4f65275c3e5721bafd`。
> 真源：[`data/repository_governance/document_system/sections.json`](<../data/repository_governance/document_system/sections.json>)。

分区把当前文档按问题域组织起来。它不改变 authority，也不把历史 evidence 提升为现行说明。一个文档可以跨多个分区，但每个分区只有一个登记入口。

按任务选择入口见 [START_HERE](START_HERE.md)；按职责类型查看完整 current surface 见 [GUIDANCE_INDEX](GUIDANCE_INDEX.md)。

## 分区总览

| Section | 入口 | 类型 | 当前成员 | 唯一职责 |
|---|---|---|---:|---|
| `repository-navigation` | [`README.md`](<../README.md>) | `manual` | 7 | 稳定仓库身份、任务路由、代码地图和 agent 最小自举入口。 |
| `knowledge` | [`data/knowledge/README.md`](<../data/knowledge/README.md>) | `manual` | 9 | current state、claim、decision、dossier、topic、terminology 与有效性投影的写入和查询入口。 |
| `documentation-framework` | [`docs/governance/document-system/ARCHITECTURE.md`](<governance/document-system/ARCHITECTURE.md>) | `manual` | 35 | 文档类型、继承策略、框架维护、自举恢复、职责投影、周期审计与常态交接。 |
| `project-manual` | [`docs/项目说明/README.md`](<项目说明/README.md>) | `manual` | 24 | 稳定语义、数学背景、工作流、风险、未来路线与编年史。 |
| `specifications` | [`specs/README.md`](<../specs/README.md>) | `manual` | 26 | 编号 specification 的规范边界、阅读顺序与非权威生态注记分流。 |
| `operations` | [`docs/OPERATIONS.md`](<OPERATIONS.md>) | `manual` | 8 | campaign、并行、环境变量、probe、脚本、agent 操作与故障处理入口。 |
| `research-archive` | [`docs/research/README.md`](<research/README.md>) | `manual` | 3 | dated dossier、外审、实验与 transcript 的证据边界和知识晋升入口。 |
| `history-archive` | [`docs/history/README.md`](<history/README.md>) | `manual` | 7 | 退出当前职责的字节快照、旧导航和冻结 delivery 文档的可发现入口。 |
| `topic-guides` | [`docs/subjects/README.md`](<subjects/README.md>) | `manual` | 10 | 少量稳定概念速查；当前值与可枚举知识仍委托给生成投影。 |
| `formal-verification` | [`formal/README.md`](<../formal/README.md>) | `manual` | 1 | Lean 模块、构建方式、公理审计、陈述边界与研究证据坐标；不自行提升 production certification。 |
| `certification` | [`docs/CERTIFICATION.md`](<CERTIFICATION.md>) | `manual` | 6 | 认证问题的有界导航入口；PROJECT_LOCK 仍是 owner-only 的最高仓内权威。 |
| `compatibility-adapters` | [`docs/compatibility_matrix.md`](<compatibility_matrix.md>) | `manual` | 4 | 外部生态借用、adapter/export 边界和冻结 IndustrialPlanner delivery 入口。 |
| `repository-governance` | [`data/repository_governance/README.md`](<../data/repository_governance/README.md>) | `manual` | 1 | 代码资产、legacy 引用扫描、文档框架机器注册表与周期审计的 fail-closed 治理。 |
| `implementation-navigation` | [`NAV_MAP.md`](<../NAV_MAP.md>) | `manual` | 2 | 代码、数据、脚本和模块局部说明的稳定导航，不承担当前状态。 |

## 仓库导航与 agent 自举 (`repository-navigation`)

入口：[`README.md`](<../README.md>)；类型：`manual`；关联分区：`knowledge`, `operations`, `documentation-framework`。

稳定仓库身份、任务路由、代码地图和 agent 最小自举入口。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`BORROWED_COMPONENTS.md`](<../BORROWED_COMPONENTS.md>) | `living` | `direct` | External component borrowing ledger and compatibility boundary; it records provenance without granting certification authority. |
| [`FILE_STATUS.md`](<../FILE_STATUS.md>) | `generated_projection` | `generator_only` | Generated compatibility redirect from the retired file-status page to current surfaces. |
| [`NAV_MAP.md`](<../NAV_MAP.md>) | `living` | `direct` | Stable map of active code, data, script and adapter entrypoints; it never carries current project state. |
| [`README.md`](<../README.md>) **（入口）** | `living` | `direct` | 稳定仓库前门，只链接当前状态、知识目录、权威边界和开发入口。 |
| [`docs/README.md`](<README.md>) | `living` | `direct` | 文档层稳定前门；按问题路由到唯一当前状态、知识投影、职责索引和框架说明。 |
| [`docs/SECTION_INDEX.md`](<SECTION_INDEX.md>) | `generated_projection` | `generator_only` | Generated current document-section map from section registry and effective policy membership. |
| [`docs/START_HERE.md`](<START_HERE.md>) | `living` | `direct` | Stable task-oriented navigation that avoids volatile values. |

## 当前状态与结构化知识 (`knowledge`)

入口：[`data/knowledge/README.md`](<../data/knowledge/README.md>)；类型：`manual`；关联分区：`research-archive`, `topic-guides`, `certification`。

current state、claim、decision、dossier、topic、terminology 与有效性投影的写入和查询入口。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`data/knowledge/README.md`](<../data/knowledge/README.md>) **（入口）** | `living` | `governed` | Operating guide for the structured knowledge layer. |
| [`docs/BACKFILL_LEDGER.md`](<BACKFILL_LEDGER.md>) | `generated_projection` | `generator_only` | Generated separation of semantic reviews, availability-only reviews and exhaustive long-tail dossier triage. |
| [`docs/CATALOG.md`](<CATALOG.md>) | `generated_projection` | `generator_only` | Generated catalog of claims, decisions, dossier inventory, semantic reviews and validity coordinates. |
| [`docs/CURRENT.md`](<CURRENT.md>) | `generated_projection` | `generator_only` | Unique human-readable current-state projection. |
| [`docs/OPEN_QUESTIONS.md`](<OPEN_QUESTIONS.md>) | `generated_projection` | `generator_only` | Generated exact set of status=open claims, deduplicated across topic memberships. |
| [`docs/REASONING_LEDGER.md`](<REASONING_LEDGER.md>) | `generated_projection` | `generator_only` | Generated reasoning classification, derivation graph, selection/separation/consumption profile, propagation-evidence boundary and historical backfill coverage. |
| [`docs/TERMINOLOGY.md`](<TERMINOLOGY.md>) | `generated_projection` | `generator_only` | Generated canonical terminology, aliases, distinctions and source coordinates. |
| [`docs/TOPIC_INDEX.md`](<TOPIC_INDEX.md>) | `generated_projection` | `generator_only` | Generated stable topic entry points over claims, dossier labels, terms and open questions. |
| [`docs/VALIDITY_LEDGER.md`](<VALIDITY_LEDGER.md>) | `generated_projection` | `generator_only` | Generated refutation, semantic replacement, implementation/experiment invalidation, attribution correction, revalidation and supersession ledger. |

## 文档系统框架 (`documentation-framework`)

入口：[`docs/governance/document-system/ARCHITECTURE.md`](<governance/document-system/ARCHITECTURE.md>)；类型：`manual`；关联分区：`repository-navigation`, `repository-governance`, `knowledge`。

文档类型、继承策略、框架维护、自举恢复、职责投影、周期审计与常态交接。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`.docsystem/RECOVERY.md`](<../.docsystem/RECOVERY.md>) | `framework_core` | `governed` | Fail-closed bootstrap recovery procedure for manifest or resolver failure. |
| [`docs/CONVERGENCE_REPORT.md`](<CONVERGENCE_REPORT.md>) | `generated_projection` | `generator_only` | Generated acceptance report for current-document reachability, unique responsibilities, volatile-state discipline and retired-entrypoint isolation. |
| [`docs/DOC_TREE_COMPLETENESS.md`](<DOC_TREE_COMPLETENESS.md>) | `generated_projection` | `generator_only` | Generated compatibility redirect from retired document-tree or subject-tree surfaces. |
| [`docs/MAINTENANCE_QUEUE.md`](<MAINTENANCE_QUEUE.md>) | `generated_projection` | `generator_only` | Generated periodic maintenance findings over existing policy, knowledge, lifecycle and Git-visible truth sources. |
| [`docs/SECTION_INDEX.md`](<SECTION_INDEX.md>) | `generated_projection` | `generator_only` | Generated current document-section map from section registry and effective policy membership. |
| [`docs/SUBJECT_TREE.md`](<SUBJECT_TREE.md>) | `generated_projection` | `generator_only` | Generated compatibility redirect from retired document-tree or subject-tree surfaces. |
| [`docs/governance/document-system/ADR/001-inherited-policy-and-progressive-disclosure.md`](<governance/document-system/ADR/001-inherited-policy-and-progressive-disclosure.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/002-self-governing-framework-core.md`](<governance/document-system/ADR/002-self-governing-framework-core.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/003-legacy-doc-classes-as-generated-projection.md`](<governance/document-system/ADR/003-legacy-doc-classes-as-generated-projection.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/004-backfill-review-and-reasoning-projection.md`](<governance/document-system/ADR/004-backfill-review-and-reasoning-projection.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/005-derivation-graph-and-mathematical-families.md`](<governance/document-system/ADR/005-derivation-graph-and-mathematical-families.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/006-selection-separation-and-consumption-profile.md`](<governance/document-system/ADR/006-selection-separation-and-consumption-profile.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/007-validity-events-and-explicit-supersession.md`](<governance/document-system/ADR/007-validity-events-and-explicit-supersession.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/008-semantic-review-and-inventory-triage.md`](<governance/document-system/ADR/008-semantic-review-and-inventory-triage.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/009-explicit-current-guidance-surface.md`](<governance/document-system/ADR/009-explicit-current-guidance-surface.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/010-bounded-entrypoints-and-on-demand-agent-guide.md`](<governance/document-system/ADR/010-bounded-entrypoints-and-on-demand-agent-guide.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/011-explicit-sections-and-retired-local-indexes.md`](<governance/document-system/ADR/011-explicit-sections-and-retired-local-indexes.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/012-current-graph-convergence-audit.md`](<governance/document-system/ADR/012-current-graph-convergence-audit.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/013-non-mutating-governance-gate.md`](<governance/document-system/ADR/013-non-mutating-governance-gate.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/014-event-driven-document-intake.md`](<governance/document-system/ADR/014-event-driven-document-intake.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/015-periodic-semantic-maintenance-audit.md`](<governance/document-system/ADR/015-periodic-semantic-maintenance-audit.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/016-real-repository-topology-and-workspace-overlays.md`](<governance/document-system/ADR/016-real-repository-topology-and-workspace-overlays.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md`](<governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/018-nondestructive-real-repository-landing.md`](<governance/document-system/ADR/018-nondestructive-real-repository-landing.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/019-bounded-governance-concurrency-and-slow-test-evidence.md`](<governance/document-system/ADR/019-bounded-governance-concurrency-and-slow-test-evidence.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/020-steady-state-transition-and-maintenance-handoff.md`](<governance/document-system/ADR/020-steady-state-transition-and-maintenance-handoff.md>) | `framework_core` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/README.md`](<governance/document-system/ADR/README.md>) | `framework_core` | `governed` | Current index of framework ADRs. |
| [`docs/governance/document-system/ARCHITECTURE.md`](<governance/document-system/ARCHITECTURE.md>) **（入口）** | `framework_core` | `governed` | Current conceptual architecture, invariants and component relationships of the self-describing document system. |
| [`docs/governance/document-system/MAINTAINING.md`](<governance/document-system/MAINTAINING.md>) | `framework_core` | `governed` | Safe change, migration, generation, testing and recovery procedure for the document framework. |
| [`docs/governance/document-system/REAL_REPOSITORY_LANDING.md`](<governance/document-system/REAL_REPOSITORY_LANDING.md>) | `framework_core` | `governed` | Current architecture, safe evolution protocol and design-decision history for the self-describing document system. |
| [`docs/governance/document-system/STEADY_STATE.md`](<governance/document-system/STEADY_STATE.md>) | `framework_core` | `governed` | Durable steady-state maintenance contract, framework reopening criteria and fail-closed handoff after the staged documentation rebuild. |
| [`docs/subjects/current_project_state.md`](<subjects/current_project_state.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/doc_tree_architecture.md`](<subjects/doc_tree_architecture.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/doc_tree_completeness.md`](<subjects/doc_tree_completeness.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/project_knowledge_tree.md`](<subjects/project_knowledge_tree.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |

## 项目手册 (`project-manual`)

入口：[`docs/项目说明/README.md`](<项目说明/README.md>)；类型：`manual`；关联分区：`knowledge`, `operations`, `specifications`。

稳定语义、数学背景、工作流、风险、未来路线与编年史。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`docs/项目说明/00_master_roadmap.md`](<项目说明/00_master_roadmap.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/01_overview.md`](<项目说明/01_overview.md>) | `normative` | `governed` | Stable project proposition, semantic layers and authority boundaries. |
| [`docs/项目说明/02_mathematical_foundations.md`](<项目说明/02_mathematical_foundations.md>) | `living` | `direct` | Mathematical objects, notation and proof obligations used by the project. |
| [`docs/项目说明/04_design_invariants.md`](<项目说明/04_design_invariants.md>) | `living` | `direct` | Cross-layer design invariants that implementation and evidence must preserve. |
| [`docs/项目说明/05_open_questions.md`](<项目说明/05_open_questions.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/06_current_status.md`](<项目说明/06_current_status.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/11_dependency_graph.md`](<项目说明/11_dependency_graph.md>) | `living` | `direct` | Dependency graph between authorities, models, solvers, evidence and publication surfaces. |
| [`docs/项目说明/12_go_criteria.md`](<项目说明/12_go_criteria.md>) | `normative` | `governed` | Stable vocabulary and evidence contract for GO, close and release judgments. |
| [`docs/项目说明/14_risk_rollout.md`](<项目说明/14_risk_rollout.md>) | `living` | `direct` | Risk classification, rollout order and rollback evidence for current engineering work. |
| [`docs/项目说明/15_workflow_testing.md`](<项目说明/15_workflow_testing.md>) | `living` | `direct` | Stable testing-layer, fixture and evidence-interpretation protocol without current receipts. |
| [`docs/项目说明/16_workflow_review.md`](<项目说明/16_workflow_review.md>) | `living` | `direct` | Review roles, adversarial checks and acceptance boundaries for project changes. |
| [`docs/项目说明/17_workflow_telemetry.md`](<项目说明/17_workflow_telemetry.md>) | `living` | `direct` | Telemetry schema, interpretation limits and non-authorizing observability contract. |
| [`docs/项目说明/18_workflow_env_config.md`](<项目说明/18_workflow_env_config.md>) | `living` | `direct` | Environment configuration ownership, precedence and reproducibility discipline. |
| [`docs/项目说明/19_implementation_rhythm.md`](<项目说明/19_implementation_rhythm.md>) | `living` | `direct` | Iteration rhythm, handoff discipline and phase-boundary maintenance protocol. |
| [`docs/项目说明/21_glossary.md`](<项目说明/21_glossary.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/23_rule_cut_evolution_protocol.md`](<项目说明/23_rule_cut_evolution_protocol.md>) | `normative` | `governed` | Stable governance protocol for rule semantics, cut-family evolution, validation and production admission. |
| [`docs/项目说明/24_repository_asset_governance.md`](<项目说明/24_repository_asset_governance.md>) | `normative` | `governed` | Stable code-asset classification, workflow isolation and retirement governance contract. |
| [`docs/项目说明/26_rules_handbook.md`](<项目说明/26_rules_handbook.md>) | `normative` | `governed` | Human-readable canonical-rule interpretation and source-of-authority guide. |
| [`docs/项目说明/27_status_dashboard.md`](<项目说明/27_status_dashboard.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/28_pitfalls_and_sop.md`](<项目说明/28_pitfalls_and_sop.md>) | `living` | `direct` | Operational pitfalls, fail-closed recovery patterns and recurring SOPs. |
| [`docs/项目说明/29_solving_methodology_skill.md`](<项目说明/29_solving_methodology_skill.md>) | `living` | `direct` | Project-level solving-methodology skill source for knowledge-computation decomposition in scientific, mathematical and solver work; it summarizes and routes methodology without granting owner authority. |
| [`docs/项目说明/README.md`](<项目说明/README.md>) **（入口）** | `living` | `direct` | Bounded project-manual front door for current guides, normative contracts, future work and history. |
| [`docs/项目说明/REASONING_METHOD.md`](<项目说明/REASONING_METHOD.md>) | `normative` | `governed` | Reusable mathematical reasoning and separation-method design principles. |
| [`docs/项目说明/ROADMAP.md`](<项目说明/ROADMAP.md>) | `living` | `direct` | Future-only roadmap with dependencies and exit evidence, excluding current-state copies. |

## 规范与设计契约 (`specifications`)

入口：[`specs/README.md`](<../specs/README.md>)；类型：`manual`；关联分区：`certification`, `compatibility-adapters`, `operations`。

编号 specification 的规范边界、阅读顺序与非权威生态注记分流。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`docs/specs_index.md`](<specs_index.md>) | `generated_projection` | `generator_only` | Generated compatibility redirect from the retired docs/specs_index.md map to specs/README.md. |
| [`specs/01_problem_statement.md`](<../specs/01_problem_statement.md>) | `normative` | `governed` | Normative problem statement, objective and certified/exploratory proposition boundary. |
| [`specs/02_global_notation_and_units.md`](<../specs/02_global_notation_and_units.md>) | `normative` | `governed` | Normative global notation, coordinates, units and indexing conventions. |
| [`specs/03_rule_canonicalization.md`](<../specs/03_rule_canonicalization.md>) | `normative` | `governed` | Normative canonical-rule ingestion, normalization and conflict handling contract. |
| [`specs/04_recipe_and_demand_expansion.md`](<../specs/04_recipe_and_demand_expansion.md>) | `normative` | `governed` | Normative recipe graph and demand-expansion contract. |
| [`specs/05_facility_instance_definition.md`](<../specs/05_facility_instance_definition.md>) | `normative` | `governed` | Normative facility-template and instance-construction contract. |
| [`specs/06_candidate_placement_enumeration.md`](<../specs/06_candidate_placement_enumeration.md>) | `normative` | `governed` | Normative candidate-placement enumeration, sound domain reduction and artifact schema contract. |
| [`specs/07_master_placement_model.md`](<../specs/07_master_placement_model.md>) | `normative` | `governed` | Normative master placement variables, constraints and objective contract. |
| [`specs/08_topological_flow_subproblem.md`](<../specs/08_topological_flow_subproblem.md>) | `normative` | `governed` | Normative topological flow diagnostic subproblem and interpretation boundary. |
| [`specs/09_exact_grid_routing_subproblem.md`](<../specs/09_exact_grid_routing_subproblem.md>) | `normative` | `governed` | Normative exact grid-routing subproblem and feasibility contract. |
| [`specs/10_benders_decomposition_and_cut_design.md`](<../specs/10_benders_decomposition_and_cut_design.md>) | `normative` | `governed` | Normative decomposition, cut validity and lifecycle design contract. |
| [`specs/11_pipeline_orchestration.md`](<../specs/11_pipeline_orchestration.md>) | `normative` | `governed` | Normative pipeline orchestration and cross-stage obligation contract. |
| [`specs/12_output_blueprint_schema.md`](<../specs/12_output_blueprint_schema.md>) | `normative` | `governed` | Normative output blueprint schema and serialization boundary. |
| [`specs/13_ecosystem_borrowing_and_compatibility_plan.md`](<../specs/13_ecosystem_borrowing_and_compatibility_plan.md>) | `normative` | `governed` | Normative borrowing and compatibility boundary for external ecosystems. |
| [`specs/14_normalized_catalog_contract.md`](<../specs/14_normalized_catalog_contract.md>) | `normative` | `governed` | Normative normalized catalog schema and identity contract. |
| [`specs/15_target_export_and_compatibility_manifest.md`](<../specs/15_target_export_and_compatibility_manifest.md>) | `normative` | `governed` | Normative target-export manifest and compatibility declaration contract. |
| [`specs/16_industrial_planner_export_contract.md`](<../specs/16_industrial_planner_export_contract.md>) | `normative` | `governed` | Normative IndustrialPlanner export contract and non-authoritative adapter boundary. |
| [`specs/17_endfield_calc_ingest_contract.md`](<../specs/17_endfield_calc_ingest_contract.md>) | `normative` | `governed` | Normative Endfield calculator ingest and normalization contract. |
| [`specs/18_preprocess_context_contract.md`](<../specs/18_preprocess_context_contract.md>) | `normative` | `governed` | Normative preprocess-context identity and reproducibility contract. |
| [`specs/19_phase3_frozen_compatible_preprocess_regeneration.md`](<../specs/19_phase3_frozen_compatible_preprocess_regeneration.md>) | `normative` | `governed` | Normative frozen-compatible preprocess regeneration and equivalence contract. |
| [`specs/20_canonical_rules_consolidation.md`](<../specs/20_canonical_rules_consolidation.md>) | `normative` | `governed` | Normative canonical-rule consolidation, provenance and conflict-resolution contract. |
| [`specs/21_frontier_probe_and_campaign_telemetry.md`](<../specs/21_frontier_probe_and_campaign_telemetry.md>) | `normative` | `governed` | Normative frontier-probe, campaign telemetry and interpretation contract. |
| [`specs/22_industrial_planner_precision_export_and_validator_spec.md`](<../specs/22_industrial_planner_precision_export_and_validator_spec.md>) | `normative` | `governed` | Normative precision export and validator contract for IndustrialPlanner derivatives. |
| [`specs/23_industrial_planner_outer_base_planning_representation.md`](<../specs/23_industrial_planner_outer_base_planning_representation.md>) | `normative` | `governed` | Normative outer-base planning representation and adapter boundary. |
| [`specs/README.md`](<../specs/README.md>) **（入口）** | `living` | `governed` | Bounded local front door for numbered specifications and ecosystem-note boundaries. |
| [`specs/ecosystem_notes/README.md`](<../specs/ecosystem_notes/README.md>) | `living` | `governed` | Current local entrypoint for frozen, non-authoritative ecosystem research notes. |

## 运行与维护 (`operations`)

入口：[`docs/OPERATIONS.md`](<OPERATIONS.md>)；类型：`manual`；关联分区：`repository-navigation`, `project-manual`, `specifications`。

campaign、并行、环境变量、probe、脚本、agent 操作与故障处理入口。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`docs/AGENT_OPERATIONS.md`](<AGENT_OPERATIONS.md>) | `living` | `direct` | 按需加载的详细 agent 运行、测试、冻结、发布和故障处理手册。 |
| [`docs/OPERATIONS.md`](<OPERATIONS.md>) **（入口）** | `living` | `direct` | Bounded local entrypoint for campaign, parallelism, scripts, agent operations and failure handling. |
| [`docs/env_variable_index.md`](<env_variable_index.md>) | `living` | `direct` | Stable index of runtime environment variables, precedence and validation boundaries. |
| [`docs/exact_campaign_operations.md`](<exact_campaign_operations.md>) | `living` | `direct` | Stable operator procedure for campaign inspection, resume, supervisor seal and canonical publication boundaries. |
| [`docs/frontier_probe_strategy.md`](<frontier_probe_strategy.md>) | `living` | `direct` | Stable strategy guide for frontier probing, fallback interpretation and evidence boundaries. |
| [`docs/parallel_configuration.md`](<parallel_configuration.md>) | `living` | `direct` | Stable method for selecting and validating process and solver-worker resource settings. |
| [`scripts/README.md`](<../scripts/README.md>) | `living` | `direct` | Stable operator map for active, governance, packaging, preprocess and historical script roles. |
| [`scripts/pumpkin_poc/README.md`](<../scripts/pumpkin_poc/README.md>) | `living` | `direct` | Bounded operator and reproduction guide for the Pumpkin proof-of-concept scripts. |

## 研究与外审档案 (`research-archive`)

入口：[`docs/research/README.md`](<research/README.md>)；类型：`manual`；关联分区：`knowledge`, `history-archive`, `topic-guides`。

dated dossier、外审、实验与 transcript 的证据边界和知识晋升入口。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`.artifacts/README.md`](<../.artifacts/README.md>) | `living` | `direct` | Current boundary, portability and retention guidance for local evidence roots. |
| [`docs/research/INDEX.md`](<research/INDEX.md>) | `generated_projection` | `generator_only` | Generated compatibility redirect from the ambiguous research INDEX to the archive front door and named transcript payload. |
| [`docs/research/README.md`](<research/README.md>) **（入口）** | `living` | `direct` | Current lifecycle and navigation guide for the research archive. |

## 历史快照与冻结交付 (`history-archive`)

入口：[`docs/history/README.md`](<history/README.md>)；类型：`manual`；关联分区：`research-archive`, `documentation-framework`, `compatibility-adapters`。

退出当前职责的字节快照、旧导航和冻结 delivery 文档的可发现入口。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`docs/history/README.md`](<history/README.md>) **（入口）** | `living` | `direct` | Current navigation across all immutable historical snapshot families. |
| [`docs/history/convergence/README.md`](<history/convergence/README.md>) | `living` | `direct` | Current navigation for Phase 3 responsibility-convergence source snapshots. |
| [`docs/history/deliveries/README.md`](<history/deliveries/README.md>) | `living` | `direct` | Current navigation for frozen adapter and delivery documentation. |
| [`docs/history/formal/README.md`](<history/formal/README.md>) | `living` | `direct` | Current navigation for retired formal-verification explanatory snapshots. |
| [`docs/history/navigation/README.md`](<history/navigation/README.md>) | `living` | `direct` | Current navigation for retired indexes, maps and knowledge-tree surfaces. |
| [`docs/history/status/README.md`](<history/status/README.md>) | `living` | `direct` | Current navigation for retired status, roadmap and project-state snapshots. |
| [`docs/history/subjects/README.md`](<history/subjects/README.md>) | `living` | `direct` | Current navigation for pre-knowledge-spine subject projections. |

## 主题阅读辅助 (`topic-guides`)

入口：[`docs/subjects/README.md`](<subjects/README.md>)；类型：`manual`；关联分区：`knowledge`, `certification`, `documentation-framework`。

少量稳定概念速查；当前值与可枚举知识仍委托给生成投影。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`docs/DOC_TREE_COMPLETENESS.md`](<DOC_TREE_COMPLETENESS.md>) | `generated_projection` | `generator_only` | Generated compatibility redirect from retired document-tree or subject-tree surfaces. |
| [`docs/SUBJECT_TREE.md`](<SUBJECT_TREE.md>) | `generated_projection` | `generator_only` | Generated compatibility redirect from retired document-tree or subject-tree surfaces. |
| [`docs/subjects/README.md`](<subjects/README.md>) **（入口）** | `living` | `direct` | Bounded entrypoint for stable thematic reading aids. |
| [`docs/subjects/authoritative_numbers.md`](<subjects/authoritative_numbers.md>) | `living` | `direct` | Guide for locating and citing machine-authoritative numeric values without copying them. |
| [`docs/subjects/certification_taxonomy.md`](<subjects/certification_taxonomy.md>) | `living` | `direct` | Concept guide separating verification, acceptance, sealing and publication. |
| [`docs/subjects/certified_exact_contract.md`](<subjects/certified_exact_contract.md>) | `living` | `direct` | Concept guide for certified-exact scope, exclusions and authority boundaries. |
| [`docs/subjects/current_project_state.md`](<subjects/current_project_state.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/doc_tree_architecture.md`](<subjects/doc_tree_architecture.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/doc_tree_completeness.md`](<subjects/doc_tree_completeness.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/project_knowledge_tree.md`](<subjects/project_knowledge_tree.md>) | `generated_projection` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |

## 形式化验证 (`formal-verification`)

入口：[`formal/README.md`](<../formal/README.md>)；类型：`manual`；关联分区：`certification`, `research-archive`, `knowledge`。

Lean 模块、构建方式、公理审计、陈述边界与研究证据坐标；不自行提升 production certification。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`formal/README.md`](<../formal/README.md>) **（入口）** | `living` | `governed` | Bounded local entrypoint for Lean replay, statement scope, axiom audit and certification boundaries. |

## 认证与发布边界 (`certification`)

入口：[`docs/CERTIFICATION.md`](<CERTIFICATION.md>)；类型：`manual`；关联分区：`knowledge`, `specifications`, `operations`, `formal-verification`。

认证问题的有界导航入口；PROJECT_LOCK 仍是 owner-only 的最高仓内权威。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`PROJECT_LOCK.md`](<../PROJECT_LOCK.md>) | `locked_authority` | `owner_only` | certified exactness、命题边界、发布纪律与禁止改动的最高仓内权威。 |
| [`certside/README.md`](<../certside/README.md>) | `normative` | `governed` | Certification-side operator entrypoint and scope boundary. |
| [`certside/binding_canonical_semantics_v1.md`](<../certside/binding_canonical_semantics_v1.md>) | `normative` | `governed` | Normative binding between certification checks and canonical project semantics. |
| [`docs/CERTIFICATION.md`](<CERTIFICATION.md>) **（入口）** | `living` | `direct` | Bounded navigation from certification questions to the owner authority, phase-gate contract, current projection and certside semantics. |
| [`docs/PHASE_1_2_CLOSE_GATE.md`](<PHASE_1_2_CLOSE_GATE.md>) | `normative` | `governed` | Stable human-readable phase-gate contract; live values come from CURRENT and gate JSON. |
| [`docs/项目说明/12_go_criteria.md`](<项目说明/12_go_criteria.md>) | `normative` | `governed` | Stable vocabulary and evidence contract for GO, close and release judgments. |

## 兼容层与适配器 (`compatibility-adapters`)

入口：[`docs/compatibility_matrix.md`](<compatibility_matrix.md>)；类型：`manual`；关联分区：`specifications`, `history-archive`, `operations`。

外部生态借用、adapter/export 边界和冻结 IndustrialPlanner delivery 入口。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`BORROWED_COMPONENTS.md`](<../BORROWED_COMPONENTS.md>) | `living` | `direct` | External component borrowing ledger and compatibility boundary; it records provenance without granting certification authority. |
| [`docs/compatibility_matrix.md`](<compatibility_matrix.md>) **（入口）** | `living` | `direct` | Current compatibility and adapter boundary; target exports never become certified proof sinks. |
| [`specs/ecosystem_notes/README.md`](<../specs/ecosystem_notes/README.md>) | `living` | `governed` | Current local entrypoint for frozen, non-authoritative ecosystem research notes. |
| [`src/adapters/README.md`](<../src/adapters/README.md>) | `living` | `direct` | Module-local implementation guidance. |

## 仓库治理 (`repository-governance`)

入口：[`data/repository_governance/README.md`](<../data/repository_governance/README.md>)；类型：`manual`；关联分区：`documentation-framework`, `repository-navigation`。

代码资产、legacy 引用扫描、文档框架机器注册表与周期审计的 fail-closed 治理。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`data/repository_governance/README.md`](<../data/repository_governance/README.md>) **（入口）** | `governance_control` | `governed` | Fail-closed repository governance registries and schemas. |

## 代码与模块导航 (`implementation-navigation`)

入口：[`NAV_MAP.md`](<../NAV_MAP.md>)；类型：`manual`；关联分区：`repository-navigation`, `operations`, `compatibility-adapters`。

代码、数据、脚本和模块局部说明的稳定导航，不承担当前状态。

| 文档 | Class | Mutation | 唯一职责 |
|---|---|---|---|
| [`NAV_MAP.md`](<../NAV_MAP.md>) **（入口）** | `living` | `direct` | Stable map of active code, data, script and adapter entrypoints; it never carries current project state. |
| [`src/adapters/README.md`](<../src/adapters/README.md>) | `living` | `direct` | Module-local implementation guidance. |

修改分区、入口或成员归属时，先改 section registry / local policy，再运行：

```bash
.venv/bin/python devtools/docctl.py render-sections --write
.venv/bin/python devtools/docctl.py render-guidance --write
```
