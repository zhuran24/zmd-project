# IndustrialPlanner cuts 机制面 round 5 独立审查报告

快照：`zmd_snapshot_3f4ceebb.zip`  
校验：`sha256 = 3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9`，与任务给定值一致。  
范围：只审 CUT-R4-H1 修复确认、PCR-CUT 通道本体、routing deletion-core minimizer 本体。

## 结论

本轮不是零 soundness finding。CUT-R4-H1 修复确认通过；deletion-core minimizer 未发现 over-cut soundness 问题；PCR-CUT 通道发现 4 个会导致 patch 证明过强或 lifted master cut 过强的问题，已给出补丁与回归。

## Findings

### PCR-R5-H1：patch boundary relaxation 只接 ground layer，排除了 full routing 可行的 elevated boundary continuation

Severity: High / soundness / possible over-cut

位置：`src/models/patch_routing_core.py` 原实现 `_create_boundary_vars()` 仅为 `GROUND_LAYER` 建 boundary vars，且 `_add_successor_constraint()` / `_add_predecessor_constraint()` 只在 `layer == GROUND_LAYER` 时使用 boundary relaxation。对应 full routing 中，普通 cell-to-cell continuation 对 `LAYERS` 均成立：`src/models/routing_subproblem.py:911-923` 支持任意 layer 的 active neighbor，`src/models/routing_subproblem.py:1120-1195` 对任意 layer 加 successor/predecessor continuity。

论证：PCR 的数学前提是 `full grid routing FEASIBLE => patch routing FEASIBLE`。原 patch model 在 `_incoming_dir_supported()` / `_outgoing_dir_supported()` 中允许 elevated state 看到 patch 外 active neighbor，但 continuity 阶段没有 elevated boundary var，于是 selected elevated state 一旦需要跨出 patch 就被强制为 0。这使 patch model 严格于 full model。若全局可行路由用 elevated bridge 穿过人工 patch 边界，patch 可能误判 INFEASIBLE，随后生成 master nogood，形成 over-cut。

复现 probe：在单 cell patch `(10,10)` 上强制选择 elevated west-to-east bridge state。补丁前 `PatchRoutingCore.solve()` 返回 `INFEASIBLE`；补丁后返回 `FEASIBLE`。回归见 `src/tests/test_patch_routing_core.py:189-218`。

修复：`src/models/patch_routing_core.py:427-459` 为所有 `LAYERS` 建 `boundary_in/out` vars；`src/models/patch_routing_core.py:516-556` 按当前 `layer` 查 boundary vars，而非硬编码 ground layer。boundary vars 仍不消耗 patch capacity、不做外部 balance，是对 full routing 的 over-approx。

### PCR-R5-H2：patch input/sink port 方向与 RoutingSubproblem 不同口径，直线可行 sink corridor 可被误判 INFEASIBLE

Severity: High / soundness / possible over-cut

位置：`src/models/patch_routing_core.py` 原 `_index_port_fronts()` 和 `_add_port_adherence()` 对 input port 使用 `ps.direction` 作为 sink outgoing direction；full routing 使用 `DIR_OPP[direction]`：`src/models/routing_subproblem.py:786-799` 与 `src/models/routing_subproblem.py:1212-1223`。

论证：port direction 指向 front cell。对 input/sink port，route 从 front cell 进入 port cell，方向应是 `DIR_OPP[port.direction]`。原 patch model 要求 route 朝 `port.direction` 离开 front cell，等价于朝远离 port 的方向输出。一个 `source -> ... -> sink` 的 straight corridor 在 full routing 语义下可行，但 patch 中 sink adherence 方向反了，会被判为无可用 `vars_for_port` 或 continuity 冲突。

复现 probe：patch cells `{(0,0),(1,0),(2,0),(3,0),(4,0)}`，source at `(0,0)` dir `E`，sink input at `(4,0)` dir `W`，中间 `(1,0),(2,0),(3,0)` free。补丁前 patch solve 为 `INFEASIBLE`；补丁后为 `FEASIBLE`。回归见 `src/tests/test_patch_routing_core.py:221-254`。

修复：`src/models/patch_routing_core.py:333-338` sink front index 改为 `send_dir = DIR_OPP[ps.direction]`；`src/models/patch_routing_core.py:603-612` input port adherence 同步使用 `send_dir`。

