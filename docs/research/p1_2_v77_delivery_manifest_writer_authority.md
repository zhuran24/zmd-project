# P1.2 V77 delivery manifest writer authority review

Date: 2026-06-10

Review anchor: `v77_delivery_manifest_writer_authority`

## Result

No new architecture-breaking flaw was found in the public CERTIFIED surface architecture. The V73-V76 spine remains the correct architecture: public readers must consume the centralized `certified_surface_verifier_v1` verdict from `src/search/certified_surface.py`, not local checkpoint fields or a standalone manifest claim.

The remaining issue was a sibling pre-publication writer seam. The central public verifier already rejected a caller-supplied memory campaign that did not match the campaign checkpoint on disk. However, the direct writer in `src/io/delivery_manifest.py::export_certified_delivery_manifest` could still build and write a certified-looking `certified_delivery_manifest.json` with `best_certified_result` from the in-memory `campaign_state` while its `artifacts.campaign_state.sha256` pointed at a different disk checkpoint.

That did not defeat the current public verifier, but it left a false-negative trap for future or direct manifest consumers: a manifest file could exist on disk with `best_certified_result` even though the referenced checkpoint was not the authority for that result.

## Finding

The writer path used the caller's `campaign_state` as authority when building `best_certified_result`. It did validate terminal evidence, delivery artifacts, and exact artifact hash compatibility, but it did not first prove that the supplied state was byte-semantically equivalent to the regular in-project checkpoint selected by `campaign_path`.

A minimal failing shape before V77 was:

1. Write an authoritative `data/checkpoints/exact_campaign_state.json` with terminal `INFEASIBLE`.
2. Build a separate in-memory campaign with terminal full-frontier `CERTIFIED` evidence and matching `final_solution.json` plus `optimal_blueprint.json`.
3. Call `export_certified_delivery_manifest(project_root=..., campaign_state=memory_campaign.state, campaign_path=disk_campaign.path)`.
4. The writer emitted `certified_delivery_manifest.json` with `best_certified_result` from memory, while the campaign artifact table described the different disk checkpoint.

`verify_certified_delivery_surface(...)` rejected the same shape as `campaign_state_payload_mismatch`, so the public gate was still correct. The writer boundary was nevertheless too permissive for a close candidate because a certified delivery artifact should not be able to advertise memory-only authority.

## Patch

V77 adds a disk-authority check to `src/io/delivery_manifest.py` before any manifest payload with `best_certified_result` can be returned or written:

- `build_certified_delivery_manifest(...)` now resolves `project_root` and `campaign_path` through one helper.
- `_validate_campaign_state_matches_disk_authority(...)` requires the checkpoint path to resolve inside the project.
- The checkpoint must be a regular file at the caller-selected path, so symlinked checkpoint paths are rejected before JSON is loaded.
- The checkpoint is loaded with the same strict JSON loader used by manifest artifact validation, so duplicate keys and non-finite JSON constants remain rejected.
- The disk checkpoint payload must be JSON-equivalent to the supplied `campaign_state`.

The guard only activates when `best_certified_result` would be present. Non-certified terminal manifests can still be used as fail-closed status snapshots, but they cannot carry certified delivery evidence.

## Regression

`test_v77_delivery_manifest_export_rejects_memory_campaign_when_disk_checkpoint_differs` reproduces the old seam and now expects the writer to fail with `disk checkpoint authority` before `certified_delivery_manifest.json` is created.

`test_v77_delivery_manifest_export_rejects_symlink_campaign_checkpoint_for_best_result` locks the regular-file side of the writer authority rule, so a symlink path cannot become a certified checkpoint authority even when it points at the correct JSON payload.

The P1.2 proof-obligation gate now lists the V77 regressions under `PO-CERTIFIED-EXPORT-SURFACE`, and the current phase anchor is advanced to `v77_delivery_manifest_writer_authority`.

Validation commands used for this patch:

```bash
python scripts/check_p1_2_proof_obligations.py
python -m pytest -q src/tests/test_delivery_manifest.py \
  src/tests/test_p1_2_proof_obligations.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/phase3b/b5a/test_b5_anchor_sprint.py
```

## Closure position

Architecture status: acceptable. The project now has one public CERTIFIED gate and the direct manifest writer no longer creates a certified-looking artifact from memory-only state.

Residual policy status: P1.2 remains blocked by the manual close gate. V77 is a safety patch and audit anchor update only. It does not claim owner clean-review credit and does not open P1.3B.
