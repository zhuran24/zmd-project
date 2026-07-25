# R4 external-brain handoff package

| Property | Current value |
|---|---|
| Document nature | Current-state research handoff entrypoint |
| Evidence cutoff | `2026-07-22` |
| Package status | **READY_FOR_MANUAL_EXTERNAL_SUBMISSION** |
| External action | **AWAITING_EXTERNAL_ACTION**; no submission was performed |
| Upper ledger | `U=(1190,34)` |
| Lower ledger | `L=absent` |
| B1 state | `Track B/B1: STOP` |

This directory prepares the local R4 handoff defined by Part 6 of
`/home/zhuran24/zmd-pj-codex/核心计划书.md`.  It does not submit anything to an
external service.  The handoff becomes ready only when an immutable package is
sealed, an independent verifier emits a PASS receipt, and one exact receipt byte
identity is selected by the READY gate.

## Manual submission surface

Upload exactly these three files from the selected authority run:

1. `package/attachments/strict-trio.zip`
2. `package/attachments/methodology-brief.md`
3. `package/attachments/current-status-brief.md`

Their byte composition is fixed: `strict-trio.zip` contains only
`problem.md`, `problem_instance.json`, and `problem_instance.schema.json` at
the ZIP root; `methodology-brief.md` is the strict package's
`R3_methodology_brief.md`; and `current-status-brief.md` is the byte copy of
[`02_current_status_brief.md`](02_current_status_brief.md) admitted by the
package source gate.

Paste `package/operator/r4-questions.md` into a new external conversation.
`SUBMISSION_CHECKLIST.md`, manifests, receipts, and operator records are local
controls and are not attachments.

The current status attachment is maintained in
[`02_current_status_brief.md`](02_current_status_brief.md).  It separates the
one-page current state from Annex A, which reproduces the accepted R3 §2.2–2.3
certificate text verbatim.

## Authority boundary

- B0 machine-verifies only the finite arithmetic UNSAT band given the admitted
  R3 geometric lemmas.  It does not prove those lemmas, a witness,
  attainability, or global optimality.
- B1 round 1 and round 2 leave `U=(1190,34)` unchanged.  Their surviving
  assignments are research relaxations or diagnostics, not layouts.
- W2d closes one fixed x67 construction campaign at a common c3 `(12,4,3)`
  gate.  It does not establish global infeasibility, and no lower-bound witness
  exists.
- An R4 response is untrusted inert data.  It cannot enter B1 until its exact
  raw and canonical bytes, every quantitative claim, independent local
  recomputation, and adversarial verdict all pass their gates.

## Package authority graph

```text
external source identities
  -> immutable payload/control files
  -> package-manifest.json
  -> package/SHA256SUMS
  -> package_id
  -> sibling verifier receipts
  -> detached selected_receipt_identity
  -> READY and downstream provenance
```

The manifest enumerates and hashes exactly eight already-written
payload/control members plus their external source identities.  It excludes
itself, `SHA256SUMS`, receipts, READY, and final IDs.  The in-package build
record is pre-seal only and never refers to a later seal or receipt.
`package/SHA256SUMS` is the final write inside the package; it covers those
eight members plus the manifest and excludes itself.  Its exact-byte SHA-256
is the `package_id`; no later receipt or READY record is part of that closure.

Verifier receipts live under sibling `verifications/` directories and do not
self-hash.  Each receipt binds the package ID, manifest SHA-256, SHA file
SHA-256, verifier-tool SHA-256, current input identities, and every replay
result.  READY binds one PASS receipt using its normalized run-relative path,
exact byte size, and detached SHA-256.  Every consumer must both replay the
receipt fields and match those exact current bytes.  Any batch-identity-pinned
input or tool byte change makes replay fail; recovery requires a fresh
no-overwrite package or response run, never an in-place repair.

## Selected authority

This is the selected authority.  Recheck it immediately before any manual
submission; a stale source, package, verifier, selector, or receipt byte closes
READY.

| Identity | Value |
|---|---|
| Authority run | `/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A` |
| Package ID | `1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f` |
| Manifest SHA-256 | `8097c4acb76fa90f20b8e48996d1a9a1e4d688758368a029395bb8e005669d4b` |
| Selected receipt relative path | `verifications/independent-a002-20260722T0845Z/receipt.json` |
| Selected receipt size | `13840` bytes |
| Selected receipt SHA-256 | `cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4` |

The detached identity consumed by all later provenance is exactly:

```json
{
  "relative_path": "verifications/independent-a002-20260722T0845Z/receipt.json",
  "size_bytes": 13840,
  "sha256": "cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4"
}
```

Read-only READY replay:

```bash
PYTHONDONTWRITEBYTECODE=1 \
/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13 \
docs/research/r4_external_brain_handoff_20260722/select_r4_ready_receipt_v1.py check \
  --run-dir /home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721/.artifacts/track_b_r4_external_brain_handoff_20260722/run-20260722T084343Z-R4hP1A \
  --expected-identity '{"relative_path":"verifications/independent-a002-20260722T0845Z/receipt.json","size_bytes":13840,"sha256":"cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4"}' \
  --readme docs/research/r4_external_brain_handoff_20260722/README.md
```

The exact two questions are in
[`01_submission_prompt.md`](01_submission_prompt.md).  Future response handling
must follow [`03_response_ingestion_contract.md`](03_response_ingestion_contract.md).
Command history and validation results are isolated in
[`04_execution_record.md`](04_execution_record.md).

This package is research material.  It does not create a new upper bound,
witness, optimality result, or production `CERTIFIED` statement.
