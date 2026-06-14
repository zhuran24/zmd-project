# 终末地 IndustrialPlanner binding round 9 review

审查对象：`zmd_snapshot_1e136b90.zip`。开工前校验 sha256 为 `1e136b90a290684874398ce5f2ddaceac156481d2178fa1333db9ba14b8e16f2`，与任务指定值一致；只解包并审查该快照。随包 `data/preprocessed/candidate_placements.json` 校验 sha256 为 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，size `45,773,799` bytes，与任务指定值一致。依赖使用 `zmd_py313_linux_x86_64.zip` 离线安装到 Python 3.13 环境。

结论：本轮发现 1 个同族残留，**F-BIND-R9-01 / LOW availability hardening**。R8-01 overload fallback 修复本身判定 sound，未发现遗漏的 binding-INFEASIBLE→exhaustion 路径；R8-02 对当前随包 certified artifact 的主链有效，但它的 gate 仍漏掉 “output-only 非空需求工件” 这一同型边界。我已给出最小补丁与回归测试。

## Finding: F-BIND-R9-01 — output-only generic I/O artifact bypasses canonical generic-input completeness check

Severity: LOW availability hardening；方向为 fail-open malformed proof input，可诱发 spurious `front_blocked` / false-INFEASIBLE，属于 R8-02 同族残留。

Files:

- 原始缺口：`src/models/binding_subproblem.py:306-342`，尤其 `:312 if input_commodities:` gate。
- 规则/交互依据：`specs/05_facility_instance_definition.md:101-109`，`rules/canonical_rules.json:305-314`，`src/models/binding_subproblem.py:406-410` 与 `:1092-1099`。
- 修复：`src/models/binding_subproblem.py:306-341`，`src/tests/test_binding.py:896-916`，`PROJECT_LOCK.md:135`。

### What happens

R8-02 的修复只在 `required_generic_inputs` 非空时执行 canonical generic-input 完备性校验。原始代码允许一个非空但 output-only 的 `generic_io_requirements.json`：`required_generic_outputs` 有合法外部源商品，`required_generic_inputs` 为空。这个工件不是 “output+input 双空” 的 toy 退化态，却会绕过 `canonical sink_kind=generic_input` 的覆盖检查。

在当前 canonical 中，`valley_battery` 与 `qiaoyu_capsule` 明确是 `sink_kind = generic_input`（`rules/canonical_rules.json:305-314`）。规范 §5.4.3 要求这些无线终品不进入 routing sink，并且其 producer 输出口也必须从 `extract_port_specs()` 排除（`specs/05_facility_instance_definition.md:101-109`）。实现中 routing-free 集合来自 `required_generic_inputs` 正槽数（`binding_subproblem.py:406-410`），而 `extract_port_specs()` 只跳过属于该集合的 generic-output commodity（`binding_subproblem.py:1092-1099`）。因此 output-only 工件会使 routing-free 集合为空，把无线终品生产端输出重新暴露成 routing terminal，回到 R8-02 描述的 “orphan source / spurious front_blocked / false-INFEASIBLE” 家族。

### Reproducer

在未打补丁的原始解包树上，以下 probe 被接受：

```text
ACCEPTED {'required_generic_outputs': {'source_ore': 18, 'blue_iron_ore': 34}, 'required_generic_inputs': {}}
```

同一 probe 在补丁后 fail-closed：

```text
ValueError generic_io_requirements.required_generic_inputs must include every canonical sink_kind=generic_input commodity with a positive slot count （非空 generic I/O 需求工件必须以正槽数覆盖所有 canonical generic_input 终品）: missing=qiaoyu_capsule,valley_battery
```

Probe payload:

```json
{
  "required_generic_outputs": {"source_ore": 18, "blue_iron_ore": 34},
  "required_generic_inputs": {}
}
```

### Fix

