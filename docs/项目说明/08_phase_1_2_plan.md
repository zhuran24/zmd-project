# 08 — Phase 1.2 plan (P1.2A entry ✅ done + P1.2B-F5/F6/F7/F8/F9)

> **2026-05-23 v2 命名更新**: 原 plan 把 `P1.11` 同时用作 "入门 7 项" 跟 "F5 pattern_nogood", 误导. v2 拆: **P1.2A** 入门 (entry hardening, 已落地) + **P1.2B-F{5,6,7,8,9}** 各 family.

## P1.2A — entry hardening ✅ DONE (2026-05-23 exit hardening delivery)

8 项 (7 原 plan + 1 新发现) 落地, 详 [06_current_status.md](06_current_status.md) + [07_historical_review.md §5.12](07_historical_review.md):

1. ✅ strict gate `EXACT_FAMILY_VALIDATOR_STRICT="0"→"1"`
2. ✅ spec drift 全清 (PoseId / family list / F3 direction / F2/F4 cert schema)
3. ✅ source_digest 真 sha256
4. ✅ ghost_rect tuple `(x, y, x_span, y_span)` lock + 非方形 fixture
5. ✅ mypy strict 37 → 0
6. ✅ radon D → max C(15)
7. ✅ F3 `evaluate_literal_port_exposure` 删
8. ✅ `on_ghost_rect_changed` test stub 收紧 (`unsafe_test_replay_fn` + double flag)

测试: 178 cuts pass (172 + 6 regression).

## P1.2B-F5 — pattern_nogood (优先级最高)

**为啥优先 F5**: F5 是 lifecycle step 2 minimize 的最小闭环 + literal path 兜底. 没 F5, LBBD 重复踩同一坑; F5 不 time-box, MUS/QuickXplain 拖死; F5 不 multiset, 132 集群拖爆.

**但**: F5 是**fallback 不是主力**. F5 ratio > 50% = stop-ship (per Gemini math review meta-audit). F9 才是主力几何 lift.

实施要求 (per Phase 1.2 P0 acceptance checklist A, [12_go_criteria.md §8.1.x](12_go_criteria.md)):
- 新模块: `src/cuts/families/pattern_nogood.py` + `oracles/pattern_nogood_oracle.py` + `helpers/bounded_core_minimizer.py`
- bounded core minimizer 合同:
  - 输入: `assignment: tuple[LiteralAssignment, ...]` + `oracle(core) -> INFEASIBLE | FEASIBLE | UNKNOWN | TIMEOUT` + `budget: max_calls, max_seconds`
  - 输出: `CoreMinimizeResult(core, is_minimal, calls, stopped_reason)`
  - 硬规则: full assignment 先 verify infeasible; 每次删 literal 后只有 oracle INFEASIBLE 才收缩; TIMEOUT/UNKNOWN/exception fail-closed (保留旧 core); 返非最小 core OK, 返未验证 core 禁止
- cert 必含: `cert_kind="bounded_deletion_core"` + `sub_problem_oracle_name` + `oracle_cert_hash` + `forbidden_pose_pattern` + `core_minimization` (size_before/after, calls, stopped_reason, last_verified)
- apply-to-master: `sum(present(g, p) for literal in core) <= len(core) - 1`. pose-bool delegate 用 `x_vars[(g, p_idx)]`. coordinate delegate 走 `_pose_present_literal(...)`. ghost-bound 用 `OnlyEnforceIf(condition_lits)` 或 per-ghost rebuild

测试覆盖 (red fixture, [15_workflow_testing.md §21.7](15_workflow_testing.md)):
- `F5-timeout-last-verified-core` — timeout 返 last verified, 不返未验证 partial
- `F5-132-group-anonymous` — slot/index permutation 触同一 cut
- `F5-cardinality-unsound-routing` — routing failure 不 auto-lift cardinality

## P1.2B-F6 — shape_packing_hall

实施要求:
- 数学根据: Hall's marriage theorem (interval graph)
- cert 必含可独立验证 Hall violation witness (e.g. `S` 跟 `N(S)`, 且 `|N(S)| < |S|`); 或跑精确 matching / max-flow
- **greedy 失败不能当不可行证明** (proof obligation 加严, per v2 plan §2.4)
- validator 重算 Hall witness

测试覆盖: basic count violation + local Hall violation + false-positive attack 三类.

## P1.2B-F7 — power_hitting_set

实施要求:
- 数学根据: set cover NP-hard + LP relaxation
- cert 表达 (二选一): 证明 "无可行覆盖" 或 "必须包含某些 pole"
- **LP relax / greedy 只能 oracle hint**, validator 必验安全下界 / dual cert
- F7 是 literal family, 进 `evaluate_literal_multiset`

## P1.2B-F8 — power_grid_reach

