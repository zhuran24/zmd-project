# Prod-scale spike design — main merger (N=8 parallel slant)

**Build target**: GPT pro audit Finding 5 close. mini Step 8 spike 50 BoolVar
toy + synthetic cuts + INFEASIBLE 早停, 不能当 Phase 1.3A integration close
gate. 此 merger 合并 8 路 parallel design 出 final spike spec.

**8 路 slant** (`docs/research/prod_scale_spike_design_20260525/`):
1. `correctness_paranoid_design.md` — fail-closed soundness + 真 lifecycle
2. `throughput_design.md` — perf metric / scale ramp / active filter / hot spot
3. `adversarial_design.md` — 15 risk inventory + feasible case + bad cert inject
4. `integration_design.md` — 端到端 9 step + 真 master + 6-dim watcher
5. `simplicity_design.md` — minimal viable subset + 反 over-engineer
6. `rollback_safety_design.md` — branch isolation + abort + state sandbox
7. `observability_design.md` — JSON lines 12 event + RSS / py-spy / post-mortem
8. `historical_paradigm_context_design.md` — 27 lever 死法 + 新 paradigm 死法预测

---

## 1. 每路 slant 核心建议摘要

| Slant | 核心 1-2 句 |
|---|---|
| correctness-paranoid | spike 必真 prod scale (81,795 BoolVar) + 真 9-step lifecycle, 0 mock. sound 必 hold + cost cap 两轴. 工时 12-22h Claude. |
| throughput | 5 类 perf metric (build/solve/RSS/proto/LLC miss) + scale ramp 10K/50K/100K + 3 filter ablation (LRU/Score/Hybrid). 工时 10h Claude + 3h wall. |
| adversarial | 15 risk inventory, 主 R3 (INFEASIBLE 早停 — 用 IP v2 blueprint hint 造 feasible + 4 metric branches/conflicts/wall/status), R8 (50 bad / 9950 good cert 混 inject 100% quarantine). 工时 14-22h. |
| integration | 9 step 全真 invoke (0 mock), 真 PoseBoolExactMaster (B1) + 3 candidate × 5 iter pseudo-LBBD, 6-dim watcher 全注册, step 8 是主交付. 工时 17-26h. |
| simplicity | 单文件 ~500-700 LOC + 50 inst subset master + 5K cert oracle replay + feasible smoke fixture, 3 metric / 4 NG, 不接 LBBD 外循环. 工时 2-3 day (~10-16h). |
| rollback-safety | branch-isolated `spike/prod_scale_master_integration_20260526`, 7-10 commit checkpoint, 7-day wall cap, 10 abort criteria, spike GO ≠ prod GO (2 PR 不 cherry-pick). |
| observability | JSON lines 12 类 event + 1Hz RSS thread + py-spy --rate 100 --native, 10 问 post-mortem GO criteria, dark matter telemetry 硬闸. 工时 20-30h (+8h vs correctness 因 12 event hook). |
| historical-paradigm | L12 v8 anchor slicing 是最危险 analog (build improve 真 solve 没量), 预测 cut framework 8 类内部死法 (N1-N8), 1.1+1.2 Layer 2 漏的 pattern 100% 一致, spike 跑完 GPT pro 预测仍 catch ≥ 1 Layer 2 finding. 工时 12-18h. |

---

## 2. 取交集 (≥6 路 strong agreement → 必入)

