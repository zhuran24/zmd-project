# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 13 (真 Pro 对抗审查·pose-bool 后端 r12 修复钉死复核)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_3b23181e.zip`, sha256 `3b23181e036be5daaf15d9166b76bb9d7b6acb49d81da3e046b8a07f1ec326b6`, 对应干净 git 树 HEAD `eb5c012` (本轮全部修复已合入, 这是**带修复的新树**)。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`, 沙盒 Python 3.13, 离线安装)。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) 已随包, 已校验。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **几何 master** (`src/models/exact_coordinate_master.py` 为坐标后端核 + certified path 实际后端, `src/models/pose_bool_exact_master.py` 为 env-gated pose-bool 后端, `src/models/master_model.py` 是公共 `MasterPlacementModel` 外壳/legacy 路径 + 委托链)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = 几何 master 的放置约束编码: footprint no-overlap / ghost 矩形 anchor 枚举 / 电力覆盖 witness / mandatory 装配 / optional·residual 基数不等式 (含 certified optional 下界) / 对称破缺 / solve 解回读 + cut 后 witness 清理。历史:

- r2 = F-GM-Q3-01 (protocol storage 下界只数 residual optional 槽、忽略 fixed required → `0>=1` false-INFEASIBLE);
- r3 = F-GM-Q3-01-R3-A (对偶残缝: `0<fixed<lower` 时 residual 池被砍, shortfall 无 literal 可补);
- r4 = F-GM-Q3-01-R4-A (fixed pole 只占格不承担电杆语义, 不入 family/count/coverage witness);
- r5 = F-GM-Q3-01-R5-A (power family 映射为空时 fixed pole 被 `0==1` 判死);
- r6 = F-GM-R6-01 (cut 成功后只清 `_last_solution`, 旧 `_solver/_status` 仍在 → `extract_solution()` 复活刚被 cut 禁止的解 = stale witness);
- r7 = 零 soundness + LOW hint; r8 = F-GM-R8-SYM-01 (双标尺对称破缺删空可行等价类);
- r9 = 零 + LOW; r10 = 零 + LOW (persisted hint 入口绕过 strict parser);
- **r11 = 真 Pro 首轮重审, 抓出 2 个 HIGH, 都在 env-gated pose-bool 后端** (F-GM-R11-PB-REQ-POLE-01 fixed required pole 被 `continue` 跳过铸 false-FEASIBLE; F-GM-R11-PB-STALE-01 cut 后只清 `_last_solution`)。两条已修已 lock (`PROJECT_LOCK.md` §3 `F-GM-R11-PB-01`)。
- **r12 = 真 Pro 第二轮, 又抓出 2 个 HIGH, 同样在 env-gated pose-bool 后端**:
  - **F-GM-R12-PB-GHOST-01 (HIGH, false-FEASIBLE)**: 当 `ghost_rect=(w,h)` 但 `ghost_anchor_filter is None` 时, 原 pose-bool build 完全没编码 ghost — 没有 anchor `u_vars`、没有 `AddExactlyOne`、没有 body-overlap 约束, 只靠 `_forbidden_cells()` 预过滤 (无 filter 时返回空集), 于是"存在一个空矩形"这个要求根本没下到模型, 真 INFEASIBLE (1×1 grid + required pole + 1×1 ghost) 铸成 OPTIMAL。
  - **F-GM-R12-PB-PROTOCOL-LB-01 (HIGH, false-FEASIBLE)**: 原 pose-bool optional 块只读 `_exact_required_pose_optional_counts`, 跳过 `_certified_optional_lower_bounds` (例如 generic-input 推导出的 `protocol_storage_box` 下界)。规则要求 ≥1 个 protocol storage box 但候选池为空时, 原 pose-bool 返回 OPTIMAL, certified-correct 是 INFEASIBLE。

**两个 r12 finding 已修复并已 lock** (`PROJECT_LOCK.md` §3 `F-GM-R12-PB-01` 条款, 延续 `F-GM-R11-PB-01` / `F-GM-Q3-01` 线)。修复落点 (本包 HEAD `eb5c012`):

