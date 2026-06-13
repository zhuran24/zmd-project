# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 15 (确认轮·F-PRE-R14-01/02 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_eca69648.zip`, sha256 `eca696483abee31138cdbdcc3cf67a8912f5e13f3b5291821cab67fffbae1302`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **preprocess 链** (canonical rules → preprocess context → 实例展开 → candidate placement 生成 → 冻结工件)。

## 本面定义与历史: preprocess, 收敛轨迹 r12 HIGH → r13 HIGH → r14 2 HIGH, 本轮目标干净轮重启

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r12 = F-PRE-R12-01 (cycle RHS 成员闭包 fail-open, demand keys 侧); r13 = F-PRE-R13-01 (cycle group recipe I/O 闭包未校验, recipe inputs/outputs 引用 internal 列表外 commodity 时静默漏算); **r14 = 自由攻击角抓 2 HIGH (均 fail-open → false 方向, 已修, 修复在本包内):**

- **F-PRE-R14-01 (多输出 recipe co-product 重复计数)**: demand backprop 按输出逐项 charge machine-run, schema-valid 的双输出 recipe 会对同一 operation 重复 charge → mandatory 机器数虚增 (probe: packaging_battery 3→4) → 潜在 false-INFEASIBLE 方向。修 = 三处 fail-closed 锁单输出: `rules/canonical_rules.schema.json` 的 `outputs` 加 `maxProperties:1` + `src/rules/semantic_validator.py` `validate_canonical_document` 加多输出拒绝分支 + `src/interchange/preprocess_context.py` `validate_preprocess_context` 加 `len(recipe.outputs)!=1` raise。
- **F-PRE-R14-02 (cycle-internal commodity 被组外 recipe 产出, fail-open)**: `role.cycle_group` 非空的商品的正需求被直接转给 cycle solver, 这步发生在「非 cycle producer 反向索引查询」之前 → 若某 cycle-internal 商品同时被一个**组外** recipe 产出, 那台 outsider 机器及其输入被静默漏算 (probe: synthetic_orb 机器缺失 + source_ore 输入不计)。修 = context validation 拒绝任何**非组内** recipe 输出 cycle-internal commodity (非 cycle recipe 消费 cycle-internal 仍是合法外部需求边, 不拒)。

两修均 fail-closed, 不改动冻结 canonical 产物 (`data/` 工件零漂移)。lock 已有 F-PRE-R14-01/02 双条款, specs/18 有 R14 两段。回归 4 个 (多输出 context 拒 + 多输出 schema 拒 + 多输出 semantic 拒 + 组外 producer 拒)。**本轮 r15 = R14-01/02 修复确认 + 自由攻击角**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-CUT 系列含 CUT-R10-L1、F-GM 系列含 persisted-hint 入口加固), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-PRE-R14-01 修复确认 (多输出 co-product, 攻击面)

① **三处 fail-closed 的覆盖完备性**: schema `maxProperties:1` + semantic validator + context validation 三道是否真封死所有「多输出 recipe 进入 demand backprop」的入口? 有没有第四条路径 (直构 `PreprocessContext` / 绕过 `load_templates` 的 recipe 注入 / solver 直调) 拿到多输出 recipe 而不过这三道?
② **单输出语义本身是否 sound**: 锁死「每 recipe 恰一输出」是否与项目 canonical 数据 + 上游 vendored recipes 一致 (会不会有合法的多输出配方被误杀)? co-product 在终末地实际游戏机制里存在吗 — 若存在, 单输出锁是正确的「不支持声明」还是漏建模? 从 `third_party_snapshots` 上游数据独立判断。
③ **demand backprop 的计数口径**: 修复后单输出 recipe 的 run 计数 (`ceil(demand/output_qty)`) 在多消费者/链式需求下仍精确无重复/无遗漏吗?

### Q2 F-PRE-R14-02 修复确认 (cycle-internal 组外 producer, 攻击面)

① **校验的方向完整性**: context validation 拒「非组内 recipe 输出 cycle-internal commodity」—— 判定用的成员集 (组内 recipe 集 vs cycle-internal commodity 集) 是否与 demand 传播实际查询的集合同源? 反方向 (组内 recipe 输出**非** cycle-internal commodity) 是 r13 管的, 本轮确认两者无重叠盲区。
② **双端覆盖**: 该校验装在 context validation, solver 直调入口 (`_solve_cycle_group_exact` 或矩阵构造) 有没有兜底? 绕过 validation 直接解 cycle group 时这条漏算还会复现吗?
③ **fail-open → fail-closed 的彻底性**: 「正需求直转 cycle solver 发生在 producer 反向索引查询前」这个时序缺陷, 修复是真的在时序上前移了校验, 还是只补了个旁路检查 (原时序缝是否还在别的调用路径上)?

### Q3 R12/R13/R11 维持轻确认

r14 补丁动了 validation 与 demand backprop 路径 — R13 的 recipe I/O 闭包校验、R12 的 RHS membership 反向索引、R11 的非负证明前提在改动后仍完好 (轻扫, 确认没被同期改动破坏)。

### Q4 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面最薄弱的点深挖。本面已审 r1-r14, 覆盖 schema 入口/strict JSON/几何契约/cycle 闭包/实例展开/工件交叉一致性/demand 数学。残留薄弱候选 (非限定): targets/demand 入口语义的其它 fail-open、utility operations 链、**多输出锁之后 recipe 数据结构是否还有第三种 commodity 引用形态** (副产物字段/催化剂/utility 关联) 影响 demand 计数、实例 id 稳定性边界。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r14 已修 finding 与已审结论 (重复报不算)。
- master/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。
- 部分再生撕裂由 golden tests 抓 (设计边界); machine_counts/port_budget/commodity_demands 在 hash 闭包外但 certified runtime 不消费 (r7/r12 已审)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3033 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1/Q2 各点逐项判读 (多输出三道封口完备 + 单输出语义正当性 / 组外 producer 校验同源 + 双端 + 时序彻底)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R14-01/02 修复确认 + 自由攻击角; 其余面不审。
