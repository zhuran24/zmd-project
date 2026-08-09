这是一份基于 AUDIT 模式的深度代码审查报告。针对 Step G (commit 3553efb) 的修复，我进行了逐行交叉验证、性能推演以及与 Spec 的对齐检查。

结论前置：**NOT GO, Step G 修不到位**。虽然 `@lru_cache` 缓解了 4900 次循环的问题，但 Hot Path 中依然残留 `json.loads` 和全量 BFS，所谓的 "1.11ms" 性能声明是虚假的。此外，漏修的 `by_exterior_watcher` 并非单纯的性能问题，而是会导致漏剪的 **P0 级 Soundness Bug**。

以下是详细的 Audit 报告。

---

### 任务 A: 验 Step G 2 fix 是否 sound + 完整

**1. Fix 1 lru_cache (P0 性能修复评估): 修复不彻底，存在虚假宣传**
- **真加了 `@lru_cache` 吗？** 是的。`src/cuts/families/region_capacity.py:126` 确实添加了 `@lru_cache(maxsize=256)` 装饰器在 `_decode_region_bitset` 上。
- **Cache key 安全性？** Cache key 是 `b64` (base64 string) 和 `grid_size` (int)。这是 content-addressed 的，因为 base64 字符串直接映射到几何 bitset，内容不变则 key 不变，绝对不会出现 stale state（脏读）问题。
- **256 maxsize 够吗？** 对于 Phase 1.1 ramp 阶段，active cut 数量通常在 100 以内，256 的容量是充足的。
- **内存 leak risk？** `lru_cache` 持有 `frozenset` 引用。70x70 的 grid 最多 4900 个 cell，每个 cell 是 `Tuple[int, int]` (约 56 bytes)。一个满载的 frozenset 约 300KB。256 个 entry 上限内存占用约 75MB，在服务端可接受，无严重 leak 风险。
- **Thread-safe？** Python 3.13 的 `functools.lru_cache` 在 C 层面实现，受 GIL 保护，是 thread-safe 的。
- **【打假】1.11ms 性能声明是 Vague Hyperbole：** 声明称 "10K calls 1.11ms (avg 0.11µs/call)" 是**绝对不可能的**。因为在 `src/cuts/families/region_capacity.py:243` 的 `evaluate_geometric_region_capacity` 中，每次调用依然执行了 `cert_dict = json.loads(cut.geometric_payload)`。Python 的 `json.loads` 解析 1KB 左右的 JSON 字符串至少需要 2-5µs。10,000 次调用仅 JSON 解析就需要 20-50ms。该声明严重失实，掩盖了 Hot Path 中仍存在高昂开销的事实。

**2. Fix 2 F4 commodity_id (High 升级修复评估): Sound 且符合 Spec**
- **移除 schema_err？** 是的。`src/cuts/families/component_reach.py:142-152` 移除了强拒逻辑，改为返回 `ValidationResult(kind="ok")`，允许 `commodity_id` pass-through。
- **几何 Soundness 验真？** Soundness 确实不依赖 `commodity_id`。在 `component_reach.py:89-131` 中，Validator 严格重算了 `src_component` 和 `sink_component` 的 BFS 连通性，并校验了 `separator_cells` 必须在 `cell_owner ∪ ghost` 中。Attacker 伪造 `commodity_id` 无法绕过这些纯几何的拓扑校验。
- **攻击面与 Defer 风险：** 允许 fake `commodity_id` 确实可能在 Audit trail 中引入 misinfo。但由于 Phase 1.1 仅依赖几何约束（Geometric mode），不将 `commodity_id` 用于逻辑推理，因此不会导致误剪（False Positive）或漏剪（False Negative）。将其 defer 到 Phase 1.5+ 配合 `commodity_route` verifier 实施是合理的工程权衡。

---

### 任务 B: 找 Step G 引入新 bug 或剩余 finding 升 P0 (≥ 5)

Step G 的修复虽然解决了 4900 次循环的问题，但依然遗留和引入了致命的性能与正确性 Bug。以下是 5 个 High-risk hypotheses，其中前 3 个达到 P0 级别：

**1. [CRITICAL P0 性能] Hot Path 中的 `json.loads` 导致 Solver 数量级退化**
- **File:Line**: `src/cuts/families/region_capacity.py:243` 和 `src/cuts/families/component_reach.py:164`
- **机制与死法**: `evaluate_geometric` 是 CP-SAT propagator 的 Hot Path，每次 state 变化都会触发。当前代码在每次调用时都执行 `json.loads(cut.geometric_payload)`。
- **影响**: 假设有 100 个 active cuts，Solver 每秒探索 10,000 个 state，则每秒触发 1,000,000 次 `json.loads`。每次耗时 2µs，总耗时 2 秒/秒 —— 意味着 Solver 100% 的 CPU 时间都在做无意义的 JSON 反序列化，搜索速度将从 10K nodes/sec 暴跌至 <1K nodes/sec。必须在 Cut `attach` 阶段将解析后的 dict 缓存到内存中，绝对禁止在 Hot Path 解析 JSON。

