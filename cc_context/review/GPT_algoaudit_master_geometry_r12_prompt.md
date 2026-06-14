# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 12 (真 Pro 对抗审查·pose-bool 后端 r11 修复钉死复核)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`, 对应干净 git 树 HEAD `8c61e1e`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`, 沙盒 Python 3.13, 离线安装)。`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) 已随包, 已校验。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **几何 master** (`src/models/exact_coordinate_master.py` 为坐标后端核, `src/models/pose_bool_exact_master.py` 为 env-gated pose-bool 后端, `src/models/master_model.py` 是公共 `MasterPlacementModel` 外壳/legacy 路径)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = 几何 master 的放置约束编码: footprint no-overlap / ghost 矩形 / 电力覆盖 witness / mandatory 装配 / optional·residual 基数不等式 / 对称破缺 / solve 解回读 + cut 后 witness 清理。历史:
- r2 = F-GM-Q3-01 (protocol storage 下界只数 residual optional 槽、忽略 fixed required → `0>=1` false-INFEASIBLE);
- r3 = F-GM-Q3-01-R3-A (对偶残缝: `0<fixed<lower` 时 residual 池被砍, shortfall 无 literal 可补);
- r4 = F-GM-Q3-01-R4-A (fixed pole 只占格不承担电杆语义, 不入 family/count/coverage witness);
- r5 = F-GM-Q3-01-R5-A (power family 映射为空时 fixed pole 被 `0==1` 判死);
- r6 = F-GM-R6-01 (cut 成功后只清 `_last_solution`, 旧 `_solver/_status` 仍在 → `extract_solution()` 复活刚被 cut 禁止的解 = stale witness);
- r7 = 零 soundness + LOW hint; r8 = F-GM-R8-SYM-01 (双标尺对称破缺删空可行等价类);
- r9 = 零 + LOW; r10 = 零 + LOW (persisted hint 入口绕过 strict parser);
- **r11 = 真 Pro 首轮重审, 抓出 2 个 HIGH, 都在 env-gated pose-bool 后端 (`PoseBoolExactMasterDelegate`)**:
  - **F-GM-R11-PB-REQ-POLE-01 (HIGH, false-FEASIBLE)**: pose-bool build 把 `exact_required_pose_optional_counts["power_pole"]` 的 fixed required 电杆需求 `continue` 跳过, 只建 residual optional pole 池 ("no demand fix")。当所有 pole pose 被 ghost body 排除时模型返回 `OPTIMAL` 无杆 = 真 INFEASIBLE 铸成 FEASIBLE (= r4 的 R4-A 缝在 pose-bool 后端复发)。
  - **F-GM-R11-PB-STALE-01 (HIGH, stale witness)**: pose-bool 增量 cut 路径只清 `owner._last_solution`, 保留旧 `_solver/_status` → `extract_solution()` 复活刚被 cut 禁止的解 (= r6 的形在 pose-bool delegate 复发)。

**两个 r11 finding 已修复并已 lock (`PROJECT_LOCK.md` §3 `F-GM-R11-PB-01` 条款, 同步 `F-GM-Q3-01-R4-A` / `F-GM-R6-01`)**。修复落点 (本包 HEAD `8c61e1e`):
- `pose_bool_exact_master.py:93-99` 新增 `_invalidate_owner_solver_witness()` (同清 `_last_solution`/`_solver`/`_status`), 在 5 条增量 cut 路径调用 (`:837` patch_routing_core / `:871` separator_capacity / `:987` benders / `:1190` lazy_demand / `:1246` blocking_cell);
- `pose_bool_exact_master.py:382-436` 累计 `required_power_pole_demand`, 在 feasible pole vars 建好后加 `sum(pole_vars) >= demand` (`:436`), 不足则 `0 >= demand` fail-closed (`:433-435`), 并填 `required_optional_slots["power_pole"]` (`:431`)。

**本轮 r12 性质 = 把 r11 两修复钉成攻击面 (不重报已修项本身)。** 真 Pro 确认轮, 独立判断, 三条主攻向:

