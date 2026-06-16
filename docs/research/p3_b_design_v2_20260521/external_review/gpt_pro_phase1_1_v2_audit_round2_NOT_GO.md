# GPT pro Phase 1.1 v2 audit round 2 — verdict NOT GO

第二次 GPT pro v2 包 audit (同 input pkg `phase1_1_gpt_pro_review_v2.zip`),
独立窗口跑. 跟 round 1 verdict 一致 NOT GO, 2 P0 + 1 High 重叠 + 新加 F2 evaluator
enclosure 漏验.

## Verdict

**NOT GO, Step A-H 修不到位.** 动态测试是绿的 (pytest 156 pass, -O 156 pass).
两个 production soundness blocker:
- F1 evaluate 修复没接入 lifecycle (round 1 P0-1 重叠)
- F3 cert 可以用同 group 假 blocker pose 替换 (round 1 P0-2 重叠)

## P0-1: F1 evaluate 修了但 production framework 没用它

### 证据

`src/cuts/families/region_capacity.py:335-371`:
```python
current_cap = compute_static_capacity(...)
return cert_dict["demand_R"] > current_cap
```
(family evaluator 真重算)

但 `src/cuts/lifecycle.py:732-734`:
```python
if cut.family == "region_capacity":
    return True  # v1.2 §6 简化 — cert in scope deterministically violates
```
(framework 入口仍 PoC 硬编码 True)

### 反例 reproduce

构造 F1 cut (region 2 cell + demand_R=2):
- 初始 state: 1 exterior block → cap=1, cut violate
- 后续 state: 移除 exterior block → cap=2, cut 应失效

```
F1 family eval init True
F1 family eval recovered False
F1 lifecycle step7 recovered True   ← P0 unsound
```

`store.py:99-105` 注释说 by_exterior_watcher defer sound 因 evaluator 重算 —
但调用方实际是 step_7_evaluate_cut (硬编码), 不调 family evaluator, 整套
defer rationale 跨.

### 必修

```python
if cut.family == "region_capacity":
    return evaluate_geometric_region_capacity(cut, state)
if cut.family == "cutset":
    return evaluate_geometric_cutset(cut, state)
if cut.family == "component_reach":
    return evaluate_geometric_component_reach(cut, state)
```
+ regression test: stale F1 cap 恢复后 step_7 必返 False.

## P0-2: F3 blocker pose 没和 front_cell owner 绑定

### 证据

`src/cuts/families/port_exposure.py:105-116`:
```python
owner = state.cell_owner.get(front_cell)
if owner != (blocking_group, blocking_slot):
    return unsound
```
(只验 front cell owner slot)

`src/cuts/families/port_exposure.py:124-140`:
```python
expected_pairs = Counter([
    (facility_group, facility_pose_id),
    (blocking_group, blocking_pose_id),
])
```
(multiset 用 cert.blocking_pose_id, 缺 `state.groups[blocking_group].selected_poses[blocking_slot] == blocking_pose_id` 链)

### 反例 reproduce

构造 state:
- `front_cell=(2,1)`, `cell_owner=("blk", 0)`
- `blk` group selected_poses[0]=p_actual (占 (2,1))
- 同 group p_fake 占 (9,9) (不挡 port)
- cert `blocking_facility=["blk", 0, "p_fake"]`
- cut literal `("blk", p_fake)`

```
F3 validator ok None
F3 literal_eval True
```

cert 证明的是 "slot 0 挡住 front_cell", literal 绑定到同组另一 pose. multiset
只在证明 "group 里某处存在 p_fake", 不是 "p_fake 正在挡 port".

### 必修

```python
selected = state.groups[blocking_group].selected_poses
if blocking_slot < 0 or blocking_slot >= len(selected):
    return unsound
if selected[blocking_slot] != blocking_pose_id:
    return unsound
# (推荐): front_cell ∈ occupied_cells(blocking_pose_id)
```

slot anonymity 论据 (state_machine_v2 §5) **只在最终 cut literal 层**成立 (slot
不进 multiset), validator 内部 binding 必用 slot resolve pose, 然后用 resolved
pose 绑 multiset.

## High 1: F2 evaluator hot path 没重验 enclosure

### 证据

`src/cuts/families/cutset.py:223-235`:
```python
free_cells = _free_cells(state)
current_edges = _cross_partition_edges(side_a, side_b, free_cells)
return cert_dict["commodity_demand"] > len(current_edges)
```

只重算 cross-partition edges, 漏 patch enclosure + partition ⊆ free check.

### 反例 reproduce

- 初始 state: patch 被 ghost 围住, validator ok
- 后续 state: 旁边 free cell 打开, validator unsound (`partition not enclosed`)
- 但 evaluator 仍 True

