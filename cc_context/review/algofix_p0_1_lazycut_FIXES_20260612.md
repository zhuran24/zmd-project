# P0-1 lazy source-side connectivity cut 修复说明

## 1. 修复范围

本补丁只修改 routing guard 的拒绝循环：`RoutingSubproblem.solve()` 仍然先求 CP-SAT incumbent，再调用 `_validate_selected_route_connectivity()` 做最终验收。若某个 commodity 的 selected route-state 图不能证明 source front → sink front 可达，则不再默认只加 selected-positive nogood，而是先尝试给该 commodity 加一条 lazy source-side connectivity cut。cut 生成或自检失败时，才回退到原 selected-positive nogood。

本补丁不把 per-commodity flow 一等编码进 CP-SAT；P1.3B 的 flow 编码仍未实现。

## 2. 割的定义

对被 guard 拒绝的 commodity `k`，使用与 `_validate_selected_route_connectivity()` 完全同构的有向 route-state arc 语义：state `u` 的某个 `flow_out=d` 指向邻格，邻格 state `v` 的 `flow_in` 含 `DIR_OPP[d]`，且同 commodity，则存在 `u -> v`。sink front 的 terminal output 不继续扩展。

令 `W` 为从 `k` 的所有 selected source-front states 出发、只沿 incumbent selected graph 可达的闭包。对可生成 cut 的拒绝 incumbent，自检会确认每个 source front 都在 `W` 中有 selected source-state，且没有 sink-front candidate state 落在 `W` 中。

令 `X` 为 full candidate graph 上的 source-side crossing vertex set。本实现把 `X` 定义为所有可能成为“第一颗 W 外 route-state”的候选 state：

1. 能直接接收 `k` 的 source front 输出、但不在 `W` 中的 candidate state；
2. 存在某个 `u in W`，且 full candidate graph 中有 guard 同构 arc `u -> v`，并且 `v not in W` 的 candidate state `v`。

随后添加：

```text
sum(r_var[s] for s in X) >= 1
```

这里 `X` 是 W 外第一节点集合，而不是 W 内边界节点集合。这样做有一个重要工程好处：若 incumbent 里某个 W 内 selected state 同时有未选中的 alternative receiver，不能因此让 selected state 本身落入 `X`，从而保证自检项 “incumbent selected ∩ X = empty” 有可验证含义。

## 3. 数学有效性证明

考虑任意真实可行的 routing 解。它必须为 commodity `k` 选择一条从某个 source front 到某个 sink front 的有向 candidate-state path。

如果该 path 的第一颗 source-front route-state 不在 incumbent 的 `W` 中，那么这颗 state 满足 “能接 source front 输出且不在 W 中”，因此属于 `X`，可行解选择了 `X` 中至少一个 state。

否则，该 path 从 `W` 中的 source-front state 开始。因为自检已确认没有 sink-front candidate state 在 `W` 中，而 path 终点必须到达 sink front，所以 path 必然存在第一次离开 `W` 的位置。设这次跨越为 `u -> v`，其中 `u in W` 且 `v not in W`。该 arc 按 guard 同构语义存在于 full candidate graph，因此 `v` 按定义属于 `X`。可行解同样选择了 `X` 中至少一个 state。

于是任何真实可行 routing 都满足 `sum(X) >= 1`。这条不等式只依赖 incumbent 诱导出的集合 `W` 和模型的 candidate graph，不假设 incumbent 本身可行连通，因此不会误杀真实可行解。

它也强于 selected-positive nogood：被拒 incumbent 的 selected set 与 `X` 交集为 0，所以 cut 排除当前 incumbent；并且所有拥有相同 source-side selected closure 的同类 incumbent 都必须改变第一颗 W 外 state，属于“一刀一族”。原 nogood 只禁止当前 selected set 的超集，是“一刀一个”。

## 4. 三项 fail-closed 自检

每条 cut 进入 model 前都由 `_self_check_source_side_connectivity_cut()` 重新计算证书，生成过程本身不被信任。

第一项重新构造 selected graph，重新 BFS 得到 `W`，检查全部 source front 在 `W` 中有 selected source-state，并检查全部 sink-front candidate state 不在 `W`。这覆盖 terminal 侧前提，避免对已经含 sink 的 W 错加 source-side cut。

