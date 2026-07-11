# Prod-Scale Spike — Correctness-Paranoid Design

**作者 slant**: correctness-paranoid (N 路并行子代理之一, per
[[design-phase-n-parallel-agents]])
**Date**: 2026-05-25
**Trigger**: GPT pro Phase 1.2 audit Finding 5
(`docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md:257-313`)
**Verdict 写入责任**: main merger, 不在此 doc

---

## 0. 立场声明 (slant 自白)

我是 correctness-paranoid 视角. 我的偏向:

1. **优先 sound 反射 P1.3A 真集成路径**, 哪怕 spike 跑得比 mini Step 8 慢
   100×. 如果 spike 用了 shortcut → 它跑通 ≠ P1.3A 跑通, 等于把 risk 折叠到
   下一阶段时炸.
2. **拒绝 INFEASIBLE 早停掩盖 solve cost**. mini Step 8 已经踩过 (synthetic
   random cuts 在 1K 就 INFEASIBLE, solve 2ms 没意义). 必须 feasible
   realistic case.
3. **真 data / 真 validator / 真 lifecycle**. 不接受 mock cert / synthetic
   pose registry / skip validator. mock 的代价不是 spike 阶段省时间, 是把
   "P1.3A 出 bug" 推到生产 168h campaign 才发现.
4. **不优化 perf**. 我不替 throughput slant 抢工作. 我只测 "跑得通而且
   sound", 不测 "跑得快". perf budget (例如 build wall 30s) 我会用,
   但作为 NOT GO 触发器, 不作为优化目标.

下面 §8 "blind spot" 我承认 perf / hardware-specific tuning / latency
profiling 不在我的 scope, 留给 throughput slant agent.

---

## 1. Spike scope (要测什么 — sound 反射 P1.3A 真集成)

### 1.1 必含的 prod-scale 数据

| 项目 | mini Step 8 (toy) | 本 spike 要的 | 来源 |
|---|---|---|---|
| Master 变量数 | 50 BoolVar (10 group × 5 pose) | **81,795 BoolVar** (真 pose registry) 或 slot-indexed 形式相应 | `data/preprocessed/candidate_placements.json` (verify 53MB, 7 facility pool, 81795 pose) |
| Mandatory instance | 10 synthetic group | **266 真 instance** | `data/preprocessed/mandatory_exact_instances.json` (verify 88KB, 266 entry) |
| Group demand | 1 (toy `GROUP_DEMAND=1`) | 真 demand (multiplicity per instance, slot semantic per `04_design_invariants §2.3.6`) | `mandatory_exact_instances.json` instance ↔ facility_type mapping |
| Source digest | 不算 (无 BState) | 真 sha256 over `canonical_rules + candidate_placements + mandatory + facility_templates + generic_io_requirements` | `compute_source_digest()` at `src/cuts/lifecycle.py:438-455` |
| Ghost rect | 不存在 | 选 ≥ 3 个真 candidate ghost: 大 (40×40), 中 (20×20), 小 (8×8) | outer search candidate frontier (`src/search/outer_search.py`) |

### 1.2 必含的 cut family 真 shape distribution

不再用 `synth_cuts()` random literal toy. 必须按真 cert body size 分布生成:

| Family | 真 cert body 主要 field | 量级估计 | 必须来自 |
|---|---|---|---|
| F1 region_capacity | `region_kind` + `cap_R` + `demand_R` + region bitmap (region 内 cells) | region 4-50 cells, 单 cut 几百 byte | `src/cuts/families/region_capacity.py` 现有 generator + `src/cuts/oracles/...` 真 emit |
| F2 cutset | partition (A, B) bitmap + min-cut witness (Dinic) + `cut_capacity` + `commodity_demand` | partition 可达 70×70 / 2 cells, 单 cut 几千 byte | `src/cuts/families/cutset.py` + `src/cuts/oracles/cutset_oracle.py` |
| F3 port_exposure | (group_a, pose_a) + (group_b, pose_b) + direction + active_port_witness | 几十 byte | `src/cuts/families/port_exposure.py` |
| F4 component_reach | BFS component bitmap + commodity_id + src/sink | 几千 byte | `src/cuts/families/component_reach.py` |
| F5 pattern_nogood | literal multiset (3-15 literal typical) + minimizer trace (`stopped_reason`/`calls`/`size_before`/`size_after`) | ~ 100-500 byte | `src/cuts/families/pattern_nogood.py` |
| F6 shape_packing_hall | region_pose_set bitmap + `region_capacity` + Hall witness | 几千 byte | `src/cuts/families/shape_packing_hall.py` |
| F7 power_hitting_set | facility_cells (post-fix per GPT pro Finding 1) + CoverSet bitmap + needed pole anchor list | 几百 byte | `src/cuts/families/power_hitting_set.py` (after patch `0001-bind-power-family-pose-cells-and-digest.py`) |
| F8 power_grid_reach | facility_cells (post-fix) + ghost_rect + disconnect witness + protocol_core_cell | 几百 byte | `src/cuts/families/power_grid_reach.py` (after patch) |
| F9 density_envelope | window W + `max_allowed_area` + `area_capacity_overflow` (per [[f9-area-only-not-density]]) | 几百 byte | `src/cuts/families/density_envelope.py` |

