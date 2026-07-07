"""B Design v2 cut framework — production src.

Phase 1 implementation per docs/research/p3_b_design_v2_20260521/PHASE_1_PLAN.md.

Modules:
- lifecycle.py: Cut schema + 9-step lifecycle (Phase 1.0 P1.1)
- store.py: CutStore + 6-dim watcher (Phase 1.0 P1.2)
- replay.py: 6-step verify + GHOST_AGNOSTIC/blocked_cells_hash dispatch (P1.3)
- helpers/: baseline_partition / power_cover / candidate_placements 等 (P1.4)
- families/: F1-F7+F9 validators + evaluators (P1.5-P1.15; F8 deleted
  2026-07-08 — retired on a false game-rule premise)
- oracles/: oracle wrappers for each family (P1.5-P1.15)
- assumptions/: ASSUMPTION_VERIFIERS dispatch table (P1.4)
- monitor/: F5/F9 ratio telemetry — Class C 退化监控

Refs:
- ../../docs/research/p3_b_design_v2_20260521/cut_lifecycle_v2.md v3.2.2
- ../../docs/research/p3_b_design_v2_20260521/cut_family_specs/{01-09}.md
- ../../docs/research/p3_b_design_v2_20260521/PHASE_0_CLOSE.md
- ../../PROJECT_LOCK.md §2B/§3A/§4
"""
