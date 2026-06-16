# GPT pro Phase 1.1 v6 audit round 1 — verdict NOT GO

GPT pro v6 包 (`phase1_1_gpt_pro_review_v6.zip` commit `afef8f1`) audit. 对应
Step N 修 (F2 cross-partition + add_cut default held) 后闭环.

## Verdict

**NOT GO, Step N 修不到位.**

Step N 把 `CutStore.add_cut()` 默认改 `initial_state="held"` 直线路径修到了;
F2 duplicate / commodity_routes / cross-partition route check 也过反例测试.
但 **store ghost transition 生命周期仍能把 held cut 静默激活**, 绕过
FAMILY_VALIDATORS. 正好落在 "production path 仍有 silent attach window?" 上.

## P0-1: ghost transition 可绕 post-attach validator, held cut 变 active

### Code 证据
- `CutStore.on_ghost_rect_changed()` 签名 `replay_fn: Callable[[Cut, BState], AttachDecision]`:
  `src/cuts/store.py:226-232`
- 新 ghost 命中 → `decision = replay_fn(cut, state)`: `src/cuts/store.py:262-263`
- ATTACH → `self.held.discard(cut_id)` (回 active): `src/cuts/store.py:264-265`
- **没强制调 family validator**

真安全 gate 在 `replay_cut()`:
- `step_6_attach_scope_check`: `src/cuts/replay.py:90-92`
- ATTACH 后取 FAMILY_VALIDATORS: `src/cuts/replay.py:122-135`
- validator ok 才 reactivate_cut: `src/cuts/replay.py:135-138`
- unsound/schema_err/timeout 则 quarantine: `src/cuts/replay.py:140-154`

`on_ghost_rect_changed` 的 replay_fn 签名 `(Cut, BState) → AttachDecision` 跟
`replay_cut(cut, state, store, canonical_rules, ...)` 不一致, 正确函数不能直接
传, caller 容易传 `step_6_attach_scope_check` (只 scope check 不 validator,
返 ATTACH).

### 动态反例
构造 scope 完全匹配但 F1 cert 明显 unsound 的 ghost-bound cut:
- `add_cut(cut)` → 默认 held
- `step_6_attach_scope_check(cut, state)` → ATTACH
- `validate_region_capacity(cut, state, {})` → unsound cap_R mismatch
- `on_ghost_rect_changed(..., replay_fn=step_6_attach_scope_check)` → cut 变
  active, 未 quarantine

```text
after_add active False held True ghost_watcher_hit True
pure_step6_decision ATTACH
validator_result unsound cap_R mismatch: cert=999, recomputed=70
after_on_ghost active True held False quarantined False
```

### 必修
1. `on_ghost_rect_changed()` 内 lazy import replay_cut, 调 `replay_cut(cut, state,
   self, canonical_rules=state.canonical_rules, ...)`, 删本函数对 held/quarantine
   重复状态修改
2. 或签名改 `Callable[[Cut, BState, CutStore], AttachDecision]` 或返带
   `post_attach_validated=True` 结构; 纯 step_6 不能再类型通过
3. 回归: scope-valid 但 validator-unsound 的 held cut, ghost transition 后必
   QUARANTINE 或 HOLD, 绝不 active

## P0/P1: add_cut 非法 initial_state 抛错后 cut 留 active

### Code 证据
`add_cut()` 先写入 store:
- `self.cuts[cut.cut_id] = cut`: `src/cuts/store.py:146`
- 注册 watchers: `src/cuts/store.py:148-161`

然后才检查 `initial_state`:
- "held" 加 held: `src/cuts/store.py:166-167`
- "active" pass: `src/cuts/store.py:168-169`
- 其它 raise: `src/cuts/store.py:170-173`

非法 initial_state raise ValueError, 但 cut 已留 self.cuts, 也不在 held/quarantined,
所以 is_active() 为真.

### 动态
```text
raised ValueError add_cut initial_state must be 'held' or 'active', got 'pending'
present_after_raise True active_after_raise True held_after_raise False
```

