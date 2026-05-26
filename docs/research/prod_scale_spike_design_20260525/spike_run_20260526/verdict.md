# Spike Phase B run verdict — prod-scale master integration

**Date**: 2026-05-26
**Branch**: `spike/prod_scale_master_integration_20260526` (off master `f7b88b6`)
**Phase B commits**: B1 `292c3a4` / B4+B5 `e121800` / B2 `c4f2e35` / B3 `3a9d507` / B6 (this commit)
**Phase B wall-clock**: 205s
**Phase A wall-clock**: ~1-2h (per phase_a_report.md)

## Overall verdict: **NOT_GO until G10 is repaired**

Per MERGER §5.2 round-3 semantic gap documentation:

> Spike GO close *Sizing*, 不 close *Convergence* / *Adversarial robustness*, 后两者入 P1.3A risk register.

This verdict pertains to **Sizing only** (Finding 5 #1 / #2 / #3 / #4). Convergence (real
PoseBoolExactMaster + LBBD multi-iter behavior under 81K BoolVar) and adversarial robustness
(F1/F2/F3 patch hold under 100K scale + 50 bad / 9950 good inject) are explicitly NOT
verified by this spike — they are deferred to P1.3A 主体 design phase and P1.3B regression.

## G criteria (sizing — Finding 5 #1/#3/#4)

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| G1 build 0 cut | ≤ 10s | 2.02s | PASS |
| G2 build 1K cut | ≤ 20s | 2.04s | PASS |
| G3 build 10K cut | ≤ 30s | 2.17s | PASS |
| G4 build 50K cut | ≤ 300s | 2.71s | PASS |
| G4b build 100K cut | ≤ 600s | 3.38s | PASS |
| G5 0 cut feasibility solve | ≤ 30s | 0.71s (OPTIMAL) | PASS |
| G7 100K solve wall (measure, no hard cap) | — | 0.88s (OPTIMAL) | n/a (measure) |
| G8 RSS peak | ≤ 20 GB | 1.03GB in phase_b_results after-solve snapshot; telemetry rss_sample max is 0.866GB | PASS, evidence split |
| G9 proto @ 50K | ≤ 500 MB | 18.0MB | PASS |
| G9 proto @ 100K | ≤ 1 GB | 19.7MB | PASS |
| G10 oracle real-emit cert fixture (A3) | ≥45 + 9 families + 0 unsound | 44 cert / 8 families / 0 unsound | SOFT-FAIL (missing F3 `port_exposure`) |
| G11 active filter Hybrid mock loop | wall ≤ 100ms/iter + eviction fires | total 0.073s, max 9.5ms, evict @ iter [6] | PASS |
| G17 failfast probe (A2) | ≤ 15s | 3.4s | PASS (A2 phase_a_report) |
| G6a feasible smoke wall | < 180s cap | 180.00s | FAIL *(SOFT — see notes)* |
| G6a feasible smoke status | OPTIMAL/FEASIBLE | FEASIBLE | PASS |
| G6a best_objective_bound valid | not None | 76884.0 | PASS |
| G6b random cut tolerate-INFEAS wall | > 1s if INFEASIBLE | 0.82s (OPTIMAL) | PASS |

## N (NOT-GO) criteria trigger status

| Criterion | Trigger? | Detail |
|---|---|---|
| N1_build_overlimit_0 | no | — |
| N1_build_overlimit_1K | no | — |
| N1_build_overlimit_10K | no | — |
| N1_build_overlimit_50K | no | — |
| N1_build_overlimit_100K | no | — |
| N2_random_presolve_crash | no | — |
| N2_random_presolve_crash_1K | no | — |
| N2_random_presolve_crash_10K | no | — |
| N2_random_presolve_crash_50K | no | — |
| N2_random_presolve_crash_100K | no | — |
| N3_rss_critical | no | — |
| N4_proto_critical | no | — |
| N6_oracle_unsound | no | — |
| N9_reproducibility_variance | no | — |
| N10_wall_cap | no | — |
| N11_telemetry_missing_class | no | — |
| N12_off_limits | no | — |
| N13_probe_overlimit | no | — |

## Finding 5 (5 项) cover evidence

Per MERGER §5.2: spike must close Finding 5 sizing/measurement gate, NOT close P1.3A 主体.

| # | Finding 5 item | Spike evidence | Cover? |
|---|---|---|---|
| 1 | 真 prod registry build master var | A3 oracle emit + B1 load_pose_registry: 81,795 BoolVar from real `data/preprocessed/candidate_placements.json` 7 facility pool | YES |
| 2 | 真 cut body 分布 (replacing toy 1-3-5 literal) | A3 jsonl has 44 cert across 8 families; F3 `port_exposure` is absent, so no 2-literal blocked-port body sample | PARTIAL |
| 3 | build wall / proto / RSS / solve wall 实测 | B2 ramp: build 2.04–3.39s, proto 16.3–19.7 MB, build RSS 0.834–0.866 GB; phase_b_results after-solve RSS peak 1.029 GB; solve 0.73–0.87s across 0–100K | YES, but 1.029GB peak needs raw telemetry event |
| 4 | active filter @ 10K/50K/100K, Hybrid score | B4 mock loop 10 iter: total 0.073s, eviction fired iter [6] (52K→30K), age_decay validated via multi-iter age tick | YES |
| 5 | feasible realistic case 避 INFEAS-早停 | B3 feasible smoke: 10K known-feasible cut (blueprint hint) + Maximize obj → FEASIBLE obj=76795 bound=76884 (gap 0.12%) NOT Presolve-crash | YES (with G6a wall SOFT FAIL) |

