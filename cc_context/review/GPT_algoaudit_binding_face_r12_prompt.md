# 终末地 IndustrialPlanner 精确求解器 — binding 面 round 12 (真 Pro 确认轮·重新坐实 R11-01 未落地的 JSON-float 入口缝 + 提供干净树独立补丁 + binding 精度链残留再猎取 + 又一次独立全面 soundness 重审)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_0590f9ca.zip`, sha256 `0590f9ca30aac5bb7afe18945eb36d347ea8b0c5b467fd6baff4679eff8c5234`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), **干净 git 树快照 (HEAD `7fec29a`, rounds 1+2 的全部已验收修复都已合入 —— 这是带修复的新树, 不是修复前的树)**。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生; 仍不准伪造/改写。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → **binding 端口绑定** → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **binding 子问题 (端口绑定 CP-SAT 模型)** (`src/models/binding_subproblem.py` 为核, 配 `src/models/port_binding.py` 域枚举引擎 / `src/preprocess/operation_profiles.py` 容量 rate→slot 取整 / `src/search/benders_loop.py` 的 binding 注入与 safe-reject ladder), 上溯到喂给它精确 rate/capacity 的 **JSON 源装载入口** (`src/io/strict_json.py` + `src/interchange/preprocess_context.py` 的 path/default loader)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = binding 子问题是否**忠实编码规则**: 端口 exact-one 商品绑定 / 容量 (rate→slot 取整) / generic 通用槽 + wireless 虚拟槽 / `__unused__` 哨兵 / binding→routing 接口 (`extract_port_specs`) / binding-local safe-reject ladder / generic I/O 需求工件 (`load_generic_io_requirements`) 的 fail-closed 装载 / **以及喂给 binding 精确容量链的 JSON 源 token 是否在入口处保精度**。只管 binding 选出的 port_specs 既不 stricter-than-rule (false-INFEASIBLE) 也不 looser-than-rule (false-FEASIBLE)。历史:

- r1-r7 = thinking/更早模型, 抓 F-BIND-R1-01/R1-02 (哨兵 + loader fail-open)、R2-01/R2-02 (master 侧 loader + JSON 重复 key)、R3-01..05/R4-01/R5-01 (proof 单解析单快照封印); r6/r7 = 零 finding (达 thinking 饱和下沿)。
- r8 = 真 Pro 首轮重审, 抓 F-BIND-R8-01 (conditional-HIGH overload fallback) / F-BIND-R8-02 (LOW generic-input 完备性), 均已修。
- r9 = 真 Pro 确认轮, 在 R8-02 同族里再抓 F-BIND-R9-01 (LOW availability, output-only 工件绕过完备性校验), 已修。
- r10 = 真 Pro 确认轮, 抓 F-BIND-R10-01 (conditional HIGH soundness, latent-on-canonical): `_rate_to_slots()` 用 `ceil(rate/capacity - 1e-9)` 把略高于整数容量倍数的 rate 向下取整一槽 → false-FEASIBLE 方向。已修 (改有理数 `Fraction` ceiling)。lock:147。
- **r11 = 真 Pro 确认轮, 在 R10-01 容量精度链同族里抓出两个残留 (本轮的直接前因, 务必读懂)**:
  - **F-BIND-R11-01 (conditional HIGH, latent-on-canonical)** = canonical/preprocess 源 JSON 的 float token 先被解析成**二进制 `float`**, 再 `Fraction(str(float))`, 把某些合法十进制边界值在入口就吞成整数, 绕过 R10 的 exact ceiling → 少要一个 binding slot, false-FEASIBLE 方向。建议修法: 给 strict JSON loader 加 `exact_decimal` 模式 (源 JSON 的 float token 保留为 `Decimal`), 再由 `_to_fraction()` exact 转 `Fraction`。
  - **F-BIND-R11-02 (conditional HIGH, latent-on-canonical)** = `demand_solver.ceil_machine_count()` 仍用 `ceil(float(x) - 1e-9)` 家族公式, 生成 `required_generic_outputs` 时可少要一个 generic output 槽 (与 R10-01、与 preprocess 面的 F-PRE-R18-02 同型)。修法: 改有理数 ceiling + 再生主链走 `solve_demands_exact()`。

