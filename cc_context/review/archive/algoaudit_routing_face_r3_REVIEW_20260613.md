# IndustrialPlanner routing 面 round 3 审查报告

审查对象只使用 `zmd_rt_r3_snapshot_b377a2a7.zip`。开工前校验 sha256 通过：`b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531`。

结论：本轮不是零 finding。F-RT-R2-01 的 sink-front 极性修复本体没有发现回退；F-RT-R2-02 的非 terminal 有向边守恒等式形状也没有发现过剪。但在终端语义与 routing 域收缩交界处发现 1 个新的 HIGH soundness finding：物理 port connector cell 仍可进入自由 routing 域，导致任意商品可把别的端口 connector 当普通传送带格穿过，或在同商品场景下复用 source/sink terminal 侧边。该漏洞绕过 CP-SAT 本体与 guard，原快照可 false-FEASIBLE。

附补丁：`zmd_rt_r3_terminal_connector_fix.patch`。补丁已在工作树应用，并新增回归 `test_port_connector_cell_cannot_be_reused_as_routing_cell`；同时给 diff-fuzz verifier 增加 connector-cell 复用自检，并修正 README 中旧的 sink polarity 说明。

---

## Finding F-RT-R3-01 — HIGH

**标题**：routing 域未剔除物理 port connector cell，terminal 节点可被当普通 belt cell/edge 复用。

**位置**：

- `src/models/routing_subproblem.py:233-265`：`_resolve_routing_domain_context()` 原样返回 `resolved_core.free_cells` 或 `grid.free_cells`，未从自由格中扣除 port connector cells。
- `src/models/routing_subproblem.py:493-503` / `516-521`：`RoutingGrid` 记录 `port_cells`，但 `free_cells` 仍包含这些 connector cell；`routable_cells = free_cells | port_cells` 也表达了“port cell 可走”的危险语义。
- `src/models/routing_subproblem.py:943-992`：successor/predecessor 连续性把 terminal 侧以外的邻接都当普通 cell-to-cell 支撑；原代码没有禁止普通 route state 从 source connector 侧喂入 source front，或从 sink connector 侧取出。
- `src/models/routing_subproblem.py:1109-1128`：connectivity guard 只按选中 route-state 图证明 source→sink reachability，不证明“节点是否占用了 port connector”。因此一旦 CP-SAT 选出这种路径，guard 会接受。

**规则依据**：

- `specs/06_candidate_placement_enumeration.md:72-75` 明确 port 的 routing front cell 是 `(port.x, port.y) + DIR_DELTA[port.dir]`，传送带必须占用 front cell；port 本体/connector cell 不是 routing cell。
- `specs/08_topological_flow_subproblem.md:29-34` 将 free-cell 空间边与 port-edge 分开：port 节点只与其法向 front cell 建一条接入/接出边，不参与普通空间邻接边。
- `PROJECT_LOCK.md:108` 锁定 terminal front polarity：source front `flow_in = Opp(dir)`，sink front `flow_out = Opp(dir)`，方向朝 connector。该 connector 侧是 terminal 侧，不是可复用的网格边。

**最小复现 probe（原快照）**：

```python
from src.models.routing_subproblem import RoutingGrid, RoutingSubproblem, analyze_exact_routing_domain

allowed = {(1, 1), (2, 1), (3, 1), (2, 2), (2, 3)}
occupied = {(x, y) for x in range(70) for y in range(70) if (x, y) not in allowed}
ports = [
    {"instance_id": "ore_src", "x": 0, "y": 1, "dir": "E", "type": "out", "commodity": "ore"},
    {"instance_id": "ore_sink", "x": 4, "y": 1, "dir": "W", "type": "in", "commodity": "ore"},
    {"instance_id": "water_src", "x": 2, "y": 1, "dir": "N", "type": "out", "commodity": "water"},
    {"instance_id": "water_sink", "x": 2, "y": 4, "dir": "S", "type": "in", "commodity": "water"},
]

grid = RoutingGrid(occupied, ports)
analysis = analyze_exact_routing_domain(grid)
print(analysis["status"], analysis["commodity_active_cells"])

routing = RoutingSubproblem(grid, ["ore", "water"], domain_analysis=analysis)
routing.build()
selected = {
    (1, 1, 0, ("W",), ("E",), "ore"),
    (2, 1, 0, ("W",), ("E",), "ore"),  # (2,1) is water_src's physical connector cell
    (3, 1, 0, ("W",), ("E",), "ore"),
    (2, 2, 0, ("S",), ("N",), "water"),
    (2, 3, 0, ("S",), ("N",), "water"),
}
print("keys exist", selected <= set(routing.r_vars))
for key, var in routing.r_vars.items():
    routing.model.Add(var == (1 if key in selected else 0))
print(routing.solve(time_limit=5.0))
print(routing.build_stats.get("last_solve", {}).get("connectivity_guard"))
```

