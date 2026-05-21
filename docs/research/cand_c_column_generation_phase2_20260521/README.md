# Phase 2 — Column Generation: share cache + Ryan-Foster + 160/266 + routing-aware + boundary equality

Date: 2026-05-21
Paradigm: cand C (column generation / branch-and-price)
Predecessor: `cand_c_column_generation_phase1_20260521/` — 4/4 ramp GO
(5/20/40/80 inst, m10 integer reconstruction True, m11 nodes 11/33/53).

## v3 status (2026-05-21 update — A3 + A1 land)

Phase 2 v2 (commit 3844aea) verdict NO-GO on 160 / 266 inst — both ramps
exit at `rmp_INFEASIBLE_at_iter_0` even though the 3-layer bootstrap
assembled 218 / 324 columns covering all instances individually.  Root
cause: 70×70 grid + 266 facility instances ≈ 96% cell utilisation
forces the column pool into an internal cell-exclusivity vs.
exactly-1 partition contradiction — no λ vector simultaneously
satisfies all `Aλ = 1` and all cell `Σλ ≤ 1` constraints with the
generated bootstrap pool.

v3 implements the **A3 set-covering + A1 alternative-blueprint
combination** (decided 2026-05-21 by user after triage):

- **A3 (default ON)**: instance coverage constraint relaxed from
  `Σ_k λ_k [iid∈k] = 1` to `≥ 1`.  This restores LP feasibility on
  every ramp that has at least one valid pose per instance.
  Soundness: the LP relaxation is an over-approximation (any
  partition solution is a valid covering solution).  The **integer
  reconstruction phase** still enforces partition exactly-1 — see A3
  branching changes below.

- **Integer leaf strict check** (in `ryan_foster.py`): natural
  integer leaf is *only* accepted if `Σ_k λ_k [iid∈k] = 1` (exactly)
  for every instance.  LP integer solutions with over-cover are
  branched: the smallest fractional λ_k contributing to the
  most-over-covered instance is forced to 0 via a synthesised
  Ryan-Foster `diff(i, j)` decision between the two iids in that
  column.  See `_is_partition_exactly_one`,
  `_select_over_cover_branch_column`.

- **m10 validator** (`integer_validator.py`) was already strict on
  partition exactly-1 via `check_set_partitioning` — it raises
  `ValidationError` on any over-cover.  Phase 2 v3 keeps this
  unchanged; the branching change above ensures the
  validator gets a partition-feasible candidate, not an over-cover
  one that would fail-close.

- **A1 (default OFF)**: alternative blueprint generator
  (`alternative_blueprint_generator.py`).  When env-enabled, after
  any CG iteration where the LP returns OPTIMAL but over-covered
  instances exist, the loop detects high-congestion cells (load ≥
  0.85 by default) and generates 2-12 facility multi-facility
  columns that hard-avoid those cells.  Re-solves RMP after each
  round.  Caps at 3 rounds per CG iter, 10 alternatives per round.

  A1 is intended as the fallback when A3 alone leaves the integer
  phase capped out (≥ 30% of ramps UNPROVEN).  Sounds expensive but
  per-round wall is bounded: 60 regions × ≤ 3 s + dedup +
  set-covering RMP solve (typically < 5 s on the augmented pool).

### env flags

| Env | Default | Effect |
|---|---|---|
| `EXACT_CANDC_LP_SET_COVERING` | `1` | A3 set-covering LP; `0` reverts to v1/v2 set-partitioning. |
| `EXACT_CANDC_A1_ALTERNATIVE_BP` | `0` | A1 alternative-blueprint hook; `1` enables. |
| `EXACT_CANDC_A1_CONGESTION_THRESH` | `0.85` | Cell load ≥ threshold flagged congested. |
| `EXACT_CANDC_A1_MAX_PER_ROUND` | `10` | Alternative count cap per round. |
| `EXACT_CANDC_A1_MAX_ROUNDS` | `3` | Rounds per CG iter (each round = detect + generate + re-solve RMP). |

