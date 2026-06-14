# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 17 (确认轮·F-PRE-R16-01/02 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`, 对应干净 git 树 HEAD `8c61e1e`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`, 沙盒 Python 3.13 离线安装)。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包并已校验**, 不必再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **preprocess 链** (canonical rules → preprocess context → 实例展开 → candidate placement 生成 → 冻结工件)。

## 本面定义与历史: preprocess, 收敛轨迹 r13 HIGH → r14 2 HIGH → r15 1 HIGH → r16 2 HIGH, 本轮 = R16 修复确认轮

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r13 = F-PRE-R13-01 (cycle group recipe I/O 闭包); r14 = F-PRE-R14-01 (多输出 co-product 重复计数) + F-PRE-R14-02 (cycle-internal 组外 producer fail-open); r15 = F-PRE-R15-01 (public solver 入口绕过 R14 fail-closed); **r16 = 真 Pro 抓 2 HIGH F-PRE-R16-01 + F-PRE-R16-02**, 已修在本包内:

- **F-PRE-R16-01** (HIGH, external_boundary producer-free): `_backpropagate_non_cycle_demands()` 在 `role.source_kind == "external_boundary"` 时直接 `continue` 把该 commodity 当终端边界源, 跳过 producer index 查询 (`src/preprocess/demand_solver.py:299-300`)。修复前 role validation 与 canonical semantic validator 都没禁止「同一 commodity 既是 external_boundary 又被某 recipe 生产」→ 把一个本由 recipe 生产的 commodity (probe 用 `steel_part`) 的 role 篡改成 `external_boundary`, backprop 会跳过 producer 机器与其上游输入 (machine count sum 219→169, false-FEASIBLE / undercount 方向)。修在: canonical semantic validation 加门 (`src/rules/semantic_validator.py:154-158`) + direct `validate_preprocess_context()` 加门 (`src/interchange/preprocess_context.py:283-287`, `external_boundary` 且 `commodity_id in producers` → reject)。回归 `test_semantic_external_boundary_source_must_not_have_recipe_producer` + `test_preprocess_context_rejects_external_boundary_commodity_with_producer`。

- **F-PRE-R16-02** (HIGH, raw cycle solver 缺 group-local role contract): 修复前 `_solve_cycle_group_exact()` 入口只重复 single-output / cycle-internal output ownership / I/O closure / RHS membership / non-negative solve, 没有重复 full validation 在 `:326-356` 做的 requested group **本地 role contract** → 把 `buckwheat` 的 role `cycle_group` 从 `buckwheat_cycle` 改成 `sandleaf_cycle` (保留 `buckwheat_cycle.internal_commodities` 不变), full validation 正确拒绝, 但 raw `solve_cycle_group_exact()` 仍直接求解返回 recipe runs (false-FEASIBLE on malformed context)。修在: 新增 `_validate_cycle_group_local_contract()` (`src/interchange/preprocess_context.py:436-467`), raw 入口矩阵构造前调用 (`:540`), 检查 square / recipes 存在 / 每个 internal commodity 有 role 且 `source_kind='cycle_internal'` 且 `role.cycle_group == group.group_id` / net-export ⊆ internal。回归 `test_cycle_solver_rejects_unvalidated_context_with_internal_role_group_mismatch`。

lock 有 F-PRE-R16-01 / F-PRE-R16-02 两条款 (`PROJECT_LOCK.md:115-116`); specs/18 有 Round 16 段。

**本轮 r17 = F-PRE-R16-01/02 修复确认 + 自由攻击角**。修复点本身已 lock, **不重报已修项本身**; 本轮把这两个修复【钉成攻击面】: 找同型残留 / 反向缺陷 / 修复不完备。

注意: 本包含其它审查面同期落的修复 (cuts/master-geometry/benders/binding/scheduler 等各面有自己的线), 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-PRE-R16-01 修复确认 + 同型残留 (攻击面, 本轮主体之一)

R16-01 的根因形态 = **backprop 在某个 `source_kind` 分支上把 commodity 当终端、跳过 producer 链, 而该终端假设没有被 validation 强制成立**。把这个形态当模板深挖:

① **终端出口枚举完备性**: `_backpropagate_non_cycle_demands()` 里有几个 `continue` 终端出口? 目前已知两个: `role.cycle_group is not None` (`src/preprocess/demand_solver.py:296-298`, 由 R14-02 + cycle solver 兜) 和 `role.source_kind == "external_boundary"` (`:299-300`, 由 R16-01 兜)。**还有没有第三种把 commodity 当终端、却没有对应 producer-free / ownership 不变量的路径**? 例如 `internal_only`、`generic_input` sink、或 `source_kind == None` 的 commodity 走到 backprop 时, validation 是否保证「不会出现既被当终端供给又有 producer 机器被跳过」或「既无终端语义又无 producer → 该报错的 missing-producer」?

