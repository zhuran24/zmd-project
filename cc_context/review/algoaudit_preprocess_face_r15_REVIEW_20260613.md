# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 15 审查报告

## 0. 快照与范围

- 指定快照：`/mnt/data/zmd_snapshot_eca69648.zip`
- sha256：`eca696483abee31138cdbdcc3cf67a8912f5e13f3b5291821cab67fffbae1302`
- 校验结论：匹配，已只解此包。
- 审查范围：preprocess 链，重点为 F-PRE-R14-01 / F-PRE-R14-02 修复确认与自由攻击角。
- 本轮结论：**非零 soundness finding**。发现并修复 1 个 HIGH：`F-PRE-R15-01`。R14 标准加载链本身成立，但 public solver / raw cycle solver 的直接上下文入口缺少重验，能让 R14 两类 invalid context 绕过 validation 后重新进入 demand backprop。

## 1. Finding

### F-PRE-R15-01 — HIGH — direct `PreprocessContext` replay 绕过 R14 fail-closed 前提

**位置**

- 原漏洞入口：`src/preprocess/demand_solver.py:104-115`。`solve_demands_exact(context=...)` 直接使用传入的 `PreprocessContext` 计算 target 与 backprop，未调用 `validate_preprocess_context()`。
- 原时序缝：`src/preprocess/demand_solver.py:293-296`。正需求遇到 `role.cycle_group is not None` 时先转给 cycle solver 并 `continue`，发生在非 cycle producer 反向索引查询之前。
- 原 raw cycle solver 入口：`src/interchange/preprocess_context.py:464-475`。`_solve_cycle_group_exact()` 只重复 R13 的 recipe I/O closure，没有重复 R14-02 的 cycle-internal output ownership。
- 修复后入口：`src/preprocess/demand_solver.py:31-37,105-114`；`src/interchange/preprocess_context.py:387-428,490-500`。
- 回归：`src/tests/test_preprocess_context.py:319-350`；`src/tests/test_preprocess_cycle_solver.py:53-64`。
- 锁与规格：`PROJECT_LOCK.md:114`；`specs/18_preprocess_context_contract.md:44`。

**问题本体**

R14-01 / R14-02 在标准文件加载链上是封住的：schema、semantic validator、`validate_preprocess_context()` 都会拒绝非法数据。但项目里 `PreprocessContext` 同时是 public regeneration API 的入参，`solve_demands()` / `solve_demands_exact()` 接受 caller 传入的 context。调用方若通过 deep-copy、测试构造、overlay 后篡改等方式得到一个未重验 context，就能绕过 R14 的三道门。

这不是“私有函数随便乱调”的问题：`solve_demands(context=...)` 与 `solve_demands_exact(context=...)` 是对外再生工件用的入口。fail-closed 姿态下，public solver 不能信任入参已经经过 builder validation。

**Probe A：R14-01 多输出 co-product 重复计数复活**

```python
import copy
from fractions import Fraction
from src.interchange.preprocess_context import CommodityRole, ProductionTarget, load_default_preprocess_context
from src.preprocess.demand_solver import solve_demands_exact, generate_ceil_machine_counts

ctx = copy.deepcopy(load_default_preprocess_context())
ctx.recipes["packaging_battery"].outputs["bonus_battery"] = Fraction(1)
ctx.targets["bonus_battery"] = ProductionTarget(
    commodity_id="bonus_battery",
    mode="equivalent_full_speed_lines",
    value=Fraction(1),
    final_recipe_id="packaging_battery",
)
ctx.commodity_roles["bonus_battery"] = CommodityRole(
    commodity_id="bonus_battery",
    source_kind="internal_only",
    sink_kind="generic_input",
    cycle_group=None,
)
flows, machines = solve_demands_exact(context=ctx)
print(machines["packaging_battery"], generate_ceil_machine_counts(machines)["packaging_battery"])
```

修复前结果：solver 接受该非法 context，`packaging_battery` 被双输出需求重复 charge，ceil 从原基线 3 漂到 4。方向是 false-INFEASIBLE 风险。

