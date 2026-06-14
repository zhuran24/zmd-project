# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 14 (真 Pro 对抗审查·pose-bool 后端 r13 修复钉死复核)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_0590f9ca.zip`, sha256 `0590f9ca30aac5bb7afe18945eb36d347ea8b0c5b467fd6baff4679eff8c5234`, 对应干净 git 树 HEAD `7fec29a` (rounds 1+2 全部修复已合入, 这是**带修复的新树**)。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`, 沙盒 Python 3.13, 离线安装)。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) 已随包, 已校验。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **几何 master** (`src/models/exact_coordinate_master.py` 为坐标后端核 + certified path 实际后端, `src/models/pose_bool_exact_master.py` 为 env-gated pose-bool 后端, `src/models/master_model.py` 是公共 `MasterPlacementModel` 外壳/legacy 路径 + 委托链 + exact-core proto 打包入口)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = 几何 master 的放置约束编码: footprint no-overlap / ghost 矩形 anchor 枚举 / 电力覆盖 witness / mandatory 装配 / optional·residual 基数不等式 (含 certified optional 下界) / 对称破缺 / solve 解回读 + cut 后 witness 清理。历史:

- r2 = F-GM-Q3-01 (protocol storage 下界只数 residual optional 槽、忽略 fixed required → `0>=1` false-INFEASIBLE);
- r3 = F-GM-Q3-01-R3-A (对偶残缝: `0<fixed<lower` 时 residual 池被砍, shortfall 无 literal 可补);
- r4 = F-GM-Q3-01-R4-A (fixed pole 只占格不承担电杆语义, 不入 family/count/coverage witness);
- r5 = F-GM-Q3-01-R5-A (power family 映射为空时 fixed pole 被 `0==1` 判死);
- r6 = F-GM-R6-01 (cut 成功后只清 `_last_solution`, 旧 `_solver/_status` 仍在 → `extract_solution()` 复活刚被 cut 禁止的解 = stale witness);
- r7 = 零 soundness + LOW hint; r8 = F-GM-R8-SYM-01 (双标尺对称破缺删空可行等价类);
- r9 = 零 + LOW; r10 = 零 + LOW (persisted hint 入口绕过 strict parser);
- **r11 = 真 Pro 首轮重审, 抓出 2 个 HIGH, 都在 env-gated pose-bool 后端** (F-GM-R11-PB-REQ-POLE-01 fixed required pole 被 `continue` 跳过铸 false-FEASIBLE; F-GM-R11-PB-STALE-01 cut 后只清 `_last_solution`)。已修已 lock (`PROJECT_LOCK.md` `F-GM-R11-PB-01`)。
- **r12 = 真 Pro 第二轮, 又抓出 2 个 HIGH, 同样在 env-gated pose-bool 后端** (F-GM-R12-PB-GHOST-01 ghost_anchor_filter=None 时 ghost 完全没编码 → 真 INFEASIBLE 铸 OPTIMAL; F-GM-R12-PB-PROTOCOL-LB-01 optional 块跳过 `_certified_optional_lower_bounds`)。已修已 lock (`PROJECT_LOCK.md` `F-GM-R12-PB-01`)。
- **r13 = 真 Pro 第三轮, 再抓出 1 HIGH + 1 LOW, 仍在 env-gated pose-bool 后端**:
  - **F-GM-R13-PB-NOGHOST-NOOP-01 (HIGH, env-gated-soundness)**: `EXACT_USE_POSE_BOOL_MASTER=1` 且 `ghost_rect is None` 时, pose-bool `build()` 把它误当成 exact-core proto 打包态的 no-op, **零约束** (无 mandatory `AddExactlyOne`、无 no-overlap), 空 CP-SAT 模型直接 `OPTIMAL` —— 不管真实可行性。直连 no-ghost solve 与"打包 proto"是两个不同语义, 旧代码不分。
  - **F-GM-R13-PB-SKIPPOWER-01 (LOW, availability)**: power coverage 块无视 `skip_power_coverage=True`, 对 powered pose 强加 `x_var == 0`/`v == 0` (无 coverer 时), 把一个合法的 geometry-only power-skipped 放置判死 (false-INFEASIBLE, 保守失败)。