实施要求:
- 数学根据: Liang-Barsky line-segment AABB intersection
- **F8 mode 锁 geometric** (cert 可引用 pole group/pose 上下文, lifecycle body 不走 literal path, [04_design_invariants §18](04_design_invariants.md))
- 复用 `ghost_geometry.py` Liang-Barsky helper
- 退化 case 必覆盖: degenerate segment (零长度) / corner touch / axis-aligned / endpoint inside / 非方形 ghost rect

## P1.2B-F9 — density_envelope (**area-only**, PROJECT_LOCK 锁)

实施要求 (per Phase 1.2 P0 acceptance checklist B):
- 新模块: `src/cuts/families/density_envelope.py` + `oracles/density_envelope_oracle.py`
- generator **只接受** `area_capacity_overflow` witness, **拒绝** `routing_overflow` / `binding_overflow` / `pcr_cut_overflow`
- cert 必含 `max_allowed_area` + `window_rect` + `group_id` + `oracle_assignment_witness` + `ghost_rect_repr`
- evaluator: `sum(|pose_cells ∩ W|)`, 不是 instance count / origin / all-in-window
- validator 同 area-based rule
- Step 8: `sum(area_overlap[p, W] * x[g, p]) <= max_allowed_area`
- 等号不 cut, 严格 `>` 才 cut (proof obligation, per v2 plan §2.4)
- **`max_density` 必是安全上界**, 不能经验估计

测试覆盖 (red fixture):
- `F9-reject-routing-overflow` — generator 拒 routing overflow witness
- `F9-any-overlap-overcount` — 历史 FP: any overlap → whole facility
- `F9-origin-in-window` — 历史 FP: origin in W → whole facility
- `F9-all-in-window-FN` — 历史 FN: edge partial 漏算

morphology safe/unsafe 详 [02_mathematical_foundations §3.9](02_mathematical_foundations.md).

## P1.2B-F2/F4 容量桥接 — Dinic / node-split min-cut

**为啥 F2/F4 重要**: 当前 generator 都是 stub (validator/evaluator 已 land 但 generator 未产真 cut). F4 BFS 只答 "有没有路", F2 才答 "路够不够宽". 这是容量盲区核心.

实施要求 (per Phase 1.2 P0 acceptance checklist C):
- F4 generator: 不再为 disconnected commodity 返 `[]`, 找真 BFS 隔断 cert (separator_cells)
- F2 generator: Dinic / max-flow 跨 partition demand 检查
- **node-split mode**: 如果 cell 容量重要 (每 cell 只能承载有限条 belt/物流), 拆 `v_in → v_out cap=cell_capacity`, 相邻 `u_out → v_in cap=edge_capacity`. min-cut 才能同时表达 cell 容量 + 边通行
- cert: `CutsetCert(capacity_model_version, side_a_bitset_b64, side_b_bitset_b64, cut_edges_or_nodes, cut_capacity, commodity_demand, contributing_commodities, witness_blob_b64)`
- validator 独立重建 node-split graph, 重算 min-cut, 不信 generator 数字
- F4 ⊆ F2 (容量 0 特例); 实施可 F4 先跑, 不触发再跑 F2 min-cut

测试覆盖:
- `F2-narrow-corridor-capacity` — BFS connected 但 capacity < demand
- `F4-disconnected-zero-capacity` — 完全无 path, F4 先触发

## family-level enable matrix (per v2 plan §5)

进 P1.3 前每 family 独立开关, 不一键全开:

| Family | Phase 1.2 单测 | P1.3 shadow | P1.3 true attach | 备注 |
|---|---:|---:|---:|---|
| F1 region_capacity | ON | ON | ON | 已最稳 |
| F2 cutset | ON | ON | guarded | 生产 route_id schema 未定前谨慎 |
| F3 port_exposure | ON | ON | guarded | active_port_witness 仍是 Phase 1.5+ |
| F4 component_reach | ON | ON | guarded | commodity route schema 未定前谨慎 |
| F5 pattern_nogood | after P1.2B-F5 | shadow first | guarded | 依赖 infeasible witness, fallback role |
| F6 shape_packing_hall | after P1.2B-F6 | shadow first | guarded | 依赖 Hall witness, 不准 greedy 当 proof |
| F7 power_hitting_set | after P1.2B-F7 | shadow first | guarded | NP-hard, LP relax 只 hint |
| F8 power_grid_reach | after P1.2B-F8 | shadow first | guarded | mode 锁 geometric |
| F9 density_envelope | after P1.2B-F9 | shadow first | guarded | area-only, 上界必安全 |

## Phase 1.2 实施顺序推荐

1. **P1.2B-F5** (优先, 是 LBBD fallback 兜底, 没它整 pipeline 不安全)
2. **P1.2B-F9** (主力几何 lift, 防 F5 ratio 超 50%)
3. **P1.2B-F2/F4 generator** (填容量盲区)
4. **P1.2B-F6** (Hall theorem refinement)
5. **P1.2B-F7** (power hitting set)
6. **P1.2B-F8** (power grid reach)

每 family land 后 Gemini per-commit cross-check, 5 family 全 land 后 GPT pro batch audit (大节点).

---
