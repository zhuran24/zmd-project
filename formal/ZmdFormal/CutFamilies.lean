import Mathlib

/-!
# Cut family 核心定理的形式化（第一梯队，2026-07-05）

对应 `docs/research/p3_0b_family_formalizability_survey_20260705/` 可开工地图的
第一梯队裁定：六个 family 的 **validator 当前实际执行的数学**全部是初等论证，
在抽象有限层就能形式化，不绑定 70×70 网格。每条定理的 docstring 锚到对应
survey 报告（`f*_*.md` 的 proposition 段，那里有 spec/impl 的 file:line）。

抽象边界（与 `DesignStatements.lean` 同一纪律）：
- 工程语义前提（cell_owner well-formed / 占据格互斥 / pose 不跨阻挡 /
  路线边不相交 / 割集分离性）在这里是**假设**，不是被证明的结论；
  其成立性由各 family validator 的重算义务与结构门承担。
- 每个 family 给两个形态：**bound**（合法放置的容量上界）与
  **infeasible**（fire 条件 = bound 的逆否：需求超上界 ⇒ 不存在合法放置）。
  后者就是 cut soundness 的数学核（"这条 cut 绝不误杀合法方案"的抽象层）。
- 名字里的重数学（Hall / max-flow / LP-dual）刻意不出现：F6 当前实现只是
  区间 floor 计数 + 鸽笼、F2 只需"每条路必过割"的弱方向、F1 的 LP 对偶是
  自认未实现项——survey 的核心发现"family 名字比实现吓人"在此坐实。
-/

namespace ZmdFormal.CutFamilies

/-! ## F9 density_envelope — 面积计数（survey: f9_density_envelope.md）

当前实现编码的离散几何面积上界：window `W` 内 group 拥有的格子只能落在
`W \ B`（`B` = ghost ∪ exterior，Impl:275-305），故 `|A ∩ W| ≤ |W \ B|`；
witness 面积严格超过 safe bound 即 fire（Impl:517-566）。 -/

/-- F9 bound：well-formed（owned∩W 避开 blocked）⇒ 面积不超过 safe upper bound。 -/
theorem f9_area_bound {α : Type*} [DecidableEq α] (A W B : Finset α)
    (hwf : A ∩ W ⊆ W \ B) : (A ∩ W).card ≤ (W \ B).card :=
  Finset.card_le_card hwf

/-- F9 infeasible：witness 面积 > safe bound ⇒ 布局不可能 well-formed。 -/
theorem f9_overflow_infeasible {α : Type*} [DecidableEq α] (A W B : Finset α)
    (hfire : (W \ B).card < (A ∩ W).card) : ¬ (A ∩ W ⊆ W \ B) :=
  fun hwf => absurd (f9_area_bound A W B hwf) (Nat.not_le.mpr hfire)

/-! ## F1 region_capacity — 容量鸽笼（survey: f1_region_capacity.md）

当前核心是 cap/demand 计数（LP-dual/Farkas 是自认未实现项）：每个放置实例
占据 ≥ cells_i 个自由格、两两互斥、全落在 region 自由格内，
故 Σ demand·cells > |R \ blocked| ⇒ 不可行。 -/

/-- F1 bound：互斥放置的格子需求总和不超过区域自由格数。 -/
theorem f1_occupancy_bound {ι α : Type*} [DecidableEq ι] [DecidableEq α]
    (S : Finset ι) (occ : ι → Finset α) (Free : Finset α) (cells : ι → ℕ)
    (hsub : ∀ i ∈ S, occ i ⊆ Free)
    (hdisj : ∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (occ i) (occ j))
    (hcells : ∀ i ∈ S, cells i ≤ (occ i).card) :
    ∑ i ∈ S, cells i ≤ Free.card :=
  calc ∑ i ∈ S, cells i ≤ ∑ i ∈ S, (occ i).card := Finset.sum_le_sum hcells
    _ = (S.biUnion occ).card := (Finset.card_biUnion hdisj).symm
    _ ≤ Free.card := Finset.card_le_card (Finset.biUnion_subset.mpr hsub)

/-- F1 infeasible：格子需求超过区域容量 ⇒ 不存在合法互斥放置。 -/
theorem f1_demand_overflow_infeasible {ι α : Type*} [DecidableEq ι] [DecidableEq α]
    (S : Finset ι) (occ : ι → Finset α) (Free : Finset α) (cells : ι → ℕ)
    (hfire : Free.card < ∑ i ∈ S, cells i) :
    ¬ ((∀ i ∈ S, occ i ⊆ Free) ∧
       (∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (occ i) (occ j)) ∧
       (∀ i ∈ S, cells i ≤ (occ i).card)) := by
  rintro ⟨hsub, hdisj, hcells⟩
  exact absurd (f1_occupancy_bound S occ Free cells hsub hdisj hcells)
    (Nat.not_le.mpr hfire)

/-! ## F7 power_hitting_set（empty-cover 版）— 集合单调性（survey: f7_power_hitting_set.md）

