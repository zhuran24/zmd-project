# 终末地 IndustrialPlanner 精确求解器 — wireless 修复链 round 5 审查报告

审查对象：`zmd_v80_impl_full_20260612_single.zip`  
审查范围：F04-R4-01 / F04-R4-02 / F04-R4-03 / F04-R4-04 修复面，r4 自报 raw port/front 消费点清单复核，r2/r3/r4 交互复核，PROJECT_LOCK 与 specs 一致性复核。  
结论日期：2026-06-12

## 0. 总结结论

**本轮零 soundness finding。**

未发现 F04-R4 residual 残留；未发现 r4 四组修复引入新的 certified-exact soundness 缝。r4 改动整体呈现为两类安全效果：

1. 对真实 proof/cut/acceptance 路径，wireless routing-free sink final output 已经被过滤，或只参与弱化/保守化的 demand-count 约束；
2. 仍存在的 raw port/front 读取点要么处于 disabled / exploratory / diagnostic / rendering / generation / non-proof candidate scoring 路径，要么对象限定为 boundary/storage 等 routing-visible commodity，不进入本轮 wireless final output soundness 链。

本轮没有附 unified diff 或补丁包，因为未发现需要修改的代码。

## 1. 环境与回归

包校验：

```text
/mnt/data/zmd_v80_impl_full_20260612_single.zip
sha256 = e676c94dcc8477d087c916299486bea08c0d5a23dfd31d20b2c4c5842684fa52
```

与任务给定 sha256 一致。

离线依赖安装使用 `zmd_py313_linux_x86_64.zip` 解出的 wheels，Python 为 3.13。执行过的回归如下：

```text
python -m pytest -q \
  src/tests/test_wireless_front_consumers_r4.py \
  src/tests/test_wireless_sink_binding_semantics.py \
  src/tests/test_flow.py \
  src/tests/test_heuristic_feasible_finder.py

27 passed, 2 warnings in 1.94s
```

```text
python scripts/check_p1_2_proof_obligations.py

P1.2 proof obligation check passed: 8 obligations anchored
```

全仓根目录直接 `python -m pytest -q` 在该解包快照中会收集到 `补丁包/gpt_deliveries/.../zip_extracted/project/src/tests/...` 下的归档重复测试模块，产生 pytest import-file-mismatch collection error。这不是产品测试失败，而是归档补丁包目录被根目录 pytest 递归收集导致的测试发现问题。

改用 `python -m pytest -q src/tests` 后，沙盒 20 分钟上限内未跑完；超时前未观察到 failure。由于本轮重点为 r4 修复面，专项回归与 proof obligation 均已覆盖关键链路。

## 2. R4-01：`validate_preprocess_context()` 镜像 canonical dual-role 守卫

### 审查文件

- `src/interchange/preprocess_context.py`
- `src/rules/semantic_validator.py`
- `rules/canonical_rules.json`
- `data/preprocessed/generic_io_requirements.json`

### 代码结论

`validate_preprocess_context()` 的三条镜像守卫与 canonical 层 `_check_commodity_metadata()` 在本轮关注语义上等价：

- `generic_input` 必须出现在 production targets；
- `generic_input` 不能作为 recipe input 被消费；
- 每个 production target 必须有 commodity metadata，且 `sink_kind == "generic_input"`。

对应位置：

- `src/interchange/preprocess_context.py:234-333`
  - target/producers/consumers 构建：`246-250`
  - target 必须有合法 recipe producer：`252-265`
  - role source/sink kind 合法性：`267-271`
  - `generic_input` 必须是 target：`272-276`
  - `generic_input` 不得作为 recipe input：`277-281`
  - target 必须有 `sink_kind == "generic_input"`：`290-297`
- `src/rules/semantic_validator.py:125-163`
  - canonical metadata guard 对应三条：`139-156`

装载路径复核：

- `load_default_preprocess_context()` 调 canonical + plan 后经 builder 进入 validate：`src/interchange/preprocess_context.py:353-358`
- `load_preprocess_context_from_paths()` 直接 rules+plan / overlay 路径同样经 builder 进入 validate：`src/interchange/preprocess_context.py:361-369`
- 全仓搜索 `PreprocessContext(` 未发现第三条业务构造路径绕过 `validate_preprocess_context()`；未发现 `from_dict` / checkpoint resume 直接反序列化 `PreprocessContext` 的 certified 入口。checkpoint/campaign 状态保存的是 cut / campaign 运行状态，不是 preprocess context 原样对象。

