# P1.2 V74 Certified Surface Authority Hardening

V73 correctly moved public `CERTIFIED` publication into one verifier, but the
review found one remaining architectural wrinkle: the verifier still accepted
caller-supplied in-memory campaign and manifest payloads as if they were the
repository's public evidence. That is safe for the current inspector path, but it
leaves a future sibling caller enough rope to publish a stale or forged in-memory
view while the on-disk checkpoint or delivery manifest says something else.

## Finding

The vulnerable pattern was not in the exact proof kernel. It was in the boundary
between proof state and public read surfaces:

1. `verify_certified_delivery_surface(..., delivery_manifest=payload)` could
   validate `payload` without proving that it matched
   `data/solutions/certified_delivery_manifest.json`.
2. `verify_certified_delivery_surface(..., campaign_state=state)` could validate
   `state` without proving that it matched the checkpoint at `campaign_path`.
3. `_resolve_resume_validation_reason` could accept a caller's
   `campaign_resume_compatible=True` as authoritative instead of recomputing
   exact artifact hashes.
4. Certified JSON artifact readers used normal `json.loads`, which silently
   accepts duplicate keys and JSON constants such as `NaN`. That means a raw
   artifact could be ambiguous while its parsed last-key-wins projection still
   matched the expected object.

Each item is a false-negative shape: the public verifier could say “current” for
an object graph that was not the current disk surface.

## Fix

V74 makes disk the authority for public `CERTIFIED` surfaces:

- `src/search/certified_surface.py` now resolves the campaign checkpoint from
  `campaign_path`, requires it to be a regular in-repo file, strict-loads it, and
  fails closed when the caller's in-memory state differs from disk.
- The same verifier strict-loads the delivery manifest from
  `data/solutions/certified_delivery_manifest.json`, rejects non-regular paths,
  and fails closed when a caller-supplied manifest payload differs from disk.
- The verifier recomputes exact artifact hashes before publication and reports
  `provided_exact_artifact_hashes_stale` if a caller passes stale hashes.
- Certified delivery artifact readers reject duplicate JSON keys and non-finite
  JSON constants before comparing `final_solution.json` or
  `optimal_blueprint.json` against the canonical projection.

The verifier still returns a verdict rather than throwing for public readers.
That keeps inspector and B5A fail-closed and explainable.

## Regression coverage

New tests cover the authority boundary directly:

- `test_v74_certified_surface_rejects_memory_manifest_when_disk_manifest_stale`
- `test_v74_certified_surface_rejects_memory_campaign_when_disk_checkpoint_differs`
- `test_v74_certified_surface_recomputes_exact_hashes_even_when_caller_claims_resume_ok`
- `test_v74_inspector_rejects_duplicate_key_delivery_manifest`
- `test_v74_delivery_manifest_rejects_duplicate_key_final_solution_artifact`

Validation command used for this patch:

```bash
python scripts/check_p1_2_proof_obligations.py
python -m pytest -p no:randomly \
  src/tests/test_delivery_manifest.py \
  src/tests/test_exact_campaign_inspector.py \
  src/tests/test_v62_candidate_frontier_contract.py \
  src/tests/test_v63_terminal_evidence_contract.py \
  src/tests/phase3b/b5a/test_b5_anchor_sprint.py -q
```

`pytest-randomly` is disabled here because the sandbox dependency set triggers a
third-party NumPy seeding error outside the P1.2 code under review. With that
environment noise removed, the targeted security regression set passes.
