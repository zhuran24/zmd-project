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

## Round 13 (2026-05-10) — half-year refresh on R1-R11 directions

R1-R11 调研截至 2026-05-08。距今约 2 天，但学术日历上有半年新进展 (CP/SAT/CPAIOR 2025 H2 会议 + 工具版本更新)。规则修订（见 `feedback_research_roi_metric.md` v2）：实施带宽空出 + 信息池可能更新 → 单 round 调研可重启。

| Agent ID | Topic | Outcome |
|---|---|---|
| `a4ecd78d0488484e7` | OR-Tools 9.16+ changelog | ⚠ 9.16 NOT released yet (R5/R6 May predict 没兑现); 9.15.6755 (2026-01-14) 仍是当前最新; post-9.15 main 6 个新字段不影响项目; 5 件套配置全部仍合理 |
| `ab0787721db5ca990` | 2025 H2 CP/SAT/INFORMS 论文 | 🥇 5 watchlist + 1 直接借鉴: IJPR 2025 LBBD 工程加强 paper (cuts + warm-start) 跟项目三层 LBBD 同构; CP'25 LLG/Solnon anytime/2D Cutting/DC-LNS; CP'25 #34 PB-OPT proof; LLM-LNS ICML'25; 无路线图变更, 无 paper 颠覆 ε-Certified/LBBD/cut 持久化方向 |
| `adee29cf670b5c3dc` | Pumpkin/Glasgow/Huub | 🥇🥇 Pumpkin v0.3.0 PyPI (2026-02-11) Python binding **已成熟**; Glasgow gcspy + VeriPB 3.0 (2026-05-09 仍每日 commit); Huub 仍无 Python; 推荐: Pumpkin P3→P2 PoC 候选 (binding subproblem D''' 独立 audit), Glasgow P3→P2 audit-only |
| `a8a448561dbacf07c` | OpenEvolve/AlphaEvolve cookbook | 🥇 OpenEvolve v0.2.27 (2026-03-18) late beta + Claude/DeepSeek 已支持; LLM-LNS ICML'25 spotlight 打过 Gurobi; AlphaEvolve arXiv 2506.13131; **R10 1 周 PoC 缩到 2-3 day**; DeepSeek V3 $5/500 iter ensemble Claude Sonnet 4.6 副; P2 #14 升级到"立即可做" |
| `ab56e030d7ec24cad` | CPMpy/cvc5/Z3 SMT 工具 | 🥇 CPMpy 0.10.0 (2026-01-19) MUS API 稳定 + OR-Tools 9.15 已对齐; cvc5 1.3.4 (2026-05-07); Z3 4.16.0; SMT-COMP 2025 QF_LIA: OpenSMT 1, cvc5 2; **P2 #18 工时 4d→1-2d**, 立即可做; P3 cvc5 维持 |
| `a3c49824ef52b2cb9` | OR-Tools custom C++ propagator | ❌ Excluded. PropagatorInterface 是 internal C++ class, 官方 Discussion #3303 推荐 reformulate, 无 user-extension API; fork-only 路径 4 周 + PROJECT_LOCK 红线; 路线图加 Excluded 条 |
| `af55dd10eeeac5fd0` | Mallob/SAT Comp 2025 | ⚠ P3 watchlist. SAT'25 parallel: Mallob 1, Painless 2; cloud track 2025 取消; Mallob v2.0.0 (2025-07-31) 单机 mono mode 但无 24 thread vs Kissat-MAB head-to-head; IPASIR-2 仍 draft; LAN 假设不适合 P2 #27 WAN |
| `a3356c51d9d10daab` | Anytime CP / ε-Certified 半年 | 🥇 CP'25 #21 Koops VeriPB PB-OPT 工业可用 (RoundingSat/Sat4j 全套 logging 完成); cake_lpr 2026-02 升级; **R11 #6 VeriPB exporter 90min→4-6h** (中间 ε-gap 没标准 schema, 自定义 transcoder 不可避免); **新增 P2 plateau-based 动态阶段切换** (Lübke&Berg AAAI'25 思路, 2h, Stage-2→Stage-3 if dual_growth<threshold for 4h) |

**Round 13 ROI estimate**: research ~25 min wallclock (8 agent 并行 ~10-15 min wall + 我 ~10 min 处理); 兑现 ROI = 4 个 P3→P2 升级 + 2 个 P2 工时缩短 + 1 个 Excluded 修正 + 1 个新 P2 项 + 1 个 R11 #6 工时修正 = 估 **~2-3 工程天 saved + 4 个 PoC 候选实施带宽利用**。
**关键 takeaway**: 半年内 9.16 没发布但工具链 (Pumpkin/OpenEvolve/CPMpy/VeriPB) 全部成熟一档; 路线图 P3 → P2 升级是主要变化。

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
| 6 | P1 #8 Combinatorial Benders Cuts (R3 `af150891e26339789` → 2026-05-10 audit `ae376dabbfd7a5096`) | ⚠ PARTIALLY_REFUTED | ~3-5 engineering days saved (path 1: avoided over-investing 1 week for 5× expected when reality is 2-3 days for 1.3-1.8×; path 2: surfaced that current cuts are already fine-grained subset, MIS only useful in INFEASIBLE-fallback path). Demoted P1 → P2. |
| 7 | P1 #25 OnlyEnforceIf 52 rewrites (R11 `a67cf942cd679915d` → 2026-05-10 audit `a4640130e3de3efa2`) | ❌ REFUTED | ~1-2 engineering days saved + 阻止 negative-ROI investment (claim "1.5-2× single wave"; reality 实际 44 处 OnlyEnforceIf, top-5 已 4/5 死/降级, presolve auto-detects 大半收益 → 真实 8-15% 总累计含已 landed 改造 3). Demoted P1 → P3 (剩 ~4 对双向 reify spike, ~½ day micro-benchmark). |
| 8 | P1 #24 Cache-aware user-layer pack (R11 `ae3590b7e2f938057` → 2026-05-10 audit `a2dfaa35dbefe2a3a`) | ⚠ GO-WITH-CAVEATS | ~½ day saved + 修正了 5 件套配比 (AMO aggregation transcript 无源整项剔除; L3 CAT 13th gen consumer i9 不支持改名 cpuset pinning). 修正后 combined +15-22% (vs claim 15-30%). 前 3 项 (THP madvise + jemalloc LD_PRELOAD + cpuset P-core pinning) 一上午搞定 90% 收益. |
| 9 | P1 #13 Compiler -march/LTO/PGO (R6 `aa2cd8e2e60b20719` → 2026-05-10 audit `a486d3f9206a2b09a`) | ⚠ PARTIALLY_REFUTED | ~3-5 engineering days saved (PGO 工时低估 2-3 倍; SAT solver SIMD/PGO 红利天花板远低于通用 C++). Wheel 实测确认 baseline x86-64-v1 + 无 LTO/PGO. 修正 stack +5-12% (vs claim 11-22%); march+LTO 1d 实验 → ≥+5% 才上 PGO. |
| 10 | P1 #12 Cache trio (R3 `ae3c21075cb388b14` → 2026-05-10 audit `a36d33351616095f1`) | ⚠ GO-WITH-CAVEATS | ~3-4 engineering days saved (1.5/3 件已实现 - CutManager dedup + per-candidate restart cache - 不是 0/3). 子问题级 LRU + subsumption trie + cross-candidate cut pool 是真增量 ~8-25% (gated by 24h spike 重复率 ≥15%). 工时 5-7d (不是 3d). |
| 11 | P1 #9 Endfield player hints (R10 `a9d8ba25a087fb653` → 2026-05-10 audit `a5070327a1e24b779`) | ⚠ PARTIALLY_DONE / 1 NO-OP refuted | ~½ day saved + 路线图状态修正. Hint A (b2a811b bridge_hop_le_2) ✅ + Hint B (94351d5 overload separation) ✅ 已落地; **Hint C compact_aspect 已被 b2a811b commit 自审为 NO-OP** (sort key 已蕴含方形偏好). "+5-10h faster" 数字 R10 transcript 无依据. 状态 = 2/3 done, 3rd refuted. |
| 12 | P1 #11 PT multi-temperature (R10 `a2d29f537e2b0ba30` → 2026-05-10 audit `a9c445cf4754e075e`) | ⚠ PARTIALLY_REFUTED | ~2-4 engineering days saved + ROI 期望修正 10× → 1.1-1.3×. Stage 1+2 (commit d07e303 + scheduler dispatch) 已落地但只是 per-process RNG reseed (不是真 PT). 真 PT (replica exchange + ordering policy) 3-5 天 (不是 zero cost) 且跟 CP-SAT 内部 LNS portfolio 重叠. Stage 3+ 降级 P2. |
| 13 | R13 OpenEvolve / AlphaEvolve (`a8a448561dbacf07c` → audit `a062ff6396a691d74`) | ⚠ PARTIALLY (5/9 CONFIRMED, 1 REFUTED) | DeepSeek V3 已被 V4 取代 (V4-flash $0.14/$0.28 比 V3 还便宜); "确定性 seed" / "circle packing 双模 ensemble SOTA" 在 release notes 找不到. P2 #14 工时 2-3d / "立即可做" verdict 站得住, 修订 API 价格表. |
| 14 | R13 CPMpy / cvc5 / Z3 (`ab56e030d7ec24cad` → audit `ae3860a1dc6cbabb8`) | ✅ CONFIRMED (8/9, 1 PARTIALLY) | cvc5 pin 应该 1.3.4 不是 1.3.3 (1 天差). 其他全对. P2 #18 工时 1-2d / 立即可做 verdict 站得住. R13 8 个调研里这条最准. |
| 15 | R13 Pumpkin / Glasgow / Huub (`adee29cf670b5c3dc` → audit `ac9e83ba97f6f4f5e`) | ⚠ PARTIALLY (20/21 CONFIRMED, 1 REFUTED 但反向利好) | Pumpkin **all_different + table 已实现** (transcript 说缺失). binding D''' 路径反而比 R13 估的更顺, 工时 3-5d 维持但风险下降. Glasgow / Huub 全 CONFIRMED. |
| 16 | R13 VeriPB / Lübke&Berg (`a3356c51d9d10daab` → audit `aec9dfe82ab5889ef`) | ⚠ PARTIALLY (4 CONFIRMED, 2 PARTIALLY, 1 REFUTED + 1 衍生 claim 失实) | **Lübke&Berg 是 CP'25 不是 AAAI'25** (commit 抄错); **plateau-based 不是 paper claim** (paper 用 fixed time-limit per phase, 不是 plateau detection); CP'24 multi-stage proof 作者错 (实际 Flippo 等不是 Boudreault & Quimper); cake_lpr 日期 2025-02 不是 2026-02. P2 #30 改"自创工程想法" not paper-grounded. R11 #6 VeriPB 4-6h 维持. |

**Pattern (updated 2026-05-10 evening, 6 audit batch)**: 救火率扩展到 **11/11 (100%)** —— P0 7 项 + P1 4 项审完，全部 turn up at least PARTIALLY_REFUTED 或 GO-WITH-CAVEATS。新覆盖类型扩展到：
- (a) "benchmark citation" type — R5/R2/R7
- (b) "Claude inference" type — R11
- (c) "paper claim displacement" type — R3 #8
- (d) **新增 "raw grep -c without classification" type** — R11 #25 (52 处只是 OnlyEnforceIf 总数 grep，无模式分类，外推 1.5-2× 必死)
- (e) **新增 "stack double-count" type** — R11 #24 / R3 #12 (多件套加和不打 stack-efficiency 折扣，真实是 0.5-0.7×)
- (f) **新增 "scope-misnaming" type** — R10 #11 (RNG reseed 被命名为 "PT 多温度" → claim 收益错位)
- (g) **新增 "soft hint roadmap drift" type** — R10 #9 (3rd hint 已被 commit 自审 NO-OP，路线图未更新)

See `feedback_verify_solver_param_claims.md` (2026-05-10 revised — rule scope broadened to all primary-source-verifiable quantitative claims).

**Net session-level ROI for follow-up audits**: ~80 min total agent time + ~50 min processing = ~130 min ≈ 2.2 hours, savings already 30-65 engineering hours = **14-30× ROI**, monotonically growing. **All P0/P1 entries with quantitative claims are now audited.**

## "P0 landing" log (2026-05-08)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| P0 #2 | 4 vs 8 worker A/B + RSS profile | ✅ **VERIFIED & landed** | telemetry analysis 2026-05-08: 4 worker peak_RSS=23.3 GiB / duration 287s vs 8 worker peak_RSS=40.0 GiB / duration 262s — 4 worker saves 41.8% RSS, only 8.7% slower, R4 gold mine confirmed |
| P0 #3 | UNSAT subsolver portfolio (R12-revised conservative) | ✅ **CONSERVATIVE LANDED** | commit 0a448d8: ignore_subsolvers filter applied (6 LNS names excluded for max_lex). Explicit subsolvers list deferred until search_branching=FIXED interaction is verified. |
| P0 #6 | OnlyEnforceIf Top-5 改造 | ⚠ **PARTIALLY LANDED** | commit 8b5d694: 改造 3 (sum-channel) done. 改造 1 REFUTED (R7 API error), 改造 2 anti-pattern (agent blueprint adds BoolVar/AddBoolOr instead of removing). 改造 4 demoted to P1 (R12 audit shows count 4 not 18, missing AddExactlyOne, presolve auto-detects). 改造 5 deferred for sentinel-pair audit. |
| P0 #4 | Domain-level prechecks | ⚠ **AUDITED, partial overlap** | R12 audit `ab23c3975f6040dc8`: R3 #8 mostly done (probing/symmetry levels); #3 in CP-SAT internal; #7 covered by existing area LB. **4 P0a survive**: #1 DFF area LB, #10 Power Budget, #11 Storage I/O, #8 remaining 2 params. ROI revised +8-16% (down from R3's +11-25%). 8 demoted to P1. |

## Data corrections (2026-05-08)

- **mandatory facility instance count = 266** (not 326). 326 is the total
  including 60 optional facility instances. Earlier round prompts that
  said "326 mandatory" conflated the two; specs/05 and PROJECT_LOCK.md
  are authoritative at 266 mandatory. Going forward: any roadmap or
  audit using "mandatory" should use 266.

## "Patch blueprint audit" log (2026-05-08)

When promoting transcript-level "Top N" recommendations to a patch, the
implementation blueprint itself must pass review. Two new failure modes
caught this session:

| # | Transcript claim | Blueprint failure | Caught by |
|---|------------------|-------------------|-----------|
| 1 | R7 改造 1: AddImplication for routing OnlyEnforceIf | API misuse — `AddImplication` 2nd arg must be BoolVar, not linear constraint | R12 `a91a3c90b172df1ce` |
| 2 | R7 改造 2: default-value channeling via new BoolVar | Anti-pattern — adds 1 BoolVar + 1 AddBoolOr, increasing model size instead of reducing | R12 `a91a3c90b172df1ce` + manual review of blueprint diff |
| 3 | R12 蓝图 改造 4: 18 处 membership reify → linear channeling | Count error (actually 4) + missing `AddExactlyOne(bucket_lits)` (math fails without it) + CP-SAT presolve already auto-detects original pattern → low expected ROI | R12 `a8eb034b3b1213a9c` |
| 4 | R3 #10 "Power Budget: sum(supply) ≥ sum(demand) + overhead" | Data-model mismatch — facility_templates uses `needs_power: bool` (no numeric power values); real precheck would be 80m coverage geometry, not sum check. R12 estimate of 0.5d is unrealistic. | manual codebase grep + rules inspection 2026-05-08 |
| 5 | R3 #8 蓝图 "set presolve_substitution_level=2" | Proto says "any positive value performs substitution" — 1 (default) vs 2 may be no-op delta; needs cp_model_presolve.cc per-level verification before claiming +N% | manual proto WebFetch 2026-05-08 |
| 6 | R12 蓝图 #1 DFF u_k formula | Agent pseudocode contains ambiguous "原归一系数 W'" without precise definition; paper (Carlier-Clautiaux-Moukrim 2007 EJOR §3.2) is paywalled; GitHub code search needs auth. Formula correctness cannot be independently verified, so implementation in src/ risks math error breaking certified_exact LB soundness. | manual paper/GitHub access attempt 2026-05-08 |
| 7 | R12 改造 5 蓝图 (sentinel row for shell guard) | Geometric reasoning correct, sentinel `(max_shell, max_shell)` math right, BUT blueprint missed that inactive path already pins `(d_lo, d_hi) = (0, 0)` via `slot.x/slot.y` inactive enforcement + unconditional dx/dy/min/max chain. Direct sentinel would create infeasibility. Correct patch is ~15 lines across 3 functions, not "2 lines" as blueprint claimed. | R12 `a7676847d82e04abb` |
| 8 | R3 #11 "Storage I/O flow conservation: 边界 in_flow - out_flow ± buffer = 0" | Schema-validator nature, not candidate-level pruning. mandatory_exact_instances has `instance_id ↔ operation_type (recipe)` fully bound; conservation is constant across all candidates (they share the same instance set). ROI ≈ 0 for actual pruning; would only catch input-data corruption that should already be caught upstream by instance_builder. | manual data-model inspection 2026-05-08 |
| 9 | R12 改造 5 修订蓝图 (decouple inactive + OnlyEnforceIf distance) | dx/dy → d_lo/d_hi chain uses `AddMinEquality` / `AddMaxEquality` which CP-SAT v9.15 does NOT support `.OnlyEnforceIf()` wrapping on. The "decouple inactive path" step is unimplementable without rewriting dx/dy compute logic or doing a deep audit of all consumers that depend on `slot.x = x_min when inactive`. True cost >3 days; demoted to P3. | manual code read of exact_coordinate_master.py:2776-2890 (2026-05-08) |

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
