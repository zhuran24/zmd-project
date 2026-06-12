# 终末地 IndustrialPlanner routing face round 6 review

审查对象：`zmd_snapshot_3f4ceebb.zip`

快照校验：通过。

```text
3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9  /mnt/data/zmd_snapshot_3f4ceebb.zip
```

环境：Python 3.13.5 venv，依赖由 `zmd_py313_linux_x86_64.zip` 离线安装。核心包版本确认到 `ortools 9.15.6755`、`pytest 9.0.2`。

## 总结论

**本轮零 soundness finding。**

未发现需要修改 routing_subproblem / guard / precheck 的 soundness 问题；本轮不提供代码补丁。

审查范围限定为题面指定的三块：R5 修复确认、`_validate_selected_route_connectivity` guard 本体、`_iter_state_patterns()` 状态枚举完备性。其它面未重审，已知历史 finding 未重复报告。

## 复现实证

### 专项 probe

新增一次性审查 probe 覆盖以下断言：

1. 独立推导的 pattern 封闭集合与 `_iter_state_patterns()` 精确相等。
2. 外置 stale `domain_analysis` 中的 occupied / out-of-grid / connector cells 均被 `_bind_domain_analysis()` 裁掉。
3. source front 被裁掉、sink front 被裁掉，均触发 `_add_port_adherence()` 的 `0 == 1` fail-closed 路径。
4. guard adjacency 对 L0→L1→L0 route-state 的邻接与独立公式一致。
5. guard 对断开的 source/sink selected states 拒收。
6. malformed selected state key 走异常路径，不返回 accepted。

命令：

```bash
cd /tmp/zmd_r6_review/project
PYTHONPATH=. /tmp/zmd_r6_review/.venv/bin/python /tmp/zmd_r6_review/routing_r6_probe.py
```

输出：

```text
[Routing Model] build 0.0s
[Routing Model] build 0.0s
[Routing Model] build 0.0s
pattern_counts {0: {'merger': 16, 'splitter': 16, 'belt': 12}, 1: {'bridge': 4}}
domain_clip_and_front_adherence ok
guard_adjacency_and_fail_closed ok
```

### 专项 pytest

命令：

```bash
cd /tmp/zmd_r6_review/project
PYTHONPATH=. /tmp/zmd_r6_review/.venv/bin/python -m pytest -q -p no:randomly \
  src/tests/test_routing.py::test_external_domain_analysis_cannot_route_through_occupied_cell \
  src/tests/test_routing.py::test_port_connector_cell_cannot_be_reused_as_routing_cell \
  src/tests/test_routing.py::test_same_commodity_disconnected_source_sink_islands_are_routable \
  src/tests/test_routing.py::test_duplicate_terminal_front_keys_fail_closed \
  src/tests/test_routing.py::test_sink_front_consumes_against_outward_normal_on_straight_corridor \
  src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel \
  src/tests/test_routing.py::test_elevated_bridge_states_require_opposite_neighbors \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_feasible_incumbent_requires_source_to_sink_connectivity \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_timeout_does_not_expose_rejected_routes \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_checks_each_selected_commodity \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_preserves_real_feasible_path \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_self_check_falls_back_to_nogood \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_rejects_source_front_without_sink_reachability
```

结果：

```text
13 passed in 2.36s
```

### proof obligations

命令：

```bash
cd /tmp/zmd_r6_review/project
PYTHONPATH=. /tmp/zmd_r6_review/.venv/bin/python scripts/check_p1_2_proof_obligations.py
```

结果：

```text
P1.2 proof obligation check passed: 8 obligations anchored
```

### 全量 pytest

尝试运行：

```bash
cd /tmp/zmd_r6_review/project
PYTHONPATH=. /tmp/zmd_r6_review/.venv/bin/python -m pytest -q -p no:randomly src/tests
```

结果：240s 沙盒限时中止，进度显示到约 7%，中止前没有打印 failure。全量未完成，因此本报告只以专项 probe、专项 pytest 与 proof-obligation 脚本作为实证基线。

## Finding 列表

本轮零 soundness finding。

## Q1: F-RT-R5-01 修复确认

### Q1.1 `grid.free_cells` 与 connector set 的时点

R5 修复点在 `src/models/routing_subproblem.py:841-859`：

- `port_connector_cells = _port_connector_cells(self.grid.port_specs)` 位于 `src/models/routing_subproblem.py:847`。
- `routable_domain_cells = set(self.grid.free_cells) - port_connector_cells` 位于 `src/models/routing_subproblem.py:848`。
- 外置 `commodity_component_cells` 与 `commodity_active_cells` 都在 bind 时与 `routable_domain_cells` 求交，见 `src/models/routing_subproblem.py:850-857`。

