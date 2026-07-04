import Mathlib

/-!
# Lean 4 statements for the two ZMD design drafts

This file intentionally contains theorem *statements* for the load-bearing
mathematics in the two reviewed design drafts.  The engineering contracts
(schema versions, digests, replay isolation, seal transitions, telemetry, and
red tests) are represented only as semantic hypotheses such as `InfeasibleOn`,
`LiftableReject`, and `P_HOM`.  That is deliberate: the requested comparison
point is the mathematical spine, not the concrete JSON/checkpoint plumbing.

来源与施工纪律（2026-07-05）：本文件的**陈述**来自盲形式化交付
`docs/research/p3_0_formal_reviews_20260705/ZmdDesignStatements.lean`，
陈述层一字不动；本方施工只填 `sorry` 证明体、并把 `native_decide` 换成
纯内核证明（公理审计纪律：仅 propext / Classical.choice / Quot.sound）。
若施工中发现陈述本身需要修改，必须走「编译 + 公理审计 + 对照设计稿原文」
三件套并在 formal/README.md 记录。
-/

universe u v w z

namespace ZmdDesignStatements

/-! ## A. Terminal no-solution evidence: dimwise antimonotonicity and covers -/

/-- Oriented rectangular dimensions.  The order is deliberately oriented:
`(w,h)` and `(h,w)` are not canonicalized. -/
abbrev Dim : Type := Nat × Nat

namespace Dim

/-- Componentwise, oriented order: `a ≤ᵈ b` means `a.w ≤ b.w` and `a.h ≤ b.h`. -/
def le (a b : Dim) : Prop := a.1 ≤ b.1 ∧ a.2 ≤ b.2

/-- Strict part of the componentwise order. -/
def lt (a b : Dim) : Prop := le a b ∧ ¬ le b a

end Dim

/-- A finite candidate domain `D` has every certified cover point below some candidate. -/
def CoversDimwise (D C : Finset Dim) : Prop :=
  C ⊆ D ∧ ∀ x, x ∈ D → ∃ c, c ∈ C ∧ Dim.le c x

/-- All points of a finite set have been replay-verified infeasible. -/
def InfeasibleOn (Feasible : Dim → Prop) (C : Finset Dim) : Prop :=
  ∀ c, c ∈ C → ¬ Feasible c

/-- The target conclusion of a terminal no-solution certificate. -/
def NoSolutionOnDomain (Feasible : Dim → Prop) (D : Finset Dim) : Prop :=
  ∀ x, x ∈ D → ¬ Feasible x

/--
The design draft's §2.1 monotonicity lemma as a semantic hypothesis:
if a smaller oriented rectangle is infeasible, every larger oriented rectangle
inside the same authoritative domain is infeasible.
-/
def DimwiseAntitoneInfeasible (D : Finset Dim) (Feasible : Dim → Prop) : Prop :=
  ∀ ⦃a b : Dim⦄, a ∈ D → b ∈ D → Dim.le a b → ¬ Feasible a → ¬ Feasible b

/--
A contract-level cover certificate.  `D.Nonempty` records the draft's explicit
choice to reject vacuous empty-domain certificates even though the pure theorem
below would be true on an empty set.
-/
def CoverCertificate (D C : Finset Dim) (Feasible : Dim → Prop) : Prop :=
  D.Nonempty ∧ CoversDimwise D C ∧ InfeasibleOn Feasible C

/--
`terminal_no_solution_evidence_contract_design_v2.md` v3 §2.1–§2.2:
componentwise antimonotonicity plus a replay-verified oriented cover implies
no candidate in the authoritative domain is feasible.
-/
theorem dimwise_antitone_cover_soundness
    {D C : Finset Dim} {Feasible : Dim → Prop}
    (hmono : DimwiseAntitoneInfeasible D Feasible)
    (hcover : CoversDimwise D C)
    (hcert : InfeasibleOn Feasible C) :
    NoSolutionOnDomain Feasible D := by
  intro x hx
  rcases hcover.2 x hx with ⟨c, hcC, hcx⟩
  exact hmono (hcover.1 hcC) hx hcx (hcert c hcC)

/--
Same theorem with the contract's non-empty-domain validity condition included.
The non-emptiness is not used by the order argument; it is a contract guard.
-/
theorem dimwise_antitone_cover_certificate_soundness
    {D C : Finset Dim} {Feasible : Dim → Prop}
    (hmono : DimwiseAntitoneInfeasible D Feasible)
    (hcert : CoverCertificate D C Feasible) :
    NoSolutionOnDomain Feasible D := by
  exact dimwise_antitone_cover_soundness hmono hcert.2.1 hcert.2.2

/-- Minimal elements of a finite domain under the oriented componentwise order. -/
noncomputable def MinimalDims (D : Finset Dim) : Finset Dim := by
  classical
  exact D.filter (fun m => ∀ x, x ∈ D → Dim.le x m → x = m)

/-- The finite-domain antichain property of `MinimalDims`. -/
def DimwiseAntichain (C : Finset Dim) : Prop :=
  ∀ ⦃a b : Dim⦄, a ∈ C → b ∈ C → Dim.le a b → Dim.le b a → a = b

/-- 施工辅助引理：`MinimalDims` 的成员刻画。 -/
private lemma mem_minimalDims {D : Finset Dim} {x : Dim} :
    x ∈ MinimalDims D ↔ x ∈ D ∧ ∀ y, y ∈ D → Dim.le y x → y = x := by
  classical
  simp [MinimalDims, Finset.mem_filter]

