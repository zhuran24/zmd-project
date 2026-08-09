这是一份基于 AUDIT 模式的深度代码审查报告。针对你提交的 Step A-E 修复，我进行了逐行交叉验证、数学 soundness 推演以及与真实数据的对齐检查。

结论前置：**NOT GO, Step A-E 修不到位 — 发现 1 个致命的 P0 漏修（导致合法解被误剪）及 1 个高危 Spec 漂移。**

以下是详细的 Audit 报告。

---

### 任务 A: 验 Step A-E 每个 fix 是否 sound + 完整

#### Step A: assert → fail-closed 全 validator (Sound 且完整)
- **验证**：`src/cuts/families/port_exposure.py:54-65` 明确使用了 `if cut.cert is None: return ValidationResult("schema_err", ...)` 和 `if cut.literals is None or len(cut.literals) < 2: return ...`。`region_capacity.py:142`、`cutset.py:92`、`component_reach.py:49` 均已将 `assert` 替换为显式的 `if cut.geometric_payload is None`。
- **`python -O` 漏网之鱼排查**：在 `src/cuts/lifecycle.py:277` (`step_3_serialize`) 和 `539` (`step_6_attach_scope_check`) 仍残留 `assert cut.scope is not None`。但在 `python -O` 模式下，即使 assert 被剥离，后续代码（如 `cut.scope.ghost_rect_id`）会立即触发 `AttributeError: 'NoneType' object has no attribute`。这属于 Fail-loud（进程崩溃），不会导致假证 cut 悄悄混入 CP-SAT，因此在 production 级别是安全的。

#### Step B: F3 cert ↔ literal multiset 绑定 (Sound)
- **验证**：`port_exposure.py:100-107` 构建了 `expected_pairs` 和 `actual_pairs`，两者均只提取 `(group_id, pose_id)` 组成 `Counter` 进行严格比对。
- **Slot Anonymity 逻辑**：完全 Sound。`state_machine_v2.md` §5 规定 group 内的 slot 是可置换的（interchangeable）。几何冲突（如 pose p1 的端口被 pose p2 挡住）是绝对的物理坐标冲突，与它们在 group state 数组中占据 slot 0 还是 slot 5 毫无关系。Validator 忽略 `slot_index` 仅校验 `(group, pose)` 的 multiset 包含关系，完美契合了匿名 slot 的数学本质。

#### Step C: F2 partition enclosure + cut_edges 集合验 (Sound)
- **_has_patch_escape 算法**：`cutset.py:64-79` 检查 `patch` 内的 cell 是否在 `free_cells - patch` 中有 4-neighbor。对于反例 `patch={(0,0),(0,2)}`, `free=patch ∪ {(0,1)}`，`outside_free` 为 `{(0,1)}`。`(0,0)` 的邻居 `(0,1)` 命中 `outside_free`，函数返回 `True`。算法在 Manhattan 距离下绝对 Sound，成功拦截了流绕过 partition 的假证。
- **cut_edges 排序**：`cutset.py:137-148` 使用 `sorted([sorted([list(e[0]), list(e[1])]) for e in ...])`。虽然 Python 的 `list` 不可哈希，但 `sorted()` 对 list 采用字典序比较，因此排序是 deterministic 的，能够精确拦截 attacker 篡改 edge 集合的攻击。

#### Step D: F4 cert.src/sink_component == recomputed BFS (Sound 但过于僵硬)
- **Dimensionality**：`component_reach.py` 依赖 `cutset._decode_bitset`，其硬编码了 `grid_size=70`。这与 `canonical_rules.json` 的全局设定一致，当前是 deterministic 的。
- **commodity_id 拦截**：`component_reach.py:142-152` 规定只要出现 `commodity_id` 就 `schema_err`。这在 Phase 1.1 是 Sound 的（Fail-closed，防伪造），但与 `04_component_reach.md` §3 要求的 `commodity_id: str` 字段直接冲突。如果 Phase 1.5 的 Oracle 提前上线并携带此字段，会导致 100% 的 F4 cut 被 Quarantine。