原快照输出要点：

```text
analysis feasible {'ore': [[1, 1], [2, 1], [3, 1]], 'water': [[2, 2], [2, 3]]}
keys exist True
solve FEASIBLE
connectivity_guard ... 'failure_count': 0 ...
```

这条 `ore` 线路穿过 `(2,1)`，而 `(2,1)` 是 `water_src` 的物理 port connector cell。按照 port/front 规则，`water_src` 的第一格 routable cell 是 `(2,2)`，不是 `(2,1)`；`ore` 不应能占用 `(2,1)`。同一根因还可构造同商品 source terminal 侧复用：一个普通 belt 从 source connector cell 喂入 source front，同时该 front 又被当作 source 注入点满足 adherence。

**修法**：

1. 新增 `_port_connector_cells()`，把所有 in-grid physical connector cells 作为 terminal nodes 收集。
2. 在 `_resolve_routing_domain_context()` 中，从 exact routing 的 `resolved_free_cells` 扣除这些 connector cells，并在 placement-core 复用路径下重建 component / neighbor map，避免复用包含 port connector 的旧连通分量。
3. 在 `_bind_domain_analysis()` 中再次扣除 connector cells，防止调用方传入外置/旧版 `domain_analysis` 时把 connector cells 偷渡进 `_commodity_active_cells`。
4. 在 successor/predecessor 约束中加 terminal-side 禁止项：普通 route state 不得向 source-front 的 connector 侧发送，也不得从 sink-front 的 connector 侧接收。这是 belt-and-suspenders；主体修复是 connector cells 不进 active routing 域。

补丁位置（修后工作树）：

- `src/models/routing_subproblem.py:115-158`：新增 connector-cell helpers。
- `src/models/routing_subproblem.py:279-320`：解析 routing 域时扣除 connector cells 并重建连通组件。
- `src/models/routing_subproblem.py:713-722`：绑定 domain analysis 时 fail-closed 二次扣除 connector cells。
- `src/models/routing_subproblem.py:1007-1011` / `1045-1049`：禁止普通 cell-to-cell continuity 使用 source/sink terminal 侧。
- `src/tests/test_routing.py:199-227`：新增回归。修后该 probe 在 precheck 阶段变成 `relaxed_disconnected`，routing solve 为 `INFEASIBLE`。
- `cc_context/verification/diff_fuzz/routing_connectivity_diff.py:51-92` / self-test：独立 verifier 增加 physical connector cell 不得承载 route-state 的检查。
- `cc_context/verification/diff_fuzz/README.md:32`：修正旧 sink-front polarity 文案。

---

## Q1 — F-RT-R2 修复确认

### Q1.1 sink-front 极性修复覆盖

未发现残留 `flow_out = dir` 的 sink-front 消费点。核验清单如下：