/-- 施工辅助引理：对 `x.1 + x.2` 的强归纳给出有限下降——域内任一点下方必有极小元。
与谓词版 `ZmdFormal.TnsCoverage.exists_minimal_below` 是同一论证的 Finset 翻译。 -/
private lemma exists_minimalDims_le {D : Finset Dim} :
    ∀ (n : Nat) (x : Dim), x.1 + x.2 ≤ n → x ∈ D →
      ∃ c, c ∈ MinimalDims D ∧ Dim.le c x := by
  intro n
  induction n with
  | zero =>
    intro x hn hx
    refine ⟨x, mem_minimalDims.mpr ⟨hx, ?_⟩, le_refl _, le_refl _⟩
    intro y _ hyx
    have hy1 : y.1 ≤ x.1 := hyx.1
    have hy2 : y.2 ≤ x.2 := hyx.2
    exact Prod.ext (by omega) (by omega)
  | succ n ih =>
    intro x hn hx
    by_cases hmin : ∀ y, y ∈ D → Dim.le y x → y = x
    · exact ⟨x, mem_minimalDims.mpr ⟨hx, hmin⟩, le_refl _, le_refl _⟩
    · push Not at hmin
      obtain ⟨y, hyD, hyx, hne⟩ := hmin
      have hy1 : y.1 ≤ x.1 := hyx.1
      have hy2 : y.2 ≤ x.2 := hyx.2
      have hlt : y.1 + y.2 < x.1 + x.2 := by
        rcases Nat.lt_or_ge y.1 x.1 with h | h
        · omega
        · have h1 : y.1 = x.1 := by omega
          have h2 : y.2 ≠ x.2 := fun h2 => hne (Prod.ext h1 h2)
          omega
      obtain ⟨c, hc, hcy⟩ := ih y (by omega) hyD
      exact ⟨c, hc, le_trans hcy.1 hy1, le_trans hcy.2 hy2⟩

/--
General-domain warning formalized: for an arbitrary finite generated domain,
the real cover is the whole minimal antichain, not necessarily a singleton.
This is the finite descent lemma used by §2.2.
-/
theorem minimalDims_cover (D : Finset Dim) :
    CoversDimwise D (MinimalDims D) := by
  constructor
  · intro m hm
    exact (mem_minimalDims.mp hm).1
  · intro x hx
    exact exists_minimalDims_le (x.1 + x.2) x (le_refl _) hx

/-- The selected cover points form an oriented antichain. -/
theorem minimalDims_antichain (D : Finset Dim) :
    DimwiseAntichain (MinimalDims D) := by
  intro a b _ _ hab hba
  exact Prod.ext (Nat.le_antisymm hab.1 hba.1) (Nat.le_antisymm hab.2 hba.2)

/--
`terminal_no_solution_evidence_contract_design_v2.md` v3 §2.2:
for a general finite domain, replaying exactly the minimal antichain is enough.
The theorem intentionally does not hard-code `(6,6)`.
-/
theorem dimwise_antitone_minimal_antichain_soundness
    {D : Finset Dim} {Feasible : Dim → Prop}
    (hmono : DimwiseAntitoneInfeasible D Feasible)
    (hmin : InfeasibleOn Feasible (MinimalDims D)) :
    NoSolutionOnDomain Feasible D := by
  exact dimwise_antitone_cover_soundness hmono (minimalDims_cover D) hmin

/-- A rectangular box domain, used only for the standard-domain corollary. -/
def BoxDomain (lo hi : Dim) : Finset Dim :=
  (Finset.Icc lo.1 hi.1).product (Finset.Icc lo.2 hi.2)

/-- 施工辅助引理：`BoxDomain` 的成员刻画。 -/
private lemma mem_boxDomain {lo hi x : Dim} :
    x ∈ BoxDomain lo hi ↔ (lo.1 ≤ x.1 ∧ x.1 ≤ hi.1) ∧ (lo.2 ≤ x.2 ∧ x.2 ≤ hi.2) := by
  unfold BoxDomain
  rw [Finset.product_eq_sprod, Finset.mem_product, Finset.mem_Icc, Finset.mem_Icc]

/--
Bottom-element collapse: any finite domain that contains `bottom` and whose
members are all componentwise above `bottom` has exactly one minimal element.
This captures the mathematical content behind the standard `(6,6)` collapse.
-/
theorem domain_with_bottom_minimalDims_singleton
    (D : Finset Dim) (bottom : Dim)
    (hbottom : bottom ∈ D)
    (hfloor : ∀ x, x ∈ D → Dim.le bottom x) :
    MinimalDims D = ({bottom} : Finset Dim) := by
  ext m
  simp only [Finset.mem_singleton, mem_minimalDims]
  constructor
  · rintro ⟨hmD, hmin⟩
    exact (hmin bottom hbottom (hfloor m hmD)).symm
  · rintro rfl
    refine ⟨hbottom, ?_⟩
    intro y hyD hyb
    have hby := hfloor y hyD
    exact Prod.ext (Nat.le_antisymm hyb.1 hby.1) (Nat.le_antisymm hyb.2 hby.2)

/--
`terminal_no_solution_evidence_contract_design_v2.md` v3 §2.2:
standard authoritative full domain with lower corner `(6,6)` collapses to one
cover point.  No transpose, area, or aspect-ratio dominance is used.
-/
theorem standard_domain_minimalDims_singleton
    {maxW maxH : Nat} (hw : 6 ≤ maxW) (hh : 6 ≤ maxH) :
    MinimalDims (BoxDomain (6, 6) (maxW, maxH)) = ({(6, 6)} : Finset Dim) := by
  apply domain_with_bottom_minimalDims_singleton
  · exact mem_boxDomain.mpr ⟨⟨le_refl _, hw⟩, ⟨le_refl _, hh⟩⟩
  · intro x hx
    have h := mem_boxDomain.mp hx
    exact ⟨h.1.1, h.2.1⟩

/--
The O(1) standard-domain certificate: once `(6,6)` is replay-verified
infeasible, the whole standard box is infeasible by the oriented monotonicity
lemma.
-/
theorem standard_domain_single_point_collapse_soundness
    {maxW maxH : Nat} {Feasible : Dim → Prop}
    (hw : 6 ≤ maxW) (hh : 6 ≤ maxH)
    (hmono : DimwiseAntitoneInfeasible (BoxDomain (6, 6) (maxW, maxH)) Feasible)
    (h66 : ¬ Feasible (6, 6)) :
    NoSolutionOnDomain Feasible (BoxDomain (6, 6) (maxW, maxH)) := by
  apply dimwise_antitone_minimal_antichain_soundness hmono
  rw [standard_domain_minimalDims_singleton hw hh]
  intro c hc
  rw [Finset.mem_singleton] at hc
  subst hc
  exact h66


