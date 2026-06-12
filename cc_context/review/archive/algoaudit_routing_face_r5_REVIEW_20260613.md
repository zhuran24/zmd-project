# IndustrialPlanner routing face round 5 review

审查对象：`zmd_snapshot_70457b5e.zip` 里的 `project/` 仓库根。开工前已校验快照 sha256：`70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`，与任务给定值一致。

结论：本轮不是零 finding。R4-01/R4-02 修复本体未发现回归，但在 build 层发现 1 个新的 fail-closed/soundness hardening 漏洞：外部传入的陈旧 `domain_analysis` 可把真实占据格重新带回 active routing domain，绕过 solid exclusion 的“只在 active free cells 上建变量”假设。已附最小补丁与回归测试。

---

## Finding F-RT-R5-01 — 外置 `domain_analysis` 未与真实 free grid 二次求交，可经陈旧分析穿越实体占据格

Severity：High for routing proof boundary / external caller hardening。当前 Benders 主路径会先用同一 `RoutingGrid` 调 `analyze_exact_routing_domain()`，因此我没有观察到常规 certified path 直接触发；但 `RoutingSubproblem(..., domain_analysis=...)` 是公开 build 入口，且 R3/R4 已把“外置 domain fail-closed 二次扣除”作为防线。这个入口若接受陈旧或外部分析，会产生 CP-SAT `FEASIBLE` 并被 guard 接受，违反 09 章 solid obstacle exclusion。

位置：

- `src/models/routing_subproblem.py:841-859`，`_bind_domain_analysis()`。
- 原实现仅执行 `analysis_cells - port_connector_cells`。由于 `_add_obstacle_exclusion()` 在 `src/models/routing_subproblem.py:1022-1024` 是 no-op，并明确依赖“只在 active free cells 上建变量”，一旦 external `commodity_active_cells` 含 occupied cell，后续 `_create_routing_variables()` 会在实体格上建 route-state。

最小复现 probe：

```text
free routing cells only: (1,0), (3,0)
occupied solid:          (2,0)
ports: src at (0,0,E), sink at (4,0,W)

slice y=0:
  src(E) -> [1,0]  #solid(2,0)  [3,0] -> sink(W)

stale caller-supplied domain_analysis claims active/component cells:
  {(1,0), (2,0), (3,0)}
```

实证：未打补丁前，`analyze_exact_routing_domain(grid)` 正确返回 `relaxed_disconnected`，但 `RoutingSubproblem(grid, ["ore"], domain_analysis=stale).solve()` 返回 `FEASIBLE`，`extract_routes()` 含 `(2,0)` 上的 L1 bridge：

```text
{'commodity': 'ore', 'x': 1, 'y': 0, 'layer': 0, 'component_type': 'belt',   'flow_in': ['W'], 'flow_out': ['E']}
{'commodity': 'ore', 'x': 2, 'y': 0, 'layer': 1, 'component_type': 'bridge', 'flow_in': ['W'], 'flow_out': ['E']}
{'commodity': 'ore', 'x': 3, 'y': 0, 'layer': 0, 'component_type': 'belt',   'flow_in': ['W'], 'flow_out': ['E']}
```

根因：R3 的 connector 二次扣除是 fail-closed 的，但只覆盖 connector；它没有把 external active/component cells 与 `self.grid.free_cells` 求交。CP-SAT 的障碍排斥又完全依赖 active domain，不再另加 occupied-cell zero row。于是陈旧分析成了“魔法通行证”。

修复：在 `_bind_domain_analysis()` 中构造 `routable_domain_cells = set(self.grid.free_cells) - port_connector_cells`，并对 external `component_cells` 与 `active_cells` 都取交集，而不是只减 connector。这样 connector、occupied solid、out-of-grid 三类都被同一口径挡回去；如果端口 front 因裁剪后不在 active domain，`_add_port_adherence()` 会添加 `0 == 1`，保持 fail-closed。

Regression：新增 `src/tests/test_routing.py:230-258`：`test_external_domain_analysis_cannot_route_through_occupied_cell()`。该测试确认 precheck 看见断连；即便调用者传入含 occupied `(2,0)` 的陈旧 feasible domain，build 后也不会为 `(2,0)` 产生 route-state，求解结果为 `INFEASIBLE`。

Unified diff：见随附 `routing_r5_fix.patch`。

---

## Q1：R4-01 / R4-02 修复确认

### R4-01 per-component domain grouping

核查结果：修复语义成立；未发现 R4 本体回归。

1. Component 划分口径与 CP-SAT 域口径：`analyze_exact_routing_domain()` 先在 `_resolve_routing_domain_context()` 中扣除 port connector cells，再基于扣除后的 `resolved_free_cells` 计算 components：`src/models/routing_subproblem.py:332-373`。R4 分组随后用同一 `component_by_cell` 给 terminal fronts 分量归类：`src/models/routing_subproblem.py:500-505`。补丁后，build 入口也会把 external active/component cells 与 `grid.free_cells - connector` 二次求交：`src/models/routing_subproblem.py:847-857`。因此 analyze 内源结果与 build 外置结果的口径已收敛。

