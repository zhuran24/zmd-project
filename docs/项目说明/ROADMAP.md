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

## 登记欠账：落地时仪表盘 §9 迁移

以下五项是文档系统落地后仍由路线图承载的登记欠账。落地时来源归档：`docs/history/status/landing/2026-08-15/document-system-consolidated-landing/docs/项目说明/27_status_dashboard.md`（SHA-256 `2f6df966769372a7f412cbf2ba14ccb2c1f6caae841b1f5366d7d0691d5cce40`）。

| # | 漂移/欠账 | 现行以谁为准 |
|---|---|---|
| A10 | ~~文件记忆层每卡两块门牌各自演化~~ **已解（08-08 单门牌化落地）**：82 张卡加 `title` 字段、两块门牌合并压缩成单一 `description`，`MEMORY.md` 改由 `title+description` 编译生成（`devtools/memory_plate_tool.py`）。残留三条**已消两条**（08-08 同日）：~~②「写卡后必跑编译」无机器闸~~ **已解**：`check-index` 纯只读逐字节比对已挂进 preflight 记忆 lane（不一致=`gate.warn` 永不 block），首跑即抓两条真漂移（含并发写方新卡完全不在索引里）；~~①注入水位无泄压手段~~ **已解**：客户端硬编码上限 `eoe` 由二进制补丁 25,000→40,000 JS 字符（`~/patch-cc-memory-index-cap.py`，已登记 cc-patch 自动补打流水线），水位 85.4%→53.4%，警戒线随之 32,000；**归档分层刻意不做**（cand-C 死刑卡是「终局知识三个月后突然要用」的反例）。**仍在**：③门牌与正文的语义现势一致性无机械体检，归判官层。**新增残留**：④`title` 会被 CC auto-memory 从顶层挪进 `metadata`（工具两处都认，但这是随时间蔓延的形态漂移）；⑤`modified` 是「最后修改」不是「首次到达」，用它当到达信号仍有语义缺口（28 张缺字段的已从迁移前 tar 复原真值；**已定修法方向**：卡的 `metadata.originSessionId` 是 CC 建卡时写的、扛得住内容重写，84/85 张卡都有、16 个 sid 里 13 个转录仍在盘上 ⇒ 用「该会话的起讫时刻」当创建区间，比 `modified` 语义正确，转录已轮转的退回 `modified`） | `.artifacts/memsys_meeting_20260808/FINAL_VERDICT.md`；工具 `devtools/memory_plate_tool.py`；坑册 28 号 E2b |
| A11 | 记忆系统全面复查会议（08-08，4 opus+4 Kimi 异构 8 席+合并/证伪席）判定的**90 项修复欠账**（总台账 75 + 跨层 G-13 + 会务 M-76/77）。**批①'急救四项已落**（`e782d4e`+`54780a2`+hook 重写）；**批③守卫修正六项已落**（zmem verify 挂 preflight/analyze-log/冲突 advisory/C9 序扫描器双修/两扫描器全命名空间，`16a9de9`+pin 换代 `f8f6d11`，门禁 21 门绿）；**批②工具+干跑就绪**（`2f17308`+`plate_v2_dryrun/`，干跑推翻「回写即可」前提：78/80 卡双门牌是两个地层、拼接式合并水位顶 96.1%，迁移=逐卡合并压缩的判断活）——迁移本体与全局 CLAUDE.md 协议改动待 owner 拍板；批⑤内容订正（Kimi 跨层 13 条+61 对冲突 advisory 阅读）与批⑥判官层立项待跑 | `.artifacts/memsys_meeting_20260808/FINAL_VERDICT.md`（终裁+实施追记）+ `MASTER_REGISTER.md` + `plate_v2_dryrun/migrate_plan.md` |
| A12 | 2026-08-13 三面防污染审计三笔挂账：①三门（obligations checker / strong-status allowlist checker / preflight）PASS 文案不自带「不证什么」限界——**挂下一次触及任一文件的 Chain B/C 批顺走，不单开**；②`EXACT_MASTER_FRONT_CLEAR_LIFT` 定理复证与 full-pool golden 接门禁——**挂 redesign 批 5/6**；③~~零税措辞止血批~~**已落**（`3377083`，2026-08-13；顺带坐实 exit-criteria 陈旧期望 134→136——拐角两 pose 裁决前旧值被静默 PASS 掩盖；存疑两处 theorem/truth 措辞仍挂各自 reseal 批）。明细/触发器/勿动清单 | `docs/research/plane_mixing_audit_20260813/FINDINGS.md`；owner 拍板 `00_master_roadmap.md` 文末（`5191abe`/`b3500cc`） |
| A14 | 2026-08-14 项目方法论整理收官（owner 令，skill 前置）：方法论地图＋APX_E 全集抢救快照（原件仅存 untracked 外审包，sha `8088f8c1` 复验一致）＋三组六席原始清点（codex/sol AB 对照＋opus 三视角）已落档。挂账三笔：①~~项目级 skill 落地批~~**已落**（08-14 owner 改口径「只放求解面核心」：瘦身版 skill＝§0b 速览＋三公理＋承重不变式，tracked 真本 `docs/项目说明/29_solving_methodology_skill.md`、安装副本 `.claude/skills/solving-methodology/SKILL.md` 逐字同、副本被清从真本重装；地图 §7 的全量三层路由提案按 owner 口径**不做**）；②**§0b 载体病五条**（版本头滞后、:277/279 六问残留、双向保真/派生闭包两公理前指未落本体区、「绿灯≠关门」六处重复陈述、APX_E 原件 untracked）修复待批；③**未愈合缺口五条**（地图 §6：出身故事绑定无维护/拒真防线不对称/无反向 reseal/外发包完备性无机器闸/口述定谳在途期无登记位）候立项 | `docs/research/methodology_compilation_20260814/METHODOLOGY_MAP.md`（§0 载体病/§6 缺口/§7 skill 提案） |
| A13 | 2026-08-13 文档补丁链已以 20260815 全量合并包（16 批）经 landing planner 落地于本分支。残余待办：①§9 适配作业：`docs/项目说明/29_solving_methodology_skill.md` 补 policy，并登记 `plane_mixing_audit_20260813` 与 `methodology_compilation_20260814` 两个 dossier；②`docs/AGENT_OPERATIONS.md` 补全并与根 `CLAUDE.md` 完成两步调和；③补丁未覆盖的剩余问题在落地后自修。与三面评估线的协调义务已由 owner 于 2026-08-15 撤销；该线文档层前置工作已结束。 | 交接坐标 `zmd_文档补丁链落地评审交接_20260813`；落地来源见本节归档坐标 |

## 排序原则

1. authority 或语义前提变化先于依赖它的工程工作。
2. 能便宜关闭作用域的证明、反例和小实验先于大预算 campaign。
3. 生成、验证、owner promotion 和生产消费分别设置退出门，不把一条绿灯跨层外推。
4. 已完成事项从本页移出并追加到 HISTORY；仍开放的稳定命题由 OPEN_QUESTIONS 自动列出。
