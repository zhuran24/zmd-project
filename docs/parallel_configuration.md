# Parallel Configuration Guide

This document describes runtime resource knobs only. It does not change the objective, candidate
proof contract, supervisor authority or public publish gate.

## Defaults and precedence

Runtime source of truth is `src/models/cp_sat_worker_config.py`. Current built-in per-stage defaults
are:

- master: 8;
- local capacity: 8;
- binding: 4;
- routing: 8.

Precedence is stage-specific `EXACT_*_CP_SAT_WORKERS`, then `EXACT_CP_SAT_WORKERS`, then the built-in
default. Launcher scripts are wrappers around this resolution and must not be treated as proof
sources.

## Process multiplication

Approximate runnable CP-SAT worker pressure is the number of parallel candidate processes multiplied
by each stage's worker count. Memory use is not linear or guaranteed by this arithmetic, so measure
RSS on the actual host. A worker/process setting that avoids OOM does not establish solver
completeness or certification.

## 48GB baseline guidance

These concrete guardrails apply to a 48GB host (project benchmark notes); they are operational
guidance only, not a soundness or certification claim:

- `4` parallel workers: generally safe; prefer `parallel_processes <= 4` on 48GB.
- `5` parallel workers: possible only after confirming the candidate domain and checkpoint set are
  stable.
- `6+` parallel workers: likely swap / severe slowdown; treat as unsafe on 48GB unless you have
  profiled real RSS on the exact same artifact set.

A conservative 48GB profile is `parallel_processes=4`, `master=4`, `local_capacity=4`, `binding=2`.

## Current artifact prerequisite

`data/preprocessed/candidate_placements.json` is present in the audited working tree. Before a
certified run, verify size 45,774,305 bytes and SHA256
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`.
The superseded 45,773,799-byte / SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` artifact predates
the boundary `(0,0)` corner-pose fix and is hash-incompatible.
A lightweight distribution is permitted to omit it, but that distribution policy is not a runtime
waiver.

## Operational guidance

Start with the project wrapper/profile selected in `CLAUDE.md`, then reduce process count or CP-SAT
workers when measured memory headroom is insufficient. Do not change exact/exploratory boundary env
variables merely to fit memory. The certified path's deny-unknown/unsafe-env checks remain in force.

A worker crash, timeout or partial wave is not frontier exhaustion. Resume only when the campaign
inspector reports compatibility with current artifacts and proof-bearing source closure.