**两个 r13 finding 已修复并已 lock** (`PROJECT_LOCK.md` `F-GM-R13-PB-NOGHOST-NOOP-01 / -SKIPPOWER-01` 条款, 延续 `F-GM-R11/R12-PB` 线)。修复落点 (本包 HEAD `7fec29a`):

- **NOGHOST 哨兵分离**: `master_model.py:2550-2554` `build_exact_core()` 在调 `model.build()` 前 `setattr(model, "_pose_bool_exact_core_proto_build", True)`, `finally` 复位 False。`pose_bool_exact_master.py:438-445` 的 no-op 短路条件改为 `ghost_rect is None and _pose_bool_exact_core_proto_build` —— 只有 proto 打包态才 no-op; 直连 no-ghost solve 继续正常建 mandatory / optional / pole / no-overlap (`:457-583`), ghost helper (`:127-129`) 返回 `enabled=False` 但不跳其它约束。
- **SKIPPOWER 尊重**: `pose_bool_exact_master.py:598-628` power coverage 块外层加 `if not bool(getattr(self.owner, "skip_power_coverage", False))` 守卫, 跳过时只写 `build_stats["power_coverage"] = {"skipped": True, "reason": "power_coverage_skipped"}`, 不再对 powered mandatory / powered ro pose 加 `==0`。

**本轮 r14 性质 = 把 r13 两修复钉成攻击面 (不重报已修项本身)。** 真 Pro 确认轮, 独立判断。前轮 thinking r2-r10 连零、真 Pro r11/r12/r13 各抓到 HIGH —— **pose-bool 后端连续三轮真 Pro 都还能挖到新 false-FEASIBLE / stale-witness 缝, 把它当作仍需深审的面**, 钉死 r13 两修复的完备性边界 + 继续找 pose-bool 后端其它 false-FEASIBLE 缝。

注意: 包内带其它面同期落的修复 (cuts / preprocess / benders / binding / routing / power-witness 条款), 各面有自己的线, **别在本轮重报**。

## 审查重点 (按本轮优先级)

### Q1 (主攻) NOGHOST 哨兵修复完备性 — `_pose_bool_exact_core_proto_build` 分支是否真把"打包 no-op"与"直连 no-ghost 实模型"切干净

r13 把 no-op 从"`ghost_rect is None` 就 no-op"收窄到"`ghost_rect is None` **且** proto 打包哨兵 True 才 no-op"。请独立判这套哨兵是否**完整且无新缝**:

- ① **哨兵生命周期 / 复位可靠性**: `build_exact_core()` 用 `try/finally` 在 `:2550-2554` 设/复位 `_pose_bool_exact_core_proto_build`。`build()` 内若抛异常, finally 是否一定复位? 有没有**别的代码路径**也会读这个哨兵 (反查所有 setattr/getattr 点)? 哨兵是 instance 属性 —— 同一 `MasterPlacementModel` 实例若先打包 proto (置 True→finally 复位 False) 后又被复用做直连 solve, 复位是否一定先发生? 反查 `build_exact_core` 是 `@classmethod` 新建实例还是复用 owner 实例 —— 若新建实例, 直连 solve 用的是另一实例, 哨兵默认 False (`getattr(..., False)`), 这条对吗? 有没有路径让哨兵在直连 solve 时残留 True (→ 退回 r13 的空模型 false-FEASIBLE)?
- ② **no-op 触发面是否还残留旁路**: 旧 no-op 在 `:438-445`。除了这条, pose-bool `build()` 里**还有没有别的 early-return / `continue` / 空集短路**, 能在 `ghost_rect is None` (或某种退化输入) 下让 mandatory `AddExactlyOne` / no-overlap **整体不下模**, 复刻 NOGHOST 的"空模型 OPTIMAL"? 重点钉: `_mandatory_groups` 为空 / `facility_pools` 为空 / 全部 group `demand<=0` 被 `:463-464` `continue` 跳过时, 模型是否变成"没有任何 mandatory 约束 + 没有 ghost"的真空模型而误判 OPTIMAL —— 这种真空在 certified 语义下应是什么? (注意区分: 真没有 mandatory 时 OPTIMAL 可能是对的; 但若**有** mandatory 却因某退化被全跳过, 就是 false-FEASIBLE。)
- ③ **直连 no-ghost solve 的语义正确性**: r13 改完后, `ghost_rect is None` 的直连 solve 会建 mandatory/optional/pole/no-overlap 但 ghost helper 返回 `enabled=False` (`:127-129`)。请验证: 一个**真有 mandatory body 互相重叠**的 no-ghost 直连 solve, no-overlap (`AddAtMostOne`, `:580-583`) 是否确实下到模型并产生 INFEASIBLE? r13 的 regression `test_pose_bool_direct_no_ghost_build_still_enforces_body_packing` (`test_master_cut_solution_invalidation.py:354-409`) 覆盖了"两 mandatory 都占 (0,0)"——但**单 mandatory + 单 optional 重叠**、**mandatory + pole 重叠**、**ro + pole 重叠**这些跨类组合在 no-ghost 直连下 no-overlap 是否也覆盖 (cell_poses 是否把跨类 literal 都收进同一 cell 桶)? 找一个 r13 regression 没覆盖、却仍可能漏挡的 no-ghost 跨类重叠组合。
- ④ **proto 打包 no-op 本身是否仍正确**: r13 保留了"proto 打包态确实 no-op"的设计 (`test_pose_bool_exact_core_packaging_no_ghost_remains_intentional_noop`, `:412-424`)。请独立判这条 no-op 在打包态是否**真无害** —— pose-bool 不参与 proto sharing 是 owner 自述, 反查 `build_exact_core()` 产出的 `core_proto = model.model.Proto()` (`:2556`) 在 pose-bool delegate 在场时是否被任何下游消费? 若打包态 pose-bool no-op 后 `model.model` 是空 proto, 而某条 certified path 会拿这个空 proto 当真 master 用, 那才是真问题 (反查 ExactMasterCore 消费者; 若证实空 proto 不入 certified 决策则确认无害)。

