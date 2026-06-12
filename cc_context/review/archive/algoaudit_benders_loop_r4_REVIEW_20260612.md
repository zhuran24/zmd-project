# 终末地 IndustrialPlanner 精确求解器 Benders/LBBD 主循环 r4 审查报告

审查对象只使用指定快照 `zmd_bl_r4_snapshot_b377a2a7.zip`。开工 sha256 校验通过：`b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531`。

本轮结论：发现 1 个新的 soundness finding，已给出补丁与回归测试。未声称“本轮零 soundness finding”。

## Finding F-BL-R4-01：binding solve 非契约状态会被误铸为 binding/routing exhaustion nogood

Severity: High / soundness

文件与攻击面：`src/search/benders_loop.py:5089-5209`, `src/search/benders_loop.py:5324-5360`, `src/search/benders_loop.py:5687-5721`, `src/search/benders_loop.py:5885-5918`, `src/search/benders_loop.py:5921-5952`。

问题：r3 已修 routing solve 的 status contract guard，`src/search/benders_loop.py:5781-5839` 只允许 routing `FEASIBLE`、`INFEASIBLE`、`TIMEOUT` 进入强分支，非预期 routing status 返回 `UNKNOWN`。但 binding solve 的 status 消费存在同型裂缝。补丁前，初始 `binding_model.solve()` 只显式处理 `TIMEOUT` 与 `INFEASIBLE`；若返回 `MODEL_INVALID`、`UNKNOWN`、`ABORT` 等非契约状态，会继续构建 routing core，跳过 `while binding_status == "FEASIBLE"`，最后落到 `binding_status="EXHAUSTED" / routing_status="ALL_INFEASIBLE"` 的 whole-layout nogood 分支。相同模式还存在于 precheck 后 binding 重解、relaxed_disconnected 后重解、routing INFEASIBLE 后枚举下一个 binding 的重解，以及 overload fallback retry status 消费。

可复现 probe：在补丁前 monkeypatch `PortBindingModel.solve()` 初始返回 `MODEL_INVALID`，并拦截 `_add_exact_whole_layout_nogood`。实际结果为 `status=master_cut_added_continue`，且进入 `cut_type=routing_exhausted_nogood`，`proof_summary.binding_status=EXHAUSTED`。这表示一个非证明状态被升级成“全部 binding/routing 穷尽”的 master cut，可能剪掉可行 layout；若后续 master 在这些伪 cut 下证明空，会产生错误的 candidate INFEASIBLE。

修法：新增 `_record_unexpected_binding_status()`，把 binding 非契约状态统一记录为 `subproblem_status_contract_violation="unexpected_binding_status"`，并返回 `RUN_STATUS_UNKNOWN`，不加 binding-local 之外的 proof-bearing cut，不加 whole-layout nogood，不推进 master 强结论。补丁覆盖：初始 binding solve、overload fallback retry、precheck safe-reject 后重解、relaxed_disconnected 后重解、routing INFEASIBLE 后重解。overload fallback 中 retry 返回 `INFEASIBLE` 时，现在也切换到 retry model 作为 proof source，避免 proof summary 继续引用 overload-separation 第一轮模型。

回归：新增 `src/tests/test_exact_contract.py:3464-3664` 两个 probe：

- `test_unexpected_initial_binding_status_returns_unknown_without_exact_safe_cut`
- `test_unexpected_binding_resolve_status_returns_unknown_without_exhaustion_cut`

两者均断言非契约 binding status 只返回 `UNKNOWN`，`generated_exact_safe_cuts == []`，且 proof summary 标记 `unexpected_binding_status`。现有 r3 回归 `test_binding_alt_cap_returns_unknown_without_whole_layout_cut` 位于 `src/tests/test_exact_contract.py:3423-3461`，本轮仍有效。

补丁：`0001-benders-binding-status-guard.patch`。

## Q1：F-BL-R3 修复确认

### cap -> UNKNOWN 路径

`EXACT_B1_BINDING_ALT_CAP` 命中时，代码先判断 `_exceeded_cap and has_binding_alternatives`，直接设置 `binding_status="ALT_CAP_REACHED"` 并返回 `RUN_STATUS_UNKNOWN`，该分支位于 `src/search/benders_loop.py:5841-5872`。关键点是 `binding_model.add_nogood_cut(selection)` 在后面的 alternatives 分支 `src/search/benders_loop.py:5873-5885`，因此 cap 命中分支不会新增 binding nogood，也不会铸造 whole-layout master cut。回归测试 `src/tests/test_exact_contract.py:3423-3461` 明确断言 `FakeBindingModel.instances[0].nogoods == []`。

