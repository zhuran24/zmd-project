# 当前文档职责索引

> 本页由有效 `DOC_POLICY.json` 契约、前门注册表与 section registry 自动生成；禁止手工修改。
> 文档系统版本：`2.6.0`；职责摘要：`sha256:e892c047be7e4732b5818f25e6c464f0a160634d9b80c6c6d0eaf903dd5453d4`。

本页回答“哪些文档仍承担当前职责、各自唯一负责什么”。它不授予新的 authority，也不列历史证据；历史 dossier 与快照分别从 CATALOG、BACKFILL_LEDGER 和 `docs/history/` 下钻。

## 使用边界

- `generated_projection` 只能修改结构化源后重建。
- `locked_authority` 只按 owner / freeze 协议改变。
- `normative` 保存稳定契约，不复制 CURRENT 中的易变状态。
- `living` 解释怎样理解和怎样做，当前值仍回到 CURRENT 或机器源。
- 修改任一路径前先运行 `docctl context <path> --intent edit`。
- 按局部问题域进入时先看 [SECTION_INDEX](SECTION_INDEX.md)；本页是全量职责投影。

## 固定入口图

这些入口的职责、注意力预算和兼容跳转来自机器可读前门注册表。

| ID | 类型 | 路径 | 预算 | 唯一职责 |
|---|---|---|---:|---|
| `agent_operations` | `manual` | [`docs/AGENT_OPERATIONS.md`](<AGENT_OPERATIONS.md>) | 360 行 | tracked 的耐久 agent 操作与维护指南；可选根 overlay 只作本机会话入口。 |
| `certified_authority` | `authority` | [`PROJECT_LOCK.md`](<../PROJECT_LOCK.md>) | — | certified exactness、命题边界与发布纪律的仓内最高权威。 |
| `current_guidance_surface` | `generated` | [`docs/GUIDANCE_INDEX.md`](<GUIDANCE_INDEX.md>) | — | 当前仍承担职责的文档表面投影。 |
| `current_state` | `generated` | [`docs/CURRENT.md`](<CURRENT.md>) | — | 唯一人类可读现态投影。 |
| `document_sections` | `generated` | [`docs/SECTION_INDEX.md`](<SECTION_INDEX.md>) | — | 按稳定 section ID 投影局部前门、当前成员和跨分区关系。 |
| `documentation_front_door` | `manual` | [`docs/README.md`](<README.md>) | 42 行 | 文档层稳定前门，解释知识投影、authority 分工和生命周期。 |
| `project_manual_front_door` | `manual` | [`docs/项目说明/README.md`](<项目说明/README.md>) | 35 行 | 项目手册分区入口，只列现行手册、规范、未来、方法与历史。 |
| `repository_front_door` | `manual` | [`README.md`](<../README.md>) | 48 行 | 仓库级稳定前门，只负责身份、分层导航、最小操作面和权威入口。 |
| `task_router` | `manual` | [`docs/START_HERE.md`](<START_HERE.md>) | 70 行 | 按用户问题选择当前状态、知识、主题、历史或操作入口。 |
| `code_map` | `guarded_document` | [`NAV_MAP.md`](<../NAV_MAP.md>) | — | Stable code and data navigation that must not become a current-state ledger. |
| `phase_gate_contract` | `guarded_document` | [`docs/PHASE_1_2_CLOSE_GATE.md`](<PHASE_1_2_CLOSE_GATE.md>) | — | Stable human-readable gate contract that points to CURRENT for live values. |
| `pipeline_orchestration_spec` | `guarded_document` | [`specs/11_pipeline_orchestration.md`](<../specs/11_pipeline_orchestration.md>) | — | Stable orchestration contract that points to CURRENT for live phase and gate state. |
| `project_dependency_graph` | `guarded_document` | [`docs/项目说明/11_dependency_graph.md`](<项目说明/11_dependency_graph.md>) | — | Stable dependency explanation that points to CURRENT for live phase state. |
| `project_go_criteria` | `guarded_document` | [`docs/项目说明/12_go_criteria.md`](<项目说明/12_go_criteria.md>) | — | Stable GO/close evidence vocabulary that points to CURRENT for current decisions. |
| `project_overview` | `guarded_document` | [`docs/项目说明/01_overview.md`](<项目说明/01_overview.md>) | — | Stable project overview that points to CURRENT for all live status. |
| `project_roadmap` | `guarded_document` | [`docs/项目说明/ROADMAP.md`](<项目说明/ROADMAP.md>) | — | Future-only roadmap that must not silently become a current-state dashboard. |
| `research_archive_front_door` | `guarded_document` | [`docs/research/README.md`](<research/README.md>) | — | Research archive entrypoint that distinguishes historical evidence from current state. |
| `subject_authoritative_numbers` | `guarded_document` | [`docs/subjects/authoritative_numbers.md`](<subjects/authoritative_numbers.md>) | — | Thematic guide to authority-bearing numbers without copying their current values. |
| `subject_certification_taxonomy` | `guarded_document` | [`docs/subjects/certification_taxonomy.md`](<subjects/certification_taxonomy.md>) | — | Stable certification vocabulary guide without copied current gate or count values. |
| `subject_certified_exact_contract` | `guarded_document` | [`docs/subjects/certified_exact_contract.md`](<subjects/certified_exact_contract.md>) | — | Stable thematic explanation of the exactness contract without copied current state. |
| `subjects_front_door` | `guarded_document` | [`docs/subjects/README.md`](<subjects/README.md>) | — | Manual thematic-reading entrypoint that delegates current facts to CURRENT. |
| `legacy_current_status` | `generated_redirect` | [`docs/项目说明/06_current_status.md`](<项目说明/06_current_status.md>) | — | 本路径不再维护独立状态正文。 |
| `legacy_document_tree_completeness` | `generated_redirect` | [`docs/DOC_TREE_COMPLETENESS.md`](<DOC_TREE_COMPLETENESS.md>) | — | 旧的一次性完整性快照已由 dossier inventory、policy coverage 和自动 checker 取代。 |
| `legacy_file_status` | `generated_redirect` | [`FILE_STATUS.md`](<../FILE_STATUS.md>) | — | 本路径不再维护独立的文件状态表，只保留到现行查询面的稳定跳转。 |
| `legacy_glossary` | `generated_redirect` | [`docs/项目说明/21_glossary.md`](<项目说明/21_glossary.md>) | — | 规范术语、alias、区别与来源已迁入结构化 terminology registry。 |
| `legacy_master_roadmap` | `generated_redirect` | [`docs/项目说明/00_master_roadmap.md`](<项目说明/00_master_roadmap.md>) | — | 旧混合路线图已按当前、未来和历史三种职责拆分。 |
| `legacy_open_questions` | `generated_redirect` | [`docs/项目说明/05_open_questions.md`](<项目说明/05_open_questions.md>) | — | 开放问题由 claim 账本中 status=open 的集合自动投影。 |
| `legacy_research_index` | `generated_redirect` | [`docs/research/INDEX.md`](<research/INDEX.md>) | — | 该路径曾只覆盖 2026-05-07/08 Phase 3C agent transcript，却容易被误读为全研究目录。 |
| `legacy_specs_index` | `generated_redirect` | [`docs/specs_index.md`](<specs_index.md>) | — | 编号规范的现行分区入口已经迁到 specs/README.md；本路径不再维护第二份规格地图。 |
| `legacy_status_dashboard` | `generated_redirect` | [`docs/项目说明/27_status_dashboard.md`](<项目说明/27_status_dashboard.md>) | — | 旧手写仪表盘已由唯一当前状态和结构化查询页取代。 |
| `legacy_subject_current_state` | `generated_redirect` | [`docs/subjects/current_project_state.md`](<subjects/current_project_state.md>) | — | 本主题路径不再维护独立现态副本。 |
| `legacy_subject_doc_tree_architecture` | `generated_redirect` | [`docs/subjects/doc_tree_architecture.md`](<subjects/doc_tree_architecture.md>) | — | 文档框架的完整现行定义已进入 framework architecture；本主题路径只保留稳定跳转。 |
| `legacy_subject_doc_tree_completeness` | `generated_redirect` | [`docs/subjects/doc_tree_completeness.md`](<subjects/doc_tree_completeness.md>) | — | 目录覆盖、当前职责和语义回填已分别由机器投影承担。 |
| `legacy_subject_project_knowledge_tree` | `generated_redirect` | [`docs/subjects/project_knowledge_tree.md`](<subjects/project_knowledge_tree.md>) | — | 项目知识对象和写入方式已经由知识层指南、CATALOG 与 topic projection 统一表达。 |
| `legacy_subject_tree` | `generated_redirect` | [`docs/SUBJECT_TREE.md`](<SUBJECT_TREE.md>) | — | 旧 subject/projection 机制不再承担当前同步职责。 |

