# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环 round 5 审查报告

快照：`zmd_snapshot_278e4d67.zip`

sha256：`278e4d67f97a88cab7bba697ec96df2f04d43ce1475bc65aef4a22519d1885a0`，已在开工前校验匹配。

审查范围：`src/search/benders_loop.py` 主循环对 master / binding / routing / flow 子问题的消费；F-BL-R4-01 修复确认；跨 candidate 会话隔离；`last_proof_summary` 完整性；以及 F-BL-R3/R4 相关抽查。未扩展到 binding/master/routing/preprocess/campaign/scheduler 内部建模正确性。

结论：**本轮零 soundness finding**。F-BL-R4-01 的五个已知 binding status 消费点都已接到 `_record_unexpected_binding_status()`，返回后不会触达 cut 登记、whole-layout nogood 或 exhaustion 分支；未发现第六处影响 proof 决策的旧式 binding status 消费。

本轮额外修了 1 个低危 proof-summary 完整性缺口：公开 certified lifecycle 入口会先 fail-closed 阻断该路径，因此不是 soundness 暴露；但直接调用 controller 的内部/forensic 路径会返回 UNKNOWN 而没有与返回 status 对齐的 proof summary。补丁已附，回归已加。

## Finding / Fix

### F-BL-R5-PS-01 — Low：power placement forensic 分支 UNKNOWN 返回前 proof summary 可能 stale/缺失

位置：

- `src/search/benders_loop.py:4528-4555`
- 回归：`src/tests/test_exact_contract.py:3666-3747`

问题描述：

在 `_run_certified_exact()` 中，若 `EXACT_POWER_PLACEMENT_SUBPROBLEM` 打开，且 `_run_power_placement_subproblem()` 返回既非 `FEASIBLE` 也非 `INFEASIBLE_CUT_ADDED` 的状态，例如 `ABORT`，旧代码直接：

```python
return RUN_STATUS_UNKNOWN, None
```

但没有先写 `self.last_proof_summary`。因此直接使用 `LBBDController.run_with_status()` 的内部/forensic 调用方可能读到空 summary 或上一阶段遗留 summary，形成“返回 status = UNKNOWN，但 summary 不对应该 UNKNOWN 原因”的完整性缺口。

soundness 判读：

这不是公开 certified lifecycle 的 false-INFEASIBLE / false-CERTIFIED 暴露。`run_benders_for_ghost_rect()` 在 certified_exact 模式会先调用 `_collect_forbidden_certified_master_domain_env_overrides()`；`EXACT_POWER_PLACEMENT_SUBPROBLEM` 被列为 unsafe env，阻断码为 `power_placement_subproblem_not_certified`，公开入口在 `src/search/benders_loop.py:6290-6316` 就返回 `UNPROVEN`，不会进入 controller 这段 power placement 子问题分支。也没有 cut 登记或 nogood 铸造。

修法：

在该 UNKNOWN 返回前写入与返回 status 对齐的 fail-closed summary：`stage="power_placement_subproblem"`、`power_placement_status=str(power_status)`、`master_follow_up="fail_closed_unknown"`，并附上 warm-start / master-search / subproblem-reuse / exact-cut-ladder 的审计字段。

回归 probe：

`test_power_placement_abort_returns_unknown_with_matching_proof_summary` 直接构造 `LBBDController`，monkeypatch `_run_power_placement_subproblem()` 返回 `("ABORT", None)`，验证：

- 返回 `RUN_STATUS_UNKNOWN`
- `result is None`
- `generated_exact_safe_cuts == []`
- `last_proof_summary["stage"] == "power_placement_subproblem"`
- `last_proof_summary["power_placement_status"] == "ABORT"`
- `last_proof_summary["master_follow_up"] == "fail_closed_unknown"`

补丁文件：`/mnt/data/zmd_review_r5.patch`。

## Q1：F-BL-R4-01 修复确认

