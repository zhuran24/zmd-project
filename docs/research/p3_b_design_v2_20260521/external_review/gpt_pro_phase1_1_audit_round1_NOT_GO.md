# GPT pro Phase 1.1 audit round 1 — verdict NOT GO

输入 pkg: `phase1_1_gpt_pro_review_v1.zip` (commit `868bef7`) + `zmd_deps_v3.zip`
+ chat prompt (4 段 A/B/C/D + 3 armor 简化版).

GPT pro 跑了 pytest 139 PASS + README smoke + ruff + mypy --strict + vulture
+ bandit + radon, **构造反例 falsify validator**.

## Verdict

**Phase 1.1 NOT GO** — 4 critical blocker (F1 demand spec-data drift + F2 fake
partition + F3 cert/literal mismatch + F4 fake commodity) 全实测复现.

## 4 Critical Blockers

### Blocker 1: F1 demand_R 不满足 spec §2b 的 P(g) ⊆ R

src 推 contributing group 只看 `placement_rule_for_group` (oracle.py:100-110,
family.py:128-150), 不验 group 真 pose domain 是否全 ⊆ R.

真数据反例:
- `boundary_io` 46 instance, placement_rule="left_or_bottom_boundary"
- 但 candidate_placements 54 boundary_storage_port pose 中 14 个 occupied 完全
  不在 union R `{(x,0)} ∪ {(0,y)}` 内
- 反例 1: `viewer::boundary_required_output_source_ore_005` 占 (31,69)/(32,69)/(33,69)
- 反例 2: `viewer::boundary_required_output_source_ore_017` 占 (69,43)/(69,44)/(69,45)

所以 demand_R=46×3=138 不是 R 内严格下界, F1 cut "cap=137 demand=138 gap=1"
是 false positive risk — 真 production 时可能误剪合法状态.

### Blocker 2: F3 validator 不验 cert ↔ literal 绑定

`port_exposure.py:60-65` 解构 `blocking_pose_id` 但不用 (vulture catch:
`port_exposure.py:63 blocking_pose_id` unused).

validator 只验 `cell_owner[front_cell] == (blocking_group, blocking_slot)`
不验 cut.literals 是否真含 cert 内 (facility_group, facility_pose_id) +
(blocking_group, blocking_pose_id).

反例: cert 证 A pose 被 block, cut.literals 写 C pose, validator `ok` +
evaluator `True`. → cert 证明的 cut object 不一致, 拿 A 证剪 C.

### Blocker 3: F2 validator 缺 A ∪ B == free_cells partition check

只验 `A ∩ B == ∅` + `cut_size` recompute + `commodity_demand > cut_size`.
没验 partition 覆盖 graph universe.

反例: A={(0,0)}, B={(60,60)}, cut_size=0, commodity_demand=1 — validator `ok`
但 A∪B 只 2 cell vs grid 4900 free_cells. fake partition.

### Blocker 4: F4 validator 不验 commodity_id 存在 production data

只验 src/sink component disjoint + 当前 BFS 仍 disconnect.

反例: commodity_id="fake_commodity_not_in_canonical_rules" — validator `ok`.
任意挑 2 不连通 cell 就能伪造 infeasible cut.

## 静态质量 finding

- **ruff**: 12 F401 在 tests unused import (cosmetic, 不阻断)
- **mypy --strict**: 29 errors / 10 files (我 commit 时只 `--ignore-missing-imports`)
- **vulture**: `port_exposure.py:63 blocking_pose_id` unused (跟 Blocker 2 同根)
- **bandit**: 14 low `B101 assert_used` (production `python -O` 删 assert,
  validator `assert cut.cert is not None` 类失效)
- **radon**: 平均 A 3.98, 多个 C 级热点 (max `segment_aabb_intersection_t` C(15))

## Spec drift

- `cut_lifecycle_v2.md` 还写 PoseId=int + symmetry_lift (src 已改 str + 9 family)
- `cut_family_specs/01` 表 region_kinds 没列 left_or_bottom_union (fixture 后
  有引用)
- F2 spec 写 partition / min-cut witness, src 没做
- F3 spec 写 up/down/left/right, src 用 N/S/E/W
- F4 spec 写 component bitset + separator + commodity_route assumption, src 没验

## 必修 (GPT 列 6 项)

1. F1 不许从 placement_rule 直接推 P(g) ⊆ R — 查真 pose_domain
2. F3 validator 验 cert.facility/blocking pose_id ↔ cut.literals 一致 +
   blocking_pose_id 必须 match state.selected_poses[slot]
3. F2 加 A ∪ B == free_cells + recomputed cut_edges set + commodity demand 重算
4. F4 加 commodity_id 存在 + cert bitset == recomputed BFS + separator 真 blocked
5. Phase 1.2 前关 silent validator gap (strict registration test)
6. source_digest 真实施 + spec drift cleanup
