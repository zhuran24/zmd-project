# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 11 (终饱和轮·CUT-R10-L1 修复确认 + 全通道自由攻击)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_eca69648.zip`, sha256 `eca696483abee31138cdbdcc3cf67a8912f5e13f3b5291821cab67fffbae1302`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制** (master 收紧用的全部 cut 通道: binding nogood / master placement nogood / deletion-core / lazy-demand / cell-pattern / lazy connectivity / D2 commodity-flow separator / PCR-CUT patch separator / whole-layout / power-conditioned)。

## 本面定义与历史: cuts, 收敛轨迹 r7 零 → r8 HIGH → r9 HIGH → r10 零, 本轮 = 终饱和轮 (冲第二个连零达饱和下沿)

本面已审 10 轮 (报告全在包内 `cc_context/review/archive/`)。近况: r7 = 零 (PCR QuickXplain/replay 本体首审干净); r8 = CUT-R8-H1 (D2 separator cut 只用 raw terminal core, 丢失编译进模型的 layout-constant context = over-cut, PCR-R5-H3 constant-support 义务在 D2 通道复发; 修 = support-augmented conflict set); r9 = CUT-R9-H1 (D2 模型不是 production routing 的 relaxation — per-cell `AddAtMostOne` 表达不了跨层 bridge crossing, 单位流守恒表达不了 splitter/merger; 修 = D2 INFEASIBLE 不再独立作 proof source, separator 入口重跑 production precheck, 仅 `front_blocked`/`relaxed_disconnected` 放行, 其余 deny-unknown 返 MODEL_INVALID 不建模不写 cut); **r10 = CUT-R9-H1 修复确认四点全过 + 零 soundness finding (连零 1) + 1 LOW 已修 — CUT-R10-L1**: 原 D2 port owner 校验 `str(None)→"None"` 当作有主端口 + 不校验 owner∈placement → synthetic owner `{"None": -1}` 可进 conflict (production 不可达但违 r9 宣称的 fail-closed 边界); 修在本包内 (`src/search/d2_separator.py` `_d2_port_owner_validation_error()` 前置拒 None/空白/ghost/不在 placement + 2 回归)。

**本轮 r11 = 终饱和轮**: r10 已零 soundness (CUT-R9-H1 四点确认干净), 本轮不为某个待确认 finding 而来, 而是 cuts 面冲饱和下沿 (连零 2) 的终审 —— 请用你最独立的判断, 把整个 cut 机制再扫一遍, 找任何残留 soundness 问题 (over-cut = false-INFEASIBLE 方向为主, under-cut/漏 nogood 致不收敛为辅); 挖不出就明确宣告本面饱和。**前 10 轮 clean/已修绝不代表本轮默认干净** —— 本面历史上多次出现「确认轮自身从新角度抓出 HIGH」(r8/r9 即在 r7 干净后接连爆 HIGH), 终饱和轮的价值正是再确认一次。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-GM 系列含 hint parser 共享化/persisted-hint 入口加固、F-PRE 系列含 R14 多输出+cycle-internal 修复), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R10-L1 修复确认 + r9/r10 D2 通道叠加链 (轻确认)

① `_d2_port_owner_validation_error()` 的前置校验是否覆盖所有非法 owner 形态 (None / 空白 / `ghost_pick` / 不在 placement 的 instance_id)? 有没有第二条构造 D2 conflict 的路径绕过它?
② r9 的 precheck gate (重跑 production precheck, deny-unknown 返 MODEL_INVALID) + r10 的 owner 校验叠加后, D2 通道完整链路 (precheck 放行 → 建 D2 模型 → support-augmented cut → master apply) 再走一遍有没有新缝。

### Q2 全通道终审 (本轮主体, 自由选点深挖)

r2-r10 已覆盖: D2 separator (r8/r9/r10), PCR-CUT (r5/r6/r7), deletion-core oracle 弱于 precheck (r5), cell-pattern generic 容量 (r2/r3/r4), lazy-demand count cut (r4), binding/whole-layout/power-conditioned condition_lits (r8), F1-F9 框架 stub 边界 (r2)。**请你独立判断哪些通道审得最浅、最可能藏残留 soundness 缝**, 选 1-2 个深挖。天然候选 (非限定):
- **lazy connectivity cut**: 多轮提及但从未作为主角深审 — 它的 cut 形式、作用域、exactness 定理 (禁的集合 ≤ 它能证明的)、fail-closed 行为。
- **deletion-core 算法本体**: r5 判 oracle 弱于真 precheck (核偏大方向安全) + deletion-minimal 非 minimum; 本轮可再挖量化范围 (`pose_idx_by_id` 来源是否等于支撑集) / 调用方是否消费 minimum 语义 / binding alternatives 穷尽前提在每个调用点都成立吗。
- **cell-pattern cut 剩余角**: r8 提到 self-front/duplicate-literal guard 当前工件无缝但留作防尘; 本轮可深挖 duplicate guard 缺失在何种 canonical 漂移下变成真缝。
- **跨通道 ladder 弱序**: r6/r8 给过 ladder 交互表; 本轮独立重验「任一 rung 失败必 fail-closed 或落更弱通道, 永不向更强 cut 升级」, 以及各 rung 之间无状态泄漏。

### Q3 自由攻击角

以上之外, 用你自己的独立判断选你认为本面最薄弱的点深挖。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r10 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/master-geometry 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- D2/PCR 剪枝变弱/重跑 precheck 的性能开销 (预期代价, 非 finding); readiness gate 的 `EXACT_B1_D2_COMMODITY_FLOW` blocker 待办 (C-4, 已挂账); F1-F9 `step_2`/`step_8` NotImplementedError (P1.3B 边界, 非缝)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3033 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 两点判读 + Q2 你选的通道深挖结论 + 一句你对「cuts 面是否已达饱和」的独立判断。
- 前 10 轮 clean/已修不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 终饱和轮全通道自由攻击 (CUT-R10-L1 轻确认 + 你选的薄弱通道深挖); 其余面不审。
