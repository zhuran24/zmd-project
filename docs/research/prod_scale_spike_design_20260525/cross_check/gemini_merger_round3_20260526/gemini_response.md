这是一份基于 OR-Tools 9.15 / CP-SAT 底层机制与计算复杂度的 Round 3 Review. 

针对你提出的核心问题：“Shrink 后 scope 还能不能 close GPT pro Finding 5”，结论是：**在 Build/Memory 维度可以完美 close，但在 Solve/Filter 维度存在物理级语义断层，会导致 CI 必然失败或数据无意义。**

以下是详细解答与 Finding 列表。

---

### Q1: 5×N 对应 Table (Finding 5 vs Spike Scope/GO Criteria)

Shrink 后的 Scope 确实覆盖了 Finding 5 的字面要求，对应关系如下：

| GPT pro Finding 5 需求 | Spike 对应 Step / Scope | 对应 GO Criteria | 覆盖度评估 |
| :--- | :--- | :--- | :--- |
| **#1 真规模 master var** | Master scale (81,795 BoolVar toy master) | G1, G2, G3, G4, G4b | **Partial** (Build 成本准，Solve 成本不准，见 Q2) |
| **#2 真 cut body size 分布** | Real oracle real emit (≥45 cert), Toy translator | G10 | **Full** (真实 protobuf 序列化与 AddLinearConstraint 复杂度被真实还原) |
| **#3 测 build/solve/RSS/ByteSize** | Cut count ramp, 基本 telemetry | G1-G9 | **Full** (物理级 metric 采集完整) |
| **#4 active filter / rotation 阈值** | Active filter sizing | G11 | **Partial** (单次 pass 无法触发 age_decay，见 Q9) |
| **#5 测 feasible realistic case** | Feasible smoke | G5, G6 | **Broken** (G6 逻辑自相矛盾，见 Q9) |

---

### Q2: Toy Master vs PoseBoolExactMaster 的代表性

**结论：Build/Memory 数据 100% 可复用，Solve 数据 0% 可复用。**

*   **Build/Memory (可复用):** CP-SAT 的 `model.Proto().ByteSize()` 和 `AddLinearConstraint()` 的时间复杂度严格正比于 $\sum (\text{terms per constraint})$。Toy master 只要变量总数 (81K) 和 Cut 密度 (真实 cert 分布) 对齐，Protobuf 序列化和 Python-to-C++ SWIG 调用的开销与 Prod 完全一致。
*   **Solve (不可复用):** CP-SAT 的 Presolve 和 Search 极度依赖约束图的拓扑结构。`PoseBoolExactMaster` 包含大量的 ExactlyOne, Implication 和 Port-linking 约束。
    *   Toy master 缺乏这些结构，LP relaxation 极其松散，分支定界树的形态完全不同。
    *   Toy master 的 Solve time 只能作为 "CP-SAT 吞吐 100K cuts 的最低开销 (Lower Bound)"，**不能**代表 Prod 的真实求解时间。

---

### Q3: Single Build/Solve 对 Filter 验证的有效性

**结论：无法 cover "rotation 阈值" 的动态有效性，只能 cover "filter 自身的计算开销"。**

Filter 的核心机制是跨迭代的。你选用的 Hybrid score = `activity_count - 0.1 * age_decay`。在 Single build/solve 场景下，所有 cut 的 `age` 都是 0 或 1，`activity_count` 也缺乏多轮累积。
因此，单次 pass 只能证明 "Python 遍历 100K 个 dict/object 并计算 score 的 Wall time $\le$ 100ms" (这是 $O(N)$ 纯内存操作，100ms 绝对够)，但**无法证明**这个 eviction 策略在真实 LBBD 中会不会导致 cycling (死循环) 或过度淘汰。

---

### Q4: 删 Adversarial Inject 的影响

**结论：Gemini Agree。删除不影响 Finding 5。**

Finding 5 的核心是 **Sizing (规模) 和 Measurement (测量)**。Adversarial inject (bad cert / forged-cert) 属于 P1.3B 的 Correctness / Robustness 范畴。在未确定 100K cuts 的内存和时间边界前，测试 bad cert 会引入不必要的噪音（例如区分是 OOM 导致崩溃还是 bad cert 导致崩溃）。将其 defer 是极其正确的决定。

---

### Q5: 单 Solve 下 Objective Bound + Status 校验的必要性

**结论：依然绝对必要。**

即使是单次 Solve，如果 CP-SAT 在 180s 内 timeout，`status` 必须是 `FEASIBLE` (找到了次优解) 或 `UNKNOWN` (连 LP root node 都没解完或没找到任何可行解)。
如果 `status == UNKNOWN` 且 `best_objective_bound` 为空，说明 10K cuts 导致 CP-SAT 的 Presolve 陷入了死锁或数值不稳定，这直接意味着 10K 挡位的 Build 方式存在物理级缺陷。保留此 Check 可以防止 "假 Solve" (即 solver 实际上什么都没干就退出了)。

---

