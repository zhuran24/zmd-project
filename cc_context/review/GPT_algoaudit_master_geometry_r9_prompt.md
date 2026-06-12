# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 9 (确认轮·F-GM-R8-SYM-01 修复确认 + 同序门卫数学 + 自由攻击角)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_095a0b6d.zip`, sha256 `095a0b6d5f7d4496f3ef99fb71f2c6873555b10324c045b5b78ef91cc85f5eda`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: 几何 master, 收敛轨迹 1→0 (r7 零)→1 (r8 HIGH), 本轮目标干净轮重启

本面近 3 轮 (报告在包内 `cc_context/review/archive/`): r6 = F-GM-R6-01 (cut 后旧 solver witness); r7 = 零 + LOW hint 加固; **r8 = F-GM-R8-SYM-01 (HIGH, false-INFEASIBLE: 同构 slot 在 `order_key` 单调之上又加 `signature` 单调 = 双 total order, pose 对一升一降时整个可行等价类被删空, max_lex 下漏真最大矩形; 实数据多 group 有反向排列; 修 = signature 单调加同序门卫 [仅当该 slot 族全候选 pose 的 signature 按 order_key 非降时才加 = 冗余剪枝, 否则跳过 + telemetry 计数] + order_key 单标尺保留) + LOW F-GM-R8-HINT-02 (telemetry 二次 int() + float/bool 截断; 修 = strict-int parser 全链)**。两修复都在本包内, lock 新增「单标尺义务」条款 (one total order per interchangeable slot family)。**本轮 r9 = SYM-01/HINT-02 修复确认 + 自由攻击角**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND / F-BL / F-RT / F-CUT / F-PRE 系列含 R12-01 条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-GM-R8-SYM-01 修复确认 (攻击面, 本轮主体)
① **同序门卫的量化范围**: 门卫判定「signature 按 order_key 非降」用的候选集是什么 — 该 slot 族**实际可选的全部 pose** (allowed tuples / candidate pose indices) 还是某个子集/超集? 子集判同序但全集不同序 = 残留 SYM-01 (必须查); 超集判不同序 = 多跳过 (安全)。逐 slot 族 (mandatory group / required_optional / residual protocol_storage_box) 核门卫输入与约束作用域是否同一集合。② **order_key 单标尺自身的保代表性**: `order_key = x*scale_x + y*scale_y + mode` 是 total order 吗 — scale 选取会不会让两个不同 (x,y,mode) 撞同 key (撞 key 时 `<=` 仍安全, 但请确认); 对每个 slot 族验证「任意可行多重集按 order_key 排序后仍可行」的前提 (slot 真同构吗 — 有没有 slot 间存在差异化约束 [如第一个 slot 有特殊处理] 使排列不可交换)? ③ **门卫判定的实现正确性**: 同序检查的比较器与加约束时用的 signature/order 值同源吗; 空族/单 pose 族边界; ④ **residual protocol_storage_box 的 543 条 signature 单调**: 这族通过了门卫 — 独立抽查验证该族确实全集同序 (而不是门卫误判); ⑤ **power_pole family 排序** (active, family, order_key 三元) 与新门卫的关系 — family 排序是另一把尺吗, 为什么它不踩 SYM-01 (r8 判安全, 请独立复核)。

### Q2 F-GM-R8-HINT-02 修复确认 (轻确认)
strict-int parser 的覆盖: 所有 hint 值入口 (mandatory pose / optional pose / ghost anchor / legacy path) 都走同一 parser 吗; bool 是 int 子类 — 显式拒了吗; telemetry 返回阶段无二次裸 int()。

### Q3 自由攻击角
以上之外, 用你自己的独立判断选 1-2 个你认为本面 (含 r8 补丁引入的新代码) 最薄弱的点深挖。r8 补丁本身是新代码 — 它的 telemetry 计数/跳过逻辑/门卫缓存有没有引入新缝, 是天然候选。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r8 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- 跳过 signature 单调导致的搜索变慢 (剪枝减弱是修复的预期代价, 非 finding); 非矩形 footprint bbox 保守口径 (lock 已接受)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3004 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q1 门卫量化范围逐族判读与 order_key 保代表性论证。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = SYM-01/HINT-02 修复确认 + 自由攻击角; 其余面不审。
