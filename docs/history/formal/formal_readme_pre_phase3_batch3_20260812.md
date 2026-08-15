# formal/ — 范式定理的机器检查层（Lean 4）

> 注：本文各处「待独立复审 / 待外审 / 送审」均指 formal 形式化产物自身的质量复审队列（P3.0 轴 A），与 P1.2 收口外审无关——P1.2 已于 2026-07-07 由 owner_manual_decision 正式 CLOSED。

**性质**：研究层前瞻投资（P3.0 头启动，对应 open question Q14）。**不进认证 TCB、
不改变任何 gate 的验收标准**——项目政策"数学 sound 用工程 verify"（`16_workflow_review.md`
§6.4）继续有效；本目录是给该政策将来 reconsider 时的地基，锁面未动。
配套设计稿：`docs/research/p3_0_formal_verification_head_start_design_v1.md`（v2）。
首批陈述已过一轮独立审查（盲形式化对拼 + 陈述保真对抗审，归档见设计稿 §7）；
`DesignStatements.lean` 的陈述即盲形式化交付原文（见下）。

## 构建

```
# 依赖: elan (scoop install elan);工具链钉在 lean-toolchain (v4.31.0)
cd formal
lake update          # 首次:拉 mathlib v4.31.0 及依赖(lake-manifest.json 已锁 rev)
lake exe cache get   # 首次:拉 mathlib 预编译缓存(~4.5GB,不拉则本地编译数小时)
lake build           # 应输出 Build completed successfully
lake env lean axiom_audit.lean   # 公理审计(68 条,应全部仅经典三公理或无公理)
```

**自 2026-07-05 起依赖 mathlib**（钉 `v4.31.0` tag，与工具链同版）：
`TnsCoverage.lean` / `F5OrbitLift.lean` 仍是 core-only，其余模块用到
`Finset`/`Multiset`/`Equiv`/`Relation` 库。

## 外审回收修订记录（2026-07-05，三包 triage）

CutFamilies + FrameworkLemmas 的 26 条经两路对抗审（各双会话）+ 盲对拼
（26 条独立陈述）回收，三方高度收敛。修订全部本地重写、重编译、重审计
（补丁未盲 apply）：

**陈述层修改（7 条）**：
- `f5_compound_safety`：重写为忠实版——补"cut 删整类"前提（`hCutClass`）
  与类局部结论（原版证的是"已给逐点 sound cut 的组合"，绕过了 lift 桥）；
- `f3_pair_literal_cut_sound`：Finset → **Multiset**（原版折叠重复 literal，
  与 lifecycle 的多重集匹配语义不符；盲方独立选择了 multiset，双审同判 BLOCK）；
- `f2_demand_overflow_infeasible`：`hhit`（必过割）从被否定合取**移到前提侧**
  （分离性是工程验证义务；原版 δ 取空集时结论平凡真、义务被吞）；
- `eq_key_violated_iff` / `tp7s_eq_key_sound` / `tp7s_eq_key_no_overcut`：
  `EqKeyViolated` def 硬化（全集约束内置），iff 形态相应调整；
- `tp7s_selected_set_nogood_overcuts`：补显式容量/需求语义与
  `SelectedSetNogoodViolated` 谓词（原版只是 card 形状反例，docstring 超卖）。

**新增（8 条）**：`f5_compound_safety_from_pointwise_sound`（弱化变体，
组合接口定位）、`f5_compound_needs_cut_invariance`（v1 §2.4 点名红测的
忠实反例——原 `needs_phom` 证的是相邻边界，已改判定位保留）、
`frontier_prune_preserves_certified_argmax`（+lex 版；原 preserves_max
只保值不保 certified witness，docstring 已收窄）、
`frontier_dominance_skip_not_migratable`（谓词迁移红测）、
`f6_packing_bound_exists_bucket`（∃ 式前提版）、`f6_cross_side_fire_infeasible`
（validator 真实 fire 形态 `C<d≤D−C'` 的合成）、
`f1_group_demand_overflow_infeasible`（group-demand 展开义务显式化）。

**docstring 强化（不改陈述）**：`f7_empty_cover_monotone`（ghost-only
scope 调用方义务）、`frontier_prune_dominates`（非剪枝 soundness 单证）、
模块头（F5 反例定位澄清）。