### 影响

`commodity_demand > cert_cut_size` 仍 satisfied (cur_edges 不变), evaluator 错
报 cut still violating → propagator emit 误剪.

### 必修

evaluator hot path 同步加 validator step 2/3 enclosure + partition⊆free 检查.

## High 2: F4 separator_cells out-of-grid 漏验

### 证据

`src/cuts/families/component_reach.py:154-168` 只验 `sep_cell in free_cells` 拒.
out-of-grid (e.g. `(999, 999)`) 既不在 free 也不在 cell_owner / ghost → silent pass.

### 反例 reproduce

`cert_dict["separator_cells"] = [[999, 999]]`, validator → ok.

### 影响

不破 BFS disconnect 证明 (src_component 严等 BFS 仍约束), 但:
- cert 语义污染
- audit trail 误导
- 未来 watcher 依赖 separator_cells 做 invalidation 漏 watch

### 必修

```python
if not (0 <= x < 70 and 0 <= y < 70):
    return unsound
if sep_cell not in state.cell_owner and sep_cell not in state.ghost_cells:
    return unsound
```

## F2 commodity_demand 没 source-of-truth

`src/cuts/families/cutset.py:202-211` 只验 `commodity_demand > cert_cut_size`,
BState 没 commodity demand registry, validator 不验 cert.demand 来自真实 routing.
外部 cert 写 `commodity_demand=999` 也通过.

只有在 F2 oracle stub (不 emit cut) 时 defer 才合理. F2 validator 注册到
replay 接受持久化 cut 时, max_flow_LP 或至少 demand source 必上. Phase 1.2 注意.

## F4 commodity_id pass-through 不只 metadata

`src/cuts/families/component_reach.py:170-184` allow commodity_id pass-through.
F4 几何 soundness 不依赖 commodity name (Step G 改 spec-aligned 合理), 但 cut
要剪 master 必须知道 src/sink 属于真实 commodity. 否则 fake commodity_id 让
apply-to-master 把几何 disconnect 套到错误 commodity. Phase 1.5+ 必 commodity
registry verify.

## ghost_rect tuple 语义 F8 风险

`src/cuts/lifecycle.py:216` 注释 `(x, y, h, w)`, 但 `src/cuts/helpers/ghost_geometry.py:108-116`:
```python
cell_aabb_from_rect((x, y, h, w)) → (x, y, x+h, y+w)
```

常规理解 w=x-dim width, h=y-dim height — 这里反过来用. 测试已 baked in 当前
行为, 但 F8 power_grid_reach 接真实 ghost_rect 时横竖会反. F8 前必须 lock spec.

## 静态质量

- ruff: 12 F401 (tests unused, cosmetic)
- mypy --strict: 34 errors / 10 file (Any return 在 region_capacity.py:371 / cutset.py:235 / canonical_rules.py:77,91 等)
- vulture: framework/stub unused 多 — **evaluate_geometric_* 被标 unused 跟 P0-1 同根信号**
- bandit: 6 Low B101 assert_used (生产入口建议改 explicit raise)
- radon: 最高 validate_port_exposure C(16) — F3 P0 正藏此

## Spec drift 具体 line

- PoseId: `lifecycle.py:48` = str, `state_machine_v2.md:44` = Tuple[str,int],
  `cut_lifecycle_v2.md:227` = int
- Family list: `lifecycle.py:56-66` 9 family (无 symmetry_lift), `cut_lifecycle_v2.md:232-241/365-374/740-747` 仍有 symmetry_lift, 缺 power_grid_reach/density_envelope
- F3 direction: `candidate_placements.py:53-60` N/S/E/W, `cut_family_specs/03_port_exposure.md:42` 仍 up/down/left/right
- source_digest: `region_capacity_oracle.py:183` 仍 "poc_source_digest", `lifecycle.py:636` 只接受此 placeholder
- F3 validator source: spec 写从 canonical_rules facility ports 校验, src 实际从
  candidate_placements pose ports — spec 该改 (src 更贴真数据)
- GroupState.remaining_count: src 是 property, spec 写 stored field

## 必修顺序 (verdict 2 推荐)

1. P0-1: lifecycle step_7_evaluate_cut family dispatch + stale F1 regression
2. P0-2: F3 blocking_slot → selected_poses[slot] → blocking_pose_id binding
3. High 1: F2 evaluator hot path enclosure 同步加
4. High 2: F4 separator_cells in-grid + 显式 ∈ cell_owner ∪ ghost
5. Phase 1.2 前 EXACT_FAMILY_VALIDATOR_STRICT default ON
6. spec drift: PoseId / family list / direction / F3 validator source / source_digest
7. F8 前 lock ghost_rect tuple 语义
