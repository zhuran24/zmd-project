# 终末地 IndustrialPlanner 精确求解器 — parallel scheduler 面 round 4 (真 Pro 重审·并行波次合并 soundness)

## 任务性质 (新会话零历史, 独立对抗审查)

项目快照包在本 Project **文件区 (来源/Sources)**: `zmd_snapshot_f4418b04.zip`, sha256 `f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1`。**只认这个文件名, 文件区其它快照包一律无视; 开工前先校验 sha256, 对不上停下来报告**。zip 内 `project/` 为仓库根 (ZIP_LZMA, `python -m zipfile -e <zip> .` 解包), 干净 git 树快照 (HEAD 2e1da65)。依赖 wheels 同在文件区 (`zmd_py313_linux_x86_64.zip`), 沙盒 Python 3.13, 离线安装。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。本面 = **多进程 parallel scheduler 波次调度与 worker 结果合并** (`src/search/exact_parallel_scheduler.py` 为核, 配 `src/search/outer_search.py` 的 wave 合并块 / frontier 重建 / 终局判据)。**campaign 持久化 / resume 状态机是 face 7 单独审, 本轮不审。**

## 本面定义与历史 + 本轮性质 (关键, 必读)

本面 = **并行调度/合并 soundness**, 不重新证明 LBBD 子问题正确性 (那是各面的事), 也不验 campaign 状态机本体 (face 7)。只校验: ① worker 结果合并身份绑定 (不把「从未派发候选」的结果写进 campaign records); ② 合并失败的完备性闸 (fail-closed 不绕过终局 CERTIFIED); ③ 并行下 UNKNOWN/CERTIFIED/INFEASIBLE 状态聚合 + 跨波/跨 respawn 的候选不丢不串不重。历史 (此前与 face 7 同包审, **finding 全部 thinking 模型所抓**):
- r1 = F78-F-02 (HIGH, false: `results_by_seq` 只认 dispatch_seq 不校验候选身份 (setdefault 先到先得), outer_search 对未匹配结果走 prune_fill 兜底照写 campaign → 队列边界可注入「从未派发的候选」结果);
- r2 = 零 finding (F-02 双侧复核三路径 [正常收割/crash drain/尾部 drain] 无旁路 + 队列/序列化边界穷举 8 类);
- r3 = 零 finding (崩溃时序/原子性角度: worker result 未消费队列丢失→checkpoint 仍 RUNNING wave→重跑不丢 soundness; 双 coordinator 判运维风险非 soundness, 连零 2 达饱和下沿)。

**本轮 r4 = 真 Pro 重审。关键背景, 决定本轮姿态:**
**此前本面全部轮次 (r1-r3) 都是较弱的 GPT thinking 模型审的; 本轮起切到 GPT Pro 扩展模式。** 同期真 Pro 一切到其它面就抓出 thinking 漏了多轮的真 finding: Benders (F-BL-R7-01)、cuts (CUT-R12-H1 / CUT-R13-H1, thinking 审 11+ 轮没发现)、preprocess (F-PRE-R15-01 / R16-01 / R16-02)、几何 master (F-GM-R11-PB-REQ-POLE-01 / STALE-01)。**所以本面绝不能因为「thinking 连零 2 达饱和」就默认干净 —— 请当作从未深审重走。前轮 clean 不构成任何先验。**

注意: 包内带其它面同期修复, 各面有自己的线, **别在本轮重报**。

## 审查重点 (并行调度/合并 soundness, 6 块, 行号基于本包 exact_parallel_scheduler.py / outer_search.py)

### Q1 [完备性主缝, 验真 fail-closed] 身份失败时整波清空 vs 终局闸
身份失败时 `sorted_wave_results` 清空 (`outer_search.py:2292-2295`) → 整波 worker 结果连同合法同伴一起丢弃, 但这些候选已 mark_candidate_started 成 RUNNING; `effective_wave_completed=False` 触发 `mark_campaign_stopped('worker_process_failed', UNKNOWN)` 并 return (`:2450-2461`)。请深挖: 这是否真能保证终局 CERTIFIED 不被绕过 —— 确认 RUNNING 候选在 frontier 重建 (`:626-676`) 保留在 potential_domain, 终局闸 (`:1848`) 只在 potential_domain 空时触发, 故合并缝是 false-FEASIBLE/INFEASIBLE 还是仅 availability 损失。重点核 `_frontier_skip_statuses` 默认只含 CERTIFIED/INFEASIBLE (`:653`)。

