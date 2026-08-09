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

/-- F1 infeasible：格子需求超过区域容量 ⇒ 不存在合法互斥放置。
（instance 级形态；group-demand 级见下一条——`S` 必须是需求的完整展开
这一绑定义务由下一条显式化。） -/
theorem f1_demand_overflow_infeasible {ι α : Type*} [DecidableEq ι] [DecidableEq α]
    (S : Finset ι) (occ : ι → Finset α) (Free : Finset α) (cells : ι → ℕ)
    (hfire : Free.card < ∑ i ∈ S, cells i) :
    ¬ ((∀ i ∈ S, occ i ⊆ Free) ∧
       (∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (occ i) (occ j)) ∧
       (∀ i ∈ S, cells i ≤ (occ i).card)) := by
  rintro ⟨hsub, hdisj, hcells⟩
  exact absurd (f1_occupancy_bound S occ Free cells hsub hdisj hcells)
    (Nat.not_le.mpr hfire)

/-- F1 group-demand 版（2026-07-05 外审修订：survey proposition 的原始
形态是 `Σ_g demand(g)·cells_per_pose(g) > cap_R`——本版把"实例集 `S`
是需求的完整展开"这一绑定义务显式写进前提 `hexp`，堵住把 `S` 错误
实例化成需求子集导致证过小命题的口子）：group 级需求超过区域容量 ⇒
不存在满足展开完整性的合法互斥放置。 -/
theorem f1_group_demand_overflow_infeasible {γ ι α : Type*}
    [DecidableEq γ] [DecidableEq ι] [DecidableEq α]
    (G : Finset γ) (demand cellsPerPose : γ → ℕ) (Free : Finset α)
    (S : Finset ι) (occ : ι → Finset α) (grp : ι → γ)
    (hgrp : ∀ i ∈ S, grp i ∈ G)
    (hexp : ∀ g ∈ G, demand g ≤ (S.filter (fun i => grp i = g)).card)
    (hcells : ∀ i ∈ S, cellsPerPose (grp i) ≤ (occ i).card)
    (hsub : ∀ i ∈ S, occ i ⊆ Free)
    (hdisj : ∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (occ i) (occ j))
    (hfire : Free.card < ∑ g ∈ G, demand g * cellsPerPose g) : False := by
  have hbound : ∑ g ∈ G, demand g * cellsPerPose g ≤ Free.card := by
    calc ∑ g ∈ G, demand g * cellsPerPose g
        ≤ ∑ g ∈ G, (S.filter (fun i => grp i = g)).card * cellsPerPose g := by
          apply Finset.sum_le_sum
          intro g hg
          exact Nat.mul_le_mul_right _ (hexp g hg)
      _ = ∑ g ∈ G, ∑ _i ∈ S.filter (fun i => grp i = g), cellsPerPose g := by
          apply Finset.sum_congr rfl
          intro g _
          rw [Finset.sum_const, smul_eq_mul, Nat.mul_comm]
      _ = ∑ g ∈ G, ∑ i ∈ S.filter (fun i => grp i = g), cellsPerPose (grp i) := by
          apply Finset.sum_congr rfl
          intro g _
          apply Finset.sum_congr rfl
          intro i hi
          rw [(Finset.mem_filter.mp hi).2]
      _ = ∑ i ∈ S, cellsPerPose (grp i) :=
          Finset.sum_fiberwise_of_maps_to hgrp _
      _ ≤ Free.card :=
          f1_occupancy_bound S occ Free (fun i => cellsPerPose (grp i))
            hsub hdisj hcells
  exact absurd hbound (Nat.not_le.mpr hfire)

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

/-- F7 infeasible 传递：覆盖集在 `Free` 上已空 ⇒ 任何更小的自由集上仍空。

**调用方义务（2026-07-05 外审点名）**：`hsub : Free' ⊆ Free` 只在 `Free`
是 **replay-stable 的 ghost-only scope** 时对搜索过程恒成立——若把
`Free` 取成含当前 `cell_owner` 阻挡的 full-free 集，回溯移走 blocker
后未来 free 集**不是**它的子集，本定理前提断裂（这正是 survey 点名
"ghost-only empty-cover 才能出 single-literal cut"的原因）。定理本身
是真单调性引理；scope 选择是工程侧 fail-closed 义务。 -/
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

