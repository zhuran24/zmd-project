# Prod-scale Spike — Historical-paradigm-context Design

**Date**: 2026-05-26
**Slant**: historical-paradigm-context (per orchestrator). 任务：让 spike
设计带上 27 lever paradigm death baseline 的全部记忆, **防自己撞已知死路**;
同时让 spike 把 cut framework 这个**新 paradigm 内部的 hidden 死法**主动
trigger 出来, 不要等 168h 真跑才 catch.
**Author**: opus subagent (historical slant); main 之后 merge correctness /
throughput / adversarial / integration / simplicity 多路.
**主线 thesis**: 新设计若不带历史 context, 很容易撞 27 lever 已 verdict 死
的方向 —— 浪费的不是几个小时 cheap gate, 是几天到几周 (B1 全套 path-1/2
≈ 3-4 周, PCR-CUT 6 Phase ≈ 1 周, augmented master ≈ 4 天). spike 设计
**每个 design choice 必 cite 一条历史 lever 的启示**.

---

## 0. 锚定 ground truth (paradigm 历史侧)

| 项 | 值 | 来源 |
|---|---|---|
| 已死 lever 总数 | 27 | `docs/项目说明/03_paradigm_death_baseline.md` §4.1-§4.7 |
| 死法 5 类 (timeline axis) | A=表达力 / B=不收敛 / C=symmetry / D=资源 / E=几何 | [[paradigm-death-timeline-27-lever]] memory |
| 共同 root cause | 4 (master 表达力 / 96% 几何 / cell-front break sym / 单机 RAM cap) | death baseline §4.8 |
| cut framework 是 4 root cause **唯一**满足 paradigm | yes | death baseline §4.9 |
| Phase 1.1 Gemini 漏 critical 数 | 4 | [[phase-1-1-go-blessed]] memory + GPT pro R5 R&R |
| Phase 1.2 Gemini 漏 BLOCKER 数 | 2 (F7/F8 facility_cells binding + source_digest stale) | `phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md` Finding 1+2+3 |
| GPT pro audit 共发 finding | 6 (2 BLOCKER + 2 HIGH + 1 MED + 1 LOW) | 同上 |
| Mini Step 8 spike scale | 10 group × 5 pose = 50 BoolVar | `spike_translator.py:43-44` |
| Prod target scale | 266 instance × ~280K pose registry | PROJECT_LOCK + `mandatory_exact_instances.json` |
| Scale gap | 1,635x pose, 26.6x group | 280K/50 + 266/10 |
| Phase 0 cheap gate 政策 | ≤ 1h 验前提 GO 后才投 Phase 1 | [[paradigm-phase0-cheap-gate]] memory |

**Phase 1.2 GPT pro Finding 5 一句话**: spike 是 50 BoolVar toy + synthetic
random cuts + INFEASIBLE 早停, 不能作为 prod-scale 接入 master 的 close gate.
这跟历史 v8 anchor slicing 死法**几何同构** — v8 build wall -92% 真实但单
anchor 5 min UNKNOWN 5.5M branches, 关注 build 没量 solve. [[project-v8-anchor-slicing-dead]]

---

## 1. 27 Lever 死法套件 → spike 每 design choice 启示 map

不抄全 27 条 (各 lever 详 death baseline §4.1-§4.7), 只挑 **直接影响 spike
设计** 的 lever, 每条带 (a) 死因 1 行, (b) spike 启示, (c) spike 怎么避.

### L1 — Coordinate-based master (Phase 3B repair5 baseline)
- **死因**: ghost rect 几何决定 master constraint, 60min UNKNOWN 是 baseline
- **启示**: spike **不能**只测 master OPTIMAL, 必测 master OPTIMAL **加 cut 后
  prune ratio** (cut framework 的价值定义)
- **spike 避法**: GO criteria 加 "vs baseline 60min UNKNOWN 的 prune metric",
  不只测 "cuts attached + status OK"

### L12 — v8 anchor slicing (build -92% 真实但 solve 同 quality)
- **死因**: 优化 build wall, 没量 solve quality
- **启示**: **本 spike 头号 risk**. mini Step 8 spike verdict "10K cuts build
  114ms" 跟 v8 build -92% 同模式 —— 都只量 build, 没量真 solve
- **spike 避法**:
  1. measurement set **必含 solve wall + status + objective**, 不只 build wall
  2. INFEASIBLE 状态 (synthetic cut collide) 必须算 "didn't actually measure
     solve"; 只有 feasible OPTIMAL 或 timeout 算真 solve measurement
  3. 加 baseline 对比 (同 master vs cut framework 加成), 不只 absolute metric

### L13 — v10 witness preflight (前提错估)
- **死因**: community blueprint 缺 41 mandatory, paradigm 数学 sound 但前提
  hidden assumption 错
- **启示**: spike 必显式检 hidden assumption — 比如 "cut store contains
  diverse cut family" (不是全 F1), "active filter 真过滤" (不是 trivially 全
  active), "source_digest pin 真 invalidate" (per GPT Finding 3)
- **spike 避法**: spike start 前列**前提清单** + 每条用真数据 check, 不假定

