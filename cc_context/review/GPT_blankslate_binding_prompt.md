# 终末地 IndustrialPlanner 精确求解器 — 端口绑定子问题面 · 独立全面 soundness 审查 (零先验白板)

## 任务性质 (新会话, 完全独立, 零历史先验)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_8a44d536.zip`, sha256 `8a44d5368d6fa57959769874588fccad0744345d94a0f277a82f3a85037f8c1b`, 对应干净 git 树 HEAD `6be75f5`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告, 不要在错包上工作**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

`data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) 已随包内置并校验, 不需要再生; 若校验对不上, 报告, 不要伪造或重写它。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 本次审查 (关键, 必读)

**这是一次完全独立、零先验的全面 soundness 审查。** 你**不知道、也不需要知道**这个项目或这个面之前任何轮次发现过什么、修过什么、哪里被认为安全。**没有任何"上一轮修复"要你确认, 没有任何预设攻击线, 没有任何"已经查过别再看"的清单。** 从零开始, **由你自己判断这个面最该攻哪**。

**本面 = 端口绑定子问题 (port binding / generic IO / wireless sink)** (`src/models/binding_subproblem.py` 为核)。

**唯一目标**: 找出任何能让 certified 求解器在 **canonical 数据 + 默认 env (无 `EXACT_*` 实验旋钮)** 下产生 **false-CERTIFIED** 的缺陷 —— 即:把非证明状态(预算耗尽/异常/非三态 status)误译成 INFEASIBLE 证明、铸出删除合法解的 master nogood、或任何路径输出 CERTIFIED 而其证明前提不成立。这是唯一会动摇求解器可信度的一类问题。

你怎么找、从哪个不变量切入、用什么对抗角度, **完全由你决定**。建议(非限制)从这些 soundness 不变量自检:status 契约完整性(每个消费 subproblem 返回值的分支, 非预期 status 是否 fail-closed 到 UNKNOWN 而非误读成 INFEASIBLE/CERTIFIED)、cut/缓存跨 iteration·跨 candidate 的有效性与单调性、proof-bearing 证据 vs telemetry-only 的区分、时间预算全出口终态、几何/容量/连通性证据的回写忠实性。但**不要被这个清单框住** —— 你认为更该攻的角度优先。

## 范围 (owner 已定的边界, 仅此而已)

- **只审 default-env certified 路径** —— production 168h 大跑跑的就是这条。**env-gated 实验旋钮**(`EXACT_USE_POSE_BOOL_MASTER` / `EXACT_POWER_PLACEMENT_SUBPROBLEM` / `EXACT_B1_*` 等)**不在本次范围**(它们被 production readiness gate 物理拦在生产路径之外)。若你顺手发现 env-gated 路径的 soundness 缝, 可附注但明确标 env-gated, 它不影响本次结论。
- **只审本面** (`src/models/binding_subproblem.py`)。怀疑跨面缺陷时, **交叉引述 `PROJECT_LOCK.md` 契约条款**而非在本轮重证其它面内部正确性。主循环对 binding status 的消费属 benders 面; 只审 binding 子问题自身编码/加载的 soundness。
- 设计决策不审 (owner 已定): canonical 口径 / 266 强制设施 / `min_side >= 6` 是 admissibility 不是 tie-break / omni_wireless / 52-Port 不变量。
- preflight `phase_1_2_spike_close` BLOCKED 是 owner gate 不是 bug; P1.3B `step_8_apply_to_master` 是未集成边界不报; `_codex_archive/` 只读历史参考。

## 自验环境与基线 (硬不变量 = 0 failed)

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed**。沙盒 pytest-randomly 报 seed 错就加 `-p no:randomly`。跑不完全量就跑专项并**如实声明**没跑全量。
- finding **必须**带可复现 probe (monkeypatch 构造能触发的输入, 断言 fail-open 终态) 或 file:line 严谨论证; **实证推翻你的怀疑就不要报** (宁可少报一条假阳, 不拿"理论上可能"凑数)。

## 交付物 (REVIEW.md)

- 逐条 finding: severity / file:line / 可复现 probe 或严谨论证 / 修法 (有把握附 unified diff + regression, **LF 行尾**, 不重写 candidate 工件)。**false-CERTIFIED on canonical+默认 env = 你唯一要全力找的那类。**
- 若你独立判断本面 sound: **明确写"本轮零 soundness finding"**, 并给出**你自己**的全面判读 —— 你扫了哪些 soundness 不变量、为什么每条都站得住。**不要复述或确认任何外部给你的分析(本提示词没有给你任何预设结论);结论必须是你自己从代码得出的。**
