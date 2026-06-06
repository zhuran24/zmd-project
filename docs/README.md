# docs/ — documentation subject/projection front door

<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary START sha256:ca8444165fd1c2128cfdc08a6ad8da370a426d6727028353da593ea29d1768f2 -->
The documentation tree is organized around **subjects** and **projections**. Subjects live in `docs/subjects/` as context-independent sources; concrete docs carry registered projection blocks that are synchronized by `scripts/sync_doc_subjects.py`. This replaces copy-based current-status prose with a small transclusion graph.
<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary END -->

## High-level routes

- `docs/subjects/` — abstract subject layer; edit these when the context-independent truth changes.
- `docs/DOC_SUBJECT_PROJECTIONS.json` — subject-to-document projection registry.
- `docs/SUBJECT_TREE.md` — architecture and maintenance runbook.
- `docs/项目说明/` — living project book.
- `docs/research/` — research, review, and historical archive.
- `specs/` — formal certified-path specifications.

## Frozen artifact warning

<!-- DOC-SUBJECT:certified_exact_contract FIELD:sot_contract START sha256:fc60ac5d700c1afc66190d3e51efc022516405defce1e7c25053cbac2b439fab -->
Frozen source-of-truth JSON files are byte-hash gated by `scripts/preflight_gate.py`. If a hash-gated JSON appears modified only because of CRLF/LF conversion, restore LF bytes rather than updating the expected hash. Semantic changes to those artifacts are `PROJECT_LOCK.md`-level decisions.
<!-- DOC-SUBJECT:certified_exact_contract FIELD:sot_contract END -->

## Maintenance commands

```bash
python scripts/sync_doc_subjects.py --check
python scripts/sync_doc_subjects.py --sync
python scripts/sync_doc_subjects.py --absorb
```

Use `--sync` after editing a subject field. Use `--absorb` only when a projection block was intentionally edited and should update the subject.
