"""Cut family validators + evaluators (B Design v2 Phase 1.1+).

One module per family per PHASE_1_PLAN §2 src 路径表:
- region_capacity (F1)        — Phase 1.1 P1.5 ✅
- cutset (F2)                 — Phase 1.1 P1.6
- port_exposure (F3)          — Phase 1.1 P1.7
- component_reach (F4)        — Phase 1.1 P1.8
- pattern_nogood (F5)         — Phase 1.2 P1.11
- shape_packing_hall (F6)     — Phase 1.2 P1.12
- power_hitting_set (F7)      — Phase 1.2 P1.13
- power_grid_reach (F8)       — DELETED 2026-07-08 (retired, false premise)
- density_envelope (F9)       — Phase 1.2 P1.15
"""
