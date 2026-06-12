# 终末地 IndustrialPlanner wireless 修复链 round 4 审查报告

审查对象：`zmd_v80_impl_full_20260612_single.zip`

校验到的包 SHA256：`a5a7e2d7b66917b1f77d621f5e5da83978948cc8bf9ea3437dbaeff9e0e40d46`

结论：**本轮不是零 finding**。r3 对 `extract_port_specs()` 与 RAB build-time filter / certificate 的修复方向是正确的，但全仓穷举端口 front 消费点后，仍发现 4 组 residual soundness finding，均属于“绕过 routing-visible port specs、重新消费 raw pose port/front”的侧门。已给出补丁与回归测试。

补丁：`wireless_r4_residual_fix.patch`，从仓库根目录应用：

```bash
patch -p1 < wireless_r4_residual_fix.patch
```

补丁 SHA256：`d7b2a6e481ae5318e13833e4de1ce3cb0a5179327f15d1169b4e16ce7ffc300f`

## Findings

### F04-R4-01 HIGH：`preprocess_context` 装载路径绕过 r3 semantic guard

位置：原始快照 `src/interchange/preprocess_context.py:234-310`, `src/interchange/preprocess_context.py:330-346`; 影响面还包括 `src/preprocess/demand_solver.py:172-192`。

问题：r3 的 dual-role guard 落在 `src/rules/semantic_validator.py`，但 preprocess 侧仍有路径直接从 raw rules + plan 构建 `PreprocessContext`，只调用 `validate_preprocess_context()`，不经过 `validate_canonical_document()`。这使得 overlay / 非 canonical 直接构造路径可以接受“某 commodity 既是 `sink_kind='generic_input'` 终品目标，又作为某 recipe input”的形态。随后 `demand_solver` 会把该 commodity 生成进 `required_generic_inputs`，导致 producer 端输出口被 routing-free 排除，而下游 recipe 仍需要实体供料，正是 r3 guard 要 fail-closed 的形态。

复现 probe，未打补丁时：

```text
semantic_validator=REJECTED
  - 商品元数据冲突：generic_input 商品 'steel_part' ...
preprocess_context=ACCEPTED
steel_part_sink_kind=generic_input
```

修法：在 `validate_preprocess_context()` 内镜像 canonical guard，要求：

1. `sink_kind='generic_input'` commodity 必须有 production target；
2. `sink_kind='generic_input'` commodity 不得出现在任何 recipe inputs；
3. 每个 production target 必须有 commodity role 且 `sink_kind='generic_input'`。

补丁后 probe：

```text
semantic_validator=REJECTED
  - 商品元数据冲突：generic_input 商品 'steel_part' ...
preprocess_context=REJECTED
ValueError: generic_input commodity 'steel_part' cannot also be a recipe input; consumer recipes: packaging_battery
```

新增回归：`src/tests/test_wireless_front_consumers_r4.py::test_preprocess_context_rejects_dual_role_generic_input_overlay`。

### F04-R4-02 HIGH：routing deletion-core minimizer raw oracle 复活 routing-free 输出 front

位置：原始快照 `src/search/routing_deletion_core_minimizer.py:50-101`; 调用点 `src/search/benders_loop.py:5398-5430`，env gate `EXACT_B1_DELETION_CORE_CUT`。

问题：`_oracle_front_blocked()` 直接遍历 `input_port_cells` + `output_port_cells` raw geometry，不消费 `extract_port_specs()` 的 routing-visible terminal 集。r2/r3 已把无线终品 producer 输出口从 `port_specs` 排除，但 deletion-core oracle 会把同一个 raw output front 当作 blocked port。若 env 开启且 routing precheck 因其它 visible blocked port 触发 deletion-core minimization，这个 oracle 可能把“只堵无线终品输出 front”的设施也保留进 minimal core，产生过强 placement nogood。

最小 probe：filtered routing precheck 对空 `port_specs` 是 feasible，但 raw deletion oracle 仍报 blocked。

