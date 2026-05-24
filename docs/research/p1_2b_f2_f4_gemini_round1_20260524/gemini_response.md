## Round 1 Overall Verdict
**CONCERN** (Borderline NOT_GO due to a hidden recursion crash in Dinic, but mathematically sound for Phase 1.2 edge-only mode).

## Verify 我提示的 Gap A/B

- **Gap A (float demand)**: **CONFIRMED**. `commodity_demands.json` 包含 float (如 `buckwheat: 5.5`)。不仅 F2 generator (`cutset_oracle.py:112`) 的 `_is_strict_positive_int` 会 silently skip 这些 commodity，**F2 Validator** (`cutset.py:22` `_parse_strict_int`) 也强校验 `isinstance(value, int)`。如果强行传入 float，整个 F2 lifecycle 会崩溃报 `schema_err`。
  - *Fix 建议*: 必须在数据加载/预处理层 (Preprocessing) 将所有 demand 和 capacity 统一 scale 为整数（例如乘以 100 或 `math.ceil`，取决于业务精度要求）。Dinic 和 CP-SAT 都不支持非整数流。

- **Gap B (commodity_routes 无 prod fill)**: **CONFIRMED**. 生产代码中 `state.commodity_routes` 永远为 `None`，F2/F4 generator 的 fail-closed gate (`if state.commodity_routes is None: return []`) 会 100% 拦截，当前不会发出任何 cut。
  - *Fix 时机建议*: 留到 Phase 1.5+ wiring 阶段。目前的 gate 完美起到了隔离作用，不会污染 Phase 1.2 的其他测试。

---

## New findings (Round 1 catch)

### 1. [SEVERITY: BLOCKER / HIGH] `dinic_node_split.py:171` — Dinic DFS 递归深度超限导致长路径静默失败 (False Negative)
- **问题陈述**: `_dfs_blocking_flow` 是递归实现的。Dinic 的 DFS 深度等于 level graph 中的最长路径。在 70x70 的网格中，源汇之间的最短路径（level 深度）可以轻易超过 1000（例如绕开障碍物的蛇形 belt）。Python 默认的 `sys.getrecursionlimit()` 是 1000。当路径长度 > 1000 时，DFS 会抛出 `RecursionError`。
- **Reproduce**: 构造一个 src 和 sink 曼哈顿距离或迷宫连通距离 > 1000 的 state。`_dfs_blocking_flow` 崩溃，被 `cutset_oracle.py:118` 的 `except Exception` 宽泛捕获，返回 `None`。本该发出的 F2 cut 被静默吞噬。
- **建议 fix**: 将 `_dfs_blocking_flow` 改写为显式栈 (explicit stack) 的迭代版本，或者在 solver 初始化时显式 `sys.setrecursionlimit(10000)`（不推荐，迭代器更稳健）。

### 2. [SEVERITY: HIGH] `cutset_oracle.py:127` — F2 Schema 无法表达 Phase 1.5+ 的 Cell Capacity 瓶颈 (Architectural Limitation)
- **问题陈述**: 当前 Phase 1.2 是 edge-only 模式 (`cell_capacity=_INF_CAP`)，没有问题。但代码已经为 Phase 1.5+ 的 node-split 预留了逻辑。如果未来 `cell_capacity` 为有限值且成为 min-cut 瓶颈，Dinic 会切断 internal edge (`v_in -> v_out`)。
- **Reproduce**: `dinic_node_split.py:249` 会跳过内部边 (`if u_idx == v_idx: continue`)。该 cell 会被划入 `side_a`。随后 `_cross_partition_edges` 会提取该 cell 与 `side_b` 之间的**相邻边**。最后 `cutset_oracle.py:127` 的交叉校验 `frozenset(result.cut_cell_edges) != recomputed_edges` 必然失败，导致 fail-closed 返回 `None`。
- **建议 fix**: 记录此架构限制。F2 的数学定义 `cut(A, B)` 是一个纯 Edge Cut 模型。如果要支持 Cell Capacity (Vertex Cut)，F2 的 Cert Schema 必须升级以支持混合割（或将 cell 拆分暴露到 schema 中），否则 Phase 1.5+ 遇到 cell 瓶颈时将永远无法生成 cut。

### 3. [SEVERITY: LOW] `cutset_oracle.py:46` vs `cutset.py:42` — Bitset 编解码的 Padding 长度计算不一致 (Latent Bug)
- **问题陈述**: Generator 编码时使用 `n_bytes = (grid_size * grid_size + 7) // 8`。Validator 解码时使用 `expected_len = grid_size * grid_size // 8 + 1`。
- **Reproduce**: 对于 70x70 (4900)，两者碰巧都等于 613。但如果未来 `grid_size` 变为 8 的倍数（例如 64x64 = 4096），编码器会生成 `(4096+7)//8 = 512` 字节，而解码器会期待 `4096//8 + 1 = 513` 字节，导致 `ValueError: bitset length mismatch`。
- **建议 fix**: 将 Validator 中的长度计算统一改为 `(grid_size * grid_size + 7) // 8`。

---

## Sanity Arguments (Disproved Hypotheses)

**1. Hypothesis: F2 `_has_patch_escape` 逻辑在 Generator 中是死代码，因为 `side_a | side_b` 永远等于 `free_cells`，无法起到校验作用。**
- **Disproof**: 证明 src 已 cover。在 Phase 1.2 中，Dinic 确实在整个 `free_cells` 上运行，`patch == free_cells`，`outside_free` 为空，函数必然返回 False。这是数学上正确的（整个网格不可能向外 escape）。该函数是为 Phase 1.5+ 预留的：当 PCR-CUT 仅在局部的 patch (subset of `free_cells`) 上运行时，`side_a | side_b` 将严格小于 `free_cells`，此时 escape 校验将发挥关键的 fail-closed 作用。

**2. Hypothesis: F4 `extract_frontier_separator` 漏掉了 `exterior_blocks`，导致提取的 separator 不完整，可能破坏 soundness。**
- **Disproof**: 证明 src 已 cover。F4 Validator (`component_reach.py:101`) 明确要求 `separator_cells` **只能**包含 `cell_owner` 或 `ghost_cells`，如果包含 `exterior_blocks` 会直接返回 `unsound`。此外，Validator 并不依赖 `separator_cells` 来证明不连通（它会独立重跑 BFS）。因此，Generator 故意过滤掉 `exterior_blocks` 既是 Schema 的硬性要求，也完全不影响数学 Soundness。

**3. Hypothesis: Dinic 建图时对相邻 Cell 添加了双向边，可能导致残差网络中的反向边被 double-count。**
- **Disproof**: 证明 src 已 cover。`_build_node_split_graph` (line 134) 使用了 `seen_pairs` 集合，确保每对相邻的 free cell 只被处理一次。随后它显式添加了两条有向边（`u_out -> v_in` 和 `v_out -> u_in`），每条边都有自己独立的 capacity 和残差反向边。这完美契合了网格图的双向通行特性，没有任何 double-count。

---

## 建议下一步 (Round 2 重点 / Phase 1.5+ defer)

1. **Round 2 必须修复**: 将 `_dfs_blocking_flow` 改为迭代式，消除 `RecursionError` 隐患。
2. **Phase 1.5+ Defer**: 
   - 修复 Gap A（在数据加载层将 float demand 缩放为 int）。
   - 修复 Gap B（在 Benders master loop 中填充 `commodity_routes`）。
   - 重新评估 F2 Schema 对 Cell Capacity (Vertex Cut) 的表达能力。