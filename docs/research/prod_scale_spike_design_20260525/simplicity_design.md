# Prod-scale spike design — simplicity slant

**Date**: 2026-05-26
**Author slant**: simplicity (1/5 parallel design rounds, per
[[design-phase-n-parallel-agents]])
**Trigger**: GPT pro Phase 1.2 audit Finding 5 (HIGH severity) — mini Step 8
spike is API sanity check only, not prod-shaped, can not gate Phase 1.3A.

## 0. 一句话框架

写**一个**脚本 + **一个**真 cert fixture set, 用 **真实 pose registry 但**
**子集 master**, 跑 **5K 真 cut + 1 个 feasible smoke + 1 个 INFEASIBLE smoke**,
盯 **3 个 metric** (build wall / proto bytesize / solve wall). **<500 LOC, ~2-3 day**.
不是 P1.3A 主体, 是把 Finding 5 的 "API sanity ≠ integration path clear" 这
个 risk 一次性补完, 然后真做 P1.3A.

---

## 1. Spike minimum viable subset

Finding 5 的**核心**风险是 mini Step 8 spike 给出的 "5-6s build" 外推是
linear scaling 假设, 没验过任何一个 prod 层数据点. 真 risk 不是 "10K cuts
能不能编译", 是这 3 件:

| Core risk | 是不是真 risk | 最小 evidence |
|---|---|---|
| **R1 prod pose universe 把 build cost / RSS 推爆** (50 BoolVar → 81795 pose, 1600x) | YES | 测 **1 个 prod-pose-count master + 5K cut → build wall + RSS** |
| **R2 真 cert body shape 跟 toy 不同导致 translator 假设崩** (toy F3/F5/F7 6 literal; real F7 可能 200 literal) | YES | 用 **真 oracle 产 cert (≥1 per family, 7 family) replay 进 translator**, 不再 synth random |
| **R3 INFEASIBLE 早停掩盖真 solve 成本** | YES | 加 **1 个 feasible smoke (hand-crafted 简单 master + 1-2 family cut)** 量 solve wall ≠ 0 |

**Minimum viable spike** (3 件全包):

```
spike_prod_shaped.py        # 单文件, ~300-400 LOC
fixtures/
  prod_master_subset.json   # 1 个 dump: real pose registry, master var dict
  cuts_real_5k.jsonl        # 5K 真 cert (per oracle replay, 7 family 混合)
  feasible_smoke.json       # 1 个手工 small feasible master + 3 cut
verdict.md                  # ~150 line, 3 metric table + GO/NOT_GO
```

**3 个 metric — full stop**:

1. **build_wall_seconds** (apply 5K real cut 到 prod-pose master 全过程)
2. **model_proto_bytes** (`model.Proto().ByteSize()`)
3. **solve_wall_seconds** (feasible smoke OPTIMAL 时间, 不是 INFEASIBLE 早停)

不测 RSS (是 nice-to-have, psutil 加进去也行 < 10 LOC, 但 build_wall +
proto_bytes 已经把 "model 巨大" 这个 risk cover, RSS 是 redundant signal).
**如果 simplicity 真要砍, 砍 RSS, 不砍前 3 个**.

---

## 2. 不在 spike scope (defer 到 P1.3A 主体 or P1.3B/1.5+)

**Spike 不做** (理由: 这些是 P1.3A integration 主体, 不是 risk-discovery):

| Defer 项 | 去哪 | 为啥不在 spike |
|---|---|---|
| 真 LBBD 外循环 wiring (cut 生成 → store → master rebuild → resolve) | P1.3A 主体 | spike 关心 "translator + scale" 不是 "loop 正确性" |
| Active cut filter / store rotation policy | P1.3A §step_8 主体 | risk 是 "filter 跟 translator 兼容", spike 验 translator scale 就够; filter 是 P1.3A close gate, 不是入口 gate |
| `by_exterior_watcher` / GHOST cache invalidation | P1.3B §12.3 | 跟 master rebuild 路径正交 |
| Multi-thread propagator safety | P1.3B §12.4 | 当前 spike 全单线程 |
| Real master 跟 outer search frontier 接口 | P1.3A 主体 | spike 只关 master 单 iter rebuild, 不关 outer |
| Full 81795 pose × 266 instance master (真 prod size) | P1.3A 主体 | 见 §3, prod-shaped ≠ prod-size |
| 100K active cut stress | P1.5+ | 当前 cut store rotation 让 active < 10K, 5K 足够 cover P1.3A 入口 |
| Memory leak under repeated rebuild (1000 iter loop) | P1.3A 主体 | 是 long-run risk, 不是入口风险; 单 build cost OK 就 GO 进 P1.3A |

