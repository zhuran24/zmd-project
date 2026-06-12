# 终末地 IndustrialPlanner 几何 master round 6 审查报告

审查对象: `zmd_snapshot_3f4ceebb.zip`

sha256 校验: `3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9`, 与任务给定值一致。只解包并审查该快照；其它快照未使用。

结论: 本轮非零 soundness finding。发现 1 个 master 侧 cut apply 后旧 solver 回读窗口，已给出补丁与回归。R5-A 空 family 修复确认通过；除该 stale-solver 问题外，Q2 解回读链与 Q3 cut apply 的 literal 解析、条件极性、计数语义未发现新的 soundness 问题。

## Finding 1: cut 成功加入后仅清 `_last_solution`，旧 `_solver/_status` 仍可被 `extract_solution()` 重新回读

Severity: High, soundness

位置:

- 原始快照 `src/models/exact_coordinate_master.py:6928`: exact-coordinate `add_benders_cut()` 成功加 cut 后只执行 `self.owner._last_solution = None`。
- 原始快照 `src/models/master_model.py:11938`: legacy `add_benders_cut()` 成功加 cut 后也只执行 `self._last_solution = None`。
- `src/models/master_model.py:11826-11836`: `extract_solution()` 的入口只检查 `_solver is not None` 且 `_status in {OPTIMAL, FEASIBLE}`；当 `_last_solution` 被清空但旧 `_solver/_status` 还在时，会用旧 CpSolver assignment 重新构造 solution。

复现 probe:

1. 构造一个 2x1 网格、一个 mandatory 1x1 设施、两个合法 pose 的 exact master。
2. `solve()` 得到 pose 0，`extract_solution()` 缓存并返回 pose 0。
3. `add_benders_cut({"solid_1": 0})` 成功加入单 pose nogood，语义上 pose 0 已被当前模型禁止。
4. 在未重新 `solve()` 前调用 `extract_solution()`。
5. 原始快照会返回同一个 pose 0；这不是缓存命中，而是 `_last_solution` 清空后从旧 `_solver` 重新读出的 stale 解。

影响论证:

这个窗口会让“刚被 cut 禁止的布局”在未重新求解前被作为当前模型的 placement_solution 交给 binding/routing/campaign。LBBD 主循环通常在 cut 后进入下一轮 solve，但 master 公共 API 本身没有 fail-closed；审查范围要求检查 master 解回读保真与 cut apply 通道，因此这是 soundness 级别问题。`extract_bound_state()` 也同理会在 cut 后继续从旧 solver 读 bound state，语义不再对应当前模型版本。

修法:

成功加入实际 cut 后，同时清空旧 solver witness 与 status，使 cut 后、重 solve 前的 `extract_solution()` 返回 `{}`，`extract_bound_state()` 返回无 incumbent bound，而不是读旧解。

修复位置:

- `src/models/exact_coordinate_master.py:6928-6935`: exact-coordinate cut 成功后新增 `self.owner._solver = None` 和 `self.owner._status = None`。
- `src/models/master_model.py:11938-11943`: legacy cut 成功后新增 `self._solver = None` 和 `self._status = None`。

回归:

- 新增 `src/tests/test_master_cut_solution_invalidation.py:60-72`，覆盖 exact-coordinate: cut 当前 pose 后，未重 solve 的 `extract_solution()` 必须为 `{}`，`extract_bound_state()["ub"]` 必须为 `None`；重 solve 后 pose 必须改变。
- 新增 `src/tests/test_master_cut_solution_invalidation.py:75-87`，覆盖 legacy 同一语义。

完整补丁: `r6_master_cut_solution_invalidation.patch`。

## Q1: F-GM-Q3-01-R5-A 修复确认

判定: 未发现 R5-A 回归。

1. 空 family 映射的成因与语义等价性

`_prepare_power_pole_families()` 每次先重置 family 映射和相关表，随后只有两条显式早退路径会让 `_power_pole_family_name_by_int` 保持为空: `skip_power_coverage` 为真，或 `_exact_powered_template_demands()` 为空，见 `src/models/exact_coordinate_master.py:2040-2074`。若存在 powered demand 且有 `power_pole` candidates，代码会遍历所有 pole pose 并按每个 powered template 的容量系数组 family，即使所有系数都是 0 也会创建 family，见 `src/models/exact_coordinate_master.py:2131-2147`。因此“family 映射为空”与“不需要或不能建立 capacity-family 语义通道”一致；未找到“有 powered demand 且有 pole pool，但映射意外为空”的构造。

如果 powered demand 存在但 pole pool 为空，family 也为空，但此时 required fixed power pole 无可用几何候选，slot 域为空会通过 `_create_base_slot_geometry()` 加 `Add(0 == 1)` fail-closed，见 `src/models/exact_coordinate_master.py:2509-2547`。这不是 fixed pole 逃出 family 计数，而是无候选放置的不可满足模型。

