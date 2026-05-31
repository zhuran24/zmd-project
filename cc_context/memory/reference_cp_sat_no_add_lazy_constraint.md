---
name: cp-sat-no-add-lazy-constraint
description: 2026-05-23 OR-Tools 9.15 CP-SAT Python 不支持 model.AddLazyConstraint. Phase 1.3 必走 LBBD 外循环 (solve → verify → generate cut → rebuild/resolve), 不在 Python callback heavy separation. Gemini math review meta-audit verdict.
metadata:
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-23 Gemini math review meta-audit catch: 原 Gemini 建议用 `model.AddLazyConstraint(...)` 做 CP-SAT lazy separation. 但项目当前 OR-Tools 9.15.6755 Python `cp_model.CpModel()` **没有此 API**.

## 验证

```python
import ortools.sat.python.cp_model as cp_model
model = cp_model.CpModel()
hasattr(model, "AddLazyConstraint")  # False
```

OR-Tools 9.15 CP-SAT Python 暴露的: `Add` / `AddLinearConstraint` / `AddBoolOr` / `AddBoolAnd` / `OnlyEnforceIf` / `AddAssumption` / `AddImplication` / `AddMaxEquality` / `AddMinEquality` / `AddNoOverlap` / ... — **不含** lazy.

C++ 层有 `SearchObserver` / custom propagator API, Python 绑定不完整, 投资 ≥ 1 周做 wrapper.

## Phase 1.3 attach 路径 verdict

**走 LBBD 外循环** (跟现 benders_loop 一致):
```
master solve
→ independent subproblem verification
→ generate cut object
→ validate/replay/scope-check
→ translate active cuts into normal CP-SAT constraints
→ solve again
```

3 个 sub-route Phase 1.3 P1.3A spike 决:
1. **Solve-rebuild** (推荐): 每轮 master.solve 前把 active cut 转 `Add` 注入新 model
2. **C++ propagator hook**: OR-Tools C++ 层 custom propagator, Python 绑定不完整 (投资高)
3. **Hard-constraint rebuild**: cut 全 hard, 每加新 cut rebuild model (兼容性最好但 build cost 大)

Spike GO 标准: 至少一条路径在 prod-scale (266 instance + ~10K cut) wall-clock 退化 < 50%.

## CP-SAT family translation (per Gemini integration notes)

| Family | CP-SAT shape |
|---|---|
| F3/F5/F7 literal | `sum(present_lits) <= len(present_lits)-1` |
| F9 area envelope | `sum(overlap_area[p,W] * x[g,p]) <= max_allowed_area` |
| F6 shape packing | `sum(x[g,p] for p in pose_set) <= packing_upper_bound` |
| F2 capacity | `sum(crossing_demand_lits) <= cut_capacity`, 不行 fallback F5 |
| F4 reachability | 优先转 F2 / F5; 纯 BFS cut 无线性 separator cert 则 fallback |

## Ghost-bound constraints

cut 只对某 ghost candidate valid → 不能无条件 attach:
- `constraint.OnlyEnforceIf(ghost_lit)` (CP-SAT 支持)
- 或 per-ghost rebuild model

## Don't do

- ❌ `model.AddLazyConstraint(...)` — API 不存在
- ❌ Python callback heavy separation — wrong place for mathematical proof reconstruction (慢, 易 thread-safety bug, ortools 不保证)

## Refs

- `docs/research/p3_b_design_v2_20260521/external_review/gemini_math_review_bundle_20260523/notes/CP_SAT_INTEGRATION_NOTES.md` (source)
- `docs/项目说明/09_phase_1_3_plan.md` P1.3A spike
- `docs/项目说明/05_open_questions.md` Q10 verdict
- [[phase-1-1-go-blessed]] — exit hardening delivery 含此 finding