构造来源也一致：

- 普通 `RoutingGrid.__init__()` 在 `src/models/routing_subproblem.py:667-685` 从 `occupied_cells`、`port_specs` 构造 `occupied`、`port_specs`、`free_cells`、`port_cells`、`routable_cells`。
- `RoutingGrid.from_placement_core()` 在 `src/models/routing_subproblem.py:693-704` 从 `RoutingPlacementCore` 复制 `occupied`、`port_specs`、`free_cells`。
- domain precheck 的解析路径也在 `src/models/routing_subproblem.py:325-363` 复制 `grid.port_specs` 或 `placement_core`，并同样减去 connector cells。

我用 grep 查了 `src/` 内对 `grid.free_cells` / `grid.port_specs` 的赋值，除 `RoutingGrid.from_placement_core()` 之外未发现 build/bind 之后的内部 mutation path。Python 外部手工改对象当然能破坏任意不变量，但这不是当前仓库内 master→routing 的生产路径；就本面而言，`_bind_domain_analysis()` 使用的是 build-time 的当前 grid snapshot，而不是 stale caller analysis 自带的自由格集合。

结论：R5 修复使用的两个集合在内部路径上没有 bind 后被改写的证据；stale `domain_analysis` 不能绕开 `grid.free_cells - connector`。

### Q1.2 occupied / out-of-grid / connector 三类格同口径挡回

三类 stale active-domain 格子的裁剪逻辑是同一个集合交：`raw_active_cells & (grid.free_cells - connector)`，见 `src/models/routing_subproblem.py:847-857`。

逐类判读：

- **occupied cell**：不在 `grid.free_cells`，因此被 `& set(self.grid.free_cells)` 裁掉。已有回归 `src/tests/test_routing.py:230-258` 覆盖 stale analysis 把 occupied `(2, 0)` 塞进 active domain 时，最终不建变量且 INFEASIBLE。
- **out-of-grid cell**：`grid.free_cells` 只由 `range(GRID_W)` × `range(GRID_H)` 生成，普通构造见 `src/models/routing_subproblem.py:675-679`，placement-core 构造也来自同一 70×70 occupied/free contract；因此 out-of-grid 不会出现在 `grid.free_cells`。
- **connector cell**：`_port_connector_cells()` 明确把 in-grid physical port connector cells 收集出来，注释说明 routing variables 活在 `port + dir` 的 front cell，connector cell 是 terminal node 而非 free belt cell，见 `src/models/routing_subproblem.py:120-133`。bind 时再次 `- port_connector_cells`，见 `src/models/routing_subproblem.py:847-848`。

本轮 probe 还故意把 connector cell 放进 `grid.free_cells`，以证明 connector subtraction 独立于 occupied-cell 排斥仍然生效。active domain 最终只剩真正 front cells，connector / occupied / out-of-grid 都没有建 route var。

### Q1.3 是否存在第四类“free_cells 里但不该该商品走”的格

在 routing_subproblem 当前输入契约内，没有发现需要额外从 active domain 中全局剔除的第四类格。

- **其它商品的 terminal front**：terminal front 是那一格物流组件本体，不是实体设施本体。规范要求 port 离开机器后至少踩中 1 个 free logistics cell，见 `specs/03_rule_canonicalization.md:290-304` 与 `specs/09_exact_grid_routing_subproblem.md:61-64`。因此 front cell 本身属于可铺物流组件的 free cell，而不是 connector/solid。若它被本商品或其它商品实际选中，`_add_capacity_constraints()` 对每个 `(cell, layer)` 加 AtMostOne，见 `src/models/routing_subproblem.py:1026-1030`；port adherence 对 terminal ground side 精确履行，见 `src/models/routing_subproblem.py:1196-1237`。没有规则要求“所有商品都必须预先避开其它商品的 terminal front cell”。
- **ghost rectangle / ghost_pick**：本 routing 子问题只接收 `occupied_cells` / `free_cells` / `port_specs` / optional `placement_core`。在当前 master→routing 提取代码中，`ghost_pick` 明确不加入 occupied cells，见 `src/search/benders_loop.py:6038-6052`。ghost 是否应作为 master 几何 blocker 属于 master/preprocess/geometry contract，本轮不把它改判为 routing_subproblem 内的额外域裁剪义务。
- **无线 routing-free 终品端口**：按 08 章，wireless routing-free 不进入本子问题 port 集合，见 `specs/08_topological_flow_subproblem.md:24-37`。这不是 active-domain 内的“free but forbidden”格。

