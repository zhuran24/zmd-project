---
status: ACCEPTED_DRAFT
source_of_truth: src/cuts/families/ (F1–F9 当前 cut-family 范式) + src/cuts/lifecycle.py + src/models/cut_manager.py (早期 no-good 范式) + src/search/benders_loop.py + exact-contract regressions
last_verified_against: 2026-06-11 (P0 binding-local routing-precheck cut ladder修订)
owner: cut-manager
---
> [!NOTE]
> **ACCEPTED_DRAFT — 本章 Type-I/II no-good cut 设计与 `src/models/cut_manager.py`（**早期** cut 范式，见下方 2026-06-04 范式更新）对齐；当前主线 cut 体系已转 F1–F9 cut-family。`[竣工图]` 标注反映代码实际状态。**

# 10 逻辑型 Benders 分解与切平面通信协议 (Logic-based Benders Decomposition & Cut Design)

> ⚠️ **范式更新 (2026-06-04)**：本章的 Type-I / Type-II **组合 no-good cut** 设计 + `src/models/cut_manager.py` 是**早期** cut 范式。项目当前主线已转 **cut-family LBBD 重设计**：9 个 cut family **F1–F9**（`src/cuts/families/`：region_capacity / cutset / port_exposure / component_reach / pattern_nogood / shape_packing_hall / power_hitting_set / power_grid_reach / density_envelope）当 Benders cut 收紧 master，每个 family = generator + validator（validator 是 **FP=0 信任边界**），proof lifecycle 在 `src/cuts/lifecycle.py`（`step_8_apply_to_master` 真 master 集成属 P1.3B 待接）。权威见 `PROJECT_LOCK.md` §2B + `CLAUDE.md`。**下方 §10.2 的 LBBD 主从循环结构仍成立**（master→flow→routing→cut→resolve），但 cut 的生成 / 校验已由 F1–F9 family 体系承担，不再是 §10.3 / §10.4 的两类裸 no-good cut；§10.3–10.5 作 cut-design 概念基础与历史读。

## 10.1 文档目的与架构定位

本文档是《明日方舟：终末地》极值排布工程的**中央调度与反馈通信协议**。
在确立了主摆放模型 (07 章)、宏观拓扑流预筛子问题 (08 章) 与微观精确路由子问题 (09 章) 后，必须构建一套能够让这三个模型自动协同、自我纠错的算法架构。本章定义了**逻辑型 Benders 分解 (LBBD)** 的执行闭环，以及当子问题判定布线失败时，如何向主问题生成极具剪枝威力的**组合互斥切平面 (Combinatorial No-Good Cuts)**。

---

## 10.2 LBBD 主从协同状态机 (The Master-Subproblem Loop)

针对外层搜索（01 章）传入的每一个确定的空地尺寸目标 $(w, h)$，系统内部执行以下 LBBD 状态机循环：

*   **Step 1: 主问题求解 (Master Placement)**
    调用 07 章 CP-SAT 模型求解当前约束下的摆放方案。
    *   *若返回 `INFEASIBLE`*：终止当前 $(w, h)$ 的探索。
    *   *若返回 `FEASIBLE`*：提取 $\mathbf{z}^*$，进入 Step 2。

*   **Step 2: 一级子问题验证 (Macro-Topological Flow)**
    将 $\mathbf{z}^*$ 冻结为静态网格障碍物，传入 08 章连续 LP 流体模型。
    *   *若返回 `INFEASIBLE`*：执行 10.3 宏观瓶颈切平面提取。**回退至 Step 1**。
    *   *若返回 `FEASIBLE`*：进入 Step 3。

*   **Step 3: 二级子问题验证 (Micro-Exact Routing)**
    将 $\mathbf{z}^*$ 传入 09 章离散 SAT 路由模型。
    *   *若返回 `INFEASIBLE`*：执行 10.4 微观死结切平面提取。**回退至 Step 1**。
    *   *若返回 `FEASIBLE`*：**【系统最高胜利】** 输出终极蓝图！

---

## 10.3 Type-I: 宏观拓扑瓶颈切 (Topological Bottleneck Cuts)

### 10.3.1 最小割溯源 (Min-Cut Extraction)
当 LP 模型无解时，依据 Farkas 引理提取对偶不可行射线，对应"最小割面障碍界限"。

### 10.3.2 肇事刚体集锁定 (Conflict Set Identification)
收集紧贴"最小割面"的实体刚体，构成**拓扑肇事集合 $\Omega_{\text{topo}} \subset \mathcal{I}$**。

### 10.3.3 切平面方程 (The Benders Cut)
$$ \sum_{i \in \Omega_{\text{topo}}} z_{i, p_i^*} \le |\Omega_{\text{topo}}| - 1 $$

---

## 10.4 Type-II: 微观精确死结切 (Micro-Routing Deadlock Cuts)

### 10.4.1 极小不可满足核提取 (MUC Extraction)
调用 `FindUnsatisfiableCore()` 提取最少冲突子句集，映射回**微观肇事集合 $\Omega_{\text{micro}}$**。

