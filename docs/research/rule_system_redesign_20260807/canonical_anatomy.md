# canonical_rules.json 结构解剖

对象：`rules/canonical_rules.json`，40,371 字节，SHA256 `b675fb6a…c4ca`（frozen artifact），`metadata.version = 1.2.0`。
读法：全文逐行读，配 `rules/canonical_rules.schema.json` 与真实消费方源码交叉核对。本文只描述现状，不提改法。

---

## 1. 顶层分区（9 个键）

| 键 | 形态 | schema 约束 | 谁真的读它 |
|---|---|---|---|
| `$schema` | 字符串 | 有 | 无（人读） |
| `metadata` | version / description | required，`additionalProperties:false` | `preprocess_context` 取 metadata 做记录 |
| `globals` | grid / time / logistics / empty_rectangle | required，逐字段封闭 | `preprocess_context` 只取 `time.tick_interval_seconds`、`logistics.belt_capacity_per_tick` |
| `routing_rules` | layers / bridge_mechanics | required，封闭 | **没有任何 Python 消费方读它**（grep 全仓：preprocess_context 不取，material_skeleton 不取） |
| `facility_templates` | 7 个模板 | required | `preprocess_context` 整体取用 |
| `recipes` | 17 条配方 | required | `preprocess_context` 逐条解析 |
| `production_targets` | 2 个成品目标 | required | `preprocess_context` 逐条解析 |
| `commodity_metadata` | 19 种商品的 source_kind/sink_kind/cycle_group | required | `preprocess_context` 解析为 commodity_roles |
| `semantics` | 13 个语义条目 + `_note` | **非 required，`additionalProperties:true`，内部零结构约束** | **没有任何代码读它**（`_note` 自述：不被 demand solver / instance builder / placement generator / 任何 certified solve path 消费） |

两条结构事实值得先记下：

1. **schema 对 `semantics` 完全不设防**。整个 semantics 区在 schema 里只有一句 description + `additionalProperties: true`，没有 required 字段、没有字段枚举、没有子结构。也就是说：条目缺 `axiom_derivation`、缺 `statement`、缺前件声明，schema 一律放行。下文所有「形态不一致」在机器层面都是合法的。
2. **数据区与语义区的机器地位相反**。`globals/facility_templates/recipes/production_targets/commodity_metadata` 是被解析、被算成 frozen 派生工件的；`routing_rules` 和整个 `semantics` 是纯人读文本。推理者读到的「规则」和求解器执行的「规则」不是同一批字节。

---

## 2. semantics 区形态学（13 个条目 + 1 个 `_note`）

### 2.1 字段出现矩阵

条目按文件顺序，`✓` = 该字段存在于条目顶层，`(嵌)` = 只出现在子条款内：

| 条目 | applies_to | statement | axiom_derivation | adjudicated | predicate_status | 独有字段 |
|---|---|---|---|---|---|---|
| `axiom_kernel` | — | — | — | — | — | status, adopted, source_doc, role, scope_premises, axioms{A1–A11}, ruling_level_inputs, model_stricter_faces |
| `boundary_placement` | ✓ | ✓ | ✓ | — | — | placement_rule, generator |
| `routing_cross_junction` | ✓ | ✓ | ✓ | — | — | clarifies |
| `mixed_commodity_flow` | ✓ | ✓ | (嵌) | (嵌) | — | terminal_clause{adjudicated, statement, axiom_derivation} |
| `connectivity_quantifier` | ✓ | ✓ | ✓ | — | — | — |
| `machine_min_clearance` | ✓ | ✓ | ✓ | — | ✓ | adjudication_ref |
| `warehouse_bridge_exclusion` | ✓ | ✓ | ✓ | ✓ | — | authority |
| `protocol_storage_box_wireless` | ✓ | ✓ | (嵌) | ✓ | — | supersedes, slot_count_clause{adjudicated, statement, axiom_derivation} |
| `power_source_note` | ✓ | ✓ | ✓ | ✓ | — | clarifies |
| `item_admission_port_exclusion` | ✓ | ✓ | (嵌) | ✓ | — | authority, rationale_restated{adjudicated, statement, axiom_derivation} |
| `rate_lemma_scope` | ✓ | ✓ | **无** | ✓ | ✓ | **usage_rule（全文唯一一处）** |
| `port_commodity_scope` | ✓ | ✓ | ✓ | ✓ | — | — |
| `power_coverage_stencil` | ✓ | **无** | ✓ | — | — | power_coverage_radius, anchor_footprint, coverage_shape{kind,width,height,definition}, generator |

字段频次：`applies_to` 12 / `statement` 11 / `axiom_derivation` 8 / `adjudicated` 6 / `generator` 2 / `clarifies` 2 / `predicate_status` 2 / `authority` 2；其余 18 个字段名各只出现 1 次。

