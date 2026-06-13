# 终末地 IndustrialPlanner Benders/LBBD 主循环 r7 真 Pro 重审

审查快照：`zmd_snapshot_5e5e0c86.zip`

SHA256 校验：`5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`，与任务给定值一致。

审查范围：`src/search/benders_loop.py` 为核心，沿 Q1 status 契约、Q2 cut/cache 生命周期单调性、Q3 timeout 出口追踪到 binding/routing/flow/cut-manager/pose-bool delegate/patch/D2/separator 相关消费点。未重报 preprocess、cuts 独立面、master 几何、binding 面历史 finding。

## 结论

本轮不是零 finding。发现并修复 1 个 HIGH soundness finding：routing precheck 的非白名单状态没有在 LBBD 主循环入口处 fail-closed，可能被 routing model build 转译成 CP-SAT `INFEASIBLE`，继而铸造 master cut。

补丁已加入：

- `src/search/benders_loop.py`
- `src/tests/test_exact_contract.py`

## Finding F-BL-R7-01

Severity: HIGH

文件与位置：

- `src/search/benders_loop.py:5294-5331`（原 routing precheck 消费点；补丁后为 `:5294-5357`）
- `src/models/routing_subproblem.py:821-823`
- regression: `src/tests/test_exact_contract.py:3867-3994`

### 问题

`_run_exact_binding_and_routing()` 从 `run_exact_routing_precheck()` 读取 `routing_precheck["status"]` 后，原代码只显式处理：

- `front_blocked`
- `relaxed_disconnected`
- 其它状态隐式进入 routing model build / solve 路径

这形成了一个 status 契约缝。当前 `RoutingSubproblem.build()` 对传入的 `domain_analysis` 执行如下语义：只要 `analysis["status"] != "feasible"`，就向 routing CP-SAT 加入 `0 == 1`，使 routing solver 返回 `INFEASIBLE`。因此，如果 routing precheck 将来或异常路径返回 `TIMEOUT`、`UNKNOWN`、`MODEL_INVALID`、`ERROR`、拼写错误状态，甚至带有 `_analysis.status = TIMEOUT` 的结果，主循环会把“precheck 未证明”升级为“routing 不可行证明”。后续在无 binding alternatives 或 binding exhausted 时，可能进入 `_add_exact_whole_layout_nogood()`，把当前 master layout 当作 exact-safe cut 切掉。

这是典型 LBBD unsoundness：非证明状态被转译为 infeasible 证明，可能删除合法 master 解。

### 复现 probe / regression

新增回归：`test_unexpected_routing_precheck_status_returns_unknown_without_routing_cut`。

probe 结构：

1. monkeypatch `run_exact_routing_precheck()` 返回 `{"status": "TIMEOUT", "_analysis": {"status": "TIMEOUT"}}`。
2. monkeypatch `RoutingSubproblem` 构造函数为若被调用即 `AssertionError`。
3. monkeypatch whole-layout nogood 路径为若被调用即 `AssertionError`。
4. 期望结果：`RUN_STATUS_UNKNOWN`，`generated_exact_safe_cuts == []`，proof summary 标记 `subproblem_status_contract_violation == "unexpected_routing_precheck_status"`。

原路径没有白名单，会继续构造 routing subproblem；真实 routing model 会因 `analysis.status != feasible` 加 `0 == 1`，fake regression 则直接失败。补丁后 regression 通过。

### 修复

补丁内容：

1. 增加 `_EXACT_ROUTING_PRECHECK_VERIFIED_STATUSES = {"feasible", "front_blocked", "relaxed_disconnected"}`。
2. routing precheck 调用捕获非 `TypeError` 异常并转成 `{"status": "ERROR", ...}`，再走统一 status 契约。
3. 在任何 B1 bypass、front-blocked cut、relaxed-disconnected branch、routing build 之前加入白名单检查。
4. 任何非白名单 precheck status 都立即设置 proof summary：
   - `routing_status = PRECHECK_<STATUS>`
   - `subproblem_status_contract_violation = unexpected_routing_precheck_status`
   - `master_follow_up = fail_closed_unknown`
   - 返回 `RUN_STATUS_UNKNOWN, None`
5. 不构造 routing subproblem，不加 master cut，不登记 exact-safe cut。

### Unified diff

见随附补丁包：`zmd_r7_lbbd_soundness.patch`。

## Q1 status 消费点逐点判读表

