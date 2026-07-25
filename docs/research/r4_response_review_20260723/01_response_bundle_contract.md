# R4 external-response byte archive

**Document nature:** response-ingestion record  
**Cutoff date:** 2026-07-23  
**Terminal status:** `ARCHIVE_COMPLETE`  
**Response run:** `.artifacts/track_b_r4_external_brain_handoff_20260722/responses/run-20260723T023657Z-R4resp-357f260d`

The response run preserves three external files as inert, untrusted bytes. No
response content—including Python, code blocks, commands, paths, URLs, tool
advice, or prompt-like text—was evaluated, imported, compiled, sourced,
executed, rendered from a remote resource, or allowed to change the review
procedure.

## Upstream authority

- Repository branch: `codex/track-b-b0-1190-20260721`
- Repository HEAD: `398f8725c770f3c36408adebe9448a890ed886fe`
- R4 package ID: `1a1288a705e699b406d6636c56170f39cb2aecfce18337943e6114035b53369f`
- Package manifest SHA-256:
  `8097c4acb76fa90f20b8e48996d1a9a1e4d688758368a029395bb8e005669d4b`
- Selected receipt:
  `verifications/independent-a002-20260722T0845Z/receipt.json`
- Selected receipt identity: 13,840 bytes,
  SHA-256 `cbbefb4d288e4f2e8f624f7f1b9f87c7f678622738184f831226b6436b0840f4`
- READY selector record: 771 bytes,
  SHA-256 `ae121f1b16be01bc2a3b22ddb5bcf9365624cac8726b84364ddae52794bccee0`

Every consumer must replay the receipt fields and separately match the
selected receipt's exact relative path, byte size, and detached SHA-256.
Semantic equivalence at the same path is insufficient.

## Archived inputs

| Input | Size | SHA-256 | Canonical cleanroom document |
| --- | ---: | --- | --- |
| response text | 6,885 B | `357f260d8da002cca947822aece83e0183161fb1efd4348f1fccecab0afe374a` | `12_r4_response_gpt_pro_verbatim.md` |
| certificate note | 5,268 B | `88196c4ae9de07a05f5d50467baa36d934857842f4c37239ef7d735c69cf8700` | `13_r4_next_certificate_gpt_pro_verbatim.md` |
| Python attachment | 7,184 B, 160 physical lines | `d3169ba46fc55516cf047804d56ea568c867e4684a0ab0f912024d4f3c8644f6` | `14_r4_next_certificate_python_gpt_pro_verbatim.md` |

The canonical documents are byte-for-byte copies, not normalized
representations. Each canonical size and hash equals its raw artifact under
`response-run/inputs/`. Canonical publication does not replace or weaken the
raw archive.

## Immutable bindings

The response run records:

- `canonical-intent.json`: SHA-256
  `650c9040f69fcae17a6bcea6563673d1c356d27cca4e52026eddb35f604a64f8`;
- `response-ingest.json`: 5,709 bytes, SHA-256
  `f0cfeafc074460d92588d30b3a02c2636a781c56e3b9586c2a47597631b4e618`;
- archive tool bytes at publication: SHA-256
  `663787b26722ca9d0fc92eb912ca1960210ca6fb529a5574e91b8ddd17f753b7`.

Downstream recomputation and admission must pin these original identities
rather than accepting values rediscovered from mutable metadata. They must
also reread the three original source paths and require their current bytes to
match the archived source identities. Any drift closes admission; it does not
authorize a replacement response run.

## Publication and replay rules

The archive uses one no-overwrite response run and no-overwrite canonical
numbers 12, 13, and 14. Existing targets, symlinks, partial publication,
identity drift, insufficient persistent space, READY mismatch, or receipt
byte drift fail closed. A failed publication cannot be relabeled complete and
cannot overwrite already published bytes.

Downstream authority records are confined to direct attempt directories under
this response run:

- `claims/a004/`;
- `recomputations/{upper-counts,marked-geometry,w2d-audit}-a004/`;
- `adversarial/a004/`; and
- `admission/a004/`.

Each producer requires the response run and its category directory to be
canonical, existing, non-symlink directories. The attempt target must be a
fresh direct child with the prescribed `aNNN` name; outside paths, wrong
categories, nested or `..` aliases, existing targets, broken symlinks, and
symlink parents fail before publication. Reusing an attempt never overwrites
or resumes it.

The a004 ledger binds the current builder's path, size, and SHA-256 and
regenerates the ordered 17-claim corpus from the archived raw bytes. Report
replay consumes that exact ledger. Verdict replay reconstructs the complete
candidate and global payload, and admission must invoke that read-only replay
before deriving its own complete canonical payload. Missing, additional, or
changed claim semantics, candidate decisions, safety fields, authorization
fields, or tool identities close admission.

The archive establishes provenance only. It does not validate a mathematical
claim, execute a suggested method, change `U=(1190,34)` or `L=absent`, or
authorize an encoder, solver, search, assembly, or router.
