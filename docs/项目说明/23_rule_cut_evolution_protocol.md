# 23｜规则与 cut 演化协议

本协议规定规则语义、cut family 和生产消费链怎样安全演化。它只描述稳定维护合同，不记录某一批次的 commit、测试收据、哈希、family 数量或 preflight 结果。

## 分层对象

一次规则或 cut 变更至少要区分：

1. **规则语义**：命题、信息层级、owner、前提与失效条件。
2. **表示**：schema、proof、snapshot、plan、wire bytes 与版本。
3. **发现与生成**：候选如何产生，是否只在 offline、shadow 或 production 中运行。
4. **验证**：validator、独立 interpreter、exact checker 分别证明什么。
5. **消费**：projection、lowering、master apply、replay 和 lifecycle 是否真正接线。
6. **权威**：测试、研究 claim、production admission、owner 决定和 certification 各自的效力。

这些层不能因名称相同而合并。一个 family 拥有 validator，不等于它拥有 production generator、lowering 或 exact checker。

## 变更包

新增或改变 family 时，应在同一变更中提供与作用域相称的材料：

- 语义与完整前件；
- schema 和版本策略；
- proof 到 snapshot / literal 的绑定；
- 独立验证或明确的 unavailable 状态；
- malformed、scope drift、错误强化和 replay 负路径；
- generation、lowering、apply 与 lifecycle 的真实接线说明；
- 受影响 claim、decision、规范、telemetry 和迁移；
- rollback、supersession 或 retirement 路径。

缺失能力必须显式写成 unavailable 或 deferred。不能用 shadow 规格、测试 helper 或遥测字段合成不存在的 production 能力。

## 独立性与 fail closed

Generator、family verifier、exact checker 和 consumer 应保持可审计的信任分离。验证异常、未知版本、前提不全、snapshot 漂移、非法强化或消费链矛盾必须阻断该 cut 的可信使用。

Rejection、telemetry 和 audit sidecar 可以解释失败，但不能自行生成、晋级、replay、compile 或 apply cut。它们也不能改变 family owner、stage、capability 或 publication authority。

## Shadow 与 production

Test/offline shadow 规格的职责是静态核验当前实现或探索迁移方案。它不得被 production runtime 隐式导入，也不得因为测试通过而改变 registry、Benders dispatch、replay、lifecycle、lowering、trusted apply、wire schema 或 owner gate。

从 shadow 进入 production 时必须建立独立的 owner-authorized 变更包，并重新满足该 family 的证明、版本、接线和发布门槛。

## Retirement 与换代

family 或规则被反例、语义修正或实现失效影响时，通过稳定 claim、validity profile、new decision 和显式 successor 保留方向性。退役内容不能在同一 ID 下悄悄恢复；重新启用必须说明新的前提、验证范围和 production admission。

## 查询与验收

- 当前状态与 owner / gate 投影：[`../CURRENT.md`](../CURRENT.md)
- 推理、分离与有效性账本：[`../REASONING_LEDGER.md`](../REASONING_LEDGER.md)、[`../VALIDITY_LEDGER.md`](../VALIDITY_LEDGER.md)
- 项目说明入口与规范术语：[`README.md`](README.md)、[`../TERMINOLOGY.md`](../TERMINOLOGY.md)
- 稳定方法边界：[`REASONING_METHOD.md`](REASONING_METHOD.md)
- 规范与实现入口：[`../../specs/README.md`](../../specs/README.md)、[`../../NAV_MAP.md`](../../NAV_MAP.md)

验收记录应留在对应任务、dossier 或机器日志中。本协议只接受能够被持续检查的稳定规则。

历史批次版本保存在 [`../history/convergence/23_rule_cut_evolution_protocol_pre_phase3_batch4_20260812.md`](../history/convergence/23_rule_cut_evolution_protocol_pre_phase3_batch4_20260812.md)。
