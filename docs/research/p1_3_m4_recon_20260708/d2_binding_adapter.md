# M4-D2 侦察报告：F5 `query_liftable` 合同 + 第一个真 binding adapter

调查对象：`C:\claude pj\zmd-pj`（certified-exact 求解器，Python/CP-SAT）。
本报告全部结论带真实签名 + 行号，只读侦察，未改动任何文件。
日期：2026-07-08。

---

## 0. 一句话核心发现（最重要，先读）

**binding 子问题在纯 certified 路径下有两种、且只有两种可能的 INFEASIBLE，二者提升语义相反：**

1. **empty binding domain**（某 `(operation_type, pose)` 的端口绑定枚举为空）——**天然 liftable、单字面即可、纯白名单派生**。这是唯一 sound 的 F5 binding cut 形态。
2. **generic I/O demand 等式不可满足**（`sum(slot_vars)==required` 撞不上）——**反单调（anti-monotone）**：加设施 = 加 slot = 放松需求等式，子集 INFEASIBLE 不蕴含超集 INFEASIBLE，**不可 lift**。

而生产 `benders_loop` 里那个"自然 F5 挂点"（binding INFEASIBLE 分支 `:6038`，已挂 `_maybe_attach_framework_cuts(trigger="binding_infeasible")`）对应的**恰恰是第 2 种不可 lift 的 demand 情形**——empty domain 在 solve() 之前就被另一条分支（`:5863`）截走了。**这是本批最大的 soundness 陷阱**（详见 §2、§5-R1）。

---

## 1. binding 求解入口（Q1）

### 1.1 求解器类/签名/输入形态/输出/时限

文件：`src/models/binding_subproblem.py`。类 `PortBindingModel`（`:438`）。

构造签名（`__init__`，`:441-454`）：
```python
PortBindingModel(
    placement_solution: Mapping[str, Mapping[str, Any]],   # 完整布局: instance_id -> {facility_type, pose_idx, ...}
    facility_pools: Mapping[str, List[Dict[str, Any]]],    # 冻结 candidate_placements 的 pose 池 (按 facility_type)
    instances: Sequence[Mapping[str, Any]],                # 266 mandatory 实例记录
    required_generic_outputs: Optional[Mapping[str, int]] = None,
    required_generic_inputs: Optional[Mapping[str, int]] = None,
    project_root, io_requirements_path,
    wireless_sink_generic_input_slots: Optional[int] = None,
    routing_context: Optional[Any] = None,                 # RAB-SEP env 门控, certified 默认 None
    canonical_rules_payload, canonical_commodity_metadata,
)
```

三个方法构成"建模 → 求解 → 读结果"链：
- `build(*, use_overload_separation=None)`（`:775`）——建 CP-SAT 变量与约束。
- `solve(time_limit_seconds: float = 30.0) -> str`（`:1273`）——返回字符串状态。
- `extract_selection()` / `extract_port_specs()` / `extract_conflict_summary()` / `extract_empty_binding_domain_instances()`。

**status 表达（`solve()`，`:1319-1323`）**：
```python
if status in (cp_model.OPTIMAL, cp_model.FEASIBLE): return "FEASIBLE"
if status == cp_model.INFEASIBLE:                    return "INFEASIBLE"
return "TIMEOUT"          # 其余 (UNKNOWN 等) 一律 TIMEOUT
```
另有 `"INVALID_INPUT"`（`:1279-1288`，缺实例元数据/元数据不一致时，早退不建 solver）。

**时限参数**：`solve(time_limit_seconds=...)`，直接写进 `solver.parameters.max_time_in_seconds`（`:1291`）。worker 数走白名单 env `EXACT_BINDING_CP_SAT_WORKERS`（`:1292-1295`，`resolve_cp_sat_worker_count`）。

### 1.2 生产里 benders_loop 怎么调它（Q1 后半 + Q4）

调用点：`LBBDController._run_exact_binding_and_routing`（`src/search/benders_loop.py:5812`）。

