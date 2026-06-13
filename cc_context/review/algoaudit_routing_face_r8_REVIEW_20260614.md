# IndustrialPlanner routing 面 round 8 真 Pro 重审 REVIEW

## 0. 结论

本轮零 soundness finding。

我只审查并解包了指定快照 `zmd_snapshot_f4418b04.zip`，其 sha256 校验为：

```text
f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1  /mnt/data/zmd_snapshot_f4418b04.zip
```

依赖包通过 `zmd_py313_linux_x86_64.zip` 离线安装到 Python 3.13 venv。`data/preprocessed/candidate_placements.json` 为测试补全而重新生成，结果匹配项目要求：

```text
adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0  data/preprocessed/candidate_placements.json
size = 45,773,799 bytes
```

本轮没有代码补丁，也没有 regression patch。以下为逐项 soundness 复核与实证 probe。

## 1. Findings

无。

## 2. 约束本体忠实度复核（Q1-Q6）

### Q1 方向 / 极性编码

规则独立推导：`port_specs[*].dir` 是从物理 connector cell 指向 routing front cell 的 outward normal。若 output/source 端口在 connector cell 向 front 注入物料，则 front cell 的 route-state 必须从 connector 侧流入，即 `flow_in = Opp(dir)`；若 input/sink 端口从 front 回收物料，则 front cell 的 route-state 必须向 connector 侧输出，即 `flow_out = Opp(dir)`。

代码在 `_index_port_fronts()` 中对 source 使用 `recv_dir = DIR_OPP[direction]`，对 sink 使用 `send_dir = DIR_OPP[direction]`（`src/models/routing_subproblem.py:786-799`）。消费点保持同一规则：`_add_port_adherence()` source 查 ground-layer `flow_in=Opp(dir)`，sink 查 ground-layer `flow_out=Opp(dir)`（`src/models/routing_subproblem.py:1196-1237`）；cell-to-cell successor / predecessor 也通过 `recv_dir = DIR_OPP[d_out]`、`send_dir = DIR_OPP[d_in]` 对接（`src/models/routing_subproblem.py:1142-1148`, `src/models/routing_subproblem.py:1180-1186`）；directed edge balance 用同一 Opp 映射（`src/models/routing_subproblem.py:1099-1113`）。

实证 probe 覆盖了 3-cell 直 corridor：source `(0,0,E)` 的 front `(1,0)` 选中 `flow_in=['W']`，sink `(4,0,W)` 的 front `(3,0)` 选中 `flow_out=['E']`，并且 `solve()` 返回 `FEASIBLE`。

### Q2 directed edge balance 的 terminal 例外边界

`_add_directed_edge_balance_constraints()` 对每个 commodity、每个非 terminal cell-to-cell directed edge 加 `sum(send_vars) == sum(recv_vars)`（`src/models/routing_subproblem.py:1068-1118`）。跳过边界恰好对应 terminal side：当前 cell 的 sink-facing side 是 front→connector，不是 cell-to-cell edge（`src/models/routing_subproblem.py:1092-1093`）；目标 cell 的 source-facing side 是 connector→front，也不是 cell-to-cell edge（`src/models/routing_subproblem.py:1099-1101`）。若邻格不在 active cells，则该方向不是 modeled interior edge，continuity 侧会把对应 state 置零（`src/models/routing_subproblem.py:1095-1097`, `src/models/routing_subproblem.py:1135-1146`, `src/models/routing_subproblem.py:1173-1184`）。

这与 port adherence 衔接无空洞：terminal side 由 exact-one 端口约束负责，ordinary side 由 predecessor/successor 加 per-edge equality 负责。已覆盖历史 bridge overlap 隐形 splitter/merger：局部 `>=1` 只提供存在性支撑，而 directed edge equality 防止一个 sender 同时支撑 ground 与 elevated 两个 receiver。

### Q3 connector 占用与 terminal-side 两层锁

connector cell 集合由 `_port_connector_cells()` 直接取 in-grid `(port.x, port.y)`（`src/models/routing_subproblem.py:120-133`）。域解析在 placement-core 路径和 grid 路径都执行 `free_cells - port_connector_cells`，并重新计算 components（`src/models/routing_subproblem.py:332-363`, `src/models/routing_subproblem.py:373-381`）。外置 `domain_analysis` 绑定时再次与 `grid.free_cells - port_connector_cells` 求交，且同时作用于 `commodity_component_cells` 与 `commodity_active_cells`（`src/models/routing_subproblem.py:841-859`）。

