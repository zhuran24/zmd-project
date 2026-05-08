# Phase 3C Optimization Research — Agent Transcript Index

This is the master index for the multi-round optimization research kicked off
2026-05-07 / 2026-05-08. Full agent transcripts (prompt + reasoning + tool uses +
final report) are archived under `agent_transcripts/`.

**Hard-rule for the research loop**: keep launching new rounds until **5
consecutive rounds yield no high-quality findings**. Round counter resets
whenever a round produces at least one actionable gold-mine.

## Round 1 (2026-05-07) — Foundations: D and E paths

| Agent ID | Topic | Outcome |
|---|---|---|
| `abd7846675c5e14fb` | CaDiCaL Learner API + IPASIR | 🥇 amazon-science fork has `--lc-out`/`--lc-in` ready-made |
| `a2c5eba9785c3363d` | CP→SAT encoding feasibility | ⚠ Full conversion blows up to 5e7-2e8 clauses; Chuffed as Benders subproblem viable |
| `a06de6cc1a7950537` | SAT solver SOTA 2024-2026 | 🥇 Don't replace CP-SAT main, only subproblem layer with CaDiCaL+IPASIR-UP |
| `a38ef37448d2d0a8d` | Painless / clause sharing | 🥇 OR-Tools 8 workers ALREADY share clauses in-process |
| `af05282ff225ef9db` | ML4CO survey | 🥇 GBDT + CAMBranch + AlphaEvolve are the right ML directions |
| `a3dd1dc86014a90af` | GNN + Learning-to-branch | 🥇 Neural Diving recommended; AlphaChip excluded (reproducibility crisis) |
| `a0ddda46b5530f550` | CP-SAT internal hooks audit | 🥇 Benders cut persistence ALREADY EXISTS in project |

## Round 2 (2026-05-07/08) — Specific PoC paths

| Agent ID | Topic | Outcome |
|---|---|---|
| `a96266f5aed302928` | Symmetry breaking 2D placement | ⚠ 99% already implemented (grouped encoding + signature monotonic); only D₄ left |
| `aa32783403f3cf351` | CP-SAT params beyond worker count | ⚠ **PARTIALLY_REFUTED 2026-05-08 by R12 `a55a893f5ab38c083`**: subsolver names exist but "+30-70%" was SAT/UNSAT benchmark, not max_lex; `core` is dangerous for our objective; LNS removal needs `ignore_subsolvers` not `subsolvers`; missed v9.15 strong variants (`objective_shaving_*`). Revised ROI +5~25%, kept as P0 with corrected config. |
| `abfed2a994c69f1f0` | AlphaEvolve PoC concrete | 🥇 OpenEvolve + Gemini Flash, $25 / 500 iter, 2-week PoC |
| `a1c65c960a2f9cb0b` | Industrial CP-SAT war stories | 🥇 168h exact proof is industry outlier; budget tiering recommended |
| `a89b891b3e3123556` | IPASIR-UP API concrete | 🥇 PySAT path + routing_subproblem PoC, 4-6 weeks |
| `a31af6debabd49128` | LNS hybrid warm-start | ⚠ LNS 0% on INFEASIBLE; useful for FEASIBLE candidates |
| `a8a152668dd067210` | Linux memory + THP + cgroups | 🥇 +15-35% from THP/baseline/cgroups; Ubuntu Server 24.04 |
| `a6d508ceece21642a` | CP solvers besides OR-Tools | 🥇 Chuffed for Benders subproblems; Pumpkin/Glasgow worth tracking |

## Round 3 (2026-05-08) — Decomposition + AI + preprocessing

| Agent ID | Topic | Outcome |
|---|---|---|
| `af150891e26339789` | Decomposition variants beyond Benders | 🥇 Combinatorial Benders Cuts (Codato-Fischetti) + Multi-Level LBBD |
| `a6480e76a7177e6fd` | Anytime ε-optimal + bound certificates | 🥇 ε-Certified (1-5% gap) is structural new direction, 1000x acceleration |
| `a37cf00dce550f097` | Domain-specific preprocessing | 🥇 12 new prechecks (DFF + energetic reasoning), +11-25% candidate pruning |
| `ae3c21075cb388b14` | Subproblem caching / memoization | 🥇 Three-piece caching: dict + subsumption trie + cross-candidate cut pool |
| `a21d52add52be96a7` | Curriculum 60→70→80 scaling | 🥇 Pure-algorithm curriculum beats ML curriculum; cut cross-scale reuse |
| `aeef0d5e64a3cfeb9` | CP-SAT log mining for conflicts | 🥇 Use `sufficient_assumptions_for_infeasibility` + MUS, not log parsing |
| `a15189ea6dd761cfe` | SMT solvers (Z3/cvc5/Yices) | 🥇 D'' = cvc5 binding subproblem replacement (1-2 weeks PoC) |
| `a4438d81d0b74ba38` | Recent CP/CPAIOR papers 2024-2026 | 🥇 Huub solver (Dekker CP'25), LLG (Baauw CP'25), DynamicSAT, ViolationLS |