**本轮 r12 的核心性质 (关键, 与往轮不同):** r11 的两条 finding **落地情况不对称**:

- **F-BIND-R11-02 (ceil) 已落地**: 它与 preprocess 面 F-PRE-R18-02 是同一个 `ceil_machine_count` 修复, 随 preprocess r18 一起合入了本包 (HEAD `7fec29a`)。**本轮不要重报它** —— 除非你独立发现该修复**不完备或引入了新缺陷**。
- **F-BIND-R11-01 (strict_json Decimal loader) 至今【未落地】**: 它的 patch 与 preprocess 面 R11-01 重叠, 当时被推迟; 本包 HEAD `7fec29a` 干净树上**这条修复并不在代码里**。⚠️ 注意 `PROJECT_LOCK.md:154` 的散文括注**声称** R11-01「a strict-JSON Decimal source loader … is a separate conditional-latent hardening landed on its own (已单独落地)」—— 这句**散文先于代码**, 不要把它当作已落地的事实。**请你独立对当前 HEAD `7fec29a` 的源码自核, 自己判定 R11-01 描述的缺陷是否仍然真实存在**, 不要因为 lock 说"已落地"就接受、也不要因为我说"未落地"就接受 —— 以你在快照源码上的实证为准。

**所以本轮 r12 的三个任务 (按优先级):**

1. **[最高优先] 重新坐实 F-BIND-R11-01 是否仍存在**: 在当前 HEAD `7fec29a` 干净树上, 独立验证: canonical/preprocess 源 JSON 里的高精度十进制 float token 是否**仍能**在 `strict_json` → `preprocess_context` 的装载链上被降为二进制 float, 从而绕过 R10 的 exact `Fraction` ceiling, 让 `build_operation_port_profiles()` / binding slot profile 少算槽 (false-FEASIBLE 方向)? 给**可复现 probe** (例如临时把 `rules/canonical_rules.json` 某条合法整数 amount 改成 `1.0000000000000001` 后, 比对装载出的槽数 = 1 还是 2; 你的 probe 不得污染随包工件, 用临时副本/临时改写后还原)。
2. **[若仍存在] 给当前 HEAD `7fec29a` 干净树的独立补丁**: 只改 **`src/io/strict_json.py`** (新增不破坏既有调用方的 exact-decimal 装载模式) **+ 其在 binding/preprocess-context 精确链上的消费点** (`src/interchange/preprocess_context.py` 的 `load_default_preprocess_context` / `load_preprocess_context_from_paths` 装载 canonical/plan 时改走 exact-decimal, `_to_fraction()` 支持 `Decimal→Fraction`)。**严禁触碰**已被 preprocess r18 改过的 `demand_solver.ceil_machine_count` / `solve_demands_exact` 接线 / `preprocess_context` 里属于 R18 的部分 —— 那些已落地, 重复改会冲突。补丁须 `patch -p1 --dry-run` 可过 (LF 行尾), 默认 strict loader 行为不变 (`1e309` 仍 fail-closed 拒绝, 现有 8 obligations + 全量 pytest 不回归), 附最小回归锚 (源 JSON 十进制边界值不降精度 + 默认模式不变)。
3. **[并行] binding 精度链其它残留再猎取 + 又一次独立全面 soundness 重审**: R11-01/R11-02 修了 JSON 入口 + generic-output 再生两处。请把**整条 binding 容量/需求精度链**当家族, 独立枚举还有没有**别的** float-epsilon / 浮点比较 / 截断取整 / 精度损失点 (见下 Q2); 并换一个新角度对本面核心 soundness 不变量做又一次全面重审 (见下 Q3), 别复读 r10/r11 已下的判读结论。

## 本面核心 soundness 不变量清单 (独立全面重审的锚点)

逐条**独立从规则推导预期语义再比对实现** (勿从实现学语义 —— F-RT-R2-01 教训: diff-fuzz oracle 抄了 solver 的反相 key, 对那一类盲 900 实例):

