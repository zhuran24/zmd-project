# IndustrialPlanner parallel scheduler 面 round 5 review

## 结论

本轮不是零 finding。确认 F-PS-R4-01 的修复思路正确，但实现仍有一个同型残留：scheduler 的 discard latch 在两条路径上不够“粘”，consumer 的 worker-failure 白名单又使用裸 `startswith`。两者叠加时，一个被判定为畸形 / validation-failure 的 wave 仍可能把身份看似合法的同伴结果写入 campaign candidate records。

已附补丁：`F-PS-R5-parallel-scheduler-fix.patch`。

修后结论：三段消费路径均 fail-closed；consumer 只对白名单的精确 reason 或冒号分隔 reason 保留身份合法的已完成进度；未发现新的未派发 / 未校验 worker 或 precheck 结果落入 campaign 的残留路径。

## Finding F-PS-R5-01 — HIGH

**标题**：validation-failure discard latch 非全路径 sticky，且 worker-failure 白名单可被前缀碰撞绕过，畸形 wave 可落地同伴结果。

**位置**：

- `src/search/exact_parallel_scheduler.py:121-122`：原实现把 `WorkerResult.error` 原样作为 `failure_reason` 返回。
- `src/search/exact_parallel_scheduler.py:491-511`：crash drain 中 `_record_worker_result()` 返回 validation failure 后虽然 `results_by_seq.clear()`，但同一 drain 循环继续处理后续 `WorkerResult`，可重新填入 `results_by_seq`。
- `src/search/exact_parallel_scheduler.py:541-544`：主循环收到非 `WorkerResult` 时只设置 `failure_reason="worker_result_invalid"` 并 break，没有置 `discard_results_due_to_worker_result_failure`，也没有清空 `results_by_seq`，尾部 drain 会继续累积。
- `src/search/outer_search.py:161-169`：`_parallel_wave_failure_discards_results()` 用裸 `startswith("worker_process_failed")` / `startswith("worker_crash_respawn_limit")` 判断不弃整波结果，存在前缀碰撞。

**可复现 probe（原包行为）**：

1. 主循环路径：构造 `[合法 seq0, 非 WorkerResult, 合法 seq1]` 的 synthetic queue。原实现返回：

```text
completed=False, failure_reason='worker_result_invalid', results=[seq0, seq1]
```

这说明 Q1(a) 指出的 `:543` 分支确实会把 `results_by_seq` 留给尾部 drain 继续重填。当前 consumer 因 `worker_result_invalid` 非白名单会弃掉它，但 scheduler 侧 F-PS-R4-01 不变量没有闭合。

2. crash drain 路径：让 `get()` 超时、进程 `exitcode=1`，`get_nowait()` drain 出 `[candidate_mismatch seq0, 合法 seq1]`。原实现返回：

```text
completed=False, failure_reason='worker_result_candidate_mismatch:0', results=[seq1]
```

这里不是尾部 drain，而是 crash drain 自身在 clear 后继续接收同一批消息，把 seq1 重新塞进 `results_by_seq`。

3. 前缀碰撞 + campaign 落地：原 consumer 对 `failure_reason="worker_process_failed_validation_failure:spoofed"` 返回“不弃”。构造一个 `completed=False`、该 failure_reason、且携带身份合法 `CERTIFIED` 的 fake wave，`run_outer_search()` 在原实现中会写出：

```text
status=UNKNOWN, last_stop_reason='worker_process_failed'
candidates={'3x3': 'CERTIFIED', '6x1': 'RUNNING'}
```

这违反“畸形 wave 全弃 proof-bearing 结果”的语义。更贴近 scheduler 的组合 probe 是：crash drain 中第一个 `WorkerResult.error="worker_crash_respawn_limit:spoofed_worker_error"`，第二个为合法 seq1；原 scheduler 直接把 raw error 作为 failure_reason 返回，且 crash drain 重填 seq1，consumer 因 `startswith("worker_crash_respawn_limit")` 判定“不弃”。

**修法**：

- `WorkerResult.error` 的 reason 改为 `worker_result_error:{dispatch_seq}:{error}`，避免 worker 内部 error 字符串进入 process/crash 白名单命名空间。
- crash drain 在 `discard_results_due_to_worker_result_failure` 置位后跳过后续 `RESULT` 消息，只保留 heartbeat telemetry。
- 主循环非 `WorkerResult` 分支同步置 discard latch 并清空 `results_by_seq`。
- return 前增加最终保险：只要 discard latch 为真，就再次清空 `results_by_seq`。
- consumer 白名单从裸 `startswith(prefix)` 收紧为 `reason == prefix or reason.startswith(prefix + ":")`，拒绝 `worker_process_failed_validation_failure:*` / `worker_crash_respawn_limit_validation_failure:*` 这类碰撞。

**Regression**：

- `test_parallel_worker_pool_discards_results_after_main_loop_invalid_message`
- `test_parallel_worker_pool_crash_drain_stops_after_validation_failure`
- `test_parallel_wave_failure_discard_helper_rejects_prefix_collisions`
- `test_outer_search_discards_worker_failure_prefix_collision_results`
- 更新 `test_parallel_worker_pool_drops_errored_strong_result`，锁定 `worker_result_error:{dispatch_seq}:...` 命名空间。

## Q1 — scheduler 侧 clear 完备性判读

修前：不完备。`_record_worker_result()` 返回 reason 的主循环路径、尾部 drain 路径会 clear；但 crash drain clear 后不停止同批 drain 继续 `_record_worker_result()`，可重填。主循环 `worker_result_invalid` 分支也没有 clear / discard latch，尾部 drain 能继续累积。