terminal side 的 belt-and-suspenders 也在：ordinary route state 不能送入 source connector side，不能从 sink connector side 接出，相关剪枝在 successor/predecessor 和 edge balance 中都存在（`src/models/routing_subproblem.py:1132-1146`, `src/models/routing_subproblem.py:1170-1184`, `src/models/routing_subproblem.py:1092-1101`）。

`RoutingGrid.routable_cells = free_cells | port_cells` 与 `RoutingGrid.neighbors()` 目前无 live proof consumer；`rg "routable_cells|\.neighbors\(" src/models src/search src/tests scripts specs` 只命中定义、该方法本身和测试 stub。此 stale API 没有进入当前 routing CP-SAT / guard / precheck 证明链。

### Q4 obstacle 域排除与外置域 clip

`_add_obstacle_exclusion()` 是 no-op，但当前证明路径的障碍排除来自“只在 active free cells 上创建 route-state”（`src/models/routing_subproblem.py:942-980`, `src/models/routing_subproblem.py:1022-1024`）。

外置域 hardening 覆盖了 F-RT-R5-01 的关键点：`_bind_domain_analysis()` 对 component 与 active 两套集合都执行 `& routable_domain_cells`，其中 `routable_domain_cells = set(self.grid.free_cells) - port_connector_cells`（`src/models/routing_subproblem.py:847-859`）。对正常 `RoutingGrid` / `RoutingPlacementCore.from_occupied_cells()`，`grid.free_cells` 只由 70×70 in-grid 且非 occupied 的格子构造（`src/models/routing_subproblem.py:47-85`, `src/models/routing_subproblem.py:660-704`），因此 occupied、connector、out-of-grid 三类 stale/malicious active cells 都不会生成 route-state。

实证 probe 注入了包含 source connector、sink connector、out-of-grid `(999,999)` 的 hostile `domain_analysis`，build 后这些 cell 均未出现在 `r_vars` 中，且 corridor 仍可行。

### Q5 pattern 封闭集

`_iter_state_patterns()` 的封闭集与 specs 对齐：

* L1 bridge：4 个 straight-only pattern，`flow_out = Opp(flow_in)`，无 turn / U-turn bridge（`src/models/routing_subproblem.py:867-875`; `specs/09_exact_grid_routing_subproblem.md:51-55`; `specs/03_rule_canonicalization.md:318-327`）。
* L0 belt：12 个 one-in/one-out pattern，排除 `d_out == d_in` 的 U-turn；保留 4 straight + 8 turn（`src/models/routing_subproblem.py:877-885`; `specs/03_rule_canonicalization.md:306-317`）。
* L0 splitter：16 个 pattern，即每个 input 下的 1-in-2-out 与 1-in-3-out，outputs 均不含 input side（`src/models/routing_subproblem.py:887-895`; `specs/03_rule_canonicalization.md:329-337`）。
* L0 merger：16 个 pattern，即每个 output 下的 2-in-1-out 与 3-in-1-out，inputs 均不含 output side（`src/models/routing_subproblem.py:897-905`; `specs/03_rule_canonicalization.md:338-345`）。

Probe 结果：L0 pattern count = 44，L1 pattern count = 4，总 route-state pattern count = 48；各集合满足上述 set predicates。这里 L0 的 44 = 12 + 16 + 16，总计 48 包含 L1 的 4 个 bridge pattern。

### Q6 cell-layer capacity

route-state `NewBoolVar` 的唯一创建点在 `_create_routing_variables()`（`src/models/routing_subproblem.py:964-980`）。同一代码块在创建后立即写入 `self.r_vars`、`self._state_meta`、`self._vars_by_cell_layer[(x,y,layer)]`，以及所有方向索引桶。`_add_capacity_constraints()` 对每个 `(cell, layer)` 桶添加 `AddAtMostOne`（`src/models/routing_subproblem.py:1026-1030`）。

`rg "NewBoolVar|r_vars\[|_vars_by_cell_layer\[" src/models/routing_subproblem.py` 只发现另一个 `l1_any` auxiliary BoolVar（`src/models/routing_subproblem.py:1039`），它是 bridge overlap helper，不是 route-state，不需要进入 cell-layer capacity 桶。

## 3. Guard + lazy cut soundness 复核（Q7）

### Guard 图语义与 CP-SAT 语义一致性

guard 从 solver 直接读取 selected `r_vars`，不是信任 `extract_routes()` 产物（`src/models/routing_subproblem.py:1258-1263`, `src/models/routing_subproblem.py:1591-1605`）。terminal nodes 只在 ground layer 识别：source front 是 selected state 的 `flow_in` 含 source terminal direction，sink front 是 selected state 的 `flow_out` 含 sink terminal direction（`src/models/routing_subproblem.py:1285-1309`）。这与 port adherence ground-only exact-one 一致（`src/models/routing_subproblem.py:1196-1237`）。

