# CLAUDE.md — Endfield IndustrialPlanner Exact Solver

## Project Overview

70x70 grid exact maximum empty rectangle solver for Arknights: Endfield IndustrialPlanner.
Objective: `max_lex(area, min_side)` — maximize area first, then min-side.
266 mandatory facility instances, OR-Tools CP-SAT, Benders decomposition (master -> binding -> routing -> flow).

## Exactness Constitution (from PROJECT_LOCK.md)

- `certified_exact` and `exploratory` are **strictly separate paths**. Never mix them.
- Exact objective is `max_lex(area, min_side)`. `min_side >= 6` is admissibility, not tie-break.
- No hard `50 power poles + 10 storage boxes` cap in exact mode — that's exploratory-only.

## Forbidden Changes

- Reintroducing exploratory caps as exact-mode bounds
- Treating exploratory artifacts as certified proof
- Changing campaign/artifact/proof schemas without updating lock/spec/test together
- Rebinding globally pooled resources into per-line hard bindings without new proof basis
- Adding exterior-path requirement for the ghost rectangle

## Source of Truth

Certified path is grounded in:
- `rules/canonical_rules.json` (consolidated preprocess/recipe/target/commodity truth)
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

Everything under `src/adapters/`, `src/render/`, `data/exports/`, `data/examples/` is **postprocess-only** — never redefines solve schemas.

## Architecture

```
main.py                          # Entry point
src/search/outer_search.py       # Outer candidate loop + frontier
src/search/benders_loop.py       # Benders decomposition (LBBD)
src/models/master_model.py       # CP-SAT placement master
src/models/exact_coordinate_master.py  # Ghost rectangle enforcement
src/models/binding_subproblem.py # Port binding
src/models/routing_subproblem.py # Grid routing
src/models/flow_subproblem.py    # Multi-commodity flow diagnostic
src/search/exact_campaign.py     # Campaign persistence + resume
src/search/exact_parallel_scheduler.py  # Multi-process parallel waves
```

## Active Scope

- Single base: `valley4_protocol_core` 70x70 only
- Other bases (`valley4_infra_outpost`, `wuling_protocol_core`, etc.) are `future_scope`
- Outer-deployment subsystem is adapter-side `future_scope`

## Current Phase: 3B Optimization / Acceleration

- Phase 3A (delivery/productization): Complete, release `r20260416`
- Phase 3B (full-scale exact proof): In progress
- Acceleration plan: `docs/phase3b_repair5_acceleration_tuning_ai_plan.md`
- 4 lanes: A=safety/observability, B=deterministic tuning, C=AI sidecar, D=runtime diagnostics
- AI is shadow-only sidecar: no proof source, no formal pruning, no checkpoint writes

## AI Safety Contract

AI modules may ONLY:
- Suggest candidate ordering (order_only)
- Classify UNKNOWN/UNPROVEN results
- Explain tuning experiments
- Suggest CP-SAT hints (as hints, not constraints)

AI modules must NEVER:
- Delete candidates or declare infeasibility
- Write to `data/checkpoints/`, `data/solutions/`, `data/blueprints/`
- Modify certified proof source or campaign hash
- Change final preflight semantics
- Authorize final 168h production run

## Commands

```powershell
# Run solver (default certified_exact mode)
python main.py --campaign-hours 168.0 --parallel-processes 4

# Run tests
python -m pytest src/tests/ -q

# Single-base e2e workflow
python scripts/run_industrial_planner_single_base_e2e.py --run-dir .artifacts/industrial_planner_single_base_e2e

# Visualization only
python main.py --vis
```

## Dependencies

- Python 3.13
- ortools (9.15.6755), pydantic (>=2), numpy, matplotlib, psutil, pandas, jsonschema, Pillow

## Conventions

- All changes touching exact boundaries must update: PROJECT_LOCK.md, FILE_STATUS.md, relevant spec, relevant tests
- Postprocess/adapter changes don't need lock updates but must not widen proof semantics
- Test with `python -m pytest src/tests/ -q` before any commit
- `_codex_archive/` contains historical Codex (GPT) workspace artifacts — read-only reference, not active code