每 family 至少 5 个真 cert (oracle 真 emit 或 fixture 真生成), 总 ≥ 45.
然后**复制** + 改 cut_id / scope.ghost_rect_id 到目标规模.

### 1.3 必含的 lifecycle phase

spike 必须跑完整 9 step 中的 **step 3-8** (oracle generate 用 fixture
代替, 因 oracle 真跑可能秒杀 spike 时间):

| Step | 必须 | 不能 shortcut 的原因 |
|---|---|---|
| 3 serialize | ✅ | 测 proto bytesize + 真 JSON 长度. mini Step 8 没测. |
| 4 deserialize | ✅ | 反向 round-trip. cut_id / cert_hash byte-equal 必 verify. |
| 5 validate (family dispatch) | ✅ | 真 validator (含 F7/F8 facility_cells exact match post-patch). FAMILY_VALIDATORS 全 dispatch. spike 通过 = sound 没 regression. |
| 6 attach-scope check | ✅ | source_digest + ghost + blocked + artifact + oracle + assumption 6 sub-check. 真 BState 真 digest. GPT pro Finding 3 已 land patch, spike 验 patch effective. |
| 7 evaluate | ✅ | family dispatch, 真 BState 真 ghost. literal/geometric 两 path 都打到. |
| 8 apply-to-master | ✅✅ | **本 spike 核心**. CP-SAT translator 每 family 调一次, build 真 model, solve. |

可 shortcut (Phase 1.3B work):
- Step 1 generate (oracle 真跑) — fixture 替代足够, 因 oracle 跑慢
  不影响 master integration 测.
- Step 2 minimize (F5 deletion / QuickXplain) — fixture 提供 pre-minimized
  cert 即可.
- Step 9 regression — 单独 test, 不在本 spike 主 budget.

### 1.4 必含的 cut store + watcher 行为

- `CutStore.add_cut(...)` 真调 (per `src/cuts/store.py:114+`). 不绕过.
- ghost_watcher / exterior_watcher 真注册. cut 入对应 watcher.
- 当 ghost_rect 变化 (spike 跑 3 个 ghost), 真 trigger watcher 重新
  evaluate.
- store rotation / capacity eviction 也要触发: 在 spike 内插一段
  "active cut > 10K 时 evict 最早的 N 个" 的 path, verify cut_id 不会
  re-use, 且 evicted cut 不影响 master.

---

## 2. Spike NOT-scope (框死 over-engineer 风险)

明确不测以下, 避免 spike 变成 P1.3B 全部工作:

1. **不优化 active cut filter / cut scoring**. 全 cut hard apply.
   per-iter cut subset 选择策略是 P1.3B work.
2. **不实施 incremental rebuild**. 每 master 周期 fresh rebuild
   (per `09_phase_1_3_plan.md` P1.3A option 1 — solve-rebuild path).
   incremental hot path 是 P1.3B perf opt.
3. **不接 real outer search**. spike 跑固定 candidate 列表 (3 个
   pre-selected ghost), 不跑 frontier 迭代. outer search ↔ master 集成是
   P1.3B 的 `benders_loop` hook.
4. **不测 168h endurance**. spike ≤ 2 hour wall clock 上限. 168h
   ramp 是 Phase 1.5+ work.
