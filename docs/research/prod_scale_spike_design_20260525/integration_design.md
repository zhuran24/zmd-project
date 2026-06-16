# Prod-scale spike design — integration slant

**Date**: 2026-05-26
**Slant**: integration (N=5 之一, per [[design-phase-n-parallel-agents]])
**Trigger**: GPT pro Phase 1.2 audit Finding 5
(`docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md:257-313`) +
mini Step 8 spike caveat — toy 50 BoolVar master + synthetic cuts +
INFEASIBLE 早停 不足以 close P1.3A integration risk.
**Sibling slants**: correctness_paranoid / throughput / adversarial /
simplicity 已 land 同目录, 主 agent merger 时阅. 本 doc 保持 integration
slant 独立判断, 不 anchor sibling.

---

## 0. 立场声明

我的偏向: **spike 必须真接现有 src 的端到端 path, 不允许 wrap mock**. 写
独立 spike 脚本走 toy master + 私造 store 看起来"独立可验", 但每跳过
一个真模块, 都是把 integration risk 推到 P1.3B/1.5+ 实际生产时炸. 反例
mini Step 8 已经付出代价: 它跳过 `step_3 ~ step_7 + CutStore + replay
+ ghost watcher + 真 BState`, 结果 GPT pro Finding 1/2/3 都是 lifecycle
真路径没跑过才漏的 bug.

简单说: spike 不是"小型 master + synthetic"; spike 是**真 wire 现有所
有 src 模块, 用真 data, 跑端到端, 只在 scale (instance 数 / cut 数 /
iter 数) 上做受控收缩**. 受控收缩允许 (spike ≠ 168h campaign), 但模块
跳跃不允许.

§11 自承我可能 over-emphasize 端到端 path, perf / correctness 细节让位
给 throughput / correctness_paranoid sibling.

---

## 1. End-to-end path (spike 必跑通的 lifecycle step)

P1.3A spike 必须**完整跑 9 step lifecycle** (per `04_design_invariants
§3` + `cut_lifecycle_v2.md v3.2.2 §4-§9`). 每 step 调真 src 函数,
不允许 mock / shortcut. 表内"真 invoke"列指向具体 file:func.

| Step | 真 invoke | 不能 mock 的原因 |
|---|---|---|
| 1 generate | `src/cuts/oracles/*.py::generate_*` 真调 (per family, 7 oracle) | oracle emit timing 跟 BState 强耦合, mock cert 跳过 oracle 就遇不到 source_digest stale (GPT pro Finding 3) 这类 真 path bug |
| 2 minimize | `src/cuts/families/pattern_nogood.py::minimize_*` (F5 deletion / QuickXplain) 真调 | minimize 改 cert literal_count → cert_hash 变, 不跑会让 step 4 round-trip / step 5 validate 走假 cert |
| 3 serialize | `src/cuts/lifecycle.py::step_3_serialize(cut)` | proto bytesize / 真 JSON 长度 spike 必量, mock 序列化没 ground truth |
| 4 deserialize | `src/cuts/lifecycle.py::step_4_deserialize(blob)` | round-trip cut_id / cert_hash byte-equal verify, mock 跳过会让 v4 replay bug 类型 ([[proof-object-lifecycle]]) 重演 |
| 5 validate | `src/cuts/replay.py::FAMILY_VALIDATORS[family]` dispatch 真调 | 9 family validator 全 wired (已 land per `replay.py:62-72`), spike 必每 family ≥ 5 cert 真跑 一次 dispatch → 验 post-patch F7/F8 facility_cells exact match + source_digest patch effective |
| 6 attach-scope check | `src/cuts/lifecycle.py::step_6_attach_scope_check(cut, state)` | source_digest / ghost_id / blocked_cells_hash / exterior_blocks_hash / artifact_hashes / oracle_version / assumptions 6 sub-check 全 dispatch, 跳过 = GPT pro Finding 3 重演 |
| 7 evaluate | `src/cuts/lifecycle.py::step_7_evaluate_cut(cut, state)` | family dispatch (literal_multiset vs geometric), 真 BState 真 ghost. spike 必每 cut 调一次 verify step 5↔7 一致 |
| 8 apply-to-master | **本 spike 主 deliverable**: 实施 `src/cuts/lifecycle.py:1005::step_8_apply_to_master` (currently NotImplementedError), per family translator | mini Step 8 实施过 5 distinct CP-SAT 形 cover 6 family 但绑 toy master. 本 spike 必绑真 master_model.AddXxx → CP-SAT, 不绕 |
| 9 regression / replay | `src/cuts/replay.py::regression_sweep(store, state)` 真调 | 跨 ghost / 跨 iter state 变后 cut store re-validate, 跳过 = ghost watcher invalidation 没真跑 |

