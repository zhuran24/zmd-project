# 老项目 LBBD 方法论：主张、版本演变与诊断

日期：2026-09-22。性质：史料判读与方法审计；状态：完成。史料截止所读 2026-09-09 后继文书；现行输入核对日为 2026-09-22。

## 一、阅读老材料前的独立判断（冻结）

### 1. 阅读边界

本节先于老项目文件、上一轮报告和提取目录的阅读写成，后续不改写。依据只有下列四份当前文件与一般优化建模知识。需要披露一个边界：启动时的记忆索引检索意外显示一条旧摘要“method divides decisions rather than constraints; CP-SAT, LBBD, and concrete placement/binding/routing are distinct choices”，以及 INNER_LOOP/GLOSSARY 文件名；没有继续读取该摘要的上下文。本节因此不是对旧项目完全无先验的盲评，但没有用旧文件设计本节方案。

当前文件简称：R＝根目录《明日方舟：终末地》游戏规则.txt；T＝根目录求解任务.txt；C＝根目录求解约束.txt；M＝求解器/会议成果/会议3/纪要.md。以下行号对应本报告记录的输入哈希。

### 2. 题目的量词先于分层

**正式要求。** 70×70 格内布局，成品产率至少 0.6 与 0.55，最大化空矩形面积，再以短边破同分；所有不得依赖量的每种取值下，每个可到达循环态都必须达标。建成后可调试，但不能靠 tick 级操作，之后零干预。判定次序在一次运行中固定，不能擅自把它改成每 tick 都可以换的对手。（R:8–32；T:2、8–16；C:3–11。）

**独立判断 J1。** 设计对象至少包含布局、固定设置和可实施的调试办法。可将正确性理解为：存在设计与调试方案，使每种允许机制取值、每个调试后允许到达的循环态都满足产率。调试能保证进入哪些状态需要单独证明。“存在一种周期流／一种好循环态”只给必要证据，不能顶替全称要求。把运行验证作为最末层可以，但其接口不能只有平均率。

### 3. 我会怎样试分

**独立判断 J2：先区分两个用途。** 压上界的模型必须包住全部达标布局，主问题的最优值或可靠界才可当 U；抬下界可以限制构型、用启发式，只要最后给出一张完整达标布局，它的面积才成为 L。两条路线可交换经证明的必要条件，不能交换没有覆盖证明的排除结论。（对应 M:17–23；C:138–145。）

**独立判断 J3：先试两道主要接口，不先认定固定层数。**

- 几何／离散主问题：选择目标矩形、非运输单位的位置朝向、台数、固定设置，以及足以约束布线的运输形状信息。把已证数量、面积、端口、供电与边带条件放进去。台数是变量；只在某目标面积已迫使台数取下限时才能固定。机器不必带可交换编号。（C:46–64、120–157；M:15。）
- 静态运输子问题：给定主问题决定，检查物理通道与分物品连续平均流。是否将运输格状态也交给子问题，需要实测；位置、端口朝向、运输格和路由往往是最紧的相邻决策，不宜全部逐层单向冻结。桥的两个物品格分开，真实相邻端口自动接通必须“当且仅当”。（R:16、59–68；M:15、19。）
- 运行／调试验证：候选静态全图之上的独立验证器，输出可复核的失败运行或充分性证明。只有能把失败归因于少量上层选择且证明对全部余下自由度都失败时，才适合成为会回割的第三层；否则先当候选检查器。种植再生环、混料、轮询、准入窗口、存货上限必须放在这一接口里。（C:58–68、80–106；M:21–23、47。）

这里的三类职责不等于必须三个求解器或三层 LBBD。LP 可以嵌进几何搜索，局部运行约束可以上收；若切开后每次都要传整张图，合并会更合理。

### 4. 各种失败分别能回什么

**独立判断 J4：先证明割排除的是所有补全。** 设主变量为 x，余下设计为 y，完整正确性为 F(x,y)。一次子问题只有证明不存在任何 y 使 F(x,y) 成立，才可排除该 x。固定了某条路由后运行失败，只否定这一完整候选；不能直接否定同一机器摆放下所有路由，更不能否定同样机数的所有布局。若失败只针对某组 x 的取值，要证明这些取值已足以导致失败，再写带前提的蕴含割。

**独立判断 J5：静态 LP 是最有希望返回可概括证书的接口。** 对固定物理图，可用流量守恒、端口／格容量、物品可通行性生成不可行证书；上层若含边是否存在或容量变量，需把证书正确提升成对其他上层赋值也有效的必要条件。单商品最小割很直观；多物品共享容量需联合 LP，不能因为每种物品各自都流得通就通过。机器配方是物品转换节点，供需随主变量变化，也必须进证书。（C:44、96、104；M:19。）

**独立判断 J6：至少区分四种输出。** 完整不可行证明可支持割；完整可行并通过运行证明可支持 L；某个放松可行只表示继续向下；TIMEOUT/UNKNOWN 只意味着本轮无结论。有限路由库失败、固定周期分母失败、某次仿真失败，均不能无条件上收为全局不可行。原样 no-good 若覆盖的是已证不可行的完整主赋值，可以正确却极慢；需要记录它每次能排除多大一类结构，而不只记录割数。

### 5. 最可能卡住的地方

**独立判断 J7：接口太宽、割太窄。** 机器位置一变，通道容量、相邻误接、弯路成本、供电与空矩形边缘全跟着变。纯几何主问题容易反复交来流不通的图；若反馈只能逐个封掉摆法，就在巨大空间里枚举。M:29–40 已有 E0 两个解流量失败、玩具 200 轮不收敛、粗网格 29 轮不收敛以及联合模型也难解的测点；这说明有困难，不证明 LBBD 永远失败，也不证明加一层就能解决。

**独立判断 J8：平均层切开了运行强耦合。** 52 个矿石出口全满载，裕量几乎为零；混做、混线、批量出货、有限存货和相位能造成“平均正确，实际饿死／堵死”。种子回路能否启动和保持正确不能由平均守恒替代。把上层选好的平均流当成下层必须实现的唯一流，可能排除同一布局的另一可实现流；只在构造分支内固定它，或保留重新选择的机会。（C:24–36、52–68、80–106。）

**独立判断 J9：固定最小机数和固定模板会误伤顶端。** 台数下限不表示可实现；适当增机可能换取简单物流。相反，纯料单配方点对点构造会丢掉最小机数混做／混线的分支。M:23 明确该构造只覆盖 219 台以上，不能拿它的失败压全局 U；C:143 说明目标 A=1113 才能推出九机型恰下限，而不是全局先固定。

**独立判断 J10：错误量词比求解慢更致命。** 存在一条良好运行，不是全部允许先后和全部可到达循环都良好。有限测试可以发现反例、验证工具实现，不能无条件提升为全称证明。反例足以否定完整候选，但从反例中提炼上层割还须处理未固定路由、设置、调试方式。

### 6. 怎样决定层数和切口

**独立判断 J11。** 每次只改变一处切口，使用相同目标、时间预算和输入比较：主问题解出的有效候选比例、子问题时间、证书提取时间、割的覆盖／复用范围、主问题增长与最后取得的 L/U 进展。切口的好处必须来自子问题更容易且反馈较强；“每层都变小”不够。若新增层不能返回比完整赋值 no-good 更可复用的解释，优先合并或仅保留为诊断器。若几何层始终盲猜，就上收局部流量／切线容量／端口可布线条件，或联合位置与局部布线；若联合模型太大，则用粗粒度条件、启发式构造与完整验证配合。层数是需要实验比较的架构选择，不是理论预先保证的常数。

**冻结结论。** 我最担心的不是“没有选对求解器”，而是尚未证明的接口契约：静态平均流、具体几何和鲁棒运行之间，哪些自由度由谁决定，失败究竟能排除哪一族补全。设计若长期靠弱 no-good、把局部失败提升成全局割，或把有限构造族当完整投影，就可能分别陷入性能死路或正确性死路。上述只是独立预判，尚未对老项目作事实断言。

<!-- INDEPENDENT-SECTION-END -->

冻结时间（UTC）：2026-09-23T03:28:19.670724+00:00。冻结范围为本节标题起至结束标记止（含尾换行）。SHA-256：`faaa2beb54e1d8a608e066a443daffa0dfb66c6cb0912d8a921cea4dc38eb526`。

| 当前输入 | SHA-256 |
|---|---|
| 《明日方舟：终末地》游戏规则.txt | `6e64e3903a65536c530b363c9f3aef8c1bb2a1c1193e866799125dd047159924` |
| 求解任务.txt | `1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac` |
| 求解约束.txt | `0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f` |
| 求解器/会议成果/会议3/纪要.md | `d6c92a966fd9b295d5ed9dab4fed9e63710b76206c13107a6897d86f42db9228` |

## 二、结论、材料身份与阅读入口

### 2.1 核心结论

**找到了真正讨论 LBBD 怎样设计的方法论，而且不是一份静止的文书。** 它从早期“摆放→连续流→精确路由→两类 no-good”的具体方案，发展到“薄处切、厚处聚；规则归属；cut 打包；工况与反馈粒度”，又在 9 月改成“分的是决定，层数由分组与先后产生，LBBD 与摆放—配口—接线必须分开评判”。[SP0:19–86](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md:19>) [CARD:30–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:30>) [ZMD1:34–77](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:34>) [IL4:15–37](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:15>)

**最可信的死路风险是接口失真和反馈经济性失衡，不是 LBBD 原理本身。** 已记录过的具体错误与风险包括：一次配口失败被提升到全部配口；不可行核漏掉障碍常量；所谓放松漏掉桥与分汇；连通后端根本没有消费数值流量。性能方面，有 33 小时停在第一轮配口枚举、587 条局部割仍找不到局部存活几何、联合后表达膨胀、压缩表达后仍 UNKNOWN 的连续记录。[SP5:82–113](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:82>) [RATE:3–43](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md:3>) [M5:15–21](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/m5_revalidation_20260803/NOTES.md:15>) [E118:6–10](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E118_solver_diverse_local_front_benders/RESULT.txt:6>) [E120:6–11](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E120_integrated_local_option_master/RESULT.txt:6>) [E121:6–10](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt:6>)

**后期材料已经主动修正了若干强断言，也实现了比逐点 no-good 更有信息的反馈。** 三机器封闭走廊里，语义反馈第二个提案成功，而整份配口 no-good 达到 200 次上限；旁路实验又证明旧割必须带运输域前提。9 月 6 日的可变摆放网络割已经出现一次整厂规模的回送与重解，但没有完成全厂见证。不能写成“后来一直没有研究”或“后来的研究已经证明新切法成功”。[COR:63–98](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:63>) [BYPASS:28–66](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_bypass_transfer_20260905/README.md:28>) [FLOWCUT:152–159](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:152>)

### 2.2 三种“方法论”及一类实现规格