- `pose_bool_exact_master.py:115-215` 新增 `_add_pose_bool_ghost_constraints()`: 用 `range(grid_w-ghost_w+1)`/`range(grid_h-ghost_h+1)` 完整枚举 anchor (有 filter 只保留 filter 内 anchor、为空/尺寸非法则 `0>=1` fail-closed), 每 anchor 建 `u` BoolVar 写入 `owner.u_vars`/`owner._ghost_domains`, 加 `AddExactlyOne(u_vars)` (`:197`), 对每个 ghost body cell 加 `sum(facility_occ_at_cell) + sum(ghost_u_covering_cell) <= 1` (`:199-204`, 只对 `cell_poses` 非空的 cell 下约束)。`build()` 把预过滤改 `forbidden=set()` (`:441` 附近), ghost↔body 关系从"预删候选"改"显式 exactly-one + overlap"。
- `pose_bool_exact_master.py:506-547` optional 块同时读 fixed demand (`_exact_required_pose_optional_counts`) 与 certified lower bound (`_certified_optional_lower_bounds`, 排除 `power_pole`, `:507-513`), 对二者模板并集建 ro pose vars; `lower>fixed` 时加 `sum(ro_vars) >= max(fixed,lower)` (`:540-541`), 否则保留 `sum == fixed_demand` (`:546`); 候选不足 `min_selected` 时 `0>=min_selected` fail-closed (`:527-529`)。

**本轮 r13 性质 = 把 r12 两修复钉成攻击面 (不重报已修项本身)。** 真 Pro 确认轮, 独立判断。前轮 thinking r2-r10 连零、真 Pro r11/r12 各抓 2 HIGH —— **pose-bool 后端连续两轮真 Pro 都还能挖到新 false-FEASIBLE 缝, 把它当作仍需深审的面**, 钉死 r12 两修复的完备性边界 + 继续找 pose-bool 后端其它 false-FEASIBLE 缝。

注意: 包内带其它面同期落的修复 (cuts / preprocess / benders / binding / routing 条款), 各面有自己的线, **别在本轮重报**。

## 审查重点 (按本轮优先级)

### Q1 (主攻) GHOST 修复完备性 — pose-bool ghost anchor 编码是否真正等价坐标/legacy 口径

r12 把 ghost 从"预过滤"换成"显式 anchor exactly-one + body overlap"。请独立判这套新编码是否**完整且无新缝**:

- ① **overlap 覆盖完整性**: `:199-204` 的 ghost body cell overlap 只对 `cell_poses.get(cell)` **非空**的 cell 下约束 (空 cell 自然可放 ghost, 这是对的)。但 `cell_poses` 在 ghost helper 被调用前 (`:580`) 是否已经累计了**所有**会占格的 literal —— x_vars (mandatory)、ro_vars (含 lower-bound 新引入的 optional)、pole_vars (`:551-566`)? 有没有哪类设施 pose 的 occupancy literal **没进 `cell_poses`** 就被 ghost helper 漏算, 导致 ghost 能跟某个真实占格设施重叠 (false-FEASIBLE)? 特别钉: pole_vars 在 `:564-565` 进 `cell_poses`, ro_vars 在 `:538-539` 进, x_vars 在哪进 (反查) —— 三类是否都在 `:580` 调用点之前完成累计?
- ② **anchor 枚举边界精确**: `range(grid_w-ghost_w+1)`/`range(grid_h-ghost_h+1)` (`:158-159`) 是否无裁剪、无 off-by-one (放得下的 anchor 一个不漏, 越界 anchor 一个不进)? `ghost_w>grid_w` / `ghost_h>grid_h` 走 `:148-153` fail-closed —— 边界 `==` 情况 (ghost 恰好满格) 是否正确产生唯一 anchor 而非误判?
- ③ **filter 语义**: `ghost_anchor_filter is not None` 时只保留 filter 内 anchor (`:161-163`), filter 与所有 anchor 交集为空时 `:183-195` fail-closed `0>=1`。这条 fail-closed 是否**精确** (该不可行才不可行)? multi-anchor filter 下, 某 anchor 合法但其 ghost cell 恰好压住另一 anchor 才会冲突的 pose, 会不会被误删/误留? (r12 自称把 union 预过滤的过保守缝一并修了, 请独立验证, 不要默认它对。)
- ④ **`build()` 改 `forbidden=set()` 的连带影响**: 预过滤从 build 移除后, 原来依赖 `forbidden` 的下游 (feasible pose 筛选 `_feasible_poses`、pole pool `:560` 的 `c in forbidden` 判断、SAC static ghost moat) 是否仍正确? 尤其 `:560` `if any(c in forbidden ...)` 现在 `forbidden` 恒空 —— pole pose 不再被任何预过滤排除, 全靠 ghost overlap 动态约束。这是否引入新缝 (例如某条下游仍假设 `forbidden` 非空才正确)?
- ⑤ **与坐标/legacy 口径对齐**: 坐标后端 `exact_coordinate_master.py:3662-3732` (anchor exactly-one + body no-overlap)、legacy `master_model.py:4618-4675` (anchor 枚举 + body overlap) 是 r4/r6 已坐实的正确口径。pose-bool 新 helper 是否**逐项对齐** (body-only 不含 connector/belt/coverage/exterior-path; exactly-one 而非 at-most-one; overlap 方向正确)? 还是只补了形、漏了某半边?

