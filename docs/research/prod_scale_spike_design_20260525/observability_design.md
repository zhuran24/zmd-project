# Prod-Scale Spike — Observability Design

**作者 slant**: observability (N 路并行子代理之一, per
[[design-phase-n-parallel-agents]])
**Date**: 2026-05-26
**Trigger**: GPT pro Phase 1.2 audit Finding 5
(`docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md:257-313`)
**Verdict 写入责任**: main merger, 不在此 doc
**Sibling slant doc**:
- `docs/research/prod_scale_spike_design_20260525/correctness_paranoid_design.md`
- `docs/research/prod_scale_spike_design_20260525/throughput_design.md`

---

## 0. 立场声明 (slant 自白)

我是 observability 视角. 我的主线 thesis:

> **无 observability 的 spike = 黑盒 verdict. 失败时不知道为啥失败,
> 成功时不知道侥幸还是真 robust.**

mini Step 8 spike 已经踩过 (`docs/research/p1_2b_mini_step_8_spike_20260525/`):
输出只有 1 个 `verdict.md` + 1 个 csv-ish table (cuts/build/solve).
跑成 INFEASIBLE 解释为 "random cut collision" — 但**没有任何 internal
trace 能 prove** 是 random collision 而不是 spike harness 自己的 bug,
更看不到 build 那 114ms 到底花在哪 (proto serialize? AddBoolOr 循环?
container resize?). GPT pro Finding 5 严格地讲, "INFEASIBLE 早停掩盖
solve cost" 只是 finding 之一 — 更根本的是 **mini Step 8 没留任何
post-mortem 素材**, 即使 verdict 改 GO 也是不可复审的 GO.

我的偏向:

1. **每个 event 必有 structured emit**. JSON lines, 每行可独立 grep /
   `jq` / pandas-load. 不接受 free-text log 加正则 parse.
2. **每个 metric 必带 unit + range + 触发看的 condition** (per `17_workflow_telemetry §20.5` 设计原则).
3. **post-mortem 优先于 real-time alerting**. spike 跑 ≤ 2h, 不需要
   push notification — 但跑完后任意 metric 异常都能 30 min 内 reconstruct
   是哪个 step / 哪个 family / 哪个 ghost 触发.
4. **dark matter telemetry 是 close gate, 不是 nice-to-have** (per
   [[gpt-pro-p1-2-in-progress-review]] 提的硬闸 + `17_workflow_telemetry §20.2`
   报警阈值).
5. **latency 必须 micro-profile**, 不只 wall clock. 项目是 latency-bound
   (per [[project-workload-latency-bound-not-bandwidth]]), L3 spill / cache
   miss / random pointer chasing 是看不见的杀手 — wall clock 只是后果,
   不是 root cause. py-spy native sample 是必含.

§9 我自己承认 over-instrument 风险, 留 §11 quantify.

---

## 1. Telemetry schema (12 类必 emit 的 event)

每 event 都是 JSON line, append 到 `data/telemetry/spike_prod_scale_<pid>.jsonl`.
**必含公共 field** (所有 event):

```jsonl
{
  "ts": "2026-MM-DDTHH:MM:SS.ffffff",  // ISO 8601 µs 精度
  "ts_mono_ns": 12345678901234,         // time.monotonic_ns(), wall-drift-free
  "pid": 12345,
  "phase": "build|solve|cut_apply|lifecycle|store|watcher|spike_setup|spike_teardown",
  "event": "<event_name>",              // 下面 12 类
  "ghost_id": "ghost_40x40_a|ghost_20x20_b|ghost_8x8_c",  // spike 跑 3 ghost
  "outer_iter": 0,                       // spike 内固定 ≤ 3
  "rss_kib": 12345678,                  // psutil.Process().memory_info().rss / 1024
  "delta_rss_kib": 12345,               // 自上次 sample 差值
  "data": { ... }                       // event-specific payload
}
```

`ts_mono_ns` 是关键 — `ts` ISO 字符串方便人看, 但 wall-drift / NTP skew
会污染 latency 计算. `ts_mono_ns` 用 `time.monotonic_ns()` 保证差值
correct. 落盘**两个都写**, 分析端默认用 mono_ns 算 latency, ts 只展示.

### 1.1 `build_start` / `build_done`

```jsonl
{"event":"build_start","data":{"scale":"10K","cut_count_target":10000,"cut_distribution":{"F1":2000,"F2":1500,"F3":1000,"F4":1200,"F5":1000,"F6":800,"F7":1000,"F8":1000,"F9":500},"bool_var_count_target":81795,"demand_constraint_count_target":266}}
{"event":"build_done","data":{"build_wall_s":58.3,"build_wall_breakdown":{"variable_decl":2.1,"demand_constraint":5.2,"cut_apply_loop":50.0,"proto_finalize":1.0},"bool_var_count_actual":81795,"constraint_count":12345,"proto_bytesize_bytes":456789012,"or_tools_internal_alloc_kib":2345678}}
```

`build_wall_breakdown` 子 field 必拆 (mini Step 8 只有 single
`build_time_seconds`, 看不到 hot spot). `cut_apply_loop` 50s 跟
`variable_decl` 2.1s 是完全不同 root cause.

### 1.2 `solve_start` / `solve_done`

```jsonl
{"event":"solve_start","data":{"presolve_enabled":true,"workers":1,"random_seed":42,"time_limit_s":600,"active_cut_count":10000}}
{"event":"solve_done","data":{"solve_wall_s":172.5,"presolve_wall_s":45.2,"search_wall_s":127.3,"status":"FEASIBLE|INFEASIBLE|UNKNOWN|OPTIMAL","conflict_count":12345,"branches":67890,"propagation_count":1234567,"booleans_remaining_after_presolve":54321,"reason_for_termination":"feasible_found|time_limit|infeasible_proof|unknown"}}
```

`reason_for_termination` 区分 `infeasible_proof` vs `time_limit` — mini
Step 8 INFEASIBLE 是 proof 还是早停, verdict.md 没写, 没法判断.
`presolve_wall_s` / `search_wall_s` 分开 (per §9.2 OR-Tools internal,
presolve 在 81K BoolVar 可能 30%+ build wall).

### 1.3 `cut_add` (每 cut 一行, ≥ 10K 行)

