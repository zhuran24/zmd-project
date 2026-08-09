# 07 routing-aware 构造日志（2026-07-20）

## 口径

本日志记录研究构造过程和可复核的运行事实。最终接受条件始终是：266 mandatory 全摆、辅助设施与传送带完整、六谓词由 pinned 独立 checker 全绿、body-only 最大空矩形审计与 checker 重算完全一致。构造器自己的检查只作早期拒绝，不能替代独立 checker。

若最终得到 `(A*, s*)`，它只描述该 concrete witness 的真实可行下界，不外推到全局。R3 回收信息在此构造中只新增 `P >= 9` 杆数 hard sentinel；当前实现应在少于 9 根杆时 fail closed。

基线固定为 `ea407fafaff56333bcf18066cecf890f0ef0c6da`。全部新输出留在 `07_routing_aware/` 的唯一 run/attempt 或 content-addressed artifact 中；不改 sealed/frozen/reseal 面。

## 已落地的构造链

1. `strict_contract.py` 从 strict 包与 canonical 输入独立复算实体、商品、source/sink、active/null 端口数字账并锁定输入摘要。
2. `geometry.py` 将边界选择压到 47 个允许模式，给出 placement/front/power 原语与 0/1/2 box 调度口径。
3. `network_router.py` 使用 component-typed 传输组件；crossing 只保留两条相互隔离的直 channel，弯带不与 crossing 混用。
4. `witness_io.py` 从生产端口描述导出 strict binding，分别生成 active 物理绑定与 null 映射，并以隔离解释器运行 pinned checker。
5. `objective_audit.py` 用独立的 prefix-sum 穷举核算 body-only 最大空矩形，campaign 要求其结果与 checker 的重算逐字段一致。
6. `run_supervisor.py` 与 `cgroup_telemetry.py` 实现 exclusive run、content-addressed publication、全局 prod-scale 锁、35G/39G/16G cgroup v2 限额、OOM 归因与 fail-closed 分类。
7. `construct_witness.py` 是操作员唯一的 witness 构造/复验 CLI。0-box 若接受即停；1-box/2-box 当前仅记录 `UNSUPPORTED_BOX_GEOMETRY`，不据此判断对应分支。

## Prod-scale 运行账

### `run-20260719T225524Z-ea407fa/a001`

- 终态：`UNKNOWN`，内部时间上限 600 s，`geometry_ready=false`。
- 当时 component allowed table 为 44 行；该次结果保留为旧模型运行事实，后续 48-row 修订不回写此目录。
- solver branches：2,731,496；solver wall time：600.01706967 s。
- cgroup `memory.peak=1110261760` bytes，`memory.swap.peak=0`，OOM 事件 delta 全为 0。
- 结论边界：没有可 replay geometry，没有进入 witness campaign。

### `run-20260720T001229Z-ea407fa/a001`

- 终态：`UNKNOWN`，solver wall time：600.016380553 s，`geometry_ready=false`。
- component allowed table 为 48 行；solver branches：3,302,107。
- cgroup `memory.peak=1187397632` bytes，`memory.swap.current=0`、`memory.swap.peak=0`，OOM 事件 delta 全为 0。
- 这次是 solver unknown，不是 cgroup OOM；没有可 replay geometry，也没有进入 witness campaign。

### `run-20260720T002443Z-ea407fa/a001`

- launcher 终态分类：`RESULT_INTEGRITY_INVALID`，`geometry_ready=false`。
- worker 内部 solver 终态为 `UNKNOWN`，wall time 600.014699281 s、branches 12,763,927、conflicts 11,232,601；cgroup OOM delta 全为 0。
- 运行期间研究 worker 源文件发生了迭代，supervisor 的起止身份检查据此报告 `WORKER_DRIFT: worker changed during the attempt`。该 fail-closed 分类优先于内部 solver 状态。
- 此 attempt 不提供可 replay geometry，也不进入 witness campaign。后续正式 attempt 启动后冻结 worker 源文件直到分类记录落盘。

### `run-20260720T004152Z-ea407fa/a001`

- 终态：`INFEASIBLE`，solver wall time 3.424977966 s、branches 56,768；cgroup OOM delta 全为 0。
- 该 attempt 只开放 247 个 `primary_even_rows` 杆候选，因此只否定这一启发式受限域，不能外推到 498 或 2507 杆域，也不能否定其他 shelf topology。
- cgroup `memory.peak=752816128` bytes，`memory.swap.peak=0`；没有 geometry，不进入 witness campaign。

### `run-20260720T004247Z-ea407fa/a001`

- 终态：`INFEASIBLE`，solver wall time 102.42839697 s、branches 470,787；cgroup OOM delta 全为 0。
- 该 attempt 只开放同八行全部 x 的 498 个 `fallback_rows` 杆候选，结论边界仍限于该启发式域。
- cgroup `memory.peak=875864064` bytes，`memory.swap.peak=0`；没有 geometry，不进入 witness campaign。

### `run-20260720T004641Z-ea407fa/a001`

- 终态：`UNKNOWN`，solver wall time 600.046397104 s，`geometry_ready=false`。
- 该 attempt 首次开放当前 topology 的全部 2,507 个合法杆候选；solver branches 918,857、conflicts 27,906。`UNKNOWN` 既不是可行也不是不可行结论。
- cgroup `memory.peak=1076178944` bytes，`memory.swap.peak=0`，OOM delta 全为 0；这是纯 solver unknown，不是资源失败。
- worker 在整次 attempt 中身份稳定，launcher 终态为 `SOLVER_UNKNOWN`。没有 geometry，不进入 witness campaign。

### 后续模型收缩边界

九个 operation signature 在同一 manufacturing template 内具有逐 index 完全相同的 geometry domain；body 冲突、杆冲突和供电覆盖也只依赖 template/pose。因此下一轮 geometry-power 层将这些对称变量压成每 template 一族，并保留解后 exact operation 展开及完整 lane/commodity 后验。该压缩不允许跳过后验；任何 component 或路由失败仍须 fail closed，不能把 geometry 解直接当作 witness。

## 分类边界

`CLEAN_RESULT` 与 `geometry_ready` 是两个不同层次：前者只说明 worker 过程、结果文件的 schema/integrity、HEAD 与 OOM 遥测满足运行合同；后者还要求结果中确有完整且可 replay 的几何。因而即便出现 `CLEAN_RESULT`，也必须读取 `geometry_ready`，不能直接送入构造链。

同理，solver `UNKNOWN`、timeout、signal、nonzero exit、result missing/invalid、telemetry missing 与 cgroup OOM 分别保留独立分类。`OOMPolicy=continue` 允许 worker/launcher 尽力写下计数器，但不会放宽接受门槛。

## 下一验收点

1. 只在当前 prod-scale unit 与进程终止、全局锁可安全取得后启动下一次 prod-scale attempt。
2. 仅当 `geometry_ready=true` 时，把该 attempt 的 explicit `shelf_power_result.json` 交给 `construct_witness run --geometry-result ...`；不做 latest-result 自动发现。
3. campaign 先尝试 0-box；如果独立 checker 接受则立即停止，不执行 1-box/2-box。
4. 只有 layout 摘要身份稳定、六谓词全绿、独立空矩形审计一致，才发布 content-addressed layout/manifest 并记录 `(A*, s*)` 下界。