### v3 dry-run + measurement command

```bash
# Dry-run (no measurement written, ≤ 1 min).
cd /home/zhuran24/claude-pj/zmd
.venv/bin/python -u docs/research/cand_c_column_generation_phase2_20260521/phase2_probe.py --dry-run

# Full measurement (6 ramps, expect 8-10 hr wall).  A1 stays OFF unless
# A3 measurement returns ≥30% UNPROVEN.
.venv/bin/python -u docs/research/cand_c_column_generation_phase2_20260521/phase2_probe.py --measure

# Optional: A3 + A1 combined experiment.
EXACT_CANDC_A1_ALTERNATIVE_BP=1 \
    .venv/bin/python -u docs/research/cand_c_column_generation_phase2_20260521/phase2_probe.py --measure
```

### v3 metric additions (telemetry only — no GO threshold change)

| Field | Description |
|---|---|
| `set_covering_on` | A3 was active on this ramp (default True) |
| `a1_enabled` | A1 hook was env-enabled (default False) |
| `a1_rounds_total` | total A1 rounds executed across all iters |
| `a1_alternatives_total` | total alternative columns added by A1 |
| `over_cover_iter_counts[]` | per-iter count of LP over-covered iids |
| `over_cover_iters_nonzero` | how many CG iters had over-cover signal |
| `rf_leaves_kind.over_cover_branched` | RF branched on over-cover |
| `rf_leaves_kind.over_cover_rejected` | RF abandoned at over-cover (no fix) |

### Soundness summary

LP relaxation (A3) is **less constrained** than the underlying
set-partition problem — any partition feasible solution is LP
feasible.  The LP optimum is a lower bound on the partition optimum.
Integer reconstruction (branch-and-price natural leaf + m10 validator)
still enforces partition exactly-1; over-cover integer LP solutions
are not valid integer leaves and are explicitly branched.  m10
remains the sound-check gate — any reported integer leaf passes
`check_set_partitioning` strict (which already raises on over-cover).

## v2 status (2026-05-21 update)

Phase 2 v1 (commit 73ea69a) sweep finished NO-GO with three classes of
critical failure:

1. **Bug 1 P0 (FIXED in v2)** — 160/266-inst bootstrap RMP infeasible at
   iter 0.  Root cause: Phase 1 `degenerate_singleton_columns` greedy
   cannot find a disjoint singleton cover for every instance once the
   pose pool is squeezed by ghost-rect filtering plus
   boundary_storage_port's tiny pool (134 poses).  Fix: new
   `feasibility_bootstrap.py` with 3-layer fallback:

   - Layer 1: try `solve_direct_mini_master` on the whole free grid
     (60s time limit) and harvest its assignment as singleton columns.
     OPTIMAL/FEASIBLE → return immediately.
   - Layer 2: if Layer 1 fails (or as supplementary diversity), run a
     region-by-region multi-facility CP-SAT generator that maximises
     facility count per region (≤ 5s per region, cap 60 regions).
   - Layer 3: Phase 1 singleton greedy as the safety net — merged with
     Layer 2 output to top up.

   The merged pool guarantees `Aλ = 1` LP feasibility on every instance
   that admits at least one ghost-rect-compatible pose.  Phase 1 ramps
   fall through to Layer 1 (succeeds quickly) so no behavioural drift.

