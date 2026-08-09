# P1.2 V31-V46 finding taxonomy and review-protocol reset

> **[Snapshot note]** Written before the P1.2 close. Statements like "P1.2 remains blocked" reflect the state at writing time; P1.2 was closed by explicit owner_manual_decision on 2026-07-07 (P1.3 opened). Current authority: data/review_gates/phase_1_2_spike_close.json.

Package: v46_review_protocol_redesign
Algorithmic reset package: v32_runtime_cache_source_digest_consolidation
Date: 2026-06-08
Review type: internal_review_protocol_redesign
Outcome: review_protocol_redesign
Infrastructure findings: 1
Resets algorithmic counter: false

## Why this exists

V31-V46 showed two different problem families that were being counted through one
`0/3` clean-review counter.  The early findings were genuine P1.2 proof-surface
issues: Step 7 attachability, source digest coverage, runtime cache authority,
and evaluator/replay fail-closed behavior.  Later findings were mostly about the
review gate itself: Markdown/HTML/XML evidence metadata parsing, package identity
canonicalization, and Git source-head authority.

Those later findings matter, but they are not the same kind of evidence as an
unsound cut, a false negative, or a fake certified-exact claim.  Treating every
review-infrastructure hardening issue as an automatic algorithmic-soundness reset
created a Zeno-style closeout loop where the gate parser became its own project.

## Classification

The P1.2 algorithmic clean counter is reset by findings that are reachable in the
certified lifecycle and can cause one of the following outcomes:

- an unsound cut is accepted or evaluated as pruning;
- a legal layout can be cut away, producing a certified false negative;
- a proof obligation such as Step 6/Step 7 attachability, source digest coverage,
  runtime-cache non-authority, F9 quarantine, or `step_8_apply_to_master`
  fail-closed status has a reachable bypass;
- a phase gate issue can actually mark P1.3B ready while the algorithmic gate is
  blocked.

Review-infrastructure findings are tracked separately when they harden receipt,
report, package, or repository provenance but do not by themselves demonstrate a
reachable algorithmic false negative or a real P1.3B false-ready path.

## V31-V46 distribution

Algorithmic / proof-obligation resets:

- V31 postmortem: Step 7 hot-path evaluation did not fully mirror Step 6
  attachability.  This was a real proof-obligation bypass.
- V32/V33 runtime-cache and source-digest consolidation: schema-valid leading
  dunder source fields, candidate placement pose caches, and port-exposure cache
  mutation paths were still proof-adjacent source-of-truth risks.  These belong
  to the algorithmic counter.

Review-infrastructure hardening:

- V37/V38: clean-review evidence provenance and package identity were too easy to
  spoof through file/path/content/package-label reuse and report body metadata.
- V44/V45/V46: clean-review package evidence used a Markdown/HTML/XML report
  parser and package-internal Git authority.  Those surfaces generated more
  parser and repository-authority variants after each patch.

The policy change is to stop treating free-form reports and package-internal Git
state as machine authority for clean-review credit.

## New protocol

Clean-review credit now requires a strict JSON receipt.  The human report remains
free text and is bound by `report_sha256`; the phase gate no longer accepts clean
credit merely because a Markdown report contains package metadata.  The receipt
must bind the archive identity and a source-tree manifest identity.

The source-tree identity is a manifest hash over package source bytes.  Git commit
hashes may be recorded in reports, but they are informational for the review gate;
the gate no longer shells out to Git to prove `source_head` in the clean-counter
protocol.

The current P1.2 status remains blocked.  The algorithmic counter is still 0/3.
The next full review should start from the post-redesign package and must classify
findings before deciding whether the algorithmic counter resets.
