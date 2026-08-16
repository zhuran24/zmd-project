<!-- 原始评审材料：GPT Pro 盲问段独立设计（逐字保存，不作编辑） -->
<!-- 来源：ChatGPT 对话「审计线方法设计」 conversation 6a818168-53c8-83ea-b57b-a697d1ec557b -->
<!-- 段位：第一段（盲问）——只给问题与仓内坐标，不给我方已有答案，完全独立设计 -->
<!-- 模型：GPT Pro（浏览器席），交付日期 2026-08-15，思考 25m5s，全程 read-only -->

结论

需要改，但不是推翻三面模型，也不是增加一个“研究面”。

真正需要改的是审计的基本单位：

旧方法主要判断“这个东西属于哪个面”；新方法必须判断“这个东西沿着哪条边，被哪个消费者，以什么作用使用”。

定理开始被编译进模型以后，危险不再只住在文书措辞里，而是住在：

定理 → checker → lowering → 具体约束 → 求解结果 → 结论或权威

这条链上的每一条边里。

因此我的总设计是：

三面本体继续保留：数学面、发布面、档案面。

“研究”不升为第四面，它是与三面正交的成熟度和权限状态。

人工审计仍然采用事件式，但触发器从“出事或大改”改成“新作用能力出现或迁移”。

增加一个很薄的、常驻机器执行的可执行消费合同。

定理成立、定理可被某消费者使用、定理可产生认证效力，这三件事永远分别过门。

一句话概括就是：

节点有身份，边有权限。证明钥匙不能打开权限锁，权限钥匙也不能把命题证明为真。

一、为什么现行架构已经不够

现行设计的核心洞见仍然成立，但它现在覆盖到了“节点”，没有完整覆盖“边”。

1. 现行消费三闸主要管文书前提，不管可执行约束

CONSUMPTION_GATES.md:7-16 把“消费”定义为进入推导链、算式、判据、排除理由或 certified 放开的前提集；CONSUMPTION_GATES.md:95-106 也明确目前是人工扫描文书前提集。

这能阻挡：

UNREVIEWED 条目被文书当成真理；

研究参数被认证文书拿去放开限制；

generated view 被当成权威真源。

但它看不见：

一个研究模块读取 Judgment
→ 看到 checker PASS
→ 向 CP-SAT 模型加一条约束
→ 某些 binding selection 从此不再存在

这里甚至不需要有任何违规措辞，污染已经发生。

2. W0 标本的边界写得清楚，但没有被端到端绑定

W0 Judgment 已经不是纯散文。它在 01_JUDGMENT.json:4-12 结构化写明：

RESEARCH_ONLY_OFFLINE_THEOREM

authority = evidence_only

no_solver_integration

no_lowering

no_certification_effect

no_claim_outside_the_pinned_context

这部分做得很好。

但独立 checker 在 03_check_w0_ghost_front_certificate.py:642-680 中，验证 Judgment schema、输入身份和证明后，输出的是一个顶层裸 status: PASS。整个 checker 文件里没有对 Judgment 的 authority、status、non_implications 做消费侧校验。

这在当前离线证明用途下不构成 checker 缺陷。它本来就只负责证明成立。

但一旦有消费者写成：

Python
运行
if receipt["status"] == "PASS":
    add_constraint(...)

证明有效性就被静默转换成了执行许可。这才是新接缝。

3. rules/derived/ 管节点新鲜度，不管具体消费者怎样翻译

rules/derived/README.md:19-30 已经有很好的状态机：

UNREVIEWED

ACTIVE

STALE

PROMOTED

只有存在 consumer 的 STALE 条目才阻断消费。

但当前条目主要登记：

命题；

scope；

premises；

premise fingerprint；

direction；

consumers。

它没有表达：

这个消费者位于 binding、master 还是 routing；

抽象触发器被映射成了哪个运行时 literal；

lowering 实际拒绝的集合是否超出了定理证明的集合；

消费者获准做的是研究剪枝、知识引用，还是认证剪枝。

