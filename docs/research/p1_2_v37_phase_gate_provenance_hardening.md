# P1.2 V37 phase-gate provenance hardening

This note records the machine-checkable provenance invariants added after the
V37 clean-review candidate probe.  A clean-review slot is not satisfied by the
spelling of an evidence path alone: the evidence body must contain the exact
normalized claimed review package, not merely broad package tokens, and
independently counted clean-review slots must not reuse the same canonical path,
the same physical file identity, or byte-identical evidence content.

The phase gate loader must also reject duplicate JSON object keys.  Python's
plain `json.loads` keeps the last value for duplicate keys, which can hide a
blocked field behind a later ready field.  Phase-gate and proof-obligation JSON
therefore fail closed on duplicate keys.

The `PO-PHASE-GATE-PROVENANCE` manifest now names the path-alias, directory
evidence, reset-reuse, duplicate-gate-id, hardlink, copied-content,
filename-only package binding, token-only package binding, and duplicate-JSON-key
regressions directly, so future proof-obligation checks fail when one of these
guards is removed from the anchored regression suite.