### binding status 五消费点核对表

行号为本轮补丁后的工作树行号。

| # | 消费点 | file:line | 状态消费与返回 | cut/exhaustion 是否可达 | 判读 |
|---|---|---:|---|---|---|
| 1 | overload fallback retry 后的非契约 `retry_status` | `src/search/benders_loop.py:5172-5181` | `_record_unexpected_binding_status(... binding_model=retry_model, extra={"overload_fallback_outcome": ...})` 后立即 `return RUN_STATUS_UNKNOWN, None` | 不可达；后续 binding INFEASIBLE whole-layout nogood 分支在 `5183+` | 已堵 |
| 2 | 初始 binding solve 非 `FEASIBLE/INFEASIBLE/TIMEOUT` | `src/search/benders_loop.py:5215-5224` | `_record_unexpected_binding_status(...)` 后立即 UNKNOWN | 不可达；routing core build 的 heartbeat 起点在 `5226+`，不会建 routing core | 已堵 |
| 3 | precheck safe-reject 后 binding 重解非契约状态 | `src/search/benders_loop.py:5364-5375` | 带 `routing_status=f"PRECHECK_{precheck_status.upper()}"`、`routing_precheck`、`binding_selection_safe_reject=True` 写 summary 后立即 UNKNOWN | 不可达；不会落入 precheck cut/exhaustion 后续分支 | 已堵 |
| 4 | `PRECHECK_RELAXED_DISCONNECTED` 后 binding 重解非契约状态 | `src/search/benders_loop.py:5726-5736` | 带 `routing_status="PRECHECK_RELAXED_DISCONNECTED"` 写 summary 后立即 UNKNOWN | 不可达；不会落入 relaxed-disconnected 后续 routing/cut 分支 | 已堵 |
| 5 | routing `INFEASIBLE` 后 binding alternative 重解非契约状态 | `src/search/benders_loop.py:5923-5933` | 带 `routing_status="INFEASIBLE"` 与 `routing_summary` 写 summary 后立即 UNKNOWN | 不可达；`break` 到 exhaustion/whole-layout nogood 的路径只在 `binding_status == INFEASIBLE` 时可达 | 已堵 |

### 有没有第六处 binding status 消费

用 `rg` 追了 `PortBindingModel(`、`binding_status`、`solve(time_limit_seconds=self.binding_seconds)`、`_record_unexpected_binding_status`。在本面主循环中，影响 proof 决策的 binding solve/status 消费点就是上表五处加上已显式契约处理的 `TIMEOUT / INFEASIBLE / FEASIBLE` 正常分支；未发现 heuristic/diagnostic 路径里仍把 `MODEL_INVALID/UNKNOWN/ABORT` 当作 exhaustion 或 cut 依据的第六处。

### overload retry proof source 切换

overload fallback 首轮 `INFEASIBLE` 且存在 overload nogood 时，retry 分支现在是全切换而不是半切换：

- retry `FEASIBLE`：`binding_model = retry_model`、`binding_status = retry_status`，并用 `binding_model.extract_conflict_summary()` 更新 cache，见 `src/search/benders_loop.py:5143-5148`。
- retry `INFEASIBLE`：同样切换 `binding_model = retry_model`、`binding_status = retry_status`，并更新 cache，见 `src/search/benders_loop.py:5149-5154`；随后 binding INFEASIBLE proof summary 在 `5192` 读取的是已切换后的 `binding_model.extract_conflict_summary()`。
- retry `TIMEOUT`：UNKNOWN summary 直接读取 `retry_model.extract_conflict_summary()`，见 `5164`。
- retry 非契约状态：`_record_unexpected_binding_status(... binding_model=retry_model ...)`，见 `5172-5181`。

