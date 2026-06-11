# 终末地 IndustrialPlanner P0-1 lazy connectivity cut 实现审查

结论：**本轮零 soundness finding**。

本轮只审 `src/models/routing_subproblem.py` 中 lazy source-side connectivity cut 与 guard/solve loop 的交互，以及 `src/tests/test_p0_certified_soundness_fixes.py` 中新增/相关测试。未进入 P1.3B flow 一等编码范围。

## 审查输入

- 项目包：`/mnt/data/zmd_v80_impl_full_20260612_single.zip`
- sha256：`9e21ca319186e64786627a1a9ed77a507959d6113bbd38c136aa8162a7ee96ac`，与任务给定值一致。
- 依赖包：`/mnt/data/zmd_py313_linux_x86_64.zip`
- Python：3.13.5

## 实际执行命令

```bash
python3 -m zipfile -e /mnt/data/zmd_v80_impl_full_20260612_single.zip /mnt/data/review_zmd
python3 -m zipfile -e /mnt/data/zmd_py313_linux_x86_64.zip /mnt/data/wheels_zmd
/opt/pyvenv/bin/python3.13 -m pip install --no-index --find-links <wheels_dir> -r requirements.txt
/opt/pyvenv/bin/python3.13 -m pytest -q --randomly-dont-reset-seed src/tests/test_p0_certified_soundness_fixes.py
/opt/pyvenv/bin/python3.13 scripts/check_p1_2_proof_obligations.py
/opt/pyvenv/bin/python3.13 -m ruff check src/models/routing_subproblem.py src/tests/test_p0_certified_soundness_fixes.py
/opt/pyvenv/bin/python3.13 -m py_compile src/models/routing_subproblem.py src/tests/test_p0_certified_soundness_fixes.py
```

结果：

- `test_p0_certified_soundness_fixes.py`：`10 passed`
- `check_p1_2_proof_obligations.py`：`P1.2 proof obligation check passed: 8 obligations anchored`
- targeted ruff：`All checks passed!`
- py_compile：通过

补充：我也跑了 `mypy --strict --explicit-package-bases src/models/routing_subproblem.py`。它在该文件与 `cp_sat_worker_config.py` 上有既存的广域类型/stub 噪声，例如 OR-Tools `CpModel.Add/NewBoolVar` stub attr-defined、未标注旧函数等；这些不是 lazy cut 新增面独有，也不是本轮 soundness finding。实现方文档中的 mypy 自验范围是 `src/cuts/`。

## Q1：割有效性审查

### 1. source/sink front 语义与 port adherence 同构

结论：未发现 invalid cut。

代码里 source/sink front 的索引与 port exact-one 约束一致：

- `_index_port_fronts()` 对 output port 使用 `recv_dir = DIR_OPP[direction]`，登记 `(front_x, front_y, recv_dir, commodity)` 为 source front；对 input port 登记 `(front_x, front_y, direction, commodity)` 为 sink front。位置：`src/models/routing_subproblem.py:603-615`。
- `_add_port_adherence()` 对 source port 强制 `GROUND_LAYER` 且 `flow_in` 含 `recv_dir` 的候选变量 `sum == 1`；对 sink port 强制 `GROUND_LAYER` 且 `flow_out` 含 `direction` 的候选变量 `sum == 1`。位置：`src/models/routing_subproblem.py:940-973`。
- `_terminal_nodes_by_front_for_keys()` 只把 ground-layer、`flow_in` 命中 source front 的状态视为 source terminal，只把 ground-layer、`flow_out` 命中 sink front 的状态视为 sink terminal。位置：`src/models/routing_subproblem.py:1028-1052`。
- cut 的定义 1 使用 full potential keys 重新枚举每个 expected source front 的所有候选 source nodes，并把不在 `W` 的候选纳入 `X`。位置：`src/models/routing_subproblem.py:1151-1176`。

因此，“当前 incumbent 的 W 内有某个 selected source-state，但真解使用同一 source front 的另一个接收 state”这一攻击会被定义 1 捕获。已有保真测试的真路径就是这种形态：被拒 incumbent 在 source front 选了 `flow_in=("E","W"), flow_out=("N",)`，真路径改用 `flow_in=("W",), flow_out=("E",)`；我额外直接抽取第一刀的 `X`，确认真路径与 `X` 的交集为 `[(1, 0, 0, ('W',), ('E',), 'ore')]`。

若某 source front 在 incumbent 中没有 selected 接收 state，`_self_check_source_side_connectivity_cut()` 会重新算 `W` 后返回 `source_front_not_in_w`，不会加 lazy cut。位置：`src/models/routing_subproblem.py:1215-1239`。正常 CP-SAT incumbent 中 `_add_port_adherence()` 的 exact-one 已保证 source-state 存在；异常情况下走 fallback，仍 fail-closed。

