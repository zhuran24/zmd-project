# F5 orbit-aware lifting soundness 论证与实施规格 v1

**Status:** HISTORICAL_OR_PLAN（研究层设计稿；F5 生产接入属 P1.3，本稿不改生产代码、不动锁面）
**Authored:** 2026-07-04
**先例定位：** `PROJECT_LOCK.md` §3A（2026-05-22）已强制 "state 必走 group-orbit 而非 per-instance，消 10^134 label symmetry；AnonymousSlotRef multiset 包含语义跨 candidate enumeration order 必 sound（slot_index 仅 debug/serialization 用，不参与 soundness 推理）"。本稿不是提出新方向，而是**给已锁定的方向补上它欠的 soundness 定理、机器可查前提和实施规格**——历史文档（`docs/项目说明/05_open_questions.md:459-483`）推荐了方案 A（orbit-aware pattern lift）但明说 true interchangeability 未被形式化证明（`manufacturing_cluster_trap.md:86-99`）。

---

## 1. 事实基线（2026-07-04 只读调查核验）

### 1.1 修正历史叙事："132!" 是错的，真实轨道结构是 8 类

132 个 `manufacturing_3x3` mandatory 实例**不是**一个同质类。按 `(facility_type, operation_type)` 的真实分组（`data/preprocessed/machine_counts.json`；skeleton 等价类 `same_operation_instances:<op>`，`material_connection_skeleton.json:458-463`）：

| operation_type | n | | operation_type | n |
|---|---:|---|---|---:|
| crusher_blue_iron | 34 | | crusher_sandleaf | 11 |
| refinery_blue_iron | 34 | | molding_bottle | 6 |
| crusher_source | 18 | | parts_maker | 6 |
| refinery_steel | 17 | | crusher_buckwheat | 6 |

合计 132。跨 operation_type **不可交换**的直接反证：recipe commodity 不同（`refinery_blue_iron` 吃 ore 出 block，`crusher_blue_iron` 吃 block 出 powder，`rules/canonical_rules.json:202-230`）。因此标签对称群不是 S₁₃₂ 而是 **G = Π_g S_{n_g}**（乘积群，g 遍历全部 `(facility_type, operation_type)` 组，含 manufacturing 8 组、`boundary_storage_port` 46、以及 optional slot families）。置换墙从 "132!≈10^224" 修正为 Π n_g!（仅 manufacturing 部分 ≈ 34!²·18!·17!·11!·6!³ ≈ 10^105）——数字变小，墙照样在，提升的价值不变。

### 1.2 机器现状：提升的"机械"已存在一半，缺的是定理

已存在（全部实测）：

- **F5 literal 已是匿名 slot 级**：`CutLiteral(AnonymousSlotRef(group_id, slot_index), pose_id)`，无 instance_id、无坐标（`src/cuts/lifecycle.py:155-165`）；
- **multiset 评估器已丢弃 slot 身份**：`evaluate_literal_multiset` 按 `(group_id, pose_id)` 多重集做包含判定（`src/cuts/lifecycle.py:1014-1070`）；
- **master 施加 whole-layout nogood 时已做标签擦除**：conflict member 从 instance_id 映射到 `mandatory::{group_id}` 的 presence literal（"组内任一 slot 实现该 pose"），以 `Σ present ≤ N-1` 形式落约束；alias 冲突 fail-closed（`src/models/exact_coordinate_master.py:6949-7078`）；
- **master 对称序**：每组 slot 按 `order_key` 单调序，第二序（signature）过 same-order gate 才加（F-GM-R8-SYM-01，`PROJECT_LOCK.md:324`；`exact_coordinate_master.py:2569-2628, 2911-2915`）；
- **slot-collision FP 陷阱已登记**：oracle 判 `[(g,0,pA),(g,0,pB)]` INFEASIBLE 是"单 slot 不能两 pose"的平凡真，multiset 提升后会错剪合法布局——validator 已禁 cert 内 slot 复用（`PROJECT_LOCK.md:406-409`；`src/cuts/families/pattern_nogood.py:239-265`）。

缺失（本稿要补的）：

- **交换性定理**：没有任何地方证明"同组实例在全部谓词语义下可交换"——评估器直接假设了它；
- **前提的机器化**：交换性依赖的数据同质性没有结构门守护（将来谁往实例记录里加一个 per-instance 字段，提升就静默变 unsound）；
- **与 master 序的复合论证**：轨道 cut 与 order_key 序同时存在时不删光等价类的证明；
- F5 sub-problem oracle 的真实 adapter 未生产化（Phase 1.5+，`src/cuts/oracles/pattern_nogood_oracle.py:89-105`）。

## 2. 形式化：群作用与两个定理

### 2.1 记号

