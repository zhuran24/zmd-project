# 终末地 IndustrialPlanner preprocess round 16 review

输入快照：`/mnt/data/zmd_snapshot_5e5e0c86.zip`

SHA256 已校验通过：`5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`。

审查范围：F-PRE-R15-01 修复确认，以及 preprocess 链自由攻击角。未审 master / routing / cuts / scheduler 等其它面；未把前轮已知结论重复报为新 finding。

## 总结

R15 主修复方向成立：`solve_demands_exact(context=...)` 已在 target-rate 与 backprop 之前调用 `validate_preprocess_context()`，`solve_demands()` 同步覆盖；全仓未发现第三条公开入口能直接绕过它进入 `_target_rate_per_tick()` / `_backpropagate_non_cycle_demands()`。

本轮不是零 finding。自由攻击与 raw-cycle 对齐检查抓到 2 个新的 preprocess soundness finding，并已给出补丁与回归：

1. `F-PRE-R16-01` HIGH：`external_boundary` 商品若同时由 recipe 生产，backprop 会在边界源处停止并跳过 producer 机器与上游输入。
2. `F-PRE-R16-02` HIGH：raw `solve_cycle_group_exact()` 入口没有重复 requested group 的本地 role contract，导致 full validation 拒绝的 group/commodity-role 不一致 context 仍可被直接 cycle-solve。

补丁文件：`/mnt/data/F_PRE_R16_preprocess_soundness.patch`。

## Q1. F-PRE-R15-01 修复确认

### 1. 入口覆盖完备性

结论：R15 对 demand backprop 的主入口覆盖完备。

关键路径：

- `src/preprocess/demand_solver.py:90-102`：`solve_demands()` 只委托 `solve_demands_exact()`。
- `src/preprocess/demand_solver.py:105-130`：`solve_demands_exact()` 在第 109 行先执行 `validate_preprocess_context(resolved_context)`，之后才在第 110-117 行计算 target demand 并进入 `_backpropagate_non_cycle_demands()`。
- `src/preprocess/demand_solver.py:264` / `:278`：`_target_rate_per_tick()` 与 `_backpropagate_non_cycle_demands()` 仍是 private helper。全仓调用点搜索显示二者只被 `solve_demands_exact()` 调用。
- `generate_ceil_machine_counts()`、`generate_port_budget()`、`generate_generic_io_requirements()` 分别在 `src/preprocess/demand_solver.py:135-188`，它们消费已经解出的 `machine_runs` / `flows`，不构造 target，也不回溯需求，因此不是第三条 demand-solve 入口。

调用图专项搜索使用：

```bash
rg "_backpropagate_non_cycle_demands|_target_rate_per_tick|solve_cycle_group_exact|generate_port_budget|generate_generic_io_requirements|generate_ceil_machine_counts|solve_demands_exact|solve_demands\(" src scripts --glob '!src/tests/**'
```

### 2. helper 抽取等价性

结论：R14 helper 抽取在 full `validate_preprocess_context()` 路径上等价；raw subset 路径在本轮补丁后也补齐了 group-local 缺口。

- `src/interchange/preprocess_context.py:251` 调用 `_validate_single_output_recipes(context)`，未传 `recipe_ids`，覆盖 `context.recipes.values()`，等价于旧的全量 recipe 遍历。
- `src/interchange/preprocess_context.py:315` 调用 `_validate_cycle_internal_output_ownership(context)`，未传 `group_ids`，遍历全部 recipe outputs 并按 declared `role.cycle_group` 检查 producer 是否属于该 group，等价于旧的全量 ownership 检查。
- raw cycle 路径在 `src/interchange/preprocess_context.py:538-540` 调用 single-output、cycle-internal output ownership 与本轮新增 `_validate_cycle_group_local_contract()`。其中 ownership helper 不是只扫 group recipes，而是扫全部 `context.recipes`，再按 `role.cycle_group in {group_id}` 过滤，因此能抓 requested group 的 outsider producer。
- subset `recipe_ids` 中的未知 recipe 在 single-output helper 中不会抛出，但本轮新增 `_validate_cycle_group_local_contract()` 会在 `src/interchange/preprocess_context.py:443-445` fail-closed；full validation 原本也在 `:332-334` fail-closed。

### 3. raw cycle solver 双端对齐

结论：R15 原补丁已覆盖 R14-01 / R14-02 / R13 / R12 RHS / R11；但本轮发现它没有覆盖 full validation 的 group-local role contract，见 `F-PRE-R16-02`。补丁后 raw cycle entry 与 full validation 在 requested group 的本地 contract 上对齐。

已实证拒绝：

- group recipe multi-output：拒绝。
- outsider producer of cycle-internal output：拒绝。
- cycle recipe I/O closure drift：拒绝。
- positive non-export internal RHS：拒绝。
- positive unknown RHS：拒绝。
- negative RHS：拒绝。
- negative run-rate solution：拒绝。
- group internal commodity role mismatch：原快照 raw solve 接受，补丁后拒绝。

