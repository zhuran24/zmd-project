<!-- 三面模型 v2 文档批异源审计报告（2026-08-16） -->
<!-- 审计方：四席 Claude Opus 并行（异源纪律：GPT 源产出派 opus 推翻）；席位=内容保真/坐标结构/裁决请求专审/薄弱三处深攻 -->
<!-- 被审对象：本 dossier 三文件的主笔初稿（GPT Pro 落地段产出） -->
<!-- 汇总：blocker=4 major=32 minor=22 note=4；修订处置见各条「建议修法」与修订批记录 -->

# 审计汇总 counts={'blocker': 4, 'major': 32, 'minor': 22, 'note': 4}


## 席位：内容保真

**总裁定**：主文档 0-27 节的实体主张总体忠实于对撞裁断——八处修正无一滑回盲答旧口径，附录六条逻辑后果与底本逐条一致，27 节骨架与 owner 十二项待裁清单完整落地，B 段内容均标注出处未冒充本仓原生结论。但审计发现一处越权裁断（§0.2 与 README 把 v1 符号判据的 supersede 写成既成事实，而同批 OWNER_DECISION_REQUEST #1 和底本 owner 事项 1 都把它列为 owner 待裁）、一处把待裁选项写进规范表（§20 baseline 行擅加"除非另有完整性风险裁定"豁免口，该豁免既非底本口径、又与冻结的 03A 协议 :41/:50 无条件保证冲突、且正是 ODR #8 选项 C 的待裁内容）、三处底本规范件整段失落（authority bridge 的 requested_effects ⊆ granted_effects 关系式、对撞"certified 摘要不变不是边界充分条件"这条明确纠错、⑤ 已裁采纳的跨面边界事件固定格式十二字段），以及底本溯源上的实质缺注：两份存档的 conversation id 完全相同，丙与合并实为同一 GPT Pro 线程的第一、二段（对撞段自陈"我对盲答的核心判断仍然维持"），而 §0.1 却以"稳健度不来自同一作者反复润色"作为方法权威的立论；丁被断言为"GPT Pro 线程"却在本批无任何出处，其 B 段逐字底本也未进 sources/，导致 §13-§18 六节全部只有对撞段的转述本。此外对撞段自引坐标有四处指错，§24 引用与所指内容零重叠。


### [BLOCKER] 内容保真-1 @ TRI_PLANE_MODEL_V2.md:32（§0.2）+ README.md:42（v1 关系索引 1）
越权裁断。§0.2 写「因此，v2 **取代** FIRST_PRINCIPLES_DESIGN.md :633-641 的符号判据表述」，README 写「符号判据：v2 supersede」，均为无条件的既成宣告。但同批 OWNER_DECISION_REQUEST.md §1 把这件事整项列为「待裁」，其选项 B 明确是「只在本 dossier 内使用，项目其它入口继续保留旧的『按面判符号』说法」——若 owner 选 B，§0.2 的「取代」当场作废。底本对撞段 owner 事项 1（collision:1082-1086）也写死「是否修改现行三面方法文档的 canonical 表述……属于 owner 权限」。README:46 又说 v1 文件、方法论入口、生成页的同步「须走后续受控批次」，说明这个 supersede 被理解为项目级而非 dossier 内局部，进一步坐实越权。文档在同一批次里既申请裁决又替 owner 裁了。

**建议修法**：把 §0.2 与 README 的 supersede 改成条件式：「若 owner 按 OWNER_DECISION_REQUEST #1 选 A，则 v2 取代 …… ；在裁决前 v1 :633-641 仍为现行表述，v2 的角色/边判据在本 dossier 内适用」。并在 §0.2 显式回指 ODR #1。


### [MAJOR] 内容保真-2 @ TRI_PLANE_MODEL_V2.md:14,18-20（§0.1）+ README.md:28-36（来源结构）
底本溯源缺注，且缺注方向恰好抬高了文档权威。两份存档的头部注释显示 conversation id 完全相同（均为 6a818168-53c8-83ea-b57b-a697d1ec557b），即丙（盲问段）与「合并」（对撞段）是同一 GPT Pro 线程的第一、二段，对撞段 collision:10 自陈「我对盲答的核心判断仍然维持」、并设专章「四、我的盲答需要撤回或修正什么」——它对丙是自审，不是独立裁断。而 §0.1 恰恰以「其稳健度不来自同一作者反复润色，而来自不同起点对同一接缝的收敛」作为整套方法权威性的立论。此外丁被断言为「另一条独立 **GPT Pro** 线程」，但两份底本对丁只写「另一外审线程」（collision:3），全批无任何材料支撑丁的模型身份；若该断言为真，则丁的 B1-B5 是由同源（GPT Pro）的对撞段独家裁断后进入方法的，全程无异源交叉，而 §13-§18 六节全部建立在这批内容上。本仓 memory 对「同源核查链会共犯地漏掉同一处」有在案实证，此处正是该风险的实例，文档未作任何标注。

**建议修法**：§0.1 与 README 来源结构补注三点：①丙与合并同属一个 GPT Pro 线程（给出 conversation id），对撞段对盲答是自审段，其独立性只对甲乙、丁成立；②丁的模型身份在本批无出处，标为未确认，或补出处；③若丁同为 GPT Pro，明写「B1-B5 的采纳裁断为同源，尚未过异源交叉」，并把该缺口挂成条件事项。同时把「稳健度不来自同一作者反复润色」改成只对甲乙↔丙这一对成立的准确表述。


### [MAJOR] 内容保真-3 @ TRI_PLANE_MODEL_V2.md:266-378（§13-§18）+ sources/ 目录
结构缺失：丁的 B 段裁断逐字底本未进 sources/。README:23-24 的文件清单只列丙、合并两份存档，全仓搜索 TYPED_OPTION / UNTYPED_ARCHIVE / typed null 也只命中本 dossier 三份文件与对撞段本身，说明丁的原文在仓内不存在。结果是 §13（state(a,c)）、§14（typed null 七态）、§15（能力四层拆 facet）、§16（条件事项记录）、§17（一库三账一流水）、§18（TYPED_OPTION/UNTYPED_ARCHIVE）六节的全部规范内容，仓内唯一可回溯的凭据是对撞段的二手转述。这与本 dossier 自设的「逐字保存，不作编辑」存档纪律不一致，也使读者无法核对对撞段对 B1-B5 的「改造后采纳」究竟改造掉了什么。

**建议修法**：补入丁的 B 段逐字存档为 sources/ 第三份；若原文已不可得，在 §0.1 与 README 文件清单显式标注「丁的逐字底本未存档，§13-§18 的可回溯凭据仅为对撞段转述」，并登记为待补件。


### [MAJOR] 内容保真-4 @ TRI_PLANE_MODEL_V2.md:151（§7）与 247（§12 第 3 组）
底本规范件失落：authority bridge 的关系式整条丢失。对撞段 collision:311 给出五种角色关系中的第五条「authority bridge：requested_effects ⊆ granted_effects」，这是「按角色分型最小契约」（八处修正之第 3 处）的组成部分。全批三份文档 grep `requested_effects` 零命中。§7 用「authority bridge 只能授予具名 effect，不能借用其它角色的 PASS」顶替——但这是在描述桥「授予」什么，底本要求的却是桥必须校验「请求的能力包含于已授予的能力」，方向与检查对象都不同：按文档的写法，一个只授具名 effect 的桥仍可越过它自己被授予的范围。§12 第 3 组只列了五个角色名而不给任何关系，因此这条关系在全文没有任何落点。

**建议修法**：§7 补回 `requested_effects ⊆ granted_effects`，与 rejector 的 `R_L ⊆ R_T`、constructor 的 `W_constructor ⊆ W_proven_valid` 并列成式；§12 第 3 组至少回指 §7 的五条关系。


### [MAJOR] 内容保真-5 @ TRI_PLANE_MODEL_V2.md（全文）；对应底本 collision:523-525
底本明确纠错整条失落：「把『certified 摘要不变』当成认证边界的充分条件」。这是对撞段「二、我方六点提案错了什么」八条里的第 5 条，且对撞段在 collision:333-341 给出了具体理由——摘要不变不代表 certified runtime 没有 import research code、source digest 没变、strong-status 写点没增加、认证 loader 没接受 research schema。全批三份文档 grep「摘要」零命中。其余七条错误在文档里都有落点（第四面→§27.1/§2；角色非终判→§6；receipt 自铸 authority→§11；一个见证→§12;2-3 实例→§10；超时阻断对象→§20；符号例子过强→§6），唯独这一条无家。它针对的正是本仓甲乙提案，遗漏意味着本仓可能继续把「certified 摘要不变」当验收充分条件。

**建议修法**：在 §12 第 4 组（权限与边界）或 §21 补一段：certified 摘要/diff 不变可作验收项，不能代替真实边界检查，并列出摘要不变仍可能漏掉的四类越界；或作为 §27 的第 13 条否决项。


### [MAJOR] 内容保真-6 @ TRI_PLANE_MODEL_V2.md:392-408（§20）+ OWNER_DECISION_REQUEST.md:140-154（§8）；对应底本 collision:444-468
结构缺失：跨面边界事件的固定格式十二字段整块未落。对撞段 ⑤ 的裁断是「修正后采纳」（collision:377），采纳内容包含固定格式边界事件「至少包含」的十二项：source asset、current domain、target domain、requested effects、将触碰的路径和 schema、consumer entrypoint、reversibility、rollback、throughput cost、owner/sink、decision deadline、未裁时阻断范围。文档把 ⑤ 的另一半（控制面 BLOCK 与数据面 NO_EFFECT 之分）完整写进了 §20，却没有任何一节承载这份字段表——grep reversibility / rollback / 可逆 / 回滚全批零命中。对照之下 §11 落了 receipt 八字段、§12 落了合同五组、§23 落了常设闸十字段，唯独边界事件格式缺位。注意这不属于 owner 待裁：底本 owner 事项 8 只把 SLA（时限、接单人、逾期动作）留给 owner，格式本身已裁定采纳。

**建议修法**：在 §20 增设「跨面边界事件固定格式」小节，落十二字段；ODR §8 的问题范围相应收缩为只问 deadline 与逾期/紧急停用条件。


### [MAJOR] 内容保真-7 @ TRI_PLANE_MODEL_V2.md:404（§20 表末行）
把待裁选项写成规范默认动作。表行「baseline research 已获准，另一项晋级申请超时 → baseline 不因无关申请自动停用，**除非另有完整性风险裁定**」。底本 collision:438 的对应行是无条件的：「原有 baseline research 已获准 → 不因另一项晋级申请超时而自动停掉」，无任何例外口。更重的是，已冻结的 03A 发射前协议两处也写成无条件保证（:41「不……停掉已经明确获准的 baseline research」、:50「已经获准的 baseline research 不因该状态自动失效」）。而这个例外口的实质内容正是同批 ODR §8 选项 C 的待裁事项（「只有出现 theorem/contract identity 破坏、stale premise 仍在生效或认证资产越权写入等完整性证据时，才立即停用当前边」）。文档先在方法正文里把待裁选项装成默认，再回头请 owner 裁同一件事。