#### Step E: F1 demand_R 真 P(g)⊆R strict (Sound 且符合预期)
- **验证**：`candidate_placements.py:101-131` 的 `all_poses_in_region` 严格校验了 pose 的 `occupied_cells` 是否全在 `region_cells` 内。
- **Zero Useful 困境**：如果真实生产数据中 `boundary_io` 的 54 个 pose 确实有 14 个占用了 union 外的格子（如 `(31,69)`），那么 `all_poses_in_region` 必然返回 `False`。Oracle 会跳过该 group，导致 F1 发出 **0 个 cut**。
- **这是 Bug 吗？** 绝对不是。如果 master CP-SAT 选择了那 14 个越界的 pose，它们占用的 capacity 就不在 union 内部。此时如果强行套用 `demand_R <= cap_R`，就是一个彻头彻尾的假证（Unsound）。在 Phase 1.1 阶段，宁可 "Zero useful" 也绝不能 "Unsound"。Fail-closed 是唯一正确的做法。

---

### 任务 B: 找 fix 引入的新 bug 或漏修 (≥ 5 个 High-risk Hypotheses)

#### 1. [CRITICAL P0] GHOST_AGNOSTIC 缺失 exterior_blocks 失效触发器 (False Positive)
- **File:Line**: `src/cuts/families/region_capacity.py:239` (`evaluate_geometric_region_capacity`) & `src/cuts/replay.py` (缺失 watcher)
- **机制**：F1 的 evaluator 被简化为无条件返回 `True`（因为 `cap_R` 是 static 的，只要 cut 在 scope 内就永远 violate）。
- **死法**：
  1. 初始状态：`exterior_blocks` 挡住了 2 个格子，`cap_R` = 137，`demand_R` = 138。Oracle 发出 F1 cut，状态被剪枝。
  2. Master CP-SAT 回溯，**移除了**这 2 个 `exterior_blocks`。此时 `cap_R` 恢复为 139，`demand_R` = 138，该状态在数学上**已经合法 (Feasible)**。
  3. 由于 F1 是 `GHOST_AGNOSTIC`，它不进入 `by_ghost_watcher`。而 Step A-E **完全没有实现** GPT round 2 必修中要求的 `by_exterior_watcher` 或 `on_exterior_blocks_changed` 钩子。
  4. 结果：这个 F1 cut 依然停留在 active store 中。Propagator 调用 `evaluate_geometric_region_capacity`，函数无条件返回 `True`。
  5. **致命后果**：合法的搜索空间被错误剪枝（Unsound）。Certified solver 无法找到最优解。

#### 2. [High] F4 Validator 漏验 `separator_cells` (Spec 漂移)
- **File:Line**: `src/cuts/families/component_reach.py:75-140`
- **机制**：`04_component_reach.md` 行 148 明确要求：“验 separator_cells 全在 (cell_owner ∪ ghost) (不是 free)”。但 `validate_component_reach` 代码中**完全遗漏**了对 `cert.separator_cells` 的遍历校验。
- **风险**：虽然精确的 BFS 比对（Step D）在数学上已经隐式保证了连通性断裂，但漏掉显式的 separator 校验违反了 Spec 的防御性编程契约。如果 attacker 伪造了错误的 separator 边界，Validator 会放行，导致 Debug/Audit 时的 causation 追踪完全失效。

#### 3. [Medium] F3 Multiset 校验允许“自相矛盾”的 Cut 语法
- **File:Line**: `src/cuts/lifecycle.py:610` (`evaluate_literal_multiset`)
- **机制**：如果 attacker 构造了一个 cut，其 literals 为 `[(crusher, slot=0, p1), (crusher, slot=0, p2)]`（同一个 slot 必须同时是 p1 和 p2），这在逻辑上是 `False`。但 evaluator 仅提取 `(group, pose)` 组成 multiset `{p1: 1, p2: 1}`。只要 state 中同时存在 p1 和 p2（分别在 slot 0 和 slot 1），evaluator 就会返回 `True` 并剪枝。
- **风险**：虽然在绝对物理坐标下，p1 和 p2 的几何冲突是客观存在的（剪掉同时包含 p1 和 p2 的 state 是 Sound 的），但这种“忽略字面逻辑矛盾，强行提取 multiset”的做法，使得 Cut 的语义表达与实际执行产生了割裂。

