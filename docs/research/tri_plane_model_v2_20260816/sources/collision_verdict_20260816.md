<!-- 原始评审材料：GPT Pro 对撞段三方裁断（逐字保存，不作编辑） -->
<!-- 来源：ChatGPT 对话「审计线方法设计」 conversation 6a818168-53c8-83ea-b57b-a697d1ec557b -->
<!-- 段位：第二段（对撞）——输入为我方两线收敛提案六点 + 另一外审线程 B 段裁断五件（出处逐条标注），与其盲答三方对撞 -->
<!-- 模型：GPT Pro（浏览器席），交付日期 2026-08-16，全程 read-only -->

先给总裁断：

材料一六点里，①②③④⑤都是“修正后采纳”，⑥直接采纳。材料二 B1 至 B5 都有实质价值，但 B2、B3、B4 不能按表面的一维结构直接落地。唯一需要明确否决的核心主张，是“研究成为与数学、发布、档案对等的第四个语义面”。

我对盲答的核心判断仍然维持，但会作三处重要升级：

研究不能成为第四个语义面，但必须成为一等的运行域、权限域和维护域。

我原先的“语义／能力／效用三本账”应改名为每条消费边的三轴裁断；仓库级存量账则采纳 B4 的“知识／能力／期权三账”。

首个新类型不应立即抽象成通用机器制度，但首个真正改变可行域的实例也不能无保护地先跑两三次。应当是“先有专用合同和专用护栏，再等样本结晶通用检查器”。

当前仓库状态也支持这个裁断：REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md:55-63 已经把消费契约列为证明产品的一部分，:33、:48 已明确 lowering 不得强于定理，:126-132 已经指出过缓不会自曝；ROADMAP.md:69 也已经把“研究 lowering 留在研究模块、触碰 src/ 即边界事件”登记为红线。当前 HEAD 仍为 8dfb5cb，tracked worktree 干净，本轮没有修改任何文件。

一、材料一逐点裁断
① “事后审计”改为“出生证查验”

裁断：修正后采纳。

方向正确，而且比单纯“事故后复盘”前移了一整个生命周期。我的盲答中“first-of-kind 人工介入”与它基本同向。

但需要改两处。

第一，出生证的对象不能只是“新类型工件”，而应是：

第一次出现的新作用边，或旧作用边第一次获得新能力。

以下情况即使没有新文件类型，也必须重新查验：

同一 theorem 第一次从文书引用变成模型剪枝；

同一 lowering 从 binding 阶段移到 master 阶段；

同一 research PASS 第一次被 certified 文书承重引用；

同一 consumer 从 shadow 变成真实改变可行域；

同一合同开始跨布局、跨 family 或跨运行域复用；

同一实现第一次请求更新 U/L、strong status 或发布面。

反过来，第十条同型离线定理，如果仍由同一个 checker、同一个消费合同、同一种作用边处理，不必重新召集整条人工审计线。

第二，“等 2 至 3 个实例再机器化”只能延后通用抽象，不能延后首个实例的安全护栏。正确节奏是：

第一实例：人工出生证、专用消费合同、专用负例、默认 shadow。

第二至第三实例：观察哪些字段真的稳定，哪些只是第一例的偶然形状。

同型稳定后：结晶通用 schema、通用 checker 和自动触发器。

之后的新实例：机器常检，人工只在换角色、换消费者、换能力或换作用域时回来。

因此最终不是单纯“出生证”，而是：

出生证＋换证＋晋级证。

② 研究 checker 收据必填 authority 与 pass_scope

裁断：修正后采纳。

“消灭可跨边界消费的裸 PASS”完全正确。现有 W0 checker 顶层只输出 status: PASS，虽然它的 Judgment 文件写了 evidence_only、no_lowering 和 no_certification_effect，但 consumer 若只读取 receipt 的 status，仍然可以把证明有效性误当成执行许可。

但仅有 authority 和 pass_scope 还不够。

推荐的最小顶层结构是：

result_kind
outcome
subject_identity
verified_scope
authority_basis
granted_effects
non_implications
contract_identity

其中：

result_kind 说明这是 theorem verification、measurement、research admission，还是 certified replay。

outcome 不再只有 PASS/FAIL，而是按类型给出 VALID、INVALID、UNKNOWN、CENSORED 等。

verified_scope 回答“检查器到底验证了什么”。

authority_basis 回答这个权威声明从哪里来，不能由 receipt 自己凭字段自封。

granted_effects 回答 consumer 获准做什么，默认必须为空。

