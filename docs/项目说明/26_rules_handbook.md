# 26 — 规则手册：游戏规则的现行理解

> **本页为无时态文档**：全篇现在时、就地更新。历史考古走 `git log` / `git blame`、[HISTORY](HISTORY.md) 与冻结快照；**凡改动本页所述稳定规则解释的批，必须同批更新本页**。
> 本页**零权威**——只做总结、指路与交叉引用。任何承重用途（外审、放开语义、写守卫、下结论）都必须回到本页指出的权威物读原文。

---

## 0. 怎么用这页

### 0.1 权威分层

| 层 | 权威物 | 管什么 |
|---|---|---|
| 1 | `PROJECT_LOCK.md` | release 边界、scope 注解、`F-*`/`PCR-*`/`CUT-*` fail-closed 条款 |
| 1' | `docs/项目说明/01_overview.md` §1.1（六谓词外延）、§1.2（`CERTIFIED` 证什么） | **谓词外延本身**。`PROJECT_LOCK.md` §1A 自己写明：若与 `01_overview` 的谓词外延冲突，以那两节为准、§1A 须 re-sync（旧节号漂移的审计记录见 [`../history/status/27_status_dashboard_20260803.md`](../history/status/27_status_dashboard_20260803.md) §9；现行 §1.3 已收束为 soundness 与 authority 链） |
| 2 | `rules/canonical_rules.json`（字节级冻结件） | admissibility、游戏语义裁决条款、`semantics.axiom_kernel` 公理系 |
| 3 | `rules/preprocess_plan.json`（冻结件） | generic-input 合同的槽位声明（`utility_operations`） |
| 4 | [`REASONING_METHOD.md`](REASONING_METHOD.md) | 归属判据 / 方法论操作卡。稳定方法就地维护；历史版本与 owner 台账从 [HISTORY](HISTORY.md) 和冻结快照考古 |
| — | 本页 | 索引 |

### 0.2 三条引用纪律（违反过、都留了病例）

1. **记忆卡与收据不是权威**。它们是推导史与裁决转述，天然丢失败分支；承重条款一律指到 `rules/canonical_rules.json` 的具体键、`PROJECT_LOCK.md` 的 `F-*` 编号或 `docs/项目说明/01_overview.md` 的节号。病例见 `sibling-line-receipt-paraphrase-not-evidence`（文件记忆层）。
2. **转来的数字当"待核"而非"已知"，并回原文查它是界还是例子**。canonical 里就有明写 "an example, not a bound" 的条款（`semantics.protocol_storage_box_wireless.slot_count_clause`）。见 `verify-premises-against-current-canonical-not-your-tree`。
3. **核裁决级前提回 main 当前版**：`git show main:rules/canonical_rules.json`，不读长活分支工作树里那份——canonical 是被 hash 钉死的冻结件，落后的分支对着旧版施工不会有任何测试变红。

### 0.3 canonical 的自述权威顺序

`semantics.axiom_kernel.scope_premises` 写死了裁决顺位：**owner 游戏内定谳 > 模拟器规则层 > canonical 文本 > 文档转述**。本页属最后一档。

---

## 1. 版本口径与外部参照

- **游戏版本口径 = 1.1（valley-4 图）**。权威：`rules/canonical_rules.json` → `semantics.axiom_kernel.scope_premises`。
  （`metadata.version` 是本规则文件自身的版本号，不是游戏版本，别混。）
- **所有"永久堵死"类结论都预设无玩家运行时干预**（玩家可手动清中毒槽）——同出 `scope_premises`。
- **两个上游参照**：`JamboChen/endfield-calc`（数值）、`hsyhhssyy/IndustrialPlanner`（几何 / 可执行模拟器）。模拟器审计基线 commit 记在 `scope_premises` 里，**引用记 commit 不记 tag**。
- **对账 SOP**：先把 canonical 条款或模型行为翻成模拟器可执行的判例跑一遍，**分歧点才升级为"单独研究 + owner 游戏实测定谳"**。上游只提供候选规则，owner 实测才算数。出处：文件记忆卡 `canonical-audit-simulator-first`、`rules-audit-20260718`。
- **模拟器的边界**：规则层（方向 / 分流 / 指针 / 混流）可信；**传输层是 rate/slot 抽象**，不模拟单件运动，带速与间距一类的量拿不到。
- **IP `outerRing` 子系统整体黑名单**（两版参数自相矛盾且与 owner 实测冲突）。出处：`rules-audit-20260718`。
- **网格与时基**：70×70（`globals.grid`）；1 tick = 2.0 s、带容量 1 件/tick、单口吞吐上限 1 件/tick（`globals.time` / `globals.logistics`）；商品 19 种（`commodity_metadata`）。

---

## 2. 认证命题的边界（一屏）

- `CERTIFIED` **恰好且仅仅**证明六个谓词 + `max_lex(area, min_side)` 下的 lex 最优性 + 发布材料同源。谓词外延与命题文本读 `docs/项目说明/01_overview.md` §1.1 / §1.2，**不在本页复述**。
- **吞吐 / 带宽 / 离散容量流明确 OUT-OF-SCOPE**：`PROJECT_LOCK.md` §1A B 块（B-1/B-3/B-4）。`src/models/flow_subproblem.py` 是连续 LP 诊断器，不门控、不产 exact-safe cut。
- **`canonical_rules.json` 的整个 `semantics` 节是描述性的**，任何求解路径都不消费它（`semantics._note` 明写）。改它只改本文件的冻结 hash（freeze-ritual），不改派生的 preprocess 工件。
- 因此：**规则理解正确 ≠ 谓词改变**。语义节的作用是让证明受众和外审能对齐"我们在什么游戏语义下作断言"。

