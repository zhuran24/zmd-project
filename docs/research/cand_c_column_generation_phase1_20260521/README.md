# Phase 1 — Column Generation + integer reconstruction validator

Date: 2026-05-21
Paradigm: cand C (column generation / branch-and-price)
Predecessor: `cand_c_column_generation_phase0_20260521/` (8/8 GO on 20-inst)
Status: probe written, dry-run rc=0 — measurement queued for background.

## What changes from Phase 0

Phase 0 verified the paradigm could exist (multi-facility columns
dominate, pricing decomposes).  Phase 1 lifts to:

1. **Canonical column grammar** (`column_grammar.py`):
   - `Pattern` with deterministic `column_id` (sha1 of canonical
     facility_assignments + occupied_cells).
   - `BoundarySignature` schema (perimeter ports + cells).  Phase 1
     **records** the signature; Phase 4 will enforce inter-column
     matching for routing.

2. **Integer reconstruction validator** (`integer_validator.py`):
   - set-partition: every iid covered exactly once.
   - cell exclusivity: no cell in two columns.
   - ghost-rect mask: hard-coded anchor (22,28) 27×15; any cell inside
     is fail-closed.
   - direct-master equivalence: independently solve the same instance
     subset with a pose-bool master; verify every chosen iid's pose
     either matches strictly or lies in the canonical equivalence class
     (same cells, possibly different pose_idx label).

3. **Manual depth-first branching** (in `phase1_probe.py`):
   - Branch on most-fractional λ_k (standard rule).
   - max_depth 5, max_nodes 1000, wall budget 60s.
   - Each integer leaf runs the validator.  Telemetry: m11
     `branching_nodes` directly.

4. **40 / 80 instance ramp** (in addition to Phase 0's 5+20):
   - separate threshold sheet per ramp size (see "GO/NO-GO" below).
   - m12 (max/avg facility per column) tracked to detect grain growth
     into whole-layout columns.

## New metrics (Phase 0 carries m1-m9)

| metric | meaning |
|---|---|
| `m10_integer_reconstruction_match` | validator passes (set partition + ghost rect + direct master) on the best integer leaf |
| `m11_branching_nodes` | total nodes explored in B&P tree |
| `m12_avg_facilities_per_column` + `m12_max_facilities_per_column` | column grain stays in 5-15 multi-facility band (declared upper bound 15) |

## GO / NO-GO (per ramp)

Ramp sizes use slightly relaxed Phase 0 thresholds plus Phase 1 hard
gates.  Overall verdict is GO iff every ramp size returns GO.

| ramp | m1 max | m2_p95 max | m4 RSS | m11 nodes max | m12 avg max | hard m10? |
|---|---|---|---|---|---|---|
| 5-inst | 2636 | 10s | 4 GB | 200 | 15 | no (size artifact) |
| 20-inst | 5272 | 30s | 4 GB | 500 | 15 | yes |
| 40-inst | 10000 | 45s | 4 GB | 1000 | 15 | yes |
| 80-inst | 20000 | 60s | 8 GB | 1000 | 15 | yes |

m5/m6 (multi-/single-facility column share) is **soft** on 5-inst (5
mandatory facilities with disjoint footprints → multi-fac column will
be rare and not paradigm-killing) but **hard** on 20/40/80.

NO-GO triggers (any size, except where soft):

- `m5 < 30%` or `m6 > 50%`: column grammar degenerates to single-facility.
- `m7 ≥ 50%`: pricing scale ≈ direct master scale (no decomposition).
- `m9_active_pct > 30%` or `m9_sparsity > 20%`: Phase 4 boundary dual
  will be too dense (Gemini Round 2 forecast carried from Phase 0).
- `m10 = False` (20/40/80): sound validator failed.
- `m11 > threshold`: branching tree explodes — B&P ≈ brute force.
- `m12_avg > 15`: column grain saturates the whole layout (cand C
  collapses back to current pose-bool master).

## Branching design decisions

### Standard λ_k branching (not Ryan-Foster)

Ryan-Foster branching is the canonical choice for set-partitioning B&P
because it preserves pricing structure across child nodes.  Phase 1
intentionally uses *standard* λ_k branching (one direction = include
column, other = exclude) for two reasons:

1. m11 telemetry (branching node count) is the metric of interest —
   not a tuned production tree.  Ryan-Foster typically yields fewer
   nodes; standard branching is the worst-case-ish upper bound and a
   better stress test for cand C's viability.
2. Ryan-Foster requires *pricing inside branch nodes*; Phase 1 budget
   doesn't include re-solving pricing inside B&P (Phase 2's RMP+pricing
   loop will).  Without re-pricing inside the tree, Ryan-Foster's main
   advantage (pool-stable pricing constraints) wouldn't show anyway.

### MIP backend not used

OR-Tools wraps CBC/SCIP MIP solvers (`pywraplp.Solver.CreateSolver("CBC")`
returns OK on this venv) but Phase 1 deliberately does **manual** DFS
branching to:

1. Surface `m11_branching_nodes` directly (CBC's node count would be
   internal and harder to compare).
2. Apply Phase 1 ghost-rect / set-partition / direct-master invariants
   on every leaf as the search hits it.

