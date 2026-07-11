# `docs/项目说明/` 项目书

本目录有 25 个专题文档，加本 README，共 26 个 Markdown 文件。它同时包含当前说明、数学背景、
历史复盘和未来计划，不能把每个文件都当成同等级的现状 authority。

## 权威顺序

1. `PROJECT_LOCK.md`：认证命题、Accepted Invariants、禁止变更与发布边界。
2. `data/review_gates/phase_1_2_spike_close.json`：owner phase gate 的机器状态。
3. `docs/项目说明/06_current_status.md`：当前工作树的人类可读状态。
4. `docs/项目说明/soundness_gap_roadmap.md`：已实现、部分实现、未实现和 scope-exclusion 矩阵。
5. 其余 phase plan / historical review / research 文档：设计或历史上下文，不能覆盖上述现状。

截至 2026-07-11，P1.2 已由 owner 显式 `owner_manual_decision` 关闭
（`closed_manual_owner_decision`，`p1_3b_entry_allowed=true`），P1.3 已开放并分批实施。当前工作树已落
producer/supervisor split、fixed-witness、OPEN-GATE、whole-layout independent reverify、central
publisher，以及 cut direct attach 的 F1/F5/F6/F7 翻译；Stage B B0/B1（contract shell、
`FrozenArtifactBundle`、`ValidatedStateSnapshot`、digest v1）已落地。direct attach 仍由
`EXACT_CUT_FRAMEWORK_ATTACH` 门控并在 certified unsafe map 中禁用；B2-B5（B0/B1/B1.5 已落地）、PIC C/D/E 与 B6 owner
promotion 尚未完成。#9a 为部署时点任务，防蓄意内鬼硬化桶（#8 深化/#2/#3/#5-F/#9b/#9c/
Option B）另列发布时点，非 P1.2 blocker。

## 推荐阅读

| 需求 | 文档 |
|---|---|
| 现在能宣称什么 | [06_current_status.md](06_current_status.md) |
| 认证命题与边界 | [01_overview.md](01_overview.md) + 根目录 `PROJECT_LOCK.md` |
| gap 当前状态 | [soundness_gap_roadmap.md](soundness_gap_roadmap.md) |
| supervisor 实现 | [p1_2_supervisor_detailed_design.md](p1_2_supervisor_detailed_design.md) |
| 数学/cut 背景 | [02_mathematical_foundations.md](02_mathematical_foundations.md) |
| 历史死路 | [03_paradigm_death_baseline.md](03_paradigm_death_baseline.md) + [07_historical_review.md](07_historical_review.md) |
| 后续 P1.3 | [09_phase_1_3_plan.md](09_phase_1_3_plan.md) |
| 测试与审查 | [12_go_criteria.md](12_go_criteria.md), [15_workflow_testing.md](15_workflow_testing.md), [16_workflow_review.md](16_workflow_review.md) |

## 文件分类

当前说明：01、04、05、06、11、12、14、15、16、17、18、21、soundness roadmap、supervisor detailed design。

历史/计划：02 的部分 cut-framework 状态段、03、07、08、09、10、13、19、20，以及
`p1_2_supervisor_redesign_draft.md`。这些文件保留当时决策和后续方向；其中旧的 `P1.3B` 人类命名应读为
当前 P1.3，`p1_3b_*` 只在机器字段中保留兼容。

## 文档维护

`docs/subjects/` 是人工维护的导航摘要。仓库不存在 `scripts/sync_doc_subjects.py`、
`scripts/check_doc_tree_completeness.py` 或 `cc_context/` projection registry，preflight 也不检查这些旧工具。
残留 `DOC-SUBJECT` marker 只表示来源/历史，不表示自动生成或禁止手改。

更新当前行为时，至少同步：`PROJECT_LOCK.md`、06、roadmap、相关 spec、代码 docstring/comment、proof
obligation/allowlist 理由和 cc_memory active 节点/边。历史日志保留当时事实，但入口必须标明其时间边界。