---

## 3. 目标空矩形：admissibility 与"空"的语义

| 项 | 现行读法 | 权威 |
|---|---|---|
| 目标 | `max_lex(area(R), min_side(R))` | `globals.empty_rectangle.objective`；`01_overview` §1.1 |
| `min_side >= 6` | **候选 admissibility floor**，不是第二目标的替代品、不是 tie-break | `globals.empty_rectangle.min_side_admissibility`；`01_overview` §1.1 |
| "空"的语义 | **什么都不能有**：设施机身、电线杆、传送带、十字 / 暗管等一切物流件均禁；完全净地 | `globals.empty_rectangle.emptiness`（`no_occupant_of_any_kind`）+ `emptiness_adjudication` |
| 挂在哪个谓词 | **甲案**：严格性由 (1)∧(5) 联合保证——(1) 排设施机身，(5) 要求所有 route cell ∈ G∖R | `01_overview` §1.1 谓词 (1)(5)；`PROJECT_LOCK.md` §1A |
| 实现锚点 | `src/search/benders_loop.py:6263` `_strict_ghost_occupancy`（解不出即 UNKNOWN，绝不退回宽松），调用点 `src/search/benders_loop.py:6687` | 源码（本页作者亲手核过） |

**方向安全不对称（引用历史结论时必查）**：在宽松口径下证出的**负结果与上界仍然有效**；**正向见证会被严格口径杀掉**。因此任何正向见证的验收必须按严格口径重查孔内物流件落位。出处：文件记忆卡 `empty-rectangle-strict-semantics`。

> 严格性属 `semantics.axiom_kernel.ruling_level_inputs` 登记的**两条不可从公理推出的 owner 裁决**之一（另一条是仓库桥排除）。

---

## 4. 口岸三分法（本手册的核心一节）

**带级混流是合法的**——同一条实体带 / 十字通道可以交错承载多种商品。限制**不在带上，在口上**：一段混流能不能**合法终止**，取决于终点的口类。权威：`semantics.mixed_commodity_flow` 及其 `terminal_clause`；公理支撑 `semantics.axiom_kernel.axioms`（A1 边守恒无回退 / A2 内容过滤点 / A3 缓存槽动态定型 / A9 进料配方盲）。

| 口类 | 现行判据（一句） | 混流终止安全性 | canonical 键 |
|---|---|---|---|
| **(1) 有线仓储口** — `protocol_core` 的 14 个实体输入，本模型里**唯一**的有线仓库输入侧 | 按商品在仓库侧逐类型开槽，容量实际不可达 | **对「已在仓库注册槽位的商品」（warehouse-registered）无限混吃安全**——canonical 原文的限定词，不是无条件全商品。**当前 19 种商品全部在册**（仓库对每种商品有编译期预锁槽，公理 A4），故该前提在本项目里**真空满足**；未来若出现未注册商品，这条不自动成立 | `mixed_commodity_flow.terminal_clause` class (1)；公理 A4 |
| **(2) 协议箱** | **有界吸收体，但界是执行不变量、不是静态计数**：6 个**独立单槽组**、每组 1 槽容量 **50**（`cache_parameters`），一槽一种商品，**同一商品可占多槽**（fill-first：占满一组才开下一组）。一件到货能不能落地，取决于**有没有一个可用组**——已定型到该商品且未满，或仍空着可动态定型。所以**「占了几槽」和「有几种商品」都不是完整的堵塞判据**：`occupied ≠ full`。对一件没有任何组能接的商品，堵塞**当且仅当 6 槽全占，与涉及多少种商品无关**（界写在**槽数**，刻意不写在商品种类数）。断电则 10 s 冲刷不跑、占用槽永不清空 | **不是无条件安全**：必须另行论证**逐次到货接收不变量**——每次落地之前至少有一个可用且未满的组。class (2) 身份本身、商品种类数，都不构成清偿。**本冻结实例已 discharge**（owner 2026-08-07：每周期 ≤ 15 件 ≪ 300 静态容量、纯流种类 ≤ 3 < 6 组、每周期清零、≤ 10 s 内瞬时滞留必散、永不中毒），故箱在本实例里是合法混流终点。⚠ **这是实例级 discharge，不是类级规则改变**——别的布局必须自己清偿 | `protocol_storage_box_wireless.slot_count_clause`（含 `cache_parameters` / `blocking_reachability_note`）；实例级 discharge 记在 `mixed_commodity_flow.terminal_clause` |
| **(3) 机器口** | **无内容选择权**，进料是配方盲的。错货落进缓存槽后没有消耗通道，**永久占死**（边守恒 + 无回退） | **不安全** | `terminal_clause` class (3)；公理 A9 / A1 / A3 |

**终端条款一句话**：一段混流**无条件安全只有 class (1) 一处**；终止于 class (2) 要另行清偿逐次到货接收不变量（本冻结实例已清偿，别的布局不自动继承）；终止于 class (3) 不安全。

**三分法的定义域**：它**只覆盖被建模的物理接收口**。只出不进的口、以及压根没有物理输入口的设施，都不在这个划分里——**边界仓储口就是这一类**（0 进 1 出的仓库取货源，`rules/preprocess_plan.json` 的 `boundary_io`），**不是** class (1) 终端。所以 class (1) 在本模型里只有协议核心的 14 个实体输入一家。

**两个常被走私混淆的行为，严格区分**：

- **裸机器口** = 错货**站住等待**，等缓存空出后**照单全收**；
- **限制口（物品准入口）** = **瞬时拒收、留在上游**。

拿后者的行为去解释前者是历史上反复发生的走私。出处：文件记忆卡 `machine-input-no-selectivity-pollution`。

