# 终末地 IndustrialPlanner 精确求解器 — cuts 机制面 round 8 (终饱和轮·跨通道 cut 语义族谱 + BendersCut/condition 本体 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_37b84be0.zip`, sha256 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。
注意: 包基点后仓库又落了 preprocess 面 F-PRE-R12-01 修复 (cycle RHS 闭包), 不在 cuts 主体; 本面主体文件与包一致。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: cuts 机制 (pose-bool/cell-pattern/lazy-demand/deletion-core/PCR/F1-F9), 收敛轨迹 1→4 (r5)→1 (r6)→0 (r7 零), 本轮 = 终饱和轮 (连零 2 达标轮)

本面近 4 轮 (报告在包内 `cc_context/review/archive/algoaudit_cuts_face_r{4..7}_REVIEW_2026061x.md`): r4 = CUT-R4-H1 (饱和不证 routing-visible); r5 = PCR-R5-H1..H4 (四义务); r6 = PCR-CUT-R6-H1 (terminal-front membership, lock 第五义务); **r7 = 零 soundness finding (首个干净轮)**: R6-H1 五向确认 (端口×patch 5 形态全表) + QX/replay 本体 (oracle 单调性/cap 由 replay 兜住/同 model 新 solver 无泄漏) + patch 构造对接 8 行保真表。这些 cut 全部 env-gated (公开 certified 被 `pose_bool_master_not_certified` blocker 拦)。**本轮 r8 = 终饱和轮: 两个未直审的横切角度 + 自由攻击角, 目标确认连零 2**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-GM 系列含 R7-HINT / F-RT / F-PRE 系列条款), 这些面各有自己的线, 别在本轮重报。cuts 主体自 r6 修复后零代码变化 (r7 零 finding 无补丁)。

## 审查重点 (按优先级)

### Q1 跨通道 cut 语义族谱比对 (新角度; 各通道单独审过, 横向语义对照从未做)
front_blocked ladder 的五种 cut 产物 (PCR patch-core nogood / deletion-core cut / lazy-demand count cut / cell-pattern cut / fallback selected nogood) + binding-local nogood + whole-layout routing_exhausted_nogood: ① 给每种 cut 列出**精确语义表**: 它禁止的解集合 (哪些变量组合)、它的证明义务来源 (patch CP-SAT replay / 删格 oracle / binding 容量 / 重解 INFEASIBLE / …)、生效 scope (per-candidate / per-ghost / whole-layout / conditioned); ② 逐条验证**语义 ≤ 证明义务**: 没有一种 cut 禁止的范围超出其证明实际覆盖的范围 (超出 = over-cut, 必须查); 特别核 scope 维度 — 证明在 candidate A 下做出, cut 是否可能在 candidate B 下生效 (condition lits 该挡的都挡了吗); ③ **弱序关系**: 同一冲突上不同通道产生的 cut 强弱排序, 确认 ladder 的 fallback 方向是「失败时换更弱/同等强度」而不是「升级成更强但证明更少」。

### Q2 BendersCut 构造与 condition 语义本体 (新角度; replay-condition lifecycle 此前只在 face 1 caller 侧审过, cuts 面对象本体没审过)
`BendersCut` 数据对象 + `_add_exact_persisted_nogood()` + condition lits 解析链 (`src/models/cut_manager.py` + benders_loop 构造点 + master apply 点): ① BendersCut 的字段集 (members/condition/kind/scope/hash) 在构造→序列化→apply 的全链上保真吗 — 有没有字段在某一跳被丢弃/默认化 (condition 丢失 = cut 无条件生效 = over-cut 方向, 必须查); ② condition lits 的语义: condition 表示「cut 仅在此上下文有效」— 解析失败/部分解析的 fail 方向是丢 cut (安全) 还是无条件加 (必须查); ③ kind/scope 字段的消费: 哪些 kind 允许进 master, 谁检查; ④ cut hash/dedup: 重复 cut 检测的 key 含 condition 吗 (不含 = 不同 condition 的同形 cut 被去重 = 丢 cut 或错配 condition)。

### Q3 自由攻击角 (终饱和轮惯例: 你自己选最薄弱的缝)
以上之外, 用你自己的独立判断选 1-2 个你认为本面还没被审透的点深挖 (例: deletion-core 与 PCR 对同一 conflict 的中间产物语义差异; F1-F9 family 中已接线部分的某个具体 family 数学; pose lookup cache 的失效时机; env 组合矩阵 [多个 cut env 同开] 的交互; 或对 r2-r6 某个历史修复设计你自己的新攻击)。说明你为什么选它、攻击了什么、结论是什么。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r7 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/routing 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82, r6 已核强制点); C-3/C-4 latent 已挂账。
- F1-F9 lifecycle step_2/step_8 stub 状态 (历轮已核); QuickXplain cap 非最小核=弱 cut 方向 (r5/r7 已判)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2990 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 cut 语义族谱全表、Q2 BendersCut 字段保真链、Q3 选点理由与攻击过程。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = cut 语义族谱 + BendersCut/condition 本体 + 自由攻击角; 其余面不审。
