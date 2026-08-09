# P1.2 V73 Certified Surface Verifier Consolidation

V72 closed the known sibling bypasses, but the review pattern showed a deeper
risk: multiple public read surfaces still had enough local predicate logic to
invent their own meaning of `CERTIFIED`. V73 consolidates that authority into a
single verifier module.

## Contract

`src/search/certified_surface.py::evaluate_certified_delivery_surface` is the
public gate for terminal certified visibility. A caller may expose terminal
`terminal_full_frontier_certified=True` only when the verifier can re-derive all
of the following from the current repository state:

1. current exact artifact hashes are readable;
2. the campaign checkpoint is resume-compatible with those hashes;
3. the campaign has valid strict terminal full-frontier certified evidence;
4. `final_solution.json` is raw-equal to the checkpoint `final_result`;
5. `optimal_blueprint.json` is raw-equal to the canonical projection of that
   `final_result`;
6. the delivery manifest is a regular file and readable as a JSON object;
7. the delivery manifest matches the current checkpoint/artifact projection, with
   only `metadata.export_timestamp` excluded from currentness comparison.

The verifier returns a `CertifiedSurfaceVerdict`, not just a boolean. Inspector
and B5A surfaces use the same verdict for their campaign and manifest summaries,
so a stale manifest cannot leave one surface showing `CERTIFIED` while another
surface hides it.

## Public-surface rule

Candidate-level `CERTIFIED` remains an incumbent status. Terminal checkpoint
`CERTIFIED` remains proof evidence. Public delivery `CERTIFIED` is only the
sealed conjunction produced by the certified surface verifier.

This intentionally keeps the exact/LBBD proof kernel unchanged while moving the
certified delivery authority into one narrow gate.