外审原件归档 `docs/research/p3_0b_formal_reviews_round2_20260705/`。

## 内容与对应表（68 条定理，六个模块）

### `TnsCoverage.lean` + `F5OrbitLift.lean`（首批 14 条，谓词/函数式表示，core-only）

| Lean 定理 | 对应设计稿命题 | 公理依赖 |
|---|---|---|
| `Tns.all_bad_of_cover` | TNS v3 覆盖论证骨架（覆盖集全 INFEASIBLE ⇒ 域全 INFEASIBLE） | 无 |
| `Tns.exists_minimal_below` | 乘积序良基性：任意域中每点下方存在极小元 | 经典三公理 |
| `Tns.all_bad_of_minimal_bad` | TNS v3 一般域形态：极小元集合（反链）是合法覆盖证书 | 经典三公理 |
| `Tns.std_domain_collapse` | TNS v3 标准域坍缩：(6,6) 单点证书覆盖全域 | 无 |
| `Tns.std_domain_minimal_66` | (6,6) 是标准域的一个极小元 | 经典三公理 |
| `Tns.std_domain_minimal_iff` | 标准域极小元**恰为** {(6,6)}（"最小反链=单点"的完整机器陈述） | 经典三公理 |
| `F5.labeled_orbit_lift` | F5 v3 定理 2 的**具名核心引理**：nogood 沿 P-preserving 重标搬运 sound | propext, Quot.sound |
| `F5.labeled_orbit_lift_group_preserving` | 同上，带设计稿"保群置换"显式前提的包装陈述 | propext, Quot.sound |
| `F5.realizes_comp` | 匿名 multiset 实现关系沿保群单射搬运 | 无 |
| `F5.nogood_mod_relabel` | 匿名 nogood 模掉重标后的排除力 | 无 |
| `F5.dedup_collapse_strengthens` | presence 去重使匹配谓词**严格变强**（存在布局实现 [v] 不实现 [v,v]） | propext, Quot.sound |
| `F5.dedup_collapse_can_false_reject` | 去重的**真误杀**形态：存在 P 使 [v,v] nogood sound 而去重后的 cut 排除满足 P 的布局 | propext, Quot.sound |
| `F5.presence_key_alias_collapse_strengthens` | attach presence-key alias（不同 pose 同 key）的语义坍缩 | propext, Quot.sound |
| `F5.presence_key_alias_can_false_reject` | alias 的真误杀形态（v3 alias 禁令前提的机器反例） | propext, Quot.sound |

### `DesignStatements.lean`（16 条，Finset/Multiset 表示，需 mathlib）

**来源**：陈述 = 盲形式化交付原文（GPT Pro 独立写就，归档
`docs/research/p3_0_formal_reviews_20260705/ZmdDesignStatements.lean`），
本方 2026-07-05 施工填全部 12 个 `sorry` 并把 `native_decide` 换成纯内核 `decide`。
与首批 14 条是**同一数学的两套表示**（谓词式 vs Finset 式），互相印证。

