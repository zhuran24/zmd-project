# SMT-MT Outer Pruning Phase 1 (2026-05-21)

## TL;DR

Phase 1 wires the **SMT Modulo Monotonic Theories** outer pruning engine
into `src/search/outer_search.py` behind `EXACT_SMT_MT_OUTER_PRUNING=1`
env flag. Phase 0 cheap-gate (Dummy inner mock) measured 76.7% prune
ratio + p95 293ms + 0.43GB RSS delta + 38.6s build wall — GO 8/8 across
all five tripwires.

Phase 1 measures the **real** prune ratio against the production B1
LBBD inner solver and verifies env-off byte-identity to baseline outer
behavior. Shadow telemetry only — never modifies certification semantics.

## Phase 0 GO recap

| metric | value | threshold | verdict |
|---|---|---|---|
| m1_total_candidates | 2,347,345 | informational | — |
| m2_prune_ratio (Dummy) | 76.7% | >= 50% GO | PASS |
| m3_containment_query_p95 | 293 ms | <= 1000 ms | PASS |
| m4_rtree_build_seconds | 38.6 s | <= 60 s | PASS |
| m5_rtree_rss_gb_delta | 0.43 GB | <= 2 GB | PASS |
| m6_prune_by_area_bucket | >= 2000: 100% / 1000-1999: 99.9% / 500-999: 99.9% / 200-499: 73.3% / < 200: 4.2% | monotone | PASS |

Phase 0 probe: `docs/research/smt_mt_outer_pruning_phase0_20260521/phase0_probe.py`

## Phase 1 wiring

Files changed:

1. `src/search/smt_mt_outer_pruning.py` (NEW, ~310 LOC):
   - `OuterPruningEngine` class with R-tree over `(w, h)` candidates.
   - `notify_infeasible(w, h)` -> propagates to all (w', h') with
     w' >= w AND h' >= h via R-tree intersection query.
   - `metrics_snapshot()` -> JSON-safe telemetry dict.
   - `write_telemetry(path)` -> atomic JSON write.
   - Module helpers: `is_enabled()`, `maybe_build_engine()`,
     `maybe_notify_infeasible()`, `maybe_write_telemetry()` — all
     env-aware (return None / [] / no-op when off).

2. `src/search/outer_search.py` (~30 LOC delta):
   - Import the engine + module helpers.
   - Build engine once after `generate_candidate_sizes(...)` call
     (returns None when env off — preserves env-off byte-identity).
   - `_smt_mt_record_infeasible(w, h)` closure: notify engine +
     bump telemetry wave counter + write `.artifacts/smt_mt_outer_pruning/
     phase1_metrics_wave_NNNN.json`. Try/except guards never bubble
     into the main loop.
   - Hook into 4 INFEASIBLE call sites:
     * Single-process precheck-elimination (line ~1654)
     * Parallel precheck-elimination (line ~1808)
     * Parallel worker INFEASIBLE result (line ~1980)
     * Serial inner returning INFEASIBLE (line ~2208)

### Env-gate behavior

| env value | engine | hook calls | telemetry |
|---|---|---|---|
| unset / `0` / `false` / `off` | None | no-op | none written |
| `1` / `true` / `yes` / `on` | constructed | propagate + log | wave files |

When env is off, `maybe_build_engine` returns None, `_smt_mt_record_infeasible`
detects None and exits before any work. The 4 hook sites add at most
one `if smt_mt_engine is None: return` branch — env-off baseline is
preserved.

### R-tree build timing

Build happens **eagerly at outer_search entry** (after candidate enumeration,
before the main while-loop), not lazy. Rationale:

- One-time amortized cost ~40s on 2.4M candidates (Phase 0); cheap vs
  168h campaign.
- Lazy-on-first-INFEASIBLE pays the build cost inside the hot path; bad.
- For the production outer (~3K size-only `(w, h)` candidates), build is
  sub-second — Phase 0 number was on the richer (w, h, anchor) pool.

### Telemetry path naming

`.artifacts/smt_mt_outer_pruning/phase1_metrics_wave_{idx:04d}.json`

One file per INFEASIBLE notification, written atomically (`*.tmp` then
rename). Each file contains the cumulative snapshot — latest file has
the full lifecycle telemetry. Schema version `schema_version: 1`.

## Pytest coverage

`src/tests/test_smt_mt_outer_pruning.py` (~210 LOC, 15 tests):

- `TestEnvGate`: 3 tests (default off, truthy variants, falsy variants).
- `TestCandidateKey`: 1 test (format).
- `TestEngineBuild`: 2 tests (populated metrics, empty candidates).
- `TestMonotonePropagation`: 5 tests
  * propagates supersets correctly
  * geometric invariant (ghost_A subset ghost_B + ghost_A INFEASIBLE -> ghost_B pruned)
  * idempotent (repeat notify on same key adds no new prunes)
  * cumulative count (union semantics)
  * no propagation when no superset exists