| 类别 | 实际回答的问题 | 应读的原文 | 本报告的判读 |
|---|---|---|---|
| 纲领／押注 | 要到什么终点，资源押在哪，什么结果使路线继续或停止 | `30_research_charter.md` 是押注板；`research-charter/SKILL.md` 管持续预算、完成和能力声明。[BOARD:1–12](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/30_research_charter.md:1>) [CHARTER:8–24](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/research-charter/SKILL.md:8>) | 这些会影响研究行为，但不能替代 LBBD 的变量分组、子问题与回割设计。 |
| 研究的方法论／推理外环 | 怎样从规则、算术、构造和失败产生新知识，再改变下一轮问题 | `zmd-method` 第 2、3 节；29 号卡的问题观、预设、记账、推理关。[ZMD1:87–178](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:87>) [CARD:10–28](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:10>) [CARD:46–64](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:46>) | 研究循环可以产生割或改变表示，但不等于一轮 master—subproblem 循环。 |
| **LBBD／求解架构的方法论** | 哪些决定一起解、谁先定；跨层保留什么信息；下层能证明什么、上层能消费什么；怎样比较切口 | **29 号卡第 3、4、6 节；`zmd-method` 第 1 节；roadmap §0b 各版；`INNER_LOOP` 与架构问题页。** [CARD:30–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:30>) [ZMD1:34–85](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:34>) [IL4:15–73](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:15>) | 本报告的主对象。7—8 月正文主要按规则归属描述，9 月明确纠正为按决定分工。 |
| 具体架构／实现规格 | 当时实际采用哪几个模型，输入输出、开关和发布状态是什么 | specs/10、specs/11、`DIVISION.md`、状态表。[SP5:18–72](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:18>) [PIPE:88–98](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/11_pipeline_orchestration.md:88>) [DIV:9–56](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md:9>) | 这是方法论的一次实现及其证据，不能反过来当成方法论必然推出的唯一架构。 |

文件名不能单独决定类别：29 号卡有很大一部分直接讨论求解架构；`zmd-method` 同时收录内环、外环和消费纪律；`INNER_LOOP` 则在 9 月由“定下来的逻辑”改成“架构探索”。应按段落取用，而不是只把带“方法论”的文件归为研究哲学。[CARD:30–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:30>) [ZMD1:15–32](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:15>) [IL1:1–9](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md:1>) [IL4:1–9](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:1>)

**建议先读次序：** `zmd-method` 第 1 节了解成熟表述 → 29 号卡第 3、4、6 节了解操作判据 → 9 月 `INNER_LOOP` 了解已撤回的说法 → specs/10 了解真实实现边界 → 走廊、旁路和 E118—E121 了解判据经受了什么实验。每一项的原文位置都在本节表格及下文，完整原路径和哈希见第八节。

## 三、版本时间线：哪些是新增、修正和撤回

日期优先使用正文日期、原始消息时间和历史考古保存的 AuthorDate；归档 mtime 只作文件身份线索，不能充当精确写作时间。提交编号仅作为档案中的版本名引用，本次未运行 git。8 月 23 日考古报告对“首次”的考证仍是历史作者的结论；本次补抽原始会话，核对了其关键出生消息，未穷举所有更早会话。

### 3.1 specs/10：从理想闭环改成有明确边界的现实规格

| 时点／版本 | 原文主张与变化 | 判断与证据边界 |
|---|---|---|
| 正文标 `2026-03-23`，早期 `ACCEPTED_DRAFT` | 固定空矩形尺寸；master 摆放；连续 LP 预筛；LP 不可行取 Farkas 射线，锁定割面附近刚体后发 Type-I no-good；路由不可行取“最少冲突”后发 Type-II；路由可行即“输出终极蓝图”。还提出平移提拉、模板对称提拉、热启动从数十秒到几百毫秒。[SP0:19–86](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md:19>) | 这是设计承诺与实现说明混排的版本。同页已承认平移／模板提拉未实现、没有真 lazy callback；“几百毫秒”和“路由过即终极蓝图”没有在本页给出实测或完整运行证明。 |
| 2026-06-04 范式更新 | 引入 F1—F9，generator＋validator，声明主线 cut 已转 family 体系；同时承认 Step 8 真 master 集成待接。[SP1:8–12](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-codex-old/zmd_transfer_20260605_slim_20260606_0035/zmd/specs/10_benders_decomposition_and_cut_design.md:8>) | 把“框架已建立”写成“cut 的生成／校验已由其承担”，容易读成生产闭环已通。此版本有三个不同字节哈希，但正文完全一致，差别仅 CRLF/LF；见第八节。 |
| 2026-06-11—13 addenda | 增加 binding-local 证据阶梯；必须激活的端口才能支持 pose 级堵口割；核须带全部常量支持；D2 不是生产路由的放松，不准独立发 master cut。[SP2:93–119](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-codex-pj/zmd_pj/specs/10_benders_decomposition_and_cut_design.md:93>) | 这些不是措辞润色，是对真实过度剪枝风险的修补。同期仍保留旧“虚拟无线 generic-input”前提。 |
| 正文核对日 2026-06-26 | 重写开头：flow 仅诊断，不产 Farkas 或证明割；真正路径是 master→binding→routing；family 框架尚未生产接入，Step 8 抛未实现；旧 Type-I/II 明确降为历史。[SP3:10–16](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:10>) [SP3:18–80](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:18>) | 早期理想管线并没有按原文整体兑现。不能将 6 月前页首“当前主线已转”当作接入证明。 |
| 正文核对日 2026-07-11 | F8 退役；F1/F5/F6/F7 翻译已有，其他族 fail closed；direct bridge 默认关闭、认证禁用；仍未 promotion。[SP4:10–16](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-zmd-codex-autonomy-20260801/zmd-pj-codex/.claude/worktrees/agent-abbb35e6fe0946fe6/specs/10_benders_decomposition_and_cut_design.md:10>) [SP4:59–72](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-zmd-codex-autonomy-20260801/zmd-pj-codex/.claude/worktrees/agent-abbb35e6fe0946fe6/specs/10_benders_decomposition_and_cut_design.md:59>) | 四族有翻译不等于四族已进入认证生产路径。 |
| 正文核对日 2026-07-18 | generic-input 改成实体箱／核心输入口及真实路由终端，明确废止“正需求即无线免路由”的旧前提。[SP5:25–33](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:25>) [SP5:88–101](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:88>) | 模型语义改变会改变割的前提；旧割不能靠兼容命名复活。 |
| 8 月状态口径，不能再沿用 7 月规格 | 状态表写 F1/F6/F7 typed lowering；F5 shadow-only、无 lowering；F2/F3/F4/F9 为旧诊断；F8 retired；attach 仍默认关闭、未 promotion。[CURRENT:1897–1901](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/CURRENT.md:1897>) [FOUND:184–205](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/02_mathematical_foundations.md:184>) | 与 7 月 specs/10 对 F5 的描述不同。这里按时点列两者，不擅自把旧句合并成一份“最终实现”。本次没有重跑旧代码核验该状态。 |

### 3.2 原生方法论：7 月 16 日到 8 月 15 日

| 时点（UTC）／载体 | 主张怎样变 | 原文 |
|---|---|---|
| 07-16 20:03 原始用户消息 | 从“为什么不同层”追问到“薄处分开、厚处同住”，要求选择由推理走到结束点；20:07 明说不能每个方案都端到端测。 | [RAW:3640–3644](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:3640>) [RAW:3657](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:3657>) |
| 07-16 21:14，roadmap v1 `5bc5dd3` | 第一份耐久文本主要是“尺寸、传播、机器兼容”三腿；有好表达就进 master，反馈踏车就找可上收规则。薄厚聚类尚未完整写入。 | [RM1:47–59](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_5bc5dd3_v1.md:47>)；时间及与原话的差异：[MO:161–185](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:161>) |
| 07-16 23:21 追问；23:24 v2 `759263a` | 用户补问下放、切分／聚类、同住和先后；文本形成四元位置：切分、住址、管线序、下游验证人，分健全影子／精确本体／启发残部。 | [RAW:4040](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:4040>) [RM2:47–79](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_759263a_v2.md:47>) [MO:187–195](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:187>) |
| 07-16 23:34 追问；23:36 v2.1 `d1a3b04` | 用户用九条规则分成四组／五组举例，指出层数不能预先固定；文本加“有序划分”，层数和切口是输出；提出聚合力／切分力／信息依赖 DAG。 | [RAW:4077](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:4077>) [RM21:76–91](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_d1a3b04_v21.md:76>) [MO:197–203](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:197>) |
| 07-17 17:25—17:39 追问；17:43 v2.2 `0561994` | 用户问九类割为何恰好九类、有没有覆盖；再问包裹怎样由两层关系推出，及与下放的关系。文本承认九族来自失败归纳、没有覆盖证明；新增责任圈、数量律、上层词汇三问，再加依赖下层决策与否，统一归属／打包。 | [RAW:5111–5145](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:5111>) [RM22:93–107](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v22_roadmap.md:93>) [RM23:113–127](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v23_roadmap.md:113>) [MO:231–255](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:231>) |
| 07-19 21:54，v2.3 `cb7dbc1` | 外部重推后分开权威归属与表示归属；加入 `owner(r)=max owner(v)`、三极性、前件、局部对偶、等式挖掘、双账。 | [RM23:129–136](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v23_roadmap.md:129>) [MO:257–271](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:257>) |
| 08-03，v2.4—v2.6 | 从“规则住哪层”扩到任何求解／研究管线；加入硬合并与硬后置的对偶、门内目标耦合、拒绝率完整计量、操作卡。 | [MO:294–296](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:294>) [APX:273–330](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md:273>) |
| 08-04，v2.7 及补记 | 预设必须说明依据与丢掉的空间；零余量作锚点；条件锚点带前提；“主线是伸”替代一味小试探。 | [MO:297–299](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:297>) [CARD:20–28](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:20>) |
| 08-05，切缝经济学 | 33 小时枚举与两千余次来回后，增加工况相关性、死因谱×否决带宽、预编译；提出“先加粗通道、不先挪刀”。 | [APX:469–511](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md:469>) [MO:300](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:300>) |
| 08-14—15，29 号卡成文 | 先是 47 行速览卡 `310afe8`；`33e78bd` 把适用域放到 description，实质判据没换；`a9e5049` 重写成 70 行道理链；最终 `ea4d67…` 主要把权威指针改到 landing 存档。 | [SK0:12–47](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/310afe8.md:12>) [SK1:1–8](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/33e78bd.md:1>) [SK2:30–70](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/a9e5049.md:30>) [CARD:8](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:8>)；日期链：[MO:302–304](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md:302>) |

不能把“层数要决定”偷换成“必须先指定一个层数参数再排规则”。7 月原话的例子是分组和顺序改变后层数随之改变；同夜 v2.1 也写“有序划分”。后来把层数单列为第四坐标，是文书的一种展开方式；9 月才明确禁止把它当独立目标。[RAW:4077](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:4077>) [RM21:76–82](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_d1a3b04_v21.md:76>) [ZMD1:57–64](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:57>) [IL4:19–23](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:19>)

### 3.3 `zmd-method`、`INNER_LOOP` 和架构问题页的后继版本