② **producer 集合同源性**: validation 端 (`validate_preprocess_context`) 的 `producers = build_producer_index(context)` (`src/interchange/preprocess_context.py:253`) 与 backprop 端的 `producer_index = build_producer_index(context)` (`src/preprocess/demand_solver.py:285`) 是否**同一函数同一定义**, 不存在「validation 看到 producer 因此拒绝 external_boundary, 但 backprop 因 key normalization / 排序 / 字符串化差异看不到该 producer」的错位? R16-01 的门基于 `commodity_id in producers` 的成员判断, 若两端对 commodity_id 的 str 化口径不一致, 门会漏。请核对 `build_producer_index` 的 key 类型 (`src/interchange/preprocess_context.py:381-389`) 与 backprop / role 查询里 commodity_id 的类型一致性。

③ **role 缺省合成的盲区**: backprop 用 `context.commodity_role(commodity_id)` (`src/preprocess/demand_solver.py:295`) 取 role; 该方法对**没有显式 role 条目**的 commodity 返回合成默认 `source_kind=None, sink_kind="none"` (`src/interchange/preprocess_context.py:139-148`), **从不抛错**。而 R16-01 / role validation 只遍历 `context.commodity_roles.values()` (显式声明的 role)。问: 一个**经由 recipe input 反向到达、但 commodity_roles 里没有条目**的 commodity, 在 backprop 里会拿到 `source_kind=None` (不命中 external_boundary 终端分支, 会继续找 producer) —— 这条路径 sound 吗? 反过来, 是否存在「validation 不强制每个 target / 每个 recipe-reachable commodity 都有显式 role, 于是某 commodity 的真实 external_boundary 语义被合成成 `None` 而错误地去找 (不存在的) producer 报 false-INFEASIBLE」, 或相反方向的 fail-open? 给出 file:line 论证或 probe。

④ **canonical 端 vs context 端两道门一致性**: R16-01 在 semantic validator (`src/rules/semantic_validator.py:154-158`) 与 `validate_preprocess_context` (`:283-287`) 各加一道。两门的判据 (`external_boundary` 且被 recipe 生产) 是否**等价覆盖**, 不存在「semantic validator 用 `commodity_metadata` 而 context validation 用 `commodity_roles`, 两者来源不同导致一边拦一边漏」的缝 (例如某 commodity 在 metadata 标 external_boundary 但 role 没标, 或反之)?

### Q2 F-PRE-R16-02 修复确认 + 双端契约对齐 (攻击面, 本轮主体之二)

R16-02 的根因形态 = **raw public 入口 (`solve_cycle_group_exact`) 的本地检查集合 ≠ full validation 在该 group 上做的检查集合**。把「两端检查集合差集」当模板深挖:

① **本地 contract 与 full validation 的逐项对齐**: 列出 full `validate_preprocess_context()` 在**单个 cycle group** 上执行的全部检查 (`src/interchange/preprocess_context.py:326-356`: square / recipes 存在 / I/O closure / 每 internal commodity 有 role 且 `role.cycle_group==group_id` / net-export ⊆ internal / **以及 `_solve_cycle_group_exact(context, group_id, {})` 与逐 net-export `{commodity:1}` 的 unit-basis 非负可解性 probe** at `:354-356`)。再列出 raw 入口现在做的全部检查 (`_validate_single_output_recipes` + `_validate_cycle_internal_output_ownership` + `_validate_cycle_group_local_contract` + I/O closure + RHS membership + 非负 solve, `src/interchange/preprocess_context.py:538-544`)。**两个集合的差集里, 还有没有 full validation 拦得住、raw 入口拦不住的项**? 重点核对: full validation 里那条 `role.source_kind == "cycle_internal"` 的**反向**检查 (`:298-309`, 即「声明 cycle_internal 必须在该 group internal_commodities 内」) 和 R16-02 新增的 `_validate_cycle_group_local_contract` 的**正向**检查 (`:446-461`, 即「group 的 internal_commodity 必须 role=cycle_internal 且 cycle_group==group_id」) 是否**双向闭合**, 不存在「某 commodity 声明属于本 group 但本 group internal 列表没列它」或「列了但 role 指向别处」其一方向 raw 入口仍漏。

② **raw 入口能否在合法 default 上误杀**: `_validate_cycle_group_local_contract` 是纯增检查。对**合法 default context** 的每个 cycle group, raw `solve_cycle_group_exact()` (经由 full validation `:354-356` 的 unit-basis probe 间接调用, 也经由 `solve_demands_exact` 的真实 cycle 求解调用) 是否仍正常返回、不把合法 group 误判 invalid? 即 R16-02 的 fail-closed 不能引入 false-INFEASIBLE 回归。请用 default pipeline probe 实证 (machine/port/demand 不变量与冻结工件一致)。

