# GPT pro Phase 1.1 v5 audit round 1 — verdict NOT GO

GPT pro v5 包 (`phase1_1_gpt_pro_review_v5.zip` commit `273fbff`) audit. 对应
Step M 修 (replay fail-closed + F2/F4 commodity registry require) 后闭环.

## Verdict

**NOT GO, Step M 修不到位.**

replay canonical_rules=None fail-closed 修对. F2 commodity registry 数学证明
还不 sound: 只证 "ID 在 registry, demand 加起来等 cert", 没证 commodity/route
真跨 cut partition, 也没防 duplicate commodity. 2 反例都能 ATTACH.

## P0-1: 同 side route 不跨 partition, F2 validator ok, replay ATTACH

### 反例数据

```text
side_a = {(0,0)}, side_b = {(0,1)}, cut_size=1
state.commodity_demands = {"c_same_side": 2}
state.commodity_routes = {"c_same_side": {"src": (0,0), "sink": (0,0)}}
cert.contributing_commodities = ["c_same_side"]
cert.commodity_demand = 2
```

src+sink 都在 side_a, 不需跨 A/B cut. 真 cross-partition demand=0, cert demand=2
是假 witness.

### 动态结果

```text
validator kind: ok
replay decision: ATTACH
active after replay: True
route does not cross A/B: {'src': (0, 0), 'sink': (0, 0)}
```

### Code 原因

`cutset.py:202-215`: state.commodity_demands 存在 check (Step M).
`cutset.py:225-227`: `sum(state.commodity_demands.get(c, 0) for c in contributing)`.
`cutset.py:228-237`: 只比 registry sum == cert demand.
`cutset.py:238-245`: 只查 commodity 在 registry.
`cutset.py:246-252`: 只 `registry_demand > cut_size`.

缺: F2 没使用 state.commodity_routes, 没验 contributing commodity route 是否
`(src in A and sink in B) or (src in B and sink in A)`.

spec `02_cutset.md:23-30 / 110-122` cross-partition 语义. Step M F2 修法只挡
"随便填不存在 commodity id", 没挡 "真实 id 但不跨 partition".

## P0-2: 同 commodity 重复两次, demand 翻倍

### 反例
```text
state.commodity_demands = {"c1": 1}
cert.contributing_commodities = ["c1", "c1"]
cert.commodity_demand = 2
cut_size = 1
```

唯一 commodity demand=1, cut_size=1 没违反, 但 cert ["c1","c1"] list sum → 2,
变假 violation.

### 动态结果
```text
validator kind: ok
unique registry demand should be: 1
cert cut_size: 1
active after replay: True
held: False quarantined: False
```

### Code 原因
`cutset.py:225-227` 直接 `sum(...)` 没去重. spec §2 是集合语义不 multiset.

## P0-3: CutStore.add_cut 仍直接 active

Step M 修 replay 但没修 store. `store.py:113-147` add_cut 直接 `self.cuts[cut_id]=cut`,
active 判断 (`store.py:171-176`) 只看 not quarantined and not held → add 完
立刻 active.

反例:
```text
bad cut active immediately after add_cut: True
bad cut replay decision: QUARANTINE
bad cut active after replay: False quarantined: True
```

silent attach window: 任何 consumer 在 add_cut→replay 之间读 active 都吃未验证 cut.

### 建议
拆 API: `add_pending_cut()` / `validate_and_attach_cut()`, 或 add_cut 默认 held.

## 实跑 gates

| Gate | 结果 |
|---|---|
| pytest cuts | 167 passed |
| pytest -O cuts | 167 passed 1 warning |
| F1 真数据 smoke | F1 cuts emitted: 0 (boundary_io 14/54 outside) |
| ruff src/cuts/ src/tests/cuts/ | All checks passed (Step M F401 force-fix OK) |
| mypy --strict | 36 errors (not 35, doc estimate 偏低) |
| vulture | evaluate_literal_port_exposure unused (走 generic multiset) |
| bandit -r src/cuts/ | 6 Low B101 assert |
| radon cc src/cuts/ -s -a | avg A; validate_component_reach D(24), validate_port_exposure D(23) |

## A. 数学层逐项

### F1: Step L 修 OK (重复部分 v3 archive)
- strict P(g)⊆R, duplicate gid 防, tuple demand, demand_R/gap consistency 全闭环
- evaluate 重算 cap (Step F), step_7 dispatch (Step I)
- production smoke F1=0 cut (boundary_io 14/54 fail-closed) 合理保守

### F2: NOT sound (P0-1 + P0-2)
好: partition disjoint / patch subset / enclosure / cut_size / cut_edges canonical.
Step M 加 state.commodity_demands require.
缺: route cross-partition + duplicate 防.