| 决策 | 几路同意 | 共同理由 |
|---|---|---|
| 真 prod scale (81K BoolVar) 是主路径 | correctness / adversarial / throughput / integration / observability / historical = 6 路 | 50 inst subset 不能 trigger L24 augmented master 30 GB RSS 这类 scale-only 死法 |
| 真 9-step lifecycle 全 invoke, 0 mock | correctness / integration / observability / historical = 4 路明确, 其它路默认接受 | mini Step 8 跳过 step 3-7 + store + replay 是 GPT pro F1/F2/F3 漏 catch 根因 |
| Feasible case 必含 (避免 INFEASIBLE 早停掩盖 solve cost) | adversarial R3 / correctness §3.2 / integration G2 / historical G2 / simplicity §1 = 5 路 | mini Step 8 1K/10K case 全 INFEASIBLE 早停, GPT Finding 5 核心 |
| Multi-iter LBBD ≥ 5 iter | integration G8 / historical G3 / correctness 含 = 3 路明确强调 | L12 v8 / L16 / PCR-CUT P5 / B1 path-2 全死于不收敛, 单 iter 测不出 |
| Step 8 apply_to_master 是 spike 主交付物 | integration §8 / correctness §1.3 / adversarial R7 = 3 路 | lifecycle.py:1005 仍 NotImplementedError, P1.3A 必须填 |
| F1/F2/F3 patch 在 scale 下 still hold (adversarial inject verify) | adversarial R8 / integration G10 / historical = 3 路 | GPT pro 已 catch 同种 bug, scale ramp 后可能复现 |
| RSS sample (psutil 1 Hz background) | observability §1.8 / correctness §3.3 / throughput §1.2 / adversarial R4 = 4 路 | latency-bound 项目 RSS spike 不可见时不可信 |
| 量化 abort criteria + wall cap | rollback / correctness / adversarial / historical = 4 路 | 防止 spike 拖成 1-2 周 implementation 反而 defer P1.3A |
| spike GO ≠ paradigm GO / prod GO | correctness §6.3 §9.5 / historical §10 / rollback §3 = 3 路明确警告 | L12 v8 教训 — build improve 真实但 solve 没量, spike GO 不解禁 27 lever |

→ **核心 9 项共识全入 final spec**.

---

## 3. 各路 strong point unique (slant-exclusive 高 ROI 建议)

下列每条单路提出但 main 评估有价值, 全入或部分入 final:

| Slant | Unique 建议 | 入 final? |
|---|---|---|
| rollback-safety | branch `spike/prod_scale_master_integration_20260526` + 7-10 commit checkpoint + state sandbox + 8 项 off-limits enforce | 全入 (其它路 0 cover branch 策略) |
| rollback-safety | 7-day wall clock 硬上限 + 10 abort criteria 量化 | 全入 |
| rollback-safety | spike GO 2 PR 流程 (doc-only verdict PR + 重写实施 PR, 不 cherry-pick spike code) | 全入 (反 sunk-cost 拖进主线) |
| throughput | 3 filter ablation (LRU / Score / Hybrid score=activity-0.1×age) | 部分入 — spike 只测推荐的 Hybrid, ablation defer P1.3A 主体 |
| throughput | LLC miss rate metric (perf stat cache-misses) — 项目 latency-bound 必测 | 入 — RSS sample + perf stat 双工具栈 |
| adversarial | IP v2 blueprint hint 造 feasible state + 4 metric (branches≥1K / conflicts≥100 / wall≥1s / status≠INFEASIBLE) 验真 solve | 全入 — Feasible smoke 必这么造 |
| adversarial | 50 bad / 9950 good cert 混 inject 验 100% quarantine + active count = 9950 | 全入 |
| integration | 6-dim watcher (by_cell/by_group/by_pose/by_commodity/by_region/by_ghost) 全 dimension 各 ≥1 注册 | 全入 |
| integration | 3 ghost transition 测 held/active/quarantined 状态机 | 全入 |
| integration | sub-route 1 (solve-rebuild) 主路径 + sub-route 3 接口兼容 (1-iter trial) + sub-route 2 (C++) defer P1.3B | 全入 |
| observability | JSON lines schema (12 event 类) | **部分入** — 取 4 必 (RSS / cut_add / replay_verdict / dark_matter), 其它 8 defer P1.3A |
| observability | dark matter telemetry 硬闸 (per `17_workflow_telemetry §20.2`) — spike INFEASIBLE 必 emit witness blob, 不能 reproduce 即 abort | 全入 |
| observability | post-mortem 10 问 (spike 跑完只看 telemetry 必能答 10 问) | 入精简版 (4 问对应 4 必 event 类) |
| historical | L12 v8 anchor slicing 是最近 analog warning, GO criteria 必含 solve-side metric | 全入 (其实跟 multi-iter LBBD 共识合) |
| historical | 预测 cut framework 8 类内部新死法 (N1-N8), spike 必主动 trigger 同类 hidden assumption | 入 — 加 G4 attach success rate + G9 stale invalidation rate + G8 adversarial validator pass 三层 |
| simplicity | "spike 答'可以开始做 P1.3A 主体了吗' 不答'P1.3A 是不是 close'" — 边界严守 | 全入 (作 final spec 序言) |
| correctness | sound 必 hold + cost cap 两轴 (不是 optimization target) | 全入 (cost cap = abort trigger, 不是 GO target) |

