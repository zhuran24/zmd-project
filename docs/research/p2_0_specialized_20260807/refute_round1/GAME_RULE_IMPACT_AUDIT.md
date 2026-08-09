# 游戏规则影响面全量清点（splitfree 重判专用，2026-08-07）

**性质**：规则影响面清点席产物。研究层，不改生产代码、不改锁面、不改 canonical、不动任何冻结件。
**触发**：owner 追问「证明时要考虑所有有影响的游戏规则——考虑到了吗？」`REJUDGE_REPORT.md` 此前没有系统做过这件事，本文书补上。

## 0. 被审的两条结论

| 代号 | 结论 | 出处 |
|---|---|---|
| **(a)** | 台间占空分配是游戏内的真自由度；机制 = **饥饿节流**（喂多快跑多快，布线即分配） | `REJUDGE_REPORT.md` §1 |
| **(b)** | 阶梯见证（制瓶机 5 满 + 1 半 ⇒ 钢块 17 产道 = 17 耗道，纯双射免分流）在**速率/机制层**可实现 | `REJUDGE_REPORT.md` §2 |

判定五类：**SUPPORTS**（构成机制基础）/ **NEUTRAL**（无接触）/ **THREATENS**（可能推翻或收窄）/ **NEEDS_SIMULATOR**（速率类分歧，按 owner 规矩以 IndustrialPlanner 模拟器判例定）/ **NOT_IN_CANONICAL**（规则只活在记忆卡或提案文书里、canonical 正文缺失）。

一条规则可以同时被判 THREATENS 与 NEEDS_SIMULATOR（威胁存在、消解方式是模拟器判例），也可以同时被判 SUPPORTS 与 NOT_IN_CANONICAL（它撑着结论，但它不在冻结文本里）。

**规则源覆盖**：`rules/canonical_rules.json` 全文（v1.2.0，40,371 字节，9 个顶层区块逐条过）；`rules/preprocess_plan.json`；`docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md`（公理 A1–A11、设备参数表 15 行、推导矩阵 #1–#21、残余清单 5.1/5.2、预测检验 P1–P3 + P-c/P-d/P-e）；`PORT_SEMANTICS_REVERDICT_A_20260806.md` 及其三则附录/批注；`MFG_SLOT_PARAMS_20260806.md`；`docs/research/rules_audit_20260718/00_owner_adjudications_and_rule_corrections.md` §3.1–3.7 与 §7；记忆卡 `machine-input-no-selectivity-pollution.md` 全文（owner 历次速率与口岸裁定）。

**机器证据**：本清点新跑的核对全部落在 §6，源数据 = `split_free_probe_v2_receipt.json`、`data/preprocessed/mandatory_exact_instances.json`、`data/preprocessed/generic_io_requirements.json`、上游 `IndustrialPlanner`（`7b946c16`）的 `src/registry/recipe-definition.ts` 与 `src/simulation/runtime/runtime-slot-access.ts`。

---

## 1. 总账

| 判定 | 条数 |
|---|---|
| SUPPORTS | 33 |
| NEUTRAL | 21 |
| **THREATENS** | **6** |
| **NEEDS_SIMULATOR** | **7 个判例** |
| **NOT_IN_CANONICAL** | **9 条** |
| 反向（规则被 (a)/(b) 伤，而非伤 (a)/(b)） | 1（`rate_lemma_scope`，报告 §4 已处理） |

（SUPPORTS/NEUTRAL 的条数取决于怎么切条目；口径 = §2 各表的行数，一行一条。THREATENS / NEEDS_SIMULATOR / NOT_IN_CANONICAL 三栏是本文书的实质产出，口径固定。）

**主线程点名的两个嫌疑，核验结果：**

- **嫌疑一（汇流点 2s CD / 双入竞争减半）——部分证实，但不伤 (a)/(b)。** 见证里**只有两处合流**，都是终端成品段（qiaoyu_capsule 3→1、valley_battery 3→1），入流各 1/5、1/5、3/20 与 1/5×3，合计 11/20 与 3/5，离带帽 1 件/tick 有 40% 以上裕量，逐流也都 ≤ 1/2（owner「最坏减半」上限）。**钢块 5 满 1 半确实是零合流的纯双射**——收据 `part_c_per_commodity.steel_block.assignment` 17 条一一对应逐条可读，无一条耗道收两条产道。真正被 2s CD 咬到零裕量的不是见证，而是**报告 §4 用来打 canonical 速率引理的那个反例**（两条 1/2 残道共道，和 = 1 = 带帽，恰好卡在边界）。详见 §6.1。
- **嫌疑二（A9 多配方）——证伪。** 17 个 operation 逐个回上游注册表核对机型与配方集：**没有任何一台机器，在只喂它自己配方原料的情况下，能匹配到第二个配方**。制瓶机（`shaper_1`）的 8 条配方里只有一条吃 `item_iron_enr`（= 钢块），且需 2 件；半速那台缓存里握着 1 件钢块时**没有任何备选配方可以开工**，只能等第 2 件——这正是阶梯占空成立所需的行为。零件机是**另一台机器**（`cmpt_mc_1`），不共享配方集。详见 §6.2。**但这个排除依赖一条实例特定事实**（同机器的其它配方要的货在本产线 19 商品里全都不存在），不是一般原理，商品集一变就要重算。

---

## 2. 逐规则清点表

### 2.1 `globals`

| # | 规则原文（`rules/canonical_rules.json`） | 判定 | 分析 |
|---|---|---|---|
| G-1 | `grid: {width: 70, height: 70}` | NEUTRAL | 纯几何域。速率算术层不接触；(b) 的几何可实现性本来就在报告 §6 声明为未验。 |
| G-2 | `time.tick_interval_seconds: 2.0` | **SUPPORTS** | 离散 tick 是占空能取分数值的前提，也是它取值受限的来源。阶梯要的两个分数都落在整数节拍上：制瓶机 duty 1/2 = 每 2 tick 到 2 件钢块开一轮（`ticks_per_cycle: 1`）；灌装机 duty 3/4 = 每 4 tick 进 6 件（1 件/tick 的道 + 半速道），长期均值 3/2 件/tick 精确。没有「半个 tick」这种不可实现的要求。 |
| G-3 | `logistics.belt_capacity_per_tick: 1.0` | **SUPPORTS** | 整个车道计数的底座。产/耗道数 = `ceil(速率/1)`，(b) 的 17=17 匹配、定理 1 的 11<12 鸽巢都直接建在它上面。 |
| G-4 | `logistics.port_max_throughput_per_tick: 1.0` | **SUPPORTS** | 逐**口**的帽，与 G-3 的逐**带**帽是两件事。已逐台核过见证的口需求：crusher_sandleaf 满速 3 件/tick 出 = 3 个出口 × 1（3×3 恰好 3 个出口，零裕量）；核心那条 3→1 合流入口 11/20 ≤ 1 ✓。全部合规。注：公理提案 §4「一致性矩阵」标该常数在仓内**零消费点**（`P-CLEAR-02`），即它是描述性常数、不进求解路径。 |
| G-5 | `logistics.machine_min_clearance_cells: 1` | NEUTRAL | 其语义已被 `semantics.machine_min_clearance` 重裁为 front 格 identity（见 S-6），不是机身护城河，与占空无关。 |
| G-6 | `empty_rectangle.objective / min_side_admissibility / emptiness` + `emptiness_adjudication`（「No occupant of any kind may intersect the target empty rectangle」，owner 2026-08-05） | NEUTRAL（对 (b) 弱有利） | 目标函数与占空正交。**弱有利的方向**：报告 §4 算出阶梯全网车道总数 622 < 均摊 628，且分流点从 36 降到 2（少 34 个分流器 = 少 34 个占格物流件），严格空地语义下占格越少空矩形越容易大。它不构成对 (b) 的支持论证，只是说明 (b) 若成立不会反噬目标。 |

### 2.2 `routing_rules`

| # | 规则原文 | 判定 | 分析 |
|---|---|---|---|
| R-1 | `layers: {ground: 0, elevated: 1}` | NEUTRAL | 已由 `semantics.routing_cross_junction` 重裁为单格十字器件的建模表示，无真实坡道。几何层事项。 |
| R-2 | `bridge_mechanics` 五布尔（`can_overlap_solid: false`、`can_overlap_straight_belt: true`、`can_overlap_curved_belt: false`、`can_overlap_splitter_merger: false`、`can_turn: false`） | NEUTRAL | 几何层。有一条对 (b) 的**间接弱有利**：`can_overlap_splitter_merger: false` 意味着分流/合流器所在格不能被桥借道；阶梯只有 2 个分流点、2 个合流点，均摊有 36 个分流点，阶梯受这条限制的面小得多。 |

