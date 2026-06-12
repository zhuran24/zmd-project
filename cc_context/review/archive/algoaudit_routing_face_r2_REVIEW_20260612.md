# 终末地 IndustrialPlanner routing 面确认轮 REVIEW

## 范围与输入确认

审查对象只使用 `zmd_routing_r2_snapshot_a02b7aed.zip`。

哈希校验结果：

```text
a02b7aed5910e33670b46c21985c4497b11ee826481366a161f1ddcb6b29aed2  /mnt/data/zmd_routing_r2_snapshot_a02b7aed.zip
```

结果：与题面 sha256 完全一致，继续审查。

本轮范围：`src/models/routing_subproblem.py` 的 routing CP-SAT 编码本体、`specs/09_exact_grid_routing_subproblem.md`、`rules/canonical_rules.json`、`specs/02_global_notation_and_units.md`，并抽查 port/front 生成侧的 outward normal 语义。

结论：本轮不是零 finding。本轮发现 2 个 soundness finding，均已给出补丁与回归。

## Findings

### R2-Q2-01, HIGH: input/sink front 方向极性反向，合法直线布线被误拒

位置：原始快照 `src/models/routing_subproblem.py:603-615` 与 `src/models/routing_subproblem.py:940-965`。

规则依据：候选端口保存的是 outside-adjacent connector cell 与 outward normal，routing front 定义为 `front = port + DIR_DELTA[dir]`。因此 output/source 端口向 front 注入时，front cell 的 `flow_in` 应为 `Opp(dir)`。input/sink 端口从 front cell 回到 connector 时，front cell 的 `flow_out` 也应为 `Opp(dir)`。

原始编码：

```python
# _index_port_fronts, sink 分支
self._sink_port_fronts[(fx, fy, direction, commodity)] += 1

# _add_port_adherence, sink 分支
(fx, fy, GROUND_LAYER, direction, commodity)
```

这要求 sink front 朝 outward normal 输出。对于 port `(4,0,W)`，front 是 `(3,0)`，物理上必须从 `(3,0)` 朝东送回 connector `(4,0)`，但原始代码要求朝西输出。

最小复现，原始快照：

```python
allowed = {(1, 0), (2, 0), (3, 0)}
occupied = {(x, y) for x in range(70) for y in range(70) if (x, y) not in allowed}
port_specs = [
    {"instance_id": "src", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
    {"instance_id": "sink", "x": 4, "y": 0, "dir": "W", "type": "in", "commodity": "ore"},
]
```

原始快照实测：

```text
precheck feasible
port_adherence {'exact_links': 1, 'blocked_ports': 1, 'ports': 2}
solve INFEASIBLE
```

这是合法的三格直线 corridor：source front `(1,0)`，中间 `(2,0)`，sink front `(3,0)`。precheck 判可行，完整 routing 因 sink front 极性反向而拒绝，属于 false-INFEASIBLE。

修复：sink front 索引与 port adherence 都改为 `send_dir = DIR_OPP[direction]`。

回归：`src/tests/test_routing.py:116-158` 新增 `test_sink_front_consumes_against_outward_normal_on_straight_corridor`，断言 precheck feasible，routing FEASIBLE，sink front `(3,0)` 的 `flow_out == ["E"]`。

### R2-Q1-01, HIGH: L0/L1 同格合法重叠时，局部 `>= 1` 支撑允许隐藏 1-to-2/2-to-1 边通道膨胀

位置：原始快照 `src/models/routing_subproblem.py:560-561`、`src/models/routing_subproblem.py:896-905`、`src/models/routing_subproblem.py:929-938`。

规则依据：`rules/canonical_rules.json` 允许 elevated bridge 与 ground straight belt 在同一 2D cell 重叠，但两者是互不干扰的独立物理通道。`specs/09` 要求每层每格单占、bridge 只能直行、bridge 下方只能为空或 ground straight belt，且方向连续。允许重叠不等于允许一个边上的单条发送通道同时喂给上下两层，也不等于允许上下两条通道合并成一条。否则等价于在 bridge overlap 处免费放置了隐形 splitter/merger。

原始编码问题：successor 与 predecessor 只要求存在至少一个接收者或发送者，而且候选接收/发送列表跨层汇总：

```python
recv_vars = self._vars_by_cell_dir_in_commodity.get((nx, ny, recv_dir, commodity), [])
self.model.Add(sum(recv_vars) >= 1).OnlyEnforceIf(var)

send_vars = self._vars_by_cell_dir_out_commodity.get((px, py, send_dir, commodity), [])
self.model.Add(sum(send_vars) >= 1).OnlyEnforceIf(var)
```

