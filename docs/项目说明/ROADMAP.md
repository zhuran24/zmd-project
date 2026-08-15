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

- **目标：** 在本阶段完成旧文档职责收束，随后把稳定的 knowledge / document checks 接入正式 preflight 或 CI，并完成两项治理硬化：
  - **B9 gate 检查路径只读化：** 只读检查不得调用写穿生成逻辑。在案事故为外部代理运行 gate 后写穿五个 tracked 文件、随后恢复；范围清点必须包含已知非纯只读的 `scripts/production_readiness_gate.py`，其磁盘检查会创建 `.artifacts`。
  - **B10 测试快照数字纪律：** 严格区分「随合法数据漂移的快照数」与「身份声明型 pin」。既往漂移样本与修复数字只从[三面防污染架构审计](../research/plane_mixing_audit_20260813/FINDINGS.md)及其证据链追溯，不在路线图复制。fixture 化与随数据更新机制仅适用于前者；后者包括 `FROZEN_ARTIFACTS` 的 SHA 一类身份声明，继续由身份 pin 的硬编码与 mismatch 拒绝纪律管辖，“好心”更新 expected 属 Forbidden 方向。
- **前提：** 先让分类、生成页、迁移和兼容入口在普通文档测试中稳定。若整改范围触及 `scripts/preflight_gate.py`，即入 Chain C reseal，必须并入 Chain B/C 批纪律，届时三面线 A12① 顺走。
- **退出证据：** 新文档 fail-closed 分类、生成页新鲜度、历史不可改写、职责索引和知识事务在正式门中被一致执行；只读检查的全调用链经副作用测试证明不改 tracked 文件、不生成或改写工作区产物，且覆盖 `scripts/production_readiness_gate.py`；合法数据快照统一从机器 fixture 取值，身份声明型 pin 继续由 mismatch 拒绝语义钉死。
- **非目标：** 不为了目录整齐而移动或删除仍被证据链引用的历史材料；不把两类数字一刀切为同一种维护机制，不自动改写身份声明型 pin。
- **坐标：** [文档系统架构](../governance/document-system/ARCHITECTURE.md)、[维护指南](../governance/document-system/MAINTAINING.md)、[三面防污染架构审计](../research/plane_mixing_audit_20260813/FINDINGS.md)。

## 工作线 G：推理外环（求解器新构想；状态：未立项/概念收敛）

- **目标：** 若本线获得立项，以可复用的命题、上下文、独立 lowering 契约和失败反馈编译能力，逐步压缩反复支付的组合搜索，并让必要条件与充分构造双向生长。
- **前提：** 两道独立闸依次成立：① Phase -1 实验闸以无删失死因谱、单家族编译、holdout 对照和外部 witness canary 产出 go/no-go 证据；② owner 立项裁决消费该证据并留下显式记录。实验全绿不等于立项。与 rule_system_redesign 线不同，本线尚无 owner 立项裁决记录。
  - Phase -1 开跑前须先把实验协议 tracked 化，并在开跑前冻结 corpus 与抽样框、cap／seed／worker／timeout、`censorStatus`、三态触达分类 `NOT_REACHED`／`REACHED_NO_EFFECT`／`EFFECT_NO_TERMINAL` 以及 go/no-go 阈值。协议本身为 `non_authorizing`，只规定证据可采纳性，不产生立项或开跑授权；本路线图只登记该要求，不替未来编写协议。
- **退出证据：** Phase -1 四类实验材料形成可复验的 go/no-go 证据包，随后由 owner 留下明确的立项或不立项裁决；任何工程实现均不得替代第二道闸。
- **非目标：** 登记不等于立项；[设计约束](../research/solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_DESIGN_CONSTRAINTS.md) 保持 `non_authorizing`，不对现行树产生新增义务。
- **坐标：** [三轮外部评审归档](../research/solver_reasoning_outer_loop_reviews_20260815/README.md)、[推理外环设计约束登记](../research/solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_DESIGN_CONSTRAINTS.md)。

## 开放残余：落地时仪表盘 §9 迁移

A10–A14 的原始登记与已发生事件保存在 [HISTORY](HISTORY.md) 和 [落地时仪表盘归档](../history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/27_status_dashboard.md)；本节只保留仍需动作的残余。

### A10：记忆元数据与现势一致性

- **目标：** 建立门牌与正文语义现势一致性的机械体检；兼容 `title` 被 CC auto-memory 移入 `metadata` 的形态；用 `metadata.originSessionId` 对应会话的起讫时刻表达创建区间，转录已轮转时才回退到 `modified`。
- **前提：** 原始问题边界以落地时仪表盘归档的 A10 为准；形态兼容不得把 `modified` 再解释成首次到达时间。
- **退出证据：** 现势一致性、两种 `title` 形态和创建区间推导均有可重复的 checker、fixture 与 provenance 说明。
- **非目标：** 不恢复已移除的仓内记忆层，不把归档分层重新设为默认方案，也不从字段存在推出语义新鲜。