non_implications 明确不授予什么。

contract_identity 防止拿旧 PASS 套到新 lowering 或新消费者上。

最关键的分离是：

pass_scope 描述证明覆盖范围，granted_effects 描述执行权限。两者不是同一个字段。

例如 W0 theorem checker 可以输出：

result_kind = THEOREM_VERIFICATION
outcome = VALID
verified_scope = pinned W0 binding-only theorem
granted_effects = []

后续独立的 research admission checker 才可能输出：

result_kind = CONSUMPTION_ADMISSION
outcome = ADMITTED
granted_effects = [RESEARCH_BINDING_PRUNING]

我仍不主张机械地把全仓每个内部子检查的 PASS 都改名。局部、不可被跨工具消费的检查项可以继续叫 PASS。必须消灭的是：

跨组件、跨文书、跨权限边界的顶层裸 PASS。

③ 研究面升为对等面，符号按工件角色给

裁断：修正后采纳。

其中包含两个不同主张，必须拆开裁。

③-A “研究面升为第四个对等面”

拒绝。

原因不是研究不重要，而是“面”在这套方法里的定义要求它拥有相对稳定的语义和符号。

原三面分别回答：

数学面：命题和模型是否真实、完整、健全。

发布面：某个结果是否有资格被承认、发布、晋级。

档案面：发生过什么、谁何时作过什么裁定。

而“研究”内部同时包含：

数学定理；

实验测量；

checker 收据；

lowering；

准入门；

冷档案；

owner 立项提案。

这些对象的“收紧”符号并不一致。把它们装进第四个“研究面”，会立刻在研究面内部重演最初的污染问题。

尤其材料一自己紧接着又提出“符号不按所在面，而按工件角色给”。这实际上说明“研究面”已经不承担符号判定功能。它更像一个运行辖区，而不是语义面。

最终建议采用二维坐标：

semantic_plane:
  MATHEMATICAL
  RELEASE
  ARCHIVAL


operational_domain:
  RESEARCH
  CERTIFIED

以后可以按 owner 裁决扩展运行域，但不能混成一根轴。

于是：

research theorem = 数学面 × 研究域；

research receipt = 档案/证据面 × 研究域；

research admission gate = 发布/准入面 × 研究域；

certified theorem lowering = 数学面 × certified 域；

owner promotion record = 发布面 × certified 域。

所以我修正盲答里的措辞：

研究不只是“成熟度和权限标签”，它需要成为一等的运行域、权限域和维护域；但它仍不应成为第四个对等语义面。

③-B “按工件角色给符号”

采纳为第一层模板，但不能替代消费边裁断。

角色判据与我的“作用边 × 消费者 × 目标结论”不是完全不同的东西，但也不等价。

准确关系是：

角色给出局部符号模板，消费边给出最终符号。角色判据是边判据的有损投影。

例如：

定理收窄，单看 theorem 节点是安全但有债。

但旧 lowering 若仍按原宽范围运行，整条消费边已经 unsound。

同一个 PASS 被背景文书引用，可能完全合法。

同一个 PASS 被拿去铸造 certified pruning，就越权。

同一触发器在 binding 阶段可精确求值。

把它前移到 master，而 master 看不到 slot-active 变量，就可能把“活动 slot 禁止”偷换成“整个 pose 禁止”。

所以最终公式应是：

verdict =
  f(
    source_role,
    edge_kind,
    consumer_stage,
    runtime_binding,
    effect_kind,
    target_claim,
    context
  )

材料一给的几个角色例子还需校准：

原说法	修正版
定理加宽＝unsound	未经新证明而加宽才是 unsound；重新证明后的加宽完全合法
定理收窄＝安全但记债	成立，但所有 ID、fingerprint、consumer 和 lowering 必须同步收窄
lowering 偏严＝杀解	对 rejector 成立，正式关系是 R_lowering ⊄ R_theorem
lowering 偏松＝只是少省钱	只对 rejector 成立；constructor 或 exact checker 的方向不能照搬
覆盖夸大＝假证书型错误	首先是测量／证据错误，只有被拿去扩大 theorem scope、授权剪枝或证明穷尽时才升级成假证书错误
PASS 越权引用＝发布面型错误	本质是能力越权，可能发生在 research→research，也可能发生在 research→certified，不只属于最终发布

对 rejector，可以使用最清楚的一组集合关系：

R_theorem(c) ⊆ D(c) - F(c)
R_lowering(c) ⊆ R_theorem(c)

其中：