```jsonl
{"event":"cut_add","data":{"cut_id":"f1_region_a_0001","family":"region_capacity","cert_bytesize":234,"literal_bytesize":56,"scope_bytesize":120,"total_bytesize":410,"watcher_dims":["by_cell","by_region"],"watcher_keys_count":{"by_cell":12,"by_region":1},"add_latency_us":230,"store_size_after_add":1234}}
```

`total_bytesize` 跟 `proto_bytesize_bytes` (§1.1) 对账, 求和应 ≈ 后者
减去 variable proto. 不对账 → store 把 cut compress / dedupe 了 (要
log 出来) 或 spike 有 bug.

### 1.4 `cut_quarantine`

```jsonl
{"event":"cut_quarantine","data":{"cut_id":"f7_phs_0042","family":"power_hitting_set","triggered_by_step":6,"reason":"source_digest_mismatch|ghost_changed|blocked_set_changed|artifact_changed|oracle_changed|assumption_changed|validator_unsound|other","detail":{"expected_digest":"f33bd659ff8c2778","got_digest":"stale-human-note-not-canonical-digest"},"action":"hold|quarantine_terminal","latency_us":450}}
```

per [[gpt-pro-p1-2-in-progress-review]] dark matter telemetry 硬闸 +
`17_workflow_telemetry §20.4` 报警阈值: spike 期间若任何 cut
`reason=source_digest_mismatch` 触发 → **abort + 反思 GPT pro Finding 3
patch 没 land 干净**.

### 1.5 `watcher_fire`

```jsonl
{"event":"watcher_fire","data":{"trigger":"ghost_rect_changed|blocked_cell_added|artifact_changed","old_ghost":[10,10,40,40],"new_ghost":[20,20,20,20],"watcher_dim":"by_ghost","affected_cut_count":1234,"lookup_latency_us":45,"replay_latency_total_ms":230,"replay_outcomes":{"active":1100,"hold":120,"quarantine":14}}}
```

`replay_outcomes` 3 数和应 = `affected_cut_count`. 不和 → spike harness
bug. `replay_latency_total_ms` / `affected_cut_count` = avg replay
latency, 跟 `17_workflow_telemetry §20.2 replay_latency_p95_ms` 单测
对账.

### 1.6 `replay_verdict` (per cut, 仅 sample, 见 §3)

```jsonl
{"event":"replay_verdict","data":{"cut_id":"f4_cr_0123","family":"component_reach","step":7,"verdict":"true|false","wall_us":180,"family_dispatch_path":"literal|geometric"}}
```

只 sample 1% cut 全 emit (10K cut → 100 行), 否则 jsonl 爆量. 全量
统计走 §1.7 transition matrix.

### 1.7 `lifecycle_transition_snapshot` (每 store size 翻倍 emit 一次)

```jsonl
{"event":"lifecycle_transition_snapshot","data":{"store_size":1024,"transition_matrix":{"new->active":1000,"new->hold":20,"new->quarantine":4,"active->hold":0,"active->quarantine":0,"hold->active":15,"hold->quarantine":5,"quarantine->none":0},"by_family_active":{"F1":300,"F2":200,"F3":100,"F4":150,"F5":100,"F6":80,"F7":50,"F8":40,"F9":4},"by_family_quarantine":{"F1":0,"F2":0,"F3":0,"F4":0,"F5":2,"F6":0,"F7":2,"F8":0,"F9":0}}}
```

post-mortem 看 transition matrix 就能回答 "spike 跑完为啥 store size
是 X". `by_family_quarantine` 集中在某 family → 那个 family validator
有 regression.

### 1.8 `rss_sample` (background thread, 每 1s)

```jsonl
{"event":"rss_sample","data":{"rss_kib":12345678,"vms_kib":23456789,"shared_kib":1234567,"swap_kib":0,"num_threads":4,"cpu_percent":98.5,"thread_cpu_breakdown":{"main":80.0,"sample_thread":0.5,"or_tools_worker_0":15.0,"or_tools_worker_1":3.0}}}
```

per §9.3 thermal 风险, 同 sample 也 emit `cpu_percent` 跟 `num_threads`,
便于跟 `temp_logger.sh` (CLAUDE.md `scripts/temp_logger.sh`) 输出对齐.

### 1.9 `proto_bytesize_sample` (build/solve 各点 emit)

```jsonl
{"event":"proto_bytesize_sample","data":{"trigger_at":"after_variable_decl|after_demand_constraint|after_1k_cuts|after_5k_cuts|after_10k_cuts|after_solve_done","proto_bytesize_bytes":456789012,"serialize_wall_ms":850,"cumulative_cut_count":10000}}
```

`serialize_wall_ms` 是 `model.Proto().ByteSize()` 本身的 cost (per
§9.2). 50K cuts 时 serialize 自己可能 ≥ 1s, 必单独算.

### 1.10 `cut_body_histogram_sample` (每 scale ramp 后 emit)

```jsonl
{"event":"cut_body_histogram_sample","data":{"scale":"10K","by_family":{"F1":{"count":2000,"cert_bytes_p50":234,"cert_bytes_p95":890,"cert_bytes_p99":1234,"literal_bytes_p50":56,"literal_bytes_p95":120,"scope_bytes_p50":120},"F2":{"count":1500,"cert_bytes_p50":2300,...}}}}
```

mini Step 8 是 random literal toy, 不知道真 distribution. 本 spike emit
这个后, 可跟 prod (Phase 1.5+) 真 distribution 对比 — 若 spike 跟
prod 偏差 ≥ 2× → spike 量纲不对, GO 不算数.

### 1.11 `cut_store_state_dump` (每 outer_iter 一次, ≤ 3 行)

```jsonl
{"event":"cut_store_state_dump","data":{"outer_iter":1,"total":12345,"active":10000,"held":2000,"quarantine":345,"watcher_entries":{"by_cell":98765,"by_pose":87654,"by_group":3210,"by_commodity":150,"by_region":456,"by_ghost":3},"capacity_eviction_count":0,"oldest_cut_age_iter":1,"newest_cut_age_iter":1}}
```

`watcher_entries` 跟 `by_cell_keys / by_pose_keys / ...` 对齐 (`17_workflow_telemetry §20.1`
现 stats). spike 跑完 grep 这 ≤ 3 行就能整段 reconstruct cut store 演化.

