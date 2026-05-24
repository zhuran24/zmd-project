## Round 2 Verdict
GO_WITH_MINOR

## R1 Fix Verify
- R1#1 iterative DFS: CORRECT — 完美模拟了递归调用栈。`stack` / `pushed` / `path_edges` 的入栈出栈逻辑与递归的 fall-through 完全等价。死胡同回溯时 `iter_ptr[parent_u] += 1` 且不重置 `stack[-1]`，精准恢复了父节点的探索进度；找到 path 时直接返回 `d` 并由外层循环重置栈，完美契合 Dinic 的多路增广特性，彻底消除了 70x70 蛇形长廊的 `RecursionError` 隐患。
- R1#3 bitset padding: CORRECT — `_decode_bitset` 已统一采用 `(grid_size * grid_size + 7) // 8` 公式，且 `extra_bits` 的高位越界校验 `arr[-1] >> (8 - extra_bits)` 逻辑严密，彻底修复了 8 的非整数倍 grid_size 下的 latent bug。

## Round 2 New Findings

### Finding 1: [HIGH] src/cuts/oracles/cutset_oracle.py:118 — Node-split capacity cuts 会被 cross-check 静默吞噬 (Phase 1.5+ Blocker)
**问题**: Phase 1.2 当前为 edge-only 模式 (`cell_capacity = _INF_CAP`) 表现正常。但在 Phase 1.5+ 开启 cell-capacity 时，若 min-cut 切在内部边 `v_in -> v_out`，`v_in` 可达而 `v_out` 不可达，`cell_v` 会被划入 `side_a`。此时 `cell_v` 与 `side_b` 的相邻细胞 `cell_w` 会在 `_cross_partition_edges` 中产生空间跨界边 `(cell_v, cell_w)`。但 `dinic_node_split_min_cut` 会跳过内部边，且因 `v_out` 不可达，不会输出 `(cell_v, cell_w)`。导致 `frozenset(result.cut_cell_edges) != recomputed_edges` 恒成立，静默丢弃所有合法的 node-capacity cuts。
**Fix**: Phase 1.5+ 需修改 cut schema 显式表达 node cuts，或调整 cross-check 逻辑以兼容内部节点被切断时的边界判定。

### Finding 2: [MEDIUM] src/cuts/families/cutset.py:149 — `cut_size` 校验假设 edge_capacity 恒为 1，破坏 Phase 1.5+ 权重图
**问题**: Validator 中直接使用 `len(current_cut_edges) != cert_cut_size` 进行校验。在 Phase 1.2 (`edge_capacity=1`) 时 `cut_capacity` 恰好等于边数，逻辑成立。但在 Phase 1.5+ 若引入非 1 权重边，`cut_capacity` 将不再等于 `len(edges)`，导致合法 cut 被 validator 误杀。Generator 端已正确使用 `cut_capacity` 填充 `cut_size`。
**Fix**: 建议将 cert schema 中的 `cut_size` 更名为 `cut_capacity`，并在 validator 中通过累加 `current_cut_edges` 的 capacity 来比对，而非单纯取 `len()`。

### Finding 3: [LOW] src/cuts/oracles/component_reach_oracle.py:136 — F4 generator 漏传 `blocking_facilities` 字段破坏 schema
**问题**: 根据 `ComponentReachCert` spec，`blocking_facilities` 是必填的 Tuple（非 `Optional`）。虽然 v1.1 validator 遵循 geometric 哲学不再校验具体 pose ID，但 generator 构造 `cert_payload_dict` 时完全省略了该 key。这会破坏 dataclass 的严格反序列化，可能导致下游 audit 工具或 Phase 1.5 causation splitter 崩溃。
**Fix**: 在 `cert_payload_dict` 中显式添加 `"blocking_facilities": []` 以满足 schema 契约。

## F4 component_reach Review
**BFS 连通性与边界**: `_bfs_component` 严格限制在 `free_cells` 内扩展，逻辑无懈可击。Validator 的重算机制 (`_validate_recomputed_components`) 极其健壮：如果 `free_cells` 在 replay 期间扩大导致 component 蔓延，即使 src/sink 仍未连通，旧的 cert 也会因 `current_src_comp != src_comp` 被判定为 unsound 并丢弃，完美契合 geometric cut 的 fail-closed 状态机语义。

**Separator 提取**: `extract_frontier_separator` 巧妙地通过 `blocked_for_separator` 过滤，只提取 `cell_owner` 和 `ghost_cells`，故意忽略了 `exterior_blocks`。这是极其正确的决定，因为 exterior blocks 是静态边界，永远不可能成为 causation split 的 target。Validator 的 `_validate_separator_cells` 也严格对齐了这一约束。

**Cert Schema Soundness**: v1.1 协议将 F4 纯粹化为 geometric cut，剥离了对 `blocking_facilities` ID 的强校验，这是架构上的巨大进步（避免了跨 permutation 的误杀）。`evaluate_geometric_component_reach` 作为 hot path，仅执行单次 BFS 且只要 `sink_cell not in current_src_comp` 就返回 True，这种 "evaluator 容忍 component 膨胀，validator 严格校验 cert 匹配" 的双层设计在性能和 Soundness 之间取得了绝佳平衡。

## Sanity (3 disproved hypotheses)

1. **Hypothesis**: Dinic 的 iterative DFS 在残差图存在环时可能陷入死循环。
   **Disproof**: DFS 严格受限于 level graph (`level[v] == level[u] + 1`)，由于 level 严格单调递增，拓扑上绝对不可能存在环。且 `iter_ptr` 保证了每条边在同一 phase 内最多被访问一次，彻底杜绝了死循环。
2. **Hypothesis**: `_has_patch_escape` 可能会在 partition 贴着网格边界 (grid boundary) 时误报 escape。
   **Disproof**: `outside_free` 被严格定义为 `free_cells - patch`。网格边界外的坐标根本不在 `free_cells` 集合中，因此 `(x+dx, y+dy) in outside_free` 永远为 False，只有真正泄漏到 patch 外的 free cell 才会触发拦截。
3. **Hypothesis**: F4 的 hot path `evaluate_geometric_component_reach` 在 component 扩大但仍未连通时返回 `True`，会导致 solver 使用 invalid proof。
   **Disproof**: Geometric cut 的本质是 "当前空间的连通性状态不可行"，不依赖具体的 separator ID。只要 src/sink 仍断开，该状态在几何上就是 infeasible 的，返回 `True` 引导 solver 回溯是绝对 Sound 的。严格的 cert 匹配交由 validator 在 full check 时处理。

## 下一步建议
1. **Phase 1.2 验收**: 当前代码对于 edge-only 模式已极其健壮，可直接合并 land。
2. **Phase 1.5+ 预警**: 重点关注 Finding 1 和 Finding 2，在引入 cell-capacity 和非 1 权重边之前，必须重构 `_cross_partition_edges` 的 cross-check 逻辑，否则会导致严重的 False Negative（漏发 cut）。
3. **性能优化 (Phase 1.3)**: F4 的 `evaluate_geometric_component_reach` 目前每次调用都是 $O(|Grid|)$ 的全量 BFS。在接入 CP-SAT propagator 的真 hot path (10K calls/sec) 前，必须按计划升级为 Incremental Connectivity (如带 rollback 的 Union-Find) 或加入 bitset dirty-flag 缓存。