**模型侧的对应**：certified 模型的 **sink-front 单商品排他** 是 class (3) 的**正确保守编码**（不是"模型比游戏严"的错误面）；登记在 `semantics.axiom_kernel.model_stricter_faces`，定谳文书 `docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md`。

### 4.1 ⚠ 用类别之前先算参数（尺子边界同在此处）

**分类标签是旧推理语境下缓存的结论，不携带"界在什么参数下可达"。** 引用任何类别前必须回原始参数拼一次账。样板：协议箱在本产线里的**堵塞判据物理不可达**——

- 格数账（**条件式**；两条前提已于 2026-08-08 批入册 `protocol_storage_box_wireless.slot_count_clause.cache_parameters`——`slot_capacity: 50` / `group_count: 6`，fill-first 与落位顺序写在同一个 `statement` 里）：**在 fill-first（同种商品占满一槽后才开新槽）＋ 单槽容量 50 两条前提下**，箱 3 个实体输入口（`protocol_storage_box_wireless.statement`）同时最多喂 3 种商品 ⇒ 最多占 3 槽 < 6 槽 ⇒ 6 槽全占的堵塞判据到不了。
  **⚠ 前提缺一不可**：条款给的上界是 **6 槽不是 3 槽**——`slot_count_clause` 与公理 A3 明写「**同一商品可占多槽**、界写在槽数」，所以「3 种商品 ⇒ 最多占 3 槽」**推不出来**，必须显式挂上 fill-first 前提。
  **⚠ 这条腿还压着一个模型面**：「3 口 ⇒ 最多 3 种」用的是模型的 **destination-front 单商品排他**（`model_stricter_faces` 第 (1) 项）。因此本腿的定性是 **current-model theorem，不是关于已定谳游戏语义的断言**；按 `model_stricter_faces_usage_rule`，它必须点名这个依赖，且该面一旦解锁就作废重证。canonical 原文：`slot_count_clause.blocking_reachability_note` 的 leg (a) 与 Status 段。
  **⚠ 另有一条不依赖该面的腿**（owner 2026-08-07）：本实例能到仓储线的商品**只有 2 种终品**，而通往 6 槽全占的唯一理论路径是「一条混流带在 10 s 窗内送来 ≥ 7 种」——这个前提在本实例里**根本凑不出来**。这条腿不碰模型面，格数账因此不再唯一依赖过严面 (1)。
  【待核】旧文写的「纯流喂养」引自速率引理，而 `semantics.rate_lemma_scope` 的**两条前件（满产 + 最小道数分配约定）在本账里未清偿**，故本条不再以它为前提，只保留上面的显式前提。
- 件数账（单槽容量参数同样已入册）：3 口 × 1 件/2 s（`globals.logistics.belt_capacity_per_tick` + `globals.time.tick_interval_seconds`）× 10 s 冲刷周期 ⇒ 每周期进货 ≤ 15 件。**到货率这一步是无条件的**；说它「远小于缓存」那一步是拿 15 去比 **6 × 50 = 300** 的静态容量（连单槽 50 都不到），所以这一步依赖已登记的容量参数。每周期清零。

**尺子的边界**：可达性审计**不能用来删 fail-closed 守卫**。判别一句话——**问这条限制的危险条件由谁保证不可达**：由物理 / 冻结数据保证的，限制在描述不存在的东西 ⇒ 可删；**由这条限制自己保证的，它就是那个保证，删了保证就没了** ⇒ 必留。出处：文件记忆卡 `classification-labels-hide-parameters`。

---

## 5. front 语义（口前带子格）

**现行读法**：候选池里存的端口坐标**本身就是** front / 带子格 = **机身外第 1 格**；物理口坐在相邻的机身边缘格上。使用中的口要求**那一格**能放带（在图内、未被机身占）。

| 细则 | 现行读法 |
|---|---|
| 表示 | **identity 语义**，绝不是 `port + DIR_DELTA`（推到体外第 2 格 = 已连根拔除的错位 bug） |
| 什么堵口 | **设施机身堵，电线杆算机身**；**带不堵** |
| 带 / 带同格 | 由十字交叉条款单独裁决：**只允许双方直穿且互相垂直**；front 格上有拐弯带或同轴平行外来带 ⇒ 口被堵 |
| 1 格带 | 合法 |
| 两个相对口 | 可以共享中间那一格 |
| 未连接的口 | 合法闲置，**不占用它的 front 格** |
| 机身间距 | **没有 body-to-body clearance**，机身可以相邻；但"零格交接"不可行（这是定理，不是公理） |
| 方向纪律 | 普通 route state 不得逆向送进 source front、也不得逆向从 sink front 取货（终端豁免键在 stored 格上） |

**权威**：`semantics.machine_min_clearance`（含 `axiom_derivation`：公理 A5a/A5d）+ `PROJECT_LOCK.md:388` `F-RT-R3-01`（**已 inverted**）+ `F-FRONT-INC-01` addendum。
**代码 SSOT**（新的 front 消费点必须走它们，本页作者亲手核过）：

- `src/models/routing_subproblem.py:160` `_port_front_cell`
- `src/placement/placement_generator.py:79` `get_port_front_cell`

**已知残留（不可达，但属完整性欠账）**：`src/models/patch_routing_core.py:569` `_add_port_adherence` 内部仍按 `DIR_DELTA` 推 front（`fx, fy = px + dx, py + dy`）。当前被 closed allowlist 挡在可达面外，**挂 PCR / pose-bool promotion 的前置硬阻断**。已核实。教训：**事故修复批的作用域 = 当时的可达面**，disabled / diagnostic 面不会被测试逼出来，promotion 前必须重扫同族语义。

