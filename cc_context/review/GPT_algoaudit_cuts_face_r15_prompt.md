# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 15 (确认轮·CUT-R14-H1 修复确认 + delegated power witness 注入侧纵深 + 自由攻击)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`, 对应干净 git 树 HEAD `eb5c012` (本轮**全部修复已合入**, 这是带修复的新树, 不是上一轮的树)。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

外置候选工件 `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包并已校验**, 不需要再生; 若校验对不上不准伪造, 停下报告。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制** (master 收紧用的所有 Benders/LBBD nogood / separator cut 通道)。

## 本面定义与历史: 上一轮 (r14) 抓出 CUT-R14-H1, 本轮 = 修复确认轮

本面近况 (报告在包内 `cc_context/review/` 与 `cc_context/review/archive/`): r10 零 + LOW CUT-R10-L1 (D2 owner gate); r11 零 (终饱和轮); r12 抓 1 HIGH CUT-R12-H1 (power INFEASIBLE cut 丢 unpowered fixed-occupancy support, 已修); r13 抓 1 HIGH CUT-R13-H1 (delegated power FEASIBLE witness 在 selected ghost context 不可恢复时仍求解 de-ghosted 子问题, 已修); **r14 抓 1 HIGH CUT-R14-H1**, 已修在本包内:

- **CUT-R14-H1 (delegated power 的 ghost provenance 在 anchor 与 cells 之间可错配)**: r13 修复把 FEASIBLE 路径的 ABORT 前移到 build 前, 但当时 `_selected_ghost_anchor()` 与 `_selected_ghost_cells()` **仍是两个独立扫描器**, 各自扫 `u_vars` 找 `Value==1`。若 master/solver 状态出现多个 `u_var` 读作 selected, 或第一个 selected ghost domain 的 `cells` 解析失败 (`try/except: continue`) 而后续 selected domain 可解析, FEASIBLE 路径可能拿 **rect A 的 anchor / condition literal** 却用 **rect B 的 ghost_cells** 当障碍 build delegated power subproblem → 子问题在错误障碍下求解, 可能注入一个实际落在 **selected empty rectangle (rect A) 内**的 synthetic power pole witness (= false-CERTIFIED 方向)。canonical `ExactCoordinateMaster` 的 `AddExactlyOne` + 同 loop 写 anchor/cells 使其在默认 env 下不可达, 暴露面 = forensic bypass / master 内部状态损坏 / 未来 backend 变体; **gated/exploratory** (`EXACT_POWER_PLACEMENT_SUBPROBLEM`, deny-unknown), 但属 HIGH。

  **修在本包内** (`src/search/benders_loop.py:4737-4833`): 新增 `_selected_ghost_context()`, 把 `(rect_idx, u_var, anchor, cells)` 作为单一 proof context **原子恢复** —— 一次读 `u_vars`/`_ghost_domains`/`_solver`; 要求 selected `u_var` **严格等于 1** (`:4762`, 否则 None); 异常不再 `continue` 而统一返回 None fail-closed (`:4760-4761`); 要求 `rect_idx` 在 domain 范围内 (`:4766`)、anchor 显式 `x/y` 可转 int (`:4775-4783`, 不再有 `(0,0)` 默认)、cells 完整可解析且非空 (`:4785-4791`); 若 master 暴露 `ghost_rect` 则要求 cells **精确等于** `anchor + ghost_rect` 展开的矩形全集 (`:4793-4808`), 无 `ghost_rect` 时至少要求 cells 最小坐标与 anchor 对齐 (`:4809-4816`)。两个旧 helper 退化为同源 wrapper (`:4820-4833`); `_run_power_placement_subproblem()` 只调用一次 `_selected_ghost_context()`, FEASIBLE 与 INFEASIBLE 两路复用同一 `(rect_idx, u_var, anchor, ghost_cells)` (`:4847-4860`, `:4913-4937`)。回归 = `src/tests/test_power_witness_cut_dilution.py` 新增两条 (anchor/cells 错配必须 ABORT; anchor 缺 x/y 不得退化成 `ghost_anchor::(0,0)`)。LOCK 登记见 `PROJECT_LOCK.md` 第 3 节 CUT-R14-H1 条款。

**本轮 r15 = CUT-R14-H1 修复确认 + delegated power witness 注入侧纵深 + 自由攻击角。**
**注意**: 本面已**连续三轮** (r12 power INFEASIBLE / r13 power FEASIBLE de-ghost / r14 power FEASIBLE anchor-cells 错配) 在 **delegated power witness 通道** 各抓出一条此前轮次漏掉的 HIGH, **故本轮绝不能默认干净**, 请用最独立的判断。**不重报 CUT-R14-H1 修复项本身** —— 它已 lock。本轮把这个修复**钉成攻击面**: 找同型残留、反向缺陷、修复不完备 (见 Q1), 并把火力延伸到**这条 ghost 上下文坐实之后, witness 真正被注入回 certified solution 的那一段** (见 Q2)。

注: 本包 (HEAD `eb5c012`) 含其它面同期工件 (master r12 / benders r8 等 env-gated hardening 确认轮、handoff stamp、八面外审台账等), 各面有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 CUT-R14-H1 修复确认 (攻击面, 本轮主体)

① **原子恢复是否真原子 / 唯一 selected 闸的彻底性**: 修复声称 `_selected_ghost_context()` 单次读 solver 视图、要求 `len(selected) == 1`。独立确认: (a) `u_vars` 迭代中任一 `solver.Value(var)` 抛异常即 `return None` (`:4760-4761`) —— 这个"任一异常全部 fail-closed"是否覆盖了 r14 之前 `_selected_ghost_cells()` 的 `continue` 漏洞的**全部**形态, 还是仍有某条路径 (例如 `int(raw_rect_idx)` 成功但 `solver.Value` 部分成功) 让 selected 列表只装到一半就判 `== 1`? (b) `len(selected) != 1` 的两端: 0 个 selected (无 ghost 被选) 与 ≥2 个 selected 都 ABORT —— 0 个 selected 在 canonical `AddExactlyOne` 下不可达, 但**确实存在 ghost rect 却恰好 0 选**的退化是否会误伤 (availability) 还是本就该 ABORT (soundness 优先)? 区分清楚。

② **几何自洽校验的强度与旁路**: 修复在有 `ghost_rect` 时要求 `cells == expected_cells` (anchor + w×h 全展开), 无 `ghost_rect` 时只要求 `min(cells) == anchor`。独立确认: (a) `cells == expected_cells` 这条强等式是否可能在**合法** canonical 场景误伤 —— 例如 `ghost_rect` 存的是 `(w,h)` 还是 `(h,w)`? domain `cells` 是否一定是完整实心矩形 (会不会 canonical 某些 ghost domain 只存边界 cells 或稀疏 cells 而非全展开)? 若是后者则合法场景被 ABORT (availability); 若 cells 一定全展开则 OK。**请用包内 `exact_coordinate_master.py` 的 domain 生成实际确认 cells 是不是 anchor 起的实心矩形全集**, 别凭猜。(b) 无 `ghost_rect` 分支只校验 `min(cells)` 对齐 anchor —— 一个 anchor 在左下角、但 cells 实际是**另一个**同样左下对齐的矩形 (面积不同) 时, 这条弱校验能否区分? 这种 master 变体 (有 ghost 但不暴露 `ghost_rect`) 是否真实存在 / 是否就是 soundness 缝?

③ **anchor 显式 x/y 与 INFEASIBLE condition key 的一致性**: 修复后 anchor 由 `_selected_ghost_context()` 保证显式 `x/y` (不再 `(0,0)` 默认), INFEASIBLE 路径仍用 `anchor.get("x", 0)` / `anchor.get("y", 0)` 写 `ghost_anchor::({x},{y})` (`:4913-4915`) 与 `condition_lits=(u_var,)` (`:4937`)。独立确认: (a) 既然 anchor 已坐实, 这里的 `.get(..., 0)` 默认值是否成了 dead code (永远命中真值) 还是仍有路径让它退化? (b) condition key 的字符串 `ghost_anchor::(x,y)` 与 condition_lits 的 `u_var` 在 replay 时由 `_resolve_condition_lits_from_condition_set()` (`:1493` 起) 重新解析 —— replay 解析出的 rect_idx / anchor 是否与产 cut 时**同一** `(rect_idx, anchor)`? key 里只有 (x,y) 没有 rect_idx, value 才是 rect_idx; 若两个不同 rect_idx 的 ghost 恰好同 anchor 坐标 (canonical 不可达但 forensic/外部 condition_set 可构造), replay 会不会把 cut 挂到错误 ghost literal 上?

④ **修复是否引入新的 false-INFEASIBLE / 过度 ABORT (availability 反向缺陷)**: 把恢复收紧成"唯一 selected + 几何精确等式", 是否在**合法** canonical 场景下误 ABORT? 重点查 ④② 的 `cells == expected_cells`: 若 canonical domain cells 与 `anchor+ghost_rect` 展开**不是逐 cell 相等** (顺序/类型/去重差异已被 set 化吸收, 但**内容**差异不会), 则每次 delegated power FEASIBLE 都 ABORT → 退 UNKNOWN, 整条 `EXACT_POWER_PLACEMENT_SUBPROBLEM` forensic 通道失效。这是**保守失败 (availability, LOW)** 还是会掩盖真问题? 区分: false-CERTIFIED = soundness (HIGH/CRITICAL); 过度 ABORT/UNKNOWN = availability (LOW 加固)。

⑤ **三通道一致性复核 (本轮把"坐实 ghost 上下文"的义务向 witness 注入侧延伸)**: CUT-R8-H1 / CUT-R12-H1 / CUT-R13-H1 / CUT-R14-H1 是同一条"separator/witness 用了哪些 constant occupancy / ghost support, cut/witness 就必须带上同一 proof context"义务的逐轮收口。独立确认: CUT-R14-H1 把 ghost provenance 坐实到了 **build 子问题之前**, 但 ghost_cells 被坐实**之后**, 子问题求解出 `selected_pose_indices`, 再经 `inject_power_poles_into_solution()` 注入回 certified solution —— 这一段是否仍有"坐实的 ghost 上下文与最终落进 solution 的 pole"之间的断点 (见 Q2)? 这条义务有没有遗漏的对称面 (routing/flow 诊断阶段是否也消费 selected ghost 而无同等前置守卫; 注: 包内 `_run_flow_diagnostic()` 跳过 `ghost_pick`, 请独立复核它确实不消费 selected ghost cells 产 witness/cut)?

### Q2 delegated power witness 注入侧纵深 (本轮深挖, 火力前移到"坐实之后")

CUT-R14-H1 把审查推进到了"ghost 上下文坐实之前"的彻底性。本轮**主深挖方向 = 坐实之后到 witness 落进 certified solution 的那一段**, 因为前几轮的修复都集中在 separator/subproblem 入口, 而 `inject_power_poles_into_solution()` 这条出口此前未被独立钉过:

- **注入侧无二次几何校验 (本轮重点猜想)**: `inject_power_poles_into_solution()` (`power_placement_subproblem.py:192-215`) **无条件信任** 子问题给的 `selected_pose_indices`, 直接按 pose 注入 synthetic pole, **没有**对注入 pose 的 `occupied_cells` 与 ghost_cells / fixed master occupancy 做二次 disjoint 断言。上一轮 (r14) REVIEW 自己在 §2③ 也点了这一处"防御纵深可加 LOW"但未报。独立判断: 这是否值得升格 —— 在 ghost 上下文已坐实、子问题 `build()` 已按 pose 全占格过滤 fixed 的前提下, 注入侧少这道二次校验**是真冗余 (子问题已保证, 注入再校验只是 belt-and-suspenders, LOW)** 还是**有缝 (存在子问题过滤与注入实际写入不一致的路径, 例如 selected pose 来自非预期 solver 状态 / pose pool 在两处不同源 / TIMEOUT-but-FEASIBLE 边界)**? 注意 `solve()` 只在 `OPTIMAL/FEASIBLE` 返回 selected (`:164-177`), TIMEOUT 不带 selected; controller 只在 `result.status == "FEASIBLE"` 注入 —— 请独立确认 CP-SAT `FEASIBLE` (非 OPTIMAL, 即 time-limit 内找到可行但未证最优) 这条边: 此处把它当 FEASIBLE 注入是否 sound (power placement 只要可行即可, 无需最优), 还是 FEASIBLE-but-not-OPTIMAL 的 selected 集可能不满足某条约束?

- **coverage table 同源等价性**: 子问题 coverage 用 master 预计算的 `_power_coverers_by_template_pose` (`power_placement_subproblem.py:135-151`), master 侧 in-master coverage 读同一 table (`master_model.py:4739/:4752/:7503`, `exact_coordinate_master.py:5167`, `pose_bool_exact_master.py:591`)。独立确认 table 构建 (`master_model.py:4006-4008` 附近, `power_index` 写入) 与 subproblem 读取是否真同源等价: 是否存在 powered instance 在 master 被认为"可覆盖"但子问题 `full_coverers` 里查不到 coverer (`get(tpl,{}).get(pose_idx,[])` 取空) → 子问题误判该 instance uncovered → INFEASIBLE 误判 (availability), 或反之 master 漏算某 powered instance 而子问题 `_powered_instances()` 也不约束它 → witness 不覆盖它却仍 FEASIBLE (soundness)? `_powered_instances()` 用 `tpl in self._powered_templates` 过滤 (`:99-108`), `_powered_templates` 来自 master `needs_power` 推导 —— 子问题收到的 `powered_templates` 与 master coverage 约束用的是否同一集合?

- **fixed-occupancy 过滤与 coverer table 的交叉一致性**: 子问题 `build()` 先按 `occupied & fixed: continue` 过滤候选 pole (`:116-126`), 再用 `available = [p for p in full_coverers if p in candidate_set]` 取交 (`:142`)。独立确认: master 预计算 coverer table 时是否已知 fixed occupancy, 还是 table 是 fixed-agnostic 的全局 coverer? 若 table 是全局的, 子问题再用 fixed 过滤掉部分 coverer 后取交, `available` 可能为空 → 该 instance 误判 uncovered → INFEASIBLE。这条 INFEASIBLE 在 ghost-conditioned cut 下是否仍 sound (即"在这个 fixed occupancy + 这个 ghost anchor 下, 唯一可覆盖该 instance 的 pole 都被挡住"是否真的成立, 还是 fixed 过滤本身漏算了某些其实可用的 pose)?

- **whole-layout power-witness fail-closed 交互 (修复后复核)**: `_add_exact_whole_layout_nogood()` 在 flag on 且 solution 含 synthetic/任意 `power_pole` 时 fail-closed skip cut (`benders_loop.py:6626-6631` 附近), binding/routing caller 在 cut 未应用时返回 UNKNOWN (`:5226-5238`, `:6165-6177` 附近)。修复后 FEASIBLE 注入 pole 后若后续阶段触发 whole-layout nogood, 是否仍正确 skip (synthetic pole 无 master presence literal, 不能被 whole-layout cut 安全引用)? 注入的 synthetic_id 形如 `pose_optional::power_pole::{pose_id}` (`:203`) —— `has_synthetic_pole` 的检测 (`:6626`) 是否真能命中这个 id 形态?

### Q3 自由攻击角

以上之外, 用你自己的独立判断选你认为本面最薄弱的点深挖。鉴于 delegated power 通道已**连出三 HIGH**, 你可以选择:
- 换出 power 通道, 攻其它 cut 通道 (D2 commodity-flow separator / PCR-CUT patch separator / binding nogood / master-placement·whole-layout nogood / cut replay·persist lifecycle / lazy-demand·cell-pattern 饱和), 找一个 proof-context 投影 / literal identity / condition 生命周期最易藏错的点;
- 或继续 power 通道挖第四层 (例如 INFEASIBLE cut 的 `conflict_set` 收集 `:4901-4911` 把 `pose_idx` parse 失败 ABORT 是否覆盖全部异常形态; condition_set 只有一条 ghost literal 是否足以让 cut 严格 ghost-conditioned)。

说明选点理由、攻击过程、结论。前两类自由攻击点 (persisted `exact_safe_cuts` telemetry-only / condition-lits replay) r14 已扫过零 finding, 若你重走请说明你看到了 r14 没看到的角度, 否则换点。

## 明确不要报的

- **已 lock 的本面已修条款 (列出, 重复报不算)**: CUT-R8-H1 (compiled constant support 必须进 master tuple) / CUT-R9-H1 (D2 separator 须先被 production routing 判 front_blocked) / CUT-R10-L1 (D2 owner gate, LOW) / CUT-R12-H1 (power INFEASIBLE cut 的 occupancy support 扩展) / CUT-R13-H1 (delegated power FEASIBLE 在 ghost context 不可恢复时 ABORT 前移) / **CUT-R14-H1 (本轮攻击面, 修复项本身已 lock —— `_selected_ghost_context()` 原子恢复 + anchor/cells 同源, 只审同型残留/反向缺陷/不完备, 不重报修复点本身)**; r2-r14 已修 finding 与已审结论 (重复报不算)。
- 设计决策 (canonical / 266 口径 / `min_side >= 6` admissibility / omni_wireless / 52-Port 不变量, owner 已定)。
- preprocess / binding / campaign / scheduler / routing / master-geometry 各面 (各自有线); 怀疑跨面时**交叉引述 PROJECT_LOCK 契约**而非在本轮重证。
- exploratory / env-gated **行为 / 性能**不审; 整条 `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_USE_POSE_BOOL_MASTER` / `EXACT_B1_BYPASS_*` 都 **env-gated 非 certified** (默认 deny-unknown 阻断)。但这类 gated cut/witness 通道的 **soundness** (forensic-bypass 暴露面, 即一旦该 env 打开就 false-CERTIFIED 的方向) 仍要审 —— 这正是 CUT-R12/R13/R14 三条的性质。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; F1-F9 `step_2`/`step_8` NotImplementedError (P1.3B 边界, 非缝)。
- persisted `exact_safe_cuts` 是 telemetry 非 proof (V82); certified mode 下 `raw_candidate_cuts=[]` 是代码强制。
- C-3/C-4 latent 待办 (已挂账)。
- env-gated pose-bool / B1-bypass 已 lock 的 hardening 条款 (F-GM-R11-PB-01 / F-GM-R12-PB-01 / F-BL-R8-01/02/03 等), 属各自面的 env-gated 加固, 非本面 cut soundness 线。

## 自验环境与已知基线

- candidate 已随包。全量 `python -m pytest -q src/tests` 应 **0 failed** (collected 3148, passed ≈3074, 具体数目以实跑为准; 硬不变量 = **0 failed**); 沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`。跑不完就跑专项 (power / cuts / D2 / PCR / binding-lifecycle / persisted-replay) + 如实声明哪些没跑完, **不许把超时谎报成全绿** (上一轮诚实声明了全量未跑完, 本轮同样标准)。
- `python scripts/check_p1_2_proof_obligations.py` 应 pass (8 obligations anchored)。
- finding 必须带**可复现 probe** 或**严谨 file:line 论证**; 实证推翻你的怀疑 (跑出来证明守卫生效 / 几何不可能 match / cells 确实全展开等式成立) 就**不要报**。
- 引用 file:line 必须**真实** (照你解包后的实际文件核对, 别编行号; 注意本包是带 r14 修复的新树, `_selected_ghost_context()` 在 `benders_loop.py:4737` 起)。

