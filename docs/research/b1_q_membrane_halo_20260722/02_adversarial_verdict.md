# B1 Q/membrane/halo adversarial verdict

| Document property | Current value |
|---|---|
| Document nature | Adversarial judgment archive for the B1 round-1 necessary condition |
| Evidence cutoff | `2026-07-22` |
| Status | **PASS — 11/11 CONFIRMED** |
| Authoritative run | `.artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/` |

No mathematical counterexample was found.  This verdict admits only the
necessary condition `(B1-QMH)` into the research encoder.  It does not
establish a witness, attainability, routing feasibility, a smaller upper
bound, global optimality, or production `CERTIFIED` status.

## Decision table

| # | Attack surface | Verdict | Independent evidence |
|---:|---|---|---|
| 1 | 47-pattern completeness; row/column zero | CONFIRMED | Each edge holds 23 length-three bodies and one gap in `0,3,...,69`.  Both gaps nonzero overlaps at `(0,0)`, leaving `24+23=47`.  A side-six rectangle cannot use the single empty boundary cell. |
| 2 | `Q_delta` completeness and activity | CONFIRMED | Strict modes give offsets `(1,a+1)` and `(a+1,1)`, 46 distinct cells per legal pattern.  Raw demand and provider capacity independently close as `52=46*1+6`, forcing all Q ports active. |
| 3 | `q/e` contact geometry | CONFIRMED | For body interval `[a,a+2]`, access midpoint `a+1` in a rectangle interval of length at least six gives contact two or three; it is two exactly at a tangential endpoint.  The full gap/span/anchor probe had no errors. |
| 4 | Endpoint-slot exclusivity | CONFIRMED | Two partial contacts using the same directed endpoint occupy the same exterior body cell.  A boundary partial therefore consumes exactly one of the eight slots and leaves at most `8-e` manufacturing partials. |
| 5 | Class excess and double counting | CONFIRMED | The strict eight-class counts are `155/12/11/32/17/32/3/3`, full-contact excess is 63, and partial extra is at most three.  Boundary full/partial contributions are exactly `-1/0`, yielding `87-q-2e`. |
| 6 | `L_MB <= 2(w+h)` and corners | CONFIRMED | Overlapping contact intervals on one directed side imply body overlap.  Adjacent sides may both use a corner, already counted as two distinct directed positions in `2(w+h)`. |
| 7 | Protocol-core/final `+5` | CONFIRMED | Each core mode has outputs split `3+3` on opposite sides; a body-empty rectangle can touch at most one such side.  The global final-input count is two. |
| 8 | Incidence cap four; Q union | CONFIRMED | An access cell has four orthogonal neighbor cells, strict modes have no duplicate relative-access port, and bodies do not overlap.  Q-out cells are already in the membrane external-cell set; adding both pools is unsound double counting. |
| 9 | Halo composition | CONFIRMED | The independent stencil recomputation gives total weight 396, 840 checked placements, powered area 3,325, and `P>=9`; hence `4900-3544-9*4=1320`. |
| 10 | Ceil arithmetic and corpus completeness | CONFIRMED | The two algorithms agree on 203,340,800 pattern-placements, 165,541,238 baseline survivors, 165,541,100 refined survivors, and 138 incremental prunes.  Both ceiling orientations retain 59,173 assignments. |
| 11 | Claim boundary | CONFIRMED | A surviving selector pair is only a relaxation assignment.  Since the inherited ceiling survives, `U` remains `(1190,34)` and there is no new UNSAT claim. |

The concrete rejected ceiling example is pattern gaps `(0,0)` with
`R=(x=1,y=1,w=34,h=35)`: `q=23`, `e=1`, and the refined left-hand side is
1321.  The internal placement `(2,2,34,35)` has `q=e=0`, left-hand side 1318,
and survives.

## Execution record (historical provenance; through 2026-07-22)

The first review found that an earlier coordinate report predated a subsequent
edit to its generating script.  That old report is not an admission artifact.
Both recomputers now embed their own script SHA-256, the agreement gate hashes
the current scripts and requires exact equality, and both independently assert
`52=46*1+6`.  The authoritative exclusive run at
`.artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/`
then produced `coordinate.json`, `independent.json`, and `agreement.json` with
`status=PASS` and `corpus_errors=[]`.

The review also reran the R3 certificate recomputation with the fixed Python
3.13 interpreter; it exited zero.  No RoundingSat or VeriPB process was started
for this gate.