### 2.2 从矩阵直接读出的形态缺陷

- **没有任何字段是 100% 覆盖的。** 最普及的 `applies_to` 也缺在 `axiom_kernel`。
- **`axiom_derivation` 覆盖 8/13。** 缺的 5 个里，`axiom_kernel` 是根（合理），`warehouse_bridge_exclusion` 明写「NOT derivable — adjudication-level input」（合理，且是显式声明），`mixed_commodity_flow` / `protocol_storage_box_wireless` / `item_admission_port_exclusion` 把 derivation 埋进子条款、顶层 statement 裸奔，`rate_lemma_scope` **既无顶层也无嵌套 derivation**——它是全区唯一一条「有 predicate_status、有 usage_rule、却完全没有推导链接」的条目，正是今日 owner 戳破的那条。
- **前件（premise）没有专用字段。** 全文只有两处写了前件：`axiom_kernel.scope_premises`（版本/审计基线/权威序）和 `rate_lemma_scope.statement` 里内嵌的散文 "Preconditions: (i)… (ii)…"。其余 11 条的适用前件要么隐含在 statement 散文里，要么根本没写。前件不是一等公民 → 推理者不可能机械地检查「前件是否成立」。
- **使用规则（usage_rule）只有一条。** `rate_lemma_scope.usage_rule` 是全文唯一显式规定「怎么引用这条才合法」的字段。其余 12 条被引用时无任何使用约束。
- **`predicate_status` 只有 2 条标了**（`machine_min_clearance` / `rate_lemma_scope` 均为 `non_predicate`）。其余 11 条与 6 个 certified 谓词的关系只能从 `applies_to` 的字符串里猜（有的写 `certified_predicate_5_routing_connectivity`，有的写 `facility_templates.xxx`，有的写 `routing_rules`，格式不统一）。
- **子条款是「打补丁」形态。** `terminal_clause` / `slot_count_clause` / `rationale_restated` 三个嵌套块都是后来（2026-08-06）为修正父 statement 而追加的，父 statement 原文一字不改地留在原地。读者要先读父句、再读子句、再自己做「子句收窄父句」的合并推理。`mixed_commodity_flow.statement` 说「mixing allowed」，`terminal_clause` 才说「adjudicated TOO WIDE at PORT level」——单读父句会得到已被推翻的结论。

### 2.3 三种条目形态（按「结论压缩程度」分类）

**(a) 参数事实型** —— 数值/几何直接以字段形式给出，可机读，无需解读散文：

- `power_coverage_stencil`：唯一一条纯参数条目（radius 5、anchor 2×2、coverage 12×12、明确的坐标区间定义、生成器路径）。它甚至没有 `statement` 字段——因为不需要散文。
- 半参数型：`boundary_placement`（`placement_rule` 字段 + 散文）。

**(b) 带前件引理型** —— 结论只在某些条件下成立，且条件被（部分）写出：

- `rate_lemma_scope`：前件 (i) 满产、(ii) 最小车道分配约定；结论「任意两种中间品不可共道」；配 usage_rule 与机器复算收据。**这是全文唯一一条把「前件」写成显式条款的引理，也正是被 owner 判为欠前件（缺「台间占空均摊」这条未声明前件）的那条。** 形态上它已经是最好的一条，仍然漏；说明「散文里列 (i)(ii)」这种形态本身不足以保证前件完备。
- `port_commodity_scope`：作用域声明型（「认证主张只在每个 warehouse-line 端口单商品的博弈片段上成立」），前件写在 statement 里。
- `connectivity_quantifier`：把谓词 5 的量词展开，附「模型比它更严」的登记。
- `warehouse_bridge_exclusion`：显式条件结论——「绑定在冻结的 3.0/2.75 产量目标上，目标一变必须重裁」，是全文对「结论依赖参数」写得最清楚的一条。

**(c) 分类标签 / 压缩结论型** —— 把一串推理压成一个名词或一句判据，参数不在场：

- `mixed_commodity_flow.terminal_clause` 的三分法：class (1) 「structurally non-rejecting」/ class (2) 「**BOUNDED mixed absorber**」/ class (3) 「no content selectivity → unsafe」。这三个标签是下游全部推理者的消费对象。
- `protocol_storage_box_wireless.slot_count_clause`：「the box blocks exactly when its 6 slots are all occupied」——一句堵塞判据，不带任何入量参数。
- `item_admission_port_exclusion`：结论「零建模必要性」，压掉了 (a)(b)(c) 三步推理。
- `machine_min_clearance`：`predicate_status: non_predicate` + 一大段「不是什么」的澄清散文。
- `axiom_kernel.model_stricter_faces`：一串「已登记的更严面」名词列表，无参数。

