## Round 2 Verdict
NOT_GO

## R1 fix verification (Finding #1/#2/#3)
- Finding #1 fix (enumerate_valid_pole_anchors + 调用点): LANDED — `src/cuts/helpers/power_cover.py:62` 提供了正确的全 grid 枚举，validator (`src/cuts/families/power_grid_reach.py:349`) 和 generator (`src/cuts/oracles/power_grid_reach_oracle.py:157`) 均已正确调用，修复了 R1 漏掉 spanning intermediate poles 的 100% FP 问题。
- Finding #2 fix (pc_cells multi-cell + 4 子 helper): PARTIAL — `build_power_network` 确实引入了 `pc_cells` footprint (`src/cuts/helpers/power_network.py:115`)，但 `_pole_pc_edges` 距离计算和去重逻辑存在严重缺陷（见 New Finding 1 & 3）。
- Finding #3 fix (evaluator selected_poses): LANDED — `src/cuts/families/power_grid_reach.py:466` 正确增加了 `pose_raw not in group_state.selected_poses` 检查，防止了 ghost AABB 被永久毒化。
- Finding #4 defer (Phase 1.5+): ACCEPTED — 宽泛的 `except Exception: return False` 作为 hot-path fail-safe 保留，牺牲 prune 率保 soundness 是合理的工程权衡。

## R2 NEW Gap E/F/G
- R2-Gap E (validator validation 时间): CONFIRMED — ~4000 个 pole 产生 ~8M 个 pair，O(|V|²) 导致单次 validation 约 1-2s。1000 个 cut 需 ~30 分钟。Phase 1.2 勉强可接受，Phase 1.5+ 强烈建议引入 spatial grid (O(N)) 优化。
- R2-Gap F (selected_poses O(n) hot-path): REJECTED — `selected_poses` 列表极小 (demand 通常 ≤ 50)，Python 中 50 个 string 的 `in` 操作耗时在纳秒级，6M ops 仅需 ~0.01s，无需 frozenset cache。
- R2-Gap G (pc/pole overlap edge dedup): REJECTED — `_build_full_free_mask` (`src/cuts/families/power_grid_reach.py:317`) 明确将 `pc_cells` 加入了 `blocked` 集合，因此 `free_cells` 绝不会包含 `pc_cells`，两者在实际调用中严格 disjoint，不会漏 edge。

## Round 2 New findings (≥3, 任何 severity, R1 没 catch 的)

### Finding 1: [CRITICAL] src/cuts/helpers/power_network.py:64 — _can_jump 使用 anchor-to-cell 距离导致 False Positive
`_pole_pc_edges` 将 pole anchor (2×2 的左上角 cell) 和 1×1 的 PC cell 传给 `_can_jump`，后者使用 `_euclidean` 计算距离。这高估了真实的最小 cell-to-cell 距离（`compute_cover_set` 正确使用了 `_min_cell_distance`）。几何上合法的 pole-to-PC jump 会被错误拒绝，导致 graph 连通性断裂并误发 FP cut。

### Finding 2: [CRITICAL] src/cuts/helpers/power_network.py:68 — Liang-Barsky 裁剪使用左上角坐标导致线段偏移
`_can_jump` 将 `(float(p1[0]), float(p1[1]))` 传给 `segment_intersects_aabb`。对于 2×2 pole，这是左上角坐标，而非物理中心 `(x + 1.0, y + 1.0)`。这导致用于 ghost 碰撞检测的线段相对于真实的 pole 中心偏移了 `(-1.0, -1.0)`，会同时引发 False Positive 和 False Negative。

### Finding 3: [HIGH] src/cuts/helpers/power_network.py:116 — pc_set -= pole_set 去重逻辑写反
注释声明 "pc cells take priority — drop any overlapping pole copy"，但 `pc_set -= pole_set` 实际上是从 `pc_set` 中删除了重叠的 PC cell 并保留了 pole！虽然当前因 `free_cells` 互斥而未触发，但这严重违反了 helper 的 API 契约，应改为 `pole_set -= pc_set`。

### Finding 4: [HIGH] src/cuts/oracles/power_grid_reach_oracle.py:84 — Generator 错误读取 facility_pools 导致静默失效
`_pose_cells_from_canonical` 试图读取 `pools = placements.get("facility_pools")`。根据 `data/preprocessed/candidate_placements.json` 的 schema，顶层 key 直接是 facility type（如 `"manufacturing_3x3"`），不存在 `"facility_pools"` 这一层。这导致 generator 永远返回 None 并静默跳过所有 facility，发出 0 个 cut。

## Sanity (GO verdict 必 ≥3 disproved hypothesis 含 file:line)
*(NOT_GO verdict, 但仍提供 disproved hypothesis 证明深度)*
1. **Hostile cert payload (越界/重复 cells)**: Disproved. `src/cuts/families/power_grid_reach.py:110` 的 `_parse_facility_cells` 严格校验了 `0 <= x < _GRID_SIZE`、严格升序排列以及无重复 cell。
2. **Watcher store integration 遗漏**: Disproved. `src/cuts/families/power_grid_reach.py:488` 的 `watcher_keys_power_grid_reach` 正确提取了 `group_keys`, `pose_keys` 和 `cell_keys`，且 `by_ghost_watcher` 由 store 自动根据 scope 挂载。
3. **Schema validation strict mode 绕过**: Disproved. `_validate_scalars` (`src/cuts/families/power_grid_reach.py:165`) 对 `pole_jump_radius` 做了严格的 `_is_strict_float` 检查，拒绝了 bool 和负数，且强制 `pole_shape_canonical` 必须为 `"2x2_rigid"`。

## 建议 Round 3 重点 / Phase 1.5+ defer
- **Round 3 必须修复**: 统一所有距离计算为 `_min_cell_distance` (cell-to-cell)；修正 Liang-Barsky 的线段端点为真实的物理中心坐标 (e.g., `x + 1.0` for 2x2 pole, `x + 0.5` for 1x1 PC cell)；修复 Generator 的 JSON key 路径。
- **Phase 1.5+ defer**: `build_power_network` 的 O(|V|²) 性能瓶颈 (R2-Gap E) 建议在 Phase 1.5+ 引入 Spatial Hash Grid 优化，将边构建降至 O(N)。