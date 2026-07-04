# F4 `component_reach`。Spec 标题为 "Cut Family 4 — component_reach"，模式是 geometric，版本 v1.1；实现文件 docstring 也写 "Family 4 component_reach"。证据：`docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md:1-6`，`src/cuts/families/component_reach.py:1-12`。生命周期表把 `component_reach` 标为 F4/geometric。证据：`src/cuts/lifecycle.py:65-84`。

## proposition
对任意当前 `BState`，令 70x70 grid 上的 `free_cells = all_cells - ghost_cells - exterior_blocks - cell_owner.keys()`；在 `free_cells` 上按四邻接建立 belt-traversable 图。若存在某个 commodity `c`，其 registry 中的 `src_c`/`sink_c` 分别等于证书 `src_cell`/`sink_cell`，且二者都在当前 `free_cells`，但从 `src_c` 做 BFS 不可达 `sink_c`，则该 commodity 不存在 belt path，因此当前布局不可行。Spec 的数学定义是 "BFS on state.free_cells from src_c 不可达 sink_c => INFEASIBLE"，soundness proof 是 component 唯一、两个不同 component 之间无 belt path。证据：`04_component_reach.md:17-26`，`04_component_reach.md:34-40`，`src/cuts/families/cutset.py:84-96`，`src/cuts/families/component_reach.py:34-47`，`src/cuts/families/component_reach.py:132-155`。

argument_type 补充说明（数学分类，非本字段但供参照）：核心是图可达性/连通分量唯一性；底层图来自 70x70 grid 的四邻接，所以也有很轻的离散几何/网格邻接定义。不是 Hall、最大流最小割、LP 对偶。Spec 明确把 F4 描述为单 commodity binary reachability，并与 F2 multi-commodity min-cut capacity 区分；helper 文档也写 F4 single commodity 只做 src→sink BFS reachability、no max-flow。证据：`04_component_reach.md:28-32`，`src/cuts/helpers/dinic_node_split.py:1-18`。

## argument_type
图可达性(图论可达性/连通分量唯一性为主，是本 family 的核心，与 family 名 component_reach 相符)｜几何(极轻量，仅体现为70x70网格四邻接的离散几何邻接定义)。不属于计数/鸽笼、Hall匹配、最大流最小割、LP对偶/Farkas、序/置换、集合覆盖。Spec 明确把 F4 描述为单 commodity binary reachability，并与 F2 multi-commodity min-cut capacity 区分；helper 文档也写 F4 single commodity 只做 src→sink BFS reachability、no max-flow。证据：`04_component_reach.md:28-32`，`src/cuts/helpers/dinic_node_split.py:1-18`。

## formalization_needs
抽象层面需要有限图论：有限 vertex set、四邻接边、reachable/path、connected component 唯一性，以及"若 sink 不在 src reachable set，则不存在 src-sink path"的定理（即 BFS 可达集的补集与该可达集不连通这一图论标准事实）。F4 核心可先对任意有限无向图证明，再实例化到 grid/free_cells。证据：`04_component_reach.md:34-37`，`src/cuts/families/component_reach.py:34-47`。

绑定到具体工程语义、必须具体计算的部分包括：70x70 `Cell` bounds 与坐标合法性、`free_cells = grid - ghost - exterior - occupied` 的具体集合运算、commodity registry 的 src/sink 真实性绑定（即证书里的 src/sink 确实对应某条真实 commodity route）、bitset/base64/JSON 编解码到 set 的正确性（含 `_decode_bitset` 的 padding 公式细节）。证据：`src/cuts/families/cutset.py:50-96`，`src/cuts/families/component_reach.py:132-155`，`src/cuts/cert_schema.py:131-174`。

不需要 Hall 定理、最大流最小割定理、LP对偶/Farkas 库来证明 F4 核心命题本身；这些只会在证明 generator/helper 的 F2 Dinic（最大流）部分时才需要。F4 helper 明写"src→sink BFS reachability only, no max-flow"。证据：`src/cuts/helpers/dinic_node_split.py:15-18`，`04_component_reach.md:28-32`。

## latent_issues
Spec open questions 包括 multi-component 是否合并 cut、cell_owner causation split 是否拆 sub-kind、与 F8 power_grid_reach 的 schema/图区别。证据：`04_component_reach.md:168-175`。

实现 docstring 仍列 Phase 1.5+ 扩展：wrap D2 separator generator、ghost-cause vs cell_owner-cause sub-kind、multi-commodity reachability matrix（表明当前实现是这些扩展之前的版本）。证据：`src/cuts/families/component_reach.py:14-18`。

Hot-path 性能 deferred：当前 BFS 在 post-attach 每 cut 一次可接受；若 Phase 1.3 接 CP-SAT propagator 10K calls/sec，需要 incremental connectivity，否则量级退化。证据：`src/cuts/families/component_reach.py:192-203`。

Spec schema 写了 `witness_path_attempt` debug 字段，伪 generator 也设置 `None`；当前 `cert_schema` 的 allowed fields 不含该字段，unknown field 会被拒绝，当前 oracle 也不输出它（spec 与实现存在字段不一致）。证据：`04_component_reach.md:56-58`，`04_component_reach.md:100-109`，`src/cuts/cert_schema.py:59-68`，`src/cuts/cert_schema.py:161-166`，`src/cuts/oracles/component_reach_oracle.py:149-164`。

`_decode_bitset` 注释记录 padding 公式曾有 latent bug；70x70 下两个公式都给 613 bytes 结果相同、问题被掩盖，但 grid size 为 8 的倍数时问题是 latent（潜伏未触发）。证据：`src/cuts/families/cutset.py:63-81`。

另外（PR2/lifecycle 层面已知记录，非本次新查但与本 family 接线相关）：Step 8 apply-to-master 对所有 family（含 F4）均未实现，`raise NotImplementedError`，属于生产未接线的已知缺口。证据：`src/cuts/lifecycle.py:1121-1126`。
