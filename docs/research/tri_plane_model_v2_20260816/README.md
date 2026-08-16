# 三面防污染模型 v2 dossier

> **日期：** 2026-08-16  
> **性质：** 正式方法论 dossier  
> **主题：** 当研究定理开始被计算消费时，怎样审计 theorem、checker、lowering（降译，即把抽象 theorem 转成具体运行时约束）、consumer、measurement 与 certified promotion 之间的作用边。  
> **非授权边界：** 本目录的方法论文档不授予实验、production、certification 或 owner authority。具体活动仍由 owner 决定、实验协议和 certified sink 分别授权。

## 本目录是什么

v1 三面模型解决了一个根病：同一个“收紧”动作在数学面与发布面上符号相反，语言混面会把发布侧“保守安全”的直觉错误搬进求解证明面。研究侧开始产出机器验证 theorem 并准备 lowering 后，污染风险从节点措辞扩展到消费链：一条正确 theorem 仍可能被错误 consumer、错误 runtime literal、过宽 scope、路径级 lifting 或越权 capability 使用。

v2 在本 dossier 内保留数学面、发布面、档案面，增加与三面正交的 `RESEARCH / CERTIFIED` 运行域轴；审计单位从节点扩展到消费边。是否把这套术语升级为项目级现行表述，仍待 owner 裁决。核心口径是：

> 节点有身份，边有权限；角色给符号模板，消费边给最终裁断。

## 文件清单

| 文件 | 角色 |
|---|---|
| [`TRI_PLANE_MODEL_V2.md`](TRI_PLANE_MODEL_V2.md) | 主方法论文档。按 28 节（0 至 27）定义坐标系、角色、作用边、三轴裁断、receipt、消费合同、typed null、capability token、条件记录、三账流水、冷档案、promotion、闸成本与 W0 canary 实例。附录列出六条无需逐例推给 owner 的逻辑后果。 |
| [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) | owner 裁决请求。十三项项目级选择均按“问题、选项、推荐、代价”展开；第一条 W0 lowering canary 保留为【已裁】记录。 |
| [`OWNER_SIGNAL_20260816.md`](OWNER_SIGNAL_20260816.md) | owner 原话窄逐字存录。保存 2026-08-16 09:14 的完整原话、落地线会话→跨会话同步→本线的转达链、“右边”的准确解释、09:19 已履行的落地线战役汇报义务及本线窄效力边界。 |
| [`README.md`](README.md) | dossier 门牌、来源结构、文件索引与 v1 关系索引。 |
| [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) | GPT Pro 第一段盲问逐字存档。输入只有问题与仓内坐标，未见甲乙已有答案。 |
| [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) | 同一 GPT Pro conversation 的第二段对撞逐字存档。输入为甲乙六点升级提案、落地线 B 段知情对撞五件与自身盲答，输出三方裁断、自审修正、28 节（0 至 27）骨架和 owner 待裁清单。 |
| [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) | 落地线 B 段知情对撞席逐字存档。模型为 GPT Pro，非盲，conversation `6a812b53-f214-83ea-9c49-7085a0bf1cda`；头注登记浏览器 `innerText` 纯文本 payload 为 12,265 字、SHA-256 `3f1917e9fc88f0dfe9bc8aa1647f45be51c8b3c560718d89cc72db98fb8bc1cc`。 |
| [`audit/ADVERSARIAL_AUDIT_20260816.md`](audit/ADVERSARIAL_AUDIT_20260816.md) | 四席 Claude Opus 异源审计报告。内容保真、坐标结构、裁决请求和三处薄弱面共 62 条发现，是本轮修订依据。 |

## 来源结构

本方法论由五路输入会师，再由本线程对撞段合并。