### 2.3 `facility_templates`

七个模板全过。口数按公理提案设备参数表「口数 = 边长」、canonical `port_rule` 给侧别。

| # | 模板 | 判定 | 分析（逐台核对见证的口需求） |
|---|---|---|---|
| F-1 | `manufacturing_3x3`（`port_rule: opposite_parallel_sides`，3 进 / 3 出，需电） | **SUPPORTS** | 见证最紧的一处：crusher_sandleaf 满速出 3 件/tick 需 **3 条出道 = 恰好 3 个出口，零裕量**；半速那台出 3/2 需 2 条道 ✓。molding_bottle 满速进 2 件/tick 需 2 个进口 ≤ 3 ✓，半速需 1 ✓。refinery_steel / parts_maker / crusher_blue_iron / crusher_source / crusher_buckwheat 全部 ≤ 2 进 ≤ 2 出 ✓。 |
| F-2 | `manufacturing_5x5`（`opposite_parallel_sides`，5 进 / 5 出） | **SUPPORTS** | seed_collector 满速出 2 件/tick = 2 出口 ≤ 5 ✓；planter 1 进 1 出 ✓。裕量大。 |
| F-3 | `manufacturing_6x4`（`port_rule: long_sides`，6 进 / 6 出） | **SUPPORTS** | packaging_battery 进 3 + 2 = 5 ≤ 6 ✓（最紧的一台）；filling_capsule 满速进 2 + 2 = 4 ≤ 6 ✓，3/4 那台进 2 + 2 = 4 ✓；三台 grinder 进 2 + 1 = 3 ≤ 6 ✓。 |
| F-4 | `protocol_core`（9×9，`core_limits: {max_outputs: 6, max_inputs: 14}`，不需电） | **SUPPORTS** | 14 进口对终端成品段绰绰有余（需求仅 2 槽）。**但这是 §6.1 那两处合流的来源**：`generic_io_requirements.json` 把 `required_generic_inputs` 定为 `qiaoyu_capsule: 1` / `valley_battery: 1`（= `ceil(总流量)`，胶囊 11/20、电池 3/5 各不足 1 件/tick），所以 3 台产机必须并进 1 个核心口。这个合流**不是阶梯造成的**，均摊下同样是 3→1。 |
| F-5 | `protocol_storage_box`（3×3，3 进 3 出，需电） | NEUTRAL | **266 mandatory 实例里零协议箱**（本清点实测 `facility_type` 计数：132 个 3×3 + 49 个 5×5 + 46 个边界口 + 38 个 6×4 + 1 个核心 = 266，无 `protocol_storage_box`）。箱条款对 (a)/(b) 无接触面。 |
| F-6 | `power_pole`（2×2，不可旋，`power_coverage_radius: 5`，无口） | NEUTRAL | 见 S-13。占空与供电无耦合（功率预算外置）。 |
| F-7 | `boundary_storage_port`（1×3，`inward_facing`，`placement_rule: left_or_bottom_boundary`，不需电） | **SUPPORTS** | 46 个边界口 + 6 个核心出口 = 52 个源头槽，正好承 34 蓝铁 + 18 源石（`generic_io_requirements.required_generic_outputs`）。**一格不多**，因此下游 refinery_blue_iron（`x=n=34`）与 crusher_source（`x=n=18`）的占空被硬钉死在满速——这正是报告 §5.2 表 T6「源口全部取等」的规则依据，且它对任意占空分配都成立。 |

### 2.4 `recipes` / `production_targets` / `commodity_metadata`

| # | 规则 | 判定 | 分析 |
|---|---|---|---|
| C-1 | 17 条配方全表（`template` / `ticks_per_cycle` / `inputs` / `outputs`） | **SUPPORTS**，见 T-1 | 配方比例是占空自由度维数（42）与两条鸽巢的唯一算术来源。**A9 多配方威胁的落点也在这里**：canonical 只记了配方的 `template`（占地形状），**没有记哪些配方属于同一台机器的内置配方集**——footprint 相同不等于机型相同。逐条回上游核实见 §6.2 与 N-3。 |
| C-2 | `production_targets`：`valley_battery` 3.0 / `qiaoyu_capsule` 2.75（`mode: equivalent_full_speed_lines`） | **SUPPORTS** | 它钉死的是**聚合活动量** `x_op`（命题 S1），不钉台间分配——这正是 (a) 成立的规则级理由：目标是产量约束，不是逐台运转约束。报告 §7「认证的六谓词没有任何『设施必须运转』的要求」与此一致。 |
| C-3 | `commodity_metadata` 19 条，特别是 `cycle_group: "buckwheat_cycle" / "sandleaf_cycle"` 与 `source_kind: "cycle_internal"` | **SUPPORTS**，见 T-5 | 两个 `cycle_internal` 族就是定理 1 奇偶性的载体。**同时它是 T-5 的来源**：`cycle_internal` 在游戏语义下 = 物质闭环，环内存料量是守恒量、由初态决定，canonical 对此零条款。 |
| C-4 | `preprocess_plan.utility_operations`（`protocol_core: 14 进 / 6 出`；`boundary_io: 0 进 / 1 出`；`box_sink: 3 进 / 0 出`） | **SUPPORTS** | 与 F-4/F-7 同源。`boundary_io` 的 `generic_output_slots: 1` = A11「一口一次只出一种货」的模型镜像。 |

### 2.5 `semantics` 十三条