| Lean 定理 | 对应设计稿命题 | 公理依赖 |
|---|---|---|
| `dimwise_antitone_cover_soundness` | TNS v3 §2.1–2.2 覆盖 soundness（Finset 版） | propext, Quot.sound |
| `dimwise_antitone_cover_certificate_soundness` | 同上，带合同层非空域守卫 | propext, Quot.sound |
| `minimalDims_cover` | 有限下降：`MinimalDims` 是合法覆盖（≈ `exists_minimal_below`） | 经典三公理 |
| `minimalDims_antichain` | 极小元集是 oriented 反链 | 经典三公理 |
| `dimwise_antitone_minimal_antichain_soundness` | TNS v3 §2.2 一般域：重放极小反链即足够 | 经典三公理 |
| `domain_with_bottom_minimalDims_singleton` | 含 bottom 的域极小元坍缩为单点（抽象版） | 经典三公理 |
| `standard_domain_minimalDims_singleton` | 标准矩形域 [6,maxW]×[6,maxH] 坍缩到 {(6,6)} | 经典三公理 |
| `standard_domain_single_point_collapse_soundness` | O(1) 标准域证书完整 soundness | 经典三公理 |
| `Orbit.named_orbit_lift_soundness` | F5 v3 §2.3 具名形态：liftable nogood 沿组内置换搬运 | 经典三公理 |
| `Orbit.anonMultisetExtends_gives_matching` | multiset 包含 ⇒ 保 key 单射匹配（重数见证） | 经典三公理 |
| `Orbit.partialSlotPermExtends_of_fintype` | 有限 slot 池上部分单射延拓为全置换（§2.3 NOTE-2） | 经典三公理 |
| `Orbit.matching_extends_to_group_permutation` | 匹配 + 延拓原理 ⇒ 存在组内置换使布局字面包含代表 pattern | 经典三公理 |
| `Orbit.anon_multiset_lift_soundness_from_named_representative` | **F5 定理 2 完整形态（anon_lift_sound）**：单个具名代表 ⇒ 计数感知匿名 multiset nogood | 经典三公理 |
| `Orbit.boolean_presence_refines_multiset` | no-alias/no-repeat 守卫下 boolean presence 精化 multiset 语义 | 经典三公理 |
| `Orbit.boolean_presence_lift_soundness_from_named_representative` | boolean master attach 形态的完整 soundness（方案 A 的定理形状） | 经典三公理 |
| `NoRepeatCounterexample.presence_dedup_strengthens_cut_counterexample` | v3 §2.3 BLOCK-2 反例：presence 去重把重数-2 cut 强化成重数-1（具体构造） | 经典三公理 |

### `CutFamilies.lean`（15 条，第一梯队 6 个 family 的当前实现核心，需 mathlib）

**来源**：陈述由本方按可开工地图
（`docs/research/p3_0b_family_formalizability_survey_20260705/`）的抽象核心
定理表写就，每条 docstring 锚到对应 survey 报告（那里有 spec/impl 的
file:line）。**待独立复审（formal 自身队列）**（与首批同流程：先落库，后送盲对拼/对抗审）。
每个 family 给 bound（容量上界）与 infeasible（fire 条件逆否 = cut soundness
数学核）两个形态；抽象层不绑 70×70。