1. **REQ-POLE 修复完不完备 (同型残留 / 反向缺陷)**。r4 的 R4-A 缝原始口径是: fixed pole 是**真电杆**, 必须**完整**进 pole family membership / count 上界 / 覆盖 witness 枚举, 而不只是占格。r11 修复只加了 `sum(pole_vars) >= demand`。请独立判: pose-bool 后端这些「required pole」是否真正承担了**完整电杆语义**? 具体钉:
   - required pole 用的是不是跟 residual pole 同一个 `pole_vars` 池 (`:414-436`)? 若是, 它们能否在 power coverage 约束 (`:443+`, mandatory powered group / required-optional powered tpl 的 `x_var <= sum(cov_vars)`) 里**当 coverer 出现**? 还是 `required_optional_slots["power_pole"]` (`:431`) 只是统计 placeholder、那些 var 没真正进 coverage 表?
   - `>=` 而非 `==` 的选择 (`:436`): 是否真不会把合法配置判死 (residual 杆仍可额外出现)? 有没有反向缝 —— 比如 fixed demand 满足后, coverage 下界又对**同一池**叠加了一个更严的 `==`/upper, 造成 over-constrain?
   - feasible pole vars 经 ghost forbidden-cell 过滤 (`:421-424`) 后再判 `len < demand → fail-closed` (`:433-435`): 这条 fail-closed 是否**精确** (该不可行才不可行)? 有没有把「ghost 挡掉部分但仍有足够 pose」的合法配置误杀 (false-INFEASIBLE, 标 LOW availability)?
   - coordinate 后端对同一语义的处理 (`exact_coordinate_master.py` 的 `_all_power_pole_slots()` / family literals / capacity witness, r11 review 引 `:3090-3122`/`:3285-3403`) 是 r4 已坐实的正确口径 —— pose-bool 后端是否**对齐**? 还是只补了 count 不等式、漏了 family/coverage 那半边 (= R4-A 在 pose-bool 只修一半)?

2. **STALE 修复完不完备 (有没有第 6、第 7 条没清的 mutation 点)**。r11 只钉了 5 条「叫得出名字的 cut 方法」。请独立全扫 pose-bool delegate 里**所有**在 solve 之后还会 `self.model.Add(...)` / 给 `owner.model` 加约束的入口, 逐一判:
   - 是否每条都在成功 mutate 后调 `_invalidate_owner_solver_witness()`? 特别留意 `add_separator_capacity_cut` (`:848-872`, 委托 `add_separator_capacity_hull_constraints`)、`add_patch_routing_core_cut` 里的 signature lifting (`:779-846`)、以及任何 helper 在 `add` 之后**提前 return** 绕过清理的分支。
   - 反向缝: `_invalidate_owner_solver_witness()` 是否可能被**过度调用** (mutate 失败/no-op 时也清), 造成 false-INFEASIBLE? (这是 availability 不是 soundness, 标 LOW)。重点仍是**漏清** (soundness)。
   - 公共外壳 `MasterPlacementModel.extract_solution()` (`master_model.py:11830`) / `extract_bound_state()` (`:11742`) 的 gate 逻辑: 清掉 `_solver`/`_status` 后, 这两个方法是否真的会返回空/no-incumbent 而**不**从别处 (例如 delegate 自缓存、`_last_solution` 以外的字段) 重建被 cut 禁止的解? 委托链 `MasterPlacementModel` → `PoseBoolExactMasterDelegate.extract_solution()` (`:874+`) 是否有独立于 `owner._solver` 的 stale 缓存?

3. **r11 修复有没有顺手引入新缝**。两处修复都改了 build / cut 路径。独立判: 改动是否破坏了 env-off (coordinate/legacy) 行为? `required_optional_slots["power_pole"]` 这个新 placeholder 是否被下游 (统计 / 对称破缺 / 别的 cut 的 slot 枚举) 误当成真 slot 域消费, 造成多收非法 tuple (false-FEASIBLE) 或删空等价类 (false-INFEASIBLE)?

