# F5 orbit-aware lifting soundness 论证与实施规格 v2

**Status:** HISTORICAL_OR_PLAN（研究层设计稿；F5 生产接入属 P1.3）
**Authored:** 2026-07-04（v2，取代 `p1_3_f5_orbit_lift_soundness_design_v1.md`；同日 v2.1 修订——本地独立核查回收：P-HOM 验证状态措辞收敛、谓词审计表内联自 v1）
**v2 修订输入**：GPT Pro 对抗审查（2 BLOCK + 4 CONCERN + 2 NOTE，归档 `p2_design_external_reviews_20260704/f5_*`），其复核脚本在真实数据上跑通（mandatory-side P-HOM 验证、计数复核、两个 toy FP 复现；runtime pose 池与 adapter 源码仍须 P1.3 结构门闭合）。

**v1→v2 关键变更**：
- 【BLOCK-1】定理 2 增加 **liftable-reject 前提**（原 v1"开放问题 1"升级为定理前提）：oracle 的 INFEASIBLE 必须是"任何扩展 π₀ 的完整解均不可行"的封闭核判决；依赖 core 外 mutable state 的判决不得生成 F5 cut。
- 【BLOCK-2】multiplicity 保真约束：v1 说 master presence nogood "直接承载" F5——对含重复 `(group, pose)` 的 pattern **错误**（boolean presence 会把"≥2 份才不可行"坍缩成"≥1 份即不可行"= FP）。v2 采用方案 A：validator 禁 cert 内重复 `(group_id, pose_id)`。
- 【CONCERN-1】规范重标从"排序去重"升级为 **idempotent canonical_relabel**（slot 重标 0..k-1）。
- 【CONCERN-2】P-HOM 门范围扩到运行时 `candidate_placements.json` 工件本体 + `orbit_homogeneity_digest` 注入 preflight 与 cut replay scope。
- 【CONCERN-4】计数修正：8 组阶乘积 = **10^123.47**（v1 误写 10^105）；(34)_8 = **7.32×10^11**（v1 误写 2×10^12）；两种计数口径分列。
- 【NOTE-1】P-HOM 前提的 **mandatory 记录侧**已在真实数据上机器验证（266 条、19 组、modulo instance_id 逐字段违例 0）；**runtime pose 池工件侧未验证**，属 P-HOM 结构门待建范围——两侧都闭合前不得宣称"P-HOM 已验证"。

---

## 1. 事实基线（v1 §1 继承，修正计数）

- 真实轨道结构：`manufacturing_3x3` 按 operation_type 分 8 组（34/34/18/17/11/6/6/6，合计 132）；跨组不可换（recipe 商品不同）。全 mandatory 19 组。
- 标签对称群 G = Π_g S_{n_g}。置换墙修正值：8 个 manufacturing 组 `log10(Π n_g!) = 123.47`；全部 mandatory 组 = 10^243.5。
- 机器现状（已存在）：`AnonymousSlotRef` 匿名 slot literal、`evaluate_literal_multiset` 多重集评估、master 组级 presence nogood（**注意**：`_conflict_pose_entries` 对重复抽象 presence fail-closed——master 当前根本无法表达 multiplicity≥2 的 cut，与 §2.3 方案 A 一致）、order_key 组内单调序 + same-order gate。
- 缺失：交换性定理、前提守门、liftable-reject 契约、规范重标——本稿补齐设计层。

## 2. 形式化：两个定理（v2 修订版）

### 2.1 记号

组 g 的实例集 = 匿名 slot 集 S_g；G = Π_g S_{n_g} 逐组作用于带标签解。pattern π = 各组 pose 多重集；带标签代表 = 多重集到具体 slot 的一个注入赋值。

### 2.2 定理 1（谓词不变性）——mandatory 侧已验证，完整 P-HOM 仍是待建结构门

σ∈G、A 为带标签（完整或部分）解 ⇒ A 与 σ(A) 谓词满足性等价、目标值相同。逐谓词数据依赖审计表如下；“已核实”只表示本审计包内源码/数据可直接支持，“待门控”表示 P1.3 必须用实际生产工件和相应源码红测闭合后，才能宣称 P-HOM 成立。

