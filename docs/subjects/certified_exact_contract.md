# Subject: certified exact contract

This subject carries the context-independent exactness contract. Concrete docs may present pieces of it, but they should not invent local variants.

Certified exact work is grounded in four frozen preprocessing/source-of-truth artifacts and strict separation between exact and exploratory paths. The current GitHub checkout is intentionally lightweight: the large `data/preprocessed/candidate_placements.json` artifact is required for certified exact runs but is not present in current `main` until restored from archive or history. The solver objective is lexicographic maximum empty rectangle: maximize area first, then maximize minimum side. The cut-family LBBD path may add sound Benders cuts, but it must not smuggle exploratory assumptions into certified feasibility or proof objects.

<!-- SUBJECT-FIELD:frontdoor_contract START -->
Certified exact mode is separate from exploratory tooling. The exact objective is `max_lex(area, min_side)`, and exploratory caps or sidecar hints must never become certified feasibility bounds. The frozen source-of-truth inputs are `rules/canonical_rules.json`, required external artifact `data/preprocessed/candidate_placements.json`, checked-in `data/preprocessed/mandatory_exact_instances.json`, and checked-in `data/preprocessed/generic_io_requirements.json`.
<!-- SUBJECT-FIELD:frontdoor_contract END -->

<!-- SUBJECT-FIELD:sot_contract START -->
Frozen source-of-truth JSON files are byte-hash gated by `scripts/preflight_gate.py` when present. In the lightweight GitHub checkout, `data/preprocessed/candidate_placements.json` is an external large artifact: expected size `45,773,799` bytes, expected SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`, regenerated with `python src/placement/placement_generator.py` or restored from a clean archive containing the 2026-06-12 preprocess F-01/F-02 repair. The previous size `53,594,995` bytes / SHA256 `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` artifact is superseded and hash-incompatible. If a hash-gated JSON appears modified only because of CRLF/LF conversion, restore LF bytes rather than updating the expected hash. Semantic changes to those artifacts are `PROJECT_LOCK.md`-level decisions.
<!-- SUBJECT-FIELD:sot_contract END -->

<!-- SUBJECT-FIELD:cut_lifecycle_contract START -->
Cut-family LBBD work must respect the cut object lifecycle: generation, validation, replay, quarantine, storage, and master application are separate trust steps. `step_8_apply_to_master` is intentionally the unresolved integration boundary until the true master-integration phase starts.
<!-- SUBJECT-FIELD:cut_lifecycle_contract END -->