当 `(2,0)` 同时选择 L0 straight 与 L1 bridge 时，`(1,0)` 的一条 east 输出可以同时支撑 `(2,0,L0)` 与 `(2,0,L1)` 两个接收 state。随后两个 state 的 east 输出又可以被 `(3,0)` 的一个接收 state 支撑。连通性 guard 只验 selected-state 图可达，不验每条 2D directed edge 上的通道数守恒，因此这个非法通道倍增可通过 guard。

隔离复现，保留 sink 极性修复但临时禁用 edge balance：

```python
RoutingSubproblem._add_directed_edge_balance_constraints = lambda self: None
allowed = {(1, 0), (2, 0), (3, 0)}
forced = {
    (1, 0, 0, ("W",), ("E",), "ore"),
    (2, 0, 0, ("W",), ("E",), "ore"),
    (2, 0, 1, ("W",), ("E",), "ore"),
    (3, 0, 0, ("W",), ("E",), "ore"),
}
```

实测：

```text
vars contains forced True
solve without edge balance FEASIBLE
guard failure_count 0
```

原始快照上也可构造组合非法 incumbent 被接受：source `(0,0,E)`，sink `(4,1,W)`，强制 state 包含 `(2,0)` 的 L0 与 L1 双重 straight，原始求解器返回 `FEASIBLE` 且 guard `failure_count == 0`。

修复：在局部 predecessor/successor 支撑之外，新增 directed edge balance 约束。对每个 commodity、每条非 terminal 的有向相邻边 `(x,y,d) -> (nx,ny,Opp(d))`，约束选中发送 state 数量等于选中接收 state 数量：

```python
self.model.Add(sum(send_vars) == sum(recv_vars))
```

source 注入边与 sink 消费边不属于 cell-to-cell edge，继续由 `_add_port_adherence()` 精确处理，因此不参与该守恒式。

修复位置：`src/models/routing_subproblem.py:641-645` 调用新约束，`src/models/routing_subproblem.py:876-926` 新增 `_add_directed_edge_balance_constraints()`。

回归：`src/tests/test_routing.py:161-196` 新增 `test_bridge_overlap_cannot_duplicate_single_edge_channel`。同一 forced illegal set 在补丁后返回 `INFEASIBLE`。

## Q1 网格 cell/层语义对照矩阵

| 规则项 | specs/canonical 语义 | 当前编码状态 | 本轮结论 |
|---|---|---|---|
| solid obstacle | 刚体占据格锁死 ground 与 elevated | 只在 active free cells 上建 routing 变量，front_blocked 也要求 front free | OK |
| 每 cell 每 layer 容量 | 每层每格最多一个方向组合与一个 commodity | `_vars_by_cell_layer[(x,y,layer)]` 全 commodity `AddAtMostOne` | OK |
| L1 bridge 形态 | elevated 只允许直行，不能转弯 | `_iter_state_patterns(ELEVATED_LAYER)` 只生成 `d_in -> Opp(d_in)` | OK |
| L1 与 L0 互斥/重叠 | L1 不可穿 solid；可叠 ground straight；不可叠 curved/splitter/merger | `_add_bridge_constraints()` 用 `l1_any => not l0_nonstraight`，solid 由 active free domain 排除 | OK |
| L0 straight 与 L1 bridge 同格独立性 | 二者可同格，但通道互不干扰 | 原始局部 `>=1` 会把单边通道倍增；补丁加入 directed edge balance | 已修复，见 R2-Q1-01 |
| ground belt 方向 | belt 需要明确 in/out，不能从同侧进出 | ground belt state 生成排除 `d_out == d_in`，包含直行与转弯 | OK |
| splitter/merger | specs/09 当前以 routing state 支持 pooling；canonical 没有额外方向表 | ground state 支持 1-to-2/3 与 2/3-to-1，并由 edge balance 保证边通道守恒 | OK，本轮无新 finding |
| bridge endpoint | L1 可与 L0 free cell 无缝接驳，无额外坡道格 | continuity 使用相邻 cell 的 matching direction，允许 L0/L1 接驳；L1 本身仍直行 | OK，未发现过剪样例 |
| port cell 与 front cell | port 是 connector，front 是第一格 routing cell | routing 变量只落在 active front/free cells；port adherence 只验 front ground layer | sink 极性已修复，见 R2-Q2-01 |

## Q2 source/sink front 检查清单

