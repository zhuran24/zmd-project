---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/search/exact_campaign.py, src/search/outer_search.py, src/search/certified_surface.py, scripts/inspect_exact_campaign_state.py
last_verified_against: 2026-06-26
owner: certified-exact-operations
---

# Exact Campaign Operations

## 1. Authority model

The campaign checkpoint is the persistent proof state, but three roles must remain separate:

1. `outer_search` is a producer. It records candidate outcomes and, after strict frontier exhaustion,
   commits a `CANDIDATE_PROPOSED` terminal proposal with replay/fixed-witness material.
2. `ExactCampaign.supervisor_seal()` is the sole durable terminal `CERTIFIED` mint. It rereads the
   canonical checkpoint and independently revalidates the proposal before sealing.
3. `publish_verified_certified_delivery_surface()` is the sole canonical public publisher. It also
   requires the P1.2 publish-open gate to be owner-closed.

A proposal, a candidate-level `RUN_STATUS_CERTIFIED`, or a schema-valid output file is not public
certification. P1.2 is currently blocked by the manual owner gate.

## 2. Read-only inspection

```bash
python scripts/inspect_exact_campaign_state.py --no-write
```

The writable form emits an informational inspector report under `.artifacts/`. The inspector is a
reader, not a proof source. Review at least:

- campaign presence and canonical path;
- `final_status`, proposal state and stop reason;
- resume compatibility with current artifact/source hashes;
- terminal frontier and fixed-witness verification;
- public certified-surface verdict and its blocked reason;
- telemetry wave/outcome counts.

Do not infer public certification from checkpoint fields without the central certified-surface
verdict.

## 3. Clean start

A typical bounded run is:

```bash
python main.py \
  --mode certified_exact \
  --campaign-hours 1 \
  --parallel-processes 1 \
  --frontier-probe-mode auto \
  --master-seconds 120 \
  --binding-seconds 120 \
  --routing-seconds 120 \
  --benders-max-iter 15
```

After the run, inspect the checkpoint and telemetry. `UNKNOWN`, `UNPROVEN`, worker failure or budget
exhaustion are triage states. None may be rewritten as frontier exhaustion.

## 4. Resume

Resume only when the inspector reports compatibility with current bytes and proof-bearing source
closure:

```bash
python main.py \
  --mode certified_exact \
  --resume-campaign \
  --campaign-hours 168 \
  --parallel-processes 4 \
  --frontier-probe-mode auto
```

A resume must preserve monotonic candidate evidence and must not revive stale proposal/current-process
markers. A supervisor seal always rereads canonical disk state rather than trusting caller memory.

## 5. Artifact-hash mismatch

The current `data/preprocessed/candidate_placements.json` is present and is expected to be exactly:

- size: `45,774,305` bytes;
- SHA256: `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`.

The superseded pre-corner-fix artifact (size `45,773,799`, SHA256
`adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`) is hash-incompatible.

Changes to canonical rules, preprocess plan, candidate placements, mandatory instances, generic I/O,
or other campaign-bound sources require reset or a newly established proof chain. The superseded
53,594,995-byte artifact must not be accepted as current.

Record resets explicitly:

```text
reset_reason:
changed_artifacts:
invalidated_evidence:
operator_note:
```

Hints and community blueprints are performance inputs only. Stale `pose_idx` values must be
regenerated; hints never become soundness evidence.

## 6. Worker failure and time budget

Worker failure must preserve completed, identity-checked evidence and leave the campaign readable.
Budget exhaustion normally yields `UNKNOWN`. An existing candidate/proposal does not convert either
condition into a terminal proof. Diagnose the failing stage before changing concurrency.

## 7. Proposal and supervisor seal

When the producer exhausts the strict frontier, inspect the proposal rather than publishing it.
The supervisor seal must validate disk-current proposal identity, sink replay, fixed witness,
terminal evidence and current hashes. Only a successful supervisor transition may create durable
terminal `CERTIFIED` state.

There is no documentation shortcut that can substitute for calling the actual supervisor path.
The current repository does not provide a production supervisor CLI or launcher, and `main.py`
stops at `CANDIDATE_PROPOSED`. A proposal-ready marker therefore means “awaiting an external,
explicit supervisor invocation”, not “sealed”.

## 8. Public publication

Canonical publication uses the verified publisher and is expected to fail while the current P1.2
open gate remains blocked. Generic serializers, report/viewer builders and adapter exports may emit
non-authoritative copies but must not write the canonical three-file surface or preserve
proof-bearing language.

The canonical set is:

- `data/solutions/final_solution.json`;
- `data/blueprints/optimal_blueprint.json`;
- `data/solutions/certified_delivery_manifest.json`.

Publication is transactional and reverified. A failure should leave no partial canonical set.

## 9. Handoff checklist

A campaign handoff should state, without collapsing the distinctions:

- exact artifact/source hashes and resume status;
- candidate/proposal state;
- whether supervisor sealing was attempted and its result;
- public-surface verifier result and publish-gate state;
- unresolved candidates, worker failures and budgets;
- tests/checkers actually run in the same worktree;
- known open P1.2 items, including PR2 and package-policy work.
