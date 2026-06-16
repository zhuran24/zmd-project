# Phase 0 Day 10-12 — Red Fixtures F1-F4

> **Status**: Day 10-12 起步 (2026-05-21)
> **Cross-refs**: `../state_machine_v2.md` (Dev A) + `../cut_lifecycle_v2.md` (Dev B)
> **Scope**: doc-only spec — framework code 未写, fixture 是 schema-level 反例 + 期待拦截路径

## 1. 目的

Phase 0 prep plan v3 Day 10-12 任务: 把 4 个 known infeasibility 反例**接进** state machine v2 + cut lifecycle v2 框架, 用 hardcode cut object 验:

1. 反例几何能被新 `MasterStateV2` 表达 (没 hidden assumption 漏掉)
2. 4 类新 cut family 的 schema 能 hardcode 出一条**拦截**该反例的 sound cut
3. cut object 跑 `evaluate_cut_as_multiset` (cut_lifecycle_v2 §5) 在反例 state 上返 `violate=True`

**不验**:
- Oracle 端 cut generation (Day 13-17 任务)
- Scope-aware replay (Day 13-17 任务)
- Validator 独立重算 cert (Day 13-17 任务)

Day 10-12 只验 "反例 ↔ cut 表达" 这一**接口契合**.

## 2. 4 个 Red Fixture

| ID | 反例 | 应被拦截的 cut family | 来源 |
|---|---|---|---|
| **F1** | Boundary saturation: 138 left+bottom cells 必 100% 铺满, 任何缺格的 assignment INFEASIBLE | Family 1 region_capacity + Family 3 port_exposure | v14 review boundary correction (commit 976bc10) |
| **F2** | Shape packing Hall: 长度 10 boundary 被 ghost 切成 [1,2,3,4]+[6,7,8,9,10], 总 cell 数 9 ≥ demand 9 pass region capacity, 但 length-3 interval `⌊4/3⌋+⌊5/3⌋=2 < 3` infeasible | Family 1 + Shape Hall extension (新 cut family schema, Day 13-17) | Gemini 反例 B |
| **F3** | Power no-cover ghost-conditioned: pose p 在 G1 ghost 下没任何 power_pole 候选覆盖 → INFEASIBLE | Family 1 region_capacity + Power-cover hitting-set extension (GPT power cut, Day 13-17) | GPT 反例 power_cover + L16 lazy power |
| **F4** | Ghost-scoped replay false positive: G1 ghost 学 cut `not(A=pA ∧ B=pB)`; G2 ghost 移挡后 A=pA ∧ B=pB **合法**, v14 pose-id-only replay 误剪 | Family 5 pattern_nogood + scope-aware replay HOLD | cut_lifecycle_v2 §4 反例 walk-through |

## 3. Fixture 文件结构

每 fixture 一个 `.md` 文件:

```
F<id>_<short_name>.md
├── 1. 反例几何 (cells / ghost / pose assignments) — concrete data
├── 2. MasterStateV2 表达 (按 state_machine_v2 §2 schema 填值)
├── 3. 期待结果 (sound INFEASIBLE / cut family 拦)
├── 4. Hardcode cut object (按 cut_lifecycle_v2 §3 Cut schema 填)
├── 5. evaluate_cut_as_multiset(cut, state) 调用 + 期待返 True
├── 6. Scope-aware replay 测试 (F4 专属)
└── 7. Open questions / 待 Day 13-17 解决项
```

## 4. 验收 criterion (Day 12 close-out)

- ✅ 4 fixtures markdown 完整 (反例几何 + state 填值 + hardcode cut + 期待 multiset match)
- ✅ schema-level inspect 无 hidden field: state_machine_v2 / cut_lifecycle_v2 schema 能 carry 全部反例信息 (没要某 fixture 不能填的字段)
- ✅ 4 个 fixture 在 cut family taxonomy (region_capacity / cutset / port_exposure / component_reach / pattern_nogood) 内有 owner — 不需要 Day 13-17 新 family 救
- ⚠️ 例外: F2 shape packing Hall + F3 power hitting-set 已知**需新 cut family** (Day 13-17 任务), fixture 内打 `[NEEDS_NEW_FAMILY]` 标记
- ✅ schema-mismatch 项进 §10 open questions (state_machine_v2 / cut_lifecycle_v2 cross-sync 列表)

## 5. 实施顺序

Day 10: F1 (boundary saturation) — 反例最 concrete, 拿来当 template 验 schema 表达力
Day 11: F4 (ghost-scoped replay) — scope-aware replay 反例, 验 cut_lifecycle_v2 §4 walk-through
Day 12: F2 + F3 — 已知 [NEEDS_NEW_FAMILY], 列出 schema gap 给 Day 13-17 接

每 fixture close-out 前跑 schema cross-check: state_machine_v2 §2 + cut_lifecycle_v2 §3 字段全部 covered.

## 6. 不在 Day 10-12 scope

- Runnable test (没 framework code, 只 spec-level)
- Oracle generation path (Step 1, Day 13-17)
- Validator 重算 cert (Step 5, Day 13-17)
- 实际 watcher index 命中验证 (Step 8, Phase 1)
- Quarantine 政策 (Step 9, Phase 1)

Day 10-12 close 后 Day 13-17 起 4 类新 cut family schema, 之后 Day 18-21 集成 + exit criteria.
