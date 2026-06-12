# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 5 (饱和确认轮·R4-A 修复确认 + slot域×candidate pool 对接 + specs 文本独立对照)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_70457b5e.zip`, sha256 `70457b5e6cd759fd0fd75873b12b61f444ad3e569bb26216cea7aa383b22b15a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。
注意: 包基点之后仓库又落了 routing 面 F-RT-R5-01 与 preprocess 面 F-PRE-R10 系列修复, 都不在 master 几何主体; 本面主体文件与包一致。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: 几何 master (`src/models/exact_coordinate_master.py` + `src/models/master_model.py`), 收敛轨迹 1→2→0→1→1→1, 本轮目标连零起步

本面近 3 轮 (报告在包内 `cc_context/review/` 与 `archive/`): r2 = F-GM-Q3-01 (protocol storage 下界只数 residual 忽略 fixed → false-INFEASIBLE; latent+API); r3 = F-GM-Q3-01-R3-A (对偶残缝: `0 < fixed < lower` 时 residual 池被「有 fixed 就跳过」砍掉, shortfall 无 literal 可补; 修 = 单一谓词 `_needs_residual_optional_slots_after_fixed_required()` 两处共用 + residual 上界扣 fixed 防双花); **r4 = F-GM-Q3-01-R4-A (同族 API 缝: 显式传 `exact_required_pose_optional_counts={"power_pole": N}` 时 fixed pole slot 只占格不承担电杆语义 — 不入 family membership/count 通道、不入覆盖 witness 枚举 → 「固定 1 杆供 1 机」false-INFEASIBLE; 修 = `_all_power_pole_slots()` 统一 fixed+residual / fixed pole 接入 family tuple+membership [active=常量1] / family count 上界与 table/geometric 覆盖 witness 改用全部 materialized slots / lazy power stats 同步)**。r2 已全量重验 66403 姿态矩形性 + 半开区间 probe + 电力覆盖 54780 poses; r3 已核 ghost 锚点域完备性 + 对称破除保真; r4 已核 bound 族×方向 6 行全表 + family 瀑布激活重标号 + pool=0 退化矩阵。**本轮 r5 = R4-A 修复确认 + 刻意换两个未审角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND 系列 / F-BL-R3/R4 / F-RT-R2..R4 / F-CUT 系列 / F-PRE-R8/R9 条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-GM-Q3-01-R4-A 修复确认 (攻击面)
把 r4 修复当攻击面打: ① `_all_power_pole_slots()` 的 fixed+residual 合并 — 有没有消费点仍只读其中一半 (合并函数存在但旧引用残留 = 修复旁路)? 全文件扫 power pole slot 的所有读取点。② fixed pole 以「active=常量 1」进 family tuple/membership — 常量化在 CP-SAT 里与真 BoolVar 在各 witness/计数约束中的行为是否完全等价 (尤其 OnlyEnforceIf/sum 中的常量折叠)? ③ family count 上界与覆盖 witness 用全部 materialized slots 后, 上界本身的推导 (min(pose_count, area_bound) 类) 对 fixed+residual 混合是否仍是有效上界? ④ 与 R3-A 的 protocol 判定交界: 两个修复都改 slot 池构成, 同时携带 protocol fixed + pole fixed 的配置有没有交叉污染?

### Q2 slot 域构建 × candidate pool 对接纵深 (新角度)
master 的每个 slot 从 candidate pool 取 pose 域。请审这条对接链: ① **empty-domain slot fast-path** (域为空的 slot 走 `Add(0==1)` infeasible 直判、不建后续 channel) — 这个 fast-path 在所有 slot 类别 (mandatory/required-optional/residual-optional) 上的语义都正确吗? 域为空对 optional slot 应该是「不可激活」而非「模型 infeasible」— 实现是哪种? ② pose 过滤链 (ghost 重叠过滤 / anchor 域 / RAB 类过滤) 每一步的过滤判据是「必要条件」还是「可能过强」— 过强 = false-INFEASIBLE 方向, 逐步判读; ③ slot 域与 family 激活变量的耦合: 域被过滤变小后, family 计数上界/瀑布激活的标号论证是否仍成立 (域大小不均匀时重标号交换论证的前提)? ④ pose_idx 与 pool 的索引一致性: master 解里的 pose_idx 在 binding/routing 消费时对的是同一个 pool 排序吗 (排序不一致 = 拿错 pose 的静默错位)?

### Q3 specs 文本独立对照 (新角度; 方法论要求: 先读规则再对照实现, 不从实现学语义)
本项目曾发生「验证器从实现学语义 → 同源错」(routing 面 F-RT-R2-01)。请**先读 specs 中 master/placement 相关章节 (`specs/07_*.md` 等, 按包内实际文件名) 与 `rules/canonical_rules.json` 的 grid/empty_rectangle/facility 字段, 自己写下 master 应编码的每条约束的预期语义, 再对照实现逐条核**: ① 约束族清单 (mandatory 计数/不重叠/在界/电力覆盖/ghost 矩形空置/admissibility `min_side>=6`) 的规则依据 — 实现更严或更松或缺失? ② ghost 矩形语义: 「矩形内全空」的「空」在规则里包括/排除什么 (设施 body? 端口 connector? belt? 电力杆?) — 实现的 ghost no-overlap 排除集与规则口径一致吗? ③ `max_lex(area, min_side)` 的目标编码与 admissibility 的分工 (admissibility 是约束不是 tie-break) 在实现里是否干净。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r4 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- canonicalization 不受 enable_symmetry_breaking 控制 (r3/r4 已判配置语义非 soundness); `upper<fixed` 边界真 INFEASIBLE 判读 + 诊断 ValueError 建议 (r4 已挂账)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2972 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 对接链逐步判读表与 Q3 规则↔约束族对照清单。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = R4-A 修复确认 + slot域×pool 对接 + specs 文本独立对照; 其余面不审。
