# Phase -1：推理外环立项前实验闸

> **状态：** 协议 v1.1 已冻结；r1 已完成并因 9/9 wall censor 判 `INCONCLUSIVE`；r2 观测增强待发射。
> **性质：** `non_authorizing / research_only`。本目录记录立项前证据，不产生推理外环立项、认证结论或发布权限。

## 冻结入口

- [实验协议](PHASE_MINUS1_PROTOCOL.md)：corpus、运行参数、删失语义、指标、阈值和 go/no-go 判据。
- [corpus manifest](corpus_manifest.json)：固定布局来源、SHA-256、机械 normalization、discovery/holdout 切分和 D5a canary。
- [`phase_minus1_harness.py`](phase_minus1_harness.py)：r1 research-only fixed-placement binding/routing harness；不调用 master、seal 或 publisher。
- [`launch_phase_minus1_batch.sh`](launch_phase_minus1_batch.sh)：r1 launcher。
- [`R1_CENSORING_OBSERVATION.md`](R1_CENSORING_OBSERVATION.md)：r1 9/9 wall censor、injected D2 effect 与工件身份。
- [`phase_minus1_harness_r2.py`](phase_minus1_harness_r2.py)：只增加阶段 progress receipt 的观测增强版；协议、预算和求解路径不变。
- [`launch_phase_minus1_batch_r2.sh`](launch_phase_minus1_batch_r2.sh)：r2 launcher。
- [`D5A_EXTERNAL_WITNESS_CANARY.md`](D5A_EXTERNAL_WITNESS_CANARY.md)：外部完整布局进入当前终验链的管道分析。

## 顺序纪律

1. 先提交协议冻结根；
2. 再提交 research-only harness；
3. 之后才允许发射 D1/D2 运行；
4. D3/D4 只有在协议预先规定的重复家族触发条件满足时才开；
5. 最终 `GO_NO_GO.md` 只向 owner 提交证据，不替代 owner 的第二道立项闸。

大日志与运行目录位于 `.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/`，不进入 Git；小型结构化收据和日终判读进入本目录。

## 命令

```bash
.venv/bin/python docs/research/solver_reasoning_outer_loop_reviews_20260815/phase_minus1/phase_minus1_harness.py validate
bash docs/research/solver_reasoning_outer_loop_reviews_20260815/phase_minus1/launch_phase_minus1_batch_r2.sh
```

launcher 标准输出会给出唯一运行目录和 PID；只以该目录下的 `.DONE` 与结构化 receipt 判断终态。
