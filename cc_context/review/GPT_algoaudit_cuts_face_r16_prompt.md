# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 16 (确认轮·CUT-R15-H1 修复确认 + delegated power witness **注入回写**侧纵深 + 自由攻击)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_0590f9ca.zip`, sha256 `0590f9ca30aac5bb7afe18945eb36d347ea8b0c5b467fd6baff4679eff8c5234`, 对应**干净 git 树** HEAD `7fec29a` (rounds 1+2 全部修复**已合入**, 这是带修复的新树, 不是上一轮的树)。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告, 不准伪造或将就别的包**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

外置候选工件 `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包并已校验**, 不需要再生; 若校验对不上不准伪造, 停下报告。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制** (master 收紧用的所有 Benders/LBBD nogood / separator cut 通道, 以及 delegated power witness/cut 通道)。

## 本面定义与历史: delegated power 通道已**连出四 HIGH**, 本轮 = CUT-R15-H1 修复确认 + 注入回写侧深挖

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r10 零 + LOW CUT-R10-L1 (D2 owner gate); r11 零 (终饱和轮); r12 抓 1 HIGH CUT-R12-H1 (power INFEASIBLE cut 丢 unpowered fixed-occupancy support, 已修); r13 抓 1 HIGH CUT-R13-H1 (delegated power FEASIBLE 在 ghost context 不可恢复时仍求解 de-ghosted 子问题, 已修); r14 抓 1 HIGH CUT-R14-H1 (delegated power 的 ghost provenance 在 anchor 与 cells 之间可错配, 已修); **r15 抓 1 HIGH CUT-R15-H1**, 已修在本包内:

- **CUT-R15-H1 (delegated power FEASIBLE witness 在「已有 pole」混合上下文里可注入重叠 synthetic pole)**: r12-r14 三条修复把审查焦点收口到「ghost 上下文坐实之前」的彻底性。r15 把火力前移到**注入回写侧**, 发现: 当传入 master solution **已经包含一个 `power_pole` entry**时, 子问题 `_fixed_occupied_cells()` (`power_placement_subproblem.py:87-97`) **显式跳过**所有 `power_pole`(因为 `PowerPlacementSubproblem` 本来就拥有 pole 选择, 把候选 pole 当障碍是错的), 但 `inject_power_poles_into_solution()` (`power_placement_subproblem.py:192-215`) **无条件信任**子问题给的 `selected_pose_indices`, **没有**对注入 pose 的 occupied_cells 与已有 pole / fixed occupancy 做二次 disjoint 断言。于是在这个混合上下文里, 子问题可以选一个 **不同 `pose_id` 但同 cell** 的 pole pose, 注入后得到 **两个 power_pole 落在同一 cell** 的 witness-certified solution (= false-witness 方向)。canonical 不可达 (delegated power 在 certified 模式被 `pose_bool_master_not_certified` / forensic gate 阻断, 子问题正常拥有全部 pole, solution 不会带预先 materialized 的 pole), 暴露面 = forensic/未来 caller 喂混合 solution; **gated/exploratory** (`EXACT_POWER_PLACEMENT_SUBPROBLEM`, deny-unknown), 但属 HIGH。

  **修在本包内** (`src/search/benders_loop.py:4878-4895`): `_run_power_placement_subproblem()` 在 build 子问题**之前**扫描 `solution` 里任何 `facility_type == "power_pole"` 的 entry, 一旦存在就 fail-closed `return "ABORT", None` (不 build, 不出 witness, 不出 cut), 并发 `abort_preexisting_power_pole_context` heartbeat。修复理由 (照抄注释): 在已 materialized pole 之上重解会要求那个 pole 同时作为 FEASIBLE witness 与 INFEASIBLE cut 的 proof support; 在那套混合 proof context 建模之前, ABORT 是安全的。回归 = `src/tests/test_power_witness_cut_dilution.py` 新增 `test_power_subproblem_aborts_when_solution_already_has_power_pole` (混合 solution + selected ghost + 同 cell 不同 pose_id 候选 → 必须 ABORT, 无 payload, 无 cut)。LOCK 登记见 `PROJECT_LOCK.md` 第 3 节 CUT-R15-H1 条款 (`PROJECT_LOCK.md:153`)。

**本轮 r16 = CUT-R15-H1 修复确认 + delegated power witness 注入回写侧纵深 + 自由攻击角。**
**注意**: 本面已**连续四轮** (r12 power INFEASIBLE / r13 power FEASIBLE de-ghost / r14 power FEASIBLE anchor-cells 错配 / r15 power FEASIBLE 已有 pole 混合注入) 在 **delegated power witness 通道** 各抓出一条此前轮次漏掉的 HIGH, **故本轮绝不能默认干净**, 请用最独立的判断。**不重报 CUT-R15-H1 修复项本身** —— 它已 lock。本轮把这个修复**钉成攻击面**: 找同型残留、反向缺陷、修复不完备 (见 Q1), 并把火力**继续沿注入回写侧深挖**到「ghost 上下文已坐实、混合-pole 已挡、子问题 FEASIBLE 之后, witness pole 真正被写回 certified solution 那一格」剩下的所有 proof-context 缝 (见 Q2)。

注: 本包 (HEAD `7fec29a`) 含其它面同期工件 (master / benders / preprocess / binding / campaign / scheduler 各面 env-gated hardening 确认轮、handoff stamp、八面外审台账等), 各面有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R15-H1 修复确认 (攻击面, 本轮主体)

① **「pre-existing pole」检测的彻底性与判据形态**: 修复用 `str((entry or {}).get("facility_type")) == "power_pole"` 扫描整个 `solution` (`benders_loop.py:4878-4882`), 任一命中即 ABORT。独立确认: (a) 这个判据**只看 `facility_type` 字段**, 是否覆盖了 r15 probe 的全部 false-witness 形态? 例如一个 entry **不带** `facility_type=="power_pole"` 但其 `pose_idx` 指向 pole_pool 里的 pose (或 synthetic_id 形如 `pose_optional::power_pole::...` 但 `facility_type` 被改写/缺失), 是否绕过这条扫描却仍在子问题/注入侧造成 pole 重叠? (b) 注入产物 synthetic entry 的 `facility_type` 确实是 `"power_pole"` (`power_placement_subproblem.py:206`); 那么**同一 controller 在同一 candidate 内多次进入 `_run_power_placement_subproblem`** (例如 INFEASIBLE cut 后 master 重解再回来) 时, 上一轮注入的 pole 会不会留在 solution 里, 让下一轮这条扫描直接 ABORT (availability) —— 还是每轮 solution 都是 master 全新 solve 的产物 (不带上轮注入)? 请用 `benders_loop.py` 的 candidate 主循环确认 solution 的来源生命周期, 区分清楚这是「正确防再注入」还是「会误伤合法重解」。

② **ABORT 与 INFEASIBLE/cut 两路的对称性**: 修复在 build **之前** ABORT, 因此**既不出 FEASIBLE witness 也不出 INFEASIBLE cut**。独立确认: (a) 一个**合法**且**确实 power-INFEASIBLE**的 master layout, 若恰好 solution 里带了一个 pole entry (forensic/未来 caller), 现在被这条扫描提前 ABORT 掉了 → 不再产出本该产出的 ghost-conditioned INFEASIBLE cut → 退 UNKNOWN。这是**保守失败 (availability)** 还是会**掩盖一个本应被 cut 永久排除的 layout**(让它在后续 candidate 反复浪费预算)? 区分: false-CERTIFIED = soundness; 丢 cut/退 UNKNOWN = availability。(b) ABORT 在 `_run_power_placement_subproblem` 的返回契约里是 `("ABORT", None)`; 沿调用链 (`_run_exact_binding_and_routing` / 主循环) 确认 ABORT 一定坐实为 fail-closed **UNKNOWN**(no cut / no certify), 没有任何路径把 ABORT 误读成 FEASIBLE-skip 或 INFEASIBLE-继续。

③ **修复是否真把「重叠 pole」这一类彻底关死, 还是只关了「已有 pole」这一个入口**: r15 修的是「solution **已含** pole」。独立确认: 在**没有**预先 pole 的正常路径里 (这条没被 r15 改动), 子问题自身的 pole-pole 非重叠约束 (`power_placement_subproblem.py:128-133` 的 `AddAtMostOne` per cell) + fixed-occupancy 过滤 (`:116-126`) 是否**足以**保证 `selected_pose_indices` 里任意两个 pose 不共格、且不压 fixed master occupancy / ghost cells? 注意 `cell_to_candidates` 只对 **>1 候选** 的 cell 加 `<= 1` (`:129-130`), 单候选 cell 不加约束 —— 这对**单个 pose 内部多格**或**两个 pose 共享某格但该格只被其中一个 pose 登记**的情形是否仍正确? 即: 一个 pose 的 `occupied_cells` 是否一定被**完整**登记进 `cell_to_candidates`(`:125-126` 对 pose 每个 cell 都 setdefault append), 有没有 pose 多格里**部分格**与另一 pose 重叠却因登记/去重差异漏掉 `AddAtMostOne` 的缝? 用包内 pole_pool 的实际 pose 几何 (1×1 还是多格?) 坐实, 别凭猜。

④ **注入侧仍无二次几何校验 (r15 自己点了但没升格, 本轮独立复判)**: r15 REVIEW 在 §Q2 明确说 `inject_power_poles_into_solution()` (`power_placement_subproblem.py:192-215`) 在「无 pre-existing pole」时**仍无**二次 disjoint 断言, 只是认为子问题约束足够而判它冗余。独立判断: 在 r15 只关了「已有 pole」入口之后, 注入侧这道缺失的二次校验是否仍可被**别的入口**触发出 false-witness —— 例如 ④③ 的单候选-cell 漏约束、selected pose 来自非预期 solver 状态、或 pose pool 在子问题 `build()` 与 `inject` 两处**不同源** (`self.facility_pools` vs `self.master.facility_pools`, `benders_loop.py:4913` vs `:4932`, 确认是否同一对象/同一 pose 索引语义)? 若两处 pool 同源且子问题约束完备 → 仍是冗余 (LOW, 顶多防御纵深); 若存在任一不一致路径 → 升格。**请独立给出判据, 不要照搬 r15 的「冗余」结论。**

### Q2 delegated power witness **注入回写**侧纵深 (本轮主深挖, 火力锁定「写回那一格」)

r12-r15 的修复已把「ghost 上下文坐实之前」+「已有 pole 混合」两类关死。本轮**主深挖方向 = 子问题 FEASIBLE 之后, synthetic pole 写回 certified solution 的最后一段里, ghost 上下文与最终落格之间剩余的所有断点**。前几轮都在「入口/坐实前」, 注入回写侧只被 r15 关了「已有 pole」这一个角, 其余角未被独立钉过:

- **注入 pole vs **最终** selected 空矩形 (TOCTOU on the empty rectangle, 本轮重点猜想)**: 子问题用 `_selected_ghost_context()` 恢复的 `ghost_cells` 当**障碍**避让 (`benders_loop.py:4909/4916`, 子问题 `build()` 把 `ghost_cells` 并进 `_fixed_occupied_cells()` 起点 `:88`)。但**注入回写** (`inject_power_poles_into_solution`, `:192-215`) **不带** ghost_cells 参数, **不重新断言**写回的 pole 避开了那个最终会被认证为「空矩形」的 ghost rect。独立判断: (a) 子问题 build 时避让的 `ghost_cells` 与最终 certified solution 里真正被当作空矩形的那块, 在产 witness 与写回之间是否**保证同一**(同一 `rect_idx`/同一 anchor/同一 cell 集), 还是存在 master 状态在 build→inject 之间漂移、或 `_selected_ghost_context()` 恢复的 cells 与下游空矩形坐标系/偏移不一致的缝? (b) 即便子问题正确避让, **注入侧零二次断言**意味着一旦 `selected_pose_indices` 来自任一非预期来源 (Q1③/④ 的单候选漏约束、未来 solver 状态), 写回时**没有最后一道防线**阻止 pole 落进空矩形 —— 这是否值得在注入侧补一道 `injected_pole_cells ∩ ghost_cells == ∅` 的 fail-closed 断言? 给出「子问题已保证→冗余 LOW」还是「存在断点→soundness」的独立判据。

- **FEASIBLE-but-not-OPTIMAL 边界**: `solve()` 把 CP-SAT `OPTIMAL` 与 `FEASIBLE` 都映射成 `status="FEASIBLE"` 并返回 selected (`power_placement_subproblem.py:164-177`); controller 在 `result.status == "FEASIBLE"` 即注入 (`benders_loop.py:4928-4935`)。独立确认: time-limit 内找到可行但未证最优的 `FEASIBLE` selected 集, 是否**一定满足全部约束** (coverage `>= 1` per powered instance + pole-pole 非重叠 + fixed/ghost 不压)? CP-SAT 返回 FEASIBLE 时 incumbent 必满足所有硬约束, 所以此处把 FEASIBLE 当可行注入应 sound (power placement 只需可行不需最优) —— 但请独立坐实: 有没有约束是用「软」方式 (objective/惩罚) 而非硬约束表达, 导致 FEASIBLE incumbent 可能违反它? 看 `build()` 全部 `model.Add(...)` (`:128-151`) 确认全是硬约束、无 objective。

- **TIMEOUT→ABORT 的语义**: 子问题 `solve()` 非 OPTIMAL/FEASIBLE/INFEASIBLE 即返回 `status="TIMEOUT"` (`:189`), controller 把 TIMEOUT 落到 `return "ABORT", None` (`benders_loop.py:5003-5004`)。独立确认: TIMEOUT 时既不注入 witness 也不出 cut, 一律 fail-closed UNKNOWN —— 有没有路径把 TIMEOUT 的空 `selected_pose_indices` 误当 FEASIBLE 注入 (空注入是 no-op 还是有副作用)? 以及 INFEASIBLE 分支里 `conflict_set` 收集遇 `pose_idx` parse 失败 `return "ABORT", None` (`:4955-4958`) 是否覆盖全部异常形态。

- **ghost-conditioned INFEASIBLE cut 的 condition 生命周期 (注入侧的对称面)**: power INFEASIBLE cut 写 `condition_set={f"ghost_anchor::({x},{y})": rect_idx}` + `condition_lits=(u_var,)` (`benders_loop.py:4962-4986`)。注入 FEASIBLE 那一路不产 cut, 但**同一 candidate 内** FEASIBLE 注入与之前/之后的 INFEASIBLE cut 共享 `_selected_ghost_context()`。独立确认: (a) cut replay 时 `_resolve_condition_lits_from_condition_set()` (`:1524` 起) 用 condition_set 的 anchor key + rect_idx value 重新解析 literal —— key 里只有 (x,y) 没有 rect_idx, 两个不同 rect_idx 的 ghost 恰好同 anchor 坐标 (canonical 不可达, forensic/外部 condition_set 可构造) 时, replay 会不会把 cut 挂错 ghost literal? (b) 注入 synthetic pole 后, 若后续阶段 (binding/routing) 触发 whole-layout nogood, `_add_exact_whole_layout_nogood()` 在 flag-on 且 solution 含 synthetic `pose_optional::power_pole::...` **或**任意 `facility_type=="power_pole"` 时 fail-closed skip (`benders_loop.py:6773-6791`) —— 这条 skip 与 r15 的「已有 pole 即 ABORT」是否一致 (都把「solution 里有 pole」当不安全信号)? 还是两处对「有 pole」的处理存在不一致的缝 (一处 ABORT 一处 skip-cut, caller 后续动作是否都坐实为 UNKNOWN)?

### Q3 自由攻击角

以上之外, 用你自己的独立判断选你认为本面最薄弱的点深挖。鉴于 delegated power 通道已**连出四 HIGH**, 你可以选择:
- 继续 power 通道挖第五层 (注入回写侧剩余角, 见 Q2; 或 coverage table 同源等价性 —— 子问题读 master 预计算 `_power_coverers_by_template_pose` `power_placement_subproblem.py:135-151`, 与 master 侧 in-master coverage `exact_coordinate_master.py:5167` 读同一 table, 确认是否真同源等价、有没有 powered instance 在 master 被认为可覆盖但子问题查不到 coverer → false-INFEASIBLE, 或反之 master 漏算而子问题 `_powered_instances()` 也不约束它 → witness 不覆盖却 FEASIBLE 的 soundness 方向; `_powered_instances()` 用 `tpl in self._powered_templates` 过滤 `:99-108`, 确认子问题收到的 `powered_templates` 与 master coverage 约束用的是否**同一集合**);
- 或换出 power 通道, 攻其它 cut 通道 (D2 commodity-flow separator / PCR-CUT patch separator / binding nogood / master-placement·whole-layout nogood / cut replay·persist lifecycle / lazy-demand·cell-pattern 饱和), 找一个 proof-context 投影 / literal identity / condition 生命周期最易藏错的点。

说明选点理由、攻击过程、结论。**自由攻击点若与前轮 (r10-r15) 已扫过零 finding 的角度重合** (persisted `exact_safe_cuts` telemetry-only / condition-lits replay / D2 support-context / coverage table 同源), 请说明你看到了前轮没看到的**新角度**, 否则换点。

## 明确不要报的

- **已 lock 的本面已修条款 (列出, 重复报不算)**: CUT-R8-H1 (compiled constant support 必须进 master tuple) / CUT-R9-H1 (D2 separator 须先被 production routing 判 front_blocked) / CUT-R10-L1 (D2 owner gate, LOW) / CUT-R12-H1 (power INFEASIBLE cut 的 occupancy support 扩展) / CUT-R13-H1 (delegated power FEASIBLE 在 ghost context 不可恢复时 ABORT 前移) / CUT-R14-H1 (`_selected_ghost_context()` 原子恢复 + anchor/cells 同源) / **CUT-R15-H1 (本轮攻击面, 修复项本身已 lock —— 「solution 已含 power_pole」即 build 前 fail-closed ABORT, 只审同型残留/反向缺陷/不完备, 不重报修复点本身)**; r2-r15 已修 finding 与已审结论 (重复报不算)。
- 设计决策 (canonical / 266 口径 / `min_side >= 6` admissibility / omni_wireless / 52-Port 不变量, owner 已定)。
- preprocess / binding / campaign / scheduler / routing / master-geometry 各面 (各自有线); 怀疑跨面时**交叉引述 PROJECT_LOCK 契约**而非在本轮重证。
- exploratory / env-gated **行为 / 性能**不审; 整条 `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_B1_BYPASS_*` 都 **env-gated 非 certified** (默认 deny-unknown 阻断, 属 P1.2 soundness 范围之外的 forensic 通道)。但这类 gated cut/witness 通道的 **soundness** (forensic-bypass 暴露面, 即一旦该 env 打开就 false-CERTIFIED 的方向) 仍要审 —— 这正是 CUT-R12/R13/R14/R15 四条的性质。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; F1-F9 `step_2`/`step_8` NotImplementedError (P1.3B 边界, 非缝)。
- persisted `exact_safe_cuts` 是 telemetry 非 proof (V82); certified mode 下 `raw_candidate_cuts=[]` 是代码强制。
- C-3/C-4 latent 待办 (已挂账)。
- env-gated pose-bool / B1-bypass 已 lock 的 hardening 条款 (F-GM-R11/R12/R13-PB-* / F-BL-R8-* / F-BL-R9-* 等), 属各自面的 env-gated 加固, 非本面 cut soundness 线。

## 自验环境与已知基线

- candidate 已随包。全量 `python -m pytest -q src/tests` 应 **0 failed** (collected ≈3148, passed ≈3092, 具体数目以实跑为准; **硬不变量 = 0 failed**); 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`。跑不完就跑专项 (power / cuts / D2 / PCR / binding-lifecycle / persisted-replay) + 如实声明哪些没跑完, **不许把超时谎报成全绿** (前两轮都诚实声明了全量未跑完, 本轮同样标准)。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (8 obligations anchored)。
- finding 必须带**可复现 probe** 或**严谨 file:line 论证**; 实证推翻你的怀疑 (跑出来证明守卫生效 / 几何不可能 match / pole_pool 全 1×1 / 两处 pool 同源 / cells 确实全展开等式成立等) 就**不要报**。
- 引用 file:line 必须**真实** (照你解包后的实际文件核对, 别编行号; 注意本包是带 rounds 1+2 全部修复的新树, `_run_power_placement_subproblem()` 的 pre-existing-pole ABORT 在 `benders_loop.py:4878` 起, `_selected_ghost_context()` 在 `:4768` 起, 注入函数在 `power_placement_subproblem.py:192` 起)。

