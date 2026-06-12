# 终末地 IndustrialPlanner Benders/LBBD 主循环 round 6 审查报告

审查基点：`zmd_snapshot_70457b5e.zip`  
期望 sha256：`70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`  
实测 sha256：`70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`  
结论：快照匹配后解包审查；未使用文件区其它快照包。

## 总结

本轮零 soundness finding。

确认 R5-PS 修复有效：`EXACT_POWER_PLACEMENT_SUBPROBLEM` forensic 分支在非契约/ABORT/TIMEOUT 路径会写入 fail-closed proof summary 并返回 `UNKNOWN`，没有发现 status × summary 错配残留。cut 生命周期、condition literal 解析、缓存复用与 proof 消费关系未发现 over-cut / stale-proof / 跨 iteration 污染。

本轮发现并修复 1 个 LOW 完整性/状态契约问题：certified 主循环达到 `max_iterations` 时，原始快照返回 `RUN_STATUS_UNPROVEN`，而该路径本质是迭代预算耗尽，应与 timeout/cap 语义一致 fail-closed 为 `UNKNOWN`。该问题不铸 cut、不返回 `INFEASIBLE`/`CERTIFIED`，因此不构成 soundness finding。

补丁文件：`zmd_benders_loop_r6.patch`。

## Findings

### F-BL-R6-01 — LOW — certified max-iteration cap 返回 UNPROVEN，而非 UNKNOWN

位置：原始快照 `src/search/benders_loop.py:4712-4724`；补丁后 `src/search/benders_loop.py:4712-4728`。  
性质：完整性/状态契约；非 soundness。

论证：`_run_certified_exact()` 的主循环耗尽 `self.max_iterations` 后，原始快照写入 `master_status="MAX_ITERATIONS"` summary，但返回 `RUN_STATUS_UNPROVEN`。这个出口不是数学穷尽证明，也不是认证阻断；它是 search/iteration budget exhaustion。按本面的 Q3 要求以及 r3 的预算耗尽修复口径，cap 命中必须 fail-closed 到 `UNKNOWN/TIMEOUT` 类状态，不能落入不透明的 `UNPROVEN`。该路径没有调用 `_add_exact_persisted_nogood()`，也没有返回 `RUN_STATUS_INFEASIBLE` 或 `RUN_STATUS_CERTIFIED`，所以不会错误剪枝或错误证明 infeasible。

复现 probe（原始快照）：构造 `LBBDController(max_iterations=0, solve_mode="certified_exact")`，master stub 只提供 `build_exact_candidate_warm_start()`；调用 `run_with_status()` 得到 `UNPROVEN, None`，`last_proof_summary["master_status"] == "MAX_ITERATIONS"`。

修法：将该出口改为 `RUN_STATUS_UNKNOWN`，补 `master_follow_up="fail_closed_unknown"`，并带上 `_master_search_summary()`，使 summary 形状与其它 master/budget unknown 出口对齐。新增回归：`src/tests/test_exact_contract.py:3750-3787`，断言 max-iteration cap 不生成 exact-safe cut，返回 `RUN_STATUS_UNKNOWN`，并写入 `master_follow_up="fail_closed_unknown"`。

## Q1 — R5-PS 修复确认

R5-PS 修复点位于 `src/search/benders_loop.py:4528-4555`。当 `EXACT_POWER_PLACEMENT_SUBPROBLEM` 打开且 `_run_power_placement_subproblem()` 返回非 `FEASIBLE` / 非 `INFEASIBLE_CUT_ADDED` 状态时，当前代码写入：`mode`、`benders_iterations`、`master_status="FEASIBLE"`、`stage="power_placement_subproblem"`、`power_placement_status`、`diagnostic_flow_status`、`enumerated_bindings=0`、`routing_attempts=0`、`master_follow_up="fail_closed_unknown"`，并合并 warm-start / master-search / subproblem-reuse / cut-ladder summary 后返回 `RUN_STATUS_UNKNOWN`。

下游 telemetry 发布 `_publish_last_run_metadata()` 使用 `.get(..., default)` 读取 fine-grained cut、routing shrink、routing domain 等可选字段，不会因该分支缺少 routing/binding summary 触发 KeyError；见 `src/search/benders_loop.py:1039-1095`。公开 certified 链上，非 canonical `EXACT_POWER_PLACEMENT_SUBPROBLEM` 会被 certified env guard 拦截为 `master_status="BLOCKED"`，不会悄悄进入主链；见 `src/search/benders_loop.py:836-907` 与 `src/search/benders_loop.py:6288-6320`。

