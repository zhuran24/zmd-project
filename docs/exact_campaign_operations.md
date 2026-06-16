---
status: CURRENT_CODE_ALIGNED
source_of_truth: code-first; src/search/exact_campaign.py, src/search/campaign_telemetry.py, scripts/inspect_exact_campaign_state.py
last_verified_against: 2026-04-17
owner: phase3b-exact-endgame
---

# Exact Campaign Operations

> ⚠️ **(2026-06-04)** frontmatter 的 `CURRENT_CODE_ALIGNED` / `last_verified_against: 2026-04-17` 是 Phase 3B 时代标注，自那以后未再复核（CP-SAT 长跑运营面在 cut-family LBBD / B1 pose-bool / Design A-B 演进后可能已漂）。当前现状权威源 = `CLAUDE.md` + `PROJECT_LOCK.md`；本文件的 campaign recovery/resume/reset/telemetry 操作面按其标注日期读、用前对照 `CLAUDE.md` runbook。

这份文档覆盖 Phase 3B 的 B1 操作面：recovery、resume、reset、telemetry
和 stop-reason 判读。它不改变 exact proof 语义，也不推进 B2/B5/B7。

## 1. 基本原则

- `data/checkpoints/exact_campaign_state.json` 是 campaign 状态入口。
- `data/checkpoints/exact_campaign_telemetry.json` 是波次和诊断入口。
- `data/solutions/certified_delivery_manifest.json` 是 delivery-side 汇总入口。
- 中间调参和长跑应放在 workspace copy；repo 主路径只接受最终冻结证据。
- `UNKNOWN` / `UNPROVEN` 不是成功终态，只是 triage 入口。
- inspector 是只读操作工具，不是 proof source。

## 2. Inspection

运行只读检查：

```bash
python scripts/inspect_exact_campaign_state.py --no-write
```

写出当前 inspector report：

```bash
python scripts/inspect_exact_campaign_state.py
```

默认输出：

```text
.artifacts/phase3b_exact_campaign_inspector/inspection_summary.json
```

检查时重点看：

- `campaign.present`
- `campaign.final_status`
- `campaign.last_stop_reason`
- `campaign.resume_compatible_with_current_hashes`
- `campaign.resume_validation_reason`
- `telemetry.wave_count`
- `delivery_manifest.present`
- `checks[]`

## 3. Clean Start

clean start 适用于没有可恢复 campaign，或已经明确接受 reset 的情况。

典型命令：

```bash
python main.py \
  --mode certified_exact \
  --campaign-hours 1 \
  --parallel-processes 1 \
  --frontier-probe-mode auto \
  --master-seconds 120 \
  --binding-seconds 120 \
  --routing-seconds 120 \
  --benders-max-iter 15
```

clean start 后立即运行 inspector，确认：

- campaign state 已出现
- telemetry 已出现
- stop reason 可读
- 如果结果是 `UNKNOWN` / `UNPROVEN`，证据仍可被 inspector 汇总

## 4. Clean Resume

clean resume 只在 `resume_compatible_with_current_hashes = true` 时使用。

```bash
python scripts/inspect_exact_campaign_state.py --no-write
```

若 inspector 显示兼容，再运行：

```bash
python main.py \
  --mode certified_exact \
  --resume-campaign \
  --campaign-hours 168 \
  --parallel-processes 4 \
  --frontier-probe-mode auto
```

resume 后确认：

- best certified result 没有回退
- telemetry wave count 继续增长
- previous `UNKNOWN` / `UNPROVEN` 候选没有被误当作穷尽证明

## 5. Artifact-Hash Mismatch Reset

只要下面任意 hash 真源变化，就必须接受 reset：

- `rules/canonical_rules.json`
- `data/preprocessed/candidate_placements.json` (required external large artifact in the current lightweight GitHub checkout)
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

Before a certified campaign run from GitHub `main`, restore or regenerate
`data/preprocessed/candidate_placements.json` and verify size `45,773,799`
bytes with SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`. The
previous size `53,594,995` bytes / SHA256
`d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` artifact is
superseded and must trigger `artifact_hash_mismatch` on resume.

reset 不是异常；它是证据链边界。记录时使用这个模板：

```text
reset_reason:
changed_artifacts:
invalidated_benchmark_baselines:
operator_note:
```

如果 inspector 显示 `resume_validation_reason = artifact_hash_mismatch`，
不要用旧 campaign 继续冒充同一条 proof chain。

Community blueprint hints are advisory only. `data/hints/blueprint_2026_05_13_master_hint.json` was generated against the superseded candidate pool, so its stored `pose_idx` values are stale after the 2026-06-12 repair. Because the source community blueprint is not part of this package, regenerate the hint locally with `scripts/blueprint_to_master_hint.py` before using it for performance; stale hints must not be treated as proof evidence and do not affect soundness.

## 6. Worker Failure

并行 worker failure 的目标是保留已完成波次，并让 campaign 仍可读。

发生后检查：

- `last_stop_reason.reason == worker_process_failed`
- `telemetry.aggregate.outcome_counts.worker_process_failed`
- 已存在的 `best_certified_result` 仍可见
- inspector 能读取 campaign 和 telemetry

worker failure 后不要直接扩大并行度。先用低并发 profile 复查是否是配置、
内存压力、worker startup 或候选个案问题。

## 7. Time Budget Exhausted

时间预算耗尽应记录为：

```text
last_stop_reason.reason == campaign_time_budget_exhausted
final_status == UNKNOWN
```

如果已有 best certified result，状态仍应保留 certified evidence，但这不等于
global terminal proof。下一步通常是 resume 或回到 B3 triage。

## 8. Candidate UNKNOWN / UNPROVEN

候选返回 `UNKNOWN` 或 `UNPROVEN` 时必须停下来保留证据。

常见 stop reason：

- `candidate_returned_unknown`
- `candidate_returned_unproven`

检查重点：

- 对应 candidate record 的 `proof_summary`
- telemetry aggregate 的 master/binding/routing 分类
- 是否为 recurring blocker
- 是否需要建立最小复现 fixture

不要把 unresolved candidate 跳过后宣称 `search_exhausted_all_candidates`。

## 9. Handoff Checklist

B1 操作面可交接时应满足：

- inspector 可复跑
- campaign state 缺失、有效、hash mismatch 都能清楚解释
- telemetry 可被独立汇总
- delivery manifest 是否存在可被独立判断
- reset 规则和 stop-reason 处理有明确人工流程
