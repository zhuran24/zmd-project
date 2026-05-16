# Set-packing prover PoC — 2026-05-17

GPT 在 L14 weighted-occupancy 死路后推荐升级到 **set-packing branch-and-bound prover**: 直接在 (x_{g,p}) 整数变量上搜, weighted LP 当 dual bound. GPT 估 1-2 个月工作.

本 PoC: 在投资 2 周 prover prototype 之前, 先验**底层假设** — set-packing 核心是 CP-SAT 解不动的, 真瓶颈是不是这里.

## TL;DR

**❌ Set-packing prover paradigm 死路 — 攻错了层. 真瓶颈不是 set-packing 核心, 是 master 多余的 port/power/connector/boundary 约束.**

实测发现:
1. **Minimum set-packing 核心**(只含 demand + cell exclusivity + ghost-forbidden) CP-SAT 8 worker 几秒就 verdict — corner/boundary 2.3s INFEASIBLE, interior 7s FEASIBLE.
2. **Full master.solve via LBBD** 同 anchor 5-30 min UNKNOWN. 慢的部分是 master 多出来的 port_binding / power_coverage / boundary_port / exact_safe_cuts.
3. GPT 提议的 prover (BnB on x_{g,p} + weighted LP dual bound) 攻的是已经 fast 的 minimum 层. 即使写出 perfect prover, paradigm 收益 ≤ CP-SAT 现有性能.

**Verdict**: ❌ paradigm 死路. **不要投资 2 周写 prover**.

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

## 真瓶颈分析

Master vs minimum 多出来的约束:
1. **port_binding** — input/output port direction + type matching
2. **power_coverage** — power_pole 必须 cover 所有 facility, 4M+ row 大约束
3. **connector** — connector routing 通过 facility port
4. **boundary_port_feasibility** — boundary port 必须在 boundary cell
5. **exact_safe_cuts** — LBBD historic cuts
6. **mandatory_group_prechecks** — group-level prechecks

任何一个或几个的组合让 CP-SAT 30 min 也 UNKNOWN. 这是 **MIP/CP-SAT 在 dense linear constraint 上的 fundamental 难度**, 跟 [[project_highs_rewrite_blocker]] 同一根因 — 不是 solver 笨, 是 problem 本身在这套约束下 hard.

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
| `poc_minimum_setpacking.py` | Step B minimum CP-SAT (bare set-packing) |
| `poc_minimum_with_power.py` | Step B direct master.solve (数据无效 — model degenerate, 留档不删) |
| `logs/step_a_trial*.log` | Step A trial 输出 |
| `logs/step_b_trial*.log` | Step B trial 输出 |

---

## 链

- [[project_l14_weighted_occupancy_dead]] — 上一步 weighted-occupancy LP 验证
- [[project_2026_05_16_session_final_state]] — 12 lever 全 verdict 死
- [[project_highs_rewrite_blocker]] — dense linear constraint 同根因瓶颈
- [[lever_verdicts]]
