# Validator Release Policy

The following material is withheld until both raw model responses have been captured and hashed:

- `solution_witness.schema.json`;
- `scripts/cleanroom_strict/validate_layout.py`;
- owner adjudications;
- this comparison rubric and all current-method notes;
- reference positive or negative fixtures.

This prevents the checker structure from suggesting a solution decomposition or rule-ownership pattern. Round 1 receives only the external package. Round 2 receives that same package plus the staged Round 2 prompt.

After release, the validator may be used to check concrete witnesses against the manifest-pinned `problem_instance.json`; replacement instance bytes are rejected. A successful report says `LAYOUT_FEASIBLE`; it is evidence only for feasibility and the recomputed best empty rectangle of that fixed layout. It is not evidence that no other layout is better. Any claimed global optimum requires a separate auditable upper-bound argument.

Raw responses, prompts, and manifests should be retained byte-for-byte with SHA-256 digests. Evaluator annotations belong in separate files so that later reviewers can distinguish model output from interpretation.
