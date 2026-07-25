# R4 external-response review

**Document nature:** terminal research handoff for response ingestion and admission  
**Cutoff date:** 2026-07-23  
**Terminal status:** `ADMISSION_PARTIAL`  
**Authoritative admission:** `admission/a004/admission.json`  
**Current project ledger:** `U=(1190,34)`, `L=absent`

The original R4 response contract has completed all four gates: verbatim
archive, independent recomputation, mathematical adversarial review, and
candidate-aware admission. The outcome is intentionally split:

- the proposed upper candidate `(1188,22)` is
  `ADMITTED_FOR_B1_ENCODER_DESIGN` as a research follow-up input;
- the x67-c5 core-guided partition-repair suggestion is
  `NEEDS_PREREQUISITES` and is not admitted for Track W execution.

No encoder, solver, RoundingSat, VeriPB, witness search, assembly, or router was
started. This review does not itself change the upper ledger or authorize
either direction to execute.

## Authority and response identities

- R4 authority run:
  `.artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A`
- Package ID:
  `1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f`
- Selected receipt:
  `verifications/independent-a002-20260722T0845Z/receipt.json`,
  13,840 bytes,
  SHA-256 `cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4`
- Response run:
  `.artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-20260723T023657Z-R4resp-357f260d`
- Response ingest: 5,709 bytes,
  SHA-256 `f0cfeafc074460d92588d30b3a02c2636a781c56e3b9586c2a47597631b4e618`

The three external inputs remain inert data. Their raw artifacts and canonical
cleanroom documents 12, 13, and 14 are byte-identical. The Python attachment
was never parsed as a program, compiled, imported, or executed.

## Terminal machine records

| Record | Status | Size | SHA-256 |
| --- | --- | ---: | --- |
| `claims/a004/quantitative-claim-ledger.json` | `COMPLETE`, 17 claims | 22,770 B | `897303dd26e307125575d4d107ba34c9ee05bf809abf894dbf54c48968654ccd` |
| `recomputations/upper-counts-a004/report.json` | `PASS_EXACT_MATCH` | 16,986 B | `710cb182b295470335375ab567be66833760c35fc494d12ea7d2998e92c1aa37` |
| `recomputations/marked-geometry-a004/report.json` | `PASS_EXACT_MATCH` | 15,502 B | `954593d928bbe449b8b5a39f8788125294383073f0894c029dd1fbf87ae0bc7e` |
| `recomputations/w2d-audit-a004/report.json` | `PASS_EXACT_MATCH` | 12,775 B | `d37db9dabf42424de9140d40e149c663f291c7f6ac2795bb7f3258bd2148d48c` |
| `adversarial/a004/verdict.json` | `COMPLETE` | 10,305 B | `1f291629a39c5d3990d028276c7a9175b56a27b048ad4259e6a7913dfd17e633` |
| `admission/a004/admission.json` | `PARTIAL` | 10,273 B | `2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff` |

The a004 chain is one authority generation. Its ledger regenerates the fixed
17 claims and binds the ledger-builder bytes; each report replays that ledger;
the verdict builder reconstructs every candidate and global field; and
admission invokes that complete verdict replay before reconstructing its own
payload. All generated JSON is strict, canonically serialized, and confined to
fresh non-symlink subdirectories of this response run.

The unnumbered ledger/recomputations, a002 recomputations and verdict, and a002
and a003 admissions remain immutable execution history. They are not accepted
by the current authority replay.

## Decision boundary

The upper candidate passed the necessity and adversarial gates:

- 110 forced marked incidences;
- `t(z)+m(z)<=4`;
- marked membrane `M_in<=w+h+12`;
- required boundary packing `23+23`, excluding every side-70 rectangle; and
- complete dimension scan with relaxed lex maximum `(1188,22)`.

The next permitted upper-bound activity is a separately authorized,
proof-bearing B1 task that designs the new encoder and translation gate. Until
that later task succeeds, `(1188,22)` is not the project upper ledger.

The witness suggestion does not avoid W2d's common c3 `(12,4,3)` gate, and
x67-c5 remains `UNKNOWN`. Its exact prerequisites are recorded in
[04_adversarial_verdict.md](04_adversarial_verdict.md). No Track W execution is
authorized.

## Reading order

1. [01_response_bundle_contract.md](01_response_bundle_contract.md) — inert
   archive and detached identities.
2. [02_necessity_proof.md](02_necessity_proof.md) — locally reconstructed
   mathematical chain.
3. [03_independent_recomputation.md](03_independent_recomputation.md) —
   checker independence, report hashes, and exact results.
4. [04_adversarial_verdict.md](04_adversarial_verdict.md) — candidate-wise
   judgment and first unclosed obligations.
5. [05_execution_record.md](05_execution_record.md) — commands, historical
   attempts, and validation transcript.

## Claims not established

This package does not establish a new current upper bound, any lower bound,
any witness, attainability of `(1188,22)`, optimality, global infeasibility, or
production `CERTIFIED` status. It does not authorize formal proof execution,
B1 encoder execution, Track W search, assembly, or routing.
