# 终末地 IndustrialPlanner preprocess round 13 review

快照校验：`/mnt/data/zmd_snapshot_095a0b6d.zip` sha256 = `095a0b6d5f7d4496f3ef99fb71f2c6873555b10324c045b5b78ef91cc85f5eda`，与指定值一致。本轮只审该快照。

本轮结论：R12-01 本体修复确认有效；另在自由攻击角发现 1 个新的 preprocess soundness finding：`F-PRE-R13-01`，severity `HIGH`。已给出补丁与回归测试。

## Q1: F-PRE-R12-01 修复确认

### 1. 反向索引校验覆盖

确认有效。`build_preprocess_context_from_rules_and_plan()` 构造 `PreprocessContext` 后立即调用 `validate_preprocess_context()`；两个文件入口 `load_default_preprocess_context()` 与 `load_preprocess_context_from_paths()` 先做 strict JSON + schema，再进入同一个 builder。R12 的反向索引校验位于 `src/interchange/preprocess_context.py:273-304`：它为每个 group 建立 `cycle_group_internal_commodities`，然后要求每个 `source_kind == "cycle_internal"` 的 commodity 同时声明存在的 group，并出现在该 group 的 `internal_commodities` 中。非 cycle commodity 携带 `cycle_group` 也会 fail-closed。

全仓语义消费点穷举结果：生产链里只有 `src/preprocess/demand_solver.py:293-296` 根据 `role.cycle_group is not None` 把需求转给 cycle group；实际求解入口是 `src/preprocess/demand_solver.py:117-123` 调用 `solve_cycle_group_exact()`。直接 public 入口 `src/interchange/preprocess_context.py:433-438` 只转发到 `_solve_cycle_group_exact()`，而 `_solve_cycle_group_exact()` 自身也做 RHS membership 规范化，所以即使绕过 context builder 直接求解，正需求的非成员 key 不能再被静默丢弃。

Probe 结果：

```text
ghost_spore omitted from internal list at context boundary: REJECTED ValueError: cycle_internal commodity 'ghost_spore' declares cycle_group 'buckwheat_cycle' but is not listed in that group's internal_commodities
positive unknown RHS key: REJECTED ValueError: cycle group 'buckwheat_cycle' external demand commodity 'ghost_spore' is not listed in internal_commodities
positive internal but non-net-export RHS key: REJECTED ValueError: cycle group 'buckwheat_cycle' external demand commodity 'buckwheat_seed' is not declared in net_export_commodities
negative net-export RHS key: REJECTED ValueError: cycle group 'buckwheat_cycle' external demand for commodity 'buckwheat' must be non-negative: -1
explicit zero unknown RHS key: ACCEPTED 0
ghost_spore downstream demand through solve_demands_exact: REJECTED ValueError: cycle_internal commodity 'ghost_spore' declares cycle_group 'buckwheat_cycle' but is not listed in that group's internal_commodities
```

### 2. RHS 三分支边界

确认有效。`_solve_cycle_group_exact()` 在 `src/interchange/preprocess_context.py:450-475` 从同一个 `CycleGroup` 对象派生 `internal_commodities` 与 `net_export_commodities` 两个 set。正需求必须同时属于二者；负需求立即 `ValueError`；零需求在 `src/interchange/preprocess_context.py:461-462` 被接受后归一成缺省 0，不进入 `normalized_external_demands`。后续 RHS 是固定数值向量，不存在把零 key 当成自由变量或松弛变量的路径。

集合源也确认同源：R11-03 的非负证明在 `validate_preprocess_context()` 中对同一 `group.net_export_commodities` 逐个调用 `_solve_cycle_group_exact(context, group_id, {commodity_id: Fraction(1)})`，运行时 RHS membership 也读取同一 group 对象，没有第二套重算集合。

### 3. 实现边界

确认有效。空 group 在文件入口会被 schema 的 `minItems` 拒绝；dict-level builder 即使绕过 schema，空 group 也不能承载任何 `cycle_internal` commodity，因为反向成员检查会拒绝。单 commodity group 若矩阵奇异会被 `_solve_square_linear_system()` 拒绝；多 group 共享 commodity 会在 group 内部角色一致性检查处拒绝。实测：

```text
shared internal commodity across groups REJECTED ValueError commodity 'buckwheat' declares cycle_group 'buckwheat_cycle', expected 'evil_cycle'
duplicate internal commodity direct builder REJECTED ValueError cycle_internal commodity 'buckwheat_seed' declares cycle_group 'buckwheat_cycle' but is not listed in that group's internal_commodities
single commodity zero-output group REJECTED ValueError cycle group matrix is singular and cannot be solved exactly
```

### 4. 冻结工件侧

确认有效。`scripts/build_current_preprocess_context.py` 的再生对比对 `commodity_demands.json`、`machine_counts.json`、`port_budget.json`、`generic_io_requirements.json`、`mandatory_exact_instances.json`、`all_facility_instances.json` 均为 `matches_frozen=True`；summary 为 `all_match=True, matched_count=6/6, mandatory_exact_instance_count=266, all_instance_count=326`。`candidate_placements.json` sha256 仍为 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，size `45,773,799` bytes。

## Q2: R11 三修复轻确认

