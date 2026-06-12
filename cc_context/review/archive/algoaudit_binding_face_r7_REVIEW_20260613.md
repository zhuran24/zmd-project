# 终末地 IndustrialPlanner binding 建模忠实度 round 7 审查报告

审查对象：`zmd_snapshot_70457b5e.zip`

快照校验：通过。

```text
70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a  zmd_snapshot_70457b5e.zip
```

运行环境：Python 3.13.5，OR-Tools 9.15.6755，依赖从 `zmd_py313_linux_x86_64.zip` 离线安装。

## 结论

**本轮零 soundness finding。**

没有发现当前快照在 binding 侧会造成 false-FEASIBLE 或 false-INFEASIBLE 的建模忠实度缺陷。没有生产代码修改，因此本轮无 unified diff、无补丁包。

本轮新增的主要证据不是沿着 r6 的“selection/nogood 对称枚举”重复确认，而是两条独立切面：

1. 先从 `specs/03_*`、`specs/04_*`、`specs/05_*` 与 `rules/canonical_rules.json` 推导 binding 期望语义，再逐条对照 `src/models/binding_subproblem.py`、`src/models/port_binding.py` 与相关消费点。
2. 对 routing-free/generic I/O 边界做 binding 侧纵深，包括当前数据链路一致性、未来 `source_kind=external_boundary` 与 `sink_kind=generic_input` 重叠扩展时的具体 owner-gate 风险点、以及虚拟 wireless 槽与物理 generic 槽的隔离性。

## Finding 列表

| severity | file:line | 结论 | probe 或论证 | 修法 |
|---|---:|---|---|---|
| N/A | N/A | 无当前 soundness finding | 见下方 Q1/Q2/Q3 对照与 probe | 无生产代码修改 |

## Q1 规则文本到实现的独立对照

我先从规则文本推导出 binding 应满足的语义，再检查实现是否更严、更松或缺失。结论是：当前 certified exact 数据与 binding 编码一致；没有发现实现比规则更严而排除合法配置，也没有发现实现比规则更松而接受规则禁止配置。唯一需要特别标注的是 overload separation：它没有 canonical 硬规则依据，是 env-gated heuristic；默认不启用，且 controller 有 env-off retry，不能作为 certified 不可行证明直接落锤。