- **甲：本仓三面审计线。** Claude Code 工作线，v1 作者，也是六点升级提案方。
- **乙：本仓落地线。** Claude Code 工作线，与甲收敛出角色符号、边界通道、常设闸过缓计价等落地件。
- **丙：本线程 A 段盲问席。** GPT Pro，盲，conversation `6a818168-53c8-83ea-b57b-a697d1ec557b`；在未见甲乙答案时独立提出作用边审计、可执行消费合同、能力集合、跨域重新铸造与 W0 canary 六步。
- **落地线 A 段盲席。** GPT Pro，盲，使用全新窗口，刻意不接仓、不带项目词汇；它与丙构成两条盲态设计来源。
- **落地线 B 段对撞席。** GPT Pro，非盲，conversation `6a812b53-f214-83ea-9c49-7085a0bf1cda`；从三轮数学评审后分支、承载完整项目语境，对落地线 A 段盲答与落地线草案作知情对撞裁断，产出 typed null、能力四层、条件事项记录、一库三账一流水、`TYPED_OPTION / UNTYPED_ARCHIVE` 五件。它的价值在知情对撞，不是第三条盲源。
- **合并：本线程 B 段对撞席。** GPT Pro，与丙同一 conversation；读取甲乙提案、落地线 B 段五件与自身盲答后完成合并裁断。相对丙是同线程自审，不另计为独立来源。

路径独立的稳健度来自两条工作线提案、两个盲态设计与一个知情对撞席的互补。丙与合并的 conversation 身份见 [`blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:1-4` 与 [`collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:1-16`；落地线 B 段席位性质和逐字正文见 [`b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:1-5`，本线程对五件的采纳改造见 [`collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:568-866`，最终骨架与 owner 清单见 `:962-1156`。

## v1 关系索引

v2 不撤销 v1 三面本体，也不重写 v1 文件。本批关系如下：

1. **符号判据：项目级 supersede 待裁。** 本 dossier 内采用“角色给模板、消费边给终判”；在 owner 对 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 1 项裁决前，[`FIRST_PRINCIPLES_DESIGN.md`](../rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md) `:633-641` 仍是项目现行表述。若 owner 选择 A，后续受控批才执行项目级取代与投影迁移。
2. **运行域轴：dossier 内新增。** `RESEARCH / CERTIFIED` 与三语义面正交；是否升级为项目级正式术语同属第 1 项待裁。
3. **审计单位：dossier 内扩展。** 节点身份继续审，新增 theorem→checker→lowering→consumer 的消费边审计，并显式暴露 lifting 的路径级开放题。
4. **继续有效。** [`FINDINGS.md`](../plane_mixing_audit_20260813/FINDINGS.md) 的混面审计与挂账继续有效；[`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) 的三极、双 ledger、UNKNOWN 不改账与求解面方法继续有效。
5. **后续投影。** v1 文件、方法论入口、生成页和文档分类的同步不在本 dossier 内完成，须待 owner 第 1 项裁决后走后续受控批次。

## 快速阅读路径

第一次阅读先看主文档第 0 至 10 节，建立“两轴坐标、节点与边、角色关系、三轴裁断、出生证与机器化节奏”；要看机器接口与状态体系，转第 11 至 20 节；要看跨认证边界，转第 21 至 22 节；要看治理成本与审计止步线，转第 23 至 24 节；要看 W0 具体实例、负 canary 与否决清单，转第 25 至 27 节。需要 owner 拍板时直接阅读 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md)，无需先掌握仓内批次坐标。

## 方法实战记录

2026-08-16，本方法第一次完整出生证查验完成于[实验三：W0 席位算术引理与固定矩形终局排除](../solver_reasoning_outer_loop_reviews_20260815/experiment_three_w0_slot_arithmetic_and_terminal_exclusion_20260816/README.md)：查验→发现义务簿记字面量缺陷→并案补丁→复验→出证，最终签发带 DEBT-B、DEBT-D1、DEBT-D2 三笔 `CONDITIONAL_DEBT` 的 `ISSUED_RESEARCH_ONLY` 出生证。

本节仅作方法实例回指；出生证状态、条件债及其触发器的权威历史记录在实验三侧 [`14_BIRTH_CERTIFICATE_AND_CONDITIONAL_DEBTS.md`](../solver_reasoning_outer_loop_reviews_20260815/experiment_three_w0_slot_arithmetic_and_terminal_exclusion_20260816/14_BIRTH_CERTIFICATE_AND_CONDITIONAL_DEBTS.md)。
