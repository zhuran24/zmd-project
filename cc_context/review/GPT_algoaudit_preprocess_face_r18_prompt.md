# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 18 (确认轮·F-PRE-R17-01/02 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`, 对应**带本轮全部修复的干净 git 树** HEAD `eb5c012`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`, 沙盒 Python 3.13 离线安装)。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包并已校验**, 不必再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **preprocess 链** (canonical rules → preprocess context → demand 反推 → 实例展开 → candidate placement 生成 → 冻结工件)。

## 本面定义与历史: preprocess, 收敛轨迹 r13 HIGH → r14 2 HIGH → r15 1 HIGH → r16 2 HIGH → r17 2 HIGH, 本轮 = R17 修复确认轮

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r13 = F-PRE-R13-01 (cycle group recipe I/O 闭包); r14 = F-PRE-R14-01 (多输出 co-product 重复计数) + F-PRE-R14-02 (cycle-internal 组外 producer fail-open); r15 = F-PRE-R15-01 (public solver 入口绕过 R14 fail-closed); r16 = F-PRE-R16-01 (external_boundary producer-free) + F-PRE-R16-02 (raw cycle solver 缺 group-local role contract); **r17 = 真 Pro 抓 2 HIGH F-PRE-R17-01 + F-PRE-R17-02**, 已修在本包内:

- **F-PRE-R17-01** (HIGH, direct context mapping key vs 对象内 id 别名绕过 R16-01): R16-01 的 external_boundary producer-free 门比较的是对象内 `role.commodity_id`。但 direct `PreprocessContext` 可把 `commodity_roles` 的 **mapping key** 仍设为真实 commodity (`steel_part`), 而对象内 `CommodityRole.commodity_id` 改成别的字符串 (`not_steel_part`)。validation 遍历 `role.commodity_id` 查 `not_steel_part in producers` 看不到 producer → 接受; backprop 用 **pending commodity id (即 key) `steel_part`** 查 role, 命中这个 external_boundary role 直接 `continue` 终止反推, 漏掉 `parts_maker` 及上游 (机器数 219→169 undercount, false-FEASIBLE 方向)。修在: `validate_preprocess_context()` 开头新增 `_validate_context_mapping_id_consistency(context)` (`src/interchange/preprocess_context.py:246`, helper 在 `:377-427`), 对 recipes / production_targets / commodity_roles / cycle_groups / utility_operations 强制 **mapping key == 对象内 id 且均为 str** (proof-critical id 一律 `_require_string_identifier`, `:425-427`)。回归 `test_preprocess_context_rejects_direct_role_key_identity_mismatch_before_external_boundary_short_circuit` (`src/tests/test_preprocess_context.py:293`)。

- **F-PRE-R17-02** (HIGH, raw cycle local contract 缺反向声明检查): R16-02 的 `_validate_cycle_group_local_contract()` 只做**正向**检查 (group 列出的每个 internal commodity 必须有 role 且 `cycle_group==group_id`), 漏了**反向**: 一个 role 声明 `cycle_group='buckwheat_cycle'` 但该 commodity 不在 `buckwheat_cycle.internal_commodities`。full validation 的反向检查 (`src/interchange/preprocess_context.py:300-311`) 会拒, 但 raw `solve_cycle_group_exact()` 接受并返回解 (false-FEASIBLE on malformed context)。修在: `_validate_cycle_group_local_contract()` 末尾新增反向扫描 (`src/interchange/preprocess_context.py:523-534`): 对所有 `context.commodity_roles.values()`, 若 `role.cycle_group == group.group_id` 则必须 `source_kind=='cycle_internal'` 且 `role.commodity_id in internal_commodities`。回归 `test_cycle_solver_rejects_unvalidated_context_with_role_declaring_group_but_missing_from_internal` (`src/tests/test_preprocess_cycle_solver.py:81`)。

两条款已入 LOCK (`PROJECT_LOCK.md:146`, **F-PRE-R17-01 / F-PRE-R17-02, conditional hardening** —— canonical build 的 dict key 与 inner id 同一循环变量派生、canonical cycle 数据恒自洽, 两条都只在手搓 dataclass 时可达, 是 **direct/raw-entry 加固, 不是 certified-path soundness reset**)。