2. “某 component 只有 source 但该 component 流量为 0”不会构成合法被误拒场景：routing 的 `port_specs` 已是 binding 选择后的 active port 集合。`binding_subproblem.extract_port_specs()` 对 `__unused__`、virtual、routing-free 端口在源头跳过：`src/models/binding_subproblem.py:1014-1073`。一旦端口进入 `port_specs`，`_add_port_adherence()` 对 source/sink front 加 exact-one：`src/models/routing_subproblem.py:1207-1230`。也就是说，routing 域判定看到的 source 不再是“可能空置”的候选，而是必须接线的已选端口。

3. `domain = 满足 component 的并集 + 逐 component peel` 没有 peel 顺序污染：`_compute_free_components()` 产出的 `cells_by_component` 互不相交：`src/models/routing_subproblem.py:214-245`；R4 分支对每个 component 独立调用 `_peel_terminal_core(component_cells, component_fronts)` 并做 `active_union.update()`：`src/models/routing_subproblem.py:531-557`。先 peel 的 component 没有可共享格可削到后续 component。

4. 单侧商品切换判据：`if not source_fronts or not sink_fronts`：`src/models/routing_subproblem.py:507-529`。该分支只在 routing 已选端口中缺少某一侧时触发，保留旧保守行为；如果 terminals 落在多个 component，直接 `relaxed_disconnected`。即便某单侧商品被 analyze 保守放过，guard 也在最终验收中要求 expected source/sink 均非空，缺任一侧即失败：`src/models/routing_subproblem.py:1659-1666`。这是 false-negative/收敛风险，不是 false-FEASIBLE。

### R4-02 duplicate terminal front key

核查结果：修复语义成立；未发现 R4 本体回归。

- `analyze_exact_routing_domain()` 与 `RoutingSubproblem.__init__()` 复用同一个 `_duplicate_terminal_front_keys()` helper：定义在 `src/models/routing_subproblem.py:136-186`，analyze 调用在 `src/models/routing_subproblem.py:398-417`，build 构造调用在 `src/models/routing_subproblem.py:761`。没有复制 key 构造逻辑导致漂移的风险。
- key 为 `(front_x, front_y, terminal_dir=Opp(dir), commodity, port_type)`，同时保留 `instance_id` 与物理端口坐标用于 conflict diagnostics：`src/models/routing_subproblem.py:147-184`。
- fail-closed 方向正确：analyze 返回 `status="front_blocked"` 且 `binding_selection_safe_reject=True`：`src/models/routing_subproblem.py:407-416`。这会进入 binding-local ladder，而不是把整个 master 布局直接定为全局 infeasible。build 层若收到绕过 analyze 的 domain，也会加 `0 == 1`：`src/models/routing_subproblem.py:814-819`。

---

## Q2：先读 specs/rules 后对照实现的规则清单

