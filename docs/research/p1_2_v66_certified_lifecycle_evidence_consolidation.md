# P1.2 V66 certified lifecycle evidence consolidation

Date: 2026-06-09

Status: **postmortem consolidation, not a clean review**.

Current anchor after this consolidation:

```text
v66_certified_lifecycle_evidence_consolidation
```

## Why this consolidation exists

V57-V66 did not reopen the V47-V50 receipt/counter gate problem.  They found a real certified-exact evidence chain that had been too large to keep under the single `PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS` label.

The reviewed surface expanded in a coherent sequence:

```text
strict exact-safe cut payload
→ strict cut condition grammar and metadata
→ current candidate-domain membership
→ full unfiltered master-domain contract
→ certified master/witness representation env guard
→ full-frontier terminal evidence
→ final_result/final_solution/manifest/inspector/wrapper export surfaces
```

That sequence is one proof chain, but it is too broad for one proof obligation.  Treating it as one giant obligation makes future review fuzzy: a finding in terminal export ordering should not be described as another cut replay parser finding.  V66 therefore splits the chain into smaller compartments.

## New P1.2 proof-obligation compartments

### PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS

Exact-safe `BendersCut` replay must be strict, all-or-nothing, and faithfully encoded by the master.

This compartment covers:

- strict JSON and duplicate-key/NaN rejection for replay evidence;
- strict bool/int payload parsing, with Python bool-as-int rejected;
- condition-required power cuts;
- strict `ghost_anchor::(x,y)` condition grammar;
- condition metadata self-consistency;
- current candidate-domain membership for condition anchors;
- missing conflict members fail closed;
- aliasing conflict members fail closed;
- master apply succeeds before cut registration or generated exact-safe counting.

### PO-CERTIFIED-MASTER-DOMAIN-FAITHFULNESS

The actual constructed certified master/witness representation must match the full-domain contract.

This compartment covers:

- persisted `master_domain_contract = full_unfiltered`;
- rejection of filtered or missing master-domain contracts on resume;
- `EXACT_MASTER_GHOST_ANCHOR_FILTER` blocking;
- pose-bool master env blocking while it is not the certified representation;
- power-pole slot override blocking;
- lazy/delegated/forensic power-placement env blocking;
- non-canonical power-witness encoding env blocking;
- blocking before session construction, precheck construction, or project-data load side effects.

### PO-CERTIFIED-FRONTIER-TERMINAL-EVIDENCE

Certified terminal status requires strict full-frontier exhaustion evidence.

This compartment covers:

- candidate-level `CERTIFIED` remains an incumbent until the whole outer frontier is exhausted;
- `UNKNOWN`, worker failure, max-attempt, best-effort, or candidate-subset stops cannot export full-domain certification;
- resume/import requires strict declare mode and strictly typed terminal state;
- terminal certified evidence must share the `has_terminal_full_frontier_certified_evidence` predicate.

### PO-CERTIFIED-EXPORT-SURFACE

Certified export surfaces can expose artifacts only after terminal full-frontier evidence is committed.

This compartment covers:

- `final_result` and `final_solution` export ordering;
- delivery manifest terminal evidence checks;
- inspector/report stale certified-surface hiding;
- B5A wrapper stale certified-surface hiding;
- unsafe-env blockers clearing stale resumed terminal state before returning;
- terminal evidence commit before `final_solution.json` is written.

## Test/currentness fix included

The V65/V66 centralized unsafe-env blocker now emits a uniform blocker payload with `env`, `value`, and `detail`.  The old ghost-anchor filter regression still expected the pre-centralized `anchor_filter_count` payload.  This was a test/diagnostic currentness mismatch, not a new solver bug.  The regression now asserts the centralized blocker shape.

## Review guidance after this anchor

Future reviews should start from `v66_certified_lifecycle_evidence_consolidation` and classify findings into one of the proof-obligation compartments above.  A finding should reset owner clean-review counting only if it is reachable and can cause one of the project safety failures:

- unsound cut;
- certified false negative;
- proof-obligation bypass;
- fake certified claim;
- reachable phase-gate false-ready.

Do not re-count V57-V66 already-known findings unless the consolidation failed to cover them or a reachable sibling bypass remains.