| 文件版本 | 原文变化 | 能作出的判断 |
|---|---|---|
| `.claude/.../zmd-method/SKILL.md`，归档 mtime 08-28，17,924 字节 | 明确标“解读层／修补层”，第 1 节讲薄厚、四维位置、包裹；把死因谱／带宽标为后来的综合。[ZMD0:8–16](</mnt/wd_external/zmd-old-extract/docs/zmd-all/05-Codex清理备份/2026-09-19-devspace-worktrees/zmd-pj-aa6a19af/.claude/skills/zmd-method/SKILL.md:8>) [ZMD0:28–85](</mnt/wd_external/zmd-old-extract/docs/zmd-all/05-Codex清理备份/2026-09-19-devspace-worktrees/zmd-pj-aa6a19af/.claude/skills/zmd-method/SKILL.md:28>) | 来源层标注较细；不能把所有操作化逐字归给 owner 的出生原话。 |
| `.agents/.../zmd-method/SKILL.md`，归档 mtime 08-29，13,933 字节 | 保留第 1 节核心；开头说是共同理解，不是逐字转录；部分来源标签收进叙述，仍说明包裹菜单是后来的操作化。[ZMD1:8–13](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:8>) [ZMD1:34–85](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:34>) | 这是重编／精简，尚未完成 9 月的“规则→决定”纠正。正文未署精确修订时刻，不能只凭 mtime 断言作者当日作出全部变更；两份 mtime 的清单依据为 [LIST:843977](</mnt/wd_external/zmd-old-extract/listing.txt:843977>) [LIST:94422](</mnt/wd_external/zmd-old-extract/listing.txt:94422>)。 |
| `zmd-research-next copy/INNER_LOOP.md`，正文 09-02 | 内环定义为多层 CP-SAT；常量假设化；cut 约等于核；“约束落在最后一个词所在层”；由两份 268 摆法推配口层价值；说上界只能靠外环、引用 1122。[IL0:7–49](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next copy/INNER_LOOP.md:7>) | 在改按决定分层的同时，又把特定框架、核心反馈机制和若干性能推断写得过强。 |
| `zmd-research-next/INNER_LOOP.md`，正文仍 09-02，mtime 09-03 | 与上一份的正文差别只在第 49 行：1122／口前格推导改为“已撤回”，但仍保留“上界只能靠外环”。同字节另存于 `history/before-2026-09-04/INNER_LOOP.md.txt`。[IL1:49](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md:49>) | 这是一次明确撤回，不是另一个独立实验。其余早期强句仍在；两个代表副本的 mtime 依据为 [LIST:133879](</mnt/wd_external/zmd-old-extract/listing.txt:133879>) [LIST:133547](</mnt/wd_external/zmd-old-extract/listing.txt:133547>)。 |
| 09-08 历史保存稿 | 明确分的是决定、不是规则，层数由分组和先后产生；不预选 LBBD；把常量假设化降为一种办法；允许有根据的架构猜想；纠正“只有外环能给上界”和 575 秒／30 毫秒外推。[IL2:15–41](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-08-assumptions-and-judgement/INNER_LOOP.md.txt:15>) [IL2:59–69](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-08-assumptions-and-judgement/INNER_LOOP.md.txt:59>) | 9 月评审的若干批评已被吸收，但评审建议与 owner 已定定义仍分开。 |
| 09-09 架构入口修复前快照 | 将失败段改成一般条件性推论，而不是“不开关就只能失败三个字”；强调可以从失败寻找共同原因；可表达性段也不再冒充架构决定。[IL3:35–51](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/INNER_LOOP.md.txt:35>) | 在原则上拓宽层间信息，不再由一种核 API 定义所有方法。 |
| 09-09 最终 `INNER_LOOP.md` | 标题改为“求解过程与内环架构探索”；说明这是定义与判据，不能代表全部过程；连接生产关系、机器与实际物流的共同构造，完整控制器未建。[IL4:1–13](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:1>) | 已从“现存线性层的定理化解释”转到多种过程的比较；没有宣布 LBBD 被否定。 |
| 架构问题页 09-09 保存稿→最终稿 | 保存稿说完整路径构造器下一步实施；最终稿明确已有局部完整路径／机身联合构造、局部运行读回和改进，整目标仍 UNKNOWN、整厂过程未完成。[Q0:1–13](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/questions/how-should-the-solver-be-divided.md.txt:1>) [Q:1–30](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md:1>) | 这是实施状态的真实推进；“有工作过程”不等于“自动控制器已存在”。 |

另有一个不能混为正式后继版本的短支线：`global_shortver_quarantine/zmd-method.SKILL.md` 为 76 行“短版执行入口”，仍保留薄厚、四维规则住址、包裹、外环与 witness 要求，且自称不是完整方法规范，并回指长版。它在所存隔离目录中的存在不能证明当时默认入口已采用它。[ZMDSHORT:8–29](</mnt/wd_external/zmd-old-extract/docs/zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/global_shortver_quarantine/zmd-method.SKILL.md:8>) [ZMDSHORT:53–76](</mnt/wd_external/zmd-old-extract/docs/zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/global_shortver_quarantine/zmd-method.SKILL.md:53>) 08-29 重构执行收据另记录过“主文 139 行、两份附件”的中间状态；这是执行收据所述版本，不能用其行数冒充本报告读取的 ZMD1（194 行）。[ZMDRESTRUCT:18–34](</mnt/wd_external/zmd-old-extract/docs/zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/EXEC_METHOD_RESTRUCTURE.md:18>)

9 月还明确撤回“分流／汇流的账已经决定归配口层”；发现一条新规则不能直接决定最后切法。“筛选 cut”的一次讨论其实在问外环选哪些命题研究，不是在选给 master 发哪一条割。两种问题必须分别保留。[Q:82–94](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md:82>) [IL4:57–67](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:57>)

## 四、如实重建：它究竟教人怎样使用 LBBD

### 4.1 当时的职责链与反馈层级

7 月现实实现与 9 月对旧代码的观察，可以合成下面这张职责表；它描述的是历史实现，不能读成最后推荐架构。[SP5:18–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:18>) [DIV:9–56](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md:9>)

| 环节 | 它定什么／消费什么 | 下层反馈应当回哪里 |
|---|---|---|
| 外层目标搜索 | 指定空矩形尺寸／候选范围 | 只有有权限的完整不可行结论才排该目标；UNKNOWN 不排目标。早期规格按固定 `(w,h)` 可行性组织。[SP0:21–36](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md:21>) |
| 候选池与 master | 合法位置、朝向；必建实体选择其摆位；桩、箱、空地锚点；可选口前格数量条件 | pose 级割必须对该摆放下所有尚可选的 binding／routing 有效。[DIV:13–20](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md:13>) [SP5:52–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:52>) |
| binding | 选哪些实体口、各口送什么货、通用槽分配 | 当前 binding 失败先排 binding；只有替代穷尽或独立证明，才能排 placement。[SP5:82–96](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:82>) |
| routing precheck | 口前格、来源／去处、自由空间连通分量 | 可直接编译回 binding 的拒绝条件，固定摆放时应尽可能批量消费，不能反复随机踩同类堵口。[DIV:24–28](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md:24>) [APX:473–511](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md:473>) |
| routing | 物流格、朝向、物品路线与实体形状一致性 | 失败需带完整上下文；来自更窄 separator 的 UNSAT 不能作完整路由否定。[DIV:17–18](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md:17>) [SP5:103–113](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:103>) |
| 终审／发布 | 检查对象与身份，按所声明命题验收 | 内部 `RUN_STATUS_CERTIFIED` 不是公开认证；更不是现行全称产率证明。[SP5:26–44](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:26>) [PIPE:88–98](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/11_pipeline_orchestration.md:88>) [RATE:41–45](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md:41>) |

连续 LP 在早期蓝图里是中间的强筛选器，在 6 月以后所读生产规格里却只是诊断器。这是实际职责退缩，不能把“有 flow_subproblem 文件”当作连续流已经把原问题投影给 master。[SP0:28–31](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md:28>) [SP3:10–16](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:10>) [SP5:23–24](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:23>)

### 4.2 主张、理由、证据和保留边界

| 主张 | 原文给的理由与做法 | 当时支持／后来限制 |
|---|---|---|
| 薄处切，厚处聚 | 少信息能压成小接口则可拆；共享大量变量、互相剪枝和交织证明义务则不宜拆；按名称分 placement/routing 没有充分理由。[ZMD1:36–47](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:36>) | 这是设计判据，不是已经解出的最优分区算法。E118—E121 给出“弱割难、合层也难、表示还能改”的实际过程，不能把薄厚当静态标签。 |
| 推理筛选，便宜探针，最后端到端比较 | 全部架构都做完整工程试验太贵；先淘汰不健全、尺寸爆炸、不兼容的候选。[RAW:3657](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:3657>) [RM1:49–56](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_5bc5dd3_v1.md:49>) | 原则有用；“必须推到选择自然出现”没有保证总能终止。9 月允许有根据的猜想并由实践修正。[IL4:23](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:23>) |
| 规则拆成影子／本体／启发残部 | 上层只能用在其变量上可求值、已证明必要的投影；下层保留精确检查；启发式不能排真解。[CARD:30–38](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:30>) | 保证投影方向有数学意义；“本体永远下游”不是所有架构的普遍义务。若精确等价消去路径变量，本体可变成定理＋重建器。[COR:25–38](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:25>) [COR:69–74](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:69>) |
| 三腿测试与信息依赖 | 尺寸紧凑、传播有力、引擎兼容；信息依赖约束可求值顺序；表示改变则重新检查归属。[RM2:57–75](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_759263a_v2.md:57>) | 有实测／算术支持其重要性，但没有统一代价函数。E121 保持同一可行集，把动态系数项数量降至约 1/37.56，仍未出解。[E121:74–142](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt:74>) |
| 层数也是结果 | 把规则／决定分组并排序，而不是继承历史站点；合层增强传播但加重模型，分层利用专用引擎与拒绝成本梯度。[RM21:76–87](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_d1a3b04_v21.md:76>) | 9 月改为层数由决定分组与先后产生；没有最后选定几层。[IL4:19–29](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:19>) |
| cut 要由两层关系推出 | 从责任圈、可抬数量律、上层词汇三问设计；依赖下层决定的部分不能硬上收；每条割带前件。[CARD:40–44](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:40>) | 正确核心是“证明仍在何种上层条件下成立”。责任圈越小仅在同一语义／固定上下文下才有更强排除；最小核并不保证最短总求解时间。 |
| cut 族需要覆盖审计 | 九族来自历史样本，不能因恰有九个就说完备；枚举验证者拒绝路径，审查其可泛化表达，以兜底 no-good 比例监测遗漏。[RM22:93–107](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v22_roadmap.md:93>) [CARD:42](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:42>) | 审计能发现缺项；有限返回分支不保证能得到小而完备、易算的数学分类。第六节专门诊断这一步。 |
| 每族可上收、保留或退役 | 有广适用算术律则毕业上收；真零散例外留 F5；前提错则退役，F8 是原文自举反例。[RM23:123–127](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v23_roadmap.md:123>) | 是方向分类。不能因 family validator 通过就宣称生产 master 已消费；8 月 F5 仍 shadow-only。[CURRENT:1897–1901](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/CURRENT.md:1897>) |
| 按“死因谱×反馈粒度”修切缝 | 集中死在另一层、反馈却一次只杀一个，就批量编译可用域／族割；几何变固定或密度变高就重审。[APX:469–511](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md:469>) | 33 小时记录、走廊 2 次对 200 次支持这个具体机制。A1 的 128 份堵口样本却不能证明堵口不可避免，死因谱仍受采样方式影响。[M5:15–21](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/m5_revalidation_20260803/NOTES.md:15>) [COR:71–80](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:71>) [A1:7–11](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/where-a1-jams.md:7>) |
| 先加粗通道，不先挪刀 | 保留已有专用工具、证明模块化和便宜门，先把已知信息跨过去。[CARD:54–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:54>) | 对已知前格条件有针对性；原文把挪刀近似等同于退回巨模型，遗漏局部联合和换分组。9 月明确尝试联合不必先修完旧管线。[IL4:37](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:37>) |
| 正确性分账 | 必要投影压 U，充分限制找 L，精确语义作检查；UNKNOWN 不改两账；早放行暂定。[CARD:46–52](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:46>) | 与独立判断一致，是应保留的基础。它没有替代原题到模型的覆盖证明，也没有补足运行接口。 |
| 常量假设化与核 | 上层事实改成下层有语义对应的开关，使不可行理由可追溯；核不保证最小，固定前提也必须带走。[IL1:13–21](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md:13>) [IL4:39–45](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:39>) | 是一种接口实现，不是 LBBD 的定义。9 月走廊使用手证前缀族，网络割使用最大流割集，均没有靠自动核发现定理。[COR:74–76](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:74>) [FLOWCUT:47–84](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:47>) |

