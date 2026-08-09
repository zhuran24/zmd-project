# Prod-scale Spike Design — Throughput Slant

**Date**: 2026-05-25
**Slant**: throughput (wall / RSS / proto bytes / filter / rotation)
**Origin**: GPT pro audit Finding 5 — mini Step 8 spike toy master (50 BoolVar)
不足以证 prod-scale (266 instance × ~280K pose) build/solve 行为
**Scope**: design only. 不写 implementation, 不 commit, 不 spawn agent.
**Sibling slants**: correctness-paranoid / adversarial-schema / integration /
simplicity — 本 doc 不替它们, main agent 自当 merger.

---

## 0. 设计前提与假设回顾

mini Step 8 (`docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md`)
**只测了 toy master (50 BoolVar)**:
- 10K cuts build 114ms + solve 2ms (INFEASIBLE 早停)
- 5 distinct CP-SAT 形 cover 6 family
- 估 prod-scale build ~5–6s (50× toy)

**这个估计存在多个未验证假设**, 是本 spike 的核心攻击面:

| 假设 | 风险 | 如果错怎样 |
|---|---|---|
| build cost 跟 master var 数量 **线性** | CP-SAT 内 hash/dedup/literal store 可能 **超线性** | prod 50× 估值偏低 10-100× |
| solve 2ms 是 “INFEASIBLE 早停” | 真 sound cut 不会早停, solve 是真 cost | solve 可能 dominate, 不是 build |
| 10K cuts 是合理上限 | LBBD 累积 cut 数没建模 → 可能 >>10K | rotation 必要不是 nice-to-have |
| proto bytesize 不重要 | CP-SAT serialize/clone overhead 跟 proto 大小线性 | RSS / build cost 跟 cuts × scope_size 二次 |
| cache friendly | 280K pose >100 MB → L3 spill 确定发生 | latency-bound 主导 build, 不是计算 |

本 spike 任务: **逐个量化**, 用真 data 跑, 不靠估算。

---

## 1. Perf metrics 必测 (含阈值)

每个 metric 必须 emit 到 `data/research/prod_scale_spike_<scale>.jsonl`, 后续
aggregate 分析。

### 1.1 Wall-clock metrics

| Metric | 测什么 | 阈值 (10K cuts) | 阈值 (50K) | 阈值 (100K) |
|---|---|---|---|---|
| `build_wall_ms` | `model = cp_model.CpModel()` → 全 cut translate 完 → `Solve()` 前 | ≤ 6000 | ≤ 30000 | ≤ 60000 |
| `solve_wall_ms` | `solver.Solve(model)` (real sound cuts, 不是 random) | ≤ 30000 | ≤ 60000 | ≤ 120000 |
| `presolve_wall_ms` | `solver.ResponseProto().solve_log` 里 "Presolve" section | ≤ 30% of solve | ≤ 30% | ≤ 30% |
| `cut_translate_p99_us` | 单 cut translate latency p99 (`Add` call wall) | ≤ 500 µs | ≤ 500 µs | ≤ 500 µs |
| `model_clone_ms` | rebuild path: `model = build_master()` 全建 fresh cost | ≤ 2000 | ≤ 2000 | ≤ 2000 |

阈值依据:
- 6000ms build @ 10K = mini Step 8 估值 (50× toy) 上限 + 安全 margin
- 30s solve = 现 `--max-time-in-seconds=30s` per iteration budget
- presolve > 30% → CP-SAT 在 cut 上花太多 presolve 时间, 可能 nogood explosion

### 1.2 Memory metrics

| Metric | 测什么 | 阈值 |
|---|---|---|
| `rss_peak_mb` | psutil `Process.memory_info().rss` peak during build+solve | ≤ 5000 MB / worker (跟 8.1 cut_store 5GB cap align) |
| `rss_delta_per_1k_cuts_mb` | (peak − baseline) / (cuts/1000) | ≤ 50 MB |
| `model_proto_bytesize` | `model.Proto().ByteSize()` (cuts attached 后) | ≤ 200 MB |
| `cut_body_bytesize_p99` | 单 cut serialize size | ≤ 4 KB |
| `cut_body_bytesize_max` | 单 cut serialize size max | ≤ 64 KB |

