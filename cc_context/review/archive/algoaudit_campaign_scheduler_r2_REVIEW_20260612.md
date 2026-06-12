# 终末地 IndustrialPlanner 精确求解器 — F78 evidence persistence r2 review

审查对象：`zmd_f78r2_snapshot_13dc4e59.zip`

快照门禁：已先验校验 sha256，结果匹配指定值。

```text
13dc4e596b5327a8fc888a39d89405553bffb7fb4c993538755580b3accd22af  zmd_f78r2_snapshot_13dc4e59.zip
```

解包根：`/mnt/data/zmd_f78r2_review/project`，zip 内 `project/` 为仓库根。依赖从 `zmd_py313_linux_x86_64.zip` 离线安装到 Python 3.13 环境。

## 结论

**本轮零 soundness finding。**

未发现 F78-F-01 / F78-F-02 修复残留的 false-CERTIFIED / false-INFEASIBLE / 队列错配写入问题，也未发现本轮范围内新的证据强化缝。没有修改源码，因此没有补丁包、没有 unified diff、没有冻结工件再生或登记 hash 推进项。

我把同类问题按两个维度泛化穷举：

1. `exact_campaign.py` 内所有候选状态、终局状态、frontier evidence 与 telemetry-like state writer；
2. `exact_parallel_scheduler.py` / `outer_search.py` 的 multiprocessing task/result/heartbeat/telemetry 边界。

## 验证命令

```bash
cd /mnt/data/zmd_f78r2_review/project
python3.13 -m py_compile \
  src/search/exact_campaign.py \
  src/search/exact_parallel_scheduler.py \
  src/search/outer_search.py \
  src/search/campaign_telemetry.py \
  src/search/certified_frontier.py \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_parallel_scheduler.py
```

结果：通过。

```bash
python3.13 -m pytest -q -p no:randomly \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_bound_state.py
```

结果：`39 passed in 4.14s`。

```bash
python3.13 -m pytest -q -p no:randomly \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_v84_terminal_layout_max_empty_rect.py \
  src/tests/test_v85_terminal_required_optionals.py \
  src/tests/test_v86_terminal_power_witness_validation.py \
  src/tests/test_v87_terminal_ghost_anchor_validation.py \
  src/tests/test_v88_terminal_ghost_anchor_required.py \
  src/tests/test_v89_terminal_ghost_pick_protocol_validation.py \
  src/tests/test_v91_terminal_nested_public_field_validation.py \
  src/tests/test_v94_terminal_protocol_storage_surplus_validation.py \
  src/tests/test_v95_terminal_optional_metadata_validation.py \
  src/tests/test_v97_canonical_campaign_state_authority.py \
  src/tests/test_v98_b5a_symlink_campaign_path_authority.py \
  src/tests/test_exact_campaign_bound_state.py \
  src/tests/test_exact_campaign_inspector.py
```

结果：`94 passed in 13.33s`。

```bash
python3.13 scripts/check_p1_2_proof_obligations.py
```

结果：`P1.2 proof obligation check passed: 8 obligations anchored`。

全量 `python3.13 -m pytest -q -p no:randomly src/tests` 也已尝试，但沙盒执行窗口内未完成；本报告不声称全量 2917 项已跑完。专项与本面相关扩展套件均为绿。

## Q1: F78-F-01 修复复核

### 入口与 resume 校验

`src/search/exact_campaign.py:50` 定义强状态集合为 `{CERTIFIED, INFEASIBLE}`。

`_validate_candidate_record` 在 `src/search/exact_campaign.py:1383-1458` 形成候选记录的核心 fail-closed 栅栏：

