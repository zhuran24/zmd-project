# 终末地 IndustrialPlanner cuts 面 round 13 审查报告

审查对象：`zmd_snapshot_5e5e0c86.zip`  
任务声明 sha256：`5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`  
实测 sha256：`5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`  
结论：校验通过，只审该快照。

## 总结

本轮不是零 finding。本轮发现并修复 1 个 power 通道 soundness finding：

- **HIGH / CUT-R13-H1：delegated power FEASIBLE witness 在选中 ghost context 不可恢复时会继续求解 de-ghosted 子问题，可能把 synthetic power_pole witness 放进被认证的 empty rectangle。**

CUT-R12-H1 本身的修复口径确认成立：INFEASIBLE cut 的 `conflict_set` 已从 powered-only 扩展为 all non-pole / non-ghost selected occupancy support，和 `PowerPlacementSubproblem` 的固定障碍编译口径对齐；ghost anchor 也仍作为 condition literal/persisted `condition_set` 保留。新 finding 是 Q2 纵深里看到的 FEASIBLE 路径 witness 完整性缺口，不是对 CUT-R12-H1 的重复报告。

补丁：`/mnt/data/CUT_R13_power_ghost_context_fix.patch`。补丁已在工作树应用并跑过专项回归。未跑完全量 `src/tests`，详见“验证”。

## Finding: CUT-R13-H1

Severity: HIGH

文件：`src/search/benders_loop.py:4777-4800` 修复后位置；原缺口在 `_run_power_placement_subproblem()` 进入 `PowerPlacementSubproblem` 前。

### 问题

`EXACT_POWER_PLACEMENT_SUBPROBLEM=1` 时，coordinate master 不 materialize residual `power_pole` slots，power witness 由 `_run_power_placement_subproblem()` 事后补齐。这个 witness 的 soundness 依赖两个上下文同时成立：

1. 每个 powered consumer 被某个 selected pole 覆盖。
2. selected pole 不与 master 固定设施和 selected ghost rectangle 重叠。

子问题本体确实会把 `ghost_cells` 编入 fixed obstacle：`src/models/power_placement_subproblem.py:87-97` 初始化 fixed occupancy，`src/models/power_placement_subproblem.py:110-151` 用 fixed 过滤 candidate pole 并约束 coverage。

但原 `_run_power_placement_subproblem()` 在 FEASIBLE 路径只做：

- `ghost_cells = self._selected_ghost_cells()`；
- 即使该集合为空，也继续 build/solve；
- FEASIBLE 后直接 `inject_power_poles_into_solution()`，返回带 synthetic poles 的 solution。

这和 INFEASIBLE cut 路径不对称：INFEASIBLE 时 `_selected_ghost_anchor()` 取不到会 ABORT；FEASIBLE 时 selected ghost context 取不到却可能继续产 witness。若 master 内部状态、solver handle、`u_vars` / `_ghost_domains` 生命周期或未来 master 变体导致 ghost context 无法恢复，子问题会退化成“不知道 empty rectangle”的 power placement。此时它可能选择一个实际落在 selected ghost rectangle 内的 pole，从而把非法 witness 当成可行 completion。

默认 certified 被 `PROJECT_LOCK L4a` 和 env blocker 阻断，降低生产暴露面；但本面已明确要求 forensic-bypass 下仍审 soundness。这个缺口是 power channel 的 proof-context 丢失，不是性能/探索行为问题。

### Probe / regression

新增回归：`src/tests/test_power_witness_cut_dilution.py:307-370`

构造一个最小 controller：powered widget 的唯一 covering pole 是可选 witness，但 fake master 无 `u_vars`、无 `_ghost_domains`、无 `_solver`。修复前 `_run_power_placement_subproblem()` 会得到 `ghost_cells=set()`，继续求解并返回 `FEASIBLE`；修复后必须 `ABORT`，且不产生 cut / witness。

### 修法

补丁把 ghost provenance 取数前移到 power subproblem build 前：

- `_selected_ghost_anchor()` 取不到：立即 `ABORT`，不 build de-ghosted 子问题。
- `_selected_ghost_cells()` 为空：立即 `ABORT`，不 build de-ghosted 子问题。
- INFEASIBLE cut 路径复用同一个 `(rect_idx, u_var, anchor)`，避免 FEASIBLE 和 INFEASIBLE 两条路径看到不同 ghost context。

修复后，power FEASIBLE witness 与 power INFEASIBLE cut 都共享同一 selected ghost context。若 ghost provenance 生命周期损坏，caller 走现有 fail-closed UNKNOWN，不会注入 pole witness，也不会写 cut。

## Q1: CUT-R12-H1 修复确认

### ① support 收集口径与子问题编译口径对齐

确认对齐。

`PowerPlacementSubproblem._fixed_occupied_cells()` 的固定障碍集合是：`ghost_cells` 加上 `master_solution` 中所有非 `facility_type == "power_pole"` 且非 `instance_id == "ghost_pick"` 的 selected pose `occupied_cells`，见 `src/models/power_placement_subproblem.py:87-97`。

