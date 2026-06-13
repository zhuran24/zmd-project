# 终末地 IndustrialPlanner binding 面 round 8 REVIEW

审查对象：`zmd_snapshot_f4418b04.zip`，sha256 已先验校验为 `f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1`，与任务给定值一致。只解包并审查该快照。解包后再生 `data/preprocessed/candidate_placements.json`，sha256 为 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，大小 `45,773,799` bytes，与任务基线一致。

结论：本轮发现 1 个 binding soundness finding，已给出补丁与回归。其余 Q1-Q5/Q7 未发现新的 false-FEASIBLE 或 false-INFEASIBLE soundness 缺口。

## Finding: F-BIND-R8-01, conditional HIGH

**标题**：`EXACT_BINDING_USE_OVERLOAD_SEPARATION` env-on 后，binding re-solve 的 INFEASIBLE 没有统一走 env-off fallback，可能把 heuristic hard nogood 的局部耗尽误铸为 binding/routing exhaustion。

**影响**：false-INFEASIBLE，条件性。默认 certified 主路径不设置 `EXACT_BINDING_USE_OVERLOAD_SEPARATION`，`PortBindingModel.build()` 只有在 env 值为 `1/true/yes/on` 时才注入 overload hard nogood，默认不受影响（`src/models/binding_subproblem.py:471-480`）。但该 env 一旦被 wrapper 或实验入口误开，并且 `_add_storage_box_overload_nogoods()` 实际加入了 hard clauses，后续枚举 binding alternatives 时的 `INFEASIBLE` 不能直接作为真实 binding exhaustion 证据。

**原始快照位置**：

- `src/models/binding_subproblem.py:499-554` 的 `_add_storage_box_overload_nogoods()` 明确加入 hard `AddBoolOr([h.Not(), low_lit.Not()])`，注释也写明这会砍合法解，caller 必须在 INFEASIBLE 时关闭 env fallback。
- `src/search/benders_loop.py:5153-5214` 只在 initial binding solve 的 `INFEASIBLE` 路径做了 env-off fallback。
- `src/search/benders_loop.py:5406-5448`、`:5784-5810`、`:5973-6007` 三个 binding re-solve 点在 `add_nogood_cut(selection)` 之后遇到 `INFEASIBLE` 直接 `break`，随后进入 `routing_exhausted_nogood` whole-layout nogood 链。
- `src/search/benders_loop.py:6055-6101` 的 fallback helper 只重建 env-off model，没有接收并回放已经被 routing/precheck 拒绝过的 binding selections，也没有保留 RAB routing context。即使某 re-solve 点调用它，也会把搜索倒回到旧 selection，不能证明“剩余 alternatives”穷尽。

**复现 probe**：我用两个 `wireless_sink` 协议箱、每箱 3 个虚拟 input slots、需求 `qiaoyu_capsule=1` 与 `valley_battery=1` 构造最小 CP-SAT binding。probe monkeypatch 两个有效 canonical generic-input 终品的 overload 分类，使 `qiaoyu_capsule` 为 high、`valley_battery` 为 low。env-on 时 overload separation 禁止二者落在同一个协议箱；枚举并 nogood 掉所有分箱 assignment 后，env-on binding 返回 `INFEASIBLE`。但把相同的 18 个 rejected selections 回放到 env-off model 后，仍有合法 co-location binding。

Probe 输出：

```text
env_on_nogoods_added=18
env_on_after_rejecting=18 status=INFEASIBLE
env_off_replay_status=FEASIBLE
env_off_replay_selection={'protocol_box_001:in:0': '__unused__', 'protocol_box_001:in:1': '__unused__', 'protocol_box_001:in:2': '__unused__', 'protocol_box_002:in:0': '__unused__', 'protocol_box_002:in:1': 'qiaoyu_capsule', 'protocol_box_002:in:2': 'valley_battery'}
```

这证明 re-solve 后的 env-on `INFEASIBLE` 可能只是 overload heuristic 把“同箱绑定”砍掉了，而不是 binding alternatives 真穷尽。若该状态直接进入 whole-layout nogood，就是 false-INFEASIBLE。

**修复**：补丁做了四件事。

1. 新增 `_binding_used_overload_separation()`，只在 `overload_separation_enabled is True` 且 `overload_nogoods_added > 0` 时触发 fallback。
2. initial solve fallback 继续保留，并传入 `_rab_sep_routing_context`，确保除了 overload env 之外不改变 binding domain 语境。
3. 在 while 枚举中记录 `binding_rejected_selections`，每次 `add_nogood_cut(selection)` 前保存当前 selection。
4. 三个 re-solve 点的 `INFEASIBLE` 都先调用 env-off fallback；fallback 重建模型后回放所有 rejected selections 再 solve。`FEASIBLE` 则继续枚举，`TIMEOUT` fail-closed 为 `UNKNOWN`，只有 env-off replay 仍 `INFEASIBLE` 才允许进入 exhaustion 链。