/-! ## B. F5 orbit-aware lifting: named slots and anonymous multisets -/

/-- A selected literal with a concrete group, concrete slot, and concrete pose. -/
abbrev NamedAtom (GroupId : Type u) (Slot : GroupId → Type v)
    (Pose : GroupId → Type w) : Type (max u v w) :=
  Sigma (fun g : GroupId => Slot g × Pose g)

/-- A group/slot key, used to state “no repeated named slot”. -/
abbrev GroupSlot (GroupId : Type u) (Slot : GroupId → Type v) : Type (max u v) :=
  Sigma Slot

/-- A group/pose key, used for anonymous multiset semantics. -/
abbrev GroupPose (GroupId : Type u) (Pose : GroupId → Type w) : Type (max u w) :=
  Sigma Pose

/-- A whole-layout selection, represented extensionally as the finite set of selected literals. -/
abbrev Layout (GroupId : Type u) (Slot : GroupId → Type v)
    (Pose : GroupId → Type w) : Type (max u v w) :=
  Finset (NamedAtom GroupId Slot Pose)

/-- The product of within-group slot permutations `Π_g S_{n_g}`. -/
abbrev SlotPerm (GroupId : Type u) (Slot : GroupId → Type v) : Type (max u v) :=
  (g : GroupId) → Equiv.Perm (Slot g)

namespace Orbit

variable {GroupId : Type u} {Slot : GroupId → Type v} {Pose : GroupId → Type w}

/-- Project a named atom to its `(group,slot)` key. -/
def atomGroupSlot (a : NamedAtom GroupId Slot Pose) : GroupSlot GroupId Slot :=
  ⟨a.1, a.2.1⟩

/-- Project a named atom to its anonymous `(group,pose)` key. -/
def atomGroupPose (a : NamedAtom GroupId Slot Pose) : GroupPose GroupId Pose :=
  ⟨a.1, a.2.2⟩

/-- Act on a literal by moving only the slot label inside its group. -/
def permuteAtom (σ : SlotPerm GroupId Slot)
    (a : NamedAtom GroupId Slot Pose) : NamedAtom GroupId Slot Pose :=
  ⟨a.1, ((σ a.1) a.2.1, a.2.2)⟩

/-- Act on an entire layout/pattern by a product of within-group slot permutations. -/
def permuteLayout
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    (σ : SlotPerm GroupId Slot) (A : Layout GroupId Slot Pose) :
    Layout GroupId Slot Pose :=
  A.image (permuteAtom σ)

/-- Named extension: a whole layout contains every literal of the named pattern. -/
def NamedExtends (P A : Layout GroupId Slot Pose) : Prop :=
  P ⊆ A

/-- A named whole-layout nogood: no feasible whole layout extends `P`. -/
def NamedNogood (Feasible : Layout GroupId Slot Pose → Prop)
    (P : Layout GroupId Slot Pose) : Prop :=
  ∀ A, Feasible A → NamedExtends P A → False

/--
The mathematical content of the draft's “liftable reject” contract: the oracle
verdict is closed under all complete extensions of the core, after all mutable
search context has either been excluded or promoted into the core/scope.
-/
def LiftableReject (Feasible : Layout GroupId Slot Pose → Prop)
    (P : Layout GroupId Slot Pose) : Prop :=
  NamedNogood Feasible P

/-- P-HOM at the level needed for nogood soundness: feasibility is invariant under `Π_g S_{n_g}`. -/
def P_HOM
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    (Feasible : Layout GroupId Slot Pose → Prop) : Prop :=
  ∀ σ A, Feasible (permuteLayout σ A) ↔ Feasible A

/-- Optional strengthened P-HOM including objective invariance, matching the draft's §2.2 table. -/
def P_HOM_with_objective
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    {Objective : Type z}
    (Feasible : Layout GroupId Slot Pose → Prop)
    (objective : Layout GroupId Slot Pose → Objective) : Prop :=
  P_HOM Feasible ∧ ∀ σ A, objective (permuteLayout σ A) = objective A

/-- No layout/pattern assigns two poses to the same `(group,slot)`. -/
def NoDuplicateNamedSlots (P : Layout GroupId Slot Pose) : Prop :=
  ∀ ⦃a b : NamedAtom GroupId Slot Pose⦄,
    a ∈ P → b ∈ P → atomGroupSlot a = atomGroupSlot b → a = b

/-- No repeated anonymous `(group,pose)` key in a pattern. -/
def NoDuplicateGroupPoses (P : Layout GroupId Slot Pose) : Prop :=
  ∀ ⦃a b : NamedAtom GroupId Slot Pose⦄,
    a ∈ P → b ∈ P → atomGroupPose a = atomGroupPose b → a = b

/--
No presence-key duplicate or alias after the exact master attach projection.
This is stronger and more implementation-faithful than just “no duplicate pose_id”.
-/
def NoPresenceKeyAlias {PresenceKey : Type z}
    (presenceKey : GroupPose GroupId Pose → PresenceKey)
    (P : Layout GroupId Slot Pose) : Prop :=
  ∀ ⦃a b : NamedAtom GroupId Slot Pose⦄,
    a ∈ P → b ∈ P →
    presenceKey (atomGroupPose a) = presenceKey (atomGroupPose b) → a = b

/-- 施工辅助引理：先 `σ` 再逐组取逆的置换作用互相抵消。 -/
private lemma permuteAtom_inv_cancel
    (σ : SlotPerm GroupId Slot) (a : NamedAtom GroupId Slot Pose) :
    permuteAtom (fun g => (σ g).symm) (permuteAtom σ a) = a := by
  obtain ⟨g, s, q⟩ := a
  show (⟨g, ((σ g).symm ((σ g) s), q)⟩ : NamedAtom GroupId Slot Pose) = ⟨g, (s, q)⟩
  rw [Equiv.symm_apply_apply]