候选杆位能否覆盖目标是杆位自身的性质（`CanCover` 与自由集无关）；自由集缩小
只会让候选集缩小，故空覆盖对"更堵"的状态保持为空。这是 F7 中不受
欧氏 vs 12×12 stencil 语义分裂影响的核心（分裂只影响 `CanCover` 的具体定义，
不影响单调性骨架）。 -/

/-- F7 单调：候选覆盖集随自由集单调。 -/
theorem f7_cover_filter_monotone {α : Type*} [DecidableEq α]
    (CanCover : α → Prop) [DecidablePred CanCover]
    (Free Free' : Finset α) (hsub : Free' ⊆ Free) :
    Free'.filter CanCover ⊆ Free.filter CanCover :=
  Finset.filter_subset_filter _ hsub

/-- F7 infeasible 传递：覆盖集在 `Free` 上已空 ⇒ 任何更小的自由集上仍空。 -/
theorem f7_empty_cover_monotone {α : Type*} [DecidableEq α]
    (CanCover : α → Prop) [DecidablePred CanCover]
    (Free Free' : Finset α) (hsub : Free' ⊆ Free)
    (hempty : Free.filter CanCover = ∅) :
    Free'.filter CanCover = ∅ :=
  Finset.subset_empty.mp (hempty ▸ f7_cover_filter_monotone CanCover Free Free' hsub)

/-! ## F4 component_reach — 有限图可达性（survey: f4_component_reach.md）

两个核心：①对邻接封闭的集合装下从它出发的一切可达点（补集无路可入）；
②子图可达 ⊆ 原图可达（阻挡增加只减少可达性）。可达性用自反传递闭包建模。 -/

/-- F4 封闭性：`R` 对邻接封闭且起点在 `R` 内 ⇒ 可达点全在 `R` 内。 -/
theorem f4_closed_set_absorbs_reach {α : Type*} (adj : α → α → Prop) (R : Set α)
    (hclosed : ∀ u ∈ R, ∀ v, adj u v → v ∈ R) {s t : α} (hs : s ∈ R)
    (hreach : Relation.ReflTransGen adj s t) : t ∈ R := by
  induction hreach with
  | refl => exact hs
  | tail _ hstep ih => exact hclosed _ ih _ hstep

/-- F4 infeasible：目标在封闭集之外 ⇒ 无路可达（连通性 cut 的数学核）。 -/
theorem f4_unreachable_outside_closed {α : Type*} (adj : α → α → Prop) (R : Set α)
    (hclosed : ∀ u ∈ R, ∀ v, adj u v → v ∈ R) {s t : α} (hs : s ∈ R) (ht : t ∉ R) :
    ¬ Relation.ReflTransGen adj s t :=
  fun h => ht (f4_closed_set_absorbs_reach adj R hclosed hs h)

/-- F4 子图单调：邻接关系缩小（阻挡增加）不会新增可达对。 -/
theorem f4_subgraph_reach_mono {α : Type*} (adj adj' : α → α → Prop)
    (hsub : ∀ u v, adj' u v → adj u v) {s t : α}
    (h : Relation.ReflTransGen adj' s t) : Relation.ReflTransGen adj s t :=
  Relation.ReflTransGen.mono hsub h

/-! ## F6 shape_packing_hall（受限版）— 区间 floor 计数 + 鸽笼（survey: f6_shape_packing_hall.md）

当前实现是一维 1×L 计数，不是 Hall 定理（多形状版才需要 Hall）：
每个 pose 占据恰 L 格、不跨阻挡（= 整体落进某个自由区间）、两两互斥
⇒ 可放数 ≤ Σ_区间 ⌊len/L⌋；对侧下界 max(0, D−C') 是纯算术。 -/

/-- F6 单区间容量：长为 `|I|` 的自由区间内互斥 L-段最多 `⌊|I|/L⌋` 个。 -/
theorem f6_strip_capacity {ι α : Type*} [DecidableEq ι] [DecidableEq α]
    (S : Finset ι) (I : Finset α) (seg : ι → Finset α) (L : ℕ) (hL : 0 < L)
    (hcard : ∀ i ∈ S, (seg i).card = L)
    (hsub : ∀ i ∈ S, seg i ⊆ I)
    (hdisj : ∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (seg i) (seg j)) :
    S.card ≤ I.card / L := by
  rw [Nat.le_div_iff_mul_le hL]
  calc S.card * L = ∑ i ∈ S, (seg i).card := by
        have h : ∑ i ∈ S, (seg i).card = ∑ _i ∈ S, L := Finset.sum_congr rfl hcard
        rw [h, Finset.sum_const, smul_eq_mul]
    _ = (S.biUnion seg).card := (Finset.card_biUnion hdisj).symm
    _ ≤ I.card := Finset.card_le_card (Finset.biUnion_subset.mpr hsub)

/-- F6 bound：pose 不跨阻挡（各自整体落进某自由区间）⇒ 可放数 ≤ Σ ⌊len/L⌋。 -/
theorem f6_packing_bound {ι κ α : Type*} [DecidableEq ι] [DecidableEq κ] [DecidableEq α]
    (S : Finset ι) (J : Finset κ) (seg : ι → Finset α) (interval : κ → Finset α)
    (L : ℕ) (hL : 0 < L) (bucket : ι → κ)
    (hbucket : ∀ i ∈ S, bucket i ∈ J)
    (hsub : ∀ i ∈ S, seg i ⊆ interval (bucket i))
    (hcard : ∀ i ∈ S, (seg i).card = L)
    (hdisj : ∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (seg i) (seg j)) :
    S.card ≤ ∑ j ∈ J, (interval j).card / L := by
  rw [Finset.card_eq_sum_card_fiberwise hbucket]
  apply Finset.sum_le_sum
  intro j _
  apply f6_strip_capacity (S.filter (fun i => bucket i = j)) (interval j) seg L hL
  · intro i hi
    exact hcard i (Finset.mem_filter.mp hi).1
  · intro i hi
    have hm := Finset.mem_filter.mp hi
    rw [← hm.2]
    exact hsub i hm.1
  · intro i hi k hk hne
    exact hdisj i (Finset.mem_filter.mp hi).1 k (Finset.mem_filter.mp hk).1 hne

/-- F6 infeasible：需求超过 Σ ⌊len/L⌋ ⇒ 不存在合法放置。 -/
theorem f6_packing_overflow_infeasible {ι κ α : Type*}
    [DecidableEq ι] [DecidableEq κ] [DecidableEq α]
    (S : Finset ι) (J : Finset κ) (seg : ι → Finset α) (interval : κ → Finset α)
    (L : ℕ) (hL : 0 < L) (bucket : ι → κ)
    (hfire : (∑ j ∈ J, (interval j).card / L) < S.card) :
    ¬ ((∀ i ∈ S, bucket i ∈ J) ∧
       (∀ i ∈ S, seg i ⊆ interval (bucket i)) ∧
       (∀ i ∈ S, (seg i).card = L) ∧
       (∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (seg i) (seg j))) := by
  rintro ⟨hbucket, hsub, hcard, hdisj⟩
  exact absurd (f6_packing_bound S J seg interval L hL bucket hbucket hsub hcard hdisj)
    (Nat.not_le.mpr hfire)

/-- F6 对侧下界：总需求 D、对侧容量 C' ⇒ 本侧至少放 D − C'（截断减法）。 -/
theorem f6_cross_side_lower_bound (D C' x y : ℕ)
    (htotal : D ≤ x + y) (hother : y ≤ C') : D - C' ≤ x := by
  omega

/-! ## F2 cutset — 割边计数（survey: f2_cutset.md）

cut soundness 只需**弱方向**（不需要 Menger/max-flow）：每条路线必用割集
`δ` 中至少一条边、路线间边不相交 ⇒ 路线数 ≤ |δ|。
"必过割"前提本身由 δ 的分离性构造保证（分离性 ⇒ 避割路不存在正是
`f4_subgraph_reach_mono` 的逆否，见 F4）。 -/

/-- F2 bound：边不相交且每条必过割的路线数不超过割边数（鸽笼）。 -/
theorem f2_cutset_bound {ι ε : Type*} [DecidableEq ι] [DecidableEq ε]
    (routes : Finset ι) (edges : ι → Finset ε) (δ : Finset ε)
    (hhit : ∀ i ∈ routes, ∃ e ∈ edges i, e ∈ δ)
    (hdisj : ∀ i ∈ routes, ∀ j ∈ routes, i ≠ j → Disjoint (edges i) (edges j)) :
    routes.card ≤ δ.card := by
  classical
  choose pick hpick using hhit
  by_contra hlt
  rw [Nat.not_le] at hlt
  obtain ⟨x, _, y, _, hne, heq⟩ :=
    Finset.exists_ne_map_eq_of_card_lt_of_maps_to
      (by rwa [Finset.card_attach])
      (fun a (_ : a ∈ routes.attach) => (hpick a.1 a.2).2)
  have hxy : x.1 ≠ y.1 := fun h => hne (Subtype.ext h)
  have h1 : pick x.1 x.2 ∈ edges x.1 := (hpick x.1 x.2).1
  have h2 : pick y.1 y.2 ∈ edges y.1 := (hpick y.1 y.2).1
  rw [heq] at h1
  exact Finset.disjoint_left.mp (hdisj x.1 x.2 y.1 y.2 hxy) h1 h2

/-- F2 infeasible：需求路线数超过割边数 ⇒ 不存在边不相交的合法路由。 -/
theorem f2_demand_overflow_infeasible {ι ε : Type*} [DecidableEq ι] [DecidableEq ε]
    (routes : Finset ι) (edges : ι → Finset ε) (δ : Finset ε)
    (hfire : δ.card < routes.card) :
    ¬ ((∀ i ∈ routes, ∃ e ∈ edges i, e ∈ δ) ∧
       (∀ i ∈ routes, ∀ j ∈ routes, i ≠ j → Disjoint (edges i) (edges j))) := by
  rintro ⟨hhit, hdisj⟩
  exact absurd (f2_cutset_bound routes edges δ hhit hdisj) (Nat.not_le.mpr hfire)

end ZmdFormal.CutFamilies
