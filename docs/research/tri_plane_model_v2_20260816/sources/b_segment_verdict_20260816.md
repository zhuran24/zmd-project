<!-- 原始评审材料：落地线 B 段对撞席裁断全文（浏览器渲染层逐字提取，不作编辑） -->
<!-- 来源：ChatGPT 对话「分支 · 项目分析与架构问题」 conversation 6a812b53-f214-83ea-9c49-7085a0bf1cda（落地线分支席） -->
<!-- 模型：GPT Pro；席位性质：**非盲**对撞席——自三轮数学评审后分支、承载完整项目语境，对落地线 A 段盲席盲答×落地线草案做知情对撞裁断；其价值在「知情对撞」，与两个盲席（本 dossier 盲问席、落地线 A 段全新窗口盲席）互补 -->
<!-- 交付日期 2026-08-16；提取方式=DOM innerText 只读；原消息 markdown 结构（标题/列表）已扁平为换行 -->
<!-- 纯文本 SHA-256：3f1917e9fc88f0dfe9bc8aa1647f45be51c8b3c560718d89cc72db98fb8bc1cc（12,265 字） -->

我先给总裁断：

盲答不是在你们四条草案外面补了几句，而是补上了一整层“时间认识论”。
你们原草案更像一套研究资产治理和机器化失效系统，擅长回答“怎么登记、怎么保存、怎么重估”；盲答则先追问“这类东西到底是什么，它现在有没有语义，执行动作能不能被库存”。

两边合起来之后，完整框架不应是“未来价值管理”，而应是：

把中间产物的事实成立性、当前能力贡献、条件期权、执行时机和历史决策质量分开管理，再用机器可见的条件边把它们重新连接。

其中最重要的修订是：

你们的“现在为零就写零”需要改成“现在是什么语义状态就写什么状态”。
ZERO、ZERO_BY_SCOPE、N/A、UNKNOWN、CENSORED 不是一回事。

一、差异清单
1. 盲答真正看见了什么
A. 它首先把“中间产物”拆成了资产与事件

盲答的四个动词：

建立；

使能；

检验；

监测。

这不是普通分类，而是在区分两种时间对象：

可库存的状态与只能在特定时点发生的事件.

证明、定义、程序、装置设计，可以作为状态保留。

某次 A/B、某次干预、某个时刻的监测结果，则是带上下文和时间的事件，不能因为未来对象终于出现，就自动获得当时不存在的证明力。

这点是你们四条草案没有显式看见的。

但它不能被理解成“测试相关的一切都不能库存”。更精确的说法是：

测试装置、协议、fixture、原始日志和校准材料可以库存；不能提前库存的是一项尚无语义对象的检验结论，或者把一次历史事件的证据效力搬到后来才出现的问题上。

B. 它纠正了“所有当前作用为零都是同一种零”

至少要区分：

状态	含义
ZERO_MEASURED	对象、干预和指标都存在，确实测得零差分
ZERO_BY_SCOPE	根据作用域可证明该产物不可能改变这本账
N/A_NOT_READY	对象、消费者、干预或测量语义尚不存在
UNKNOWN_UNMEASURED	有定义，但没测
CENSORED	测了，但预算或观察窗没有给出目标判词
SENSOR_UNVALIDATED	打印出了数字，但尚未证明 evaluator 真能响应变化

这会直接修正三件事：

W0 定理当前对 certified 上下界的贡献不是模糊的“零”，而是 ZERO_BY_SCOPE；

Phase -1 旧门的终局信息是 CENSORED，不是零；

一个尚未做敏感性自检的终点指标，即使长期打印 0，也应先标 SENSOR_UNVALIDATED。

C. 它引入了“终局相关性”和“语义就绪性”的双链

盲答实际上定义了两个方向：

终局义务⟵贡献链⟵中间产物

以及：

当前状态⟶所需对象、消费者、干预、测量通道是否就绪.

两条链的交集才是“现在执行”。

只满足终局相关性，进入期权库。

只满足技术就绪性，则是已经能做，但研究上没有理由做的忙碌。

这个“双向交汇”比单独写激活触发器更完整。

D. 它补出了决策敏感性门

这是盲答里最有价值、你们原草案确实没有的一项：

如果所有可能结果都会导向同一个后续动作，这个实验几乎没有决策信息价值。

也就是说，实验开跑前必须写出：

结果 A → 做什么
结果 B → 做什么
结果 C / INCONCLUSIVE → 做什么