2. 空映射路径 fixed pole 几何约束是否保留

fixed required power pole 作为 required optional slot 在 `_prepare_slot_specs()` 中正常创建，保留 `tuple_to_pose_idx`、`allowed_tuples` 与 mode/domain 信息，见 `src/models/exact_coordinate_master.py:2271-2293`。slot 变量由 `_create_required_optional_slot_vars()` 建立，plain path 会调用 `_create_base_slot_geometry()`，后者创建 `x/y/mode/order_key`、footprint interval、必要的 domain table，见 `src/models/exact_coordinate_master.py:2755-2767` 与 `src/models/exact_coordinate_master.py:2509-2587`。R5-A 的空映射早退仅跳过 family channel，见 `src/models/exact_coordinate_master.py:2984-2995`，不跳过 required slot 的 no-overlap、在界、domain table、ghost no-overlap 等几何约束。

`_all_power_pole_slots()` 明确包含 required optional 和 residual optional 的 `power_pole` slots，见 `src/models/exact_coordinate_master.py:2978-2982`。build 顺序是 required optional slot 先建，再 attach required pole family，再 residual pole，随后 core no-overlap、ghost no-overlap 和 power coverage，见 `src/models/exact_coordinate_master.py:3316-3330`。power coverage 读取 `_all_power_pole_slots()`，见 `src/models/exact_coordinate_master.py:5684-5707`，所以 fixed pole 在非 skip coverage 场景仍会被 witness/coverage 通道读取。

补充 probe: `probe_skip_power_keeps_geometry` 构造 `skip_power_coverage=True` 且仍有 powered mandatory demand 与 fixed required pole 的模型，断言 family map 为空、模型可行、`_all_power_pole_slots()` 长度为 1、`extract_solution()` 回读出唯一 `power_pole` placement。结果: OK。

3. 非空映射但 tuple 表空的 fail-closed 路径

当 family 映射非空时，`_attach_required_power_pole_family_channels()` 会创建 `slot.family` 并要求 `[x, y, mode, family]` 在 tuple table 中；如果 tuple table 为空，仍执行 `self.model.Add(0 == 1)`，见 `src/models/exact_coordinate_master.py:2996-3016`。补充 probe `probe_nonempty_family_empty_required_tuple_rows_fails_closed` 通过 monkeypatch 将 required tuple rows 置空，模型状态为 INFEASIBLE。结果: OK。

## Q2: 解回读保真链审查

判定: 已修复 cut 后 stale solver 回读问题；其它环节未发现新的 soundness 问题。

1. `(x, y, mode) -> pose_idx -> facility_pools[tpl][pose_idx]` 反查

mode token 包含 orientation、port_mode、footprint key；footprint key 基于相对 occupied cells 与 footprint bounds，见 `src/models/exact_coordinate_master.py:989-1004`。`_prepare_template_domains()` 对每个 template 建立 `tuple_to_pose_idx`，若同一 `(x, y, mode)` 对应多个 pose，会直接 `raise ValueError("Duplicate coordinate pose key ...")`，见 `src/models/exact_coordinate_master.py:1668-1691`。因此 mandatory、fixed required optional、residual active optional 共用的 `_slot_pose_idx()` 反查是单值的，未知 tuple 会抛 KeyError 而不是静默读错，见 `src/models/exact_coordinate_master.py:6585-6594`。

mode 的矩形域若不是完整 cartesian cells，`_build_mode_rect_domains_from_pose_indices()` 会启用 domain table，见 `src/models/exact_coordinate_master.py:1553-1616`；`_create_base_slot_geometry()` 会对 `[x, y, mode]` 加 allowed assignments，optional 情况下由 `active` enforce，见 `src/models/exact_coordinate_master.py:2570-2587`。这避免了 solver 选择 rectangle hull 中不存在的 pose tuple。

2. 未激活 residual slot 回读

exact delegate 的 `extract_solution()` 对 residual optional 只在 `slot.active is not None and solver.Value(slot.active) == 1` 时读取 `_slot_pose_idx()`，见 `src/models/exact_coordinate_master.py:6632-6637`。未激活 slot 的 `x/y/mode` 即使被 CP-SAT 任意赋域内值，也不会进入 solution dict。

3. ghost 矩形回读一致性

