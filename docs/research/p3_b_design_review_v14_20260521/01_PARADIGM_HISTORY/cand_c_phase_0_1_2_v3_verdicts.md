# Cand C (Column Generation / Branch-and-Price) — Phase 0/1/2 v1/v2/v3 实测

## 起点

Cand C 是项目 paradigm investigation 标记的 alive candidate 之一. 跟 24 lever 死法不同方向: 不
在 CP-SAT pose-bool master 内加 cut, 而是 **重写 master form 为 set
partitioning / set covering LP + pricing CP-SAT + branch-and-price**.

## Phase 0 (probe paradigm survival, 2026-05-21 早)

测 5/20/40/80 inst ramp 上 paradigm 是否能跑通 (RMP + pricing 1 iter + 至
少能解出 LP). verdict **4/4 GO** — paradigm 在小规模 survives.

## Phase 1 (integer reconstruction, 2026-05-21 上午)

加 m10 integer reconstruction (m10 = "RMP LP optimal 是否能 round 到 set
partitioning integer feasible"). 4/4 ramp GO (5/20/40/80 inst):
- m10 = True
- m11 (branching nodes): 11/33/53 (size-scaled)
- m13 cache hit rate ≥ 0.80
- m14 RF (Ryan-Foster) vs std nodes ratio measured

Phase 1 验证 paradigm 在 80 inst scale 下还能 integer 解. 推 Phase 2.

## Phase 2 v1 (commit 73ea69a, 2026-05-21 中午) — NO-GO

8 ramps (5/20/40/80/160/266 + 2 variants). Bug summary:

- 160/266-inst bootstrap RMP **infeasible at iter 0**. 根因: Phase 1 的
  `degenerate_singleton_columns` greedy 找不到 disjoint singleton cover
  在 pose pool 被 ghost-rect filter + boundary_storage_port 134 pose 小池
  挤压后.
- 80-inst RF `nodes=N leaves=0`. depth-cap 5 不足.
- 80inst_routing_aware + 80inst_boundary_eq 各种 RMP infeasibility / m10
  inconsistency (deferred to Phase 3).

## Phase 2 v2 (commit 3844aea) — NO-GO

Fix Bug 1+2:
- 3-layer feasibility bootstrap (`feasibility_bootstrap.py`): Layer 1
  direct mini-master 60s → Layer 2 region multi-facility CP-SAT → Layer 3
  Phase 1 singleton greedy
- RF max_depth 5 → 10 + `_attempt_rounded_leaf` at depth cap + `branch_and_price_with_fallback`

160/266 inst 仍 `rmp_INFEASIBLE_at_iter_0` 即使 bootstrap 装配了 218/324
column cover all instance individually. **根因**: cell-exclusivity vs
exactly-1 partition contradiction 在 96% 利用率下无 λ 同时满足.

## Phase 2 v3 (2026-05-21 下午) — NO-GO (最终)

A3 (set covering 替 set partition) + A1 (alternative blueprint) 升级. 实
测数据:

| Ramp | iters | exit_reason | m5 multi-col % | m8 sound | m10 integer recon | m14 RF/std | verdict |
|---|---|---|---|---|---|---|---|
| 5inst | 3 | no_negative_rc_at_iter_3 | 72.2 | True | **False** | — | GO (size-scaled threshold pass) |
| 20inst | 70 | duplicate_column_at_iter_70 | 91.6 | True | True | 2.44 | **NO-GO** (m14 > 0.5 cap) |
| 40inst | 92 | duplicate_column_at_iter_92 | 92.2 | True | True | 4.38 | **NO-GO** (m14 > 0.5 cap) |
| 80inst | 100 | no_negative_rc_at_iter_100 | 83.9 | True | **False** | 1.54 | **NO-GO** (m10 False — sound 临界) |
| 160inst | 0 | **rmp_INFEASIBLE_at_iter_0** | 35.0 | **False** | False | — | **NO-GO** (RMP infeasible) |
| 266inst | 0 | **rmp_INFEASIBLE_at_iter_0** | 24.4 | **False** | False | — | **NO-GO** (RMP infeasible) |

## 各 ramp 死法分类

### 5 inst — m10 失败 (sound check threshold relaxed pass)

只 3 iter exit at `no_negative_rc`, RMP converged but integer reconstruction
fails. 5 inst 太小, set covering LP relax to all = 1 容易, integer round
难 (`m10_integer_reconstruction_required = False` 在 5 inst threshold).

### 20-40 inst — m14 RF 不加速

m14 = RF nodes / std nodes. 应 ≤ 0.5 (RF 半树). 实测 2.44 / 4.38 → RF
**比 std 多 2-4 倍 nodes**. Ryan-Foster 在 pair 选错时反而加速负贡献.

### 80 inst — m10 sound 临界

100 iter `no_negative_rc` exit, RMP 收敛 but integer reconstruction
False. 80 inst 是 sound 临界点 — 上不去也下不来. (这是 Sound 性临界文件
单独提到的 trap 来源.)

### 160-266 inst — RMP infeasible at iter 0

最严重: bootstrap 装 218 / 324 column cover all instance individually,
但 RMP LP **0 iter infeasible**. 根因:

- 132 个 `manufacturing_3x3` 占 132 × 9 = 1188 cell
- 49 个 `manufacturing_5x5` 占 49 × 25 = 1225 cell
- 38 个 `manufacturing_6x4` 占 38 × 24 = 912 cell
- 46 个 `boundary_storage_port` 占 46 × 3 = 138 cell (必须 perimeter)
- 1 个 `protocol_core`
- ≈ **3479 cell** facility footprint
- 加 power_pole + belt + connector ≈ 4300+ cell 实际占用
- **4900 cell grid - ghost rect 400-600 = 4300-4500 free cell**
- 利用率 ~ 96%

LP relax (set covering A3): Σ_k λ_k [iid∈k] ≥ 1 per instance, Σ_k λ_k *
indicator(k uses cell c) ≤ 1 per cell. 两约束族在 96% utilization 下无
共同可行 λ — partition contradiction.

## verdict_failures 全表 (从 phase2_results.json)

```json
"verdict_failures": [
    "20inst:m14_rf_no_speedup",
    "40inst:m14_rf_no_speedup",
    "80inst:m10_integer_reconstruction_failed,m14_rf_no_speedup",
    "160inst:m6_too_many_singleton_columns,m8_sound_check_failed,m10_integer_reconstruction_failed",
    "266inst:m5_not_enough_multi_facility_columns,m6_too_many_singleton_columns,m8_sound_check_failed,m10_integer_reconstruction_failed"
]
```

## 项目方判断 (送审稿前)

- cand C **现 cut language 范畴穷尽**. Ryan-Foster + set covering A3 +
  alternative blueprint A1 已经是 textbook column generation 的最强组合.
- 160/266 inst RMP infeasible at iter 0 是 **geometric stress**, 不是
  algorithmic engineering 问题 — 加新 column 没用, 因为 LP relax 本身
  在 96% utilization 下不可行.
- **现 cut language** = set partitioning / set covering + cell-exclusivity
  + ghost-rect filter. 表达不了 "perimeter constraint × component
  connectivity" 这类 cut.
- → 推 Design B (重写 master + 自研 cut engine, 不在 cand C 的 set
  partition LP 范畴内)


## 关键 telemetry 数据 (供 stress test 参考)

- 5 inst: pricing pose pool 71085 records, n_pose 每 cell avg 327
- 20 inst: m1 generated columns = 238, m12 avg 6.75 facility/col
- 40 inst: m1 = 92 iter ends, max 8.7 facility/col
- 80 inst: m1 generated 100 iter, m5 83.9% multi-col
- 160 inst: bootstrap n_columns = 218, **n_covered_instances = 218 / 160 = each instance covered** (但 LP 不可行)
- 266 inst: bootstrap n_columns = 324, n_covered = 266 / 266 (每 inst covered) 但 LP 不可行
