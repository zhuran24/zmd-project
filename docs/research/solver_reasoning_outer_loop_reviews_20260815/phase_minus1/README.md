# Phase -1：推理外环立项前实验闸

> **状态：** 协议 v1.1 已冻结；corpus 静态 admission `9/9` 通过；实验尚未开跑。
> **性质：** `non_authorizing / research_only`。本目录记录立项前证据，不产生推理外环立项、认证结论或发布权限。

## 冻结入口

- [实验协议](PHASE_MINUS1_PROTOCOL.md)：corpus、运行参数、删失语义、指标、阈值和 go/no-go 判据。
- [corpus manifest](corpus_manifest.json)：固定布局来源、SHA-256、机械 normalization、discovery/holdout 切分和 D5a canary。
- [`phase_minus1_harness.py`](phase_minus1_harness.py)：research-only fixed-placement binding/routing harness；不调用 master、seal 或 publisher。
- [`launch_phase_minus1_batch.sh`](launch_phase_minus1_batch.sh)：以 `setsid nohup` 发射长运行，写 `EXIT_CODE` 和 `.DONE`。

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
bash docs/research/solver_reasoning_outer_loop_reviews_20260815/phase_minus1/launch_phase_minus1_batch.sh
```

launcher 标准输出会给出唯一运行目录和 PID；只以该目录下的 `.DONE` 与结构化 receipt 判断终态。