1. **端口 exact-one 商品绑定**: 每个物理端口/虚拟槽恰好绑一个商品或 `__unused__` 哨兵; 不存在跨 commodity 共享同一物理端口 cell 叠加吞吐 (false-FEASIBLE)。
2. **容量 rate→slot 取整 + 其源精度 (本轮 R11-01 焦点)**: `_rate_to_slots()` (`operation_profiles.py`) 的有理数 ceiling 既不少给槽 (false-FEASIBLE) 也不多要槽 (false-INFEASIBLE); **且喂给它的 rate/capacity 必须从源 JSON 起就是 exact 有理数** —— 任何把源 float token 先降为二进制 float 再转 Fraction 的入口都会让 R10 的 exact ceiling 形同虚设。
3. **generic 通用槽 + wireless 虚拟槽语义**: generic-output 只接 `boundary_io`/`protocol_core`, generic-input 只接 `wireless_sink`; 每 slot `ExactlyOne(real_commodities + __unused__)`; 需求约束 `sum(vars)==required` (含 `required==0` 强制全 false)。
4. **`__unused__` 哨兵精确计数**: 哨兵 binding-internal, 永不进 `extract_port_specs` / 任何 routing/flow 面; reserved name 在需求 loader 被拒; `R<S`/`R=S`/`R>S` 三态计数正确 (不依赖当前 52=52 满额巧合)。
5. **routing-free 终品对偶排除**: canonical `sink_kind==generic_input` 终品 (`qiaoyu_capsule`/`valley_battery`) 无线消费, 其 producer **输出**口必须从 `extract_port_specs()` 排除; **输入**口 (原料) 保留 routed。排除必须在**每个** routability 消费侧成立。
6. **generic I/O 需求工件 fail-closed 装载**: section 缺失/类型错/负数/重复 key/非有限数/reserved 哨兵/角色错全 fail-closed; 非空工件必须正槽覆盖所有 canonical generic_input 终品 (R8-02/R9-01)。
7. **binding-local safe-reject ladder**: `front_blocked`/`relaxed_disconnected` 先加 binding-level nogood 并枚举剩余 alternatives, 只有 binding CP-SAT `INFEASIBLE` (overload env-on 时还需 env-off replay 仍 INFEASIBLE) 才允许铸 whole-layout nogood; budget exhaustion 永不当 exhaustion proof。

## 审查重点 (行号基于本包 HEAD `7fec29a` 的源码, 解包后请自核, 别照抄)

### Q1 [重新坐实 R11-01 JSON-float 入口缝是否仍存在 + (若仍在) 给干净树独立补丁, 最高优先]

待审入口链 (HEAD `7fec29a` 自核):

- `src/io/strict_json.py:29-33` `_parse_json_float()`: 当前是否仍返回 Python **二进制 `float`** (即 `parse_float=float`)? 有没有任何 `exact_decimal` / `Decimal` 装载模式? (我方读到的现状是: 仍是 `float(value)` + `math.isfinite` 检查, **没有** Decimal 模式 —— 请你独立确认 / 推翻。)
- `src/interchange/preprocess_context.py:592-597` `load_default_preprocess_context()` 与 `:600-611` `load_preprocess_context_from_paths()`: 是否都直接 `load_strict_json(...)` 装 `canonical_rules.json` / `preprocess_plan.json`, 拿到的 number 已是二进制 float?
- `src/interchange/preprocess_context.py:860-871` `_to_fraction()`: float 分支是否仍 `Fraction(str(value))` (即对**已经损失精度的二进制 float** 做 `str()`, 而非对源 lexeme)?
- `src/preprocess/operation_profiles.py:78-110` `build_operation_port_profiles()` 用这个 `PreprocessContext` 构造 binding 侧 `OperationPortProfile` → `_rate_to_slots()` 拿到的"精确 Fraction"实际上是**入口已被二进制 float 污染过的值**。

请独立判定并给结论:

- **(a) 缺陷是否仍真实存在**: 给可复现 probe。参考做法 —— 把 `rules/canonical_rules.json` 里某条 amount 从 `1` 临时改成 `1.0000000000000001` (这是合法 JSON, 规则真值 = `10000000000000001/10000000000000000`, 在 capacity `1` 下需 **2** 槽), 走 `load_preprocess_context_from_paths()` + `build_operation_port_profiles()`, 看装出的槽数。若得 1 槽 = 缺陷仍在 (false-FEASIBLE 方向); 若得 2 槽 = 已修。**probe 必须用临时副本或改完即还原, 不得留下对随包工件的污染**。
- **(b) 是 certified 主链可达还是仅 future/owner-gated 触发**: 明确 —— 当前随包 canonical 17 recipe 的 amount/rate 集为 `{1/5, 1, 2, 3}` + capacity `1.0`, 都是"干净"整数/简单小数, 不落进二进制不可表示的高精度十进制边界带, 所以这是 **latent-on-canonical** (打包数据下不触发, 方向是 false-FEASIBLE/false-CERTIFIED)。请独立复核这个 latency 判定: 现有随包 canonical 源里**确实**没有任何一个 amount/rate/capacity 字面量在 `json.loads` 后 `float != Fraction(str(原 lexeme))` (即没有现成被吞的边界值)? 给你扫的依据。
- **(c) 干净树独立补丁 (若 (a) 确认缺陷仍在)**: 只改 `strict_json.py` (加一个**不改默认行为**的 exact-decimal 装载入口, 例如 `loads_strict_json(text, *, exact_decimal=False)` / 单独的 `load_strict_json_exact_decimal()`, float token → `Decimal`, 非有限仍 raise, 重复 key / NaN/Infinity 仍拒) + `preprocess_context.py` 的两个 path/default loader 改走该 exact-decimal 入口 + `_to_fraction()` 加 `Decimal` 分支 (`Fraction(Decimal)` 是精确的)。**不要碰** `demand_solver.ceil_machine_count` / `solve_demands_exact` 接线 / 任何属于 preprocess R18 的部分 (已落地, 改了会冲突)。给 unified diff + 最小回归锚: ① 源 JSON 写 `1.0000000000000001` 经 exact-decimal loader → `Fraction(10000000000000001, 10000000000000000)` (不降精度) → 该 recipe 槽数 = 2; ② 默认 `load_strict_json` (非 exact-decimal) 行为与 `1e309` fail-closed 不变。补丁后请跑该 probe + binding/preprocess targeted 集合证明不回归。

> 注意跨面边界: rate/容量字面量的**值本身是否正确**属 preprocess/canonical 真源面 (不审); 本面只验 **binding 精确容量链从源 token 到 slot 全程不丢精度**。但 R11-01 的入口缝是 binding 精度链的直接上游 (binding profile 直接消费 `PreprocessContext` 的 rate), 故归本面。修补只动 strict_json + 其 binding-链消费点, 不重定义 canonical 数值真源。

### Q2 [binding 容量/需求精度链同型残留再猎取 (float / epsilon / 截断取整 家族枚举) — 核心]

R10-01 修了 `_rate_to_slots` 一处取整, R11-01 (待落地) 修源 JSON 入口, R11-02 (已落地) 修 `ceil_machine_count`。请把**整条 binding 容量/需求精度链**当家族, 独立枚举还有没有**别的** float-epsilon / 浮点比较 / 截断取整 / 精度损失点, 能诱发 false-FEASIBLE (少要槽) 或 false-INFEASIBLE (多要槽):

- (a) **离散化点全枚举**: 全仓 grep `_rate_to_slots` / `ceil_machine_count` 的所有调用方 + 任何**别的**把连续 rate/需求映射成离散槽数/端口数/机器数的地方 (`round()` / `int(float_expr)` / `>= float` / `<= float` / `math.ceil(float...)` / `- 1e-9` / `EPSILON`)。`operation_profiles.py` 顶部仍有 `EPSILON = 1e-9` 常量 (`:17`) —— 它现在还被谁消费? 是死代码还是仍潜伏在某条判定里? `demand_solver.py` 的 `EPSILON`/`INTEGER_SNAP_TOLERANCE = 1e-9` (`:38-39`)、`generate_port_budget` 的 status 判定 (`52.0000000005` 是否仍可能被判 feasible? r11 说补丁一并改了 exact 比较 —— 请核这部分**是否真随 R18 落地了**, 还是只在 R11 的未落地补丁里)。
- (b) **wireless-sink 槽数 + generic 槽数的整数性**: `_normalize_wireless_sink_generic_input_slots` (`binding_subproblem.py:82-99`) + `load_wireless_sink_generic_input_slots` (`:101-151`) 把 plan 里的 `wireless_sink.generic_input_slots` 装载成槽数。请核这条链是否对 float/bool/负数/非有限 fail-closed (一个写成 `3.0000000001` 的 plan 值若被 `int()` 截断成 3 而非 raise, 是同型缝)。**特别注意**: 若 R11-01 的 JSON-float 入口缝仍在, 那么 `wireless_sink.generic_input_slots` 这个 plan 值如果**本就是整数**写法 (`3`) 没问题, 但若有人写 `3.0` 经二进制 float → `int()` 是否仍 = 3 (无损), 写 `3.0000000001` 是否被 `_strict_nonnegative_int` 拒 (期望: 拒, 因为非整数 float)? 这条链与 R11-01 的入口装载是否共用同一个 strict_json (是 `load_strict_json` 还是另一路)? 给 file:line。
- (c) **`aggregate_*` 诊断路径的 float 累加 (R10-01 留下的 seam)**: `aggregate_commodity_rates` (`operation_profiles.py:148-163`) 对 `rate` 做 `float(rate) * count` (`:159/161`)。请回溯它的消费者: 这个 `float(Fraction)` 聚合产物**是否**被任何 certified proof 消费 (preprocess sizing gate / 容量校验 / master optional lower bound 推导)? 若只进诊断/telemetry → 非 soundness; 若进了判定 FEASIBLE/INFEASIBLE 或推导 demand 下界的 proof 路径 → float 累加误差可能在 266 实例规模放大成 off-by-one (高价值 finding)。区分 proof 消费 vs 诊断消费, 给 file:line。