**建议修法**：§20 该行恢复底本无条件表述；把「完整性事件可停用现有边」单独标为待裁（回指 ODR #8 选项 C），不进规范表；或明写「本行在 ODR #8 裁定前按无条件解释」。


### [MAJOR] 内容保真-8 @ TRI_PLANE_MODEL_V2.md:118（§6）
漂移，且丢掉的正是纠错所指的那一项。§6 写「把 theorem 收窄可以保持 soundness，但要登记被移除区域为 UNKNOWN，并同步更新 ID、fingerprint 与 consumer」。底本 collision:230 的校准行是「成立，但所有 ID、fingerprint、consumer **和 lowering** 必须同步收窄」——文档漏掉 lowering。这不是可省的第四项：对撞段 collision:202-204 给出的整条论证就是「定理收窄，单看 theorem 节点是安全但有债；但旧 lowering 若仍按原宽范围运行，整条消费边已经 unsound」。同时「必须同步收窄」被弱化为「同步更新」，语义强度下降。按文档现行写法，收窄 theorem 后只改 ID/指纹/consumer 而 lowering 仍按旧宽范围运行，是被允许的读法。

**建议修法**：§6 补回 lowering 并恢复「必须同步收窄」的强度，最好一并写出对撞段的理由句（旧 lowering 按原宽范围运行会使整条消费边 unsound）。


### [MAJOR] 内容保真-9 @ TRI_PLANE_MODEL_V2.md:247(§12)、408(§20)、467(§23)、479(§24)、136(§6) 的对撞段自引坐标
坐标错：五处对撞段自引行号与所指内容不符，其中一处零重叠。实测底本锚点：④ 五项最小契约 :261-364、止步线 :365-374、⑤ :375-468（控制面 BLOCKED :381、数据面 NO_EFFECT :405、共存表 :431-442、固定格式 :444-468）、⑥ :470-503、③-B :189-259。对照：§24「对撞段的止步线裁断见 :398-421」——该区间整段落在 ⑤ 的 EXPIRED_BLOCKED/NO_EFFECT 里，与止步线（:365-374）**零重叠**；§12「五组合同的修订见 :316-421」——五组实际在 :265-364，所引区间漏掉第一至三组（正是文档 §12 的 1-3 项）且溢出到 ⑤；§20「两种 BLOCK 的正面区分见 :422-481」——正面区分在 :379-442，所引起点已越过两个定义段、终点溢入 ⑥；§23「材料一第六点的采纳结论见 :482-503」——采纳裁断句在 :472，落在区间外；§6「见 :199-315」——③-B 的关键关系句「角色给出局部符号模板，消费边给出最终符号」在 :193-197，落在区间外，且区间溢入 ④。因不是同一偏移量，无法用「按另一版本行号计算」一次性解释，需逐条重算。（其余对撞段与全部盲答、仓内文件引用经抽查均正确：B1-B5 :568-866、骨架 :962-1156、附录 :1142-1156、blind :36-160/:162-210/:822-950 以及 ARCHITECTURE_SKETCH、01_JUDGMENT、03_check、rules/derived、03A 等全部落点无误。）

**建议修法**：按实测锚点重算五处：§24→:365-374；§12→:261-364；§20→:379-442；§23→:470-503；§6→:189-259。


### [MINOR] 内容保真-10 @ TRI_PLANE_MODEL_V2.md:260（§13）
坐标错兼内部枚举不自洽。§13 写「W0 theorem 在 pinned W0 context 中可以是 VERIFIED；对另一个 layout 或 rectangle，它可能是 NOT_APPLICABLE」。底本 collision:702-706 用的是「可 ACTIVE ……应当 NOT_APPLICABLE 或 STALE」，即 activation/适用性轴。文档换成 VERIFIED 后，同一句里的 NOT_APPLICABLE 已不属于它自己在 §15 定义的 verification_state 枚举（UNVERIFIED|VERIFIED|REFUTED|STALE），造成一句话跨两根轴取值。B3 的原意恰是强调 rules/derived 的 ACTIVE/STALE 机需要按 context 索引，换词把这层意思也一并抹掉了。

**建议修法**：恢复底本用词：pinned context 下 ACTIVE，异 context 下 NOT_APPLICABLE 或 STALE；或明写这是 §15 之外的第五根「适用性/activation」轴并给出枚举。


### [MINOR] 内容保真-11 @ TRI_PLANE_MODEL_V2.md:60（§2）
坐标表述不自洽。§2 是定义两轴坐标系的节，底本 collision:175-183 的五个例子第一轴一律是「面」（research receipt = 档案/证据面 × 研究域，research admission gate = 发布/准入面 × 研究域）。文档在同一段里把前两例改成「证据/档案**角色** × RESEARCH」「发布/准入**角色** × RESEARCH」，第三例又用「发布**面** × CERTIFIED」。「角色」在本文档 §4 是另一套独立分类（theorem/receipt/lowering/measurement/gate/archive/publisher），在定义坐标系的地方把两轴之一的取值换成另一套分类的名字，会让读者误以为坐标第一轴是角色轴。

**建议修法**：§2 五个例子统一用「面」；若确要点出 receipt 同时具有档案面身份与 checker receipt 角色，另起一句说明两者关系，不要混进坐标式。


### [MINOR] 内容保真-12 @ TRI_PLANE_MODEL_V2.md:118（§6）
强度漂移。底本 collision:229 的校准行是「未经新证明而加宽才是 unsound；重新证明后的加宽完全合法」——这是一条双向校准，前半纠正「加宽＝unsound」的过强说法，后半明确合法加宽不该被误判。文档只保留前半且弱化为「未经新证明把 theorem 加宽会造成 scope 失真」（「失真」弱于底本的 unsound），后半「重新证明后的加宽完全合法」全文无对应。§27.9 只否决了「把局部 theorem 方便地写宽」，不覆盖「已重证的加宽合法」。在本仓「保守不是美德、方向盘常态朝上」的口径下，丢掉合法加宽这一半是有方向性的损失。

**建议修法**：§6 恢复双向表述：未经新证明的加宽是 unsound，重新证明后的加宽完全合法且不记债。


### [MINOR] 内容保真-13 @ TRI_PLANE_MODEL_V2.md:175-179（§9）
底本枚举被裁剪。对撞段 collision:33-45 列了六种「即使没有新文件类型也必须重新查验」的情形，文档 §9 把它们分派进出生证/换证/晋级证时丢了两处：①换证段写「同一合同开始跨布局或跨 family 复用」，底本原文是「跨布局、跨 family **或跨运行域**复用」——跨运行域（research↔certified）是三者中风险最高的一项，全批 grep「跨运行域」零命中；②底本第 3 项「同一 research PASS 第一次被 certified 文书承重引用」在三张证里都没有明确落点（晋级证只写到 publication、terminal mint、认证账更新，不含 certified 文书的承重引用）。三证分派本身是文档的合理解读（底本只给了「出生证＋换证＋晋级证」的名目未作分派），但分派过程不应漏项。

**建议修法**：§9 换证补回「跨运行域复用」；把「research PASS 首次被 certified 文书承重引用」明确归入出生证或晋级证。


### [MINOR] 内容保真-14 @ TRI_PLANE_MODEL_V2.md:306（§15）+ OWNER_DECISION_REQUEST.md:129（§7 选项 B）
能力令牌枚举漏一项。底本 collision:673-681 列九个 token，文档 §15 与 ODR §7 选项 B 一致地漏掉 `OWNER_DECISION`。这一项不是可省的凑数项：盲答 blind:475 把 owner_decision 列在 forbidden_effects，配合 blind:477「普通边只能保持或减少能力，只有具名的 owner gate 或 certified sink 才能增加能力」——`OWNER_DECISION` 正是让「边不能自升权、只有 owner 闸能加能力」这条规则在 token 层面可机器表达的那一枚。漏掉它，§15「机器只认 token 集合」的模型里就没有 owner 权限的位置。

**建议修法**：§15 与 ODR §7 选项 B 的 token 清单补 `OWNER_DECISION`，并说明它只能由具名 owner 闸持有、不可由任何边请求。


### [MINOR] 内容保真-15 @ TRI_PLANE_MODEL_V2.md:201-212,216-223（§11）
应补注而未补注：typed outcome 的取值范围缺失。§11 的节引明确要求 receipt 声明「typed outcome」，字段表也列了 `outcome`，但全节没有说明 typed outcome 到底取什么值——只在 W0 例子里出现一个 `VALID`。底本 collision:86 给了明确枚举：「outcome 不再只有 PASS/FAIL，而是按类型给出 VALID、INVALID、UNKNOWN、CENSORED 等」，且 CENSORED 与 §14 的 typed observation 轴有直接呼应。§11 是本文档给机器接口下定义的地方（receipt 八字段、合同五组、闸十字段都在各自节里给全），此处独缺取值，实现方无法据本节写 schema。

**建议修法**：§11 补上按 result_kind 分型的 outcome 取值示例（VALID/INVALID/UNKNOWN/CENSORED/ADMITTED 等），并注明该枚举随 result_kind 而定、不是全局固定集。


### [MINOR] 内容保真-16 @ TRI_PLANE_MODEL_V2.md:20（§0.1 末句）
自述的底本使用口径与实际引用不符。§0.1 写「本文以对撞段为底本，盲答只补充未被重复展开的 W0 六步实例与十二条拒绝理由」，但正文实际从盲答取材远不止这两处：§3 引 blind :162-210（作用边模型与四种边）、§7 引 blind :336-450（集合关系推导）、§19 引 blind :879-914（SHADOW/RESEARCH_ACTIVE 两阶段）。§0.1 是本 dossier 的溯源契约节，读者据它判断每节该回哪份底本核对，口径与实际不符会让核对落空。

**建议修法**：§0.1 末句改为如实列举盲答的实际取材范围（作用边分类、集合关系推导、SHADOW/ACTIVE 两阶段、W0 六步、十二条拒绝），或改成「盲答用于对撞段未重复展开处，逐节以在案证据标注为准」。


## 席位：坐标结构