### Q2 (主攻) PROTOCOL-LB 修复完备性 — certified optional 下界编码是否无漏、无 over/under-constrain

r12 把 optional 块改成同时读 fixed demand + certified lower bound。请独立判:

- ① **覆盖所有下界模板**: `:507-513` 从 `_certified_optional_lower_bounds` 收集, 但**显式排除了 `power_pole`** (`:512` `str(tpl) != "power_pole"`)。这是否正确? `power_pole` 的下界由 `required_power_pole_demand` 路径 (`:567-573`) 单独处理, 二者会不会出现**某个 template 两条路径都不管 / 都管** (漏或双重)? 反查 `_certified_optional_lower_bounds` 实际可能含哪些 key, 确认 `power_pole` 之外的每个 key 都被 `:506-547` 块覆盖。
- ② **`max(fixed,lower)` 编码相容**: `lower>fixed` 时 `sum(ro_vars) >= max(fixed,lower)` (`:540-541`); `lower<=fixed` 时 `sum == fixed_demand` (`:546`)。两分支拼接处 (`lower==fixed`) 是否正确? `>=` vs `==` 的选择会不会在某配置 over-constrain (合法配置判死, false-INFEASIBLE→availability) 或 under-constrain (该满足的下界没下到, false-FEASIBLE→soundness)? 重点钉 soundness 方向: 有没有 path 让 `sum` 既不 `==` 也不 `>=` 下界 (例如 `min_selected<=0` 在 `:522` 直接 `continue` 跳过 —— 这是否可能在 lower>0 但被某种类型转换/读取错误吞成 0 时漏掉下界)?
- ③ **powered 下界模板进 coverage 通道**: lower-bound 新引入的 ro_vars, 若该模板是 powered (`:530-532` `is_powered`), 会进 `powered_ro_templates`, 在 `:605-615` 加 `v <= sum(cov_vars)` 或 `v == 0`。请验证: 一个**只因 certified lower bound 才被建出来**的 powered optional pose (fixed_demand=0, lower>0), 它的 coverage 下界 (`:605-615`) 与基数下界 (`:540-541`) 是否相容 —— 会不会出现"基数要求选 ≥lower 个, 但每个都因无 coverer 被 `v==0` 钉死"造成 `0>=lower` 式 false-INFEASIBLE (availability), 或反向漏挡 (soundness)? 这是 r4/r5 family-mapping-empty 缝在 lower-bound 路径的潜在复发点, 重点钉。
- ④ **slot placeholder 误消费**: `:542-544`/`:547` 填 `residual_optional_slots[tpl]` / `required_optional_slots[tpl]` (后者标注 `# placeholder`)。这些 placeholder 是否被下游 (统计 / 对称破缺 slot 枚举 / cut 的 slot 域 / extract_solution slot 回读) **误当真 slot 域消费**, 造成多收非法 tuple (false-FEASIBLE) 或删空等价类 (false-INFEASIBLE)? 与 r11 的 `required_optional_slots["power_pole"]` placeholder 同型, 一并钉。
- ⑤ **与坐标后端对齐**: 坐标后端 `exact_coordinate_master.py:6180-6214` 加 `protocol_storage_box` 下界 (residual terms 空则 `0>=shortfall` fail-closed)。pose-bool 无 slot identity, 直接在 concrete pose literal 上表达。语义是否真等价 (fixed 进、residual 补 shortfall、不双花 capacity)? 还是漏了坐标后端"fixed count 从 upper bound 扣除防双花"那半边?

### Q3 (并行) pose-bool 后端其它 false-FEASIBLE 缝 + 几何 master 不变量换角度重审

r11/r12 各抓 2 HIGH 都在 pose-bool, 说明这后端的 soundness 表面还没被穷尽。只在你独立挖到**新角度**时报 (前轮已查点换新角度, 别复读)。框架:

- ① **ghost u_var 与 `EXACT_USE_PORT_ACTIVE` front_clear 块的交互** (`:617+`): ghost u_var 写进了 `owner.u_vars` 和 `rect_terms_by_cell`, 但**没**进 `cell_poses` (只有 facility occupancy 进 `cell_poses`)。front_clear 块 (`:633-665`) 用 `_poses_by_cell_global` / `cell_poses` 判 front 是否空。ghost 占的 cell 算不算"空"? 按 owner body-only 口径 ghost 是空矩形所以 front 在 ghost cell 上**应该**算 clear —— 但 ghost cell 同时被 `AddExactlyOne` 选中时, 一个 port front 落在被选 ghost 矩形内、被判 clear、binding 据此激活该 port, 是否产生几何矛盾 (port 在"空"矩形里, 但 belt/connector 又得占格)? 这是 env-gated 叠 env-gated (`EXACT_USE_PORT_ACTIVE`), 若构造出 false-FEASIBLE 标 HIGH-conditional, 若只是 false-INFEASIBLE/over-cut 标 LOW。
- ② **footprint no-overlap 忠实度**: pose-bool 的 cell exclusivity 是 `AddAtMostOne(vars_in_cell)` (`:575-578`), 由各 pose `occupied_cells` 填 `cell_poses`。这是 body occupancy 的 exact set-packing, 不是 bbox。但请验证: 非矩形 footprint 的 `occupied_cells` 是否被**完整**填入 (没有只取 bbox 角点 / 漏掉内凹 cell), 否则 under-approximate 漏挡 (false-FEASIBLE)? port_cells / power_coverage_cells 是否被误当 occupancy 计入 (over-approximate, 这方向只 availability)?
- ③ **mandatory 装配 + powered group**: x_vars 的 `AddExactlyOne` per group (反查) 是否保证每个 mandatory 装配恰好选一个 pose? powered group `x_var <= sum(cov_vars)` (`:600-601`) 与 `x_var == 0` (`:603`, 无 coverer 时) —— `==0` 把"无 coverer 的 powered mandatory" 钉死是 fail-closed, 这对吗 (真该 INFEASIBLE)? 还是某情况下该 pose 本可被其它 pole 覆盖却因 `_power_coverers_by_template_pose` 表不全被误钉 (false-INFEASIBLE)?
- ④ **`max_lex(area, min_side)`**: master 是否只判固定 `(w,h)` 可行性, **无** CP-SAT 加权目标? ghost feasibility 约束 + lower-bound count 是否纯约束、不引入优化目标? frontier 在外层按 tuple 比较? `min_side>=6` 是 admissibility 不是 tie-break? (本轮 r12 新增的是约束不是目标 —— 验证没顺手引入 ghost 相关的隐藏目标项。)
- ⑤ **hint 永不约束**: pose-bool `apply_solution_hint()` (`:1140-1173`) 是否只 `AddHint`、经 strict parser skip malformed、无 `Add(...)` 约束可行域? (r10 已修, 验证 r12 改动没复发。)

## 面边界 (只审本面, 以下明确不审)

- 其余 7 面及各自子问题正确性: **preprocess / cuts / benders·LBBD / binding / routing / campaign / scheduler** 各有独立审查线, 本轮不审。怀疑跨面时, 交叉引述 `PROJECT_LOCK.md` 对应契约 (而非在本轮重证), 在返回里指出可疑点交回主线即可。
- 子问题正确性 (端口绑定 / 网格布线 / 多商品流诊断的内部 soundness) 不审 —— 本面只到 master 几何编码 + solve 解回读边界。

## 明确不要报的

- **r12 两 finding 本身** (F-GM-R12-PB-GHOST-01 / F-GM-R12-PB-PROTOCOL-LB-01) 已修已 lock, 不重报修复本身 —— 只报「修复不完备 / 同型残留 / 反向缺陷 / 顺手引入的新缝」。
- **r11 两 finding 本身** (F-GM-R11-PB-REQ-POLE-01 / F-GM-R11-PB-STALE-01) 已修已 lock, 同样只报"不完备/残留/新缝"。
- 设计决策: canonical / 266 口径 / omni_wireless / 52-Port (R=S=52) 不变量 / `__unused__` sentinel 语义 / `min_side>=6` admissibility —— owner 已定。
- r2-r10 已修 finding 与已审结论 (重复报不算): F-GM-Q3-01 系列 (r2/r3-A/r4-A/r5-A)、F-GM-R6-01、F-GM-R8-SYM-01、LOW-HINT (r9/r10) 各条款本身。
- preprocess / cuts / benders / binding / routing / campaign / scheduler 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate, 是 owner 手动 gate 不是 bug); P1.3B `step_8_apply_to_master` 禁区 (`src/cuts/lifecycle.py` 显式 not-yet-integrated 边界); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- **env-gated / 条件路径行为不属 P1.2 certified soundness**: `EXACT_USE_POSE_BOOL_MASTER`、`EXACT_POWER_PLACEMENT_SUBPROBLEM`、`EXACT_B1_BYPASS_*`、`EXACT_USE_PORT_ACTIVE` 等都 env-gated, **不在默认 certified path 上**。但 pose-bool 后端可直接 `EXACT_USE_POSE_BOOL_MASTER=1` 启用, 所以其 false-FEASIBLE / stale-witness 缝**仍是本面 finding** (这是 r11/r12 已确立、lock 已收的口径, 见 `F-GM-R11-PB-01` / `F-GM-R12-PB-01`) —— 只是严重度按下方纪律标"env-gated/conditional"而非 certified soundness reset。
- 不要把「pose-bool 被 `pose_bool_master_not_certified` env guard 挡在公共 certified path 外」本身当 finding —— 这是已知 gate, 是这后端非 certified 的原因, 不是 bug。
- **ghost 不含 exterior-path 要求是 owner 已定禁区 (`PROJECT_LOCK.md` §4 Forbidden), 别建议加**。

