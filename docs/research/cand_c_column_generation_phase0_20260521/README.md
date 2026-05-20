# Phase 0 cheap gate — Column Generation / Branch-and-Price

Date: 2026-05-21
Paradigm: cand C (column generation with intermediate-granularity patterns)
Status: probe written, dry-run only — measurement queued.

## Why this paradigm

27 lever全 verdict 死 (含 Phase 0 LIC ❌ / Benders symm ❌ / IHS ❌). Common
root cause: cut amplification / accumulation / family abstraction 三 axis
全死. 几何结构性地打碎 sub-pose-level 等价性. Cut 强度上没 free lunch.

Cand C 是唯一**真换 master variable basis** 的方向：让 master 挑“板块”
（5-15 facility 提前拼好的局部 layout），不让它挑 280K 张姿势卡。

Phase 0 测的是这个 paradigm 最 fundamental 的两个前提：

1. **中间粒度 pattern 存在** — column generation 真能产出多 facility
   的 pattern，不退化为 single-facility-per-column。
2. **Pricing subproblem 不退化为原问题** — pricing 的 vars 应该远小于
   "直接用 pose-bool master 解这个 subset" 的 vars。

如果任一前提不成立，cand C 本质上 = current master，无收益。

## 9 个 metric

| metric | 含义 | 5-inst GO | 20-inst GO |
|---|---|---|---|
| m1_generated_columns | CG loop 产出 column 数 | ≤ 2,636 (≤50% 5,272 baseline) | ≤ 5,272 (≤25% 21,086 baseline) |
| m2_pricing_p95_seconds | pricing CP-SAT p95 wall | ≤ 10s | ≤ 30s |
| m3_rmp_lp_p95_seconds | RMP LP solve p95 | ≤ 5s | ≤ 5s |
| m4_rss_gb | peak RSS | ≤ 4 GB | ≤ 4 GB |
| m5_multi_facility_column_pct | column 覆盖 ≥2 facility 比例 | ≥ 30% | ≥ 30% |
| m6_single_facility_column_pct | column 覆盖 = 1 facility 比例 | ≤ 50% | ≤ 50% |
| m7_pricing_vars_vs_direct_ratio | pricing model vars / direct mini master vars | < 50% | < 50% |
| m8_mini_exactness_match | LP/integer 跟 direct master 一致 (差 ≤1) | match | match |
| m9_proxy_dual_active_pct | perimeter I/O proxy 非零 dual % | ≤ 30% | ≤ 30% |
| m9_proxy_dual_sparsity | proxy dual ≥0.1 magnitude 的 window % | ≤ 20% | ≤ 20% |

baseline `5,272` = 5 instance × ~1k pose/instance (粗估直接 pose-bool
mini master vars). `21,086` = 20 instance × ~1k pose/instance。粗估
保守上限，实际 m7 会精确算 ratio。

## GO/NO-GO 规则

**GO**: 8 个 metric 在 5-instance + 20-instance 都通过。

**NO-GO** (任一)：

- `m6 > 50%`: column 退化到 single-facility-per-column。`λ_k` 选的还是
  单 pose，cand C 等价 current master。
- `m7 ≥ 50%`: pricing model 跟直接 mini master 同 scale。Pricing 没
  decompose 出来。
- `m1` 太大：column generation 也得跑 ≥ N column 才收敛，且 N 大到接
  近 baseline。CG 没省东西。
- `m2` pricing 太慢：CP-SAT 在 region 内都不收敛，scale 上去必爆。
- `m8` mismatch：实现错（sound 性 sanity check）。
- `m9_proxy_dual_active_pct > 50%`: 太多 window 的 perimeter capacity 已经
  binding → Phase 4 加 routing 后这些 window 的 boundary dual 会爆，定价
  被迫穷举 2^144 boundary bit → 指数爆。
- `m9_proxy_dual_sparsity > 40%`: 显著非零 (≥0.1) 的 dual 占比过高，同
  上语义但更严：本来 sparse-dual 的 LP 才适合 column generation。
- 任何 phase crash。

## m9 perimeter I/O capacity proxy (Gemini round 2 finding)

### Source

