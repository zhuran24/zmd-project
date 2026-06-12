# 终末地 IndustrialPlanner 精确求解器 Benders/LBBD 主循环面确认轮 REVIEW

## 审查入口与快照校验

只使用 `zmd_audit_snapshot_6867b7ce.zip`。开工前校验通过：

```text
sha256 6867b7ce75b5aa61efe9864572cc1b2781ea68d07bcf7efeca28a3ec8ee3487b  /mnt/data/zmd_audit_snapshot_6867b7ce.zip
```

解包根：`/mnt/data/zmd_review_work/project`。未使用文件区其它旧快照包。环境：Python `3.13.5`，OR-Tools `9.15.6755`，依赖来自 `zmd_py313_linux_x86_64.zip` 离线安装。

## 结论

本轮在原始快照中发现 2 个主循环状态消费/证明语义问题，均已给出 unified diff 与回归测试。修复后，本轮审查范围内未发现剩余 soundness finding。

补丁文件：`/mnt/data/benders_main_loop_status_fix.patch`

冻结工件条款：本次只改 `src/search/benders_loop.py` 与 `src/tests/test_exact_contract.py`。未修改、未再生任何登记 hash 的冻结工件；无新增登记位置、sha256 或字节数需要登记。

## Findings

### F-1: binding alternative cap 可在未穷尽替代 binding 时铸造 whole-layout routing-exhausted nogood

Severity: High soundness, guarded reachability。

位置：`src/search/benders_loop.py:5745-5790` 原始逻辑；修复后为 `src/search/benders_loop.py:5765-5797`。

原始代码在 routing 返回 `INFEASIBLE` 后读取 `EXACT_B1_BINDING_ALT_CAP`。当 `enumerated_bindings >= cap` 时，直接跳过 `binding_model.add_nogood_cut(selection)` 与下一次 binding 枚举，`break` 到 `_add_exact_whole_layout_nogood(... cut_type="routing_exhausted_nogood", binding_exhausted=True, routing_exhausted=True)`。这把“迭代预算耗尽”误写成“所有 binding alternatives 都已证明 routing 不可行”。

最小构造：一个候选 placement 有两个 binding choices；第一个 binding 的 routing 为 `INFEASIBLE`，第二个 binding 可行或至少未审；设置 `EXACT_B1_BINDING_ALT_CAP=1`。原始主循环在第一个 routing infeasible 后就 break 到 whole-layout nogood，可导致后续 master 将该 placement 排除，进而把存在可行替代 binding 的候选推进到 false-INFEASIBLE。

备注：public certified 入口当前会把 `EXACT_B1_BINDING_ALT_CAP` 视为 proof-semantics env 并阻断，因为它在 `_CERTIFIED_KNOWN_ENV_NAMES` 中但不在 `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`；对应 guard 在 `src/search/benders_loop.py:511-517`, `src/search/benders_loop.py:758-811`, `src/search/benders_loop.py:850-870`。但 `_run_exact_binding_and_routing()` 本身仍是主循环证明状态消费点，直接调用、测试 harness、未来 allowlist 漂移或非标准入口都不应把 budget cap 解释为证明。

修复：cap 命中且 `has_binding_alternatives` 仍为真时，立即 fail-closed 返回 `RUN_STATUS_UNKNOWN`，记录 `binding_status="ALT_CAP_REACHED"` 与 `binding_alternative_cap`，不添加 binding-level nogood，也不添加 master whole-layout nogood。只有无替代 binding 或替代绑定已实际由 CP-SAT 返回 `INFEASIBLE` 时，才允许进入 whole-layout routing-exhausted nogood。

回归：`src/tests/test_exact_contract.py:3322-3441` 新增 `test_binding_alt_cap_returns_unknown_without_whole_layout_cut`。该 probe 直接构造两个 binding alternatives，routing 固定 `INFEASIBLE`，cap=1，并把 `_add_exact_whole_layout_nogood` 替换为抛错哨兵。修复后返回 `UNKNOWN` 且未调用 whole-layout cut。

