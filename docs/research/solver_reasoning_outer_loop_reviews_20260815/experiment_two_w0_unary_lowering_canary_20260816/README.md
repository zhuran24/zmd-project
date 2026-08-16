# 实验二：W0 一元 lowering 金丝雀

> **当前状态：** `COMPLETE_INCONCLUSIVE`
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

## 运行与终判

- [`12_check_canary_run.py`](12_check_canary_run.py)：纯标准库 post-run 独立复算；
- [`13_RUN_RECEIPT.json`](13_RUN_RECEIPT.json)：从 36 份 local-optional evidence 文件重算的 compact receipt；
- [`14_FINAL_REPORT.md`](14_FINAL_REPORT.md)：四格账、热点迁移和决策边界。

冻结三臂已经完成，run `EXIT_CODE=0 / .DONE`，独立 checker 为 `PASS`，科学判词为 `INCONCLUSIVE`：A/B 完全复现 1007 个 `Active_041` 循环且 observer 不扰动；一元 lowering 的 reject set 与 theorem trigger 精确等值；C 在第一次 binding solve 的 20 秒 cap 内没有 proposal 或终态，因此 `J-trigger=0` 不能升级成真实 family 消费成功。

## 当前非蕴含

本结果不解冻通用 D3/D4，不证明跨布局家族性、endpoint compute gain、上下界进展、production promotion、认证或发布面变化。