External reviewer (Gemini 3.1 pro) round 2 sanity check 提出: **当前 8 个
metric 只测几何 packing (cell exclusivity + facility coverage)，没测
routing-induced boundary 压力**。Phase 4 加 routing 后，每个 12×12 window
的 144 个 boundary bit 都会被 routing 约束赋上 dual → pricing subproblem
被迫枚举 2^144 boundary 配置 → 指数爆，即使 Phase 0 几何 GO 整 paradigm
依然死。

要在 Phase 0 cheap gate **预先 forecast** Phase 4 boundary dual 是不是
会 dense，加 lightweight LP proxy 模拟 boundary capacity 压力。

### 数学

每个 12×12 window `w` 加 LP 约束 (在 RMP 端，不是 pricing 端):

```
Σ_k (port_cells_in_w of column_k) · λ_k  ≤  capacity_w
```

- `port_cells_in_w of column_k` = column k 里所有 facility pose 的 input
  + output port cell 落在 window w 内的数量。Port count 由 pose schema
  fixed (从 `candidate_placements.json` 的 `input_port_cells` +
  `output_port_cells` 字段抽)。
- `capacity_w` = window 周长 × 4 方向 - 4 corner direction-slot. 12×12
  full window = 2*(12+12)-4 = 44 perimeter cells, ×4 = 176, -16 corner
  = **160 slots**. (probe 实测确认: 70×70 grid 上 36 个 window 满 capacity
  160 一致.)

### 为什么放在 RMP 不是 pricing

1. **m9 要 LP dual** — pricing 是 CP-SAT 没有 LP dual; RMP 是 GLOP 直接
   `Constraint.dual_value()` 拿。
2. **Boundary capacity 是跨 column 的资源争用** — 多 column 共占 window
   的 perimeter，是 RMP 层的 set-packing-style 约束，不是单 column 内
   pricing 决策。
3. **Pricing 端加约束只会限制单个 column 的 port 总数**，跟 "Phase 4
   多 column 共享 boundary 时谁先抢到 slot" 不是一回事。Gemini finding
   讲的是后者。

### 物理灵感

Rent's Rule (Landman & Russo 1971): 一个 sub-circuit 的 external
connection 数 ≈ `K · T^p` 其中 T 是 gate count, p ∈ (0,1). 直接应用 = 
"任何 region 的 I/O 不能超过周长"。Global routing 文献 (Cho BoxRouter
DAC 2006) 用同样原理在 placement 阶段就提前估 routing congestion 避免
detailed routing 时撞 capacity 死锁。

### Metric 怎么算

每个 RMP solve 完抽 proxy dual 向量 (用 ortools GLOP
`Constraint.dual_value()`, sign-flip 让 ≥0 表示 binding 压力):

- 取 CG loop 最后 5 个 iter 的 dual snapshot avg (smooth 早期 bootstrap
  噪声)
- `m9_proxy_dual_active_pct` = `mean(非零 dual window 数) / 总 window 数`
  阈值: `|dual| > 1e-7`
- `m9_proxy_dual_sparsity` = `mean(≥0.1 magnitude dual window 数) / 总
  window 数` (更严)

active_pct ≤ 30% + sparsity ≤ 20% 即 GO. 表示大部分 window 的 perimeter
还宽松, Phase 4 加 routing 时 boundary 不太可能 dense-dual.

## 架构

```
                          dual π_iid, μ_xy
   +---------+   ============================>   +----------------+
   |  RMP    |                                     |  Pricing       |
   |  LP     |                                     |  CP-SAT        |
   | GLOP    |   <============================     |  region-bounded|
   |         |       new pattern (negative rc)     |                |
   +---------+                                     +----------------+

   vars λ_k ∈ [0,1]                               vars z_{iid,pose} ∈ {0,1}
   constraints:                                    constraints:
     cov_i: Σ_k [i∈k]·λ_k ≥ 1                       at most 1 pose per iid
     cell_xy: Σ_k [xy∈k]·λ_k ≤ 1                    cell exclusivity in region
                                                    2 ≤ #facilities ≤ 15
   objective: min Σ cost_k · λ_k                   objective: min cost - π·cov - μ·cells
```

每次迭代：

1. solve RMP LP → 拿 dual `π_iid` (facility coverage) 跟 `μ_xy` (cell)
2. 跑 pricing CP-SAT 在 4 个 (uniformly sampled) regions per iter，挑
   最负 reduced cost
3. 若最佳 rc < -1e-6 → 加 column，重复
4. 否则停 (LP optimum 达到)