其它 power status 分支也未见错配：`FEASIBLE` 只注入 power witness 后回到主链；`INFEASIBLE` 只有在存在当前 ghost anchor、构造 `condition_set` 与 `condition_lits` 后才调用 `_add_exact_persisted_nogood()`；缺 conflict、缺 ghost anchor、cut 未成功或 `TIMEOUT` 全部返回 `ABORT`，由 R5-PS 修复分支收敛到 `UNKNOWN`。相关代码见 `src/search/benders_loop.py:4762-4869`。

## Q2 — cut 类型 × 有效性依据矩阵

| cut 类型 | 加入位置 | 有效性依据 | 跨 iteration / condition / cache 判读 |
|---|---:|---|---|
| `binding_pose_domain_empty_nogood` / `rab_sep_clear_deficit_certificate` | `src/search/benders_loop.py:5005-5094` | 当前 placement 下某 owner pose 的 binding domain 为空；RAB certificate 形态还包含当前 blocker poses。 | placement-local nogood，不依赖 iteration 号。cut 失败则返回 `UNKNOWN` 或继续其它证据，不退化为强证明。|
| `binding_infeasible_nogood` | `src/search/benders_loop.py:5183-5213` | 当前 whole-layout 的 binding CP-SAT 返回 `INFEASIBLE`；overload fallback 先按契约重解，retry TIMEOUT/unexpected 都 fail-closed。 | whole-layout conflict 仅禁当前 master solution 的 pose 组合。应用失败返回 `UNKNOWN`。|
| `routing_front_blocked_nogood` fallback | `src/search/benders_loop.py:5377-5701` | routing precheck 对当前 binding/placement 得到 `front_blocked`，fallback 使用 `placement_level_conflict_set`。binding-selection safe-reject 在仍有 alternatives 时先局部排除当前 binding。 | placement-local；env-gated ladder 变体在公开 certified 下由 env guard 阻断。无 unconditional 降级。|
| `routing_exhausted_nogood` | `src/search/benders_loop.py:5941-5968` | 当前 placement 的 binding alternatives 已穷尽，所有 routing attempts 均 infeasible 后，才加 whole-layout nogood。 | 不依赖 iteration 瞬态；若 power witness incomplete 或 master 不能表达该 conflict，则 cut application 返回 False，caller 返回 `UNKNOWN`。|
| routing lazy connectivity cut / selected-route nogood | `src/models/routing_subproblem.py:1727-1841` | routing 子问题内部发现 CP-SAT incumbent 不连通时，对同一个 routing model 增加 source-side cut 或 selected route nogood。 | subproblem-local，不持久化到 master，不跨 candidate/iteration 消费。guard deadline 用 `perf_counter()`，超时返回 `TIMEOUT`。|
| `power_subproblem_infeasible_nogood` | `src/search/benders_loop.py:4802-4866` | power subproblem infeasible 且能定位当前 selected ghost anchor；metadata 与 `condition_set` 一致。 | 必须 ghost-conditioned。`BendersCut.from_dict()` 强校验 condition-required metadata；condition 无法解析时 replay skip，不能转成 unconditional cut。|
| persisted `exact_safe_cuts` replay | `src/search/benders_loop.py:6560-6602` | certified replay 被强制置空，当前仅统计 replay input count。 | telemetry-only，不作为 proof；即使未来启用，condition 解析失败也 skip。|

condition literal 解析失败的处理是 fail-closed：`_resolve_condition_lits_from_condition_set()` 明确返回 `( [], False )`，caller 必须 skip cut；未知 key、非 int rect index、anchor parse 失败、u_var 缺失、anchor 与 ghost domain 不一致都会失败，见 `src/search/benders_loop.py:1488-1533`。`CutManager` 还要求 condition-required power cut 必须带 condition_set 且 metadata 与 ghost anchor 匹配，见 `src/models/cut_manager.py:186-210`；dedup signature 包含 condition，避免 ghost A 与 ghost B 下的同 conflict 被吞并，见 `src/models/cut_manager.py:419-428`。