历史见 `docs/research/front_offset_incident_20260718/`（事故普查与修复批全档）。

---

## 6. generic-input 合同（实体端口建模）

**槽位声明的权威 = `rules/preprocess_plan.json` → `utility_operations`（冻结件）**：

| operation | 设施 | generic 输入槽 | generic 输出槽 |
|---|---|---|---|
| `protocol_core` | 中枢 | **14** | 6 |
| `box_sink` | 协议箱 | **3** | **0** |
| `boundary_io` | 边界仓储口 | 0 | 1 |
| `power_supply` | 电线杆 | 0 | 0 |

- 协议箱**实体上**有 3 进 3 出（与 `manufacturing_3x3` 同款口形、四朝向、需电），本产线里输出口**合法闲置**，故 `box_sink` 的 generic 输出槽登记为 0；"无线"只存在于**箱 → 仓库**这一段，产线 → 箱必须用带接实体进口。权威：`semantics.protocol_storage_box_wireless`（其 `supersedes` 字段点名退役了"无口黑洞"读法）。
- **成品必须从 producer 的 output front 路由到 provider 的实体 input front**；下界同时识别 provider operation 与**实际实例**，不得给未实例化的模板记容量。

### 6.1 协议箱下界为 0 及其前提

**provider-aware / instance-aware 下界规则**（`PROJECT_LOCK.md` `F-GM-Q3-01`）：先算 gross 正需求，**再减去 mandatory provider 实例按原子 operation map 提供的实体 generic-input 容量**，只有残余需求才折算成可选 `protocol_storage_box`（每箱 `box_sink=3` 槽）。

**在现行冻结项目下**：gross 需求 = 2，mandatory `protocol_core` 贡献 1 × 14，残余 = 0，**因此协议箱下界 = 0，绝不是 `ceil(2/3)=1`**。

同段还挂着四条派生义务（`R3-A` 残余池仍须构造、`R4-A` 固定槽须带模板全角色语义、`R5-A` 空家族表须整体跳过而非发空表）与 V94 终端箱最小性支配义务，**本页不复述**，改这块之前逐条读原文。

**exact session 纪律**：从**同一份 hash-bound 的 `preprocess_plan.json` snapshot** 解析、传递、比较完整的 `generic_input_slots_by_operation` map；禁止退回 box-only 标量，禁止中途重读。权威边界见 `PROJECT_LOCK.md` 的 `F-GM-Q3-01`，操作入口见 [`../AGENT_OPERATIONS.md`](../AGENT_OPERATIONS.md) §5。

---

## 7. 其他现行裁决速查

| 主题 | 现行读法（一句） | 权威键 |
|---|---|---|
| 边界口放置 | 左 / 下边界带**包含 (0,0) 角**；两种基线位姿都容许角锚点。生成期**不得**预删互斥的角位姿——互斥由 master 的格独占下游强制，不靠剪候选池 | `semantics.boundary_placement`（生成器 `src/placement/placement_generator.py` 的 `gen_boundary_ports`） |
| 十字交叉 | `ground`/`elevated` 双层是**单格十字件**（两条互相垂直的直通道共享一格）的**建模表示**，没有物理坡道 / 高差；两通道可载不同商品但必须垂直；桥不能拐弯，也不能与同格的非直件共存 | `semantics.routing_cross_junction` |
| 连通性量词（谓词 5） | 按商品：**每个 sink front 可由某个 source front 到达**，且**每个 source front 能到达某个 sink front**。**允许多个互不相连的同商品连通岛**；既不是单一生成分量要求，也不是吞吐保证 | `semantics.connectivity_quantifier` |
| 仓库桥 | 中间产物经箱 / 中枢进仓库后能从中枢出口和边界取货口再出来——**游戏机制真实，但被排除为合法布线结构**（会挤占蓝铁 / 源石的输出产能）。**这条绑定在冻结的产量目标上，产量目标一变必须重裁** | `semantics.warehouse_bridge_exclusion`；属 `axiom_kernel.ruling_level_inputs` |
| 供电 | 中枢**就是**基地电源、自身无覆盖范围也不需供电；电线杆无条件从中枢取电并广播；发电在别的基地（电力预算外部化）。故"受电设施须被某根杆的覆盖模板盖住"与游戏机制效果等价，**不建模任何连线约束** | `semantics.power_source_note` |
| 供电覆盖几何 | 2×2 杆锚点，12×12 轴对齐方形覆盖（按 `power_coverage_radius` 展开、裁到网格内）；覆盖 = **相交**语义（机身与覆盖区 ≥1 格重叠即算），**不是包含** | `semantics.power_coverage_stencil`；`01_overview` §1.1 谓词 (6) |
| 物品准入口（限制口） | 游戏里存在，**刻意不建模——这半句在现役 main 下仍成立**：几何上等价于一条直带（能放它的格就能放直带）。**2026-08-08 批已把该条款的 authority 改写成条件式**：「无候选池或谓词消费它」不再是常驻权威，而是**当下的偶然状态**——任何"禁止只有筛选口才能实现的事"的谓词都算消费它，接入之日 authority **当场失效**、豁免必须连同 statement 重裁（canonical `item_admission_port_exclusion.authority`）。同批已把这个省略面登记进 `model_stricter_faces` **第 (6) 项**（本批把它从无条件 safe-exclusion 定理**降格**为显式的认证 scope 限制，并写明 de-mix 禁令不得再拿本条款当正当性来源）。⚠ 另，**「建模必要性 = 零」的三腿重述已动摇**：速率腿缺占空前件（见下行速率引理两前件纪律）、分拣终点腿仅在「两种货可去同一终端」时成立（模拟器判例：异终端分拣不可替代，且分拣零吞吐税），仅存仓库口混吃一腿。worktree 中未接入的 de-mix 禁令是**第一个消费该豁免的谓词**，接入即踩断 authority 前提——处置 owner 已定（先放着＝维持现状，随系统性梳理/墙审计首轮回桌，准入口为种子案例） | `semantics.item_admission_port_exclusion`；判例 `.artifacts/gpt_pro_review_batch_20260807/verdict/fen2/SIM_JUDGE_D1.md`；决策页同目录 `ADJUDICATION_fen2.md` B1 |
| 速率引理 | **带两条前件**：(i) 冻结产量目标下满产；(ii) 最小道数分配约定。**缺前件不得引用**。在前件下：中间产物的每道残余速率两两之和 > 1 ⇒ 中间产物不得共道；**唯一在速率上合法的混流域 = 终品进有线仓储口的终端段** | `semantics.rate_lemma_scope`（含 `usage_rule`：任何把 front 排他读成 WLOG 而非"仅保守"的叙事升格，必须引用本条并逐条清偿两前件） |
| 端口商品域 | binding 模型是**槽—单商品**制：每个端口槽恰载一种商品。裁决过的游戏语义允许有线仓储口同时吸多种，模型表达不了——这条 scope 声明就是为了让这个表达力缺口不被静默读成完全一般性 | `semantics.port_commodity_scope` |
| 公理系 | `semantics` 全节的语义地基 = **11 条公理 A1–A11**；节内其他条目都是其上的**定理或 owner 裁决**，各自带 `axiom_derivation` 反指回来。公理不改变任何认证谓词 | `semantics.axiom_kernel.axioms`；存档全文 `docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md` |
| 不可从公理推出的两条 | 空矩形严格性、仓库桥排除——**裁决级输入** | `semantics.axiom_kernel.ruling_level_inputs` |

