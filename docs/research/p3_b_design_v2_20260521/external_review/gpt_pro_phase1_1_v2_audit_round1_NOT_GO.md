# GPT pro Phase 1.1 v2 audit round 1 — verdict NOT GO

第一次 GPT pro v2 包 audit (`phase1_1_gpt_pro_review_v2.zip` commit 2165285).
对应 Step A-H 修复闭环 audit.

## Verdict

**NOT GO，Step A-H 修不到位。** 动态测试是绿的，找到 2 个新 P0 + 1 High + spec
drift 必修.

## P0-1: F1 Step F 真重算 evaluator 没接到 lifecycle

**File:line**: `src/cuts/lifecycle.py:723-735` (step_7_evaluate_cut)
**反例 reproduce**:
- 初始 state F1 cut: demand_R=138, cap_R=137 (validator emit)
- 移除 exterior_blocks: cap_R=139, demand 不变
- `evaluate_geometric_region_capacity` (family) 返 False ✓
- `step_7_evaluate_cut` (lifecycle) 返 True ✗ (硬编码 region_capacity 永真)

**机制**: Step F 修了 families/region_capacity.py 的 evaluator (真重算 cap_R),
但 lifecycle step_7 入口仍是 PoC 写死 `return True`. production framework 调
step_7 时绕过 family 真重算 → propagator 把已失效 F1 cut 当有效 cut → 假剪合
法 state.

**必修**: step_7_evaluate_cut 按 family dispatch 到对应 evaluate_geometric_*
或 evaluate_literal_multiset.

## P0-2: F3 blocking_slot 没绑定真实 blocking_pose_id

**File:line**: `src/cuts/families/port_exposure.py:105-116` + `:124-140`
**反例 reproduce** (真数据 `boundary_storage_port`):
- facility pose A `viewer::boundary_required_output_blue_iron_ore_020`
  port_cell=(0,13) port_direction=N front_cell=(0,12)
- blocker pose C `viewer::boundary_required_output_blue_iron_ore_019`
  occupied_cells=[(0,10),(0,11),(0,12)] — 实际占 (0,12)
- 伪造 blocker pose B `viewer::boundary_required_output_blue_iron_ore_021`
  occupied_cells=[(0,16),(0,17),(0,18)] — 不占 (0,12)
- state: `selected_poses=[C, A, B]`, `cell_owner[(0,12)]=("boundary_io",0)`
- cert: `blocking_facility=["boundary_io", 0, B]` (用 B 而非 C)
- validator → ok, evaluator → True

**机制**: validator 步 3 只检查 `cell_owner[front_cell] == (group, slot)` 通过.
后 multiset 用 cert 里的 `blocking_pose_id` (= B). 缺
`state.groups[group].selected_poses[slot] == blocking_pose_id` 校验.
attacker 让 cert 声称 blocker 是同 group 另一 pose, 系统学到错 cut `not(A and B)`
但真冲突是 `(A and C)`. 误剪合法状态 (A and B but not C).

**必修**: 在 cell_owner 检查后加 binding step:
```python
state.groups[blocking_group].selected_poses[blocking_slot] == blocking_pose_id
# 推荐还加: front_cell in occupied_cells(blocking_pose_id)
```

## High: F4 separator_cells 仍有 schema hole

**File:line**: `src/cuts/families/component_reach.py:154-168`
**反例**: cert.separator_cells = [[999, 999]] (out-of-grid), validator 返 ok.

**机制**: 原 Gemini r33 修法只验 `sep_cell in free_cells` 拒, 漏验:
- in-grid 边界
- 显式 ∈ cell_owner ∪ ghost (positive check)

不直接破 BFS soundness (cert.src_component 严等 BFS 仍约束), 但污染 audit trail
+ 未来 watcher invalidation 漏 watch.

**必修**: `0 <= x < 70 and 0 <= y < 70 and (sep_cell in cell_owner or in ghost)`.

## 静态质量 (verdict 1 跑了 + verdict 2 verify)

- pytest cuts 156 pass
- pytest -O 156 pass (1 warning re: -O 跳 assert)
- F1 真数据 smoke 0 cut (boundary_io 14/54 fail-closed 预期)
- ruff: 12 F401 tests unused (cosmetic)
- mypy --strict: 34 errors (vs 已知 29, strict typing hygiene)
- vulture: framework/evaluator/stub unused — **evaluator unused 跟 P0-1 同根**
- bandit: 6 Low B101 assert_used (lifecycle.py:436/634/789/800 + replay.py:191 + store.py:131)
- radon: 平均 A; 最高 validate_port_exposure C(16)

## 包完整性问题

`STEP_A_TO_H_CHANGELOG.md` 在解压后未找到 (v2 包内已改名 COMMIT_LOG.md
但 prompt 误用旧名). 不是 soundness P0 但影响 reviewer 复盘.

## Defer items (可接受)

- Phase 1.3 P1.21 hot path perf opt (json.loads cache / by_exterior_watcher /
  F4 incremental BFS) — 当前 step_7 单点 not hot
- F4 commodity_id pass-through — Step G 改 spec-aligned 合理, 但 Phase 1.5+
  commodity registry verifier 需

## 必修清单

1. P0-1: step_7_evaluate_cut family dispatch + regression test
2. P0-2: F3 blocking_slot → selected_poses[slot] → blocking_pose_id 绑定
3. High: F4 separator_cells in-grid + ∈ cell_owner ∪ ghost 显式
4. spec drift: PoseId int → str (state_machine_v2 / cut_lifecycle_v2) / family
   list 9 family (无 symmetry_lift) / F3 direction up/down → N/S/E/W /
   source_digest 真实施 (替 "poc_source_digest")
5. EXACT_FAMILY_VALIDATOR_STRICT default ON (Phase 1.2 P1.11 前)
