# 三面防污染模型 v2：owner 裁决请求

> **日期：** 2026-08-16  
> **用途：** 把方法论中必须由 owner 决定的项目级选择集中上桌。技术上可直接推出的六条逐边后果不列为请求，见 [`TRI_PLANE_MODEL_V2.md`](TRI_PLANE_MODEL_V2.md) 附录 A。  
> **读法：** 每项按“问题、选项、推荐、代价”展开，正文给出足以直接裁决的含义；仓内登记、历史批次和代码坐标集中在脚注。

## 术语

- **lowering（降译）：** 把抽象 theorem 转成具体运行时约束、变量域收缩或过滤动作。
- **canary（金丝雀）：** 用范围小、故障敏感的实例先验证边界，不能把局部成功外推成整条路线成立。
- **receipt（收据）：** 机器输出的结构化结果。顶层收据至少区分结果种类、判词、验证范围、权威依据、获准作用与明确不蕴含项。
- **typed outcome（类型化判词）：** 判词随收据种类变化，例如 theorem verification 使用 `VALID / INVALID / UNKNOWN`，测量使用 `MEASURED / CENSORED`，消费准入使用 `ADMITTED / DENIED`；它们不是一套可互换的全局 PASS/FAIL。
- **authority basis（权威依据）：** 一条 authority 声明真正依靠的 owner 原话、当前机器真源、具名 verifier 或 certified sink，不是收据自己写给自己的标签。
- **granted effect / capability token（获准作用／能力令牌）：** 精确命名“允许做哪一种事”的机器项，例如只观察、研究剪枝、认证剪枝、更新上界账或发布；它不是密码学密钥。
- **admission wrapper（准入包装器）：** 在 consumer 真正采用收据前，联合核对来源身份、scope、合同和获准作用的独立入口。
- **premise fingerprint / currency（前提指纹／新鲜度）：** 对承重前提与当前 context 的机器身份；漂移后旧消费进入 `STALE`，不能继续幽灵运行。
- **SHADOW：** 只记录“本来会拒绝什么”而不改变模型的影子运行。
- **strong status（强状态）：** 会参与剪枝、终态证据或发布的强结论状态，例如 proof-bearing `INFEASIBLE` 或 `CERTIFIED`；它不能由普通 research receipt 铸造。
- **sink（终端消费方）：** 真正准备让 strong status、上下界或发布结果生效的一方。
- **facet（独立维度）：** 不相互蕴含的状态轴，例如“已实现”“已验证”“已授权”“已激活”必须分别记录。
- **U/L update（上界／下界账更新）：** 改变“更优解不存在”的上界账或“某个值确实可达”的下界账。
- **`EXPIRED_BLOCKED`：** 控制面状态，只表示一项能力迁移逾期未获批准，不把数学对象判成不可行。
- **SLA（裁决时限）：** 一项边界事件由谁接单、在什么期限内裁定、逾期挡什么。
- **typed measurement state（类型化测量状态）：** 区分测得零、未测、删失、作用域必零和传感器未验证，禁止把它们都写成 0。
- **identity/event substrate、append-only、projector：** 共享稳定身份与只追加事件，再由确定性投影器生成只读视图；“只读投影”本身不授予 authority。
- **coupling / rehydrate（耦合／重新激活）：** 资产与未来用途之间的已知连接，以及冷档案重新进入活跃候选、重验并建消费合同的过程。
- **corpus、censoring、Phase -1：** corpus 是冻结实验样本集；censoring 是预算结束前没有终态的删失；Phase -1 是工作线 G 的局部证据阶段，不代表推理外环立项。
- **lifting（判词提升）：** 把一个局部对象空间里的判词搬到更宽对象空间或更强结论，例如把 binding 局部不可行提升成布局级全局 cut。

## 总览

