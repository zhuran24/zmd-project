# 终末地 IndustrialPlanner cuts 机制面 round 6 审查报告

快照校验：`/mnt/data/zmd_snapshot_38b57070.zip` 的 sha256 为 `38b570700c77f3f1a7b3f6c2ac7e9c2f2ec6385c7a93c2ee34ca7ce857ab8abe`，与任务指定值一致后才解包审查。仓库根为 zip 内 `project/`。

结论：本轮发现 **1 个 HIGH soundness finding**，属于 PCR patch 的 port-terminal 边界漏建模，会让 patch 模型比完整 routing 更严格。已提供 unified diff 补丁和回归测试。补丁后，Q1 的 PCR-R5-H1/H2/H4 复核仍通过，H3 的 “port connector 伸入 patch” 子情形被补齐；Q2 ladder 和 Q3 cut 生命周期未发现额外 soundness finding。

---

## Finding PCR-CUT-R6-H1：front cell 在 patch 内、connector 在 patch 外的端口被 PCR patch 丢弃

Severity：HIGH

影响范围：env-gated PCR-CUT (`EXACT_B1_PATCH_ROUTING_CORE`)。公开 certified 默认仍被 blocker gate 挡住，但该机制一旦启用，会破坏 PCR 的核心前提 “patch routing 必须 over-approximate full routing”。

原始代码位置：

- `src/models/patch_routing_core.py:322-328`：`_index_port_fronts()` 只在 port connector cell 属于 `patch_spec.cells` 时索引端口；connector 在 patch 外直接 `continue`。
- `src/models/patch_routing_core.py:575-578`：`_add_port_adherence()` 同样只处理 connector cell 在 patch 内的端口。
- `src/search/patch_conflict_separator.py:314-318`：separator 只把 connector cell 在 patch 内的 `port_specs` 放进 patch 模型。
- `src/models/patch_routing_core.py:128-146`：signature lifting 的 local signature 文本和实现都只按 port connector 是否在 patch 内决定是否保留端口。

### 为什么这是 over-cut / false conflict

完整 routing 的端口语义不是在 occupied connector cell 上走 belt，而是在 terminal front cell 上注入或吸收流。对于 output port，route state 在 front cell 上必须有来自 connector 方向的 `flow_in`；对于 input/sink port，route state 在 front cell 上必须向 connector 方向 `flow_out`。

因此，当 connector cell 刚好在 patch 外、front cell 在 patch 内时，完整 routing 仍然可以合法使用这个端口；旧 PCR patch 却把这个端口当作 “patch 外接口” 丢掉。更糟的是，这种 connector cell 往往是 occupied，不属于 `full_grid_active_cells`，所以普通 boundary relaxation 不会替它产生自由边界变量。结果是 patch 可能缺少完整 routing 的合法 source/sink terminal，变得比完整模型更严格。

最小可复现 probe：

```python
from src.models.patch_routing_core import PatchSpec, PatchPortSpec, PoseAssumption, PatchRoutingCore
from src.models.routing_subproblem import GRID_H, GRID_W, RoutingGrid, RoutingSubproblem

ports_dict = [
    {"instance_id": "src", "x": 0, "y": 0, "dir": "E", "commodity": "ore", "type": "out"},
    {"instance_id": "sink", "x": 3, "y": 0, "dir": "W", "commodity": "ore", "type": "in"},
]
free_corridor = {(1, 0), (2, 0)}
full_occupied = {(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in free_corridor}
full = RoutingSubproblem(RoutingGrid(full_occupied, ports_dict), ["ore"])
full.build()
assert full.solve(time_limit=5.0) == "FEASIBLE"

ports = [
    PatchPortSpec("src", 0, 0, "E", "ore", "out", 0),   # connector outside patch, front (1,0) inside
    PatchPortSpec("sink", 3, 0, "W", "ore", "in", 0),   # sink connector inside patch, front (2,0) inside
]
assumptions = [
    PoseAssumption("src", 0, "src_p0", "assum_src"),
    PoseAssumption("sink", 0, "sink_p0", "assum_sink"),
]
core = PatchRoutingCore(
    PatchSpec.from_cells("external_source_probe", frozenset({(1, 0), (2, 0), (3, 0)})),
    full_grid_occupied={(0, 0), (3, 0)},
    full_grid_active_cells={"ore": {(1, 0), (2, 0)}},
    patch_port_specs=ports,
    pose_assumptions=assumptions,
    boundary_relaxation=True,
)
core.build()
print(dict(core._patch_port_fronts_source), dict(core._patch_port_fronts_sink), core.solve(2.0))
```

