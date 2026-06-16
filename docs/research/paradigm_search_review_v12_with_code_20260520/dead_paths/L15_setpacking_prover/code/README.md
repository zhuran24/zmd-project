# Set-packing prover PoC — 2026-05-17

GPT 在 L14 weighted-occupancy 死路后推荐升级到 **set-packing branch-and-bound prover**: 直接在 (x_{g,p}) 整数变量上搜, weighted LP 当 dual bound. GPT 估 1-2 个月工作.

本 PoC: 在投资 2 周 prover prototype 之前, 先验**底层假设** — set-packing 核心是 CP-SAT 解不动的, 真瓶颈是不是这里.

## TL;DR

**❌ Set-packing prover paradigm 死路 — 攻错了层**. PoC + Step D 层逐拆 isolation 实测**精确锁到瓶颈** = **`_add_geometric_power_coverage_constraints` (供电塔覆盖约束块)**.

实测核心数据:
1. **Minimum set-packing 核心**(只 demand + cell exclusivity + ghost-forbidden) CP-SAT 几秒搞定 — corner 2.3s INFEASIBLE, interior 7s FEASIBLE.
2. **Master skip_power_coverage=True**: 27×15 anchor (22,28)/(0,0) master.solve **完整 2 个 LBBD iter 55-66s 跑完** (status UNPROVEN — 找到可行解但还没全局验证)
3. **Master 默认 (带 power_coverage)**: 同 anchor **30 min UNKNOWN** (没 verdict).

Power_coverage 体积:
- vars: 24,824 → 57,668 (**+132%**)
- constraints: 69,910 → 132,515 (**+90%**)

加这一块, master.solve 速度从**秒级 → 30+ min UNKNOWN**. 这一块是真 bottleneck.

**GPT prover paradigm**: 攻的是 set-packing core (CP-SAT 几秒搞定的层), **不 cover power_coverage**. 即使写出 perfect prover, paradigm 救不了瓶颈层.

**Verdict**: ❌ 不要投资 2 周写 prover. 下一步算法改进应该针对 **power_coverage encoding 重设计** (跟 [[project_highs_rewrite_blocker]] / [[project_rewrite_path_exhausted]] 同根因 — dense linear constraint hard 不在 solver 选择, 在 encoding 本身).

---

## Step A: CP-SAT full master.solve via LBBD baseline

设 `EXACT_MASTER_GHOST_ANCHOR_FILTER="x,y"` 限定 anchor + 直接 `run_benders_for_ghost_rect`. 跳过 outer_search frontier 抢先.

| Trial | Anchor | 类型 | master_seconds | wall (s) | status |
|---|---|---|---|---|---|
| 2 | (22,28) | interior | 300 | 322 | UNKNOWN |
| 3 | (0,0) | corner | 600 | 622 | UNKNOWN |
| 4 | (22,28) | interior | **1800** | 1822 | **UNKNOWN** |

CP-SAT 给 30 min 单 anchor 仍 UNKNOWN. **不是给时间不够 — 是 CP-SAT 在 master 完整约束下 stuck**.

## Step B: 拆 master, 看哪层 stuck

### 1. Minimum set-packing 核心 (skip_power_coverage + 不含 port_binding/boundary_port)

只含: demand (sum x_{g,p} = d_g) + cell exclusivity (sum_overlap ≤ 1) + ghost-forbidden (x_{g,p}=0 if pose 碰 B).

| Trial | Candidate | Anchor | Workers | wall (s) | status | branches |
|---|---|---|---|---|---|---|
| B1 | 27×15 | (0,0) corner | 1 | 2.4 | **INFEASIBLE** | 0 |
| B2 | 27×15 | (22,28) interior | 1 | 300 (timeout) | UNKNOWN | 307K |
| B3 | 27×15 | (22,28) interior | 8 | 7.2 | **OPTIMAL** (feasible) | 12K |
| B4 | 27×15 | (0,0) corner | 8 | 2.3 | INFEASIBLE | 0 |
| B5 | 27×15 | (21,0) top edge | 8 | 2.3 | INFEASIBLE | 0 |
| B6 | 28×15 | (0,0) corner | 8 | 2.3 | INFEASIBLE | 0 |
| B7 | 28×15 | (21,27) interior | 8 | 7.1 | **OPTIMAL** (feasible) | 9K |

