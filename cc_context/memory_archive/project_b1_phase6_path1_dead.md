---
name: b1-phase6-path1-dead
description: "2026-05-18 Phase 6 path-1 (master 持有 port-selection) 实测全 verdict 死路: v1 per-pose port_active 2.3M vars UNPROVEN 134s / v2 anchor bug INFEASIBLE 52s / v3 修 anchor sound 最小 form 8 worker 300s UNKNOWN 346s / v3 1 worker 600s UNKNOWN 645s. 4 个数据点, solver knob (workers/time) 不救. sound 数学路径但 master.solve 架构层不可解. B1 paradigm Phase 0-6 全 verdict, certified FEASIBLE/INFEASIBLE 没拿到. 累积 14+1=15 条 lever 全 verdict."
metadata: 
  node_type: memory
  type: project
  originSessionId: continued-from-7db7f276
---

## Phase 6 path-1 verdict: ❌ dead end

用户 /goal "开始路线1, 改责任边界: 把 port-selection 提到 master."

### 实测数据点

| 配置 | vars | constraints | time | verdict |
|---|---|---|---|---|
| v1 per-pose port_active (~2.3M vars) | 2,588K | 3,106K | 134s | UNPROVEN |
| v2 grid-fc + anchor offset bug | (phantom 超 grid 多 fc=0) | | 52.5s | INFEASIBLE |
| v3 修 anchor (sound 最小 form) 8w 300s | 333K | 867K | 346s | UNKNOWN |
| v3 1w 600s | 333K | 867K | 645s | UNKNOWN |

### 结论

master 持有 port-selection 数学 sound 但**架构层不可解**:
- 加 grid-level `fc[(cell, dir)]` (~16K BoolVar) + 联动 fc + sum(occupiers) <= 1 (sound a priori clearance)
- 加 pose-level `sum(fc at port_cells) >= demand × x_var` (mandatory + ro storage box)
- 总 master proto 333K vars / 867K constraints (vs baseline 285K vars OPTIMAL 53s)
- master.solve 不论 workers 或 time, **均 UNKNOWN** (没 verdict)

solver knob 不救 — 不是 8 worker mem contention 问题, 也不是 300s timeout 问题.

### 关键 anchor bug 修正 (副 finding)

`PoseBoolExactMasterDelegate._build_port_lookup_cache` (line 512-551) 加 anchor offset (`cell[0]+ax`) — 但 pose 数据 occupied_cells/port_cells 是 **GLOBAL** 坐标 (anchor=occ_min). 加 anchor offset 让 phantom 坐标超 grid.

历史: Phase 5 a priori clearance 用 cache 但 self-consistent (port pose + front pose 都 phantom 偏移同样 amount), 不 expose bug. Phase 6 v2 加 grid boundary check 暴露.

Phase 6 v3 自己 reimplement cell/port lookup 不用 cache (直接 global 坐标). cache bug 保留 (因 Phase 5 path 仍 work, 不动以保 backward compat).

### 累积 B1 验证全 verdict (Phase 0-6)

- Phase 0: pose-bool master + power_coverage prototype ✅ 49-53s OPTIMAL
- Phase 1: end-to-end (master+binding+routing precheck) ✅ 但 routing front_blocked
- Phase 2: production land PoseBoolExactMasterDelegate ✅
- Phase 3: LBBD wiring ✅ 完整跑通
- Phase 4: inferred counts fix + multi-anchor LBBD trial 🟡 全 UNPROVEN (routing cut 不收敛)
- Phase 5: 3 种 cut 形式 (cell-level reactive / a priori mutual / a priori channeled-OR) 均 over-restrictive 🟡
- Phase 6 path-1: master 持 port-selection ❌ 架构层不可解

**端到端 certified FEASIBLE/INFEASIBLE 未拿到**. B1 paradigm 全 verdict.

### 下一步 options

1. **Phase 6 path-2**: master 不持 port-selection, binding-aware cut (Phase 5 cut 强化, lazy fc form). 风险高 (Phase 5 reactive cut 5 iter 1587 cuts 不收敛, lazy 同 form 可能也不收敛)
2. **接受 B1 verdict 死**: 回 L11 (牺牲严格性) 路径. 用户之前明确拒绝
3. **paradigm shift**: completely different approach (e.g. column generation, decomposition by component, problem-specific heuristic + bound)

### 链

- [[b1-phase6-audit-finding]] — Phase 6.1 audit + 6.1.5 PoC 否定 storage-box-only 假设
- [[b1-phase6-plan-port-active]] — 原 plan (scope 估算错 superseded by audit_finding + 这条)
- [[b1-phase5-cell-cut-findings]] — Phase 5 cut 不收敛
- [[2026-05-16-session-final-state]] — L14 之前 verdict 全死
- [lever verdicts](docs/lever_verdicts.md)
- `docs/research/b1_pose_bool_phase0_20260517/phase6_2_form_compare.md` — Phase 6.2 v1-v3 verdict 表
- `src/models/pose_bool_exact_master.py` — Phase 6.2 v3 sound form (env `EXACT_USE_PORT_ACTIVE` gated)
