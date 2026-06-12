# 终末地 IndustrialPlanner 精确求解器 — evidence persistence r3 review

审查对象：`zmd_f78r3_snapshot_32a25b71.zip`

快照门禁：开工前仅校验并解包指定快照，sha256 匹配用户给定值；未使用文件区其它旧快照包。

```text
32a25b711dcd9b35eb12fc0df1b1e17809492bf7a0a10228406f2dc896abe360  /mnt/data/zmd_f78r3_snapshot_32a25b71.zip
```

解包根：`/mnt/data/zmd_r3_work/project`。zip 内 `project/` 为仓库根。依赖从 `zmd_py313_linux_x86_64.zip` 离线安装到 Python 3.13 环境。

## 结论

**本轮零 soundness finding。**

本轮没有发现崩溃时序、原子写、双进程误启动、audit/telemetry/frontier_probe 隔离相关的 false-CERTIFIED / false-INFEASIBLE / 终局证据强化问题。没有修改源码，因此没有补丁、没有 unified diff、没有冻结工件登记推进项。

本轮刻意不重复 r1/r2 已审结论；只复核 r1/r2 修复后，在“任意 kill / 部分落盘 / 重跑 resume / 多进程写入边界”下，持久化状态是否会比崩溃前作出更强证明主张。

## 审查与实证范围

代码面：

- `src/search/exact_campaign.py`：`atomic_write_json`、`save`、`load_or_create`、`_validate_resume_state`、候选记录校验、terminal evidence 校验、`mark_candidate_started`、`mark_candidate_result`、`mark_campaign_stopped`、`best_certified_result`。
- `src/search/outer_search.py`：终局 commit、parallel wave 前后 checkpoint、worker result 消费、telemetry best-effort、frontier probe 读写。
- `src/search/exact_parallel_scheduler.py`：worker task/result schema、worker 进程入口、队列 drain/respawn/result identity。
- `src/search/certified_frontier.py`：terminal frontier evidence 构造与重放校验。
- `src/search/certified_surface.py`、`src/io/delivery_manifest.py`、`src/io/serializer.py`：终局 public surface 文件的 currentness / disk authority / atomic write。
- `src/search/campaign_telemetry.py`：campaign telemetry 读写与损坏隔离。

## 验证命令

```bash
cd /mnt/data/zmd_r3_work/project
python3.13 -m py_compile \
  src/search/exact_campaign.py \
  src/search/exact_parallel_scheduler.py \
  src/search/outer_search.py \
  src/search/campaign_telemetry.py \
  src/search/certified_frontier.py \
  src/search/certified_surface.py \
  src/io/delivery_manifest.py \
  src/io/serializer.py
```

结果：通过。

```bash
python3.13 -m pytest -q -p no:randomly \
  src/tests/test_exact_campaign_state_soundness.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_bound_state.py \
  src/tests/test_exact_campaign_inspector.py
```

结果：`64 passed in 4.39s`。

```bash
python3.13 scripts/check_p1_2_proof_obligations.py
```

结果：`P1.2 proof obligation check passed: 8 obligations anchored`。

冻结工件复核，仅再生未改内容：

```bash
sha256sum data/preprocessed/candidate_placements.json
python3.13 src/placement/placement_generator.py
sha256sum data/preprocessed/candidate_placements.json
wc -c data/preprocessed/candidate_placements.json
```

结果：再生前后均为

```text
adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0  data/preprocessed/candidate_placements.json
45773799 data/preprocessed/candidate_placements.json
```

全量 `python3.13 -m pytest -q -p no:randomly src/tests` 也已尝试；沙盒执行窗口 10 分钟内未完成，未观测到失败，但本报告不声明全量套件已跑完。

## Crash / corruption probe 摘要

我用临时 project 构造了以下落盘状态并通过 `ExactCampaign.load_or_create(..., resume=True)` 与 `validate_exact_campaign_resume_state(...)` 复验。关键观测如下：

