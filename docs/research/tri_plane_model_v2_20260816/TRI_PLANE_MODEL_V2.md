# 三面防污染模型 v2：研究工件的作用边审计方法

> **日期：** 2026-08-16  
> **性质：** 正式方法论文档  
> **适用对象：** 研究定理、独立 checker、lowering（降译，即把抽象 theorem 转成具体运行时约束）、实验测量、消费准入、跨域晋级与研究资产维护  
> **效力边界：** 本方法定义研究工件的验证、消费、晋级与维护纪律，本身不授予任何实验、生产或认证权限。任何具体执行、production 使用、certified 效力或 owner authority 仍须由各自权威入口单独授予。

## 0. 文档身份与效力

> 本方法定义 research artifact 的验证、消费、晋级与维护纪律，本身不授予实验、生产或认证权限。

### 0.1 来源结构

本方法由五路输入会师，再由本线程对撞段合并。五路中，甲乙是两条 Claude Code 工作线的收敛提案，丙与落地线 A 段是两个彼此独立的盲席，落地线 B 段则是承载完整项目语境的知情对撞席。稳健度来自“工作线提案、两个盲态设计、一个知情对撞裁断”之间的互补，不意味着每一步都由独立作者完成。

- **甲：本仓三面审计线。** 它是 v1 作者与六点升级提案方，提供三面本体、混面病例、出生证查验、面身份收据、边界事件通道与过缓计价等问题意识。
- **乙：本仓落地线。** 它与甲收敛出角色符号、研究边界通道、常设闸吞吐成本和最小消费合同等落地要求。
- **丙：本线程 A 段盲问席，GPT Pro，盲。** conversation `6a818168-53c8-83ea-b57b-a697d1ec557b` 的第一段在未见甲乙答案时，从现有 W0 定理、消费三闸、`rules/derived/` 与认证链边界独立推出“节点有身份，边有权限”，并把审计单位从节点扩到 theorem、checker、lowering、consumer 之间的作用边。
- **落地线 A 段盲席，GPT Pro，盲。** 该席使用全新窗口，刻意不接仓、不带项目词汇，从通用研究方法问题独立设计；它与丙构成两条盲态来源。
- **落地线 B 段对撞席，GPT Pro，非盲。** conversation `6a812b53-f214-83ea-9c49-7085a0bf1cda` 的线程“分支 · 项目分析与架构问题”从三轮数学评审后分支，承载完整项目语境，对落地线 A 段盲答与落地线草案作知情对撞裁断。typed null、能力四层、条件事项记录、一库三账一流水、`TYPED_OPTION` 与 `UNTYPED_ARCHIVE` 五件出自此席；它的价值正是知情对撞，不得标成盲源。
- **合并：本线程 B 段对撞席，GPT Pro，同线程自审。** 同一 conversation `6a818168-53c8-83ea-b57b-a697d1ec557b` 的第二段读取甲乙六点提案、落地线 B 段五件和自身盲答，完成三方裁断。它相对甲乙与落地线材料提供新的合并视角，相对丙则是同线程自审，不另计为独立来源。

本文以本线程对撞段为合并底本；本线程盲答用于对撞段未重复展开的作用边分类、集合关系推导、SHADOW/RESEARCH_ACTIVE 两阶段、W0 六步实例和完整拒绝理由，逐节以“在案证据”标注为准。

丙与合并的同一 conversation 身份见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:1-4` 与 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:1-16`。落地线 B 段知情对撞席的逐字底本见 [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:1-5`，其头注登记纯文本 payload 为 12,265 字、SHA-256 `3f1917e9fc88f0dfe9bc8aa1647f45be51c8b3c560718d89cc72db98fb8bc1cc`。本线程对 B1 至 B5 的采纳与改造见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:568-866`，最终骨架与逻辑后果见同文件 `:962-1156`。

### 0.2 与 v1 的关系

v2 在本 dossier 内提出相对 v1 的三处结构修订，不撤销 v1 已经站住的本体与审计结论；是否把这些修订升级为项目级现行表述，仍待 owner 第 1 项裁决。

1. **符号判据升级。** v1 以“收紧在不同面上的符号”判面；v2 改为“角色给模板、消费边给终判”。角色判据仍有用，但只是完整边判据的有损投影。
2. **增加正交运行域轴。** 数学面、发布面、档案面仍是三种语义面；`RESEARCH` 与 `CERTIFIED` 是与三面正交的运行域。研究获得一等运行、权限、维护与资源席位，但不升为第四个语义面。
3. **审计单位扩展。** v1 主要审节点与措辞；v2 同时审消费边，尤其审抽象触发条件怎样绑定到运行时 literal、哪个 consumer 在什么 context 中产生了什么 effect。

在 owner 对 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 1 项作出项目级裁决前，v1 的 [`FIRST_PRINCIPLES_DESIGN.md`](../rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md) `:633-641` 仍是项目现行表述；本 dossier 内采用“角色给模板、消费边给终判”。若 owner 选择第 1 项 A，v2 才在后续受控投影批中取代该段项目级符号判据表述。无论该项如何裁定，三面本体、[`FINDINGS.md`](../plane_mixing_audit_20260813/FINDINGS.md) 的混面审计结论与 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) 的求解面方法论继续有效。v1 文件本批不改。

## 1. 问题：定理开始改变计算以后，污染住在边上

> 当研究工件从“被阅读”变成“被执行”时，主要风险从文书分类转移到 theorem、checker、lowering、consumer 与 authority 之间的作用边。

**lowering（降译）**是把抽象定理转换成具体运行时约束、变量域收缩、过滤器或停止规则的动作。研究定理只被阅读时，主要风险是陈述范围、证据等级或引用权威写错；定理一旦通过 lowering 改变搜索域，错误会直接表现为某些候选从系统里消失，而且可能没有任何终端报警。

现有消费三闸主要检查文书前提集：它能阻止 `UNREVIEWED` 条目、generated view 或低权威参数成为承重前提，却不直接看见某个研究模块在 CP-SAT 模型里加了什么约束。W0 标本也显示出同一接缝：Judgment 已经写明 `evidence_only`、`no_lowering` 与 `no_certification_effect`，而独立 checker 的顶层输出仍是 `status: PASS`。这在离线证明职责内没有错误，但任何只读取裸 PASS 的 consumer 都可能把“定理成立”静默改写成“允许改变模型”。

所以 v2 的问题不是再给文档多加一层标签，而是把以下链条逐边建模：

```text
theorem → checker → lowering → concrete effect → solver result → claim / authority
```

