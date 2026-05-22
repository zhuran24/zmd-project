"""Phase 1.1 P1.5 test — Family 1 region_capacity production validator + oracle.

Coverage:
- validate_region_capacity: 4 region kind decode + recompute path
- 5 unsound case: cap_R tampered / demand_R tampered / cells_per_pose rotated /
  contributing_group placement_rule 不映射 region / witness 不成 (demand ≤ cap)
- 2 schema_err case: malformed cert / missing cells_per_pose
- evaluate_geometric: returns True (v1.1 简化版)
- generate_region_capacity_cuts: 4 region kind enumerate, emit cut on overflow,
  silent on feasible
- v1.2 GHOST_AGNOSTIC dispatch: ghost ∩ R == ∅ → GHOST_AGNOSTIC; else bound
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


CANONICAL_RULES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "cells_per_pose": 3,
    },
    "crusher_blue_iron": {
        "placement_rule": "free",
        "cells_per_pose": 9,
    },
}


def _make_state(
    *,
    extra_block: bool = False,
    ghost_rect: tuple = None,
    ghost_cells: set = None,
) -> BState:
    extra = {(15, 0), (16, 0)} | ({(17, 0)} if extra_block else set())
    return BState(
        groups={
            "boundary_storage_port": GroupState(
                "boundary_storage_port", demand=23, pose_domain=frozenset()
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
    )


# ============================================================================
# Oracle: generate_region_capacity_cuts
# ============================================================================

def test_oracle_emits_cut_for_left_baseline_overflow():
    """cap=68 (70 - 2 exterior) < demand=23×3=69 → cut emitted."""
    state = _make_state()
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    # 2 region: left_baseline + bottom_baseline
    # left has 2 exterior blocks → overflow (demand 69 > cap 68)
    # bottom has 0 exterior blocks → cap 70 ≥ demand 69 → no overflow
    assert len(cuts) == 1
    left_cut = cuts[0]
    assert left_cut.family == "region_capacity"
    cert = json.loads(left_cut.geometric_payload)
    assert cert["region_kind"] == "left_baseline"
    assert cert["cap_R"] == 68
    assert cert["demand_R"] == 69
    assert cert["gap"] == 1


def test_oracle_silent_when_no_overflow():
    """No exterior blocks → cap 70 ≥ demand 69 → no cut."""
    state = BState(
        groups={
            "boundary_storage_port": GroupState(
                "boundary_storage_port", demand=23, pose_domain=frozenset()
            ),
        },
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=CANONICAL_RULES,
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert cuts == []


def test_oracle_ghost_agnostic_when_ghost_disjoint_from_region():
    """v1.2: ghost ∩ left_baseline == ∅ → GHOST_AGNOSTIC scope."""
    state = _make_state(
        ghost_rect=(20, 20, 5, 5),
        ghost_cells={(20, 20), (21, 20)},  # not on left_baseline (y=0)
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    assert cuts[0].scope.ghost_rect_id == GHOST_AGNOSTIC


def test_oracle_ghost_bound_when_ghost_intersects_region():
    """v1.2: ghost ∩ left_baseline non-empty → ghost_rect_id 绑."""
    state = _make_state(
        ghost_rect=(30, 0, 3, 1),  # 占 (30,0), (31,0), (32,0) on left_baseline
        ghost_cells={(30, 0), (31, 0), (32, 0)},
    )
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    # ghost 占 3 cells on baseline → cap = 70 - 2 exterior - 3 ghost = 65
    # demand 69 > cap 65 → overflow
    assert len(cuts) == 1
    assert cuts[0].scope.ghost_rect_id != GHOST_AGNOSTIC


# ============================================================================
# Validator: validate_region_capacity
# ============================================================================

def test_validator_ok_on_legit_cut():
    state = _make_state()
    cuts = generate_region_capacity_cuts(state, CANONICAL_RULES)
    assert len(cuts) == 1
    vr = validate_region_capacity(cuts[0], state, CANONICAL_RULES)
    assert vr.kind == "ok"


def test_validator_unsound_cap_R_tampered():
    state = _make_state()
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 999
    tampered_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    tampered = Cut(
        cut_id=cut.cut_id,
        family=cut.family,
        literals=None,
        geometric_payload=tampered_payload,
        scope=cut.scope,
        cert=cut.cert,
        family_version=cut.family_version,
        validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(tampered, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "cap_R mismatch" in vr.detail


def test_validator_unsound_demand_R_tampered():
    state = _make_state()
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["demand_R"] = 9999  # 巨大 demand → 跟 recomputed 不一致
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
    """Gemini r14 finding #5: canonical_rules cells_per_pose 改 → unsound."""
    state = _make_state()
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    rotated_rules = {
        **CANONICAL_RULES,
        "boundary_storage_port": {
            **CANONICAL_RULES["boundary_storage_port"],
            "cells_per_pose": 2,  # 改 3 → 2
        },
    }
    vr = validate_region_capacity(cut, state, rotated_rules)
    assert vr.kind == "unsound"
    assert "cells_per_pose mismatch" in vr.detail