当前补丁位置：`src/search/benders_loop.py:5269-5284`、`:5420-5504`、`:5839-5903`、`:6063-6134`、`:6182-6234`。回归测试：`src/tests/test_binding.py::test_lbbd_retry_helper_replays_rejected_selections_after_overload_exhaustion`。

## Q1-Q2：实例覆盖完备性与空 binding 域来源

`port_binding.supports_exact_pose_level_binding()` 的规则是 `generic_input_slots == 0 and generic_output_slots == 0`（`src/models/port_binding.py:31-33`），所以制造 recipe 和 `power_supply` 等 exact profile 走 fixed-op 绑定。`_build_fixed_operation_domains()` 对 exact profile 枚举 pose-level domain，并只在非 exact profile 上跳过（`src/models/binding_subproblem.py:647-708`）。generic-output 只接 `boundary_io` / `protocol_core`（`:709-748`），generic-input 只接 `wireless_sink`（`:757-794`）。

实证覆盖 probe 结果：

```text
mandatory_coverage_counts={'fixed_op': 219, 'generic_output': 47}
mandatory_bad_count=0
all_coverage_counts={'fixed_op': 269, 'generic_input': 10, 'generic_output': 47}
all_bad_count=0
full_build_binding_domains=269 fixed_choices=50 binding_vars=219
full_build_empty_domains=0
full_build_generic_output_slots=52 generic_input_slots=30
full_build_domain_size_counts={1: 50, 3: 11, 9: 121, 25: 32, 50: 17, 360: 35, 540: 3}
```

这覆盖了 266 mandatory 与合成/optional 全 326 实例。219 个 mandatory recipe 都落在 fixed-op 路径；47 个 mandatory boundary/core 落在 generic-output 路径；10 个 wireless sink 落在 generic-input 路径；50 个 `power_supply` optional 是 exact profile 且 0 输入/0 输出，domain size 为 1，不会形成漏证实例。

空域方面，`_rate_to_slots()` 使用 `ceil(rate / capacity - 1e-9)`（`src/preprocess/operation_profiles.py:48-55`），`_enumerate_side_binding_patterns()` 在 `total_slots > ordered_cell_count` 时直接 raise `ValueError`（`src/models/port_binding.py:150-153`），不是返回空 domain；当 `routing_context=None` 的 certified 主路径不启用 RAB filter 时，side enumeration 在 `total_slots <= cell_count` 下总能给出组合。probe 对所有 exact profiles 检查 `sum(profile.input_slots/output_slots)` 与 candidate pool 最小物理端口数，得到：

```text
exact_profile_slot_deficits=[]
```

因此本快照中没有由 rate→slot 取整导致的端口不足，也没有 env-off 纯 binding 的空域。`empty_binding_domain_instances` 在全 326 placement 构造中为 0。若未来真的出现 `total_slots > cell_count`，当前路径会 fail-fast 抛异常，而不是被 `_build_fixed_operation_domains()` 伪装为可铸 whole-layout nogood 的空域证据。

## Q3-Q4：端口 cell 容量与 routing-free 终品排除

端口容量没有额外的“同 cell 多商品叠加”漏洞。`_enumerate_side_binding_patterns()` 按 commodity 的 required slot 数从 `remaining_indices` 选组合，并在选中后 remove index（`src/models/port_binding.py:143-179`），所以同一 side cell 在一个 binding pattern 中最多出现一次。`_materialize_side_binding()` 把每个被选中的 cell 映射为一个 `(cell, commodity)`（`:182-197`）。固定 profile 的容量语义是每个物理端口承载一个 belt，slot 数由 `ceil(rate / belt_capacity_per_tick)` 给出；规则文本也把 port/belt 容量定为 0.5/s，即本模型 tick 下 1 per tick（`specs/03_rule_canonicalization.md:273-282`）。generic output/input 侧则是每 slot `ExactlyOne`，slot domain 中每个 slot 同时只能选一个 commodity 或 `__unused__`（`src/models/binding_subproblem.py:748`、`:794`）。结构上不存在跨 commodity 共享同一物理端口 cell 叠加吞吐的 false-FEASIBLE。

routing-free 终品集在当前 frozen artifacts 中也精确。`routing_free_sink_commodities` 来自正需求的 `required_generic_inputs`（`src/models/binding_subproblem.py:369-373`）；artifact loader 对 generic input 要求 canonical `sink_kind == generic_input`（`:249-305`），并且 master certified 入口委托同一 loader（`src/models/master_model.py:2007-2014`）。probe 从 canonical 反推得到：

```text
canonical_generic_inputs=['qiaoyu_capsule', 'valley_battery']
positive_required_inputs=['qiaoyu_capsule', 'valley_battery']
routing_free_sets_equal=True
routing_free_toy_status=FEASIBLE
routing_free_toy_exported_commodities=['dense_source_powder', 'fine_buckwheat_powder', 'steel_bottle', 'steel_part']
```

