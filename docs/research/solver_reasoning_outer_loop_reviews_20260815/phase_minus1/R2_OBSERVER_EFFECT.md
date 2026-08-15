# Phase -1 r2：累计 progress snapshot 的观测者效应

> **运行目录：** `.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/phase-minus1-r2-20260815/`
> **终止状态：** `EXTERNAL_INTERRUPT / HARNESS_INSTRUMENTATION_OBSERVER_EFFECT`，`EXIT_CODE=70`。
> **性质：** r2 的阶段顺序与已落 append/receipt 事件可作诊断；其性能、proposal 速率和 terminal 结果不可采纳。

## 为什么主动终止

r2 为了避免 r1 的“终态前全空白”，每经过一个昂贵阶段就把**累计全部 events 与 feedback receipts**重新写入一个原子 JSON snapshot。第一布局 `POSTMEM-00` 在 180 秒 watchdog 前已把 progress 文件写到约 60 MB。

其最后完整 progress 显示：

- binding proposals：95；
- binding solves：95；
- exact routing prechecks：95；
- routing solves：0；
- organic feedback applied：95；
- 已完成 next-selection effect：94；
- 末个 feedback 在 watchdog 时仍 pending；
- 95 个观察全部是 exact `front_blocked`，precheck replay 均一致；
- 实际消费仍是 285-literal 完整 binding-selection nogood。

但计时拆分只有：

- occupancy build：约 0.167 秒；
- binding build：约 0.237 秒；
- 95 次 binding solve 累计：约 2.564 秒；
- 95 次双份 exact precheck 累计：约 0.375 秒；
- routing build/solve：0 秒。

真实模型与 precheck 工作合计约 3.34 秒，剩余约 175 秒主要由反复序列化和改写累计 progress 消耗。继续跑完整 corpus 会测量 logger，而不是 binding/routing 接口。

因此主执行席终止整个 process group，并写入：

```text
.DONE
EXIT_CODE=70
RUN_TERMINATION.json
```

终止时保留 `POSTMEM-00` layout receipt 和 `POSTMEM-00/01` progress receipts。没有把 r2 的 wall timeout 当作求解墙，也没有修改冻结协议、预算或阈值。

## r2 仍提供的有效诊断

1. **真实热点形状被看见：** 当前布局反复经历 `binding FEASIBLE → exact precheck front_blocked → selection nogood → next binding FEASIBLE`，而 routing solver 尚未被调用。
2. **producer→consumer 有机链可达且有效：** 已完成的 94 个 organic feedback 都改变了下一 selection。
3. **接口信息比消费形式丰富：** 每轮 precheck 通常给出约 545–557 个 blocked ports、约 267–279 个 placement conflict instances，并能完全重放；当前 consumer 却只编译成一个 285-literal 的完整 selection point nogood。
4. **r2 的原标签需要校正：** `binding_selection_family` 只能描述诊断候选来源，不能描述实际消费形式；r3 将实际 `feedbackForm` 固定为 `point_nogood`，局部 blocked-port 几何只登记为 `NOT_COMPILED` diagnostic candidates。

## r3 修法

r3 不再保存累计快照：

- tiny atomic progress 只含当前 stage、计数、计时与最后事件摘要；
- 每次 precheck 追加一行 compact event JSONL；
- 每次 feedback applied/outcome 追加一行 compact feedback JSONL；
- blocked ports 被压成数量、冲突并集、局部几何签名计数与摘要哈希，不复制完整历史；
- parent watchdog 从 append-only journals 生成删失 receipt。

r3 只修证据观测，不改 corpus、discovery/holdout、20/30/180 秒预算、workers、seed、无 ALT_CAP 口径、D3/D4 门槛或 go/no-go 判据。
