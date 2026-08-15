# ZMD 未来路线图

> 本页只管理未来工作、顺序依赖与退出证据。它不陈述“现在已经做到哪一步”，不复制 gate、hash、上下界、实验计数或 owner 决定值。当前事实看 [CURRENT](../CURRENT.md)，开放命题看 [OPEN_QUESTIONS](../OPEN_QUESTIONS.md)，已完成事件追加到 [HISTORY](HISTORY.md)。

## 维护规则

一次路线图更新只能改变未来结构：新增工作线、调整依赖、补充退出证据或显式退役方向。完成状态、研究结论与 owner 裁决分别写入 machine source、claim ledger 与 decision ledger，再由生成页投影。

每条工作线都用四个字段表达：目标、前提、退出证据、非目标。没有退出证据的“做完”不得关项。

## 工作线 A：whole-layout 认证级存在性与 lower side

- **目标：** 对现行六谓词语义建立可发布的 whole-layout existence / witness 证据，并把 lower side 从开放状态推进到可复验结论。
- **前提：** canonical rules、命题 scope 与 terminal validator 保持显式一致。
- **退出证据：** 满足 `PROJECT_LOCK.md` 的 proof-bearing terminal artifact，或形成新的 scoped claim 明确关闭更小问题。
- **非目标：** research witness、局部 antecedent 或 solver FEASIBLE 不自动等于 production `CERTIFIED`。
- **坐标：** [`CLAIM-CERTIFIED-EXISTENCE-OPEN`](../OPEN_QUESTIONS.md#claim-certified-existence-open)、[witness / lower-bound topic](../TOPIC_INDEX.md)。

## 工作线 B：cut framework 的 production promotion

- **目标：** 把已登记的 typed / shadow / diagnostic family 按作用域完成 soundness、消费、遥测、rollback 与 owner promotion 闭环。
- **前提：** 候选发现、选择、有效性验证和 solver consumption 分开记账；实验未激活不能替代正式 soundness。
- **退出证据：** 对应 family 的 scoped proof、独立 verifier、生产宿主证据与明确 owner decision。
- **非目标：** 工程接线、shadow run、单个 candidate valid 或某次速度改善都不单独授权 attach。
- **坐标：** [cut-framework topic](../TOPIC_INDEX.md)、[REASONING_LEDGER](../REASONING_LEDGER.md)、[当前 owner decisions](../CATALOG.md)。

## 工作线 C：P2.0 吞吐与 `min_side` 闭环

- **目标：** 在独立 P2.0 语义账本中继续收紧 throughput / route / area 边界，并解决 `min_side` 上界开放项。
- **前提：** 条件式上界必须保留前提，route-state、flow 和 area 量纲不能混同。
- **退出证据：** 新的 formally scoped claim、独立复算或反例，连同 `does_not_imply` 边界。
- **非目标：** P2.0 结果不回写 P1.2 certified theorem scope，除非另有明确 authority 变化。
- **坐标：** [`CLAIM-P2-MIN-SIDE-UPPER-OPEN`](../OPEN_QUESTIONS.md#claim-p2-min-side-upper-open)、[P2 topic](../TOPIC_INDEX.md)。

## 工作线 D：领域分离与通用传播边界

- **目标：** 系统描述哪些候选依靠领域结构被发现和验证，并判断能否对指定通用 CP-SAT 传播建立正式不完备性命题。
- **前提：** “没激活”“预算耗尽”“没搜索到”与“形式上不可能分离”严格区分。
- **退出证据：** 有明确传播系统、实例族、量词与证明的 formal claim，或可重放的反例关闭过强猜想。
- **非目标：** 领域 separator 的存在不自动证明所有通用传播都不完备。
- **坐标：** [`CLAIM-GENERIC-CP-SAT-SEPARATION-IMPOSSIBILITY-OPEN`](../OPEN_QUESTIONS.md#claim-generic-cp-sat-separation-impossibility-open)、[separation profiles](../REASONING_LEDGER.md)。

## 工作线 E：proof logging 与独立复验

- **目标：** 为关键 infeasibility、bound 与 terminal verdict 建立可携带、可独立 replay 的证明日志或 sidecar。
- **前提：** proof format、checker TCB、输入 hash 与 scope 都能冻结和重建。
- **退出证据：** 独立 checker 在干净环境复验，并由 scoped claim 说明它证明和不证明什么。
- **非目标：** checker 能读某格式，不等于 production pipeline 已消费该证明。
- **坐标：** [formal-verification topic](../TOPIC_INDEX.md)。

## 工作线 F：文档治理硬化

- **目标：** 在本阶段完成旧文档职责收束，随后把稳定的 knowledge / document checks 接入正式 preflight 或 CI。
- **前提：** 先让分类、生成页、迁移和兼容入口在普通文档测试中稳定。
- **退出证据：** 新文档 fail-closed 分类、生成页新鲜度、历史不可改写、职责索引和知识事务在正式门中被一致执行。
- **非目标：** 不为了目录整齐而移动或删除仍被证据链引用的历史材料。
- **坐标：** [文档系统架构](../governance/document-system/ARCHITECTURE.md)、[维护指南](../governance/document-system/MAINTAINING.md)。

## 排序原则

1. authority 或语义前提变化先于依赖它的工程工作。
2. 能便宜关闭作用域的证明、反例和小实验先于大预算 campaign。
3. 生成、验证、owner promotion 和生产消费分别设置退出门，不把一条绿灯跨层外推。
4. 已完成事项从本页移出并追加到 HISTORY；仍开放的稳定命题由 OPEN_QUESTIONS 自动列出。
