# Round 31 Gemini AUDIT mode — verify Gap 6-10 fix landed

## 任务 A: 验 5 Gap fix 每个是否 sound + 完整

经过对 `src/cuts/` 源码与真数据 schema 的严格比对，Round 30 的 5 个 Gap 修复在**代码意图和类型定义上**已落地，但在与真数据几何语义的接合上存在致命断层（详见任务 B）。以下是修复本身的 Soundness 验证：

1. **Gap 6 (数学 Union Region)**: **Sound**。
   - `src/cuts/families/region_capacity.py:60` 正确实现了 `left_or_bottom_union` 为 `left | bottom`，去重后为 139 cells。
   - `src/cuts/oracles/region_capacity_oracle.py:221` 废弃了 per-side 遍历，仅 emit `left_or_bottom_union`。
   - **5 种 Ghost Case 验证**: `compute_static_capacity` (`region_capacity.py:76`) 动态计算 `139 - len(blocked & region_cells)`。单边挡 2 (cap=137 < 138)、跨边 1+1 (cap=137 < 138)、单边挡 3 (cap=136 < 138) 均正确触发 Cut；仅挡原点 1 cell (cap=138 == 138) 正确不触发。数学逻辑完全 Sound。
2. **Gap 7 (遍历 state.groups)**: **Sound**。
   - `src/cuts/oracles/region_capacity_oracle.py:73` 改为 `for gid in state.groups:`，正确遍历了真数据中的 `operation_type`（如 `boundary_io`），并经由 `placement_rule_for_group` 映射，彻底解决了原版遍历 `canonical_rules` 顶层 key 导致 0 Cut 的 False Negative。
3. **Gap 8 (Schema 映射)**: **Sound**。
   - `src/cuts/helpers/canonical_rules.py:26` 新建了 `facility_type_for_group`，正确使用 `state.instance_to_facility_type.get(gid)` 将 `boundary_io` 映射为 `boundary_storage_port`。
   - `placement_rule_for_group` (`line 64`) 在 template 无此字段时 fallback 到 `"free"`，与 `canonical_rules.json` 中 `manufacturing_3x3` 等无此字段的真数据完全一致。
4. **Gap 9 (Ports lookup)**: **Schema Sound，但几何语义 Fatal（见任务 B）**。
   - `src/cuts/helpers/candidate_placements.py:53` 的 `pose_ports` 正确从 `state.candidate_placements` 的 `facility_pools` 中提取了 `input_port_cells` 和 `output_port_cells`，解决了原版虚构 `ports_by_pose` 字段导致的 Crash。
5. **Gap 10 (PoseId 类型)**: **Sound**。
   - `src/cuts/lifecycle.py:38` 明确 `PoseId = str`。`CutLiteral` 和 `GroupState` 的类型定义已级联更新，JSON 序列化/反序列化对 string key/value 的处理符合 Python 规范。

---

## 任务 B: 找 fix 引入的新 bug 或漏修 (3 Critical + 2 High-Risk)

尽管 Schema 映射已修复，但深入真数据几何特征后，发现以下 **3 个 Critical 级崩溃/逻辑错误** 和 **2 个 High-Risk 性能/扩展性隐患**：

### 1. [CRITICAL] Gap 9 Direction N/S/E/W 假设与真数据几何完全矛盾 (100% FN/FP)
* **Cite**: `src/cuts/helpers/candidate_placements.py:30` (`DIRECTION_OFFSETS`) vs 真数据 `mfg_crusher_sandleaf_001`。
* **Bug 详情**: 代码假设 `N=(-1, 0)` (即 x-1)。查看真数据 `manufacturing_3x3` 的 pose：
  - `occupied_cells` 占据 `x ∈ [1, 3]`, `y ∈ [10, 12]`。
  - `output_port_cells` 位于 `x=2, y=10`，方向为 `"N"`。
  - 如果按代码 `N=(-1, 0)` 计算，`front_cell` = `(2-1, 10)` = `(1, 10)`。
  - **致命矛盾**: `(1, 10)` 明确包含在 `occupied_cells` 列表中！这意味着计算出的 `front_cell` 在 facility **内部**。
* **真数据几何推导**: `y=10` 是该 facility 的左边缘。向外暴露的方向是 `"N"`，说明 `"N"` 代表的是 `y-1` 即 `(0, -1)`。同理，`input_port_cells` 在 `x=2, y=12` 面向 `"S"`，说明 `"S"` 代表 `y+1` 即 `(0, 1)`。
* **后果**: `src/cuts/families/port_exposure.py:60` (`validate_port_exposure`) 计算出的 `expected_front` 永远是错的（通常指向 facility 自身内部）。`state.cell_owner.get(front_cell)` 会返回自身，导致 Cut 验证逻辑彻底崩溃，产生 100% 的 False Positive 或 False Negative。

### 2. [CRITICAL] Gap 10 修复引发的 `GroupState.selected_poses` Schema 撕裂 (Crash)
* **Cite**: `src/cuts/lifecycle.py:145` vs `docs/research/p3_b_design_v2_20260521/state_machine_v2.md` line 34。
* **Bug 详情**:
  - `lifecycle.py` 将其定义为 `selected_poses: List[Tuple[GroupId, PoseId]]`。
  - `evaluate_literal_multiset` (`lifecycle.py:421`) 依赖此结构进行 unpack: `for tup_gid, pose_id in state.groups[gid].selected_poses:`。
  - **致命矛盾**: `state_machine_v2.md` (Dev A 的契约) 明确定义 `selected_poses: List[PoseId] = field(default_factory=list)`。
