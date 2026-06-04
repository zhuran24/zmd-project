# Phase 3C Optimization Roadmap v1

**Date**: 2026-05-08
**Status**: HISTORICAL (2026-06-04) — 项目已转入 **cut-family LBBD / Phase 1.2 spike close**（见 `CLAUDE.md`）；本 Phase 3C 优化 roadmap 非当前主线，下方 P0/P1 条目作历史研究记录读。
**Source**: 10 rounds of agent research (78 transcripts archived under
`docs/research/agent_transcripts/`, indexed at `docs/research/INDEX.md`)
**Note**: 即便在当时 roadmap 语境下，research 也是迭代未闭合 —— 每条 "solver
parameter +N%" 型 P0/P1 必须经 follow-up 源码 audit 才能 land，见 P0 #1
（REFUTED 2026-05-08 by R12 `af3d797751cb8bbb2`）先例。教训记于
`feedback_verify_solver_param_claims.md`。

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
| 4 | **Domain-level prechecks (R3-revised → blueprint stalled / many demoted)** — R12 audits + manual data-model inspection. Net status: #8 partial landed env-gated (commit 16970ff); #10 跳过 (needs_power is bool, not numeric); **#11 demoted to Excluded** (mandatory_exact_instances has fixed instance↔recipe binding; conservation is constant across candidates, not pruning); **#1 DFF blueprint BLOCKED** on paper-level formula verification (paywalled). 10 of 12 R3 entries are demoted/skipped. | R3 `a37cf00dce550f097` + R12 audits | currently #8 env-gated only; everything else needs user-supplied unblock (paper access for DFF / decision on #11 schema validator) | requires user decision | stalled |
| 5 | ~~**AddCircuit for routing subproblem**~~ | ~~R7 `a5e5d808402d6e43d`~~ | **REFUTED by R12 `ab52ebd0fdc64a308`** — `AddCircuit` is a TSP/Hamiltonian primitive (in-degree=out-degree=1). Our routing is multi-commodity flow with splitters (1→2/3), mergers (2/3→1), 2 layers, multi-source/multi-sink. Codebase grep `MTZ\|DFJ\|subtour\|Hamilton\|circuit\|TSP` returns zero matches — there is no subtour-elimination to replace. R7's precondition ("if MTZ/DFJ exist") was lost when promoted to P0. Move to Excluded. | — | NEGATIVE / removed |
| 6 | **OnlyEnforceIf top-5 audit fixes** — **PARTIALLY LANDED 2026-05-08**: R12 audit `a91a3c90b172df1ce` rebuilt R7's "Top-5" with patch blueprints. **改造 3 (sum-channel) landed** in commit 8b5d694 (3 paired half-reify → 1 channeling each, mathematically equivalent). **改造 1 (routing AddImplication) is REFUTED** — R7's API call is invalid (AddImplication's 2nd arg must be BoolVar, not linear constraint). **改造 2 (default-value channeling) is anti-pattern** — agent's blueprint adds new BoolVar + AddBoolOr, *increasing* constraint count. 改造 4/5 (membership reify, sentinel rows) deferred — non-trivial math conditions to verify. | R7 `a7a4c0f20baf602f5` + R12 `a91a3c90b172df1ce` | 改造 3 contribution alone: 5-10% (full Top-5 ROI 20-40% claim is now suspect since 2/5 didn't survive audit) | 1h done; 4/5 deferred | partial landed |
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
| 24 | **Cache-aware user-layer pack** — **GO-WITH-CAVEATS 2026-05-10 audit `a2dfaa35dbefe2a3a`**: AMO aggregation transcript 无源 → **整项剔除**；L3 CAT 在 13th gen i9 不支持 → 改名 cpuset P-core pinning。验证 individual ROI（Springer 2020 SAT THP paper / OR-Tools discussion #4012 / jemalloc bench）：**THP madvise +10-25%（1 行 grub config）/ jemalloc LD_PRELOAD +5-10%（env var 1 行）/ cpuset pinning +2-5%（systemd-run 1h）/ PGO +3-7%（5-7 天，不是 2-3 天）**。Combined gain 实际 **+15-22%（vs claim 15-30%）**，受 stack-efficiency 0.5-0.7 收敛上界 (1.15×1.07×1.05×1.03)−1 ≈ 33% 上界×0.6 ≈ 20%。**前 3 项一上午 90% 收益**，PGO 单独评估降到 P2。 | R11 `ae3590b7e2f938057` audit by `a2dfaa35dbefe2a3a` | THP+jemalloc+pinning 立即做：+15-22%（一上午）；PGO P2-gated 单独跑 | THP+jemalloc+pinning ~3h；PGO ~5-7 天 | ~30× (前 3 项) / PGO 单独评估 |
| 25 | ~~**OnlyEnforceIf 52 rewrites in `exact_coordinate_master.py`**~~ — **REFUTED 2026-05-10 audit `a4640130e3de3efa2`**: 实际数 = **44**（不是 52）；R11 数字纯属 grep -c，无模式分类；R11 自承"OR-Tools 抽象层之上不存在 cardinality encoding 选择杠杆"自打脸；R12 audit `a8eb034b3b1213a9c` 已发现 CP-SAT presolve 自动识别双向 reify 模式吃掉大半收益。P0 #6 top-5 已 4/5 死/降级，外推 44 处大部分 (~30+) 跟改造 1/2/5 同形（死或负 ROI）。真实可获益 = 改造 3 已落地 5-10% + 剩 ~4 对双向 reify 改造 4-类（每对 ≤1%，受 presolve 抑制）。**真实总收益 8-15%（不是 1.5-2× = 50-100%）**。**降级 P1 → P3**。 | R11 `a67cf942cd679915d` audit by `a4640130e3de3efa2` | 3-5%（剩余可仿改造 4 对，gated by cert hash benchmark） | ~½ day micro-benchmark + 4 对 spike | **demoted to P3** |
| 26 | **改造 4 (membership signature reify → linear channel) — DEMOTED FROM P0 #6** | R12 `a8eb034b3b1213a9c` | uncertain — CP-SAT presolve already detects original pattern; only 4 actual reify pairs (not 18); needs explicit `AddExactlyOne(bucket_lits)` and micro-benchmark cert hash check | ~½ day incl benchmark | gated by benchmark |
| 28 | ~~**改造 5 (sentinel-row for power pole shell guard)**~~ — **DEMOTED to P3** 2026-05-08 | R12 `a7676847d82e04abb` + manual code read | **Root blocker**: dx/dy → d_lo/d_hi chain uses `AddMinEquality` / `AddMaxEquality` (CP-SAT global constraints which CANNOT be `.OnlyEnforceIf()`-wrapped per OR-Tools v9.15). Correct implementation requires either rewriting dx/dy compute logic (no MinEquality) or auditing entire inactive `slot.x = x_min` dependency surface (line 2848-2849 + downstream). True engineering cost >3 days, ROI 3-5% — net ROI ≤ 1%/day. | — | **demoted to P3 (cheap-experiment slot)** |
| 8 | ~~**Combinatorial Benders Cuts (MIS, Codato-Fischetti)**~~ — **PARTIALLY_REFUTED 2026-05-10 by audit `ae376dabbfd7a5096`** (read R3 transcript + WebFetched paper + read benders_loop.py/cut_manager.py). "master LP gap -30%+" 数字非论文 claim，是路线图作者从 R3 agent 定性 "considerably tighter" 误转。Codato-Fischetti *OR* 54(4) 2006 真实 claim："considerably tighter on **two MIP classes**"——论文 master 是 ILP 不是 CP-SAT，红利核心是消除 big-M LP relaxation，**CP-SAT 没 big-M 形式不直接适用**。项目当前 cut **已是 fine-grained subset**：`binding_pose_domain_empty_nogood` (benders_loop.py:3936) + `routing_front_blocked_nogood` (~4179) 走 `_build_conflict_from_instance_ids`；whole-layout 只在 `binding_status=INFEASIBLE` 全局兜底 (~4053) 才用。CP-SAT CDCL 已自动学 minimal-ish learnt clause，外部 MIS 是冗余先验。真实可改进点窄到 = 把 whole-layout fallback 升级到 unsat-core MIS（`SufficientAssumptionsForInfeasibility`）。**降级 P1 → P2，缩范围**。 | R3 `af150891e26339789` audit by `ae376dabbfd7a5096` | ~1.3-1.8× （不是 5×） — 仅 INFEASIBLE 兜底生效 | ~2-3 天（不是 1 周） — binding_subproblem 重构成 assumption-based + 升级 INFEASIBLE 路径 cut 提取 | **demoted to P2** |
| 9 | **Endfield player hint/nogood (3 specific)** — **PARTIALLY_DONE 2026-05-10 audit `a5070327a1e24b779`**: Hint A `bridge_hop_le_2` ✅ landed (commit b2a811b, routing_subproblem.py:850-853); Hint B `storage_box_overload_separation` ✅ landed (commits 1ba7ca2/22af98a/94351d5 + stage 3 fallback ladder, env-gated); Hint C `compact_block_aspect_prior` ❌ **NO-OP refuted** (b2a811b commit message 自承: outer_search.py:229-235 sort key `(-area, -min_side, -max_side, -ghost_w)` 已经蕴含方形偏好——area 同分时 min_side 大者优先 = 方形优先；aspect_penalty 在 (area, min_side) 平面是 sort key 子函数，新增 NO-OP)。"+5-10h faster" 数字 **R10 transcript 无依据**——是路线图编辑拍的，无玩家实测无 solver benchmark。**状态：2/3 done, 3rd refuted as NO-OP**。剩余动作 = 30 min 微 A/B 测 Hint A 实际 effect，再决定 Hint B 是否生产开（默认 env-unset shadow）。 | R10 `a9d8ba25a087fb653` audit by `a5070327a1e24b779` | unmeasured (predicted modest early-incumbent speedup) | done | ✅ 2/3 done, 3rd N/A |
| 10 | **SMAC3-as-OptunaHub-sampler A/B** | R10 `a660692b75d21afb7` | racing kills slow configs early | 1 line | ~50× |
| 11 | **PT multi-temperature parallel scheduling** — **PARTIALLY_REFUTED 2026-05-10 audit `a9c445cf4754e075e`**: stage 1 (commit d07e303 master_model.py EXACT_MASTER_RANDOM_SEED env hook) + stage 2 (exact_parallel_scheduler.py:131-143 base+worker_index dispatch) **已落地**，但只是 **per-process RNG reseed portfolio**——CP-SAT 内部 8-worker portfolio 已经在做类似 diversification (`subsolvers`/`extra_subsolvers`/`PORTFOLIO_SEARCH`)，外层 reseed marginal lift **1.05-1.3× (不是 10×)**。R10 真意是"不同进程跑不同 ordering 探索强度 + 周期性交换 incumbent"，那需要 IPC + replica buffer + ordering policy → **3-5 天 (不是 zero cost 1 day)** 且跟 CP-SAT 内部 LNS portfolio 重叠。**状态：stage 1+2 done, 真 PT (stage 3+) 降级 P2**。 | R10 `a2d29f537e2b0ba30` audit by `a9c445cf4754e075e` | stage 1+2 已落 ~1.1-1.3×；真 PT stage 3+ unknown | done (stage 1+2) | ✅ stage 1+2 done; stage 3+ P2 |
| 12 | **Cache: dict + subsumption trie + cross-candidate cut pool** — **GO-WITH-CAVEATS 2026-05-10 audit `a36d33351616095f1`**: 已实现 ~1.5/3 — `CutManager._structured_signature` (cut_manager.py:192-193) frozenset dedup ✓ + `loaded_exact_safe_cuts` 的 `get_candidate_cuts(ghost_w, ghost_h)` (exact_campaign.py:384-386) **是 per-candidate restart cache，不是跨候选共享**；`_POSE_LEVEL_BINDING_CACHE` 已实现。真增量 = (a) 子问题级 LRU 没做 ~3-8%; (b) subsumption trie 是真增量 ~3-10%（CP-SAT 内置 1UIP 是 per-Solve()，不跨 invocation）; (c) cross-candidate pool 真未实现 ~2-8%（候选间结构差异大）。**净增量 ~8-25% wallclock（vs claim 20%）**，但 R3 agent 自己强调"前提是先 24h instrument 重复率 ≥15% 才划算"。工时 5-7 天（不是 3 天）含 file-lock + worker process 隔离。**Spike 先**: 加子问题 invocation key 计数 24h，重复率 <15% 直接 KILL。 | R3 `ae3c21075cb388b14` audit by `a36d33351616095f1` | gated by spike: 8-25% (gated 重复率 ≥15%) | ~5-7 days | gated by 24h spike |
| 13 | **Compiler optimization (-march, LTO, PGO)** — **PARTIALLY_REFUTED 2026-05-10 audit `a486d3f9206a2b09a`**: wheel 实测 (`objdump -d` 433 万行 + `.comment` GCC 14.2.1) 确认 baseline = **x86-64-v1 + -O3 + 无 LTO 无 PGO**——理论自编空间存在；但 R6 数字源头是 R2/R4 自己估 + JetBrains/BOLT 等**非 SAT solver** benchmark。CP-SAT control-flow 密集 (CDCL propagator/conflict-analysis), SIMD/PGO 红利天花板远低于通用 C++。修正：**march=native +2-4% / LTO +1-3% (跨 absl .so 边界无效) / PGO +2-5%**。**Stack gain 5-12%（不是 11-22%）**。"1d + 2-3d" 工时低估约 2-3 倍（OR-Tools build 30-60 min × 3 + corpus 设计 + 升级重训），真实 5-7 工作日。建议**保 P1 但缩到先做 march+LTO 一日实验**——看到 ≥+5% 才上 PGO。 | R6 `aa2cd8e2e60b20719` audit by `a486d3f9206a2b09a` | march+LTO 实验 +3-7%；PGO gated +2-5% | march+LTO 1d；PGO 5-7d (gated) | ~5-7× (实验) |

---

## P2 — opportunistic / experimental

| # | Item | Source | Save | Cost | ROI |
|---|------|--------|------|------|-----|
| 14 | **AlphaEvolve cut-evolution PoC** — **R13 refresh + 多次 audit/verify (`a8a448561dbacf07c` / `a062ff6396a691d74` / `a7f6f2df056acf347` / `abd0d088248413ba4`)**: OpenEvolve v0.2.27 ✅; AlphaEvolve arXiv 2506.13131 ✅; LLM-LNS ICML'25 spotlight 打过 Gurobi ✅。**Max 订阅跟 API 完全分开** (`abd0d088248413ba4`): "A paid Claude subscription doesn't include access to the Claude API or Console" 官方原话, 5x/20x 只覆盖 web/desktop/Claude Code, API 独立 organization + 独立 billing。**PoC 完成 2026-05-10 (子代理 mini evolve, 详 `docs/research/profiles/p2_14_alphaevolve_poc_20260510/`)**: 子代理 `ada46d235d22806ab` 一次 spawn 6 cut 变体, 启发式评分 5/6 满分 + 1/6 接近满分, 全部符合 AI Safety Contract, 5 个新颖维度 → **PoC verdict: GO production** (gated by 真长跑 baseline)。

**Production 500 iter 路径** (修订 by `a9d4b8fc01f24e9b9` user IP / `a6c3a5f3d9dc7d7f6` $1000 credit / `a7460c780eaa03097` Gemini 3.1): (A) ~~$200 promo~~ **已过期** (2026-04 一次性窗口); (B) **付 Anthropic API ~$90-115** (Opus 4.7 $5/$25 per M, 最稳); (C) **Gemini 3.1 Pro Preview $2/$12 ~$60-70** (2026-02-19 当前 frontier, 比 2.5 Pro 贵 +60%/+20%); (D) **Gemini 2.5 Pro $1.25/$10 ~$40-50** (OpenEvolve 直接支持); (E) **Vertex AI Gemini + GCP Free Credit ($110.66 余额, 5/29 到期)** (~$0 但 0.5-1 d Vertex OpenAI 集成, ROI 边际); (F) ~~$1000 GenAI App Builder credit~~ **不能 cover Gemini API** (audit `a6c3a5f3d9dc7d7f6` 验证仅限 Vertex AI Search/Agent Builder)。**Pro 系列 free tier 已废 (2026-04-01 起), 必须 paid Tier 1 + 换 model variant 才升 quota**。production 推迟到 **168h 真长跑跑出 binding solve 时间 baseline 后** 决定。**PoC 阶段用 Agent tool 子代理 (5-10 iter) 跑 mini evolve, 消耗 Max 订阅 quota 不需要 API key** — 验证 LLM 能否生成有用 cut, go/no-go gate 决定 production 是否花钱跑 OpenEvolve 完整 500 iter。Go/no-go: PoC 中 LLM 提议的 cut 在微 evaluator 评分上能否显著超过手写 baseline。 | R10 `a08591c75ba861e6e` + R13 `a8a448561dbacf07c` audit `a062ff6396a691d74` + verify `a7f6f2df056acf347` + Max-API audit `abd0d088248413ba4` | PoC 验证 LLM evolve 能力; production gated by PoC 结果 + user 选 A/B/C | PoC 30-60 min (Agent tool 5-10 iter); production 1-2 day + ~$58-115 | gated by PoC verdict |
| 15 | **IL from solver traces (S4 data already collected)** | R10 `ac82668b944498f96` | candidate ordering accuracy +N%; faster than RL by 10-100× | ~1-2 weeks | gated by expert-signal precheck |
| 16 | **cpsat-autotune Optuna full sweep** | R5 `a89d19953587dd79f` | +5-25% (not 70%) | ~1 week | ~3× |
| 17 | **ALNS Python warm-start (incumbent + AddHint)** | R6 `a7322ed66982214c7` | feasible-side LB acceleration | ~4-5 days | ~3× |
| 18 | **MUS via CPMpy QuickXplain** — **PoC 完成 2026-05-10**: 装 `cpmpy>=0.10.0` PyPI 包 dep constraint 限 ortools<=9.14, 必须 **--no-deps** 绕过 (R13 audit `ae3860a1dc6cbabb8` 没 verify pip install 这一步, 算第 5 个 PARTIALLY 翻盘点; API 在 9.15 上工作 ✅)。PoC `scripts/mus_extraction_poc.py` 微型 INFEASIBLE demo: deletion + QuickXplain 都从 6 约束精确提取 3 约束最小核心 (50% reduction)。**Production 集成需要把项目 binding/routing 子问题从 cp_model 重写成 CPMpy DSL 或 OR-Tools→CPMpy 桥接器, ~1 周量级**, 不在 PoC 范围 — 仍 P2 gated by 真长跑数据 (P1 #8 audit 已发现项目 INFEASIBLE-fallback whole-layout cut 实际罕见, 真集成 ROI 待真长跑测出 fallback 触发频率才知道)。 | R5 `a3bef849bbe8777ab` + R13 `ab56e030d7ec24cad` audit `ae3860a1dc6cbabb8` + PoC 2026-05-10 | PoC 验证 MUS 50% size reduction; production 集成 gated | PoC done; production 集成 ~1 周 (gated) | ~3× (production gated) |
| 30 | **plateau-based 动态阶段切换** （R13 新增 2026-05-10, **R13 audit `aec9dfe82ab5889ef` 修正**: 不是 paper-grounded 而是项目自创工程想法）— 不强行固定 25h/50h/85h 时间切分; Stage-2 提前进 Stage-3 if dual_growth_rate < threshold for 4h。补 P1 #7 主流程的硬切分 fallback。**注意**: R13 transcript 把 Lübke&Berg CP'25 paper（不是 AAAI'25）当依据，audit 实读 paper 发现 paper 用 fixed time-limit per phase 不是 plateau detection — **本条目为项目自创设计，无 paper 直接依据**。CP'25 #21 Koops VeriPB PB-OPT 工业可用 ✅ 但中间 ε-gap 没标准 schema ✅ → R11 #6 VeriPB exporter 90min→4-6h 自定义 transcoder 不可避免（建议先做 Stage-3 final OPT cert, 中间 ε-gap cert 暂缓）。 | R13 `a3356c51d9d10daab` audit `aec9dfe82ab5889ef` (paper 引用修正); Koops CP'25 #21 ✅ | 防 Stage-2 dual 增长慢时浪费时间 (自创设计) | 2h (动态切换) + 4-6h (R11 #6 修订估时) | gated by P1 #7 主流程 land |
| 31 | **Pumpkin solver D''' binding-subproblem audit PoC** （R13 P3→P2 升级 2026-05-10 by `adee29cf670b5c3dc` + audit `ac9e83ba97f6f4f5e`）— Pumpkin v0.3.0 PyPI (2026-02-11) Python binding (PyO3 Rust，等价 Python API) ✅ + 5 pytest + nqueens 例子 ✅。**Propagator 已实现**: cumulative / disjunctive / element / 算术 / 子句 + **all_different + table** ✅（R13 transcript 误报缺失，audit 发现已存在 → binding D''' 路径反而比 R13 估的更顺）。**仍缺**: circuit / no_overlap_2d (master/routing 不行, 仅 binding)。跟 OR-Tools CP-SAT 跑同一 binding 实例对照, 独立 audit 通道 (不替换 main solver)。 | R6 `a6341e4ac38a35db5` + R13 `adee29cf670b5c3dc` audit `ac9e83ba97f6f4f5e` | binding 子问题独立 audit 通道, 防止 OR-Tools regression 没被察觉; 约束语义比 R13 报告广 | ~3-5 day (维持估时, 风险下降) | gated by 真长跑 baseline |
| 32 | **Glasgow + VeriPB 3.0 sidecar audit PoC** （R13 P3→P2 升级 2026-05-10 by `adee29cf670b5c3dc` + audit `ac9e83ba97f6f4f5e` CONFIRMED 5/5）— Glasgow Constraint Solver gcspy Python binding ✅ (2026-05-09 仍每日 commit) + 招牌 VeriPB 3.0 proof logging ✅。binding/routing 子问题作 audit-only 通道, 不替换 main solver。作者自称"no stable API" ✅ + C++23 编译门槛高 (GCC 13+ / Clang 21+) ✅ 是风险（CachyOS GCC 已 ≥14, OK）。 | R6 `a97ae4416eb4bd8cf` + R13 `adee29cf670b5c3dc` audit `ac9e83ba97f6f4f5e` | proof-logging 独立验证通道 (P1 #7 ε-Certified 主流程的"硬证据" sidecar) | ~5-7 day (gcspy 学习 + 编译 + cert harness) | gated by P1 #7 完成 |
| 19 | **Linux migration + THP/cgroups (CachyOS, switched 2026-05-08)** — Originally pinned Fedora 43, but user reported Fedora 41-44 ALL fail to boot on ASUS Z790 motherboard (root cause: BIOS memory fragmentation + Fedora's GRUB 2.06 doesn't coalesce fragments → kernel can't allocate contiguous load region → "out of memory" at boot). Fix path: switch distro to one with newer bootloader. **CachyOS selected because**: (a) **Limine** as default EFI bootloader (verified 2026-05-08 from `src/modules/bootloader/bootloader.conf` `efiBootLoader: "limine"` + 4 alternatives selectable via packagechooser_bootloader: grub/sb-shim/systemd-boot/refind/limine) — Limine is modern UEFI bootloader codebase, bypasses GRUB 2.06 memory-fragmentation issue at root and requires no user action during install, (b) cachyos-bore kernel default = brings the +5-10% BORE/EEVDF scheduler bonus that was previously gated behind Fedora COPR, (c) jemalloc/mimalloc/tcmalloc available via pacman, (d) Python 3.13 + ortools 9.15 manylinux wheel work cleanly on Arch glibc. **Risks (mitigations)**: rolling release → use `IgnorePkg = linux* glibc python python-ortools ortools` in `/etc/pacman.conf` during 168h campaign + don't `pacman -Syu` mid-run; remote machine on Arch is risky → defer 机 B install until host A baseline confirmed. **CachyOS distro itself NO LONGER REJECTED** — earlier rejection assumed Fedora was viable; with Fedora unbootable on user's hardware, CachyOS is the highest-ROI path (combines distro fix + scheduler bonus in one move). | R2 `a8a152668dd067210` + 2026-05-08 ASUS Z790 hardware fail report | +20-45% (distro baseline +15-35% + cachyos-bore default +5-10%) | ~1 day install + base benchmark | ready to start, ISO already downloaded (E:\Fedora\ from earlier — Fedora ISO no longer used; CachyOS ISO TBD) |
| 20 | **py-spy --native profile playbook** — **part 1 done 2026-05-10** (短跑 10min profile, master 阶段热点固化在 `docs/research/profiles/p1_20_short_profile_20260510/`)。**part 2 pending**：168h 真 campaign 启动后用 `py-spy record --pid <main.py PID> --duration 600 --native` attach 抓中段 profile，补全 binding/routing 热点（本次 short profile 没走到这俩阶段，main.py 在 master iteration 1 UNKNOWN 后退出）。 | R6 `a03cda5a8b71604d1` | identifies hot paths, prerequisite to compiler tuning ROI | 4 hours | high (diagnostic) |
| 21 | **Branch-and-Price PoC (root-CG only)** | R10 `a434c6a1198c78a5a` | LP gap -30% if pricing tractable | ~1 week | gated by go/no-go |
| 22 | **HiGHS 1.14 area oracle** | R7 `a2bbf0cd35f724a3c` | LP relaxation upgrade | ~1 week | ~3× |
| 27 | **Two-host candidate-level parallel (机 A 主机 + 机 B 远程, WAN)** — 2026-05-08 user gained 2nd machine (home WAN-connected). Eligible modes (WAN-friendly only): independent campaign sessions per machine + periodic incumbent merge / cut-pool exchange (~5-30 min cadence) / async portfolio with different random_seed × worker profiles. NOT eligible: sub-ms clause sharing, inter-worker fine-grained sync. | R8 `a08abe0c37f20c6b8` (re-evaluated, NOT excluded anymore) | 2× wall-clock if both hosts utilized (best case); WAN connection overhead 5-15% | 1-2 weeks for orchestration + sync layer | gated by 机 B 规格 + 连接方式 |
| 29 | **CP-SAT `symmetry_level=0` 实验**（短跑 A/B 已部分验证 2026-05-10）— **项目实际默认强化到 `symmetry_level=3`**（不是 CP-SAT 默认 `=2`），git blame 显示是 Codex 时代 initial migrate commit 引入的，无原因记录。Profile 显示 6 个对称性检测函数累计 **~4.8% CPU**（比 audit 原估 3% 多 60%）。env override `EXACT_MASTER_SYMMETRY_LEVEL` 已存在不用加代码。**短跑 A/B 验证**（`docs/research/profiles/p2_29_symmetry_ab_20260510/`）：env 设 0 真的把所有 6 个函数 sample 都归零，省 ~4.8%。**但短跑 master 都 UNKNOWN，没法比 search 完备性 / cert hash 一致性 / incumbent 质量差异**——这是真长跑级别的判断。**生产决策保留 `=3` 默认不动**，等 168h 真长跑启动后做完整 A/B（2 个 worker process 并行，一个 `=0` 一个默认，比较 first incumbent 时间 + 多迭代后 best feasible）。 | profile A/B in `docs/research/profiles/p2_29_symmetry_ab_20260510/` | 短跑已 verify ~4.8% master CPU 省下；真长跑收益 unknown | ~30min 真长跑 A/B 实验 | gated by 真长跑 |

---

## P3 — Phase 4-5 only

- **VeriPB / cake_lpr formal proof** — R4 `a7b0041317b6e6139`, R6 `aafcddf4215ab99e7`
- **PBLean + exact-SCIP + VIPR pipeline** — R7 `aaa9a46efbbbe9596`
- **Glasgow PB sidecar (D''' audit)** — R6 `a97ae4416eb4bd8cf`
- **Spectral / SDP small-subproblem audit** — R7 `a7db41848a47c8250`
- **cvc5 binding-subproblem replacement (D'')** — R3 `a15189ea6dd761cfe`
- **Huub solver integration** — R4 `a11eb425ca2c37694` (waiting on Python binding maturity)
- ~~**Pumpkin / Glasgow LCG**~~ — R6 `a6341e4ac38a35db5` (~~track upstream~~) — **R13 升级到 P2 #31/#32**, 见 P2 段。Pumpkin Python binding + Glasgow gcspy + VeriPB 3.0 半年内成熟到 P2 PoC 等级
- **`presolve_extract_integer_enforcement` cheap-experiment slot** — R11 `a67cf942cd679915d` (DEMOTED from P0 #23 by R12 `a0b6fa2949affdad1`); ~1h to set flag and grep `"linear: extracted enforcement literal"` rule stats; only revisit if Boolean half is firing a lot in our presolve log; default keep `false`

---

## Excluded — do not re-investigate

| Direction | Reason | Source |
|-----------|--------|--------|
| ~~Distributed / multi-machine~~ | **2026-05-08 RE-OPENED**: 用户 added 2nd machine (remote, home WAN). Subset still excluded: sub-ms clause sharing (LAN-only), inter-worker fine-grained sync (CP-SAT internal). New eligible mode: candidate-level parallel + periodic incumbent sync (WAN-friendly). See updated `project_hardware_constraint.md`. | revised |
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
| OR-Tools custom C++ propagator extension | **R13 排除 2026-05-10 by `a3c49824ef52b2cb9`**: PropagatorInterface 是 internal C++ class (`ortools/sat/integer.h` + `cp_constraints.h`), 官方 Discussion #3303 推荐 reformulate 不是 subclass。无 Python binding, fork-only 路径 4 周 + PROJECT_LOCK 红线 (修改 certified proof source)。项目特异规则继续走 add_hint (软) + assumption literal (半硬) + cut callback (硬, LP relaxation 层) 三条路。 | R13 `a3c49824ef52b2cb9` |

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

## Lane view (GPT v3 review 2026-05-13)

GPT v3 全量审查指出现有 P0/P1/P2 单一 ROI 维度门槛太松——11/11 P0/P1 PARTIALLY_REFUTED。建议加一层 lane 分类:

- **Lane A — proof-safety**: 影响 exactness 边界, 出问题就是 false infeasible / false optimum, 即使没"+N%"也必须做
- **Lane B — deterministic-performance**: 落地能复现的 +N% wall-clock, 数据驱动决策
- **Lane C — speculative-research**: PoC + gated by 长跑数据, 没真长跑 baseline 之前不下结论

当前 entries 大致 mapping (不动 ROI 视图, 只是加一层 view):

### Lane A — proof-safety
- P0 #1 ghost-conditioned power cut — **landed 2026-05-13**
- P0 #2 关 EXACT_POWER_PLACEMENT_SUBPROBLEM 进 certified path — **landed 2026-05-13**
- P1 #4 add_benders_cut 接口加 condition_lits — **landed 2026-05-13**
- P1 #3 CORE_TEST_FILES 覆盖 power subproblem / coordinate cut / condition_lits — **landed 2026-05-13**
- 未来 (gated): power subproblem pole alternatives exhaustion — only relevant if EXACT_POWER_PLACEMENT_SUBPROBLEM 重启
- P3: VeriPB / cake_lpr formal proof, exact-SCIP + VIPR

### Lane B — deterministic-performance
- P0 #2 4-worker baseline — landed
- P1 #7 ε-Certified three-stage 168h split
- P1 #9 player hint/nogood — 2/3 done
- P1 #10 SMAC3 OptunaHub sampler
- P1 #13 march/LTO 实验 (PGO gated)
- P1 #24 cache-aware pack (THP/jemalloc/pinning) — landed
- P2 #19 CachyOS migration — landed
- P2 #20 py-spy native profile — part 1 done

### Lane C — speculative-research
- P1 #12 cache trio — gated by 24h spike (P1 #12 instrumentation landed)
- P2 #8 Combinatorial Benders Cuts — PARTIALLY_REFUTED, demoted to P2
- P2 #14 AlphaEvolve cut-evolution PoC — sub-agent PoC done, production gated by baseline
- P2 #15 IL from solver traces — gated by expert-signal precheck
- P2 #16 cpsat-autotune Optuna full sweep
- P2 #17 ALNS Python warm-start
- P2 #18 MUS via CPMpy QuickXplain — PoC done, production gated
- P2 #21 Branch-and-Price PoC
- P2 #22 HiGHS area oracle
- P2 #27 two-host candidate-level parallel (WAN)
- P2 #29 symmetry_level=0 实验 — short-run A/B done, full A/B gated
- P2 #30 plateau-based 动态阶段切换 — 自创设计, gated by P1 #7
- P2 #31 Pumpkin solver D''' audit
- P2 #32 Glasgow + VeriPB 3.0 sidecar audit

**怎么用 lane view**: 启动一轮工作时先确认 lane —— Lane A 优先级永远最高（不能砍）；Lane B 按 ROI 排；Lane C 不投入工时直到长跑出 baseline。

## Cross-reference

- Agent transcripts: `docs/research/agent_transcripts/`
- Per-round index + outcomes: `docs/research/INDEX.md`
- Maintenance scripts: `CLAUDE.md` § Maintenance scripts
- Hardware envelope: `project_hardware_constraint_single_machine.md` (memory)
- GPT v3 review (2026-05-13): `~/下载/zmd_v3_review_power_subproblem_audit.md` (4 power-subproblem findings) + activity log final version (5 findings + 元层面 3 条)