R_theorem(c) 是定理证明允许排除的集合；

R_lowering(c) 是具体 consumer 实际排除的集合；

F(c) 是真实可行集合；

D(c) 是当前搜索域。

于是：

R_lowering = R_theorem：精确编译；

R_lowering ⊂ R_theorem：安全但少剪；

R_lowering ⊄ R_theorem：存在错误剪枝；

context 不满足 theorem scope：lowering 必须无作用。

④ 五项最小契约与止步线

裁断：修正后采纳。

五项的方向总体正确，但其中第二、第三、第四项需要重构，而且你们漏了最关键的一条“consumer binding”。

我建议仍保持“五组”，但改成：

第一组：来源身份

包含：

theorem / Judgment ID；

proposition fingerprint；

proof checker identity；

premise fingerprint；

problem / objective / context identity。

第二组：消费者与运行时绑定

包含：

consumer entrypoint；

consumer stage；

effect kind；

abstract trigger；

abstract trigger 到 runtime literal 的映射。

这一组是你们提案里最大的缺项。没有它，即使定理和 receipt 都正确，也不知道 consumer 实际执行的是不是同一个命题。

第三组：语义关系

按作用角色分别定义：

rejector：R_lowering ⊆ R_theorem；

constructor：W_constructor ⊆ W_proven_valid；

exact checker：要求双向等价；

ledger updater：只允许更新明确授权的账；

authority bridge：requested_effects ⊆ granted_effects。

“带见证”可以用于揭示违反包含关系的反例，但一个见证不能证明全集包含。最终仍需独立 lowering checker、有限域穷举、形式证明或与作用域相称的验证方法。

第四组：权限与边界

包含：

result kind；

verified scope；

granted effects；

research allowlist；

certified write denylist；

禁止反向 import；

禁止 strong-status、U/L、review gate、publisher 等资产写入。

“certified 摘要不变”可以作为验收项，但不能代替真实边界检查。摘要不变不代表：

certified runtime 没有 import research code；

source digest 没有变化；

strong-status 写点没有增加；

认证 loader 没有接受 research schema。

第五组：新鲜度与失败动作

包含：

current context fingerprint；

premise currency；

stale 传播；

failure action；

review trigger；

supersession / retirement。

其中必须写死：

contract mismatch
→ no effect
→ treatment result INVALID 或 UNKNOWN
→ baseline candidate 不被拒绝
止步线

“审计线不做质量评分”采纳。因为把 soundness、authority、utility 压成一个总分，会再次把性质相反的量混成一根轴。

“审计线不强制预注册”也采纳，但含义应是：

审计线不成为全项目实验方法委员会，不对所有研究统一征收预注册税。

这不妨碍具体实验线为了因果 A/B、go/no-go 或防结果后改阈值而自行要求冻结协议。审计线只检查“你声称遵循的协议是否真的遵循”，不负责给每项实验强制创造协议。

⑤ 跨面边界事件固定格式，超时默认 BLOCKED

裁断：修正后采纳。

这里必须明确区分两种完全不同的 BLOCK。

控制面 BLOCKED

用于：

research→certified 晋级申请；

新 effect grant；

修改认证资产；

研究 theorem 进入 production registry；

请求更新 U/L、strong status 或发布面。

若到期没有裁决：

transition_state = EXPIRED_BLOCKED

含义只有：

请求的新能力没有获得，边界不发生迁移。

它不表示 theorem 为假，也不表示研究资产无效，更不表示某个候选不可行。

数据面 NO_EFFECT

用于数学或求解运行中：

scope mismatch；

theorem stale；

lowering checker 分歧；

runtime literal binding 不明确；

contract fingerprint 不一致；

checker UNKNOWN。

正确动作是：

runtime_effect = NO_EFFECT
candidate_status = 保持 baseline 结果
treatment_outcome = INVALID 或 UNKNOWN

绝不能是：

candidate = INFEASIBLE

所以两者完全可以共存：

场景	默认动作
晋级申请超时	阻断晋级边，不授予新能力
research lowering 合同异常	不加约束，不拒候选
certified 发布材料不全	阻断发布
theorem scope 不匹配	该 theorem 在本 context 无作用
原有 baseline research 已获准	不因另一项晋级申请超时而自动停掉

一句话：

BLOCKED 挡的是能力迁移，NO_EFFECT 保的是数学可行域。

固定格式边界事件建议至少包含：

source asset；

current domain；

target domain；

requested effects；

将触碰的路径和 schema；

consumer entrypoint；

