# GPT pro Phase 1.1 v4 audit round 2 — verdict NOT GO

第二次 v4 包独立 audit. Verdict 跟 round 1 一致, finding 高度重叠 + 反例补强.

## Verdict

**Step L 的 F1 语义修 OK, 但发现新 Critical — NOT GO.**

1. F1 duplicate contributing_groups 修到位
2. F2/F4 新 Critical: 外部/replay/disk cut 进 CutStore 时可伪造 commodity_demand
   / commodity_id, validator 给 ok, replay ATTACH
3. v4 包 ruff 清理没真落包: `ruff check src/cuts/ src/tests/cuts/` 仍报 12 F401,
   跟 commit log "ruff F401 12 个清" 不一致

## 实跑结果

| Gate | 结果 |
|---|---|
| `pytest src/tests/cuts/ -q` | 161 passed |
| `python -O -m pytest src/tests/cuts/ -q` | 161 passed, 1 warning |
| production smoke | F1 cuts emitted: 0; 266 instance / 273 pose |
| `ruff check src/cuts/ src/tests/cuts/` | fail, 12 F401 |
| `mypy --strict src/cuts/` | fail, 35 errors / 10 files |
| `vulture src/cuts/` | exit 3, dead-code candidates |
| `bandit -r src/cuts/` | 6 Low B101 assert |
| `radon cc src/cuts/ -s -a` | average A(4.36), validate_port_exposure D(23) |

真数据 verify:
- candidate_placements: BSP=54, mfg_3x3=132, mfg_5x5=49, mfg_6x4=38, total=273
- port direction N=273, S=257, E=0, W=0
- boundary_io demand=46, template w=1 h=3, placement_rule=left_or_bottom_boundary
- 14/54 BSP 不在 left∪bottom union (sample `viewer::boundary_required_output_source_ore_005`
  占 (31,69)/(32,69)/(33,69))

## Critical 1: F2 commodity_demand 无 source-of-truth

构造 70×70 全图左右两半, free_cells=4900, side_a=2450, side_b=2450, 真 cross edges=70,
cert 伪造 commodity_demand=71 + contributing_commodities=["FAKE"]:

```
validate_cutset    ok None
replay_cut         ATTACH  is_active=True  quarantined=False  held=False
```

### Code 原因
- 几何 partition + cut edges 重算 sound
- `cutset.py:202-209` 只 commodity_demand > cut_size, 没 state/registry 重算
- F2 oracle stub 不 emit (`cutset_oracle.py:35-57`), 但 validator 注册 (`replay.py:54-58`)
- `replay_cut` 对已注册 validator 调 ok 后 ATTACH (`replay.py:116-148`)
- `CutStore.add_cut` 只注册不验 source (`store.py:113-148`)

### Critical 理由
F2 数学前提是 "所有需要跨这个 partition 的 commodity 总需求 > cut capacity".
spec 写了 commodity_demand + contributing_commodities + menger_witness_kind +
witness_blob_b64 (`02_cutset.md:64-77`), 当前 src 没把这些连到真实 commodity source.

必修:
- BState 加 commodity route/demand registry, 或 validator 接 registry 参数
- 重算哪些 commodity 跨 A/B, demand sum 是否等于 cert
- contributing_commodities exact set, 不允 FAKE
- 无 registry 时 schema_err / HOLD
- F2 validator 注册前的 production path 不允 attach 或 replay 层强制 stub cut 全拒

## Critical 2: F4 commodity_id 也能伪造并 ATTACH

构造 vertical wall 把 (0,0) 跟 (69,0) 分开, cert commodity_id="FAKE_COMMODITY",
state 无 commodity registry:

```
validate_component_reach  ok None
replay_cut                ATTACH  is_active=True  quarantined=False  held=False
```

### Code 原因
- 几何 BFS + separator 严
- `component_reach.py:184-198` commodity_id pass-through metadata
- spec require commodity_id 必填字段 (`04_component_reach.md:48-56`)
- spec require Assumption("commodity_route", ...) (`04_component_reach.md:70-77`)
- 当前 assumption verifier 只 placement_rule / left_or_bottom_boundary_saturation
  (`assumptions/verifiers.py:87-98`), 没 commodity_route

### 严重性 (跟 F2 不同)
- F4 几何断连证明 sound
- 但 "这个 src/sink 是否真属于必连通 commodity" 没证明

判定:
- **Phase 1.1 几何 validator: OK**
- **Phase 1.3/1.5 apply-to-master 前: Critical blocker**

Step 8 apply-to-master 看 F4 active 就加 master constraint 而不查 commodity registry
→ 误剪合法解.

## F1 审查: Step L 修 OK

四层关键防线:
- strict P(g)⊆R (`:273-285`)
- cells_per_pose 重算 (`:286-312`)
- tuple demand == state.groups[gid].demand × cpp (`:313-326`)
- demand_R 独立重算 + gap (`:328-377`)
- duplicate gid 拒 (`:244-260`)

三个攻击全拒:
```
duplicate_same_gid          unsound duplicate contributing group 'a'
fake_second_gid_missing     unsound group 'b' placement_rule 不映射 ...
tuple_mismatch              unsound contributing_groups tuple demand mismatch for 'a'
```