### Q2 (主攻) SKIPPOWER 修复完备性 — `skip_power_coverage=True` 守卫是否对称、无反向漏挡

r13 把 power coverage 块整体包进 `if not skip_power_coverage`。请独立判:

- ① **守卫覆盖是否完整**: `:598-628` 守卫只包了 mandatory powered group (`:601-611`) 与 powered ro tpl (`:613-623`) 两块 coverer 约束。pose-bool 里**还有没有别的地方**对 powered pose / pole 施加了与 power coverage 相关的硬约束 (例如 `required_power_pole_demand` 的 `sum(pole_terms) >= demand` 在 `:572-578`, 在守卫块**之外**)? `skip_power_coverage=True` 时, 这些守卫外的 power 相关约束是否**应该**也跳过 —— 还是它们本就与 coverage 正交 (pole demand 是 demand 不是 coverage)? 钉清楚: skip_power_coverage 的语义边界到底是"跳 coverage witness"还是"跳所有 power 语义", 守卫范围与该语义是否精确匹配 (漏包 → 仍误杀 availability; 多包 → 把该保留的 demand 约束也跳了 → false-FEASIBLE, soundness 方向)。
- ② **EXACT_USE_PORT_ACTIVE front_clear 块是否受 skip 影响**: front_clear / cleared-count 块 (`:636+`) 在 power coverage 守卫**之后**, 不受 `skip_power_coverage` 控制。这对吗? skip_power_coverage 与 EXACT_USE_PORT_ACTIVE 是两个正交开关, front_clear 是 routing-visibility 不是 power-coverage —— 但请验证: 有没有配置组合 (`skip_power_coverage=True` + `EXACT_USE_PORT_ACTIVE=1`) 让 front_clear 块假设了 power coverage 已建而其实被跳, 产生不一致约束 (任一方向)?
- ③ **skip 路径下 powered group 是否仍被 mandatory `==demand` 正确约束**: skip_power_coverage=True 时不加 coverer 约束, 但 mandatory `sum(group_vars) == demand` (`:487`) 仍在。验证: skip 下一个 powered mandatory 是否仍**必须被选** (demand 约束保留) 且 ghost/no-overlap 仍生效 —— 即 skip 只松了 power coverage, 没顺手松掉几何强制 (若 skip 把整个 group 建模也跳了就是 false-FEASIBLE)。
- ④ **与坐标/legacy owner 的 skip 口径对齐**: 坐标后端 / legacy `MasterPlacementModel` 在 `skip_power_coverage=True` 时是怎么处理 powered pose 的 (反查坐标后端对应开关)? pose-bool r13 的"整块跳过 coverer 约束"是否与坐标后端**逐项等价** —— 还是坐标后端在 skip 下还保留了某条 power 相关约束 (例如 pole demand 或 family count) 而 pose-bool 现在全跳了 (→ 二者口径分叉, 若 pose-bool 比坐标更松则是潜在 soundness)?