### A11：记忆系统后续批

- **目标：** 推进仍待 owner 拍板的迁移本体，并执行批⑤内容订正与批⑥判官层工作。
- **前提：** 原始任务边界、批序和勿动面以落地时仪表盘归档的 A11 为准；干跑或工具就绪不构成迁移授权。
- **退出证据：** 迁移本体取得显式 owner 决定；各后续批分别留下输入范围、冲突处置、机械验收和回退边界。
- **非目标：** 不把历史干跑结果写成已获准的生产迁移，不把不同记忆地层机械拼接成单一门牌。

### A12：三面防污染架构审计挂账

- **目标：** 为 obligations checker、strong-status allowlist checker 与 preflight 的 PASS 文案补齐“不证什么”的限界，按触发器「Chain B/C 批顺走」处理；完成 `EXACT_MASTER_FRONT_CLEAR_LIFT` 定理复证与 full-pool golden 门禁接线，按触发器「挂 redesign 批 5/6」处理。
- **前提：** 采用 [HISTORY 的 2026-08-13 节](HISTORY.md)、[`DECISION-RULE-SYSTEM-REDESIGN-OPEN-20260813`](../CATALOG.md#decision-rule-system-redesign-open-20260813)、[`DECISION-LEDGER-AUTHORITY-INTERFACES-20260813`](../CATALOG.md#decision-ledger-authority-interfaces-20260813)、[`DECISION-SEMANTICS-SPLIT-EXPERIMENT-FIRST-20260813`](../CATALOG.md#decision-semantics-split-experiment-first-20260813) 与落地时仪表盘归档作为出处；技术范围回到 [`plane_mixing_audit_20260813`](../research/plane_mixing_audit_20260813/FINDINGS.md)。
- **退出证据：** 三个门的成功输出都明确声明作用域与非蕴含边界；front-clear lift 由独立复证、full-pool golden 和门禁消费共同约束。
- **非目标：** 不从 checker PASS 推导 soundness、owner close 或 release closure，不在未触发对应批次时单开无宿主改动。

### A13：文档补丁链落地后残余

- **目标：** 完成 `CLAUDE.md` 两步调和的第二步（换轻量版、单独提交）；解决 historical+triage 补登记与“新建 tracked dossier 必须 active 且 closure=null”的 intake 语义冲突；在新的受控 landing 计划中把 00/27 successor 的历史引用改指落地时字节归档；自修补丁未覆盖的问题。
- **前提：** 以 [HISTORY 的 2026-08-15 节](HISTORY.md)、[`DECISION-LEDGER-AUTHORITY-INTERFACES-20260813`](../CATALOG.md#decision-ledger-authority-interfaces-20260813) 和落地归档为出处；当前 00/27 successor 是 finalized plan 的字节级成品，不能直接重写或绕开 `verify-migration --finalized`。
- **退出证据：** overlay 调和按确认后的 tracked/本机边界完成；intake 能区分历史补登记与新 dossier workflow；新 landing plan 封存并验证指向落地归档的 successor；其余缺口各有具名 checker 或显式关闭记录。
- **非目标：** 不放宽新 dossier 的 fail-closed workflow 规则，不手改生成页，不用旧快照替代真正退休时刻的落地归档。

### A14：求解面方法论载体与维护闭环

- **目标：** 修复 §0b 的版本头滞后、`277/279` 行六问残留、双向保真与派生闭包两公理未进入本体区、“绿灯≠关门”重复陈述、APX_E 原件未进入 tracked 真源；补齐出身故事绑定无维护、拒真防线不对称、缺少反向 reseal、外发包完备性无机器闸、口述定谳在途期无登记位。
- **前提：** 原始问题集以 [方法论地图](../research/methodology_compilation_20260814/METHODOLOGY_MAP.md) 和落地时仪表盘归档的 A14 为准；方法论 skill 继续只覆盖求解面，不接管发布或治理 authority；口述定谳登记位的设计有在案先例可参考——[`DECISION-OUTER-LOOP-REVIEW-REGISTRATION-20260815`](../CATALOG.md#decision-outer-loop-review-registration-20260815) 的窄记录形态（只登记动作本身、`does_not_imply` 明列不批内容/不立项/零现行义务）。
- **退出证据：** 判据本体有明确 canonical successor；公理、操作卡与维护触发器在单一真源闭合；APX_E 与外发包完备性进入可验证的 tracked 路径；反向 reseal 和口述定谳过渡状态有机器可见入口。
- **非目标：** 不把方法论 skill 扩成全项目默认手册，不把历史判例改写成现态，也不从方法论登记授予数学或发布 authority。

## 排序原则

1. authority 或语义前提变化先于依赖它的工程工作。
2. 能便宜关闭作用域的证明、反例和小实验先于大预算 campaign。
3. 生成、验证、owner promotion 和生产消费分别设置退出门，不把一条绿灯跨层外推。
4. 已完成事项从本页移出并追加到 HISTORY；仍开放的稳定命题由 OPEN_QUESTIONS 自动列出。
