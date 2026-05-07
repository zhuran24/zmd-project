# Phase 3C Optimization Roadmap v1

**Date**: 2026-05-08
**Status**: Active — supersedes prior research-mode planning
**Source**: 10 rounds of agent research (78 transcripts archived under
`docs/research/agent_transcripts/`, indexed at `docs/research/INDEX.md`)
**Status**: research is iterating, not closed. Each P0/P1 entry of "solver
parameter +N%" type must be verified by a follow-up source-code audit before
landing — see P0 #1 (REFUTED 2026-05-08 by R12 `af3d797751cb8bbb2`) for the
precedent. Lesson recorded in `feedback_verify_solver_param_claims.md`.

## ROI scoring legend

For each item we estimate two numbers:

- **Save**: expected reduction in 168h campaign wall-clock OR insurance against
  catastrophic loss (e.g., OOM mid-run wiping 100h of progress)
- **Cost**: engineer-time to land + verify (in Claude-pace, not human-pace —
  see `feedback_work_time_estimates.md`)

ROI = Save / Cost (rough order-of-magnitude). Tiers:

- **P0** ROI ≥ 50× — do first, cheapest leverage
- **P1** ROI 5-50× — second wave, 1-2 week window
- **P2** ROI 1-5× — opportunistic, after P0+P1 land
- **P3** Phase 4-5 — not in scope for current campaign
- **Excluded** — definitively ruled out, do not re-investigate

---

## P0 — land first (highest ROI)

| # | Item | Source | Save | Cost | ROI |
|---|------|--------|------|------|-----|
| 1 | ~~**shared_tree workers explicit set**~~ | ~~R5 `a6d05a19c340d22c4`~~ | **REFUTED by R12 `af3d797751cb8bbb2`** — at 8 workers + max objective, OR-Tools auto formula `(N-16)/2` correctly disables it; explicit set ≥2 would cut portfolio diversity in half (8 = 4 portfolio + 4 shared_tree). Google's implicit-on threshold for objective mode is `num_workers ≥ 26`. Net: original "1000×" claim is wrong; actual recommendation is **leave at default -1 (auto)** and only revisit if master scales to ≥26 workers. | — | NEGATIVE / removed |
| 2 | **4 vs 8 worker A/B + RSS profile** — ✅ **VERIFIED 2026-05-08** via existing telemetry: `baseline_4x4_normal_300s_20260506_150657` (peak_RSS=23.3 GiB, duration=287.4s, peak_CPU=1634%) vs `matrix_4x8_300s_20260506_170203` (peak_RSS=40.0 GiB, duration=262.4s, peak_CPU=1188%). **4 worker saves 41.8% RSS, only 8.7% slower, higher effective CPU utilization** (8 worker thrashes 16-core machine). **Verdict: use 4 worker for 168h campaign — OOM insurance is real and performance loss is negligible.** Action: invoke production 168h campaign with `EXACT_CP_SAT_WORKERS=4` env override (do NOT change `DEFAULT_MASTER_CP_SAT_WORKERS=8` in code — code default stays for dev workflow, production goes via env). | R4 `a08387fbca2c9ad18` | -41.8% RSS / -8.7% wall-time | already done (data analysis only) | ✅ landed |
| 3 | **CP-SAT subsolver portfolio (max_lex-tuned)** — **PARTIALLY_REFUTED** by R12 `a55a893f5ab38c083`: R2's "+30-70%" came from SAT/UNSAT benchmark, not transferable; `core` subsolver is dangerous for max_lex (MaxSAT-style); LNS removal requires `ignore_subsolvers` not `subsolvers`. v9.15 has stronger variants R2 missed: `objective_shaving_no_lp/max_lp`, `probing_max_lp`. Real lever: 8 workers run only 6 of 16 default subsolvers — pick which 6. Use `solver.parameters.subsolvers = [default_lp, max_lp, probing, probing_max_lp, lb_tree_search, objective_lb_search]` + `ignore_subsolvers = [rins, rens, graph_arc_lns, graph_cst_lns, feasibility_pump, violation_ls]`. NOT `core`. | R2 `aa32783403f3cf351` (REVISED) | +5~25% (max +40% on lucky combo) — not +30-70% | ~1 day A/B with revised config | ~30-50× |
| 4 | **Domain-level prechecks (12 new)** | R3 `a37cf00dce550f097` | +11-25% candidate pruning (~20-40h) | ~3 days | ~10× |
| 5 | ~~**AddCircuit for routing subproblem**~~ | ~~R7 `a5e5d808402d6e43d`~~ | **REFUTED by R12 `ab52ebd0fdc64a308`** — `AddCircuit` is a TSP/Hamiltonian primitive (in-degree=out-degree=1). Our routing is multi-commodity flow with splitters (1→2/3), mergers (2/3→1), 2 layers, multi-source/multi-sink. Codebase grep `MTZ\|DFJ\|subtour\|Hamilton\|circuit\|TSP` returns zero matches — there is no subtour-elimination to replace. R7's precondition ("if MTZ/DFJ exist") was lost when promoted to P0. Move to Excluded. | — | NEGATIVE / removed |
| 6 | **OnlyEnforceIf top-5 audit fixes** | R7 `a7a4c0f20baf602f5` | +20-40% solve | ~2 days | ~20× |
| 23 | ~~**`presolve_extract_integer_enforcement=true`**~~ | ~~R11 `a67cf942cd679915d`~~ | **REFUTED by R12 `a0b6fa2949affdad1`** — R11 misdescribed mechanism. Param does NOT touch our 100 OnlyEnforceIf; it CREATES new enforcement literals from plain linear constraints with at-bound integer-var-of-large-coefficient terms. R11's "+5-15% / 2-3×" was zero-citation Claude inference. Proto explicitly warns of MIPLIB regressions (manna81 LP looser, neos literal explosion). Demoted to P3 (cheap one-liner experiment, ~0 expected value) — keep `false` default unless presolve log shows non-trivial `"linear: extracted enforcement literal"` rule stats. | — | NEGATIVE / demoted to P3 |

