## Round 3 Verdict
GO_WITH_MINOR

## R2#3 Fix Verify
CORRECT — cert_payload 中加入 `"blocking_facilities": []` 满足了 F4 spec v1.1 的 schema 契约。关于 `cert_hash` 的影响分析：由于 `cert_hash` 是基于 `canonical_bytes_for_cert(cert_payload_dict)` 计算的，在 JSON `sort_keys=True` 的标准下，`"blocking_facilities"` 会按字母序稳定排在 `"commodity_id"` 之前。这必然导致 hash 发生改变，但这是完全 expected 且 sound 的行为。`oracle_cert_hash` 作为基于内容的 identity，内容扩充理应导致 hash 变化，这保证了跨 worker 的 reproducibility，且不会引发 false dedup risk。同时，v1.1 validator 已经移除了对该字段的强校验，因此携带空列表不会破坏现有的 292 cuts pytest。

## Round 3 New Finding (1 个 minimum)

### Finding 1: [MEDIUM] src/cuts/oracles/cutset_oracle.py:150 — `_is_strict_positive_int` 拒绝真实数据中的 float demand
真实数据 `data/preprocessed/commodity_demands.json` 中包含浮点数 demand（如 `"buckwheat": 5.5`, `"qiaoyu_capsule": 0.55`）。但在 `_try_generate_one` 中，`demand_raw` 被 `_is_strict_positive_int` 严格校验为 `int`，导致所有带小数 demand 的 commodity 被 fail-closed 默默 skip，漏掉合法的 F2 cuts。由于 Dinic 算法需要整数容量，Phase 1.5+ 引入真实 cell capacity 时需统一进行 capacity scaling（如乘 100）或 math.ceil。当前 fail-closed 是 sound 的（不报假 cut），但会降低 LBBD 剪枝效率。

## F2 generator 边界 case

**1. `src == sink` skip 边界 (cutset_oracle.py:137)**
正确。当 `src == sink` 时，demand 在拓扑上无需跨越任何 edge 即可满足（或者属于 degenerate route）。此时 Dinic 无法提取有意义的 adjacency cut，跳过生成 F2 cut 是符合 Menger 定理和 F2 物理意义的。

**2. bfs_component 单源 skip 边界 (cutset_oracle.py:140)**
正确且 fail-closed 设计精妙。当 `src` 和 `sink` 都在 `free_cells` 中但互相 disconnected 时，F2 generator 选择 skip。这是因为此时 cut capacity 为 0，虽然也满足 `< demand`，但 F4 (component_reach) 专门负责处理 binary reachability（连通性断裂），F4 提取的 frontier separator 比 F2 的 0-capacity cut 表达力更强且更直接。交由 F4 处理避免了 cut family 之间的重叠和冗余。

**3. `result.cut_capacity >= demand` 等号 skip 边界 (cutset_oracle.py:159)**
正确。根据 Menger 定理，最大流 = 最小割。当 `cut_capacity == demand` 时，网络刚好能够承载所需的 demand，此时 flow 是 FEASIBLE 的。只有当 `cut_capacity < demand` 严格成立时，才会发生 Menger violation 导致 INFEASIBLE。因此，在等号边界处 skip 是严格 sound 的。

## Sanity (3 disproved, reference file:line)

1. **[Disproved]** `extract_frontier_separator` 提取的 separator_cells 可能会越界（坐标 < 0 或 >= 70）导致 validator 报 schema_err。
   *Disproof*: `src/cuts/helpers/dinic_node_split.py:59` 中 `extract_frontier_separator` 依赖 `neighbors_4conn` 获取邻居，而 `neighbors_4conn` (line 39) 严格执行了 `0 <= nx < grid_size and 0 <= ny < grid_size` 的边界检查，保证返回的 cell 绝对在 grid 内部。
2. **[Disproved]** `dinic_node_split_min_cut` 提取的 `cut_cell_edges` 可能会包含重复的无向边（例如同时包含 (A,B) 和 (B,A)），导致 cut_size 计算错误。
   *Disproof*: `src/cuts/helpers/dinic_node_split.py:277` 中明确对边进行了 canonicalize 处理：`pair = (cell_u, cell_v) if cell_u <= cell_v else (cell_v, cell_u)`，并存入 `cell_cut_edges_set` (set 结构) 中去重，最后返回 `tuple(sorted(...))`，绝对不会重复。
3. **[Disproved]** `_has_patch_escape` 在传入的 `patch` 为空集时，可能会在遍历时崩溃或返回错误结果。
   *Disproof*: `src/cuts/families/cutset.py:112` 中，如果 `patch` 为空，`outside_free = free_cells - patch` 等于 `free_cells`。接下来的 `for cell in patch:` 循环根本不会执行，直接 fall-through 返回 `False`。逻辑安全无崩溃。

## 下一步建议
**Close**. Phase 1.2 P1.2B-F2/F4 核心逻辑已达到高度 sound 状态。Round 3 发现的 float demand 属于 Phase 1.5+ capacity scaling 范畴的已知限制（当前 fail-closed 不破 soundness）。建议直接合并 `d5e653d` 并进入 Phase 1.3 (Propagator Integration)。