---

## 8. `model_stricter_faces` = 完整性欠账台账

**是什么**：`rules/canonical_rules.json` → `semantics.axiom_kernel.model_stricter_faces` 是**唯一**登记处，专记"certified 模型比裁决过的游戏语义**更严**"的面。在册各条都是保守的、都不 unsound，但**按定义是待放开清单**。**2026-08-08 批起在册 6 项**（此前 4 项，新增第 (5) 项 `warehouse_bridge_exclusion`、第 (6) 项准入口省略面），且各项已编号。

**同批新增两条兄弟键，引用前必读**：

- `model_stricter_faces_usage_rule`——这个台账是**模型欠账与认证 scope 的账本，不是游戏语义前提的来源**。在册面可以拿来描述当前受限模型，**但不得用来证明关于游戏语义的定理，也不得用来支撑全游戏 lex 最优性主张**。任何依赖在册面的 current-model theorem **必须点名这个依赖**，且该面一解锁就作废重证（样板见 §4.1 格数账 leg (a)）。
- `model_stricter_faces_completeness`——本台账被要求对"已知会移除某条游戏行为的模型限制"**穷尽**。**不在册 ≠ 等价**；新发现的面必须**先登记，再**用于 certified 求解或最优性叙事。

**怎么查**（本页刻意不抄在册条目——它会随放开批变动）：

```bash
python3 -c "import json;print(json.load(open('rules/canonical_rules.json'))['semantics']['axiom_kernel']['model_stricter_faces'])"
```

**三条纪律**：

1. **别把一个放开的 soundness 押在过严面上**。押上去等于埋雷：将来有人做"对齐游戏语义"的批去松掉那条保守面，被押的放开会**静默**失去正当性——没有任何测试会红，因为两处改动分属不同批、互不引用。换支点优先找**构造性**的（只依赖冻结工件 + 少量代码事实，不依赖"模型碰巧更严"）。出处：文件记忆卡 `relaxation-built-on-stricter-face-is-a-trap`。
2. **反过来做放松批时，先查这条面有没有被别人当支点**。
3. **每个 guard / 限制批的验收必答两问**：堵了哪些孔？有没有把合法能力关在门外？新增过严面必须当场登记进本台账。见 §9.1。

**一条实例值得单记**：routing 复验多加的 no-orphan / selected-source-reaches-sink 条件**不在**谓词 5 的量词里（`semantics.connectivity_quantifier` 不含它们），是模型自加的保守面——复验实现在 `src/models/routing_subproblem.py:1710` `_validate_selected_route_connectivity`。

---

## 9. 两条 §0b 级公理与判据体系指路

### 9.1 双向保真公理

**判据句**：**堵孔（防纳伪）与把所有合法规则放进模型（防拒真）同等重要。** 本项目认证的是 `max_lex` **全局最优**，证书说的是"不存在更好的解"；模型比游戏语义严时，被关在门外的合法布局若含真最优，证书在游戏真语义下**为假**——与放进非法解同等 unsound。

四象限：过严 + 见证 = 安全；**过严 + INFEASIBLE / 最优性证明 = 假证书**；过松 + 见证 = 假见证；过松 + INFEASIBLE = 安全。**"过严 = 保守 = 安全"只在见证半边成立。**

守卫文化的报警通道天然只装在纳伪侧——过严限制只产生"缺失的答案"、不产生"错误的答案"，**永不自曝**，必须主动审计。**"墙审计" = "孔审计"的对偶**：周期性从公理系枚举游戏合法能力、逐条核模型的可表达性。

出处：文件记忆卡 `bidirectional-fidelity-axiom`；迁移前台账登记见 [冻结 roadmap 快照](../history/status/00_master_roadmap_pre_phase3_20260812.md) 的 `§0a`。

### 9.2 规则派生闭包公理

