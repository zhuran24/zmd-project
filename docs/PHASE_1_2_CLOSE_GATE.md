# Phase 1.2 close gate

Current gate state: BLOCKED.

Phase 1.2 spike close is deliberately not treated as complete yet. The current review anchor is v28, and v28 found confirmed real soundness holes. That resets the consecutive-clean counter to zero.

The close policy is:

- require 3 consecutive independent full reviews with zero major or soundness findings;
- reset the counter whenever a full review finds a major, high, critical, P0/P1, or soundness-class issue;
- do not enter P1.3B `PoseBoolExactMaster` LBBD master integration until this gate is closed.

Machine-readable state lives in:

```text
data/review_gates/phase_1_2_spike_close.json
```

The everyday consistency check is:

```bash
python scripts/check_phase_review_gate.py
```

This health check should pass while the gate is blocked, because "blocked pending clean reviews" is the honest current state. It should fail only if the machine-readable state contradicts itself, required evidence files disappear, front-door docs stop carrying the blocked status, or someone marks the gate closed without the required clean-review count.

The explicit phase-transition check is:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

At the current baseline this command is expected to fail. It should become green only after the review counter reaches 3/3 and `next_phase_entry.allowed` is true.

When v29 and later reviews are completed, update the JSON counter and review history. Only after the counter reaches three consecutive clean full reviews should `next_phase_entry.allowed` become `true` and `status` become `closed`.
