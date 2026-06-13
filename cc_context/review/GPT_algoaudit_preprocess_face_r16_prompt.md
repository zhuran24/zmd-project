# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 16 (确认轮·F-PRE-R15-01 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_c9315ba2.zip`, sha256 `c9315ba216598e08ecb4103ca2563d7aabdecae11d48205803c17921fc4ead61`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **preprocess 链** (canonical rules → preprocess context → 实例展开 → candidate placement 生成 → 冻结工件)。

## 本面定义与历史: preprocess, 收敛轨迹 r13 HIGH → r14 2 HIGH → r15 1 HIGH, 本轮 = R15 修复确认轮

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r13 = F-PRE-R13-01 (cycle group recipe I/O 闭包); r14 = F-PRE-R14-01 (多输出 co-product 重复计数) + F-PRE-R14-02 (cycle-internal 组外 producer fail-open); **r15 = 抓 1 HIGH F-PRE-R15-01 (public solver 入口绕过 R14 fail-closed)**, 已修在本包内:

- **F-PRE-R15-01**: `solve_demands_exact(context=...)` (public regeneration API 入口) 直接用 caller 传入的 `PreprocessContext` 计算 target + backprop, **修复前不调用 `validate_preprocess_context()`** → caller 通过 deep-copy / 测试构造 / overlay 篡改得到未重验 context, 可绕过 R14-01 (单输出) + R14-02 (cycle-internal ownership) 的三道 fail-closed 门 (schema/semantic/context validation 原本只在文件加载链生效)。两 probe: 多输出 co-product 重复计数 (packaging_battery ceil 3→4, false-INFEASIBLE 方向) + cycle-internal 组外 producer 漏算 (false-FEASIBLE/undercount)。修在本包内: `solve_demands_exact()` 解析 context 后立即调 `validate_preprocess_context()` (`src/preprocess/demand_solver.py:106`); R14 校验抽成共享 helper `_validate_single_output_recipes()` / `_validate_cycle_internal_output_ownership()` (`src/interchange/preprocess_context.py:387-428`, 带 `recipe_ids`/`group_ids` 子集参数); raw cycle solver `_solve_cycle_group_exact()` 入口加 group-local guard (`:496-500`)。lock 有 F-PRE-R15-01 条款, specs/18 有 Round 15 段。回归 3 个 (public solver 拒 direct 多输出 context / public solver 拒 direct outsider cycle-internal producer / raw cycle solver 拒 direct outsider producer)。

**本轮 r16 = F-PRE-R15-01 修复确认 + 自由攻击角**。

注意: 本包含其它审查面同期落的修复 (cuts/master-geometry 等各面有自己的线), 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-PRE-R15-01 修复确认 (攻击面, 本轮主体)

① **入口覆盖完备性**: `solve_demands_exact()` 加的 `validate_preprocess_context()` 是否封住所有「未重验 context 进入 demand backprop」的 public 入口? `solve_demands()` 经 `solve_demands_exact()` 同步覆盖 — 还有没有**第三个** public 入口 (其它 module 直接构造 context 后调矩阵构造 / target rate / backprop 的函数, 例如 `generate_port_budget` / `generate_ceil_machine_counts` 等是否也吃 caller context 而不重验)? 全仓搜 `_backpropagate_non_cycle_demands` / `_target_rate_per_tick` / `solve_cycle_group_exact` / `generate_port_budget` 的调用者与 context 信任假设。
② **helper 抽取等价性**: R14 校验从 inline 抽成 `_validate_single_output_recipes` / `_validate_cycle_internal_output_ownership` (带子集参数) — 抽取后 `validate_preprocess_context` 全量调用的行为与抽取前**严格等价**吗 (没有因子集参数默认值 / 遍历范围变化漏掉某些 recipe)? 子集参数 (`recipe_ids` / `group_ids`) 在 raw cycle solver 的 group-local 调用下, 覆盖范围是否恰好等于该 group 应检查的集合 (不多不少)?
③ **raw cycle solver 双端对齐**: `_solve_cycle_group_exact()` 入口的 group-local guard + 既有 R13 closure 检查, 与 full `validate_preprocess_context` 的检查在该 group 上是否一致 (绕过 full validation 直调 cycle solver 时, R14-01/R14-02/R13 三类缺陷都兜住)?
④ **重验的副作用**: `solve_demands_exact` 每次调用都跑 full `validate_preprocess_context` — 对正常 (合法) context 是否纯增开销无行为变化 (不会把某些合法 context 误判 invalid)? 默认 `load_default_preprocess_context()` 路径仍正常 (回归/golden 工件一致)?

### Q2 R14/R13/R12/R11 维持轻确认

r15 补丁动了 demand_solver 入口 + preprocess_context 的 validation 结构 (抽 helper) — R14-01 (多输出锁) / R14-02 (cycle-internal ownership) / R13 (recipe I/O 闭包) / R12 (RHS membership) / R11 (非负证明) 在抽取重构后仍完好 (轻扫, 确认没被同期改动破坏)。

### Q3 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面最薄弱的点深挖。本面已审 r1-r15, 覆盖 schema 入口/strict JSON/几何契约/cycle 闭包/实例展开/工件交叉一致性/demand 数学/public 入口重验。残留薄弱候选 (非限定): demand backprop 的其它 fail-open、utility operations 链、co-product 数据结构形态、实例 id 稳定性边界、public API 其它入口的 context 信任假设。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r15 已修 finding 与已审结论 (重复报不算)。
- master/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。
- 部分再生撕裂由 golden tests 抓 (设计边界); machine_counts/port_budget/commodity_demands 在 hash 闭包外但 certified runtime 不消费 (r7/r12 已审)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3036 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 四点逐项判读 (入口完备 / helper 等价 / 双端对齐 / 重验副作用)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-PRE-R15-01 修复确认 + 自由攻击角; 其余面不审。