旧代码实测输出的关键现象：`_patch_port_fronts_source == {}`，sink front 存在，但 patch solve 为 `INFEASIBLE`。同一布局的完整 `RoutingSubproblem` 为 `FEASIBLE`，选中的直线状态为 `(1,0)` 与 `(2,0)` 两格 ground belt，从 source connector 注入并向 sink connector 输出。

这给出了严格反例：`full routing FEASIBLE` 但 `patch routing INFEASIBLE`，违反 PCR cut 的逆否证书前提。

### 修复

补丁文件：`industrialplanner_cuts_r6_pcr_front_port.patch`

修复要点：

1. `PatchRoutingCore._index_port_fronts()` 改为按 terminal front cell 是否在 patch free cells 内来索引端口，而不是要求 connector cell 在 patch 内。
2. `PatchRoutingCore._add_port_adherence()` 改为只要 connector cell 或 front cell 任一与 patch 相交，就处理端口；front 在 patch 内时加 exact terminal link，front 在 patch 外但 full-active 时仍由 boundary relaxation 吸收。
3. `_build_patch_inputs()` 改为 connector cell 或 front cell 任一在 patch 内时纳入 `patch_ports`。
4. `build_local_pose_signature()` 同步把 front-in-patch 的 external connector 纳入 signature，防止 signature lifting 把“端口 terminal 影响 patch”和“不影响 patch”的 pose 合并。
5. 新增 3 个回归：完整 routing 可行而 patch 也必须可行；separator 必须纳入 external connector；local signature 必须保留 front-in-patch external port。

补丁后关键 probe 变为：`_patch_port_fronts_source == {(1, 0, "W", "ore"): 1}`，`_patch_port_fronts_sink == {(2, 0, "E", "ore"): 1}`，patch solve 为 `FEASIBLE`。

---

## Q1：PCR-R5-H1..H4 修复确认与交互审查

### H1 全层边界 relaxation

结论：R5 修复本身 sound。`src/models/patch_routing_core.py:427-459` 对每个 patch boundary cell、每个 commodity、每个跨出 patch 且邻格在 full active 内的方向，在 `for layer in LAYERS` 下同时创建 `boundary_out` 与 `boundary_in`。`LAYERS = [0, 1]`，没有 ground-only residual seam。

约束形态也符合 over-approx：boundary vars 不占 patch capacity、不做边界间 balance；patch 内选中的 outgoing/incoming state 只 implication 到对应 boundary var，见 `src/models/patch_routing_core.py:516-522` 与 `src/models/patch_routing_core.py:552-557`。这些自由边界只能放松 patch，不会使 patch 比 full routing 更严格。邻格越界出 70×70 时不会开普通 boundary，这与完整 routing 的普通 cell-to-cell 边不可越界一致。

### H2 sink/source 极性

结论：R5 的 `DIR_OPP` 极性修复正确。

独立规则推导如下。port `dir` 指向 terminal front cell：`front = port_cell + DIR_DELTA[dir]`。output/source 从 port connector 向 front cell 注入，front cell 的 route state 看到的 predecessor 在 `DIR_OPP[dir]`；input/sink 从 front cell 向 port connector 输出，front cell 的 route state 的 outgoing 方向也是 `DIR_OPP[dir]`。因此 source 侧应索引 `(front, recv_dir=DIR_OPP[dir])`，sink 侧应索引 `(front, send_dir=DIR_OPP[dir])`。

patch 代码在 `src/models/patch_routing_core.py:333-338` 与 `src/models/patch_routing_core.py:603-612` 采用该极性；完整 routing 在 `src/models/routing_subproblem.py:786-799` 与 `src/models/routing_subproblem.py:1212-1223` 也一致。回归 `test_input_port_adherence_uses_direction_toward_sink_port` 覆盖了 sink 极性。

### H3 support 充分性

结论：原 R5 support 的 “patch + 四向 cardinal 邻居” 对普通 boundary/free-cell occupancy 是充分的；本轮发现的漏洞不是 diagonal，也不是远程效应，而是 terminal front 在 patch 内时 external connector 的端口语义被旧代码丢掉。补丁后该子情形被纳入 patch ports、support assumptions 和 local signature。

