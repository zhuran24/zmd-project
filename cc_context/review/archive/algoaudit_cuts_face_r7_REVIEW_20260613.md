# 终末地 IndustrialPlanner cuts 机制面 round 7 审查报告

快照校验：`/mnt/data/zmd_snapshot_37b84be0.zip` 的 sha256 为 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`，与任务指定值一致。只解包并审查该快照，仓库根为 zip 内 `project/`。依赖包 `zmd_py313_linux_x86_64.zip` 已离线安装到 Python 3.13 venv 后用于定向测试。

结论：**本轮零 soundness finding**。R6 的 `PCR-CUT-R6-H1` terminal-front membership 修复在本轮攻击面下确认 sound；QuickXplain/replay 本体没有发现可导致 unsound cut 的实现偏差；patch 构造与 separator 对接没有发现口径错位或跨 patch 污染。

说明：本轮只审 `R6-H1 修复确认 + QuickXplain/replay + patch 构造与 separator 对接`。绑定、routing、preprocess、master 几何和其它同期修复面未重新展开。

---

## Q1：PCR-CUT-R6-H1 修复确认

### Q1-1 新判据「connector 或 front ∈ patch」完备性

结论：完备，未发现第三种需要端口语义的 patch 相交形态。

相关代码：

- `src/models/patch_routing_core.py:119-159`：`build_local_pose_signature()` 只要 connector `(x, y)` 或 terminal front `(fx, fy)` 与传入 cell set 相交，就保留端口条目。
- `src/models/patch_routing_core.py:325-338`：`_index_port_fronts()` 按 terminal front 是否在 `_patch_free_cells` 内建立 source/sink terminal front。
- `src/models/patch_routing_core.py:562-632`：`_add_port_adherence()` 只跳过 connector 与 front 均不在 patch 的端口；其余端口按 front 是否 patch-active 分支处理。
- `src/search/patch_conflict_separator.py:314-330`：separator `_build_patch_inputs()` 也按 connector 或 front 任一在 patch 内收集 `PatchPortSpec`。

形态拆分如下：

| 形态 | 处理结果 | soundness 判读 |
|---|---|---|
| connector 在 patch 内，front 在 patch 内 | indexed front + exact adherence | 与完整 routing 的 terminal front 语义一致 |
| connector 在 patch 外，front 在 patch 内 | indexed front + exact adherence，owner 进入 assumptions/support | R6-H1 的核心反例已补齐 |
| connector 在 patch 内，front 在 patch 外 | 不建内部 exact link；若 front 在 full active，则由 boundary relaxation 吸收 | patch 是 over-approx，不会比 full 更严格 |
| connector 与 front 都在 patch 外，但路线穿过 patch | 无端口语义；普通 cell-to-cell transit 由 boundary vars 处理 | terminal 不在 patch，端口不应成为 patch 内约束 |
| front 在 patch 内但被 occupied | `_patch_active_cells_by_commodity` 不含该 front；owner assumption 下 forbid owner，缺 owner 时 fail-closed infeasible | 与 full routing 的 blocked terminal front 一致；separator support 会把 blocker 加回 core |

定向 probe 覆盖了四个边界：外部 connector 双 front-in-patch 可行、connector-in/front-out 被 boundary 吸收、front-in-patch occupied 时 blocker 被 support augmentation 加回、connector/front 都在 patch 外的 transit 状态可由 boundary relaxation 可行化。probe 输出：`R7 probe bundle passed: Q1 terminal-front cases + Q2 subset/QX cap fallback`。

### Q1-2 front-in-patch 外部端口的 adherence 语义

结论：修后是 exact terminal link，不是无条件 link；owner assumption 来自 separator 的 port collection 与 support collection，缺 assumption 时直接 fail-closed 或产生无法接受的 core 路径。

代码路径：

- separator 先把 front-in-patch external connector 收进 `patch_ports`：`src/search/patch_conflict_separator.py:314-330`。
- `support_instance_ids.update(pp.instance_id for pp in patch_ports if pp.instance_id)` 保证 patch port owner 进入 `PoseAssumption`：`src/search/patch_conflict_separator.py:337-352`。
- `_add_port_adherence()` 对 front 在 patch active 内且有 route vars 的端口，在 owner assumption literal 为真时加 `sum(vars_for_port) == 1`：`src/models/patch_routing_core.py:584-632`。

因此 front-in-patch external source/sink 的 terminal side 会像完整 `RoutingSubproblem` 一样在 front cell 上 exact-one 接驳。`RoutingSubproblem` 的对应语义在 `src/models/routing_subproblem.py:786-799` 与 `src/models/routing_subproblem.py:1196-1231`，极性一致：source 使用 `DIR_OPP[dir]` 作为 incoming terminal side，sink 使用 `DIR_OPP[dir]` 作为 outgoing terminal side。

probe 中 `patch_cells={(1,0),(2,0)}`、source connector `(0,0)`、sink connector `(3,0)` 均在 patch 外，fronts 均在 patch 内。结果：`_patch_port_fronts_source == {(1,0,"W","ore"): 1}`，`_patch_port_fronts_sink == {(2,0,"E","ore"): 1}`，`port_adherence.exact_links == 2`，patch solve 为 `FEASIBLE`。

### Q1-3 反向情形：connector 在 patch 内但 front 在 patch 外

结论：修前已有处理，修后语义没有变强；front 出 patch 且在 full active 时被 boundary relaxation 吸收。

关键代码：`src/models/patch_routing_core.py:584-594`。front 不在 patch-local active set 时，代码检查 `front_in_full = (fx, fy) in self.full_grid_active_cells[commodity]`。若 boundary relaxation 开启且 front 在 full active 内，则直接 `continue`，不加 exact internal terminal link，也不 forbid owner。

这正是 over-approx：完整 routing 的 terminal front 位于 patch 外，patch 内没有必要证明外部 routing 如何接上该 port。若 front 不在 full active，说明 front blocked 或越界，则在 owner assumption 下 forbid owner：`src/models/patch_routing_core.py:595-600`。

probe 中 patch 含 occupied connector `(0,0)` 但不含 front `(1,0)`，full active 含 `(1,0)`。构建统计为 `exact_links=0`、`unconditional_links=1`、`blocked_ports=0`，solve 为 `FEASIBLE`。

### Q1-4 signature 纳入的对称性

结论：新增 front-in-patch external port 维度只会细分 equivalence class，不会把不等价 pose 合并。

`build_local_pose_signature()` 的等价键包括：facility type、operation type、footprint cells、以及所有 connector/front 与传入 cell set 相交的端口条目 `(x, y, dir, commodity, type)`，见 `src/models/patch_routing_core.py:97-159`。master lifting 逐 owner 枚举 pose，并重新计算同一个 signature 后比较，见 `src/models/pose_bool_exact_master.py:720-759` 与 `src/models/pose_bool_exact_master.py:761-828`。

separator 传给 master 的不是裸 `spec.cells`，而是 `support_signature_cells = patch + cardinal ring`，见 `src/search/patch_conflict_separator.py:332-354` 和 `src/search/patch_conflict_separator.py:497-499`。这使 signature 同时覆盖 patch 内 footprint、boundary-neighbor occupancy support，以及 front-in-patch external connector 的 owner pose。结果可能比最小等价类更细，但这是安全的弱化，不是 over-cut。

probe 比较了同一 footprint 下「有 external connector，front 在 patch 内」与「无该 port」的两个 pose。修后 signature 不相等，且 port 条目为 `((0, 0, "E", "ore", "out"),)`，不会把 terminal 影响 patch 的 pose 与不影响 patch 的 pose 合并。

### Q1-5 与 H3 support 的对接

结论：外部 connector owner 会进入 support assumptions；front blocker 也会进入 support assumptions；accepted cut 使用 support augmentation 后不会只 blame victim。

相关代码：

- `src/search/patch_conflict_separator.py:121-143`：support signature cells 为 patch cells 加四向 cardinal ring。
- `src/search/patch_conflict_separator.py:337-342`：support owner 来自 support cells 上的 occupancy owner，且显式加入所有 `patch_ports` 的 `instance_id`。
- `src/search/patch_conflict_separator.py:146-162`：`_augment_core_with_patch_support()` 把 solver core 与 support assumptions 合并，额外 term 只会弱化 nogood。
- `src/search/patch_conflict_separator.py:477-481`：separator 在 master cut 前执行 support augmentation。

front-in-patch external connector 与 terminal front 相邻，因此 connector cell 必然在 patch 的 cardinal ring 中；即使 owner map 有异常，`patch_ports` 的 `instance_id` 也会把该 owner 加进 support assumptions。front 被 blocker 占用时，blocker 位于 patch cell 或 cardinal support ring，`_augment_core_with_patch_support()` 会把 blocker owner 加到 master terms。

probe 中 victim connector `(0,0)` 在 patch 外，front `(1,0)` 在 patch 内且被 blocker 占用。`_build_patch_inputs()` 得到 assumptions `{victim, blocker}`；patch model INFEASIBLE；lifecycle accepted；augmentation 后 core owner 集仍为 `{victim, blocker}`。

---

## Q2：QuickXplain 最小化与 replay 本体

### Q2-1 oracle 单调性前提

结论：满足。assumption subset 的方向是「assumption 越多，模型越受约束，INFEASIBLE 越可能」。

实现细节：

- 初次 solve 对所有 `_assumption_vars` 调 `model.AddAssumption(var)`：`src/models/patch_routing_core.py:641-653`。
- replay/QX 通过 `_add_assumption_subset()` 清空 `model.Proto().assumptions` 后只添加当前 subset 的 literals：`src/models/patch_routing_core.py:757-770`。
- 未被 assumption 的 BoolVar 是自由变量，solver 可令其为 false，从而关闭 `OnlyEnforceIf(v)` 的 port adherence 或满足 `v.Not()` 的 blocked-port forbid。把某个 literal 加进 subset 等价于强制该 owner pose 存在，只会增加约束。

probe 结果：在一个只有 owner `A` 的 terminal front 被 blocked、decoy `D` 无端口的模型上，subset statuses 为：`empty=FEASIBLE`、`D=FEASIBLE`、`A=INFEASIBLE`、`A_D=INFEASIBLE`。方向正确。

### Q2-2 QX 递归实现对照

结论：递归形态符合 QuickXplain 的 monotone conflict minimization 结构，没有发现返回 SAT core 后被直接消费的路径。

代码：`src/models/patch_routing_core.py:886-914`。

递归逻辑为：若 background 已 infeasible，返回空增量；若 candidates 为空，返回空；若单元素且 background 可行，返回该元素；否则分割 `c1/c2`，先在 `background ∪ c1` 下解释 `c2`，再在 `background ∪ x2` 下解释 `c1`，返回并集。这与 monotone predicate `oracle(S) := solve_with_subset(S) == INFEASIBLE` 的方向匹配。

更重要的是，QX 结果不直接进入 master cut。`extract_and_validate_patch_core()` 总是先 replay raw core，再 replay QX core；QX core replay 不复现 INFEASIBLE 时 fallback 到已 replay-valid 的 raw core，见 `src/models/patch_routing_core.py:948-987`。

### Q2-3 cap 命中路径

结论：cap 命中不会产生 unsound cut。实现注释说 cap 时返回 conservative remaining candidate set，但实际有一条更保守的 fail-closed/fallback 行为：若 cap 在 `oracle(background)` 调用处触发，QX 可能返回空或非最小候选；下游 replay 会兜住，invalid 则 fallback raw。

关键代码：

- cap 判定在 `oracle()` 内：`src/models/patch_routing_core.py:886-894`。
- QX result 仍会经过 `validate_patch_core()`：`src/models/patch_routing_core.py:976-987`。
- metadata 暴露 `quickxplain.capped`：`src/search/patch_conflict_separator.py:487-491`。

probe 设 `oracle_call_cap=0`，QX 立即 capped 并返回一个 replay-invalid minimized core；`extract_and_validate_patch_core()` 返回 `accepted=True`、`reason="minimization_failed_replay_fallback_raw"`，且 `minimized_validation.candidate_core == raw_validation.candidate_core`。因此下游消费的是 raw validated core，不是 invalid QX core。

本轮不把 “cap 时 core 不保证最小” 当 finding；这是已知弱 cut 方向。当前 metadata 中 `quickxplain.capped=True` 可区分该情形，未发现把 capped result 当 proof-minimal 消费的 soundness 风险。

### Q2-4 replay validate 的独立性

结论：replay 使用同一个 `CpModel` 对象但新建 `CpSolver`，并只通过 assumptions proto 字段改变启用 subset；没有增量 solver 状态、hint 或上一轮搜索状态复用。对 replay 的 proof 目的而言足够独立。

代码：`src/models/patch_routing_core.py:772-804`。每次 `_solve_with_subset()` 都创建新的 `cp_model.CpSolver()`，设置 time limit、presolve、workers 和 memory cap，然后 `solver.Solve(core.model)`。`validate_patch_core()` 默认 `presolve=False, workers=1`，见 `src/models/patch_routing_core.py:807-851`。

同对象重解的唯一共享状态是 CP model 的约束本体；assumptions 被 `_add_assumption_subset()` 明确清空并重建。没有看到 solver 对象复用、solution hint 注入或 assumption cache 复用。

### Q2-5 replay 后到 master cut 前的 core 改写

结论：唯一实质改写是 support augmentation；不需要二次 replay，因为它是 replay-valid core 的 assumption superset，且 assumption monotonic 已成立。

代码：

- replay-valid core 选择：`src/search/patch_conflict_separator.py:477-479`。
- support augmentation：`src/search/patch_conflict_separator.py:479-481`。
- master terms 转换与 add：`src/search/patch_conflict_separator.py:481-499`。

若 `C` 在 patch model 下 INFEASIBLE，则 `C ∪ S` 在同一 model 下仍 INFEASIBLE；augmentation 只会让 master nogood 更弱。后续 `PoseBoolExactMasterDelegate.add_patch_routing_core_cut()` 会重新用 support cell set 做 signature lifting，并在 unknown instance、pose out of range、empty equivalent vars、lifted var overlap 时 fail-closed 返回 `added=False`，见 `src/models/pose_bool_exact_master.py:775-828`。未发现 replay 后有会加强 core 或删除必要 owner 的路径。

---

## Q3：patch 构造与 separator 对接

| 审查点 | 代码位置 | 结论 |
|---|---|---|
| patch cells 选择与收集口径 | `src/search/patch_conflict_separator.py:207-288`，`src/search/patch_conflict_separator.py:291-354` | candidate 生成阶段先按 `max_cells` 过滤，返回的 `_PatchCandidateRecord.cells` 就是最终 patch。`_build_patch_inputs()` 只消费 `candidate.cells`，没有用截断前快照收集 ports/active/support。口径一致。 |
| top-K/cap 截断 soundness | `src/search/patch_conflict_separator.py:248-264`、`src/search/patch_conflict_separator.py:266-288` | 大 patch 被跳过，不会缩成另一种 patch 后继续沿用旧 witness。跳过只损失发现 cut 的机会，不会产生 over-cut。 |
| precheck summary → patch 字段保真 | `src/search/benders_loop.py:5381-5500`，`src/search/patch_conflict_separator.py:388-406` | PCR separator 不从 `routing_precheck_summary` 的 blocked_port/commodity 字段重建 patch ports；它使用 binding 后的 `port_specs` 原始字段。`PatchPortSpec` 转换保留 `instance_id/x/y/dir/type/commodity/pose_idx`，未发现 F-RT-R2-01 式方向/极性二次翻译点。 |
| `full_grid_active_cells` 来源时点 | `src/search/patch_conflict_separator.py:309-313`，`src/search/benders_loop.py:5246-5286`、`src/search/benders_loop.py:5468-5477` | active cells 在 `_build_patch_inputs()` 中由传入的同一 `placement_solution` 重算 occupancy/free cells；`port_specs` 来自同一 iteration 的 binding model。PCR 调用发生在 routing precheck front_blocked 分支内，master solution 没有在中间被改写。 |
| occupied/owner support 来源 | `src/search/patch_conflict_separator.py:49-65`、`src/search/patch_conflict_separator.py:309-342` | occupied 与 owner_by_cell 同源于 `placement_solution + facility_pools`。support assumptions 来自 patch+cardinal ring owner 和 patch_ports owner。 |
| 多 patch 逐个评估状态隔离 | `src/search/patch_conflict_separator.py:431-520` | 每个 candidate 都新建 `PatchSpec`、`PatchRoutingCore`、assumptions、patch_ports、support set。失败 patch 的 replay/QX 只修改自己的 model；master 只在 `add_patch_routing_core_cut()` 成功时被修改。add 失败返回 rejected 并继续，未发现污染后续 patch 的状态。 |
| master cut add fail-closed | `src/models/pose_bool_exact_master.py:779-828`，`src/search/patch_conflict_separator.py:497-520` | master delegate 对 unknown instance、pose idx 越界、无 equivalent vars、lifted var overlap 均返回 `added=False` 且不 Add constraint。separator 只有 `added` 为真才 accepted 并 return。 |
| `require_replay` 参数 | `src/search/patch_conflict_separator.py:403`、`src/search/patch_conflict_separator.py:466-471` | 参数当前未被用作关闭 replay 的开关；实际路径始终调用 `extract_and_validate_patch_core()`。这是偏保守行为，不是 soundness 风险。 |

整体结论：patch 选择可以因 top-K 和 `max_patch_cells` 变弱，但收集 port、active cells、support assumptions 的口径始终跟最终 candidate patch 走；没有发现 “候选 patch 被截断，但 ports/support 仍按旧 patch 收集” 的错位。

---

## 自验记录

已执行：

```bash
sha256sum /mnt/data/zmd_snapshot_37b84be0.zip
# 37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd

python -m pytest -q -p no:randomly src/tests/test_patch_routing_core.py
# 17 passed in 3.86s

python -m pytest -q -p no:randomly \
  src/tests/test_patch_routing_core.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py
# 34 passed in 4.08s

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

PYTHONPATH=. python ../review_probe_r7.py
# R7 probe bundle passed: Q1 terminal-front cases + Q2 subset/QX cap fallback
```

全量测试也启动过：

```bash
python -m pytest -q -p no:randomly src/tests
```

沙盒 300 秒超时，超时前进度约 16%，未出现 failure。本报告不宣称全量 pytest 完成。

---

## 最终状态

**本轮零 soundness finding**。没有生成补丁。R6-H1 的 terminal-front membership 修复已覆盖 port indexing、adherence、separator collection、local signature lifting 四个原漏洞点；QuickXplain/replay 的不确定路径由 replay/fallback 兜住；patch 构造与 separator 对接未发现会产生 unsound master cut 的错位。