- front cell 坐标：`analyze_exact_routing_domain()` 在 `src/models/routing_subproblem.py:294-335` 使用 `front = port + DIR_DELTA[dir]`，这里只判定 front 可用性，不消费 terminal polarity。
- solver terminal 索引：`_index_port_fronts()` 在 `src/models/routing_subproblem.py:603-616` 对 source 使用 `recv_dir = DIR_OPP[direction]`，对 sink 使用 `send_dir = DIR_OPP[direction]`。
- 局部支持剪枝：`_incoming_dir_supported()` / `_outgoing_dir_supported()` 在 `src/models/routing_subproblem.py:719-731` 分别读取 `_source_port_fronts` / `_sink_port_fronts`，没有重新推导相反方向。
- adherence：`_add_port_adherence()` 在 `src/models/routing_subproblem.py:998-1021` 对 source-front 取 ground-layer `flow_in = Opp(dir)`，对 sink-front 取 ground-layer `flow_out = Opp(dir)`。
- guard：`_terminal_fronts_by_commodity()`、`_terminal_nodes_by_front_for_keys()`、`_route_state_adjacency()` 在 `src/models/routing_subproblem.py:1042-1128` 消费已经按 `DIR_OPP` 建好的 source/sink front key；sink front 的 `flow_out` 被视为 terminal，不再扩展成普通邻接边。
- diff-fuzz oracle：`cc_context/verification/diff_fuzz/routing_connectivity_diff.py:51-68` 也已按 `DIR_OPP` 重导 sink-front send dir。`cc_context/verification/diff_fuzz/README.md:32` 在补丁中已同步为 `flow_out = Opp(port.dir)`，避免以后把旧约定从文档里“复活”。

source/sink 对称性成立：source 是从 connector 注入 front，所以 front 的 `flow_in = Opp(dir)`；sink 是从 front 送回 connector，所以 front 的 `flow_out = Opp(dir)`。

### Q1.2 directed edge balance 形状

`_add_directed_edge_balance_constraints()` 在 `src/models/routing_subproblem.py:876-926` 按 commodity、按非 terminal 有向 cell-to-cell 边建立：

```text
sum(selected send states on u --d--> v) == sum(selected receive states on v from Opp(d))
```

这个等式没有发现过强。合法 splitter/merger 的分流/汇流发生在同一个 ground cell 的多个出边/入边上；对每一条单独有向边，物理通道数仍必须左右相等。L0 straight 与 L1 bridge 在同一 2D cell 合法重叠时，一条有向边上如果两层都跨过，就应有两条发送态与两条接收态；如果只有一侧两层、一侧单层，就是 F-RT-R2-02 要禁止的隐形 splitter/merger。

terminal edge 豁免的方向本身是正确的：source/sink connector 侧不是 cell-to-cell edge，adherence 已经负责 exact-one。问题在本轮 finding 中：原代码让 connector cell 本身进入 active routing 域后，terminal 豁免会把本不应存在的普通边漏过去。补丁把 connector cell 排除后，terminal 豁免边界恢复为恰好。

### Q1.3 capacity / bridge / edge-balance 交互 probe

构造了一个强制布局：`ore` 在 `(1,2)-(3,2)` 走 L0 horizontal straight；`water` 从 `(2,4)` 经 L1 bridge `(2,3),(2,2)` 到 `(2,1)` vertical，下穿/上跨重叠点 `(2,2)`。强制选择这些 route states 后，修后模型返回 `FEASIBLE`，`directed_edge_balance` 建了 10 条约束，说明没有把合法的 L0-straight + L1-bridge 共存误剪成 infeasible。

---

## Q2 — 容量与多 commodity 语义核验

核验到的状态矩阵如下：

| 维度 | 编码位置 | 结论 |
|---|---|---|
| 同一 `(cell, layer)` 内不同 state / commodity | `_vars_by_cell_layer` + `AddAtMostOne`，`src/models/routing_subproblem.py:782`、`834-837` | 恰好互斥。不同 commodity 同层混线不可发生；同 commodity 同层多 state 也不可发生。 |
| L1 bridge 形态 | `_iter_state_patterns()`，`src/models/routing_subproblem.py:675-683` | L1 只生成 `flow_out = Opp(flow_in)` 的直桥，不生成弯桥 / splitter / merger。 |
| L0 + L1 同 cell | `_add_bridge_constraints()`，`src/models/routing_subproblem.py:839-850` | L1 存在时，L0 可为空或 straight belt；L0 non-straight splitter/merger/turn 与 L1 互斥。 |
| 不同 commodity 不同层 | capacity 是 per `(cell, layer)`，bridge 只禁止 L0 non-straight | 合法，例如 L0 `ore` straight + L1 `water` bridge；上述 probe 已实证。 |
| 非 terminal 有向边 | `_add_directed_edge_balance_constraints()`，`src/models/routing_subproblem.py:876-926` | 每 commodity 的每条非 terminal directed edge 发送态数等于接收态数，堵住 L0/L1 overlap 的隐形 fork/merge。 |
| terminal front | `_add_port_adherence()`，`src/models/routing_subproblem.py:998-1028` | 每个 port spec 对应的 front-side state sum 精确等于 1。 |
| physical port connector | 本补丁新增 | connector cell 不再属于 free routing 域；防止任意 commodity 过线、跨商品偷穿、terminal 侧复用。 |

