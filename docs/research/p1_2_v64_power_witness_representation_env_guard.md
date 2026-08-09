# P1.2 V64 power-witness representation env guard

V64 extends the V63 certified exact terminal-evidence boundary to sibling
master/witness representations exposed by environment/debug knobs.  A certified
exact run must fail closed before `ExactSearchSession` or precheck construction
when any env knob can remove, delegate, or bypass certified master power-witness
coverage.

The reset-grade sibling drift covered by this anchor is:

- `EXACT_LAZY_POWER_COMPLETION=1`, which skips certified geometric power
  coverage constraints in the coordinate exact master and replaces them with a
  lazy completion representation.
- `EXACT_POWER_PLACEMENT_SUBPROBLEM=1`, which delegates power placement evidence
  to a subproblem representation rather than the certified master witness.
- `EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST=1`, which disables the
  lower certified-mode guard for forensic/test use and therefore must never be
  accepted by certified lifecycle entry points.

The centralized unsafe-env map in `src/search/benders_loop.py` is the authority
for these fail-closed blockers.  Outer campaign entry, direct certified Benders
entry, and the P1.2 proof-obligation checker all require the same map/code
symbols so future sibling drift cannot reappear as a late fail-closed path or a
certified-looking artifact from a changed power-witness representation.