ghost 建模对每个 anchor 创建一个 BoolVar 和对应 optional interval，并在存在候选时 `AddExactlyOne(list(u_vars.values()))`，随后与 core intervals 做 `AddNoOverlap2D`，见 `src/models/exact_coordinate_master.py:3557-3605`。master 回读 `_extract_selected_ghost_pick()` 只返回 solver.Value(var)==1 的唯一 anchor，并从 `_ghost_domains[rect_idx]["anchor"]` 或 cells 派生 anchor，见 `src/models/master_model.py:11785-11823`。因此 `ghost_pick.pose_idx` 是 ghost rect index，anchor 与所选 `u_var` 同源；downstream/campaign 对 ghost marker 也有专门分支，不把它当设施占用，见 `src/search/benders_loop.py:4878-4885`、`src/search/benders_loop.py:6027-6051`、`src/search/benders_loop.py:6103-6113`、`src/search/exact_campaign.py:295-296` 与 `src/search/exact_campaign.py:825-831`。

4. `_last_solution` 与 solver witness 失效时机

`solve()` 每次求解后会写入新的 `_solver/_status` 并清 `_last_solution`，见 `src/models/master_model.py:11514-11518`。`from_exact_core()` overlay 会清 `_solver/_status/_last_solution` 并标记未 built，见 `src/models/master_model.py:2715-2719`。本轮 finding 修复了 cut apply 成功后的缺口: exact 与 legacy cut 成功后现在同时清 `_last_solution/_solver/_status`，见 `src/models/exact_coordinate_master.py:6928-6935` 与 `src/models/master_model.py:11938-11943`。

solution hint 不改变可行域，只在 `solve()` 内先清旧 hints 再应用新 hints，见 `src/models/master_model.py:11285-11320`；随后同一次 `solve()` 会清 `_last_solution`。直接对 `model.model.Add(...)` 做外部裸修改不属于 master 公共变更通道，代码无法自动拦截；在本轮审查的 master API 通道中，修复后未发现 stale 解可被合法调用链读出的路径。

5. bound state extraction 语义

`extract_bound_state()` 仅从当前 `_solver` 读取 `BestObjectiveBound()` 到 `lb`，在 status 为 OPTIMAL/FEASIBLE 时读取 `ObjectiveValue()` 到 `ub`，再按 `(ub - lb) / max(abs(ub), 1)` 计算 gap，见 `src/models/master_model.py:11738-11783`。它不依赖 placement cache。修复后 cut 成功会清 `_solver/_status`，所以 cut 后未重 solve 的 bound state 不再误用旧模型的 objective/bound。现有 `src/tests/test_master_extract_bound_state.py:36-86` 覆盖 no solver、optimal、feasible gap、UNKNOWN 无 incumbent 与 epsilon target。

下游消费补充: BindingSubproblem 初始化对 placement entry 做 top-level dict copy，见 `src/models/binding_subproblem.py:332-335`；power injection 也复制原 solution 并按 `facility_pools["power_pole"][pose_idx]` 注入 pole，见 `src/models/power_placement_subproblem.py:191-214`。本轮未发现消费者会把 inactive residual 或 ghost marker 当真实设施 pose 消费。

## Q3: master 侧 cut apply 通道审查

判定: 除 Finding 1 的 solver witness 失效缺口外，未发现新的 cut apply soundness 问题。

1. conflict member 到 present literal 的解析与 alias 处理

exact-coordinate cut 不直接使用 z BoolVar，而是把 conflict member 规范化为 `(scope, pose_idx, slots, pose_tuple)`。mandatory instance 先映射到 group_id，再以 `(mandatory::<group_id>, pose_idx)` 作为抽象 presence key；optional solution id 通过 `_infer_optional_template_from_solution_id()` 映射到 template，再以 `(optional::<tpl>, pose_idx)` 为 key。任何 pose 缺失、template 解析失败或 key 重复都会返回空 entries，使 `add_benders_cut()` 返回 False，见 `src/models/exact_coordinate_master.py:6817-6882`。这对 alias 采取 fail-closed，而不是去重继续。

present literal 本身由 `_slot_pose_match_literal()` 和 `_pose_present_literal()` 建立: match literal 等价于 slot 的 `x/y/mode`，residual optional 还要求 `active == 1`，见 `src/models/exact_coordinate_master.py:6750-6787`；present literal 等价于任一 slot match，见 `src/models/exact_coordinate_master.py:6789-6815`。因此同一 `(instance, pose)` 经 group/optional 表示不会产生计数不一致的重复 literal。

2. condition `OnlyEnforceIf` 极性

exact add cut 构造 `sum(present_lits) <= len(present_lits) - 1`，若有 condition literals 则 `bound.OnlyEnforceIf(cond)`，见 `src/models/exact_coordinate_master.py:6915-6918`。OR-Tools 语义下这表示所有 condition 为真时 cut 生效，condition 假时该 bound 不约束，正符合 ghost A cut 只在 ghost A anchor 选中时启用。legacy path 也同样实现，见 `src/models/master_model.py:11931-11937`。