下游消费上，`_run_certified_exact()` 对 `_run_exact_binding_and_routing()` 返回 `RUN_STATUS_UNKNOWN` 只向外返回 `UNKNOWN`，不继续加 cut，见 `src/search/benders_loop.py:4688-4695`。outer serial 路径把 `UNKNOWN` 写回 campaign，并在 certified strict 默认下停止为 `UNKNOWN`，见 `src/search/outer_search.py:2626-2671`。这条链上没有把 “UNKNOWN + 部分枚举信息” 当成 INFEASIBLE 或 exhausted 的消费点。

### routing status guard

routing solve 的三态 guard 在场：routing `FEASIBLE` 才 certified，`TIMEOUT` 返回 `UNKNOWN`，非 `INFEASIBLE` 的其它值标记 `subproblem_status_contract_violation="unexpected_routing_status"` 并返回 `UNKNOWN`，见 `src/search/benders_loop.py:5781-5839`。现有回归 `test_unexpected_routing_status_returns_unknown_without_exact_safe_cut` 继续覆盖该合同。

### binding / flow status 同型缝

binding status 缝是本轮唯一新增 finding，已补。补丁后所有 binding solve/re-solve 的非契约 status 都走 `UNKNOWN`，不会进入 exhaustion cut。flow 诊断在 certified exact 主路径中只作为 `diagnostic_flow_status` telemetry 写入 proof summary，见 `src/search/benders_loop.py:4542-4548`；本轮未发现 flow status 被用于强 cut 或强终态的消费点。

### binding model 生命周期与穷尽证明可信度

每次 `_run_exact_binding_and_routing()` 都重新构造并 build 一个新的 `PortBindingModel`，见 `src/search/benders_loop.py:4967-4975`。generic IO 约束来自 master 快照并在 binding model 构造时传入，见 `_binding_generic_requirements_kwargs()` 附近的 `src/search/benders_loop.py:4892-4936`。binding-local nogood 只在这个 model 的枚举生命周期内累计；cap 分支不会加 nogood并立即 UNKNOWN；真正的 binding/routing exhaustion 只在同一 model 对所有 alternatives 加完 nogood 且最后重解返回合法 `INFEASIBLE` 后，才进入 `routing_exhausted_nogood`，见 `src/search/benders_loop.py:5921-5952`。补丁把非契约 status 从这个证明链中剔除，因此“穷尽证明 = binding 重解 INFEASIBLE”的来源恢复为可判读的同一模型生命周期。

## Q2：重入与重试语义清单

单 candidate 重入入口 `run_benders_for_ghost_rect()` 每次调用先 `_reset_last_run_metadata()`，见 `src/search/benders_loop.py:6227-6233`。certified exact 的 exact session 可复用静态 core，但 master overlay 每次按 candidate 重新构建，见 `src/search/benders_loop.py:6444-6527`；controller 也每次重新构造，见 `src/search/benders_loop.py:6823-6839`；binding model 则在每个 master layout 的 `_run_exact_binding_and_routing()` 内重新构造，见 `src/search/benders_loop.py:4967-4975`。

persisted `exact_safe_cuts` 在 certified exact 中明确不 replay：campaign 里读到的 candidate cuts 会被置空，注释说明这些只是 performance hints 而非 proof objects，见 `src/search/benders_loop.py:6550-6558`。因此同一 candidate 重跑时丢失上一轮 binding-local nogood 或 generated exact cut 不影响正确性，只影响重新枚举/重新证明的效率。

warm hint 注入点不是硬约束：`_run_certified_exact()` 只在第一轮把 `solution_hint` 传给 `master.solve()`，并设置 `known_feasible_hint=False`，见 `src/search/benders_loop.py:4147-4150` 与 `src/search/benders_loop.py:4391-4440`。本轮未发现把 hint 当 proof-bearing 状态读取的路径。

campaign resume 对中间状态的处理是 fail-closed：合法 status 集合包含 RUNNING/UNKNOWN/UNPROVEN/CERTIFIED/INFEASIBLE，强状态只有 CERTIFIED/INFEASIBLE，见 `src/search/exact_campaign.py:40-51`。`mark_candidate_started()` 对非强状态会重新标 RUNNING、递增 attempts 并清掉 solution，见 `src/search/exact_campaign.py:2008-2037`；强状态不会被 RUNNING 降级。`mark_candidate_result()` 禁止强状态冲突，禁止强状态降级为弱状态，且非 CERTIFIED 不允许携带 solution，见 `src/search/exact_campaign.py:2051-2090` 与 `src/search/exact_campaign.py:2130-2143`。

退出路径：binding/routing timeout 返 `UNKNOWN`；master 非 FEASIBLE/OPTIMAL/INFEASIBLE 返 `UNKNOWN`，见 `src/search/benders_loop.py:4471-4501`；Benders 内层 max_iterations 返 `UNPROVEN`，这是非强终态，见 `src/search/benders_loop.py:4697-4709`；outer campaign time budget 与 max_attempts 均返 `UNKNOWN`，见 `src/search/outer_search.py:1930-1941` 与 `src/search/outer_search.py:2059-2071`。未见预算耗尽路径直接铸 CERTIFIED/INFEASIBLE。

