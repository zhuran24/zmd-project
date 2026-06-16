这是一份针对 Phase 0 Day 1-16b (B Design v2) 进展以及 Round 14 修复情况的 Round 15 Cross-Check 报告。

总体评价：**Day 1-16b 的架构重构非常扎实**。将 Cut 提升为一等公民、引入 Anonymous Slot Ref 消除 Label Symmetry、以及严格的 Scope-Aware Replay，确实从根本上避开了之前 27 个死路中的 Class A (表达力不足) 和 Class D (Master 变量爆炸) 陷阱。

以下是对 4 个任务的具体验证与深入分析：

---

### 任务 A: 验 Round 14 5 finding 修法 (Soundness Check)

经过对 `cut_lifecycle_v2.md` v3.1 和各 `cut_family_specs` v1.1 的交叉比对，**5 个修复全部 Sound，没有引入新 Bug，且逻辑闭环。**

1.  **F7 Causation Split (Ghost vs Cell Owner)** (`07_power_hitting_set.md` §5b):
    *   **Sound 吗？** 绝对 Sound。区分 `empty_coverset_ghost` 和 `empty_coverset_cell_owner` 是极其精准的修复。它完美防止了 Master 移走 Blocker 后合法 Pose 被误杀的 False Positive。
    *   **跟 Family 5 重复吗？** **不重复，且 F7 严格优于 F5。** F5 (`pattern_nogood`) 是 Sub-problem Oracle 吐出的一个“黑盒” Infeasible Core；而 F7 的多 Literal Cut 是一个**白盒的、纯几何推导的极小 Core** (只包含 Facility 本身 + 真正占据 Pole 候选格子的那几个 Blocker)。F7 的 Core Size 远小于 F5 的盲目提取，剪枝效率更高。
2.  **F6 Partition 改 Static + Demand 改 `group.demand`** (`06_shape_packing_hall.md` §5a & §7):
    *   **跨层 Sound 吗？** Sound。因为 Hall Condition 的本质是“这个 Baseline 区域在当前 Ghost 切割下，**总共**只能容纳 $K$ 个设施”。而 `group.demand` 是 Source-of-truth 要求的**总**放置量。用“总容量 < 总需求”作为无条件 Infeasible 的判定，完全不依赖当前的 `cell_owner` 进度，跨层 Replay 绝对安全。
3.  **F1 `cap_R` 改 Static** (`01_region_capacity.md` §2a & §6):
    *   **Sound 吗？** Sound。与 F6 同理，将 Capacity 剥离 `cell_owner` 后，`evaluate_geometric` 无条件返回 `True` 是数学上严密的（因为 Cert 生成时已经保证了静态容量 < 需求）。这极大降低了 Propagation 的开销。
4.  **Replay `blocked_cells_hash` 校验** (`cut_lifecycle_v2.md` §4 Step 3):
    *   修复精准，堵住了跨 Session 地图边界微调导致的旧 Cut 误用漏洞。
5.  **F1 Cert 补充 `cells_per_pose`** (`01_region_capacity.md` §3 & §7):
    *   修复正确，消除了 Validator 对外部隐式状态的依赖，保证了 Cert 的自包含性 (Self-contained)。

---

### 任务 B: 验 F5 反例评估 (Power Grid Disconnect)

你的评估是**完全正确**的。F5 全局电力孤岛反例**确实不撞**已死的 Path 14, Path 13 和 L23。

*   **为什么不撞 PCR-CUT (Path 14) / D2 (L23)？** Belt Routing 是基于连续的 `free_cells` 寻路，且受限于 Port 方向；而 Power Network 是基于离散的 Pole 候选点、以 $R_{conn}$ 为半径的**跃迁图 (Jump Graph)**。两者的图拓扑结构、连通性判定逻辑完全不同。
*   **Family 8 vs Family 4 Generalization 选哪个？**
    *   **我强烈支持你的推荐：选 B (加 Family 8 `power_grid_reach` 独立 Family)。**
    *   **Reason:** 如果强行泛化 Family 4，其 Schema 会变成一个巨大的 Union Type（既要包容 Belt 的 Port/Direction，又要包容 Power 的 Radius/Pole_Chain）。这不仅会让 Validator 的逻辑充满 `if-else`，还会导致 Cert Payload 序列化时的字段冗余。将连续流 (Belt) 和离散跃迁流 (Power) 分开为 F4 和 F8，符合高内聚低耦合的 Schema 设计原则。

---

### 任务 C: 结合 27 Lever Timeline 的新反例与风险预警

