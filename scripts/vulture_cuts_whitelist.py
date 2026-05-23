"""Vulture whitelist for cut framework public extension points.

These names are intentionally unused inside Phase 1.1 unit tests because they are
phase boundary APIs or serialized cert schema fields used by later integration.
"""
from src.cuts import lifecycle

lifecycle.RegionCapacityCert
lifecycle.RegionCapacityCert.region_cells_bitset_b64
lifecycle.RegionCapacityCert.lp_dual_ray_b64
lifecycle.RegionCapacityCert.lp_dual_objective
lifecycle.step_2_minimize
lifecycle.step_8_apply_to_master