修复后结果：`solve_demands_exact()` 在 target/backprop 前调用 `validate_preprocess_context()`，抛出 `preprocess recipe 'packaging_battery' must provide exactly one output commodity`。

**Probe B：R14-02 cycle-internal 组外 producer 漏算复活**

```python
import copy
from fractions import Fraction
from src.interchange.preprocess_context import PreprocessRecipe, load_default_preprocess_context, solve_cycle_group_exact
from src.preprocess.demand_solver import solve_demands_exact

ctx = copy.deepcopy(load_default_preprocess_context())
ctx.recipes["synthetic_buckwheat"] = PreprocessRecipe(
    recipe_id="synthetic_buckwheat",
    template="manufacturing_3x3",
    ticks_per_cycle=1,
    inputs={"source_ore": Fraction(1)},
    outputs={"buckwheat": Fraction(1)},
)
print(solve_cycle_group_exact(ctx, "buckwheat_cycle", {"buckwheat": Fraction(1)}))
flows, machines = solve_demands_exact(context=ctx)
print(machines.get("synthetic_buckwheat"), flows.get("source_ore"))
```

修复前结果：raw cycle solver 接受 outsider producer，并只返回 cycle 内 recipe run；public demand solver 也接受非法 context。`synthetic_buckwheat` 机器没有被纳入，`source_ore` 输入没有按这个 producer 的生产链计入。方向是 false-FEASIBLE / undercount 风险。

修复后结果：

- `solve_demands_exact(context=ctx)` 先整体重验 context，拒绝 `synthetic_buckwheat`。
- `solve_cycle_group_exact(ctx, "buckwheat_cycle", ...)` 在 raw cycle 入口重复 cycle-internal output ownership guard，也拒绝 `synthetic_buckwheat`。

**修法**

1. `solve_demands_exact()` 在解析 context 后立刻调用 `validate_preprocess_context(resolved_context)`，位置早于 `_target_rate_per_tick()` 和 `_backpropagate_non_cycle_demands()`。
2. 将 R14-01 单输出校验抽成 `_validate_single_output_recipes()`，供 full context validation 与 direct cycle solver 共享。
3. 将 R14-02 cycle-internal output ownership 抽成 `_validate_cycle_internal_output_ownership()`，full validation 全量调用，raw cycle solver 以 `group_ids={group_id}` 精确兜底。
4. 补充三条回归：public solver 拒绝 direct 多输出 context、public solver 拒绝 direct outsider cycle-internal producer、raw cycle solver 拒绝 direct outsider cycle-internal producer。
5. 记录 lock/spec：F-PRE-R15-01。

Unified diff 见同目录 `F-PRE-R15-01.patch`。

## 2. Q1 — F-PRE-R14-01 修复确认

### 2.1 三处 fail-closed 覆盖

标准 canonical 加载链确认 sound：

- schema 层：`rules/canonical_rules.schema.json:378-389`，`outputs` 有 `minProperties:1` + `maxProperties:1`。
- semantic validator：`src/rules/semantic_validator.py:100-109`，多输出 recipe 报错。
- context validation：`src/interchange/preprocess_context.py:240-252` 调用 `_validate_single_output_recipes()`；helper 在 `src/interchange/preprocess_context.py:387-405` 对 `len(outputs) != 1` fail-closed。

本轮发现的缺口不是这三道门本身，而是 public solver 接受外部传入 `PreprocessContext` 后没有强制重走第三道门。补丁后 `src/preprocess/demand_solver.py:105-114` 把入口补上，`solve_demands()` 因调用 `solve_demands_exact()` 同步覆盖。因此“多输出 recipe 进入 demand backprop”的 public 入口已封住。

### 2.2 单输出语义是否正当

当前 canonical 数据是单输出：`rules/canonical_rules.json` 共 17 个 recipe，全部 1 output。

上游 vendored snapshot 独立检查结果：`third_party_snapshots/endfield_calc/upstream_materialized_snapshot/recipes.json` 共 172 个 recipe，其中 131 个单输出、38 个双输出、3 个零输出；字段集合只有 `id / inputs / outputs / facilityId / craftingTime`。双输出样例是 dismantler 类 recipe，例如 `dismantler_copper_grass_1_1` 同时产出 `item_copper_bottle` 与 `item_liquid_plant_grass_1`。