```text
routing_precheck_with_filtered_port_specs=feasible
legacy_raw=True
filtered_visible=False
```

修法：新增 `build_routing_visible_port_keys_by_instance(port_specs)`，deletion-core oracle 可选接收 per-instance routing-visible `(x, y, dir, type)` key set。Benders 调用 deletion-core 时用当轮 binding 的 `port_specs` 构造 key set，只检查 routing-visible ports。未传入该参数时保留 legacy raw 行为，便于测试/兼容。

新增回归：`src/tests/test_wireless_front_consumers_r4.py::test_deletion_core_oracle_consumes_filtered_routing_visible_ports`。

### F04-R4-03 HIGH：pose-bool exact master 多处 env-gated raw port/front 消费点未过滤

位置：原始快照 `src/models/pose_bool_exact_master.py:293-329`, `src/models/pose_bool_exact_master.py:367-409`, `src/models/pose_bool_exact_master.py:806-833`, `src/models/pose_bool_exact_master.py:908-966`。

问题：pose-bool master 是另一个 build-time / cut-time 侧门，独立消费 raw port/front：

* `EXACT_USE_PORT_ACTIVE` Step 3 用 `profile.output_slots + generic_output_slots` 计算 output demand，仍把 `filling_capsule -> qiaoyu_capsule`、`packaging_battery -> valley_battery` 的 routing-free final output 算作必须清 front；
* `EXACT_B1_PORT_CLEARANCE_HARD` 遍历 `_poses_by_port_at_cell_dir`，该 cache 由全部 raw input/output ports 构造；
* `add_routing_port_blocking_cell_cut()` 通过 `_enumerate_poses_with_port_at()` 泛化 blocked port cell 时，同样从 raw cache 取 pose；
* `add_routing_port_lazy_demand_cut()` output-side demand 未排除 routing-free final outputs。

这几条都是 env-gated，但属于 certified exact master / cut 面。打开后会把本应被 `extract_port_specs()` 排除的无线终品 producer 输出 front 重新变成 hard front-clear / blocking cut 的依据。

修法：给 pose-bool delegate 增加 routing-visible demand helper，所有 input demand 保留；output demand 排除 `generic_io_requirements.required_generic_inputs` 中的 routing-free sink commodities。具体修改：

* `EXACT_USE_PORT_ACTIVE` 与 lazy demand cut 改用 routing-visible demand；
* `_build_port_lookup_cache()` 额外维护 `_routing_visible_poses_by_port_at_cell_dir`；
* hard clearance 与 blocking-cell cut 只使用 routing-visible cache；
* 对未来“同一 operation 同时有 visible output 与 routing-free output”的混合侧，cache/hard path 不按 raw output port 泛化，只让 demand-count cut 保守处理，避免因无 binding-slot identity 而把 routing-free 端口当 visible 端口硬清。

当前规则下 `filling_capsule` 的 raw profile 是 4 个 visible input、1 个 routing-free output；补丁后 helper 判定为 `(input_demand=4, output_demand=0)`。

新增回归：

* `test_pose_bool_front_caches_exclude_routing_free_output_side`
* `test_pose_bool_visible_cache_is_conservative_for_mixed_output_side`

### F04-R4-04 MED-HIGH：SAC / L2 / dynamic separator 仍用 routing-free final output 作为 source-side front

位置：原始快照 `src/models/separator_capacity_hull.py:129-181`, `src/models/separator_capacity_hull.py:190-239`, `src/models/abstract_routing_layer.py:122-174`, `src/search/separator_capacity_separator.py:78-99`; 调用点包括 `src/models/pose_bool_exact_master.py` 的 static/dynamic SAC gate 与 `src/search/benders_loop.py` 的 L2/dynamic SAC gate。