persisted cut replay 侧会把 `condition_set` 解析回 `u_var`；未知 key、非整数 rect_idx、rect_idx 越界或 anchor 不匹配都返回 `ok=False`，caller 必须 skip cut，不能退化成无条件，见 `src/search/benders_loop.py:1488-1533` 与 `src/search/benders_loop.py:6588-6606`。这与 master 的 `OnlyEnforceIf` 极性互补，未发现反极性 over-cut。

3. `N` 与实际 literal 数

exact path 在所有 entries 成功解析为 present literal 后才添加 bound；任何 member 解析不到 literal 都直接 `return False`，见 `src/models/exact_coordinate_master.py:6896-6913`。最终约束使用 `len(present_lits) - 1`，见 `src/models/exact_coordinate_master.py:6915-6916`，所以 N 与实际进入 sum 的 literal 数一致。legacy path 也在所有 var 解析成功且无 alias 后才添加 `sum(literals) <= len(literals) - 1`，见 `src/models/master_model.py:11910-11937`。

4. all-or-nothing 与部分状态

exact path 在 entries 为空或任一 present literal 缺失时，不更新 `coordinate_benders_cut_count`、不写 `coordinate_benders_last_cut`、不清 solver/cache，也不添加实际 nogood bound，见 `src/models/exact_coordinate_master.py:6896-6913` 与 `src/models/exact_coordinate_master.py:6919-6927`。在失败前可能已创建的 helper equality/match literals 只是定义性通道，不构成 conflict nogood；从可行布局集合看没有“半个 cut”残留。成功路径现在还会清 solver/status，避免 Finding 1 的旧 witness 泄漏，见 `src/models/exact_coordinate_master.py:6928-6935`。

## 验证记录

环境:

- Python: `/mnt/data/zmd_review_r6/.venv313/bin/python`, Python 3.13.5
- OR-Tools: 9.15.6755
- 依赖安装: 从 `/mnt/data/zmd_py313_linux_x86_64.zip` 解出的 wheels 离线安装 `requirements.txt`

专项测试:

```bash
PYTHONPATH=. /mnt/data/zmd_review_r6/.venv313/bin/python -m pytest -q -p no:randomly \
  src/tests/test_exact_coordinate_protocol_bounds.py \
  src/tests/test_master_extract_bound_state.py \
  src/tests/test_master_cut_solution_invalidation.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py::test_resolver_resolves_ghost_anchor_condition_to_u_var \
  src/tests/test_benders_cut_replay_condition_lifecycle.py::test_empty_condition_set_resolves_to_no_lits \
  src/tests/test_benders_cut_replay_condition_lifecycle.py::test_persisted_cut_replay_preserves_condition_does_not_overprune \
  src/tests/test_benders_cut_replay_condition_lifecycle.py::test_persisted_cut_replay_fires_when_condition_active \
  src/tests/test_benders_cut_replay_condition_lifecycle.py::test_coordinate_replay_alias_collision_fails_closed_instead_of_one_literal_ban \
  src/tests/test_benders_cut_replay_condition_lifecycle.py::test_legacy_benders_cut_alias_collision_fails_closed \
  src/tests/test_power_witness_cut_dilution.py::test_whole_layout_cut_dilution_fails_closed_when_synthetic_pole_loses_literal \
  src/tests/test_master.py::test_extract_solution_emits_pose_optional_identifier \
  src/tests/test_master.py::test_exact_core_clone_rebinds_solution_extraction_and_benders_cuts
```

结果: `26 passed in 1.42s`。

R5-A 补充 probes:

```bash
cd /mnt/data/zmd_review_r6/project
PYTHONPATH=. /mnt/data/zmd_review_r6/.venv313/bin/python /mnt/data/zmd_review_r6/probe_r6_master.py
```

结果:

```text
probe_skip_power_keeps_geometry: OK
probe_nonempty_family_empty_required_tuple_rows_fails_closed: OK
```

cut stale solver probe 修复后结果:

```text
add True
after last None solver none? True status None
extract after cut {}
status2 CpSolverStatus.OPTIMAL sol2 {... 'pose_idx': 1 ...}
```

P1.2 proof obligations:

```bash
PYTHONPATH=. /mnt/data/zmd_review_r6/.venv313/bin/python scripts/check_p1_2_proof_obligations.py
```

结果: `P1.2 proof obligation check passed: 8 obligations anchored`。

全量测试说明:

尝试运行 `PYTHONPATH=. /mnt/data/zmd_review_r6/.venv313/bin/python -m pytest -q -p no:randomly src/tests`，900 秒超时未完成；超时前输出推进到约 16% 进度，未捕获到失败断言。因此本报告以专项测试与 probes 为验证依据，不声明全量 suite 完跑。