若三行完全相同，那就不是决策性实验，最多是记录、展示或心理安慰。

这条应立即进入金丝雀协议。

E. 它补出了“为什么必须现在做”的时机门

相关、就绪、会改变决策，仍不代表必须现在做。

还需要回答：

是否存在知识流失；

输入即将漂移；

后面重建是否更贵；

是否有长交付周期；

当前是否正好有一个最小、干净的检验对象；

等到通用系统建完再测，是否会把多种原因缠在一起。

这对 W0 金丝雀尤其关键。

F. 它提出了防后见之明倒签

需要同时保留两份不同的判断：

当时做出保留或执行决策是否合理；

今天这个产物在新条件下是否变得有价值。

后来激活了，可以给资产重新定价，但不能回头改写：

“所以当年提前满预算跑是对的。”

长期没激活，也不能倒推出：

“所以当年低成本保存一定错了。”

这是历史决策质量与当前资产价值的分账。

G. 它看见了指标也需要先验“接线测试”

它没有满足于冻结指标定义，而是继续追问：

这个传感器到底会不会动？

这对终点账本是决定性的。

一个定义完全严谨的 M
t
	​

 evaluator，仍可能因为：

lex comparator 写反；

同面积 min_side 没进入第二关键字；

stale theorem 被错误消费；

NOT_REACHED 被当作 0；

重复证书被双重计数；

而变成一块雕刻精美、背后没接线的仪表盘。

H. 它把未来价值管理成期权，而不是预测

这比“未来也许有用”严格得多。

它要求：

互补项类型；

可观察触发器；

保存成本；

重建成本；

激活时机；

退场条件；

当前系统拖累；

不激活时的预算上限。

这是一种受控期权，不是无限期供养许可。

2. 你们原草案看见了、盲答没有充分处理的东西
A. 前提指纹与自动失效

盲答有人工“激活扫描”，但没有真正回答：

未来规则、输入、目标和消费者变化后，怎么防止旧条件价值继续幽灵存活？

你们的前提指纹能够做到：

premise fingerprint changed⟹conditional edge becomes STALE.

这不是文档便利，而是防止旧定理、旧期权和旧债务在新世界里继续被错误消费的必要机制。

B. 双向清账的机器化

盲答已经独立看见了手工版双向扫描：

新成果出现，扫描休眠资产；

架构变化，检查贡献链断没断。

所以“激活扫描”本身不是你方独有。

你方真正独有的是把它机器化为两条增量传播：

新节点出现
→ 哪些条件边现在满足
→ 哪些休眠资产转 READY

以及：

前提、目标或输入漂移
→ 哪些条件边失效
→ 哪些 ACTIVE / READY 资产转 STALE

它不是每次人工翻一本簿，而是依赖图上的正向激活与反向撤稿。

C. 事实冻硬、结构冻晚

盲答说“接口描述未来”，是对的，但容易进一步滑成“提前把未来 API 也设计完”。

你们原草案里的这条必须保留：

冻结命题、证据、输入身份和能力签名；不要过早冻结消费者拓扑、模块边界和生产 API。

例如 W0 应冻结：

active_output_slot(boundary_port_041)
→ no canonical routing witness

以及消费者必须能表达“一元 binding-domain 排除”。

但不应在第一号对象上就冻结完整通用 compiler 的类层级、文件布局和长期运行时协议。

事实硬，结构晚。

D. 债务的阻断范围、责任和关闭证据

盲答的激活合同更偏正向资产。

三面线与开放欠账系统还拥有几个承重字段：

负责人；

到期日或触发器；

触发后阻断什么；

关闭需要什么证据；

已登记不等于已解决；

未关闭的债务怎样污染下游结论。

这部分不能被普通“期权状态机”吞掉。

E. exact 项目特有的 lowering 与 authority 问题

盲答只说未来需要一个消费者。

项目里还必须多问：

定理本身是否成立；

consumer 是否能表达其前件；

lowering 实际拒绝集合是否超出定理授权；

context、极性与 grounding 是否一致；

这次接线是否得到 owner 实验权限；

它是否触及认证或发布权限。

这套 exact-solver 的信任边界，是盲答不可能凭一般研究语境自行补出的。

3. 你初步差异清单中需要修正的两点
“类型化耦合”不是你方独有

盲答明确说了：

用接口描述未来，不用故事描述未来。

所以双方都看见了类型化耦合。

真正差异是：

盲答把它用作期权准入与贡献链；

