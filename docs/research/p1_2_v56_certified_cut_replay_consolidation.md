# P1.2 V56 certified cut replay faithfulness consolidation

Date: 2026-06-08

Status: **NOT CLEAN / consolidation anchor**.  This document records the V53-V56 postmortem and turns those four sibling findings into one P1.2 proof obligation: exact-safe persisted `BendersCut` replay must be strictly parsed, all-or-nothing, and faithfully encoded by every certified master backend.

## Why this consolidation exists

V51 and V52 were manually counted as clean outside the repo.  V53 then opened a different proof surface from the earlier V29-V31 cut-lifecycle findings and from the V47-V50 review-gate findings.  The new surface was not the receipt protocol; it was the certified exact replay path for persisted exact-safe Benders cuts:

```text
campaign exact_safe_cuts / structured cut artifact
    -> BendersCut.from_dict
    -> certification blockers / artifact hashes / condition resolution
    -> master.add_benders_cut
    -> CutManager.register_structured_cut / generated_exact_safe_cuts
```

The safety issue is that a certified cut is only sound if the replayed master constraint represents the original conflict exactly enough for pruning.  Silently coercing payloads, dropping unresolved members, deduping aliased literals, or registering a cut before the master accepts it can strengthen a multi-member nogood into a one-literal ban.  That is a reachable false-negative risk in certified exact mode.

## V53-V56 finding taxonomy

| Review | Finding class | Consolidated lesson |
| --- | --- | --- |
| V53 | certified replay evidence strictness | `exact_safe` and related replay evidence must be strictly typed.  Truthy strings such as `"false"` must not become certified-safe booleans, and duplicate JSON keys must fail closed. |
| V54 | certified conflict / condition payload strictness | `conflict_set` and `condition_set` members in `source_mode="certified_exact"` cuts must be strict integers.  `bool` is not an integer proof payload, and string coercion is not replay-safe. |
| V55 | unresolved member dilution | A cut over `{A, B}` must not be replayed as a cut over `{A}` if `B` cannot be resolved.  Missing members fail closed. |
| V56 | aliasing member dilution | Distinct conflict members must not be replayed as one backend literal.  If two members alias to the same master literal, the backend must reject the whole cut. |

V55 and V56 are the strongest findings: they directly show how a multi-member nogood can be strengthened during replay/lowering.  V53 and V54 are the evidence-layer siblings that make sure malformed persisted state cannot enter that path as certified input.

## Consolidated proof obligation

`PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS` is now part of `data/proof_obligations/p1_2_proof_obligations.json`.  Its contract is:

1. Exact-safe certified cut JSON must be strict JSON, with no duplicate keys and no non-standard constants.
2. `source_mode="certified_exact"` cuts must use strict `bool` `exact_safe` values and strict integer `conflict_set` / `condition_set` payloads.  Python `bool` values are rejected even though `bool` subclasses `int`.
3. Campaign resume and pre-master replay must validate persisted exact-safe cuts before inheriting certification state.
4. Every conflict member must resolve to a concrete master literal; unresolved members fail closed instead of being dropped.
5. Distinct conflict members must map one-to-one to distinct backend literals; alias collisions fail closed instead of deduping into a stronger cut.
6. Exact-safe cuts are registered, persisted, or counted only after the master backend accepts the whole cut.

## Machine gate changes

`scripts/check_p1_2_proof_obligations.py` now checks that the manifest contains this obligation, that the V53-V56 regression tests are listed and present, and that the main replay/lowering code still exposes the expected fail-closed structure:

- `BendersCut.from_dict` / `to_dict` use strict replay payload helpers.
- `CutManager.load` uses strict JSON for structured cut artifacts.
- campaign candidate validation parses exact-safe cuts through `BendersCut.from_dict` and requires `exact_safe is True`.
- `_add_exact_persisted_nogood` applies to the master before registering/counting the cut.
- `run_benders_for_ghost_rect` replay resolves conditions and only registers loaded cuts after master application succeeds.
- coordinate, pose-bool, and legacy master backends retain missing-member and alias-member fail-closed logic.

This is still a structural gate, not a theorem prover.  It prevents the known V53-V56 class from drifting back into local, duplicated proof checks.

## Current review anchor

The current review anchor is now:

```text
v56_certified_cut_replay_consolidation
```

P1.2 remains blocked.  The owner still keeps the clean-review count outside the repo, and the repo remains fail-closed until an explicit owner manual decision opens P1.3B.  Future reviews should start from this anchor and focus on whether any remaining payload-coercion, missing-member, alias-member, condition-resolution, or apply/register atomicity bypass is reachable in certified exact mode.
