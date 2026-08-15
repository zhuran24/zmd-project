# Phase -1：推理外环立项前实验闸

> **状态：** 协议冻结中；实验尚未开跑。
> **性质：** `non_authorizing / research_only`。本目录记录立项前证据，不产生推理外环立项、认证结论或发布权限。

## 冻结入口

- [实验协议](PHASE_MINUS1_PROTOCOL.md)：corpus、运行参数、删失语义、指标、阈值和 go/no-go 判据。
- [corpus manifest](corpus_manifest.json)：固定布局来源、SHA-256、机械 normalization、discovery/holdout 切分和 D5a canary。

## 顺序纪律

1. 先提交协议冻结根；
2. 再提交 research-only harness；
3. 之后才允许发射 D1/D2 运行；
4. D3/D4 只有在协议预先规定的重复家族触发条件满足时才开；
5. 最终 `GO_NO_GO.md` 只向 owner 提交证据，不替代 owner 的第二道立项闸。

大日志与运行目录位于 `.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/`，不进入 Git；小型结构化收据和日终判读进入本目录。