因此 conflict summary / nogood 登记 / exhaustion 证明源在 retry INFEASIBLE 分支都指向 retry model，未见“status 用 retry，summary 用第一轮”的半切换残留。唯一保守备注是 retry `TIMEOUT`/非契约分支没有调用 `_update_binding_cache_from_summary()`；这只影响 `_subproblem_reuse_summary()` 里的 cache telemetry 字段，不回流 proof 决策。

### `_record_unexpected_binding_status()` 的 `master_status: "FEASIBLE"`

`_record_unexpected_binding_status()` 位于 `src/search/benders_loop.py:6057-6097`，其中 `master_status` 硬编码为 `"FEASIBLE"`。五个调用点都位于 `_run_exact_binding_and_routing()` 内，该函数只在 `_run_certified_exact()` 已从 master 得到可抽取 solution 后调用：master 非 FEASIBLE/OPTIMAL 会在进入绑定/布线前返回 UNKNOWN/INFEASIBLE/CERTIFIED 等对应路径。因此这五处的硬编码符合调用前置条件。

下游未发现把该字段当作强 proof 分支条件使用；outer/campaign 的分支基于显式返回的 `status`，proof summary 主要落盘、telemetry、triage 展示。因此该字段即使未来某处调用前置条件变化，也更像审计字段问题而非当前 soundness 问题。

### cap 命中 + 非契约状态的路径顺序

binding alternative cap 分支在 `src/search/benders_loop.py:5856-5887`。当 `EXACT_B1_BINDING_ALT_CAP` 命中且当前 binding model 仍有 alternatives 时，代码写 `binding_status="ALT_CAP_REACHED"`、`routing_status="INFEASIBLE"` 的 UNKNOWN summary 并立即返回。它在 `binding_model.add_nogood_cut(selection)` 与重解之前，所以 cap 命中不会铸造 nogood，也不会伪装成 binding/routing exhaustion。

若未命中 cap，后续重解只在 `FEASIBLE` 时继续枚举、`INFEASIBLE` 时进入 exhaustion 分支、`TIMEOUT` 时 UNKNOWN；非契约状态由 `src/search/benders_loop.py:5923-5933` 立即 fail-closed UNKNOWN。cap 与非契约状态同时相关的路径没有 false-INFEASIBLE 组合。

## Q2：跨 candidate 会话隔离

### static exact core 生命周期与 mutation 点

`ExactSearchSession.create()` 通过 `MasterPlacementModel.build_exact_core(...)` 创建 static core，见 `src/search/benders_loop.py:1582+` 与 `src/models/master_model.py:2522-2608`。core 打包了 proto、source_instances、facility_pools、rules、generic IO、mandatory groups、coordinate binding、candidate precheck artifacts 等。

单个 candidate 求解时，主路径不在 core 上加约束；每个 candidate 通过 `MasterPlacementModel.from_exact_core(...)` 克隆出 overlay：

- `src/models/master_model.py:2715`：`model.model = cp_model_from_proto(_clone_model_proto(core.proto))`，CP-SAT proto 是克隆。
- `src/models/master_model.py:2726`：`build_stats` 深拷贝。
- `src/models/master_model.py:2733-2735`：mandatory groups 与 candidate precheck artifacts 复制到 overlay 侧。
- `src/models/master_model.py:2802-2810`：coordinate delegate 绑定 clone model 后在 overlay 上加 ghost constraints。
- `src/models/master_model.py:2847-2863`：legacy 路径也是绑定 overlay 变量、清 overlay ghost/u_vars，然后在 overlay model 上加 ghost constraints。

生产路径中看到的 constraint/domain mutation 都落在 candidate overlay `master.model`、controller 局部 binding/routing model、或 CutManager/controller 局部结构上；未发现写回 `exact_session.core.proto` 或 core domain 的路径。