当前数据也符合该约束：

```text
required_generic_inputs:
  qiaoyu_capsule: 1
  valley_battery: 1

rules/canonical_rules.json:
  qiaoyu_capsule  -> sink_kind generic_input, source_kind internal_only
  valley_battery  -> sink_kind generic_input, source_kind internal_only
```

二者均由对应 recipe 生产，且未作为 recipe input 消费。

### 判定

修复正确且完整。未发现第三装载路径绕过 canonical 与 preprocess-context 双层守卫。该修复是 fail-closed，不引入新 soundness 风险。

## 3. R4-02：deletion-core minimizer routing-visible port key

### 审查文件

- `src/search/routing_deletion_core_minimizer.py`
- `src/search/benders_loop.py`
- `src/tests/test_wireless_front_consumers_r4.py`

### 代码结论

`build_routing_visible_port_keys_by_instance(port_specs)` 的 key 形式为：

```text
(instance_id) -> set[(x, y, dir, type)]
```

其中 `(x, y, dir, type)` 对 front-blocked oracle 的语义足够：该 oracle 只需要判断某实例某物理 port-front 是否 routing-visible 且被阻塞，不需要保留端口 multiplicity。

对应位置：

- `src/search/routing_deletion_core_minimizer.py:38-68`
  - `RoutingVisiblePortKey = Tuple[int, int, str, str]`
  - 以 `instance_id` 分桶，避免跨实例碰撞；
  - 只接受 `type in {"in", "out"}`；
  - `x/y` 转 int，`dir/type/instance_id` 转 str。
- `_oracle_front_blocked()` 可选接收 `routing_visible_port_keys_by_instance`：`src/search/routing_deletion_core_minimizer.py:82-144`
  - 未传参时保留 legacy raw 行为；
  - 传入 visible key set 时，raw pose port 若不在当实例 visible set 中则跳过：`125-136`。
- `minimize_routing_front_blocked_core()` 将 visible map 传给初始 oracle 与 deletion trial oracle：`src/search/routing_deletion_core_minimizer.py:161-226`

key 规范化风险复核：

- 同实例、同 cell、同 direction、同 type 的重复 port 会被 set 合并；这不会改变 front-blocked 布尔判断。重复端口 multiplicity 对“该 front 是否可阻塞导致 routability 失败”的 oracle 不构成独立事实。
- 同 cell、同 direction 但 input/output 双角色端口由 `type` 区分，不会互相覆盖。若 routing-free output 与 visible input 共用几何，input 仍可见，output 被跳过，符合语义。
- `dir` 没有额外 upper-case normalization，但 `port_specs` 来自当前 binding 的 `extract_port_specs()`，与 routing/precheck 对 direction 的使用共享同源 canonical `N/S/E/W` 表示。若出现非法方向，后续 routing/front 逻辑会失败或不可证明，不会静默形成 certified false success。
- per-instance 分桶避免不同设施在同格同向的 key 碰撞。

Benders 调用时机复核：

- Benders 在每轮 binding 后取 `port_specs = binding_model.extract_port_specs()`；同一轮 routing precheck、D2/PCR、deletion-core 均使用该 binding 的 `port_specs`。
- deletion-core 调用处传入 `build_routing_visible_port_keys_by_instance(port_specs)`：`src/search/benders_loop.py:5418-5439`。
- 在该 oracle/minimization 调用期间 binding 不会变化；变化只能发生在新增 cut 后下一轮求解。因此不存在 visible key 与 oracle pose/binding 脱节的问题。

legacy 不传参调用点复核：

全仓搜索 `minimize_routing_front_blocked_core`、`_oracle_front_blocked`、`build_routing_visible_port_keys_by_instance` 后，未发现 certified 生产路径继续以 legacy raw 行为调用 deletion-core。legacy no-param 行为保留在 unit tests / 兼容性层，未接入本轮 certified wireless 链。

专项测试覆盖：

