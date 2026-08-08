# canonical_rules.json 改稿逐条对照（DRAFT，未落地）

> 起草席（opus，隔离 worktree）2026-08-07。**本目录只是草案，未向 main 提交任何字节。**
> 底稿：`.artifacts/gpt_pro_review_batch_20260807/verdict/fen1/ADJUDICATION_fen1.md` §3（26 段清单）＋ §2 合稿纪律。
> 外审逐字文本出处一律记作 `REPLY_VERBATIM.md:NN`（同目录 `verdict/fen1/`）。
>
> | | |
> |---|---|
> | 基线 | `rules/canonical_rules.json` @ `3234c30`，40,371 B，`b675fb6a…c4ca` |
> | 草案 **v3** | `canonical_rules.DRAFT.json`，**59,989 B**，**`c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0`** |
> | 草案 v2（已被 v3 取代，勿用） | 58,938 B，`fedc9537…bea2` |
> | 草案 v1（已被取代，勿用） | 55,729 B，`3cb6bea9…123d` |
> | 改动面 | `semantics` 下 6 棵子树；其余全部子树与全部顶层键**逐字节未动**（机器核对，见 §4） |
>
> **v2 = v1 ＋ 主线程 2026-08-07 五条裁决**（#1 甲 / #2 采纳最小改法 / #3 维持 / #4 维持 / #5 并入 / #6 建档）。
> 逐条落地见 **§5**，C6 完整性规则的饱和扫描见 **§6**。
> **v3 = v2 ＋ 对抗复核四条发现的修复**（F1 承重 / F2 / F3 / F4），逐条见 **§7**；v2→v3 全部字节差异见同目录 `V2_TO_V3.diff`。

---

## 0. 合稿时用的两条自定规则（先声明，免得被读成擅改）

**规则 A（保留规则）**：外审替换文本若会丢掉现文里的**归档指针 / 交叉引用 / 括注 / 机器验证记录**，且保留它不与替换意图冲突，则一律保留，并在本表标 `[保留]`。全部 **6** 处：C9 的归档路径、C8+C11 的 `See semantics.axiom_kernel.`、C12 的模型编码句、C20 的末句、C21 的几何括注、**C18 的 10/17 订正记录（v3 按 F2 补，见 §7.2）**。

**规则 B（合并规则）**：同一字段被清单里两段同时点名时（C8/C11、C12/C13），合成一次写入，合成方式逐段写在下面。合成不改动任何一方的实质断言。

**未做的**：C7（`model_stricter_faces_open_candidates`）按 §2.6 拒绝改期；C24/C25/C26 是承重档订正，不属 canonical 字节，转 `RESEAL_CHECKLIST.md` §3。

---

## 1. 总览（26 段）

| # | 落点 | 档位 | 本草案状态 |
|---|---|---|---|
| C1 | `axiom_kernel.axioms.A2_content_filter_points` | 采纳原文 | ✅ 逐字 + `[保留]` 交叉引用一句 |
| C2 | `axiom_kernel.scope_premises` | 采纳但改写 | ✅ 基准声明句按 §2.5 重写 |
| C3 | `axiom_kernel.model_stricter_faces` 头段 | 采纳原文 | ✅ 逐字 |
| C4 | 同上 五项枚举 | 采纳但改写 | ✅ (1)/(4) 点名所在层 |
| C5 | 新增 `model_stricter_faces_usage_rule` | 采纳原文 | ✅ 逐字 |
| C6 | 新增 `model_stricter_faces_completeness` | 采纳原文 | ✅ 逐字 |
| C7 | 新增 `model_stricter_faces_open_candidates` | 拒绝改期 | ⛔ 不做（§2.6 撞 mixflow scope） |
| C8 | `terminal_clause.axiom_derivation` | 采纳原文 | ✅ 与 C11 合成 |
| C9 | `terminal_clause.adjudicated` | 采纳但改写 | ✅ 补 X1 格数层 |
| C10 | `terminal_clause.statement` 开头 | 采纳原文 | ✅ 逐字前置 |
| C11 | `terminal_clause.axiom_derivation` 末段 | 采纳原文 | ✅ 与 C8 合成 |
| C12 | `terminal_clause.statement` 终端判据段 | 采纳但改写 | ✅ owner 08-06 措辞原样未动 |
| C13 | `terminal_clause.statement` 末句 | 采纳原文 | ✅ 与 C12 合成 |
| C14 | `slot_count_clause.statement` | 采纳但改写＋同批前置 | ✅ 三条约束全满足 |
| C15 | 新增 fill-first ＋ 单槽容量 50（带 provenance） | 新增（核签补） | ✅ `cache_parameters` 对象 |
| C16 | `rate_lemma_scope.statement` | 采纳但改写 | ✅ (ii) 拆实例事实/占空假设 |
| C17 | `rate_lemma_scope.usage_rule` | 采纳原文 | ✅ 逐字 + `[保留]` 锁条引用 |
| C18 | 新增 `recompute_scope` | 采纳原文 | ✅ 逐字 |
| C19 | `u > 5/6` 更弱前件 | 采纳原文（降级附注） | ✅ 新键 `weaker_precondition_note` |
| C20 | `port_commodity_scope.statement` 尾段 | 采纳原文 | ✅ 逐字 + `[保留]` 末句 |
| C21 | `item_admission_port_exclusion.statement` | 采纳但改写（合份2） | ✅ 逐字 + `[保留]` 括注 |
| C22 | `rationale_restated.statement` | 采纳原文 | ✅ 逐字 |
| C23 | `item_admission_port_exclusion.authority` | 份2 供稿 | ✅ 条件式措辞，点名 fb76e15 |
| C24–C26 | 承重档订正 | 必改 / 加注 / 回填 | → `RESEAL_CHECKLIST.md` §3（非 canonical 字节） |

**新增键 4 个**（schema 侧零风险，见 §4）：`model_stricter_faces_usage_rule`、`model_stricter_faces_completeness`、`recompute_scope`、`weaker_precondition_note`，外加 `slot_count_clause` 下两个新子键 `cache_parameters`（对象）与 `blocking_reachability_note`。

---

## 2. 逐段对照

### C1 · `axioms.A2_content_filter_points`（采纳原文 / `REPLY_VERBATIM.md:57`）

**BEFORE**
> Exactly four points in the network decide by item content: (i) admission rules (the 1x1 admission port, deliberately unmodeled - see item_admission_port_exclusion), (ii) cache-slot typing (A3), (iii) pipe-family domain locks (inapplicable here, A10), (iv) domain flags and player-configured slot locks (A11). Senders are content-blind: … **but legal layouts feed machine inputs through single-slot logistics chains where no selection is possible.** Bare machine ports accept whatever fits a compatible slot; …

**AFTER** = `:57` 逐字（全文见 DRAFT.json）。要害改动：把「多槽选择不可达」从 A2 自称的事实，改写成 **A5(a) ＋ 单槽参数推出的拓扑定理**，并明写 `A2 alone does NOT make that multi-slot case unreachable`。

`[保留]` 末尾补回一句 `The admission port itself is deliberately not modeled - see item_admission_port_exclusion.`——现文 (i) 里的交叉引用被外审文本丢掉了，规则 A 保留。