你方进一步要求把它做成机器可匹配、带 premise fingerprint 的激活边。

“双向清账”也不是盲答完全没有

盲答写了：

每当新发现、架构改变、终局义务修改，做激活扫描。

它有治理动作，但没有机器闭包、依赖 DAG、stale propagation 和 currency 闸。

所以差异不是“有或没有”，而是：

人工周期性扫描
vs
事件驱动的自动激活与自动撤稿
二、哪些应立即收编

我会分成“原样收编”“改造后收编”“不应字面收编”三档。

1. 原样收编

以下五项可以直接进入现行方法论：

typed null 纪律：0 / N/A / UNKNOWN / CENSORED / ZERO_BY_SCOPE 分开；

决策敏感性门；

时机优势门；

防倒签，历史决策质量与当前资产价值分开；

指标 evaluator 的合成扰动敏感性测试。

2. 改造后收编
动词四分类改成“动作 facets”，不要强迫每个产物只属于一类

W0 包里同时存在：

theorem：建立；

checker：使能；

canary：检验；

endpoint ledger：监测。

所以最好登记为：

action_facets = [ESTABLISH, ENABLE, TEST, MONITOR]

具体 artifact 各自选一个或多个角色，不做互斥枚举。

三本账采用只读投影，不建三套独立真源

盲答的三本账非常好：

已知什么；

系统现在能做什么；

为未来保留了什么分支。

但它们应从同一个规范化 registry 生成，不能各自手填。

期权预算保留，但不强求虚假的数字期望值

在深不确定研究里，不必硬算：

p×value−cost.

可以使用分级保留决策：

HOT_OPTION
WARM_OPTION
COLD_TYPED_OPTION
UNTYPED_ARCHIVE
RETIRE_FROM_MAINTENANCE

并记录成本、重建难度和 endpoint leverage，不必假装知道概率。

3. 不应字面收编
“写不出类型化耦合就不给保存资格”过严

应改为：

写不出类型化耦合，不给“已登记期权”资格；但可以给低成本冷档案资格。

否则会杀掉真正的新概念，因为有些产物的未来价值恰恰要等一种尚未发明的抽象出现后才看得见。

因此分两层：

层级	要求	待遇
TYPED_OPTION	有互补项类型、贡献链、触发器	进入主动扫描和有限维护
UNTYPED_ARCHIVE	只有内在成立性与低成本可复现包	不记未来价值、不占热维护预算，只保留供以后重索引

“不给期权信用”不等于“删除”。

三、ENDPOINT_METRICS_PROTOCOL_V1 的敏感性测试

这部分应该立即加入，而且成本应被压在纯 evaluator 级别。

核心形式是：

E:FrozenEndpointSnapshot→(L,U,B,G,M,H,F,C)

测试不调用 CP-SAT，不改真实 ledger，不碰 certified authority，只在临时 synthetic snapshot 上做已知扰动。

最小测试矩阵
合成扰动	预期反应	要抓的故障
加入一份更高分 witness	L 上升，M 只保留 lex 更优矩形	下界没接线、比较器错误
同面积加入更高 min_side witness	L 按第二关键字上升	min_side 被漏掉
排除最高 band 中一个但非最后一个矩形	B−1，U 不变	把单点排除误当 band 关闭
排除最高 band 最后一个矩形	U 降到下一 band，G−1	上界 band 切换错误
排除分数不优于 L 的矩形	M,G,U 全不变	越界计数
重复加入同一 witness 或同一 exclusion	所有量幂等	双重计数
提交 contextHash 不匹配的证书	fail-closed 或完全不消费	stale 证书污染
L=ABSENT	输出 M
⊥
，不得伪造 M	absent sentinel 偷换
把 10 秒成本从 binding 搬到 routing，总成本不变	stage share 变化，总成本不变	热点迁移未被捕获
routing 根本未到达	NOT_REACHED，不能记录为 0 秒工作量	未到达和真零混淆
删除一个一元 binding domain value	binding envelope 按冻结公式下降	残余自由 evaluator 未接线
三类控制必须同时存在
正控制

已知应该变化，确认仪表真的会动。

负控制

已知不该变化，确认 evaluator 不会把无关事件算成终点进展。

例如 W0 定理只改变固定布局 binding family，不能写 rectangle-level exclusion，所以：

ΔL = 0
ΔU = 0
ΔM = 0

应作为 ZERO_BY_SCOPE 正确输出。

stale 控制

输入身份或前提指纹变化时，旧资产必须退出计算，而不是继续贡献旧余额。

