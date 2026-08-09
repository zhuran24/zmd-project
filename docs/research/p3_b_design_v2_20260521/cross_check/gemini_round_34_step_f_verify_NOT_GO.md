这是一份基于 AUDIT 模式的深度代码审查报告。针对 Step F (commit e0ec660) 的修复，我进行了逐行交叉验证、性能推演以及与 Spec 的对齐检查。

结论前置：**NOT GO, Step F 修不到位 / 新 P0 出现**。虽然修复了 F1 的数学 Unsoundness 和 F4 的漏验，但 F1 的修复在 CP-SAT 的 Hot Path 中引入了致命的 **P0 性能灾难**，并且完全漏修了 Round 33 强制要求的 `by_exterior_watcher`。

以下是详细的 Audit 报告。

---

### 任务 A: 验 Step F 2 fix sound + 完整

#### Fix 1: F1 evaluate 真重算 (Sound 但引入致命性能 Bug)
- **File:Line**: `src/cuts/families/region_capacity.py:239-248`
- **重算逻辑**: 现 `evaluate_geometric_region_capacity` 确实提取了 `region_cells` 并调用 `compute_static_capacity`。公式 `len(region_cells) - len(blocked & region_cells)` 与 Oracle 完全一致，数学上的 False Positive (误剪合法解) 已被修复。
- **`cert.demand_R` 锁定**: `demand_R` 锁定在 Oracle 生成时的快照是 Sound 的。因为 `demand` 来源于 `mandatory_exact_instances.json` (真数据中 boundary_io demand=46)，属于 source-of-truth。如果 master 更改了 demand，会导致 `source_digest` 变化，从而在 `replay_cut` Step 1 触发全量 Quarantine。因此在同一 session 内绝对安全。
- **Fail-safe**: `except Exception: return False` 是一种防御性设计。如果 payload 损坏，返回 `False` 会让 propagator 跳过该 cut，防止 CP-SAT solver 崩溃，设计合理。

#### Fix 2: F4 separator_cells 漏验 (Sound 且完整)
- **File:Line**: `src/cuts/families/component_reach.py:121-131`
- **校验逻辑**: Validator step 7 确实遍历了 `cert.separator_cells`，并严格判断 `if sep_cell in free_cells: return ValidationResult("unsound", ...)`。
- **契约一致性**: 报错 detail 明确 cite 了 "spec 04_component_reach.md line 148"，与 Spec wording 完全一致。
- **Back-compat**: 使用了 `cert_dict.get("separator_cells", [])`，当旧版 cert 默认无此字段时返回空列表，不会 trigger check，兼容性良好。

---

### 任务 B: 找 Step F 引入新 bug 或漏修 (5 项 High-risk Hypotheses)

#### 1. [CRITICAL P0 性能] F1 `evaluate_geometric` Hot Path O(|Grid|) 灾难
- **File:Line**: `src/cuts/families/region_capacity.py:243-244`
- **机制**: `evaluate_geometric_region_capacity` 是 CP-SAT propagator 的 hot path，每次 state 变化触发 watcher 时都会被高频调用。当前实现每次调用都执行 `json.loads` 解析 payload，并调用 `_decode_region_bitset`。
- **死法**: `_decode_region_bitset` 内部包含一个 `for x in range(70): for y in range(70):` 的 **4900 次双重循环**。在 CP-SAT 搜索树中，propagator 每秒可能被调用上万次。每次调用执行 4900 次 Python 循环 + base64 解码 + JSON 解析，将导致 Solver 性能出现数量级坍塌（从毫秒级退化到分钟级）。
- **修复要求**: 必须在 `Cut` object 初始化或 attach 阶段缓存解码后的 `region_cells`，绝对禁止在 `evaluate` hot path 中做 O(|Grid|) 的反序列化。

