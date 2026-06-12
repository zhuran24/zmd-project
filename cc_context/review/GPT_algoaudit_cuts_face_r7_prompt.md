# 终末地 IndustrialPlanner 精确求解器 — cuts 机制面 round 7 (饱和确认轮·PCR-CUT-R6-H1 修复确认 + QuickXplain/replay 本体 + patch 构造与 support 对接)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_37b84be0.zip`, sha256 `37b84be0749893447ccab8113934d8a518237702de0e00ed8d64176a913c57dd`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: cuts 机制 (pose-bool/cell-pattern/lazy-demand/deletion-core/PCR/F1-F9), 收敛轨迹 1→1→4 (r5)→1 (r6), 本轮目标首个干净轮

本面近 3 轮 (报告在包内 `cc_context/review/archive/algoaudit_cuts_face_r{4..6}_REVIEW_2026061x.md`): r4 = CUT-R4-H1 (饱和不证 routing-visible); r5 = PCR-R5-H1..H4 (全层边界/极性/blocker support/lifting 重叠); **r6 = PCR-CUT-R6-H1 (HIGH: patch 端口成员判据用「connector ∈ patch」— connector 在 patch 外但 terminal front 在 patch 内的端口被 `_index_port_fronts`/`_add_port_adherence`/separator 收集/local signature 四处整体丢弃; connector 是 occupied 格不入 active cells → boundary relaxation 永不为它开变量 = 端口注入/吸收能力消失, patch 比 full 严, 严格反例 full FEASIBLE/patch INFEASIBLE; 修 = 四处全改「connector 或 front 与 patch 相交」即纳入 + front-in-patch 外部端口入 signature)**。r6 还核了 ladder 5 rung 交互 (成功即 skip 无叠加/全失败 cut_stall+UNKNOWN) + cut 生命周期 6 场景 (单调累积/重建不带旧 cut/persisted 强制清空/within-instance 强制)。这些 cut 全部 env-gated (公开 certified 被 `pose_bool_master_not_certified` blocker 拦)。**本轮 r7 = R6-H1 修复确认 + 两个未深审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-GM 系列含 R7-HINT / F-RT / F-PRE 系列条款), 这些面各有自己的线, 别在本轮重报。本面主体自 r6 修复 (PCR-CUT-R6-H1, lock「terminal-front membership」第五义务条款) 后零代码变化, 该修复在本包内。

## 审查重点 (按优先级)

### Q1 PCR-CUT-R6-H1 修复确认 (攻击面)
① **新判据「connector 或 front ∈ patch」的完备性**: 还有没有第三种端口×patch 相交形态被漏 (connector 和 front 都在 patch 外但路由必须穿过 patch — 这种不需要端口语义, boundary relaxation 覆盖, 请验证这个论断; front 在 patch 内但不在 `_patch_free_cells` [被 occupied] — 处理方向?)? ② **front-in-patch 外部端口的 adherence 语义**: 修后这类端口加的是 exact terminal link 还是无条件 link — 它的 pose assumption 不在 patch 内时 assumption literal 从哪来, 缺 assumption 时 fail 方向? ③ **反向情形**: connector 在 patch 内但 front 在 patch 外 — 修前就处理吗, 修后语义变了没 (front 出 patch 应走 boundary relaxation 吸收, 验证)? ④ **signature 纳入的对称性**: front-in-patch 外部端口入 local signature 后, lifting 的等价类划分还正确吗 (同 signature 的两个 pose 必须对 patch 可行性等价 — 新增维度会不会把本应等价的 pose 分开 [安全] 或把不等价的并在一起 [必须查])? ⑤ **与 H3 support 的对接**: 外部 connector 的 owner pose 现在入 support assumptions 吗 — 该端口的存在依赖外部 pose 的放置, cut 不含它 = 又一个「blame victim」形态?

### Q2 QuickXplain 最小化与 replay 本体 (新角度; r5 只判了 cap 方向安全, 算法本体从未深审)
`src/models/patch_routing_core.py` 的 QuickXplain/最小化与 replay: ① **oracle 单调性前提**: QuickXplain 要求约束集可行性单调 (超集 INFEASIBLE ⊇ 子集判定) — patch assumption 子集求解的语义满足吗 (assumption 越多越约束 → INFEASIBLE 越可能, 验证实现里子集语义方向没反)? ② **QX 递归实现对照教科书算法**: 分割/递归/base case 的实现有没有偏差导致返回非 core (即返回的集合其实 SAT — 那 replay 会兜住吗)? ③ **cap 命中路径**: oracle 调用数撞 cap 时返回什么 — 当前候选集 (superset core) 还是失败? 返回 superset 时下游把它当什么消费 (更大 core = 更弱 cut = 安全, 但确认没有「当 minimal 消费」的元数据错标); ④ **replay validate 的独立性**: replay (presolve=false workers=1) 用的是同一个 model 对象重解还是重建 — 同对象重解会不会带上增量状态 (assumption 缓存/上轮 hint) 使 replay 不独立? ⑤ replay INFEASIBLE 之后、master cut 之前还有哪些步骤可能改写 core 内容 (augment support 等) — 改写后还需要再 replay 吗 (当前实现再不再)?

### Q3 patch 构造与 separator 对接 (新角度)
`src/search/patch_conflict_separator.py` 的 patch 提取: ① **patch cells 选择的 soundness 无关性论断验证**: 任意 patch 形状下「patch 模型 over-approx ⇒ cut sound」— 但实现里 patch 选择 (top-K, ≤900 cells cap) 截断时, port/active cells/assumption 收集是跟着截断后的 patch 走的吗 (收集基于截断前快照 = 口径错位)? ② **precheck summary → patch 的字段保真**: blocked_port/commodity 等从 routing precheck summary 读出转 PatchSpec/PatchPortSpec 时有没有字段丢失或方向/极性转换 (又一个 F-RT-R2-01 形态的转换点)? ③ **`full_grid_active_cells` 的来源时点**: separator 喂给 PatchRoutingCore 的 active cells 与当时 master solution 的 occupied 是同快照吗 (跨时点 = patch 模型用错域)? ④ **多 anchor/多 patch 并发**: top-K patches 逐个评估时共享什么状态 — 前一个 patch 的失败会污染后一个吗?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r6 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/master 几何/campaign/scheduler/routing 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82); C-3/C-4 latent 已挂账。
- F1-F9 lifecycle step_2/step_8 stub 状态 (历轮已核); QuickXplain cap 返回非最小核=弱 cut 方向 (r5 已判, Q2③ 审的是元数据标注不是方向本身)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2988 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 五点逐项结论、Q2 QX 单调性/递归对照、Q3 对接保真表。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R6-H1 修复确认 + QX/replay 本体 + patch 构造对接; 其余面不审。
