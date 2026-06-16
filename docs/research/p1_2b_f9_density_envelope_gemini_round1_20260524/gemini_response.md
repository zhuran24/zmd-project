## Verdict
NOT_GO

## Findings (severity-sorted)
1. [BLOCKER] `src/cuts/families/density_envelope.py:333` — Validator and Evaluator diverge on area counting (Sum vs Union), leading to infinite loops.
   - Reproduce: Create a witness with two overlapping poses (or two instances of the same pose) such that their sum of cells in `W` is 18, but their union is 9. Set `max_allowed_area = 10`. The validator's `_recompute_assignment_area_overlap` computes the sum (`total += 1` for each cell), so it sees 18 > 10 and accepts the cut. However, the evaluator's `evaluate_geometric_density_envelope` counts unique cells in `state.cell_owner`, computing the union. It sees 9 <= 10 and returns `False`. The cut is added but fails to fire on the exact witness that generated it, causing the solver to infinite loop.
   - Suggested fix: Change `_recompute_assignment_area_overlap` to compute the union of cells:
     ```python
     occupied_cells = set()
     for (g, p) in witness_pairs:
         # ...
             if cell in window_cells:
                 occupied_cells.add(cell)
     return len(occupied_cells)
     ```
     *(Note: The generator's oracle-side check in `density_envelope_oracle.py` will automatically inherit this fix since it calls the same helper).*

2. [HIGH] `src/cuts/families/density_envelope.py:223` — Total witness instances can exceed group demand.
   - Reproduce: For a group with `demand=2`, provide a witness with 3 distinct poses: `[["g1", "pA"], ["g1", "pB"], ["g1", "pC"]]`. The `Counter(pairs)` logic only checks if the count of *each specific pose* exceeds demand (`1 <= 2` for all three). It passes validation, but the total number of instances used (3) exceeds the group's actual demand (2). This allows the oracle to artificially inflate the area and generate mathematically unsound cuts.
   - Suggested fix: Add a check for the total length of the witness multiset:
     ```python
     if len(pairs) > group_demand:
         return _vr("unsound", t0, f"total witness instances {len(pairs)} > group demand {group_demand}")
     ```

3. [HIGH] `src/cuts/oracles/density_envelope_oracle.py:133` — Multiset order of `oracle_assignment_witness` violates canonical form / anonymity.
   - Reproduce: Call `generate_density_envelope_cuts` twice with the same `assignment_witness` but permuted (e.g., `(("g1", "p1"), ("g1", "p2"))` vs `(("g1", "p2"), ("g1", "p1"))`). The list comprehension `[[g, p] for (g, p) in assignment_witness]` preserves the input order, resulting in different JSON bytes, different `cert_hash`es, and different `cut_id`s for mathematically identical cuts. This defeats the cut store's deduplication.
   - Suggested fix: Sort the witness pairs before adding them to the payload dictionary:
     ```python
     "oracle_assignment_witness": sorted([[g, p] for (g, p) in assignment_witness]),
     ```

## Sanity arguments
- **Dynamic `safe_ub` soundness**: `safe_ub` depends on `cell_owner_other`, which is safe because `watcher_keys_density_envelope` watches all cells in `W`. If `cell_owner_other` changes inside `W`, the cut is correctly invalidated. If it changes outside `W`, `safe_ub` is unaffected, so the cut remains valid (optimal behavior).
- **`raw_cell` bool conversion**: `int(True) == 1` is safe because `occupied_cells` comes from trusted `state.candidate_placements`, not the untrusted cert payload.
- **`GHOST_AGNOSTIC` string comparison**: Safe and correctly rejects ghost-agnostic cuts per the F9 invariant.
- **Evaluator fail-safe**: Returning `False` on malformed payloads is safe because validated cuts in the store are guaranteed to be well-formed.
- **70x70 grid bounds**: Mathematically correct (`x + h <= 70` correctly allows `x=69, h=1` and rejects out-of-bounds).
- **`exterior_blocks` changes**: Correctly handled by `exterior_blocks_hash` in `CutScope`, which will cause a cache miss if the exterior geometry changes, preventing unsound retroactive cuts.

## Gemini self-summary
In this round 1 cross-check of the F9 density_envelope cut family, I focused heavily on the mathematical invariants and the LBBD trust boundaries. I found a critical blocker where the validator computes the sum of overlapping areas while the evaluator computes the union, which would lead to accepted cuts failing to fire on their own witnesses (causing infinite loops). I also identified two high-severity issues: the validator fails to cap the total number of witness instances against the group's demand (allowing artificially inflated area claims), and the generator serializes the witness multiset without sorting, violating canonical form and breaking cut deduplication. The dynamic `safe_ub` logic, however, is soundly protected by the region watchers.
