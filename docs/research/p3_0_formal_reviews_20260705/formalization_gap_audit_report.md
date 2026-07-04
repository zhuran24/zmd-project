# P3.0 formalization-gap adversarial audit

Scope: compare the nine compiled Lean statements in `TnsCoverage.lean` and `F5OrbitLift.lean` against the authoritative v3 design prose in `terminal_no_solution_evidence_contract_design_v2.md` and `p1_3_f5_orbit_lift_soundness_design_v2.md`. Build/proof correctness was not re-audited. The sandbox has no `lean`/`lake`, so the proposed Lean patch is a text-level patch that should be followed by `lake build` and the axiom audit script in the target environment.

Final judgement: **修后可**. The TNS statements are a good abstract mathematical baseline once README stops implying that schema/seal/oriented-key engineering is machine-checked. The F5 file is useful as a lemma bank, but as-is it must not be advertised as having formalized the full v3 theorem 2. The missing bridge is `anon_lift_sound`: finite same-group permutation extension from anonymous per-group multiset containment to a named representative.

## BLOCK-1 — F5 theorem-2 coverage is overstated

Location:
- Design: `p1_3_f5_orbit_lift_soundness_design_v2.md` §2.3, lines 50-58. The theorem has three premises and concludes: any labelled solution whose per-group selected-pose multiset contains `[π₀]` is infeasible.
- Lean: `F5OrbitLift.lean`, `labeled_orbit_lift`, lines 31-42. It proves only a fixed named-pattern transport along a supplied `σ`.
- Overclaim sites: `README.md` line 27 and `p3_0_formal_verification_head_start_design_v1.md` lines 61-64.

Finding: `labeled_orbit_lift` is a correct core lemma, not the full v3 theorem 2. The missing quantifier/constructor is: from `Realizes A_g pattern_g` for every group, construct a product of finite same-group permutations `σ ∈ Π_g S_{n_g}` such that `σ(A)` extends the named oracle core. The design proof explicitly uses finite bijection completion on lines 56-58; the Lean file says this is future `anon_lift_sound`, so the README row claiming theorem-2 coverage is too large.

Repair: keep the core lemma, add an explicit same-group/bijective wrapper to pin the intended design shape, and downgrade the README/P3 prose to “core lemma, full anonymous theorem pending”. The patch adds:

```lean
/-- σ 不跨组:每个 slot 的 group id 在 σ 后保持不变。 -/
def GroupPreserving {Slot Group : Type} (grp : Slot → Group)
    (σ : Slot → Slot) : Prop :=
  ∀ s, grp (σ s) = grp s

/-- 带设计稿“保群置换”显式前提的包装版。 -/
theorem labeled_orbit_lift_group_preserving {Slot Pose Group : Type}
    (grp : Slot → Group)
    (P : (Slot → Pose) → Prop)
    (σ : Slot → Slot)
    (_hBij : Function.Bijective σ)
    (_hGroup : GroupPreserving grp σ)
    (hHom : ∀ L, P L → P (fun s => L (σ s)))
    (p : List (Slot × Pose))
    (hNogood : ∀ L, Matches L p → ¬ P L) :
    ∀ L, Matches L (p.map (fun sp => (σ sp.1, sp.2))) → ¬ P L := by
  exact labeled_orbit_lift P σ hHom p hNogood
```

## CONCERN-1 — `hHom`/P-HOM abstraction is legitimate, but the same-group semantics must not disappear from the correspondence table

Location:
- Design: theorem 1 says `σ∈G` and label-invariance/P-HOM, lines 30-46; theorem 2 premise 1 references it at lines 50-52.
- Lean: `labeled_orbit_lift` accepts an arbitrary `σ : Slot → Slot` plus `hHom : ∀ L, P L → P (L ∘ σ)`, lines 36-40.

Finding: this is not a theorem bug. It is a useful discovery: the named transport proof only needs one-way `P` preservation for the given `σ`. However, the design theorem’s `σ∈G` condition is what justifies `hHom` in the system and what makes the anonymous-to-named construction possible. Therefore the Lean theorem is stronger as pure math but narrower as a formalization of the system theorem.

Repair: the wrapper above and README boundary text make this explicit. The same-group/P-HOM gate remains an external assumption, not a Lean-checked model fact.

## CONCERN-2 — `dedup_collapse_strengthens` proves strict semantic strengthening, not by itself an actual false reject

Location:
- Design: no-duplicate/alias premise and false-positive rationale, `p1_3...` line 53.
- Lean: `F5OrbitLift.lean`, `dedup_collapse_strengthens`, lines 86-98.
- README: line 30 says “误杀”.

Finding: the current theorem proves `∃ L, Realizes L [v] ∧ ¬ Realizes L [v,v]`. That is necessary evidence that presence dedup makes the match predicate stronger. It does not by itself exhibit a predicate `P` for which the original `[v,v]` nogood is sound while the deduped `[v]` cut rejects a `P`-satisfying layout. The README wording “误杀” therefore outruns the theorem.

Repair: add the stronger theorem below and make README distinguish “strict strengthening” from “false reject”.

```lean
theorem dedup_collapse_can_false_reject :
    ∃ (L : Bool → Bool) (P : (Bool → Bool) → Prop),
      (∀ L', Realizes L' (fun _ => True) [true, true] → ¬ P L') ∧
      Realizes L (fun _ => True) [true] ∧
      P L := by
  obtain ⟨L, hOne, hNotTwo⟩ := dedup_collapse_strengthens
  refine ⟨L, (fun L' => ¬ Realizes L' (fun _ => True) [true, true]), ?_, hOne, hNotTwo⟩
  intro L' hR hNotR
  exact hNotR hR
```