因此，ACTIVE 只能表示“这个定理节点通过了某种审查”，不能表示“所有 lowering 都自动正确”。

4. 仓里其实已经有一个更早的同型信号

CLAIM-STRICT-HOLE-AVOIDS-X1-Y1 的 authority 是 research_only，但 consequences 写着“候选生成和结构推理可把 x=1 与 y=1 作为禁碰轨道”。

目前全仓搜索没有找到真实生成器在消费它，所以今天没有可执行污染。

这恰好说明：

一个节点即使同时写了 authority 和 operational effect，也仍然缺少“究竟哪一个消费者被允许怎样使用它”的边合同。

5. 现行 cut 协议已经给出了正确的分层方向

23_rule_cut_evolution_protocol.md:7-16 已经把以下六件事分开：

语义；

表示；

发现与生成；

验证；

消费；

权威。

所以不需要重建另一套庞大生命周期。需要补的只是定理流水线中目前没有被一等建模的那根轴：

已验证定理如何被某个具体消费者翻译成实际作用。

二、总体架构：三面保留，增加“作用边”模型

我不会增加第四个“研究面”。

原因很简单：

W0 命题本身是数学对象；

checker receipt 是证据或档案对象；

research_only 是权限上限；

lowering 是数学对象到模型约束的转换边；

后续 promotion 是权限变化。

“研究”横跨这些对象，不是与数学面、发布面、档案面对等的一种语义类型。

新的图应当长成这样：

数学命题节点
    │
    ├─ proof verification
    │      └─ 定理验证收据
    │             granted_effects = []
    │
    ├─ executable consumption contract
    │      └─ lowering
    │             └─ 研究模型消费者
    │                    granted_effects = [research_model_pruning]
    │
    ├─ knowledge citation contract
    │      └─ 研究结论或承重文书
    │
    └─ explicit promotion bridge
           └─ 认证侧重新验证、重新铸造

其中有四种本质不同的边：

验证边：证明命题成立，不改变模型，不授予权威。

执行边：把命题翻译成约束、过滤器、变量域或 stopping rule。

引用边：把命题用作另一结论的前提。

晋级边：让研究工件获得生产或认证能力。

档案边仍然只是保存事实。档案一旦被拿来支撑结论，审计对象就不再是档案节点，而是那条引用边。

三、① 审计线的介入模式

现行“出事或大改时审一次”需要改成：

人工仍是事件式，机器边界则常驻；事件从事故事件改成能力转移事件。

1. 四个介入层级
A. 定理实例级：机器自动，人工不驻场

适用于同一种定理模板、同一种 lowering、同一个消费者不断量产新实例。

每个实例自动检查：

定理状态与 premise fingerprint；

当前运行 context 是否满足定理 scope；

Judgment、checker、lowering、consumer 的身份是否匹配；

该实例是否仍属于已经审过的 lowering family；

失败时是否真的退回无作用。

不要求三面审计线逐条人工重审。

否则定理量产以后，审计线会立即成为吞吐瓶颈。

B. lowering family 级：首次出现或结构变化时人工介入

以下任一发生，必须重新过堂：

第一条定理申请被编译消费；

新增一种 effect kind，例如从 binding pruning 变成 master pruning；

lowering compiler 版本或抽象 literal 映射变化；

消费位置前移或后移；

theorem scope、polarity、premise algebra 变化；

研究结果第一次被承重文书引用；

同一合同开始跨实例、跨布局或跨 family 复用。

这一层盯的不是“定理对不对”，而是：

它在消费者手里究竟变成了什么；

消费者可见的信息是否足够表达定理前件；

lowering 有没有偷偷变强；

失败方向是否正确。

C. 跨面晋级级：硬停，单独 owner gate

以下任一发生，直接视为面边界事件：

修改 certified src/ 来容纳研究 lowering；

certified 模块开始 import 研究模块；

certified loader 开始接受研究 receipt/schema；

研究结果开始更新认证 U/L、strong status、terminal evidence 或 publication surface；

研究定理申请进入 production/certified cut 或静态模型；

同一个研究条目被原地改标签为“已认证”。

