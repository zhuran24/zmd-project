# 终末地 IndustrialPlanner routing face round 7 review

审查对象：`zmd_snapshot_37b84be0.zip`

快照校验：通过。

```text
37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd  /mnt/data/zmd_snapshot_37b84be0.zip
```

环境：Python 3.13.5 venv，依赖由 `zmd_py313_linux_x86_64.zip` 离线安装；核心求解依赖确认使用 `ortools 9.15.6755`。

## 总结论

**本轮零 soundness finding。**

本轮未发现需要修改 `src/models/routing_subproblem.py`、routing precheck 生产者、或 full routing 接受边界的 soundness 问题；因此不提供代码补丁。

审查范围限定为题面指定的 routing 编码面：Q1 CP-SAT 约束本体、Q2 routing precheck 生产者/消费点、Q3 自由攻击角。PCR patch 模型、cuts 面、binding/master 几何面未作为本轮 finding 来源重复报告。

## Finding 列表

无。

## 复现实证

### 专项 probe

一次性 probe：`/mnt/data/zmd_r7_audit/routing_r7_probe.py`。覆盖：独立 pattern 集合等价、每个 `r_var` 的 capacity/index/bridge 分类完整性、source/sink terminal ground-side 例外、terminal 例外不外溢到 L1、source-front merger 的非 terminal 输入仍必须有 predecessor、directed edge balance 阻止 L0/L1 单边重复通道、grid 路径与 placement-core 路径 precheck 口径一致。

命令：

```bash
cd /mnt/data/zmd_r7_audit/project
source /mnt/data/zmd_r7_venv/bin/activate
PYTHONPATH=. python /mnt/data/zmd_r7_audit/routing_r7_probe.py
```

输出：

```text
[Routing Model] build 0.0s
patterns_ok {'belt': 12, 'splitter': 16, 'merger': 16, 'bridge': 4} indexed_vars 12
[Routing Model] build 0.0s
[Routing Model] build 0.0s
terminal_boundaries_ok
[Routing Model] build 0.0s
edge_balance_and_precheck_ok
```

### 专项 pytest

命令 1：

```bash
cd /mnt/data/zmd_r7_audit/project
source /mnt/data/zmd_r7_venv/bin/activate
python -m pytest -q -p no:randomly \
  src/tests/test_routing.py::test_sink_front_consumes_against_outward_normal_on_straight_corridor \
  src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel \
  src/tests/test_routing.py::test_port_connector_cell_cannot_be_reused_as_routing_cell \
  src/tests/test_routing.py::test_external_domain_analysis_cannot_route_through_occupied_cell \
  src/tests/test_routing.py::test_same_commodity_disconnected_source_sink_islands_are_routable \
  src/tests/test_routing.py::test_duplicate_terminal_front_keys_fail_closed \
  src/tests/test_routing.py::test_exact_routing_precheck_flags_front_blocked \
  src/tests/test_routing.py::test_exact_routing_precheck_flags_relaxed_disconnected \
  src/tests/test_routing.py::test_terminal_aware_peeling_prunes_non_terminal_dead_end_branch \
  src/tests/test_routing.py::test_elevated_bridge_states_require_opposite_neighbors \
  src/tests/test_routing.py::test_routing_placement_core_precheck_matches_grid_path
```

结果：

```text
11 passed in 1.11s
```

命令 2：

```bash
cd /mnt/data/zmd_r7_audit/project
source /mnt/data/zmd_r7_venv/bin/activate
python -m pytest -q -p no:randomly \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_feasible_incumbent_requires_source_to_sink_connectivity \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_timeout_does_not_expose_rejected_routes \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_checks_each_selected_commodity \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cuts_converge_on_three_commodity_probe \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_preserves_real_feasible_path \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_self_check_falls_back_to_nogood \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_rejects_source_front_without_sink_reachability \
  src/tests/test_p0_certified_soundness_fixes.py::test_front_blocked_safe_reject_enumerates_binding_before_master_cut
```

结果：

```text
8 passed in 1.40s
```

### proof obligations

命令：

```bash
cd /mnt/data/zmd_r7_audit/project
source /mnt/data/zmd_r7_venv/bin/activate
python scripts/check_p1_2_proof_obligations.py
```

结果：

```text
P1.2 proof obligation check passed: 8 obligations anchored
```

### 未完成的全量/宽集说明