**本轮 r18 = F-PRE-R17-01/02 修复确认 + 自由攻击角**。修复点本身已 lock, **不重报已修项本身**; 本轮把这两个修复【钉成攻击面】: 找同型残留 / 反向缺陷 / 修复不完备 —— 即, 继续找 **public / raw / direct 入口的 "validation 看见的不变量 ≠ consumption 实际依赖的不变量" 这类不对称**。canonical 数据恒自洽, 这些都是 direct-entry hardening 类。

注意: 本包含其它审查面同期落的修复 (cuts / master-geometry / benders / binding / scheduler 等各面有自己的线), 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-PRE-R17-01 修复确认 + 同型残留 (攻击面, 本轮主体之一)

R17-01 的根因形态 = **validation 端读对象内 id 做不变量检查, 而 consumption 端 (backprop / role 查询) 用的是 mapping key; 两者在 direct context 上可被做成不一致, 让 validation 的门基于错的 key 通过, consumption 走真正的 key 命中危险分支**。把这个形态当模板深挖:

① **mapping key/id 一致性门的覆盖完备性**: `_validate_context_mapping_id_consistency()` (`src/interchange/preprocess_context.py:377-422`) 现在覆盖 recipes / production_targets / commodity_roles / cycle_groups / utility_operations 五个 mapping 的 key==inner-id + str 类型。**还有没有第六个 proof-critical 容器, 它的 key 和某个内部 id 也会被 validation 与 consumption 用不同口径读, 但没进这道门**? 例如: `facility_templates` 的 key、`generic_io` 相关结构、recipe 的 `inputs`/`outputs` 里的 **value** (rate, 不只是 commodity key)、cycle group 的 `recipes` list 里的 recipe id 与 `context.recipes` key 的引用一致性。给出 file:line 论证: 哪些容器的 key 进了 backprop / producer index / role 查询的命中路径, 是否全部被这道门覆盖。

② **str 化口径一致性 (R17-01 加固后仍存在的缝)**: 现在门强制 proof-critical id 为 `str`。但 consumption 端历史上有不少 `str(commodity_id)` / `str(recipe_id)` 强转 (例如 `_validate_cycle_internal_output_ownership` 的 `str(commodity_id)` at `:479`、`build_producer_index` 的 key 是裸 `commodity_id` 未强转 at `:439-440`、`consumers.setdefault(str(commodity_id),...)` at `:259`)。问: **producer index 的 key (裸, 未 str 化) 与 R16-01 门里 `role.commodity_id in producers` 的成员判断, 在门强制 str 之后是否真的口径一致**? 现在 `_require_string_identifier` 保证 role.commodity_id 是 str, 但 `build_producer_index` 的 key 来自 `recipe.outputs` 的 key —— 那条路径上 recipe.outputs 的 key 是否也被同一道门强制为 str (`:387-388` 只 check recipe output **key** 是 str)? 若 recipe.outputs key 是 str 但 commodity_roles key 经别的路径仍可能是非 str 别名, 门是否真的闭合? 用 probe 或 file:line 论证确认无残留 int/str 混用缝。

③ **门的执行顺序 (短路 vs 兜底)**: `_validate_context_mapping_id_consistency()` 在 `validate_preprocess_context()` 的**最前面** (`:246`, 在 single-output / producer index / role 遍历**之前**), 这是对的 (先归一化 id 再做语义检查)。但 **raw `solve_cycle_group_exact()` 路径不经过 `validate_preprocess_context()`** —— 它只调 `_validate_single_output_recipes` + `_validate_cycle_internal_output_ownership` + `_validate_cycle_group_local_contract` + I/O closure + RHS membership (`src/interchange/preprocess_context.py:605-611`)。**raw cycle 入口是否也需要 mapping key/id 一致性检查**? 一个 direct context 把 cycle group 的某 internal commodity 的 role key 与 inner id 做成不一致, 经 raw `solve_cycle_group_exact()` 求解时, `_validate_cycle_group_local_contract` 的反向扫描 (`:523`) 遍历 `role.commodity_id`, 而正向检查 (`:501-516`) 用 `group.internal_commodities` 的字符串去 `context.commodity_roles.get(commodity_id)` (用 key)。这两端在 raw 路径上是否也存在 R17-01 同型的 key/id 别名缝, 因为 raw 路径没跑那道 mapping 一致性门? 给 probe 或论证。

④ **R17-01 门是否引入误杀 (availability 回归)**: `_require_string_identifier` 强制 proof-critical id 必须是 `str`。default canonical context 的所有 id 是否本来就是 str (`load_default_preprocess_context()` 全程跑通 `validate_preprocess_context` 不报)? 确认这道纯增门不会把某个合法但用了 int/非 str key 的 canonical 结构误杀。用 default pipeline probe 实证 (6/6 frozen artifact diff 全匹配, 266/326 instance count 不变)。

