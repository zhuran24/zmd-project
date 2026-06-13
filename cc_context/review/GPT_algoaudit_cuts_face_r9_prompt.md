# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 9 (确认轮·CUT-R8-H1 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_13fbe643.zip`, sha256 `13fbe6432947212e62304ddd2c7f199b7e4c3b0bb81e01ed3f9ff6ffe20e7430`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制** (front_blocked ladder 各 cut 通道 + BendersCut 本体)。

## 本面定义与历史: cuts, 收敛轨迹 …→0 (r7 零)→1 (r8 HIGH), 本轮目标干净轮重启

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r6 = PCR-CUT-R6-H1 (patch 端口成员判据); r7 = 零 (本面首个干净轮); **r8 = CUT-R8-H1 (HIGH, over-cut: env-gated `EXACT_B1_D2_COMMODITY_FLOW` rung 的 master cut 只用 raw terminal assumption core, 但 D2 模型把当前全 layout footprint 编译成常量 occupied grid — CP-SAT core 只覆盖 assumption literals, 常量 context 不受保护 → "当前障碍下不可行"被升级为"任意 layout 不可行"; toy 反例 = 单行走廊+墙挡中点, core 只含 src, 移墙后同 poses FEASIBLE)**。修复**在本包内** (`src/search/d2_separator.py`): cut 从 raw core 扩成 **support-augmented conflict set** — `_build_d2_supported_conflict_set()` 把全部当前 port owners (assumptions 全集) + 全部 occupancy contributors (`_build_occupancy_support_pose_terms()`, 跳过 `ghost_pick`) + raw core 合并进 master nogood; 并入只弱化, 被禁集合回落到 D2 实际证明范围内。lock 有 CUT-R8-H1 条款 (separator cut 不得窄于其模型编译进的 layout context, 泛化全通道), specs/10 有 §10.9。回归 `src/tests/test_d2_separator_support_context.py` (走廊 toy: cut 含 src/sink/wall 三 support + raw core alone 不 sound 的双向证明)。**本轮 r9 = CUT-R8-H1 修复确认 + 自由攻击角**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-RT / F-GM / F-PRE 系列含 F-PRE-R13-01), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R8-H1 修复确认 (攻击面, 本轮主体)

① **support 集合的完备性**: `_build_occupancy_support_pose_terms()` 收集的集合与 D2 模型实际编译的常量贡献者**同口径**吗 — 对照 `_placement_to_occupied()` 逐条件比对 (pool 取法 / pose_idx 边界 / occupied_cells 空与非空 / facility_type 缺失), 有没有"贡献了 occupied cells 但被 support 漏掉"的缝 (漏 = 残留 CUT-R8-H1) vs "没贡献却被并入" (= 只弱化, 安全)? `ghost_pick` 排除的正当性 (ghost 在 master 是什么变量, 它的 footprint 进 D2 occupied 吗 — 若进了却不在 conflict, 是缝吗)?
② **非 core terminal owners 并入的必要性与充分性**: assumptions 全集并入 — D2 模型里非 core terminals 以什么形式参与 (`d2_commodity_flow_core.py` 的 forced/blocked port 预处理、terminal obligations 的 assumption guard 范围)? 有没有 terminal 语义以**非 assumption、非 occupancy** 的第三种形式进入模型常量而两个 support 来源都覆盖不到?
③ **cut 形态对接**: `conflict_set` dict 合并三来源时同 instance 同 pose 无损吗 (raw_core 的 pose_idx 与 placement_solution 的 pose_idx 恒一致? 不一致时 dict 后写覆盖先写 — 哪边赢, 赢错了是什么方向)? `master_delegate.add_benders_cut(conflict_set)` 的 presence-nogood 语义与"禁止该 support tuple 共现"一致吗?
④ **fail-closed 行为维持**: 修复没动 D2 的 FEASIBLE/UNKNOWN/ERROR/empty-core 不写 cut 路径吗; metadata `support_conflict_size`/`support_owners` 真实性。

### Q2 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面最薄弱的点深挖。天然候选: r8 补丁本身的新代码; `D2CommodityFlowCore` 模型本体的 relaxation 方向 (cell capacity / flow conservation 是 production routing 的必要条件这个前提本身 — 有没有 D2 比 production **更松**之外还存在**更严**的编码点, 更严点若存在会让 INFEASIBLE 不再蕴含 production INFEASIBLE); `benders_loop.py` D2 rung 的 wiring (成功后 skip 其余通道的状态机)。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r8 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/master-geometry 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- D2 cut 修复后变弱导致的剪枝效率下降 (修复的预期代价, 非 finding); cell-pattern duplicate-literal 防尘罩建议 (r8 已记录为未来加固, 当前工件实证无缝)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3008 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 四点逐项判读 (support 同口径比对 / 第三形式排查 / dict 合并方向 / fail-closed 维持)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = CUT-R8-H1 修复确认 + 自由攻击角; 其余面不审。