reversibility；

rollback；

throughput cost；

owner / sink；

decision deadline；

未裁时阻断范围。

⑥ 常设闸必须标吞吐成本

裁断：采纳。

而且这不是新增方向，仓内草图已经在 REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md:126-132 明确指出“过缓不会自曝”。现在需要做的是把这条散文原则变成结构字段。

每个常设闸至少登记：

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

其中 measurement_state 必须采用 B1 的 typed-null 纪律。没有测量时不能写 0。

这条成本登记不意味着 soundness 门可以因太慢而自动关闭。它只保证：

安全成本不再隐形；

临时防线不会因为无人量化而永久固化；

是否换方案、加资源或降低频率能被 owner 明确裁量。

所以“过严不自曝”与“过缓不自曝”确实应当对称管理，但它们对应不同风险：

过严隐藏的是被杀掉的合法解；

过缓隐藏的是被消耗掉的研究节拍和未来发现。

二、我方六点提案错了什么、漏了什么
明确错的部分
1. 把研究升为第四个对等语义面

这是分类错误。研究需要一等治理席位，但其内部不具有统一符号，应作为与三面正交的运行域。

2. 把“工件角色判符号”当成最终判据

角色只能给模板，最终必须看具体 edge、consumer、runtime binding、effect 和 target claim。

3. 让 receipt 的 authority 字段看起来像 authority 真源

receipt 可以报告 authority，但不能自铸 authority。其值必须由 schema、issuer、owner decision、sink 或具名 verifier 共同约束。

4. 把“一个见证”当成拒绝集包含关系的证明

见证可以推翻包含关系，不能普遍证明包含关系。必须有独立 lowering correctness mechanism。

5. 把“certified 摘要不变”当成认证边界的充分条件

摘要不变只能防表面漂移，防不了反向 import、写能力、schema admission、source digest 和 strong-status 新入口。

6. 把“2 至 3 个实例后再机器化”写得过于宽

可以延迟通用抽象，不可以让第一条可执行 lowering 在无合同、无负例、无 no-effect fallback 的情况下先跑。

7. “超时默认 BLOCKED”没有说明阻断对象

若不区分控制面与数据面，极易被错误解释成“审计没批，所以候选拒绝”。必须固定为只阻断 requested transition。

8. 几个符号例子表述过强

“定理加宽”“lowering 偏松”“覆盖夸大”都必须加上角色和消费语境，否则会把安全变化、效用退化和真正 unsound 混在一起。

我方提案漏掉的关键件

Consumer identity 和 stage：谁在什么位置消费。

抽象触发器到 runtime literal 的映射：理论上的 active_slot 是否被偷换成了 pose_selected。

合同失败的 no-effect 语义：数学面 fail-closed 必须是不加新约束。

独立 lowering checker 与负 canary：proof checker 不能顺手兼任。

能力集合而非 authority 等级：具体允许 research pruning、publication 还是 mint。

跨面单向依赖和写能力控制：research 可读 certified，certified 不 live-import research。

晋级时重新铸造：不能原地把 research_only 改成 certified。

SHADOW 到 RESEARCH_ACTIVE 的中间阶段：先记录 would-reject，再真实改变模型。

上下文索引状态：同一 theorem 在 W0 context 可用，不代表在另一个布局 context 也 ACTIVE。

typed null 与 sensor validity：打印了 0 不等于测得 0。

冷档案机制：不是所有未来可能有价值的 theorem 都值得承担持续 currency 成本。

存量账与实验流水分离：receipt 不能直接改写 capability 或 authority 存量。

吞吐成本的具体测量状态：不能只写“有成本”，还要说明已测、删失还是传感器未验证。

三、材料二 B1 至 B5 裁断
B1 typed null 六态

裁断：修正后采纳。

这是对现有方法的明显增益。它直接堵住：

没建 consumer 却写“拒绝数 0”；

长跑删失却写“没有发现”；

evaluator 根本没被测试过，却把打印数字当真观测；

形式上不可能改变某账，与“跑了但没变化”混成同一个零。

我建议把它正式建模为 typed observation：

Observation<T> =
  VALUE_MEASURED(T)
  | ZERO_BY_SCOPE(proof_ref)
  | NOT_READY
  | NOT_APPLICABLE_BY_TYPE
  | UNKNOWN_UNMEASURED
  | CENSORED(partial_state, reason)
  | SENSOR_UNVALIDATED(raw_value)

其中：

ZERO_MEASURED 可以保留为 VALUE_MEASURED(0) 的具名投影。