- `status` 必须属于 `VALID_CANDIDATE_STATUSES`，见 `src/search/exact_campaign.py:1420-1422`；
- `CERTIFIED` 必须携带 mapping 型 `solution`，见 `src/search/exact_campaign.py:1423-1424`；
- 任何非 `CERTIFIED` 记录只要带 `solution` 就拒绝，错误码为 `candidate_non_certified_solution_present:<key>`，见 `src/search/exact_campaign.py:1425-1426`；
- `exact_safe_cuts` 必须是 list，且每条 cut 可 parse 为 `BendersCut`、`source_mode == certified_exact`、`exact_safe is True`，并通过 cut condition domain 校验，见 `src/search/exact_campaign.py:1430-1449`；
- `RUNNING` 与非 `RUNNING` 的 `finished_at` 形态互斥，见 `src/search/exact_campaign.py:1451-1457`。

`_validate_resume_state` 在 `src/search/exact_campaign.py:1461-1563` 先做 schema、solve mode、required fields、artifact hashes 精确匹配，再对 terminal evidence surface 与每个 candidate record 做校验。artifact hash mismatch 在 `src/search/exact_campaign.py:1490-1493` fail-closed；candidate 遍历在 `src/search/exact_campaign.py:1536-1545`。

### mark_candidate_started 的强状态 no-op

`mark_candidate_started` 在 `src/search/exact_campaign.py:1997-2026` 对同 artifact hash 下已有强状态记录直接 no-op，见 `src/search/exact_campaign.py:2001-2009`。对弱状态记录，它会以 defaults + existing 合并，然后显式设置 `RUNNING` 并 `record.pop("solution", None)`，见 `src/search/exact_campaign.py:2010-2020`。

复核结论：no-op 没有引入新的 proof strengthening 缝。它确实会保护任何已经存在的同 hash 强记录，但新代码的公开 writer 已不能通过“弱状态 + 残留 solution”生成这种记录；同 hash 的坏强证据只能来自旧版/外部/直接篡改且还要通过 terminal/project 校验。这个边界属于“无法从 checkpoint 自证历史 provenance”的固有限制，不是本轮新残留。

手动重跑场景也未被反向破坏：`mark_candidate_started` 不再降级强记录，但 `mark_candidate_result` 仍允许用同一强状态的新结果刷新记录。例如已有 `CERTIFIED` 后再写入 `CERTIFIED`，必须携带 fresh `solution`；已有 `INFEASIBLE` 后再写入 `INFEASIBLE` 也可更新 proof_summary/cut counters。真正被阻断的是强→弱降级和强↔强矛盾。

### mark_candidate_result 的单调语义

`mark_candidate_result` 在 `src/search/exact_campaign.py:2028-2135` 先校验 incoming status/solution 组合，再看 existing 记录：

- 非法 status 直接 `ValueError`，见 `src/search/exact_campaign.py:2040-2042`；
- `CERTIFIED` 必须带 fresh solution mapping，见 `src/search/exact_campaign.py:2043-2044`；
- 非 `CERTIFIED` 不得带 solution，见 `src/search/exact_campaign.py:2045-2046`；
- `CERTIFIED` ↔ `INFEASIBLE` 矛盾强状态直接 raise，见 `src/search/exact_campaign.py:2054-2062`；
- 既有强状态遇到弱结果时追加 `CANDIDATE_STRONG_STATUS_DOWNGRADE_BLOCKED` audit event 并 return，不改候选记录，见 `src/search/exact_campaign.py:2063-2079`；
- 真正写入 `CERTIFIED` 时只写 incoming `solution=dict(solution)`，非 `CERTIFIED` 统一 `record.pop("solution", None)`，见 `src/search/exact_campaign.py:2119-2132`。

强→弱阻断路径会跳过 cut/counter/proof_summary 更新。复核结论：这是 completeness/telemetry 取舍，不影响 soundness。candidate 仍保持原强状态和原 witness；cut/counter 不参与 terminal certificate authority，且 resume 会重新校验 `exact_safe_cuts` 的结构与 exact-safe 属性。计数器仅在 `_validate_candidate_record` 中按 strict int 校验，不作为“强证据”或 frontier exhaustion 的判据。

### 回归覆盖

`src/tests/test_exact_campaign_state_soundness.py` 覆盖了强状态重跑保留、fresh solution 必需、强→弱阻断与非 `CERTIFIED` 携带 stale solution 的 resume 拒绝。专项测试已通过。

