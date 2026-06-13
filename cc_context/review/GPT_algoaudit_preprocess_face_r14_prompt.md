# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 14 (确认轮·F-PRE-R13-01 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_2cd169b4.zip`, sha256 `2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **preprocess 链** (canonical rules → preprocess context → 实例展开 → candidate placement 生成 → 冻结工件)。

## 本面定义与历史: preprocess, 收敛轨迹 3 HIGH (r11) → 1 HIGH (r12) → 1 HIGH (r13), 本轮目标干净轮重启

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r11 = F-PRE-R11-01/02/03 (schema 入口 / 几何契约 / 非负证明); r12 = F-PRE-R12-01 (cycle RHS 成员闭包 fail-open, demand keys 侧); **r13 = F-PRE-R13-01 (HIGH, cycle group recipe I/O 闭包未校验: cycle 矩阵与解后 machine-run 聚合只看 `internal_commodities`, cycle recipe 的 inputs/outputs 引用列表外 commodity [canonical drift 场景] 时该外部消耗/产出静默漏出 `commodity_demands`/`port_budget`/`generic_io_requirements` — 冻结工件少算外部供料却仍报 52-port budget 可行; probe: planter_buckwheat 突变加 source_ore 输入 → context 照常接受, 漏 11/tick, port total 仍 52; R12-01 成员闭包类从 demand keys 延伸到 recipe I/O 的同族缝)**。r13 修复**在本包内** (`src/interchange/preprocess_context.py`): 双端 I/O 闭包校验 — `_cycle_group_recipe_io_outside_internal()` (group recipes 的 `inputs ∪ outputs ⊆ internal_commodities` 否则 ValueError 列明 recipe:commodities), 装在 context validation **和** `_solve_cycle_group_exact()` 入口 (覆盖未验证 context 直调)。lock 有 F-PRE-R13-01 条款, specs/18 有 Round 13 段。回归 = context builder 突变拒绝 + solver 直调拒绝两个。**本轮 r14 = R13-01 修复确认 + 自由攻击角**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-CUT 系列含 CUT-R9-H1、F-GM 系列含 hint parser 共享化), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-PRE-R13-01 修复确认 (攻击面, 本轮主体)

① **闭包检查的完备性**: `_cycle_group_recipe_io_outside_internal()` 对 recipe 引用的判定 — `set(recipe.inputs) | set(recipe.outputs)` 是 recipe 对外部世界的**全部**接口吗? Recipe 数据结构有没有第三种 commodity 引用形态 (副产物/催化剂/ticks 相关字段/utility 关联) 被漏掉? `recipe is None: continue` 分支安全吗 (unknown recipe 在 validation 循环前面已 raise, solver 直调路径上 unknown recipe 后续矩阵构建会 KeyError fail-closed — 请独立确认这条兜底真实存在)?
② **双端覆盖**: validation 端与 solver 入口端用的是**同一个** helper 吗 (同源无第二套实现)? 还有没有第三条路径绕过两端拿 cycle group 解题 (全仓搜 `_solve_square_linear_system` / 矩阵构造的调用者)?
③ **修复与 R12-01/R11-03 的相容性**: I/O 闭包通过后, R12 的 RHS membership 检查和 R11 的非负证明前提是否仍然完整 (修复有没有改动它们的代码路径)?
④ **漏出面的另一半**: r13 修的是"cycle recipe 引用外部 commodity"; 反方向 — **非 cycle recipe 引用 cycle internal commodity** 时, demand 传播会把需求转给 cycle group (`role.cycle_group is not None` 分支)吗? 这条流向的正确性 r12 验过 demand keys 侧, 但请确认非 cycle recipe 产出/消耗 cycle-internal 商品的流量在 machine_runs/外部需求里没有第二种静默漏算。

### Q2 R11/R12 维持轻确认

r13 补丁动了 validation 循环与 solver 入口 — R12 反向索引检查与 RHS 三分支、R11-03 非负证明 (零 RHS + 单位方向 solve) 在改动后仍完好; `load_templates()` schema 校验与几何契约未被同期改动破坏 (轻扫)。

### Q3 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面最薄弱的点深挖。r13 补丁本身是新代码; preprocess 链上 r2-r13 未审过的角落也行 (例: targets/demand 入口语义、utility operations 链、实例 id 稳定性的边界)。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r13 已修 finding 与已审结论 (重复报不算)。
- master/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。
- 部分再生撕裂由 golden tests 抓 (r12 已审 = 设计边界); machine_counts/port_budget/commodity_demands 在 hash 闭包外但 certified runtime 不消费 (r12 已审)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3020 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 四点逐项判读 (接口完备/双端同源/相容性/反向流向)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R13-01 修复确认 + 自由攻击角; 其余面不审。