| 规则语义 | 规则依据 | 实现位置 | 对照结论 |
|---|---|---|---|
| 端口分入口/出口；空置端口合法；同侧端口同质，不存在编号绑定物料 | `specs/03_rule_canonicalization.md:51-61`, `213-219`, `264-267` | `src/preprocess/operation_profiles.py:32-55`, `src/models/port_binding.py:143-179`, `src/models/binding_subproblem.py:647-702` | fixed operation domain 只选择满足吞吐槽数的若干端口，未选端口不 materialize，等价于合法空置。每个 commodity 只按 required slot 数组合选择，不绑定端口编号。未发现 false-INFEASIBLE 或 false-FEASIBLE。 |
| 6×4 机器输入/输出必须在两条平行长边；3×3/5×5 允许任意一对平行边作为输入/输出 | `specs/03_rule_canonicalization.md:221-239`, `rules/canonical_rules.json:38-68` | `src/placement/placement_generator.py:129-180`, binding 消费 `pose.input_port_cells`/`pose.output_port_cells` 于 `src/models/port_binding.py:51-68` | 侧别几何由 candidate pose 生成，binding 不重新学习几何，而是在给定 pose 上只做 commodity-to-port-cell 组合。对 binding 面而言没有遗漏的 CP-SAT 约束；几何正确性属 placement generator 面。 |
| 协议核心 6 个 output、14 个 input，均可空置；边界口单逻辑口且朝场内供料 | `specs/03_rule_canonicalization.md:250-262`, `rules/canonical_rules.json:69-80`, `104-113` | core/boundary pose 生成在 `src/placement/placement_generator.py:183-226`, `264-289`；generic output binding 在 `src/models/binding_subproblem.py:709-748` | core 与 boundary 的物理可见输出槽进入 generic output 池；未使用通过 `__unused__` 表达。当前 52=52 由精确计数逼满，不是 domain 结构性禁止空置。 |
| 单端口容量为 1 item/tick，配方速率需向上取整为整数槽数 | `specs/03_rule_canonicalization.md:273-282`, `specs/04_recipe_and_demand_expansion.md:22-30`, `rules/canonical_rules.json:15-18` | `src/preprocess/operation_profiles.py:32-55` | `input_slots`/`output_slots` 由 rate/capacity ceil 得出。probe 对全部 18 个 non-generic operation profile 的首个 pose 做了域枚举计数校验，所有 domain 的 input/output commodity 计数均等于 profile slot count。 |
| 全局资源池，不允许把外部源口或中间产物硬绑定到产线编号 | `specs/03_rule_canonicalization.md:541`, `565-567` | `src/models/binding_subproblem.py:709-748`, `796-820` | generic output slot domain 为所有 required external commodities 加 `__unused__`，全局精确计数只约束商品出现次数，不限定某实例供给某产线。满足 pooling。 |
| generic output 每槽 ExactlyOne；真实商品精确出现次数；`__unused__` 是内部哨兵且需求工件不得使用 | `specs/04_recipe_and_demand_expansion.md:120-133`, `specs/05_facility_instance_definition.md:107`, `data/preprocessed/generic_io_requirements.json:11-18` | loader 校验 `src/models/binding_subproblem.py:222-246`; output slot ExactlyOne `709-748`; exact count `809-820`; extract skip `1055-1061` | 与规则一致。`__unused__` 只在 binding 内部存在，精确计数决定当前无空槽，未来 R<S 时不会误判合法空置为 INFEASIBLE。 |
| wireless sink 是 3 个虚拟 generic input 槽；参与 binding 计数，但无坐标、无方向、不经 routing front filter、不进 port_specs | `specs/05_facility_instance_definition.md:101-107`, `rules/canonical_rules.json:83-92`, `rules/preprocess_plan.json:51-55` | `src/models/binding_subproblem.py:750-795`, `1037-1043` | 实现只为 `wireless_sink` 生成虚拟 slot，slot dict 不含 `x/y/dir`，并带 `routing_free=True`, `virtual=True`。`extract_port_specs()` 在访问坐标前跳过这些槽。probe 确认所有虚拟槽无坐标且无协议箱 port spec 输出。 |
| routing-free final products 没有 routing sink，因此生产设施实体输出口以及该 commodity 的 generic-output 口必须从 routing-visible port specs 排除；原料 input 口保留 | `specs/05_facility_instance_definition.md:109`, `rules/canonical_rules.json:305-374` | routing-free set `src/models/binding_subproblem.py:369-373`; fixed output skip `1021-1025`; generic output skip `1060-1061`; fixed-domain RAB skip `563-605` | 当前 canonical 只有 `valley_battery`、`qiaoyu_capsule` 是 `sink_kind=generic_input`，且都是 `source_kind=internal_only`。实现与规则同向：只排除 routing-free 商品的 output terminal，不排除生产设施 input terminal。 |
| generic I/O 需求从 canonical 角色生成，output 必须是 external boundary，input 必须是 generic input | `src/preprocess/demand_solver.py:182-192`, `rules/canonical_rules.json:305-374`, `data/preprocessed/generic_io_requirements.json:11-18` | binding loader role check `src/models/binding_subproblem.py:249-305`；strict 装载入口 `57-200` | 当前 artifact 的 `required_generic_outputs={blue_iron_ore:34, source_ore:18}`，`required_generic_inputs={qiaoyu_capsule:1, valley_battery:1}`，交集为空。默认 loader 校验 output/source 与 input/sink 角色，未发现当前数据下缺失约束。 |
| 端口侧别和商品方向：机器 input port 是 routing sink，机器 output port 是 routing source；边界供料口算 output | 端口定义见 `specs/03_rule_canonicalization.md:51-52`，边界供料语义见 `specs/05_facility_instance_definition.md:57-63` | binding type 输出 `src/models/binding_subproblem.py:1018-1034`, `1062-1071`; routing 消费 `src/models/routing_subproblem.py:424-465`, `1199-1221`; boundary generator `src/placement/placement_generator.py:264-289` | polarity 一致。`extract_port_specs()` 将 input side 标成 `type="in"`，routing 将非 `out` 视为 sink；output side 标成 `type="out"`，routing 视为 source。边界口端口在 generator 中进入 `output_port_cells`，符合“对场内供料”。 |
| overload separation | 未找到 canonical hard rule；注释也写明是 env-gated heuristic/player consensus | 注入点 `src/models/binding_subproblem.py:456-480`, `_add_storage_box_overload_nogoods()` `499-554`; controller retry `src/search/benders_loop.py:5121-5170`, `5970-6016` | 默认 OFF。若强行开启，它确实比规则更严；但 certified controller 在 INFEASIBLE 且实际注入 nogood 时重建 env-off binding 并重解，TIMEOUT 时返回 UNKNOWN，不把 heuristic INFEASIBLE 当证明。因此不是当前 proof-surface soundness finding。 |

