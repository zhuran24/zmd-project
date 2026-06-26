---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/models/routing_subproblem.py and routing-focused regression tests; splitter/merger support is current-code aligned
last_verified_against: 2026-06-26 working tree
owner: exact-routing
---
> [!NOTE]
> **CURRENT_CODE_ALIGNED:** 本文件已按 2026-06-26 工作树重新核对。变量体系使用 CP-SAT BoolVar 编码；当前模块没有通用 MUC 提取/发布接口，routing 失败也不能自动升级为永久 placement no-good。

# 09 逐格精确路由子问题 (Exact Grid Routing Subproblem)

## 9.1 文档目的与模型边界

本文档描述 certified candidate 检查中的离散 routing 子问题。它接收 master placement 和 binding 选出的物理端口，求一组满足当前 routing 模型的有向网格 route states。

连续 flow 模型不是本模块的前置 gate。`benders_loop.py` 可以在进入 binding/routing 前运行 flow 诊断，但该诊断状态只写 telemetry；即使 flow 返回 `INFEASIBLE` 或 `TIMEOUT`，certified acceptance 仍由 binding/routing 及其 fail-closed guards 决定。本模块 `FEASIBLE` 也只支持当前 candidate 的内部 verdict，不能直接铸造 campaign terminal `CERTIFIED` 或公开蓝图。

**【模型边界声明】**：
*   **包含域**：单向带方向连续性、多商品微观不相交路径 (Disjoint Paths)、真三维高架桥连续跨越、制造单位出入口至少 1 格缓冲强制规则、公共资源池的端到端精确定位。
*   **不包含域**：**绝对不再更改任何刚体实体的位置！** 机器、供电桩、边界口、空地禁区在本模型中已被视作具有无穷高 Z 轴属性的绝对刚体障碍物。

---

## 9.2 真 3D 离散路由张量域 (3D Routing Tensor Space)

### 9.2.1 物理路由层级 ($\mathcal{L}$)
依据 02 章定义，路由空间为 $\mathcal{C} \times \mathcal{L}$，其中 $\mathcal{C}$ 为 $70 \times 70$ 网格，层级 $L \in \{0, 1\}$：
*   $L = 0$：地面层 (Ground Level)。承载普通传送带、分流器、汇流器、准入口。
*   $L = 1$：高架层 (Elevated Level)。仅承载连续拼接的物流桥。

### 9.2.2 离散路由决策变量 (Routing Variables)
对于每一个网格点 $c \in \mathcal{C}$，层级 $L \in \{0,1\}$，方向 $d \in \{N, S, E, W\}$，商品类别 $k \in \mathcal{K}$，引入极其纯粹的离散 0-1 变量：
$$ r_{c, L, d_{\text{in}}, d_{\text{out}}}^k \in \{0, 1\} $$
**语义**：当且仅当在格子 $c$ 的层级 $L$ 上，放置了一个物流设施，使得商品 $k$ 从方向 $d_{\text{in}}$ 流入，并从方向 $d_{\text{out}}$ 流出时，该变量为 1。
*(约束：传送带必须有明确的进出，强制 $d_{\text{in}} \neq d_{\text{out}}$，天然涵盖了 4 种直带和 8 种弯带。起终点接入机器时，允许 $d_{\text{in}}$ 或 $d_{\text{out}}$ 为空 $\emptyset$。)*

---

## 9.3 核心微观物理法则约束 (Micro-Physics Hard Constraints)

本模型采用极度严苛的布尔可满足性 (SAT) 约束，一比一复刻游戏内部的建造限制。

### 9.3.1 实体刚体绝对排斥规则 (Solid Obstacle Exclusion)
设 $\Omega_{\text{solid}}$ 为 07 章主模型 $\mathbf{z}^*$ 确定的所有刚体占据的绝对坐标集合。对于 $\forall c \in \Omega_{\text{solid}}$，该坐标的地面与高架层**全部锁死**：
$$ \sum_{L \in \{0,1\}} \sum_{k \in \mathcal{K}} \sum_{d_{\text{in}}, d_{\text{out}}} r_{c, L, d_{\text{in}}, d_{\text{out}}}^k = 0 \quad \forall c \in \Omega_{\text{solid}} $$

### 9.3.2 离散信道单占与防撞约束 (Capacity & Collision-Free)
每一层级的每一个独立格子，最多只能铺设一种方向组合、运送一种商品的一条带子：
$$ \sum_{k \in \mathcal{K}} \sum_{d_{\text{in}} \neq d_{\text{out}}} r_{c, L, d_{\text{in}}, d_{\text{out}}}^k \le 1 \quad \forall c \notin \Omega_{\text{solid}}, \forall L \in \{0, 1\} $$

