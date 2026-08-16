# 规则系统重设计线批 0 自量凭据

> 凭据版本：v1.1，2026-08-15（批尾放行补记）
>
> 模板：`EIGHT_STEP_TEMPLATE_V1.md`
>
> 当前结论：`FINAL_PASS_WITH_OPEN_DEBTS`。五件主交付物、三条定向验收、本凭据与批尾共享文档三检均已完成；owner 已放行，三检全绿，未产生共享生成页差异。开放欠账与“需要你拍板的八件”仍按各自状态保留，不因本批通过而关闭。
>
> 权威边界：本凭据是批 0 的自量与执行留痕，不是 owner 对“需要你拍板的八件”的逐项批准，不改 §0b，不建立 `rules/derived/`，不授权新增代码埋点，不执行 freeze-ritual。

## A. 批头

| 字段 | 本批填写 |
|---|---|
| 批 id / 标题 | `RULE-SYSTEM-REDESIGN-BATCH0-20260815` / 工作规则上线 |
| 日期 / 分支 / 起始基线 | 2026-08-15 / `main` / 开工时工作区已有并行线提交，批 0 首个提交父链包含 `fd276c2` |
| 批尾放行时共享 HEAD | `8375484`（含另一线最新提交）；批 0 三笔既有提交为 `80b5364` / `7a4df51` / `5b93084` |
| 变更 pathspec | 仅 `docs/research/rule_system_redesign_20260807/batch0_20260815/*.md`，未触及 `rules/`、`src/`、`scripts/`、`data/` |
| 一句话目标 | 把三条消费侧闸、八步模板、席位清单、外发登记和开放欠账做成可执行文书，并用本批与三份历史文书实测它们 |
| Plan / 立论 | 本对话执行席，按权威批表拆件并落文 |
| refute | 同一执行席的第二遍反向审查，加历史随机回测；不是人员独立席，故不把本凭据升级成科学结论的独立核签 |
| 拒真 | 以“合法背景引用、合法检索使用、合法研究级参数使用”三类正例检查三闸是否过严；默认分席推荐仍待 owner 裁 |
| 收批 | 本对话执行席完成批 0 自量；owner 已放行，批尾三检全绿，最终 verdict 见本文件末尾 |
| owner 已给事实题答案 | 允许本线立项并按缺省批序先做批 0；立项不等于八件逐项批准 |
| 本批明确不做 | 不改既有权威正文；不建 `rules/derived/`；不改代码和数据；不跑 freeze-ritual；不跑全树冻结门禁；不提前运行批尾三检 |
| 本批证据等级上限 | docs 侧工作规则与历史证据；代码现态只读核验；不产生新的游戏事实或 certified 数学结论 |

### 八件待裁总声明

`OWNER_DECISION_SUMMARY.md`“需要你拍板的八件”全部保持待 owner 逐项拍板。本批直接相交项如下：

- 第 4 件 `rules/derived/`：未批准，目录未创建。
- 第 5 件 checker 进 CI 与转硬门时点：未批准，本批只有人工文书闸。
- 第 6 件 §0b 三处改动：模板中均标“待 owner 认可”，未修改 §0b。
- 第 7 件新增第五卡点与埋点：未批准，仅建立 `OD-B0-INST-01` 欠账。
- 第 8 件拒真席排法：按设计默认推荐写入席位矩阵，但显式标“待 owner 裁”。

## 第 0 步：批型判定与档案检索

### 0.1 七条件逐条判定

