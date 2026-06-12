# 终末地 IndustrialPlanner cuts round 2 live exact-safe review

## 0. 快照与结论

审查对象只使用指定快照：`/mnt/data/zmd_cuts_r2_snapshot_db740254.zip`。开工前校验 sha256 结果为：

```text
db740254b993c2c5870698e220b10c7110a6624dfe19405b67cae1df653bc144  /mnt/data/zmd_cuts_r2_snapshot_db740254.zip
```

结论分两层：

1. **公开 certified 默认路径：本轮零 soundness finding。** 在默认 certified guard 下，`EXACT_USE_POSE_BOOL_MASTER`、`EXACT_B1_DELETION_CORE_CUT`、`EXACT_B1_LAZY_DEMAND_CUT`、`EXACT_B1_PATCH_ROUTING_CORE`、`EXACT_B1_D2_COMMODITY_FLOW` 等非默认 proof-semantics env 不是“打开后继续认证”，而是在 `run_benders_for_ghost_rect()` 入口被 fail-closed 为 `BLOCKED`，不会进入 master/subproblem/cut 写入阶段。
2. **附带 1 个 env-gated named hook 的 exact-safe hardening finding，已给补丁与回归。** 该问题位于 pose-bool delegate 的 cell-pattern cut。如果绕过或未来移除 certified env guard 并把 pose-bool/cell-cut 提升为认证路径，旧代码会把“有多个物理端口，但 binding 只需选择其中一个”的端口格当成必然激活端口，从而 over-cut 一个真实可行 placement。当前公开 certified 默认不会 false-CERTIFIED，因为 `EXACT_USE_POSE_BOOL_MASTER=1` 本身被 `pose_bool_master_not_certified` blocker 拦住。

补丁文件：`zmd_cuts_r2_cut_cell_pattern_exact_safe.diff`。补丁仅改源码与测试，不触碰 canonical 规则、candidate placement 冻结工件或登记 hash。

## 1. Finding

### CUT-R2-H1 — pose-bool cell-pattern cut 对可选 binding slot 过强；当前认证守卫阻断，但 hook 本身不是 exact-safe

Severity：**P2 hardening / env-gated certification-blocked**。如果未来 owner 将 `EXACT_USE_POSE_BOOL_MASTER` 或 cell-cut hook 提升为 certified 允许项而未带本补丁，则升级为 objective-level soundness 风险。

位置：

- `src/search/benders_loop.py:447-449`：`EXACT_USE_POSE_BOOL_MASTER` 被声明为 certified master-domain unsafe override，blocker code 为 `pose_bool_master_not_certified`。
- `src/search/benders_loop.py:6160-6188`：certified 入口收集 unsafe env blocker，非空时发布 `BLOCKED` metadata 并返回，不构建 master，也不进入 cut 生成链。
- `src/search/benders_loop.py:5327-5330`、`src/search/benders_loop.py:5529-5544`：若 pose-bool env 可达，front_blocked 回落链会调用 delegate 的 `add_routing_port_blocking_cell_cut()`。
- `src/models/pose_bool_exact_master.py:864-913`（原快照行号）：`_build_port_lookup_cache()` 原先把 raw physical port 全部登记为 routing-visible candidate；同时对已经是 global 坐标的 `occupied_cells` / `port_cells` 再加一次 anchor。
- `src/models/pose_bool_exact_master.py:1037-1061`（原快照行号）：cell cut 形状为 `sum(port_candidates) + sum(blocker_candidates) <= 1`。

旧代码隐含定理是：只要 pose 在 `port_cell` 有朝 `direction` 的物理端口，并且另一个 pose 占据 `front_cell`，两者同选就必定 routing front_blocked。这个定理少了一个关键前提：**该物理端口必须在任意 binding alternative 中都必然 active 且 routing-visible。**

反例是很小的、可复现的。构造一个 maker pose，有两个 input physical ports：`(0,1,N)` 与 `(1,1,N)`；operation input demand 只有 1；blocker 占 `(0,2)`，也就是第一个端口的 front cell。这个 placement 仍然可行，因为 binding 可以选择第二个输入端口 `(1,1,N)`，其 front `(1,2)` 未被占用。旧 cell cut 会把 maker 登记进 `(0,1,N)` 的 `port_candidates`，把 blocker 登记进 `(0,2)` 的 `blocker_candidates`，再添加 `maker + blocker <= 1`，从而把 `maker=1, blocker=1` 这个可行 placement 切掉。

