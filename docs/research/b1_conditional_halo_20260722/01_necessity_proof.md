# B1 round-2 conditional-halo necessity proof

| Document property | Current value |
|---|---|
| Document nature | Necessity proof for the B1 round-2 conditional-halo geometry |
| Evidence cutoff | `2026-07-22` |
| Status | **PROVED — mathematical premise for geometry admission** |
| Scope | `geometry_only_pre_encoder` |

This paper establishes a necessary inequality for every feasible layout. It is
an upper-ledger research lemma. It does not establish a witness, attainability,
routing feasibility, a smaller upper bound, global optimality, or production
`CERTIFIED` status.

## 1. Coordinates and the clipped conditional capacity

Let

```text
G = {0,...,69} x {0,...,69}
```

be the grid-cell set, with zero-based coordinates, southwest origin, `x`
increasing east, and `y` increasing north. A power-pole anchor
`q=(q_x,q_y)` occupies the four cells `q+{0,1}²`, so both anchor coordinates
are in `0,...,68`. In this round, the summation index `q` always denotes a
power pole. The boundary-access set from B1 round 1 remains named `Q_delta`;
its rectangle count is written `a_delta(R)=|R intersect Q_delta|`.

The power-coverage square relative to a pole anchor is `[-5,6]²`. Coverage
means that at least one powered-facility body cell intersects the square after
translation and clipping to `G`. This coverage square is not the dual halo
stencil.

The doubled dual stencil `lambda2` is defined by the 14 orbit entries in
[`conditional_halo_stencil_v1.json`](conditional_halo_stencil_v1.json). For
offset `(d_x,d_y)`, its orbit key is

```text
(max(|2*d_x-1|, |2*d_y-1|), min(|2*d_x-1|, |2*d_y-1|)).
```

The expanded stencil has 96 nonzero cells and doubled total weight 792. Let
`R=(x,y,w,h)` denote the half-open body-empty cell set
`[x,x+w) x [y,y+h)`. Define the boundary-clipped capacity

```text
C2_q(R) = sum(lambda2(c-q) for c in G minus R),
C_q(R)  = C2_q(R)/2.
```

The order of operations is part of the definition: translate the stencil,
clip it to `G`, then remove the cells in `R`.

## 2. Local halo inequality

The strict instance has 219 mandatory powered manufacturing facilities with
total body area 3,325. Their possible oriented body dimensions are `3x3`,
`5x5`, `6x4`, and `4x6`.

Fix a pole at the origin. Consider an oriented manufacturing body that
intersects the pole's `[-5,6]²` coverage square and does not overlap the pole's
2x2 body. Direct enumeration checks all such placements:

| Body dimensions | Checked placements |
|---|---:|
| `3x3` | 180 |
| `5x5` | 220 |
| `6x4` | 220 |
| `4x6` | 220 |
| **Total** | **840** |

For every checked placement `F`, the 14-orbit certificate satisfies

```text
2*|F| <= sum(lambda2(c) for c in F).
```

The weights are nonnegative. Facilities and poles in a feasible layout have
nonoverlapping bodies, so every actual pole/facility coverage relation is one
of these checked local placements, translated without changing the
inequality.

## 3. All-selected-poles conditional inequality

For each mandatory powered facility, choose one selected pole whose coverage
square intersects its body. If several poles cover it, choose any one. This
partitions the 219 facilities by their chosen pole.

For a fixed selected pole `q`, bodies assigned to it are mutually disjoint.
They are contained in `G minus R` because `R` is body-empty. Summing the local
inequality over the bodies assigned to `q` therefore gives

```text
2*(area assigned to q)
    <= sum(lambda2(c-q) over their disjoint body cells)
    <= C2_q(R).
```

Summing this inequality over the chosen poles and then adding any selected but
unchosen poles, whose capacities are nonnegative, yields

```text
sum(C2_q(R) for every selected pole q) >= 2*3325 = 6650,
```

or, in undoubled units,

```text
sum(C_q(R) for every selected pole q) >= 3325.       (B1-CH)
```

The quantifier is every selected pole. Replacing it by "any nine poles" is not
valid when a layout selects more than nine poles.

Stencils belonging to different poles may overlap. No overlap subtraction is
needed: each facility is assigned to one pole, while each pole has its own
upper-bound chain. Counting the same empty grid cell in two different pole
capacities can only weaken `(B1-CH)`; it cannot invalidate it. Optional powered
3x3 storage boxes are omitted, which is also a safe relaxation.

## 4. Actual-pole-count area ledger

Let `P` be the actual number of selected poles. The 3,544 mandatory body cells,
the `4P` pole-body cells, and `R` are disjoint. Optional auxiliaries can only
consume more cells. B1 round 1 independently established that the number of
distinct body-free access cells required outside `R` is at least

```text
ceil((580-w-h+floor(a_delta(R)/2)+e_delta(R))/4),
```

where `e_delta(R)` is the number of tangential endpoint partial contacts. Thus
every feasible layout satisfies

```text
w*h
  + ceil((580-w-h+floor(a_delta(R)/2)+e_delta(R))/4)
  + 4*(P-9)
  <= 1320.                                           (B1-ACTUAL-P)
```

The local halo certificate also gives `3325 <= 396P`, hence `P>=9`.
At either ceiling dimension `(34,35)` or `(35,34)`, nonnegativity of
`a_delta` and `e_delta` makes the left side of `(B1-ACTUAL-P)` at least
`1318+4*(P-9)`. Consequently every ceiling survivor has exactly nine poles.
This is a derived ceiling diagnostic, not an axiom and not a replacement for
the all-selected-poles inequality.

## 5. Promotion boundary

`(B1-CH)` may enter a research encoder only after two independent full-coordinate
recomputations agree and a geometry-only adversarial review confirms this
paper. A satisfiable encoded assignment remains a relaxation assignment, not
a facility layout. An upper-ledger improvement additionally requires a
complete machine-verified UNSAT prefix under the separately admitted
translation and proof gates.
