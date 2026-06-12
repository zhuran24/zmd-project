# 终末地 IndustrialPlanner binding 忠实度面 R5 审查报告

审查对象：`zmd_fbind_r5_snapshot_54ffa047.zip`  
期望 sha256：`54ffa047d9c9fe0e350a8d920d4db1189db0403e8956bca0482e66ff85fbfb01`  
实测 sha256：`54ffa047d9c9fe0e350a8d920d4db1189db0403e8956bca0482e66ff85fbfb01`  
结论：校验一致后开工。zip 内 `project/` 已解包；快照未携带 `.git` 目录，因此本文行号以解包后的原始文件内容为准。

本轮结论：**非零**。发现 1 个新的 soundness finding，属于 R4 修复后 Q2 单快照族终验暴露出的残余缝：outer frontier domain 与后续 `ExactSearchSession` / parallel worker session 仍不是同一快照源。

---

## Finding F-BIND-R5-01

Severity：**HIGH**

标题：`outer_search` 的 certified frontier domain 仍在 `ExactSearchSession.create` 之外二次读取 wireless slot，且 parallel worker 会再次独立建 session；同一轮证明无法证明单源同快照

### 位置

原始快照中：

- `src/search/outer_search.py:1698-1715`：`run_outer_search` 在创建任何 `ExactSearchSession` 之前直接调用 `load_project_data`、`load_generic_io_requirements_artifact`，并在 `required_generic_inputs` 非空时直接 `load_wireless_sink_generic_input_slots(project_root)`，随后用该值计算 `safe_area_upper_bound`。
- `src/search/outer_search.py:1725-1736`：上述 `safe_area_upper_bound` 进入 `candidate_generation`，并生成 certified full-frontier 候选域。
- `src/search/outer_search.py:1876-1883`、`2037-2042`、`2425-2430`：serial precheck、parallel coordinator、serial solve 路径才创建或确保 `ExactSearchSession`，此时 session 会再次从 project root 读取同族 artifacts。
- `src/search/exact_parallel_scheduler.py:220-224`：parallel worker 进程启动时再次 `create_exact_search_session(Path(project_root), ...)`，没有与 coordinator 的 frontier-domain artifact hash / wireless slot snapshot 做一致性校验。

相关验证面：

- `src/search/exact_campaign.py:1147-1158` 与 `1185-1195` 也直接读取 wireless slot，但这两个 helper 当前主要用于 project-bound resume / terminal validation。它们可用于 fail-closed 校验当前 project，却不能证明 live outer candidate domain 与后续 solver session 同源。

### 为什么这是 soundness 缝

R4 已把 binding capacity 修到从 master snapshot 注入：`LBBDController._binding_generic_requirements_kwargs()` 读取 `self.master.generic_io_requirements` 与 `self.master.wireless_sink_generic_input_slots`，并在主 binding 和 overload retry 共用。但 `outer_search` 的 certified candidate domain 仍先从磁盘读取一次 wireless slot，后续 `ExactSearchSession.create` 又读取一次。这意味着 full-frontier 候选域和 solver 证明可以来自两个时间点。

在真实 project 中这个值会实质改变 certified frontier 上界。用原始 canonical artifacts 实测：

```text
required_generic_inputs = {'qiaoyu_capsule': 1, 'valley_battery': 1}
slots=1 -> static lower bound 3562, safe_area_upper_bound 1338
slots=3 -> static lower bound 3553, safe_area_upper_bound 1347
```

也就是说，wireless slot 由 3 漂到 1 时，frontier 候选域上界会少 9 个面积单位。若 coordinator 用 slot=3 生成候选域，而 worker/session 用 slot=1 证明候选 INFEASIBLE，terminal frontier 的 full-domain optimality 证据就会混用两个 domain。反方向也可能导致候选域被过窄枚举。单次 artifact drift 往往会被 terminal safe-area mismatch 或 solution replay 捕获；但当前 proof chain 本身没有把 outer domain 与 session / worker session sealed 在同一 artifact snapshot 上，因此不满足本轮 Q2 要求的“全部链回 `ExactSearchSession.create` 的同一次 plan 读取”。在 parallel 路径中，worker session 连 artifact hash equality 都没有回报给 coordinator。

### 可复现 probe

以下 monkeypatch probe 在原始 R5 代码上执行，不需要跑完整求解。它只验证调用顺序与使用值：outer 先用 slot=3 建 frontier domain，后续 `ExactSearchSession` 才以 slot=1 出现。

