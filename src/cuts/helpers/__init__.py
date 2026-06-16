"""Geometric / combinatorial helpers for cut family validators.

Phase 1.0 P1.4 modules:
- ghost_geometry: Liang-Barsky line-AABB intersection (Family 8 power_grid_reach)
- baseline_partition: contiguous-unblocked partition lens (Family 6 shape_packing_hall)
- power_network: pole adjacency + bfs_component (Family 8 power_grid_reach)

Phase 1.1+ family validators (src/cuts/families/*) consume these helpers.
"""