阈值依据:
- 5GB cap per worker 来自 `12_go_criteria.md` §8.1 报警阈值
- 200 MB proto = CP-SAT 内部 clone/copy 阶段 RAM peak 跟 proto 线性
- 4 KB p99 / 64 KB max cut body: 防 outlier cut (大 region Hall / 大 multiset)
  scope_size 失控

### 1.3 Distribution metrics

| Metric | 测什么 |
|---|---|
| `cut_body_size_hist` | bytesize 分布 (P50/P75/P90/P95/P99/Max), 按 family 拆 |
| `cut_translate_wall_hist` | per-cut translate wall (P50/P95/P99), 按 family 拆 |
| `cut_scope_size_hist` | `len(literals)` / `len(region_pose_set)` / `len(coeffs)` 分布 |
| `cuts_per_family_count` | F1/F2/F3/F4/F5/F6/F7/F8/F9 各自 count |

**为啥要拆 family**: 不同 family 的 hot path 不同 (F6 region Hall 可能 scope
1000+ pose, F8 per-pose-forbid 永远 scope=1). aggregate 数字会被均值欺骗,
hot family 隐在 P99 里。

---

## 2. Scale ramp 设计 (10K / 50K / 100K)

### 2.1 10K cuts — primary validation point

- mini Step 8 验过 toy, prod-scale 重测
- 跑 3 次取 median (warm-up + measured)
- **必测的**: build_wall + solve_wall + RSS + proto bytesize
- **GO 决策点**: 此 scale 不过, 全 spike 死

### 2.2 50K cuts — stress test

- 反映 LBBD 长跑场景 (1 candidate 几百 iter × 几百 cut/iter)
- 看 super-linear scaling 信号: build 应 ≤ 30s
- **关键测**: presolve_wall_ms 占比 (CP-SAT presolve 在 cut 多时容易爆)
- **此 scale 必触发 active cut filter** 否则单 candidate 撑不完

### 2.3 100K cuts — extreme / break point

- 故意超 production realistic 上限 (~50K 估)
- 找 hard limit: 哪个 metric 先撞墙? build wall? RSS? proto bytesize?
- **不要求过**, 但必须知道死哪
- 给 rotation 策略提供经验数据 (capacity 怎么设)

### 2.4 Scale ramp 顺序

```
10K (3 run) → 50K (1 run) → 100K (1 run)
```
- 10K 多 run 因为是 GO 决策点, 噪声敏感
- 50K/100K 单 run 因为时间成本 + 趋势看清就够

### 2.5 真 cuts 不是 synthetic

mini Step 8 用 synthetic random cuts, 早停假 INFEASIBLE。prod-scale spike 必
须用 **真 oracle 跑出的真 cut**:
- F1-F9 各 oracle 喂真 `data/preprocessed/candidate_placements.json` (53MB) +
  `mandatory_exact_instances.json` (88KB) data
- 每 family 至少 attach 部分占比 (e.g. F5 占 50% 上限 per `12_go_criteria.md`
  §8.1 报警阈值, 防 F5 cut ratio > 50% 触发 stop-ship)
- F5/F8 占大头 (经验), F2/F4 量少但 cert 大
- 真 cut 才能测真 solve cost (而不是 INFEASIBLE 早停的假 2ms)

---

## 3. Active cut filter 设计

### 3.1 为啥要 filter

- 10K+ active cut 全 attach 到 master 每次 solve = build cost 不可控
- CP-SAT 不区分 "新 cut" / "旧 cut", 全 propagate
- 旧 cut 大多 dominated (newer cut 覆盖 + 更紧), keep 它纯 overhead

### 3.2 候选策略 (实测对比)

| 策略 | 描述 | 优点 | 缺点 |
|---|---|---|---|
| **LRU** | 按 last-active-iteration 淘汰 | 实施简单, mem cheap | 可能淘汰核心 cut (上次没 active 但本次 hot) |
| **Score-based** | score = activity_count × age_decay + family_weight | 反映实际 cut 价值 | score 设计需调参, 易 over-fit |
| **Age-only** | 超过 N iter 没 active 就 drop | 简单 deterministic | 全 cut 同等对待, 不反映 cut 质量 |
| **Hybrid** | LRU + score, 满 capacity 才触发 | 灵活 | 复杂 |

### 3.3 推荐 spike 测什么

