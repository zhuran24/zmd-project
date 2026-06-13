# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 13 (确认轮·CUT-R12-H1 修复确认 + power 通道纵深 + 自由攻击)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_5e5e0c86.zip`, sha256 `5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制**。

## 本面定义与历史: cuts, r12 抓出 CUT-R12-H1 (power 通道), 本轮 = 修复确认轮

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r10 零 + LOW CUT-R10-L1 (D2 owner gate); r11 零 (终饱和轮); **r12 抓 1 HIGH CUT-R12-H1**, 已修在本包内:

- **CUT-R12-H1 (power-conditioned infeasible cut 丢失 unpowered fixed-occupancy support)**: `PowerPlacementSubproblem` 的固定占用集合包括**所有非 `power_pole`、非 `ghost_pick` 设施占用格** (不只 powered consumers), 所以候选 pole 过滤阶段 `if occupied & fixed: continue` 会被不需要电的设施 (真实数据: `boundary_storage_port` ×46、`protocol_core` ×1) 挡掉唯一 covering pole cell。但原 `_run_power_placement_subproblem()` 在 INFEASIBLE 时只把 `tpl in powered_templates` 的 selected poses 放入 `conflict_set` → 把"powered pose + unpowered blocker + ghost anchor 下无 pole"错误投影成"powered pose + ghost anchor 下无 pole" → unpowered blocker 移走后真实可能有 pole witness, 原 cut 仍误禁合法 layout (= CUT-R8-H1 "编译进模型的常量 support 必须进 master tuple" 义务在 power 通道复发)。**gated/exploratory**: 默认 certified 被 `EXACT_POWER_PLACEMENT_SUBPROBLEM` env guard (deny-unknown) 阻断, forensic-bypass 才暴露; 但属 HIGH。修在本包内 (`src/search/benders_loop.py:4805-4859`): `conflict_set` 改为收**所有非 pole/非 ghost 的 selected occupancy support** + entry 无法解析 `pose_idx` 时 fail-closed `ABORT`; proof_summary 记 `support_conflict_scope = all_non_pole_selected_occupancy`; `power_placement_subproblem.py` 顶部 exact-preservation 文档同步更新。lock 有 CUT-R12-H1 条款。回归 = `test_power_witness_cut_dilution.py` 4×1 probe (powered + unpowered blocker 同占唯一 pole cell, conflict_set 须含 blocker)。

**本轮 r13 = CUT-R12-H1 修复确认 + power 通道纵深 + 自由攻击角**。(注: 上一轮 r12 是本面切到真 Pro 模型后的第一轮, 一上来就抓出此前轮次漏掉的 HIGH, 故本轮**绝不能默认干净**, 请用最独立的判断。)

注意: 本包 (4d225f9) 含其它面同期修复 (preprocess F-PRE-R15-01 等), 各面有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R12-H1 修复确认 (攻击面, 本轮主体)

① **support 收集口径与子问题编译口径对齐**: 修复后 `conflict_set` 收"所有非 pole/非 ghost selected occupancy" —— 这个集合是否**恰好等于** `PowerPlacementSubproblem` 实际编译进固定障碍的设施集合 (不多不少)? 子问题 fixed occupancy 的口径 (遍历 master_solution union 非 pole/非 ghost 的 `occupied_cells`) 与 cut `conflict_set` 的口径是否同源? 有没有第三类占用 (ghost body / wireless / 其它) 在子问题算障碍但没进 conflict_set, 或反之 (进了 conflict_set 但子问题没当障碍 — 那是无害弱化还是别的)?
② **ABORT fail-closed 的彻底性**: entry 无法解析 `pose_idx` 时 ABORT —— 这条 fail-closed 是否覆盖所有非法 entry 形态? ABORT 后 caller 的处理 (不写 cut, fall through) 是否安全 (不会误把 ABORT 当证明性结论)?
③ **弱化方向确认**: 修复把更多 pose 并入 conflict_set (cut 变弱) —— 独立确认这只会**弱化** cut (禁的集合变大但仍 ⊆ proof context), 不会反向 over-cut 或漏禁。ghost-conditioned 前提 (cut 必须带 ghost anchor 条件) 在修复后仍完整?
④ **与 CUT-R8-H1/CUT-R9-H1 的一致性**: power 通道这个修复, 与 D2 通道的 support-augmentation (CUT-R8-H1) + precheck gate (CUT-R9-H1) 是同一套"separator cut 不得窄于模型 context"义务的实例。三个通道 (D2 / PCR / power) 的 support 收集口径是否一致 (都收全部 occupancy contributors)?

### Q2 power 通道纵深 (本轮深挖)

CUT-R12-H1 揭示 power-conditioned cut 通道之前审得浅。本轮深挖该通道其它角度: power subproblem 的 FEASIBLE 路径 (coverage witness 是否完整正确) / power coverage 在 master 内编码 (in-master coverage 与 subproblem 的等价性声明是否真成立) / `_selected_ghost_anchor()` 取不到时的 ABORT / power 通道与 whole-layout power-witness fail-closed 的交互。

### Q3 自由攻击角

以上之外, 用你自己的独立判断选你认为本面最薄弱的点深挖。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r12 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/master-geometry 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory **行为/性能**不审, 但 CUT-R12-H1 这类 gated cut 的 **soundness** 仍要审 (forensic-bypass 暴露面); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- C-3/C-4 latent 待办 (已挂账); F1-F9 `step_2`/`step_8` NotImplementedError (P1.3B 边界, 非缝)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3037 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 四点逐项判读 (口径对齐 / ABORT 彻底 / 弱化方向 / 三通道一致)。
- 前轮 clean/已修不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = CUT-R12-H1 修复确认 + power 通道纵深 + 自由攻击; 其余面不审。