**前轮 thinking r2-r10 连零不构成任何先验; 真 Pro r11 一上来就在 pose-bool 抓出 2 HIGH。** 请把 pose-bool 后端当作仍需深审的面, 用最独立、最对抗的判断重走一遍, 尤其盯 r11 两修复的**完备性边界**。

注意: 包内带其它面同期落的修复 (cuts / preprocess / benders / binding / routing 条款), 各面有自己的线, **别在本轮重报**。

## 审查重点 (按本轮优先级)

### Q1 (主攻) REQ-POLE 修复完备性 — pose-bool fixed required pole 是否承担完整电杆语义

- ① fixed required pole 是否进 power coverage 表 (能当 coverer 覆盖 powered 设施)? 还是只数了个数、没进 coverage / family 通道 → 复刻 R4-A 「只占格不承担语义」的一半?
- ② `sum(pole_vars) >= demand` (`:436`) 对**共享池**叠加: 与 residual 上界 / coverage 下界是否相容 (无 over-constrain false-INFEASIBLE, 无 under-constrain 漏挡)?
- ③ ghost forbidden 过滤后的 `len(feas) < demand → 0>=demand` fail-closed (`:433-435`): 边界精确性 (合法贴边配置不误杀)。
- ④ 与 coordinate 后端 (r4 已坐实正确口径) 的语义对齐缺口逐项。

### Q2 (主攻) STALE 修复完备性 — pose-bool cut 后 witness 清理是否无遗漏

- ① 全扫 delegate 所有 post-solve model-mutation 入口, 找第 6+ 条未清 `_solver/_status` 的路径 (= r6/R11-STALE 同型残留)。
- ② `MasterPlacementModel.extract_solution()` / `extract_bound_state()` 的 gate: 清字段后是否真返回空, 有无独立 stale 缓存绕过。
- ③ exact-coordinate (`exact_coordinate_master.py` r11 review 引 `:7028-7080`) 与 legacy (`master_model.py:11945-11947`) 两路径是否仍正确同清 (r11 改 pose-bool 时没碰坏这两条)。

### Q3 (并行) 几何 master soundness 不变量换角度重审 (前轮已查过的点, 换新角度, 别复读)

只在你独立挖到新角度时报。框架:
- ① 几何约束忠实度: footprint bbox over-approximate (保守安全) 不 under-approximate (漏挡 false-FEASIBLE)? ghost anchor 枚举完整 (`range(grid-w+1)` 无裁剪、越界 fail-closed)? ghost「空」口径 = **body-only** (不含 connector/belt/coverage)? `AddNoOverlap2D` 只收 body+ghost? **有无暗藏 exterior-path/connectivity 约束 (禁区, 存在即 finding)**?
- ② optional/residual 基数不等式族 (F-GM-Q3-01 系列): 每条不等式是否**规则蕴含的有效不等式** (无启发式 stricter-than-rule)? 混合 fixed/residual 时既不漏 fixed 也不双花 residual upper?
- ③ 对称破缺保代表性 (F-GM-R8-SYM-01): 双标尺 (order_key/signature) 是否只在同序门卫成立时加? 门卫量化范围 == slot 实际域 (allowed_tuples 反查)?
- ④ `max_lex(area, min_side)`: master 只判固定 `(w,h)` 可行性, **无** CP-SAT 加权目标? frontier 在外层按 tuple 比较? `min_side>=6` 是 admissibility 不是 tie-break?
- ⑤ hint 永不约束: malformed hint (非 int / 越界 pose / 不存在 anchor) 降级 skip 而非进可行域, 只写 `solution_hint` proto?

## 面边界 (只审本面, 以下明确不审)

- 其余 7 面及各自子问题正确性: **preprocess / cuts / benders·LBBD / binding / routing / campaign / scheduler** 各有独立审查线, 本轮不审。怀疑跨面时, 交叉引述 `PROJECT_LOCK.md` 对应契约 (而非在本轮重证), 在返回里指出可疑点交回主线即可。
- 子问题正确性 (端口绑定 / 网格布线 / 多商品流诊断的内部 soundness) 不审 —— 本面只到 master 几何编码 + solve 解回读边界。

## 明确不要报的