## Q1: F78-F-02 修复复核

### scheduler 侧身份绑定

`WorkerTask` / `WorkerResult` 定义在 `src/search/exact_parallel_scheduler.py:26-64`。结果接收集中走 `_record_worker_result`，见 `src/search/exact_parallel_scheduler.py:108-138`。

`_worker_result_identity_violation` 在 `src/search/exact_parallel_scheduler.py:79-105` 校验四元组：

- `dispatch_seq` 可转 int 且存在于本波 `tasks_by_seq`；
- `attempt_index` 与任务一致；
- `candidate` 三元组与任务一致；
- 派生 `candidate_key` 与任务一致。

`_record_worker_result` 还拒绝 errored result、非法 status、`CERTIFIED` 缺 solution、非 `CERTIFIED` 带 solution、非 mapping `proof_summary`、非 list `exact_safe_cuts`、重复 dispatch_seq，见 `src/search/exact_parallel_scheduler.py:120-137`。

`build_parallel_worker_tasks` 每波从 `enumerate(candidates)` 生成 dispatch_seq，并校验 attempt_indices 长度，见 `src/search/exact_parallel_scheduler.py:141-183`。`run_wave` 进入时构造 `tasks_by_seq` 并要求 dispatch_seq 唯一，见 `src/search/exact_parallel_scheduler.py:452-454`。所有普通收割、crash drain、尾部 drain 路径都调用 `_record_worker_result`，分别见 `src/search/exact_parallel_scheduler.py:475-490`、`src/search/exact_parallel_scheduler.py:520-531`、`src/search/exact_parallel_scheduler.py:533-556`。

复核结论：round 1 的 `results_by_seq` 仅信 dispatch_seq / setdefault 先到先得问题已修复。本波错配结果不会写入 campaign；重复 seq 不会覆盖先前结果；errored 强结果不会被当作证据落盘。

### consumer 侧二次身份绑定

`outer_search.py` 另有独立消费侧校验 `_parallel_wave_result_identity_failure`，见 `src/search/outer_search.py:115-158`。它重复检查 duplicate seq、unknown seq、attempt mismatch、candidate mismatch、candidate_key mismatch、worker error、status/solution 组合。

在 parallel wave 消费处，`wave_identity_failure` 非空时：

- `effective_wave_completed=False`，见 `src/search/outer_search.py:2193-2199`；
- `sorted_wave_results=()`，即该 malformed wave 的返回结果全丢弃，见 `src/search/outer_search.py:2205-2208`；
- telemetry 记录 failure_reason，但 candidate_results 为空；
- campaign 最终以 `worker_process_failed` / `UNKNOWN` 停机，见 `src/search/outer_search.py:2363-2374`。

scheduler 已经捕获的错配结果不会进入 `wave.results`；如果错配由 synthetic/buggy wave executor 直接返回给 consumer，consumer 会整波丢弃。这两种路径都只损害 completeness，不损害 soundness。

### 漏维度复核：epsilon / solve_mode / master_search_profile

`WorkerResult` 不携带 `epsilon_stage`、`solve_mode` 或 `master_search_profile`，因此四元组身份没有直接比较这些字段。这一处没有形成当前 soundness finding，原因是：

- `solve_mode` 与 `master_search_profile` 是 pool/worker 启动参数，worker session 创建时从 parent 固定传入，见 `src/search/exact_parallel_scheduler.py:193-224`；
- `epsilon_stage` 是 task 字段，worker 调用 solver 时直接传入，见 `src/search/exact_parallel_scheduler.py:272-289`；
- wave 成功或失败后都会 respawn / replace queues，见 `src/search/exact_parallel_scheduler.py:557-560` 与 `_respawn_all_workers` 的 queue replacement，`src/search/exact_parallel_scheduler.py:374-391`；
- stale cross-wave result 若要被当前 wave 接受，必须在当前 result_queue 中同时撞中 dispatch_seq、attempt_index、candidate、candidate_key；在当前实现的 queue 生命周期下，普通 crash/retry 不提供这种漂移路径。