| # | 事项 | 状态 | 与既有事项的关系 |
|---|---|---|---|
| 1 | 项目级概念命名与 v1 投影迁移 | 待裁 | 属三面审计线的后续投影事项；求解面方法论只提供“必须有稳定 successor”的一般先例[^tri-plane-a12][^roadmap-a14] |
| 2 | 第一条 W0 lowering canary | **已裁** | owner 原话、执行侧授权存录与派生边界件三者分责记录[^owner-signal][^w0-authorization][^canary-addendum] |
| 3 | 后续 research canary 的常设代码落位 | 待裁 | 现行登记只约束第一条 canary；是否常设化是本项首次上桌[^roadmap-g] |
| 4 | research receipt 顶层协议何时强制 | 待裁 | 与既有形态/凭据 checker 硬门请求及 PASS 限界挂账并联，不重复请求旧 checker 改造[^owner-summary][^plane-findings] |
| 5 | theorem registry 的物理家址 | 待裁 | 非冻结派生目录已经获准存在；本项一经裁定会激活既有 theorem-registry 对齐条件项[^owner-summary][^theorem-debt] |
| 6 | research feedback 与 certified cut framework 是否合流 | 条件待裁 | 已有触发器键控条件项，本请求只确认触发前默认关系[^roadmap-g] |
| 7 | capability token 的正式枚举与授予者 | 待裁 | 新项目级事项；首号金丝雀已经暴露开放 token 与收据自铸问题，需作为验收样本[^canary-token-gap] |
| 8 | 跨域边界事件的裁决期限与紧急停用条件 | 待裁 | 固定事件格式与 BLOCK/NO_EFFECT 语义已由方法给定；本项只裁 SLA、接单人和是否停现有边[^open-debt][^canary-addendum] |
| 9 | 常设闸的吞吐成本与复审阈值 | 待裁 | 与既有代码埋点请求并联；运行时成本数字依赖该埋点先获准[^owner-summary][^instrument-debt] |
| 10 | 一库三账一流水的项目级落地 | 待裁 | 与 theorem registry 家址、既有对齐债和档案面表示分类裁定权存在顺序依赖[^theorem-debt][^archive-interface] |
| 11 | `TYPED_OPTION` / `UNTYPED_ARCHIVE` 准入边界 | 待裁 | 新项目级资产维护事项 |
| 12 | 预注册的项目级适用范围 | 待裁 | 工作线 G 已有局部纪律；本项只问是否推广及推广到哪些实验[^roadmap-g] |
| 13 | 作用边组合与 lifting 的路径级义务 | 待裁 | 新设计洞；逐边合规不自动推出多边路径合规 |

## 1. 项目级概念命名与 v1 投影迁移

**问题。** 本方法用“两根轴”区分语义与运行辖区：数学面、发布面、档案面是三种语义，`RESEARCH` 与 `CERTIFIED` 是运行域。需要决定这套名字只在本 dossier 内使用，还是成为项目级正式术语，并在后续受控批次更新 v1 投影。该迁移属于三面审计线的后续事项；求解面方法论的 successor 工作只提供一般维护原则，不是本项的登记宿主。[^tri-plane-a12][^roadmap-a14]

**选项。**

- **A：正式采用“三语义面＋运行域”。** 本次确认项目级术语，v1 文件与生成投影在后续受控批次迁移。
- **B：只在本 dossier 内使用。** 项目其它入口继续保留旧的“按面判符号”说法。
- **C：把研究升为第四个对等面。** 四面并列，不再单设运行域轴。主方法第 27 节已把这一做法列为明确否决；此处仍列出，是因为项目级终裁权在 owner。

**推荐。** 选 A。它保留 v1 已经站住的三面本体，又给研究一等运行、权限与维护席位；同时避免把 theorem、measurement、gate 和 archive 再装进一个内部符号相反的“研究面”。

**代价。** A 需要一个后续三面线投影迁移批，更新术语入口、v1 关系说明和索引；B 会长期产生两套翻译；C 最省一次迁移，但会重新制造本方法要解决的分类污染。