## CONCERN-3 — v3 attach presence-key alias is not modeled by `Realizes`

Location:
- Design: `p1_3...` line 53 says the true master key is `(group_id, attach_pose_key(pose_id))`; different `pose_id`s aliasing to the same presence key must fail closed.
- Lean: `Realizes` at `F5OrbitLift.lean` lines 50-57 compares `Pose` values directly.

Finding: `Realizes` is faithful to a per-group pose multiset evaluator over semantic pose equality. It is not faithful to the master attach layer if `attach_pose_key : Pose → Key` is non-injective. That is not a proof bug, but README should not claim the v3 alias guard is machine-covered by the Bool duplicate theorem.

Repair: the patch adds `RealizesKey` and two alias counterexamples, while documenting that production soundness still depends on the validator/attach fail-close.

```lean
def RealizesKey {Slot Pose Key : Type} (L : Slot → Pose) (G : Slot → Prop)
    (key : Pose → Key) (p : List Key) : Prop :=
  ∃ f : Fin p.length → Slot,
    Function.Injective f ∧ (∀ i, G (f i)) ∧ ∀ i, key (L (f i)) = p.get i

theorem presence_key_alias_can_false_reject :
    ∃ (L : Bool → Bool) (key : Bool → Unit) (P : (Bool → Bool) → Prop),
      (∀ L', Realizes L' (fun _ => True) [true, false] → ¬ P L') ∧
      RealizesKey L (fun _ => True) key [key true] ∧
      P L := by
  obtain ⟨L, key, _, hKey, hNotOriginal⟩ := presence_key_alias_collapse_strengthens
  refine ⟨L, key, (fun L' => ¬ Realizes L' (fun _ => True) [true, false]), ?_, hKey, hNotOriginal⟩
  intro L' hR hNotR
  exact hNotR hR
```

## CONCERN-4 — `std_domain_minimal_66` does not prove “minimal antichain = singleton”

Location:
- Design: `terminal_no_solution...` line 43 says the standard domain has covering set `{(6,6)}` and warns general domains can have multi-element minimal antichains.
- Lean: `TnsCoverage.lean`, `std_domain_minimal_66`, lines 96-104.
- README: line 26 claims “标准域最小反链 = 单点”.

Finding: `std_domain_minimal_66` only proves `(6,6)` is a minimal element. It does not prove that every minimal element is `(6,6)`. `std_domain_collapse` already covers the standard domain soundness, so this is not a soundness hole, but it is a correspondence-table overclaim.

Repair: add the exact iff theorem and change the README row.

```lean
theorem std_domain_minimal_iff (a b : Nat) :
    MinimalIn StdDomain a b ↔ a = 6 ∧ b = 6 := by
  constructor
  · intro h
    have h66 : StdDomain 6 6 :=
      ⟨Nat.le_refl _, by omega, Nat.le_refl _, by omega⟩
    have hbelow := h.2 6 6 h66 h.1.1 h.1.2.2.1
    exact ⟨hbelow.1.symm, hbelow.2.symm⟩
  · intro h
    rcases h with ⟨rfl, rfl⟩
    exact std_domain_minimal_66
```

## NOTE-1 — TNS orientation is preserved in the Lean math, but key-parser/oriented-schema discipline is not Lean-checked

Location:
- Design: `terminal_no_solution...` line 43 and O-8 lines 110-113 require `dimwise_ge_oriented_v1`, no transpose, no `(min,max)` canonicalization.
- Lean: `TnsCoverage.lean` lines 14-23 uses ordered arguments `(w,h)` and product order.

Finding: no semantic orientation is lost in `UpwardClosed`; `bad a b` and `bad b a` are different propositions. The product order is the right abstraction. What Lean does not cover is the engineering key discipline: regex parsing, tuple/key/record consistency, and rejecting `6x7` as covering `7x6`. README should call that out as validator layer.

Repair: documentation-only boundary text added.

## NOTE-2 — `Realizes` matches multiset-count semantics under the intended per-group/full-assignment assumptions

Boundary checks:
- Empty pattern: `Fin 0 → Slot` makes `Realizes []` true, matching ordinary multiset inclusion. A cut on the empty pattern would be a global infeasibility claim; that belongs in schema/oracle policy, not this theorem.
- Group size smaller than pattern length: no injective assignment exists, matching “count is insufficient”.
- Same pose multiple times: requires distinct slots, matching multiplicity semantics and exposing why boolean presence cannot carry such cuts.
- Multiple groups: not modeled by this single `G : Slot → Prop`; full theorem must product over groups in `anon_lift_sound`.
- Attach alias: not modeled by equality on `Pose`; covered by the new `RealizesKey` counterexample and by production fail-close.

## NOTE-3 — `hNogood` correctly abstracts liftable reject

Location:
- Design: liftable reject premise at `p1_3...` line 54.
- Lean: `labeled_orbit_lift` line 41 uses `hNogood : ∀ L, Matches L p → ¬ P L`.

Finding: this is the right abstraction boundary. It says the oracle conclusion is a whole-layout nogood, which is exactly the liftable-reject contract after adapter validation. Lean does not and should not prove that `query_liftable` is implemented correctly in this layer.

## NOTE-4 — P3 doc count is stale

Location: `p3_0_formal_verification_head_start_design_v1.md` lines 4 and 54 say 7 theorems, while README and the task describe 9.

Repair: patch updates the count to 9 and softens the F5 summary so it does not claim the full anonymous theorem.