2. **Bug 2 P1 (FIXED in v2)** — `RF branching: nodes=N leaves=0` at
   80-inst and 80inst_routing_aware ramps.  Root cause analysis from
   the v1 results JSON: 20/40 ramps hit `leaves=2` and `leaves=1` at
   depth-cap 5, but 80-inst's residual fractional pair set is larger
   so depth 5 wasn't enough to make the LP integer feasible.  Fix:

   - Rewrote `ryan_foster.py` with per-node telemetry
     (`BranchNodeTrace`) so we can diagnose leaves=0 post-hoc — every
     node now records `(decisions, lp_status, lp_obj, fractional
     pairs, integer feasibility, pool_kept/total/killed_by_last)`.
   - Default max_depth bumped from 5 → 10.  Caller still passes its
     own value.
   - At-depth-cap behaviour: instead of silently abandoning the node,
     attempt `_attempt_rounded_leaf` — greedy round of fractional λ_k
     in descending order, accept iff no cell conflict and every
     instance covered exactly once.  Records `leaf_kind="rounded_at_cap"`.
   - Added `branch_and_price_with_fallback` — if RF B&P returns
     `leaves_found == 0`, automatically falls back to Phase 1's
     `branch_and_price_depth_first` (most-fractional λ branching) so
     m10 integer reconstruction still has a chance to pass and m14
     records `"RF failed, std fallback used"`.

3. **Bugs 3-5 P2 (DEFERRED to Phase 3)** — boundary equality RMP
   infeasible + routing-aware m10 inconsistency.  These overlap with
   GPT v13's cut-language thesis (region capacity cut, port exposure
   cut, proof object lifecycle).  The two variant ramps
   (`80inst_routing_aware`, `80inst_boundary_eq`) are **excluded** from
   Phase 2 v2's default ramp sweep — see `default_ramps()` for the
   commented-out lines.  `--only-ramp 80inst_routing_aware` still
   works as an experimental knob; their thresholds remain in
   `GO_THRESHOLDS_BY_RAMP`.

Status: v2 probe written, dry-run rc=0, measurement queued for
background scheduling.  Expected wall: 6 baseline ramps without the 2
variants ≈ 8-10 hr (v1 was 12 hr including the 2 deferred variants).

## What changes from Phase 1

Phase 1 verified the paradigm survives integer reconstruction on 5-80
instances.  Phase 2 lifts to production scale (160/266 instances) and
adds the three pillars that Gemini round-2 review flagged as gating:

1. **Shared pricing pose-index cache** (`pricing_cache.py`)
   Phase 1 each ramp rebuilt `enumerate_poses_in_region` from scratch
   per region.  Phase 2 builds one union pose pool + per-cell index +
   per-instance index, then serves region queries by intersection.
   - Data structure: dict-based.  `PricingShareCache.pose_records` is
     `Dict[(tpl, pose_idx), PoseRecord]` (Phase 1 dataclass duck-typed).
     `cell_index: Dict[(x, y), List[(tpl, pose_idx)]]` for cell queries
     (used by `query_region_poses` when we need cell-set membership).
     `instance_pose_index: Dict[iid, List[(tpl, pose_idx)]]` for the
     instance-tied lookup that pricing CP-SAT needs.
   - Ghost-rect filter pre-applied at cache-build time so per-iter
     pricing doesn't re-check.
   - m13 = `cache_hit_rate` = hits / (hits + miss_fallback).  By
     construction we serve 100% from the index unless the region falls
     outside the precomputed grid (which we never do in Phase 2).

2. **Ryan-Foster branching** (`ryan_foster.py`)
   Phase 1 used most-fractional-λ branching (single column var).  Phase
   2 picks a *fractional pair* (i, j) — two instance ids both covered
   by some fractional column — and branches:
   - `same(i, j)`: pricing enforces `sum_p z[i, p] == sum_p z[j, p]`.
   - `diff(i, j)`: pricing enforces `sum_p z[i, p] + sum_p z[j, p] <= 1`.
   RMP-level: column pool is masked — columns inconsistent with the
   active decision set get λ_k upper-bound 0.
   - Node schema: `BranchNode(decisions: Tuple[BranchDecision, ...], depth)`.
     `BranchDecision(i, j, kind)` with canonical `i <= j`.
   - Pair selection: pair whose fractional cover is closest to 0.5
     (most balanced — strongest fractional resolution).
   - m14 = `rf_nodes / std_nodes` ratio.  Threshold ≤ 0.5 (i.e. RF
     halves the standard-branching tree).  Measured on 20/40/80 ramps.

