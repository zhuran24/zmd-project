# P0 certified-exact soundness fixes (2026-06-11)

This patch fixes three certified-path soundness defects.  The guiding rule is fail-closed: an uncertain placement or route may become `UNKNOWN`/`TIMEOUT`, but it must not become `CERTIFIED` and must not be cut from the master without exact evidence.

## P0-1 / A-1 — Routing CP-SAT FEASIBLE did not prove source→sink connectivity

### What changed

`src/models/routing_subproblem.py` now validates every CP-SAT incumbent before returning `FEASIBLE` from `RoutingSubproblem.solve()`.

The new guard rebuilds the selected route-state graph per commodity from `r_vars`:

- source fronts are taken from `_source_port_fronts`;
- sink fronts are taken from `_sink_port_fronts`;
- selected route-state arcs follow `flow_out` into the neighbor's matching `flow_in`;
- every source front must reach at least one sink front;
- every sink front must be reachable from at least one source front.

If an incumbent is locally supported but globally disconnected, the solver adds a selected-route nogood and resolves inside the remaining time budget.  If all such incumbents are exhausted, CP-SAT returns `INFEASIBLE`; if the budget expires before a connected incumbent is found, the certified path returns `TIMEOUT` and the Benders loop keeps the candidate non-certified.

### Why this is sound

The existing local predecessor/successor constraints remain necessary.  The new guard adds the missing global implication at the acceptance boundary: `FEASIBLE` is promoted only after graph reachability has been verified against the selected incumbent.  Rejecting a disconnected incumbent by exact selected-state nogood cannot remove a valid connected routing, because it forbids only that exact disconnected route-state assignment.

### Fail-closed boundary

`RoutingSubproblem.solve()` never returns `FEASIBLE` for an incumbent whose reachability proof fails.  Time-budget exhaustion after one or more rejected incumbents returns `TIMEOUT`.

### Env/default-path impact

No env knob is introduced.  Existing routing model construction and local constraints remain in place; only the certified acceptance boundary is tightened.

### Regression evidence

`src/tests/test_p0_certified_soundness_fixes.py::test_routing_feasible_incumbent_requires_source_to_sink_connectivity` forces a locally closed source component plus a separate sink component.  Before the patch the forced incumbent is `FEASIBLE`; after the patch the guard rejects it once and the model proves `INFEASIBLE`.

## P0-2 / B-01 — Coordinate master intervals used template dimensions instead of selected pose footprints

### What changed

`src/models/exact_coordinate_master.py` now derives a footprint token and bounding box from each candidate pose's `occupied_cells` relative to its anchor.  That footprint token is part of the coordinate mode token.

Each coordinate slot now has channelled footprint variables:

- `footprint_dx_min`, `footprint_dy_min`;
- `footprint_width`, `footprint_height`;
- `footprint_x_start`, `footprint_y_start`;
- `footprint_x_end`, `footprint_y_end`.

`mode -> (dx_min, dy_min, width, height)` is enforced with `AddAllowedAssignments`, and `AddNoOverlap2D` receives variable-size intervals built from those footprint channels.  Power selected-geometry witness constraints now use the same footprint start/span channels instead of `slot.x/slot.y` plus template dimensions.

If a candidate pose lacks `occupied_cells`, or if a mode's footprint bounds are unstable after footprint-token splitting, the coordinate backend raises instead of under-approximating geometry.

### Why this is sound

The no-overlap and power-cover witnesses now over-approximate the actual occupied pose cells by the pose's bounding box.  For rectangular footprints this is exact.  For non-rectangular footprints it is conservative: it may reject some feasible packings, but it cannot allow true physical overlap or claim coverage for cells outside the selected footprint span.

### Fail-closed boundary

Missing or unstable footprint evidence fails during model construction rather than silently falling back to template dimensions.  Non-rectangular footprints use a conservative bounding box.

### Env/default-path impact

No env knob is introduced.  Pose-bool and exploratory paths are untouched.  Coordinate certified default behavior is tightened only where the old fixed template span could under-approximate selected-pose geometry.

### Regression evidence