### 4. 重验副作用

结论：对合法 default context，R15 的 full revalidation 是纯增 fail-closed 开销，没有发现行为变化。

验证结果：

```text
preprocess context diff summary:
{'all_match': True, 'matched_count': 6, 'total_count': 6, 'mandatory_exact_instance_count': 266, 'all_instance_count': 326, 'generic_output_slots': 52, 'generic_input_slots': 0}
```

默认 demand / machine count / port budget probe 也通过，R15 revalidation 没有误杀当前合法 context。

## Q2. R14/R13/R12/R11 维持轻确认

专项 probe 输出摘要：

```text
public solve_demands_exact multi-output: REJECTED
public solve_demands_exact outsider cycle producer: REJECTED
raw cycle solver group recipe multi-output: REJECTED
raw cycle solver outsider producer: REJECTED
raw cycle solver recipe I/O closure: REJECTED
raw cycle solver positive non-export internal RHS: REJECTED
raw cycle solver positive unknown RHS: REJECTED
raw cycle solver negative RHS: REJECTED
raw cycle solver negative run-rate: REJECTED
default pipeline: ACCEPTED and matches expected exact demand/port invariants
```

轻确认结论：

- R14-01：single-output 锁仍由 canonical semantic validation、`validate_preprocess_context()`、raw group recipe guard 三端覆盖。
- R14-02：cycle-internal output ownership 仍由 full validation 与 raw group guard 覆盖。
- R13：cycle recipe I/O closure full/raw 两端覆盖。
- R12：positive RHS key 必须同时是 internal 与 net-export，negative RHS 拒绝；本轮补丁还让 raw entry 对 group net-export subset / internal role mismatch 也 fail-closed。
- R11：负 run-rate 在 solve 时拒绝；unit-export basis 的合法性仍由 full validation 调 `_solve_cycle_group_exact()` 证明。

## Finding F-PRE-R16-01: external_boundary producer ownership fail-open

Severity：HIGH

文件位置：

- 根因：`src/preprocess/demand_solver.py:295-300`。`_backpropagate_non_cycle_demands()` 在 `role.source_kind == "external_boundary"` 时直接 `continue`，不会查询 producer index。
- 修复前缺口：`src/interchange/preprocess_context.py:278-310` 的 role validation 没有禁止 producer 与 `external_boundary` 并存；`src/rules/semantic_validator.py:140-154` 也没有 canonical 语义门。
- 补丁：`src/interchange/preprocess_context.py:283-287`、`src/rules/semantic_validator.py:154-158`。

### 攻击过程

在原始快照上，把 canonical 中实际由 `parts_maker` 生产的 `steel_part` 的 role 篡改为 `source_kind="external_boundary"`，保持 recipe 不变。该 context 通过 `validate_preprocess_context()`，随后 `solve_demands_exact()` 在 backprop 时把 `steel_part` 当作边界供应，跳过 `parts_maker` 及其上游。

原始快照 probe 输出：

```text
F-PRE-R16-01: ACCEPTED
  machine_count_sum 169
  parts_maker_present False
  steel_part_flow 6
  port_total 46
  generic_outputs {'blue_iron_ore': 22, 'source_ore': 18, 'steel_part': 6}
```

正常合法基线的 machine count sum 为 219；该 mutation 将 `steel_part` 变成 generic boundary output，导致 producer 机器消失。这是 fail-open undercount，不是单纯报错质量问题。

### 修法

补丁增加两道门：

1. canonical semantic validation：任一 recipe output 的 commodity 若 metadata 标为 `external_boundary`，拒绝。
2. direct `validate_preprocess_context()`：同样拒绝 producer 与 `external_boundary` 并存，覆盖 hand-built / mutated context。

回归：

- `src/tests/test_rules.py::test_semantic_external_boundary_source_must_not_have_recipe_producer`
- `src/tests/test_preprocess_context.py::test_preprocess_context_rejects_external_boundary_commodity_with_producer`

补丁后 probe 输出：

```text
F-PRE-R16-01: REJECTED ValueError external_boundary commodity 'steel_part' cannot also be produced by recipes: parts_maker
```

## Finding F-PRE-R16-02: raw cycle solver misses group-local role contract

Severity：HIGH

文件位置：

- 根因：`src/interchange/preprocess_context.py:495-540`。修复前 `_solve_cycle_group_exact()` 入口只重复 single-output、cycle-internal output ownership、I/O closure、RHS membership 和 non-negative solve，没有重复 full validation 在 `src/interchange/preprocess_context.py:326-356` 做的 requested group 本地 role contract。
- 补丁：`src/interchange/preprocess_context.py:436-467` 新增 `_validate_cycle_group_local_contract()`，并在 `src/interchange/preprocess_context.py:538-540` 进入矩阵构造前调用。

### 攻击过程

在原始快照上，把 `buckwheat` 的 commodity role 从 `buckwheat_cycle` 改成 `sandleaf_cycle`，但保留 `buckwheat_cycle.internal_commodities` 不变。full validation 正确拒绝，但 raw `solve_cycle_group_exact()` 仍直接求解并返回 recipe runs：