**请裁：** A / B / C。裁决前，v1 的按面符号判据仍是项目现行表述，v2 只在本 dossier 内适用。

## 2. 第一条 W0 lowering canary

**状态：已裁，不再请求。**

**原问题。** 是否允许已经证明的 W0 一元 theorem 在研究沙盒中真实 lowering 一次，并做 on/off 测量。

**owner 2026-08-16 09:14 裁定原话：**

> 先开吧,不过我想着先开一个,然后剩下一个空位交给右边,开了之后你再好好跟我讲一下这个v2战役

该原话、跨会话转达链和窄效力由本 dossier 的逐字存录承载；执行侧授权存录保存同一次授权的执行简报，发射前增补则是派生边界件。三者不互相替代。[^owner-signal][^w0-authorization][^canary-addendum]

**授权语义。** 只解冻实验闸内的一次活动：在 `RESEARCH` 运行域沙盒中，对固定 W0 theorem 做一次静态 lowering baseline/treatment 测量。它不是推理外环立项，不解锁通用 D3 family compilation、通用 D4 holdout A/B、theorem registry 常态化、certified cut 合流或其它待裁事项；也不得外推跨布局／跨矩形／跨 theorem 的家族普遍性，不得改写 certified-exact U/L，不得启用 production default，不得触碰 strong status、supervisor、publisher、认证或公开发布面。执行侧真源的完整冻结面优先于本段摘要。[^w0-authorization]

**“右边”与尾句的指向。** owner 原话没有具名“右边”。按落地线转达与 owner 后续在本线的知情使用，它指本三面审计线；该解释不冒充 owner 原话的一部分。尾句的受话人是落地线，指其自身的 v2 战役汇报义务；落地线已于 09:19 交付六节讲解。该尾句与本线窄授权无关，也不是在指本 dossier 的三面模型 v2。完整事实链见窄存录。[^owner-signal]

**执行建议。** 严格按窄授权运行。本项无需再选 A/B/C。

**代价。** 只占用一个 research canary 席位；结果最高支持固定 context 内的真实消费测量，不购买家族普遍性、全局面貌或整线立项。

## 3. 后续 research canary 的常设代码落位

**问题。** 第一条 W0 canary 的 lowering、度量和收据已经被限定在 research dossier，触碰 tracked `src/` 即成为边界事件。这只是第一条 canary 的实例红线，不是项目级常设规则。后续出现第二、第三个同型 canary 时，需要决定代码长期住在哪里，并同时考虑共享 `.artifacts/`、checkpoint、环境配置和进程缓存等非 `src/` 影响面。[^roadmap-g]

**选项。**

- **A：canary 阶段一律留在 research dossier。** research 可以读取 certified 真源，certified 不反向 import research；共享可写状态另行显式隔离。
- **B：允许一个独立、明确 noncert 的 tracked code 子树。** 等 2 至 3 个同型实例后再建立，仍与 certified source、loader 和写权限隔离。
- **C：直接进入 certified `src/`，靠 default-off flag 隔离。** 主方法第 27 节已明确否决这一做法；此处仍列出，是因为项目级终裁权在 owner。

**推荐。** 当前选 A，并保留“家族性通过后重新上桌 B”。不选 C。default-off 是配置，不是结构隔离；它会提前扩大 source digest、测试、重构与误启表面。

**代价。** A 可能有少量 research harness 重复，并需要显式隔离共享可写根与缓存；B 需要新增代码分类、loader、source-boundary 和 context-fingerprint 契约；C 初期接线最省，但把实验债提前压进认证面。

**请裁：** A / B / C。

## 4. Research receipt 顶层协议何时成为强制门

**问题。** 可跨组件消费的 research receipt 是否必须从裸 `PASS` 升级为八字段 envelope：`result_kind`、typed `outcome`、`subject_identity`、`verified_scope`、`authority_basis`、`granted_effects`、`non_implications`、`contract_identity`。既有请求已经在问“形态/凭据 checker 何时进入硬门”，三面线也已把旧 PASS 限界修改挂在自然触发批；本项不重复请求那三只旧 checker 的 reseal，只决定新 theorem pipeline 的适用范围与回扫策略。[^owner-summary][^plane-findings]