| Lean 定理 | 对应 survey 命题 | 公理依赖 |
|---|---|---|
| `CutFamilies.f9_area_bound` | F9：well-formed ⇒ \|A∩W\| ≤ \|W\B\|（面积上界） | 经典三公理 |
| `CutFamilies.f9_overflow_infeasible` | F9 fire：witness 面积超 safe bound ⇒ 非 well-formed | 经典三公理 |
| `CutFamilies.f1_occupancy_bound` | F1：互斥放置格子需求总和 ≤ 区域自由格数 | 经典三公理 |
| `CutFamilies.f1_demand_overflow_infeasible` | F1 fire：Σ demand·cells > \|R\blocked\| ⇒ 无合法放置 | 经典三公理 |
| `CutFamilies.f7_cover_filter_monotone` | F7：候选覆盖集随自由集单调 | propext, Quot.sound |
| `CutFamilies.f7_empty_cover_monotone` | F7 fire 传递：empty-cover 对更堵状态保持为空 | 经典三公理 |
| `CutFamilies.f4_closed_set_absorbs_reach` | F4：邻接封闭集装下全部可达点 | 无 |
| `CutFamilies.f4_unreachable_outside_closed` | F4 fire：目标在封闭集外 ⇒ 无路可达 | 无 |
| `CutFamilies.f4_subgraph_reach_mono` | F4：子图可达 ⊆ 原图可达（阻挡单调） | 无 |
| `CutFamilies.f6_strip_capacity` | F6：单自由区间内互斥 L-段 ≤ ⌊len/L⌋ | 经典三公理 |
| `CutFamilies.f6_packing_bound` | F6：不跨阻挡 ⇒ 可放数 ≤ Σ ⌊len/L⌋（分桶鸽笼） | 经典三公理 |
| `CutFamilies.f6_packing_overflow_infeasible` | F6 fire：需求超 Σ floor ⇒ 无合法放置 | 经典三公理 |
| `CutFamilies.f6_cross_side_lower_bound` | F6：对侧下界 max(0, D−C')（截断减法） | propext, Quot.sound |
| `CutFamilies.f2_cutset_bound` | F2 弱方向：边不相交必过割的路线数 ≤ \|δ\|（**不需要** MFMC） | 经典三公理 |
| `CutFamilies.f2_demand_overflow_infeasible` | F2 fire：demand > \|δ\| ⇒ 无边不相交合法路由 | 经典三公理 |
| `CutFamilies.f3_blocked_port_infeasible` | F3（第二梯队）：required port front 被选中 pose 占据 ⇒ 违反（`PortExposureFree` 对 ports 全量化 = **all-ports-active 显式假设**；`frontCell` 抽象参数 = 方向原语坑不进定理） | propext, Quot.sound |
| `CutFamilies.f3_pair_literal_cut_sound` | F3 双 literal nogood：{A,B} 同选即 fire，与其他 literal 无关（literal 子多重集匹配语义的数学核） | 经典三公理 |

### `FrameworkLemmas.lean`（9 条，搜索框架层承重骨架，需 mathlib）

**来源**：F5 复合安全 = `p1_3_f5_orbit_lift_soundness_design_v1.md` §2.4 引理
原文（v2 声明"同 v1"）；TP7-S 键边界 = `p2_0_throughput_certification_paradigm_design_v2.md`
v3 终审 BLOCK（回退循环第 1/2 条）；frontier 剪枝 = 项目 max_lex 目标的搜索剪枝
soundness。**待独立复审（formal 自身队列）**（与 CutFamilies 同批送审）。

| Lean 定理 | 对应命题 | 公理依赖 |
|---|---|---|
| `Framework.f5_compound_safety` | F5 v1 §2.4：P-HOM + 序代表选择 + cut 逐点 sound ⇒ 复合不删光合法类 | **无** |
| `Framework.f5_compound_needs_phom` | v1 §2.4 反方向陷阱的机器反例：无 P-HOM 则复合删光合法类（"标签敏感 cut + 序"红测的数学面） | propext |
| `Framework.frontier_prune_dominates` | 剪枝支配：被剪候选由 in-hand witness 支配 | 经典三公理 |
| `Framework.frontier_prune_preserves_max` | 剪枝保最优：幸存集 ∪ {w₀} 的 max = 全集 max（任意线性序） | 经典三公理 |
| `Framework.frontier_prune_preserves_max_lex` | 具体化：max_lex(area, min_side) = `ℕ ×ₗ ℕ` 特例 | 经典三公理 |
| `Framework.eq_key_violated_iff` | TP7-S 等式键排除集刻画：恰排除 A = S 一个赋值 | 经典三公理 |
| `Framework.tp7s_eq_key_sound` | 等式键 sound：Farkas 证 S 不可行 ⇒ 排除集全不可行 | 经典三公理 |
| `Framework.tp7s_eq_key_no_overcut` | 等式键不过切：真超集不触发（排除超集需独立证明） | 经典三公理 |
| `Framework.tp7s_selected_set_nogood_overcuts` | 选中集式 nogood 过切玩具反例（半容量路 + 并行路）的机器版 | propext, Quot.sound |

### `WCompleteness.lean`（3 条，Q1 分类学 W-完备骨架，需 mathlib）

**来源**：`docs/research/q1_infeasibility_class_taxonomy_design_v1.md` §5/§7
的 Lean 化。**Lean 化自查发现**：设计稿 v1 §5 "完整赋值的扩展=自身"论证
隐含两个未点名前提（Feasible⊆Complete、Complete 间无真包含），已在本模块
显式化——设计稿 v2 修订时应补进 §5 工程条件清单。**待独立复审（formal 自身队列）**。

| Lean 定理 | 对应命题 | 公理依赖 |
|---|---|---|
| `WCompleteness.complete_infeasible_liftable_reject` | 完整+不可行 ⇒ liftable-reject（"扩展=自身"的显式前提版） | propext, Quot.sound |
| `WCompleteness.w_completeness_f5_fallback` | W-完备单点见证：D_cut 成员必有 sound 且排除自身的 F5 fallback nogood | 经典三公理 |
| `WCompleteness.incomplete_assignment_fallback_unsound` | 反面：无完整性语义则 fallback 会误剪可行扩展（最小构造） | propext, Quot.sound |
| `WCompleteness.oracle_nogood_compound_search_safety` | **全链组合**：oracle liftable-reject → anon nogood → 与代表选择复合后搜索空间仍含可行解（`anon_lift_sound` × `f5_compound_safety` 组装） | 经典三公理 |

"经典三公理" = `propext`、`Classical.choice`、`Quot.sound`（Lean/mathlib 标准信任基）。
无任何 `sorry`，无 `native_decide`/`ofReduceBool`（68/68 见 `axiom_audit.lean`）。
注：2026-07-05 外审回收修订后，上表 CutFamilies / FrameworkLemmas 两节中
被修订条目以修订记录节 + 源码 docstring 为准。

## 陈述层修改记录（施工中，均已过编译+公理审计）

对盲形式化交付陈述的修改仅两类，数学内容均不变：

1. **universe 特化**：`matching_extends_to_group_permutation` /
   `anon_multiset_lift_soundness_from_named_representative` /
   `boolean_presence_lift_soundness_from_named_representative` 三条的
   `hExtend : PartialSlotPermExtends Slot` 特化为
   `PartialSlotPermExtends.{u, v, max v w}`。原因：原定义 `{ι : Type*}` 的
   universe 在定理层是刚性参数，证明内部需要以 `Slot g × Pose g` 的 subtype
   （宇宙 `max v w`）为 index 调用它，非特化不可。`partialSlotPermExtends_of_fintype`
   本身保持全 universe 多态，实例化后传入即可，组合无损。
2. **证明手段替换**：C 部分反例的 `native_decide` → 纯内核 `decide`
   （避免引入 `ofReduceBool` 编译器信任公理，守住"仅经典三公理"审计线）。

## 抽象边界（读定理前必看）

- 模型侧前提——逐维反单调（`UpwardClosed`/`DimwiseAntitoneInfeasible`）、
  谓词同组换位不变（P-HOM）、liftable reject、feasible 布局 well-formed
  （无重复 `(group,slot)`）——在这里是**假设**，不是被证明的结论。它们的成立性
  由对应设计稿的机器可查义务承担（TNS 的 ghost-use inventory / master"缩小不收紧"
  审计；F5 的逐谓词审计表 + 结构门 + immutable_scope 白名单）。
- oriented 键/schema/digest/seal 等工程纪律（如拒绝把 6x7 当 7x6 的键解析层）
  是 validator 层义务，**不**被这里的数学定理覆盖。
- alias 反例覆盖的是"语义上会出什么事"；生产端防线仍是 attach/validator 的
  fail-closed（不同 pose_id 解析到同一 presence key 即拒绝）。
- Lean 陈述的任何修改都必须重新对照设计稿原文并过独立复审（本批的两处修改
  见上节记录）。

## 下一批砖（给后续模型,按序）

1. ~~`anon_lift_sound`~~ **已完成**（2026-07-05，见 `DesignStatements.lean`
   `Orbit.anon_multiset_lift_soundness_from_named_representative` 全链）。
2. ~~第一梯队 family 核心定理~~ **已完成**（2026-07-05，`CutFamilies.lean`
   15 条：F9/F1/F7/F4/F6/F2 各 bound+infeasible 形态；待独立复审（formal 自身队列））。
3. ~~第二梯队 F3~~ **已完成**（2026-07-05，`CutFamilies.lean` F3 节 2 条，
   all-ports-active 显式量化 + frontCell 抽象参数）；F8 power_grid_reach
   **P1.3 已开启；等 P1.3 内欧氏 vs 12×12 stencil reconcile 完成**（代码自认 landmine）。
4. ~~F5 复合安全引理~~ / ~~TNS lex 支配~~ / ~~TP7-S 键边界~~ **已完成**
   （2026-07-05，`FrameworkLemmas.lean` 9 条，各带正反两面；待独立复审（formal 自身队列））。
5. ~~完备性 Q1 分类学设计稿~~ **v1 已写**（2026-07-05，
   `docs/research/q1_infeasibility_class_taxonomy_design_v1.md`，待外审（formal 自身队列））；
   ~~W-完备 Lean 骨架~~ **已完成**（`WCompleteness.lean` 3 条）。
6. 送审（formal 自身队列）：CutFamilies + FrameworkLemmas + WCompleteness + 分类学设计稿
   （四包已备好待跑）。
7. ~~组合定理~~ **已完成**（`WCompleteness.oracle_nogood_compound_search_safety`）。
   更远的砖：TP7-D 周期日历证书的可判定验收语义；F8 等 P1.3 内 stencil reconcile 完成。