我没有完成全量 `python -m pytest -q src/tests`。先尝试过较宽的 routing 相关 pytest 集合以及单文件 `src/tests/test_routing.py`，均在 300s 沙盒限时处中止；中止前只输出进度点，没有 failure 摘要。上面的结论基于静态逐行审查、专项 probe、专项 pytest 与 proof-obligation 脚本。

## Q1：从 specs 独立推导的 CP-SAT 约束族清单与逐族对照

规格来源：`specs/09_exact_grid_routing_subproblem.md` §9.2-9.4、§9.7-9.8，以及 `specs/03_rule_canonicalization.md:306-344` 的传送带 / 物流桥 / splitter / merger 规则。

### 1. 状态域与 pattern 封闭集

应有约束族：

- L0 ground route state：12 个基础 belt pattern，即单输入、单输出，`d_in != d_out`，覆盖 4 直 + 8 弯；来自 `specs/03_rule_canonicalization.md:306-317`。
- L0 splitter：1 进多出，建模中按容量节点处理；实现允许 1 进 2 出与 1 进 3 出，用以支持多 sink pooling，来自 `specs/03_rule_canonicalization.md:329-336`。
- L0 merger：多进 1 出，建模中按容量节点处理；实现允许 2 进 1 出与 3 进 1 出，来自 `specs/03_rule_canonicalization.md:338-344`。
- L1 elevated bridge：只允许直线，不能转弯；来自 `specs/09_exact_grid_routing_subproblem.md:51-55` 与 `specs/03_rule_canonicalization.md:318-327`。

实现对照：

- `src/models/routing_subproblem.py:867-905` 的 `_iter_state_patterns()` 精确生成 L0 belt 12、splitter 16、merger 16、L1 bridge 4，总计 48 个 pattern。
- L1 pattern 固定 `flow_out = DIR_OPP[d_in]`，见 `src/models/routing_subproblem.py:868-875`，因此 bridge 不可能转弯。
- 专项 probe 独立重建 pattern 集合并做 set equality，输出 `{'belt': 12, 'splitter': 16, 'merger': 16, 'bridge': 4}`。

结论：pattern 状态封闭集与规格一致，未发现遗漏状态导致 false-INFEASIBLE，也未发现多余转弯 bridge / U-turn belt 导致 false-FEASIBLE。

### 2. obstacle/domain exclusion

应有约束族：solid obstacle 不得铺任何 L0/L1 route state，见 `specs/09_exact_grid_routing_subproblem.md:43-45`。

实现对照：

- 普通 `RoutingGrid` 只把未占据格放入 `free_cells`，见 `src/models/routing_subproblem.py:675-679`。
- `RoutingPlacementCore.from_occupied_cells()` 同样先构造 70×70 的 `free_cells`，见 `src/models/routing_subproblem.py:53-63`。
- precheck 解析时统一减去 port connector cells：placement-core 路径见 `src/models/routing_subproblem.py:332-361`，grid 路径见 `src/models/routing_subproblem.py:363-382`。
- build 绑定外置 domain 时再次与 `set(self.grid.free_cells) - port_connector_cells` 求交，见 `src/models/routing_subproblem.py:845-859`。
- `_add_obstacle_exclusion()` 不再加显式线性约束，因为变量只在 active free cells 上创建，见 `src/models/routing_subproblem.py:1022-1024`。

结论：occupied / out-of-grid / connector 三类不可铺格不会生成 route state。外置 stale `domain_analysis` 不能把 occupied/connector 穿回变量域。

### 3. capacity AtMostOne per `(cell, layer)`

应有约束族：每个 cell-layer 最多一个 route component / commodity / direction pattern，见 `specs/09_exact_grid_routing_subproblem.md:47-49`。

实现对照：

- 每个 route var 创建后立即加入 `_vars_by_cell_layer[(x, y, layer)]`，见 `src/models/routing_subproblem.py:964-980`，没有其它 `r_vars` 创建点。
- `_add_capacity_constraints()` 对每个 cell-layer 列表加 `AddAtMostOne`，见 `src/models/routing_subproblem.py:1026-1030`。
- 专项 probe 对每个 `r_var` 反查其 cell-layer bucket，未发现漏入。

结论：全部 state var 都进入对应 cell-layer capacity bucket。L0 与 L1 可在同一 2D cell 共存，但各自层内最多一个 state，符合双层物理模型。

### 4. bridge 共存约束

