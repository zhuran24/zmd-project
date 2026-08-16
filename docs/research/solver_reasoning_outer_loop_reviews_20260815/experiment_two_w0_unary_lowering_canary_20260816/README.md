# 实验二：W0 一元 lowering 金丝雀

> **当前状态：** `COMPLETE_INCONCLUSIVE`。协议、发射前增补、research-only 实现、三臂运行、独立重聚合与 post-run checker 均已完成；冻结科学判词为 `INCONCLUSIVE`。
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

首次包含上述文件的 Git commit 是协议冻结身份。实现和运行没有回改冻结判据；删失与 `NO_EFFECT` 的类型化修复通过后继提交完成并保留原 arm receipt。

## 实现与收口

- [`03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md`](03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md)：八字段收据、控制面／数据面阻断消歧、research redline 与 S0–S5 非等价；
- [`04_W0_UNARY_LOWERING_SPEC.json`](04_W0_UNARY_LOWERING_SPEC.json)：唯一 W0 lowering 规格；
- [`06_check_w0_unary_lowering_contract.py`](06_check_w0_unary_lowering_contract.py)：theorem currency、proto delta、truth table 与 4 个 mutation canary；
- [`08_check_endpoint_metrics_sensitivity.py`](08_check_endpoint_metrics_sensitivity.py)：11 个 endpoint evaluator 控制；
- [`09_run_w0_unary_lowering_arm.py`](09_run_w0_unary_lowering_arm.py)、[`10_aggregate_w0_unary_lowering_canary.py`](10_aggregate_w0_unary_lowering_canary.py)、[`11_run_w0_unary_lowering_canary_suite.py`](11_run_w0_unary_lowering_canary_suite.py)：三臂运行、重聚合与 detached suite；
- [`12_check_gpt56pro_canary_lineage.py`](12_check_gpt56pro_canary_lineage.py)：纯标准库 post-run 独立复算；
- [`13_GPT56PRO_RUN_RECEIPT.json`](13_GPT56PRO_RUN_RECEIPT.json)：tracked compact receipt；
- [`14_GPT56PRO_FINAL_REPORT.md`](14_GPT56PRO_FINAL_REPORT.md)：完整判词、四格账、装置史与决策边界。

## 冻结结果

- A/B 各完成 1007 个事件，ordered selection sequence 完全一致；observer 墙钟相对 baseline 为 `-0.152%`；
- lowering 合同和 11 项 endpoint 灵敏度全部 PASS；
- C 在 S2 将 target 有效域 `3→1`、活动值 `2→0`；
- C 首次 binding solve 在 20 秒内返回 `UNKNOWN/CENSORED`，没有 proposal，故运行时 family collapse 与 compute gain 均未观测；
- exact 上下界与 public/certified surfaces 保持 `ZERO_BY_SCOPE`／身份不变。

因此，编译域效果成立，但第二层真实消费的终态门没有闭合。`INCONCLUSIVE` 不购买下一条 theorem lowering、通用 D3/D4、跨布局 holdout、production default 或 certified-exact 进展。
