# Corrected-Semantics Round 4/5 Prototype

This directory contains the research-only reconstruction of the compact
front-clear-lifted coordinate master used to re-evaluate RND-06/RND-07.  It is
not imported by production code and must not write frozen or sealed artifacts.
Raw campaign output belongs under
`.artifacts/front_offset_incident_20260718/round45_bespoke_coordinate_master/`.

## Soundness Boundary

For a fixed ghost rectangle, every live feasible layout can be normalized by:

1. keeping all 266 mandatory facilities;
2. retaining only optional protocol boxes that own either of the two active
   generic-input slots (at most two boxes);
3. selecting one existing covering pole for each remaining powered facility
   and retaining their union (at most `219 + box_count <= 221` poles); and
4. forgetting belt paths while retaining the 628 active physical port cells.

The prototype represents that normalized layout and deliberately omits routing
connectivity.  Therefore prototype `INFEASIBLE` implies that the corresponding
live anchor is infeasible, provided all semantic, hash, process-exit, and
independent-oracle gates pass.  Prototype `FEASIBLE` is only a relaxation
witness, and `UNKNOWN` proves nothing.  Results are research evidence, not
sealed `CERTIFIED_INFEASIBLE` artifacts.

## Fixed Experiment Contract

The campaign uses one worker, no warm hint, and the strict-lean solver profile.
Seeds are 71 for 7x7, 72 for 6x8, and 73 for 8x6.  Each anchor is run in a fresh
process at both 600 and 1200 seconds.  Long arms run one at a time in user
systemd services with `MemoryHigh=34G`, `MemoryMax=38G`, and
`MemorySwapMax=16G`.

Use `run_campaign.py --help` for the preparation, launch, status, and summary
commands after the harness has passed its focused tests and repository gates.
