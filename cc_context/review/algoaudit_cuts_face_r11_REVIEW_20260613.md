# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 11 REVIEW

## 0. 快照与结论

- 指定快照: `/mnt/data/zmd_snapshot_eca69648.zip`
- 实测 sha256: `eca696483abee31138cdbdcc3cf67a8912f5e13f3b5291821cab67fffbae1302`
- 校验结论: 与任务指定值一致。
- 解包根: `/mnt/data/zmd_r11_work/project`
- 依赖环境: Python 3.13.5 + OR-Tools 9.15.6755, 从 `/mnt/data/zmd_py313_linux_x86_64.zip` 离线安装。

## 1. Finding 汇总

本轮零 soundness finding。

没有发现新的 over-cut / false-INFEASIBLE 方向问题；也没有发现会把“不确定/弱证明”升级成更强 master cut 的路径。未修改代码，因此无补丁包。

独立判断: cuts 面在本轮可视为达到饱和下沿。这里的“饱和”不是说未来永远不可能有工程灰尘，而是说在当前快照、当前 cuts 入口与现有宪法边界内，我没有找到可复现或可严谨成立的 soundness 缝；r10 零之后，本轮形成 cuts 面连零 2。

## 2. Q1: CUT-R10-L1 修复确认 + r9/r10 D2 链路

### 2.1 D2 port owner 前置校验

结论: CUT-R10-L1 修复成立。

关键代码:

- `src/search/d2_separator.py:172-200` `_d2_port_owner_validation_error()`
- `src/search/d2_separator.py:250-259` 在 `run_d2_separation()` 一进入正式占用格、precheck、D2 build 前先调用 owner 校验
- `src/search/d2_separator.py:295-301` owner assumptions 为空时继续 fail-closed
- `src/models/pose_bool_exact_master.py:919-968` master delegate 对未知 instance、非法 pose、重复 literal alias 均拒绝加 cut

判读:

1. `None` owner 在 `raw_instance_id is None` 处分支拒绝，返回 `unowned_port_spec_not_certified_for_d2_cut`。
2. 空字符串或纯空白 owner 经 `str(...).strip()` 失败后拒绝，返回同一 unowned reason。
3. `ghost_pick` 不进入 `placement_owner_ids`，因此 port owner 指向 `ghost_pick` 时被当作 `not_in_placement` 拒绝。
4. 任意不在当前 placement 的 synthetic owner，例如历史上的 `"None"`、`"missing"`，都被 `port_spec_owner_not_in_placement_not_certified_for_d2_cut` 拒绝。
5. 没发现第二条绕开 `_d2_port_owner_validation_error()` 构造 D2 conflict 的路径。D2 的唯一 master-cut 出口在 `src/search/d2_separator.py:353-368`，即先构造 support-augmented conflict，再调用 `master_delegate.add_benders_cut()`。

我额外跑了一个小 probe，覆盖 `None / blank / ghost_pick / missing` 四类 owner，全部在 master delegate 被调用前返回 ERROR，未写 cut。

### 2.2 r9 precheck gate + r10 owner gate 叠加后的 D2 全链路

结论: D2 链路 sound。

链路实际形态:

1. `benders_loop` 只在 production precheck 已经给出 `front_blocked` 的主分支里尝试 D2: `src/search/benders_loop.py:5384-5443`。
2. D2 separator 内部并不信任外层状态，会重新按同一个 occupied grid + terminal context 调 `run_exact_routing_precheck()`: `src/search/d2_separator.py:203-223` 与 `src/search/d2_separator.py:261-276`。
3. D2 只接受 `front_blocked` / `relaxed_disconnected` 两种 production precheck 证明态；其它状态，包括 `feasible`、`unknown`、异常，都不会建 cut: `src/search/d2_separator.py:278-293`。
4. D2 模型若非 `INFEASIBLE`，或者 `INFEASIBLE` 但抽不到 raw core，也不写 cut: `src/search/d2_separator.py:319-340`。
5. D2 的 raw terminal core 不直接上 master。最终 conflict 由所有 terminal owners、所有 occupancy support owners、raw core 三者取并集构成: `src/search/d2_separator.py:126-152` 与 `src/search/d2_separator.py:353-365`。
6. master delegate 侧再次做 fail-closed literal resolution: `src/models/pose_bool_exact_master.py:931-960`。