在解决了 Class A 和 Class D 后，B Design v2 面临的最大威胁是 **Class B (Cut 累积失效) 和 Class C (退化为 Full No-good)**。

**风险 1：F7 (Power) 的 Cell_Owner Causation 退化 (Class C 风险)**
*   *场景*：假设一个 Crusher 的 Power CoverSet 被 4 个相邻的 Refinery 挤空了。F7 会生成一个包含 5 个 Literal 的 Cut (1 个 Crusher + 4 个 Refinery)。
*   *问题*：这种 Cut 极其特化。如果 Master 把其中一个 Refinery 往旁边挪了 1 格，CoverSet 可能依然是空的，但旧的 Cut 无法命中（因为 Literal 绑死了具体的 Pose ID）。这会导致 Solver 在这个局部区域疯狂生成大量高度相似的 5-Literal Cuts，陷入 **Class B (Cut Accumulation 不够)** 的泥潭。

**风险 2：M5 Trivial Orbit 的幽灵 (Class C 风险)**
*   *场景*：`state_machine_v2.md` §5 引入了 Anonymous Slot Ref，完美解决了同 Group 内的 Label Symmetry (132! 的排列组合)。
*   *问题*：这只解决了**逻辑对称性**，没有解决**几何对称性**。如果一个 3x3 的设施在 $(10, 10)$ 不合法，它在 $(10, 11)$ 大概率也不合法。当前的 Literal-based Cut (F3, F5, F7) 依然是死绑 `pose_id` 的。如果不能跨几何平移 (Translation Lift)，Solver 依然会撞墙。

---

### 任务 D: B 5 Unsolved Issue 现 Spec 充分性评估 (Issue 3 重点)

你在 `paradigm_death_timeline.md` §3 中给 Issue 3 (Manufacturing Cluster Trap) 标了 ⚠️，这个判断**极其敏锐且正确**。

**当前 Spec 绝对不足以应对 132 个 Manufacturing_3x3 的 Cluster Trap。**

*   **拦 132! Permutation 够吗？**
    *   通过 Anonymous Slot Ref (Multiset 包含语义，`cut_lifecycle_v2.md` §5)，我们确实拦住了“同一个几何布局，不同的 Instance 编号”这 132! 种逻辑排列。
    *   **但是**，我们拦不住“微小几何扰动”带来的组合爆炸。
*   **走 Full No-good 退化的风险有多大？**
    *   **致命级 (Stop-ship)**。如果 10 个 3x3 设施挤在一个死胡同里导致 Routing Infeasible，Family 5 会生成一个包含 10 个 Literal 的 Cut。Master 稍微把其中一个设施平移 1 格，又会生成一个新的 10-Literal Cut。这会瞬间产生数以十万计的 Pattern Nogood Cuts，耗尽 48GB RAM，且永远无法证明 OPTIMAL。

**Day 18-21 怎么加 Dedicated Orbit-Aware Lift？**

我建议在 Day 18-21 放弃在 Family 5 上修修补补，而是**引入一种全新的 Geometric Cut 思想来降维打击 Cluster Trap**：

**方案：引入 `Family 9: local_density_capacity` (局部密度/窗口容量 Cut)**
*   *核心思想*：将 Combinatorial 的 Pattern Nogood 转化为 Geometric 的 Capacity Bound。
*   *机制*：如果 Oracle 发现某个区域 $W$ (比如一个 15x15 的 Window) 内塞了 10 个 3x3 设施导致 Routing 彻底堵死，不要生成绑定这 10 个具体 Pose 的 Literal Cut。
*   *Cut 形式*：生成一个 Geometric Cut，声明 **"在 Window $W$ 内，`manufacturing_3x3` 的总数量不能超过 9"**。
*   *Schema 契约*：这与 Family 1 `region_capacity` 非常相似，但 F1 是基于全局 Baseline 的静态容量，而 F9 是基于 Oracle 反馈的**动态局部窗口容量**。
*   *收益*：一条 F9 Cut 直接秒杀了该窗口内所有可能的 $\binom{N}{10}$ 种微小几何扰动，将 Class C (Full No-good) 瞬间提升为 O(1) 的几何剪枝。

**总结**：Phase 0 Day 1-16b 的基础框架已经坚如磐石。Day 17 请按计划推进 F2/F3/F4/F8 的 Spec。Day 18-21 的生死决战，请务必将精力放在**如何将 Literal-based 的特化 Cut (F5, F7_cell_owner) 向上 Lift 成 Geometric/Density Cut** 上。这是跨越 96% Utilization 几何死结的最后一块拼图。