### 4.3 九族到底是什么

6 月更新列的家族是：F1 区域容量、F2 割集、F3 端口暴露、F4 分量可达、F5 模式 no-good、F6 形状装填 Hall 条件、F7 供电覆盖 hitting set、F8 电网可达、F9 密度包络。它们不是九层，也不是九个自动穷尽失败的定理。[SP1:12](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-codex-old/zmd_transfer_20260605_slim_20260606_0035/zmd/specs/10_benders_decomposition_and_cut_design.md:12>)

原文自己承认它们从失败样本归纳而来，没有覆盖性证明，且 F8 建立在错误游戏前提上。后期 registry 是 F1—F7＋F9；“在册”“有 validator”“有 generator”“可翻译”“生产启用”是五件不同的事。例如数学基础页明确 F2/F4 generator 仍为 stub，通用 minimize 仍未实现，F5 只有专用删减实现。[RM22:95–107](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v22_roadmap.md:95>) [FOUND:184–205](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/02_mathematical_foundations.md:184>)

**判读。** 九族体系提供了一张找证据／管生命周期的目录，不能充当“为什么本题应这样分层”的证明。最有效的新割也未必从已有九族名称里自动长出来；需要看当前对象的接口，比如封闭走廊的前缀式和可变摆放网络的供需式。

## 五、实测支持到哪里：卡住后的研究与自我纠正

以下“结果”均指老材料记录的实测或检查结果。本次回读原报告、定理和记录，不重跑求解器，也不把旧规则域直接映射为现行题面的证据。特别是 219、266、268 台／单位等口径各有历史前提，不能与现行 C 的 217 台下限直接互换。

### 5.1 最值得看的连续证据

| 记录 | 原文实际结果 | 支持的主张 | 不支持的推论 |
|---|---|---|---|
| 08-03—05 M5 重验 | 第一次约 9 分钟 OOM；重试始终停在 iteration 1 的 binding↔routing，约 33 小时后停止；master 供电摆放已可行，完整存在性仍 OPEN。[M5:3–21](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/m5_revalidation_20260803/NOTES.md:3>) | master 快照可行远不够；内部枚举可以吞掉全部预算；工况和修正后候选池会改变成本。 | 33 小时不是不可行证明；无证据证明合并必更快。 |
| 08-05 方法补记 | 作者记录正式门 2,259 次以上来回，冒烟的 3 次中已有 2 次 front 阻塞且 routing 未运行；提出固定布局预编译端口域。[APX:479–508](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md:479>) | 这里存在可提前知道却未消费的信息，反馈粒度是实际瓶颈。 | 2,259 是原文的“以上”记录，本次未重计原日志；不能推广为所有切口都同病。 |
| 研究树 E118，1,205 候选固定域 | 从 504 割继续，8 份新几何均被完整局部选项检查拒绝，83 新割，总 587；最好仍有 6 个选中机身没有局部可行选项，终局两臂 UNKNOWN。[E118:69–145](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E118_solver_diverse_local_front_benders/RESULT.txt:69>) | 已有真实 Benders 学习和独立重放，不是根本没回割；但多学割没有在这轮改善构造。 | 不证明 587 割已经饱和，也不证明其无用；它们会影响后来 master 搜索。 |
| E119 饱和审查 | 新增 83 割中 61 个结构相对原库为新，73.49%；相同主体反复死于不同阻挡配置；提议把“至少一个局部选项可行”直接放进 proposer。[E119:83–151](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E119_local_front_cut_family_saturation_audit/RESULT.txt:83>) | 只按具体阻挡配置解释同一个存在性条件，会反复支付成本；值得试表示改变。 | “旧割命中零”本来就是自适应生成保证，不能据此说旧割没剪枝。原文第 128 行已说明。 |
| E120 联合局部选项 | 同一语言中，9,808 个选项、11,016 变量、21,369 约束、4,548,696 个动态系数出现；两臂各约 90 秒 UNKNOWN、无候选。[E120:64–119](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E120_integrated_local_option_master/RESULT.txt:64>) | 合并确能精确表达关系，却可能有很高表示成本；变量个数不是唯一规模指标。 | 原文把关系称为“太稠密”是该次诊断；两次 90 秒不足以证明所有联合求法都不行。 |
| E121 占格因子化 | 共享占格变量保持相同可行集，动态项降到 121,095，缩小 37.5622 倍；两臂约 90 秒仍 UNKNOWN；47 份旧几何、384,160 个选项检查无差异。[E121:51–142](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt:51>) | E120 的 455 万项不是数学上不可避免；表示可以大改而不改变分工／可行集。 | 压缩表达不等于发现可行解；也不能仅凭仍 UNKNOWN 宣判该固定骨架无解。 |
| 09-04 冻结 A1 | 128 份样本都先堵口；精确最小化却达到零堵口，然后暴露断连；全预检编译进普通配口后该语言内不可行，另核得到 279 矛盾。[A1:7–11](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/where-a1-jams.md:7>) | “首个失败原因”不等于不可避免的根因；要么优化查反例，要么完整刻画域。 | 样本全堵口不证明摆法必堵口；编译语言不可行不能排所有游戏配口。 |
| 09-02／04 的 268 实验 | 摆放已计 front-clear 数量；普通 binding 未启用 routing context，仍选堵口；575 秒与 30 毫秒分别只测摆放／配口，路由预算没有执行。[DIV:24–30](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md:24>) [IL4:69–71](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:69>) | “有足够可用口”和“实际选对口”没有在接口上闭合。 | 两份高度相似摆法不足以证明整个 binding 层无价值；不能把未跑的 3600 秒算成完整一圈实测。 |
| 09-05 封闭走廊 | 三机、13 运输格，4,320 配口／8,640 匹配，348 个物理可行；前缀容量＋终端兼容与全枚举一致。联合、投影和语义反馈都找到局部最优；语义反馈第二提案成功，no-good 200 次停。[COR:7–80](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:7>) | 强而有前提的投影可以作为预编译、反馈，甚至消掉子问题变量；“有意义的割”确有实测例。 | 不是 LBBD 战胜联合；三者都成功。目标是局部位置 k，不是全厂空矩形。 |
| 09-05 加旁路迁移 | 同一固定消费机位的 540 配口中，旁路使 234 个可行；旧前缀式会误排全部 234；新图全部相关边割仍放过 54 个形状非法配口，加 `a+b≤2` 才在此有限域吻合。[BYPASS:28–96](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_bypass_transfer_20260905/README.md:28>) | 割要带域前提；图容量不包含桥／转弯的全部实体形状信息；需要从反例得到具体新条件。 | 旧闭域定理没有被推翻，推翻的是跨域无条件使用；新式也不保证任意区域充分。 |
| 09-05 实际 routing 后端流率对照 | 同一 18 状态拓扑返回 FEASIBLE；每口 2/5 时共同通道为 4/5，可行；每口 3/5 时需 6/5，容量 1 不足。后端根本未接数值率。[RATE:3–39](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md:3>) | 连通接口缺数值率是真实可复现的语义缺口，而且发生在运行／相位之前。 | 不是证明曾有完整 Q1 工厂被错误发布；只核这一固定拓扑和外部率义务。 |
| 09-06 可变摆放网络回割 | 6 个小固定配置与联合 C 模型一致，失败割排原图而放过 5 个已知修复；整厂 feedback_005 返回一份摆放、原矿网络只有 10/52、加割再解后 UNKNOWN。[FLOWCUT:105–118](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:105>) [FLOWCUT:152–159](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:152>) | 从几何常量走向可变姿态／空格表达的回割已有实现，不能说永远只会整图 no-good。 | 零箱／活动类前提仍在；C 网络不是联合十九物品流；一次整厂反馈不证明速度优势。 |

E118—E121 的正文未署逐次实验日期；代表文件在 listing 的 mtime 分别为 08-29、08-29、08-29、08-30，只可作为档案线索。清单坐标：[LIST:121016](</mnt/wd_external/zmd-old-extract/listing.txt:121016>) [LIST:121022](</mnt/wd_external/zmd-old-extract/listing.txt:121022>) [LIST:121028](</mnt/wd_external/zmd-old-extract/listing.txt:121028>) [LIST:121034](</mnt/wd_external/zmd-old-extract/listing.txt:121034>)。上述顺序由实验明确的承接关系确认：E119 审查 E118，E120 替换 E117/E118 的间接表示，E121 因子化 E120。[E119:6–9](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E119_local_front_cut_family_saturation_audit/RESULT.txt:6>) [E120:6–11](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E120_integrated_local_option_master/RESULT.txt:6>) [E121:6–10](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt:6>)

### 5.2 后来的“反馈”比旧 no-good 多了什么

**封闭走廊的原文推理。** 对切在列 j 与 j+1 之间的唯一通路，物品 c 的净源汇差记作 `d_c(j)`；必要条件是 `|d_A(j)|+|d_B(j)|≤1`，另加同列源汇物品兼容。在该纯料、简单路径、单位流、闭域模型里，原文还给出充分性的逐格构造。第一批 16 个反馈式一次删除共同 master 域 3,600 配口中的 3,252 个，留下恰好 348 个可行者。[COR:25–38](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:25>) [COR:71–80](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:71>)

**我的判断。** 这里改进的关键不是把不确定的“最小核”缩得更小，而是找到表达整类失败的数学投影。它既可以成为 LBBD 的反馈，也可以直接编译进联合模型，因此实验支持“改进信息表示”，没有独立选定“必须分层”。

**可变摆放网络的原文推理。** 在包含全部候选的固定数学节点全集中，供给 `b(x)` 和容量 `cap(x,F)` 随姿态选择 x、自由格指示 F 改变。失败分区 S 给出必要式 `Σ b_v(x) ≤ Σ cap_a(x,F)`；对 `min` 形式容量选取失败点处取等的仿射上界，得到能回 master 的线性必要式。必须枚举全候选目录，包括当时未选中的姿态；否则遗漏“换一个未选姿态修复”的项，割会错误。[FLOWCUT:11–84](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:11>)

**我的判断。** 这正面补上了早期“锁定割面附近肇事刚体”没有说明的证明步骤：如何让在固定图上找到的容量证据，对后来改变的图仍有效。它不是普遍完成了原题投影；零箱、活动角色、权重和候选域都仍是前提。该正文 130 行的“首次尝试没有 proposal”是较早记录，152—159 行追加的 feedback_005 已经走过一次 proposal→失败→割→重解；不能只读前段宣布“没有任何整厂回割”。

### 5.3 明确修正／撤回清单