5. **不优化 F4/F8 hot path**. (per `09_phase_1_3_plan.md §12.2`).
   spike 用现版本 evaluate, 即使 BFS 每次 O(|Grid|). 慢就慢, 测它慢多少.
6. **不测 binding / routing subproblem 真集成**. spike 只到 master.
   binding/routing 在 LBBD 外循环里, spike 不绕回去.
7. **不测 master objective**. 用 feasibility check (`solver.Solve` 无
   objective) — 因为加 objective 后 solve cost 不可预测, 会污染 build
   cost measurement.
8. **不替换 OR-Tools 9.15**. CP-SAT 不支持 `AddLazyConstraint` 已经是
   workflow 约束 ([[cp-sat-no-add-lazy-constraint]]), spike 不试 lazy
   path.
9. **不测 multiprocess.spawn worker 间共享**. 单 process spike, 测算
   master integration 本身. multiprocess 集成在 Phase 1.3B (`HR1
   thread-safe` 评估 per §12.4).

---

## 3. 量化 GO criteria (sound 反射 P1.3A 真集成)

spike 跑完后, 同时满足以下才 GO:

### 3.1 Build cost (model construction + cut apply)

- **fresh build with 0 active cut**: ≤ 10s wall
  (81,795 BoolVar + 266 demand constraint + slot-index decomposition)
- **fresh build + 1,000 cuts** (各 family 按真 distribution): ≤ 20s wall
- **fresh build + 10,000 cuts**: ≤ 60s wall
  (per `mini Step 8 spike` extrapolation 5-6s, 但 mini Step 8 是 50 var,
  本 spike 81,795 var 约 1600×, 预算放宽到 60s)
- **fresh build + 50,000 cuts**: ≤ 300s wall (5 min)
  上界, 超过即 master cycle 不可用

### 3.2 Solve cost (feasibility check, no objective)

- **0 cut feasibility check**: ≤ 30s wall (verify CP-SAT presolve 不爆)
- **1,000 cut feasibility check**: ≤ 60s wall
- **10,000 cut feasibility check**: ≤ 180s wall (3 min)
- 关键: **必须有 FEASIBLE solve**, 不能 1K cuts 就全 INFEASIBLE.
  如果 INFEASIBLE 早停 → 测量 solve cost = 0 没意义.
  → mitigation: spike 用 oracle 真 emit cut, sound 不与 BState 冲突, 应
  保 feasible (除非 spike fixture 设计错, 需 debug 而非接受)

### 3.3 RSS (psutil resident_set_size)

- **0 cut master**: ≤ 1 GiB
- **10,000 cut master**: ≤ 4 GiB
- **50,000 cut master**: ≤ 12 GiB
  上界对应单 worker headroom (per `[[real-culprit-power-coverage]]` —
  workers=1 plateau 12.78 GB ⇒ 168h 实测可承受)

### 3.4 Proto bytesize (model.Proto().ByteSize())

- **0 cut**: ≤ 50 MiB
- **10,000 cut**: ≤ 500 MiB
- **50,000 cut**: ≤ 2 GiB
  上界对应 CP-SAT 内部 proto 反序列化 cost. 超过 2 GiB → CP-SAT
  internal copy 翻倍 RSS, 撞 §3.3 cap.

### 3.5 Lifecycle correctness (sound 必 hold)

- **189 现有 cut framework test 全 pass** (per `12_go_criteria §8.1`)
- **F7/F8 facility_cells exact match patch 已 land + regression test
  pass** (per `0001-bind-power-family-pose-cells-and-digest.py`)
- **oracle scope_digest 用 `compute_source_digest(state)` 不再用
  `state.source_digest`** (GPT pro Finding 3 fix). spike 内 step 6
  不应有任何 QUARANTINE 因 digest mismatch.
- **每 family 的 step 5 validator round-trip pass** (生成 cut →
  serialize → deserialize → validate → 仍 sound)
- **每 family 的 step 7 evaluate 跟 step 5 一致** (cert sound + state
  unchanged → evaluate True)
- **step 8 apply 后 master cycle 仍 sound**: 即 master 不会因 cut apply
  错变 INFEASIBLE 而原 state 实际 feasible (反例必无)

### 3.6 真集成 path 全闭环

- spike 单跑 fixture, 但 fixture 必须是 oracle 真调一次 emit 的, 不允许
  hand-craft.
