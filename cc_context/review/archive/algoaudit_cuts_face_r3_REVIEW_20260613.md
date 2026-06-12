# REVIEW.md — cuts round 3 adversarial review

## 0. Intake / reproducibility

- Snapshot accepted: `/mnt/data/zmd_cut_r3_snapshot_b377a2a7.zip`.
- Required sha256: `b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531` — verified, matches the prompt exactly.
- Unpacked repo root: `project/` from the zip. The unpacked tree is a clean archive snapshot but not a `.git` checkout.
- Dependency install: offline wheels from `zmd_py313_linux_x86_64.zip` into Python 3.13; OR-Tools reports `9.15.6755`.
- Public certified default still blocks the pose-bool/cell-pattern hook through the existing env gate. The finding below is therefore an env-gated / future-promotion soundness hardening issue, not a default-path certification exploit.

## 1. Result

本轮不是零 finding。

I found and patched one CUT-R2-H1-family over-cut in the env-gated pose-bool cell-pattern mechanism. Q2 nogood literal scope / `condition_lits` audit did not find a new over-cut. The whole-layout synthetic power witness fail-closed boundary remains intact. V82 persisted `exact_safe_cuts` replay remains telemetry-only in certified mode.

## 2. Finding CUT-R3-H1 — generic utility slots are capacity, not mandatory per-port demand

- Severity: P2 hardening / env-gated soundness. It becomes soundness-critical if `add_routing_port_blocking_cell_cut` is promoted onto a certified proof path without this fix.
- Files: `src/models/pose_bool_exact_master.py:176-201`, `src/models/pose_bool_exact_master.py:226-266`; binding semantics in `src/models/binding_subproblem.py:709-748`, `src/models/binding_subproblem.py:809-820`, `src/models/binding_subproblem.py:1055-1061`.
- Regression: `src/tests/test_wireless_front_consumers_r4.py:154-217`, `src/tests/test_wireless_front_consumers_r4.py:330-451`, `src/tests/test_wireless_front_consumers_r4.py:454-504`.

### What was wrong

The R2 fix correctly refused raw per-cell port cuts unless a side was necessarily active and routing-visible. However, `_profile_port_demands()` still counted `profile.generic_output_slots` as visible output demand unconditionally, and counted `profile.generic_input_slots` toward input-side demand. That is not a per-port activation proof.

For generic outputs, `PortBindingModel` creates one CP-SAT choice per physical generic-output slot over `generic_commodities + ["__unused__"]` (`src/models/binding_subproblem.py:709-748`). The required generic outputs constrain only the number of real commodity assignments (`src/models/binding_subproblem.py:809-820`). `extract_port_specs()` drops `__unused__` and routing-free commodities (`src/models/binding_subproblem.py:1055-1061`). Therefore, with two physical output slots and one required generic output, binding may leave the blocked first physical slot as `__unused__` and route from the second slot. A master-level cell-pattern cut over the first slot would falsely ban a feasible placement.

For generic inputs, the current canonical implementation materializes wireless sink generic inputs as virtual/routing-free slots (`src/models/binding_subproblem.py:771-788`). Counting those virtual slots as physical input-front demand can similarly make `input_demand >= port_count` true without proving that every physical input port on the pose is active.

### Minimal reproducer / proof witness

The pre-patch probe used one `protocol_core`-like pose with two north-facing physical output cells and one required generic output. A blocker occupies the front cell of the first output. The binding model front-filter removes the first slot, assigns `source_ore` to the second slot, and remains feasible. The old cell cut still registered the first port as necessarily visible and made the master infeasible.

Pre-patch output:

```text
profile_demands (0, 6, 0, 6)
mandatory_output_exact True
cell_cut_added True
master_status_after_cut INFEASIBLE
generic_output_slots_post_filter 1
binding_status FEASIBLE
binding_selection {'binding_choice': {'blocker_001': 0}, 'generic_inputs': {}, 'generic_outputs': {'core_001:out:1': 'source_ore'}}
port_specs [{'instance_id': 'core_001', 'x': 1, 'y': 1, 'dir': 'N', 'type': 'out', 'commodity': 'source_ore'}]
```

This is the over-cut shape: `core pose + blocker pose` is a feasible placement with a feasible binding, but the pose-bool cell-pattern cut eliminates it.

Post-patch sanity probe:

```text
profile_demands (0, 0, 0, 6)
mandatory_output_exact False
cell_cut_added False
```

### Patch summary

The patch narrows `_profile_port_demands()`:

- Generic-input slots no longer count as physical routing-visible input demand. Only concrete input-slot demand is used for the input-side `input_demand >= physical_port_count` proof.
- Generic-output slots count as visible output demand only when required generic-output count globally saturates known mandatory generic-output capacity. Under saturation, every generic-output physical slot is forced away from `__unused__`; without saturation, no per-cell active-slot proof exists at master level.
- If mandatory generic-output capacity is not knowable from the master snapshot, the check fails closed by not counting generic-output slots, weakening the cell-pattern cut rather than over-cutting.
- `PROJECT_LOCK.md` and `specs/10_benders_decomposition_and_cut_design.md` now record the tightened generic-slot contract.

The actual code change is in `src/models/pose_bool_exact_master.py:116-201` and `src/models/pose_bool_exact_master.py:252-266`.

## 3. Q1 CUT-R2-H1 repair confirmation

### Q1.1 Input-side fixed-pattern semantics

For concrete non-generic input slots, the R2 predicate is sound: when concrete demand covers all physical input ports on the side, fixed pattern enumeration has no inactive physical port left to choose around. The patched `_mandatory_port_side_is_cell_pattern_exact()` uses concrete routing-visible input demand only (`src/models/pose_bool_exact_master.py:252-256`). This avoids the newly found virtual generic-input overcount.

### Q1.2 Output-side visible/total/demand predicate

The original three conditions were insufficient because `generic_output_slots` was treated as visible mandatory demand even when binding could assign `__unused__`. The patch adds the missing saturation proof. With required generic outputs below known mandatory capacity, the output side is not registered into raw per-cell routing-visible index. With required generic outputs equal to known capacity, the existing cell-pattern strength is preserved by `test_pose_bool_cell_pattern_cut_keeps_saturated_generic_output_side()` (`src/tests/test_wireless_front_consumers_r4.py:454-504`).

Mixed visible + routing-free output sides still fail the `visible_output == total_output` check and remain delegated to the weaker exact lazy-demand/count family.

### Q1.3 `_profile_port_demands()` exception direction

Exception/unknown-profile handling remains fail-closed in the safe direction. `_profile_port_demands()` returns zeros on unknown operation profile, and `_mandatory_port_side_is_cell_pattern_exact()` returns `False` on exception (`src/models/pose_bool_exact_master.py:176-180`, `src/models/pose_bool_exact_master.py:241-251`). That suppresses raw per-cell registration and weakens the cut; it does not strengthen the cut or over-cut placements.

### Q1.4 Global-coordinate cache double-anchor sweep

I re-checked the pose-bool lookup builders after the R2 fix. `_build_port_lookup_cache()` consumes candidate pose `occupied_cells`, `input_port_cells`, and `output_port_cells` as global coordinates, with no anchor re-addition. `_build_global_pose_cache()` also records pose cells directly from `occupied_cells`. I did not find another same-file path that re-applies anchor to candidate pose data for the routing-visible cell-pattern indexes.

## 4. Q2 nogood scope and `condition_lits` audit

No new nogood / `condition_lits` over-cut found in this pass.

### Binding-level nogood literal boundary

Audited registration points:

- Binding safe-reject precheck path: `src/search/benders_loop.py:5278-5284`.
- Routing-infeasible-but-binding-alternatives-remain path: `src/search/benders_loop.py:5818-5819`.

Literal coverage:

- `extract_selection()` records variable-backed binding choices, fixed binding choices, generic input slot choices, and generic output slot choices, including `__unused__` (`src/models/binding_subproblem.py:972-1005`).
- `add_nogood_cut()` adds literals for every variable-backed selected binding choice and every selected generic input/output commodity slot (`src/models/binding_subproblem.py:1090-1106`).
- Fixed binding choices have no CP variable in the current binding model. Their omission from `literals` is not an under-scoping bug because they are invariant within that binding CP instance.
- Generic output `__unused__` is included in `extract_selection()` and has a corresponding CP literal, so two bindings differing only by which physical generic-output slot is unused are not collapsed into one nogood.

Conclusion: the literal set is sometimes larger than a minimal unsat core, which only weakens learning. I did not find a routing-relevant binding dimension that is missing from the literal set and would cause a different binding to be banned accidentally.

### Master placement nogood / conditioned cut boundary

Audited registration points and condition contracts:

