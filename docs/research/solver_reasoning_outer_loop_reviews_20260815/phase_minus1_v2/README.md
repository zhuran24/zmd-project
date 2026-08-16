# Phase -1 v2：高预算死因谱

> **状态：** `RUNNING`。协议已在 `6c9fc1f4201c2eb79f0ea87b4e5530cfe245897a` 冻结；harness 提交为 `4dd5f7daf64ddcedc325159c53ccee8bd8c0c168`；run id 为 `phase-minus1-v2-r1-20260815`。
> **性质：** `non_authorizing / research_only`。本目录不产生推理外环立项、认证结论或发布权限。

## 冻结入口

- [`PHASE_MINUS1_V2_PROTOCOL.md`](PHASE_MINUS1_V2_PROTOCOL.md)：高预算完整布局、有限域 slice、窗口饱和度与结论分类。
- [`corpus_manifest_v2.json`](corpus_manifest_v2.json)：三个 deep arms、六个 calibration slices、输入身份与执行参数。
- [`phase_minus1_v2_harness.py`](phase_minus1_v2_harness.py)：deep 监控、正式 5000-event 饱和窗口、有限域 slice 与四并发 supervisor。
- [`launch_phase_minus1_v2.sh`](launch_phase_minus1_v2.sh)：`setsid nohup` launcher；顶层与每个 arm 均写 `EXIT_CODE`、`.DONE` 和完整日志。
- [`RUN_LAUNCH.md`](RUN_LAUNCH.md)：运行目录、PID、启动时 admission 与首批 slice sanity receipts。

## 前代

v1 位于 [`../phase_minus1/`](../phase_minus1/)，冻结判词为 `INCONCLUSIVE`。v2 不修改 v1 协议、证据包或判词，只把 v1 的 4.678 rounds/s、0/9 full-layout terminal 与重复局部死因作为预注册设计依据。

## 明确不做

- D3 family compilation：`DEFERRED_BY_OWNER`；
- D4 paired A/B：`DEFERRED_BY_OWNER`；
- supervisor seal、publisher、certified surface：禁止；
- preflight / slow lane：不运行。

## 发射命令

```bash
bash docs/research/solver_reasoning_outer_loop_reviews_20260815/phase_minus1_v2/launch_phase_minus1_v2.sh
```

launcher 标准输出给出唯一运行目录和 PID；只以该目录及 arm 子目录中的 `.DONE` 和结构化 receipt 判断终态。