应有约束族：L1 bridge 只能直线；若同格有 L1 bridge，则 L0 要么为空，要么是 straight belt；见 `specs/09_exact_grid_routing_subproblem.md:51-55`。

实现对照：

- L1 只生成 straight bridge pattern，见 `src/models/routing_subproblem.py:868-875`。
- straight 判据 `_is_straight_state()` 是 `len(flow_in) == len(flow_out) == 1` 且 `flow_out == Opp(flow_in)`，见 `src/models/routing_subproblem.py:93-98`。
- `_create_routing_variables()` 对所有 L1 var 记录 `_l1_vars[(x, y)]`，对所有 L0 非 straight belt 记录 `_l0_nonstraight_vars[(x, y)]`，见 `src/models/routing_subproblem.py:981-984`。
- `_add_bridge_constraints()` 建 `l1_any = max(l1_vars)`，并对每个 L0 nonstraight var 加 `l1_any -> not var`，见 `src/models/routing_subproblem.py:1031-1042`。
- L0 empty 合法：实现只禁止 L0 nonstraight 与 L1 共存，没有要求 L0 必选。

结论：bridge 共存约束与规格一致。straight 判据不把 splitter/merger 算作 straight；L0 empty 被允许；未发现 false-FEASIBLE。

### 5. continuity：successor / predecessor

应有约束族：每个被选中的 state 的每个 `flow_out` 必须有邻格接收者；每个被选中 state 的每个 `flow_in` 必须有前驱发送者。source ground side 无 predecessor，sink ground side 无 successor；非 terminal side 不得被豁免。见 `specs/09_exact_grid_routing_subproblem.md:57-60` 与 §9.7 的 selected graph 语义。

实现对照：

- `_add_continuity_constraints()` 对每个 commodity、active cell、layer、四方向分别调用 successor 与 predecessor，见 `src/models/routing_subproblem.py:1059-1066`。
- successor：取当前 cell/layer/direction 的 out vars；若是 ground sink terminal side，直接返回；否则邻格不在 active domain、邻格 source terminal side、或无 receiver vars 时，逐个 `var == 0`；有 receiver vars 时，对每个 out var 加 `sum(recv_vars) >= 1 OnlyEnforceIf(var)`，见 `src/models/routing_subproblem.py:1120-1156`。
- predecessor：取当前 cell/layer/direction 的 in vars；若是 ground source terminal side，直接返回；否则前格不在 active domain、前格 sink terminal side、或无 sender vars 时，逐个 `var == 0`；有 sender vars 时，对每个 in var 加 `sum(send_vars) >= 1 OnlyEnforceIf(var)`，见 `src/models/routing_subproblem.py:1158-1194`。
- `sum(BoolVars) >= 1 OnlyEnforceIf(var)` 与“若该 side 所属 state 被选中，则至少一个兼容邻接 state 被选中”语义等价。空邻接集合走 `var == 0`，不是 vacuous true。
- 邻接 receiver/sender bucket 是 layer-agnostic 的 `_vars_by_cell_dir_in_commodity` / `_vars_by_cell_dir_out_commodity`，见 `src/models/routing_subproblem.py:977-980`。这与 bridge 无需额外起降格的跨层接驳一致。
- terminal 例外边界精确：source 例外仅 `layer == GROUND_LAYER` 且 matching source side，见 `src/models/routing_subproblem.py:1170-1171`；sink 例外仅 `layer == GROUND_LAYER` 且 matching sink side，见 `src/models/routing_subproblem.py:1132-1133`。专项 probe 证明 source-front 的 L1 同向 state 不被 source 例外支持，实际不生成；source-front merger 的 source side 可无 predecessor，但其额外 `N` 输入仍必须有 predecessor，否则原始 CP-SAT model `INFEASIBLE`。

结论：successor/predecessor 的 Add/OnlyEnforceIf 形态与“必须接续”语义等价；terminal 例外没有扩散到 L1 或同格其它非 terminal side。

### 6. per-edge channel conservation

应有约束族：对每条有向 cell-to-cell edge，同 commodity 的发送通道数必须等于接收通道数，避免一个 sender 被 L0/L1 两个 receiver 同时消费，或反向 phantom merger/splitter。该约束是 F-RT-R2-02 修复本体。

实现对照：

