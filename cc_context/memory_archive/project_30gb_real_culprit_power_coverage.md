---
name: 30gb-real-culprit-power-coverage
description: "2026-05-15 inspector verify: 30 GB 大头是 763 pole_slot×4761 pose 域 + propagation buffer; cover_lit aggregate 死 (production 不走 table encoding)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-15 inspector dump (master.build for 36x35) 颠覆所有 subagent 估值**.

## Production 实际 encoding (inspector verified)

```
"power_coverage": {
    "representation": "coordinate_geometric",
    "encoding": "geometric_element_witness_v1",
    "powered_slots": 763,
    "pole_slots": 763,
    "cover_literals": 0,             # ← 注意 ZERO
    "witness_indices": 763,           # AddElement-based
    "element_constraints": 2289,
    "radius": 5
}
```

**所有之前 subagent (#4 / #5 / #6) 估值 cover_lit 11K-167K 都基于 source
`_add_table_power_coverage_constraints` (L4655-4705)**, **但 production 不走
这个**! 走 `_add_geometric_power_coverage_constraints` (L5285+, AddElement-based).

cover_lit aggregate (sig-class / family / 任何) 设计前提 = wrong source file.
**KILL cover_lit aggregate path**.

## 真大头 (build vs solve)

**inspector v3 实测 (36x35 grid, baseline)**:
- master.init: 12.8s
- master.build(): 73.8s
- **build-time peak RAM: 3.10 GB** (RUSAGE_SELF.ru_maxrss)
- vs spike peak (solve-time): **30 GB**

**结论**: 30 GB 大头**不在 build storage**, 在 **solve-time propagation buffer
动态膨胀** (factor ~10x build storage). tight pole_slot ub 减 build 是 linear
3.10 → 估 ~1 GB, **但 solve-time 减幅未知** — propagation buffer 不一定 linear scale
to pole_slot count.

需要 solve-time spike (跑 master.solve 全 30 min cap, 拿 ru_maxrss peak) 才知道真减幅.

之前 spike#4 (ub=200) 30 sec status=UNKNOWN exit, master.solve 没充分 unfold 30 GB,
**RAM 数据没拿到**.

## tight pole_slot upper bound — FAIL (batch sweep verified)

batch sweep 实测 (build-only, 36x35):

| ub | pole_slots | build_seconds | peak_gb | 减幅 |
|---|---|---|---|---|
| default | 763 | 73.8 | 3.10 | baseline |
| 100 | 100 | 73.9 | 2.82 | -9.0% |
| 50 | 50 | 73.8 | 2.81 | -9.4% |

减幅 **plateau 在 ~9.4%** at pole_slot=50. pole_slot **不是 build RAM driver**.
build_seconds 完全不动 (~73s constant), 跟 ub 无关.

**path KILL (build-time)**. solve-time 假设线性也站不住 (从 build linear inference).

## 真路径: EXACT_MASTER_CP_SAT_WORKERS 减少 — SUBAGENT VERIFIED 9-12 GB

subagent ab76bd4188 (CP-SAT 9.15 source-verified):
- **Per-worker (replicated)**: FullProblemSolver + Model + SatSolver + IntegerTrail
  + clause db + LP scratch. propagation state per-worker.
- **Shared (single instance)**: `model_proto`, `SharedClausesManager` (单 buffer,
  hash-dedup), `SharedBoundsManager`. **shared floor ~3.5 GB**.
- workers=2 在 CP-SAT 9.15 选 `default_lp` + `no_lp` (LP-heaviest first via
  GetFullWorkerParameters priority).

**预测 8→2 worker**: 9-12 GB peak (**-60~70%**), 不是 linear 75% 因 shared floor.

**spike#5 final verdict** (12:20-12:50, full 30 min cap):
- 49s @9.4 GB → 3:00 @16 GB → 7:00+ plateau 16.4-17.1 GB
- **final RSS max 16.38 GB** (vs baseline 30 GB = **-45%**)
- master worker profile: `master=2[EXACT_MASTER_CP_SAT_WORKERS]` env hook 正确生效
- master.solve status=UNKNOWN — 30 min 内没找 feasible (跟 baseline 8-worker 一致, problem
  难度本质非 worker 问题)
- CPU 1.8 cores busy throughout, master.solve in flight (非 build idle plateau)

**等 spike#5 final + master solve status**:
- 若 peak ≤ 15 GB → **解锁 -p 2 production** (任务 #67 命中, 2 outer × 12 GB
  = 24 GB / 47 GB 单机 fits)
- master solve quality 是 secondary concern (worker=2 比 worker=8 search 弱,
  但 wall-cap unchanged, 只影响 feasibility 找速度)

**PROJECT_LOCK status**: grep 0 hit, worker count 是 implementation detail,
不需 gate. env hook 已 exist (cp_sat_worker_config.py).

## 2026-05-15 spike#6 (workers=1) FINAL verdict

- 30 min cap 跑完, final RSS max **12.19 GiB** (12783872 KB)
- vs workers=2 plateau 16.4 GiB → **-26%**
- vs baseline 8 workers 30 GiB → **-59%**
- -p 2 + workers=1: 2 × 12.19 × 1.15 + 8 = **36 GiB fits 47 GiB** (11 GiB margin)
- **任务 #67 实质命中**: production wrapper run_campaign_p2_workers1.sh
  EXACT_GATE_WORKER_PEAK_RSS_GIB=14 (15% buffer over 12.19) calibrated for
  -p 2 production

production roll-out plan:
```bash
EXACT_MASTER_CP_SAT_WORKERS=1 \
EXACT_GATE_WORKER_PEAK_RSS_GIB=16 \
bash scripts/run_campaign_linux.sh --campaign-hours 168 --parallel-processes 2 --resume-campaign
```

caveat: workers=1 search quality 比 8 workers 弱 (单 search worker, 无 parallel
diversity). 但 baseline 8 workers 也 0 FEASIBLE 找到 (subagent ac11053494 verify),
说明问题不在 worker 数. workers=1 -p 2 throughput 2x 可能 net 加速 candidate
coverage (-p 2 双 outer 并行).

跟 hint persistence path 兼容 (subagent ac11053494 verify), 但 hint persistence
当前 0 ROI 因 0 FEASIBLE → 暂不 enable.

## 2026-05-15 update: -p 2 数学 (subagent a66c6054 verified)

- spike#5 plateau **16.4 GB** (8+ min converged plateau)
- 减幅 -45% vs 30 GB baseline ✓
- readiness gate 公式 (production_readiness_gate.py:344): `needed = parallel × 30 GB + 8 host`
- workers=2 + 25% buffer: 20.5 GB × 2 + 8 = **49 GB > 47 GB BLOCK 0.5 GB**
- No buffer (raw 16.4): 16.4 × 2 + 8 = 41 GB fits 6 GB buffer

**决策点**: buffer 25% safety conservative 但 BLOCK; 15% 边缘; no-buffer
fit. spike#6 (workers=1) 数据若 ≤ 14 GB → workers=1 + -p 2 = 36 GB fits
大富余.

**真路径** (revised plan):
1. spike#6 workers=1 verify peak ≤ 14 GB
2. update readiness gate: `WORKER_PEAK_RSS_BY_MASTER_WORKERS_GIB = {1:14, 2:20.5, 4:26, 8:30}`
3. 168h switch to **-p 2 + workers=1** (if spike#6 confirms) or
   **-p 1 + workers=2** (stability win, no throughput gain)

## 旧 path (KILL ed)

`_power_pole_slot_upper_bound` 公式 (exact_coordinate_master.py:1933-1937):
```
mandatory_powered_nonpole (219)
+ fixed_required_optional_powered_demands (0)
+ residual_optional_powered_slot_upper_bounds (protocol_storage_box: 544)
= 763
```

这是 **trivial worst-case ub** (假设每个 powered_slot 都需 own pole). 实际:
- 一个 pole radius=5 cover 大约 12 cells (相邻 powered 共用 pole)
- 219 mandatory_powered 实际可能只需 30-60 个 pole
- 现 ub 过宽 ~3-7x

### tight ub 路径

**方法 1: 几何 LP 算 tight ub**
- 每个 pole 最多 cover N=12 (radius=5 covers (2*5+1)^2=121 cells, 但占据 1, 净 cover 120 — 但只算 mandatory powered cell 重叠 = ~12 typical)
- ub = ceil(219 / 12) = 19? 太 tight
- 安全 ub = ceil(219 / 4) = 55 (conservative)
- 加 protocol_storage_box: 544 / 12 ≈ 45 pole
- 总 ub ≈ 100-150 (vs current 763)

**减 80% pole_slot count → propagation state 8 worker × 150 slot = ~6 GB peak** (vs 30 GB)

### PROJECT_LOCK 影响

`_power_pole_slot_upper_bound` 是 **search space size constraint**, 不是 **proof
basis**. tight ub 不丢 cover semantic (只是限制 search 空间). 跟 PROJECT_LOCK
"Forbidden Changes" 不冲突:
- 不 reintroduce exploratory cap (这是 derived ub 从几何, 不是任意 cap)
- 不 rebind globally pooled resource
- 不 change schemas (ub change 内部, 不动 proof object)

但**需 spec/test 同步**:
- spec: 描述 tight ub 来源 (geometric coverage bound)
- test: regression 验 same instance feasibility 不变 (old 763 vs new 150 → status 同)

### 实施 plan (Claude pace)

| Step | LOC | 工时 |
|---|---|---|
| 1 | geometric tight ub 算 (新 method `_geometric_pole_count_upper_bound`) | ~50 | 1h |
| 2 | env-gated `EXACT_POLE_SLOT_TIGHT_UPPER_BOUND=1` 切换 | ~30 | 30 min |
| 3 | regression test: same instance 跑 old + new ub, 验 feasibility 同 | ~80 | 1h |
| 4 | RAM peak 实测 spike (跟 baseline 30 GB 比) | wall 30 min | 30 min |
| 5 | spec/test 同步 + commit | ~50 (doc) | 1h |
| **总** | **~210** | **3-4h** |

ROI: -50~80% RAM (估值, 待 spike 验), 低风险 (search space tighten 数学上 sound),
不动 proof basis.

## 链

- [[rewrite-path-exhausted]]
- [[p1-24-oom-blocked]]
- [[verify-solver-param-claims]] (3 个 subagent 估值都基于错 source)

## inspector 完整 output

`.artifacts/cover_lit_sig_class_poc/dump_stats.log` (29.9 KB full dump)

key:
- mandatory: 266
- residual_optional.power_pole: 763
- residual_optional.protocol_storage_box: 544
- _power_pole_family_name_by_int count: **35** (subagent #6 PoC 算 121, 但这是
  local_signature, 不是 family — 不同 partition)
- master_mode_literals: 3146
- master_interval_count: 5666
- coordinate_symmetry.power_pole_family_order_constraints: 762
