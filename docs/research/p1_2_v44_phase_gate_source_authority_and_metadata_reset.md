# P1.2 V44 phase-gate source authority and metadata reset

Package: v44_candidate
Review type: independent_full_external
Outcome: major_soundness_findings_found
Major or soundness findings: 2
Resets counter: true

V44 found two phase-gate provenance blockers in the post-V43 candidate:

1. `current_review_package.source_head` was still accepted through Git authority roots that were not self-contained in the source tree. A `.git` file could point at a sibling repository, and `.git/objects/info/alternates` could make `git rev-parse HEAD^{commit}` plus `git cat-file -t` prove a commit object that was not carried by the current source package. A bare gitdir shape also made `_project_git_head()` return `None`, leaving the declared source head unchecked.
2. Evidence metadata hardening was still line-local and single-unescape. Multiline HTML tables, nested HTML entities, escaped fullwidth delimiters, escaped blockquotes, and CSV-like metadata could leave stale visible package metadata in clean-review evidence while the ASCII colon lines below satisfied the machine check.

The follow-up patch centralizes these as machine gates in `scripts/check_phase_review_gate.py`, adds regressions in `src/tests/test_phase_review_gate.py`, and anchors those regressions under `PO-PHASE-GATE-PROVENANCE`.
