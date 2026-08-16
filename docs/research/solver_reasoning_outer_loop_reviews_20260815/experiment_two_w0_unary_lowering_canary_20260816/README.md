# 实验二：W0 一元 lowering 金丝雀

> **当前状态：** `PROTOCOL_FROZEN_PENDING_IMPLEMENTATION`；本目录首次进入 Git 的提交是冻结身份，后续实现不得回改门槛。
> **日期：** 2026-08-16。
> **权限边界：** research-only；只验证一条已证 W0 Judgment 的静态 lowering 与真实消费，不解冻通用 D3/D4，不改 `src/`、认证或发布面。

## 冻结包

- [`00_OWNER_AUTHORIZATION_20260816.md`](00_OWNER_AUTHORIZATION_20260816.md)：窄实验授权与非蕴含边界；
- [`00_OWNER_SIGNAL_AND_BOUNDARY.md`](00_OWNER_SIGNAL_AND_BOUNDARY.md)：允许面、冻结面与 research-only 面边界；
- [`01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md`](01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md)：唯一 canonical 三臂协议、soundness、局部效果、资源和判词；
- [`01_W0_UNARY_LOWERING_CANARY_PROTOCOL.md`](01_W0_UNARY_LOWERING_CANARY_PROTOCOL.md)：兼容导航，不拥有门槛；
- [`02_ENDPOINT_METRICS_PROTOCOL_V1.md`](02_ENDPOINT_METRICS_PROTOCOL_V1.md)：类型化空值、终点货币、残余 envelope、资源向量与 evaluator 灵敏度；
- [`02_ENDPOINT_METRICS_PROTOCOL_V1.json`](02_ENDPOINT_METRICS_PROTOCOL_V1.json)：终点来源、保护面、合成扰动与机器冻结口径；
- [`03_CANARY_MANIFEST.json`](03_CANARY_MANIFEST.json)：输入、源码、运行时、固定上下文、运行参数和预注册预测。

首次包含上述文件的 Git commit 是协议冻结身份。实现、运行收据和最终报告必须记录该 commit，且不得回改冻结判据。

## 当前非蕴含

本目录当前只含协议，不表示 lowering 已实现、checker 已通过、A/B 已运行或金丝雀已给出任何判词。
