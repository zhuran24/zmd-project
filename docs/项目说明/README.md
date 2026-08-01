# `docs/项目说明/` 项目书

本目录有 29 个专题文档，加本 README，共 30 个 Markdown 文件。它同时包含当前说明、数学背景、
历史复盘和未来计划，不能把每个文件都当成同等级的现状 authority。

## 当前权威与历史入口

1. `PROJECT_LOCK.md`：认证命题、Accepted Invariants、禁止变更与发布边界。
2. `data/review_gates/phase_1_2_spike_close.json`：owner phase gate 的机器状态。
3. `docs/项目说明/06_current_status.md`：当前工作树的人类可读状态。
4. `docs/项目说明/24_repository_asset_governance.md`：代码资产分类、维护者实现索引和
   developer/evidence/replay/full 工作流的治理 authority；不授予认证或 production authority。
5. `docs/项目说明/soundness_gap_roadmap.md`：截至 2026-07-11 的 P1.2 soundness
   历史快照；仅用于追溯当时的 IMPLEMENTED/OPEN/PARTIAL 与 P1.2 scope exclusion，
   不是当前 authority。
6. 其余 phase plan / historical review / research 文档：设计或历史上下文，不能覆盖上述现状。

截至 2026-08-01，P1.2 已由 owner 显式 `owner_manual_decision` 关闭
（`closed_manual_owner_decision`，`p1_3b_entry_allowed=true`），P1.3 已开放。当前研究账本为
`U=(1188,18)`、`L=absent`：strict/SMM3 曾以 `FORMAL_AUTHORITY_INCOMPLETE` 失败、账本未动，
其后 SMM4 fresh-authority 的 `smm4-formal-a004`（07-27，one-shot 已消费不得重试）以
detached receipt 与 immutable closeout 双 `VERIFIED` 授权上界账更新。该结果 conditional on
frozen A004-admitted geometric lemmas（SMM-209），且不建立 witness、attainability、
optimality 或 production `CERTIFIED`。

cut framework 的 Stage B B0-B5b 工程面已完成。typed lowering 仅 F1/F6/F7；F5 保持
shadow-only、无 apply/lowering；F2/F3/F4/F9 保持 `LEGACY_DIAGNOSTIC`，F8 已退役。
`EXACT_CUT_FRAMEWORK_ATTACH` 仍为 unsafe/default-off，PIC-4/PIC-5 证据充分性与 B6 owner
promotion 仍未关闭。规则与 cut 演化规格仍是 test/offline-only shadow；noncert cuts A/B
只提供局部研究与机制证据。两者均不授权 family-global soundness、production `CERTIFIED`、
项目上下界、witness 或 optimality。#9a 仍是部署时点任务，防蓄意内鬼硬化桶仍属发布时点，
均不是 P1.2 blocker。

## 推荐阅读

| 需求 | 文档 |
|---|---|
| 现在能宣称什么 | [06_current_status.md](06_current_status.md) |
| 认证命题与边界 | [01_overview.md](01_overview.md) + 根目录 `PROJECT_LOCK.md` |
| P1.2 gap 历史快照（截止 2026-07-11） | [soundness_gap_roadmap.md](soundness_gap_roadmap.md) |
| supervisor 实现 | [p1_2_supervisor_detailed_design.md](p1_2_supervisor_detailed_design.md) |
| 数学/cut 背景 | [02_mathematical_foundations.md](02_mathematical_foundations.md) |
| 历史死路 | [03_paradigm_death_baseline.md](03_paradigm_death_baseline.md) + [07_historical_review.md](07_historical_review.md) |
| 项目怎么走到今天（人话编年史） | [22_project_journey_plain_language.md](22_project_journey_plain_language.md) |
| 规则与 cut 演化 shadow 协议（test-only；production deferred） | [23_rule_cut_evolution_protocol.md](23_rule_cut_evolution_protocol.md) |
| 代码资产分类、搜索、lint 与测试工作流 | [24_repository_asset_governance.md](24_repository_asset_governance.md) |
| 07-20 自治作战交接书（史料：GHOST 方法论+十天计划） | [25_autonomy_campaign_plan_20260720.md](25_autonomy_campaign_plan_20260720.md) |
| 当前研究账本与 `(1188,18)` authority 链 | [SMM4 fresh authority](../research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md) + 历史：[R4 `(1188,22)`](../research/b1_r4_1188_22_pb_20260723/README.md)、[strict closeout](../research/b1_sidewise_marked_membrane_strict_20260724/README.md) |
| noncert cuts A/B 证据边界 | [Gate 1 v4](../research/noncert_cuts_ab_trust_gate1_v4_20260724/README.md) + [AB16](../research/noncert_cuts_ab16_20260724/README.md) |
| 后续 P1.3 | [09_phase_1_3_plan.md](09_phase_1_3_plan.md) |
| 测试与审查 | [12_go_criteria.md](12_go_criteria.md), [15_workflow_testing.md](15_workflow_testing.md), [16_workflow_review.md](16_workflow_review.md) |

## 文件分类

当前说明：01、04、05、06、11、12、14、15、16、17、18、21、24、supervisor detailed design。

测试/离线 shadow 协议：23（non-authorizing；production 接线延期）。

历史/计划：02 的部分 cut-framework 状态段、03、07、08、09、10、13、19、20、
`soundness_gap_roadmap.md`（截止 2026-07-11），以及
`p1_2_supervisor_redesign_draft.md`。这些文件保留当时决策和后续方向；其中旧的 `P1.3B` 人类命名应读为
当前 P1.3，`p1_3b_*` 只在机器字段中保留兼容。

## 文档维护

`docs/subjects/` 是人工维护的导航摘要。仓库不存在 `scripts/sync_doc_subjects.py`、
`scripts/check_doc_tree_completeness.py` 或 `cc_context/` projection registry，preflight 也不检查这些旧工具。
残留 `DOC-SUBJECT` marker 只表示来源/历史，不表示自动生成或禁止手改。

更新当前行为时，至少同步：`PROJECT_LOCK.md`、06、`00_master_roadmap.md`、相关 spec、代码 docstring/comment、proof
obligation/allowlist 理由和 cc_memory active 节点/边。历史日志保留当时事实，但入口必须标明其时间边界。

新增或重分类代码资产时，还必须同步
`data/repository_governance/code_assets.json` 并运行
`python devtools/check_repository_code_assets.py check`；`.rgignore` 只允许作为 manifest 的
developer 搜索投影，不能单独承担分类或全仓安全边界。