- `src/tests/test_wireless_front_consumers_r4.py:37-64` 构造 raw pose 中存在 wireless output blocked front，但 visible `port_specs` 为空的场景；raw oracle 会认为 blocked，visible oracle 会正确忽略。

### 判定

修复正确且完整。visible key 的 set 合并最多弱化 core，不会产生错误归因；Benders 传参时机与当轮 binding 一致；legacy raw 行为未残留在 certified 路径。

## 4. R4-03：pose-bool exact master raw port/front 消费替换

### 审查文件

- `src/models/pose_bool_exact_master.py`
- `src/tests/test_wireless_front_consumers_r4.py`
- `data/preprocessed/candidate_placements.json`

### 代码结论

r4 在 pose-bool exact master 中引入 routing-visible demand helper 与 routing-visible pose cache。关键语义为：

- input demand 全保留；
- output demand 排除 `required_generic_inputs` 对应的 routing-free sink commodities；
- 若某 operation 同时有 visible output 与 routing-free output，则 hard-clear / generalized blocking-cell cache 不按 raw output 端口强行泛化，只由 demand-count cut 保守处理。

对应位置：

- `_routing_free_sink_commodities()`：`src/models/pose_bool_exact_master.py:106-114`
- `_profile_port_demands()`：`src/models/pose_bool_exact_master.py:116-137`
  - input demand 全部保留；
  - output demand 过滤 routing-free sink commodities；
  - `generic_output_slots` 保留为 visible output demand。
- `_mandatory_port_side_is_routing_visible()`：`src/models/pose_bool_exact_master.py:145-160`
  - input side 有需求即 visible；
  - output side 只有当 `output_demand > 0` 且 `output_demand == total_output` 时进入 hard/cache visible side；
  - mixed output side 不进入 hard/cache 泛化路径。

四处 raw 消费替换复核：

1. `PORT_ACTIVE` 输出需求
   - env block：`src/models/pose_bool_exact_master.py:314-421`
   - Step 3 使用 `_routing_visible_profile_demands()`：`354-386`
   - pure routing-free output 的 demand 为 0，不生成 raw output hard 需求；
   - mixed output 只要求 visible output demand 数量的 clear fronts，不把所有 raw output ports 都硬性当作 routing-visible。

2. `CLEARANCE_HARD` cache
   - env block：`src/models/pose_bool_exact_master.py:423-466`
   - 使用 `_routing_visible_poses_by_port_at_cell_dir`：`439`
   - 不再从 raw `_poses_by_port_at_cell_dir` 直接泛化无线输出口。

3. blocking-cell cut
   - `_enumerate_poses_with_port_at()` 返回 routing-visible cache：`src/models/pose_bool_exact_master.py:1021-1027`
   - `add_routing_port_blocking_cell_cut()` 由此只泛化 visible port：`1037-1075`

4. lazy-demand cut
   - `add_routing_port_lazy_demand_cut()` 使用 `_routing_visible_profile_demands()`：`src/models/pose_bool_exact_master.py:955-1019`
   - demand 为 0 的 side 跳过；mixed output 以 visible demand 数量生成保守 cut。

cache 切换复核：

- `_build_port_lookup_cache()` 仍构建 raw `_poses_by_port_at_cell_dir`，但 routing-hard 与 generalized cut 使用 `_routing_visible_poses_by_port_at_cell_dir`：`src/models/pose_bool_exact_master.py:864-913`。
- raw `_build_global_pose_cache()` 仍可服务 port-active/lazy-demand 的候选枚举，但约束强度由 filtered demand 决定，不再把 routing-free output 当作 mandatory routed output：`src/models/pose_bool_exact_master.py:915-953`。

当前 artifact 复核：

```text
protocol_storage_box poses: 4624
protocol_storage_box input ports total: 0
protocol_storage_box output ports total: 0
```

因此 r4/r1 语义下，协议箱 wireless final sink 没有物理端口可被 pose-bool raw front 误消费。

混合 output side 复核：

- 混合侧不进入 hard/cache 泛化，避免把 routing-free output 的 raw front 当作所有 pose 必须 clear 的 hard 条件。
- demand-count cut 只要求 visible output demand 对应数量的 clear output fronts。若 raw output port 数量多于 visible demand，routing-free output 可以落在 blocked/raw 端口，visible output 可选择 clear 端口。这是弱约束，但 sound。
- 该处理不会“反向放过 visible 口”：visible output 仍通过 demand-count 受约束；只是不会把具体 raw side/cell 过早绑定为 hard obstruction proof。