`_patch_support_signature_cells()` 在 `src/search/patch_conflict_separator.py:121-143` 包含 patch cells 与四向邻居。由于 routing continuity、port front、boundary relaxation 都只通过 cardinal edge 交互，对角邻居不会直接改变 patch belt 可行性；远程 full-grid 影响被 boundary vars 过近似吸收，不需要进入 core。

occupancy owner 映射来自 `_placement_to_occupied()`。support owner 被加入 assumptions，然后 `_augment_core_with_patch_support()` 在 `src/search/patch_conflict_separator.py:146-162` 合并到 solver core；额外加 support term 只会弱化 nogood，不会加强。owner 解析失败时没有可映射 assumption，后续 raw core/replay/add cut 任一阶段失败都会 reject；不会退化成无 owner 的强 cut。

### H4 重叠回落

结论：R5 修复 sound。`PoseBoolExactMasterDelegate.add_patch_routing_core_cut()` 在 `src/models/pose_bool_exact_master.py:798-807` 发现 lifted var set 重叠时直接返回 `added=False`，在 `src/search/patch_conflict_separator.py:497-520` caller 只在 `add_outcome.get("added")` 为真时记录 accepted 并返回；否则记为 rejected 后继续候选，最终 `cut_added=False` / `exhausted_no_accepted_cut`。没有“未加 cut 但标记已处理”的状态污染。

### 四修复相互作用

H1 × H3：boundary 邻格 occupancy 已由 patch + cardinal ring support 捕获；本轮补丁又把 front-in-patch 的 external connector owner 纳入 port/signature 路径，补齐 terminal 交互。

H2 × replay validate：replay 走同一 `PatchRoutingCore` 模型，仅替换 assumption subset，见 `src/models/patch_routing_core.py:757-804` 与 `src/models/patch_routing_core.py:807-851`。因此 accepted core 使用修后极性重新求证；若极性错误导致 replay 不复现 INFEASIBLE，会 fail-closed。

---

## Q2：front_blocked ladder 多 rung 交互

代码路径在 `src/search/benders_loop.py:5381-5701`。代码里还有一个 D2 flow env-gated rung，位于 PCR 前；按本轮目标，重点结论如下。

| rung | 次序与互斥 | 失败行为 | soundness 判读 |
|---|---|---|---|
| D2 flow | 若 `EXACT_B1_D2_COMMODITY_FLOW` 成功加 cut，设置 `_b1_d2_skip_other_cuts=True`，跳过 PCR/deletion/lazy/cell | exception 只打印，继续后续 rung | 本轮非主体；与 PCR 不叠加 |
| PCR-CUT | D2 未成功时尝试；成功后 `cut_added=True` 且 `_b1_pcr_skip_other_cuts=True` | reject/exception 不置 `cut_added`，继续 deletion/lazy/cell 逻辑 | 成功后不与 deletion/lazy/cell 同 conflict 叠加；本轮补丁修复其 patch over-approx 漏洞 |
| deletion-core | 只有 PCR/D2 未成功时可能启用；若 env 开启，`_skip_per_port_loop = _b1_use_deletion_core ...` 会跳过 per-port lazy/cell，即使 deletion 没加 cut | 若没得到/没加 cut，最终 `cut_added=False`，返回 `RUN_STATUS_UNKNOWN` | 这是 fail-closed 的收敛取舍，不是 over-cut；没有把 ladder 完成误当 proof |
| lazy_demand | deletion 未启用时，per-port 收集 target；lazy 分支 `continue`，不会同一 blocked_port 再走 cell cut | 若 target 无法映射或 delegate 不加 cut，最终 UNKNOWN | 每条 lazy cut 独立依赖 pose/front blocker demand，不依赖前一 rung 未加 cut |
| cell_cut / fallback nogood | lazy 未启用时，cell cut 可对多个 blocked_port 加多条 cut；若 cell_cut 不在场，才走 `_add_exact_persisted_nogood()` 生成当前进程内 cut | 无 conflict set 或 add fail 时不剪；最终 UNKNOWN | 多条 sound cut 叠加仍 sound；fallback 是先 apply master cut 再 register/generated telemetry |

关键点：PCR 成功后不会继续走 deletion-core。若所有在场 rung 都 reject/fail，`src/search/benders_loop.py:5680-5701` 将 `master_follow_up` 标为 `cut_stall` 并返回 `RUN_STATUS_UNKNOWN`，不是 certified，也不会假装剪枝完成。

