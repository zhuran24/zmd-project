# 终末地 IndustrialPlanner cuts 面 round 12 独立审查报告

## 0. 输入校验与范围

- 指定快照：`/mnt/data/zmd_snapshot_c9315ba2.zip`
- sha256：`c9315ba216598e08ecb4103ca2563d7aabdecae11d48205803c17921fc4ead61`，已匹配后开工。
- 解包根：`/mnt/data/zmd_r12_work/project`
- 依赖：已从 `/mnt/data/zmd_py313_linux_x86_64.zip` 离线装入 Python 3.13 venv。
- 外置候选工件：`data/preprocessed/candidate_placements.json` sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，大小 `45,773,799` bytes，已匹配。

本轮没有得到“零 soundness finding”。发现并修复 1 个 cuts 面 soundness 问题：`CUT-R12-H1`。因此 cuts 面 **未达成三连饱和**，r12 不能作为第三个 clean round 计入闭合标准。

## 1. Finding

### CUT-R12-H1 — HIGH，power-conditioned infeasible cut 丢失 unpowered fixed-occupancy support

**位置**

- 原始包漏洞点：`src/search/benders_loop.py:4810-4815`
- 子问题证明上下文：`src/models/power_placement_subproblem.py:86-96`, `src/models/power_placement_subproblem.py:113-150`
- 修复后代码：`src/search/benders_loop.py:4805-4859`
- 回归：`src/tests/test_power_witness_cut_dilution.py:244-352`

**严重性说明**

这是 gated/exploratory 通道内的 HIGH：默认 certified / production campaign 仍由 PROJECT_LOCK 和 env guard 阻断 `EXACT_POWER_PLACEMENT_SUBPROBLEM=1`，所以默认公开 certified 路径未暴露。但一旦用 forensic bypass 打开该通道，它会生成 `exact_safe=True` 的 master cut，且 cut 的 forbidden tuple 比实际证明上下文更宽，会误删合法布局。

**问题机制**

`PowerPlacementSubproblem` 的固定占用集合不是“powered consumers only”。它把当前 master solution 里的每个非 `power_pole`、非 `ghost_pick` 设施占用格都纳入固定障碍：`_fixed_occupied_cells()` 遍历 `master_solution` 并 union 每个非 pole/ghost pose 的 `occupied_cells`。随后 `build()` 在候选 pole 过滤阶段执行 `if occupied & fixed: continue`，最后 coverage 约束要求每个 powered instance 至少有一个仍可用的 covering pole。

因此 power subproblem 的 INFEASIBLE 证明可能依赖一个不需要电的设施挡住唯一 pole cell。例如当前真实 mandatory 数据里存在 unpowered 非 pole 固定占用 contributors：`boundary_storage_port` 46 个、`protocol_core` 1 个。它们不需要 power，但它们的占用格会过滤候选 pole。

原始 `_run_power_placement_subproblem()` 在 `result.status == "INFEASIBLE"` 时只把 `tpl in powered_templates` 的 selected poses 放入 `conflict_set`。这会把证明从：

> powered pose + unpowered blocker pose + ghost anchor 下无法放 pole

错误投影成：

> powered pose + ghost anchor 下无法放 pole

于是下一轮如果 powered pose 和 ghost anchor 不变，但 unpowered blocker 移走，真实上可能出现可用 pole witness；原 cut 仍会禁止这个合法 layout。这是 CUT-R8-H1 “compiled constant support 必须进入 master tuple”的同类漏网鱼，只是藏在 power-conditioned cut 通道里。

**可复现 red probe / regression**

新增测试构造 4×1 极小布局：

- `powered_001` 位于 `(0,0)`，需要 power。
- 唯一能覆盖它的 `power_pole` pose 占 `(2,0)`。
- `boundary_001` 是 unpowered `boundary_storage_port`，也占 `(2,0)`，因此子问题中唯一 pole 被 fixed occupancy 过滤掉。
- ghost anchor 条件正常存在。

