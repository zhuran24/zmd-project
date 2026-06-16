## Round 5 Verdict
GO

## R4 fix verification (Finding #1/#2/#3/#4)
- Finding #1 fix (evaluator protocol_core position check): LANDED — `src/cuts/families/power_grid_reach.py:596` (`_eval_check_protocol_core_position`). 完美实现了 O(81) 的 hot-path 检查，确保 9×9 footprint 仍被 `protocol_core` 占据。
- Finding #2 fix (validator SoT cross-check): LANDED — `src/cuts/families/power_grid_reach.py:507` (`_validate_source_of_truth_scalars`)。分别通过 `_validate_pole_radius_sot` 和 `_validate_pc_anchor_sot` 独立校验了 radius 和 anchor，彻底封堵了 R=0.001 伪造攻击。
- Finding #3 defer (Phase 1.2 bounds-only): ACCEPTED — 在 `state.cell_owner` 为空时 fallback 到 bounds-only 检查，符合 Phase 1.2 fixture/early-phase 的预期，且在 production 状态下会被严格校验。
- Finding #4 fix (negative coord parse): LANDED — `src/cuts/families/power_grid_reach.py:126`。明确加入了 `x < 0 or y < 0` 的前置拦截，修复了负数越界漏洞。

## R5 NEW Gap N/O/P
- R5-Gap N (4-round 收敛慢): REJECTED — F8 的高复杂度源于其全局连通性（Global Connectivity）的本质，需要动态构建几何图并进行 BFS，同时涉及多维度的 SoT 交叉验证（radius, protocol core, ghost, exterior）。前 4 轮的修补是收敛到 Soundness 的必经之路，当前架构已无系统性盲点。
- R5-Gap O (canonical pole→pole simplification): CONFIRMED — Spec §1c 明确记录了该简化，且在 `src/cuts/assumptions/verifiers.py:114` (`verify_power_pole_jump_radius`) 中被严格 enforce，符合 Phase 1.2 预期。
- R5-Gap P (Phase 1.2 close criteria): CONFIRMED — Phase 1.2 的 single-case scope (ghost-only cause) 被 `_validate_ghost_only_disconnect` 严格约束，排除了 cell_owner 导致的 disconnect，完全满足 close criteria。

## Round 5 New findings
(无新 finding，代码极其严密，防御纵深设计极佳)

## Sanity (GO verdict 必 ≥3 disproved hypothesis)

1. **Hypothesis**: `_validate_pc_anchor_sot` 在 `state.instance_to_facility_type` 缺失时返回 `None` (Accept)，会导致恶意伪造的 anchor 绕过验证。
   **Disproved**: 在 `validate_power_grid_reach` 的执行链中，`_validate_group_and_template` (line 546) 优先于 SoT 校验执行。如果 `instance_to_facility_type` 缺失，`_validate_group_and_template` 会直接返回 `unsound` (line 253)，因此恶意 cert 根本无法到达 SoT 校验阶段。Fail-closed 逻辑闭环完美。

2. **Hypothesis**: `evaluate_geometric_power_grid_reach` 在 `state.cell_owner` 为空时直接返回 `True`，如果此时 power network 实际上 reconnect 了，会导致 False Positive 误剪。
   **Disproved**: Generator 阶段严格执行了 `_validate_ghost_only_disconnect` (line 391) 检查，确保该 cut 的 disconnect **仅由 ghost 引起**。由于 ghost 始终存在，即使 `cell_owner` 为空（没有任何 facility 阻挡），网络依然是断开的。因此 evaluator 不重算 BFS 直接返回 `True` 是 100% Sound 的 O(1) 优化。

3. **Hypothesis**: `watcher_keys_power_grid_reach` 没有监听 `protocol_core` 的 cells，如果 master 移动了 protocol core，cut 不会被 watcher 触发 re-evaluate，导致 cut 永久残留。
   **Disproved**: F8 是 Geometric mode cut，其 `evaluate_geometric_power_grid_reach` 会在每次 Benders iteration 的 hot path 上对所有 attached cuts 执行。如果 protocol core 移动，`_eval_check_protocol_core_position` 会立刻返回 `False`，该 cut 会被正确跳过（不加入 solver）。Geometric cut 不依赖 watcher 来维持正确性，当前实现完全符合生命周期设计。

## 终结建议
- **close at this round (Phase 1.2 final)**: F8 已达到极高的工程质量与数学严谨度，可直接合入主分支。
- Phase 1.5+ defer items: 
  - 引入专用的 `pole_to_pole_jump_radius` canonical 字段。
  - 扩展 watcher 监听范围至 `BoundingBox(facility, R_jump + pc_size)` 以支持 cell_owner 释放后的 reconnect 场景。
  - 启用 multi-literal 支持 cell_owner 导致的 disconnect。