因此不能说“终末地机制不存在 co-product”。更准确的结论是：**当前 solver/canonical 子集不支持 co-product，单输出锁是正确的 unsupported-mode fail-closed 声明**。若未来要纳入上游 dismantler 类双输出 recipe，就必须把 demand backprop 从“按 commodity 找唯一 producer 并逐项 charge”改成“recipe-flow 级的耦合求解”，否则机器 run 共享关系会被算错。

### 2.3 单输出下 run 计数口径

单输出前提成立时，`_backpropagate_non_cycle_demands()` 的计数口径是 sound 的：每个正需求 commodity 只会通过唯一 producer 反向展开，`run_rate = demand / output_rate`，然后把该 recipe 的 input 需求入队。若多个 downstream consumer 需要同一 commodity，需求先在 `flows[commodity_id] += demand_rate` 和 pending 队列中累加式传播，不存在 co-product 那种“同一 operation 被多个输出重复 charge”的共享 run 问题。

也就是说，R14-01 的数学修复方向正确；本轮补丁只是把这个前提从“标准加载链成立”提升到“public demand solver 入口也强制成立”。

## 3. Q2 — F-PRE-R14-02 修复确认

### 3.1 校验方向与集合同源

R14-02 标准 context validation 使用的两类集合与实际传播路径同源：

- cycle-internal commodity 的归属来自 `context.commodity_roles[*].cycle_group`，并在 `src/interchange/preprocess_context.py:293-304` 验证它必须在对应 `cycle_group.internal_commodities` 内。
- group 内 recipe 集来自 `context.cycle_groups[group_id].recipes`。
- producer ownership guard 在 `src/interchange/preprocess_context.py:408-428` 遍历所有 recipe outputs：只要输出 commodity 的 role 声明了 `cycle_group`，该 recipe 必须属于对应 group recipes。

反方向由 R13 closure 继续管：`src/interchange/preprocess_context.py:321-332` 对每个 cycle group 调 `_cycle_group_recipe_io_outside_internal()`，确保组内 recipe 的 inputs/outputs 不越出 `internal_commodities`。两者一个管“组外 recipe 不许产 cycle-internal commodity”，一个管“组内 recipe I/O 不许引用组外 commodity”，没有重叠盲区。

### 3.2 双端覆盖

修复前只有 context validation 端覆盖，raw `_solve_cycle_group_exact()` 直调端缺 R14-02 guard。这就是本轮 finding 的一半。

补丁后 raw cycle solver 在 `src/interchange/preprocess_context.py:490-500` 先取 group，再调用：

- `_validate_single_output_recipes(context, recipe_ids=group.recipes)`
- `_validate_cycle_internal_output_ownership(context, group_ids={group_id})`

所以直接解某个 cycle group 时，针对这个 group 的 cycle-internal producer ownership 已兜底；配合原有 R13 closure 检查，cycle solver 的两端入口现在对齐。

### 3.3 时序彻底性

`_backpropagate_non_cycle_demands()` 内部时序仍然是“cycle_group 正需求先进入 cycle solver，再跳过 non-cycle producer 查询”（`src/preprocess/demand_solver.py:293-298`）。这条时序本身是设计语义：cycle-internal commodity 由 cycle solver 供给。

真正需要关闭的是“进入这条时序前，是否已经证明没有 outsider producer”。补丁后 `solve_demands_exact()` 在 `src/preprocess/demand_solver.py:105-114` 于 target-rate 与 backprop 前全量重验 context，确保 R14-02 ownership 已成立；raw cycle solver 也在自身入口重复 group-local guard。因此 fail-open 缝已前移关闭，而不是只在旁路上贴一个检查。

## 4. Q3 — R12 / R13 / R11 轻确认