| 旧说法或用法 | 后来的纠正 | 性质 |
|---|---|---|
| Farkas 流反馈似乎已在主循环工作 | flow diagnostic-only；无射线／proof-bearing cut；旧 Type-I/II 降为历史。[SP5:74–80](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:74>) | 实现声明撤回／澄清，并非 Farkas 方法被数学否定。 |
| 路由当前选择失败就可禁摆放 | 先穷尽 binding 或补独立 placement 证明。[SP5:82–86](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:82>) | 割的量词纠正。 |
| raw core 已包含所有原因 | 加 occupancy／端口常量支持；即使如此还要证明 separator 是放松。[SP5:103–113](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:103>) | 两种独立错误的连续修补。 |
| generic-input 可无线免路由 | 成品必须接实体 provider 口；旧无线解释废止。[SP5:88–101](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:88>) | 游戏／模型语义纠正。 |
| 九族作为既有方案、F8 在册 | 承认是归纳无覆盖论证；F8 前提证伪退役。[RM22:95–107](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v22_roadmap.md:95>) [CURRENT:1897–1901](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/CURRENT.md:1897>) | 家族选择与前提的自我否定。 |
| 四维坐标是在分“规则” | 9 月改为分决定；层数随分组与先后产生。[IL4:19–23](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:19>) | 方法对象纠正。 |
| 配口与分汇账已经决定同层 | owner 明确撤回已定说法，最终归属仍待全部相关事实。[Q:84–88](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md:84>) | 架构结论降为候选。 |
| 575 秒＋30 毫秒就足以宣判旧切法 | 后文承认没有整圈实测，也不能按堵口数推重解数。[IL4:69–71](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:69>) | 性能论证收窄。 |
| 上界只能靠外环、与求解器无关 | 上界也可来自放松模型和完整排除证据。[IL1:49](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md:49>) [IL4:65](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:65>) | 一般性错误修正。 |
| 架构必须先穷尽理由再试 | 9 月允许以有根据的猜想起步、在构造中补足或推翻。[IL4:23](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:23>) | 研究选择纪律放宽。 |
| 端口前格整格必须独占 | 后继联合构造发现整格预留拒掉运行控制中的 12 条路；保留必要轴允许垂直桥通过，123 个接口分别通过。[Q:50–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md:50>) | 具体接口从“格”细化到“轴”；不是所有布线完备性已证。 |

## 六、逐条对照独立判断，并诊断方法本身

### 6.1 与冻结判断 J1—J11 的对照

| 冻结判断 | 老材料对应事实 | 审计结论 |
|---|---|---|
| J1／J10：原题有鲁棒运行量词 | 后端连数值率都未消费；后期工作过程才明确 timed supply、真实入口与复制语义；有限 traces 不能代替无界保证。[RATE:17–45](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md:17>) [CONNECT:119–130](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/notes/2026-09-08-connected-production-construction.md:119>) | 预判得到具体支持。静态 LBBD 必须有到原题的桥；有别的认证环节并不自动完成它。 |
| J2：L/U 两条用途必须分开 | 29 号卡已明确双账与三极性。[CARD:46–52](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:46>) | 不能批成“老方法完全不懂放松／构造之别”。风险在实际实例域和结论使用，而不是这条原则缺失。 |
| J3：位置、口、路由不能按名词自然独立 | 9 月明确纠正为决定分组；配口未消费 front-clear 是实例。[IL4:19–33](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:19>) [DIV:24–28](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md:24>) | 预判吻合，但该实例首先证明接口漏信息，不单独证明合层必胜。 |
| J4：失败要否定全部补全才能投影 | binding 替代、障碍常量支持和 D2 非放松三条 addenda 正是同一问题。[SP5:82–113](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:82>) | 已发生的正确性风险，不只是设想。 |
| J5：连续／网络证书可能是较好接口 | 老 flow 未实现证明回路；9 月闭域前缀、可变摆放网络已给成功局部／一次整厂反馈。[SP5:23–24](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:23>) [COR:71–80](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:71>) [FLOWCUT:152–159](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:152>) | 有正面支持，但尚无全厂性能优势；冻结节的“最有希望”仍只是研究判断。 |
| J6：UNKNOWN、放松可行、完整可行要分开 | specs 与 E118—E121 一直明确 UNKNOWN 不变 L/U。[SP5:52–58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:52>) [E121:165–170](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt:165>) | 应保留。不能将长期 UNKNOWN 变成“方法已证无效”。 |
| J7：弱割导致枚举 | 33 小时、局部新割无改善、走廊 200 次 vs 2 次构成三种尺度的证据。[M5:15–21](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/m5_revalidation_20260803/NOTES.md:15>) [E118:97–145](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E118_solver_diverse_local_front_benders/RESULT.txt:97>) [COR:71–80](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:71>) | 支持窄反馈可能不经济；不证明所有弱割都毫无价值。 |
| J8：固定平均流可能压掉另一可实现流 | 老后端先前未传数值率；后期速率／拓扑分离已明确。[RATE:17–45](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md:17>) | 找到信息遗漏，未找到“因固定唯一流而错删某完整工厂”的直接事故；该项保留为本题设计风险。 |
| J9：最小机数／模板不能普遍固定 | 9 月指出 632 满速口是过紧拷贝；旧实验均有模板／角色域；当前正式 1113 才强制下限。[IL1:31–35](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md:31>) [E118:69–82](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E118_solver_diverse_local_front_benders/RESULT.txt:69>) [C:143–146](</home/zhuran24/zmd-research-fresh/求解约束.txt:143>) | 一致，但不同规则／单位口径不得混用。 |
| J11：同题面比较切口、记录总成本 | 局部走廊做了共同域比较；E120→E121 提醒表示可独立改变；后期明确没有整厂一圈比较。[COR:63–98](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:63>) [E121:51–142](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt:51>) [IL4:69–73](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:69>) | 预判得到细化：不仅比较层数，还要分开语义分组、具体编码和反馈强度。 |

### 6.2 D1：先固定切法，再给规则分住址，可能形成循环论证

**原文。** 29 号卡以 `owner(r)=max{owner(v)}` 说明规则权威归属，并说这是语义必然；`zmd-method` 按规则给四维坐标。[CARD:38](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:38>) [ZMD1:57–64](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md:57>)

**判断。** 公式的右边已经假定各变量归属与层序。它能回答“在这套表示里，完整求值最早何时信息齐全”，不能反过来推出这套分组最好。先把路由放最后，再因规则用了路由变量而把它放最后，没有论证为什么路由变量不能换一种表示、部分前移或与局部摆放联合。这会让方法论擅长修既有切法，却难以发现切法本身不划算。

**进一步问题。** “共享决策变量的片必须同住”若照字面当普遍定理，几乎会消灭分解：LBBD 正可以把共同的主变量固定成参数后，使多个子问题容易处理。真正应量的是**条件化后**剩余耦合，以及可传递的证明／目标信息，不是原始规则有没有共用变量。9 月已经明确“固定接口后合法可组合才算独立”。[RM2:57–60](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_759263a_v2.md:57>) [IL4:13–21](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:13>)