/--
`p1_3_f5_orbit_lift_soundness_design_v2.md` v3 §2.3, named-slot form:
a liftable named nogood can be transported along any group-preserving slot
permutation.
-/
theorem named_orbit_lift_soundness
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    {Feasible : Layout GroupId Slot Pose → Prop}
    {P : Layout GroupId Slot Pose}
    (hPHOM : P_HOM Feasible)
    (hReject : LiftableReject Feasible P)
    (σ : SlotPerm GroupId Slot) :
    LiftableReject Feasible (permuteLayout σ P) := by
  intro A hFeas hExt
  have hFeas' : Feasible (permuteLayout (fun g => (σ g).symm) A) :=
    (hPHOM (fun g => (σ g).symm) A).mpr hFeas
  apply hReject (permuteLayout (fun g => (σ g).symm) A) hFeas'
  intro p hp
  have h1 : permuteAtom σ p ∈ permuteLayout σ P := Finset.mem_image_of_mem _ hp
  have h2 : permuteAtom σ p ∈ A := hExt h1
  have h3 : permuteAtom (fun g => (σ g).symm) (permuteAtom σ p) ∈
      permuteLayout (fun g => (σ g).symm) A := Finset.mem_image_of_mem _ h2
  rwa [permuteAtom_inv_cancel] at h3

/-- Count-aware anonymous presence semantics: map named literals to a multiset of `(group,pose)`. -/
def anonMultiset (A : Layout GroupId Slot Pose) : Multiset (GroupPose GroupId Pose) :=
  A.val.map atomGroupPose

/-- Multiset containment, stated by counts to avoid any ambiguity with set inclusion. -/
def MultisetContains {α : Type u} [DecidableEq α] (small big : Multiset α) : Prop :=
  ∀ x : α, Multiset.count x small ≤ Multiset.count x big

/-- Anonymous multiset extension: `A` contains the pattern with at least the same multiplicities. -/
def AnonMultisetExtends
    [DecidableEq GroupId] [∀ g, DecidableEq (Pose g)]
    (P A : Layout GroupId Slot Pose) : Prop :=
  MultisetContains (anonMultiset P) (anonMultiset A)

/-- Count-aware anonymous nogood.  This is *not* boolean presence. -/
def AnonMultisetNogood
    [DecidableEq GroupId] [∀ g, DecidableEq (Pose g)]
    (Feasible : Layout GroupId Slot Pose → Prop)
    (P : Layout GroupId Slot Pose) : Prop :=
  ∀ A, Feasible A → AnonMultisetExtends P A → False