③ **net_export 子集 / RHS 双端**: R16-02 新增检查里 net-export ⊆ internal (`:462-467`) 与 raw solve 内部 RHS membership (`:559-568`, positive RHS 必须同时 internal 且 net-export) 是否**无重叠盲区也无矛盾**? 是否存在「group 声明某 commodity 为 net_export 但它既不是 internal 也无 producer」之类被一端放过的形态?

### Q3 R15/R14/R13/R12/R11 维持轻确认

r16 补丁动了 demand_solver 的终端分支门 (R16-01) + preprocess_context 的 raw cycle 入口 (R16-02 新增 helper) + semantic_validator。轻扫确认这些改动**没有破坏**既有门: R15-01 (public solver 重验入口) / R14-01 (单输出锁) / R14-02 (cycle-internal ownership) / R13-01 (recipe I/O 闭包) / R12-01 (RHS membership 双端) / R11-03 (cycle solve 非负证明) 在 r16 重构后仍完好 (确认没被同期改动削弱或绕过)。

### Q4 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面**当前最薄弱**的点深挖, **换新角度** (别复读 r1-r16 已审判读)。本面已审 r1-r16, 覆盖: schema 入口 / strict JSON / 几何契约 / cycle 闭包 / 实例展开 / 工件交叉一致性 / demand 数学 / public 入口重验 / 终端边界 producer-free / raw cycle 本地 contract。残留薄弱候选 (非限定, 仅供启发):
- **role 完整性不变量**: validation 是否强制「每个 target commodity、每个 recipe-reachable commodity 都有显式 role 条目」, 还是依赖合成默认 → 合成默认是否在某条 demand 路径上把语义算错 (Q1③ 的延伸)。
- **utility operations 链**: r15 轻扫过, 是否真的完全不参与 demand 生产/消费, 还是有 slot 计数进入 generic_io / port budget 的口径缝。
- **实例展开 / instance id 稳定性**: backprop 解出的 machine_runs → ceil → instance 展开的口径在边界 (run_rate 恰好整数 / 极小分数) 上是否 sound。
- **co-product 数据结构形态**: 上游 vendored snapshot 确有双输出 dismantler recipe; 当前 canonical 单输出锁是否在**所有**消费 recipe.outputs 的路径上都 fail-closed (不止 backprop)。

说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical / 266 口径 / min_side>=6 admissibility / omni_wireless / 52-Port 不变量, owner 已定); r1-r16 已修 finding 与已审结论本身 (重复报不算 finding)。
- 已 lock 的本面条款: F-PRE-R10-01/02、R11-01/02/03、R12-01、R13-01、R14-01/02、R15-01、R16-01/02 (见 `PROJECT_LOCK.md` 对应行)。这些是**攻击面的基线**, 找它们的同型残留/不完备可以报, 复述它们本身不可以。
- master / binding / campaign / scheduler / routing / cuts 各面 (各自有线)。怀疑跨面时交叉引述 `PROJECT_LOCK.md` 对应契约条款, 不在本轮重证。
- `candidate_placements.json` 外置再生撕裂 (已随包并校验, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。部分再生撕裂由 golden tests 抓 (设计边界); machine_counts/port_budget/commodity_demands 在 hash 闭包外但 certified runtime 不消费 (r7/r12 已审)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3058, 数目以实跑为准, **硬不变量 = 0 failed**); 跑不完就跑专项 + 如实声明跑了哪些 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`; 沙盒插件干扰可 `-p no:ddtrace -p no:cov -p no:json-report -p no:metadata`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations anchored)。
- 工件一致性自验 (可选但推荐): `python scripts/build_current_preprocess_context.py --output <tmp>/ctx.json --diff-json <tmp>/diff.json --diff-md <tmp>/diff.md` 应 `all_match: true` (6/6 frozen artifacts), `mandatory_exact_instance_count=266`, `all_instance_count=326`, `generic_output_slots=52`, `generic_input_slots=0`。
- **finding 必须带可复现 probe 或 file:line 严谨论证**; **实证推翻你的怀疑就不要报**。

## 严重度纪律

- **false-CERTIFIED / false-FEASIBLE / undercount (该有的机器/供料被漏掉) = soundness** —— P1.2 闭环只认这个, 标 HIGH。
- **false-INFEASIBLE / 保守过度拒绝 (合法 context 被误杀) = availability** —— 标 LOW 加固, 不是闭环 blocker。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 分段判读: Q1 (R16-01 四点: 终端出口完备 / producer 集合同源 / role 缺省盲区 / 两道门一致) + Q2 (R16-02 三点: 本地 contract 对齐 / 不误杀 / net-export 双端) + Q3 (R11-R15 维持) + Q4 (自由攻击角选点与结论)。
- 前 16 轮的结论不代表本轮默认干净; 这是**真 Pro 确认轮, 独立下结论**。按你自己的独立判断给最终判读。

## 范围边界

- 重点 = F-PRE-R16-01/02 修复确认 (同型残留/反向缺陷/不完备) + 自由攻击角; 其余 7 面不审。