/-- F6 bound 的存在式前提版（2026-07-05 外审修订）：validator 侧的
"不跨阻挡"语义是**存在**某个自由区间容纳该 pose（`∀ i, ∃ j`），不是
外部预给的全局 bucket 函数——本版把 `f6_packing_bound` 的 bucket 前提
降为存在式，choice 在证明内部完成，不留给工程侧当白证义务。 -/
theorem f6_packing_bound_exists_bucket {ι κ α : Type*}
    [DecidableEq ι] [DecidableEq κ] [DecidableEq α]
    (S : Finset ι) (J : Finset κ) (seg : ι → Finset α) (interval : κ → Finset α)
    (L : ℕ) (hL : 0 < L)
    (hsub : ∀ i ∈ S, ∃ j ∈ J, seg i ⊆ interval j)
    (hcard : ∀ i ∈ S, (seg i).card = L)
    (hdisj : ∀ i ∈ S, ∀ j ∈ S, i ≠ j → Disjoint (seg i) (seg j)) :
    S.card ≤ ∑ j ∈ J, (interval j).card / L := by
  classical
  choose bucket hbJ hbsub using hsub
  -- 把部分函数补全成全函数（S 外取值任意，不影响结论）。
  by_cases hJ : J.Nonempty
  · obtain ⟨j₀, hj₀⟩ := hJ
    let bk : ι → κ := fun i => if h : i ∈ S then bucket i h else j₀
    apply f6_packing_bound S J seg interval L hL bk
    · intro i hi
      simp only [bk, dif_pos hi]
      exact hbJ i hi
    · intro i hi
      simp only [bk, dif_pos hi]
      exact hbsub i hi
    · exact hcard
    · exact hdisj
  · -- J 空 ⇒ S 空（每个成员都需要一个区间）⇒ 平凡。
    have hS : S = ∅ := by
      by_contra hne
      obtain ⟨i, hi⟩ := Finset.nonempty_iff_ne_empty.mpr hne
      exact hJ ⟨bucket i hi, hbJ i hi⟩
    simp [hS]

