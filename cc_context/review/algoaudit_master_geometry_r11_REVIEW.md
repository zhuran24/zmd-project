# 终末地 IndustrialPlanner 几何 master round 11 审查报告

## 0. 快照校验与范围

- 审查对象只使用 `/mnt/data/zmd_snapshot_5e5e0c86.zip`。
- sha256 校验结果：`5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`，与任务指定值一致。
- 解包根：`project/`。
- 本轮只审几何 master soundness：`src/models/exact_coordinate_master.py`、`src/models/pose_bool_exact_master.py`、`src/models/master_model.py`。
- 结论：**本轮不是零 finding**。主线 coordinate exact master 在 Q1/Q2/Q3 指定点未发现新的 soundness 缝；但 env-gated 的 `PoseBoolExactMasterDelegate` 仍在本面文件和直接 `MasterPlacementModel` 后端范围内，存在 2 个 soundness finding。

## 1. Findings

### F-GM-R11-PB-REQ-POLE-01 — HIGH — pose-bool 后端忽略 fixed required `power_pole` 需求，导致 false-FEASIBLE

**文件/位置**

- 原始快照：`src/models/pose_bool_exact_master.py:370-419`。
- 关键旧逻辑：`ro_counts` 遍历 required optional 时，`tpl == "power_pole"` 直接 `continue`；随后 `power_pole` 只建 residual optional 池，注释为 “no demand fix”。

**问题**

`exact_required_pose_optional_counts={"power_pole": 1}` 表示有 fixed required 电杆。coordinate exact 后端已把 fixed pole 物化成 required optional slot，并纳入 pole body / family / coverage 语义；但 pose-bool 后端把 fixed pole 需求跳过，只留下“可选 residual pole 池”。如果所有 pole pose 被 ghost body 排除，旧模型没有任何约束要求放杆，仍可返回 `OPTIMAL`，这是把真 INFEASIBLE 判成 FEASIBLE。

最小反例：1×1 grid，唯一 `power_pole` pose 在 `(0,0)`，ghost 固定为 `(0,0)` 的 1×1，且 required pole count = 1。规则上 required pole body 必须存在并与 ghost body no-overlap，故不可行；旧 pose-bool 模型中 pole var 被 ghost 过滤后为空，且 required count 被跳过，模型可行。

**复现 probe**

补丁前手动 probe 结果：

```text
EXACT_USE_POSE_BOOL_MASTER=1
1x1 grid, one required power_pole at (0,0), ghost_rect=(1,1), ghost_anchor_filter={(0,0)}
old status: CpSolverStatus.OPTIMAL
old solution: {}
```

补丁后的 regression：

```text
src/tests/test_master_cut_solution_invalidation.py::test_pose_bool_exact_required_power_pole_is_enforced_against_ghost
```

该测试断言同一反例为 `cp_model.INFEASIBLE`。

**修法**

在 pose-bool build 中累计 `required_power_pole_demand`；在 feasible `pole_vars` 生成后，把 fixed pole 需求施加到共享 pole pool：

- 如果 feasible pole vars 数量小于 fixed demand，添加 fail-closed infeasible 约束；
- 否则添加 `sum(pole_vars) >= required_power_pole_demand`；
- 同时将 `required_optional_slots["power_pole"]` 填入占位，保持统计/slot 语义可见。

这里使用 `>=` 而非 `==` 是因为 residual power poles 仍可作为 coverage witness 额外出现；fixed required 语义需要“至少这些 required pole 存在”，不应禁止 residual pole。

---

### F-GM-R11-PB-STALE-01 — HIGH — pose-bool cut 后未清 `_solver/_status`，`extract_solution()` 可复活刚被 cut 禁掉的旧 witness

**文件/位置**

- 原始快照：`src/models/pose_bool_exact_master.py:762-820`、`831-852`、`919-968`、`1167-1171`、`1217-1227`。
- 对照：coordinate exact 的 `src/models/exact_coordinate_master.py:7028-7080` 已在 cut 成功后同步清理 `_last_solution/_solver/_status`；legacy 路径 `src/models/master_model.py:11904-11948` 也已同步清理。