### F-2: routing solve unexpected/UNKNOWN 状态落入默认 INFEASIBLE 分支

Severity: Medium soundness hardening。

位置：`src/search/benders_loop.py:5726-5763` 修复后显式处理；原始代码只特殊处理 `FEASIBLE` 与 `TIMEOUT`，其它任何 routing status 均落入 routing-infeasible/binding-exhaustion 分支。

当前 `RoutingSubproblem.solve()` 的 producer contract 实际只返回 `FEASIBLE`、`INFEASIBLE`、`TIMEOUT`：guard deadline 返回 `TIMEOUT`，CP-SAT infeasible 返回 `INFEASIBLE`，其余非成功状态也返回 `TIMEOUT`，见 `src/models/routing_subproblem.py:1471-1585`。所以从未 monkeypatch 的现有 producer 看，`UNKNOWN` 不可达。

但是 Q1 要求穷举 TIMEOUT/UNKNOWN 不得变成 INFEASIBLE 或 CERTIFIED。原始主循环作为 consumer 没有显式 contract check：若 producer 未来新增 `UNKNOWN`、或测试/adapter 返回 `UNKNOWN`，它会走“routing infeasible”路径，进而可能枚举 binding nogood，或在无 alternatives 时添加 whole-layout routing-exhausted nogood。

修复：在 `routing_status == "TIMEOUT"` 分支之后新增显式 guard：`routing_status != "INFEASIBLE"` 一律 fail-closed `RUN_STATUS_UNKNOWN`，记录 `subproblem_status_contract_violation="unexpected_routing_status"`，不添加任何 cut。

回归：`src/tests/test_exact_contract.py:3444-3518` 新增 `test_unexpected_routing_status_returns_unknown_without_exact_safe_cut`。probe 用 fake routing 返回 literal `UNKNOWN`；修复后候选为 `UNKNOWN`，`exact_safe_cuts == []`，不会把 UNKNOWN 消费成 routing-exhausted nogood。

## Q1 子问题状态消费矩阵

表内“继续 master”指 `_EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE`，即当前候选不会直接被标记 `INFEASIBLE`；只有 master 在 cut 加入后重解并证明无解，caller 才返回 `RUN_STATUS_INFEASIBLE`。表内“ANY”表示后续维度不会被读取，是短路维度，不是默认吞噬分支。