### 1.12 `dark_matter_emit` (强制写)

```jsonl
{"event":"dark_matter_emit","data":{"outer_iter":2,"ghost_rect":[10,10,40,40],"subproblem":"spike_master","status":"INFEASIBLE","master_solution_hash":"...","state_digest":"f33bd659ff8c2778","families_tried":["F2","F4","F6","F8","F9","F5"],"empty_reason_by_family":{"F9":"not_area_capacity_overflow","F5":"oracle_timeout_no_verified_core","F2":"oracle_skipped_in_spike","F4":"oracle_skipped_in_spike","F6":"oracle_skipped_in_spike","F8":"oracle_skipped_in_spike"},"witness_blob_path":"data/telemetry/spike_witnesses/iter2.json"}}
```

per `17_workflow_telemetry §20.2`. spike 里 oracle 不真跑 (per
correctness_paranoid §1.3 shortcut), 但 INFEASIBLE 时仍必 emit 这条 —
`families_tried` 全标 `oracle_skipped_in_spike` 是 spike 限制, 不是
spike 漏 — 但**不能不 emit**. 漏 emit → main merger 没法判断这次
INFEASIBLE 是不是 dark matter (spike 真 INFEASIBLE 还是 family 漏检
cover).

---

## 2. Structured logging vs free text (硬选 JSON lines)

**硬选 JSON lines (.jsonl)**, 不接受 plain log text.