| 条件 | 触发 | 理由 | 证据坐标 |
|---|---|---|---|
| ¹ 引用分类标签或定量参数 | 是 | 三闸引用 `reachability`、`UNREVIEWED`、`candidates`、批次文书权威等级；两张台账含包 sha、call site、日期与状态 | 五件主文书 |
| ² 新增或保留限制 | 是 | G1/G2/G3 是消费限制，且开放欠账给出阻断范围 | `CONSUMPTION_GATES.md`、`OPEN_DEBT_LEDGER.md` |
| ³ 影响模型可行集 | 否 | 本批只新增 docs 文书，不改任何模型、候选池、guard 或 solver 输入 | `git status -- rules src scripts data` 无本批 tracked 修改 |
| ⁴ 修改冻结参数、配方、目标量或实例集 | 否 | 所有值仅登记现有历史字节与只读现态 | 外发台账与开放欠账台账 |
| ⁵ 出现只有 owner 能定的残余 | 是，但本批不新上桌 | 八件待裁继续开放；拒真席、§0b、埋点、derived 目录均不得擅裁 | `OWNER_DECISION_SUMMARY.md` |
| ⁶ 触及承重代码语义面或工件字节 | 否于写入，属于只读核验 | C-08 四 call site 只读重定位并跑现有哨兵；本批不改代码 | `OPEN_DEBT_LEDGER.md` §3 |
| ⁷ 触及 fail-closed、过滤、剥落或降级路径 | 是于治理语义 | 三闸规定何时 BLOCK；开放欠账规定何时降级 conditional；无埋点必须如实登记 | 三闸与 `OD-B0-INST-01` |

### 0.2 批型与触发步骤

本批是复合型 docs 治理批：

1. 以“guard/限制/准入策略批”处理三条消费侧闸，因此步骤 1、2、5、6 必跑。
2. 以“工程/基建批，无科学断言”处理模板、席位表和两张账本的载体建立，因此步骤 0、5 必跑，步骤 2/6 因条件 ⁷ 触发。
3. 批表验收明确要求一份完整八步凭据，故本凭据把步骤 0 至 7 全部执行；对不适用项写明理由，不用空白冒充完成。

fail-closed 兜底：虽然没有模型写入，三闸会改变“哪些文书能被消费”。因此不能按普通排版批跳过可达性、双向保真与历史回测。

### 0.3 四路档案检索

| 路 | 检索范围 | 结论 | 对本批动作 |
|---|---|---|---|
| 记忆层 | `.artifacts/memsys_meeting_20260808/` 的历史快照与 `DOC_MEMORY_FIXLIST_20260806.md` | 找到 C-26 收据转述误用的订正前承重句 | G2 增加 `LEGACY_GENERATED_EQUIVALENT` 历史兼容判读 |
| roadmap 台账 | `FINAL_DESIGN.md` §3.8、§4、§6、文末欠账；`OWNER_DECISION_SUMMARY.md` | 批 0 五件、三验收、八件待裁边界明确 | 作为范围与红线权威 |
| `docs/research/` 目录 | canonical 20260807/08、P2.0、U-01、规则重设计 dossier | 找到 C-08、C-15、C-17、C-26 与 :769 的第一手坐标 | 用于首批台账与回测总体 |
| 裁决索引/外审归档 | `.artifacts/gpt_pro_review_batch_20260807/` fen1 至 fen5 的 prompt、reply、adjudication | 五个历史 GPT Pro 审查包均有回件和本地核签；fen6 是盲推导，不属审查包 | 外发台账首批登记 fen1 至 fen5，排除 fen6 |

### 0.4 canonical 新鲜度

| 检查 | 实测 | 结果 |
|---|---|---|
| 工作树 canonical SHA-256 | `c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0` | 记录 |
| `git show main:rules/canonical_rules.json` SHA-256 | 同为 `c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0` | PASS |
| `80b5364` 是否为当前 HEAD 祖先 | `git merge-base --is-ancestor ...` exit 0 | PASS |
| `7a4df51` 是否为当前 HEAD 祖先 | exit 0 | PASS |

### 0.5 refute 攻击面 ⓪

refute 判定：不能把本批仅归类为“无科学断言工程批”。三闸是治理 guard，会产生 BLOCK 与 conditional，必须按限制批补跑可达性和双向保真。已据此执行完整八步，而不是只做文件存在性检查。

## 第 1 步：参数账

### 1.1 标签行

| 标签 | 判据原文/执行化含义 | 一次算完的判断 | 结论 | 未声明前件 | refute 复核 |
|---|---|---|---|---|---|
| G1 | `NOT_ASSESSED` 或 conditional 且开放前件非空，不得承重 | 回读条款状态、开放前件与本文用途 | 危险消费历史可达，守卫成立 | 过渡期无结构字段时需人工等价判读 | 历史样本命中 2 次 |
| G2 | generated/UNREVIEWED/candidates 不得进前提集 | 检查路径/状态/候选身份和实际消费关系 | 危险消费历史可达，守卫成立 | 旧架构没有 `docs/generated/` 路径，需要历史等价类 | 首轮字面回测零命中，修闸后同样本命中 1 次 |
| G3 | 批次文书参数权威封顶，不得直接支撑 certified 放开 | 回读量的出处形态与动作强度 | 危险消费历史可达，守卫成立 | “批次文书”不等于“错误”，研究级使用仍需保留 | 历史样本命中 3 次 |

