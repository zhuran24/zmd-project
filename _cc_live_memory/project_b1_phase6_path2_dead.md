---
name: b1-phase6-path2-dead
description: "2026-05-18 路线 2 (lazy demand cut) 实测 UNPROVEN 778s (10 iter 不收敛). 跟 sketch 预测 < 30% 一致, 跟 Phase 5 cell_cut 5 iter 1587 cuts 不收敛同 framework. master 每 iter OPTIMAL (77.8s avg, baseline 53s + cut 累积), routing 反复 reject, cut 加得动但不强 — sum(blockers) <= K-demand OnlyEnforceIf form 不约束 binding port-selection 跟 master cleared subset 对齐. B1 paradigm 全 verdict 死: 路线 1 master 解不动 + 路线 2 cut 不收敛."
metadata: 
  node_type: memory
  type: project
  originSessionId: continued-from-7db7f276
---

## 路线 2 (lazy demand cut) verdict: ❌ dead

用户 /goal "试一下路线二把" 后实施 + 实测.

### 实施 (commit pending)

- **Step 1** (~135 LOC in `src/models/pose_bool_exact_master.py`):
  - 加 `_poses_by_cell_global` / `_poses_by_port_cell_dir_global` global-coord cache fields
  - `_build_global_pose_cache()` 一次构建 (global 坐标, 跟 _build_port_lookup_cache phantom-offset bug 不同路径)
  - 加 `add_routing_port_lazy_demand_cut(pose_var, op_type, tpl, pose_idx)` 方法
  - Cut form: `sum(blocker_count_k) <= K - demand`.OnlyEnforceIf(pose_var) per side (input + output, 各侧 K vs demand 看 slack)
  - Refactor Phase 6.2 v3 build 复用 global cache

- **Step 2** (~50 LOC in `src/search/benders_loop.py`):
  - 加 `_b1_use_lazy_demand` env gate `EXACT_B1_LAZY_DEMAND_CUT=1`
  - routing precheck reject 时 dedup blocked_ports 到 instance_id set
  - 调 `delegate.add_routing_port_lazy_demand_cut` per pose
  - 修 indent bug (instance-level fallback 位置错位)

### 实测 (3 个数据点)

| trial | env | max_iter | verdict | time |
|---|---|---|---|---|
| v1 | lazy_demand on | 10 | UNKNOWN | 86.4s (iter 1 bail) |
| v1 sanity | no Phase 6 | 1 | UNPROVEN | 86.8s |
| v2 修 type-field bug | lazy_demand on | 10 | **UNPROVEN** | **778.2s** |

v1 bug: routing 输出 blocked_port 没 "type" field (我假设 'in'/'out' 直接读), side="" 让 cut method 返回 False, cut_added=False, wrapper bail UNKNOWN.

v2 修: 改 API 不传 side, 函数内对 input+output 两侧各加 cut (如果有 slack). 修后完整跑 10 iter 但 cut 不收敛, UNPROVEN.

### v2 实测细节

- master 每 iter OPTIMAL (平均 77.8s/iter = baseline 53s + cut 累积 ~25s slowdown)
- routing 每 iter 反复 reject (cell-level front_blocked 仍多 ports)
- cut 累 ~10 × N cuts (N=每 iter unique pose, 估 50-100)
- 没收敛迹象 (FEASIBLE/INFEASIBLE 都没出, 10 iter 全 UNPROVEN)

### 根因 — 跟 Phase 5 cell_cut 同 framework 不收敛

Cut form `sum(blockers) <= K - demand`.OnlyEnforceIf(pose_var) 是 **weak**:
- master 拿 cut 后选 layout 满足 sum constraint (cleared port 总数 >= demand)
- binding 端 free 选 demand 个 port active, **不强制跟 master 的 cleared port 对齐**
- 如果 binding 选的 port 不在 master cleared subset, routing reject again
- master 加新 cut, binding 仍 free 选, 死循环

**根因**: master/binding port-selection 不匹配是 fundamental, 不论 prebuild (路线 1 死) 还是 lazy cut (路线 2 死) 都解不了. cut form 没强制 cross-component port-selection consistency.

### B1 paradigm 全 verdict 死

- 路线 1 (master 持 port-selection, prebuild): master.solve 架构层 UNKNOWN
- 路线 2 (master 不持, lazy cut): master OPTIMAL 但 cut 不收敛

两条路代表 B1 paradigm 在"master 加 port-aware 约束"层面的全部 incremental options. 都死了.

### 累积 16 条 lever 全 verdict (新加 B1 Phase 6 路线 2)

剩 options:
- L11 牺牲严格性 (用户拒绝)
- paradigm shift (column generation / 改 problem / heuristic+bound)
- 接受 verdict

### 链

- [[b1-phase6-path1-dead]] — 路线 1 实测死路 (master 解不动)
- [[b1-phase5-cell-cut-findings]] — Phase 5 cell_cut 同 framework 不收敛
- `docs/research/b1_pose_bool_phase0_20260517/phase6_2_path2_lazy_cut_sketch.md` — 含 sketch 跟 实测 verdict
- `docs/research/b1_pose_bool_phase0_20260517/phase6_path2_lazy_demand_trial.py` — 端到端 trial
- `src/models/pose_bool_exact_master.py` — lazy demand cut 方法 (env EXACT_B1_LAZY_DEMAND_CUT)
- `src/search/benders_loop.py` — routing reject 接 lazy cut hook
