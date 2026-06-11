# 终末地 IndustrialPlanner P0-1 lazy connectivity cut 审查

## 结论

本轮零 soundness finding。

我没有找到 lazy source-side connectivity cut 会剪掉真实 routing 解的残留缺陷；也没有找到自检失败后静默吞掉拒绝、预算语义漂移、跨 commodity 污染或 telemetry 破坏外层接口的问题。本轮未提供补丁，因为没有需要修复的 finding。

## 审查范围

重点审查文件与行段：

- `src/models/routing_subproblem.py:603-615`：source/sink front 建索引。
- `src/models/routing_subproblem.py:673-711`：ground belt/splitter/merger 与 elevated bridge state pattern。
- `src/models/routing_subproblem.py:832-848`：cell-layer capacity 与 bridge/ground coexistence 约束。
- `src/models/routing_subproblem.py:865-938`：successor/predecessor continuity 约束。
- `src/models/routing_subproblem.py:940-973`：port adherence exact-one。
- `src/models/routing_subproblem.py:1017-1073`：candidate/selected route-state graph 与 adjacency。
- `src/models/routing_subproblem.py:1121-1176`：`W` 与 `X` 构造。
- `src/models/routing_subproblem.py:1178-1326`：lazy cut self-check 与 cut 添加。
- `src/models/routing_subproblem.py:1334-1430`：最终 connectivity guard。
- `src/models/routing_subproblem.py:1471-1585`：guard rejection solve loop、fallback nogood、TIMEOUT/INFEASIBLE 语义。
- `src/tests/test_p0_certified_soundness_fixes.py:123-420`：P0 guard 与 lazy cut 回归测试。
- `specs/09_exact_grid_routing_subproblem.md:100-130` 与 `PROJECT_LOCK.md:91`：规格与 proof obligation 对齐。

## 关键 soundness 论证

### 1. Source/sink front 语义与 port adherence 对齐

`_index_port_fronts()` 对输出端口使用 `recv_dir = DIR_OPP[direction]`，对输入端口使用原 `direction` 建 sink front；`_add_port_adherence()` 对 source front 的 ground `flow_in` 和 sink front 的 ground `flow_out` 分别加 exact-one。`_terminal_nodes_by_front_for_keys()` 也只把 ground source/sink terminal state 作为 terminal node。因此 lazy cut 的 source start 和 sink target 与 CP-SAT 的端口履行变量集合一致。

若某 source front 在 incumbent 中没有 selected source-state，`_self_check_source_side_connectivity_cut()` 的 `source_front_not_in_w` 分支会失败并回退 nogood；不会在缺 source 证据时加 cut。

### 2. Arc 语义没有发现会导致 invalid cut 的窄化

对普通输出，`_add_successor_constraints()` 要求 `u.flow_out=d` 时邻格存在同 commodity、`flow_in=DIR_OPP[d]` 的接收 state；`_add_predecessor_constraints()` 是同一关系的反向支撑。`_route_state_adjacency()` 用同一条 directed relation 建图：同 commodity、邻格、输出方向与输入反向匹配。它同样跨 layer，因为 CP-SAT 的 `_vars_by_cell_dir_in_commodity` / `_vars_by_cell_dir_out_commodity` 索引也跨 layer；因此 ground/elevated bridge 之间的邻格接续没有被 lazy graph 漏掉。

Splitter/merger 的多入多出也被逐方向展开：CP 约束对每个 `flow_out` / `flow_in` 分别加支撑，candidate graph 也逐方向枚举。graph 未编码 cell capacity、bridge coexistence、AtMostOne 等组合约束，这只会让 potential graph 变宽，不会让 cut 误杀可行 path；在更宽图上通过“删 X 后 source 不可达 sink”的 separator 检查，仍是安全证书。

### 3. Sink terminal 不外扩的同构盲区被 fail-closed 条件盖住

显式攻击过 terminal-output skip，尤其是 elevated bridge 位于 sink-front cell 且 `flow_out` 等于 sink direction 的角落。代码里 `_route_state_adjacency()` 对 sink-front direction 不外扩，而 CP successor exemption 只对 ground sink-front output 生效；这看起来像可能的“共同遗漏”。进一步从约束倒推后，没有形成 invalid cut：

- 对 ground sink-front output，若 omitted terminal arc 的 source node 在 `W`，该 node 本身就是 sink-front candidate，self-check ① 的 `sink_front_inside_w` 必然回退；若它不在 `W`，任何 path 使用该 omitted arc 前已经选择了第一颗 `W` 外 state，cut 已被满足。
- 对 elevated sink-front-direction bridge，若 elevated bridge node 在 `W`，它必须由某个 predecessor state 接入。port adherence 同时强制该 sink front 选择一个 ground `flow_out=d` state；bridge coexistence 约束只允许该 ground state 是 straight belt，也就是同样的 `flow_in=DIR_OPP[d]`。于是接入 elevated bridge 的 predecessor 在 guard graph 中也会接入这个 ground sink state，导致 sink candidate 落入 `W`，self-check ① 回退。若 elevated bridge node 不在 `W`，它本身或更早的 first outside state 已经在 `X`。

