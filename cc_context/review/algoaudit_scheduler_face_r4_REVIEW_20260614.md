# 终末地 IndustrialPlanner parallel scheduler 面 r4 review

快照：`zmd_snapshot_f4418b04.zip`

SHA256 校验：`f4418b045b257e186c0d06ad6045908a33118d597b8f65666fb39691378965d1`，与任务给定值一致。

审查范围：`src/search/exact_parallel_scheduler.py` 的 worker pool / wave 执行 / result queue 收割，以及 `src/search/outer_search.py` 的 parallel wave 合并、frontier 重建、终局判据。未审 campaign/resume 状态机本体、LBBD 子问题证明、cuts/preprocess/geometry 等跨面内容。

## Findings

### F-PS-R4-01 - HIGH - scheduler-side validation failure could leak a retained first result into campaign records

位置：

- 原始 `src/search/exact_parallel_scheduler.py:475-579`
- 原始 `src/search/outer_search.py:2280-2295`, `src/search/outer_search.py:2297-2451`

问题：

`ExactParallelWorkerPool.run_wave()` 在 `_record_worker_result()` 报错时会设置 `failure_reason`，但此前已经进入 `results_by_seq` 的结果不会被清空；尾部 drain 也会继续尝试把后续 identity-valid `RESULT` 放进 `results_by_seq`。`outer_search` 只在 consumer-side `wave_identity_failure` 非空时把 `sorted_wave_results` 清空。若 scheduler-side 已经判出 `worker_result_duplicate_dispatch_seq:*`、`worker_result_candidate_mismatch:*`、`worker_result_invalid`、errored result 等失败，但返回的 `ParallelWaveExecution.results` 里仍带有先前被接纳的 `CERTIFIED`，consumer 会先把该 candidate 写入 campaign，再以 `worker_process_failed`/`UNKNOWN` 停波。

这不会立即导出 terminal `CERTIFIED`，因为 `effective_wave_completed=False` 时 `outer_search` 会先走 `worker_process_failed` 返回 `UNKNOWN`。但 candidate-level `CERTIFIED` 是后续 frontier pruning / resume 可消费的强记录；一旦该强记录来自一个已被 scheduler 判定畸形的 wave，就违反了 F78-F-02 对 duplicate/malformed result “全弃”的 fail-closed 语义。风险不是 false-immediate-final，而是 malformed wave 的残留强记录在后续重建 frontier 时成为 proof-bearing pruning 输入。

可复现 probe：

1. 对 `ExactParallelWorkerPool.run_wave()` 注入两个同一 `dispatch_seq=0`、同一 `attempt_index`、同一 candidate 的 `WorkerResult`，第一个为 `CERTIFIED`，第二个为 `INFEASIBLE`。
2. 原始行为：`wave.completed is False`，`wave.failure_reason == "worker_result_duplicate_dispatch_seq:0"`，但 `wave.results == [(0, "CERTIFIED")]`。
3. 再用 fake `run_parallel_exact_campaign_wave()` 返回 `completed=False`、`failure_reason="worker_result_duplicate_dispatch_seq:0"`、`results=(CERTIFIED result,)`。
4. 原始 `outer_search` 会返回 `UNKNOWN` 且 `final_result is None`，但 campaign 中对应 candidate 已落为 `CERTIFIED`，而同波未完成候选为 `RUNNING`。

修法：

- 在 scheduler 侧增加 `discard_results_due_to_worker_result_failure`。一旦 `_record_worker_result()` 或 result payload 类型校验失败，就设置该闸、清空 `results_by_seq`，并让尾部 drain 只保留 heartbeat，不再累积 proof-bearing result。
- 在 consumer 侧新增 `_parallel_wave_failure_discards_results()`。除明确的 worker crash / process-failure 类 failure reason 外，`completed=False` 的 wave 一律不消费 `wave_execution.results`。这使 custom executor 或未来 scheduler 变体即使返回了 validation-failure results，也不会写入 campaign。
- 保留 worker crash 路径的合法进度保存：`worker_process_failed*` / `worker_crash_respawn_limit*` 仍可携带 identity-valid completed progress，但终局导出仍被 `effective_wave_completed=False` 阻断。

回归：

- 新增 `test_parallel_worker_pool_discards_all_results_after_duplicate_dispatch_seq()`，锁 scheduler 侧 duplicate seq 后 `wave.results == ()`。
- 新增 `test_outer_search_discards_scheduler_validation_failure_results()`，锁 consumer 侧 scheduler validation failure 即使带 `CERTIFIED` result，也只留下 started/RUNNING 候选，不写 `CERTIFIED` campaign record，telemetry candidate_results 为空。

## Q1-Q6 复核判读

### Q1 完备性主缝：身份失败清波与终局闸

修前 consumer-side `wave_identity_failure` 已会把 `sorted_wave_results` 清空；修后 scheduler-side validation failure 也同样清空 proof-bearing results。已 `mark_candidate_started()` 的候选会以 `RUNNING` 留在 campaign。`_compute_exact_frontier_state()` 默认 `_frontier_skip_statuses` 仅含 `CERTIFIED` / `INFEASIBLE`，所以未完成 `RUNNING` 不会被跳过；终局 `CERTIFIED` / `INFEASIBLE` 只在 `potential_domain` 为空时触发。身份失败导致的是 fail-closed `UNKNOWN` 与 availability 损失，不会绕过 full-frontier 终局闸。

