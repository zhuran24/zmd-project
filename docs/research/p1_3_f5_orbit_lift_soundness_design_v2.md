# F5 orbit-aware lifting soundness 论证与实施规格 v2

**Status:** HISTORICAL_OR_PLAN（研究层设计稿；F5 生产接入属 P1.3）
**Authored:** 2026-07-04（v2，取代 `p1_3_f5_orbit_lift_soundness_design_v1.md`；同日 v2.1 修订——本地独立核查回收：P-HOM 验证状态措辞收敛、谓词审计表内联自 v1）
**v2 修订输入**：GPT Pro 对抗审查（2 BLOCK + 4 CONCERN + 2 NOTE，归档 `p2_design_external_reviews_20260704/f5_*`），其复核脚本在真实数据上跑通（P-HOM 全量验证、计数复核、两个 toy FP 复现）。

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

### 2.2 定理 1（谓词不变性）——前提 mandatory 侧已验证，pose 池侧与守门待建

σ∈G、A 为带标签（完整或部分）解 ⇒ A 与 σ(A) 谓词满足性等价、目标值相同。逐谓词数据依赖审计表（v2.1 起内联，原 v1 §2.2；每行是独立证明义务，实施时逐条出红测）：

| 谓词 | 语义依赖的数据 | label-invariance 依据 |
|---|---|---|
| (1) ghost 空 / (2) 不重叠 | 被选 pose 几何 | pose 池按 template 共享（`placement_generator.py:485-501`），几何谓词只看 pose cell 集——多重集不变 |
| (3) placement_rule | template 级规则 | 实例记录仅 7 字段、无 per-instance 规则（`instance_builder.py:62-68`） |
| (4) binding 精确计数 | operation profile + pose | domain 由 `(operation_type, pose)` 枚举（`binding_subproblem.py:985-1000`）；需求按 operation_type 聚合；变量名含 instance_id 但仅命名不进语义 |
| (5) routing 连通 | port specs 的 (commodity, 几何) | commodity 由 profile 定、坐标由 pose 定；instance_id 只进诊断标签（`routing_subproblem.py:451-472, 994-1039`） |
| (6) power 覆盖 | template 级 needs_power + pose 几何 | power 索引按 template/pose（`master_model.py:2422-2424, 3733-3744`） |
| (P7 吞吐，前瞻) | operation 速率 + selected graph | 速率按 operation_type——与吞吐稿 v2 兼容 |
| 目标 | 仅 ghost rect | 与标签无关 |

**前提 P-HOM 的现状与守门**：
- mandatory 记录：**已全量机器验证**——19 组 266 条 modulo instance_id 零违例（外审复核脚本 `f5_verify_review_claims_gpt.py`）。
- **但验证范围不含运行时 pose 池工件**：master 实际消费 `candidate_placements.json`；"pose 池无 instance 维度"目前只有生成器意图证据（`placement_generator.py:485-501`），工件本体可能漂移。P-HOM 结构门必须覆盖三件：①mandatory 全记录同质；②operation profiles 无 per-instance 键；③**实际 `candidate_placements.json.facility_pools` 无 instance 维度字段**。三者合并产出 `orbit_homogeneity_digest`，注入 certified preflight 与 cut replay scope；digest 缺失/漂移/新增 per-instance 字段一律 fail-closed。

### 2.3 定理 2（轨道提升 soundness）——前提收紧版

**前提**（三条缺一不可，每条对应红测）：

1. **P-HOM**（§2.2）。
2. **无重复约束（BLOCK-2 / 方案 A）**：cert 内禁止重复 `(group_id, slot_index)`（既有）**且禁止重复 `(group_id, pose_id)`**（v2 新增）。理由：同组两 slot 同 pose 在几何上必重叠（谓词 2 平凡不可行），此类核的 INFEASIBLE 是平凡真；multiset 提升后（"该 pose 出现 ≥1 即禁"）严格强于 oracle 所证（"出现 ≥2 才不可行"），错剪合法解。此类几何平凡由 no-overlap/F6 承担，不进 F5。若未来需要 multiplicity≥2 的 cut，必须先给 master cardinality-aware attach（count/threshold literal），在此之前方案 A 是唯一安全形态——master 现有 alias fail-close 也恰好挡住这类 cut 的表达。
3. **liftable reject（BLOCK-1）**：oracle 的 INFEASIBLE 必须证明"任何完整解，只要扩展 π₀ 的**任一带标签代表**，即不可行"。现行 adapter 协议 `query(core, state, deadline)` 允许读取 state 中 core 外的 mutable 上下文（当前 incumbent 的其他已选 pose、cell owner、routing blocker）——此时判决是"core ∧ 上下文不可行"，**不是轨道不变命题**（toy 复现：同一 core 在含 blocker 的 S1 判不可行、删 blocker 的 S2 可行；F5 cut 只记 core，在 S2 误触发 = FP）。实施契约：adapter 升级为 `query_liftable(core, immutable_scope, deadline)`——immutable_scope 只含冻结工件与候选级常量（ghost rect 经 scope 绑定）；若不可行性论证需要 mutable 上下文，要么把上下文提升为 core literal（cut 变大但 sound），要么该判决禁止生成 F5。