| 谓词 | 语义依赖的数据 | 当前证据状态 | P1.3 必过结构门 |
|---|---|---|---|
| (1) ghost 空 / (2) 不重叠 | 被选 pose 几何 | 本包未含 `placement_generator.py` 与 `candidate_placements.json`，不能仅凭生成器意图证明；几何谓词本身只看 pose cell 集 | 对实际 `candidate_placements.json.facility_pools` 做 schema 审计：pose 字段不得含 `instance_id`/slot/per-instance key；同一 `facility_type` pool 被同组实例共享；若 pose_id 到 attach key 非一一映射，必须显式 fail-closed |
| (3) placement_rule | template 级规则 | `instance_builder.py:62-68` 的 manufacturing 记录除 `instance_id` 外只有 `facility_type/operation_type/is_mandatory/bound_type/solve_modes/notes`；规则在 `canonical_rules.json.facility_templates` 的 template 层 | mandatory 记录 modulo `instance_id` 逐字段同质；新增 per-instance 规则字段 fail-closed |
| (4) binding 精确计数 | operation profile + pose | `operation_profiles.py:78-110,148-189` 支持“profile/需求按 operation_type 聚合”；本包未含 `binding_subproblem.py`，不能核实 domain 枚举 | adapter 红测必须证明 binding domain 只由 `(operation_type, canonical_pose)` 和 immutable scope 枚举；任何 `instance_id` 仅可出现在诊断字符串，且不得进入约束、目标或 cache key |
| (5) routing 连通 | port specs 的 (commodity, 几何) | commodity/profile 侧可由 `operation_profiles.py` 支持；本包未含 `routing_subproblem.py`，不能核实 port spec 枚举 | adapter 红测必须证明 port specs 只由 operation profile 与 pose geometry 生成；任何 current owner/blocker 若参与证明，必须提升为 core literal 或拒绝生成 F5 |
| (6) power 覆盖 | template 级 needs_power + pose 几何 | `master_model.py:2422-2424` 按 template 取 `needs_power`；`master_model.py:3733-3794` 的支持索引按 template/pose_idx 扩展，未见 instance_id 参与 | 若 power adapter 接 F5，必须继承 CUT-R12-H1 的完整固定占用 support 规则；否则不得把依赖 mutable occupancy 的 INFEASIBLE 作为 F5 |
| (P7 吞吐，前瞻) | operation 速率 + selected graph | `OperationPortProfile` 为 operation_type/facility_type/rates 级；P7 尚未进入 F5 certified scope | P7 接入前必须补独立谓词不变性红测 |
| 目标 | 仅 ghost rect | scope 由 `ghost_rect_id`、`blocked_cells_hash`、`exterior_blocks_hash` 绑定 | ghost 相关性必须在 `query_liftable` 的 immutable_scope 与 `CutScope` 中一致声明 |

**前提 P-HOM 的现状与守门**：
- mandatory 记录侧：已机器验证 19 组 266 条 modulo `instance_id` 零违例。
- runtime pose 池侧：本稿不得宣称已验证。master 实际消费 `candidate_placements.json`；该工件缺失、漂移或新增 per-instance 字段时，定理 1 前提未闭合。
- P1.3 必须产出 `orbit_homogeneity_digest = sha256(canonical_json({mandatory_mod_instance_id, operation_profile_projection, candidate_facility_pools_projection, attach_key_projection, predicate_adapter_versions}))`，并把该 digest 同时写入 certified preflight、F5 cert replay scope 与 cut-store scope。digest 缺失、计算失败、工件不可得、字段新增未白名单化或 replay 漂移一律 fail-closed。

### 2.3 定理 2（轨道提升 soundness）——前提收紧版

**前提**（三条缺一不可，每条对应红测）：

