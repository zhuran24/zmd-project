---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/models/flow_subproblem.py and its call sites in src/search/benders_loop.py
last_verified_against: 2026-07-11
owner: flow-diagnostic
---

# 08 拓扑流诊断器

## 8.1 当前边界

`src/models/flow_subproblem.py` 实现的是连续多商品流 LP 诊断器，不是
`certified_exact` 的前置 soundness gate，也不是 proof-bearing cut oracle。

在当前认证命题中，候选可行性由 placement、binding、routing、power 与终端复验共同决定。
flow 结果只能帮助解释空间走廊和端口拥塞：

- `FEASIBLE` 不会放宽 routing 的离散连通性检查；
- `INFEASIBLE` 或 `UNKNOWN` 在 certified 路径中不能单独淘汰候选；
- 本模块的 `bottleneck_instances` 是启发式诊断，不是 Farkas ray、最小割证书或 exact-safe cut；
- `extract_flow_matrix()` 的连续流量是诊断数据，不是传送带方向、组件类型或发布证据。

因此，旧文档所写的“第一级验证子问题”“flow 失败后不进入 routing”“自动生成 Farkas
Benders cut”均不是当前代码行为。

## 8.2 输入与网络

`build_flow_network(occupied_cells, port_dict, commodity_demands)` 在 70×70 网格上构造：

1. 未占据格形成 free-cell 节点；
2. 四邻接 free cells 形成容量为 `2.0` 的有向边；
3. 端口仅在其正前方是 free cell 时接入，端口边容量为 `1.0`；
4. 每种 commodity 建立 `S_<commodity>` 与 `T_<commodity>`，并按端口类型连接 source/sink。

这些容量是粗粒度诊断模型的参数，不等同于 `specs/09` 中离散 L0/L1 routing
组件的完整物理语义。

## 8.3 LP 约束与返回值

`FlowSubproblem.build_and_solve()` 使用 GLOP，建立：

- 每条有向边、每种 commodity 的非负连续流；
- source/sink 总需求等式；
- 非 source/sink 节点的流守恒；
- 每条非超级节点有向边的跨 commodity 容量约束。

返回值只有 `FEASIBLE`、`INFEASIBLE`、`UNKNOWN`。当前实现按有向边分别限容，
并没有把反向边合并成一个共享截面约束；不能用旧公式
`sum_k(f_uv^k + f_vu^k) <= 2` 描述代码。

## 8.4 瓶颈信息的真实强度

GLOP Python API 路径没有在本模块中提取对偶不可行射线。`_extract_bottlenecks()`
仅把网络中已登记 port 的 instance 收集为潜在 blocker。它没有证明这些 instance
构成最小割，也没有最小化冲突集。

任何把这组 instance 写成 sound no-good、Farkas certificate 或 proof-bearing
`INFEASIBLE` 的调用都会越过当前认证边界。若未来要让 flow 进入 theorem，必须另行定义离散
容量语义、证书格式、独立 verifier、replay 与发布义务，不能靠修改本文档升级其 authority。

## 8.5 与 routing / cut framework 的关系

当前正常认证拓扑是 placement master → binding → routing；flow 仅为旁路诊断。
`src/cuts/` 的 active F1-F7+F9 体系与本模块不是“自动 Farkas 回灌”的同一实现；F8 已退役。
F1/F5/F6/F7 虽已有 env-gated direct attach，仍在 certified unsafe map 中。任何 cut-family promotion
或 per-commodity flow 编码进入认证前提前，仍受 `PROJECT_LOCK.md` 的 phase 边界、Stage B/PIC
清单与 proof obligation gate 约束。