```text
q1_empty_file                                  resumed=false reset_reason=state_json_invalid best=false
q1_truncated_json                             resumed=false reset_reason=state_json_invalid best=false
q1_complete_old_with_temp_residual             resumed=true  status=RUNNING attempts=1 best=false
q2_1_running_resume_before_rerun               resumed=true  status=RUNNING attempts=1 best=false
q2_1_running_after_rerun_start                 status=RUNNING attempts=2 best=false
q2_2_worker_result_not_consumed_queue_lost     resumed=true  status=RUNNING attempts=1 best=false
q2_3_certified_candidate_no_terminal           resumed=true  status=CERTIFIED final_result=false best=false
q2_4_terminal_surface_missing_evidence         resumed=false reset_reason=missing_state_field:terminal_frontier_evidence best=false
q2_4_terminal_evidence_none                    direct=terminal_frontier_evidence_missing resumed=false best=false
q2_4_terminal_evidence_empty_object            direct=terminal_frontier_evidence_schema_invalid resumed=false best=false
q2_4_valid_terminal_after_save                 resumed=true  final_status=CERTIFIED terminal_evidence=true best=true
q2_5_stale_final_result_with_unknown_stop      resumed=false reset_reason=final_status_mismatch best=false
q4_audit_log_non_list_after_blocked_downgrade  resumed=true  candidate_status=CERTIFIED best=false
q4_downgrade_block_statuses                    before=CERTIFIED after_attempt=CERTIFIED
```

这些 probe 覆盖了空文件、截断 JSON、旧完整 checkpoint、残留 temp、RUNNING 残留、worker 队列丢失、候选级 CERTIFIED 但无 terminal commit、terminal 字段缺 evidence、terminal evidence 损坏、终局正常保存、非终局 stop 携带 stale final_result、audit_log 损坏/丢失等形态。

## Q1：原子写与部分写入状态矩阵

`ExactCampaign.save()` 最终调用 `atomic_write_json`。该函数在目标同目录创建唯一临时文件，`json.dump` 后 `flush` + `os.fsync(file)`，再 `os.replace(tmp, target)`，最后对目录做 best-effort `fsync`，并清理残留 temp；见 `src/search/exact_campaign.py:1280-1313` 与 `src/search/exact_campaign.py:2192-2195`。同目录 temp + replace 给出的物理形态是“旧完整文件或新完整文件”，不是半旧半新拼接文件。

| 持久化对象 / 损坏形态 | resume / verifier 行为 | soundness 结论 |
|---|---|---|
| campaign checkpoint 为空文件 | `load_or_create` strict JSON load 抛错，`reset_reason=state_json_invalid`，重建空 state；见 `src/search/exact_campaign.py:1805-1866` | fail-closed；丢进度，不产生 proof |
| campaign checkpoint 截断 JSON | 同上，strict JSON parse 失败后新建空 state | fail-closed |
| campaign checkpoint 完整旧版本 | 若 hash / schema / required fields / terminal evidence 均有效则按旧完整状态 resume；否则 reset。旧非终局状态不会导出 certified；旧终局状态还必须通过 terminal full-frontier 和 project-bound 校验 | 不会比已落盘的旧状态更强；最多回退进度 |
| campaign checkpoint 完整但缺字段 | `REQUIRED_STATE_FIELDS` 包含 `terminal_frontier_evidence` 等核心字段，缺字段返回 `missing_state_field:*`；见 `src/search/exact_campaign.py:125-141`、`src/search/exact_campaign.py:1475-1477` | fail-closed |
| campaign checkpoint 带 CERTIFIED-looking surface 但无 terminal full evidence | `has_certified_export_surface` 命中后若不满足 strict terminal full-frontier evidence，返回 `terminal_certified_frontier_evidence_invalid`；见 `src/search/exact_campaign.py:1579-1605`、`src/search/exact_campaign.py:1777-1789` | fail-closed |
| campaign checkpoint terminal evidence 为 `None` / `{}` / 计数漂移 / digest 漂移 | `terminal_frontier_evidence_violation` 分别报 missing / schema_invalid / count_mismatch / digest_mismatch 等；见 `src/search/certified_frontier.py:291-421` | fail-closed |
| temp 文件残留，canonical checkpoint 仍为旧完整文件 | reader 只读 canonical path；残留 `.exact_campaign_state.json.tmp-*` 不被消费 | fail-closed；probe 证实 bogus temp 被忽略 |
| `os.replace` 前崩溃 | canonical 仍为旧完整文件，temp 残留被忽略 | fail-closed |
| `os.replace` 后、目录 fsync 前断电 | Linux 路径有目录 fsync；Windows/不支持目录 fsync 时最坏表现为旧文件、目标缺失或新文件。目标缺失时 resume 新建空 state；public verifier 要求 canonical campaign state 文件存在且可读 | fail-closed；可能丢进度，不强化 proof |
| telemetry JSON 截断 | `load_campaign_telemetry_payload` 会抛错；`outer_search` 捕获后设置 `reset_campaign_telemetry=True`，telemetry append best-effort 捕获异常；见 `src/search/campaign_telemetry.py:2316-2357`、`src/search/outer_search.py:1553-1589`、`src/search/outer_search.py:1684-1696` | 非 proof；损坏只影响统计/诊断 |
| `audit_log` 损坏或丢失 | `audit_log` 是 campaign state 内字段，不是独立 proof 文件；`get_audit_log` 对非 list 返回空 list；见 `src/search/exact_campaign.py:1992-1995` | 非 proof；不会解除强→弱阻断 |
| `frontier_probe` 损坏或丢失 | `frontier_probe` 是 campaign state 内调度字段；读入只影响 probe candidate 优先级，terminal evidence 不消费它；见 `src/search/outer_search.py:268-321`、`src/search/outer_search.py:715-732` | 非 proof；最坏为调度/可用性问题 |
| `final_solution.json` 部分写 | 使用 `atomic_write_json`；public verifier / manifest builder 要求 final_solution 与 terminal final_result JSON 等价；见 `src/search/certified_surface.py:426-444`、`src/io/delivery_manifest.py:437-463` | fail-closed |
| `optimal_blueprint.json` 部分写 | blueprint writer 走 `atomic_write_json`；manifest/currentness 校验要求 blueprint 匹配 final_result；见 `src/io/serializer.py:129-150`、`src/io/delivery_manifest.py:437-466` | fail-closed |
| `certified_delivery_manifest.json` 部分写 | manifest export 走 `atomic_write_json`；public verifier 对 manifest 缺失/加载错误/currentness mismatch 全部 blocked；见 `src/io/delivery_manifest.py:148-175`、`src/search/certified_surface.py:277-349` | fail-closed |

