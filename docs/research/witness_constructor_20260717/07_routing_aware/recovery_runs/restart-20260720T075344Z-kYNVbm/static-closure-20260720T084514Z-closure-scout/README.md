# Static count-closure reconnaissance

This unique recovery directory contains a pure-stdlib, no-solver, no-router
reconnaissance snapshot.  It is research evidence only.  The JSON rows are
necessary-condition arithmetic and fixed-geometry incidence checks; they do
not establish a local packing, a global layout, routing, a lower-bound
artifact, or optimality.

## Main results

- 123 local observations collapse to 72 component/target catalog rows.
- With periodic `F=(10,5,4)` in c0/c1/c2, fixed c3 `(12,4,3)`, and the known
  c10/c11 alternatives, every one-new-target closure is a c5 target.  The two
  cleanest identities were c5 `(13,4,4)` (313 body cells, 15 residual) and
  `(11,5,4)` (320 body cells, 8 residual).  All queried phases for both are
  exact `INFEASIBLE`; this is scoped to those local models and pole phases.
- The exhaustive two-new-local-target integer catalog contains 5,384 rows;
  5,132 remain after filtering targets whose discovered observations are all
  exact `INFEASIBLE`.  Rows are sorted by minimum residual cells, maximum local
  active incidence, unexplored count, total residual, then count-distance.
- Moving the three c5 poles to x=67 or x=68 does not expand its 328-cell
  component in any audited y phase.  It only changes candidate incidence.
- c5 baseline-count `(10,4,4)` is exact `INFEASIBLE` at x=64, x=65, and x=66,
  dy=0 in the discovered query artifacts.
- Moving c10 poles `(65,41),(65,53)` to x=66 is collision-free, preserves
  212 component cells and 40 gateways, and expands all three static candidate
  domains.  Target `(9,2,2)` has 33 residual cells there, but is unqueried.
- Moving both c11 poles `(5,41),(5,53)` to x=6 is invalid before packing: the
  pole at `(6,41)` occupies protected cells `(7,41),(7,42)`.  The report also
  includes a collision-free y=53-only control, without a feasibility claim.

`static_closure_report.json` is the compact handoff.  The observed catalog and
the complete pair enumeration are separate so the compact report stays easy
to inspect.  `enumerate_static_closure.py` exclusively creates all JSON
outputs and does not import a constraint solver.