selected graph 的 adjacency 使用 `flow_out` 指向邻格、目标 state 的 `flow_in = Opp(flow_out)`，并且 sink terminal output 不继续扩展（`src/models/routing_subproblem.py:1311-1330`）。它与 CP-SAT 的 successor/predecessor 支撑同样是 layer-agnostic 的 cell-to-cell directed side 语义（`src/models/routing_subproblem.py:1120-1194`）。因此 guard 没有引入与 CP-SAT route-state 编码不同的连通定义。

### Pooling 判据

guard 对每个 commodity 检查：每个 expected source front 必须有 selected source node；每个 expected sink front 必须有 selected sink node；从所有 source nodes 出发，每个 sink front 至少被某个 source 到达；并且每个 source front 至少能到达某个 sink node（`src/models/routing_subproblem.py:1613-1667`）。这精确对应 specs/08 的全局 pooling，不要求 source-sink 硬配对，也不强压同 commodity 所有 terminal fronts 到同一连通分量（`specs/08_topological_flow_subproblem.md:23-37`, `specs/08_topological_flow_subproblem.md:88-92`; `PROJECT_LOCK.md:123`）。

### Fail-closed acceptance boundary

`solve()` 在 CP-SAT `OPTIMAL/FEASIBLE` 后必须通过 `_validate_selected_route_connectivity()` 才返回 `FEASIBLE`（`src/models/routing_subproblem.py:1728-1789`）。guard 拒绝的 incumbent 只会添加 self-checked lazy cut 或 fallback selected-positive nogood 后继续求解（`src/models/routing_subproblem.py:1791-1826`）。预算耗尽时，已有 guard rejection 的路径会清空 `_solver`、置 `_status=UNKNOWN` 并返回 `TIMEOUT`（`src/models/routing_subproblem.py:1737-1753`）。`extract_routes()` 还有 status + `_connectivity_guard_accepted` 双门闩（`src/models/routing_subproblem.py:1844-1870`）。

### lazy source-side cut 证书

`_add_source_side_connectivity_cut()` 先从 rejected incumbent 重算 W，然后生成 candidate graph crossing X，最后调用 `_self_check_source_side_connectivity_cut()`（`src/models/routing_subproblem.py:1535-1589`）。self-check 独立验证：

1. X 属于 potential graph（`src/models/routing_subproblem.py:1455-1458`）。
2. 每个 source front 在 W 中，且没有 sink candidate node 位于 W（`src/models/routing_subproblem.py:1460-1497`）。
3. 在完整 potential graph 中移除 X 后，从所有 source-front candidate states BFS，不可到达任何 sink-front candidate state（`src/models/routing_subproblem.py:1498-1527`）。
4. rejected incumbent selected set 与 X 不相交（`src/models/routing_subproblem.py:1528-1533`）。

任一证书失败都会 fallback selected-positive nogood，而不是附加 cut（`src/models/routing_subproblem.py:1565-1577`, `src/models/routing_subproblem.py:1813-1825`）。这与 `specs/09` 的 lazy cut addendum 完全同构（`specs/09_exact_grid_routing_subproblem.md:108-128`）并保持 acceleration-only：最终接受仍依赖 guard。

### r7 advisory：source-entry arcs

`_route_state_adjacency()` 作为 potential-graph oracle 时确实没有显式过滤“进入 source terminal side”的 arcs（`src/models/routing_subproblem.py:1311-1330`）。本轮复核结论仍是无 soundness 影响：source terminal side 的 predecessor cell 是 connector cell，而 connector cells 已在域解析与外置域绑定两处被剔除（`src/models/routing_subproblem.py:332-363`, `src/models/routing_subproblem.py:847-859`），因此当前 proof path 不会存在从 connector side 进入 source front 的 candidate route-state。即便将其视为 potential graph 的保守 over-approx，self-check 是在 over-approx 上证明 `X` 切断所有 source→sink；这只会让 cut 更难通过，不会让无效 cut 通过。

## 4. Precheck 三态消费 + benders r7 契约一致性复核（Q8）

### routing 端 status 集合

`analyze_exact_routing_domain()` 的可达 return status 为：

* duplicate terminal front key 或 blocked front：`front_blocked`（`src/models/routing_subproblem.py:398-417`, `src/models/routing_subproblem.py:476-494`）。
* terminal-bearing component 缺 source 或 sink counterpart：`relaxed_disconnected`（`src/models/routing_subproblem.py:531-597`）。
* 否则：`feasible`（`src/models/routing_subproblem.py:614-630`）。

