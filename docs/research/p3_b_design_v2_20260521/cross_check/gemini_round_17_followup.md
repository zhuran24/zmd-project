这是一份针对 Phase 0 Day 17 (Round 17) 的 Cross-Check 报告。

总体评价：**Day 17 的修补非常精准，6 大新/旧 Family 的 Spec 已经达到了极高的严密性。** 尤其是 F8 的 Liang-Barsky 严格化和 F4 的 Geometric 哲学贯彻，扫清了最后几个可能导致 False Positive 的地雷。

以下是对 A/B/C/D 四个任务的详细回应：

---

### 任务 A: 验 Round 16 4 finding 修对

**1. F4 v1.1 删 ID 校验 (Sound 吗？充分吗？)**
*   **结论**：**绝对 Sound，且单一校验充分。**
*   **分析**：Geometric Cut 的核心哲学就是“空间占用即阻断”。只要 `separator_cells` 里的格子不在 `free_cells` 里，不管它是被 Ghost 挡的、被 Crusher 挡的、还是被 Refinery 挡的，BFS 寻路在物理上就是断的。删掉 ID 校验完美防止了“换个设施挡同一个位置却被误判为 Unsound”的 False Positive。

**2. F3 v3.2.1 移除 `by_ghost_watcher` (漏不漏？)**
*   **结论**：**不漏，逻辑完美闭环。**
*   **分析**：如果 Ghost 移动**覆盖**了 Front Cell，Master 的约束本身就会阻止这个 Pose 被选中（Pose Domain 缩减），根本轮不到 F3 发挥作用。如果 Ghost 移动**让出**了 Front Cell，此时 Front Cell 要么变成 Free（F3 Cut 应该失效，此时 `by_cell_watcher` 会因为 `cell_owner` 没占而正确处理），要么被其他设施占了（触发 `by_cell_watcher`）。Ghost 的变化不直接改变 `cell_owner`，因此 F3 不监听 Ghost 是完全正确的，省去了大量无效 Replay。

**3. F8 v1.1 Liang-Barsky 边界处理 (Edge case 怎么处理？)**
*   **结论**：**算法 Sound，但需要明确坐标系定义以防 Edge Case。**
*   **分析**：在离散 Grid 中，最严谨的做法是将 Cell 视为一个 $1 \times 1$ 的正方形，Pole 的坐标取其**中心点**。例如，Pole 在 `(60, 60)`，其中心点为 `(60.5, 60.5)`。Ghost `(x=60, y=60, h=15, w=15)` 的 AABB 是 `[60.0, 75.0] \times [60.0, 75.0]`。
*   使用中心点 `p1=(60.5, 60.5)` 和 `p2=(61.5, 61.5)` 跑 Liang-Barsky，可以完美避免“线段刚好贴着 Ghost 边缘（比如 x=60）算不算相交”的浮点数/边界包含争议。只要线段穿过 AABB 内部（`t0 < t1`），就是 Blocked。你目前的实现方向是完全正确的。

**4. F5 fixture E1 静默表加 F9 (其他 Fixture 也要加吗？)**
*   **结论**：**需要。**
*   **建议**：为了保证 Fixture 作为“反例 Owner”的排他性证明，F1 应该声明 F8/F9 为何静默（电力正常、密度未超）；F2-F4 也应补齐对 F6-F9 的静默说明。这在 Phase 1 实施测试用例时，是验证“没有发生 Cut Family 误拦截”的重要依据。

---

### 任务 B: 找新 Bug (Soundness / Schema 漏洞)

在反复推敲 v3.2.1 和 v1.1 spec 后，我发现了 **1 个 Watcher 漏入 Bug** 和 **1 个 Schema 状态依赖 Bug**。

**1. [Watcher 漏入] F8 (power_grid_reach) 漏监听潜在的 Pole 释放区域**
*   **位置**: `cut_family_specs/08_power_grid_reach.md` §8 (Watcher)
*   **问题**: F8 目前的 `by_cell_watcher` 监听了 `candidate_pole_cells`。这些是**当前**在 CoverSet 里或者被 Ghost 挡住的 Pole。但是，如果 Facility 旁边的一个格子**目前被其他设施 (cell_owner) 占了**，它不在 `candidate_pole_cells` 里。当 Master 回溯移走那个设施时，这个格子变成了 `free_cells`，它可能成为一个新的 Pole 候选，从而让 Power Network 重新连通！
*   **后果**: 因为 F8 没有监听这个“新释放”的格子，Cut 不会被重新 Evaluate，导致 False Positive（误剪了已经恢复供电的解）。
*   **修复**: F8 的 `by_cell_watcher` 必须监听 Facility 周围半径 `R_conn` 内的**所有**合法 Grid Cell（即 `PoolPole ∩ BoundingBox(Facility, R_conn)`），而不仅仅是生成 Cut 时的 `candidate_pole_cells`。

