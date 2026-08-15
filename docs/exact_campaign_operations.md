# Exact Campaign Operations

This guide describes the stable operating boundary of the certified-exact campaign. It does not
copy the current gate, artifact digests, bounds, release state, or test receipts. Read
[`CURRENT.md`](CURRENT.md) for the current projection and use the registered machine checks for
byte identity.

## Authority model

Keep these roles separate:

1. `outer_search` produces candidate outcomes and may persist a terminal proposal after strict
   frontier exhaustion.
2. `ExactCampaign.supervisor_seal()` is the durable terminal certification mint. It rereads the
   canonical checkpoint and independently validates the proposal.
3. `publish_verified_certified_delivery_surface()` is the canonical public publisher. It enforces
   the publication gate and all other publication preconditions.

A candidate result, proposal marker, schema-valid output, local replay, or successful checker is not
public certification. The exact authority boundary is defined by [`PROJECT_LOCK.md`](../PROJECT_LOCK.md),
not by this runbook.

## Inspect before acting

Use the campaign inspector before a clean start, resume, seal, handoff, or publication:

```bash
python scripts/inspect_exact_campaign_state.py --no-write
```

Review at least:

- canonical campaign path and checkpoint readability;
- terminal state, proposal state, stop reason, and current-process markers;
- artifact and source identity compatibility;
- frontier, replay, and fixed-witness evidence;
- supervisor-seal state;
- central certified-surface verdict and publication-gate reason;
- worker failures, unresolved candidates, and resource exhaustion.

The inspector is a reader. Its report does not become a proof source.

## Clean start and resume

Choose runtime budgets from the command-line help and the host capacity rather than copying a dated
profile from a report:

```bash
python main.py --mode certified_exact --help
```

A clean start establishes a new proof state. A resume is permitted only when the inspector and the
campaign implementation accept the complete identity closure for the current bytes and proof-bearing
sources. Resume must preserve monotonic evidence and must not revive stale proposal or process
markers.

Any change to canonical rules, preprocess inputs, candidate placements, mandatory instances,
generic input slots, proof-bearing I/O, or other campaign-bound sources requires the reset or
re-establishment path enforced by the implementation. Record the reason and the invalidated evidence
in the campaign handoff. Never waive an identity mismatch in prose.

## Failure and budget states

Worker failure must preserve readable, identity-checked evidence already committed. Resource or time
exhaustion normally leaves an unresolved state. Neither condition becomes frontier exhaustion merely
because a candidate or proposal exists.

Diagnose the failing stage before changing concurrency. Operational tuning cannot alter proof
semantics, supervisor authority, or publication requirements.

## Proposal, seal, and publication

After the producer reports strict frontier exhaustion, inspect the persisted proposal. The supervisor
must reread canonical disk state and verify the proposal identity, replay, fixed witness, terminal
evidence, and current source closure. Invoke the production supervisor through its registered
launcher rather than simulating the transition in documentation.

Canonical publication uses the verified publisher and is transactional. Generic serializers,
viewers, reports, and adapter exports may produce non-authoritative derivatives, but they must not
write the canonical certified surface or preserve proof-bearing labels without the central verdict.

## Machine identity checks

Do not copy current digests or artifact sizes into this guide. Obtain them from the authoritative
manifests and checkers used by the campaign:

```bash
python scripts/check_external_artifacts.py
python scripts/inspect_exact_campaign_state.py --no-write
python scripts/check_phase_review_gate.py
```

Use the exact command set returned by the current [`AGENT_OPERATIONS.md`](AGENT_OPERATIONS.md) and
`docctl context` operation card when a path has a narrower contract.

## Handoff record

A handoff should distinguish:

- artifact/source compatibility and any reset;
- candidate and proposal state;
- supervisor invocation and result;
- public-surface verification and publication gate;
- unresolved candidates, failures, and exhausted budgets;
- checks actually run in the same worktree;
- remaining owner, release, or hardening work.

Do not collapse those layers into a single “passed” or “certified” label.