N/A_NOT_READY 最好拆成临时的 NOT_READY 与永久类型不适用的 NOT_APPLICABLE_BY_TYPE。

SENSOR_UNVALIDATED 可以保存 raw value，但不得支撑任何“真实测量”结论。

还应保留当前 Phase -1 已使用的独立 reachability 轴：

NOT_REACHED
REACHED_NO_EFFECT
EFFECT_NO_TERMINAL

因为“consumer 没到达”和“到达后测得零”不是同一件事。

与三轴裁断的关系：

ZERO_BY_SCOPE 主要进入语义轴；

ZERO_MEASURED、CENSORED、SENSOR_UNVALIDATED 进入效用／测量轴；

任何一种 observation 都不自动授予能力，granted_effects 仍为空。

B2 authority 四层

裁断：改造后采纳。

若把四层理解为一根线性楼梯，它与我的“能力是集合，不是等级”冲突，而且会产生错误推论：

VERIFIED < AUTHORIZED_FOR_EXPERIMENT < AUTHORIZED_FOR_PRODUCTION

这不总成立。

例如：

theorem checker 已实现并验证，但 pruning consumer 根本没实现；

owner 可以授权开展实验实现，但当前代码尚不存在；

production 中某个 noncert telemetry 获准，不代表 certified pruning 获准；

一个 verifier 的 VERIFIED 不会自动授权 publication 或 strong-status mint。

所以 B2 应改成四个独立 facet：

implementation_state
verification_state
authorization_scopes
activation_state

更具体地：

implementation_state:
  ABSENT | PARTIAL | IMPLEMENTED


verification_state:
  UNVERIFIED | VERIFIED | REFUTED | STALE


granted_effects:
  set of exact capability tokens


activation_state:
  INACTIVE | SHADOW | ACTIVE

B2 的四个词可以保留为人类查询投影：

IMPLEMENTED：实现面事实；

VERIFIED：验证面事实；

AUTHORIZED_FOR_EXPERIMENT：拥有某些 research effect grants；

AUTHORIZED_FOR_PRODUCTION：拥有某些 production effect grants。

但机器控制仍以精确的 granted_effects 为准，例如：

RESEARCH_OBSERVATION
RESEARCH_MODEL_PRUNING
PRODUCTION_NONCERT_TELEMETRY
CERTIFIED_MODEL_PRUNING
UPPER_LEDGER_UPDATE
LOWER_LEDGER_UPDATE
TERMINAL_STATUS_MINT
PUBLICATION
OWNER_DECISION

尤其在本仓，“production”与“certified”不能偷懒合并。是否允许生产运行，与是否允许产生认证效果，是两件事。

所以 B2 不与能力集合冲突，前提是：

四层是里程碑投影，不是单一 authority scalar。

B3 条件事项 discriminated union 与 state(a,c)

裁断：改造后采纳。

三个 kind 很有价值：

LATENT_ASSET：已知自身成立，但没有当前消费耦合；

CONDITIONAL_DEBT：当前结论、能力或迁移依赖尚未清偿条件；

MEASUREMENT_GAP：需要的效果或成本测量缺失、删失或无可信传感器。

state(a,c) 也是正确升级。当前 rules/derived/ 的 ACTIVE/STALE 是一个良好第一版，但 theorem 开始跨 context 消费后，全局标量会不够：

W0 theorem 在 pinned W0 context 可 ACTIVE；

对另一个 rectangle 或 layout 应当 NOT_APPLICABLE 或 STALE；

同一 theorem 对文书引用可用，对 master pruning 未必可用。

我建议进一步写成：

artifact_state(asset, context, time)
edge_state(consumption_edge, context, time)

并把 STALE 视为 freshness 轴，而不是替代 kind：

kind = CONDITIONAL_DEBT
freshness = STALE

还有一个重要修正：

discriminated union 应当作用于“条件记录”，不应强迫整个 artifact 只能属于一种 kind。

同一个 theorem 可能同时有：

一条 LATENT_ASSET 记录，描述尚未找到的未来 family coupling；

一条 MEASUREMENT_GAP，描述当前缺少运行时收益测量；

一条 CONDITIONAL_DEBT，描述某个已申请的 lowering 还缺独立验证。

它们应是三个独立 condition records，共同指向同一个 canonical asset。

前提 fingerprint 漂移统一转 STALE 完全采纳，但阻断范围仍按 context 与 consumer 决定，不能一处漂移让全仓所有无关 context 一起红。

B4 一库三账一流水