| # | 条目 | 判定 | 分析 |
|---|---|---|---|
| S-1 | `axiom_kernel`（A1–A11） | 逐条见 §2.6 | — |
| S-2 | `boundary_placement`（左/下边界含 (0,0) 角；生成期不得预删互斥角 pose） | NEUTRAL | 候选池生成规则，几何层。 |
| S-3 | `routing_cross_junction`（「The two channels may carry DIFFERENT commodities but must be perpendicular when co-located; a bridge cannot turn」） | NEUTRAL | 几何层。与 (a)/(b) 的速率账无接触（十字两通道各自满速已由 owner 实测坐实，见 A7）。 |
| S-4 | `mixed_commodity_flow` + `terminal_clause`（三分口岸：(1) 有线仓储口无限混吃 / (2) 协议箱 6 槽有界 / (3) 机器口无选择性、混流终止于机器口不安全） | **SUPPORTS** | **见证完全不需要混流**：17 种 split-free 商品各走自己的道；被迫分流的 buckwheat/sandleaf，分流后两支仍各自只跑一种货——**分流不是混流**。所有终端都是单商品，class (3) 的污染机制不触发，class (1) 的两处 3→1 合流也是单商品并流。⚠ 反向：该条末句「under `semantics.rate_lemma_scope` the legal mixing domain is in fact confined to the final-product terminal segments」被报告 §3 定理 2 在速率层收窄（阶梯下**速率兼容的异商品段对**出现在端口残道上——速率算术不再把中间品钉死为纯流；这是速率排除失效，**不构造实际共道**。原文此处写「混流窗口」，勘误二轮按 D-05 术语订正，20260807），但这伤的是本条的措辞，不是 (a)/(b)。 |
| S-5 | `connectivity_quantifier`（「per commodity, every SINK front is reachable from SOME source front AND every SOURCE front can reach SOME sink front. Multiple independent connected islands of the same commodity are ALLOWED」） | **SUPPORTS** | (b) 的形态是**点对点专线的大集合**（钢块 17 条互不相干的产→耗直连），这在「允许多连通岛」下完全合法；若谓词 5 要求单一生成分量，17 条独立专线会被判非法、(b) 直接死。这条是 (b) 在连通语义上的通行证。 |
| S-6 | `machine_min_clearance`（「the stored port coordinate in candidate placements IS the front/belt cell itself」；「Machine bodies may touch; there is no body-to-body clearance requirement」） | NEUTRAL | 几何层。 |
| S-7 | `warehouse_bridge_exclusion`（「the in-game 'warehouse bridge' … is REAL game mechanics but is EXCLUDED as a legal wiring structure in this model」；「If the production targets ever change, this exclusion must be re-adjudicated」） | NEUTRAL（对 (a)/(b)），**但承重于定理 1** | 对 (a)：仓库桥被排除只会**缩小**布线自由度，占空多胞形（由 `x_op` 与 `n_op` 决定）不变，(a) 不受影响。对 (b)：见证是纯直连布线，天然合规。**但报告 §3 定理 1 隐含依赖它**——若仓库桥合法，buckwheat 可以走「planter → 核心进口 → 仓库 → 边界取货口 → crusher」，产道与耗道不再需要直接匹配，11 < 12 的鸽巢就绕开了。报告没有把这条前提写出来。它是 owner 裁决级输入（公理提案推导 #15：「不可推——产线论证建模选择，绑定 3.0/2.75 产量目标，目标变更须重裁」），本身条件性成立。**建议报告 §3 定理 1 补一句前提。** |
| S-8 | `protocol_storage_box_wireless` + `slot_count_clause`（6 个独立单槽组；「blocks exactly when its 6 slots are all occupied, REGARDLESS of how many commodity types are involved」） | NEUTRAL | 零实例（F-5）。 |
| S-9 | `power_source_note`（中枢是电源；杆无条件远距取电；「covered by some pole stencil」与游戏效果等价） | NEUTRAL | 见 A8。 |
| S-10 | `item_admission_port_exclusion` + `rationale_restated`（限制口存在但刻意不建模；理由 (a) 中间品不能共道 / (b) 唯一混流域终止于有线仓储口 / (c) 分拣终端定理） | **SUPPORTS (a)**，反向受伤 | **对 (a) 是独立支持**：限制口的速率语义（`rationale_restated` 原文「10 s fixed-window quotas of floor(r/6)」）本身就是一个**显式限流器**——游戏里除了「少喂料」之外还有第二条给机器降占空的通路，(a) 的机制不是孤证。⚠ 反向：理由 (a) 引 `rate_lemma_scope` 说「intermediate commodities cannot legally share a lane」，这在阶梯下不成立（报告 §4 反例 40 对）；但 (b)(c) 两条独立成立，裁决结论（必要性 = 零）不动。已由报告 §5.1 的 Q7 登记。 |
| S-11 | `rate_lemma_scope`（前件 (i) 满产 + (ii) 最小车道分配；残道集 `{5/6, 11/12, 19/22, 21/22, 10/11, 1}`；`predicate_status: "non_predicate"`） | 反向（本报告的靶子） | 报告 §4 已完整处理：欠一条「均摊占空」前件。本清点独立复核的补充结论：该条 `usage_rule` 明写「rate arithmetic never enters a certificate」，故 (a)/(b) 与它的冲突**不伤任何在案证书**，只伤叙述层。 |
| S-12 | `port_commodity_scope`（binding 槽位单商品制；表达力缺口被钉在终端成品段） | **SUPPORTS** | 见证每条道、每个槽都是单商品，完全落在该 scope 声明的作用域内 ⇒ (b) 不额外扩大表达力缺口。 |
| S-13 | `power_coverage_stencil`（12×12 轴对齐方形，相交判据） | NEUTRAL | 逐台供电覆盖与占空无关：闲置与半速机器同样需要覆盖（谓词 6 按 `needs_power` 判，不按运转状态判），所以占空分配改变不影响供电几何。 |

### 2.6 公理核 A1–A11

| # | 公理（canonical `semantics.axiom_kernel.axioms` 原文摘要） | 判定 | 分析 |
|---|---|---|---|
| A1 | 运输守恒·单向：「items are neither created, destroyed nor moved backwards」；「Default failure mode of a transport step: the move simply does not happen and the item waits upstream in place」 | **SUPPORTS (a)**；例外条款见 **T-2** | **这是 (a) 的正面机制条文**：搬不动就在上游等 = 供料不足直接转成机器空转，不会凭空补料也不会退货。配合有限缓存 ⇒ 长期消耗率 = 长期到达率。⚠ 例外「explicitly configured per-device blockage auto-clearing (destroys items; unconfigured it is fully inert)」是唯一能破坏守恒账的通道，见 T-2。 |
| A2 | 调度筛点恰四个；「Senders are content-blind: splitter rotation reads priority group and cursor, never item type」；「legal layouts feed machine inputs through single-slot logistics chains where no selection is possible」 | **SUPPORTS (a)** | 「发送端内容盲 + 单槽链无选择」正是「布线即分配」的规则依据：机器**没有**调节自己进料速率的手段，它的占空完全由上游送来多少决定。若机器能挑货或能主动拉货，(a) 的「布线即分配」就不成立。 |
| A3 | 缓存格：动态定型 + 静态锁；「One commodity per slot at any time」；「a full same-type slot rejects at node level rather than overflowing to a free slot」 | **SUPPORTS**，稳态外见 **T-4** | 正面：双原料机器（三台 grinder、灌装机、装配机）各原料独占一槽，组内互斥保证一种原料吃不掉另一种的槽位——见证里每台机器的两种原料按配方比例精确供给（如 grinder_fine_buckwheat 半速那台：buckwheat_powder 1 件/tick : sandleaf_powder 1/2 件/tick = 恰好 2:1），稳态不会有一侧撑爆。⚠ 非稳态下「满容整节点拒收」会把失衡变成队头阻塞，见 T-4。 |
| A4 | 设备构成；仓库是唯一隐式设备；「The wired warehouse INPUT side is the protocol core alone」 | **SUPPORTS** | 核心 14 进口是终端成品的合法非拒收终点，§6.1 那两处合流的落点合法。 |
| A5 | 接口四款（a front 身份 / b 闲置口不占格 / c 边圈全功能 / d FrontUsable 闭集） | NEUTRAL | 几何层。A5b「未接线的口合法闲置、不占其 front 格」对 (b) 有**弱有利**：见证里大量机器只用了部分口（如 5×5 采种机 5 个出口只用 2 个），闲置口不额外占地。 |
| A6a | 形态公理：「every logistics device laid on the grid is a specialized straight belt; functional belts are straight-only; one cell never hosts two independent devices」 | NEUTRAL | 几何层。 |
| A6b | 「Belts are single-channel FIFO with no overtaking」（明标：游戏侧未实测、不挂 owner 名下） | **SUPPORTS** | 单商品道上 FIFO 无害（先后同型）。它真正的作用是让「一条道混两种货」变危险——见证不用混流，所以这条只当护栏、不当负担。 |
| A7 | 速率公理：「Belt line throughput cap = 30 items/min … 2 s headway」；「**Device cadence upper bound = recipe duration (attained absent blocking and starvation)**」；「Rate-to-geometry conversion is fixed at the single point slots = ceil(rate/cap)」 | **SUPPORTS (a)**，等号方向见 **N-1** | 「节拍上界 = 配方 duration，无阻塞且不断供时取等」是 canonical 里**唯一**直接触及饥饿节流的句子，也是 (a) 的最强正面文本。⚠ 但它只给**上界**：「断供 ⇒ 跑不满」在案，「断供多少 ⇒ 恰好慢多少」（即长期吞吐 = 供料率）**没有条文**，那要靠 A1 守恒 + A9 消耗定量 + 有限缓存推出来。见 N-1。 |
| A8 | 供电使能：「an uncovered powered device performs none of its behavior rules」；功率预算外置 | NEUTRAL | 半速机器与满速机器同样需要覆盖，占空不改变供电几何或预算（预算已外置）。 |
| A9 | 转化公理：「Recipe sets are built into machines … **one machine generally carries several recipes, and processing starts when cached inputs match ANY recipe of the set**」；产出侧「when products cannot be placed the recipe halts in waiting-output … (simulator answer taken as working default; game-side undecided)」 | **THREATENS → 已核实排除**（T-1）；产出侧另见 **T-3** | 主线程点名的嫌疑二。**结论：证伪，(a)/(b) 不受伤**，逐机核对见 §6.2。产出侧的「游戏侧未定谳」是另一条独立威胁（T-3）。 |
| A10 | 域公理：19 商品全固体，管道族条款不适用 | NEUTRAL | 明确 scope，无接触。 |
| A11 | 商品身份：来源侧身份来自玩家配置；「Legal initial state: map crops provide the first seeds (owner-adjudicated); **the general legality domain of pre-seeded caches remains unadjudicated**」 | **SUPPORTS**（源侧）+ **THREATENS**（初态，T-5） | 正面：46 个边界口各出一种货，与 F-7 的 52 槽账闭合。⚠ 「预置缓存合法域未定谳」直接顶着两个作物闭环能否被充到目标占空，见 T-5。 |