### 修法
initial_state 校验挪到 mutation 前, 收紧 `Literal["held", "active"]`. 更好把
"active" 从 public API 移掉, test fixture 走私有 helper.

## Step N F2 数学修复: 没打穿

重跑 v5 F2 三反例:
1. same-side route → `unsound commodity 'c1' route 不跨 partition`
2. duplicate contributing → `unsound duplicate contributing commodity 'c1'`
3. commodity_routes 未注入 → `schema_err`

F2 Step N 本身 OK; NOT GO 原因是 store/replay 生命周期没把 validator gate 焊死.

## A. 数学层

### F1: 主体 sound (Step L close)
strict P(g)⊆R / duplicate gid / tuple demand / demand_R 重算 / gap consistency /
evaluate 重算. production smoke F1=0 cut (boundary_io 14/54 outside) 保守 FN.

### F2: 数学 OK, lifecycle 漏口
partition / cut_edges / commodity registry / cross-partition / duplicate 全闭.

### F3: binding 4 层 OK
direction / front math / cell_owner slot / selected_poses[slot] / occupied_cells /
multiset / port 存在. spec direction up/down/left/right vs src N/S/E/W 仍 drift.

### F4: BFS / separator OK, commodity registry OK (Step M+N)

### multiset / Liang-Barsky / ghost_rect
ghost_rect (x,y,h,w) → AABB (x+h, y+w) 反惯例, F8 前 lock + 非方形 fixture.

## B. 架构层

### FAMILY_VALIDATORS strict default 0
F1-F4 注册不吃坑, F5-F9 前 default 1.

### CutStore.add_cut default held
直线 OK. 2 洞:
1. `on_ghost_rect_changed` 绕 replay validator (P0-1)
2. 非法 initial_state 抛错后留 active (P0-3)

### BState 6 字段 production inject
靠 caller 手填, Phase 1.2 前唯一 builder 统一构造.

### source_digest placeholder
`lifecycle.py:643-645 / region_capacity_oracle.py:179-186 / replay.py:206`
仍 "poc_source_digest". 真 hash 我算:
```
canonical_rules.json:        8ac667a1bce67ff9084701d18892f370e19d68cc9b5ace44bd63c68b20d3d6ea
candidate_placements.json:   2bf8eb7af8cf6330a6987bd0e509865752a7df1a67ffaffa9bcb1ec30a6395e3
mandatory_exact_instances.json: 545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6
```
Phase 1.2 F5-F9 前硬阻断项.

### lru_cache / Phase 1.3 hot path
F1 bitset decode lru_cache(256) 在 `region_capacity.py:170-183`. Phase 1.3 前
排期 cache.

## C. 静态质量 + spec drift

```
pytest cuts: 170 passed
pytest -O cuts: 170 passed
ruff src: All checks passed (deps zip 内 default config)
mypy --strict: 37 errors / 10 files (typing hygiene)
vulture: evaluate_literal_port_exposure unused (走 generic multiset)
bandit: 5 Low B101 assert
radon: cutset.validate D(27), component_reach.validate D(24),
       port_exposure.validate D(23), region_capacity.validate C(20)
```

spec drift: PoseId / family list / F3 direction / F1 region_kind / source_digest
(全在 Phase 1.2 P1.11 入门 plan).

## 必修清单 (优先)

### Blocker before GO
1. on_ghost_rect_changed 强制 full replay + family validator gate
2. add_cut 事务顺序: 先校验 initial_state, 再写 cuts/watchers
3. 回归: scope-valid validator-unsound ghost-bound held cut ghost transition 后
   不能 active; `initial_state="pending"` raise 后 store 不能残留 cut

### Before Phase 1.2 F5-F9
- EXACT_FAMILY_VALIDATOR_STRICT default ON
- source_digest 真 hash
- BState production builder 统一
- spec drift 清: PoseId / family list / F3 direction / F1 union region /
  source_digest
- F8 前 ghost_rect tuple lock + 非方形 fixture

## 结论
Step N F2 修 OK + add_cut default held 直线修 OK; 但 Step N 没把 "held cut
只能经 replay+validator 才 active" invariant 焊进整 lifecycle. 本轮 NOT GO.
