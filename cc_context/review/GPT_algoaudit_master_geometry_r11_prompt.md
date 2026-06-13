# 终末地 IndustrialPlanner 精确求解器 — 几何 master 面 round 11 (真 Pro 重审·几何编码 soundness 全面复核)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_5e5e0c86.zip`, sha256 `5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **几何 master** (`src/models/exact_coordinate_master.py` 为核, 配 `src/models/pose_bool_exact_master.py` / `src/models/master_model.py` 的几何约束编码)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = 几何 master 的放置约束编码: footprint no-overlap / ghost 矩形 / 电力覆盖 witness / mandatory 装配 / optional·residual 基数不等式 / 对称破缺 / solve 解回读。历史:
- r2 = F-GM-Q3-01 (protocol storage 下界只数 residual optional 槽、忽略 fixed required → 合法配置编成 `0>=1` false-INFEASIBLE);
- r3 = F-GM-Q3-01-R3-A (对偶残缝: `0<fixed<lower` 时 residual 池被「有 fixed 就跳过」旧逻辑砍掉, shortfall 无 literal 可补);
- r4 = F-GM-Q3-01-R4-A (fixed pole 只占格不承担电杆语义, 不入 family/count/coverage witness);
- r5 = F-GM-Q3-01-R5-A (power family 映射为空时 fixed pole 被 `0==1` 判死);
- r6 = F-GM-R6-01 (cut 成功后只清 `_last_solution`, 旧 `_solver/_status` 仍在 → `extract_solution()` 从旧 CpSolver 重建刚被 cut 禁止的解 = stale witness);
- r7 = 零 soundness + LOW hint;
- r8 = F-GM-R8-SYM-01 (双标尺对称破缺: `order_key` 与 `signature` 两把不同 total order, pose 对在一个 key 上升另一个下降时整个可行等价类被删空 → false-INFEASIBLE);
- r9 = 零 + LOW; r10 = 零 (饱和下沿连零 2)。

**本轮 r11 = 真 Pro 重审。关键背景, 决定本轮姿态:**
**此前本面全部轮次 (r2-r10) 都是较弱的 GPT thinking 模型审的; 本轮起切到 GPT Pro 扩展模式 (真深度推理)。** 同期真 Pro 一切到其它面就抓出 thinking 漏了多轮的真 finding: cuts (CUT-R12-H1 / CUT-R13-H1, thinking 审 11+ 轮没发现)、preprocess (F-PRE-R15-01 / R16-01 / R16-02)、Benders/LBBD (F-BL-R7-01, thinking r3-r7 漏了 routing precheck 消费点)。**所以本面绝不能因为「thinking 连零 2 达饱和下沿」就默认干净 —— 请把几何 master 当作一个从未被深度审过的面, 用你最独立、最对抗的判断, 重走一遍几何编码 soundness。前轮 clean 不构成任何先验。**

注意: 包内带其它面同期落的修复 (cuts / preprocess / benders / binding / routing 条款), 各面有自己的线, **别在本轮重报**。

## 审查重点 (几何编码 soundness, 按优先级)

### Q1 几何约束编码忠实度 (有无 stricter-than-rule 的 false-INFEASIBLE)

master 把规则编成 CP-SAT 约束。任何比规则**更严**的约束 = 把合法布局判死 (false-INFEASIBLE, 会漏掉真最大矩形); 任何比规则**更松**的约束 = 把非法布局放过 (false-FEASIBLE, 更危险)。请独立审:

① footprint 从 `occupied_cells` 推导的 no-overlap bbox: 是否 over-approximate (保守, 非矩形 footprint 用 bbox 包住 = 安全方向) 而**不** under-approximate (漏挡 = false-FEASIBLE)? mode-channel footprint 在各 orientation/port_mode 下是否正确?
② ghost 矩形编码: anchor 枚举域是否完整 (`range(grid-w+1)` 无裁剪、越界 fail-closed)? ghost「空」的口径是否 = **body-only** (设施 body + pole body, **不含** connector/belt/coverage cells)? `AddNoOverlap2D` 是否只收 body interval + ghost? **有没有暗藏的 exterior-path / connectivity 约束 (这是禁区, 若存在即 finding)**?
③ 半开坐标域 off-by-one: 贴边 anchor 合法、越界非法的边界是否精确?
④ `max_lex(area, min_side)` 目标是否**没有** CP-SAT 加权目标 (frontier 在外层按 tuple 比较, master 只判固定 (w,h) 的可行性)? `min_side>=6` 是 admissibility 不是 tie-break?