**P0 cluster delivery target**: end of week 2026-05-15. All P0 items are
exact-mode-safe per PROJECT_LOCK.md.

---

## P1 — 1-2 week window

| # | Item | Source | Save | Cost | ROI |
|---|------|--------|------|------|-----|
| 7 | **ε-Certified three-stage 168h split (25h/50h/85h)** | R3+R7+R10+R11 (`a6480e76a7177e6fd`, `a0ac44e2d03f4edb2`, `acb9bd4fdd02868c2`, `a823b529b0879c4bb`) | avoids 168h run-out (catastrophic save) + 1000× tiered acceleration | **~5h prep + ~5 days** (R11 revealed engineering-layer prerequisites) | very high |
| 7a | **— prep: schema_v4 with `bound_state` block** | R11 `a823b529b0879c4bb` | required by #7; current checkpoint has no `lb`/`ub`/`gap`/`epsilon` fields | ~30 min + lock/spec/test sync | gating |
| 7b | **— prep: cut pool ε-stage bucketing** | R11 `a823b529b0879c4bb` | reuse 5%-stage cuts in 1%/0% stages (looser ε ⟹ tighter ε is sound) | ~45 min | gating |
| 7c | **— prep: `fill_tightened_domains_in_response=true`** | R11 `a823b529b0879c4bb` | only public CP-SAT cross-solve dual-info channel | ~30 min | gating |
| 7d | **— prep: bound regression guard + audit log** | R11 `a823b529b0879c4bb` | catches silent monotonicity violations across waves | ~20 min | gating |
| 7e | **— prep: hint cross-wave persistence** | R11 `a823b529b0879c4bb` | `add_hint() + use_optimization_hints + repair_hint=True` | ~30 min | gating |
| 24 | **Cache-aware user-layer pack: THP + tcmalloc/jemalloc + PGO + L3 isolation + AMO aggregation** | R11 `ae3590b7e2f938057` | +15-30% combined for long-running 168h workloads | THP/malloc swap ~½ day; PGO ~2-3 days; L3 isolation 1 hour | ~10× |
| 25 | **OnlyEnforceIf 52 rewrites in `exact_coordinate_master.py`** (extends P0 #6 from top-5 → all 52) | R11 `a67cf942cd679915d` | 1.5-2× single wave (binding subproblem hot path) | ~1-2 days incl PROJECT_LOCK review | ~5× |
| 8 | **Combinatorial Benders Cuts (MIS, Codato-Fischetti)** | R3 `af150891e26339789` | master LP gap -30%+ | ~1 week | ~5× |
| 9 | **Endfield player hint/nogood (3 specific)** | R10 `a9d8ba25a087fb653` | early-incumbent +5-10h faster | ~½ day | ~20× |
| 10 | **SMAC3-as-OptunaHub-sampler A/B** | R10 `a660692b75d21afb7` | racing kills slow configs early | 1 line | ~50× |
| 11 | **PT multi-temperature parallel scheduling** | R10 `a2d29f537e2b0ba30` | exploration diversity at zero added cost | ~1 day | ~10× |
| 12 | **Cache: dict + subsumption trie + cross-candidate cut pool** | R3 `ae3c21075cb388b14` | re-solve avoidance ~20% | ~3 days | ~5× |
| 13 | **Compiler optimization (-march, LTO, PGO)** | R6 `aa2cd8e2e60b20719` | +6-12% from march+LTO; +5-10% PGO | 1 day + 2-3 days | ~5-10× |

---

## P2 — opportunistic / experimental

| # | Item | Source | Save | Cost | ROI |
|---|------|--------|------|------|-----|
| 14 | **AlphaEvolve cut-evolution PoC** | R10 `a08591c75ba641e6e` | unknown ceiling, framework now cookbook-ready | ~1 week | gated by go/no-go |
| 15 | **IL from solver traces (S4 data already collected)** | R10 `ac82668b944498f96` | candidate ordering accuracy +N%; faster than RL by 10-100× | ~1-2 weeks | gated by expert-signal precheck |
| 16 | **cpsat-autotune Optuna full sweep** | R5 `a89d19953587dd79f` | +5-25% (not 70%) | ~1 week | ~3× |
| 17 | **ALNS Python warm-start (incumbent + AddHint)** | R6 `a7322ed66982214c7` | feasible-side LB acceleration | ~4-5 days | ~3× |
| 18 | **MUS via CPMpy QuickXplain** | R5 `a3bef849bbe8777ab` | conflict-extraction quality up | ~4 days | ~3× |
| 19 | **Linux migration + THP/cgroups** | R2 `a8a152668dd067210` | +15-35% baseline | ~1 day OS prep + bring-up | gated by user willingness |
| 20 | **py-spy --native profile playbook** | R6 `a03cda5a8b71604d1` | identifies hot paths, prerequisite to compiler tuning ROI | 4 hours | high (diagnostic) |
| 21 | **Branch-and-Price PoC (root-CG only)** | R10 `a434c6a1198c78a5a` | LP gap -30% if pricing tractable | ~1 week | gated by go/no-go |
| 22 | **HiGHS 1.14 area oracle** | R7 `a2bbf0cd35f724a3c` | LP relaxation upgrade | ~1 week | ~3× |

---

## P3 — Phase 4-5 only

- **VeriPB / cake_lpr formal proof** — R4 `a7b0041317b6e6139`, R6 `aafcddf4215ab99e7`
- **PBLean + exact-SCIP + VIPR pipeline** — R7 `aaa9a46efbbbe9596`
- **Glasgow PB sidecar (D''' audit)** — R6 `a97ae4416eb4bd8cf`
- **Spectral / SDP small-subproblem audit** — R7 `a7db41848a47c8250`
- **cvc5 binding-subproblem replacement (D'')** — R3 `a15189ea6dd761cfe`
- **Huub solver integration** — R4 `a11eb425ca2c37694` (waiting on Python binding maturity)
- **Pumpkin / Glasgow LCG** — R6 `a6341e4ac38a35db5` (track upstream)
- **`presolve_extract_integer_enforcement` cheap-experiment slot** — R11 `a67cf942cd679915d` (DEMOTED from P0 #23 by R12 `a0b6fa2949affdad1`); ~1h to set flag and grep `"linear: extracted enforcement literal"` rule stats; only revisit if Boolean half is firing a lot in our presolve log; default keep `false`

---

## Excluded — do not re-investigate

| Direction | Reason | Source |
|-----------|--------|--------|
| Distributed / multi-machine / Ray cluster / Dask | Single-machine hardware constraint | `project_hardware_constraint_single_machine.md` |
| GA / BRKGA / Memetic | 5 mismatches with our model | R4 `a0d2d950c3bbd8398` |
| FPGA / GPU SAT (TurboSAT etc.) | All hardware paths excluded for current phase | R4 `a6e2f3150e1184d9d` |
| Belief Propagation / Survey Propagation | Emergency fallback only, no use case fits | R7 `ac494304c28cb7af7` |
| AlphaProof for combinatorics | 20.3% pass@1 too weak | R7 `aaa9a46efbbbe9596` |
| Decision Diagrams (MDDs) | Doesn't fit ghost-rectangle structure | R9 |
| Gravitational Search Algorithm | No packing implementations, semantics mismatch | R10 `acbe77fbda04756f7` |
| Crystallization / LBM-as-optimizer | Not algorithm classes in literature | R10 `acbe77fbda04756f7` |
| AlphaChip-style RL | Reproducibility crisis | R1 `a3dd1dc86014a90af` |
| ICL / Reasoning LLMs in solver hot path | $0.05-0.30/decision economically unviable | R4 `a55aa02cbc6f623ac` |
| Streaming / online optimization | Doesn't fit campaign batch model | R7 `ab26579806bc582bd` |
| Hyperopt | Unmaintained per Microsoft Azure deprecation note | R10 `a660692b75d21afb7` |
| RLT (Reformulation Linearization Technique) | Master is enumerated already, RLT-1 implicit; CP-SAT no cut-generator API | R11 `a2dc46b9af8a17e14` |
| Fixed-Parameter Tractability (treewidth/FPT) | 70×70 treewidth=70; W[1]-hard for natural parameterizations | R11 `a007c0e7513c91e75` |
| GPU LP/MIP (cuPDLPx/cuOpt) | Master is CP-SAT not LP; scale mismatch (need 1M+ nonzeros for sweet spot) | R11 `a241150d7be611784` |
| Planar graph algorithms (Lipton-Tarjan etc.) | Routing 2-layer + multi-commodity + cross-port bindings break planarity | R11 `a5ed0a16a983cc48c` |
| Auto-symmetry full integration (saucy/dejavu 1-week wire-up) | Downgrade to 0.5-day `symmetry_level:3` log probe; full integration not justified above already-99% manual breaking | R11 `a7741c394a61d5aa4` |

---

## Implementation rules

1. **All P0/P1 work touches PROJECT_LOCK.md gating tests** — every change must
   leave `python -m pytest src/tests/ -q` green.
2. **AI-related items (P2 #14, #15)** must respect AI Safety Contract from
   CLAUDE.md: order_only / hint_only, no checkpoint writes, no certified-proof
   modification.
3. **Each landed item gets a follow-up entry in CHANGELOG.md** + scoreboard
   delta in `data/exports/` if applicable.
4. **No new research rounds** without explicit user request.

## Cross-reference

- Agent transcripts: `docs/research/agent_transcripts/`
- Per-round index + outcomes: `docs/research/INDEX.md`
- Maintenance scripts: `CLAUDE.md` § Maintenance scripts
- Hardware envelope: `project_hardware_constraint_single_machine.md` (memory)