我用一个专门 probe 验证了这个角落：构造 sink-front `(2,1,'E')` 上的 elevated bridge `(2,1,1,('W',),('E',),'ore')` 进入 `W`，self-check 返回 `False, sink_front_inside_w`，没有加 lazy cut。

### 4. `X` 的有效性不依赖生成过程可信

即使 `_source_side_crossing_boundary()` 生成的 `X` 有 bug，只要 `_self_check_source_side_connectivity_cut()` 通过，核心有效性来自证书②：在 full potential graph 删除 `X` 后，从全部 source-front candidate state BFS 不可达任何 sink-front candidate state。于是任何最终 guard-accepted routing 都必须含有一条 source candidate 到 sink candidate 的 directed path；该 path 若不选 `X`，会与证书②矛盾。

证书③ `selected ∩ X = ∅` 保证 cut 真切掉当前 incumbent；证书① 保证 source 侧 closure 前提成立且不会对已含 sink 的 `W` 乱加 source-side cut。任一证书失败，`solve()` 会走 `_add_selected_route_nogood()` fallback，不存在“不加 cut 也不加 nogood 就继续”的死循环。

### 5. 多 commodity 与 capacity 不造成 cross-contamination

`_potential_route_keys_for_commodity()` 用 `key[5]` 按 commodity 过滤，cut vars 只来自当前失败 commodity 的 `r_vars`。共享 cell/layer capacity 是全局限制，但它只会减少可行解集合；per-commodity source→sink 必要条件本身不依赖其他 commodity。因此没有发现跨 commodity 的 invalid cut 路径。

## 实际 probe 与命令结果

环境与完整性：

```text
sha256 zmd_v80_impl_full_20260612_single.zip = 9e21ca319186e64786627a1a9ed77a507959d6113bbd38c136aa8162a7ee96ac
```

基线与工程检查：

```text
PYTHONPATH=. python3.13 -m pytest -q --randomly-dont-reset-seed src/tests/test_p0_certified_soundness_fixes.py
=> 10 passed in 4.63s

PYTHONPATH=. python3.13 scripts/check_p1_2_proof_obligations.py
=> P1.2 proof obligation check passed: 8 obligations anchored

PYTHONPATH=. python3.13 -m ruff check src/models/routing_subproblem.py src/tests/test_p0_certified_soundness_fixes.py
=> All checks passed!

PYTHONPATH=. python3.13 -m mypy --strict --explicit-package-bases src/cuts/
=> Success: no issues found in 36 source files
```

补充 probe 1：复现“断开 incumbent 被 cut 后真路径仍保留”的核心断言，并直接检查 connected path 与 `X` 的交集不是偶然。

```text
selfcheck True ok W 4 X 9 disc∩X 0 connected∩X [(1, 0, 0, ('W',), ('E',), 'ore')]
```

含义：被拒 incumbent 不选 `X`，而保真的真路径选择了 source-front alternative state，正好落在定义①的 `X` 中。

补充 probe 2：攻击 elevated bridge + sink-front terminal skip 角落。

```text
W size 4 contains elevated True contains ground sink True
self-check False sink_front_inside_w {'commodity': 'ore', 'source_fronts': [[1, 0, 'W']], 'sink_fronts': [[2, 1, 'E']], 'w_size': 4, 'x_size': 0, 'sink_fronts_inside_w': [[2, 1, 'E']]}
```

含义：这个最像“graph 共同漏弧”的 case 没有穿过自检；实现回退 nogood，不加 lazy cut。

我也运行了 `PYTHONPATH=. python3.13 -m mypy --strict --explicit-package-bases src/models/routing_subproblem.py`。该目标当前有 45 个类型检查错误，主要来自 OR-Tools `cp_model` stub 未暴露 `Add/NewBoolVar/AddBoolOr` 等 CamelCase API、以及本文件既有未标注函数；它不是本补丁声称的 mypy gate，也未对应 lazy cut soundness finding。

## 测试判别力评估

新增测试能覆盖本步关键行为：

- `test_routing_lazy_connectivity_cuts_converge_on_three_commodity_probe` 验证多 commodity rejected incumbent 走 cut 路径而非 nogood-only。
- `test_routing_lazy_connectivity_cut_preserves_real_feasible_path` 不只是“最后能 FEASIBLE”，补充 probe 显示真路径确实命中本轮 `X`，所以它对 invalid source-start cut 有判别力。
- `test_routing_lazy_connectivity_cut_self_check_falls_back_to_nogood` 用 monkeypatch 删除必要 source candidate，触发 `x_not_complete_crossing_boundary`，覆盖 self-check 失败回退。
- 既有 timeout/extract gate 测试确认 rejected stale incumbent 不会通过 `extract_routes()` 泄露。

这些测试不是形式化证明，但与上述 line-level 约束核对互相咬合，没有发现“测试侥幸过但实现 invalid”的残留路径。

## Findings

无。

本轮零 soundness finding。