| Binding status | Routing precheck | Routing solve / guard | 主循环动作 | 候选级结果 |
|---|---|---|---|---|
| `TIMEOUT` | ANY | ANY | 不建 routing，不加 cut，写 `binding_status=TIMEOUT` | `UNKNOWN` |
| `INFEASIBLE`，overload retry 未启用或 retry 仍 `INFEASIBLE` | ANY | ANY | 添加 `binding_infeasible_nogood` whole-layout cut；cut 失败则不继续证明 | cut 成功则继续 master；cut 失败为 `UNKNOWN` |
| `INFEASIBLE`，overload retry 为 `TIMEOUT` | ANY | ANY | 不加 whole-layout cut | `UNKNOWN` |
| `INFEASIBLE`，overload retry 为 `FEASIBLE` | 重新进入 FEASIBLE rows | 重新进入 FEASIBLE rows | 使用 retry binding model 继续 | 由后续 row 决定 |
| `FEASIBLE` | `front_blocked` 且 `binding_selection_safe_reject=True` 且存在 binding alternatives | 后续 routing 不运行 | 对当前 binding 添加 binding-level nogood，重解 binding | 新 binding `FEASIBLE` 则循环；重解 `TIMEOUT` 为 `UNKNOWN`；重解 `INFEASIBLE` 后进入 binding exhausted whole-layout cut |
| `FEASIBLE` | `front_blocked` 且无 alternatives，或安全标志不允许 binding-local reject | 后续 routing 不运行 | 走 D2/PCR/deletion-core/lazy-demand/cell-cut/fallback placement-local ladder；任一级 cut 成功则继续 master；无 cut 则不证明 | cut 成功则继续 master；无 cut 为 `UNKNOWN` |
| `FEASIBLE` | `relaxed_disconnected` 且存在 binding alternatives | 后续 routing 不运行 | 对当前 binding 添加 binding-level nogood，重解 binding | 新 binding `FEASIBLE` 则循环；重解 `TIMEOUT` 为 `UNKNOWN`；重解 `INFEASIBLE` 后 whole-layout cut |
| `FEASIBLE` | `relaxed_disconnected` 且无 alternatives | 后续 routing 不运行 | 直接进入 binding/routing exhausted whole-layout cut | cut 成功则继续 master；cut 失败为 `UNKNOWN` |
| `FEASIBLE` | `pass` | routing `FEASIBLE`, guard accept | routing subproblem 只在 connectivity guard accept 后返回 `FEASIBLE`；`extract_routes()` 也要求 guard accepted | `CERTIFIED` |
| `FEASIBLE` | `pass` | routing `FEASIBLE`, guard reject | 当前 producer 不会把该组合返回给主循环；guard reject 在 `RoutingSubproblem.solve()` 内添加 lazy connectivity cut 或 selected-route nogood 后重解 | 收敛后落到 guard accept / routing `TIMEOUT` / routing `INFEASIBLE` rows |
| `FEASIBLE` | `pass` | routing `FEASIBLE`, guard timeout | producer 映射为 routing `TIMEOUT` | `UNKNOWN` |
| `FEASIBLE` | `pass` | routing `TIMEOUT` | 不加 cut，写 `routing_status=TIMEOUT` | `UNKNOWN` |
| `FEASIBLE` | `pass` | routing `UNKNOWN` 或其它 unexpected status | 修复后显式 contract guard，不加 cut | `UNKNOWN` |
| `FEASIBLE` | `pass` | routing `INFEASIBLE`，存在 alternatives 且 cap 未命中 | 当前 binding 加 binding-level nogood，重解 binding | 新 binding `FEASIBLE` 则循环；重解 `TIMEOUT` 为 `UNKNOWN`；重解 `INFEASIBLE` 后 whole-layout cut |
| `FEASIBLE` | `pass` | routing `INFEASIBLE`，存在 alternatives 但 alt cap 命中 | 修复后不再断言 exhaustion；不加 binding nogood，不加 master cut | `UNKNOWN` |
| `FEASIBLE` | `pass` | routing `INFEASIBLE`，无 alternatives 或 alternatives 已由 binding CP-SAT 耗尽 | 添加 `routing_exhausted_nogood` whole-layout cut | cut 成功则继续 master；cut 失败为 `UNKNOWN` |

Guard 消费补充：`RoutingSubproblem.solve()` 在 `src/models/routing_subproblem.py:1516-1532` 仅当 `_validate_selected_route_connectivity()` 接受 incumbent 时返回 `FEASIBLE`；reject 时在 `src/models/routing_subproblem.py:1534-1569` 加 connectivity cut 或 fallback selected-route nogood 并继续；deadline 到达后在 `src/models/routing_subproblem.py:1480-1496` 返回 `TIMEOUT`。因此 `FEASIBLE+guard-reject` 在当前 producer contract 下不会越过 routing 子问题边界。

Binding alternatives 终止条件：`_binding_has_alternatives()` 只判断是否存在 binding/generic IO 变量；真正“剩余 alternatives 是否耗尽”由每次 `add_nogood_cut(selection)` 后的 binding CP-SAT `solve()` 返回 `FEASIBLE/TIMEOUT/INFEASIBLE` 决定。每次 binding-local nogood 排除当前 selection，有限域单调收缩；重解 `INFEASIBLE` 才证明 alternatives 穷尽。修复后的 alt cap 不再冒充该证明。

## Q2 nogood/cut 添加时机与作用域

