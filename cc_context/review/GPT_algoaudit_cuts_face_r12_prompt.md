# 终末地 IndustrialPlanner 精确求解器 — cuts 面 round 12 (再确认轮·cuts 面冲第三个连零 + 全通道独立再审)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_c9315ba2.zip`, sha256 `c9315ba216598e08ecb4103ca2563d7aabdecae11d48205803c17921fc4ead61`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **cuts 机制** (master 收紧用的全部 cut 通道: binding nogood / master placement nogood / deletion-core / lazy-demand / cell-pattern / lazy connectivity / D2 commodity-flow separator / PCR-CUT patch separator / whole-layout / power-conditioned)。

## 本面定义与历史: cuts, 收敛轨迹 r8 HIGH → r9 HIGH → r10 零 → r11 零, 本轮 = 第三个连零再确认轮

本面已审 11 轮 (报告全在包内 `cc_context/review/` 与 `cc_context/review/archive/`)。近况: r8 = CUT-R8-H1 (D2 separator over-cut, support-augmented 修); r9 = CUT-R9-H1 (D2 非 production relaxation, deny-unknown precheck gate 修); **r10 = 零 soundness (CUT-R9-H1 四点确认) + LOW CUT-R10-L1 (D2 port owner 校验加固)**; **r11 = 零 soundness (终饱和轮: CUT-R10-L1 确认 + 深挖 lazy connectivity / deletion-core / 跨通道 ladder 弱序全 sound + 抽查 PCR/cell-pattern/conditioned)**。**连零 2, 已达饱和下沿**。

**本轮 r12 = 第三个连零再确认轮**: owner 要在饱和下沿 (连零 2) 基础上再加一轮独立确认 (冲连零 3, 满足"3 连续独立全审零 finding"的闭合标准)。**前两轮 (r10/r11) clean 绝不代表本轮默认干净** —— 本面历史上多次出现确认轮自身从新角度抓出 HIGH (r8/r9 在 r7 clean 后接连爆 HIGH; r5 PCR 首审一次爆 4 HIGH)。请用**你自己最独立的判断**, 换一个 r10/r11 没用过的攻击角, 把整个 cut 机制再独立审一遍。

注意: 本包含其它审查面同期落的修复 (lock 末 F-PRE-R15-01 = preprocess public 入口重验等), 各面有自己的线, 别在本轮重报。

## 审查重点 (按优先级)

### Q1 前轮已确认点的轻复核 (不重复深挖, 只确认没被同期改动破坏)

r10 确认了 CUT-R9-H1 修复 (D2 deny-unknown precheck gate) + CUT-R10-L1 (D2 port owner 校验); r11 确认了 lazy connectivity / deletion-core / ladder 弱序。轻扫确认这些结论在本包仍成立, 同期 preprocess 修复 (F-PRE-R15-01) 没有触碰 cuts 通道。

### Q2 全通道独立再审 (本轮主体, 换新角度)

r11 已从「lazy connectivity / deletion-core / ladder 弱序」角度深挖。**本轮请换一组 r10/r11 覆盖最浅的角度**, 独立重新验证关键通道。天然候选 (非限定, 选你判断最可能藏缝的):
- **binding nogood 本体**: `extract_selection` / `__unused__` 槽语义 / nogood literal 集是否恰好等于被排除的不可行 binding 配置 (不多禁合法配置, 不漏禁)。
- **master placement nogood / whole-layout nogood**: 它们的「禁的集合 ≤ 能证明不可行的」是否严格成立; power witness 不完整时的 fail-closed; ghost 排除是否正确。
- **lazy-demand / cell-pattern cut 的 generic 容量饱和证明** (r2-r4 审过, 本轮独立重证 52=52 饱和逻辑 + `__unused__` 压成 0 的前提是否仍 sound)。
- **cut 在 LBBD 主循环的累积/重建/persisted replay 生命周期** (V82 telemetry-only 边界是否仍代码强制: certified 下 `raw_candidate_cuts=[]`)。

### Q3 自由攻击角

以上之外, 用你自己的独立判断选你认为本面最薄弱的点深挖。说明选点理由、攻击过程、结论。

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r2-r11 已修 finding 与已审结论 (重复报不算)。
- preprocess/binding/campaign/scheduler/routing/master-geometry 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审; persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- D2/PCR 剪枝变弱/重跑 precheck 的性能开销 (预期代价, 非 finding); readiness gate 的 `EXACT_B1_D2_COMMODITY_FLOW` blocker 待办 (C-4, 已挂账); F1-F9 `step_2`/`step_8` NotImplementedError (P1.3B 边界, 非缝)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3036 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 列 Q2 你选的通道独立再审结论 + 一句你对「cuts 面是否已达三连饱和」的独立判断。
- 前 11 轮 clean/已修不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = 第三个连零再确认轮, 换新角度全通道独立再审; 其余面不审。