## Round 4 (2026-05-08) — Filling gaps

| Agent ID | Topic | Outcome |
|---|---|---|
| `a11eb425ca2c37694` | Huub solver deep integration | 🥇 But not ready: missing circuit/flow propagators, Python binding immature |
| `a7b0041317b6e6139` | VeriPB / CakePB / Alethe | 🥇 Phase 5 only; current Phase 3B doesn't need formal proofs |
| `a21c8156ce15501b0` | CP-SAT issue tracker patterns | 🥇 5 Perron quotes + 2GB proto limit warning |
| `a0d2d950c3bbd8398` | Memetic / GA / BRKGA | ❌ 5 mismatches, exclude (reversible if RINS proves <1.2x) |
| `a55aa02cbc6f623ac` | ICL / Reasoning LLMs for CO | ⚠ Not for hot path ($0.05-0.30/decision); validation only |
| `a08387fbca2c9ad18` | CP-SAT memory profiling | 🥇 4 vs 8 worker A/B = cheapest experiment, -30-40% RSS |
| `acb01aa0ca95c3510` | LP relaxation strengthening | 🥇 PDLP area oracle; Combinatorial Benders is main line |
| `a6e2f3150e1184d9d` | Hardware FPGA/GPU SAT | ❌ All hardware paths excluded; TurboSAT 12-24mo watch list |

## Round 5 (2026-05-08) — Implementation depth

| Agent ID | Topic | Outcome |
|---|---|---|
| `acb4e62e0c603bceb` | OR-Tools 9.16 changelog deep dive | ⚠ 9.15 IS latest; 9.16 expected May; 2 new no_overlap_2d params |
| `a3bef849bbe8777ab` | MUS algorithms (QuickXplain etc.) | 🥇 CPMpy already implements all; 4-day project to wire |
| `a89d19953587dd79f` | cpsat-autotune Optuna integration | 🥇 1-week PoC; 5-25% gain expected (not 70%) |
| `a6d05a19c340d22c4` | CP-SAT shared_tree workers | ❌ **REFUTED 2026-05-08 by R12 `af3d797751cb8bbb2`**: at 8 workers + max objective, OR-Tools auto formula `(N-16)/2` correctly disables it; explicit ≥2 would halve portfolio diversity. Google's implicit-on threshold for objective mode is `num_workers ≥ 26`. Original "+10-30% UNSAT" was for SAT/feasibility benchmarks, not max-problem. Lesson: solver-param gold mines must verify by reading source/proto, not just trust agent benchmark citations. |
| `a13cf5eff78c9773b` | Neural-Symbolic hybrid | ⚠ Don't open new lane; NeuroBack/AlphaProof patterns already in E1/E3 |
| `a573a93d8823d4dbd` | Factory game community | 🥇 ModRef 2023 LBBD validates our path; Venturini engineering tips |
| `a0a1880745aab67e3` | INFORMS / EURO industrial | 🥇 Solar Plant IJOC 2024 must-read; Hexaly as exploratory accelerator |
| `ad3d563e90a007e30` | Codex residual code audit | 🥇 ~150 LOC dead code + 4 expandable hooks (precheck functions) |

## Round 6 (2026-05-08) — Frontier exploration

