# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 19 (确认轮·F-PRE-R18-01/02/03 修复确认 + 残留 validation-vs-consumption 不对称 / float-epsilon 族自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_0590f9ca.zip`, sha256 `0590f9ca30aac5bb7afe18945eb36d347ea8b0c5b467fd6baff4679eff8c5234`, 对应**带本轮全部修复的干净 git 树** HEAD `7fec29a` (round-1 + round-2 全部修复已合入)。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`, 沙盒 Python 3.13 离线安装)。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包并已校验**, 不必再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **preprocess 链** (canonical rules → preprocess context → demand 反推 → 实例展开 → candidate placement 生成 → 冻结工件)。

## 本面定义与历史: preprocess, 收敛轨迹 r13 HIGH → r14 2 HIGH → r15 1 HIGH → r16 2 HIGH → r17 2 HIGH → r18 3 hardening, 本轮 = R18 修复确认轮

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r13 = F-PRE-R13-01 (cycle group recipe I/O 闭包); r14 = F-PRE-R14-01 (多输出 co-product 重复计数) + F-PRE-R14-02 (cycle-internal 组外 producer fail-open); r15 = F-PRE-R15-01 (public solver 入口绕过 R14 fail-closed); r16 = F-PRE-R16-01 (external_boundary producer-free) + F-PRE-R16-02 (raw cycle solver 缺 group-local role contract); r17 = F-PRE-R17-01 (direct context mapping key vs 对象内 id 别名绕过 R16-01) + F-PRE-R17-02 (raw cycle local contract 缺反向声明检查); **r18 = 真 Pro 抓 3 个 hardening**, 已修在本包内并已入 LOCK (`PROJECT_LOCK.md:154`, **F-PRE-R18-01 / -02 / -03, conditional hardening**):

- **F-PRE-R18-01** (hardening, raw cycle 入口未继承 R17 identity guard): raw `_solve_cycle_group_exact()` 之前只跑 group-local 检查, 没跑 R17-01 的 `_validate_context_mapping_id_consistency()`。一个手搓 context 把 `commodity_roles['buckwheat'].commodity_id` 设成 `'buckwheat_seed'`、或 group recipe 的 key 与 inner `recipe_id` 不一致, 经 raw `solve_cycle_group_exact()` 仍能解 (R17-02 反向扫描只拦 inner id 落在 internal 之外的情况, 别名到另一个组内 id 仍放过)。修在: raw `_solve_cycle_group_exact()` 在 matrix 构造前先跑 `_validate_context_mapping_id_consistency(context)` (`src/interchange/preprocess_context.py:634`); 同时 id-type pass 扩到 `facility_templates` key / recipe template ref / target `final_recipe_id` / role `cycle_group` / utility `facility_type` (`:378-430`)。回归 `src/tests/test_preprocess_cycle_solver.py` + `src/tests/test_preprocess_context.py`。

- **F-PRE-R18-02** (hardening, machine-count ceil 的 float-epsilon 下偏): `ceil_machine_count()` 之前走 `ceil(float(normalize_artifact_number(value)) - 1e-9)` —— 一个落在 `(N, N+1e-9]` 的精确非整数 machine_run 会被抹回 `N`, 少算一台机器 (undercount = false-FEASIBLE 方向, 与 binding 面 F-BIND-R10-01 同型)。修在: `ceil_machine_count()` 改走 `_to_fraction()` + 有理数取整 (`src/preprocess/demand_solver.py:80-84`); proof-critical 再生路径 (`demand_solver.py` main / `scripts/build_current_preprocess_context.py`) 喂精确 `Fraction`。Canonical 可达性: `solve_demands_exact(load_default_preprocess_context())` 的 machine runs 全是整数 / 半整数 / 一个 `11/4`, 无值落在 epsilon band, 再生 machine total 仍 219, frozen artifact diff 仍 6/6。