## 当前分区

分区是真正按问题组织的局部入口；完整成员清单见 [SECTION_INDEX](SECTION_INDEX.md)。

| Section | 局部入口 | 类型 | 唯一职责 |
|---|---|---|---|
| `repository-navigation` | [`README.md`](<../README.md>) | `manual` | 稳定仓库身份、任务路由、代码地图和 agent 最小自举入口。 |
| `knowledge` | [`data/knowledge/README.md`](<../data/knowledge/README.md>) | `manual` | current state、claim、decision、dossier、topic、terminology 与有效性投影的写入和查询入口。 |
| `documentation-framework` | [`docs/governance/document-system/ARCHITECTURE.md`](<governance/document-system/ARCHITECTURE.md>) | `manual` | 文档类型、继承策略、框架维护、自举恢复、职责投影、周期审计与常态交接。 |
| `project-manual` | [`docs/项目说明/README.md`](<项目说明/README.md>) | `manual` | 稳定语义、数学背景、工作流、风险、未来路线与编年史。 |
| `specifications` | [`specs/README.md`](<../specs/README.md>) | `manual` | 编号 specification 的规范边界、阅读顺序与非权威生态注记分流。 |
| `operations` | [`docs/OPERATIONS.md`](<OPERATIONS.md>) | `manual` | campaign、并行、环境变量、probe、脚本、agent 操作与故障处理入口。 |
| `research-archive` | [`docs/research/README.md`](<research/README.md>) | `manual` | dated dossier、外审、实验与 transcript 的证据边界和知识晋升入口。 |
| `history-archive` | [`docs/history/README.md`](<history/README.md>) | `manual` | 退出当前职责的字节快照、旧导航和冻结 delivery 文档的可发现入口。 |
| `topic-guides` | [`docs/subjects/README.md`](<subjects/README.md>) | `manual` | 少量稳定概念速查；当前值与可枚举知识仍委托给生成投影。 |
| `formal-verification` | [`formal/README.md`](<../formal/README.md>) | `manual` | Lean 模块、构建方式、公理审计、陈述边界与研究证据坐标；不自行提升 production certification。 |
| `certification` | [`docs/CERTIFICATION.md`](<CERTIFICATION.md>) | `manual` | 认证问题的有界导航入口；PROJECT_LOCK 仍是 owner-only 的最高仓内权威。 |
| `compatibility-adapters` | [`docs/compatibility_matrix.md`](<compatibility_matrix.md>) | `manual` | 外部生态借用、adapter/export 边界和冻结 IndustrialPlanner delivery 入口。 |
| `repository-governance` | [`data/repository_governance/README.md`](<../data/repository_governance/README.md>) | `manual` | 代码资产、legacy 引用扫描、文档框架机器注册表与周期审计的 fail-closed 治理。 |
| `implementation-navigation` | [`NAV_MAP.md`](<../NAV_MAP.md>) | `manual` | 代码、数据、脚本和模块局部说明的稳定导航，不承担当前状态。 |

