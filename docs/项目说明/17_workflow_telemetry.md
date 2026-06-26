# 17 — Observability / telemetry plan

> **未来/诊断 telemetry 设计**：telemetry 不授予 proof authority，旧 P1.3B 名称按 P1.3 读取。


cut framework 跑起来后, 我们怎么知道在跑正常? Phase 1.1 当前只有单测 (`pytest src/tests/cuts/`) 验 sound, Phase 1.3 真接进 benders_loop 后必须有 runtime metric, 不能等 168h trial 结束才看. 本节定 metric / 落盘 / trigger.

### 20.1 现状 telemetry (已实施)

`src/cuts/store.py::CutStore.stats()` 返 snapshot:
```
{
  "total_cuts": int,       # 总 cut 数 (含 active + held + quarantined)
  "active": int,           # 当前 attach master 的 cut 数
  "held": int,             # held queue 待 replay 的 cut 数
  "quarantined": int,      # validator reject 进隔离的 cut 数
  "by_cell_keys": int,     # 6 dim watcher 各自 key 集合大小
  "by_group_keys": int,
  "by_pose_keys": int,
  "by_commodity_keys": int,
  "by_region_keys": int,
  "by_ghost_keys": int,
}
```
单测里被 exit_criteria ramp report 用. Phase 1.3 接 benders_loop 后要在每 outer iter / benders 内 iter 后 snapshot.

### 20.2 Phase 1.3 production integration metric（实施时）

按 §22 review 实践拆 4 类 (cardinality / quality / latency / safety):

**cardinality (cut 数量/分布)**
- `cut_count_by_family`: dict[F1-F9 → int], 当前 store 中各 family 数
- `cut_count_by_state`: dict[active/held/quarantined → int] (现 stats 已有)
- `cut_generation_rate`: cut 加入速度 / outer iter (诊断 oracle 产 cut 是否健康)
- `cut_per_candidate_dist`: 各 candidate 累积 cut 数分布 (诊断 cut share 是否跨 candidate)

**quality (cut 是否真有用)**
- `cut_active_to_total_ratio`: active / total, 太低 (< 50%) 暗示 quarantine 多 / replay 不通过
- `replay_reject_rate`: replay_cut 返 QUARANTINE / HOLD 占总 replay 比例 (§14.3 revert criterion ≥ 5% → abort)
- `cut_pruning_contribution`: 每 cut attach 后 master.solve UNKNOWN→INFEASIBLE 比例 (Phase 1.5+ 数据)
- `cut_redundancy_rate`: 同 scope/cert 的重复 cut 占比 (high → minimize step 失效)

**latency (hot path, 单位修正 per v2 plan §2.6)**
- `step_7_evaluate_latency_p50/p95/p99`: evaluate dispatch 延迟 (hot path, **p95 ≤ 500µs, stretch goal ≤ 100µs**)
- `replay_latency_p50/p95/p99`: on_ghost_rect_changed 内 replay 延迟 (validator / replay 是 ms 级, 跟 hot path 分开)
- `validator_latency_by_family`: 各 F1-F9 validator 入口延迟 (ms 级, 诊断哪个 family 拖)
- `watcher_query_latency`: 6 dim watcher lookup 延迟 (µs 级)
- `telemetry_write_overhead`: telemetry 落盘 overhead — 必单独量, 不进 hot path, batch-flush 时 < 0.1% wall

**safety (adversarial soundness 指标)**
- `schema_err_count_by_field`: validator schema_err 按字段分布 (high → spec drift)
- `cert_literal_mismatch_count`: F3 cert↔literal multiset 不绑事件 (Step B / Step J 验, 应 0)
- `ghost_agnostic_reject_count`: F2/F4 GHOST_AGNOSTIC reject (Step O 验, 应 0 if no oracle bug)
- `canonical_rules_none_hold_count`: replay 因 canonical_rules None 走 HOLD 的事件 (Step M, 应 0 in production)