**总裁定**：机械层面主笔的自称基本属实：94 个相对链接全部解析成功、无缺文件，全部约 107 个行号区间（96 个链内 + 11 个脚注内）均在文件范围内且格式合法，28 个编号节 0-27 齐备、节引与底本骨架 collision_verdict_20260816.md:966-1076 逐字一致、除第 0 节外 27 节均有在案证据段、附录六条与 :1144-1154 对应、README 文件清单与目录实物一致。真正的问题出在两处机械核查不到的地方。其一是权威锚：OWNER_DECISION_REQUEST 第 2 项——全文唯一标【已裁】的事项——靠一句全仓仅此一处、且与既有冻结授权存录 00_OWNER_AUTHORIZATION_20260816.md:7-8 不同源的 owner 引文关闭，无任何仓内坐标，这是不修不能提交的一条；同时主文档 §0.2 与 README:42 已把「v2 取代 v1 符号判据」写成既成事实，而 OWNER_DECISION_REQUEST 第 1 项恰恰把这件事整个列为待裁且选项 B 是「只在本 dossier 内使用」，构成三文档间的直接矛盾与一次替 owner 完成的投影裁断。其二是坐标与内容的对应：对撞段的引用明显是按行号连续切块分配的（20-198 / 199-315 / 316-421 / 422-481 / 482-503），不是按内容定位，导致 §24 的止步线引到了 BLOCK 段（零重叠）、§12 的五组合同漏掉第一至第三组、§20 的两种 BLOCK 漏掉两个平面的定义、§23 漏掉「裁断：采纳」与四个字段。此外 §7 把最高优先底本的逐字公式记在次优先底本名下，主文档全文不回指 OWNER_DECISION_REQUEST，README 阅读路径漏掉 §9、§10。共 16 条，1 blocker、4 major、9 minor、2 note。


### [BLOCKER] 坐标结构-1 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:48-51
第 2 项是全文唯一标【已裁】的事项，其关闭完全依赖一句 owner 逐字原话「先开吧,不过我想着先开一个,然后剩下一个空位交给右边」，但该字符串在全仓（.md/.json 全文检索）只出现在本文件自身，没有任何仓内存录坐标做锚。同一金丝雀已有冻结的授权真源 docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/00_OWNER_AUTHORIZATION_20260816.md:7-8，其中记的「授权原句」是另一段完全不同的文字（「owner 信号落地：金丝雀解冻，整包归你——冻结协议→落库→实现→跑→报告，一条龙……」）。本文件的两条脚注 [^roadmap-g][^canary-addendum] 只覆盖边界语义，不覆盖这句裁定本身。等于用一句无法核验、且与既有冻结存录不同源的引文关闭了一个 owner 决策项；第 54 行「另一空位按 owner 原话留给右侧工作线」同样悬空（「空位」「右边」在仓内无任何指称）。

**建议修法**：要么补上该原话的仓内窄逐字存录坐标（照 ROADMAP A14 引用的 OWNER_INSTRUCTION_20260815.md 先例建一份），并说明它与 00_OWNER_AUTHORIZATION_20260816.md:7-8 的关系（是同一次信号的另一段，还是另一次信号）；要么把第 2 项的状态从【已裁】退回，改为引用 00_OWNER_AUTHORIZATION_20260816.md 的既有原句。


### [MAJOR] 坐标结构-2 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:32（并同 README.md:42）
主文档 §0.2 无条件宣告「v2 **取代** FIRST_PRINCIPLES_DESIGN.md:633-641 的符号判据表述」，README 第 42 行同样写「符号判据：v2 supersede」。但同批的 OWNER_DECISION_REQUEST.md:26-40 把这件事整个列为第 1 项【待裁】，且选项 B 明写「只在本 dossier 内使用，项目其它入口继续保留旧的『按面判符号』说法」。owner 若选 B，主文档这句话即为假。这既是三份文档之间的直接矛盾，也是 dossier 在自己声明「本目录不授予 authority」（README:6、主文档:6）的前提下替 owner 完成了一次投影裁断。底本亦不支持这种既成事实口吻——collision_verdict_20260816.md:1086 明写「我的建议是不设第四个语义面，但是否改变项目级术语属于 owner 权限」。

**建议修法**：把 §0.2 与 README 第 42 行改成条件式：「本 dossier 内采用『角色给模板、消费边给终判』；是否升为项目级并取代 FIRST_PRINCIPLES_DESIGN.md:633-641，属 OWNER_DECISION_REQUEST 第 1 项待裁」，并加指向该请求的链接。


### [MAJOR] 坐标结构-3 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:479
§24 在案证据写「对撞段的止步线裁断见 collision_verdict_20260816.md:398-421」。该区间与止步线毫无关系：398-421 是控制面 EXPIRED_BLOCKED 与数据面 NO_EFFECT 的定义段（属 §20 的内容）。底本的「止步线」小节在 :365-373（365 行标题「止步线」，367 行「审计线不做质量评分」采纳，369-373「审计线不强制预注册」及其含义）。这是零重叠的坐标错误。

**建议修法**：改为 `collision_verdict_20260816.md` `:365-373`。


### [MAJOR] 坐标结构-4 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:247
§12 在案证据写「对撞段对五组合同的修订见 collision_verdict_20260816.md:316-421」。底本的五组合同在 :261-364（261「④ 五项最小契约与止步线」，269 第一组来源身份，283 第二组消费者与运行时绑定，299 第三组语义关系，315 第四组权限与边界，343 第五组新鲜度与失败动作，359-364 写死 contract mismatch → no effect）。所引 316-421 把第一至第三组（:269-313）整段排除在外——而正文第 237-239 行恰恰逐条复述的就是这三组；同时 316-421 又吞进了止步线（365-373）和 ⑤ BLOCK 段（375-421），那属于 §24 与 §20。

**建议修法**：改为 `collision_verdict_20260816.md` `:261-364`。


### [MAJOR] 坐标结构-5 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:408
§20 在案证据写「对撞段对两种 BLOCK 的正面区分见 collision_verdict_20260816.md:422-481」。两种 BLOCK 的正面区分在 :375-442（375「⑤ 跨面边界事件固定格式」，381-403 控制面 BLOCKED，405-429 数据面 NO_EFFECT，431-438 场景表，440-442「BLOCKED 挡的是能力迁移，NO_EFFECT 保的是数学可行域」）。所引 422-481 只截到该段尾巴，把两个平面的定义全部漏在外面，却把 :444-468 的边界事件格式清单（对应 OWNER_DECISION_REQUEST 第 8 项）与 :470-481 的 ⑥ 常设闸（属 §23）纳入。

**建议修法**：改为 `collision_verdict_20260816.md` `:375-443`。


### [MINOR] 坐标结构-6 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:467
§23 在案证据写「材料一第六点的采纳结论见 collision_verdict_20260816.md:482-503」。⑥ 的标题与裁断在 :470-472（「⑥ 常设闸必须标吞吐成本」/「裁断：采纳」），十字段清单在 :476-488，其中 protected_risk / effect_scope / per_item_cost / per_run_cost（:478-481）落在所引区间之外——而正文第 450-461 行正是逐字抄这十个字段。所引区间恰好漏掉了「采纳结论」这句本身。

**建议修法**：改为 `collision_verdict_20260816.md` `:470-503`。


### [MINOR] 坐标结构-7 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:153
§7 的核心公式与三种读数直接来自最高优先底本 collision_verdict_20260816.md:236-259（R_theorem(c) ⊆ D(c) - F(c)；R_lowering(c) ⊆ R_theorem(c)；R_L = R_T 精确编译 / R_L ⊂ R_T 安全但少剪 / R_L ⊄ R_T 错误剪枝），constructor、exact checker、ledger updater、authority bridge 四种关系亦逐条来自 :299-311。但 §7 的在案证据只引 blind_answer_20260815.md:336-450（次优先底本）与两处仓内先例，完全没有引对撞段。按本 dossier 自定的底本优先级（README:34「本文以其为底本」），这是把最高优先来源的逐字内容记在次优先来源名下。

**建议修法**：在 §7 在案证据中补 `collision_verdict_20260816.md` `:236-259,299-313`，并保留 blind 的坐标作为盲态独立推导的旁证。


### [MINOR] 坐标结构-8 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:64
§2 在案证据引 collision_verdict_20260816.md `:6-16,20-198` 作「对撞段对『第四面』的正面裁断」。第四面的正面裁断实际在 :125-198（125「③-A 研究面升为第四个对等面」、127「拒绝」、155、187）。所引的 20-124 是 ①（出生证/换证/晋级证）与 ②（receipt 顶层协议）两段，分别属于 §9 与 §11，与第四面无关，属过宽引用。

**建议修法**：改为 `:6-16,125-198`。


### [MINOR] 坐标结构-9 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:532
§27 在案证据引 blind_answer_20260815.md `:952-1037` 作「十二条完整理由」。第十二条（:1029「把三面审计线变成所有研究批次的常驻审批者」）的正文延伸到 :1041（1031-1041 是其理由与正确分工四项），所引区间在 1037 截断，恰好切掉了正文第 530 行「机器管实例，人工管 first-of-kind、换证和晋级」所依据的 :1037-1041。

**建议修法**：改为 `:952-1041`。


### [MINOR] 坐标结构-10 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md（全文）
主文档全文没有任何一处提到或链接 OWNER_DECISION_REQUEST.md（已 grep 确认零命中）。附录 A 只说「以下六条不需要 owner 在每个实例上重新决定」，却不告诉读者「需要 owner 决定的十二条在哪」。方向是单向的：OWNER_DECISION_REQUEST.md:4 指向主文档附录 A，主文档不回指。从主文档入场的读者（README:50 也只说「需要 owner 拍板时直接阅读 OWNER_DECISION_REQUEST」，那是 README 的路径）无法从附录 A 走到待裁清单。

**建议修法**：在附录 A 开头或结尾补一句并链接：「需要 owner 决定的十二项见 [`OWNER_DECISION_REQUEST.md`](OWNER_DECISION_REQUEST.md)。」


### [MINOR] 坐标结构-11 @ docs/research/tri_plane_model_v2_20260816/README.md:50
快速阅读路径给出四段：0-8、11-20、21-24、25-27，第 9 节（出生证、换证与晋级证）与第 10 节（先专用后通用的机器化节奏）不在任何一段里——而这两节正是底本 ① 的核心裁断（collision :20-64）且被 OWNER_DECISION_REQUEST 第 3、4 项直接依赖。另外「要看跨认证边界，转第 21 至 24 节」的标签与内容不符：§23 是常设闸吞吐成本、§24 是审计线止步线，都不属于跨认证边界（那是 §21-§22）。

**建议修法**：路径改为覆盖 0-10、11-20、21-22（跨认证边界）、23-24（治理成本与止步线）、25-27（W0 实例与否决清单）。


