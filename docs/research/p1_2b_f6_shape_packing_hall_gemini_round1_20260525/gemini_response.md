## Round 1 Verdict
NOT_GO

## Verify Gap A/B
- **Gap A (spec §5b drift)**: CONFIRMED. Spec §5b (`remaining_count`) drifted from the v1.1 intent in §5a.bis (`group.demand`). The implementation (`shape_packing_hall_oracle.py:126` and `shape_packing_hall.py:237`) correctly followed the v1.1 intent to use the state-independent `group.demand` as the source-of-truth, and further correctly split it into `group_demand` and `region_demand` to handle per-region logic. The code is correct; the spec §5b needs a documentation update.
- **Gap B (region_demand default)**: CONFIRMED. Defaulting `region_demand` to `min(group.demand, region_cap)` (e.g., 23) is a severe OVER-TRIGGER (False Positive). If the total demand is 46, the master solver might intend to place 20 on the left baseline and 26 on the bottom. If the left baseline's `total_packable` is 22, the generator will emit a cut (`22 < 23`) and permanently prune this valid state, even though the master only needed 20 slots there. 
  *推荐*: Phase 1.2 generator 必须极其保守。在没有 master solution 提供精确 `region_demand` 的情况下，只有当 `total_packable == 0` (连 1 个都放不下) 且 `group_demand > 0` 时才发 cut，或者直接将 F6 禁用推迟到 Phase 1.5+。

## Round 1 New findings (≥3, 任何 severity)

### Finding 1: [CRITICAL] src/cuts/families/shape_packing_hall.py:263 — 验证器 Fail-open 导致伪造 pose_length 绕过 Soundness
`_validate_facility_template_match` 包含 `if facility_type is None or state.facility_templates is None: return None`。注释称为了兼容 Phase 1.2 fixture 缺失 wiring 而 defer check。这是致命的 soundness 漏洞：Adversary 可以提交一个伪造的 cert，声明 `pose_length = 35`，使得 `max_packable` 极小从而触发 cut，并故意在 state 中不提供 `facility_templates`。验证器会直接放行该伪造 cut。
*Fix*: 必须 fail-closed。如果缺失 source-of-truth，返回 `unsound` 或 `schema_err`。应去修复测试 fixture 补充 mock templates，而不是削弱验证器。

### Finding 2: [HIGH] src/cuts/families/shape_packing_hall.py:426 — evaluate_geometric 逻辑冗余且存在概念错误
v1.1 移除了 `cell_owner` 后，partition 仅依赖 `ghost_cells` 和 `exterior_blocks`。这两个变量被严格绑定在 cut scope 中 (`ghost_rect_id` 和 `exterior_blocks_hash`)。如果 cut 处于 active 状态（未被 Replay 拦截），说明这两个变量**绝对没有改变**。因此 `recomputed_lens` 永远等于 `cert_lens`，`evaluate_geometric` 永远会返回 `True`。当前代码在 hot-path 中执行 O(N) 的无意义网格扫描。
*Fix*: 既然 v1.1 的 partition 在 scope 内是 100% static 的，`evaluate_geometric` 在校验完 schema 后应直接 `return True`。

### Finding 3: [MEDIUM] src/cuts/families/shape_packing_hall.py:461 — Watcher region_id 字符串格式与 Spec 不符
代码中注册 watcher 的 key 为 `region_id = f"shape_packing_hall:{region_kind}"`。但 Spec §8 明确规定格式为 `region_id = f"{cert.region_kind}:shape_hall"`。这种硬编码字符串的不匹配将导致 cut 被挂载到错误的 watcher 树上，当 region 发生 invalidation 时，该 cut 永远不会被唤醒。
*Fix*: 修改为 `region_id = f"{region_kind}:shape_hall"` 以对齐 Spec 和 cut store 预期。

### Finding 4: [MEDIUM] src/cuts/helpers/baseline_partition.py:28 — (0,0) 角落重叠导致全局 False Negative
`left_baseline` (列 y=0) 和 `bottom_baseline` (行 x=0) 都包含了原点 `(0, 0)`。Generator 分别独立计算两个 region 的 capacity。如果 `group_demand = 46`，左侧算出 capacity 23，底部算出 capacity 23，Generator 会认为 23+23=46 满足需求，不发 cut。但实际上 `(0,0)` 不能被同时占用，全局真实 capacity 只有 45。这是一个数学上的 False Negative。
*Fix*: 在 Phase 1.5+ 引入 Multi-region Hall 时，必须将两个 baseline 作为一个联合区间处理，并在交点处应用互斥约束。

## Sanity (如果 GO, 至少 3 disproved hypothesis 含 file:line)
*(Verdict 为 NOT_GO，但仍提供已证伪的高风险假设)*
1. **Hypothesis**: `partition_offsets` 的重叠校验逻辑存在越界或乱序漏洞。
   **Disproved**: `src/cuts/families/shape_packing_hall.py:190` 严格维护了 `prev_end = off + L - 1`，并校验 `off <= prev_end`。无论是 offset 乱序（如 `[10, 0]`）还是真实重叠，都会被正确拦截并返回 `schema_err`。
2. **Hypothesis**: `pose_shape_canonical` 的正则解析允许 `0x3_rigid` 这种退化维度。
   **Disproved**: `src/cuts/families/shape_packing_hall.py:129` 显式拆分了字符串并执行了 `min(a, b) != 1` 和 `max(a, b) != pose_length` 的强校验，`0x3` 会在 min 校验中失败。
3. **Hypothesis**: 如果 `state.instance_to_facility_type` 为空，Generator 会崩溃。
   **Disproved**: `src/cuts/oracles/shape_packing_hall_oracle.py:137` 的 `_auto_detect_boundary_groups` 安全地处理了 None 的情况并返回 `[]`，导致生成 0 个 cut，符合 fail-closed 语义。

## 建议 Round 2 重点 / Phase 1.5+ defer
1. **Round 2 重点**: 修复 Validator 的 fail-open 漏洞 (Finding 1)；修正 Watcher key 字符串 (Finding 3)；将 `evaluate_geometric` 优化为 O(1) 静态返回 (Finding 2)。
2. **Phase 1.5+ Defer**: 彻底废弃当前的 `region_demand` 默认 fallback 逻辑 (Gap B)，在 Master 真正提供 per-region placement count 之前，F6 不应在生产环境激活；解决 `(0,0)` baseline 交叉点的联合容量计算问题 (Finding 4)。