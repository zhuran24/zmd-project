# IndustrialPlanner cuts face round 8 review

快照校验通过: `/mnt/data/zmd_snapshot_37b84be0.zip` 的 sha256 为 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`，与任务指定值一致。本轮只审该快照。

结论: 本轮不是零 soundness finding。发现 1 个 soundness finding，位于 env-gated 的 `EXACT_B1_D2_COMMODITY_FLOW` front_blocked 旁路。用户指定的五种 front_blocked cut 产物、binding-local nogood、whole-layout routing-exhausted nogood，以及 `BendersCut`/condition 本体链路未发现新的 over-cut。

补丁已在工作树中应用，补丁文件为 `/mnt/data/zmd_audit_r8_d2_support_context.patch`。新增回归 `src/tests/test_d2_separator_support_context.py`。

## Finding CUT-R8-H1: D2 commodity-flow cut 丢失 occupancy / non-core terminal proof context

Severity: High for the gated path `EXACT_B1_D2_COMMODITY_FLOW=1` together with pose-bool/cell-cut mode. 公开 certified 默认仍被相关 gate 拦住，但一旦该 D2 rung 开启，它在 front_blocked ladder 中优先于 PCR/deletion/lazy/cell/fallback 成功返回，因此会直接影响 master pruning。

位置:

- `src/search/benders_loop.py:5403-5440`: D2 separator 作为 front_blocked rung，成功后 `_b1_d2_skip_other_cuts=True`，跳过后续 cut channels。
- 原快照 `src/search/d2_separator.py:47-60`: D2 occupied grid 从当前 `placement_solution` 的所有 footprint 常量构造。
- 原快照 `src/search/d2_separator.py:126-139`: D2 model 以当前 `occupied` 和当前 `port_specs` 构造。
- 原快照 `src/search/d2_separator.py:174-185`: master cut 只用 `raw_core` 中的 terminal owner pose，形式为 `{pa.instance_id: pa.pose_idx for pa in raw_core}`。
- `src/models/d2_commodity_flow_core.py:104-110`: `_free_cells = grid - occupied_cells` 是常量，不受 assumption literal 保护。
- `src/models/d2_commodity_flow_core.py:140-193`: terminal obligations 才受 per-owner assumptions 保护，且非 core terminal literals 仍处于当前模型上下文。
- `src/models/d2_commodity_flow_core.py:243-280`: CP-SAT 只返回 assumption sufficient core，不会返回 occupancy 常量或非 assumption context。

问题:

D2 的 UNSAT core 只覆盖 assumption literals。可是 D2 model 中，当前所有 facility footprints 已被编译成 constant occupied cells，非 core terminal owners 也以当前 port position 参与约束。原实现把“在当前障碍/当前其它 terminal helper 下，core terminal 子集不可行”的证明，升级成“只要这些 raw core poses 还在，任意其它 layout 都不可行”。这禁止的解集合大于 D2 实际证明义务，是 over-cut。

最小复现实证:

新增回归构造一个嵌入 70x70 的单行走廊。source 在 `(0,0)` 朝 E，sink 在 `(69,0)` 朝 W。wall pose 把除走廊外所有 cell 占住；当 wall 额外占用 `(35,0)` 时 D2 infeasible，solver core 只返回 `src`。把 wall 移走后，source/sink poses 不变，D2 feasible。因此 `{src: 0}` 不是 sound master cut。

Probe 结果由新增测试固定:

```text
blocked layout: D2 INFEASIBLE, raw core [('src', 0)]
moved-wall layout: D2 FEASIBLE with same source/sink poses
patched separator conflict: {'src': 0, 'sink': 0, 'wall': 0}
```

修法:

把 D2 cut 从 raw terminal core 扩展为 support-augmented proof-context nogood。补丁新增:

- `_build_occupancy_support_pose_terms(...)`: 收集所有被 D2 编译进 `occupied_cells` 的 selected owner pose，跳过 `ghost_pick`。
- `_build_d2_supported_conflict_set(...)`: 将所有当前 port owners、所有 occupancy contributors、以及 solver raw core 合并为 master conflict set。
- cut metadata 增加 `support_conflict_size` 和 `support_owners`，便于后续 telemetry 对照。
- 新增 `src/tests/test_d2_separator_support_context.py` 两个回归: 一个验证 separator cut 包含 source/sink/wall support，一个证明 raw terminal core alone 在该 toy case 下不 sound。

修复后 cut 更弱，但满足 `cut semantic ≤ proof obligation`: master 只禁止“同一 terminal/occupancy support tuple 再次同时出现”的 layout，不再跨障碍上下文泛化。

## Q1: 跨通道 cut 语义族谱

下表按 current code 的实际约束形态列出语义、证明义务、scope 与本轮结论。D2 是本轮自由攻击角发现的额外 front_blocked rung，不属于任务列出的五种产物，但它在现行 ladder 中位于 PCR 前，因此一并纳入弱序审计。

| cut channel | 实际禁止的解集合 | 证明义务来源 | scope / condition | 语义 ≤ 证明义务结论 |
| --- | --- | --- | --- | --- |
| D2 commodity-flow core, patched | `sum(x_i,p_i for all current port owners plus occupancy support owners plus raw core) ≤ K-1`。禁止同一 terminal/occupancy proof-context tuple 再出现。 | `D2CommodityFlowCore` 的 relaxation INFEASIBLE，assumption core 只证明 terminal subset；补丁把 grid occupancy constants 与当前 terminal helper context 纳入 support。 | env-gated，front_blocked rung，master-level unconditioned，但 conflict 已包含当前 proof context。 | 原快照不满足，见 CUT-R8-H1。补丁后满足。 |
| PCR patch-core nogood | 对每个 core owner，枚举同 owner 在 `support_signature_cells` 上 patch-local signature 相同的 poses，约束 `sum_i sum(eq_vars_i) ≤ K-1`。它禁止的不只是当前 tuple，而是一组 patch-equivalent tuple。 | patch CP-SAT INFEASIBLE，`extract_and_validate_patch_core` raw/minimized replay；`_augment_core_with_patch_support` 加入 patch 内及 cardinal ring 的 constant-occupancy support；master delegate 对每项做 signature lifting，并拒绝 unresolved 或 overlapping lifted terms。 | env-gated，per patch / current master，unconditioned。`support_signature_cells` 由 patch cells 加一圈 cardinal ring 得到。 | 满足。它的泛化维度正是 replay + support signature 覆盖的维度，失败时不加 cut。 |
| deletion-core cut | `delegate.add_benders_cut(core_result.pose_idx_by_id)`，即删除最小化后的 instance-pose conjunction no-good。 | `minimize_routing_front_blocked_core` 的 cheap oracle 在同一 routing-visible port set 上反复验证 front-blocked；caller 用 `routing_precheck_summary.blocked_ports` 提供 blocker seed。 | env-gated，master-level，当前 front_blocked branch。若 binding selection 是 safe-reject 且仍有 alternatives，caller 先加 binding-local nogood 并重新枚举，不直接 master cut。 | 满足当前 contract。oracle 只证明 front-blocked，不证明完整 routing infeasible；实际 cut 也只用于 front_blocked rejection。失败或无 core 时不 fallback 成更强 cut。 |
| lazy-demand count cut | 对某个 selected pose 的每一侧约束 `pose_var => sum(front blockers) ≤ K - demand - const_blocked`；若 slack < 0 则禁该 pose。 | binding/profile 的 routing-visible demand: 至少 demand 个 physical front cells 必须可用。blocker terms 由全局 pose occupancy cache 枚举。 | env-gated，per selected pose，OnlyEnforceIf 当前 pose var。 | 满足。它禁止的是“该 pose 被选中且可见端口需求不可能满足”的集合，和证明需求一致；无法构造时不加 cut。 |
| cell-pattern cut | `sum(port_candidates at port_cell+dir) + sum(blocker_candidates occupying front_cell) ≤ 1`。 | routing precheck 发现 concrete visible port 的 front_cell 被占；delegate 只枚举 routing-visible exact port candidate 与 occupancy candidate。 | env-gated，cell-level pattern，unconditioned。 | 满足。实际候选集按 concrete port cell/dir 与 front occupancy 泛化；本轮数据 probe 覆盖 66,403 poses / 599,382 ports，`self_front=0` 且 `outgrid_front=0`，未发现 duplicate self literal seam。 |
| fallback selected nogood | `_add_exact_persisted_nogood` 对 `blocked_port.placement_level_conflict_set` 生成 selected instance-pose tuple no-good。 | routing precheck 的 front_blocked witness，含 port owner 与 blocker conflict set；BendersCut 构造后 roundtrip 验证，再由 master presence nogood apply。 | 默认 fallback，master-level，unconditioned；persisted exact cuts 当前不 replay，作为 telemetry / in-process generated record。 | 满足。它是同一 witness 的 selected tuple 禁止，弱于 cell-pattern/lazy/deletion/PCR 泛化。 |
| binding-local nogood | `PortBindingModel.add_nogood_cut(selection)` 在 binding 子模型内加 `sum(current binding literals) ≤ n-1`。不碰 master pose vars。 | 当前 binding selection 被 routing precheck safe-reject、relaxed disconnected 或 routing infeasible 排除；还有 binding alternatives 时用于枚举下一组 binding。 | binding-local，per master layout / per binding model。 | 满足。它不跨 master layout 剪枝，不存在 candidate A proof 在 candidate B 生效的问题。 |
| whole-layout routing_exhausted_nogood | `_add_exact_whole_layout_nogood` 对当前 selected layout 的所有 non-ghost owner poses 加 conjunction no-good。 | binding alternatives exhausted 且 routing attempts 全不可行；若 power witness 不完整会 skip 并 UNKNOWN。 | whole-layout master cut，`ghost_pick` 排除；返回 `MASTER_CUT_ADDED_CONTINUE`，不升级为 candidate-wide infeasible。 | 满足。禁止范围是当前完整 layout tuple，不超出“该 layout 全绑定/路由已耗尽”的证明。 |

弱序关系审计结果:

PCR 成功后跳过 deletion/lazy/cell/fallback；deletion env 打开时若不成功会停在 UNKNOWN 或 cut_stall，不会向更强但证明更少的 cut 升级；lazy env 打开时若 per-pose cut 构造失败也不自动回退为 fallback；cell-pattern env 下 `add_routing_port_blocking_cell_cut` 返回 false 时不加 selected fallback。这些都是 fail-closed 或换更弱/同等证明通道。原快照中唯一违反弱序直觉的是 D2: 它在 PCR 前成功后跳过其它 channels，但 raw core cut 比其 proof 更强。CUT-R8-H1 的 patch 将 D2 成功 cut 降回 proof-covered support tuple。

## Q2: BendersCut / condition 本体链路

字段保真链结论: 未发现 condition 丢失导致无条件 over-cut。

| 链路点 | 代码位置 | 审计结论 |
| --- | --- | --- |
| 数据对象字段 | `src/models/cut_manager.py:212-232` | `BendersCut` 持有 `cut_type/conflict_set/iteration/metadata/schema_version/source_mode/exact_safe/artifact_hashes/proof_stage/binding_exhausted/routing_exhausted/proof_summary/created_at/epsilon_stage/condition_set`。实际 schema 没有单独 top-level `scope` 字段，scope 由 `cut_type/proof_stage/metadata.kind/condition_set/*_exhausted` 表示。 |
| serialization | `src/models/cut_manager.py:234-268` | `to_dict()` 保留 `condition_set`；certified_exact 下 conflict 和 condition 都走 strict int mapping，非 mapping 或 bool/int 混淆会抛错。 |
| deserialization | `src/models/cut_manager.py:271-312` | `from_dict()` 读取 `condition_set` 并回填 dataclass；不会默认丢为 `{}` 后继续通过 condition-required cut。 |
| certified condition requirement | `src/models/cut_manager.py:94-209` | 对需要 ghost condition 的 certified cut，空 condition 会 raise；condition key 必须为 canonical `ghost_anchor::(x,y)`，并与 metadata 中的 `ghost_rect_idx/ghost_anchor` 匹配。 |
| dedup key | `src/models/cut_manager.py:387-389`, `:419-428`, `:515-529` | structured signature 是 `(conflict_signature, condition_signature)`，同 conflict 但不同 condition 不会互相吞掉。`active_cuts` legacy projection 不含 condition，但本 certified replay 路径不靠它 apply structured cuts。 |
| in-process construction | `src/search/benders_loop.py:6127-6173` | `_add_exact_persisted_nogood()` 将 `condition_set` 写入 `BendersCut`，立即 `to_dict/from_dict` roundtrip，再调用 `master.add_benders_cut(..., condition_lits=...)`。roundtrip 失败或 master apply 失败都返回 false，不会无条件加。 |
| condition literal resolver | `src/search/benders_loop.py:1488-1533` | `_resolve_condition_lits_from_condition_set()` 解析失败、unknown key、非 int rect_idx、ghost domain mismatch、u_var missing 都返回 `([], False)`；caller 必须 skip cut，不会退化成 unconditional。 |
| master apply | `src/models/pose_bool_exact_master.py:918-967`, `src/models/exact_coordinate_master.py:6903-6955`, `src/models/master_model.py:11904-11948` | 三条 apply 路径都只在 conflict members 全量解析成功时添加 presence no-good；`condition_lits` 非空时用 `OnlyEnforceIf`。解析失败返回 false，不加约束。 |
| current replay lifecycle | `src/search/benders_loop.py:6560-6577` | certified mode 下 persisted `exact_safe_cuts` 当前强制 `raw_candidate_cuts=[]`，即 persisted cuts 是 telemetry/performance hints，不作为 proof replay。 |
| power conditioned generation | `src/search/benders_loop.py:4802-4852` | power infeasible cut 生成时强制读取 selected ghost anchor，构造 `condition_set={ghost_anchor::(x,y): rect_idx}` 并传入对应 `u_var` 作为 `condition_lits`；取不到 anchor 时 ABORT，不加全局 cut。 |

kind/scope 消费结论: master apply 层只消费 presence no-good shape 与 condition literals，不按 `metadata.kind` 做语义分派。soundness 由生成点和 certified filters 负责。由于当前 certified persisted replay fail-closed，外部 artifact 的未知 kind 不能直接进入 master apply；in-process 生成点是 hardcoded callsite，未发现 kind/scope 丢失导致 over-cut 的路径。

## Q3: 自由攻击角

我选择了两个缝隙深挖。

第一，D2 commodity-flow separator。选择理由是它是现行 front_blocked ladder 中位于 PCR 前的跨通道 rung，但不在任务列出的五个已饱和 cut 产物里，且结构上与 PCR 一样有“solver core 只返回 assumptions，但模型还含 constant context”的典型支撑丢失风险。攻击结果为 CUT-R8-H1，已给补丁和 regression。

第二，cell-pattern 泛化里的 self-front / duplicate literal seam。攻击点是 `sum(port_candidates)+sum(blocker_candidates)≤1` 如果同一 pose 同时作为 port candidate 与 blocker candidate 出现，会把二元 pattern cut 退化成对单 pose 的更强 ban。代码层面 `add_benders_cut` 对 duplicate alias 会 fail-closed，但 cell-pattern 没有同样的 duplicate-name guard。本轮用当前 `candidate_placements.json` 做实证 probe: 7 templates，66,403 poses，599,382 ports，`self_front=0`，`outgrid_front=0`，未发现当前工件中存在这一 seam。结论: 当前快照无 soundness finding；建议后续如 placement generator 支持自朝内/边界 port，再给 cell-pattern delegate 加 duplicate literal guard 作为防尘罩。

## 自验结果

执行环境: Python 3.13 venv，离线 wheels 来自 `zmd_py313_linux_x86_64.zip`。

已执行:

```text
PYTHONPATH=. pytest -q -p no:randomly src/tests/test_d2_separator_support_context.py
2 passed in 2.34s

PYTHONPATH=. pytest -q -p no:randomly \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py \
  src/tests/test_v82_persisted_cut_replay_fail_closed.py \
  src/tests/test_patch_routing_core.py \
  src/tests/test_d2_separator_support_context.py
37 passed in 9.68s

PYTHONPATH=. pytest -q -p no:randomly src/tests/cuts
463 passed in 16.88s

PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored
```

未执行全量 `python -m pytest -q src/tests`。本轮执行了 cuts 机制相关专项、BendersCut/condition lifecycle 专项、PCR 专项、D2 新回归，以及 P1.2 proof obligation check。
