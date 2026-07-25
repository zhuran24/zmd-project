# R4 response independent recomputation

**Document nature:** research recomputation and artifact ledger  
**Cutoff date:** 2026-07-23  
**Terminal status:** `THREE_REPORTS_PASS_EXACT_MATCH`  
**Authority response run:** `.artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-20260723T023657Z-R4resp-357f260d`

The authoritative recomputation set is the three `a004` reports listed below.
Each checker was written locally from the mathematical claim, is shorter than
200 physical lines, uses only an allowlisted standard-library subset, and has
bytes distinct from every external response file. The external Python
attachment was not decoded as a program, parsed as a program, compiled,
imported, or executed.

## Provenance closure

The downstream runner pins and rereads:

- the original R4 package, manifest, selected-receipt detached identity, READY
  selection, and selector tool;
- `response-ingest.json` at 5,709 bytes and SHA-256
  `f0cfeafc074460d92588d30b3a02c2636a781c56e3b9586c2a47597631b4e618`;
- all three original source paths, raw artifacts, and canonical documents;
- the fixed ordered 17-claim semantics and exact claim-ledger builder identity;
  and
- the exact checker path, profile, byte size, and SHA-256 for each checker.

The runner then replays each report's checker snapshot, evidence identity,
stdout and stderr records, parsed result object, expected and actual claim
values, exact-match flags, offline sandbox argv, return code, timeout state,
ledger-builder identity, and all execution-authority flags. The verdict and
admission layers reconstruct their complete canonical payloads rather than
accepting selected fields. A label or a coordinated downstream hash refresh
cannot satisfy these gates.

## Artifact identities

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `claims/a004/external-code-inert-inspection.json` | 5,510 B | `ff004391bef1962f5d4a848eed1397e70cd7a3d75385c31cb87d20063676bad8` |
| `claims/a004/quantitative-claim-ledger.json` | 22,770 B | `897303dd26e307125575d4d107ba34c9ee05bf809abf894dbf54c48968654ccd` |
| `upper-counts-a004/report.json` | 16,986 B | `710cb182b295470335375ab567be66833760c35fc494d12ea7d2998e92c1aa37` |
| `marked-geometry-a004/report.json` | 15,502 B | `954593d928bbe449b8b5a39f8788125294383073f0894c029dd1fbf87ae0bc7e` |
| `w2d-audit-a004/report.json` | 12,775 B | `d37db9dabf42424de9140d40e149c663f291c7f6ac2795bb7f3258bd2148d48c` |
| `adversarial/a004/verdict.json` | 10,305 B | `1f291629a39c5d3990d028276c7a9175b56a27b048ad4259e6a7913dfd17e633` |
| `admission/a004/admission.json` | 10,273 B | `2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff` |

The registered local checker identities are:

| Checker | Profile | Lines | SHA-256 |
| --- | --- | ---: | --- |
| `independent_r4_upper_counts_v1.py` | strict instance | 191 | `f3ab9fed7f6af39d9861f6c524065f3f7c76f476933f729c4d9d8b0aba41bc85` |
| `independent_r4_marked_geometry_v1.py` | strict instance | 193 | `7c4d930af4bba4b007131dd798d7f7720e67b6c12ba7bbf33d078a3a94a86eec` |
| `independent_r4_w2d_audit_v1.py` | detached W2d authority | 199 | `f9d568b691d7056595f703e1d3047051bec6cad7e634e70802f8a16238f48d73` |

All three executions used the fixed Python 3.13 interpreter inside
`bwrap --unshare-net`, with an empty response-data mount set, a 60-second wall
timeout, and a 1 MB stdout/stderr cap. Each returned zero with empty stderr and
`PASS_EXACT_MATCH`.

The authority-chain tool identities are:

| Tool | Size | SHA-256 |
| --- | ---: | --- |
| `build_r4_claim_ledger_v2.py` | 36,579 B | `95bc53e24267c318e2584b9cf095afbc97becfc469f3e7b3f1ff500d55b7e597` |
| `run_r4_local_recomputation_bundle_v2.py` | 37,243 B | `8f569368cf163982486e341ee664640aeda1de7d5aef290e7a9449e329ea0df8` |
| `build_r4_adversarial_verdict_v2.py` | 19,505 B | `b414a9250e298f447796e4a5fa8f889efa275aef70d18e9c7626fefe294fbb6c` |
| `close_r4_response_candidate_admission_v2.py` | 17,955 B | `cf47cc662e3c3cf6e7e13915869866a09067854b837a5a775bdf8504dfd3f5d5` |

## Upper-candidate results

The strict-count checker independently rebuilt:

- 266 required instances, 219 manufacturing instances, and 3,544 required body
  cells;
- 3,325 powered body cells, halo weight 792, 840 eligible placements, per-pole
  charge 396, and `P>=9`;
- 628 active terminal incidences;
- the ordinary membrane constants `63+24=87`, `K_in<=S+48`, and outside
  numerator 580; and
- 58 manufacturing marks plus 52 necessarily active noncorner raw-provider
  slots.

The geometry checker exhaustively rebuilt:

- 178 physical port occurrences for the local access-cell enumeration;
- 352,440 three-terminal and 3,920,400 four-terminal combinations;
- `t(z)+m(z)<=4`, `M_in<=S+12`, and the `23+23` boundary split;
- the decisive totals `34x35 -> 1325`, `29x41 -> 1324`,
  `17x70 -> full-span rejection`, and `22x54 -> 1320`; and
- a complete `6<=w<=h<=70` scan with no survivor lexicographically better than
  `(1188,22)`.

## Witness-suggestion results

The W2d checker read only
`/home/zhuran24/zmd-pj-codex-baselines/witness-ea407fa-20260720`, verified
detached HEAD `ea407fafaff56333bcf18066cecf890f0ef0c6da`, and matched six fixed
authority-file hashes. It confirmed:

- two exact 17-component manifests, both requiring c3 `(12,4,3)`;
- c3 `INFEASIBLE` after `7156+12=7168` sound cuts and zero candidate nogoods;
- x67-c5 `(10,4,4)` still `UNKNOWN` after 4,010 cuts and zero candidate
  nogoods; and
- W2d remains stopped with no witness or global-infeasibility claim.

The suggestion is therefore `NEEDS_PREREQUISITES`, not an executable search
candidate.

## Historical non-authoritative attempts

The unnumbered ledger and recomputations, the a002 recomputations and verdict,
and the a002/a003 admissions matched the numerical conclusion recorded at
their respective times. Later fail-closed audits found first that report
provenance needed full replay, then that the fixed 17-claim semantics and
verdict/admission payloads also needed builder-owned complete replay. Their
bytes remain unchanged, but the current validators intentionally reject them
as authority. Only the unified a004 chain is current.

## Claim boundary

Independent arithmetic and geometry are complete for research admission. The
project ledger remains `U=(1190,34)`, `L=absent`. No formal upper-ledger update,
witness, attainability, optimality, global infeasibility, or production
`CERTIFIED` result is established here.
