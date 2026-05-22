# GPT pro Phase 1.1 v4 audit round 1 — verdict NOT GO

GPT pro v4 包 (`phase1_1_gpt_pro_review_v4.zip` commit `a38620c`) audit. 对应
Step L 修 (F1 duplicate contributing_groups) 后闭环 audit + 之前 v1-v3 已 catch
finding 重审.

## Verdict

**Step L 修 OK 但发现新 critical: Phase 1.1 Step A-L production NOT GO.**

不是 "Step L duplicate 修不到位"; `validate_region_capacity()` 同 gid 去重 +
tuple demand + gap consistency 这几刀本身有效. 但 2 个 production 级洞绕过/污
染这些修复:

1. **P0**: `replay_cut(..., canonical_rules=None)` 跳过所有 post-attach validator
   直接激活 cut. Step L 已修的 F1 duplicate 反例可重新 ATTACH + evaluate=True.
2. **P0**: F2/F4 validator 已注册, 但缺 commodity / route source-of-truth; 外
   部或持久化 cut 进 store 可伪造需求/commodity, validator 返 ok, replay ATTACH,
   step_7 evaluate True.

静态 gate 也不绿: pytest 过, 但 ruff `src/cuts/ src/tests/cuts/` 没过 (12 F401),
mypy strict 35 errors, vulture/bandit/radon 都有需处理项.

## P0-1: validator 可被 `canonical_rules=None` 整体绕过

### Code path
- `src/cuts/replay.py:109-114`: `canonical_rules is None` 时 `store.reactivate_cut()`
  → 直接 ATTACH, 不跑 family validator
- `src/cuts/replay.py:129-148`: 只有 `canonical_rules` 非 None 才调 validator
- `src/cuts/families/region_capacity.py:249-260`: Step L duplicate gid 防线在
  validator 内
- `src/cuts/families/region_capacity.py:328-377`: tuple demand / `demand_R` 重算
  / gap consistency 也都在 validator 内
- `src/cuts/families/region_capacity.py:421-427`: evaluator 仍读 cert 的 demand_R

### 反例 reproduce
构造 Step L 已能拒的 F1 duplicate cut, 走 replay:

```
replay_duplicate_with_canonical_rules_None   ATTACH  active=True  eval=True
replay_duplicate_with_canonical_rules_present QUARANTINE active=False
  reason: duplicate contributing group 'boundary_io' ...
```

### 必修
- `replay_cut()` 禁止 `canonical_rules=None → ATTACH`
- 优先用 `state.canonical_rules`, 没就 QUARANTINE 或 HOLD, 不准激活
- `CutStore.add_cut()` 也最好 pending/held, replay+validator 成功才 active

## P0-2: F2/F4 已注册 validator 缺 commodity/route registry

### F2 cutset

- `replay.py:54-59` 已注册 `"cutset"`
- `cutset_oracle.py:35-57` stub `return []`
- `cutset.py:202-209` 只 `commodity_demand > cut_size`, 没 state/master registry 重算
- `cutset.py:211` max-flow / LP witness defer Phase 1.5+
- spec 要求 cert 含 `contributing_commodities`, `menger_witness_kind`,
  `witness_blob_b64` (`cut_family_specs/02_cutset.md:72-76`); validator 应 verify
  max-flow witness (`cut_family_specs/02_cutset.md:156-159`)

反例: 70×70 中只 2 free cells 封闭 patch, cert 写 `commodity_demand=2`,
`cut_size=1`, `contributing_commodities=["fake"]`, state 无 commodity registry.

```
validate_cutset_fake_demand     ok None
replay_cut_fake_demand          ATTACH  active=True  quarantined=False
step_7_evaluate_fake_demand     True
```

### F4 component_reach

- `replay.py:54-59` 注册 `"component_reach"`
- `component_reach_oracle.py:34-44` stub
- `component_reach.py:114-144` BFS bitset 严等 (好)
- `component_reach.py:154-182` separator in-grid + ∈ cell_owner ∪ ghost (好)
- `component_reach.py:184-198` commodity_id pass-through 当 metadata
- evaluator `:225-235` 只看 src/sink disconnected

反例: src=(0,0)/sink=(2,0) 中间 ghost, commodity_id="fake", state 无 route.

```
validate_component_reach_fake_commodity ok None
replay_cut_fake_commodity              ATTACH  active=True  quarantined=False
step_7_evaluate_fake_commodity         True
```

### 影响
F2: 几何 cut edges 不等于 sound — Menger 数学前提是 "所有跨 partition commodity
总需求 > cut capacity". 当前 src 没把 cert 字段连到真实 commodity source.
F4: BFS sound 但 "两 cell 不连通 ≠ 当前布局 infeasible". 必须真实 commodity/route
要求绑定.

### 必修
- F2: BState 加 commodity demand registry, validator 重算 cross-partition demand,
  contributing_commodities exact set, 无 registry 时 schema_err/HOLD
- F4: 同上 commodity route registry, 无 registry 时 fail-closed
- 短期建议 F2/F4 从 FAMILY_VALIDATORS 去掉 直到 registry land

## 任务 A: 数学层逐项

### F1: Step L 本体 OK
- strict P(g)⊆R `:151-167` + `helpers/candidate_placements.py:126-162`
- duplicate gid 防线 `:244-260`
- tuple demand 真等 `:313-326`
- demand_R 重算 + gap `:328-377`

duplicate 同 gid 反例: `F1_duplicate_same_gid_result unsound duplicate contributing
group 'boundary_io'`. validator 内部 sound.

