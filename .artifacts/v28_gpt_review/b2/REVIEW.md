# Phase 1.2 spike close review — strict soundness/sizing audit

Package under review: `phase1_2_spike_review_v28.zip`

Verified package sha256:

```text
c00a957c73f1a05b532de73451aff8676fc0e3303dfc453bd62630e4b06e5253  /mnt/data/phase1_2_spike_review_v28.zip
```

## Executive verdict

**Decision: (b) spike evidence is not sufficient to close Phase 1.2 yet.**

The prod-scale sizing evidence is broadly reproducible and the F9 single-group sizing invariant is correct as a *vector-size* statement. However, the reviewed package still contains accepted cut certificates that can be forged into false-positive cuts. Because `PROJECT_LOCK.md` requires **Exactness FP = 0**, Phase 1.2 should not be closed until the attached soundness patches, or equivalent repairs, land and are re-run through the cut-family regression suite.

This is not a request to rework the overall LBBD/cut-family paradigm. It is a narrow fail-closed hardening requirement for certificate validation.

## Verification run summary

Commands run from the unpacked package and patched overlay:

```bash
# Original package
cd /mnt/data/work2/pkg/_phase1_2_pkg_v28/project
PYTHONPATH=. python -m pytest src/tests/cuts -q
PYTHONPATH=. python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py

# Patched overlay
cd /mnt/data/work2/patched_project
PYTHONPATH=. python -m pytest src/tests/cuts -q
```

Observed results:

| Check | Result |
|---|---:|
| Original cuts suite | `418 passed in 4.97s` |
| Patched cuts suite | `425 passed in 5.46s` |
| Type-pool poses | `81,795` |
| Concrete/group-expanded master proxy | `325,747` |
| F9 current single-group max | `784` |
| F9 same-template stress proxy | `4,608` |
| F9 all-manufacturing stress proxy | `11,644` |
| F4 group-expanded proxy | `20,157` |
| OR-Tools linear proto bytes/term | `4.03` at 784 tail terms; `4.01` at 5429 tail terms |
| OR-Tools BoolOr/no-good bytes/term | `10.01` at 784 tail terms; `10.00` at 5429 tail terms |

Logs are included under `logs/`.

---

## A. Soundness findings

### Finding A1 — CRITICAL: F5 `pattern_nogood` accepts slot-colliding forged cores

**Files:**

- `src/cuts/families/pattern_nogood.py`
- regression tests: `src/tests/cuts/test_family_pattern_nogood.py`

**Original issue:** `_validate_forbidden_pose_pattern` checked group existence, `pose_id ∈ pose_domain`, and exact duplicate triples, but did not require:

1. `slot_index < state.groups[group_id].demand`,
2. uniqueness of `(group_id, slot_index)`, and
3. per-group literal count not exceeding group demand.

The bug is especially dangerous because F5 certificates are slot-indexed, while the generic literal evaluator intentionally drops slot identity and evaluates a `(group, pose)` multiset. A core that is UNSAT only because one anonymous slot is assigned two different poses can therefore be lifted into a stronger no-slot multiset cut.

**Formal counterexample:**

Let one group `g` have `demand(g)=2` and pose domain `{pA, pB}`. Consider forged F5 core

```text
[(g, 0, pA), (g, 0, pB)]
```

An oracle re-query over slot assignments can report this core infeasible because a single slot 0 cannot take both `pA` and `pB`. But the evaluator's multiset condition is equivalent to requiring selected poses to contain both `(g,pA)` and `(g,pB)`. The feasible assignment

```text
slot 0 -> pA
slot 1 -> pB
```

satisfies demand and pose-domain constraints, yet the lifted multiset cut fires. Thus the original validator can accept a certificate whose evaluated cut prunes a feasible layout, violating `Exactness FP = 0`.

**Patch:** fail closed unless every F5 literal references a real unique anonymous slot. Added adversarial tests for slot collision and out-of-range slot.

---

### Finding A2 — CRITICAL: F9 `density_envelope` accepts arbitrary too-low `max_allowed_area`

**Files:**

- `src/cuts/families/density_envelope.py`
- `src/cuts/oracles/density_envelope_oracle.py`
- regression tests: `src/tests/cuts/test_family_density_envelope.py`

**Original issue:** `_validate_max_allowed_area` recomputed a static safe upper bound

```text
safe_ub = |W| - |(ghost ∪ exterior) ∩ W|
```

and accepted any certificate value `K = max_allowed_area` with `K <= safe_ub`. This proves only

```text
true_area(W,g) <= safe_ub
```

It does **not** prove

```text
true_area(W,g) <= K
```

for any smaller `K`.

**Formal countermodel:**

