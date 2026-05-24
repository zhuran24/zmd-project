## Round 2 Verdict
NOT_GO

## R1 Fix Verify

- R1#1 fail-closed (3 layer): CORRECT — `_validate_facility_template_match` 严格检查 `instance_to_facility_type`、`facility_type` 和 `facility_templates`，任何缺失均返回 `unsound`。前置 phase 均为基础校验，无 bypass 路径。
- R1#2 evaluator O(1): NEW_GAP — O(1) scope check 确实修复了 scope drift 时的 FP。但 evaluator 直接 trust payload 中的 `region_demand` 引入了跨 master iteration 的严重 unsound（见 Finding 1）。
- R1#3 watcher format: CORRECT — `region_id = f"{region_kind}:shape_hall"` 完全对齐 spec §8 要求。
- Gap B conservative default: CORRECT — Generator 强制要求 `region_demand_overrides`，且在 `group_demand < 1` 或 override 缺 key（master 放置 0 个）时正确 skip，避免了 FP。

## Round 2 New Findings (≥2, 任何 severity)

### Finding 1: [CRITICAL] src/cuts/families/shape_packing_hall.py:461 — Evaluator permanently kills valid scope due to stale `region_demand`
Evaluator 检查 `total_packable < region_demand` 时，使用的是 cert payload 中静态写死的 `region_demand`。在 Phase 1.5+ 的 Benders loop 中，如果 master problem 更新了 demand 使其变得 feasible（例如 `<= total_packable`），subproblem 的 evaluator 依然会读取旧的 stale demand（例如 `3 < 5` 永远为 True），导致其错误地认为 cut 仍在 violating，从而永久性地误杀当前完全合法的 `BState` (ghost+exterior)。Evaluator 必须基于当前 master demand 或实际的 `cell_owner` 摆放量进行评估。

### Finding 2: [HIGH] src/cuts/oracles/shape_packing_hall_oracle.py:214 — Generator populates `blocked_cells_hash` with `cell_owner`, breaking cross-layer survival
`_try_build_cut` 中将 `scope.blocked_cells_hash` 赋值为 `compute_blocked_cells_hash(state)`。由于该 hash 通常包含 `cell_owner`（已放置的格子），任何新的 pose 放置都会导致该 hash 改变。如果 `lifecycle.step_6` 严格校验 `blocked_cells_hash`，F6 cut 会在每次 `cell_owner` 改变时被错误地 invalidate，这彻底破坏了 v1.1 核心的 `cell_owner` independence invariant，导致 cut 无法跨层存活。应将其设为 `""` 或类似 `GHOST_AGNOSTIC` 的常量。

## Sanity (≥3 disproved hypothesis with file:line)

1. **Hypothesis**: `_validate_partition_internal_consistency` (line 197) 仅检查 `off <= prev_end`，允许连续段 (`off == prev_end + 1`)，adversary 可通过人为切碎 segment 来降低 `total_packable` 伪造 Hall witness。
   **Disproved**: `_validate_partition_recompute` (line 380) 会将 cert 的 lens/offsets 与重新计算的 maximal segments 进行严格的 byte-equal 比对，人为切碎的 segment 会因不匹配被直接 `unsound` 拒绝。
2. **Hypothesis**: `_validate_facility_template_match` (line 284) 未校验 `placement_rule == "left_or_bottom_boundary"`，adversary 可为 `anywhere` 的 group 提交 baseline Hall cut 导致 FP。
   **Disproved**: Hall cut 表达的是物理容量上限 (`Count(on baseline) <= capacity`)，这是一个 globally valid 的几何约束。无论 group 是否被强制要求放在 baseline，只要它实际被放置在 baseline，该物理约束就绝对成立，因此不需要校验 `placement_rule`。
3. **Hypothesis**: `compute_baseline_partition_lens` (line 51) 中 `blocked` 集合若包含越界的 `ghost_cells` 会导致 partition 计算越界或崩溃。
   **Disproved**: 遍历逻辑 `for idx, cell in enumerate(region_cells): if cell in blocked:` 仅在严格合法的 `region_cells` 范围内迭代，`blocked` 中多余的越界坐标会被安全地忽略，不会引发异常。

## 下一步建议
1. **修复 Finding 1**：重新设计 F6 的 evaluator 语义。如果 F6 作为 master problem 的全局约束，subproblem evaluator 不应基于 stale demand 返回 True；应考虑在 evaluator 中引入对当前 `state.cell_owner` 实际摆放量的 O(1) 统计，或由框架提供 current master demand。
2. **修复 Finding 2**：在 generator 中将 F6 的 `blocked_cells_hash` 显式置空或设为忽略标记，确保 `lifecycle.step_6` 不会因 `cell_owner` 变化而 drop F6 cuts。