- **F-PRE-R18-03** (hardening, direct recipe 数值 contract 未镜像 schema 正性): source schema 要求 `ticks_per_cycle >= 1` 且每个 recipe input/output amount `> 0` (`rules/canonical_rules.schema.json`), 但 direct `validate_preprocess_context()` 之前没复检。手搓把 `packaging_battery.outputs['valley_battery']` 改成 0 / -1 能过 validation; `solve_demands_exact()` 随后 seed 一个 0/负 target rate, `_backpropagate_non_cycle_demands()` 经 `if demand_rate <= 0: continue` (`demand_solver.py:288`) 直接跳过, 漏掉 `packaging_battery` 及上游机器 (false-FEASIBLE 方向)。修在: `validate_preprocess_context()` 在 producer-index 构造前调 `_validate_recipe_rate_contract(context)` (`:253`, helper 在 `:468-485`); raw cycle solve 对 group recipes 也跑同 contract (`:640`)。

三条款均 conditional hardening, **canonical 恒自洽** (build 从一个循环变量派生 dict key 与 inner id, canonical rate 永不撞 epsilon band, canonical recipe 全正), 仅手搓 dataclass / future data 可达, 是 **direct/raw-entry + future-rate 加固, 不是 certified-path soundness reset**。

**本轮 r19 = F-PRE-R18-01/02/03 修复确认 + 残留攻击角**。修复点本身已 lock, **不重报已修项本身**; 本轮把这三个修复【钉成攻击面】, 钉两条主线:

1. **validation-vs-consumption 不对称残留**: 继续找 public / raw / direct 入口里「validation 看见 / 检查的不变量 ≠ consumption 实际依赖的不变量」这类不对称 —— R18-01 (raw 入口漏继承 full-validation 的 guard) / R18-03 (validation 漏复检 schema 正性 contract) 是这族的最新两例, 找它们的同型残留。
2. **float-epsilon / 截断取整族残留**: R18-02 修了 `ceil_machine_count` 的下偏 ceil, 但 **`normalize_artifact_number()` (`src/preprocess/demand_solver.py:43-62`) 仍带 `INTEGER_SNAP_TOLERANCE = 1e-9` 的 near-integer snap 路径** (`round(numeric)` + `abs(numeric - rounded_int) <= 1e-9`)。继续找其它 `1e-9` / `EPSILON` / `float()` 强转 / `round()` 截断点, 判是否在 proof-critical 工件路径上、canonical 是否可达。

注意: 本包含其它审查面同期落的修复 (cuts / master-geometry / benders / binding / scheduler / campaign 等各面有自己的线), 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-PRE-R18-01 修复确认 + raw 入口 guard 继承完备性 (攻击面, 本轮主体之一)

R18-01 的根因形态 = **raw `_solve_cycle_group_exact()` 历史上是 full validation `validate_preprocess_context()` 的「子集入口」, 只跑了部分本地检查; 每当 full validation 新增一道 proof-critical 门 (R17-01 的 mapping identity guard), raw 入口默认不继承, 直到被单独补焊**。把这个形态当模板深挖:

① **raw 入口现在跑了哪些门, 漏了哪些**: full `validate_preprocess_context()` (`src/interchange/preprocess_context.py:240-374`) 的门序列是: mapping identity (`:246`) → template ref (`:248-252`) → recipe rate contract (`:253`) → single-output (`:254`) → producer index + target/role 语义 (`:256-327`) → cycle-internal ownership 全局 (`:318`) → 逐 group 方阵/recipe-exist/role/net-export/IO 闭包/unit-basis probe (`:329-359`) → 非 cycle 多 producer (`:361-366`) → utility (`:368-374`)。raw `_solve_cycle_group_exact()` (`:629-643`) 现在跑: mapping identity (`:634`) → recipe rate contract for group recipes (`:640`) → single-output for group recipes (`:641`) → cycle-internal ownership `group_ids={group_id}` (`:642`) → local contract (`:643`) → IO 闭包 (`:645`)。**问: full validation 里有没有第三道 proof-critical 门, raw 入口仍没继承, 而 raw 求解的矩阵/RHS/解的正确性又依赖它**? 重点核对:
   - **target/role 语义检查** (`:262-327`, 含 R16-01 external_boundary producer-free `:286`、generic_input target 对应 `:291-300`、cycle_group 声明一致 `:301-316`): raw 入口完全没跑。但 raw 求解只从 `group.recipes` / `group.internal_commodities` 构矩阵 (`:676-685`) —— 这些语义门里有没有哪一条, 一旦 violated 会让**本 group 的矩阵/解**被算错 (不只是「别的 commodity 语义脏」)? 给 file:line 论证: raw 单 group 解是否真的不依赖任何 target/role 全局语义门成立。
   - **`recipe.template not in context.facility_templates`** (`:248-252`): raw 入口没检查 group recipe 的 template 引用。这会影响 raw 解吗 (矩阵只用 `output_rate`/`input_rate`, 不碰 template)? 还是纯下游 (instance 展开才用 template) 因此 raw 解 sound 但 direct caller 拿解去展开会炸? 判这是 raw-solve soundness 缝还是纯下游 availability。
   - 给 probe 或论证: raw 入口当前门集合相对 full validation 的差集里, 是否有任何一条是 raw 解正确性的**必要前提**而未补。

② **R18-03 recipe-rate contract 的覆盖完备性**: `_validate_recipe_rate_contract()` (`:468-485`) 现在检 `ticks_per_cycle` 是正 int + 每个 input/output amount `> 0`。full validation 对**全部** recipe 跑 (`:253`), raw 对 **group recipes** 跑 (`:640`)。问:
   - **non-group recipe 的非正 rate 在 raw 路径有没有未检消费点**? raw 求解只用 group recipe, 所以 group 外 recipe 的脏 rate 不进 raw 矩阵 —— 但 `build_producer_index()` (`:444-452`) 在 full validation 里登记**全部** recipe 的 outputs。raw 入口不建 producer index, 因此 group 外 recipe 的非正 rate 在 raw 路径确实无消费点? 确认。
   - **`output_rate()` / `input_rate()` 对缺失 commodity 返回什么** (是否 0 / KeyError)? 若 `recipe.output_rate(c) - recipe.input_rate(c)` 在某 commodity 上一端取默认 0、另一端非 0, 矩阵 net_rate 是否正确? 这跟 rate 正性 contract 正交但属同一「矩阵元素来源」审查面。给 file:line。
   - R18-03 的 contract 用 `_to_fraction(amount)` (`:480`) 判正性。一个 amount 是 `float('nan')` / `float('inf')` 经 `_to_fraction` (`demand_solver.py:347-358`, float 走 `Fraction(str(value))`) 会怎样 (`Fraction('nan')` 抛 ValueError? `Fraction('inf')` 抛?)—— 这是 fail-closed (抛错) 还是 fail-open (混入矩阵)? 判 canonical 可达性 (canonical amount 全是有限正数) + 是否值得作 hardening 候选列出。

③ **R18-01 门是否引入误杀 (availability 回归)**: raw 入口新增 `_validate_context_mapping_id_consistency` + `_validate_recipe_rate_contract`。default canonical context 经 full validation 的 unit-basis probe (`:357-359`) 间接调 raw `_solve_cycle_group_exact()`, 也经 `solve_demands_exact` 真实 cycle 求解调用 —— 确认这些纯增门不把合法 canonical group 误判 invalid (false-INFEASIBLE 回归)。用 default pipeline probe 实证 (`solve_demands_exact(load_default_preprocess_context())` 跑通 + 6/6 frozen artifact diff 全匹配 + machine total 219)。

### Q2 F-PRE-R18-02 修复确认 + float-epsilon / 截断族残留 (攻击面, 本轮主体之二)

R18-02 的根因形态 = **proof-critical 数值在 float 域做 `- 1e-9` 下偏 ceil, 让恰好 fractionally 高于整数的精确值被误降一台**。R18-02 只修了 `ceil_machine_count`。把「float-epsilon / 截断取整在 proof-critical 工件路径」当模板深挖, **这是本轮最强候选**:

① **`normalize_artifact_number()` 的 near-integer snap (强候选)**: `normalize_artifact_number()` (`src/preprocess/demand_solver.py:43-62`) 仍带 `INTEGER_SNAP_TOLERANCE = 1e-9`: 对 Fraction 先短路 (denom==1 → int, 否则 `float(value)`), 然后 `rounded_int = round(numeric); if abs(numeric - rounded_int) <= 1e-9: return int(rounded_int)`。问:
   - 这个 snap **把 `N + 1e-10` 和 `N - 1e-10` 都吸到 `N`** —— 它消费的是 `flows` (commodity_demands.json) 与 `port_budget` 的数字 (`save_preprocessed_artifacts` 经 `normalize_json_numbers` → `normalize_artifact_number`, `demand_solver.py:65-77` + `:225-228`; `generate_port_budget` 直接调 `normalize_artifact_number` on `source_req`/`blue_iron_req`/`total_req`, `:152-154`)。这些工件里有没有 proof-critical 数字, 经此 snap 后会**向下**偏 (例如一个真实需求 `N + 1e-10` 个 boundary port 被 snap 成 `N`, 漏一个 port 供给 = false-FEASIBLE 方向)? 还是这些工件全在 certified runtime 的消费闭包外 (r7/r12 已审 machine_counts/port_budget/commodity_demands 在 hash 闭包外、certified runtime 不消费)? 给 file:line 论证: `normalize_artifact_number` 的输出落到哪些工件、哪些工件进 certified 消费、canonical 数据下有没有值落在 `(N - 1e-9, N) ∪ (N, N + 1e-9]` 的 snap band。
   - 与 R18-02 的判读对照: R18-02 之所以是 latent, 是因为 `ceil_machine_count` 现在走精确 Fraction。`normalize_artifact_number` 对 **non-integer-denominator Fraction** 先 `float(value)` 再 snap (`:48-49`) —— 这一步把精确有理数降成 float 再判 1e-9, 是否是 R18-02 同型缝在 artifact-number 路径的残留? 明确判: 是 (a) canonical latent 但值得 hardening 候选, 还是 (b) 设计上故意的 artifact-boundary 容差 (因为这些工件不进 certified proof, 只是人读的 JSON)? 拿不准就两种判读都给, 标可达性。

② **`generate_port_budget` 的 `float(total_req) <= 52.0 + EPSILON` 比较 (`:167`)**: 52 口预算的 FEASIBLE/INFEASIBLE 状态由 `float(total_req) <= 52.0 + EPSILON` 决定 (`EPSILON = 1e-9`)。问: 这个 `status` 字段进 certified 消费闭包吗? 一个 `total_req == 52 + 5e-10` 会被判 FEASIBLE (因 `+ EPSILON` 放宽), 这是 false-FEASIBLE 方向 —— 但 canonical total_req 是确定整数 (`source_ore + blue_iron_ore`), 永不落在边界 band。判: 是 latent 还是有真实消费者。若 `status` 字段无 certified 消费者 (只是工件里的诊断字段), 明确说不属 soundness。

③ **`generate_generic_io_requirements` 的 `> 0` float 门 (`:184`/`:190`)**: `required_generic_outputs` / `required_generic_inputs` 用 `_mapping_get_fraction(flows, commodity_id) > 0` 过滤 commodity, 且 outputs 用 `ceil_machine_count(...)`。问:
   - `_mapping_get_fraction` 返回 Fraction 还是 float? 若 Fraction, `> 0` 是精确比较 (安全); 若 float, 一个真实正需求被 float 误差吃成 `0.0` 会漏掉一个 generic slot (undercount = false-FEASIBLE)。给 file:line 确认 `_mapping_get_fraction` 的返回类型与 `> 0` 比较口径。
   - `required_generic_outputs` 现在用 R18-02 修好的 `ceil_machine_count` (`:182`), 确认这条路径已享 R18-02 的精确 ceil (即 R18-02 的修复真的覆盖到 generic_io 再生, 不只是 machine_counts)。这是 R18-02 修复完备性的一部分。