在修复前运行：

```bash
PYTHONPATH=. pytest -q -p no:randomly \
  src/tests/test_power_witness_cut_dilution.py::test_power_subproblem_infeasible_cut_keeps_unpowered_occupancy_support
```

失败输出核心为：

```text
E       AssertionError: assert {'powered_001': 0} == {'boundary_001': 0, 'powered_001': 0}
```

这证明原 cut 的 `conflict_set` 丢了 `boundary_001`，即丢了实际让 pole unavailable 的 fixed-occupancy support。

**修复**

补丁把 power subproblem infeasible cut 的 `conflict_set` 改为当前 solution 中所有非 `power_pole`、非 `ghost_pick` 的 selected occupancy support，并在 entry 无法严格解析 `pose_idx` 时 fail-closed `ABORT`。这只会弱化 cut，不会扩张 cut 的 forbidden set；它让 cut 的生效范围不超过子问题实际编译过的固定占用上下文。

同时在 `proof_summary` 记录：

```text
support_conflict_scope = all_non_pole_selected_occupancy
```

并更新 `power_placement_subproblem.py` 顶部 exact-preservation 文档，避免继续声称 infeasible cut 只禁止 powered-instance tuple。

**补丁文件**

- `/mnt/data/cuts_r12_power_support.patch`

## 2. Q1 轻复核结论

- D2 deny-unknown production precheck gate 仍在：`src/search/d2_separator.py:261-293` 先跑 production `run_exact_routing_precheck`，只有 `front_blocked` / `relaxed_disconnected` 才允许继续加 D2 cut；其它状态为 `MODEL_INVALID` 不写 cut。
- D2 port owner 校验仍在：`src/search/d2_separator.py:172-200` 对缺失、空白、ghost、placement 中不存在的 owner fail-closed。
- D2 support augmentation 仍在：`src/search/d2_separator.py:342-368` 使用 port owners + occupancy contributors + raw core 共同构造 master conflict tuple。
- 条件 cut replay 生命周期仍保持 V82 fail-closed：`src/search/benders_loop.py:6576-6593` 在 certified mode 下强制 `raw_candidate_cuts = []`，persisted `exact_safe_cuts` 只保留 telemetry 输入计数，不作为 proof replay；条件 replay 解析逻辑虽然保留，但 certified 下没有 raw cuts 可进入。
- lazy connectivity / deletion-core / ladder 弱序本轮只轻扫，没有发现与本包同期 preprocess public-entry 修复的交叉破坏。

## 3. Q2 全通道独立再审结论

本轮换了一个偏“support projection / literal identity / lifecycle replay”的角度，不沿 r11 的 lazy-connectivity / deletion-core 深挖路线重复走。

### 3.1 binding nogood 本体

`PortBindingModel.extract_selection()` 返回三类完整选择：`binding_choice`、`generic_inputs`、`generic_outputs`。`add_nogood_cut()` 对这三类选择逐 literal 收集，并加 `sum(literals) <= len(literals)-1`，只排除当前 exact binding assignment，不上升为 placement nogood。`__unused__` 在 binding domain 中是显式 sentinel，`extract_port_specs()` 在输入/输出两侧都过滤 `None` / `__unused__`，无线 virtual input 也不会流入 routing specs。

结论：binding nogood 本体未发现 soundness finding。它排除的是当前不可行 binding 配置本身，不多禁同 placement 下其它 binding alternative；routing precheck safe-reject 路径在存在 binding alternatives 时继续 `binding_model.add_nogood_cut(selection)` 并 re-solve。

### 3.2 master placement nogood / whole-layout nogood