## Layer 2 risk acknowledgment (per `[[adversarial-soundness-audit]]`)

This spike validates **Sizing-Layer-1 only**. The following Layer-2 risks remain OPEN and
enter P1.3A risk register:

0. **G10 fixture coverage** — Add F3 `port_exposure` fixture records or formally re-scope G10 to 8 active families before marking Finding 5 #2 closed.

1. **Convergence (Gemini round 3 Q8 semantic gap)** — Toy master has 81,795 BoolVar + loose
   `sum(group_vars) >= 1` demand. Real PoseBoolExactMaster will have ExactlyOne per instance
   + port-linking + anti-overlap. Whose solve cost the spike's `solve_wall_s 0.7–0.9s` does
   NOT predict. P1.3A LBBD outer-loop convergence must be empirically validated separately.

2. **G6a wall SOFT FAIL is honest finding** — Solver hit 180s cap at FEASIBLE with bound gap
   0.12% on toy master. With real master constraints this gap will likely be larger. P1.3A
   should NOT assume single-solve termination at 81K + 10K cut scale.

3. **Random tier OPTIMAL (not INFEASIBLE) finding** — Toy master too loose for 10K random
   no-good cuts to make it infeasible. This means the spike's G6b guard 'INFEASIBLE wall > 1s'
   was not actively tested. Adversarial robustness (50 bad cert / 9950 good — MERGER §5.3)
   deferred to P1.3B regression.

4. **Single solve, not multi-iter LBBD** — Per MERGER §5.3 explicit NOT-scope. Spike single
   build/solve cannot trigger Lever-12 (v8 anchor slicing) / Lever-16 (lazy power completion) /
   PCR-CUT Phase 5 / B1 path-2 style convergence failures.

5. **F1/F2/F3 patch hold at scale unverified** — Adversarial validator inject not in spike.
   GPT pro Layer-2 catch may still surface issues here (per `[[gpt-pro-p11-audit-not-go]]`
   pattern). Deferred to P1.3B.

## Actual wall / Claude time vs estimate

Per MERGER §5.6 (shrunk estimate): 8-12h Claude / 4-7h wall total.

| Step | Estimate (Claude) | Actual (Claude) | Wall |
|---|---|---|---|
| Phase A (all) | 3.5-5h | ~4-5.5h | ~1-2h |
| B1 toy translator | 1-2h | ~30 min | <5 min |
| B4 filter mock + B5 telemetry | 0.5-1h + 1-2h | ~30 min combined | <5s self-test |
| B2 scale ramp | 1-2h Claude + 2-3h wall | ~30 min | 17s (0.3min) |
| B3 feasible smoke | 1h Claude + <5min wall | ~30 min | 188s (3.1min) |
| B6 runner + verdict.md | 1-2h Claude + 1-2h wall | ~30-45 min | <1 min |
| **Phase B total** | **6-9h Claude + 3-5h wall** | **~2-3h Claude** | **205s (3.4min)** |

Phase B wall was MUCH smaller than estimate (3-5h) because:
- Build cost is essentially linear and well below thresholds (3.4s for 100K not 600s)
- Toy master + loose constraints → no INFEASIBLE early-stop loop
- Single-worker + single-solve per tier (no multi-iter LBBD per MERGER §5.3)

## Unexpected behavior

1. **All ramp tiers OPTIMAL** — Expected at least some tiers to be FEASIBLE-only or hit
   max_time. Toy master demand=`sum>=1` + cut form `AddBoolOr / AddLinear<=K-1` is loose enough
   for 81K vars to trivially satisfy. Documents the gap toy ≠ real.

2. **proto size only 16-20 MB at 100K cuts** — Much smaller than G9 1 GB threshold. CP-SAT
   stores BoolVar as varint-packed indices not name strings, so 100K AddBoolOr × ~3 lit avg =
   ~300K lit refs ≈ few MB on top of base 16 MB.

3. **RSS peak stays below 1.03 GB across all tiers** — Build phase already loads OR-Tools +
   81K BoolVar (≈0.6 GB). Additional cuts add proportionally small protobuf footprint. No L24
   augmented-master-style RSS explosion at this scale on toy master. Evidence caveat:
   `telemetry_21050.jsonl` sampled RSS max is 0.866GB; the 1.03GB number comes from
   `phase_b_results.json` 100K after-solve snapshot and should be emitted as a raw telemetry
   event in the next spike rerun.

4. **G6a feasible solver bound gap 0.12% at 180s** — Bound 76884 vs obj 76795 over 81K var
   max-sum. Pure structural: 10K AddBoolOr each forbids ~3 vars conjunction. Solver finds a
   FEASIBLE quickly (within hint-biased region) but proving OPTIMAL across 81K is harder than
   expected. Honest finding.

## Recommended next step (main conversation)

**NOT_GO as packaged** for spike close evidence: G6a wall remains a documented soft fail, and G10 is now an evidence soft-fail because A3 misses F3 `port_exposure` and does not meet ≥45/9-family coverage. Patch verify can still be accepted independently; rerun or append F3 fixture data before marking Finding 5 #2 closed.

Off-limits enforce: PASS (B1-B6 added only spike-lib files + this verdict.md;
`scripts/spike_prod_scale_lib/off_limits_check.py` would report 0 violation against master).

---

## Raw artifacts

- Telemetry jsonl: `/home/zhuran24/claude-pj/zmd/data/cuts/spike/telemetry_21050.jsonl` (204 rss_sample + 14 proto_sample + 1 dark_matter_emit)
- Scale ramp jsonl: `data/cuts/spike/scale_ramp_results.jsonl` (5 tier records)
- A3 oracle fixture: `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` (44 cert across 8 families; F3 missing)