### [MINOR] 坐标结构-12 @ docs/research/tri_plane_model_v2_20260816/README.md:33 与 TRI_PLANE_MODEL_V2.md:19
两处都把丁描述为「另一条独立 **GPT Pro** 线程的 B 段裁断」。底本自己的身份行 collision_verdict_20260816.md:3 只写「另一外审线程 B 段裁断五件」，没有给出模型身份；collision:4 的模型标注只覆盖对撞段本身。「GPT Pro」是文档在底本之外加的属性，无坐标支撑。相关地，五席中甲、乙、丁三席在 sources/ 下都没有逐字存档（目录只有 blind 与 collision 两份），README「来源结构」段落对此未作说明，读者会以为五席皆可回溯。

**建议修法**：丁改为「另一条独立外审线程」；并在 README「来源结构」末尾补一句：甲、乙、丁三席的原始材料未在本 dossier 内逐字存档，其内容只能经对撞段的逐条转述核验。


### [MINOR] 坐标结构-13 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:225
§11 写「另一份 receipt 才可能报告 `RESEARCH_MODEL_PRUNING`」，但所引底本对应处 collision_verdict_20260816.md:111-113 的 admission 示例是 `granted_effects = [RESEARCH_BINDING_PRUNING]`。底本两个 token 名并存（:113 RESEARCH_BINDING_PRUNING，:674 RESEARCH_MODEL_PRUNING），文档静默统一为后者而未加注。对 §25 尤其要紧：W0 canary 的 consumer stage 固定为 binding，正是底本用 BINDING 命名的那一档。

**建议修法**：在 §11 或 §15 加一句注：底本在 :113 与 :674 出现两个 token 名，本文统一采用 `RESEARCH_MODEL_PRUNING`，`RESEARCH_BINDING_PRUNING` 视为其 binding-stage 具名投影。


### [MINOR] 坐标结构-14 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:487
§25 第二段用陈述语气写「独立消费合同采用 `REJECTOR` 角色，consumer stage 固定为 binding……allowed effect 只含 `RESEARCH_MODEL_PRUNING`」，在案证据只引 blind_answer:822-950（设计稿）与 03A:62-64（授权语义），没有引已在仓的 experiment_two 金丝雀实物。实测该包里并不存在 `RESEARCH_MODEL_PRUNING` 或 `REJECTOR` 字样：06_check_w0_unary_lowering_contract.py:561,609 与 09_run_w0_unary_lowering_arm.py:533,633 的 granted_effects 用的是 `blocks_true_canary_arms`、`may_be_consumed_only_by_the_frozen_three_arm_aggregator` 等描述串。读者会把这段读成对现存包的描述，实际是对设计的规定。

**建议修法**：在 §25 该段前加一句时态限定（「以下为本方法对首号 canary 的规定形态，与 experiment_two 现有冻结件的字段命名不逐字对应」），或补引 04_W0_UNARY_LOWERING_SPEC.json / 06_check_w0_unary_lowering_contract.py 的实际坐标并说明差异。


### [NOTE] 坐标结构-15 @ docs/research/tri_plane_model_v2_20260816/README.md:24
文件清单里把对撞段的输出描述为「27 节骨架」，而该骨架是 0 至 27 共 28 节（collision:966-1076），README 自己在第 20 行也写「按 0 至 27 节」。同一页两种数法。

**建议修法**：改为「28 节（0 至 27）骨架」。


### [NOTE] 坐标结构-16 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:289
§14 引 collision `:568-613`，但正文第 287 行「任何 observation 都不自动授予 capability」对应的底本句在 :615（「任何一种 observation 都不自动授予能力，granted_effects 仍为空」），刚好落在区间外一行。

**建议修法**：改为 `:568-615`。


## 席位：裁决请求专审

**总裁定**：OWNER_DECISION_REQUEST 的十二项与底本 collision_verdict_20260816.md「六、必须由 owner 裁决才能定的事项」一一对应，无凭空新增、无实质同一事项被立成第二笔请求，去重意图明确且多数标注方向正确；但审计面逐条穷尽后共发现 17 处问题，其中一处为 blocker：第 2 项据以关闭的 owner 原话在全仓无逐字存录（本文件是唯一出现处、无出处脚注），且本项未引用该次解冻的授权真源 00_OWNER_AUTHORIZATION_20260816.md，而该真源记的是另一句原话，等于在既有授权链外新立了一份携带额外分配决定的竞争记录。其余 major 集中在四类：①窄授权表述不精确——「右边」被自行解释成「右侧工作线」（仓内唯一在案用法指会话线程），非蕴含清单相对授权存录漏掉家族普遍性外推、certified-exact 上下界外推、production default 与认证/发布表面四类禁止；②去重标注错位或缺漏——第 1 项并联 A14 属坐标错位（A14 限求解面方法论载体，三面线入口是 A12）、第 10 项正文裁掉底本明列的四个具名对象后仍标「新事项」并与第 5 项/OD-B1-THEOREM-REG-01/档案面批 representation_class 裁定权三处漏并联、第 5 项未注明本请求本身即命中 OD-B1-THEOREM-REG-01 触发器、第 4 项选 A 会预决 OWNER_DECISION_SUMMARY 第 5 件并使 A12 触发器失效、第 9 项选 B 以第 7 件获准为前提，均未上桌；③越权自行裁断——第 7 项把底本明列的待裁子问题「production 与 certified 是否分开」降级为代价描述而主文档 §15 已写成结论，主文档/README 又把「v2 取代 v1 符号判据」写成既成事实而第 1 项仍列为待裁；④owner 读者画像不合规——文首承诺「坐标统一放在脚注」但总览表与正文遍布裸坐标，术语块只解释四词而 U/L update、EXPIRED_BLOCKED、六字段收据、删失、Phase -1 等十余个术语首现即用未释。四件套（问题—选项—推荐—代价）与推荐明说这两条本身全项合规，第 2 项作为已裁项的处理形态也正确。


### [BLOCKER] 裁决请求专审-1 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:48-52
第 2 项据以关闭的 owner 原话「先开吧,不过我想着先开一个,然后剩下一个空位交给右边」在全仓无任何逐字存录——`grep -rn "先开吧" docs/` 唯一命中就是本文件自身，且该引文没有脚注给出处。同时本项脚注只指向派生件 03A 增补，未引用该次解冻的授权真源 `docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_two_w0_unary_lowering_canary_20260816/00_OWNER_AUTHORIZATION_20260816.md`（`00_OWNER_SIGNAL_AND_BOUNDARY.md:4` 明写该文件才是授权真源）。更严重的是，该授权存录记的是另一句原话「金丝雀解冻，整包归你——冻结协议→落库→实现→跑→报告，一条龙」，不含「先开一个／剩下一个空位」这层资源分配。于是同一次授权在仓内出现两份互不引用的逐字记录，且本文件这份还额外携带一项在案存录里没有的分配决定。本仓已有该类记录的窄存录先例（`docs/research/solver_reasoning_outer_loop_reviews_20260815/OWNER_INSTRUCTION_20260815.md`：性质、仓外转录锚、效力边界三件齐全），ROADMAP A14 也把「口述定谳在途期无登记位」列为待补缺口。

**建议修法**：按 OWNER_INSTRUCTION_20260815.md 形态为这句原话补一份窄逐字存录（含仓外会话转录路径与效力边界），本项脚注改指 00_OWNER_AUTHORIZATION_20260816.md 为授权真源、03A 为派生边界件，并在正文说明这句与既有授权原句是同一次授权的两段还是两次信号。


### [MAJOR] 裁决请求专审-2 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:54
「另一空位按 owner 原话留给右侧工作线」把原话里的「右边」自行解释成了 ROADMAP 意义上的「工作线」。仓内唯一在案的 owner 同词用法是 `docs/research/solver_reasoning_outer_loop_reviews_20260815/OWNER_INSTRUCTION_20260815.md:11`：「ok，剩下的你先跟右边那个三面的线程讨论一下，然后就开干」——「右边」指的是并发的浏览器/会话线程（且那次正是指三面线程），不是路线图工作线。本文件在没有任何存录支撑的情况下作了替换解释，并把它写成「按 owner 原话」的执行建议，属于在窄授权上自行裁断指派对象。

**建议修法**：删去对「右边」的具体化解释，或改写为「第二个 canary 席位的归属按 owner 原话保留，具体指向待 owner 确认」；若确知所指，补出处。


### [MAJOR] 裁决请求专审-3 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:52
授权语义段的非蕴含清单相对在案存录被收窄，等于以省略扩大了授权面。`00_OWNER_AUTHORIZATION_20260816.md:20-24` 的未授权事项包含「不改 src/、认证面、supervisor、publisher、强状态或发布表面」「不把局部循环塌缩写成 certified-exact 上下界进展、家族普遍性或整线立项」；`00_OWNER_SIGNAL_AND_BOUNDARY.md:17-21` 的冻结面另含「默认启用、生产 promotion、cut framework promotion、认证或发布效力」「跨布局／跨矩形／跨 theorem 的家族普遍性主张」；03A:64 另含「不触认证面，不允许 production default 或 public certified effect」。本文件只复述了「不立项／不解锁 D3、D4／不解锁 registry 常态化与 cut 合流」，遗漏了家族普遍性外推、certified-exact 上下界外推、production default 与发布表面这四类禁止，而这恰是最容易被下游误用的方向。

**建议修法**：把授权语义段的非蕴含清单与 00_OWNER_AUTHORIZATION_20260816.md 未授权事项、00_OWNER_SIGNAL_AND_BOUNDARY.md 冻结面逐条对齐，缺项补齐或显式声明本段只做摘要、以真源为准。


### [MAJOR] 裁决请求专审-4 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:17
总览表第 5 行写「`#4` 已批准 `rules/derived/`」，裸编号在本文件语境下首先读作本文件自己的第 4 项（Research receipt 顶层协议，状态待裁），造成「待裁项已批准」的自相矛盾。相邻行对同一登记面都用了全限定写法（第 4 行 `OWNER_DECISION_SUMMARY #5`、第 9 行 `OWNER_DECISION_SUMMARY #7`），唯独此处省略。正文 §5 的表述本身正确（owner 已接受 `rules/derived/`，见 OWNER_DECISION_SUMMARY.md:8）。

**建议修法**：改为 `OWNER_DECISION_SUMMARY #4`。