3. **160 / 266 instance ramp** (in `phase2_probe.py::default_ramps`)
   Adds two new sizes on top of Phase 1's 5/20/40/80.  Thresholds for
   m1, m2, m4 widen for the larger sizes; m15 caps RSS hard at 24 GB
   (target 12 GB).

4. **Routing-aware pricing seed** (`routing_aware_pricing.py`)
   Phase 4 will run a real routing subproblem; Phase 2 seeds it with:
   - Perimeter port-direction bonus: pose ports paired with their
     own perimeter edge get a small additive reward in the pricing
     reduced cost.  Weight 0.05 — well below typical dual magnitudes
     so it never dominates feasibility, only breaks ties.
   - Rent's-Rule cap: at most `K=3` distinct (io, dir) commodity
     classes per column (Gemini Q3).  Implemented via CP-SAT
     class-indicator booleans (one per class, AddMaxEquality with
     OnlyEnforceIf fallback).
   - Dual source: there is no separate "routing dual" yet (Phase 4
     adds it).  Phase 2 derives the routing-aware seed entirely
     inside the pricing CP-SAT objective; the dual it produces for
     the *existing* set-partition coverage constraints is the same
     dual we already pulled in Phase 1.  The Rent's cap and bonus
     bias *which columns* pricing generates, not which duals the
     RMP exposes.
   - Variant ramp `80inst_routing_aware` measures m16 = m5 multi%
     under routing-aware pricing.  Threshold ≥ 30% (must not drop
     below the baseline floor).

5. **Boundary equality constraints in RMP** (`boundary_constraints.py`)
   Phase 1 froze `BoundarySignature`; Phase 2 wires it into the LP:
   - Encoding: per-(cell, dir) net-flow equality:
     `sum_k λ_k * (n_in(k, cell, dir) - n_out(k, cell, dir)) == 0`.
     This is the linear projection of "input matches output at every
     shared boundary slot" onto λ.
   - Granularity: per-cell-direction (not aggregated per region).
     Reasoning: routing in Phase 4 will need per-slot equality, so
     measuring dual sparsity at *that* granularity here gives the
     directly-comparable signal.
   - Variant ramp `80inst_boundary_eq` measures m17 = dual sparsity
     (pct of constraints with |dual| ≥ 0.1).  Threshold ≤ 30% (target
     ≤ 10%) — high active rate predicts Phase 4 routing infeasibility.

## File map

```
__init__.py                       (empty — package marker)
pricing_cache.py        ~180 LOC  Task 1 — share cache
ryan_foster.py          ~220 LOC  Task 2 — RF branching
routing_aware_pricing.py ~230 LOC Task 4 — routing-aware seed
boundary_constraints.py ~190 LOC  Task 5 — boundary equality
phase2_probe.py        ~770 LOC  main entry + 8 ramps + metric
README.md              this file
```

Total ≈ 1840 LOC + README + tests = well under 3500 LOC cap.

## Metric set (Phase 1 m1-m12 + Phase 2 m13-m18)

| Metric | Description | Phase 2 threshold |
|---|---|---|
| m1   | generated columns | size-scaled (266: 60K) |
| m2   | pricing p95 wall | ≤ 120 s on 266-inst |
| m3   | RMP LP p95 wall | ≤ 10 s |
| m4   | peak RSS | ≤ 24 GB on 266-inst (= m15 hard cap) |
| m5   | multi-facility column % | ≥ 30% |
| m6   | singleton column % | ≤ 50% |
| m7   | pricing vars / direct master vars | ≤ 0.50 |
| m8   | mini exactness sound check | True |
| m9   | proxy dual active / sparsity % | ≤ 30 / ≤ 20 |
| m10  | integer reconstruction valid | True (also reported as m18) |
| m11  | RF branching nodes | size-scaled (266: 5000) |
| m12  | avg facilities/column | ≤ 15 |
| m13  | share cache hit rate | ≥ 0.80 |
| m14  | RF vs std nodes ratio | ≤ 0.5 |
| m15  | 160/266 RSS hard cap | ≤ 24 GB |
| m16  | routing-aware m5 | ≥ 30% |
| m17  | boundary equality dual sparsity | ≤ 30% |
| m18  | full-pool integer reconstruction | True |