**问题**

pose-bool 后端的多条模型增量 cut 路径只清 `owner._last_solution`，保留旧 `owner._solver` 和 `owner._status`。而 `MasterPlacementModel.extract_solution()` 只要 `_solver` 非空且 `_status` 是 FEASIBLE/OPTIMAL，就会委托 delegate 从旧 solver assignment 重建解。于是 cut 成功之后、不重新 solve 之前，`extract_solution()` 会把刚刚被 cut 禁止的旧布局重新交出去。

这与 r6 类 stale witness 完全同形，只是残留在 pose-bool delegate 中。即使 pose-bool 后端是 env-gated，它仍是本面文件中可直接启用的 master 后端，因此属于 geometry master witness soundness。

**复现 probe**

补丁前手动 probe 结果：

```text
EXACT_USE_POSE_BOOL_MASTER=1
solve one mandatory solid with two poses -> selected pose_idx = 1
add_benders_cut({"solid_1": 1}) -> True
old owner._solver: <CpSolver object>
old owner._status: CpSolverStatus.OPTIMAL
old extract_solution(): returns solid_1 at pose_idx 1 again
```

补丁后的 regression：

```text
src/tests/test_master_cut_solution_invalidation.py::test_pose_bool_benders_cut_invalidates_solver_before_extract
```

该测试断言 `add_benders_cut()` 后 `_solver is None`、`_status is None`、`extract_solution() == {}`，重新 solve 后选择的 pose 不再是被 cut 禁止的 pose。

**修法**

新增 `PoseBoolExactMasterDelegate._invalidate_owner_solver_witness()`，统一清理：

```python
self.owner._last_solution = None
self.owner._solver = None
self.owner._status = None
```

并在所有 pose-bool 本地模型增量 cut 成功后调用，包括：

- `add_patch_routing_core_cut()`；
- `add_separator_capacity_cut()`；
- `add_benders_cut()`；
- `add_routing_port_lazy_demand_cut()`；
- `add_routing_port_blocking_cell_cut()`。

## 2. Q1 几何约束编码忠实度判读

### 2.1 footprint / bbox / mode-channel

`exact_coordinate_master.py:966-1008` 从 `occupied_cells` 减去 anchor 得到相对 body cells，并把完整 footprint key 纳入 mode token：`(orientation, port_mode, footprint_key)`。这意味着 orientation/port_mode 相同但实际 body footprint 不同的候选不会被混到同一 mode。

`exact_coordinate_master.py:1557-1620` 对每个 mode 反查 pose tuple 并收集 footprint bounds；如果同一 mode 的 footprint bounds 不唯一，则抛 `ValueError` fail-closed。非矩形或非连续 anchor 域通过 `use_domain_table=True` 走 `AddAllowedAssignments`，不会把“坐标矩形域中的空洞”误当成合法 pose。

`exact_coordinate_master.py:2357-2480` 用 footprint bbox 生成 interval：`start = x + min_dx/min_dy`，`end = start + width/height`。这对非矩形 body 是 bbox over-approximation，会比精确 body 更保守，方向是防 false-FEASIBLE；没有发现 under-approximate 漏挡。

### 2.2 ghost 矩形

`exact_coordinate_master.py:3632-3736` 的 ghost anchor 枚举为：

```python
for anchor_x in range(self.grid_w - ghost_w + 1):
    for anchor_y in range(self.grid_h - ghost_h + 1):
```

因此贴边 anchor 合法，越界 anchor 不进入域。ghost 大于 grid 或 filter 排空时添加 infeasible 约束，属于 fail-closed。

`AddNoOverlap2D` 在 `exact_coordinate_master.py:3729-3732` 中只接收 `self._core_x/_y_intervals` 和 ghost intervals。`_core_*_intervals` 的来源是 mandatory / required optional / residual optional / power pole 的 body footprint intervals；未纳入 connector、belt、coverage cells。检索 ghost 相关路径没有发现 exterior-path / connectivity 类约束。ghost “空”的口径与 owner 已定的 **body-only** 一致。

### 2.3 半开坐标 off-by-one