另一个同源问题是 `_build_port_lookup_cache()` 对 pose 的 global cell 再加 anchor。仓库内 `_build_global_pose_cache()` 已注明 candidate pose data 是 global 坐标；旧 cache 的 double-anchor 会把 candidate alias 到错误 cell，轻则漏 cut，重则把 unrelated pose 带进 cut。

修法：

- 新增 `_mandatory_port_side_is_cell_pattern_exact(group_id, side_key, port_count)`，只有当该 side 的 visible demand 覆盖该 side 的所有物理端口时，才允许把 raw per-cell port 登记到 `_routing_visible_poses_by_port_at_cell_dir`。
- input side：canonical input 都 routing-visible，但 raw per-cell pattern 只有在 `input_demand >= physical_port_count` 时 exact。
- output side：必须满足 visible output 非零、visible output 等于 total output，并且 `output_demand >= physical_port_count`；mixed visible + routing-free output 继续交给更弱但有效的 lazy-demand/count cut。
- residual optional / RO pose 不具备 operation binding identity 时，不登记进 routing-visible raw per-cell index。
- `_build_port_lookup_cache()` 改为直接使用 global `occupied_cells` 与 `port_cells`，不再加 anchor；power pole occupied cache 同步改为 global。

回归：

- `test_pose_bool_cell_pattern_cut_refuses_inactive_binding_slot_overcut`：固定 maker 与 blocker 同选，确认 patched `add_routing_port_blocking_cell_cut()` 对 inactive binding slot 返回 `False`，且 CP-SAT 仍可行。
- `test_pose_bool_port_lookup_cache_uses_global_cells_without_anchor_shift`：确认 cache 使用 `(11,21)` 与 `(11,22,N)`，不会产生 phantom `(21,41)` / `(21,42,N)`。

## 2. Q1 live cut 族 exact-safe 对照

