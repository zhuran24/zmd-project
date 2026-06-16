# P1.2 V38 Phase Gate Package Identity Hardening

## Context

The V38 clean-review pass found that phase-gate clean evidence could still be
bound to a self-declared `review_history[].package` string instead of the
actual current review package. That left a fake-ready path where three clean
reviews used unique files, unique content digests, and unique package labels,
but none of the evidence proved it was reviewing the uploaded `zmd_N.7z`
archive identity.

## Decision

The gate now treats clean-review package identity as a fail-closed prerequisite
for counting clean credit. A blocked gate with no post-reset clean reviews does
not need current package metadata. Once a clean full external review is claimed,
the gate requires a `current_review_package` object and every clean evidence file
must carry matching structured metadata:

- `package`
- `archive_name`
- `archive_sha256`
- `archive_size_bytes`
- `source_head`
- `source_list_identity`

All post-reset clean reviews must reference that same current package key. The
three clean reviews are still required to use distinct evidence paths, distinct
physical files, and distinct content digests.

## Rationale

Putting the final archive SHA256 inside the repository before packaging is
self-referential for full project archives. The safer invariant is therefore:
the machine gate cannot count clean review credit until the current package
identity has been provided and every clean evidence artifact exactly matches it.
Missing, malformed, duplicate-key, stale, or body-only package evidence remains
blocked instead of being interpreted as clean.

## Required Regression Family

The P1.2 provenance proof obligation now anchors these regression classes:

- reject clean reviews when `current_review_package` is absent;
- reject clean review package labels that differ from the current package;
- reject evidence that only mentions the package name but omits archive
  SHA256, size, source HEAD, or source-list identity;
- reject duplicate JSON keys inside the current package metadata;
- preserve V38's hidden-major/outcome/count/reset consistency checks.