**选项。**

- **A：立即覆盖全部历史 research checker。** 先全仓回填，再允许任何新消费。该选择会实质预决既有“先 advisory、后转硬门”的请求，并使旧 PASS 限界的 Chain B/C 顺走触发器失效，需 owner 一并确认撤销原排程。[^owner-summary][^plane-findings]
- **B：新 theorem pipeline 的顶层 receipt 立即强制；通用 schema 等 2 至 3 个同型实例后结晶；历史 checker 只在首次跨组件消费或自然触发批次回扫。**
- **C：长期 advisory。** receipt 可以继续输出裸 PASS，只要求文书加免责声明。主方法第 27 节已明确否决这种做法；此处仍列出，是因为项目级终裁权在 owner。

**推荐。** 选 B。它立刻守住新作用边，又避免在首例形状尚未稳定时冻结一套错误的全仓 schema。内部不可跨组件消费的子检查项无需统一改词。

**代价。** B 要增加 admission wrapper 和 consumer 解析；历史回扫会形成触发器债，但不会一次性征收全仓迁移税。A 最整齐但成本最高且改变两笔既有排程，C 成本最低但不能阻止程序只读 `status == PASS`。

**请裁：** A / B / C。若选 A，请同时确认预决既有硬门请求并撤销旧 PASS 修改的顺走触发器；若选 B，视为与既有硬门请求并联执行，不另开重复请求。

## 5. Theorem registry 的物理家址

**问题。** owner 已接受 `rules/derived/` 作为非冻结派生层，但这只批准该目录存在，不等于未来 theorem registry 必须直接住进去。已有条件项要求：一旦常态消费获准或任何 registry 实例化提案出现，research registry 要与非冻结派生层的状态机、指纹、currency 和 `_authority` 头对齐，或说明分叉理由。本项本身已经命中“registry 实例化提案出现”这一触发器；一经裁定，必须同时给该条件项指派负责人和到期日。第一条 W0 canary 的窄授权明确不允许在 canary 内实例化常态 registry。[^theorem-debt][^w0-authorization]

**选项。**

- **A：直接把 theorem registry 建在 `rules/derived/`。** 共用条目类型与状态机。
- **B：建立独立 research theorem registry，但复用 `UNREVIEWED / ACTIVE / STALE / PROMOTED`、premise fingerprint 与 currency 形态。**
- **C：暂不决定任何 registry。** 每个 theorem 继续留在各自 dossier；出现第二至第三个同型 theorem/consumer 后再上桌。

**推荐。** 原则上选 B，物理路径等第二至第三个同型 theorem/consumer 出现后再定。这样既保持研究运行域独立，又避免另造一套状态词。第一条 W0 canary 不应为了单例提前建全局 registry。

**代价。** B 多一个 projector/索引层；A 最省重复，但容易让“派生规则条目”与“可执行 research theorem”被误读成同一 authority；C 初期零成本，长期会失去 consumer reverse index 与统一 currency。A/B 的任何落地都必须支付既有对齐条件项的负责人、期限和关闭证据成本。

**请裁：** A / B / C，或“先裁 B 的分离原则，路径延后至 2 至 3 个实例”。若不选 C，请同时指定既有对齐条件项的负责人和到期日；本裁决本身不扩大第一条 canary 的授权。

## 6. Research feedback 与 certified cut framework 是否合流

**问题。** research theorem lowering 与 typed cut 都会剪枝，但它们当前的 authority、生命周期、consumer 和威胁模型不同。工作线 G 已把合流登记为触发器键控事项：只有第三层家族普遍性通过，或出现“定理进认证路径”提案，才重新裁。[^roadmap-g]