## 总览

| 类别 | 数量 |
|---|---:|
| `locked_authority` | 1 |
| `generated_projection` | 25 |
| `normative` | 33 |
| `living` | 47 |
| `governance_control` | 1 |
| `framework_core` | 26 |

## 锁定权威入口

| 文档 | Section | Authority | Mutation | 唯一职责 |
|---|---|---|---|---|
| [`PROJECT_LOCK.md`](<../PROJECT_LOCK.md>) | `certification` | `machine_authority` | `owner_only` | certified exactness、命题边界、发布纪律与禁止改动的最高仓内权威。 |

## 自动生成查询页

| 文档 | Section | Authority | Mutation | 唯一职责 |
|---|---|---|---|---|
| [`FILE_STATUS.md`](<../FILE_STATUS.md>) | `repository-navigation` | `projection_only` | `generator_only` | Generated compatibility redirect from the retired file-status page to current surfaces. |
| [`docs/BACKFILL_LEDGER.md`](<BACKFILL_LEDGER.md>) | `knowledge` | `projection_only` | `generator_only` | Generated separation of semantic reviews, availability-only reviews and exhaustive long-tail dossier triage. |
| [`docs/CATALOG.md`](<CATALOG.md>) | `knowledge` | `projection_only` | `generator_only` | Generated catalog of claims, decisions, dossier inventory, semantic reviews and validity coordinates. |
| [`docs/CONVERGENCE_REPORT.md`](<CONVERGENCE_REPORT.md>) | `documentation-framework` | `projection_only` | `generator_only` | Generated acceptance report for current-document reachability, unique responsibilities, volatile-state discipline and retired-entrypoint isolation. |
| [`docs/CURRENT.md`](<CURRENT.md>) | `knowledge` | `projection_only` | `generator_only` | Unique human-readable current-state projection. |
| [`docs/DOC_TREE_COMPLETENESS.md`](<DOC_TREE_COMPLETENESS.md>) | `documentation-framework`, `topic-guides` | `projection_only` | `generator_only` | Generated compatibility redirect from retired document-tree or subject-tree surfaces. |
| [`docs/MAINTENANCE_QUEUE.md`](<MAINTENANCE_QUEUE.md>) | `documentation-framework` | `projection_only` | `generator_only` | Generated periodic maintenance findings over existing policy, knowledge, lifecycle and Git-visible truth sources. |
| [`docs/OPEN_QUESTIONS.md`](<OPEN_QUESTIONS.md>) | `knowledge` | `projection_only` | `generator_only` | Generated exact set of status=open claims, deduplicated across topic memberships. |
| [`docs/REASONING_LEDGER.md`](<REASONING_LEDGER.md>) | `knowledge` | `projection_only` | `generator_only` | Generated reasoning classification, derivation graph, selection/separation/consumption profile, propagation-evidence boundary and historical backfill coverage. |
| [`docs/SECTION_INDEX.md`](<SECTION_INDEX.md>) | `documentation-framework`, `repository-navigation` | `projection_only` | `generator_only` | Generated current document-section map from section registry and effective policy membership. |
| [`docs/SUBJECT_TREE.md`](<SUBJECT_TREE.md>) | `documentation-framework`, `topic-guides` | `projection_only` | `generator_only` | Generated compatibility redirect from retired document-tree or subject-tree surfaces. |
| [`docs/TERMINOLOGY.md`](<TERMINOLOGY.md>) | `knowledge` | `projection_only` | `generator_only` | Generated canonical terminology, aliases, distinctions and source coordinates. |
| [`docs/TOPIC_INDEX.md`](<TOPIC_INDEX.md>) | `knowledge` | `projection_only` | `generator_only` | Generated stable topic entry points over claims, dossier labels, terms and open questions. |
| [`docs/VALIDITY_LEDGER.md`](<VALIDITY_LEDGER.md>) | `knowledge` | `projection_only` | `generator_only` | Generated refutation, semantic replacement, implementation/experiment invalidation, attribution correction, revalidation and supersession ledger. |
| [`docs/research/INDEX.md`](<research/INDEX.md>) | `research-archive` | `projection_only` | `generator_only` | Generated compatibility redirect from the ambiguous research INDEX to the archive front door and named transcript payload. |
| [`docs/specs_index.md`](<specs_index.md>) | `specifications` | `projection_only` | `generator_only` | Generated compatibility redirect from the retired docs/specs_index.md map to specs/README.md. |
| [`docs/subjects/current_project_state.md`](<subjects/current_project_state.md>) | `topic-guides`, `documentation-framework` | `projection_only` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/doc_tree_architecture.md`](<subjects/doc_tree_architecture.md>) | `topic-guides`, `documentation-framework` | `projection_only` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/doc_tree_completeness.md`](<subjects/doc_tree_completeness.md>) | `topic-guides`, `documentation-framework` | `projection_only` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/subjects/project_knowledge_tree.md`](<subjects/project_knowledge_tree.md>) | `topic-guides`, `documentation-framework` | `projection_only` | `generator_only` | Generated compatibility redirects from retired subject-level state, architecture, completeness and knowledge-tree copies. |
| [`docs/项目说明/00_master_roadmap.md`](<项目说明/00_master_roadmap.md>) | `project-manual` | `projection_only` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/05_open_questions.md`](<项目说明/05_open_questions.md>) | `project-manual` | `projection_only` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/06_current_status.md`](<项目说明/06_current_status.md>) | `project-manual` | `projection_only` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/21_glossary.md`](<项目说明/21_glossary.md>) | `project-manual` | `projection_only` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |
| [`docs/项目说明/27_status_dashboard.md`](<项目说明/27_status_dashboard.md>) | `project-manual` | `projection_only` | `generator_only` | Generated compatibility redirects to unique current, future, terminology or open-question successors. |