④ **R18-02 修复是否真覆盖所有 proof-critical ceil 调用点**: grep 全 preprocess 链的 `ceil` / `math.ceil` / `int(...)` 截断, 列出每个调用点, 判它消费的是 Fraction (已享精确取整) 还是 float (残留下偏风险)。R18-02 改了 `ceil_machine_count` 本体, 但调用它的两个再生路径 (`generate_ceil_machine_counts` `:132-136` 全工件、`generate_generic_io_requirements` `:182` generic outputs) 是否都喂精确 Fraction (来自 `solve_demands_exact` 而非 float `solve_demands`)? 给 file:line: proof-critical 再生入口 (`demand_solver.py` main `:234-238`、`scripts/build_current_preprocess_context.py`) 是否全走 `solve_demands_exact` (Fraction) 而非 `solve_demands` (float)。

### Q3 R17/R16/R15/R14/R13/R12/R11 维持轻确认

r18 补丁动了三处: raw `_solve_cycle_group_exact` 入口 (新增 mapping identity + recipe rate guard, `:634`/`:640`) + `validate_preprocess_context` (新增 `_validate_recipe_rate_contract` `:253`) + `ceil_machine_count` 重写 (`demand_solver.py:80-84`)。轻扫确认这些改动**没有破坏**既有门:
- R17-01 (mapping key==inner-id, `_validate_context_mapping_id_consistency` `:378-430`, 在 full validation `:246` 与 raw `:634` 两端)
- R17-02 (raw cycle local contract 反向扫描, `_validate_cycle_group_local_contract` `:556-567`)
- R16-01 (external_boundary producer-free, canonical 端 `src/rules/semantic_validator.py:154-158` + context 端 `src/interchange/preprocess_context.py:286-290`)
- R16-02 (raw cycle group-local contract 正向, `:524-555`)
- R15-01 (public solver 重验入口, `solve_demands_exact` 在 `src/preprocess/demand_solver.py:106` 调 `validate_preprocess_context`)
- R14-01 (单输出锁 `_validate_single_output_recipes` `:488-498`) / R14-02 (cycle-internal ownership `_validate_cycle_internal_output_ownership` `:501-521`)
- R13-01 (recipe I/O 闭包 `_cycle_group_recipe_io_outside_internal` `:700+`) / R12-01 (RHS membership 双端 `:651-674`) / R11-03 (cycle solve 非负证明 `:687-693`)
确认 r18 重构后这些门仍完好, 没被同期改动削弱或绕过 (尤其新增的 `_validate_recipe_rate_contract` 与 `ceil_machine_count` 重写没改变既有门的语义)。

### Q4 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面**当前最薄弱**的点深挖, **换新角度** (别复读 r1-r18 已审判读)。本面已审 r1-r18, 覆盖: schema 入口 / strict JSON / 几何契约 / cycle 闭包 / 实例展开 / 工件交叉一致性 / demand 数学 / public 入口重验 / 终端边界 producer-free / raw cycle 本地 contract / direct context key==id 别名 / cycle role 双向闭包 / raw 入口 guard 继承 / machine-count 精确取整 / direct recipe 正性 contract。残留薄弱候选 (非限定, 仅供启发):