### 2. arc 语义与 CP-SAT continuity 约束

结论：未发现会产生 invalid cut 的同构盲区。

CP-SAT continuity 的真实局部语义是：

- successor：选中 `u=(x,y,layer,*,flow_out,k)` 且输出方向 `d` 非 ground sink terminal 时，邻格 `(x+dx, y+dy)` 必须至少有一个同 commodity、`flow_in` 含 `DIR_OPP[d]` 的候选状态被选中。位置：`src/models/routing_subproblem.py:874-905`。
- predecessor：选中 `v=(x,y,layer,flow_in,*,k)` 且输入方向 `d` 非 ground source terminal 时，邻格 `(x+dx, y+dy)` 必须至少有一个同 commodity、`flow_out` 含 `DIR_OPP[d]` 的候选状态被选中。位置：`src/models/routing_subproblem.py:907-938`。
- splitter/merger 多入多出并没有特殊边类型；变量创建时每个 `flow_out` 与 `flow_in` 都进入 direction index。位置：`src/models/routing_subproblem.py:781-786`。

lazy cut/guard 的候选图语义为：按 `flow_out` 的每个方向找邻格上同 commodity 且 `flow_in` 含反向方向的候选状态；sink-front terminal output 不继续扩展。位置：`src/models/routing_subproblem.py:1017-1073`。这覆盖了 belt、splitter、merger 与跨 layer 接收，因为 index 本身不按 layer 限制，和 CP-SAT 的 aggregate successor/predecessor 约束一致。

我重点攻击了一个容易漏看的点：`_route_state_adjacency()` 对 sink-front output 的“不外扩”判断没有检查 `layer`，而 `_add_successor_constraints()` 的 terminal 豁免只在 `GROUND_LAYER`。枚举 audit 的确能找到 elevated sink-front output 状态，例如 `(5,0,1,('E',),('W'),'ore')` 的 outgoing `W` 在 CP-SAT successor 里需要后继，但 guard adjacency 会把它当 terminal 不外扩。

该点不是本轮 lazy cut soundness finding，原因如下：

1. 这种 omitted arc 只有在“第一次离开 W 的边”的源点也在 `W` 时才可能让 `X` 不完整。
2. 若 elevated sink-front output 状态 `u` 在 `W`，它不能是 source start；它必须由某个 `p in W` 经同方向输出到达。
3. 同一 sink front 的 port exact-one 要求有一个 ground sink state 被选中。若同 cell 还选中了 elevated bridge，`_add_bridge_constraints()` 禁止 ground non-straight；因此 ground sink state 只能是与 elevated bridge 同输入/同输出的 straight ground state。位置：`src/models/routing_subproblem.py:837-848`，直线判断与 non-straight index 在 `src/models/routing_subproblem.py:787-790`。
4. 于是从同一个 `p` 的 guard arc 会同时到达这个 ground sink state，使 ground sink candidate 落入 `W`。
5. 自检 1 会检测 `sink_front_inside_w` 并 fallback，不会添加 lazy cut。位置：`src/models/routing_subproblem.py:1223-1239`。

我构造了这个攻击形态：一个 commodity 有两个 sinks，source-side W 到达 sink1 的 ground sink state 和 elevated sink-output state，同时 sink2 仍不可达。结果 `_self_check_source_side_connectivity_cut()` 返回 `False, "sink_front_inside_w"`，不加 cut。这说明该 layer 细节会降低 cut 机会，但不会形成自检通过的 invalid cut。

### 3. W 与 X 的有效性

`X` 的有效性并不只依赖生成过程。自检 2 重新构建 full potential graph，删除传入的 `crossing`，从所有 potential source-front states 出发 BFS，并要求不可达任何 potential sink-front state。位置：`src/models/routing_subproblem.py:1241-1269`。

这条检查本身就是 vertex-cut 证书：若某个 guard-accepted connected routing 避开 `X`，它必然在删除 `X` 后仍提供一条 source-front candidate 到 sink-front candidate 的路径，和自检 2 矛盾。因此只要 potential graph 覆盖 guard 接受语义，`sum(X) >= 1` 就不会剪掉任何最终可接受的真 routing。

自检 3 还确认 incumbent selected set 与 `X` 交集为空，确保这条 cut 真能排除当前被拒 incumbent。位置：`src/models/routing_subproblem.py:1271-1276`。

### 4. 多 commodity 与容量交互

每个 cut 的 `potential_keys` 来自 `_potential_route_keys_for_commodity(commodity)`，只包含当前 commodity 的 route-state。位置：`src/models/routing_subproblem.py:1118-1119`。`crossing <= potential_keys` 又在自检中显式验证。位置：`src/models/routing_subproblem.py:1198-1201`。