保守备注：`MasterPlacementModel.__init__()` 对 `facility_pools` 是 `{tpl: list(pool) ...}` 的列表浅拷贝，pose dict 本体在从 core 构造 overlay 时可能共享，见 `src/models/master_model.py:2260` 与 `src/models/master_model.py:2680-2683`。本轮按主循环消费面追踪到的使用是读取或构造新 dict，未发现候选内 mutation pose dict 的路径；因此不报 soundness finding。但若未来在 overlay 构建中原地写 pose dict，应优先把 facility pool pose dict 深拷贝化，避免 core 污染。

### 跨 candidate 存活容器清单

| 容器/状态 | 生命周期 | 是否跨 candidate 存活 | 是否回流 proof 决策 | 判读 |
|---|---|---:|---:|---|
| `ExactSearchSession.core` | serial 为 campaign/session 级；parallel 为每 worker 级 | 是 | 作为只读 master static core，被 overlay 克隆使用 | 未见 mutation，sound |
| candidate overlay `MasterPlacementModel` | 每 candidate 新建 | 否 | 是，master proof/cut 作用对象 | 隔离 |
| `LBBDController` | 每 candidate 新建 | 否 | 是，主循环 proof 决策 | 隔离 |
| `CutManager` | `run_benders_for_ghost_rect()` 内每 candidate 新建，`src/search/benders_loop.py:6444+` 附近 | 否 | 只在当前 candidate 内去重/登记 fresh cuts | 隔离 |
| `generated_exact_safe_cuts` | controller 局部，`src/search/benders_loop.py:2540` 初始化 | 否；结束时发布到 metadata/campaign | 发布后为 telemetry/checkpoint；当前 candidate 内才作用于 master | 不跨 candidate 剪枝 |
| persisted `exact_safe_cuts` / campaign candidate cuts | campaign 文件跨 run/candidate 保存 | 是 | certified_exact 下 replay input 计数后置空，`src/search/benders_loop.py:6556-6572` | telemetry 非 proof，sound |
| `_update_binding_cache_from_summary()` counters | controller 局部，`src/search/benders_loop.py:4013-4024` | 否 | 不保存 conflict，不加 cut；只进 `_subproblem_reuse_summary()` | telemetry |
| routing shrink counters | controller 局部，`src/search/benders_loop.py:3960-4012` | 否 | summary/telemetry | telemetry |
| `last_proof_summary` | controller 单槽 | 否；结束后被发布到 module metadata | outer/campaign 分支不用它决定强 status | telemetry/审计 |
| `run_benders_for_ghost_rect.last_run_metadata` | module 函数属性单槽 | serial 进程内跨调用存在，但每 candidate 开头 `_reset_last_run_metadata()`，`src/search/benders_loop.py:6244` | outer/parallel 在调用返回后立即读取 | 已重置，隔离 |
| `ExactCampaign.state` | campaign 级持久 | 是 | `mark_candidate_result()` 接收显式 status；strong 状态只承认 `CERTIFIED/INFEASIBLE`，`src/search/exact_campaign.py:40-51` | proof summary 不把 UNKNOWN 升级强证据 |
| master hint persistence | 按 `project_root` + `candidate_key` 绑定，见 `src/search/benders_loop.py:6519-6523` | 可能跨 wave 同 candidate | hint，不是 proof；certified unsafe env guard 管 domain knobs | 不构成 proof 剪枝 |

未发现 candidate B 因 candidate A 的 binding conflict cache 被剪的通路。binding cache 只记录 hit/miss/reused instance id 这类 summary counter，既不保存 candidate A 的 conflict set，也不调用 `master.add_benders_cut()`。

### serial vs parallel 共享态差异

parallel worker 在 `src/search/exact_parallel_scheduler.py:221-225` 每 worker 创建一个 `ExactSearchSession`，之后每个 task 调 `run_benders_for_ghost_rect(... session=session ...)`，见 `280-297`。serial 路径同样复用 session，但每个 candidate 仍重建 overlay/controller/cut_manager。二者在“static core 复用 + candidate overlay 重建”这条主隔离边界上等价。

差异点：