**在案证据：** 消费三闸的消费定义与人工执行边界见 [`CONSUMPTION_GATES.md`](../rule_system_redesign_20260807/batch0_20260815/CONSUMPTION_GATES.md) `:7-16,95-106`；W0 Judgment 的非蕴含边界见 [`01_JUDGMENT.json`](../solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/01_JUDGMENT.json) `:2-12`，checker 顶层 PASS/FAIL 见 [`03_check_w0_ghost_front_certificate.py`](../solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/03_check_w0_ghost_front_certificate.py) `:642-708`；盲答对该接缝的独立诊断见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:36-160`。

## 2. 坐标系：三语义面与运行域正交

> 数学面、发布面、档案面保持不变，研究／认证等运行域作为第二根轴，不新增第四个语义面。

三语义面分别回答三种不同问题：

- **数学面：** 命题是否成立，模型是否过松或过严，lowering 是否保持证明范围。
- **发布面：** 某个结果、能力或状态是否获准进入更强的承认、生产或认证通道。
- **档案面：** 发生过什么，谁在何时给过什么信号，旧读法如何被替代。

`RESEARCH` 与 `CERTIFIED` 则回答对象在哪个运行辖区内活动。一个 research theorem 属于“数学面 × RESEARCH”；一份 research receipt 属于“档案面 × RESEARCH”，同时具有 `checker receipt` 工件角色；一个 research admission gate 属于“发布面 × RESEARCH”；一个 certified theorem lowering 属于“数学面 × CERTIFIED”；owner promotion record 属于“发布面 × CERTIFIED”。认证 sink 的重放与重新铸造是发布面在 `CERTIFIED` 运行域中的执行动作，不把整个 `CERTIFIED` 域简化成发布事务面。

研究内部同时存在定理、测量、checker、lowering、准入门和档案，它们没有统一的“收紧符号”。若把研究升为第四个对等语义面，研究面内部会立即重演原病：对 theorem 的收窄可能安全但退化，对 lowering 的偏严可能杀解，对准入门的收紧可能只是阻止越权。研究需要一等治理席位，但这个席位应当由运行域、能力与维护轴表达。

**在案证据：** v1 三面符号判据见 [`FIRST_PRINCIPLES_DESIGN.md`](../rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md) `:633-641`；对撞段对“第四面”的正面裁断与面×域例子见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:6-16,125-198`；现行架构草图本身声明 `research_only / non_authorizing` 且不触碰认证表面，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:4-8`。

## 3. 审计单位：节点有身份，边有权限

> 工件节点登记它是什么，消费边登记谁以什么作用、在什么 context 中使用它。

**消费边**是从一个来源工件指向一个具体 consumer 的有向关系。它至少包含来源身份、consumer、运行位置、context、effect 和目标结论。节点上的 `research_only`、`ACTIVE` 或 `PASS` 只能说明节点自身状态，不能自动创建一条获准的消费边。

例如，同一个 W0 theorem 可以被三种 consumer 使用：文书把它当局部证明背景，binding 模型把它降译成一元约束，认证发布器把它解释成 certified 上界依据。三个动作读取同一个节点，但它们的正确性关系、所需信息与权限完全不同。v2 因而采用“节点有身份，边有权限”：节点登记 theorem、receipt、measurement 或 archive 的身份，边登记“谁可以怎样用”。

消费位置也是边身份的一部分。binding 阶段能看见 `active_output_slot`，master 阶段可能只看见 pose selection；把同一个 theorem 前移到信息不足的位置，会把精确触发器偷换成更强条件。文件没有改名，风险却已经换型，所以换 consumer 或换 stage 必须换证。

**在案证据：** 盲答的作用边模型见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:162-210`；现行 cut 演化协议已把语义、验证、消费和权威分开，见 [`23_rule_cut_evolution_protocol.md`](../../项目说明/23_rule_cut_evolution_protocol.md) `:5-16`；开放欠账台账对不同 call site 分行、按各自作用域阻断的先例见 [`OPEN_DEBT_LEDGER.md`](../rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md) `:10-16,35-92`。

## 4. 工件角色分类

> theorem、checker receipt、lowering、measurement、gate、archive 与 publisher 各有不同的正确性关系和默认能力。

角色决定一件工件首先应当满足什么关系，但不单独决定最终裁断。

| 角色 | 首要问题 | 默认能力 |
|---|---|---|
| `theorem` | 命题是否由前提推出，scope 是否准确 | 不改变模型，不授予 authority |
| `checker receipt` | checker 对哪个 subject、哪些字节、什么范围给了什么 outcome | 仅报告验证结果，`granted_effects` 默认空 |
| `lowering` | 抽象命题是否被正确绑定到 runtime literal 和具体 effect | 未经消费合同不得生效 |
| `measurement` | 观测是否真实、完整、未删失，sensor 是否有效 | 只增加证据，不自铸 permission |
| `gate` | 哪一种能力迁移或发布动作是否被允许 | 只阻断自己声明的 transition |
| `archive` | 历史工件是否可恢复、其原 context 与非蕴含边界是否完整 | 不承担当前 currency、consumer 兼容或 authority |
| `publisher` | 是否从获准、当前、可重放的 sink 状态发布 | 只能消费认证侧重验后的 authority |

角色表的用途是给审计一个起点。例如 receipt 自己不能把 `authority = machine` 写成事实，archive 不能被直接当当前前提，measurement 的零不能自动解释为作用域必零。但最终仍要看它通过哪条边被谁消费。

**在案证据：** 推理外环六器官对观察、验证、编译和测量的职责拆分见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:23-36`；知识治理已将 `representation_class`、`authority` 与 `authority_basis` 分开，且禁止登记册自铸 authority，见 [`ADR/017`](../../governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md) `:8-18`。

## 5. 作用边分类

> 验证边、引用边、执行边、测量边和晋级边不得因连接同一个工件而合并。

五种边分别回答不同问题：

1. **验证边：** checker 是否复算了特定 theorem 或 artifact。输出是验证 outcome，不是执行许可。
2. **引用边：** 某份文书或更高层 theorem 是否可把来源工件放入前提集。它受 scope、authority 与 currency 约束。
3. **执行边：** lowering 是否可以在某个 consumer 里改变变量域、添加约束、过滤候选或影响停止条件。
4. **测量边：** observer 是否真实看到 consumer 到达、effect 发生和资源变化。测量不反向证明 theorem sound。
5. **晋级边：** research effect 是否获得 production 或 certified 能力。它需要显式 owner / sink，不由长期使用或 PASS 累积产生。

同一 theorem 的验证边通过，不推出执行边通过；执行边产生性能收益，不推出晋级边通过；晋级边获准，也不能把错误 theorem 变真。五种边必须各自留证。

五类边的合规是逐边谓词，不蕴含一条多边路径整体合规。局部判词被搬到更宽对象空间的 lifting（判词提升），或一条 pruning 边的结果再被另一条 ledger-update 边消费，可能复合出没有任何单边持有的作用。是否把 lifting 建成第六类边，或采用路径级 grant 闭包检查，属于 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 13 项待裁；在裁决前，任何首次跨对象空间提升都必须显式上桌，不得从五类局部边的绿灯推出路径绿灯。

**在案证据：** 规则与 cut 演化协议明确区分验证、消费与权威，见 [`23_rule_cut_evolution_protocol.md`](../../项目说明/23_rule_cut_evolution_protocol.md) `:7-16`；W0 包明确“独立 checker PASS”与“真实系统消费、lowering 全部未测试”同时成立，见 [`experiment_one README`](../solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/README.md) `:3-22,75-76`；本仓 F5 adapter 已把可提升与不可提升的两种局部 `INFEASIBLE` 模式分开，见 [`f5_binding_empty_domain_adapter.py`](../../../src/search/f5_binding_empty_domain_adapter.py) `:1-19,66-116`。

## 6. 符号判据：角色给模板，消费边给终判

> 最终符号由 source role、consumer、runtime binding、effect kind、target claim 和 context 联合决定。

角色判据是快速模板。未经新证明把 theorem 加宽是 unsound；完成新的范围证明后再加宽完全合法，不记缩圈债。把 theorem 收窄可以保持 soundness，但要登记被移除区域为 `UNKNOWN`，并让 ID、fingerprint、consumer 与 lowering **全部同步收窄**。只收窄 theorem 而让旧 lowering 继续按原宽范围运行，会使整条消费边变成 unsound。对 rejector 而言，lowering 偏严会多杀候选，偏松只会少剪；对 constructor 或 exact checker，这个方向不能照搬。覆盖夸大首先是测量错误，只有在它被拿去扩大 theorem scope、证明穷尽或授权剪枝时，才升级成假证书型错误。PASS 越权也不是一个固定“发布面错误”，而是 requested effect 超过 granted effect 的能力越权。

最终裁断可写成：

```text
verdict = f(
  source_role,
  edge_kind,
  consumer_stage,
  runtime_binding,
  effect_kind,
  target_claim,
  context
)
```

因此，“按工件角色给符号”与“按作用边给终判”不是二选一。前者提供局部模板，后者补上 consumer、runtime 信息与目标结论。角色判据是边判据的有损投影。

**在案证据：** v1 按面符号见 [`FIRST_PRINCIPLES_DESIGN.md`](../rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md) `:633-641`；对撞段对角色模板与边终判的关系、六个输入维度及例子校准见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:189-259`；缩圈的 `UNKNOWN`、债与身份纪律见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:81-122`。

## 7. Rejector、Constructor 与 Exact Checker 的关系式

> 排除器要求拒绝集不超出定理，构造器要求产物落在已证有效集，精确 checker 要求双向等价。

每条消费合同必须先具名 `object_space`，也就是关系式量化的对象空间。对 W0，一元 theorem 的 binder 是 `BindingSelection`，因此其拒绝集首先是 binding selection 的集合，不能无证明地当成外层布局集合。若 theorem 与 lowering 的对象空间不同于 consumer 实际改变的搜索域，必须另附 transport（跨对象空间传递）证明；transport 缺失或模式不匹配时，边只能 `NO_EFFECT`。

本仓 F5 adapter 给出了现成对照：generic-I/O demand-equality 的子集 `INFEASIBLE` 对超集是反单调的，绝不能 lift；empty-binding-domain 模式才是可提升的 pose 性质。因此“局部不可行”不是天然的“外层对象可全局排除”。

在同一具名 `object_space` 和 context `c` 内，设 `D(c)` 是 lowering 前的域，`F(c)` 是真实可行集合，`R_T(c)` 是 theorem 已证明可拒绝的集合，`R_L(c)` 是 lowering 实际拒绝的集合。各角色的关系是：

```text
rejector:
  R_T(c) ⊆ D(c) - F(c)
  R_L(c) ⊆ R_T(c)

