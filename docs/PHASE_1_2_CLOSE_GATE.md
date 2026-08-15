# P1.2 Phase Gate Contract

> This page defines the stable gate contract. It does not copy the current decision ID, date,
> status value, review count, anchor, or next-phase flag. Read the generated
> [current-state projection](CURRENT.md) and the machine gate
> `data/review_gates/phase_1_2_spike_close.json` for those values. The pre-knowledge-spine page is
> archived at
> [docs/history/status/PHASE_1_2_CLOSE_GATE_pre_knowledge_spine_20260811.md](history/status/PHASE_1_2_CLOSE_GATE_pre_knowledge_spine_20260811.md).

## Authority model

The P1.2 publish gate is owner-controlled. Its state may change only through an explicit
**owner manual decision** recorded in the machine gate. Tests, receipts, reviewer prose, seals,
proof-obligation PASS, generated Markdown, or a successful checker run cannot create or infer that
owner action.

The repository intentionally does not derive the owner-maintained clean-review count. That count is
owner-maintained outside the repo; the gate file records only the governance result the owner chose
to enter.

## Machine source and projection

- machine authority: `data/review_gates/phase_1_2_spike_close.json`
- human-readable projection: [docs/CURRENT.md](CURRENT.md)
- stable decision history and supersede links: [docs/CATALOG.md](CATALOG.md)
- technical obligations: `data/proof_obligations/p1_2_proof_obligations.json`
- release boundary: `PROJECT_LOCK.md`

A Markdown page is never a substitute for the gate JSON. The generated projection is a reading aid
that is checked against the machine source.

## Meaning of the gate

A gate state that permits next-phase entry grants permission to begin the next phase. It does not,
by itself:

- produce a supervisor-sealed campaign;
- prove that a feasible whole-layout witness exists;
- publish a canonical delivery surface;
- finish later production-integration work;
- waive any proof obligation, frozen-input check, or publisher precondition.

Conversely, technical checks cannot replace the owner gate. Technical authority and governance
authority are conjunctive, not interchangeable.

## Checker commands

Validate the machine gate and its required documentation markers:

```bash
python scripts/check_phase_review_gate.py
```

Require the machine gate to permit the named next phase:

```bash
python scripts/check_phase_review_gate.py --require-ready phase_1_2_spike_close
```

Interpret the command output against [docs/CURRENT.md](CURRENT.md). Do not paste its current values
back into this page.

## Review anchor and later work

Any review anchor named by the gate is a point-in-time authority object with the scope stated by its
machine record. Later worktree bytes do not become covered merely because an earlier anchor or
packet passed. Fresh claims must use the current proof-obligation/source closure and any required
reseal process.

Current cut integration, production attach safety, research ledgers, and open work are separate
claims and decisions. Read [docs/CATALOG.md](CATALOG.md) rather than inferring them from the phase
gate.