- `_add_directed_edge_balance_constraints()` 遍历每个 commodity、active cell、四方向，跳过 source/sink terminal connector side 后，对 `send_vars = _vars_by_cell_dir_out_commodity[(x,y,d,k)]` 与 `recv_vars = _vars_by_cell_dir_in_commodity[(nx,ny,Opp(d),k)]` 加 `sum(send_vars) == sum(recv_vars)`，见 `src/models/routing_subproblem.py:1068-1118`。
- 发送/接收 bucket 在变量创建时对每个 `flow_out` / `flow_in` direction 都 append，见 `src/models/routing_subproblem.py:975-980`。因此 belt、splitter、merger、terminal-front ground state、bridge endpoint 都进入相应 edge 计数；terminal connector side 由 `_add_port_adherence()` 单独精确处理，见 `src/models/routing_subproblem.py:1081-1084`。
- edge balance 故意不含 layer，统计的是 cell-to-cell side channel 数；跨层接驳是否合法由 continuity + bridge mechanics 决定。
- 专项 probe 复现 `src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel` 的攻击形态：同一 directed edge 上一个发送端试图同时支撑 L0 与 L1 接收端，原始 CP-SAT model 返回 `INFEASIBLE`。

结论：per-edge channel conservation 的量化范围覆盖 commodity × all layer × all state side，没有发现 terminal/bridge 端点漏计。

### 7. port adherence exact-one

应有约束族：每个 source/sink physical front 必须在 ground layer 恰好履行一次。source port 要求 front cell 有一个 state 从 `Opp(port_dir)` 方向接收；sink port 要求 front cell 有一个 state 向 `Opp(port_dir)` 方向输出。见 `specs/09_exact_grid_routing_subproblem.md:67-75`。

实现对照：

- `_index_port_fronts()` 对 source 记录 `(front_x, front_y, recv_dir, commodity)`，对 sink 记录 `(front_x, front_y, send_dir, commodity)`，见 `src/models/routing_subproblem.py:786-799`。
- `_add_port_adherence()` 对每个 `port_spec` 逐条处理；front 不在 active domain 时直接 `0 == 1`；source exact-one 使用 ground layer `_vars_by_cell_layer_dir_in_commodity[(front, 0, recv_dir, commodity)]`；sink exact-one 使用 ground layer `_vars_by_cell_layer_dir_out_commodity[(front, 0, send_dir, commodity)]`；见 `src/models/routing_subproblem.py:1196-1237`。
- 变量集语义是“direction ∈ `flow_in` / `flow_out` 的全部 ground state”，所以 splitter / merger state 只要包含该 terminal side，就算履行该端口。结合 per-cell-layer AtMostOne，每个 port front 的履行仍是一个 ground component。此口径与 splitter/merger “特殊传送带节点 / 容量节点”抽象一致，见 `specs/03_rule_canonicalization.md:331-344`。
- `_duplicate_terminal_front_keys()` 对相同 `(front, terminal_dir, commodity, type)` 的多 physical port fail-closed，避免两个 physical ports 共用一条 exact-one row 导致 multiplicity collapse；见 `src/models/routing_subproblem.py:136-186` 与 build 中的 `src/models/routing_subproblem.py:814-816`。

结论：source/sink front exact-one 的量化集合与当前 pooling / capacity-node 口径一致；splitter/merger 含该方向时正确计入履行；重复 terminal key fail-closed。

### 8. 1-cell minimum gap 与 final connectivity guard

应有约束族：机器之间不得零距离硬连，必须经过至少一个 free logistics front cell；见 `specs/03_rule_canonicalization.md:290-304` 与 `specs/09_exact_grid_routing_subproblem.md:61-64`。局部 continuity 之外，最终 acceptance 还必须证明 source→sink reachability；见 `specs/09_exact_grid_routing_subproblem.md:100-128`。

实现对照：

- port 语义始终是 connector cell + outward dir 得到 front cell，routing vars 活在 front cell 而不是 connector cell，见 `_port_connector_cells()` 注释 `src/models/routing_subproblem.py:120-126` 与 `_add_port_adherence()` 的 front 计算 `src/models/routing_subproblem.py:1200-1206`。
- `_add_gap_rule()` 记录该规则由 front-cell model 与 placement port-clearance 处理，见 `src/models/routing_subproblem.py:1239-1242`。
- `solve()` 只有在 CP-SAT incumbent 通过 `_validate_selected_route_connectivity()` 后才返回 `FEASIBLE`，见 `src/models/routing_subproblem.py:1773-1789`；guard 失败则添加 self-checked source-side cut 或 fallback selected-route nogood 后继续，见 `src/models/routing_subproblem.py:1791-1826`。
- `extract_routes()` 要求 CP-SAT status 是 feasible/optimal 且 `_connectivity_guard_accepted` 为 true，否则返回空，见 `src/models/routing_subproblem.py:1844-1849`。