## Q3：终止与 frontier 推进保真

候选生成的目标排序为 `max_lex(area, min_side)`：`candidate_objective()` 返回 `(area, min(w,h))`，排序键为 `(-area, -min_side, -max_side, -w)`，见 `src/search/certified_frontier.py:163-172`。outer 的 `_is_objectively_worse_or_equal()` 直接比较该二元目标，见 `src/search/outer_search.py:454-458`，因此 min_side 只在 area 相等时参与二级比较，不会跨 area 误剪。

frontier 剪枝条件判读：`_compute_exact_frontier_state()` 只把 explicit CERTIFIED 与 explicit INFEASIBLE 作为可跳过强状态，见 `src/search/outer_search.py:631-646` 与 `src/search/outer_search.py:653-661`。随后三类派生剪枝分别是：被已证 CERTIFIED 尺寸按维度覆盖的更小 rectangle，`ghost_w <= cert_w and ghost_h <= cert_h`；包含已证 INFEASIBLE 尺寸的更大 rectangle，`ghost_w >= inf_w and ghost_h >= inf_h`；以及相对 best certified 在 `(area,min_side)` 上不可能更优的候选，见 `src/search/outer_search.py:663-674`。这些条件与“字典序不可能更优或几何单调蕴含”一致。

UNKNOWN 阻挡语义：默认 `_frontier_skip_statuses` 只有 CERTIFIED/INFEASIBLE，UNKNOWN 不在其中，见 `src/search/outer_search.py:653-655`。虽然有 `EXACT_OUTER_SKIP_UNKNOWN` 实验门，但 certified exact 模式若开启该门会直接 BLOCKED/UNPROVEN，不进入 certified 搜索，见 `src/search/outer_search.py:1702-1716`。terminal frontier validator 也要求 projection 的 `potential_domain` 与 `frontier` 为空，否则拒绝 terminal certified evidence，见 `src/search/certified_frontier.py:417-420`。因此 UNKNOWN 不会被静默跳过后宣称 CERTIFIED。

admissibility 一致性：candidate 生成从 `min_side` 到 max inclusive，见 `src/search/certified_frontier.py:53-94`；outer 的 candidate_generation 同时记录 `min_side` 和 `min_side_admissibility`，见 `src/search/outer_search.py:1792-1803`；terminal validator 拒绝 `min_side > expected_min_side_admissibility` 的切片域，并要求 final result min_side 不低于 admissibility，见 `src/search/certified_frontier.py:351-354` 与 `src/search/certified_frontier.py:368-373`。本轮未发现一侧 `>=6`、另一侧 `>6` 的 off-by-one。

## Q4：抽查维持

A-1 connectivity guard 仍在 routing subproblem 的 solve 循环中。CP-SAT 返回 FEASIBLE/OPTIMAL 后会调用 `_validate_selected_route_connectivity()`，只有 connectivity 通过才返回 `FEASIBLE`；断连 incumbent 会被 cut/nogood 后继续求解，见 `src/models/routing_subproblem.py:1389-1477` 与 `src/models/routing_subproblem.py:1528-1643`。`extract_routes()` 还要求 `_connectivity_guard_accepted`，见 `src/models/routing_subproblem.py:1645-1650`。

A-2 binding 枚举优先仍在场。precheck 对 binding-selection-local 的 safe reject 先 `binding_model.add_nogood_cut(selection)` 并重解 alternatives，只有无 alternatives 或无法加安全 cut 才进入更强 master cut/UNKNOWN 分支，见 `src/search/benders_loop.py:5306-5360` 与 `src/search/benders_loop.py:5362-5682`。

F-BL-R3-01 回归仍在场并通过，见 `src/tests/test_exact_contract.py:3423-3461`。它专门防止 `EXACT_B1_BINDING_ALT_CAP` 把预算耗尽误判为 alternatives 穷尽。

## 自验结果

已跑：

```bash
python3 -m pytest -q src/tests/test_exact_contract.py -k 'binding_alt_cap or unexpected_routing_status or routing_timeout_returns_unknown or unexpected_initial_binding_status or unexpected_binding_resolve_status' -p no:randomly
# 5 passed, 88 deselected

python3 -m pytest -q src/tests/test_exact_contract.py -p no:randomly
# 93 passed

python3 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

python3 -m pytest -q src/tests/test_exact_campaign_state_soundness.py src/tests/test_exact_outer_skip_unknown.py src/tests/test_v62_candidate_frontier_contract.py -p no:randomly
# 34 passed

python3 -m pytest -q src/tests/test_binding.py -p no:randomly
# 24 passed
```

尝试跑全量：

```bash
python3 -m pytest -q src/tests -p no:randomly
```

沙盒 300 秒超时，超时前未见 failure。单独 `src/tests/test_routing.py` 也因耗时在 300 秒内未完成，超时前未见 failure。上述未完成项未作为“全量绿”宣称。
