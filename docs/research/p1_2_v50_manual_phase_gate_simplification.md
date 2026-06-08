# P1.2 V50 manual phase-gate simplification

Date: 2026-06-08

Status: implemented as a gate simplification, not as a clean review.

## Summary

V47-V50 showed that the strict JSON receipt protocol had successfully narrowed
the old Markdown/HTML/XML/Git-authority attack surface, but the repository was
still trying to prove a human governance rule: three consecutive clean external
reviews.  That made the phase gate itself a security protocol with its own
state-machine bugs.

This patch keeps the owner standard intact:

- Phase 1.2 still requires three consecutive clean full reviews before P1.3B.
- P1.3B remains blocked by default.
- `src/cuts/lifecycle.py::step_8_apply_to_master` remains fail-closed while the
  gate is blocked.

It removes the repo-derived authority that caused the V47-V50 loop:

- the repository no longer computes 0/3, 1/3, 2/3, or 3/3;
- review receipts are informational records only;
- Markdown reports, JSON receipts, package metadata, source-tree manifests, and
  package-internal Git authority cannot open P1.3B;
- only an explicit owner manual decision can change `next_phase_entry.allowed`
  to true.

## Why this is not a relaxation

The old automatic counter gave a stronger-looking guarantee than it could
honestly provide.  V47-V50 found multiple ways for receipt or history state to
misrepresent clean credit.  Continuing down that path would require auditing the
clean-review gate as a separate high-security protocol before it could be used
to audit P1.2.

The simplified gate is narrower and more honest.  It does not claim to know
whether the owner has counted three clean reviews.  It only enforces fail-closed
repository state until the owner writes an explicit manual decision.

## Review classification after this patch

Future reviewers should not attack the old receipt-derived automatic counter as
if it were still a release authority.  It is not.

A finding should block manual clean-review credit if it is one of:

- an unsound cut;
- a certified false negative;
- a proof-obligation bypass;
- a fake certified-exact claim;
- a reachable phase-gate false-ready path under the simplified manual gate.

Review-infrastructure observations that do not create a reachable false-ready
transition under the simplified gate should be recorded as hardening suggestions,
not as automatic P1.2 algorithmic-counter resets.

## Operational rule

`python scripts/check_phase_review_gate.py` should pass while reporting blocked
manual state.  `python scripts/check_phase_review_gate.py --require-ready
phase_1_2_spike_close` should fail until the owner intentionally opens P1.3B.