**spike 入口 wrapper** (要求): 单 `spike_e2e.py` 入口 driver, 串接
oracle → store.add_cut → step3 → step4 → step5 (replay dispatch) →
step6 → step7 → step8 (新 translator) → ghost transition → step9. 不
允许在任一 step 注 fake input bypass 上 step 输出.

---

## 2. Real master integration (用哪个 master, 哪个 benders, 哪个 outer)

### 2.1 Master 选 PoseBoolExactMaster (B1)

**决策**: spike 必接 `src/models/master_model.py` 现有 PoseBoolExactMaster
delegate (B1 paradigm, `EXACT_USE_POSE_BOOL_MASTER=1` env-gated landed —
per [[b1-phase2-production-land]]), 不是从头写 toy.

理由:
- P1.3A 的 `EXACT_B_DESIGN_V2=1` env flag (per `09_phase_1_3_plan §12.1`)
  会切到 cut framework 注入路径, 这个路径接 PoseBoolExactMaster 现在
  跑得通. spike 不接它 = 没 prove "切 env flag 后 step_8 真能 attach".
- 历史 [[lever24-augmented-master-dead]] 已 verdict augmented master
  scale 死, B1 是当前唯一活路径. spike 用其它 master shape 等于测
  paradigm-dead 路径.

### 2.2 Benders loop: 抽接口, 不全跑

**决策**: spike **不**真跑 `src/search/benders_loop.py::LBBDController`
全栈 (6067 行, binding/routing/flow 4 sub 都接). spike 只跑 master.solve
+ cut framework, sub-problem 用 stub.

理由 + 防御:
- 全栈 binding/routing/flow 跑通是 P1.3B 责任, 不是 spike. spike 卡在
  sub-problem perf 上, master integration risk 反而验不到.
- 但 spike **必须** import `LBBDController` 真初始化一次, verify
  constructor signature 跟 cut framework 注入点兼容 (e.g. spike
  pseudo-loop 模拟 `_run_certified_exact()` 的 cut emit → master.solve →
  evaluate 循环 ≥ 5 iter, 不真调 binding/routing).
- Sub-problem stub 必须 deterministic: 给 fixed precompute "front_blocked"
  / "binding_infeasible" 结果, 让 spike 在 iter 间真触发不同 cut family
  emit. stub 输出靠固定 fixture, 不靠 random.

### 2.3 Outer search: 3 candidate snapshot

**决策**: spike **不**真跑 `src/search/outer_search.py` frontier 全扫,
但**必须**用真 `outer_search` 模块的 candidate emit 接口取 3 个 candidate
snapshot (大 / 中 / 小 ghost). 不是手写 3 个 ghost rect.

理由:
- candidate 选择逻辑跟 ghost_rect_id 编码 / area lower bound 算法强耦合
  (per `outer_search.py:18` LB 计算). 手写 ghost rect 会让 `ghost_rect_id`
  跟 outer 真发的 id 编码不同, spike 跑通后 P1.3B 真接时 watcher key
  全对不上, 假阳性 GO.
- spike: 启动时调一次 outer_search 列前 3 个 candidate, 后续主循环锁定
  这 3 个 candidate 反复跑 (≥ 5 iter × 3 candidate = 15 master.solve).

### 2.4 何时算"真集成反映 P1.3A"

P1.3A plan §1 列 3 sub-route. 本 spike 用 sub-route 1 (solve-rebuild,
推荐路径). 但**模块接口**必须保证后续切 sub-route 3 (hard-constraint
rebuild) 不需重写 spike harness — 即 `step_8_apply_to_master` 必须接受
"rebuild" flag 控制是 incremental Add 还是 fresh build. sub-route 2
(C++ propagator hook) 不在 spike scope (≥ 1 周 Python binding 工作, 超
spike budget).

---

## 3. Cut store integration (6-dim watcher + 状态机)

### 3.1 必跑的 store 行为