| cut 族 | 形状 | 有效性定理 / 前提 | 代码前提检查与 fail-closed | 结论 |
|---|---|---|---|---|
| binding-level nogood | 在当前 `PortBindingModel` 上添加 `sum(selected_decision_bool_lits) <= k-1`。fixed binding choice 不进 literals。 | 当某个完整 binding selection 已被 routing precheck 安全拒绝，或 exact routing 子问题证明该 binding infeasible，排除同一 binding tuple 不会切掉其它 binding。fixed choices 在当前 binding model 中不可变，省略 fixed lit 不放大作用域。 | `src/models/binding_subproblem.py:972-1005` 抽取 selection；`src/models/binding_subproblem.py:1090-1106` 添加 local nogood，空 literals 直接 no-op。调用点：`src/search/benders_loop.py:5278-5296` precheck safe reject；`src/search/benders_loop.py:5643-5667` relaxed_disconnected；`src/search/benders_loop.py:5818-5830` routing INFEASIBLE 且仍有 alternatives。`_binding_has_alternatives()` 在 `src/search/benders_loop.py:5966-5971`。 | 公开 certified 默认路径 sound。作用域是当前 binding subproblem，不持久化、不跨 candidate。 |
| master placement nogood | 对当前 master 添加 placement-local 或 whole-layout Benders cut：`sum(presence_lits(conflict_set)) <= |S|-1`，可带 condition_lits。 | 只有当 conflict_set 指定的 placements 已有新鲜 binding/routing proof 证明不可行时有效。empty-domain cut 只覆盖导致 domain empty 的 owner/blocker 证书；whole-layout cut 只在 binding/routing alternatives 耗尽后有效。 | empty binding domain 与 RAB-SEP 证书：`src/search/benders_loop.py:4990-5079`；binding infeasible whole-layout：`src/search/benders_loop.py:5151-5181`；front_blocked legacy placement-local fallback：`src/search/benders_loop.py:5545-5584`；routing exhausted whole-layout：`src/search/benders_loop.py:5853-5884`。结构化登记与 master 添加在 `_add_exact_persisted_nogood()`：`src/search/benders_loop.py:5997-6043`；whole-layout power witness synthetic pole 不完整时 fail-closed skip：`src/search/benders_loop.py:6045-6093`。 | 公开 certified 默认路径 sound。 |
| routing deletion-core cut | 若启用，会把 deletion-minimized core 作为 master Benders cut：`delegate.add_benders_cut(core_instance_pose_map)`。 | 有效性来自 front_blocked oracle invariant：初始 layout 已 front_blocked；每次删除 candidate 后只有 oracle 仍 front_blocked 才接受删除；因此最终 core 仍 front_blocked。若初始 oracle 不认，则回落 full layout，不比原 precheck 更强。 | 该 hook 需要 `EXACT_USE_POSE_BOOL_MASTER=1` 且 `EXACT_B1_DELETION_CORE_CUT=1`，公开 certified 入口会因 non-default proof-semantics env fail-closed。内部最小化：`src/search/routing_deletion_core_minimizer.py:41-68` 只使用 routing-visible `port_specs`；`src/search/routing_deletion_core_minimizer.py:82-144` oracle；`src/search/routing_deletion_core_minimizer.py:185-230` initial replay 与 deletion invariant。调用点：`src/search/benders_loop.py:5466-5513`。 | 默认 certified 不可达；hook 内部没有发现 over-cut，但它用的是 front_blocked oracle replay，不是完整 routing CP-SAT replay。 |
| lazy-demand cut | 对某 pose side 添加 demand-count cut，要求至少 visible demand 个 front cell 可清：等价于限制 blockers 数量，条件化在 pose_var 上。 | 只要 side 上有 `d` 个 routing-visible demand，则任何可行 routing 至少需要 `d` 个可用 front cells。对 mixed visible + routing-free output，只计 visible demand，因此 cut 更弱但不 over-cut。 | `src/models/pose_bool_exact_master.py:116-137` 计算 visible demand，routing-free sink output 被排除；`src/models/pose_bool_exact_master.py:955-1019` 添加 lazy-demand cut。`src/models/binding_subproblem.py:563-605` 与 `src/models/binding_subproblem.py:1007-1073` 也在 binding/domain 与 port_specs 输出侧跳过 routing-free sink commodity，生成侧与 F04-R4-03 对齐。该 hook 在公开 certified 中因 env guard 不可达。 | 默认 certified 不可达；生成公式本身 sound。 |
| cell-cut / routing-port blocking cell cut | `sum(poses_with_active_visible_port_at(port_cell, dir)) + sum(poses_occupying(front_cell)) <= 1`。 | exact 前提必须是：port candidate 中每个 pose 被选中时，该具体 physical port 必然 active 且 routing-visible。否则 blocker 可能只挡住 inactive binding slot，placement 仍可行。 | 原快照未检查该 per-port 必然 active 前提，见 CUT-R2-H1。补丁后 `_mandatory_port_side_is_cell_pattern_exact()` 只登记 demand 覆盖全部 physical ports 的 side；并修正 global coord cache。该 hook 在公开 certified 中因 env guard 不可达。 | 公开 certified 默认无 false-certified；hook 已补丁。 |
| lazy connectivity cut | routing subproblem 内部 source-side component cut：`sum(route_vars crossing source-side W to complement) >= 1`；若 self-check 不通过，回退 selected-route nogood。 | 对当前 routing CP-SAT incumbent，若所有 sources 在 W、无 sink 在 W，且 crossing 集合完整，则任意可行 route 必须使用至少一条 crossing edge。 | `src/models/routing_subproblem.py:1233-1331` self-check；`src/models/routing_subproblem.py:1333-1387` 添加 cut 或 fail-closed fallback；`src/models/routing_subproblem.py:1592-1623` incumbent 被 guard 拒绝后添加 connectivity cut，失败则 selected-route nogood。 | 本体既有双独立零 finding；本轮只看交互，未发现其它 cut 借它放大作用域。 |

## 3. Q2 作用域、生命周期、resume / `exact_safe_cuts` 消费点

### 3.1 作用域与生命周期