**关键划界**: spike 答 "我可以开始做 P1.3A 主体 implementation 了吗?", 不答
"P1.3A 是不是 close 了". 后者是 P1.3A 自己的 close gate.

---

## 3. "Prod-shaped" 定义

**Prod-shaped ≠ prod-size**. Finding 5 给的修法清单 5 条是 prod-size 加 RSS
加 100K cut stress, 那个会变成 ~3-5 day 大活, 跟做半个 P1.3A 没区别. 我的
slant 是把 "shape" 跟 "size" 切开:

### 必 prod-scale 的维度 (改变这维度可能撞 risk)

| 维度 | toy spike | prod-shaped spike | 为啥必 prod |
|---|---|---|---|
| **pose universe** (每 instance 候选 pose 数) | 5 pose/instance | 真 `candidate_placements.json` 全量 ~308 pose/instance | F6/F1/F9 cut 用 `region_pose_set`, 真数据可能 200-500 pose/region, toy 5 没有暴露任何 region 大小 risk |
| **cert body shape** (literal 数 / 几何 region 大小) | F3 6 literal | 真 oracle 产的 cert (F5/F7 200+ literal, F6 region 50-200 pose, F1 area_overlap 全量) | translator 是按 cert payload literal-by-literal 编 constraint, 真 cert body 是 translator 时间复杂度真主因 |
| **family mix ratio** | 5 family 各 1/5 | 真 oracle 分布 (估计 F5/F7 占 60%, F6 < 10%, F8 trickle) | mix 决定 translator 内部分支命中率 + 平均 constraint complexity |

### 可 sub-scale 的维度 (改变不会改 risk verdict)

| 维度 | toy spike | sub-scale spike (我推荐) | 为啥可 sub |
|---|---|---|---|
| **instance 数** | 10 | 50-80 instance | build cost 主要由 pose 数主导 (linear in BoolVar), 50 instance × 308 pose = 15K BoolVar 已经够把 build cost ramp 出 prod 量级信号 (与 full 266 比 5x, 远大于 toy 50 vs 81795 的 1600x) |
| **active cut 数** | 10K | 5K 真 cut + 5K synth (混合) | linear scaling 已经 mini step 8 verify 过, 真 risk 是 cert body shape 不是 cut count |
| **master 目标函数** | 无 (feasibility) | 简单 max area (避免 prod max_lex 复杂 obj) | spike 不验 solver tuning, obj 复杂度影响小 |
| **outer frontier 接入** | 无 | 仍无 | 跟 master rebuild 正交 |
| **multi-process** | 单进程 | 单进程 | spike 验 build 不验 worker contention |
| **完整 ghost / power / connector / routing constraint** | 简化 demand=1 | 复制 master 的 placement_rule + port 但不复制 routing/power (只用 F8 cut 模拟 power 影响) | routing 是 sub-problem 不是 master, master 真 prod 是 placement + port + ghost; spike 复 placement + port 就 prod-shape |

**最简口径**: spike master = **真 prod `candidate_placements.json` 子集 (50 instance) +**
**真 placement_rule + 真 port constraint + 真 ghost binding cell**, 不接 routing/
power sub-problem (那是 sub-problem side, master 收到的是 F2/F4/F7/F8 cert).

---

## 4. 极简 GO criteria

**3 个全过即 GO** (Phase 1.3A 入口):

| GO #1 | **build_wall < 30s** at 5K real cut + 50-inst prod-pose master |
| GO #2 | **model_proto_bytes < 500 MB** (CP-SAT proto serialize 上限实测约 2 GB, 500 MB 留 4x headroom) |
| GO #3 | **feasible smoke solve_wall > 0.05s** AND **OPTIMAL** (确认 solver 真在 search, 不是 INFEASIBLE 早停; 0.05s 是 "非零" 下限不是 perf 目标) |