专项测试覆盖：

- `test_pose_bool_front_caches_exclude_routing_free_output_side`：routing-free output side 不进入 visible cache。
- `test_pose_bool_visible_cache_is_conservative_for_mixed_output_side`：混合 visible+routing-free output 时，visible demand 存在，但 output hard/cache 泛化保持为空。

### 判定

修复正确且完整。raw cache 仍存在但不再作为 wireless final output 的 proof-hard 泛化入口；混合 output 处理为弱化/保守，不构成漏证导致的 false feasible 或 false cut。

## 5. R4-04：separator / SAC hull / L2 abstract routing / dynamic separator routing-free source 过滤

### 审查文件

- `src/models/separator_capacity_hull.py`
- `src/models/abstract_routing_layer.py`
- `src/search/separator_capacity_separator.py`
- `src/search/benders_loop.py`
- `src/models/pose_bool_exact_master.py`
- `src/search/patch_conflict_separator.py`
- `src/tests/test_wireless_front_consumers_r4.py`

### 代码结论

`routing_free_sink_commodities` 参数已接入核心 separator 分类链：

- `classify_pose_commodity_side()`：`src/models/separator_capacity_hull.py:129-192`
  - input commodities 全保留：`149`
  - output commodities 过滤 routing-free sink commodities：`150-158`
  - 被过滤 output 不再产生 routed source commodity：`186-191`
- `add_separator_capacity_hull_constraints()` 接收并传入该参数：`src/models/separator_capacity_hull.py:195-244`
- `solve_abstract_routing()` 接收并过滤 output commodities：`src/models/abstract_routing_layer.py:52-184`
- L2 infeasible 后动态 separator 继续传入该参数：`src/models/abstract_routing_layer.py:286-300`
- `analyze_layout_for_separator_violations()` 接收并传入 classify：`src/search/separator_capacity_separator.py:32-86`

构造点一致性复核：

- Benders 主链从 `generic_io_requirements.required_generic_inputs` 中正 demand commodity 构造 routing-free set：`src/search/benders_loop.py:4539-4546`
- Benders L2 call 传入：`src/search/benders_loop.py:4566-4578`
- Benders dynamic separator call 传入：`src/search/benders_loop.py:4629-4640`
- pose-bool static SAC hull call 传入：`src/models/pose_bool_exact_master.py:509-516`
- pose-bool delegate dynamic SAC call 传入：`src/models/pose_bool_exact_master.py:680-700`

容量数学 soundness 复核：

- 删除 routing-free final output source commodity 只会减少 routed source 需求，不会凭空增加容量压力；对 infeasibility cut 来说是弱化而不是收紧。
- input commodity 全保留，因此真正需要被送入 operation 的 routed inputs 不会被过滤。
- 对 mixed output side，如果 raw output 侧同时含 visible 与 hidden output，classification 的 side-distribution 可能因 hidden output 参与 raw side 统计而更容易变为 `AMBIG` / `NONE`，不是更强的错误单侧约束。这最多弱化 SAC/L2 cut。

第三调用点复核：

全仓搜索发现 `src/search/patch_conflict_separator.py:183-193` 在 PCR candidate selection 中调用 `analyze_layout_for_separator_violations()` 时未传 `routing_free_sink_commodities`。该点不构成 soundness finding，原因如下：

- 该调用只用于 patch candidate scoring / prioritization；
- `select_patch_candidates()` 同时使用 raw blocked-port clusters 与 SAC pressure 来决定“尝试哪里做 patch”；
- 真正构造 patch proof 时，`run_patch_conflict_separation()` 通过 `_build_patch_inputs()` 从当轮 filtered `port_specs` 生成 `patch_ports`：`src/search/patch_conflict_separator.py:247-292, 369-383`；
- patch cut 只有在 patch CP-SAT infeasible 且 `extract_and_validate_patch_core()` replay 通过后才会被接受：`src/search/patch_conflict_separator.py:403-410`。