### Q2 F-PRE-R17-02 修复确认 + 双向闭包 (攻击面, 本轮主体之二)

R17-02 的根因形态 = **raw 入口的本地 contract 只做了正向 (group → role), 漏了反向 (role → group)**。把「单向 vs 双向闭包」当模板深挖:

① **反向扫描的完整性**: R17-02 新增的反向扫描 (`:523-534`) 现在拦「role 声明属于本 group 但不在 internal_commodities」。但它是**逐 group 调用** (`_validate_cycle_group_local_contract(context, group)` 只针对 raw 入口请求的那一个 group, `:607`)。问: 一个 role 声明 `cycle_group='groupB'`, 但 raw 入口求解的是 `groupA` —— 此时 `_validate_cycle_group_local_contract(context, groupA)` 的反向扫描 `if role.cycle_group != groupA.group_id: continue` 会跳过这个指向 groupB 的 role, **groupB 的契约在这次 raw 调用里根本没被检查**。full validation 会遍历所有 group 兜住, 但 raw 单 group 求解不会。这条路径 sound 吗? 即, raw `solve_cycle_group_exact(context, 'groupA', ...)` 只验 groupA 的本地 contract; 若 groupB 的 role/internal 不一致, 但 groupB 不参与本次 groupA 求解, 是否**不影响 groupA 的解的正确性** (因为矩阵只从 groupA.recipes / groupA.internal_commodities 构造)? 还是存在「groupA 的某 recipe 也被 groupB 引用 / 某 commodity 被两 group 都声明」的交叉污染让 groupA 的解被算错? 给出 file:line 论证或 probe: raw 单 group 求解是否真的只依赖该 group 的本地不变量, 不依赖任何其它 group 的契约成立。

② **正向 + 反向是否真的双向闭合 (无第三方向缝)**: 列出 cycle group ↔ role 之间所有应当成立的不变量, 逐条核对 raw 入口现在是否双端都拦:
   - (a) group.internal 列了 C → C 必须有 role 且 `cycle_group==group_id` (正向, `:501-516` ✅)
   - (b) role 声明 `cycle_group==group_id` → 必须 `source_kind=='cycle_internal'` 且在 group.internal (反向, R17-02 新增 `:523-534` ✅)
   - (c) group.net_export 列了 C → C 必须在 group.internal (`:517-522` ✅)
   - (d) **group.recipes 列了 R → R 的 outputs 必须 ⊆ group.internal** (I/O 闭包, 由 `_cycle_group_recipe_io_outside_internal` at `:609` 兜)
   - (e) **某 recipe R 输出 cycle-internal commodity C, 但 R 不在 C 所属 group.recipes** (R14-02, 由 `_validate_cycle_internal_output_ownership(context, group_ids={group_id})` at `:606` 兜 —— 但注意它也是**逐 group_ids** 限定的, 同 ①: 若 C 属于 groupB 但 R 在 groupA 求解上下文被引用, 是否漏?)
   **还有没有第 (f) 方向**: 例如「group.recipes 列了 R, 但 R 的某 output commodity 的 role 指向**另一个** group」, 或「两个 group 的 internal_commodities 有交集」这类被所有逐 group 检查都放过的形态? 给 file:line 论证。

③ **R17-02 是否引入误杀**: 反向扫描是纯增检查。对 default canonical context 的每个 cycle group, raw `solve_cycle_group_exact()` (经 full validation `:356-358` 的 unit-basis probe 间接调用, 也经 `solve_demands_exact` 真实 cycle 求解调用) 是否仍正常返回、不把合法 group 误判 invalid? R17-02 的 fail-closed 不能引入 false-INFEASIBLE 回归。用 default pipeline probe 实证。

### Q3 R16/R15/R14/R13/R12/R11 维持轻确认

