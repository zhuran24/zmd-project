# B1 conditional halo: mathematical adversarial verdict

| Document property | Current value |
|---|---|
| Document nature | Mathematical adversarial verdict for the conditional-halo geometry |
| Evidence cutoff | `2026-07-22` |
| Status | **PASS — 18/18 attack surfaces confirmed** |
| Scope | `geometry_only_pre_encoder` |

No counterexample was found in the admitted geometry. The verdict covers the
necessity paper, the declarative doubled stencil, and the two authoritative
full-coordinate recomputations. It does not admit an encoder, a translated
OPB, a solver result, or an upper-bound improvement.

## Admitted statement

For every body-empty rectangle `R` in a feasible layout, with `q` ranging over
all selected power poles,

```text
sum_q C2_q(R) >= 6650,
```

where `C2_q(R)` is obtained by translating the doubled 14-orbit stencil,
clipping it to the 70x70 grid, and removing the cells of `R`.

The review independently confirmed the strict coordinate and pole domains,
the distinction between the power-coverage square and the dual stencil, the
14-orbit expansion, the 840 local inequalities, the powered-area ledger, the
facility-to-pole assignment argument, and the all-selected-poles quantifier.
It also confirmed that cross-pole stencil overlap needs no subtraction and
that omitting optional 3x3 storage boxes is a safe relaxation.

## Recomputed evidence

The direct range-add and independent prefix implementations agree on:

- 2,520 ceiling rectangles;
- 4,761 pole anchors;
- 11,997,720 rectangle/pole pairs;
- 3,170,162 pole-body/rectangle intersections;
- canonical corpus digest
  `fe8da9696c2c7604f1153e4691ccdfe8e35b67a30adf54d301b421b113d096b2`;
- an empty `corpus_errors` list.

The actual-pole ledger remains a separately identified prerequisite. It gives
`P>=9`, and at the ceiling the lower ledger is 1,318 for nine poles and 1,322
for ten poles. Thus exact nine is derived at the ceiling; it is not substituted
for the theorem's all-selected-poles quantifier.

## Claim boundary

This verdict admits only a research necessary condition. It proves no witness,
attainability, routing feasibility, upper-bound improvement, global
optimality, or production `CERTIFIED` status. Encoder translation,
control/treatment attribution, diagnostic completion, and any complete UNSAT
prefix require their own later admissions.
