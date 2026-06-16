这是一份针对 B Design v2 (Phase 0 Day 1-16b) 框架及 3 个新 Cut Family (1, 6, 7) 的 Cross-Check 报告。

在深入审查数学定义、Soundness 证明、Schema 契约和 Replay 生命周期后，我发现了 **3 个严重破坏 Soundness 的核心 Bug**，**2 个 Schema 漏字段/逻辑断层**，并为你构造了 **F5 级反例**。

---

### 任务 A: 找 Bug / 漏字段 / Soundness 证错

#### 1. [Soundness 致命 Bug] Family 7 (Power) 漏捕获 `cell_owner` 导致 False Positive
*   **出处**: `docs/research/p3_b_design_v2_20260521/cut_family_specs/07_power_hitting_set.md` §5b (Generator) & §4 (Cut 构造)
*   **问题**: L16 的 `compute_cover_set` 依赖 `state.free_cells` (排除了 `cell_owner` 占用的格子)。如果 Facility A 的最后一个合法 Pole 候选位置，被 Master 刚刚放置的 **Facility B** (比如一个 Crusher) 物理占用了，导致 A 的 `CoverSet` 变为空。此时 Generator 会生成一个 Family 7 Cut，其 Literal 仅仅是 `not(Facility_A[slot] = pose_A)`。
*   **后果**: 极其严重的 **False Positive**。这个 Cut 永久封杀了 `pose_A`（在当前 Ghost 下），但实际上 `pose_A` 是完全合法的，真正导致 Infeasible 的是 `Facility_B` 的摆放。一旦 Master 回溯移走 Facility B，A 本可以正常获得 Power，但却被这个残缺的 Cut 误剪了。
*   **修复建议**: Generator 必须区分 CoverSet 是被 Ghost/Exterior 彻底清空的（此时单 Literal 安全），还是被 `cell_owner` 挤压空的。如果是后者，Cut 的 Literals 必须把占用 Pole 候选格子的其他 Facility 实例也加进来（退化为类似 `pattern_nogood` 的多 Literal Cut）。

#### 2. [Replay 逻辑 Bug] Family 6 (Shape Hall) 深度 Cut 在浅层 Replay 必遭误杀 (Quarantine)
*   **出处**: `06_shape_packing_hall.md` §5a (`compute_baseline_partition_lens`) & §7 (Validator)
*   **问题**: §5a 中计算 `partition_lens` 时，明确包含了 `blocked.update(state.cell_owner.keys())`。这意味着 Partition 是高度 State-dependent（依赖当前放置的其他设施）的。但在 §7 Validator 重算时，要求 `tuple(recomputed_lens) == tuple(cert_partition_lens)`，否则直接返回 `unsound` 并 Quarantine。
*   **后果**: 如果在搜索树深层 (Depth 10) 触发了 Hall Cut，其 `partition_lens` 会因为各种 `cell_owner` 变得非常细碎（比如 `[1, 2, 1]`）。当跨 Candidate 或回溯到浅层 (Depth 0) Replay 这个 Cut 时，浅层的 `cell_owner` 是空的，算出来的 `recomputed_lens` 可能是 `[10]`。Validator 发现 `[10] != [1, 2, 1]`，判定 Cut Unsound 并将其永久 Quarantine。这导致 Family 6 的 Cut 根本无法跨层/跨 Candidate 存活。
*   **修复建议**: Geometric Cut 的 Partition 应该 **只** 依赖 `ghost_cells` 和 `exterior_blocks`（Static 属性）。如果真要包含 `cell_owner` 造成的碎片化，就不能走 Geometric 路线，必须把贡献碎片的 Facility 作为 Literals 记录下来。

#### 3. [Soundness 矛盾] Family 1 (Region Capacity) 动态 Capacity 与无条件 True 的冲突
*   **出处**: `01_region_capacity.md` §2a (Capacity bound) & §6 (evaluate_geometric)
*   **问题**: §2a 定义 `cap_R` 时提到“减 already-placed-and-fixed overlap”，如果这包含了 `cell_owner`（即动态 Capacity），那么 `cap_R` 是随着 Master 放置而缩小的。然而，§6 的 `evaluate_geometric_region_capacity_v3` 却为了“Propagation 简化”**无条件返回 `True`** (`return True # cert.demand_R > cert.cap_R, scope 内永 violate`)。
*   **后果**: 如果 `cap_R` 是在深层因为其他设施放置而缩小的，生成 Cut 后无条件返回 True，会导致回溯到浅层时（此时其他设施已移走，实际 Capacity 已经恢复，`demand_R ≤ cap_R`），该 Cut 依然在 Propagation 中无条件报错，造成 **False Positive** 误剪。
*   **修复建议**: 明确 `cap_R` 的定义。如果 `cap_R` 仅由 Ghost 决定（Static），无条件 True 是对的；如果 `cap_R` 包含 `cell_owner`，则 `evaluate_geometric` 必须实时重算 `current_cap` 并判断 `demand_R > current_cap`。