这与 LBBD 原论文一致：它从变量分组、固定试值、考察下层证明对哪些其他试值仍成立出发，并没有规定共享变量的约束必须永远在一个求解上下文。[Hooker 与 Ottosson，§2，PDF 第 4—5 页](https://johnhooker.tepper.cmu.edu/benders.pdf)。此项外部核对在第一节冻结之后完成。

**风险类型：** 架构保守和错误推理；不是已证明旧 LBBD 无效。后期按决定分组的纠正值得保留。

### 6.3 D2：从下层失败到上层割，中间缺的是量词，不只是“找更小的核”

**原文错误与风险。** specs/10 依次记录 binding-local 误升格、遗漏布局常量、D2 漏桥和分汇。[SP5:82–113](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:82>)

**判断。** 设位置为 x、配口为 b、路由为 r。证明 `¬∃r F(x*,b*,r)`，只允许禁 `(x*,b*)`；要禁 x*，要证明 `¬∃b,r F(x*,b,r)`。把核缩小到只剩两个机器编号，不会自动消掉固定 b、障碍、候选域、空矩形、路由语言等前提。一个在更严格模型内的核，就算重放千次仍不可行，也不能排它没有覆盖的原题补全。

**早期提拉另有一步没有保证。** “空间平移不变”最多在环境也相容时支持一组对象共同平移；早期式子 `Σ_i Σ_{q∈Δ(p_i*)} z_iq ≤ |Ω|−1` 实际禁止各对象在各自邻域内独立变化的笛卡尔积。即使原冲突整体平移仍冲突，独立挪开一台也可能解除冲突。需要证明这个更大排除集，而不是靠“平移”这个名字。该技术原文明确未实现，因此这里是设计式的缺证，不声称已经因此误剪生产解。[SP0:63–74](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md:63>)

**风险类型：** 正确性死路。现行若用 LP 或运行反例回割，也必须完整处理相同义务。

### 6.4 D3：反馈再精确，也可能只是在解一个没有产率的代理题

**原文。** 7 月认证链不由 flow 决定；9 月固定拓扑实验显示 rate 根本不在后端接口内。[SP5:23–33](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:23>) [RATE:17–45](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md:17>)

**判断。** 把静态存在有向路、选口和供电做成很严格的证据链，仍然没有原题要求的连续供货、混料、有限库存、未知先后与调试可达性。这个缺口先于“要不要更多层”。给没有 rate 的路由更大的预算、更多哈希检查、更细核，都不能凭空引入该数值义务。

**对现行题的后果。** 平均流是很有用的上界放松；用于下界时必须与实体通道和运行保证接起来。当前 T:2、C:3—11 的全称要求，保留“仓库同时可以接受两种成品”的题面前提，不能被一次路由 FEASIBLE 或一条好运行轨迹替代。[T:2–15](</home/zhuran24/zmd-research-fresh/求解任务.txt:2>) [C:3–11](</home/zhuran24/zmd-research-fresh/求解约束.txt:3>) [M:19–23](</home/zhuran24/zmd-research-fresh/求解器/会议成果/会议3/纪要.md:19>)

**风险类型：** 目标迁移。不能称老项目暗中把连通等同吞吐——后期原文已公开声明边界；问题是这个边界迟迟未桥接到完整工厂。

### 6.5 D4：“有限拒绝路径×最泛化表达”没有给出一个可执行、廉价的割覆盖算法

**原文。** 29 号卡和 v2.2 称 cut 类型空间有界可枚举，等于验证者拒绝路径清单乘每条最泛化健全表达。[CARD:42](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:42>) [RM22:100–107](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v22_roadmap.md:100>)

**判断。** 程序只有一个 `return INFEASIBLE`，也能表示极复杂的不可行集合；有限控制流不意味着少数短公式能描述这个集合。若允许足够强表达语言，最强投影本身就可能与完整子问题一样难。若限制语言，“最泛化”还可能有多个互不包含的答案，必须先规定比较关系与代价。

E119 并没有看到一个简单反复饱和的局部死因族；E120 把同一存在性关系直接编码后，又付出稠密系数成本；E121 才证明其中大部分重复可消掉，却仍未解决搜索。这串记录比“应当能归纳出一个小定理”更有判别力。[E119:93–151](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E119_local_front_cut_family_saturation_audit/RESULT.txt:93>) [E120:85–149](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E120_integrated_local_option_master/RESULT.txt:85>) [E121:74–142](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt:74>)

**修正方式。** 把覆盖审计当诊断，把小而有效的割族当待检验的性能假设；允许先用健全弱割、一次性必要式、局部联合和换表示竞争。不要把“发现一套完整语义死因学”设为开始求解的门票。

### 6.6 D5：“先加粗通道，不先挪刀”在没有停止条件时会固化旧架构

**原文。** 挪刀被描述为退回巨模型、交还所有分解收益。[APX:482–485](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md:482>) [CARD:58](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:58>)

**判断。** 这是固定摆放中 front 可预编译的合理局部建议；作为一般法则则排除了中间方案：只合并一台机器与邻近通道、按生产关系共同修改、选一部分口变量进 master、让几何与流量共享摘要。局部联合不等于整图巨模型，强反馈也不保证比联合便宜。

原方法同时说层数待定，却给现存切口默认优先权；执行者可能永远觉得还欠一族割、一次预编译，迟迟不比较替代分组。后期已经明确“尝试联合表示不以修好整套旧分解流程为前提”，并有真实联合局部构造。[IL4:37](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:37>) [CONNECT:132–167](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/notes/2026-09-08-connected-production-construction.md:132>)

**风险类型：** 性能和研究路径依赖。现行会议 3 的弱反馈／联合难解两侧测点，正需要有限对照，不需要预先押某一边必胜。[M:29–45](</home/zhuran24/zmd-research-fresh/求解器/会议成果/会议3/纪要.md:29>)

### 6.7 D6：按单次成本从便宜到贵排门，不是一般的最优次序

**原文。** 管线序反复要求按实测拒绝成本便宜→贵。[RM2:62–65](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_759263a_v2.md:62>) [CARD:32](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md:32>) [APX:106–107](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md:106>)

**独立数学检查。** 对可任意交换、不会改变后续分布的两个独立过滤器 i、j，测试成本为 c，拒绝概率为 p；i 在前的期望成本是 `c_i+(1-p_i)c_j`，j 在前是 `c_j+(1-p_j)c_i`。i 在前更好当且仅当 `c_i p_j ≤ c_j p_i`。例如成本 1、拒绝率 0.001 的门，与成本 10、拒绝率 0.9 的门：便宜先测期望成本 10.99，较贵先测为 10.1。

**判断。** 即使在这个很简单的场景，也要看拒绝率，不能只看成本；真实 LBBD 还有前提依赖、条件概率、缓存和失败回传价值，问题更复杂。原文已有拒绝率、目标耦合和死因谱意识，应把这些也纳入门序比较。这个反例否定的是“纯成本排序普遍最优”的强读法，不证明旧管线某次具体排序必错，也不允许越过信息依赖硬顺序。

### 6.8 D7：把 cut 等同核，会漏掉更适合本题的反馈，也会误判优化职责

**原文。** 09-02 内环把常量假设化写成 cut 的全部性质来源；同日评审指出核、翻译后的约束和层间反馈不是同一对象，并提醒目标界反馈。[IL1:13–23](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md:13>) [REVIEW:274–340](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/reviews/2026-09-02-gpt-pro-inner-loop-review.md:274>)

**判断。** 原始核只是一组前提；上层真正加入的是证明适用的约束。网络供需不等式、已证容量下界、局部精确投影、构造见证和目标界都可能是更有用的信息。9 月走廊甚至特意说明其语义反馈不属于当时词汇表狭义的“cut”，尽管其功能正是向上排除候选。术语若把最强信息挡在讨论外，方法会被工具 API 牵着走。[COR:74–76](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:74>) [FLOWCUT:47–84](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:47>)

不过，“没有 optimality cut 就错”也不能一概而论：若外层枚举／搜索空矩形目标、内层严格判断固定目标可行性，足够强的 feasibility cuts 可以完成该结构；只有把成本／面积优化分给子问题时，才必须明说怎样回目标界。早期规格本就按固定 `(w,h)` 工作，不能用直接优化的义务错审它。[SP0:21–36](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md:21>) [REVIEW:322–340](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/reviews/2026-09-02-gpt-pro-inner-loop-review.md:322>)

### 6.9 D8：性能的局部证据被升级成架构结论，会反复把研究导向错误的修法

**原文。** 09-02 文本用两份 268 摆法、575 秒／30 毫秒推配口层“没有存在理由”；又从层次名义上的倒挂推分汇账同层。09-09 文字已撤回这些外推。[IL1:23–43](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md:23>) [IL4:69–71](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:69>) [Q:84–88](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md:84>)

**判断。** 两份摆法在同一层都被接受，只能说明这两次没有过滤价值，不能测出该摘要对后续路由的帮助。反过来，走廊某次语义反馈很快，也不能宣告其全厂必胜。应统一题面、域、目标和证据能力，分列建模、重建、子求解、证书、检查和后继成本，再比较最终 L/U 或完整候选进展。

“薄厚”仍值得用，但应作为可修正的测量问题，而不是凭“共享变量很多”“人类按地区做”直接得出的唯一分解。9 月完整过程说明已把 pose/port＋反馈、局部生产组和全基地流量等列为可组合的严肃候选。[CONNECT:132–167](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/notes/2026-09-08-connected-production-construction.md:132>)

### 6.10 对现行题可直接采用的最低方法合同

这不是新分层定案，而是由上述审计得到的最低要求：

1. **先写每个模型的用途和覆盖映射。** 压 U 的几何／流量模型必须接受每张达标布局的像；抬 L 的受限构造可丢布局，但失败不改全局 U。现行会议 3 已这样规定。[M:17–23](</home/zhuran24/zmd-research-fresh/求解器/会议成果/会议3/纪要.md:17>)
2. **接口同时说明决定与尚未决定的自由度。** 位置是否固定、口是否可改、路由是否可重选、平均率由谁承担、运行验证对哪些调试／顺序量化。只写“输入布局、输出 PASS/FAIL”不够。
3. **每条排除带齐前提。** 在固定图找到的 LP／最小割证书要提升到可变几何变量；未选候选、箱体、桥轴、真实自动接通和目标矩形不能从证明上下文消失。可变摆放网络的全候选做法可作局部范例，不能原样覆盖现行全部结构。[FLOWCUT:41–84](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:41>) [M:15–21](</home/zhuran24/zmd-research-fresh/求解器/会议成果/会议3/纪要.md:15>)
4. **同时允许三种修法竞争。** 提前编译便宜必要条件、增强反馈、局部共同决定。用有界实验决定下一步，而不要求先推出唯一层数。当前会议 3 也未找到同时广覆盖且解得动的 70×70 模型。[M:40–48](</home/zhuran24/zmd-research-fresh/求解器/会议成果/会议3/纪要.md:40>)
5. **把运行保证作为明确交付。** 静态流只过必要层；抬 L 还要给实际全通道、调试可达性及所有允许循环的达标保证。原题要求不因选择 LBBD 而降低。[T:2–15](</home/zhuran24/zmd-research-fresh/求解任务.txt:2>) [C:3–11](</home/zhuran24/zmd-research-fresh/求解约束.txt:3>)

本节 2—5 是本报告建议，不是历史作者已经实现的能力。现有史料证明了若干接口缺陷和局部修法；没有证明改用某套完整架构就能解出当前题目。

## 七、上一轮覆盖了什么，遗漏了什么

**上一轮并非只写了纲领，甚至也不是完全没有诊断 LBBD。** 《方法论诊断》冻结判断已有 LBBD 的补全量词；正文 3.5 批按规则定层与保留切口，3.6 批有限死因分类，3.7 举常量支持与非放松错误，3.8 指静态认证和真实运行之间缺口。[PREV:42–61](</home/zhuran24/zmd-research-fresh/求解器/老项目/方法论诊断.md:42>) [PREV:154–210](</home/zhuran24/zmd-research-fresh/求解器/老项目/方法论诊断.md:154>) 《目录》和第 01 份阅读报告也已给出方法出生、三层职责和走廊线索。[DIR:43–71](</home/zhuran24/zmd-research-fresh/求解器/老项目/目录.md:43>) [READING:34–38](</home/zhuran24/zmd-research-fresh/求解器/老项目/阅读/01-01-方法论纲领与LBBD入口.md:34>) [READING:373–377](</home/zhuran24/zmd-research-fresh/求解器/老项目/阅读/01-01-方法论纲领与LBBD入口.md:373>)

真正缺的是以 **“LBBD 怎么设计和使用”作为中心对象** 的组织，而不是零星术语或文件缺失：

| 本次补齐的内容 | 上一轮相应边界 |
|---|---|
| specs/10 各版逐次对照：理想 LP／两类割→family 更新→证明阶梯→flow 诊断；区分仅换行版本和语义变化 | 上一轮主要读后期规格、汇总设计／实现差异，没有给同名文件的完整版本序列。[DIR:47](</home/zhuran24/zmd-research-fresh/求解器/老项目/目录.md:47>) |
| 原始 07-16—17 用户消息的直接核对 | 第 01 份报告明确只读考古／原话锚点，没有另核原始会话。此次选择性补抽 29,405,781 字节 JSONL，并核 8 条消息。[READING:36–38](</home/zhuran24/zmd-research-fresh/求解器/老项目/阅读/01-01-方法论纲领与LBBD入口.md:36>) [RAW:3640–3657](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:3640>) [RAW:4040–4077](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:4040>) [RAW:5111–5145](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl:5111>) |
| 主张→理由→实测→修正的逐条对照，尤其层数不是独立参数、反馈不止核、按成本排序的反例 | 上一轮 3.5、3.6 已诊断部分原则，但没有逐项重建整套操作方法。[PREV:154–180](</home/zhuran24/zmd-research-fresh/求解器/老项目/方法论诊断.md:154>) |
| E118→E119→E120→E121 的完整转向：弱割→审查→联合→同域因子化 | 上一轮停滞表重点到 E118/E119，没有接上 E120/E121 的反向限制，容易只留下“该合层”的半边印象。[PREV:247](</home/zhuran24/zmd-research-fresh/求解器/老项目/方法论诊断.md:247>) |
| 走廊 2 提案／200 次、旁路 234／54 的完整条件与定理，及可变摆放网络一次整厂回送 | 第 01 份报告明确只得入口摘要、没有完整 README／枚举表与检查器源码；本次直接读完整实验说明与回割推导。[READING:373–377](</home/zhuran24/zmd-research-fresh/求解器/老项目/阅读/01-01-方法论纲领与LBBD入口.md:373>) [COR:63–98](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md:63>) [BYPASS:28–96](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_bypass_transfer_20260905/README.md:28>) [FLOWCUT:47–84](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md:47>) |
| 7 月 F5 翻译与 8 月 F5 shadow-only 的状态分离；9 月末版页面与其历史快照分开 | 不再把同一树里的多个“当前”拼成一个最终运行事实。[SP5:60–72](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md:60>) [CURRENT:1897–1901](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/CURRENT.md:1897>) [Q0:1–13](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/questions/how-should-the-solver-be-divided.md.txt:1>) [Q:1–30](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md:1>) |

**还需纠正上一轮阅读台账的一处继承问题。** 第 01 份报告第 412 行沿用“层数／切口在册二十天无主动复审”的初始考古说法；但考古终卷明确收窄：只能说 v2.1 未显式规定工况迁移触发器，不能说没有其他复审信号，08-03 也有门内切口重审。上一轮《方法论诊断》后文已经提醒这一点。本报告采纳收窄版，不再把“完全没有重新思考架构”当事实。[READING:412](</home/zhuran24/zmd-research-fresh/求解器/老项目/阅读/01-01-方法论纲领与LBBD入口.md:412>) [DOS:411–434](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/INNER_LOOP_MISMATCH_DOSSIER.md:411>) [PREV:252–258](</home/zhuran24/zmd-research-fresh/求解器/老项目/方法论诊断.md:252>)

**综合判词。** 老 LBBD 方法论有真实的正确性积累，也有具体的局部有效反馈；它可能把工作带进死路的部分，是把规则归属当架构设计、把稀少强割的存在当一般保证、默认保留已有切口，以及在不完整的模型合同上讨论求解效率。后来材料已经修正其中不少问题，但截止所读 09-09 文书，完整自动过程和全厂运行见证仍未完成。材料没有建立“方法论导致停滞的唯一原因”，也没有建立“换掉 LBBD 就可解决”。[IL4:5–13](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md:5>) [Q:22–28](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md:22>) [CONNECT:102–120](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/notes/2026-09-08-connected-production-construction.md:102>)


## 八、来源、版本身份与核查边界

### 8.1 本次查阅范围

以既有 `extracted-final.tsv`、`methodology-index.tsv` 和 `listing.txt` 定位。先对指定入口、specs/11 及 inner_loop_archaeology 系列按哈希去重，得到 471 个路径、58 份不同字节内容；再沿正文引用追到后继历史快照、实验与状态材料。这个数描述首轮定位集合，不代表全包只有这些方法文件，也不代表 58 份全部逐字通读。主张与定量结论只取正文实际回读的区段。

此外，对既有方法索引中的 135 份不同内容作薄厚、cut 方法论、分层归属词组复扫，回读短版隔离副本和重构收据；这些补查没有产生另一个已证全厂架构。

重点补查了同名的 specs/10、29 号卡的保存版本、两套 zmd-method 长版及短版隔离副本、五份不同内容的 INNER_LOOP（含历史保存稿）、架构问题页的前后两版。后继原路径与内容身份列在下表。目录 mtime 只用于定位先后，正文／消息日期优先；没有把复制时间当思想出生日期，也没有用归档中的 CURRENT 标签替代版本审计。

本次只从压缩包补抽一份原始会话，存于 `lbbd-method-seat-a/raw/`，其余正文复用既有抽取。原始消息按 JSONL 物理行号定位，只回读所列用户消息，不读取或引用模型内部推理。没有整包解压，没有运行旧求解器、证明检查器或 git。报告不对旧认证状态作运行级复验。

补抽件：[5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl>)；29,405,781 字节；SHA-256 `7104f965a95aa3499d63db8ff683243c54e03166e24c34d184ee094f7dbbf68f`。与转录清单记录大小一致。读取的物理行为 3640、3644、3657、4040、4077、5111、5132、5145；对应 UTC 时间和可见正文保存在外置盘 [birth-excerpts.json](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/birth-excerpts.json>)。

### 8.2 原文路径和内容身份

正文引用 `ID:行号` 的链接直接指向这一行；行号范围写在链接文字里。下表保存完整原路径和 SHA-256，避免把同名副本混用。对 `docs/` 下材料，去掉 `/mnt/wd_external/zmd-old-extract/docs/` 前缀就是 tar 内原路径；RAW 去掉本次 `raw/` 前缀后同理。现行输入和上一轮报告列其仓库绝对路径。

| ID | 原文完整路径 | SHA-256 |
|---|---|---|
| SP0 | [zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md>) | `082011e1cfd488d79a4d3a5f5be920dfd88dec8c098f8c51a4cfc94149338cdc` |
| SP1 | [zmd-all/03-大型归档/E-codex-old/zmd_transfer_20260605_slim_20260606_0035/zmd/specs/10_benders_decomposition_and_cut_design.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-codex-old/zmd_transfer_20260605_slim_20260606_0035/zmd/specs/10_benders_decomposition_and_cut_design.md>) | `7bf39dcd227f646ed67eaed5ea361727d9c48669a72174f027490fd99b333654` |
| SP2 | [zmd-all/01-项目仓库与工作树/C-codex-pj/zmd_pj/specs/10_benders_decomposition_and_cut_design.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-codex-pj/zmd_pj/specs/10_benders_decomposition_and_cut_design.md>) | `ab8dbdd858ebb9bc417fd0619cf032fdf732728be48fd886a3335a2b8e612e40` |
| SP3 | [zmd-all/01-项目仓库与工作树/C-claude-pj/zmd-pj/specs/10_benders_decomposition_and_cut_design.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd-pj/specs/10_benders_decomposition_and_cut_design.md>) | `14f8a48ea9f7c9145b4d0c2f4431a80c75b998e59bfbab336586769014c23088` |
| SP4 | [zmd-all/03-大型归档/E-zmd-codex-autonomy-20260801/zmd-pj-codex/.claude/worktrees/agent-abbb35e6fe0946fe6/specs/10_benders_decomposition_and_cut_design.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-zmd-codex-autonomy-20260801/zmd-pj-codex/.claude/worktrees/agent-abbb35e6fe0946fe6/specs/10_benders_decomposition_and_cut_design.md>) | `c6ddd590e692fbf27eb370f31b7948857001cf6e37b61580602b78bbae3ff278` |
| SP5 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md>) | `b72c424459005055b53c0381af81abbbac93b398d235c6a831bdde99fbc6c5d9` |
| CARD | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md>) | `ea4d67e92e01f40c58ae00528b97b8c4ef52cb55ae55c082f67ea49c5133ecbf` |
| ZMD0 | [zmd-all/05-Codex清理备份/2026-09-19-devspace-worktrees/zmd-pj-aa6a19af/.claude/skills/zmd-method/SKILL.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/05-Codex清理备份/2026-09-19-devspace-worktrees/zmd-pj-aa6a19af/.claude/skills/zmd-method/SKILL.md>) | `bcf57ae014248610a2ee3372e97ae5a51fb5ca462cf44775b0a9b4ca8ad6a2dd` |
| ZMD1 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md>) | `3afed7cc6bb2f3f1fa8cb94ea0929541f5bb539070b159912cd202d2620ec6f6` |
| IL0 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next copy/INNER_LOOP.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next copy/INNER_LOOP.md>) | `99662f93dc4239871f28121d3685a5ff9b888afa476cc9e29194fe780e2aa576` |
| IL1 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md>) | `563d053f6960ca0f949dea6a305c8a0d8ee15461a30ed1ad3204374a35d25581` |
| IL4 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md>) | `15d682662c30979b3d8c1f6092578c1a003a746c5ff02340e9e285b3c4714bed` |
| Q | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md>) | `21825dc06ed8e0ebf3ebf0e6db844ec8d30aa27da51122f26c6572460e6f6b21` |
| MO | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/METHODOLOGY_ORIGIN.md>) | `452dee631cdba0c37410159576bc6633c2d760c205d696be219d5edbfd88092e` |
| DOS | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/INNER_LOOP_MISMATCH_DOSSIER.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/INNER_LOOP_MISMATCH_DOSSIER.md>) | `e218043379a4fd920a82e205fedde8cc1e473572227e735b3354fdcfe99f07aa` |
| RM1 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_5bc5dd3_v1.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_5bc5dd3_v1.md>) | `06633f4a7e3eb89313d0e5018154d26221f52047bf8f9c9a67d9c7feb816723d` |
| RM2 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_759263a_v2.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_759263a_v2.md>) | `f15c90fe11751b6ce41f41f95878b029449b97276b73a8d55613e88ceca86b6d` |
| RM21 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_d1a3b04_v21.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/roadmap_d1a3b04_v21.md>) | `b0355115edd2bf549208717efeee3c14393c70bd1e8d1354423aa886c8d5d16d` |
| RM22 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v22_roadmap.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v22_roadmap.md>) | `7e23b365d691086e8c12c2e460a54c333cf79389b46ff28c27c0ac9bebe89dc3` |
| RM23 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v23_roadmap.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/v23_roadmap.md>) | `3c3940a6a49508d7eb1809370528eaf6e132d71ca2d4e839847467e4224df5d5` |
| SK0 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/310afe8.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/310afe8.md>) | `4731f6b489303db07d0427b65a8a90cdbb2344ce4f8f49f2584f2db7490c3b8b` |
| SK1 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/33e78bd.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/33e78bd.md>) | `3dc220827c27dc9a7c7a3dbd9e920735f884a07d4bd5b17ebdde910548e0feb2` |
| SK2 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/a9e5049.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/a9e5049.md>) | `3c632a968bc80857d2122d22518eedb15a8060684dc6687a045c619d6d7b8cc8` |
| PIPE | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/11_pipeline_orchestration.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/11_pipeline_orchestration.md>) | `53a0608b16fd62cb8fc162dcda946695d00d8ae35bce24b40e40e3604ec785b7` |
| IL2 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-08-assumptions-and-judgement/INNER_LOOP.md.txt](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-08-assumptions-and-judgement/INNER_LOOP.md.txt>) | `693903c1f32f52a38127e885a298baa00613ce950032fb4a552d753a2b0cb397` |
| IL3 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/INNER_LOOP.md.txt](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/INNER_LOOP.md.txt>) | `2a6511e2c99b398e4f8de2471efc29193738fac0eb0ba3f594d15e09c8bf8ac7` |
| DIV | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/DIVISION.md>) | `75854ec256eb2afdb84604b5ce51833ac75def490a56f9a271ff2e128a1cf687` |
| APX | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/research/methodology_compilation_20260814/APX_E_pipeline_methodology.snapshot.md>) | `8088f8c19ffa3b28d9c1b164b087072c70d1e85101e20ea693c8108dbafd98fb` |
| BOARD | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/30_research_charter.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/30_research_charter.md>) | `fdbb29aaacba4ce46a8a7844c71d1c2b3b5e0d46f9bce8d273f545fb81bbc22d` |
| CHARTER | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/research-charter/SKILL.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/research-charter/SKILL.md>) | `43da472c55d282a9a7ad5bc1c827087e325b0cc2f44b7cc522a5542df0e310ec` |
| FOUND | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/02_mathematical_foundations.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/02_mathematical_foundations.md>) | `9ed3fcfa639383ba99bc4bef6000302db211b91c28cafa6c505448d5c41e3899` |
| CURRENT | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/CURRENT.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/CURRENT.md>) | `5fdbf1c125a44658de9ccf63307ee25b3ad4099fc7895d50f9dec8db9aebd44e` |
| COR | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_port_feedback_20260905/README.md>) | `ff90e7bf3d8d13f8d6d031cc83b8e4986d3fc233642210fc4cbce6a393835518` |
| BYPASS | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_bypass_transfer_20260905/README.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/corridor_bypass_transfer_20260905/README.md>) | `d0910558b822ff3b66598ffd8ea777358915e6e4a67c1975cef4a5e6fab9288b` |
| RATE | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/routing_rate_contract_20260905/README.md>) | `583aeb060f48a5d7a94f29b316d3e61285120ddcaf40df055f25ffd276dc1100` |
| FLOWCUT | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/spikes/full_base_candidate_20260905/cut-transfer-review.md>) | `30bc2e7c41886afc58da92f3931a3c3eac70e869cb30ef3093627e6eee0120a0` |
| CONNECT | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/notes/2026-09-08-connected-production-construction.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/notes/2026-09-08-connected-production-construction.md>) | `9cb940ef2c3c38d3f3380126dc75842137bdcfa1425b729b547fbcb55946e5a9` |
| REVIEW | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/reviews/2026-09-02-gpt-pro-inner-loop-review.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/reviews/2026-09-02-gpt-pro-inner-loop-review.md>) | `b060883242aa7fe55901a2ad6b4d4538842894637f29283ef166448b599c6da9` |
| A1 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/where-a1-jams.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/where-a1-jams.md>) | `bb25e26666dfaf069e850ef5d20d918b5fe8db5b4a50eae9923d8f081c48b4b6` |
| M5 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/m5_revalidation_20260803/NOTES.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/m5_revalidation_20260803/NOTES.md>) | `54a3d8fae5e0bce2bcbbbdeb8f8bf1cf2eb131ec709a7ed8c186d000239c62e1` |
| E118 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E118_solver_diverse_local_front_benders/RESULT.txt](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E118_solver_diverse_local_front_benders/RESULT.txt>) | `55e56c60f949a54ff5e1065db3d734e2b347102e36d855c875ae4fb6eed194cd` |
| E119 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E119_local_front_cut_family_saturation_audit/RESULT.txt](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E119_local_front_cut_family_saturation_audit/RESULT.txt>) | `a0dae6e343a381c1b87166aa6686c8245d82dd572fe716f7633a3570ea0b0c49` |
| E120 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E120_integrated_local_option_master/RESULT.txt](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E120_integrated_local_option_master/RESULT.txt>) | `c9dc1cdedad9b09286dd8c23d42af0bc2837c22e86cf94d76166ea10c5cf23a5` |
| E121 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research/research_lab/campaigns/zero_condition/experiments/E121_occupancy_factored_local_option_master/RESULT.txt>) | `1bedb7ec3cc76797e7ebd89579e3971edd3a3dba7e9901e3e3bde3b6ae56714b` |
| RAW | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/raw/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/outer_loop_archaeology_20260822/recheck_scratch/retirement_sessions/.claude/projects/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76.jsonl>) | `7104f965a95aa3499d63db8ff683243c54e03166e24c34d184ee094f7dbbf68f` |
| R | [/home/zhuran24/zmd-research-fresh/《明日方舟：终末地》游戏规则.txt](</home/zhuran24/zmd-research-fresh/《明日方舟：终末地》游戏规则.txt>) | `6e64e3903a65536c530b363c9f3aef8c1bb2a1c1193e866799125dd047159924` |
| T | [/home/zhuran24/zmd-research-fresh/求解任务.txt](</home/zhuran24/zmd-research-fresh/求解任务.txt>) | `1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac` |
| C | [/home/zhuran24/zmd-research-fresh/求解约束.txt](</home/zhuran24/zmd-research-fresh/求解约束.txt>) | `0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f` |
| M | [/home/zhuran24/zmd-research-fresh/求解器/会议成果/会议3/纪要.md](</home/zhuran24/zmd-research-fresh/求解器/会议成果/会议3/纪要.md>) | `d6c92a966fd9b295d5ed9dab4fed9e63710b76206c13107a6897d86f42db9228` |
| PREV | [/home/zhuran24/zmd-research-fresh/求解器/老项目/方法论诊断.md](</home/zhuran24/zmd-research-fresh/求解器/老项目/方法论诊断.md>) | `8fc23137a542981aa733c7e87c5c1638a1b5b1df97c102f274ff72b0cfcac0bb` |
| READING | [/home/zhuran24/zmd-research-fresh/求解器/老项目/阅读/01-01-方法论纲领与LBBD入口.md](</home/zhuran24/zmd-research-fresh/求解器/老项目/阅读/01-01-方法论纲领与LBBD入口.md>) | `99fa6dd3fffc21fbe252d5f84ffafd70f6a133e2383d1c1577ad8128ce48aca6` |
| DIR | [/home/zhuran24/zmd-research-fresh/求解器/老项目/目录.md](</home/zhuran24/zmd-research-fresh/求解器/老项目/目录.md>) | `18c8c8ed35c9b907fb49d0d4899723f9852edc492c18a554e1e949c9cbf1cb69` |
| Q0 | [zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/questions/how-should-the-solver-be-divided.md.txt](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/questions/how-should-the-solver-be-divided.md.txt>) | `f81f5b8758b599133df3842d46815243eab925ccfc9cf0b12c33a7d35288af58` |
| LIST | [/mnt/wd_external/zmd-old-extract/listing.txt](</mnt/wd_external/zmd-old-extract/listing.txt>) | `4c1d301a8b1fb4d5518d9cd7f7ea154c3a366edb38d7d1fc63def94207b302a6` |
| ZMDSHORT | [zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/global_shortver_quarantine/zmd-method.SKILL.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/global_shortver_quarantine/zmd-method.SKILL.md>) | `34b12718589adc46554dc2ca90a66d2cd1bb78a56610b41aabc06d8b781598a2` |
| ZMDRESTRUCT | [zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/EXEC_METHOD_RESTRUCTURE.md](</mnt/wd_external/zmd-old-extract/docs/zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/EXEC_METHOD_RESTRUCTURE.md>) | `5d50c4e44be7e60970222a5d506671455508e65d8655f08eb591d987a82ba520` |