## Q1 是否存在规则有而 binding 未编码的约束

本轮范围内没有发现静默缺失。

需要分清两层：side geometry 规则，例如 6×4 long sides、3×3/5×5 opposite sides、protocol core 固定口位，不是在 binding CP-SAT 里二次编码，而是在 `candidate_placements.json` 的 pose 生成阶段 materialize 成 `input_port_cells`/`output_port_cells`。binding 的职责是对 master 已选 pose 上的端口 cell 做 commodity 分配、计数和 routing-visible terminal 提取。按这个边界检查，没有发现 binding 应该补但未补的规则约束。

## Q2 routing-free / generic I/O 边界判读

当前 routing-free 集合的生产链路和消费链路如下：

`canonical_rules.json commodity_metadata` → `src/preprocess/demand_solver.py:182-192` 生成 `generic_io_requirements.json` → master/session 读取同一 snapshot → `PortBindingModel` 使用传入的 normalized 需求或 strict loader → `routing_free_sink_commodities = positive required_generic_inputs`。

实际消费点包括：

- binding 内：`src/models/binding_subproblem.py:369-373`, `563-605`, `1007-1073`。
- Benders L2/dynamic separator 入口：`src/search/benders_loop.py:4565-4666`。
- separator/abstract classification：`src/models/separator_capacity_hull.py:129-155`, `src/models/abstract_routing_layer.py:123-142`。
- deletion-core oracle：`src/search/routing_deletion_core_minimizer.py:41-49`，它只消费当轮 `extract_port_specs()` 的 visible terminal，不从 raw pose geometry 复活 routing-free terminal。

### Q2 三类判读表

| 检查点 | 当前是否错 | 若未来引入 external_boundary ∩ generic_input 重叠 | 判读 |
|---|---|---|---|
| 当前 canonical/data 是否存在重叠角色 | 不错。probe 确认 `required_generic_outputs ∩ required_generic_inputs = ∅`，且 canonical 中没有 `source_kind=external_boundary` 且 `sink_kind=generic_input` 的商品。 | N/A | 当前 sound。证据：`rules/canonical_rules.json:305-374`, `data/preprocessed/generic_io_requirements.json:11-18`。 |
| `routing_free_sink_commodities` 的集合来源是否同步 | 不错。binding 和 Benders 相邻消费者均从 positive `required_generic_inputs` 得到集合。 | 若 future overlap 仍按商品级集合表达，则“这个商品的 output source 是否 routing-free”会失去角色维度。 | 须挂 owner-gate 扩展守卫。当前没有第二个消费点使用不同集合。 |
| 固定生产设施 output 过滤 | 不错。当前 routing-free 商品只可能是内部终品 output，且没有 recipe input consumer；过滤 output terminal 正是 spec 要求。 | 若某商品既是 external source 又是 wireless final sink，商品级过滤会把它所有 output terminal 都当 routing-free，而不是按 role 区分 source/sink。 | 重叠出现才错。具体点：`src/models/binding_subproblem.py:1021-1025`。 |
| generic output slot 的 assignment 与 extraction | 不错。当前 generic output 商品只有 `source_ore`、`blue_iron_ore`，都不是 routing-free。 | 人工 probe 构造 `required_generic_outputs={dual:1}` 且 `required_generic_inputs={dual:1}` 时，binding 可同时给物理 output 槽和 wireless input 槽分配 `dual`，但 `extract_port_specs()` 返回空列表，因为 generic output 被 routing-free 过滤。 | 重叠出现才错。具体点：`src/models/binding_subproblem.py:1055-1061`。需要 disjoint guard 或 per-role routing-free 分类。 |
| RAB 对 generic output front 的 build-time 过滤 | 不错。当前所有 generic output 都是 routed external source，先做 front-free 过滤与后续 port_specs 保持一致。 | 人工 probe 中若把物理 output 槽 front block，`_build_generic_output_domains()` 会先删掉该槽，exact output count 随后使模型 INFEASIBLE；但无 routing_context 时同一 overlap assignment 会被 `extract_port_specs()` 整体跳过。这个差异证明 future overlap 下 build-time RAB 与 extraction 会语义分叉。 | 重叠出现才错。具体点：`src/models/binding_subproblem.py:728-731` 与 `1055-1061`。这是 owner-gate 扩展守卫应钉住的最具体 binding 点。 |
| required_generic_outputs 与 required_generic_inputs 同商品时计数是否互相污染 | 不错。当前无重叠。 | 即使未来重叠，计数约束仍是两套变量族：output 只数 `generic_output_vars`，input 只数 `generic_input_vars`。不会把同一物理槽重复计数。 | 永远不错，按当前数据结构论证。证据：`src/models/binding_subproblem.py:796-820`。 |
| 同一物理槽是否会被 output/input 两边复用 | 不错。current disjoint。 | `wireless_sink` input slot 是 virtual generic-input family；physical generic-output slot 只来自 `boundary_io`/`protocol_core`。两者不是同一 slot，也不是同一 instance role。 | 永远不错，按当前 family 隔离论证。证据：`src/models/binding_subproblem.py:709-795`。 |
| selection 提取是否因同商品两角色而歧义 | 不错。current disjoint。 | 即使同名 commodity 同时出现，selection key space 仍分 `generic_outputs` 与 `generic_inputs`，不会把 source assignment 与 sink assignment 合并。 | 永远不错。证据：`src/models/binding_subproblem.py:972-1005`。 |
| wireless sink 虚拟槽是否可能进入 port_specs | 不错。 | 即使 commodity overlap，virtual generic input slot 仍在 `slot.get("routing_free") or slot.get("virtual")` 分支被跳过，且 slot 本身没有坐标。 | 永远不错。证据：`src/models/binding_subproblem.py:780-787`, `1037-1043`。 |