- `TestModuleHelpers`: 4 tests (env-off None, env-on engine, no-op
  notify, no-op telemetry).
- `TestTelemetryWrite`: 2 tests (JSON content, path format).
- `TestOuterSearchIntegrationSurface`: 2 tests (import symbols
  identity, env-off engine None).
- `TestDirectlyInfeasibleSet`: 1 test (directly-notified vs
  propagated separation).

Tests run in <1s (no inner solver, tiny candidate pools).

## Phase 1 trial

`docs/research/smt_mt_outer_pruning_phase1_20260521/phase1_trial.py`

- Curated 10-candidate pool spanning area buckets (2500/1600/1200/1000/
  700/500/405/300/240/200) to hit each m6 bucket.
- `--dry-run`: verify env + engine build + a synthetic
  notify(50,50) cycle without invoking the real inner solver.
- Full run: `EXACT_SMT_MT_OUTER_PRUNING=1 EXACT_USE_POSE_BOOL_MASTER=1
  EXACT_OUTER_SKIP_UNKNOWN=1` then call `run_outer_search` with
  `start_area` capped to the pool max + `max_attempts=10` +
  `benders_max_iter=5` (matches PCR-CUT Phase 4 trial budget).

Wall budget: ~10 candidates × 5 min B1 LBBD + 38s engine build = up
to 1h. With `EXACT_OUTER_SKIP_UNKNOWN=1` set we never block on a single
UNKNOWN — the trial walks through the whole pool.

## GO/NO-GO

| metric | threshold | source |
|---|---|---|
| m1_real_prune_ratio | >= 30% (Phase 0 Dummy was 76.7%; real expected lower) | latest `phase1_metrics_wave_*.json` |
| m2_query_p95_real | <= 1000 ms | same |
| m3_total_outer_wall | <= 1h | trial summary `outer_wall_seconds` |
| m4_telemetry_correctness | all wave files parse + monotone counts | manual check |
| m5_env_off_regression | env-off outer behavior byte-identical to baseline | pytest |

## Failure modes anticipated

1. **m1_real_prune_ratio very low**. Real B1 LBBD rarely returns
   INFEASIBLE — most candidates exit as UNPROVEN or UNKNOWN (LBBD
   inner cut loop didn't close). UNPROVEN doesn't trigger monotone
   propagation (proof is incomplete). If most trials end UNPROVEN,
   prune ratio stays near 0 — that's the dominant Phase 1 risk.
2. **m3 wall overruns 1h**. B1 master alone takes 50-120s per
   candidate; 10 × 120s + LBBD iters could push past 30 min easily.
   Set `--benders-max-iter 5` and `--master-seconds 120` (in trial
   defaults) to bound.
3. **R-tree build OOM**. Phase 0 measured 0.43 GB delta on 2.4M
   (w, h, anchor) candidates; outer pool is ~3K (w, h) pairs only —
   irrelevant in production.

## If Phase 1 GO

- Phase 2: extend to `(w, h, anchor)` enumeration. Requires bigger
  outer_search refactor (anchor delegation is currently inside the
  master model — see `master_model.py` ghost placement vars).
- Phase 3: combine SMT-MT with PCR-CUT lifting — every routing
  conflict core that's pose-independent could be a SMT-MT theory
  predicate too.
- Phase 4: stack with candidate C (column generation) — orthogonal
  paradigms (CG = inner quality, SMT-MT = outer pruning).

## If Phase 1 NO-GO

Most likely scenario: real prune ratio is low because UNPROVEN
dominates over INFEASIBLE. Then SMT-MT outer pruning has no fuel.
Investigate whether `EXACT_OUTER_SKIP_UNKNOWN=1` (best-effort mode)
+ `epsilon-certified` path produces more INFEASIBLE verdicts that
fuel propagation. If still no signal, mark Lever 25 dead.

## Run

```bash
# Pytest
.venv/bin/python -m pytest src/tests/test_smt_mt_outer_pruning.py -v

# Dry-run trial (no real inner)
.venv/bin/python -u docs/research/smt_mt_outer_pruning_phase1_20260521/phase1_trial.py \
    --dry-run

# Full trial (background; 30-60 min wall)
EXACT_SMT_MT_OUTER_PRUNING=1 \
EXACT_USE_POSE_BOOL_MASTER=1 \
EXACT_OUTER_SKIP_UNKNOWN=1 \
.venv/bin/python -u docs/research/smt_mt_outer_pruning_phase1_20260521/phase1_trial.py \
    --max-candidates 10 --benders-max-iter 5
```

Output: `phase1_trial_summary.json` + telemetry wave files under
`.artifacts/smt_mt_outer_pruning/`.

## Citation

Bayless, S., Bayless, N., Hoos, H., Hu, A. *SAT modulo monotonic theories.*
AAAI 2015. We use 2D-poset bbox containment as a concrete monotone
theory predicate over `(w, h)` size pairs.