- **三策略 ablation** in spike: LRU / Score / Hybrid 各跑一次, 比 wall+收敛
- 别在 spike 做 Age-only (太弱, 经验值不需要再验)
- score 公式 spike 用最简: `score = activity_count - 0.1 * (current_iter - last_active_iter)`

### 3.4 Filter wall budget

- 每 master iteration filter wall ≤ 100ms (10K cut 上限测)
- 不能拖累 build (build 6s + filter 100ms = 6.1s 可接受)
- filter 本身是 O(N log N) sort, 100ms @ 10K cut 充裕

### 3.5 Filter 触发时机

- **每 master iteration 前**: 选 active subset attach
- 不动 cut store backing (rotation 是 store 层职责, filter 是 attach 层职责)
- spike emit `filter_wall_ms`, `cuts_attached_count`, `cuts_dropped_count`

---

## 4. Cut store rotation 阈值

### 4.1 跟 filter 区别

- **filter** = 每 iteration 选 active subset attach
- **rotation** = cut store 物理 evict (释放 RAM / 持久化 disk)
- 两层独立: filter dropped cut 仍在 store; rotation evicted cut 物理消失

### 4.2 capacity-based eviction 测什么

依据 `12_go_criteria.md` §8.1: cut_store RSS 逼近 5GB/worker → capacity eviction
触发。

| Metric | 测什么 | 阈值 |
|---|---|---|
| `store_rss_pre_evict_mb` | eviction 触发时 cut_store backing RSS | ≤ 5000 MB |
| `eviction_wall_ms` | 单次 evict 操作 wall (含 RAM 释放 + 持久化 disk) | ≤ 500 ms |
| `evict_ratio` | 单次 evict cut 数 / total store | ≥ 0.1 (太小频繁触发) |
| `evict_recall_rate` | evicted cut 在后续 iter 被 re-emit 比例 | ≤ 0.05 (>5% 说明 evict 错了) |

### 4.3 Sound 怎么验

**关键**: evict 必不能伤 soundness。
- evicted cut 不在 active filter pool → 不影响当前 iter solve
- evicted cut 若被 re-emit (oracle 重新发现), store 必须 dedup (按 cert hash)
  防重复 attach
- spike 必跑一个 invariant check: evict 100 cut, 后续 50 iter 不能出现 master
  违反这 100 cut 的 sol (因为 oracle 必 re-emit)

### 4.4 推荐策略

- **trigger**: store RSS > 4.5 GB OR cut count > 50K
- **evict policy**: 按 score 同 §3.3 (filter 排序的尾部 10%)
- **persistence**: spike 阶段不持久化 disk (单次 process 内测试), production
  defer 到 Phase 1.5+

---

## 5. Hot spot 找法

throughput slant 关键: **不能只用 py-spy / cProfile**, 它们看 CPU time 但
latency-bound 工作负载真瓶颈在 cache miss / memory stall, 不在 instruction
count。

### 5.1 工具栈 (优先级)

1. **`perf stat -e cache-misses,cache-references,L1-dcache-load-misses,LLC-load-misses,LLC-loads`**
   - 跑 spike binary, 测 LLC (L3) miss rate
   - 280K pose registry >100 MB 必 L3 spill, 此命令验证 (per
     `project_workload_latency_bound_not_bandwidth` memory)
   - 阈值: LLC miss rate > 30% → 确认 cache-bound, hot path 必须 cache-blocking 重构
2. **`perf record -e cycles,cache-misses --call-graph dwarf` + `perf report`**
   - 函数级定位 cache miss hot
   - python wrapper → CP-SAT C++ 跨语言 stack 必须 dwarf unwind
3. **`py-spy record --idle --native -o flame.svg --duration 60`**
   - 补充 perf, 看 Python 侧 hot
   - 跟 perf 互补: py-spy 看 wall time, perf 看硬件事件
4. **psutil `memory_info().rss` + `memory_full_info().uss`** sampling 每 0.5s
   - RSS 增长曲线 → 找 build/solve 哪段 RAM 爆
   - USS 排除 shared lib → 真 process owned RAM
5. **`/usr/bin/time -v`** 跑完打总报告
   - max resident set size + page faults (major/minor)
   - minor page fault 多 → glibc malloc arena fragmentation, jemalloc 应已缓解

### 5.2 Hot spot 假设

throughput slant 直觉 hot 在哪 (待验):
- **Build phase** hot: `model.Add(LinearConstraint)` 内部 hash dedup, 跟 cut
  scope_size 平方