- 组 g 的实例集视为匿名 slot 集 S_g = {0,…,n_g−1}；全局标签群 **G = Π_g S_{n_g}** 以逐组置换作用于"带标签的解"（每 slot 一个 pose 赋值 + 由此派生的 binding/routing/power 选择）。
- 一个 **pattern** π = 各组的 (pose 多重集) 组合；其带标签实现 = 任一把多重集内 pose 分配到具体 slot 的注入。F5 cert 的 `forbidden_pose_pattern`（三元组列表）是 π 的一个带标签代表。

### 2.2 定理 1（谓词不变性 / 交换性）

**命题**：设 σ ∈ G，A 是任一带标签完整（或部分）解。则 A 满足谓词集 {(1)…(6)}（及未来 P7）当且仅当 σ(A) 满足；且二者 ghost 目标值相同。

**证明结构 = 逐谓词的数据依赖审计**（每行都是一个独立证明义务，实施时逐条出红测）：

| 谓词 | 语义依赖的数据 | label-invariance 依据（实测证据） |
|---|---|---|
| (1) ghost 空 / (2) 不重叠 | 各实例的 pose 几何 | pose 池按 template 共享（`placement_generator.py:485-501`：pool key = canonical template；pose 字段无 instance 维度），几何谓词只看被选 pose 的 cell 集——多重集不变 |
| (3) placement_rule | template 级规则 | 规则挂在 `facility_templates`，无 per-instance 规则（`instance_builder.py:62-68` 仅 7 字段） |
| (4) binding 精确计数 | operation profile + pose | binding domain 由 `(operation_type, pose)` 枚举（`binding_subproblem.py:985-1000`）；需求按 operation_type 聚合（`operation_profiles.py:133-189`）；变量名含 instance_id 但仅是命名，不进语义 |
| (5) routing 连通 | port specs 的 (commodity, 几何) | port spec 的 commodity 由 operation profile 定、坐标由 pose 定；instance_id 只进诊断标签（`routing_subproblem.py:451-472, 994-1039`） |
| (6) power 覆盖 | template 级 needs_power + pose 几何 | `master_model.py:2422-2424, 3733-3744`：power 索引按 template/pose |
| (P7 吞吐，前瞻) | operation 速率 + selected graph | 速率按 operation_type（`operation_profiles.py:21-31`）——交换性对 P7 自动成立，与 `p2_0_throughput_certification_paradigm_design_v1.md` 兼容 |
| 目标 | 仅 ghost rect | 与实例标签无关 |

**前提（必须机器化，见 §4）**：P-HOM——同组实例的 mandatory 记录除 `instance_id` 外逐字段相同（含 `bound_type`/`solve_modes`/`notes`）；operation profile 仅按 operation_type 键控；pose 池仅按 template 键控；需求仅聚合形态。当前数据全部成立（`instance_builder.py:52-70`；`mandatory_exact_instances.json` 抽查），但**没有门在守**。

### 2.3 定理 2（轨道提升 soundness）

**命题**：设 sub-problem oracle 在定理 1 的前提下对带标签 pattern π₀（某组内两两不同 slot）复验为 INFEASIBLE（含独立复验）。则对**任意**带标签解 A，若 A 的逐组被选 pose 多重集包含 π₀ 的多重集像 [π₀]，A 不可行。

**证明**：A 的多重集包含 [π₀] ⇒ 存在 σ ∈ G 使 σ(A) 的具体 slot 赋值字面上扩展 π₀（把 A 中承载 [π₀] 各 pose 的 slot 重标到 π₀ 指名的 slot；π₀ 无 slot 复用保证注入存在）。oracle 的 reject 语义是"任何扩展 π₀ 的完整解都不可行"；故 σ(A) 不可行；由定理 1，A 不可行。∎

**两个边界条件（都已有机器对应物，必须保持）**：

1. **无 slot 复用前提**：π₀ 内同一 `(group_id, slot_index)` 出现两次时，"INFEASIBLE" 可能是平凡真，提升会产生 FP——validator 禁令（`pattern_nogood.py:239-265`）是定理 2 的前提，不是工程洁癖，红测必须钉死"去掉禁令 → 构造出 FP"。
2. **oracle verdict 本身必须 label-invariant**：oracle 若在语义里读了 instance 标签（而非 (group, pose) 数据），定理 1 的传递断裂。实施义务：真实 adapter（binding/routing/PCR）生产化时，输入必须经**规范重标**（canonical relabeling：按 `canonical_sort_assignment` 序把 pattern 映到规范代表，`bounded_core_minimizer.py:115-125` 已有），使 oracle 只见规范形。

### 2.4 引理（与 master 对称序的复合安全）