可选 hardening 方向是给 `WorkerTask` / `WorkerResult` 增加 `task_fingerprint`，覆盖 epsilon、solve_mode、profile 与 timeout envelope。但这属于纵深防御建议，不是本轮 soundness 缝。

### telemetry failure_reason 不会变强证据

parallel wave 的 `failure_reason` 只进入 telemetry append 与 stop reason 的 generic `worker_process_failed` 路径，见 `src/search/outer_search.py:2344-2351` 与 `src/search/outer_search.py:2363-2374`。它不会被 `best_certified_result`、terminal final_result、terminal frontier evidence 或 candidate strong status 作为证据消费。

## Q2: campaign writer 穷举

### exact_campaign.py 内 writer 清单

| writer | 位置 | 写入面 | 结论 |
|---|---:|---|---|
| `_build_initial_state` | `src/search/exact_campaign.py:1349-1374` | 初始 schema/artifact/final/candidates | 构造空状态，`final_result=None`、`final_status=None`、`terminal_frontier_evidence=None`，不能强化证据。 |
| `load_or_create` | `src/search/exact_campaign.py:1805-1866` | resume accepted state 的 `updated_at/reset_reason/campaign_hours`，以及 time-budget stop 清理 | 只在 `_validate_resume_state` 已通过后改元数据；artifact mismatch / malformed state 会新建空状态。time-budget clear 不会留下 certified export surface。 |
| `update_candidate_bound_state` | `src/search/exact_campaign.py:1916-1990` | `bound_state`、candidate timestamps、`audit_log` | 不写 `status`、`solution`、`final_result` 或 terminal evidence。`bound_state` 是进度/诊断面，不能把弱记录变强。 |
| `mark_candidate_started` | `src/search/exact_campaign.py:1997-2026` | candidate `RUNNING`、attempts/timestamps、清 `solution`；强状态 no-op | 弱记录启动时剥离 solution；强记录不降级。不能从弱记录继承 stale witness。 |
| `mark_candidate_result` | `src/search/exact_campaign.py:2028-2135` | candidate `status`、`solution`、`proof_summary`、cuts/counters | fresh solution 与非 certified no-solution 规则前置；强↔强冲突 raise；强→弱 audit + return。不能让弱/陈旧 solution 穿成强证据。 |
| `update_candidate_running_proof_summary` | `src/search/exact_campaign.py:2137-2160` | RUNNING 记录的 `proof_summary` 与 timestamp | 仅当当前 status 为 `RUNNING` 才写；不写 `status/solution/final_result`。`proof_summary` 不是强状态来源。 |
| `mark_campaign_stopped` | `src/search/exact_campaign.py:2162-2177` | `last_stop_reason`、可选 `final_status`、非 terminal certified 时清 `terminal_frontier_evidence` | 单独写 `CERTIFIED` stop 不足以导出证据；resume/export 必须通过 terminal final_result + frontier evidence 校验。非 certified stop 会清 terminal evidence。 |
| `save` | `src/search/exact_campaign.py:2192-2195` | `updated_at` + atomic JSON write | 不改变证明语义；无 strengthening。 |

`append_candidate_cuts` 与 `set_final_result` 族方法在本快照的 `ExactCampaign` 中不存在；grep 未发现这些方法定义。候选 cuts 只通过 `mark_candidate_result` 落入候选记录；terminal `final_result` 由 `outer_search.py` 的 terminal commit helper 直接写入。

### outer_search.py 对 campaign state 的直接写入