修后：完备。三段消费现在满足：

- crash drain：任一 validation failure 置 latch + clear；同一 drain 的后续 `RESULT` 被跳过。
- 主循环正常 get：`_record_worker_result()` failure 和非 `WorkerResult` failure 都置 latch + clear。
- 尾部 nowait drain：latch 置位后跳过后续 `RESULT`；若尾部自身发现 validation failure，也置 latch + clear。
- 返回前最终 guard 再清一次，防止未来改动引入重填。

`worker_crash_respawn_limit:*` 不清空是保留的设计：它不是 worker-result validation failure，而是 worker/process crash stop；其中已完成且通过身份校验的结果可以作为合法进度保留，campaign 随后仍以 `UNKNOWN` 停止，不会终局 CERTIFIED。

## Q2 — consumer 白名单 + 前缀碰撞判读

修前：白名单过宽。全仓实际 production scheduler 只原生生成 `worker_crash_respawn_limit:*`，`worker_process_failed:*` 主要由 wrapper/test/future path 使用；但 `_record_worker_result()` 原样透传 `result.error`，使 worker-side error reason 可以碰撞这些前缀。consumer 没有能力区分“真实 worker/process failure”与“畸形 worker-result failure 冒名”。

修后：白名单闭合为精确名称空间：

- 不弃结果：`worker_process_failed`、`worker_process_failed:*`、`worker_crash_respawn_limit`、`worker_crash_respawn_limit:*`。
- 弃整波结果：`worker_process_failed_validation_failure:*`、`worker_crash_respawn_limit_validation_failure:*`、`worker_result_error:*`、`worker_result_*`、`parallel_wave_result_*` 等所有 validation failure。

consumer 合并前仍有第二道身份防线：`_parallel_wave_result_identity_failure()` 检查 dispatch_seq 唯一且已派发、attempt_index、candidate tuple、candidate_key、status/solution/error 约束；身份失败时 `discard_wave_results=True`，不会进入 `mark_candidate_result()`。它不重复校验 `proof_summary` / `exact_safe_cuts` 类型，但 production scheduler 已在 `_record_worker_result()` 校验；本轮未发现绕过 scheduler 并让这些字段作为 proof-bearing 结果落地的 production 路径。

## Q3 — 完备性闸 + 不误弃判读

畸形 wave 修后会得到 `sorted_wave_results=()`，`effective_wave_completed=False`，随后 `mark_campaign_stopped("worker_process_failed", UNKNOWN)` 并返回。已 `mark_candidate_started()` 的候选保持 `RUNNING`；`_compute_exact_frontier_state()` 默认只跳过 `CERTIFIED` / `INFEASIBLE`，不跳过 `RUNNING`，所以 resume / 下一轮 frontier 会把它们留在 `potential_domain`。终局 CERTIFIED / INFEASIBLE 只在 frontier/potential domain 被耗尽时进入，畸形 wave 不会靠 stale result 绕过终局闸。

合法全 CERTIFIED wave 不会被误弃：`completed=True` 且 `wave_identity_failure is None` 时 `discard_wave_results=False`。合法 worker process/crash failure 可以携带身份有效的部分完成进度；这些进度可写入 candidate records，但 campaign 仍以 `UNKNOWN` 停止，且不会导出 terminal certified result。这是 availability/progress 保留，不是 false-CERTIFIED 终局。

## Q4 — 同型第三实例猎取结论

发现的第三实例就是本轮 F-PS-R5-01 的组合缝：scheduler validation-failure 结果残留 + consumer 前缀碰撞，能把畸形 wave 的同伴结果落进 campaign。

修后复核：

- `wave_candidate_results_by_key` 先放 coordinator precheck 结果；precheck 候选来自 `wave_candidate_entries`，即当前 frontier/potential-domain 选择项，不接受 worker 输入的 candidate identity。
- worker merge 的 `matching_solve_entry` 虽有 `prune_fill` fallback，但在 `_parallel_wave_result_identity_failure()` 通过后，result 的 dispatch_seq/candidate/candidate_key 必与 `tasks` 匹配，而 `tasks` 由 `solve_wave_entries` 构造，因此 `matching_solve_entry is None` 在 production 路径不可达。
- 若 consumer 身份复核失败，`sorted_wave_results=()`，不会执行 `mark_candidate_result()`。
- 未发现另一个“未派发 / 未通过身份或有效性校验的 worker/precheck 结果落地 campaign”的残留路径。

## 验证

```text
sha256sum /mnt/data/zmd_snapshot_1e136b90.zip
1e136b90a290684874398ce5f2ddaceac156481d2178fa1333db9ba14b8e16f2

sha256sum data/preprocessed/candidate_placements.json
adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0

PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_parallel_scheduler.py
19 passed in 3.39s

PYTHONPATH=. python -m pytest -q -p no:randomly src/tests/test_exact_contract.py
96 passed in 6.81s

PYTHONPATH=. python scripts/check_p1_2_proof_obligations.py
P1.2 proof obligation check passed: 8 obligations anchored

python -m ruff check src/search/exact_parallel_scheduler.py src/search/outer_search.py src/tests/test_parallel_scheduler.py
All checks passed!
```

全量 `src/tests` 曾启动一次，但 300s 沙盒超时未完成；因此本轮实跑结论以上述专项 + exact_contract + proof obligations 为准。
