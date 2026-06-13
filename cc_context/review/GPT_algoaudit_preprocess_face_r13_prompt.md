# 终末地 IndustrialPlanner 精确求解器 — preprocess 面 round 13 (确认轮·F-PRE-R12-01 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_095a0b6d.zip`, sha256 `095a0b6d5f7d4496f3ef99fb71f2c6873555b10324c045b5b78ef91cc85f5eda`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **preprocess 链** (canonical rules → preprocess context → 实例展开 → candidate placement 生成 → 冻结工件)。

## 本面定义与历史: preprocess, 收敛轨迹 3 HIGH (r11) → 1 HIGH (r12), 本轮目标干净轮重启

本面近 2 轮 (报告在包内 `cc_context/review/archive/`): r11 = F-PRE-R11-01 (第三 canonical 入口 `load_templates()` 不校验 schema) + R11-02 (几何契约缺 rotatable/is_solid_z 钉死) + R11-03 (cycle-group 解非负性未证明), 三修复都在包内; **r12 = F-PRE-R12-01 (HIGH, cycle RHS 成员闭包 fail-open: RHS 按 `internal_commodities` 迭代组装 → 列表外 key 的正需求被静默丢弃, `cycle_internal` 只查 group 存在不查反向成员 → canonical 漏列时正流量配零台机器进冻结工件; probe ghost_spore: flow 3/5 机器 0)**。r12 修复**也在本包内** (HEAD 3b08bb3): ① context 校验加反向索引检查 (每个 `cycle_internal` commodity 必须出现在其声明 group 的 `internal_commodities` 列表里, 不只查 group 存在); ② `_solve_cycle_group_exact()` 入口 RHS 规范化 (正需求 key 必须同时 ∈ internal_commodities 且 ∈ net-export 集, 否则拒绝; 负需求一律拒绝; 显式零保留) — 保住 R11-03 非负证明前提 (RHS 落在已证非负的 net-export 单位方向的非负张成内)。lock 有 F-PRE-R12-01 条款, specs/18 有 R12 段。**本轮 r13 = R12-01 修复确认 + 自由攻击角**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-RT / F-CUT / F-GM 系列含 F-GM-R8-SYM-01), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-PRE-R12-01 修复确认 (攻击面, 本轮主体)

① **反向索引校验的覆盖完备性**: 校验装在哪一层 — context 构建期还是 solver 入口, 还是两端都有? 有没有绕过路径 (其它调用点直接拿 cycle group 解题而不经过校验)? `cycle_internal` 的**消费点**全仓穷举 — 每个把 commodity 判为 cycle-internal 的读处, 其成员前提是否都被该校验覆盖 (数据流入口唯一 ≠ 语义消费点唯一, 按语义穷举)。
② **RHS 规范化三分支的边界**: 正需求 ∈ internal ∩ net-export 才放行 — 这两个集合的取值与 R11-03 非负证明用的集合**同一**吗 (同源同快照, 还是各自重算可能漂)? 负需求拒绝的 fail-closed 方向; 显式零保留会不会成为旁路 (zero 进 RHS 后有没有任何下游把它当自由变量松弛)。
③ **修复实现正确性**: 成员判定用的集合与 RHS 组装迭代的集合同源吗; 空 internal_commodities / 单 commodity group / 多 group 共享 commodity 等边界; 拒绝路径是 raise/fail-closed 还是静默跳过 (静默跳过 = 残留 fail-open)。
④ **冻结工件侧**: 修复后再生的 `generic_io_requirements.json` / 实例工件与 RHS 闭包的一致性 — 有没有"工件已冻结但校验只管再生路径"的缝。

### Q2 R11 三修复维持轻确认

r12 补丁动过 cycle 求解入口附近 — R11-03 的非负证明 (net_export ∈ internal + 单位方向基 + per-solve 负值检查) 在 r12 改动后是否完好; `load_templates()` schema 校验与几何契约 (rotatable/is_solid_z 钉死) 未被同期改动破坏 (轻扫, 不深挖)。

### Q3 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面最薄弱的点深挖。r12 补丁本身是新代码 (反向索引校验 + RHS 规范化), 它有没有引入新缝是天然候选; preprocess 链上 r2-r12 还没人审过的角落也行。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r12 已修 finding 与已审结论 (重复报不算)。
- master/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- 部分再生撕裂由 golden tests 抓 (r12 已审结论 = 设计边界); machine_counts/port_budget/commodity_demands 在 hash 闭包外但 certified runtime 不消费 (r12 已审)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3004 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 各点逐项判读 (校验覆盖/三分支边界/集合同源性/工件侧)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R12-01 修复确认 + 自由攻击角; 其余面不审。
