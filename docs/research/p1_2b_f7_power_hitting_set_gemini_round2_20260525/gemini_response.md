## Round 2 Verdict
NOT_GO

## R1 Fix Verify
- **R1#1 facility_cells exclude (validator + oracle)**: CORRECT. 
  Validator (`power_hitting_set.py:246`) 和 Oracle (`power_cover_oracle.py:126`) 均已将 `facility_cells` 正确加入 blocked mask / 从 free_cells 中剔除。边界 case 下（如 facility cells 与 ghost 重叠），`frozenset` 的 union 操作天然去重，不会引入 over-rejection，彻底修复了 R1 的 fail-open 漏判。
- **Oracle/validator mask 一致性**: CORRECT. 
  Oracle 的 `_ghost_only_free_cells_minus_facility` (`power_cover_oracle.py:136`) 与 Validator phase 7 的 inline mask (`power_hitting_set.py:269`) 逻辑完全等价（均为 `grid - ghost - exterior - facility`），跨 worker 具有 100% 的 reproducibility。

## Round 2 New Findings (≥2, 任何 severity)

### Finding 1: [CRITICAL] src/cuts/families/power_hitting_set.py:116 — PoseId 类型强校验导致 100% schema_err (Spec Drift)
Validator 的 `_validate_scalars` 强制要求 `facility_pose_id` 必须是字符串 (`_is_non_empty_str(fp)`)。但在真实数据和 Spec F3 反例中（`"facility_pose": ["crusher_blue_iron", 17]`），`PoseId` 通常是 `int`。若传入 `int`，Validator 会在 Phase 3 直接抛出 `schema_err` 拒绝合法 cut；同时 `watcher_keys_power_hitting_set` (line 343) 也会因类型不符被 `except` 吞掉，导致 watcher 注册失败。
**Fix**: 将 `_is_non_empty_str(fp)` 放宽为允许 `int` 或 `str`，并在后续比对时统一转为 string 或保持原类型比对。

### Finding 2: [MEDIUM] src/cuts/oracles/power_cover_oracle.py:246 — Generator 漏填 active_assumptions
Generator 在构造 `CutScope` 时未传入 `active_assumptions`，导致其默认为空元组 `()`。这违反了 Spec §4 要求的 `Assumption("power_pole_radius", "R=5")` 和 `Assumption("power_pole_shape", "1x1_rigid")`（或实施的 2x2_rigid）。虽然 `artifact_hashes` 能提供基础保护，但丢失了 v2 lifecycle 要求的显式假设追踪。
**Fix**: 在 `_build_cut` 的 `CutScope` 初始化中补齐 `active_assumptions`。

### Finding 3: [LOW] src/cuts/helpers/power_cover.py:84 — 遗留的 dead code `compute_cover_set_ghost_only`
Helper 文件中保留了 `compute_cover_set_ghost_only` 函数，且 docstring 标明 "Used by F7 validator phase 7"。但实际上 Validator phase 7 (`power_hitting_set.py:269`) 已经 inline 了 mask 构造并直接调用了 `compute_cover_set`。该 helper 目前在整个 codebase 中 0 引用。
**Fix**: 移除该 dead code 以保持代码整洁。

## Sanity (3 disproved hypothesis)
1. **Hypothesis**: `_min_cell_distance` 中的 `math.sqrt(min_sq) <= pole_radius` 存在浮点精度丢失风险，导致边界覆盖被误判。
   **Disproof**: 坐标差的平方和 `min_sq` 是整数。对于刚好在半径边缘的 case（如 R=5.0, min_sq=25），`math.sqrt(25)` 在 IEEE 754 下精确等于 `5.0`，`5.0 <= 5.0` 严格成立，无精度丢失风险 (`power_cover.py:36`)。
2. **Hypothesis**: Validator phase 7 的 ghost-only mask 若与 facility_cells 存在重叠，会导致 mask 异常。
   **Disproof**: `blocked = frozenset(state.ghost_cells) | frozenset(state.exterior_blocks) | facility_set` (`power_hitting_set.py:269`)。Python 的 `frozenset` union 操作天然处理元素重叠，不会引发任何异常或重复剔除。
3. **Hypothesis**: Generator 在 `_pose_cells_from_canonical` 中若遇到 `occupied_cells` 为空列表会 crash。
   **Disproof**: 若 `occupied` 为空，循环结束返回 `tuple(sorted([]))` 即 `()` (`power_cover_oracle.py:108`)。后续 `compute_cover_set` 遇到空的 `facility_cells` 会安全地返回 `frozenset()` (`power_cover.py:66`)，逻辑安全。

## 建议 Round 2 重点 / Phase 1.5+ defer
- **立即修复**: Finding 1 的 `PoseId` 类型强校验是 Blocker，必须兼容 `int`。
- **立即修复**: Finding 2 补齐 `active_assumptions` 以对齐 v2 schema。
- **Phase 1.5+ defer**: Cell_owner causation 的多 literal 扩展 (witness_kind="empty_coverset_cell_owner") 维持 defer 状态，当前单 literal 拦截逻辑已通过 ghost-only 二次校验确保 sound。