# Core analysis retained from the formal reply

## Why the previous method failed

The v9 package documents that ghost anchor slicing improved build cost, not solve cost. The decisive telemetry is that a 27x15 single-anchor slice still had 3,853,132 mandatory pose literals and stayed UNKNOWN after a five-minute solve. This means the dominant search tree is mandatory facility placement, not the outer ghost-anchor choice.

## New reduction target

The new lever is a positive-certificate witness lane. When greedy plus the community blueprint hint yields a complete mandatory placement hint, the solver can avoid branching over millions of mandatory pose choices by forcing each mandatory slot's coordinate tuple in a cloned model:

```text
mandatory slot x == hinted x
mandatory slot y == hinted y
mandatory slot mode == hinted mode
one compatible ghost anchor literal == 1
```

Residual optional facilities remain free. Existing Benders cuts remain active because the lane clones the current master model after cuts have been replayed.

## Why this preserves exactness

The forced clone is not used to prove absence. It is only used to find a concrete witness.

```text
forced clone FEASIBLE + extracted solution
=> use as normal master FEASIBLE incumbent
=> still must pass exact binding and exact routing

forced clone INFEASIBLE / UNKNOWN / timeout / incomplete
=> do not mark parent INFEASIBLE
=> fall back to normal master with remaining budget, or UNKNOWN if budget is gone
```

This is intentionally different from hard-fixing a blueprint as the proof target. A failed blueprint-shaped witness says nothing about all other placements.

## What changed

- `src/models/master_model.py`
  - Added `candidate_witness_compatible_ghost_anchors()`.
  - Added `install_solution=True` to `_validate_coordinate_forced_hint()` so a feasible clone can install the solver and extracted solution.
- `src/search/benders_loop.py`
  - Added `EXACT_MASTER_WITNESS_PREFLIGHT` lane inside the existing per-candidate `master_seconds` budget.
  - Added proof telemetry under `master_witness_preflight`.
- `src/tests/test_master.py`
  - Added compatible-anchor scan and clone-install regression coverage.
- `src/tests/test_witness_preflight.py`
  - Added controller-level fail-closed tests.
- `docs/phase3c_witness_preflight_20260516.md`
  - Added the algorithm and exactness contract.
- `docs/env_variable_index.md` and `CHANGELOG.md`
  - Added the new env controls and engineering history.

## Limitations

This does not claim a completed 70x70 campaign or final optimum proof. It lowers search difficulty when a complete mandatory witness is available. If no complete witness exists, or if all forced witnesses fail, the solver returns to the original exact path and may still be UNKNOWN.