- R12 RHS membership：`_solve_cycle_group_exact()` 仍在归一化 external demands 时拒绝不在 `internal_commodities` 或不在 `net_export_commodities` 的正需求；本轮新增 guard 位于其前，不放宽 RHS membership。
- R13 recipe I/O closure：full validation 仍在 `src/interchange/preprocess_context.py:321-332` 调 closure；raw cycle solver 仍在 `src/interchange/preprocess_context.py:502-504` 调 closure。本轮只是把 R14 guard 抽 helper，没有删除 R13 检查。
- R11 非负/精确前提：`solve_cycle_group_exact()` 对 negative external demand 仍 fail-closed；demand propagation 仍忽略非正 pending demand，target validation 仍要求 target value > 0。本轮补丁不改变 exact Fraction 求解与 artifact number normalization。

## 5. Q4 — 自由攻击角

### 5.1 选点一：public direct-context replay

选择理由：前几轮已经把 schema、canonical semantic、builder validation 打得很厚，但 preprocess 再生链同时暴露 `solve_demands(context=...)` 这类“已经构造好的 context”入口。若 fail-closed 只在 loader 上，攻击者或后续维护代码可以在 loader 后改对象，像从正门过安检后把危险品从后门递进来。

攻击结果：成立，即 F-PRE-R15-01。补丁已封 public solver 与 raw cycle solver 的相关入口。

### 5.2 选点二：多输出锁之后是否还有第三种 commodity 引用形态

检查上游 materialized recipes 字段集合为 `id / inputs / outputs / facilityId / craftingTime`，没有发现单独的 byproduct、catalyst、utility、side-input 之类 commodity-bearing 字段。当前 canonical `rules/canonical_rules.json` 也只在 recipes 的 `inputs/outputs`、commodity metadata、targets、preprocess plan 的 cycle groups/utility operations 中引用 commodity。

utility operations 路径轻扫后未发现新的 demand 生产/消费语义：它们在 preprocess context 中是 facility/slot 级声明，不参与 `_backpropagate_non_cycle_demands()` 的 producer ownership 或 machine-run 计算。因此本角度没有追加 soundness finding。需要注意的是，上游确实存在双输出 recipe；未来若把 dismantler 类 recipe 纳入 canonical，不能靠字段扫描继续假设单输出，而应升级 recipe-flow solve。

## 6. 实证与回归

已执行：

```bash
python -m pytest -q src/tests/test_preprocess_context.py src/tests/test_preprocess_cycle_solver.py src/tests/test_demand.py src/tests/test_rules.py -p no:randomly
# 59 passed in 0.66s

python -m pytest -q \
  src/tests/test_preprocess_context.py \
  src/tests/test_preprocess_cycle_solver.py \
  src/tests/test_demand.py \
  src/tests/test_preprocess_plan_schema.py \
  src/tests/test_preprocess_golden.py -k 'not chain_regenerates' \
  src/tests/test_rules.py \
  src/tests/test_operation_profiles.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/test_placements.py \
  src/tests/test_preprocess_candidate_geometry_contract.py \
  -p no:randomly
# 99 passed, 1 deselected in 26.00s

python -m ruff check \
  src/interchange/preprocess_context.py \
  src/preprocess/demand_solver.py \
  src/tests/test_preprocess_context.py \
  src/tests/test_preprocess_cycle_solver.py
# All checks passed!

python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
```

工件一致性：

```bash
python scripts/build_current_preprocess_context.py \
  --output /mnt/data/zmd_r15_work/current_preprocess_context.json \
  --diff-json /mnt/data/zmd_r15_work/preprocess_context_diff_report.json \
  --diff-md /mnt/data/zmd_r15_work/preprocess_context_diff_report.md
```

结果：`all_match: true`，6/6 frozen preprocess artifacts 匹配；`mandatory_exact_instance_count=266`，`all_instance_count=326`，`generic_output_slots=52`，`generic_input_slots=0`。

candidate placements 未再生，只校验现有文件：`data/preprocessed/candidate_placements.json` sha256 为 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`，size `45,773,799` bytes，匹配题面基线。

未完成声明：尝试跑全量 `python -m pytest -q src/tests -p no:randomly`，600 秒超时，停在约 6% 进度；因此本报告不声称全量 3033+ 测试已跑完。

## 7. 交付文件

- `REVIEW.md`：本报告。
- `F-PRE-R15-01.patch`：修复补丁与回归测试。