### L14 — Weighted occupancy (数学能力上限)
- **死因**: interior anchor LP=1.000 exact 永不可 cert. paradigm 类不够强.
- **启示**: spike 不是验 cut framework 数学**能不能** prove (paradigm
  baseline 已论证); 是验**工程实施**能不能 scale. 两类 risk 分开.
- **spike 避法**: spike doc 明确标 "本 spike 只验工程实施 scale, 不重验
  paradigm 数学 soundness — 后者已 close 在 Phase 1.0/1.1/1.2"

### L15 — Set-packing prover (攻错层)
- **死因**: minimum set-packing 核心 CP-SAT 几秒搞定, 真瓶颈在 port+power
  +connector 约束组合
- **启示**: spike 不能只 stress test "master 加 N cuts 能不能编译", 必测
  cut 真切到 search space (不是 cut 都 trivially redundant 等于没加)
- **spike 避法**: 加 "cut effectiveness metric" — measure 加 cut 前后 master
  search tree node count, 不只 status

### L16 — Lazy power completion (cut 不收敛)
- **死因**: master 端 81.8s OPTIMAL, 但 cut 端 loose 134→133 stuck / tight
  振荡. cut 学不出
- **启示**: spike 必跑**多轮 LBBD iter** (≥ 5 iter), 测 cut 累积是否 converge
  prune ratio, 不只单轮 build
- **spike 避法**: spike workload 必含 multi-iter "feedback loop" — master
  solve → 生 cut → attach → re-solve, 测 iter 间 prune ratio 单调改善

### B1 Phase 4 routing convergence (~500-610 ports 系统性)
- **死因**: pose-bool master 不知 port direction, 任何 master OPTIMAL 都让
  routing sub-problem reject
- **启示**: cut framework 在 master 外累知识, **跟 B1 同样有 master ↔ sub
  oracle 不一致 risk** — F2/F4 cutset cert 可能在 cut 加进 master 后变 stale
  (master state 改, cert 不再 hold)
- **spike 避法**: spike 测 "cert stale invalidation" — 同 cut 在不同 master
  state 下 evaluate, 量 invalidation 频率

### B1 Phase 5 cell cut (3 form 全 over-restrictive)
- **死因**: cell-level cut 信息密度太低, 任何 form 都把 feasible pose 误切
- **启示**: cut framework FP=0 是 Phase 1.2 close gate. spike 必 stress test
  FP rate 在 prod scale 下保持 0 (不是只在 unit fixture 测)
- **spike 避法**: spike 加 "FP audit pass" — 用真数据 cert + 真 master state,
  跑 1000+ cuts, sample 100 cut replay validate, 0 false positive

### B1 Phase 6 path-2 lazy demand cut (10 iter UNPROVEN 不收敛)
- **死因**: cut weak — `sum(blockers) <= K-demand` `OnlyEnforceIf` 不约束
  binding port-selection 跟 master cleared subset 对齐