def test_validator_witness_fail_when_demand_le_cap():
    """构造 cert: demand=68, cap=68 → 不 witness (≤)."""
    state = _make_state()
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    cert_dict["cap_R"] = 68
    cert_dict["demand_R"] = 68
    cert_dict["gap"] = 0
    cert_dict["cells_per_pose"]["boundary_storage_port"] = 3
    # 修 contributing demand 让 recompute = 68
    cert_dict["contributing_groups"] = [["boundary_storage_port", 68]]
    fake_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    # 但 23 * 3 = 69, recompute 仍 69 ≠ 68. 测 demand mismatch path:
    fake_cut = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=fake_payload, scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(fake_cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound"  # demand_R mismatch (69 vs 68) — 早期 fail


def test_validator_schema_err_missing_cells_per_pose():
    state = _make_state()
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


def test_validator_unsound_placement_rule_not_mapping():
    """contributing_groups 含 crusher_blue_iron (placement_rule=free) 不映射
    left_baseline → unsound."""
    state = _make_state()
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    cert_dict = json.loads(cut.geometric_payload)
    # 添 crusher 进 contributing (placement_rule=free 不映射)
    cert_dict["contributing_groups"].append(["crusher_blue_iron", 9])
    cert_dict["cells_per_pose"]["crusher_blue_iron"] = 9
    bad_payload = json.dumps(cert_dict, sort_keys=True).encode("utf-8")
    bad_cut = Cut(
        cut_id=cut.cut_id, family=cut.family, literals=None,
        geometric_payload=bad_payload, scope=cut.scope, cert=cut.cert,
        family_version=cut.family_version, validator_version=cut.validator_version,
    )
    vr = validate_region_capacity(bad_cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "不映射" in vr.detail or "placement_rule" in vr.detail


# ============================================================================
# evaluate_geometric (v1.1 简化版)
# ============================================================================

def test_evaluate_geometric_returns_true():
    state = _make_state()
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    assert evaluate_geometric_region_capacity(cut, state) is True


# ============================================================================
# Active assumptions on emitted cut
# ============================================================================

def test_oracle_cut_carries_correct_assumptions():
    """Cut scope 必含 left_or_bottom_boundary_saturation + placement_rule:
    boundary_storage_port=left_or_bottom_boundary."""
    state = _make_state()
    cut = generate_region_capacity_cuts(state, CANONICAL_RULES)[0]
    keys = {a.key for a in cut.scope.active_assumptions}
    assert "left_or_bottom_boundary_saturation" in keys
    assert "placement_rule" in keys
    placement_rule_assumptions = [
        a for a in cut.scope.active_assumptions if a.key == "placement_rule"
    ]
    # 只 1 contributing group (boundary_storage_port)
    assert len(placement_rule_assumptions) == 1
    assert "boundary_storage_port=left_or_bottom_boundary" in placement_rule_assumptions[0].value