- spike 跑通 ≥ 3 个 candidate ghost (大/中/小), 每个 ghost 都触发完整
  9 step (step 1-2 用 oracle real emit; step 3-8 必跑; step 9 = step 5
  re-entry on new state).
- 跨 ghost watcher invalidation: ghost_rect 切换时, 关联 cut 自动
  re-evaluate. spike verify count(re-evaluated cuts) > 0 且
  count(QUARANTINE) = expected.

---

## 4. 量化 NOT GO criteria (abort + 设计反思)

触发任一即 abort, 不交付 spike, 回 design 阶段:

1. **任何 step 5/7 mismatch**: 真 oracle emit 的 cut 在 same state
   被 step 5 validate sound 但 step 7 evaluate False → soundness
   regression, **stop ship**.
2. **任何 false-positive cut 出现**: cut apply 后 master INFEASIBLE,
   但 spike 反向 verify (e.g. brute force or witness check) state 实际
   feasible → **stop ship**, F7/F8 patch 没真 fix 或漏其它 family.
3. **build wall > 5 min on 10K cuts**: 单 master 周期不可用, 即使
   P1.3B 加 incremental rebuild 也救不动 (10× headroom 不够).
4. **solve wall > 10 min on 10K cuts**: master.solve 不收敛, 跟
   [[real-culprit-power-coverage]] 历史经验一致 (master 解不动是
   project 长期主瓶颈, spike GO 应该 strictly better, 不是 strictly
   worse).
5. **RSS > 20 GiB on 50K cuts**: 触 OOM, 单 worker 不能跑.
6. **proto bytesize > 4 GiB on 50K cuts**: CP-SAT internal copy 翻倍
   即 8 GiB, 必触 OOM.
7. **任何 INFEASIBLE 解释不通**: 即 cut framework 报 INFEASIBLE 但
   spike 反向 witness verify state feasible → 跟 #2 同根, 但单独标
   出 (这是 [[dark-matter-telemetry]] 应该 catch 的事).
8. **测试 regression**: cuts test 不再 189 全 pass (无论是 spike
   wrapper 漏 setup 还是 spike 改 src 引入 regression — 任一都
   abort).
9. **mypy strict regression**: spike 引入新 src 必须仍 mypy strict
   pass (per `12_go_criteria §8.1` row 5).
10. **ghost watcher 漏 invalidation**: spike 切 ghost 后, 应 re-evaluate
    的 cut 没 re-evaluate → store/watcher 集成 bug, 比 master integration
    更基础, **stop ship**.

---

## 5. Source of truth verify list (不允许 mock)

每项必从这些 file 真读, mock 即 abort:

```
data/preprocessed/candidate_placements.json    (53 MB, 81795 pose, 7 pool — verified by ls + python json.load)
data/preprocessed/mandatory_exact_instances.json (88 KB, 266 entry — verified)
data/preprocessed/generic_io_requirements.json (561 byte — verified)
rules/canonical_rules.json                     (9045 byte — verified)
```

spike 启动序列 (必走):

1. Read `candidate_placements.json` → 真 pose registry → 建 master
   variable space.
2. Read `mandatory_exact_instances.json` → 266 instance → group demand
   constraint.
3. Read `canonical_rules.json` → facility_templates → placement rule /
   port rule.
4. Read `generic_io_requirements.json` → commodity demands.
5. Build `BState` 真 fill: `groups` / `cell_owner` / `ghost_rect` /
   `canonical_rules` / `instance_to_facility_type` / `facility_templates`
   / `candidate_placements` / `commodity_demands` / `commodity_routes`
   (per `lifecycle.py:352-392` field list).
6. `state.source_digest` 留空 (None) — 让 `compute_source_digest(state)`
   真算 sha256 (per GPT pro Finding 3 修复路径).

oracle / generator 的 fixture cert 必须来自 oracle 真调一次, 不允许
hand-craft. fixture 生成 script 在 spike 内独立 commit, 跑前先调用一次
oracle, 把 cert 缓存为 fixture, 后续 replay (类似 mini Step 8 的
synth_cuts 改成 oracle_emit_real). 缓存这层不是 mock — 因为 cert 是真
oracle 输出, 只是不每次都 re-emit (节省 spike wall clock).

---

