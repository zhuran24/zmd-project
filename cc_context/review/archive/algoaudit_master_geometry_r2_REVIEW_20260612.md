# IndustrialPlanner geometry master review: bidirectional feasibility fidelity

Snapshot accepted: `zmd_audit_snapshot_6867b7ce.zip`

Verified snapshot sha256 before unpacking:
`6867b7ce75b5aa61efe9864572cc1b2781ea68d07bcf7efeca28a3ec8ee3487b`

Candidate placement artifact also matches the frozen registry in `specs/06_candidate_placement_enumeration.md`: `data/preprocessed/candidate_placements.json`, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, size `45,773,799` bytes.

## Findings

### F-GM-Q3-01: protocol storage lower bound ignored fixed required storage-box slots

Severity: HIGH for coordinate-exact API paths that pass fixed required optional protocol boxes; latent for the default non-pose-bool campaign path in this snapshot, because that path does not appear to pass `_exact_required_pose_optional_counts` into the coordinate delegate.

Files:

- `src/models/exact_coordinate_master.py:5967-6001` after patch, originally the lower-bound block at `5967-5999`.
- Regression: `src/tests/test_exact_coordinate_protocol_bounds.py:1-53`.

Rule / spec basis:

- `PROJECT_LOCK.md:96-100` says protocol storage boxes consume plan-defined wireless generic input slots and the master may derive certified optional lower bounds from the shared fail-closed generic I/O loader.
- `src/models/master_model.py:2030-2055` computes the lower bound as `ceil(sum(required_generic_inputs) / wireless_sink_generic_input_slots)`. For the frozen project demand `qiaoyu_capsule=1`, `valley_battery=1`, and `generic_input_slots=3`, the necessary lower bound is exactly `ceil(2 / 3) = 1`.

Bug:

`CoordinateExactMasterDelegate._prepare_slot_specs()` builds fixed required optional slots first, then skips the residual optional slot pool for the same template when `_exact_required_pose_optional_counts[tpl] > 0` (`src/models/exact_coordinate_master.py:2253-2282`). The original global inequality code later enforced the protocol-storage lower bound only over `self.residual_optional_slots["protocol_storage_box"]`. Therefore this legal configuration was rejected:

- one fixed required `protocol_storage_box` slot,
- zero residual protocol slots,
- generic input demand `2`, wireless slots per box `3`, so required lower bound `1`.

The fixed required slot already satisfies the lower bound, but the old constraint encoded `0 >= 1`, making the master false-INFEASIBLE.

Minimal probe result:

- Before patch: `CpSolverStatus.INFEASIBLE`.
- After patch: `CpSolverStatus.OPTIMAL`.

Fix:

Count fixed required protocol-storage slots as a constant contribution and only require residual active slots for the remaining shortfall:

`residual_active_count >= max(0, lower_bound - fixed_required_count)`

This preserves the previous residual-only behavior when there are no fixed required slots, preserves the existing build_stats schema, and fails closed when the fixed count is insufficient and no residual pool exists.

Frozen artifacts: no canonical rules, candidate placements, preprocessed JSON, or registered hashes were modified. No frozen artifact regeneration is required.

## Q1: no-overlap and footprint bidirectional fidelity

Result: no additional unresolved Q1 soundness finding.

The current frozen pose pool is fully rectangular, so the coordinate master’s bbox representation is exact for this snapshot rather than a conservative over-approximation.

| template | poses | non-rect | missing occupied_cells | relative footprint bounds |
|---|---:|---:|---:|---|
| `boundary_storage_port` | 134 | 0 | 0 | `(0,0,0,2)` x67; `(0,2,0,0)` x67 |
| `manufacturing_3x3` | 17,408 | 0 | 0 | `(0,2,0,2)` x17,408 |
| `manufacturing_5x5` | 16,368 | 0 | 0 | `(0,4,0,4)` x16,368 |
| `manufacturing_6x4` | 16,380 | 0 | 0 | `(0,5,0,3)` x8,190; `(0,3,0,5)` x8,190 |
| `power_pole` | 4,761 | 0 | 0 | `(0,1,0,1)` x4,761 |
| `protocol_core` | 6,728 | 0 | 0 | `(0,8,0,8)` x6,728 |
| `protocol_storage_box` | 4,624 | 0 | 0 | `(0,2,0,2)` x4,624 |

Mode-channel audit:

