# docs/项目说明/ — 终末地 IndustrialPlanner 70×70 求解器项目说明

终末地 (Arknights: Endfield) IndustrialPlanner 70×70 grid certified exact solver 的项目说明文档. 21 个 sub-doc + 本 README. 不是计划书 / 不是 spec, 是**项目本身的说明** — 给 implementer / reviewer / maintainer / 用户的 SoT.

## 文档地图

| Sub-doc | 主题 | line | 来源 |
|---|---|---|---|
| [01_overview.md](01_overview.md) | 项目概览 (战略 + 数学问题陈述 + paradigm 选择) | 158 | math §1 + plan §1 |
| [02_mathematical_foundations.md](02_mathematical_foundations.md) | 核心数学原理 (9 family + sound deduction + scope/replay/multiset/adversarial) | 495 | math §2 + §3 |
| [03_paradigm_death_baseline.md](03_paradigm_death_baseline.md) | 已 verify 不通的 paradigm (27 lever 死路按数学根据分类) | 210 | math §4 + plan §4 |
| [04_design_invariants.md](04_design_invariants.md) | 设计哲学 + 核心 invariants (PROJECT_LOCK §3A) | 103 | plan §2 + §18 |
| [05_open_questions.md](05_open_questions.md) | 待定 mathematical questions (33 + 6 Q) | 544 | math §5 + plan §17 |
| [06_current_status.md](06_current_status.md) | 现状细则 (commit `c8fb7ef` 起算) | 35 | plan §6 |
| [07_historical_review.md](07_historical_review.md) | 历史回顾 (Phase 0 → Step O) | 116 | plan §5 |
| [08_phase_1_2_plan.md](08_phase_1_2_plan.md) | Phase 1.2 plan (P1.11 入门 + 5 family) | 134 | plan §10 + §11 |
| [09_phase_1_3_plan.md](09_phase_1_3_plan.md) | Phase 1.3 plan (CP-SAT propagator 集成) | 46 | plan §12 |
| [10_phase_1_5_plan.md](10_phase_1_5_plan.md) | Phase 1.5+ plan (production integration) | 63 | plan §13 |
| [11_dependency_graph.md](11_dependency_graph.md) | 依赖图 (family / step / phase) | 83 | plan §9 |
| [12_go_criteria.md](12_go_criteria.md) | GO 标准 / 验收准则 | 76 | plan §8 |
| [13_schedule_estimate.md](13_schedule_estimate.md) | 排期估算 (Claude pace) | 17 | plan §16 |
| [14_risk_rollout.md](14_risk_rollout.md) | 风险评估 + mitigation + rollout policy | 79 | plan §14 |
| [15_workflow_testing.md](15_workflow_testing.md) | 测试 strategy + fixture 清单 | 94 | plan §21 |
| [16_workflow_review.md](16_workflow_review.md) | 审查策略 (Gemini + GPT pro + 数学验证 workflow) | 199 | plan §22 + math §6 |
| [17_workflow_telemetry.md](17_workflow_telemetry.md) | Observability / telemetry plan | 85 | plan §20 |
| [18_workflow_env_config.md](18_workflow_env_config.md) | 环境变量 / 配置清单 | 51 | plan §19 |
| [19_implementation_rhythm.md](19_implementation_rhythm.md) | 实施 rhythm (Phase 1.1 经验) | 16 | plan §15 |
| [20_skip_directions.md](20_skip_directions.md) | 默认 skip 的方向 (历史死路 baseline) | 15 | plan §7 |
| [21_glossary.md](21_glossary.md) | Glossary 术语表 + refs | 147 | plan Appendix A + math A |

合计 ~2766 line (~21 个 standalone doc), 跟原单 plan 1449 line + 单 math 1580 line 大致对应 (受众段 + spec 关系 + 文档维护合进本 README).

## 受众分流

不同身份 focus 不同 doc, 不要求一口气全读完.

**implementer (下个 session 接手的 Claude / 人)**
- 入口: [06](06_current_status.md) → [08](08_phase_1_2_plan.md) → [11](11_dependency_graph.md)
- 实施前必读: [04](04_design_invariants.md) + [02](02_mathematical_foundations.md) 那 family 那段 + [18](18_workflow_env_config.md)
- 每段做完前 verify: [12](12_go_criteria.md) + [15](15_workflow_testing.md) + [16](16_workflow_review.md)
- 出错回头: [14](14_risk_rollout.md)

**reviewer (GPT pro batch audit / Gemini per-commit cross-check / 数学 consultant)**
- 主战场: [02](02_mathematical_foundations.md) 各 family 数学根据 + [05](05_open_questions.md) open Q
- context: [01](01_overview.md) + [03](03_paradigm_death_baseline.md) (为啥不重蹈 27 lever)
- 我们对 reviewer 的期待: [16](16_workflow_review.md) audit verdict criteria
- 不必读: commit-level 实施细则 ([08]-[10])

**未来 maintainer (Phase 1.2/1.3/1.5 接手, 数周-数月后)**
- context 恢复: [01](01_overview.md) → [03](03_paradigm_death_baseline.md) → [07](07_historical_review.md)
- 改某 family 牵动哪些: [11](11_dependency_graph.md) + [18](18_workflow_env_config.md)
- 边界: [04](04_design_invariants.md) PROJECT_LOCK §3A
- 术语 anchor: [21](21_glossary.md)

