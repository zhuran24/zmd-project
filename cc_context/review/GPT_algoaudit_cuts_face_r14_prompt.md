# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 14 (确认轮·CUT-R13-H1 修复确认 + FEASIBLE witness 通道纵深 + 自由攻击)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`, 对应干净 git 树 HEAD `8c61e1e`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

外置候选工件 `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包并已校验**, 不需要再生; 若校验对不上不准伪造, 停下报告。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制** (master 收紧用的所有 Benders/LBBD nogood / separator cut 通道)。

## 本面定义与历史: 上一轮 (r13) 抓出 CUT-R13-H1, 本轮 = 修复确认轮

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r10 零 + LOW CUT-R10-L1 (D2 owner gate); r11 零 (终饱和轮); r12 抓 1 HIGH CUT-R12-H1 (power INFEASIBLE cut 丢 unpowered fixed-occupancy support, 已修); **r13 抓 1 HIGH CUT-R13-H1**, 已修在本包内:

- **CUT-R13-H1 (delegated power FEASIBLE witness 在 selected ghost context 不可恢复时仍求解 de-ghosted 子问题)**: `EXACT_POWER_PLACEMENT_SUBPROBLEM=1` 时 coordinate master 不 materialize residual `power_pole` slots, power witness 由 `_run_power_placement_subproblem()` 事后补齐。`PowerPlacementSubproblem` 本体会把 `ghost_cells` 编入 fixed obstacle (`src/models/power_placement_subproblem.py:87-97`, `:110-151`), 但**原** FEASIBLE 路径只做 `ghost_cells = self._selected_ghost_cells()`, **即使该集合为空也继续 build/solve**, FEASIBLE 后直接 `inject_power_poles_into_solution()` 返回带 synthetic poles 的 solution。这与 INFEASIBLE cut 路径不对称 (后者 `_selected_ghost_anchor()` 取不到会 ABORT)。若 master 内部状态 / solver handle / `u_vars`·`_ghost_domains` 生命周期或未来 master 变体导致 ghost context 无法恢复, 子问题退化成"不知道 empty rectangle"的 power placement → **可能选一个实际落在 selected ghost rectangle 内的 pole, 把非法 witness 当成可行 completion** (= false-CERTIFIED 风险方向)。**gated/exploratory**: 默认 certified 被 `PROJECT_LOCK` L4a 与 env guard (deny-unknown) 阻断, forensic-bypass 才暴露; 但属 HIGH。

  **修在本包内** (`src/search/benders_loop.py:4768-4897`): ghost provenance 取数前移到 build 前 —— `_selected_ghost_anchor()` 取不到立即 `ABORT` (`:4780-4791`); `_selected_ghost_cells()` 为空立即 `ABORT` (`:4794-4802`); INFEASIBLE cut 路径复用同一 `(rect_idx, u_var, anchor)` (`:4792`, `:4855-4857`), 避免两条路径看到不同 ghost context。caller 对非 FEASIBLE / 非 CUT_ADDED 统一 `fail_closed_unknown` (`:4534-4561`), 不把 ABORT 当证明性结论。回归 = `src/tests/test_power_witness_cut_dilution.py:307` (`test_power_subproblem_aborts_when_selected_ghost_context_missing`: fake master 无 `u_vars`/`_ghost_domains`/`_solver`, 修复前从 FEASIBLE 注 pole witness, 修复后必须 `ABORT` 不产 cut/witness)。

**本轮 r14 = CUT-R13-H1 修复确认 + FEASIBLE witness 通道纵深 + 自由攻击角。**
**注意**: 本面已连续两轮 (r12 power INFEASIBLE / r13 power FEASIBLE) 在 **power-conditioned cut 通道** 各抓出一条此前轮次漏掉的 HIGH, **故本轮绝不能默认干净**, 请用最独立的判断。**不重报 CUT-R13-H1 修复项本身** —— 它已 lock。本轮把这个修复**钉成攻击面**: 找同型残留、反向缺陷、修复不完备 (见 Q1)。

注: 本包 (HEAD `8c61e1e`) 可能含其它面同期工件 (face 6 / face 8 确认轮等), 各面有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R13-H1 修复确认 (攻击面, 本轮主体)

① **FEASIBLE 与 INFEASIBLE 两路 ghost context 真的同源吗**: 修复声称两条路径复用同一 `(rect_idx, u_var, anchor)`。独立确认: `_selected_ghost_anchor()` 与 `_selected_ghost_cells()` 在同一次 solver state 下被读取, 二者解析出的 selected ghost rect 是否**保证同一个 rect_idx** (两个函数各自独立扫 `u_vars` 找 `Value==1`, 若有多个 u_var 同时为 1 / 或扫描顺序不稳定, anchor 与 cells 会不会指向**不同** ghost rect)? `_selected_ghost_cells()` 用 `ghost_domains[rect_idx].get("cells")`, `_selected_ghost_anchor()` 用 `ghost_domains[rect_idx].get("anchor")` —— 这两个 dict 字段在同一 domain entry 里是否**几何自洽** (anchor 与 cells 描述同一个矩形)? 不自洽时 cut 的 condition key `ghost_anchor::(x,y)` 会不会与子问题实际用的 ghost_cells 错配?

② **ABORT 前置守卫的彻底性 / 旁路**: 修复在 build **前** 用 `_selected_ghost_anchor() is None` 和 `not ghost_cells` 两道闸 ABORT。独立确认这两道闸覆盖**所有** ghost-context 不完整形态: (a) `_selected_ghost_cells()` 内部 `try/except: continue` 吞掉异常后返回**部分扫描**或空集 —— 空集已 ABORT, 但"非空但不完整 / 来自错误 rect"的集合能否漏过? (b) `_selected_ghost_anchor()` 返回非 None 但 `anchor` dict 缺 `x`/`y` 时走 `anchor.get("x", 0)` 默认 0 —— 这个静默默认 0 会不会让 condition key 退化成 `(0,0)` 而 cut 仍被写入 (INFEASIBLE 路径)? (c) ghost context 在 build/solve **之后** 是否可能被 master 状态改写 (TOCTOU), 使注入时的 ghost 与守卫时的 ghost 不一致?

③ **FEASIBLE witness 注入后的几何合法性谁来兜底**: 守卫保证子问题**带正确 ghost_cells 求解**, 子问题 `build()` 用 `occupied & fixed: continue` 过滤掉与 fixed (含 ghost_cells) 重叠的 pole pose (`power_placement_subproblem.py:116-126`)。独立确认: 被注入的 `selected_pose_indices` 对应的 pole **一定** 不与 ghost_cells 重叠 (即过滤是 pose 级 `occupied_cells` 全集对 fixed 求交, 而非仅覆盖锚点)? `inject_power_poles_into_solution()` 注入时是否对子问题给的 pose 做二次几何校验, 还是无条件信任? 若子问题因 TIMEOUT/部分 FEASIBLE 给出 pole, 会不会有 witness 落进 ghost rect?

④ **修复是否引入新的 false-INFEASIBLE / 过度 ABORT (availability 反向缺陷)**: 把 ABORT 前移到 build 前, 是否在**合法**场景下 (selected ghost 确实存在但 `_selected_ghost_cells()` 因 `u_vars`/`_ghost_domains`/`_solver` 任一为空而返回空集) 误 ABORT? 例如某些 master backend (pose-bool vs coordinate) 本就不挂 `u_vars`/`_ghost_domains`/`_solver` 这三个属性名 —— 那样 FEASIBLE 永远 ABORT, 退 UNKNOWN。这是**保守失败 (availability, LOW)** 还是会掩盖真问题? 区分清楚: false-CERTIFIED = soundness (HIGH/CRITICAL); 过度 ABORT/UNKNOWN = availability (LOW 加固)。

⑤ **三通道一致性复核 (power FEASIBLE 这条新边)**: CUT-R8-H1 (D2 support-augmentation) / CUT-R12-H1 (power INFEASIBLE occupancy support) 都是"separator/witness 用了哪些 constant occupancy, cut/witness 就必须带上同一 proof context"义务。CUT-R13-H1 把这条义务延伸到 **FEASIBLE witness 的 ghost support**。独立确认: power FEASIBLE witness 现在与 D2/PCR/power-INFEASIBLE 同套义务一致 —— witness 用了 ghost_cells 当障碍, witness 的合法性前提 (ghost provenance) 就必须在产 witness 前坐实。这条延伸有没有遗漏的对称面 (例如 routing/flow 诊断阶段是否也消费 selected ghost 而无同等前置守卫)?

### Q2 FEASIBLE witness 通道纵深 (本轮深挖)

CUT-R13-H1 揭示 delegated power **FEASIBLE** 路径之前审得浅 (此前轮次盯 INFEASIBLE cut 多)。本轮深挖 FEASIBLE witness 注入这条线的其它角度:
- **coverage witness 完整性**: 子问题 coverage 约束要求每个 powered instance ≥1 covering selected pole (`power_placement_subproblem.py:135-151`), 用 master 预计算 `_power_coverers_by_template_pose`。in-master coverage table 与 subproblem 读的 table 是否同源等价 (`master_model.py` / `pose_bool_exact_master.py` / `exact_coordinate_master.py` 的 table 构建 vs subproblem 读取)? 是否存在 powered instance 在 master 里被认为"可覆盖"但子问题 table 里查不到 coverer → 子问题 INFEASIBLE 误判, 或反之 master 漏算某 powered instance 而子问题不约束它 → witness 不覆盖它却仍 FEASIBLE?
- **pole-pole non-overlap**: 子问题 `cell_to_candidates` 按 cell 加 `sum<=1` (`:128-133`) —— 注入的多 pole witness 是否保证两两不占同格 + 不与任何 fixed 设施占格重叠?
- **`_powered_templates` 口径**: 子问题 `_powered_instances()` 只约束 `tpl in _powered_templates` 的 instance。若 `_powered_templates` 漏了某需电设施类型, 该设施不被要求覆盖 → witness 可能 FEASIBLE 但实际有设施没电。`_powered_templates` 的来源与 canonical 需电设施集是否一致 (这是口径正确性, 不是 owner 已定的 266 口径)?
- **whole-layout power-witness fail-closed 交互**: `_add_exact_whole_layout_nogood()` 在 flag on 且 solution 含 synthetic/any `power_pole` 时 fail-closed skip cut (`benders_loop.py` 附近), 避免 synthetic pole 无 master presence literal 时把 whole-layout cut 稀释。修复后这条交互是否仍完整 (FEASIBLE 注入 pole 后若后续阶段触发 whole-layout nogood, 是否仍正确 skip)?

### Q3 自由攻击角

以上之外, 用你自己的独立判断选你认为本面最薄弱的点深挖。鉴于 power 通道已连出两 HIGH, 你可以选择换出 power 通道、攻其它 cut 通道 (D2 commodity-flow separator / PCR-CUT patch separator / binding nogood / master-placement·whole-layout nogood / cut replay·persist lifecycle / lazy-demand·cell-pattern 饱和), 找一个 proof-context 投影 / literal identity / condition 生命周期最易藏错的点; 也可以继续 power 通道挖第三层。说明选点理由、攻击过程、结论。

## 明确不要报的

- **已 lock 的本面已修条款 (列出, 重复报不算)**: CUT-R8-H1 (compiled constant support 必须进 master tuple) / CUT-R9-H1 (D2 precheck gate) / CUT-R10-L1 (D2 owner gate, LOW) / CUT-R12-H1 (power INFEASIBLE cut 的 occupancy support 扩展) / **CUT-R13-H1 (本轮攻击面, 修复项本身已 lock, 只审同型残留/反向缺陷/不完备, 不重报修复点本身)**; r2-r13 已修 finding 与已审结论 (重复报不算)。
- 设计决策 (canonical / 266 口径 / `min_side >= 6` admissibility / omni_wireless / 52-Port 不变量, owner 已定)。
- preprocess / binding / campaign / scheduler / routing / master-geometry 各面 (各自有线); 怀疑跨面时**交叉引述 PROJECT_LOCK 契约**而非在本轮重证。
- exploratory **行为/性能**不审; 但 CUT-R13-H1 这类 gated cut 通道的 **soundness** (forensic-bypass 暴露面) 仍要审。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; F1-F9 `step_2`/`step_8` NotImplementedError (P1.3B 边界, 非缝)。
- persisted `exact_safe_cuts` 是 telemetry 非 proof (V82); certified mode 下 `raw_candidate_cuts=[]` 是代码强制。
- C-3/C-4 latent 待办 (已挂账)。

## 自验环境与已知基线

- candidate 已随包。全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3058, 具体数目以实跑为准; 硬不变量 = **0 failed**); 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`。跑不完就跑专项 (power / cuts / D2 / PCR / binding-lifecycle) + 如实声明哪些没跑完, **不许把超时谎报成全绿**。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (8 obligations anchored)。
- finding 必须带**可复现 probe** 或**严谨 file:line 论证**; 实证推翻你的怀疑 (跑出来证明守卫生效 / 几何不可能 match) 就**不要报**。
- 引用 file:line 必须**真实** (照你解包后的实际文件核对, 别编行号)。

## 严重度纪律

- **false-CERTIFIED** (cut 误删合法 layout 致最优解丢失 / witness 把非法解认证成可行) = **soundness**。P1.2 闭环只认这个; 这是 HIGH/CRITICAL。
- **false-INFEASIBLE / 过度 ABORT·UNKNOWN** (保守失败, 不会误认证, 只是少跑出本可证的解) = **availability**, 标 **LOW** 加固。
- 修复方向: soundness 缺口必须 fail-closed (宁可 UNKNOWN 不可 false-CERTIFIED)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 五点逐项判读 (① 两路同源 / ② ABORT 彻底·旁路 / ③ 注入几何合法性 / ④ 反向过度 ABORT / ⑤ 三通道一致) + Q2 纵深结论 + Q3 自由攻击结论。
- 前轮 clean/已修不代表本轮默认干净; 本面连续两轮 power 通道出 HIGH, 请按你自己的**独立判断**下结论, 真 Pro 确认轮独立背锅。

## 范围边界

- 重点 = CUT-R13-H1 修复确认 + FEASIBLE witness 通道纵深 + 自由攻击; 其余面 (preprocess/binding/campaign/scheduler/routing/master-geometry) + 各自子问题正确性**不审**, 列入不审范围。
