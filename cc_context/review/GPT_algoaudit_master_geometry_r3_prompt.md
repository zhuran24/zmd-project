# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 3 (饱和确认轮·F-GM-Q3-01 修复攻击面 + 对称破除/ghost 锚点域角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_gm_r3_snapshot_b377a2a7.zip`, sha256 `b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: 几何 master (`src/models/exact_coordinate_master.py` + `master_model.py` 几何侧), r1-r2 已收敛

历史 (报告在包内 `cc_context/review/algoaudit_master_geometry_r2_REVIEW_20260612.md` 等): r1 抓 B-01 (no-overlap 用模板固定尺寸非真 footprint, 已修为 occupied_cells 派生 bbox) + 再审 2 finding 已修 + 确认 1 轮零; r2 双向保真轮抓 **F-GM-Q3-01** (coordinate delegate 的 protocol storage 下界只对 residual optional 槽编码, fixed required 槽不抵扣 → 「fixed 槽已满足下界 + 零 residual」合法配置被编码成 `0 >= 1` false-INFEASIBLE; 修 = `residual_active >= max(0, lower_bound - fixed_required_count)` shortfall 编码)。r2 已审过: 66403 全姿态矩形性独立重验 / 半开区间 off-by-one probe / 13 约束族×规则溯源矩阵 / 4761 杆电力覆盖全验 / ghost 编码无暗藏连通约束。**本轮 r3 = F-GM-Q3-01 修复确认 + 刻意换角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND-R1..R5 / F-BL-R3 / F-RT-R2 / F-CUT-R2 / F-PRE-R8/R9 系列条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-GM-Q3-01 修复确认 (攻击面)
把 r2 修复当攻击面打: ① shortfall 编码 `residual_active >= max(0, lower_bound - fixed_required_count)` — `fixed_required_count` 的统计口径是否恰好 = 「计入该下界的 fixed required optional 槽」(多算 = 下界变松 = 完整性方向; 少算 = 残留原 bug 的弱化版)? fixed 槽的判定来源与 master 实际固定约束是否同一来源 (两个来源可分裂)? ② `max(0, ...)` 截断: lower_bound 为 0 或负时的边界行为? ③ 该下界的 lower_bound 本身来源 (`ceil(generic input demand / wireless slots)`) 在修复后是否仍从同一快照取数 (与 F-BIND-R3/R4/R5 单快照族一致)? ④ 修复是否对称地覆盖了所有用到「required-optional 数量下界」的编码点 (只修 protocol storage 一处还是该模式有同型兄弟)?

### Q2 对称性破除与解空间保真 (新角度)
specs/07 §7.5 的对称破除约束 (同模板实例间的字典序/排序约束)。这是 exact 求解里最容易「切掉解」的约束类: ① 每条 symmetry breaking 约束是否严格只在**同构解等价类内**裁剪 (被裁的每个解必有一个保留的等价代表)? 等价性判定依据什么 — 模板相同就等价, 还是要求 operation/binding 角色也可互换? 若两个同模板实例的 operation_type 不同 (一台 crusher 一台 packer 同为 3x3), 它们**不可互换**, 字典序约束会切掉真解 — 请核实实例→变量的分组粒度。② 对称破除与 mandatory instance 的固定 anchor/pose 顺序交互: resume/重建时实例顺序是否稳定 (顺序漂移 = 同一解这次合法下次被切)? ③ residual optional (供电桩) 的激活对称破除 (若有「激活第 k 个之前必须激活第 k-1 个」类约束): 与 pose 选择的耦合是否会切掉「只有高编号杆有合法 pose」的配置?

### Q3 ghost rectangle 锚点域完备性 (新角度)
ghost 矩形 (w,h) 的候选锚点集 R_{w,h}: ① 枚举是否覆盖全部合法左下角 (0 <= x <= 70-w, 0 <= y <= 70-h)? 边界 off-by-one 会漏掉贴边最优解 (false-INFEASIBLE 方向 = objective 级)。② (w,h) 与 (h,w) 双向枚举: 项目已声明候选域全向 (V75+); master 侧对一个给定 oriented (w,h) 的锚点枚举是否依赖「w<=h」之类的隐含假设? ③ ghost 与 mandatory/optional 实例的 no-overlap: ghost 用的 footprint 是否精确 w×h (不会被 bbox 通道意外放大/缩小)? ④ 70×70 网格边界本身: 实例 footprint 越界裁剪与 ghost 锚点裁剪是否同一坐标约定 (半开 vs 闭区间混用会产生 1 格缝)。

### Q4 抽查维持
r1/r2 已修结论抽查 2-3 处仍在场 (B-01 footprint bbox 派生 / mode-channel 双向 bbox / F-GM-Q3-01 回归有效性), 不用全量重审。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r2 已修 finding 与已审结论 (重复报不算)。
- binding 建模/Benders 主循环/routing 编码/cuts/preprocess/campaign/scheduler 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; 非矩形 footprint 的 bbox 保守过近似是已登记决策 (lock: may over-approximate, must not under-approximate)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2955 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 对称破除分组粒度判读与 Q3 锚点域核验范围。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-GM-Q3-01 修复确认 + 对称破除解空间保真 + ghost 锚点域完备性; 其余面不审。