---

### C2 · `axiom_kernel.scope_premises`（采纳但改写 / `:81` ＋ **合稿纪律 §2.5**）

**BEFORE**
> Game v1.1 valley-4; simulator audit baseline = upstream IndustrialPlanner commits 8da9017a / dd334ed5; all permanent-blocking conclusions assume no runtime player intervention (players can manually clear poisoned slots); authority order: …

**AFTER**（首句重写，其余照收 `:81`）
> Game v1.1 valley-4. Upstream baselines are TWO DIFFERENT repositories, not one: JamboChen/endfield-calc@8da9017a (2026-07-17) is the recipe/item/facility numeric catalog and carries NO geometry; hsyhhssyy/IndustrialPlanner@dd334ed5 (2026-07-17) is the base-placement simulator supplying entity geometry, ports, base definition and logistics devices (attribution source: docs/research/rules_audit_20260718/00_owner_adjudications_and_rule_corrections.md section 1; an earlier canonical wording put both commits under one repository name and is corrected here). Current simulator audit baseline: IndustrialPlanner@7b946c16 (2026-08-05) - every simulator-side cross-check from 2026-08-05 onward was run against it. Player configuration that defines the initial instance, … [以下逐字同 `:81`]

**改写依据（起草席复核实测）**：`rules_audit_20260718/00` §1 表格逐字——`JamboChen/endfield-calc` = 配方/物品/设施数值目录、`8da9017a`（2026-07-17）、**无几何**；`hsyhhssyy/IndustrialPlanner` = 基地摆放模拟器、`dd334ed5`（2026-07-17）。当前基准 `7b946c16`（2026-08-05）另有三处独立佐证：`MANIFEST.md:213`、`VERIFICATION_ANNEX_20260806.md:9/:21`、`GAME_RULE_IMPACT_AUDIT.md:19/:320`。

---

### C3 + C4 · `axiom_kernel.model_stricter_faces`（头段采纳原文 `:281`；五项采纳但改写 `:317-323`）