| 行为 | 真 invoke (src) | spike 必触 |
|---|---|---|
| add_cut (held 默认, per GPT pro v5 fix) | `store.add_cut(cut, cell_keys=..., group_keys=..., pose_keys=..., commodity_keys=..., region_keys=..., initial_state="held")` | ≥ 1 次 per cut |
| 6-dim watcher 注册 | by_cell / by_group / by_pose / by_commodity / by_region / by_ghost (auto from cut.scope) | 9 family 各 ≥ 1 cut, 覆盖 6 watcher 全部 dimension |
| 7th watcher (by_exterior) | **defer 到 P1.3B §12.3** (per plan), spike 不实施 — 但 spike 必须 emit telemetry warn "F1 GHOST_AGNOSTIC cut 现走 evaluate 重算, watcher gap 存在" | F1 ≥ 1 cut |
| quarantine_cut (post-validate unsound / scope_mismatch / artifact_changed) | `store.quarantine_cut(cut_id, QuarantineReason(...))` | spike 必至少 1 case (inject 1 个 forged-cert cut, 经 step 5 fail → store quarantine 验通) |
| hold_cut (scope mismatch on candidate transition / canonical_rules=None) | `store.hold_cut(cut_id)` | spike 必 ghost 切换时 trigger old_ghost 的 cut 入 hold |
| reactivate_cut (replay 返 ATTACH) | `store.reactivate_cut(cut_id)` | spike 必 ghost 切回后 cut 从 hold 回 active |
| on_ghost_rect_changed | `store.on_ghost_rect_changed(old_id, new_id, state)` (内部走 replay_cut full path per `store.py:267-296`) | spike ≥ 3 ghost transitions (大→中, 中→小, 小→大) |
| capacity-based eviction | **当前 src `store.py` 未实施** eviction policy (P1.5+ scope). spike 不要求实施, 但**必须**: (a) emit `store.stats()` 跨 iter trend, (b) verify `len(store.cuts)` monotone 增长 (无 evict), (c) telemetry warn "no eviction policy, P1.5+ 必加" | 跨 5 iter 必 emit |
| regression_sweep (cross-state replay) | `replay.py::regression_sweep(store, state, canonical_rules=...)` | spike 必每次 ghost transition 后调一次 verify |

### 3.2 spike 必 verify 的 invariant

- **`store.is_active(cut_id) == False` 直到 step 5 ATTACH** (per GPT pro
  v5 P0-2 fix: held 默认). spike 必 add_cut 后立刻 assert is_active=False.
- **quarantine 不可恢复**: 一旦 cut 入 quarantined, 后续任何 ghost
  transition / regression_sweep 不重活. spike 必 inject 1 quarantine
  case 后跑 5 iter verify cut 不出现在 active.
- **watcher key 完整**: 9 family 各 ≥ 1 cut 时, `store.stats()` 报的
  6 watcher dim 都 ≥ 1 key. 缺 dim = family 注册 漏 watcher key
  (oracle bug), spike abort.

---

## 4. 3 sub-route PoC (P1.3A plan §1, spike 怎么覆盖 N=1, 2, 3)

P1.3A plan 列 3 sub-route, integration slant 视角逐个判:

### 4.1 sub-route 1: solve-rebuild (推荐, spike 主路径)

每轮 master.solve 前把 active cut 转 `model.Add` 注入 fresh model. spike
**必跑此路径**, 因为是 plan §1 推荐 + 跟现 `benders_loop._run_certified_exact`
默认一致.

Spike 覆盖方式:
- `step_8_apply_to_master(cut, master)`: 调 master 内 `model.Add(...)`
  / `AddBoolOr(...)` / `AddLinearConstraint(...)` (per family translator,
  cover 9 family — mini Step 8 已 prove 5 distinct shape, spike 落地全
  9 个).
- 主 loop: rebuild master fresh 每 iter, `for cut in store.active_cuts():
  step_8_apply_to_master(cut, master)`, 然后 master.solve.
- 量: build wall / solve wall / RSS, 但**整合 cost not perf** (perf sibling
  覆盖).

### 4.2 sub-route 2: C++ propagator hook (defer, 不 spike)

per plan 投资 ≥ 1 周 Python binding 工作. spike 不在 scope, 但 spike
**必须**: 在 `step_8_apply_to_master` 加 TODO docstring 描述 sub-route 2
如何替换 — 留 hook 不让未来重写.

### 4.3 sub-route 3: hard-constraint rebuild (备用, spike 验接口兼容)

cut 全 hard. spike 不专跑此 sub-route (跟 sub-route 1 主要差异是
constraint 强度不是接口), 但**必须** verify `step_8_apply_to_master` 接
受 `mode="hard"` 参数, 用 1 个 spike-side 1-iter trial 跑通验通.

### 4.4 risk per sub-route

- sub-route 1 risk: master.solve 跟 cut count 关系不线性 (mini Step 8 估
  5-6s 可能错). 本 spike 必量 3-5 iter trend (不只 1 shot), 看 cut 累
  积后 build/solve cost 是否 super-linear.
