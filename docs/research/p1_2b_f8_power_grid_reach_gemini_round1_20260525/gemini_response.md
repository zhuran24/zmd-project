## Round 1 Verdict
NOT_GO

## Verify Gap A/B/C/D
- Gap A (pole_jump_radius caller-supplied): CONFIRMED — 严重漏洞。Generator 在 `src/cuts/oracles/power_grid_reach_oracle.py:255` 构造 `CutScope` 时，**完全没有**按 Spec §4 写入 `active_assumptions`。Validator 也仅从 `cert_dict` 读取该值而无任何交叉校验。Caller 传入的 radius 既无 source-of-truth 校验也无 audit trail 记录，信任边界被完全破坏。
- Gap B (protocol_core state-dependent): CONFIRMED — 严重漏洞。O(1) Evaluator (`src/cuts/families/power_grid_reach.py:408`) 仅校验了 `ghost_rect_id` 和 `exterior_blocks_hash`。如果 Master 在后续 state 中将 `protocol_core` 移动到其他 pose，Power Network 可能已经重新连通，但 Evaluator 仍会返回 `True` 导致 False Positive 误剪。
- Gap C (O(1) evaluator monotonicity): CONFIRMED — 致命漏洞。Evaluator 甚至**没有检查该 facility 是否仍被放置**！Spec §6 明确要求 `if (facility_group, facility_pose_id) not in [... selected_poses]: return False`，但代码中完全遗漏。由于 F8 是 `literals=None` 的全局 geometric cut，一旦触发，只要 ghost 不变就会永久 block 整个 state，即使 solver 已经把该 facility 移走！
- Gap D (Liang-Barsky endpoint on edge): CONFIRMED — 数学上 touching 算作 block。`cell_aabb_from_rect` 将边界严格扩展到 `x+h`，且 `segment_aabb_intersection_t` 中 `qi < 0` 不会 reject `qi == 0` 的平行相切情况。这在数学上是 safe/conservative 的（相切即视为阻断），符合 "含边" 的保守定义，不会导致 False Negative。

## Round 1 New findings (≥3, 任何 severity)

### Finding 1: [CRITICAL] src/cuts/oracles/power_grid_reach_oracle.py:175 — 寻路图缺失全局中间节点导致 100% 误判
Generator 和 Validator (`src/cuts/families/power_grid_reach.py:321`) 在构建 `build_power_network` 时，传入的 poles 列表仅为 `list(cover_set)`。`cover_set` 仅包含紧贴 facility 的局部 pole anchors！这导致图中**完全缺失了跨越 grid 的所有中间 pole 候选**。任何距离 `protocol_core` 大于 `pole_jump_radius` 的 facility 都会因 BFS 无法直达 core 而被错误判定为 disconnect (False Positive)。必须传入 `_enumerate_valid_pole_anchors(full_free)`。

### Finding 2: [CRITICAL] src/cuts/helpers/power_network.py:65 — 9x9 protocol_core 被错误降维为单点计算跳跃距离
`build_power_network` 将 `pc_cell` 作为一个普通 `Pole` 节点加入图，并使用 `_euclidean(p1, p2)` 计算跳跃距离。但 `protocol_core` 是 9x9 的巨型建筑，`pc_cell` 只是其左上角 anchor。位于 core 右下角相邻的 pole 距离 anchor 超过 9 个 cell，会被 `_euclidean` 判定为大于 `pole_radius=5` 从而无法连接，导致大面积 False Positive。

### Finding 3: [CRITICAL] src/cuts/families/power_grid_reach.py:408 — Evaluator 缺失 facility placement 校验导致永久毒化
如 Gap C 所述，`evaluate_geometric_power_grid_reach` 遗漏了 Spec §6 要求的 `selected_poses` 检查。由于 F8 cut 的 `literals=None`，只要 ghost 和 exterior 不变，该 cut 就会一直 active。Solver 即使回溯并移走了触发 disconnect 的 facility，依然会被该 cut 拦截，导致整个 ghost 空间被永久毒化 (False Positive)。

### Finding 4: [HIGH] src/cuts/families/power_grid_reach.py:426 — Evaluator fail-safe 掩盖严重 Schema 错误
`evaluate_geometric_power_grid_reach` 的 `except Exception: return False` 过于宽泛。如果 payload JSON 损坏或 scope 字段缺失，它会静默返回 `False`（放行）。对于 Soundness 审查员而言，底层数据结构的损坏应当 fail-closed 或抛出异常，而不是静默失效。

## Sanity (如果 GO, 至少 3 disproved hypothesis 含 file:line)
*(Verdict 为 NOT_GO，无需 disprove)*

## 建议 Round 2 重点 / Phase 1.5+ defer
1. **Round 2 必须修复**：重写 `build_power_network` 的调用，必须传入全局 `free_cells` 上的所有合法 pole anchors，而不仅仅是 `cover_set`。
2. **Round 2 必须修复**：`evaluate_geometric_power_grid_reach` 必须补回 `(group, pose) in selected_poses` 的检查，否则 `literals=None` 会摧毁求解器。
3. **Round 2 必须修复**：`build_power_network` 必须支持 `protocol_core` 的多 cell 距离计算（或 Bounding Box 距离），不能仅测距到 anchor。
4. **Phase 1.5+ Defer**：将 `pole_jump_radius` 正式加入 `canonical_rules` schema，消除 caller-supplied 带来的信任边界风险。