### 8.3 同名版本的字节差异

specs/10 共发现 8 种字节内容，归并为 6 种正文内容；6 月 4 日更新稿的 SP1、SP1b、SP1c 正文相同，分别为混合换行、LF、CRLF，不算三次方法变化。29 号卡的正文成稿与其历史保存的 SK0、SK1、SK2 区分见第三节；不能把所有载体都当成一种摘要。IL1 与 `history/before-2026-09-04/INNER_LOOP.md.txt` 字节相同，后者是保存副本。其余各版的实际差异已按时点列在第三节。

| 版本 | 字节数 | SHA-256 | 身份 |
|---|---:|---|---|
| [SP0](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd/specs/10_benders_decomposition_and_cut_design.md>) | 4,837 | `082011e1cfd488d79a4d3a5f5be920dfd88dec8c098f8c51a4cfc94149338cdc` | 语义变化见第三节 |
| [SP1](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-codex-old/zmd_transfer_20260605_slim_20260606_0035/zmd/specs/10_benders_decomposition_and_cut_design.md>) | 6,096 | `7bf39dcd227f646ed67eaed5ea361727d9c48669a72174f027490fd99b333654` | 语义变化见第三节 |
| [SP1b](</mnt/wd_external/zmd-old-extract/docs/zmd-all/04-审查交接与传输包/E-codex-upload/zmd-20260606-203821/zmd/specs/10_benders_decomposition_and_cut_design.md>) | 6,009 | `dc8a444f260b15346929cbaeaeff97ca8037c6df7d5856b5fea533a778670440` | 仅换行不同，正文同 SP1 |
| [SP1c](</mnt/wd_external/zmd-old-extract/docs/zmd-all/04-审查交接与传输包/E-c-bridge-gh-pull/zmd_full_20260606_231614/specs/10_benders_decomposition_and_cut_design.md>) | 6,097 | `55581b1e4bcdc5b3fca1997b5522169245bff0b95256ffa9d6a4207e0a23860a` | 仅换行不同，正文同 SP1 |
| [SP2](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-codex-pj/zmd_pj/specs/10_benders_decomposition_and_cut_design.md>) | 13,143 | `ab8dbdd858ebb9bc417fd0619cf032fdf732728be48fd886a3335a2b8e612e40` | 语义变化见第三节 |
| [SP3](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-claude-pj/zmd-pj/specs/10_benders_decomposition_and_cut_design.md>) | 11,797 | `14f8a48ea9f7c9145b4d0c2f4431a80c75b998e59bfbab336586769014c23088` | 语义变化见第三节 |
| [SP4](</mnt/wd_external/zmd-old-extract/docs/zmd-all/03-大型归档/E-zmd-codex-autonomy-20260801/zmd-pj-codex/.claude/worktrees/agent-abbb35e6fe0946fe6/specs/10_benders_decomposition_and_cut_design.md>) | 12,308 | `c6ddd590e692fbf27eb370f31b7948857001cf6e37b61580602b78bbae3ff278` | 语义变化见第三节 |
| [SP5](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/specs/10_benders_decomposition_and_cut_design.md>) | 12,894 | `b72c424459005055b53c0381af81abbbac93b398d235c6a831bdde99fbc6c5d9` | 语义变化见第三节 |
| [SK0](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/310afe8.md>) | 4,402 | `4731f6b489303db07d0427b65a8a90cdbb2344ce4f8f49f2584f2db7490c3b8b` | 语义变化见第三节 |
| [SK1](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/33e78bd.md>) | 4,392 | `3dc220827c27dc9a7c7a3dbd9e920735f884a07d4bd5b17ebdde910548e0feb2` | 语义变化见第三节 |
| [SK2](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.artifacts/inner_loop_archaeology_20260823/scratch/skill_versions/a9e5049.md>) | 15,693 | `3c632a968bc80857d2122d22518eedb15a8060684dc6687a045c619d6d7b8cc8` | 语义变化见第三节 |
| [CARD](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/docs/项目说明/29_solving_methodology_skill.md>) | 16,015 | `ea4d67e92e01f40c58ae00528b97b8c4ef52cb55ae55c082f67ea49c5133ecbf` | 语义变化见第三节 |
| [ZMD0](</mnt/wd_external/zmd-old-extract/docs/zmd-all/05-Codex清理备份/2026-09-19-devspace-worktrees/zmd-pj-aa6a19af/.claude/skills/zmd-method/SKILL.md>) | 17,924 | `bcf57ae014248610a2ee3372e97ae5a51fb5ca462cf44775b0a9b4ca8ad6a2dd` | 语义变化见第三节 |
| [ZMDSHORT](</mnt/wd_external/zmd-old-extract/docs/zmd-all/02-git备份与快照/E-zmd_backups/zmd-pj-ops-20260830/evidence_vault/skills_round2_20260828/global_shortver_quarantine/zmd-method.SKILL.md>) | 5,579 | `34b12718589adc46554dc2ca90a66d2cd1bb78a56610b41aabc06d8b781598a2` | 语义变化见第三节 |
| [ZMD1](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-pj/.agents/skills/zmd-method/SKILL.md>) | 13,933 | `3afed7cc6bb2f3f1fa8cb94ea0929541f5bb539070b159912cd202d2620ec6f6` | 语义变化见第三节 |
| [IL0](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next copy/INNER_LOOP.md>) | 9,051 | `99662f93dc4239871f28121d3685a5ff9b888afa476cc9e29194fe780e2aa576` | 语义变化见第三节 |
| [IL1](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next/INNER_LOOP.md>) | 9,097 | `563d053f6960ca0f949dea6a305c8a0d8ee15461a30ed1ad3204374a35d25581` | 语义变化见第三节 |
| [IL2](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-08-assumptions-and-judgement/INNER_LOOP.md.txt>) | 9,628 | `693903c1f32f52a38127e885a298baa00613ce950032fb4a552d753a2b0cb397` | 语义变化见第三节 |
| [IL3](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/INNER_LOOP.md.txt>) | 9,919 | `2a6511e2c99b398e4f8de2471efc29193738fac0eb0ba3f594d15e09c8bf8ac7` | 语义变化见第三节 |
| [IL4](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/INNER_LOOP.md>) | 10,439 | `15d682662c30979b3d8c1f6092578c1a003a746c5ff02340e9e285b3c4714bed` | 语义变化见第三节 |
| [Q0](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/history/2026-09-09-architecture-entry-repair/questions/how-should-the-solver-be-divided.md.txt>) | 17,571 | `f81f5b8758b599133df3842d46815243eab925ccfc9cf0b12c33a7d35288af58` | 语义变化见第三节 |
| [Q](</mnt/wd_external/zmd-old-extract/docs/zmd-all/01-项目仓库与工作树/C-zmd-projects/zmd-research-next-docs/questions/how-should-the-solver-be-divided.md>) | 18,096 | `21825dc06ed8e0ebf3ebf0e6db844ec8d30aa27da51122f26c6572460e6f6b21` | 语义变化见第三节 |

