# 实验二：W0 一元 lowering 金丝雀

> **当前状态：** `IMPLEMENTED_READY_FOR_FROZEN_RUN`
> **日期：** 2026-08-16
> **权限边界：** research-only；只验证一条已证 W0 Judgment 的静态 lowering 与真实消费，不解冻通用 D3/D4，不改 `src/`、认证或发布面。

## 冻结包

- [`00_OWNER_AUTHORIZATION_20260816.md`](00_OWNER_AUTHORIZATION_20260816.md)：窄实验授权与非蕴含边界；
- [`01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md`](01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md)：三臂、soundness、局部效果、资源和判词；
- [`02_ENDPOINT_METRICS_PROTOCOL_V1.md`](02_ENDPOINT_METRICS_PROTOCOL_V1.md)：类型化空值、终点货币、残余 envelope、资源向量与 evaluator 灵敏度；
- [`03_ENDPOINT_METRICS_PROTOCOL_V1.json`](03_ENDPOINT_METRICS_PROTOCOL_V1.json)：当前 endpoint source hashes、protected surfaces 与合成扰动向量。

首次包含上述文件的 Git commit `0339c745b6c7f498fc989398de380a78578fc785` 是协议冻结身份。实现、运行收据和最终报告必须记录该 commit，且不得回改冻结判据。

## 实现包

- [`05_LOWERING_CONTRACT_V1.json`](05_LOWERING_CONTRACT_V1.json)：W0 target 与 unary lowering 等值合同；
- [`06_check_endpoint_metrics.py`](06_check_endpoint_metrics.py)：endpoint evaluator 纯标准库合成灵敏度检查；
- [`07_check_lowering_contract.py`](07_check_lowering_contract.py)：CpModel snapshot 纯标准库独立差分检查；
- [`08_CANARY_MANIFEST.json`](08_CANARY_MANIFEST.json)：输入、代码、W0、运行参数与旧前缀身份；
- [`09_w0_unary_lowering_canary.py`](09_w0_unary_lowering_canary.py)：单臂 research harness；
- [`10_launch_w0_unary_lowering_canary.py`](10_launch_w0_unary_lowering_canary.py)：三臂发射、聚合和 evidence manifest；
- [`11_IMPLEMENTATION_SELF_RECEIPT.md`](11_IMPLEMENTATION_SELF_RECEIPT.md)：边界、proto、灵敏度与开发跑自检。

## 当前非蕴含

lowering 与测量器官已实现并通过开发自检，但正式 1007-event 三臂尚未运行，金丝雀还没有最终判词。