---

## 4. Disagreement list + resolve

### D1. Scale: 全量 81K BoolVar (6 路) vs 50 inst subset (simplicity)

- **6 路立场**: 50 inst 不能 trigger scale-only 死法 (L24 augmented master 30 GB)
- **simplicity 立场**: "prod-shaped" ≠ "prod-size", 50 inst 已能验 lifecycle 主路径
- **Resolve**: 主路径走 81K 全量 (consensus). simplicity 的 50 inst subset 作 **failfast probe fixture** (spike 启动前 5-10 min run, 验 harness 自身无 bug, 不替代主测). 工时 +1h, ROI 高 (probe fail 立刻知 spike 自己写错, 不等全量跑 1h 才发现).

### D2. Observability: 12 event class 全 cover (observability) vs 3-5 metric (simplicity)

- **observability 立场**: telemetry 漏路径 → post-mortem 无法 reconstruct → spike 黑盒
- **simplicity 立场**: 12 event 散 4 file 加 hook overhead +8h, spike 自己跑慢
- **Resolve**: spike 取 **4 必 event** (RSS sample / cut_add / replay_verdict / dark_matter_emit) 各 ≥1, 其它 8 类 (build_start/build_done/solve_start/solve_done/cut_quarantine/watcher_fire/lifecycle_transition_snapshot/proto_bytesize_sample/cut_body_histogram_sample/cut_store_state_dump) defer P1.3A 主体. 工时削 ~4h.

### D3. Multi-iter LBBD: 5 iter × 3 candidate (3 路) vs 不接 LBBD (simplicity)

- **3 路立场**: 单 iter 测不出收敛性, L16 / B1 path-2 教训
- **simplicity 立场**: spike 推成 P1.3A 半成品风险
- **Resolve**: spike **真接 LBBD 外循环但严守边界** — 5 iter × 3 candidate (=15 master.solve), benders_loop 接 deterministic sub-problem stub (binding/routing 不真跑, 返 fixed verdict). 既测多 iter 收敛, 又不变成 P1.3A 完整. integration §2.2 同思路.

### D4. C++ propagator sub-route (sub-route 2): 测 vs defer

- **integration §4.2**: defer P1.3B (CP-SAT C++ propagator hook 非 spike scope)
- **其它路**: 没碰
- **Resolve**: 接受 integration 立场, spike 主测 sub-route 1 (solve-rebuild), sub-route 3 (hard-constraint rebuild) 1-iter trial 验接口兼容, sub-route 2 全 defer.

### D5. Cut count ramp: 10K / 50K / 100K (throughput) vs 1K / 10K / 50K (correctness)

- **throughput**: 100K 测 break point (extreme)
- **correctness**: 50K 已是 master cycle 不可用上限, 100K overkill
- **Resolve**: 取 **1K / 10K / 50K** (correctness). 100K 砍 — spike 是 "可以开始 P1.3A 吗" 不是 "找 break point" (per simplicity). 100K 死时间多 30-60min wall, ROI 低. 真 break point 留 P1.3A 主体跑.

### D6. 工时估范围: 10-30h Claude 中位数

- **范围**: simplicity 10-16h ↔ observability 20-30h
- **Resolve**: final 估 **15-22h Claude + 3-6h wall**. 中位数. 含必要 observability (4 event) 不含全 12. 含真 9 step lifecycle (correctness/integration) 不含 LBBD 全栈. simplicity 担心的 "推成 P1.3A 半成品" 通过 D3 严守边界规避.

### D7. Spike branch 策略: long-lived feature branch (rollback) vs 没碰 (其它)