| writer | 位置 | 写入面 | 结论 |
|---|---:|---|---|
| `_mark_certified_campaign_blocked` | `src/search/outer_search.py:161-179` | 清 `final_result/final_status/terminal_frontier_evidence`，再 `UNPROVEN` stop | 降强/清理路径，不能产生强证据。 |
| `_persist_frontier_probe_state` / `_record_probe_candidate_dispatch` | `src/search/outer_search.py:304-354` | top-level `frontier_probe` | 调度 telemetry / resume aid，不在 terminal proof surface。 |
| `_commit_terminal_full_frontier_certified_result` | `src/search/outer_search.py:853-879` | `final_result`、`final_status`、terminal stop、`terminal_frontier_evidence` | 写完后立即调用 project-bound terminal evidence validator；失败 raise，caller 清 certified surface。 |
| `_record_precheck_elimination` | `src/search/outer_search.py:1438-1501` | 通过 `mark_candidate_result(...INFEASIBLE...)` 写候选 | 走 F-01 新 writer guard；不携带 solution。 |
| parallel wave result consume | `src/search/outer_search.py:2193-2374` | 通过 `mark_candidate_result` 写 matched results；失败 stop | 先二次身份校验，畸形波次不写错配结果；非 completed stop 为 UNKNOWN。 |
| serial selected solve consume | `src/search/outer_search.py:2412-2598` | `mark_candidate_started` / `mark_candidate_result` / `mark_campaign_stopped` | 走 campaign writer guard；CERTIFIED 仅写 candidate，不直接发布 terminal result。 |
| `_append_wave_telemetry_best_effort` | `src/search/outer_search.py:1553-1588` | separate campaign telemetry JSON | 捕获异常、只写 telemetry 文件，不是 proof object。 |

### 字段族：deny-unknown 与自由值边界

- Top-level campaign state：`REQUIRED_STATE_FIELDS` 必须存在，见 `src/search/exact_campaign.py:123-141`；未知 top-level 字段允许存在，当前用于 `frontier_probe`、`audit_log` 等扩展面。未知 top-level 字段不被 terminal proof 消费。
- `artifact_hashes`：必须 mapping 且与当前 hash closure 精确相等，见 `src/search/exact_campaign.py:1490-1493`。
- candidate record：required candidate fields 必须存在，见 `src/search/exact_campaign.py:179-190` 与 `src/search/exact_campaign.py:1390-1392`；status 是 deny-enum；`solution` 字段有 status-sensitive deny rule；`proof_summary` 是 mapping 型扩展面；`bound_state` 是自由/diagnostic 面；`exact_safe_cuts` 做 structural + exact-safe semantic validation。
- `last_stop_reason`：普通 stop 只要求 mapping 且含 `reason`，见 `src/search/exact_campaign.py:1496-1499`；terminal `CERTIFIED` stop 走更严格 `_terminal_certified_last_stop_reason_violation`，未知字段拒绝，见 `src/search/exact_campaign.py:309-327`。
- `final_result`：非 None 时必须 mapping，且 `final_status == CERTIFIED`、`declare_mode == strict`，见 `src/search/exact_campaign.py:1500-1512`。terminal certified final_result 顶层字段 deny-unknown，只允许 `ghost_rect/placement_solution/search_status/search_stats`，见 `src/search/exact_campaign.py:58-65` 与 `src/search/exact_campaign.py:1625-1633`；`ghost_rect`、`search_stats`、solution entries 也有各自 unknown-field guard。
- `terminal_frontier_evidence`：要求 schema/source/reason/candidate_generation/domain/counts/digests/frontier keys 与当前 candidates 重算一致，见 `src/search/certified_frontier.py:291-421`。`candidate_generation` 拒未知键，见 `src/search/certified_frontier.py:316-320`；terminal evidence 顶层未知键本身不是 fail reason，但所有 authority-bearing fields 都被重算比对，未知字段被忽略，不能强化证据。
- certified export surface：只要 `final_status == CERTIFIED`、`final_result` mapping 或 `last_stop_reason.status == CERTIFIED` 任一出现，就必须有完整 terminal frontier certified evidence，否则 `_validate_resume_state` 拒绝，见 `src/search/exact_campaign.py:1579-1605` 与 `src/search/exact_campaign.py:1777-1793`。

## Q3: 队列 / 序列化边界穷举