### 1.2 量子行

| 量 | 值 | 出处形态 | 权威等级 | 用途 | 指纹/版本 |
|---|---:|---|---|---|---|
| 主交付文件数 | 5 | 批表 + 文件系统实测 | 批 0 验收事实 | 验收 ① | 文件字节见下表 |
| 外发首批 id 数 | 5 | 外发台账 | 批次文书 | 验收 ① | FEN1 至 FEN5 |
| 开放欠账首批 id 数 | 8 | 开放欠账台账 | 批次文书 | 验收 ① | C08×4、埋点×1、canonical×2、chain×1 |
| G1/G2/G3 回测命中 | 2 / 1 / 3 | 人工语义重建 + hash/anchor 断言 | 批次实测 | 验收 ③ | 固定 seed `5861986475307631752` |
| C-08 定向哨兵 | 3 passed | pytest 现有测试 | 代码测试证据 | 台账状态校验 | 0.79s |
| canonical 当前 sha | `c3fc...42c0` | 冻结机器真源当前字节 | canonical | 新鲜度 | main 与 worktree 一致 |
| GPT Pro 历史包 SHA | 五个完整 SHA-256 | 归档 zip | 历史归档字节 | 外发登记 | `OUTBOUND_REVIEW_LEDGER.md` |
| 平台会话 id | `MISSING`×5 | MISSING | 未知 | 不参与结论 | 保留缺口，不猜造 |
| 上传字节与归档 zip 同一性 | `ARCHIVE_BYTES_ONLY` | MISSING 平台回执 | 归档级 | 不宣称上传逐字同一 | 五包一致保守标注 |

五件实测字节：

| 文件 | 字节数 |
|---|---:|
| `CONSUMPTION_GATES.md` | 6,180 |
| `EIGHT_STEP_TEMPLATE_V1.md` | 19,890 |
| `SEAT_CHECKLIST_V1.md` | 9,698 |
| `OUTBOUND_REVIEW_LEDGER.md` | 10,314 |
| `OPEN_DEBT_LEDGER.md` | 13,087 |

### 1.3 九本账逐行对表

本批不建立新的游戏数学结论，九本账用于检查三闸和历史样本是否把量的类型混掉。

| 账目 | 本批接触 | 结果 |
|---|---|---|
| 面积 | 否 | 没有用面积数字支撑本批结论 |
| 边界周长 | 否 | 历史样本中的 139/138/141 只作为 G1 例证，不晋升为本批结论 |
| 台数容纳 | 否 | 266 mandatory 仅在历史文书中出现，不参与本批验收 |
| 端口槽位 | 是，历史 C-17/C-08 | 只登记“6 槽、3 口、call site”，不把未冻结容量拿来放开代码 |
| 供电覆盖 | 否 | 不对 A8 作新判断 |
| 商品源汇 | 否 | 不对流向作新判断 |
| 整除 | 否 | 无新整除论证 |
| 模数 | 否 | 无新模数论证 |
| 入量 × 周期 vs 容量 | 是，作为历史病例 | 用于识别 G1/G3 与 :769 连锁重核，未把 §0b 改动写成已批准；该 §0b 接线仍待 owner 认可 |

### 1.4 MISSING 三级阶梯

