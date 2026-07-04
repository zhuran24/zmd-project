# F2 / cutset（两个名字对应同一 family）：
- 文档正式标题 `Cut Family 2 — cutset`，mode 是 `geometric`，family_version `v1.0`：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:1-5。
- lifecycle 的 9-family 表把 `F2` 映射到 `cutset`，`CutFamily` literal 中 `"cutset"` 注释为 `F2 (geometric)`：src/cuts/lifecycle.py:6-9、src/cuts/lifecycle.py:65-68。
- 代码实现 docstring 也称 `Family 2 cutset`，实现 `cut_family_specs/02_cutset.md v1.0`：src/cuts/families/cutset.py:1-3。
- 当前 oracle 常量 `ORACLE_NAME = "cutset_v1"`、`CERT_KIND = "menger_min_cut"`，构造出的 Cut 使用 `family="cutset"`：src/cuts/oracles/cutset_oracle.py:56-60、src/cuts/oracles/cutset_oracle.py:215-229。

## proposition
设 G=(V,E) 是 70x70 free-cell 网格上的 4-neighbor belt graph，V 是 free cells，E 是相邻 free cells 间的 belt edge——spec 明确这么定义：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:14-15。给定不相交的 A,B 分割，令 cut(A,B) 为连接 A/B 的边数，Menger/min-cut 给出跨分割 edge-disjoint path 数的上限：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:17-19。

抽象命题可写成：对所有当前状态诱导的 free-cell 图 G=(V,E)，对所有互不相交的 A,B ⊆ V，令 P=A∪B。若 P 对外无 4-neighbor free-cell escape，且对某个非空 commodity 集合 C 中每个 commodity，src_c 与 sink_c 位于 A/B 两侧，并且 Σ_{c∈C} demand(c) > |{e∈E : e connects A and B}|，则不存在满足这些 commodity demand 的 edge-capacity-1、edge-disjoint routing。

文档把该条件写成 `sum demand > cut(A,B) ⇒ INFEASIBLE`：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:21-30；validator 额外把"patch 对外无 escape"作为当前实现所需的封闭性条件：src/cuts/families/cutset.py:117-127、src/cuts/families/cutset.py:169-183。

## argument_type
最大流最小割(Menger定理) + 几何(网格/邻接/分割) 的组合：

- 数学核心是 Menger / max-flow min-cut 型论证：spec 标题为 `Menger's theorem`，写明 `max edge-disjoint paths from A to B = min edge cut size`，因此 `cut size < demand → INFEASIBLE`：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:45-51。
- 当前实现还包含离散几何/图论检查：70x70 网格、4-neighbor Manhattan adjacency、free-cell partition、patch enclosure：src/cuts/families/cutset.py:50-60、src/cuts/families/cutset.py:99-127。
- 当前 generator/helper 使用 Dinic max-flow/min-cut；helper docstring 写明 node-split 图、super-source/sink、Dinic solve，结果 invariant 是 `max_flow_value == cut_capacity`：src/cuts/helpers/dinic_node_split.py:1-28、src/cuts/helpers/dinic_node_split.py:316-326、src/cuts/helpers/dinic_node_split.py:335-411。
- 当前 validator 的 soundness 检查不依赖 LP/Farkas/Hall；LP dual witness 是未来项：src/cuts/families/cutset.py:11-15、src/cuts/oracles/cutset_oracle.py:16-20。

## formalization_needs
- 抽象层面需要一个有限图上的 cut/edge-disjoint path 定理：文档核心是 Menger/max-flow min-cut，当前命题只需"任何 A-B path 必跨 δ(A,B)，若 demand 超过 cut edge 容量则不可行"的图论容量论证：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:45-51。
- 若形式化当前 validator，而不是 generator，需要把以下机械检查映射到 Lean 中的有限集合/有限图事实：bitset 解码成 A,B、free-cell 计算、A/B disjoint、A∪B free/enclosed、cross edges 枚举等：src/cuts/families/cutset.py:63-81、src/cuts/families/cutset.py:84-127、src/cuts/families/cutset.py:169-202。
- 与项目设定绑定的部分包括 70x70 坐标范围、Manhattan 4-neighbor、ghost_cells/exterior_blocks/cell_owner 定义 free_cells、commodity registry schema：src/cuts/families/cutset.py:50-60、src/cuts/families/cutset.py:84-96、src/cuts/lifecycle.py:428-435。
- 可以相对抽象化的部分是 finite graph 上的 A/B cut 容量与 demand 比较；spec 的 G=(V,E)、partition、cut(A,B)、demand > cut(A,B) 都不是 70x70 专有：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:14-30。
- 如果要形式化 generator 的 Dinic 结果，需要额外证明或信任 Dinic/max-flow implementation 与 min-cut extraction；helper 明确有 residual graph、Dinic、reachable min-cut、cut extraction 逻辑：src/cuts/helpers/dinic_node_split.py:104-132、src/cuts/helpers/dinic_node_split.py:287-313、src/cuts/helpers/dinic_node_split.py:335-411。但 validator 当前不需要证明 Dinic 正确性，因为它重算证书给出的 partition cross edges，而非信任 generator 的 max-flow 值：src/cuts/families/cutset.py:186-202。
- 当前不需要 Hall 定理或 LP/Farkas 库来覆盖已实现 validator core；LP dual witness 被列为未来项，当前 cutset cert schema 也没有 witness 字段：src/cuts/cert_schema.py:40-48、src/cuts/oracles/cutset_oracle.py:16-20、docs/项目说明/10_phase_1_5_plan.md:84-87。

## latent_issues
- spec §9 自列 open questions：patch boundary selection、multi-commodity vertex split graph 与 cut_edges 表达力差异、cell_owner 挤压 cut size 时多 literal cut 形式：docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:175-180。
- 实现 docstring 自列 Phase 1.5+ 扩展：PCR-CUT patch extraction、multi-commodity vertex split、max-flow LP witness algebraic check：src/cuts/families/cutset.py:11-15。
- `_decode_bitset` 注释承认旧 padding formula 有 latent bug，在 grid size 是 8 的倍数时会暴露；70x70 下两种公式同为 613：src/cuts/families/cutset.py:65-69。
- `_has_patch_escape` 注释说明若 patch 外 free cell 不在 partition 但流可绕过，会导致 cut_size 假证；validator 当前对此 fail-closed：src/cuts/families/cutset.py:121-127。
- evaluator docstring 记录过一个已修复问题：旧版只重算 cut_edges、漏验 enclosure，状态变化后可能 validator unsound 但 evaluator 仍 True；当前要求同步验 (A∪B) ⊆ free + enclosure：src/cuts/families/cutset.py:322-327。
- replay.py 的注释仍说 "F2 oracle is stub"，但当前 cutset_oracle.py 已实现 Dinic generator；这是文档/注释漂移：src/cuts/replay.py:57-60、src/cuts/oracles/cutset_oracle.py:1-20。
- lifecycle 里 `step_8_apply_to_master` 仍是 NotImplementedError，这是集成层未完成，不是 F2 数学命题本身：src/cuts/lifecycle.py:1121-1126。
- 项目 open questions 仍把"F2 patch_routing_core 复用 sound 性"列为 P1，要求 Phase 1.5+ F2 oracle 实施时复 verify：docs/项目说明/05_open_questions.md:132-142、docs/项目说明/05_open_questions.md:545-550。