### Q2 owner-gate 建议，非当前 finding

如果未来 owner 明确允许某商品同时 `source_kind=external_boundary` 与 `sink_kind=generic_input`，需要先选一种语义：

- 禁止重叠：在 canonical validator、preprocess context validator、generic I/O loader 或 master snapshot 层 fail-closed 拒绝 `required_generic_outputs.keys() ∩ required_generic_inputs.keys()`。
- 允许重叠：把 `routing_free_sink_commodities` 从“商品级集合”升级为“role-aware terminal policy”，并修 `src/models/binding_subproblem.py:728-731`, `1021-1025`, `1055-1061` 以及 separator/abstract classification 的商品侧过滤。

这不是当前 snapshot bug，因为当前 canonical 与 generated artifacts 明确 disjoint；probe 只用于证明未来扩展边界在哪里裂开。

## Q3 selection/nogood 表示完备性抽查

本轮重新列出 binding CP-SAT 的自由度：

1. fixed operation pose-level binding choice：`self.binding_vars[instance_id][idx]`，当 domain 数大于 1 时 `AddExactlyOne`；当 domain 数等于 1 时记录为 `fixed_binding_choice`，没有 BoolVar。
2. generic input slot commodity choice：`self.generic_input_vars[slot_id][commodity]`，包含 `__unused__`，每槽 `AddExactlyOne`。
3. generic output slot commodity choice：`self.generic_output_vars[slot_id][commodity]`，包含 `__unused__`，每槽 `AddExactlyOne`。
4. RAB 过滤、search guidance、conflict summary 不引入新的 CP-SAT semantic decision variable。overload separation 使用已有 generic input slot variables 加约束，不引入未 selection 的新选择变量。

`extract_selection()` 覆盖上述所有自由度：

- fixed choice 常量进 `selection["binding_choice"]`：`src/models/binding_subproblem.py:982-984`。
- variable binding choice 进同一 map：`985-989`。
- 每个 generic input slot 的选中 commodity 进 `selection["generic_inputs"]`：`991-996`。
- 每个 generic output slot 的选中 commodity 进 `selection["generic_outputs"]`：`998-1003`。

`add_nogood_cut()` 只对存在 BoolVar 的部分加 literal：`src/models/binding_subproblem.py:1090-1106`。固定常量省略是安全的，因为它们在同一 model 中没有替代取值；若一个 model 只有固定常量而没有任何 BoolVar，函数不会添加空 nogood，这不会误排任何尚未证伪的 alternative。若存在 generic slot 或多域 binding choice，nogood 覆盖每个 slot 的实际 commodity，两个不同解不会因未记录某个 slot 的 `__unused__` 而折叠成同一 selection。