| 消费点 | 允许/证明状态 | 非预期 / timeout / 空解处理 | 判读 |
|---|---:|---|---|
| certified master solve | CP-SAT `OPTIMAL/FEASIBLE` 继续；`INFEASIBLE` 返回 terminal infeasible | 其它 CP-SAT status 归 `UNKNOWN`；empty extracted solution 归 `UNKNOWN` | sound |
| exploratory master solve | `OPTIMAL/FEASIBLE` 继续；`INFEASIBLE` 返回 infeasible | 其它 status 归 `UNKNOWN`；empty solution 归 `UNKNOWN` | sound；exploratory max-iteration 返回 `UNPROVEN`，不铸 exact-safe proof |
| power placement subproblem consumer | `FEASIBLE` 注入 witness；`INFEASIBLE_CUT_ADDED` 继续 master | 其它 status（含 `ABORT` / timeout）归 `UNKNOWN` | sound；该 env 在 certified lifecycle 中还被 proof-semantics blocker 拦截 |
| `_run_power_placement_subproblem()` 内部 | `FEASIBLE` / `INFEASIBLE` | `INFEASIBLE` 仅在 ghost anchor condition 与 cut literal 解析成功后加 conditioned nogood；其它 status 返回 `ABORT` | sound；condition 失败不降级为 unconditional cut |
| flow diagnostic | exact 主链只记录 telemetry | `UNKNOWN` 不触发 exact cut；exploratory 无 bottleneck 时返回 `UNKNOWN` | sound |
| binding initial solve | `FEASIBLE` 进入 routing；`INFEASIBLE` 进入 retry/whole-layout nogood 路径 | `TIMEOUT` 归 `UNKNOWN`；其它 status 由 `_record_unexpected_binding_status()` 归 `UNKNOWN` | sound |
| binding retry without overload separation | `FEASIBLE/INFEASIBLE/TIMEOUT` | 其它 status 由 `_record_unexpected_binding_status()` 归 `UNKNOWN` | sound |
| binding re-solve after precheck safe reject / routing infeasible | `FEASIBLE` 枚举下一 binding；`INFEASIBLE` 表示当前 layout binding exhausted | `TIMEOUT` 归 `UNKNOWN`；其它 status 归 `UNKNOWN` | sound |
| routing precheck | 补丁后仅 `feasible/front_blocked/relaxed_disconnected` 可继续 | `TIMEOUT/UNKNOWN/MODEL_INVALID/ERROR/拼写异常` 立即 `UNKNOWN`，不 build routing，不加 cut | **已修复** |
| routing precheck `front_blocked` | 可加 placement-local / delegate cut；cut 添加失败则 `UNKNOWN` | 无 cut 时 `cut_stall -> UNKNOWN` | sound |
| routing precheck `relaxed_disconnected` | 有 binding alternative 时只 reject 当前 binding；无 alternative 时可进入 whole-layout exhausted 证明 | binding re-solve timeout/unexpected 归 `UNKNOWN` | sound，前提是 precheck status 已白名单 verified；补丁补上入口门 |
| routing solve | `FEASIBLE` 返回 certified layout；`INFEASIBLE` 仅在 full routing model solve 后进入 binding enumeration/exhaustion | `TIMEOUT` 归 `UNKNOWN`；其它 status 归 `UNKNOWN` 并记录 contract violation | sound |
| routing connectivity guard | connected incumbent 才 `FEASIBLE`；guard 内部 lazy cuts 只在 routing model 内 | deadline 耗尽返回 routing `TIMEOUT`，主循环归 `UNKNOWN` | sound |
| L2 abstract routing layer | `INFEASIBLE + violations` 只尝试 add separator cuts | `FEASIBLE/TIMEOUT` fall through baseline routing；branch enabling env 在 certified lifecycle 中是 proof-semantics blocker | sound for certified terminal proof |
| D2 / PCR / deletion-core / lazy demand / cell-pattern separators | 主循环只消费 `cut_added=True` | exception 或 non-infeasible result 不作为 infeasible proof；无 cut 则 fallback 或 `UNKNOWN` | sound for main loop consumption；strict certified run 会先 block proof-affecting env flags |
| pre-master mandatory / coordinate validation | 只有所有被考虑 anchor 都 `INFEASIBLE` 才 trigger | `UNKNOWN/SKIPPED/FEASIBLE/其它` 均作为 non-triggering，不返回 infeasible | sound |
| max iteration cap | 无证明 | certified 返回 `UNKNOWN`，不当穷尽证明 | sound |

## Q2 cut 类型 × 有效性依据矩阵