保留 “both output+input empty” 的 early return，所以 toy/test 退化态不受影响；但只要 generic I/O 工件非空（output 或 input 任一 section 有内容），就必须以正槽数覆盖所有 canonical `sink_kind=generic_input` 商品。补丁还更新了 lock 条款，避免后续再把 “output-only” 误读成合法空需求。

Regression: `test_load_generic_io_requirements_rejects_output_only_when_canonical_generic_inputs_exist`。

## Q1 — R8-01 overload fallback 修复 soundness + 同型枚举结论

判定：R8-01 修复 sound，未发现残留的 binding-INFEASIBLE→exhaustion 绕过 fallback 路径。

同型枚举结果如下。初始 solve 在 `src/search/benders_loop.py:5136`，若返回 `INFEASIBLE`，先在 `:5153-5210` 做 env-off fallback，只有 fallback 后仍为 `INFEASIBLE` 才进入 `binding_infeasible_nogood`（`:5212-5236`）。后续三条 binding re-solve 路径分别是 safe-reject/front-blocked 分支 `:5440`，relaxed-disconnected 分支 `:5845`，routing-INFEASIBLE 后继续枚举分支 `:6078`；三处在 `INFEASIBLE` 后都调用 `_retry_current_binding_without_overload_separation()`（`:5464`, `:5867`, `:6100`），在 `FEASIBLE` 时恢复枚举，在 `TIMEOUT` 时 fail-closed 为 `UNKNOWN`，只有 retry 后仍 `INFEASIBLE` 才 break 到 `routing_exhausted_nogood`（`:6165-6173`）。我也静态搜索了 `_add_storage_box_overload_nogoods` 的调用点；实际注入只在 `PortBindingModel.build()` 的 env-gated block（`binding_subproblem.py:508-517`）发生，无第二条隐藏注入路径。

`_retry_current_binding_without_overload_separation()` 使用 `nonlocal binding_model, binding_status`（`benders_loop.py:5270-5285`），并把 `binding_rejected_selections` 传给 retry helper。`_retry_binding_without_overload_separation()` 在构建 retry model 时只把 `EXACT_BINDING_USE_OVERLOAD_SEPARATION` 强制为空（`:6215-6240`），仍使用同一 `solution`、同一 `routing_context`、同一 master snapshot 的 generic I/O kwargs（`:6224-6231`），并在 solve 前 replay 所有 rejected selections（`:6232-6235`）。因此 env-off replay 没有放松 exact-one、容量、generic input/output 需求；它只移除 overload heuristic hard nogoods。

`_binding_used_overload_separation()`（`:6183-6188`）以 `overload_separation_enabled is True` 且 `overload_nogoods_added > 0` 作为触发条件。`PortBindingModel.build()` 在 env-on 且 `_add_storage_box_overload_nogoods()` 返回后写入这两个 summary 字段（`binding_subproblem.py:508-517`），而 `_add_storage_box_overload_nogoods()` 每添加一个 CP-SAT clause 就递增计数（`:587-590`）。如果 env-on 但 count 为 0，事实上没有 hard nogood 注入，不需要 fallback；若 count > 0，predicate 命中。未发现 false-negative 形态；false-positive 最坏只是多一次 env-off solve，属于性能问题而非 soundness。

## Q2 — R8-02 完备性校验修复 soundness + gate 边界判读

当前随包 certified 主链上，R8-02 的 intended 修复对真实 artifact 是生效的：`ExactSearchSession.create()` 先调用 `load_generic_io_requirements_artifact(project_root)`（`benders_loop.py:1575-1591`），master 侧 loader 委托 binding loader（`master_model.py:2007-2014`），然后 master core 保存同一 normalized snapshot（`master_model.py:2531-2607`），binding 通过 `_binding_generic_requirements_kwargs()` 消费该 snapshot（`benders_loop.py:4939-4983`）。随包 `data/preprocessed/generic_io_requirements.json:11-18` 的 `required_generic_inputs` 非空且正槽覆盖 `qiaoyu_capsule`、`valley_battery`，所以原 R8 gate 在当前 artifact 上确实会触发。

