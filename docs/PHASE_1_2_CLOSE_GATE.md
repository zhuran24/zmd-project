# Phase 1.2 close gate

Current gate state: BLOCKED.

Phase 1.2 spike close is deliberately not treated as complete yet.  The current
review anchor is `v46_review_protocol_redesign`: after V31-V46, findings are now
classified into two counters instead of one undifferentiated reset bucket.

The **algorithmic-soundness counter** is the one that controls P1.3B entry.  It
is still 0/3.  It resets only for reachable algorithmic/soundness findings:
unsound cuts, certified false negatives, proof-obligation bypasses, fake
certified-exact claims, or a real phase-gate false-ready transition into P1.3B.

The **review-infrastructure hardening track** records receipt, report, package,
source-tree, and review-provenance problems.  Those findings still matter, but
they do not automatically reset the algorithmic counter unless the reviewer can
show a reachable false-ready or certified-lifecycle false-negative path.

Future clean-review credit must be bound by strict JSON review receipts.  The
human review report remains free text and is bound by `report_sha256`; it is not
machine authority for archive identity.  Clean-review receipts must bind the
archive name, archive SHA256, archive size, source-tree identity, review result,
reported major/soundness count, report path, report SHA256, and current review
anchor.  Package-internal Git `source_head` is informational only for this gate;
the receipt protocol uses a source-tree manifest identity instead.

Daily consistency check:

```bash
python scripts/check_phase_review_gate.py
```

Entry check for P1.3B:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

At the current baseline this command is expected to fail with clean=0/3 after
`v46_review_protocol_redesign`.  It should become green only after the
algorithmic counter reaches 3/3 and `next_phase_entry.allowed` is true.

The gate also keeps `src/cuts/lifecycle.py::step_8_apply_to_master` fail-closed
until Phase 1.2 is formally closed.  P1.3B master integration must not land while
this close gate is blocked.