## 现行规范与契约

| 文档 | Section | Authority | Mutation | 唯一职责 |
|---|---|---|---|---|
| [`certside/README.md`](<../certside/README.md>) | `certification` | `normative_input` | `governed` | Certification-side operator entrypoint and scope boundary. |
| [`certside/binding_canonical_semantics_v1.md`](<../certside/binding_canonical_semantics_v1.md>) | `certification` | `normative_input` | `governed` | Normative binding between certification checks and canonical project semantics. |
| [`docs/PHASE_1_2_CLOSE_GATE.md`](<PHASE_1_2_CLOSE_GATE.md>) | `certification` | `normative_input` | `governed` | Stable human-readable phase-gate contract; live values come from CURRENT and gate JSON. |
| [`docs/项目说明/01_overview.md`](<项目说明/01_overview.md>) | `project-manual` | `normative_input` | `governed` | Stable project proposition, semantic layers and authority boundaries. |
| [`docs/项目说明/12_go_criteria.md`](<项目说明/12_go_criteria.md>) | `project-manual`, `certification` | `normative_input` | `governed` | Stable vocabulary and evidence contract for GO, close and release judgments. |
| [`docs/项目说明/23_rule_cut_evolution_protocol.md`](<项目说明/23_rule_cut_evolution_protocol.md>) | `project-manual` | `normative_input` | `governed` | Stable governance protocol for rule semantics, cut-family evolution, validation and production admission. |
| [`docs/项目说明/24_repository_asset_governance.md`](<项目说明/24_repository_asset_governance.md>) | `project-manual` | `normative_input` | `governed` | Stable code-asset classification, workflow isolation and retirement governance contract. |
| [`docs/项目说明/26_rules_handbook.md`](<项目说明/26_rules_handbook.md>) | `project-manual` | `normative_input` | `governed` | Human-readable canonical-rule interpretation and source-of-authority guide. |
| [`docs/项目说明/30_research_charter.md`](<项目说明/30_research_charter.md>) | `project-manual` | `normative_input` | `governed` | Owner-approved research-direction and line-opening charter; its dated final section is the sole writable source for current research bets and changes only at decision points. |
| [`docs/项目说明/REASONING_METHOD.md`](<项目说明/REASONING_METHOD.md>) | `project-manual` | `normative_input` | `governed` | Reusable mathematical reasoning and separation-method design principles. |
| [`specs/01_problem_statement.md`](<../specs/01_problem_statement.md>) | `specifications` | `normative_input` | `governed` | Normative problem statement, objective and certified/exploratory proposition boundary. |
| [`specs/02_global_notation_and_units.md`](<../specs/02_global_notation_and_units.md>) | `specifications` | `normative_input` | `governed` | Normative global notation, coordinates, units and indexing conventions. |
| [`specs/03_rule_canonicalization.md`](<../specs/03_rule_canonicalization.md>) | `specifications` | `normative_input` | `governed` | Normative canonical-rule ingestion, normalization and conflict handling contract. |
| [`specs/04_recipe_and_demand_expansion.md`](<../specs/04_recipe_and_demand_expansion.md>) | `specifications` | `normative_input` | `governed` | Normative recipe graph and demand-expansion contract. |
| [`specs/05_facility_instance_definition.md`](<../specs/05_facility_instance_definition.md>) | `specifications` | `normative_input` | `governed` | Normative facility-template and instance-construction contract. |
| [`specs/06_candidate_placement_enumeration.md`](<../specs/06_candidate_placement_enumeration.md>) | `specifications` | `normative_input` | `governed` | Normative candidate-placement enumeration, sound domain reduction and artifact schema contract. |
| [`specs/07_master_placement_model.md`](<../specs/07_master_placement_model.md>) | `specifications` | `normative_input` | `governed` | Normative master placement variables, constraints and objective contract. |
| [`specs/08_topological_flow_subproblem.md`](<../specs/08_topological_flow_subproblem.md>) | `specifications` | `normative_input` | `governed` | Normative topological flow diagnostic subproblem and interpretation boundary. |
| [`specs/09_exact_grid_routing_subproblem.md`](<../specs/09_exact_grid_routing_subproblem.md>) | `specifications` | `normative_input` | `governed` | Normative exact grid-routing subproblem and feasibility contract. |
| [`specs/10_benders_decomposition_and_cut_design.md`](<../specs/10_benders_decomposition_and_cut_design.md>) | `specifications` | `normative_input` | `governed` | Normative decomposition, cut validity and lifecycle design contract. |
| [`specs/11_pipeline_orchestration.md`](<../specs/11_pipeline_orchestration.md>) | `specifications` | `normative_input` | `governed` | Normative pipeline orchestration and cross-stage obligation contract. |
| [`specs/12_output_blueprint_schema.md`](<../specs/12_output_blueprint_schema.md>) | `specifications` | `normative_input` | `governed` | Normative output blueprint schema and serialization boundary. |
| [`specs/13_ecosystem_borrowing_and_compatibility_plan.md`](<../specs/13_ecosystem_borrowing_and_compatibility_plan.md>) | `specifications` | `normative_input` | `governed` | Normative borrowing and compatibility boundary for external ecosystems. |
| [`specs/14_normalized_catalog_contract.md`](<../specs/14_normalized_catalog_contract.md>) | `specifications` | `normative_input` | `governed` | Normative normalized catalog schema and identity contract. |
| [`specs/15_target_export_and_compatibility_manifest.md`](<../specs/15_target_export_and_compatibility_manifest.md>) | `specifications` | `normative_input` | `governed` | Normative target-export manifest and compatibility declaration contract. |
| [`specs/16_industrial_planner_export_contract.md`](<../specs/16_industrial_planner_export_contract.md>) | `specifications` | `normative_input` | `governed` | Normative IndustrialPlanner export contract and non-authoritative adapter boundary. |
| [`specs/17_endfield_calc_ingest_contract.md`](<../specs/17_endfield_calc_ingest_contract.md>) | `specifications` | `normative_input` | `governed` | Normative Endfield calculator ingest and normalization contract. |
| [`specs/18_preprocess_context_contract.md`](<../specs/18_preprocess_context_contract.md>) | `specifications` | `normative_input` | `governed` | Normative preprocess-context identity and reproducibility contract. |
| [`specs/19_phase3_frozen_compatible_preprocess_regeneration.md`](<../specs/19_phase3_frozen_compatible_preprocess_regeneration.md>) | `specifications` | `normative_input` | `governed` | Normative frozen-compatible preprocess regeneration and equivalence contract. |
| [`specs/20_canonical_rules_consolidation.md`](<../specs/20_canonical_rules_consolidation.md>) | `specifications` | `normative_input` | `governed` | Normative canonical-rule consolidation, provenance and conflict-resolution contract. |
| [`specs/21_frontier_probe_and_campaign_telemetry.md`](<../specs/21_frontier_probe_and_campaign_telemetry.md>) | `specifications` | `normative_input` | `governed` | Normative frontier-probe, campaign telemetry and interpretation contract. |
| [`specs/22_industrial_planner_precision_export_and_validator_spec.md`](<../specs/22_industrial_planner_precision_export_and_validator_spec.md>) | `specifications` | `normative_input` | `governed` | Normative precision export and validator contract for IndustrialPlanner derivatives. |
| [`specs/23_industrial_planner_outer_base_planning_representation.md`](<../specs/23_industrial_planner_outer_base_planning_representation.md>) | `specifications` | `normative_input` | `governed` | Normative outer-base planning representation and adapter boundary. |