**2. [CRITICAL P0 正确性] 漏修 `by_exterior_watcher` 导致 False Negative (漏剪)**
- **File:Line**: `src/cuts/store.py:66` (缺失 watcher) & `src/cuts/families/region_capacity.py:68` (依赖 exterior)
- **机制与死法**: Round 34 认为 `by_exterior_watcher` 只是 "efficiency P1"，这是**严重的误判**。在 F1 中，`cap_R = |R| - |ghost ∩ R| - |exterior ∩ R|`。如果 Master 搜索树回溯导致 `exterior_blocks` 增加，`cap_R` 会**减小**。
- **影响**: 一个原本合法的状态（`demand_R <= cap_R`），可能因为 `exterior_blocks` 增加而变成违规（`demand_R > cap_R`）。由于没有 `by_exterior_watcher`，Propagator 不会被唤醒，`evaluate_geometric` 不会被调用，这个 Cut 就被**静默漏掉**了（False Negative），导致 Solver 接受非法的 Master Plan。这是致命的 Soundness Bug。

**3. [CRITICAL P0 性能] F4 `_bfs_component` 在 Hot Path 中执行 O(|Grid|) 搜索**
- **File:Line**: `src/cuts/families/component_reach.py:170`
- **机制与死法**: `evaluate_geometric_component_reach` 在每次触发时，都会调用 `_bfs_component(src_cell, free_cells)`。
- **影响**: 这是一个纯 Python 实现的 BFS，最坏情况下需要遍历 4900 个 cell。在 Hot Path 中每秒执行上百万次 BFS，将直接导致 Solver 假死（耗时百秒级）。F4 的 evaluate 必须依赖增量连通性数据结构，或者将 BFS 降级为仅在 Validator 中执行，Hot Path 仅做 O(1) 的脏标记检查。

**4. [High 内存/安全] F4 `commodity_id` 无边界 Pass-through 导致 OOM 风险**
- **File:Line**: `src/cuts/families/component_reach.py:142`
- **机制与风险**: 移除了 `schema_err` 后，代码没有对 `commodity_id` 的长度或类型做任何限制。
- **影响**: 恶意 Oracle 或损坏的 Payload 可以注入一个 100MB 的超大字符串作为 `commodity_id`。由于 `json.loads` 和序列化过程会将其完整加载到内存，这会导致 Store 占用暴涨，甚至引发 Python 进程 OOM。必须添加 `len(commodity_id) <= 256` 的防御性校验。

**5. [Medium 稳定性] `lru_cache` 容易被恶意 Payload 触发 Thrashing (缓存抖动)**
- **File:Line**: `src/cuts/families/region_capacity.py:126`
- **机制与风险**: `maxsize=256`。如果 Oracle 存在抖动，生成了超过 256 个具有微小差异（例如无关紧要的 cell 发生翻转）的 `region_cells_bitset_b64`。
- **影响**: Cache 将被频繁 Evict（Thrashing）。一旦 Cache 击穿，系统将退化回每次调用执行 4900 次 Python 循环的灾难状态，导致不可预测的性能毛刺。

---

### 任务 C: Phase 1.1 production GO verdict

**Verdict: NOT GO, Step G 修不到位 — list 反例 / 漏修**

虽然 Step G 修复了 F1 的 4900 次循环和 F4 的 Spec 冲突，但由于对 CP-SAT Propagator Hot Path 的性能要求理解不足，以及对 `exterior_blocks` 依赖的数学本质存在误判，当前代码绝对无法进入 Phase 1.2 生产环境。

**阻断项 (Blockers) 必修列表：**

1. **P0 性能 (JSON in Hot Path)**:
   - `src/cuts/families/region_capacity.py:243` 和 `src/cuts/families/component_reach.py:164` 必须移除 `json.loads`。
   - **修法**: 在 `Cut` object 初始化或 `validate` 阶段，将解析后的 `cert_dict` 挂载到内存（例如 `cut._parsed_cert`），`evaluate_geometric` 只能读取内存对象，做到真正的 O(1)。
2. **P0 正确性 (Missing Exterior Watcher)**:
   - `src/cuts/store.py:66` 必须添加 `by_exterior_watcher`。
   - **修法**: 任何依赖 `exterior_blocks` 的 Cut (如 F1) 必须在 `add_cut` 时注册到该 watcher。Master 更改 exterior 时必须触发 re-evaluate，否则会导致严重的 False Negative。
3. **P0 性能 (BFS in Hot Path)**:
   - `src/cuts/families/component_reach.py:170` 必须移除全量 BFS。
   - **修法**: 引入增量连通性检查，或者在 Phase 1.1 阶段将 F4 的 `evaluate_geometric` 简化为仅检查 `separator_cells` 是否被 free_cells 重新覆盖（O(|separator_cells|)），而不是做 O(|Grid|) 的全量 BFS。
4. **必修技术债**:
   - Round 33/34 遗留的 `#6 strict registration gate default ON` 和 `#7 spec docs align` 必须在 Phase 1.2 P1.11 落地前彻底清理。