#### 2. [High 漏修] 缺失 `by_exterior_watcher` 导致 Lifecycle 绕过与 Zombie Cuts
- **File:Line**: `src/cuts/store.py:59-75` & `src/cuts/replay.py`
- **机制**: Round 33 明确要求实现 `on_exterior_blocks_changed` 钩子和 `by_exterior_watcher`。Step F 完全无视了这一要求。
- **死法**: 当 master 回溯导致 `exterior_blocks` 改变时，由于没有 watcher，F1 cut 不会被立即 re-evaluate（导致 False Negative 漏剪）。更严重的是，它绕过了 `replay_cut` Step 3 的 `exterior_blocks_hash` 校验，本该被 Quarantine 的 cut 继续作为 Zombie 留在 active store 中。

#### 3. [High 升级] F4 `commodity_id` 强拒导致 Phase 1.5+ 100% 瘫痪
- **File:Line**: `src/cuts/families/component_reach.py:142-152`
- **机制**: 当前代码只要 `commodity_id` 存在就抛出 `schema_err`。但 `04_component_reach.md` §3 明确规定 `commodity_id` 是必填字段。
- **死法**: 一旦 Phase 1.5+ 的 Oracle 按照 Spec 规范输出了 `commodity_id`，Phase 1.1 的 Validator 会将 100% 的 F4 cuts 拦截进 Quarantine，导致整个 Component Reach 剪枝网络瞬间瘫痪。必须降级为 warning 或直接忽略，而不是 fail-closed。

#### 4. [Medium] F3 Multiset 校验允许“自相矛盾”的 Cut 语法
- **File:Line**: `src/cuts/lifecycle.py:610`
- **机制**: `evaluate_literal_multiset` 仅提取 `(group, pose)` 的 multiset。如果 attacker 构造 `[(crusher, slot=0, p1), (crusher, slot=0, p2)]`，这在逻辑上是绝对的 False（一个 slot 不可能同时装两个 pose）。
- **风险**: Evaluator 会提取 `{p1: 1, p2: 1}`，只要 state 中存在这两个 pose 就返回 True。虽然几何上 sound，但破坏了 Cut literal 的逻辑语义契约。

#### 5. [Low] F2 `cut_edges` 排序依赖 `list()` 转换的脆弱性
- **File:Line**: `src/cuts/families/cutset.py:137-148`
- **机制**: `sorted([list(e[0]), list(e[1])])` 强依赖 `Cell` 是 Tuple/List。
- **风险**: 如果未来 JSON schema 将 Cell 改为 `{"x": 1, "y": 2}`，`list(e[0])` 将提取字典的 keys `['x', 'y']`，导致所有 edge 变成 `[['x', 'y'], ['x', 'y']]`，发生静默哈希碰撞，校验逻辑完全失效。

---

### 任务 C: GPT pro round 2 + 此轮 Phase 1.1 production verdict

#### Phase 1.1 Step A-F 状态核对
- **P0 + High 是否全 close?** 否。F1 的 Unsoundness 虽修，但引入了 P0 性能灾难；Round 33 要求的 `by_exterior_watcher` 漏修。
- **必修 #6 (strict registration gate) & #7 (spec docs align)**: 依然未做。这是 Phase 1.2 P1.11 落地前必须清理的技术债。
- **F4 commodity_id**: 属于严重的 Schema Drift，不能 defer，必须在 Phase 1.1 解决，否则会阻断 Phase 1.5 的联调。

#### Verdict
**NOT GO, Step F 修不到位 / 新 P0 出现 — list file:line 必修**

**必须追加的 Fix (阻断项)**：
1. **P0 性能**: `src/cuts/families/region_capacity.py:243` 必须移除 hot path 中的 `json.loads` 和 `_decode_region_bitset`，改为在 attach 阶段缓存或使用极速的 bitset intersection。
2. **High 漏修**: `src/cuts/store.py` 必须补齐 `by_exterior_watcher`，并在 `replay.py` 中实现 `on_exterior_blocks_changed` 钩子。
3. **High 升级**: `src/cuts/families/component_reach.py:142` 移除对 `commodity_id` 的 `schema_err` 强拒，改为兼容 Spec 的读取或忽略。