**判据句**：**规则系统是生成式的**——基础规则组合出派生规则、派生再与基础及其他派生组合出下一级；某些组合把解空间压小到**稍微验算就会结晶出新规则**。**派生规则应当被系统推出，而不是等人绊倒。**

落地要求：①派生规则是**一等登记对象**，必带完整前提集与层级，前提变更可追溯失效；②承重结论出厂前对前提集**跑组合扫描至饱和**（不再产出新规则），**塌点**（自由度被组合钉死）显式上报。

**样板 —— "5 满 1 半"条件定理（务必连前提一起引用）**：
*条件于「钢块免分流（全满带）」时*，制瓶机的占空分配唯一 = 5 台满 + 1 台半。五条前提各处于不同派生层级：钢瓶总量 5.5（一级派生）× 带容量 1 件/tick（基础）× 配方 2:1（基础）× 免分流（目标性约束）× 六台全开（二级派生）⇒ 每台占空被逼进 {1/2, 1} 两档 ⇒ `k·1 + (6−k)·½ = 5.5` ⇒ `k = 5` 唯一。
**无条件情形下仍是 42 维自由**——同一问题两个层级两个答案，两个都对。**把它当无条件规则用就是错的。**

出处：文件记忆卡 `rule-derivation-closure-axiom`。

### 9.3 判据体系指路

科学 / 求解 / 数学面的**任何**“知识 × 计算”分解边界（住址、切分、管线门序、cut 打包），走 [`REASONING_METHOD.md`](REASONING_METHOD.md) **操作卡的七问（⓪–⑥）**，其中 ⓪ 是押任何结构性预设之前最先问的锚点问。本页不复制操作卡与过堂表；起争议回方法正文仲裁。

---

## 10. 退役读法一览

引用旧文书、旧收据、旧记忆卡时对照本表。左列一律**不得**再作为前提使用。

| 退役读法 | 现行读法 | 谁点名退役 |
|---|---|---|
| 协议箱"每窗口至多 6 **种**商品" | **槽数口径**：6 槽全占才堵，与商品种类数无关 | `semantics.protocol_storage_box_wireless.slot_count_clause`（明写 "an example, not a bound"） |
| "箱 = 有界吸收体 ⇒ 可能堵 ⇒ 不能当汇流区终点" | 堵塞判据在本产线**物理不可达**（§4.1 格数账） | **条件性退役，不是无条件**：论据的两条前提（fill-first + 单槽容量 50）2026-08-08 批已入册 `slot_count_clause.cache_parameters`，但账本身仍是条件式的——类级条款只给「6 槽全占才堵」的界，本实例的清偿以 `terminal_clause` 的实例级 discharge 注为准。记忆卡 `classification-labels-hide-parameters` |
| "错货不放行进支线 ⇒ 非门口堵塞" | **没有下一条出边就队头阻塞** | `semantics.item_admission_port_exclusion.rationale_restated` (c) 分拣终点定理 |
| "限制口是官方分拣解法，直接解混料绝症" | **刻意不建模在现役 main 仍成立**，但**安全排除账已降格**：2026-08-08 批把它从无条件 safe-exclusion 定理改成显式的认证 scope 限制，authority 改为**条件式**（谓词一接入即失效），省略面登记为 `model_stricter_faces` 第 (6) 项。「必要性 = 零」的三腿仅存仓库口混吃一腿（速率腿缺占空前件、分拣终点腿限两货同终端）。处置 owner 已定＝先放着、随墙审计首轮回桌 | `semantics.item_admission_port_exclusion`（`.authority`）；`axiom_kernel.model_stricter_faces` (6)；本页 §7 准入口行 |
| "模型的 front 排他 = 模型比游戏严" | **翻案**：sink-front 排他是对机器口污染的**正确保守编码**；写宽的是混流条款，已由终端条款补齐 | `mixed_commodity_flow.terminal_clause`；`docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md` |
| 空矩形宽松读法（路由可穿 ghost） | **严格**：什么都不能有 | `globals.empty_rectangle.emptiness_adjudication`（明写旧宽松读法 void） |
| 协议箱 = "无线全向零口黑洞" | 实体 3 进 3 出、需电；无线仅箱 → 仓库段 | `protocol_storage_box_wireless.supersedes` |
| `front = port + DIR_DELTA`（体外第 2 格） | **identity**：stored 坐标本身就是带子格 | `PROJECT_LOCK.md:388` `F-RT-R3-01`（inverted）+ `F-FRONT-INC-01` |
| 中枢 `generic_input_slots = 0` | **14** | `rules/preprocess_plan.json`；`PROJECT_LOCK.md` `F-GM-Q3-01` |
| 箱下界 = `ceil(gross/3) = 1` | **0**（先扣 mandatory provider 容量） | `PROJECT_LOCK.md` `F-GM-Q3-01` |
| 速率引理无条件成立 | **双前件**，缺前件不得引用 | `semantics.rate_lemma_scope` |
| "机器输入口会挑自己要的货" | 进料**配方盲**、无内容选择权 | `terminal_clause` class (3)；公理 A9 |

---

## 11. 已登记欠账与【待核】

**canonical 措辞欠账**：**两条已于 2026-08-08 批结清**，记在此处以备回查——