R11-03 保持完好：`validate_preprocess_context()` 仍要求每个 `net_export_commodity` 属于 `internal_commodities`，并对零 RHS 与每个 net-export 单位方向求解；`_solve_cycle_group_exact()` 仍在求解后拒绝任何负 run rate。R12 的 RHS 规范化没有削弱这个前提，反而限制正 RHS 只能落在已证明的 net-export 单位方向非负张成内。

R11-01 保持完好：`src/placement/placement_generator.py:474-481` 的 `load_templates()` 仍使用 strict JSON loader 并立刻校验 `canonical_rules.schema.json`。

R11-02 保持完好：`src/placement/placement_generator.py:182-188` 对 `rotatable` / `is_solid_z` 做 boolean 类型检查并要求所有模板 `is_solid_z=True`；各 port family 在 `src/placement/placement_generator.py:190-266` 仍钉死对应的 rotatable 与尺寸/半径/placement_rule 契约。

## Finding F-PRE-R13-01 — cycle group recipe I/O closure 未校验，外部输入可被 cycle solve 静默漏算

Severity: HIGH

位置：原始快照 `src/interchange/preprocess_context.py:319-346` 只校验 group 的 recipe 存在、internal commodity 角色一致、net-export 属于 internal，但没有校验 cycle group recipe 的全部 inputs/outputs 是否闭合在 `internal_commodities` 内。原始快照 `_solve_cycle_group_exact()` 在 `src/interchange/preprocess_context.py:477-486` 只按 `group.internal_commodities` 建矩阵/RHS；`src/preprocess/demand_solver.py:117-129` 在 cycle 求解后只把 recipe run rate 加入 machine_runs，不再回推这些 cycle recipe 的非 internal 输入/输出。因此，如果 canonical drift 让 cycle recipe 消耗 `source_ore`、`blue_iron_ore` 这类外部 commodity，该外部需求不会进入 `commodity_demands.json` / `port_budget.json` / `generic_io_requirements.json`。

复现 probe（原始快照）：

```python
import copy, json
from pathlib import Path
from fractions import Fraction
from src.interchange.preprocess_context import build_preprocess_context_from_rules_and_plan
from src.preprocess.demand_solver import solve_demands_exact, generate_port_budget

root = Path.cwd()
rules = json.loads((root / "rules/canonical_rules.json").read_text())
plan = json.loads((root / "rules/preprocess_plan.json").read_text())
mut = copy.deepcopy(rules)
mut["recipes"]["planter_buckwheat"]["inputs"]["source_ore"] = 1
ctx = build_preprocess_context_from_rules_and_plan(mut, plan)
flows, machines = solve_demands_exact(context=ctx)
print("source_ore flow:", flows.get("source_ore"))
print("planter_buckwheat runs:", machines.get("planter_buckwheat"))
print("expected extra source_ore from planter:", machines.get("planter_buckwheat") * Fraction(1, mut["recipes"]["planter_buckwheat"]["ticks_per_cycle"]))
print("port total:", generate_port_budget(flows, context=ctx)["miracle_52_budget"]["total_boundary_and_core_ports_required"])
```

原始输出：

```text
context accepted
source_ore flow: 18
planter_buckwheat runs: 11
expected extra source_ore from planter: 11
port total: 52
```

影响：这会让冻结工件声称 52-port budget 仍可行，但真实 cycle machines 额外消耗 11/tick `source_ore`。这是 fail-open，因为缺的是外部供料端口与 commodity demand，而不是保守过量计数。

修法：cycle group 必须是 recipe I/O 闭包。每个 group recipe 的 `inputs ∪ outputs` 必须全部属于该 group 的 `internal_commodities`；这个检查放在 context validation，并同步放在 `_solve_cycle_group_exact()` 入口，覆盖直接 public solver 调用的未验证 context。

补丁：`F-PRE-R13-01.patch`

回归：

- `test_preprocess_context_rejects_cycle_recipe_io_outside_group_internal_commodities`
- `test_cycle_solver_rejects_unvalidated_context_with_cycle_recipe_io_outside_internal`

补丁后 probe：

```text
ValueError cycle group 'buckwheat_cycle' recipes must reference only commodities listed in internal_commodities; outside commodities: planter_buckwheat: source_ore
```

## 自验记录

通过：

```text
python3.13 -m pytest -q src/tests/test_preprocess_context.py src/tests/test_preprocess_cycle_solver.py -p no:randomly
23 passed in 2.00s

python3.13 -m pytest -q \
  src/tests/test_preprocess_context.py \
  src/tests/test_preprocess_cycle_solver.py \
  src/tests/test_demand.py \
  src/tests/test_preprocess_plan_schema.py \
  src/tests/test_placements.py \
  src/tests/test_rules.py \
  src/tests/test_p1_2_proof_obligations.py \
  -p no:randomly
79 passed in 11.38s

python3.13 scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored
```

冻结对比：

```text
all_match=True, matched_count=6/6
commodity_demands.json True
machine_counts.json True
port_budget.json True
generic_io_requirements.json True
mandatory_exact_instances.json True
all_facility_instances.json True
candidate_placements.json sha256 adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0, size 45773799
```

未完成：全量 `python3.13 -m pytest -q src/tests -p no:randomly` 曾尝试运行，但在沙盒 300s 命令限额内未完成；没有把它作为通过证据。
