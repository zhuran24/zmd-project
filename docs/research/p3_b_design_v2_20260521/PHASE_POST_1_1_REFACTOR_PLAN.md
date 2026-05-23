# Phase 1.1 闭环后重构计划

到 commit `afef8f1` (Step N) 为止 Phase 1.1 4 family (F1-F4) validator / oracle /
evaluator / lifecycle / replay / store 全部 sound 闭环, 通过 7 轮 GPT pro audit
+ 22 轮 Gemini cross-check 验证. 这份文件汇总到目前为止确定下来的后续重构,
按 Phase 1.2 → Phase 1.3 → Phase 1.5+ 三段排.

---

## 1. 现状 (commit `afef8f1` 起算)

### 已闭环
- F1 region_capacity / F2 cutset / F3 port_exposure / F4 component_reach
  validator + oracle + evaluator
- Lifecycle 9 step (gen / minimize / serialize / deserialize / validate /
  attach-scope check / evaluate / apply-to-master / replay)
  - Step 2 minimize defer Phase 1.1 P1.11 (F5 deletion + QuickXplain)
  - Step 8 apply-to-master defer Phase 1.3 P1.21 (CP-SAT 真集成)
- CutStore 6-dim watcher (by_cell / by_group / by_pose / by_commodity /
  by_region / by_ghost), quarantine / hold / on_ghost_rect_changed 状态机
- Replay fail-closed (canonical_rules=None → state.canonical_rules fallback
  → HOLD), 不允 silent ATTACH
- CutStore.add_cut 默认 `initial_state="held"` (production 必经 replay /
  validator gate 才 active, test fixture 可 bypass)

### 测试 / 静态 gate 状态
- pytest: 170 cuts test pass (普通模式 + `python -O` 防线 regression)
- ruff: clean (`--config "lint.per-file-ignores={}"` 跑也 clean)
- mypy --strict: 36 errors (typing hygiene, 非 runtime fatal)
- vulture: `evaluate_literal_port_exposure` 仍标 unused (走 generic multiset
  path, P1 decide 删或接进 dispatch)
- bandit: 6 Low B101 assert (lifecycle / store / replay 内部, validator 入口
  已改 explicit guard)
- radon: average A; `validate_port_exposure` D(23), `validate_component_reach`
  D(24) (Step J / Step K 加 binding 后升, P1 拆 helper)

### Audit archive (包内 ship)
- `external_review/gpt_pro_phase1_1_v{1,2,3,4,5}_audit_*.md` (9 个 GPT pro audit)
- `cross_check/gemini_round_{14..35}*.md` (22 个 Gemini cross-check)

---

## 2. 默认 skip 的方向 (历史死路)

后续重构不再 propose 这些:

- **HiGHS / Gurobi 替 OR-Tools**: PoC 实测 42 GB > 30 GB OR-Tools (Phase 3B
  repair5).
- **多机分布式**: 硬件 1 主机 + 1 远程, WAN 延迟 ≥ 100 ms.
- **LP relaxation 替 CP-SAT**: B1 pose-bool master 已 verdict 死, master.solve
  解不动是 inherent.
- **27 lever 死路**: B1 / PCR-CUT / SAC-Hull / D2 / cand C / L01-L26 系列,
  各 paradigm_death_timeline.md cite. 真 paradigm 投资必绕开.

---

## 3. Phase 1.2 P1.11 入门 (低风险 factual 收尾)

进 F5-F9 实施前必清这几项. 全是 schema / spec / static hygiene, 不动 paradigm.

### 3.1 strict registration gate default ON
- 文件: `src/cuts/replay.py:122`
- 改: `EXACT_FAMILY_VALIDATOR_STRICT` default `"0"` → `"1"`
- 影响: 未注册 family 进 replay → `NotImplementedError` 不 silent attach
- F1-F4 已注册, 切换不影响当前. F5-F9 实施时每加 1 个必 register, 测试覆盖

### 3.2 spec docs align (必修 #7)
- `docs/research/p3_b_design_v2_20260521/state_machine_v2.md:42-45`: PoseId
  改 `str` (src `lifecycle.py:42-49` 已是 str)
