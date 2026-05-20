# Phase 3C Master CP-SAT RAM 调研 findings (2026-05-15)

## TL;DR

- master CP-SAT peak **30 GB 大头** = solve-time propagation buffer (8 worker × ~3.5 GB/worker), 不是 build storage (build 完仅 3.10 GB).
- **真路径** = 减 `EXACT_MASTER_CP_SAT_WORKERS` (8 → 2). spike 实测 plateau **16.4 GB** (-45%).
- **-p 2 + workers=2**: 数学边缘 (2×16.4 + 8 = 41 GB vs 47 GB hardware), readiness gate 25% buffer 会 BLOCK; tight buffer 卡进.
- **-p 2 + workers=1** (待 spike#6 验): 估 peak ≤ 14 GB → needed 36 GB, 大富余 fits.

## Round 1-4 调研 verdict 矩阵

| Path | Verdict | Source |
|---|---|---|
| HiGHS rewrite (Phase 1-3) | KILL — 42 GB > 30 GB (假 win) | commits 9bee9f2 → 51a9dbc |
| SCIP separator | KILL — -24% RAM 但 wall ×10 | commit a160f7c |
| anchor slicing (GPT 提) | KILL | [[project_gpt_anchor_slicing_proposal]] |
| 8 CP-SAT params (lin/no_overlap/LP-filter/...) | KILL — 全 0~+10% 反弹 | spike#3 batch + 668bd03 + 51161b0 |
| max_memory_in_mb | KILL — broken (OR-Tools Issue #1944) | commit 3357dec |
| cover_lit family aggregate | KILL — capacity-class 非几何 silent unsound | subagent a32bfc78 |
| cover_lit sig-class aggregate | KILL — production 走 geometric encoding (cover_literals=0), wrong source path | inspector dump 2026-05-15 |
| tight pole_slot ub | KILL — build RAM -9% plateau | spike batch sweep 50/100/200/400/600 |
| EXACT_POWER 重开 | KILL — Scheme A 数学可行但 ROI -10~15% | subagent a9111515 |
| ortools 9.16 cherry-pick | WAIT — release imminent ~2 weeks | subagent af81fe96 |
| AI sidecar 集成 | DEFERRED — 现 5 cuts (门槛 1000), 需 7 天攒数据 | subagent a42525635 |
| column generation | KILL — 无 working PoC (single 2D + flow coupling) | subagent a6139410 |
| clause sharing 关掉 | KILL — MB-scale 非 GB | subagent acd85a93 |
| workers=8→2 | **WIN -45% RAM (16.4 GB plateau)** | spike#5 2026-05-15 |
| workers=8→1 | TBD (spike#6 in flight) | - |

## 30 GB 来源 (source-verified)

OR-Tools 9.15 source ([cp_model_solver.cc](https://raw.githubusercontent.com/google/or-tools/v9.15/ortools/sat/cp_model_solver.cc) +
[synchronization.cc](https://raw.githubusercontent.com/google/or-tools/v9.15/ortools/sat/synchronization.cc), subagent ab76bd4188):

- **Per-worker (replicated)**: `FullProblemSolver` + `Model local_model_` + `SatSolver` +
  `IntegerTrail` + clause db + LP scratch. propagation state per-worker.
- **Shared (single instance)**: `model_proto` (pointer-shared), `SharedClausesManager`
  (bounded ~MiB buffer), `SharedBoundsManager`.
- **Shared floor ~3.5 GB** (build storage + shared buffers)
- **8 worker × ~3.3 GB/worker scratch = ~26 GB**, 加 shared floor ~30 GB

减 workers 8→2 直接砍 6 worker × ~3.3 GB = -19.8 GB → peak ~10-12 GB
理论. spike#5 实测 16.4 GB (subagent 估值偏 optimistic; 实际 workers=2 选
default_lp + no_lp 都是 LP-heaviest, 比 average worker 重).

## production roll-out plan (spike#6 数据已 verified)

### Step 1: spike#6 (workers=1) VERIFIED 12.78 GB plateau

13:01-13:04 elapsed 11-13 min, RSS 12.77-12.78 GB **rock stable**. 13:21 elapsed
仍 12.78 GB. workers=1 master.solve 真 plateau 12.78 GB.

**-p 2 + workers=1 数学**: 2 × 12.78 × 1.10 + 8 = **36 GB < 40 GB idle avail**
(4 GB headroom). 解锁 -p 2 production 任务 #67 实质命中.

### Step 2: 24h trial validate quality (workers=1 + -p 2)

```bash
bash scripts/run_campaign_p2_workers1.sh --campaign-hours 24 --resume-campaign
```

wrapper 已 land (commit 9ace1d2), env auto-set:
- EXACT_MASTER_CP_SAT_WORKERS=1
- EXACT_GATE_WORKER_PEAK_RSS_GIB=14 (+10% buffer over 12.78 plateau)
- 默认 --parallel-processes 2

检查 (24h 后):
- RAM peak 真值 (vs spike 12.78 GB)
- candidates_proven_per_hour (vs baseline 8-worker)
- master_avg_wall_s
- workers=1 是否 INFEASIBLE 假阳性 (search diversity 弱)

### Step 3: 168h production (if Step 2 OK)

```bash
bash scripts/run_campaign_p2_workers1.sh --campaign-hours 168 --resume-campaign
```

throughput 期望 2x (双 outer parallel), wall per-candidate 可能 slower
(workers=1 search 弱). net 看 24h trial.

### Fallback path

若 workers=1 quality 不可接受:
```bash
bash scripts/run_campaign_workers2.sh --campaign-hours 168 --parallel-processes 1
```
workers=2 + -p 1 = 24 GB peak, 稳定 baseline (commit 16d8a1c wrapper).

### 风险

- workers=2 search quality 比 workers=8 弱 — wall slower, 可能 master 找不到 feasible (false UNKNOWN).
- workers=1 wall 更慢, 但 RAM 最低.
- 24h trial 是验证 quality 关键 gate.

## Round 4 candidates (post round 1-3)

Subagent a376920340 调研 round 4, 但 verify 后实际状态:

| Path | Status | Note |
|---|---|---|
| Path A: CpSolverSolutionCallback RSS-aware StopSearch | **KILL** | CP-SAT `CpSolverSolutionCallback.OnSolutionCallback` 只在 intermediate feasible solution 触发. master 当前 0 feasible 找到 → callback never fires → RSS gate 永不 trigger. 外部 watcher (SIGTERM on RSS) 是 OS OOM kill 等价, 无新功能 |
| Path B: 静态 outer-frontier infeasibility prune | **已 implemented** (subagent 错判) | `compute_exact_static_area_lower_bound` + `safe_area_upper_bound` 已 cap, 2145 → 1196 candidates (-44%). 真实 lower bound 3553 cells (mandatory 3544 + protocol_storage_box min 9), max ghost area 1347 |
| Path C-F: pose dominance / mode collapse / preprocess analysis / branch-and-cut | KILL | round 1-3 already covered or no API |

## 不会再走的 paths (避免下次浪费时间)

1. **CP-SAT 参数 tune (除 num_search_workers)**: 30+ params 试过, 全 0 改善.
2. **Model encoding 改 cover_lit / family**: production 不走 table encoding (cover_literals=0).
3. **rewrite to non-CP-SAT solver**: HiGHS / SCIP / column generation 都 fail.
4. **EXACT_POWER 拆 subproblem**: Scheme A 数学正确但 ROI 不够.

## 链 (related memory)

- [[project_30gb_real_culprit_power_coverage]] 真大头 verified
- [[project_rewrite_path_exhausted]] 旧 verdict (overridden by workers=2 win)
- [[project_p1_24_oom_blocked]] -p 4 / -p 2 OOM 历史
- [[feedback_verify_solver_param_claims]] subagent claim verify lesson

## inspector / spike artifacts (gitignored .artifacts/)

- `.artifacts/cover_lit_sig_class_poc/dump_master_build_stats.py` (build-time inspector, 73s build)
- `.artifacts/cover_lit_sig_class_poc/compute_tight_pole_ub.py` (LP set cover)
- `.artifacts/cover_lit_sig_class_poc/batch_ub_sweep.sh` (6 ub batch sweep)
- `.artifacts/spike_workers_2/` (workers=2 plateau verified)
- `.artifacts/spike_workers_1_chain.sh` / `spike_workers_4_chain.sh` (cascading chain)
- `.artifacts/spike_3param_combo/` (3-param CP-SAT 0 改善 + 反弹)
- `.artifacts/spike_tight_pole_ub/` (ub=200 fast exit)