constructor:
  W_constructor(c) ⊆ W_proven_valid(c)

exact_checker:
  Accepted_exact(c) = F(c)

ledger_updater:
  updated_ledgers ⊆ granted_ledgers

authority_bridge:
  requested_effects ⊆ granted_effects
```

由 rejector 关系得到三种读数：`R_L = R_T` 是精确编译，`R_L ⊂ R_T` 是安全但少剪，`R_L ⊄ R_T` 是错误剪枝。一般研究剪枝只要求包含关系；只有自称 exact 或完整性本身进入证明时才要求等价。constructor 失败只能表示没有构造出来，不能升级成 `INFEASIBLE`；exact checker 的等号只在合同具名的对象空间与精确语义下成立；ledger updater 与 authority bridge 都不能借用其它角色的 PASS 扩大自己被授予的集合。

**在案证据：** 对撞段给出的 rejector 读数与四种其它角色关系见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:236-259,299-313`；盲态集合推导见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:336-450`；求解面方法论把必要投影、充分限制、精确语义三极分开，并规定 UNKNOWN 不改上下界账，见 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) `:46-52`；F5 的两种 `INFEASIBLE` transport 方向见 [`f5_binding_empty_domain_adapter.py`](../../../src/search/f5_binding_empty_domain_adapter.py) `:1-19,66-116`。

## 8. 每条消费边的三轴裁断

> 每条边分别给出 semantic correctness、capability admission 和 utility evidence，禁止压成总分。

一条边必须分别回答：

- **semantic correctness：** theorem、runtime binding 与具体 effect 的关系是否成立。
- **capability admission：** 该 consumer 是否获准产生这种 effect。
- **utility evidence：** 在当前工况下是否节省了昂贵工作，成本是否迁移到别处，测量是否可信。

三轴不可相互抵销。一个 unsound lowering 不能因提速巨大而获得通过；一个 sound lowering 也不能因 checker PASS 自动取得 certified pruning；一个已获研究授权的边若收益为零，语义与权限仍可能都正确，只是期权价值下降。

因此审计线不得给“综合安全分”或“总质量分”。总分会把不可交换的性质压成一根刻度，并让某一轴的高分掩盖另一轴的硬失败。三轴是 edge verdict；仓库级知识、能力和期权存量另见第 17 节。

**在案证据：** 对撞段把盲答“三本账”修正为每条消费边的三轴裁断，见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:8-16,735-792,880-894`；现有知识治理也已证明表示身份与 authority 必须正交，见 [`ADR/017`](../../governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md) `:14-18`。

## 9. 出生证、换证与晋级证

> 首个新作用边、消费位置变化、作用域扩张、能力扩张和跨域迁移分别触发不同级别的人工查验。

**出生证**面向第一条新作用边，而不只是第一种文件格式。首次从文书引用变成模型剪枝、首次真实改变可行域、首次请求更新 U/L 或 strong status，都属于出生事件。

**换证**面向已有边的语义变化：consumer stage 前移或后移、runtime literal 映射变化、theorem scope 改变、同一合同开始跨布局、跨 family 或跨运行域复用、effect kind 变化。即使文件名与 theorem ID 不变，只要边的承重关系改变，就必须换证。

**晋级证**面向能力迁移：research effect 进入 production 或 certified，某个 research PASS 第一次被 certified 文书承重引用，或某个 receipt 开始支撑 publication、terminal mint、认证账更新。晋级证不能由出生证或长期无事故替代。

同型实例在同一 checker、合同、consumer 与 effect 下重复出现时，不必每次召集整条审计线。机器负责实例检查，人工回到 first-of-kind、结构迁移与跨域晋级。

