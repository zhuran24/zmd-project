# PHASE_POST_1_1_REFACTOR_PLAN.md — SUPERSEDED

> **Status**: 2026-05-23 拆分重组到项目顶层 `docs/项目说明/`. 本 file 仅留 redirect stub, 不再 update.

## 重组目的

原 plan 1449 line 跟 `MATHEMATICAL_FOUNDATIONS.md` 1580 line 二份 doc 数学原理 + 死路 paradigm 重合 ~30-40%, 维护双倍. 用户决策: 改成项目顶层 `docs/项目说明/` 文件夹 (21 sub-doc 中等粒度), 各 sub-doc 各管一摊, 不重复.

## 新位置

`docs/项目说明/` (项目顶层) — 跟 `docs/research/` 平级.

入口: `docs/项目说明/README.md` 含总索引 + 受众分流 + 21 sub-doc 文档地图.

## 内容 mapping (本 file 原 section → 新 sub-doc)

| 原 section | 新位置 |
|---|---|
| §0 受众段 | `docs/项目说明/README.md` (合进总索引) |
| §1 战略 / 上下文 | `docs/项目说明/01_overview.md` (跟 math §1 合并) |
| §2 设计哲学 + invariants | `docs/项目说明/04_design_invariants.md` (含 §18 PROJECT_LOCK §3A) |
| §3 核心数学原理 (overview, 已 cite math) | `docs/项目说明/02_mathematical_foundations.md` (math doc 整体) |
| §4 paradigm 决策 (overview, 已 cite math) | `docs/项目说明/03_paradigm_death_baseline.md` (跟 math §4 合并) |
| §5 历史回顾 | `docs/项目说明/07_historical_review.md` |
| §6 现状细则 | `docs/项目说明/06_current_status.md` |
| §7 默认 skip 方向 | `docs/项目说明/20_skip_directions.md` |
| §8 GO 标准 | `docs/项目说明/12_go_criteria.md` |
| §9 依赖图 | `docs/项目说明/11_dependency_graph.md` |
| §10 + §11 Phase 1.2 plan | `docs/项目说明/08_phase_1_2_plan.md` |
| §12 Phase 1.3 plan | `docs/项目说明/09_phase_1_3_plan.md` |
| §13 Phase 1.5+ plan | `docs/项目说明/10_phase_1_5_plan.md` |
| §14 风险评估 + rollout | `docs/项目说明/14_risk_rollout.md` |
| §15 实施 rhythm | `docs/项目说明/19_implementation_rhythm.md` |
| §16 排期估算 | `docs/项目说明/13_schedule_estimate.md` |
| §17 Open questions | `docs/项目说明/05_open_questions.md` (跟 math §5 合并) |
| §18 PROJECT_LOCK §3A 边界 | `docs/项目说明/04_design_invariants.md` |
| §19 环境变量 / 配置 | `docs/项目说明/18_workflow_env_config.md` |
| §20 telemetry plan | `docs/项目说明/17_workflow_telemetry.md` |
| §21 测试 strategy | `docs/项目说明/15_workflow_testing.md` |
| §22 审查策略 | `docs/项目说明/16_workflow_review.md` (跟 math §6 合并) |
| Appendix A 术语表 | `docs/项目说明/21_glossary.md` (跟 math A 合并) |

## Git 历史

完整 commit 历史详 `git log -- docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md`. 关键 commit:
- `46561c2` — plan 初版 rewrite 加 6 段战略层
- `d86d473` — 加 §3 核心数学原理 13 subsection
- `af83885` — 高中 7 项 gap 补完 (§0/§14.3/§19/§20/§21/§22/Appendix A)
- `290bd32` — §3 + §4 收缩为 overview (本 file 末态)
- 本 commit — superseded by docs/项目说明/

旧 plan content 100% 进新位置, 无丢失.
