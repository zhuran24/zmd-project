## Round 1 Verdict
NOT_GO

## Verify Gap A/B/C
- **Gap A (1×1 vs 2×2 spec drift)**: CONFIRMED. Spec §1a/§3 错误地写了 "1×1 pole"，但实施代码 (`_POLE_SIZE = 2`, `pole_shape_canonical = "2x2_rigid"`) 遵循了 `canonical_rules.json` 的 ground truth。这是一个 **Sound 的设计决策**。如果强行用 1×1 去算 CoverSet，会导致本放不下 2×2 pole 的地方被误判为可放，从而漏剪 (False Negative)；反之如果按 1×1 剪了，实际游戏是 2×2，则是正确的。实施跟真数据是对的，Spec 文本需要修。
- **Gap B (metric label missing)**: CONFIRMED. Schema 确实漏了 metric label，但实施在 `src/cuts/helpers/power_cover.py` 的 `_min_cell_distance` 中硬编码了标准的 Euclidean 距离 (`math.sqrt(min_sq) <= pole_radius`)。对于网格类游戏，默认 Euclidean 是符合直觉和项目共识的。推荐在 Phase 1.5+ 的 `Assumption` 中显式加上 `power_metric=euclidean`。
- **Gap C (ghost ∩ cell_owner edge case)**: REJECTED. 设计没有漏 catch。在 `compute_cover_set_ghost_only` 中，掩码是 `ghost_cells | exterior_blocks`，完全忽略了 `cell_owner`。如果 ghost 单独就能把 CoverSet 清空，那么无论 `cell_owner` 是否与 ghost 重叠，根据单调性，ghost + cell_owner 也必然为空。因此，只要 ghost-only CoverSet 为空，将其归因为 ghost cause 并生成单 literal cut 是 100% sound 的。

## Round 1 New findings (≥3, 任何 severity)

### Finding 1: [CRITICAL] src/cuts/families/power_hitting_set.py:_validate_coverset_empty — 漏排除 facility_cells 导致 Replay 阶段 100% 误杀
在 Validator 重算 CoverSet 时，`free_cells` 的构造仅排除了 `ghost_cells`、`exterior_blocks` 和 `cell_owner_keys`。但在 Replay 阶段（或 facility 尚未 placed 的状态下），该 facility 的 cells 不在 `cell_owner` 中，导致 `free_cells` **包含了 facility 自身的占地**。
由于 3×3 或 5×5 的 facility 内部足以塞下一个 2×2 的 pole，`compute_cover_set` 会在 facility 内部找到合法的 pole anchor（距离为 0 ≤ R），导致 `cover_full` 非空，Validator 错误地返回 `unsound` 并隔离该合法 cut。
**修复**：`free_cells` 必须显式扣除 `facility_cells`（`compute_cover_set_ghost_only` 同理）。

### Finding 2: [MEDIUM] src/cuts/oracles/power_cover_oracle.py:_pose_cells_from_canonical — O(N) 线性扫描导致 Generator 性能隐患
Generator 在查找目标 pose 的 occupied_cells 时，遍历了 `state.candidate_placements["facility_pools"][facility_type]` 列表。对于 70x70 棋盘，一个 3x3 facility 有约 4600 个合法 pose。每次 generate 都要做 $O(N)$ 扫描，若 target_poses 较多会产生不必要的毫秒级开销。建议在 Phase 1.5+ 引入 pose_id 到 cells 的 dict 索引。

### Finding 3: [LOW] src/cuts/helpers/power_cover.py:_covers_any_facility_cell — 浮点数开方比较可优化为整数平方比较
`_min_cell_distance` 使用了 `math.sqrt(min_sq)` 并与 `pole_radius` 进行浮点比较。虽然对于 `R=5.0` 这种整数半径在 Python 中不会有精度问题，但更安全且性能更好的做法是直接比较平方值：`min_sq <= pole_radius ** 2`，彻底规避潜在的浮点精度边界 case。

### Finding 4: [INFO/SPEC DRIFT] src/cuts/families/power_hitting_set.py:watcher_keys_power_hitting_set — 优化去除了 ghost_blocked_pole_cells 监听
Spec §8 要求监听 `ghost_blocked_pole_cells`，但实施代码仅监听了 `facility_cells`。这是一个**聪明的优化且 Sound**：因为 Phase 1.2 仅处理 `power_cover_emptyset_ghost`，该 cut 的有效性仅依赖于 ghost 和 exterior。即使 `cell_owner` 在 ghost 区域内发生变化，也不会影响 ghost-only cut 的成立。建议更新 Spec 以反映此 payload/watcher 减负优化。

## Sanity (Disproved Hypotheses)
1. **Hypothesis**: `_validate_scalars` 允许 `pole_radius` 为 int，会导致类型校验失败。
   **Disproved**: `_is_strict_float` 的实现为 `isinstance(value, (int, float))`，兼容了 `canonical_rules.json` 中 `5` 被解析为 int 的情况，且后续强转了 `float(pole_radius)`，安全 (`power_hitting_set.py:_validate_scalars`)。
2. **Hypothesis**: `needs_power=False` 的 facility（如 protocol_core）会被误生成 cut。
   **Disproved**: Generator 的 `_facility_template_needs_power` 和 Validator 的 `_validate_group_and_template` 均严格校验了 `tpl.get("needs_power") is True`，Fail-closed 拦截了此类攻击 (`power_cover_oracle.py:65`)。
3. **Hypothesis**: `compute_cover_set` 遍历 anchor 时可能会越界。
   **Disproved**: 遍历范围是 `range(grid_size - pole_size + 1)`，对于 70x70 和 2x2 pole，最大 anchor 为 68，加上 dx=1 刚好是 69，严格在 0~69 范围内，无越界风险 (`power_cover.py:_enumerate_valid_pole_anchors`)。

## 建议 Round 2 重点 / Phase 1.5+ defer
- **Round 2 重点**：修复 Finding 1，确保 Validator 在构造 `free_cells` 和 `ghost_only` 掩码时，强制 `blocked_cells |= set(facility_cells)`，否则 Replay 必挂。
- **Phase 1.5+ defer**：多 literal 的 cell_owner causation cut (v1.1 case B)；引入 `power_metric=euclidean` Assumption；优化 pose_id 查找性能。