我另做了一个 mismatch probe：fake wave 中一个 malformed result 加一个合法同伴，返回后 campaign stop 为 `worker_process_failed`/`UNKNOWN`，candidate 状态只剩 `RUNNING`，重算 `potential_domain_size=17`，`best_certified=None`。这验证了“合法同伴被清掉后不会产生 false terminal”的路径。

### Q2 UNPROVEN 状态白名单与串并行语义

`VALID_WORKER_RESULT_STATUSES` 与 `_VALID_PARALLEL_WORKER_RESULT_STATUSES` 均包含 `UNPROVEN`。静态检查显示 `run_benders_for_ghost_rect()` 在 certified blockers 等路径上确实可能返回 `RUN_STATUS_UNPROVEN`，因此它不是完全不可达状态。parallel consumer 对 `UNPROVEN` 走 `mark_candidate_result(..., UNPROVEN)`，再由 `_terminal_stop_reason_for_status()` 映射为 `candidate_returned_unproven`；serial 路径也在 `outer_search.py:2672-2707` 做同样的 candidate result + campaign stopped 处理。结论：`UNPROVEN` 是 fail-closed terminal，不会变成 false `CERTIFIED`，且串并行语义一致。

### Q3 crash respawn 与尾部 drain

respawn 时 `_respawn_all_workers()` 会重建 task/result queue。若旧 worker 已 put 但 coordinator 未 get，该 result 只可能丢在旧 queue；因为 `pending` 按 `results_by_seq` 重算，未记录的 candidate 会重投，属于安全重跑而不是“已完成但未落盘”。若 result 已被记录，则 pending 不含该 candidate。尾部 drain 在本补丁后对 validation-failure wave 不再追加 proof-bearing results；对 worker crash / respawn-limit wave，仍允许保存 identity-valid completed progress，但 `effective_wave_completed=False` 会先停为 `worker_process_failed`/`UNKNOWN`，不会执行 terminal `CERTIFIED`。

### Q4 跨波身份隔离：epsilon / solve_mode / profile 未入身份四元组

当前生产 queue 生命周期足以隔离跨波：每个 successful wave 结束后 `run_wave()` 调 `_respawn_all_workers()`，重建 task_queue/result_queue；failure wave 则 terminate 并由 outer 立即返回。`solve_mode` 与 `master_search_profile` 固定在 pool 构造和 worker startup；`epsilon_stage` 是 task 字段，同一 wave / respawn 重投保持一致。`dispatch_seq` 虽每波从 0 重排，`attempt_index` 在单次 run 内随 selection/evaluation 增长，但跨 resume 不持久；这不构成 queue stale 风险，因为进程与 queue 不跨 resume 存活。

### Q5 候选漏分/重分：depth multiplier 超额分发

`_select_parallel_wave_candidate_entries()` 用 `selected_keys` 跨 probe/objective/prune/anchor/prune_fill 去重，`build_parallel_worker_tasks()` 再以 dispatch_seq 唯一性建 `tasks_by_seq`，重复 dispatch_seq 会 fail closed。每轮 `frontier_state` 都由 campaign records 全量重算，不依赖增量 frontier 游标；因此已落为 `CERTIFIED`/`INFEASIBLE` 的候选被跳过，未完成/UNKNOWN 默认不会被跳过，不存在跨波候选串号导致的漏解。

### Q6 coordinator precheck 与 worker result 合并

precheck 命中的 entry 立即 `_record_precheck_elimination()` 写成 `INFEASIBLE`，并不会进入 `solve_wave_entries`。同一波的 `wave_candidate_results_by_key` 先放 precheck，再放 worker result；由于 selection 阶段已经按 candidate_key 去重，正常路径不存在同 key precheck + worker 冲突。`matching_solve_entry = next(... candidate_key ...)` 在 identity-valid worker result 下应总能命中；`None` fallback 只属于 telemetry defensive fallback，不会把未派发候选写入 campaign。

## Regression / verification

已执行：

```text
python3.13 -m venv /mnt/data/zmd_r4/.venv
/mnt/data/zmd_r4/.venv/bin/python -m pip install --no-index --find-links .../wheels -r project_requirements.lock.txt
/mnt/data/zmd_r4/.venv/bin/python -m pytest -q src/tests/test_parallel_scheduler.py -p no:randomly
# 15 passed
/mnt/data/zmd_r4/.venv/bin/python -m pytest -q src/tests -k 'parallel or worker_process_failed or outer_skip_unknown' -p no:randomly
# 33 passed, 3087 deselected
/mnt/data/zmd_r4/.venv/bin/python -m pytest -q src/tests/test_exact_outer_skip_unknown.py src/tests/test_exact_campaign_state_soundness.py src/tests/test_exact_campaign_bound_state.py -p no:randomly
# 21 passed
/mnt/data/zmd_r4/.venv/bin/python scripts/check_p1_2_proof_obligations.py
# P1.2 proof obligation check passed: 8 obligations anchored
/mnt/data/zmd_r4/.venv/bin/python -m py_compile src/search/exact_parallel_scheduler.py src/search/outer_search.py src/tests/test_parallel_scheduler.py
# pass
```

未执行全量 `python -m pytest -q src/tests`：本快照解包后没有 `data/preprocessed/candidate_placements.json`，我未在本轮再生 45MB 外置工件，因此没有声称全量 3044+ 测试通过。

## Patch

补丁文件：`parallel_scheduler_r4.patch`

应用方式：

```text
cd project
patch -p1 < /path/to/parallel_scheduler_r4.patch
```

我已在 fresh extracted original tree 上验证该 patch 可用 `patch -p1` 干净应用，并且补丁后目标文件与审查工作树一致。
