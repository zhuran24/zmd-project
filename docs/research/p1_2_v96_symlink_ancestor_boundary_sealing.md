# P1.2 V96 symlink-ancestor boundary sealing

Date: 2026-06-11

Review anchor: `v96_symlink_ancestor_boundary_sealing`

## Result

Sixteenth overnight independent review round: one algorithmic/soundness
finding, reproduced locally before patching. Owner clean-streak count
remains 0.

## Finding

### F-01 (proof obligation bypass): symlinked ancestor directories escaped the artifact authority boundary

V84 rejects artifacts that are themselves symlinks, but a symlinked parent
directory (e.g. replacing `data/preprocessed` or `data/solutions` with a link
pointing outside the project) still resolved: exact artifact hashes and the
public manifest/final_solution could be served from out-of-project content
under canonical in-project path names, and the central verifier stayed
`publishable=True` (both probes reproduced). Certified exact artifacts and
public delivery-surface artifacts now reject any symlinked path component
between the project root and the file.

## Regression

New: `test_v96_exact_artifact_hashes_reject_symlinked_parent_project_authority`
and `test_v96_certified_surface_rejects_manifest_under_symlinked_solutions_parent`
(from the reviewer bundle, locally re-verified). Zero collateral: full suite
at the documented environmental baseline (2828 passed).

## Review provenance

Reviewer report/probes/outputs archived under the 2026-06-11 12:3x
`补丁包/gpt_deliveries/` directory.

## Closure position

Sealed fail-closed; the filesystem authority boundary now covers the whole
path, not just the leaf. Residuals carried forward: proof-carrying candidate
certificates (future work), `EXACT_SUBPROBLEM_PARAMS` on watch.

Residual policy status: P1.2 remains blocked by the manual close gate. V96
does not claim owner clean-review credit and does not open P1.3B.