rung 间状态泄漏未发现。PCR 的 patch/core/lifecycle metadata 局部留在 separator；deletion-core 独立用 `port_specs` 和当前 `solution` 建 oracle；lazy/cell 只消费 `routing_precheck_summary` 和 master delegate 的只读 pose lookup cache。所有实际加 cut 的 delegate 方法都清 `_last_solution`，不会复用旧 incumbent。

---

## Q3：cut 跨迭代生命周期

| 场景 | 代码位置 | 判读 |
|---|---|---|
| 同一 master 实例内 cut 累积 | master 在 `run_benders_for_ghost_rect()` 中构建一次后交给 `LBBDController`，见 `src/search/benders_loop.py:6497-6512`、`src/search/benders_loop.py:6516-6528`、`src/search/benders_loop.py:6547-6558`；LBBD loop 在 cut added 后 `continue`，见 `src/search/benders_loop.py:4698-4704` | 约束添加到同一个 CP-SAT model，没有删除路径；已剪解不会在同一 instance 内复活 |
| master cut 添加方法 | PCR cut `src/models/pose_bool_exact_master.py:814-819`；pose nogood `src/models/pose_bool_exact_master.py:960-967`；lazy `src/models/pose_bool_exact_master.py:1161-1168`；cell `src/models/pose_bool_exact_master.py:1208-1224` | 每次 add 都向 model 添加 constraint 并清 `_last_solution`；没有覆盖/移除旧 constraint 的逻辑 |
| generated exact_safe cut | `_add_exact_persisted_nogood()` 在 `src/search/benders_loop.py:6141-6173` 先构造/校验 `BendersCut`，再 `master.add_benders_cut()`，成功后 register 并 append 到 `generated_exact_safe_cuts` | 该路径的 cut 是当前进程即时 proof 后应用；后续 persisted 输出只是 telemetry |
| master 重建 | 新 candidate/ghost 或 exact_core/non-exact 分支会创建新 `MasterPlacementModel`，见上方构建位置 | 旧内存约束不跨实例继承。若不带旧 cut，是收敛性问题，不是假设“已知冲突已剪”；每个新实例重新经历 proof/rung |
| persisted `exact_safe_cuts` replay | `src/search/benders_loop.py:6560-6577` 在 certified exact 下统计输入数量后强制 `raw_candidate_cuts = []`；后面的 replay loop `6577-6609` 因空列表不执行；最终 metadata 标 `persisted_exact_safe_cut_replay_enabled=False`，见 `src/search/benders_loop.py:6899-6906` | 磁盘 cut 不会直接重放为 proof。`CutManager.load()` 虽有 exact_safe/hash/mode 过滤 (`src/models/cut_manager.py:450-513`)，但 certified 主路径的强边界是在 benders load/apply 侧将 raw candidates 清空 |
| within-instance lifting | `enumerate_pose_vars_with_patch_signature(instance_id, ...)` 只解析同一个 owner 的 pose pool，见 `src/models/pose_bool_exact_master.py:720-759`；`add_patch_routing_core_cut()` 对每个 core term 分 owner 枚举并检查 lifted set overlap，见 `src/models/pose_bool_exact_master.py:779-807` | PROJECT_LOCK 的不跨 instance lifting 仍被代码强制；H4 overlap fail-closed 后仍成立 |

---

## 回归与自验

已执行：

```bash
python -m pytest -q -p no:randomly src/tests/test_patch_routing_core.py
# 17 passed in 30.53s

python -m pytest -q -p no:randomly \
  src/tests/test_patch_routing_core.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py
# 34 passed in 4.52s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

cd /mnt/data/zmd_r6_applycheck/project && patch -p1 --dry-run < /mnt/data/industrialplanner_cuts_r6_pcr_front_port.patch
# patch dry-run clean
```

全量 `python -m pytest -q -p no:randomly src/tests` 已启动，但沙盒 300 秒超时，超时前未看到 failure；本报告不宣称全量完成。

---

## 最终状态

本轮不是 clean 轮：发现并修复 1 个 HIGH soundness finding。补丁后，PCR-R5 四项义务在本轮攻击范围内没有剩余已知 soundness finding；front_blocked ladder 的失败路径 fail-closed；cut 生命周期没有发现跨迭代复活或 persisted proof replay 路径。