- `docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md:225-241 / 365-374 /
  740-747`: 删 `symmetry_lift`, 加 `power_grid_reach` / `density_envelope`
  (src 9 family list `lifecycle.py:56-66`)
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/03_port_exposure.md:39-44`:
  direction 改 `N / S / E / W` (src `candidate_placements.py:53-60`)
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/01_region_capacity.md:
  139-145`: region_kind 加 `left_or_bottom_union` (Step G land)
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md:64-77 /
  156-159`: cert schema 加 `contributing_commodities` 集合语义 (不 multiset),
  validator 加 cross-partition 描述 (Step N land)
- `docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md:
  48-77 / 145-150`: commodity_id / commodity_route assumption 改 registry
  require (Step M+N land), separator in-grid + ∈ owner∪ghost 描述

### 3.3 source_digest 真 hash
- 当前 `src/cuts/lifecycle.py:635-637` + `src/cuts/oracles/region_capacity_oracle.py:
  179-186` 写死 `"poc_source_digest"`
- 改: hash `canonical_rules.json + candidate_placements.json + mandatory_exact_instances.json
  + generic_io_requirements.json + oracle_versions` 内容
- spec 已 require: `cut_lifecycle_v2.md:881-903 / 80-86 / 146-154`
- 不修则 replay 不能识别 data source 轮换, 跨 session cert 可信度差

### 3.4 ghost_rect tuple 语义 lock
- 当前 `src/cuts/lifecycle.py:216` 注释 `(x, y, h, w)`, `helpers/ghost_geometry.py:
  108-116` 返回 `(x, y, x+h, y+w)` — h / w 跟常规 (x+w, y+h) 反
- F8 power_grid_reach 实施前必锁:
  - 写明 schema: `(x, y, height, width)` 或改 object `{"x", "y", "height", "width"}`
  - 加非方形 fixture, e.g. `(10, 20, 3, 7)` verify AABB
- 否则 F8 接真 ghost_rect 时横竖反

### 3.5 mypy strict 收尾
- 36 errors / 10 files, 主要泛型缺参 + Any return + unused ignore
- 重点收: `lifecycle.py` (`BState`) + `replay.py` + 4 family validator
- 让 schema 类型契约真在 type system 内 enforce

### 3.6 拆 validator helper (radon D 级降)
- `validate_port_exposure D(23)` 拆: parse_cert / front_cell_math /
  blocking_pose_binding / literal_multiset / port_exists
- `validate_component_reach D(24)` 拆: components_disjoint / membership /
  recompute_bfs / separator / commodity_registry
- `validate_region_capacity C(20)` 顺手拆 cells_per_pose / demand /
  gap_consistency
- `validate_cutset C(18)` 顺手拆 partition / cut_edges / commodity_route /
  witness
- 不只是好看 — Step J/K/L/M/N 反复在最大函数里漏接线 invariant, 拆开后下次
  audit reviewer 更易定位

### 3.7 evaluate_literal_port_exposure 决定
- vulture 标 unused (走 generic `evaluate_literal_multiset`)
- 选项 a: 删 (统一 generic path)
- 选项 b: 接进 `step_7_evaluate_cut` literal dispatch 作 F3 specific evaluator
  并加测试
- 倾向 a (factual simpler, sound 不变)

---

## 4. Phase 1.2 P1.11-P1.15 实施 (5 new family)

入门完后进 5 个 family 实施. 每个 family 单独 commit (≥ 5 commit), 跟 Phase 1.1
同样 cross-check rhythm.

### 4.1 P1.11 F5 pattern_nogood
- 用途: literal-based cut, 拒已知 unsat 状态. 是 deletion-minimize / QuickXplain 入口
- 实施: `src/cuts/families/pattern_nogood.py` (validator + evaluator) +
  `src/cuts/oracles/pattern_nogood_oracle.py` (从 master infeasible witness 提)
- spec: `cut_family_specs/05_pattern_nogood.md`
- lifecycle Step 2 minimize 接 deletion + QuickXplain 在这步 land

### 4.2 P1.12 F6 shape_packing_hall
- 用途: geometric cut, Hall's marriage 定理推 region 内 pose 数下界
- 实施: validator (cert.required_count vs region.available_slots) + oracle
  (greedy bipartite match)
- spec: `cut_family_specs/06_shape_packing_hall.md`

### 4.3 P1.13 F7 power_hitting_set
- 用途: literal-based cut, 必选 power pole set
- 实施: hitting-set greedy minimize + multiset evaluate (复用 F3 path)
- spec: `cut_family_specs/07_power_hitting_set.md`

### 4.4 P1.14 F8 power_grid_reach
- 用途: geometric cut, Liang-Barsky AABB + BFS 电网可达
- 实施: `helpers/ghost_geometry.py` 已有 Liang-Barsky helper, 复用
- 前置: ghost_rect tuple 语义必先 lock (§3.4)
- spec: `cut_family_specs/08_power_grid_reach.md`

### 4.5 P1.15 F9 density_envelope
- 用途: geometric cut, region density 上界 (单位 cell pose count)
- 实施: validator (cert.density vs region.area × max_density) + oracle
- spec: `cut_family_specs/09_density_envelope.md`

### 4.6 P1.15+ test fixture 补全
- F3 direction E / W synthetic fixture (真数据只 N=273 S=257, E=W=0)
- F8 直接复用 E / W fixture
- ghost_rect 非方形 fixture
- F5-F9 各 family 7-10 test (sound case + ≥ 3 attack 反例 + schema_err)

---

## 5. Phase 1.3 P1.21 (CP-SAT propagator 真集成)

F5-F9 落地后, evaluator 才进真 hot path (10K calls/sec). 这阶段 perf opt 必要.

### 5.1 step_8_apply_to_master 实施
- 当前 `src/cuts/lifecycle.py:743-751` NotImplementedError
- 接 `benders_loop` hook (env flag `EXACT_B_DESIGN_V2=1` 切新框架)
- Lazy → hard constraint 转化, 跟 master CP-SAT model 真集成

### 5.2 evaluate hot path perf opt
GPT v3 Gemini r35 已识别, Step H 加 TODO docstring 留好:

- **cache parsed cert_dict on Cut**: 避 hot path `json.loads(cut.geometric_payload)`
  每次 ~2µs, 10K calls 累 20-50ms/sec. 修法: attach 阶段 eager parse 挂内存
  (Cut frozen → side cache 或 store layer cache)
- **F4 evaluate 改 incremental connectivity**: 当前 `_bfs_component`
  O(|Grid|) per call. Phase 1.3 propagator 10K/sec 数量级退化. 修法 union-find
  with rollback / cache last-known component bitset + dirty flag
- **lru_cache(256) on _decode_region_bitset**: Step G land OK, 但 Phase 1.3
  跨 cut 反复调时 cache miss risk. 修法 attach-time eager decode 持 FrozenSet
  于 Cut.scope (替 global LRU)

### 5.3 by_exterior_watcher 实施
- GPT v3 Gemini r35 P0, Step H 暂 defer (sound 不需要, evaluate 重算保)
- Phase 1.3 lazy → hard constraint 后, evaluator 不再被自动调, watcher 必必
- 实施: `CutStore` 加 `by_exterior_watcher: Dict[Cell, Set[CutId]]`, 跟
  exterior_blocks 变化时 trigger affected cut re-replay
- F1 GHOST_AGNOSTIC cut 注册到此 watcher (`store.py:213-215` 当前注释明示
  defer)

### 5.4 propagator thread-safe 评估
- 当前 `lru_cache(256)` multiprocess spawn 各 worker 一份, 不共享
- Phase 1.3 propagator 如果 master CP-SAT 内部多线程 callback, lru_cache 是
  thread-safe (GIL + functools 实施) 但 cache pollution 跨决策回溯仍要 verify
- HR1 thread-safe 是 Phase 1.3 评估项, 不必修但需测试覆盖

---

## 6. Phase 1.5+ (production integration)

Phase 1.3 framework 跑通后接真生产 data + 真 oracle.

### 6.1 commodity registry production inject
- 当前 `BState.commodity_demands` / `commodity_routes` Phase 1.1 mock 注入
- Phase 1.5+ 真 inject 路径: 从 `data/preprocessed/commodity_demands.json` +
  routing planner output + master_solution.commodities 真 build
- 设计 `build_bstate_from_production_inputs()` 统一入口, 覆盖:
  - canonical_rules + facility_templates
  - mandatory_exact_instances + instance_to_facility_type
  - candidate_placements
  - commodity demand / routes (从 production data)
  - source_digest 真 hash

### 6.2 registry schema 评估 (route_id vs commodity_id)
GPT v5 / v6 提出: 当前 `{commodity_id: {"src", "sink", "demand"}}` 只支撑
"一 commodity 一 route". 真生产同 commodity 可能多 src/sink pair:
- e.g. `blue_iron_ore` 多 mining tile → 多 refinery
- e.g. 不同 floor 同 commodity 多 belt route

候选 schema:
```python
commodity_routes: {
    route_id: {
        "commodity_type": str,
        "src": (x, y),
        "sink": (x, y),
        "demand": int,
    }
}
```

cert 改用 `contributing_route_ids` 不是 `contributing_commodities`.

**决策点**: Phase 1.5+ 真生产 commodity registry data 设计时定. 不提前 refactor —
当前 Phase 1.1 / 1.2 / 1.3 不需要多 route 语义, 提前改 schema 风险 over-engineer.

### 6.3 各 family oracle 真实施
当前 F2 / F3 / F4 oracle 是 stub `return []`. Phase 1.5+ 接真 generator:

- **F2 cutset**: 复用 PCR-CUT `patch_routing_core.run()` (Phase 0-1 GO 但 Phase
  5 multi-anchor verdict NOT GO — 仍可作 generator 模板, paradigm 死的部分是
  跨 anchor 收敛, 单 cut 生成本身 OK)
- **F3 port_exposure**: 直接遍历 `state.cell_owner` + `candidate_placements`
  pose ports, 找 front_cell 被占的 case
- **F4 component_reach**: 复用 `src/search/d2_separator.py` BFS components +
  find_separator
- **F5 pattern_nogood**: deletion / QuickXplain 复用 L16 `core_minimizer.py`
- **F6 / F8 / F9**: 各自 spec §5 generator pseudocode

### 6.4 F3 active_port_witness verify
- spec `03_port_exposure.md:144-147` 要求 verify `active_port_witness_b64`
- 当前 validator 没查 (Phase 1.1 v1.0 假设 "all listed ports active")
- Phase 1.5+ 真 production data 时可能有 port 被 boundary_constraints LP
  disable, 必加 witness 验

### 6.5 F2 max_flow_LP algebraic witness
- spec `02_cutset.md:156-159` 要求 verify max-flow LP dual
- 当前 defer Phase 1.5+
- 接真 commodity routes + LP solver 后实施

---

## 7. Defer high-risk (Phase 1.3+ 评估)

GPT pro v5 verdict 排序 (最先爆 → 后):

1. **source_digest placeholder** — Phase 1.2 §3.3 必修
2. **strict default 0** — Phase 1.2 §3.1 必修
3. **F2 commodity_demand registry** — Step M+N 已 partial close (require +
   cross-partition + dedup), Phase 1.5+ schema refactor 评估
4. **HR5 GHOST_AGNOSTIC exterior_blocks invalidate watcher** — Phase 1.3 §5.3
5. **HR1 thread-safe** — Phase 1.3 §5.4 评估
6. **HR3 free-placement / HR4 non-rect ghost** — Phase 1.5+ 真 production data
   pattern 出现时再决策

---

## 8. 实施 rhythm (Phase 1.1 经验)

每 commit 后立刻 Gemini cross-check (per [[feedback_gemini_review_algorithm_math]]).
大节点 (Phase 1.2 入门收尾 / Phase 1.2 5 family 全 land / Phase 1.3 集成
land) 打包给 GPT pro batch audit (per [[feedback_big_milestone_gpt_pro_review]]).

每轮 audit:
- prompt 跟 zip 单独给 (per [[review-pkg-no-prompt-inside]])
- 包内只放事实素材, 不放 verdict claim / Close 列表 (per [[review-pkg-no-prompt-inside]] §"不放主动性内容")
- response 收到立刻 cp 进 `docs/research/.../external_review/`
  (per [[external-review-reproducibility]])
- finding 必先 reproduce verify 才 archive
  (per [[audit-verify-before-archive]])

---

## 9. 排期估算 (Claude pace, 不按人类工程师)

per [[work_time_estimates]] Claude 节奏估:

- Phase 1.2 §3 入门 7 项 — 单步 30-60 min Claude, 累计 ~5-7 commit, ~3-4 小时
- Phase 1.2 §4 5 family 实施 — 每 family ~1-2 commit + Gemini cross-check,
  累计 ~10-15 commit, ~6-10 小时 Claude work
- Phase 1.3 §5 propagator 集成 + perf opt — paradigm work, ~10-20 小时 Claude
  + master CP-SAT 真集成 wall-clock 死时间 (build / 测时间不可压)
- Phase 1.5+ §6 production integration — 跟真生产 data schema 设计耦合, 估
  随 Phase 1.5 data pipeline 进度

实际 wall-clock 主要消耗在 168h campaign 长跑 (cut framework 修改不直接影响
campaign 时间), 不在 Claude implementation 时间.

---

## 10. Open questions (待定)

1. Phase 1.5+ commodity registry schema (commodity_id vs route_id 级别) 何时
   决策? — Phase 1.5 真生产 data pipeline 设计时
2. F2 patch_routing_core 复用是否真 sound (paradigm 死在 multi-anchor 收敛,
   单 cut 生成仍 OK)? — Phase 1.5+ F2 oracle 实施时复 verify
3. evaluate_literal_port_exposure 删 vs 接进 dispatch — Phase 1.2 §3.7 一行决定
4. ghost_rect tuple 改 object schema vs 保留 tuple + 明确文档 — Phase 1.2 §3.4
   F8 实施前

## 11. 跟 PROJECT_LOCK.md §3A invariants 边界

后续重构不能跨这些边界 (per `PROJECT_LOCK.md` §3A):
- family ↔ mode XOR (literal vs geometric) 不可改
- cut.scope + cert + literals XOR geometric_payload 必填
- GHOST_AGNOSTIC sentinel 不能跟普通 ghost_id 混用
- 9 family list frozen (无 symmetry_lift, 含 F1-F9)
- ASSUMPTION_VERIFIERS dispatch 必经 verifiers module, 不准 inline

任何 §3A 边界改动必先 PROJECT_LOCK 更新 + 跨 spec / src / test 同步.