| MISSING 量 | L1 仓内检索 | L2 模拟器 | L3 owner | 最终状态 | 处置 |
|---|---|---|---|---|---|
| fen1 至 fen5 平台会话 id | 归档只见仓内代号 | 不适用 | 不需要为批 0 追问 | MISSING | 台账写 MISSING，不猜造 |
| 上传字节与归档 zip 同一性 | 有归档 zip，无平台回执 | 不适用 | 不上桌 | `ARCHIVE_BYTES_ONLY` | 不声称逐字相同 |
| routing context strict-emptiness 完整作用域 | 代码和测试显示刻意排除 ghost marker | 需后续跨层 sentinel | 非 owner 事实题 | `OPEN_REVALIDATION` | `OD-B0-C08-03` |
| heuristic ghost-inclusive certified 语义 | 当前代码显示 ghost 未进 routing occupancy | 后续定向测试 | 非 owner 事实题 | OPEN | `OD-B0-C08-04` |
| 埋点授权 | docs 可列缺口，代码实现需第 7 件裁定 | 不适用 | 待 owner | `OPEN_AUTHORIZATION_PENDING` | `OD-B0-INST-01` |

refute 总复核：所有 MISSING 都保留为缺口或阻断，没有用另一份批次文书复述来伪造升级。

## 第 2 步：可达性尺子

### 2.1 三闸逐条六选一

| 限制 | 危险条件 | 判定 | 保证方 | 保守代价 | 摘除条件 |
|---|---|---|---|---|---|
| G1 | 条件/界未核条款被当承重前提 | 限制成立 | 历史反例 + 本限制自己 | 会阻止“先用后补”的快写法；允许明确背景引用 | 只有当上游 reachability 与开放前件在权威载体关闭时，单项不再触发 |
| G2 | 视图、未审条目、候选或历史等价摘要进入前提集 | 限制成立 | 历史 C-26 + 本限制自己 | 需要回读机器真源；合法检索记录仍允许 | 对象成为已审真源，或只作检索线索且不入推导 |
| G3 | 批次文书参数直接支撑 certified 放开/无条件证明 | 限制成立 | 历史 P2.0 审计 + 本限制自己 | 研究结论需降级或补 provenance | 参数进入 canonical/冻结真源且当前指纹匹配 |

三闸不是删除候选。本批没有删 guard，不触发删除三签或 freeze-ritual。

### 2.2 触发器

| 触发器 | 激活判据 | 本批观测 | 到期/动作 |
|---|---|---|---|
| G1 | 前提集中出现条件/待核条款 | 随机样本 2 命中 | 常驻人工过堂；机器化时另批 |
| G2 | 前提集中出现视图/未审/候选/历史等价摘要 | 初始字面规则 0 命中；修闸后 1 命中 | 修闸已完成并提交 `7a4df51` |
| G3 | 前提参数只在批次文书 | 随机样本 3 命中 | 常驻人工过堂 |
| C-08 routing context | strict-empty 结论仅凭该 context | 当前存在作用域不清风险 | 2026-08-22，`OD-B0-C08-03` |
| C-08 heuristic | `ghost_rect != None` 仍返回强 `CERTIFIED` | 当前代码面可达 | 2026-08-22，`OD-B0-C08-04` |
| 无埋点假零 | 文书写“从未触发/拒绝率 0”但无数据源 | 当前治理面存在 | 2026-08-29 先交设计清单，实施待 owner 第 7 件裁定 |

### 2.3 反向哨兵

- 合法背景引用必须能通过 G1。
- generated/receipt 只作检索线索并回读真源，必须能通过 G2。
- 批次参数用于研究假设、保守估算且明确权威上限，必须能通过 G3。
- 现有三条 C-08 哨兵：
  - `test_extract_occupied_cells_includes_ghost_cells`
  - `test_witness_pose_resolved_occupancy_includes_ghost`
  - `test_ghost_pick_marker_excluded_from_context_even_with_pool`

实测：`3 passed in 0.79s`。

## 第 3 步：前件卫生

### 3.1 七问

| 问 | 本批答案 |
|---|---|
| 自由度问 | 三闸不是数学等式。真正自由量是“对象实际用途、上游状态、参数出处形态”，均要求逐行登记，不能从文件名推断 |
| 约定问 | “历史等价类”只用于架构上线前回测，不扩成“所有 receipt 都非法”；这是明确作用域，不是假装自然定理 |
| 量词问 | “不得进入前提集”只量化承重消费，不禁止全文出现；“三闸各命中”指三份样本合集至少一次，不要求每份命中三闸 |
| 语境问 | certified 放开、研究假设、背景引用三种语境分开；G3 只阻止批次参数直接支撑强动作，不宣布批次参数为假 |
| 权威问 | owner 立项、canonical 字节、历史外审、批次设计、归档 zip 分层登记，没有互相冒充 |
| 使能问 | 三闸是消费使能条件，不是免责声明；文件头写“非权威”不能抵消实际承重 |
| 聚合问 | 验收计数只聚合唯一 id；SHA 和文件字节逐项记录；回测命中按语义事件计数，不把关键词次数当命中数 |