```text
STATUS UNKNOWN None
EVENT ('campaign_snapshot_before_session', '/tmp/tmpk1cc8k_i')
EVENT ('outer_direct_plan_read', 3)
EVENT ('safe_area_lb_slot', 3)
EVENT ('candidate_generation_safe_area', None, 1003)
EVENT ('exact_session_created_later_with_core_slot', 1)
EVENT ('campaign_stop', 'max_attempts_exhausted', 'UNKNOWN')
EVENT ('campaign_save',)
```

其中 `candidate_generation_safe_area` 的第二个数值 `1003` 是由 outer 直接读取的 slot=3 派生；随后 session core 才出现 slot=1。该 probe 证明两者不是同一 authority，也不是 `ExactSearchSession.create` 的同一次读取。

### 建议修法

补丁见：`fbind_r5_snapshot_seal.patch`。

补丁策略是 fail-closed，不试图在本轮重构所有 loader：

1. 在 `outer_search.run_outer_search` 中保存 certified outer domain snapshot：`artifact_hashes`、`generic_io_requirements`、`wireless_sink_generic_input_slots`。
2. 每次真实 `ExactSearchSession` 创建/确保后，校验 session 的 `artifact_hashes`、`core.generic_io_requirements`、`core.wireless_sink_generic_input_slots` 与 outer snapshot 完全一致；不一致直接 `RuntimeError`。
3. Parallel worker pool 启动时接收 coordinator expected artifact hashes；worker 自建 `ExactSearchSession` 后若 hashes 不同，启动失败并返回 `STARTUP_ERROR`，避免 worker 在不同 artifact universe 下产出 candidate proof。
4. 新增回归：`test_outer_search_rejects_wireless_slot_drift_between_frontier_and_session`，模拟 outer slot=3、session slot=1，期望 fail-closed。

该补丁不触碰 frozen artifacts，不需要 `candidate_placements.json` 再生，也不需要登记 hash 更新。

---

## Q1：R4 修复本身复核

### Q1.1 `required_generic_inputs` 为空但 placement 含 `wireless_sink`

结论：**binding 侧无残留 fallback 读盘**。

`PortBindingModel._build_generic_input_domains()` 先取 `generic_commodities = sorted(self.required_generic_inputs.keys())`，为空立即 return（`src/models/binding_subproblem.py:757-760`）。因此即使 placement 中已有 `operation_type == "wireless_sink"` 的实例，也不会调用 `_wireless_sink_input_slot_count()`，不会触发 `load_wireless_sink_generic_input_slots()` fallback。

动态 probe：临时 project root 故意不写 `rules/preprocess_plan.json`，但 placement 内含一个 `wireless_sink` protocol storage box，且显式传入 `required_generic_inputs={}`。结果：

```text
EMPTY_DEMAND_WIRELESS_BOX ('FEASIBLE', 0)
```

这说明空需求 + 有箱形态即便可达，也不复活 R4 的读盘缝。

### Q1.2 normalizer 与 loader 边界值一致性

`src/models/binding_subproblem.py:82-98` 的 `_normalize_wireless_sink_generic_input_slots` 与 `load_wireless_sink_generic_input_slots()` 共用同一规范化入口。动态 probe 覆盖 0、大整数、bool、负数、浮点、字符串：

```text
NORM_PARITY 0 ok ok 0 0
NORM_PARITY 1000000000000 ok ok 1000000000000 1000000000000
NORM_PARITY True TypeError TypeError
NORM_PARITY False TypeError TypeError
NORM_PARITY -1 ValueError ValueError
NORM_PARITY 1.5 TypeError TypeError
NORM_PARITY '3' TypeError TypeError
```

结论：0 和大整数行为一致；bool 没有被 Python 的 `int` 子类身份偷渡；非 int 与负数均 fail-closed。

### Q1.3 0 槽语义

动态 probe：`generic_input_slots=0` 且 `required_generic_inputs={'phase': 1}`，分别走 fallback 与显式注入路径，结果一致：

```text
ZERO_SLOT_FALLBACK ('INFEASIBLE', 0)
ZERO_SLOT_INJECTED ('INFEASIBLE', 0)
```

原因：`_build_generic_input_domains()` 生成 0 个 virtual slot；`_add_generic_input_requirements()` 对正需求加 `sum(vars_for_commodity) == required`（`src/models/binding_subproblem.py:796-807`），空 sum 等于 0，因此 required > 0 时 CP-SAT INFEASIBLE。master lower bound 在 slot=0 时不强制 protocol box 下界，属于剪枝弱化，不是 false feasible；binding 会 fail-closed。