### PCR-R5-H3：patch CP-SAT 将 full placement occupancy 编成常量，但 UNSAT core / master terms 只覆盖 port owners，可能忘掉真正 blocker

Severity: High / soundness / over-cut

位置：`src/search/patch_conflict_separator.py` 原 `_build_patch_inputs()` 从全布局构造 `occupied` / `free_cells`，但 `PoseAssumption` 只来自 `patch_ports`；`run_patch_conflict_separation()` 将 solver core 直接转为 master terms。patch 中某个 port front 被 blocker footprint 占用时，blocker 作为常量影响 infeasibility，却不在 solver assumption core 中。

论证：若 patch INFEASIBLE 的原因是 victim port front 被 blocker footprint 占用，patch solver core 可能只含 victim 的 assumption，因为 blocker 的 footprint 是常量。原 master cut 会变成“victim pose 不可选”，即使 blocker 换位置后 victim pose 可以被 route，属于 over-cut。这个问题不需要跨 instance lifting，只要有一个无 patch port 的 blocker footprint 就能触发。

复现 probe：victim source port at `(0,0)` dir `E`，front `(1,0)` 被 blocker footprint 占用；`port_specs` 只有 victim。补丁前 cutter 的自然 core 支撑缺 blocker；补丁后 `_build_patch_inputs()` 支撑 assumptions 包含 `victim` 与 `blocker`，并在加 master cut 前强制把 blocker 加回 augmented core。回归见 `src/tests/test_patch_routing_core.py:257-330`。

修复：新增 `src/search/patch_conflict_separator.py:121-162`：

- `_patch_support_signature_cells()` = patch cells 加一圈 cardinal boundary neighbor cells。patch 内 occupancy 决定本地 capacity，boundary neighbor occupancy 决定 boundary relaxation 是否可用。
- `_augment_core_with_patch_support()` 将 solver UNSAT core 与 constant-occupancy support assumptions 合并。额外 terms 只会削弱 nogood，不会加强。

`_build_patch_inputs()` 现在返回 `support_signature_cells`，并把 support cells 中的 occupancy owners 与 patch port owners 都建为 assumptions：`src/search/patch_conflict_separator.py:291-351`。`run_patch_conflict_separation()` 在 master cut 前做 augmentation，并把 expanded support signature cells 传给 signature lifting：`src/search/patch_conflict_separator.py:431-496`。

### PCR-R5-H4：signature lifting 可重复计入同一组 master BoolVar，导致线性 nogood 系数加倍

Severity: High / soundness / possible over-cut

位置：`src/models/pose_bool_exact_master.py:add_patch_routing_core_cut()`。原实现对每个 core term 生成 `equivalent_vars` 后直接 `sum(sig_exprs) <= K - 1`。若两个 core owners 在同一 mandatory group 下拥有相同 patch-local signature，它们的 lifted var set 可以重叠。此时同一 BoolVar 被重复计入，例如 `2*x <= 1`，会把“两个 owner 同时出现才冲突”的证明强化成“一个 pose 也不能选”。

论证：`enumerate_pose_vars_with_patch_signature()` 是 within-instance / same resolved pool 的 lifting，未跨 instance 扫描，但 mandatory group 的多个 instance 共享 group-level `x_vars`。不同 instance 的 lifted sets 可能因相同 local signature 而重叠。重复线性项不是弱化，而是加强 master cut。

复现 probe：构造两个同 group instance `A/B`，两个 pose 在 patch 内 signature 相同，`add_patch_routing_core_cut([("A",0), ("B",1)], patch_cells)`。补丁前会添加含重复 var set 的 cut；补丁后 fail-closed 返回 `overlapping_signature_lift_terms`。回归见 `src/tests/test_patch_routing_core.py:333-363`。

修复：`src/models/pose_bool_exact_master.py:775-810` 记录所有 lifted var names，若新的 equivalent var set 与已见集合有交集，返回 `added=False`，不加 cut。PCR caller 对 `added=False` 已按 reject 处理并继续回落。

## Q1 CUT-R4-H1 修复确认

结论：确认 sound，未发现新的 CUT-R4-H1 soundness finding。