问题：`classify_pose_commodity_side()` 从 `profile.output_slots` 无条件枚举 output commodities，并用 raw output front 计算 source side。对 `qiaoyu_capsule` / `valley_battery` 这类 routing-free final sink commodity，这等于在 separator-capacity 层重新创造一个不存在的 routed source。static SAC、L2 abstract routing、dynamic separator 都会消费这个分类，env 开启时可能形成 over-strong separator cut。

修法：`classify_pose_commodity_side()`、`add_separator_capacity_hull_constraints()`、`solve_abstract_routing()`、`analyze_layout_for_separator_violations()` 增加 `routing_free_sink_commodities` 参数，并过滤 output commodities；input commodities 全保留。`BendersLoop` 与 `PoseBoolExactMasterDelegate` 从 `generic_io_requirements.required_generic_inputs` 构造 routing-free set 后传入 SAC/L2/dynamic 调用。

新增回归：`test_separator_capacity_classification_excludes_routing_free_sources`。

## Q1 端口 front 消费点穷举清单

已检索关键词与调用链：`front`, `port`, `blocked_ports`, `is_port_front_usable`, `routing_binding_context`, `extract_port_specs`, `port_specs`, `PortBindingContext`, `separator`, `patch`, `PCR`, `D2`, `flow_diagnostic`, `boundary_port`, `clearance`。

判定如下：

* `src/models/binding_subproblem.py`：r3 修复本身正确。`_filter_pose_binding_domain()` 用 routing-visible port 集；`extract_port_specs()` 排除 routing-free final producer outputs 与 virtual wireless sink generic inputs。无新增 finding。
* `src/models/routing_binding_context.py`：`is_port_front_usable()` 的非测试调用点主要是 RAB filter 与 generic-output domain；routing-free final outputs 已由 RAB visible-port construction 排除。无新增 finding。
* `src/models/routing_subproblem.py`：routing precheck / analyze path 消费 `port_specs`，不直接复活 raw routing-free outputs。无新增 finding。
* `src/search/benders_loop.py`：常规 binding/routing path 消费 `extract_port_specs()`；但 deletion-core、L2 SAC、dynamic SAC 调用链发现 F04-R4-02 与 F04-R4-04，补丁已修。
* `src/search/routing_deletion_core_minimizer.py`：发现 F04-R4-02，补丁已修。
* `src/models/pose_bool_exact_master.py`：发现 F04-R4-03 与 SAC 调用传播点，补丁已修。
* `src/models/separator_capacity_hull.py`：发现 F04-R4-04，补丁已修。
* `src/models/abstract_routing_layer.py`：发现 F04-R4-04 的 L2 消费点，补丁已修。
* `src/search/separator_capacity_separator.py`：发现 F04-R4-04 的 dynamic separation 消费点，补丁已修。
* `src/models/patch_routing_core.py`：PCR/patch routing core 消费 filtered `port_specs`，未见 raw pose output-front 复活。无新增 finding。
* `src/search/patch_conflict_separator.py`：patch/PCR separator 消费 patch routing result / port specs，未见独立 raw wireless output-front 消费。无新增 finding。
* `src/models/d2_commodity_flow_core.py`, `src/search/d2_separator.py`：D2 path 消费 filtered port specs，未见 raw wireless output-front 消费。无新增 finding。
* `src/search/heuristic_feasible_finder.py`：`_verify_binding()` / `_verify_routing()` 经 `extract_port_specs()`；`_verify_flow()`/flow diagnostic 读 raw commodity flow，但在 certified exact 主循环里是 diagnostic metadata，不作为 exact acceptance/cut 的 routing proof。未报 soundness finding。
* `src/models/flow_subproblem.py`：diagnostic flow 会按 raw profile 建流并检查 blocked front，但当前 certified exact 的证明路径不依赖它；exploratory/旧 LBBD 若未来重新作为 cut source 使用，应另设 owner gate。未报本轮 soundness finding。
* `src/models/master_model.py`：coordinate delegate 的 `_add_port_clearance_constraints()` exact 模式跳过；boundary-storage port feasibility screen 面向 boundary source/storage port，并非 wireless final producer output。无新增 finding。
* `src/cuts/oracles/port_exposure_oracle.py`：cut-family/oracle 框架里有 raw front oracle，但未见当前 certified exact wireless chain 的启用调用；更像历史/探索切面。本轮不作为 blocking finding，但建议若将来接入 exact cut，必须先改成 routing-visible port-spec oracle。