- **Solve phase** hot: propagator 跑 cut 时随机访问 280K pose state array →
  L3 spill
- **不在** Python 解释器: GIL contention 在 single-thread CP-SAT 不重要

### 5.3 spike 必产 artifact

- `data/research/prod_scale_perf_<scale>.txt`: perf stat 输出
- `data/research/prod_scale_flame_<scale>.svg`: py-spy flame
- `data/research/prod_scale_rss_<scale>.csv`: RSS sampling 时序

---

## 6. Build vs solve 时间分布

### 6.1 假设 (待 spike 验)

throughput slant 倾向: **prod-scale 后 solve 是 bottleneck, build 不是**。
理由:
- mini Step 8 build 114ms 估 prod 6s, 单次 iter 可接受
- solve 真 sound cut 不早停, 必 propagate 全部 cut → 50K propagator call/sec
  数量级 → propagator latency 直接撞 30s budget
- LBBD 多 iter, build 摊薄 (10 iter × 6s = 60s vs 10 iter × 25s solve = 250s)

### 6.2 怎么 separate 测

- spike 拆 phase emit 各自 wall:
  - `build_master_wall` (build_toy_master 等价 prod registry build)
  - `attach_cuts_wall` (all cuts translate 完)
  - `presolve_wall` (从 solve log 解析)
  - `search_wall` (solve 总 wall − presolve)
- 各 phase RSS delta 单独记
- **关键 ratio**: `solve_wall / build_wall`
  - < 2: build dominant, opt build (cache, incremental rebuild)
  - 2-10: balanced
  - \> 10: solve dominant, opt cut quality / propagator order (本 spike 主关注)

### 6.3 incremental rebuild option

P1.3A plan §1 提 "solve-rebuild 每轮 rebuild model 不是 incremental"。spike
应顺手测 incremental path (只 add 新 cut 不 rebuild) vs full rebuild:
- 若 incremental wall < 50% of rebuild → P1.3A 直接走 incremental
- 若 incremental 触发 CP-SAT presolve invalidation 整体反而更慢 → 保持 rebuild

---

## 7. L3 cache spill 测

### 7.1 为啥确定 spill

- 280K pose registry: per pose ~400 bytes (id + coords + facility_ref) =
  112 MB
- i9-13900KS L3 = 36 MB
- 工作集 / L3 = 3.1× → 100% spill

### 7.2 测具体怎么 spill

- `perf stat -e LLC-loads,LLC-load-misses` 跑 spike, 计 miss rate
- 预期 > 30%, 但具体数字决定 mitigation 价值
- 跟 baseline 比 (e.g. master.solve without cuts) 看 cut attach 增加多少
  spill

### 7.3 Mitigation 设计 (spike 不实施, 但量化收益方向)

| Mitigation | 收益估 | 实施成本 |
|---|---|---|
| pose registry struct-of-arrays (SoA) | -30% spill (热字段集中) | 中 (重构 registry) |
| cut scope 排序 (按 pose_id 连续) | -10% spill (propagator 顺序访问) | 低 (attach 时 sort) |
| pose state bitset 替 int array | -50% spill (8x 密度) | 高 (BoolVar 改 bit) |
| huge page (2MB) for registry | -5% spill (TLB 改善) | 低 (host 已 THP enabled) |

spike 不实施, 但 perf stat 数据决定 P1.3B+ opt 投资优先级。

### 7.4 CachyOS host 状态利用

- THP `[always]` (per CLAUDE.md): 2MB page, TLB pressure 减
- jemalloc LD_PRELOAD: arena fragmentation 减 (helps RSS)
- isolcpus=0-7 P-core: 跑 spike 必 `taskset -c 0-7` pin P-core
- 这些状态 spike 必 inherit (用 `scripts/run_campaign_linux.sh` wrapper 思路)

---

## 8. 量化 GO criteria (P1.3A 进 master 前必满足)

**全 hard gate, 任一不过 BLOCK P1.3A**:

| Gate | 阈值 | 测试 scale |
|---|---|---|
| G1: build_wall_ms | ≤ 6000 | 10K cuts |
| G2: solve_wall_ms | ≤ 30000 (within iteration budget) | 10K cuts, 真 sound cut |
| G3: rss_peak_mb | ≤ 5000 / worker | 10K cuts |
| G4: model_proto_bytesize_mb | ≤ 200 | 10K cuts |
| G5: cut_translate_p99_us | ≤ 500 | 10K cuts |
| G6: 50K cuts build_wall_ms | ≤ 30000 | 50K cuts |
| G7: filter (LRU/Score/Hybrid) 至少一个能把 10K 物理 attach 减至 ≤ 5K 且 sol quality 不退化 | — | 10K cuts |
| G8: rotation eviction 验证不伤 soundness (re-emit dedup work) | invariant pass | 50K cuts |
| G9: LLC miss rate | ≤ 50% (>50% 必先做 mitigation 才进 master) | 10K cuts perf stat |

---

## 9. 量化 NOT GO criteria (任一触发, P1.3A 拒 master 直接接入)

- N1: 10K cuts build_wall_ms > 60000 → 10× 估值偏差, mini Step 8 估算错, 必
  重审 Phase 1.3A
- N2: rss_peak_mb > 10000 / worker → 5GB cap 双倍, 单 worker 撑不住 48GB
  机器 (-p 2 + workers=1 已是当前 production min)
- N3: model_proto_bytesize_mb > 1000 → CP-SAT clone/serialize cost 失控
- N4: cut_translate_p99_us > 5000 → translator 写法有性能 bug, 不是 CP-SAT 问题
- N5: 真 sound cut solve_wall_ms > 120000 → cut 太弱不 prune, propagator
  spin, 必先回 Phase 1.2 加 cut family / 改 cut 强度
- N6: 50K cuts build 超 super-linear (>>50× 10K cost) → CP-SAT 内部 dedup 是
  O(N²), 必须改 incremental 或换 cut 表达
- N7: rotation eviction 后 re-emit_rate > 0.2 → eviction policy 频繁伤 soundness
- N8: 三 filter 策略全 wall > 200ms per iter → filter 本身成 bottleneck, 反
  思 cut 数上限
- N9: LLC miss rate > 80% → 必须先 SoA 重构 pose registry 才进 master,
  阻塞 P1.3A

---

## 10. 工时估

| Phase | Claude pace | wall-clock 死时间 | 总 |
|---|---|---|---|
| Step 1: real cut emit harness (复用 9 oracle 跑 prod data, emit JSONL) | 2h | — | 2h |
| Step 2: prod-scale translator (扩 mini step 8 spike 跑真 master regfistry) | 3h | — | 3h |
| Step 3: 10K cuts run (3 run + perf stat + py-spy + RSS sample) | 30min | 30min (3 run × 10min wall) | 1h |
| Step 4: 50K cuts run (1 run) | 15min | 30min wall | 45min |
| Step 5: 100K cuts run (1 run) | 15min | 60min wall | 1h15 |
| Step 6: filter ablation (LRU/Score/Hybrid × 10K cuts) | 1h | 30min wall | 1h30 |
| Step 7: rotation eviction invariant check (50K with eviction + soundness verify) | 1h | 30min wall | 1h30 |
| Step 8: data aggregate + verdict.md 写完 | 2h | — | 2h |
| **Total** | **~10h Claude pace** | **~3h wall-clock 死时间** | **~13h** |

注: wall-clock 死时间假设 CP-SAT 真跑 (无法压缩)。10K cut 真 solve 数分钟级
不是秒级。

跟 Phase 1.3A spike plan (≤ 3 day, 即 3 working day 人类节奏) 对照, Claude
pace 13h ~= 1.5-2 working session 落地, 跟 plan budget 一致。

---

## 11. 我的 throughput slant 偏向 — 自承认 (per [[design-phase-n-parallel-agents]])

**为啥可能 over-emphasize perf, 忽略 correctness**:

1. **本 design 9 个 metric 全 perf, 0 个 correctness invariant**. 整个 GO
   criteria G1-G9 里只 G8 沾边 soundness (rotation eviction 不伤 sound), 其余
   全 wall/RSS/cache。throughput agent 看不到 cut quality / sol quality
   退化, 容易把 "build 6s + solve 25s" 当 success, 忘记 "solve 25s 但结果
   错" 比 "solve 60s 但 sol 对" 烂多了。
2. **filter 策略 (§3) 完全按 perf 维度选**. score = activity_count -
   age_decay 是 throughput 视角的 cut "价值", 但 correctness slant 会问:
   "drop 一个低 activity 但 unique-cover-edge-case 的 cut, 会不会让 master
   出错 sol?" — 这问题我没问。