结论：CP-SAT 局部约束与 post-solve guard 共同构成当前规格要求的 full routing acceptance boundary。

## Q2：routing precheck 生产者本体与消费点全扫

### Q2.1 producer 口径

`analyze_exact_routing_domain()` / `run_exact_routing_precheck()` 的生产口径如下：

- `_resolve_routing_domain_context()` 接受 `RoutingGrid` 或 `RoutingPlacementCore`，复制 selected `port_specs`，收集 connector cells，并统一使用 `resolved_free_cells = free_cells - port_connector_cells`，placement-core 路径见 `src/models/routing_subproblem.py:325-361`，grid 路径见 `src/models/routing_subproblem.py:363-382`。
- duplicate terminal front key 直接返回 `front_blocked` 且 `binding_selection_safe_reject=True`，见 `src/models/routing_subproblem.py:398-417`。
- 普通 `front_blocked` 条件是 front out-of-grid 或 front 不在 `resolved_free_cells`，见 `src/models/routing_subproblem.py:424-459`；若存在 blocked port，汇总 conflict ids 后返回 `front_blocked`，见 `src/models/routing_subproblem.py:476-494`。
- `relaxed_disconnected` 使用 `resolved_free_cells` 的 undirected connected components，要求每个 same-commodity component 至少同时含 source front 与 sink front；多岛同商品只要每个岛都有 source/sink 就允许 pooling/existence，见 `src/models/routing_subproblem.py:500-573` 与 `src/tests/test_routing.py:261-297`。
- active-domain shrink 使用 `_peel_terminal_core()` 去掉非 terminal dead-end leaves，见 `src/models/routing_subproblem.py:248-289`；它只删除不可能位于任何 terminal-to-terminal path 上的非 terminal 叶子。
- `domain_stats` 来自同一 `commodity_component_cells` / `commodity_active_cells`，见 `src/models/routing_subproblem.py:575-630`。

结论：precheck 生产的 free/component/active 口径与 build 端 `_bind_domain_analysis()` 的 `grid.free_cells - connector` 求交口径同源。

### Q2.2 front_blocked 误报/漏报后果链

- 若 producer 报 `front_blocked`：相对于当前 routing CP-SAT 域，它不是“实际可达但误报”。front 不在 `resolved_free_cells` 或 terminal key 重复时，build 端也会 fail-closed：duplicate key 在 `src/models/routing_subproblem.py:814-816` 加 `0 == 1`；front 不在 active domain 时 `_add_port_adherence()` 在 `src/models/routing_subproblem.py:1207-1210` 加 `0 == 1`。
- 在 LBBD 消费侧，`front_blocked` 不直接返回 certified INFEASIBLE。若有 binding alternatives，先加 binding-local nogood 并重解，见 `src/search/benders_loop.py:5325-5379`。无 alternatives 时进入 front_blocked cut ladder，见 `src/search/benders_loop.py:5381-5701`；有 cut 才继续 master，无 cut 则 `RUN_STATUS_UNKNOWN`，见 `src/search/benders_loop.py:5680-5701`。
- 若 producer 漏报 blocked 而返回 feasible：后续会构建 full `RoutingSubproblem` 并运行 CP-SAT；port adherence / continuity / capacity 会给出 `INFEASIBLE`、或在预算不足时 `TIMEOUT`，不会 false-certify。主循环对 routing `TIMEOUT` 返回 `RUN_STATUS_UNKNOWN`，见 `src/search/benders_loop.py:5800-5838`；非契约状态也 fail-closed 为 unknown，见 `src/search/benders_loop.py:5840-5858`。

结论：front_blocked 的漏报是性能/搜索后移；没有发现 false-FEASIBLE。front_blocked 的消费侧没有裸用 precheck 结论直接产出 candidate-wide infeasibility certificate。

### Q2.3 relaxed_disconnected 消费点

`relaxed_disconnected` 与 `front_blocked` 的消费不同：它可以在 binding alternatives 耗尽后进入 `routing_exhausted_nogood` whole-layout cut 路径，见 `src/search/benders_loop.py:5703-5741` 与 `src/search/benders_loop.py:5941-5972`。