## 关键决策点

### 1. Pattern grammar = pricing CP-SAT 自由产生 (不预生成)

不用 random sample / cluster heuristic — pricing CP-SAT 在 region 内
直接 search 出 reduced-cost-最小的 (facility, pose) 组合。Phase 0 强制
`2 ≤ #facilities ≤ 15` 让 column 必为多 facility，否则就是 baseline
重复。

**舍弃方案**: 预生成 random pattern + 验 cell overlap → 容易 miss 真
正有 routing-friendly 几何的 pattern；pricing CP-SAT 数学上 sound。

### 2. RMP backend = ortools.pywraplp GLOP

scipy 在主环境里**没装** (`.venv/bin/python -c "import scipy"` 失败)。
不为 Phase 0 装新 dep。GLOP 是 OR-Tools 自带的纯 LP，性能足够，dual
直接通过 `Constraint.dual_value()` 拿。

### 3. Pricing region 怎么切

固定 region size 12×12，stride 6，sliding window。70×70 grid 共 ~100
个 region。每 iter 试 4 个（cursor 滑动），挑最佳。

**为什么 12×12**: facility size 上限 6×4，12×12 能放下 4 个 5×5 或
6 个 3×3 — 撑得起 5-15 facility 中间粒度 hypothesis。

**为什么 stride 6**: overlap 让 column 边界有 redundancy，pricing 更
容易找到 negative rc 的 column。

### 4. Mini exactness 验证

`solve_direct_mini_master()` 复刻 production pose-bool master 的核心
form (`x_{iid,pose}` BoolVar + `AddAtMostOne` cell exclusivity)，restrict
到同 instance subset + 同 bounding region。

- m7: `max(pricing_vars) / direct_master_vars` — pricing 应该 << direct
- m8: `|CG_obj - direct_obj| ≤ 1` — sound 性 (两个 form 应该给同 cost)

m8 是 sound check 不是 quality check — Phase 0 的 cost = facility
count，强制所有 instance 出现，所以两个值都应该 = `len(instances)`。
mismatch = 实现 bug（typically：pricing 多算了 cost，或 RMP 约束写错）。

### 5. 不接的东西 (Phase 0 范围外)

- Power coverage: Phase 4 才接。
- Routing / port direction / boundary mask: Phase 2-3 接。
- Ghost rectangle anchoring: Phase 1+ 接。
- Branch-and-price 完整树: Phase 5 (Phase 0 只测 root LP)。
- 完整 lex objective (area, min_side): Phase 1+。

Phase 0 不是为了 prove cand C 完整 work，是为了 prove cand C *能*开始
work — 中间粒度 pattern 存在 + pricing 真能 decompose。

## 预期 measurement wall

| Phase | 估时 (Claude pace) |
|---|---|
| 5-instance, ≤60 iter × (RMP <1s + pricing ≤5s × 4 tries) | ~20-25 min |
| 20-instance, ≤120 iter × (RMP <2s + pricing ≤10s × 4 tries) | ~30-40 min |
| direct mini master baselines (2×) | ~1 min |

预估 wall ≤ 1h，理想情况 30-40 min。RMP 数百次 GLOP solve 是 trivial；
pricing 是大头 (~5s × ~250 calls × 2 phase)。

## 不在 Phase 0 范围

- 不改 src/
- 不读 `paradigm_search_review_v12_*` (GPT 给的方案，避免抄)
- 不参考 `lever25_ihs_phase0_*` / `benders_symmetry_*` /
  `layout_invariant_cert_*` (前 3 个 phase 0 的 dir)
- 不评估 “cand C 加 ε 修补” 之类的混合方案

## 文件

- `phase0_probe.py` — probe (无 src 依赖；纯读 `data/preprocessed/`)
- `phase0_results.json` — measurement 结果 JSON (跑 --measure 才生成)
- `phase0_status.json` — 进度/exit code (每跑必写)
- `README.md` — 本文件

## 运行

```bash
# smoke test (data 加载 + RMP toy + pricing toy)
python -u docs/research/cand_c_column_generation_phase0_20260521/phase0_probe.py --dry-run

# 完整测量
python -u docs/research/cand_c_column_generation_phase0_20260521/phase0_probe.py --measure
```

dry-run rc=0 + status=ok 才能 background 跑 measure。

## 决策

(留空，跑完 --measure 后填。)