`run_exact_routing_precheck()` 只包装这份 analysis 并透传 `status`（`src/models/routing_subproblem.py:633-654`）。`CONNECTIVITY_GUARD_TIMEOUT` 只出现在 routing solve `build_stats["last_solve"]`，不是 precheck status（`src/models/routing_subproblem.py:1737-1753`）。

Benders allowlist 为 `{"feasible", "front_blocked", "relaxed_disconnected"}`（`src/search/benders_loop.py:122-125`），与 routing 端当前实际 status 集合完全一致。Probe 通过三个小场景实证枚举了这三种 status，结果为 `['feasible', 'front_blocked', 'relaxed_disconnected']`。

### 异常与 TypeError 路径

非-`TypeError` 的 precheck 异常会合成为 `{"status":"ERROR", ...}`，随后因不在 allowlist 中 fail-closed UNKNOWN，且不 build routing、不加 cut（`src/search/benders_loop.py:5315-5320`, `src/search/benders_loop.py:5335-5346`, `src/search/benders_loop.py:5347-5393`）。

`TypeError` 被单独当作调用签名兼容 fallback：placement-core 调用 TypeError 后转 grid 路径，grid 带 `occupied_owner_by_cell` 调用 TypeError 后转不带 owner 的 legacy 调用（`src/search/benders_loop.py:5306-5334`）。若最终仍没有 precheck，代码会填一个 default feasible summary（`src/search/benders_loop.py:5349-5356`），但此时 `routing_domain_analysis = None`，后续 `RoutingSubproblem.build()` 会重新运行 production `analyze_exact_routing_domain()`，然后仍必须通过 CP-SAT + connectivity guard 才能返回 certified feasible（`src/search/benders_loop.py:5357`, `src/search/benders_loop.py:5836-5883`; `src/models/routing_subproblem.py:801-839`, `src/models/routing_subproblem.py:1728-1789`）。因此 current TypeError fallback 不会把本该 blocked 的布局直接认证为 feasible，也不会把 unknown precheck status 转译成 routing INFEASIBLE proof。

未来若 routing 新增第 4 个 status 且仍放在 `status` 字段里，benders allowlist 会 fail-closed 到 UNKNOWN（`src/search/benders_loop.py:5366-5393`）。一个“缺失 status 字段”的未来 payload 会命中当前默认 `"feasible"`，这不是当前 producer 可达路径；建议未来扩展 precheck schema 时把“status 必填”继续作为契约测试，但本轮不作为当前 soundness finding。

### front_blocked / relaxed_disconnected 消费

`binding_selection_safe_reject=True` 且 binding 仍有替代时，benders 先加 binding-level nogood 并重解 binding，不直接投影 master cut（`src/search/benders_loop.py:5406-5460`; `PROJECT_LOCK.md:134`）。`front_blocked` 的 master cut ladder 只在没有 binding 替代后进入（`src/search/benders_loop.py:5462-5782`）。`relaxed_disconnected` 同样先走 binding alternative 枚举，binding 耗尽后才进入 whole-layout nogood（`src/search/benders_loop.py:5784-5822`, `src/search/benders_loop.py:6022-6053`）。

`relaxed_disconnected` 的必要性成立：它在 `free_cells - port_connector_cells` 的更宽连通图上证明某个 terminal-bearing component 缺少 counterpart source 或 sink；之后 CP-SAT active-domain 只会收缩该图，不可能跨越实体障碍或 connector terminal cell 恢复连通（`src/models/routing_subproblem.py:500-573`）。因此 binding exhausted 后的 whole-layout nogood 仍基于 full routing 的必要条件，不是 heuristic timeout 或预算证书。

### 其它消费点

`heuristic_feasible_finder.py` 的 precheck short-circuit 是 best-effort verifier，不产生 proof cut 或 candidate-wide INFEASIBLE certificate（`src/search/heuristic_feasible_finder.py:145-209`）。`campaign_triage.py` / `campaign_telemetry.py` 只做分类/telemetry。`d2_separator.py` 只在 production routing precheck 已为同一 occupied grid + terminals 给出 `front_blocked` 或 `relaxed_disconnected` 时才允许 D2 继续；其它 status 返回 no-cut diagnostic（`src/search/d2_separator.py:203-223`, `src/search/d2_separator.py:261-292`）。未发现裸用 precheck 结论直接产 candidate-wide INFEASIBLE 证书的 live path。

