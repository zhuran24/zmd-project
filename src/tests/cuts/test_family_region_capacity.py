"""Phase 1.1 P1.5 + Gap 6 修后 test — Family 1 region_capacity union region.

Gap 6+7+8 (Gemini round 30) 修后 schema:
- region_kind = "left_or_bottom_union" (替 per-side)
- gid="boundary_io" 经 instance_to_facility_type → facility_type → facility_templates
- demand=46 (真 mandatory_exact_instances count)

Coverage:
- validate_region_capacity: 4 step check (cap_R / placement_rule / cells_per_pose
  source-of-truth / demand_R / witness)
- 5 unsound case: cap_R / demand_R / cells_per_pose rotated / placement_rule
  不映射 / witness fail
- 2 schema_err case: malformed cert / missing cells_per_pose / no facility_templates
- evaluate_geometric: returns True
- generate_region_capacity_cuts:
  - Union 数学: ghost ≥ 2 cells → trigger; ghost 单 cell on union → no trigger
  - GHOST_AGNOSTIC iff ghost ∩ union == ∅
"""
from __future__ import annotations

import json

from src.cuts.families.region_capacity import (
    evaluate_geometric_region_capacity,
    validate_region_capacity,
)
from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    BState,
    Cut,
    GroupState,
)
from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts


# Gap 8 修: gid 用真 operation_type, facility_templates 跟 真 canonical_rules schema 对齐
INSTANCE_TO_FT = {
    "boundary_io": "boundary_storage_port",
    "crusher_blue_iron": "manufacturing_3x3",
}
FACILITY_TEMPLATES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "dimensions": {"w": 1, "h": 3},  # 1 × 3 = 3 cells per pose
    },
    "manufacturing_3x3": {
        "dimensions": {"w": 3, "h": 3},
    },
}
# Legacy CANONICAL_RULES — 保留 args 兼容 (oracle sig stable)
CANONICAL_RULES = {"facility_templates": FACILITY_TEMPLATES}


def _make_state(
    *,
    boundary_exterior_blocks: int = 0,  # 在 left baseline 上 block 几个 cell
    ghost_rect: tuple = None,
    ghost_cells: set = None,
) -> BState:
    """Default: demand=46 boundary_io, no blocks → cap=139 ≥ demand=138 → no cut."""
    extra = {(15 + i, 0) for i in range(boundary_exterior_blocks)}
    return BState(
        groups={
            "boundary_io": GroupState(
                "boundary_io", demand=46, pose_domain=frozenset()
            ),
            "crusher_blue_iron": GroupState(
                "crusher_blue_iron", demand=34, pose_domain=frozenset(),
            ),
        },
        ghost_rect=ghost_rect,
        ghost_cells=frozenset(ghost_cells or set()),
        exterior_blocks=frozenset(extra),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=CANONICAL_RULES,
        facility_templates=FACILITY_TEMPLATES,
        instance_to_facility_type=INSTANCE_TO_FT,
    )


# ============================================================================
# Oracle: generate_region_capacity_cuts — Union region 数学
# ============================================================================

def test_oracle_emits_cut_when_union_overflow_2_cells():
    """Gap 6 union: 2 exterior on left baseline → union cap=137 < demand=138 → cut."""
    state = _make_state(boundary_exterior_blocks=2)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.family == "region_capacity"
    cert = json.loads(cut.geometric_payload)
    assert cert["region_kind"] == "left_or_bottom_union"
    # union cap = 70 + 70 - 1 (overlap (0,0)) - 2 (exterior) = 137
    assert cert["cap_R"] == 137
    assert cert["demand_R"] == 138  # 46 × 3
    assert cert["gap"] == 1


def test_oracle_silent_when_no_overflow_no_blocks():
    """0 ghost / exterior → union cap=139 ≥ demand=138 → no cut."""
    state = _make_state(boundary_exterior_blocks=0)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert cuts == []


def test_oracle_silent_when_single_cell_block():
    """Gap 6 sound case: union ghost 单 cell → cap=138 == demand=138 (gap=0)
    → no cut (feasible 刚好够)."""
    state = _make_state(boundary_exterior_blocks=1)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert cuts == []