### [MAJOR] 裁决请求专审-5 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:13,28,226
第 1 项把「三面模型 v1→v2 术语与投影迁移」并联到 ROADMAP A14，坐标错位。A14（ROADMAP.md:103-108）的范围是求解面方法论载体：§0b 版本头、277/279 行六问、双向保真与派生闭包两公理、APX_E 原件、方法论 skill，其前提句明写「方法论 skill 继续只覆盖求解面，不接管发布或治理 authority」——三面防污染模型属治理/审计面，不在 A14 的判据本体内。三面线在 ROADMAP 上的既有挂账入口是 A12（ROADMAP.md:95 一节，标题即「三面防污染架构审计挂账」）。后果是：选 A 所需的「后续受控投影迁移批」看似已有登记宿主，实际无人认领。

**建议修法**：把并联对象改为 A12（或明说三面线术语迁移当前无登记宿主、需随本项裁定新建触发器键控登记），A14 只在「方法论载体需有 canonical successor」这条一般原则上引用。


### [MAJOR] 裁决请求专审-6 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:32 / README.md:42
主文档与门牌已把「v2 取代 v1 符号判据」写成既成事实——主文档 §0.2 末句「因此，v2 **取代** FIRST_PRINCIPLES_DESIGN.md `:633-641` 的符号判据表述」，README v1 关系索引第 1 条「符号判据：v2 supersede」——而裁决请求第 1 项仍把「是否成为项目级正式术语、v1 投影是否迁移」列为待裁，选项 B 明写「只在本 dossier 内使用，项目其它入口继续保留旧的按面判符号说法」。两者对应关系不一致：若 owner 选 B，主文档已宣告的 supersede 就失去依据；且该 supersede 动作本身（改写另一条已立项线 rule_system_redesign 的在案表述）没有作为任何一项请求上桌，而 OWNER_DECISION_SUMMARY 第 2 件正是把「撤销只加不改、原地改写父句」保留为 owner 待裁事项。

**建议修法**：要么把主文档/README 的 supersede 声明降级为「待第 1 项裁定后生效的提案」，要么在第 1 项正文明说 supersede 已单方面执行、选 B 需回滚，并给出回滚代价。


### [MAJOR] 裁决请求专审-7 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:18,92-104
第 5 项漏注触发后果。`OD-B1-THEOREM-REG-01`（OPEN_DEBT_LEDGER.md:179-182）的触发器是「编译器官获 owner 批准转入常态消费，或任何『theorem registry 实例化』提案出现」；本项把 A/B 两个 registry 实例化方案摆上桌，提交与裁定本身就命中该触发器，条件项将从 `CONDITIONAL` 转为激活，而该行的临时负责人写的是「届时指派」、到期日为「无（触发器键控）」，触发后必须补指派与期限。此外 `00_OWNER_AUTHORIZATION_20260816.md:23` 把「不实例化常态 theorem registry，不触发 rules/derived/ 与未来 registry 已同形态的宣称」列为窄授权的未授权事项，与本项是活边界。文档只写了「不重复建债」，读者无法看出裁定动作会激活一笔已在册欠账。

**建议修法**：在第 5 项与总览行补一句触发后果：本项一经裁定即命中 OD-B1-THEOREM-REG-01 触发器，须同时指派负责人与到期日；并注明与第一条 canary 未授权事项的关系（裁定不等于允许在 canary 内实例化）。


### [MAJOR] 裁决请求专审-8 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:136
第 7 项相对最高优先底本丢失了一个待裁子问题，并把它替换成了已裁口吻。底本 collision_verdict_20260816.md:1078 起「六、必须由 owner 裁决才能定的事项」第 7 条把「production 与 certified 是否分开」列为该项需 owner 决定的第一个子问题；本文件的「还需一并裁定」只保留了三问（谁授研究 token、谁授 certified token、U/L update / strong-status mint / publication 各归哪个 sink），把 production/certified 之分降级成选项 A 的代价描述（「A 实现便宜但会把 production 与 certified 偷懒合并」）。主文档 §15 更已直接写成结论「尤其要分开 production 与 certified」。该条既不在附录 A「不推给 owner 的六条逻辑后果」之列，属于文档自行裁断了底本指定由 owner 定的事项。

**建议修法**：把「production 与 certified 是否分开」恢复为第 7 项「还需一并裁定」的第一子问题，或在附录 A 说明为何它可降为逻辑后果并给出理由。


### [MAJOR] 裁决请求专审-9 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:22,174-186
第 10 项正文把底本明列的范围裁掉后仍标「新事项」，导致该并联而未并联。底本 collision_verdict_20260816.md「六、10」原文是「是否把现有 knowledge ledger、rules/derived/、未来 theorem registry 和 option registry 纳入同一规范化事件／投影架构」；本文件只写「把全仓研究资产分成知识、能力、期权三本存量账」，四个具名对象全部脱落。后果是三处并联漏标：①与本文件第 5 项（theorem registry 家址）就同一对象各自成票，两项分别裁定可能得出互斥结果，彼此无交叉标注；②与 OD-B1-THEOREM-REG-01 的形态对齐义务无标注；③与 OWNER_DECISION_SUMMARY.md:6 的 2026-08-13 状态追记③无标注——该追记把「`representation_class` 的 enum 扩类裁定权」明确划给档案面批（OWNER_RULING_EVENT），而本项 B 方案要在 knowledge ledger 上新增三本只读投影，正落在该批的裁定权内。

**建议修法**：第 10 项正文恢复底本的四个具名对象；总览行「新事项」改为并联本文件第 5 项、OD-B1-THEOREM-REG-01 与档案面批的 representation_class 裁定权，并说明与第 5 项的裁定顺序依赖。


### [MAJOR] 裁决请求专审-10 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:78-88
第 4 项只对选项 B 标注了并联，未说明选项 A 会实质预决另一张票。选项 A 是「立即覆盖全部历史 research checker，先全仓回填，再允许任何新消费」——这既预先决定了 OWNER_DECISION_SUMMARY 第 5 件（形态/凭据 checker 何时进硬门，其默认推荐是「先 advisory 跑一个批次周期，第三批完成后转硬门」，仍待裁），也改写了 A12 的触发器键控排程（FINDINGS.md:10 明写三门 PASS 限界「挂下一次触及任一文件的 Chain B/C 批顺走，不单开」）。owner 若在不知情下选 A，等于用本票撤销另一票的默认路线与另一笔挂账的触发器。

**建议修法**：在第 4 项代价栏或请裁行补注：选 A 将实质预决 OWNER_DECISION_SUMMARY 第 5 件并使 A12 的 Chain B/C 顺走触发器失效，需一并确认；选 B/C 不产生该后果。


### [MAJOR] 裁决请求专审-11 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:158-170
第 9 项未标注跨票前置依赖。选项 B 要求「必填……单位成本、运行成本、人类队列成本、typed measurement state、误挡率」，这些数字全部依赖被测代码埋点；而埋点授权属 OWNER_DECISION_SUMMARY 第 7 件，仍待裁，OD-B0-INST-01 的状态正是 `OPEN_AUTHORIZATION_PENDING`（OPEN_DEBT_LEDGER.md:101-107，明写「代码实施等待 owner 第 7 件裁定」，阻断范围「没有观测点时不得写拒绝率为 0」）。若 owner 否决第 7 件而批准本项 B，B 的必填栏即无合法数据源，只能按欠账规则填「无埋点」。文档只写「作为既有 #7 与 OD-B0-INST-01 的增量验收」，没有把「B 以 #7 获准为前提」摆出来，末尾的建议裁决顺序也未涉及与另一张票的先后。

**建议修法**：在第 9 项与建议裁决顺序中补注：本项 B 的运行时成本项以 OWNER_DECISION_SUMMARY 第 7 件获准为前提，未获准时对应字段按 OD-B0-INST-01 阻断规则填写；建议第 7 件先裁。


### [MAJOR] 裁决请求专审-12 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:5
文首读法承诺「仓内坐标统一放在脚注，正文不要求 owner 回查内部文件」，实际正文与总览表遍布裸仓内坐标：总览表十二行中十行带坐标（`ROADMAP A14`、`ROADMAP G-③`、`ROADMAP G-②`、`OWNER_DECISION_SUMMARY #5/#7`、`OD-B1-THEOREM-REG-01`、`OD-B0-INST-01`、`A12`），正文 §1「已并联 ROADMAP A14」、§3「已在 ROADMAP G-③ 登记」、§4「既有 OWNER_DECISION_SUMMARY #5……三面线 A12 也已挂 PASS 限界改造」、§5「OD-B1-THEOREM-REG-01 已登记」、§6「工作线 G」、§9「OWNER_DECISION_SUMMARY #7、OD-B0-INST-01」、§12「Phase -1」同样如此。owner 画像要求讲解不落内部坐标；此处不是坐标该不该记录的问题（去重标注确实必须可核），而是文档自陈的读法与正文形态不符，读者无法只读正文完成裁决。

**建议修法**：总览表的「既有事项关系」列改写成一句人话（如「与既有的埋点承认请求是同一件事的两个阶段」），坐标以脚注号挂出；正文并联句同样改为语义描述＋脚注，或把读法承诺改成如实描述。


### [MAJOR] 裁决请求专审-13 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:7
术语块只解释了 lowering、canary、receipt、certified 四个词，但正文首现即用而未解释的机器术语远不止此：§4 的 `result_kind + typed outcome + verified_scope + authority_basis + granted_effects + non_implications` 六字段与 admission wrapper；§5 的 `UNREVIEWED / ACTIVE / STALE / PROMOTED`、premise fingerprint、currency；§6 的 typed lowering、sink promotion、shadow、certified attach；§7 的 facet 与缩写 `U/L update`（上/下界台账更新，缩写全文未展开，且选项 B 的 token 例子里只列了 `UPPER_LEDGER_UPDATE`、未列 `LOWER_LEDGER_UPDATE`）、`TERMINAL_STATUS_MINT`；§8 的 `EXPIRED_BLOCKED`；§9 的 typed measurement state、误挡率；§10 的 identity/event substrate、append-only event、projector、视图新鲜度；§11 的 coupling、rehydrate；§12 的 corpus、删失、`Phase -1`。这与文首「每项按问题、选项、推荐、代价展开」并「术语首现有解释」的定位不符，也违反 owner 读者画像「术语首现时解释其含义」。

**建议修法**：扩充术语块或在各项首现处就地补一句中文释义，尤其是 `U/L update`、`EXPIRED_BLOCKED`、六字段收据、删失、Phase -1 这几个 owner 无法从字面推出的。


### [MINOR] 裁决请求专审-14 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:20,140-154
第 8 项漏并联一处既有局部登记，并存在与冻结件的潜在冲突。总览行只写「复用开放欠账的到期不判假原则，但尚无项目级 SLA」，未提本文件自己 §2 脚注引用的 03A 增补：`03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md:37-44` 已把 `EXPIRED_BLOCKED / NO_EFFECT` 双语义写成冻结协议，且明写 `EXPIRED_BLOCKED`「不停掉已经明确获准的 baseline research」。第 8 项选项 B 直接复用该词而不指其已冻结定义；选项 C 在其上增加「立即停用现有边」，与该冻结件的保证方向相反——若 C 获准且回溯适用于该 canary，需走发射前修订提交（03A:5 的适用顺序条款），文档未提。