### Q3 [R11-02 (已落地) 不完备性 + generic I/O loader 家族再确认 + 全面重审残余角度]

- (a) **R11-02 (已落地的 ceil 修复) 独立验证**: `demand_solver.ceil_machine_count()` (`:80-84`) 现在是 `(num + den - 1) // den` 有理数 ceiling + 主链 `main()` / `build_current_preprocess_context.py` 走 `solve_demands_exact()`。请独立判: ① 这个有理数 ceiling 在所有 `value > 0` 上恰好 = `ceil`, 无 off-by-one (整数边界 `Fraction(2,1)` → 2 不是 3)? ② `value <= 0` 时它**没有**早返回 0 (不像 `_rate_to_slots` 有 `<=0 → return 0`) —— `ceil_machine_count` 收到 0 或负 Fraction 会怎样 (机器数语义上 0 合法吗? 负数应 raise 还是 0?)，是否存在调用方喂 0/负值导致错误槽数? ③ 这个修复**自己**有没有引入新缝 (例如把某个合法的整数机器数算成 +1, 生成多余 generic output 槽 → false-INFEASIBLE 方向)?
- (b) **generic I/O loader 家族再确认 (换角度, 别复读 r10/r11 判读)**: r11 已确认新增 canonical generic_input 终品时 loader fail-closed 属 owner-gate 设计、正槽口径一致 (`int(required) > 0` vs 完备性 `>0` 同口径)。本轮换角度: ① `routing_free_sink_commodities` 的 `int(required) > 0` (`binding_subproblem.py:409`) —— 这个 `int(required)` 的 `required` 上游是 `load_generic_io_requirements` 装载的槽数, 它经过 strict_json 吗? 若 R11-01 入口缝在, 一个写成 `1.0000000001` 的 required 值会被 `int()` 截断成 1 还是被 `_strict_nonnegative_int` 拒? (期望拒, 但请核这条链是否**也**该挂在 exact-decimal loader 上, 还是它本来就只收 int 字面量。) ② 完备性校验取的 canonical generic_input set 与 `extract_port_specs` 排除用的 set 是否同源 (`commodity_metadata[*].sink_kind==generic_input`), 有无两处独立读取可能漂移?
- (c) **全面重审新角度 (任选高价值方向, 别复读上轮 Q 判读)**: 例如 —— ① exact-one 约束在 generic 槽与 fixed binding **混合**实例上有无 double-binding 漏洞 (一个商品被 fixed 口和 generic 口同时计数满足 demand, 实际物理吞吐不够)? ② `extract_port_specs` (`binding_subproblem.py:1044`) 在 `R<S` (某槽落 `__unused__`) 时是否正确**不导出** `__unused__` 同时**导出**所有真实绑定 (不漏不重), 且导出的 port_spec 槽数与 binding 模型选中的物理槽数一致 (没有把 `_rate_to_slots` 算出的"需求槽数"与"实际枚举出的物理槽数"混淆)? ③ `_enumerate_side_binding_patterns()` 的 `total_slots > ordered_cell_count` raise (`port_binding.py:149-152`) 是否在**所有** profile 上先于 binding CP-SAT 求解 (build-time raise 而非 solver-time 伪 INFEASIBLE)? raise 被谁 catch? catch 后是否被误读成 binding INFEASIBLE 铸 nogood (与 lock:134/136 status contract 的交互)? 请挑你独立判断最可能藏 soundness 缺陷的方向深挖, 给可复现 probe 或 file:line 论证。

