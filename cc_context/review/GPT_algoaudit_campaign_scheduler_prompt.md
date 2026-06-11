# 终末地 IndustrialPlanner 精确求解器 — certified 证据持久化审查: campaign/resume 状态机 + 多进程波次合并

## 任务性质 (新会话零历史, 独立对抗审查)

附件是完整项目快照 zip (zip 内 `project/` 为仓库根; ZIP_LZMA, 用 `python -m zipfile -e <附件>.zip .` 解包)。依赖 wheels 在本 Project 文件区, 沙盒 Python 3.13, 离线 `pip install --no-index --find-links <wheels目录> -r requirements.txt`。

求解内核 (master/binding/routing/cuts) 与 preprocess 链已多轮对抗审查。**本轮审从未独立审过的两个证据持久化面**: 168h campaign 的断点续跑状态机, 和多进程并行波次的结果合并。这两层不做数学证明, 但它们**搬运并存活证明结论**——任何一处把弱结论存成强结论 (UNKNOWN→CERTIFIED / 半途→完成 / 张冠李戴的候选结果), 都等价于 false CERTIFIED; 任何一处把强结论丢弱 (CERTIFIED 被覆盖/丢失) 都伤完整性。若审完确认无残留, 明确报零——这是 owner 判定该面「第一轮干净」的输入。

## 项目一句话

70×70 网格 certified-exact 最大空矩形求解器 (目标 `max_lex(area, min_side)`, 266 强制设施, OR-Tools CP-SAT 9.15 + Benders/LBBD)。宪法 `PROJECT_LOCK.md`; fail-closed 默认姿态。

## 审查面

### 面 A — campaign/resume 状态机 (`src/search/exact_campaign.py`)

关注: `ExactCampaign.load_or_create` / `_validate_resume_state` / `_validate_candidate_record` / `mark_candidate_started` / `mark_candidate_result` / `update_candidate_bound_state` / `update_candidate_running_proof_summary` / `mark_campaign_stopped` / `best_certified_result` / `save` / `atomic_write_json` / terminal-certified 校验族 (`_validate_terminal_solution_against_project` / `terminal_certified_final_result_violation*` / `has_valid_terminal_full_frontier_certified_evidence*`)。

### 面 B — 多进程波次合并 (`src/search/exact_parallel_scheduler.py` + `src/search/outer_search.py` 的消费侧)

关注: `ExactParallelWorkerPool.run_wave` (结果队列收割/崩溃检测/respawn/排水) / `_worker_entry` / `WorkerTask`/`WorkerResult` 的 dispatch_seq 与 candidate_key 对应 / outer_search 把 wave 结果写进 campaign 的循环 (≈ `outer_search.py:2139-2312`: status 分发 → `mark_candidate_result` → `wave_execution.completed` 不达 → `mark_campaign_stopped("worker_process_failed", UNKNOWN)`)。

## 审查重点 (按优先级)

### Q1 状态强度单调性与张冠李戴 (false-CERTIFIED 风向)
- `mark_candidate_result` 的覆盖语义: 弱结论能否覆盖强结论, 或反之在什么序下合法? 一个 resume 后被重跑的候选, 旧 CERTIFIED record (含 solution) 与新 UNKNOWN/INFEASIBLE 结果如何合并——有没有路径让**陈旧 solution 在 status 已不是 CERTIFIED 时存活** (注意 :2056-2069 的 solution pop 逻辑) 或让 INFEASIBLE 错误钉死一个其实没证完的候选?
- 波次合并的**身份对应**: `results_by_seq` 按 dispatch_seq 收, crash respawn 后 pending 任务重新入队——同一 candidate 能否产生两个 result (死亡 worker 残留队列 + respawn 重跑)? `setdefault` 保第一个——第一个一定是有效完整的吗 (worker 在写 result 与崩溃之间的半写状态)? dispatch_seq 在 respawn 后会不会复用导致错配?
- worker 进程间 result 队列的序列化边界: `WorkerResult` 经 multiprocessing queue 传递, 有没有字段在 pickle round-trip 后语义漂移 (如 status 字符串 vs 枚举)?

### Q2 resume 的 deny-unknown 与 fail-closed
- `_validate_resume_state` / `_validate_candidate_record`: 哪些字段是 deny-unknown 封闭的, 哪些放行自由值? 一个被手工篡改/旧 schema 的 state 文件能否 resume 出比它实际证明强的状态?
- artifact hash 兼容检查 (`is_compatible_with_current_hashes`): 工件换代后 resume 是否严格 fail-closed 拒绝 (这条很快会被真实触发——preprocess 修复将换 `candidate_placements` hash)?
- `atomic_write_json` + `_fsync_directory`: 断电/崩溃在写状态文件中途, 重启后读到的是旧完整版还是半写版? Windows 与 Linux 语义差异?
- `mark_candidate_started` 后崩溃 (无 finished): resume 后该候选会被重跑还是被误当完成?

### Q3 终局判定与部分失败
- `final_result` 提升链: 候选级 CERTIFIED 何时允许成为 terminal full-frontier 证据? `declare_mode != strict` 的 block 逻辑、frontier 未穷尽时的禁止提升、`mark_campaign_stopped` 的 stop_reason/status 组合——有没有组合能把 time-budget/worker-failure 停机伪装成完整 frontier 终局?
- wave 部分失败: 一个 worker errored → `failure_reason` → break, **其余已收 result 仍被写进 campaign** (outer_search 标记循环不看 completed)——这些 sibling result 的可信度论证? 之后 `mark_campaign_stopped(worker_process_failed, UNKNOWN)` 是否足够 fail-closed?
- `best_certified_result` 的择优比较与 `max_lex` 目标一致性。

### Q4 工程面
respawn 计数/泄漏、result 队列 drain 竞态、heartbeat 仅遥测不入证据、`peak_rss` 统计不影响判定、telemetry append 失败不破坏状态机。

## 明确不要报的

- persisted `exact_safe_cuts` 是 telemetry 不是 proof object (V82 已封口, 重放校验在 cut 消费侧)。
- proof-carrying certificate (future work); P1.3B `step_8_apply_to_master` 禁区; exploratory 不审。
- `candidate_placements.json` 外置缺失本身 (已知)。
- preprocess 链已另行审查处置中, 非本轮范围。

## 自验环境与已知基线

- `python scripts/check_p1_2_proof_obligations.py` 应 pass。
- `python -m pytest -q -p no:randomly src/tests/test_exact_campaign_inspector.py src/tests/test_parallel_scheduler.py` 与 campaign 相关测试族应过 (以包内实际收集为准)。
- 已知环境性失败 (非 finding, 因外置工件): test_binding 10 ERROR / test_regression 5 / test_routing 3 / test_master 1 / test_preprocess_golden 1。
- finding 必须带可复现 probe (构造 state 文件/模拟 crash-resume/伪造 wave 结果, 实证状态机吐出错误强度 = 金标准) 或严谨论证 (file:line)。实证推翻你的怀疑就不要报。

## 交付物

- `REVIEW.md`: 逐条 finding (severity / file:line / probe 或论证 / 修法), 有把握附 unified diff + regression; **关键论证写在回复正文**。
- **若审完确认两面 sound, 明确写「本轮零 soundness finding」** + 列实际审过的面、构造过的攻击 probe、论证依据。

包 sha256: `<SEND_TIME_FILL>`