### 2.7 公理提案的推导矩阵 / 参数表 / 预测检验（canonical 未收录的部分）

| # | 条目 | 判定 | 分析 |
|---|---|---|---|
| D-1 | 推导 #20：「单分流器支线喂料 ≤ 进料率一半 ⇒ 满速机器（30/min）不可能从流动干线经单分流器喂饱 ⇒『一口一带』从记账惯例升格为动力学必然」 | **SUPPORTS (b)**，**NOT_IN_CANONICAL** | **这是本次清点对 (b) 最有分量的正面发现。** 阶梯见证从不要求分流器去喂满速机器：满速机器全部走点对点专线；两个分流点各把一条速率 1 的产道**恰好对半**劈给两台半速机器（各要 1/2）。这正是内容盲分流器的**缺省行为**，零配置、零调参。对照均摊：需要 13 个（buckwheat）和 23 个（sandleaf）分流点，且要求的比例是 1/3 与 **7/22**——7/22 分母含 11，不是分流器对半/三分能直接产生的比例，只能靠下游背压逼出来（见 M-6）。**「阶梯比均摊更合分流器语义」是均摊约定的又一条独立弱点。** |
| D-2 | 预测检验 P-d（owner 08-06 定谳原话：「肯定对半，没连上的口不会轮询」） | **SUPPORTS (b)**，**NOT_IN_CANONICAL** | 三出口分流器只接两口 ⇒ **严格对半、不丢货**。见证的两个分流点正是这个形态（`part_g_segment_thickness` 实测 `split_points: 1`，两段各 1/2）。规则给的比例和见证要的比例逐字相等。canonical 正文无此条款。 |
| D-3 | owner 08-06 速率注记：「借道汇流点 2s CD、双入满速竞争**最坏减半**（各 ≤0.5 件/tick）⇒ 借道段共乘算术 = 各流之和 ≤1 件/tick、残余 >1/2 的输出道不可被满速流借道」 | 见证：**SUPPORTS**；报告 §4 反例：**零裕量**。**NOT_IN_CANONICAL** | 主线程点名的嫌疑一。见证的两处合流各流 ≤1/5 < 1/2、合计 ≤3/5 < 1，裕量充足 ✓。**报告 §4 用来打 canonical 的那个反例**（两条 1/2 残道共道）恰好落在两个上限上：每流 1/2 = 「最坏减半」的上限，和 = 1 = 带帽。**算术上合法，但零裕量**——见 §6.1 的诚实注记。该条款是 owner 定谳，**canonical 正文完全没有**。 |
| D-4 | 设备参数表：分流器「游标只在本 tick 真发生搬运时旋转、停在失败侧；未连接死端口被跳过、不阻塞轮转；全部出边不可搬运 = 队头阻塞」 | **SUPPORTS**，**NOT_IN_CANONICAL** | 见证的两个分流点两支都常态可搬（各要 1/2、供给恰 1/2），不进队头阻塞分支。 |
| D-5 | 设备参数表：汇流器「1×1、3 进 1 出；仲裁细节**未定谳**（D2）」 | **NEEDS_SIMULATOR**（M-3） | 见证的两处合流恰好是 3 进 1 出的单器件形态，但三路仲裁语义是公开欠账（残余 5.2#12）。速率有大裕量，风险低，但没有在案答案。 |
| D-6 | `MFG_SLOT_PARAMS_20260806.md`：制造机「每种原料 1 槽 × 容量 50，同侧全部口共绑同一 buffer 组」；**输出缓冲 1 槽 × 50** | 输入侧 **SUPPORTS**；输出侧 **THREATENS**（T-6），**NOT_IN_CANONICAL** | 输入侧已闭（P-c owner 确认，`slots=ceil` 换算方向安全）。**输出侧从未被论证**：crusher_sandleaf 满速要从**一个** 1 槽×50 的产物缓冲经 3 个出口同时推出 3 件/tick。这条前提 (a)(b) 与均摊**共享**（均摊下 duty 21/22 同样要 `ceil(63/22)=3` 条出道），所以它不改变 (a)/(b) 相对均摊基线的胜负，但它是全项目未登记的承重前提。见 T-6。 |
| D-7 | 推导 #1（机器口污染链）/ #21（分拣终端定理） | NEUTRAL | 见证零混流（S-4），污染链前提不触发。 |
| D-8 | 推导 #16（连通量词）/ #17（FrontUsable）/ #18（边圈）/ #19（供电忠实性） | NEUTRAL | 分别对应 S-5 / A5d / A5c / S-9，已在上表处理。 |
| D-9 | 残余 5.1#9：模拟器自有调度决策，含「**一 tick 内链式连锁搬运**（决定带链是逐格走还是整链齐动，压 P2.0 startup 瞬态）」 | **THREATENS**（并入 T-4） | 明标「模拟器实现常数，游戏对应未证，引用须降级」。它直接压 (b) 的启动瞬态。 |

### 2.8 记忆卡 `machine-input-no-selectivity-pollution.md` 的历次 owner 裁定

| # | 裁定 | 判定 | 分析 |
|---|---|---|---|
| M-a | 「机器入口没有选择物品的权利」；错货到口只等待、缓存耗尽后照单全收 | **SUPPORTS (a)** | 与 A2 同向：机器无法自我调速也无法挑货 ⇒ 占空 = 供料的函数。 |
| M-b | 口岸三分法终版（有线仓储口无限混吃 / 协议箱 6 槽有界 / 机器口配方槽污染） | **SUPPORTS** | 见证的终端全部合法（S-4/A4）。 |
| M-c | 「**输出口门口过境安全**（输出口只推不吞）」（08-06 公理终审 ④） | **SUPPORTS**，**NOT_IN_CANONICAL**（半在案） | canonical `axiom_kernel.model_stricter_faces` 记了「source-front equal exclusivity … a confirmed over-strict face」这个**结论**，但没记「输出口只推不吞」这条**机制**。对 (b)：见证的半速机器出口残道 1/2 若要被借道，正靠这条。 |
| M-d | 「回退」= 不放行留上游，非反向搬运（08-06 公理终审 ⑤） | **SUPPORTS (a)** | 消掉了「机器会把多余料退回去」这种会破坏 (a) 守恒账的读法。 |
| M-e | A9 三点精化：配方内置、一机多配方、匹配任一即开工（08-06 公理终审 ①） | **THREATENS → 已排除**（T-1） | 见 §6.2。 |
| M-f | A11 认：「一口配置后一次只出一种，品种随玩家配」 | **SUPPORTS** | 与 F-7 / C-4 闭合。 |
| M-g | 箱速率账、箱=汇流区合法终点裁决（08-07） | NEUTRAL | 零箱实例。 |

---

## 3. THREATENS 汇总：六条，逐条给伤害面

### T-1 · A9 多配方自动开工 —— 已核实排除，但排除依赖实例特定事实

**规则原文**（canonical `semantics.axiom_kernel.axioms.A9`）：
> "Recipe sets are built into machines - players cannot author recipe content, one machine generally carries several recipes, and **processing starts when cached inputs match ANY recipe of the set** (owner 2026-08-06). Intake is recipe-blind while processing is recipe-exact."

**若成立的伤害面**：阶梯占空的半速机器长期握着**半份原料**。制瓶机 duty 1/2 时缓存里常驻 1 件钢块（配方要 2 件）。如果同一台机器的配方集里存在一条**只要 1 件钢块**的配方，那台机器会立刻改跑那条配方——见证里的「5 满 + 1 半」就不再是 5 台产瓶 + 1 台半速产瓶，而是 5 台产瓶 + 1 台产别的东西，**(b) 的 17=17 双射当场瓦解**。canonical 的 `recipes` 表按 `template`（占地形状）组织，`manufacturing_3x3` 下同时挂着 `parts_maker`（1 钢块 → 1 钢件）与 `molding_bottle`（2 钢块 → 1 钢瓶），从 canonical 文本**读不出**它们是不是同一台机器。这个嫌疑是真的。

**核实结论：不成立。** 详细证据链在 §6.2。三句话版本：制瓶机是上游 `shaper_1`、零件机是 `cmpt_mc_1`，**两台不同的机器，不共享配方集**；`shaper_1` 的 8 条内置配方里只有一条吃钢块（`item_iron_enr`），其余 7 条要铜锭/石英玻璃/浓缩石英/铁锭/希兰岩粉——**本产线 19 商品里一件都没有**；17 个 operation 逐个走完同一套核对，全部只有唯一可匹配配方。