此时不是普通审计，而是一个新的 promotion 变更包。

D. 事故与大重构级：保留现行全仓审计

发生以下情况时，仍做传统广域审计：

已发现越权消费；

模型结构或发布权威链大改；

status/schema 大范围统一；

新的自动生成文档或知识投影上线；

consumer inventory 与实际代码发生不明漂移。

因此不是废掉现行事件式，而是把它放回它最合适的位置。

2. 日常到底盯什么

只盯会产生以下任一效果的边：

删除或新增候选；

改变量域或添加硬约束；

把一次失败升级成 INFEASIBLE；

更新上界、下界、终态或证书解释；

让某个 claim 成为承重前提；

增加 owner、production、certification 能力；

改写当前权威投影。

纯粹的：

proof search；

离线观察；

telemetry；

排序建议；

不参与停止条件的 branch ordering；

档案保存；

不进入这套重合同。

这条边界能防止审计线膨胀成研究总管。

四、② 新符号判据：按“作用边 × 消费者 × 目标结论”判，不再只按面判

原判据 FIRST_PRINCIPLES_DESIGN.md:633-641 是：

收紧更安全，发布面；

收紧使命题变假，数学面；

只记录，档案面。

它仍然可以作为第一问，但已经不能独立给出最终符号。

新的完整问法应当是：

这个动作通过哪条边，对哪个状态空间产生了什么作用，又准备支撑哪一种结论？

1. 对剪枝定理，用拒绝集合关系判

设在运行 context c 下：

R_T(c)：定理已经证明可以安全排除的候选集合；

R_L(c)：lowering 实际排除的候选集合；

F(c)：当前语义下真正可行的候选；

D(c)：lowering 前的搜索域。

定理本身应当证明：

R_T(c) ⊆ D(c) − F(c)

lowering 准入则要求：

R_L(c) ⊆ R_T(c)

于是四种情况被机械分开：

关系	判定
R_L = R_T	精确编译
R_L ⊂ R_T	安全但少剪，属于效用退化
R_L ⊄ R_T	lowering 越过证明边界，存在错误剪枝
runtime context 不满足 theorem scope	不得产生任何作用

这里有一个非常重要的结论：

定理范围缩窄，不是 soundness 红灯。

它只会让 R_T 变小，语义仍然安全，但适用率和收益下降。

只有当：

文书仍声称它是一般定理；

或 lowering 没有同步缩窄 scope guard；

或消费者把局部定理用到更广域；

才转成真正的污染。

2. 消费位置本身是合同的一部分

W0 定理证明的是：

active_output_slot(boundary_port_041, 0) → 不可路由

如果在 binding 阶段能直接看到准确的 active_output_slot literal，那么加入：

¬active_output_slot(boundary_port_041, 0)

可以是精确 lowering。

但如果把它前移到 master，master 只知道：

boundary_port_041 的 pose 被选中

然后为了“保守”直接禁止这个 pose，那么触发条件已经从：

pose selected AND slot active

变成了：

pose selected

这就是 R_L 严格大于 R_T。即使定理、checker、PASS 全都没有错，lowering 仍然会杀掉合法 binding。

所以“消费位置变化”必须自动使旧合同失效。

3. 必要剪枝、充分构造、最终检查要分三种关系
Rejector，排除器

要求：

每一个被删对象都由定理覆盖；

影响 upper/optimality 通道；

未知时不得删除。

Constructor，构造器

要求：

每一个产出的 witness 都满足已证充分条件；

可以更新 lower；

构造失败只能是 UNKNOWN，不能变成 INFEASIBLE。

Exact checker，精确检查器

要求两向关系，不只是单向包含。

因此不应把所有“定理消费”压成一个 direction: stricter。

4. 权威不是一根高低刻度，而是一组能力

machine、owner_decision、research_authority 并不是一个简单的线性等级：

machine checker 可以证明某个结构条件；

owner 可以决定项目是否立项；

machine checker 不能替 owner 关门；

owner 决定也不能让错误定理变真。