**规律**:
- Corner/boundary touching anchor: CP-SAT propagator **2-3s INFEASIBLE**, 0 branch. (boundary_storage_port 不够 boundary cell, 立刻 detect.)
- Interior anchor: CP-SAT 8 worker **7s FEASIBLE** (找到 placement). 1 worker 5 min UNKNOWN (search 慢).

**关键 insight**: minimum set-packing CORE 是 CP-SAT **轻松搞定**的, 不是难题. corner/boundary 立刻 verdict, interior 8 worker 几秒找到 feasible.

### 2. Direct master.solve isolated build (m.solve(), 不走 LBBD pipeline) — **数据无效**

Trial 8-12: 我尝试用 `MasterPlacementModel.from_exact_core(...).build().solve()` 直接调, 结果全 **0.0s INFEASIBLE**.

但 build_stats 显示 `integers: 0, booleans: 0, conflicts: 0, branches: 0`: **模型 presolve 后是空的**. 不是真的 CP-SAT 验证 INFEASIBLE, 是 isolated build 没构造完整 model (`master_pose_bool_literals: 0`). 数据**作废**, 不能用作 paradigm 判断.

正确的 baseline 用 Step A (走 run_benders_for_ghost_rect, model 构造完整).

---

## paradigm 假设 evaluation

GPT 假设:
1. **CP-SAT 在 set-packing 上 stuck, custom prover 更强**
2. **Prover paradigm 投资 1-2 月有 ROI**

### 假设 1 — ❌ 不成立

minimum set-packing core (B1-B7):
- Corner/boundary: CP-SAT 2-3s INFEASIBLE, 0 branch (propagator instant)
- Interior: CP-SAT 8w 7s FEASIBLE

CP-SAT 在 set-packing 核心**完全够用**, 几秒级 verdict. paradigm 假设 1 直接 ❌.

那 Step A 30 min UNKNOWN 哪里来的? 是 master **多余的 port_binding / power_coverage / boundary_port / exact_safe_cuts** 让 CP-SAT 卡住.

### 假设 2 — ❌ 攻错层

GPT 的 prover 设计 (BnB on x_{g,p} + LP dual bound) 攻的是 minimum 核心. minimum 核心 CP-SAT 已经 fast. prover 即使写出来也最多 match CP-SAT, 不会快几个数量级.

真要 prove candidate INFEASIBLE, 必须 leverage master 多余约束 (port / power / boundary). GPT 的 set-packing prover paradigm 不 cover 这些约束.

---

## 真瓶颈 layer-by-layer 锁定 (Step D)

### Exact master coordinate-based 模型的真实 layers

跟 minimum pose-bool 模型不一样, exact master 用 **coordinate-based** (x, y, mode IntVars + AddNoOverlap2D 几何不重叠). build() 顺序 (CoordinateExactMasterDelegate.build at exact_coordinate_master.py:3010):

1. `_create_mandatory_slot_vars` — 266 个 mandatory facility 的 (x, y, mode) IntVars
2. `_create_required_optional_slot_vars` — required optional slot vars
3. `_create_residual_optional_slot_vars` — residual optional vars (power_pole 等)
4. `_create_power_pole_slot_vars` — power_pole 专用 slot vars
5. `_add_coordinate_symmetry_breaking`
6. `AddNoOverlap2D(_core_x_intervals, _core_y_intervals)` — 266 矩形不重叠 (geometric)
7. `_add_ghost_constraints` — ghost rect 排斥
8. **`_add_geometric_power_coverage_constraints`** ← 真瓶颈 (skip 开关存在)
9. `_add_global_valid_inequalities`
10. `_add_search_guidance`

### Step D 实测: skip_power_coverage on/off

| Config | vars | constraints | master.solve 27×15 anchor (22,28) wall | status |
|---|---|---|---|---|
| skip_power=True | 24,824 | 69,910 | **65.9s** (2 LBBD iter 全跑完) | UNPROVEN |
| skip_power=True (anchor 0,0) | 24,824 | 69,910 | **54.3s** | UNPROVEN |
| skip_power=False (full) | 57,668 | 132,515 | **30 min UNKNOWN** | UNKNOWN |