如何保证便宜

使用几十个合成矩形的小 universe；

预期值手工写死，不调用 production evaluator 自己生成 golden；

evaluator 是纯函数；

收据记录 evaluator SHA、fixture SHA、扰动 ID 和预期差分；

只有全套灵敏度通过，真实运行中的“零”才允许写成 ZERO_MEASURED 或 ZERO_BY_SCOPE。

这只能证明仪表接线和基本语义正确，不能证明账本覆盖了所有成本逃逸维度。后者仍要靠终点账的资源向量与“未覆盖维度债”管理。

四、三本账与语义／资源四格账怎么拼

它们不是竞争结构，而是两种不同会计对象。

盲答的三本账是存量表。

此前的四格账是交易流水。

最干净的架构是：

一库、三本存量账、一张四格流水
1. 一库

唯一规范化真源保存：

artifact identity；

命题和输入；

context；

premise fingerprint；

activation edges；

preservation；

authority；

experiment transaction；

closure events。

2. 三本存量账

从一库生成只读投影。

知识账

回答：

已经严格知道什么？

W0 定理完成后，这本账增加。

能力账

回答：

当前系统已经可以可靠执行什么？

W0 定理尚未 lowering 时，这本账仍为零。

金丝雀成功后，可以增加一项：

已验证的一元 theorem-to-binding lowering 能力

注意是能力增加，不是 certified bounds 增加。

期权账

回答：

哪些已验证资产等待什么互补项即可激活？

W0 定理在 canary 前是一个 typed option。

canary 成功后，它的一条期权边被激活或兑现，但定理仍可保有其他未来期权边。

3. 四格流水

每次实验记录：

	语义状态	资源轨迹
切面	family、域、reject set、lowering effect	本层调用、时间、内存
终点	L,U,B,G,M,H 与 endpoint obligation	端到端墙钟、CPU、RSS、阶段迁移

它记录的是这次动作产生的差分，不重复保存三本账的全量状态。

W0 的完整会计形状
canary 前
知识账：+1 条已证 W0 Judgment
能力账：0，尚无 lowering
期权账：+1 条 compiler canary typed option
终点语义账：ΔL=ΔU=ΔM=0
canary 成功后
知识账：不变
能力账：+1 条已验证的一元 lowering 能力
期权账：对应激活边从 DORMANT → CONSUMED/ACTIVE
切面语义：1007 family 塌缩
终点语义：仍可能完全中性
终点资源：记录净收益或成本迁移

这就不会出现：

用 theorem 数量冒充系统能力；

用 compiler 能力冒充 bounds 进展；

用 endpoint 中性否认基础能力进展。

五、把激活合同、条件价值登记、三面线债台账合成一种记录

不应建立三份表互相引用。

应建立一个带 kind 的条件事项记录，它是 discriminated union，也就是共同头部加不同类型的专用字段。

共同头部
id
subject_ids
kind
context
premise_ids
premise_fingerprint
authority
created_at
original_decision_basis
current_status
条件边

价值不是 artifact 的固有标量，而是一条关系：

{a,c
1
	​

,…,c
k
	​

}
⟶
Γ
	​

Y⟶D⟶O

其中：

a：当前产物；

c
i
	​

：所需互补项；

Γ：激活条件；

Y：产生的能力或信息；

D：改变的判断；

O：终局义务。

所以一个 artifact 可以有多条未来价值边，不需要假装提前知道完整的 Γ(a)。

每条边记录：

complement_types
activation_predicate
trigger_event
trigger_detector
contribution
decision_consequence
endpoint_obligation
保存合同
preservation_tier
frozen_bytes
self_test
environment_identity
maintenance_cost
rebuild_cost
revalidation_cost

这里必须把“重建成本”和“重新证明／重新验真成本”分开。代码重写可能便宜，重新获得证据身份可能很贵。

治理合同
responsible_role
budget_cap
due_date_or_trigger
blocking_scope
exit_condition
closure_evidence
用 kind 区分正向期权与负向债务
LATENT_ASSET

触发后：

DORMANT → READY
CONDITIONAL_DEBT

触发前可能无阻断。

触发后：

CONDITIONAL → OPEN_BLOCKING

例如现有 OD-B1-THEOREM-REG-01：

触发器：compiler organ 转入常态消费，或 theorem registry 实例化；

触发前：不阻断；

触发后：登记面未对齐就禁止声称同形态。