Binding-level nogood：`binding_model.add_nogood_cut(selection)` 只加在当前 `PortBindingModel` 内，作用域是“当前 placement 下的当前 binding selection”。触发条件是 front/relaxed precheck 的 binding-local safe reject，或当前 binding 的 routing `INFEASIBLE`。它不会进入 master、不会 persisted 到其它 placement，也不会被复用到不同 binding model。

Master whole-layout `binding_infeasible_nogood`：只在 binding model 证明无 binding selection，且 overload-separation retry 没有恢复可行 binding 后添加。该 cut 的语义是当前 placement 的 binding 域为空；cut 添加失败时返回 `UNKNOWN`，不把候选归为 infeasible。

Master whole-layout `routing_exhausted_nogood`：只应在 binding alternatives 真实穷尽后添加。F-1 修复前 alt cap 可破坏这个条件；修复后 cap 命中返回 `UNKNOWN`。routing `TIMEOUT`、unexpected `UNKNOWN`、binding re-solve `TIMEOUT` 都不会添加该 cut。

front_blocked ladder：在 PCR-CUT env 关闭的 certified 默认下，PCR 分支不启用；后续 deletion-core、lazy-demand、cell-cut、fallback placement-local nogood 逐级尝试。每一级只有在构造出证据并成功添加 cut 后才继续 master；全部失败时返回 `UNKNOWN`。`minimize_routing_front_blocked_core()` 接收的是 `build_routing_visible_port_keys_by_instance(port_specs)`，见 `src/search/benders_loop.py:5469-5477`，不会把 routing-free 端口送入 deletion-core oracle。

Lazy connectivity cut：只存在于 routing 子问题内部，guard reject 后添加 source-side connectivity cut 或 selected-route nogood，并重解 routing model；主循环不会因为局部连通 incumbent 未过 guard 而返回 `CERTIFIED`。cut 不命中新 incumbent 时仍回到 routing solver，再次过 guard；deadline 到达则返回 `TIMEOUT`，主循环消费为 `UNKNOWN`。

Pre-binding L2/SAC/deletion-core 类 cut：`_run_certified_exact()` 中 L2/SAC separator 只在 separator 自己返回不可行/可加 cut 时继续 master；`TIMEOUT` 或 `FEASIBLE` 都落回 exact binding+routing verifier，不形成 certificate。

Persisted `exact_safe_cuts`：本轮确认主入口仍把 loaded persisted exact safe cuts 从证明输入中排除，只作为 telemetry/生成记录处理；没有把 V82 telemetry 当 proof hint 重放。

## Q3 多批修复交互缝

Wireless routing-free × A-2 binding 枚举：同步关系成立。master 侧从 `generic_io_requirements.required_generic_inputs` 计算 routing-free commodities 供 L2/SAC 使用，见 `src/search/benders_loop.py:4550-4557`。binding model 中 wireless sink virtual input slots 标记 `routing_free=True`/`virtual=True`，见 `src/models/binding_subproblem.py:753-769`；`extract_port_specs()` 跳过 routing-free/virtual inputs 与 routing-free sink commodity outputs，见 `src/models/binding_subproblem.py:1019-1045`。RAB 过滤同样只看 routing-visible ports，见 `src/models/binding_subproblem.py:569-575`。因此 binding alternatives 的枚举域和 routing/precheck 看到的端口集合一致。

F-BIND loader × session 构造：loader fail-closed 是 loud failure，不会被候选求解 catch-all 吞成 `UNKNOWN`。`load_wireless_sink_generic_input_slots()` 对缺文件、缺 key、非整数、负数均抛异常，见 `src/models/binding_subproblem.py:82-142`。`ExactSearchSession.create()` 直接调用 `load_generic_io_requirements_artifact()` 与 `load_wireless_sink_generic_input_slots()`，未捕获这些异常，见 `src/search/benders_loop.py:1571-1579`。`run_benders_for_ghost_rect()` 也直接构造/校验 session，未包 catch-all，见 `src/search/benders_loop.py:6154-6178`。被吞掉的只有 heartbeat callback 异常，见 `src/search/benders_loop.py:6095-6099`，不涉及配置 loader。