**残留风险**：排除的依据是「其它配方要的货不在本产线」，不是「机器只有一条配方」。若 `production_targets` 或 mandatory 实例集变化引入新商品，这个核对要整套重做。**建议把这条核对固化成探针**，与报告 §9 的欠账 3（`n_op` 依赖实例普查）挂同一个重算触发条件。

### T-2 · A1 例外①：可配置的堵塞自动清理会**销毁物品**

**规则原文**（canonical A1）：
> "Known exceptions: **explicitly configured per-device blockage auto-clearing (destroys items; unconfigured it is fully inert)**, waiting-output blocking …"

**伤害面**：(a) 的整个机制建立在「物品不生不灭 ⇒ 长期消耗率 = 长期到达率」上。一旦某台设备开了自动清理，它会**丢货**，那台机器的实际吞吐就不再等于供料率，「布线即分配」的等号断掉。公理提案残余 5.2#10 记「堵塞清理销毁机制的游戏对应（SIM-M29）——A1 唯一例外通道，**未定谳**」。

**严重度：低，但要写进作用域。** 该开关未配置时「fully inert」，而认证求的是静态布局、不含运行期玩家配置，所以合法布局默认不开。**处置建议**：把「无自动清理配置」与公理提案 §0 已有的「无运行期玩家干预」并列，写进 (a)/(b) 的作用域前提。这是措辞动作，不是研究动作。

### T-3 · A9 产出侧 waiting-output 的**游戏对应未定谳**

**规则原文**（canonical A9）：
> "Output side: when products cannot be placed the recipe halts in waiting-output, the device blocks, no product is destroyed (**simulator answer taken as working default; game-side undecided**)."

**伤害面**：(a) 的「喂多快跑多快」是**供给侧**的节流。产出侧还有一条对偶通路：下游吃不下 ⇒ 机器阻塞 ⇒ 占空被**背压**压低。两条通路都存在时，占空是「供给上界」与「背压上界」的较小者。见证的稳态里两侧恰好相等（这正是它是可行解的意思），所以稳态下无差别。但如果游戏侧的真行为不是「阻塞并保留产物」而是别的（例如丢弃产物、或降频而非停机），那么 (a) 的「布线即分配」在**满载/背压场景**下的表述要改。

**严重度：中。** 它不推翻 (a) 的核心（供给侧节流），但让 (a) 的完整表述缺一半。判例见 M-7。

### T-4 · A3「满容整节点拒收」+ 50 槽容量：(b) 的稳态是**零裕量刀刃平衡**，规则层不保证它是吸引子

**规则原文**（canonical A3）：
> "An empty slot accepts any domain-matching commodity not already held by another slot of the same slot GROUP; **a full same-type slot rejects at node level rather than overflowing to a free slot.**"

**伤害面**：(b) 声称的是「速率/机制层可实现」，而报告给的是一个**不动点**（各速率精确守恒的稳态），不是一个**吸引子**证明。整张网没有任何裕量：52 个源头槽正好承 34+18（F-7），10 个 operation 的占空被 `x_op = n_op` 钉死在满速（收据 `part_a_duty_freedom`），任何一台机器一旦落后就没有加速追赶的余地。而 A3 的「满容整节点拒收、不找空格溢出」意味着失衡会转成**队头阻塞并向上游传播**，配合公理提案残余 5.1#9 明标未证的「一 tick 内链式连锁搬运」（压 startup 瞬态），**启动瞬态能不能收敛到目标稳态，规则层给不出答案**。

**严重度：中。** 它不威胁 (b) 作为「速率算术层存在性」的判定（报告 §6 已把结论限定在算术层），但威胁把 (b) 读成「这个布局摆下去真的会这样跑」。**建议把 (b) 的措辞钉死为「稳态不动点存在」，收敛性单列欠账。** 判例见 M-5。

### T-5 · 作物族是**物质闭环**，环内存料量由初态决定，而「预置缓存合法域未定谳」

**规则原文**（canonical A11）：
> "Legal initial state: map crops provide the first seeds (owner-adjudicated); **the general legality domain of pre-seeded caches remains unadjudicated** (adjacent question, separate clause)."

配合 `commodity_metadata` 的 `source_kind: "cycle_internal"` 与 `cycle_group`。

**伤害面**：本清点算了一遍两个作物环的物质账。buckwheat 环：11 台 planter 满速吃 11 件种子/tick、出 11 件作物/tick；作物 1:1 劈给粉碎（11/2）与采种（11/2）；采种机 1 进 2 出 ⇒ 出 11 件种子/tick。**产种 11 = 耗种 11，环内总存料量是守恒量**——它不由 `production_targets` 决定，由初始装料决定。sandleaf 环同构（21）。

后果：环里循环的料**太少**，全环按比例慢转，planter 达不到满速，(b) 假设的「planter 全 1」就不成立；料**太多**，缓存填满、A3 整节点拒收、机器阻塞。**目标占空只在一个特定的环内存料量上达到**，而这个量怎么建立起来（地图作物？预置缓存？运行期人工投料？）——A11 只裁了「首粒种子来自地图作物合法」，一般情形明写未定谳（D9）。

**严重度：中偏高，且此前无人登记。** 注意它同样打均摊（均摊也要 planter 全 1），所以不改变阶梯对均摊的相对优劣，但它是 (b) 的「可实现」这个词里一块没铺的地。判例见 M-5。

### T-6 · 制造机**同侧多出口并联抽货**的可加性从未被论证

**规则原文**（`MFG_SLOT_PARAMS_20260806.md`）：
> "grinder_1（粉碎机 3×3，单原料配方族）｜输入缓冲 **1 组 1 槽 × 容量 50**（三个输入口全部绑定同一组）｜**输出缓冲 1 槽 × 50**"

该文书 §「对悬空点的落定」通篇只论**输入**方向（「同商品多口并联可加性」「双带并联喂同一槽」），把 P-c 判别实验设计成「1 台高耗机 + 2 条满速带**量入货**」。**输出方向一句没有。**

**伤害面**：crusher_sandleaf 满速产 3 件 sandleaf_powder/tick，必须从**一个** 1 槽×50 的产物缓冲经 **3 个出口同时**推出 3 件/tick；crusher_buckwheat 与两台采种机同理要 2 件/tick 经 2 个出口。

canonical A7 原文只写了**输入**方向：
> "per manufacturing slot parameters (**one input buffer slot x 50 per ingredient, all same-side ports bound to one buffer group**) this conversion is a demand-side lane lower bound and direction-safe."

**输出缓冲一字未提。** 唯一在案的「多口并行满速」断言是公理提案 A7 给**协议箱**的（「协议箱 3 进 3 出合计 90/90 同时满速（SIM-R03 回归断言）」，且这条本身也不在 canonical 里），制造机没有对应断言。若产物缓冲的出货有逐槽/逐 tick 节流，这些机器全部满不了速。

**严重度：高，但不是 (a)/(b) 特有。** 它是**全项目共享的承重前提**：`n_op` 的推导（`crusher_sandleaf: n=11, x=21/2`）本身就假设每台能出 3 件/tick，均摊约定同样依赖它（duty 21/22 下仍要 `ceil(63/22)=3` 条出道）。所以它不改变本轮重判的任何相对结论，但它是一条**从未登记的全局前提**，值得单独立项。判例见 M-2。

---

## 4. NEEDS_SIMULATOR 判例清单：七个

按 owner 规矩（「canonical 对账以模拟器为第一参照：先模拟器跑判例，分歧再单独研究 + 游戏定谳」），每个判例给「摆什么 / 看什么 / 判什么」。

### M-1 · 机器配方能否由玩家钉死；未钉死时自动选配方的顺序