`_build_whole_layout_conflict()` 排除 `ghost_pick`，其它 solution pose 进入 conflict tuple；`_add_exact_whole_layout_nogood()` 在 power-subproblem flag on 且 solution 含 synthetic `power_pole` witness 时 fail-closed，避免 witness incomplete 的 whole-layout cut；`_add_exact_persisted_nogood()` 构造 `BendersCut` 后 round-trip 校验，`master.add_benders_cut()` 失败则不注册 cut。coordinate / pose-bool backend 均有 malformed / duplicate literal fail-closed 逻辑，避免把 `{A,B}` 稀释或膨胀成更强 cut。

结论：除本轮发现的 power-conditioned infeasible cut support projection 问题外，master / whole-layout nogood 未发现新增 soundness finding。

### 3.3 lazy-demand / cell-pattern generic 容量饱和

本轮重点重证了 `__unused__` 与 52=52 饱和前提：

- `BindingSubproblem` 仍把 `__unused__` 加入 generic input/output slot domain，而不是结构性删除。
- pose-bool cell-pattern 只在 side 的 visible demand 覆盖全部 physical ports 时注册 port candidates；generic-output slot 只有在 mandatory generic-output capacity 与 required generic-output demand 全局相等时才计入 visible output demand。
- 自定义 probe 确认当前数据：`generic_output_capacity = 52`，`generic_output_required = 52`，`generic_output_saturated = True`。
- probe 还检查了 current candidate data 下的 cell-pattern hazards：`cell_pattern_self_overlap_count = 0`，`cell_pattern_intra_port_duplicate_keys = 0`，`candidate_pose_duplicate_occupied_cells = 0`。

结论：lazy-demand / cell-pattern 的 generic 容量饱和逻辑本轮未发现 soundness finding。

### 3.4 D2 commodity-flow separator

D2 已具备三层防线：owner 校验、production precheck deny-unknown gate、support-augmented conflict tuple。当前实现不会把 D2 自己的 stricter-than-production infeasibility 直接升级为 master cut；只有 production precheck 已给出 layout-local impossibility 时才进入 D2 cut emission。

结论：本轮未发现 D2 新 soundness finding。

### 3.5 PCR-CUT patch separator

PCR-CUT 仍保留 replay validation：raw core 必须用同一 patch model、只启用 candidate core assumptions 复验为 INFEASIBLE；QuickXplain 失败时回退 raw validated core；patch support 侧包含 constant occupancy 支撑，signature lifting 对 unresolved / overlap var sets fail-closed。

结论：本轮未发现 PCR-CUT 新 soundness finding。

### 3.6 cut replay / persist lifecycle

certified mode 下 persisted `exact_safe_cuts` 不参与 master 收紧，`raw_candidate_cuts=[]` 是代码强制，不是文档假设。`persisted_exact_safe_cut_replay_input_count` 仅用于 telemetry，`persisted_exact_safe_cut_replay_enabled=False`。

结论：cut replay 生命周期未发现 soundness finding。

## 4. Q3 自由攻击角

我选择 power-conditioned infeasible cut 作为自由攻击角，理由是它同时具备三种高风险味道：

1. 它是 cut channel，但被 PROJECT_LOCK 标为 exploratory，容易因为“默认禁用”而在确认轮中被轻扫过去。
2. 它把一个独立子问题的证明投影回 master，最容易出现 proof context 与 conflict tuple 不一致。
3. 它已经有 ghost-conditioned 和 witness-complete 的历史修补，说明该通道的语义边界复杂。

攻击过程从 `PowerPlacementSubproblem` 的 fixed occupancy 编译口径出发，反推 `benders_loop` 写入 master cut 的 conflict tuple 是否覆盖了所有编译常量。这个角度找到了 CUT-R12-H1。

## 5. 验证记录

### 5.1 新增 regression red/green

修复前：

```text
FAILED src/tests/test_power_witness_cut_dilution.py::test_power_subproblem_infeasible_cut_keeps_unpowered_occupancy_support
AssertionError: assert {'powered_001': 0} == {'boundary_001': 0, 'powered_001': 0}
```

修复后：