**选项。**

- **A：现在合流。** research theorem 直接复用 certified cut registry/lifecycle。
- **B：现在两套设计，复用 typed lowering、独立 verifier、sink promotion 等原则；触发条件到达后再裁是否共享 production registry。**
- **C：永久禁止合流。** 即使将来进入认证，也保持完全独立实现。

**推荐。** 选 B。它不提前购买 production authority，也不关闭未来复用的期权。

**代价。** B 在研究期会有少量重复合同；A 接线最快但可能把 research PASS、shadow 和 certified attach 混成一条生命周期；C 边界最硬，但将来可能重复成熟的 typed infrastructure。

**请裁：** 当前确认 B 为触发前默认，还是提前改成 A/C。若维持 B，本项只确认既有条件项，不重复请求后续 promotion。

## 7. Capability token 的正式枚举与授予者

**问题。** “已实现”“已验证”“获准实验”“获准生产”不是一根线性等级。项目需要决定机器准入究竟认自由文本、四层标签，还是认精确的 capability token，并明确 production 与 certified 是否分开、每种 token 由谁授予。

**选项。**

- **A：只保留四层 authority 标签。** `IMPLEMENTED / VERIFIED / AUTHORIZED_FOR_EXPERIMENT / AUTHORIZED_FOR_PRODUCTION` 逐级解释。
- **B：四层仅作人类投影；机器使用独立 facet 与闭合 token 集。** 候选词表包括 `RESEARCH_OBSERVATION`、`RESEARCH_MODEL_PRUNING`、`PRODUCTION_NONCERT_TELEMETRY`、`CERTIFIED_MODEL_PRUNING`、`UPPER_LEDGER_UPDATE`、`LOWER_LEDGER_UPDATE`、`TERMINAL_STATUS_MINT`、`PUBLICATION`、`OWNER_DECISION`；`OWNER_DECISION` 只能由具名 owner 闸持有，普通边不得请求。
- **C：每份文书自由写 allowed usage。** 不建统一枚举。

**推荐。** 选 B，并把 production 与 certified 分开。它能表达“实现了但没验证”“获准 research observation 但没获准 pruning”“允许 production telemetry 但不允许 certified effect”等真实组合。

**代价。** B 需要 schema、issuer 与 admission checker；A 实现便宜但会把 implementation、verification、production 与 certified 混成一根刻度；C 最灵活但机器无法可靠拒绝越权。首号金丝雀已经是已知回扫对象：现行 envelope 接受任意字符串 token，authority source 路径不带 digest，contract checker 的 PASS receipt 自铸状态 token，FAIL receipt 仍带非空 `granted_effects`。正式机制必须把这些行为改成“闭合词表、authority source 绑定 digest、FAIL/INVALID grant 为空”。[^canary-token-gap]

**还需一并裁定。**

1. production 与 certified 是否正式分开；
2. 谁可以授予 research token；
3. 谁可以授予 certified token；
4. U/L update、strong-status mint、publication 与 `OWNER_DECISION` 分别由哪个具名 sink 或 owner 闸独占。

**请裁：** A / B / C，并回答四个子问题。

## 8. 跨域边界事件的 SLA 与紧急停用条件

**问题。** 主方法已经固定边界事件的十二字段格式，也已区分 `EXPIRED_BLOCKED` 与数据面的 `NO_EFFECT`。本项不再裁格式，只裁：谁接单、deadline 如何设、逾期是否只挡新迁移，以及什么完整性证据允许立即停用一条已经获准的现有边。首号 W0 canary 的冻结增补已经给出局部先例：`EXPIRED_BLOCKED` 不停掉已明确获准的 baseline research。[^canary-addendum]

**选项。**