| cut 族 | 添加到哪里 | 存续 | 跨 candidate / 跨 instance lifting |
|---|---|---|---|
| binding-level nogood | 当前 `PortBindingModel` CP-SAT model。 | 只在当前 master placement 的 binding alternative 枚举循环内存活。binding re-solve 时旧 no-good 仍在同一个 binding model 上，只排除已证伪的 selection tuple。 | 无持久化，无跨 candidate。 |
| master placement nogood | 当前 `MasterPlacementModel`。 | 当前 `run_benders_for_ghost_rect()` 中随 master 迭代存活；新 candidate / resume 不直接重放。 | 不做 instance-signature lifting；conflict_set 以当前 solution instance_id → pose_idx 建立。 |
| routing deletion-core | 当前 pose-bool master delegate。 | 只在进程内当前 master 存活；不登记 `generated_exact_safe_cuts`。 | 默认 certified blocked；hook 无持久化。 |
| lazy-demand / cell-cut | 当前 pose-bool master delegate。 | 只在当前 master 存活；不进入 `exact_safe_cuts`。 | 默认 certified blocked；hook 无持久化。 |
| lazy connectivity cut | 当前 `RoutingSubproblem`。 | 只影响当前 routing CP-SAT solve 的 incumbent rejection / proof。 | 不写 master，不持久化。 |
| persisted `exact_safe_cuts` | campaign/checkpoint JSON telemetry。 | resume 后只用于 schema/hash/计数/metadata；certified run 会重新生成 fresh cuts。 | V82 边界在代码里强制：不作为 proof object，不加回模型。 |

### 3.2 `exact_safe_cuts` resume 消费点穷举

我按 `exact_safe_cuts`、`preloaded_exact_safe_cuts`、`get_candidate_cuts`、`loaded_exact_safe_cuts`、`generated_exact_safe_cuts`、`persisted_exact_safe_cut` 全仓搜索，消费点如下：

- `src/search/exact_campaign.py:1441-1454`：resume state validation 中将 raw cut 经 `BendersCut.from_dict()` parse，并检查 condition domain；这是 schema/telemetry 校验，不 apply。
- `src/search/exact_campaign.py:1909-1911`：`get_candidate_cuts()` 返回 candidate record 中的 telemetry list。
- `src/search/exact_campaign.py:2039-2112`：`mark_candidate_result()` 写回 `exact_safe_cuts` 与计数。
- `src/search/outer_search.py:949-966`、`src/search/outer_search.py:1294-1308`：把 run metadata / worker metadata 复制进 campaign payload。
- `src/search/outer_search.py:2238-2245`：resume/parallel 前建立 `preloaded_cut_map`，来源是 `exact_campaign.get_candidate_cuts()`。
- `src/search/exact_parallel_scheduler.py:151-179`：把 preloaded cuts 放进 `WorkerTask`；`src/search/exact_parallel_scheduler.py:280-296`：worker 调用 `run_benders_for_ghost_rect(... preloaded_exact_safe_cuts=...)`；`src/search/exact_parallel_scheduler.py:300-309`：worker result 只回传 metadata 中的新 telemetry。
- `src/search/benders_loop.py:6430-6446`：certified run 统计输入 persisted cut 数量，但 V82 注释后强制 `raw_candidate_cuts = []`。
- `src/search/benders_loop.py:6447-6479`：保留的 replay loop 在 certified 下因 `raw_candidate_cuts=[]` 无元素可执行。
- `src/search/benders_loop.py:6771-6775`：run metadata 输出 `persisted_exact_safe_cut_replay_enabled=False`，并记录 loaded/generated 数量。

结论：V82 “telemetry-only，不是 proof object” 边界是代码强制的。resume 后没有发现任何 certified path 将 persisted `exact_safe_cuts` 直接加回 master 当约束。`CutManager.load()`/`cuts_for_stage()` 等框架能力没有被 campaign `exact_safe_cuts` runtime 消费。

## 4. Q3 cut 间交互

公开 certified 默认下，实际可能组合的是 binding-level nogood、fresh master placement nogood、routing subproblem 内部 lazy connectivity cut，以及 legacy front_blocked placement-local fallback。每个 cut 都有独立 proof 前提，不依赖“其它 cut 已经存在”才成立；因此它们的交集仍是可行域的安全子集。

重点交互检查：