它与 W0 激活合同在结构上是同一种条件边，只是极性相反：

资产边满足后产生能力；

债务边满足后产生义务和阻断。

MEASUREMENT_GAP

例如：

指标已有定义，但 SENSOR_UNVALIDATED

触发器是首次作为验收指标消费；若敏感性 receipt 未存在，则变成 blocker。

这样三面线债务、休眠期权和指标接线欠账可以用同一登记系统表达，而不是三本散开的表。

六、盲答因不知项目而存在的错漏
1. “检验与监测不能库存”说得太绝对

更准确的是：

检验行为的原始事件不可重演为另一个时点的 confirmatory evidence，但协议、装置、日志、fixture、校准和原始数据可以库存。

而且旧数据以后可以被重新分析，但只能诚实标记：

POST_HOC_EXPLORATORY

不能倒签成当时预注册的 confirmatory evidence。

Phase -1 v1 就是典型例子：

对完整终局死因谱，主问题被删失；

但它仍留下 wall shape、反馈触达、局部签名和 observer-effect 材料。

不能说整次运行“后来自动有了终局证据”，也不能说它客观上“一点信息都没有”。

应按 estimand 分账。

2. “当前存在能影响指标的机制”不是指标有效性的必要条件

对进度指标而言，真实干预能否改变它很重要。

但有两种例外。

终点中性低层实验

W0 金丝雀按 scope 本来就不应改变 M
t
	​

,L,U。

这时指标有效性的证据不是“W0 让它动了”，而是：

合成扰动能让它按预期动；

W0 scope non-interference 让它正确保持不动。

护栏指标

护栏的正常目标就是不变。

其有效性来自正控制施压时能报警，而不是常态运行中一定变化。

所以应将：

metric sensitivity

与：

current intervention expected effect

分开。

3. “消费者已经存在”容易制造循环门

如果把语义就绪性解释成“生产 consumer 必须已经存在”，那么 compiler canary 永远无法开始：

要先有 compiler，才能测试要不要造 compiler。

正确的就绪定义是：

承重语义对象、干预对象、反事实、检查条件和最小 test scaffold 已能被明确实例化。

不要求最终生产器官已经建好。

W0 已具备：

已证 theorem；

固定 context；

单原子 trigger；

独立 checker；

现有 binding consumer 词汇；

可写的 lowering correctness contract；

on/off 反事实。

所以语义就绪。

4. “可被多种未来路线调用”不应成为硬准入

这是一个固定实例的 exact optimization 项目。

有些中间产物即使只使用一次，也可能：

关闭最高 lex band；

抬高一次下界；

打通唯一认证链；

验证一个承重器官；

消灭一个深枚举墙。

多次复用不是唯一价值来源。

应把“复用广度”与“终点杠杆”并列：

Option Merit=reuse breadth+endpoint leverage+decision leverage.

W0 theorem 跨布局复用尚未建立，但作为编译器官的第一个定义件仍可能有很高决策杠杆。

5. 单一状态机过于线性

同一个 artifact 可以同时：

在 W0 context 下已验证；

在另一个 layout 下不适用；

在当前 solver 中休眠；

在未来某个 compiler context 下 ready；

在旧规则版本下 stale。

所以状态必须是 context-indexed：

state(a,c).

不能给 artifact 一个全局“已激活”标签就结束。

6. 它遗漏了 lowering 可能比定理更严

“消费者存在”还不够。

必须验证：

RejectSet(L
J
	​

,c)⊆AuthorizedRejectSet(J,c).

否则 theorem 正确、编译错误，仍会产生假排除。

7. 它遗漏了 authority

技术上可执行、数学上正确，也不等于：

已获实验授权；

可默认开启；

可进入 certified path；

可改变发布面。

所以能力账必须至少分：

IMPLEMENTED
VERIFIED
AUTHORIZED_FOR_EXPERIMENT
AUTHORIZED_FOR_PRODUCTION

这些状态不能压成一个“系统能做”。

8. 它仍然有一点“已知接口类型”的视角偏置

未来有用性有时不是等一个已知类型的消费者，而是未来发明了一个新概念，使旧产物突然获得新解释。

因此 typed activation graph 只能表示当前已知的价值下界：

Γ
known
	​

(a)⊆Γ
true
	​

(a).

没有已登记 activation edge，不等于永远无价值。

这就是为什么仍要保留一个低成本 UNTYPED_ARCHIVE 层。

七、金丝雀与“为表演价值而强行集成”的分界