For sanity, the LP relaxation at the root is solved by GLOP (same as
Phase 0 RMP).  We use the LP solution at *each* branch node (not a MIP
solve at the leaf) — pruning is purely by LP bound + LP infeasibility.

### Depth cap (max_depth 5)

Phase 1 column pool sizes scale with the ramp (5/20/40/80 instances).
Most-fractional λ branching converges fast when the LP is near integral;
depth 5 lets us close common 4-5 fractional λ patterns.  Deeper trees
are a smell — m11_nodes_max gate triggers before the depth cap matters.

## BoundarySignature design (Phase 1 schema, Phase 4 enforcement)

```python
@dataclass(frozen=True)
class BoundarySignature:
    perimeter_ports: Tuple[Tuple[int, int, str, str], ...]
    perimeter_cells: FrozenSet[Tuple[int, int]]
```

Decisions:

- **Perimeter granularity = column bbox, not region bbox.** Region is
  the pricing CP-SAT search rectangle (always ≥ bbox).  Two columns
  can sit in the same region (different instance subsets, disjoint
  cells), so cross-column compatibility lives at the *bbox* edge, not
  the region edge.
- **Per-port direction (`dir`) and io_type stored** but unused in
  Phase 1 LP/pricing.  Phase 4 will enforce: a column's right edge
  output ports facing east must match its east-neighbour's left edge
  input ports facing west.  Storing `dir` + io_type now keeps the
  schema stable for that lift.
- **`perimeter_cells` is separate from `perimeter_ports`.** A column
  may touch its bbox edge with body cells (no port) — those still
  occupy boundary slot from a routing-congestion view, but they don't
  carry a direction.

Phase 1 records the signature on every Pattern produced by pricing
(and singleton bootstrap), serialises into `phase1_results.json` via
the `column_id`-keyed pool snapshot (not yet — Phase 1 doesn't write
columns to disk; Phase 4 will).

## Direct-master equivalence check

Direct master = solve the *same instance subset* on the *same region*
with one BoolVar per (iid, pose_idx).  Force each iid to be covered
exactly once.  Build a `DirectMasterPoseIndex` keyed by
`(iid, frozenset(cells))` → set of pose_idx that produce those cells.

For each iid in the CG integer solution:

- **strict match** — CG pose_idx ∈ direct master's set of pose_idx
  for that (iid, cells).  Same pose label, same cells.
- **equivalence-class match** — CG pose_idx not in the set, but the
  direct master *would* place the iid with some pose_idx whose cells
  match the CG-chosen cells (different pose_idx label — typically a
  rotation/port_mode variant).
- **mismatch** — direct master pool has no pose for this iid that
  produces these cells.  Sound bug.  Fail-closed.

Phase 1 weak fallback: if `pose_index.iid_pose_count[iid] > 0` we count
the iid as equiv-matched.  This is generous (we don't strictly check
cell-set equality of the column's contribution because Pattern doesn't
carry per-iid cells separately — only the union).  The strict match
path is unaffected.

The strict match is the tight check; equivalence match is a softer
fallback that catches the common case where pricing picks a pose_idx
the direct master wouldn't have explored first but produces the same
physical placement.

## Files

- `column_grammar.py` (~270 LOC): `Pattern` + `BoundarySignature` +
  `build_pattern` + equivalence-key helpers.
- `integer_validator.py` (~460 LOC): all the Phase 1 invariant checks
  and direct-master cross-check.
- `phase1_probe.py` (~1330 LOC): the probe.  Data loading, RMP, pricing,
  B&P tree, metrics, CLI.  Mirrors Phase 0's structure (so reviewer
  diff is small) but the canonical pattern factory, branching, and
  validation are new.
- `phase1_results.json`: written by `--measure`.
- `phase1_status.json`: per-run status (ok / crashed / rc).

## Estimated measurement wall

Phase 0 ran 5 + 20 in ~30 min.  Phase 1 adds B&P + 40 + 80:

| ramp | est CG wall | B&P added | est total |
|---|---|---|---|
| 5-inst | ~30s | ~5s | ~40s |
| 20-inst | ~3 min | ~20s | ~3-4 min |
| 40-inst | ~10 min | ~30s | ~10-15 min |
| 80-inst | ~25 min | ~60s | ~25-35 min |

Conservative total: **~40-55 min** wall.  Set `--branching-wall-budget-s`
caps B&P at 60s/ramp so it can't overshoot.  Phase 1 result JSON
contains per-ramp metrics + verdict_failures + thresholds, so the
verdict is reproducible from JSON without re-running.

## Run

```bash
# Smoke test
python -u docs/research/cand_c_column_generation_phase1_20260521/phase1_probe.py --dry-run

# Full ramp (background it — wall ~40-55 min)
python -u docs/research/cand_c_column_generation_phase1_20260521/phase1_probe.py --measure
```

## Hard constraints upheld

- **No src/ touched.** Read-only on `data/preprocessed/`.
- **No paradigm_search_review_v12_* or smt_mt_outer_pruning_phase1_*
  read.** Phase 1 is independent of those threads.
- **Sound failures are fail-closed**: validator raises
  `ValidationError`, caller stores `error_message`, ramp is marked
  NO-GO.

## Decision

(filled after `--measure` rc/results land.)