- `src/models/exact_coordinate_master.py:962-1004` derives relative occupied cells and builds a footprint key from actual `occupied_cells`.
- `src/models/exact_coordinate_master.py:1650-1681` includes `(orientation, port_mode, footprint_key)` in the coordinate mode token and rejects duplicate `(x, y, mode)` pose keys.
- `src/models/exact_coordinate_master.py:1553-1616` requires a stable footprint bbox for every mode after footprint-token split, and fails closed if `occupied_cells` are missing.
- `src/models/exact_coordinate_master.py:2335-2458` channels `mode -> (dx_min, dy_min, width, height)` through `AddAllowedAssignments`, then builds half-open CP-SAT intervals `[start, start + width)`.
- `src/models/exact_coordinate_master.py:3240-3241` applies `AddNoOverlap2D` to those mode-channelled intervals.

Off-by-one probe:

- `[0,2)` adjacent to `[2,4)` solved `OPTIMAL`.
- `[0,2)` overlapping `[1,3)` solved `INFEASIBLE`.

Therefore the encoded interval boundary is the intended half-open geometry: edge-touching facilities are legal; one-cell overlap is illegal.

Under-prune direction: I found no channel that can select a smaller footprint for a larger true pose. In particular, the 6x4 template has separate footprint bounds for horizontal and vertical orientations, and `port_mode` remains part of the token even for templates where it does not change the footprint.

Over-prune direction: if future canonical data introduces non-rectangular footprints, the no-overlap bbox may reject interlocking L-shape layouts. That would be a conservative approximation explicitly allowed by `PROJECT_LOCK.md:109`; it is not active in this frozen pose pool because all 66,403 footprints are rectangular.

## Q2: ghost rectangle and admissibility

Result: no additional unresolved Q2 soundness finding.

Ghost encoding:

- `src/models/exact_coordinate_master.py:3424-3524` creates one optional ghost interval pair per anchor, `AddExactlyOne` over ghost anchors, and `AddNoOverlap2D` between all core intervals and ghost intervals.
- The ghost intervals are also half-open: `[anchor_x, anchor_x + w)` and `[anchor_y, anchor_y + h)`. The off-by-one probe above applies to this geometry too, so a facility adjacent to the ghost boundary is not rejected.
- I found no exterior-path or connectivity constraint in the ghost encoder. Fully enclosed legal empty rectangles remain allowed, matching `PROJECT_LOCK.md:104` and the forbidden-change clause at `PROJECT_LOCK.md:212`.

Admissibility placement:

- `PROJECT_LOCK.md:11-13` defines `max_lex(area, min_side)` and says `min_side >= 6` is candidate admissibility, not a tie-break.
- `src/search/exact_campaign.py:517-538` loads the canonical floor from `rules/canonical_rules.json::globals.empty_rectangle.min_side_admissibility` and validates the objective.
- `src/search/exact_campaign.py:1119-1125` enumerates candidate widths and heights starting at the admissible minimum.
- `src/search/exact_campaign.py:1663-1666` rejects a terminal certified result whose ghost rectangle falls below the admissibility floor.
- `src/search/certified_frontier.py:321-354` rejects missing/mismatched/sliced terminal-frontier evidence and `src/search/certified_frontier.py:368-372` rejects final results below the admissibility floor.

The coordinate delegate itself assumes the outer campaign supplied an admissible `(w, h)`, which matches `specs/06_candidate_placement_enumeration.md:84-91`.

## Q3: hard-constraint family traceability matrix