/--
A concrete matching from every named pattern occurrence to a selected atom in a
layout with the same anonymous `(group,pose)` key.  This is the witness hidden
inside multiset containment.
-/
def HasGroupPoseMatching
    (P A : Layout GroupId Slot Pose) : Prop :=
  ∃ f : {a : NamedAtom GroupId Slot Pose // a ∈ P} →
        {b : NamedAtom GroupId Slot Pose // b ∈ A},
    Function.Injective f ∧
    ∀ a, atomGroupPose (f a).1 = atomGroupPose a.1

/--
Finite-multiset containment supplies an injective occurrence matching.
This is where multiplicity is preserved; replacing the multiset by a set would
make this lemma false.
-/
theorem anonMultisetExtends_gives_matching
    [DecidableEq GroupId] [∀ g, DecidableEq (Pose g)]
    {P A : Layout GroupId Slot Pose}
    (h : AnonMultisetExtends P A) :
    HasGroupPoseMatching P A := by
  classical
  -- 逐 key 的 fiber 基数不等式：count 就是 filter 的 card。
  have hcard : ∀ x : GroupPose GroupId Pose,
      (P.filter (fun a => atomGroupPose a = x)).card ≤
        (A.filter (fun a => atomGroupPose a = x)).card := by
    intro x
    have hx := h x
    rw [anonMultiset, anonMultiset, Multiset.count_map, Multiset.count_map] at hx
    simpa [Finset.filter, Multiset.filter_congr, eq_comm] using hx
  -- 每个 fiber 上取一个嵌入。
  have hemb : ∀ x : GroupPose GroupId Pose,
      Nonempty ({a : NamedAtom GroupId Slot Pose // a ∈ P.filter (fun a => atomGroupPose a = x)} ↪
        {b : NamedAtom GroupId Slot Pose // b ∈ A.filter (fun b => atomGroupPose b = x)}) := by
    intro x
    apply Function.Embedding.nonempty_of_card_le
    simpa [Fintype.card_coe] using hcard x
  have e : ∀ x : GroupPose GroupId Pose,
      {a : NamedAtom GroupId Slot Pose // a ∈ P.filter (fun a => atomGroupPose a = x)} ↪
        {b : NamedAtom GroupId Slot Pose // b ∈ A.filter (fun b => atomGroupPose b = x)} :=
    fun x => Classical.choice (hemb x)
  -- fiber 同构：subtype-of-subtype ↔ filter-subtype（两侧）。
  let isoP : ∀ x : GroupPose GroupId Pose,
      {a : {a : NamedAtom GroupId Slot Pose // a ∈ P} // atomGroupPose a.1 = x} ≃
        {a : NamedAtom GroupId Slot Pose // a ∈ P.filter (fun a => atomGroupPose a = x)} :=
    fun x =>
      { toFun := fun a => ⟨a.1.1, Finset.mem_filter.mpr ⟨a.1.2, a.2⟩⟩
        invFun := fun b => ⟨⟨b.1, (Finset.mem_filter.mp b.2).1⟩, (Finset.mem_filter.mp b.2).2⟩
        left_inv := fun a => rfl
        right_inv := fun b => rfl }
  let isoA : ∀ x : GroupPose GroupId Pose,
      {b : {b : NamedAtom GroupId Slot Pose // b ∈ A} // atomGroupPose b.1 = x} ≃
        {b : NamedAtom GroupId Slot Pose // b ∈ A.filter (fun b => atomGroupPose b = x)} :=
    fun x =>
      { toFun := fun b => ⟨b.1.1, Finset.mem_filter.mpr ⟨b.1.2, b.2⟩⟩
        invFun := fun c => ⟨⟨c.1, (Finset.mem_filter.mp c.2).1⟩, (Finset.mem_filter.mp c.2).2⟩
        left_inv := fun b => rfl
        right_inv := fun c => rfl }
  -- Sigma 拼装：逐 fiber 嵌入沿 key 汇成整体嵌入，sigmaFiberEquiv 两头收尾。
  let F : (Σ x : GroupPose GroupId Pose,
        {a : {a : NamedAtom GroupId Slot Pose // a ∈ P} // atomGroupPose a.1 = x}) ↪
      (Σ x : GroupPose GroupId Pose,
        {b : {b : NamedAtom GroupId Slot Pose // b ∈ A} // atomGroupPose b.1 = x}) :=
    Function.Embedding.sigmaMap (Function.Embedding.refl _) (fun x =>
      ((isoP x).toEmbedding.trans (e x)).trans (isoA x).symm.toEmbedding)
  refine ⟨fun a =>
    (Equiv.sigmaFiberEquiv
        (fun b : {b : NamedAtom GroupId Slot Pose // b ∈ A} => atomGroupPose b.1))
      (F ((Equiv.sigmaFiberEquiv
        (fun a : {a : NamedAtom GroupId Slot Pose // a ∈ P} => atomGroupPose a.1)).symm a)),
    ?_, ?_⟩
  · intro a₁ a₂ hh
    exact (Equiv.sigmaFiberEquiv _).symm.injective
      (F.injective ((Equiv.sigmaFiberEquiv _).injective hh))
  · intro a
    exact (F ((Equiv.sigmaFiberEquiv
      (fun a : {a : NamedAtom GroupId Slot Pose // a ∈ P} => atomGroupPose a.1)).symm a)).2.2

/--
The precise group-theoretic extension principle used in §2.3 NOTE-2:
for each group, any finite injective partial map between slots extends to a
full permutation of that group's slot type.  Finiteness of slot pools is one
standard way to obtain this property; the anonymous theorem below only needs
this property, not any stronger enumeration details.
-/
def PartialSlotPermExtends (Slot : GroupId → Type v) : Prop :=
  ∀ (g : GroupId) {ι : Type*} [Fintype ι],
    (src dst : ι → Slot g) →
    Function.Injective src → Function.Injective dst →
    ∃ σ : Equiv.Perm (Slot g), ∀ i : ι, σ (src i) = dst i

/-- Slot finiteness is used exactly to discharge `PartialSlotPermExtends`. -/
theorem partialSlotPermExtends_of_fintype
    [∀ g, Fintype (Slot g)] [∀ g, DecidableEq (Slot g)] :
    PartialSlotPermExtends (GroupId := GroupId) Slot := by
  classical
  intro g ι _ src dst hsrc hdst
  -- 经典拼装：range src ≃ ι ≃ range dst；补集由基数相等取双射；sumCompl 粘合。
  have hcompl : Fintype.card ↥(Set.range src)ᶜ = Fintype.card ↥(Set.range dst)ᶜ := by
    have h1 := Fintype.card_compl_set (Set.range src)
    have h2 := Fintype.card_compl_set (Set.range dst)
    have h3 := Set.card_range_of_injective hsrc
    have h4 := Set.card_range_of_injective hdst
    omega
  let e_mid : ↥(Set.range src) ≃ ↥(Set.range dst) :=
    (Equiv.ofInjective src hsrc).symm.trans (Equiv.ofInjective dst hdst)
  let e_compl : ↥(Set.range src)ᶜ ≃ ↥(Set.range dst)ᶜ := Fintype.equivOfCardEq hcompl
  refine ⟨(Equiv.Set.sumCompl (Set.range src)).symm.trans
    ((e_mid.sumCongr e_compl).trans (Equiv.Set.sumCompl (Set.range dst))), ?_⟩
  intro i
  simp only [Equiv.trans_apply]
  rw [Equiv.Set.sumCompl_symm_apply_of_mem (Set.mem_range_self i)]
  have hmid : e_mid ⟨src i, Set.mem_range_self i⟩ = ⟨dst i, Set.mem_range_self i⟩ := by
    simp only [e_mid, Equiv.trans_apply]
    have h1 : (Equiv.ofInjective src hsrc).symm ⟨src i, Set.mem_range_self i⟩ = i := by
      apply (Equiv.ofInjective src hsrc).injective
      rw [Equiv.apply_symm_apply]
      rfl
    rw [h1]
    rfl
  simp only [Equiv.sumCongr_apply, Sum.map_inl, hmid]
  exact Equiv.Set.sumCompl_apply_inl _ _

/-- 施工辅助定义：把「组相等」证明变成 `Slot g × Pose g` 的显式 cast（`▸` 的
motive 搜索会丢弃类型 ascription，包成 def 让 unifier 走 defeq）。 -/
private def castSnd {b : NamedAtom GroupId Slot Pose} {g : GroupId} (h : b.1 = g) :
    Slot g × Pose g := h ▸ b.2

/-- 施工辅助引理：把「组相等」的依赖 cast 显式化——atom 的 `(group,slot)` 投影。 -/
private lemma groupSlot_cast (b : NamedAtom GroupId Slot Pose) (g : GroupId) (h : b.1 = g) :
    atomGroupSlot b = ⟨g, (castSnd h).1⟩ := by
  subst h; rfl

/-- 施工辅助引理：同上，`(group,pose)` 投影。 -/
private lemma groupPose_cast (b : NamedAtom GroupId Slot Pose) (g : GroupId) (h : b.1 = g) :
    atomGroupPose b = ⟨g, (castSnd h).2⟩ := by
  subst h; rfl

/-- 施工辅助引理：同上，atom 本体的显式化。 -/
private lemma atom_cast_eq (b : NamedAtom GroupId Slot Pose) (g : GroupId) (h : b.1 = g) :
    b = ⟨g, castSnd h⟩ := by
  subst h; rfl

/--
Given an occurrence matching and the partial-extension principle, construct a
product permutation whose action makes the layout literally contain the named
representative pattern.
-/
theorem matching_extends_to_group_permutation
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    {P A : Layout GroupId Slot Pose}
    (hExtend : PartialSlotPermExtends.{u, v, max v w} (GroupId := GroupId) Slot)
    (hMatch : HasGroupPoseMatching P A)
    (hPslots : NoDuplicateNamedSlots P)
    (hAslots : NoDuplicateNamedSlots A) :
    ∃ σ : SlotPerm GroupId Slot, NamedExtends P (permuteLayout σ A) := by
  classical
  obtain ⟨f, hfinj, hfkey⟩ := hMatch
  -- f 保 (group,pose) key ⇒ 像的组与原组相同。
  have hkeyfst : ∀ (a : {a : NamedAtom GroupId Slot Pose // a ∈ P}),
      (f a).1.1 = a.1.1 :=
    fun a => congrArg (fun t : GroupPose GroupId Pose => t.1) (hfkey a)
  -- 逐组：src = f 像的 slot（cast 回组 g），dst = pattern 原子自己的 slot；
  -- 两侧单射由 NoDuplicateNamedSlots + f 单射保证，然后调 hExtend。
  have hstep : ∀ g : GroupId, ∃ σg : Equiv.Perm (Slot g),
      ∀ (sp : Slot g × Pose g) (hsp : (⟨g, sp⟩ : NamedAtom GroupId Slot Pose) ∈ P),
        σg (castSnd (hkeyfst ⟨⟨g, sp⟩, hsp⟩) : Slot g × Pose g).1 = sp.1 := by
    intro g
    haveI : Fintype {sp : Slot g × Pose g // (⟨g, sp⟩ : NamedAtom GroupId Slot Pose) ∈ P} :=
      Fintype.ofInjective
        (fun q => (⟨⟨g, q.1⟩, q.2⟩ : {a : NamedAtom GroupId Slot Pose // a ∈ P}))
        (fun q₁ q₂ h => Subtype.ext (eq_of_heq
          (Sigma.mk.inj_iff.mp (congrArg Subtype.val h)).2))
    have hsrc : Function.Injective
        (fun q : {sp : Slot g × Pose g // (⟨g, sp⟩ : NamedAtom GroupId Slot Pose) ∈ P} =>
          (castSnd (hkeyfst ⟨⟨g, q.1⟩, q.2⟩) : Slot g × Pose g).1) := by
      intro q₁ q₂ heq
      have h₁ : (f ⟨⟨g, q₁.1⟩, q₁.2⟩).1.1 = g := hkeyfst ⟨⟨g, q₁.1⟩, q₁.2⟩
      have h₂ : (f ⟨⟨g, q₂.1⟩, q₂.2⟩).1.1 = g := hkeyfst ⟨⟨g, q₂.1⟩, q₂.2⟩
      have hgs : atomGroupSlot (f ⟨⟨g, q₁.1⟩, q₁.2⟩).1 =
          atomGroupSlot (f ⟨⟨g, q₂.1⟩, q₂.2⟩).1 := by
        rw [groupSlot_cast _ g h₁, groupSlot_cast _ g h₂]
        exact congrArg (fun s => (⟨g, s⟩ : GroupSlot GroupId Slot)) heq
      have hbeq : (f ⟨⟨g, q₁.1⟩, q₁.2⟩).1 = (f ⟨⟨g, q₂.1⟩, q₂.2⟩).1 :=
        hAslots (f ⟨⟨g, q₁.1⟩, q₁.2⟩).2 (f ⟨⟨g, q₂.1⟩, q₂.2⟩).2 hgs
      have hpe := hfinj (Subtype.ext hbeq)
      exact Subtype.ext (eq_of_heq
        (Sigma.mk.inj_iff.mp (congrArg Subtype.val hpe)).2)
    have hdst : Function.Injective
        (fun q : {sp : Slot g × Pose g // (⟨g, sp⟩ : NamedAtom GroupId Slot Pose) ∈ P} =>
          q.1.1) := by
      intro q₁ q₂ heq
      have hgs : atomGroupSlot (⟨g, q₁.1⟩ : NamedAtom GroupId Slot Pose) =
          atomGroupSlot (⟨g, q₂.1⟩ : NamedAtom GroupId Slot Pose) :=
        congrArg (fun s => (⟨g, s⟩ : GroupSlot GroupId Slot)) heq
      have := hPslots q₁.2 q₂.2 hgs
      exact Subtype.ext (eq_of_heq (Sigma.mk.inj_iff.mp this).2)
    obtain ⟨σg, hσg⟩ := hExtend g
      (ι := {sp : Slot g × Pose g // (⟨g, sp⟩ : NamedAtom GroupId Slot Pose) ∈ P})
      _ _ hsrc hdst
    exact ⟨σg, fun sp hsp => hσg ⟨sp, hsp⟩⟩
  choose σ hσ using hstep
  refine ⟨σ, ?_⟩
  intro p hp
  have hbg : (f ⟨p, hp⟩).1.1 = p.1 := hkeyfst ⟨p, hp⟩
  -- pose 保持：cast 显式化后与 pattern 原子的 pose 相等。
  have hpose : (castSnd hbg : Slot p.1 × Pose p.1).2 = p.2.2 := by
    have hk := hfkey ⟨p, hp⟩
    rw [groupPose_cast _ p.1 hbg] at hk
    exact eq_of_heq (Sigma.mk.inj_iff.mp hk).2
  -- slot 归位：σ 把 f 像的 slot 送回 pattern 原子的 slot。
  have hslot : σ p.1 (castSnd hbg : Slot p.1 × Pose p.1).1 = p.2.1 :=
    hσ p.1 p.2 hp
  refine Finset.mem_image.mpr ⟨(f ⟨p, hp⟩).1, (f ⟨p, hp⟩).2, ?_⟩
  rw [atom_cast_eq (f ⟨p, hp⟩).1 p.1 hbg]
  show (⟨p.1, (σ p.1 (castSnd hbg : Slot p.1 × Pose p.1).1,
      (castSnd hbg : Slot p.1 × Pose p.1).2)⟩ : NamedAtom GroupId Slot Pose) = p
  rw [hslot, hpose]

/--
`p1_3_f5_orbit_lift_soundness_design_v2.md` v3 §2.3, anonymous multiset form:
from one liftable named representative pattern, obtain a count-aware anonymous
multiset nogood for all feasible whole layouts.

Exact prerequisites encoded here:
* P-HOM: `hPHOM`.
* Liftable reject: `hReject`, i.e. all complete extensions of the named core are infeasible.
* Feasible layouts are well-formed: no repeated `(group,slot)`.
* The representative pattern itself has no repeated `(group,slot)`.
* The per-group finite partial injection can be extended to a total group permutation;
  finite slot pools imply this via `partialSlotPermExtends_of_fintype`.

Notice what is *not* required for the count-aware multiset theorem: no duplicate
`(group,pose)`.  Two copies of the same pose are sound here only because the
multiset remembers the count.  The boolean-presence theorem below needs the
extra no-alias/no-repeat condition.
-/
theorem anon_multiset_lift_soundness_from_named_representative
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    {Feasible : Layout GroupId Slot Pose → Prop}
    {P : Layout GroupId Slot Pose}
    (hExtend : PartialSlotPermExtends.{u, v, max v w} (GroupId := GroupId) Slot)
    (hPHOM : P_HOM Feasible)
    (hFeasibleWellFormed : ∀ A, Feasible A → NoDuplicateNamedSlots A)
    (hReject : LiftableReject Feasible P)
    (hPslots : NoDuplicateNamedSlots P) :
    AnonMultisetNogood Feasible P := by
  intro A hFeas hExt
  obtain ⟨σ, hσ⟩ := matching_extends_to_group_permutation hExtend
    (anonMultisetExtends_gives_matching hExt) hPslots (hFeasibleWellFormed A hFeas)
  have hFeas' : Feasible (permuteLayout σ A) := (hPHOM σ A).mpr hFeas
  exact hReject (permuteLayout σ A) hFeas' hσ

/-- Boolean presence set after the master attach key projection. -/
def presenceSet {PresenceKey : Type z} [DecidableEq PresenceKey]
    (presenceKey : GroupPose GroupId Pose → PresenceKey)
    (A : Layout GroupId Slot Pose) : Finset PresenceKey :=
  A.image (fun a => presenceKey (atomGroupPose a))

/-- Boolean presence extension: every projected presence key in `P` appears in `A`. -/
def BooleanPresenceExtends {PresenceKey : Type z} [DecidableEq PresenceKey]
    (presenceKey : GroupPose GroupId Pose → PresenceKey)
    (P A : Layout GroupId Slot Pose) : Prop :=
  presenceSet presenceKey P ⊆ presenceSet presenceKey A

/-- Boolean presence nogood, the master form that loses multiplicities. -/
def BooleanPresenceNogood {PresenceKey : Type z} [DecidableEq PresenceKey]
    (presenceKey : GroupPose GroupId Pose → PresenceKey)
    (Feasible : Layout GroupId Slot Pose → Prop)
    (P : Layout GroupId Slot Pose) : Prop :=
  ∀ A, Feasible A → BooleanPresenceExtends presenceKey P A → False

/--
The key-faithfulness side condition needed when reducing boolean presence to
count-aware multiset semantics: in feasible layouts, a key matching a pattern
key must denote the same `(group,pose)`, not an alias.
-/
def PresenceKeyFaithfulForPattern {PresenceKey : Type z}
    (presenceKey : GroupPose GroupId Pose → PresenceKey)
    (Feasible : Layout GroupId Slot Pose → Prop)
    (P : Layout GroupId Slot Pose) : Prop :=
  ∀ A, Feasible A →
    ∀ ⦃p a : NamedAtom GroupId Slot Pose⦄,
      p ∈ P → a ∈ A →
      presenceKey (atomGroupPose a) = presenceKey (atomGroupPose p) →
      atomGroupPose a = atomGroupPose p

/--
Boolean presence is sound only after proving it refines the count-aware multiset
condition for this pattern.  The two explicit hypotheses record the draft's
v3 no-repeat/alias guards: no duplicate projected keys inside the cert, and no
runtime alias from a feasible layout atom back to a pattern key.
-/
theorem boolean_presence_refines_multiset
    [DecidableEq GroupId] [∀ g, DecidableEq (Pose g)]
    {PresenceKey : Type z} [DecidableEq PresenceKey]
    {Feasible : Layout GroupId Slot Pose → Prop}
    {presenceKey : GroupPose GroupId Pose → PresenceKey}
    {P A : Layout GroupId Slot Pose}
    (hPatternNoAlias : NoPresenceKeyAlias presenceKey P)
    (hFaithful : PresenceKeyFaithfulForPattern presenceKey Feasible P)
    (hFeas : Feasible A)
    (hBool : BooleanPresenceExtends presenceKey P A) :
    AnonMultisetExtends P A := by
  classical
  intro x
  by_cases hx : Multiset.count x (anonMultiset P) = 0
  · simp [hx]
  · -- pattern 侧：no-alias ⇒ 匿名投影无重复 ⇒ count ≤ 1。
    have hnodup : (anonMultiset P).Nodup := by
      rw [anonMultiset]
      apply Multiset.Nodup.map_on
      · intro a haP b hbP hab
        exact hPatternNoAlias haP hbP (congrArg presenceKey hab)
      · exact P.nodup
    have hle1 : Multiset.count x (anonMultiset P) ≤ 1 :=
      Multiset.nodup_iff_count_le_one.mp hnodup x
    -- layout 侧：presence 命中 + key 保真 ⇒ count ≥ 1。
    have hmem : x ∈ anonMultiset P :=
      Multiset.count_pos.mp (Nat.pos_of_ne_zero hx)
    rw [anonMultiset, Multiset.mem_map] at hmem
    obtain ⟨p, hpP, hpx⟩ := hmem
    have hpP' : p ∈ P := hpP
    have hxkey : presenceKey x ∈ presenceSet presenceKey A := by
      apply hBool
      rw [presenceSet, Finset.mem_image]
      exact ⟨p, hpP', by rw [hpx]⟩
    rw [presenceSet, Finset.mem_image] at hxkey
    obtain ⟨a, haA, hak⟩ := hxkey
    have hax : atomGroupPose a = x := by
      have hfa := hFaithful A hFeas hpP' haA (by rw [hak, ← hpx])
      rw [hfa, hpx]
    have hge1 : 1 ≤ Multiset.count x (anonMultiset A) := by
      rw [anonMultiset]
      have : x ∈ Multiset.map atomGroupPose A.val :=
        Multiset.mem_map.mpr ⟨a, haA, hax⟩
      exact Multiset.count_pos.mpr this
    omega

/--
Boolean master attach soundness as a corollary of the count-aware theorem plus
no-repeat/no-alias/refinement assumptions.  This is the theorem shape that
justifies the design's “方案 A: reject duplicate `(group,pose)` and attach-key
alias” before emitting a boolean presence nogood.
-/
theorem boolean_presence_lift_soundness_from_named_representative
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    {PresenceKey : Type z} [DecidableEq PresenceKey]
    {Feasible : Layout GroupId Slot Pose → Prop}
    {presenceKey : GroupPose GroupId Pose → PresenceKey}
    {P : Layout GroupId Slot Pose}
    (hExtend : PartialSlotPermExtends.{u, v, max v w} (GroupId := GroupId) Slot)
    (hPHOM : P_HOM Feasible)
    (hFeasibleWellFormed : ∀ A, Feasible A → NoDuplicateNamedSlots A)
    (hReject : LiftableReject Feasible P)
    (hPslots : NoDuplicateNamedSlots P)
    (hPatternNoAlias : NoPresenceKeyAlias presenceKey P)
    (hFaithful : PresenceKeyFaithfulForPattern presenceKey Feasible P) :
    BooleanPresenceNogood presenceKey Feasible P := by
  intro A hFeas hBool
  exact anon_multiset_lift_soundness_from_named_representative
    hExtend hPHOM hFeasibleWellFormed hReject hPslots A hFeas
    (boolean_presence_refines_multiset hPatternNoAlias hFaithful hFeas hBool)

end Orbit


/-! ## C. Concrete no-repeat counterexample for boolean presence deduplication -/

namespace NoRepeatCounterexample

/-- One group. -/
inductive G where
  | g
  deriving DecidableEq, Fintype

/-- Two slots in that group. -/
inductive S where
  | s0 | s1
  deriving DecidableEq, Fintype

/-- One pose. -/
inductive P where
  | p
  deriving DecidableEq, Fintype

abbrev SlotOf (_ : G) := S
abbrev PoseOf (_ : G) := P

abbrev Atom := NamedAtom G SlotOf PoseOf
abbrev Lay := Layout G SlotOf PoseOf
abbrev GPose := GroupPose G PoseOf

def a0 : Atom := ⟨G.g, (S.s0, P.p)⟩
def a1 : Atom := ⟨G.g, (S.s1, P.p)⟩

/-- Named pattern requiring two copies of the same `(group,pose)` on two slots. -/
def duplicatePosePattern : Lay :=
  {a0, a1}

/-- A layout with only one copy of that pose. -/
def singlePoseLayout : Lay :=
  {a0}

/-- Boolean attach key: exactly the anonymous `(group,pose)` key. -/
def presenceKey (x : GPose) : GPose := x

/-- A toy feasible predicate: the one-copy layout is feasible. -/
def FeasibleToy (A : Lay) : Prop :=
  A = singlePoseLayout

/-- Count-aware nogood predicate specialized to the toy. -/
def CountAwareNogoodToy (Ptn : Lay) : Prop :=
  ∀ A, FeasibleToy A → Orbit.AnonMultisetExtends Ptn A → False

/--
`p1_3_f5_orbit_lift_soundness_design_v2.md` v3 §2.3 BLOCK-2 counterexample:
boolean presence deduplication strengthens a multiplicity-2 cut into a
multiplicity-1 cut.  The two-copy count-aware nogood is compatible with the
one-copy feasible layout, but the boolean presence key is already triggered by
that feasible one-copy layout.
-/
theorem presence_dedup_strengthens_cut_counterexample :
    FeasibleToy singlePoseLayout ∧
    Orbit.BooleanPresenceExtends presenceKey duplicatePosePattern singlePoseLayout ∧
    ¬ Orbit.AnonMultisetExtends duplicatePosePattern singlePoseLayout ∧
    CountAwareNogoodToy duplicatePosePattern := by
  refine ⟨rfl, ?_, ?_, ?_⟩
  · show Orbit.presenceSet presenceKey duplicatePosePattern ⊆
      Orbit.presenceSet presenceKey singlePoseLayout
    decide
  · show ¬ ∀ x : GPose,
      Multiset.count x (Orbit.anonMultiset duplicatePosePattern) ≤
        Multiset.count x (Orbit.anonMultiset singlePoseLayout)
    decide
  · intro A hFeasible hContains
    change A = singlePoseLayout at hFeasible
    subst A
    revert hContains
    show ¬ ∀ x : GPose,
      Multiset.count x (Orbit.anonMultiset duplicatePosePattern) ≤
        Multiset.count x (Orbit.anonMultiset singlePoseLayout)
    decide

end NoRepeatCounterexample

end ZmdDesignStatements
