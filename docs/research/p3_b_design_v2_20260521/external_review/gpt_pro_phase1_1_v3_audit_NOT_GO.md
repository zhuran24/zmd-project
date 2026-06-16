# GPT pro Phase 1.1 v3 audit — verdict NOT GO (新 P0)

GPT pro v3 包 (`phase1_1_gpt_pro_review_v3.zip` commit `bdaa303`) audit.
对应 Step I/J/K 修复闭环 audit + v2 round 1+2 catch 重审.

## Verdict

**Step I/J/K 修 OK，但 v3 仍然不是 production GO** — 找到 1 个新 P0 (不在
v1/v2 + Gemini r33-r35 已 catch 清单)。

**最终**: "Step I/J/K 修 OK 但发现新 critical — 必修后再推 Phase 1.2 F5-F9."

## P0 (新): F1 duplicate `contributing_groups` 可伪造 over-demand cut

### File:line
- `src/cuts/families/region_capacity.py:239-242` — validator 读 cert tuple 列表
  转 list, 没去重
- `src/cuts/families/region_capacity.py:246-293` — 循环逐项检查 gid, 缺 seen_gid
- `src/cuts/families/region_capacity.py:109-126` — compute_demand 按 cert tuple
  逐项累加, 同 gid 出现两次累加两次, 忽略 `_demand_in_cert`
- `src/cuts/families/region_capacity.py:295-321` — witness 只验 recomputed >
  cap_R, 重复计数后假 demand 通过
- `src/cuts/families/region_capacity.py:365-371` — evaluator 不重算 demand, 拿
  cert.demand_R 跟当前 cap 比

### 反例 reproduce

actual: demand=70 (单 group), cap_R=139 (合法状态).

cert duplicate 同一 group:
```json
"contributing_groups": [["g", 70], ["g", 70]],
"demand_R": 140,
"cap_R": 139
```

实跑:
```
F1_duplicate_contributing_groups_validator ok
F1_duplicate_evaluate True
```

→ cert 通过, 错误剪合法 state (真 demand 70 ≤ cap 139 应可行).

### 必修建议 (GPT 提)

validator 加:
```python
seen_gids: set[str] = set()
for gid, demand_in_cert in contributing_groups:
    if gid in seen_gids:
        return "unsound duplicate contributing group"
    seen_gids.add(gid)
    expected = state.groups[gid].demand * current_cpp
    if demand_in_cert != expected:
        return "unsound contributing group demand mismatch"

if cert_dict["gap"] != cert_dict["demand_R"] - cert_dict["cap_R"]:
    return "unsound gap mismatch"
if cert_dict["gap"] <= 0:
    return "unsound non-positive gap"
```

regression: `actual demand=70, cap=139, duplicated contributing_groups →
validator 必拒`.

## 验证 v2 round 1+2 修复 (Step I/J/K close 确认)

- **P0-1** step_7 dispatch: `lifecycle.py:723-753` 真接 family evaluator. 实测:
  `F1_eval_gen=True / step7_gen=True / cap_gen=89`, 移除 exterior_blocks 后:
  `F1_eval_after_unblock=False / step7_after_unblock=False / cap_after=139` ✓
- **P0-2** F3 blocking_slot binding: `port_exposure.py:119-148` 真验
  `selected_poses[slot]==blocking_pose_id` + 149-170 `front_cell ∈ occupied_cells`.
  实测: `F3_valid=ok / F3_blocking_pose_mismatch=unsound` ✓
- **High** F4 separator: `component_reach.py:154-182` 验 in-grid + ∈ cell_owner ∪
  ghost. 实测: `[[999,999]] → unsound not in grid / [[69,69]] → unsound not in
  cell_owner ∪ ghost` ✓
- **F2 evaluator enclosure**: `cutset.py:223-247` hot path 同步加. 实测:
  `F2_eval_patch_escape=False` ✓

Step I/J/K 全 4 fix 接线 OK, 不是漏修.

## 静态层 (实跑)

```
pytest cuts: 158 passed in 1.24s
pytest -O cuts: 158 passed (1 warning)
F1 真数据 smoke: F1 cuts emitted=0 (boundary_io 14/54 outside 数学 fail-closed 预期)
ruff: 12 errors (全 tests F401 unused)
mypy --strict: 34 errors (typing hygiene, 非 runtime fatal)
vulture: evaluate_geometric_region_capacity 已不被标 unused (Step I dispatch OK)
        evaluate_literal_port_exposure 仍 unused (literal 走 generic multiset eval)
bandit: 6 Low B101 assert (lifecycle/store/replay 内部)
radon: 平均 A 4.31; 最高 validate_port_exposure D(23) — Step J 加 binding 后升级
       建议拆 3 helper (cert schema / blocking pose binding / literal multiset)
```

## 任务 A: 数学层 (逐项)

### F1 `P(g)⊆R` strict + cap_R + evaluate 真重算
- Step E/F/G/I 本身基本 OK, 但被 duplicate group P0 卡住
- `all_poses_in_region` fail-closed None 合理 sound
- `cap_R` 重算只排除 ghost/exterior 不排除普通 occupied 符合 F1 下界
- evaluator 重算 cap + 跟 cert.demand_R 比, dispatch OK
- 但 evaluator 仍信 cert 的 demand_R → duplicate group P0 穿透 validator 后继续生效

### F2 partition enclosure + cut_edges + evaluator enclosure
- validator/evaluator 修复 OK (Step C + Step I/J/K bonus)
- `_has_patch_escape` 覆盖 spec §1a OK
- cut_edges canonical compare fail-closed (但 IndexError 而非 schema_err, Phase
  1.2 改 explicit)