### 9.3.3 真 3D 物流桥高架规则 (Elevated Bridge Mechanics)
物流桥可以在 $L=1$ 层连续拼接，但必须遵守其对 $L=0$ 层的投影依赖关系：
1. **直线强制律**：高架层 $L=1$ 的路由变量仅允许 $d_{\text{in}}$ 与 $d_{\text{out}}$ 相对的形态（如南北直行、东西直行）。**物流桥严禁转弯。**
2. **高架悬空合法性**：若某格子 $L=1$ 层有桥，则其正下方 $L=0$ 层要么为空，要么只能是一条**直线传送带 (Straight Belt)**。
3. **无缝起降合法性**：物流桥的两端必须能与 $L=0$ 层的非实体格子发生无缝层级接驳，无需占用额外的起降坡道格子。

### 9.3.4 微观流体方向连续性定律 (Directional Continuity)
对于除了物理端口之外的所有自由物流格子，必须满足方向匹配的基尔霍夫定律：
如果格子 $c$ 在 $L$ 层向 $d_{\text{out}}$ 方向输出物料 $k$，则相邻格 $c'$ 在接驳层级 $L'$ 必须存在一个接收该物料、且流入方向 $d_{\text{in}} = \text{Opp}(d_{\text{out}})$ 的组件。

### 9.3.5 机器出入口至少相隔1格规则 (The 1-Cell Minimum Gap Rule)
依据 03 章 3.6.3 节规则，制造单位的出口与任何单位的入口不可实现"零距离"面对面硬连：
所有的管线，从机器物理边界离开后，必须至少踩中 1 个属于 $\mathcal{V}_{\text{free}}$ 的物流格子，才能再次进入下一台机器的物理边界。

---

## 9.4 端口度数履行与公共资源池寻路 (Port Adherence & Pooling)

### 9.4.1 端口度数强制履行 (Degree Adherence)
机器端口度数 / 拓扑必须被绝对执行（**当前权威源** = `rules/canonical_rules.json` 的 `operation_type` + `port_topology`，见 04 章 §4.7；04 章 §4.8 的变体度数字典已 **[DEPRECATED]**，仅作历史参考、勿引为真源）：
若 07 章规定实例 $i$ 的某条输出边分配了 $N$ 个出口，则该边上的物理边缘节点向外发射的路由变量总和必须**精确等于** $N$。

### 9.4.2 全局资源软连接 (Global Pooling Soft-Matching)
在本路由子问题中，彻底兑现 03 章关于"不硬绑定专线"的承诺。
**路由引擎的终极任务**：在 $\mathcal{C} \times \mathcal{L}$ 的张量网格中，为所有物流带找到无交集、无方向冲突的连通子图。求解器自动计算出最顺畅的连接拓扑。

---

## 9.5 失败处理与 cut 边界

当前 `RoutingSubproblem` 没有一个可被文档概括为“任意 UNSAT 都提取 MUC，然后永久拉黑当前 placement”的通用接口。局部 precheck、binding alternative、lazy connectivity cut、selected-route nogood 和 placement-level cut 的量词不同，必须按 `benders_loop.py` 的 exact-safe proof ladder 处理：

- 当前 binding 下 routing 不可行时，若仍有 binding alternatives，应先排除当前 binding 并重解；
- lazy connectivity cut 只在独立 certificate check 通过后加入 routing model；
- selected-route nogood 只排除一个被终端 guard 拒绝的 routing incumbent；
- placement/whole-layout no-good 只有在完整 scope/proof 成立时才允许写入，whole-layout 路径还要经过 independent infeasibility re-verifier；
- timeout、`UNKNOWN`、unsupported proof stage 或不完整冲突集不得提升为永久 `INFEASIBLE` cut。

因此，早期的 MUC 方程只能作为设计动机，不能当作当前代码行为。

---

## 9.6 candidate 输出与发布边界

routing `FEASIBLE` 后，controller 可以提取当前 candidate 的 placement、binding 与 routing witness，并返回内部 `RUN_STATUS_CERTIFIED`。该状态不是项目终局：

1. outer search 仍需完成完整 candidate frontier/optimality 过程；
2. producer 只能把终端材料提交为 `CANDIDATE_PROPOSED`；
3. supervisor 必须从已提交磁盘字节复验并 mint durable terminal `CERTIFIED`；
4. fixed-witness、P1.2 owner gate 与中央 publisher 全部通过后，canonical solution/blueprint/manifest 才可公开。

`RoutingSubproblem` 本身不写 `final_solution.json`、`optimal_blueprint.json` 或 delivery manifest，也不授予 release authority。

---

## 9.7 [2026-06-11 P0 Soundness Addendum] Incumbent-level source→sink reachability

