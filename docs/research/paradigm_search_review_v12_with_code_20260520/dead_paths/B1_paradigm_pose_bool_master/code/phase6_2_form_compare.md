# Phase 6.2 master 持有 port-selection 实验序列

## 设计
- master 选 layout, 用 grid-level `fc[(cell, dir)]` BoolVar 表 "front cell 不被 facility 占".
- 联动 `fc + sum(occupiers of front cell) <= 1`.
- pose-level 约束: `sum(fc at port_cells) >= demand × x_var` (mandatory) / 类似 ro storage box.

理论 sound: master 给 layout 后, binding 端在 cleared subset 选 demand 个 active port.

## 实验数据点

| 版本 | vars | constraints | workers | t | verdict |
|---|---|---|---|---|---|
| v1 per-pose port_active BoolVar | 2,587K | 3,106K | 8 default | 134s | UNPROVEN |
| v2 grid-fc + anchor offset bug | (有 phantom 坐标超 grid → 多 fc=0) | | 8 default | 52.5s | INFEASIBLE |
| v3 修 anchor (sound 最小 form) | 333K | 867K | 8 default | 346s | UNKNOWN |
| v3 + workers=1 + 600s | 333K | 867K | 1 | 645.1s | UNKNOWN |

## 分析
- v1 太多 vars (2M+) 不可行
- v2 anchor bug 暴露 INFEASIBLE (phantom 坐标让 fc=0 太多)
- v3 sound 但 master 搜索空间膨胀 — CP-SAT 在 5 min 内不解
- v3+w1 看 mem/contention 是否 root cause

## 结论: Phase 6 path-1 ❌ verdict dead

v3 + w1 实测 UNKNOWN 645.1s 确认: master 持有 port-selection 路径数学 sound, 但 master.solve **架构层不可解** (在合理时间). 不论 1 worker 600s 或 8 worker 300s, master.solve 均 UNKNOWN. 不是 form 细节或 solver knob 问题, 是 model 量级 (333K vars × constraints 联动让 search space 不收敛).

## Path E backup: lazy fc cut

- master 不 prebuild fc + sum constraint
- 第一 iter master 自由 (Phase 4 baseline 53s OPTIMAL)
- routing reject (P, port_k front_blocked) → 加 cut `sum(fc at P's port_cells) >= demand × x_var` for that P only
- cut 增量加, master incremental solve. Cut count: ~10-100 vs prebuild 280K.

风险: Phase 5 实测 cell-level reactive cut 5 iter 1587 cuts 不收敛. lazy form cut count 小但每 cut 强 (sum >= demand 形式), 可能收敛.