### 3.2 聚合操作扫描

| 工件/操作 | 聚合 | 隐含前件 | 处置 |
|---|---|---|---|
| 五文件存在性脚本 | `len(unique ids)` | id 正则必须唯一且稳定 | 同时列出完整 id，避免只有总数 |
| 回测命中 | 每闸 hit count | 一次命中必须有“前提锚点 + 消费/动作锚点” | Python 只做 hash/anchor 断言，语义由人工重建，不伪称全自动 checker |
| 包登记 | 五个 zip 汇总 | 归档字节不必等于平台上传字节 | 统一标 `ARCHIVE_BYTES_ONLY` |
| C-08 状态 | 四 call site 总账 | 同一历史欠账可在当前树分化 | 四处逐项记 CLOSED/OPEN/REVALIDATION，不写一个模糊总状态 |

### 3.3 被当常数的量

| 量 | 谁钉死 | 坐标 |
|---|---|---|
| 五件主交付路径 | `FINAL_DESIGN.md` 批 0 行 + 本批文件系统 | 本目录五文件 |
| 回测种子 | `sha256("7a4df51...:batch0-consumption-gates-backtest-v1")[:8]` | seed `5861986475307631752` |
| 三份样本字节 | SHA-256 | `5680...bbe1`、`8454...9e2`、`23ca...c7b` |
| C-08 当前符号位置 | 当前源码与现有测试 | 开放欠账台账 §3 |
| 到期日 | 本批临时责任席安排 | 2026-08-22 / 2026-08-29；不冒充 owner 优先级批准 |

### 3.4 六层覆盖

| 层 | 状态 | 说明 |
|---|---|---|
| 几何层 | 明确没审 | 本批不重判布局几何；只读 C-08 occupancy 语义 |
| 速率/计数算术层 | 审了，限历史病例 | 仅核对箱案/分流器数字是否作为前提被消费，不重证游戏算术 |
| 参数来源层 | 审了 | 外发 sha、canonical sha、批次文书/MISSING/归档身份逐项登记 |
| 语义锚点层 | 审了 | 三闸围绕消费语义、背景引用与 certified 动作区分 |
| 实现一致层 | 部分审 | C-08 三条现有测试通过；heuristic 与 routing-context 开放面未关闭 |
| 方向暴露层 | 审了 | 每闸同时检查合法使用正例；开放欠账明确阻断范围 |

## 第 4 步：owner 裁决包

本批不新建 owner 裁决包，理由如下：

1. 批 0 的范围、顺序和红线已经由 owner 给定。
2. C-08、外发登记、历史回测均可由仓内材料计算，不应上交 owner。
3. 与八件待裁相交的事项只登记状态，不偷渡裁决。

固定问题“这包里有没有本可以自己算的？”答案：没有包；仓内可算项已自行完成。仍待 owner 的是既有八件，不因本批模板出现而改变状态。

## 第 5 步：连锁重写

### 5.1 本批自身的规则修正事件

| 前提/规则 | 原形 | 新形 | 触发 | 影响 |
|---|---|---|---|---|
| G2 历史回测触发器 | 只列 `docs/generated/`、UNREVIEWED、candidates | 增加窄作用域 `LEGACY_GENERATED_EQUIVALENT` | 历史树没有 `docs/generated/`，首轮字面回测将零命中 | 能命中 C-26 同型，但不把所有 receipt 引用一概判红 |

修闸提交：`7a4df51811f74c2cb8722cd0204d39a6eb13256d`。

### 5.2 六类消费者

