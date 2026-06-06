# Documentation tree completeness contract

This file is the closeout contract for the documentation tree. It answers the question: **what makes the documentation tree complete enough to stop reorganizing and start maintaining?**

## Definition

<!-- DOC-SUBJECT:doc_tree_completeness FIELD:definition START sha256:e868db72259f760ef7a59cb2e58085f34dc3db789dddacaa3921cb98c78a0b84 -->
A documentation-tree closeout is complete when the living surface is governed by explicit subjects, every concrete projection is registered and synchronized, every top-level documentation surface is classified, and the closure criteria are enforced by `scripts/check_doc_tree_completeness.py` plus preflight. It does **not** mean that historical archives are rewritten into present-tense prose.
<!-- DOC-SUBJECT:doc_tree_completeness FIELD:definition END -->

## Done criteria

<!-- DOC-SUBJECT:doc_tree_completeness FIELD:done_criteria START sha256:8722751f983889bc1e2f736da422bb7447fedb0b2d78594570db6cf5c7501ed4 -->
Done criteria: subject/projection sync is clean; no unregistered projection blocks exist; every subject field has at least one projection; `docs/` top-level files/directories, `docs/项目说明/` chapters, `docs/research/` first-level archive directories, and `specs/*.md` are all listed in `docs/DOC_TREE_COMPLETENESS.json`; required front-door projection slots exist; and `python scripts/check_doc_tree_completeness.py` passes.
<!-- DOC-SUBJECT:doc_tree_completeness FIELD:done_criteria END -->

## Preflight contract

<!-- DOC-SUBJECT:doc_tree_completeness FIELD:preflight_contract START sha256:f5599b3201fb6b031d765fe0c39f369525e6cd7f9c47155849058fc9c75de39f -->
Preflight treats documentation-tree completeness as a hard gate: run `python scripts/check_doc_tree_completeness.py` after adding, moving, or deleting documentation surfaces, and update the manifest only when the new surface has a declared role and authority boundary.
<!-- DOC-SUBJECT:doc_tree_completeness FIELD:preflight_contract END -->

## Boundary of the claim

This is a governance closeout, not a semantic proof over every historical archive sentence. Historical research directories can preserve dated claims, superseded plans, and raw transcript evidence. Living/front-door claims must either be subject projections or point to an explicit authority.

The closeout is therefore complete when the following command passes:

```bash
python scripts/check_doc_tree_completeness.py
```

Preflight runs the same checker. Future documentation changes should be incremental: add a subject field when a context-independent fact needs reuse, add a projection when a concrete document needs that fact, and update `docs/DOC_TREE_COMPLETENESS.json` when a documentation surface is added or removed.