不同 gid 但 "同 group split" 攻击: 在合法 BState 里 GroupId == operation_type,
如果两 gid 都在 state.groups 就是不同 group. validator 不能猜 alias. 是 BState/
source_digest 层问题.

真数据 F1 0 cut 合理: boundary 54 poses 14 个不满足 left∪bottom union,
`viewer::boundary_required_output_source_ore_005` 占 (31,69)/(32,69)/(33,69)
(`candidate_placements.json:985-1007`).

### F2 partition/enclosure OK, commodity_demand registry 缺 P0
- partition disjoint `:131-137`
- partition cells free `:139-153`
- patch enclosure `:155-164`
- cut_edges canonical `:177-200`
- evaluator 同步 enclosure `:223-247`
- cut_edges malformed → schema_err catch (但 IndexError, Phase 1.2 改 explicit)

### F3 binding 4 层 OK
- 2 literals `:69-77`
- direction/front math `:88-104`
- cell_owner slot `:106-117`
- slot range + selected_poses[slot] == blocking_pose_id `:119-148`
- front_cell ∈ blocking_pose.occupied_cells `:149-170`
- multiset exact `:172-194`
- port 真存在 `:196-223`
- generic multiset eval slot anonymity `lifecycle.py:672-720`

后续:
- spec direction 仍 up/down/left/right (`cut_family_specs/03_port_exposure.md:39-44`),
  src N/S/E/W
- spec require active_port_witness (`:144-147`), src 没查

### F4 BFS/separator 几何 OK, commodity_id 不能长期 pass-through
- BFS frozenset 严等
- separator in-grid + ∈ owner∪ghost
- commodity_id pass-through 当前 Phase 1.5+ apply-to-master 前必加 registry

### multiset/Liang-Barsky/ghost_rect
- multiset eval OK (`lifecycle.py:696-720`)
- Liang-Barsky degenerate/touch/axis-aligned OK
- ghost_rect tuple (x,y,h,w) → AABB (x+h, y+w) 跟常规 (x+w, y+h) 反 — F8 前
  必锁 spec + 非方形 fixture (e.g. (10,20,3,7))

## 任务 B: 架构层

### Silent attach 两层
1. `canonical_rules=None` 跳 Step 7 (P0-1)
2. unknown family + env strict=0 → ATTACH (`replay.py:116-127`)

Phase 1.2 前 strict default 1 或 certified path 永 fail-closed.

### CutStore add 直接 active 注册 (`store.py:113-147`)
约定"只 add 已 validate cut"太脆, 建议 add 默认 pending/held, replay 成功才 active.

### Defer 风险排序
1. replay fail-closed + strict default + add_cut pending
2. F2/F4 commodity/route registry 或 unregister
3. source_digest 真 hash (替 `"poc_source_digest"`)
4. spec/schema drift PoseId / family list / F1 union / F3 directions
5. Phase 1.3 hot path: by_exterior_watcher, parsed cert cache, decoded bitset

### BState schema / PoseId / source_digest
- `lifecycle.py:44-48` PoseId=str ✓
- doc `state_machine_v2.md:44` 仍 Tuple[str,int]
- doc `cut_lifecycle_v2.md:227` 仍 int
- `source_digest` 仍 `"poc_source_digest"` placeholder
- attach check 写死 `lifecycle.py:635-637`
- oracle 写死 `region_capacity_oracle.py:179-186`

### lru_cache(256) OK
multiprocess spawn 每 worker 一份, 内存 ~99MB/worker 上限. Phase 1.3 propagator
前应 attach-time eager decode 代替 global LRU.

## 任务 C: 静态质量 + spec drift

### ruff
- src/cuts/ clean
- src/tests/cuts/ 12 F401 (跟 COMMIT_LOG.md:18 "ruff F401 12 个清" 矛盾)

### mypy strict (35 errors, 不 34)
多个 `Dict` 缺 type args / `Any` return / unused ignore.

### vulture
- `port_exposure.py:236` `evaluate_literal_port_exposure` unused (走 generic)
- `lifecycle.py:539` `step_5_validate_region_capacity` unused (旧 PoC, 建议删/shim)

### bandit
6 Low B101 assert (`lifecycle.py:436,634,802,813 / replay.py:191 / store.py:131`).
store.py:131 production path 建议 explicit if.

### radon
- `validate_port_exposure D(23)` Step J 加 binding 后升级, 建议拆
- `validate_region_capacity C(20)`
- `validate_component_reach C(19)`

### spec drift 必修
1. PoseId state_machine_v2.md:44 / cut_lifecycle_v2.md:227 vs src str
2. family list cut_lifecycle_v2.md:232-240 仍 symmetry_lift
3. F1 spec schema region kind 旧四类, src 加 left_or_bottom_union
4. F2 spec max-flow witness, src defer (validator 注册时这是 P0 一部分)
5. F3 spec direction up/down/left/right, src N/S/E/W
6. F4 spec commodity_id / commodity_route assumption, src pass-through

## 必修清单 (优先)

1. 改 replay_cut(): 禁 canonical_rules=None → ATTACH; state fallback; 无 source
   fail-closed + regression
2. CutStore new cut 默认 pending/held, replay+validator OK 后才 active
3. F2/F4 registry 落地前 fail-closed 或 unregister
4. source_digest 真 digest
5. ruff tests F401 真清
6. spec drift 同步
7. fixtures: F2/F4 fake commodity rejected / F1 dup with rules=None rejected /
   F3 E/W synthetic / ghost_rect non-square h/w