**在案证据：** 对撞段对出生证对象、换证触发器与晋级证的裁断见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:20-64`；现有开放欠账台账已经采用稳定 ID、触发器、阻断范围和关闭证据，见 [`OPEN_DEBT_LEDGER.md`](../rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md) `:10-16`。

## 10. 先专用后通用的机器化节奏

> 第一例用专用合同和专用 canary 守住，待 2 至 3 个同型实例稳定后再抽象通用 schema 与 checker。

**canary（金丝雀）**是一个范围小、故障敏感、能够尽早暴露边界错误的实例。第一例不能无保护地先运行两三次，它必须具备人工出生证、专用消费合同、专用负例与默认 shadow。可以延后的只是通用抽象，不是首例安全。

第二至第三个同型实例用于识别哪些字段是真正不变量，哪些只是第一例的偶然形状。只有当 role、consumer、effect、scope binding 和失败动作重复稳定后，才把它们结晶成通用 schema、通用 checker 和自动触发器。随后同型实例走机器常检，人工只处理换证或晋级。

这条节奏同时避免两种错误：过早把首例偶然结构冻结成全局契约，以及为了等待“更懂以后再做”而让第一条可执行 lowering 裸奔。

**在案证据：** 对撞段给出的四步结晶节奏见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:38-64`；架构草图规定每次人工走通的冻结产物是未来接口打样，而不是一次建满通用系统，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:53-65,142-148`。

## 11. Research receipt 顶层协议

> 所有可跨组件消费的 receipt 必须声明 result kind、typed outcome、verified scope、authority basis、granted effects 和非蕴含边界。

顶层 receipt 至少包含：

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

`verified_scope` 回答 checker 验证了什么；`granted_effects` 回答这个 receipt 被允许触发什么。两者不能合并。`authority_basis` 也不能由 receipt 自己凭一个字符串自封，它必须指向当前权威真源、具名 verifier 或 owner / sink。

`outcome` 是随 `result_kind` 分型的 typed outcome，不是一套全局固定枚举。theorem verification 可以使用 `VALID / INVALID / UNKNOWN`，测量可以使用 `MEASURED / CENSORED / SENSOR_UNVALIDATED`，消费准入可以使用 `ADMITTED / DENIED / UNKNOWN`。不同 `result_kind` 的 outcome 不得互相借义。

现有 W0 theorem checker 可以诚实输出：

```text
result_kind = THEOREM_VERIFICATION
outcome = VALID
verified_scope = pinned W0 binding-only theorem
granted_effects = []
```

独立 consumption admission 通过以后，另一份 receipt 才可能报告 `RESEARCH_MODEL_PRUNING`。底本早期示例中的 `RESEARCH_BINDING_PRUNING` 视为该 token 在 binding stage 的具名投影；正式词表仍待 owner 在 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 7 项裁定。本方法消灭的是可跨组件消费的顶层裸 PASS，不要求把每个内部子检查项的 `PASS` 全仓重命名。

**fail-closed（失败闭合）**在 receipt 层表示缺件、未知 schema 或身份不匹配时不猜测通过；它不等于在数学数据面拒绝候选，后者见第 20 节。

首号金丝雀的机器 envelope 目前只强制八字段存在，不强制 `granted_effects` 使用闭合词表，也不强制它与 outcome 相容；`authority_basis.source_paths` 也没有绑定被引权威文件的 digest。现行 contract checker 的 FAIL receipt 仍把“阻断真臂”写进非空 `granted_effects`，PASS receipt 则发出自定义状态 token。因此“authority_basis 反自封”和“FAIL outcome 不授予能力”目前仍是文本纪律，不是已经闭合的机器纪律。后续机器判据应要求：authority source 带 digest 与 currency；token 来自闭合词表；FAIL/INVALID 类 outcome 的 `granted_effects` 恒空，阻断后果进入 `blocking_scope` 或 `non_implications`。

**在案证据：** W0 checker 当前顶层只有 PASS/FAIL，见 [`03_check_w0_ghost_front_certificate.py`](../solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/03_check_w0_ghost_front_certificate.py) `:679-708`；现行审计已登记“PASS 文案不自带不证什么”，见 [`FINDINGS.md`](../plane_mixing_audit_20260813/FINDINGS.md) `:7-12`；`authority_basis` 的现行准入纪律见 [`ADR/017`](../../governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md) `:14-18`；首条 W0 canary 已把八字段超集与 `verified_scope / granted_effects` 分离写入发射前协议，见 [`03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md) `:7-35`。现行 schema 的开放字符串与未绑定 digest 的 authority source 见 [`03B_RECEIPT_ENVELOPE_SCHEMA_V1.json`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03B_RECEIPT_ENVELOPE_SCHEMA_V1.json) `:6-55`，receipt helper 与 PASS/FAIL token 实况见 [`w0_canary_receipt_contract.py`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/w0_canary_receipt_contract.py) `:80-101` 和 [`06_check_w0_unary_lowering_contract.py`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/06_check_w0_unary_lowering_contract.py) `:548-609`；对撞段的 receipt 协议见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:65-124`。

## 12. 可执行消费合同

> 每条 theorem→consumer 边必须绑定来源身份、消费者位置、runtime literal 映射、语义关系、权限边界和失败动作。

最小合同采用五组字段，而不是重复保存完整 theorem：

1. **来源身份：** theorem/Judgment ID、proposition fingerprint、proof checker identity、premise fingerprint、problem/objective/context identity。
2. **消费者与运行时绑定：** consumer entrypoint、consumer stage、`object_space`、`claim_channel / target_claim`、effect kind、abstract trigger 及其到 runtime literal 的映射。effect kind 说明这条边做什么动作；claim channel 说明该动作准备支撑上界相关搜索、下界 witness、纯可行性判断还是其它结论，因而决定第 7 节的 `F(c)` 采用哪一种语义。
3. **语义关系：** 内联第 7 节的五类关系，即 rejector 的 `R_L ⊆ R_T`、constructor 的 `W_constructor ⊆ W_proven_valid`、exact checker 的双向等价、ledger updater 的 `updated_ledgers ⊆ granted_ledgers`、authority bridge 的 `requested_effects ⊆ granted_effects`，并绑定独立 lowering checker、transport 证明或其它相称验证方法。
4. **权限与边界：** result kind、verified scope、granted effects、research allowlist、certified write denylist、import 方向和禁止触碰的 strong-status/U/L/publisher 资产。`certified` 摘要或 diff 不变可以是验收项，但不是边界充分条件：runtime 仍可能 import research code、source digest 可能变化、strong-status 写点可能增加、认证 loader 也可能接受 research schema。
5. **新鲜度与失败动作：** current context fingerprint、runtime environment/config fingerprint、currency、STALE 传播、复审触发器、supersession 与 retirement。合同异常必须在产生模型改动前判成 `NO_EFFECT`；若实现无法前置全部 guard，只能丢弃并重建整个模型，不得依赖事后撤销约束。

“拒绝集包含关系带见证”只能作为反例机制：一个见证足以推翻包含关系，不能普遍证明全集包含。真正准入仍需要独立 checker、有限域穷举、形式证明或与 scope 相称的验证。

合同的机器闸应挂在 consumer 第一次准备改变可行域的位置。挂在 theorem checker 太早，checker不知道具体 consumer；挂在终审太晚，被错误删除的候选不会再出现；挂在 telemetry 里则只有观察能力，没有授权能力。

**在案证据：** 架构草图把“哪类消费者、何种极性、允许何种 lowering、需要哪些指纹、如何失效”列为证明产品第五件，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:53-63`；对撞段对五组合同的修订见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:261-364`；盲答的 W0 合同保留了 `claim channel`，见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:842-864`；现行 cut 协议要求 proof 到 literal 的绑定、错误强化负路径和真实消费接线，见 [`23_rule_cut_evolution_protocol.md`](../../项目说明/23_rule_cut_evolution_protocol.md) `:18-31`。

## 13. 前提指纹与 context currency

> 前提、作用域或 consumer binding 漂移使对应 context 下的 edge 进入 STALE，旧消费立即失效而不是继续幽灵运行。

状态不是 artifact 的单一全局标量。v2 分别观察：

```text
artifact_state(asset, context, time)
edge_state(consumption_edge, context, time)
```

context 状态至少拆成三轴：

| 轴 | 受控取值 | 未访问 context 的默认 |
|---|---|---|
| applicability | `UNASSESSED_IN_CONTEXT / APPLICABLE / NOT_APPLICABLE_IN_CONTEXT` | `UNASSESSED_IN_CONTEXT` |
| verification | `UNVERIFIED / VERIFIED / REFUTED` | `UNVERIFIED` |
| freshness | `UNBOUND / CURRENT / STALE` | `UNBOUND` |

W0 theorem 在 pinned W0 context 中可以是 `APPLICABLE + VERIFIED + CURRENT`；另一个 layout 或 rectangle 在未检查前只能是 `UNASSESSED_IN_CONTEXT + UNVERIFIED + UNBOUND`，不得默认为永久不适用，也不得从相邻 context 继承状态。§14 的 `NOT_APPLICABLE_BY_TYPE` 属 observation 轴，表示某种测量按类型永久没有语义，不得与本节的 context applicability 压成同一字段。

前提、scope、runtime literal 映射、consumer stage、runtime environment/config 或 lowering digest 任一漂移，只使受影响 context 下的 edge 进入 `STALE`。edge 激活还要求“当前 runtime context 蕴含 theorem scope”有据可查；指纹未漂移只证明被绑定材料没变，不证明一个新 context 满足旧 theorem。对第一号固定对象，精确相等 guard 可以充分；参数化 family theorem 必须结构化 premises，并证明 `runtime context ⊨ theorem context`。

失效后的安全动作是停止旧消费并要求重核，而不是沿用同名条目、旧缓存或 generated view。

**在案证据：** `rules/derived/` 已有 `UNREVIEWED → ACTIVE → STALE` 状态机和前提指纹先例，且只在存在 consumer 时阻断，见 [`rules/derived/README.md`](../../../rules/derived/README.md) `:7,19-44`；架构草图要求缩圈改变前提或家族范围时改变指纹并阻断旧消费，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:120-124`；落地线 B 段知情对撞席对条件事项、context 与 fingerprint 的逐字裁断见 [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:550-677`，本线程对 `state(a,c)` 的采纳与改造见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:689-733`；固定 guard 与 family entailment 的边界见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:884-900`。

## 14. typed null 与 reachability

> 测得零、作用域必零、未建对象、未测、删失和传感器未验证必须使用不同机器状态，且与 NOT_REACHED 等触达状态正交。