所以消费合同不应只写一个模糊的 authority_level，而应写确切能力，例如：

allowed_effects:
  - research_model_pruning


forbidden_effects:
  - certified_model_pruning
  - upper_ledger_update
  - lower_ledger_update
  - terminal_status_mint
  - publication
  - owner_decision

普通边只能保持或减少能力。只有具名的 owner gate 或 certified sink 才能增加能力。

权威不能从一个 PASS 字符串里凭空印出来。

5. 最终要同时维护三本账
账	问题	典型状态
语义正确性账	lowering 是否超出证明范围	sound / unsound / unknown
能力与权威账	该消费者是否获准产生这种作用	allowed / forbidden
效用账	覆盖率、剪枝量、墙钟收益是否足够	improved / neutral / degraded / unknown

用户列出的三种危险由此完全分开：

情况	语义账	权威账	效用账
定理范围缩窄	仍可为 sound	不变	退化
lowering 用得比证明广	unsound	即使权限正确也不能救	可能表面更快
研究结论被当认证结论	命题甚至可能是真的	越权	无关

这三种情况绝不能共享一个“保守／不保守”标签。

6. fail closed 也必须按面解释

这是我会写进首条硬规则的地方：

在研究剪枝或数学约束面，contract failure 的安全回退是“不加这条约束”，不是“拒绝这个候选”。

具体处置：

scope 不匹配：不 lowering；

theorem stale：不 lowering；

checker UNKNOWN：不 lowering；

literal binding 不清：不 lowering；

lowering checker 分歧：不 lowering；

treatment run 标为 INVALID 或 UNKNOWN，不能伪装成“零收益”。

而在发布面：

authority 不清：阻断发布。

如果有人说“为了 fail closed，合同异常时就把候选禁掉”，那正是在重新犯这条审计线最初要解决的错误：把发布面的保守直觉搬进数学面。

五、③ 最小契约与准入机制

我认为需要，但最小对象不是“再写一份定理登记”，而是一条可执行消费边合同。

可以叫：

Executable Consumption Contract，可执行消费合同

它至少包含以下内容：

edge_id


source:
  judgment_id
  proposition_fingerprint
  premise_fingerprint / problemHash
  objectiveHash
  contextHash
  proof_checker_identity


consumer:
  entrypoint
  stage
  effect_kind
  claim_channel


binding:
  abstract_trigger
  runtime_literal_mapping


semantic_relation:
  reject_set_subset_of_theorem
  或 exact
  或 witness_subset_of_proven_valid


allowed_effects:
  research_model_pruning


failure_action:
  no_effect
  run_result = INVALID_OR_UNKNOWN


verification:
  independent_lowering_checker
  negative_canaries
  lowering_digest
  consumer_digest


state:
  DECLARED | SHADOW | RESEARCH_ACTIVE | STALE | RETIRED
1. 它最小在哪

它不重复保存：

定理全文；

完整 proof；

Judgment 里的 premises；

人工审查签名；

实验收益数据；

owner 裁决正文。

它只负责把已有定理节点与某个具体消费者连起来。

2. 它挂在哪里
第一号 W0 canary

我会把合同放在新的 W0 lowering canary dossier 里，与现有离线证明包平行，而不是修改现有证明包。

原因是当前包已经诚实声明“本包不包含 lowering”。后续增加一份独立合同，不会推翻这句话：

旧 proof PASS 仍然不自动蕴含 lowering；

新合同单独证明某个 lowering 可以被某个研究消费者使用。

执行闸的位置

真正的机器闸必须挂在：

研究模型即将第一次改变可行域的位置。

例如就在研究 harness 向 binding model 添加约束之前。

不能挂在：

theorem checker 里，因为太早，它不知道消费者；

最终 checker 里，因为被误删的候选永远到不了最终 checker；

文书 preflight 里，因为它看不见运行时 literal；

telemetry 里，因为 telemetry 只能观察，不能授权。

流水线成熟以后

若出现第二、第三种 theorem→consumer edge，再把这种合同抽成统一的非冻结 edge registry。

