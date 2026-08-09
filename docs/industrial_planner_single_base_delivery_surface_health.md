# IndustrialPlanner single-base current surface health

> **Boundary (2026-06-26):** This document describes the frozen IndustrialPlanner postprocess/adapter surface from the April 2026 delivery line, not the current P1.2 solver or authenticated release state. Here, “current” means current within that delivery surface. Nothing in this workflow may mint, infer, or publish proof-bearing `CERTIFIED`.

This note describes the smallest checked-in health snapshot for the active
IndustrialPlanner single-base consumer surface.

It does **not** replace the richer no-drift audit. Instead it compresses the
already-converged surface-alignment summary down to three small files at the top
of `data/examples/industrial_planner/`:

- `current_surface_health.json`
- `current_surface_health.md`
- `current_surface_health.txt`

## What problem it solves

The detailed no-drift audit under
`.artifacts/industrial_planner_single_base_delivery_surface_alignment/` is still
useful when you need full per-check drift detail.

But a lot of consumers only need one tiny answer:

- is the current single-base consumer surface clean or drifting?
- how many checks were run?
- how many drift checks fired?
- which active release / delivery status does that verdict apply to?

The compact health snapshot exists so CI, reviewer tooling, and small automation
scripts can read that answer without parsing the larger audit payload first.

## Source of truth

`current_surface_health.*` is derived from:

- `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json`
- `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md`
- `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt`

So the detailed surface-alignment audit remains the underlying source of truth.

## Build command

```bash
python scripts/build_industrial_planner_single_base_delivery_surface_health.py
```

That writes the checked-in defaults:

- `data/examples/industrial_planner/current_surface_health.json`
- `data/examples/industrial_planner/current_surface_health.md`
- `data/examples/industrial_planner/current_surface_health.txt`

## Promotion-chain behavior

`build_industrial_planner_single_base_delivery_release.py` now also writes the
compact current-surface health snapshot after the converged surface-alignment
audit finishes clean.

That means a successful release promotion now leaves behind both:

- the full audit summary for detailed drift diagnosis
- the compact health snapshot for zero-parse status checks

## Scope boundary

This artifact is still intentionally scoped to the active
`valley4_protocol_core` 70×70 single-base line.

It does not widen support to other bases, and it does not claim the full-scale
70×70 exact `CERTIFIED` end-state is already finished. That status remains an
honest `open` until the solver-side exact campaign really lands it.