power INFEASIBLE cut 的 `conflict_set` 遍历同一个 `solution`，跳过同样两类 entry：`facility_type == "power_pole"` 和 `instance_id == "ghost_pick"`，其余全部收 `pose_idx`，见 `src/search/benders_loop.py:4840-4850`。这覆盖了真实数据里的 unpowered fixed-occupancy blockers，例如 `boundary_storage_port` 和 `protocol_core`，不再把证明上下文错误投影成 powered-only。

唯一刻意不进入 `conflict_set` 的 fixed 部分是 `ghost_cells`。它由 `condition_lits=(u_var,)` 和 persisted `condition_set={"ghost_anchor::(x,y)": rect_idx}` 表达，见 `src/search/benders_loop.py:4852-4876`；schema/metadata 校验见 `src/models/cut_manager.py:24-27`、`src/models/cut_manager.py:153-209`，replay resolver fail-closed 见 `src/search/benders_loop.py:1489-1534`。因此 proof context 是“all non-pole selected occupancy + selected ghost anchor condition”，没有第三类障碍被模型使用却丢出 cut。

我还跑了数据口径 probe：`candidate_placements.json` 共 66,403 个 pose，`occupied_cells` missing=0、empty=0、bad=0；mandatory exact instances 共 266，其中 `boundary_storage_port=46`、`protocol_core=1`，正是 CUT-R12-H1 关心的 unpowered blockers。

### ② ABORT fail-closed 的彻底性

CUT-R12-H1 修复里的 INFEASIBLE cut entry 解析失败会 `ABORT`，见 `src/search/benders_loop.py:4845-4848`；空 conflict set 也 `ABORT`，见 `src/search/benders_loop.py:4849-4850`。`_add_exact_persisted_nogood()` 若 structured cut validation、master add、cut-manager register 任一失败，返回 False，caller 也转 `ABORT`，见 `src/search/benders_loop.py:6143-6189` 与 `src/search/benders_loop.py:4889-4891`。

caller 对 power subproblem 的非 FEASIBLE / 非 CUT_ADDED 状态统一 `fail_closed_unknown`，不把 ABORT 当证明性结论，见 `src/search/benders_loop.py:4531-4558`。

本轮补丁进一步补齐 FEASIBLE 路径：selected ghost anchor/cells 不可恢复时，在 build subproblem 前 `ABORT`，见 `src/search/benders_loop.py:4777-4800`。这样 ABORT 语义覆盖了 “cut provenance 不完整” 和 “witness provenance 不完整” 两边。

补充说明：如果传入完全非 mapping 的 adversarial `solution`，`PowerPlacementSubproblem.build()` 仍可能 fail-stop 抛异常而不是返回 ABORT；这不会产生 cut 或 witness，不构成本轮 over-cut/false-cert finding。后续可把该类异常包装成 telemetry ABORT，属于可观测性硬化。

### ③ 弱化方向确认

确认弱化方向正确。

master nogood 形式是“当前 tuple 全部同时出现则禁止”。把 conflict set 从 powered-only 扩展到 all non-pole selected occupancy 后，约束从 `not(powered tuple)` 变成 `not(powered tuple AND blocker tuple AND ...)`。前者禁止更多 layout，后者只禁止更具体的 proof context，所以这是严格弱化，不会反向 over-cut。

ghost-conditioned 前提保持完整：runtime cut 使用 `OnlyEnforceIf(u_var)`，persisted cut 记录 canonical `ghost_anchor::(x,y)`，condition key、metadata ghost rect index、metadata anchor 三者必须一致才能通过 `BendersCut` 校验，见 `src/models/cut_manager.py:153-209`；condition replay 解析失败不会退化成 unconditional cut，见 `src/search/benders_loop.py:1489-1534`。

### ④ 与 CUT-R8-H1 / CUT-R9-H1 的一致性

确认一致。

D2 通道文档和实现明确采用 support-augmented tuple：D2 常量 occupancy 来自 `occupied_cells`，`_build_occupancy_support_pose_terms()` 收所有贡献 fixed footprint 的 selected owners，`_build_d2_supported_conflict_set()` 把 terminal assumptions、occupancy support、raw core 合并，见 `src/search/d2_separator.py:94-152`。D2 还要求 port owner validation 和 production precheck gate，避免 core 在更窄上下文里被认证，见 `src/search/d2_separator.py:172-217`。

PCR 通道同样把 patch 内部 cells 和 cardinal ring 的 constant occupancy 变成 support signature，再用 `_augment_core_with_patch_support()` 把 support assumptions 加回 solver core，见 `src/search/patch_conflict_separator.py:121-162`；实际 cut 生成前还做 replay validation，见 `src/search/patch_conflict_separator.py:466-499`。

power 通道现在与这套义务一致：separator / witness 使用了哪些 constant occupancy，cut 或 witness 就必须带上同一证明上下文。CUT-R12-H1 修复解决 INFEASIBLE cut 的 occupancy support；本轮补丁解决 FEASIBLE witness 的 ghost support。

## Q2: power 通道纵深

### FEASIBLE path witness 完整性