我认为这不是 soundness finding，理由是 `relaxed_disconnected` 是 full routing 的必要条件证明，而不是启发式猜测：如果 source/sink fronts 位于不同 `free_cells - connector` undirected components，L0 belt、L1 bridge、splitter、merger 都只能占用这些 free cells 并通过四邻接 continuity 连接；bridge 不能跨 solid cell 或 port connector cell“跳跃”。因此 CP-SAT 不可能在这些 components 之间构造 selected route-state path。该证明口径比后续 build active domain更宽；在更宽图上都断开，则 shrink 后更不可能连通。

### Q2.4 domain_stats / connected component 与 build 求交宽窄后果

- 生产路径中，precheck `_analysis` 直接作为 `domain_analysis` 传给 `RoutingSubproblem.from_placement_core()`，见 `src/search/benders_loop.py:5275-5303` 与 `src/search/benders_loop.py:5757-5780`。
- build 端 `_bind_domain_analysis()` 对 raw component/active cells 再次与 `set(self.grid.free_cells) - port_connector_cells` 求交，见 `src/models/routing_subproblem.py:845-859`。
- 若外置或 stale analysis 比 build 域宽：occupied / connector / out-of-grid 会被裁掉；可能让本次 build 更快地 `INFEASIBLE`，但不会 false-FEASIBLE。R5 回归 `src/tests/test_routing.py:230-258` 与本轮 probe 覆盖了 occupied/stale 域裁剪。
- 若外置 analysis 被手工改得比 producer 域窄：`RoutingSubproblem` 会按窄域建模，理论上可能造成 false-INFEASIBLE。生产路径未发现这种窄化来源；producer 的 `_peel_terminal_core()` 只剪非 terminal leaves，本轮按图论重新审过，未发现会删除 terminal-to-terminal simple path 必需 cell 的情况。

结论：生产路径上 precheck 域与 build 域同源，build 端额外求交是 fail-closed 防 stale 宽域；没有发现由 domain_stats/component 口径不一致导致的 false-FEASIBLE。

### Q2.5 precheck 与 binding 选择时序

主循环在 `binding_status == "FEASIBLE"` 后，先 `selection = binding_model.extract_selection()`，再 `port_specs = binding_model.extract_port_specs()`，见 `src/search/benders_loop.py:5244-5247`。`extract_port_specs()` 内部也从当前 solver incumbent 的 `extract_selection()` 生成被选 binding/generic slots 的 ports，见 `src/models/binding_subproblem.py:1007-1073`。

precheck 调用发生在这组 selected `port_specs` 之后，见 `src/search/benders_loop.py:5275-5303`。因此本轮没有发现“precheck 用 binding 选择前 port 全集导致高估需求”的路径。

### Q2.6 全仓消费点扫描结论

`rg "front_blocked|relaxed_disconnected|run_exact_routing_precheck|binding_selection_safe_reject" src -S` 的实质消费点：

- `src/search/benders_loop.py`：certified LBBD 主消费点。front_blocked 走 binding-local reject 或 cut ladder；relaxed_disconnected 走 binding-local reject，binding exhausted 后 whole-layout nogood；routing TIMEOUT/异常状态 fail-closed。
- `src/search/heuristic_feasible_finder.py:145-209`：best-effort verifier。这里 front_blocked / relaxed_disconnected 直接返回 `INFEASIBLE`，但注释明确是 best_effort 语义、不加 nogood，见 `src/search/heuristic_feasible_finder.py:152-154` 与 `src/search/heuristic_feasible_finder.py:180-184`。它不是 certified proof producer。
- `src/search/campaign_triage.py`、`src/search/campaign_telemetry.py`：仅做分类/telemetry。
- `src/search/routing_deletion_core_minimizer.py`、`src/models/pose_bool_exact_master.py`、`src/models/binding_subproblem.py` 中的 front-blocked 相关逻辑属于 cuts/binding-aware 其它面；本轮未重开为 routing full model finding。

结论：未发现 precheck 结论被裸用为 certified candidate-wide INFEASIBLE 的消费点。

## Q3：自由攻击角

### 攻击角 A：solve loop 的 incumbent / cut / TIMEOUT 边界

选择原因：局部 CP-SAT 可行不等于全局 routable，`solve()` 的 guard 循环是 certified acceptance 的最后门闩；这里若有 stale incumbent、TIMEOUT 后 extract、或 cut 失败放行，会直接 false-CERTIFIED。

