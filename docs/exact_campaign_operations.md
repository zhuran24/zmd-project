---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/search/exact_campaign.py, src/search/outer_search.py, src/search/certified_surface.py, scripts/inspect_exact_campaign_state.py
last_verified_against: 2026-07-18
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
certification. The P1.2 owner gate was closed on 2026-07-07 by explicit
`owner_manual_decision`; public certification still requires the supervisor-sealed disk authority
and verified publisher.

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
- public certified-surface verdict and publication-gate reason;
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

The current frozen campaign inputs include:

- `rules/canonical_rules.json`: `17,510` bytes, SHA256
  `5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05`;
- `rules/preprocess_plan.json`: `1,383` bytes, SHA256
  `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee`;
- `data/preprocessed/candidate_placements.json`: `54,467,709` bytes, SHA256
  `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3`.

The candidate superseded chain is `45,774,305` bytes /
`a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`, then the pre-corner-fix
`45,773,799` bytes / `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`,
then `53,594,995` bytes / `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f`,
then `53,595,501` bytes / `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef`.
Every member is historical and hash-incompatible.

Changes to canonical rules, preprocess plan, candidate placements, mandatory instances, generic I/O,
or other campaign-bound sources require reset or a newly established proof chain. Campaign identity
must carry and atomically compare the complete `generic_input_slots_by_operation` map parsed from the
same hash-bound plan snapshot; a box-only scalar or a second plan read is not compatible.

The current generic-input model routes finished goods from producer outputs to physical provider
inputs. `box_sink` exposes 3 inputs and 3 outputs; the mandatory core exposes 14 inputs and 6 outputs.
The provider-aware, instance-aware box lower bound is 0 because current demand 2 is covered by that
real core capacity; an uninstantiated template earns no credit.

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
The production supervisor launcher is `scripts/run_supervisor_seal.py` (independent, marker-driven,
landed 2026-07-04), and `main.py` still stops at `CANDIDATE_PROPOSED`. A proposal-ready marker
therefore means “awaiting an external, explicit supervisor invocation”, not “sealed”.

## 8. Public publication

Canonical publication uses the verified publisher. As of 2026-07-07, the P1.2 open-gate check
should pass on the explicit owner decision; all other publisher preconditions still apply. Generic
serializers, report/viewer builders and adapter exports may emit non-authoritative copies but must
not write the canonical three-file surface or preserve proof-bearing language.

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
- post-P1.2 / release-time items, including PR2 deliberate-insider hardening and package-policy work.
