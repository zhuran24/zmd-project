# 09. Known non-claims and TCB

## Known non-claims

- No claim that all bugs are impossible.
- No claim that future P1.3B production integration is safe.
- No claim that `step_8_apply_to_master` production integration is complete.
- No claim that owner clean-review count has been satisfied.
- No claim that the repo can automatically open P1.3B.
- No claim that Python, OS, filesystem, pytest, or human review are mathematically infallible.

## TCB

- Python runtime executing scripts/check_p1_2_proof_obligations.py
- current Git/source tree supplied to the checker
- filesystem path and regular-file semantics used by the checker
- pytest/CI exit status reporting faithfully when invoked
- human reviewer interpretation of the 2026-06-17 P1.2 boundary files

## Operational assumptions

- Python: `Python 3.13.5`
- Dependency bundle SHA256: `84f2bdf40edc4c7f5d6bb947e4fbb5f3ffd8c244c839095236ad1548ad0dee54`
- The phase gate remains `blocked_manual_review_count` and `next_allowed=False` unless an owner manual decision opens the next phase.
- Review receipts remain informational and cannot open P1.3B.
