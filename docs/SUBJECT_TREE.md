# Documentation subject/projection tree

The documentation tree is now governed by a subject/projection layer rather than by isolated file copies. The idea mirrors the CC memory instance/projection model: the abstract subject holds the context-independent truth, and concrete docs are projections that serve particular readers.


## Logical project knowledge tree

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer START sha256:9dd6b559dd17a70fab730793a77d2e4a91c27eedcdfbf1bf81fdeba5f658592f -->
The project uses **one logical knowledge tree with two physical projections**. `docs/` is the stable documentation projection; `cc_context/memory/` is the collaboration-continuity projection. Neither tree is allowed to become a second independent truth source: volatile living claims should be promoted into a subject field and projected to every surface that needs them.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer END -->

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:projection_rule START sha256:671f0705419a7ca28ff595ea1437d45799031db2ba94a84ac2ec8645b59a4f03 -->
Living/current claims should flow through subject fields and registered projection slots. Historical review notes, raw transcripts, dated decisions, and evidence archives should remain evidence nodes: they may link to subjects, but they should not be auto-rewritten into present-tense truth.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:projection_rule END -->

<!-- DOC-SUBJECT:doc_tree_architecture FIELD:governance_gate_summary START sha256:7adb5eada37f191c32fc8321b84bdc8a2b9208aa016d0c3e37a82790430a43bb -->
Preflight runs `python scripts/sync_doc_subjects.py --check`. A changed subject with stale projections, or an edited projection that has not been absorbed into its subject, blocks the gate instead of silently drifting.
<!-- DOC-SUBJECT:doc_tree_architecture FIELD:governance_gate_summary END -->

## Components

1. **Subjects** live in `docs/subjects/*.md`. They contain `SUBJECT-FIELD` blocks.
2. **Projection registry** lives in `docs/DOC_SUBJECT_PROJECTIONS.json`. It declares every concrete document projection.
3. **Projection slots** live in concrete Markdown files and are bounded by `DOC-SUBJECT` markers.
4. **Sync tool** lives at `scripts/sync_doc_subjects.py`.
5. **Preflight gate** runs `python scripts/sync_doc_subjects.py --check`.

## Complete closeout criteria

<!-- DOC-SUBJECT:doc_tree_completeness FIELD:done_criteria START sha256:8722751f983889bc1e2f736da422bb7447fedb0b2d78594570db6cf5c7501ed4 -->
Done criteria: subject/projection sync is clean; no unregistered projection blocks exist; every subject field has at least one projection; `docs/` top-level files/directories, `docs/项目说明/` chapters, `docs/research/` first-level archive directories, and `specs/*.md` are all listed in `docs/DOC_TREE_COMPLETENESS.json`; required front-door projection slots exist; and `python scripts/check_doc_tree_completeness.py` passes.
<!-- DOC-SUBJECT:doc_tree_completeness FIELD:done_criteria END -->

## Edit workflow

When the abstract fact changes:

```bash
# edit docs/subjects/<subject>.md
python scripts/sync_doc_subjects.py --sync
python scripts/sync_doc_subjects.py --check
```

When a concrete document's projection is the place where you discover the better wording or changed fact:

```bash
# edit the text inside one DOC-SUBJECT block
python scripts/sync_doc_subjects.py --absorb
python scripts/sync_doc_subjects.py --check
```

The checksum in the projection start marker is what makes `--absorb` safe: it only accepts edits made from a projection that was synced to the latest subject. If both subject and projection moved independently, the tool refuses and asks for a human merge.

## What this does not try to solve yet

This first layer handles exact field transclusion. It does not attempt semantic NLP over arbitrary prose. Historical archive values remain legal when they are dated and clearly historical. New volatile present-tense claims should be promoted to a subject field instead of being copied into free prose.
