# Project Knowledge Layer

This directory is the neutral control layer for the project knowledge tree. It is not a third content tree; it holds the registry that binds abstract subjects to their projections in both `docs/` and `cc_context/memory/`.

The intended model is:

```text
abstract subjects / single source fields
├── docs/ projection: stable project expression
└── cc_context/memory/ projection: collaboration continuity
```

`docs/` answers what the project is, what the current contract is, how it is verified, how it is delivered, and where historical material lives. `cc_context/memory/` answers what the previous working window knew, which mistakes were corrected, which user/process constraints matter, which old statements require distrust, and what the next window should read first.

Use `scripts/sync_doc_subjects.py --check` before publishing. Use `--sync` after editing a subject field, or `--absorb` after intentionally editing a projection block from a current subject hash.

Canonical registry:

```text
cc_context/knowledge/PROJECT_SUBJECT_PROJECTIONS.json
```