构造（`:5840-5848`）：
```python
binding_model = PortBindingModel(
    solution,                       # ← placement_solution = 当前 master incumbent 布局 (黑名单派生态!)
    self.master.facility_pools,     # ← 冻结 pose 池 (白名单)
    self.master.source_instances,   # ← 266 mandatory 实例 (白名单)
    project_root=self.project_root,
    routing_context=_rab_sep_routing_context,   # 默认 None (env EXACT_B1_ROUTING_AWARE_BINDING 门控, :5832)
    **LBBDController._binding_snapshot_kwargs(self),   # 见下
)
binding_model.build()
...
binding_status = binding_model.solve(time_limit_seconds=self.binding_seconds)   # :5962
```

`_binding_snapshot_kwargs`（`:5807-5810`）= `_binding_generic_requirements_kwargs`（`:5751-5795`）∪ `_binding_canonical_rules_kwargs`（`:5797-5805`），提供：
- `required_generic_outputs` / `required_generic_inputs` ← `self.master.generic_io_requirements`（冻结 `generic_io_requirements.json` 快照，白名单）。
- `wireless_sink_generic_input_slots` ← `self.master.wireless_sink_generic_input_slots`（冻结 `preprocess_plan.json`，白名单）。
- `canonical_rules_payload` ← `self.master.rules`（冻结 `canonical_rules.json`，白名单）。

**关键：唯一黑名单输入是第一个位置参 `solution`（= incumbent placement_solution）。其余全是冻结工件快照。**

---

## 2. 子集 vs 完整布局 + 约束方向性（Q2 —— 本报告核心）

### 2.1 现状：binding 只对"完整候选布局"审，没有子集 API

`PortBindingModel` 吃的是一个具体的、完整的 `placement_solution`（所有已放实例 + 各自 pose_idx）。没有任何"对子集/部分 pose 集合求解"的入口。要拿 core（部分 pose 集合）喂它，只能自己构造一个"只含 core 实例"的 `placement_solution`——**而这正是不 sound 的做法**（见 2.3）。

### 2.2 模型内部耦合结构（决定方向性）

`build()`（`:775-809`）建三类变量：

| 变量族 | 建法 | 耦合 |
|---|---|---|
| `binding_vars[instance_id]` | 每实例 `AddExactlyOne`（`:1040`） | **无跨实例耦合**——每个 exact-pose-binding 实例独立选一个绑定模式 |
| `generic_input_vars[slot_id]` | 每 slot `AddExactlyOne`(commodities + `__unused__`)（`:1132`） | 经全局需求和耦合 |
| `generic_output_vars[slot_id]` | 每 slot `AddExactlyOne`(...+`__unused__`)（`:1086`） | 经全局需求和耦合 |

唯一的全局约束是 generic I/O **需求等式**：
```python
# _add_generic_input_requirements  :1134-1145
if required == 0:  for var in vars: model.Add(var == 0)     # required=0 → 该商品全禁
else:              model.Add(sum(vars_for_commodity) == required)   # 精确等式!
# _add_generic_output_requirements :1147-1158  同构
```

两条铁的观察：
1. **demand 是精确等式（`== required`），不是下界也不是上界**；`required` 是从冻结工件读的**固定常量**，**不随放置实例数缩放**（它是全基地的总需求）。
2. 每个 slot 的 `AddExactlyOne` 里**永远有 `__unused__` 选项**（`:1051` / `:1099`），所以**没有任何约束强迫一个 slot 必须承载某需求商品**。多出来的 slot 可以躺平走 `__unused__`。

而 slot 从哪来？由放置实例决定：`wireless_sink` 实例 → 虚拟 input slot（每实例 `wireless_sink_generic_input_slots` 个，`:1114`）；`boundary_io`/`protocol_core` 实例的 pose output_port_cells → output slot（`:1063`）。**放的实例越多 → slot 越多。**

### 2.3 方向性结论：demand-INFEASIBLE 反单调、不可 lift；empty-domain 单调、可 lift

**推论 A（加设施放松 demand）**：因为 demand 是"`sum==required`、`required` 固定、多余 slot 可 `__unused__`"，所以**加设施只增不减可行性**。若一个子集因 slot 不够（撞不上某商品的 `required`）而 INFEASIBLE，其超集加了更多 slot 后可能 FEASIBLE。

