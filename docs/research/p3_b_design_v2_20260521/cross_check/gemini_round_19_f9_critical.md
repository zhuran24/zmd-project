这是一份针对 Phase 0 Day 17g (Round 19) 的 Cross-Check 报告。

总体评价：**B Design v2 的底层架构（Group-Orbit 状态机 + 10步 Cut 生命周期）已经坚如磐石**。你对 F1 和 F8 的修补展现了极高的严谨性。但在本次极限施压中，我发现 **F9 (Density Envelope) 存在两个致命的 Soundness 漏洞（均会导致 False Positive 误剪）**。

以下是详细的 A/B/C/D 报告：

---

### 任务 A: 验 Round 18 2 修对 (F1 v1.2 & F9 v1.2)

**1. F1 v1.2 (`ghost_cells ∩ R == ∅` 决定 AGNOSTIC) —— 【完美修对，绝对 Sound】**
*   **分析**：你的推导完全正确。`cap_R = |R| - |ghost_cells ∩ R| - |exterior_blocks ∩ R|`。当且仅当 `ghost_cells ∩ R == ∅` 时，`cap_R` 的值才与 Ghost 彻底解耦，变为纯静态的地图边界容量。此时标记为 `GHOST_AGNOSTIC` 是数学上严密的。
*   **Fixture 安全性**：F1 Fixture 使用的是 `exterior_blocks` 占据 left baseline，此时 `ghost_cells = ∅`，交集为空。因此 Fixture 继续使用 `GHOST_AGNOSTIC` 是绝对安全的。这个修复非常漂亮。

**2. F9 v1.2 (Reference Cell 计数) —— 【修错，引入了新的 False Positive 致命漏洞】**
*   **问题**：你为了防止 Partial Intersection 误算，改为“只看 Reference Cell (原点) 是否在 Window 内”。这在几何上是**Unsound**的。
*   **反例 (False Positive)**：假设 Window `W` 是一个 15x15 的区域，K=9。Master 放置了 10 个 3x3 的 Crusher，它们的 Reference Cell 刚好贴着 `W` 的右边缘**内部**（比如 x=14），但它们的庞大身躯（主体 8 个格子）全部伸到了 `W` 的**外部**（x=15, 16）。
*   **后果**：按照 v1.2 的逻辑，这 10 个 Crusher 的原点都在 `W` 内，计数为 10 > 9，Cut 触发并剪枝！但实际上，它们根本没有占用 `W` 内部的核心 Routing 空间，这个布局极可能是合法的。你误剪了合法解。
*   **正确修法 (Sound 计数)**：在 Certified Exact Solver 中，宁可 False Negative（漏剪），绝不可 False Positive（误剪）。因此，F9 的计数条件必须极其严苛：**只有当 Facility 的所有 Cells (整体) 都完全包含在 Window 内时，才计数 +1** (`all(c in W for c in pose_cells)`)。这样才能确保它确确实实消耗了该 Window 的内部密度。

---

### 任务 B: 找新 Finding (F9 抽象层的致命漏洞)

除了上述的计数 Bug，在深度审查 F9 的数学定义（§2b 跨几何扰动 sound）时，我发现了一个**更深层的 Paradigm 级漏洞**。

