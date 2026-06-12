# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环面 round 4 (饱和确认轮·F-BL-R3 修复攻击面 + 重入/终止语义角度)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_bl_r4_snapshot_b377a2a7.zip`, sha256 `b377a2a75e67697a38b2e46f8dc1407677a1f9936406b51695a7094487524531`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本面定义与历史: Benders/LBBD 主循环 (`src/search/benders_loop.py` 为核), r1-r3 已收敛

历史 (报告在包内 `cc_context/review/algoaudit_benders_loop_r3_REVIEW_20260612.md` 等): r1 抓 A-1 (routing 局部连续≠全局连通) + A-2 (front_blocked binding-local 证据直接铸 master nogood), 已修并经 2 轮独立确认; r3 涟漪轮抓 **F-BL-R3-01** (`EXACT_B1_BINDING_ALT_CAP` 命中把预算耗尽当 alternatives 穷尽证明铸 whole-layout nogood; 修 = cap 命中+仍有替代 → UNKNOWN, 穷尽证明唯一来源 = binding 重解 INFEASIBLE) 与 **F-BL-R3-02** (routing 非三态 status 落默认 INFEASIBLE 分支; 修 = 显式 contract guard, 非 FEASIBLE/INFEASIBLE/TIMEOUT 一律 UNKNOWN 无 cut)。r3 已审过: 16 行状态消费矩阵 / 五类 cut 时机与作用域 / 三交互对 / max_lex 排序键与 UNKNOWN-frontier 阻挡链。**本轮 r4 = F-BL-R3 修复确认 + 刻意换角度**。

注意: 包内带着其它审查面同期落的修复 (lock 末 F-BIND-R1..R5 / F-GM-Q3 / F-RT-R2 / F-CUT-R2 / F-PRE-R8/R9 系列条款), 这些面各有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 F-BL-R3 修复确认 (攻击面)
把 r3 修复当攻击面打: ① cap→UNKNOWN 路径: `EXACT_B1_BINDING_ALT_CAP` 命中返回 UNKNOWN 后, candidate 的后续处理 (campaign 记录 / frontier 推进 / retry) 是否把 UNKNOWN 当 UNKNOWN 对待 — 有没有下游消费点把「UNKNOWN + 部分 binding nogood 已加」的状态误读成更强的东西? cap 命中时**已经加进 binding model 的 nogood** 在同一 candidate 后续 retry/重入时是否被正确重建 (而不是带着旧 nogood 继续数新的 alternatives)? ② status contract guard: 覆盖的是 routing solve 的返回值; binding solve 与 flow 诊断的 status 消费是否有同型缝 (非预期值落进强分支)? ③ 修复后「穷尽证明 = binding 重解 INFEASIBLE」: 这个 INFEASIBLE 是在加完全部 nogood 后的同一 model 上得出 — 若 binding model 在循环中途有任何约束被意外保留/丢失 (例如 generic slot 约束随重解漂移), INFEASIBLE 证明是否仍然可信? 给出 model 生命周期的判读。

### Q2 重入与重试语义 (新角度)
同一 candidate 可能多次进入 benders loop (serial retry / parallel worker 重派 / campaign resume 后重跑)。请审: ① 每次进入时 master/binding/routing 的模型与 cut 状态是「全新构建」还是「携带上次状态」? 若全新, 上次 run 加的 binding nogood/master nogood 丢失是否影响**正确性** (应只影响效率— 重新枚举重新证明; 若有路径把上次的部分结论当本次前提, 给 probe)? ② candidate 状态从 RUNNING/UNKNOWN 重入时, 有没有路径读取上次的中间产物 (warm hint 之外的任何 proof-bearing 状态)? hint 是允许的 (AddHint 非约束), 但要确认 hint 注入点不会把 hint 当硬约束。③ 迭代上限/时间预算耗尽的退出路径: 每个退出点的 candidate 终态是否都落 UNKNOWN/TIMEOUT 而非强结论?

### Q3 终止与 frontier 推进保真 (r3 Q4 的纵深)
r3 验证过 max_lex 排序键。本轮纵深: ① outer loop 从大 area 往下扫的剪枝条件 — 「当前已证 CERTIFIED(area=A, min_side=M)」之后哪些 candidate 被跳过? 跳过条件是否严格等价于「字典序不可能更优」(若把 min_side 二级序也用于跳过, 需要 area 相同才可比)? ② UNKNOWN candidate 的阻挡语义: 终态 frontier 评估时 UNKNOWN 是否一律视为「未证伪」从而阻挡 CERTIFIED 宣称 (而不是被静默跳过)? ③ admissibility (min_side >= 6) 在 outer 候选生成与 frontier 评估两侧是否一致 (一侧 >= 一侧 > 的 off-by-one 会漏/多候选)?

### Q4 抽查维持
r1/r3 已修结论抽查 2-3 处仍在场即可 (A-1 connectivity guard 验收边界 / A-2 binding 枚举优先 / F-BL-R3-01 回归测试有效性), 不用全量重审。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r1-r3 已修 finding 与已审结论 (重复报不算)。
- binding 建模/master 几何/routing 编码/cuts/preprocess/campaign/scheduler 各面 (各自有线; 本面只管主循环编排/状态消费/cut 时机/终止语义)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈2955 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 重入路径清单与 Q3 剪枝条件判读。
- 前 N 轮 clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-BL-R3 修复确认 + 重入/重试语义 + 终止/frontier 推进保真; 其余面不审。