- parallel 的 `run_benders_for_ghost_rect.last_run_metadata` 是每个 worker 进程内单槽；worker 在每次调用返回后立即读取，见 `src/search/exact_parallel_scheduler.py:298-307`。serial 在主进程每次调用返回后立即读取，见 `src/search/outer_search.py:2537-2543`。两者都依赖 `run_benders_for_ghost_rect()` 开头 `_reset_last_run_metadata()`。
- parallel 可以按 worker 派生 `EXACT_MASTER_RANDOM_SEED_BASE`，见 `src/search/exact_parallel_scheduler.py:203-215`。这可能影响 CP-SAT 搜索轨迹与预算下 UNKNOWN 发生位置，但不会改变 proof 有效性；强结论仍需当前 candidate 当前进程 fresh proof。
- worker result 入口校验要求 status 在有效集合内、CERTIFIED 带 solution、非 CERTIFIED 不带 solution、proof_summary 是 mapping，见 `src/search/exact_parallel_scheduler.py:121-131`。

未发现 serial 独有的跨 candidate proof 残留，也未发现 parallel 独有的共享态导致 false proof。可产生运行轨迹差异的是 seed/预算/调度，不是 proof 结论语义差异。

## Q3：proof summary 完整性

### `last_proof_summary` 单槽覆写时序

`LBBDController.last_proof_summary` 是单槽，主循环在每个 terminal/UNKNOWN 返回前写入对应 summary；内部状态如 `MASTER_CUT_ADDED_CONTINUE` 可以设置 summary 后继续下一轮，但最终 `run_with_status()` 返回的 public status 会以最后一次 terminal 写入为准。F-BL-R4-01 五个 unexpected binding status 分支都在写 summary 后立即 UNKNOWN，避免中途 summary 被后续 cut/exhaustion 覆写。

本轮唯一发现的错配风险是 F-BL-R5-PS-01：power placement forensic 子问题非契约状态原先直接 UNKNOWN 返回，不写 summary。已补。

### summary key 的下游消费性质

`subproblem_status_contract_violation`、`master_follow_up`、`binding_status`、`routing_status` 等字段下游主要用于审计、triage、telemetry、campaign 记录。outer serial 分支在 `src/search/outer_search.py:2568-2671` 按显式返回 status 做 `CERTIFIED/INFEASIBLE/UNKNOWN` 处理；campaign 的 `mark_candidate_result()` 也直接接收 status 并写入 record，见 `src/search/exact_campaign.py:2039-2147`。没有看到把 `subproblem_status_contract_violation` 或 `master_follow_up` 当作强证据把 UNKNOWN 升级为 INFEASIBLE/CERTIFIED 的消费者。

campaign 运行态 heartbeat merge 只在 candidate 仍是 `RUNNING` 时写 summary，见 `src/search/exact_campaign.py:2148-2171`；terminal result 会由 `mark_candidate_result()` 用最终 proof_summary 覆盖。因此 heartbeat 中途 summary 不会压过 terminal status。

### heartbeat fail-open 检查

controller 内部 `_emit_heartbeat()` 捕获 heartbeat callback 异常并返回，见 `src/search/benders_loop.py:2693-2719`。这类异常不会改变 proof 控制流，也不会导致 cut 或 certified 状态。

`run_benders_for_ghost_rect()` 的 campaign heartbeat helper 对外部 heartbeat callback 异常同样吞掉，见 `src/search/benders_loop.py:6250-6266`；但如果 `ExactCampaign.update_candidate_running_proof_summary()` 或 `campaign.save()` 本身抛异常，当前 helper 没吞，会让运行失败/中断。这是 availability 风险，不是 fail-open proof 风险：它不会把 UNKNOWN 变成 INFEASIBLE，也不会登记 fresh exact-safe cut。

## Q4：抽查维持

### F-BL-R3-01 cap → UNKNOWN