```bash
PYTHONPATH=. pytest -q -p no:randomly \
  src/tests/test_power_witness_cut_dilution.py::test_power_subproblem_infeasible_cut_keeps_unpowered_occupancy_support
```

```text
1 passed in 1.06s
```

### 5.2 Power 相关测试

```bash
PYTHONPATH=. pytest -q -p no:randomly \
  src/tests/test_power_witness_cut_dilution.py \
  src/tests/test_power_placement_subproblem.py
```

```text
12 passed in 1.14s
```

### 5.3 cuts/D2/PCR/binding-lifecycle 专项

```bash
PYTHONPATH=. pytest -q -p no:randomly \
  src/tests/test_d2_separator_support_context.py \
  src/tests/test_wireless_front_consumers_r4.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_coordinate_benders_cut_presence_nogood.py \
  src/tests/test_v82_persisted_cut_replay_fail_closed.py \
  src/tests/test_patch_routing_core.py \
  src/tests/test_power_witness_cut_dilution.py \
  src/tests/test_power_placement_subproblem.py \
  src/tests/test_master_cut_solution_invalidation.py \
  src/tests/cuts
```

```text
537 passed in 11.61s
```

### 5.4 binding / exact contract 抽查

```bash
PYTHONPATH=. pytest -q -p no:randomly \
  src/tests/test_binding.py \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_use_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_retry_binding_receives_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_require_wireless_slot_snapshot_for_generic_inputs \
  src/tests/test_exact_contract.py::test_binding_infeasible_generates_exact_safe_whole_layout_cut \
  src/tests/test_exact_contract.py::test_binding_alt_cap_returns_unknown_without_whole_layout_cut \
  src/tests/test_exact_contract.py::test_unexpected_initial_binding_status_returns_unknown_without_exact_safe_cut \
  src/tests/test_exact_contract.py::test_unexpected_binding_resolve_status_returns_unknown_without_exhaustion_cut \
  src/tests/test_exact_contract.py::test_binding_domain_empty_generates_singleton_cut_and_continues_master_loop \
  src/tests/test_exact_contract.py::test_relaxed_disconnected_only_rejects_binding_selection_without_persisted_cut \
  src/tests/test_v83_certified_surface_soundness.py
```

```text
36 passed in 3.75s
```

### 5.5 proof obligations

```bash
PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
```

```text
P1.2 proof obligation check passed: 8 obligations anchored
```

### 5.6 cell-pattern / saturation probe

Probe 文件：`cc_context/review/probes/algoaudit_cuts_r12_cell_pattern_saturation_probe.py`

```bash
PYTHONPATH=. python cc_context/review/probes/algoaudit_cuts_r12_cell_pattern_saturation_probe.py
```

```text
candidate_sha256 adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0
candidate_bytes 45773799
mandatory_instances 266
required_optional_counts {'protocol_storage_box': 1}
wireless_sink_generic_input_slots 3
constructor_seconds 11.945
generic_output_capacity 52
generic_output_required 52
generic_output_saturated True
mandatory_feasible_pose_count 293498
cell_pattern_exact_side_pose_count 24270
cell_pattern_front_pairs_checked 92726
cell_pattern_out_of_grid_fronts 0
cell_pattern_self_overlap_count 0
cell_pattern_intra_port_duplicate_keys 0
candidate_pose_duplicate_occupied_cells 0
probe_ok
```

### 5.7 全量测试

尝试运行：

```bash
PYTHONPATH=. pytest -q -p no:randomly src/tests
```

沙盒 420 秒超时，停在约 16% 进度；超时前未看到 failure，仅看到进度点和两个 skip。未把该项记为完整通过。

## 6. 本轮结论

- 本轮非零：发现并修复 `CUT-R12-H1`。
- 已附 unified diff 与 regression。
- cuts 面第三个连续独立 clean round **未成立**；建议将 r12 记为修复轮，下一轮重新从“连零计数”开始或按 owner 标准重置到 r13 确认轮。