master 侧 cut 应用也是 all-or-nothing：exact-coordinate master 对 conflict member 解析失败、pose 缺失、alias 到同一个 presence literal 等情况返回 False；成功时添加 `sum(present_lits) <= N-1`，condition literal 通过 `OnlyEnforceIf` 保留，并清空 `_last_solution`，见 `src/models/exact_coordinate_master.py:6809-6920`。因此“cut 已加入但 master 原样返回同一解”的正常路径被排除；若 cut dedup / apply fail，则 caller 不把它当作有效削减。

## Q2 — 缓存 proof-bearing vs telemetry-only 判读

| 缓存/复用项 | 位置 | 判读 |
|---|---:|---|
| pose-level binding domain cache | `src/models/port_binding.py:28-90`, `src/models/port_binding.py:113-140` | proof-safe。key 是 operation type + 相对 port cell/dir signature；缓存值是 immutable pattern tuple，每次 materialize 成新的 binding dict/list。|
| routing-aware binding domain filter | `src/models/binding_subproblem.py:563-637` | proof-safe。layout-local filter 在 raw cache 之后执行，返回新 list，不污染 raw cache；certificate 从当前 placement owner/blocker pose 构造。|
| binding CP-SAT solve summary/cache telemetry | `src/models/binding_subproblem.py:935-970`, `src/models/binding_subproblem.py:1075-1085` | solve status proof-bearing，cache hit/miss 仅 telemetry。TIMEOUT 统一映射为 `TIMEOUT`，由 caller fail-closed。|
| routing placement core / domain analysis reuse | `src/models/routing_subproblem.py:633-654`, `src/models/routing_subproblem.py:801-812` | proof-safe。analysis 绑定当前 placement core、port specs 与当前 binding selection；只在同一 routing attempt 内复用。|
| routing shrink counters / core timing / overlay timing | `src/search/benders_loop.py:1039-1095` | telemetry-only。未作为 infeasible/certified proof 消费。|
| pre-master coordinate / mandatory precheck budgets | `src/search/benders_loop.py:1899-1994`, `src/search/benders_loop.py:6743-6758` | partial/UNKNOWN 不触发强结论；mandatory precheck 显式排除 `partial_due_to_time_budget`。|
| persisted exact_safe cut replay input count | `src/search/benders_loop.py:6560-6577` | telemetry-only。certified run 把 replay list 清空，fresh proof 必须在当前进程再生成。|

## Q3 — 时间预算传递与耗尽出口清单