### Q2 [并行/串行语义漂移] 状态白名单不对称 UNPROVEN
scheduler `VALID_WORKER_RESULT_STATUSES (:21-23)` 与 consumer `_VALID_PARALLEL_WORKER_RESULT_STATUSES (outer_search.py:92-93)` 都含 UNPROVEN, 但 `_worker_entry` 实际只产 CERTIFIED/INFEASIBLE/UNKNOWN (benders 返回) 或 UNKNOWN (异常 `:314-329`) —— **UNPROVEN 永不被 worker 生成**。请确认: 是否存在路径让 worker 注入 UNPROVEN 经 `_terminal_stop_reason_for_status (:1665)` 走 candidate_returned_unproven 终局; consumer 合并块 (`:2357` {INFEASIBLE,UNKNOWN,UNPROVEN} 分支) 对 UNPROVEN 的 mark_candidate_result 语义是否与 sequential 路径一致 (避免并行/串行 declare 语义漂移)。

### Q3 [false-FEASIBLE 风险] crash respawn + 尾部 drain 时序
`run_wave` 在 `wave_crash_respawns<=2` 内 `_respawn_all_workers()` 后重投 pending (`:521-525`), respawn 重建 task_queue/result_queue (`:400-405`)。请深挖: respawn 丢弃旧 result_queue 时是否可能丢一个已 put 未 get 的合法 RESULT, 致该候选既未记录又被当 pending 重跑 (重跑安全) 还是被当已完成 (危险); 尾部 while drain (`:548-571`) 在 failure_reason 已置后仍继续 `_record_worker_result` 累积 —— 确认不会让迟到的 stale CERTIFIED 在 failure 波次悄悄进 results_by_seq 影响后续 (注意 `:2293` 已用 wave_identity_failure 清空, 但 `wave_execution.failure_reason` 路径未清 results)。

### Q4 [跨波身份隔离] epsilon/solve_mode/profile 不入身份四元组
WorkerResult 身份 (seq/attempt/candidate/candidate_key) 不含 epsilon_stage/solve_mode/master_search_profile (ledger 挂账纵深建议)。请确认当前 queue 生命周期 (每波新建 task, respawn 重建 queue) 下确无跨波/跨 respawn 的 task 残留漂移: 一个上一波 stale result 不可能 dispatch_seq 撞中本波任务而四元组仍匹配 (dispatch_seq 每波 enumerate 从 0 重排 `build_parallel_worker_tasks:161`, attempt_index 是 campaign 全局递增 `:2263-2265` —— 二者组合是否足以隔离跨波)。

### Q5 [候选漏分/重分] 波次 depth multiplier 超额分发
`limit=2*parallel_processes (:1195)` 使一波 task 数可超 worker 数, 经单 task_queue 串行 drain。请确认: 同一波内 `_append_parallel_wave_head` 多 selection_steps (objective/prune/anchor/prune_fill `:1250-1274`) 用 selected_keys 去重, 不把同一候选派两次 (dispatch_seq 撞 → tasks_by_seq 唯一性断言 `:468-469` raise); 跨波候选不因 frontier 未推进而重复消耗预算或漏掉 (核 potential_domain 是否每波后由 campaign records 重算而非增量维护, `:635`)。

### Q6 [合并去重串号] coordinator_precheck_results 与 worker 结果合并
合并块用 `wave_candidate_results_by_key` 以 candidate_key 为键 (`:2300-2303` 先填 precheck, `:2384` 再填 worker)。请确认 precheck 淘汰候选 (已 `_record_precheck_elimination` 标 INFEASIBLE) 与 solve_wave_entries 的 worker 结果在同一 candidate_key 上不冲突; `matching_solve_entry` 用线性 next() 按 candidate_key 匹配 (`:2304-2313`) —— 若同一波重复 candidate_key 是否错配 selection_reason/wave_slot_index (selected_keys 去重应防住, 但抽查 prune_fill 兜底 `:2317` 对 None match 处理是否真安全)。