`commodity_demands: {id: int}` 当前只支撑 demand 数, 没 route 信息. 建议 schema
改 `route_id → {commodity_type, src, sink, demand}`. 否则 commodity_id 当 key
时 "同物料多条 src/sink route" 覆盖不了.

### F3: 当前 validator sound
四层 binding (direction/front math, cell_owner slot, selected_poses[slot]
== blocking_pose_id, front_cell ∈ occupied_cells) + multiset exact + port 存在.
真数据 N=273 S=257 E=0 W=0, Phase 1.2 加 E/W fixture.
spec `03_port_exposure.md:42` 仍 up/down/left/right, src N/S/E/W (drift 必修).

### F4: 单 route per registry key 下 sound
BFS 严等 + separator in-grid + ∈ owner∪ghost + Step M registry route src/sink
等 cert. 比 F2 好.

schema 风险 (跟 F2 同): `commodity_routes: {commodity_id: {src, sink}}` 只支撑
"一 id 一 route". 真生产同 commodity 多 route (e.g. blue_iron_ore 多 instance/port)
schema 覆盖不了. 建议改 route_id 级别.

### multiset / Liang-Barsky / ghost_rect
- multiset eval OK (`lifecycle.py:680-728`)
- Liang-Barsky degenerate/touch/axis-aligned OK
- ghost_rect (x,y,h,w) → AABB (x+h, y+w) 跟惯例 (x+w, y+h) 反 — F8 前 lock spec +
  非方形 fixture (e.g. (10,20,3,7))

## B. 架构层

### B1. FAMILY_VALIDATORS strict default 0
`replay.py:122-133` default "0". F1-F4 注册了不吃坑, Phase 1.2 F5-F9 上线前
必切 1.

### B2. CutStore.add_cut 直接 active — P0-3
已述. 必修 add_cut 默认 pending/held.

### B3. BState 新字段 + production inject 路径
6 字段 (canonical_rules / facility_templates / instance_to_facility_type /
candidate_placements / commodity_demands / commodity_routes) 已加.
建议 Phase 1.2/1.5 前唯一入口 `build_bstate_from_production_inputs()` 统一构造.

### B4. source_digest placeholder
`lifecycle.py:643-645` / `region_capacity_oracle.py:179-186` / `replay.py:206`
仍 "poc_source_digest". spec `cut_lifecycle_v2.md:881-903` 已要求真 digest.
Phase 1.2 前必修, 不然 replay data freshness 证明不成立.

### B5. lru_cache(256)
F1 decode cache OK. Phase 1.3 propagator 前应 attach-time eager decode 替 global LRU.

## C. 静态质量 + spec drift

### C1 ruff: all pass (Step M force fix OK)
### C2 mypy strict: 36 errors / 10 files (typing hygiene, 非 runtime fatal)
### C3 vulture: evaluate_literal_port_exposure unused (走 generic multiset path)
### C4 bandit: 6 Low B101 assert (lifecycle/store/replay 内部)
### C5 radon: validate_component_reach D(24), validate_port_exposure D(23), 建议拆 helper
### C6 spec drift
- state_machine_v2.md:44 PoseId Tuple[str,int] vs src str
- cut_lifecycle_v2.md:227 PoseId int vs src str
- cut_lifecycle_v2.md:232-240 family list 仍 symmetry_lift
- cut_family_specs/03_port_exposure.md:42 direction up/down vs src N/S/E/W
- cut_family_specs/01 region_kind 缺 left_or_bottom_union (Step G 加)
- F2 spec max-flow witness src defer
- F4 spec commodity_id / commodity_route assumption src pass-through (Step M 改 require)

## 必修清单

1. **F2 validator**: contributing_commodities 去重 + 必 require state.commodity_routes
   + 每 route 真跨 A/B + registry_demand 用去重 + cert.gap 验
2. **F2 regression**: rejects_duplicate / rejects_same_side_route / requires_commodity_routes /
   replay_same_side_route_quarantines_or_holds
3. **CutStore.add_cut** 改 pending/held 默认, 拆 API: add_pending_cut /
   validate_and_attach_cut / _add_active_cut_private
4. **Phase 1.2 前 strict gate default ON**
5. **schema/spec lock**:
   - PoseId=str / F3 N/S/E/W / ghost_rect tuple object schema /
     source_digest 真 hash / F2/F4 route id vs commodity type 命名

一句话: Step M 把 replay 大洞补上了, 但 F2 新 registry 证明还不够, store 接线
仍能 silent attach. 不能推 Phase 1.2 F5-F9.
