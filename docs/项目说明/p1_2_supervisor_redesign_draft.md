# P1.2 supervisor redesign 草案

> **历史草案，已由当前实现与 `p1_2_supervisor_detailed_design.md` 取代。**
> 本文件保留设计动机，不得作为当前代码状态或 release readiness 的依据。

## 当时要解决的问题

旧链允许 producer 在同一控制流里求解、组装 terminal evidence、写 `CERTIFIED` 并触发公开输出。
即使存在 sink replay，也容易把“求解者提供的数据”与“独立 authority 的裁决”混为一体。草案提出：

1. producer 只落 proposal；
2. 独立 supervisor 从磁盘读取并复验；
3. public publisher 只接受 supervisor-sealed state；
4. phase gate 与技术 seal 分开。

## 当前落地映射

- proposal status：`CANDIDATE_PROPOSED`
- producer：`outer_search.py:_commit_terminal_full_frontier_certified_result`
- mint：`ExactCampaign.supervisor_seal()`
- fixed witness：`terminal_fixed_witness_capsule.py` / `terminal_fixed_witness_verifier.py`
- open gate：`certified_surface.resolve_p1_2_publish_open_gate()`
- public publisher：`publish_verified_certified_delivery_surface()`

当前工作树只实现上述 Python authority 边界；没有 production supervisor CLI/launcher。`main.py` 终点仍是
`CANDIDATE_PROPOSED`，这项操作接线属于未完成工作。

## 尚未落地的草案目标

更小/read-once/controlled-loader TCB、immutable package materialization 和完整 archive policy 仍属 PR2。
因此“架构方向已落地”不能写成“P1.2 已闭合”。