- **A：不设项目级时限。** 每项等待 owner 自然处理，仍保留固定事件格式。
- **B：设固定或按类别的 deadline；逾期只进入 `EXPIRED_BLOCKED`，阻断 requested transition，不影响原有已授权边。**
- **C：采用 B，并增加紧急停用现有边的条件。** 只有出现 theorem/contract identity 破坏、stale premise 仍在生效或认证资产越权写入等完整性证据时，才立即停用当前边。若 C 回溯适用于已经冻结的 W0 canary，必须另走协议修订，不能静默改变现有保证。[^canary-addendum]

**推荐。** 选 C，但只对未来事件立即生效；是否回溯修改首号 W0 canary 单独明示。常态逾期只挡新能力，明确完整性事件才停现有边。

**代价。** C 需要事件分类、接单人、deadline、emergency criterion 和既有协议的回溯边界；B 更简单，但遇到真实越权时还需临时解释；A 零流程成本但会制造无期限悬挂。

**请裁：** A / B / C；指定默认 deadline、接单角色，并说明 C 是否回溯适用于已冻结的 W0 canary。

## 9. 常设闸的吞吐成本与复审阈值

**问题。** 常设闸会保护 soundness 或 authority，也可能长期消耗墙钟、人时和研究队列。既有请求仍在等待 owner 决定是否承认生产代码中的有限埋点；开放欠账也规定没有观测点时不得写“拒绝率为 0”。本项不重复请求“要不要埋点”，而是决定每个常设闸是否必须交成本账、何时复审。[^owner-summary][^instrument-debt]

**选项。**

- **A：只写定性成本。** 例如“低”“可接受”。
- **B：必填保护对象、单位成本、运行成本、人类队列成本、typed measurement state、误挡率和复审触发器；不自动关闭 soundness 闸。** 运行时字段以既有埋点请求获准为前提；若埋点未获准，必须按开放欠账写“无埋点＋欠账号”，不得伪造 0。
- **C：在 B 基础上设自动 sunset。** 超过阈值或长期无收益时自动停用。

**推荐。** 选 B。成本必须可见，但是否换方案、加资源、降低频率或继续承担应由 owner 裁，不由一个效用阈值自动撤掉 soundness 防线。

**代价。** B 需要埋点和周期性复算；若旧埋点请求未获准，只能先维护 typed gap。A 容易让临时退守永久化；C 自动化最强，但会把 utility 与 soundness 再次混成一根开关。

**请裁：** A / B / C。建议先裁既有埋点请求，再裁本项 B 的运行时必填范围；本项作为既有埋点请求与开放欠账的增量验收，不另建重复埋点债。

## 10. 一库三账一流水的项目级落地

**问题。** 需要决定是否把现有 knowledge ledger、`rules/derived/`、未来 theorem registry 和 option registry 纳入同一套规范化 identity/event 架构，再由 projector 生成知识、能力、期权三本只读视图。该问题依赖第 5 项先明确 theorem registry 的分离原则或家址，也命中既有 registry 对齐条件项；若需要扩展知识表示分类，还必须服从档案面批保留的 `representation_class` 裁定权。[^theorem-debt][^archive-interface]

**选项。**

- **A：直接扩展现有 knowledge ledger，让一份记录同时承载全部知识、能力、期权与流水。**
- **B：共享稳定 identity 与 append-only event，authority 真源继续分离；知识、能力、期权是三本只读投影；实验只追加 `(cost, Δknowledge, Δcapability, Δoption)` 流水。先用 theorem canary 做小范围 pilot。**
- **C：不统一。** 各研究线继续在 dossier 内自由记账。

**推荐。** 选 B，但在第 5 项确定 registry 分离原则以后再启动 pilot。它共享身份而不合并 authority，延续“记录位置与认识论权威正交、projection 不自铸 authority”的治理原则。

**代价。** B 需要事件 schema、projector、迁移、视图新鲜度检查和档案面表示分类协调；A 文件少但会形成全能大对象；C 初期便宜，跨线查询、失效传播和期权复用会继续靠人工。

**请裁：** A / B / C。若选 B，只批准 pilot 与接口，不在第一条 canary 前建满全局系统；执行顺序为第 5 项先、本项后。

