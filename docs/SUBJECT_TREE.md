# Documentation subject/projection tree

The documentation tree is now governed by a subject/projection layer rather than by isolated file copies. The idea mirrors the CC memory instance/projection model: the abstract subject holds the context-independent truth, and concrete docs are projections that serve particular readers.

<!-- DOC-SUBJECT:doc_tree_architecture FIELD:governance_gate_summary START sha256:7adb5eada37f191c32fc8321b84bdc8a2b9208aa016d0c3e37a82790430a43bb -->
Preflight runs `python scripts/sync_doc_subjects.py --check`. A changed subject with stale projections, or an edited projection that has not been absorbed into its subject, blocks the gate instead of silently drifting.
<!-- DOC-SUBJECT:doc_tree_architecture FIELD:governance_gate_summary END -->

## Components

1. **Subjects** live in `docs/subjects/*.md`. They contain `SUBJECT-FIELD` blocks.
2. **Projection registry** lives in `docs/DOC_SUBJECT_PROJECTIONS.json`. It declares every concrete document projection.
3. **Projection slots** live in concrete Markdown files and are bounded by `DOC-SUBJECT` markers.
4. **Sync tool** lives at `scripts/sync_doc_subjects.py`.
5. **Preflight gate** runs `python scripts/sync_doc_subjects.py --check`.

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