⇒ **"子集 binding-INFEASIBLE ⇒ 任何超集也 binding-INFEASIBLE" 对 demand 情形为假。** 把"只含 core 实例的布局 INFEASIBLE"直接 lift 成 F5 cut = **误剪合法解（FP）**。这与设计稿 §2.3 前提 3（liftable-reject）要防的正是同一类病：判决依赖 core 外的"缺席上下文"（这里是"其余供给 slot 的实例都缺席"）。

**推论 B（empty domain 内蕴、可 lift）**：`_build_fixed_operation_domains`（`:985-1045`）对每个支持 exact-pose-binding 的实例，调
```python
enumerate_pose_level_port_bindings_with_cache_info(operation_type, pose)   # port_binding.py:40
```
该枚举**只依赖 `(operation_type, pose)`**——`operation_type` 决定 port profile（冻结 `OPERATION_PORT_PROFILES`），`pose` 的 `input_port_cells`/`output_port_cells` 来自冻结 pose 池。域为空 ⇒ `empty_binding_domain_instances` 记账（`:1015-1027`），`build()` 里 `model.Add(0==1)`（`:782-783`）。
- `supports_exact_pose_level_binding(op)`（`port_binding.py:31`）= profile 无 generic hub slot。这类实例**跟 generic demand 完全解耦**（它们不产生 generic slot），其**唯一失败模式就是 empty domain**。
- empty domain 是纯 `(operation_type, pose)` 属性，**全白名单派生、与其余布局无关**。⇒ "任何含 group g 在 pose p 的布局，该实例都绑不上" **恒真、可 lift**。这是 sound 的 F5 binding cut。

**方向性一句话**：**exact-pose-binding 实例 = 每实例独立、只会 empty-domain 失败（可 lift）；generic-hub 实例 = 经全局等式耦合、demand 短缺失败（反单调、不可 lift）。** 二者无交叉耦合（exact-binding 域枚举彼此独立、也不进 demand 和）。

### 2.4 一个致命错位：生产挂点对应的是不可 lift 的那一种

`benders_loop` 在 `binding_model.solve()` **之前**（`:5863-5952`）先处理 empty domain：`extract_empty_binding_domain_instances()` 非空即走 `binding_pose_domain_empty_nogood`（instance-specific，未 lift）并早退。**所以能走到 `solve()==INFEASIBLE`（`:5979`/`:6038`）的，一定不是 empty domain，而是 demand 等式撞墙**——正是反单调、不可 lift 的那种。

而现有 F5-式挂点在 `:6055-6061`：
```python
proof_summary["cut_framework_attached"] = self._maybe_attach_framework_cuts(
    trigger="binding_infeasible", iteration=iteration, solution=solution,
)
```
它挂在 demand-INFEASIBLE 分支。**若 D2 天真地"在这里塞 binding adapter、把当前 INFEASIBLE lift 成 F5"，就会把反单调判决 lift 成 cut = 不 sound。** 正确的 sound binding adapter 只能回答 empty-domain 型 core（应对接 `:5863` empty-domain 分支，或干脆做成不依赖 incumbent、纯从白名单重算 empty-domain 的 query）。

---

## 3. binding 构造输入的白名单/黑名单归类（Q3）

对照设计稿 §4 ④ 的 immutable_scope 白/黑名单，逐个 `PortBindingModel` 输入归类：

