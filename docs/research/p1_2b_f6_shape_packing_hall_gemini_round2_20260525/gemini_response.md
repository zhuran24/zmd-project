## Round 2 Verdict
NOT_GO

## R1 Fix Verify

- R1#1 fail-closed (3 layer): CORRECT. Validator 显式检查了 `state.instance_to_facility_type`、`facility_type` 和 `state.facility_templates` 是否为 None 或缺失，全路径返回 `unsound`。`pose_length` 严格与 template dimensions 交叉校验，成功堵死 adversary 绕过路径。
- R1#2 evaluator O(1): WRONG. Evaluator 盲目信任静态 payload (`total_packable < region_demand`) 且完全忽略 `state`。当 cut 在 propagation 中被 watcher（如 `by_ghost_watcher`）因 ghost 移动而唤醒时，evaluator 会在 scope 校验前被调用。由于它不检查 scope 且永远返回 `True`，它会向 solver 谎报 cut 仍在 violating（即使新 ghost 位置已让 region 完全空闲），导致严重的 False Positive 冲突。
- R1#3 watcher format: CORRECT. `watcher_keys_shape_packing_hall` 正确使用了 `f"{region_kind}:shape_hall"` 格式，与 spec §8 完全对齐。
- Gap B conservative default: WRONG. 当 region fully blocked 时 default `region_demand = 1` 是 Unsound 的。因为 placement rule `left_or_bottom_boundary` 允许 group 的全部 demand 由**另一个** region 满足。仅因单边 blocked 就 emit cut，会错误地剪枝掉所有 pose 都合法放置在另一边 unblocked region 的有效状态。

## Round 2 New Findings (≥2, 任何 severity)

### Finding 1: [CRITICAL] src/cuts/families/shape_packing_hall.py:408 — Evaluator O(1) optimization causes False Positive conflicts on ghost movement
Evaluator `evaluate_geometric_shape_packing_hall` 信任静态 payload，但未检查 cut 的 scope (`ghost_rect`) 是否仍与当前 state 匹配。当 watcher 因 ghost 移动触发 evaluation 时，evaluator 在 scope validation 之前被调用。因为它忽略 `state` 且对合法 payload 永远返回 `True`，它会错误地告诉 solver 该 cut 仍在 violating，从而引发虚假冲突并错误剪枝。

### Finding 2: [HIGH] src/cuts/oracles/shape_packing_hall_oracle.py:108 — Phase 1.2 conservative default `region_demand=1` is UNSOUND for shared boundary groups
Generator 在 `region_demand_overrides` 为 None 时默认 `region_demand = 1`。如果某 region（如 `left_baseline`）被完全遮挡，它会 emit 一个要求该区域至少放 1 个 pose 的 cut。然而，`left_or_bottom_boundary` 规则意味着 group 的所有 demand 都可以合法地放在另一个 region。为单边 blocked 触发 cut 会制造虚假冲突，拒绝掉所有 pose 都放在未遮挡区域的合法状态。

### Finding 3: [HIGH] src/cuts/oracles/shape_packing_hall_oracle.py:105 — `region_demand_overrides` missing keys incorrectly fallback to 1 instead of 0
当 Phase 1.5+ caller 提供 `region_demand_overrides` 时，缺失的 key `(group_id, region_kind)` 意味着 master solution 在该区域放置了 0 个 pose。然而，generator 的逻辑 `if ... in overrides: ... else: region_demand = 1` 错误地将 missing keys fallback 到了 Phase 1.2 的默认值 1。这将导致 generator 在 master solution 故意放置 0 个 pose 的区域 emit unsound cuts，破坏 Phase 1.5+ 的集成。

## Sanity (≥3 disproved hypothesis with file:line)
1. **Hypothesis**: `_validate_partition_internal_consistency` 可能会在 `off == prev_end` 时允许 segment 重叠。
   **Disproof**: `if off <= prev_end:` 严格拦截了相等的情况，确保 segments 绝对无重叠 (`src/cuts/families/shape_packing_hall.py:165`)。
2. **Hypothesis**: `compute_baseline_partition_lens` 如果 baseline 最后一个 cell 是空的，可能会漏掉最后一个 segment。
   **Disproof**: 循环结束后的 `if current_len > 0:` 确保了最后一个 segment 必定被 append (`src/cuts/helpers/baseline_partition.py:62`)。
3. **Hypothesis**: `_validate_scalars` 可能会允许 `pose_length = 1`，导致退化为 F1 region_capacity。
   **Disproof**: 校验循环中的 tuple `("pose_length", 2)` 强制要求 `pose_length >= 2` (`src/cuts/families/shape_packing_hall.py:96`)。

## 下一步建议
1. **Evaluator Scope Check**: 修改 `evaluate_geometric_shape_packing_hall`，在直接信任 payload 前，必须 O(1) 校验 `compute_ghost_rect_id(state.ghost_rect) == cut.scope.ghost_rect_id`，若不匹配则返回 `False`（cut 不再 active）。
2. **Fix Default Demand**: Phase 1.2 不能仅因单边 blocked 就 emit cut。必须联合检查 `left_baseline` 和 `bottom_baseline` 的 `total_packable` 之和是否严格小于 `group_demand`，才能证明真正的 dead state。
3. **Fix Override Fallback**: 在 generator 中，若 `region_demand_overrides is not None`，对于 missing keys 应 default 为 `0` 并 `continue`（跳过），而不是 fallback 到 `1`。