- ~~缓存槽 **fill-first** 前提（同种商品占满一槽后才开新槽）的明文，以及**单槽容量参数**未入 canonical~~ ⇒ **已结清**：入册为 `protocol_storage_box_wireless.slot_count_clause.cache_parameters`（`slot_capacity: 50` / `group_count: 6`，fill-first 与落位顺序写在同一 `statement`，另带 `provenance` 与 `evidence_grade`）。§4.1 的两本账现在有明文条款可引。
- ~~协议箱由 `terminal_clause` class (2) 提升为 **drain 终点**的措辞改判~~ ⇒ **已结清，但落法与原议不同**：**类级规则一个字没动**（class (2) 仍是需清偿接收不变量的有界吸收体），改判落成 `mixed_commodity_flow.terminal_clause` 里的**实例级 discharge 注**——只对冻结的 266 实例集断言不变量已清偿，别的布局不继承。见 §4 class (2) 行。
- **证据等级两句订正（新欠，挂下一次动 canonical 的批；owner 2026-08-08 深夜两笔口述定谳）**：①`cache_parameters.evidence_grade` 里 capacity-50 现归模拟器级——**错级**，owner 已答「条款」，应升 owner 口述定谳级（错级根因＝落地批沿用了份6 对勘书早于 08-07「口述即定谳」权威裁定的过时框架；declaration-order 落位机制的精度**仍留**模拟器级不动）。②`terminal_clause.adjudicated` 前提 (ii) 存货口半边的「EXTRAPOLATED FROM THE SIMULATOR … NOT owner-adjudicated」——owner 已定谳「仓库存货口与取货口只能放在仓库基线上，条款」，该半边升 owner 定谳级，X1 关案四前提全齐。两句都是**保守方向的错级**（低估口述权威、不危及 soundness），故不单独走 reseal、随下批 canonical 顺手改。
- **fen8 核签两笔（挂同一下批；出处 `.artifacts/gpt_pro_review_batch_20260808/verdict/fen8/ADJUDICATION_fen8.md` ⑦）**：①「**每台物理机只承担一个 operation**」是 266 台账（逐 operation Σceil）的**未登记承重前提**——若同机型可跨 operation 合并，台数下界变 ceil(Σ)、恰差 2 台/34 格（grinder_1 与 seedcol_1 各 1）；核签席已用推理关在**已建模域内关闭**（合并机单输出槽组⇒输出必混流⇒需分拣⇒唯一分拣器件=准入口=面 (6) 省略对象），故 266 零拒真，但该前提须补登——推荐登记为 A9＋终端分类 (3)＋面 (6) 的**派生后果**（非独立限制）；34 格同时是**面 (6) 省略代价在 mandatory 侧的精确上界**，喂墙审计种子案例。②`terminal_clause` 里「3 口×1 件/2s⇒15 件/周期」的下层前提「逐口 0.5/s」**必须显式挂 A7**（owner 游戏侧带宽＋一口至多一带几何），禁写成「模拟器注册表如此声明」——E-24 实证注册表层**根本没有**端口吞吐字段（逐口 0.5/s 的出处是引擎=速率抽象层）。数字均不变。

- `src/models/patch_routing_core.py:569` `_add_port_adherence` 的 front 偏移残留（§5，不可达，挂 PCR / pose-bool promotion 前置）。
- **source-front 排他 = confirmed over-strict**，已在 `model_stricter_faces` 在册；解锁走**独立的 sealed-face 批**，刻意不并入其他 freeze-ritual。