- **摆什么**：一台 `shaper_1`（制瓶机），只喂 `item_iron_enr`（钢块），供料速率 1 件/tick（= 半速）。跑两组：① 配方槽不设 `channelRecipes`；② 配方槽钉死为 `r_shaper_iron_enr_bottle_from_iron_enr_basic`。
- **看什么**：机器实际跑出的产物类型与产率；`manualRecipeOnly` 在该实体定义上的取值；缓存里长期驻留 1 件钢块时是否触发任何别的配方。
- **判什么**：确认 (i) 玩家钉配方通路存在且钉死后不会跑别的配方；(ii) 未钉死时也只有一条可匹配配方（本清点静态核对已预答「是」，见 §6.2，此判例是动态复核）。**这条同时是 N-2 欠账的定谳材料。**
- **预答（本清点静态核实）**：`src/simulation/runtime/runtime-slot-access.ts:939-961` 的 `manualRecipeOnly` 分支在钉死时**只返回那一条配方**；`src/simulation/topology-compiler.ts:1435-1449` 显示 `manualRecipeOnly = modeSwitchable ? !automaticMode : ch.manualRecipeOnly ?? false`，而 `isAutomaticRecipeChannelMode`（`src/shared/recipe-channel-behavior.ts:6-12`）只在配置键显式为 `true` 时返回真 ⇒ **可切换机型的缺省是手选模式**。自动模式下的排序是 `sortRecipePlansByEfficiency`（`runtime-slot-access.ts:1037-1055`）：产物总量降序 → 原料总量升序 → recipeId 升序。

### M-2 · 制造机同侧多出口并联抽货的可加性（T-6）

- **摆什么**：一台 `grinder_1` 跑 `r_crusher_moss_powder_from_moss_basic`（1 进 → 3 出，2s），进料满速；出口侧分别接 1 / 2 / 3 条满速带，各带末端接不拒收终端（协议核心进口）。
- **看什么**：1 分钟内三种接法各自的总出货件数；机器是否进 waiting-output / block 状态。
- **判什么**：3 出口是否合计 90 件/分钟（= 3 件/tick）。若否 ⇒ `n_op` 的推导前提破，全项目重算，与 (a)/(b) 无关但优先级更高。
- **对照**：协议箱已有 `SIM-R03` 的 90/90 回归断言，制造机没有——本判例就是补这个对照。

### M-3 · 三进汇流器的仲裁（D2 / 残余 5.2#12）

- **摆什么**：一个汇流器，三条入边速率 1/5、1/5、3/20 件/tick（= 见证里 qiaoyu_capsule 的三条产道），出边接核心进口。
- **看什么**：稳态下三条入边各自的通过率是否等于其入流率；有无一路被饿死；出边总速率是否 11/20。
- **判什么**：见证的两处 3→1 合流是否真的无损通过。速率裕量大（0.55 vs 帽 1），预期通过，但 D2 目前是明写的公开欠账。

### M-4 · 饥饿节流的等号（N-1 的定谳材料）

- **摆什么**：一台 `shaper_1` 钉死制瓶配方，进料速率分别设为 2 / 1 / 3/2 件 钢块/tick（对应 duty 1、1/2、3/4）。
- **看什么**：10 分钟长期产出的钢瓶件数；机器缓存曲线（是否单调增长 = 供过于求，还是稳定 = 等号成立）。
- **判什么**：长期吞吐是否**恰等于**供料率经配方换算的值（duty 1/2 ⇒ 0.5 瓶/tick；duty 3/4 ⇒ 0.75 瓶/tick）。这是 (a) 的核心断言，目前只有 A7 的「上界」条文，没有等号条文。
- **附带**：duty 3/4 那档特别值得看——3/4 不是 `ticks_per_cycle` 的整数倍（灌装机 10 件/5 tick 在 3/4 下是每 20/3 tick 一轮），要确认长期均值精确而不是被节拍取整吃掉。

### M-5 · 作物闭环的充料与稳态（T-4 + T-5）

- **摆什么**：完整的 buckwheat 环（11 planter + 6 crusher + 6 seed_collector，占空按阶梯），初始环内存料量设三档：不足 / 目标 / 过量。
- **看什么**：各机器的稳态占空是否落到 `[1×11]` / `[1,1,1,1,1,1/2]` / `[1,1,1,1,1,1/2]`；从零启动能否自行收敛；缓存是否有单调堆积或耗尽。
- **判什么**：(i) 目标占空对应的环内存料量是多少、怎么建立；(ii) 该稳态是不是吸引子。**这是 (b) 从「不动点存在」升格为「真能这么跑」的必经判例。**

### M-6 · 均摊约定所需的非二/三分比例能否由背压产生并稳定

- **摆什么**：sandleaf 的均摊分流结构（收据 `part_g_segment_thickness.sandleaf.uniform_duty`：23 个分流点、最细段 7/22），与阶梯结构（1 个分流点、两段 1/2）并排跑。
- **看什么**：均摊结构里各分流器实际劈出的比例是否收敛到 7/22 这类非二/三分比例；收敛需要多久；有无振荡。
- **判什么**：**这是给均摊约定的反向压力测试。** 分流器是内容盲、对半/三分的（D-2），7/22 分母含 11，不可能由分流器树直接产生，只能靠下游背压逼出来。若模拟器显示均摊比例不稳定或收敛极慢，则「均摊是残道最优约定」（报告 §4 Part F）在**可实现性**上要额外打折——这会进一步加强报告 §4 推荐的措辞方向 b。

### M-7 · waiting-output 的游戏/模拟器行为对齐（T-3 / D5）

- **摆什么**：一台满速机器，出口接一条通向已饱和终端的带。
- **看什么**：机器进入 block 后是否保留产物、是否停止消耗输入、恢复供货后是否原样继续。
- **判什么**：确认 canonical A9 采用的「模拟器答案作工作默认」与游戏一致，从而补全 (a) 在背压侧的表述。**游戏侧定谳只有 owner 能给。**

---

## 5. NOT_IN_CANONICAL 欠账表：九条

这类本身是规则系统病——承重条款活在记忆卡与提案文书里，冻结文本查不到。按对 (a)/(b) 的承重度排序。

| # | 缺失的条款 | 现在活在哪 | 承重于什么 | 建议处置 |
|---|---|---|---|---|
| **N-1** | **饥饿节流的等号**：欠料机器的长期吞吐**恰等于**供料率（canonical A7 只写了「节拍上界 = 配方 duration，无阻塞且不断供时取等」这个**上界**方向） | 无。目前只能由 A1 守恒 + A9 定量消耗 + 有限缓存**推**出来 | **(a) 的整个机制。**「喂多快跑多快」这句话在 canonical 里没有对应条文 | 走 freeze-ritual，在 A7 补一句等号方向（或作为 A1×A9 的显式推导条目入推导矩阵）。定谳材料 = M-4 |
| **N-2** | **玩家钉死机器配方**（手选模式）与**未钉死时的自动选配方顺序**。canonical A9 只写了自动分支「processing starts when cached inputs match ANY recipe of the set」，只字未提可以钉死 | 上游源码（`manualRecipeOnly` / `channelRecipes` / `sortRecipePlansByEfficiency`）；无 owner 定谳、无文书 | **全项目**：266 个 mandatory 实例各带一个固定 `operation_type`（本清点实测），这个建模本身就预设了配方可钉死。A9 的现行措辞与它**字面冲突** | 走 freeze-ritual，在 A9 补手选/自动两分支。定谳材料 = M-1 |
| **N-3** | **机器 → 内置配方集的归属数据**。canonical `recipes` 只有 `template`（占地形状），没有机型身份；从 canonical 读不出 `parts_maker` 与 `molding_bottle` 是不是同一台机器 | 上游 `src/registry/recipe-definition.ts` 的 `machineId` 字段 | T-1 的整套核对全靠回上游做；canonical 自身无法回答 A9 的适用范围 | 建议给 canonical `recipes` 每条补一个 `machine_id`（描述性、不进求解路径）。零风险，收益是让 A9 在 canonical 内部可判 |
| **N-4** | **owner 08-06 速率注记**：「借道汇流点 2s CD、双入满速竞争最坏减半（各 ≤0.5 件/tick）⇒ 共道段各流之和 ≤1 件/tick、残余 >1/2 的输出道不可被满速流借道」 | 公理提案 §5.2#2；记忆卡 | 主线程嫌疑一的整个判据；也是报告 §4 那个反例合法性的判据 | 随下批 canonical freeze-ritual（与 `rate_lemma_scope` 措辞修正同批）写入 A7 |
| **N-5** | **分流器语义**：空口不轮询、已连接出边严格对半；游标只在真搬运时旋转、停在失败侧；全出边不可搬 = 队头阻塞 | 公理提案设备参数表 + 补遗二（P-d owner 定谳「肯定对半，没连上的口不会轮询」） | **(b) 的两个 50/50 分流点**；D-1 的「一口一带」推论 | 随下批写入。这是 (b) 目前最干净的正面支撑，值得进冻结文本 |
| **N-6** | **制造机的输出缓冲参数**（1 槽 × 50）。⚠ **输入侧已在 canonical**：A7 原文有「one input buffer slot x 50 per ingredient, all same-side ports bound to one buffer group」——缺的**只有输出侧** | `MFG_SLOT_PARAMS_20260806.md` 表首列；公理提案参数表 | 见证里所有并联**出**道（crusher_sandleaf 的 3 条、crusher_buckwheat 与两台采种机的各 2 条） | 随下批把输出侧参数补进 A7，与 N-7 同条处理；写入时不要把未证的输出侧可加性（T-6）一起写成已定 |
| **N-7** | **同侧多出口并联抽货的可加性**（输出方向） | **无处**。`MFG_SLOT_PARAMS` 只论输入侧；A7 的多口满速断言只覆盖协议箱 | crusher_sandleaf / crusher_buckwheat / 两台采种机的满速产出 ⇒ `n_op` 全表 | 先跑 M-2 判例拿模拟器答案，再决定是补条款还是补前提声明 |
| **N-8** | **作物闭环的环内存料守恒与初态充料**（`cycle_internal` 商品的物质闭环性质，以及目标占空对应的存料量） | 无。A11 只裁了「首粒种子来自地图作物合法」，并明写「预置缓存的一般合法域仍未定谳（D9）」 | T-5：(b) 的两个作物环能否达到目标占空 | 先跑 M-5 拿模拟器答案；「预置缓存合法域」本身是 owner-only 裁决 |
| **N-9** | **「输出口只推不吞、过境安全」的机制陈述** | 记忆卡（08-06 公理终审 ④）；公理提案 §5.2#2。canonical `axiom_kernel.model_stricter_faces` 只记了**结论**（source-front 排他是确认过严面），没记机制 | 见证半速机器出口残道被借道的合法性 | 随下批与 N-4 同条写入 |