### Q2 optional / residual 基数不等式族 (F-GM-Q3-01 系列核心, 真 Pro 主攻)

这是本面历史 finding 最密集处 (r2/r3-A/r4-A/r5-A 全在此, 全是 false-INFEASIBLE)。请独立深挖:

① protocol storage 下界约束: fixed required + residual optional 混合时, 下界是否正确编码 (`residual_active >= max(0, lower - fixed_required_count)`, 既不漏 fixed 也不双花 residual upper)? `0<fixed<lower` 的 shortfall 是否有 residual literal 可补 (R3-A 缝)?
② power pole family: fixed pole 是否承担**完整**电杆语义 (family membership / count 上界 / coverage witness 枚举全部用 materialized slots, 而非只 residual)? family 映射为空 / tuple 表异常空时, 是否正确处理 (**不**用 `0==1` 判死合法纯几何固定杆配置, R4-A/R5-A 缝)?
③ mandatory exactly-one → slot 装配是否正确 (266 实例精确, 无多收非法 tuple)?
④ 所有 optional 基数不等式 (area 必要条件 / ceil lower / family capacity) 是否**全部**是规则蕴含的有效不等式 (无启发式 stricter-than-rule)?
⑤ pool=0 退化 / `upper<fixed` 边界: 逐 cell 判读是真 INFEASIBLE 还是 false?

### Q3 对称破缺保代表性 + solve 派生字段 (F-GM-R8-SYM / R6 类)

① 对称破缺 (`order_key` / `signature` / power family 复合排序): 是否**保代表性** (绝不删任何可行等价类)? F-GM-R8-SYM-01 揭示双标尺 (两把 total order) 会删空等价类 —— 现在 signature 单调是否**只在全候选集 signature 按 order_key 非降时才加** (同序门卫)? 门卫量化范围是否 == slot 实际域 (allowed_tuples 反查)?
② cut 后 solver 派生字段清理: cut 成功后 `_solver` / `_status` / `_last_solution` 是否**同清** (否则 `extract_solution()` / `extract_bound_state()` 从旧 CpSolver assignment 重建刚被 cut 禁止的解 = stale witness)? exact + legacy 双路径是否都清?
③ hint 永不约束: malformed hint (非 int / 越界 pose / 不存在 anchor) 是否降级 skip 而非进入可行域? hint 只写 `solution_hint` proto 不加约束?

## 明确不要报的

- 设计决策 (canonical / 266 口径 / omni_wireless / 52-Port 不变量 / `min_side>=6` admissibility, owner 已定); r2-r10 已修 finding 与已审结论 (重复报不算)。
- preprocess / cuts / benders / binding / routing / campaign / scheduler 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory **行为/性能**不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- **ghost 不含 exterior-path 要求是 owner 已定的禁区, 别建议加**。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **≈3037 passed, 0 failed** (本包基点; 包基点之后仓库又落了 cuts/preprocess/benders 其它面修复 +5 测试 [现仓库 3042], 都不在本面几何 master 主体, 本面主体文件与包一致)。跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读: Q1 几何约束忠实度逐项 (footprint/ghost/坐标域/目标) / Q2 基数不等式族×规则蕴含矩阵 (每条约束的规则依据 + 混合 fixed/residual 判读) / Q3 对称破缺保代表性 + cut 后 witness 清理判读。
- 真 Pro 首轮重审, 前轮 thinking 连零不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 几何编码 soundness 三块 (约束忠实度 / optional·residual 基数不等式族 / 对称破缺保代表性 + solve witness 清理) 的真 Pro 复核; 其余面不审。