- sub-route 3 risk: hard constraint 在 LBBD 不收敛 → spike 1-iter trial
  不足够, 但 spike 责任只验"接口可切", 不验收敛 (P1.3B 责任).
- sub-route 2 risk: 不在 spike, 由 P1.3B 决定要否投资.

---

## 5. Active filter trigger (哪 step 触发, spike 怎么 verify)

### 5.1 active filter 当前 src 现状

`src/cuts/store.py` 的 `is_active(cut_id)` 已实施 (line 203-208), 但
**真正的 active subset 选择 (cut scoring / capacity eviction)** 当前
**未实施** — `09_phase_1_3_plan §12.1` 列在 P1.3B scope.

spike integration slant 决策: spike **不**实施 active filter, 但**必须**
verify trigger 点 exist, P1.3B 实施时只需在这些点加 logic:

| Trigger 点 | spike 必 emit telemetry | P1.3B 实施时插入 |
|---|---|---|
| 每 master.solve 前 (cut → model 注入前) | `len(store.active_cuts)`, family 分布 (F1..F9 各几个) | active filter 选 subset, drop 低 score |
| ghost transition (`on_ghost_rect_changed` 后) | `held` / `quarantined` counts diff | filter 重 rank held cut, 选 top-K active |
| iter 末 (master.solve 完, 收 subproblem stub 结果) | cut "活跃度" (本 iter 多少 cut 被 master propagator 真触) — spike 用 stub | filter 更新 score, age decay |

### 5.2 spike trigger 次数

3 candidate × 5 iter = 15 master.solve. 每 solve 前 trigger 一次 filter
hook (telemetry only spike, P1.3B 加 logic). 总 ≥ 15 次 filter trigger
event emit.

### 5.3 spike verify filter 干净

filter 在 spike 是 no-op (全 active), 但**必须** verify:
- 每 trigger event emit 的 cut_id 集合, 与下一 master.solve 真 attach
  的 cut_id 集合 byte-equal (== set equality). 不 equal = 有 cut leak /
  drop, 比 filter logic 本身更基础的 bug.
- telemetry 跨 15 event 累积 cut 不变 (spike 不动 cut store), 即每次
  event log 的 cut_id set 都是 superset of 前次.

---

## 6. Step 6 attach scope check (真 hash 计算, 不 mock)

### 6.1 6 sub-check 真跑表

`step_6_attach_scope_check(cut, state)` 内含 6 sub (per `lifecycle.py`
源码 + GPT pro Finding 3 patch 后):

| Sub | spike 必 verify | 不能 mock 的 reason |
|---|---|---|
| source_digest | `cut.scope.source_digest == compute_source_digest(state)` 真比 | GPT pro Finding 3 patch (oracle 全用 `compute_source_digest(state)` 不再用 `state.source_digest`). spike 必每 oracle emit 一次 cut verify cert.scope.source_digest 跟当前 state digest match |
| ghost_rect_id (dispatch ghost-bound vs GHOST_AGNOSTIC) | spike 跑 GHOST_AGNOSTIC (F1) + ghost-bound (F2-F9) 各 ≥ 1 cut | 走两路 dispatch 才能 cover step 6 真分支 |
| blocked_cells_hash (ghost-bound cut, ghost_rect_id match 时) | spike 必跑 1 case: ghost match 但 blocked_cells 变 → HOLD/QUARANTINE | spike 直接构造 state 改 cell_owner (i.e. 新 facility 占新 cell), verify hash 真变 |
| exterior_blocks_hash (GHOST_AGNOSTIC cut) | spike 必跑 1 case: F1 GHOST_AGNOSTIC cut, exterior 变 → 触 hash 比 | F1 cut 不入 by_ghost_watcher (per store §7 footnote), 必须靠 hash 真比 catch invalidation |
| artifact_hashes | spike 必模拟 1 case artifact rotate (改 1 个 hash 比 cert scope mismatch) | 验 step 6 真 fail-closed reject |
| oracle_version / assumptions | spike 必 emit 真 oracle_version 写入 cut.scope (从 oracle src 真读, 不 mock) | 验 oracle version 跨 iter 一致, P1.5+ 改 oracle 后 spike 自动报 rotate |

### 6.2 真 hash 计算 (spike fixture 必跑真函数)

- `compute_source_digest(state)`: sha256 over canonical_rules +
  candidate_placements + mandatory + facility_templates +
  generic_io_requirements (per `lifecycle.py:438-455`). spike 必从真 4 个
  data file 加载, 不 hand-craft state.