共享 cell-layer 容量 `AddAtMostOne` 是跨 commodity 的全局约束，但 lazy cut 表达的是“当前 commodity 若要从 source front 连到 sink front，必须选中 X 中至少一个本 commodity state”。这是单 commodity 的必要条件；其他 commodity 只会进一步限制可行性，不会让这个必要条件失效。因此没有发现跨 commodity invalidity。

## Q2：自检独立性与 fail-closed

结论：未发现 silent no-op、无 cut/无 nogood 死循环，或 TIMEOUT/INFEASIBLE 语义漂移。

- `_add_source_side_connectivity_cut()` 先生成 `W` 和 `crossing`，然后调用 `_self_check_source_side_connectivity_cut()`。位置：`src/models/routing_subproblem.py:1278-1319`。
- 自检内部重新调用 `_terminal_fronts_by_commodity()`、`_potential_route_keys_for_commodity()`、`_compute_selected_source_side_closure()`、`_route_state_adjacency()`，重新算 `W`、source/sink terminal nodes 与 full graph BFS；没有信任传入的 `w_closure`。位置：`src/models/routing_subproblem.py:1185-1276`。
- 自检失败时 `_add_source_side_connectivity_cut()` 返回 `kind=fallback`，不加 cut。位置：`src/models/routing_subproblem.py:1313-1319`。
- `solve()` 对每个 failed commodity 单独尝试 cut；任一 fallback 都会触发一次原有 `_add_selected_route_nogood(solver)`，并记录 `{commodity, reason, nogood_size, diagnostics}`。位置：`src/models/routing_subproblem.py:1534-1568`。
- 若 guard diagnostics 没有 failed commodity，也会走 `no_failed_commodity_diagnostics` fallback，随后加 nogood。位置：`src/models/routing_subproblem.py:1547-1558`。
- 预算复用同一 deadline；每轮 solve 前重算 remaining，guard 已拒过 incumbent 后耗尽时间会返回 `TIMEOUT`，清空 `_solver` 并把 `_status` 置为 `UNKNOWN`。位置：`src/models/routing_subproblem.py:1471-1499`。
- `extract_routes()` 仍要求 CP-SAT status 为 feasible/optimal 且 `_connectivity_guard_accepted` 为 true。位置：`src/models/routing_subproblem.py:1587-1592`。

因此，cut 自检失败路径仍回到原 fail-closed guard loop；不会出现“拒绝了 incumbent 但既不加 cut 也不加 nogood 就重解”的静默循环。

## Q3：测试判别力

结论：新增测试对本步主风险有实际判别力；不是形式证明，但和上述代码级证明相互覆盖。

相关测试点：

- `test_routing_lazy_connectivity_cuts_converge_on_three_commodity_probe`：三 commodity 同时被拒，断言走 cut 路径且无 fallback。位置：`src/tests/test_p0_certified_soundness_fixes.py:276-323`。
- `test_routing_lazy_connectivity_cut_preserves_real_feasible_path`：先让 disconnected incumbent 因 objective 优先出现，再确认 lazy cut 后仍能找到 source→sink 真路径。位置：`src/tests/test_p0_certified_soundness_fixes.py:326-373`。
- `test_routing_lazy_connectivity_cut_self_check_falls_back_to_nogood`：monkeypatch 删掉一个必需 source candidate，确认自检报 `x_not_complete_crossing_boundary` 并 fallback。位置：`src/tests/test_p0_certified_soundness_fixes.py:376-420`。
- `test_routing_guard_checks_each_selected_commodity`：确认每个 failed commodity 都被记录，避免只处理第一个 commodity 的漏诊断。位置：`src/tests/test_p0_certified_soundness_fixes.py:221-273`。

我额外构造的两个 probe：

1. “alternate source state” probe：直接抽取 first lazy cut 的 `X`，确认 existing true path 命中 `X` 的第一个 source candidate，覆盖“同一 source front 换另一颗接收 state”的攻击。
2. “elevated sink-front output” probe：刻意让 W 包含 elevated sink-output 状态，同时还有另一个 sink 不可达；自检返回 `sink_front_inside_w` 并 fallback，覆盖 layer terminal mismatch 攻击。

## Q4：工程面

- targeted ruff：通过。
- py_compile：通过。
- telemetry 字段 `attempts / rejected_incumbents / cuts_added / cut_sizes / fallback_nogoods` 在成功与 fallback 路径均有填充。位置：`src/models/routing_subproblem.py:1444-1459`、`src/models/routing_subproblem.py:1521-1531`、`src/models/routing_subproblem.py:1571-1581`。
- benders loop 只消费 routing `solve()` 的状态和 `extract_routes()`，本步没有放松最终 guard 双门；外层接口未见破坏。
- 未发现新增 env knob；routing worker env 仍为原 CP-SAT worker 设置。位置：`src/models/routing_subproblem.py:1498-1504`。

## Finding 列表

本轮零 soundness finding。

没有附 unified diff；本轮未修改项目代码。
