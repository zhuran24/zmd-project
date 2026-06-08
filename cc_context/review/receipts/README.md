# Review receipts

This directory is reserved for optional review receipt records.  As of the V50
manual phase-gate simplification, receipts are **informational only**: they may
help the owner audit a review package, but they do not grant clean-review credit
and they cannot open P1.3B.

The project-owner standard still requires three consecutive clean full reviews
before P1.3B.  That count is owner-maintained outside the repo.  The repository
only enforces fail-closed state until an explicit owner manual decision is
recorded in `data/review_gates/phase_1_2_spike_close.json`.

Do not put API keys, private reviewer notes, or free-form metadata parsers here.
