# 终末地 IndustrialPlanner 精确求解器 — Benders/LBBD 主循环面 round 7 (真 Pro 重审·LBBD soundness 三支柱全面复核)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_5e5e0c86.zip`, sha256 `5e5e0c863fba4247158c55108eb8bdf4d29e872660312e0f61a1a8cb15029b4a`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD: master 放置 → binding 端口绑定 → routing 网格布线 → flow 诊断)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **Benders/LBBD 主循环** (`src/search/benders_loop.py` 为核)。

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面历史 (报告在包内 `cc_context/review/` 与 `archive/`):
- r3 = F-BL-R3-01 (预算耗尽误当穷尽证明铸 nogood) + F-BL-R3-02 (routing 非三态 status 落 INFEASIBLE 分支);
- r4 = F-BL-R4-01 (binding 状态契约同型缝五消费点, `_record_unexpected_binding_status()` 统一 fail-closed);
- r5 = 零 soundness + LOW F-BL-R5-PS-01 (env 门控 power placement forensic 分支非契约 status×summary 错配, 完整性非 soundness);
- r6 + 涟漪确认轮 = 零 soundness finding。

**本轮 r7 = 真 Pro 重审。关键背景, 决定本轮姿态:**
**此前本面全部轮次 (r3-r6 + 确认轮) 都是较弱的 GPT thinking 模型审的; 本轮起切到 GPT Pro 扩展模式 (真深度推理)。** 同期真 Pro 一切到其它面就抓出 thinking 漏了多轮的 HIGH: cuts 面 CUT-R12-H1 (power-conditioned infeasible cut 丢失 unpowered fixed-occupancy support, thinking 审 11 轮没发现, 真 Pro 第一轮就抓), preprocess 面 R14/R15 系列亦然。**所以本面绝不能因为"thinking 审过多轮零"就默认干净 —— 请把 Benders/LBBD 主循环当作一个从未被深度审过的面, 用你最独立、最对抗的判断, 重新把 LBBD 的 soundness 走一遍。前轮 clean 不构成任何先验。**

注意: 包内带其它面同期落的修复 (cuts CUT-R12-H1 / preprocess F-PRE-R15-01 / routing / master 几何 / binding / campaign 等条款), 这些面各有自己的线, **别在本轮重报**。

## 审查重点 (LBBD soundness 三支柱, 按优先级)

### Q1 master ↔ subproblem 接口的 status 契约完整性 (r3/r4 主题的真 Pro 复核)

LBBD 正确性第一道防线 = 每个 subproblem 返回的 status 被 master 正确解读, 任何「非预期 / 非三态 / 预算耗尽 / 异常」status 必须 fail-closed 到 UNKNOWN, **绝不能**被误读成 INFEASIBLE (→ 误铸 nogood 删合法解) 或 CERTIFIED。请独立穷举 benders_loop 主循环里**每一个**消费 subproblem status 的分支 (master solve / binding solve+重解 / routing precheck / routing solve / flow 诊断 / 各 separator / 条件化 power witness):

① 每个消费点处理的 status 取值集合是否**完备** —— 有没有漏掉的 status 落进 `else`/默认分支被误分类? 有没有"成功路径假定 status∈{OPTIMAL,FEASIBLE}"但实际可能返回别的值的地方?
② 预算耗尽 / TIMEOUT / MODEL_INVALID / 异常 / 空解 / None, 是否**全部**收敛到 UNKNOWN/TIMEOUT 而非 INFEASIBLE?
③ r3 (预算耗尽 nogood)、r3 (routing 非三态)、r4 (binding 五消费点统一 fail-closed) 修的那几处, 修复是否**彻底** —— 有没有同型的第 N 个消费点 (尤其新加的 separator / power witness / PCR 路径) 漏网, 仍在用旧的"非预期即 INFEASIBLE"或裸 assert 写法?

### Q2 cut / 缓存的跨 iteration、跨 candidate 生命周期与单调性 (LBBD 核心, 真 Pro 主攻)

LBBD 正确性依赖「加进 master 的每个 cut 永远有效」。请独立审:

① master 上累积的**每一类** cut (binding 穷举 whole-layout nogood / routing front_blocked ladder 各形态 / lazy connectivity cut / 条件化 power witness nogood / PCR-CUT signature-lifted nogood 等) 的有效性证明, 是否依赖「加 cut 那一刻」的瞬时状态 (binding model 内容 / routing 域 / 选中的 ghost anchor / iteration 计数 / 外置 domain)? **若依赖, 跨 iteration 复用、尤其跨 candidate 复用时, 该前提还成立吗** (cut 污染 = 直接 soundness 缝)? 逐类给出"有效性所依赖的前提 + 该前提在复用时是否被保持"的判读。
② cut 的 condition literals (ghost anchor 等) 解析失败时, 是 fail-closed 不加, 还是被降级成**无条件** cut (后者 = over-cut, 在不该禁的上下文里也禁 = 删合法解)?
③ 各类**缓存** (binding cache / subproblem reuse / shrink counters / 域分析缓存) 逐个判读 proof-bearing vs telemetry-only: 缓存命中返回的结果, 有没有可能是「不同前提下算出的旧解」被当成新前提的证明被消费 (= 把 telemetry 误当 proof)?
④ 终止 / 单调论证: 每个 cut 是否**严格**削减 master 解空间? 有没有「加了 cut 但 master 仍能返回同一解」的活锁路径 (完整性方向; 但若靠 iteration cap 兜底, cap 命中必须落 UNKNOWN, 与 F-BL-R3-01 一致, 不得当穷尽证明)?

### Q3 时间预算传递与全部耗尽出口的终态 (真 Pro 穷举)

certified 主链上每个 stage (master solve / binding solve+重解 / routing precheck / routing solve / guard / 每个 separator / power witness) 的时间预算:

① 预算从 campaign 层到各 stage 的传递链 —— 有没有 stage 用了**硬编码默认**而非传入预算 (导致超预算运行或过早截断)?
② **逐条**列出所有预算耗尽 / TIMEOUT 出口 (含 master / binding / routing precheck / routing / guard / 每个 separator / power witness), 判读是否**都**收敛到 UNKNOWN/TIMEOUT 而非 INFEASIBLE/CERTIFIED (r4 核过主干, 本轮请穷举包括 separator/guard/precheck 在内的全部 timeout 出口);
③ 时间测量本身: 用的是**单调时钟**吗? 预算检查点之间最长可能的「未检查窗口」是否有界 (一个 stage 内部无预算检查的死循环 = 挂死方向)?

## 明确不要报的

- 设计决策 (canonical/266 口径/omni_wireless/52-Port 不变量, owner 已定); r3-r6 已修 finding 与已审结论 (重复报不算)。
- preprocess / binding / master 几何 / campaign / scheduler / routing / cuts 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory **行为/性能**不审 (但 env 门控 cut 的 **soundness** 仍要审); persisted `exact_safe_cuts` 是 telemetry 非 proof (V82)。
- facility_pools pose dict 浅拷贝共享 (r5 已挂账保守备注, 当前无 mutation 路径)。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **全绿 (≈3037 passed, 0 failed)**; 跑不完就跑专项 + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三张清单: Q1 status 消费点逐点判读表 / Q2 cut 类型×有效性依据矩阵 (含跨 candidate 复用前提) / Q3 全部 timeout 出口终态清单。
- 真 Pro 首轮重审, 前轮 thinking clean 不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = LBBD soundness 三支柱 (status 契约完整性 / cut·缓存生命周期单调性 / 时间预算全出口终态) 的真 Pro 复核; 其余面不审。
