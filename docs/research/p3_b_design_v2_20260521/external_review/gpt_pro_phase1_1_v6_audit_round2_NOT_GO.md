# GPT pro Phase 1.1 v6 audit round 2 — verdict NOT GO

第二次 v6 包独立 audit. Verdict 跟 round 1 一致 NOT GO, 同一 ghost lifecycle
漏口的另一端 — validator side (round 1 是 store/replay side).

## Verdict

**Step N 修 OK 但发现新 critical (选项 2)** — Phase 1.1 Step A-N production NOT GO.

新 P0 不是 F2 cross-partition 没修, 也不是 add_cut default held 没生效:

> 一个依赖 ghost 的 F1/F2/F4 cut, 可以把 `scope.ghost_rect_id` 错标成
> `GHOST_AGNOSTIC`, 然后 replay 通过, reactivate 变 active; 之后 ghost 变了
> store 不会 watch 它也不会 replay/hold/quarantine. 一个已失效 cut 继续 active.

soundness 生命周期漏口.

## 实跑 gates

```text
pytest cuts: 170 passed in 0.85s
pytest -O cuts: 170 passed
ruff src/cuts/ src/tests/cuts/: All checks passed
mypy --strict: Found 37 errors in 10 files
vulture: 多 unused (含 evaluate_literal_port_exposure)
bandit: 5 Low B101 assert_used
radon: cutset.validate D(27) component_reach.validate D(24) port_exposure.validate D(23)
```

## P0: GHOST_AGNOSTIC 错标后 ghost 变更不触发 replay

### 关键路径

`step_6_attach_scope_check` 对 GHOST_AGNOSTIC 放行:
- `src/cuts/lifecycle.py:648-657`

```text
如果 cut.scope.ghost_rect_id == GHOST_AGNOSTIC:
    不要求当前 ghost_rect_id 匹配
    只 check exterior_blocks_hash
```

CutStore.add_cut 只有 ghost_rect_id != GHOST_AGNOSTIC 才挂 ghost watcher:
- `src/cuts/store.py:159-161`

ghost 变更 on_ghost_rect_changed 只 replay watcher 里挂到旧/新 ghost 的 cut:
- `src/cuts/store.py:226-276`

cut 错标 GHOST_AGNOSTIC → 不进 ghost watcher. 后 ghost 变了 不会被 hold/
replay/quarantine.

前提: validator 必证明 cut 真 ghost-agnostic. 但 F1/F2/F4 validator 没 family-
specific scope check.

## 动态反例 1: F2 cutset ghost wall

构造:
- 70×70 grid, old state ghost 竖墙 x=1, y=0..69
- A 左列 x=0, B 右区 x=2..69
- commodity c1 (0,0)→(2,0) demand=1
- old state ghost wall A/B 分开, cut_edges=[] cut_size=0 demand=1 → F2 cert 成立
- scope 故意 GHOST_AGNOSTIC
- new state 去 ghost wall → A/B 连通 cut 失效

实跑:
```text
old ok None eval True
new unsound partition not enclosed eval False
add False True {}
replay ATTACH True {}
after True False False
```

- old validator OK, evaluator True
- new state validator 已 unsound, evaluator False
- 但 store cut 没 ghost watcher: {}
- ghost change 后仍 active

Code 点:
- F2 validator 没查 cut.scope.ghost_rect_id 是否能是 GHOST_AGNOSTIC: `cutset.py:99-301`
- spec 要 F2 scope 绑 ghost: `02_cutset.md:87-89 / 168-173`

## 动态反例 2: F4 component reach ghost wall

同 ghost 竖墙:
- src (0,0) 左 sink (2,0) 右, old state 隔开
- cert src_component 左列, sink_component 右区, separator_cells ghost wall
- scope 故意 GHOST_AGNOSTIC
- old F4 cert 成立, new 去 ghost → src/sink 连通

实跑:
```text
ok None
unsound src_component cert mismatch
ATTACH True {}
True False False False
```

F4 validator 没 scope guard: `component_reach.py:50-233`.
spec F4 scope 依赖 ghost/cell_owner: `04_component_reach.md:39-40 / 70-72 / 161-167`.

## 动态反例 3: F1 region capacity GHOST_AGNOSTIC 错标

构造最小 F1:
- group g 单 pose 占 (0,0), R={(0,0)}, ghost 覆盖 (0,0) → cap_R=0 demand=1
- scope 故意 GHOST_AGNOSTIC
- new state 去 ghost → cap_R=1 cut 不成立

实跑:
```text
validate old ok None
evaluate old True
validate new unsound cap_R mismatch: cert=0, recomputed=1
evaluate new False
replay ATTACH active? True ghost_watchers {}
after ghost change active? True held? False quarantined? False
```

Code 点:
- F1 oracle 生成时知道 GHOST_AGNOSTIC iff ghost ∩ R == ∅ 规则:
  `region_capacity_oracle.py:170-177`
- spec 也明定: `01_region_capacity.md:83-89`
- 但 validator 不 fail-closed

F1 generator 保守, validator/replay 不是.

