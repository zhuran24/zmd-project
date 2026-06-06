# cc_context/knowledge/ — shared subject graph

This directory is the project knowledge-tree control plane. It is intentionally
not a third documentation tree: it holds machine-readable wiring for the single
logical subject graph that projects into both `docs/` and `cc_context/memory/`.

- `PROJECT_SUBJECT_PROJECTIONS.json` is the authoritative projection registry.
- `docs/subjects/*.md` still holds the human-editable subject bodies.
- `scripts/sync_doc_subjects.py` checks, syncs, or absorbs registered projection
  blocks across documentation and memory surfaces.

The naming is deliberately neutral. A projection target may be a public-facing
document, a root runbook, or a GPT handoff memory node; the registry owns the
cross-tree linkage rather than belonging exclusively to `docs/`.
