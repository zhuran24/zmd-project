# Cut Family 3，名字 `port_exposure`。spec 标题写明 `Cut Family 3 — port_exposure`，mode 是 `literal`，family version 是 `v1.0`。证据：`SPEC:1`, `SPEC:3-6`（SPEC = C:/claude pj/zmd-pj/docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md）。
lifecycle 的 9-family map 也列出 `F3 port_exposure`，并在 `_FAMILY_MODE_MAP` 中把 `port_exposure` 映射为 `literal`。证据：`src/cuts/lifecycle.py:6-9`, `src/cuts/lifecycle.py:77-83`。
实现文件 docstring 写 `Family 3 port_exposure — production validator + literal-based evaluator`。证据：`src/cuts/families/port_exposure.py:1-3`（VAL）。

## proposition
spec 层数学命题可写成：对任意当前布局/状态中的 facility `A` 和 pose `pA`，若 `pA` 有一个必须暴露的 port `p_k` 位于 cell `c_k`、方向 `d_k`，令 `front = c_k + dir(d_k)`；如果 `front ∈ cell_owner` 或 `front ∉ free_cells`，则该配置 `INFEASIBLE`，原因是该 port 被 blocked。证据：facility port/front cell 定义在 `SPEC:10-12`；公式在 `SPEC:14-20`。

soundness 解释是：port 的 front cell 必须 belt-usable；如果 `cell_owner` 占用 front cell，就不能放 belt、不能从 port 通流，facility 无法供应/接收 commodity，因此 infeasible。证据：`SPEC:25-28`。

literal cut 的命题不是单纯"某个 ghost rect 不可行"，而是一个 pose/literal nogood：`cut.literals` 包含 facility A 的 pose `pA` 和占用 front cell 的 blocking facility B 的 pose/slot；当这两个 literal 同时出现在 state 中时违反 cut。证据：`SPEC:22-23`, `SPEC:51-75`, `SPEC:115-120`。

当前代码实际可执行判定只覆盖"front cell 被某个 blocking facility 占用"这一分支：validator 检查 `front_cell = port_cell + direction_offset(port_direction)`，检查 `state.cell_owner[front_cell] == (blocking_group, blocking_slot)`，再检查 blocking pose 的 `occupied_cells` 包含该 front cell。证据：`VAL:64-76`, `VAL:79-112`（VAL = src/cuts/families/port_exposure.py）。

spec 中的 `front ∉ free_cells` 广义分支没有作为 F3 validator 的独立分支实现；generator 对 out-of-grid、ghost、exterior front 直接 skip，对没有 `cell_owner` 的 front 也返回 no cut。证据：`src/cuts/oracles/port_exposure_oracle.py:205-215`（ORACLE）。spec 也说 ghost-occluded front v1.0 不发 cut，交给 master ghost constraint。证据：`SPEC:165-166`。

## argument_type
几何(区间/圆/线段)、集合覆盖 —— 具体是离散网格邻接几何论证 + 有限 multiset/命题式 nogood 论证。

当前 F3 的核心是离散几何/网格邻接论证：port cell 加 N/S/E/W offset 得到 front cell，front cell 若被占用则 port 不暴露。证据：`SPEC:10-20`, `SPEC:25-28`, `HELP:56-64`, `VAL:64-76`, `VAL:87-112`。

同时有有限 multiset/propositional nogood 论证：literal-based family 通过 `(group, pose)` 多重集 subset match 判断 cut 是否被当前 state 违反；slot index 在评价中是匿名的。证据：`LIFE:1014-1027`, `LIFE:1060-1070`, `LIFE:1073-1085`, `LIFE:1113-1114`。

当前 validator 没用 Hall、max-flow min-cut、Farkas/LP dual 来证明 F3；它的可执行 checks 是上述四个几何/binding/multiset/port-existence 函数。证据：`VAL:185-190`。

spec/pseudocode 提到 `boundary_constraints` 和 `active_port_witness_b64`，这属于 per-(cell, dir) net-flow equality / boundary equality 方向；但当前 oracle 把 witness defer 到 Phase 1.5+，validator 不检查。证据：`SPEC:46-48`, `SPEC:144-147`, `ORACLE:14-17`, `ORACLE:294-296`。boundary_constraints.py 文件描述的 equality 是每个 boundary key 上 `sum λ*(input-output)==0`。证据：`C:/claude pj/zmd-pj/docs/research/cand_c_column_generation_phase2_20260521/boundary_constraints.py:9-18`, `:92-99`, `:102-133`（BOUND，注意此文件路径在 docs/research 下，不在 src/ 生产路径）。

## formalization_needs
抽象层可表达的核心定理 1：在有限二维 grid 上，若 selected pose `pA` 有 active/required port `(c,d)`，`front = c + offset(d)`，且另一个 selected pose `pB` 的 occupied cells 包含 `front`，并且项目语义规定 port front 必须 free/belt-usable，则该 placement 违反 port exposure 约束。所需数学对象是 finite grid、direction enum、offset、finite set membership、port relation、occupied relation。证据：`SPEC:10-20`, `SPEC:25-28`, `HELP:56-64`, `VAL:64-76`, `VAL:139-158`, `VAL:106-112`。