这条链同时覆盖了 r9 的“D2 不是 production routing relaxation，不能独立当 proof source”问题，以及 r10 的“synthetic owner 不得进入 conflict”问题。当前实现没有把 D2 的诊断性 INFEASIBLE 升格为 proof cut。

## 3. Q2: 本轮深挖通道

我选了三个更薄的角落深挖: lazy connectivity cut、deletion-core、跨通道 ladder 弱序。理由是 D2 / PCR 已连续多轮作为主战场，而 lazy connectivity 多轮被提到却不是主角；deletion-core 与 ladder 则最容易出现“弱 oracle 被调用方误当强证明”或“失败后误升级”的问题。

### 3.1 lazy connectivity cut

结论: sound。

关键代码:

- terminal route-state 建图: `src/models/routing_subproblem.py:1244-1330`
- selected source-side closure: `src/models/routing_subproblem.py:1378-1406`
- crossing boundary 生成: `src/models/routing_subproblem.py:1408-1433`
- source-side cut 自检: `src/models/routing_subproblem.py:1435-1533`
- cut 写入 / fallback: `src/models/routing_subproblem.py:1535-1589`
- selected route exact nogood fallback: `src/models/routing_subproblem.py:1689-1699`
- solve loop 中只有 connectivity guard 接受后才返回 FEASIBLE: `src/models/routing_subproblem.py:1728-1842`
- route 提取也要求 `_connectivity_guard_accepted`: `src/models/routing_subproblem.py:1844-1849`

攻击过程:

我重点看它有没有把“当前解断开”直接翻译成“必须选某个边界状态”的 cut。若这样做，很容易 over-cut，因为当前断开不等于所有可行解都要穿同一个边界。

实际实现多了一层硬自检:

1. 先在当前 selected route states 上算 source-side closure `W`。
2. 用全 potential route-state graph 算 crossing set `X`。
3. 自检要求 `X` 完全属于 potential graph；所有 source front 都在 `W`；没有 sink front 已经落进 `W`。
4. 把 `X` 从全 potential graph 里移除，再检查 source 是否仍能到任何 sink。若还能到 sink，则 `X` 不是完整割面，直接 fallback，不写 `sum(X) >= 1`。
5. 若当前 incumbent 已经选了 crossing state，也 fallback，避免 cut 不排除当前坏解或语义不清。
6. 只有自检通过时，才写 `sum(crossing_vars) >= 1`；自检失败时只写当前 route-state 精确 nogood。

证明口径很直接: 自检已经在“全潜在状态图”里证明 `X` 是 source 到 sink 的必要割面，所以任何合法连通 route 都至少要选一个 `X` 中状态；当前坏 incumbent 又被确认没有选 `X`。因此 cut 排除的是当前断路候选，不排除任何真实连通候选。若证明不了完整割面，就回退到 exact selected-route nogood，不升级。

专项回归中相关 lazy connectivity 测试通过:

- `test_routing_lazy_connectivity_cuts_converge_on_three_commodity_probe`
- `test_routing_lazy_connectivity_cut_preserves_real_feasible_path`
- `test_routing_lazy_connectivity_cut_self_check_falls_back_to_nogood`

### 3.2 deletion-core 算法本体

结论: sound，且调用方没有消费 “minimum core” 语义。

关键代码:

- visible terminal filter: `src/search/routing_deletion_core_minimizer.py:41-68`
- cheap oracle: `src/search/routing_deletion_core_minimizer.py:82-144`
- deletion-minimal loop: `src/search/routing_deletion_core_minimizer.py:161-247`
- caller 收集 blocker ids / visible keys / 写 master cut: `src/search/benders_loop.py:5540-5575`
- binding alternative safe-reject 优先于 master cut: `src/search/benders_loop.py:5328-5382`

攻击过程:

我按三个方向打它:

1. oracle 是否比 production precheck 弱到会制造过切？
2. `pose_idx_by_id` 的来源是否可能包含超出证明支撑集的成员，并被调用方当作最小证明？
3. binding alternatives 没穷尽时，会不会把“当前 binding 选择不可行”误切成“当前 placement 不可行”？

结果:

- oracle 只证明一种很窄的事实: 某个 routing-visible terminal front 出界，或被另一个 selected footprint 占住。它不尝试证明所有 routing 不可行形态，弱点只会让 cut 变少或变大，不会让假证明变强。
- `build_routing_visible_port_keys_by_instance()` 只从当前 `port_specs` 建 visible key，避免从 raw pose geometry 复活 routing-free / wireless output。已有回归 `test_deletion_core_oracle_consumes_filtered_routing_visible_ports` 覆盖这点。
- deletion loop 只在 `still_blocked=True` 时删除 instance，所以正常返回的 final `S` 仍满足 cheap oracle 的 front-blocked 事实；遇到 budget cap 时同样保持这个不变量。
- `abort_reason="fallback_no_deletion"` 分支会返回 full layout，但这只发生在 cheap oracle 对 full layout 都无法复现 front-blocked 时。主循环里如果 binding alternatives 还存在，会在 `src/search/benders_loop.py:5328-5382` 先走 binding nogood，不进入 master cut；没有 alternatives 时，full-layout nogood 是安全的弱 cut。
- 调用方只把 `pose_idx_by_id` 当作普通 conflict tuple 给 `add_benders_cut()`，没有假设它是 cardinality-minimum。注释里的 “minimal” 实际上只是 deletion-minimal；即使不是 minimum，也不影响 soundness。
- `ghost_pick` / 不可解析 optional / alias 等脏成员若进入 conflict，delegate 会拒绝，不会静默降级为更强 cut。这是 under-cut / cut_stall，不是 over-cut。

### 3.3 跨通道 ladder 弱序

结论: 未发现“失败后向更强 cut 升级”的通道泄漏。

关键代码:

- D2 尝试与失败 fall-through: `src/search/benders_loop.py:5418-5447`
- PCR 尝试与失败 fall-through: `src/search/benders_loop.py:5449-5520`
- D2/PCR 成功后禁用 deletion-core: `src/search/benders_loop.py:5532-5539`
- deletion-core 成功后跳过 lazy/cell/fallback per-port loop: `src/search/benders_loop.py:5576-5581`
- lazy demand / cell cut / fallback instance nogood 的递减路径: `src/search/benders_loop.py:5576-5681`
- 无 cut 时返回 UNKNOWN，不继续认证: `src/search/benders_loop.py:5683-5704`
- relaxed_disconnected 只枚举 binding alternatives 或 break 到更弱 whole-layout 路径: `src/search/benders_loop.py:5706-5744`
- whole-layout 在 power witness 不完整时 fail-closed 跳过: `src/search/benders_loop.py:6178-6226`

判读:

- D2 / PCR 都是 env-gated，异常只打印并 fall through，不会写半成品 cut。
- D2 / PCR 写成后设置 skip flag，阻止同一个 incumbent 再叠加更弱但语义不同的 deletion / lazy / cell cut。
- deletion-core 写成后跳过 per-port loop；写不成则不把 core 失败解释为其它更强证明。
- lazy demand 与 cell-pattern 是 front-blocked 分支中的 reactive cut；若不能解析 target 或候选为空，最后要么走更普通的 placement local nogood，要么 `cut_added=False` 返回 UNKNOWN。
- relaxed_disconnected 没被直接升级成细粒度 master cut。binding 有 alternatives 时只切当前 binding selection；binding 穷尽后才走 whole-layout routing exhausted 口径。

这条 ladder 的结构是“强 separator 成功即停；失败只回落或 UNKNOWN”，没有看到“上游不确定但下游当成更强证明”的路径。

## 4. 其它通道抽查

### 4.1 PCR-CUT patch separator

结论: soundness gate 仍完整。

关键代码:

- patch solver 模型本体声明为 boundary relaxation，patch INFEASIBLE 才能推出 full-grid INFEASIBLE: `src/models/patch_routing_core.py:1-12`
- replay validation 要求 candidate core 单独复现 INFEASIBLE；非 assumption literal、FEASIBLE、UNKNOWN 都 invalid: `src/models/patch_routing_core.py:807-851`
- QuickXplain cap 命中时返回保守候选，caller 仍二次 replay: `src/models/patch_routing_core.py:863-920`
- raw/minimized lifecycle: `src/models/patch_routing_core.py:923-996`
- separator 只在 lifecycle accepted 后才 augment support 并调 master: `src/search/patch_conflict_separator.py:466-499`
- master signature lifting 任一 core term 解析失败、pose 越界、无等价 var、lift alias overlap 都拒绝加 cut: `src/models/pose_bool_exact_master.py:762-829`