| constraint family | implementation | rule / spec basis | fidelity conclusion |
|---|---|---|---|
| Candidate pose domains and bounds | `exact_coordinate_master.py:1553-1616`, `2491-2569` | `specs/06:33-40`, `specs/06:48-64`, `specs/07:113-117` | Exact over current artifact. Missing `occupied_cells` fail closed; non-rect bbox is conservative and lock-authorized. |
| Mandatory placement assignment | `exact_coordinate_master.py:2221-2251`, build flow `3235-3241` | `specs/07:46-48` | One coordinate slot per mandatory instance group member; no optional activation leak. |
| Required optional placement assignment | `exact_coordinate_master.py:2253-2275` | `specs/07:50-57`, lock protocol wireless clauses | Fixed required optional slots are always active. Finding F-GM-Q3-01 repaired their interaction with certified lower bounds. |
| Residual optional activation | `exact_coordinate_master.py:2277-2323`, residual creation around `2834-2918` and power-pole creation around `3100-3195` | `specs/07:50-54` | Activation waterfall is symmetry-only over interchangeable residual slots; no fixed 60 cap. |
| Core no-overlap | `exact_coordinate_master.py:2335-2458`, `3240-3241` | `specs/07:59-62`, `PROJECT_LOCK.md:109` | Exact for current all-rect pool; half-open interval boundary verified. |
| Ghost exact-one and ghost no-overlap | `exact_coordinate_master.py:3424-3524` | `specs/06:84-91`, `specs/07:56-62`, `PROJECT_LOCK.md:104/212` | Exact-one anchor plus no-overlap only. No exterior connectivity requirement found. |
| Power coverage | geometric guard `4917-4951`; table fallback `4953-5003`; selected-geometry witness `5050-5124`; build hook `5598-5680` | `specs/07:64-70`; `PROJECT_LOCK.md:109` | Current powered pose count 54,780: all rectangular. Power-pole coverage cells match expected clipped radius rectangle for all 4,761 poles. Table fallback uses exact `occupied_cells` coverers when geometric support is unsafe. |
| Certified protocol-storage lower bound | `master_model.py:2030-2055`, `exact_coordinate_master.py:5967-6001` | `PROJECT_LOCK.md:96-100` | Formula `ceil(required_generic_inputs / slots_per_box)` is exact as a necessary lower bound. Patched to count already fixed required storage slots. |
| Power-pole upper/capacity valid inequalities | `_power_pole_slot_upper_bound` family in coordinate delegate; global valid inequality stats around `exact_coordinate_master.py:6003+` | `specs/07:64-70`; exact-safe capacity support from candidate pole families | Necessary upper/capacity constraints only. I did not find a default stricter-than-rule engineering cap. |
| Symmetry breaking | coordinate symmetry pass before no-overlap, build flow `3235-3241` | `specs/07:74-85` | Non-strict/order-key and activation-waterfall constraints act only on interchangeable slots; no physical solution class is removed. |
| Clearance / port-front blocking | not a hard coordinate-master geometry constraint; candidate generation and downstream binding/routing carry port semantics | `specs/06:68+`; binding/routing specs out of this face | No extra exact-coordinate clearance constraint was found that would shrink the placement feasible region beyond candidate domains and no-overlap. |
| Boundary resource pool capacity | candidate pool anchors and mandatory counts in master; commodity/global resource binding is outside this face | `specs/06:60-64`; `PROJECT_LOCK.md:95` | No additional per-line/per-instance master hard binding found. |
| Benders / external cuts | `master.add_benders_cut` family, not a native geometry hard constraint in this review | specs/07 Benders loop context | Not re-audited here except for absence of hidden ghost exterior-path constraints. |

## Q4 spot checks from prior zero-finding claims

1. Footprint rectangularity claim: independently verified over the full frozen pose pool. Result: 66,403 / 66,403 poses have non-empty rectangular `occupied_cells`; 0 non-rectangular; 0 missing.

2. Power coverage exactness claim: independently checked all powered facility footprints and all power-pole coverage cells. Result: 54,780 powered non-pole poses are rectangular; 4,761 / 4,761 power-pole coverage sets equal the expected canonical clipped radius rectangle. In code, `master_model.py:3330-3374` indexes pole coverage cells from `power_coverage_cells`, while `master_model.py:3427-3457` indexes powered pose support from exact `occupied_cells`; the coordinate delegate only uses the geometric witness if `_supports_rectangular_power_coverage()` returns true.

## Verification commands run

Environment: `/mnt/data/zmd_venv313` using sandbox Python 3.13 and offline wheels from `zmd_py313_linux_x86_64.zip`.

Passed:

```bash
/mnt/data/zmd_venv313/bin/python -m pytest -q src/tests/test_exact_coordinate_protocol_bounds.py -p no:randomly
# 1 passed

/mnt/data/zmd_venv313/bin/python -m pytest -q src/tests/test_master.py -p no:randomly
# 226 passed

/mnt/data/zmd_venv313/bin/python -m pytest -q src/tests/test_exact_contract.py src/tests/test_v84_terminal_layout_max_empty_rect.py -p no:randomly
# 91 passed

/mnt/data/zmd_venv313/bin/python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

Also run:

```bash
/mnt/data/zmd_venv313/bin/python -m pytest -q src/tests -p no:randomly
```

The full suite attempt timed out in the sandbox before completion, with progress output only and no failure observed before timeout. I am not claiming a full-suite pass.

## Patch package

Unified diff: `/mnt/data/zmd_geometry_master_audit_patch.diff`

Patch dry-run was checked against the original source/test file set with:

```bash
patch --dry-run -p1 < /mnt/data/zmd_geometry_master_audit_patch.diff
```

Result: both touched paths checked cleanly.