因此 PCR 中这一路 raw SAC pressure 最多造成候选选择低效或无效，不直接铸造 certified cut。

专项测试覆盖：

- `test_separator_capacity_classification_excludes_routing_free_sources` 验证 `qiaoyu_capsule` 不再作为 routed source，但 input commodities 仍保留。

### 判定

修复正确且核心 certified separator/L2/dynamic/SAC 链已覆盖。PCR candidate-selection 未传参是 non-blocking hygiene 备注，不是 soundness finding。

## 6. Q2：raw port/front 消费点再穷举复核

本节列出本轮实际复核过的 port/front 消费点与结论。

### 6.1 binding / RAB / extract_port_specs

文件：`src/models/binding_subproblem.py`

- constructor 从 `required_generic_inputs` 构造 `routing_free_sink_commodities`：`188-192`
- `_filter_pose_binding_domain()` 保留所有 input ports，过滤 routing-free output ports：`382-424`
- RAB generic output domain 当前面向 `required_generic_outputs` source 侧；`extract_port_specs()` 仍有最终防线，若 generic output 选中 routing-free commodity 会跳过：`825-891`
- `extract_port_specs()` 明确跳过：
  - routing-free physical output ports：`839-843`
  - routing-free / virtual generic input slots：`855-861`
  - routing-free generic output slots：`873-879`

判定：safe。r2/r3 防线仍有效，r4 deletion-core 使用的 visible key 也来自该 filtered `port_specs`。

### 6.2 routing binding context / exact routing precheck / routing subproblem

文件：

- `src/models/routing_binding_context.py`
- `src/models/routing_subproblem.py`

结论：这些模块只消费调用方传入的 `port_specs`。Benders certified 主链传入的是 binding 后 filtered `port_specs`，因此不会重新从 raw pose ports 引入 wireless final output fronts。

关键位置：

- `run_exact_routing_precheck()` 对 `resolved_port_specs` 做 front blocked 分析：`src/models/routing_subproblem.py:283-356`
- `RoutingSubproblem.from_placement_core()` 使用传入 `port_specs` 建 grid：`src/models/routing_subproblem.py:590-599`
- `_index_port_fronts()` 遍历 `self.grid.port_specs`：`src/models/routing_subproblem.py:603-615`

判定：safe。

### 6.3 Benders 主循环

文件：`src/search/benders_loop.py`

复核点：

- 当轮 `port_specs = binding_model.extract_port_specs()` 后，routing precheck、D2、PCR、deletion-core 都使用同一轮 filtered `port_specs`。
- D2 separator 调用传入 `port_specs`：`5300-5306`
- PCR 调用传入 `port_specs`：`5349-5357`
- deletion-core 调用传入 `build_routing_visible_port_keys_by_instance(port_specs)`：`5418-5439`
- front-blocked `blocked_port` 来源于 routing precheck summary，而 precheck 基于 filtered `port_specs`。

判定：safe。没有发现 Benders certified cut/acceptance 使用 raw wireless output front。

### 6.4 `port_exposure_oracle.py`

文件：`src/cuts/oracles/port_exposure_oracle.py`

r4 自判“未接入 certified wireless 链”，本轮复核同意。

关键点：

- `_env_enabled()` 默认 false：`68-73`
- `generate_port_exposure_cuts()` env 未开直接返回空：`128-130`
- env 开启后确实会 raw `pose_ports()` 扫描：`153-204`
- 全仓搜索未发现 certified production 路径调用 `generate_port_exposure_cuts()`；只存在测试、归档脚本、env allowlist。
- cut replay/lifecycle 虽能识别 `port_exposure` cut，但 certified Benders 当前禁用 persisted exact-safe cut replay：`src/search/benders_loop.py:6330-6342`，发布 metadata 也标记 replay disabled：`6665-6671`。

判定：safe。该 oracle 不是本轮 certified wireless 链入口。

### 6.5 `flow_subproblem.py` 与 Benders flow diagnostic

文件：

- `src/models/flow_subproblem.py`
- `src/search/benders_loop.py`

r4 自判“diagnostic 不作 proof”，本轮复核同意。

关键点：

