# REVIEW.md — IndustrialPlanner routing round 4

## 0. 输入与结论

快照只使用 `/mnt/data/zmd_snapshot_278e4d67.zip`。开工前校验：

```text
278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0  zmd_snapshot_278e4d67.zip
```

与任务给定 sha256 一致。仓库根为 zip 内 `project/`。

本轮结论：F-RT-R3-01 的 connector 扣除/terminal-side continuity 修复在我检查到的当前消费面上未发现新的 connector false-FEASIBLE 或 connector 过剪；但 Q2/Q3 角度发现并修复 2 个问题：

1. **F-RT-R4-01 / HIGH / false-INFEASIBLE**：`analyze_exact_routing_domain()` 把同一 commodity 的所有 terminal fronts 强制压到单个连通分量，误拒“两个互不连通但各自有 source+sink 的同商品岛”。这与当前 solver guard 和 specs/08 的全局 pool 语义不一致。
2. **F-RT-R4-02 / MEDIUM / fail-closed hardening for external/future `port_specs`**：canonical 非重叠 pose 构造不出重复 terminal key；但直接开放 `port_specs` 时可构造两个物理端口折叠到同一个 `(front, terminal_dir, commodity, type)` key，旧 adherence 只重复加同一个 `sum == 1`，没有表达 multiplicity=2。已加重复 key fail-closed。

补丁已生成：`/mnt/data/frt_r4_routing_fixes.patch`，sha256：

```text
3201074e7c8dc9eb008e63038bfbfa8ea1f5491abdf193fc541a0e792ec880e3  frt_r4_routing_fixes.patch
```

`patch --dry-run -p1 < /mnt/data/frt_r4_routing_fixes.patch` 已在重新解包的原始快照上通过。

## 1. Finding F-RT-R4-01 — 同 commodity 多岛合法网络被 precheck/domain shrink 误拒

Severity: **HIGH**。类型：false-INFEASIBLE / completeness。位置：`src/models/routing_subproblem.py` 原逻辑在 `analyze_exact_routing_domain()` 的 commodity component 汇总段；补丁后代码在 `src/models/routing_subproblem.py:500-573`。

旧逻辑对一个 commodity 取 `front_cells` 的所有 component id，只要 `len(component_ids) > 1` 就返回 `relaxed_disconnected`。这对“source A → sink A”和“source B → sink B”两个互不连通的同商品小网络过严：当前 routing guard 的语义是每个 source 至少到达一个 sink、每个 sink 可由某个 source 到达，而不是要求同 commodity 全体 terminal 在同一个空间连通块中。specs/08 的 super source/sink pool 模型也允许多个物理岛各自有供需闭合。

最小 probe：

```python
from src.models.routing_subproblem import RoutingGrid, RoutingSubproblem, analyze_exact_routing_domain

allowed = {(1,0), (2,0), (3,0), (1,10), (2,10), (3,10)}
occupied = {(x,y) for x in range(70) for y in range(70) if (x,y) not in allowed}
ports = [
    {"instance_id":"src1",  "x":0, "y":0,  "dir":"E", "type":"out", "commodity":"ore"},
    {"instance_id":"sink1", "x":4, "y":0,  "dir":"W", "type":"in",  "commodity":"ore"},
    {"instance_id":"src2",  "x":0, "y":10, "dir":"E", "type":"out", "commodity":"ore"},
    {"instance_id":"sink2", "x":4, "y":10, "dir":"W", "type":"in",  "commodity":"ore"},
]

grid = RoutingGrid(occupied, ports)
print(analyze_exact_routing_domain(grid)["status"])
r = RoutingSubproblem(grid, ["ore"])
r.build()
print(r.solve(time_limit=5.0), r.build_stats.get("last_solve", {}).get("connectivity"))
```

旧代码观测：`analyze` 为 `relaxed_disconnected`，normal build/solve 为 `INFEASIBLE`。同一个物理布局如果绕过该 precheck，用外置 feasible `domain_analysis` 明确给出这 6 个 active cells，则 CP-SAT 返回 `FEASIBLE`，提取到两条直线 `(1,0)-(3,0)` 与 `(1,10)-(3,10)`，guard `failure_count == 0`。这说明误拒来自 precheck/domain shrink 生产者，不来自 routing encoding 本体。

消费侧放大路径：`run_exact_routing_precheck()` 把 `_analysis` 带给 benders loop；benders 在 `src/search/benders_loop.py:5283-5293` 保存 precheck status 和 domain stats，`relaxed_disconnected` 会先走 binding-local safe reject (`src/search/benders_loop.py:5306-5315`)，之后在无替代或替代耗尽时进入 `src/search/benders_loop.py:5684-5722` 的拒绝路径。因此该 producer 过严会丢弃合法 binding/layout。