## 11. `TYPED_OPTION` 与 `UNTYPED_ARCHIVE` 的准入边界

**问题。** 有些研究成果自身成立，但今天尚未发明能看见其未来价值的抽象。若要求它们立即找到 consumer 或删除，会杀死新概念；若所有东西都以“未来可能有用”进入活跃扫描，又会制造无限维护债。

**选项。**

- **A：不设冷档案。** 没有当前 coupling 的成果退役或删除。
- **B：低使用率成果都可进 `UNTYPED_ARCHIVE`。** 不设反债务洗白限制。
- **C：两层登记。** `TYPED_OPTION` 有已知 coupling、context、trigger、维护成本和主动扫描；`UNTYPED_ARCHIVE` 只保存原身份、原 context、proof/evidence 和非蕴含边界，不承担当前 currency。准入检查按 canonical asset 汇总全部 condition records，任一记录仍有 consumer、阻断、到期义务或现行 claim 依赖，整个资产都禁止转冷。

**推荐。** 选 C。重新使用冷档案时，必须新建 `TYPED_OPTION`、按当前 context 重验、建立消费合同并重新申请 capability。

**代价。** C 需要冷档索引、资产级义务并集和 rehydrate 流程；A 会丢未来期权；B 会把真实债务藏进冷库。

**请裁：** A / B / C。

## 12. 预注册的项目级适用范围

**问题。** 审计线已经明确不普遍强制预注册，但工作线 G 的 Phase -1 这类 go/no-go 实验需要在开跑前冻结 corpus、预算、censoring 状态和阈值。需要决定这种纪律是否推广，以及推广到哪些实验。现有要求只覆盖该线，不等于项目级普遍规则。[^roadmap-g]

**选项。**

- **A：所有 research 实验统一预注册。**
- **B：按实验作用分类。** 因果 on/off、go/no-go、高预算 campaign、会支撑 promotion 的实验必须预注册；探索性探针和纯发现实验不强制，但不得事后冒充确认性证据。
- **C：项目级不要求预注册。** 完全由各线自由决定。

**推荐。** 选 B。它把防结果后改阈值的成本放在真正需要因果或准入解释的实验上，不让审计线变成所有探索工作的审批队列。

**代价。** B 需要在实验出生证中先判作用类型；A 最统一但研究节拍最慢；C 最自由，但确认性结论的可采纳性需要每次重新争论。

**请裁：** A / B / C。若选 B，视为扩展 Phase -1 的既有局部纪律，而不是由三面审计线接管实验选题。

## 13. 作用边组合与 lifting 的路径级义务

**问题。** v2 当前能逐条检查验证边、引用边、执行边、测量边和晋级边，但“每条边分别合规”不自动推出整条路径合规。局部 binding 判词可能被 lift 成布局级 cut；一条持 research pruning token 的边产出结果，另一条持 ledger-update token 的边再把它读成强证据，两条局部权限可能复合出没有任何单边获准的更强作用。需要决定由谁、用什么关系裁断路径。

**选项。**

- **A：只保留边局部义务。** 路径风险由人工 first-of-kind 审计兜底，并明确承认没有机器闭包保证。
- **B：引入第六类“lifting 边”。** 凡把判词搬到更宽 `object_space` 或更强 `claim_channel`，必须单独取得出生证，并附 transport 证明；transport 缺失时 `NO_EFFECT`。
- **C：引入路径级 grant 闭包检查。** 沿路径的 `requested_effects`、对象空间变化和 claim-channel 提升必须被一个具名 path grant 覆盖，不能由单边 token 并集自行合成。

**推荐。** 选 B。它先把最危险、最可识别的“局部判词提升”变成显式对象，代价与现有代码模式相称；等出现 2 至 3 条真实 lifting 路径后，再判断是否需要 C 的通用路径闭包机制。