- `compute_blocked_cells_hash(state)`: 对 state.cell_owner 排序后 sha256.
  spike 每 iter master.solve 后**真更新** state.cell_owner (模拟新
  facility placement), 让 hash 真变.
- `compute_exterior_blocks_hash(state)`: spike 模拟 ghost 变 → exterior
  变, hash 真变.

### 6.3 Replay path verify

spike 必跑 `replay.py::replay_cut` 至少 N=10 次 (覆盖 ATTACH / HOLD /
QUARANTINE 三 outcome 各 ≥ 3 次), 每次 verify:
- ATTACH: store.is_active(cut_id) == True
- HOLD: cut_id in store.held
- QUARANTINE: cut_id in store.quarantined + reason_code 正确

---

## 7. Spike 跑通后 P1.3A 还 open 的 integration risk

### 7.1 spike 能 cover

- ✅ 9 step lifecycle 真闭环 (step 3-8 全 dispatch, step 9 regression
  跨 ghost transition 真 sweep)
- ✅ PoseBoolExactMaster 真接 (env flag `EXACT_USE_POSE_BOOL_MASTER=1`
  + `EXACT_B_DESIGN_V2=1` toggle 链路 verify)
- ✅ 6-dim watcher 全 dimension 注册 (9 family 覆盖)
- ✅ store 状态机 (held / active / quarantined) 跨 ghost transition 正确
- ✅ step 6 attach scope 6 sub-check 全 dispatch (含 GPT pro Finding 3
  patch effective verify)
- ✅ 3 candidate × 5 iter pseudo-LBBD 跑通 (15 master.solve)
- ✅ sub-route 1 (solve-rebuild) 接口 + sub-route 3 (hard-constraint) 接
  口兼容
- ✅ filter trigger 点 emit telemetry, hook 留给 P1.3B

### 7.2 spike 不能 cover (留 P1.3B / 1.5+)

- ❌ **真 binding / routing / flow subproblem 集成**: spike 用 stub.
  真接后 LBBD 收敛行为完全不同 ([[b1-phase6-path2-dead]] 教训 — sub-
  problem 跟 cut 框架 wired 后 cut weak 不收敛).
- ❌ **active filter logic (cut scoring / capacity eviction)**: spike 留
  hook, P1.3B 实施.
- ❌ **by_exterior_watcher**: defer 到 P1.3B §12.3.
- ❌ **multi-thread propagator safety + lru_cache 跨 worker**: HR1
  per §12.4. spike 单 process.
- ❌ **F4 BFS incremental connectivity / F8 power_network all-pairs hot
  spot**: per §12.2 + GPT pro Finding 4. spike 不优化 perf, throughput
  sibling 负责.
- ❌ **真 outer_search frontier 迭代**: spike 锁 3 candidate, 真 outer 跑
  几千 candidate, cut emit 数完全不同.
- ❌ **真 168h endurance** + RSS / cut store 漂移: spike ≤ 2h wall.
- ❌ **真 master objective `max_lex(area, min_side)`**: spike 用 feasibility
  check 简化. 真 master 加 objective 后 solve cost 量级不同 (
  [[lever24-augmented-master-dead]] 教训).
- ❌ **真 multiprocess.spawn `-p 4` worker 间 cut store 共享**: spike 单
  process.

### 7.3 spike 跑通**不能**保证

- ⚠️ 真 168h campaign 收敛 ≥ 30%
- ⚠️ binding/routing 接 LBBD 后 cut framework 仍 effective
- ⚠️ master.solve 不撞 paradigm-level 死墙 (24+ lever 死法)

第 7.3 是 paradigm-level risk, 不在 spike scope — spike GO 仅 prove
"P1.3A integration 路径无技术阻塞", 不 prove "项目能收敛". main merger
看到此 spike GO 时不可误读为 paradigm-level GO.

---

## 8. 量化 GO criteria

spike 跑完同时满足才 GO:

| # | Criteria | 量 |
|---|---|---|
| G1 | 端到端 path 跑通 | 9 step 全 invoke, 0 NotImplementedError raise, 0 fail-closed assert violation |
| G2 | 9 family validator dispatch 全过 | 9 family × ≥ 5 cert = ≥ 45 cert 真 step 5 validate, 全 sound (oracle real-emit cert 应 sound; 若有 unsound = oracle bug, 非 spike fail 但 spike abort 报 bug) |
| G3 | 6-dim watcher 全 dimension 注册 | `store.stats()` 6 个 watcher_keys 都 ≥ 1 |
| G4 | 状态机跨 ghost transition 正确 | 3 ghost transitions 后, held / active / quarantined count diff 跟 trace expected diff 一致 (spike 跑前预算 expected, 比 actual) |
| G5 | step 6 6 sub-check 全 dispatch | telemetry log 必含每 sub 至少 1 个 ATTACH + 1 个 HOLD/QUARANTINE 决策 case |
| G6 | replay verdict 一致 (regression sweep) | 同 cut 在 same state replay 2 次, AttachDecision byte-equal |
| G7 | quarantine inject case effective | 1 个 forged-cert cut (cert.scope.source_digest 篡改) 必经 replay_cut 返 QUARANTINE, store.is_active=False, audit reason_code="scope_verify_failed" 或 "post_attach_validation_unsound" |
| G8 | sub-route 1 跑通 + sub-route 3 接口兼容 | 5 iter × 3 candidate solve-rebuild 全 OPTIMAL / FEASIBLE, sub-route 3 1-iter trial 跑通 |
| G9 | filter trigger emit ≥ 15 event + cut_id set 一致 | telemetry log per-iter cut_id set with byte-equal verify |
| G10 | F7/F8/source_digest Finding 1-3 patch 在 spike scale 下 still hold | spike inject 1 case per Finding (3 case 共 cover) 必 QUARANTINE, 0 漏 |

GO 全过 → spike GO → P1.3A 进 P1.3B 实施.

---

## 9. 量化 NOT GO criteria (任一触发 abort + 设计反思)

| # | NOT GO trigger | 含义 |
|---|---|---|
| N1 | 任一 step (3-8) 调真 src 函数 raise unexpected exception | src 路径有 latent bug, spike catch — 反 GO 但价值高 (即 P1.3A 真做时也会撞, 早撞早修) |
| N2 | 6-dim watcher 任一 dim count == 0 | 某 family oracle 漏注册 watcher key, store routing 死 |
| N3 | replay verdict 跨 2 次跑不一致 (G6 fail) | non-deterministic, [[proof-object-lifecycle]] 重演 |
| N4 | quarantine inject case 漏 catch (G7/G10 fail) | GPT pro Finding 1/2/3 patch 在 prod scale 失效, sound 漏洞 |
| N5 | step 5↔7 一致性破 (oracle emit cut 经 validate sound 但 evaluate False) | family validator/evaluator 实施有 bug, sound 漏洞 |
| N6 | sub-route 1 solve-rebuild 在 5 iter 内任一 master.solve UNKNOWN / timeout | master.solve 跟 cut count 关系 super-linear, mini Step 8 估值错, P1.3A 必先 fix master perf 才能接 |
| N7 | sub-route 3 hard-constraint 接口不兼容 (step_8_apply_to_master 不能切 mode) | spike 接口设计错, P1.3B 切 sub-route 需重写 spike harness |
| N8 | store eviction-free 跑 5 iter 后 cut count > 5000 (oracle 暴 emit) | spike 锁的 3 candidate × 5 iter 不应该 emit 这么多 cut, 说明 spike harness 写错, abort |
| N9 | ghost transition 后 active cut count 大幅波动 (e.g. > 50% cut hold/reactivate) | watcher key 编码错 (e.g. ghost_rect_id 算法不一致) |
| N10 | telemetry 输出不可解读 (e.g. JSON malformed, missing field) | spike 自身 instrument 有 bug, 主 merger 没法判 GO/NOT GO |

任一 trigger → abort + 写 abort_reason.md 解释 root cause + 反 design.
spike 阶段 abort 价值远高于 P1.3A 阶段 abort (晚 1 week 撞同样 bug).

---

## 10. 工时估 (Claude pace, per [[work-time-estimates]])

按 Claude pace 估, 死时间分开标.

