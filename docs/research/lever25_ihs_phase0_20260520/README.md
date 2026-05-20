# Lever 25 IHS (Implicit Hitting Set) — Phase 0 cheap gate

## TL;DR

Lever 25 explores the **Implicit Hitting Set (IHS)** paradigm as an alternative
to standard LBBD cut accumulation. Instead of adding each oracle-extracted core
directly to the master, IHS keeps an *external* store of all observed cores and
solves a minimum hitting set ILP to derive the cut sent into the master.

Phase 0 question: **does the LBBD oracle even produce cores of size > 1?**
If every core has size 1 (single pose literal), the hitting-set optimizer
degenerates to "union of singletons", and IHS reduces to standard LBBD. In
that case the paradigm cannot help — fail-fast NO-GO without writing the full
HS-driven master integration.

## Hypothesis (formalized)

Run LBBD inner loop on anchor (22, 28), 27×15 candidate, 10 iters total.
Record `(iter, source, core_size, literals)` for every cut produced.

**Stage 1 (iters 1-5, observation only):**
- GO if p50(core_size) ≥ 3 AND ≥ 50% of cores have size > 1
- NO-GO if p50(core_size) < 3 OR ≥ 80% of cores have size == 1
- PENDING otherwise (keep collecting)

**Stage 2 (iters 6-10, only if Stage 1 GO):**
- Solve minimum hitting set ILP on accumulated cores (CP-SAT, 5s budget)
- Measure: HS solve wall, HS size vs union size (compression ratio), final
  LBBD status
- GO if final status ∈ {CERTIFIED, INFEASIBLE} AND hs_wall ≤ 60s AND
  compression < 1.0 (HS strictly smaller than union)
- NO-GO otherwise

## Why this Phase 0 design

- **Aborts fast on the most likely failure mode.** Path 17 D2 verdict
  ([[project_d2_path17_verdict]]) observed core_size==1 across all iters,
  same degenerate pattern as Path 12 RAB-SEP and Path 14 PCR-CUT. Prior
  estimate of Stage 1 NO-GO is ~70%.
- **No src changes.** Pure monkey-patch on `MasterModel.build` (wraps the
  delegate's `add_benders_cut` and `add_patch_routing_core_cut` after
  construction). Stage 2 measures compression *offline* on accumulated cores
  rather than live-rewriting the cut, which removes risk of breaking LBBD
  convergence while still answering the gate question.

## Difference vs standard LBBD

| | standard LBBD | IHS |
|---|---|---|
| cut store | master accumulates | external store outside master |
| per-iter cut | 1 oracle core added directly | HS ILP run over all cores, derived cut added |
| compression | none — adds union of cores | minimum HS may be much smaller than union |
| degenerate case | always adds 1 cut/iter | if all cores size 1 → HS = union → no benefit |

## Metrics (recorded in `phase0_results.json`)

| metric | meaning | threshold |
|---|---|---|
| `m1_core_size_p50` | median across all observed cores | ≥ 3 (Stage 1 GO) |
| `m1_pct_size_eq_1` | fraction of cores with size = 1 | < 80% (Stage 1 GO) |
| `m1_distribution` | full size histogram | descriptive |
| `m3_hs_solve_wall_s` | min hitting set ILP wall | ≤ 60s (Stage 2 GO) |
| `m4_final_status` | LBBD final status | CERTIFIED/INFEASIBLE (Stage 2 GO) |
| `m5_compression` | hs_size / union_size | < 1.0 (Stage 2 GO) |

## Active source path

We use the **PCR-CUT** environment-gated path
(`EXACT_B1_PATCH_ROUTING_CORE=1`, commit b5c7a58 era) as the live cut source
because it is the most recent and stable separator that lands the most
multi-literal cores via signature lifting. Other paradigms (SAC-Hull, D2
commodity flow, deletion-core, lazy demand, cell cut) are explicitly disabled
for this probe to avoid confounding the size distribution.

Cuts are observed via two hooks:
- `delegate.add_benders_cut(conflict_set)` — captures `instance_id -> pose_idx`
  dict size as `core_size`. Used by d2 / deletion-core / placement_local_nogood.
- `delegate.add_patch_routing_core_cut(core_terms, patch_cells)` — captures
  `len(core_terms)` as `core_size`. Used by PCR-CUT.

## How to run

```bash
# Dry-run: verify imports + hooks resolve + HS optimizer sanity (no real LBBD).
.venv/bin/python -u docs/research/lever25_ihs_phase0_20260520/phase0_probe.py --dry-run

# Real run (background recommended — expect 10-60 min wall depending on
# whether Stage 1 NO-GOs early or runs full 10 iters).
.venv/bin/python -u docs/research/lever25_ihs_phase0_20260520/phase0_probe.py \
    > docs/research/lever25_ihs_phase0_20260520/phase0_run.log 2>&1 &
```

Outputs:
- `phase0_results.json` — verdict + per-iter cores + HS metrics + raw cores
- `phase0_run.log` — full stdout (banner + per-iter prints + HS sanity)

## Known failure modes / risks

- **Stage 1 NO-GO (~70% prior).** Path 17 D2 saw 100% core_size=1.
  PCR-CUT may also collapse to size 1 cores under pose-bool master. Expected
  outcome: abort fast, verdict "NO-GO stage1_no_go" within ~10-15 min wall.
- **PCR-CUT separator finds zero cuts.** Then `total_cores == 0` and verdict
  is "INCONCLUSIVE no_cores_observed". Either anchor (22, 28) too easy or
  PCR-CUT silently fails — log inspection needed.
- **LBBD raises exception.** Captured into `lbbd_exception` in results JSON.
- **Stage 2 HS optimizer can't solve in budget.** Recorded as `hs_wall > 60s`
  → Stage 2 NO-GO. Cores larger than ~100 literals each would push CP-SAT
  hitting set ILP toward the 5s per-call budget.

## Hard constraints (probe self-imposed)

- No src edits. All hooks are monkey-patches.
- No reading `docs/research/paradigm_search_review_v12_with_code_20260520/`
  (GPT plan details) — implementation derived independently from raw
  architecture spec.
- No reading `docs/research/layout_invariant_cert_phase0_20260520/` or
  `docs/research/benders_symmetry_phase0_20260520/` (just-failed Phase 0s,
  avoid pattern contamination).
- LOC budget: ≤ 450 (probe + README). `python -u` mandatory for unbuffered
  prints.

## What is NOT in scope for Phase 0

- Live HS-driven cut wiring into master (would replace `add_benders_cut` body).
  Done offline-batch here; if GO, that wiring is Phase 1 work in src/.
- Multi-anchor sweep (only (22, 28) here; Phase 1+ if GO).
- Persistent cut store across master rebuilds (master rebuilds wipe cuts;
  IHS requires external persistence).
- Proof object serialization for HS-derived cuts (PROJECT_LOCK lifecycle work
  in Phase 1+ if GO).
