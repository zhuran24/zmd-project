# 终末地 IndustrialPlanner 精确求解器 — parallel scheduler 面 round 6 (真 Pro 确认轮·F-PS-R5-01 修复验证 + 同型残留猎取)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_b4041f3e.zip`, sha256 `b4041f3eb065e9756a1dbd21f3e513479dfd504e2024b74fb08a2d235af08893`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD `8c61e1e`)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

**本包变化**: `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **多进程 parallel scheduler 波次调度与 worker 结果合并** (`src/search/exact_parallel_scheduler.py` 为核, 配 `src/search/outer_search.py` 的 wave 合并块 / frontier 重建 / 终局判据)。**campaign 持久化 / resume 状态机是 face 7 单独审, 本轮不审。**

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = **并行调度/合并 soundness**: ① worker 结果合并身份绑定 (不把「从未派发候选」或「畸形波次」的结果写进 campaign records); ② 合并失败的完备性闸 (fail-closed 不绕过终局 CERTIFIED); ③ 并行下状态聚合 + 跨波/跨 respawn 候选不丢不串不重。历史:
- r1 = F78-F-02 (HIGH, `results_by_seq` 只认 dispatch_seq 不校验候选身份 → 可注入「从未派发」结果)。r2/r3 = 零 (thinking 饱和下沿)。
- r4 = F-PS-R4-01 (HIGH, result-validation failure 后 `results_by_seq` 未清空 → 畸形波次的合法同伴 CERTIFIED 泄漏进 campaign), 已修。
- **r5 = 真 Pro 确认轮重审 r4 修复, 抓 F-PS-R5-01 (HIGH), 已修, 本轮来确认**:
  - **F-PS-R5-01** = r4 的 discard latch **非全路径 sticky** + consumer 白名单 **裸 `startswith` 前缀碰撞**, 两者叠加, 畸形 wave 仍能落地身份看似合法的同伴结果。三条具体缝:
    - (i) crash drain 中 `_record_worker_result()` 返回 validation failure 后虽 `results_by_seq.clear()`, 但**同一 drain 循环继续处理后续 RESULT 消息可重填**;
    - (ii) 主循环收到**非 WorkerResult** 时只设 `failure_reason="worker_result_invalid"` 并 break, **未置 discard latch、未清 results**, 尾部 drain 继续累积;
    - (iii) `WorkerResult.error` 原样作 `failure_reason` 返回, 可冒名 `worker_process_failed*` / `worker_crash_respawn_limit*` 前缀; consumer `_parallel_wave_failure_discards_results()` 裸 `startswith` 把 `worker_process_failed_validation_failure:*` 这类**该弃**的 reason 误判为「不弃」→ 身份合法的 CERTIFIED 落进 campaign。
  - **修复 (本包已含)**:
    - `exact_parallel_scheduler.py` `_record_worker_result()` (~:121): `result.error` reason 改为 `worker_result_error:{dispatch_seq}:{error}` 命名空间隔离, 不再裸透传进白名单前缀域;
    - crash drain (~:493): `discard_results_due_to_worker_result_failure` 置位后 `continue` 跳过后续 RESULT;
    - 主循环非 WorkerResult 分支 (~:543): 同步置 discard latch + `results_by_seq.clear()`;
    - return 前最终 guard (~:594): latch 为真再 clear 一次;
    - consumer `_parallel_wave_failure_discards_results()` (`outer_search.py:~161`): 白名单从裸 `startswith(prefix)` 收紧为 `reason == prefix or reason.startswith(prefix + ":")`, 拒绝前缀碰撞。

**本轮 r6 = 真 Pro 确认轮。姿态:** **不重报已修的 F-PS-R5-01 / F-PS-R4-01 / F78-F-02 本身**; 任务 = ① 独立判定 R5 两侧修复是否**真覆盖所有泄漏路径** (三条缝是否各自闭合、有没有第四条同型缝); ② 把修复点当攻击面找**同类残留**; ③ 确认修复**没有反向**误弃合法 CERTIFIED (availability) 或破坏 frontier 完备性闸。包内带其它面同期修复, 别重报。

## 审查重点 (行号基于本包, 以符号名为准)

### Q1 [验 discard latch 全路径 sticky, 最高优先 false-CERTIFIED]
`run_wave` 三段消费 (主循环正常 get / crash drain / 尾部 nowait drain) 现都应满足「任一 validation failure → 置 latch + 清 results, 此后同段及后续段不再重填」。请逐路径独立验:
- (a) crash drain 修复 (`continue` 跳过后续 RESULT): 确认 latch 置位后该 drain 循环**不再有任何分支**重新 `_record_worker_result()` 或重填 `results_by_seq`; heartbeat 仍收但不影响 results。
- (b) 主循环非 WorkerResult 分支: 确认 `discard latch=True` + `clear()` + `break` 三者齐, 且 break 后到 return 之间无路径重填。
- (c) 尾部 nowait drain: latch 置位后跳过后续 RESULT; 若尾部**自身**首次发现 validation failure, 是否也置 latch + clear?
- (d) **最终 guard 的充分性**: return 前 `if latch: clear()` 是否真能兜住所有未来重填? 还是只兜了已知三缝、仍存在某条「set failure_reason 但既没置 latch 也没被 guard 覆盖」的路径 (例如某个 `failure_reason =` 赋值点没有配套 latch 置位)? 请枚举 `exact_parallel_scheduler.py` 内**所有** `failure_reason =` / `discard_results_due_to_worker_result_failure =` 赋值点, 核对二者是否一一对应闭合。

### Q2 [验 consumer 白名单收紧后的前缀闭合 + 命名空间隔离]
- (a) 收紧后 `reason == prefix or reason.startswith(prefix + ":")` 是否**穷尽**了所有应「保留结果」的合法 reason、且**排除**了所有应「弃整波」的畸形 reason? 请枚举全仓 failure_reason 取值域 (scheduler 内所有赋值点 + `outer_search.py` 内 wrapper/respawn 路径如 `:~2472`) 核对前缀集闭合, 特别是有没有新的合法 reason 字符串既不等于前缀也不以 `prefix:` 开头而被误弃 (availability)。
- (b) `worker_result_error:{dispatch_seq}:{error}` 命名空间隔离: worker 内部 error 字符串现包在 `worker_result_error:` 前缀下。确认这层前缀**不可能**再被 consumer 判成「保留」(即 `worker_result_error:...worker_process_failed...` 这类嵌套不会因 consumer 逻辑被误放行); 反向确认它一定落进「弃」分支。

### Q3 [**r6 核心怀疑点**: consumer 第二道身份防线对 proof_summary / exact_safe_cuts 的类型校验缺口]
r5 review 的 Q2 判读自陈: consumer 合并前的第二道防线 `_parallel_wave_result_identity_failure()` (`outer_search.py`) 校验 dispatch_seq 唯一且已派发 / attempt_index / candidate tuple / candidate_key / status·solution·error 约束, 但**不复校验 `proof_summary` / `exact_safe_cuts` 字段类型**, 理由是「production scheduler 已在 `_record_worker_result()` 校验过」。请把这条**当攻击面独立证伪或坐实**:
- (a) 是否存在**任何**路径, 让一个 worker 结果**绕过** scheduler 的 `_record_worker_result()` 字段校验 (或该校验对 `proof_summary`/`exact_safe_cuts` 本就不完整), 而仍带着畸形/伪造的 `proof_summary` (例如 `master_status=CERTIFIED` 但内容不自洽) 或畸形 `exact_safe_cuts` 抵达 consumer 的 `mark_candidate_result()`, 被当 proof-bearing 落进 campaign? 注意: persisted `exact_safe_cuts` 按 lock 是 telemetry 非 proof, 但 `proof_summary` 的 `master_status` 是否在下游被读作终局判据?
- (b) `_record_worker_result()` 对 `proof_summary` / `exact_safe_cuts` 究竟校验到什么程度 (类型? 键? 值自洽?)? 若只校验存在性/类型而不校验自洽, consumer 又完全不复验, 那么「scheduler 已校验」这个完备性论证是否**真成立**, 还是又一个 r5 Q2 式的「数据流入口唯一 ≠ 语义消费点唯一」缝? 这正是本面要找的同型下一个。
- (c) 若结论是「确实有缺口」→ 给出 file:line + 可复现 probe + 修法 (consumer 加一道 proof_summary/exact_safe_cuts 类型·自洽复校, 或证明 scheduler 校验已充分故 consumer 复校仅冗余)。若结论是「无缺口, 冗余即可」→ 明确论证 scheduler 校验对这两字段的覆盖足以兜住所有 production 路径。

### Q4 [完备性闸 + 不误弃 + 同型第四实例]
- (a) 畸形 wave 修后 → `sorted_wave_results=()` → `effective_wave_completed=False` → `mark_campaign_stopped(UNKNOWN)`; 已 `mark_candidate_started=RUNNING` 的候选留在 frontier `potential_domain`, 终局 CERTIFIED/INFEASIBLE 只在 domain 耗尽时触发 → 畸形 wave 绝不靠 stale result 绕过终局。请独立复核此链未被 R5 修复破坏。
- (b) **反向误弃**: 一个完全合法、全 CERTIFIED 的波次, 会不会因 R5 收紧 (latch 过粘 / 白名单过窄) 被整波误弃 → 合法 certified 进度丢失 (availability, 非 soundness, 但请明确标注严重度)。
- (c) F78-F-02 / F-PS-R4-01 / F-PS-R5-01 是同一家族「畸形/未校验结果流进 campaign records」的三个实例。请猎取**第四个**: 全仓还有没有别的路径让未通过身份/有效性校验的 worker 或 precheck 结果经 `mark_candidate_result` / prune_fill / coordinator merge 落进 campaign 强记录? 重点核合并块对 `wave_candidate_results_by_key` 的填充、precheck elimination 与 worker 结果的 candidate_key 匹配 (`matching_solve_entry`)、prune_fill 兜底对 None match 的处理。

## 明确不要报的

- **F-PS-R5-01 / F-PS-R4-01 / F78-F-02 本身已修, 重复报不算**; 只报修复**不完备 / 同型残留 / 反向缺陷**。
- 已修条款: F78-F-02 + F-PS-R4-01 + F-PS-R5-01 (lock:93 区)、F-BIND-R5-01 (lock:103 worker artifact-hash 封印); Accepted invariant (lock:91 coordinator-only writer + 不相交候选波次)。
- **跨面边界**: ① campaign/resume 状态机本体 (持久化原子性 / resume 一致性 / 强状态单调 `mark_candidate_result`) 是 **face 7 单独审, 本轮不审**; 怀疑「并行下 worker CERTIFIED 覆盖已有强记录」时真正防线在 face 7 `exact_campaign.py` 的强→弱阻断, 交叉引述而非在本面重证。② worker 进程内 Benders/cuts/binding/几何 正确性属各自面。③ 终局 full-frontier evidence 重放属 `certified_frontier.py` (face 7/终局证据线)。
- 设计决策 (canonical / 266 口径 / `min_side>=6` admissibility, owner 已定); master/routing/cuts/preprocess/benders/binding/campaign 各面。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3058, HEAD 8c61e1e; 数目以实跑为准, 硬不变量 0 failed)。跑不完就跑 parallel/scheduler 专项 (`test_parallel*` / `test_exact_parallel*` / `test_outer_search*`) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 契约: `PROJECT_LOCK.md:91,93` (coordinator-only / F78-F-02 含 F-PS-R4-01 + F-PS-R5-01)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附四段判读: ① discard latch 全路径 sticky + 赋值点闭合 (Q1) / ② consumer 白名单前缀闭合 + 命名空间隔离 (Q2) / ③ **consumer 对 proof_summary/exact_safe_cuts 类型复校缺口的证伪或坐实 (Q3, 本轮核心)** / ④ 完备性闸 + 无误弃 + 同型第四实例猎取结论 (Q4)。
- 真 Pro 确认轮; 前轮修复点是攻击面起点, 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-PS-R5-01 两侧修复 soundness + Q3 consumer proof 字段复校缺口 + 同型残留 + 无误弃的真 Pro 确认; campaign/resume (face 7) 与其余面不审。
