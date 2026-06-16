## Round 4 Verdict
NOT_GO

## R3 fix verification (Finding #1/#2/#3)
- Finding #1 fix (any-pair segment scan): LANDED — `src/cuts/helpers/power_network.py:82`. 遍历所有 cell pair 且正确处理了 `ghost_aabb` 阻挡，退化 case (同 cell distance=0) 也能被 Liang-Barsky 正确处理。
- Finding #2 fix (validator trust via active_assumptions): REGRESSION — `src/cuts/families/power_grid_reach.py:382`. 引入了 `active_assumptions` 但 Validator 验证逻辑中直接 `del canonical_rules` 且未将 `cert_payload` 与 assumption 交叉校验，导致恶意 payload 依然可以绕过验证 (见 R4-Gap K / Finding 2)。
- Finding #3 fix (active_assumptions in CutScope + verifier dispatch): LANDED — `src/cuts/oracles/power_grid_reach_oracle.py:276` 成功注入，`verifiers.py` 成功分发。

## R4 NEW Gap K/L/M
- R4-Gap K (active_assumption ↔ cert payload 冗余): CONFIRMED. Validator 盲信 `cert_dict["pole_jump_radius"]`，而 `attach-scope` 只校验 Assumption 对象中的值。攻击者可在 payload 填 `0.001` 伪造断网，在 assumption 填 `R=5` 骗过 attach 检查。
- R4-Gap L (bounds-only when cell_owner empty): CONFIRMED. 当 `cell_owner` 为空时盲目返回 True，允许早期 Phase 注入伪造的 `protocol_core` 坐标，且由于 `evaluate_geometric` 的缺陷 (见 Finding 1)，该 Cut 会永久生效。
- R4-Gap M (verifier dict literal vs register_verifier API): REJECTED. `_VERIFIERS` 字典字面量用于模块内部的静态初始化是 Python 标准做法，`register_verifier` 的防覆盖机制是为外部模块 (Phase 1.1+ 动态注册) 设计的，此处直接初始化是安全的。

## Round 4 New findings (≥3, 任何 severity, R1+R2+R3 没 catch 的)

### Finding 1: [CRITICAL] src/cuts/families/power_grid_reach.py:441 — evaluate_geometric 漏校验 protocol_core 移动
`evaluate_geometric_power_grid_reach` 仅校验了 target facility 是否仍在 `selected_poses`，却**完全没有校验** `protocol_core` 是否仍在 `cert_dict["protocol_core_cell"]`。如果 Master 求解器将 `protocol_core` 移动到未被 ghost 阻挡的新位置，电力网络已恢复连通，但该 O(1) 评估器仍会返回 `True`，导致合法的 State 被永久误杀 (Soundness 破产)。

### Finding 2: [CRITICAL] src/cuts/families/power_grid_reach.py:382 — Validator 彻底丢失对 payload 关键标量的 source-of-truth 校验
R3 修复移除了 Validator 中对 `canonical_rules` 的直接校验 (`del canonical_rules`)，转而依赖 `active_assumptions`。但 Validator 在重建图时使用的是 `cert_dict["pole_jump_radius"]` 和 `cert_dict["protocol_core_cell"]`，且**从未**断言这些 payload 字段与 Assumption 的值一致。这使得 R4-Gap K 攻击路径完全成立，恶意 Prover 可用 `R=0.001` 轻易伪造断网。

### Finding 3: [HIGH] src/cuts/assumptions/verifiers.py:180 — verify_protocol_core_position 在 cell_owner 为空时盲目放行
当 `state.cell_owner` 为空时，函数直接 `return True`。这意味着在 Master 尚未放置任何设施的早期阶段，恶意 Prover 可以提交带有任意合法边界内坐标 (如 `(0,0)`) 的伪造 F8 Cut。结合 Finding 1，该 Cut 会被成功 Attach 并在后续真实 `protocol_core` 放置后持续毒化状态。

### Finding 4: [HIGH] src/cuts/families/power_grid_reach.py:126 — _parse_protocol_core_cell 边界检查存在数学漏洞允许负数坐标
检查逻辑为 `if not (0 <= x + _PROTOCOL_CORE_SIZE <= _GRID_SIZE):`。当 `x = -1` 且 size 为 9 时，`-1 + 9 = 8`，满足 `0 <= 8 <= 70`，导致负数坐标 (如 `[-1, -1]`) 被错误放行。虽然 `verifiers.py` 中有正确的 `< 0` 拦截，但由于 Finding 2 的存在，恶意 payload 仍可携带负数坐标进入 Validator 图构建逻辑。

## Sanity (GO verdict 必 ≥3 disproved hypothesis 含 file:line)
- **Hypothesis 1**: `_can_jump_via_cells` 的 any-pair 扫描可能过慢或允许穿透 ghost。
  **Disproved**: `src/cuts/helpers/power_network.py:82`。2x2 占地最多 16 个 pair，且严格调用了 `segment_intersects_aabb` (Liang-Barsky 算法)，任何与 ghost AABB 相交的线段都会被正确拦截，性能与正确性均有保障。
- **Hypothesis 2**: `_pole_pole_edges` 的 early reject cutoff `(pole_radius + 2.0 * math.sqrt(2.0)) ** 2` 太紧，可能误删合法边。
  **Disproved**: `src/cuts/helpers/power_network.py:116`。Anchor 到其 2x2 footprint 任意 cell 的最大距离为 $\sqrt{2}$。两 Pole 任意 cell 间的最小距离 $\ge \text{anchor\_dist} - 2\sqrt{2}$。若此值 $> R$，则 $\text{anchor\_dist} > R + 2\sqrt{2}$，数学上绝对安全。
- **Hypothesis 3**: `_validate_ghost_only_disconnect` 中的 `if not cover_ghost:` 是死代码会导致 False Positive。
  **Disproved**: `src/cuts/families/power_grid_reach.py:350`。`ghost_only_free` 是 `free_cells` 的超集，因此 `cover_ghost` 必为 `cover_set` 的超集。由于前置逻辑已保证 `cover_set` 非空，`cover_ghost` 绝对不可能为空。该死代码无害，不会影响 Soundness。

## 建议
**Round 5 必须修复**：
1. `evaluate_geometric` 必须增加对 `protocol_core` 当前位置的 O(1) 校验 (例如调用 `_protocol_core_footprint_owned`)。
2. Validator 必须在 `_validate_scalars` 中直接校验 `cert_dict` 的 `pole_jump_radius` 和 `protocol_core_cell` 是否与 `active_assumptions` 中的字符串值严格一致，或者恢复对 `canonical_rules` 的直接读取。
3. 修复 `_parse_protocol_core_cell` 的负数漏洞 (`x < 0 or y < 0`)。