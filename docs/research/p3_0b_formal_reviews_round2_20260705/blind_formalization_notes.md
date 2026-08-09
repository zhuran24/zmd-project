# ZMD 盲形式化说明

## 读前目标清单（26 条）

我按 `CONTEXT.md` 的目标对象拆成 26 条：六个当前实现 family 各两条（bound/fire）共 12 条，F3 两条，F5 设计稿两条，frontier 一条，TP7-S/selected-solution nogood 边界九条。`survey_completeness.md` 已读，它明确说 family completeness 仍 open、没有不可行类 exhaustive partition，因此没有把“F1-F9 完备性”写成定理。`survey_f8_power_grid_reach.md` 也已读；但 `CONTEXT.md` 第 1 项只点名 F9、F1、F7、F4、F6、F2 六个 current-core family，所以 F8 没作为本次 26 条目标之一。

1. `F9_density_bound`：对应 `survey_f9_density_envelope.md / proposition` 的 window safe upper bound，`owned_g∩W ⊆ W\blocked ⇒ |owned_g∩W| ≤ |W\blocked|`。
2. `F9_density_fire`：同一命题的逆否形态，witness area 超过 safe bound 时不能满足 well-formed owner 语义。
3. `F1_region_capacity_bound`：对应 `survey_f1_region_capacity.md / proposition`，mandatory demand 的占用 cell 总数受 `R\blocked` 容量上界约束。
4. `F1_region_capacity_fire`：同一命题的 fire 形态，`Σ demand·cells_per_pose > cap_R` 时不存在 disjoint、避 blocked、落在 region 内的 mandatory placement。
5. `F7_power_hitting_set_bound`：对应 `survey_f7_power_hitting_set.md / proposition`，ghost-only free scope 下 CoverSet 为空，未来 free set 只会缩小时 CoverSet 仍为空，容量上界为 0。
6. `F7_power_hitting_set_fire`：同一命题的 single-literal fire 形态；需要供电的 pose 必须有 covering pole anchor，而 full 与 ghost-only CoverSet 均为空则无合法 powered placement。
7. `F4_component_reach_bound`：对应 `survey_f4_component_reach.md / proposition`，若 BFS/reachability 断言 src 不可达 sink，则合法 path witness 集合 cardinality 上界为 0。
8. `F4_component_reach_fire`：同一命题的 fire 形态，不可达时不存在该 commodity 的 belt path。
9. `F6_shape_packing_interval_bound`：对应 `survey_f6_shape_packing_hall.md / proposition` 的当前受限版本，`1×L` rigid poses 在 baseline unblocked intervals 中的数量受 `Σ floor(len(I)/L)` 上界约束。
10. `F6_shape_packing_hall_fire`：同一命题的 fire 形态，`C_R < d_R ≤ D - C_R'` 与两侧容量上界一起矛盾。
11. `F2_cutset_bound`：对应 `survey_f2_cutset.md / proposition`，edge-capacity-one 且 edge-disjoint 的跨 A/B 路由可注入 cut edges，所以 route 数不超过 cut size。
12. `F2_cutset_fire`：同一命题的 fire 形态，总 unit demand 大于 cut size 时不存在满足 demand 的 routing。
13. `F3_blocked_port_infeasible`：对应 `survey_f3_port_exposure.md / proposition` 的 blocked front-cell 分支，并显式加入 all-ports-active 与 direction primitive 一致性前提。
14. `F3_two_literal_nogood_sound`：对应 F3 literal cut / multiset evaluator 语义，target pose 与 blocker pose 两个 literal 同时出现时，nogood sound。
15. `F5_orbit_cut_order_composite_safe`：对应 `design_excerpts.md` F5 轨道提升设计稿 v1/v2 §2.4，order 保每个 orbit 至少一个代表，G-invariant cut 删除整类，两者复合不删光未被证明 infeasible 的合法类。
16. `F5_non_invariant_cut_order_counterexample`：对应同节“反方向陷阱”，用 two-point orbit 形式化“非 G-invariant cut + order 可删光合法类”的反例形态。
17. `frontier_pruning_preserves_lex_optimum`：对应 `design_excerpts.md / 搜索目标语义` 与 §3c 迁移规则，只在当前 schema、且手中已有 certified witness 时，跳过 lex 不优于 witness 的候选不改变最优值。
18. `TP7_T1_periodic_average_necessary`：对应 `design_excerpts.md` TP7-S T1，离散周期运行的平均流满足非终端节点守恒。
19. `TP7_T2_periodic_average_necessary`：对应 TP7-S T2，selected physical state 的跨商品 through 不超过 belt capacity。
20. `TP7_T3_periodic_average_necessary`：对应 TP7-S T3，port throughput 有上下界，route-visible port 等于 incident terminal arc flow，未知/重复/无 incident selected state 的正吞吐被拒绝。
21. `TP7_T4_periodic_average_necessary`：对应 TP7-S T4，machine 的输入/输出端口速率与 `u[i]·qty/tpc_i` 耦合。
22. `TP7_T5_periodic_average_necessary`：对应 TP7-S T5，production target rate 是精确等式，而不是“至少”或可溢出。
23. `TP7_T6_periodic_average_necessary`：对应 TP7-S T6，routing-free sink 平衡，外部注入仅允许来自 external boundary source slot。
24. `TP7_full_eq_key_excluded_iff`：对应 `design_excerpts.md` §3b 的完整 0/1 等式键，完整键 nogood 的排除集恰好是 recorded assignment 本身。
25. `TP7_full_eq_key_sound`：对应 §3b 的 selected-solution nogood soundness，若 TP7-S/Farkas 只证明固定图 S infeasible，则完整等式键只剪掉 S，不剪 S 的超集。
26. `TP7_selected_only_nogood_overcuts_toy`：对应 §3b 玩具反例，一条半容量路不够，添加并行路可行；只禁选中集式 nogood 会把可行超集一起剪掉。

