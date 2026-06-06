---
name: b1-phase6-audit-finding
description: "2026-05-18 Phase 6.1 audit + 6.1.5 PoC finding: 原 Phase 6 plan 估算错 (假设只 storage box port 可 inactive). 真因: port_binding._enumerate_side_binding_patterns 让任何 facility (fixed op / boundary_io / protocol_core / wireless_sink) pose 都可能 inactive port_cells — total_slots < ordered_cell_count 时 enumerate 选子集. Phase 6 scope 放大: port_active BoolVar 给所有 facility 的所有 port_cell, ~200K vars. PoC env flag (EXACT_B1_PORT_CLEARANCE_SKIP_STORAGE_BOX) verdict 否定 (27×15 INFEASIBLE 51.5s + 15×10 INFEASIBLE 56.5s) 后 revert."
metadata: 
  node_type: memory
  type: project
  originSessionId: continued-from-7db7f276
---

## Phase 6.1 audit 关键发现

`binding_subproblem.py` 内部 port decision 分 3 类:
1. **Fixed operation** (大部分 mandatory): `binding_vars[I][choice_idx]` AddExactlyOne 选 1 个 enumerate 好的 port 配置
2. **Generic output** (boundary_io / protocol_core): `generic_output_vars[slot][commodity]` AddExactlyOne 强制选 commodity (无 __unused__)
3. **Generic input** (wireless_sink / storage box): `generic_input_vars[slot][commodity]` AddExactlyOne 选 commodity **或 __unused__**

audit 第一遍推断: 只有 wireless_sink port 可以 inactive (有 __unused__). 其他 op_type port 必 active. → 假设 Phase 6 scope 只动 storage box.

## Phase 6.1.5 PoC 验证否定

env flag `EXACT_B1_PORT_CLEARANCE_SKIP_STORAGE_BOX=1` 让 protocol_storage_box port 不进 a priori clearance. 跑 27×15 anchor (22,28) + 15×10 anchor (28,30):

- 27×15 (22,28): **INFEASIBLE 51.5s** (vs Phase 5b 47s, 几乎无差)
- 15×10 (28,30): **INFEASIBLE 56.5s** (vs Phase 5b 55.3s, 几乎无差)

假设否定. Storage box 不是唯一 over-restriction 来源.

## 真因 (`port_binding.py:143-178`)

`_enumerate_side_binding_patterns`:
- `required = [(commodity, count)]` 从 profile 拿
- `total_slots = sum(count)` (profile demand 数量)
- 检查 `total_slots > ordered_cell_count` raise
- **但 total_slots < ordered_cell_count 时 backtrack 用 combinations(remaining, count) 选子集** — 剩下没选的 port_cell **不出现在 active_ports 中**

也就是 fixed operation pose 也可能有 5 个 port_cell 但 profile demand 只 3 个 → 选 3 个 active, 2 个 inactive.

`_materialize_side_binding` 只 materialize binding_pattern 中的 cell → 这些是 active. 其他 cell 不在 `input_ports[] / output_ports[]` 输出 (不参与 routing).

**结论**: 任何 facility 的 port_cell 都可能 inactive. a priori clearance "所有 port_cell front 必空" 对所有 op_type 都 over-restrictive.

## Phase 6 scope 调整 (放大)

原 plan 估 ~150 LOC PoC 验证后缩 scope. 实际:
- port_active BoolVar 给所有 facility 所有 port_cell
- 数量 ~200K (170K mandatory × pose × port + 30K ro storage_box × pose × port)
- 联动:
  - `port_active[gid, pose_idx, port_local_idx] <= x_var[(gid, pose_idx)]` (pose 不选则 port 必 inactive)
  - `sum(port_active for input side) == profile.input_slot_count × x_var` (active 数量精确, binding 端配 commodity)
- 端口数量约束按 (input side / output side) 分别 enforce

工作量估: ~500-800 LOC. **scope 没缩**, 但路径明确.

## Phase 6 实施计划 (revised)

- 6.2: master 加 port_active BoolVars (~200K) + 联动 (`x_var <-> port_active count`)
- 6.3: port-conditional clearance (replace Phase 5b a priori): 对每 (port_cell, dir, port_local_idx), enforce `port_active=1 → front_cell 必空`. 实现: 用 port_active 替代 pose_var 做 channeled-OR over (gid × pose_idx 维度), 然后 `any_port_active + sum(front_cell_occupier) <= 1`
- 6.4: master 端 commodity balance (按 input/output side 数量 == profile.demand × pose_active count). 不需要 commodity 粒度 — master 不知 commodity, binding 端配
- 6.5: 端到端 trial 27×15 + 6 anchor

## 文件 + 链

- `src/models/pose_bool_exact_master.py` — Phase 6.2-6.4 改动入口 (build 末尾加 port_active + 重写 a priori clearance)
- `src/models/port_binding.py:143-178` — 真因来源 (_enumerate_side_binding_patterns)
- `src/models/binding_subproblem.py` — port decision schema (audit 来源)
- `docs/research/b1_pose_bool_phase0_20260517/phase6_poc_skip_storage_box.py` + `.log` — PoC verdict 否定 evidence
- [[b1-phase6-plan-port-active]] — 原 plan (scope 估算错, 需 superseded)
- [[b1-phase5-cell-cut-findings]] — Phase 5 实测发现 (over-restrictive 真因 unconfirmed)