汇流/分流语义：同 commodity 的 ground-layer splitter/merger 是编码允许项，和 specs/09 的 pooling 语义一致；多 source 汇到同一 belt、一个 source 分到多个 sink 都是合法形态。不同 commodity 的汇流/混线在同层被 `AtMostOne` 禁止，在不同层只允许桥/直带共存且 commodity 仍保持独立 route-state graph。

---

## Q3 — 终端语义抽查

- `front cell = port + dir` 在 precheck、索引、adherence、guard/oracle 中一致。
- source-front 方向是 `flow_in = Opp(dir)`；sink-front 方向是 `flow_out = Opp(dir)`。F-RT-R2-01 的修复半径内没有发现“索引修了、adherence/guard 未修”的同源漂移。
- 多 port 共享同一 front cell：如果共享的是同一 routable front cell、但 terminal 方向不同，ground-layer splitter/merger/straight state 可以在 capacity 允许的范围内同时满足多个 terminal directions；如果两个 port 生成完全相同的 `(front, direction, commodity, type)` key，当前代码会添加重复的 `sum(vars)==1`，不会表达 multiplicity=2。就 canonical 非重叠 pose 来看我没有构造出这种重复物理 terminal key；若以后 `port_specs` 入口对外开放，建议加 fail-closed duplicate terminal-key 检查，避免重复端口规范被静默折叠。
- 本轮 finding 修复后，front cell 仍可共享；被禁止的是 physical connector cell 进入 routing 域，二者没有混同。

---

## Q4 — guard / fuzz 同步维持

Guard 与编码的 reachability 语义仍基本同构：从 source-front selected states BFS，经 `flow_out -> neighbor.flow_in` 扩展，sink-front `flow_out` 作为 terminal 消费边停止。但 guard 不检查“被选 route state 是否占用了 physical port connector cell”，也不检查 terminal-side 普通边复用。这不是 guard 的理想证明面；connector/terminal-side 排他必须在 CP-SAT 域与 continuity 编码层 fail-closed。

本轮发现说明：仅靠 reachability guard 不足以覆盖 terminal-domain 污染。补丁后 guard 可以继续只做连通性边界，因为非法 connector route state 已不会被创建；diff-fuzz oracle 也已在补丁中新增 route cells 不得落在 port connector set 内的独立检查，并把旧 sink polarity README 文案修正掉。

---

## 自验记录

已执行并通过：

```text
python -m pytest -q \
  src/tests/test_routing.py::test_sink_front_consumes_against_outward_normal_on_straight_corridor \
  src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel \
  src/tests/test_routing.py::test_port_connector_cell_cannot_be_reused_as_routing_cell \
  src/tests/test_routing.py::test_routing_supports_splitter_state \
  -p no:randomly
# 4 passed in 0.61s

python -m pytest -q \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_feasible_incumbent_requires_source_to_sink_connectivity \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_rejects_source_front_without_sink_reachability \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_timeout_does_not_expose_rejected_routes \
  -p no:randomly
# 3 passed in 0.70s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

python cc_context/verification/diff_fuzz/routing_connectivity_diff.py --self-test
# PASS — accepts valid flow; catches A-1 dead-end + capacity overload + connector reuse.
```

另外手写强制 probe 验证 L0 straight + L1 bridge 合法重叠仍为 `FEASIBLE`。我没有声称全量 `src/tests` 跑完；本轮只跑了 routing/guard/proof/fuzz 专项与针对性 probes。