1. **P-HOM**（§2.2）。
2. **无重复约束（BLOCK-2 / 方案 A）**：cert 内禁止重复 `(group_id, slot_index)`（既有），禁止重复 `(group_id, pose_id)`（v2 新增），并且禁止两个 literal 解析到同一 master attach presence key `presence_key=(group_id, attach_pose_key(pose_id))`。当前实现应要求 `attach_pose_key` 与实际 master pose_idx/pose_tuple 一一对应；解析器不可用或发现 alias 时 fail-closed。理由：同组两 slot 同 pose 在 manufacturing_3x3 几何上必重叠（谓词 2 平凡不可行），此类核的 INFEASIBLE 是平凡真；multiset 提升或 boolean presence attach 会把“出现 ≥2 才不可行”坍缩成“出现 ≥1 即禁”，错剪合法解。不同 pose_id 且不同 presence_key 的同组双 literal 仍允许，master cut 表达的是“两者同时 present 不可行”，不会坍缩为单 pose 禁令。若未来需要 multiplicity≥2 的非平凡 cut，必须先给 master cardinality-aware attach（count/threshold literal），在此之前方案 A 是唯一安全形态。
3. **liftable reject（BLOCK-1）**：oracle 的 INFEASIBLE 必须证明“任何完整解，只要扩展 π₀ 的任一带标签代表，即在当前 immutable_scope 下不可行”。`INFEASIBLE` 的语义是生产谓词宇宙中的无扩展性：剩余 placement、binding、routing、power/throughput 子变量任意补全都不能满足，而不是某个已选 incumbent 上下文下的失败。现行 adapter 协议 `query(core, state, deadline)` 允许读取 state 中 core 外的 mutable 上下文（当前 incumbent 的其他已选 pose、cell owner、routing blocker），因此 P1.3 必须替换为 `query_liftable(core, immutable_scope, deadline)`。`immutable_scope` 白名单仅含：P-HOM digest 覆盖的冻结工件、group demand/domain、canonical_rules/facility_templates/operation profiles、actual candidate pools、commodity/static IO 常量、以及经 `CutScope` 绑定的 ghost/exterior scope；不得含 `selected_poses`、`cell_owner`、当前 binding/routing decision、incumbent、solver hint、mutable cache 结果。ghost rect 若参与判决必须作为 scope-bound 常量进入 immutable_scope 并与 `ghost_rect_id/blocked_cells_hash/exterior_blocks_hash` replay 一致；若判决需要 mutable occupancy/blocker，要么把 blocker 提升为 core literal，要么该判决禁止生成 F5。

**命题**：满足前提 1–3 时，oracle 对 π₀ 的 INFEASIBLE ⇒ 任意带标签解 A，若其逐组被选 pose 多重集包含 [π₀]，则 A 不可行。

**证明**（NOTE-2 补严版）：设 A 的组 g 被选 pose 多重集 ⊇ [π₀]|_g。对每组 g：取 A 中承载 [π₀]|_g 各 pose 的 slot 集 T_g（|T_g| = k_g，前提 2 保证 π₀ 无 slot 复用、无 presence-key alias，多重集元素两两可分配），构造 S_{n_g} 中把 T_g 映到 π₀ 指名 slot 的置换（先定义 T_g 上的双射，再任意补全到 S_{n_g} 的完整置换，补全存在因为剩余 slot 集与剩余像集等势）。令 σ = 各组置换之积，则 σ(A) 字面扩展 π₀。由前提 3，σ(A) 在同一 immutable_scope 下不可行；由定理 1（前提 P-HOM，且 immutable_scope 不含标签敏感 mutable state），A 不可行。canonical_relabel 只选择 π₀ 的序列化代表；实现必须保证 cert、minimizer trial core 与 oracle re-query 是同一个 canonical core，不得用 silent dedup 或后置重标替代一次已复验的 core。∎

### 2.4 与 master 对称序的复合（含 CONCERN-3 澄清）

复合安全引理同 v1（序保代表元 × 轨道 cut 删整类）。**CP-SAT `symmetry_level=3` 的定位**：它是 solver 内部搜索/预处理策略，不是建模层第二全序，不落入 F-GM-R8-SYM-01 的"至多一个全序"计数——前提是消费方式保持"TIMEOUT/UNKNOWN → no-cut、只有可复验 INFEASIBLE 产 cut"。若未来把 solver 内部对称产物外显为约束、或把 timeout 当穷尽证明，需重证。

## 3. 与既有禁令的边界

同 v1 §3（跨 operation_type 合并死、跨 candidate 越 scope 死、方案 B/C 挂起）。v2 补一句：liftable-reject 前提正是「Q5 跨 instance lifting 必死」教训在组内轨道场景的对偶——那里死于数据身份破坏可交换性，这里防的是**上下文**破坏可交换性。

## 4. 实施规格（v2 修订版，P1.3 执行）

