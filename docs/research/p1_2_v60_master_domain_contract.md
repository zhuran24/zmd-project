# P1.2 V60 master-domain contract hardening

Certified exact campaign candidates are full ghost-anchor-domain claims.  The
runtime may expose experimental anchor-slicing controls for RAM probes, but a
terminal `INFEASIBLE` campaign record cannot inherit those controls unless the
proof state records and validates a partition-aware domain contract.

This hardening keeps the release-authoritative path fail-closed:

1. `ExactCampaign` schema v4 persists `master_domain_contract` with the only
   accepted value `ghost_anchor_domain=full_unfiltered` and no anchor filter.
2. Resume validation rejects missing, filtered, or version-mismatched master
   domain contracts before any terminal candidate can prune the frontier.
3. `run_benders_for_ghost_rect` returns `UNPROVEN` before master construction
   when `EXACT_MASTER_GHOST_ANCHOR_FILTER` is present in `certified_exact` mode.
4. The P1.2 proof-obligation checker anchors these state and entrypoint checks.

A future partition-aware proof path must define a separate state schema that
records the filtered domain, coverage composition, and merge rule before it can
produce terminal certified campaign evidence.