| 输入 | 来源 | 归类 | 依据 |
|---|---|---|---|
| `facility_pools`（pose 池） | 冻结 `candidate_placements.json` | **白** | frozen artifact；binding 域枚举的 pose 数据源 |
| `instances`（266 mandatory） | 冻结 `mandatory_exact_instances.json` | **白** | frozen artifact；组结构 |
| `required_generic_outputs/inputs` | 冻结 `generic_io_requirements.json` | **白** | 组需求（设计白名单"group demand"） |
| `wireless_sink_generic_input_slots` | 冻结 `preprocess_plan.json` | **白** | frozen artifact 常量 |
| `canonical_rules_payload` | 冻结 `canonical_rules.json` | **白** | frozen artifact |
| operation port profiles | `OPERATION_PORT_PROFILES`（源码常量） | **白** | 组结构常量 |
| `placement_solution`（第 1 位置参） | master incumbent | **黑** | incumbent 派生态；对应设计黑名单 `selected_poses` 全体 |
| `routing_context` (RAB-SEP) | `build_routing_binding_context(solution, ...)`（`:5834`） | **黑** | 从 incumbent + 网格 cell 占用建；含 cell_owner 类信息。certified 默认关（`:5832`）但一旦开就是黑名单，会让 binding 域依赖其余布局的 front-block（`_filter_pose_binding_domain`，`:901-943`）——**adapter 必须拒绝在 routing_context≠None 下 lift** |

BState 侧证据（设计稿引"digest 刻意排除 selected_poses"属实）：
- `GroupState.selected_poses`（`lifecycle.py:389`）是 incumbent 可变态；`_group_static_source_payload`（`:488-502`）**显式排除** selected_poses、只留 `demand` + `pose_domain` 进 source_digest（注释 `:491-494`）。
- `BState.cell_owner`（`lifecycle.py:407`）= incumbent 占用，黑名单。
- 白名单字段（进 source_digest / 或结构常量）：`canonical_rules`、`candidate_placements`、`instance_to_facility_type`、`facility_templates`、`commodity_demands`、`commodity_routes`、`groups[].demand`、`groups[].pose_domain`（`source_digest_payload`，`:505-521`）。
- ghost 相关（`ghost_rect`/`ghost_cells`/`exterior_blocks`）= 候选级常量，设计要求**必须经 `CutScope` 字段绑定**才可依赖（`compute_ghost_rect_id`/`compute_blocked_cells_hash`，`:444-462`）。

---

## 4. 挂点当时可喂 adapter 的材料（Q4）

在 `_run_exact_binding_and_routing` 的 binding-INFEASIBLE 分支（`:5979`-`:6078`）作用域内，现成可用对象：

- `binding_model`（`PortBindingModel` 实例）——`extract_conflict_summary()`（`:1428`，含 `binding_domains` 每实例域大小、`empty_binding_domain_instances`、`required_generic_*`、`selection`）、`extract_empty_binding_domain_instances()`（`:1442`）、`extract_selection()`（`:1325`）、`extract_port_specs()`（`:1360`）。
- `solution`（incumbent placement_solution，**黑名单**——adapter 不得读它做判决）。
- `LBBDController._binding_snapshot_kwargs(self)`（`:5807`）——可复用地重建一个 adapter-侧 binding 模型的白名单输入（generic reqs + canonical rules + wireless slots）。
- `self.master.facility_pools` / `self.master.source_instances`（白名单）。
- `_binding_snapshot_kwargs` 的三个子方法（`:5751`/`:5797`）可直接复用来喂 adapter。

**`_maybe_attach_framework_cuts` → `_build_cut_framework_state`（`:7539-7646`）已经组装好一个 BState**，正是 adapter 该收的 immutable_scope 载体：
```python
BState(
    groups={gid: GroupState(demand, pose_domain, selected_poses=incumbent)},  # selected_poses 黑, 其余白
    cell_owner={},                     # 生产此处恒空 (:7630)
    ghost_rect=(anchor_x, anchor_y, ghost_h, ghost_w),
    ghost_cells=..., exterior_blocks=frozenset(),
    artifact_hashes=dict(self.artifact_hashes),
    canonical_rules=rules, instance_to_facility_type=..., facility_templates=templates,
    candidate_placements={"facility_pools": facility_pools},   # ← adapter 重算 empty-domain 的数据源!
)
```
注意：该 BState 里 `groups[gid].selected_poses` 注入了 incumbent（`:7596-7599, 7620-7625`），**是黑名单**；`query_liftable` 的 immutable_scope 必须结构性地把它挡在 adapter 视野外（现协议 `query(core, state)` 直接把整个 BState 递进去 = 泄漏，见 §5-R2）。

