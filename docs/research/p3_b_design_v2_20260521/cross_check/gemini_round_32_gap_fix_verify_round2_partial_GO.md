# Round 32 Gemini AUDIT mode — verify Gap 11-14 fix landed

## 工作模式声明
当前处于严格 AUDIT mode。本次审查基于 Round 31 提出的 5 个 Gap 修复（commit a82c97e），通过对 `src/` 源码与真数据 schema 的逐行比对，验证修复是否真正落地且 Sound。

---

## 任务 A: 验 Gap 11-14 修是否 sound + 完整

经过严格比对，Round 31 提出的 Gap 11-14 修复已全部正确落地，彻底解决了原有的 Crash 和 False Negative (FN) / False Positive (FP) 致命断层。

### 1. Gap 11 Direction 修复验证 (Sound)
*   **Cite**: `src/cuts/helpers/candidate_placements.py:30`
*   **验证逻辑**: 修复将 `DIRECTION_OFFSETS` 更新为 `"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)`。
*   **真数据 Sample 验证**:
    *   **Sample 1 (`manufacturing_3x3`)**: `viewer::mfg_crusher_sandleaf_001`，Anchor `(1, 10)`，`occupied_cells` 为 `x ∈ [1,3], y ∈ [10,12]`。其 Output Port 位于 `x=2, y=10, dir="N"`。应用 `N=(0, -1)`，计算得 `front_cell = (2, 9)`。`y=9` 严格在 `occupied_cells` 的 `y ∈ [10,12]` 边界之外。
    *   **Sample 2 (`boundary_storage_port`)**: `viewer::boundary_required_output_blue_iron_ore_019`，Anchor `(0, 10)`，`occupied_cells` 为 `(0,10), (0,11), (0,12)`。Output Port 位于 `x=0, y=10, dir="N"`。应用 `N=(0, -1)`，计算得 `front_cell = (0, 9)`，严格在设施外部。
    *   **Sample 3 (`manufacturing_6x4`)**: `viewer::mfg_filling_capsule_001`，Anchor `(1, 50)`，`occupied_cells` 为 `x ∈ [1,6], y ∈ [50,53]`。Input Port 位于 `x=3, y=53, dir="S"`。应用 `S=(0, 1)`，计算得 `front_cell = (3, 54)`，严格在设施外部。
*   **结论**: 修复后的坐标系推导与真数据几何特征 100% 吻合，彻底解决了原版 `N=(-1,0)` 导致 `front_cell` 算在设施内部的致命 FP。

### 2. Gap 12 Schema 撕裂修复验证 (Sound)
*   **Cite**: `src/cuts/lifecycle.py:145` & `src/cuts/lifecycle.py:421`
*   **验证逻辑**:
    *   `GroupState.selected_poses` 已被正确修正为 `List[PoseId] = field(default_factory=list)`，与 `state_machine_v2.md` 的契约完全对齐。
    *   `evaluate_literal_multiset` 中的循环已修正为 `for pose_id in state.groups[gid].selected_poses:`，并使用 `state_counts[(gid, pose_id)] += 1` 进行计数。
*   **结论**: 彻底消除了原版 `for tup_gid, pose_id in ...` 尝试对 string 进行 tuple unpack 导致的 100% Crash 风险。Multiset 包含语义的 Counter 匹配逻辑完全 Sound。

### 3. Gap 13 Spec Fixture 同步验证 (Sound)
*   **Cite**: `docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md` (Fixture section) & `src/cuts/families/region_capacity.py:60`
*   **验证逻辑**: Spec 文档的 Fixture 已更新为 `region_kind="left_or_bottom_union"`，`cap=137`，`demand=138`。这与 `region_capacity.py` 中 `left | bottom` 去重后 139 cells 的真实数学逻辑完全一致。
*   **结论**: 消除了 Spec 示例与代码实现之间的硬冲突，Validator 不会再因为 `region_kind` 不匹配而误判 Fixture 为 `unsound`。

### 4. Gap 14 O(N) 线性扫描性能修复验证 (Sound)
*   **Cite**: `src/cuts/helpers/candidate_placements.py:44` (`find_pose`)
*   **验证逻辑**: 引入了 `_POSE_CACHE_KEY = "__pose_id_cache__"`。在首次调用时，遍历 `facility_pools` 构建 `(ft, pose_id) -> pose` 的字典缓存，后续调用直接 `return cache.get((ft, pose_id))`。
*   **结论**: 将单次 Validate 轮次中可能高达百万次的 dict 线性比对降维至 O(1) Hash 查找，成功挽救了 Step 5 的 1s Timeout Budget。

---

## 任务 B: 找 fix 引入的新 bug 或漏修 (5 High-Risk Hypotheses)