## 6. Sound 反射 P1.3A 真集成路径 (spike 跑通后还 open 的 risk)

spike GO 后, P1.3A 真实施会经历:

### 6.1 spike **已 prove safe** 的 risk:

- ✅ CP-SAT API 形状 (Add / AddLinearConstraint / 无 AddLazyConstraint)
  在真 master scale 跑通 (mini Step 8 只 prove 50 BoolVar, 本 spike
  prove 81,795)
- ✅ 9 family lifecycle step 3-8 真 closure (mini Step 8 跳过 step
  3/4/5/6/7, 本 spike 走完)
- ✅ source_digest GPT pro Finding 3 patch 生效 (mini Step 8 不测
  Step 6)
- ✅ F7/F8 facility_cells GPT pro Finding 1/2 patch 生效 (mini Step
  8 用 synthetic, 不触 validator real path)
- ✅ build wall / solve wall / RSS / proto bytesize 在真 scale 的
  量级 (mini Step 8 只 50 BoolVar 外推, 本 spike 真测)
- ✅ ghost watcher 切换 invalidation (mini Step 8 单 ghost 也没
  ghost)
- ✅ cut store rotation / capacity eviction 在 10K-50K active cut
  range 行为

### 6.2 spike 跑通后**还 open**的 risk (必交付 P1.3B):

- ❌ **incremental rebuild path**: spike 用 fresh rebuild, P1.3B 可能
  需要 OR-Tools solver hint / warm start 减 build cost.
- ❌ **active cut filter / scoring**: spike 全 apply, P1.3B 需选 subset
  + per-iter prune 已 stale 的 cut.
- ❌ **F4 BFS incremental connectivity** (per `§12.2`).
- ❌ **F8 power_network all-pairs hot spot** (per GPT pro Finding 4):
  spike 量级会暴露这个 perf bug 但不修.
- ❌ **真 outer search ↔ master loop**: spike 跑固定 3 candidate, 真
  benders 跑 frontier 迭代, candidate 数 / cut emit 数完全不同.
- ❌ **binding / routing subproblem 集成**: spike 不绕回去, P1.3B 必走.
- ❌ **multiprocess.spawn worker 间 lru_cache 跨 worker 行为**
  (per `§12.4 HR1 thread-safe`).
- ❌ **168h endurance**: spike ≤ 2h, 168h ramp 是 Phase 1.5+.
- ❌ **master objective**: spike 用 feasibility, 真 master 要
  max_lex(area, min_side) (per CLAUDE.md / PROJECT_LOCK Exactness
  Constitution).

### 6.3 spike 跑通**不能保证**的事:

- ⚠️ 真 168h campaign 收敛 ≥ 30% (per `§8.4 Phase 1.5+ GO`).
- ⚠️ 真 binding/routing 进 LBBD 后 cut framework 仍 effective (history
  17 lever 失败教训, e.g. [[b1-phase6-path2-dead]] cut weak).
- ⚠️ master objective on 真 instance 不撞 [[lever24-augmented-master-dead]]
  的 master.solve scale 死墙.

第 6.3 段是 paradigm-level risk, 不在 P1.3A 责任范围 — spike 顶多 prove
"integration 路径不卡死", 不 prove "整个项目能收敛". 写在这里是为了 main
merger 看到时不会误把 spike GO 当 paradigm 解禁.

---

## 7. 工时估 (Claude pace, per [[work-time-estimates]])

按 Claude pace (不按人类工程师 buffer). 死时间分开标.

| 段 | Claude 工时 | Wall-clock 死时间 | 备注 |
|---|---|---|---|
| §5 fixture build script (oracle real emit + cache) | 2-4 h | 0 | 9 family × 5 cert ≈ 45 cert, oracle 真调 缓存 |
| §1.3 lifecycle step 3-8 wrapper (spike harness) | 1-2 h | 0 | 现有 step_3 ~ step_7 已实施, 只需 spike-side glue |
| §1.4 store + watcher integration | 1-2 h | 0 | CutStore.add_cut 已实施 |
| Step 8 apply-to-master 实施 (F1-F9 各 translator) | 4-8 h | 0 | mini Step 8 已写 5 translator, 本 spike 补缺 + 真 BoolVar lookup |
| Build / solve / RSS / proto bytesize 测量 + telemetry | 2-3 h | 0 | psutil + model.Proto().ByteSize() + time.monotonic |
| §3 scale ramp (0/1K/10K/50K) 跑 + 收数据 | 1-2 h Claude | **2-4 h wall** (50K cuts solve 单跑可能 5 min) | wall 主因是 solve cost, agent 等待 |
| §4 NOT GO 任一触发 abort + 反思写 doc | 1 h | 0 | 不一定触发 |
| 收尾 verdict.md + 数据表 | 1 h | 0 | |
| **合计** | **12-22 h Claude** | **2-4 h wall** | |