结论：本面没有发现“应由 routing_subproblem 再裁掉、但 R5 修复未裁”的第四类格。

### Q1.4 front 被裁出 active domain 的 source/sink fail-closed

`_add_port_adherence()` 对所有 `self.grid.port_specs` 逐条循环，不按 patch/domain 跳过，见 `src/models/routing_subproblem.py:1200-1206`。

- 若 front cell 不在该 commodity 的 active domain，立即 `self.model.Add(0 == 1)`，见 `src/models/routing_subproblem.py:1207-1210`。
- source port 要求 ground layer 上 `flow_in == Opp(port_dir)` 的变量 exact-one，见 `src/models/routing_subproblem.py:1212-1217`。
- sink port 要求 ground layer 上 `flow_out == Opp(port_dir)` 的变量 exact-one，见 `src/models/routing_subproblem.py:1218-1223`。
- 如果 front 在 active domain 但没有任何可用 state，也同样 `0 == 1`，见 `src/models/routing_subproblem.py:1225-1228`。

本轮 probe 分别构造 source front 被裁掉、sink front 被裁掉两例，均触发 `blocked_ports >= 1` 且 `solve()` 返回 `INFEASIBLE`。没有发现“port 不在 patch/域内就早退跳过”的绕路。

## Q2: guard 本体深审

### Q2.1 `_route_state_adjacency` 与 CP-SAT successor/predecessor 语义

guard 的 selected graph 并不是从 `extract_routes()` 来的，而是直接从 CP-SAT solver 选中的 `r_vars` key 来的：`_selected_route_keys()` 位于 `src/models/routing_subproblem.py:1258-1263`，`_validate_selected_route_connectivity()` 第一步调用它，见 `src/models/routing_subproblem.py:1604`。

邻接构建分两步：

- `_route_state_input_index()` 以 `(x, y, direction, commodity)` 建 input index，不包含 layer，见 `src/models/routing_subproblem.py:1274-1283`。
- `_route_state_adjacency()` 对 selected state 的每个 `flow_out`，走到邻格，并寻找 `flow_in == Opp(flow_out)`、同 commodity 的 selected state；sink-front terminal output 不继续展开，见 `src/models/routing_subproblem.py:1311-1330`。

这与 CP-SAT 约束同构：

- successor 约束对某 `(x, y, layer, d_out, commodity)` 的 selected out-var，寻找邻格 `(nx, ny)` 上任意 layer 的 `flow_in == Opp(d_out)` 接收 var，见 `src/models/routing_subproblem.py:1120-1156`，尤其 `src/models/routing_subproblem.py:1148` 的 `_vars_by_cell_dir_in_commodity` 不含 layer。
- predecessor 约束对某 selected in-var，寻找前格任意 layer 的 `flow_out == Opp(d_in)` 发送 var，见 `src/models/routing_subproblem.py:1158-1194`，尤其 `src/models/routing_subproblem.py:1186` 的 `_vars_by_cell_dir_out_commodity` 不含 layer。
- directed-edge balance 在同一 directed cell edge 上做发送数 = 接收数，见 `src/models/routing_subproblem.py:1068-1118`。它约束通道数，不改变 guard 使用的 route-state arc 语义。

跨层边：guard 忽略 layer 是正确的。09 章允许 continuity 的接驳层级 `L'` 可不同，见 `specs/09_exact_grid_routing_subproblem.md:57-60`；bridge 无需额外起降格，见 `specs/09_exact_grid_routing_subproblem.md:51-55`。CP-SAT 也通过 layer-agnostic `_vars_by_cell_dir_*_commodity` 实现这一点。因此 L0↔L1、L1↔L0、L1↔L1 的 receiver/sender 语义一致。

terminal 例外：

- source-front terminal side 是 BFS 起点，不需要 predecessor。CP-SAT 在 source ground side 上直接返回，见 `src/models/routing_subproblem.py:1170-1171`；guard 在 `_terminal_nodes_by_front_for_keys()` 中把 ground state 的 matching `flow_in` 标为 source node，见 `src/models/routing_subproblem.py:1301-1304`。
- sink-front terminal side 是 BFS 终点，不需要 successor。CP-SAT 在 sink ground side 上直接返回，见 `src/models/routing_subproblem.py:1132-1133`；guard 在 `_terminal_nodes_by_front_for_keys()` 中把 ground state 的 matching `flow_out` 标为 sink node，见 `src/models/routing_subproblem.py:1305-1308`，并且 `_route_state_adjacency()` 不从 sink terminal output 继续展开，见 `src/models/routing_subproblem.py:1322-1324`。
- CP-SAT 还显式禁止“从相邻 route state 流入 source terminal side”和“从 sink terminal side 反向作为 predecessor”，见 `src/models/routing_subproblem.py:1142-1146` 与 `src/models/routing_subproblem.py:1180-1184`。`_route_state_adjacency()` 本身没有接收 `source_fronts` 参数，因此对任意手造 key 集合会比 CP-SAT potential graph 稍宽；但对 solver-selected incumbent，这类 key 不可能满足 CP-SAT constraints。本轮 probe 也验证了 malformed/手造非法 selected key 不会走 accepted 路径。对 lazy-cut potential graph 而言，较宽只会让 cut self-check 更保守，失败则回退 nogood，不构成 false-FEASIBLE。