## Q2：崩溃-重跑时间轴推演

### ① `mark_candidate_started` 写入后、solve 前崩溃

parallel 路径会先对 wave 中候选执行 `mark_candidate_started`，然后立即 `save`，再 dispatch worker；见 `src/search/outer_search.py:2151-2160`。sequential 路径同样在 solve 前 `mark_candidate_started` + `save`；见 `src/search/outer_search.py:2408-2413`。

落盘形态是候选 `RUNNING`、无 `solution`、`finished_at=None`、attempts 已 +1。`_validate_candidate_record` 明确要求 RUNNING 无 finished_at，非 CERTIFIED 不得携带 solution；见 `src/search/exact_campaign.py:1420-1427`、`src/search/exact_campaign.py:1451-1457`。resume 后 `_compute_exact_frontier_state` 只把 CERTIFIED / INFEASIBLE 视为显式证明状态；RUNNING 保留在 potential domain，会重跑；见 `src/search/outer_search.py:626-676`。probe 观测 attempts 从 1 增至 2 只发生在下一次实际 re-dispatch 时，不会形成 proof 主张。

结论：fail-closed，最多重复计算。

### ② worker 完成但 result 未消费，队列内容丢失

worker result 队列不是持久化证据；worker 进程也没有 campaign path。parallel worker 的 `WorkerTask` / `WorkerResult` schema 不包含 campaign state path；worker 调用 `run_benders_for_ghost_rect(..., campaign=None, ...)`；见 `src/search/exact_parallel_scheduler.py:26-64`、`src/search/exact_parallel_scheduler.py:272-289`。coordinator 只有在 `_parallel_wave_result_identity_failure` 通过之后，才把 result 写入 campaign，然后 wave 末尾一次 `save`；见 `src/search/outer_search.py:2193-2208`、`src/search/outer_search.py:2217-2342`。

崩溃在 worker 完成但 result 未消费时，checkpoint 仍是 dispatch 前的 RUNNING wave。resume 后重跑 potential candidate，不会把队列中未落盘结果当成 proof。

结论：fail-closed，丢 work 不丢 soundness。

### ③ `mark_candidate_result(CERTIFIED)` 写入后、terminal commit 前崩溃

候选级 CERTIFIED 记录保存后，checkpoint 可持有 candidate solution，但 `final_result=None`、`final_status=None`、`terminal_frontier_evidence=None`。probe 中 `q2_3_certified_candidate_no_terminal` 被正常 resume，但 `best_certified_result=false`。

这是有意的两层语义：候选级 CERTIFIED 可以作为 incumbent / pruning 证据，但不是 full-frontier terminal export。`best_certified_result` 只有 `has_valid_terminal_full_frontier_certified_evidence_for_project` 为真才返回结果；见 `src/search/exact_campaign.py:2179-2190`。public surface 也会在 terminal evidence 无效时 blocked；见 `src/search/certified_surface.py:195-238`。

结论：不会撑起 terminal proof；继续搜索或等待 frontier exhausted。