### Q3 (并行) pose-bool 后端其它 false-FEASIBLE / stale-witness 缝 + 几何 master 不变量换角度重审

r11/r12/r13 三轮真 Pro 都在 pose-bool 出 finding, 说明这后端 soundness 表面仍没被穷尽。只在你独立挖到**新角度**时报 (前轮已查点换新角度, 别复读)。框架:

- ① **r12 GHOST 修复在 r13 改动后是否仍完整**: r13 动了 `build()` 的前段 (哨兵分支) 和 power 块, ghost helper 自身 (`:115-215`) 没动 —— 但 `_add_pose_bool_ghost_constraints(cell_poses)` 在 `:585` 调用, 它消费的 `cell_poses` 现在经过 r13 的"直连 no-ghost 也建 mandatory"路径累计。验证: 三类 occupancy literal (x_vars `:485-486` / ro_vars `:543-544` / pole_vars `:569-570`) 在 r13 改动后是否仍**全部在 `:585` 调用前进 cell_poses**? r13 哨兵分支若在某退化下提前 return (`:438-445`), 是否可能 ghost helper 拿到不完整 cell_poses 而漏挡 ghost↔body 重叠 (false-FEASIBLE)? 钉死 r13 改动与 r12 ghost 编码的交界。
- ② **PROTOCOL-LB (r12) 在 r13 power 守卫改动后的复发面**: r12 引入的 powered lower-bound ro pose, 走 `powered_ro_templates` (`:535-537`), 在 r13 守卫块 (`:613-623`) 里加 coverer 约束。r13 给这块加了 `skip_power_coverage` 守卫 —— 验证: `skip_power_coverage=True` 时, 一个**只因 certified lower bound 才建出来**的 powered optional pose (fixed=0, lower>0), 它的基数下界 `sum(ro_vars) >= lower` (`:546`) 仍在, 但 coverage 下界被跳。这是否产生新的不一致: 基数要求选 ≥lower 个 powered storage box, 但 skip 下它们不需要被任何 pole 覆盖 —— 这在 certified 语义下对吗 (skip_power 本就是 geometry-only, 不要 coverage 是预期)? 还是反过来某配置让 lower 约束在 skip 下变得**永远满足不了**或**被误绕过** (任一方向标清)?
- ③ **stale-witness 在 r13 改动后是否复发**: r11/r6 已坐实 cut 后必须清 `_solver/_status/_last_solution` (经 `_invalidate_owner_solver_witness()`, `:93`)。r13 改了 `build()` 但没碰 cut 路径 —— 验证 r13 的哨兵属性 (`_pose_bool_exact_core_proto_build`) 是否会被 cut 后的 re-build / re-solve 误读 (例如某 cut 路径触发 rebuild 时哨兵残留), 或 r13 新增的 `build_stats["power_coverage"]` skip 记录是否被 extract/witness 回读时误用。`apply_solution_hint()` 在 `:1153`、各 cut 方法在 `:942/:1102` 调 `_invalidate_owner_solver_witness()` —— 确认 r13 改动没在 build/solve 之间新开一个绕过 invalidate 的 witness 复活口。
- ④ **footprint no-overlap 忠实度 (换角度)**: pose-bool cell exclusivity 是 `AddAtMostOne(vars_in_cell)` (`:580-583`), 由各 pose `occupied_cells` 填 `cell_poses`。换个角度钉: 非矩形 / 内凹 footprint 的 `occupied_cells` 是否被**完整**填 (没只取 bbox / 漏内凹 cell), 否则 under-approximate 漏挡 (false-FEASIBLE)? `input_port_cells` / `output_port_cells` / `power_coverage_cells` 是否被误当 body occupancy 计入 cell_poses (over-approximate, 只 availability)? 与 r13 NOGHOST 修复后"直连 no-ghost 也靠 no-overlap 保几何"叠加 —— no-ghost 下 footprint 忠实度更关键 (没 ghost 兜底, 全靠 no-overlap)。
- ⑤ **mandatory + powered group + `max_lex` 目标 (换角度)**: x_vars 的 `sum(group_vars) == demand` (`:487`) 是否保证每个 mandatory 装配恰好选 demand 个 pose (不是 `>=`/`<=`)? master 是否只判固定 `(w,h)` 可行性, **无** CP-SAT 加权目标 (反查 `build()` 全程无 `Maximize`/`Minimize`)? r13 新增的哨兵分支 / skip 守卫是否顺手引入隐藏目标项或改了可行集语义 (应纯约束)? `min_side>=6` 是 admissibility 不是 tie-break, frontier 在外层按 tuple 比较?
- ⑥ **hint 永不约束 (回归确认)**: pose-bool `apply_solution_hint()` (`:1153-1410` 区间) 是否只 `AddHint`、经 strict parser skip malformed、无 `Add(...)`/`OnlyEnforceIf(...)` 约束可行域? (r10 已修, 确认 r12/r13 改动没复发。)