B 段裁断提出“零至少六态”。本文采用更明确的 typed observation：

```text
Observation<T> =
  VALUE_MEASURED(T)
  | ZERO_BY_SCOPE(proof_ref)
  | NOT_READY
  | NOT_APPLICABLE_BY_TYPE
  | UNKNOWN_UNMEASURED
  | CENSORED(partial_state, reason)
  | SENSOR_UNVALIDATED(raw_value)
```

`ZERO_MEASURED` 可作为 `VALUE_MEASURED(0)` 的具名投影。`NOT_READY` 表示语义对象尚未建成，`NOT_APPLICABLE_BY_TYPE` 表示某种 observation 按类型永久不适用；两者不能继续压成一个 `N/A_NOT_READY`。这里的 `NOT_APPLICABLE_BY_TYPE` 只属于测量轴，不是第 13 节的 context applicability。`SENSOR_UNVALIDATED` 可以保存打印值，但不能支撑“真实测量”结论。

这条轴与 reachability 正交：`NOT_REACHED` 表示 consumer 没有到达，`REACHED_NO_EFFECT` 表示到达但没有可测变化，`EFFECT_NO_TERMINAL` 表示 effect 已发生但预算内没有终态。没到达不是测得零，删失也不是没有发现。

任何 observation 都不自动授予 capability。`ZERO_BY_SCOPE` 主要支撑语义轴；`VALUE_MEASURED(0)`、`CENSORED`、`SENSOR_UNVALIDATED` 进入效用与测量轴。

**在案证据：** B1 的六种零态逐字底本见落地线 B 段知情对撞席 [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:49-67`；本线程对 typed null、reachability 正交和 observation 不授予能力的改造见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:568-615`。现行草图自凭据已明确“无过滤器时写 `NOT_TESTED`，不得写 0”，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH_SELF_RECEIPT.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH_SELF_RECEIPT.md) `:5,64-83`；开放欠账也规定无埋点不得写真零，见 [`OPEN_DEBT_LEDGER.md`](../rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md) `:96-106,194`。

## 15. 能力向量而非 authority 阶梯

> IMPLEMENTED、VERIFIED 与 experiment／production grants 是独立 facet，机器准入只认精确 granted effects。

B 段裁断的 `IMPLEMENTED / VERIFIED / AUTHORIZED_FOR_EXPERIMENT / AUTHORIZED_FOR_PRODUCTION` 可以保留为人类里程碑投影，不能作为单一线性阶梯。一个 checker 可以 VERIFIED，而 consumer 尚未实现；owner 可以授权研究实现，而代码仍是 ABSENT；某种 production telemetry 获准，也不等于 certified pruning 获准。

机器状态至少拆为：

```text
implementation_state: ABSENT | PARTIAL | IMPLEMENTED
verification_state: UNVERIFIED | VERIFIED | REFUTED
freshness_state: UNBOUND | CURRENT | STALE
applicability_state: UNASSESSED_IN_CONTEXT | APPLICABLE | NOT_APPLICABLE_IN_CONTEXT
activation_state: INACTIVE | SHADOW | ACTIVE
granted_effects: set<capability_token>
```

**capability token（能力令牌）**不是密码学令牌，而是精确命名的一项获准作用。候选词表例如 `RESEARCH_OBSERVATION`、`RESEARCH_MODEL_PRUNING`、`PRODUCTION_NONCERT_TELEMETRY`、`CERTIFIED_MODEL_PRUNING`、`UPPER_LEDGER_UPDATE`、`LOWER_LEDGER_UPDATE`、`TERMINAL_STATUS_MINT`、`PUBLICATION`、`OWNER_DECISION`；其中 `OWNER_DECISION` 只能由具名 owner 闸持有，普通边不得请求。底本中的 `RESEARCH_BINDING_PRUNING` 是 `RESEARCH_MODEL_PRUNING` 的 binding-stage 投影。

正式词表、授予者以及 production 与 certified 是否在项目级分开，仍由 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 7 项裁定。在词表闭合前，这些 token 只有人读分类作用，不构成机器准入机制；词表闭合后，未知 token 必须 fail-closed deny，不能静默忽略。无论最终是否采用两套顶层分类，一个 production grant 都不得被解释成未具名的 certified effect。