- **rollback 立场**: branch-isolated, 失败 `git branch -D`
- **其它**: 没明示, 默认 master
- **Resolve**: 全接 rollback 立场. `spike/prod_scale_master_integration_20260526` branch, 7-10 commit checkpoint, 失败 delete, GO 后走 2 PR 流程 (doc-only verdict PR + 重写实施 PR, 不 cherry-pick).

---

## 5. Final spike spec (合并版)

### 5.1 Branch + commit 策略

- Branch: `spike/prod_scale_master_integration_20260526` (off master `20f1f22`)
- 7-10 commit checkpoint, each `[SPIKE]` 前缀 + interim GO/NOT-GO signal
- 失败 → `git branch -D` (zero touch master)
- GO → 2 PR (PR #1 verdict doc only / PR #2 重写 P1.3A 实施, **不 cherry-pick spike code**); **PR #2 用 semantic invariant check 验 fidelity** (Gemini round 2 F5 fix — raw protobuf hash compare 数学不成立: `NewBoolVar()` 按调用顺序递增分配 Integer Variable Index, PR #2 重构必改 ID, hash 100% 报错. 改为: PR #2 master.Proto() 必 emit (a) `len(variables)` 跟 spike baseline 严格等 (b) `len(constraints)` 严格等 (c) 固定 random seed 下 `master.ResponseProto().objective_value` + `status` 严格一致)
- 7-day wall clock 硬上限 (per rollback §2.1)
- State sandbox: `EXACT_SPIKE_OUTPUT_DIR=data/cuts/spike/`, 8 项 off-limits (PROJECT_LOCK / canonical_rules / data/preprocessed / 9 family validator entry / docs/项目说明 spec / CLAUDE.md / src/cuts/lifecycle.py 主 step 函数 / replay.py) PR rebase 时 zero diff enforce

### 5.2 Scope (要测的) — 2026-05-26 shrink per scope creep audit

**重要 — Spike scope 严守 GPT pro Finding 5 close gate 5 项需求**:
1. 真 prod registry build master var (Finding 5 #1)
2. 真 cut body size 分布 (Finding 5 #2)
3. 测 build wall / proto bytesize / RSS / solve wall (Finding 5 #3)
4. active cut filter / rotation 阈值 10K/50K/100K (Finding 5 #4)
5. feasible realistic case 避 INFEASIBLE 早停 (Finding 5 #5)

P1.3A 主体 (真 master integration / LBBD multi-iter / 9 family translator 真接 master / 6-dim watcher / adversarial inject / sub-route PoC) 全 defer P1.3A 正式 design 阶段, 不在 spike scope. 此 shrink 后 spike 答 "Finding 5 close 了吗" 不答 "P1.3A 是不是 close" (per simplicity slant §1).

**Spike 必测**:
- **Master scale**: 81,795 BoolVar **toy master** (真 prod pose registry from `data/preprocessed/candidate_placements.json`), simple Add() / AddLinearConstraint() 跑 build/solve cost measurement. **不接 PoseBoolExactMaster** (P1.3A 主体的事, 这里只测 BoolVar build 跟 constraint add cost).
- **Failfast probe**: 50 inst subset fixture, 启动前 ≤15s timeout (per Gemini round 1 F3)
- **Real oracle real emit**: 9 family × ≥5 cert = ≥45 cert 真 oracle 调跑出 (验 Finding 5 #2 真 cut body size 分布). 真 cert 经 toy translator 转 CP-SAT constraint 验 build cost.
- **Cut count ramp**: 1K / 10K / 50K / **100K** (Gemini round 1 F2 — 168h / 60s/iter × 10 cut/iter ≈ 100K accumulated, 必测 50K→100K L3 cache boundary)
- **Feasible smoke**: IP v2 blueprint hint case (per adversarial R3) — `master.ResponseProto().best_objective_bound` 有效 + `status` OPTIMAL/FEASIBLE + branches≥1K / conflicts≥100 / wall≥1s (Gemini round 2 Finding 3 — wall-time 单独不够, 含 objective bound)
- **Active filter sizing**: 跑推荐 Hybrid (score = activity_count - 0.1 × age_decay) 在 100K cut 挡位下 filter wall ≤ 100ms/iter, eviction trigger RSS>4.5GB OR cut count>50K. **只 sizing 不 ablation, 不接 master**.
- **基本 telemetry**: RSS sample (psutil 1Hz background) + proto bytesize milestone sample + dark_matter_emit (INFEASIBLE 时强制 emit witness blob). 不 hook lifecycle 12 类全 event.

### 5.3 NOT-scope (不测的, 严守边界 — 2026-05-26 扩大 per scope creep audit)

**P1.3A 主体 work (全 defer 到正式 P1.3A 阶段 N=8 parallel design 重新决策)**:
- ❌ **真接 PoseBoolExactMaster (B1)** — toy master 就够测 Finding 5 5 项. 真 master wire 是 P1.3A 主体.
- ❌ **`step_8_apply_to_master` 9 family translator 真实施** — spike 只验 toy translator build cost. 9 family 真 translator 接真 master 是 **P1.3B 主体**.
- ❌ **Multi-iter LBBD loop (15 iter × candidate / batch no-good stub / objective bound 收敛)** — spike 只 single build/solve measurement. LBBD multi-iter 是 P1.3A 主体.
- ❌ **6-dim watcher 全注册 + 3 ghost transition + 状态机** — spike 不 wire cut store 状态机, 只 sizing measurement. cut store integration 是 P1.3A 主体.
- ❌ **跨 candidate source_digest invalidation (G16/G16b)** — outer search candidate 切换是 P1.3A 主体, spike single candidate sizing.
- ❌ **Adversarial inject 50 bad / forged-cert** — F1/F2/F3 patch 验在 scale 下 still hold 是 P1.3B regression 测试, defer.
- ❌ **3 sub-route PoC (solve-rebuild / C++ propagator / hard-constraint)** — sub-route 决策是 P1.3A 主体, spike 只用 simple Add() 验 build cost.
- ❌ **9 step lifecycle 全 invoke** (step 1/3/4/5/6/7/9) — spike 只 invoke step 1 oracle emit (真 cert body 来源). 真 lifecycle 全 invoke 是 P1.3A 主体.

**其它**:
- ❌ 真跑 binding subproblem
- ❌ 真跑 routing subproblem
- ❌ Multi-process / multi-worker (spike single worker)
- ❌ 168h ramp (spike ≤ 2h run; 100K cut 是 168h 等价累积上限 — spike cut count cover 但 wall 不 ramp)
- ❌ Active filter ablation 全跑 — 只 Hybrid sizing
- ❌ Observability 全 12 event class — 只 RSS / proto / dark_matter
- ❌ Cut purge 物理删机制 — defer P1.3A 主体
- ❌ **`cp_model.SolutionCallback` 注入 cut** (Gemini round 2 Q8.2 — 防 spike 实施时手滑用 callback) — spike 实施严守 Outer-loop pattern

### 5.4 量化 GO criteria (10 项 — 严守 Finding 5 close gate)

shrink per scope creep audit: 删 G10/G12/G13/G14/G15/G15b/G16/G16b (P1.3A/P1.3B 主体 criteria). 保留 sizing / measurement / 直接对应 Finding 5 5 项的 criteria.

**Build cost** (Finding 5 #3):
- G1: 81K BoolVar + 0 cut build wall ≤ 10s
- G2: 81K + 1K cut build wall ≤ 20s
- G3: 81K + 10K cut build wall ≤ **30s**
- G4: 81K + 50K cut build wall ≤ 300s
- G4b: 81K + 100K cut build wall ≤ 600s (Gemini round 1 F2 — 168h 等价上限)

**Solve cost (single solve, no LBBD loop)** (Finding 5 #3 + #5):
- G5: 0 cut feasibility wall ≤ 30s
- G6: 10K cut feasibility wall ≤ 180s, status OPTIMAL or FEASIBLE (**不能 INFEASIBLE 早停**, per adversarial R3 + Gemini round 2 Finding 3: 同时 `master.ResponseProto().best_objective_bound` 有效不空, status 不是 UNKNOWN)
- G7: 100K cut feasibility 不 hard cap (因 100K 加 cut 后 solve 可能 INFEASIBLE 是预期, 只 measure wall + status 不 verdict)

**Resource** (Finding 5 #3):
- G8: RSS peak ≤ 20 GB single worker, 100K 挡位必 measure (Gemini round 1 F2); 100K 挡位 RSS 超线性 (50K→100K 涨 >2x) trigger N3
- G9: proto.ByteSize() ≤ 500 MB @ 50K, ≤ 1 GB @ 100K

**Real cert sound** (Finding 5 #2):
- G10 (renumbered): ≥45 cert 真 oracle 调出, validator 全 sound (cert body 分布 sample 出 jsonl, vs mini Step 8 spike 1-3-5 literal 简单分布)

**Active filter sizing** (Finding 5 #4):
- G11 (renumbered): Hybrid filter (activity - 0.1 × age) 在 100K cut 挡位 filter wall ≤ 100ms/iter, eviction trigger RSS>4.5GB OR cut count>50K **能正常触发不报错** (不验 filter 是否 sound, sound 是 P1.3A 主体)

**Failfast probe** (Gemini round 1 F3):
- G17: 50 inst subset probe wall ≤ **15s**. 超时 abort spike (probe 自身慢 = harness bug)

### 5.5 量化 NOT GO criteria (任一触发 → abort + reflect)

shrink per scope creep audit: 删 N5/N7/N8/N8b (对应已删 GO criteria).

- N1: G1-G4b 任一 build wall 超阈值 ×2 (e.g. 0 cut build > 20s, 100K cut build > 1200s)
- N2: G6 INFEASIBLE 早停 (即便 blueprint hint, feasible case 设计错或 oracle cert sound 错)
- N3: G8 RSS > 30 GB (撞 L24 augmented master 死法 reference); 100K 挡位 RSS 超线性 (50K→100K 涨 >2x) trigger Gemini round 1 F2 警告; **同时监控 SWIG proxy leak** (Gemini round 2 Q8.1 — `cp_model.Add()` 100K 次同 model 实例可能 SWIG wrapper C++ released but Python proxy 未回收)
- N4: G9 proto > 2 GB (撞 spawn proto copy 风险)
- N6: G10 oracle real-emit cert unsound (oracle 自身 bug, spike abort 报 bug)
- N9: Reproducibility variance > 30% (同 seed 3 次跑差太大)
- N10: 7-day wall clock 用完仍未 cover 主路径
- N11: spike 跑后 jsonl RSS/proto/dark_matter 3 必 event 任一 = 0
- N12: Off-limits file 8 项任一 diff non-zero
- N13: G17 probe wall > 15s (harness 自身 bug, 不进主测)

### 5.6 工时 estimate (shrink 后)

| 段 | Claude 工时 | Wall-clock 死时间 |
|---|---|---|
| Branch setup + state sandbox + off-limits enforce | 0.5-1h | 0 |
| Failfast probe (50 inst subset, G17 15s timeout) | 1h | <0.5h probe run |
| Real oracle real emit fixture (≥45 cert, 9 family) | 2-3h | 10-20 min oracle calls |
| Toy translator (验 build cost, simple Add()/AddLinearConstraint, 不接 PoseBoolExactMaster) | 1-2h | 0 |
| Scale ramp (1K / 10K / 50K / 100K cut, single build/solve no LBBD loop) | 1-2h | 2-3h CP-SAT real run |
| Feasible smoke (IP v2 blueprint hint, 验 G6 不 INFEASIBLE 早停) | 1h | <5 min wall |
| Active filter Hybrid sizing (filter wall + eviction trigger 验) | 0.5-1h | 0 |
| 3 必 telemetry hook (RSS / proto / dark_matter) + post-mortem | 1-2h | 0 |
| Run + verify + write spike verdict.md | 1-2h | 1-2h spike full run |
| **TOTAL** | **8-12h Claude** | **4-7h wall** |

vs round 0 / 1 / 2 (17-29h Claude / 3-9h wall): shrink 后 **~60% 时间**. 严守
Finding 5 close gate scope, P1.3A 主体 work (step 8 真实施 / LBBD multi-iter /
真 master / 6-dim watcher / adversarial inject / 跨 candidate / sub-route) 全
defer P1.3A 正式 design 阶段重新走 N=8 parallel.

Per `[[work-time-estimates]]` Claude pace 折扣, ~1-2 working session 日历, 7-
day cap 极宽裕. P1.3A ≤ 3 day budget 不被 spike 占用 (spike 自己 ≤ 1 day).

---

## 6. Main merger 自评 blind spot

我做 merger 的 bias:
1. **取交集偏 correctness + integration 立场** — 因为这 2 路跟项目 core (sound + 真路径) 最 align, 可能 under-weight throughput / observability 的 perf-only 视角. Mitigation: D2 取 4 必 observability event 不 0, D5 留 LLC miss metric.
2. **D6 工时估中位数** — 没真碰过 prod 81K scale, 实际可能 off by 1.5-2x. Mitigation: 7-day wall cap + failfast probe 防过度投入.
3. **D3 LBBD 多 iter 决策** — simplicity 担心的 "推成 P1.3A 半成品" 我用 "benders sub-problem stub" 规避, 但 stub 自身可能引入新 risk (stub return value 不能反映真 binding/routing 行为). **Round 1 update**: Gemini F1 catch — 原 G15 用 search tree node count 单调减作 mitigation 自己数学不成立 (CP-SAT presolve 重排), 已改 wall-time 收敛 metric + stub 改 targeted no-good 模拟 Benders 真动力学.
4. **没真懂 OR-Tools 9.15 CP-SAT internals** — presolve / propagator / search 路径黑盒, spike 跑出非预期 behavior 我可能不会立刻识别. **Round 1 update**: Gemini F1 BLOCKER 正好打在这个 blind spot 上, 现 G15 改 wall-time 收敛规避 internals 黑盒依赖. 仍残: 100K cut presolver 行为未验, 加 G4b 测.
5. **8 路 sibling slant 自承的 blind spot 我可能 fold 不进 final** — 每路自己标的 "潜在 blind spot" 在 merger 后仍 open. spike 跑完即便 17 GO criteria 全过, GPT pro / Gemini cross-check 可能仍 catch ≥ 1 Layer 2 finding (per historical §11 prediction). 这是接受的 — spike 责任是闭住本层让下层洞落 Phase 1.5+ ramp 区, 不是 close 所有 risk.

**Round 1 Gemini cross-check 后新自评**:
6. **D5 cut count ramp 折取错** — Gemini F2 catch 100K cut blind spot, 用 168h/60s × 10 cut/iter ≈ 100K 累积 + L24 30 GB 死法引证. 我原取 correctness "50K 已极限" 立场, throughput 原立场被 Gemini 量化加固. 已恢复 100K 挡位 (G4b).
7. **D3 LBBD iter 数我估错** — Gemini F6 catch 5 iter 不触 phase transition (iter 7+ 才进 marginal cut 区), L16/B1 path-2 死在 10 iter UNPROVEN. 已 5→15 iter. **2026-05-26 user scope creep audit 后删除** — multi-iter LBBD 整段 leak P1.3A 主体, defer 到 P1.3A 正式 design 重新 走 N=8 parallel.

**2026-05-26 user scope creep audit 后第三批自评 (最严重 bias)**:
9. **D3 + 取整 correctness/integration slant 把 spike scope leak 进 P1.3A 主体** — 用户 catch: spike 应严守 Finding 5 close gate (sizing / measurement), 但我 MERGER §5.2 写了 step 8 真实施 + LBBD multi-iter + 真 master integration + 6-dim watcher + adversarial inject + 3 sub-route — 全是 P1.3A 主体的事. simplicity slant §1 当时明示 "spike 答'可以开始做 P1.3A 主体了吗' 不答'P1.3A 是不是 close'", 我 merger 取交集时 override 了 simplicity. 这是 main merger 同种 RLHF bias 的典型表现 (correctness/integration slant "做全 = 安全" inclination). [[adversarial-soundness-audit]] Layer 2 attack 是数据层, 此处是 phase boundary 层 — 不同 attack vector, 同种 inclination.
10. **Audit 体系本身没 catch 9** — 8 路 sibling 含 simplicity (raise 了) 但 main override; round 1 + round 2 Gemini cross-check 都 focus 数学/CP-SAT 内部 (round 1 NOT GO 数学层 6 finding / round 2 NOT GO 数学层 4 finding) **0 catch phase boundary leak**. Gemini 是数学/paradigm 强 audit 但 phase boundary / project 流程 audit 它没 strong opinion. user 是唯一能 catch 这层 audit 的人.
11. **Shrink 后再 Gemini cross-check round 3** — 但目的不再是数学层 verify (round 1/2 已 cover), 而是验 shrink 后 scope 还能不能 close Finding 5 5 项需求 (sizing / measurement / feasible smoke / active filter / RSS). 若 round 3 GO, 才真启动 spike.

---

## 7. 下一步 (spike 实施前)

1. ~~**Gemini cross-check 本 MERGER doc round 1**~~ ✅ (verdict NOT_GO, archive
   `cross_check/gemini_merger_round1_20260526/`). 6 finding fix landed.
2. ~~**Gemini cross-check round 2**~~ ✅ (verdict NOT_GO 但显式 "无需 round 3",
   archive `cross_check/gemini_merger_round2_20260526/`). 4 finding fix landed.
3. ~~**User scope creep audit (2026-05-26)**~~ ✅ catch §5 scope leak P1.3A 主体.
   shrink §5 scope 严守 Finding 5 close gate (8-12h Claude / 4-7h wall). P1.3A
   主体 work 全 defer 到 P1.3A 正式 design 阶段重新走 N=8 parallel.
4. **Gemini cross-check round 3** — 验 shrink 后 scope 仍能 close Finding 5
   5 项需求 (sizing / measurement / feasible smoke / active filter / RSS).
   若 round 3 GO_WITH_MINOR 或 GO 才进 spike 实施.
5. **GPT pro 选择**: 不立刻送 GPT pro (spike 还未跑). 等 spike 跑完 verdict.md 后打
   v14 包 (含 patch verify + Finding 5 close spike verdict).
6. **实施 spike**: round 3 GO 后, 按 §5 shrink spec spawn opus closed-loop
   agent (per `[[subagent-for-closed-loop-tasks]]`), branch
   `spike/prod_scale_master_integration_20260526`, 7-day wall cap, **8-12h
   Claude / 4-7h wall** budget.
7. **失败回退**: 7-day wall cap 触发 → `git branch -D` + 主对话写 reflect doc.

### Round 1 catch summary
- 1 BLOCKER (G15 metric + stub) / 3 HIGH (F2 100K / F3 probe / F6 15 iter) /
  2 MEDIUM (F4 G3 30s / F5 protobuf checksum) / 1 missing risk (C6.3 source_digest
  invalidation) / 3 residual (入 P1.3A risk register)

### Round 2 catch summary (round 1 fix verify + new finding)
- Round 1 fix verdict: 4 CORRECT / 3 PARTIAL / 1 INCORRECT (per round 2 verdict.md)
- 4 new finding: 1 BLOCKER (Finding 1 protobuf hash 数学不成立, F5 INCORRECT) /
  2 HIGH (Finding 2 stub 单 cut/iter 退化 / Finding 3 wall-time 假收敛盲区) /
  1 MEDIUM (Finding 4 G16 物理 leak)
- 2 missing risk: Q8.1 SWIG memory leak / Q8.2 GIL callback blocking
- 全 mechanical fix (改 metric / 加 batch / 加 check / 加 gc), 不涉及 paradigm 重设
- Gemini 自己说"无需 round 3 漫长拉扯", main 接受 → 直接 spike 实施 (round 3 risk 是
  GO ritual, per [[gemini-prompt-audit-mode]] 反例)

---

## 8. References

- 8 路 raw design: 本目录 `*_design.md`
- GPT pro audit: `docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md`
- Phase 1.3A plan: `docs/项目说明/09_phase_1_3_plan.md`
- B1 PoseBoolExactMaster: `src/models/pose_bool_exact_master.py`
- 9 step lifecycle: `src/cuts/lifecycle.py`
- mini Step 8 spike: `docs/research/p1_2b_mini_step_8_spike_20260525/`
- 27 lever paradigm death: `docs/项目说明/03_paradigm_death_baseline.md`