## 面边界 (只审本面, 以下明确不审)

- 其余 7 面及各自子问题正确性: **preprocess / cuts / benders·LBBD / binding / routing / campaign / scheduler / power-witness 子问题** 各有独立审查线, 本轮不审。怀疑跨面时, 交叉引述 `PROJECT_LOCK.md` 对应契约 (而非在本轮重证), 在返回里指出可疑点交回主线即可。
- 子问题正确性 (端口绑定 / 网格布线 / 多商品流诊断 / power placement subproblem 的内部 soundness) 不审 —— 本面只到 master 几何编码 + solve 解回读边界。

## 明确不要报的

- **r13 两 finding 本身** (F-GM-R13-PB-NOGHOST-NOOP-01 / F-GM-R13-PB-SKIPPOWER-01) 已修已 lock, 不重报修复本身 —— 只报「修复不完备 / 同型残留 / 反向缺陷 / 顺手引入的新缝」。
- **r11 / r12 各两 finding 本身** (F-GM-R11-PB-REQ-POLE-01 / -STALE-01; F-GM-R12-PB-GHOST-01 / -PROTOCOL-LB-01) 已修已 lock, 同样只报"不完备/残留/新缝"。
- 设计决策: canonical / 266 口径 / omni_wireless / 52-Port (R=S=52) 不变量 / `__unused__` sentinel 语义 / `min_side>=6` admissibility —— owner 已定。
- r2-r10 已修 finding 与已审结论 (重复报不算): F-GM-Q3-01 系列 (r2/r3-A/r4-A/r5-A)、F-GM-R6-01、F-GM-R8-SYM-01、LOW-HINT (r9/r10) 各条款本身。
- preprocess / cuts / benders / binding / routing / campaign / scheduler / power-witness (CUT-R12~R15-H1) 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate, 是 owner 手动 gate 不是 bug); P1.3B `step_8_apply_to_master` 禁区 (`src/cuts/lifecycle.py` 显式 not-yet-integrated 边界); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- **env-gated / 条件路径行为不属 P1.2 certified soundness**: `EXACT_USE_POSE_BOOL_MASTER`、`EXACT_POWER_PLACEMENT_SUBPROBLEM`、`EXACT_B1_BYPASS_*`、`EXACT_USE_PORT_ACTIVE` 等都 env-gated, **不在默认 certified path 上**。但 pose-bool 后端可直接 `EXACT_USE_POSE_BOOL_MASTER=1` 启用, 所以其 false-FEASIBLE / stale-witness 缝**仍是本面 finding** (这是 r11/r12/r13 已确立、lock 已收的口径, 见 `F-GM-R11-PB-01` / `F-GM-R12-PB-01` / `F-GM-R13-PB-*`) —— 只是严重度按下方纪律标"env-gated/conditional"而非 certified soundness reset。
- 不要把「pose-bool 被 `pose_bool_master_not_certified` env guard 挡在公共 certified path 外」本身当 finding —— 这是已知 gate, 是这后端非 certified 的原因, 不是 bug。
- **ghost 不含 exterior-path 要求是 owner 已定禁区 (`PROJECT_LOCK.md` Forbidden), 别建议加**。