- **role 完整性不变量 (r18 之后仍未被触及的横切)**: validation 是否强制「每个 target commodity、每个 recipe-reachable commodity 都有显式 role 条目」, 还是依赖 `commodity_role()` 的合成默认 (`src/interchange/preprocess_context.py:139-148`, 缺失 role → `source_kind=None, sink_kind='none', cycle_group=None`, **从不抛错**)? r18 修的是 mapping identity (key==id) 与 recipe 正性, 但**「role 条目存在性」本身**没被钉。问: 一个真实 external_boundary 语义的 commodity 因没显式 role 被 `commodity_role()` 合成成 `source_kind=None` —— 在 `_backpropagate_non_cycle_demands` (`demand_solver.py:292-301`) 里它不命中 `cycle_group` 分支、不命中 `external_boundary` 分支, 直接去 `producer_index.get()` 找 producer。若它**确有** producer recipe (本该 external_boundary 终止反推, 现却继续往上反推) → 多算机器 (false-INFEASIBLE 方向, over-count) 还是少算 (取决于拓扑)? 若它**没有** producer → 抛 `commodity {c!r} has positive demand but no producer recipe` (`:301`, fail-closed)。逐分支判: 合成默认 role 在每条 demand 路径上是 fail-closed、语义中性、还是某条路径上把语义算错? 给 file:line + probe。注意: full validation 对 **target** commodity 强制 role 存在 (`:320-327`)、对 **cycle internal** commodity 强制 role 存在 (`:341-346`), 但**中间非 cycle producer-owned commodity** 不强制显式 role —— 这类靠 `producer_index` 命中、role 走合成默认, 判这是否 sound (producer-owned 中间品本就该靠 producer 反推, 合成 role 的 `source_kind=None` 不影响)。

- **`build_producer_index` 的 key 口径 vs R16-01 成员判断 (r17 之后仍值得一钉的口径缝)**: `build_producer_index()` (`:444-452`) 的 key 来自 `recipe.outputs` 的裸 key (未 `str()` 强转, `:447-448`)。R17-01 的 mapping identity guard 现在强制 recipe output key 是 str (`:391-392`)。R16-01 的 `role.commodity_id in producers` 成员判断 (`:286`) 现在两端都 str (role.commodity_id 经 `:403` 强制 str)。**确认这条「producer index key 来自 recipe.outputs str-forced key」↔「R16-01 成员判断用 role.commodity_id str」在 R17-01 门焊死后真的口径闭合**, 无残留 int/str / 别名缝。这是 R17-01 修复完备性在 producer-index 侧的收尾确认 (上轮 Q1② 已问过但值得在 r18 重构后复核一次, 因为 r18 在 producer-index 构造前**插了** `_validate_recipe_rate_contract` `:253`, 确认插入位置没改变 R17-01 门已先于 producer-index 跑的顺序 `:246` < `:256`)。

- **`solve_demands` (float) vs `solve_demands_exact` (Fraction) 的混用面**: public `solve_demands()` (`demand_solver.py:87-99`) 返回 float dict (兼容老 tests/render)。问: 有没有 proof-critical 工件再生路径误用了 float 版 `solve_demands` 而非 `solve_demands_exact`, 让 R18-02 的精确 ceil 收益被 float 入口提前丢失? 列出所有 `solve_demands(` (float) 调用点, 逐个判是不是 proof-critical (若是 render/诊断/老 test 则无所谓; 若是工件再生则是 R18-02 修复的回归缝)。

- **实例展开 / instance id 稳定性在 ceil 边界**: backprop 解出的 machine_runs → R18-02 精确 ceil → instance 展开 (266/326) 的口径在边界 (run_rate 恰好整数 / 极小分数) 上是否 sound。R18-02 改了 ceil 本体, 确认 instance 计数 (`mandatory_exact_instance_count=266`, `all_instance_count=326`) 在修复前后不变 (frozen 对拍)。