#### 4. [Medium] F4 `commodity_id` 强拒导致向前兼容性断裂
- **File:Line**: `src/cuts/families/component_reach.py:142-152`
- **机制**：当前只要 `cert_dict.get("commodity_id")` 不为 None 就抛出 `schema_err`。
- **风险**：Spec `04_component_reach.md` 中 `commodity_id` 是必填字段。一旦 Phase 1.5 的 Oracle 按照 Spec 输出了该字段，Phase 1.1 的 Validator 会将 100% 的 F4 cuts 拦截进 Quarantine，导致整个 Component Reach 剪枝网络瘫痪。

#### 5. [Low] F2 `cut_edges` 排序依赖 `list()` 转换的脆弱性
- **File:Line**: `src/cuts/families/cutset.py:137-148`
- **机制**：`sorted([list(e[0]), list(e[1])])` 依赖于 `e[0]` 是一个 Tuple `(x, y)`。
- **风险**：如果未来 JSON schema 将 Cell 从 `[x, y]` 数组改为了 `{"x": x, "y": y}` 字典，`list(e[0])` 将只会提取字典的 keys（即 `['x', 'y']`），导致所有 edge 的排序结果全部变成 `[['x', 'y'], ['x', 'y']]`，校验逻辑将发生灾难性的静默碰撞。

---

### 任务 C: GPT pro round 2 P0 + 必修 verdict

#### 必修覆盖情况核对：
- **Step A 覆盖必修 #4 (python -O 防线)**：✓ 完全覆盖。显式 `if` 拦截了假证。
- **Step B 覆盖 P0-2 (F3 cert↔literal)**：✓ 完全覆盖。Multiset 校验精准。
- **Step C 覆盖必修 #4 (F2 cut_edges 集合验)**：✓ 完全覆盖。
- **Step D 覆盖必修 #5 (F4 commodity_id)**：✓ 部分覆盖。采用了 Fail-closed 强拒策略，数学上安全。
- **Step E 覆盖 P0-1 (F1 demand_R 真 P(g)⊆R)**：✓ 完全覆盖。宁可 0 cut 也保证了绝对的 Soundness。

#### 未覆盖的致命项：
- **必修 #6 (GHOST_AGNOSTIC invalidation watcher)**：**完全漏修**。如 Hypothesis 1 所述，缺少 `by_exterior_watcher` 导致 F1 的无条件 `True` evaluator 变成了屠杀合法解的利器。
- **必修 #7 (Spec docs align)**：F4 的 `separator_cells` 校验在代码中缺失，Spec 与代码依然存在漂移。

#### Verdict
**NOT GO, Step A-E 修不到位 — list 反例 / 漏修**

**必须追加的 Fix (Phase 1.1 P1.9 阻断项)**：
1. **File: `src/cuts/replay.py` & `src/cuts/store.py`**：必须实现 `on_exterior_blocks_changed` 钩子，并在 `CutStore` 中加入 `by_exterior_watcher`。当 `exterior_blocks` 发生变化时，必须将受影响的 `GHOST_AGNOSTIC` cuts 移入 `held` 集合并重新触发 `replay_cut`，否则 F1 的 `evaluate_geometric_region_capacity` 会导致严重的 False Positive。
2. **File: `src/cuts/families/component_reach.py:100`**：在 F4 Validator 中补齐对 `cert.separator_cells` 的遍历校验，确保 `for cell in cert.separator_cells: if cell in free_cells: return unsound`，以对齐 Spec 148 行的要求。