抽象层可表达的核心定理 2：literal cut 是有限 multiset nogood；若 cut literal multiset `{(A,pA),(B,pB)}` 是当前 selected pose multiset 的子多重集，则 cut evaluator 返回 violated。所需支持是 finite maps/counters/multisets，不需要 Hall/max-flow/LP。证据：`SPEC:22-23`, `SPEC:115-120`, `LIFE:1014-1027`, `LIFE:1045-1070`, `LIFE:1113-1114`。

与项目具体几何/数据结构强绑定的部分：`candidate_placements` 如何由 canonical facility geometry/rotation/translation 得到；group_id 如何映射 facility_type；port cells 和 occupied cells 是否忠实；`cell_owner` 是否忠实于 selected poses；direction convention 是否与全项目一致。这些不是纯 multiset 定理本身，而是项目模型形式化前提。证据：`HELP:1-5`, `HELP:7-19`, `HELP:128-171`, `src/cuts/helpers/canonical_rules.py:25-33`, `HELP:56-58`, `LIFE:405-427`。

若只形式化当前 v1.0 validator 所覆盖的 soundness 核心，不需要 LP dual、Farkas、max-flow min-cut 或 Hall 定理；当前可执行 validator 只做 geometry/binding/literal/port-existence checks。证据：`VAL:185-190`。

若把 spec 中 `active_port_witness_b64` / `boundary_constraints` 那条路线也纳入形式化，则需要形式化 per-boundary-key linear equality/net-flow equality，甚至 RMP/LP solver witness 的语义；boundary_constraints.py 把该约束写成每个 boundary slot 上 input-output 净流为零，并有 dual collection。证据：`SPEC:46-48`, `SPEC:144-147`, `BOUND:9-18`, `BOUND:92-99`, `BOUND:102-160`。但当前 F3 code 把这部分 deferred/placeholder。证据：`ORACLE:14-17`, `ORACLE:294-296`。

若要证明 cut 可跨 replay/状态重用，还需要形式化或信任 lifecycle scope：source digest、ghost/exterior hash、artifact hash、oracle version、active assumptions；这是工程 replay soundness，而不是 port-blocked 几何命题本身。证据：`LIFE:175-188`, `LIFE:941-984`。

若 theorem 要覆盖 spec 的 `front ∉ free_cells` 广义分支，还需要形式化 `free_cells`、ghost/exterior/out-of-grid 与 master constraints 的关系；当前实现没有把该分支作为 F3 cut 验证，而是 skip/交给别处。证据：`SPEC:17-20`, `SPEC:165-166`, `ORACLE:205-215`。

## latent_issues
spec 命题覆盖 `front_cell ∈ cell_owner OR ∉ free_cells`，但当前 generator/validator 只实际发出并验证 `cell_owner` blocker 分支；ghost/exterior/out-of-grid skip，front 没 owner 也 skip。证据：`SPEC:17-20`, `ORACLE:205-215`, `VAL:87-112`。

spec cert schema/pseudocode 包含并验证 `active_port_witness_b64`，当前 code 只要求字段存在，不解析、不验证，generator 写 `None`。证据：`SPEC:46-48`, `SPEC:144-147`, `CERT:49-58`, `ORACLE:14-17`, `ORACLE:294-296`, `VAL:175-190`。

spec 的 open question 承认 active port subset 未解决：多 port facility 中只有部分 active 时 cut 是否覆盖，v1.0 假设 all ports active。证据：`SPEC:161-164`。

spec 的 open question 还承认 ghost-occluded front 不发 cut，并说 Phase 1 验 trigger 路径。证据：`SPEC:165-166`。当前 generator 也 skip ghost/exterior/out-of-grid。证据：`ORACLE:205-211`。

spec generator 伪代码从 `master_solution.placed_facility_poses` 遍历；当前 generator 明确 `master_solution` unused/deferred，并从 `state.cell_owner` derive targets。证据：`SPEC:84-90`, `ORACLE:80-103`, `ORACLE:118-128`。

spec validator 伪代码从 `canonical_rules_facility_ports` 查 port；当前 validator `del canonical_rules`，实际从 `candidate_placements` pose 层查 port。证据：`SPEC:131-133`, `VAL:161-168`, `HELP:1-5`, `HELP:174-192`。

spec 伪代码里 `blocking_pose_id = state.groups[blocking[0]].selected_poses[blocking[1]][1]` 暗示 selected_poses 元素像 tuple；当前 lifecycle 明确 `selected_poses` 是 `List[PoseId]`，generator 也直接取 `selected_poses[blocking_slot]`。证据：`SPEC:97-105`, `LIFE:381-388`, `ORACLE:224-230`。

direction primitive 仍有共享几何模型风险：helper 注释说 N/S 与 canonical DIR_DELTA 相反，shared primitives 前 no cert。证据：`HELP:56-58`。

lifecycle 的 Step 8 apply-to-master 仍未实现。证据：`LIFE:1121-1126`。

replay 文件顶部注释说"Family validators currently wired: region_capacity"，并说 Phase 1.1+ adds port_exposure；但同一文件当前 `FAMILY_VALIDATORS` 表已经注册 `port_exposure`。这是注释与代码状态不一致。证据：`REPLAY:17-22`, `REPLAY:57-72`。