PCR 的风险点依旧是“patch 只看局部，常量占用与边界邻域必须进 support”。当前实现用 `_patch_support_signature_cells()` 包含 patch cells + one-cell cardinal ring，并把这些 owner 加入 assumptions/support: `src/search/patch_conflict_separator.py:121-162` 与 `src/search/patch_conflict_separator.py:332-354`。这会让 cut 变弱，不会变强。

### 4.2 cell-pattern / lazy-demand 剩余角

结论: 当前未形成 soundness finding。

- lazy-demand 只按 routing-visible profile demand 加 “至少 demand 个 front 必须清空” 的反向约束；off-grid front 计入 const_blocked，若需求已不可能满足则禁用该 pose: `src/models/pose_bool_exact_master.py:1107-1171`。这是从 port demand 出发的必要条件。
- cell-pattern cut 仍是 `sum(port_candidates)+sum(blocker_candidates)<=1`: `src/models/pose_bool_exact_master.py:1189-1227`。我注意到它没有显式 duplicate-literal guard；若未来 canonical 允许某 pose 同时“在 port_cell 有 routing-visible port 朝 direction”且“自身占据 front_cell”，重复 literal 会把该 pose 禁掉，形成潜在过切。但在当前口径下，port front 是 routing free terminal cell，相关旧回归已经覆盖 virtual generic input、inactive slot、unused generic output、unknown capacity 等过切风险。本轮没有找到当前 artifact 内可触发的 duplicate/self-front 实证，所以不作为 finding 上报。建议以后若 canonical 规则改动，给这个函数加 alias/dedup 防尘测试。

### 4.3 persisted / conditioned cuts

结论: 未发现 condition 丢失导致无条件 replay 的问题。

- condition_set malformed 会被 blocker 拦住: `src/search/benders_loop.py:1469-1484`
- persisted condition replay 必须解析回 ghost anchor literal；未知 key、非 int、anchor 不匹配都 skip，不会退化成 unconditional: `src/search/benders_loop.py:1489-1534` 与 `src/search/benders_loop.py:6593-6608`
- power-conditioned cut 生成时携带 `condition_lits=(u_var,)`: `src/search/benders_loop.py:4818-4855`

## 5. 实证记录

### 5.1 通过的专项测试

```bash
python -m pytest -q -p no:randomly \
  src/tests/test_d2_separator_support_context.py \
  src/tests/test_wireless_front_consumers_r4.py \
  src/tests/test_exact_contract.py::test_routing_front_blocked_unencodable_optional_conflict_fails_closed \
  src/tests/test_exact_contract.py::test_relaxed_disconnected_only_rejects_binding_selection_without_persisted_cut \
  src/tests/test_p0_certified_soundness_fixes.py::test_front_blocked_safe_reject_enumerates_binding_before_master_cut \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cuts_converge_on_three_commodity_probe \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_preserves_real_feasible_path \
  src/tests/test_p0_certified_soundness_fixes.py::test_routing_lazy_connectivity_cut_self_check_falls_back_to_nogood
```

结果: `24 passed in 1.51s`

```bash
python -m pytest -q -p no:randomly src/tests/test_patch_routing_core.py src/tests/cuts/test_family_cutset.py
```

结果: `41 passed in 3.83s`

### 5.2 proof obligation 脚本

```bash
python scripts/check_p1_2_proof_obligations.py
```

结果: `P1.2 proof obligation check passed: 8 obligations anchored`

### 5.3 D2 owner validation probe

额外手写 probe 覆盖 `None / blank / ghost_pick / missing` owner，全部在 D2 build 与 master delegate 前 fail-closed。

结果: `D2 owner validation probe passed: None/blank/ghost/missing fail before master cut`

### 5.4 全量测试状态

尝试运行:

```bash
python -m pytest -q -p no:randomly src/tests
```

该命令在沙盒中超时终止；终止前进度约 16%，未看到失败输出。因此本报告不声称全量 3033 测试已完成，只声明上述 cuts 相关专项与 proof obligation 已通过。

## 6. 最终判断

本轮零 soundness finding。

CUT-R10-L1 owner gate 修复确认通过；r9 precheck gate 与 r10 owner gate 叠加后，D2 通道没有发现可绕过的 conflict 构造路径。lazy connectivity、deletion-core、PCR-CUT、cell/lazy-demand、conditioned/whole-layout、以及跨通道 ladder 的当前实现都保持 fail-closed 或只写被证明支撑的 cut。

独立判断: cuts 面达到饱和下沿，可以按“连零 2”视作本面终饱和通过。
