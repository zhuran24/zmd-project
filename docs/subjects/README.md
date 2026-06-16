# Documentation subjects

This directory is the abstract subject layer of the documentation tree.

A **subject** is the context-independent source for a fact, contract, or governance rule that appears in more than one concrete document. Concrete documents should not hand-copy those facts. They should carry a registered projection block that is synchronized by `scripts/sync_doc_subjects.py`.

The subject/projection rules are:

1. Edit a subject field when the abstract fact changes, then run `python scripts/sync_doc_subjects.py --sync`.
2. Edit a projection block only when you intentionally want the concrete document to propose a subject change, then run `python scripts/sync_doc_subjects.py --absorb`.
3. Run `python scripts/sync_doc_subjects.py --check` before committing. Preflight runs the same check.
4. Do not copy current phase, current counts, frozen source-of-truth claims, or documentation governance text outside registered projection blocks unless the text is explicitly historical.

Projection blocks use this marker format:

```md
<!-- DOC-SUBJECT:<subject_id> FIELD:<field_id> START sha256:<hash> -->
...
<!-- DOC-SUBJECT:<subject_id> FIELD:<field_id> END -->
```

Subject fields use this marker format inside `docs/subjects/*.md`:

```md
<!-- SUBJECT-FIELD:<field_id> START -->
...
<!-- SUBJECT-FIELD:<field_id> END -->
```

The checksum in each projection marker is the hash of the subject field that last generated the projection. That lets the sync tool distinguish two cases that look similar in a diff:

- subject changed, projection is stale: run `--sync`;
- projection was intentionally edited while its marker still matches the subject: run `--absorb` to update the subject, then fan the change back out to all projections.