`EXACT_B1_BINDING_ALT_CAP` 命中时，代码在加 binding nogood 与重解之前返回 UNKNOWN，见 `src/search/benders_loop.py:5856-5887`。summary 记录 `binding_status="ALT_CAP_REACHED"`，没有 `binding_exhausted=True` 或 `routing_exhausted=True` 的 cut 登记。维持 r4 结论。

### r4 Q2 重入清单抽查

- `run_benders_for_ghost_rect()` 开头调用 `_reset_last_run_metadata()`，见 `src/search/benders_loop.py:6244`。
- certified_exact persisted exact_safe_cut replay 被显式置空，`raw_candidate_cuts = []`，见 `src/search/benders_loop.py:6556-6572`；loaded/generated counts 只发布 metadata。
- hint persistence context 按 candidate key 设置，见 `src/search/benders_loop.py:6519-6523`；hint 是 warm-start/性能路径，不是 proof 剪枝依据。

### r4 Q3 UNKNOWN 不在 frontier skip 集

frontier 默认只跳过 `CERTIFIED` / `INFEASIBLE`，见 `src/search/outer_search.py:653-655`；`UNKNOWN` 只有 `EXACT_OUTER_SKIP_UNKNOWN` 打开时才跳过。该 env 在 certified_exact 的 unsafe env guard 中被列为 blocker，见 `src/search/benders_loop.py:467-469`。serial UNKNOWN 分支默认 mark stopped 并返回 UNKNOWN，见 `src/search/outer_search.py:2626-2671`。维持 UNKNOWN 不被当作 frontier exhausted 的结论。

## 自验

环境：Python 3.13.5；依赖离线从 `zmd_py313_linux_x86_64.zip` 安装；OR-Tools 9.15。

已跑命令与结果：

```bash
python -m pytest -q \
  src/tests/test_exact_contract.py::test_unexpected_initial_binding_status_returns_unknown_without_exact_safe_cut \
  src/tests/test_exact_contract.py::test_unexpected_binding_resolve_status_returns_unknown_without_exhaustion_cut \
  src/tests/test_exact_contract.py::test_power_placement_abort_returns_unknown_with_matching_proof_summary \
  src/tests/test_exact_contract.py::test_unexpected_routing_status_returns_unknown_without_exact_safe_cut \
  -p no:randomly
# 4 passed in 1.16s
```

```bash
python -m pytest -q src/tests/test_exact_contract.py -p no:randomly
# 94 passed in 3.40s
```

```bash
python -m pytest -q src/tests/test_exact_campaign_state_soundness.py src/tests/test_p0_certified_soundness_fixes.py -p no:randomly
# 14 passed in 1.04s
```

```bash
python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

尝试全量：

```bash
python -m pytest -q src/tests -p no:randomly
```

该命令运行到约 7% 时因本沙盒工具超时中止；超时前未见失败输出。本报告不声称全量 suite 已跑完。

## Patch 摘要

```diff
--- a/src/search/benders_loop.py
+++ b/src/search/benders_loop.py
@@ -4537,6 +4537,21 @@
                     iteration += 1
                     continue
                 else:
+                    self.last_proof_summary = {
+                        "mode": "certified_exact",
+                        "benders_iterations": iteration,
+                        "master_status": "FEASIBLE",
+                        "stage": "power_placement_subproblem",
+                        "power_placement_status": str(power_status),
+                        "diagnostic_flow_status": diagnostic_flow_status,
+                        "enumerated_bindings": 0,
+                        "routing_attempts": 0,
+                        "master_follow_up": "fail_closed_unknown",
+                        **self._exact_warm_start_summary(),
+                        **self._master_search_summary(),
+                        **self._subproblem_reuse_summary(),
+                        **self._exact_cut_ladder_summary(),
+                    }
                     return RUN_STATUS_UNKNOWN, None
```

完整 unified diff 与回归测试见交付 patch。