- Source front：`front = port + dir`，source 从 connector 注入 front，因此 front 的 `flow_in == Opp(dir)`。编码原本正确，补丁未改动。
- Sink front：`front = port + dir`，sink 从 front 回到 connector，因此 front 的 `flow_out == Opp(dir)`。原始编码反向，已修复。
- 多 commodity 隔离：state key 带 commodity，continuity 与 edge balance 都按 commodity 建约束；同一 cell-layer 的跨 commodity 冲突由 `AddAtMostOne` 排除。
- 多端口共享同一 front：routing 层不会放宽 cell-layer 容量；若 binding 给出物理上共享同一 front 的多条实体连接，routing 会 infeasible，而不是 false-feasible。
- 容量 1 item/Tick：routing 层是拓扑与离散通道证明层。每个 layer cell 至多一个组件、每个端口 exact link 一条通道，对应 specs/02 的单带容量单位；数值吞吐与 splitter/merger 调度没有在 routing CP-SAT 中模拟，本轮未把 diagnostic flow 当 proof。

## Q3 precheck 与完整 solve 一致性

- `front_blocked`：precheck 要求每个 `front = port + dir` 在网格内且属于 free cell。完整 routing 的 terminal adherence 只能在 ground front cell 上接入，不能让 terminal 直接穿 solid 或从 L1 接口接入。因此该 safe reject 不比完整 solve 更严。
- `relaxed_disconnected`：precheck 使用 2D free component 连通性，忽略方向、层、容量与 splitter/merger 细节。它只在 front cells 处于不同 solid-separated components 时拒绝；完整 routing 不能跨越 solid component 边界，因此该判定是保守拒绝。
- timeout 方向：当前 precheck 是确定性图分析，没有 CP-SAT 时间预算路径。未发现“超时当 blocked”的 fail-open 或 over-strict 分支。
- 本轮新增 regression `test_sink_front_consumes_against_outward_normal_on_straight_corridor` 同时覆盖 precheck feasible 但原完整 solve false-INFEASIBLE 的缝隙。

## Q4 guard 与编码独立性复核

- terminal polarity：guard 通过 `_source_port_fronts` 与 `_sink_port_fronts` 取得 source/sink fronts。sink 极性修复在 `_index_port_fronts()`，因此 guard 的 terminal 方向与 CP-SAT port adherence 同源更新，不存在一边修、一边漂移。
- adjacency：guard 与 lazy cut 仍使用与 modeled successor 相同的方向匹配语义，terminal sink side 不扩展。edge balance 是 CP-SAT 编码补强，不改变 guard 的 reachability acceptance 边界。
- budget/fail-closed：专项 P0 回归继续覆盖 guard 拒绝后 timeout 不暴露 stale routes、lazy cut self-check 失败回退 nogood、多 commodity 分别检查。补丁后这些回归全绿。

## 补丁摘要

修改文件：

- `src/models/routing_subproblem.py`
- `src/tests/test_routing.py`
- `src/tests/test_p0_certified_soundness_fixes.py`

应用方式：

```bash
cd project
patch -p1 < routing_r2_soundness_fixes.diff
```

冻结工件条款：本补丁只修改源码与测试，不修改 `rules/canonical_rules.json`、`candidate_placements.json` 或任何登记 hash 的冻结工件。无需再生冻结工件，无 sha256/字节数登记更新。

## 自验记录

环境：Python 3.13 venv，离线 wheels 来自 `zmd_py313_linux_x86_64.zip`。

通过的命令：

```bash
PYTHONPATH=. python -m py_compile \
  src/models/routing_subproblem.py \
  src/tests/test_routing.py \
  src/tests/test_p0_certified_soundness_fixes.py
```

```bash
PYTHONPATH=. python -m pytest -q \
  src/tests/test_routing.py::test_sink_front_consumes_against_outward_normal_on_straight_corridor \
  src/tests/test_routing.py::test_bridge_overlap_cannot_duplicate_single_edge_channel \
  src/tests/test_routing.py::test_routing_supports_splitter_state \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_feasible_incumbent_requires_source_to_sink_connectivity \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_timeout_does_not_expose_rejected_routes \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_checks_each_selected_commodity \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cuts_converge_on_three_commodity_probe \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_preserves_real_feasible_path \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_self_check_falls_back_to_nogood \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_guard_rejects_source_front_without_sink_reachability \
  -p no:randomly
```

结果：

```text
10 passed in 1.90s
```

```bash
PYTHONPATH=. python -m pytest -q src/tests/test_p0_certified_soundness_fixes.py -p no:randomly
```

结果：

```text
12 passed in 2.06s
```

```bash
PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
```

结果：

```text
P1.2 proof obligation check passed: 8 obligations anchored
```

未宣称全量 `src/tests` 完成。一次扩展尝试 `PYTHONPATH=. python -m pytest -q src/tests/test_routing.py -k 'not small_solve' -p no:randomly` 在沙盒 180s 限制内未结束，退出前未出现失败摘要。因此本交付只声称上述专项与 proof obligation 通过。
