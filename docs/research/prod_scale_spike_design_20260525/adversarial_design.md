# Prod-scale Spike — Adversarial Design

**Date**: 2026-05-25
**Slant**: adversarial (per orchestrator). 任务：设计 prod-scale spike, 让
GPT pro audit Finding 5 提的 risk **全部 trigger**, 不让 INFEASIBLE 早停
掩盖 solve cost. 每个 design choice 都问"这个 case 没 cover 哪个 risk?".
**Author**: opus subagent (adversarial slant); main 之后会 merge correctness /
throughput / integration / simplicity 4 路.

## 0. 锚定 ground truth

| 项 | 值 | 来源 |
|---|---|---|
| Mandatory instance | 266 | `data/preprocessed/mandatory_exact_instances.json` |
| Pose registry total | 81,795 (~280K with rotation/port mode) | `data/preprocessed/candidate_placements.json` |
| Facility pool 数 | 7 | 同上, `facility_pools` 顶层 keys |
| Largest pool | manufacturing_3x3, 17,952 pose | 同上 |
| 大 grid | 70×70 = 4,900 cell | PROJECT_LOCK |
| Master variable count (估) | 81,795 pose-bool 或 ~280K slot-indexed | per [[b1-phase2-production-land]] |
| Mini Step 8 spike scale | 10 group × 5 pose = **50 BoolVar** | `spike_translator.py:43-44` |
| GPT pro Finding 5 ratio | prod **/ toy = 1,635x pose**, 26.6x group | 280K/50 = 5600, 266/10 |

**Finding 5 一句话**: spike 测的是 50 BoolVar toy + synthetic random cuts +
INFEASIBLE 早停, **不能**外推到 280K pose + 真 cert + feasible long-run solve.
verdict 里写的 "prod 约 50× = 5-6s build" 这个 50x 乘数本身是 hand-wave (实际
ratio 1,635x), 而 solve cost 因为 INFEASIBLE 早停**根本没测**.

---

## 1. Risk Inventory (≥10 类)

每类 risk 带 **attack scenario** (具体怎么让 spike 漏掉).

### R1 — Pose universe scale 折线断点
**Risk**: build cost 不是 mini spike 假设的 linear-in-cuts. CP-SAT 内部
constraint→variable hash, presolve domain propagation, 在 50 vs 280K
variable 上 cost curve 可能完全不同 (cache miss / hashmap rehash threshold).
**Attack**: spike 只测 50 BoolVar, prod 280K 上 build 实测可能 >50x mini
预测 (worst case quadratic-ish 在 domain reduction).
**spike miss 标志**: 不测 prod scale 真 BoolVar 就 GO.

### R2 — Real cut body size 分布 vs 1-3-5 literal toy
**Risk**: mini spike 的 F3/F5/F7 multiset cut 都是 6 literal hardcoded
(`spike_translator.py:189-192`). 真 cut body:
- F2 cutset 可能含 50-200 blocker pose (separator 大)
- F4 component_reach 同量级
- F6 region_pose_set 在 70×70 region 上可达 4000+ pose membership
- F7 power_hitting_set CoverSet 实测 45+ cell × 多 pose = 100s+
**Attack**: 真 cut body 比 toy 大 1-2 数量级, 单 cut constraint registration
cost + proto serialize cost 完全不同.
**spike miss 标志**: 用 toy literal count 不取真分布.

### R3 — INFEASIBLE 早停掩盖 solve cost (Finding 5 直接提)
**Risk**: spike 1K/10K case 全 INFEASIBLE, CP-SAT 几 ms 检 conflict 退出.
prod 真迭代 master.solve 在 feasible region 里搜 candidate, solve time
完全不一样 (Phase 3B 实测可 600s+ UNKNOWN — [[lever24-augmented-master-dead]]).
**Attack**: spike 报告 "solve 2ms 没问题" 但 prod 真接进去后 solve 几百秒
甚至 UNKNOWN.
**spike miss 标志**: 不强制 feasible long-solve case 就 GO.