修法：按 component 分组 terminal fronts。若某 commodity 同时有 source 和 sink，则每个含 terminal 的 component 必须至少有一个 source front 和一个 sink front；满足的多个 component 取 domain union，并按 component 各自执行 `_peel_terminal_core()`。若 commodity 当前只有单侧 terminal，则保留旧的单 component 保守行为，以兼容 routing-free/wireless 局部 precheck 语义。补丁主体在 `src/models/routing_subproblem.py:500-573`。

回归：`src/tests/test_routing.py:230-266` 新增 `test_same_commodity_disconnected_source_sink_islands_are_routable()`。补丁后 probe 输出：

```text
analysis status feasible []
solve normal FEASIBLE {'selected_route_states': 6, 'checked_commodities': 1, 'failure_count': 0, 'failures': []}
```

## 2. Finding F-RT-R4-02 — terminal key 折叠在 canonical 下构造不出，但外置 port_specs 可触发

Severity: **MEDIUM**。类型：non-canonical direct/external `port_specs` false-FEASIBLE hardening。位置：旧 adherence 在 `src/models/routing_subproblem.py:_add_port_adherence()` 对每个 port 重复加 `sum(vars_for_port) == 1`，但 `_source_port_fronts/_sink_port_fronts` 和 guard metadata 都以 set/dict key 消费 terminal front，重复 key 不表达 multiplicity。

canonical 复核结论：在当前 pose generator 与 binding 语义下，重复 key 构造不出。

几何论证：端口 key 含 `front = port + dir` 与 terminal direction `Opp(dir)`；若两个端口有相同 `front` 和相同 `dir`，则两者 connector cell 都等于 `front - dir`，即 connector cell 相同。对于 generator 生成的任意边缘端口，`connector - dir` 是 facility body 的 occupied cell；因此两个不同设施若共享该 connector+dir，其 body backing cell 重叠，master no-overlap 禁止。单个 pose 内，generator 不产生相同 `(x, y, dir, side)` 的重复端口。

实证复核脚本调用 `generate_all_pools(load_templates())`，结果：

```text
pool_counts {'manufacturing_3x3': 17408, 'manufacturing_5x5': 16368, 'manufacturing_6x4': 16380, 'protocol_core': 6728, 'protocol_storage_box': 4624, 'power_pole': 4761, 'boundary_storage_port': 134}
total_ports 599382
bad_back_cell 0
within_pose_duplicate_same_side_connector_dir 0
```

不过直接开放 `RoutingGrid(..., port_specs=...)` 时可构造：

```python
ports = [
    {"instance_id":"src_a", "x":0, "y":0, "dir":"E", "type":"out", "commodity":"ore"},
    {"instance_id":"src_b", "x":0, "y":0, "dir":"E", "type":"out", "commodity":"ore"},
    {"instance_id":"sink",  "x":4, "y":0, "dir":"W", "type":"in",  "commodity":"ore"},
]
```

旧模型会让 `src_a/src_b` 折叠到同一个 source-front exact-one key。补丁新增 `_duplicate_terminal_front_keys()`，在 `analyze_exact_routing_domain()` 中把它作为 `front_blocked` fail-closed 返回，并在 `RoutingSubproblem.build()` 中对外置 feasible `domain_analysis` 再次 fail-closed。位置：`src/models/routing_subproblem.py:136-186`, `src/models/routing_subproblem.py:398-417`, `src/models/routing_subproblem.py:761`, `src/models/routing_subproblem.py:814-819`。

补丁后 probe：

```text
front_blocked duplicate_terminal_front_key 2
INFEASIBLE
```

回归：`src/tests/test_routing.py:269-306` 新增 `test_duplicate_terminal_front_keys_fail_closed()`。

## 3. Q1 — F-RT-R3-01 connector 修复确认清单