## 严重度纪律

- **false-CERTIFIED** (cut 误删合法 layout 致最优解丢失 / witness 把非法解 —— 例如 pole 落进 selected empty rectangle / 漏覆盖某需电设施 —— 认证成可行) = **soundness**。P1.2 闭环只认这个; 这是 HIGH/CRITICAL。**只有 canonical + 默认 env 下的 false-CERTIFIED 才是 soundness reset**; env-gated / conditional 通道一旦打开才暴露的 false-CERTIFIED 是 HIGH 但请**明确标注其 gated 性质** (forensic-bypass-only)。
- **false-INFEASIBLE / 过度 ABORT·UNKNOWN** (保守失败, 不会误认证, 只是少跑出本可证的解) = **availability / hardening**, 标 **LOW**, 并明确标其 gated/conditional 性质。
- 修复方向: soundness 缺口必须 fail-closed (宁可 UNKNOWN 不可 false-CERTIFIED)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 五点逐项判读 (① 原子恢复/唯一 selected 闸 / ② 几何自洽校验强度·旁路 / ③ anchor·condition key 一致性 / ④ 反向过度 ABORT / ⑤ 三通道一致延伸) + Q2 注入侧纵深结论 (注入侧二次校验是冗余还是缝 / coverage table 同源 / fixed 过滤交叉一致 / whole-layout 交互) + Q3 自由攻击结论。
- 前轮 clean/已修不代表本轮默认干净; 本面**连续三轮 delegated power 通道出 HIGH**, 请按你自己的**独立判断**下结论, 真 Pro 确认轮独立背锅。

## 范围边界

- 重点 = CUT-R14-H1 修复确认 + delegated power witness 注入侧纵深 + 自由攻击; 其余面 (preprocess/binding/campaign/scheduler/routing/master-geometry) + 各自子问题正确性**不审**, 列入不审范围。