/-- F6 组合 fire（2026-07-05 外审修订，validator 当前真实 fire 形态
`C_R < d_R ≤ D − C_R'` 的 soundness 合成）：本侧容量 C（由
`f6_packing_bound` 给出）、对侧容量 C'、总需求 D、证书下界 d 满足
`C < d ≤ D − C'` 时，任何"本侧放 x 个、对侧放 y 个、合计覆盖需求"
的放置方案都矛盾。 -/
theorem f6_cross_side_fire_infeasible (C C' D d x y : ℕ)
    (hcert : C < d) (hd : d ≤ D - C')
    (hsplit : D ≤ x + y) (hx : x ≤ C) (hy : y ≤ C') : False := by
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

/-- F2 infeasible（2026-07-05 外审修订：**分离性移到前提侧**——`hhit`
（每条路必过割）由 δ 的分离性构造保证，是 A/B 分割 + enclosure 的
**工程验证义务**，不是被否定的合法性成分；原版把它放进被否定合取里，
δ 取空集时结论平凡真、分离性义务被静默吞掉）：在分离性成立的前提下，
需求路线数超过割边数 ⇒ 这批路线不可能边不相交。 -/
theorem f2_demand_overflow_infeasible {ι ε : Type*} [DecidableEq ι] [DecidableEq ε]
    (routes : Finset ι) (edges : ι → Finset ε) (δ : Finset ε)
    (hhit : ∀ i ∈ routes, ∃ e ∈ edges i, e ∈ δ)
    (hfire : δ.card < routes.card) :
    ¬ (∀ i ∈ routes, ∀ j ∈ routes, i ≠ j → Disjoint (edges i) (edges j)) := by
  intro hdisj
  exact absurd (f2_cutset_bound routes edges δ hhit hdisj) (Nat.not_le.mpr hfire)

/-! ## F3 port_exposure — 格邻接 + 双 literal nogood（survey: f3_port_exposure.md，第二梯队）

第二梯队条件已按 survey 裁定显式化：
- **all-ports-active 假设**（SPEC:161-164 自认 open，`active_port_witness`
  未实现是 P1.5 硬门）内嵌为 `PortExposureFree` 对 `ports i` 的**全量化**——
  若真实语义中某 port 可 inactive，本前提偏强，届时定理要改量化域；
- **方向原语坑**（helper 自认 N/S 与 canonical DIR_DELTA 相反，shared
  primitives 前 no cert）：`frontCell` 是抽象参数，"c + dir(d) 算得对"
  是工程侧义务，不进定理；
- 只覆盖当前 validator 实际执行的 `cell_owner` blocker 分支（VAL:79-112）；
  spec 的 `front ∉ free_cells` 广义分支实现里没有（ORACLE:205-215），不形式化。 -/

/-- F3 约束谓词：每个选中 pose 的每个 required port 的 front cell 不被任何
选中 pose 占据（对 `ports i` 全量化 = all-ports-active 显式假设）。 -/
def PortExposureFree {ι π α : Type*} (selected : Finset ι) (occupied : ι → Finset α)
    (ports : ι → Finset π) (frontCell : π → α) : Prop :=
  ∀ i ∈ selected, ∀ q ∈ ports i, ∀ j ∈ selected, frontCell q ∉ occupied j

/-- F3 infeasible：某选中 pose 的 required port front 被另一选中 pose 占据
⇒ 违反 port exposure（SPEC:14-28 的可执行分支）。 -/
theorem f3_blocked_port_infeasible {ι π α : Type*}
    (selected : Finset ι) (occupied : ι → Finset α)
    (ports : ι → Finset π) (frontCell : π → α)
    {A B : ι} {p : π}
    (hA : A ∈ selected) (hB : B ∈ selected)
    (hp : p ∈ ports A) (hblock : frontCell p ∈ occupied B) :
    ¬ PortExposureFree selected occupied ports frontCell :=
  fun hfree => hfree A hA p hp B hB hblock

/-- F3 约束谓词的 multiset 版（2026-07-05 外审修订）：lifecycle evaluator
的 literal 语义是**匿名 slot 的 multiset**（重复 `(group,pose)` literal
带重数），Finset 会折叠重数——literal cut 定理必须在 Multiset 上陈述。 -/
def PortExposureFreeMS {ι π α : Type*} (selected : Multiset ι)
    (occupied : ι → Finset α) (ports : ι → Finset π) (frontCell : π → α) : Prop :=
  ∀ i ∈ selected, ∀ q ∈ ports i, ∀ j ∈ selected, frontCell q ∉ occupied j

/-- F3 literal cut soundness（2026-07-05 外审修订：`selected` 与 cut body
均改 **Multiset**——原版用 Finset `{A,B} ⊆ selected` 会折叠重复 literal，
与 docstring 声称的"子多重集匹配语义"不符）：双 literal nogood `[A, B]`
在任何以 ≥ 该重数选中这两个 literal 的状态上 fire 都 sound，与其他被选
literal 无关。 -/
theorem f3_pair_literal_cut_sound {ι π α : Type*} [DecidableEq ι]
    (occupied : ι → Finset α) (ports : ι → Finset π) (frontCell : π → α)
    {A B : ι} {p : π}
    (hp : p ∈ ports A) (hblock : frontCell p ∈ occupied B) :
    ∀ selected : Multiset ι, ({A, B} : Multiset ι) ≤ selected →
      ¬ PortExposureFreeMS selected occupied ports frontCell := by
  intro selected hsub hfree
  have hA : A ∈ selected :=
    Multiset.mem_of_le hsub (Multiset.mem_cons_self A _)
  have hB : B ∈ selected :=
    Multiset.mem_of_le hsub (Multiset.mem_cons_of_mem (Multiset.mem_singleton_self B))
  exact hfree A hA p hp B hB hblock

end ZmdFormal.CutFamilies