| Cut / cache 类型 | 有效性依赖前提 | 跨 iteration / candidate 复用判读 |
|---|---|---|
| binding whole-layout nogood | 当前 master layout 下 binding model 已证明无可行 binding，或 routing 枚举所有 binding 后均不可行 | 作为 master cut 只在当前 in-process model 累积；持久化 replay 在 V82 后关闭，跨 checkpoint 不作为 proof |
| binding empty-domain singleton / RAB clear-deficit certificate | 当前 placement pose 的端口绑定域为空；RAB 分支还要求 layout-local routing context 过滤后确为空 | raw pose-level binding cache 只缓存 operation + normalized port geometry 的绑定 pattern；RAB 过滤在命中后按当前 layout 重新做，不污染 raw cache |
| routing front_blocked placement-local nogood | verified precheck 的 `placement_level_conflict_set` 能映射到当前 solution pose literals | conflict 解析失败则不加；无 cut 返回 `UNKNOWN`，不 over-cut |
| routing cell-pattern cut | port_cell+direction 与 front_cell 的 generalized pattern | proof-affecting pose-bool/env path 在 certified lifecycle blocked；delegate 中候选 literal 缺失则不加；condition_lits 空时只用于该 generalized pattern，不来自 failed condition replay |
| lazy demand cut | 某 pose 被选中时必须保留足够 cleared front cells 满足 binding active port demand | delegate 从 master pose vars 和 global port/front cache建约束；cache是 master build 内只读几何索引，不是跨 candidate proof |
| deletion-core cut | deletion oracle 返回的 reduced conflict_set；只弱化当前 front_blocked context | oracle caps/timeout 只影响能否找到 cut；空 conflict 不加；hard-coded 30s 是 performance window，未作为 terminal proof |
| D2 support-augmented nogood | D2 full-grid commodity-flow under selected terminal + occupancy support UNSAT；conflict_set 加入 all port owners + occupancy contributors | D2 `FEASIBLE/UNKNOWN/MODEL_INVALID/ERROR` 不加 cut；only `INFEASIBLE` + non-empty support core 才调用 master cut；env proof branch blocked in certified lifecycle unless run directly |
| PCR signature-lifted cut | patch CP-SAT `INFEASIBLE`，QuickXplain/validation replay accepted，core augmented with patch support signature cells | accepted cut requires replay validation and delegate signature-lift resolution；no equivalent vars / overlap / rejected replay => no cut；env proof branch blocked in certified lifecycle |
| separator capacity hull cut | separator capacity violation from current layout; delegate adds hull constraints over master pose metadata/cell poses | dynamic/abstract enabling flags are proof-semantics envs in strict certified; if direct branch has no accepted cut it falls through baseline |
| power-subproblem ghost-conditioned nogood | power infeasibility under selected ghost anchor and all non-pole fixed occupancy support | condition_set key must match selected ghost anchor and literal; missing condition or add failure => `ABORT/UNKNOWN`; cut-manager requires condition for power cut types |
| persisted exact_safe cuts | none for proof in current release | replay input count is telemetry; `raw_candidate_cuts = []`; even dead replay code skips unresolvable condition instead of unconditionalizing |
| routing model internal connectivity cuts | only cut routing CP-SAT incumbent disconnectedness inside subproblem | Not master cuts; deadline exhaustion returns `TIMEOUT`; cannot delete master solution directly |
| binding domain cache | operation_type + normalized local port geometry | Cache returns raw binding patterns only; layout-local routing-aware filtering is performed after cache hit, so no stale layout proof is reused |
| routing placement core reuse | occupied cells / port specs transformed into current placement core before routing | Reuse summary is telemetry; routing model still built/solved for current candidate unless precheck verified cut path fires |
| shrink counters / telemetry caches | domain_stats/build_stats counters | Telemetry-only; not consumed as proof or as master cut support |

Condition literal audit：`_resolve_condition_lits_from_condition_set()` 对未知 condition key、非 strict int、ghost anchor mismatch、缺失 `u_var` 全部返回 `ok=False`；调用侧 skip cut。没有发现 condition 解析失败降级为 unconditional cut 的路径。持久化 replay 目前整体禁用，因此这条保险带是 dead-code defensive guard，不是当前 proof source。

单调性 audit：所有会让 `_EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE` 继续的路径，要么实际向 master 加约束并返回 `True`，要么返回 `cut_stall/UNKNOWN`。`max_iterations` 命中返回 `UNKNOWN`，不作为穷尽证明。

## Q3 timeout / budget 出口清单

