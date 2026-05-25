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
- GO → 2 PR (PR #1 verdict doc only / PR #2 重写 P1.3A 实施, **不 cherry-pick spike code**); **PR #2 必须 emit 同结构 `cp_model.Proto()`, hash compare spike verdict 的 baseline protobuf hash 验 fidelity** (Gemini round 1 F5 fix — 防重写后性能特征跟 spike 验过的不一致, 撞 L13 hidden assumption 死法)
- 7-day wall clock 硬上限 (per rollback §2.1)
- State sandbox: `EXACT_SPIKE_OUTPUT_DIR=data/cuts/spike/`, 8 项 off-limits (PROJECT_LOCK / canonical_rules / data/preprocessed / 9 family validator entry / docs/项目说明 spec / CLAUDE.md / src/cuts/lifecycle.py 主 step 函数 / replay.py) PR rebase 时 zero diff enforce

### 5.2 Scope (要测的)

- **Master scale**: 81,795 BoolVar (真 prod pose registry from `data/preprocessed/candidate_placements.json`), env `EXACT_USE_POSE_BOOL_MASTER=1` 用 PoseBoolExactMaster (B1, per `[[b1-phase2-production-land]]`)
- **Failfast probe**: 50 inst subset fixture, spike 启动前 5-10 min run (per D1)
- **Lifecycle**: 9 step 全真 invoke (step 1 oracle real emit / step 3 serialize / step 4 deserialize / step 5 validate dispatch / step 6 attach scope check / step 7 evaluate / **step 8 apply_to_master = 主交付** / step 9 regression sweep)
- **Real oracle real emit**: 9 family × ≥5 cert = ≥45 cert 真 step 5 validate (per integration §1, correctness §1.2)
- **Cut count ramp**: 1K / 10K / 50K (per D5)
- **Feasible smoke**: IP v2 blueprint hint case (per adversarial R3) — branches≥1K / conflicts≥100 / wall≥1s / status≠INFEASIBLE
- **Cut count ramp**: 1K / 10K / 50K / **100K** (Gemini round 1 F2 fix — 168h / 60s/iter × 10 cut/iter ≈ 100K accumulated, 必测 50K→100K L3 cache boundary 防超线性 RSS)
- **Multi-iter LBBD**: **≥15 iter** single candidate × 3 candidate (Gemini round 1 F6 fix — L16/B1 path-2 死在 iter 10 UNPROVEN, iter 7+ 才进 marginal cut presolver 失效区, 5 iter 触不到 phase transition), benders_loop 接 **targeted no-good sub-problem stub** (Gemini round 1 F1 fix — stub 必须读 master `SolutionInfo()` 当前 selected_pose set 产 `sum(x[g,p] for selected) ≤ len-1` 切当前解, 不能返 fixed verdict, 否则模拟不到 Benders 动力学)
- **6-dim watcher**: 全 dimension (by_cell / by_group / by_pose / by_commodity / by_region / by_ghost) 各 ≥1 注册 (per integration G3)
- **3 ghost transition**: 测 held/active/quarantined 状态机 + **跨 candidate source_digest invalidation** (Gemini round 1 C6.3 missing risk — outer search 切 candidate 时 ghost_id 变, store cache by_ghost watcher 必清, source_digest 必重新 emit 即便 byte-equal)
- **Adversarial inject**: 50 bad cert + 9950 good cert 混 (per adversarial R8) + 3 forged-cert case (per Finding 1/2/3 each)
- **Sub-route**: 主测 sub-route 1 (solve-rebuild), sub-route 3 1-iter trial 验接口, sub-route 2 defer (per D4)
- **Active filter**: 跑推荐的 Hybrid (score = activity_count - 0.1 × age_decay), ablation defer P1.3A (per D2)

### 5.3 NOT-scope (不测的, 严守边界)

- ❌ 真跑 binding subproblem (targeted no-good sub-problem stub instead)
- ❌ 真跑 routing subproblem
- ❌ Multi-process / multi-worker (spike single worker, CP-SAT threading non-determinism risk 文档化 per Gemini C6.1)
- ❌ 168h ramp (spike ≤ 2 hour run; 100K cut 是 168h 等价累积上限 — spike scale 不 ramp 但 cut count 必 cover)
- ❌ Sub-route 2 (C++ propagator) — defer P1.3B
- ❌ Active filter ablation 全跑 — 只测推荐 Hybrid
- ❌ Observability 全 12 event class — 只 4 必
- ❌ Cut purge 物理删机制 — Gemini C6.2 derived risk, defer P1.3A 主体 (spike 只测 logical filter)

### 5.4 量化 GO criteria (17 项, 全 hold 才 GO)

Round 1 Gemini fix landed: G3 60s→30s (F4), G15 改 wall-time 收敛 metric (F1),
加 G16 跨 candidate invalidation (C6.3), 加 G17 failfast probe timeout (F3).

**Build cost** (Gemini F4 收紧 G3):
- G1: 81K BoolVar + 0 cut build wall ≤ 10s
- G2: 81K + 1K cut build wall ≤ 20s
- G3: 81K + 10K cut build wall ≤ **30s** (折中: Gemini 6s 没考虑 9 family translator dispatch overhead, 收紧到 30s 卡 SWIG vectorized 反模式)
- G4: 81K + 50K cut build wall ≤ 300s
- **G4b**: 81K + 100K cut build wall ≤ 600s (Gemini F2 加)

**Solve cost (feasibility only)**:
- G5: 0 cut feasibility wall ≤ 30s
- G6: 1K cut feasibility wall ≤ 60s
- G7: 10K cut feasibility wall ≤ 180s, status OPTIMAL or FEASIBLE (**不能 INFEASIBLE 早停**, per adversarial R3 metric)

**Resource**:
- G8: RSS peak ≤ 20 GB single worker (per adversarial R4, correctness §3.3); 100K cut 挡位 RSS 必 measure (Gemini F2)
- G9: proto.ByteSize() ≤ 500 MB @ 50K, ≤ 1 GB @ 100K (Gemini F2)

**Lifecycle correctness**:
- G10: 9 step 全 invoke, 0 NotImplementedError, 0 fail-closed assert violation (per integration G1)
- G11: ≥45 cert 真 step 5 validate, 全 sound (oracle real-emit cert 应 sound; 若有 unsound = oracle bug, spike abort 报 bug, per integration G2)
- G12: 6-dim watcher 全注册, `store.stats()` 6 dim 各 ≥1 (per integration G3)

**Adversarial**:
- G13: 50 bad cert 100% quarantine, store active count = 9950 (per adversarial R8)
- G14: 3 forged-cert case (F1/F2/F3 each 1) 必 quarantine, 0 漏 (per integration G10)

**Multi-iter convergence** (Gemini F1 BLOCKER + F6 HIGH fix):
- G15: **≥15 iter LBBD single candidate**, wall-time 收敛: iter N+1 wall ≤ iter N wall × 1.5 (允许 noise) AND 最后 5 iter avg wall ≤ first 5 iter avg wall × 0.7 (真收敛 signal). **不用 search tree node count** (Gemini 论证 CP-SAT presolve 重排让 node count 不单调甚至激增).
- G15b: stub 必返 targeted no-good (读 master `SolutionInfo()` 当前 selected_pose set 产 `sum(x[g,p] for selected) ≤ len-1` 切当前解), 不能返 fixed verdict.

**跨 candidate state isolation** (Gemini C6.3 missing risk fix):
- G16: 3 candidate 切换时, store.snapshot() after candidate N vs N+1 必 verify: by_ghost watcher entries cleared, source_digest 重新 emit (hash 应 equal 但 emit timestamp 必 update), cross-candidate cache 无 leak.

**Failfast probe** (Gemini F3 HIGH fix):
- G17: 50 inst subset probe wall ≤ **15s**. 超时 abort spike (probe 自己慢 = harness bug, 不进 81K 主测).

### 5.5 量化 NOT GO criteria (任一触发 → abort + reflect)

- N1: G1-G4b 任一 build wall 超阈值 ×2 (e.g. 0 cut build > 20s, 100K cut build > 1200s)
- N2: G7 INFEASIBLE 早停, 即便加 blueprint hint (feasible case 设计错或 cut sound 错)
- N3: G8 RSS > 30 GB (撞 L24 augmented master 死法 reference); 100K 挡位 RSS 超线性 (e.g. 50K→100K 涨 >2x) trigger Gemini F2 警告
- N4: G9 proto > 2 GB (撞 spawn proto copy 风险)
- N5: G10 9 step 任一 raise / assert violation
- N6: G11 oracle real-emit cert unsound (oracle 自身 bug, 不是 spike fail 但 spike abort 报 bug)
- N7: G13/G14 adversarial inject 漏 ≥1 (F1/F2/F3 patch 在 scale 下失效)
- N8: G15 wall-time 不收敛 (iter 15 wall > iter 1 wall × 0.7) OR stub 没产 targeted no-good (撞 L16/B1 path-2 死法)
- N8b: G16 跨 candidate 切换 store cache leak (by_ghost watcher 残留 OR source_digest 没重新 emit)
- N9: Reproducibility variance > 30% (per rollback §8.4, 同 seed 3 次跑差太大)
- N10: 7-day wall clock 用完仍未 cover 主路径 (per rollback §2.1)
- N11: spike 跑后 jsonl 4 必 event 任一 = 0 (per observability §9.1 精简版)
- N12: Off-limits file 8 项任一 diff non-zero (per rollback §5.3)
- N13: G17 probe wall > 15s (harness 自身 bug, 不进主测)

### 5.6 工时 estimate

| 段 | Claude 工时 | Wall-clock 死时间 |
|---|---|---|
| Branch setup + state sandbox + off-limits enforce | 0.5-1h | 0 |
| Failfast probe (50 inst subset) | 1h | 5-10 min run |
| Real oracle real emit fixture (≥45 cert) | 2-3h | 10-20 min oracle calls |
| Spike harness 9-step glue (wrapper 不 reimplement src) | 2-3h | 0 |
| Step 8 apply_to_master 实施 (9 family translator 真接 PoseBoolExactMaster) | 4-6h | 0 |
| Multi-iter LBBD loop (≥15 iter × 3 candidate, targeted no-good sub-problem stub) | 3-4h (Gemini F6 +1h, F1 stub redesign +1h) | 2-4h CP-SAT real run (Gemini F6 wall ×3) |
| Scale ramp (1K / 10K / 50K / 100K cut) | 1-2h | 2-3h CP-SAT real run (Gemini F2 100K +1-2h) |
| Adversarial inject (50 bad cert + F1/F2/F3 forged) | 2h | 0 |
| 跨 candidate source_digest invalidation verify (G16) | 1h | 0 |
| Failfast probe + 15s timeout enforce (G17) | 0.5h | <0.5h probe run |
| 4 必 telemetry event hook + post-mortem | 1.5-2h | 0 |
| Run + verify + write spike verdict.md | 1-2h | 2-4h spike full run (Gemini multi-iter + 100K wall 加 1-2h) |
| **TOTAL** | **20-29h Claude** | **5-9h wall** |

Round 1 Gemini fix 后工时 +3-4h Claude / +2-3h wall (vs round 0 17-25h / 3-6h).
Per `[[work-time-estimates]]` Claude pace 折扣, ~2-3 working session 日历仍可
hold. 落入 P1.3A ≤ 3 day budget 略紧, 用 7-day cap 兜底.

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
7. **D3 LBBD iter 数我估错** — Gemini F6 catch 5 iter 不触 phase transition (iter 7+ 才进 marginal cut 区), L16/B1 path-2 死在 10 iter UNPROVEN. 已 5→15 iter.
8. **跨 candidate state isolation 完全漏了** — Gemini C6.3 missing risk 全 8 路 0 cover. 已加 G16. 这是 review 加严最值钱的一条 — outer search 切 candidate 时 store cache 不 invalidate 会让 spike 跑到 candidate 2 时用 candidate 1 的 ghost cache, 产 false-positive cut. Layer 2 hidden assumption.

---

## 7. 下一步 (spike 实施前)

1. ~~**Gemini cross-check 本 MERGER doc**~~ ✅ Round 1 完 (verdict NOT_GO, archive at
   `cross_check/gemini_merger_round1_20260526/`). Round 1 fix landed 本 merger §5 update.
2. **Gemini cross-check round 2**: 验本 round 1 fix effective (F1 stub redesign + G15 wall-time
   metric + G4b 100K + G15 15 iter + G16 跨 candidate + G17 probe timeout + F4/F5 fix). 若 round 2
   GO_WITH_MINOR 或 GO, 才进 spike 实施.
3. **GPT pro 选择**: 不立刻送 GPT pro (spike 还未跑). 等 spike 跑完出 verdict.md 才打包送 v14 (含 patch verify + spike verdict).
4. **实施 spike**: round 2 GO 后, 按 §5 spec 实施. 单线闭环 (per `[[subagent-for-closed-loop-tasks]]`) 可 spawn opus agent.
5. **失败回退**: 7-day wall cap 触发 → `git branch -D spike/prod_scale_master_integration_20260526` + 主对话写 reflect doc + 重设计 N=8 parallel.

### Round 1 catch summary (per cross_check archive)
- 1 BLOCKER (G15 metric + stub) — fixed §5.2 / §5.4
- 3 HIGH (F2 100K cut / F3 probe timeout / F6 15 iter) — fixed §5.2 / §5.4
- 2 MEDIUM (F4 G3 30s / F5 protobuf checksum) — fixed §5.4 / §5.1 待 round 2 cross-check
- 1 missing risk (C6.3 source_digest invalidation) — fixed §5.4 G16
- 3 residual P1.3A risk (C7) — 入 P1.3A risk register (待 plan doc update)

---

## 8. References

- 8 路 raw design: 本目录 `*_design.md`
- GPT pro audit: `docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md`
- Phase 1.3A plan: `docs/项目说明/09_phase_1_3_plan.md`
- B1 PoseBoolExactMaster: `src/models/pose_bool_exact_master.py`
- 9 step lifecycle: `src/cuts/lifecycle.py`
- mini Step 8 spike: `docs/research/p1_2b_mini_step_8_spike_20260525/`
- 27 lever paradigm death: `docs/项目说明/03_paradigm_death_baseline.md`