## 关键抽象选择

Lean 文件使用 `import Mathlib`，但把几何、parser、digest、scope replay、candidate registry 绑定都抽象成谓词或参数。这是有意的：survey 多次把 70×70、bitset/base64、SHA、JSON strictness、canonical_rules lookup 归为工程绑定层，而不是可一次性证明的数学核心。数学层统一用有限集合、自然数 cardinality、有限图 reachability、注入到 cut edges、以及有理数线性等式/不等式表示。

六个 family 的 bound/fire 没按名称偷换成重定理。F6 没用 Hall theorem，而是 `1×L` 区间 floor-sum；F2 虽然文档提到 Menger/min-cut，但 statement 采用更初等的“edge-disjoint route crossEdge 注入 cutEdges”形态；F7 只做 empty CoverSet，不做 min hitting set；F9 只做 safe area upper bound，不恢复 quarantined tight-K。

TP7-S 的 T1–T6 写成“离散周期运行平均语义 ⇒ 对应约束”的必要性 lifting theorem。材料没有给离散调度语义的 Lean 级定义，所以 `DiscreteRun`、`AverageWitness` 和 `hSemantics` 显式作为前提，而不是脑补出一个游戏运行模型。

## 最容易写歪的地方及处理

第一，F3 有两个未决前提：all ports active 与方向原语 N/S 约定风险。我没有把它们藏进 `Legal`，而是在 `F3_blocked_port_infeasible` 中显式放入 `ActivePort` 和 `DirectionPrimitiveMatchesProjectNS`。同时，current validator 只覆盖 front cell 被 `cell_owner` blocker 占用的分支；ghost/exterior/out-of-grid 的 broad `front ∉ free_cells` 在说明里保留为边界，不擅自扩成 F3 production theorem。

第二，F7/F8 power 语义存在旧欧氏 coverage 与 active certified 12×12 square stencil 的分裂。F7 statement 只依赖抽象 `CoverSet` 和单调性，不选择具体距离模型；F8 survey 已读，但不纳入本次 26 条，因为 `CONTEXT.md` 的 current-core family 清单没有点名 F8。

第三，TP7 selected-solution nogood 的关键不是“有 Farkas 证书所以能禁超集”，而是恰好相反：Farkas 只证明固定完整图 S 不可行。Lean 中 `FullEqKeyConstraint` 是完整 mismatch-sum，排除集 iff `cand = key`；`SelectedOnlyKeyExcluded` 的 toy theorem 则展示 selected-only 子句会排除 `halfRoute=true, parallelRoute=true` 这个可行超集。

## 机检状态

当前沙盒没有 `lean`/`lake` 可执行文件，依赖包中也没有 Lean 工具链，因此我无法在本地实际跑 Lean 4/mathlib v4.31.0。文件按 Lean 4 + mathlib 风格书写，26 个目标定理均允许 `sorry`；其中 theorem statement 是本交付的主体。
