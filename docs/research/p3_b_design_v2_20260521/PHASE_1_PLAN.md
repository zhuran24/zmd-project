# B Design v2 Phase 1 Implementation Plan

> **Status**: A3 Day 18-21 集成层 deliverable (2026-05-22)
> **Cross-refs**: `PHASE_0_CLOSE.md` + cut_family_specs/{01-09} + cut_lifecycle_v2 v3.2.2 + B core PoC + `../PROJECT_LOCK.md` §2B/§3A/§4 (B Design v2 边界)
> **Workflow rule** ([[gemini-review-algorithm-math]] v3): 任何决策性输出必 Gemini cross-check; 决策按稳健方向选

## 1. Scope

Phase 1 = B Design v2 9 family 完整 src 实施 + benders_loop integration + 5/20/40/80 inst ramp 测试.

**不在 Phase 1 scope** (defer Phase 2+):
- F4 升级 Kinematic Reachability (port_directions field + Stateful BFS A*)
- F8 v2 cell_owner causation split
- F9 K binary search 紧化
- Step 10 dominance/expiry/demotion
- Rust/pyo3 bitset kernel (numpy bitset 先跑通)

## 2. src/ 路径表

```
src/cuts/
├── __init__.py
├── lifecycle.py                  # Cut object schema + 9 步 lifecycle 函数
│                                   # 从 docs/research/.../poc/b_core_lifecycle_poc.py 迁
├── store.py                      # CutStore + 6 维 watcher + on_ghost_rect_changed
├── replay.py                     # replay_cut + 6 步 verify + dispatch
├── helpers/
│   ├── __init__.py
│   ├── ghost_geometry.py         # Liang-Barsky AABB intersection (Family 8)
│   ├── baseline_partition.py     # compute_baseline_partition_lens (Family 6)
│   └── power_network.py          # build_power_network + bfs_component (Family 8)
├── families/
│   ├── __init__.py
│   ├── region_capacity.py        # Family 1 validator + evaluate_geometric
│   ├── cutset.py                  # Family 2 (wrap patch_routing_core)
│   ├── port_exposure.py           # Family 3 (literal, wrap boundary_constraints)
│   ├── component_reach.py         # Family 4 (wrap d2_separator)
│   ├── pattern_nogood.py          # Family 5 (literal, wrap L16 deletion minimizer)
│   ├── shape_packing_hall.py     # Family 6 (geometric, 新 helper)
│   ├── power_hitting_set.py      # Family 7 (literal, wrap benders_loop:4219-4268)
│   ├── power_grid_reach.py       # Family 8 (geometric, 新 helper)
│   └── density_envelope.py        # Family 9 (paradigm 降级版)
├── oracles/
│   ├── __init__.py
│   ├── region_capacity_oracle.py     # 复用 cand C farkas_certificate
│   ├── cutset_oracle.py               # 复用 PCR-CUT patch_routing_core
│   ├── port_exposure_oracle.py        # 复用 boundary_constraints
│   ├── component_reach_oracle.py      # 复用 d2_separator
│   ├── pattern_nogood_oracle.py       # L16 deletion + QuickXplain
│   ├── shape_hall_oracle.py
│   ├── power_cover_oracle.py          # L16 lazy power + causation split
│   ├── power_grid_oracle.py
│   └── density_envelope_oracle.py     # area_capacity_overflow only
├── assumptions/
│   ├── __init__.py
│   └── verifiers.py              # ASSUMPTION_VERIFIERS dispatch table
└── monitor/
    ├── __init__.py
    └── cut_family_ratio.py       # F5/F9 ratio telemetry (Class C 监控)

src/tests/cuts/
├── test_lifecycle.py              # 9 步 lifecycle (从 PoC test 迁)
├── test_store.py                  # CutStore + watcher
├── test_replay.py                 # 6 步 verify + dispatch
├── test_family_1.py 到 test_family_9.py    # 每 family 单元测试
├── test_replay_suite.py           # 27+ ghost anchors (criterion #4)
└── test_helpers/                  # AABB / partition / power network

src/integration/
└── b_design_v2_hook.py           # benders_loop hook (env flag
                                    # EXACT_B_DESIGN_V2=1 切新框架)
```

## 3. 实施顺序 + 工时 (Claude pace, 稳健估)

按依赖图 + 风险 (先稳后险):

### Phase 1.0 — Framework (Day P1.1-P1.4, ~3-4 day)