**建议修法**：第 8 项补注 03A 已冻结的 EXPIRED_BLOCKED 定义为既有局部先例，并说明选 C 是否回溯适用于已冻结协议、如回溯需走发射前修订。


### [MINOR] 裁决请求专审-15 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:32-34,66,82
三个选项与主文档「明确否决的做法」正面冲突而未标注：第 1 项选项 C「把研究升为第四个对等面」对应 TRI_PLANE_MODEL_V2.md:519 第 1 条否决（底本 collision_verdict_20260816.md:9 也称其为「唯一需要明确否决的核心主张」）；第 3 项选项 C「进入 certified src/ 靠 default-off flag 隔离」对应 §27 第 5 条否决；第 4 项选项 C「长期 advisory，只要求文书加免责声明」对应 §27 第 2 条否决。这三条都不在附录 A「不推给 owner 的六条逻辑后果」之列，主文档也未把它们标为待裁。结果是同一批文档里，同一件事在主文档是「明确否决」、在请求里是可选项，owner 无法判断这些 C 选项是真选项还是陪衬。

**建议修法**：在这三个选项处加一行「主文档第 27 节已将本做法列为明确否决，此处仍列为选项是因为终裁权在 owner」，或反向把 §27 相应条目标注为「待第 N 项裁定」。


### [MINOR] 裁决请求专审-16 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:15,60
第 3 项的登记引用不够准确。ROADMAP G-③（ROADMAP.md:69）登记的是「实验闸内任何已证定理静态 lowering 活动的硬红线——lowering 入口与度量埋点一律落研究面模块，certified 源文件零改动，触 src/ 即面边界事件」，是对第一条 canary 这一实例的红线，并未登记「是否把 src/ 零修改升为常设规则」这个问题。文档写「该问题已在 ROADMAP G-③ 登记，本项只请求常态口径」，两句自相牵制（既称已登记又称只问常态），容易被读成常态规则已有登记宿主。

**建议修法**：改为「G-③ 只登记了第一条 canary 的硬红线，常设化问题尚无登记宿主，本项即为其首次上桌」。


### [NOTE] 裁决请求专审-17 @ docs/research/tri_plane_model_v2_20260816/OWNER_DECISION_REQUEST.md:52
术语漂移一处：底本 collision_verdict_20260816.md「六、2」写的是「D4 paired A/B」，00_OWNER_AUTHORIZATION_20260816.md:21 写「D4 holdout A/B」，ROADMAP.md:64 写「holdout 对照」。本文件用「通用 D4 holdout A/B」，与授权存录一致、与底本用词不同。不构成语义错误，登记备查。

**建议修法**：无需修改；若后续统一术语，以授权存录与 ROADMAP 的 holdout 为准。


## 席位：薄弱三处深攻

**总裁定**：被审对象（根目录 /home/zhuran24/zmd-pj/docs/research/tri_plane_model_v2_20260816/）在结构、坐标与底本忠实度上总体扎实：三面×运行域的正交裁断、五类边、三轴不可压分、控制面 BLOCK 与数学面 NO_EFFECT 的分离、附录 A 的六条"不推给 owner"都与最高优先底本 collision_verdict 一致，OWNER_DECISION_REQUEST 十二项与既有 OWNER_DECISION_SUMMARY/开放欠账/工作线 G 的去重并联做得干净，未见越权自行裁断。但主笔自报的三处薄弱经独立评估**两处成立、一处部分成立**，且成立方式比自报更具体：①外推问题的真实形态不是"rejector 经验能否照搬"，而是全文的集合关系**没有声明量化对象空间**，且 collision:303-311 给出的另外四条角色形式关系被降格为散文——文档层可补；②消费边全集问题的真实形态不是列举遗漏，而是**全文所有义务都是边局部的，没有任何路径/组合义务**，而仓内 `src/search/f5_binding_empty_domain_adapter.py` 就是一条现成的"子问题局部判词被 lift 成跨布局全局 cut"通道，这是设计洞，应进 OWNER_DECISION_REQUEST 或挂债；③"第二套 authority 系统"攻击**不成立于 §15 的正面表述**（production/certified 已明确分开、明确禁止从"更高等级"猜权限），但成立于其可执行性：首号金丝雀的 03B schema 把 granted_effects 定义成开放字符串数组、authority_basis.authority_class 是 const 字面量且 source_paths 不带 digest、FAIL 收据仍带非空 granted_effects——§11「authority_basis 不能自封」在首例已被形式绕过，而文档引该 schema 作在案证据时未补注。另找到两处未自报薄处：§12 消费合同丢了底本盲答:854 的 claim channel（与 §6 终判公式直接矛盾，唯一 blocker）；§13/§14/§15 三条轴上 NOT_APPLICABLE 类取值三处同名不同义、且未访问 context 的默认状态未定。共 13 条，1 blocker / 8 major / 3 minor / 1 note，全部可由补注 + 两笔上桌收口，无需推翻文档骨架。


### [BLOCKER] 薄弱三处深攻-1 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§6(:120-132) 与 §12(:235-247)、§25(:487)
文档内部矛盾（未自报的第四薄处）。§6 把终判写成 verdict = f(source_role, edge_kind, consumer_stage, runtime_binding, effect_kind, target_claim, context)，把 target_claim 列为独立自变量；但 §12 的五组最小合同——即机器闸实际绑定的那份对象——**没有任何字段承载 target_claim**。第一组是来源身份，第二组是 consumer/stage/effect kind/trigger 映射，第三组是角色关系，第四组是 result kind/verified scope/granted effects/allowlist/denylist，第五组是新鲜度与失败动作。全文 grep「target_claim」只在 §6 的公式代码块内出现一次（:129），再无第二处。后果是按 §12 建出来的合同不足以计算 §6 的 f，两条最承重的规范条款互不可满足。这不是底本裁剪：盲答 blind_answer_20260815.md:854 的 W0 合同第二项明确写着 `claim channel：UPPER_AFFECTING_RESEARCH_SEARCH`，而 §25 复述该六步合同时（:487 列 REJECTOR 角色、binding stage、abstract trigger、actual lowering、allowed effect）恰恰把这一项静默丢掉。collision 底本重构五组时也未显式撤销它。反方向的辩护——granted_effects 里的 UPPER_LEDGER_UPDATE / LOWER_LEDGER_UPDATE 已隐含 claim channel——不成立：文档自己在 §6 把 effect_kind 与 target_claim 列为 f 的两个不同自变量，且一条 grant 只含 RESEARCH_MODEL_PRUNING 的 rejector 边仍需回答「这次剪枝准备支撑上界最优性主张还是可行性主张」，剪枝的 soundness 恰好按这个答案分叉。

**建议修法**：裁决 A（文档补注）。在 §12 第二组「消费者与运行时绑定」加入 `claim_channel / target_claim` 字段（底本用词为 claim channel，取值形如 UPPER_AFFECTING_RESEARCH_SEARCH / LOWER_WITNESS / FEASIBILITY_ONLY），并在字段说明里点明它与 effect_kind 的分工：effect_kind 说这条边做什么动作，claim_channel 说这个动作准备支撑哪一种结论、因而 §7 的 F(c) 按哪个可行性语义取。同时在 §25 的合同复述里补回 `claim channel：UPPER_AFFECTING_RESEARCH_SEARCH`，与盲答 :854 对齐。§6 公式不动。


### [MAJOR] 薄弱三处深攻-2 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§7(:142-153)、§12 第三组(:239)
自报薄弱①成立，但成立点与自报不同。自报担心的是「从 rejector 单标本外推到五角色」的经验强度；真实缺陷是两条更硬的：(a) §7 的 R_T(c) ⊆ D(c) − F(c)、R_L(c) ⊆ R_T(c) **没有声明这些集合量化在哪个对象空间上**。W0 定理的 binder 是 `b: BindingSelection`（01_JUDGMENT.json:62-66,:85），R_T 因此是 binding selection 的集合；而 §7 把 D(c) 定义成「lowering 前的搜索域」，在本仓这通常指外层布局/候选搜索域。两个空间之间需要一条 transport 论证（局部对象被排除 ⇒ 外层对象被排除），而这条论证在本仓已知是**分模式成立、分模式失效**的：`src/search/f5_binding_empty_domain_adapter.py:6-14` 明写 PortBindingModel 有两种 INFEASIBLE 模式，generic-I/O 需求等式模式是反单调的、子集 INFEASIBLE 不蕴含超集 INFEASIBLE、绝不可 lift；空绑定域模式才可 lift。文档把 R_L ⊆ R_T 写成跨角色通用判据而不要求具名对象空间，等于把这条已被仓内代码认定为分模式的 transport 默认成恒真。(b) §7 标题是「Rejector、Constructor 与 Exact Checker 的关系式」，但只有 rejector 拿到了代码块形式关系；constructor、exact checker、ledger updater、authority bridge 各得一句散文（:151）。collision 底本 :303-311 是逐条给了形式关系的：constructor 为 W_constructor ⊆ W_proven_valid、exact checker 要求双向等价、ledger updater 只更新明确授权的账、authority bridge 为 requested_effects ⊆ granted_effects。§12 第三组也只列角色名不列关系式。于是自报所问的「exact checker 双向等价对哪个对象空间量化」「authority bridge 的 token 组合有无隐式权限升级」在文档里根本没有可对话的形式对象。

**建议修法**：裁决 A（文档补注）。§7 加一段前置定义：每条边的合同必须具名 `object_space`（本例为 binding_selection），凡 R_T 与 R_L 的对象空间不同于 consumer 实际改变的搜索域时，必须另附 transport 论证或退回 NO_EFFECT；举 f5 适配器的两种 INFEASIBLE 模式为在案对照。同时把 collision:303-311 的四条形式关系逐条搬进 §7 代码块并在 §12 第三组内联，尤其 W_constructor ⊆ W_proven_valid 与 requested_effects ⊆ granted_effects，让「构造失败不得升格 INFEASIBLE」和「token 不得组合升权」各有可检查的式子而不只有口号。