| 边界 | 位置 | 校验/消费 | 结论 |
|---|---:|---|---|
| parent → worker task queue | `src/search/exact_parallel_scheduler.py:457-458` | parent 只 enqueue `WorkerTask`；worker 对 task 没有完整对称 schema validator | task 来源是 parent 内部 builder； malformed task 最多导致 worker crash / UNKNOWN wave，不会绕过 parent result 校验。 |
| worker startup READY / STARTUP_ERROR | `src/search/exact_parallel_scheduler.py:219-244`、`src/search/exact_parallel_scheduler.py:393-431` | READY/ERROR 只影响 pool startup | 不写 campaign proof。startup error fail-closed。 |
| worker heartbeat | `src/search/exact_parallel_scheduler.py:255-270`、`src/search/exact_parallel_scheduler.py:513-516` | heartbeat 被 normalize 后进 `heartbeat_events` | telemetry-only，不写 candidate status/solution/final_result。 |
| worker → parent result queue | `src/search/exact_parallel_scheduler.py:292-322`、`src/search/exact_parallel_scheduler.py:108-138` | `WorkerResult` dataclass + identity/status/solution/error/duplicate guard | sound。错配/errored/重复结果不入 proof-bearing result set。 |
| crash drain / tail drain | `src/search/exact_parallel_scheduler.py:475-490`、`src/search/exact_parallel_scheduler.py:533-556` | 同样调用 `_record_worker_result` | 无旁路。 |
| wave object → outer_search consumer | `src/search/outer_search.py:115-158`、`src/search/outer_search.py:2193-2208` | consumer 侧独立二次校验；畸形 wave 整波 returned results 清空 | no mismatched campaign write。 |
| telemetry append | `src/search/outer_search.py:1553-1588`、`src/search/campaign_telemetry.py:2330` | best-effort JSON telemetry | 不被 terminal proof 消费。 |
| pickle/dataclass round-trip | `WorkerTask` / `WorkerResult` fields | status 以 string 传输，parent 端 exact enum revalidation | 无 enum/string 漂移导致的强证据接受。 |

## Q4: r1 “无 finding” 抽查

### resume hash fail-closed

`compute_exact_artifact_hashes` 绑定 required/optional artifacts；`_validate_resume_state` 要求 `artifact_hashes` mapping 精确等于当前 hash closure，见 `src/search/exact_campaign.py:1490-1493`。`load_or_create` 只有在 `_validate_resume_state` 返回 None 时才 resume，否则以 `reset_reason` 新建空 state，见 `src/search/exact_campaign.py:1818-1866`。这条仍成立。

### terminal export 守卫 / partial worker failure fail-closed

terminal `CERTIFIED` 导出不是单个 candidate `CERTIFIED` 触发。`mark_candidate_result` 明确不提升 `state["final_result"]`，见 `src/search/exact_campaign.py:2119-2124`。只有 `_commit_terminal_full_frontier_certified_result` 会写 terminal surface，并立即 project-bound 验证，见 `src/search/outer_search.py:853-879`；失败后 caller 走 `_mark_certified_campaign_blocked` 清理 certified surface，见 `src/search/outer_search.py:1807-1839`。

parallel partial failure 下，outer_search 会先保存已身份匹配的有效进度和 telemetry，再以 `worker_process_failed` / `UNKNOWN` 停机，见 `src/search/outer_search.py:2342-2374`。这不会导出 terminal result；`best_certified_result` 又要求 project-bound valid terminal full frontier evidence，见 `src/search/exact_campaign.py:2179-2185`。这条仍成立。

## PROJECT_LOCK 复核

`PROJECT_LOCK.md:92-93` 已新增 F78-F-01 / F78-F-02 条款：candidate solution hygiene 与 parallel wave identity binding 均有锁文，且与代码实现一致。

## 冻结工件条款

本轮未修改代码、规则、canonical 内容、生成工件或登记 hash；没有触发冻结工件再生。无期望 sha256/字节数更新项，无登记位置推进清单。
