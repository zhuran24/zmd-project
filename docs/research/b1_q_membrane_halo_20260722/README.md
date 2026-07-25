# Track B/B1 round 1: Q/membrane/halo

| Document property | Current value |
|---|---|
| Document nature | Current-state research round report |
| Evidence cutoff | `2026-07-22` |
| Status | **COMPLETE** — all admitted round-1 research and translation gates pass; `U` remains `(1190,34)` |
| Authoritative run | `.artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/` |

## Round result

```text
U old -> new: (1190,34) -> (1190,34)
```

The round admits one new research necessary condition, `(B1-QMH)`, whose
proof is recorded in [`01_necessity_proof.md`](01_necessity_proof.md):

```text
w*h + ceil((580-w-h+floor(|R intersect Q_delta|/2)+e)/4) <= 1320,
```

where `e` counts boundary partial contacts at tangential rectangle endpoints.
It does **not** tighten the inherited upper ledger.  Both ceiling orientations
`(34,35)` and `(35,34)` survive, with 59,173 pattern-placement assignments
each.  No RoundingSat or VeriPB process was started.

This is upper-ledger research only.  It does not prove a witness,
attainability, routing feasibility, global optimality, or production
`CERTIFIED` status.  A surviving selector assignment is a relaxation
assignment, not a layout.

## Funnel verdicts

| Gate | Status | Exact result |
|---|---|---|
| Paper necessity proof | PASS | Derives `(B1-QMH)` and rejects direct Q-out plus membrane addition as double counting. |
| Coordinate recomputation | PASS | Pinned strict SHA; full 47-pattern coordinate scan. |
| Independent interval/distribution recomputation | PASS | No import of the primary implementation or encoder. |
| Script-bound agreement | PASS | Current script hashes match both reports; `corpus_errors=[]`; raw-provider identity `52=46*1+6` closes. |
| Adversarial review | PASS | [`02_adversarial_verdict.md`](02_adversarial_verdict.md) confirms 11/11 attack surfaces; no mathematical counterexample. |
| Build-only OPB encoder | PASS | 2,567 variables, 96 constraints, 2 equalities, 94 pair exclusions; no nonlinear `W*H`. |
| Independent-rebuild translation gate | PASS | 18/18 checks; constraint multiset has zero missing and zero unexpected constraints. |

The complete scan has 203,340,800 pattern-placements.  The inherited B0
membrane baseline retains 165,541,238; `(B1-QMH)` retains 165,541,100 and
therefore removes 138.  Exactly four oriented dimensions change:

| Oriented dimension | Removed |
|---|---:|
| `(34,35)` | 47 |
| `(35,34)` | 47 |
| `(29,41)` | 22 |
| `(41,29)` | 22 |

The refined scan retains 2,127 oriented dimensions.  The 24 dimensions
retained by the inherited baseline with a side of 70 disappear because every
legal rectangle anchor has `x,y>=1`; this is a placement-domain fact, not a
new frontier improvement.

The ceiling-only OPB contains exactly one of 47 pattern selectors, exactly one
of 2,520 rectangle-placement selectors, and the 94 precomputed forbidden
pairs.  Its pair corpus is 118,440 and 118,346 pairs survive.  It is
intentionally satisfiable as a relaxation, so a formal UNSAT proof run would
have no admissible purpose in this round.

## Admitted soundness and trust basis

The authoritative coordinate and interval/distribution reports embed the
SHA-256 of their current generating scripts.  The agreement gate hashes those
scripts independently and rejects any report whose embedded digest is stale.
Both recomputers and the agreement gate also fail closed unless strict
raw-output demand and total provider capacity close as `52=46*1+6`.

That saturation identity makes every boundary Q port active in every feasible
layout: demand is 52, while the only provider capacity is exactly `46 boundary
ports * 1 + 6 protocol-core outputs`.

The translation gate has no import, execution, or semantic-code dependency on
the encoder.  It reads the current encoder file only to reseal its path,
SHA-256, and size against the artifact provenance.  It has no source or runtime
dependency on either recomputer, their comparison gate, the B0 encoder, or the
R3 certificate script.  Its author did see an early portion of the primary
recomputation during reconnaissance, so it is not claimed as an epistemically
sealed clean-room implementation.  The delivered gate independently parses
strict data, rebuilds geometry and the OPB multiset, and is used only for
translation fidelity.

## Authoritative run, artifact classification, and hashes

The authoritative no-overwrite run is:

```text
.artifacts/track_b_b1_q_membrane_halo_20260722/run-20260722T0902-nGEfoW/
```

### Execution-record exclusions (historical; through 2026-07-22)

Run `run-20260722T0850-mZ0JPp`, the unversioned `band-estimate.json`, and the
`band-v2.translation-gate.json`/`translation-v2.json` reports inside the
authoritative directory are non-authoritative reconnaissance artifacts.  The
authoritative inputs and output are the following exact bytes:

| Artifact | SHA-256 |
|---|---|
| `coordinate.json` | `0fa96587f4eb1043b02924e4fced8a682b0da0c09278d7b4aeb704aa74c8a254` |
| `independent.json` | `9164064e201ac2d3128fbd7b1e0bc154b7cd1d0fd3f5588d3b51a6d575f6b952` |
| `agreement.json` | `b1f8ee3cf01b43de97da955e736102c86d65c5b61d01205ad8ff505f6a5b2c65` |
| `band-estimate-v2.json` | `2fe8ca7a0b3b2ecd71e56a3bed1034db03a67d6eb47a07c08c3fb22319f66a95` |
| `band-v2.opb` | `0c5a2ea2dd0a978de07cf91120cd81d79e39169e01757da9268b0f044afeef1b` |
| `band-v2.meta.json` | `c0f5fabcfadecd035f291e2e32375af916f0594be665f4ea6e0363422cfde7dc` |
| `band-v2.var-map.json` | `97b03894b69f6d51df2d25e2543aac3989a0495342f050ecb8e092b8977d4c1f` |
| `band-v3.translation-gate.json` | `45363308076ae6fcd837f349e3769bc6e1ad0b4bc8f660b0fa3dc475d20d2bf2` |

Source hashes bound by the reports are:

| Source | SHA-256 |
|---|---|
| coordinate recomputer | `153347c1d4bfeb7ab8cdbb8a2630dc758e0ed02645e5c7a146796f4e099ab83d` |
| independent recomputer | `d9542bf915d3e5c2ec2f45cfa51284ffab631b223b0f848b8c94b6196afa931a` |
| agreement gate | `f45712c48e89d4cf5cec63ac8bd7a0ab984af98c49bddec9f412ef6e333c93ba` |
| band encoder | `72b3fef803aec508d4f130c2991224b3c96a8b519187766c2fe25dd89d12ab26` |
| translation gate | `dd536ffe7f94c78db6d8fa897741474afa4d277df1e26ac4b6f6f5da6e60ecc4` |

The dormant formal-run contract remains `MemoryHigh=35GiB`,
`MemoryMax=39GiB`, `MemorySwapMax=16GiB`, `OOMPolicy=continue`, one worker, a
5,000,000,000-byte proof cap, and a 10GiB disk low-water mark.  Only
`band-estimate-v2.json` and `band-v2.meta.json` carry
`resource_contract.formal_run_authorized=false`.  The translation gate
reconstructs and checks the estimate and metadata resource contracts, checks
the build-only claim scope, and records
`proof_status=translation_gate_only_no_solver_or_proof_run_no_unsat_claim`.
The OPB and variable map do not carry the authorization field; a gate PASS
closes translation fidelity and the no-proof claim boundary, not an UNSAT
claim.

## Reproduction

Use only the fixed interpreter:

```text
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13
```

The authoritative run's funnel was executed in this order:

1. `verify_b1_q_membrane_halo_v1.py --output .../coordinate.json`
2. `recompute_b1_q_membrane_halo_independent_v1.py --output .../independent.json`
3. `compare_b1_q_membrane_halo_recomputations_v1.py --coordinate ... --independent ... --output .../agreement.json`
4. `b1_q_membrane_halo_band_encoder_v1.py estimate --project-root ... --output .../band-estimate-v2.json`
5. `b1_q_membrane_halo_band_encoder_v1.py encode --estimate-sha256 2fe8ca... --opb-out .../band-v2.opb --meta-out .../band-v2.meta.json --var-map-out .../band-v2.var-map.json`
6. `verify_b1_q_membrane_halo_band_translation_v1.py --opb ... --meta ... --var-map ... --estimate ... --output .../band-v3.translation-gate.json`

All writers use exclusive creation.  Reusing an output path is a hard failure.

## Core-plan next-round direction

The next B1 research candidate is **core-plan candidate 2: conditional halo**:

```text
Σ_q C_q(R) ≥ 3325
```

Here `q` ranges over all selected power poles, and `C_q(R)` is the capacity of
the translated pole stencil that remains in-grid and outside the candidate
empty rectangle `R`.  This round did not prove, recompute, attack, encode, or
scan that condition.

### Survivor diagnostics and possible prerequisite lemmas

At `(34,35)` or `(35,34)`, an internal `q=e=0` placement has membrane
left-hand side 1,318, leaving two cells of slack under 1,320.  In the inherited
area ledger, a tenth power pole costs four cells and a `3×3` storage box costs
nine cells.  The current ceiling survivors therefore expose exact-nine-pole
and no-`3×3`-storage-box occupancy as possible prerequisite lemmas for the
conditional-halo candidate; they are not a separate next-round candidate.
They target the 55,930 `q=e=0` survivors per orientation that the boundary-Q
refinement cannot see.  Use in a subsequent encoder requires a necessity
proof, independent recomputation, and adversarial review.