---

## 6. 两个点名嫌疑的核验细节

### 6.1 嫌疑一：合流点 2s CD 与双入竞争减半

**做法**：逐商品打开收据 `part_c_per_commodity`，比较 `producer_lanes` 与 `consumer_lanes`，凡产道数 > 耗道数即存在多对一（合流）。

**结果（19 种商品全表）**：

| 形态 | 商品数 | 商品 |
|---|---|---|
| 纯双射（无分流、无合流），`method: sorted_bijection` | **15** | blue_iron_block / blue_iron_ore / blue_iron_powder / buckwheat_powder / buckwheat_seed / dense_blue_iron_powder / dense_source_powder / fine_buckwheat_powder / sandleaf_powder / sandleaf_seed / source_ore / source_powder / **steel_block** / steel_bottle / steel_part |
| 合流 3→1，`method: cpsat` | **2** | qiaoyu_capsule、valley_battery |
| 必然分流（鸽巢），无指派 | **2** | buckwheat、sandleaf |

**主线程点名的「钢块 5 满 1 半的纯双射是否真的零合流」——是。** 收据 `part_c_per_commodity.steel_block.assignment` 是 17 条一一对应，17 个 `refinery_steel#*.out.0` 打到 17 个互不相同的耗口（`molding_bottle#0.in.0/.in.1` … `molding_bottle#5.in.0`、`parts_maker#0..5.in.0`），每条产道整条进入一个耗道、每个耗道恰收一条产道。**零分流、零合流。**

**两处合流的速率账**：

| 商品 | 三条入流 | 合计 | 逐流 vs「最坏减半」上限 1/2 | 合计 vs 带帽 1 |
|---|---|---|---|---|
| qiaoyu_capsule | 1/5、1/5、3/20 | **11/20 = 0.55** | 最大 0.2 ≤ 0.5 ✓ | 0.55 ≤ 1 ✓（45% 裕量） |
| valley_battery | 1/5、1/5、1/5 | **3/5 = 0.6** | 0.2 ≤ 0.5 ✓ | 0.6 ≤ 1 ✓（40% 裕量） |

**且这两处合流不是阶梯造成的**：`data/preprocessed/generic_io_requirements.json` 的 `required_generic_inputs` 是 `{qiaoyu_capsule: 1, valley_battery: 1}`（`ceil(总流量)`，两者总流量都不足 1 件/tick），所以 3 台产机并进 1 个核心口是**任何占空分配下都一样**的形态，均摊也是 3→1。合流数不是阶梯的代价。

**诚实注记：真正被 2s CD 咬到零裕量的不是见证，是报告 §4 的反例。** 报告 §4 用「grinder_fine_buckwheat 半速机的 fine_buckwheat_powder 出口残道 1/2 + molding_bottle 半速机的 steel_bottle 出口残道 1/2，和 = 1 ≤ 带容量」来打 canonical 速率引理。把 owner 的注记套上去：两条流要共道就得先过一个汇流点，该点每 2 秒只放一件（合计 ≤1 件/tick），双入满速竞争下**各 ≤0.5 件/tick**。两条 1/2 的流恰好各自等于 0.5、合计恰好等于 1——**算术合法，但两个不等式全部取等，零裕量**。加上汇流器仲裁本身是明写的公开欠账（D2，公理提案残余 5.2#12），这个反例是「刚好站得住」而不是「宽裕地站得住」。

这**不削弱**报告 §4 的结论（引理欠一条前件、方向 b 更强），因为报告的 40 对反例不止这一对，而且报告 §3 的定理 2 完全不依赖共道可行性——它只需要「存在两条速率之和 ≤ 带容量的不同商品段」这个**速率算术判据**，本来就没主张一定要真去共道。但**引用这个具体例子时应当带上「零裕量 + D2 未定谳」这个注**，别把它说成宽裕成立。

### 6.2 嫌疑二：A9 多配方

**做法**：canonical 只给 `template`（占地形状），读不出机型身份，所以回上游注册表 `IndustrialPlanner`（`7b946c16`）`src/registry/recipe-definition.ts` 的 `machineId` 字段，把 zmd 的 17 个 operation 逐个落到机型上，再列出该机型的**全部**内置配方，检查「只喂本 operation 的原料时，有没有第二条配方能匹配」。

**zmd 商品链 ↔ 上游 item 的对应**（由配方形状 + 链拓扑唯一确定，逐条 amounts 与 durationSeconds 精确吻合）：
`blue_iron_ore = item_iron_ore` → `blue_iron_block = item_iron_nugget` → `blue_iron_powder = item_iron_powder` → `dense_blue_iron_powder = item_iron_enr_powder` → `steel_block = item_iron_enr` → `steel_bottle = item_iron_enr_bottle` / `steel_part = item_iron_enr_cmpt`；`sandleaf = item_plant_moss_3`、`sandleaf_powder = item_plant_moss_powder_3`；`source_ore = item_originium_ore` → `source_powder = item_originium_powder` → `dense_source_powder = item_originium_enr_powder`；`valley_battery = item_proc_battery_3`（`r_packaging_battery_from_iron_cmpt_and_originium_enr_powder_basic`，`{iron_enr_cmpt: 10, originium_enr_powder: 15}` 与 canonical `packaging_battery` 的 `{steel_part: 10, dense_source_powder: 15}` 逐数吻合）。buckwheat 族落在 `item_plant_moss_1` 或 `item_plant_moss_2` 上（两者结构同构，不影响任何结论）。

**逐机型核对结果**：