我建议把下面这条直接作为可引用判据。

最小决策性接线判据

只有当接线是回答一个已冻结、会改变下一步决策的反事实问题所必需的最小可逆干预时，它才是实验；若接线完成本身就是成功，或者所有可能结果都导向继续同一路线，它就是价值表演。

展开为六项：

对象已存在
theorem、固定 context、触发器和待检消费位置已经明确。

反事实已冻结
baseline 与 treatment 只差声明的 lowering，不是 treatment 顺手换了算法、预算和数据。

结果会改变决策
至少一个阳性、一个阴性和一个删失结果分别对应不同后续动作。

接线是最小且可逆的
局部、default-off、research-only，不顺带建通用平台，不触碰认证与发布权限。

成功不以“接上了”为定义
必须看到冻结可观测量的因果差分，而不是只看到路径执行。

失败有真实退出含义
若无论结果如何都说“至少说明值得继续”，那么实验没有决策敏感性。

还有一个很实用的自测：

把报告里的“已经集成、已经接入、路径已打通”全部删掉，剩下的结果还能回答一个非平凡问题吗？
不能，就是表演性接线。

W0 金丝雀为什么不会被这条错杀

它的目的不是证明：

W0 theorem 看起来有用。

它要回答的是：

一个已经独立证明的一元 Judgment，能否被 sound 地编译到真实 binding consumer，并因果性地消灭它授权的重复工作，而不越权、不把代价藏到别处？

四道门全部有答案。

终局相关性

它验证器官⑤编译和器官⑥测量，这两者是推理外环最终能否存在的必要能力。

语义就绪性

已有：

W0 theorem；

独立 checker；

固定 context；

一元 trigger；

现有 point-nogood consumer 路径；

可定义的 on/off。

决策敏感性

至少有这些不同结局：

结果	后续决策
lowering sound、family 塌缩、成本可控	允许考虑下一号 theorem 或 family canary
sound，但无实际塌缩	consumer 位置或触发器表达有误，停止宣称真实消费
family 塌缩，但总代价严重回归	修订编译位置或暂缓扩线
无法在不越权的情况下表达	当前 consumer vocabulary 对此类 theorem 不适配
结果删失	不升级判词，重新设计小协议或里程碑轴

不是所有结果都导向“继续建通用 compiler”。

时机优势

现在已经出现第一条钉死、可独立复算、触发器极小的 theorem。

此时不做窄 canary，反而等到通用 compiler 建成后再测，会把：

theorem soundness；

lowering；

registry；

runtime pipe；

family generality；

endpoint metrics；

全部缠在一起，失去判决力。

最小可逆性

只要协议保持：

W0-local；

unary constraint；

default-off；

research-only；

no D3/D4 generic promotion；

no certification surface；

它就是最小接线，不是强行把休眠资产拖进热路径长期供养。

但金丝雀成功的定义必须保持窄

它可以证明：

W0 theorem → lowering → real consumer → causal local effect

它不能证明：

通用 family compiler 有用；

跨布局普遍性；

M
t
	​

 已变化；

certified exact 更接近闭合；

终点收益超过长期维护成本。

所以它是能力账激活实验，不是终点进展实验。

最后压缩成可以交 owner 的结论

盲答最重要的新贡献不是“期权”两个字，而是把中间产物分成了可库存资产与上下文事件，并把 0 拆成了 ZERO / N/A / UNKNOWN / CENSORED / ZERO_BY_SCOPE。它还补出了决策敏感性、时机优势、指标接线自检和防后见倒签，这些都应立即收编。

你们原草案不可替代的部分，是 premise fingerprint、自动激活与自动撤稿、事实冻硬结构冻晚，以及 exact 项目所需的 lowering、authority、阻断范围与关闭证据。

统一形态不是再建三本独立台账，而是：

一个规范化成果／义务 registry，三本存量投影，知识、能力、期权；每次实验另写一张“切面／终点 × 语义／资源”的四格交易流水。

激活合同、条件价值和三面线欠账则合并成一种“条件事项记录”：

正向资产在触发后变 READY；

负向债务在触发后变 BLOCKING；

前提指纹漂移使二者都能自动 STALE；

同一真源生成期权视图、欠账视图和消费者视图。

最后，“不要为证明有用而强行集成”不能作为杀死金丝雀的口号。正确边界是：

为展示存在感而接线，禁止；为制造一个预注册、决策敏感、最小可逆的因果反事实而接线，正是研究。

W0 金丝雀属于后者。