- F2 oracle 当前 stub 不 emit, 但 commodity_demand 无 source-of-truth registry
  — Phase 1.2 F2 上线前必修

### F3 cert↔literal multiset + blocking_slot → pose binding
- Step B/J 修复 OK
- multiset 精确相等 + binding 三层 (slot 范围 + selected_poses[slot] +
  occupied_cells include front_cell)

### F4 BFS bitset + separator + commodity_id
- BFS frozenset 严等 + separator in-grid + ∈ cell_owner ∪ ghost OK
- commodity_id pass-through 当前 geometric-only OK, Phase 1.5+ apply-to-master
  时 必 commodity registry verify

### multiset eval
- 跨 group permutation soundness OK
- backtracking 匹配 + 数量消耗 + 0-literal 构造层拒

### Liang-Barsky + direction N/S/E/W
- 退化 segment / corner-touch / endpoint inside 边界覆盖
- 真数据 273 pose × 530 port → 方向 N=273 / S=257 / E=0 / W=0
  代码支持 N/S/E/W, 测试覆盖 W, 但**真数据只 N/S 覆盖** — Phase 1.2 E/W
  fixture 必加
- ghost_rect tuple `(x,y,h,w)` 跟 cell_aabb_from_rect `(x+h, y+w)` 语义 h/w
  反常规 — 测试 baked in, F8 power_grid_reach 前必 lock schema

## 任务 B: 架构层

### FAMILY_VALIDATORS strict default
- default 0 silent attach. 未注册 family cut + ATTACH (实测验). Phase 1.2 F5-F9
  上线前必 default 1.

### CutStore watcher + GHOST_AGNOSTIC
- 状态机闭环 OK
- GHOST_AGNOSTIC 不入 by_ghost_watcher, Step F evaluate 重算补 sound, watcher 是
  efficiency, defer 合理

### 最先爆排序 (verdict)
1. **source_digest placeholder** — replay/source mismatch 直接污染 cert 可信
2. **strict validator default 0** — F5-F9 silent attach
3. **F2 commodity_demand registry** — F2 oracle 上线即需
4. HR5 GHOST_AGNOSTIC invalidate / non-rect / free-placement (Phase 1.3+ 性能/覆盖)
5. thread-safe (多 worker shared store 前)

### BState schema + PoseId + source_digest
- 4 字段完整 production interface
- state_machine_v2.md:42-45 `PoseId=Tuple[str,int]` vs src `PoseId=str` 仍 drift
- source_digest 仍 `"poc_source_digest"` placeholder (`region_capacity_oracle.py:179-186`
  + `lifecycle.py:627-669` 只接受此). docs 已要求 digest 覆盖
  canonical_rules + candidates + mandatory_instances + oracle_versions
  (cut_lifecycle_v2.md:80-86 / 146-154 / 291-296 / 388-395 / 878-895). Phase
  1.2 前必修.

### lru_cache(256)
- multiprocess spawn 每 worker 一份, 不共享, 不 leak
- Phase 1.3 hot path 接 propagator 后建议 decode 后的 frozenset 进 cert/runtime
  parsed payload 避免重复 JSON decode

## 任务 C: 静态质量 + spec drift

### ruff F401 (12 个 tests)
`test_family_cutset.py:22,26 / test_lifecycle.py:30 / test_replay.py:21,22,24,25,26 /
test_store.py:16,26,27,28`

### mypy strict 34 errors
`lifecycle.py:221,230,236,264,325,334,423,540,756,787 / canonical_rules.py:36,77,91 /
region_capacity.py:197,371 / cutset.py:94,102,247 / candidate_placements.py:70,104,129 /
component_reach.py:53 / power_network.py:44,45 / oracles/region_capacity_oracle.py:212,231,234,246 /
port_exposure.py:48,178,183 / replay.py:46,67,155`

### vulture
- evaluate_geometric_region_capacity ✓ 不再 unused (Step I OK)
- evaluate_literal_port_exposure 仍 unused (走 generic multiset)

### bandit Low B101 assert
`lifecycle.py:436,634,802,813 / replay.py:191 / store.py:131` (内部, 短期 defer)

### radon
- validate_port_exposure D(23) — Step J binding 加后升级, 建议拆 3 helper
- validate_component_reach C(19)
- segment_aabb_intersection_t C(15)

### spec drift
1. `state_machine_v2.md:42-45` PoseId Tuple[str,int] vs src str
2. `cut_lifecycle_v2.md:225-241,365-374,740-747` PoseId int + 仍有 symmetry_lift
3. `cut_family_specs/03_port_exposure.md:39-44` direction up/down vs src N/S/E/W
4. `cut_family_specs/02_cutset.md:129-162` evaluate/validator 描述没跟上 enclosure
5. `cut_family_specs/04_component_reach.md:50-56,145-150` commodity_id / blocking_facilities
   写得像 soundness 条件, src 是 geometric-only pass-through

## 最小必修包 (GPT 推荐 v4)

1. **修 F1 duplicate `contributing_groups` P0** (validator gid 去重 + tuple
   demand 校验 + gap 校验)
2. **加 F1 regression test** (`actual demand=70, cap=139, duplicated ->
   reject`)
3. **清 ruff F401** (cosmetic, CI 红)
4. **Phase 1.2 前 strict default 1** + F5-F9 注册 validator test
5. **source_digest 真实施** (覆盖 canonical_rules + candidate_placements +
   instance_to_facility_type + facility_templates + oracle_version)
6. **F2 oracle 上线前 commodity demand registry**

修完 #1 #2 后 Step I/J/K 闭环可重新判定; 在此 P0 修前 Phase 1.1 Step A-K 不能
production GO.