**2. [Schema 状态依赖] F9 (density_envelope) 的 Assignment Witness 携带了脆弱的 Slot ID**
*   **位置**: `cut_family_specs/09_density_envelope.md` §3 (Schema) & §7 (Validator)
*   **问题**: `oracle_assignment_witness` 的类型是 `Tuple[Tuple[GroupId, int, PoseId], ...]`，其中包含了 `slot` (int)。在 §7 的 Validator 中，这个 witness 被直接传给 `sub_oracle.verify_infeasibility`。
*   **后果**: `slot` 是 Master 内部的枚举顺序（State-dependent）。如果这个 Cut 在另一个 Candidate 中被 Replay，同一个 Pose 可能会被分配给不同的 `slot`。如果 Oracle 的验证逻辑死板地校验 `slot`，会导致合法的 Witness 验证失败，从而引发 Quarantine。
*   **修复**: 几何密度 Cut 不应该关心 Slot。Schema 中应改为 `Tuple[Tuple[GroupId, PoseId], ...]`（去掉 int slot）。Oracle 的 `verify_infeasibility` 只需要知道“这 K+1 个 Pose 同时存在”即可验证 Infeasible。

---

### 任务 C: 验 F10 反例 (Kinematic Belt Knot) 处理方向

**1. Defer 到 Phase 1 合理吗？**
*   **极其合理。** Kinematic (运动学) 限制本质上是 Routing Oracle 内部的寻路图定义问题（将普通的 4-way Grid Graph 升级为带有入边方向状态的 State-expanded Graph）。它不改变 B Design v2 的宏观 Cut 架构和生命周期。Phase 0 保证拓扑连通性 (Topological Reachability) 已经足够，Kinematic 细节完全可以作为 Phase 1 Oracle 升级的 Task。

**2. 升级 Family 4 vs 加 Family 10 哪个好？**
*   **坚持推荐升级 Family 4。**
*   **理由**: Family 4 的本质是“基于某种规则的 Free Cells 寻路不可达”。无论是普通的 BFS，还是带方向限制的 A*，其输出的 Witness 都是一样的：`src`, `sink`, `separator_cells`。如果单开 F10，你会发现 F10 的 Schema 和 Validator 逻辑与 F4 有 90% 的重复。只需要在 F4 的 Cert 中加一个可选字段 `kinematic_constraints: Optional[Dict]` 即可完美兼容。

**3. Belt Routing 还有类似 Kinematic 反例吗？**
*   **有，经典异星工厂/戴森球痛点**：
    *   **交叉死锁 (Crossing Limit)**: 两个 Commodity 的路径必须在 2D 平面上交叉，但 Endfield 可能没有空间放置“地下传送带 (Underground Belt)”的 Ramp（出入口）。拓扑上连通，但平面图 (Planar Graph) 嵌入失败。
    *   **吞吐量瓶颈 (Throughput Limit)**: 两个产线汇聚到一条传送带，需求是 30 items/s，但 MK1 传送带上限是 15 items/s。F4 (连通) 和 F2 (Min-cut size=1) 都会 Pass，但实际流量 Infeasible。*(注：这需要 F2 的 Cut Size 引入权重/带宽概念)*。
    *   **端口方向锁死 (Port Direction Lock)**: 设施的 Port 是向上的，但紧贴着 Port 的上方被限制只能向左走，导致传送带无法满足“出端口后必须直行 1 格”的 Kinematic 规则。

---

### 任务 D: 找 F11+ 反例 (突破 9 大 Family 的盲区)

在 9 大 Family 齐备的情况下，空间、形状、连通性、电力、局部密度都已被封死。如果还有 INFEASIBLE 能够静默穿透这 9 层防御，那必定是**全局资源/系统性约束**。

我为你构造 **F11: 全局吞吐量/流量平衡死结 (Global Flow Balance Deadlock)**。

#### F11 反例设定
*   **设施放置**: 
    *   `Refinery_A` (产出 30 塑料/分钟) 放在地图左上角。
    *   `Factory_B` (消耗 45 塑料/分钟) 放在地图右下角。
*   **网络设定**: 
    *   中间有极其宽阔的空地，Belt 随便连 (F4 Pass)。
    *   中间的 Cutset 截面宽度为 10，远大于 1 条 Belt 的需求 (F2 Pass)。
    *   电力、空间、密度全部完美 (F1, F3, F5-F9 全部 Pass)。
*   **真实结果：INFEASIBLE**
    *   在 Endfield 的生产逻辑中，如果 Master Assignment 选定的设施总产出 (30) 小于总消耗 (45)，且没有外部输入，这个工厂系统是无法运转的。
    *   **盲区原因**: 目前的 B Design v2 假设 Master 已经通过 `demand` 数量（比如必须放 132 个 Crusher）隐式保证了全局物料平衡。但如果游戏允许“可选放置”或者“多配方切换”，导致产线上下游的**流速 (Flow Rate)** 不匹配，现有的 9 个纯几何/拓扑 Family 将全部静默。

#### 建议
*   **Phase 0 结论**: 如果 `canonical_rules.json` 中的 `demand` 是硬编码且绝对平衡的（即 266 个 Mandatory 设施本身就是一个完美平衡的蓝图），那么 F11 不会发生。
*   **Phase 2 预警**: 如果未来引入了可选设施 (Optional Facilities) 或配方选择，必须引入 **Family 10: flow_conservation (流量守恒 Cut)**，使用基于网络流的代数 Cut 来拦截供需不平衡。

---
**总结**: Phase 0 Day 17 的设计已经达到了可以直接进入 Phase 1 编码实施的成熟度。请修复任务 B 中的两个小 Bug，然后安心推进代码落地！已 Cross-check 完毕。