### [MAJOR] 薄弱三处深攻-3 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§5(:102-110)、§8(:159-167)、附录A(:538)；OWNER_DECISION_REQUEST.md 总览表
自报薄弱②成立，但真实形态不是「消费边全集列举不全」，而是**全文没有任何路径级/组合级义务**。§5 的五类边、§8 的三轴裁断、附录 A 第 1 条「rejector 的 lowering 不得拒绝 theorem 未证明可拒绝的对象」全部是逐边局部谓词；§5 只禁止「不同种类的边因连接同一工件而合并」，未禁止「多条各自合规的边沿路径复合出一个没有任何单条边持有的作用」。仓内已有现成通道：`src/search/f5_binding_empty_domain_adapter.py:96-116` 把一个子问题局部判词（该 pose 的绑定域为空）lift 成跨布局全局反驳并产 cut——判词本身是局部的、lift 才是把它送进全局对象空间的那一步，而 lift 在 §5 的五类边里不属于任何一类（它不是执行边——不改本层可行域；不是晋级边——不涉 research→certified 能力域；不是引用边——不是文书前提集）。同型组合还有：一条持 RESEARCH_MODEL_PRUNING 的边产出的剪枝结果，被另一条持 UPPER_LEDGER_UPDATE 的边读作证据，复合效果等价于一次未被任何边授予的 CERTIFIED_MODEL_PRUNING 级作用，而两条边各自的 §8 三轴裁断都能通过。这条洞同时是自报③「token 组合越权」的真正落点，也让附录 A 第 1 条的「不需要 owner 逐例决定」在路径层面失去保证。

**建议修法**：裁决 B（真设计洞，进 OWNER_DECISION_REQUEST）+ A 尾（文档补注）。B：在 OWNER_DECISION_REQUEST.md 新增第 13 项「作用边组合与判词提升（lifting）的路径级义务」，问题＝逐边合规是否蕴含路径合规、谁负责路径级裁断；选项＝(A) 只保留边局部义务并显式承认路径风险由人工 first-of-kind 兜；(B) 引入第六类「提升边」，凡把判词搬到更宽对象空间者必须单独出生证 + transport 证明；(C) 引入路径级 grant 闭包检查（沿路径的 requested_effects 并集必须被某个具名 grant 覆盖）；推荐 B，代价是每条 lift 多一份 transport 证据。若 owner 不想现在开，退而在 ROADMAP 工作线 G 挂触发器键控条件项（触发器＝任何 research 判词首次被上层 lift 或跨对象空间复用）。A 尾：§5 末尾补一句「五类边的合规是逐边谓词，不蕴含路径合规」，并在 §7 引 f5 适配器为在案对照。


### [MAJOR] 薄弱三处深攻-4 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§25(:485-495)、§13(:250-264)
底本承重内容被静默丢弃（未自报的第五薄处）。盲答 blind_answer_20260815.md:894-896 在第三步 scope guard 之后写明一条前瞻限制：「对于第一号固定对象，精确相等 guard 足够安全。未来如果要做参数化 family theorem，不能继续只依赖一个 hash，必须把 premises 结构化，并证明 runtime context 蕴含 theorem context。」文档 §25 完整复述了六步（旧包不动／新建合同／锁 scope guard／SHADOW 后 ACTIVE／pose ban 反例／A-B 只测收益），并逐项列出十项 scope guard，却把这条唯一说明「hash 相等 guard 为何不可外推」的限制整条丢掉。全文 grep「蕴含」只命中「非蕴含边界」，无一处 entailment 义务；§13 讲 context currency 时也只说漂移进 STALE，未说 runtime context 满足 theorem scope 该怎样被证明。后果是：§9 换证触发器里「同一合同开始跨布局或跨 family 复用」只给了「必须换证」这个程序结论，没给「换证时要证什么」这个数学内容，而这恰是从单标本走向 family 的唯一技术闸。该缺失与本席第 2 条发现（对象空间/transport）是同一件事的两端。

**建议修法**：裁决 A（文档补注）。在 §25 scope guard 段末补回盲答 :894-896 原意：精确相等 guard 只对第一号固定对象充分；参数化 family theorem 必须把 premises 结构化，并显式证明 runtime context ⊨ theorem context，hash 相等不再是合格 guard。同时在 §13 增一句正面义务：edge 激活的前置条件是「当前 context 蕴含 theorem scope」有据可查，而不只是「指纹未漂移」。


### [MAJOR] 薄弱三处深攻-5 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§11(:214,:229)、§15(:297-306)；对照 experiment_two_w0_unary_lowering_canary_20260816/03B_RECEIPT_ENVELOPE_SCHEMA_V1.json、w0_canary_receipt_contract.py:94-101、06_check_w0_unary_lowering_contract.py:561,:609
自报薄弱③的成立形态。§15 的正面表述守住了自报攻击的直接版本——production 与 certified 明确分开、明确写「机器只认 token 集合，不从更高等级猜测附带权限」、四层只作人类里程碑投影——所以「AUTHORIZED_FOR_PRODUCTION 被误读成 CERTIFIED_MODEL_PRUNING」这一击不成立。但攻击在可执行性上成立，且首号金丝雀已经现形：(a) 03B schema 里 `granted_effects` 是 `{type: array, items: {type: string, minLength: 1}}`——开放字符串数组，无枚举、无与 `outcome` 的相容性约束；(b) `authority_basis.authority_class` 是 `const: "research_only_non_authorizing"`，`source_paths` 只要求非空字符串数组、**不带 digest**，而同一收据里 manifest 与 schema 都是带 sha256 的；helper `w0_canary_receipt_contract.py:94-101` 把这段整体写成常量。也就是说 §11 的「authority_basis 不能由 receipt 自己凭一个字符串自封，它必须指向当前权威真源」在首例里是靠一个 const 字面量 + 一串未绑定字节的路径满足的，权威源文件改了收据也不会知道。(c) `06_check_w0_unary_lowering_contract.py:609` 在 FAIL 分支仍发出 `granted_effects: ["blocks_true_canary_arms"]`——把「阻断后果」写进了 §15 定义为「精确命名的一项获准作用」的字段，而 §4 明写 checker receipt 的 granted_effects 默认为空；PASS 分支 :561 则自铸 `marks_W0_unary_lowering_as_contract_validated_for_this_pinned_context`，是 checker 收据给自己盖状态章。文档 §11 引 03A/03B 作在案证据时说的是「已把八字段超集与 verified_scope/granted_effects 分离写入发射前协议」——就协议文本而言属实，不构成假陈述；但读者会据此认为机器侧已守住 §11 的两条分离，而 schema 实际只保证字段存在。

**建议修法**：裁决 A（文档补注）为主、B 为尾。A：§11 在引 03B 处补一句限界——该 schema 只强制八字段 presence，不强制 granted_effects 的词表闭合、不强制 authority_basis 与权威真源的字节绑定，故「反自封」目前是文本纪律不是机器纪律；并给出机器判据方向：authority_basis 必须携带被引权威文件的 digest 与 currency，granted_effects 必须来自闭合词表且与 outcome 相容（FAIL 类 outcome 的 granted_effects 恒空，阻断后果应放 non_implications 或另设 blocking_scope 字段）。B：把「首例已在自铸非枚举 token、FAIL 收据带非空 granted_effects」作为验收口径写进 OWNER_DECISION_REQUEST #7（capability token 的正式枚举与授予者）的代价段，使 #7 的裁决自带一笔已知回扫对象；不必新开一项。


### [MAJOR] 薄弱三处深攻-6 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§13(:256-262)、§14(:270-285)、§15(:300-304)
自报薄弱③里「state(a,c) 状态爆炸或错误继承」这一击成立，形态是同名异义 + 默认未定（也是未自报的一半）。(a) §13 举例说「W0 theorem 在 pinned W0 context 中可以是 VERIFIED；对另一个 layout 或 rectangle，它可能是 NOT_APPLICABLE」——但 §15 声明的机器枚举 `verification_state: UNVERIFIED | VERIFIED | REFUTED | STALE` 里**没有 NOT_APPLICABLE**，而 §14 的 `NOT_APPLICABLE_BY_TYPE` 又被定义成 observation 轴上的「按类型永久不适用」。同一个词根在三条正交轴上出现三次、含义各不相同，且 §13 用的那个取值不在任何已声明枚举内。(b) 更硬的一点：artifact_state(asset, context, time) 是一个在 context 上的全函数，而 context 空间（布局 × 矩形 × consumer stage × 运行配置）无界，文档**没有规定未被访问 context 的默认取值**。若默认落到 §14 的 NOT_APPLICABLE_BY_TYPE 语义就是永久性静默退役（此后不会有人回来重验）；若默认落到 STALE 就是全仓长红、与 §13 自己「不必让全部无关 context 一起红」的目标冲突。底本本身在这点上就有歧义（collision:705「对另一个 rectangle 或 layout 应当 NOT_APPLICABLE 或 STALE」并列了两个语义相反的答案），文档照抄未仲裁。这正是「错误继承」的入口：默认未定时，实现者最省事的做法是从最近的已知 context 继承。

**建议修法**：裁决 A（文档补注）。§13 明确三件事：①未被访问 context 的默认状态是一个独立取值（建议 UNVERIFIED_IN_CONTEXT 或复用 §14 的 UNKNOWN_UNMEASURED 语气），**永远不得默认为 NOT_APPLICABLE_BY_TYPE，也不得从相邻 context 继承**；②把 §13 例子里的 NOT_APPLICABLE 改成 §15 枚举内的取值，或在 §15 枚举里正式加入 NOT_APPLICABLE 并说明它与 §14 同名取值分属不同轴；③加一张三轴取值对照小表（verification_state / observation / freshness），点名 NOT_APPLICABLE 类词在三轴上的不同含义，防止实现者压成一个字段。


### [MAJOR] 薄弱三处深攻-7 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§16(:317-324)、§18(:376)
自报薄弱③里「债务改名/拆记录/转冷档案洗白」这一击成立。§16 采纳了 collision B3 的正确改造——discriminated union 作用于 condition record 而非 artifact，同一 theorem 可同时挂 LATENT_ASSET、MEASUREMENT_GAP、CONDITIONAL_DEBT 三条独立记录；§18 的反洗白规则则写成「凡已有当前 consumer、当前阻断范围、到期义务或现行 claim 依赖的**事项**，都不得降入 UNTYPED_ARCHIVE」。两条合起来留了口子：判据的评值单位是「事项/记录」，而记录可拆。把一个资产上的 CONDITIONAL_DEBT 关闭或改写成 LATENT_ASSET 之后，剩下的记录逐条看都不满足四个禁止条件，资产整体即可转冷——债务被拆散洗白，而每一步都合规。文档也没有把现行 OPEN_DEBT_LEDGER 已有的两条防线升格成本方法规范：它在 §18 只把该台账列为「在案证据」（:378 引 :10-16），而台账那两条——关闭必须留关闭证据、关闭不得删除原行——恰是防拆记录洗白的关键，本方法正文一字未收。