攻击过程：

- 审查 `solve()`：每次 CP-SAT `OPTIMAL/FEASIBLE` 后立即调用 `_validate_selected_route_connectivity()`，见 `src/models/routing_subproblem.py:1773-1775`。
- guard 通过时才设置 `_connectivity_guard_accepted=True` 并返回 `FEASIBLE`，见 `src/models/routing_subproblem.py:1777-1789`。
- guard 失败时，不返回；先尝试 `_add_source_side_connectivity_cut()`，其 self-check 失败则 fallback `_add_selected_route_nogood()`，见 `src/models/routing_subproblem.py:1791-1826`。
- 若 guard reject 后耗尽预算，显式 `self._solver = None`、`self._status = UNKNOWN` 并返回 `TIMEOUT`，见 `src/models/routing_subproblem.py:1737-1753`。
- `extract_routes()` 双重检查 solver status 与 `_connectivity_guard_accepted`，见 `src/models/routing_subproblem.py:1844-1849`。
- 专项 pytest 覆盖 rejected incumbent、guard timeout 不暴露 routes、多 commodity guard、lazy cut self-check fallback 与 source-front-without-sink 等路径，8 项全过。

结论：未发现 rejected incumbent 越过 guard、TIMEOUT 暴露 stale witness、或 self-check 失败仍添加未证 cut 的路径。

### 攻击角 B：extract_routes 输出对 blueprint 的保真与“额外闭环”

选择原因：即使 solve acceptance sound，输出层如果从非 solver-key 数据重建路线、丢 layer/flow、或在 TIMEOUT 后吐旧解，会污染后续 blueprint。

攻击过程：

- `extract_routes()` 只遍历 `self.r_vars.items()`，并用 `self._solver.Value(var) == 1` 选中 state，见 `src/models/routing_subproblem.py:1851-1854`；不是从日志、build_stats、precheck 或 guard diagnostics 重建。
- 输出保留 `x/y/layer/commodity/component_type/flow_in/flow_out`，单输入/单输出时额外给 `dir_in/dir_out`，见 `src/models/routing_subproblem.py:1855-1869`。这些字段直接来自 route-state key 与 `_state_meta`，没有二次推断方向。
- TIMEOUT / INFEASIBLE / guard 未接受时返回空，见 `src/models/routing_subproblem.py:1844-1849`。
- 额外闭环攻击：当前 guard 不要求所有 selected states 都从 source reachable；理论上 CP-SAT 可选择一段与 terminals 无关的闭合环。但这不是 false feasibility：删除这些额外 selected states 只会释放 capacity/bridge constraints，不会破坏已由 guard 证明的 source→sink routes。它可能影响蓝图简洁度，但不影响“存在可行 routing”的 certification soundness。本轮不作为 soundness finding。

结论：extract_routes 不存在 stale witness 或字段重建失真；额外闭环不是本轮 soundness 问题。

### 攻击角 C：外置 `domain_analysis` 信任边界

选择原因：R5 修复的是 stale 宽域穿墙；本轮换角度看“生产者 `_analysis` 与消费者 build 的信任边界”。

攻击过程：

- 宽域攻击：把 occupied cell、connector cell、out-of-grid cell 塞进 external `domain_analysis`。`_bind_domain_analysis()` 通过 `grid.free_cells - connector` 裁掉，见 `src/models/routing_subproblem.py:845-859`；专项 probe 与既有回归均通过。
- 窄域攻击：若外部手工传入过窄且 status=feasible 的 `domain_analysis`，build 会按窄域建变量，可能导致 false-INFEASIBLE。生产路径中没有发现这种手工窄化来源；`benders_loop` 传入的是同一轮 precheck 返回的 `_analysis`，见 `src/search/benders_loop.py:5302` 与 `src/search/benders_loop.py:5763-5768`。
- producer 自身唯一窄化是 `_peel_terminal_core()`。该算法只反复剥离非 terminal 且当前 degree < 2 的 leaf，见 `src/models/routing_subproblem.py:269-289`；任意连接两个 terminal 的 simple path 不会使用被剥掉的非 terminal leaf。因此 shrink 不删除必需 routing corridor。

结论：生产路径 sound；外部恶意/错误传入 too-narrow `domain_analysis` 是 API 信任边界问题，不是当前 master→binding→precheck→routing 生产链 soundness finding。