## 严重度纪律

- **false-CERTIFIED** (cut 误删合法 layout 致最优解丢失 / witness 把非法解 —— 例如 pole 落进 selected empty rectangle / 两 pole 共格 / 漏覆盖某需电设施 —— 认证成可行) = **soundness**。P1.2 闭环只认这个; 这是 HIGH/CRITICAL。**只有 canonical + 默认 env 下的 false-CERTIFIED 才是 soundness reset**; env-gated / conditional 通道一旦打开才暴露的 false-CERTIFIED 是 HIGH 但请**明确标注其 gated 性质** (forensic-bypass-only, 非默认 certified-path reset)。
- **false-INFEASIBLE / 过度 ABORT·UNKNOWN** (保守失败, 不会误认证, 只是少跑出本可证的解) = **availability / hardening**, 标 **LOW**, 并明确标其 gated/conditional 性质。
- 修复方向: soundness 缺口必须 fail-closed (宁可 UNKNOWN 不可 false-CERTIFIED)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 四点逐项判读 (① pre-existing-pole 检测彻底性·判据形态 / ② ABORT 与两路对称性·反向过度 ABORT / ③ 重叠 pole 是否彻底关死·单候选-cell 漏约束 / ④ 注入侧二次校验冗余还是缝) + Q2 注入回写侧纵深结论 (注入 pole vs 最终空矩形 TOCTOU / FEASIBLE-not-OPTIMAL 边界 / TIMEOUT→ABORT 语义 / condition 生命周期·whole-layout 一致性) + Q3 自由攻击结论。
- 前轮 clean/已修不代表本轮默认干净; 本面**连续四轮 delegated power 通道出 HIGH**, 请按你自己的**独立判断**下结论, 真 Pro 确认轮独立背锅。

## 范围边界

- 重点 = CUT-R15-H1 修复确认 + delegated power witness 注入回写侧纵深 + 自由攻击; 其余面 (preprocess/binding/campaign/scheduler/routing/master-geometry) + 各自子问题正确性**不审**, 列入不审范围。
