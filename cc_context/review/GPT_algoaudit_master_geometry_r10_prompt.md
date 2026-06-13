# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 10 (终饱和轮·深角落 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_2cd169b4.zip`, sha256 `2cd169b46a12cc1e52e1915d89279be48fc0f6adbd02b1530d0994d18d1879eb`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **几何 master** (`src/models/exact_coordinate_master.py` 为主, 含 master_model 坐标 delegate 链)。

## 本面定义与历史: 几何 master, 收敛轨迹 r7 零 → r8 HIGH → r9 零, 本轮 = 终饱和轮 (连零 2 即达饱和下沿)

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r7 = 零 + LOW hint 加固; r8 = F-GM-R8-SYM-01 (双标尺对称破缺, 修 = 同序门卫) + LOW HINT-02; **r9 = 零 soundness (SYM-01 修复四向确认: 门卫量化范围 = slot 实际域逐族 / order_key 注入式 + 保代表性 / 543 条 residual 全集同序实证 / power family 复合尺复核) + LOW (community/legacy/pose-bool 三 hint 入口残留裸 int(), 修 = 共享 `src/models/solution_hint_parser.py` 全入口复用)**。LOW 修复在本包内。**本轮 r10 = 终饱和轮**: 连零 2 即达本面饱和下沿。**警示先例**: face 2 上一次终饱和轮 (r8) 恰恰抓出了 SYM-01 这个 HIGH false-INFEASIBLE — 终饱和轮不是走过场, 请按你最强攻击力做。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-CUT 系列含 CUT-R9-H1、F-PRE-R13-01 等), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 r9 LOW 修复轻确认

hint parser 共享化: 全仓搜还有没有 hint 值入口绕过 `solution_hint_parser.parse_strict_int_hint_value` (新旧入口枚举); parser 本体 `type(value) is int` 口径; 测试断言是否还固定旧截断行为。轻扫, 非主体。

### Q2 本面深角落 (终饱和轮主体 — 选 r2-r9 没有专审过的区域至少两个深挖)

候选区域 (按你判断挑, 也可以选你自己发现的别处):
- **ghost rectangle 交互约束本体**: ghost 矩形与 facility 的 no-overlap / 域排除编码 (mode-channelled bbox), ghost anchor 枚举与 `u_var` 通道, "ghost 不要求外部路径" (lock 明文) 之外 ghost 有没有被隐式加了别的要求; max_lex 目标在 (area, min_side) 上的字典序编码正确性。
- **power coverage witness 链**: footprint-channel power coverage 的存在性见证 (矩形性检查 fail-closed 回退精确 coverer 表是 P0 再审修的, 但那是 2026-06-11 — 本包还带着后续多轮改动, 链路有没有被同期改动碰过); pole capacity family 分组 (`_pose_power_capacity_signature`) 与 coverage 的对接。
- **mandatory exactly-one ↔ slot 装配链**: 266 实例到 slot 的装配 (mandatory group / required_optional / residual) 在多轮对称/signature 改动后的整体一致性; slot domains 与 AddAllowedAssignments/AddForbiddenAssignments 的互斥完备。
- **delta/interval 编码**: NoOverlap2D 或等价的区间/delta 编码与 footprint bbox 的对接 (非矩形 footprint 保守 bbox 是 lock 已接受口径, 但 bbox 推导本身的 mode 通道对不对)。

### Q3 自由攻击角

以上之外按你自己的独立判断深挖 1-2 处。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, 非矩形 footprint bbox 保守口径, ghost 无外部路径要求, owner 已定); r2-r9 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- 跳过 signature 单调的搜索变慢 (R8 修复预期代价)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3018 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 各选定区域的攻击过程与判读。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 终饱和轮深角落 + 自由攻击角; 其余面不审。
