# Phase -1 v2 运行发射记录

> **状态：** `RUNNING`。
> **性质：** `research_only / non_authorizing`。本记录只证明预注册运行已发射，不预告结果，也不授权 D3/D4 或推理外环立项。

## 身份

- 协议冻结提交：`6c9fc1f4201c2eb79f0ea87b4e5530cfe245897a`；
- harness 提交：`4dd5f7daf64ddcedc325159c53ccee8bd8c0c168`；
- run id：`phase-minus1-v2-r1-20260815`；
- 启动 UTC：`2026-08-16T03:17:00Z`；
- 启动时仓库分支：`main`；
- launcher PID：`1691983`；
- 大工件目录：`.artifacts/solver_reasoning_outer_loop_phase_minus1_v2_20260815/phase-minus1-v2-r1-20260815/`。

## 发射形态

tracked launcher 使用：

```text
setsid nohup
→ 顶层 full.log
→ 三个 deep child 独立 process group
→ 一个串行 slice child
→ 每 arm EXIT_CODE + .DONE
→ 全部 arm 结束后顶层 EXIT_CODE + .DONE
```

发射后只读检查确认：

- corpus admission：`3/3 ADMITTED`；
- `DEEP-POSTMEM-00`：运行中；
- `DEEP-W0-ALIGNMENT`：运行中；
- `DEEP-GREEDY-S0`：运行中；
- `SLICE-POSTMEM-00-P1`：`SLICE_BINDING_EXHAUSTED / UNCENSORED`，actual product `1`；
- `SLICE-POSTMEM-00-P64`：`SLICE_BINDING_EXHAUSTED / UNCENSORED`，actual product upper bound `27`，精确枚举 27 个 selections；
- `SLICE-POSTMEM-00-P4096`：运行中。

上述两个 slice 结果只是 restricted-domain terminal calibration，不是完整布局 INFEASIBLE。

## 冻结边界

- deep max wall：每 arm `28800 s`；
- 正式窗口：`5000` events；
- 经验提前停止：至少 `60000` events、12 个完整窗、末 3 窗全部达到冻结饱和阈值；
- slice max wall：每 arm `2700 s`；
- alternative cap：不存在；
- D3：`DEFERRED_BY_OWNER`；
- D4：`DEFERRED_BY_OWNER`。

只以运行目录中的结构化 receipts、`.DONE` 和 SHA-bound journals 收割最终结果。
