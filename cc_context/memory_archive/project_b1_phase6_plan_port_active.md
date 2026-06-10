---
name: b1-phase6-plan-port-active
description: "2026-05-18 用户决策走 Phase 6 path-1: 改 master/binding 责任边界, 把 port-selection 决策从 binding 提到 master 让 port-conditional clearance 成立. 5 phase 子任务 #131-135 (audit / port_active vars / port-conditional clearance / commodity balance / 端到端 trial). 估时 1 周量级 (~500 LOC), minimum viable 2-3 day. 这是 B1 paradigm 的最后一公里, 解决 master a priori port_clearance over-approximation 根因."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## Phase 6 path-1 plan: master 持 port-selection 决策

### 起点 (Phase 5 实测发现)

详见 [[b1-phase5-cell-cut-findings]]. 简言之: a priori port_clearance "所有 port front 必空" 是 over-approximation, 因为 master 不知 binding 选哪些 port active. 真正 sound 需要 port-conditional.

### Phase 6 实施 (5 个子任务)

**6.1: audit binding port-selection schema** (#131, 0.5 day)
- 看 `binding_subproblem.py`: `_build_fixed_operation_domains` (line 324), `_build_generic_input_domains` (line 408), `_build_generic_output_domains` (line 375), `extract_selection` (line 618), `extract_port_specs` (line 653)
- 确认 binding 内部 BoolVar `binding_vars[instance_id][choice_idx]` (line 363-366) 表达 "这个 instance 选这种 port 配置"
- 列 binding decision space: 每 facility 几个 binding choice, 每个 choice 含一组 port active 状态

**6.2: master 加 port_active BoolVars** (#132, 1 day)
- 新文件或 PoseBoolDelegate 加 `port_active[instance_id, port_idx]` BoolVar
- 联动约束: `port_active[I, p] <= sum(x_var for (g, pose_idx) where g.instance_ids contains I and pose has port_idx p)` (即 facility instance 没摆放 → 所有 port 不能 active)
- mandatory + ro 都加 port_active

**6.3: port-conditional clearance** (#133, 0.5 day)
- 替换 Phase 5b 的 a priori hard port_clearance
- 形式: `for each (instance, port_idx): port_active[I, p] AND pose 选 (含此 port) → port_front_cell 必空`
- 实现: 联动 (pose 选 + port_active) → cell exclusivity at port_front

**6.4: commodity balance** (#134, 1 day)
- master 加 `for each commodity c: sum(port_active[I, p] for input ports producing c) == sum(port_active[J, q] for output ports consuming c)`
- 必须知道每 port 的 commodity 类型 (在 facility template 数据里)
- 让 master 强制 binding 必须满足 supply/demand

**6.5: 端到端 trial** (#135, 0.5 day)
- 跑 27×15 anchor (22,28) + 6 anchor 看是否拿 certified FEASIBLE
- 跑全 pytest 2207 验 env off 不破

### Minimum viable subset (2-3 day)

如果时间紧, 跳 6.4 commodity balance, 改让 binding 处理 supply/demand. 但这样 master 加 port_active 后 binding 仍要 enumerate matching, master 可能选 port_active 不平衡的组合让 binding INFEASIBLE — 进入 binding 反复 INFEASIBLE 的死循环 (类似 Phase 3 之前问题). **不推荐**.

完整 5 子任务才稳.

### 关键实现细节

**port_active 跟 pose 联动**:
- 每个 facility template 的 pose 数据含 `input_port_cells` / `output_port_cells`. port_idx 是 pose-local enumeration. 但**不同 pose 的 port count 可能不同** (rotation 影响).
- 简化: 每 instance 全 (input + output) ports 各 1 个 port_active BoolVar (按 facility template 的最大 port count). pose 选 → 该 pose 的 port count 个 active. 其他 port_active 强制 0.
- 或更精确: port_active 按 (template, port_local_idx) 编号, 跨 pose 共享语义.

**clearance constraint**:
- 现 PoseBoolDelegate 有 `_poses_by_port_at_cell_dir` cache (line 396 area). 改成 `_pose_port_active_at_cell_dir`: 给定 (cell, dir), 列所有 (pose_var, port_active_var) pair.
- constraint: `(pose_var AND port_active_var) → front_cell 必空`. 等价 `pose_var + port_active_var + front_cell_occupied_indicator <= 2`. 实际加 indicator 或 OnlyEnforceIf.

**commodity balance**:
- 每个 mandatory facility 的 operation_type 决定 port commodity. canonical_rules.json 里有 operation_profiles.
- balance constraint: `sum(active inputs for commodity c) == sum(active outputs for commodity c)`. 加 `sum >= required_count` for required commodity (来自 generic_io_requirements).

### Risk

1. port_active 加 ~266 instance × 5 port = 1330 个新 BoolVar. master vars 总 ~270K, 加 1330 (~0.5%) 小. 但 clearance constraints 可能多 (每 (cell, dir) port_active pair × front cell exclusivity).
2. master 可能解空间更大 (新自由度 1330 BoolVar). solve time 可能慢.
3. commodity balance 表达正确性 — 错了 master 出 infeasible binding 的 layout, 仍 stuck.

### Phase 6 完成 = goal 完成

如果 Phase 6.5 trial 27×15 拿 certified FEASIBLE/INFEASIBLE (非 UNKNOWN/UNPROVEN), 这是端到端 verified. B1 lever 完成. 项目从 14 lever 全死 → B1 paradigm 完整 land.

如果仍 UNKNOWN/UNPROVEN, B1 也死 — 但 path 1 是 final option, 没别的 incremental tweak.

### 链

- [[b1-phase5-cell-cut-findings]] — Phase 5 实测发现
- [[b1-phase3-lbbd-land]] — Phase 3 wiring
- `src/models/pose_bool_exact_master.py` — PoseBoolDelegate
- `src/models/binding_subproblem.py` — binding internal (port-selection 来源)
- `rules/canonical_rules.json` operation_profiles — commodity per port template