结论：作为 final acceptance guard over CP-SAT incumbents，guard adjacency 与当前 CP-SAT successor/predecessor/terminal 语义一致；未发现“guard 更宽导致 false-FEASIBLE”的路径。若未来把 `_route_state_adjacency()` 作为纯 potential graph oracle 使用，建议显式传入 `source_fronts` 并过滤 source-entry arcs，以减少保守 fallback，但这不是本轮 soundness finding。

### Q2.2 多 source / 多 sink pooling 判定

guard 不要求 perfect matching，也不要求 all-to-all。它做两件事：

- 从所有 source-front selected nodes 的并集出发，要求每个 sink front 至少被某个 source 达到，见 `src/models/routing_subproblem.py:1645-1650`。
- 对每个 source front 单独出发，要求它至少能到达一个 sink node，见 `src/models/routing_subproblem.py:1652-1657`。

这正好匹配 09 章 addendum 的文字：每个 source front 至少到达一个 sink front，且每个 sink front 被某个 source front 到达，见 `specs/09_exact_grid_routing_subproblem.md:100-106`。也匹配 08 章 pool semantics：同 commodity 是全局资源池软配对，不硬绑定专线，见 `specs/08_topological_flow_subproblem.md:88-92`。

结论：guard 的多源多汇语义是 existence/pooling，不是完美匹配；实现与 specs 一致。

### Q2.3 extract 与 guard 之间的信息丢失

题面假设 guard 输入是 `extract_routes()`；当前实现并非如此。

- `solve()` 在收到 CP-SAT `FEASIBLE`/`OPTIMAL` 后，先调用 `_validate_selected_route_connectivity(solver)`，只有 connected 才设置 `_connectivity_guard_accepted = True` 并返回 `FEASIBLE`，见 `src/models/routing_subproblem.py:1773-1789`。
- `extract_routes()` 是 guard 接受之后的输出路径；若 status 不是 feasible/optimal，或 `_connectivity_guard_accepted` 不为真，直接返回空列表，见 `src/models/routing_subproblem.py:1844-1849`。
- 真正输出时，`extract_routes()` 保留 `x`、`y`、`layer`、`commodity`、`component_type`、完整 `flow_in`、完整 `flow_out`，见 `src/models/routing_subproblem.py:1851-1868`。

结论：guard 不依赖 `extract_routes()`，不存在 extract→guard 的字段裁剪导致验收图变弱的问题。

### Q2.4 guard fail handling

guard 的正常拒收路径是 fail-closed：

- 缺 source-front selected node / 缺 sink-front selected node 会进入 `missing_sources` / `missing_sinks`，见 `src/models/routing_subproblem.py:1620-1629`。
- sink 不可达、source 无 sink 可达会进入 failure，见 `src/models/routing_subproblem.py:1645-1667`。
- `solve()` 对 guard 拒收的 incumbent 先尝试 self-checked lazy cut，失败则加 selected-route nogood，继续求解，见 `src/models/routing_subproblem.py:1791-1826`。
- 如果一直只有被 guard 拒收的 incumbent 且时间耗尽，`solve()` 清空 `_solver`、置 UNKNOWN 并返回 `TIMEOUT`，见 `src/models/routing_subproblem.py:1737-1753`。

字段缺失/结构异常没有被吞掉后返回 success；异常会中断而不是 produced FEASIBLE。就 certified acceptance 来说，这是 fail-closed 而非 fail-open。

## Q3: 状态模式枚举完备性

### Q3.1 独立推导的封闭集合

令方向集合 `D = {N, S, E, W}`，`Opp(N)=S`、`Opp(S)=N`、`Opp(E)=W`、`Opp(W)=E`。

从 `specs/03_rule_canonicalization.md:306-344`、`specs/09_exact_grid_routing_subproblem.md:43-64` 和当前 accepted capacity-node splitter/merger 口径推导：