`extract_port_specs()` 在 fixed output 侧跳过 routing-free commodity（`src/models/binding_subproblem.py:1021-1025`），在 generic output 侧也跳过 `__unused__` 与 routing-free commodity（`:1055-1061`），而 generic input virtual slots 从不导出 routing specs（`:1037-1043`）。toy probe 同时放置 `packaging_battery` 与 `filling_capsule`，它们的终品输出 `valley_battery` / `qiaoyu_capsule` 没有进入 `port_specs`，只保留生产这些终品所需的 routed raw/material 输入。这与 `specs/05_facility_instance_definition.md:101-109` 以及 `PROJECT_LOCK.md:96-99` 的 producer-side routing-free 对偶排除一致。

## Q5-Q7：safe-reject 终态、overload 互锁、`__unused__` 精确计数

safe-reject ladder 的核心结构是 sound 的：`_binding_has_alternatives()` 只要存在 fixed binding vars、generic input vars 或 generic output vars 就返回 True（`src/search/benders_loop.py:6135-6140`，补丁后行号后移），`add_nogood_cut()` 只切当前 selection 中实际有变量的 literal（`src/models/binding_subproblem.py:1090-1106`）。如果 routing-front 阻塞来自 singleton fixed binding，而其它 generic slots 仍有自由度，循环可能继续枚举一些与真实 blocker 无关的 generic choices，但每次只加 binding-local nogood；只有 CP-SAT 在已加 selection nogoods 后返回 `INFEASIBLE`，才表示当前 binding 变量空间已穷尽。这个行为符合 `PROJECT_LOCK.md:134-135`，问题只出在本轮 finding 指出的 overload hard nogood 会让 CP-SAT 的“穷尽”语义被额外 heuristic clause 污染；补丁已把所有 re-solve `INFEASIBLE` 都接回 env-off replay fallback。

overload separation 默认关，certified 主链构造 `PortBindingModel` 时只传 `project_root`、`routing_context` 与 master snapshot requirements，不主动传任何 overload env（`src/search/benders_loop.py:5014-5021`）。本轮 finding 的补丁使 env-on 且 `overload_nogoods_added > 0` 的所有终态都 fail-closed 或 env-off 复核；若 env-off replay `TIMEOUT`，不会铸 nogood，只返回 `UNKNOWN`。若 env-off replay 仍 `INFEASIBLE`，才恢复原 exhaustion 证明链。

`__unused__` 精确计数成立。generic output/input slot domain 明确加入 `__unused__`（`src/models/binding_subproblem.py:713`、`:761`），每 slot `ExactlyOne`（`:748`、`:794`）。需求约束对每个真实 commodity 做 `sum(vars)==required`；`required==0` 时强制全部 real vars 为 false（`:796-820`）。reserved sentinel 在 requirement loader 中被拒（`:229-234`），`extract_port_specs()` 不导出 `__unused__`（`:1040`、`:1059`）。probe 用两个 generic-output slots 检查 `R<=S` 与 `R>S`：

```text
unused_required_1_status=FEASIBLE selection={'boundary_port_001:out:0': 'source_ore', 'boundary_port_002:out:0': '__unused__'} exported=['source_ore']
unused_required_2_status=FEASIBLE selection={'boundary_port_001:out:0': 'source_ore', 'boundary_port_002:out:0': 'source_ore'} exported=['source_ore', 'source_ore']
unused_required_3_status=INFEASIBLE selection={} exported=[]
```

因此不依赖当前 52=52 满额巧合：任意 `R<S` 会把剩余槽落到 `__unused__`，`R=S` 满额，`R>S` 正确 INFEASIBLE。

## 补丁摘要

补丁文件：`F-BIND-R8-01.patch`。

主要改动：

- `src/search/benders_loop.py`
  - 统一 overload fallback 触发判断。
  - 在 binding alternative loop 中记录并回放 rejected selections。
  - 三个 re-solve `INFEASIBLE` 点均执行 env-off replay fallback。
  - fallback helper 接收 `rejected_selections` 与 `routing_context`。
- `src/tests/test_binding.py`
  - 新增回归 `test_lbbd_retry_helper_replays_rejected_selections_after_overload_exhaustion`。

## 已运行验证

```text
PYTHONPATH=. python src/placement/placement_generator.py
# candidate_placements.json sha256 = adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
# size = 45,773,799 bytes

python -m py_compile src/search/benders_loop.py src/tests/test_binding.py
# passed

PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_binding.py
# 25 passed in 4.46s

PYTHONPATH=. python -m pytest -q -p no:randomly \
  src/tests/test_binding.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/cuts/test_family_port_exposure.py
# 62 passed in 7.90s

PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `PYTHONPATH=. python -m pytest -q -p no:randomly src/tests` 也启动过，但在沙盒 300 秒命令时限内未跑完，进度输出到约 6% 后被 timeout 中断；未观察到失败断言。完整全量回归建议在无 300 秒限制的本地环境补跑。