| 规则文本 | 预期编码语义 | 实现对照 | 结论 |
|---|---|---|---|
| `specs/06_candidate_placement_enumeration.md:72-76`：belt 必须占用 `(port.x, port.y)+DIR_DELTA[port.dir]` front；wireless 例外。`specs/08_topological_flow_subproblem.md:32-34`：出口 `p -> v`，入口 `v -> p`。 | port connector 是 terminal node；routing state 必须在 front cell；source front 从 connector 侧接收 `Opp(dir)`，sink front 向 connector 侧送出 `Opp(dir)`。 | `_port_connector_cells()`：`src/models/routing_subproblem.py:120-133`；front blocked：`424-465`；port key index：`786-799`；exact-one port adherence：`1196-1230`。 | sound。R2 极性错已修；本轮未发现反向残留。 |
| `specs/09_exact_grid_routing_subproblem.md:43-45` 与 `rules/canonical_rules.json:30-35`：solid cell 两层全锁死，bridge 也不能穿 solid。 | 所有 route-state 只能建在真实 free cells。 | analyze 内源域扣 connector 并以 free cells 建 component：`332-373`。本轮发现 external domain_analysis 入口未与 free cells 求交；补丁改为 `grid.free_cells - connector` 二次裁剪：`847-857`。 | 原实现外置入口更松，F-RT-R5-01 已修。 |
| `specs/09_exact_grid_routing_subproblem.md:47-49`：每 cell/layer 至多一种方向组合、一种 commodity。 | AtMostOne(cell, layer) across all route-state vars。 | `_add_capacity_constraints()`：`1026-1029`。 | sound。 |
| `specs/09_exact_grid_routing_subproblem.md:51-55`、`specs/03_rule_canonicalization.md:318-327`、`rules/canonical_rules.json:30-35`：L1 只直桥；可叠直地面带；不可叠实体、弯带、分流/汇流；不需要额外 ramp。 | L1 patterns only straight; L1 cell may coexist only with empty L0 or straight L0; no extra takeoff/landing cells; continuity can switch layer by neighbor receiver. | `_iter_state_patterns(ELEVATED_LAYER)` 只产生 `d_out=Opp(d_in)`：`866-877`；`_add_bridge_constraints()` 禁 L1 over L0 non-straight/split/merge：`1031-1042`；solid 由 active domain 排除；successor/predecessor 跨 layer 查 receiver/sender：`1120-1194`。 | sound。桥与 L0 直带方向不要求相同，文本只要求“直线传送带”，未限定同向/垂直。 |
| `specs/09_exact_grid_routing_subproblem.md:57-60`：非端口自由格方向连续。`specs/08_topological_flow_subproblem.md:50-58`：中间节点守恒与相邻截面容量。 | 每个 selected output 必有相邻 compatible input；每个 selected input 必有相邻 compatible output；同商品同 directed edge 的发送数等于接收数，防止一条边喂两层。 | `_add_successor_constraints()`：`1120-1156`；`_add_predecessor_constraints()`：`1158-1194`；`_add_directed_edge_balance_constraints()`：`1068-1118`。 | sound。R2-02 的 hidden splitter/merger 漏洞未复现。 |
| `specs/03_rule_canonicalization.md:306-317`：12 种基础 belt，`d_in != d_out`。 | L0 belt 状态枚举所有非同向 in/out。 | `_iter_state_patterns(GROUND_LAYER)` belt 分支：`879-886`。 | sound。 |
| `specs/03_rule_canonicalization.md:329-344`：splitter/merger 可按容量节点处理。 | L0 splitter 1-in-2/3-out；merger 2/3-in-1-out；受 cell/layer AtMostOne 与 edge balance 约束。 | `_iter_state_patterns()` splitter/merger 分支：`887-904`。 | 未报 finding。文本字面写 1→3 / 3→1，但同段允许按容量节点处理，且现有回归显式覆盖 1→2 sink 场景；按当前项目口径，这是已接受建模抽象。 |
| `specs/09_exact_grid_routing_subproblem.md:61-64` 与 `specs/03_rule_canonicalization.md:290-299`：机器间不可零长度硬连，至少一格物流设施。 | 端口 connector 不可被当 routing cell；front cell 必须是 free routing cell；面对面无 front free cell 会 blocked。 | connector 扣除：`120-133`、`332-373`；front blocked：`433-465`；`_add_gap_rule()` 说明由 placement port-clearance 层执行：`1239-1242`。 | routing 层没有额外 gap row；对当前 front-cell 语义足够，未发现 false-FEASIBLE。 |
| `specs/03_rule_canonicalization.md:211-219 / 221-239`：同边端口同质，允许部分端口空置。 | unused 由 binding 在进入 routing 前裁掉；routing 只对已选 active ports exact-one。 | `extract_port_specs()` 跳过 `__unused__` / virtual / routing-free：`src/models/binding_subproblem.py:1014-1073`；`_add_port_adherence()` exact-one：`1207-1230`。 | sound。 |
| `specs/09_exact_grid_routing_subproblem.md:100-128`：CP-SAT FEASIBLE 不能直接认证，必须 guard 重建 selected graph，source reach sink 且 sink reachable；lazy cut 必须自证，否则 nogood。 | guard adjacency 与候选 lazy-cut adjacency 同构；最终 acceptance 只由 guard 通过决定。 | `_route_state_adjacency()`：`1311-1329`；`_validate_selected_route_connectivity()`：`1591-1687`；cut self-check/fallback 区域：`1434-1588`。独立 fuzz verifier 也重新派生 front 和 connector。 | sound。guard 与 R2/R3/R4 修复同步。 |

---

## Q3：三批修复叠加组合语义与端到端 probes

### 组合语义核查

- R2 edge balance 与 R3 connector 扣除不冲突：edge balance 在 `_commodity_active_cells` 上枚举 directed edges：`src/models/routing_subproblem.py:1088-1114`；connector cells 在 analyze 与 patched build bind 阶段已从 active cells 中剔除：`332-373`、`847-857`。terminal-side ban 只处理 source/sink front 的 connector-facing side，不依赖 connector cell 继续留在 domain。
- R3 terminal-side ban 与 R4 per-component grouping 不冲突：R4 grouping 的 terminal fronts 是 front cells，不是 connector cells：`500-557`；successor/predecessor 只禁止“从普通 route 进入 source connector side / 从 sink connector side 继续流出”的错误方向：`1132-1146`、`1170-1184`。
- R4 multi-component union 与 bridge 跨越不冲突：component 是 2-D free-cell 连通域，bridge 仍只能在 component 内相邻连续；L1 不提供隔空跨 component 跳跃，因为 successor/predecessor 仍要求 adjacent receiver/sender：`1120-1194`。
- Guard 同步性：guard 用 selected route-state 的 `flow_out -> neighbor flow_in=Opp(dir)` 建图，并且不展开 terminal sink front：`1311-1329`；这与 CP-SAT successor/predecessor 的 terminal 例外一致。R2/R3/R4 的关键边界在 guard 的独立 diff verifier 中也有对应检查：front 极性重派生、connector reuse 拒绝、capacity/selected graph 检查。

