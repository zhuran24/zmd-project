# docs/ — documentation subject/projection front door

<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary START sha256:e99ba762ef5fb654e50fe091103cde7cff8cee13657021cc04d593d5bb9d3954 -->
The documentation tree is organized around **subjects** and **projections**. Subjects live in `docs/subjects/` as context-independent sources; concrete docs and memory nodes carry registered projection blocks that are synchronized by `scripts/sync_doc_subjects.py`. This replaces copy-based current-status prose with a small transclusion graph.
<!-- DOC-SUBJECT:doc_tree_architecture FIELD:docs_readme_summary END -->

## High-level routes

- `docs/subjects/` — abstract subject layer; edit these when the context-independent truth changes.
- `cc_context/knowledge/PROJECT_SUBJECT_PROJECTIONS.json` — repo-wide subject-to-projection registry for docs and memory.
- `docs/SUBJECT_TREE.md` — architecture and maintenance runbook.
- `docs/DOC_TREE_COMPLETENESS.md` — explicit done criteria for documentation-tree closeout.
- `docs/项目说明/` — living project book.
- `docs/research/` — research, review, and historical archive.
- `specs/` — formal certified-path specifications.


## Documentation vs memory

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:docs_role START sha256:33a68fa34851c05416e51ad86e69e80c86595e6cf05b70a8d248bac6bb916c63 -->
The documentation tree is the stable project surface. It answers: what the project is, what the current contract is, how it is verified, how it is delivered, and where historical material lives. It should be publishable, reviewable, and low-noise.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:docs_role END -->

The companion memory projection lives under `cc_context/memory/`; see `cc_context/memory/project_knowledge_tree_architecture.md` for the GPT handoff side of the same subject.

## Frozen artifact warning

<!-- DOC-SUBJECT:certified_exact_contract FIELD:sot_contract START sha256:7d54b0d99a9f208e7b36757aec06c1851a9aea69cd51c7d3e76eceabb59ae4a2 -->
Frozen source-of-truth JSON files are byte-hash gated by `scripts/preflight_gate.py` when present. In the lightweight GitHub checkout, `data/preprocessed/candidate_placements.json` is an external large artifact: expected size `53,594,995` bytes, expected SHA256 `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f`, recoverable from `C:\22957\download\zmd.7z` or historical commit `f58f0e2`. If a hash-gated JSON appears modified only because of CRLF/LF conversion, restore LF bytes rather than updating the expected hash. Semantic changes to those artifacts are `PROJECT_LOCK.md`-level decisions.
<!-- DOC-SUBJECT:certified_exact_contract FIELD:sot_contract END -->

## Completeness gate

<!-- DOC-SUBJECT:doc_tree_completeness FIELD:preflight_contract START sha256:f5599b3201fb6b031d765fe0c39f369525e6cd7f9c47155849058fc9c75de39f -->
Preflight treats documentation-tree completeness as a hard gate: run `python scripts/check_doc_tree_completeness.py` after adding, moving, or deleting documentation surfaces, and update the manifest only when the new surface has a declared role and authority boundary.
<!-- DOC-SUBJECT:doc_tree_completeness FIELD:preflight_contract END -->

## Maintenance commands

```bash
python scripts/sync_doc_subjects.py --check
python scripts/sync_doc_subjects.py --sync
python scripts/sync_doc_subjects.py --absorb
```

Use `--sync` after editing a subject field. Use `--absorb` only when a projection block was intentionally edited and should update the subject.