master 的 order_key 单调序是**代表元选择**：每个 G-等价类至少留一个满足序的代表（F-GM-R8-SYM-01 的表述与 same-order gate 保证）。轨道 cut 是 **G-不变集合的删除**：删的是整个等价类。两者复合：被 cut 删的类整类消失（正确——定理 2 证明整类不可行）；未被 cut 删的类，其序代表仍存活。故复合不产生"类内代表被序删光而类未被证不可行"的 false-INFEASIBLE。**注意反方向陷阱**：若未来引入非 G-不变的 cut（读 slot 身份的 cut），此引理失效——这正是 §3A "slot_index 不参与 soundness 推理" 的深层原因，红测应含一个"标签敏感 cut + 序 = 删光合法类"的反例展示。

## 3. 与既有禁令的边界（本稿不越界的声明）

- **仍然死的**：跨 operation_type 合并轨道（recipe 不同，§1.1 反证）；跨 candidate/ghost 的 cut 复用越过 scope 绑定（Q5 / Path 18 LIC，`05_open_questions.md:83-94`；scope 字段 `ghost_rect_id`/`source_digest` 机制不动，`lifecycle.py:174-188, 941-984`）；F5+F6/F3 复合 cut（历史方案 B）与 instance partition（方案 C）继续按 `05_open_questions.md:459-483` 挂起，本稿采纳并形式化的是方案 A。
- 提升只作用于**标签**，不触碰几何、scope、ghost 依赖声明——F5 的 ghost 依赖仍随 sub-problem 决定（binding→GHOST_AGNOSTIC 合法，routing→必绑，`02_mathematical_foundations.md:347-376`）。

## 4. 实施规格（P1.3 时执行；按依赖排序）

1. **P-HOM 结构门**（先行，独立小步）：新 checker 校验——同组 mandatory 记录 modulo instance_id 逐字段相等；`operation_profiles` 无 per-instance 键；`facility_pools` 无 instance 维度。挂进 preflight；任何将来引入 per-instance 字段的改动被迫显式面对交换性破坏。产出 = 定理 1 前提的机器锚。
2. **规范重标层**：generator 在 minimize 前、oracle query 前把 pattern 映到规范代表（组内按 pose_id 字典序占用 slot 0..k-1）；cert 存规范形。消除"同一轨道的 cut 因标签不同重复生成"（这是撞墙计数虚高的直接来源）。
3. **validator 增补**：现有检查（slot 无复用、pose ∈ pose_domain、frozenset 等值）之上，加"cert 必须是规范形"检查——非规范形 = schema_err（fail-closed，防重复与防 canonical drift）。
4. **oracle adapter 生产化**（P1.3 主工作量，与 F5 本体同期）：binding/routing adapter 的输入接规范重标层；每个 adapter 出一条 label-invariance 红测（对随机 σ 重标输入，verdict 必须不变）。
5. **master attach**：已有 presence nogood 机械（§1.2）直接承载 F5 literal cut 的施加；alias fail-closed 保留。Step 8 接入时 F5 无需新增 master 端表达形式。
6. **验收 telemetry**（沿用历史判据，`05_open_questions.md:481-483`）：生产 trial 中 manufacturing 组 F5 cut 计数 >10⁵ = 提升失效（撞墙）；<10³ = 工作。加一个新指标：规范化去重命中率（同轨道重复 pattern 被去重的比例）——它直接度量提升价值。
7. **红测清单**：①slot-collision FP 反例（去禁令必现）；②标签敏感 cut × 序删光类反例（§2.4）；③σ-重标 verdict 不变性（每 adapter）；④P-HOM 门对注入 per-instance 字段 fail-closed；⑤规范形 validator 拒非规范 cert。

## 5. 组合收益计数

带标签 pattern 空间（大小 k 的组内 pattern）约 C(n_g,k)·k!·|pose|^k；轨道商后为 pose 多重集计数 C(|pose|+k−1, k) 量级——每组 k 阶 pattern 缩减约 n_g!/(n_g−k)! 倍。对 n=34 组、k=8 的 pattern，缩减 ≈ 34·33·…·27 ≈ 2×10¹²。全 132 实例 full-assignment nogood 的极端情形从 Π n_g! ≈ 10¹⁰⁵ 个等价重复缩到 1 个多重集 cut。这就是历史 "132! 撞墙" 的修正版本量化。

## 6. 开放问题

1. oracle adapter 对**部分赋值**上下文的 verdict invariance：state 中未涉组的已选 pose 也要参与重标吗？（建议：state 同样过规范重标——需要在 adapter 规格里定死）
2. 轨道 cut 与 whole-layout nogood 独立复验（I1）的组合：I1 复验的是带标签 conflict_set，提升后复验对象应是规范代表——I1 输入是否也走重标层，P1.3 定。
3. `boundary_storage_port`（46 同质）与 optional families 的同型处理：定理与机器完全同构适用，实施时一并覆盖还是先 manufacturing 8 组试点，P1.3 排期定。
4. 方案 B（跨 family 复合 cut）的重启条件：若验收 telemetry 显示提升后仍撞墙（>10⁵），再议。

---

*v1 完。对抗审查工作包（含本稿 + 全部证据源文件）另行打包。*