## 明确不要报的

- 已修条款 (重复报不算): **F78-F-02** (lock:93, parallel wave 结果身份绑定: worker result 仅当 dispatch_seq/attempt_index/candidate/candidate_key 全匹配派发任务才被接受, 调度/消费双侧独立校验, 重复 seq/错配身份/errored 全弃, 畸形波次→worker_process_failed/UNKNOWN); **F-BIND-R5-01** (lock:103, worker artifact-hash 封印 + STARTUP_ERROR); Accepted invariant (lock:91, coordinator-only writer + 不相交候选波次)。r2/r3 已审结论 (task_fingerprint 纵深建议属可选加固非缝; 双 coordinator 判运维风险; worker result 队列丢失→checkpoint RUNNING 重跑不丢 — 别当新 finding)。
- **跨面边界 (别误判为本面缝)**: ① **campaign/resume 状态机本体 (持久化原子性、resume 一致性、终局证据 mark_candidate_result 单调) 是 face 7 单独审, 本轮不审**; 本面 worker 结果经 mark_candidate_result 落盘时, 强状态单调/弱覆盖审计阻断由 face 7 的 `exact_campaign.py:2058-2079` 兜底, 怀疑「并行下一个 worker 的 CERTIFIED 覆盖另一已有强记录」时真正防线在 face 7, 交叉引述而非在本面重证。② worker 进程内 Benders/cuts/binding/几何 正确性属各自面, 本面只假设 worker 返回 status 语义与 sequential 同源 (都走 `run_benders_for_ghost_rect`)。③ 终局 full-frontier evidence 重放完备性属 certified_frontier.py (face 7/终局证据线), 本面只负责把候选状态正确喂进去。
- 设计决策 (canonical / 266 口径 / `min_side>=6` admissibility, owner 已定); master / routing / cuts / preprocess / benders / binding / campaign 各面 (各自有线)。
- `candidate_placements.json` 外置 (再生 `python src/placement/placement_generator.py`, 期望 sha256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, 45,773,799 bytes, 不准伪造)。
- preflight `phase_1_2_spike_close` BLOCKED (owner gate); P1.3B `step_8_apply_to_master` 禁区; exploratory 行为/性能不审; persisted `exact_safe_cuts` 是 telemetry 非 proof。

## 自验环境与已知基线

- 再生工件后全量 `python -m pytest -q src/tests` 应 **≈3044 passed, 0 failed** (HEAD 2e1da65)。跑不完就跑 parallel/scheduler 专项 (`test_parallel*` / `test_exact_parallel*` 等) + 如实声明 (沙盒 pytest-randomly 报 seed 错就 `-p no:randomly`)。
- `python scripts/check_p1_2_proof_obligations.py` pass (8 obligations)。
- finding 必须带可复现 probe 或严谨论证 (file:line); 实证推翻你的怀疑就不要报。
- 契约: `PROJECT_LOCK.md:91,93,103` (coordinator-only / F78-F-02 / F-BIND-R5-01); `specs/10_benders_decomposition_and_cut_design.md` (LBBD 主从结构)。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression (LF 行尾)。
- **若确认 sound, 明确写「本轮零 soundness finding」** + 附三段判读: worker 身份绑定 (Q2/Q4) / 完备性闸 + crash 时序 (Q1/Q3) / 候选分配 + 合并去重 (Q5/Q6) 的真 Pro 复核。
- 真 Pro 首轮重审, 前轮 thinking 连零不代表本轮默认干净; 按你自己的独立判断下结论。

## 范围边界

- 重点 = parallel scheduler 波次调度 / worker 结果合并 / 完备性闸 soundness 的真 Pro 复核; **campaign/resume 状态机 (face 7) 与其余面不审**。