| Day | 内容 | LOC est | 依赖 |
|---|---|---|---|
| P1.1 | `src/cuts/lifecycle.py` (从 PoC 迁 + 完整 9 步 函数) | ~600 | PoC |
| P1.2 | `src/cuts/store.py` (CutStore + 6 维 watcher + dispatch) | ~700 | lifecycle |
| P1.3 | `src/cuts/replay.py` (6 步 verify + GHOST_AGNOSTIC/blocked_cells_hash dispatch) | ~400 | store |
| P1.4 | `src/cuts/assumptions/verifiers.py` + `helpers/ghost_geometry.py` (Liang-Barsky AABB intersection, Gemini r24 C1 加 explicit) + `helpers/baseline_partition.py` + `helpers/power_network.py` | ~500 | - |

测试: ~1500 LOC (跟 PoC 14 test 同 pattern 扩到 framework).

**稳健点**: PoC 14/14 PASS 已验, 但 PoC 是 single-family 简化. Framework
真实施时 multi-family interaction + watcher race condition 要小心. **每 commit
立刻 Gemini cross-check** (按 v3 rule).

### Phase 1.1 — Family 1/2/3/4 (Day P1.5-P1.10, ~5-6 day)

| Day | 内容 | LOC est | 依赖 src |
|---|---|---|---|
| P1.5 | Family 1 region_capacity validator + evaluate_geometric + oracle | ~400 | farkas_certificate |
| P1.6 | Family 2 cutset (wrap patch_routing_core) | ~300 | patch_routing_core |
| P1.7 | Family 3 port_exposure (literal) | ~300 | boundary_constraints |
| P1.8 | Family 4 component_reach (wrap d2_separator) | ~300 | d2_separator |
| P1.9-10 | 集成测试 + Family 1-4 end-to-end small fixture | ~500 | - |

### Phase 1.2 — Family 5/6/7/8/9 (Day P1.11-P1.18, ~7-8 day)

| Day | 内容 | LOC est | 依赖 |
|---|---|---|---|
| P1.11 | Family 5 pattern_nogood (L16 deletion + Class C monitor) | ~400 | L16 |
| P1.12 | Family 6 shape_packing_hall (新 baseline_partition helper) | ~350 | - |
| P1.13 | Family 7 power_hitting_set (causation split) | ~450 | benders_loop:4219-4268, F5 |
| P1.14 | Family 8 power_grid_reach (新 power_network + Liang-Barsky) | ~500 | helpers |
| P1.15 | Family 9 density_envelope (paradigm 降级版, area_capacity_overflow only) | ~300 | F5 |
| P1.16-18 | F1-F8 协调 dedup + monitor + integration | ~600 | - |

### Phase 1.3 — benders_loop integration (Day P1.19-P1.22, ~4 day, v2 解耦 Gemini r24 C3)

v2 (Gemini round 24 C3): 解耦算法 bug vs IO bug — smoke test 提前到 P1.20
(纯内存) 跑通 9 family 数学逻辑, 再 P1.22 上 disk persist + rotation. 排查时
能分清 "数学错" vs "文件读写错".

| Day | 内容 |
|---|---|
| P1.19 | `b_design_v2_hook.py` hook 进 outer_search.py / benders_loop.py |
| P1.20 | **smoke test 5 inst (纯内存版, 提前 — v2 Gemini r24 C3)** — 验 9 family 数学不爆, 无 disk persist |
| P1.21 | env flag `EXACT_B_DESIGN_V2=1` 切新 vs 老 cut, A/B 测试基础 |
| P1.22 | 跨 candidate cut store 持久化 (`data/cuts/active/*.json` + `data/cuts/quarantine/*.json` 分目录, Gemini r24 D1) + capacity-based eviction (LRU, PROJECT_LOCK §4 豁免范围, 不属 Step 10) |

### Phase 1.4 — Ramp 测试 (Day P1.23-P1.28, ~6 day Claude pace + 3-5 day wall clock)