### Q1.4 非 certified / heuristic fallback 隔离

非测试 `PortBindingModel(` 生产引用只有三处：

- `src/search/benders_loop.py:4967` 主 binding，R4 后注入 master snapshot。
- `src/search/benders_loop.py:5872` overload retry，R4 后共用同一个 kwargs helper。
- `src/search/heuristic_feasible_finder.py:129` best-effort heuristic verifier，未被 certified proof chain 引用；全仓非测试 `rg heuristic_feasible_finder` 未发现 certified decision consumer。

结论：heuristic fallback 仍会读盘，但未作为 certified 证据入口消费；本轮不报。

---

## Q2：`wireless_sink | generic_input_slots | get_operation_port_profile` 非测试引用重扫

重扫命令：

```bash
rg -n "wireless_sink|generic_input_slots|get_operation_port_profile" \
  src scripts PROJECT_LOCK.md specs -g '!src/tests/**'
```

命中 134 行。分类如下。

### 硬消费点

1. **master lower bound**
   - `src/search/benders_loop.py:1356-1374`：`compute_exact_static_area_lower_bound(..., wireless_sink_generic_input_slots=...)` 传入 `infer_certified_optional_lower_bounds()`。
   - `src/search/benders_loop.py:6232`、`6325`、`6335`：candidate precheck / pose-bool 分支从 `exact_session.core.wireless_sink_generic_input_slots` 取值。
   - 其中 pose-bool certified 入口被 unsafe env guard 阻断，非默认 proof path。

2. **outer safe-area / frontier domain**
   - `src/search/outer_search.py:1698-1715`：仍直接读 project root 的 wireless slot，未链回 session。本项即 Finding F-BIND-R5-01。

3. **campaign helpers / terminal validators**
   - `src/search/exact_campaign.py:1147-1158`：required optional counts helper 直接读 wireless slot。
   - `src/search/exact_campaign.py:1185-1195`：safe-area validation helper 直接读 wireless slot。
   - 这些 helper 是 project-bound validation authority，可 fail-closed 校验当前 project；但不能证明 live outer domain 与 solver session 同源。纳入 F-BIND-R5-01 的同族残留背景。

4. **coordinate stats / coordinate master ordering**
   - `src/models/exact_coordinate_master.py:5974-5975`：stats 从 `owner._required_generic_input_slot_total()` 与 `owner.wireless_sink_generic_input_slots` 读取，owner 是 `MasterPlacementModel`。
   - `src/models/exact_coordinate_master.py:6144-6154`：`_group_port_demand()` 使用 `get_operation_port_profile()` 只参与 search ordering key，不生成约束。Q4 复核见下。

5. **binding capacity**
   - `src/models/binding_subproblem.py:319`、`324-329`：`PortBindingModel.__init__` 接收并规范化 `wireless_sink_generic_input_slots`。
   - `src/models/binding_subproblem.py:750-755`：仅未注入时 fallback 读盘。
   - `src/models/binding_subproblem.py:757-794`：按 slot count 物化 routing-free virtual generic input slots。
   - `src/search/benders_loop.py:4892-4936`：certified 主路径从 master snapshot 构造 binding kwargs；`4967` 主 binding 与 `5872` retry 共用。

### 非硬消费 / 定义 / 文档 / 非 proof 路径

- `src/preprocess/operation_profiles.py`、`src/interchange/preprocess_context.py`：profile/context 定义与 strict context parser。
- `src/models/port_binding.py:31-45`：pose-level binding cache gate；generic hub operation 会被拒绝下放到 pose-level enumeration，不是 capacity 约束。
- `src/models/separator_capacity_hull.py:143-155`、`src/models/abstract_routing_layer.py:103-135`：实体 port commodity side/classification；routing-free generic sink commodity 已剔除，不创建 wireless capacity。
- `src/models/pose_bool_exact_master.py`：env-gated 非默认 master，certified 入口由 unsafe env guard 阻断。
- `src/preprocess/instance_builder.py:42`、`PROJECT_LOCK.md`、`specs/05_facility_instance_definition.md`、`scripts/build_current_preprocess_context.py`：定义/文档/生成辅助。

Q2 结论：binding capacity、master core、coordinate stats 的 R4 注入链成立；但 outer safe-area 与 parallel worker session 没有 session-snapshot seal，因此本轮非零。