`src/tests/test_p0_certified_soundness_fixes.py::test_coordinate_master_no_overlap_uses_pose_footprint_not_template_dims` builds two mandatory 4x6 vertical poses for a template declared as 6x4.  The two anchors are non-overlapping under the old fixed 6x4 interval model but overlap physically.  Before the patch the model returns `OPTIMAL`; after the patch it returns `INFEASIBLE`.

## P0-3 / A-2 — Binding-local `front_blocked` evidence became a placement-level master cut

### What changed

`src/search/benders_loop.py` now treats routing precheck statuses with `binding_selection_safe_reject=True` as binding-local when binding alternatives remain.  `front_blocked` and `relaxed_disconnected` share the same ladder:

1. add `binding_model.add_nogood_cut(selection)` for the current binding;
2. resolve the binding model;
3. continue with the next binding if one exists;
4. only after alternatives are exhausted, fall through to the existing whole-layout routing-exhausted cut path.

If binding re-solve times out, the run returns `UNKNOWN` with `master_follow_up=fail_closed_unknown`.

### Why this is sound

A blocked front cell depends on the current binding's selected physical port and direction.  It does not prove that every binding for the same placement is blocked.  Enumerating binding-level nogoods preserves all placement alternatives until the binding subproblem itself proves they are exhausted.

### Fail-closed boundary

The patch prevents fallback placement-local nogoods while a binding-local reject can still be resolved by choosing another binding.  Timeout during that enumeration returns `UNKNOWN`.

### Env/default-path impact

No env knob is introduced.  Existing env-off / Path 12/13 behavior remains unchanged except that default certified `front_blocked` evidence no longer writes an unsafe placement-level cut before binding enumeration.

### Regression evidence

`src/tests/test_p0_certified_soundness_fixes.py::test_front_blocked_safe_reject_enumerates_binding_before_master_cut` simulates a first binding that returns `front_blocked` with `binding_selection_safe_reject=True` and a second binding that routes.  Before the patch the loop writes a `routing_front_blocked_nogood`, never calls routing, and ends `INFEASIBLE`; after the patch it adds one binding-level nogood, retries precheck, calls routing once, and returns `CERTIFIED` without an exact-safe master cut.

## Synchronized contract updates

- `PROJECT_LOCK.md`: added invariants for routing incumbent reachability, pose-footprint geometry, and binding-local precheck evidence.
- `specs/09_exact_grid_routing_subproblem.md`: added §9.7 incumbent source→sink reachability acceptance boundary.
- `specs/07_master_placement_model.md`: added §7.8 candidate-pose footprint channels for coordinate master no-overlap/power witnesses.
- `specs/10_benders_decomposition_and_cut_design.md`: added §10.7 binding-local precheck evidence ladder.
- `src/tests/test_p0_certified_soundness_fixes.py`: regression tests for all three P0 fixes.

## Self-checks run

```text
python -m py_compile src/models/routing_subproblem.py src/models/exact_coordinate_master.py src/search/benders_loop.py src/tests/test_p0_certified_soundness_fixes.py
python -m ruff check .
MYPYPATH=$PWD python -m mypy --explicit-package-bases --ignore-missing-imports --follow-imports=silent src/models/cut_manager.py src/models/power_placement_subproblem.py src/models/master_model.py src/search/benders_loop.py
python scripts/check_p1_2_proof_obligations.py
python -m pytest -q --randomly-dont-reset-seed src/tests/test_p0_certified_soundness_fixes.py
python -m pytest -q --randomly-dont-reset-seed src/tests/test_exact_contract.py::test_routing_exhaustion_generates_exact_safe_whole_layout_cut src/tests/test_exact_contract.py::test_routing_timeout_returns_unknown_without_exact_safe_cut
python -m pytest -q -s --randomly-dont-reset-seed src/tests/test_routing.py::test_routing_supports_splitter_state
```

Notes:

- `python -m pytest ...` without `--randomly-dont-reset-seed` can fail in this container before test execution with `pytest_randomly`/NumPy seed range errors.  The same tests pass with seed reset disabled.
- `src/tests/test_routing.py::test_routing_small_solve` still times out in this lightweight environment during routing build/solve and was not used as evidence for this patch.
- Full `scripts/preflight_gate.py` was started and passed checks 1-13 in the visible log, but the run exceeded the local timeout during/after the P1.2 obligation stage.  The standalone P1.2 obligation script passed.
