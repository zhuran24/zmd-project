---
name: docs-project-spec-folder
description: 2026-05-23 plan + math 拆 docs/项目说明/ 21 sub-doc, 项目顶层. README 索引 + 受众分流. 旧 plan + math 留 redirect stub.
metadata:
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-23 用户原话: "不应该叫'计划书'而是叫'项目说明文档', 也不应该写成一个, 应该写成文件夹的形式". 完整 reorganization:

## 位置 + 结构

`docs/项目说明/` (项目顶层, 跟 docs/research/ 平级)

- `README.md` — 总索引 + 受众分流 + 文档地图
- `01_overview.md` (158 line) — 战略 + 数学问题陈述 + paradigm 选择
- `02_mathematical_foundations.md` (495 line) — 9 family + sound deduction + scope/replay/multiset/adversarial
- `03_paradigm_death_baseline.md` (210 line) — 27 lever 死路按数学根据分类
- `04_design_invariants.md` (103 line) — 设计哲学 + PROJECT_LOCK §3A
- `05_open_questions.md` (544 line) — 33 + 6 Q 合并
- `06_current_status.md` (35 line)
- `07_historical_review.md` (116 line)
- `08_phase_1_2_plan.md` (134 line)
- `09_phase_1_3_plan.md` (46 line)
- `10_phase_1_5_plan.md` (63 line)
- `11_dependency_graph.md` (83 line)
- `12_go_criteria.md` (76 line)
- `13_schedule_estimate.md` (17 line)
- `14_risk_rollout.md` (79 line)
- `15_workflow_testing.md` (94 line)
- `16_workflow_review.md` (199 line)
- `17_workflow_telemetry.md` (85 line)
- `18_workflow_env_config.md` (51 line)
- `19_implementation_rhythm.md` (16 line)
- `20_skip_directions.md` (15 line)
- `21_glossary.md` (147 line)

合计 ~2766 line, 跟原 plan 1449 + math 1580 ≈ 3029 line 大致对应.

## 来源

- 原 `PHASE_POST_1_1_REFACTOR_PLAN.md` 1449 line + `MATHEMATICAL_FOUNDATIONS.md` 1580 line 重合 ~30-40% (数学原理 + 死路 paradigm + 审查 workflow + 术语表)
- 用户两条 feedback:
  1. "应叫项目说明文档不应叫计划书" — naming 改
  2. "应写成文件夹的形式" — 拆多 sub-doc

## 现有 spec 跟新 dir 关系

留 `docs/research/p3_b_design_v2_20260521/` 原位 (B Design v2 framework spec SoT + audit archive):
- `cut_lifecycle_v2.md` / `state_machine_v2.md` / `schema_update_v3.md`
- `cut_family_specs/01-09_*.md` (9 family detailed spec)
- `red_fixtures/F1-F5*.md` (5 known-infeasibility 反例)
- `paradigm_death_timeline.md` (27 lever chronological)
- `PHASE_0_CLOSE.md` / `PHASE_1_PLAN.md` (历史 archive)
- `cross_check/` + `external_review/` (Gemini + GPT pro audit archive)
- `poc/` (PoC artifacts)

`项目说明/` sub-doc cite spec 用 relative path `docs/research/p3_b_design_v2_20260521/<file>`.

## 旧 file 处理

`docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md` + `MATHEMATICAL_FOUNDATIONS.md` 改成 redirect stub:
- 顶部 SUPERSEDED status
- 内容 mapping 表 (原 section → 新 sub-doc)
- 不删 file 保 git 历史 + cross-ref 安全

## SoT 政策

- 项目说明 (paradigm + 数学 + plan + workflow + 术语) SoT = `docs/项目说明/`
- B Design v2 framework spec SoT = `docs/research/p3_b_design_v2_20260521/`
- invariant lock SoT = `PROJECT_LOCK.md` §3A (项目根)
- 各 SoT 不重复, cross-ref 走 relative path

## 维护

- 新 family / paradigm 死路 / open Q 决策 / spec 大改 → 同步对应 sub-doc + 跨 doc cross-ref
- 每大节点 (Phase 1.2 / 1.3 / 1.5+) audit (Gemini per-commit + GPT pro batch)
- implementer 进 Phase 时必读最新版

## Refs

- `docs/项目说明/README.md` — 入口
- gpt-pro-p11-audit-not-go(已归档) — Phase 1.1 audit 历史
- [[plan-doc-strategic-layers]] — plan doc 必含战略层 (现 superseded by 项目说明 dir 结构)