**Phase 1.2 P0-E dark matter telemetry (Gemini math review meta-audit 2026-05-23)**

每次 subproblem 返 INFEASIBLE 后:
1. 依次尝试强 family: F2/F4/F6/F8/F9
2. 再尝试 F5 fallback
3. 全部返空 → 写 `data/cuts/telemetry/unexplained_infeasible.jsonl`:

```jsonl
{"iter": 123, "ghost_rect": [x,y,h,w], "subproblem": "routing_v2", "status": "INFEASIBLE",
 "master_solution_hash": "...", "state_digest": "...",
 "families_tried": ["F2","F4","F6","F8","F9","F5"],
 "empty_reason_by_family": {"F9": "not_area_capacity_overflow", "F5": "oracle_timeout_no_verified_core"},
 "witness_blob_path": "data/cuts/telemetry/witnesses/..."}
```

报警阈值 (per acceptance checklist E):
- F5 cut ratio > 50% → stop-ship, 必须补强几何 lift（⚠️ 2026-06-04: F9 几何 lift 已 tight-K quarantine 实质停用，此 remedy 暂不可用、相关 stop-ship 逻辑待 F9 解封，见 PROJECT_LOCK §3A）
- F5 median core size > 40 → 需 minimizer 加强 / 更强 family
- F9/F5 ratio 长期 < 0.2 → density lift 没接上
- unexplained infeasible 连续出现 → 人工复盘提炼 F10
- cut_store RSS 逼近 5GB/worker → capacity eviction, 留 audit trail (不 silent delete)

**psutil RSS per worker emit** (不用逻辑估算, 真 RSS).

### 20.3 落盘 schema (Phase 1.3 落地)

类比 `data/telemetry/subproblem_repeat_<pid>.jsonl` (§P1 #12 cache-trio spike) 的 worker-per-file jsonl:

`data/telemetry/cut_store_<pid>.jsonl` — append 每 5 min snapshot
```jsonl
{"ts":"2026-MM-DDTHH:MM:SS","pid":12345,"outer_iter":47,"benders_iter":3,
 "cardinality":{"total":120,"active":85,"held":30,"quarantined":5,
   "by_family":{"region_capacity":40,"cutset":25,...}},
 "quality":{"active_ratio":0.71,"replay_reject_rate":0.012,...},
 "latency":{"step_7_p95_us":340,"replay_p95_ms":12,...},
 "safety":{"schema_err":0,"cert_literal_mismatch":0,...}}
```

aggregate 工具 (类比 `scripts/analyze_subproblem_repeat_rate.py`):
- `scripts/analyze_cut_store_telemetry.py` (Phase 1.3 加) — 跨 worker pid 合并 + 各 metric 分布报告

### 20.4 trigger / alerting

168h campaign 内不做 push alerting (Phase 3B 项目政策无 telemetry receiver), 但 implementer / 用户主动看的 trigger:

- **24h shadow trial 完**: 必看 cardinality + quality, 若 `replay_reject_rate ≥ 5%` → 不进真 attach trial (§14.3 revert criterion)
- **168h 启动后每 6h 心跳检查**: 看 `cut_count_by_family` 是否各 family 都产, 不是只 F1 / F2 占 99% (oracle 偏 / spec drift 暗号)
- **168h 结束**: 跑 aggregate 脚本, 进 `docs/research/.../telemetry_aggregate/` archive 跟 outcome 关联

### 20.5 设计原则 (避免 metric bloat)

- 加 metric 必能回答 "出问题 我怎么定位" — 不加只 "好看不动" 的 metric
- 每 metric 写入 § 20.2 表时必标 unit + 触发看的 condition + 期望 range
- telemetry 落盘 overhead 必量 (Phase 1.3 perf opt §12.2): 写盘 < 0.1% wall, 否则 batch-flush
- worker-per-file jsonl 不 SQL / 不集中 db — 跨 worker 合并是 offline analyze 脚本的事

---