裁断：修正后采纳。

它与我的盲答不冲突，但双方说的是不同层级。

我的“语义／能力／效用三本账”更准确地说，是：

每条消费边的三轴裁断。

B4 的“知识／能力／期权三账”则是：

整个研究资产组合的三种存量投影。

两者应同时存在。

最终合并为：

EdgeVerdict =
  (semantic_correctness, capability_admission, utility_evidence)


RepositoryStocks =
  (knowledge_stock, capability_stock, option_stock)


ExperimentTransaction =
  (cost, Δknowledge, Δcapability, Δoption)

这里的“一库”不能解释成“所有 authority 都塞进一个大 JSON 文件”。正确含义是：

单一规范化 identity/event substrate，各种权威来源仍保持分离，三账均由确定性 projector 生成只读视图。

例如：

theorem verification event 更新知识账投影；

implementation event 更新能力账中的 implemented facet；

owner grant event 更新 capability grants；

holdout 失败可能降低 option value 或退役 TYPED_OPTION；

measurement event只增加证据，不直接自铸 authorization。

任何实验都不应直接手改三本存量账。它只能追加交易流水，然后由 projector 计算新存量。

我建议把“四格交易流水”收敛成：

成本与被消耗资源；

知识增量或减量；

能力增量或减量；

期权新增、收窄、触发、退役或转冷档。

测量值、删失状态和 sensor validity 作为这笔交易的证据附件。

B5 TYPED_OPTION 与 UNTYPED_ARCHIVE

裁断：修正后采纳。

这是我的盲答明显缺少的一块。

Γ_known(a) ⊆ Γ_true(a) 指出了一个很重要的事实：

今天不知道某个成果将来会和什么组合，不等于它没有未来价值。

因此不能要求所有研究资产要么立即找到 consumer，要么退役删除。那会系统性杀死尚未有语言描述的未来耦合。

两层登记应这样解释：

TYPED_OPTION

必须有：

已知 coupling；

context；

trigger；

可能影响的账；

当前 maintenance cost；

主动扫描规则；

复核触发器。

它进入 option stock 的活跃扫描，但不因此获得执行权。

UNTYPED_ARCHIVE

保存：

原始 theorem / artifact identity；

原上下文；

proof 或 evidence；

当时已知的非蕴含边界。

它不承担：

当前 currency 保证；

主动扫描；

当前 consumer 兼容；

当前 authority；

持续维护预算。

重新启用时，不能直接从冷档案被 consumer 引用，必须走：

UNTYPED_ARCHIVE
→ 创建新的 TYPED_OPTION
→ 当前 context 重验
→ 建立消费合同
→ 再申请 effect grant

必须增加一条反滥用规则：

任何已经有当前 consumer、当前阻断范围、到期义务或现行 claim 依赖的事项，都不得降入 UNTYPED_ARCHIVE。

否则团队可以把真实债务丢进冷库，伪装成“未来也许有用的资产”，从而逃避维护。

所以 B5 是防杀新概念的好机制，但必须同时防“债务洗白”。

四、我的盲答需要撤回或修正什么

有，需要明确说。

1. 修正“研究只是成熟度与权限”

我不撤回“不设第四个语义面”，但撤回其中可能让人误解为“研究不需要一等架构席位”的表达。

新表述是：

研究不是第四个语义面，但必须是一等的运行域、权限域、维护域和资源域。

2. 撤回“语义／能力／效用三本账是唯一总账架构”

它们应改名为：

每条 consumption edge 的三轴 verdict。

仓库级全局账本采用 B4：

知识存量；

能力存量；

期权存量；

实验交易流水。

3. 修正过于 rejector-centric 的最小契约

我盲答中的集合关系主要以剪枝定理为例。最终合同必须按 role 分型：

rejector；

constructor；

exact checker；

ledger updater；

authority bridge。

不能拿 R_lowering ⊆ R_theorem 管所有工件。

4. 修正全局状态枚举

原先的 DECLARED / SHADOW / RESEARCH_ACTIVE / STALE / RETIRED 不能作为 artifact 的唯一全局状态。

应改为：

lifecycle；

freshness；

implementation；

verification；

grants；

activation；

并全部按 context 或 edge 索引。

5. 增加“先专用、后通用”的结晶节奏

我原先强调 first-of-kind 审计，但没有明确说通用机器 schema 应等待多个实例。材料一①这一点成立。

修正为：

第一例必须有专用机器或人工护栏；

通用机器制度等 2 至 3 个同型实例后再抽象。