facility interval 与 ghost interval 都使用半开端点：facility `end = start + width/height`，ghost `end = anchor + ghost_w/ghost_h`。anchor 枚举到 `grid - size`，因此最右/最上贴边合法，`grid - size + 1` 以外非法。未发现 off-by-one。

### 2.4 `max_lex(area, min_side)` 目标

在三份 master 文件中没有发现主 CP-SAT model 的 `self.model.Maximize()` / `self.model.Minimize()`。两处 `local_model.Maximize()` 位于局部容量/筛选计算，不是 master objective。master 仍是固定 `(w,h)` feasibility；frontier tuple 比较在外层完成。`min_side >= 6` 未被编码成 CP-SAT tie-break 目标。

## 3. Q2 optional / residual 基数不等式族判读矩阵

| 约束族 | 规则依据 / 代码位置 | 判读 |
|---|---|---|
| protocol storage lower | `exact_coordinate_master.py:6180-6215` | 使用 `protocol_shortfall = lower - fixed_required_count`，仅在 shortfall > 0 时要求 residual active 数量补足；fixed ≥ lower 时不再强迫 residual。修复了 r2/r3 型混合 fixed/residual false-INFEASIBLE 缝。 |
| protocol residual upper | `exact_coordinate_master.py:1642-1652` | residual upper = certified total upper - fixed required count，避免 fixed 与 residual 双花 upper。 |
| `0 < fixed < lower` residual 保留 | `exact_coordinate_master.py:1654-1664` | protocol storage 在 fixed 不足 lower 时仍创建 residual slots，shortfall 有 literal 可补。 |
| fixed required power pole，coordinate 后端 | `exact_coordinate_master.py:3090-3122`、`3285-3403` | required pole slots 被纳入 `_all_power_pole_slots()`、family literals/count vars 和 capacity witness；family map 为空时返回而不是 `0==1` 判死；无 powered demand / 无 family count vars 时 capacity VI 返回，不误杀纯几何 fixed pole。 |
| fixed required power pole，pose-bool 后端 | 原始 `pose_bool_exact_master.py:370-419` | **Finding F-GM-R11-PB-REQ-POLE-01**。fixed pole demand 被跳过，已补 `sum(pole_vars) >= demand` / 不足 fail-closed。 |
| mandatory exactly-one / slot 装配 | coordinate: `exact_coordinate_master.py:2615-2694`，pose-bool mandatory: `pose_bool_exact_master.py:338-368` | coordinate 用 slot x/y/mode 加 allowed tuples 限域；pose-bool 用 feasible pose vars 且 `sum == demand`。未发现多收非法 tuple。 |
| optional family capacity lower | `exact_coordinate_master.py:6266-6322` | 对每个 powered template，聚合 family count vars 的正系数并要求总 capacity ≥ demand；若确有 demand 但无正项则 infeasible。该不等式是 coverage 必要条件，不是启发式收紧。 |
| power pole residual upper | `exact_coordinate_master.py:2054`、`6216-6265` | residual pole 数量 upper 由 mandatory powered non-pole、required optional powered、residual powered active 之和给出；它是“最多需要这么多 coverers”的存在性压缩，不要求更多 pole。默认路径 sound。env override `EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE` 在 certified session 另有 blocker，不作为默认 soundness finding。 |
| pool=0 / `upper < fixed` | coordinate: `exact_coordinate_master.py:1642-1664`、`6180-6215`；pose-bool fixed pole patch: `pose_bool_exact_master.py:430-436` | 当规则需求/shortfall 为正且无可行 literal 时 fail-closed；需求为 0 时不额外添加 infeasible。 |

## 4. Q3 对称破缺、solve 派生字段、hint 判读

### 4.1 对称破缺保代表性

`exact_coordinate_master.py:2553-2577` 的 `_signature_order_is_compatible_with_slot_order()` 按 slot 实际域中的 pose tuples 反查 `(order_key, signature, pose_idx)`，并仅当 signature 在 order_key 排序下非降时返回 true。`exact_coordinate_master.py:2579-2613` 在所有 slot 兼容后才添加 signature 单调约束；否则记录 skipped stats 并不加约束。量化范围来自 slot 的 `allowed_tuples` / tuple map，等于 slot 实际域，未复现 r8 双标尺删空等价类。