### Probe A — 双孤岛同 commodity，两个 component 各有 source+sink，应 FEASIBLE

```text
component A, y=0:
  src_a(0,0,E) -> [1,0] - [2,0] - [3,0] -> sink_a(4,0,W)

component B, y=10:
  src_b(0,10,E) -> [1,10] - [2,10] - [3,10] -> sink_b(4,10,W)
```

结果：`analyze_exact_routing_domain.status == feasible`；`RoutingSubproblem.solve() == FEASIBLE`；guard `failure_count == 0`。

覆盖点：R4-01 per-component grouping、per-component peel、guard 多 source/sink selected graph。

### Probe B — connector barrier，commodity 只能穿过别人的 connector 才能相连，应 INFEASIBLE

```text
             water_sink(2,4,S)
                    ^
                  [2,3]
                  [2,2]
ore_src(0,1,E) -> [1,1]  X=(2,1 water_src connector)  [3,1] -> ore_sink(4,1,W)
```

结果：`analyze_exact_routing_domain.status == relaxed_disconnected`，disconnected commodity 为 `ore`；`RoutingSubproblem.solve() == INFEASIBLE`。

覆盖点：R3 connector domain subtraction、terminal-side 禁止、R4 分量判定同口径。

### Probe C — 多商品 bridge crossing，L1 与 L0 直带合法叠加，应 FEASIBLE

```text
free cells:
  horizontal row: y=4, x=1..5
  vertical col:   x=3, y=1..7

ore:   src(0,4,E) -> sink(6,4,W)
water: src(3,0,N) -> sink(3,8,S)
```

结果：`analyze_exact_routing_domain.status == feasible`；`RoutingSubproblem.solve() == FEASIBLE`；guard `failure_count == 0`。实际 crossing cell `(3,4)` 上 solver 选择了 `ore` 的 L1 bridge 与 `water` 的 L0 straight belt 共存，符合 bridge 可叠直带规则：

```text
(3,4) ore   layer=1 bridge flow W->E
(3,4) water layer=0 belt   flow S->N
```

覆盖点：R2 directed-edge balance、多 commodity layer capacity、bridge over straight L0、guard selected graph。

### Probe D — F-RT-R5-01 regression，陈旧 external domain 穿越 solid，补丁后应 INFEASIBLE

```text
src(E) -> [1,0]  #solid(2,0)  [3,0] -> sink(W)
external domain_analysis falsely says active cells include (2,0)
```

结果：补丁前 `solve() == FEASIBLE` 且 route 使用 `(2,0)` L1 bridge；补丁后 no route-state at `(2,0)`，`solve() == INFEASIBLE`。

---

## 验证记录

已执行：

```bash
PYTHONPATH=. python /tmp/routing_r5_probes.py
python -m pytest -q \
  src/tests/test_routing.py::test_external_domain_analysis_cannot_route_through_occupied_cell \
  src/tests/test_routing.py::test_port_connector_cell_cannot_be_reused_as_routing_cell \
  src/tests/test_routing.py::test_same_commodity_disconnected_source_sink_islands_are_routable \
  src/tests/test_routing.py::test_duplicate_terminal_front_keys_fail_closed \
  src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel \
  src/tests/test_routing.py::test_sink_front_consumes_against_outward_normal_on_straight_corridor \
  -p no:randomly
python -m pytest -q src/tests/test_p0_certified_soundness_fixes.py -p no:randomly
python scripts/check_p1_2_proof_obligations.py
python cc_context/verification/diff_fuzz/routing_connectivity_diff.py --self-test
```

结果：

```text
custom probes: dual_island FEASIBLE; connector_barrier INFEASIBLE; bridge_crossing FEASIBLE; stale_domain_solid_hole INFEASIBLE after patch
6 selected routing regressions passed
12 p0 certified soundness regressions passed
P1.2 proof obligation check passed: 8 obligations anchored
routing_connectivity_diff self-test PASS
```

未完成项：

```text
python -m pytest -q src/tests/test_routing.py -p no:randomly
```

该命令在沙盒 300s 限时内未跑完，超时前输出 24 个 passing dots，未观察到失败。未跑全量 `src/tests`，因此不声明全量 2968 passed。