## Step N 两个显式修复: OK

### 1. F2 cross-partition route check: OK
关键 check 在 `cutset.py:259-278`. 结合 demand registry + routes registry +
duplicate + sum check, v5 same-side 反例修到了.

### 2. CutStore.add_cut default held: OK 但不是完整生命周期防线
`store.py:113-123` default initial_state="held". active bypass `:168-169` 仍存在.
production 没直接调 active bypass, 测试 fixture escape hatch.
建议 Phase 1.2 前再收紧.

## A. 数学层

### F1 主体 sound, scope 缺一刀
- strict P(g)⊆R `:266-285`
- duplicate `:244-260`
- cap_R 重算 `:224-235`
- demand_R 重算 `:328-346`
- gap `:356-377`
- evaluator 重算 `:391-430`

production smoke F1 oracle 保守 emit 0 cuts (boundary 14/54 outside).

### F2 数学 OK, lifecycle scope P0
但允 ghost-dependent proof 用 GHOST_AGNOSTIC scope.

### F3 binding OK, 剩死代码
direction / front math / cell_owner / slot binding / occupied_cells / multiset /
port 存在. `evaluate_literal_port_exposure` `:236` vulture unused (走 generic).

### F4 BFS/route OK, lifecycle scope P0

### multiset / Liang-Barsky / N/S/E/W / ghost_rect
- multiset eval `lifecycle.py:680-728` OK
- N/S/E/W 真数据 N=273 S=257 E=0 W=0
- ghost_rect (x,y,h,w) → (x+h, y+w) 反惯例 (`ghost_geometry.py:108-116`)

## B. 架构层

### FAMILY_VALIDATORS strict default 0
F1-F4 注册不吃坑, F5-F9 前 default ON.

### BState production inject
6 字段 (canonical_rules / facility_templates / instance_to_facility_type /
candidate_placements / commodity_demands / commodity_routes) 已加.
问题不是字段缺, 是 replay/validator 没把 scope.ghost_rect_id 当证明对象验.

### source_digest placeholder 仍在
spec 已要求真 hash bundle. Phase 1.2 前必修.

### lru_cache(256)
当前不是 P0, Phase 1.3 排.

## C. 静态质量 + spec drift

### mypy 37 errors / 10 files
集中 Dict/Callable/Counter 泛型缺参 + Any return + 未注解.

### vulture
`port_exposure.py:236 evaluate_literal_port_exposure` unused (走 generic),
建议删或接入.

### bandit 5 Low B101 assert
`lifecycle.py:444 / 642 / 810 / 821 / replay.py:197`.

### radon
- cutset.validate D(27)
- component_reach.validate D(24)
- port_exposure.validate D(23)
- region_capacity.validate C(20)

最复杂 validator 已 D, 建议 Phase 1.2 前拆 helper, 尤其 F2/F4.

### spec drift
- PoseId src str / spec `cut_lifecycle_v2.md:223-228` int
- family list spec `cut_lifecycle_v2.md:232-241` 仍 symmetry_lift
- F3 direction spec up/down vs src N/S/E/W (`cut_family_specs/03_port_exposure.md:42`)
- F1 spec region_kind 缺 left_or_bottom_union (`cut_family_specs/01_region_capacity.md:42-53/139-140`)
- source_digest spec 要真 hash, src placeholder

## 必修补丁建议

### 1. 给 F1/F2/F4 加 scope contract validator
- F1: `cut.scope.ghost_rect_id == GHOST_AGNOSTIC` → 必 `state.ghost_cells &
  region_cells == ∅` (spec §3 / oracle.py:170-177)
- F2: 不允 GHOST_AGNOSTIC (Phase 1.1 fail-closed; spec §3 必绑当前 ghost)
- F4: 不允 GHOST_AGNOSTIC (separator + BFS free_cells 受 ghost 影响)

### 2. 回归测试
- F1: GHOST_AGNOSTIC + ghost_cells intersects R → reject
- F2: ghost wall cert + GHOST_AGNOSTIC → reject
- F4: ghost separator cert + GHOST_AGNOSTIC → reject
- lifecycle: ghost-dependent active cut, ghost change 必 hold/replay/quarantine

### 3. 测试 fixture 别让错误 scope 正常化
F2/F4 fixture 太容易 GHOST_AGNOSTIC. 分:
- 合法 scope: 绑 compute_ghost_rect_id(state.ghost_rect)
- 非法 scope: 故意 GHOST_AGNOSTIC 并断言 reject

### 4. Phase 1.2 前 strict gate default ON

### 5. source_digest placeholder 必清

## 结论

**Step N 修 OK 但发现新 critical** — Phase 1.1 Step A-N production NOT GO.

P0: F1/F2/F4 validator/replay 没验 GHOST_AGNOSTIC 是否真合法; store 又依赖
ghost_rect_id 决定 watcher → 错标 cut replay 后 active, ghost 变化不 replay,
失效 cut 继续 active.

修完 scope contract + 回归测试后, 重新审一次. 当前不建议推 Phase 1.2 F5-F9.