1. disjointness 与 binding `extract_port_specs()` 是同一口径。pose-bool delegate 中 `_routing_free_sink_commodities()` 取 `owner.generic_io_requirements["required_generic_inputs"]` 正数集，`_required_generic_output_commodities()` 取 `required_generic_outputs` 正数集，`_required_generic_outputs_are_all_routing_visible()` 只在二者 disjoint 时为 True：`src/models/pose_bool_exact_master.py:106-140`。binding 侧 `PortBindingModel.__init__()` 规范化同名两节并从 required generic inputs 正数集构造 `routing_free_sink_commodities`：`src/models/binding_subproblem.py:342-373`；`extract_port_specs()` 对 concrete output 和 generic_output 均按该集合丢弃 route-free sinks：`src/models/binding_subproblem.py:1018-1071`。

2. certified path 上两边集合来源同步。`ExactSearchSession.create()` 先加载一次 `generic_io_requirements` 并传给 `MasterPlacementModel.build_exact_core()`：`src/search/benders_loop.py:1571-1588`；master normalize 后把 snapshot 放进 `ExactMasterCore`：`src/models/master_model.py:2263-2268` 与 `src/models/master_model.py:2590-2596`；每次 binding 构造经 `_binding_generic_requirements_kwargs()` 从 master snapshot 复制同一 `required_generic_outputs/inputs`：`src/search/benders_loop.py:4911-4955`，实际传入 `PortBindingModel`：`src/search/benders_loop.py:4986-4993` 与 retry path `src/search/benders_loop.py:6000-6006`。

3. “混合需求 fail-closed 计 0”覆盖 lazy-demand 与 cell-pattern cache。`generic_output_visible` 只有在 global saturation 与 routing-visible disjointness 同时成立才计入：`src/models/pose_bool_exact_master.py:215-222`。lazy-demand cut 读取 `_routing_visible_profile_demands()`：`src/models/pose_bool_exact_master.py:1092-1156`；cell-pattern cache 只把 `_mandatory_port_side_is_cell_pattern_exact()` 为 True 的侧写入 routing-visible port cache：`src/models/pose_bool_exact_master.py:257-298` 与 `src/models/pose_bool_exact_master.py:1002-1040`。全仓搜索 `_generic_output_slots_are_globally_saturated` / `_required_generic_outputs_are_all_routing_visible` 未发现第三个 saturation consumer。

4. broad `except Exception` 的方向是 fail-closed。`_required_generic_outputs_are_all_routing_visible()` 的 broad except 会把异常吞成 False：`src/models/pose_bool_exact_master.py:133-140`。这会静默关闭该加速 cut，可能降低可观测性，但不会把不可证明的 routing-visible 输出当成可证明输出。

## Q2 PCR-CUT 通道本体判读

补丁后，PCR 的 patch 前提编码位置如下：

- patch 输入使用 full-grid free cells 作为每个 commodity 的 active domain，是对真实 routing domain 的 over-approx：`src/search/patch_conflict_separator.py:309-312`。
- 只约束 port cell 在 patch 内的 selected routing-visible `port_specs`；port cell 不在 patch 的 terminal 被丢弃或由 boundary relaxation 吸收，是 over-approx：`src/search/patch_conflict_separator.py:314-327` 与 `src/models/patch_routing_core.py:583-593`。
- artificial boundary 现在对所有 routing layers 建虚拟 in/out vars，且这些 vars 不消耗 patch capacity、不做外部 balance，是 over-approx：`src/models/patch_routing_core.py:427-459` 与 `src/models/patch_routing_core.py:516-556`。
- patch constants 的 master support 现在覆盖 patch cells 与一圈 cardinal boundary cells，并使用该 expanded set 做 signature lifting：`src/search/patch_conflict_separator.py:121-162`、`src/search/patch_conflict_separator.py:291-351`、`src/search/patch_conflict_separator.py:474-496`。

QuickXplain cap 判读：`minimize_patch_core_quickxplain()` 在 oracle cap 命中时返回保守的 remaining candidate set，不声称全局 minimum；随后 `extract_and_validate_patch_core()` 必须 replay validate minimized core，若 invalid 则回退到已验证 raw core：`src/models/patch_routing_core.py:861-918` 与 `src/models/patch_routing_core.py:921-994`。非最小核使 `sum_i term_i <= K-1` 的 K 更大，禁止的是更具体的共现组合，方向是更弱而不是更强。