不堆其它 metric. 不加 "RSS < N GB" (proto_bytes 已 cover). 不加 "presolve
wall ratio" (P1.3A 主体的 close gate). 不加 "10K/50K/100K ramp" (5K 足够把
linear scaling 抽样验过).

---

## 5. 极简 NOT_GO criteria

**任一即 NOT_GO** (要么改 spike scope, 要么 paradigm 警戒):

- **NG #1** build_wall > 90s — translator 时间复杂度严重 super-linear, 必先
  charactize 哪个 family 撑爆 (大概率 F5/F7 多 literal cert)
- **NG #2** proto_bytes > 2 GB — CP-SAT proto serialize 撞工程 ceiling, P1.3A
  必须先做 cut compression / shared-symbol pool, 不能直接 wire
- **NG #3** translator 在某 family cert 上 throw (KeyError / ValueError /
  cardinality assertion fail) — 不是 perf 风险是 correctness 风险, 立刻
  upgrade 为 P1.2 retroactive fix
- **NG #4** feasible smoke 跑 OPTIMAL 用 > 30s — solver-side risk, master
  CP-SAT 跟 cut 加进去后 solve 性能瓶颈, P1.3A 必先做 solver param tuning
  (workers / linearization / search portfolio) 才能进 wiring

不堆 NOT_GO. 4 条覆盖 "translator broken / model too big / solver too slow /
build too slow" 4 类 risk verdict.

---

## 6. Implementation 量级估 (Claude pace)

| Item | LOC | Wall (Claude pace) |
|---|---|---|
| `spike_prod_shaped.py` 主脚本 (load fixture + apply cut + solve + metric dump) | 250-350 | 0.5 day |
| `fixtures/prod_master_subset.json` (从 `data/preprocessed/candidate_placements.json` cut 50 instance + 真 placement_rule + port) | 80 LOC + dump script 100 LOC | 0.5 day |
| `fixtures/cuts_real_5k.jsonl` (跑现有 F1-F9 oracle 7 family 共 5K cert) | dump script 100-150 LOC (调现有 oracle) | 0.5 day |
| `fixtures/feasible_smoke.json` (手工 5-instance master + 3 family cut) | 50 LOC fixture + 50 LOC builder | 0.25 day |
| `verdict.md` (3 metric table + GO/NG verdict + caveat) | ~150 line | 0.25 day |
| **Total** | **~500-700 LOC + 3 fixture** | **~2 day** |

**Wall-clock 死时间**: real cut fixture dump 跑 oracle 7 family 5K cert 可能
~5-15 min (oracle 不慢但 5K 是 5K), spike 主跑 build + solve ~30-60s 一次,
跑 3-5 次量数据 = 5 min. 总 wall < 30 min, agent 时间是主.

**对比 Finding 5 修法建议 5 条全做**: ~3-5 day (full prod 266 inst + active
filter wiring + 100K stress + RSS + presolve). 我的 simplicity 版砍掉 **不**
**影响 GO/NOT_GO verdict** 的维度, 时间砍到 1/3-1/2.

---

## 7. Vs over-engineering 自检

**3 个最容易 over-engineer 的方向 + 我的 minimal 反方向**:

### Over #1: 把 spike 做成 "Phase 1.3A 完整 master integration 半成品"

**症状**: spike 接 LBBD 外循环, spike 跑真 outer frontier, spike 跑 multi-
process. **代价**: 3 天变 3 周.
**Minimal 反方向**: spike 只 build → apply cut → solve **一次**, 不循环.
P1.3A 主体处理循环.

### Over #2: 把 metric 堆到 10+ 个 "为完整测所有 risk"

**症状**: 加 RSS / presolve wall ratio / linearization stat / propagator
callback count / Phase-by-phase build profile / model.Proto sub-component
breakdown.
**代价**: spike script 500 LOC → 2000 LOC, verdict.md 150 line → 800 line,
review burden 变 P1.3A 自己 close gate 等级.
**Minimal 反方向**: 3 个 metric. 任一 NG 触发再 ad-hoc 加 profile, 不预先堆.