r17 补丁动了 `validate_preprocess_context` 的入口 (新增 mapping 一致性门 `:246`) + `_validate_cycle_group_local_contract` 末尾 (反向扫描 `:523-534`)。轻扫确认这些改动**没有破坏**既有门:
- R16-01 (external_boundary producer-free, canonical 端 `src/rules/semantic_validator.py:154-158` + context 端 `src/interchange/preprocess_context.py:285-289`)
- R16-02 (raw cycle group-local contract 正向, `_validate_cycle_group_local_contract` `:501-522`)
- R15-01 (public solver 重验入口, `solve_demands_exact` 在 `src/preprocess/demand_solver.py:109` 调 `validate_preprocess_context`)
- R14-01 (单输出锁 `_validate_single_output_recipes`) / R14-02 (cycle-internal ownership `_validate_cycle_internal_output_ownership`)
- R13-01 (recipe I/O 闭包 `_cycle_group_recipe_io_outside_internal`) / R12-01 (RHS membership 双端) / R11-03 (cycle solve 非负证明)
确认 r17 重构后这些门仍完好, 没被同期改动削弱或绕过。

### Q4 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面**当前最薄弱**的点深挖, **换新角度** (别复读 r1-r17 已审判读)。本面已审 r1-r17, 覆盖: schema 入口 / strict JSON / 几何契约 / cycle 闭包 / 实例展开 / 工件交叉一致性 / demand 数学 / public 入口重验 / 终端边界 producer-free / raw cycle 本地 contract / direct context key==id 别名 / cycle role 双向闭包。残留薄弱候选 (非限定, 仅供启发):

- **machine-count ceil 的 epsilon 下偏 (强候选)**: `ceil_machine_count()` (`src/preprocess/demand_solver.py:81-87`) 对**非整数** Fraction 走 `int(math.ceil(float(normalized) - INTEGER_SNAP_TOLERANCE))` —— 这正是本轮 binding 面 F-BIND-R10-01 (`_rate_to_slots` 的 `ceil(rate - 1e-9)`) 刚被钉的**同型 float-epsilon 下偏 ceiling 形态**。问: backprop 解出的 machine_run Fraction 经 `generate_ceil_machine_counts` → `ceil_machine_count` 时, 是否存在某 run_rate 恰好 fractionally 高于整数 (例如 `2 + 1/10^9`) 被 `- INTEGER_SNAP_TOLERANCE` 抹回整数、少算一台机器 (undercount = false-FEASIBLE 方向)? 注意 `:85-86` 对 **int 值的 Fraction** 先短路返回 (精确整数安全), 危险只在**非整数 Fraction** 经 `float()` 转换 + 减 tolerance 那条路径。canonical rate ∈ {0.2, 1, 2, 3} / capacity 1.0 是否让所有 machine_run 恰好落在「精确整数 → 走短路」或「离整数足够远 → tolerance 不影响」, 使这条缝在 certified 路径上 latent (同 F-BIND-R10-01 的判读)? 还是存在某条 demand 链 (尤其 cycle 求解出的 Fraction 经 `:127` 累加进 `mutable_machine_runs` 后) 落在 `(N, N + INTEGER_SNAP_TOLERANCE]` band 被误降一台? 给 file:line 论证 / probe; 若实证 latent 也请明确说「与 F-BIND-R10-01 同型、canonical 数据下不可达」, 不要当成新 soundness 报 (但**值得作为 invariant-hardening 候选**显式列出)。
- **role 完整性不变量**: validation 是否强制「每个 target commodity、每个 recipe-reachable commodity 都有显式 role 条目」, 还是依赖 `commodity_role()` 的合成默认 (`src/interchange/preprocess_context.py:139-148`, 缺失 role → `source_kind=None, sink_kind='none'`, **从不抛错**)? 合成默认是否在某条 demand 路径上把语义算错 (一个真实 external_boundary 语义的 commodity 因没显式 role 被合成成 `None`, 在 backprop 里不命中终端分支而去找不存在的 producer 报 false-INFEASIBLE; 或反方向 fail-open)。这是 r17 之后 direct-entry 角度的延伸 —— mapping key/id 一致性已被钉, 但**「validation 是否强制 role 条目存在性」这条横切不变量本身**没被 R17 触及。
- **co-product 数据结构形态**: 上游 vendored snapshot 确有双输出 dismantler recipe; 当前 canonical 单输出锁 (R14-01) 是否在**所有**消费 `recipe.outputs` 的路径上都 fail-closed (不止 backprop / not just `validate_preprocess_context`)? 例如 `build_producer_index` (`:436-444`) 对多输出 recipe 会把它登记成多个 commodity 的 producer —— 若某 direct context 绕过单输出锁 (锁在 `validate_preprocess_context` 里, raw cycle 入口的 `_validate_single_output_recipes(context, recipe_ids=group.recipes)` 只锁 group 内 recipe), 非 group recipe 的多输出是否在 raw 路径有未锁的消费点?
- **实例展开 / instance id 稳定性**: backprop 解出的 machine_runs → ceil → instance 展开的口径在边界 (run_rate 恰好整数 / 极小分数) 上是否 sound (与第一条 ceil 候选相关但聚焦 instance 计数稳定性 266/326)。