| stage / 出口 | 预算来源 | 终态判读 |
|---|---|---|
| master solve | `self.master_seconds` 传给 `master.solve(time_limit_seconds=...)`，见 `src/search/benders_loop.py:4431-4440` | CP-SAT unknown/timeout 类状态进入 `master_status="UNKNOWN"` 并返回 `RUN_STATUS_UNKNOWN`，见 `src/search/benders_loop.py:4488-4501`。|
| master infeasible | 同上 | 只有 CP-SAT `INFEASIBLE` 才返回 `RUN_STATUS_INFEASIBLE`，见 `src/search/benders_loop.py:4473-4487`。|
| certified iteration cap | `self.max_iterations` | 原始快照返回 `UNPROVEN`；本轮补丁改为 `UNKNOWN` + `master_follow_up="fail_closed_unknown"`，见 `src/search/benders_loop.py:4712-4728`。|
| binding initial solve | `self.binding_seconds`，见 `src/search/benders_loop.py:5100-5109` 与 `src/models/binding_subproblem.py:935-970` | `TIMEOUT` 返回 `RUN_STATUS_UNKNOWN`，见 `src/search/benders_loop.py:5109-5123`。|
| binding overload fallback retry | `self.binding_seconds` | retry `TIMEOUT` 返回 `UNKNOWN`，unexpected binding status 走 `_record_unexpected_binding_status()` fail-closed，见 `src/search/benders_loop.py:5159-5182`。|
| routing precheck safe-reject 后 binding resolve | `self.binding_seconds` | re-solve `TIMEOUT` 返回 `UNKNOWN`，并写 `master_follow_up="fail_closed_unknown"`，见 `src/search/benders_loop.py:5328-5364`。|
| relaxed-disconnected precheck 后 binding resolve | `self.binding_seconds` | re-solve `TIMEOUT` 返回 `UNKNOWN`，见 `src/search/benders_loop.py:5703-5738`。|
| routing model solve | `self.routing_seconds`，见 `src/search/benders_loop.py:5800` | routing `TIMEOUT` 返回 `RUN_STATUS_UNKNOWN`，见 `src/search/benders_loop.py:5821-5838`。|
| routing connectivity guard | routing subproblem 内 `time.perf_counter()` deadline，见 `src/models/routing_subproblem.py:1727-1755` | guard deadline 耗尽返回 `TIMEOUT`，被 benders loop 映射为 `UNKNOWN`。|
| binding alternative cap | env `EXACT_B1_BINDING_ALT_CAP` | cap 只代表预算/枚举截断；仍有 alternatives 时返回 `UNKNOWN`，见 `src/search/benders_loop.py:5860-5891`。|
| routing infeasible 后 binding alternatives resolve | `self.binding_seconds` | re-solve `TIMEOUT` 返回 `UNKNOWN`，见 `src/search/benders_loop.py:5904-5922`。|
| power placement forensic subproblem | env `EXACT_POWER_SUBPROBLEM_SECONDS`，公开 certified 默认被 env guard 拦 | `TIMEOUT`/其它状态返回 `ABORT`，由 R5-PS repaired caller 返回 `UNKNOWN`，见 `src/search/benders_loop.py:4528-4555` 与 `src/search/benders_loop.py:4868-4869`。|
| coordinate forced-anchor precheck | caller 传入 `time_limit_seconds` | 非 `INFEASIBLE` 状态短路为 non-triggering；不会用 UNKNOWN/TIMEOUT 证明 infeasible，见 `src/search/benders_loop.py:1899-1994`。|
| mandatory rectangle precheck | precheck 自身预算 | `partial_due_to_time_budget` 被排除，不触发强剪枝，见 `src/search/benders_loop.py:6743-6758`。|
| routing precheck / routing build | deterministic 70×70 域分析；`build(time_limit)` 显式 `del time_limit`，见 `src/models/routing_subproblem.py:633-654` 与 `src/models/routing_subproblem.py:801-812` | 未发现 status-bearing timeout；它们是有界域分析/模型构建，不产生 timeout 强证明。|
| flow diagnostic | `self.flow_seconds` 转 ms 传入 diagnostic flow | certified 主链中为诊断字段；未作为 `CERTIFIED`/`INFEASIBLE` proof 消费。|

时间测量：routing solve 的 deadline 使用 `time.perf_counter()`，core/overlay timing 也使用单调时钟；binding/master 的实际 wall limit 交给 CP-SAT `max_time_in_seconds`。routing solve 即便 `time_limit=0` 也会给 CP-SAT 一个 `0.001s` 最小尝试窗口，但循环在第一次 rejected incumbent 后检查 deadline 并返回 `TIMEOUT`。未发现 stage 内部无界自旋且不检查预算的路径；precheck/build 是 70×70 网格和有限 port/spec 集上的确定性循环。

## 回归与验证

已执行：

```bash
sha256sum /mnt/data/zmd_snapshot_70457b5e.zip
PYTHONPATH=. python3.13 -m pytest -q \
  src/tests/test_exact_contract.py::test_certified_max_iterations_cap_returns_unknown_without_exact_safe_cut \
  src/tests/test_exact_contract.py::test_power_placement_abort_returns_unknown_with_matching_proof_summary \
  -p no:randomly
PYTHONPATH=. python3.13 -m pytest -q src/tests/test_exact_contract.py -p no:randomly
PYTHONPATH=. python3.13 -m pytest -q \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_p0_certified_soundness_fixes.py \
  -p no:randomly
PYTHONPATH=. python3.13 scripts/check_p1_2_proof_obligations.py
```

结果：

- sha256 匹配。
- 新增 cap 回归 + R5-PS 回归：`2 passed`。
- `src/tests/test_exact_contract.py`：`95 passed`。
- `test_exact_campaign_state_soundness.py` + `test_p0_certified_soundness_fixes.py`：`14 passed`。
- proof obligation：`P1.2 proof obligation check passed: 8 obligations anchored`。

补充：尝试执行 `PYTHONPATH=. python3.13 -m pytest -q src/tests -p no:randomly`，在沙盒 300 秒限制内超时，超时前无失败输出；因此本轮未声称全量 `src/tests` 完跑。`python3.13 -m ruff ...` 未执行成功，原因是当前 Python 3.13 环境中未安装 `ruff`。
