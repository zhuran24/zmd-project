# B1 round 1 necessity proof: `Q_delta` x membrane x halo

Status: admitted research necessary lemma.  The two standalone recomputations,
their script-bound agreement gate, and the adversarial verdict in this
directory passed before the encoder was started.

This is an upper-ledger research argument.  It does not establish a witness,
attainability, routing feasibility, global optimality, or production
`CERTIFIED` status.

## 1. Fixed facts and notation

Let `R` be a body-empty integer rectangle with width `w`, height `h`, area
`A=wh`, and `S=w+h`.  The strict instance has 3,544 required body cells and 628
active terminal incidences.  The already reviewed power-halo lemma gives at
least nine 2 by 2 pole bodies, so at most

```text
4900 - 3544 - 9*4 - A = 1320 - A
```

body-free cells exist outside `R`.

The 46 boundary facilities force 23 bodies on the left edge and 23 on the
bottom edge.  Their two one-cell gaps give exactly 47 boundary patterns.  In a
fixed pattern `delta`, let `Q_delta` be the 46 distinct active access cells of
those facilities.  A body-empty rectangle with both sides at least six cannot
contain row 0 or column 0, hence its anchor has `x,y >= 1`.

The word active is forced rather than assumed.  The strict raw-output demand is
52, while the only providers have total physical capacity
`46 boundary ports * 1 + 6 protocol-core outputs = 52`.  Feasibility therefore
saturates every boundary port and all six core outputs.  Both recomputations
derive and fail closed on this equality.

For a fixed pattern and rectangle placement define:

- `q = |R intersect Q_delta|`;
- `e` as the number of those `q` boundary terminals whose supporting
  three-cell boundary body has contact length two with the corresponding side
  of `R`.

Because the active boundary port is on the middle body cell, contact length is
three unless its access coordinate is a tangential endpoint of the rectangle
side.  At an endpoint the contact length is exactly two.  Thus `e` is also the
number of boundary partial contacts.

## 2. Refined membrane count

First consider manufacturing and boundary-terminal incidences whose access
cells lie in `R`.  Write their count as `K_MB` and their total side-contact
length as `L_MB`.

For manufacturing contacts, the independently reviewed eight-class table has
full-contact excess 63.  Every partial manufacturing contact can add at most
three over its full-contact allowance.  Across the four rectangle sides there
are at most eight directed endpoint positions, and two partial contacts cannot
use the same position without body overlap.

Each full boundary contact has `(s,a,l,k)=(3,1,3,1)` and contributes
`2k-l=-1`.  Each partial boundary contact has `(3,1,2,1)` and contributes zero.
Moreover, each of the `e` boundary partial contacts consumes one of the eight
endpoint positions.  Therefore the number of manufacturing partial contacts
is at most `8-e`, and

```text
2*K_MB - L_MB
    <= 63 + 3*(8-e) + (-(q-e))
    = 87 - q - 2e.
```

All contact intervals are disjoint on each directed rectangle side, so
`L_MB <= 2S`.  The protocol core contributes at most three outputs into `R`,
and the whole instance has only two active final inputs.  Adding this existing
safe `+5` relaxation gives

```text
U_delta(R)
    = S + 48 - floor(q/2) - e
```

as an upper bound on all active terminal incidences whose access cells lie in
`R`.  The integer identity used here is

```text
floor((87-q-2e)/2) = 43 - floor(q/2) - e.
```

Hence at least

```text
580 - S + floor(q/2) + e
```

terminal incidences have access cells outside `R`.  At most four incidences can
use one such cell.  Combining this fact with the nine-pole free-cell cap yields
the candidate necessary condition

```text
A + ceil((580-S+floor(q/2)+e)/4) <= 1320.       (B1-QMH)
```

Every true feasible layout must satisfy this inequality for its actual
boundary pattern and rectangle placement.  Routing connectivity and component
capacity are otherwise relaxed away.

## 3. The forbidden additive interpretation

The cells in `Q_delta` outside `R` are already active external access cells.
They are not a disjoint second pool that may be added to the membrane cell
lower bound.  If `q_out=46-q` and `N` is the number of other external access
cells, the remaining incidence capacity obeys

```text
external incidences - q_out <= 3*q_out + 4*N.
```

Consequently the sound union lower bound is

```text
q_out + N >= max(q_out, ceil(external incidences/4)).
```

Here the second term is always at least 110 while `q_out <= 46`, so the direct
`Q_delta` union term is completely dominated.  The expression

```text
A + (46-q) + ceil((580-S)/4) <= 1320
```

double-counts the forced boundary access cells and is not an admissible
necessary condition.  It is retained only as a mutation canary.

## 4. Claim and promotion boundary

The lemma admitted by this paper, if both later gates pass, is only
`(B1-QMH)`.  A surviving pattern/rectangle assignment is a relaxation witness,
not a layout.  If the exact band scan retains a `(34,35)` or `(35,34)`
assignment, the certified upper ledger remains `(1190,34)` and no new UNSAT
claim is made.
