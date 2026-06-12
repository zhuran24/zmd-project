# 终末地 IndustrialPlanner 精确求解器 — cuts 机制面 round 3 (饱和确认轮·CUT-R2-H1 修复攻击面 + nogood 作用域最小性角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_cut_r3_snapshot_b377a2a7.zip`, sha256 `b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面历史与本轮定位

cuts 面轮次史: r1 (C-3 F2 容量 / C-4 readiness blocker, latent 非公开路径, 挂账); **r2 live exact-safe 轮抓 1 P2 hardening 已修 — CUT-R2-H1**: env 门控 pose-bool cell-pattern cut (`add_routing_port_blocking_cell_cut`, 形状 `sum(port_candidates) + sum(blocker_candidates) <= 1`) 把「binding 可选端口」当「必然激活端口」量化 — visible demand 不覆盖该 side 全部物理端口时, blocker 挡 inactive slot 的合法 placement 被 over-cut (反例: 双输入口 demand=1 + blocker 挡第一口 front, binding 走第二口本可行); 同源: `_build_port_lookup_cache` 对 global 坐标 pose data double-anchor → 幻影格 alias。修 = `_mandatory_port_side_is_cell_pattern_exact()` (input 侧 `demand >= 物理端口数` / output 侧 visible 非零 = total 且 `>= 端口数` 才登记 raw per-cell; RO pose 无 binding identity 不登记; 混合侧留给更弱但 exact 的 lazy-demand) + cache 直用 global 坐标。lock 新增 F-CUT-R2-01 + specs/10 §10.8。r2 还核了六 cut 族 exact-safe 矩阵 / `exact_safe_cuts` resume 消费点穷举 (V82 telemetry-only 代码强制) / cut 间交互 / F1-F9 框架边界 (step_2/step_8 仍 NotImplementedError)。**本轮 r3 = CUT-R2-H1 修复确认 + 刻意换角度**。

注意: 公开 certified 默认路径上非默认 proof-semantics env 全被入口 blocker 拦 (pose-bool/deletion-core/lazy-demand/PCR/D2 都不可达), 本面的发现多为 env-gated hardening — 但「未来 promote 时升级为 soundness」的前提缺陷照报。包内带着其它面同期修复 (lock 末 F-BIND/F-BL/F-GM/F-RT/F-PRE 系列), 各有线别重报。

## 审查重点 (按优先级)

### Q1 CUT-R2-H1 修复确认 (攻击面)
① `_mandatory_port_side_is_cell_pattern_exact()` 的前提本身: input 侧 `input_demand >= port_count` 是否真保证「pose 选中 ⇒ 该 side 每个物理端口必然 active 且 routing-visible」— 注意 binding 的 fixed pattern 枚举语义 (端口选择是按 slot 组合枚举的), demand 数值够数但 binding 是否仍可能选择**子集之外**的组合使某端口 inactive? ② output 侧三条件 (visible 非零 / visible == total / demand >= 端口数) 有没有漏掉一个使「mixed 侧被错误登记」的输入形态 (probe 构造)? ③ `_profile_port_demands` 异常时 `return False` (fail-closed 不登记) — 这个方向对吗 (不登记 = 该 side 不参与 cell cut = 弱化非 over-cut, 应当 sound, 请确认)? ④ cache global 坐标修复后, 全文件还有没有别处对 candidate pose data 重复加 anchor (r2 只点了 `_build_port_lookup_cache` 与 pole cache 两处)?

### Q2 nogood 作用域最小性与 condition_lits 语义 (新角度)
r2 审过各 cut 族的形状与有效性前提; 本轮审 **literal 集边界**: ① binding-level nogood 的 literal 集 (`extract_selection` → `add_nogood_cut`): 包含全部 generic slot 选择 — literal 集**过大**只是弱化 (排除更少 = sound), **过小**才是 over-cut (排除未证伪的邻近 selection); 有没有 selection 维度**没**进 literal 集但**影响** routing 结果的 (= 同一 literal 组合下另一个真实不同的 binding 被连带排除)? ② master placement nogood 的 condition_lits (`OnlyEnforceIf`): 条件集是证明成立的上下文 — 条件集**漏掉**一个证明依赖的上下文变量 = cut 在其它上下文里也生效 = over-cut 方向; 逐个登记点核对 condition_lits 是否完整覆盖证明上下文 (特别是 ghost 锚点/condition domain)。③ whole-layout nogood 的 power witness synthetic pole fail-closed skip (r2 已点) 的边界维持确认。

### Q3 抽查维持
r2 已审结论抽查 2-3 处 (V82 telemetry-only 边界 / lazy connectivity cut 自检回退 / F1-F9 框架无 certified runtime apply), 不用全量重审。C-3/C-4 latent 挂账状态确认 (P1.3B 前必修清单还在不在文档里)。

## 明确不要报的

- r1/r2 已修 finding 与已审结论复述 (但其修复的**新**缝算); C-3/C-4 挂账本体 (owner 已知)。
- binding/master/routing/preprocess/campaign/scheduler 各面 (各自有线)。
- 设计决策 (canonical/266/52-Port); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, 已两轮确认)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 `adcc2a6e…`, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2955 passed, 0 failed)**; 跑不完跑专项 (src/tests/cuts / test_wireless_front_consumers_r4 / test_p0_certified_soundness_fixes) + 如实声明 (`-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); over-cut 类给出被误剪的可行 placement 实例; 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 实际核过的 nogood 登记点 × condition_lits 对照清单。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = CUT-R2-H1 修复确认 + nogood 作用域最小性/condition_lits + 抽查维持; 其余面不审。