说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical / 266 口径 / min_side>=6 admissibility / omni_wireless / 52-Port 不变量, owner 已定); r1-r18 已修 finding 与已审结论本身 (重复报不算 finding)。
- 已 lock 的本面条款: F-PRE-R10-01/02、R11-01/02/03、R12-01、R13-01、R14-01/02、R15-01、R16-01/02、R17-01/02、**R18-01/02/03** (见 `PROJECT_LOCK.md` 对应行, R18 在 `:154`, R17 在 `:146`, R10-R16 在 `:110-116`)。这些是**攻击面的基线**, 找它们的同型残留/不完备可以报, 复述它们本身不可以。
- master / binding / campaign / scheduler / routing / cuts 各面 (各自有线)。**本轮兄弟面同期落的 hardening 补丁** (binding F-BIND-R11-01/02 / cuts CUT-R15-H1 / scheduler F-PS-R7-01 / campaign F-CAM-R6-01 / master-geometry F-GM-R12/R13-PB / benders F-BL-R8/R9 等) 不在本轮重报。**特别注意**: F-BIND-R11-02 (binding 面) 与 F-PRE-R18-02 (本面) **是同一个 `ceil_machine_count` 修复的两面投影** —— 本轮**不重报** `ceil_machine_count` 本体; 若发现**其它**未被 R18-02 覆盖的 float-epsilon ceil/snap 缝 (见 Q2 ① `normalize_artifact_number`), 那是**本面新发现**, 可作 invariant-hardening 候选报, 但要明确标「与 F-PRE-R18-02 / F-BIND-R10-01 同型」并判 canonical 可达性。怀疑跨面时交叉引述 `PROJECT_LOCK.md` 对应契约条款, 不在本轮重证。
- **env-gated / exploratory 行为不属 P1.2 soundness**: `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_BYPASS_*` 等全部 env-gated, 默认 off, 非 certified 路径; 这些后端的 false-FEASIBLE 是 env-gated backend hardening, 不是 certified soundness reset。
- `candidate_placements.json` 外置再生撕裂 (已随包并校验, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。部分再生撕裂由 golden tests 抓 (设计边界); machine_counts/port_budget/commodity_demands 在 hash 闭包外但 certified runtime 不消费 (r7/r12 已审)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3092, **数目以实跑为准, 硬不变量 = 0 failed**); 跑不完就跑专项 + 如实声明跑了哪些 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`; 沙盒插件干扰可 `-p no:ddtrace -p no:cov -p no:json-report -p no:metadata`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations anchored)。
- 工件一致性自验 (可选但推荐): `python scripts/build_current_preprocess_context.py --output <tmp>/ctx.json --diff-json <tmp>/diff.json --diff-md <tmp>/diff.md` 应 `all_match: true` (6/6 frozen artifacts), `mandatory_exact_instance_count=266`, `all_instance_count=326`, `generic_output_slots=52`, `generic_input_slots=0`。
- **finding 必须带可复现 probe 或 file:line 严谨论证**; **实证推翻你的怀疑就不要报**。

## 严重度纪律

- **false-CERTIFIED / false-FEASIBLE / undercount (该有的机器/供料被漏掉) on canonical 数据 + 默认 env = soundness reset** —— P1.2 闭环只认这个可达的, 标 HIGH。
- **env-gated / conditional / direct-entry 才可达 / false-INFEASIBLE (合法 context 被误杀) = hardening / availability** —— 不是闭环 blocker, **明确标 "hardening / 仅 direct-entry 可达 / canonical latent"**。R18-01/02/03 本身就是 conditional hardening (canonical 恒自洽, 仅手搓 dataclass / future-rate 可达); 本轮若再挖到同类, 同样按这个口径标, 别夸大成 certified soundness reset。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 分段判读: Q1 (R18-01 三点: raw 入口 guard 继承完备 / R18-03 rate-contract 覆盖 / 不误杀) + Q2 (R18-02 四点: `normalize_artifact_number` snap 残留 / port_budget float 比较 / generic_io `> 0` 门 / ceil 调用点全覆盖) + Q3 (R11-R17 维持) + Q4 (自由攻击角选点与结论, 尤其 role 完整性不变量 + `normalize_artifact_number` 的 canonical 可达性判读)。
- 前 18 轮的结论不代表本轮默认干净; 这是**真 Pro 确认轮, 独立下结论**。按你自己的独立判断给最终判读。

## 范围边界

- 重点 = F-PRE-R18-01/02/03 修复确认 (同型残留/反向缺陷/不完备) + 残留 validation-vs-consumption 不对称 + float-epsilon 族 + 自由攻击角; 其余 7 面不审, 跨面只列「不审」交叉引 LOCK 条款。