**用户 (审 progress + 数学严肃性)**
- 现在到哪了: [06](06_current_status.md) + [17](17_workflow_telemetry.md)
- 还多久: [13](13_schedule_estimate.md)
- 待定决策点: [05](05_open_questions.md)
- 出错怎么 revert: [14](14_risk_rollout.md) rollout policy

## 跟现有 spec / archive 关系

`docs/项目说明/` 是项目说明 SoT. `docs/research/p3_b_design_v2_20260521/` 是 B Design v2 framework spec SoT + audit archive, 各 doc 不重复:

| Doc 系列 | 职责 | 位置 |
|---|---|---|
| **项目说明 (本 dir)** | 已确定 paradigm + open Q + 实施 plan + workflow + 术语 | `docs/项目说明/01-21*.md` |
| **B Design v2 framework spec** | cut object schema + lifecycle 9 step + 各 family validator contract + state machine + state invariants | `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md` / `state_machine_v2.md` / `schema_update_v3.md` / `cut_family_specs/0X.md` |
| **paradigm 死路 timeline** | 27 lever chronological + 死因 axis 分类 + 共同 root cause + unsolved issue | `docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md` |
| **Red fixtures** | known-infeasibility 反例 + cut object hardcode + evaluate 期望 | `docs/research/p3_b_design_v2_20260521/red_fixtures/F1-F5*.md` |
| **Phase 闭环 doc** | Phase 0 close / Phase 1 旧 plan | `docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md` / `PHASE_1_PLAN.md` (历史 archive) |
| **Audit archive** | Gemini per-commit cross-check + GPT pro batch audit 全 round response | `docs/research/p3_b_design_v2_20260521/cross_check/` + `external_review/` |
| **PROJECT_LOCK** | 数学/工程 invariant lock | `PROJECT_LOCK.md` §3A (项目根) |
| **CLAUDE.md** | 项目 instructions + maintenance runbook + Active scope + Forbidden changes | `CLAUDE.md` (项目根) |

跨 dir cross-ref 用 relative path. `项目说明/` 的 sub-doc 经常 cite `docs/research/p3_b_design_v2_20260521/` 内 spec, e.g. "详 cut_lifecycle_v2 §3" 指那个 dir 的 spec.

## 文档维护

### 更新 trigger
- 新 family propose (F10+) → [02](02_mathematical_foundations.md) + [05](05_open_questions.md) 重审
- 已 open Q 决策 → 从 [05](05_open_questions.md) 移出, 进 [02](02_mathematical_foundations.md) 或 [03](03_paradigm_death_baseline.md)
- 新 paradigm 死路 → [03](03_paradigm_death_baseline.md) 加 + [05](05_open_questions.md) 重审 completeness
- spec / src / data schema 大改 → [02](02_mathematical_foundations.md) + [04](04_design_invariants.md) 同步
- PROJECT_LOCK §3A 改 → [04](04_design_invariants.md) + [05](05_open_questions.md) frozen Q 重审
- 实施完一阶段 (Phase 1.2 / 1.3 / 1.5+) → [06](06_current_status.md) + [07](07_historical_review.md) 同步; phase plan ([08]/[09]/[10]) 转 history

### review 政策
本 dir 每大节点 (Phase 1.2 / 1.3 / 1.5+ boundary) audit:
- Gemini per-commit 改本 dir 时跑 ([16](16_workflow_review.md) workflow §22.1)
- GPT pro batch 整 phase 完时 review ([16](16_workflow_review.md) workflow §22.2)
- 实施 implementer 进 Phase 时必读最新版

### changelog

| Date | 版本 | 改动 |
|---|---|---|
| 2026-05-23 | v1.0 | 初版 21 sub-doc, 从 `docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md` (1449 line) + `MATHEMATICAL_FOUNDATIONS.md` (1580 line) 拆分重组到项目顶层 `docs/项目说明/` |
| 2026-05-23 | v1.1 | Phase 1.1 exit hardening delivery 落地 — 178 cuts pass / mypy strict pass / radon A 无 D, P1.2A 入门 ✅ done. 同时 merge Gemini math review meta-audit 修正 (F9 area-only / F8 mode 锁 geometric / CP-SAT no AddLazyConstraint / dark matter telemetry / 11 red fixture matrix / Phase 1.2 P0 acceptance checklist). 6 sub-doc update: 06 status / 07 history / 02 math (F9 area-only + morphology safe/unsafe) / 04 invariants / 05 open Q (Q10 verdict) / 08 phase 1.2 (P1.2A/B 命名 + 5 family 详) / 09 phase 1.3 (P1.3A spike) / 12 GO (P0 acceptance) / 15 testing (11 red fixture) / 17 telemetry (µs vs ms 单位 + dark matter) |
| 2026-05-24 | v1.2 | Phase 1.1 复查补强 — strict base64/bitset/Cut schema/F1-F4 bool numeric schema fail-closed，新增 7 个 regression，cuts pytest 188 pass (`python` + `python -O`)，ruff/mypy/vulture/bandit/radon 全 PASS，exit_criteria 0 FAIL。更新 06/12/15 与顶层 README，使 1.1 gate 口径对齐。 |

## cite 约定

跨 sub-doc cite 用 markdown link `[NN](NN_name.md)`. 跨 dir cite 用 relative path.

详 cite 约定 (`[cite spec X §N]` / `[cite lifecycle §N]` / `[cite plan §N]` / `[cite death-timeline LN]` / `[cite lock §3A]` / `[[memory-name]]`) 在 [01](01_overview.md) 开头.