- `flow_subproblem.py` 文件头明确说明 certified_exact 中 flow 只作为 diagnostic，不能产生 formal pruning certificate：`1-10`
- `build_flow_network()` 会消费调用方给的 port_dict，本身不负责 wireless 过滤：`63-116`
- Benders certified 主链 `_run_flow_diagnostic()` 使用 raw pose ports 构建 dummy commodity flow，但结果仅写入 diagnostic metadata：`src/search/benders_loop.py:4841-4879` 与 `4531-4537`
- 未发现 certified 主链把 flow result 作为 acceptance、rejection 或 cut 依据。
- exploratory `_run_exploratory()` 中 flow 可影响 cut/acceptance，但该路径不是 certified-exact owner 链。

判定：safe。raw flow diagnostic 不参与证明。

### 6.6 `heuristic_feasible_finder._verify_flow`

文件：`src/search/heuristic_feasible_finder.py`

关键点：

- `_verify_flow()` 使用 raw pose ports：`212-266`
- `_verify_routing()` 使用 binding 产出的 filtered `port_specs` 后再路由验证；
- `find_feasible_for_candidate()` 可返回 `status="CERTIFIED"` 但 metadata 标记 `declare_mode: best_effort`：`403-420`
- 全仓搜索未发现该 heuristic feasible finder 被 certified exact owner 主链调用；主要存在于测试路径。

判定：safe。不是 certified wireless proof/acceptance 链。

### 6.7 master_model boundary-storage 筛与 raw front cache

文件：`src/models/master_model.py`

关键点：

- `_add_port_clearance_constraints()` raw front heuristic 在 exact mode 明确跳过：`4605-4648`，其中 exact skip 在 `4612-4614`
- exact boundary storage screen 只针对 `boundary_storage_port`，不是 wireless final output producer；boundary storage raw output ports 是 routing-visible source 侧。
- `_pose_greedy_blocking_cells()` 只对 `boundary_storage_port` 添加 port cells：`5226-5246`
- boundary storage feasibility screen 相关：`8647-8829`、`8930-8974`

判定：safe。未发现 wireless final output raw front 进入 exact proof。

### 6.8 D2 / PCR / patch routing core

文件：

- `src/search/d2_separator.py`
- `src/models/d2_commodity_flow_core.py`
- `src/search/patch_conflict_separator.py`
- `src/models/patch_routing_core.py`

D2：

- D2 separator docstring 声明 pipeline 输入为 master+binding feasible 与 `port_specs`：`src/search/d2_separator.py:1-15`
- assumptions 从拥有 `port_specs` 的 owner 构造：`63-81`
- D2 core build 使用传入 `port_specs`：`136-140`
- `d2_commodity_flow_core.py` 消费 `port_specs`，未发现 raw `input_port_cells` / `output_port_cells` proof 入口。

PCR：

- `_collect_blocked_port_cells()` raw 扫描 input/output ports：`src/search/patch_conflict_separator.py:68-118`
- 该 raw 数据只用于 patch candidate cluster / scoring。
- `_build_patch_inputs()` 从 filtered `port_specs` 生成 patch ports：`247-292`
- `run_patch_conflict_separation()` 使用 patch ports 建模，并只在 validated infeasible core 后产出 cut：`369-410`

Patch routing core：

- `build_local_pose_signature()` 将 raw ports 纳入 signature：`src/models/patch_routing_core.py:119-156`
- signature-lift 中包含 routing-free raw ports 只会让 equivalence 更窄，减少泛化，不会扩大到不等价 pose。
- patch model 的 port/front 约束来自 filtered `patch_port_specs`：`322-337`、`563-607`

判定：safe。PCR raw front/SAC pressure 是候选选择信息，不是 proof cut source；patch proof 使用 filtered ports 与 replay 验证。

### 6.9 其它 raw port 读取

复核到的其它 raw port 读取主要位于：

- placement generation / serialization；
- rendering / visualization；
- symmetry / instrumentation；
- archived patch packages；
- P1.3B exploratory 禁区。

这些位置不构成本轮 certified wireless 修复链的 proof/cut/acceptance 消费点。

## 7. Q3：r2/r3/r4 交互与默认 env 行为

### deletion-core 与 placement nogood 强度