## 活跃说明与操作入口

| 文档 | Section | Authority | Mutation | 唯一职责 |
|---|---|---|---|---|
| [`.artifacts/README.md`](<../.artifacts/README.md>) | `research-archive` | `current_guidance` | `direct` | Current boundary, portability and retention guidance for local evidence roots. |
| [`BORROWED_COMPONENTS.md`](<../BORROWED_COMPONENTS.md>) | `repository-navigation`, `compatibility-adapters` | `current_guidance` | `direct` | External component borrowing ledger and compatibility boundary; it records provenance without granting certification authority. |
| [`NAV_MAP.md`](<../NAV_MAP.md>) | `repository-navigation`, `implementation-navigation` | `current_guidance` | `direct` | Stable map of active code, data, script and adapter entrypoints; it never carries current project state. |
| [`README.md`](<../README.md>) | `repository-navigation` | `current_guidance` | `direct` | 稳定仓库前门，只链接当前状态、知识目录、权威边界和开发入口。 |
| [`data/knowledge/README.md`](<../data/knowledge/README.md>) | `knowledge` | `current_guidance` | `governed` | Operating guide for the structured knowledge layer. |
| [`docs/AGENT_OPERATIONS.md`](<AGENT_OPERATIONS.md>) | `operations` | `current_guidance` | `direct` | 按需加载的详细 agent 运行、测试、冻结、发布和故障处理手册。 |
| [`docs/CERTIFICATION.md`](<CERTIFICATION.md>) | `certification` | `current_guidance` | `direct` | Bounded navigation from certification questions to the owner authority, phase-gate contract, current projection and certside semantics. |
| [`docs/OPERATIONS.md`](<OPERATIONS.md>) | `operations` | `current_guidance` | `direct` | Bounded local entrypoint for campaign, parallelism, scripts, agent operations and failure handling. |
| [`docs/README.md`](<README.md>) | `repository-navigation` | `current_guidance` | `direct` | 文档层稳定前门；按问题路由到唯一当前状态、知识投影、职责索引和框架说明。 |
| [`docs/START_HERE.md`](<START_HERE.md>) | `repository-navigation` | `current_guidance` | `direct` | Stable task-oriented navigation that avoids volatile values. |
| [`docs/compatibility_matrix.md`](<compatibility_matrix.md>) | `compatibility-adapters` | `current_guidance` | `direct` | Current compatibility and adapter boundary; target exports never become certified proof sinks. |
| [`docs/env_variable_index.md`](<env_variable_index.md>) | `operations` | `explanatory` | `direct` | Stable index of runtime environment variables, precedence and validation boundaries. |
| [`docs/exact_campaign_operations.md`](<exact_campaign_operations.md>) | `operations` | `explanatory` | `direct` | Stable operator procedure for campaign inspection, resume, supervisor seal and canonical publication boundaries. |
| [`docs/frontier_probe_strategy.md`](<frontier_probe_strategy.md>) | `operations` | `explanatory` | `direct` | Stable strategy guide for frontier probing, fallback interpretation and evidence boundaries. |
| [`docs/history/README.md`](<history/README.md>) | `history-archive` | `current_guidance` | `direct` | Current navigation across all immutable historical snapshot families. |
| [`docs/history/convergence/README.md`](<history/convergence/README.md>) | `history-archive` | `current_guidance` | `direct` | Current navigation for Phase 3 responsibility-convergence source snapshots. |
| [`docs/history/deliveries/README.md`](<history/deliveries/README.md>) | `history-archive` | `current_guidance` | `direct` | Current navigation for frozen adapter and delivery documentation. |
| [`docs/history/formal/README.md`](<history/formal/README.md>) | `history-archive` | `current_guidance` | `direct` | Current navigation for retired formal-verification explanatory snapshots. |
| [`docs/history/navigation/README.md`](<history/navigation/README.md>) | `history-archive` | `current_guidance` | `direct` | Current navigation for retired indexes, maps and knowledge-tree surfaces. |
| [`docs/history/status/README.md`](<history/status/README.md>) | `history-archive` | `current_guidance` | `direct` | Current navigation for retired status, roadmap and project-state snapshots. |
| [`docs/history/subjects/README.md`](<history/subjects/README.md>) | `history-archive` | `current_guidance` | `direct` | Current navigation for pre-knowledge-spine subject projections. |
| [`docs/parallel_configuration.md`](<parallel_configuration.md>) | `operations` | `explanatory` | `direct` | Stable method for selecting and validating process and solver-worker resource settings. |
| [`docs/research/README.md`](<research/README.md>) | `research-archive` | `current_guidance` | `direct` | Current lifecycle and navigation guide for the research archive. |
| [`docs/subjects/README.md`](<subjects/README.md>) | `topic-guides` | `explanatory` | `direct` | Bounded entrypoint for stable thematic reading aids. |
| [`docs/subjects/authoritative_numbers.md`](<subjects/authoritative_numbers.md>) | `topic-guides` | `explanatory` | `direct` | Guide for locating and citing machine-authoritative numeric values without copying them. |
| [`docs/subjects/certification_taxonomy.md`](<subjects/certification_taxonomy.md>) | `topic-guides` | `explanatory` | `direct` | Concept guide separating verification, acceptance, sealing and publication. |
| [`docs/subjects/certified_exact_contract.md`](<subjects/certified_exact_contract.md>) | `topic-guides` | `explanatory` | `direct` | Concept guide for certified-exact scope, exclusions and authority boundaries. |
| [`docs/项目说明/02_mathematical_foundations.md`](<项目说明/02_mathematical_foundations.md>) | `project-manual` | `explanatory` | `direct` | Mathematical objects, notation and proof obligations used by the project. |
| [`docs/项目说明/04_design_invariants.md`](<项目说明/04_design_invariants.md>) | `project-manual` | `explanatory` | `direct` | Cross-layer design invariants that implementation and evidence must preserve. |
| [`docs/项目说明/11_dependency_graph.md`](<项目说明/11_dependency_graph.md>) | `project-manual` | `explanatory` | `direct` | Dependency graph between authorities, models, solvers, evidence and publication surfaces. |
| [`docs/项目说明/14_risk_rollout.md`](<项目说明/14_risk_rollout.md>) | `project-manual` | `explanatory` | `direct` | Risk classification, rollout order and rollback evidence for current engineering work. |
| [`docs/项目说明/15_workflow_testing.md`](<项目说明/15_workflow_testing.md>) | `project-manual` | `explanatory` | `direct` | Stable testing-layer, fixture and evidence-interpretation protocol without current receipts. |
| [`docs/项目说明/16_workflow_review.md`](<项目说明/16_workflow_review.md>) | `project-manual` | `explanatory` | `direct` | Review roles, adversarial checks and acceptance boundaries for project changes. |
| [`docs/项目说明/17_workflow_telemetry.md`](<项目说明/17_workflow_telemetry.md>) | `project-manual` | `explanatory` | `direct` | Telemetry schema, interpretation limits and non-authorizing observability contract. |
| [`docs/项目说明/18_workflow_env_config.md`](<项目说明/18_workflow_env_config.md>) | `project-manual` | `explanatory` | `direct` | Environment configuration ownership, precedence and reproducibility discipline. |
| [`docs/项目说明/19_implementation_rhythm.md`](<项目说明/19_implementation_rhythm.md>) | `project-manual` | `explanatory` | `direct` | Iteration rhythm, handoff discipline and phase-boundary maintenance protocol. |
| [`docs/项目说明/28_pitfalls_and_sop.md`](<项目说明/28_pitfalls_and_sop.md>) | `project-manual` | `explanatory` | `direct` | Operational pitfalls, fail-closed recovery patterns and recurring SOPs. |
| [`docs/项目说明/29_solving_methodology_skill.md`](<项目说明/29_solving_methodology_skill.md>) | `project-manual` | `explanatory` | `direct` | Project-level solving-methodology skill source for knowledge-computation decomposition in scientific, mathematical and solver work; it summarizes and routes methodology without granting owner authority. |
| [`docs/项目说明/README.md`](<项目说明/README.md>) | `project-manual` | `current_guidance` | `direct` | Bounded project-manual front door for current guides, normative contracts, future work and history. |
| [`docs/项目说明/ROADMAP.md`](<项目说明/ROADMAP.md>) | `project-manual` | `current_guidance` | `direct` | Future-only roadmap with dependencies and exit evidence, excluding current-state copies. |
| [`formal/README.md`](<../formal/README.md>) | `formal-verification` | `current_guidance` | `governed` | Bounded local entrypoint for Lean replay, statement scope, axiom audit and certification boundaries. |
| [`rules/derived/README.md`](<../rules/derived/README.md>) | `specifications` | `current_guidance` | `governed` | Non-frozen derived rule registry: schema, UNREVIEWED-state entries and packaging declaration; never canonical authority, never certification evidence. |
| [`scripts/README.md`](<../scripts/README.md>) | `operations` | `current_guidance` | `direct` | Stable operator map for active, governance, packaging, preprocess and historical script roles. |
| [`scripts/pumpkin_poc/README.md`](<../scripts/pumpkin_poc/README.md>) | `operations` | `current_guidance` | `direct` | Bounded operator and reproduction guide for the Pumpkin proof-of-concept scripts. |
| [`specs/README.md`](<../specs/README.md>) | `specifications` | `current_guidance` | `governed` | Bounded local front door for numbered specifications and ecosystem-note boundaries. |
| [`specs/ecosystem_notes/README.md`](<../specs/ecosystem_notes/README.md>) | `specifications`, `compatibility-adapters` | `current_guidance` | `governed` | Current local entrypoint for frozen, non-authoritative ecosystem research notes. |
| [`src/adapters/README.md`](<../src/adapters/README.md>) | `implementation-navigation`, `compatibility-adapters` | `current_guidance` | `direct` | Module-local implementation guidance. |