### R4 — RSS / 内存峰值
**Risk**: prod master.solve peak 30 GB (per [[30gb-real-culprit-power-coverage]]),
8 worker 时. mini spike 没测内存. cut framework 加进去后 worker propagation
buffer 可能再加 10-50%.
**Attack**: 单机 48 GB 撞 OOM, 跟 [[p1-24-oom-blocked]] 同种死法.
**spike miss 标志**: 不用 psutil 量 RSS 就 GO.

### R5 — Proto ByteSize / 序列化爆炸
**Risk**: CP-SAT 内部把 model 序列化成 proto 给 C++ solver. 10K cut × 数百
literal each → proto 几百 MB. 单进程内存不爆, 但 multiprocess.spawn fork
worker 时 proto 复制 8 份 = GB 量级.
**Attack**: workers > 1 时 spawn 阶段 OOM, master 单 process 跑得动但并行起
不来.
**spike miss 标志**: 不量 `model.Proto().ByteSize()` 就 GO.

### R6 — Active cut filter / store rotation 缺失
**Risk**: cut framework 没 GC, 10K 全 active 累. prod 每个 LBBD iter 加 ~10-50
cut, 168h × 60-100 iter/h 累 100K+. mini spike 没测 rotation / GC.
**Attack**: cut store unbounded growth, RSS 线性涨直到 OOM, master rebuild
cost 线性涨直到 wall-clock 超 30s budget.
**spike miss 标志**: 不测 active filter (per [[gpt-pro-p1-2-in-progress-review]] #3)
就 GO.

### R7 — 跨 family interaction (variable structure conflict)
**Risk**: mini spike 用统一 BoolVar `x[g, p]`. 实际 production master
用 pose-bool 或 slot-indexed (per spike verdict §3 caveat). F3/F5/F7 multiset
nogood 在 slot-indexed 下要 `2·x_count[g,p] ≤ K-1`, 跟 mini 用的 `count·x[g,p]`
**不同 semantic** (前者 tight, 后者 loose-but-sound). 切到 prod master 时
constraint shape 全要改.
**Attack**: spike 报 GO 但 prod master 一接进去 cut soundness 都对不上,
要么 over-cut (false positive) 要么 under-cut (no convergence).
**spike miss 标志**: 用跟 prod 不一样的 var structure 测.

### R8 — Geometric cut scope drift (Finding 1-3 同种 schema bug)
**Risk**: GPT pro Finding 1-2 catch F7/F8 validator 不验 `facility_cells ↔
candidate_placements`, Finding 3 catch source_digest stale. spike 用 synthetic
cut **绕过** validator, 完全没测这种 schema-level attack 在 prod scale 下
还能不能 catch (10K cut 中只要 1 个 stale digest 就污染整个 store).
**Attack**: prod 接入后 validator 真跑, schema bug 在 10K rate 下漏一两个,
攻击者 (或随机噪音) 注 stale cut, store 静默污染.
**spike miss 标志**: 不 inject 已知 bad cert 测 quarantine rate.

### R9 — Solve quality vs UNKNOWN 退化
**Risk**: 加 cut 本应让 master 收敛更快. 但 cut 太多 / 太弱时 CP-SAT
propagator overhead > 收益, solve 反而退化到 UNKNOWN. mini spike 没测
"cut count vs solve quality" curve.
**Attack**: spike GO 但 prod 加 cut framework 后 OPTIMAL → UNKNOWN, 收敛
反而变差 (跟 [[lever24-augmented-master-dead]] 同种 master.solve 解不动死法).
**spike miss 标志**: 不在 feasible case 上做 "with cuts vs without cuts"
回归对比.

### R10 — Multi-worker scaling
**Risk**: prod 用 `--parallel-processes 4` (or 1 per [[30gb-real-culprit]]).
mini spike 单进程. worker 共享 cut store 时同步 cost / serialization /
RSS 倍数全没量.
**Attack**: spike 单 worker GO, 4 worker 启动后 IPC / spawn proto copy /
shared cut store 同步撞死.
**spike miss 标志**: 不测 multiprocess.spawn workers ≥ 2 就 GO.

### R11 — Long-run state drift
**Risk**: 168h campaign 中 ghost rect 变, source_digest 变, scope 失效的 cut
积累. mini spike 测 single iter rebuild, 不测跨 iter state mutation.
**Attack**: 多 iter 后 store 里大量 quarantine cut 占内存但 useless.
**spike miss 标志**: 不模拟 ≥10 iter LBBD loop with state mutation 就 GO.

### R12 — Determinism / replay 失效
**Risk**: PROJECT_LOCK 要 deterministic. multi-thread CP-SAT propagator
callback 顺序 + cache pollution 跨 worker 可能让 same seed 不同 cut order.
**Attack**: spike 跑两次 GO, prod 上同 seed 重跑结果不一样, replay 失效.
**spike miss 标志**: 不跑 N≥3 重复 with same seed 验 bit-equal 就 GO.

### R13 — Warmstart / hint interaction
**Risk**: prod 用 community blueprint hint (per CLAUDE.md `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH`).
hint + cut 同时存在时 CP-SAT propagation 顺序未定. mini spike 没 hint.
**Attack**: spike GO, prod hint + cut 共存 → hint 被 cut quarantine 或 cut
被 hint 绕过, 两边收益都丢.
**spike miss 标志**: 不带 hint 测就 GO.

### R14 — Time-budget interaction (max-time-in-seconds)
**Risk**: prod master `--max-time-in-seconds=30s` per iter. mini spike 用 30s
但 INFEASIBLE 早停 0.002s, 30s budget 没意义. prod 真 solve 撞 30s 上限时
CP-SAT 返 UNKNOWN, cut framework 接 UNKNOWN 的逻辑 mini 没测.
**Attack**: spike GO, prod 大量 UNKNOWN, 整 framework 不知怎么消化 UNKNOWN
verdict (UNKNOWN 是否要 cut? 不能 cut, sound 不成立 — [[smt-mt-phase1-marginal]]
踩过这坑).
**spike miss 标志**: 不在 30s budget 边界测 UNKNOWN path 就 GO.

### R15 — Cut order sensitivity
**Risk**: 10K cut 加入 master 顺序影响 propagator 早期裁剪效率. mini spike
按 synth 顺序固定, 没测 shuffle.
**Attack**: spike 用 favorable 顺序 GO, prod LBBD 真生成顺序差异大, build
cost 翻倍.
**spike miss 标志**: 不测 ≥3 种 cut 加入顺序 (LIFO / FIFO / family-grouped)
就 GO.

---

## 2. 每 Risk 对应 test case

| Risk | 必含 test case | 该 case 触发 risk 的机制 |
|---|---|---|
| R1 | TC-prod-vars: 用真 `candidate_placements.json` 建 ~280K BoolVar master | 直接 trigger CP-SAT hashmap / domain prop 在真 scale 下的非线性 |
| R2 | TC-real-body: 从 7 family oracle 真跑出 N=200 cut, 量 literal 分布; 用真分布 sample 合成 10K cut | trigger 真 cut body size (50-200+ literal each), 不靠 6-literal toy |
| R3 | TC-feasible-long: 用 IP v2 blueprint 已知 feasible 配置作 master state, 加 10K **应当全 pass** 的 cut (scope 跟当前 ghost 完全 disjoint), 强制 solve 找完整 feasible solution | INFEASIBLE 不发生, solve 真跑到底, wall-clock 暴露真 solve cost |
| R4 | TC-rss: 全程 `psutil.Process().memory_info().rss` sampling 100ms 一次, 报 peak / steady | 直接量 RSS, 不再 hand-wave |
| R5 | TC-proto: build 完后 `model.Proto().ByteSize()` + serialize to disk 测 wall, 跟 toy 比 | 量 proto 真大小; 8 worker 时乘 8 算预估 spawn cost |
| R6 | TC-rotation: 跑 50K cut, 启用 active filter (top-K by score), 验 store size 上限 + RSS 不线性涨 | 模拟 168h 累积; 没 filter 时 trigger R6 死法 |
| R7 | TC-var-shape: 同 cut body 在 pose-bool 跟 slot-indexed 两种 master var 下都过 (or 报 cut translator 适配代价) | 强制 spike 暴露 var structure mismatch, 跟 prod master rewrite 同步 |
| R8 | TC-adversarial-cert: inject 50 个已知 bad cert (Finding 1-3 patch 后 validator 必拒) + 10K good cert, 验 quarantine 率 = 50/10050 = 0.498% 精确 | trigger schema attack 在 prod rate 下还能 catch |
| R9 | TC-with-vs-without: 同 feasible state 两路 — (a) 不加 cut solve, (b) 加 10K cut solve. 对比 wall-clock + status. 必须 (b) ≤ (a) 或 status 不退化 | 直接 trigger cut framework 是否真有用 |
| R10 | TC-multiproc: `multiprocessing.spawn 4 worker` 各自 build master + 10K cut, 测启动 wall + 总 RSS + 是否撞 OOM | trigger spawn proto copy + shared store |
| R11 | TC-lbbd-loop: 模拟 ≥10 iter LBBD, 每 iter ghost rect 变 (cycle 5 size), source_digest 跟变, 验 store 里 stale cut 比例 + quarantine path 正确 | trigger 跨 iter state mutation 实际行为 |
| R12 | TC-determinism: 同 seed 跑 3 次, 验 cut order / solver branch / objective 全 bit-equal | trigger replay 失效 |
| R13 | TC-hint-coexist: 注入 IP v2 blueprint hint + 10K cut, 验 hint 不被 quarantine + solve 用上 hint | trigger hint × cut interaction |
| R14 | TC-unknown-path: 让 master.solve 撞 30s budget 返 UNKNOWN, 验 framework 不把 UNKNOWN 当 FEASIBLE 也不当 INFEASIBLE 错生 cut | trigger UNKNOWN handling soundness |
| R15 | TC-order: 同 10K cut 3 种顺序 (LIFO / FIFO / family-grouped) 各跑一次, 报 build + solve wall 差异 | 暴露 cut order sensitivity |

---

## 3. Feasible Realistic Case 设计

GPT pro Finding 5 最难的一条: spike 必须**真 solve**, 不能 INFEASIBLE 早停.

### 怎么造一个 feasible state?

**Source**: IP v2 community blueprint `/home/zhuran24/下载/BP-2026-05-13 08_35_36.blueprint(1).json`
(per CLAUDE.md D step 2 hint 注入). 这是用户手调验证 feasible 配置, 225
instance 落 placement. 已有 converter
`scripts/blueprint_to_master_hint.py` 把它转成 `Dict[instance_id, pose_idx]`.

**Master state 构造**:
1. 用 blueprint converter 产 hint dict
2. 把 hint 当 hard constraint 写进 master (`x[i, p] == 1` for 225 instance)
3. 剩下 41 mandatory instance 用 candidate_placements 里 default pose 占位
4. ghost rect 用 blueprint 自然 max empty rect 15×27 area 405

**Cert / cut body 必须长什么样 (避免 INFEASIBLE)**:
- 10K cut 全部 scope 跟 current ghost / hint **disjoint** — 也就是
  cert 描述的 region / cover_set / blocker 都在 hint 配置之外的 facility
  上, 或在 ghost rect 之外 cell 上
- 具体造法: 把 oracle 反过来用 — 给一个**不会被 hint 触犯**的 fake violation
  (e.g., region 在右下角 10×10, 该区只 1 个非 hint instance), oracle 不发,
  自己用 oracle 同 schema 合成 cut payload
- F8 forbid pose 全选 `(g, p)` 中 `p` 是 hint 没用到的 pose_idx

**为啥这样必 feasible**: 因为 hint 已经是 user-verified valid solution,
所有 hint instance 跟 ghost / power / port 都 consistent. 额外加的 cut 全
disjoint, 不破坏 hint, 所以 master 至少能 retain hint solution → feasible.

**solve 不早停的保证**:
- 不能让 solve 立刻 hit hint solution 退出 — 把 hint 写成 `AddHint`
  (soft) 不是 hard, 加一个 objective `maximize sum(non-hint-pose)`, 让
  solver 必须**搜整个 feasible region** 找 max, 不能直接返 hint
- 或者直接 `Solve` 求 first feasible 但加 `--enumerate-all-solutions=true`
  限制 N solutions, 让 solver 走完整 BCP / probing

### Solve wall 量化目标

不卡死 budget, 但要测出 wall:
- baseline (no cut): record wall_a
- with 10K cut: record wall_b
- GO: wall_b / wall_a ≤ 1.5 (cut framework <50% overhead)
- NOT GO: wall_b / wall_a > 5 (cut framework 退化太重)
- 中间 1.5-5 → AMBER, 进 P1.3B 逐步优化

---

## 4. INFEASIBLE 早停掩盖 cost 的反制

**直接证据**: spike 必须报告 4 个数, 不报齐不能 GO:

| Metric | 含义 | min 阈值 |
|---|---|---|
| `solver.NumBranches()` | CP-SAT 实际搜索 branch 数 | ≥ 1,000 (否则没真 search) |
| `solver.NumConflicts()` | 真触发的冲突 | ≥ 100 |
| `solver.WallTime()` | solve wall-clock | ≥ 1.0s (否则 fast trivially) |
| status | OPTIMAL / FEASIBLE / UNKNOWN | 不准 INFEASIBLE |

如果 case INFEASIBLE → spike 必须**单独标注 R3 漏测**, 不能算 solve cost
data point.

**反向验证**: 跑同 case 但**不加任何 cut** (baseline), 再跑同 case 加 10K
cut. 两次都要 status ≠ INFEASIBLE, 才能比较 wall_a vs wall_b 测 cut overhead.

**冗余检查**: spike 报告里**强制**列每个 scale (100/1K/10K) 各自 4 metric +
status, reviewer 一眼能看出哪个 case 是 trivial early-exit.

---

## 5. Adversarial cert/cut shape (Finding 1-3 在 prod scale 下)

**问题**: spike 默认绕 validator. 但 prod 接入后 validator 跑, 如果 schema
attack 在 10K rate 下漏 1-2 个, store 静默污染.

**Adversarial test**:

### TC-inject-bad-cert
1. 写 4 类 bad cert generator (各派 1 个变体):
   - **F7 fake facility_cells** (Finding 1 attack scenario)
   - **F8 fake facility_cells** (Finding 2 attack scenario)
   - **stale source_digest** (Finding 3 attack scenario)
   - **scope drift** (cut scope `ghost_rect` 跟 state.ghost_rect 不匹配)
2. spike 跑 10K cut, 其中:
   - 9,950 good cut (synthetic but passes Finding 1-3 patch)
   - 50 bad cert (10 each + 20 random 其他 schema attack)
3. 验:
   - validator 拒掉 50/50 bad cert (FP=0 maintained at prod rate)
   - quarantine path 触发 + cert 不进 active store
   - reviewer 能看到 quarantine 报告精确

### GO 标准 (Finding 1-3 maintained at scale)
- 50 bad cert 100% quarantined (1 漏 = NOT GO)
- quarantine wall < 100ms (不能阻塞主 path)
- store active size 精确等于 9,950 (不能多不能少)

**为啥要在 spike 测 不只在 unit test**: unit test 每个 patch 测 1-2 个
adversarial case. prod scale 下要测 **10K rate + bad cert 混入比例** 还能
不能 catch — 量变可能引出 quality issue (e.g., hash collision 让 stale
digest 偶尔 match, 或 batch validate 时 caller 错过 individual fail).

---

## 6. Spike 自己的 blind spot (meta-adversarial)

即便 R1-R15 全 cover, spike 还可能漏:

### B1 — Synthetic cut 不能完全模拟 oracle 真行为
oracle 发 cut 的时机依赖 master state. spike 预生成 10K cut 写死, 跟"oracle
在每 iter 根据 state 真发" 不一样. **mitigation**: 至少跑一个 mini end-to-end
trial (3 iter LBBD 真启 oracle), 看 cut 实际 emission rate vs synthetic 假设.

### B2 — CachyOS / jemalloc / isolcpus / THP 主机特殊性
spike 跑机器 = prod 跑机器 = 同一 i9-13900KS + CachyOS. 但 mini spike 没
量过这些 host-level 调优对 cut framework 的实际影响 (e.g., jemalloc 多线程
arena 对 CP-SAT propagator 友好度未知). **mitigation**: spike 必须在
`bash scripts/run_campaign_linux.sh` wrapper 下跑, 跟 prod 同环境.

### B3 — Cold start vs warm cache
首次跑 spike OS file cache 冷, 10K cut JSON / proto 序列化撞 disk. 第二次
跑全 warm 数据不一样. **mitigation**: 跑 3 次 (cold, warm, warm), 报中位数
+ 全部 3 个值.

### B4 — Spike 用 deterministic synthetic, 漏 stochastic 行为
prod CP-SAT 用 random seed (虽 deterministic), 但 cut 真生成有 timing
race (multi-worker). spike 不测 race condition. **mitigation**: TC-multiproc
跑时跑 5 次, 看是否出现 wall-clock 长尾.

### B5 — Spike GO 不等于 paradigm GO
即便 spike 全 GO, P1.3B 接入后仍可能撞 paradigm-level 死法 (24 lever 经验).
spike 是 implementation feasibility, 不是 algorithmic convergence.
**mitigation**: spike GO 后必跑一个 24h prod trial 验真 convergence (跟
Phase 1.3B 的 GO 标准对齐, 不替代).

### B6 — Adversarial slant 自己的盲点
我这版设计 over-emphasize 单 master single-shot integration. 漏了**整 LBBD
loop 跨 subproblem 的 interaction** (binding / routing / flow 跟 cut framework
共存). spike 单独测 master 可能 GO 但跟 binding subproblem 接一起死.
**mitigation**: B5 那个 24h trial 必带全 stack, 不只 master.

---

## 7. 量化 GO criteria

spike 必须 trigger **≥12 of R1-R15** 且每个 trigger case **expected behavior**:

| Risk | Trigger 证据 | Expected behavior |
|---|---|---|
| R1 | 280K BoolVar 实际 build | wall ≤ 60s, RSS peak ≤ 20 GB |
| R2 | 真 oracle 跑出 N=200 cut 测的分布 | 跟 mini 6-literal 差异报告 |
| R3 | 10K cut 在 feasible state 上 solve 不早停 (≥1K branch, ≥1s wall) | wall ≤ 1.5x baseline no-cut |
| R4 | psutil RSS 全程 sampling | peak ≤ 30 GB single worker |
| R5 | proto.ByteSize() 实测 | < 500 MB (8 worker spawn 安全) |
| R6 | 50K cut + active filter on | store size ≤ filter 阈值, RSS plateau |
| R7 | pose-bool + slot-indexed 两路都过 OR 报 adapter cost | adapter 代码量 ≤ 200 LOC |
| R8 | 50 bad cert 100% quarantine | 漏 0 |
| R9 | with-cut vs no-cut feasible 比较 | wall_b/wall_a ≤ 1.5 OR status 不退化 |
| R10 | spawn 4 worker | 启动 wall ≤ 60s, 总 RSS ≤ 40 GB |
| R11 | 10 iter LBBD with state mutation | stale cut 比例 ≤ 30% |
| R12 | 3 重复 same seed | bit-equal verified |
| R13 | hint + cut 共存 | hint 不被 quarantine, solve 用上 hint |
| R14 | UNKNOWN path | framework 不基于 UNKNOWN 错生 cut |
| R15 | 3 种 cut order | wall 差异 ≤ 2x |

**GO**: ≥12/15 risk triggered + expected behavior. ≤2 risk 在 AMBER (可接受
但需 P1.3B 关注). 0 risk NOT GO.

**Phase 1.3A close gate** (per Finding 5 建议): 这个 prod-scale spike 跑过
+ verdict GO, 才能进 P1.3B master integration.

---

## 8. 量化 NOT GO criteria (spike 漏 risk → abort + 重设)

任一以下 trigger → spike abort + 重新设计:

1. **任何 risk 没法实施 trigger** (e.g., 找不到 feasible state generator 让
   solve 真跑). 报告"spike 漏 R-X" + 给出还需的工具/数据.
2. **某 risk trigger 但 expected behavior 没达** (e.g., R4 RSS peak 60 GB).
   报告 NOT GO + finding, 进 P1.3B 前要先优化.
3. **3+ risk simultaneous NOT GO**: spike 自身 framework 有结构错误, 重新
   设计 (e.g., 整个 var structure 选错, 7 risk 同时报问题).
4. **发现新 risk 不在 R1-R15** (e.g., spike 跑出来 R16): 立即停, 加进 risk
   inventory, 重设 spike cover R16, 然后重跑.
5. **Reproducibility 失效**: spike 跑两次 verdict 不一致 → 框架自身不
   deterministic, abort.

---

## 9. 工时估 (Claude pace)

per [[work-time-estimates]] 用 Claude 节奏估, 死时间分开报.

| 阶段 | Claude 工时 | 死时间 | 说明 |
|---|---|---|---|
| Spike harness 写 (15 risk 的 test case + 测量代码) | 4-6h | — | 复用 `spike_translator.py` 框架 + `blueprint_to_master_hint.py` |
| Real cut body 分布采集 (跑 oracle 200 cut 抽样) | 1-2h | 0.5h oracle 跑 | 用现有 oracle, 不写新 |
| Feasible state generator (用 blueprint hint) | 2-3h | — | 复用 `blueprint_to_master_hint.py` |
| Adversarial bad cert generator (4 类 × 12 变体) | 2-3h | — | 抄 GPT pro patches/0001 同 schema |
| Multi-worker test (TC-multiproc) | 1-2h | spawn 30s × 5 重复 | 用 `multiprocessing.spawn` |
| 10-iter LBBD loop sim (TC-lbbd-loop) | 2-3h | 10 iter × ~60s solve = 10 min | 复用 `benders_loop.py` 框架 |
| 跑全 spike + 报告 | 1h | **30-60 min wall** (10K cut × 多 scale × 多 case) | |
| 写 verdict.md | 1-2h | — | |
| **总** | **14-22h Claude** | **45-75 min wall** | |

跟 P1.3A spike 进度对比: P1.3A 计划 ≤3 day (per 09_phase_1_3_plan.md), 这个
prod-scale spike 是 P1.3A 的**入口 gate** (per Finding 5), 总投入 1-1.5
工作日 Claude pace, 在 P1.3A budget 内.

---

## 10. Adversarial Slant 自承

我这版设计**有意 over-emphasize edge case**, 因为 GPT pro Finding 5 + Layer 2
adversarial 教训 (per [[adversarial-soundness-audit]]) 显示 main-path-only
audit 漏 BLOCKER. 但 over-emphasize 的代价:

### 我可能 over-emphasize 的地方
1. **R8/R12 adversarial cert/determinism**: 这俩在 prod 实际撞概率不高
   (validator + replay 已成熟). 但我把它们设成 spike 必测 — 工时多 3-4h.
   correctness-paranoid slant 会认同, throughput / simplicity slant 可能
   觉得 overkill.
2. **R7 var structure 双路**: pose-bool + slot-indexed 都测 doubles 工作
   量. integration slant 可能说 "现在 master 是哪路就测哪路, 切结构是 P1.5+
   事".
3. **B5 24h trial**: 加在 spike 后面让总 wall 多 24h. simplicity slant 会
   说 "spike 就是 spike, 不该带 24h trial".
4. **R11 10-iter LBBD**: 跟 P1.3B 实质重叠. throughput slant 会说"P1.3B 自
   己测, spike 不用做".

### Main path 我可能忽略的
1. **常规 happy path performance**: 大部分 prod iter 是 happy path
   (feasible + 几十 cut + ms 级 solve). 我没设 TC 测 "100 cut feasible solve
   wall < 1s" 这种 main-path baseline 数据点.
2. **简单 metric**: build wall + solve wall + RSS 三件套是 80% 信息. 我
   加 15 个 risk 实际可能 5 个 risk 就够 catch 大部分问题.
3. **Spike→prod 直接路径**: 我没设 "spike GO → P1.3B 第一步 commit 是什么"
   的衔接, 主要在 verify spike 本身.

main 整合时建议: 我这版作 **correctness 上限** (worst case + adversarial
全 cover), correctness-paranoid slant 直接拿. throughput / simplicity
slant 砍掉 R8/R12/B5 这种边缘, 留 R1-R6 + R9-R11 + R14 核心 10 个 risk
作 **可执行 baseline**. integration slant 重点决 R7 var structure 一路还是
两路.

---

## 11. 潜在 blind spot (即便 main 整合 4 路 slant 后仍可能漏)

1. **CP-SAT 内部 API breaking change** (OR-Tools 9.15 → 未来 9.16+): spike
   设计绑死 9.15 API, 升级时 spike 自己要重写. 项目 168h freeze 期不升级
   (per CLAUDE.md `pacman_campaign_freeze.sh`), 长期是 risk.
2. **数据 schema 演化**: candidate_placements / mandatory_exact_instances
   schema 改 (e.g., 加新 pool / 新 facility), spike data fixture 失效. 没
   设 versioning.
3. **跨项目知识 leak**: spike 假设当前 7 family 是终态. F10+ 加新 family
   时 spike 不一定 cover 新 form.
4. **Performance regression detection**: spike 是 one-shot. 没设 CI/baseline
   compare 让后续 commit 触 spike 退化能 catch.
5. **Real-world chaos**: prod 168h 跑可能撞 cosmic ray bit flip / disk
   wearout / kernel scheduler hiccup. spike 短时跑 catch 不到. 用户已知, 不
   是 spike 责任, 但 GO 后跑 168h 前的 readiness gate 该带这层 (per
   `scripts/production_readiness_gate.py`).
6. **Human reviewer fatigue**: spike 出 15 risk × 多 scale × 多 metric 报告
   ≈ 几十表格. 没设 reviewer-friendly TL;DR. 信息过载本身 = bug 漏检 risk.

---

## 12. Summary (TL;DR)

**目标**: 把 mini Step 8 spike 50 BoolVar + INFEASIBLE 早停的弱 verdict
升级成 P1.3A close gate 级 prod-scale spike.

**手段**: 15 类 risk × 15 test case, feasible state 用 IP v2 blueprint hint
强制 solve 不早停, adversarial bad cert inject 测 Finding 1-3 patch 在 10K
rate 下还能 catch.

**GO 标准**: ≥12/15 risk triggered + expected behavior, RSS peak ≤30GB,
build ≤60s, with-cut wall ≤1.5x no-cut wall, bad cert 100% quarantine.

**工时**: 14-22h Claude + 45-75 min wall (single-machine spike), 不含可选
B5 24h trial.

**承认 slant**: 此版 adversarial 偏向, over-emphasize R8/R12/B5; main 整合
其他 slant 砍冗余但保 R1-R6/R9-R11/R14 核心 10 个.