**注**: 12-22h Claude 工时 ≠ 12-22h 日历时间. 串行跑约 1-2 day 日历
(per `[[work-time-estimates]]` discount). 大头死时间是 50K cuts solve
wall, 不可压缩.

跟 mini Step 8 对比: mini Step 8 是 ~2 h Claude / 0 wall (50 BoolVar
toy). 本 spike 10× 工作量, 但反射 100× 真 path, ROI 高.

---

## 8. 我的 correctness-paranoid slant 偏向 (main merger 看这段)

### 8.1 我有可能 over-cautious 的地方

- **§1.1 demanding 81,795 BoolVar**: 项目历史
  [[lever24-augmented-master-dead]] 已经 prove master.solve scale 是
  死墙. 我坚持真 scale 是因为 mini Step 8 的 50 BoolVar 外推 1600× 不
  trustworthy — 但 throughput slant 可能会 argue 用 30,000 BoolVar
  subset 也 informative + 跑得快 5×. 我反对 subset 因为 sound 反射要求
  真 scale.
- **§1.3 demanding 走完 step 3-8 全 dispatch**: 我坚持因为
  mini Step 8 只走 step 8 translator, GPT pro Finding 3 (source_digest
  oracle bug) 正是因为 lifecycle 中 step 没真跑过才漏掉. 但
  simplicity slant 可能 argue step 3/4 是 round-trip, 没必要每 cut 都
  跑, 抽样即可.
- **§3.5 demanding 189 test 全 pass during spike**: 我坚持因为 spike
  即使是 PoC 也不允许 break 现有 sound boundary. 但 simplicity slant
  可能 argue spike branch 单跑 spike harness 即可, regression test 留
  CI.