- **启示**: F2/F4/F6 翻成 master constraint 的形 (per mini spike "Linear
  area / Multiset nogood / Region Hall") **可能 weak**. spike 必量 effective
  prune contribution per family.
- **spike 避法**: spike 按 family 分桶 measure prune ratio, 哪个 family
  contribute < 1% prune 标记 "translation weak, 需 Phase 1.3B 重设计"

### Path 12 RAB-SEP / Path 13 SAC-Hull / Path 14 PCR-CUT / Path 17 D2 (multi-anchor 0/8 CERTIFIED)
- **死因**: 单 cut sound 但跨 anchor 不 sufficient. 累 70+ cut 后 master
  sustain OPTIMAL, layout L2 同 patch routing-feasible 但别 patch P2 routing-INFEASIBLE
- **启示**: cut framework 比这 4 个 paradigm 强的关键在 **F1-F9 同时多家
  cumulative**, 不是单 family separator. spike 必 stress "multi-family
  cumulative" workload — 同时 attach F1/F2/F4/F5/F6/F7/F9 cut, 测累积 prune
- **spike 避法**: spike workload 跨 family mix, 不只单 family stress

### Lever 24 — Augmented master Candidate D (603.9s UNKNOWN + RSS 32 GB)
- **死因**: 280K pose × 8 ports = 2.36M OnlyEnforceIf, master 加 too many
  hard constraint 直接 RSS 爆 + UNKNOWN
- **启示**: **本 spike 最大 RAM risk**. 10K cuts × ~5 literal/cut = 50K
  multiset constraint, 加在 280K pose-bool 上 RAM 可能爆 (mini spike 50
  BoolVar 不暴露)
- **spike 避法**:
  1. 必测 psutil RSS peak (per worker)
  2. RSS > Phase 3B repair5 baseline (master 30→47 GB) + cuts overhead 必
     fail (用户硬件 48 GB cap)
  3. active filter 真过滤 — 不是把 10K cut 全 push 进 master proto

### L25 — Layout-invariant cert / Lever 26 Benders symmetry (cell-front break sym)
- **死因**: per-instance 几何 high-resolution 已让 sub-pose 等价性消失
- **启示**: cut signature lifting 不能跨 instance (PROJECT_LOCK §3A). spike
  必 verify cut scope 真 within-instance, 没 accidentally cross-instance
- **spike 避法**: spike audit cut store 里每个 cut 的 scope, assert 全是
  within-instance scope, 跨 instance scope 直接 fail (paradigm 红线)

### L23 — Rewrite path exhausted / HiGHS rewrite blocker
- **死因**: 单机 48 GB + 现 solver, 决定性收益物理不可达
- **启示**: spike 跑不动**不能**作为 "换 solver" 的 trigger — 这条路 verdict
  死. spike 跑不动是 cut framework 设计本身要调
- **spike 避法**: spike NOT GO 路径 doc 明确禁 "换 solver" 作 mitigation

### Cand C Phase 2 (160/266 真 INFEASIBLE, 96% 几何死结)
- **死因**: instance 几何下界, paradigm sound 不能改 instance
- **启示**: spike 用 prod instance (266 mandatory 全集) 跑可能直接撞 96% 几何
  INFEASIBLE — 这不是 cut framework bug, 是 instance 性质
- **spike 避法**: spike 分两类 workload: (a) 已知 feasible 子集 (e.g. corner
  candidates) 测 OPTIMAL with cut framework; (b) 已知 INFEASIBLE 子集 (e.g.
  interior 27×15) 测 cut framework 真 prove INFEASIBLE 不只 UNKNOWN

### Phase 0 cheap gate workflow (历史 meta-lever)
- **来源**: [[paradigm-phase0-cheap-gate]] memory
- **启示**: 本 spike **就是** Phase 1.3A 进入前的 cheap gate (≤ 1 day,
  prod scale 但 1 candidate 1 iter, 不全 168h). 不该 over-engineer.
- **spike 避法**: spike 时间预算硬封 1.5 day (含 setup + run + analyze).
  超 1.5 day 必停手, 反思 spike scope 是不是设大了

---

## 2. 新 paradigm (cut framework) 内部的可能死法

27 lever 是**旧 paradigm 自身**死法. spike 暴露的可能是 **cut framework 自己
的 hidden 死法** — 这层之前没人撞过, 风险来自 unknown unknown. 列 ≥ 5 类
新死法, 每条带 spike 怎么 trigger.

### N1 — Cut 多到 master rebuild 不动 (build wall 雪崩)
- **机制**: mini spike 测 10K cuts build 114ms toy scale linear. 但 280K
  BoolVar 上, constraint registration 内部 hash + presolve domain reduction
  可能 cliff (per L1 → L24 augmented master 32 GB UNKNOWN 经验). build cost
  在 scale gap 1,635x 上不一定保 linear.
- **跟 27 lever 区别**: 27 lever 没人测过 "cut framework 多家 family attach
  prod-scale" 这个组合.
- **spike trigger**: 测 10K / 50K / 100K cuts build wall × 280K pose master,
  画 build cost curve. 找 cliff point.
- **fail signal**: build wall > 30s @ 100K cuts → cut framework 在 prod
  capacity 下 untenable

### N2 — Active filter 失效退化成 full-attach
- **机制**: 设计 active filter 减负, 但实施 bug / by_exterior_watcher 漏 /
  ghost_rect_watcher 误判, 实际 100% cut 被 push 进 master proto, 等于没 filter
- **跟 27 lever 区别**: filter 是 cut framework 独有机制, 27 lever 没这层
- **spike trigger**: spike 在 store 里塞 10K cut, 触发 ghost change, 测
  active set 大小 vs total. expected ratio < 10%, actual > 50% → filter
  broken
- **fail signal**: ghost change 后 active cut ratio > 30% → filter 失效

### N3 — Watcher 退化 (cut 全部要 re-evaluate, 评 frequency 爆)
- **机制**: hot path 10K calls/sec (per Phase 1.3 plan §12.2). watcher 没
  attach 好, 每次 master decision 都 trigger full evaluate; F4 BFS O(|Grid|)
  per call → 10K × 4900 cells = 49M cell op/sec, RSS 雪崩
- **跟 27 lever 区别**: 这是 lazy → hard constraint 转化的实施层 risk,
  paradigm sound 但 perf 死
- **spike trigger**: spike 跑 ≥ 100 master decision, 测 evaluator call
  frequency × per-call wall, 算 throughput
- **fail signal**: evaluator latency > 100µs / call @ 10K calls/sec → watcher
  退化

### N4 — Replay 不收敛 (cut 加进去 master 状态变了, 旧 cert 再 evaluate 失效)
- **机制**: cert 在 state A 生成 sound, master 加 cut 后到 state B, 同 cert
  在 B 上 evaluate 可能 false / unsound. Step 6 attach scope check 应该
  catch, 但 GPT Finding 3 已显示 source_digest 实施 bug
- **跟 27 lever 区别**: cert lifecycle (gen → serialize → deserialize →
  validate → attach → re-evaluate) 6 步是 cut framework 独有, 历史 paradigm
  没这层. per [[proof-object-lifecycle]] memory v4 replay bug 是 known risk
- **spike trigger**: spike 多 iter LBBD, 每 iter 记 cut store 全 state, 跑
  完后用 final state 把每个 cut re-validate, 找 stale invalidation rate
- **fail signal**: stale invalidation rate > 5% → cert lifecycle 实施 bug

### N5 — Multi-family cumulative cut interact 出非预期 INFEASIBLE
- **机制**: F1 region capacity cut + F6 Hall cut + F9 density cut 单独 sound,
  叠加可能 over-restrict (multiple sound necessary conditions 合并 trivially
  imply space 空集). [[adversarial-soundness-audit]] Layer 2 漏的就是这类
- **跟 27 lever 区别**: B1 Phase 5 cell cut 是单 family over-restrictive,
  这里是 multi-family interaction over-restrictive
- **spike trigger**: spike 测 known-feasible candidate (e.g. 15×27 blueprint
  area=405) 加全 F1-F9 cut, 必保 master 仍 feasible (找到那个 known witness)
- **fail signal**: known-feasible candidate 在 cut framework 下 INFEASIBLE
  → multi-family interaction over-restrict, soundness 破

### N6 — Cut store growth 无界 (RSS leak)
- **机制**: cut store rotation / GC defer 到 Phase 1.5+ (per mini spike
  verdict §"Phase 1.5+ defer"). prod 168h 长跑可能 store 长成 millions
  级别, RSS 爆
- **跟 27 lever 区别**: HiGHS / augmented master 是 master 自身 RSS 爆, 这
  里是 cut store 累积 RSS 爆
- **spike trigger**: spike 跑 ≥ 1 candidate 多 iter, log cut store size
  growth curve + RSS. 外推到 168h 估 store cap
- **fail signal**: store growth > 10x linear in iter count → 168h 必爆

### N7 — Strict gate ON 在 prod 数据上 fail-closed 过多 → 没 cut 生效
- **机制**: Phase 1.2 close 把 strict gate default ON (per §8.1). prod 真数
  据 cert 可能更 noisy, validator 把太多 cert reject (fail-closed by design),
  到 master 的 effective cut 为 0
- **跟 27 lever 区别**: strict gate 是新设计, 历史 paradigm 没 cert
  validator 这层
- **spike trigger**: spike 用真 cert (从已有 Phase 3B trial archive 拉),
  measure validator reject rate
- **fail signal**: reject rate > 50% → validator 过严 / cert quality 不够,
  cut framework 在 prod 退化成 noop

### N8 — Cut family bias (1 family 占 99%, 别的全 silent)
- **机制**: prod 真数据可能 F1 / F5 强势, F2/F4/F6/F7/F8/F9 oracle 实际上不
  emit cut. paradigm baseline §4.10 issue 3 manufacturing cluster trap 就在
  F5 retraction 风险层. 整套 framework 退化成单家 paradigm
- **跟 27 lever 区别**: 27 lever 是单 paradigm 死, 这里是 framework 多 family
  实际就活了 1 family
- **spike trigger**: spike per-family cut emit rate measure, 哪个 family
  emit < 1% 标记 "dormant"
- **fail signal**: 1 family > 90% emit → framework 在真数据上退化, 应
  补强或合并

---

## 3. 本次 GPT audit 2 BLOCKER 是不是新死法早期信号?

**答**: 是. 而且**信号 weight 很高**, 因为是 cut framework 内部 hidden
assumption 暴露, 不是表面 bug.

### Finding 1+2 (F7/F8 facility_cells 没 bind 到 pose registry) → N4 replay 失效 + N7 strict gate 同质
- **本质**: validator 用 cert 自带 cells 而不去 pose registry exact match,
  cert 可以 "literal 指 pose A, cells 写 pose B 位置" 形 false positive
- **跟新死法关联**: 这是 N4 (replay invalidation) 的极端形 — 不光 stale,
  是从 generation 就允许 inconsistent. 也是 N7 inverse — strict gate 没
  catch 它该 catch 的, 太松不太严
- **spike 启示**: spike 必有 "validator audit" 阶段 — 故意 inject
  adversarial cert (cert 跟 pose registry 不一致 / cert 跟 state 不一致 /
  cert digest stale), 跑 validator, 必 reject. 0 reject = spike 必 BLOCK

### Finding 3 (source_digest stale 让 attach quarantine) → N2 active filter / N7 strict gate 同质
- **本质**: oracle 用 `state.source_digest or compute_source_digest(state)`,
  state.source_digest 是 caller-side cache. cut 写 scope.source_digest 是
  stale 值, Step 6 attach 重算 digest 不匹配, cut 进 QUARANTINE. 整链路
  "生 cut 但 attach 全丢"
- **跟新死法关联**: 这是 N2 (active filter 退化) 的源头 — filter 实际
  100% reject 不是 100% accept, 但等价于 cut framework 对 master 0
  effective cut. 也是 N7 (strict gate fail-closed 过多) 的 hidden
  precursor
- **spike 启示**: spike 必测 **attach success rate** —— 生成 N cut, 进
  master 的 effective cut M, M/N 必 ≥ 90%. 否则链路漏 cut, framework
  退化

### audit 共同 pattern
2 BLOCKER 都是 **lifecycle 跨 step 接合处的 hidden assumption 漏** (cert
gen ↔ validator binding / state cache ↔ scope digest). spike 设计因此要
特别强 cross-step soundness — 不要只测每步 isolated 通过, 必测整 chain
attach-to-evaluate 闭环.

---

## 4. 跟 Phase 1.1 Gemini 漏 4 critical + Phase 1.2 漏 2 BLOCKER 的 pattern 一致性

| Phase | Gemini 漏 | GPT pro catch (BLOCKER+HIGH) | 漏的 pattern |
|---|---|---|---|
| 1.1 | 4 critical (per [[phase-1-1-go-blessed]]) | R1-R5 5 轮 deliverable 才 close | Layer 2 adversarial soundness (假 cert 能 pass?) |
| 1.2 | 2 BLOCKER (F7 + F8 cells binding) + 2 HIGH (source_digest, spike scope) | 本次 GPT pro audit | Layer 2 同 + lifecycle 接合 |
| 1.3A spike (本次 spike) | ? | ? | **预测**: prod-scale 下 multi-family interaction (N5) + cut store 长跑 RAM (N6) — Gemini 单 family unit test 漏不到 |

**pattern 一致性**: 3 个 Phase 全是 **Layer 1 (单 family unit / API
contract / per-step soundness) close, Layer 2 (adversarial / 跨 step /
prod scale 累积 / multi-family interaction) 留洞**. 来源 [[adversarial-soundness-audit]]
memory.

**spike 必带 Layer 2 武装**:
- Adversarial fixture (假 cert / stale digest / cross-family overlap conflict)
- Multi-family workload (不只单家)
- 多 iter LBBD (不只单轮)
- Real cert from Phase 3B trial archive (不全 synthetic)
- Prod scale variable (280K, 不 50)
- RSS + wall + status 全 measure (不只 build)

**预测**: 本 spike 跑完, GPT pro 还会 catch ≥ 1 Layer 2 finding (类似
"spike 测了 multi-family interaction 但用的是 synthetic state 不是
benders_loop dump 出的真 state, prod 真路径仍 untested"). 这不是 spike
失败, 是 Layer 2 audit 本质 — **每层都会留下层洞**, 重要的是 spike 闭住
本层洞, 让下层洞落进 Phase 1.5+ ramp 区.

---

## 5. Spike 跟 27 lever 哪条最接近 / 最容易撞

**最接近 L12 v8 anchor slicing** (build -92% 真实但 solve 同 quality).
两者形式同构:
- v8: 优化 build wall (sliced anchor 减小 model)
- spike: 验 build wall (10K cuts 加进 master)
- v8 失败: 没量 solve quality
- spike 风险: 如果只 verify "build cost ≤ 30s + attach success", 漏 solve
  prune ratio, 跟 v8 同模式 ❌

**为啥 spike 不会重蹈** (设计承诺):
1. **GO criteria 必含 solve-side metric**: prune ratio vs Phase 3B repair5
   baseline. v8 没这一条所以死.
2. **INFEASIBLE 早停不算 measurement** (per Finding 5 + adversarial design):
   只 feasible OPTIMAL 或 timeout 算真 solve measurement. v8 把 build wall
   improve 当成 win, spike 把 INFEASIBLE 当成 no-data.
3. **多 iter LBBD** (per N1 N5 trigger): v8 单 anchor 单 build, spike 多
   iter 看 cut 累积是否 converge. converge = paradigm work; 不 converge =
   跟 L16 Lazy Power Completion 同死法, NOT GO.

**次接近 L24 augmented master Candidate D** (280K vars × 8 ports = 2.36M
OnlyEnforceIf, 603.9s UNKNOWN + RSS 32 GB).
- 相似性: spike 也是把 N cut 加进 280K pose-bool master, constraint count
  类似量级 (10K cut × ~5 literal = 50K constraint 比 augmented 的 2.36M
  小 47x, 但仍可能 RAM stress)
- **spike 不会重蹈**: cut 是 LINEAR CONSTRAINT 不是 INDICATOR (mini spike
  family map 已确认), CP-SAT presolve 处理 linear 比 indicator 高效 ~10x
  per [[project-30gb-real-culprit-power-coverage]] memory. 但 spike **必测
  RSS peak**, 不假定.

**第三接近 PCR-CUT Phase 5 multi-anchor 0/8 CERTIFIED**.
- 相似性: PCR-CUT 端到端工程跑通但 multi-anchor 不收敛. cut framework 也
  可能多 family 跑通但 multi-iter 不 converge (N5 / N1 兼有)
- **spike 不会重蹈**: cut framework 不只单 separator (PCR-CUT 是 patch belt
  CP-SAT 单一 cut form), 是 9 family 多角度. 但 spike **必测 multi-iter
  converge**, 不假定 family 多就 converge.

---

## 6. Spike 失败的 "Historical analog"

若 spike NOT GO, 它会归到 27 lever 哪种死法? 按 4 root cause 分类:

| Spike 失败模式 | Historical analog | Root cause | 暗示 |
|---|---|---|---|
| Build wall > 30s @ 10K cuts | L24 augmented master RSS 32 GB | RC1+RC4: master expressiveness + RAM | cut framework attach 形被 master 卡死, 类似 augmented master |
| Solve UNKNOWN 跟 baseline 同 quality | L12 v8 anchor slicing | RC1: master expressiveness | cut 没真 prune, framework 等于没装 |
| Multi-iter 不 converge (5 iter UNPROVEN) | L16 Lazy Power / PCR-CUT P5 | RC1+RC2: cut 表达力 + 几何 | cut 累积不 sufficient, framework 跟 PCR-CUT 同模式 |
| Known-feasible candidate INFEASIBLE | B1 Phase 5 cell cut over-restrict | RC2+RC3: 几何 + sym | multi-family interaction 撞穿 sound necessary 条件 |
| RSS > 47 GB peak | L23 rewrite path exhausted + L24 | RC4: 单机 RAM cap | 必 Phase 1.5+ 加 store rotation, 或 fail Phase 1.3A 重设计 active filter |
| Validator reject rate > 50% | (新, 没历史 analog) | (cut framework 独有) | 新死法 N7, 不是 paradigm bug 是 strict gate 过严 |
| Cut store linear growth > expected | (新, 没历史 analog) | (cut framework 独有) | 新死法 N6, store GC 必 Phase 1.5+ 提前 |

**分类用法**: spike fail 后, 看落哪栏. RC1-4 栏 → paradigm 死, 项目需
paradigm shift (但 7 类 attempt 已穷尽, 这条危机非常重); 新死法栏 → cut
framework 实施层调, 不动 paradigm.

---

## 7. 量化 GO criteria (历史 paradigm 视角)

每条带 "为啥这条 threshold 选这个 — 历史教训".

### G1 — Build wall scaling
- **指标**: 280K pose-bool master + 10K cuts 单 build wall ≤ 30s
- **历史依据**: per mini spike "30s GO threshold", per `CLAUDE.md` master
  `--max-time-in-seconds=30s` per iter convention
- **历史教训**: L24 augmented master 30 GB / 603.9s 是 build/solve 一起雪崩
  的 reference fail point. 30s build cap 留 580s 给 solve 完成 single iter,
  类似 cand C Phase 1 单 iter budget

### G2 — Solve wall + status
- **指标**: known-feasible candidate (e.g. corner 5×5) 加全 family cut 后,
  master 单 iter ≤ 60s OPTIMAL (不 UNKNOWN 不 INFEASIBLE)
- **历史依据**: cand C Phase 1 5-inst 5s OPTIMAL, 20-inst 30s OPTIMAL 是
  baseline; 加 cut 不该让 OPTIMAL 变 UNKNOWN
- **历史教训**: L12 v8 死法 — 不能只测 build, 必测 solve OPTIMAL

### G3 — Multi-iter convergence
- **指标**: ≥ 5 LBBD iter, search tree node count 单调减 ≥ 30% per iter, 或
  iter 5 vs iter 1 prune ratio ≥ 2x
- **历史依据**: PCR-CUT Phase 5 70 cut sustain OPTIMAL 不收敛是反例; cand C
  Phase 1 dual ramp 8/8 GO 是正例
- **历史教训**: L16 / PCR-CUT P5 / B1 P6 path-2 全死于不收敛, spike 必早期
  catch

### G4 — Attach success rate
- **指标**: oracle 生 N cut, Step 6 attach success M, M/N ≥ 90%
- **历史依据**: GPT Finding 3 source_digest stale 直接让 M/N = 0%, 是 spike
  trigger 这个 risk 的直接动机
- **历史教训**: cut framework lifecycle 6 步任一断 = framework 0 effective

### G5 — FP rate (sound 验)
- **指标**: 跑完后 sample 100 cut + 真 master state, replay validate, 0 false
  positive
- **历史依据**: Phase 1.1 close gate "FP=0", Phase 1.2 GPT Finding 1+2 暴露
  FP > 0
- **历史教训**: cut framework FP=0 是数学红线, 不能漂

### G6 — Multi-family balance
- **指标**: cut emit rate, 单 family ≤ 70%, ≥ 3 family active emit
- **历史依据**: paradigm baseline §4.10 issue 3 manufacturing cluster trap
  (F5 retraction 风险); 4 root cause 翻译给 cut framework "表达几何+物流多
  类型 INFEASIBLE"
- **历史教训**: framework 退化成单 family = 退化成单 paradigm = 跟 PCR-CUT
  / RAB-SEP 单 separator 同死

### G7 — RSS peak
- **指标**: spike 跑期间 psutil RSS peak ≤ 40 GB (留 8 GB headroom 给 OS +
  缓冲), per worker
- **历史依据**: Phase 3B repair5 master baseline 30-47 GB, 单机 48 GB cap;
  P1 #24 4-parallel OOM 是反例 ([[project-p1-24-oom-blocked]])
- **历史教训**: 单机 RAM 不可扩 (RC4), spike 撞 RAM cap = framework 在 prod
  必 OOM

### G8 — Adversarial validator pass
- **指标**: inject 20+ adversarial cert (cert ↔ pose registry mismatch /
  stale digest / forged cells / cross-instance scope), validator 全 reject
- **历史依据**: GPT Finding 1+2+3 直接动机; [[adversarial-soundness-audit]]
  Layer 2 政策
- **历史教训**: Gemini 漏 Layer 2 几乎是 3 Phase 一致 pattern, spike 必自
  带 adversarial fixture

### G9 — Stale cert invalidation rate
- **指标**: spike 多 iter 跑完, 用 final state validate 所有 store 中 cut,
  stale rate ≤ 5%
- **历史依据**: [[proof-object-lifecycle]] memory v4 replay bug + Finding 3
  digest stale 都是 invalidation 信号
- **历史教训**: cert lifecycle 实施 bug 比 paradigm 数学 bug 更隐蔽 (sound
  但 attach 错), 必量化

---

## 8. 量化 NOT GO criteria (撞历史死法 pattern → abort)

每条 NOT GO 必关联**一个具体历史 lever**, 不是抽象 abort.

| NOT GO 触发条件 | Historical analog | Abort 后路 |
|---|---|---|
| Build wall > 60s @ 10K cuts | L24 augmented master | Phase 1.3A 设计 active filter / store rotation 加密, 不前进 1.3B |
| Solve UNKNOWN @ known-feasible candidate | L12 v8 anchor slicing | Phase 1.2 cut family 翻成 master constraint 形要重设计, 退回 §3 mini spike form mapping 重审 |
| Multi-iter 5 iter 全 same prune (不收敛) | L16 Lazy Power Completion | cut framework 累积不 sufficient, 必加 Phase 1.5+ orbit-aware lift 提前到 Phase 1.3A |
| Known-feasible candidate INFEASIBLE | B1 Phase 5 cell cut over-restrict | 1 个或多个 family 数学 unsound, fail-closed retract family, 不前进 1.3B |
| Attach success rate < 50% | Finding 3 source_digest stale 极端形 | Phase 1.3A 暂停, 重整 cert lifecycle 6 步实施, 跑额外回归测 |
| FP rate > 0 (1 个就算) | Finding 1+2 false-positive | Phase 1.2 close gate 撤回, retract Phase 1.2 verdict, 加全 family pose-registry binding audit |
| RSS > 47 GB | L23 / L24 / P1 #24 OOM | 单机 RAM cap 撞, cut store cap / GC 必前移到 1.3A |
| Adversarial validator pass < 100% | Layer 2 audit 漏 | 当场加 missing fixture, 不进 1.3A 直到全 pass |
| 单 family emit > 95% | paradigm baseline §4.10 issue 3 | framework 退化成单 paradigm, 必补 family 或合并 |
| Stale cert invalidation > 20% | [[proof-object-lifecycle]] v4 bug | cert lifecycle hidden bug, 暂停 spike, 加 invalidation regression test |

**Abort 政策**:
- 任何 1 条 NOT GO 触发 = spike NOT GO, 不前进 Phase 1.3B
- 多条同时触发 = paradigm level review, 评估是不是 cut framework 自身要调
  (新死法证据) 或撞历史死法重蹈

---

## 9. 工时估 (Claude pace per [[work-time-estimates]])

| Step | Wall-clock | Agent work | Notes |
|---|---|---|---|
| Spike scope freeze (本 doc + main merge 4 路 slant) | 2-3 hour | 1 hour | main agent merge work |
| Real cert harvest (从 Phase 3B trial archive 拉 1000+ cert) | 1 hour | 30 min | grep + jq + dump |
| Adversarial fixture build (20+ fixture) | 2 hour | 1 hour | 主要写 |
| Spike harness (prod-scale master + cut store + LBBD outer) | 4-6 hour | 2 hour | reuse benders_loop scaffolding |
| Spike single run (1 known-feasible candidate, 5 iter) | 30-60 min wall | 0 agent | actual CP-SAT solve, 死时间 |
| Spike known-INFEASIBLE run (1 candidate, ≥ 1 iter) | 30-60 min wall | 0 agent | 同 |
| Adversarial validator run | 5 min wall | 0 agent | 单 process inject + assert |
| Multi-iter convergence + RSS profile run | 1 hour wall | 0 agent | 5 iter × ~10 min |
| Analyze + verdict.md | 2 hour | 2 hour | metric 整理 + GO/NOT GO map |
| GPT pro audit pack (per [[big-milestone-gpt-pro-review]]) | 1 hour | 1 hour | zip + README |
| **总计** | **~12-18 hour wall** | **~8-10 hour agent** | 含 ~3-4 hour 死时间 (CP-SAT 长跑) |

**对比 mini Step 8 spike**: mini 工时估约 1-2 hour, 本 spike ~10x. 因为
prod scale + adversarial fixture + multi-iter LBBD + 真 cert. 这个 10x 是
合理代价 (mini 50 BoolVar 不 cover prod risk, 必须升)

**死时间**: CP-SAT 真跑约 2-4 hour 不可压. agent 期间可 parallel 写 analyze
脚本 + 准备 GPT pack.

---

## 10. 我 historical-paradigm slant 偏向 (自承)

**why I might over-anchor history → miss 新可能**:

1. **27 lever 都死的滤镜让我 default 悲观**. spike NOT GO criteria 我列了
   10 条, 每条都关联历史 lever. 但 cut framework 是 4 root cause **唯一**
   满足 paradigm — 它有 fundamental reason 不死. 我可能 systematic 低估
   "spike GO" 概率, 让 GO criteria 过严, NOT GO 过松.

2. **多 Layer 2 audit 漏 pattern 让我对 spike 自身信任度低**. 我说 "spike
   跑完 GPT pro 还会 catch ≥ 1 Layer 2 finding" — 这预测可能太悲观, 让用户
   觉得 spike "无论怎么做都不够". 应该 frame 为 "spike 闭住本层, 下层 risk
   预算给 Phase 1.5+", 不是 "spike 必有漏".

3. **per-lever cite 让 design 看上去 paranoid**. spike 实际可能 1-2 个核心
   risk 决定 GO/NOT GO (build wall + solve quality), 不是 10 个 risk
   parallel. 我列 10 条让 spike 复杂度看起来高, 实施时可能反而抓不住重点.
   correctness / throughput slant 可能 frame 简洁, merge 时 main agent 要
   warning 我.

4. **历史死法套件 ≠ 全可能**. 我列的新死法 N1-N8 都从历史外推, 但真新死
   法可能 N9+ 我没想到 (e.g. CP-SAT 9.15 → 9.16 升级时 cut framework 跟新
   presolver 不兼容; multi-process spawn worker 各自 cut store 不同步,
   一致性 bug). 我对 "unknown unknown" 的 coverage 必有 gap.

5. **PROJECT_LOCK red line 我 default 不质疑**. 比如 "禁跨 instance lifting"
   是 §3A red line, 我直接当 spike 必遵, 不评估 "spike 可以临时 enable 看
   prod 真数据下 lifting 还会不会 trivial". 这是历史 anchor 让我保守, 不
   挑战 baseline.

**main merge 时建议**: 把我的 NOT GO criteria 数量从 10 砍到 4-5 个核心
(build wall + solve quality + FP=0 + RSS); 历史 cite 留 1 个 paragraph
不是 per-criterion; 新死法 N1-N8 留 reference 不进 spike 主流程 (作 Phase
1.5+ ramp 监控指标).

---

## 11. 潜在 blind spot

1. **CP-SAT 内部行为我没建模**. spike 设计假定 build / solve / presolve 是
   3 个独立阶段, 但 9.15 实测可能 presolve 消化 cut 期间出 unexpected
   behavior (e.g. presolve 把 multiset nogood expand 成 2^n disjunct).
   spike 必加 "presolve report" 抓非预期 expansion.

2. **multi-process 没建模**. 项目 production 4-parallel worker, 但 spike
   我默认 single-process. workers 间 cut store 不共享 (per [[project-30gb-real-culprit]]),
   实际 prod cut 累积 4x 慢. spike 应至少跑 1 个 multi-process scale 测.

3. **历史 lever 没全 cite**. 我挑了 ~15 个最相关 lever, 27 lever 里有些
   (e.g. v3 / GPT-5.5 hint scheduling / SMT-MT Phase 1) 可能跟 spike 有
   latent 关联. 比如 SMT-MT inner UNPROVEN → prune 0.75% 模式 跟 N3 watcher
   退化有 surface 相似. 没全 mapping.

4. **新 paradigm 内部死法可能我都低估**. N1-N8 是从历史外推, 假定 cut
   framework 死法跟旧 paradigm 同结构. 实际新死法可能完全异质 (e.g. cut
   store + watcher + lifecycle 6 步组合产生的死法没历史 precedent).

5. **历史死法之间的 interaction 没建模**. 27 lever 是单 lever 死, 但 cut
   framework 多 family + 多 lifecycle step 同时跑, 可能产生 "L12 build cost
   控好了但 L24 RAM 仍爆" 这类组合 fail. spike 单维度量 metric 漏组合.

6. **Adversarial fixture 不全覆盖 Layer 2**. 我列 8 类 fixture (假 cert /
   stale digest / cross-instance / multi-family overlap / 等), 但 Layer 2
   定义本质是 "我没想到的攻击". 必 spawn 独立 adversarial subagent (per
   [[design-phase-n-parallel-agents]]) 跑一遍, 不只我自己 brainstorm.

7. **"cut framework 是 4 root cause 唯一满足 paradigm" 这个论证可能过强**.
   死亡 baseline §4.9 说 "不得不走的路", 但 paradigm 数学 sound 不等于工程
   可行 (cand C Phase 1 GO Phase 2 v3 INFEASIBLE 是 reference). spike 失败
   不 necessarily 推翻 cut framework paradigm, 但我 default 不区分 "paradigm
   死" vs "工程实施死", historical anchor 让我倾向 "工程死" — 但可能真是
   paradigm 死.

---

**END of historical-paradigm-context design**.