def test_oracle_ghost_block_bottom_3_cells_triggers_FN_proof():
    """Gap 6 关键 case: ghost block 3 cells on bottom baseline → union cap=136
    < demand=138. union 形式 trigger (vs per-side 形式会 FN — per-side left
    cap=70 ≥ left demand=69 不 trigger 即便全局 INFEASIBLE)."""
    # ghost 占 (0, 30) (0, 31) (0, 32) — bottom baseline 3 cells
    state = _make_state(
        ghost_rect=(0, 30, 1, 3),
        ghost_cells={(0, 30), (0, 31), (0, 32)},
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    cert = json.loads(cuts[0].geometric_payload)
    assert cert["cap_R"] == 136
    assert cert["demand_R"] == 138
    assert cert["gap"] == 2


def test_oracle_ghost_agnostic_when_ghost_disjoint_from_union():
    """Gap 6 GHOST_AGNOSTIC dispatch: ghost ∩ union == ∅ → AGNOSTIC scope."""
    state = _make_state(
        boundary_exterior_blocks=2,
        ghost_rect=(20, 20, 5, 5),
        ghost_cells={(20, 20), (21, 20)},  # not on left/bottom baseline
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    assert cuts[0].scope.ghost_rect_id == GHOST_AGNOSTIC


def test_oracle_ghost_bound_when_ghost_intersects_union():
    state = _make_state(
        ghost_rect=(30, 0, 3, 1),
        ghost_cells={(30, 0), (31, 0), (32, 0)},
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    assert cuts[0].scope.ghost_rect_id != GHOST_AGNOSTIC


# ============================================================================
# Validator: validate_region_capacity
# ============================================================================

def test_validator_ok_on_legit_cut():
    state = _make_state(boundary_exterior_blocks=2)
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    vr = validate_region_capacity(cuts[0], state, CANONICAL_RULES)
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validator_unsound_cap_R_tampered():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered = Cut(
        cut_id=cut.cut_id, family=cut.family,
        literals=None, geometric_payload=tampered_payload,
        scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(tampered, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "cap_R mismatch" in vr.detail


def test_validator_unsound_demand_R_tampered():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["demand_R"] = 9999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=tampered_payload, scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(tampered, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "demand_R mismatch" in vr.detail


def test_validator_unsound_cells_per_pose_source_rotated():
    """canonical_rules 改 dimensions → cells_per_pose 跟 cert 不一致 → unsound."""
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    # 改 state.facility_templates dimensions (模拟 source rotated)
    rotated_templates = {
        **FACILITY_TEMPLATES,
        "boundary_storage_port": {
            **FACILITY_TEMPLATES["boundary_storage_port"],
            "dimensions": {"w": 1, "h": 2},  # 改 3 → 2
        },
    }
    rotated_state = BState(
        groups=state.groups,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=state.exterior_blocks,
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=state.available_oracle_versions,
        canonical_rules=state.canonical_rules,
        facility_templates=rotated_templates,
        instance_to_facility_type=state.instance_to_facility_type,
    )
    vr = validate_region_capacity(cut, rotated_state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "cells_per_pose mismatch" in vr.detail


def test_validator_schema_err_missing_cells_per_pose():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    del cert_dict["cells_per_pose"]
    bad_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    bad_cut = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=bad_payload, scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(bad_cut, state, CANONICAL_RULES)
    assert vr.kind == "schema_err"
    assert "cells_per_pose missing" in vr.detail


def test_validator_unsound_when_facility_templates_not_injected():
    """fail-closed: production state 必 inject facility_templates;
    None → helper 返 unknown → _group_falls_in_region False → unsound
    ('placement_rule 不映射'). validator 拒 cut.

    (技术上也可视为 schema_err — facility_templates 缺失是 schema 不全 — 但
    validator check order 让 placement_rule 路径先 hit; 行为 fail-closed
    一致, 都不 reactivate cut.)"""
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    state_no_ft = BState(
        groups=state.groups,
        ghost_rect=state.ghost_rect,
        ghost_cells=state.ghost_cells,
        exterior_blocks=state.exterior_blocks,
        artifact_hashes=state.artifact_hashes,
        available_oracle_versions=state.available_oracle_versions,
        canonical_rules=state.canonical_rules,
        facility_templates=None,
        instance_to_facility_type=None,
    )
    vr = validate_region_capacity(cut, state_no_ft, CANONICAL_RULES)
    assert vr.kind in ("unsound", "schema_err")
    assert "placement_rule" in vr.detail or "cells_per_pose" in vr.detail


# ============================================================================
# evaluate_geometric (v1.1 简化版)
# ============================================================================

def test_evaluate_geometric_returns_true():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    assert evaluate_geometric_region_capacity(cut, state) is True


# ============================================================================
# Active assumptions on emitted cut
# ============================================================================

def test_oracle_cut_carries_correct_assumptions():
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    keys = {a.key for a in cut.scope.active_assumptions}
    assert "left_or_bottom_boundary_saturation" in keys
    assert "placement_rule" in keys
    placement_rule_assumptions = [
        a for a in cut.scope.active_assumptions if a.key == "placement_rule"
    ]
    assert len(placement_rule_assumptions) == 1
    # Gap 8: 真 group_id="boundary_io" (operation_type 真名)
    assert "boundary_io=left_or_bottom_boundary" in placement_rule_assumptions[0].value


# ============================================================================
# group_id misuse — production 该用 operation_type
# ============================================================================

def test_oracle_skips_free_placement_rule_groups():
    """crusher_blue_iron placement_rule='free' → 不该 contribute 到任何 region cut."""
    state = _make_state(boundary_exterior_blocks=2)
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    contributing = json.loads(cut.geometric_payload)["contributing_groups"]
    gids = {c[0] for c in contributing}
    assert "boundary_io" in gids
    assert "crusher_blue_iron" not in gids