逻辑上它可以成为 rules/derived/ 的同族对象，但不应直接给现行 theorem entry 增加一堆手写 consumer 字段。更好的形态是：

一条 edge 一文件；

theorem 和 consumer 都只被引用；

consumer reverse index 机器生成；

theorem STALE 时，所有 active edge 自动禁用。

当前 owner 只批准了 rules/derived/ 现有非冻结层的存在，所以扩出正式 edge 子目录本身仍应作为独立机制批裁定。第一号 canary 不需要提前购买这套全局框架。

3. 文书侧只需增加一个很小的 G4

现有 G1-G3 继续保留。

文书与知识账本侧新增：

G4：请求的作用能力不得超过来源与显式闸口授予的能力。

最小凭据：

来源 claim / theorem
来源 authority 与 authority_effect
目标语境
本次请求的作用
是否存在具名 promotion / owner / certified mint
判定

例如：

research_only 定理可以作为认证提案的背景证据；

不能直接作为 certified 放开或认证剪枝的承重前提；

owner 可以决定“允许开展研究实验”，但这不把定理升格为认证定理。

4. 两套 PASS 怎么处理

我不建议全仓把 PASS 改名。仓内研究工具已有大量局部 PASS，全面改名成本高，而且治标不治本。

真正的硬规则应是：

任何跨工具消费者都不得只判断裸 status == PASS。

机器接口应当至少区分：

JSON
{
  "result_kind": "theorem_verification",
  "outcome": "VALID",
  "granted_effects": []
}

和：

JSON
{
  "result_kind": "research_consumption_admission",
  "outcome": "ADMITTED",
  "granted_effects": ["research_model_pruning"]
}

认证链则使用自己的 schema 和 granted effects。

现有 W0 checker 可以保持它的证明职责；第一次消费时，增加一个独立 admission wrapper，联合读取：

Judgment；

proof receipt；

consumption contract；

runtime context。

这样不会把 proof checker 变成权限管理器。

5. 明确不挂在哪里

我会明确禁止把研究消费合同挂进：

rules/canonical_rules.json

PROJECT_LOCK.md 的逐定理条款

certified cut registry

certified src/ 中的默认关闭 feature flag

data/review_gates/

单纯的 claim consequences 字段

archive decision log

theorem checker 的裸 PASS 文案

这些位置要么会把研究迭代冻住，要么会让“存在合同”被误读成“已经认证”。

六、④ 跨面边界：用单向能力桥，不用标签自律

跨面机制应当遵循一句话：

认证资产可以作为研究输入被读取；研究工件不能反向取得认证作用，除非经过一个显式、重新铸造的 promotion sink。

1. 允许的方向

研究 harness 可以：

读取 canonical rules；

读取候选池和固定布局；

调用现有模型或纯函数；

引用 certified source 作为待测对象；

把输入 digest 写进研究收据。

这只是依赖，不是晋级。

2. 默认禁止的方向

必须机器阻断：

