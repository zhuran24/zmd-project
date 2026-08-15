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

Before a certified run, verify `rules/canonical_rules.json` at 59,989 bytes / SHA256
`c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0`,
`rules/preprocess_plan.json` at 1,383 bytes / SHA256
`5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`, and
`data/preprocessed/candidate_placements.json` at 54,467,709 bytes / SHA256
`f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`.
The 45,774,305-byte `a914…`, 45,773,799-byte `adcc…`, 53,594,995-byte `d5e3…`, and
53,595,501-byte `78e2…` candidate artifacts are a superseded, hash-incompatible historical chain.
A lightweight distribution is permitted to omit it, but that distribution policy is not a runtime
waiver.

All workers must inherit the complete `generic_input_slots_by_operation` map from the same
hash-bound plan snapshot and compare it atomically on resume. The current provider-aware,
instance-aware contract routes finished goods to physical provider inputs and derives a box lower
bound of 0: demand 2 is already covered by the mandatory core's 14 real input ports.

## Operational guidance

Start with the current wrapper/profile documented by [`scripts/README.md`](../scripts/README.md) and
[`AGENT_OPERATIONS.md`](AGENT_OPERATIONS.md), then reduce process count or CP-SAT workers when measured memory headroom is insufficient. Do not change exact/exploratory boundary env
variables merely to fit memory. The certified path's deny-unknown/unsafe-env checks remain in force.

A worker crash, timeout or partial wave is not frontier exhaustion. Resume only when the campaign
inspector reports compatibility with current artifacts and proof-bearing source closure.