**命题**：满足前提 1–3 时，oracle 对 π₀ 的 INFEASIBLE ⇒ 任意带标签解 A，若其逐组被选 pose 多重集包含 [π₀]，则 A 不可行。

**证明**（NOTE-2 补严版）：设 A 的组 g 被选 pose 多重集 ⊇ [π₀]|_g。对每组 g：取 A 中承载 [π₀]|_g 各 pose 的 slot 集 T_g（|T_g| = k_g，前提 2 保证 π₀ 无 slot 复用、多重集元素两两可分配），构造 S_{n_g} 中把 T_g 映到 π₀ 指名 slot 的置换（先定义 T_g 上的双射，再任意补全到 S_{n_g} 的完整置换——补全存在因为剩余 slot 集与剩余像集等势）。令 σ = 各组置换之积，则 σ(A) 字面扩展 π₀。由前提 3，σ(A) 不可行；由定理 1（前提 P-HOM），A 不可行。∎

### 2.4 与 master 对称序的复合（含 CONCERN-3 澄清）

复合安全引理同 v1（序保代表元 × 轨道 cut 删整类）。**CP-SAT `symmetry_level=3` 的定位**：它是 solver 内部搜索/预处理策略，不是建模层第二全序，不落入 F-GM-R8-SYM-01 的"至多一个全序"计数——前提是消费方式保持"TIMEOUT/UNKNOWN → no-cut、只有可复验 INFEASIBLE 产 cut"。若未来把 solver 内部对称产物外显为约束、或把 timeout 当穷尽证明，需重证。

## 3. 与既有禁令的边界

同 v1 §3（跨 operation_type 合并死、跨 candidate 越 scope 死、方案 B/C 挂起）。v2 补一句：liftable-reject 前提正是「Q5 跨 instance lifting 必死」教训在组内轨道场景的对偶——那里死于数据身份破坏可交换性，这里防的是**上下文**破坏可交换性。

## 4. 实施规格（v2 修订版，P1.3 执行）

1. **P-HOM 结构门**（范围扩大版，§2.2）：三件套 + `orbit_homogeneity_digest` 进 preflight 与 cut scope。
2. **canonical_relabel（CONCERN-1 修正）**：定义 idempotent 函数——逐组按 `(pose_id, occurrence_serial)` 排序后把占用 slot **重标为 0..k_g−1**（现有 `canonical_sort_assignment` 只排序去重、留 slot gap，不足）。应用点：generator 初始 full assignment、deletion minimizer 每个 trial core、oracle query 输入、cert 存储。
3. **validator 增补**：既有检查 + 禁重复 `(group_id, pose_id)`（前提 2）+ `cert == canonical_relabel(cert)`（非规范形 = schema_err）。
4. **oracle adapter 生产化**：`query_liftable` 契约（前提 3）；每 adapter 两条红测——σ-重标 verdict 不变性、上下文依赖判决被拒。
5. **master attach**：presence nogood 机械直接承载（前提 2 保证无 multiplicity≥2 pattern；alias fail-close 保留为纵深）。
6. **验收 telemetry**：cut 计数阈值（>10⁵ 撞墙 / <10³ 工作）+ 规范化去重命中率。
7. **红测清单**（v1 五条基础上增补）：⑥重复 `(group,pose)` cert 必拒 + 若放行则构造出 multiplicity 坍缩 FP；⑦上下文依赖 oracle 判决生成 F5 被拒（toy S1/S2 反例已有复现脚本）；⑧canonical_relabel 幂等性与 minimizer 中途重标一致性。

## 5. 组合收益计数（CONCERN-4 修正版）

两种口径（P = 组内 pose 池大小，k = pattern 阶）：
- 允许重复 pose：带标签空间 C(n,k)·P^k，轨道商 C(P+k−1,k)；
- **禁止重复 `(group,pose)`（v2 采用）**：带标签空间 C(n,k)·(P)_k，轨道商 C(P,k)，缩减因子精确 = n!/(n−k)!。
n=34、k=8 时缩减 (34)_8 = 34·33·…·27 = **7.32×10¹¹**。full-assignment 极端情形：等价重复从 Π n_g!（8 组 = 10^123.5，全 19 组 = 10^243.5）缩到每轨道 1 条。

## 6. 开放问题（v1 四条的 v2 状态）

1. ~~部分赋值上下文的 verdict invariance~~ → **已升级为定理前提 3（liftable reject），不再是开放问题**；残余细节 = immutable_scope 的精确白名单（P1.3 定）。
2. I1 复验输入是否过重标层——维持开放，倾向"是"（与 canonical_relabel 应用点 4 同批定）。
3. boundary_storage_port(46) 与 optional families 的同型覆盖——维持开放（先 manufacturing 8 组试点）。
4. 方案 B（跨 family 复合 cut）重启条件——维持（telemetry 撞墙再议）。
5. **新增**：multiplicity≥2 cut 的 cardinality-aware attach（方案 B'）——仅当发现真实需要"同 pose 多份才不可行"的非平凡核时立项（几何平凡核不算）。

---

*v2 完。v1 保留为历史快照；外审原件与复核脚本见 `p2_design_external_reviews_20260704/`。*
