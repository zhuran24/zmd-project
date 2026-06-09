# Phase 1.2 close gate

Current gate state: BLOCKED by default.

Phase 1.2 spike close is deliberately not treated as complete yet.  V50 changed
the gate model: the **three clean full reviews** rule remains a project-owner
standard, but the repository no longer tries to prove or count those reviews
from receipts, Markdown reports, package metadata, source-tree manifests, or
package-internal Git authority.

The previous automatic counter became its own attack surface during V47-V50.
Those rounds found receipt/state-machine false-ready paths rather than new
cut-family algorithmic bugs.  The safer model is now:

- the owner keeps the clean-review count outside the repo;
- review receipts are optional/informational audit records;
- the repo stays fail-closed until an explicit owner manual decision opens
  P1.3B;
- `next_phase_entry.allowed` must remain false without that decision.

## Current review anchor

After V57-V66 and the lifecycle-evidence consolidation, the current review anchor is:

```text
v66_certified_lifecycle_evidence_consolidation
```

Those rounds did not reopen the old automatic receipt/counter gate.  They found
a real certified solver safety surface: certified lifecycle evidence must stay
faithful from exact-safe cut replay through master-domain construction, outer
frontier termination, and certified export surfaces.  V66 splits the previous
oversized replay obligation into four compartments:

- `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS` for strict payloads, condition/domain
  replay, all-or-nothing member resolution, one-to-one master literal encoding,
  and apply-before-register atomicity;
- `PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS` for the full unfiltered
  master-domain and canonical power-witness representation contract, including
  unsafe env fail-closed behavior before session/precheck/project-load side
  effects;
- `PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE` for strict full-frontier exhaustion
  evidence rather than candidate-level or best-effort incumbents;
- `PO-CERTIFIED-EXPORT-SURFACE` for `final_result`, `final_solution`, delivery
  manifest, inspector/report, and wrapper export surfaces.

See `docs/research/p1_2_v56_certified_cut_replay_consolidation.md`,
`docs/research/p1_2_v64_power_witness_representation_env_guard.md`, and
`docs/research/p1_2_v66_certified_lifecycle_evidence_consolidation.md`.

Daily consistency check:

```bash
python scripts/check_phase_review_gate.py
```

Entry check for P1.3B:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

At the current baseline this command is expected to fail because the owner has
not manually opened P1.3B.  That failure is correct: the script is no longer a
3-clean counter, and it cannot prove owner review judgment.

The gate also keeps `src/cuts/lifecycle.py::step_8_apply_to_master` fail-closed
while P1.3B is not manually allowed.  P1.3B master integration must not land
while this close gate is blocked.
