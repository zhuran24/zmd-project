# GPT pro Phase 1.1 v5 audit round 2 — verdict NOT GO

第二次 v5 包独立 audit. Verdict 跟 round 1 一致, 反例补强 + 额外 dynamic
reproduction.

## Verdict

**NOT GO, Step M 修不到位.**

不是 replay canonical_rules=None 没修 — 那刀修对. 真挡 GO 的:

1. **F2 commodity registry 仍不 sound**: validator 只查 "id 在 registry, demand
   等 cert", 没证 commodity/route 真跨 partition, 也没防 duplicate commodity
   重复计 demand. 动态反例 unsound cut 返 ok.
2. **CutStore.add_cut 仍直接 active**: Step M 修 replay fail-closed, 没堵 "新 cut
   add 后 replay 前能被 active 查询" silent attach window.

## 实跑 gates (跟 round 1 一致 — 高 confidence signal)

```text
pytest cuts:                            167 passed
pytest -O cuts:                         167 passed, 1 warning
production smoke:                       F1=0, instances=266, poses=273
ruff src/cuts/ src/tests/cuts/:         All checks passed
mypy --strict:                          36 errors / 10 files (not 35)
vulture:                                evaluate_literal_port_exposure unused
bandit:                                 6 Low B101 assert
radon:                                  component_reach.validate D(24),
                                        port_exposure.validate D(23),
                                        region_capacity.validate C(20),
                                        cutset.validate C(18)
```

## P0-1: F2 registry 修法仍不 sound

### 直接问题

`cutset.py:202-215` Step M require state.commodity_demands.
`cutset.py:225-227` registry_demand = sum(...) 直接 list 求和.
`cutset.py:228-237` 只 cert vs registry demand 比.
`cutset.py:238-245` 只查 commodity 在 registry.

缺:
1. contributing 不能 multiset (集合语义)
2. 每个 contributing route 必 src ∈ A AND sink ∈ B (或反)

### 反例 A: route 不跨 partition

```text
A = {(0,0)}, B = {(0,1)}, cut_size=1
state.commodity_demands = {"c": 2}
state.commodity_routes = {"c": {"src": (0,0), "sink": (0,0)}}
cert.contributing_commodities = ["c"]
cert.commodity_demand = 2
```

route src/sink 都在 A — 真跨 partition demand=0. validator 输出:

```text
ValidationResult: ok None
Route c src/sink: {'src': (0, 0), 'sink': (0, 0)}
A={(0,0)}, B={(0,1)}; route stays in A, true cross-partition demand=0
Cert commodity_demand: 2 cut_size: 1
```

spec 是 cross-partition 语义:
- `02_cutset.md:14-18` demand / routing graph / commodity src-sink 定义
- `02_cutset.md:24-30` cut 必分离 commodity src/sink, demand 需穿过 cut
- `02_cutset.md:112-123` generator `sum_commodity_demand_cross_partition(A, B, ...)`

spec ↔ src gap, 不是 test 风格.

### 反例 B: duplicate commodity demand 翻倍

```text
state.commodity_demands = {"c": 1}
contributing_commodities = ["c", "c"]
commodity_demand = 2, cut_size = 1
```

唯一 commodity demand=1 不该 2>1. validator 输出:

```text
ValidationResult: ok None
True registry demand for unique {c}: 1
Cert demand after duplicate sum: 2
```

F1 已有 duplicate group 防 (`region_capacity.py:244-260` Step L), F2 缺同等防线.

### F2 必修

schema 改 route 级:
```python
commodity_routes: {
    route_id: {
        "commodity": str,
        "src": [x, y],
        "sink": [x, y],
        "demand": int,
    }
}
```

validator:
1. contributing_route_ids 非空
2. route_id 唯一 (set 去重)
3. 每 route_id 在 registry
4. src ∈ A xor sink ∈ A
5. sum(route.demand) == cert.commodity_demand
6. cert.commodity_demand > cut_size

否则 Step M 的 commodity_demands registry 只是验数字来源, 不验证明对象.

## P0-2: CutStore.add_cut 直接 active

Step M 修 replay, store 层仍:

`store.py:113-148` add_cut:
- `:129` 只查 duplicate id
- `:131` 只 assert cut.scope is not None (python -O 删)
- `:132` `self.cuts[cut.cut_id] = cut`
- `:134-147` 注册 watchers