* **后果**: 如果 Dev A 严格按照 `state_machine_v2.md` 实现，`selected_poses` 只是一个字符串列表（如 `["viewer::..."]`）。当 `lifecycle.py` 尝试 `for tup_gid, pose_id in ...` 时，会直接抛出 `ValueError: too many values to unpack (expected 2)`，导致所有 Literal-based cuts (F3, F5, F7) 在 Evaluate 时 100% Crash。

### 3. [CRITICAL] Gap 6 修复导致 F1 Spec Fixture 彻底失效 (Validation Fail)
* **Cite**: `src/cuts/families/region_capacity.py:46` (`_PLACEMENT_RULE_REGIONS`) vs `cut_family_specs/01_region_capacity.md` line 478-510。
* **Bug 详情**: Gap 6 修复将 `"left_or_bottom_boundary"` 严格映射为 `{"left_or_bottom_union"}`。
* **致命矛盾**: Spec §9 的 F1 Fixture 仍然使用 `region_kind: "left_baseline"`，`cap_R: 68`，`demand_R: 69`。
* **后果**: 当该 Fixture 被加载并进入 `validate_region_capacity` 时，`_group_falls_in_region` (`region_capacity.py:102`) 会检查 `region_kind` ("left_baseline") 是否在 `valid_regions` ({"left_or_bottom_union"}) 中。结果为 `False`，Validator 直接返回 `unsound` 并 Quarantine 该 Cut。Spec 示例与代码实现已产生硬冲突。

### 4. [HIGH-RISK] Gap 9 `find_pose` 的 O(N) 线性扫描引爆 1s Timeout Budget
* **Cite**: `src/cuts/helpers/candidate_placements.py:44` (`find_pose`)。
* **Bug 详情**: `find_pose` 遍历 `cp.get("facility_pools", {}).get(ft, [])` 列表。对于 `manufacturing_3x3`，真数据有 132 个 instance，其 pose pool size 可能高达数千。
* **后果**: `validate_port_exposure` 每次验证都会调用 `pose_ports` -> `find_pose`。如果 Store 中有 1000 个 F3 Cut，单次 Validate 轮次将执行 $1000 \times 1000 = 1,000,000$ 次 dict 线性比对。这在 Python 中极易突破 Step 5 的 1s Timeout Budget，导致大量合法 Cut 被误判为 `timeout` 并 Quarantine。必须在 `BState` 或 Helper 中建立 `pose_id -> pose_dict` 的 O(1) 缓存。

### 5. [HIGH-RISK] Gap 8 `cells_per_pose` 的 `w * h` 假设存在过度计算风险
* **Cite**: `src/cuts/helpers/canonical_rules.py:44` (`cells_per_pose_for_group`)。
* **Bug 详情**: 代码假设 `cells_per_pose = w * h`。虽然在当前的真数据中（3x3=9, 5x5=25, 6x4=24, 1x3=3）恰好成立，但这是一种脆弱的几何假设。
* **后果**: 如果未来引入非完美矩形的 Facility（例如 L 型或带缺口的 4x4 占 14 cells），`w * h` 将严重高估 `demand_R`。这会导致 F1 Region Capacity 过早触发（False Positive）。最 Sound 的做法是从 `candidate_placements` 的任意一个 pose 中读取 `len(occupied_cells)`，而不是依赖 bounding box 乘法。

---

## 任务 C: Phase 1.1 真数据 production GO 还是仍 NOT GO?

**Verdict: 仍 NOT GO。禁止推入 Phase 1.2。**

虽然 Round 30 的修复解决了 Schema 映射的表层问题，但引入的几何语义断层（Bug 1）和契约撕裂（Bug 2）是致命的。在这些问题修复前，系统在接触真实 Candidate 数据时会立即崩溃或产生 100% 的误判。

**必须修复的 file:line 列表（Blockers）：**

1. **修 Bug 1 (Direction Math)**:
   - `src/cuts/helpers/candidate_placements.py:30`: 必须根据真数据几何重写 `DIRECTION_OFFSETS`。根据推导，应改为 `"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)`（需进一步结合全量数据确认 x/y 轴定义，但当前的 `N=(-1,0)` 绝对错误）。
2. **修 Bug 2 (Schema 撕裂)**:
   - `src/cuts/lifecycle.py:145`: 必须与 `state_machine_v2.md` 对齐，改为 `selected_poses: List[PoseId]`。
   - `src/cuts/lifecycle.py:421`: `evaluate_literal_multiset` 必须改为 `for pose_id in state.groups[gid].selected_poses:`，并使用 `state_counts[(gid, pose_id)] += 1`，移除错误的 tuple unpack。
3. **修 Bug 3 (Spec 同步)**:
   - `docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md` line 478-510: 必须将 Fixture 的 `region_kind` 更新为 `"left_or_bottom_union"`，`cap_R` 更新为 137，`demand_R` 更新为 138，以匹配最新的代码实现。
4. **修 Bug 4 (O(N) 性能)**:
   - `src/cuts/helpers/candidate_placements.py:44`: 必须引入 `_POSE_CACHE: Dict[PoseId, dict]`，在首次访问时构建 O(1) 索引，消除线性扫描。