**现状缺口**：`_maybe_attach_framework_cuts`（`:7692-7818`）目前只生成 F1(`region_capacity`)/F7(`power_hitting_set`)/F6(`shape_packing_hall`)，**根本没调 `generate_pattern_nogood_cuts`（F5）**。`_REGISTERED_SUB_PROBLEM_ORACLES` 默认空（`pattern_nogood_oracle.py:89`）。所以 D2 要做两件事：①升级协议为 `query_liftable`；②注册并接第一个真 binding adapter 进这条（或 empty-domain 专属的）生成链。

---

## 5. 实施风险清单（Q5）

**R1（最高危 · soundness）：demand-INFEASIBLE 不可 lift。** 生产 binding INFEASIBLE 挂点（`:6038`）对应的全是 demand 等式撞墙（反单调）。天真"把当前 binding INFEASIBLE 交给 minimizer/adapter 去 lift"= 误剪 FP。**第一个真 binding adapter 的 sound 语义只能是 empty-domain 型**：给定 core，对每个 `(group_id→operation_type, pose_id)` 从 immutable_scope 的 `candidate_placements` 重新枚举 `enumerate_pose_level_port_bindings(operation_type, pose)`，**任一 core 字面 pose 域为空 ⇒ INFEASIBLE（可 lift）**；否则 FEASIBLE/UNKNOWN（绝不基于全局 demand 短缺回 INFEASIBLE）。这天然是单字面核；minimizer 会收敛到那个空域字面。

**R2（协议泄漏）：现 `query(core, state: BState, deadline)` 把整个 BState（含 `selected_poses` / `cell_owner` / routing 派生）递给 adapter。** 升级 `query_liftable(core, immutable_scope, deadline)` 必须传一个**结构性剔除黑名单字段**的视图（新 dataclass / 冻结投影），让 adapter **物理上读不到** incumbent。否则"白名单"只是口头约定，adapter 仍能偷读 `selected_poses` 做判决。设计稿 §4 ④两条红测须落地：σ-重标 verdict 不变性、上下文依赖判决被拒。

**R3（routing_context 污染）：** 若 `EXACT_B1_ROUTING_AWARE_BINDING` 开（`:5832`），binding 域被 `_filter_pose_binding_domain`（`:901-943`）按其余布局的 front-block 过滤——**域是否为空开始依赖 incumbent**，empty-domain 不再纯白名单。adapter 必须 fail-closed 拒绝在 routing_context≠None（或该 env 开）时 lift。

**R4（group_id ↔ operation_type ↔ facility_type 映射）：** F5 core 用 `group_id`；binding 域枚举要 `operation_type` + `facility_type`(取 pose)。BState 有 `instance_to_facility_type: Dict[GroupId, str]`（`lifecycle.py:418`，如 `"boundary_io"→"boundary_storage_port"`），但 group_id 与 operation_type 的等同关系要核实（`_build_cut_framework_state` 用 `group.get("group_id")`，`:7606`；需确认 mandatory_groups 的 group_id 就是 operation_type，否则域枚举第一个参数取错）。**建议加一条红测：core 的 group_id 能唯一解析到 operation_type + 冻结 pose 对象。**

**R5（重复 empty-domain nogood）：** empty domain 已有 `binding_pose_domain_empty_nogood`（`:5921`，instance-specific 未 lift）。F5 的增量价值 = 把它 **orbit-lift**（从"此实例此 pose 绑不上"泛化成"此 group 任何实例此 pose 都绑不上"）。要确认两条 cut 不冲突、且 F5 版确实更强（覆盖同组其余 slot）而非重复劳动。

**R6（demand 侧 sound cut 的正确出口不在 F5）：** 若确有"某组某 pose 恒不可行"之外、真正内蕴的 binding 结构矛盾，它属于 candidate-level infeasible（整候选死），不是 pose-pattern nogood，别硬塞 F5。方案 A（`multiplicity≥2`）已被设计稿 §2.3 BLOCK-2 挡在门外（master 无 cardinality-aware attach）。