但 gate 本身过窄：它只检查 “input 非空”，没有检查 “需求工件非空”。output-only 工件不是合法退化态，却会被原始 loader 接受。这就是 F-BIND-R9-01。

完备性口径方面，canonical set 取自 `commodity_metadata[*].sink_kind == generic_input`，与规范 §5.4.3 的无线终品定义一致（`specs/05...:109`）。routing-free sink set 当前由 positive `required_generic_inputs` 形成（`binding_subproblem.py:406-410`），所以 loader 层要求 every canonical generic-input 都有 positive slot count 是必要的，不是从实现倒推出来的偶然约束。

类型/取整方面没有发现新的 fail-open：`load_generic_io_requirements()` 先经 `_load_generic_io_requirement_section()` 与 `_normalize_generic_io_requirement_mapping()`（`binding_subproblem.py:203-246`）解析，bool、float、str、负数都会 fail-closed；`_validate_generic_io_requirement_roles()` 中的 `int(...)` 只作用在已归一化的 int 上。master 侧入口也委托同一 loader（`master_model.py:2007-2014`），未保留更宽松解析分叉。

## Q3 — 两修复交互 + 回归判读

R8-01 的 env-off retry 不重新从磁盘装载 generic I/O artifact。它通过 `LBBDController._binding_generic_requirements_kwargs(self)` 使用 master 已冻结的 normalized `generic_io_requirements` snapshot（`benders_loop.py:4939-4983`, `:6224-6231`）。因此 overload env 切换不会改变需求集；R8-02/R9-01 的 loader 校验只在 session/master proof boundary 处发生一次，之后 binding/retry 共享同源快照。

R8-02/R9-01 的完备性校验不会误拒合法 “部分 generic input 生产配置”。`qiaoyu_capsule` 与 `valley_battery` 是 canonical production targets 且 sink_kind 为 generic_input（`rules/canonical_rules.json:293-314`）；规范要求无线消费侧以虚拟槽消费，生产端对偶排除 routing terminal（`specs/05...:101-109`）。这是 placed certified instance 的 binding/routing 接口不变量，不是某个 candidate 几何局部 “用到多少终品” 的可选条件。真正合法的 toy 退化态仍是 output+input 双空，early return 保留。

## Patch contents

`binding_r9.patch` 包含：

1. `src/models/binding_subproblem.py`：把 canonical generic-input 完备性检查从 `if input_commodities:` 中移出，保留双空 early return。
2. `src/tests/test_binding.py`：新增 output-only artifact 回归测试。
3. `PROJECT_LOCK.md`：把 invariant 从 “非空 input section” 精确为 “非空 generic I/O artifact”。

该 patch 已在原始解包树上通过 `patch -p1 --dry-run`。

## Verification

通过：

```text
python3.13 -m pytest -q src/tests/test_binding.py src/tests/test_exact_contract.py src/tests/test_wireless_sink_binding_semantics.py src/tests/cuts/test_family_port_exposure.py -p no:randomly
155 passed in 8.32s
```

通过：

```text
python3.13 -m pytest -q \
  src/tests/test_binding.py::test_load_generic_io_requirements_rejects_output_only_when_canonical_generic_inputs_exist \
  src/tests/test_binding.py::test_load_generic_io_requirements_rejects_missing_or_zero_canonical_generic_inputs \
  src/tests/test_binding.py::test_load_generic_io_requirements_rejects_non_canonical_roles \
  src/tests/test_binding.py::test_lbbd_retry_helper_replays_rejected_selections_after_overload_exhaustion \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_use_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_retry_binding_receives_master_generic_io_snapshot \
  -p no:randomly
6 passed in 4.29s
```

通过：

```text
python3.13 scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored
```

全量 `python3.13 -m pytest -q src/tests -p no:randomly` 已尝试运行，300 秒沙盒超时前只看到进度点输出，未观察到 failure；因此本轮完整 suite 未能在沙盒内跑完。
