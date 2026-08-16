# W0 一元 lowering 金丝雀协议 v1.1：发射前增补

> **状态：** `FROZEN_ON_FIRST_COMMIT / PRE_RUN`。本文件首次进入 Git 的提交是发射前修订身份；它只增补已冻结 v1，不回写或重判 v1 历史文本。
> **前代：** [`01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md`](01_W0_UNARY_LOWERING_CANARY_PROTOCOL_V1.md) 与 [`02_ENDPOINT_METRICS_PROTOCOL_V1.md`](02_ENDPOINT_METRICS_PROTOCOL_V1.md)。
> **适用顺序：** v1 与本增补冲突时，本增补只在下列新增字段、控制面语义和面边界上优先；其余门槛、三臂、预算和判词仍由 v1 冻结。

## 1. 收据八字段超集

所有 contract、sensitivity、arm、aggregate 和 final-verdict 收据必须在顶层同时包含：

```text
result_kind
outcome
subject_identity
verified_scope
authority_basis
granted_effects
non_implications
contract_identity
```

含义：

- `result_kind`：收据种类，不携带 PASS 权限；
- `outcome`：该种类允许的判词；
- `subject_identity`：实际被检查、运行或汇总的对象身份；
- `verified_scope`：本次确实核验到哪里；
- `authority_basis`：为何允许作出该范围内的判词；
- `granted_effects`：该判词真正授予哪些后续使用能力；
- `non_implications`：明确不授予什么；
- `contract_identity`：协议冻结提交、发射前修订提交、manifest、schema 与承重文件身份。

`verified_scope` 与 `granted_effects` 必须分离。核验范围再宽，也不能自动获得未被授权的效果；反之，授权文本也不能替代实际核验。

机器 schema：[`03B_RECEIPT_ENVELOPE_SCHEMA_V1.json`](03B_RECEIPT_ENVELOPE_SCHEMA_V1.json)。任一字段缺失或类型不符，收据不可采纳。

## 2. `BLOCKED` 双语义

本实验只允许以下两个不同平面的阻断词：

- `EXPIRED_BLOCKED`：控制面状态。授权、contract currency 或迁移窗口失效时，只阻断能力迁移、promotion 和新 treatment；不把数学对象判为不可行，也不停掉已经明确获准的 baseline research。
- `NO_EFFECT`：数据面结果。干预在已验证范围内未产生预注册局部差分；数学可行域保持原语义，不得将其改写为 `INFEASIBLE`、`EXCLUDED` 或控制面失效。

两者不得混写为裸 `BLOCKED`。控制面超时不产生数据面证据；数据面无效也不自动撤销此前的研究授权。

## 3. 研究面第七红线

lowering 入口、S0–S5 快照、资源计量、launcher 和收据必须全部位于本 research dossier。`src/models/*`、其他 `src/` certified source、supervisor、publisher、canonical 或发布表面保持零字节改动。

若实现便利性要求修改 tracked `src/`，这是 `BOUNDARY_EVENT`：立即停止，不得把“default-off”“只加埋点”或“研究用途”当作越界豁免；收尾必须报告文件、原因和拟议动作，等待另行审查。等待期间控制面状态为 `EXPIRED_BLOCKED`，但已经获准的 baseline research 不因该状态自动失效。

S0–S5 的 research-harness 计量不等于规则系统八件裁定表第 7 件所指的“被测生产代码埋点”；本实验不解锁、不代行、也不关闭该项。

## 4. 最小决策性接线判据

本实验引用并受以下完整判据约束：

> 只有当接线是回答一个已冻结、会改变下一步决策的反事实问题所必需的最小可逆干预时，它才是实验；若接线完成本身就是成功，或者所有可能结果都导向继续同一路线，它就是价值表演。

因此，“模块已导入”“约束已添加”“路径已到达”都不构成成功；必须由冻结的 proto contract、三臂差分、资源账和不同 outcome 对应的不同后续动作共同给出判词。

## 5. 授权语义补精确

2026-08-16 owner 信号授权的是：实验闸内、研究面沙盒中的一次静态 W0 lowering on/off 测量。它不是推理外环整线立项，不解冻通用 D3/D4 编译或 holdout，不触认证面，不允许 production default 或 public certified effect。

## 6. 执行顺序增补

在任何真臂前，必须依次完成：

1. 本增补与八字段 schema 进入独立发射前修订提交；
2. lowering contract checker PASS；
3. Endpoint Metrics Protocol v1 的 11 个扰动、正控、负控与 stale 控制全部 PASS，并生成八字段收据；
4. 才允许发射 A/B/C 真臂。

批尾必须把本次 local-optional `.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816/` 根登记进 dossier inventory；不得复制实验一曾出现的未登记活树盲区。