src/** 或 certified loader import docs/research/**；

certified runtime 读取 live rules/derived/** 条目作为约束；

certified loader 接受研究 receipt schema；

研究 run 写入认证 review gate、delivery manifest、strong candidate status；

研究模块更新认证 U/L；

研究 INFEASIBLE 被持久化为 certified proof-bearing INFEASIBLE；

原地把 research 条目标成 certified。

研究代码可以产生自己的 namespaced RESEARCH_INFEASIBLE 或实验终态，但它们不能被认证 sink 识别成强状态。

3. 第一号实验采用更严格的实际边界

对当前静态 lowering canary，我会规定：

lowering 代码与埋点全部在 research dossier 或 research harness；

tracked src/ 零修改；

src/ 修改立即停止，转入面边界评审；

研究侧可以 import 现有 src，但 src 不得反向 import 研究侧；

研究结果只写研究 artifacts。

这与 ROADMAP.md:69 的现行红线方向一致。

4. 真正 promotion 时怎样过桥

未来若某条定理真的要进入认证路径，不能“翻一个 flag”或“把 research_only 改成 machine”。

必须创建新的 promotion package，至少包含：

明确的 owner promotion 决定；

被认证侧接受的 theorem identity 与完整 premise root；

当前运行重推定理，或把精确 theorem/checker/input 身份纳入认证依赖根；

独立 lowering correctness checker；

malformed、scope drift、错误强化、stale premise 的红测试；

certified 侧自己的实现，不 live-import 研究模块；

certified sink 对 exact inputs、consumer、lowering 和 proof 重新验证；

PROJECT_LOCK、spec、test、source digest 边界同步更新；

原研究包继续保持历史 research 身份，必要时标 PROMOTED，但不成为认证运行时的活依赖。

这直接复用仓里已经成熟的原则：

PROJECT_LOCK.md:194-195：checker PASS 不等于 owner 关门；

PROJECT_LOCK.md:357：proof authority 在 sink 重新验证，而不是由 producer、writer、registry 或当前进程授予；

PROJECT_LOCK.md:700：shadow、lowering、production attach 与 owner promotion 分离。

这套模式比给研究文件反复加“non-authorizing”字样可靠得多。

七、把设计落到 W0 第一号 canary 上

对现有 W0 定理，我会这样做。

第一步：现有证明包保持不动

继续保持：

J-W0-GHOST-FRONT-BOUNDARY-041-V1

exact problemHash；

exact objectiveHash；

exact contextHash；

fixed W0 layout；

fixed 6×7 rectangle；

quantified component 仅为 binding selection；

evidence_only。

不修改旧包来伪装它当初已经含有 lowering。

第二步：新建独立的消费合同

合同声明：

effect kind：REJECTOR

claim channel：UPPER_AFFECTING_RESEARCH_SEARCH

consumer stage：binding

exact abstract trigger：active_output_slot(boundary_port_041, 0)

actual lowering：加入 ¬active_output_slot(boundary_port_041, 0)

required relation：R_L = R_T

allowed effect：仅 research_model_pruning

certification、U/L、strong status、D3 family generalization 全部为 false。

第三步：scope guard 必须逐项锁住

只有以下全部一致才准激活：

problemHash；

objectiveHash；

contextHash；

fixed layout identity；

fixed rectangle；

instance id；

pose index；

slot index；

binding 的 active-output 语义；

canonical predicate 5 版本。

任何一项不符，lowering 不产生作用。

对于第一号固定对象，精确相等 guard 足够安全。

未来如果要做参数化 family theorem，不能继续只依赖一个 hash，必须把 premises 结构化，并证明 runtime context 蕴含 theorem context。

第四步：先 SHADOW，再 RESEARCH_ACTIVE

SHADOW 阶段：

计算“这条 lowering 本来会拒绝什么”；

不改变模型；

对每个 would-reject selection，核对 theorem trigger；

用错误 slot、错误 pose、移动 rectangle、换 layout 等 mutation canary 证明 guard 会关掉；

不以 coverage 代替证明。

RESEARCH_ACTIVE 阶段：

仅在同一 research harness 中实际加约束；

做 baseline/treatment 配对；

记录候选数、binding proposals、routing calls、墙钟和终态；

contract mismatch 时回到无约束 baseline，同时 treatment 记为 INVALID/UNKNOWN。

第五步：尤其禁止把触发器偷偷提升成 pose ban

这是该 canary 最值得做的反例测试：

正确：禁止该 slot 在该固定上下文中 active；

错误：禁止 boundary_port_041 pose；

更错误：禁止所有 boundary storage port 的同类 pose；

更错误：把固定 W0 定理写成跨布局 family cut。

这些错误都可能比正确 lowering 更“有效”，但它们增加的收益正来自未证拒绝集合。

第六步：A/B 只衡量收益，不证明零误杀

即使 treatment：

得到相同最终 optimum；

跑得更快；

final checker 也通过；

仍然不能据此证明 lowering sound。

被错误删除但不改变这个实例 optimum 的解，最终 checker 永远看不到。

soundness 必须先由 scope transport 与 R_L ⊆ R_T 保证，A/B 只回答“值不值得”。

八、⑤ 我会明确拒绝的常见做法
1. 增加一个与三面对等的“研究面”

研究是成熟度与权限，不是语义类型。加第四面会把数学命题、实验收据、研究权限再次装进同一个桶，问题反而复发。

2. 全仓重命名 PASS，或给 PASS 后面统一加免责声明

词汇不是根因。真正的问题是消费者有没有严格解析 schema、result kind 和 granted effects。散文免责声明阻止不了一行 status == "PASS"。

3. 让 theorem checker PASS 自动打开 lowering

定理正确不等于：

runtime context 满足 scope；

abstract trigger 映射到了正确 literal；

lowering 没有变强；

这个消费者有权动模型。

至少是四个独立问题。

4. 在 contract 异常时“保守地”拒绝候选

这是最危险的伪安全做法。数学面里的安全回退是撤掉新约束，返回 UNKNOWN；拒绝候选会把验证故障变成假不可行。

5. 把研究 lowering 放进 certified src/，然后靠 default-off env flag 隔离

default-off 是运行配置，不是结构隔离。代码路径一旦存在，就会进入 source digest、测试、未来重构和误启风险。第一号 canary 不应为实验便利给认证面埋一根暗管。

6. 把每一条机器消费的定理都塞进 canonical 或 PROJECT_LOCK 冻结

hash 只证明字节没变，不证明定理正确。对高频派生定理做全局 freeze 会把研究节拍拖死。

正确做法是：

源定理保持可重推；

每条活消费边绑定精确 fingerprint；

运行前重验或把依赖纳入对应运行的 artifact root。

7. 用最终 checker、同 optimum 或 A/B 零差异证明“没有误杀”

错误剪掉的解不会到达最终 checker；同 optimum 也不能证明没有删掉其他合法解。性能对照不是 soundness proof。

8. 因为 research lowering 与 cut 都会剪枝，就立刻合并两套框架

它们当前的 authority、生命周期和威胁模型不同。可以复用 typed lowering、独立 verifier、sink promotion 这些原则，但不应共享 production registry 或 certified apply path。

等到真正出现“定理进认证路径”提案时，再由 owner 决定是否合流。

9. 把定理缩窄一律判成失败，或者反过来把局部定理方便地写宽

前者把效用问题误报成 soundness 问题；后者直接制造错误剪枝。范围变化必须分别记语义正确性和适用率。

10. 强制所有 lowering 都与 theorem 完全等价

如果一个 lowering 只实现 theorem reject set 的一部分，它仍然可以完全 sound，只是剪得少。

只有当它声称“精确编译”或其完整性会进入证明时，才要求等价。一般研究剪枝最低要求是 R_L ⊆ R_T。

11. 依赖目录名、文件头或手写 consumers 清单隔离

docs/research/、non_authorizing 和 research_only 都只是节点标签。真正的隔离必须发生在：

import 方向；

loader schema；

write capability；

consumer admission；

sink replay。

12. 把三面审计线变成所有研究批次的常驻审批者

这会迅速把研究流水线堵死，也会让审计者变成事实登记维护者。

正确分工是：

作者和实现者登记 edge；

机器检查定理实例；

审计线审 first-of-kind、结构迁移和跨面晋级；

owner 只负责需要 owner 能力的门。

最终裁定

我的独立判断是：

三面模型不需要扩面，但审计线必须升级为“作用边审计”。

具体改法不是再造一套宏大治理架构，而是三件事：

把人工介入从“事故驱动”改成“能力转移驱动”；

给每条 theorem→lowering→consumer 边增加最小可执行消费合同；

把数学正确性、作用权限、实际效用拆成三本账。

最核心的硬规则可以压成三句：

定理 PASS 只证明定理，不授权消费。
lowering 只能拒绝定理已经证明可拒绝的对象。
研究作用进入认证面时，必须由认证 sink 和 owner 重新铸造，不能继承。

本次全程只读。tracked worktree、index 和 tracked diff 均为空；仓内原有的大量 untracked .artifacts/ 等材料未作任何改动。