### ④ `_commit_terminal_full_frontier_certified_result` 写入后、validator 抛错前崩溃

实际代码顺序不是“先保存 terminal evidence，再验证”。`_commit_terminal_full_frontier_certified_result` 先在内存中设置 `final_result`、`final_status`、stop reason、`terminal_frontier_evidence`，然后调用 `has_valid_terminal_full_frontier_certified_evidence_for_project`，只有 validator 通过后才 `save`；见 `src/search/outer_search.py:853-879`。

因此崩溃夹缝分两类：

- validator 前崩溃：没有 `save`，磁盘仍是旧完整 checkpoint。
- validator 后、save 后崩溃：磁盘为已通过 project-bound validator 的完整 terminal checkpoint。

手工构造“final_result/final_status/last_stop_reason 已经像 CERTIFIED，但 terminal evidence 缺失或损坏”的落盘状态时，resume 分别返回 `terminal_frontier_evidence_missing`、`terminal_frontier_evidence_schema_invalid` 或缺字段 reset；probe 已覆盖 `None`、`{}`、缺字段三种形态。terminal evidence 自身会重算 candidate domain、status counts、status digest、potential domain、frontier、best candidate 与 final candidate；见 `src/search/certified_frontier.py:249-287`、`src/search/certified_frontier.py:291-421`、`src/search/certified_frontier.py:437-458`。

结论：validator 与 save 的非原子性没有形成 false terminal 夹缝；磁盘上只可能是旧状态、有效新状态或被 resume 拒绝的新坏状态。

### ⑤ `mark_campaign_stopped` 与 final save 之间崩溃

`mark_campaign_stopped` 只是内存 mutation；不调用 `save`。若崩溃发生在 stop 与 save 之间，磁盘仍是旧完整 checkpoint。若非终局 stop 被保存，`mark_campaign_stopped` 会在 status/reason 不是 terminal full frontier CERTIFIED 时清空 `terminal_frontier_evidence`；见 `src/search/exact_campaign.py:2162-2177`。

更强的防御在 blocker 路径：`_mark_certified_campaign_blocked` 会先清空 `final_result`、`final_status`、`terminal_frontier_evidence`，再写 UNPROVEN stop 并清理 stale delivery artifacts；见 `src/search/outer_search.py:161-190`。即使构造 stale `final_result` + `final_status=UNKNOWN` 且 `terminal_frontier_evidence=None` 的落盘形态，resume 也会因 `final_status_mismatch` reset；probe 中 `q2_5_stale_final_result_with_unknown_stop` 为 `resumed=false`、`best=false`。

结论：不会把非终局 stop 升格为 terminal proof；最坏保留旧完整状态或 reset。

## Q3：多进程写入独占性

PROJECT_LOCK 的“coordinator-only writer with disjoint candidate waves”在 worker 层是机制，不只是约定：

- `WorkerTask` / `WorkerResult` 都不包含 campaign state path；见 `src/search/exact_parallel_scheduler.py:26-64`。
- worker 调用 Benders 时显式传 `campaign=None`；见 `src/search/exact_parallel_scheduler.py:272-289`。
- campaign 写入只在 `outer_search` coordinator：wave dispatch 前保存 RUNNING，result 消费后写 candidate records，terminal commit 时写 terminal evidence；见 `src/search/outer_search.py:2151-2160`、`src/search/outer_search.py:2217-2342`、`src/search/outer_search.py:853-879`。

双 campaign 进程误启动同一 state 文件时，当前代码没有 pid lock / file lock / 启动互斥检测。这是操作可靠性风险：两个 coordinator 会 last-writer-wins，可能丢掉另一个进程刚写入的 candidate progress 或 telemetry。但本轮没有把它判为 soundness finding，原因是：

1. `atomic_write_json` 用同目录唯一 temp + `os.replace`，两个 writer 不会把 canonical 文件写成交错 JSON；目标最终是某一个 writer 的完整 JSON。
2. 任一完整 JSON 在 resume / public verifier 前都要重新通过 schema、hash、candidate record、terminal evidence、project-bound solution、delivery artifacts currentness、disk authority 校验。
3. terminal evidence 的 status digest 绑定 candidate records 和 certified solution digest；若 last-writer JSON 丢了或改了参与 terminal proof 的 record，digest / potential-domain / best-candidate 校验会失败。
4. 若 last writer 覆盖掉另一个进程的更强进展，结果是弱化或回退进度，不是证明增强。

建议另行作为运维硬化项考虑 lockfile，但在本轮 soundness 审查范围内，缺少双实例锁没有导向 false proof。