#### 4. [Schema 漏字段] `blocked_cells_hash` 沦为摆设，Replay 算法未校验
*   **出处**: `cut_lifecycle_v2.md` §4 (Scope-aware replay 算法)
*   **问题**: `schema_update_v3.md` (Gap 4) 明确说明 `ghost_rect_id` 只 Hash 矩形坐标，而把 Exterior blocks 等交给 `CutScope.blocked_cells_hash`。但在 §4 的 `replay_cut` 5 步 Verify 算法中：Step 1 查 Source，Step 2 查 Ghost ID，Step 3 查 Artifact Hashes，Step 4 查 Oracle，Step 5 查 Assumptions。**全程没有任何一行代码校验 `cut.scope.blocked_cells_hash == current_blocked_cells_hash`**。
*   **后果**: 如果跨 Session/Phase 时 Exterior blocks 发生了改变（比如地图某处新增了不可用地形），旧的 Cut 会被错误地 Attach，因为它的 `blocked_cells_hash` 根本没被检查。

#### 5. [Schema 漏字段] Family 1 Cert 缺少 `pose_shape` 导致 Validator 隐藏假设
*   **出处**: `01_region_capacity.md` §3 (Cert payload schema) & §7 (Validator)
*   **问题**: 在 Validator 中，重算 Demand 时调用了 `recomputed_demand_R += state.groups[gid].demand * self._cells_per_pose(gid)`。但是 `RegionCapacityCert` 的 Schema 中只有 `contributing_groups: Tuple[Tuple[GroupId, int], ...]`，并没有记录生成该 Cut 时所依据的 `cells_per_pose`。
*   **后果**: Validator 强依赖了外部状态 (`self._cells_per_pose`)，如果 Source-of-truth 发生了微调（某个 Facility 从 3x3 变成了 2x3），Validator 可能会用新的 Size 去乘旧的 Demand，导致重算结果与 Cert 内部的 `demand_R` 不匹配，从而引发不可预期的 Quarantine。应当将 `cells_per_pose` 作为 Cert 的一部分固化下来，或者作为 Active Assumption 显式声明。

---

### 任务 B: 构造 F5+ 反例 (突破现有 7 大 Family 的盲区)

现有的 4 个 Geometric/Literal Family (F1, F2, F3, F4) 加上 PCR-CUT (F2/F4) 和 D2 (F4)，完美覆盖了区域容量、形状匹配、局部电力覆盖和单条传送带寻路。

但我为你构造 **F5: Power Grid Disconnect (全局电力孤岛)** 反例。在这个反例中，现有的 7 个 Family **全部静默**，但 Master Assignment 实际上是 INFEASIBLE 的。

#### F5 反例几何与设定
*   **Grid**: 70x70
*   **Ghost**: 一个纵向的巨大矩形 `G = (x=30..44, y=0..69)`，宽度为 15，像一条河一样把地图切成绝对不相连的左半区 (Left) 和右半区 (Right)。
*   **设施放置**:
    *   `protocol_core` (全局电力枢纽，必须连接) 放置在 Left 区 `(10, 10)`。
    *   `crusher_A` 和 `shop_B` 放置在 Right 区 `(60, 60)` 和 `(60, 65)`。
*   **网络设定**:
    *   传送带 (Belt) **不需要**跨区：`crusher_A` 和 `shop_B` 之间互相连传送带，内部消化了产物。
    *   电力网络 (Power)：所有设施必须通过 Power Pole 连回 `protocol_core`。Power Pole 的最大连接半径 `R_conn = 10`。

#### 为什么现有 7 个 Family 全部静默？
1.  **Family 1 (Region Capacity)**: 左右半区空间极大，容量远超需求。**Pass**。
2.  **Family 6 (Shape Hall)**: 空间连续且充裕，没有碎片化。**Pass**。
3.  **Family 7 (Power Hitting Set)**: F7 的数学定义 (§1a) 是 `CoverSet(p, state) ≠ ∅`。在 Right 区，`crusher_A` 和 `shop_B` 周围有大把的空地可以放 Power Pole。因此它们的局部 CoverSet 绝对不为空！F7 认为局部有电线杆可以覆盖，**Pass**。
4.  **Family 4 (Component Reach / D2)**: F4 是基于 `state.free_cells` 跑 BFS 查连通性。但由于 `crusher_A` 和 `shop_B` 的传送带需求在 Right 区内部已经闭环（互相连接），它们**不需要**向 Left 区寻路。因此 Belt Routing Oracle 认为可行，**Pass**。
5.  **Family 2 (Cutset)**: 同上，没有跨区的 Belt 流量需求，Cutset 不会触发。**Pass**。

#### 真实结果：INFEASIBLE
尽管 `crusher_A` 旁边能造电线杆，但这根电线杆**永远无法跨越宽度为 15 的 Ghost 连回 Left 区的 `protocol_core`**（因为 `R_conn = 10 < 15`）。Right 区成为了一个**全局电力孤岛**。Master 的这个 Assignment 是绝对的 INFEASIBLE。

#### 结论
当前的 B Design v2 缺乏对 **Power Network Global Connectivity (电力网全局连通性)** 的 Cut 表达。Family 7 仅保证了“设施头上能插眼（局部覆盖）”，但没有保证“眼能连回基地”。
**Day 17 建议**: 需要引入一个新的 Family（例如 `power_grid_reach`），或者将 Family 4 (`component_reach`) 的语义泛化，使其不仅能跑 Belt 的连续 Free Cell BFS，还能跑基于 `R_conn` 跃迁的 Power Pole BFS。