- **§4 abort 触发 10 个**: 我列得多, 因为 correctness-paranoid 视角
  任何 sound 漏洞都要 abort. 但 adversarial-schema slant 可能 argue
  几个 abort 触发器有冗余 (#1/#2/#7 都是 sound 错).

### 8.2 我没 over 的地方 (硬要求)

- §1.1 真 data file (4 文件 + verified path) 不能 mock.
- §3.5 sound criteria 全 hold.
- §4 #1 #2 #7 #10 任一 → abort. 这 4 个是真 sound 触发, 不是 perf.
- §6.2 列出 spike 跑通 ≠ P1.3A 跑通的 9 个 open risk, 必须写进
  spike verdict.md, 不能让 main merger 误读 spike GO 为 P1.3A GO.

### 8.3 哪些 design decision 我倾向 over-cautious (main merger 可以 trade)

- **§3.2 solve cost cap (10K cuts 180s)**: 我设宽是 correctness 优先,
  不卡 perf. throughput slant 可能要求 ≤ 60s.
- **§3.3 RSS cap (50K cuts 12 GiB)**: 我对齐 [[real-culprit-power-coverage]]
  workers=1 plateau, 给 168h campaign headroom. throughput slant 可
  能要求 ≤ 8 GiB (留 multi-worker space).
- **§7 工时 12-22h Claude**: 我估宽是 sound 优先 (oracle 真调慢 +
  fixture cache 设计 + 4 scale ramp 各跑一次). simplicity slant 可
  能压到 8h (单 ghost + 跳 50K scale).

---

## 9. 潜在 blind spot (我承认 correctness 视角看不到的)

### 9.1 Perf 量级判断

我用 §3.1 / §3.2 / §3.3 的 number 都是 conservative cap, 不是 expected
target. 真实 build wall 可能比 60s 高也可能低, 我没 throughput slant
那种 ROI 量化经验. 建议 throughput slant 单独 review §3 number, 提
expected number, 让 GO criteria 跟实际 number 之间留 ≥ 2× headroom.

### 9.2 OR-Tools internal behavior

- CP-SAT presolve 在 81,795 BoolVar 行为我没实测. mini Step 8 用 50
  BoolVar, presolve 几乎 instant. 真 scale presolve 可能 ≥ build wall
  10-30%, 但具体不可预测.
- `model.Proto().ByteSize()` 在 50K cuts 时序列化时间本身可能 ≥ 1s,
  这个 cost 我没单列 (列在 build wall 内).
- OR-Tools 9.15 在 81K BoolVar + ≥ 10K constraint 是否有 known bug
  我没 check. 建议 simplicity / integration slant 查 OR-Tools 9.15
  release notes.

### 9.3 Hardware-specific 行为

- i9-13900KS + jemalloc + isolcpus 已 land (per CLAUDE.md
  P1 #24 wrapper), spike 必须用 wrapper 跑.
- thermal throttle 在 spike 长跑 (50K cuts solve 5+ min) 可能 trigger,
  我没列 thermal monitoring 步骤. 建议 verify slant 加 `temp_logger.sh`
  并行跑.

### 9.4 不在 spike 但相邻的事

- benders_loop 真 hook ↔ master integration 接口 — 我假定 spike harness
  独立, 不动 `src/search/benders_loop.py`. 但 P1.3B 真 hook 时, spike
  harness ↔ benders_loop interface 可能不匹配, 这层接口 design 不在我
  scope.
- master 加 objective (`max_lex(area, min_side)`) 后行为完全不同 —
  spike 测 feasibility, 真集成测 optimal. throughput slant + adversarial
  slant 应该思考 objective 加上后 solve cost 跳几个量级.

### 9.5 跟 paradigm death timeline 的关系

[[paradigm-death-timeline-27-lever]] 已 28 lever (含 PCR-CUT Phase 5
🟡). cut framework 是 paradigm 之外的 cross-cutting infra, spike GO
**不能解禁** 任何 lever. 我反复在 §6.3 强调过, 这里再标一次.

---

## 10. 交付物清单 (spike GO 时 main merger 看的)

spike 跑完 deliver:

1. `verdict.md`: GO / NOT_GO 判定 (按 §3 / §4 criteria) + 每项 number
   实测值. 不允许 hand-wave.
2. `spike_harness.py`: spike 启动 entry. 必 deterministic (fixed seed,
   fixed ghost candidate list).
3. `fixtures/`: oracle real-emit cert cache (≥ 45 cert, 9 family × 5).
4. `telemetry/`: build_wall.csv, solve_wall.csv, rss_psutil.csv,
   proto_bytesize.csv (per scale).
5. `repro/`: 1 行命令复现 (e.g. `bash scripts/run_prod_scale_spike.sh`).
6. `open_risk.md`: 复制 §6.2 + §6.3, 给 main merger / next stage
   implementer 看. 防 spike GO 误读为 P1.3A GO.

---

## Cite list (本 doc 引用 file path, grep-verified)

- `data/preprocessed/candidate_placements.json` (53MB, 81795 pose)
- `data/preprocessed/mandatory_exact_instances.json` (88KB, 266 entry)
- `data/preprocessed/generic_io_requirements.json` (561 byte)
- `rules/canonical_rules.json` (9045 byte)
- `src/cuts/lifecycle.py:352-392` (BState fields)
- `src/cuts/lifecycle.py:438-455` (compute_source_digest)
- `src/cuts/lifecycle.py:1005-1010` (step_8_apply_to_master NotImplementedError)
- `src/cuts/store.py:68+` (CutStore class)
- `src/cuts/families/` (9 family src)
- `src/cuts/oracles/` (9 oracle src)
- `docs/research/p1_2b_mini_step_8_spike_20260525/spike_translator.py` (mini Step 8 spike)
- `docs/research/p1_2b_mini_step_8_spike_20260525/verdict.md` (mini Step 8 verdict)
- `docs/research/phase1_2_gpt_pro_audit_20260525/AUDIT_REPORT.md:257-313` (Finding 5)
- `docs/项目说明/09_phase_1_3_plan.md:1-73` (P1.3A spike plan)
- `docs/项目说明/12_go_criteria.md:105-122` (Phase 1.3 GO)
- `docs/项目说明/04_design_invariants.md:1-80` (9 family / 9 step rationale)
