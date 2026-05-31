---
name: b1-phase5-cell-cut-findings
description: "2026-05-18 commit 47b6230: B1 Phase 5 3 种 cut 形式实测均 over-restrictive (cell-level reactive 不收敛 / a priori mutual 切多 facility 共享 port_cell / a priori implication 切假设所有 port 必 active). Root cause: a priori port_clearance 是 over-approximation — master 不知道 binding 选哪些 port active. 真正 sound 需要 port-conditional constraint (binding 选 port → port active → port front 空). 这是 Phase 6 path-1 工作 (改 master/binding 责任边界)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## Phase 5 三种 cut 实测全 over-restrictive

### 实验

1. **Cell-level reactive cut** (`PoseBoolDelegate.add_routing_port_blocking_cell_cut`):
   - mutual exclusion form: `sum(port_poses_at_C_d) + sum(front_poses) <= 1`
   - 实测 5 iter 加 1587 cuts, blocked_ports 仍 519-611 浮动不收敛
   - 切掉合法解 (多个 facility 共享 port_cell)

2. **A priori hard mutual** (env `EXACT_B1_PORT_CLEARANCE_HARD`):
   - 47666 个 `sum(port) + sum(front) <= 1` constraints
   - 6 anchor + 4 small candidate (10-20×10-15) **全 INFEASIBLE in 47-56s**
   - over-restrictive (同 cut 1 切多 facility 共享)

3. **A priori hard implication (channeled-OR)**:
   - `any_port = OR(port_poses)` + `any_port + sum(front) <= 1`
   - 47666 主约束 + ~K1 channeling
   - 同 INFEASIBLE 47s — sound form 但仍 over-approximation

## Root cause: master 不知 binding 选哪些 port

每个 mandatory facility 有 5-7 个 port (input/output). binding 阶段选其中**一部分**接 commodity, 剩下当 "generic input/output slot" 不要求 routing.

**没接的 port 前面被堵没事** — 没传送带要从那出.

我加的 a priori port_clearance 把"所有 port 必须 active"当 hard, 自然 INFEASIBLE.

routing precheck 也是 same over-approximation (历史上一直 reject 所有 layout — Phase 4 UNPROVEN). 实际 routing CP-SAT 可能能 solve some layouts (bypass routing precheck trial 跑 42 min binding enumerate stuck, 不可定论).

## Path 1 (用户选): 改 master/binding 责任边界 — Phase 6

把 port-selection 决策从 binding 提到 master:
1. master 加 BoolVar `port_active[instance_id, port_idx]`
2. master 加 constraint `port_active <= pose 选" 联动 (pose 不选 → port 不能 active)
3. master 加 commodity balance: 每 commodity supply == demand (跨 active ports)
4. master 加 port-conditional clearance: `port_active=1 → port_front 必空`
5. binding 拿 master 的 port_active 选择, 在已选用的 port 中配对 (现在自由)

估时 1 周量级 (~500 LOC + 调试). minimum viable subset 可能 2-3 day.

## Phase 6 task list (#131-135)

- 131: audit binding port-selection schema
- 132: master 加 port_active BoolVars
- 133: port-conditional clearance
- 134: master 端 commodity balance
- 135: 端到端 trial 27×15

## 12 commit 累计 B1 (2026-05-17 → 2026-05-18)

- `12f5e64` Phase 0 prototype 5 anchor verdict GO
- `237a74b` Phase 1 end-to-end master+binding
- `7b8b31d` Phase 2 code audit
- `8f7cb2c` Phase 2 caveat
- `31fb3ea` Phase 2 production land (PoseBoolDelegate + env flag)
- `22cb862` Phase 2 lever_verdicts update
- `f19b5a0` Phase 3 wiring
- `131fb78` Phase 3 lever_verdicts
- `c64d15f` Phase 4 inferred counts fix + multi trials
- `5e29f42` Phase 4 lever_verdicts
- `47b6230` Phase 5 cell-level cut + a priori port_clearance (这次)

## 链

- [[b1-phase3-lbbd-land]]
- [[b1-phase4-routing-convergence]]
- `src/models/pose_bool_exact_master.py` — PoseBoolDelegate (含 port_lookup cache)
- `src/search/benders_loop.py` — 3 env-on branches (line 5169-5197 direct instantiate / line 5408 skip precheck / line 4515 cell-cut path)
- `src/models/routing_subproblem.py` line 320 — `port_cell` 加入 blocked_port output