说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical / 266 口径 / min_side>=6 admissibility / omni_wireless / 52-Port 不变量, owner 已定); r1-r17 已修 finding 与已审结论本身 (重复报不算 finding)。
- 已 lock 的本面条款: F-PRE-R10-01/02、R11-01/02/03、R12-01、R13-01、R14-01/02、R15-01、R16-01/02、**R17-01/02** (见 `PROJECT_LOCK.md` 对应行, R17 在 `:146`)。这些是**攻击面的基线**, 找它们的同型残留/不完备可以报, 复述它们本身不可以。
- master / binding / campaign / scheduler / routing / cuts 各面 (各自有线)。**本轮兄弟面同期落的 hardening 补丁** (binding F-BIND-R10-01 `_rate_to_slots` 有理数取整 / cuts CUT-R14-H1 / scheduler F-PS-R6-01) 不在本轮重报; 若发现 preprocess 面有 F-BIND-R10-01 同型的 ceil epsilon 缝 (见 Q4 第一条), 那是**本面新发现**, 可作为 invariant-hardening 候选报, 但要明确标「与 F-BIND-R10-01 同型」并判 canonical 可达性。怀疑跨面时交叉引述 `PROJECT_LOCK.md` 对应契约条款, 不在本轮重证。
- **env-gated / exploratory 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_*` 等全部 env-gated, 默认 off, 非 certified 路径; 这些后端的 false-FEASIBLE 是 env-gated backend hardening, 不是 certified soundness reset。
- `candidate_placements.json` 外置再生撕裂 (已随包并校验, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。部分再生撕裂由 golden tests 抓 (设计边界); machine_counts/port_budget/commodity_demands 在 hash 闭包外但 certified runtime 不消费 (r7/r12 已审)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3074, **数目以实跑为准, 硬不变量 = 0 failed**); 跑不完就跑专项 + 如实声明跑了哪些 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`; 沙盒插件干扰可 `-p no:ddtrace -p no:cov -p no:json-report -p no:metadata`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations anchored)。
- 工件一致性自验 (可选但推荐): `python scripts/build_current_preprocess_context.py --output <tmp>/ctx.json --diff-json <tmp>/diff.json --diff-md <tmp>/diff.md` 应 `all_match: true` (6/6 frozen artifacts), `mandatory_exact_instance_count=266`, `all_instance_count=326`, `generic_output_slots=52`, `generic_input_slots=0`。
- **finding 必须带可复现 probe 或 file:line 严谨论证**; **实证推翻你的怀疑就不要报**。

## 严重度纪律

- **false-CERTIFIED / false-FEASIBLE / undercount (该有的机器/供料被漏掉) on canonical 数据 + 默认 env = soundness reset** —— P1.2 闭环只认这个可达的, 标 HIGH。
- **env-gated / conditional / direct-entry 才可达 / false-INFEASIBLE (合法 context 被误杀) = hardening / availability** —— 不是闭环 blocker, **明确标 "hardening / 仅 direct-entry 可达 / canonical latent"**。R17-01/02 本身就是 conditional hardening (canonical 恒自洽, 仅手搓 dataclass 可达); 本轮若再挖到同类, 同样按这个口径标, 别夸大成 certified soundness reset。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 分段判读: Q1 (R17-01 四点: 门覆盖完备 / str 口径一致 / raw 入口是否需同门 / 不误杀) + Q2 (R17-02 三点: 反向扫描完整性逐 group 缝 / 正反双向闭包无第三缝 / 不误杀) + Q3 (R11-R16 维持) + Q4 (自由攻击角选点与结论, 尤其 ceil epsilon 候选的 canonical 可达性判读)。
- 前 17 轮的结论不代表本轮默认干净; 这是**真 Pro 确认轮, 独立下结论**。按你自己的独立判断给最终判读。

## 范围边界

- 重点 = F-PRE-R17-01/02 修复确认 (同型残留/反向缺陷/不完备) + 自由攻击角; 其余 7 面不审, 跨面只列「不审」交叉引 LOCK 条款。
