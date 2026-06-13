# 终末地 IndustrialPlanner 精确求解器 — parallel scheduler 面 round 5 (真 Pro 确认轮·F-PS-R4-01 修复验证 + 同型残留猎取)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_1e136b90.zip`, sha256 `1e136b90a290684874398ce5f2ddaceac156481d2178fa1333db9ba14b8e16f2`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD 26e4543)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

**本包变化**: `data/preprocessed/candidate_placements.json` (45,773,799 bytes, sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) **已随包, 已校验**, 无需再生。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **多进程 parallel scheduler 波次调度与 worker 结果合并** (`src/search/exact_parallel_scheduler.py` 为核, 配 `src/search/outer_search.py` 的 wave 合并块 / frontier 重建 / 终局判据)。**campaign 持久化 / resume 状态机是 face 7 单独审, 本轮不审。**

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = **并行调度/合并 soundness**: ① worker 结果合并身份绑定 (不把「从未派发候选」或「畸形波次」的结果写进 campaign records); ② 合并失败的完备性闸 (fail-closed 不绕过终局 CERTIFIED); ③ 并行下状态聚合 + 跨波/跨 respawn 候选不丢不串不重。历史:
- r1 = F78-F-02 (HIGH, `results_by_seq` 只认 dispatch_seq 不校验候选身份 → 可注入「从未派发」结果); r2/r3 = 零 (thinking 饱和下沿)。
- **r4 = 真 Pro 首轮重审, 抓 F-PS-R4-01 (HIGH), 已修, 本轮来确认**:
  - **F-PS-R4-01** = scheduler 侧 result-validation failure 后 `results_by_seq` **未清空**; 畸形波次 (duplicate_dispatch_seq / 身份不匹配 / errored 等被 `_record_worker_result` 拒的结果) 触发 failure_reason 后, 已累积的合法同伴结果 (含 CERTIFIED) 仍残留在 `results_by_seq`, 经 consumer prune_fill 兜底**泄漏进 campaign candidate records** → 违反 F78-F-02「畸形波次全弃」语义 (false-CERTIFIED 方向)。
  - 修复两侧: **scheduler 侧** 引入 `discard_results_due_to_worker_result_failure` 闸 (`exact_parallel_scheduler.py:477`), 任一 `_record_worker_result` 返回 reason (`:507,:511,:554,:582,:587`) 即 `results_by_seq.clear()`, 尾部 drain 在闸置位后 `continue` 不再累积 (`:569-570`); **consumer 侧** 新增白名单 `_parallel_wave_failure_discards_results` (`outer_search.py:161-169`), 仅 `worker_process_failed` / `worker_crash_respawn_limit` 前缀返回 False (干净中止, 无结果落地不需弃), 其余 failure_reason 一律 True (畸形 → 弃整波结果), 用于 `:2307` 合并判读。

**本轮 r5 = 真 Pro 确认轮。姿态:** **不重报已修的 F-PS-R4-01 本身**; 任务 = ① 独立判定两侧修复是否**真覆盖所有泄漏路径**; ② 把修复点当攻击面找**同类残留** (还有没有别的 validation-failure 路径让 stale CERTIFIED 流进 campaign / 还有没有别的 failure_reason 该弃却没弃); ③ 确认修复**没有反向**误弃合法 CERTIFIED (availability) 或破坏 frontier 完备性闸。包内带其它面同期修复, 别重报。

## 审查重点 (行号基于本包 exact_parallel_scheduler.py / outer_search.py)

### Q1 [验 scheduler 侧 clear 完备性, 最高优先 false-CERTIFIED]
`run_wave` 三段消费: 主循环正常 get (`:534-555`)、crash drain (`:490-512`)、尾部 nowait drain (`:557-587`)。请逐路径独立验:
- (a) **每条 set failure_reason 的路径是否都清了 results 或保证无残留**: `:507/511`(crash drain)、`:554`(主循环 break 前)、`:582/587`(尾部 drain) 都 clear; 但 `:543-544` 主循环 `worker_result_invalid` 直接 `break` **未显式 clear** —— 此时 `discard_...=False`, 后续尾部 drain (`:569`) 因闸未置位仍会 `_record_worker_result` 累积, 而 `sorted_results` (`:594-595`) 从 `results_by_seq` 取 → 这条路径的残留结果是否会泄漏? 请深挖 `:543` break 后到 `:589` 之间 results_by_seq 的状态 (这是 r4 修复可能漏的同型缝, 重点查)。
- (b) crash drain `:508-511` 的 `else`(非 WorkerResult)分支 clear 了, 但 `:512 if failure_reason is not None: break` 之后, `results_by_seq` 已 clear — 确认 break 退出后不会有路径重填残留。
- (c) `_record_worker_result` (`:107-137`) 返回 reason 的全部条件 (重复 seq / 身份不匹配 / errored) 是否都被三段消费正确接住并触发 clear。