## 明确不要报的

- **F-BIND-R11-02 (ceil_machine_count, 已落地) / R10-01 / R9-01 / R8-01 / R8-02 本身, 重复报不算** (lock 已追加条款); 只报: 修复**不完备**、**有同型残留**、或**引入新缺陷 (反向 false-FEASIBLE/INFEASIBLE / 下游类型契约破坏 proof 路径)**。
- **F-BIND-R11-01 例外**: 它是本轮**点名要你坐实**的对象 —— 若你独立确认它**仍存在** (HEAD `7fec29a` 上 JSON float token 仍能绕过 exact ceiling), **请正式报告并给干净树补丁**, 这正是本轮高价值产出; 若你独立确认它**已落地/不再可达**, 明确写出推翻依据。**不要因为 lock:154 散文说"已落地"就跳过它** —— 散文与代码可能不一致, 以源码实证为准。
- 已修 lock 条款: F-BIND-R1-01/R1-02 (lock:98/99)、R2-01/R2-02 (lock:100/101)、R3-01..05/R4-01 (lock:102)、R5-01 (lock:103)、R8-01 (lock:134)、R8-02/R9-01 (lock:135)、R10-01 (lock:147); 关联 F-PRE 系列 (lock:104-110/154) 属 preprocess 面 (其中 R18-02 ceil = 本面 R11-02, 已落地); F-BL/F-CUT/F-GM 系列 (lock:136-138/148-153) 属 benders/cuts/master 面。**r6/r7/r8/r9/r10/r11 已审结论不必重证** (除非新角度发现旧判读有漏洞 —— 那是高价值 finding)。
- **跨面边界 (明确列入"不审")**: ① 上游 master/preprocess 保证 pose 端口坐标几何正确 + canonical rate/amount **数值真源** (geometry-master / preprocess 面; 本面只验 rate→slot 取整忠实 + 源 token 到 Fraction 全程不丢精度); ② 下游 routing 内部对偶 (deletion-core/lazy-demand/separator/PCR-CUT) 属 cuts/routing 面, 本面只验 binding 侧 `extract_port_specs` + RAB `_filter_pose_binding_domain` 排除是否对 routing-free 终品成立; ③ 需求工件单快照封印的 outer/worker 部分属 campaign/scheduler 面; ④ RAB-SEP / PCR-CUT / pose-bool master 均 env-gated 默认关, certified 主链 `routing_context=None` 不经 RAB filter — env-on 行为属 cuts 面; ⑤ master 侧 generic I/O 入口委托同一 loader (r10 已确认无 fork, 不必重证, 除非新角度发现裂缝)。怀疑跨面时**交叉引述 PROJECT_LOCK 契约** (如 lock:96/97/100/104/128/154) 而非重证。
- **env-gated / 默认关 行为不属 P1.2 certified soundness**: `EXACT_USE_POSE_BOOL_MASTER` (被 `pose_bool_master_not_certified` 挡) / `EXACT_POWER_PLACEMENT_SUBPROBLEM` (deny-unknown) / `EXACT_B1_BYPASS_*` / `EXACT_B1_PATCH_ROUTING_CORE` / `EXACT_BINDING_USE_OVERLOAD_SEPARATION` / RAB-SEP 均 env-gated, 它们的缺陷最多是 hardening/availability, 明确标; 只有在 canonical + 默认 env 下能铸 false-CERTIFIED 才是 soundness reset。
- 设计决策 (canonical / 266 口径 / omni_wireless 虚拟槽 / 52-Port 满额不变量 / `min_side>=6` admissibility, owner 已定)。
- master / routing / cuts / preprocess / benders / campaign / scheduler 各面 (各自有线)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3092, HEAD `7fec29a`; 数目以实跑为准, **硬不变量 = 0 failed**; 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。跑不完就跑 binding+容量+源装载专项 (`test_operation_profiles` / `test_binding*` / `test_port_binding*` / `test_wireless_sink_binding_semantics` / `test_preprocess_context` / `test_demand` / `test_strict_json` 若存在) + `test_exact_contract` + `cuts/test_family_port_exposure` + 如实声明哪些跑了哪些没跑完。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带**可复现 probe 或严谨 file:line 论证**; **实证推翻你的怀疑就不要报**。
- 规则文本: `specs/05_facility_instance_definition.md` §5.4.3 (协议箱无线消费 + 生产端对偶排除, 行约 101-109); 商品角色真源 `rules/canonical_rules.json` `commodity_metadata` (source_kind/sink_kind, `qiaoyu_capsule`/`valley_battery`); rate/容量/amount 真源 `rules/canonical_rules.json` + `rules/preprocess_plan.json` (`belt_capacity_per_tick`, recipe rate/amount), 经 `src/io/strict_json.py` → `src/interchange/preprocess_context.py` 装载为 `Fraction` (本轮焦点 = 这条装载链的入口精度)。
- 契约: `PROJECT_LOCK.md:96/97` (无线终品 routing-free 对偶排除)、`:98/99` (哨兵 + loader fail-closed)、`:100/101` (proof-surface-wide 单 loader + 严格 JSON 解析)、`:102/103` (单解析单快照)、`:104` (strict 解析延伸到 preprocess 再生链 + 数值溢出)、`:134` (safe-reject + R8-01 overload fallback)、`:135` (R8-02/R9-01 loader 完备性)、`:136` (budget-exhaustion / status contract)、`:147` (R10-01 有理数 ceiling)、`:154` (F-PRE-R18 + 散文里提到的 R11-01/R11-02 —— ⚠️ 散文声称 R11-01 已落地, 请以源码实证为准, 这正是本轮要坐实的点)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾, `patch -p1 --dry-run` 可过)。
- **若 R11-01 仍存在 (最可能的本轮主产出)**: 正式报 F-BIND-R11-01 (或沿用此编号注明"r11 未落地, r12 重新坐实并提供干净树补丁"), 给 probe (源 JSON 边界值 → 槽数 1 vs 2) + 仅改 strict_json + preprocess-context 消费点的 unified diff + 最小回归锚 (源十进制不降精度 + 默认模式不变)。
- **若确认 sound (R11-01 已落地 + 无新残留), 明确写「本轮零 soundness finding」** + 附分段判读: ① R11-01 JSON-float 入口缝坐实结论 (仍在 / 已修, 给实证) (Q1) / ② binding 容量/需求精度链 float/epsilon/取整 家族残留再枚举结论 (Q2) / ③ R11-02 (已落地) 无回归 + generic I/O 家族再确认 + 全面重审新角度结论 (Q3), 每条带规则依据。
- 真 Pro 确认轮; 前轮修复点 (含**未落地**的 R11-01) 是攻击面起点, 按你**自己的独立判断 + 源码实证**下结论。

## 严重度纪律

- **false-CERTIFIED on canonical + 默认 env = soundness reset** (P1.2 闭环只认这个); env-gated / conditional / 把合法解误删成 INFEASIBLE 但**对外保守失败** (false-INFEASIBLE / 保守 UNKNOWN) = availability/hardening, 明确标 **LOW/conditional**。
- R11-01 的缺陷方向是 false-FEASIBLE/false-CERTIFIED, 但 canonical 数据不触发该高精度十进制边界带, 所以是 **conditional HIGH, latent-on-canonical** (与 R10-01 同档)。同族残留按此标尺定档 —— 能在 canonical + 默认 env 下直接铸 false-CERTIFIED 才升真 HIGH soundness reset, 仅 latent / 仅诊断路径 / 仅 future-rate/future-source 触发的标 conditional / LOW。

## 范围边界

重点 = 重新坐实 R11-01 JSON-float 入口缝是否仍存在 + (若仍在) 给 HEAD `7fec29a` 干净树的独立补丁 (只改 strict_json + preprocess-context 消费点, 不碰已落地的 demand_solver/ceil) + binding 容量/需求精度链同族残留再猎取 + R11-02 已落地修复无回归 + 又一次独立全面 soundness 重审; 其余面不审。