**代价。** B 让每条 lift 多一份 transport 证明、独立负例和出生证；A 最省成本，但路径越权只能靠人发现；C 覆盖最全，但需要定义 token 组合代数和路径枚举，过早落地可能把首例偶然形状冻结成全局框架。

**请裁：** A / B / C。若暂不裁，任何 research 判词首次被上层 lift 或跨对象空间复用时必须停在 first-of-kind 人工审计，不得从逐边 PASS 推出路径 PASS。

## 建议的裁决顺序

先裁 1、3、4、7、8、13，它们决定术语、边界、receipt、capability 与路径义务的最小骨架。其中既有生产代码埋点请求应先于第 9 项；第 5 项应先于第 10 项。再裁 5、6、9、10、11、12，它们决定规模化后的家址、合流、成本和资产组合。第 2 项已经关闭，不占本轮选择。

---

[^tri-plane-a12]: `docs/项目说明/ROADMAP.md:89-94`。A12 是三面防污染架构审计的现行挂账入口；项目级 v1→v2 投影若获准，应由该线或其后继宿主认领。
[^roadmap-a14]: `docs/项目说明/ROADMAP.md:103-108`。A14 管求解面方法论载体与 successor，只提供“方法论本体须有稳定 successor”的一般先例，不接管三面治理术语迁移。
[^roadmap-g]: `docs/项目说明/ROADMAP.md:61-69`。工作线 G 仍是“未立项/概念收敛”；其条件项分别登记外部 witness、research feedback/certified cut 合流与第一条 static lowering 的 `src/` 红线。
[^owner-summary]: `docs/research/rule_system_redesign_20260807/OWNER_DECISION_SUMMARY.md:8,24-28`。第 4 件已接受 `rules/derived/`；第 5、6、7、8 件仍逐项待裁。
[^plane-findings]: `docs/research/plane_mixing_audit_20260813/FINDINGS.md:7-16`。D1 登记旧 PASS 文案缺少“不证什么”，其修改按 Chain B/C 自然触发批顺走。
[^theorem-debt]: `docs/research/rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md:31-33,174-182`。`OD-B1-THEOREM-REG-01` 是 registry 实例化后必须激活的形态对齐条件项。
[^open-debt]: `docs/research/rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md:10-16`。逾期不自动判假，只激活声明的阻断范围。
[^instrument-debt]: `docs/research/rule_system_redesign_20260807/batch0_20260815/OPEN_DEBT_LEDGER.md:96-107,194`。代码实施仍等待既有埋点请求裁定；无埋点不得写真零或误挡率为零。
[^archive-interface]: `docs/research/rule_system_redesign_20260807/OWNER_DECISION_SUMMARY.md:6-8`。档案面批保留 `representation_class` 扩类裁定权，并要求知识登记面不自铸 owner authority。
[^owner-signal]: [`OWNER_SIGNAL_20260816.md`](OWNER_SIGNAL_20260816.md) 保存 2026-08-16 09:14 的完整 owner 原话、落地线→跨会话同步→本线的转达链、“右边”的准确解释、09:19 已履行的落地线战役汇报义务与本线窄效力边界。
[^w0-authorization]: `docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/00_OWNER_AUTHORIZATION_20260816.md:1-24`。这是执行侧授权存录；其中引用的是落地线向执行席发出的简报转述语，不是 owner 逐字原话，并列出完整未授权事项。
[^canary-addendum]: `docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md:37-64`。该派生边界件冻结 `EXPIRED_BLOCKED / NO_EFFECT`、research dossier 边界和一次静态 W0 lowering on/off 的授权语义。
[^canary-token-gap]: `docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/03B_RECEIPT_ENVELOPE_SCHEMA_V1.json:33-60`、`w0_canary_receipt_contract.py:80-101`、`06_check_w0_unary_lowering_contract.py:548-609`。现行 schema 只保证字段存在，token 为开放字符串，authority source 未绑定 digest，FAIL receipt 仍带非空 grant。
