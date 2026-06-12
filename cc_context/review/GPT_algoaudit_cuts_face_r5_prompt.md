# 终末地 IndustrialPlanner 精确求解器 — cuts 机制面 round 5 (饱和确认轮·CUT-R4-H1 修复确认 + PCR-CUT 通道本体 + deletion-core 算法本体)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3f4ceebb.zip`, sha256 `3f4ceebb5606d2d2b054b5af82899202fc1dcdae8cee9c97626bbaf57b8e58b9`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: cuts 机制 (pose-bool/cell-pattern/lazy-demand/deletion-core/PCR/F1-F9), r2-r4 收敛轨迹 1→1→1, 本轮目标首个干净轮

本面近 3 轮 (报告在包内 `cc_context/review/archive/algoaudit_cuts_face_r{2..4}_REVIEW_2026061x.md`): r2 = CUT-R2-H1 (cell-pattern cut 把 binding 可选端口当必然激活 + lookup cache double-anchor); r3 = CUT-R3-H1 (generic 槽是 binding 容量非逐口需求, 修 = 饱和证明 [required==capacity 压 `__unused__`=0] + 容量 fail-closed); **r4 = CUT-R4-H1 (饱和只证非 `__unused__` 不证 routing-visible — 正数 required generic-output commodity 同时在 routing-free generic-input sink 集时, binding 把物理输出槽赋给无线商品后 `extract_port_specs()` 丢弃 = 该 front 不需可达, cut 仍当必然 routed → 误剪; 修 = `_required_generic_outputs_are_all_routing_visible()` [两集 disjoint, 异常 fail-closed False] 作为 generic_output_visible 第二合取, 混合需求 fail-closed 计 0)**。这些 cut 全部 env-gated (公开 certified 被 `pose_bool_master_not_certified` blocker 拦), 升级条件 = 未来 promote。**本轮 r5 = CUT-R4-H1 修复确认 + 两个从未独立审过的 cut 通道本体**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL-R3..R6 / F-GM-Q3 系列含 R5-A / F-RT-R2..R5 / F-PRE-R8..R10 条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R4-H1 修复确认 (攻击面)
① disjointness 检查 `_required_generic_outputs_are_all_routing_visible()` 的两个集合来源 (`required_generic_outputs` 正数集 vs `_routing_free_sink_commodities()` = `required_generic_inputs` 正数集) 与 binding 侧 `extract_port_specs()` 实际丢弃判据是否**同一口径** (binding 用 `self.routing_free_sink_commodities`, 构造参数可能与 owner 的 generic_io_requirements 不同源 — 有没有两边集合不同步的构造)? ② 「混合需求 fail-closed 计 0」在 lazy-demand/count cut 与 cell-pattern cache 两个消费者上是否都生效 (有没有第三个消费者读 saturation 却没读 disjointness)? ③ 异常 fail-closed False 的 except 范围会不会吞掉本应暴露的编程错误 (过宽 except = 静默弱化, 方向安全但值得确认)?

### Q2 PCR-CUT 通道本体 (新角度; env-gated `EXACT_B1_PATCH_ROUTING_CORE`, Phase 2-4 已落地但从未被独立外审)
PCR-CUT 流程: master OPTIMAL → routing precheck front_blocked → 提取 patch (≤900 cells) → 真 patch belt CP-SAT 求最小 conflict core (QuickXplain) → replay validate (presolve=false workers=1 重解必须 INFEASIBLE) → within-instance signature lifting → master nogood `sum_i sum_p x_var[i,p] <= K-1`。请独立审 (代码在 `src/search/benders_loop.py` PCR 分支 + `docs/research/pcr_cut_patch_routing_conflict_20260519/` 相关实现): ① **patch 边界 soundness**: patch 是全网格的子区域 — patch 内 INFEASIBLE 能推出全网格该布局 INFEASIBLE 吗 (patch 外的绕行路径被排除的依据是什么)? 这是该通道的核心数学前提, 请找出实现里编码这个前提的位置并判读它是否成立; ② QuickXplain 最小化的 oracle 调用 (cap 32) — cap 命中时返回的是「最小核」还是「某个核」, 非最小核会让 lifting 后的 nogood 更弱还是更强 (更强 = over-cut 方向, 必须查)? ③ replay validate 的环境 (presolve=false workers=1) 与原 solve 的等价性 — replay INFEASIBLE 是「证明」还是「复测」; ④ signature lifting 的 within-instance 限制 (PROJECT_LOCK 禁跨 instance) 在实现里是怎么强制的, 有没有 lifting 把不同 instance 的 pose 并进同一 nogood 的路径; ⑤ fail-closed: 任一 cut replay 不成 INFEASIBLE 必须不加 — 全 reject 后回落路径完好吗?

### Q3 deletion-core minimizer 算法本体 (新角度)
`src/search/routing_deletion_core_minimizer.py` (env `EXACT_B1_DELETION_CORE_CUT`): 从 front_blocked conflict 出发删格重判, 求最小阻塞核。请审: ① 删格重判的 oracle (`_oracle_front_blocked()`) 与真 routing precheck 的语义同构性 — oracle 更弱 (漏判 blocked) 会让 minimizer 提前停 = 核偏大 = cut 偏弱 (安全); oracle 更强 (误判 blocked) 会让核偏小 = cut 偏强 = **over-cut (必须查)**; ② 删除顺序对最小性的影响 — deletion-based minimization 得到的是 minimal (不可再删) 还是 minimum (全局最小), 实现把结果当哪种语义消费; ③ 得到的核转成 master cut 时的量化范围 (哪些 pose/instance 进 cut) 与核的实际支撑集是否一致 (超集 = over-cut)。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r4 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/routing 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82); C-3/C-4 latent 已挂账。
- F1-F9 lifecycle step_2/step_8 stub 状态 (历轮已核, 维持即可, 重报不算)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2974 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 PCR 前提编码位置判读与 Q3 oracle 同构性论证。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = CUT-R4-H1 修复确认 + PCR-CUT 通道本体 + deletion-core 算法本体; 其余面不审。
