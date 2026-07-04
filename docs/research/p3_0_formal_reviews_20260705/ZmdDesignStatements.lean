import Mathlib

/-!
# Lean 4 statements for the two ZMD design drafts

This file intentionally contains theorem *statements* for the load-bearing
mathematics in the two reviewed design drafts.  The engineering contracts
(schema versions, digests, replay isolation, seal transitions, telemetry, and
red tests) are represented only as semantic hypotheses such as `InfeasibleOn`,
`LiftableReject`, and `P_HOM`.  That is deliberate: the requested comparison
point is the mathematical spine, not the concrete JSON/checkpoint plumbing.
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

/--
General-domain warning formalized: for an arbitrary finite generated domain,
the real cover is the whole minimal antichain, not necessarily a singleton.
This is the finite descent lemma used by §2.2.
-/
theorem minimalDims_cover (D : Finset Dim) :
    CoversDimwise D (MinimalDims D) := by
  sorry

/-- The selected cover points form an oriented antichain. -/
theorem minimalDims_antichain (D : Finset Dim) :
    DimwiseAntichain (MinimalDims D) := by
  sorry

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
  sorry

/--
`terminal_no_solution_evidence_contract_design_v2.md` v3 §2.2:
standard authoritative full domain with lower corner `(6,6)` collapses to one
cover point.  No transpose, area, or aspect-ratio dominance is used.
-/
theorem standard_domain_minimalDims_singleton
    {maxW maxH : Nat} (hw : 6 ≤ maxW) (hh : 6 ≤ maxH) :
    MinimalDims (BoxDomain (6, 6) (maxW, maxH)) = ({(6, 6)} : Finset Dim) := by
  sorry

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
  sorry


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
  sorry

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
  sorry

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
  sorry

/--
Given an occurrence matching and the partial-extension principle, construct a
product permutation whose action makes the layout literally contain the named
representative pattern.
-/
theorem matching_extends_to_group_permutation
    [DecidableEq GroupId] [∀ g, DecidableEq (Slot g)] [∀ g, DecidableEq (Pose g)]
    {P A : Layout GroupId Slot Pose}
    (hExtend : PartialSlotPermExtends (GroupId := GroupId) Slot)
    (hMatch : HasGroupPoseMatching P A)
    (hPslots : NoDuplicateNamedSlots P)
    (hAslots : NoDuplicateNamedSlots A) :
    ∃ σ : SlotPerm GroupId Slot, NamedExtends P (permuteLayout σ A) := by
  sorry

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
    (hExtend : PartialSlotPermExtends (GroupId := GroupId) Slot)
    (hPHOM : P_HOM Feasible)
    (hFeasibleWellFormed : ∀ A, Feasible A → NoDuplicateNamedSlots A)
    (hReject : LiftableReject Feasible P)
    (hPslots : NoDuplicateNamedSlots P) :
    AnonMultisetNogood Feasible P := by
  sorry

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
  sorry

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
    (hExtend : PartialSlotPermExtends (GroupId := GroupId) Slot)
    (hPHOM : P_HOM Feasible)
    (hFeasibleWellFormed : ∀ A, Feasible A → NoDuplicateNamedSlots A)
    (hReject : LiftableReject Feasible P)
    (hPslots : NoDuplicateNamedSlots P)
    (hPatternNoAlias : NoPresenceKeyAlias presenceKey P)
    (hFaithful : PresenceKeyFaithfulForPattern presenceKey Feasible P) :
    BooleanPresenceNogood presenceKey Feasible P := by
  sorry

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
  · native_decide
  · native_decide
  · intro A hFeasible hContains
    change A = singlePoseLayout at hFeasible
    subst A
    exact (by native_decide : ¬ Orbit.AnonMultisetExtends duplicatePosePattern singlePoseLayout) hContains

end NoRepeatCounterexample

end ZmdDesignStatements
