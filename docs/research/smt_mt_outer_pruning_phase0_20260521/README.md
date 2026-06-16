# SMT-MT Outer Pruning Phase 0 (2026-05-21)

## TL;DR

Phase 0 cheap-gate probe for **SMT Modulo Monotonic Theories** (Bayless et al.,
AAAI 2015) outer-search pruning. Mocks the inner solver with a Dummy
threshold/random verdict and measures whether geometric monotone containment
prunes enough of the candidate pool to be worth Phase 1+ investment.

This is the **23rd-after** paradigm probe (27 lever + 3 Phase 0 verdicts all
dead at session start). Sits orthogonally to candidate C (column generation):
SMT-MT is outer-pruning, CG is inner-quality; they can stack if both GO.

## Monotone property

`ghost_A INFEASIBLE => for all ghost_B s.t. ghost_B contains ghost_A,
ghost_B is INFEASIBLE.`

Reason: the 70x70 grid has 266 mandatory facilities to place. The ghost
rectangle is a reserved empty region. A larger ghost reserves *more* empty
cells and leaves *fewer* cells for facilities — so if the smaller ghost is
already infeasible, the larger one is even tighter.

This is the textbook monotone-theory predicate: a single inner INFEASIBLE
verdict can be lifted to a closed upper set in the candidate lattice.

## Phase 0 design (no inner solver)

Why we can run Phase 0 without finishing the real inner solver: monotone
propagation correctness is purely combinatorial. We just need to verify
that **the propagation yield is high** on a realistic Dummy oracle.

- **Candidate registry**: 4-tuple `(w, h, anchor_x, anchor_y)`. `w, h` from
  `outer_search.generate_candidate_sizes` logic (w in [6, 70], h in [6, w]);
  anchor enumerated explicitly on 70x70. ~2.35M total candidates.
- **R-tree index**: 2D bounding box `(ax, ay, ax+w, ay+h)`. We use
  `rtree` (PyPI 1.4.1, libspatialindex C++ wrapper). Lookup =
  `intersection()` then Python-side full-containment filter.
- **Dummy inner**: area >= 500 -> INFEASIBLE; area <= 100 -> CERTIFIED;
  else random. Crude but realistic-ish: real candidates lose feasibility
  fast as area grows (we hit UNPROVEN/UNKNOWN long before INFEASIBLE in
  production, but the pruning *shape* matches what a true SMT-MT theory
  solver would produce on hard INFEASIBLE rejections).
- **Trial loop**: pick random UNLABELED candidate, run Dummy. On
  INFEASIBLE -> query containment -> mark superset INFEASIBLE. Count.

## Hypothesis (Phase 0 GO/NO-GO)

| metric | meaning | GO threshold | NO-GO threshold |
|---|---|---|---|
| `m1_total_candidates` | Pool size | informational | informational |
| `m2_prune_ratio_after_trials` | fraction labeled INFEASIBLE after 1000 Dummy trials | >= 50% | < 30% |
| `m3_containment_query_p95_ms` | per-query wall p95 | <= 1000 ms | > 5000 ms |
| `m4_rtree_build_seconds` | one-time index build | <= 60 s | (no NO-GO if m2/m3/m5 OK) |
| `m5_rtree_rss_gb_delta` | RSS added by index | <= 2 GB | > 8 GB |
| `m6_prune_by_area_bucket` | per-area-bucket pruned ratio | informational; large-area buckets should dominate | — |

**GO** iff all four (m2, m3, m4, m5) GO. **NO-GO** iff any one tripwire.

## Why this Phase 0 is genuinely cheap

- No src/ edit. Probe is standalone.
- Dummy inner is O(1). Real inner (benders_loop.run_benders_for_ghost_rect)
  averages minutes-to-30min per candidate — Phase 0 finishes in minutes.
- Only one new dep: `rtree` (clean install, no version conflict in
  ortools-9.15 venv).
- ~360 LOC for probe + README. No project-state coupling.

## Failure modes we expect to find

1. **m2 too low** (< 30%). Possible if INFEASIBLE happens mostly on
   *small* candidates (e.g., binding INFEASIBLE on tight rect). Monotone
   propagation goes upward only — small INFEASIBLE prunes large supersets,
   which is *good*, but the small candidates themselves are the bottom of
   the search order. The 50% threshold assumes a healthy fraction of
   large-area Dummy INFEASIBLE.
2. **m3 too slow**. Should not happen for rtree on ~2.4M boxes — the
   spatial index reduces a brute-force O(N) scan to O(log N) plus
   filter-on-intersection. But Python-side intersection iteration could
   blow up if intersection set is huge for very-small query bboxes.
3. **m5 too large**. rtree libspatialindex uses ~200 bytes/entry under
   default settings. 2.4M * 200B = ~480 MB. Should fit easily.

## If Phase 0 GO

Phase 1+ (not in this scope) would need to:

1. Modify `outer_search.py` to explicitly enumerate (size, anchor)
   instead of size-only (current). This is a meaningful refactor — the
   current loop delegates anchor to `master_model`. Estimated 1 week.
2. Wire SMT-MT pruning into `frontier_selection`. Update
   `_compute_frontier_candidate_metrics` to include "already-pruned"
   counter via the rtree.
3. Cross-check: ghost-rect monotonicity is sound iff the inner solver
   has no positive non-monotonic constraint (e.g., "we *want* room for
   power poles" — that's an exploratory cap, banned in certified mode).
   PROJECT_LOCK guarantees this.

## Relationship to other paradigms

- **Candidate C (Column Generation)**: improves inner *quality*. Stacks
  with SMT-MT if both work — SMT-MT prunes the outer candidate space,
  CG strengthens the inner LP relaxation.
- **PCR-CUT / SAC-Hull / RAB-SEP**: are inner cut amplification. Killed.
  SMT-MT is structurally different — it operates above the LBBD loop.
- **D2 Path 17**: tightened binding cut but did not change outer pruning.

## Citation

Bayless, S., Bayless, N., Hoos, H., Hu, A. *SAT modulo monotonic theories.*
AAAI 2015. The original paper covers Boolean monotonicity over predicate
networks; we use a simpler geometric instantiation: `bbox_containment` is
a 2D-poset predicate.

## Run

```bash
# Dry-run (no measurement; verifies imports + enumeration + R-tree toy)
.venv/bin/python -u docs/research/smt_mt_outer_pruning_phase0_20260521/phase0_probe.py \
    --dry-run

# Full Phase 0 measurement
.venv/bin/python -u docs/research/smt_mt_outer_pruning_phase0_20260521/phase0_probe.py \
    --infeasible-trials 1000 --seed 42
```

Output: `phase0_metrics.json` (m1-m6 + GO/NO-GO verdict) in this directory.

Expected wall: a few minutes. Build dominates (~30 s for 2.4M-entry rtree),
trial loop is fast (~1000 * single-rtree-query).