第二项重建 full potential candidate-state graph，删除 `X`，再从全部 source-front candidate state 重新 BFS。若任何 sink-front candidate state 仍可达，则说明 `X` 不是完整 crossing boundary，cut 不会加入。

第三项检查 incumbent selected set 与 `X` 的交集为空。若交集非空，`sum(X) >= 1` 不能切掉当前 incumbent，循环可能不进展，因此 fail-closed。

任一项失败时，`solve()` 调用原 `_add_selected_route_nogood()`，并把 `{commodity, reason, nogood_size, diagnostics}` 记录进 `build_stats["last_solve"]["connectivity_guard"]["fallback_nogoods"]`。

## 5. Telemetry

`build_stats["last_solve"]["connectivity_guard"]` 现在包含：

```text
attempts
rejected_incumbents
cuts_added
cut_sizes
fallback_nogoods
```

`rejected_incumbents` 保留原语义；`cuts_added` 和 `cut_sizes` 记录通过自检并实际加入 model 的 source-side cuts；`fallback_nogoods` 记录每个 cut 自检失败后的回退原因。

## 6. env-off / exploratory 影响

本补丁没有新增环境变量，也没有改变 certified / exploratory 的外层分流。lazy cut 默认启用，但只会添加自检通过的有效不等式；自检失败回退到原 selected-positive nogood。最终是否可接受仍由 `_validate_selected_route_connectivity()` 和 `_connectivity_guard_accepted` 双门决定，`extract_routes()` 的门禁未放松。

## 7. 三件套与文件清单

- `src/models/routing_subproblem.py`：新增 candidate/selected graph helper、source-side crossing cut、自检、telemetry，并保留 guard 最终验收边界。
- `src/tests/test_p0_certified_soundness_fixes.py`：保留既有 7 条 P0 regression，并新增 lazy cut 收敛、完整性保真、自检回退、多 commodity telemetry 断言。
- `PROJECT_LOCK.md`：新增 P0-1 lazy cut 不变式。
- `specs/09_exact_grid_routing_subproblem.md`：新增 §9.8 lazy source-side connectivity cuts，写明割形状、有效性证明、自检义务和 fallback 语义。
- `FILE_STATUS.md`：同步 routing runtime/spec 的 source-of-truth 说明。

## 8. Probe 输出

修前 nogood-only 三 commodity disconnected probe：

```json
{
  "attempt_statuses": ["OPTIMAL", "INFEASIBLE"],
  "cut_sizes": [],
  "cuts_added": 0,
  "fallback_nogoods": [],
  "first_failure_count": 3,
  "first_nogood_size": 24,
  "probe": "three_commodity_fixed_disconnected",
  "rejected_incumbents": 1,
  "status": "INFEASIBLE"
}
```

修后同一 probe 走 cut 路径：

```json
{
  "attempt_statuses": ["OPTIMAL", "INFEASIBLE"],
  "cut_sizes": [5, 5, 5],
  "cuts_added": 3,
  "fallback_nogoods": [],
  "first_failure_count": 3,
  "first_nogood_size": null,
  "probe": "three_commodity_fixed_disconnected",
  "rejected_incumbents": 1,
  "status": "INFEASIBLE"
}
```

修后 feasible corridor preservation probe：

```json
{
  "accepted_routes": 11,
  "attempt_statuses": ["OPTIMAL", "OPTIMAL", "OPTIMAL"],
  "cut_sizes": [9, 9],
  "cuts_added": 2,
  "fallback_nogoods": [],
  "probe": "feasible_corridor_disconnected_incumbent_first",
  "rejected_incumbents": 2,
  "status": "FEASIBLE"
}
```

## 9. 自验命令

```text
python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored

python -m pytest -q --randomly-dont-reset-seed src/tests/test_p0_certified_soundness_fixes.py
10 passed in 3.39s

python -m py_compile src/models/routing_subproblem.py src/tests/test_p0_certified_soundness_fixes.py
OK

python -m ruff check src/models/routing_subproblem.py
All checks passed!

python -m ruff check src/tests/test_p0_certified_soundness_fixes.py
All checks passed!

python -m mypy --strict --explicit-package-bases src/cuts/
Success: no issues found in 36 source files
```