| zmd operation | 上游机型 | 该机型配方数 | 喂它的商品 | 可匹配的配方数 | 其余配方为什么匹配不上 |
|---|---|---|---|---|---|
| `refinery_blue_iron` | `furnance_1` | 25 | `item_iron_ore` | **1** | 25 条里只有 `r_furnace_iron_nugget_from_iron_ore_basic` 吃铁矿 |
| `refinery_steel` | `furnance_1` | 25 | `item_iron_enr_powder` | **1** | 只有 `r_furnace_iron_enr_from_iron_enr_powder_basic` |
| `crusher_blue_iron` | `grinder_1` | 12 | `item_iron_nugget` | **1** | 只有 `r_crusher_iron_powder_from_iron_nugget_basic` |
| `crusher_source` | `grinder_1` | 12 | `item_originium_ore` | **1** | 只有 `r_crusher_originium_powder_basic` |
| `crusher_sandleaf` | `grinder_1` | 12 | `item_plant_moss_3` | **1** | 只有 `r_crusher_moss_powder_from_moss_basic`（唯一的 1→3） |
| `crusher_buckwheat` | `grinder_1` | 12 | `item_plant_moss_1/2` | **1** | 其余 11 条各吃不同植物/矿物 |
| `grinder_dense_blue_iron` | `thickener_1` | 7 | `{iron_powder, moss_powder_3}` | **1** | 7 条都要 moss_powder_3 + 一种**不同的**主粉（crystal / originium / quartz / carbon / moss_powder_1 / moss_powder_2） |
| `grinder_dense_source` | `thickener_1` | 7 | `{originium_powder, moss_powder_3}` | **1** | 同上 |
| `grinder_fine_buckwheat` | `thickener_1` | 7 | `{moss_powder_1, moss_powder_3}` | **1** | 同上 |
| **`molding_bottle`** | **`shaper_1`** | **8** | **`item_iron_enr`** | **1** | 8 条里只有 `r_shaper_iron_enr_bottle_from_iron_enr_basic` 吃 `item_iron_enr`；其余要 copper_nugget / quartz_glass / quartz_enr / iron_nugget / copper_enr / xiranite_powder / xiranite_enr_powder，**本产线一件都没有**。而且这唯一一条要 **2 件** ⇒ 半速机缓存里握着 1 件时**没有任何配方可开工，只能等**。 |
| **`parts_maker`** | **`cmpt_mc_1`** | **9** | **`item_iron_enr`** | **1** | 只有 `r_component_iron_enr_cmpt_from_iron_enr_basic`。**与制瓶机是两台不同的机器** |
| `seed_collector_buckwheat` | `seedcol_1` | 10 | 对应作物 | **1** | 10 条各对应一种植物 |
| `seed_collector_sandleaf` | `seedcol_1` | 10 | `item_plant_moss_3` | **1** | 只有 `r_seedcol_moss_seed_from_moss_basic` |
| `planter_buckwheat` | `planter_1` | 4 | 对应种子 | **1** | 4 条各对应一种种子 |
| `planter_sandleaf` | `planter_1` | 4 | `item_plant_moss_seed_3` | **1** | 只有 `r_planter_moss_from_moss_seed_basic` |
| `packaging_battery` | `tools_asm_mc_1` | 14 | `{iron_enr_cmpt, originium_enr_powder}` | **1** | 另两条也用 originium_enr_powder，但配对的是 xiranite_poly / xiranite_powder，本产线没有 |
| `filling_capsule` | `filling_pd_mc_1` | 6 | `{iron_enr_bottle, moss_enr_powder_1 或 _2}` | **1** | 6 条按 (瓶型 × 粉型) 组合，本产线只有一种粉型在场 |

**结论：17 / 17 全部唯一可匹配。** A9 的多配方条款在本实例上**不产生任何行为分歧**，(a) 的饥饿节流与 (b) 的阶梯见证都不受它影响。这个结论**不依赖**「配方可以钉死」——即使机器处于自动模式，可选集合也只有一个元素，`sortRecipePlansByEfficiency` 的排序（产物总量降序 → 原料总量升序 → id 升序）无从发挥。

**顺带的正面收获**：制瓶机唯一那条配方要 **2 件**钢块，而同机型没有任何「1 件即可开工」的配方——这正是 owner 亲自举的「6 台总 duty 5.5 摊成 5 台满速 + 1 台半速」在机制层能成立的原因：半速那台就是**长期停在「握着 1 件、等第 2 件」**的状态，而这个状态在游戏机制里是一个稳定的合法状态，不是一个会被别的配方抢走的空档。

**残留风险已在 T-1 记明**：排除依据是实例特定的（其它配方的原料在本产线不存在），商品集一变要整套重做。

---

## 7. 诚实边界：本清点没覆盖到的东西

1. **几何层完全没碰。** 与报告 §6 同一条边界：本文所有 SUPPORTS 判定都是「规则不禁止」或「规则算术允许」，不是「70×70 上真摆得下」。拓扑、占地、跨层交叉、供电覆盖的实际布局全部未验。特别是 F-1 记的两处零裕量（crusher_sandleaf 满速要恰好 3 个出口；52 源头槽恰好承 34+18）在几何层可能是硬约束。

2. **上游注册表不是权威，且两份快照不一致。** §6.2 的核对用的是 `/home/zhuran24/upstream/IndustrialPlanner`（`7b946c16`）的当前 `recipe-definition.ts`。仓内还有一份 `src/adapters/industrial_planner/item_registry.json`（自称 `IndustrialPlanner-2` 快照，2026-03-28 生成，167 条配方），两份的配方数与机型集合**不同**（例如 `shaper_1` 在旧快照里 5 条、在当前上游 8 条）。本清点两份都查了、结论一致（钢块相关的配方归属在两份里都是 shaper vs cmpt 分开），但按 owner 的权威序（**owner 游戏定谳 > 模拟器规则层 > canonical 文本 > 文书转述**），§6.2 的整套结论是**模拟器规则层**级别，**没有 owner 游戏侧定谳**。M-1 判例是它的动态复核，游戏侧终审仍是 owner-only。

3. **zmd 商品 ↔ 上游 item 的对应是我在本清点里现推的**，依据是配方 amounts + durationSeconds + 链拓扑的唯一嵌入，没有找到仓内现成的对照表（`src/adapters/industrial_planner/` 下的语义映射我没有逐层展开验证）。buckwheat 落在 `moss_1` 还是 `moss_2` 我**没有分辨出来**——两者在配方结构上完全同构，对本文任何结论无影响，但这是一个我明确没做完的点。

4. **动力学一概没算。** T-4 / T-5 指出的收敛性、启动瞬态、闭环充料，我只做了物质守恒的静态账（产种 11 = 耗种 11），没有做任何时序仿真。M-5 判例是补这块的，本清点没跑。

5. **没有跑任何模拟器判例。** §4 的七个判例全部是设计，一个都没执行。M-1 有一条**静态源码级预答**（读 `runtime-slot-access.ts` / `topology-compiler.ts` / `recipe-channel-behavior.ts` 得出「可切换机型缺省手选」），其余六个是纯设计。

6. **模型可表达性没查。** (b) 在游戏机制层可实现，不等于**官方 routing/binding 模型能表达它**。谓词 (4)「端口精确计数」对逐机车道数的处理、`generic_input_slots_by_operation` 的等式/不等式语义，我只查到 `required_generic_inputs` 是聚合 `ceil`（这足以说明 §6.1 那两处合流是模型侧强制的），**没有**追到 binding 对 recipe-backed 机器逐台口数的约束形态。这是一条我知道存在、但本轮没走完的线。

7. **`semantics` 各条目的 `axiom_derivation` 反向链没有逐条复核。** 我读了全部原文并按内容判定，但没有逐条验证「某条 semantics 声称由 A-x 推出」这个推导本身成立。矛盾猎人席的活，不在本轮范围。

8. **只用了三个规则源。** 主线程指定的三源（canonical / 公理系文书 / 记忆卡）我逐字过完了，另外主动加了 `MFG_SLOT_PARAMS`、`PORT_SEMANTICS_REVERDICT_A`、`rules_audit_20260718/00`、`preprocess_plan.json` 与三份 preprocessed 工件。`VERIFICATION_ANNEX_20260806.md`（57KB，三席验证意见原文）与 `DOC_MEMORY_FIXLIST_20260806.md` **我没有读**——里面可能有本轮该收的规则细节。这是本清点最大的一块已知未覆盖面。

9. **owner 口述规则的引用等级。** 本文引用的 owner 裁定全部转引自记忆卡与公理提案，没有回到原始对话记录。公理提案 §0 自己写着「owner 明言历史对账『每次都会落下东西』——本文任何『已穷尽』口吻按此打折」，这条打折同样适用于本文书。

---
**§7.3 悬案销账（2026-08-07 晚，sim-blind-packager 席）**：buckwheat = `item_plant_moss_1`（荞花）已定——判据非配方结构（确同构）而是 i18n 显示名与终产物链闭合（moss_1=荞花 → `item_bottled_rec_hp_3`=精选荞愈胶囊 ↔ qiaoyu_capsule；moss_2=柑实 → 罐头链）。sandleaf = `item_plant_moss_3`（砂叶）、valley_battery = `item_proc_battery_3` 同时确认。T-1 核对自此有确定商品身份锚。