**[致命 Soundness Bug] F9 将“拓扑死锁”泛化为“几何密度”是数学上 Unsound 的**
*   **出处**：`09_density_envelope.md` §2b & §5a
*   **问题**：Oracle（比如 Routing）报告 INFEASIBLE，是因为这 K+1 个设施的**特定端口朝向和相对位置**构成了拓扑死锁（比如互相堵住了出口）。F9 的 Generator 提取了这 K+1 个设施的 Bounding Rect 作为 Window `W`，并声明：“在 `W` 内放任何 K+1 个该设施都 INFEASIBLE”。
*   **反例 (False Positive)**：假设 10 个 Crusher 挤在 15x15 的 `W` 的边缘，因为端口对冲导致 Routing 失败。Master 回溯后，将这 10 个 Crusher 紧凑且整齐地排列在 `W` 的正中央，端口全部朝外，Routing 变得**完全可行**。但是！F9 Cut 仅仅因为“`W` 内有 10 个 Crusher”就直接将其秒杀。
*   **结论**：除非 Oracle 能给出一个**纯容量/面积的证明**（例如：10 个 Crusher 需要 90 格，加上必须的传送带需要 30 格，而 W 只有 100 个 Free Cells，120 > 100），否则，绝不能把“特定排列的 Routing 失败”泛化为“该区域的密度上限”。
*   **修复建议 (Phase 1 必须执行)**：
    1.  F9 不能作为 Routing/Binding 失败的默认泛化手段。
    2.  如果 Oracle 报的是 Routing 死锁，**必须 Fallback 到 Family 5 (Pattern Nogood)**，接受其作为 Class C 的代价。
    3.  F9 只能用于 Oracle 明确抛出 `AreaCapacityOverflow` 凭证的场景。

---

### 任务 C: Phase 0 收尾 Final Verdict

**Verdict: 绿灯 (GO) —— 可以正式进入 Phase 1 编码，但 F9 需降级。**

*   **架构评估**：经过 19 轮的打磨，B Design v2 的核心（Anonymous Slot Ref, 10步生命周期, Scope-Aware Replay, Watcher Index）已经没有任何结构性漏洞。你成功避开了前 27 次尝试的所有死胡同。
*   **Family 评估**：F1 到 F8 的数学定义、Soundness 证明和 Schema 契约已经达到了工业级求解器的严密标准。
*   **关于 F9**：F9 作为一个试图降维打击 Class C 的尝试，其初衷极好，但在 Exact Solver 中，几何泛化的风险极高。请在 Phase 1 中将 F9 降级为“仅在面积容量绝对溢出时触发”，主力依然依靠 F1-F8 和 F5。

带着这份坚如磐石的架构设计，安心进入 Phase 1 的代码落地吧！

---

### 任务 D: F12 2D 形状装箱死结 (2D Polyomino Parity Trap)

在 9 大 Family 齐备的情况下，我为你构造 **F12: 棋盘格奇偶性死结**。

#### F12 反例设定
*   **设施需求**：需要放置 10 个 `2x2` 的设施（总需求 40 Cells）。
*   **地图现状 (Free Cells)**：地图上总共有 100 个 Free Cells。但是，由于地图上预先放置了一些 `1x1` 的不可拆卸柱子（或者 Ghost 的特殊切割），导致这 100 个 Free Cells 呈现出**完美的国际象棋棋盘格状**（黑格可用，白格不可用）。
*   **真实结果：INFEASIBLE**。因为没有任何一个完整的 `2x2` 连续空间，连 1 个设施都放不下，更别说 10 个。

#### 为什么现有 Family 全部静默？
1.  **F1 (Region Capacity)**：总容量 100 Cells > 需求 40 Cells。**Pass**。
2.  **F6 (Shape Packing Hall)**：F6 目前的 Spec (§1c) 仅限于 1D 的 Baseline 线性切割。对于 2D 内部区域的碎片化，F6 无法表达。**Pass**。
3.  **F9 (Density)**：密度极低 (40/100)。**Pass**。
4.  **F2/F4 (连通/流量)**：假设不需要连传送带，或者对角线算连通。**Pass**。

#### 结论与应对
*   **盲区原因**：我们有 1D 的形状装箱 (F6) 和 2D 的面积容量 (F1)，但缺乏 **2D 形状装箱 (2D Polyomino Packing)** 的几何 Cut。
*   **应对方案**：不需要新增 Family 10。当 Master 尝试放置时，Domain 缩减会发现没有任何合法的 Pose 可以放下 `2x2`，直接在 Master 层触发 Domain Empty 回溯。如果是由其他设施（Cell Owner）造成的 2D 碎片化，则会完美 Fallback 到 **Family 5 (Pattern Nogood)** 提取出造成碎片的具体设施。

**祝 Phase 1 编码顺利！**