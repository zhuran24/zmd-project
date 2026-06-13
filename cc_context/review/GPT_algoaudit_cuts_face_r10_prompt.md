# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 10 (确认轮·CUT-R9-H1 修复确认 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_2cd169b4.zip`, sha256 `2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制**。

## 本面定义与历史: cuts, 收敛轨迹 r7 零 → r8 HIGH → r9 HIGH, 本轮目标干净轮重启

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r7 = 零; r8 = CUT-R8-H1 (D2 raw-core cut 丢 occupancy proof context, 修 = support-augmented conflict set); **r9 = CUT-R9-H1 (HIGH: D2 模型不是 production routing 的 relaxation — per-cell `AddAtMostOne` 是 2D 表达不了跨层 bridge crossing, 单位流守恒表达不了 splitter/merger 一源多汇 → production 可行 layout 被 D2 判 INFEASIBLE, support 全并入也救不了; 双 probe 反例 [crossing/splitter] 都钉成回归)**。r9 修复**在本包内** (`src/search/d2_separator.py`): D2 INFEASIBLE 不再独立作 master-cut proof source — separator 入口对同一 occupied+port_specs **重跑 production routing precheck** (`_d2_precheck_status_for_cut_context`), 仅 `front_blocked`/`relaxed_disconnected` 放行, 其余一切状态 deny-unknown 返 `MODEL_INVALID` (不建 D2 模型不写 cut); 配套 `_placement_to_occupied` 显式跳过 `ghost_pick` (separator occupied ≤ production 口径) + 无主 port spec fail-closed + metadata 记 `routing_precheck_status`/`routing_precheck_domain_stats`。lock 有 CUT-R9-H1 条款, specs/10 有 §10.10。**本轮 r10 = CUT-R9-H1 修复确认 + 自由攻击角**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-GM 系列含 r9 的 hint parser 共享化、F-PRE-R13-01 等), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R9-H1 修复确认 (攻击面, 本轮主体)

① **precheck gate 的语义对齐**: separator 内重跑的 `run_exact_routing_precheck(RoutingGrid(occupied, port_specs))` 与 production caller (benders_loop 的精确调用形态, 可能带 `occupied_owner_by_cell`/`placement_core` 优化参数) 是同一判定函数的同一语义吗? 精简调用形态会不会产出与 production 形态**不同的 status** — 若会, 各 status 错位组合下哪些方向安全 (separator 判 blocked 而 production 判 feasible = 还 unsound 吗? 注意 gate 的 proof 主张是"production precheck 证明同一上下文不可行")? 逐状态枚举 `run_exact_routing_precheck` 的全部可能返回值, 确认 deny-unknown 集合无遗漏。
② **口径单调性独立复核**: 修复的安全论证 = separator occupied (skip ghost) ⊆ production occupied, 且 blocked/disconnected 判定沿障碍单调 — 请独立验证: (a) `front_blocked` 的判定本质 (port front cell 被 occupied 占) 在 separator-occupied ⊆ production-occupied 时, separator 判 blocked ⇒ production 上下文同样 blocked 吗 (blocked 的 front cell 必在两边都占)? (b) `relaxed_disconnected` 的连通性判定同向单调吗 (障碍越多越断)? (c) separator occupied 真的 ⊆ production 吗 — production routing 的 occupied_cells 构造里有没有 separator 漏掉的成分 (或反向: separator 多算的成分)?
③ **ladder 位置前提**: 修复 soundness 还依赖 caller — benders_loop 的 front_blocked master-cut ladder 只应在 `binding_selection_safe_reject=False` 或 binding alternatives 穷尽后到达 (lock 既有 binding-local 证据条款)。独立读 `benders_loop.py` 的分支结构确认这个前提, 以及 D2 cut (support tuple 全集) ⊇ fallback selected nogood tuple 的弱化方向。
④ **MODEL_INVALID 的状态机消费**: benders_loop 对 `d2_status == "MODEL_INVALID"` / `cut_added=False` 的处理 — fall through 到 PCR/deletion/lazy/cell/fallback 正常吗, 有没有路径把 MODEL_INVALID 误读成证明性结论?

### Q2 自由攻击角

以上之外, 用你自己的独立判断选 1-2 个你认为本面最薄弱的点深挖。天然候选: r9 补丁新代码 (precheck gate 实现/异常处理/unowned port 判定); r8+r9 双补丁叠加后的 D2 通道整体 (gate 放行后 support-augmented cut 的完整链路再走一遍); 或 cuts 面其它通道 r2-r9 未覆盖的角落。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r9 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/master-geometry 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- D2 修复后剪枝变弱/重跑 precheck 的性能开销 (预期代价, 非 finding); readiness gate 的 `EXACT_B1_D2_COMMODITY_FLOW` blocker 待办 (C-4, 已挂账)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3018 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 四点逐项判读 (状态集合枚举 / 单调性三问 / ladder 前提 / MODEL_INVALID 消费)。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = CUT-R9-H1 修复确认 + 自由攻击角; 其余面不审。