`_add_continuity_constraints` 的局部 predecessor/successor 支撑只证明每个被选 route-state 在邻域中有局部接续；它不单独证明某个 commodity 的源 front 与汇 front 处于同一个有向连通分量。Certified acceptance 因此不得把 CP-SAT `FEASIBLE` 直接等同于 routable。

`RoutingSubproblem.solve()` 在接受 incumbent 前必须重建选中 route-state 的有向图：按 commodity 从所有 source front 对应的 selected state 出发，沿 `flow_out` 到邻格 `flow_in` 遍历，要求每个 source front 至少到达一个 sink front，并要求每个 sink front 被某个 source front 到达。失败 incumbent 必须先尝试 self-checked lazy source-side connectivity cut；若 cut 证书失败则回退加 selected-route nogood，然后继续求解。若 CP-SAT 证明所有这类 incumbent 不可行，则返回 `INFEASIBLE`；若时间/预算耗尽或无法形成 connected incumbent，则返回 `TIMEOUT`/`UNKNOWN`，不得生成 false `CERTIFIED`。

长期方向仍是把 per-commodity reachability/flow 一等编码进 routing CP-SAT；当前 guard 是 certified-safe 的 fail-closed boundary。

## 9.8 [2026-06-11 P0-1] Lazy source-side connectivity cuts

The §9.7 guard remains the certified acceptance boundary.  The lazy cut described here is only a convergence accelerator inside the guard rejection loop; it never allows a CP-SAT incumbent to bypass the final selected-graph reachability validation.

For a rejected commodity $k$, rebuild the selected route-state graph with the exact same directed arc semantics used by the guard: a selected state $u=(x,y,L,d_{in},d_{out},k)$ has an arc to a selected state $v$ when some $d \in d_{out}$ points to the adjacent cell and $v$ has $\mathrm{Opp}(d)$ in its `flow_in`; terminal sink-front outputs are not expanded.  Let $W$ be the closure reachable from all selected source-front states of commodity $k$ in that selected graph.  For the rejected incumbent considered by this cut, no sink-front state may lie in $W$.

The lazy cut set $X$ is a vertex cut over **candidate** route-states, not merely selected route-states.  It contains every candidate state outside $W$ that could be the first route-state reached after leaving the selected source-side closure: (1) every non-$W$ candidate state that can receive directly from a commodity-$k$ source front, and (2) every non-$W$ candidate state reached by a potential guard-isomorphic arc from a state in $W$.  The attached inequality is:

$$
\sum_{s \in X} r_s^k \ge 1.
$$

Validity: any physical routing that connects a commodity-$k$ source front to a sink front induces a directed candidate-state path from a source-front state to a sink-front state.  If that path starts with a source-front state outside the incumbent closure $W$, its first state is in $X$.  Otherwise the path starts inside $W$; since no sink front is in $W$, the path has a first state outside $W$, and that first outside state is reached by a guard-isomorphic arc from a state in $W$, so it is also in $X$.  Therefore every feasible connected routing selects at least one state in $X$, and the inequality cannot remove a true routing solution.  This is stronger than a selected-positive nogood because the rejected incumbent selects zero states in $X$, so the cut removes that incumbent and every other incumbent with the same source-side reachable closure, instead of only one exact selected set.

Every lazy cut must pass an independent fail-closed certificate check before it is added to the CP-SAT model:

1. Recompute $W$ from the incumbent selected graph and confirm that every source front has a selected source-front state in $W$ and that no sink-front candidate state is in $W$.
2. Rebuild the full potential candidate-state graph for commodity $k$, remove $X$, and run a fresh BFS from all source-front candidate states.  No sink-front candidate state may remain reachable.  This proves $X$ is a complete crossing boundary for the modeled arc semantics.
3. Confirm the incumbent selected route-state set is disjoint from $X$, so the newly attached inequality actually separates the rejected incumbent.

If any certificate check fails, the solver must attach the pre-existing selected-positive nogood for the rejected incumbent and record the fallback reason in `build_stats["last_solve"]["connectivity_guard"]`.  Multiple failing commodities in the same incumbent are handled independently: each commodity attempts its own source-side cut, and each failed certificate contributes a telemetry fallback record.  `cuts_added`, `cut_sizes`, and `fallback_nogoods` are diagnostic telemetry only; certified soundness continues to come from the final §9.7 guard.

No environment knob controls this behavior.  It is enabled by default because it only adds self-certified valid inequalities or falls back to the previous fail-closed nogood path.  The long-term human-facing P1.3 direction remains to encode per-commodity flow/connectivity directly in CP-SAT; this lazy-cut graph machinery is deliberately reusable for that future first-class encoding, but it is not that encoding.