overload retry 场景也没有打破这个论证。controller 在 overload heuristic 造成 INFEASIBLE 可能性时重建 env-off model，并在 FEASIBLE/INFEASIBLE 分支把 `binding_model` 换成 retry model：`src/search/benders_loop.py:5121-5170`, `5970-6016`。因此后续 selection/nogood 来自实际被继续使用的 retry model，而不是来自 heuristic-on 的过期 fixed 集。固定/常量不进入 nogood literal 的省略仍然局限在“本 model 中无自由度”的事实内。

## Probe 与回归

本轮新增审查 probe：`cc_context/review/algoaudit_binding_face_r7_probe.py`。该 probe 做四件事：

1. 校验当前 canonical/generated generic I/O 没有 output/input 交集，也没有 external_boundary+generic_input 角色重叠。
2. 对所有 18 个 non-generic operation profile 的首个 pose 枚举 binding domain，校验每个 domain 的 commodity count 等于 profile slot count，最大 domain count 为 540。
3. 构造含 fixed operation、generic output、wireless generic input 的小模型，确认 `extract_selection()` 覆盖 binding choice、全部 generic input slots、全部 generic output slots，并确认 nogood 后可得到不同 selection。
4. 构造人工 dual-role overlap：无 routing_context 时同一 commodity 可同时占一个物理 generic output 与一个 virtual generic input，但 port_specs 为空；加入阻塞 front 的 routing_context 后 generic output slot 被 RAB 先删掉并导致 INFEASIBLE。该 probe 分类为“future-overlap owner-gate hazard, not current snapshot bug”。

probe 摘要输出：

```json
{
  "current_role_sets": {
    "external_boundary_and_generic_input": [],
    "output_input_intersection": [],
    "required_generic_inputs": ["qiaoyu_capsule", "valley_battery"],
    "required_generic_outputs": ["blue_iron_ore", "source_ore"]
  },
  "fixed_domain_count": 18,
  "fixed_domain_max_count": 540,
  "selection_coverage": {
    "binding_domain_instances": ["packaging_battery_001"],
    "binding_var_instances": ["packaging_battery_001"],
    "generic_input_slots": 3,
    "generic_output_slots": 1,
    "nogood_retry_status": "FEASIBLE",
    "nogood_second_selection_differs": true
  },
  "artificial_overlap_boundary": {
    "blocked_front_status": "INFEASIBLE",
    "blocked_generic_output_slots_after_rab": 0,
    "no_routing_context_port_specs": [],
    "classification": "future-overlap owner-gate hazard, not current snapshot bug"
  }
}
```

执行过的命令与结果：

```text
PYTHONPATH=. python cc_context/review/algoaudit_binding_face_r7_probe.py
# pass，输出如上

PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored

PYTHONPATH=. python -m pytest -q -p no:randomly \
  src/tests/test_binding.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_wireless_front_consumers_r4.py \
  src/tests/test_exact_contract.py::test_certified_binding_kwargs_use_master_generic_io_snapshot \
  src/tests/test_exact_contract.py::test_certified_retry_binding_receives_master_generic_io_snapshot
# 45 passed in 6.74s
```

全量 `PYTHONPATH=. python -m pytest -q -p no:randomly src/tests` 已尝试，但沙盒 300s 超时，日志在 7% 进度前没有失败输出。因此本报告只声明专项与 proof obligations 通过，不声称全量 pytest 完成。

## 最终判断

当前 round 7 关注的三件事都未发现当前 soundness 缺陷：

- Q1：规则文本与 binding 约束族对照通过；overload 是默认关闭并有 retry 的 heuristic，不进入 certified hard-rule soundness。
- Q2：当前 routing-free/generic I/O 生产链与消费点同步；物理 generic output 与虚拟 wireless input 当前隔离正确；future dual-role overlap 有明确 owner-gate 风险点，但不是当前 snapshot finding。
- Q3：selection 覆盖所有 CP-SAT 决策自由度；nogood 不因固定常量省略而误排未证伪 alternative；overload retry 后 selection 属于 retry model，自洽。

**本轮零 soundness finding。**
