# Phase 1.2 close gate

**Current machine state: BLOCKED.**

The authoritative record is `data/review_gates/phase_1_2_spike_close.json`:

```text
status = blocked_manual_review_count
owner_manual_state.p1_2_close_status = not_closed
owner_manual_state.p1_3b_entry_allowed = false
next_phase_entry.allowed = false
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
to allowed.

Prerequisite scope (owner rulings 2026-07-06, twice on the same day — the evening ruling
governs): the morning ruling briefly widened the closeout prerequisite to the full PR2 TCB
deepening backlog; the same evening, after distinguishing accidental corruption (already caught
fail-closed by the always-on byte-sha floor) from deliberate insider tampering (the only adversary
the structural anchors/TOCTOU/OS-isolation hardenings address), the owner deferred all
deliberate-insider-only hardenings (#8 deepening, #2/#3, #5-F, #9b/#9c, #5 Option B) to release
time and ruled them not prerequisites for P1.2 closure. Net effect: the coding-type closeout
prerequisites are substantively cleared; what remains is the closeout external review plus the
owner manual gate. Production byte re-pinning (#9a) remains a deployment-time task. Details in
memory card `deliberate-insider-hardening-deferred-to-release`.

The checker should pass while the gate is blocked. That PASS means the repository is consistently
fail-closed, not that P1.2 is ready.

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
- no current text may say the owner gate or P1.2 is closed.

## Technical and governance conditions

A future close requires both technical and owner conditions. The technical side includes no
producer-side durable/public mint, supervisor disk-current replay and fixed-witness validation,
independent reverify for proof-bearing whole-layout eliminations, a single transactional canonical
publisher, current package/policy boundaries, PR2 TCB work as scoped by the owner (2026-07-06: the
full deepening backlog — see Authority model above), and required tests
on the same worktree.

The governance side requires the explicit owner manual decision. Neither side substitutes for the
other.

## Checker commands

Validate the current blocked state:

```bash
python scripts/check_phase_review_gate.py
```

Require actual readiness for the next stage:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

The second command is expected to fail while `next_phase_entry.allowed=false`. That failure is the
correct release behavior.

## Step 8 boundary

While the gate is blocked, `src/cuts/lifecycle.py:step_8_apply_to_master` must remain fail-closed.
F1–F9 generator/validator/lifecycle implementation does not mean production master integration is
active. Step 8 belongs to future P1.3 work after this gate is explicitly opened.