标签型条目的共同特征：**判据（"blocks when 6 slots full"、"bounded absorber"）与判据成立所需的参数（入口数、单口速率、冲刷周期、槽容量）不在同一条目、多数根本不在同一分区**。见第 3 节。

---

## 3. 实体参数散布图：以 `protocol_storage_box` 为例

owner 今日第一枪的复现路径。协议箱要判「会不会堵」，需要六个量。它们的实际存放位置：

| 参数 | 值 | 存放位置 | 形态 |
|---|---|---|---|
| 分类标签「有界吸收体」 | class (2) BOUNDED mixed absorber | `semantics.mixed_commodity_flow.terminal_clause.statement`（散文中段） | 标签，无参数 |
| 堵塞判据 | 「6 槽全占时堵，与商品种类数无关」 | `semantics.protocol_storage_box_wireless.slot_count_clause.statement` | 标签/压缩结论 |
| 槽数 = 6 | 6 | 同上（散文），以及父条目 `statement` 里的 "flushes its 6 cache slots" | 散文数字，非字段 |
| **单槽容量** | **文件里根本没有** | 最接近的是 `axiom_kernel.axioms.A7_rates` 里 "one input buffer slot x 50 per ingredient"——那是 **manufacturing 机器**的槽参数，不是协议箱的 | 缺失 |
| 物理口数 = 3 入 / 3 出 | 3+3 | `semantics.protocol_storage_box_wireless.statement` 散文（"3 inputs on one side, 3 outputs on the opposite side"） | 散文数字 |
| 单口速率 = 1 件 / tick | `port_max_throughput_per_tick: 1.0` | **`globals.logistics`**（另一个顶层分区） | 参数字段 |
| tick = 2.0 s | `tick_interval_seconds: 2.0` | **`globals.time`**（另一个顶层分区） | 参数字段 |
| 冲刷周期 = 10 s | 10 | `semantics.protocol_storage_box_wireless.statement` 散文（"flushes … every 10s"） | 散文数字 |
| 供电前件 | `needs_power: true` | **`facility_templates.protocol_storage_box`**（第三个分区） | 参数字段 |
| 供电前件的行为含义 | 「不供电就永不冲刷，占用槽永不清」 | `axiom_kernel.axioms.A8_power` + `slot_count_clause.statement` 末句（重复表述） | 散文，两处 |
| 几何 3×3 / 可旋转 / 实心 / 对边口 | w=3,h=3,rotatable,is_solid_z,port_rule | `facility_templates.protocol_storage_box` | 参数字段 |

**散布结论**：判「堵不堵」需要的量分散在 **3 个顶层分区、5 个条目、至少 4 种表达形态**（字段值 / 散文数字 / 隐含在别的实体的公理句里 / 完全缺失）。其中：

- 「6 槽」「3 口」「10 s」这三个只以**散文数字**存在，无字段、无 schema、不可枚举、grep 不成表；
- 「1 件/tick」「2.0 s」在 `globals`，与协议箱条目之间**没有任何交叉引用**（`protocol_storage_box_wireless.applies_to` 指向 `facility_templates.protocol_storage_box` 和 `preprocess_plan.utility_operations.box_sink`，不指向 `globals.logistics`）；
- 「单槽容量」在文件中**不存在**，只有 manufacturing 的 ×50 可被误取；
- 因此，「6 槽全占 → 堵」这句判据，在它所在的条目里**没有任何一个参数可以用来检验它是否可达**。要检验必须跨三个分区手工凑参数，而没有任何机制提示读者需要去凑。

同类散布可用同法画给 `power_pole`（radius 5 同时出现在 `facility_templates.power_pole.power_coverage_radius`、`semantics.power_coverage_stencil.power_coverage_radius`、`axiom_kernel.A8` 散文三处，是全文唯一被三重冗余记录的参数）与 `protocol_core`（`core_limits.max_inputs=14` 在 templates；「唯一有线仓储输入侧」在 A4；「14 physical inputs」在 terminal_clause 散文）。

---

## 4. 条目间引用方式

**没有任何机器可解析的交叉引用。** 引用全部是散文里的字符串，共五种互不统一的写法：

