## Round 3 Verdict
NOT_GO

## Round 2 Fix Verification
- **BLOCKER safe_ub static formula: NEW_GAP** — The Round 2 fix correctly identified the TOCTOU bug and made `safe_ub` static. However, it failed to realize that making `safe_ub` static makes it mathematically impossible for `recomputed_sum` to strictly exceed `safe_ub`. `recomputed_sum` is the union of valid cells in $W$, which is bounded by the total valid cells in $W$ (which is exactly the static `safe_ub`). Thus `recomputed_sum > safe_ub` is impossible. The ONLY reason the tests still pass is because of a pre-existing BLOCKER bug in the validator (see Finding #1) that allows the oracle to claim a tighter, unproven bound (e.g., `cert_max = 0`), which satisfies `recomputed_sum > cert_max` but results in a trivially unsound cut.
- **HIGH validator union excludes ghost: CORRECT** — The validator now correctly excludes ghost/exterior cells, perfectly matching the evaluator's semantics (which iterates `cell_owner` and thus never sees ghost cells).

## New Findings (round 3)

1. **[SEVERITY=BLOCKER] src/cuts/families/density_envelope.py:316 — Validator accepts unsound tighter bounds (`cert_max <= safe_ub`)**
   **Issue summary:** The validator checks `if cert_max > safe_ub: return _vr("unsound", ...)`. This logic is backwards. `safe_ub` is the maximum area the validator can *prove* is available. If the oracle provides a `cert_max` that is *smaller* than `safe_ub`, it is claiming a tighter bound for which the validator has no proof. By accepting `cert_max < safe_ub`, the validator allows the oracle to inject trivially unsound cuts that prune valid solutions.
   **Reproduce:** 
   ```python
   def test_unsound_cut_accepted():
       state = _make_state() # safe_ub = 100
       # Oracle maliciously or buggily sends cert_max = 0
       cert_payload = _make_density_envelope_cert(
           max_allowed_area=0,
           assignment_witness=[["g1", "p_3x3_a"]] # area = 9
       )
       cut = _make_density_envelope_cut(cert_payload)
       vr = validate_density_envelope(cut, state, canonical_rules={})
       assert vr.kind == "ok" # PASSES!
   ```
   The cut asserts `area <= 0`, pruning any valid placement of the group.
   **Suggested fix:** The validator must enforce `cert_max >= safe_ub` (or exactly `== safe_ub`). However, see Finding #2 before implementing this.

2. **[SEVERITY=BLOCKER] src/cuts/families/density_envelope.py — F9 is mathematically dead under static capacity**
   **Issue summary:** If Finding #1 is fixed (enforcing `cert_max >= safe_ub` for soundness), F9 can never generate a cut. 
   Proof:
   1. `safe_ub` is exactly the number of cells in `window_cells \ static_blocked`.
   2. `recomputed_sum` is the size of `occupied_cells`, which is explicitly constructed as a subset of `window_cells \ static_blocked`.
   3. Therefore, `recomputed_sum <= safe_ub` is a mathematical certainty.
   4. The strict overflow check requires `recomputed_sum > cert_max`.
   5. If we enforce `cert_max >= safe_ub` for soundness, we require `recomputed_sum > safe_ub`, which is impossible.
   Even if `safe_ub` were tightened to include demand (`group.demand * max_pose_area`), `recomputed_sum` is bounded by that too, so the impossibility holds. F9 only worked previously because it used dynamic capacity (TOCTOU) or allowed ghost cells in the union. As a static, single-group area cut, it is fundamentally a paradox.
   **Suggested fix:** F9 must be redesigned or removed. To express "this window is too full", the cut must include the variables of other groups (e.g., `area(g) <= static_capacity - sum(area(other))`), which requires a multi-group evaluator and schema. A constant-bound static cut for a single group is unworkable.

3. **[SEVERITY=MINOR] src/cuts/families/density_envelope.py:187 — Multiset count allows duplicate identical poses**
   **Issue summary:** `_validate_assignment_witness` uses `Counter(pairs)` to cap instances per pose to `group_demand`. This allows the witness to contain the exact same pose multiple times (e.g., `[("g1", "p1"), ("g1", "p1")]`). While physically meaningless (instances would perfectly overlap), it doesn't cause soundness issues because `recomputed_sum` uses set union, so duplicates add 0 area. However, it's semantically weird.
   **Suggested fix:** Cap the count of each identical pose to 1 (`if count > 1:`), or leave as is since it is mathematically harmless.