原代码在 witness 覆盖与 pole-pole non-overlap上是完整的：coverage table 来自 master 预计算 `_power_coverers_by_template_pose`，subproblem 用同一 table 过滤可用 coverers 并要求每个 powered instance 至少一个 selected pole，见 `src/models/power_placement_subproblem.py:135-151`；FEASIBLE 后注入 synthetic `power_pole` entry，见 `src/models/power_placement_subproblem.py:192-215`。

本轮发现的缺口在 ghost context provenance：FEASIBLE path 没有把“selected ghost 可恢复且 cells 非空”作为 witness 前置条件。已修。

### master 内 coverage 与 subproblem coverage 等价性

两边都使用 `_power_coverers_by_template_pose`：table 构建扫描 `power_pole.power_coverage_cells` 并过滤与 powered pose 自身占用重叠的 pole，见 `src/models/master_model.py:3331-3375`、`src/models/master_model.py:3582-3644`；legacy / pose-bool / coordinate table coverage 都读取该 table，见 `src/models/master_model.py:4730-4760`、`src/models/pose_bool_exact_master.py:426-451`、`src/models/exact_coordinate_master.py:5161-5212`。power subproblem 也读取同一 table，见 `src/models/power_placement_subproblem.py:135-151`。

因此 coverage relation 本身未发现 divergence。坐标几何 witness 与 table witness 的其它 encoding 分支属于 power-coverage 面，本轮没有扩大到重新证明所有几何变体；本轮只确认 delegated subproblem 使用的 relation 与 in-master table relation 同源。

### `_selected_ghost_anchor()` 取不到时的 ABORT

原 INFEASIBLE cut 路径已 ABORT；本轮补丁把 ABORT 前移，使 FEASIBLE 和 INFEASIBLE 都必须先拿到 selected ghost anchor，并要求 selected ghost cells 非空。修复后 caller 仍按现有 `fail_closed_unknown` 处理，不会写 cut，也不会注入 witness。

### whole-layout power-witness fail-closed 交互

`_add_exact_whole_layout_nogood()` 在 `EXACT_POWER_PLACEMENT_SUBPROBLEM` flag on 且 solution 含 synthetic/any power_pole 时返回 False，避免 synthetic pole 没有 master presence literal 时把 whole-layout cut 稀释成“无 pole witness”的上游 tuple，见 `src/search/benders_loop.py:6191-6239`。现有回归仍通过。

## Q3: 自由攻击角

我选择攻击 “condition / witness 生命周期是否会在 replay 或后续 cut 中被悄悄丢失”。理由是 CUT-R12-H1 暴露的根因不是 power 覆盖半径，而是 proof context 投影错误；同类错误最容易在 persisted condition、FEASIBLE witness 注入、whole-layout nogood 之间藏身。

攻击结果：

1. persisted power cut 的 ghost condition 不会静默丢失。`condition_set` 是 cut signature 的一部分，schema 要求 power cut 必须有 exactly one ghost anchor condition，metadata 必须匹配，replay 解析失败 skip/fail-closed，不退化为 unconditional cut。
2. whole-layout nogood 在 delegated power witness 存在时 fail-closed，不会把 `{facility tuple + synthetic pole tuple}` 稀释成 `{facility tuple}`。
3. 发现并修复 FEASIBLE witness 的 ghost provenance 前置校验缺口，即 CUT-R13-H1。

## 验证

使用 Python 3.13 venv + 离线 wheel 包安装依赖后执行。

通过：

```bash
python -m pytest -q -p no:randomly \
  src/tests/test_power_witness_cut_dilution.py \
  src/tests/test_power_placement_subproblem.py \
  src/tests/test_benders_cut_condition_lits.py \
  src/tests/test_benders_cut_replay_condition_lifecycle.py \
  src/tests/test_exact_contract.py::test_power_placement_abort_returns_unknown_with_matching_proof_summary
```

结果：`29 passed in 3.55s`

通过：

```bash
python -m pytest -q -p no:randomly \
  src/tests/test_v86_terminal_power_witness_validation.py \
  src/tests/test_v87_terminal_power_pole_irredundancy.py \
  src/tests/phase3b/power_coverage/test_witness_audit.py \
  src/tests/cuts/test_family_power_hitting_set.py \
  src/tests/cuts/test_family_power_grid_reach.py \
  src/tests/test_highs_power_coverage.py
```

结果：`78 passed in 20.01s`

通过：

```bash
python scripts/check_p1_2_proof_obligations.py
```

结果：`P1.2 proof obligation check passed: 8 obligations anchored`

尝试但未完成：

```bash
python -m pytest -q -p no:randomly src/tests
```

沙盒超时前未跑完整套，因此不声明全量绿。

## 补丁摘要

变更文件：

- `src/search/benders_loop.py`
- `src/tests/test_power_witness_cut_dilution.py`

补丁效果：

- delegated power subproblem build 前强制恢复 selected ghost anchor；失败则 ABORT。
- selected ghost cells 为空则 ABORT。
- INFEASIBLE cut 复用同一 ghost context，减少 TOCTOU 式上下文漂移。
- 新增 regression：缺失 ghost context 时不能从 FEASIBLE path 注入 pole witness。
