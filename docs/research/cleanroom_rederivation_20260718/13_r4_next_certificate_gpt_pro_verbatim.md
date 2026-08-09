# R4 next upper certificate

## Claim

For the byte-locked strict instance with SHA-256
`e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c`,
every feasible layout has objective at most

**U = (1188, 22)**

in lexicographic order `(empty-rectangle area, shorter side)`.

The certificate is a sound relaxation. It does not claim attainability of
`(1188,22)`, produce a witness, or establish a lower bound.

## Lemma 1: inherited body, power, and ordinary membrane accounting

The required bodies occupy 3,544 cells. Powered required bodies occupy 3,325
cells. The doubled local halo weights have total 792, every one of the 840
eligible powered-body placements has weight at least twice its body area, and
therefore one pole can be charged at most 396 powered-body cells. Hence at
least nine 2x2 poles are required. Required bodies plus nine pole bodies occupy
at least 3,580 cells.

For a body-free rectangle of dimensions `w x h`, set `S=w+h`. The ordinary
terminal membrane calculation reconstructed from the instance has full-contact
excess 63 and endpoint increment at most 3. At most eight contacts cross side
endpoints. Manufacturing and boundary-port terminals with access in the
rectangle are therefore at most `S+43`; the protocol core and two final inputs
add at most five. Thus at most `S+48` of the 628 active terminal incidences have
access cells in the rectangle.

## Lemma 2: 110 marked interior-side terminals

Call a port an interior-side port when its body cell is not a corner of its
rectangular body. On a port-bearing side, at most two active ports can be body
corners. For each manufacturing input or output side, mark
`max(0, active_count-2)` active interior-side terminals. The instance forces 58
such manufacturing marks.

The 46 boundary ports and all six protocol-core output slots are needed to
supply the exact 52 raw outputs. Every one of those 52 ports is an interior-side
port. Mark them too. This gives 110 marked active terminals.

For every marked side class, if `r` marks lie on a side of length `s`, then
`2r <= s`; the largest `r` is 3 and the largest marked side length is 9.

## Lemma 3: marked membrane

Assume the rectangle's shorter side is at least 9. A full contact interval of
length `s` exposes at most `r <= s/2` marks. A partial contact of overlap length
`ell` can expose at most `min(r,ell)` marks, so its doubled excess over half
length is at most `r <= 3`. There are at most eight endpoint-crossing contacts.
If `J` marked terminals have access cells in the rectangle, then

`2J <= 2S + 8*3`, hence `J <= S+12`.

## Lemma 4: local access-cell capacity

For an access cell, let `t` be the number of adjacent active terminal
incidences and `m` the number among them that are marked interior-side
terminals. Then

**`t + m <= 4`.**

To see this, consider the four possible neighboring body cells around the
access cell. Two bodies in perpendicular directions overlap in their diagonal
quadrant unless at least one incident terminal is at the appropriate body
corner. A corner terminal can clear at most one such quadrant; an
interior-side terminal clears none. With four incident terminals, four
quadrants must be cleared, so no incident terminal can be marked. With three
incident terminals, two quadrants must be cleared, so at most one can be
marked. The cases with at most two terminals satisfy the inequality directly.

Let `N` be the number of distinct outside-rectangle access cells. Summing the
local inequality gives

`4N >= T_out + M_out`,

where `T_out` is the number of all active terminal incidences outside the
rectangle and `M_out` is the number of marked incidences outside it.
Consequently, for shorter side at least 9,

`N >= ceil(((628-(S+48)) + (110-(S+12)))/4)`.

The ordinary unmarked access-cell bound is retained as well, and the stronger
of the two is used.

## Lemma 5: no admissible rectangle has a side of 70

A length-3 boundary body can be packed at most 23 times on either supported
70-cell boundary. There are 46 required boundary ports, so every feasible
layout has exactly 23 left-boundary bodies and exactly 23 bottom-boundary
bodies. Each supported boundary is therefore body-occupied in 69 of its 70
cells. An admissible body-free rectangle spanning all 70 rows or all 70 columns
would contain at least six cells of one of those supported boundaries, which
is impossible.

## Final scan

For each normalized dimension pair `6 <= w <= h <= 70`, the checker:

1. applies the ordinary membrane/access bound;
2. when `w >= 9`, also applies the marked-terminal access bound;
3. rejects `h=70` by Lemma 5; and
4. tests whether the rectangle area, the 3,580 mandatory body cells, and the
   required outside access cells fit in the 4,900-cell grid.

The inherited relaxation reproduces `(1190,34)`, attained in that relaxation
by `34x35`. The marked-terminal step removes `34x35`, leaving `(1190,17)` via
`17x70`. Boundary packing removes that full-span case. The lexicographically
largest remaining relaxed dimension is `22x54`, giving **`(1188,22)`**.

## Checker

Run:

```bash
python3 r4_next_certificate.py problem_instance.json
```

The checker is 160 physical lines, uses only the Python standard library, and
contains assertions for every numerical value used above.
