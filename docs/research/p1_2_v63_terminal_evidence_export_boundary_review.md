# P1.2 V63 terminal evidence export boundary review

This note records the V63 follow-up hardening for the V62 terminal frontier evidence contract.

Certified export, report, resume/import, delivery manifest, and B5A wrapper boundaries must not publish candidate-level incumbents, stale `final_result`, partial-frontier states, or contradictory stop records as terminal `CERTIFIED` evidence. The shared predicate is `has_terminal_full_frontier_certified_evidence`; it requires strict declare mode, `final_status=CERTIFIED`, a mapping `final_result`, and `last_stop_reason.status=CERTIFIED` with `reason=search_exhausted_all_candidates`.

The unsafe certified master-domain environment override set is centralized in `_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES`, including `EXACT_MASTER_GHOST_ANCHOR_FILTER`, `EXACT_USE_POSE_BOOL_MASTER`, and `EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE`. `outer_search` consumes that centralized set immediately after campaign load and before session construction.
