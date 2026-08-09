# P1.2 V78 certified manifest writer canonical-surface hardening

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Date: 2026-06-10

Review anchor: `v78_certified_manifest_writer_canonical_surface`

## Result

No new architecture-breaking flaw was found in the exact/LBBD proof kernel.  The
real pattern behind the long P1.2 review tail is narrower: the solver had grown
several ways to *publish* certified-looking delivery evidence, while the proof
object and public reader authority were being tightened one sibling seam at a
time.

The V73-V77 architecture is still the right spine: public `CERTIFIED` visibility
must go through `src/search/certified_surface.py`, and the delivery-manifest
export must prove that the in-memory campaign state matches the regular
in-project checkpoint on disk. V78 closes the remaining writer-authority edge
around where a certified manifest may be written.

## Finding

V77 made `export_certified_delivery_manifest(...)` disk-authoritative for the
campaign checkpoint, but two lower-level writing seams still existed:

1. `write_certified_delivery_manifest(output_path, payload)` could directly
   persist an arbitrary payload containing `best_certified_result` without going
   through the builder, disk checkpoint authority check, project-bound terminal
   evidence check, artifact currentness check, or central public verifier.
2. `export_certified_delivery_manifest(..., output_path=...)` still accepted a
   caller-selected output path.  For a certified payload this could create a
   standalone certified-looking manifest outside the canonical public surface,
   even though the central verifier only treats
   `data/solutions/certified_delivery_manifest.json` as the publishable manifest.

Neither seam defeated the current public verifier, but it was still bad phase
architecture: a certified delivery artifact should not be publishable from a raw
writer or from a side output path. The safe shape is one gate, one writer, one
canonical manifest surface.

## Patch

V78 changes `src/io/delivery_manifest.py` as follows:

- `write_certified_delivery_manifest(...)` now always rejects payloads with
  `best_certified_result`; the raw writer has no certified-payload override.
- `export_certified_delivery_manifest(...)` validates any payload with
  `best_certified_result` before writing it directly to the canonical target.
- Certified manifest output is accepted only at the canonical in-project path
  `data/solutions/certified_delivery_manifest.json`.
- Relative output paths are resolved against the project root before validation
  and writing, so the validator and writer agree on the exact filesystem target.
- The canonical output target must not be a symlink or other non-regular file.
- The output parent must resolve inside the project, so a symlinked delivery
  directory cannot smuggle the certified manifest outside the project tree.

This does not change non-certified status-snapshot manifests. It only fences the
`best_certified_result` publication surface.

## Regression

New tests:

- `test_v78_delivery_manifest_export_rejects_certified_best_result_to_noncanonical_output_path`
- `test_v78_write_certified_delivery_manifest_rejects_direct_best_result_payload`
- `test_v78_delivery_manifest_export_rejects_symlink_canonical_output_for_best_result`

The proof-obligation gate now structurally requires the canonical-output helper,
raw writer guard with no certified-payload override, regular canonical output
check, canonical direct atomic write, and the V78 regressions under
`PO-CERTIFIED-EXPORT-SURFACE`.

Validation commands used for this patch:

```bash
python scripts/check_p1_2_proof_obligations.py
python -m pytest -p no:randomly -q src/tests/test_delivery_manifest.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/phase3b/b5a/test_b5_anchor_sprint.py
```

## Closure position

Architecture status: acceptable with the V78 repair. P1.2's repeated findings do
not indicate that the cut-family/LBBD solver architecture itself is wrong. They
showed that the certified delivery-evidence publication boundary needed to be
made explicit and canonical. After V78, the publication side has one public
verifier and one canonical manifest writer path for certified payloads.

Residual policy status: P1.2 remains blocked by the manual close gate. V78 is a
safety patch and audit anchor update only. It does not claim owner clean-review
credit and does not open P1.3B.