| 维度 | JSON lines | Plain log + regex |
|---|---|---|
| 解析成本 | `jq` / `pandas.read_json(lines=True)` 1 行 | 每个分析脚本重写 regex |
| schema 演化 | 加 field 不破坏旧 parse | 加 field 必须改 regex |
| field 完整性 | schema 必填 (§1 每 event 列), missing = bug | 自由文本, 漏 field 静默 |
| 跨 worker 合并 | concat + `jq -s` | 各种 sed/awk hack |
| 历史 precedent | `data/telemetry/subproblem_repeat_<pid>.jsonl` 已 in-use (CLAUDE.md P1 #12 spike) | 项目内已 phased out |

**必含 field 清单** (任何 event 漏 = spike harness bug):

1. `ts` (ISO 8601, µs precision)
2. `ts_mono_ns` (time.monotonic_ns, drift-free)
3. `pid`
4. `phase`
5. `event`
6. `ghost_id`
7. `outer_iter`
8. `rss_kib` (psutil.Process().memory_info().rss / 1024)
9. `delta_rss_kib` (自上次 sample 差值, 首条 = 0)
10. `data` (event-specific dict)

落盘约定:

- `data/telemetry/spike_prod_scale_<pid>.jsonl` — main jsonl
- `data/telemetry/spike_witnesses/iter<N>.json` — dark matter witness blob (§1.12)
- `data/telemetry/spike_profiles/<phase>_<scale>.speedscope.json` — py-spy 输出 (§4)
- `data/telemetry/spike_summary_<pid>.json` — spike 结束后由 aggregator 写, 给 verdict.md 引用

worker-per-file (跟 `subproblem_repeat_<pid>.jsonl` 同 convention) —
即使 spike 单 process, 也按 PID 命名以便未来 multiprocess 扩展.

---

## 3. RSS sample 策略

### 3.1 频率与方式

**1 Hz background thread**, 不在 hot path 内 sample.

```
策略: threading.Thread(daemon=True) → 每 1.0s sample → append 到 jsonl
psutil: psutil.Process().memory_info()  // 标准 API, ~ 100µs / call
落盘: 直接 jsonl write (open(..., 'a')), 不 batch — 因为 1Hz 写入 < 100 B/s
```

| 频率 | 优 | 劣 | 判 |
|---|---|---|---|
| 100 Hz (10ms) | RSS spike 看得清 | 100 µs/call → 1% CPU overhead, hot path interference | ❌ |
| 10 Hz (100ms) | RSS spike 看见 | 10 µs/sec overhead, 可接受 | ⚠️ optional |
| **1 Hz (1s)** | 主流, 落盘 < 100 B/s, post-mortem 够看 | 单次 cut_add (µs 级) 看不到 | ✅ default |
| 0.1 Hz (10s) | 几乎无 overhead | spike 跑 < 100s 时 sample ≤ 10 点, 不够 | ❌ |
| 同步 (only on event) | 准确, 无 thread | 漏 sample 之间的 idle 状态 | ❌ |

**1 Hz default + on key event 强制 sample**. key event = build_start /
build_done / solve_start / solve_done / 每 1K cuts add (per §1.1-1.9
event 已在 `rss_kib` 公共 field 内同步 sample) → 实际 hybrid:
background 1Hz + event-driven.

### 3.2 Background thread 实现要点

```
- daemon=True (主进程退出自动 clean up, 不残留 zombie)
- 用 threading.Event 控制 stop, 不用 while True
- jsonl write 不加锁 (Python GIL + 单进程 append-only, ≤ 4 KiB write atomic)
- 异常 catch + 自 emit error event, 不让 sample thread crash 影响 spike
- 跟主 thread 用同一 file handle? — ✗, 单独 open file handle, line-buffered
```

### 3.3 sample thread 自身 overhead 验证

spike 启动前先跑 30s baseline (无 build / 无 solve), 让 sample thread
跑 → 看 `rss_sample` event 频率, 确认稳定 1 Hz; 看 `delta_rss_kib`
≈ 0 (无操作 RSS 不应漂); 看 main thread `cpu_percent` < 5% (sample
thread overhead 主要 jsonl write, 不应抢 CPU).

若 baseline 不通过 (sample 频率漂 / jsonl write 缺行 / overhead > 5%)
→ **abort, 不交付 spike**. 这是 telemetry 自身 sound 必要条件.

---

## 4. py-spy / cProfile integration

### 4.1 py-spy (主用)

py-spy 是 Rust 写的 sampling profiler, 不需要 attach instrumented binary,
**对 spike 主进程 zero overhead**. 项目历史用过
([[multiprocess-hang-inspect-all]]).

```
启动 spike: 主 shell 进 spike pid
另开 terminal: py-spy record \
  --output data/telemetry/spike_profiles/full_run.speedscope.json \
  --format speedscope \
  --duration 7200 \
  --rate 100 \
  --native \
  --pid <spike_pid>
```

key parameter:
- `--rate 100` (100 Hz sample, 每 10ms 一次) — 比默认 100Hz, 长跑 2h
  ≈ 720K sample, speedscope 文件 ~ 50-100 MB
- `--native` — sample C extension (CP-SAT 是 native, 不开 native 看
  不到 OR-Tools 内部 hot spot, 全 stack 在 `swig::call`)
- `--format speedscope` — 输出 speedscope (https://www.speedscope.app/) 可直接拖入浏览器看 flamegraph

### 4.2 cProfile (辅用, 不替代 py-spy)

cProfile 优势: 精确 call count / cumtime, 可看 build_loop 内 AddBoolOr
具体调多少次. **劣势**: 装饰所有 function 入口出口, **overhead 30-100%**,
会污染 build wall measurement. 故策略:

- **spike main run 不用 cProfile** (用 py-spy).
- **spike 跑完, 在另一个 shell, 单独跑一次 minimal repro (1K cuts) +
  cProfile**, 输出 `spike_cprofile_1k.pstats`, 给 hot function call count
  做 cross-check.

```
python -m cProfile -o data/telemetry/spike_profiles/spike_cprofile_1k.pstats \
  -m spike_harness --scale 1K --no-rss-sample
```

`--no-rss-sample` (spike harness 加 flag) — cProfile run 内关 RSS
sample thread, 因 cProfile 会装饰它扭曲读数.

### 4.3 flamegraph post-mortem

spike 跑完, py-spy speedscope.json 直接给 main merger / next implementer.
关键 hot spot 应看到:

| 期望 hot 区 | 占 sample % expected | NOT GO 信号 |
|---|---|---|
| CP-SAT `Solve` C++ 层 | ≥ 30% (10K cut solve 时) | 不到 5% → spike 没真跑 solve, solve 早停 |
| `model.Add*` Python 层 | 30-60% (build 时) | < 10% → spike 没真 build, mock 了 |
| `lifecycle.step_*` Python 层 | 5-20% | > 40% → step dispatch overhead 失控, 跟 hot path 设计冲突 |
| `psutil.Process.memory_info` | < 0.5% | > 5% → sample 频率太高 |
| `json.dumps` / `file.write` (telemetry) | < 1% | > 5% → telemetry overhead 失控, §11 abort 条件 |

---

## 5. Proto bytesize / cut body distribution

### 5.1 Proto bytesize sample 点

`model.Proto().ByteSize()` 不是 free call (per §9.2, 50K cut 可能 ≥ 1s).
策略: **不每 cut sample, 只 milestone sample**.

per §1.9 `proto_bytesize_sample` event, milestone:

| Milestone | 期望读数范围 |
|---|---|
| `after_variable_decl` | 50-150 MiB (81795 BoolVar pure decl) |
| `after_demand_constraint` | 70-200 MiB (+266 demand constraint) |
| `after_1k_cuts` | 80-250 MiB |
| `after_5k_cuts` | 150-400 MiB |
| `after_10k_cuts` | 200-500 MiB |
| `after_50k_cuts` | 800-2000 MiB |
| `after_solve_done` | same as build done (solver 不改 model proto) |

超过 expected upper bound (e.g. 50K cuts > 2000 MiB) → CP-SAT internal
copy 翻倍后 RSS 撞 §3.3 cap → **NOT GO**.

### 5.2 Cut body histogram (per §1.10)

每 family 至少 5 cert 后 emit 一次 histogram:

```
per family:
  cert_bytesize: [p50, p90, p95, p99, max]
  literal_bytesize: [p50, p90, p95, p99, max]
  scope_bytesize: [p50, p90, p95, p99, max]
  total_bytesize: [p50, p90, p95, p99, max]
```

跨 family aggregate:
- `total_proto_bytesize_share_by_family`: 哪个 family 占 master proto 比例最高
- 期望: F2 cutset / F4 component_reach / F6 shape_packing_hall 占比最大
  (cert 含 bitmap, 几千 byte/cut), F3 port_exposure 最小 (~ 几十 byte)
- 若反过来 (F3 占比最大) → cert serialize 有 bug 或 spike fixture 量纲不对

### 5.3 跟 prod 真分布对比 (validation)

mini Step 8 verdict 外推 "约 50× = 5-6s" 是基于 cut body 同 distribution
假设, 实际 random toy. 本 spike emit §1.10 后, 给出 expected prod
distribution baseline:

| Family | Spike sampled p50 cert byte | prod expected p50 cert byte | 来源 |
|---|---|---|---|
| F1 | 230 | 200-400 (region 4-50 cell) | `src/cuts/families/region_capacity.py` cert schema |
| F2 | 2300 | 2000-8000 (partition bitmap 1000-2500 cell) | `src/cuts/families/cutset.py` |
| F3 | 60 | 50-120 (两 pose id + direction) | `src/cuts/families/port_exposure.py` |
| F4 | 1800 | 1500-5000 (BFS component bitmap) | `src/cuts/families/component_reach.py` |
| F5 | 200 | 100-500 (literal multiset 3-15) | `src/cuts/families/pattern_nogood.py` |
| F6 | 2500 | 2000-8000 (region_pose_set bitmap) | `src/cuts/families/shape_packing_hall.py` |
| F7 | 350 | 300-600 (CoverSet bitmap, post-patch) | `src/cuts/families/power_hitting_set.py` |
| F8 | 400 | 300-700 (disconnect witness, post-patch) | `src/cuts/families/power_grid_reach.py` |
| F9 | 150 | 100-300 (window W + max_allowed_area) | `src/cuts/families/density_envelope.py` |

spike 实测 cert byte 跟 expected 范围**偏差 ≥ 2×** → fixture 量纲不对,
spike 跑通 ≠ prod 跑通, **GO 不算数**.

---

## 6. Cut store state snapshot

per §1.11 `cut_store_state_dump`, 每 outer_iter 一次. spike 跑 3 ghost
≤ 3 行 snapshot, post-mortem 看 cut growth pattern:

### 6.1 必抽查的 invariant

每 snapshot 必验:
- `total == active + held + quarantine` (cut 守恒)
- `sum(by_family_active.values()) == active` (family 分布完整)
- `watcher_entries.by_cell <= total * 50` (per cut 最多触 ~50 cell watcher,
  上界经验值)
- `watcher_entries.by_ghost <= 3` (spike 跑 3 ghost)
- `capacity_eviction_count >= 0`, 单调非减
- `newest_cut_age_iter >= 0`, `oldest_cut_age_iter >= 0`

任一 invariant 不 hold → **abort + 反思 store/watcher 一致性 bug**.

### 6.2 post-mortem 关键问题

aggregator 跑完后看以下问题, 每个必能 answer:

1. **cut 数从哪来?** — `transition_matrix.new->*` 之和 → §1.7 总 add
2. **cut 数为啥这么多?** — `by_family_active` 分布 → 哪 family 主导
3. **held 队列堆多大?** — `held` 跟 capacity rotation 距离
4. **quarantine 集中在哪?** — `by_family_quarantine` → 哪 family validator 在 reject
5. **watcher 内存占比?** — `sum(watcher_entries.values()) * 32B` (估值, dict key + ptr)
6. **rotation 触发?** — `capacity_eviction_count > 0` → 期望 spike 内不应 trigger (10-50K active 在 cap 内)

### 6.3 跟 §1.7 transition matrix 关系

snapshot 是横截面, transition matrix 是流量. 两者 cross-check:

```
snapshot.active[t=N] - snapshot.active[t=0] = 
    sum_{t=1..N} transition_matrix[t].(new->active + hold->active) 
  - sum_{t=1..N} transition_matrix[t].(active->* )
```

不对账 → cut accounting 漏 event, 是比 sound regression 更基础的
spike harness bug.

---

## 7. Dark matter telemetry

per `17_workflow_telemetry §20.2` Phase 1.2 P0-E + [[gpt-pro-p1-2-in-progress-review]]
"dark matter telemetry 硬闸".

### 7.1 spike 内的 dark matter 定义

> spike 主 CP-SAT solve 返 INFEASIBLE, 但 spike 内**没有任何 family
> 应能 explain 这次 INFEASIBLE** (因为 spike fixture 是 oracle 真 emit
> 的 sound cut, 不应自发生成不可解状态).

mini Step 8 verdict 把 INFEASIBLE 解释为 "random cut collision" 是
**未量化 dark matter** — 没说 collision 触哪 family / 是否有 family
应能 explain / explain 不了的为啥不能.

### 7.2 spike 内 emit dark matter 流程 (§1.12 event)

每次 spike master.solve 返 INFEASIBLE:

1. 收集 spike state: `master_solution_hash` (空 / 部分 / cleared) +
   `state_digest` (`compute_source_digest(state)`)
2. **Spike-specific 限制**: 不真调 oracle (per correctness_paranoid §1.3
   shortcut), 但仍 emit `families_tried` = 全 9 family, `empty_reason_by_family`
   = `oracle_skipped_in_spike` 标全.
3. emit `dark_matter_emit` 行到 jsonl.
4. 写 witness blob (state full snapshot) 到
   `data/telemetry/spike_witnesses/iter<N>.json`. blob 含: 当前 active
   cut id list / ghost rect / 哪些 instance 满足 demand / master.Proto()
   主 stat. blob 必能 reproduce — 即把 blob load 回去, spike harness
   能 rebuild 一个 INFEASIBLE master.

### 7.3 报警阈值 (spike 内调整版)

spike 跑 3 ghost × ≤ 3 outer_iter = ≤ 9 INFEASIBLE 触发机会. 触发数:

- 0 次 INFEASIBLE → **可疑 GO** (spike fixture 设计太 weak, solve 全
  trivial FEASIBLE; per correctness_paranoid §3.2 "必须有 FEASIBLE solve"
  反过来也成立 — 也必须**至少触一次** edge case 来验 dark matter path)
- 1-3 次 INFEASIBLE, 全有 witness blob, 全可 reproduce → **GO**
- ≥ 4 次 INFEASIBLE, 但都来自同一 root cause (e.g. fixture 把同 ghost
  cell 双重 block) → **abort + fix fixture**
- 任一次 INFEASIBLE 没 witness blob, 或 blob load 不能 reproduce →
  **abort + 反思 dark matter emit 缺路径**

### 7.4 跟 §1.4 cut_quarantine 区别

- `cut_quarantine`: 单 cut 被 lifecycle step 6 拒掉. 触发数 ≥ 0 任意,
  正常.
- `dark_matter_emit`: master solve 整体 INFEASIBLE, 且 spike 内 family
  集体 silent. 触发数应 ≤ 3 (per §7.3).

---

## 8. Replay verdict trace

per `04_design_invariants` 9 step. spike 跑完每 cut 经历的 step
verdict 必能 reconstruct.

### 8.1 Transition matrix (§1.7)

9 step 简化为 cut 状态机 (NEW / ACTIVE / HOLD / QUARANTINE / EVICTED):

```
NEW    -- step 5 sound + step 6 attach pass --> ACTIVE
NEW    -- step 5 sound + step 6 attach fail (recoverable) --> HOLD
NEW    -- step 5 unsound OR step 6 terminal fail --> QUARANTINE
ACTIVE -- watcher fire + step 6 recheck fail (recoverable) --> HOLD
ACTIVE -- watcher fire + step 5 unsound OR terminal --> QUARANTINE
HOLD   -- next watcher fire + step 6 recheck pass --> ACTIVE
HOLD   -- next watcher fire + terminal fail --> QUARANTINE
ACTIVE -- capacity rotation --> EVICTED
QUARANTINE -- never recover --> QUARANTINE (terminal)
```

§1.7 `transition_matrix` 是 8 个 cell. spike 跑完 aggregate 全 snapshot
transition_matrix sum 得总流量 matrix. Post-mortem 看主对角线 (e.g.
NEW->ACTIVE 主流, 占 ≥ 90%) 跟侧链 (NEW->QUARANTINE 应 ≤ 1%).

### 8.2 per-step latency p-tile

每 step 单独 emit latency, post-mortem 看 p95:

| Step | spike expected p95 | NOT GO (over 2× expected) |
|---|---|---|
| 3 serialize | < 1 ms / cut (大 cert 如 F2 / F6 可 5 ms) | > 10 ms |
| 4 deserialize | < 1 ms / cut | > 10 ms |
| 5 validate | < 5 ms / cut (F2/F4 cutset/component 算 BFS 可 20 ms) | > 50 ms |
| 6 attach-scope | < 100 µs / cut (digest compare + ghost lookup) | > 1 ms |
| 7 evaluate | < 500 µs / cut (per `17_workflow_telemetry §20.2`, stretch ≤ 100 µs) | > 5 ms |
| 8 apply-to-master | < 1 ms / cut (model.Add* C++ 层) | > 10 ms |

每 step latency 单独 emit (per §1.6 sample 1% cut) — post-mortem 算
百分位. p95 超 expected 2× → 该 step hot path 有 bug.

### 8.3 family × step 矩阵

spike 跑完最终 aggregator 输出 9 family × 6 step 矩阵, 每格 p50/p95
latency. 主要看:

- F4 component_reach 在 step 7 evaluate 是否 hot (BFS O(|Grid|), per
  correctness_paranoid §2.5 不优化)
- F8 power_grid_reach 在 step 5 validate 是否 hot (all-pairs power_network,
  per GPT pro Finding 4)
- F2 cutset 在 step 3 serialize 是否 hot (partition bitmap 大)

---

## 9. 量化 GO criteria (observability 视角)

**Observability 自身的 GO criteria**, 跟 correctness_paranoid §3 / throughput §3
互相独立但并列.

### 9.1 Telemetry coverage % (硬 100%)

spike 跑完, jsonl 内每个 event 类型至少出现 1 次 (12 类全 cover):

- `build_start` ≥ 1 (per scale 0/1K/10K)
- `build_done` ≥ 1
- `solve_start` ≥ 1
- `solve_done` ≥ 1
- `cut_add` ≥ 10000 (10K scale 跑过)
- `cut_quarantine` ≥ 0 (允许 0, 但若 cut 加 10K 全 active 也 suspicious)
- `watcher_fire` ≥ 2 (3 ghost - 1 = 2 切换)
- `replay_verdict` ≥ 100 (10K cut * 1% sample)
- `lifecycle_transition_snapshot` ≥ log2(10000) ≈ 13 (size 翻倍)
- `rss_sample` ≥ 1800 (30 min spike * 60s / 1Hz)
- `proto_bytesize_sample` ≥ 6 (build milestones)
- `cut_body_histogram_sample` ≥ 3 (per scale ramp 后)
- `cut_store_state_dump` ≥ 3 (per outer_iter)
- `dark_matter_emit` ≥ 0 (允许 0, per §7.3 也允许触多次)

任一类型 = 0 (除非允许 0 的 quarantine / dark_matter) → **abort, telemetry
设计漏路径**.

### 9.2 Data quality threshold

spike jsonl 跑完 sanity check (单独脚本 `analyze_spike_telemetry.py`):

| 检查 | 阈值 | 不达标后果 |
|---|---|---|
| jsonl 行数 | ≥ 10000 (大头 cut_add) | abort |
| 每行 JSON parse | 100% pass | abort (jsonl 截断 = telemetry 写入 race) |
| 每行 schema validate (§2 必含 10 field) | 100% pass | abort |
| `ts_mono_ns` 严格递增 | 100% (容忍 ≤ 5 行 backward jump 因 sample thread) | warn |
| `delta_rss_kib` 跟前 sample 差值对账 | 100% pass | warn |
| §6.1 cut store invariant | 100% pass | abort |
| §6.3 snapshot ↔ transition matrix 对账 | 100% pass | abort |
| `cut_add.total_bytesize` sum ≈ proto_bytesize | 偏差 ≤ 10% | warn |
| `transition_matrix` cell 之和 ≈ store delta | 偏差 ≤ 5% | warn |
| dark matter witness blob load 后可 reproduce | 100% (若有 emit) | abort |

### 9.3 Post-mortem reconstructability test

spike 跑完, **不看 spike 本身, 只看 telemetry**, 能不能 answer 这 10 个
问题:

1. spike build 80% wall 花在哪个 sub-step?
2. solve 80% wall 是 presolve 还是 search?
3. RSS peak 多少, 何时?
4. 10K cut 时 master proto bytesize 多少?
5. 每 family 平均 cert body 多大?
6. 哪个 family 在 step 5 validate 最慢?
7. watcher fire 时 affected cut 平均多少?
8. 有没有 cut 被 quarantine? 哪 family? 哪 step? 哪 reason?
9. 有没有 dark matter? 触哪 ghost? 能不能 reproduce?
10. lifecycle transition 主流是不是 NEW->ACTIVE? (即 store 不堆 hold)

**10 问全 yes → 9.3 pass**. 任何 ≤ 9 → abort + observability 设计漏路径.

### 9.4 Aggregator 工具交付

spike 跑完必交付:

- `scripts/analyze_spike_telemetry.py` — 跑 §9.2 sanity check, 输出
  `data/telemetry/spike_summary_<pid>.json`
- `verdict.md` 内必 cite §9.3 10 问的 answer (一问一段, 1-3 句)
- speedscope flamegraph (§4) 必交付 + `verdict.md` 必指出 3 个 top hot
  function

---

## 10. 量化 NOT GO criteria (observability 视角)

任一触发 → abort + 反思 observability 设计:

1. §9.1 任一 event 类型 count = 0 (除允许的 quarantine / dark_matter).
2. §9.2 任一 abort 触发条件.
3. §9.3 10 问任一不能 answer.
4. **Telemetry overhead 失控**:
   - jsonl write 占 main thread CPU > 5% (per §4 flamegraph)
   - RSS sample thread overhead > 5% CPU
   - 单 cut_add latency > 10 µs (telemetry 拖 hot path)
5. **Sample thread 自杀**: spike 跑完 jsonl 内 `rss_sample` 不连续
   (gap > 5s) → sample thread crash / GIL deadlock.
6. **Witness blob 不可 reproduce**: dark matter emit 写 blob, blob load
   后 spike harness 不能 rebuild INFEASIBLE master → witness 是假的.
7. **jsonl 文件截断 / 损坏**: 最后 N 行不是完整 JSON → 写盘 race condition,
   spike harness 没 flush.
8. **跨 ghost watcher invalidation 漏 emit**: §1.5 `watcher_fire`
   `affected_cut_count` ≠ aggregator 反查的真实 affected count → store
   集成 bug.
9. **dark matter telemetry 没触发但 INFEASIBLE 发生**: master.solve
   返 INFEASIBLE 但 jsonl 内无 `dark_matter_emit` event → §7 path 漏接.
10. **transition matrix self-inconsistency**: §6.3 cross-check 偏差
    > 5%, 即 cut accounting 漏 event → §1.7 emit 路径漏 hook.
11. **py-spy / speedscope 输出空**: spike 跑 ≥ 30s 但 speedscope.json
    sample count < 1000 → py-spy attach 失败, hot spot 不可见.
12. **§5.3 cut body distribution 跟 prod expected 偏差 ≥ 2×**: fixture
    量纲不对, spike GO 不算 prod GO.

---

## 11. 工时估 (Claude pace, per [[work-time-estimates]])

按 Claude pace. 死时间分开标.

| 段 | Claude 工时 | Wall-clock 死时间 | 备注 |
|---|---|---|---|
| §1 telemetry schema 12 类 event emit hook 实施 | 4-6 h | 0 | 12 类 event, 每个 emit point 嵌入 lifecycle / store / watcher / build / solve, 不重写 src |
| §2 jsonl writer + file rotation 工具 | 1-2 h | 0 | 已有 telemetry path 框架, 加 spike-specific writer |
| §3 RSS sample background thread | 1 h | 0 | threading.Thread + psutil + jsonl |
| §3.3 baseline sample thread overhead 验证 | 0.5 h | **30s wall** | spike 启动前必跑 |
| §4 py-spy / cProfile harness | 1-2 h | 0 | 写 shell wrapper attach 主 spike pid |
| §5 proto bytesize milestone emit + cut body histogram | 2-3 h | 0 | 9 family fixture sample + p-tile compute |
| §6 cut_store_state_dump + invariant check | 1-2 h | 0 | 直接调 CutStore.stats() 包装 |
| §7 dark_matter_emit hook + witness blob writer | 2-3 h | 0 | 嵌入 spike main loop INFEASIBLE 后 |
| §8 replay verdict 1% sample + latency p-tile | 1-2 h | 0 | 嵌入 lifecycle step dispatch |
| §9 `analyze_spike_telemetry.py` aggregator | 3-4 h | 0 | sanity check + summary json + verdict.md auto-cite §9.3 10 问 |
| §10 NOT GO abort hook (每 abort 触发 + early exit) | 1-2 h | 0 | spike harness 检测 + exit 1 |
| spike full run (3 ghost × 0/1K/10K scale) telemetry 收集 | 1 h Claude | **2-4 h wall** | spike 主 solve cost, agent 等结果 |
| spike rerun 50K scale (per correctness_paranoid §3.3) | 0.5 h Claude | **1-2 h wall** | 单 run 5 min solve, 一次 ramp |
| 收尾 verdict + flamegraph 分析 + analyze.py 跑结果归档 | 2-3 h | 0 | post-mortem 主大头 |
| **合计** | **20-30 h Claude** | **3-6 h wall** | |

**跟 sibling 工时对比**:
- correctness_paranoid §7: 12-22 h Claude + 2-4 h wall
- observability (本 doc): 20-30 h Claude + 3-6 h wall

我比 correctness 多 8 h, 主因 §1 12 类 event emit hook 散落多个文件
(lifecycle 4 处 + store 2 处 + watcher 1 处 + build/solve 2 处 + spike
main 3 处), 加 §9 aggregator. correctness slant agent 默认假设 spike
verdict 是 hand-written, 我假设 verdict.md 是 aggregator auto-gen + 人
工审一遍.

**关键 trade-off**: spike 主大头死时间 (solve wall) 不动. observability
overhead 加到 Claude 工时, 不延 wall clock. 仍 1-2 day 日历.

---

## 12. 我的 observability slant 偏向 (main merger 看这段)

### 12.1 为啥可能 over-instrument 拖慢 spike

我列了 12 类 event, 每 cut_add 都 emit 一行 (10K-50K 行). 风险:

1. **jsonl write 累计 overhead**: 10K cut_add * (~150 byte / line + write
   syscall) ≈ 1.5 MB / sec * fsync ≈ ≥ 100 µs / cut. **若 cut_add 本身
   100 µs**, telemetry 翻倍 latency → 污染 build wall measurement, 让
   correctness_paranoid §3.1 (build ≤ 60s) 不可信.
   - mitigation: spike 内用 `line-buffered open` + 不 fsync, OS 后台
     flush. write syscall amortized < 10 µs / line. 落盘损失风险 ≤ 1s
     最后内容, post-mortem 可接受.
2. **RSS sample 1Hz × 30 min = 1800 行**: 微. 但加 thread context switch
   overhead, 跟 OR-Tools `--native` py-spy 一起会扭曲. mitigation:
   §3.3 baseline 验, 不达标 abort.
3. **py-spy --rate 100 --native** 在长跑 7200s 大约 720K sample,
   speedscope.json ≈ 100 MB. 解析 + 浏览器 load 不卡, 落盘 100 MB 不爆.
4. **§1.6 1% replay_verdict sample + §1.7 size 翻倍 snapshot**: 已经
   主动减量. 但仍可能漏关键 transition (e.g. burst quarantine in 100
   cuts 内). mitigation: §1.4 cut_quarantine 是 100% emit (不 sample),
   quarantine 漏不了.
5. **§1.10 cut_body_histogram_sample 每 scale 1 次**: 不算 hot. 不
   over.
6. **§6 cut_store_state_dump 每 outer_iter 一次**: 3 行总. 不 over.

整体: **§1.3 cut_add 是 over-instrument 单点风险**. 若 §3.3 baseline
overhead 测出 > 1% → 把 cut_add 改成 batch (每 100 cut emit 一次
summary 行 + 单 cut 不 emit). spike harness 留 flag `--full-cut-trace`
default off, on 时全 emit (debug 模式).

### 12.2 我有可能 over-cautious 的地方

- **§1.7 transition matrix size 翻倍 emit**: log2(10000) ≈ 13 行只. 但
  我可能 over — store size 不一定纯增, capacity rotation 后会减, 翻倍
  trigger 失效. mitigation: 加 fallback "每 1000 cut 强制 emit 一次"
  即可, 不动主路径.
- **§9.1 coverage % 硬 100%**: 我坚持因 telemetry 漏 event = post-mortem
  漏 path. simplicity slant 可能 argue 6-8 类 event 覆盖足够. 我反对
  因为 12 类 each 都对应一个 post-mortem 问题 (§9.3 10 问).
- **§9.3 10 问硬性**: 我列 10 问是为 force aggregator + verdict.md 不
  hand-wave. 但 10 问可能有冗余 (e.g. #4 #5 都是 cert body 类). main
  merger 可压成 6-7 问保 trade-off.

### 12.3 哪些 design decision 我倾向 over-cautious (main merger 可以 trade)

- **§3 RSS 1 Hz**: 我说 1 Hz default. throughput slant 可能要 10 Hz
  看 RSS spike 细节. 我反对因 §3.1 表已论证 1 Hz 够 post-mortem +
  overhead 安全. 若 throughput slant 真要 10 Hz, 让他自己负 §11
  baseline overhead 测验.
- **§4 py-spy --rate 100**: 100 Hz 算高. 默认 OK, 但若 spike 跑 < 1h,
  --rate 200 也可接受. 让 throughput slant 提决定.
- **§7.3 dark matter 触发数允许 1-3**: 我宽松, 因 spike 是 exploration.
  correctness_paranoid §3.5 / §4 可能更严 (期望 0 次 dark matter, 任
  一触发即 abort). 我让步 — 用 correctness 严的版本也 OK, observability
  本身 emit path 不变.

---

## 13. 潜在 blind spot (我承认 observability 视角看不到的)

### 13.1 真 sound regression 我看不到

我看到 telemetry coverage 100% + jsonl 全 schema valid + transition
matrix 一致 — 但这只 prove **telemetry 系统自身 sound**, 不 prove cut
framework sound. F7/F8 facility_cells 漏验 (GPT pro Finding 1/2) /
oracle source_digest 漏写 (Finding 3) 这类 sound bug, telemetry 不出
warning. **correctness_paranoid §3.5 / §4 才管这事**.

### 13.2 真 perf number 是不是 acceptable 我没量化

我说 "build wall 80% 花在哪个 sub-step 必能 answer" — 但 80% 花在
`AddBoolOr` 是 acceptable 还是 disaster? 我看不出. **throughput slant
应该判**.

### 13.3 真 hardware-specific 行为我没动

CLAUDE.md `scripts/temp_logger.sh` 输出 thermal zone 数据, observability
设计未 hook. 若 spike 跑 ≥ 30 min 撞 thermal throttle, py-spy 可能看到
CPU drop 但 root cause 不在 spike. mitigation: 建议 verify slant
并行启 `temp_logger.sh`, 跟 spike jsonl post-mortem 时对齐 `ts_mono_ns`.

### 13.4 跨 process / 跨 worker observability

spike 单 process (per correctness_paranoid §2.9). 但若未来 P1.3B 扩
multiprocess, jsonl 已按 PID 命名 (§2 落盘约定) — 可 concat. **但
跨 worker shared lru_cache / spawn fork 后 RSS double-count 等问题不
在我 scope**. integration slant 应负.

### 13.5 跟 paradigm death timeline 关系

[[paradigm-death-timeline-27-lever]] cut framework 是 paradigm 之外
infra. observability GO **不能解禁** 任何 lever. 跟 correctness_paranoid
§9.5 同声明, 不重复.

### 13.6 我不替 simplicity slant 想

我加 12 类 event + aggregator + py-spy + cProfile + 10 问硬性. simplicity
slant 可能 argue 6 类 event + 1 个 verdict.md 够. main merger trade-off,
我不替他想.

---

## 14. 交付物清单 (spike GO 时 main merger 看的)

spike 跑完 deliver (在 correctness_paranoid §10 之外的 observability
deliverable):

1. `data/telemetry/spike_prod_scale_<pid>.jsonl` — 主 jsonl, ≥ 10K 行.
2. `data/telemetry/spike_witnesses/iter<N>.json` (≥ 0 个) — dark matter witness blob.
3. `data/telemetry/spike_profiles/full_run.speedscope.json` — py-spy flamegraph.
4. `data/telemetry/spike_profiles/spike_cprofile_1k.pstats` — cProfile cross-check.
5. `data/telemetry/spike_summary_<pid>.json` — aggregator auto-gen.
6. `scripts/analyze_spike_telemetry.py` — 跑 §9.2 sanity + §9.3 10 问.
7. `verdict.md` 内含:
   - §9.3 10 问的 answer (一问一段)
   - §10 NOT GO 条件全部 evaluated (即使没触发也列每条 "PASS")
   - 3 个 top hot function (来自 speedscope flamegraph)
   - cross-cite 到 correctness_paranoid / throughput verdict 的对应 number

---

## Cite list (本 doc 引用 file path, grep-verified)

- `docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md:257-313` (GPT pro Finding 5)
- `docs/项目说明/17_workflow_telemetry.md` (现有 telemetry plan, dark matter §20.2 / 落盘 schema §20.3 / 报警 §20.4 / 设计原则 §20.5)
- `docs/项目说明/04_design_invariants.md` (9 step lifecycle / 9 family)
- `docs/项目说明/12_go_criteria.md` (P0 acceptance)
- `docs/项目说明/15_workflow_testing.md` (11 red fixture matrix)
- `docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py` (mini Step 8 spike)
- `docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md` (mini Step 8 verdict)
- `docs/research/prod_scale_spike_design_20260525/correctness_paranoid_design.md` (sibling slant — sound 反射)
- `docs/research/prod_scale_spike_design_20260525/throughput_design.md` (sibling slant — perf ROI)
- `src/cuts/lifecycle.py:438-455` (compute_source_digest)
- `src/cuts/lifecycle.py:1005-1010` (step_8_apply_to_master NotImplementedError)
- `src/cuts/store.py:68+` (CutStore.stats)
- `scripts/temp_logger.sh` (thermal monitor 并行)
- `data/telemetry/subproblem_repeat_<pid>.jsonl` (P1 #12 spike jsonl convention precedent)