## Q2 RAB 过滤修复审查

r3 RAB 修复本身审查通过。

* routing-visible 集合构造方向正确：input 全保留；output 仅排除 `routing_free_sink_commodities`。当前契约下 routing-free 的是 final sink wireless generic input，因此 producer output 端不进 routing，recipe/material input 端仍必须 routing-visible。
* 没发现 input 侧也应 routing-free 的 canonical 形态。`wireless_sink` 是 virtual generic input，不是 raw pose input port；新增/补强后的 semantic guard 阻断“generic_input commodity 同时是 recipe input”的 future dual-role 形态。
* RAB 是保守剪枝优化：少剪或留下更多 pattern 只会慢，不会把 routing 不可行布局证明为可行；危险方向是剪多。r3 过滤 routing-free outputs 后避免剪多，方向 sound。
* `EXACT_B1_ROUTING_AWARE_BINDING` env off 时，RAB filter 不运行，默认路径保持 r3 前后行为不变。

## Q3 语义守卫审查

原始 r3 guard 没覆盖所有装载路径，见 F04-R4-01。补丁后 canonical validator 与 preprocess-context validator 双层 fail-closed：无论通过 canonical document 还是直接 rules+plan 构建 preprocess context，都拒绝 dual-role generic_input。

判定边界：guard 恰好阻断“routing-free final sink commodity 又作为 recipe input”的断料形态。它不会误杀当前合法扩展：source-only commodity、普通 recipe intermediate、普通 final generic_input 均可保留；只有 generic_input 目标同时出现在 recipe inputs 时拒绝。

## Q4 回归与文档一致性

新增回归文件：`src/tests/test_wireless_front_consumers_r4.py`，共 5 个测试，覆盖：

1. preprocess context 绕过 semantic validator 的 dual-role 拒绝；
2. deletion-core oracle 只消费 filtered routing-visible ports；
3. pose-bool cache 排除 routing-free final output side；
4. pose-bool mixed output side 不做 raw-port hard 泛化；
5. separator capacity classification 排除 routing-free final output sources。

执行结果：

```text
python -m pytest -q -p no:randomly \
  src/tests/test_wireless_front_consumers_r4.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_rules.py --tb=short

30 passed in 1.49s
```

证明义务脚本：

```text
python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored
```

语法检查：

```text
python -m py_compile \
  src/interchange/preprocess_context.py \
  src/search/routing_deletion_core_minimizer.py \
  src/models/pose_bool_exact_master.py \
  src/models/separator_capacity_hull.py \
  src/models/abstract_routing_layer.py \
  src/search/separator_capacity_separator.py \
  src/search/benders_loop.py
```

全量 pytest 说明：

* 仓库根目录直接 `python -m pytest` 会收集到 `补丁包/gpt_deliveries/.../zip_extracted/...` 下的归档重复测试，并因此出现 duplicate collection import mismatch；这不是当前源树测试失败。
* `python -m pytest -q -p no:randomly src/tests --tb=short` 曾运行到约 16% 后在 900s 超时，超时前未观察到 failure；本轮未宣称完成全量 2903 绿。

文档方面：`PROJECT_LOCK.md` / `specs/05` 已写“exclusion must hold at every consumer”的方向。原 r3 文档列举面偏少；补丁后实际代码面与该契约对齐。

## 交付件

* `REVIEW.md`：本报告。
* `wireless_r4_residual_fix.patch`：源码补丁 + regression tests。
* `wireless_r4_review_patch_bundle.zip`：报告与补丁打包。
