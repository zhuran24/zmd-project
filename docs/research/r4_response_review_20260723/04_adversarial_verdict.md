# R4 response mathematical adversarial verdict

**Document nature:** research-level adversarial review  
**Cutoff date:** 2026-07-23  
**Terminal status:** `UPPER_PASS; WITNESS_NEEDS_PREREQUISITES`  
**Authoritative machine verdict:** `adversarial/a004/verdict.json`, SHA-256 `1f291629a39c5d3990d028276c7a9175b56a27b048ad4259e6a7913dfd17e633`  
**Current project ledger:** `U=(1190,34)`, `L=absent`

The review began only after the complete quantitative claim ledger and all
three local recomputations were available. It treats every external-response
byte as inert evidence and relies only on locally written checkers, the
byte-locked strict instance, the detached W2d authority, and geometric
arguments reconstructed in
[02_necessity_proof.md](02_necessity_proof.md).

The machine verdict is accepted only through the verdict builder's read-only
complete replay. That replay regenerates the fixed 17-claim ledger, replays all
three a004 reports, reconstructs every candidate decision and every global
safety or authorization field, and requires the strict canonical JSON payload
to match exactly. The a004 admission invokes this replay rather than
maintaining a separate field whitelist.

## Upper-bound candidate `(1188,22)`

**Verdict:** `PASS`, limited to `ADMITTED_FOR_B1_ENCODER_DESIGN`.

The following attacks did not produce a counterexample:

1. **Marked-terminal census.** Exact binding forces all 52 raw-provider output
   slots active because the provider capacity is exactly the 52-unit raw
   demand. Those slots are noncorner. Together with 58 forced manufacturing
   marks, this closes `M=110`.
2. **Local sharing.** The complete four-direction/body-overlap enumeration
   gives maximum marked counts one and zero when an access cell has three and
   four active incidences, respectively. Together with the trivial
   `t<=2` cases, this closes `t(z)+m(z)<=4`.
3. **Marked membrane.** Contact intervals on one directed rectangle side
   cannot overlap. Every partial contact crosses a directed side endpoint,
   and body overlap forbids two contacts from using the same endpoint.
   Full-contact half density, at most eight partial contacts, and per-contact
   doubled excess at most three close `M_in<=S+12`.
4. **Boundary packing.** Forty-six length-three bodies across two supported
   70-cell boundaries, each of capacity 23, force a `23+23` split and 69
   occupied cells on each boundary. A minimum-width rectangle spanning all 70
   rows or columns must hit one of those bodies.
5. **Dimension arithmetic.** `34x35` and `29x41` require 1325 and 1324 cells
   in the relaxation and are rejected. `17x70` is rejected by the full-span
   lemma. The complete normalized scan leaves `22x54`, with
   `1188+132=1320`, and no lexicographically better survivor.

The first unclosed obligation is downstream, not geometric: no B1 encoder,
translation admission, lex-better-band formula, RoundingSat proof, or VeriPB
check has been produced for this candidate. Therefore this task does not
change the upper ledger to `(1188,22)`.

## Witness repair suggestion

**Verdict:** `NEEDS_PREREQUISITES`; it is not an executable Track W candidate.

The detached W2d authority contains two exact 17-component count-closure
manifests, and both require c3 target `(12,4,3)`. That row is locally
`INFEASIBLE` after 7,156 imported plus 12 continuation sound cuts, with no
candidate nogoods. The separate x67-c5 target `(10,4,4)` remains `UNKNOWN`
after 4,010 cuts, also with no candidate nogoods. Merely targeting x67-c5 does
not alter or avoid the common c3 row.

The suggested repair may be reconsidered only after all of these prerequisites
exist:

1. a byte-pinned partition-mutation domain, protected invariants, Hamming
   objective, and deterministic tie-break;
2. per-cut provenance and complete pin, geometry, front, connectivity, and
   power hypothesis dependencies for the 7,168 c3 cuts;
3. an independently checked `guard => cut` construction for every conditional
   cut, with missing or unknown dependencies disabling the cut;
4. a new hash-pinned exact 17-component manifest, independently count-closure
   checked, that does not require c3 `(12,4,3)`;
5. accepted results for every local row needed by that manifest—x67-c5's
   current `UNKNOWN` is not feasibility;
6. proof that partition mutation preserves the coordinate frame and all body,
   front, connectivity, power, and assembly interfaces; and
7. owner authorization that explicitly supersedes the W2d stop and supplies a
   new search resource contract.

Until then, `research_followup_admitted=false`,
`track_w_execution_authorized=false`, and no search, assembly, router, or
solver may start.

## Claim boundary

The split verdict supports one later B1 design input and rejects immediate
Track W execution. It establishes neither `(1188,22)` as the current upper
ledger nor any lower bound, witness, attainability, optimality, global
infeasibility, or production `CERTIFIED` conclusion.
