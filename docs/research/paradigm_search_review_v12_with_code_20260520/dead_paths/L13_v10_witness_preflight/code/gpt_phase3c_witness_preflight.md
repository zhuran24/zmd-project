# Phase 3C witness preflight reducer (2026-05-16)

## Why v8 anchor slicing was not enough

The v9 smoke evidence shows that ghost anchor slicing reduced build cost, but it did not reduce the dominant solve tree.  A single 27x15 anchor slice still carried 3,853,132 mandatory pose literals and stayed UNKNOWN after five minutes.  The bottleneck is therefore mandatory facility placement, not the first ghost-anchor choice.

## New reducer

`EXACT_MASTER_WITNESS_PREFLIGHT=1` enables a witness-only preflight lane inside the existing master time budget.  It uses the full mandatory placement hint that already exists after greedy plus community blueprint merge, computes ghost anchors whose cells do not overlap that mandatory witness, and solves a cloned CP-SAT model with these fields forced:

- mandatory slot `x`
- mandatory slot `y`
- mandatory slot `mode`
- one compatible ghost anchor literal

Residual optional facilities remain free.  Existing Benders cuts are present because the lane clones the current master model at the current iteration.

## Exactness contract

The lane is positive-certificate only.

- If the forced clone is FEASIBLE or OPTIMAL and a solution can be extracted, the parent master may use that solution as an ordinary FEASIBLE incumbent and continue through diagnostic flow, exact binding, and exact routing.
- If the forced clone is INFEASIBLE, UNKNOWN, incomplete, timed out, or cannot extract a solution, the parent candidate is not marked INFEASIBLE.  The controller falls back to the normal master solve with the remaining master budget.
- If the lane consumes the whole master budget without a witness, the parent result is UNKNOWN, never INFEASIBLE.

This differs from hard-fixing a blueprint as a proof of optimality.  It can certify a concrete witness, but it cannot rule out all other placements.

## Env variables

```bash
EXACT_MASTER_WITNESS_PREFLIGHT=1
EXACT_MASTER_WITNESS_PREFLIGHT_SECONDS=30
EXACT_MASTER_WITNESS_PREFLIGHT_MAX_ANCHORS=16
```

`EXACT_MASTER_WITNESS_PREFLIGHT_SECONDS=0` means the preflight may use the full per-candidate master budget.  This is exact but usually too aggressive for exploration.

## Recommended smoke command

```bash
EXACT_COMMUNITY_BLUEPRINT_HINT_PATH=data/hints/blueprint_2026_05_13_master_hint.json \
EXACT_MASTER_WITNESS_PREFLIGHT=1 \
EXACT_MASTER_WITNESS_PREFLIGHT_SECONDS=30 \
EXACT_MASTER_WITNESS_PREFLIGHT_MAX_ANCHORS=32 \
python -m src.search.outer_search ...
```

## Telemetry

Proof summaries now include:

```json
"master_witness_preflight": {
  "enabled": true,
  "attempted": true,
  "accepted": true,
  "status": "FEASIBLE",
  "reason": "forced_witness_accepted",
  "candidate_anchor_count": 2464,
  "compatible_anchor_count": 123,
  "anchor_attempt_count": 1,
  "accepted_anchor_idx": 42
}
```

`master_last_solve.forced_witness_preflight=true` indicates that the installed master solution came from the cloned forced-witness validation solve.