**建议修法**：裁决 A（文档补注）。§18 把反洗白判据的评值单位从「事项」改为「资产」：转入 UNTYPED_ARCHIVE 的准入检查必须对指向同一 canonical asset 的**全部 condition records 求并集**，任一记录持有当前 consumer / 阻断范围 / 到期义务 / 现行 claim 依赖即整体禁止转冷。§16 补一句对应约束：condition record 的关闭、改 kind、拆分或合并都不减少资产层义务，关闭须留关闭证据且不得删除原记录（与 OPEN_DEBT_LEDGER 现行纪律同构）。


### [MAJOR] 薄弱三处深攻-8 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§17(:341-356)、§14(:287)
自报薄弱③里「measurement event 被 projector 静默升格成 authorization」这一击部分成立：文档在 observation 层守住了（§14:287「任何 observation 都不自动授予 capability」），但在 projector/账层丢了底本的承重分离。collision:768-778 给出的是一张事件类型→账户的授权映射：theorem verification event 更新知识账投影、implementation event 更新能力账的 implemented facet、**owner grant event 更新 capability grants**、holdout 失败降低 option value、**measurement event 只增加证据，不直接自铸 authorization**。文档 §17 把这张映射整体压成「四格分别记录资源成本、知识增减、能力增减和期权新增/收窄/触发/退役/转冷档；typed observation、删失与 sensor validity 是交易证据。确定性 projector 再生成三本只读视图」。「确定性」「只读」都是 projector 的**形式**属性，不是权限属性：一个确定性 projector 完全可以从知识账或效用账的事件推出一条 capability grant，输出仍是只读视图，仍然确定。文档因此没有写下能力账唯一的正面写入规则，「一库」退化成全能登记册的路正是从这里开的。

**建议修法**：裁决 A（文档补注）。§17 补回事件类型→账户的授权映射，并把其中两条写成硬规则：capability_stock 只能被具名 grant event（owner / sink / 具名 issuer）改变；measurement event 与 knowledge event 只增加证据，projector 不得由它们推出任何 capability grant。同时点明「确定性 + 只读」是 projector 的形式属性，不构成权限约束。


### [MAJOR] 薄弱三处深攻-9 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§21(:414-420)、§12 第四组(:240)
自报薄弱②里「账面 research effect 实际写入 certified 会读的中间工件」这一击成立。§21 抽象层面是对的（「边界必须落在 import 方向、loader schema、write capability、consumer admission 与 sink replay 上」），但它把红线**实例化**成的只有一条：`docs/research/**` 代码不得被 certified live-import、研究 run 不得写 U/L / review gate / delivery manifest / supervisor / publisher，以及「若需修改 tracked src/，必须停止并另行上桌」。共享可写数据命名空间与进程内共享状态完全没进这张清单，而它们在本仓是实在的：(a) `.artifacts/` 既是首号金丝雀自己的产物根（03A_PRELAUNCH_PROTOCOL_ADDENDUM_V1_1.md:75 登记 `.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816/`），又是 W0 定理 problemHash 的组成部分（01_JUDGMENT.json:32-42 把 `.artifacts/w0_fixrerun_20260804/...` 两个文件钉成问题身份）——同一命名空间既被研究 run 写、又被认证问题身份读；(b) `src/search/master_hint_persistence.py:49-53` 的 `data/checkpoints/master_hints/` 是跨 run 持久、按 candidate_key 索引、由环境变量 EXACT_MASTER_HINT_PERSISTENCE 开关的提示存储；(c) `src/models/port_binding.py:28` 的 `_POSE_LEVEL_BINDING_CACHE` 是进程级全局缓存，同进程内先后跑 baseline 与 treatment 时是共享状态。这三类都不触 `src/`，因此不会触发 §21 与 ROADMAP G-③ 的边界事件，却都是 research→certified 方向的实际影响面。附带一条同源缺口：§12 第五组的 current context fingerprint 未包含运行环境变量/配置，而本仓已有 `EXACT_B1_ROUTING_AWARE_BINDING`（f5 适配器 :44-46 据此决定是否允许 lift）这种直接改变 soundness 论证前提的环境开关——同一份合同在不同环境下其实是不同的 consumer。

**建议修法**：裁决 A（文档补注）。§21 在「目录名、文件头、default-off flag 都不是完整隔离」之后补一段：跨域写能力边界必须覆盖共享可写数据命名空间（本仓至少 `.artifacts/`、`data/checkpoints/`、`data/preprocessed/`）与进程内共享缓存，并说明现行红线只钉 `src/`、这些面尚无机器闸——首号金丝雀本身即写入 `.artifacts/`，而 W0 problemHash 又从该命名空间取字节。§12 第五组把 runtime environment / config fingerprint 并入 current context fingerprint，举 `EXACT_B1_ROUTING_AWARE_BINDING` 为在案例子。若 owner 需要机器闸，作为 OWNER_DECISION_REQUEST #3（canary 常设代码落位）的附带范围提出，不必新开一项。


### [MINOR] 薄弱三处深攻-10 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§19(:386)、§20(:401)、§12 第五组(:241)
自报薄弱②里「NO_EFFECT 非原子回滚」这一击部分成立。§20 的表格行写的是「NO_EFFECT，不加新约束」——这是前置判定形态，正确；但 §19 写「任何 fingerprint 或 contract mismatch 都立即退回 NO_EFFECT」、§12 第五组写「NO_EFFECT 回退」，「退回/回退」预设了事后可撤销。在 CP-SAT 上这个预设不成立：`CpModel` 没有删除约束的 API，实现 `w0_unary_lowering.py:113` 是就地 `binding_model.model.Add(target_var == 1)`，一旦加入无法撤回。而本仓的检查时序恰恰把 mismatch 放在添加之后——`06_check_w0_unary_lowering_contract.py` 的 `audit_proto_delta` 审的是应用后的真实 proto delta（模块 docstring 自陈「audits the actual CpModel proto delta rather than trusting this module's receipt」），`extra_constraint` 变异探针也是先 apply 再审。当前实现靠「所有 guard 都在 Add 之前」侥幸不出事（`apply_w0_unary_lowering:91-105` 确实全部前置），但文档没有把这条时序要求写成规范，第二例换个实现顺序就会落进「已经污染了模型、只能靠丢弃整个模型才能真正 NO_EFFECT」的状态。

**建议修法**：裁决 A（文档补注）。§20 表格下方或 §19 末尾补一句实现形态约束：NO_EFFECT 只有两种合格实现——在产生任何模型改动之前完成全部 guard 判定，或丢弃并重建整个模型；不得依赖事后撤销约束，因为求解器模型对象一般不提供撤销原语。§12 第五组把「NO_EFFECT 回退」改称「NO_EFFECT 前置判定或整模型丢弃」以免误导。


### [MINOR] 薄弱三处深攻-11 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§20 在案证据(:408)、§23 在案证据(:467)
在案证据坐标不准（两处，同一段底本的分界处）。§20 声称「对撞段对两种 BLOCK 的正面区分见 collision_verdict_20260816.md :422-481」，但控制面 BLOCKED 的定义与语义（「若到期没有裁决：transition_state = EXPIRED_BLOCKED」及其三条不蕴含）位于底本 :379-403，完全落在所引范围之外；:422-481 起于数据面 NO_EFFECT 的动作块，且尾段 :470-481 已越界进入材料一⑥「常设闸吞吐成本」，与两种 BLOCK 无关。所引范围内确有 :431-438 的共存表与 :440-442 的一句话总结，故不是空指，但对「正面区分」这个具体主张而言恰好漏掉了区分的前一半。§23 声称「材料一第六点的采纳结论见 :482-503」，而第六点的裁断句「裁断：采纳」在 :472，:482 落在字段代码块中段（per_run_cost 一带），所引范围不含裁断结论本身。

**建议修法**：裁决 A（文档补注/改坐标）。§20 的在案证据改引 collision `:379-443`（含控制面 BLOCKED 定义、数据面 NO_EFFECT 动作、共存表与一句话总结）；§23 改引 `:470-503`（含裁断句与完整字段清单）。两处都不改正文表述。


### [MINOR] 薄弱三处深攻-12 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§2(:60)
面×域实例表相对底本缺项。collision:173-183 给了五条映射：research theorem = 数学面×研究域、research receipt = 档案/证据面×研究域、research admission gate = 发布/准入面×研究域、**certified theorem lowering = 数学面×certified 域**、**owner promotion record = 发布面×certified 域**。§2 只给四条，把最后两条并成一条「认证 sink 的重放属于发布面 × CERTIFIED」。丢掉的 certified theorem lowering 是全表**唯一的数学面×CERTIFIED 实例**，也正是 §22 promotion 重新铸造的目标态；缺了它，读者从 §2 的坐标系里读不出「认证域里也有数学面对象」，容易把 CERTIFIED 域整体读成发布/认证事务面，而这恰好是 v1 混面病的近亲。（§2 把 receipt 的「档案/证据面」改写成「证据/档案角色」是有意且更准确的改动——三面里并无「证据面」——此处不作为问题。）

**建议修法**：裁决 A（文档补注）。§2 的实例列表补回「certified theorem lowering 属于数学面 × CERTIFIED」，并把 owner promotion record 与认证 sink 重放分列（前者发布面×CERTIFIED，后者是 §22 的重新铸造动作）。


### [NOTE] 薄弱三处深攻-13 @ docs/research/tri_plane_model_v2_20260816/TRI_PLANE_MODEL_V2.md:§15(:306)
token 词表两处观察。(a) §15 的示例 token 列表相对 collision:673-681 少了 `OWNER_DECISION`；因为列表以「例如」引出、且 OWNER_DECISION_REQUEST #7 已把正式枚举整体上桌待裁，这不构成错误，但 §15 同时写着「机器只认 token 集合」——在词表尚未闭合、且本文档不打算闭合它的前提下，这句话描述的是一个尚不存在的机制。(b) 与之配套的空白是：文档未规定**未知 token 的准入语义**。若未知 token 一律 deny，token 机制才是真闸；若被忽略，一条含未知 token 的 grant 就等于无声降级为它已知的那部分。首号金丝雀发出的 `permits_endpoint_metric_sensitivity_check` / `marks_W0_unary_lowering_as_contract_validated_for_this_pinned_context` / `blocks_true_canary_arms` 三个 token 都不在 §15 任何列表内，正是这类情形的现成样本。

**建议修法**：裁决 A（文档补注）。§15 加一句：在 capability token 词表由 owner 正式闭合（OWNER_DECISION_REQUEST #7）之前，token 集合只具人读效力，不构成机器准入机制；闭合后未知 token 一律 deny（fail-closed），不得静默忽略。是否补回 OWNER_DECISION 由 #7 一并裁，本文档不预先定死。