Lazy connectivity cut × guard：guard 仍是 certification 出口前的硬门。routing 子问题只有 guard accepted 才返回 `FEASIBLE`；guard reject 后 cut/nogood 只在 routing-local model 内单调累积并重解；deadline 返回 `TIMEOUT`。主循环收到 `TIMEOUT` 后 fail-closed `UNKNOWN`。未发现 cut 添加后新 incumbent 绕过 guard 的路径。

## Q4 epsilon ladder 与 max_lex 语义抽查

候选排序：`certified_frontier.candidate_sort_key()` 是 `(-area, -min_side, -max_side, -w)`，并且 `candidate_objective()` 是 `(area, min_side)`，见 `src/search/certified_frontier.py:163-172`。这实现 `max_lex(area, min_side)` 的主目标与 tie-break 扫描。

UNKNOWN frontier：默认情况下 `outer_search._compute_exact_frontier_state()` 只跳过 `CERTIFIED/INFEASIBLE`，不跳过 `UNKNOWN`，见 `src/search/outer_search.py:650-676`；`_terminal_stop_reason_for_status(RUN_STATUS_UNKNOWN)` 在 env 默认 off 时返回 `candidate_returned_unknown`，见 `src/search/outer_search.py:1591-1607`。串行路径收到 UNKNOWN 后 mark candidate UNKNOWN 并返回 `RUN_STATUS_UNKNOWN`，见 `src/search/outer_search.py:2543-2588`；并行路径也把第一个 UNKNOWN/UNPROVEN terminal reason 写入 campaign stop 后返回，见 `src/search/outer_search.py:2278-2304` 与 `src/search/outer_search.py:2384-2395`。`EXACT_OUTER_SKIP_UNKNOWN` 被显式标为非 strict blocker，见 `src/search/outer_search.py:104-112`。

best_certified_result：`ExactCampaign.mark_candidate_result()` 不会在单个 candidate `CERTIFIED` 时提升 `final_result`，它只记录 candidate solution，见 `src/search/exact_campaign.py:2130-2143`。最终结果只有 `_commit_terminal_full_frontier_certified_result()` 在 full-frontier evidence 有效后提交，见 `src/search/outer_search.py:853-879`。`ExactCampaign.best_certified_result()` 又反查 `has_valid_terminal_full_frontier_certified_evidence_for_project()`，见 `src/search/exact_campaign.py:2190-2201`。terminal evidence 还会拒绝 potential_domain/frontier 非空，见 `src/search/certified_frontier.py:403-420`。因此一个 higher-frontier `UNKNOWN` 会挡住较小 `CERTIFIED` 对 strict final 的宣告。

## 自验

已运行并通过：

```text
python -m pytest -q -p no:randomly src/tests/test_exact_contract.py
# 89 passed in 1.81s

python -m pytest -q -p no:randomly \
  src/tests/test_exact_outer_skip_unknown.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_wireless_front_consumers_r4.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py
# 33 passed in 0.63s

python -m pytest -q -p no:randomly \
  src/tests/test_routing.py::test_exact_routing_precheck_flags_relaxed_disconnected \
  src/tests/test_routing.py::test_exact_routing_precheck_flags_front_blocked \
  src/tests/test_routing.py::test_routing_placement_core_precheck_matches_grid_path \
  src/tests/test_routing.py::test_routing_subproblem_from_placement_core_matches_grid_build \
  src/tests/test_routing.py::test_routing_local_pattern_filter_reduces_state_space_without_changing_feasibility
# 5 passed in 0.30s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `python -m pytest -q -p no:randomly src/tests` 尝试过，但在沙盒 1200s 超时，中断时约到 14% 进度，无完整 pass/fail 汇总；因此本报告不声称全量套件完成。