### Q2 [验 consumer 白名单 soundness + 前缀碰撞同型]
`_parallel_wave_failure_discards_results` (`outer_search.py:161-169`) 用 `startswith` 判定: `worker_process_failed` / `worker_crash_respawn_limit` → False (不弃), 其余 → True (弃)。请独立验:
- (a) **False 分支的正确性**: 这两个 reason 对应「worker 进程级失败 / crash 超限」, 声称此时**无 worker 结果落地** (干净中止, RUNNING 候选靠 frontier 重建保留) 故不需弃。请核实: 走到这两个 reason 时, `results_by_seq` 是否**确实为空或已被 scheduler 清** (`:518-526` worker_crash_respawn_limit 在 `break` 前没 clear results — 但此前是否可能已有合法结果累积? 若有, scheduler 侧 `completed=False` 但 results 非空, consumer 又判「不弃」→ 这些结果会被怎么处理? 是否泄漏?)。这是 Q1(a) 的对偶, 请交叉验。
- (b) **前缀碰撞 (同型攻击)**: `startswith("worker_process_failed")` — 是否存在某个**应该弃**的 failure_reason 字符串恰好以这两个前缀开头而被误判为「不弃」? 反向: 某个应「不弃」的 reason 没匹配上前缀被误弃 (availability)。请枚举全仓所有 failure_reason 赋值点 (`exact_parallel_scheduler.py` 内 `failure_reason =` + `outer_search.py:2472` 等) 核对前缀集闭合。
- (c) consumer 合并块 (`:2300` 一带) 是否**独立**复核身份, 还是完全信任 scheduler 的 discard? 若 scheduler clear 有漏 (Q1a), consumer 是否有第二道防线?

### Q3 [完备性闸 + 不误弃]
修复后畸形波次 → 弃整波结果 → `effective_wave_completed=False` → `mark_campaign_stopped(..., UNKNOWN)`。请验: ① 被弃波次的候选 (已 mark_candidate_started=RUNNING) 是否正确保留在 frontier `potential_domain`, 终局 CERTIFIED 闸只在 potential_domain 空时触发 → 畸形波次绝不绕过终局 (false-FEASIBLE/INFEASIBLE 都不会)? ② 修复是否**反向误弃**: 一个完全合法、全 CERTIFIED 的波次, 会不会因某非畸形原因 (如正常 worker_process_failed 与合法结果共存) 被整波弃掉 → 合法 certified 进度丢失 (这是 availability 损失, 非 soundness, 但请明确标注严重度)。

### Q4 [同型残留: 其它 validation-failure→campaign 泄漏路径]
F78-F-02 (身份绑定) + F-PS-R4-01 (validation-failure 残留) 是同一家族「畸形/未派发结果流进 campaign records」的两个实例。请猎取**第三个**: 全仓还有没有别的路径, 让一个未通过身份/有效性校验的 worker 结果 (或 precheck 结果) 经由 `mark_candidate_result` / prune_fill / coordinator merge 落进 campaign 强记录? 重点核 `:2300-2317` 合并块对 `wave_candidate_results_by_key` 的填充、precheck elimination 与 worker 结果的 candidate_key 匹配 (`matching_solve_entry`)、以及 `:2317` prune_fill 兜底对 None match 的处理。

## 明确不要报的

- **F-PS-R4-01 / F78-F-02 本身已修, 重复报不算** (lock:93 区已补强); 只报修复**不完备 / 同型残留 / 反向缺陷**。
- 已修条款: F78-F-02 (lock:93)、F-BIND-R5-01 (lock:103 worker artifact-hash 封印); Accepted invariant (lock:91 coordinator-only writer + 不相交候选波次)。r2/r3 已审结论 (task_fingerprint 纵深属可选加固; 双 coordinator 判运维风险; worker result 队列丢失→checkpoint RUNNING 重跑不丢)。
- **跨面边界**: ① **campaign/resume 状态机本体 (持久化原子性、resume 一致性、强状态单调 mark_candidate_result) 是 face 7 单独审, 本轮不审**; 怀疑「并行下 worker CERTIFIED 覆盖已有强记录」时真正防线在 face 7 `exact_campaign.py` 的强→弱阻断, 交叉引述而非在本面重证。② worker 进程内 Benders/cuts/binding/几何 正确性属各自面。③ 终局 full-frontier evidence 重放属 certified_frontier.py (face 7/终局证据线)。
- 设计决策 (canonical / 266 口径 / `min_side>=6` admissibility, owner 已定); master/routing/cuts/preprocess/benders/binding/campaign 各面。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- candidate 已随包, 全量 `python -m pytest -q src/tests` 应 **0 failed** (passed ≈3050, HEAD 26e4543; 数目以实跑为准, 硬不变量 0 failed)。跑不完就跑 parallel/scheduler 专项 (`test_parallel*` / `test_exact_parallel*`) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 契约: `PROJECT_LOCK.md:91,93` (coordinator-only / F78-F-02 含 F-PS-R4-01)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读: ① scheduler 侧 clear 完备性 (Q1, 含 `:543` break 路径) / ② consumer 白名单 + 前缀碰撞 (Q2) / ③ 完备性闸 + 同型第三实例猎取结论 (Q3/Q4)。
- 真 Pro 确认轮; 前轮修复点是攻击面起点, 按你自己的独立判断下结论。

## 范围边界

- 重点 = F-PS-R4-01 两侧修复 soundness + 同型残留 + 无误弃的真 Pro 确认; campaign/resume (face 7) 与其余面不审。
