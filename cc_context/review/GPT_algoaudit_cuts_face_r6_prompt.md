# 终末地 IndustrialPlanner 精确求解器 — cuts 机制面 round 6 (饱和确认轮·PCR-R5 四义务修复确认 + ladder 多 rung 交互 + cut 跨迭代生命周期)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_38b57070.zip`, sha256 `38b570700c77f3f1a7b3f6c2ac7e9c2f2ec6385c7a93c2ee34ca7ce857ab8abe`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: cuts 机制 (pose-bool/cell-pattern/lazy-demand/deletion-core/PCR/F1-F9), 收敛轨迹 1→1→1→4 (r5), 本轮目标首个干净轮

本面近 3 轮 (报告在包内 `cc_context/review/archive/algoaudit_cuts_face_r{3..5}_REVIEW_2026061x.md`): r3 = CUT-R3-H1 (generic 槽饱和证明); r4 = CUT-R4-H1 (饱和不证 routing-visible, 修 = disjointness 第二合取); **r5 = PCR-CUT 首审爆 4 HIGH 全 over-cut 方向, 已修 (PCR-R5-H1..H4)**: H1 = boundary relaxation 只开 ground 层 (elevated 跨界被禁 → patch 比全网格更严, 违反「patch 必须 over-approximate 全 routing」核心前提; 修 = 全层边界变量); H2 = patch sink front 极性用 `ps.direction` 应为 `DIR_OPP[ps.direction]` (F-RT-R2-01 极性类在重实现复发; 修 = DIR_OPP); H3 = patch 内 blocker 设施 footprint 以常量身份占格、不入 conflict core (cut 漏真 blocker 把 victim 无条件禁; 修 = `_patch_support_signature_cells()` [patch + 四向邻居] 上的 occupancy owner 以 assumption 身份入 core, `_augment_core_with_patch_support()` 并入 master cut); H4 = signature lifting 对重叠 lifted var 重复计入 (共现禁退化成单 pose 禁; 修 = 重叠检测 → `added=False` 不加 cut)。r5 还确认 CUT-R4-H1 修复 sound + deletion-core 通道干净 (oracle 弱方向安全/minimal 语义一致/量化范围==支撑集)。这些 cut 全部 env-gated (公开 certified 被 `pose_bool_master_not_certified` blocker 拦)。**本轮 r6 = PCR-R5 修复确认 + 两个未深审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-GM 系列含 R6-01 / F-RT-R2..R5 / F-PRE-R8..R11 条款), 这些面各有自己的线, 别在本轮重报。本面主体自 r5 修复 (PCR-R5-H1..H4) 后零代码变化, 该修复在本包内。

## 审查重点 (按优先级)

### Q1 PCR-R5-H1..H4 修复确认 (攻击面, 逐个攻击 + 相互作用)
① **H1 全层边界**: 修后每个 LAYER 在 patch 边界都开了出入变量 — 边界变量的约束形态 (无代价自由出入?) 是否使 patch 模型对「经 patch 外绕行」严格 over-approximate? 有没有某层/某方向的边界仍然被禁 (residual 缝)? ② **H2 极性**: 修后 patch sink front `send_dir = DIR_OPP[ps.direction]` — 与 `routing_subproblem` 的 sink 极性 (`flow_out = Opp(port_dir)`) **从规则文本独立推导后**对照 (别从实现学实现, F-RT-R2-01 的 fuzz oracle 同源反教训); source 侧极性顺带核。③ **H3 support 充分性**: support signature cells = patch + 四向 cardinal 邻居 — 还有没有 master 决策影响 patch belt 可行性但不在该集合 (对角邻居? port connector 伸入? 远程效应?)? occupancy owner → master assumption literal 的映射保真 (owner 解析失败时 fail 方向)? ④ **H4 重叠回落**: `added=False` 后 caller 的回落 — 无 cut 但有没有任何状态被误标 (如该 conflict 被记成已处理)? ⑤ **四修复相互作用**: H1 边界×H3 support 的组合 (边界格的 owner 算 support 吗), H2 极性×replay validate (replay 用修后极性重验过吗)。

### Q2 front_blocked ladder 多 rung 交互 (新角度; 单 rung 各审过, 交互从未审)
front_blocked 处理 ladder: PCR-CUT → deletion-core → lazy_demand → cell_cut (env 组合决定哪些 rung 在场)。请审 `benders_loop` 的 front_blocked 分支: ① **次序与互斥**: 同一 conflict 上 PCR 成功加 cut 后还会继续走 deletion-core 吗 — 多 rung 对同一 conflict 各自加 cut 时, cut 叠加 (交集更小) 有没有可能比任一单 cut 更强到 over-cut (每个 cut 单独 sound 则叠加 sound — 验证每个 rung 的 cut 都是独立 sound 的, 不依赖「前面 rung 没加过」)? ② **全失败回落**: 所有在场 rung 都 reject/fail 后, 最终回落是 UNKNOWN/不剪 (fail-closed) 还是有路径把「ladder 走完」误当「证明完成」? ③ **rung 间状态泄漏**: 前一 rung 的中间产物 (patch/core/oracle 缓存) 被后一 rung 复用时语义还对吗 (PCR 的 patch 域 vs deletion-core 的删格域是不同抽象)?

### Q3 cut 跨迭代生命周期 (新角度)
master 收 cut 后跨 iteration 的存续语义: ① **同一 master 实例内**: cut 累积单调吗 — 有没有路径移除/覆盖已加 cut (移除 = 已排除解复活)? ② **master 重建时**: 哪些场景重建 master (candidate 切换/重入/resume)? 重建后旧 cut 带不带过去 — 带 = 旧 cut 对新 candidate 仍有效吗 (cut 的有效性依赖加 cut 时的 candidate 上下文吗, 逐 cut 类别判读); 不带 = 纯收敛性问题 (安全) 还是有「重建后跳过已知冲突的重发现」假设? ③ **persisted `exact_safe_cuts` telemetry-only 边界**: V82 已判 persisted cuts 永不作 proof — 在当前代码里找出强制这个边界的位置 (load 侧拒绝? apply 侧降级?), 确认没有路径把磁盘 cut 直接当有效 cut 重放; ④ **within-instance lifting 限制** (PROJECT_LOCK 禁跨 instance) 在 H4 修复后仍被强制的代码位置。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r5 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/routing 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, Q3③ 审的是该边界的代码强制点不是重判设计); C-3/C-4 latent 已挂账。
- F1-F9 lifecycle step_2/step_8 stub 状态 (历轮已核, 维持即可, 重报不算)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2982 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 四修复逐项攻击结论、Q2 ladder 次序判读、Q3 生命周期逐场景表。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = PCR-R5 修复确认 + ladder 交互 + cut 生命周期; 其余面不审。