`store.py:171-176` is_active: cut in cuts AND not quarantined AND not held →
add_cut 默认就 active.

### 动态反例

```text
validator before store: unsound
active immediately after add_cut: True
held immediately after add_cut: False
quarantined immediately after add_cut: False
replay decision: QUARANTINE
active after replay: False
quarantined after replay: True
```

silent attach window: validator unsound 已知, store add 后 replay 之间 active
窗口.

`replay.py:109-120` 的 fail-closed 只保护 replay 入口, 不保护 add→replay 之间.

### store 必修

方案 A: add_cut(..., initial_state="held")
方案 B: 拆 API add_pending_cut + attach_validated_cut

回归: tampered cut add 后 is_active 必 False, validator/replay 成功后才 True.

## Step M replay fail-closed: OK 但只 replay 内 OK

`replay.py:109-120`:
- canonical_rules=None → fallback state.canonical_rules
- 还 None → store.hold_cut + HOLD

v4 canonical_rules=None bypass 关掉.

caveat:
1. CutStore.add_cut 不经 replay (上述 P0-2)
2. 未注册 family fallback 仍默认非 strict (`replay.py:122-133`), Phase 1.2 F5-F9 前 strict default ON

## A. 数学层

### F1: 当前更像 safe false-negative, 没打出 FP
全闭环 (strict P(g)⊆R, duplicate gid, tuple demand, demand_R/cap/gap consistency,
evaluate 重算). production smoke F1=0 (boundary_io 14/54 outside) 保守不 unsound.

### F2: NOT sound (P0-1)
schema commodity_demands 当前 `{id: int}` 只支撑 demand 数, 没 route 信息.
建议 schema 改 route_id 级别.

### F3: 当前 sound
4 层 binding + multiset exact + port 存在 + generic multiset eval. spec drift
direction up/down vs N/S/E/W.

### F4: 单 route per registry key 下 sound, schema 需 lock
BFS 严等 + separator + Step M registry route src/sink 等 cert.
schema 风险: `commodity_routes: {id: {src, sink}}` 一 id 一 route.
真生产同 commodity 多 route 覆盖不了, 建议 route_id 级别.

### multiset / Liang-Barsky / ghost_rect
- multiset eval OK
- Liang-Barsky OK
- ghost_rect (x,y,h,w) → AABB (x+h, y+w) 反惯例, F8 前 lock + 非方形 fixture

## B. 架构层

1. FAMILY_VALIDATORS strict default 0, F5-F9 前必 1
2. CutStore.add_cut 直接 active — P0-2
3. BState 6 inject 字段, production 路径建议统一 build_bstate_from_production_inputs
4. source_digest placeholder 仍在 — Phase 1.2 前必修
5. lru_cache(256) Phase 1.3 前 attach-time eager decode

## C. 静态质量 + spec drift

- ruff: All pass
- mypy: 36 errors typing hygiene
- vulture: evaluate_literal_port_exposure unused
- bandit: 6 Low B101
- radon: validate D(24)/D(23) 建议拆 helper

spec drift:
- PoseId state_machine_v2.md:42-45 / cut_lifecycle_v2.md:223-229 仍 Tuple[str,int] / int
- family list cut_lifecycle_v2.md:232-241 仍 symmetry_lift
- F3 direction cut_family_specs/03:39-44 up/down/left/right
- F1 region_kind cut_family_specs/01:139-145 缺 left_or_bottom_union
- source_digest spec 已要求真 hash, src placeholder

## 必修清单

```
P0-1: F2 cutset validator 从 route registry 重算 cross-partition demand,
      拒 duplicate route. (src/cuts/families/cutset.py:202-245)
      regression: non-crossing / duplicate validator 必 unsound

P0-2: CutStore.add_cut 不能默认 active. (src/cuts/store.py:113-148, 171-176)
      regression: validator unsound 的 cut, add_cut 后 is_active=True 必 False

P1: EXACT_FAMILY_VALIDATOR_STRICT default 改 ON
P1: source_digest 从 placeholder 改真 hash
P1: F4/F2 registry schema lock route_id 级别, 支持同 commodity 多 route
P1: ghost_rect tuple 语义锁死 + 非方形 fixture
```

判断: Step M replay fail-closed OK; F2 registry 不够 + store active 窗口仍在.
Phase 1.1 Step A-M 不能 production GO, 不建议直接推 Phase 1.2 F5-F9.