| 类别 | 检索/重判 | 状态 | 负责人/到期 |
|---|---|---|---|
| canonical 条目 | C-15/C-17 当前 canonical 与 20260808 diff 回读 | 成立但理由/措辞已换，启动时关闭历史欠账 | canonical 历史执行席，已闭 |
| 仓库内承重文书 | G1/G2/G3 三份随机样本 | 需重验；本批只回测，不改历史原件 | 后续消费者按三闸处理 |
| 兄弟线净输入 | C-26 receipt paraphrase | 作废为证据，可保留为索引 | 常驻消费闸 G2 |
| 代码 call site | C-08 四处 | 两闭、一作用域复核、一开放 | 2026-08-22 |
| 记忆卡 | C-26 订正卡 | 成立，作为历史证据，不作机器真源 | 无改写 |
| 在飞外部输入 | fen1 至 fen5 | fen1 snapshot superseded，其余历史作用域限定 | `OUT-*` 五行；原会话单独失效通知均 `NOT_EVIDENCED` |

### 5.3 :769 连锁重写

`OD-B0-CHAIN-769` 已登记总责席、2026-08-22 到期日和两项子动作：

- 定理 #21 不得继续用“箱只是有界吸收”标签代替参数账。
- U-01“箱口限制多余、二期删”必须重跑可达性签、拒真签和 owner 签；本批不执行删除。

## 第 6 步：双向保真验收

### 6.1 三闸两问

| 闸 | 堵住的非法孔 | 可能关掉的合法能力 | 正例保留方式 | 判定 |
|---|---|---|---|---|
| G1 | 条件/待核条款洗成既定前提 | 合法的背景说明、开放问题罗列 | 明标“界未核”、列开放前件、声明不参与结论 | 没有过严到禁止背景引用 |
| G2 | 视图/摘要/候选替代真源 | 合法的检索导航和候选研究 | 放进“检索记录”，回读真源；候选只进待审/反例队列 | 修闸后仍保留 receipt 作为索引 |
| G3 | 批次参数直接放开 certified 限制 | 合法的研究估算、保守分析、裁决分支账 | 明标批次文书、权威封顶、登记形态欠账 | 没有把“非冻结”误写成“必假” |

### 6.2 对称套用

- G1 同时检查证明的正向前提与删除限制的反向前提。
- G2 同时检查输入侧 source、输出侧 consumer，中间摘要不能在任一方向冒充真源。
- G3 同时检查“放开/删除”的增解动作和“无条件证明/证书强化”的叙述动作。

### 6.3 fail-closed 与观察性

本批没有新增运行时埋点，故不能写“真零”。所有“零触发/零拒绝”类证据必须写：

`无埋点（欠账号 OD-B0-INST-01）`

现有文书级回测有明确数据源，命中数 2/1/3 不属于无埋点推断。

C-08 定向测试命令：

```text
.venv/bin/python -m pytest -q \
  src/tests/test_ghost_strict_emptiness.py::test_extract_occupied_cells_includes_ghost_cells \
  src/tests/test_ghost_strict_emptiness.py::test_witness_pose_resolved_occupancy_includes_ghost \
  src/tests/test_rab_sep_soundness_sentinels.py::test_ghost_pick_marker_excluded_from_context_even_with_pool
```

结果：`3 passed in 0.79s`。

拒真席默认独立分席仍待 owner 裁。本批自量采用同一执行席的反向 pass，故只接纳“批 0 文书与验收事实”，不声称完成全项目席位制度的独立性验收。

## 第 7 步：饱和扫描

### 7.1 三层圈定

| 层 | 内容 | 结果 |
|---|---|---|
| 层 0 | 五件主交付、三条验收、八件待裁红线 | 全覆盖 |
| 层 1 | 三闸彼此交叉、C-08、C-15/C-17、C-26、:769、fen1-5 | 发现一条新结晶：G2 需历史兼容等价类 |
| 层 2 | G2 修闸对合法 receipt 检索、候选研究和未来 `docs/generated/` 的反向影响 | 未发现需继续扩闸的新结晶；保留窄作用域 |

### 7.2 pairwise 交叉