## 严重度纪律

- **false-CERTIFIED on canonical + 默认 env = soundness reset (P1.2 闭环只认这个, HIGH)**: 把 certified path (坐标后端 `ExactCoordinateMaster`, 默认 env) 上的真 INFEASIBLE 铸成 FEASIBLE / 放过非法布局 / cut 后复活被禁解 → 这是 P1.2 soundness reset。
- **env-gated / conditional 路径的 false-FEASIBLE / stale-witness** (pose-bool 后端在 `EXACT_USE_POSE_BOOL_MASTER=1` 下的缝): 按 r11/r12 口径**仍记 soundness finding 并修**, 但**明确标 "env-gated, 非 certified-path reset"** —— 是 hardening, 不重置 P1.2 闭环计数。
- **false-INFEASIBLE 保守失败 = availability**: 把合法布局判死 (会漏真最大矩形但不会误认证) → 标 LOW 加固。
- 每条 finding 必须自带 severity 分类标签 (soundness-reset / env-gated-soundness / availability), 不要含糊。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3074, 数目以实跑为准; **硬不变量 = 0 failed**, passed 数随其它面修复浮动)。沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`。跑不完就跑专项 + 如实声明全量未完成 (别 claim 全量通过)。本面相关专项至少包含: `src/tests/test_master_cut_solution_invalidation.py` (含 r11/r12 新增的 ghost + protocol-lb regression)、`src/tests/test_master.py`、`src/tests/test_exact_coordinate_protocol_bounds.py`、`src/tests/test_solution_hint_malformed_defense.py`、`src/tests/test_ghost_anchor_filter.py`。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations anchored)。
- **finding 必须带可复现 probe 或严谨 file:line 论证; 实证推翻你的怀疑就不要报。** 攻击 pose-bool 后端时, 起 `EXACT_USE_POSE_BOOL_MASTER=1` 构造最小反例 —— r12 用的 probe 模板可借鉴 (1×1 grid + 单 required pole + 1×1 ghost / 空候选池 + generic-input 推下界), 见 `test_master_cut_solution_invalidation.py:190-340` 区间 r11/r12 新增的 5 条 regression 测试 (`test_pose_bool_unfiltered_ghost_*` / `test_pose_bool_protocol_storage_*`)。

## 交付物

- `REVIEW.md` (LF 行尾): 逐条 finding (severity 标签 / file:line / probe 或论证 / 修法, 有把握附 unified diff + regression 测试)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读:
  - **Q1 GHOST 完备性**: overlap 覆盖完整性 (三类 occupancy literal 是否全进 `cell_poses`, 逐类点 file:line) + anchor 枚举边界精确性 + filter 语义 (含 multi-anchor) + `forbidden=set()` 连带影响 + 与坐标/legacy 对齐缺口矩阵;
  - **Q2 PROTOCOL-LB 完备性**: 下界模板覆盖 (含 `power_pole` 排除是否正确不漏不重) + `max(fixed,lower)` 分支拼接相容性 + powered 下界模板进 coverage 通道的 family-empty 复发检查 + slot placeholder 误消费判读 + 与坐标后端"扣 fixed 防双花"对齐;
  - **Q3 其它缝 + 不变量换角度**: ghost↔front_clear 交互 / footprint 忠实度 / mandatory+powered group / max_lex 目标 / hint 永不约束 逐项 (独立判读)。
- 真 Pro 确认轮, 前轮已修不代表本轮默认干净; pose-bool 后端**连续两轮真 Pro 都还在出 HIGH**, 按你自己最独立、最对抗的判断下结论。

## 范围边界

- 重点 = r12 两修复 (GHOST anchor 显式编码 / PROTOCOL-LB certified 下界) 的**完备性钉死** + pose-bool 后端其它 false-FEASIBLE 缝挖掘 + 几何 master 不变量换角度重审; 其余面不审。