## 5. 实证命令与结果

使用环境：Python 3.13.5，OR-Tools 9.15.6755，`pytest-randomly` 禁用。

```bash
sha256sum /mnt/data/zmd_snapshot_f4418b04.zip
python3.13 -m venv /mnt/data/zmd_r8_venv
source /mnt/data/zmd_r8_venv/bin/activate
python -m pip install --no-index --find-links /mnt/data/zmd_deps/.../wheels -r requirements.txt
python src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
stat -c %s data/preprocessed/candidate_placements.json
```

结果：snapshot sha256 与任务指定值一致；candidate artifact 再生成 sha256 与 size 均一致。

```bash
PYTHONPATH=$PWD python scripts/check_p1_2_proof_obligations.py
```

结果：`P1.2 proof obligation check passed: 8 obligations anchored`。

```bash
PYTHONPATH=$PWD pytest -q -p no:randomly \
  src/tests/test_routing.py::test_routing_grid_construction \
  src/tests/test_routing.py::test_routing_small_solve \
  src/tests/test_routing.py::test_routing_supports_splitter_state \
  src/tests/test_routing.py::test_sink_front_consumes_against_outward_normal_on_straight_corridor \
  src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel \
  src/tests/test_routing.py::test_port_connector_cell_cannot_be_reused_as_routing_cell \
  src/tests/test_routing.py::test_external_domain_analysis_cannot_route_through_occupied_cell \
  src/tests/test_routing.py::test_same_commodity_disconnected_source_sink_islands_are_routable \
  src/tests/test_routing.py::test_duplicate_terminal_front_keys_fail_closed
```

结果：`9 passed in 20.54s`。

```bash
PYTHONPATH=$PWD pytest -q -p no:randomly \
  src/tests/test_routing.py::test_packaging_battery_pose_binding_domain \
  src/tests/test_routing.py::test_crusher_sandleaf_pose_binding_domain \
  src/tests/test_routing.py::test_generic_hub_binding_is_not_locally_enumerable
```

结果：`3 passed in 4.83s`。

```bash
PYTHONPATH=$PWD pytest -q -p no:randomly \
  src/tests/test_routing.py::test_port_balance_analysis_identifies_dead_end_and_split_merge_needs \
  src/tests/test_routing.py::test_port_balance_analysis_is_insensitive_to_pooled_port_instance_ids \
  src/tests/test_routing.py::test_exact_routing_precheck_flags_front_blocked \
  src/tests/test_routing.py::test_exact_routing_precheck_flags_relaxed_disconnected \
  src/tests/test_routing.py::test_terminal_aware_peeling_prunes_non_terminal_dead_end_branch \
  src/tests/test_routing.py::test_routing_local_pattern_filter_reduces_state_space_without_changing_feasibility \
  src/tests/test_routing.py::test_elevated_bridge_states_require_opposite_neighbors \
  src/tests/test_routing.py::test_routing_placement_core_precheck_matches_grid_path \
  src/tests/test_routing.py::test_routing_subproblem_from_placement_core_matches_grid_build \
  src/tests/test_routing.py::test_benders_loop_import \
  src/tests/test_routing.py::test_candidate_sizes_generation \
  src/tests/test_routing.py::test_outer_search_import \
  src/tests/test_routing.py::test_routing_solver_worker_override_changes_only_solver_parameter
```

结果：`13 passed in 21.38s`。

```bash
PYTHONPATH=$PWD pytest -q -p no:randomly \
  src/tests/test_exact_contract.py::test_unexpected_routing_precheck_status_returns_unknown_without_routing_cut \
  src/tests/test_exact_contract.py::test_relaxed_disconnected_only_rejects_binding_selection_without_persisted_cut \
  src/tests/test_exact_contract.py::test_routing_front_blocked_unencodable_optional_conflict_fails_closed \
  src/tests/test_p0_certified_soundness_fixes.py::test_front_blocked_safe_reject_enumerates_binding_before_master_cut
```

结果：`4 passed in 1.14s`。

自定义 probe 结果：

```text
probe_ok pattern_counts 44 4 statuses ['feasible', 'front_blocked', 'relaxed_disconnected'] vars 6
```

说明：我尝试过一次 `pytest -q -p no:randomly src/tests/test_routing.py` 单进程整文件运行；它在本沙盒里输出到 24 个点后超过外层 timeout。随后按上面的三组拆分运行覆盖了该文件收集到的 25 个测试，全部通过。没有运行全量 `src/tests`，因为本轮范围限定 routing soundness，且整库测试会显著超过本轮审查预算。
