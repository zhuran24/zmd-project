# B1 Phase 6 Path-1 — Master 持有 Port-Selection

## 当时项目情况

B1 Phase 5 3 form 全 over-restrictive. **真因**: master 不知 binding 选哪些 port active. User /goal "开始路线1, 改责任边界".

## 为什么走这条路

把 port-selection 决策**从 binding 提到 master**. master 加 BoolVar `port_active[instance_id, port_idx]` + 联动 + commodity balance + port-conditional clearance.

理论上数学 sound — port-conditional 不是 over-approximation.

## 实验过程

4 个 form 实测:

| 配置 | vars | constraints | time | verdict |
|---|---|---|---|---|
| v1 per-pose port_active (~2.3M vars) | 2,588K | 3,106K | 134s | UNPROVEN |
| v2 grid-fc + anchor offset bug | (phantom 超 grid) | | 52.5s | INFEASIBLE (bug) |
| v3 修 anchor (sound 最小 form) 8w 300s | 333K | 867K | 346s | UNKNOWN |
| v3 1w 600s | 333K | 867K | 645s | UNKNOWN |

## 实验结果

master 持 port-selection 数学 sound 但 **架构层不可解**:
- 加 grid-level `fc[(cell, dir)]` (~16K BoolVar) + 联动 fc + sum(occupiers) <= 1 (sound a priori clearance)
- 加 pose-level `sum(fc at port_cells) >= demand × x_var`
- 总 master proto 333K vars / 867K constraints (vs baseline 285K vars OPTIMAL 53s)
- master.solve **不论 workers 或 time, 均 UNKNOWN**

solver knob 不救 — 不是 8 worker mem contention, 不是 300s timeout.

## 经验跟教训 (含瓶颈理解更新)

- **认知错误**: 之前以为 audit 第一遍推断只有 wireless_sink port 可以 inactive (scope 估 ~150 LOC PoC). PoC env flag (`EXACT_B1_PORT_CLEARANCE_SKIP_STORAGE_BOX`) verdict 否定 — 27×15 INFEASIBLE 51.5s + 15×10 INFEASIBLE 56.5s 跟 Phase 5b 几乎一样.
- **真因 (`port_binding._enumerate_side_binding_patterns`)**: total_slots < ordered_cell_count 时 backtrack 用 combinations 选子集 — 剩下 port_cell 不出现在 active_ports. **任何 facility 都可能有 inactive port_cell**. Phase 6 scope 放大到 ~200K port_active vars.
- **瓶颈理解更新**: master 持 port-selection 的 sound 数学路径下, 加 ~16K fc vars + pose-level clearance 让 master proto 333K vars + 867K cstr, master.solve 架构层不可解. 这是**第一次实测 master form scale 是 fundamental 限制** — 后来在 Augmented master Candidate D (L23) 上得到 stronger evidence.

## code/

- `code/` 含 phase6_2 v1/v2/v3 trial scripts + logs + form_compare.md + skip_storage_box PoC
- 实施: `shared_infra/src/models/pose_bool_exact_master.py` Phase 6.2 v3 (env `EXACT_USE_PORT_ACTIVE`)
