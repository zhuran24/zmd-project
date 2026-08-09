这是一份针对 Phase 1.1 F1 spec-data gap 的深度 Audit 报告。我将直接对比 src 假设与你提供的真数据 schema，指出会导致 crash、False Negative (FN) 或 False Positive (FP) 的致命断层。

---

### 任务 A: Gap 6 数学决策 (F1 demand_R)

**强制推荐: 选项 a) Union region**

**数学证明 (Soundness & No FN):**
定义 $R = \text{left\_baseline} \cup \text{bottom\_baseline}$。
根据真数据，$|R| = 70 + 70 - 1 (\text{原点重叠}) = 139$ cells。
`demand_R` = 46 instances × 3 cells/pose = 138 cells。
`cap_R` = $139 - |\text{ghost} \cap R| - |\text{exterior} \cap R|$。

在 5 种 Ghost 分布 case 下的 Soundness 验证：
1. **Left ghost (单边挡 2 cells)**: `cap_R` = 139 - 2 = 137。`demand_R` (138) > `cap_R` (137)。Cut 触发。**Sound** (因为左侧剩 68 cells 最多放 22 个，底侧 70 cells 最多放 23 个，总计 45 < 46，确实 Infeasible)。
2. **Bottom ghost (单边挡 2 cells)**: 同上，`cap_R` = 137，Cut 触发。**Sound**。
3. **Union ghost (仅挡原点 1 cell)**: `cap_R` = 139 - 1 = 138。`demand_R` (138) == `cap_R` (138)。Cut **不触发**。**Sound** (因为左侧剩 69 cells 刚好放 23 个，底侧剩 69 cells 刚好放 23 个，23+23=46，刚好 Feasible，若触发则是 FP)。
4. **单边 ≥ 2 (左侧挡 3 cells)**: `cap_R` = 139 - 3 = 136。`demand_R` (138) > `cap_R` (136)。Cut 触发。**Sound**。
5. **跨边 1+1 (左挡 1，底挡 1)**: `cap_R` = 139 - 2 = 137。`demand_R` (138) > `cap_R` (137)。Cut 触发。**Sound**。

**反驳选项 b) Per-side region (为什么会 FN):**
如果采用选项 b，$R = \text{left\_baseline}$ (70 cells)，静态设定 `demand_R = 69`。
**致命 FN Case**: 假设 Ghost 挡住了 Bottom 的 3 个 cells。
- Bottom 剩余 67 cells，最多只能放 $\lfloor 67/3 \rfloor = 22$ 个 instance。
- 为了满足 46 个的总需求，Left **必须**放 24 个 instance (需要 72 cells)。
- 但 Left 只有 70 cells，全局已经 **INFEASIBLE**。
- 然而在选项 b 下，Left 的 Cut 评估：`cap_R` = 70 (左侧无 ghost)，`demand_R` = 69。69 ≤ 70，**Cut 不触发 (False Negative)**。
- 结论：单边的实际 demand 是随另一边的 capacity 动态变化的，静态切分 demand 必然导致 FN。

**关于 GHOST_AGNOSTIC 的处理:**
采用 Union region 时，`cap_R` 依赖于 ghost 是否与 Union 区域相交。
根据 `cut_lifecycle_v2.md` v1.2 规则：
- 如果 `state.ghost_cells & region_cells == ∅`，则 `ghost_rect_id = GHOST_AGNOSTIC`，跨 ghost 安全 replay。
- 如果相交，则必须绑定当前的 `compute_ghost_rect_id(state.ghost_rect)`。这在数学上完全 sound，且 `lifecycle.py` Step 3 的 `exterior_blocks_hash` 拆分已经完美支持了这种动态降级。

---

### 任务 B: 找漏的 spec-data gap (未列出的致命断层)

以下是我在对比 `src` 和真数据时发现的 4 个致命 Gap，它们会导致代码在运行时 100% Crash 或静默失效 (FN)。

#### Gap 7: F1 Oracle 遍历 `canonical_rules` 顶层 Key 导致永远 0 Cut (FN)
*   **Cite**: `src/cuts/oracles/region_capacity_oracle.py:65` (`_enumerate_contributing_groups`)
*   **代码假设**:
    ```python
    for gid, entry in canonical_rules.items():
        rule = entry.get("placement_rule")
    ```
*   **真数据**: `canonical_rules.json` 的顶层 keys 是 `["metadata", "globals", "routing_rules", "facility_templates", "recipes", ...]`。
*   **实际差异**: 代码在遍历顶层 keys。当 `gid` = `"facility_templates"` 时，`entry` 是一个包含所有 template 的 dict，它本身并没有 `placement_rule` 字段。因此 `rule` 永远为 `None`。
*   **后果**: `_enumerate_contributing_groups` 永远返回 `[]`。F1 Generator 永远不会生成任何 Cut (100% False Negative)。