r4 deletion-core 使用 routing-visible keys 后，oracle 忽略 wireless routing-free output blocker。若被忽略的是唯一 raw blocker，则 core 不再以该 hidden output 作为解释；若还有 visible blocker，则 core 基于 visible blocker 最小化。这样产生的 cut/nogood 最多更弱，不会错误归因到不可见 wireless output。

核心原因是：deletion-core 的 visible map 与 routing precheck 使用同一轮 `binding_model.extract_port_specs()` 结果。该 `port_specs` 已经承接 r2/r3 的过滤：wireless final output 不泄入 routing，RAB/cert 也不以 routing-free final output 为 front blocker。

### pose-bool lazy/generalized cut 与 binding/recheck 交互

pose-bool 中 hard/cache/blocking-cell/lazy-demand 仅对 visible demand 生效。mixed output case 不做 raw hard 泛化，可能使 master cut 更弱，但后续 binding + exact routing precheck 仍以 filtered `port_specs` 证明可行/不可行。因此不会把 hidden output front 错切成全局 hard obstruction。

### separator/SAC/L2/dynamic 与 binding/recheck 交互

routing-free output commodity 从 source side 删除，input 保留。该操作只减少 abstract routed demand，不会让 capacity hull 更强。L2/dynamic separator 若因此少出 cut，是弱化；真正 routing proof 仍由 filtered `port_specs` exact routing/precheck 承接。

### 默认 env 行为

本轮涉及的 pose-bool port-active / hard-clear / SAC / L2 / D2 / PCR 等多为 env-gated 或 exact-mode feature 路径。默认 env 全关时，r4 对这些 gated 逻辑不改变 certified 默认行为。always-on 的 preprocess validation、`extract_port_specs()` 过滤、Benders deletion-core visible map 传入均是 fail-closed 或 weaker-safe 方向。

判定：交互 sound。未发现 r2/r3/r4 修复相互抵消或绕开的路径。

## 8. Q4：文档一致性

复核文件：

- `PROJECT_LOCK.md`
- `specs/05_facility_instance_definition.md`

`PROJECT_LOCK.md:94-95` 与 `specs/05_facility_instance_definition.md:101-107` 已列明：

- `protocol_storage_box` 是 omni-wireless，no physical port cells；
- wireless final outputs 不得进入 route/flow sink fronts；
- 消费点清单包括：
  - `extract_port_specs()`；
  - RAB build-time domain filtering / certs；
  - routing deletion-core minimizer with current binding `port_specs`；
  - pose-bool exact master 的 port-active / hard-clear / cache / lazy-demand；
  - separator-capacity / L2 abstract routing / dynamic separator classification；
  - canonical 与 `validate_preprocess_context()` 双路径 dual-role guard。

代码实际复核到的 certified 消费点集合与上述文档清单一致。文档未漏列本轮 r4 proof-critical 消费点；文档也未把 PCR candidate scoring、flow diagnostic、heuristic feasible finder、render/generation 等 non-proof raw readers 列为 certified proof obligations。该边界与代码实际语义一致。

判定：文档一致，无列多/列少 soundness finding。

## 9. Non-blocking 备注

以下均不是 soundness finding：

1. 根目录 `pytest -q` 会误收集归档补丁包里的重复 test module，建议日常 CI 明确限定 `src/tests` 或忽略 `补丁包/` 归档目录。该问题不影响 r4 soundness 结论。
2. PCR candidate selection 中仍有 raw blocked-front cluster 与未传 `routing_free_sink_commodities` 的 SAC pressure call。该信息只用于候选排序/选择；patch model 与 replay proof 使用 filtered `port_specs`。若未来想减少无效 patch 尝试，可将 routing-free set 也线程传入 PCR candidate scoring，但不是本轮必须修复项。
3. `flow_subproblem.py` 与 heuristic feasible finder 内仍存在 raw port flow 逻辑。前者在 certified 主链只是 diagnostic，后者未接入 certified owner 主链；不构成本轮 finding。

## 10. 最终判定

**本轮零 soundness finding。**

F04-R4-01 至 F04-R4-04 修复均按预期封住对应 residual；对 r4 自报清单与额外 raw port/front 消费点的独立复核未发现第五处 certified wireless soundness 缝。preprocess/wireless 修复链可以按“本轮零 finding”输入 owner 收口判断。