6. 增加 typed null、sensor validity 和冷档案

这三项是材料二带来的真实新增：

零值不能再裸记；

evaluator 未验证时不能称测量；

没有当前 coupling 的有效成果不应被迫承担活跃维护成本。

7. 强化常设闸的吞吐成本

盲答虽然谈了效用账，但没有把“审计机制自身的吞吐成本”提升成每个常设闸的必填合同字段。现在应当补上。

8. 对“裸 PASS”作更精确的收缩

我仍不支持全仓词法式重命名，但修正为：

所有可跨组件消费的顶层 research receipt，必须消灭裸 PASS；不可消费的内部子检查不必统一改词。

五、合并后的最终方法论文档骨架

下面这套标题和一句话主张，可以直接作为终态方法文档的章节骨架。

0. 文档身份与效力

本方法定义 research artifact 的验证、消费、晋级与维护纪律，本身不授予实验、生产或认证权限。

1. 问题：定理开始改变计算以后，污染住在边上

当研究工件从“被阅读”变成“被执行”时，主要风险从文书分类转移到 theorem、checker、lowering、consumer 与 authority 之间的作用边。

2. 坐标系：三语义面与运行域正交

数学面、发布面、档案面保持不变，研究／认证等运行域作为第二根轴，不新增第四个语义面。

3. 审计单位：节点有身份，边有权限

工件节点登记它是什么，消费边登记谁以什么作用、在什么 context 中使用它。

4. 工件角色分类

theorem、checker receipt、lowering、measurement、gate、archive 与 publisher 各有不同的正确性关系和默认能力。

5. 作用边分类

验证边、引用边、执行边、测量边和晋级边不得因连接同一个工件而合并。

6. 符号判据：角色给模板，消费边给终判

最终符号由 source role、consumer、runtime binding、effect kind、target claim 和 context 联合决定。

7. Rejector、Constructor 与 Exact Checker 的关系式

排除器要求拒绝集不超出定理，构造器要求产物落在已证有效集，精确 checker 要求双向等价。

8. 每条消费边的三轴裁断

每条边分别给出 semantic correctness、capability admission 和 utility evidence，禁止压成总分。

9. 出生证、换证与晋级证

首个新作用边、消费位置变化、作用域扩张、能力扩张和跨域迁移分别触发不同级别的人工查验。

10. 先专用后通用的机器化节奏

第一例用专用合同和专用 canary 守住，待 2 至 3 个同型实例稳定后再抽象通用 schema 与 checker。

11. Research receipt 顶层协议

所有可跨组件消费的 receipt 必须声明 result kind、typed outcome、verified scope、authority basis、granted effects 和非蕴含边界。

12. 可执行消费合同

每条 theorem→consumer 边必须绑定来源身份、消费者位置、runtime literal 映射、语义关系、权限边界和失败动作。

13. 前提指纹与 context currency

前提、作用域或 consumer binding 漂移使对应 context 下的 edge 进入 STALE，旧消费立即失效而不是继续幽灵运行。

14. typed null 与 reachability

测得零、作用域必零、未建对象、未测、删失和传感器未验证必须使用不同机器状态，且与 NOT_REACHED 等触达状态正交。

15. 能力向量而非 authority 阶梯

IMPLEMENTED、VERIFIED 与 experiment／production grants 是独立 facet，机器准入只认精确 granted effects。

16. 条件事项记录

LATENT_ASSET、CONDITIONAL_DEBT 和 MEASUREMENT_GAP 作为独立 condition records 指向同一资产，其状态按 context 和时间计算。

17. 一库三账一流水

规范化 identity/event source 生成知识、能力、期权三本只读存量投影，每次实验只追加成本与三类 delta 的交易流水。

18. TYPED_OPTION 与 UNTYPED_ARCHIVE

已知 coupling 的资产承担主动扫描和维护成本，尚无可表达 coupling 的有效成果进入冷档案，重新使用前必须重新类型化和复验。

19. SHADOW 到 RESEARCH_ACTIVE

新 lowering 必须先记录 would-reject 而不改模型，通过负 canary 和 contract replay 后才能获得 research execution grant。

20. 失败语义：控制面 BLOCK，数学面 NO_EFFECT

晋级申请未获裁时阻断能力迁移，运行合同异常时撤掉新作用并返回 INVALID／UNKNOWN，绝不把候选判成 INFEASIBLE。

21. 跨域单向边界

research 可以读取 certified 真源作实验输入，certified 不得 live-import research code、receipt 或 registry。