- **`machine_min_clearance_cells` 不是机身间距（在案纠正）**：该参数**不要求机器机身之间留空**，**机身允许贴合**；它只要求**被实际使用的** stored port / front 格可布带（`rules/canonical_rules.json:462-467`）。exact 模式并**不**施加「所有端口前格都空」这一近似（`MasterPlacementModel._add_port_clearance_constraints` 在 `exact_mode` 下直接 `skipped_in_exact_mode` 返回，其 docstring 写明「严格精确路径不允许把『所有端口前方都必须畅通』这种近似假设当成正式剪枝」）。任何把该参数当作机身 moat 计入几何封锁的推导都会**判死过多（超杀）**。同时须区分：供电覆盖是 **12×12 coverage square**（anchor `(x,y)` 覆盖 `[x-5,x+6]×[y-5,y+6]`，边界裁剪，`rules/canonical_rules.json:100-109`），与 conditional/membrane **halo stencil** 不是同一个东西（`docs/research/b1_conditional_halo_20260722/01_necessity_proof.md:30-53`）。出处：`DOSSIER-POLE-GATE-CANARY-20260821-7F3338D139`。
- **纯几何 coverer 判空守卫对 powered pose 的实际作用面为空（在案观察）**：`MasterPlacementModel._candidate_pose_indices_for_group` 会删除「coverer 表为空」的 pose，判空依据是**纯几何** coverer 表 `_power_coverers_by_template_pose`（**不扣任何固定占用**）。纯标准库对冻结字节重算显示，四个 powered 模板的**零 coverer 计数均为 0**：`manufacturing_3x3` 17,952 poses（base coverer 60–180）、`manufacturing_5x5` 16,896（80–220）、`manufacturing_6x4` 16,900（80–220）、`protocol_storage_box` 18,496（55–180）。即该守卫在当前冻结盘面上**一个 powered pose 都不删**，实际作用面比其名义更窄；今后任何基于该函数的删除都必须完全归因于**新引入且已证明恒定**的固定占用输入。出处同上。
- **`L4a` / `L4b` 幽灵编号（挂下次动 `src/models/exact_coordinate_master.py` 注释面的批）**：该文件多处注释以 "PROJECT_LOCK L4a" / "PROJECT_LOCK L4b" 形式引用条款编号，但 `PROJECT_LOCK.md` 全文**无此编号**。穷尽搜索（`L4a` / `L4b` / `L4-a` / `lazy power completion` / `power placement subproblem`，排除 `docs/research/` 快照）后，编号唯一出处是 `docs/lever_verdicts.md:377`，原文为「GPT v11 **提议**新 PROJECT_LOCK L4a/L4b 边界切开」——**提案从未被采纳**，且所属研究线 L16 的终态判词是 ❌ 死路（`docs/lever_verdicts.md:377-400`）。实质约束确实存在但**不叫这个名字**：真源是 `PROJECT_LOCK.md:703`（§4 Forbidden Changes，`EXACT_POWER_PLACEMENT_SUBPROBLEM` 为 exploratory only）＋ certified unsafe env map（`src/search/benders_loop.py` 的 `lazy_power_completion_not_certified` 与 `power_placement_forensic_bypass_not_certified`）。清理时改为引用这两处真源，不保留提案编号。出处同上。
- **certified 面供电判死不留可复用结构信息（在案观察）**：certified_exact 强制 C1 表示，供电覆盖由 `CoordinateExactMasterDelegate._add_c1_power_coverage_constraints` 留在 master；供电不可行表现为 **master 直接 INFEASIBLE**（`src/search/benders_loop.py` 的 `RUN_STATUS_INFEASIBLE` 返回点），既不做供电子问题也不升 UNKNOWN，运行时**不产生 cut、core 或 conflict_set**——下一个 ghost rect 从零重推。C1 已有具体杆锚 Bool、常量 optional interval、`AddNoOverlap2D` 与每格 coverage channel；缺的是把高阶 covering 蕴含投影成短的设施联合约束，不是缺供电语义变量。旧 `cover_choice_idx` 归属勘误与 C1 五要素见 `.artifacts/gpt_harvest_20260818/ERRATUM_POLE_GATE_CANDIDATES_ADDENDUM_C1_ATTRIBUTION_20260821.md`；native 正例与根传播缺口见 `DOSSIER-GPT-CUT-SHAPES-20260821-745509BF6B`。
- **冻结链常数锚定仍待独立 hardening（触发器：下次修改 cfg-relaxation admission、checker 或重发冻结证书包）**：下一带批的 M1 已把四个常数钉到 proposition-bound map 并补定向负控，但没有修改既有 admission；不得把批内整改倒读成旧冻结链已完成来源 hardening。触发时须从既有命题来源重建常数映射、保留旧 admission 字节，并让新 checker/receipt 显式绑定来源。出处：`DOSSIER-SIXPRED-UPPER-NEXT-BAND-20260821-CAA91F9B9A`；`.artifacts/sixpred_upper_next_band_20260821/certs/REMEDIATION_RECEIPT.json` M1；对应 CLOSEOUT §7.1、§9。
- **负控执行数与互异载荷数必须分账（触发器：下次生成或验收 cfg-relaxation 负控）**：该批终态记录 288 个文件路径/执行实例全部被拒，但只有 264 个互异 SHA-256 载荷；每个 family/root 的 `embedded_columns_forged_rehashed` 与 `objective_coefficient_inflated_rehashed` 构成 24 对重复字节。后继 generator 必须制造真正互异的 embedded-column forge，并在 receipt 同时报 `execution_instance_count` 与 `unique_payload_count`，禁止把 288 次拒绝写成 288 种独立篡改。出处同上；对应 CLOSEOUT §7.1、§9。
- **六谓词上界方法天花板、条件价目与反向下界入口（research 指针）**：对该 CLOSEOUT 的起点 `(1170,30)`，严格部分只有：同形方法要关闭维度必须有 `wh≥1137`；下行新增 root 的阈值至多 135；面积每降 1，阈值降 4；十二带已把 33 个面积单位中的 15 个消耗掉而未关闭一根。全方向永不关闭、全域最小缺口 5、硬下限附近约削 135 都是经验外推。现有弱对偶只给条件门：若独立证明 `30×39` 与 `26×45` 的所有 admissible 情形均满足 `packaging_battery` 接触重数 `≤1`，则 A/B 对偶分别给 132、134，并条件性得到端点 `(1170,18)`；该标量前件未证，CLOSEOUT 明确禁止把条件端点写成结论。该 CLOSEOUT §11 同时登记下界方向尚无已建立见证：构造一个 admissible `30×39` strict-empty-rectangle witness 会让起点上界与见证相遇，优先级高于机械追加下一带。出处：`DOSSIER-SIXPRED-UPPER-NEXT-BAND-20260821-CAA91F9B9A`；`.artifacts/gpt_harvest_20260818/TASK_SIXPRED_UPPER_CLOSEOUT_20260821.md` §3、§5、§11。

**【待核】**：

- 文件记忆卡 `empty-rectangle-strict-semantics` 内记的 canonical 字节身份是**中间代**（已被后续公理 kernel 批取代）。记忆层订正走记忆维护纪律，不走本页。
- 本页凡未标"亲手核过"的代码行号，随重构漂移；**查 pin 面与符号一律 `git grep` 起手**（拼接字符串能骗过普通 grep，`.rgignore` 会把 `docs/research/**/*.py` 整类投影出 rg 默认结果）。

---

## 12. 改这页的规矩

1. **只写现行读法**。旧读法进 §10 的"退役读法"表并写清谁点名退役，**不复述旧论证**。
2. **日历日期只允许出现在"历史见 …"指针和文件路径里**。
3. **每条承重断言必须带具名来源**（canonical 键 / `F-*` 编号 / 文件路径 + 符号）。
4. **拿不准就标【待核】**——过时的带日期断言只是旧，错误的现在时断言会害人。
5. 改 `rules/canonical_rules.json` / `rules/preprocess_plan.json` / `PROJECT_LOCK.md` 一律是 **freeze-ritual**（更新 pin → 重生成派生产物 → 重跑 gate；close-kernel sealed 文件还要走完整 reseal 连锁，见 `docs/项目说明/28_pitfalls_and_sop.md` SOP-1 / SOP-2）。本页跟着改，但**永远不反过来当权威**。