1. **P-HOM 结构门**（范围扩大版，§2.2）：三件套升级为五件套：mandatory modulo `instance_id`、operation profile projection、actual candidate pool projection、attach-key projection、adapter-version projection。五件套 hash 为 `orbit_homogeneity_digest`，写入 preflight、F5 cert payload 或 scope artifact hash、cut replay scope；缺失或漂移 fail-closed。
2. **canonical_relabel（CONCERN-1 修正）**：定义 idempotent 且不 silent-dedup 的函数。逐组收集 literal，按 `(pose_id, occurrence_serial)` 排序后把 slot 重标为 `0..k_g−1`；`occurrence_serial` 由同 pose 的稳定枚举产生。应用点：generator 初始 full assignment、deletion minimizer 每个 trial core、oracle query 输入、cert 存储、validator re-query。任何阶段若先前复验的是旧 core，后续重标/去重后的 core 必须重新复验。
3. **validator 增补**：既有检查 + 禁重复 `(group_id, slot_index)` + 禁重复 `(group_id, pose_id)` + 禁重复 `presence_key` + `cert == canonical_relabel(cert)`（非规范形 = schema_err）。validator 不得用 canonical_relabel 的输出替换非规范 cert 后继续验证；必须拒绝。
4. **oracle adapter 生产化**：废弃 `query(core, state, deadline)` 的 F5 cut 资格；只允许 `query_liftable(core, immutable_scope, deadline)` 生成 F5。每 adapter 至少四条红测：σ-重标 verdict 不变性、上下文依赖判决被拒、mutable blocker 未入 core 时拒绝、ghost/exterior scope replay 漂移拒绝。
5. **master attach**：presence nogood 机械直接承载仅限 `presence_key` 无重复的 pattern；解析 pose_id 到 attach key 失败或 alias 时 fail-closed。若未来接 cardinality-aware attach，必须给 count/threshold literal 的证书语义和 Step 7 evaluator 同步重证。
6. **验收 telemetry**：cut 计数阈值（>10⁵ 撞墙 / <10³ 工作）+ 规范化去重命中率 + digest/relabel/immutable-scope 拒绝计数。
7. **红测清单**（v1 五条基础上增补）：⑥重复 `(group,pose)` cert 必拒 + 若放行则构造出 multiplicity 坍缩 FP；⑦两个不同 pose_id alias 到同一 presence_key 必拒；⑧上下文依赖 oracle 判决生成 F5 被拒（toy S1/S2 反例已有复现脚本）；⑨canonical_relabel 幂等性、非 silent-dedup、minimizer 中途重标一致性；⑩candidate_placements 注入 per-instance 字段时 P-HOM gate fail-closed。

## 5. 组合收益计数（CONCERN-4 修正版）

两种口径（P = 组内 pose 池大小，k = pattern 阶）：
- 允许重复 pose：带标签空间 C(n,k)·P^k，轨道商 C(P+k−1,k)；
- **禁止重复 `(group,pose)`（v2 采用）**：带标签空间 C(n,k)·(P)_k，轨道商 C(P,k)，缩减因子精确 = n!/(n−k)!。
n=34、k=8 时缩减 (34)_8 = 34·33·…·27 = **7.32×10¹¹**。full-assignment 极端情形：等价重复从 Π n_g!（8 组 = 10^123.5，全 19 组 = 10^243.5）缩到每轨道 1 条。

## 6. 开放问题（v1 四条的 v2 状态）

1. ~~部分赋值上下文的 verdict invariance~~ → 已升级为定理前提 3（liftable reject），且 immutable_scope 白名单见 §2.3；不再作为开放问题保留。
2. ~~I1/F5 复验输入是否过重标层~~ → F5 相关 generator、minimizer、validator re-query 一律必须过 canonical_relabel；若遗留 I1 名称桥接 whole-layout nogood，桥接层也必须证明其输入与 F5 cert core 相同或 fail-closed。
3. boundary_storage_port(46) 与 optional families 的同型覆盖——维持开放（先 manufacturing 8 组试点）。
4. 方案 B（跨 family 复合 cut）重启条件——维持（telemetry 撞墙再议）。
5. **新增**：multiplicity≥2 cut 的 cardinality-aware attach（方案 B'）——仅当发现真实需要"同 pose 多份才不可行"的非平凡核时立项（几何平凡核不算）。

---

*v2 完。v1 保留为历史快照；外审原件与复核脚本见 `p2_design_external_reviews_20260704/`。*