**R7（minimizer 与 adapter 的 verdict 契约）：** `deletion_minimize_core`（`bounded_core_minimizer.py:175`）要求初次 full-assignment 必须 INFEASIBLE 否则 `raise ValueError`（`:194`）；trial 只有 INFEASIBLE 才缩核；UNKNOWN/TIMEOUT 保核不停（`:255-258`）；越界 verdict 当异常 fail-closed（`:235-244`）。empty-domain adapter 天然稳定（同 core 恒定 verdict），风险低；但 adapter 绝不能对 demand 情形返回 INFEASIBLE（会污染缩核）。

**R8（canonical_relabel 复验，M4-D1 既有）：** generator 已在 relabel 后**重新过 oracle 复验**（`pattern_nogood_oracle.py:201`）并禁重复 `(group,pose)`（`:196-199`）。empty-domain adapter 必须对 relabel 后的 core 仍给一致 verdict（因判决只依赖 pose 域，与 slot 标签无关，天然满足 σ-不变——正好是设计要的红测锚）。

---

## 6. 关键锚点行号索引（复核用）

- Protocol `SubProblemOracleAdapter`：`src/cuts/oracles/pattern_nogood_oracle.py:62-86`；`query(core, state, *, deadline_seconds) -> (verdict, blob)`。
- 注册表默认空：`pattern_nogood_oracle.py:89`；`register/lookup/clear`：`:92-115`。
- generator `generate_pattern_nogood_cuts`：`pattern_nogood_oracle.py:123-214`（relabel 复验 `:192-202`）。
- `OracleVerdict`/`LiteralAssignment`/`deletion_minimize_core`：`src/cuts/helpers/bounded_core_minimizer.py:56/60/175`；`canonical_relabel`：`:138-172`。
- `PortBindingModel`：`src/models/binding_subproblem.py:438`；`build`:775；`solve`:1273；demand 等式 `:1145`/`:1158`；域枚举 `:997`；empty-domain 记账 `:1015-1027`。
- `enumerate_pose_level_port_bindings_with_cache_info`：`src/models/port_binding.py:40`（只吃 `operation_type, pose`）；`supports_exact_pose_level_binding`：`:31`。
- benders 调用点：构造 `benders_loop.py:5840-5848`；`solve` `:5962`；empty-domain 分支 `:5863-5952`；demand-INFEASIBLE 分支 `:6038-6078`；F5-式挂点 `:6055-6061`。
- `_binding_snapshot_kwargs`：`benders_loop.py:5807`（子方法 `:5751`/`:5797`）。
- `_build_cut_framework_state`：`benders_loop.py:7539-7646`；`_maybe_attach_framework_cuts`：`:7692-7818`（未含 F5）。
- `BState`：`src/cuts/lifecycle.py:397-437`；`GroupState.selected_poses`：`:389`；source_digest 排除 selected_poses：`:488-502`。
- 测试用 `FakeAdapter` 形态：`src/tests/cuts/test_family_pattern_nogood.py:65-95`。

---

## 7. 不确定 / 待核实（未编造）

- **group_id 是否恒等于 operation_type**（R4）：`_build_cut_framework_state` 从 `mandatory_groups[].group_id` 取，binding 从 `instances[].operation_type` 取；设计稿把二者当同一物（8 组按 operation_type 分），但我未在源码逐字确认 mandatory_groups 的 group_id 字段就是 operation_type 字符串。落地前须核 `mandatory_exact_instances.json` / master `_mandatory_groups` 构造。
- **是否存在 exact-pose-binding 实例的 pose 域"因组合"为空**：我判断为否（各实例域枚举独立、无跨实例耦合），但未穷举所有 operation profile；若某 profile 的域枚举暗含跨实例假设需复核。
- **demand 情形是否 100% 无可 lift 子核**：我的论证基于"slot 恒可 `__unused__` + required 固定 + 加设施只增 slot"。未构造形式化反例证明"绝对无"，但方向性（反单调）在约束层证据充分。若未来 master 引入"必须用满某端口"类约束，需重证。