| 对 | 结晶 |
|---|---|
| G1 × G2 | 摘要中的“待核”不能既逃过路径检查又被当作条件已清；最终仍回到实际消费关系 |
| G1 × G3 | 批次参数导致 reachability 只能 conditional 时，G1 与 G3 双闸均命中，但阻断理由分别记录 |
| G2 × G3 | 批次 receipt 同时是摘要和参数来源时，必须回读真源；不能因双重命中把同一缺口算成两份独立证据 |
| 三闸 × 外发台账 | raw reply/receipt 不能越过本地核签、快照有效性和当前真源 |
| 三闸 × 开放欠账 | “已登记”不等于“已关闭”，开放行继续阻断对应强结论 |

### 7.3 终止状态

| scope | rounds | new_entries | terminated_by | 状态 |
|---|---:|---:|---|---|
| 批 0 文书规则 pairwise | 2 | 1 | 第二轮 pairwise 零新结晶 | `PAIRWISE_FIXED_POINT_INCOMPLETE` |

诚实边界：这不是规则闭包饱和；没有运行完备求解器或 proof checker；未扫描全仓所有历史文书。`rules/derived/` 未创建，任何扫描产出仍在 docs 侧且不得被当成已审 L2 条目。

## B. 消费侧三闸随机回测

### B.1 抽样协议

模式：分层随机，每个闸对应一个已登记历史病灶总体，固定种子，一闸抽一份，G3 排除已被前两层抽中的路径。G2 只有一份保留订正前承重句的可恢复历史快照，因此该层总体为单元素；不伪造第二份独立历史原件。

```text
seed_material = 7a4df51811f74c2cb8722cd0204d39a6eb13256d:batch0-consumption-gates-backtest-v1
seed_u64      = 5861986475307631752
algorithm     = Python random.Random(seed); G1/G2/G3 各抽一份；路径不得重复
```

抽中样本：

| 闸层 | 路径 | SHA-256 |
|---|---|---|
| G1 | `docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md` | `5680b9860970e7dd249b1403ba7df53361dce3c7a701f2398e11b9c481cbbbe1` |
| G2 | `.artifacts/memsys_meeting_20260808/plate_v2_dryrun/apply_backup_082723/rules-audit-20260718.md` | `84543fc23535cdfd424a54e2697f4d39100852f226344a825975d3e8b6b119e2` |
| G3 | `docs/research/p2_0_specialized_20260807/refute_round1/GAME_RULE_IMPACT_AUDIT.md` | `23ca6fde7820020e22f45bae73e7d3e207748e19e87c0fa60e01096309416c7b` |

### B.2 命中明细

| 闸 | 命中坐标 | 前提 | 消费动作 | 处置 |
|---|---|---|---|---|
| G1 | 公理核 `:141 → :142` | 速率引理明确 conditional 于满产 + 最小车道，且数值未独立复算 | #8 把 #7 用作 front 排他的 WLOG 支撑 | BLOCK 该继承，除非开放前件在权威载体关闭 |
| G1 | 公理核 `:155`、`:231-233` | “箱只是有界吸收”，未把界可达性参数化 | 用来给 W-ADM-03“限制口必要性=零”补独立支撑 | BLOCK 标签替代参数账；转 `OD-B0-CHAIN-769` |
| G2 | 规则审计 `:27-29`，订正 `:94-99` | 兄弟线 receipt 的 `semantics` 转述被读成“错货不阻塞” | 推出“免费开关、直接回答 band22、对证明链零影响” | `LEGACY_GENERATED_EQUIVALENT` 命中；回读原码后结论翻案 |
| G3 | 影响审计 `:125` | 公理提案推导 #20，canonical 未收录 | 被称为对 (b) 最有分量的正面发现 | 研究级可留；不得直接支撑 certified/无条件强化 |
| G3 | 影响审计 `:128` | 批次设备参数表的分流器游标/死口语义 | `SUPPORTS` (b)，同时 `NOT_IN_CANONICAL` | 权威封顶批次文书，需 provenance 回流 |
| G3 | 影响审计 `:130` | `MFG_SLOT_PARAMS_20260806.md` 的 1 槽×50、多口绑定 | 输入侧直接 `SUPPORTS`，输出侧又暴露承重缺口 | 研究级可用，强结论保持 conditional |

命中计数：`G1=2，G2=1，G3=3`。三闸均非零。

### B.3 修闸记录

首轮只按未来正式对象 `docs/generated/`、UNREVIEWED、candidates 做字面检索时，历史树 G2 为零命中。按验收规则判定“闸写空了”，没有换样本，而是：