- Power subproblem conditioned nogood: `src/search/benders_loop.py:4796-4833`. The code aborts when the selected ghost anchor is unavailable; otherwise it passes both `condition_set={ghost_anchor::(x,y): rect_idx}` and `condition_lits=(u_var,)`.
- Persisted conditioned replay resolver: `src/search/benders_loop.py:1488-1533`. It accepts only supported `ghost_anchor::(x,y)` keys, requires strict integer rect indexes, validates the domain anchor, and returns `ok=False` on mismatch rather than applying the cut unconditionally.
- Persisted cut application: `src/search/benders_loop.py:5997-6043`. The live cut uses `master.add_benders_cut(..., condition_lits=tuple(condition_lits))`, and schema v3 preserves `condition_set`.
- Certified replay boundary: `src/search/benders_loop.py:6430-6479`. In certified mode, persisted `exact_safe_cuts` are not consumed as proof (`raw_candidate_cuts = []`). The resolver remains fail-closed for any hypothetical replay path.
- Cut manager validation: `src/models/cut_manager.py:24-27`, `src/models/cut_manager.py:138-209`. Certified power-conditioned cuts require a condition set whose key and metadata agree. Dedup includes `condition_set` (`src/models/cut_manager.py:419-428`), so ghost-A and ghost-B cuts do not alias.
- Whole-layout conflict builder excludes `ghost_pick` (`src/search/benders_loop.py:5973-5983`), preventing the ghost selector from entering an unconditional facility-pose conflict set.

Other master nogood families inspected:

- Binding-domain-empty / RAB front-blocked placement-local conflict sets include the owner pose and blocker poses only after independent placement-level proof or binding exhaustion. Ghost picks are ignored by occupancy extraction and flow diagnostics, so there is no missing ghost condition in that proof context.
- Routing-front-blocked placement-local fallback builds conflict sets from explicit `placement_level_conflict_set` instance IDs after binding-local alternatives have been handled first. I did not find a condition variable that the proof depends on but the cut omits.
- Exploratory F1-F9 cuts are not on the certified runtime apply path; `step_2_minimize()` and `step_8_apply_to_master()` remain `NotImplementedError`.

### Whole-layout synthetic power witness

The prior fail-closed guard is still present: with `EXACT_POWER_PLACEMENT_SUBPROBLEM` on and a synthetic power-pole witness in the solution, `_add_exact_whole_layout_nogood()` emits `whole_layout_nogood_skipped_power_witness_incomplete` and returns `False` (`src/search/benders_loop.py:6045-6084`). This keeps an incomplete pole witness out of a whole-layout cut.

## 5. Maintenance spot-checks

- V82 persisted `exact_safe_cuts`: certified mode still sets `raw_candidate_cuts = []` before replay (`src/search/benders_loop.py:6430-6447`). Existing replay tests stayed green.
- Lazy routing connectivity cuts: the lock still requires independent W/X certificate validation and fallback to selected-positive nogood (`PROJECT_LOCK.md:111`).
- F1-F9 lifecycle boundary: `step_2_minimize()` and `step_8_apply_to_master()` remain hard stubs (`src/cuts/lifecycle.py:716-725`, `src/cuts/lifecycle.py:1106-1111`).
- C-3/C-4 latent挂账: the P1.3B / F2-F4 capacity checklist remains documented under go criteria (`docs/项目说明/12_go_criteria.md:56-64`). I did not re-report the known owner-tracked items as new findings.

## 6. Validation run

Commands run after the patch:

```bash
python -m py_compile src/models/pose_bool_exact_master.py src/tests/test_wireless_front_consumers_r4.py
python -m pytest -q src/tests/test_wireless_front_consumers_r4.py -p no:randomly
python -m pytest -q src/tests/test_wireless_front_consumers_r4.py src/tests/test_binding.py src/tests/test_benders_cut_condition_lits.py src/tests/test_benders_cut_replay_condition_lifecycle.py src/tests/test_power_witness_cut_dilution.py src/tests/test_v82_persisted_cut_replay_fail_closed.py src/tests/test_p0_certified_soundness_fixes.py -p no:randomly
python -m pytest -q src/tests/cuts -p no:randomly
python scripts/check_p1_2_proof_obligations.py
```

Observed results:

```text
10 passed in 0.36s
66 passed in 3.31s
463 passed in 7.27s
P1.2 proof obligation check passed: 8 obligations anchored
```

I also attempted a full `python -m pytest -q src/tests -p no:randomly`; in this sandbox it did not complete before a 240s timeout and showed no failure before timeout. I therefore rely on the targeted cuts/binding/proof suites above rather than claiming a full-suite pass.