差异:
- vars: +32,844 (+132%)
- constraints: +62,605 (+90%)
- master.solve wall: **几十秒 → 30 min UNKNOWN, 跨数量级**

### 锁定 verdict

真 bottleneck = **`_add_geometric_power_coverage_constraints`** (exact_coordinate_master.py:5327).

power_coverage encoding 内部: 每个 powered_slot (facility cell) 需要找一个 pole_slot 在 radius 范围内 cover, 用 element_witness_v1 / table_pairwise_witness_v1 encoding. 这是 **disjunctive coverage constraint** (对每 facility, "存在某 pole 在范围内"是 OR-of-many-pairs), CP-SAT 在这种密集 disjunctive linearization 上跟 LP-MIP 一样 stuck.

跟 [[project_highs_rewrite_blocker]] (HiGHS 重写撞 42 GB RAM) / [[project_rewrite_path_exhausted]] (任何 LP-MIP solver 对 dense linear constraint 解不动) **同根因**.

### 算法改进方向 (下一阶段, 这次不做)

1. **重设计 power_coverage encoding** — 不要 disjunctive over-all-pole-pairs, 改 column generation / lazy cut / 几何 separator (类似 SCIP separator callback PoC, 验过 fire OK 但 production 集成未完)
2. **缩 powered_slot × pole_slot pair 数量** — 现 266 facility × ~100 pole = 26K pair, 加 geometric pre-pruning 可能减一半
3. **Lazy power_coverage 进 binding subproblem** — master 只保 set-packing 核心, power 进 LBBD subproblem 按需触发. PROJECT_LOCK 禁止 EXACT_POWER_PLACEMENT_SUBPROBLEM 重开 (L4), 但 lazy cut style 不同
4. **加 dominance + reduce variable count** — power_pole slot 数量上限可能能压, 见 [[project_phase3c_roadmap]] #84 (tight pole_slot upper bound -80%)

未来真要算法改进, 围绕 #1 / #2 / #4. #3 看 PROJECT_LOCK 重审 vs lazy cut 边界.

---

## 下一步选项 (不是 set-packing prover)

| 路径 | 描述 | 估计 |
|---|---|---|
| 1. **拆 port/power 进 separator** | LBBD 进一步分解, master 只保 set-packing 核心, port/power 进 lazy cut. 用 SCIP separator callback. | Phase 4 重写 attempt 已验死路 [[project_rewrite_path_exhausted]] |
| 2. **改数据** | 扩 community blueprint 到 266 mandatory, 改 greedy heuristic 尊重 blueprint 空地. 让 [[project_v10_witness_preflight_dead]] 可能复活 | 1-2 周, ROI 未知 |
| 3. **L11 hard-fix blueprint** | 牺牲严格性, 用 community blueprint 当 ground truth. 用户已拒绝 | 1-2 天, 但破坏 PROJECT_LOCK |
| 4. **L6 AI sidecar** | ML 学 master heuristic / cut. long-term, 收益不确定 | 1-2 月 |
| 5. **接受 verdict** | Phase 3B 至此终结, 用户决定 release 现有 incumbent (area 405) 还是搁置 | 无工作量 |

---

## 文件清单

| 文件 | 内容 |
|---|---|
| `poc_single_anchor_baseline.py` | Step A driver (run_benders_for_ghost_rect, env anchor filter) |
| `poc_minimum_setpacking.py` | Step B minimum CP-SAT (bare set-packing, pose-bool 形式) |
| `poc_minimum_with_power.py` | Step B direct master.solve (数据无效 — model degenerate, 留档不删) |
| `poc_layer_isolation.py` | Step D: skip_power_coverage=True/False 对比 |
| `poc_count_layers.py` | Step D: 数 power_coverage 加多少 vars/constraints |
| `logs/step_a_trial*.log` | Step A trial 输出 |
| `logs/step_b_trial*.log` | Step B trial 输出 |
| `logs/step_d*.log` | Step D layer isolation 输出 |

---

## 链

- [[project_l14_weighted_occupancy_dead]] — 上一步 weighted-occupancy LP 验证
- [[project_2026_05_16_session_final_state]] — 12 lever 全 verdict 死
- [[project_highs_rewrite_blocker]] — dense linear constraint 同根因瓶颈
- [[lever_verdicts]]
