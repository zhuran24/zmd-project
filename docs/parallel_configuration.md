# Parallel Configuration Guide

This document explains how the current certified-exact launcher knobs interact
with CPU threads and memory.

## 1. Current defaults

Runtime source of truth: `src/models/cp_sat_worker_config.py`

Default per-stage CP-SAT workers:

- `master = 8`
- `local_capacity = 8`
- `binding = 4`
- `routing = 8`

Environment precedence:

1. stage-specific env
   - `EXACT_MASTER_CP_SAT_WORKERS`
   - `EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS`
   - `EXACT_BINDING_CP_SAT_WORKERS`
   - `EXACT_ROUTING_CP_SAT_WORKERS`
2. global env
   - `EXACT_CP_SAT_WORKERS`
3. built-in defaults

`main.py` prints the resolved worker profile at startup.

## 2. Why memory scales with parallel workers

The production parallel path uses separate worker processes.
On the current platform, that means `spawn` semantics rather than implicit large-object sharing.
Each worker independently loads large preprocess artifacts such as `candidate_placements.json`
and constructs its own `ExactMasterCore`-side data.
In the current lightweight GitHub checkout, restore that artifact before running
certified parallel workers.

So memory scales roughly with:

`parallel_processes × per-process exact data footprint`

It is not safe to assume that adding more processes is “free” just because CPU utilization looks low.

## 3. 48GB baseline guidance

From the current project benchmark notes, a 48GB machine should treat these as the practical guardrails:

- `4` parallel workers: generally safe
- `5` parallel workers: possible, but headroom is noticeably tighter
- `6` parallel workers: likely to enter swap / severe slowdown territory
- `7+` parallel workers: treat as unsafe on 48GB unless you have measured a lower-memory build path

A good rule of thumb is:

- prefer `parallel_processes <= 4` on 48GB
- only go to `5` after confirming the current candidate domain and checkpoint set are stable
- avoid `6+` unless you have profiled real RSS on the exact same artifact set

## 4. How to trade processes vs per-process workers

When `parallel_processes > 1`, do not keep every stage at the largest worker count.
A smaller per-process worker profile often gives better total throughput because it avoids memory pressure and thread oversubscription.

Reasonable starting points:

### Conservative 48GB profile

- `parallel_processes = 4`
- `master = 4`
- `local_capacity = 4`
- `binding = 2`
- `routing = 4`

### Single-process deep search profile

- `parallel_processes = 1`
- keep defaults, or raise only after verifying the solver benefits on the current candidate

## 5. Which knob to lower first

If the machine is slowing down, paging, or becoming unstable:

1. lower `parallel_processes` first if RSS is the problem
2. lower per-process CP-SAT workers next if CPU oversubscription is the problem
3. avoid changing both aggressively at once unless you are running a clean benchmark sweep

In short:

- **memory pressure** -> reduce `parallel_processes`
- **CPU thrash / oversubscription** -> reduce stage worker counts

## 6. Launcher-script reminder

The PowerShell wrappers under `scripts/*.ps1` do not redefine precedence.
They only pass arguments and environment overrides through to `main.py`.

If a run behaves unexpectedly, the first thing to inspect is the startup line printed by:

`resolved_cp_sat_worker_profile: ...`