| Agent ID | Topic | Outcome |
|---|---|---|
| `a97ae4416eb4bd8cf` | Pumpkin / Glasgow LCG | 🥇 Glasgow PB sidecar (D''') for audit, not replacement |
| `a6341e4ac38a35db5` | Codex S100-S150 runtime data | 🥇 42×32 NEVER had real solve (only no-solve probes) |
| `aafcddf4215ab99e7` | SAT/UNSAT proof tooling 2024-2026 | 🥇 cake_lpr is Phase 5 cleanest trust base |
| `a656b69d449b928b7` | OR-Tools main branch undocumented | 🥇 v9.16 99% complete (May release); 2 new params (357, 361) |
| `a03cda5a8b71604d1` | Profile/trace tools | 🥇 py-spy --native; 4-hour playbook ready |
| `aa7992fdbe17e1229` | Endfield game-specific simplifications | 🥇 326 instances (corrected from 266); 3 pose削减 (-25% candidate pool) |
| `aa2cd8e2e60b20719` | Compiler optimization | 🥇 +6-12% from march+LTO (1 day); +5-10% PGO (2-3 days) |
| `a7322ed66982214c7` | Tabu / Hexaly modern | 🥇 ALNS Python lib, 4-5 days to incumbent + AddHint |
| `a43e97232d861bfd4` | CP-SAT industrial deployments | 🥇🥇 OnlyEnforceIf audit + 168h is outlier warning |

## Round 7 (2026-05-08) — Frontier round 2

| Agent ID | Topic | Outcome |
|---|---|---|
| `a7a4c0f20baf602f5` | OnlyEnforceIf audit (project-specific) | 🥇 100 calls catalogued; Top 5 改造 +20-40% solve |
| `aaa9a46efbbbe9596` | AlphaProof / Lean 4 / mathlib | 🥇 PBLean + exact-SCIP correct path; AlphaProof excluded (combinatorics 20.3%) |
| `a7db41848a47c8250` | Spectral / SDP relaxation | ⚠ Excluded for main path; small-subproblem SDP as Phase 5 candidate |
| `ac494304c28cb7af7` | Belief propagation / SP | ❌ Excluded; emergency fallback only |
| `a2bbf0cd35f724a3c` | Modern interior-point LP solvers | 🥇 HiGHS 1.14 area oracle (1 week落地) |
| `a0ac44e2d03f4edb2` | ε-gap progressive tightening | 🥇 5-day implementation, 3-stage 5%→1%→0% with bound transfer |
| `a5e5d808402d6e43d` | CP-SAT routing/graph cross-module | ❌ **REFUTED 2026-05-08 by R12 `ab52ebd0fdc64a308`**: AddCircuit assumes Hamiltonian cycle, our routing is multi-commodity flow with splitters/mergers/bridges. R7 had precondition "if MTZ/DFJ exist" but codebase grep confirms zero MTZ/DFJ — nothing to replace. R7 itself flagged the precondition; roadmap dropped it. |
| `ab26579806bc582bd` | Streaming / online / anytime | 🥇 Online排除; anytime 4 engineering kits吸收 |

## Round 8 (2026-05-08) — gap-filling round 3

| Agent ID | Topic | Outcome |
|---|---|---|
| (8 agents) | Various: Ray/Dask, lazy clauses, MaxSAT, etc. | 🥇 6 real gold mines (#39-44); Ray/Dask excluded post single-machine constraint |

## Round 9 (2026-05-08) — frontier round 3

| Agent ID | Topic | Outcome |
|---|---|---|
| (8 agents) | lb_tree_search, SAT restart, Math+MIS, sym-aware Benders, SAT inprocessing | 🥇 5 real gold mines (#45-49); Decision Diagrams excluded; 2D packing solvers conditional |

## Round 10 (2026-05-08) — final round before roadmap

| Agent ID | Topic | Outcome |
|---|---|---|
| `a434c6a1198c78a5a` | Branch-and-Price for 2D placement | ⚠ PoC viable but pricing geometry-coupled; 1-week go/no-go gate |
| `a2d29f537e2b0ba30` | MCMC / CEM / SMC / Parallel Tempering | 🥇 PT multi-temperature scheduling on existing 4-process is near-zero-cost |
| `acbe77fbda04756f7` | Physics-inspired heuristics (non-SA) | ❌ GSA/crystallization/LBM all excluded; ACO pheromone idea redundant w/ Round 1-2 |
| `a9d8ba25a087fb653` | Endfield expert-player layouts | 🥇🥇 3 project-specific hints/nogoods: bridge_hop≤2, storage-box overload sep, compact aspect prior |
| `a08591c75ba641e6e` | AlphaEvolve cut-discovery cookbook | 🥇🥇 Complete 1-week PoC framework: evaluator + config + prompt + safety contract alignment |
| `a660692b75d21afb7` | HP tuning method comparison | 🥇 SMAC3-as-OptunaHub-sampler 1-line A/B; Hyperopt dead, Ax/BoTorch tier-2 |
| `ac82668b944498f96` | Imitation Learning from solver traces | 🥇🥇 IL > RL for our setup; CAMBranch 10% data; S4 dataset already aligned; expert-signal precheck required |
| `acb9bd4fdd02868c2` | ε-optimal convergence rates | 🥇 168h three-stage budget (25h / 50h / 85h) + 75h hard checkpoint + Stage-3 dual-growth diagnostic |

**Round 10 ROI estimate** (savings/research time): ~22 min research; estimated savings ≥ 1 engineering week through avoided RL detour, AlphaEvolve framework reuse, expert-layout hints, 168h budget split. ~50-100x ROI on potential. **But unrealized until landed.**

**Stop signal applied**: per user 2026-05-08 — *"按节约的时间与调研时间的值来算"*. Continued research has predicted ROI ≤ 1 from here; landing Top-5 P0 gold mines is now the highest-ROI next action.

(Stop later retracted same day: predicted-ROI=1 was unjustified pulled-from-air; user pushed back, Round 11 launched with 8 directions not yet investigated. See Round 11 section.)

## Round 11 (2026-05-08) — directions not yet investigated

| Agent ID | Topic | Outcome |
|---|---|---|
| `a2dc46b9af8a17e14` | RLT for 2D placement | ❌ Master already enumerated, RLT-1 implicit; no PoC |
| `a67cf942cd679915d` | SAT cardinality encoding + OnlyEnforceIf | 🥇🥇 `presolve_extract_integer_enforcement=true` 1h → +5-15% (maybe 2-3×); 52 OnlyEnforceIf rewrites in `exact_coordinate_master.py` 1-2d → 1.5-2× |
| `a007c0e7513c91e75` | Fixed-parameter tractability | ❌ 70×70 treewidth=70 + W[1]-hard; no FPT route viable |
| `a7741c394a61d5aa4` | Auto symmetry detection (nauty/bliss/dejavu) | ⚠ Downgrade to 0.5d probe via `symmetry_level:3` log inspection; full week not justified |
| `ae3590b7e2f938057` | Cache-aware data structures | 🥇 THP + tcmalloc/jemalloc + PGO + L3 isolation +15-30% combined (user-layer only, no OR-Tools src changes) |
| `a823b529b0879c4bb` | Anytime certificate engineering | 🥇🥇 8 patches ~5h: schema_v4 with bound_state, cut pool ε-bucket, fill_tightened_domains, hint persistence, VeriPB exporter — **revealed P1 #7 ε-Certified missing engineering layer** |
| `a241150d7be611784` | GPU LP/MIP (cuPDLPx, cuOpt) | ❌ Master is CP-SAT not LP; scale mismatch (few-thousand bools vs GPU sweet-spot 1M+ nonzeros) |
| `a5ed0a16a983cc48c` | Planar graph algorithms (Lipton-Tarjan) | ❌ Routing 2-layer + multi-commodity + cross-port bindings break planarity at solver level |

**Round 11 ROI**: research ~22 min; 3 real high-yield (SAT encoding 3 dirs + cache-aware + anytime cert eng), 5 excluded — density 37.5%, ROI > 1 confirmed. Anytime cert eng was net-saver: caught a hidden P1 #7 spec gap (5 day → reality 5h prep + 5 day) that would have wasted ~5 days of misdirected work.

**Round 12 decision**: not yet evaluated. Hypothesis: P0 landing now has higher ROI than further research, but per Round 11 lesson **don't pull "predicted ROI ≤ 1" from thin air** — at minimum, list residual unprobed directions and judge each.

## "Research firefighting" ROI realized log (2026-05-08)

Follow-up source-code audits ("R12-style") on P0 roadmap items — saved hours
> spent doing the audit by avoiding negative-ROI implementations.

| # | Audit | Verdict | Saved |
|---|-------|---------|-------|
| 1 | P0 #1 shared_tree (R5 → R12 `af3d797751cb8bbb2`) | ❌ REFUTED | ~5-20h (would have halved portfolio diversity at 8 workers) |
| 2 | P0 #3 UNSAT subsolver portfolio (R2 → R12 `a55a893f5ab38c083`) | ⚠ PARTIALLY_REFUTED | ~5-10h (avoided adding `core` which degrades max_lex; corrected `subsolvers` vs `ignore_subsolvers` confusion) |
| 3 | P0 #5 AddCircuit (R7 → R12 `ab52ebd0fdc64a308`) | ❌ REFUTED | ~5-10h (would have wasted on infeasible refactor; original "1 day" was off by infinity since AddCircuit can't handle splitters/mergers) |
| 4 | P0 #23 presolve_extract_integer_enforcement (R11 → R12 `a0b6fa2949affdad1`) | ❌ REFUTED | ~1-2h (param doesn't do what R11 said; was zero-citation Claude inference; MIPLIB regressions warned in proto) |
| 5 | P1 #7 ε-Certified prep (R3+R7+R10 → R11 `a823b529b0879c4bb`) | ⚠ engineering layer missing | ~5d (reveal that "5-day implementation" was on top of unbuilt schema_v4 + bound_state foundation) |

**Pattern (updated 2026-05-08 evening)**: parameter-level P0 救火率 **4/4 (100%)** — covers BOTH "benchmark citation" type (R5 shared_tree, R2 UNSAT subsolver, R7 AddCircuit) AND "Claude self-inference" type (R11 presolve_extract_integer_enforcement, where R11 had no citation at all and even misdescribed the mechanism). Lesson now stronger: ANY parameter-level P0/P1 entry whose ROI claim cannot be traced to a primary source-code or proto reading **must be follow-up audited**. See `feedback_verify_solver_param_claims.md` (revised).

**Net session-level ROI for follow-up audits**: ~30 min total agent time + ~20 min processing = ~50 min, savings already 16-42 engineering hours = **20-50× ROI**, monotonically growing.

## "P0 landing" log (2026-05-08)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| P0 #2 | 4 vs 8 worker A/B + RSS profile | ✅ **VERIFIED & landed** | telemetry analysis 2026-05-08: 4 worker peak_RSS=23.3 GiB / duration 287s vs 8 worker peak_RSS=40.0 GiB / duration 262s — 4 worker saves 41.8% RSS, only 8.7% slower, R4 gold mine confirmed |
| P0 #3 | UNSAT subsolver portfolio (R12-revised conservative) | ✅ **CONSERVATIVE LANDED** | commit 0a448d8: ignore_subsolvers filter applied (6 LNS names excluded for max_lex). Explicit subsolvers list deferred until search_branching=FIXED interaction is verified. |
| P0 #6 | OnlyEnforceIf Top-5 改造 | ⚠ **PARTIALLY LANDED** | commit 8b5d694: 改造 3 (sum-channel) done. 改造 1 REFUTED (R7 API error), 改造 2 anti-pattern (agent blueprint adds BoolVar/AddBoolOr instead of removing). 改造 4/5 deferred for deeper audit. |

## "Patch blueprint audit" log (2026-05-08)

When promoting transcript-level "Top N" recommendations to a patch, the
implementation blueprint itself must pass review. Two new failure modes
caught this session:

| # | Transcript claim | Blueprint failure | Caught by |
|---|------------------|-------------------|-----------|
| 1 | R7 改造 1: AddImplication for routing OnlyEnforceIf | API misuse — `AddImplication` 2nd arg must be BoolVar, not linear constraint | R12 `a91a3c90b172df1ce` |
| 2 | R7 改造 2: default-value channeling via new BoolVar | Anti-pattern — adds 1 BoolVar + 1 AddBoolOr, increasing model size instead of reducing | R12 `a91a3c90b172df1ce` + manual review of blueprint diff |

**Lesson**: even after a transcript survives "is it a real gold mine"
audit, the patch blueprint produced from the transcript is a *separate
artifact* that needs its own review — agent might quote API docs
correctly but still output blueprints that don't compile or that
contradict the stated optimization goal. Always grep actual codebase
and count constraints/vars before/after for any "improvement" patch.

## Reading these transcripts

Each `.output` file is JSONL (one event per line):
- `type: "user"` — original prompt
- `type: "assistant"` with `message.content[].type == "thinking"` — reasoning
- `type: "assistant"` with `tool_use` — what the agent did
- `type: "user"` with `tool_result` — what came back
- `type: "assistant"` final message — the report

Quick read of one transcript:
```powershell
python -c "
import json
for line in open('docs/research/agent_transcripts/<id>.output', encoding='utf-8'):
    e = json.loads(line)
    if e.get('type') == 'assistant':
        for c in e.get('message', {}).get('content', []):
            if c.get('type') == 'text':
                print(c.get('text', ''))
                print('---')
"
```

## Refresh / preserve discipline

Tools live in `scripts/refresh_*.py` — see CLAUDE.md `## Maintenance scripts`.
Agent transcripts copied here from session-temp once per session via:
```powershell
# (ad-hoc; transcripts are session-scoped)
robocopy "$env:LOCALAPPDATA\Temp\claude\D--claude-pj-zmd\<session>\tasks" `
         "docs\research\agent_transcripts" *.output
```