首轮全路径去重映射：[source-groups.json](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/source-groups.json>)；其 listing 时间与行号：[source-times.json](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/source-times.json>)；本报告逐项来源身份：[source-manifest.json](</mnt/wd_external/zmd-old-extract/lbbd-method-seat-a/source-manifest.json>)。这些是查核附件，方法、实验、诊断全文均在本报告。

### 8.4 结论的强度

- **直接核到：** 方法原文的表述、已保存版本的差异、原始出生消息，以及原报告记录的实验结果和撤回状态。
- **本报告的判断：** 分组与可表达性不能混同；共享变量不是一律合层的理由；成本排序要考虑拒绝率；核／割提升须证明量词；强割族与高效率不是有限代码分支自动附送的性质。这些判断在第六节逐条给出了推理或具体反例。
- **没有核到：** 一个能解现行全题的完整 LBBD 系统；任何切法在全厂上稳定优于另一个的对照；“方法论是历史停滞唯一原因”的因果证明；修改方法后必然解出的保证。

本报告将现行正式约束作为输入接受，没有逐条重新证明其中的派生结论。现行三份正式文件与会议 3 的字节在报告完成检查时仍与第一节记录一致。第一节冻结区段 SHA-256 再核仍为 `faaa2beb54e1d8a608e066a443daffa0dfb66c6cb0912d8a921cea4dc38eb526`。它保留了阅读前判断，也保留了启动时记忆索引意外显示一句旧摘要的披露；后文没有倒改这一先验记录。