```text
F-PRE-R16-02 full validation: REJECTED ValueError cycle_internal commodity 'buckwheat' declares cycle_group 'sandleaf_cycle' but is not listed in that group's internal_commodities
F-PRE-R16-02 raw solve: ACCEPTED {'planter_buckwheat': Fraction(2, 1), 'seed_collector_buckwheat': Fraction(1, 1)}
```

这说明 raw public solver 入口仍可在 malformed context 上产生看似合法的 exact result，与 full validation 的 group-local contract 不对齐。R15 已经把 raw cycle solver 纳入 public bypass threat model，因此这里按 soundness finding 处理。

### 修法

在 raw cycle solver 入口重复 requested group 的本地 contract：

- group 必须 square；
- group recipes 必须存在；
- every `internal_commodity` 必须有 `commodity_roles` entry；
- every internal commodity 必须 `source_kind='cycle_internal'` 且 `role.cycle_group == group.group_id`；
- every net-export commodity 必须属于 internal set。

回归：

- `src/tests/test_preprocess_cycle_solver.py::test_cycle_solver_rejects_unvalidated_context_with_internal_role_group_mismatch`

补丁后 probe 输出：

```text
F-PRE-R16-02 full validation: REJECTED ValueError cycle_internal commodity 'buckwheat' declares cycle_group 'sandleaf_cycle' but is not listed in that group's internal_commodities
F-PRE-R16-02 raw solve: REJECTED ValueError commodity 'buckwheat' declares cycle_group 'sandleaf_cycle', expected 'buckwheat_cycle'
```

## Patch

Unified diff：`/mnt/data/F_PRE_R16_preprocess_soundness.patch`

变更文件：

- `PROJECT_LOCK.md`
- `specs/18_preprocess_context_contract.md`
- `src/interchange/preprocess_context.py`
- `src/rules/semantic_validator.py`
- `src/tests/test_preprocess_context.py`
- `src/tests/test_rules.py`
- `src/tests/test_preprocess_cycle_solver.py`

补丁已在 fresh extract 上验证可应用：

```text
patching file PROJECT_LOCK.md
patching file specs/18_preprocess_context_contract.md
patching file src/interchange/preprocess_context.py
patching file src/rules/semantic_validator.py
patching file src/tests/test_preprocess_context.py
patching file src/tests/test_rules.py
patching file src/tests/test_preprocess_cycle_solver.py
3 passed in 3.00s
```

## Verification

环境：Python 3.13；pytest 禁用 `pytest-randomly`，并在专项测试中禁用 `ddtrace/cov/json-report/metadata` 插件以避免沙盒 collection/插件干扰。

已跑命令与结果：

```bash
python3.13 -m pytest -q -p no:randomly -p no:ddtrace -p no:cov -p no:json-report -p no:metadata \
  src/tests/test_rules.py src/tests/test_preprocess_context.py src/tests/test_preprocess_cycle_solver.py \
  src/tests/test_demand.py src/tests/test_operation_profiles.py
# 67 passed in 3.50s
```

```bash
python3.13 -m pytest -q -p no:randomly -p no:ddtrace -p no:cov -p no:json-report -p no:metadata \
  src/tests/test_preprocess_golden.py::test_regenerated_instance_distribution_matches_machine_counts \
  src/tests/test_preprocess_golden.py::test_regenerated_preprocess_invariants_match_current_frozen_contract \
  src/tests/test_preprocess_golden.py::test_frozen_preprocess_artifacts_are_cleanly_serialized_without_binary_noise
# 3 passed in 2.95s
```

```bash
python3.13 scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

```bash
python3.13 -m ruff check PROJECT_LOCK.md specs/18_preprocess_context_contract.md \
  src/interchange/preprocess_context.py src/rules/semantic_validator.py src/tests/test_preprocess_context.py \
  src/tests/test_rules.py src/preprocess/demand_solver.py src/tests/test_preprocess_cycle_solver.py
# All checks passed!
```

```bash
python3.13 scripts/build_current_preprocess_context.py \
  --output /mnt/data/zmd_r16_work/tmp_outputs_after_patch2/current_preprocess_context.json \
  --diff-json /mnt/data/zmd_r16_work/tmp_outputs_after_patch2/diff.json \
  --diff-md /mnt/data/zmd_r16_work/tmp_outputs_after_patch2/diff.md
# {'all_match': True, 'matched_count': 6, 'total_count': 6, 'mandatory_exact_instance_count': 266, 'all_instance_count': 326, 'generic_output_slots': 52, 'generic_input_slots': 0}
```

未跑完整 `python -m pytest -q src/tests`。原因：包含 candidate placement 相关 golden regeneration，沙盒工具时限内会被拖住；用户本轮明确要求不要审 `candidate_placements.json` 外置再生。已覆盖本轮触达的 preprocess validation / demand / raw cycle / operation profile / selected frozen parity tests。
