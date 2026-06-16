# CP-SAT Integration Notes for B Design v2 Cuts

## Key point

Do not implement Gemini's `AddLazyConstraint` suggestion for the current CP-SAT path.

In the uploaded dependency package, OR-Tools is `9.15.6755`; `cp_model.CpModel()` exposes `Add`, `AddLinearConstraint`, `AddBoolOr`, `OnlyEnforceIf`, `AddAssumption`, etc., but not `AddLazyConstraint`.

The project should keep this rhythm:

```text
master solve
→ independent subproblem verification
→ generate cut object
→ validate/replay/scope-check
→ translate active cuts into normal CP-SAT constraints
→ solve again
```

## Family translation sketch

| Family | CP-SAT shape |
|---|---|
| F3/F5/F7 literal | `sum(present_lits) <= len(present_lits)-1` |
| F9 area envelope | `sum(overlap_area[p,W] * x[g,p]) <= max_allowed_area` |
| F6 shape packing | `sum(x[g,p] for p in pose_set) <= packing_upper_bound` |
| F2 capacity | `sum(crossing_demand_lits) <= cut_capacity`, if demand can be represented; otherwise generate F5 fallback |
| F4 reachability | Prefer conversion to F2 or F5 unless a linear separator certificate exists |

## Ghost-bound constraints

If a cut is valid only under a ghost candidate, do not attach it unconditionally.

Use one of:

```python
constraint = model.Add(...)
constraint.OnlyEnforceIf(ghost_lit)
```

or rebuild a per-ghost model where that ghost is fixed.

## Do not do this

```python
# Not available on current CP-SAT Python model
model.AddLazyConstraint(...)
```

Also avoid heavy Python callbacks for separation. They are the wrong place for independent mathematical proof reconstruction.