power pole residual 对称破缺 `exact_coordinate_master.py:3380-3390` 是 active 前缀 + family 非降 + 同 family 时 order_key 非降。这里约束的是可交换 residual pole slots 的 canonical representative；required fixed pole slots不参与 residual 排序，未发现删除可行等价类。

### 4.2 cut 后 witness 清理

coordinate exact：`exact_coordinate_master.py:7028-7080` 已在 cut 成功后清 `_last_solution/_solver/_status`。legacy：`master_model.py:11904-11948` 同样清理。

pose-bool 原始代码只清 `_last_solution`，保留 `_solver/_status`，触发 **F-GM-R11-PB-STALE-01**。补丁后通过统一 helper 修复所有 pose-bool 本地模型增量 cut。

### 4.3 hint 永不约束

coordinate hint：`exact_coordinate_master.py:6785-6874` 使用 strict int parser，非 int / 越界 pose / 缺失 ghost anchor index 均 skip；只调用 `AddHint()`。pose-bool hint：`pose_bool_exact_master.py:970-1003` 同样只对存在的 BoolVar 调 `AddHint()`。`src/tests/test_solution_hint_malformed_defense.py` 覆盖 malformed hint 防御。未发现 hint 进入可行域。

## 5. 补丁内容

补丁文件：`geometry_master_r11.patch`。

变更摘要：

1. `src/models/pose_bool_exact_master.py`
   - 新增 `_invalidate_owner_solver_witness()`。
   - fixed required `power_pole` 需求在 feasible pole pool 上强制：`sum(pole_vars) >= required_power_pole_demand`，不足则 infeasible。
   - 所有 pose-bool 本地模型增量 cut 成功后统一清 `_last_solution/_solver/_status`。
2. `src/tests/test_master_cut_solution_invalidation.py`
   - 新增 `test_pose_bool_benders_cut_invalidates_solver_before_extract()`。
   - 新增 `test_pose_bool_exact_required_power_pole_is_enforced_against_ghost()`。

补丁已在原始解包副本上执行：

```text
cd /mnt/data/zmd_r11_review/orig && git apply --check ../geometry_master_r11.patch
PATCH_OK
```

## 6. 测试记录

已运行并通过：

```text
python -m pytest -q -p no:randomly src/tests/test_master_cut_solution_invalidation.py
4 passed in 2.45s

python -m pytest -q -p no:randomly src/tests/test_exact_coordinate_protocol_bounds.py src/tests/test_solution_hint_malformed_defense.py
28 passed in 2.63s

python -m pytest -q -p no:randomly \
  src/tests/test_master_cut_solution_invalidation.py \
  src/tests/test_exact_coordinate_protocol_bounds.py \
  src/tests/test_solution_hint_malformed_defense.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py::test_pose_bool_replay_alias_collision_fails_closed \
  src/tests/test_ghost_anchor_filter.py::test_certified_exact_blocks_pose_bool_master_env_before_session \
  src/tests/test_master.py::test_ghost_signature_bucket_mandatory_region_counting_falls_back_for_unsupported_footprints
35 passed in 2.62s

python -m pytest -q -p no:randomly src/tests/test_master.py
227 passed in 17.09s

python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored
```

补丁后手动 probes：

```text
fixed required pole blocked by ghost -> CpSolverStatus.INFEASIBLE
pose-bool benders cut -> solver None, status None, extract_solution() == {}
```

未完成：

```text
python -m pytest -q -p no:randomly src/tests
```

该全量命令在沙盒 300s 限时内未跑完，输出到约 6% 进度时超时，期间未见失败汇总。另有一次 `src/tests/test_master.py` 初跑出现 `test_ghost_signature_bucket_mandatory_region_counting_falls_back_for_unsupported_footprints` 的 instrumentation top-entry 断言失败；该测试随后单测通过，整份 `test_master.py` 复跑通过，判断为测试顺序/计时 instrumentation 选择的非稳定现象，不归因于本补丁。