22. Certified promotion 重新铸造

研究 theorem 进入认证路径必须由 owner 决定、certified sink 重验、独立 lowering checker 和认证侧实现共同构成新变更包。

23. 常设闸吞吐成本

所有常设闸必须登记保护对象、单位成本、测量状态、误挡率、复审触发器和 sunset／reapproval 条件。

24. 审计线止步线

审计线不做综合质量评分、不替 owner 决策、不普遍强制预注册，也不接管 theorem 发现与实验选题。

25. W0 第一号 canary 的最小实例化

W0 只允许把精确 active_output_slot(041,0) lowering 为 binding-stage 禁用该活动 slot，不得提升成 pose ban、跨布局 family rule 或 certified cut。

26. 机器验收与负 canary

错误 slot、错误 pose、移动 rectangle、换 layout、stale premise、错误 consumer stage 和伪造 grant 都必须使 lowering 退回 NO_EFFECT。

27. 明确否决的做法

禁止第四个混合语义面、裸 PASS 消费、receipt 自铸 authority、合同失败时拒候选、default-off certified 暗管、最终 checker 代替零误杀证明和研究标签原地升格。

六、必须由 owner 裁决才能定的事项

下面这些不是纯技术推论，必须由 owner 决定后才能成为现行义务。

1. 官方概念模型的命名

是否正式采用“三语义面＋研究运行域”，以及是否修改现行三面方法文档的 canonical 表述。

我的建议是不设第四个语义面，但是否改变项目级术语属于 owner 权限。

2. 第一条 W0 lowering canary 是否解冻

当前 D3 family compilation 与 D4 paired A/B 仍是 DEFERRED_BY_OWNER，任何真实模型消费都需要 owner 明确授权。

3. Research canary 的代码落位边界

是否继续坚持 src/ 零修改，还是允许某个明确隔离的非认证模块进入 tracked code surface。

现行 ROADMAP.md:69 的默认是 research 模块内实现，触及 src/ 即停下过审。

4. Research receipt 协议何时成为强制门

哪些 receipt 必须采用 result_kind + granted_effects，是先对新 theorem pipeline 生效，还是回扫全部研究 checker。

5. Theorem registry 的物理家址

未来 registry 是进入 rules/derived/ 同型子结构，还是独立 research registry；当前 OD-B1-THEOREM-REG-01 只登记了触发后对齐义务，没有选定实现。

6. Research feedback 与 certified cut framework 是否合流

在 family 普遍性未通过前继续两套独立设计；真正合流需要 owner 决定是否复用 typed cut registry、lifecycle 和 production promotion。

7. Capability grant 的正式枚举

尤其需要决定：

production 与 certified 是否分开；

谁可授予 research pruning；

谁可授予 certified pruning；

U/L update、strong-status mint、publication 分别由哪个 sink 授权。

8. 跨面边界事件的 SLA

是否设固定裁决期限、由谁接单、逾期何时进入 EXPIRED_BLOCKED，以及什么情况必须立即停用现有边而不是只阻断新晋级。

9. 常设闸的成本预算与复审阈值

哪些闸必须测人时、墙钟和误挡率，何种成本或连续低收益触发 owner 复审，是否设置 sunset。

10. 一库三账一流水的项目级落地

是否把现有 knowledge ledger、rules/derived/、未来 theorem registry 和 option registry 纳入同一规范化事件／投影架构。

11. 冷档案的准入边界

哪些资产允许进入 UNTYPED_ARCHIVE，以及怎样防止把当前债务、阻断义务或现行 consumer 依赖洗成冷档案。

12. 预注册的项目级适用范围

审计线本身不普遍强制预注册，但哪些因果实验、go/no-go 批或高成本 campaign 必须预注册，仍需由 owner 或相应实验协议裁定。

以下几条不应推给 owner，因为它们是方法内部的逻辑后果：

rejector 的 lowering 不得拒绝 theorem 未证明可拒绝的对象；

theorem PASS 不自动产生 granted effects；

数学合同异常时必须 NO_EFFECT，而不是拒候选；

测量删失、未测和 sensor 未验证不得写成零；

research→certified 必须重新铸造，不能靠改标签完成；

活跃 consumer 所依赖的事项不能被扔进冷档案逃避维护。

最终合并设计可以压成一句话：

保留三种语义，增加一等研究运行域；以消费边为审计对象，以角色关系判正确性，以 capability token 判权限，以 typed observation 判效用，以出生证、换证和重新铸造管理生命周期。