不同 gid 但 actual 是 1 group 攻击不成立: 合法 BState 里 GroupId == operation_type,
不同 gid 在 state.groups 就是不同 group. 同 gid 重复已修.

evaluator 仍信 cert.demand_R: 前提是所有进 active store 的 F1 cut 先过
validate_region_capacity, Phase 1.3 hot path 不允绕 replay/validator 直吃外部
cert. evaluator 不是 trust boundary, replay path 当前对 F1 安全. Phase 1.3 接
propagator 时把"active cut 必经 validator"做硬 invariant.

## F2 几何修 OK, source 缺口 P0

修好部分:
- partition disjoint `:131-137`
- partition cells free `:139-153`
- patch enclosure `:155-164`
- cut_edges canonical set `:177-200`
- evaluator 同步 free + enclosure `:223-247`

cut_edges malformed 现在 catch 成 schema_err (`:215-220`), 短期能挡 Phase 1.2 改
explicit shape check.

真 NOT GO 是 commodity_demand registry 缺失.

## F3 binding 四层覆盖主要攻击面

7 层校验 (front math / cell_owner slot / slot range / selected_poses[slot]
match / occupied_cells include / multiset / port 真存在 + generic multiset 不
看 slot index).

5 攻击全拒:
```
valid                                       ok None
literal_pose_mismatch                       unsound cert ↔ literals multiset mismatch
selected_pose_mismatch                      unsound blocking_pose_id mismatch
blocking_pose_not_occupying_front           unsound front_cell not in blocking_pose occupied_cells
bad_front_math                              unsound front_cell mismatch
```

validate_port_exposure D(23), 建议拆 helper, 不是 P0.

## F4 BFS/separator 几何 sound, commodity source 待补

F4 比 spec 更严 (spec 只 separator not free, src 加 in-grid + ∈ cell_owner ∪
ghost). Step K 方向正确. commodity_id pass-through 是 Critical 2.

## multiset / Liang-Barsky / directions / ghost_rect

- multiset eval 匿名 slot OK (`lifecycle.py:672-720`, state_machine §5)
- direction N/S/E/W: 真数据 N=273 S=257 E=0 W=0, Phase 1.2 加 E/W fixture
- ghost_rect tuple 语义反常规 (h/w 跟惯例 w/h 反), F8 前 lock spec + 非方形
  fixture

## 架构层

### FAMILY_VALIDATORS strict default 0 — Phase 1.2 前必切 1
未注册 family + env=0 → silent ATTACH (`replay.py:116-127`). F5-F9 还没注册.
Phase 1.2 做 F5-F9 前:
- CI / production EXACT_FAMILY_VALIDATOR_STRICT=1
- 本地增量开发允许 0
- oracle stub family 明确 deny external cut

### CutStore watcher / GHOST_AGNOSTIC 风险排序
1. source_digest placeholder (`lifecycle.py:635-637 / region_capacity_oracle.py:179-186`)
   — 数据轮换后无法识别 source
2. F2/F4 commodity registry — Critical 1/2
3. strict default 0 — `replay.py:116-127`
4. GHOST_AGNOSTIC + exterior watcher deferred (`store.py:99-105`)
   — sound 暂靠 evaluator 重算, 性能后痛
5. ghost transition 只看 by_ghost_watcher (`store.py:219-223`)

### BState schema PoseId=str ✓, doc 仍 Tuple[str,int]/example PoseId int
- src `lifecycle.py:42-49 / 186-198`
- doc `state_machine_v2.md:42-45 / 274-279`

## 静态质量 / spec drift

### ruff
仍 12 F401, 跟 commit log 不一致:
- test_family_cutset.py:22,26
- test_lifecycle.py:30
- test_replay.py:21,22,24,25,26
- test_store.py:16,26,27,28

### mypy 35 errors
泛型缺参 / Any return / unused ignore. `region_capacity.py:427` Any return
对应 `:424-427`.

### vulture
`evaluate_literal_port_exposure` unused (`:236`) — generic path OK 但需 whitelist.

### bandit 6 Low B101
lifecycle / store / replay 内部 assert. python -O pytest 已过. store.py:131
production 入口建议改 explicit guard.

### radon
- validate_port_exposure D(23) — Step J 加 binding 后升级
- validate_region_capacity C(20)
- validate_component_reach C(19)
- segment_aabb_intersection_t C(15)

### spec drift 必修
- state_machine_v2.md PoseId Tuple/str
- cut_lifecycle_v2.md family list symmetry_lift
- F2 spec max-flow witness
- F3 spec direction up/down vs N/S/E/W
- F4 spec commodity_id / commodity_route assumption

## 必修建议

1. F2 commodity source: 无 registry 不允 validate_cutset ok
2. F4 commodity_route verifier: 无 registry F4 cut HOLD / schema_err
3. strict validator gate default ON
4. v4 包 ruff F401 真清
5. spec drift: PoseId=str / 去 symmetry_lift / F3 N/S/E/W / F2/F4 source registry
6. F8 前 lock ghost_rect tuple 语义

结论: 不能给 Phase 1.1 Step A-L production GO; F1 Step L 语义修通过, 但 F2/F4
source-of-truth 缺口让 framework 不是 production sound.