1. **`applies_to` 字段的点路径**（12 处）——但目标混杂三个命名空间：文件内路径（`facility_templates.boundary_storage_port`、`globals.logistics.machine_min_clearance_cells`）、**外部文件路径**（`preprocess_plan.utility_operations.box_sink`）、**自然语言谓词名**（`certified_predicate_5_routing_connectivity`、`certified predicate 4 (port exact counting)`、`any certification-narrative use of rate arithmetic`）。同一字段里三种指称对象，无法统一解析。
2. **`semantics.xxx` 散文引用**（约 8 处）：`semantics.axiom_kernel`、`semantics.rate_lemma_scope`、`semantics.mixed_commodity_flow.terminal_clause`、`semantics.port_commodity_scope`。写在 statement/axiom_derivation 的句子中间。
3. **`kernel Ax` 引用**（A1, A3, A5a, A5b, A6a, A8, A9, A11 被引；A2/A4/A7/A10 只在 `axiom_derivation` 组合句里露面或不被引）——指向 `axiom_kernel.axioms` 的键，但键名是 `A1_transport_conservation` 形态，引用写作 `A1`，**字面不匹配**。
4. **`derivation #N` 引用**（#1, #2, #8a, #9, #10, #11, #14, #15, #16, #19, #21 共 11 个编号）——**编号表不在本文件内**，在 `docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md` 的 derivation matrix #1–#21 里。文件内是 11 个悬空引用，读者不打开那份归档就无法验证任何一条 derivation。
5. **外部文档路径**（5 个 `docs/…`、2 个 `src/placement/placement_generator.py:符号`、若干 `PROJECT_LOCK.md` 条款号）——`generator` 字段只给了 2 条条目（boundary_placement、power_coverage_stencil），其余 11 条与代码之间没有任何链接。

**没有反向索引**：`axiom_kernel` 不知道哪些条目引了它的哪条公理；`globals.logistics` 不知道哪条 semantics 依赖它的数值。改一个参数，无法机械地找出受影响的结论集合。这正是 owner 说的「规则在案但推理没把有影响的因素算上」的结构条件——**依赖是单向、散文、且不完整的**。

---

## 5. 自描述机制清单（canonical 自带的「元规则」）

文件内已经存在的、意在自我约束的机制，共 7 项：

| 机制 | 位置 | 它承诺什么 | 实际强度 |
|---|---|---|---|
| `semantics._note` | semantics 顶部 | 声明整区 descriptive-only、不被任何 solve path 消费、改它只动 frozen hash | 与源码一致（已核：无消费方）；但它同时意味着**语义区的错误不会被任何测试发现** |
| `axiom_kernel` | semantics.axiom_kernel | 11 条公理作为整区语义地基，其余条目是其上的定理或 owner 裁决 | 只有 8/13 条目真的挂了 `axiom_derivation`；derivation 编号表在文件外 |
| `axiom_kernel.scope_premises` | 同上 | 全区适用前件：游戏 v1.1 valley-4、模拟器审计基线 commit、无玩家运行时干预、权威序（owner 实测 > 模拟器规则层 > canonical 文本 > 文档转述） | 全文唯一的全局前件声明；条目级前件无对应机制 |
| `axiom_kernel.ruling_level_inputs` | 同上 | 登记两条「不可由公理推出」的 owner 裁决（空矩形严格性、warehouse_bridge_exclusion） | 显式、闭合，形态良好 |
| `axiom_kernel.model_stricter_faces` | 同上 | 登记模型比游戏语义更严的四个面（保守不伤 soundness） | 名词列表，无参数、无解锁条件、无对应测试 |
| `usage_rule` | 仅 rate_lemma_scope | 规定引用该引理必须同时 discharge 两条前件，否则只能读作保守编码 | 全文唯一一条；且它自己的前件集被证不完备 |
| `predicate_status` | machine_min_clearance, rate_lemma_scope | 标注该条与 6 个 certified 谓词的关系 | 只标了 2/13 |
| 版本化/取代标注 | `supersedes`（1）、`clarifies`（2）、`adjudication_ref`（1）、`adjudicated`（6）、`source_doc`（1）、`adopted`（1） | 记录裁决出处与被取代的旧读法 | 六个不同字段名做同一件事，无统一格式，无日期字段（日期混在散文里） |

对照任务书里点名的 `mutation_policy`：**该文件中不存在此键**（全文搜索 0 命中）。变异/守卫策略在仓库其他处（哨兵测试、preflight FROZEN_ARTIFACTS 钉哈希），canonical 自身不带变异策略字段。

---

## 6. 与今日两枪的对应（只做定位，不提改法）

- **第一枪（协议箱）**：标签在 `mixed_commodity_flow.terminal_clause`（class 2），判据在 `protocol_storage_box_wireless.slot_count_clause`，参数散在 `globals.time` + `globals.logistics` + `facility_templates` + 散文数字，单槽容量根本不在文件里。判据条目与参数之间零引用（第 4 节），所以「判据在物理入量下是否可达」这个问题**在文件结构上无法被提出**。
- **第二枪（rate_lemma_scope）**：它是全文前件写得最显式的一条（有 Preconditions (i)(ii)、有 usage_rule、有机器复算收据），仍然漏了「台间占空均摊」这条残道前件——说明缺陷不在「这条写得草率」，而在于**前件以自由散文列举、没有任何完备性检查装置**（无 schema 约束、无反向依赖索引、无消费方测试、`axiom_derivation` 恰好也缺）。

---

*本文件只读普查，未修改 canonical、src、scripts 或任何锁面文件。*
