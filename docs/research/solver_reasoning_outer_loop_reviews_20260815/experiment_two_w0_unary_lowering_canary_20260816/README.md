# 实验二：W0 一元 lowering 金丝雀

> **当前状态：** `PROTOCOL_FROZEN_PENDING_IMPLEMENTATION`
> **日期：** 2026-08-16
> **权限边界：** research-only；只验证一条已证 W0 Judgment 的静态 lowering 与真实消费，不解冻通用 D3/D4，不改 `src/`、认证或发布面。

## 冻结包

- [`00_OWNER_AUTHORIZATION_20260816.md`](00_OWNER_AUTHORIZATION_20260816.md)：窄实验授权与非蕴含边界；
- [`01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md`](01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md)：三臂、soundness、局部效果、资源和判词；
- [`02_ENDPOINT_METRICS_PROTOCOL_V1.md`](02_ENDPOINT_METRICS_PROTOCOL_V1.md)：类型化空值、终点货币、残余 envelope、资源向量与 evaluator 灵敏度；
- [`03_ENDPOINT_METRICS_PROTOCOL_V1.json`](03_ENDPOINT_METRICS_PROTOCOL_V1.json)：当前 endpoint source hashes、protected surfaces 与合成扰动向量。

首次包含上述文件的 Git commit 是协议冻结身份。实现、运行收据和最终报告必须记录该 commit，且不得回改冻结判据。

## 当前非蕴含

本目录当前只含协议，不表示 lowering 已实现、checker 已通过、三臂已运行或金丝雀已给出任何判词。