### 10.4.2 微观排斥方程 (Micro No-Good Cut)
$$ \sum_{i \in \Omega_{\text{micro}}} z_{i, p_i^*} \le |\Omega_{\text{micro}}| - 1 $$

---

## 10.5 工业级切平面强化技术 (Industrial Cut Lifting)

### 10.5.1 空间平移不变性提拉 (Spatial Translation Lifting)
对 $\Omega_{\text{micro}}$ 中每台机器定义局部邻域 $\Delta(p_i^*)$，注入强化切平面：
$$ \sum_{i \in \Omega_{\text{micro}}} \left( \sum_{q \in \Delta(p_i^*)} z_{i, q} \right) \le |\Omega_{\text{micro}}| - 1 $$

### 10.5.2 模板级对称性拉黑 (Template-Level Symmetry Breaking)
将基于实例 ID 的切平面升维为模板级聚合变量 $Z_{T(i), p}$：
$$ \sum_{i \in \Omega_{\text{conflict}}} Z_{T(i), p_i^*} \le |\Omega_{\text{conflict}}| - 1 $$

> [!NOTE]
> **[竣工图]** 空间平移提拉 (§10.5.1) 和模板级对称性拉黑 (§10.5.2) 在代码中尚未实现。[TBD] 待路由子问题完成后，根据实际切面效果决定是否需要这些强化技术。

---

## 10.6 代码落地：惰性回调与热启动 (Lazy Callbacks & Hot-Start)

本工程采用 **「累积切面 + 重新求解」+ 热启动 (Hot-Start)** 模式（CP-SAT **不支持**真正的惰性约束回调 Lazy Constraint Callback，故非真 lazy；见下方 [竣工图]）：
1. 主模型收到切平面（累积注入后重新 `Solve()`）。
2. 将上一次合法摆放解中（未惹事的机器位置）作为 **Solution Hint** 喂给主模型。
3. 求解器瞬间意识到只需微调惹事机器，每次 Benders 迭代重新求解时间从数十秒坍缩至几百毫秒。

> [!NOTE]
> **[竣工图]** CP-SAT 不支持真正的惰性约束回调 (Lazy Constraint Callback)。代码中使用「累积切面 + 重新求解」的模式替代：每轮将新切面注入模型后重新调用 `model.Solve()`，通过 `model.AddHint()` 提供上一轮解作为热启动。效果等价但每轮有模型重建开销。


---

## 10.7 [2026-06-11 P0 Soundness Addendum] Binding-local precheck evidence ladder

Routing precheck 的 `binding_selection_safe_reject=True` 只说明当前 binding selection 不可接受，不自动证明当前 placement pose combination 不可路由。尤其是 `front_blocked`：端口前格是否被占用取决于 `binding_idx` 选出的具体端口/方向；同一 pose 换另一个 binding 可能打开前格。

因此 LBBD loop 对 `front_blocked` 与 `relaxed_disconnected` 使用同一 proof ladder：只要 binding model 仍有可枚举替代，先写 binding-level nogood (`binding_model.add_nogood_cut(selection)`) 并重解 binding。只有所有 binding 替代已穷尽，或另有独立 exact proof 表明该 placement 下任意 binding 都必然失败，才允许投影为 master placement-level nogood。若无法建立 exact placement-level proof，certified path 必须返回 `UNKNOWN` 而不是误剪 placement。

## 10.8 [2026-06-12 cuts R2 Addendum] Cell-pattern cut 的必然激活端口前提 (F-CUT-R2-01)

env 门控的 pose-bool cell cut（`add_routing_port_blocking_cell_cut`，形状 `sum(在 (cell,dir) 有端口的 pose) + sum(占 front cell 的 pose) <= 1`）是 master 级 cut，对 pose 变量量化，构造时不知道未来 binding 子问题会选哪个 alternative。其隐含定理"port pose + blocker pose 同选必然 front_blocked"需要一个关键前提：**该物理端口在 pose 被选中时必然 active 且 routing-visible**。

因此 raw per-cell 端口只在该 side 的 visible demand 覆盖该 side 全部物理端口时才允许登记进 routing-visible 索引（`_mandatory_port_side_is_cell_pattern_exact()`——input 侧：`input_demand >= 物理端口数`；output 侧：visible output 非零、等于 total output、且 `>= 物理端口数`）。否则被挡的端口可能只是一个 binding 可不选的 slot：binding 换另一个槽后 placement 仍可行，cut 会误剪（最小反例：双输入口、demand=1 的机器 + 占第一口 front cell 的 blocker——binding 选第二口即合法）。混合 visible + routing-free 的输出侧继续交给更弱但 exact 的 lazy-demand/count cut；residual-optional pose 没有 operation binding identity，不登记 raw per-cell 索引。

另一同源前提：candidate pose data 是 global 坐标（同 `_build_global_pose_cache` 的注释），端口/格子 lookup cache 不得再叠加 anchor 偏移——double-anchor 会把 candidate alias 到幻影格，轻则漏 cut、重则把无关 pose 带进 cut。该 hook 在公开 certified 路径被 `pose_bool_master_not_certified` env guard 阻断；本前提约束任何未来把 pose-bool/cell cut 提升为 certified 的决定。
