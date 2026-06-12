# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 7 (饱和确认轮·F-GM-R6-01 修复确认 + ghost 矩形编码本体 + solution hint 通道)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_38b57070.zip`, sha256 `38b570700c77f3f1a7b3f6c2ac7e9c2f2ec6385c7a93c2ee34ca7ce857ab8abe`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: 几何 master (`src/models/exact_coordinate_master.py` + `src/models/master_model.py`), 收敛轨迹 1 (r4)→1 (r5)→1 (r6), 本轮目标首个干净轮

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r4 = F-GM-Q3-01-R4-A (fixed pole 不承担杆语义); r5 = F-GM-Q3-01-R5-A (R4-A 退化边界: family 映射空时对 fixed pole `Add(0==1)` 判死合法几何); **r6 = F-GM-R6-01 (HIGH, API soundness: cut 应用成功后只清 `_last_solution`, 旧 `_solver`/`_status` 仍在, `extract_solution()`/`extract_bound_state()` 可从旧 solver witness 重建刚被 cut 禁止的解; 修 = exact 与 legacy 双路径 cut 成功后同清 `self._solver = None` + `self._status = None`)**。r6 已核 R5-A 修复 (空映射成因等价/几何保留/非空空表 fail-closed) + 解回读链 5 环 (tuple 反查/inactive slot/ghost 同源/bound state) + cut apply (alias fail-closed/OnlyEnforceIf 极性/N 计数/all-or-nothing)。**本轮 r7 = R6-01 修复确认 + 两个未深审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-RT-R2..R5 / F-CUT 系列含 PCR-R5 / F-PRE-R8..R11 条款), 这些面各有自己的线, 别在本轮重报。本面主体自 r6 修复 (F-GM-R6-01) 后零代码变化, 该修复在本包内。

## 审查重点 (按优先级)

### Q1 F-GM-R6-01 修复确认 (攻击面)
① **清理完备性**: `_solver`/`_status`/`_last_solution` 之外, 还有没有从 solve 派生、cut 后变 stale 的缓存状态 (objective 值缓存? bound state 缓存? hint 残留? 任何 `_last_*` / memo 字段)? 全扫两个 master 类的实例字段, 列出每个 solve-派生字段在 cut apply 成功路径上的处置。② **清理后的消费方向**: `extract_solution()` / `extract_bound_state()` 在 `_solver=None` 后是 loud-fail (异常/明确 None) 还是有路径静默重建或返回旧值? ③ **exact vs legacy 双路径平行性**: 两边清理的字段集与时机是否一致, 有没有一边清了另一边漏的字段? ④ **反方向**: cut 应用失败/部分失败 (all-or-nothing 回滚) 路径上, 不该清的 witness 有没有被误清 (清过头 = 丢合法 witness, 方向安全但影响收敛, 请判读)?

### Q2 ghost 矩形编码本体 (新角度; 此前 r5 只做过 specs 文本对照, 编码实现从未独立深审)
`exact_coordinate_master` 的 ghost 矩形 enforcement: ① **anchor/尺寸域构造**: ghost 候选 (x, y, w, h) 的变量域与 candidate 给定尺寸的联动 — 域裁剪有没有裁掉合法 anchor (false-INFEASIBLE 方向) 或留进非法 anchor (false-FEASIBLE 方向)? ② **ghost×placement 互斥的「空」口径**: 项目口径 = ghost 内须空的是设施 body (body-only), port connector 可以伸进 ghost。互斥约束的实现 (per-cell 或 interval) 与这个口径严格一致吗 — 逐设施类别 (含 boundary 1x3 与 pole 2x2) 判读哪些格被纳入互斥; ③ **max_lex 目标实现**: area 主、min_side 次的词典序在 CP-SAT 里怎么编码 (单目标加权? 两阶段?) — 编码保证「area 严格优先」在所有数值范围下成立吗 (权重溢出/越界)? `min_side >= 6` 是 admissibility 不是 tie-break — 实现位置对吗? ④ **禁区确认**: PROJECT_LOCK 禁止给 ghost 加 exterior-path 要求 — 确认现实现没有任何形态的外部连通约束。

### Q3 solution hint 通道 (新角度; 从未独立审过)
`apply_solution_hint()` / `AddHint` 路径 (含 community blueprint hint 注入 `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` 经 benders_loop merge 后传入): ① **hint 永不约束**: AddHint 的 CP-SAT 语义 = 搜索起点建议, 不改可行集 — 实现里有没有任何把 hint 误编码成约束 (Add/AddBoolOr 等) 的路径? 错误/不可行 hint 必须只影响速度不影响结论, 请构造一个故意错误的 hint 实证结论不变; ② **merge 语义**: greedy hint 与 community hint 的覆盖合并 (community 覆盖 greedy on overlap) 在 slot 粒度上有没有产生半套 hint (部分 slot 来自 A 部分来自 B) 导致 hint 自相矛盾 — 自相矛盾的 hint 对 CP-SAT 是合法输入吗 (应只是没用); ③ **malformed hint 防御**: 越界 pose_idx / 不存在的 instance / 非 int 值在哪一层被拒, fail 方向是丢 hint 继续 (安全) 还是异常中断 solve (可用性) 还是静默错位应用 (必须查)? ④ **hint×cut 交互**: cut 应用后重 solve 时旧 hint 还挂在模型上吗 — 指向已被禁解的 hint 是纯性能问题还是有 soundness 缝?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r6 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/cuts 各面 (各自有线); PCR patch 模型 (cuts 面 r5 刚修四义务)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- canonicalization 不受 enable_symmetry_breaking 控制 (已判配置语义); `upper<fixed` 真 INFEASIBLE + 诊断建议 (已挂账)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2982 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 solve-派生字段处置全表、Q2 ghost 编码逐项判读、Q3 错误 hint 实证。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-GM-R6-01 修复确认 + ghost 编码本体 + hint 通道; 其余面不审。