| Day | 内容 |
|---|---|
| P1.23 | 5 inst smoke (含 disk persist 版, P1.20 内存 only 通过后 disk 跑) |
| P1.24 | 20 inst ramp (验 invariant 跨 multi-candidate) |
| P1.25 | 40 inst ramp |
| P1.26 | 80 inst ramp + Class C monitor report (exit criterion #5 + #7) |
| P1.27 | 160 inst ramp + cut store size report (exit criterion #6 — **< 5 GB/worker**, Gemini r24 A1.2 修 — v1 12 GB/worker × 4 worker = 48 GB OOM 致 168h 崩) |
| P1.28 | 266 inst (full mandatory) — 真正 verdict B Design v2 解 96% utilization 几何死结 |

**wall clock 死时间**: 80/160/266 inst 每 inst 跑 inner LBBD 可能 5-30 min, 总
wall clock ~3-5 day (跟 cand C ramp 同量级).

## 4. 总工时估

- Claude pace: **~22-28 day** (8 family × 0.5-1 day + framework 4 day + integration 3 day + ramp 跑 5 day)
- wall clock 死时间: **~3-5 day** (ramp 真跑)
- 全 Phase 1: **~25-33 day Claude pace** wall clock 接近 ~30-40 day

**对比 Phase 0**: ~17 day (Day 1-17k). Phase 1 比 Phase 0 大 ~1.5-2x.

## 5. 风险 + 缓解 (稳健方向)

### R1. Framework race condition (watcher + propagation)

PoC single-thread, 实际 worker process 多 thread → on_ghost_rect_changed 跟
propagation race. **缓解**: Phase 1 framework 阶段先 single-thread, multi-thread
defer Phase 1.5.

### R2. cut store disk 占用爆 (168h campaign)

Gemini round 14 cut_lifecycle §10 已 flag. **缓解**: P1.21 加 disk quota +
rotation (active vs quarantine 分目录). 168h 预算 < 12 GB/worker (criterion #6).

### R3. Phase 0 spec 跟 src 实施细节漂移

**缓解**: 每 commit 后立刻 Gemini cross-check (按 v3 rule). 不堆累积 finding.

### R4. ramp 80/160 inst 撞新坑 (F10/F14 反例真触发)

Phase 0 spec 这些 fallback Family 5. **缓解**: P1.25 加 F10/F14 synthetic
test, ramp 出 INFEASIBLE 时验 Family 5 真接住.

### R5. 266 inst RAM 撞 48 GB cap

cand C Phase 2 v3 死路核心. **缓解**: P1.27 先 160 inst 看 cut store 增长率,
线性外推 266 是否 fit. 若 >40 GB 加 cut store rotation (capacity-based eviction,
PROJECT_LOCK §4 豁免范围, 不属 Step 10 expiry).

**RAM budget 重算** (Gemini round 24 A1.2 critical fix):
- 单机 48 GB cap = master process (~16 GB OS+CP-SAT) + 4 worker × 5 GB cut
  store + 8 GB other = **44 GB** 安全余量 4 GB
- v1 12 GB/worker × 4 = 48 GB 加 master = 必 OOM
- exit criterion #6 改 < 5 GB/worker (script v2 已修)

### R6. F9 QuickXplain 耗时爆炸 (Gemini round 24 C2 新加)

F9 v1.5 spec §5b 提到 minimize window 走 QuickXplain on window expansion,
反复调 sub-problem oracle (binding/routing/PCR-CUT). 若 oracle 是 routing,
每次调用秒级到分级, QuickXplain N 次 → 总耗时分到小时级 single anchor.

**缓解** (稳健方向): Phase 1 v1.5 实施时**直接用 Bounding Rect 作 Window**,
不强制 minimize (Phase 0 spec §5b 已标 v1.0 不 minimize, v1.1 加). Phase 2
加 QuickXplain 才上.

## 6. Decision points (Phase 1 中可能要重新走 Gemini)

按 v3 rule, 这些是 Phase 1 中**必 Gemini cross-check** 的 decision points:

1. P1.13 F7 causation split src 实施 — 多 literal cut 数学 sound 跟 spec 一致?
2. P1.14 F8 Liang-Barsky algorithm src 实施 — edge case (line 贴 ghost 边)?
3. P1.21 cut store persist disk schema — 跟 cut_lifecycle §3 schema 字段全 cover?
4. P1.25 Class C monitor 触发 (F5 > 50%) 怎么应对 — Phase 1 加 stop-ship 还是 continue?
5. P1.27 266 inst verdict — 真解了 96% utilization 还是 hit 新 paradigm 死结?

## 7. Phase 1 完成 deliverable

- `src/cuts/` 完整框架 + 9 family 实施 + 测试
- `data/cuts/*.json` 持久化 cut store (active + quarantine 分目录)
- `data/cuts/ramp_reports/{5,20,40,80,160,266}_inst.json` ramp 数据
- `scripts/b_design_v2_exit_criteria.py` 全 8 PASS (从 PENDING_PHASE_1 → PASS)
- 168h campaign go/no-go gate ✅ → 真启动 168h 大跑

## 8. Phase 1 后 (Phase 2+)

- F4 Kinematic 升级 (port_directions + Stateful BFS A*)
- F8 v2 cell_owner causation split
- F9 K binary search 紧化 + window minimize QuickXplain
- Step 10 dominance/expiry/demotion
- Rust/pyo3 bitset kernel (若 numpy 性能撞墙)
- multi-thread cut store + watcher concurrent

## 9. Cross-refs

- [[phase0-b-prep-progress]] memory — Phase 0 进度
- `PHASE_0_CLOSE.md` — Phase 0 close summary
- `PROJECT_LOCK.md` §2B/§3A/§4 — B Design v2 boundary update
- `scripts/b_design_v2_exit_criteria.py` — 8 exit criteria checklist script
- cut_family_specs/{01-09} + cut_lifecycle_v2 v3.2.2 + state_machine_v2 — spec
- poc/ — B core PoC 14/14 PASS reference
