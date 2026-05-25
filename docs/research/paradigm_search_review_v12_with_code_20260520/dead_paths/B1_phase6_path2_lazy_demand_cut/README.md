# B1 Phase 6 Path-2 — Lazy Demand Cut

## 当时项目情况

B1 Phase 6 path-1 (master 持 port-selection) 架构层不可解后. User /goal "试一下路线二把".

## 为什么走这条路

master 不持 port-selection (back to Phase 4 baseline), 但加 **lazy demand cut** routing reject 时反馈. cut form: `sum(blockers) <= K - demand`.OnlyEnforceIf(pose_var).

paradigm: 让 master 端 OPTIMAL fast 解锁, binding/routing 后 cut 给 demand-aware 约束.

## 实验过程

实施 (commit pending):
- Step 1 (~135 LOC in `pose_bool_exact_master.py`): 加 `_build_global_pose_cache` + `add_routing_port_lazy_demand_cut` 方法
- Step 2 (~50 LOC in `benders_loop.py`): env gate `EXACT_B1_LAZY_DEMAND_CUT=1` + routing precheck reject 时 dedup blocked_ports → instance_id set, 调 delegate.add_routing_port_lazy_demand_cut per pose

3 个 trial:

| trial | env | max_iter | verdict | time |
|---|---|---|---|---|
| v1 | lazy_demand on | 10 | UNKNOWN | 86.4s (iter 1 bail, type-field bug) |
| v1 sanity | no Phase 6 | 1 | UNPROVEN | 86.8s |
| v2 修 type-field bug | lazy_demand on | 10 | **UNPROVEN** | **778.2s** |

## 实验结果

v2 修 type-field bug 后完整跑 10 iter:
- master 每 iter OPTIMAL (平均 77.8s/iter = baseline 53s + cut 累积 25s slowdown)
- routing 每 iter 反复 reject (cell-level front_blocked 仍多 ports)
- cut 累 ~10 × N cuts (N=每 iter unique pose, 估 50-100)
- 没收敛迹象 (10 iter 全 UNPROVEN)

## 经验跟教训 (含瓶颈理解更新)

- **Cut form weak**: `sum(blockers) <= K - demand`.OnlyEnforceIf(pose_var) 不强制 binding 选的 port 跟 master cleared subset 对齐.
- **Root cause**: master/binding port-selection 不匹配是 fundamental, 不论 prebuild (path-1) 还是 lazy cut (path-2) 都解不了. cut form 没强制 cross-component port-selection consistency.
- **瓶颈理解更新**: B1 paradigm 全 verdict 死 (路线 1 master 解不动 + 路线 2 cut 不收敛). 这是 14+2=**16 lever 累积全 verdict** 的关键节点. 项目 paradigm investigation 此后转 GPT review v1-v5 给 6 新 paradigm framework (Path 12-17).

## code/

- `code/` 含 phase6_path2_lazy_demand_trial.py + sanity_baseline + v2 verdict log
- 实施: `shared_infra/src/models/pose_bool_exact_master.py` + `shared_infra/src/search/benders_loop.py` env `EXACT_B1_LAZY_DEMAND_CUT`