1. **L0 belt**
   - 集合：`{ flow_in=(a,), flow_out=(b,), component_type='belt' | a,b ∈ D, b != a }`
   - 数量：`4 * 3 = 12`
   - 依据：belt 为单格有向映射，输入方向与输出方向不同，见 `specs/03_rule_canonicalization.md:306-317`。

2. **L0 splitter**
   - 集合：`{ flow_in=(a,), flow_out=O, component_type='splitter' | a ∈ D, O ⊆ D \ {a}, |O| ∈ {2,3} }`
   - 1-in-2-out 数量：`4 * C(3,2) = 12`
   - 1-in-3-out 数量：`4 * C(3,3) = 4`
   - 总数：`16`
   - 依据：分流器是 1 进多出容量节点，原文 1 进 3 出并按可行分配器处理，见 `specs/03_rule_canonicalization.md:329-336`；题面本轮也明确要求核 1-in-2-out 组合。

3. **L0 merger**
   - 集合：`{ flow_in=I, flow_out=(b,), component_type='merger' | b ∈ D, I ⊆ D \ {b}, |I| ∈ {2,3} }`
   - 2-in-1-out 数量：`4 * C(3,2) = 12`
   - 3-in-1-out 数量：`4 * C(3,3) = 4`
   - 总数：`16`
   - 依据：汇流器按与分流器近似的容量节点处理，见 `specs/03_rule_canonicalization.md:338-344`。

4. **L1 bridge**
   - 集合：`{ flow_in=(a,), flow_out=(Opp(a),), component_type='bridge' | a ∈ D }`
   - 数量：`4`
   - 依据：L1 只允许直桥，不允许转弯，见 `specs/09_exact_grid_routing_subproblem.md:51-55`。

总封闭集合数量：`12 + 16 + 16 + 4 = 48`。

### Q3.2 与实现逐项对照

实现位于 `src/models/routing_subproblem.py:867-905`：

- L1 branch 在 `src/models/routing_subproblem.py:868-875`：对每个 `d_in` 产出 `flow_out=(DIR_OPP[d_in],)`，`component_type='bridge'`。与推导的 4 个 L1 bridge 精确相等。
- L0 belt 在 `src/models/routing_subproblem.py:877-885`：双循环所有 `d_in,d_out`，跳过 `d_out == d_in`。与推导的 12 个 belt 精确相等。
- L0 splitter 在 `src/models/routing_subproblem.py:887-895`：对每个 `d_in`，从 `D \ {d_in}` 选 `out_deg in (2,3)` 的组合。数量 `4 * (C(3,2)+C(3,3)) = 16`，与推导相等。
- L0 merger 在 `src/models/routing_subproblem.py:897-905`：对每个 `d_out`，从 `D \ {d_out}` 选 `in_deg in (2,3)` 的组合。数量 `16`，与推导相等。

本轮 probe 对实现集合和独立 expected set 做 set equality，结果：

```text
pattern_counts {0: {'merger': 16, 'splitter': 16, 'belt': 12}, 1: {'bridge': 4}}
```

结论：没有发现漏枚举合法 pattern，也没有发现多枚举非法 pattern；splitter / merger 的组合数学与实现一致。

### Q3.3 component_type 与下游消费一致性

`component_type` 下游消费路径：

- `_create_routing_variables()` 把 `component_type` 保存到 `_state_meta`，见 `src/models/routing_subproblem.py:969-973`。
- L1 bridge 的物理约束主要按 layer 收集到 `_l1_vars`，见 `src/models/routing_subproblem.py:981-982`。
- L0 非直线状态按 `component_type != 'belt' or not _is_straight_state(...)` 收到 `_l0_nonstraight_vars`，见 `src/models/routing_subproblem.py:983-984`。
- `_add_bridge_constraints()` 若同格有 L1，则禁止 L0 non-straight，只允许 L0 empty 或 straight belt，见 `src/models/routing_subproblem.py:1031-1042`，与 09 章直桥跨 straight belt 规则一致。
- continuity、edge balance、guard 都消费 `flow_in` / `flow_out`，不把 `component_type` 当作 reachability 语义来源。这是正确的，因为连通性只由 directed sides 决定。
- `extract_routes()` 输出 `component_type` 作为 blueprint metadata，见 `src/models/routing_subproblem.py:1856-1863`。

结论：pattern 的 `component_type` 标注与 guard / extract / edge-balance / bridge-overlap 消费假设一致。

## 最终状态

本轮没有补丁。

**本轮零 soundness finding。**