## Q4：audit_log、telemetry、frontier_probe 的证据隔离复核

### audit_log

F78-F-01 的强→弱阻断不是依赖 audit_log 持久化实现的。`mark_candidate_result` 在发现 existing status 是 CERTIFIED/INFEASIBLE 且 incoming 是 UNKNOWN/UNPROVEN/RUNNING 等弱状态时，会先追加 audit event，然后立刻 `return`，不会改写原 candidate record；见 `src/search/exact_campaign.py:2058-2079`。如果 `audit_log` 不是 list，代码只是不追加 breadcrumb，但仍然 return，阻断仍发生。

`get_audit_log` 对非 list 返回空 list；见 `src/search/exact_campaign.py:1992-1995`。`_validate_resume_state` 不把 audit_log 当 proof 字段校验；这在本轮看是正确隔离：audit 是可观测性，不是 proof precondition。probe 将 `audit_log` 改成非 list 后，candidate 仍保持 CERTIFIED，resume 通过但 `best_certified_result=false`，没有 terminal proof。

结论：audit_log 截断/丢失最多让诊断 breadcrumb 消失，不会让强→弱覆盖静默生效。

### telemetry

campaign telemetry 是单独 JSON，写入也走 `atomic_write_json`；见 `src/search/campaign_telemetry.py:2330-2357`。读取损坏会抛错，`outer_search` 捕获后将 telemetry reset 为新的 best-effort payload；见 `src/search/outer_search.py:1684-1696`。append 失败也只写入 `last_run_telemetry_error`，不改变 campaign proof state；见 `src/search/outer_search.py:1553-1589`。

结论：telemetry 不进 proof。损坏影响统计与 UI，不影响 terminal evidence。

### frontier_probe

`frontier_probe` 是 campaign state 顶层调度字段，不是独立文件。读写位置在 `_load_frontier_probe_state` / `_persist_frontier_probe_state`；见 `src/search/outer_search.py:268-321`。其消费点只是在 auto probe 模式下优先恢复某个 pending candidate；见 `src/search/outer_search.py:715-732`。

terminal proof 不使用 `frontier_probe`。full-frontier evidence 用 `candidate_generation`、candidate records、status digest、potential domain、frontier 和 final candidate 重算；见 `src/search/certified_frontier.py:249-287`、`src/search/certified_frontier.py:291-421`。因此 frontier_probe 损坏最多影响下一轮先跑哪个候选，或在恶劣 malformed 值下造成可用性异常；不会改变 frontier 完备性主张。

结论：frontier_probe 是调度 telemetry，不是 proof input。

## 末端 public surface 原子性补充

terminal checkpoint 与 `final_solution.json` / `optimal_blueprint.json` / `certified_delivery_manifest.json` 不是同一个跨文件事务。该非原子性被 public verifier 的 currentness / disk authority 兜住：

- terminal campaign 必须有 valid terminal full-frontier evidence；见 `src/search/certified_surface.py:195-238`。
- `final_solution.json` 和 `optimal_blueprint.json` 必须存在且匹配 campaign `final_result`；见 `src/search/certified_surface.py:254-275`、`src/io/delivery_manifest.py:437-466`。
- manifest builder 要求 campaign state 使用 canonical checkpoint，并且传入 payload 与磁盘 checkpoint JSON 等价；见 `src/io/delivery_manifest.py:326-370`。
- public verifier 会重新解析 canonical campaign checkpoint，拒绝 missing / malformed / non-canonical / payload mismatch；见 `src/search/certified_surface.py:529-566`。

所以跨文件崩溃会产生“campaign 已 terminal 但 final artifacts 未写完”、“final artifacts 写完但 manifest 未写完”、“manifest 旧/坏”等中间形态；这些形态均 blocked，不会成为 certified delivery surface。

## 最终判断

本轮从物理写入与时间轴角度未发现新的 soundness 缝。当前实现的核心安全结构是：

1. 单文件 checkpoint 使用 temp + fsync + replace + 目录 fsync 的原子写路径；
2. resume 对 JSON、schema、hash、candidate records、terminal evidence 全部 fail-closed；
3. terminal export 在 save 前完成 project-bound evidence validation；
4. public surface 不信任单个文件，要求 campaign checkpoint、final_solution、blueprint、manifest 同时 current 且相互匹配；
5. worker 进程无 campaign writer 能力，双 coordinator 的 last-writer-wins 最多造成进度回退；
6. audit_log、telemetry、frontier_probe 均被隔离在 proof 之外。

因此结论保持：**本轮零 soundness finding。**