**在案证据：** B2 的 `IMPLEMENTED / VERIFIED / AUTHORIZED_FOR_EXPERIMENT / AUTHORIZED_FOR_PRODUCTION` 四层逐字底本见落地线 B 段知情对撞席 [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:825-846`；本线程把它改造成独立 facet 与 token 集的裁断见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:617-687`。知识治理已明确表示位置、认识论 authority 与 owner 决定不能压成一个字段，见 [`ADR/017`](../../governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md) `:8-18`；`PROJECT_LOCK.md` 也规定 checker PASS、内部 seal 与 owner 关门不是同一能力，见 [`PROJECT_LOCK.md`](../../../PROJECT_LOCK.md) `:194-195`。

## 16. 条件事项记录

> LATENT_ASSET、CONDITIONAL_DEBT 和 MEASUREMENT_GAP 作为独立 condition records 指向同一资产，其状态按 context 和时间计算。

统一条件事项记录采用共同头部与 `kind` discriminated union：

- `LATENT_ASSET`：资产自身成立，但尚未知道当前可执行 coupling。
- `CONDITIONAL_DEBT`：某个结论、能力或迁移依赖尚未清偿条件。
- `MEASUREMENT_GAP`：所需效果、成本或传感器验证缺失、删失或未建立。

union 作用于 condition record，不强迫整个 artifact 只能属于一种 kind。同一个 theorem 可以同时有一条未来 coupling 的 `LATENT_ASSET`、一条缺运行收益的 `MEASUREMENT_GAP` 和一条 lowering 尚未验证的 `CONDITIONAL_DEBT`。每条记录分别计算 `state(asset, context, time)` 或 `edge_state(edge, context, time)`。

前提 fingerprint 漂移统一进入 `STALE`，但阻断范围按具体 context 与 consumer 决定。到期未清也不把 theorem 判假，只激活记录里声明的阻断范围。

condition record 的关闭、改 kind、拆分或合并都不能减少 canonical asset 层的既有义务。关闭必须保留关闭证据与“不再阻断什么”，原记录不得删除；把一笔 `CONDITIONAL_DEBT` 改名成 `LATENT_ASSET` 不能洗掉其历史阻断关系。

**在案证据：** B3 的共同头部、条件边、治理合同和 `LATENT_ASSET / CONDITIONAL_DEBT / MEASUREMENT_GAP` 逐字底本见落地线 B 段知情对撞席 [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:550-677`；本线程对 context 状态与多记录形态的改造见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:689-733`。现行开放欠账已经规定稳定 ID、状态、到期日、阻断范围与关闭证据，且逾期不自动判假，见 [`OPEN_DEBT_LEDGER.md`](../rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md) `:10-16`；`OD-B0-INST-01` 是现成的 measurement gap，见同文件 `:96-107`。

## 17. 一库三账一流水

> 规范化 identity/event source 生成知识、能力、期权三本只读存量投影，每次实验只追加成本与三类 delta 的交易流水。

“一库”指单一规范化 identity/event substrate，不是把所有 authority 塞进一个大 JSON 文件。owner authority、机器真源、research evidence 与 archive 仍保持各自来源，只共享稳定身份和事件关联。

仓库级存量分成：

```text
RepositoryStocks =
  (knowledge_stock, capability_stock, option_stock)
```

- **知识账：** 当前有哪些 theorem、反例、scope 与验证状态。
- **能力账：** 当前有哪些实现、verifier、consumer、grant 与 activation。
- **期权账：** 哪些资产已知可能在某个触发器下产生未来价值，维护成本是多少。

每次实验不直接手改三本存量账，只追加：

```text
ExperimentTransaction =
  (cost, Δknowledge, Δcapability, Δoption)
```

四格分别记录资源成本、知识增减、能力增减和期权新增/收窄/触发/退役/转冷档；typed observation、删失与 sensor validity 是交易证据。确定性 projector 再生成三本只读视图。

事件类型对账户的写入权限必须固定：theorem verification event 只更新知识账；implementation event 只更新能力账的 implemented facet；holdout 或测量 event 只增加证据、调整 utility/option 读数；只有具名 grant event 才能改变 capability grants，grant issuer 必须是 owner、认证 sink 或另行具名的授权入口。projector 的“确定性＋只读”只是形式属性，不构成权限约束，禁止从 measurement 或 knowledge event 推导 capability grant。

这与第 8 节不冲突：第 8 节是单条边的三轴 verdict，本节是全仓资产组合的三种存量。

**在案证据：** B4 的“一库、三本存量账、一张四格流水”逐字底本见落地线 B 段知情对撞席 [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:455-545`；本线程对 identity/event source、只读投影与交易 delta 的改造见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:735-792`。现行知识治理已采用 source record 与 generated projection 分离、decision register 不自铸 authority，见 [`ADR/017`](../../governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md) `:14-18`。

## 18. TYPED_OPTION 与 UNTYPED_ARCHIVE

> 已知 coupling 的资产承担主动扫描和维护成本，尚无可表达 coupling 的有效成果进入冷档案，重新使用前必须重新类型化和复验。

B 段裁断用 `Γ_known(a) ⊆ Γ_true(a)` 表达一个重要限制：今天已知的耦合集只是资产真实未来耦合集的一部分。没有当前 consumer 不等于没有未来价值，强迫所有研究成果立即找到用途或退役，会系统性杀死尚未有语言表达的新概念。

`TYPED_OPTION` 必须有已知 coupling、context、trigger、可能影响的账、maintenance cost、主动扫描规则和复核触发器。它进入 option stock，但不因此获得 execution grant。

`UNTYPED_ARCHIVE` 保存原始 artifact identity、原 context、proof/evidence 和当时已知的 non-implications；它不承担当前 currency、主动扫描、consumer 兼容、当前 authority 或持续维护预算。重新启用必须依次经过：

```text
UNTYPED_ARCHIVE
→ 新建 TYPED_OPTION
→ 当前 context 重验
→ 建立消费合同
→ 申请 effect grant
```

冷档案不能成为债务洗白通道。准入检查以 canonical asset 为单位，对指向同一资产的全部 condition records 求并集；任一记录仍持有当前 consumer、当前阻断范围、到期义务或现行 claim 依赖，整个资产都不得降入 `UNTYPED_ARCHIVE`。关闭、改名或拆分某条记录不能改变这项资产层判定。

**在案证据：** B5 的 `TYPED_OPTION / UNTYPED_ARCHIVE` 两层登记与“不给期权信用不等于删除”的逐字底本见落地线 B 段知情对撞席 [`sources/b_segment_verdict_20260816.md`](sources/b_segment_verdict_20260816.md) `:360-395`，`Γ_known(a) ⊆ Γ_true(a)` 与保留低成本冷档案的理由见同文件 `:850-865`；本线程对重启路径和反债务洗白规则的改造见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:794-866`。现行开放欠账规定登记不能抵消阻断、关闭不能删除原行，见 [`OPEN_DEBT_LEDGER.md`](../rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md) `:10-16`。

## 19. SHADOW 到 RESEARCH_ACTIVE

> 新 lowering 必须先记录 would-reject 而不改模型，通过负 canary 和 contract replay 后才能获得 research execution grant。

`SHADOW` 是影子运行：consumer 计算本来会拒绝哪些对象并留下 receipt，但不改变模型。它用于核对 theorem trigger、runtime literal 映射、scope guard 和 effect 计数。影子结果本身不证明实际路径安全，也不授予 `RESEARCH_MODEL_PRUNING`。

进入 `RESEARCH_ACTIVE` 前，必须有独立 lowering contract checker、错误 scope/slot/pose 等负 canary、contract replay 和显式 research grant。激活以后仍只在声明的 research context 产生作用；任何 fingerprint 或 contract mismatch 都必须得到 `NO_EFFECT`。

`NO_EFFECT` 只有两种合格实现：在产生任何模型改动之前完成全部 guard 判定，或丢弃已经变动的模型并从干净输入重建。不得假定求解器模型对象支持事后撤销约束；例如 CP-SAT 的 `CpModel` 添加约束后没有通用删除原语。

shadow 与 active 的分离让第一例可以被真实观察，又不会为了测量而先把未经验证的约束装进可行域。

**在案证据：** 盲答的 W0 SHADOW/RESEARCH_ACTIVE 两阶段见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:879-914`；现行 cut 协议规定 offline shadow 不得隐式改变 production registry、lowering 或 owner gate，且进入 production 必须另建 owner-authorized 变更包，见 [`23_rule_cut_evolution_protocol.md`](../../项目说明/23_rule_cut_evolution_protocol.md) `:39-43`。

## 20. 失败语义：控制面 BLOCK，数学面 NO_EFFECT

> 晋级申请未获裁时阻断能力迁移，运行合同异常时撤掉新作用并返回 INVALID／UNKNOWN，绝不把候选判成 INFEASIBLE。

同一个“fail-closed”在不同面上必须给出不同动作。

| 场景 | 正确默认动作 |
|---|---|
| research→certified 晋级超时或未裁 | `EXPIRED_BLOCKED`，只阻断 requested transition，不授予新 capability |
| research lowering scope/contract 不匹配 | `NO_EFFECT`，不加新约束，treatment 记 `INVALID` 或 `UNKNOWN` |
| theorem `STALE` | 停止旧消费，等待当前 context 重验 |
| certified 发布材料不全 | 阻断 publication |
| baseline research 已获准，另一项晋级申请超时 | baseline 不因无关申请自动停用 |

控制面的 BLOCKED 说“这条能力迁移没有批准”；数学面的 NO_EFFECT 说“新约束没有资格改变可行域”。把二者混成“审计没批，所以候选不可行”，正是 v1 要防的符号污染。完整性证据是否允许立即停用一条已经获准的现有边，属于 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 8 项待裁；在该项裁决前，本表按上述无条件口径解释。

### 跨域边界事件固定格式

任何 research 工件申请触碰 certified 资产、扩大 effect 或改变运行域时，边界事件至少记录：

```text
source_asset
current_domain
target_domain
requested_effects
touched_paths_and_schemas
consumer_entrypoint
reversibility
rollback
throughput_cost
owner_or_sink
decision_deadline
unresolved_blocking_scope
```

其中格式本身是方法义务，不等待 SLA 裁决。`decision_deadline` 的具体值、接单人和紧急停用条件由 owner 在第 8 项决定；未裁时 `unresolved_blocking_scope` 只能阻断声明的迁移，不能产生数据面证据。

**在案证据：** 对撞段对两种 BLOCK、共存表和固定格式字段的裁断见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:375-468`；首条 W0 canary 已把 `EXPIRED_BLOCKED` 与 `NO_EFFECT` 写成不同平面的受控语义，见 [`03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md) `:37-43`；开放欠账台账也规定逾期不自动把结论判假，只激活阻断范围，见 [`OPEN_DEBT_LEDGER.md`](../rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md) `:10-16`；求解面方法论规定资源中止不改任何账，见 [`29_solving_methodology_skill.md`](../../项目说明/29_solving_methodology_skill.md) `:48-52`。

## 21. 跨域单向边界

> research 可以读取 certified 真源作实验输入，certified 不得 live-import research code、receipt 或 registry。

research 可以读取 canonical rules、候选池、现有模型纯函数和认证源字节，把它们的 digest 写入研究 receipt。这是研究对认证真源的只读依赖，不是 authority 迁移。

反方向默认禁止：certified runtime 不得 live-import `docs/research/**` 的代码，不得把 live `rules/derived/**` 或 future theorem registry 当 certified constraint source，不得接受 research receipt schema 铸造 strong status，不得让研究 run 写 U/L、review gate、delivery manifest、supervisor 或 publisher。

目录名、`research_only` 文件头和 default-off flag 都不是完整隔离。边界必须落在 import 方向、loader schema、write capability、consumer admission 与 sink replay 上。`certified` 摘要、状态页或 diff 没有变化，也不能替代这些检查，因为隐藏的 import、loader admission、source digest 变化和 strong-status 写入口都可能不出现在摘要里。

write capability 还必须覆盖共享可写命名空间和进程内共享状态。本仓至少要显式看见 `.artifacts/`、`data/checkpoints/`、`data/preprocessed/` 及进程级 cache：首号金丝雀会写自己的 `.artifacts/` 根，而 W0 theorem 的 problem identity 又读取另一个 `.artifacts/` 根；master hint 会持久化到 `data/checkpoints/master_hints/`；binding 代码有进程级 `_POSE_LEVEL_BINDING_CACHE`。这些面都可能在不修改 `src/` 的情况下跨 run 或跨 arm 传递影响。

因此，第 12 节的 context fingerprint 必须包含 runtime environment、配置、共享缓存隔离与可写根身份。类似 `EXACT_B1_ROUTING_AWARE_BINDING` 这种改变 lift soundness 前提的环境开关，不能被当作合同外背景。当前 `src/` 红线尚未形成覆盖全部共享状态的机器闸；是否把这些检查纳入 canary 常设落位契约，随 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 3 项一并裁定。

第一号 research lowering 的入口、测量和 receipt 留在 research dossier；若需要修改 tracked `src/`，必须停止并另行上桌。

**在案证据：** 工作线 G 已登记静态 lowering 留在研究模块、certified 源文件零改动、触 `src/` 即面边界事件，见 [`ROADMAP.md`](../../项目说明/ROADMAP.md) `:61-69`；当前 W0 canary 的发射前协议同样规定 research dossier 内落位、修改 tracked `src/` 即 `BOUNDARY_EVENT` 并停止，见 [`03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md) `:46-54`；W0 problem identity 对 `.artifacts/` 输入的绑定见 [`01_JUDGMENT.json`](../solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/01_JUDGMENT.json) `:31-40`；跨 run hint 与进程 cache 见 [`master_hint_persistence.py`](../../../src/search/master_hint_persistence.py) `:11-37` 和 [`port_binding.py`](../../../src/models/port_binding.py) `:28,106-138`；环境开关对 lift 前提的影响见 [`f5_binding_empty_domain_adapter.py`](../../../src/search/f5_binding_empty_domain_adapter.py) `:38-49,66-86`；认证宪法禁止把 exploratory artifact 当 certified proof，见 [`PROJECT_LOCK.md`](../../../PROJECT_LOCK.md) `:693-700`。

## 22. Certified promotion 重新铸造

> 研究 theorem 进入认证路径必须由 owner 决定、certified sink 重验、独立 lowering checker 和认证侧实现共同构成新变更包。

promotion 不是把 `research_only` 改成 `certified`，也不是翻一个 default-off flag。最小变更包包括：

1. 显式 owner promotion 决定；
2. 被认证侧接受的 theorem identity 与完整 premise root；
3. 当前运行重推 theorem，或把 theorem/checker/input 身份纳入认证依赖根；
4. 独立 lowering correctness checker；
5. malformed、scope drift、错误强化、stale premise 的红测试；
6. 认证侧自己的实现，不 live-import research 模块；
7. certified sink 对 exact inputs、consumer、lowering 和 proof 重新验证；
8. `PROJECT_LOCK`、spec、test 与 source digest 边界同步更新；
9. 原 research 包保留其历史 research 身份，必要时标 `PROMOTED`，但不成为 certified runtime 的活依赖。

**sink（终端消费方）**是实际准备让强状态影响 frontier、terminal evidence 或 publication 的一方。authority 在 sink 重新铸造，不由 producer、writer、registry、当前进程新鲜度或历史 PASS 继承。

**在案证据：** `PROJECT_LOCK.md` 已规定 strong-status proof authority 必须由 sink 从磁盘重放并重新绑定，见 [`PROJECT_LOCK.md`](../../../PROJECT_LOCK.md) `:357`；cut 协议规定 shadow 进入 production 需要 owner-authorized 变更包并重新满足证明、版本、接线与发布门槛，见 [`23_rule_cut_evolution_protocol.md`](../../项目说明/23_rule_cut_evolution_protocol.md) `:39-47`；工作线 G 把 research feedback 与 certified cut 合流保留为 owner 开放题，见 [`ROADMAP.md`](../../项目说明/ROADMAP.md) `:69`。

## 23. 常设闸吞吐成本

> 所有常设闸必须登记保护对象、单位成本、测量状态、误挡率、复审触发器和 sunset／reapproval 条件。

过严限制不会主动报告自己杀掉了多少合法解，过缓常设闸也不会主动报告自己吞掉了多少研究节拍。每个常设闸至少登记：

```text
protected_risk
effect_scope
per_item_cost
per_run_cost
human_queue_cost
measurement_state
observed_false_block_rate
review_trigger
sunset_or_reapproval_trigger
owner_of_tradeoff
```

未测成本必须使用 typed observation，不能写 0。成本账不意味着 soundness 门可以因太慢而自动关闭；它只让“安全换降速”成为可见交易，使 owner 能决定换方案、加资源、改变频率或继续承担成本。

临时退守若只进不出、案例补丁占比持续上升或 gate 成本长期无测量，均触发复审，而不是等系统自己报警。

**在案证据：** 架构草图已明确“过缓也不会自曝”，要求保守动作明码标价并以上桌方式处理，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:126-132`；`OD-B0-INST-01` 要求有限存量清单、观测点、缺口与预计成本，无埋点不得写真零，见 [`OPEN_DEBT_LEDGER.md`](../rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md) `:96-107`；材料一第六点的采纳结论与完整字段清单见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:470-503`。

## 24. 审计线止步线

> 审计线不做综合质量评分、不替 owner 决策、不普遍强制预注册，也不接管 theorem 发现与实验选题。

审计线负责检查角色、消费边、scope、runtime binding、capability、currency、失败动作与跨域迁移。它不评价 theorem “有多漂亮”，不决定研究路线值不值得投资源，也不把 soundness、authority 与 utility 压成一个总分。

审计线不普遍强制预注册。具体因果 A/B、go/no-go 或高预算实验可以由自己的协议要求冻结 corpus、阈值与删失口径；审计线只检查“声称遵循的协议是否真的遵循”，不成为全项目实验委员会。

人的位置保留在新数学模板发明、资源分配和 owner 治理。常规实例验证、currency、receipt 解析与 A/B 计数应在形态稳定后交给机器。

**在案证据：** 架构草图把人的职责收敛到模板发明与治理，并明确不自动化 owner 决定，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md) `:134-142`；工作线 G 已对 Phase -1 单独要求 tracked protocol 和预冻结阈值，但同时声明协议不产生立项或开跑授权，见 [`ROADMAP.md`](../../项目说明/ROADMAP.md) `:61-66`；对撞段的止步线裁断见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:365-374`。

## 25. W0 第一号 canary 的最小实例化

> W0 只允许把精确 `active_output_slot(041,0)` lowering 为 binding-stage 禁用该活动 slot，不得提升成 pose ban、跨布局 family rule 或 certified cut。

W0 现有 theorem 保持不动：`J-W0-GHOST-FRONT-BOUNDARY-041-V1`、精确 `problemHash`、`objectiveHash`、`contextHash`、固定布局、固定 6×7 rectangle、binding-only 量化与 `evidence_only` 身份继续由原包承载。新 canary 不反写旧包来伪装它当初已有 lowering。

以下是本方法对首号 canary 的规定形态，不声称与 experiment_two 已冻结文件中的自由文本 token 逐字对应。独立消费合同采用 `REJECTOR` 角色，consumer stage 固定为 binding，`object_space = binding_selection`，`claim channel = UPPER_AFFECTING_RESEARCH_SEARCH`，abstract trigger 是 `active_output_slot(boundary_port_041, 0)`，actual lowering 是 `¬active_output_slot(boundary_port_041, 0)`，allowed effect 只含 `RESEARCH_MODEL_PRUNING`，其 binding-stage 投影可记作 `RESEARCH_BINDING_PRUNING`。第一号固定对象要求 `R_L = R_T`；certification、U/L、strong status、跨布局 family generalization 全部不在 grant 中。当前 canary 实物使用的是描述性 `granted_effects` 字符串，尚未实现本方法的闭合 capability token 词表。

scope guard 必须逐项锁住 problem、objective、context、fixed layout、fixed rectangle、instance、pose、slot、active-output 语义与 canonical predicate 5。任一不符，lowering 为 `NO_EFFECT`。精确相等 guard 只对第一号固定对象充分；未来参数化 family theorem 不能继续只依赖一个 hash，必须结构化 premises，并证明 `runtime context ⊨ theorem context`。

执行分六步：旧证明包不动；新建独立消费合同；锁定 scope guard；先 SHADOW 再 RESEARCH_ACTIVE；用 pose ban 等错误强化作反例；A/B 只测收益，不证明零误杀。

2026-08-16 的窄授权只允许研究沙盒中的一次静态 lowering on/off 测量，不构成推理外环立项、通用 D3/D4 解冻或 certified promotion。

**在案证据：** W0 theorem 的身份、hash 与公式见 [`01_JUDGMENT.json`](../solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/01_JUDGMENT.json) `:2-12,43-85`；原包明确不含 lowering，见 [`experiment_one README`](../solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/README.md) `:3-16,75-76`；六步实例化与 claim channel 原文见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:822-950`；owner 原话、转达链与窄效力见 [`OWNER_SIGNAL_20260816.md`](OWNER_SIGNAL_20260816.md)；派生执行边界见 [`03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md) `:62-64`；当前 contract checker 的描述性 token 实况见 [`06_check_w0_unary_lowering_contract.py`](../solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/06_check_w0_unary_lowering_contract.py) `:548-609`。

## 26. 机器验收与负 canary

> 错误 slot、错误 pose、移动 rectangle、换 layout、stale premise、错误 consumer stage 和伪造 grant 都必须使 lowering 退回 NO_EFFECT。

机器验收至少覆盖：

- theorem/Judgment、checker、contract 与 consumer digest 对拍；
- abstract trigger 到 runtime literal 的精确映射；
- 错误 slot、错误 pose、移动 rectangle、换 layout 的 scope mutation；
- stale premise 与旧 context fingerprint；
- 把 binding theorem 错放到 master stage；
- 伪造或扩大 `granted_effects`；
- 正确 treatment 能产生预期 would-reject，错误变体全部退回 `NO_EFFECT` 的灵敏度检查。

负 canary 证明 guard 会在已知错误上关闭，但不能单独证明所有未来 lowering 都 sound。独立关系验证仍是主体。最终 checker、相同 optimum 或 A/B 零差异也不能证明“没有误杀”，因为被错误删除的合法解不会到达终审。

**在案证据：** W0 六步中的 mutation canary、pose ban 反例与 A/B 边界见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:879-950`；现行自凭据明确零误杀仍为 `NOT_TESTED`，不能由 checker PASS 外推，见 [`REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH_SELF_RECEIPT.md`](../solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH_SELF_RECEIPT.md) `:75-85`。

## 27. 明确否决的做法

> 禁止第四个混合语义面、裸 PASS 消费、receipt 自铸 authority、合同失败时拒候选、default-off certified 暗管、最终 checker 代替零误杀证明和研究标签原地升格。

本节给出本方法内部的明确推荐。第 1、2、5 条仍在 owner 裁决请求中保留反向选项，是因为项目级终裁权属于 owner；在相关请求裁定前，它们不得被误读成已经改写项目现行入口。

1. **否决第四个混合语义面。** 研究内部没有统一符号，升面会把 theorem、measurement、gate 与 archive 再装进一个桶；正确结构是三语义面与运行域正交。
2. **否决全仓词法式重命名 PASS 或只加免责声明。** 词汇不是根因；跨组件 consumer 必须解析 `result_kind`、scope、authority basis 与 granted effects。散文挡不住 `status == "PASS"`。
3. **否决 theorem checker PASS 自动打开 lowering。** theorem 正确、runtime context 匹配、literal 映射正确、lowering 不变强和 consumer 获权是至少五个独立问题。
4. **否决合同异常时“保守地”拒候选。** 数学面的安全回退是撤掉新约束并返回 INVALID/UNKNOWN；拒候选会把验证故障变成假不可行。
5. **否决把 research lowering 塞进 certified `src/` 再靠 default-off flag 隔离。** default-off 是配置，不是结构隔离；代码会进入 source digest、测试、重构和误启面。
6. **否决把每条机器消费定理都塞进 canonical 或 `PROJECT_LOCK.md` 冻结。** hash 只证明字节没变，不证明 theorem 正确；高频派生层应重推并对活消费边绑定 fingerprint。
7. **否决用最终 checker、同 optimum 或 A/B 零差异证明零误杀。** 被错误删除的对象不会到达终审，性能对照不是 soundness proof。
8. **否决因 research lowering 与 cut 都会剪枝就立即合并框架。** 两者当前 authority、生命周期与威胁模型不同；只复用原则，合流等待 family 普遍性与 owner 裁定。
9. **否决把 theorem 收窄一律判失败，或把局部 theorem 方便地写宽。** 前者把 utility 退化误报成 soundness，后者直接扩大未证拒绝集。
10. **否决强制所有 lowering 与 theorem 完全等价。** 一般 rejector 只需 `R_L ⊆ R_T`；子集 lowering 可以 sound 但少剪。
11. **否决依赖目录名、文件头或手写 consumers 清单隔离。** 真边界在 import、loader、write capability、consumer admission 与 sink replay。
12. **否决把审计线变成所有研究批次的常驻审批者。** 这会让研究吞吐被治理队列锁死，也让审计者错位成事实登记者；机器管实例，人工管 first-of-kind、换证和晋级。
13. **否决把“certified 摘要不变”当成认证边界充分条件。** 摘要不变仍可能漏掉 research import、source digest 变化、新 strong-status 写点和认证 loader 接受 research schema；必须检查真实 import、loader、write capability、consumer admission 与 sink replay。

**在案证据：** 前十二条完整理由见 [`sources/blind_answer_20260815.md`](sources/blind_answer_20260815.md) `:952-1041`；第 13 条与对撞后的其它修正见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:505-535,868-960`。

# 附录 A：不推给 owner 的六条逻辑后果

以下六条是本方法内部的逐边逻辑后果，不需要 owner 在每个实例上重新决定。它们不自动解决多边路径的 lifting 与 token 组合问题；该路径级义务见 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md) 第 13 项。其余必须由 owner 决定的项目级事项也集中在该文件。

1. rejector 的 lowering 不得拒绝 theorem 未证明可拒绝的对象。
2. theorem PASS 不自动产生 `granted_effects`。
3. 数学合同异常时必须 `NO_EFFECT`，而不是拒绝候选。
4. 测量删失、未测和 sensor 未验证不得写成零。
5. `RESEARCH → CERTIFIED` 必须重新铸造，不能靠改标签完成。
6. 活跃 consumer 所依赖的事项不能被扔进 `UNTYPED_ARCHIVE` 逃避维护。

这六条的原始裁断见 [`sources/collision_verdict_20260816.md`](sources/collision_verdict_20260816.md) `:1142-1156`。