## GO / NO-GO

**Phase 2 GO** (all of):
- 8 ramps (5/20/40/80/160/266 + 2 variants) all per-ramp verdict GO.
- m13 ≥ 0.80 once measured (cache supplies 100% by construction).
- m14 ≤ 0.5 on at least 20/40/80 (where std baseline runs).
- m15 ≤ 24 GB.
- m17 ≤ 30%.
- m18 True on every ramp.
- pricing p95 ≤ 120 s on 266-inst.

**Phase 2 NO-GO** triggers (any one):
- 160 / 266 RSS > 24 GB or system OOM.
- RF branching nodes > 1000 on 266-inst (degeneration).
- Routing-aware pricing pushes m5 below 30% (paradigm-killing
  side-effect).
- Boundary equality dual sparsity > 50% (Phase 4 will be infeasible).

## Failure modes

- **Cache too coarse**: if pricing CP-SAT builds dominate wall time
  irrespective of cache, the share cache buys nothing.  Mitigation:
  measure m2 before vs after Phase 1.  Phase 1 80-inst pricing p95
  was 20.1 s; Phase 2 target 12-15 s after cache hit.
- **Ryan-Foster degeneracy**: pair selection might keep picking the
  same (i, j) on different paths.  Mitigation: pair selection skips
  pairs already decided (Phase 2 `select_ryan_foster_pair` filters).
- **Rent's cap kills feasibility**: K=3 might be too tight; ramp
  `80inst_routing_aware` is the canary.  If m16 < 30%, raise K to 4
  in Phase 3.
- **Boundary equality dual blow-up**: if every slot has a non-zero
  dual, the equality constraint is over-restrictive for the LP
  geometry — flag for Phase 4 routing relaxation.

## How to run

```bash
# Dry-run smoke (no measurement written; just sanity checks the
# share cache, RF pair selection, routing-aware pricing path, and
# boundary equality RMP).
cd /home/zhuran24/claude-pj/zmd
.venv/bin/python -u docs/research/cand_c_column_generation_phase2_20260521/phase2_probe.py --dry-run

# Full measurement (8 ramps).  Expect 10-15 hr wall-clock.
.venv/bin/python -u docs/research/cand_c_column_generation_phase2_20260521/phase2_probe.py --measure

# Or restrict to a single ramp:
.venv/bin/python -u docs/research/cand_c_column_generation_phase2_20260521/phase2_probe.py \
    --measure --only-ramp 80inst --only-ramp 80inst_boundary_eq
```

Output files:

- `phase2_results.json` — per-ramp metrics + verdict.
- `phase2_status.json` — exit status, peak RSS, elapsed seconds.

## Connection to Phase 4

Phase 2 doesn't close the loop yet — there is no real routing.  The
boundary equality dual (m17) is the lowest-cost evidence that the
Phase 1 `BoundarySignature` schema can carry the Phase 4 routing
information without RMP explosion.  Routing-aware pricing is the
*seed* — Phase 4 swaps the Rent's-Rule cap for a real reduced-cost
component sourced from the routing subproblem's dual.

If Phase 2 verdict is GO, Phase 3 is "pricing CP-SAT
acceleration" (warm-starts, parallel-pricing, primal heuristics) and
Phase 4 is "real routing closure".