- **r11 两 finding 本身** (F-GM-R11-PB-REQ-POLE-01 / F-GM-R11-PB-STALE-01) 已修已 lock, 不重报修复本身 —— 只报「修复不完备 / 同型残留 / 反向缺陷 / 顺手引入的新缝」。
- 设计决策: canonical / 266 口径 / omni_wireless / 52-Port (R=S=52) 不变量 / `__unused__` sentinel 语义 / `min_side>=6` admissibility —— owner 已定。
- r2-r10 已修 finding 与已审结论 (重复报不算): F-GM-Q3-01 系列 (r2/r3-A/r4-A/r5-A)、F-GM-R6-01、F-GM-R8-SYM-01、LOW-HINT (r9/r10) 各条款本身。
- preprocess / cuts / benders / binding / routing / campaign / scheduler 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate, 是 owner 手动 gate 不是 bug); P1.3B `step_8_apply_to_master` 禁区 (`src/cuts/lifecycle.py` 显式 not-yet-integrated 边界); exploratory **行为/性能**不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- **ghost 不含 exterior-path 要求是 owner 已定禁区 (`PROJECT_LOCK.md` §4 Forbidden), 别建议加**。
- pose-bool 后端被 `pose_bool_master_not_certified` env guard 挡在公共 certified path 外 —— 这是已知 gate, **不要**把「它被 gate 挡住」当作 finding; 但它仍是可直接 `EXACT_USE_POSE_BOOL_MASTER=1` 启用的 master 后端, 所以其 false-FEASIBLE / stale-witness 缝**仍是本面 soundness finding** (这是 r11 已确立、lock 已收的口径, 见 `F-GM-R11-PB-01`)。

## 严重度纪律

- **false-CERTIFIED = soundness** (P1.2 闭环只认这个): 把真 INFEASIBLE 铸成 FEASIBLE / 把非法布局放过 / cut 后复活被禁解 → HIGH。pose-bool 后端虽 env-gated, 其 false-FEASIBLE/stale-witness 按 r11 口径仍记 soundness。
- **false-INFEASIBLE 保守失败 = availability**: 把合法布局判死 (会漏真最大矩形但不会误认证) → 标 LOW 加固。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3058, 数目以实跑为准; **硬不变量 = 0 failed**, passed 数随其它面修复浮动)。跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。本面相关专项至少包含: `src/tests/test_master_cut_solution_invalidation.py`、`src/tests/test_master.py`、`src/tests/test_exact_coordinate_protocol_bounds.py`、`src/tests/test_solution_hint_malformed_defense.py`、`src/tests/test_ghost_anchor_filter.py`。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations anchored)。
- **finding 必须带可复现 probe 或严谨 file:line 论证; 实证推翻你的怀疑就不要报。** 攻击 pose-bool 后端时, 起 `EXACT_USE_POSE_BOOL_MASTER=1` 构造最小反例 (r11 用 1×1 grid + 单 required pole + ghost 全占的 probe 模板可借鉴, 见 `test_master_cut_solution_invalidation.py` 里 r11 新增的两条 regression 测试)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法, 有把握附 unified diff + regression, LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读:
  - **Q1 REQ-POLE 完备性**: fixed required pole 是否进 coverage/family 通道 (逐通道点名 file:line) + `>=` 选择相容性 + ghost-filter fail-closed 精确性 + 与 coordinate 后端对齐缺口矩阵;
  - **Q2 STALE 完备性**: pose-bool 全部 post-solve model-mutation 入口清单 (每条标是否清 `_solver/_status`) + `extract_solution/extract_bound_state` gate 判读 + exact/legacy 两路径仍同清确认;
  - **Q3 不变量换角度重审**: 几何忠实度 / 基数不等式族×规则蕴含矩阵 / 对称破缺保代表性 / max_lex 目标 / hint 永不约束 逐项 (前轮已查点换新角度的独立判读)。
- 真 Pro 确认轮, 前轮已修不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = r11 两修复 (REQ-POLE 电杆完整语义 / STALE cut 后 witness 清理) 的**完备性钉死** + 几何 master soundness 不变量换角度重审; 其余面不审。