| Stage | Budget 来源 | Timeout / 耗尽终态 | 判读 |
|---|---|---|---|
| master solve | `master_seconds` | 非 `OPTIMAL/FEASIBLE/INFEASIBLE` -> `UNKNOWN` | sound |
| empty solution after master | n/a | `EMPTY_SOLUTION` -> `UNKNOWN` | sound |
| binding initial solve | `binding_seconds` | `TIMEOUT` -> `UNKNOWN` | sound |
| binding retry without overload separation | `binding_seconds` | `TIMEOUT` -> `UNKNOWN` | sound |
| binding re-solve after nogood | `binding_seconds` | `TIMEOUT` -> `UNKNOWN` | sound |
| routing precheck | deterministic finite grid analysis; no CP-SAT budget | 补丁后 `TIMEOUT/ERROR/UNKNOWN` status -> `UNKNOWN` | **已修复** |
| routing solve | `routing_seconds`; subproblem uses `perf_counter()` deadline and CP-SAT per-attempt remaining time | `TIMEOUT` including connectivity guard timeout -> `UNKNOWN` | sound |
| routing connectivity guard | same `routing_seconds` deadline | `CONNECTIVITY_GUARD_TIMEOUT` -> routing `TIMEOUT` -> `UNKNOWN` | sound |
| flow diagnostic | `flow_seconds` | exact 主链 telemetry-only；exploratory `TIMEOUT` -> `UNKNOWN` | sound |
| power placement subproblem | `EXACT_POWER_SUBPROBLEM_SECONDS` default 10s; enabling env blocked in strict certified lifecycle | non-feasible/non-cut status -> `ABORT` -> consumer `UNKNOWN` | sound for certified proof; budget is env-local, not campaign-derived |
| L2 abstract routing | `EXACT_B1_ABSTRACT_ROUTING_SECONDS` default 5s | `TIMEOUT` falls through baseline; no terminal infeasible | sound |
| D2 separator | `EXACT_B1_D2_FLOW_SECONDS` default 30s | non-`INFEASIBLE` result no cut; exceptions no cut | sound |
| PCR separator | overall seconds + per-patch seconds + QuickXplain cap | budget exhausted returns no accepted cut; fallback baseline | sound |
| deletion-core minimizer | hard-coded `max_seconds=30.0`, `max_oracle_calls=128` | empty/no core no cut; fallback/UNKNOWN | sound, but not campaign-budget-coupled |
| dynamic separator hull | max-per-iteration env cap | no accepted cut falls through baseline | sound |
| binding alternative cap | env cap | cap hit with remaining alternatives -> `UNKNOWN`, not whole-layout exhaustion | sound |
| certified max_iterations | `max_iterations` | `MAX_ITERATIONS` -> `UNKNOWN` | sound |

Timing audit：proof-relevant timed loops use CP-SAT `max_time_in_seconds` and/or `time.perf_counter()` deadlines. Some build telemetry uses `time.time()` only for printed wall-time/build_stats and is not used as a proof deadline. The longest unchecked windows observed are finite deterministic preprocessing/build phases over the fixed 70×70 grid or separator candidate generation; PCR and deletion-core add explicit per-solve/call caps.

## Tests / validation

Commands run in Python 3.13 after offline dependency install from `zmd_py313_linux_x86_64.zip`:

```bash
python3.13 -m pytest -q \
  src/tests/test_exact_contract.py::test_unexpected_initial_binding_status_returns_unknown_without_exact_safe_cut \
  src/tests/test_exact_contract.py::test_unexpected_binding_resolve_status_returns_unknown_without_exhaustion_cut \
  src/tests/test_exact_contract.py::test_unexpected_routing_status_returns_unknown_without_exact_safe_cut \
  src/tests/test_exact_contract.py::test_unexpected_routing_precheck_status_returns_unknown_without_routing_cut \
  src/tests/test_exact_contract.py::test_routing_timeout_returns_unknown_without_exact_safe_cut \
  src/tests/test_exact_contract.py::test_certified_max_iterations_cap_returns_unknown_without_exact_safe_cut \
  -p no:randomly
# 6 passed

python3.13 -m pytest -q src/tests/test_exact_contract.py -p no:randomly
# 96 passed

python3.13 -m pytest -q \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  src/tests/test_d2_separator_support_context.py \
  src/tests/test_power_placement_subproblem.py \
  src/tests/test_power_witness_cut_dilution.py \
  -p no:randomly
# 33 passed

python3.13 -m pytest -q \
  src/tests/test_v82_persisted_cut_replay_fail_closed.py \
  src/tests/test_p1_2_proof_obligations.py \
  -p no:randomly
# 6 passed

python3.13 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

Full `python3.13 -m pytest -q src/tests -p no:randomly` was attempted but did not complete in the sandbox; it timed out after reaching 13% progress, with no failures printed before timeout. Therefore I am not claiming a full-suite pass.
