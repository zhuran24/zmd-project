# Subject: certified exact contract

This subject carries the context-independent exactness contract. Concrete docs may present pieces of it, but they should not invent local variants.

Certified exact work is grounded in four frozen preprocessing/source-of-truth artifacts and strict separation between exact and exploratory paths. The solver objective is lexicographic maximum empty rectangle: maximize area first, then maximize minimum side. The cut-family LBBD path may add sound Benders cuts, but it must not smuggle exploratory assumptions into certified feasibility or proof objects.

<!-- SUBJECT-FIELD:frontdoor_contract START -->
Certified exact mode is separate from exploratory tooling. The exact objective is `max_lex(area, min_side)`, and exploratory caps or sidecar hints must never become certified feasibility bounds. The frozen source-of-truth artifacts are `rules/canonical_rules.json`, `data/preprocessed/candidate_placements.json`, `data/preprocessed/mandatory_exact_instances.json`, and `data/preprocessed/generic_io_requirements.json`.
<!-- SUBJECT-FIELD:frontdoor_contract END -->

<!-- SUBJECT-FIELD:sot_contract START -->
Frozen source-of-truth JSON files are byte-hash gated by `scripts/preflight_gate.py`. If a hash-gated JSON appears modified only because of CRLF/LF conversion, restore LF bytes rather than updating the expected hash. Semantic changes to those artifacts are `PROJECT_LOCK.md`-level decisions.
<!-- SUBJECT-FIELD:sot_contract END -->

<!-- SUBJECT-FIELD:cut_lifecycle_contract START -->
Cut-family LBBD work must respect the cut object lifecycle: generation, validation, replay, quarantine, storage, and master application are separate trust steps. `step_8_apply_to_master` is intentionally the unresolved integration boundary until the true master-integration phase starts.
<!-- SUBJECT-FIELD:cut_lifecycle_contract END -->