| 段 | Claude 工时 | Wall-clock 死时间 | 备注 |
|---|---|---|---|
| §5 Fixture build: 9 oracle real emit 45 cert (per §1 表) cache | 2-3 h | 5-15 min oracle real call | per family ≥ 5 cert |
| §1.3 spike_e2e.py harness (9 step glue, 不动 src 主 step 函数) | 2-3 h | 0 | wrapper logic, 不 reimplement |
| §3 store wiring (真 add_cut / replay_cut / on_ghost_rect_changed) | 1-2 h | 0 | 全 reuse 现 store/replay src |
| **§8 step_8_apply_to_master 实施** (9 family translator, 真 attach 到 PoseBoolExactMaster) | 4-6 h | 0 | spike 主 deliverable; mini Step 8 已 prove 5 distinct shape, spike 落地全 9 + 真 master 接 |
| §2 master / benders / outer wiring (3 candidate snapshot, sub stub, pseudo-loop) | 2-3 h | 0 | reuse outer_search candidate emit + LBBDController constructor verify |
| §6 step 6 sub-check verify trace (6 sub case 各 1) | 1-2 h | 0 | inject fake state mutation per sub |
| §5-§7 Quarantine inject case (3 Finding 各 1 + 1 forged-cert) | 1 h | 0 | 复用 GPT pro patch 0001 fixture |
| §3/§5/§9 telemetry instrument (G3/G5/G9 emit log) | 2 h | 0 | JSON lines emit |
| spike 跑 (3 candidate × 5 iter = 15 master.solve, 真 PoseBoolExactMaster) | 1 h Claude | **1-3 h wall** (B1 master 单 solve 50s avg, 15 × 50s = 12.5 min, 加 RSS sampling + telemetry overhead) | wall 主因是 master.solve |
| Abort 触发场景 (N1-N10 任一) → reflect + 修 spike harness 重跑 | 0-3 h Claude (条件) | 0-3 h wall | 不一定触发 |
| 收尾 verdict.md (GO/NOT GO + per criteria 实测值 + open risk 复制 §7) | 1-2 h | 0 | |
| **合计** | **17-26 h Claude** | **2-6 h wall** | |

跟 P1.3A plan budget (≤ 3 day, 即 Claude pace ≈ 1-3 working day, per
[[work-time-estimates]]) 对照, 17-26 h Claude ≈ 2-3 working session.
落在 budget 内.

跟 sibling 对照: correctness_paranoid 12-22 h / throughput 13 h /
adversarial 14-22 h / simplicity 2-3 day (~10-16 h). 本 doc (integration)
最高, 因为坚持真接 src 模块代价大. main merger trade 时若砍, 砍 §10 工
时 trade 给 simplicity 路径, 但 §1 端到端 path 不能砍.

---

## 11. 我 integration slant 偏向 — 自承

### 11.1 可能 over-emphasize 的地方

1. **§1 demand 真 step 1 oracle emit (45 cert)**: oracle 真跑慢 (5-15 min
   wall), simplicity sibling 可 argue mock cert fixture 也能验 step 3-8.
   我反对因为 oracle real path 是 GPT pro Finding 3 的真 trigger 点
   (source_digest), 跳过等于 spike 跑通但 P1.3A 重演 Finding 3.
2. **§2.1 demand 真 PoseBoolExactMaster (B1 master, ~80K BoolVar scale)**:
   throughput sibling 可 argue 用 sub-scale master (50 inst) 也能验 perf.
   我接受 sub-scale 是 perf 取舍, 但**接口必须真 B1 master 接** (env
   flag toggle), 否则 spike GO 不反映 P1.3A 真切 env 后行为.
3. **§2.3 demand outer_search candidate snapshot**: simplicity sibling
   会 argue 手写 3 个 ghost rect 够. 我反对因为 ghost_rect_id 编码差异
   会让 spike watcher key 跟生产对不上, 假阳性 GO.
4. **§9 N1-N10 abort triggers**: 10 个 NOT GO 触发我列得多, 因为
   integration slant 把任何 src wire 不通都当 hard fail. adversarial
   sibling 可能合并 N5/N7/N9 为一类 "interface mismatch".

### 11.2 我没 over (硬要求)

- §1 9 step 全真 invoke, 不允许任一 step mock.
- §3 store 6-dim watcher + 状态机真跑.
- §6 step 6 6 sub-check 真 dispatch (含 GPT pro Finding 3 patch verify).
- §7.2 spike 不能 cover 9 个 risk 必写进 verdict.md 给 main merger
  看, 防 spike GO 误读为 P1.3A GO.

### 11.3 trade 余地

- §10 工时压不动 (oracle real emit + 9 family translator + 3 candidate
  loop 都是硬工作). 但 spike scale ramp 可砍 — 不跑 1K/10K/50K 全 ramp,
  只跑 1 个固定 scale (e.g. 200 cut total × 5 iter), 让 throughput
  sibling 专门负责 ramp.
- §8 GO criteria G10 (Finding 1-3 patch 在 scale 下 hold) 可砍, 因为已
  unit-test 在 Finding 1-3 patch 时 land. 但我倾向保留, 因为 spike scale
  catch 跟 unit test scale 不同的 hash collision / rate-dependent bug.

---

## 12. 潜在 blind spot (integration 视角看不到的)

### 12.1 Perf 量级判断

我 §10 估 master.solve 50s avg / iter 是基于 [[b1-phase4-routing-convergence]]
经验, 不是 spike 实测. 真 spike 跑可能 30s 也可能 120s, 影响 wall budget.
throughput sibling 该量真值.