| 面 | 代码位置 | 审查结论 |
|---|---:|---|
| connector 集合来源 | `src/models/routing_subproblem.py:120-133` | `_port_connector_cells()` 只取 in-grid physical port connector `(port.x, port.y)`，与 PROJECT_LOCK 的 F-RT-R3-01 定义一致。 |
| placement-core 域入口 | `src/models/routing_subproblem.py:279-299` | core path 先扣 `port_connector_cells`，再过滤 `free_neighbors_by_cell`，再重算 connected components；没有复用扣除前 component map。 |
| grid 域入口 | `src/models/routing_subproblem.py:310-320` | grid path 同样从 `grid.free_cells` 扣 connectors，并重算 components。 |
| precheck front 可用性 | `src/models/routing_subproblem.py:424-459` | front 必须在扣除后的 `resolved_free_cells`；若某 port 的 front 正好是另一 port connector，会进入 `front_blocked`，不会作为 belt cell。按 specs/06:72-75、specs/08:29-34、specs/09:61-63，该过剪不存在，因为 connector 非 routing cell，port edge 与 space edge 分离。 |
| 外置 `domain_analysis` | `src/models/routing_subproblem.py:846-860` | `_bind_domain_analysis()` 对 component/active cells 二次扣除 `port_connector_cells`，外置旧域不能把 connector 带回变量域。 |
| route state 创建 | `src/models/routing_subproblem.py:984-1004` | `_create_routing_variables()` 只遍历 `_commodity_active_cells`，connector 被扣后不会生成 `r_vars`。 |
| `RoutingGrid.routable_cells` 残留 | `src/models/routing_subproblem.py:687-710` | 仍为 `free_cells | port_cells`，但全库 grep `\.neighbors\(|neighbors\(` 只发现 `RoutingGrid.neighbors()` 自身、`_cell_neighbors()` 和测试 fake；routing solver/precheck 不消费该属性。当前不是 soundness hole；若未来启用 `grid.neighbors()`，应同步扣 connector 或删除该 dead/stale API。 |
| source connector-side successor ban | `src/models/routing_subproblem.py:1037-1065` | 对普通态向 source front 的 connector 侧发送做零化。几何上 source front `f = p + d`，其 `recv_dir = Opp(d)`；若相邻格向 `f` 发送并使 `recv_dir` 匹配，则相邻格唯一为 `p`，即 connector。不会误杀非 connector 普通态。 |
| sink connector-side predecessor ban | `src/models/routing_subproblem.py:1075-1101` | 对普通态从 sink front 的 connector 侧接收做零化。同理，匹配 `send_dir = Opp(d)` 的 predecessor 唯一为 connector cell。 |
| independent verifier | `cc_context/verification/diff_fuzz/routing_connectivity_diff.py:71-97`, `293-310` | oracle 独立从 port_specs 推导 connector cell，并检查 route-state 占 connector；self-test 覆盖 connector reuse。 |

结论：F-RT-R3-01 的主修复在 routing domain、外置 analysis、placement-core reuse 和 verifier 上闭合；本轮未找到 connector false-FEASIBLE。

## 4. Q2 — 域收缩/复用与 precheck 三态消费表

### 域收缩与复用

`_routing_shrink_summary()` 只是 telemetry：`src/search/benders_loop.py:3960-3968` 返回当前记录的 domain/state-space 数字；`_update_routing_shrink_from_domain_stats()` 与 `_update_routing_shrink_from_build_stats()` 在 `src/search/benders_loop.py:3990-4010` 只复制统计值，不生产 routing domain。因此 shrink summary 本身不会把 connector 带回，也不会剪掉格子。

真正的域生产者是 `analyze_exact_routing_domain()`，入口统一走 `_resolve_routing_domain_context()`，该入口现在扣 connector 并重算 components。补丁 F-RT-R4-01 修正了 producer 对多 component same-commodity 的过严 shrink；补丁 F-RT-R4-02 修正了 malformed/external terminal key 折叠。

### precheck 三态 × benders 消费侧

| precheck status | producer 语义 | benders 消费 | 审查结论 |
|---|---|---|---|
| `feasible` | relaxed/domain precheck 通过，并携带 `_analysis` | `src/search/benders_loop.py:5724-5766` 用 `_analysis` 建 routing model；`src/search/benders_loop.py:5781-5800` 只有 routing solve `FEASIBLE` 且 solver guard 接受后才返回 certified。 | precheck-feasible 没被当成证明；solve 可拒绝，安全。 |
| `front_blocked` | 某 port front 越界/不在扣 connector 后 free domain，补丁后也承载 duplicate terminal key fail-closed | 若有 binding alternatives 且 safe reject，`src/search/benders_loop.py:5306-5315` 加 binding nogood 重枚举；否则走 `src/search/benders_loop.py:5362-5682` 的 cut ladder，无法加 cut 则 UNKNOWN。env bypass 只改本地 `precheck_status`，但旧 `_analysis` 仍传给 routing build，不会把 blocked analysis 变证明。 | 消费侧未把 front_blocked 当全局无条件 layout proof；符合 PROJECT_LOCK:115 的 binding-local 约束。 |
| `relaxed_disconnected` | front component 关系不满足 relaxed connectivity | 若有 binding alternatives，`src/search/benders_loop.py:5684-5710` 加 binding nogood 并 re-solve；无替代/替代 INFEASIBLE 后才 break 到 layout exhaustion path。 | 消费方式基本 fail-closed；本轮找到的是 producer 过严，已由 F-RT-R4-01 修正。 |