#### Gap 8: Group ID 与 Facility Template 命名空间混淆 (Crash)
*   **Cite**: `src/cuts/oracles/region_capacity_oracle.py:117` (`_build_cut`) 和 `src/cuts/families/region_capacity.py:151` (`validate_region_capacity`)
*   **代码假设**: `cells_per_pose_map = {gid: canonical_rules[gid]["cells_per_pose"]}`。代码假设 `gid` (Group ID) 可以直接作为 `canonical_rules` 的 key 来查找属性。
*   **真数据**: 在 `mandatory_exact_instances.json` 中，真实的 Group ID (即 `operation_type`) 是 `"boundary_io"`。但在 `canonical_rules.json` 中，定义物理属性的是 `facility_templates["boundary_storage_port"]`。
*   **实际差异**: `canonical_rules` 中根本不存在 `"boundary_io"` 这个 key。
*   **后果**: 即使修复了 Gap 7，代码在尝试获取 `canonical_rules["boundary_io"]["cells_per_pose"]` 时会立即抛出 `KeyError: 'boundary_io'` (100% Crash)。必须引入 `operation_type` -> `facility_type` 的映射层。

#### Gap 9: F3 Validator 虚构了 `ports_by_pose` 字段 (Crash / FN)
*   **Cite**: `src/cuts/families/port_exposure.py:101`
*   **代码假设**:
    ```python
    ports_by_pose = group_entry.get("ports_by_pose")
    pose_ports = ports_by_pose.get(facility_pose_id)
    ```
*   **真数据**: `canonical_rules.json` 中没有任何 `ports_by_pose` 字段。真实的端口数据存在于 `candidate_placements.json` 中，层级为 `facility_pools[facility_type][pose_idx]["input_port_cells"]` 和 `"output_port_cells"`。
*   **实际差异**: 端口的几何绝对坐标 (x, y, dir) 是在 Pose 生成阶段 (candidate_placements) 确定的，而不是在 canonical_rules (template 阶段) 确定的。
*   **后果**: `ports_by_pose` 永远为 `None`。F3 Validator 会静默跳过端口验证 (FN)，或者在后续尝试迭代 `None` 时 Crash。

#### Gap 10: PoseId 类型断层 (int vs str) 导致 Multiset 匹配失效 (FN)
*   **Cite**: `src/cuts/lifecycle.py:46` (`PoseId = int`) 和 `src/cuts/lifecycle.py:361` (`CutLiteral` 反序列化)
*   **代码假设**: `PoseId` 是一个整数 (例如 0, 1, 2)。
*   **真数据**: `candidate_placements.json` 中的 `pose_id` 是字符串，例如 `"viewer::boundary_required_output_blue_iron_ore_019"`。
*   **实际差异**: `BState.groups[gid].selected_poses` 存储的是字符串 ID，而 CutLiteral 如果被强制转型或假设为 int，会导致类型不匹配。
*   **后果**: 在 `src/cuts/lifecycle.py:284` (`evaluate_literal_multiset`) 中，`Counter` 匹配时 `(gid, int)` 永远无法匹配 `state_counts` 中的 `(gid, str)`。所有 Literal-based cuts (F3, F5, F7) 永远返回 `False` (100% False Negative)。

---

### 任务 C: 是否 NOT GO Phase 1.1?

**Verdict: Phase 1.1 NOT GO until Gap 7+8+9 修**

按当前的 audit findings，Phase 1.1 实际跟真数据接合时 **0 个 family 能跑通**。全部会在 Generator 或 Validator 阶段直接 Crash 或静默失效。

**最可能死法 (Top 3 Crash/FN Paths):**
1.  **F1 Generator 胎死腹中 (Gap 7)**: `src/cuts/oracles/region_capacity_oracle.py:65` 遍历了错误的 JSON 层级，导致 F1 永远无法发现 `boundary_storage_port`，0 cuts generated。
2.  **F1 Validator KeyError (Gap 8)**: 即使手动 mock 绕过 Generator，`src/cuts/families/region_capacity.py:151` 尝试用 `gid="boundary_io"` 去查 `canonical_rules` 时，会直接 `KeyError` 崩溃，因为真数据的 key 是 `boundary_storage_port`。
3.  **F3 Validator 查无此 Port (Gap 9)**: `src/cuts/families/port_exposure.py:101` 试图从 `canonical_rules` 读取 `ports_by_pose`，该字段在真数据中不存在 (实际在 `candidate_placements.json` 中)，导致 F3 验证逻辑完全瘫痪。

**必须修复的 file:line:**
*   **修 Gap 7**: `src/cuts/oracles/region_capacity_oracle.py:65` 必须改为遍历 `canonical_rules.get("facility_templates", {}).items()`。
*   **修 Gap 8**: `src/cuts/families/region_capacity.py:151` 和 `oracle.py:117` 必须引入 `BState` 或外部映射，将 `gid` (`operation_type`) 映射为 `facility_type` 后，再去 `canonical_rules["facility_templates"]` 中查找 `cells_per_pose` 和 `placement_rule`。
*   **修 Gap 9**: `src/cuts/families/port_exposure.py:101` 必须改为从 `state.artifact_hashes` 对应的 `candidate_placements.json` 内存结构中读取 `input_port_cells` 和 `output_port_cells`，而不是查 `canonical_rules`。
*   **修 Gap 6 (数学)**: `src/cuts/oracles/region_capacity_oracle.py:207` 必须实现 Union region 逻辑，将 left 和 bottom 合并为一个 `R` 计算 `cap_R` 和 `demand_R`，废弃当前的 per-side 循环。