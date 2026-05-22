"""canonical_rules + facility_templates lookup helpers (Gap 8 修, round 30 audit).

修真数据 schema 跟 spec 假设不一致的核心断层 (per Gemini round 30):
- group_id (operation_type, e.g. "boundary_io") **不**是 canonical_rules 顶层 key
- facility_type (e.g. "boundary_storage_port") 才是 canonical_rules.facility_templates key
- 必须经 instance_to_facility_type 映射查 cells_per_pose / placement_rule / port_rule

helpers/__init__.py 没 re-export 这些 (避 circular import 风险 — helpers/canonical
ref BState, lifecycle 不该 ref helpers).

Phase 1.1 P1.5+ 各 family validator / oracle 调这些 helper 替直接 dict access.

Refs:
- docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_30_gap6_audit_NOT_GO.md
- rules/canonical_rules.json — facility_templates 结构 source-of-truth
- data/preprocessed/mandatory_exact_instances.json — operation_type → facility_type
"""
from __future__ import annotations

from typing import Optional

from src.cuts.lifecycle import BState, GroupId


def facility_type_for_group(state: BState, gid: GroupId) -> Optional[str]:
    """operation_type (group_id) → facility_type lookup.

    Returns None 若 mapping 未 inject 或 group not registered.
    Fail-closed: 调用方应 raise / 拒 cut on None (production 应 inject 完整).
    """
    if state.instance_to_facility_type is None:
        return None
    return state.instance_to_facility_type.get(gid)


def facility_template_for_group(state: BState, gid: GroupId) -> Optional[dict]:
    """group_id → canonical_rules.facility_templates[facility_type] (full template entry)."""
    ft = facility_type_for_group(state, gid)
    if ft is None or state.facility_templates is None:
        return None
    return state.facility_templates.get(ft)


def cells_per_pose_for_group(state: BState, gid: GroupId) -> Optional[int]:
    """Compute cells_per_pose from facility_template.dimensions.w × h.

    canonical_rules 没 cells_per_pose 字段 (Gap 2). 从 dimensions 算.
    e.g. boundary_storage_port w=1 h=3 → 3 cells. manufacturing_3x3 w=3 h=3 → 9.

    Returns None 若 lookup chain 任一步 fail (fail-closed, 调用方 raise / 拒 cut).
    """
    template = facility_template_for_group(state, gid)
    if template is None:
        return None
    dims = template.get("dimensions")
    if not isinstance(dims, dict):
        return None
    w = dims.get("w")
    h = dims.get("h")
    if not isinstance(w, int) or not isinstance(h, int):
        return None
    return w * h


def placement_rule_for_group(state: BState, gid: GroupId) -> str:
    """canonical_rules.facility_templates[facility_type].placement_rule.

    Default "free" 若 template 没此字段 (e.g. manufacturing_* templates 都没,
    只 boundary_storage_port 有 "left_or_bottom_boundary").

    Returns "unknown" 若 lookup chain fail (fail-closed marker, validator
    应拒 cut).
    """
    template = facility_template_for_group(state, gid)
    if template is None:
        return "unknown"
    return template.get("placement_rule", "free")


def port_rule_for_group(state: BState, gid: GroupId) -> str:
    """canonical_rules.facility_templates[facility_type].port_rule.

    e.g. "opposite_parallel_sides" / "long_sides" / "core_specific" /
    "omni_wireless" / "inward_facing" / "none".

    Returns "unknown" 若 lookup fail.
    """
    template = facility_template_for_group(state, gid)
    if template is None:
        return "unknown"
    return template.get("port_rule", "none")