---

## Q3：r1-r4 交互推演

### 组合 A：哨兵 / routing-free virtual slot × 0 槽快照

`wireless_sink` virtual slots 在 `binding_subproblem.py:771-788` 标记 `routing_free=True`、`virtual=True`。`extract_port_specs()` 在 `src/models/binding_subproblem.py:1037-1043` 跳过 `None`、`__unused__`，并跳过 `routing_free` 或 `virtual` slot。因此 0 槽时没有虚拟槽；正需求由 `sum([])==required` fail-closed；无需求时 `_build_generic_input_domains()` 直接 return。哨兵逻辑不需要为 0 槽补特殊分支。

### 组合 B：strict loader × kwargs 注入

certified binding 注入路径绕过 binding 的 disk loader，但其源头来自 `ExactSearchSession.create()`：`benders_loop.py:1571-1588` 读取 generic IO 与 wireless slot，随后 `MasterPlacementModel.build_exact_core()` 规范化并冻结到 core（`master_model.py:2531-2596`）。`_binding_generic_requirements_kwargs()` 又对缺失、bool、非 int、负数做 RuntimeError fail-closed（`benders_loop.py:4917-4936`）。因此 loader 的 BOM/strict JSON 防御在 certified binding 当下不是最后一道门，而是 session 创建时的入口门；注入路径本身没有放松类型。

### 组合 C：single snapshot × overload retry

主 binding 与 overload retry 分别在 `benders_loop.py:4967` 与 `5872` 构造 `PortBindingModel`，两者都展开 `**LBBDController._binding_generic_requirements_kwargs(self)`。R4 的 retry 同快照回归通过，未发现主/重试分叉。

---

## Q4：薄点抽查

### Q4.1 AST / indirect mutation scan

扫描范围：`src/**/*.py` 排除 `src/tests/**`，覆盖直接 assignment、annotation、subscript write、`setattr(..., 'generic_io_requirements' / 'wireless_sink_generic_input_slots', ...)`、`__dict__`、以及 `.update/.clear/.pop/.setdefault/__setitem__` 等间接 mutation 形态。

结果：

- 没有发现 `setattr` 写入目标字段。
- 没有发现目标字段上的 mutating method call。
- 没有发现生产代码通过 `__dict__` 间接改写目标字段。
- 直接写入集中在构造/局部：`MasterPlacementModel.__init__` 的 `self.generic_io_requirements` 与 `self.wireless_sink_generic_input_slots`、`ExactMasterCore` dataclass annotation、`ExactSearchSession.create` 局部变量、`_binding_generic_requirements_kwargs` 的 kwargs 组装等。

结论：r4 “无生产 mutation” 结论经更宽 AST 扫描仍成立。

### Q4.2 `_ordered_generic_slot_commodities` / port demand hint 复核

本轮重扫中相关薄点是 `exact_coordinate_master.py:6144-6154` 的 `_group_port_demand()`：它读取 `profile.generic_input_slots`，但只进入 `_ordered_groups_for_search()` 的排序 key，影响 search order，不创建 lower bound、capacity row 或 feasibility 约束。仍判定为 hint，不报 soundness。

---

## 回归与自验

环境：Python 3.13 venv，依赖从 `zmd_py313_linux_x86_64.zip` 离线安装，OR-Tools `9.15.6755`。

原始快照上执行：

```text
R4 四条回归：4 passed in 2.53s
python scripts/check_p1_2_proof_obligations.py：passed, 8 obligations anchored
python -m pytest -q -p no:randomly src/tests/test_binding.py src/tests/test_exact_contract.py src/tests/test_master.py：338 passed in 23.60s
```

全量 `python -m pytest -q -p no:randomly src/tests` 曾尝试执行，但在约 7% 进度处被运行时限截断，截断前未见 failure summary；因此本轮全量未完成。

应用建议补丁后执行：

```text
R4 四条回归 + 新增 R5 回归：5 passed in 1.66s
python -m pytest -q -p no:randomly src/tests/test_exact_contract.py：89 passed in 4.27s
python -m pytest -q -p no:randomly src/tests/test_binding.py src/tests/test_exact_contract.py src/tests/test_master.py：339 passed in 19.73s
python scripts/check_p1_2_proof_obligations.py：passed, 8 obligations anchored
```

补丁不涉及 frozen artifact；无需再生 `candidate_placements.json`，无 sha256/字节数登记更新项。