**BEFORE**（一句话四项）
> Registered faces where the certified model is STRICTER than adjudicated game semantics (**all conservative, never unsound**): sink-front single-commodity exclusivity (correct encoding of machine-port pollution, kernel derivation #8a); source-front equal exclusivity (owner 2026-08-06: …); routing reverification's extra no-orphan / selected-source-reaches-sink conditions; binding slot-single-commodity (see port_commodity_scope).

**AFTER 头段** = `:281` 逐字：删掉无条件的 `all conservative, never unsound`，改为可行性方向 / 最优性方向分写，明写 `restricted-model optimum is at most the adjudicated-game optimum in lexicographic order`。

**AFTER 五项**（C4 改写点：(1) 与 (4) 分属不同层，措辞各自点名）
- **(1)** `ROUTING-LAYER destination-front single-commodity exclusivity (the routing model's sink-front exclusivity, imposed on the front CELL of a receiving port) must be split by terminal class. Its application to class (3) machine inputs is the adjudicated pollution-safety encoding (kernel derivation #8a) and is not, by itself, a model-stricter debt. Its application to class (1) protocol-core inputs, and to any class (2) storage-box input execution that satisfies the class-(2) acceptance invariant, is model-stricter;`
  — 加了 `ROUTING-LAYER` 与 `front CELL`；`[保留]` 现文的 `kernel derivation #8a` 指针（外审文本丢了）。
- **(2)(3)** 逐字同 `:319-320`（(2) 补回现文的 `owner 2026-08-06` 归属，规则 A）。
- **(4)** `BINDING-LAYER slot single-commodity typing - a different layer from (1), which constrains the front CELL: this one constrains the port SLOT itself, every binding slot carrying exactly one commodity although adjudicated wired warehouse-line inputs may absorb several commodities at once (see port_commodity_scope for the scope declaration this creates);`
  — 加了 `BINDING-LAYER` 与「(1) 管格、(4) 管槽」的对照，正是 C4 要的「否则读起来像重复登记」；`[保留]` `port_commodity_scope` 交叉引用。
- **(5)** 逐字同 `:322-323`（`warehouse_bridge_exclusion` 新入表，⑧ 的正解）。

---

### C5 / C6 · 两个新增键（采纳原文 `:297` / `:328`）

`model_stricter_faces_usage_rule`：登记表是**模型欠账与认证 scope 台账**，不得当游戏语义前提，不得支撑全游戏 lex 最优断言。逐字。

`model_stricter_faces_completeness`：登记表**必须穷尽**；不在表上不等于等价；新面必须先登记再用于 certified solve 或最优性叙事。逐字。

> ⚠ 这两键与 C21 之间有一个派生闭包问题，见 `BLOCKERS.md` #1。

---

### C8 + C11 · `terminal_clause.axiom_derivation`（两段合成，均采纳原文）

**BEFORE**
> kernel A1 (edge conservation, no return) + A2 (four content-filter points; machine intake blind) + A3 (…) + A9 (…) => pollution-chain derivation #1 and sorting-terminal theorem #21. See semantics.axiom_kernel.

**AFTER** = `:63` 全文 ＋ 末句换成 `:115` 的 #21 受限宇宙句 ＋ `[保留]` `See semantics.axiom_kernel.`

**合成理由（规则 B）**：清单把同一字段点了两次。`:63` 的末句是一个占位指针（`Sorting-terminal reasoning is separately governed by the corrected receiving-terminal scope in this clause.`），`:115` 正是那个 scope 的实体文本，二者是「指针 ↔ 被指对象」，合成无损。**丢掉的只有 `:115` 的首句**（`Kernel A1, A2, A3 and A9 support the three receiving behaviors stated here.`）——它复述的正是 `:63` 明确纠正掉的「A1/A2/A3/A9 单独成立」框架，保留会把 ② 刚修好的缺环再打开。此判断已登记 `BLOCKERS.md` #4 供复核。

---

### C9 · `terminal_clause.adjudicated`（采纳但改写 / `:106` ＋ **§2.3 X1 层**）

**BEFORE**
> 2026-08-06 owner port-semantics final adjudication + precision fix (archived: docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md, appendices one and two)

**AFTER**（`[保留]` 归档路径 ＋ 外审的口朝向层 ＋ 我方 X1 格数层，标 (a)/(b) 两条独立理由；**(b) 腿在 v3 按 F1 补了前提集/触发器/证据等级，下引为 v3 现文**）
> …(a) port orientation - preprocess_plan fixes boundary_io at 0 generic input slots and 1 generic output slot, so it has no physical input port at which a receiving branch could terminate; (b) cell count (**2026-08-07 reasoning closure ordered by owner - a DERIVATION over the frozen instance, not an in-game adjudication**) - boundary-line devices fit only the left-plus-bottom edge strip of 139 cells (70 + 70 - 1 shared corner), of which the mandatory set already consumes 46 boundary pickup ports x 3 cells = 138, so a second boundary-line device class (the simulator's 3x1 storage-side loader with one WarehouseSink input) would need 141 > 139 cells and cannot be placed in ANY layout holding the 266 mandatory instances. **This cell-count leg is CONDITIONAL on a stated premise set - change a premise and it must be re-derived: (i) the frozen production targets, which fix the pickup-port count at 46; (ii) the storage-side loader obeying the same left_or_bottom_boundary rule as the pickup port - owner-tested 2026-07-18 for the pickup half, but EXTRAPOLATED FROM THE SIMULATOR (same tag, same bus-attachment rule) for the storage half, NOT owner-adjudicated; (iii) a 3x1 port body; (iv) the 70x70 grid. It re-derives on any production-target change - the same trigger as warehouse_bridge_exclusion.**

**为什么必须两层**（§2.3）：光有 (a)，有人可辩「#21 说的边界口指**存货口**，它确实有 WarehouseSink 输入」；(b) 证明存货口在任何容纳 266 mandatory 的布局里物理放不下，把这条退路封死。

---

### C10 + C12 + C13 · `terminal_clause.statement`（三处，合成两次写入）

**C10 前置**（`:109` 逐字，插在最前）
> This tri-partition ranges only over modeled physical RECEIVING facility input ports at which a belt segment terminates. Output-only ports and devices with no physical input port are outside the partition. In particular, boundary_storage_port is a 0-input/1-output warehouse pickup source and is NOT a class (1) terminal.

**C12 + C13 合成**（规则 B：现文这两段是同一句里前后相连的 `…class (3); under semantics.rate_lemma_scope…`，只能一次替换）

BEFORE
> Terminal clause: a mixed-commodity segment is safe only if it terminates at a structurally non-rejecting terminal per class (1), or within the stated bound at class (2). The certified model's sink-front single-commodity exclusivity is a correct conservative encoding of class (3); under semantics.rate_lemma_scope the legal mixing domain is in fact confined to the final-product terminal segments (qiaoyu_capsule + valley_battery into core inputs).

AFTER
> Terminal clause: a mixed-commodity segment is unconditionally safe by terminal class only at class (1). It may terminate at class (2) only when a separate execution argument establishes the per-arrival acceptance invariant stated in protocol_storage_box_wireless.slot_count_clause; class (2) membership, or a count of commodity types, does not itself discharge that invariant. Mixed flow terminating at class (3) remains unsafe under the pollution premises stated above, and **the certified model's sink-front single-commodity exclusivity is a correct conservative encoding of that class (3) case** `[保留]`. The rate lemma narrows the mixing domain to final-product terminal segments only for a particular layout that separately discharges every precondition in semantics.rate_lemma_scope. The certified predicates do not discharge those preconditions, so this terminal clause makes no unconditional claim that all other legal layouts are intermediate-pure-flow.

**§2.4 合规声明**：class (2) 描述句里 owner 2026-08-06 的
`the box blocks when all 6 slots are occupied REGARDLESS of how many commodity types are involved (slot-count wording is deliberate; the earlier type-count reading was the too-wide mistake this clause closes)`
**一个字都没动**（机器核对通过）。外审 `:153` 想覆盖它的部分被挡在 C12 落点之外。该句仍有一处精度可议（occupied ≠ full），处理见 `BLOCKERS.md` #2。

---

### C14 · `slot_count_clause.statement`（采纳但改写 / `:147` ＋ **§2.4 三条约束**）

**BEFORE**
> The box's 6 cache slots are 6 INDEPENDENT single-slot groups (…): one commodity per occupied slot, and the SAME commodity may occupy several slots. **The box therefore blocks exactly when its 6 slots are all occupied**, REGARDLESS of how many commodity types are involved - bounded mixed absorption with the bound stated in SLOTS, deliberately not in commodity types. Unpowered, the 10 s flush never runs and occupied slots never clear (power is a behavioral precondition, kernel A8).

**AFTER**（外审 `:147` 为骨架，三条约束逐条兑现）
- ④ 的核心：`blocks exactly when` 这个**双条件**被改成逐次到货的接收不变量——`Whether an arriving item is accepted depends on the current type AND the remaining capacity of all 6 groups`、`occupied is not the same as full`、`Class-(2) safety is therefore an execution invariant, not a static count`。
- **约束①（owner 措辞）**：owner 定谳句原样保留，只把它**条件化到它真正成立的那种到货上**：
  `For an arrival of a commodity that no group already holds with remaining capacity, the box blocks exactly when its 6 slots are all occupied, REGARDLESS of how many commodity types are involved - bounded mixed absorption with the bound stated in SLOTS, deliberately not in commodity types (owner 2026-08-06 adjudication, wording preserved verbatim).`
  这正是份6 深挖 1 ① 的实测结论：该读法「对一个全新商品在保守方向上正确」。`adjudicated` 字段里的 `the earlier 'six different commodities' phrasing was an example, not a bound` 未动。
- **约束②（capacity 50 不得偷写）**：statement 里出现的 `capacity 50` 一律带 `(parameters and provenance: cache_parameters below)` 指针，参数本体连 provenance 同批入册 = C15。
- **约束③（我方两本账）**：不塞进 statement，另立 `blocking_reachability_note`（见下），避免把条件式论证混进无条件条款正文。
- `[保留]` 断电句（`Unpowered, the 10 s flush never runs…`）——外审文本没有它。

---

### C15 · 新增 `slot_count_clause.cache_parameters` ＋ `blocking_reachability_note`（核签补 / 底稿 §2.4、`CROSSCHECK_6S.md` 深挖 1 ②）

`cache_parameters` = 对象，5 字段：

| 字段 | 内容 |
|---|---|
| `slot_capacity` | `50` |
| `group_count` | `6` |
| `statement` | 静态本地容量 6×50=300；**落位顺序 = 声明顺序里最早可收的那一组**（storage_slot_1→6，「可收」= 空组，或已定型为该商品且未满）；owner 2026-08-06 游戏定谳：**fill-first 成立**（满格后同种开新组）且同种可占多组；模拟器规则层精度补充：检索键是声明顺序不是内容，**严格更早的空组优先于更晚的已定型未满组**；一个 10 s 冲刷周期内两种读法重合（冲刷把全部组一起清空，之后按声明顺序重填） |
| `provenance` | `entity-definition.ts:835-866` 的 `createSlots("slot", [50], …)` 连续 6 次 ＋ `createSlots` 逐 capacity 造槽（`:517-526`）；落位顺序 = `topology-compiler.ts:250-280`（一个输入口绑 6 组 ⇒ 按声明顺序 push 6 条边）＋ `stage-3:300-345`（逐边独立试、失败只 continue），由回归测试 `storage-multi-slot-routing.test.ts:176-188` 钉死；快照 `IndustrialPlanner@7b946c16`（2026-08-05），2026-08-07 盲对勘席逐字核对 |
| `evidence_grade` | owner 游戏定谳（fill-first ＋ 同种多组）／模拟器规则层源码（容量 50 ＋ 声明顺序机制）；按 `scope_premises` 权威序，模拟器行只是佐证，**永不能顶替 owner 游戏定谳** |

**为什么写「声明顺序」而不是只写 fill-first**：份6 深挖 1 ① 实测出一个反例——1 号组空、3 号组装着未满的 X 时，新到的 X 落进 **1 号组**（空槽分支先命中），即字面 fill-first 不是全称成立。owner 定谳的两半（满格开新组、同种可占多组）不受影响，所以按权威序把 owner 定谳写成条款主体、把模拟器机制写成精度补充，两者在一个冲刷周期内重合这一点也一并写明。**这是本草案唯一一处对 owner 措辞做机制级细化的地方，已登记 `BLOCKERS.md` #3。**

`blocking_reachability_note` = C14 约束③ 的两本账，逐条标条件：
- **(a) 格数账**：3 个实体输入口 ⇒ **在模型的 destination-front 单商品排他下**每口恰一种商品 ⇒ 至多 3 种商品到箱；配合已登记的落位顺序与 50 容量、且冲刷周期从 6 空组起算 ⇒ 每周期至多 3 组被定型 ⇒ 6 组全占的堵塞态到不了。**明写条件**：依赖两个新登记参数**以及那个模型面**；只靠条款文本上界是 6 槽不是 3 槽（同种可占多组）。
- **(b) 件数账**：3 口 × 1 件/2 s × 10 s ⇒ 每周期 ≤ 15 件（这个到货率无条件）；但「远小于缓存」这一步是与 300 件静态容量比，仍依赖容量参数。
- 收尾明写：两本账都不是认证谓词（速率与时序 OUT-OF-SCOPE），都**不履行**一般布局的接收不变量，只解释冻结产线上它为何被自动满足。

> **对任务书口径的一处订正已兑现**：handbook `:99` 原话是两本账**都**依赖未入册的单槽容量参数，无条件的只有「每周期 ≤ 15 件」这个到货率、不是整条安全结论（底稿 §2.4 末段）。草案按 handbook 原话写，没有按「件数无条件 / 槽数 conditional」写。
> **一处比 handbook 更严的收紧**：把「3 口最多喂 3 种商品」显式限定在**模型的 front 排他面之下**（游戏里一条混流带可以从一个口送进多种商品）。见 `BLOCKERS.md` #3。

---

### C16 · `rate_lemma_scope.statement`（采纳但改写 / `:186` ＋ 底稿 §1.4 仲裁）

**BEFORE**（两前件）
> Preconditions: (i) full production …; (ii) **minimal-lane-allocation convention** - each commodity occupies the fewest belt lanes its rate admits; …

**AFTER**（三前件 (i)(ii)(iii)，即份1 形态 = 份4 要求的严格超集）
- (i) 满产（逐字）
- (ii) **台间等占空**，按改写点拆成两半：
  > Precondition (ii) has a FACT half and an ASSUMPTION half, and only the second is imposed here. Fact half (a property of the frozen instance set, not a restriction introduced by this lemma): for each operation o with exact aggregate machine-run demand R_o, the frozen mandatory instance set already contains exactly n_o = ceil(R_o) machines carrying o - verified for all 17 operations across the 266 = 219 + 46 + 1 instances. Assumption half: every one of those n_o machines runs at the same utilization u_o = R_o / n_o.
  （核签 CLAIM-B 实测 17/17 全中；不这么拆，读者会以为机器数是我们在这里限制的自由选择）
- (iii) **不额外分道**（逐字，`each per-machine commodity stream` 的逐机器局部最小——正是 §1.4 里替份4 消掉读法二分的那句）
- 结论段逐字：残道集 `{5/6, 11/12, 19/22, 21/22, 10/11, 1}`、两两和 > C、21/22 在 sandleaf 输入侧、终品排除在 pair test 外、**离开这个前件族则本引理对该布局不作任何断言**。

**⑥ 仲裁落地声明**：最少车道前件**保留**（份1 ⑥ ACCEPT）。份4 R-03 删的是 REJUDGE 定理 1 的车道前件，两条定理对车道数单调性相反，互不冲突（底稿 §1.1-1.2）。本草案**不删** (iii)。

**段内删除声明（v3 按 F2 补，v1/v2 漏声明）**：外审的整段替换会把现文末尾这句**整句删掉**——
> `Machine-verified recompute (2026-08-06): pairwise-sum<=1 counterexamples over intermediate residual lanes = 0; full-rate recipe share corrected to 10/17 (an earlier 9/17 was a transcription error); residual-rate set {…} with 21/22 arising on an input-side feed lane (sandleaf feed), a side label the earlier prose omitted.`

其中残道集与 21/22 侧标已被新 statement 与 C18 的 `recompute_scope` 吸收，**但「反例 = 0」的机器验证表述与「10/17（旧 9/17 系笔误）」这条订正记录在 v2 里净消失了**——而且因为整个字段本就在改动清单里，逐字段 diff 照不出来。**处置（裁决所选路径）**：把这条记录**移进 `recompute_scope`**（见 C18），不做净删除。理由：本项目 08-07 刚吃过登记丢失/陈旧反向传播的亏（P2 陈旧登记事故），笔误订正的历史痕迹正是最不该在冻结件里蒸发的东西。

---

### C17 · `rate_lemma_scope.usage_rule`（采纳原文 / `:228`）

**BEFORE**
> …Any narrative promotion that leans on this lemma … must cite this entry AND discharge both preconditions; outside them, front exclusivity remains a conservative correct encoding and nothing more is claimed.

**AFTER** = `:228` 逐字。要害：明写 `A certificate therefore does NOT discharge preconditions (ii) or (iii)`、`A post-hoc external proof may discharge the preconditions; the ordinary CERTIFIED result alone cannot`。
`[保留]` 末尾补回 `Rate arithmetic never enters a certificate (PROJECT_LOCK.md 1A B unchanged).`——现文有、外审文本丢了，是锁条引用不能掉。

---

### C18 · 新增 `rate_lemma_scope.recompute_scope`（采纳原文 / `:262`）

逐字。3.3 的三点全在：满道被脚本主动删除、含 1 的集合是**派生集合**不是 stdout 字面集合、终品只在 pair test 前排除、脚本**不验证**「2-4 条终品车道」这个几何数量。

**v3 追加一句（F2 处置，`[保留]` 规则 A 的第 6 例）**：
> Machine-verified record carried over from the superseded statement text (2026-08-06 recompute): pairwise-sum <= 1 counterexamples over intermediate residual lanes = 0, and the full-rate recipe share was corrected to 10/17 - an earlier 9/17 was a transcription error.

⇒ C18 **不再是逐字节等同 `:262`**，差异恰为这一句尾附，性质与 C1/C17/C20 的 `[保留]` 相同（把现文里会被替换稿丢掉的内容补回），已在本表与 §1 总览声明。对抗复核席实跑确认：10/17 为真、反例仍为 0。

---

### C19 · 新增 `rate_lemma_scope.weaker_precondition_note`（采纳原文，降级为附注 / `:193-209`）

首行即写死身份：`ARCHIVAL NOTE, not a precondition of the lemma above.`
内容：`u > 5/6` ＋ 保留 (iii) 即可；k∈{1,2,3} 三档末道下界 `u>5/6`、`2u-1>2/3`、`3u-2>1/2` 全 > 1/2；三个非均摊实例 `[1, 9/10×5]`、`[1, 19/20×10]`、`[1, 7/8, 7/8]`（核签独立复算通过）证明它严格弱于均摊。末尾写明**不作主前件**的三条理由（仍需 (iii)、比均摊难核、证书两者都不履行），以及更一般的「每条非满中间车道 > 1/2」没有证书变量能见证。

---

### C20 · `port_commodity_scope.statement` 尾段（采纳原文 / `:240`）

BEFORE 从 `By semantics.rate_lemma_scope this expressiveness gap is confined to…` 起整段；AFTER 为 `:240` 逐字——把「缺口被限制在 2-4 条终品车道」从无条件事实降格为「只在该分配剖面内、且前件全部单独履行后才成立」。
`[保留]` 末句 `This entry exists so the gap cannot silently be read as full generality.`

---

### C21 + C23 · `item_admission_port_exclusion`（**份1 + 份2 合稿**，底稿 §2.7）

**C21 `statement`**（采纳原文 `:370` ＋ 规则 A 括注）

BEFORE
> …geometrically and for connectivity it is equivalent to a straight belt (any cell that admits it admits a straight belt), and its filtering function is throughput-scope (OUT-OF-SCOPE). **Omitting it cannot exclude any feasible layout and cannot admit any infeasible one.**

AFTER = `:370` 逐字（几何等价**完整保留**，`[保留]` 现文括注 `(any cell that admits it admits a straight belt)`），无条件断言降格为
> Until an independent completeness transformation is supplied, omission of the admission port is an explicit certification-scope restriction rather than an unconditional safe-exclusion theorem.

这正是 **B1 甲案的 canonical 落地形态**（显式 scope restriction），几何等价本体没被碰，**不重开 B1**。

**C23 `authority`**（份2 供稿 / `ADJUDICATION_fen2.md` B1 段）

BEFORE
> safe-exclusion argument; **no candidate pool or predicate consumes it**

AFTER（条件式，按任务书「如实反映 ③ 谓词将消费它、现役 main 下暂仍成立」）
> Safe-exclusion argument, now explicitly CONDITIONAL. As of this batch no candidate pool and no predicate of the released model consumes the admission port, so the exclusion still stands on the released model - but that is a contingent state, not a standing authority. Any predicate that forbids what only a filtering admission port could realize WOULD consume it; the de-mix prohibition proposed on the mixflow line (two commodities merging and later splitting) is exactly such a predicate - it lives on branch mixflow-surgery (commit fb76e15, routing_subproblem._add_demix_ban_constraints) and is NOT merged into the released model as of 2026-08-07. If any batch lands such a predicate, this authority lapses on landing and the exclusion must be re-adjudicated together with the statement above. Owner disposition 2026-08-07: leave the exclusion in place for now, carried as the explicit certification-scope restriction stated above; modeling the 1x1 filter cell is NOT undertaken by this batch.

**「现役 main 下暂仍成立」是实测的、不是假设**（起草席核实）：`rg -i 'demix|de_mix|de-mix|split_free|mixflow' src/ scripts/` 零命中；`git merge-base --is-ancestor fb76e15 main` 退出 1；`git branch --contains fb76e15` 只有 `mixflow-surgery`。main 里唯一相关物是 `docs/research/p2_0_specialized_20260807/refute_round1/split_free_probe_v2.py`，那是独立算术探针脚本、不是模型谓词、不进求解链。

**只采份1 会留下什么**：一个仍然声称「无谓词消费它」的授权字段，而 statement 已经承认它是 scope restriction——自相矛盾（§2.7 的乙腿）。故 C21/C23 必须同批。

---

### C22 · `rationale_restated.statement`（采纳原文 / `:376`）

BEFORE 的三条腿 (a)(b)(c) 整段被替换。AFTER 逐字：几何等价与配额出界**仍成立**；「分拣从不被结构性需要」**对全部合法布局不成立**；只在单独履行 `rate_lemma_scope` 全部前件的布局内，中间纯流 ＋ class (1) 吸收才可能使准入口不必要；sorting-terminal 定理仍是**必要条件**，不是「任何分拣构造都可移除」的证明。

> 与份2 事实链一致：(a) 腿已被本仓 `split_free_probe_v2` 机器推翻、(c) 腿落在吞吐层对连通性证书不适用、只剩 (b) 覆盖终品段。AFTER 文本不再把 (a)(c) 当支点。

---

## 3. 未做项与理由

| # | 未做 | 理由 |
|---|---|---|
| C7 | 新增 `model_stricter_faces_open_candidates` | 底稿 §2.6：U-02 已被 `RESEAL_MANIFEST.md:116` disposition 到路由复验登记面并划归 mixflow 线，本批加它撞 scope。线索（份2 Q6 反例在禁令 OFF 时 FEASIBLE）转 mixflow 线。**v2 复核仍不做**：U-02 是 PLAUSIBLE 未 CONFIRMED，按 C6 的字面（`known to remove an adjudicated-game behavior`）不入表合规 |
| ~~—~~ | ~~`terminal_clause` class (2) 的 occupied/full 精度~~ | **v2 已做**（裁决 #2），见 §5.2 |
| ~~—~~ | ~~「箱由 class (2) 提升为 drain 终点」的措辞改判~~ | **v2 已做**（裁决 #5），落成实例级 discharge 注，见 §5.3 |
| C24/C25/C26 | 承重档订正 | 非 canonical 字节，转 `RESEAL_CHECKLIST.md` §3 |

---

## 4. 机器验证（起草席自产，命令可复跑）

解释器一律 `/home/zhuran24/zmd-pj/.venv/bin/python`（正牌 `.venv`，非 backup）。

```
CR 字节数                                  0            （LF 纯净）
size                                       59,989 B     （v3）
sha256                                     c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0
src/io/strict_json.loads_strict_json       PASS         （重复键 / NaN / 溢出全过）
jsonschema.validate vs canonical_rules.schema.json      PASS
src.rules.models.CanonicalRulesDocument.model_validate  PASS
placement_generator.load_templates()（F-PRE-R11-01 运行期门）  PASS, 7 templates
顶层键序列 与基线逐字相同                   True
semantics 键序列 与基线逐字相同             True
变动子树                                   axiom_kernel / mixed_commodity_flow / protocol_storage_box_wireless
                                           / item_admission_port_exclusion / rate_lemma_scope / port_commodity_scope
非 semantics 顶层变动                       []           （零）
metadata.version                           1.2.0 未动
power_coverage_stencil                     radius 5 未动
```

**把草案换进 `rules/` 跑内容门**（跑完已还原，`sha256 = b675fb6a…`，`git status` 只剩本草案目录）：

```
pytest -p no:randomly --basetemp=.pytest_tmp/draftcheck -q \
  src/tests/test_rules.py src/tests/test_preprocess_context.py \
  src/tests/cuts/test_helpers_power_cover_stencil.py src/tests/test_material_skeleton.py
→ 85 passed in 1.11s
```

**additive-only 自查**：本批**不碰** `rules/preprocess_plan.json`，其 additive-only fail-closed（顶层出现 `recipes`/`production_targets`/`commodity_roles` 即拒）与本批无关。canonical 侧的对应红线是 schema root 的 `additionalProperties: false`——**本草案零顶层新增键**，全部新键都在 `semantics` 内；schema 对 `semantics` 是 `additionalProperties: true` 且**没有 `properties` 子节点**（`canonical_rules.schema.json:431-435`），即整棵子树零约束，任意深度新键合法。pydantic 侧 `semantics: Optional[Dict[str, Any]]`（`src/rules/models.py:185`），`extra="forbid"` 只作用于声明了字段的模型层，不下探。

**唯一会因本批变红的测试类别 = sha pin 断言**，不是文本断言。全仓唯一读 `semantics` 的内容断言是 `src/tests/cuts/test_helpers_power_cover_stencil.py:100-110`（只读 `power_coverage_stencil`），与本批改动面不相交——已实测通过。

**v2 复跑**：同一组门在 v2 上全部重跑 —— `strict_json` / `jsonschema` / `CanonicalRulesDocument` / `load_templates()` 全 PASS，换进 `rules/` 跑内容门 **85 passed in 0.91s**，跑完已还原（`sha256 = b675fb6a…`）。

**⚠ v2 引入了一个字符类变化**：为满足裁决 #5「裁决出处必须写」，实例级 discharge 注里出现路径 `docs/项目说明/00_master_roadmap.md`。这是**冻结件里第一次出现 CJK 字符**（此前非 ASCII 只有 `—`×3 与 `§`×4，现增 `项目说明`×各 1）。JSON/strict_json/schema/pydantic 均无影响（已实测），sha 按 UTF-8 字节算不受影响；提出来只是让落地席知情——该 roadmap 路径本身含中文，没有 ASCII 别名，要写出处就必须带它。

---

## 5. v2：主线程 2026-08-07 五条裁决的落地

### 5.1 裁决 #1（走甲）· `model_stricter_faces` 新增第六项

**落法**：在五项枚举末尾追加 `(6) ITEM-ADMISSION-PORT OMISSION: …`（全文见 DRAFT.json）。要点四段：
1. **为什么它是过严面**：准入口的过滤行为**能改变混流路线的运行安全**，所以省略它**可能移除一条已定谳的游戏行为**——这是 C6 完整性规则的入表判据原文（`known to remove an adjudicated-game behavior`）。
2. **它就是 C21 的台账化**：条目内容是 C21 自身降格结论的复述（无条件安全排除定理 → 显式认证 scope restriction），并写明 `This entry is the debt record required by model_stricter_faces_completeness`。
3. **owner 处置写进条款**：`Disposition owner-decided 2026-08-07 - keep the omission in place - carried on four terms:` 四要素逐条落字——① de-mix 禁令暂维持无条件、**但不得再引用 `item_admission_port_exclusion` 作正当性**；② 本条目即登记的欠账；③ 证据靠**扩展现有诊断臂**取得，而不是去建模过滤格；④ 该谓词一旦接入released model，豁免条款的 authority **当场失效**（指向 `item_admission_port_exclusion.authority`）。
4. **重开条件**：`Reopen triggers: that predicate landing, or the first wall-audit round, in which this face is the named seed case.`

**取材出处（逐条可查）**

| 要素 | 仓内锚点 |
|---|---|
| 条目实体内容 | C21 的 `:370` 文本（本批 `item_admission_port_exclusion.statement`） |
| 「维持禁令 + 不得再引用豁免条款」 | `verdict/fen2/ADJUDICATION_fen2.md` B1「若维持无条件禁令」分支（`:228-232`） |
| 「登记欠账」 | 同上 `:230`「在 `model_stricter_faces` 完整性欠账台账登记」 |
| 「诊断臂扩展」 | `00_master_roadmap.md` 08-07 行：口数扫描臂（14/28/56/128）＋听诊协议「诊断臂翻案 ⇒ 直接 freeze-ritual 实现」 |
| 「接入时 authority 失效」 | 本批 C23 的 `authority` 条件式措辞（同批自洽） |
| 「owner 已决先放着 / 墙审计首轮回桌 / 准入口=种子案例」 | `26_rules_handbook.md:168`（§7 准入口行）逐字 |

**这不是发明条款**：第六项没有引入任何新的事实断言——它断言的「省略准入口可能移除游戏行为」是 C21 已经写下的，「处置=先放着」是 owner 已决的。它只是把这条从条款自述搬进台账，使 C6 的 `exhaustive` 名副其实。

---

### 5.2 裁决 #2 · `terminal_clause` class (2) 的 occupied ≠ full 精度（采纳最小改法原文）

**BEFORE**（owner 2026-08-06 定谳句）
> …and **the box blocks when all 6 slots are occupied** REGARDLESS of how many commodity types are involved (slot-count wording is deliberate; the earlier type-count reading was the too-wide mistake this clause closes)

**AFTER**
> …and, **for an arrival of a commodity that no slot already holds with remaining capacity**, the box blocks when all 6 slots are occupied REGARDLESS of how many commodity types are involved (slot-count wording is deliberate; the earlier type-count reading was the too-wide mistake this clause closes); **occupied is not the same as full - see protocol_storage_box_wireless.slot_count_clause for the per-arrival acceptance invariant that governs class-(2) safety**

**owner 那半句仍逐字未动**（机器核对：`REGARDLESS of how many commodity types are involved (slot-count wording is deliberate` 整串在 v2 中原样存在）。只前加到货限定、后加指针句。理由（裁决原话）：本批已动 `terminal_clause`，同段精度病不分两批踩两次 freeze-ritual；方向虽保守，但按双向保真公理**过严措辞也是账**。

---

### 5.3 裁决 #5 · handbook §11 第 2 条并入：实例级 discharge 注

**类级规则一个字不动**——C12 的 `It may terminate at class (2) only when a separate execution argument establishes the per-arrival acceptance invariant …; class (2) membership, or a count of commodity types, does not itself discharge that invariant.` 原样保留。

**紧随其后追加实例级 discharge**（全文见 DRAFT.json，数字全部取自 owner 裁决行，零新造）：

> For THIS frozen instance the invariant is nevertheless discharged, by owner adjudication 2026-08-07 (project ledger docs/项目说明/00_master_roadmap.md, 2026-08-07 box ruling): 3 input ports x 1 item per 2 s across the 10 s flush period admit at most 15 arrivals per cycle; 15 is far below the box's 300-item static capacity and below even a single slot's 50; pure-flow commodity kinds are at most 3 against 6 groups; and every cycle clears. The 6-occupied blocking state is therefore physically unreachable in this instance - the sole theoretical route to it, a mixed belt carrying 7 or more kinds inside one 10 s window, cannot be assembled here because the only commodities reaching the storage line are the 2 final products - and even a transient stall would clear within 10 s and can never poison the box. The protocol storage box is accordingly a legal mixed-flow terminal in this instance. This is an INSTANCE-LEVEL discharge recorded against the frozen 266-instance set, not a change to the class-level rule stated above: any other layout must discharge the invariant on its own.

**数字逐个对源**（`00_master_roadmap.md` 08-07「owner 裁决：箱=汇流区合法终点（class (2) 提升成立）」行逐字）：

| 草案里的数 | 裁决行原话 |
|---|---|
| 3 口 × 1 件/2 s ⇒ 每周期 ≤ 15 件 | 「3 入口×1件/2s ⇒ 每 10s 冲刷周期进货 ≤15 件」 |
| 15 ≪ 300 静态容量 | 「件数 15≪300」 |
| 纯流种类 ≤ 3 < 6 组 | 「纯流种类 ≤3<6 格」 |
| 6 格全占物理不可达 | 「箱堵塞判据（6 格全占）物理不可达，连暂时堵门都没有」 |
| 理论例外 = 10 s 内 7+ 种，本实例仅 2 终品凑不出 | 「理论例外=混流带 10s 内 7+ 种，本实例仓储系候选仅 2 终品凑不出」 |
| 即便发生也 ≤10 s 清空、永不中毒 | 「即便发生也只等 ≤10s 永不中毒」 |

`≪ 单槽 50` 一项按裁决指令补（15 < 50，与「15≪300」同源同向，不是新造数字）。

---

### 5.4 裁决 #3 · 维持，并按要求确认 `blocking_reachability_note` 的定性

(a) fill-first / 声明顺序的处理**原样保留**（owner 定谳作主体、模拟器机制标为 `Simulator rule-layer precision`、写明周期内重合、`evidence_grade` 声明佐证边界）。不去问 owner。

(b) 按裁决要求**确认并补强了定性措辞**，`blocking_reachability_note` 末尾现在明写：

> Status: leg (a) as stated here is a **CURRENT-MODEL theorem, not an assertion about adjudicated game semantics** - per model_stricter_faces_usage_rule it **names its dependency on registered face (1)** and is invalidated for re-proof if that face is unlocked; the owner leg above and leg (b) do not carry that dependency.

**顺带补了一条模型无关的腿**（同源于 owner 08-07 裁决行，使 (a) 不再是唯一支点）：

> Owner's 2026-08-07 adjudication reaches the same bound WITHOUT leaning on that model face: in this instance the only commodities that can reach the storage line are the 2 final products, so the sole theoretical route to 6 occupied groups - a mixed belt carrying 7 or more kinds inside one 10 s window - cannot be assembled at all.

这一条正面回答了 v1 `BLOCKERS.md` #3(b) 的隐患：格数账原先**唯一**支点是过严面 (1)，将来解锁该面会静默失效；现在同一结论另有一条只依赖冻结实例商品域的腿。

---

### 5.5 裁决 #4 · 维持 C8+C11 的合成

丢 `:115` 首句的判断被确认正确（保留会重开 ② 刚补上的缺环）。合成文本未动。

---

### 5.6 裁决 #6 · provenance 归档已建

`docs/research/canonical_batch_20260808/BOX_CACHE_PARAMETER_PROVENANCE.md` 已立（本 worktree 内，同样未提交）：份6 深挖 1 ② 条目逐字转录 ＋ 落位顺序三段机制链 ＋ 与 owner 定谳的关系说明 ＋ 本批承重点清单 ＋ 仍欠的一步（owner 游戏侧定级）。canonical 里的 provenance 指针**保留原样**，现在指得到实体。

---

## 6. C6 完整性规则的饱和扫描（派生闭包公理要求）

**扫描判据**（C6 逐字）：`every model restriction known to remove an adjudicated-game behavior` 必须在 `model_stricter_faces` 有登记。
**扫描域**：`semantics` 全部 14 个条目 ＋ `globals` 里被 `ruling_level_inputs` 点名的一条 ＋ 三条在案候选（U-02 / X1 / X3）。逐条给归属。

| # | 条目 | 归属 | 一句话 |
|---|---|---|---|
| 1 | `_note` | 不是限制 | 元注记（声明整节 descriptive-only、不被任何 solve 路径消费） |
| 2 | `axiom_kernel.axioms` A1-A11 | 不是限制 | 游戏语义本体，是被登记面的**对照物**而非限制 |
| 3 | `axiom_kernel.ruling_level_inputs` → 空矩形严格性 | 不是**模型**限制 | owner 2026-08-05 游戏定谳（空地=什么都不能有），严的是**游戏语义**不是模型；模型忠实镜像它 |
| 4 | `axiom_kernel.ruling_level_inputs` → 仓库桥排除 | **被 (5) 覆盖** | 本批 C4 新入表，正是 ⑧ 的正解 |
| 5 | `boundary_placement` | 不是限制（反限制） | 明写候选池 `MUST NOT pre-delete` 互斥角位、含 (0,0) 角——它是**防过严**条款 |
| 6 | `routing_cross_junction` | 不是限制 | 桥不能转弯/不能与非直件共格 = 游戏 A6a 镜像；X2 双声明已由份6 收口为「模拟器实现残留」，非拒真墙 |
| 7 | `mixed_commodity_flow.terminal_clause` | **被 (1) 覆盖** | class (1)/(2) 上的 front 排他即 (1) 明确登记的那半；class (3) 那半 (1) 明写「不是欠账」 |
| 8 | `connectivity_quantifier` | **被 (1)(3) 覆盖** | 该条款自己就写着「certified 模型比本量词更严：sink-front 排他 + no-orphan / selected-source-reaches-sink」，并已交叉引用 `model_stricter_faces` |
| 9 | `machine_min_clearance` | 不是生效限制 | 明写「不是 N 格护城河、机身可相邻」= 反过严澄清。附注：`patch_routing_core.py:569` `_add_port_adherence` 的 front 偏移残留在 `26_rules_handbook.md` §11 在册，**不可达**、挂 PCR / pose-bool promotion 前置，不是生效中的限制 |
| 10 | `warehouse_bridge_exclusion` | **被 (5) 覆盖** | 同 #4 |
| 11 | `protocol_storage_box_wireless` | **被 (1) 覆盖**；B2 是 open scope decision | 箱口上的 front 排他即 (1)；「箱口是否进仓储系放开」（B2 / 口数扫描臂）是**尚未成为限制的未来放开面**，不是已知移除的行为 |
| 12 | `power_source_note` | 不是限制 | 明写 pole-only 覆盖与游戏 **effect-equivalent**（mandatory hub 使每根桩必带电），既不更严也不更松 |
| 13 | `item_admission_port_exclusion` | **新发现 ⇒ 本批入表为 (6)** | 见 §5.1。**这是本次饱和扫描唯一的新发现** |
| 14 | `rate_lemma_scope` | 不是限制 | 叙事引理，`usage_rule` 已明写它不进证书、不约束模型 |
| 15 | `port_commodity_scope` | **被 (4) 覆盖** | binding 槽位单商品制，本批 C4 已点名「不同层」 |
| 16 | `power_coverage_stencil` | 不是限制 | 参数形态（12×12 相交判据），份6 盲对勘 V7 逐字命中游戏值 |
| 17 | **U-02**（两商品合流再分流 INFEASIBLE） | **不入表（合规）** | C6 的门槛是 `known to remove`；U-02 现状是 **CONCERN PLAUSIBLE 未 CONFIRMED**，且份2 Q6 反例指向它可能来自**禁令**而非 routing 表达力。已 disposition 到路由复验登记面并划归 mixflow 线（`RESEAL_MANIFEST.md:116`）。坐实后再入表，属 mixflow 线 scope |
| 18 | **X1**（模拟器存货口 `loader_1`） | **不入表（本批已关案，但关案是条件式的）** | 它曾是份6 列的唯一新拒真候选墙，本批 C9 的格数账关案：边界条带 139 格已被 46 台取货口占 138 格，存货口再要 3 格 ⇒ 141 > 139，**在任何容纳 266 mandatory 的布局里都放不下**——模型没有「移除」一条可实现的游戏行为，那条行为在本实例几何上不存在。**⚠ v3 按 F1 订正：这条关案带前提集（①产量目标冻结⇒46 ②存货口贴总线规则=取货口同款 ③口体 3×1 ④70×70），产量目标一变就要重推（与仓库桥同触发器）；且前提②的存货口半边是模拟器同标志外推、不是 owner 游戏定谳**（取货口半边才是 owner 07-18 实测）。前提集一动，本行归属要跟着重判 |
| 19 | **X3**（A8 供电外部化） | **不入表（方向相反）** | 模型把发电预算外部化 = **更松**不是更严（若翻案，266 台静态 3310 kW vs 模拟器基础 200 kW）。`model_stricter_faces` 是过严面台账；过松面属纳伪侧，份6 已挂完整性台账说明行，是另一张表的事 |

**扫描结论**：**新发现 1 条**（#13，已入表为 (6)）；覆盖 5 条；不是限制 9 条；合规不入表 3 条（U-02 / X1 / X3，理由各异）。扫描后 `model_stricter_faces` 的 `exhaustive` 声明在本批范围内**站得住**。

> 扫描口径声明：本表按 C6 的字面判据（`known to remove an adjudicated-game behavior`）执行，**不是**「所有可疑面」的清单。PLAUSIBLE 级候选（U-02）与方向相反的面（X3）刻意留在表外并各自写明去处——按 `model_stricter_faces_usage_rule`，把未坐实的东西塞进台账会反过来污染台账的证据等级。

---

## 7. v3：对抗复核四条发现的修复

复核报告：`scratchpad/fr_verify/VERIFY_REPORT.md`，总判【修 4 处后可落地】。四条全部按其建议改法执行。
**v2→v3 的全部字节差异见同目录 `V2_TO_V3.diff`**（JSON 侧恰 3 行，逐行对应 F1/F2/F4）。

### 7.1 F1（承重）· X1 格数腿补前提集与触发器，归属改成不冒充游戏定谳

**病灶**（复核原文）：冻结件把 X1 关案写成了无条件，且「前提集被丢了」「前提②本身不是 owner 定谳」——`(owner 2026-08-07, X1 closure)` 读起来是权威序最高级的游戏定谳，实际有一半是模拟器外推，而**这一半是承重的**（若存货口不受 `left_or_bottom_boundary` 约束，139 格条带的账整个不成立）。

**两处改动**（`terminal_clause.adjudicated`）：

| | v2 | v3 |
|---|---|---|
| 归属 | `(owner 2026-08-07, X1 closure)` | `(2026-08-07 reasoning closure ordered by owner - a DERIVATION over the frozen instance, not an in-game adjudication)` |
| 前提集 | 无（只隐式带住①④，靠 `the 266 mandatory instances`） | 追加整句：四条前提 (i)-(iv) 逐条列出、②的存货口半边明标 `EXTRAPOLATED FROM THE SIMULATOR … NOT owner-adjudicated`、末尾 `It re-derives on any production-target change - the same trigger as warehouse_bridge_exclusion.` |

**前提集逐条对源**（`00_master_roadmap.md:629` X1 关案登记行逐字：「前提集（动谁重推谁）：①产量目标冻结⇒46；②存货口贴总线规则=取货口同款（取货口半 owner 07-18 实测、存货口半模拟器同标志外推）；③口体 3×1；④70×70——产量目标变则重推（与仓库桥条款同触发器）」）：

| v3 写的 | 登记行原话 |
|---|---|
| (i) frozen production targets fix the pickup-port count at 46 | ①产量目标冻结⇒46 |
| (ii) storage-side loader obeys the same `left_or_bottom_boundary` rule；pickup 半 owner 07-18 实测、storage 半模拟器外推 | ②存货口贴总线规则=取货口同款（取货口半 owner 07-18 实测、存货口半模拟器同标志外推） |
| (iii) a 3x1 port body | ③口体 3×1 |
| (iv) the 70x70 grid | ④70×70 |
| re-derives on any production-target change, same trigger as `warehouse_bridge_exclusion` | 产量目标变则重推（与仓库桥条款同触发器） |

**这条修复消掉的不对称**：同批 face (5) 对 `warehouse_bridge_exclusion` 写着 `target-conditional`、要求全局最优时按显式 scope restriction 处理；roadmap 明说 X1 与仓库桥**同触发器**，v2 却给了它无条件待遇。v3 后两者待遇一致。它同时兑现 owner 派生闭包公理的「派生规则一等登记**带前提集**」，并避免了 08-07 刚立家规点名的证据等级混用。

**复述同步三处**（复核只点了 §6 第 18 行，另两处是同一复述的其它落点，一并改，均记在 `V2_TO_V3.diff`）：本表 §2 C9 的 AFTER 引文、§6 扫描表第 18 行、`BLOCKERS.md` §3 的 X1 条目。

### 7.2 F2 · 10/17 订正记录移进 `recompute_scope`，并补声明

选定路径 = **保留记录**（不是只在 DRAFT_DIFF 声明）。落点与文本见 §2 C18；被删原句与处置理由见 §2 C16 的「段内删除声明」。规则 A 的 `[保留]` 从 5 例增至 6 例。

### 7.3 F3 · 一处 size-only pin 提及写进史料名单

`docs/research/p2_0_specialized_20260807/refute_round1/GAME_RULE_IMPACT_AUDIT.md:17`（tracked）含 `40,371 字节`但**不含 sha**，所以 sha 扫描照不到、v2 的不改名单也没点它——落地当天走 §7 验收步 `rg -i '40,371|40371'` 时它会以「名单外残留」跳出来，逼落地席现判。已按复核判断（属史料：记的是某轮审查当时覆盖了哪一版规则文件，不是现行状态断言）写进 `RESEAL_CHECKLIST.md` §1C 点名。**canonical 字节零改动。**

### 7.4 F4 · 实例 discharge 里的「≤3 种」补模型依赖指针

`terminal_clause` 实例 discharge 中 `pure-flow commodity kinds are at most 3 against 6 groups` 与 owner 其他数字并排、不带任何 current-model 提示，而 `blocking_reachability_note` 对**同一个「≤3」的来路**标了 leg (a) 是 CURRENT-MODEL theorem。v3 在该句后加指针：

> `- see protocol_storage_box_wireless.slot_count_clause.blocking_reachability_note for the model dependence of that count;`

只读 `terminal_clause` 的人不会再把「≤3」当成已定谳的游戏语义。该段真正承重的仍是「仅 2 终品」那条模型无关腿，未动。

### 7.5 v3 机器复验

```
size / sha256          59,989 B / c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0
CR 字节                 0
strict_json / jsonschema / pydantic / load_templates()      全 PASS
换进 rules/ 跑内容门     85 passed in 0.92s（跑完已还原，sha = b675fb6a…）
非 ASCII 字符集         ['§','—','明','目','说','项']（与 v2 相同，未新增字符类）
顶层键 / 非 semantics 子树                                  零差异
owner 08-06 定谳句       仍逐字在（机器核对）
```