多 source/多 sink front exact-one 一致性：`_index_port_fronts()` 在 `src/models/routing_subproblem.py:786-799` 用 `DIR_OPP` 为 source/sink 建 terminal direction；`_add_port_adherence()` 在 `src/models/routing_subproblem.py:1118-1144` 对每个物理 port 加 exact-one。补丁 F-RT-R4-02 防止重复 physical ports 折叠到同一 exact-one key。

## 5. Q3 — terminal key 折叠挂账复核

结论分两层：

1. **canonical pose + binding pipeline 下构造不出**。理由见 F-RT-R4-02：相同 `(front, direction)` 推出相同 connector；generator 端口 backing cell 恒在 body occupied 内；不同设施会 body overlap，单 pose 内实测无重复端口。
2. **外置/future `port_specs` 入口能构造**。因此补丁新增 fail-closed 检查，并覆盖 external `domain_analysis` 绕过路径。

该补丁不改变 canonical 合法解域，只把非法/重复 terminal spec 从“折叠成一个端口”改为显式 `front_blocked`/`INFEASIBLE`。

## 6. Q4 抽查维持

F-RT-R2-01 极性：`_index_port_fronts()` 对 source 与 sink 都使用 `DIR_OPP[direction]` (`src/models/routing_subproblem.py:786-799`)；`_add_port_adherence()` source 取 ground `flow_in=Opp(dir)`，sink 取 ground `flow_out=Opp(dir)` (`src/models/routing_subproblem.py:1129-1144`)；diff-fuzz oracle 独立同样在 `cc_context/verification/diff_fuzz/routing_connectivity_diff.py:51-68` 推导。

F-RT-R2-02 边守恒：`_add_directed_edge_balance_constraints()` 对每个 non-terminal directed cell-to-cell edge 建 `sum(send_vars) == sum(recv_vars)` (`src/models/routing_subproblem.py:985-1031`)，并跳过 source/sink terminal sides，形状符合上一轮修复目标。

guard reachability：`_validate_selected_route_connectivity()` 收集 missing source/sink、unreachable sink、source_without_sink，并在 `src/models/routing_subproblem.py:1513-1559` 拒绝 locally-closed-but-globally-dead incumbents。F-RT-R4-01 的多岛合法网络能通过 guard，是因为每个 source 到达一个 sink，且每个 sink 可由某个 source 到达。

fuzz oracle 独立性：oracle connector occupancy 检查基于 rule-derived `_port_connector_cells()`，不是复制 solver active-domain 实现；self-test 已包含 connector reuse 场景 (`cc_context/verification/diff_fuzz/routing_connectivity_diff.py:293-310`)。

## 7. 验证记录

环境：Python 3.13，依赖离线安装到 `/mnt/data/zmd_pydeps`，命令均以 `PYTHONPATH=/mnt/data/zmd_pydeps:$PWD` 在 `/mnt/data/zmd_review_r4/project` 下执行。

通过：

```text
python -m py_compile src/models/routing_subproblem.py src/tests/test_routing.py

python -m pytest -q -p no:randomly \
  src/tests/test_routing.py::test_same_commodity_disconnected_source_sink_islands_are_routable \
  src/tests/test_routing.py::test_duplicate_terminal_front_keys_fail_closed \
  src/tests/test_routing.py::test_port_connector_cell_cannot_be_reused_as_routing_cell \
  src/tests/test_routing.py::test_routing_placement_core_precheck_matches_grid_path \
  src/tests/test_routing.py::test_routing_subproblem_from_placement_core_matches_grid_build \
  src/tests/test_routing.py::test_sink_front_consumes_against_outward_normal_on_straight_corridor \
  src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel \
  src/tests/test_routing.py::test_routing_supports_splitter_state \
  src/tests/test_routing.py::test_elevated_bridge_states_require_opposite_neighbors \
  src/tests/test_wireless_sink_binding_semantics.py::test_wireless_sink_virtual_slots_do_not_emit_routing_port_specs \
  src/tests/test_wireless_sink_binding_semantics.py::test_wireless_sink_routing_has_no_sink_front_and_needs_no_belt_to_box \
  src/tests/test_wireless_sink_binding_semantics.py::test_wireless_sink_commodity_does_not_reenter_routing_from_producer_output \
  src/tests/test_wireless_sink_binding_semantics.py::test_routing_aware_filter_ignores_blocked_wireless_producer_output_fronts
# 13 passed in 1.16s

python -m pytest -q -p no:randomly src/tests/test_p0_certified_soundness_fixes.py
# 12 passed in 0.86s

python cc_context/verification/diff_fuzz/routing_connectivity_diff.py --self-test
# PASS — accepts valid flow; catches A-1 dead-end + capacity overload + connector reuse.

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

未完成：全量 `python -m pytest -q src/tests` 未跑完；一次 `src/tests/test_routing.py` 全文件尝试在 240 秒沙盒超时后停止。因此本报告只声明上述专项与脚本通过。
