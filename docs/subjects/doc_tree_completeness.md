# Subject: documentation tree completeness

This subject defines what **complete closeout** means for the documentation tree. It is intentionally narrower than a claim that every historical sentence in the archive is semantically fresh. The archive remains historical evidence. Completeness means the living documentation surface has an explicit subject/projection architecture, a manifest of owned surfaces, and a preflight-enforced checker that detects unregistered growth and projection drift.

<!-- SUBJECT-FIELD:definition START -->
A documentation-tree closeout is complete when the living surface is governed by explicit subjects, every concrete projection is registered and synchronized, every top-level documentation surface is classified, and the closure criteria are enforced by `scripts/check_doc_tree_completeness.py` plus preflight. It does **not** mean that historical archives are rewritten into present-tense prose.
<!-- SUBJECT-FIELD:definition END -->

<!-- SUBJECT-FIELD:done_criteria START -->
Done criteria: subject/projection sync is clean; no unregistered projection blocks exist; every subject field has at least one projection; `docs/` top-level files/directories, `docs/项目说明/` chapters, `docs/research/` first-level archive directories, and `specs/*.md` are all listed in `docs/DOC_TREE_COMPLETENESS.json`; required front-door projection slots exist; and `python scripts/check_doc_tree_completeness.py` passes.
<!-- SUBJECT-FIELD:done_criteria END -->

<!-- SUBJECT-FIELD:preflight_contract START -->
Preflight treats documentation-tree completeness as a hard gate: run `python scripts/check_doc_tree_completeness.py` after adding, moving, or deleting documentation surfaces, and update the manifest only when the new surface has a declared role and authority boundary.
<!-- SUBJECT-FIELD:preflight_contract END -->