- binding nogood + master placement nogood：binding nogood 只在当前 binding model 排除一个已证伪 selection；master placement nogood 只有在 placement-level proof 已形成时写 master。二者不共享条件 literal，也不把 binding-level 信息持久化到 candidate 之间。
- lazy connectivity cut + master cuts：connectivity cut 只在 routing subproblem 内拒绝不连通 incumbent。若 routing 最终 `INFEASIBLE`，外层优先加 binding nogood 继续枚举 alternatives；只有 alternatives 耗尽才添加 whole-layout routing_exhausted nogood。
- front_blocked 回落链：PCR-CUT、D2、deletion-core、lazy-demand、cell-cut、legacy placement-local cut 是强到弱/不同粒度的梯子。PCR/D2 exception 路径只打印并 fall through，不留下 partial constraint；deletion-core 若启用但未形成 cut，最多造成 no-cut/UNKNOWN，不是 over-cut。默认 certified guard 下这些非默认 env hook 不进入。
- CUT-R2-H1 是唯一发现的潜在交互风险：旧 cell-cut 把 binding slot 的“可能端口”升级成 master placement 的“必然端口”。补丁后 per-cell port candidate 只来自必然 active 的 side，恢复独立有效性。

## 5. Q4 `src/cuts/` F1-F9 框架边界

`src/cuts/` 框架仍是独立 lifecycle/store/replay scaffolding，不是本轮公开 certified runtime 的 cut 写入路径。

- Family map 位于 `src/cuts/lifecycle.py:57-67`：F1 `region_capacity`、F2 `cutset`、F3 `port_exposure`、F4 `component_reach`、F5 `pattern_nogood`、F6 `shape_packing_hall`、F7 `power_hitting_set`、F8 `power_grid_reach`、F9 `density_envelope`。
- `src/cuts/lifecycle.py:716-725`：`step_2_minimize()` 仍 `NotImplementedError`。
- `src/cuts/lifecycle.py:926-969`：`step_6_attach_scope_check()` 做 attach/scope guard，不 apply master。
- `src/cuts/lifecycle.py:1058-1099`：`step_7_evaluate_cut()` 只评价 cut 是否 violated。
- `src/cuts/lifecycle.py:1106-1110`：`step_8_apply_to_master()` 仍 `NotImplementedError`，这是显式未接线边界。
- `src/cuts/replay.py:75-180`：`replay_cut()` 只返回 reactivation/hold/quarantine 语义；未发现 certified master apply。
- 全仓搜索未发现 `src/search/benders_loop.py`、`src/models/master_model.py` 或 certified outer search runtime 导入 `CutStore` / `replay_cut` / F1-F9 lifecycle 并把 family cut 加入 master。相关调用集中在 tests/scripts/report builders。

PCR-CUT/Phase 4 hook 不属于 `src/cuts/` F1-F9 apply-to-master；它在 `src/search/benders_loop.py:5331-5342` 受 `EXACT_B1_PATCH_ROUTING_CORE` env gate 控制。该 env 默认 off；在 certified run 中非默认 proof-semantics env 会被入口 guard blocking，因此默认 certified 零影响。

## 6. 补丁与冻结工件条款

补丁：`/mnt/data/zmd_cuts_r2_cut_cell_pattern_exact_safe.diff`

应用方式：

```bash
cd project
patch -p1 < /path/to/zmd_cuts_r2_cut_cell_pattern_exact_safe.diff
```

`patch --dry-run -p1` 已在原始快照目录验证通过。

冻结工件：本补丁仅修改：

- `src/models/pose_bool_exact_master.py`
- `src/tests/test_wireless_front_consumers_r4.py`

不修改 `candidate_placements.json`、canonical rules、hash registry、preprocess artifacts 或任何冻结工件，因此不需要再生冻结工件，也没有新的登记 sha256/字节数清单。

## 7. 自验

已完成：

```bash
python -m pytest -q src/tests/test_wireless_front_consumers_r4.py -p no:randomly
# 7 passed in 1.06s

python -m pytest -q src/tests/cuts src/tests/test_p0_certified_soundness_fixes.py src/tests/test_wireless_front_consumers_r4.py -p no:randomly
# 482 passed in 8.38s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

python -m pytest -q \
  src/tests/test_v82_persisted_cut_replay_fail_closed.py \
  src/tests/test_regression.py::test_resume_does_not_replay_persisted_exact_safe_cuts_into_master \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  -p no:randomly
# 14 passed in 1.69s
```

尝试过全量：

```bash
python -m pytest -q src/tests -p no:randomly
```

该全量命令在 300 秒沙盒超时处被终止，进度约 16%，超时前没有失败输出。未完成的全量 run 不计为全绿声明。