### Q6: G11 Filter Sizing 阈值的合理性

**结论：阈值合理，双 trigger 设计非常标准。**

*   **100ms/iter @ 100K cuts:** Python 中对 100K 个元素执行简单的浮点运算和排序，时间复杂度 $O(N \log N)$。在现代 CPU 上，Timsort 100K 个部分有序的 float 耗时约 10-20ms。100ms 阈值既不苛刻，也能防范写出 $O(N^2)$ 的低效 filter 逻辑。
*   **双 Trigger (RSS > 4.5GB OR count > 50K):** 这是经典的 OR-Tools 内存防御模式。Cut count 防御 CP-SAT 内部模型膨胀 (Proto size)，RSS 防御 Python 侧对象泄漏。4.5GB 留足了 buffer，防止在 8GB 容器中被 OOM killer 猎杀。

---

### Q7: 8-12h Claude / 4-7h Wall 工时评估

**结论：合理且偏保守（安全）。**

去除了 Multi-iter LBBD 和状态机后，最大的时间黑洞（调试 CP-SAT 跨迭代状态不一致、调试 Python-C++ 内存泄漏）已被消除。4-7h 的 Wall time 主要将被 50K/100K 挡位的 CP-SAT 求解等待时间占据（G4b 允许 600s，G7 不设 hard cap）。只要不手贱去跑全量 ablation，这个工时完全 hold 得住。

---

### Q8: Shrink 后 Spike GO 是否等价于 "Finding 5 Close"?

**结论：不等价。存在语义降级。**

Shrink 后的 Spike GO 实际上是 **"Finding 5 的必要不充分条件"**。
*   **真实等价:** 如果 Spike 失败，Prod 必失败（例如 100K cuts 直接 OOM，那 Prod 也不可能跑得动）。
*   **语义降级:** Spike 成功，只代表 "系统具备了承载 100K cuts 的物理容量"，**不代表** "系统能在 100K cuts 下收敛"。
**缺什么才能真等价？** 缺 P1.3A 主体的 Multi-iter LBBD 和 PoseBoolExactMaster。
**建议：** 接受这种不等价。作为 Phase 1.3A 的前置 Spike，证明 "物理容量达标" 已经足以 close Finding 5 的 *Sizing* 目的。强求完全等价会导致 Scope 再次膨胀回 P1.3A。

---

### Q9: Hidden Findings (Round 3 必须 Catch 的互锁问题)

这里存在两个严重的逻辑互锁问题，会导致你的 CI 必然失败。

#### 🔴 BLOCKER: G6 逻辑自相矛盾 (FEASIBLE vs Random Cuts)
*   **数据/逻辑:** G6 要求在 10K cut 下 `status OPTIMAL/FEASIBLE`，且不能 `INFEASIBLE` 早停。但是，你的 10K cuts 是从 45 个真实 cert 中 sample/ramp up 出来的。在 Toy master (缺乏真实变量互斥约束) 的情况下，强行注入 10K 个真实的、可能互相冲突的 cuts，**极大概率会在 Presolve 阶段直接证明 INFEASIBLE**。
*   **后果:** CP-SAT 会在 0.1s 内返回 `INFEASIBLE`，导致 G6 失败。你无法在随机组合的 10K cuts 下保证数学上的 FEASIBLE。

#### 🔴 HIGH: G11 Filter Age Decay 无法被触发
*   **数据/逻辑:** 单次 Build/Solve 架构下，没有 LBBD 循环。Filter 函数只会被调用一次（或在单次上下文中 mock 调用）。`age` 变量永远无法递增，`0.1 * age_decay` 永远为 0。
*   **后果:** G11 实际上只测了 `activity_count` 的排序，完全没有 verify 到 Hybrid score 的核心逻辑。

---

### 结论与 Verdict

**OVERALL VERDICT: NOT_GO**

**一句话理由：** Shrink 后的 Scope 极其精准，但 G6 的 FEASIBLE 强校验与随机 Cut 注入在数学上互斥，且单次 Pass 导致 G11 的 Age Decay 逻辑物理失效，必须进行 Mechanical Fix 才能防止 CI 必挂。

#### 必修项 (Mechanical Fixes):

1.  **Fix G6 (解除 FEASIBLE 互锁):**
    *   修改 G6 标准：允许 `INFEASIBLE`，但前提是 `wall_time > 1.0s` (证明不是 trivial presolve 瞬间发现的空集，而是经过了实际的 propagation)。或者，在 10K 挡位**只注入**从 Feasible Smoke case 中提取的 known-feasible cuts。
2.  **Fix G11 (Mock Loop 激活 Age):**
    *   在 Active filter sizing 步骤中，**强制要求写一个纯 Python 的 `for i in range(10):` mock loop**。在 loop 内随机增加 activity 并递增 age，只测 filter 函数本身的 100ms 性能和 eviction 触发，不挂载 CP-SAT solve。这样既不违反 "不跑 Multi-iter LBBD" 的 NOT-scope，又能真实 verify Hybrid 公式。