1. 回读 C-26 原件与订正链。
2. 增加窄作用域 `LEGACY_GENERATED_EQUIVALENT`。
3. 精确提交 `7a4df51`。
4. 用同一 seed、同一三份样本重跑，G2 命中 1。

## C. 三条验收自量

| 验收 | 实测 | 结论 |
|---|---|---|
| ① 五份文件存在且两账首批非空 | 五文件均存在且非空；外发唯一 id 5 个；开放欠账唯一 id 8 个 | PASS |
| ② 本批按新模板出完整凭据 | 本文件逐步覆盖 0 至 7、三闸、席位、方向暴露与失败后果 | PASS，仍受“非独立人员核签”边界约束 |
| ③ 随机三份历史承重文书，三闸各至少命中一次 | 固定 seed；命中 2/1/3；G2 经一次修闸后同样本重测 | PASS |

## D. 提交与批尾三检

已完成提交：

1. `80b53640d6b7cfac6c4df71cf140c5407e8c3d6f`，五件主交付物。
2. `7a4df51811f74c2cb8722cd0204d39a6eb13256d`，G2 历史兼容修闸。
3. `5b93084ba0336b32465926e082948f6b6c81c710`，本批完整自量凭据。

owner 放行时，另一线最新既有提交为 `8375484`。开跑前 `git status --short --untracked-files=no` 无 tracked 改动，`docs/CURRENT.md`、`docs/CATALOG.md` 等共享生成页无他人未提交差异，满足串行开跑条件。

批尾三检命令与结果：

| 检查 | 结果 |
|---|---|
| `.venv/bin/python devtools/docctl.py intake --changed` | exit 0；成功识别当前比较修订与 changed paths |
| `.venv/bin/python devtools/docctl.py doctor` | `PASS: document system is self-consistent and compatibility projections are fresh` |
| `.venv/bin/python devtools/check_knowledge_docs.py` | `PASS: knowledge spine is internally consistent and generated projections are fresh` |

三检后复查：tracked diff、staged diff、共享生成页 diff 均为空。`8375484` 所代表的另一线既有输入已在当前 HEAD 中，未出现需要覆盖或拆分的并发脏改动；本轮知识重建未产生额外生成页提交。当前这份批尾补记只按自身精确 pathspec 提交。

## E. 收批表

| 步 | 触发 | 完成 | 结论 |
|---|---|---|---|
| 0 批型与档案 | 是 | 是 | PASS |
| 1 参数账 | 是 | 是 | PASS WITH MISSING，MISSING 均显式阻断/降级 |
| 2 可达性尺子 | 是 | 是 | PASS |
| 3 前件卫生 | 是 | 是 | PASS |
| 4 裁决包 | 条件触发 | 是 | 无新 owner 包，理由已写 |
| 5 连锁重写 | 是 | 是 | G2 修闸与 :769 欠账均登记 |
| 6 双向保真 | 是 | 是 | 三闸正例保留；C-08 三哨兵通过；埋点仍开放 |
| 7 饱和扫描 | 验收要求完整凭据 | 是 | `PAIRWISE_FIXED_POINT_INCOMPLETE`，不宣称饱和 |

方向暴露：

- 过严面：G2 若把所有 receipt 一概封死会误伤检索，已用窄作用域修正。
- 过松面：人工三闸尚无机器 checker；无埋点不能观察真实运行时拒绝面。
- `NOT_ESTABLISHED`：全仓所有历史文书均过三闸、拒真席人员独立性、C-08 两个开放 call site、埋点库存与代码实施。
- conditional：任何依赖 `OD-B0-C08-03`、`OD-B0-C08-04`、`OD-B0-INST-01`、`OD-B0-CHAIN-769` 的强结论。

本批可合法发布的最高结论：批 0 五件工作文书已建立，三条自量验收通过，批尾文档治理三检全绿；开放欠账继续按阻断范围约束后续强结论。

不得发布的更强表述：八件已获批准、三闸已机器化、全仓历史已清洗、C-08 已全闭、规则闭包已饱和。

收批席最终 verdict：`FINAL_PASS_WITH_OPEN_DEBTS`。