Replay validate 判读：`validate_patch_core()` 用 presolve=false、workers=1 复解同一个 patch CP-SAT：`src/models/patch_routing_core.py:805-849`。它是 patch model 内的确定性 replay proof，不独立证明 patch-over-approx 数学前提；该前提必须由 patch encoding 本身保证。上述 H1/H2/H3/H4 正是补齐此前缺口。

within-instance signature lifting 判读：`enumerate_pose_vars_with_patch_signature()` 只解析传入的 `instance_id`，并在该 owner 对应的 mandatory group / optional template / pole pool 内枚举，不跨 unrelated instance 池：`src/models/pose_bool_exact_master.py:720-759`。补丁新增 lifted var overlap fail-closed，防止同 group alias/重叠 var set 被重复计入：`src/models/pose_bool_exact_master.py:775-810`。

fail-closed 判读：patch solve 非 INFEASIBLE 不尝试 cut；raw replay invalid 直接 reject；minimized replay invalid 回退到 raw；master delegate `added=False` 计为 reject 不加 cut；PCR caller 只有 `sep_result.cut_added` 才 skip other cuts，否则继续回落 deletion/lazy/cell：`src/search/patch_conflict_separator.py:459-496` 与 `src/search/benders_loop.py:5445-5518`。

## Q3 deletion-core minimizer 算法本体判读

结论：未发现 deletion-core over-cut soundness finding。

1. oracle 没有比真 routing precheck 更强。真 precheck 在 front out-of-grid 或 front_cell 不在 resolved free cells 时给 `front_blocked`：`src/models/routing_subproblem.py:424-458`。deletion oracle 只在 out-of-grid 或 front cell 被另一个 instance 占用时返回 True：`src/search/routing_deletion_core_minimizer.py:125-144`，并且可用 `routing_visible_port_keys_by_instance` 过滤到实际 `extract_port_specs()` 的 routing-visible terminal 集：`src/search/routing_deletion_core_minimizer.py:41-68` 与 `src/search/routing_deletion_core_minimizer.py:125-136`。它会漏掉 same-instance occupied front、duplicate terminal、port connector exclusion、relaxed disconnection 等真 precheck 情况，因此是弱 oracle；弱 oracle 只会让 core 偏大或 fallback，不会让核偏小而 over-cut。

2. 删除顺序得到的是 deletion-minimal，不是全局 minimum。实现文档写明返回 deletion-minimal：`src/search/routing_deletion_core_minimizer.py:9-19`；算法是单 pass deletion，只有 trial subset 仍 oracle-blocked 才删除：`src/search/routing_deletion_core_minimizer.py:207-230`。调用方只把结果作为 placement-local nogood，不消费“全局最小”语义：`src/search/benders_loop.py:5550-5568`。

3. master cut 的量化范围与核支撑一致。返回的 `pose_idx_by_id` 只来自当前保留下来的 `S`：`src/search/routing_deletion_core_minimizer.py:234-247`；caller 直接传给 pose-bool delegate `add_benders_cut()`：`src/search/benders_loop.py:5562-5568`。`add_benders_cut()` 对 instance→pose var 解析失败、pose_idx 非法、重复 BoolVar alias 均 fail-closed 不加：`src/models/pose_bool_exact_master.py:906-955`。此外，有 binding alternatives 时 front_blocked 先走 binding selection nogood/re-solve，不进 deletion-core：`src/search/benders_loop.py:5325-5367` 与 `_binding_has_alternatives()` `src/search/benders_loop.py:6054-6059`，因此 deletion-core 的 port set 是固定 binding selection 下的 routing-visible port set。

## Regression / self-check

已运行：

```text
PYTHONPATH=. /mnt/data/zmd_venv/bin/python -m pytest -q -p no:randomly \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_patch_routing_core.py \
  src/tests/test_wireless_front_consumers_r4.py

33 passed in 4.63s
```

```text
PYTHONPATH=. /mnt/data/zmd_venv/bin/python scripts/check_p1_2_proof_obligations.py

P1.2 proof obligation check passed: 8 obligations anchored
```

尝试运行全量：

```text
PYTHONPATH=. /mnt/data/zmd_venv/bin/python -m pytest -q -p no:randomly src/tests
```

结果：300 秒沙盒超时，进度约 16%，超时前未见 failure。因此本轮全量未完成，专项与 proof-obligation 已通过。