### Over #3: fixture build 自动化变成框架

**症状**: 写 fixture generator framework, factory pattern, schema validate
generator, YAML-driven fixture variant matrix. **代价**: fixture 本身 200
LOC, framework 800 LOC.
**Minimal 反方向**: fixture 用现有 oracle 的 dump 一次性 generate, 写入
jsonl/json, 之后 spike `json.load` 读. fixture 是数据不是代码. 第二次需要变
体直接复制 fixture file 改 attribute, 不写 framework.

---

## 8. 我 simplicity slant 偏向 — 自承可能 under-cover 的 risk

我这版砍掉了 4 件东西 (full prod size / RSS / 100K stress / multi-iter loop),
每件对应一个可能 miss 的 risk:

| 砍掉 | Potentially missed risk | 我为啥赌 OK |
|---|---|---|
| **Full 266 inst prod** (我做 50 inst) | 266 inst 比 50 inst 多 5x BoolVar, 如果 build cost super-linear (非 O(n)), 50 inst GO 但 266 inst 撞 NG | mini step 8 已 verify 10K cut 线性 (114ms / 10K = 11.4µs/cut), 主因是 cert body 不是 BoolVar 数; 5x BoolVar 放大 ≤ 2x build wall, 30s GO 至少 60s 余量, 50 inst 拿 GO 后 266 inst 大概率也 GO. **如果 50 inst 已经撞 NG, 266 一定撞 → spike 仍然 catch risk, 只是 GO false-positive 风险存在** |
| **RSS** | proto_bytes < 500 MB 但实际 solver 内存翻倍 (build 一份 + presolve 一份) RSS > 10 GB 撑爆 47 GB | proto_bytes 跟 solver in-memory 约 2-4x linear correlation, 500 MB proto 对应 RSS ≤ 4 GB, 远低于 47 GB 单 worker cap; 真 RSS 风险是 multi-worker (workers=8 × 4 GB = 32 GB) 那是 P1.3A 主体 OOM 风险 不是 spike 入口风险 |
| **100K active cut stress** | 5K 线性 OK 但 100K 命中 CP-SAT 内部 hash table resize / proto serialize buffer ceiling, 退化突然 | 当前 cut store rotation 设计 (per [[gpt-pro-p1-2-in-progress-review]] #3) 让 active < 10K, 5K 是 50% load 已经 cover production 工作点; 100K 是 future Phase 1.5+ scenario |
| **Multi-iter rebuild loop** | 单次 build OK 但 1000 iter loop 撞 memory fragmentation / GC pressure / CP-SAT internal cache pollution | 单 iter build wall 是 master.solve 周期主因; loop 退化是 long-run risk, P1.3A close gate (跑真 LBBD 几小时) 自然 catch; spike 入口风险只是 "单 iter 能不能" |

**Simplicity slant 的 systematic blind spot**: 我倾向 "linear scaling 假设
成立, GO 后撞 NG 再说" — 这在 toy 已经 verify 过 linear 的项目 (mini step 8)
合理, 在没 verify 过的项目危险. 这次 OK 因为 mini step 8 + Finding 5 已经
告诉我们 10K cut 是 linear, prod-pose master 是未验. 如果**那**层也非线性,
我这版会放走 risk.

---

## 9. 潜在 blind spot

除了 §8 自承 4 件, 还有 3 个 simplicity slant 容易看不到:

**B1: cert body 真分布我 estimate 错**. 我假设 F5/F7 200 literal, F6 region
50-200 pose. 没真跑过 oracle 量分布. 如果 F7 真 cert body 是 2000 literal,
5K F7 cert 的 translator 工作量是我 estimate 的 10x, build 可能撞 NG.
**Mitigation**: spike 第一步先 dump 5K real cert 后**先量 cert body size
histogram**, < 1 KB code, 喂进 verdict.md table. 这个不是 over-engineering,
是 GO 前必须知道的 ground truth.

**B2: 真 prod master 加 placement_rule + port constraint 后 build cost 主因
**可能不是 BoolVar 数, 是 placement_rule 内 Auxiliary constraint 数**.
50 instance 包含的 placement_rule 复杂度跟 cut translator 是正交 cost.
spike build wall 报数可能 "高" 但是 placement_rule + port 占, 不是 cut. 我
看不出来. **Mitigation**: spike 报两个 build wall — `base_build_wall` (master
only) + `with_cuts_build_wall` (apply cut 后), delta 是真 translator cost.
~5 LOC 加, 必要.

**B3: simplicity 让我倾向只看 wall-clock + bytes**, 没看 solver 内部状态
(presolve 是否触发 / linearization 是否爆 / search portfolio 是否切到 LP).
GO verdict 可能 misleading — wall OK 但 solver 选错 mode. **Mitigation**:
verdict.md 加 1 行 "CP-SAT solver.ResponseStats() 关键字段 dump" (presolve_
time / num_bool / num_int / num_constraints), 不分析, 只 dump 给读者看. ~10
LOC 加.

---

## 10. 跟其它 4 slant 的合点

我没读其它 4 个 slant 的 doc (parallel design, 故意 isolated), 但按 GPT pro
Finding 5 + project context 估其它 slant 多半在以下方向:

| 其它 slant 大概会推 | 我 simplicity 视角 verdict |
|---|---|
| **Correctness-paranoid**: 每 family cert 必有 ≥1 ground-truth assertion (translate 出 constraint 跟手算 reference 比对), 不只 "不 throw" | **必接受**. §5 NG #3 我只防 "throw", 但真 risk 是 translator silently 编错 constraint. 加 7 family × 1 assertion = ~50 LOC, GO 必带 |
| **Throughput-maximizing**: 加 batched build (vector translate), 加 incremental rebuild benchmark vs fresh rebuild | **可 minimal 推迟**. P1.3A 主体决定 solve-rebuild 还是 incremental, spike 入口只验 fresh rebuild 够. throughput slant 想要的 batched/incremental 是 P1.3A optimization, 不是 entry gate |
| **Adversarial-schema**: spike 必跑 malformed cert / oversize cert body / cert version mismatch 的 fail-closed 测试 | **接受 1-2 个 minimal case**. validator 层已经 fail-closed (P1.2 schema gate 已 cover), spike 加 2 个 adversarial case (1 malformed JSON + 1 body 巨大) 防 translator silently 接受 → ~30 LOC. 全套 adversarial matrix (10+ case) 推回 P1.2 retroactive |
| **Integration**: spike 必 dry-run 一次 `benders_loop._run_certified_exact` hook 入口 (env flag toggle), 不只独立脚本 | **可 defer**. integration slant 想要的是 P1.3A 主体的工作, spike 跑独立脚本拿到 build/proto/solve metric 已经把 "API path clear" 这个 Finding 5 的 risk 答完. hook 接进 benders_loop 是 P1.3A 本体, spike GO 后立刻做 |

**总合**: simplicity slant 给的 minimum viable 必须接受 correctness-paranoid
的 "ground-truth assertion per family" + adversarial-schema 的 2 minimal
case, 共 ~80 LOC 加进 §1 的 ~500-700 LOC 估算. throughput / integration slant
的扩展项 minimum 不接受, 推 P1.3A 主体.

最终 spike 规模: **~580-780 LOC + 3 fixture, ~2-3 day Claude pace**. 仍远小
于 Finding 5 修法建议全做 (~3-5 day) 或 P1.3A 主体 (~1-2 week).

---

## 附: 决策 cheat sheet

| 问题 | 我答案 |
|---|---|
| Spike 跑几天? | 2-3 day (Claude pace) |
| Spike 跑多大 master? | 50 instance, 真 prod pose (~15K BoolVar) |
| Spike 跑多少 cut? | 5K real cert + 1 feasible smoke + 2 adversarial |
| 几个 metric? | 3 (build_wall / proto_bytes / solve_wall) + 1 cert-size histogram + 1 stats dump |
| 跟 P1.3A 关系? | 入口 gate, 不是 close gate |
| 不做的最大件事? | full 266 inst + multi-iter loop + 100K cut + RSS |
| 最大 blind spot? | cert body 真分布 estimate 错 → 先 dump histogram 防 |
| 哪些 slant 必接? | correctness ground-truth + adversarial 2 case |