Let `W` contain 100 unblocked cells, so `safe_ub=100`. Let group `g` have a legal 3x3 pose fully inside `W`, giving a feasible state with `area_g(W)=9`. A forged certificate sets `K=0` and supplies that pose as an overflow witness. The original validator sees `0 <= 100`, recomputes witness overlap `9 > 0`, and accepts. The evaluator then cuts the feasible state with `area_g(W)=9`.

The failed inference is the invalid implication:

```text
(true_area <= safe_ub) and (K <= safe_ub)  ==>  true_area <= K
```

A single model with `true_area=9`, `K=0`, `safe_ub=100` falsifies it.

**Patch:** fail closed for `K < safe_ub` until F9 carries a replayable proof that the tighter area cap is valid. The generator is also guarded so it emits no nontrivial F9 cut unless `max_allowed_area == safe_ub`. This is intentionally conservative and effectively quarantines current nontrivial F9 cuts; to recover F9 performance, add a proof-carrying area-capacity subcertificate and validate it instead of trusting `K`.

**Sizing note:** this finding does not invalidate the F9 vector-size conclusion. It invalidates certificate tightness, not the single-group lowering size.

---

### Finding A3 — HIGH: F6 `shape_packing_hall` trusts per-side `region_demand` above source-of-truth lower bound

**Files:**

- `src/cuts/families/shape_packing_hall.py`
- `src/cuts/oracles/shape_packing_hall_oracle.py`
- regression tests: `src/tests/cuts/test_family_shape_packing_hall.py`

**Original issue:** the validator checked `region_demand <= group_demand` and rough geometry bounds, but it did not independently prove that `region_demand` instances are forced onto the named baseline side. For `left_or_bottom_boundary`, total demand may be split between left and bottom.

**Formal bound:**

For a group with total demand `D`, region `R`, opposite region `R'`, and opposite-side capacity `C_other`, the only source-of-truth lower bound for placements forced into `R` by capacity alone is

```text
forced_R >= max(0, D - C_other)
```

Proof: at most `C_other` instances can be placed in `R'`. Therefore at least `D - C_other` instances must be outside `R'`, i.e. in `R`, when this value is positive. Conversely, for any `k > max(0, D-C_other)`, the inequality alone does not force `k` placements into `R`; a split with `D-k` or more in `R'` remains algebraically possible unless an additional certificate proves otherwise.

**Counterexample:**

Let `D=30`, pose length `3`, and opposite baseline packable capacity `C_other=23`. The forced lower bound on the left side is `7`. A forged `region_demand=23` can pass the old validator and create a Hall cut for a side that only 7 instances are forced to occupy. A feasible split with 7 left and 23 bottom is then incorrectly pruned.

**Patch:** recompute the opposite-baseline capacity from the state and reject `region_demand > max(0, group_demand - other_capacity)`. The generator applies the same guard to overrides. To regain stronger incumbent-side F6 cuts, the certificate should either be literal-conditioned on the incumbent side assignment or carry a replayable proof that those specific instances must be on that side.

---

### Finding A4 — MED/HIGH hardening: F7/F8 should also pin hard-coded template dimensions to `canonical_rules`

**Files:**

- `src/cuts/families/power_hitting_set.py`
- `src/cuts/families/power_grid_reach.py`
- regression tests:
  - `src/tests/cuts/test_family_power_hitting_set.py`
  - `src/tests/cuts/test_family_power_grid_reach.py`

**Status:** v28 already fixed the HIGH F7 radius fail-open by checking `power_coverage_radius` against `state.canonical_rules`. The same source-of-truth pattern should be applied to hard-coded footprints used by F7/F8:

- `power_pole` must be canonical `2x2`, and
- F8 `protocol_core` must be canonical `9x9`.

**Why this matters:** radius and footprint jointly define geometric coverage/reach. If canonical rules later change a footprint but the validator continues using a stale helper size, the certificate is no longer source-of-truth checked. That is the same class as the F7 radius bug, though I did not find a concrete current-data false positive under v28's existing canonical file.

**Patch:** added fail-closed checks against `state.canonical_rules.facility_templates.{power_pole,protocol_core}.dimensions`, plus regression tests for dimension drift.

---

### Finding A5 — no same-axis numeric fail-open found in F1-F4

I did not find the F7-style numeric source-of-truth fail-open pattern in F1-F4:

- **F1 region_capacity** recomputes region cells, demand, capacity, and `cells_per_pose` from state/templates.
- **F2 cutset** recomputes cut edges and commodity demand through the registry/state.
- **F3 port_exposure** checks the front cell, blocker cell owner/pose, and port relation; no trusted capacity/radius scalar was found.
- **F4 component_reach** recomputes BFS components and route endpoints from state/candidate placement data.

This is not a formal proof over all future refactors; it is the result of the current v28 code review on the F7 sibling-fail-open axis.

---

## B. Sizing-math review

### Reproduced numbers

The sizing gate reproduces the claimed core values:

```text
type-pool total poses: 81795
concrete master var upper proxy: 325747
F9 current single-group max: 784
F9 same-template proxy max: 4608
F9 all-manufacturing cross-group proxy max: 11644
F4 component_reach group-expanded max: 20157
linear proto bytes/term: 4.03 / 4.01
BoolOr no-good bytes/term: 10.01 / 10.00
```

### F9 single-group invariant

The F9 **single-group vector bound is sound in the current implementation**:

1. A density-envelope certificate carries one `group_id`.
2. The validator rejects any assignment witness whose group differs from the certificate group.
3. The evaluator counts only cells owned by that certificate group.
4. Watcher keys are keyed to that one group.

Therefore a single current F9 cut cannot, through the family validator/evaluator path, expand to all-manufacturing scale. The `11,644` value is correctly labeled as a cross-group stress proxy, not the current per-cut vector bound. `784` is the current single-group per-cut sizing bound, assuming the downstream master translator preserves the same one-group semantics.

### Remaining sizing boundary

The concrete master proxy `325,747` is still a sizing/counting proxy, not a built and solved full concrete `PoseBoolExactMaster`. P1.3A should keep the existing guard: cap and log `len(final_concrete_literals)` after group/template/optional expansion, plus cumulative proto budgets by constraint kind.

---

## C. Phase-boundary decision

**Chosen option: (b) do not close Phase 1.2 yet; close after specific evidence.**

Required close evidence:

1. Land F5 slot-domain/unique-slot validation or equivalent.
2. Land F9 fail-closed quarantine or implement a replayable proof for tight `max_allowed_area`.
3. Land F6 source-of-truth lower-bound validation or condition the cut on a proved side assignment.
4. Land F7/F8 canonical template-dimension guards or document and prove why the hard-coded dimensions cannot drift from `canonical_rules`.
5. Re-run full `src/tests/cuts` with the new adversarial tests. The attached overlay gives `425 passed`.
6. Add a P1.3A assertion/telemetry point that logs final concrete literal count per cut after all expansions, not just type-pool proxies.

**Formal reason not to close now:**

Let the Phase 1.2 close criterion include “all active cut-family validators are sound: every accepted cut has FP=0.” Findings A1 and A2 construct accepted original-v28 certificates `C` and feasible states `S` such that the evaluator returns true on `C,S`. Hence `∃ C,S: accepted(C) ∧ feasible(S) ∧ prunes(C,S)`. This directly negates the universal soundness criterion `∀ C,S: accepted(C) ∧ feasible(S) -> not prunes(C,S)`. Therefore the present evidence is insufficient to certify that criterion.

---

## D. Doc-currency / reproducibility

I checked the top-level README, `project/README.md`, spike `verdict.md`, `RESULTS.md`, and `sizing_gate.py` around the authoritative current numbers and the known stale-claim traps.

No stale authoritative claim was found for:

- cuts tests: `418` in the original package,
- F3 micro-probe: `12/12`,
- remap audit: `36/150` pairs ≈ `24%`,
- type-pool `81,795`,
- concrete proxy `325,747`,
- F9 `784 / 4,608 / 11,644`,
- F4 `20,157`, and
- the F9 single-group/stress-proxy distinction.

The docs explicitly mark old values such as `9`, `36/50`, and MSB-first F1 decoding as historical/stale context rather than current facts.

---

## E. Exactness constitution / scope creep

I did not find evidence that the package promotes exploratory caps into exact bounds, lifts F9 across instances, or treats exploratory artifacts as certified proof. The main constitution violation risk is narrower and more severe: some validators can accept certificates whose scalar/literal payload is not fully source-of-truth justified, contradicting the `Exactness FP = 0` invariant.

The attached patches are fail-closed. They may reduce cut emission, but false negatives are allowed by the lock while false positives are not.

---

## Patch map

The zip contains both an overlay and a git-style diff:

- `patched_files/` — copy this directory over the project root.
- `phase1_2_spike_close_soundness_patches.gitdiff` — reviewable diff against v28.
- `apply_overlay.sh` — helper script.

Patched source files:

```text
src/cuts/families/density_envelope.py
src/cuts/families/pattern_nogood.py
src/cuts/families/power_grid_reach.py
src/cuts/families/power_hitting_set.py
src/cuts/families/shape_packing_hall.py
src/cuts/oracles/density_envelope_oracle.py
src/cuts/oracles/shape_packing_hall_oracle.py
src/tests/cuts/test_family_density_envelope.py
src/tests/cuts/test_family_pattern_nogood.py
src/tests/cuts/test_family_power_grid_reach.py
src/tests/cuts/test_family_power_hitting_set.py
src/tests/cuts/test_family_shape_packing_hall.py
```

Recommended apply/verify:

```bash
cd project
/path/to/apply_overlay.sh .
PYTHONPATH=. python -m pytest src/tests/cuts -q
PYTHONPATH=. python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py
```