3. **rotation eviction (§4)** 我说 "evict_recall_rate ≤ 0.05" 当 sound proxy,
   但只 5% re-emit 也可能是某 critical scenario 100% recall 失败, aggregate
   数字骗人。
4. **Build vs solve 分布 (§6)** 我直觉 solve 是 bottleneck, 是 perf 视角。
   correctness slant 可能反过来: build 6s 累 60s/candidate × 几百 candidate
   = 几小时, 比 solve 单次 25s 更要命。
5. **LLC miss (§7)** mitigation 我列 SoA/sort/bitset, 全 perf opt, 没考虑
   bitset 改 BoolVar 的 sound 影响 (BoolVar → bit 需 CP-SAT API 支持, 不一定
   保持 equivalent semantics)。

main agent merger 时, 应让 correctness-paranoid slant 给 G8-G9 之上加 sound
gate (e.g. "cut store eviction 100% re-emit dedup 验证, 不是 5% recall
proxy")。

---

## 12. 潜在 blind spot (throughput 视角看不到的)

1. **Adversarial cut 形状**: 真 oracle 可能 emit 病态 cut (scope 巨大 / 全 0
   coeff / cert 矛盾), throughput perf 不变但 correctness 崩。adversarial-schema
   slant 该 cover。
2. **Multi-worker 协调**: 当前 spike 设计单 worker scope, 但 `-p 2
   workers=1` production setup 有 2 worker × cut_store。worker 间 cut
   sharing / dedup / sync 没 cover, integration slant 该补。
3. **Phase 1.5+ persistence**: rotation evict 我 defer disk persist, 但
   168h campaign 重启恢复必须能 reload 历史 cut。simplicity slant 可能问
   "为啥不一开始就走 disk?", 答案是 spike cost vs production 区分, 但
   trade-off 没量化。
4. **EXACT_B_DESIGN_V2 env flag rollback**: P1.3A plan §12.1 提 env flag
   切新框架。如果 spike 数据 marginal, rollback 必须 1-line revert, throughput
   设计没说怎么保 rollback 路径。
5. **Cut quality regression**: spike 跑 10K cuts 是 size 上限, 但若 cut
   质量 (master prune 效率) 在 50K 时反而下降 (cut 互相矛盾 over-restrict
   master), perf 看不出来。correctness slant 该测 "cut 加越多 master
   solve 反而越慢" 的反常曲线。
6. **GIL contention multi-thread propagator**: CLAUDE.md 提 thread-safe
   评估 (12.4), throughput spike 单 process 测不到这层。
7. **Real campaign 168h drift**: spike 是 single-process snapshot, 168h 长
   跑 RSS / cut store 累积漂移没测。

---

## 13. 结论 (one-paragraph)

throughput slant 主张: **prod-scale spike 必须用真 oracle 真 cut 真 master
registry 跑 10K/50K/100K 三档**, 测 build/solve wall + RSS + proto bytesize
+ LLC miss + cut translate p99 共 5 类 metric, 设 9 个 hard GO gate + 9 个
NOT GO trigger, 实施 LRU/Score/Hybrid 三 filter 策略 ablation, 顺带验
rotation eviction 不伤 soundness。10h Claude pace + 3h wall-clock 死时间, 落
入 Phase 1.3A 3-day budget。**自承偏 perf 忽略 correctness, 9 GO gate 只 G8
沾 sound, main merger 必让 correctness-paranoid slant 补 sound invariant
gate**。

---

## Appendix A — 跟 mini Step 8 verdict 的对照

mini Step 8 已验:
- 5 distinct CP-SAT 形 cover 6 family ✅
- toy 10K build 114ms ✅
- no AddLazyConstraint dependency ✅

本 spike 在此之上新增:
- 真 master registry (266 inst × 280K pose) 不是 toy 50 BoolVar
- 真 oracle 真 cut 不是 synthetic random
- 加 RSS / proto bytesize / LLC miss 共 5 类 perf metric
- 三 filter ablation + rotation eviction sound 验证
- 10K/50K/100K 三档 scale ramp
- 9 hard GO gate + 9 NOT GO trigger

mini Step 8 caveat #2 (toy 50 BoolVar, prod 5–6s) 本 spike 直接量化, 不再估算。