### 12.2 Concurrent / multi-worker 行为

spike 单 process, P1.3B 真接 `multiprocess.spawn -p 4` 后 cut store 跨
worker 行为完全不验. integration slant 没列 multi-worker 是因为 spike
budget 不允许, 但 P1.3B 第一周必碰到. main merger 应让 adversarial /
throughput sibling 写 multi-worker mini-spike 补.

### 12.3 OR-Tools 9.15 API surface

CP-SAT 不支持 `AddLazyConstraint` ([[cp-sat-no-add-lazy-constraint]]) 已
确认. 但 9.15 在 81K BoolVar + 10K Add 是否有 known limit (`SetMaximumNumberOfHints`
/ `SetSolutionLimit` / internal solver memory limit) 我没 check. spike
跑通才发现 OR-Tools 内部 cap 比预期低是 NOT GO risk.

### 12.4 数据 schema 漂移

spike fixture cache 45 cert 锁在 spike 启动时. P1.3B 真做时若
canonical_rules.json 或 candidate_placements.json 改 schema (新 facility
/ 新 pose / 新 commodity), spike fixture 失效. integration slant 没列
fixture versioning, simplicity sibling 该补.

### 12.5 PROJECT_LOCK / Exactness Constitution 边界

spike GO 不解禁 PROJECT_LOCK 边界 (e.g. 不能因 spike 跑通就 weak 任一
soundness gate). 这点跟 correctness_paranoid sibling §6 一致, 但 integration
slant 容易因为 "spike 跑通 = 集成可行" 错把 paradigm-level 边界放开.

### 12.6 心跳 / 长跑 spike 中断恢复

spike 跑 1-3 h wall, 中途 Claude session 中断 / 心跳 fail / api error
应能 resume. spike 必 emit per-iter checkpoint (state + store state +
telemetry), 不是 monolithic 一次跑. integration slant 没强调, simplicity
sibling 该补 minimal checkpoint design.

---

## 交付物清单 (spike GO 时 main merger 看的)

1. `verdict.md`: GO / NOT GO + §8/§9 criteria 实测值 (no hand-wave)
2. `spike_e2e.py`: 入口 (deterministic, fixed seed, 3 candidate snapshot)
3. `fixtures/oracle_real_emit_cert/`: 9 family × 5 cert cache (oracle
   real-emit, 缓存避免每跑都真调 oracle)
4. `telemetry/`: per-iter store.stats() / watcher dim count / filter
   trigger event / step 6 sub-check trace, JSON lines
5. `open_risk.md`: 复制 §7.2 + §7.3, 给 main merger / P1.3B implementer
6. `step_8_apply_to_master_translator.py`: 9 family CP-SAT translator 实
   施 (本 spike 主 deliverable, P1.3B 直接用)

---

## Cite list (grep-verified file path)

- `/home/zhuran24/claude-pj/zmd/src/cuts/lifecycle.py:1005-1010` (step_8 NotImplementedError)
- `/home/zhuran24/claude-pj/zmd/src/cuts/lifecycle.py:438-455` (compute_source_digest)
- `/home/zhuran24/claude-pj/zmd/src/cuts/store.py:67-330` (CutStore + 6-dim watcher)
- `/home/zhuran24/claude-pj/zmd/src/cuts/replay.py:62-179` (FAMILY_VALIDATORS + replay_cut)
- `/home/zhuran24/claude-pj/zmd/src/cuts/oracles/` (9 oracle src)
- `/home/zhuran24/claude-pj/zmd/src/cuts/families/` (9 family validator/evaluator)
- `/home/zhuran24/claude-pj/zmd/src/models/master_model.py` (PoseBoolExactMaster delegate)
- `/home/zhuran24/claude-pj/zmd/src/search/benders_loop.py` (LBBDController, 6067 line)
- `/home/zhuran24/claude-pj/zmd/src/search/outer_search.py` (frontier candidate emit)
- `/home/zhuran24/claude-pj/zmd/docs/项目说明/09_phase_1_3_plan.md` (P1.3A 3 sub-route)
- `/home/zhuran24/claude-pj/zmd/docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md:257-313` (Finding 5)
- `/home/zhuran24/claude-pj/zmd/docs/research/p1_2b_mini_step_8_spike_20260525/` (mini Step 8 spike — what this spike upgrades)
- `/home/zhuran24/claude-pj/zmd/data/preprocessed/candidate_placements.json` (真 pose registry)
- `/home/zhuran24/claude-pj/zmd/data/preprocessed/mandatory_exact_instances.json` (266 instance)
