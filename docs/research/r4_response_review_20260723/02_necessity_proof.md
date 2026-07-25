# R4 `(1188,22)` candidate: local necessity proof

**Document nature:** research-level paper proof for response admission  
**Cutoff date:** 2026-07-23  
**Terminal status:** `PASS` for the necessity layer only  
**Authority response run:** `.artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-20260723T023657Z-R4resp-357f260d`

This document reconstructs the proposed upper-bound inequality from the
byte-locked strict instance. It does not run or trust the external Python
attachment. The result admits `(1188,22)` as input to a later B1
encoder-design task; it does not change the project ledger, which remains
`U=(1190,34)` and `L=absent`.

## Semantics

Let `R` be an axis-aligned rectangle containing no facility or pole body cell.
Transport components and active terminal access cells may lie in `R`. Normalize
its dimensions as `6 <= w <= h <= 70`, and write `S=w+h`.

The strict instance fixes 628 active facility-terminal incidences. For an
access cell outside `R`, let `t` be the number of active incidences using it.
For the marked subset defined below, let `m` be the number of marked
incidences using that cell. Let `N` be the number of distinct outside access
cells.

## Inherited body, power, and ordinary membrane bounds

The 266 required bodies occupy 3,544 cells. Powered required bodies occupy
3,325 cells. The independently reconstructed 14-orbit nonnegative halo
stencil has doubled total weight 792. Every one of the 840 eligible relative
placements of a powered body receives at least twice its body area, so one
pole can cover at most 396 powered-body cells in the charging argument.
Consequently

`P >= ceil(3325/396) = 9`.

Each pole body occupies four cells. Because `R` is body-cell empty, required
bodies and the first nine pole bodies consume at least

`3544 + 9*4 = 3580`

cells outside `R`.

For manufacturing bodies and boundary ports, the strict `(side length,
maximum active side count, multiplicity)` table is:

| side | active | multiplicity |
| ---: | ---: | ---: |
| 3 | 1 | 155 |
| 3 | 2 | 12 |
| 3 | 3 | 11 |
| 5 | 1 | 32 |
| 5 | 2 | 17 |
| 6 | 3 | 32 |
| 6 | 4 | 3 |
| 6 | 5 | 3 |

A body-disjoint rectangle cannot contact two different sides of the same
solid rectangular facility. Full contacts therefore have total doubled
excess 63 over half-density. A partial contact crosses an endpoint of a
directed rectangle side. There are at most eight such contacts, and each adds
at most three more doubled units. Hence their 87 total doubled excess units
give at most `S+43` manufacturing and boundary-port incidences inside `R`.
The protocol core contributes at most three output incidences from one of its
two opposite output faces, and the instance has only two final-input
incidences. Thus

`T_in <= S+48`

and

`T_out >= 628-(S+48) = 580-S`.

## The 110 marked incidences

On each manufacturing input or output side, at most two physical ports occupy
body corners. Mark `max(0, active_count-2)` necessarily active noncorner
incidences. Recomputing every operation group gives 58 manufacturing marks.

The strict raw-output demand is exactly 52. Its only provider slots are the 46
required boundary-port outputs and the six protocol-core outputs. There are
exactly 52 such slots, all are noncorner, and exact port binding therefore
activates every one. Marking them produces

`M = 58+52 = 110`.

The complete marked-side census is:

| side | marks | side occurrences |
| ---: | ---: | ---: |
| 3 | 0 | 253 |
| 3 | 1 | 57 |
| 5 | 0 | 98 |
| 6 | 0 | 38 |
| 6 | 1 | 32 |
| 6 | 2 | 3 |
| 6 | 3 | 3 |
| 9 | 3 | 2 |

Every class satisfies `2r <= s`; the largest mark count is three and the
largest marked side is nine.

## Marked membrane

Assume `w>=9`. Contact intervals on one directed side of `R` are disjoint,
because two facilities sharing a contact cell would share the body cell just
outside it. A full contact of length `s` exposes at most `r<=s/2` marks. A
partial contact of overlap length `ell` exposes at most `min(r,ell)` marks, so
its doubled excess over `ell` is at most `r<=3`.

Every partial contact crosses a directed side endpoint. Body nonoverlap permits
at most one crossing contact at each of the eight directed endpoints, so the
total endpoint allowance is 24 doubled units. If `M_in` marked incidences have
access cells in `R`, then

`2*M_in <= 2*S+24`,

or

`M_in <= S+12`.

Therefore `M_out >= 110-(S+12)=98-S`.

## Local access-cell capacity

An access cell has four orthogonal neighboring body positions. For `t<=2`,
`t+m<=4` follows from `m<=t`. For `t=3` and `t=4`, an independent exhaustive
enumeration anchors every strict-template port occurrence at one access cell,
chooses distinct incident directions, rejects overlapping bodies, and counts
noncorner incidences:

| `t` | combinations | nonoverlapping | maximum `m` |
| ---: | ---: | ---: | ---: |
| 3 | 352,440 | 30,080 | 1 |
| 4 | 3,920,400 | 8,192 | 0 |

Thus every access cell satisfies

`t+m <= 4`.

Summing over outside access cells gives

`4N >= T_out+M_out >= 678-2S`.

The ordinary capacity bound `4N>=T_out` remains valid independently. For
`w>=9`,

`N >= max(ceil((580-S)/4), ceil((678-2S)/4))`.

For `w<9`, retaining only the ordinary bound is a safe relaxation.

## Full-span exclusion

Each required boundary body occupies three consecutive cells on either the
left or bottom supported boundary. A 70-cell boundary has 68 anchors and
nonoverlap permits at most 23 bodies. Because 46 such bodies are required,
every feasible layout has exactly 23 on each supported boundary, occupying 69
of its 70 cells.

A body-free rectangle spanning all 70 rows contains at least six cells of the
bottom boundary; one spanning all 70 columns contains at least six cells of
the left boundary. Either interval must meet the 69 occupied cells. Hence no
admissible rectangle has `h=70`.

## Complete dimension scan

The body and outside-access accounting requires

`w*h + N <= 4900-3580 = 1320`.

The complete normalized scan uses the ordinary bound everywhere, adds the
marked bound for `w>=9`, and rejects `h=70`. Its decisive cases are:

| dimensions | area | required `N` | sum | disposition |
| --- | ---: | ---: | ---: | --- |
| `34x35` | 1190 | 135 | 1325 | rejected |
| `29x41` | 1189 | 135 | 1324 | rejected |
| `17x70` | 1190 | 126 | 1316 | rejected by full span |
| `22x54` | 1188 | 132 | 1320 | survives the relaxation |

Scanning all `6<=w<=h<=70` leaves no lexicographically better pair than
`(1188,22)`. This is a necessary-condition result only: the surviving
`22x54` dimensions need not be attainable.

## Claim boundary

The paper proof and independent coordinate enumerations support
`ADMITTED_FOR_B1_ENCODER_DESIGN`. A later task must still encode the complete
lex-better band, pass an independent translation gate, and produce any
required formal UNSAT evidence before the project upper ledger can change.
Nothing here establishes a witness, attainability, optimality, global
infeasibility, or production `CERTIFIED` status.