在确认没有 Critical 级别的 Crash 或 100% FN/FP 后，我深入挖掘了当前架构在扩展性和并发场景下的 5 个高风险隐患（High-Risk Hypotheses）：

### 1. [High-Risk] `_POSE_CACHE_KEY` 注入导致的多线程并发 Mutation 风险
*   **Cite**: `src/cuts/helpers/candidate_placements.py:51` (`cp[_POSE_CACHE_KEY] = cache`)
*   **隐患详情**: 代码直接修改了传入的 `state.candidate_placements` 字典以挂载缓存。如果 CP-SAT 的多个 Worker 线程共享同一个只读的 `BState` 实例并并发执行 Cut Evaluate，这种 Lazy-build 的字典 Mutation 极易引发 `RuntimeError: dictionary changed size during iteration` 或竞态条件。
*   **建议**: 在 Phase 1.2 中，应将 Cache 提升至 `BState` 的初始化阶段（预热），或使用线程安全的锁机制，避免在 Hot Path 中修改共享的只读数据结构。

### 2. [High-Risk] `contributing_groups` Payload 存储了 `cpp` 而非 `demand_in_R` (Schema 违背)
*   **Cite**: `src/cuts/oracles/region_capacity_oracle.py:117` (`"contributing_groups": [[gid, d] for gid, d in contributing_groups]`)
*   **隐患详情**: 根据 Spec §3，`contributing_groups` 应该存储 `(group_id, demand_in_R)`。但在 Oracle 的 `_build_cut` 中，传入的 `contributing_groups` 列表里的 `d` 实际上是 `cpp` (cells_per_pose)。因此 Cert Payload 中存储的是 `[gid, 3]` 而不是 `[gid, 138]`。
*   **为何当前未爆**: `src/cuts/families/region_capacity.py:151` 的 Validator 在读取时，直接忽略了 Payload 中的数值（将其命名为 `_demand_in_cert`），并使用 `state.groups[gid].demand * cpp` 重新计算了 Demand。
*   **风险**: 一旦 Phase 1.1 的 Minimizer (Step 2) 尝试通过削减 `demand_in_R` 来生成 Minimal Core，Validator 的强制重算将导致 `demand_R mismatch`，从而错误地 Quarantine 合法的 Minimized Cut。

### 3. [High-Risk] "Free" Placement 设施静默消耗 Boundary 容量 (False Negative 风险)
*   **Cite**: `src/cuts/families/region_capacity.py:102` (`_group_falls_in_region`)
*   **隐患详情**: `manufacturing_3x3` 等设施没有 `placement_rule`，Fallback 为 `"free"`。`_group_falls_in_region` 会直接返回 `False`，这意味着它们永远不会被计入 `left_or_bottom_union` 的 `demand_R`。
*   **风险**: 如果 Master Solver 在搜索过程中，将大量 `"free"` 设施放置在了 Boundary 区域，Boundary 的实际可用容量将急剧减少。但由于 F1 的 `cap_R` 是静态的（仅减去 Ghost 和 Exterior），F1 Cut 无法感知这种动态的容量挤压，导致本该 Infeasible 的状态无法触发 Cut（False Negative）。

### 4. [High-Risk] `cells_per_pose = w * h` 假设在非矩形设施下的高估风险
*   **Cite**: `src/cuts/helpers/canonical_rules.py:44` (`cells_per_pose_for_group`)
*   **隐患详情**: 当前通过 `w * h` 计算 `cells_per_pose`。虽然在当前的真数据（3x3, 5x5, 6x4, 1x3）中恰好成立，但这是一种脆弱的几何假设。
*   **风险**: 如果未来引入 L 型或带有缺口的设施（例如 4x4 占地但实际只占用 14 cells），`w * h` 将严重高估该设施的 `demand_R`。这会导致 F1 Region Capacity 过早触发，产生 False Positive，剪掉合法的搜索空间。最稳健的做法是读取 `candidate_placements` 中 `len(occupied_cells)`。

### 5. [High-Risk] `evaluate_geometric` 无条件返回 True 导致 `GHOST_AGNOSTIC` 永久死胡同
*   **Cite**: `src/cuts/families/region_capacity.py:246` (`evaluate_geometric_region_capacity`)
*   **隐患详情**: 该函数当前无条件 `return True`。对于绑定了 `ghost_rect_id` 的 Cut，当 Ghost 改变时，Watcher 会将其 Invalidate，这很 Sound。但对于 `GHOST_AGNOSTIC` 的 Cut（例如 Ghost 完全不与 Union 区域相交），它永远不会被 Watcher 移除。
*   **风险**: 如果 `demand_R` 或 `cap_R` 的计算存在任何边缘 Case 的瑕疵（例如上述的 High-Risk 3 或 4），导致错误地生成了一个 `GHOST_AGNOSTIC` Cut，这个无