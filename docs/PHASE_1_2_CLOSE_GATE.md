# Phase 1.2 close gate

**Current machine state: CLOSED; P1.3 entry allowed.**

The authoritative record is `data/review_gates/phase_1_2_spike_close.json`:

```text
status = closed_manual_owner_decision
owner_manual_state.p1_2_close_status = closed
owner_manual_state.p1_3b_entry_allowed = true
next_phase_entry.allowed = true
```

The `p1_3b_*` field names are retained for machine compatibility. Human-facing documentation calls
the next stage **P1.3**.

## Authority model

The clean-review standard is maintained by the project owner outside the repository. Owner
clarification (2026-07-06): the literal "three consecutive clean reviews" figure is a historical
convenience baseline, not the operative criterion — closeout review continues until the owner
judges it sufficient (possibly more or fewer than three rounds). The machine field
`required_consecutive_clean_full_reviews=3` and the "three clean reviews" wording in the closing
acknowledgement field are retained for checker compatibility only (the same pattern as the
`p1_3b_*` fields). Review receipts, Markdown reports, package metadata, tests and Git/package
manifests are informational; they do not calculate clean credit and cannot open the gate. Only an
explicit `owner_manual_decision` with the required acknowledgements may set the next-stage state
to allowed. That close action was actually entered on 2026-07-07 by owner
`owner_manual_decision` after three closeout external-review axes (permission structure, math
semantics, TCB-line honesty) produced 24 clusters and zero true above-TCB soundness findings.

Prerequisite scope (owner rulings 2026-07-06, twice on the same day — the evening ruling
governs): the morning ruling briefly widened the closeout prerequisite to the full PR2 TCB
deepening backlog; the same evening, after distinguishing accidental corruption (already caught
fail-closed by the always-on byte-sha floor) from deliberate insider tampering (the only adversary
the structural anchors/TOCTOU/OS-isolation hardenings address), the owner deferred all
deliberate-insider-only hardenings (#8 deepening, #2/#3, #5-F, #9b/#9c, #5 Option B) to release
time and ruled them not prerequisites for P1.2 closure. Net effect: the coding-type closeout
prerequisites were substantively cleared, the closeout external review completed cleanly, and the
owner manual gate was closed on 2026-07-07. Production byte re-pinning (#9a) remains a
deployment-time task. Details in memory card `deliberate-insider-hardening-deferred-to-release`.

The checker should pass in the closed state. That PASS means the gate JSON is internally
consistent with the explicit owner decision, not that P1.3 implementation work is finished.

## Review anchor versus current worktree

`v99_p1_2_close_kernel_sealing` remains the last owner-approved review anchor embedded in the
checker and gate file. It was a point-in-time source-hash seal. The current worktree contains later
PR1 publication-chain changes, including producer/supervisor separation, fixed-witness verification,
independent whole-layout reverify, publish-open enforcement and central canonical publication.
Those later bytes are not covered by the old v99 seal.

Therefore:

- v99 may be cited as historical evidence only;
- the current worktree requires fresh proof-obligation/allowlist resealing and validation;
- an old packet/checker PASS must not be described as a current technical close;
- no current text may infer owner-gate closure, release, or publication from tests, receipts,
  Markdown, old packets, seals or checker PASS alone;
- current text may say P1.2 is CLOSED only because the owner truly entered
  `owner_manual_decision` on 2026-07-07.

## Technical and governance conditions

P1.2 close required both technical and owner conditions. For the closed 2026-07-07 state, the
technical side is the owner-accepted closeout package: no producer-side durable/public mint,
supervisor disk-current replay and fixed-witness validation, independent reverify for proof-bearing
whole-layout eliminations, a single transactional canonical publisher, current package/policy
boundaries, PR2 TCB work as scoped by the owner (2026-07-06: deliberate-insider-only hardenings
deferred to release time — see Authority model above), and required tests on the same worktree.

The governance side was the explicit owner manual decision. Neither side substitutes for the
other; the close decision does not by itself release public artifacts or complete P1.3.

## Checker commands

Validate the current closed state:

```bash
python scripts/check_phase_review_gate.py
```

Expected output in this state:

```text
phase_1_2_spike_close: status=closed_manual_owner_decision, anchor=v99_p1_2_close_kernel_sealing, next_allowed=True, counting_authority=owner_manual_count_outside_repo
```

Require actual readiness for the next stage:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

The second command now exits successfully because `next_phase_entry.allowed=true`. That success is
entry permission for P1.3, not a release claim.

## Step 8 boundary

With the gate open, P1.3 has progressed beyond a wholly stubbed Step 8: F1/F5/F6/F7 translations and the env-gated direct bridge are present, and Stage B B0/B1/B1.5 has landed. The bridge remains unsafe/default-off for certified runs; F2/F3/F4/F9 fail closed, F8 is retired, and B2-B5/PIC C-D-E/RFC-002/003/B6 remain before certified promotion.