## 严重度纪律

- **false-CERTIFIED on canonical + 默认 env = soundness reset (P1.2 闭环只认这个, HIGH)**: 把 certified path (坐标后端 `ExactCoordinateMaster`, 默认 env) 上的真 INFEASIBLE 铸成 FEASIBLE / 放过非法布局 / cut 后复活被禁解 → 这是 P1.2 soundness reset。
- **env-gated / conditional 路径的 false-FEASIBLE / stale-witness** (pose-bool 后端在 `EXACT_USE_POSE_BOOL_MASTER=1` 下的缝): 按 r11/r12/r13 口径**仍记 soundness finding 并修**, 但**明确标 "env-gated, 非 certified-path reset"** —— 是 hardening, 不重置 P1.2 闭环计数。
- **false-INFEASIBLE 保守失败 = availability**: 把合法布局判死 (会漏真最大矩形但不会误认证) → 标 LOW 加固。
- 每条 finding 必须自带 severity 分类标签 (soundness-reset / env-gated-soundness / availability), 不要含糊。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3092, 数目以实跑为准; **硬不变量 = 0 failed**, passed 数随其它面修复浮动)。沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`。跑不完就跑专项 + 如实声明全量未完成 (别 claim 全量通过)。本面相关专项至少包含: `src/tests/test_master_cut_solution_invalidation.py` (含 r11/r12/r13 新增的 ghost + protocol-lb + noghost + skippower regression)、`src/tests/test_master.py`、`src/tests/test_exact_coordinate_protocol_bounds.py`、`src/tests/test_solution_hint_malformed_defense.py`、`src/tests/test_ghost_anchor_filter.py`。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations anchored)。
- **finding 必须带可复现 probe 或严谨 file:line 论证; 实证推翻你的怀疑就不要报。** 攻击 pose-bool 后端时, 起 `EXACT_USE_POSE_BOOL_MASTER=1` 构造最小反例 —— r13 用的 probe 模板可借鉴 (NOGHOST: 1×1 grid + 两 mandatory 都占 (0,0) + 不传 ghost_rect; SKIPPOWER: 2×1 grid + powered machine + 无 pole 候选 + 1×1 固定 ghost + skip_power_coverage=True), 见 `test_master_cut_solution_invalidation.py:354-467` 区间 r13 新增的 3 条 regression 测试 (`test_pose_bool_direct_no_ghost_*` / `test_pose_bool_exact_core_packaging_*` / `test_pose_bool_respects_skip_power_*`), 以及 `:190-353` 的 r11/r12 五条。

## 交付物

- `REVIEW.md` (LF 行尾): 逐条 finding (severity 标签 / file:line / probe 或论证 / 修法, 有把握附 unified diff + regression 测试)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读:
  - **Q1 NOGHOST 哨兵完备性**: 哨兵生命周期/复位可靠性 (try/finally + 实例复用反查, 逐点 file:line) + no-op 触发面是否还有旁路 (退化输入空模型复刻检查) + 直连 no-ghost solve 跨类重叠 no-overlap 覆盖矩阵 + proto 打包 no-op 本身仍正确 (空 proto 消费者反查);
  - **Q2 SKIPPOWER 完备性**: 守卫覆盖范围 vs skip 语义边界精确匹配 (守卫外 power 约束清单) + front_clear 与 skip 正交性 + skip 下 mandatory 几何强制是否保留 + 与坐标/legacy skip 口径对齐缺口;
  - **Q3 其它缝 + 不变量换角度**: r12 ghost 在 r13 改动后完整性 / PROTOCOL-LB 在 skip 守卫下复发面 / stale-witness 在 r13 后复发 / footprint 忠实度 / mandatory+powered+max_lex / hint 永不约束 逐项 (独立判读)。
- 真 Pro 确认轮, 前轮已修不代表本轮默认干净; pose-bool 后端**连续三轮真 Pro 都还在出 finding**, 按你自己最独立、最对抗的判断下结论。

## 范围边界

- 重点 = r13 两修复 (NOGHOST 哨兵分离 / SKIPPOWER 守卫) 的**完备性钉死** + pose-bool 后端其它 false-FEASIBLE / stale-witness 缝挖掘 + 几何 master 不变量换角度重审; 其余面不审。