## 治理控制面

| 文档 | Section | Authority | Mutation | 唯一职责 |
|---|---|---|---|---|
| [`data/repository_governance/README.md`](<../data/repository_governance/README.md>) | `repository-governance` | `governance_control` | `governed` | Fail-closed repository governance registries and schemas. |

## 文档框架核心

| 文档 | Section | Authority | Mutation | 唯一职责 |
|---|---|---|---|---|
| [`.docsystem/RECOVERY.md`](<../.docsystem/RECOVERY.md>) | `documentation-framework` | `framework_definition` | `governed` | Fail-closed bootstrap recovery procedure for manifest or resolver failure. |
| [`docs/governance/document-system/ADR/001-inherited-policy-and-progressive-disclosure.md`](<governance/document-system/ADR/001-inherited-policy-and-progressive-disclosure.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/002-self-governing-framework-core.md`](<governance/document-system/ADR/002-self-governing-framework-core.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/003-legacy-doc-classes-as-generated-projection.md`](<governance/document-system/ADR/003-legacy-doc-classes-as-generated-projection.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/004-backfill-review-and-reasoning-projection.md`](<governance/document-system/ADR/004-backfill-review-and-reasoning-projection.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/005-derivation-graph-and-mathematical-families.md`](<governance/document-system/ADR/005-derivation-graph-and-mathematical-families.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/006-selection-separation-and-consumption-profile.md`](<governance/document-system/ADR/006-selection-separation-and-consumption-profile.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/007-validity-events-and-explicit-supersession.md`](<governance/document-system/ADR/007-validity-events-and-explicit-supersession.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/008-semantic-review-and-inventory-triage.md`](<governance/document-system/ADR/008-semantic-review-and-inventory-triage.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/009-explicit-current-guidance-surface.md`](<governance/document-system/ADR/009-explicit-current-guidance-surface.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/010-bounded-entrypoints-and-on-demand-agent-guide.md`](<governance/document-system/ADR/010-bounded-entrypoints-and-on-demand-agent-guide.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/011-explicit-sections-and-retired-local-indexes.md`](<governance/document-system/ADR/011-explicit-sections-and-retired-local-indexes.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/012-current-graph-convergence-audit.md`](<governance/document-system/ADR/012-current-graph-convergence-audit.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/013-non-mutating-governance-gate.md`](<governance/document-system/ADR/013-non-mutating-governance-gate.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/014-event-driven-document-intake.md`](<governance/document-system/ADR/014-event-driven-document-intake.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/015-periodic-semantic-maintenance-audit.md`](<governance/document-system/ADR/015-periodic-semantic-maintenance-audit.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/016-real-repository-topology-and-workspace-overlays.md`](<governance/document-system/ADR/016-real-repository-topology-and-workspace-overlays.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md`](<governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/018-nondestructive-real-repository-landing.md`](<governance/document-system/ADR/018-nondestructive-real-repository-landing.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/019-bounded-governance-concurrency-and-slow-test-evidence.md`](<governance/document-system/ADR/019-bounded-governance-concurrency-and-slow-test-evidence.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/020-steady-state-transition-and-maintenance-handoff.md`](<governance/document-system/ADR/020-steady-state-transition-and-maintenance-handoff.md>) | `documentation-framework` | `framework_definition` | `immutable` | Accepted framework design decisions. New decisions use a new ADR; accepted ADR text is not rewritten. |
| [`docs/governance/document-system/ADR/README.md`](<governance/document-system/ADR/README.md>) | `documentation-framework` | `framework_definition` | `governed` | Current index of framework ADRs. |
| [`docs/governance/document-system/ARCHITECTURE.md`](<governance/document-system/ARCHITECTURE.md>) | `documentation-framework` | `framework_definition` | `governed` | Current conceptual architecture, invariants and component relationships of the self-describing document system. |
| [`docs/governance/document-system/MAINTAINING.md`](<governance/document-system/MAINTAINING.md>) | `documentation-framework` | `framework_definition` | `governed` | Safe change, migration, generation, testing and recovery procedure for the document framework. |
| [`docs/governance/document-system/REAL_REPOSITORY_LANDING.md`](<governance/document-system/REAL_REPOSITORY_LANDING.md>) | `documentation-framework` | `framework_definition` | `governed` | Current architecture, safe evolution protocol and design-decision history for the self-describing document system. |
| [`docs/governance/document-system/STEADY_STATE.md`](<governance/document-system/STEADY_STATE.md>) | `documentation-framework` | `framework_definition` | `governed` | Durable steady-state maintenance contract, framework reopening criteria and fail-closed handoff after the staged documentation rebuild. |

当前机器状态见 [CURRENT](CURRENT.md)，按分区进入见 [SECTION_INDEX](SECTION_INDEX.md)，开放问题见 [OPEN_QUESTIONS](OPEN_QUESTIONS.md)，按任务进入见 [START_HERE](START_HERE.md)，历史材料见 [CATALOG](CATALOG.md) 与 [history](history/README.md)。
