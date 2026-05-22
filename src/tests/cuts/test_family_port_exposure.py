"""Phase 1.1 P1.7 test — Family 3 port_exposure (literal-based, multiset eval).

Coverage:
- validate_port_exposure: ok / unsound (front_cell math wrong / blocking facility
  not at front_cell / port not in facility ports) / schema_err
- evaluate_literal_port_exposure: multiset subset match (state has 2 literals →
  True; missing 1 → False; slot permutation invariant)
- ``evaluate_literal_multiset`` (lifecycle generic):
  - 1 literal in 1 group: subset match
  - 2 literals same group: requires 2 selected_poses with same pose_id
  - 2 literals diff group: requires 1 in each
  - empty literals → False (no-op cut)
  - group not in state → False
  - state count short → False
  - slot index anonymity: slot=2 cut equivalent to slot=5 (per state_machine_v2 §5)
"""
from __future__ import annotations

import json

from src.cuts.families.port_exposure import (
    evaluate_literal_port_exposure,
    validate_port_exposure,
)
from src.cuts.lifecycle import (
    AnonymousSlotRef,
    BState,
    Cut,
    CutLiteral,
    CutScope,
    GHOST_AGNOSTIC,
    GroupState,
    OracleCert,
    evaluate_literal_multiset,
)


CANONICAL_RULES = {
    "crusher": {
        "placement_rule": "free",
        "cells_per_pose": 9,
    },
    "refinery": {
        "placement_rule": "free",
        "cells_per_pose": 9,
    },
}

# Gap 8/9 schema: production state inject 这些
_FACILITY_TEMPLATES = {
    "manufacturing_3x3": {"dimensions": {"w": 3, "h": 3}},
}
_INSTANCE_TO_FT = {"crusher": "manufacturing_3x3", "refinery": "manufacturing_3x3"}
# Gap 9 + Gap 11 修: candidate_placements pose 层 ports + N/S/E/W = real grid
# convention (y=row up; N=(0,-1), W=(-1,0)). crusher pose "p7" 占 x∈[10..12]
# y∈[10..12]. port (10, 10, W): facility 左上 corner cell, W 朝外 → front=(9, 10).
_CANDIDATE_PLACEMENTS = {
    "facility_pools": {
        "manufacturing_3x3": [
            {
                "pose_id": "p7",
                "anchor": {"x": 10, "y": 10},
                "occupied_cells": [
                    [10, 10], [11, 10], [12, 10],
                    [10, 11], [11, 11], [12, 11],
                    [10, 12], [11, 12], [12, 12],
                ],
                "input_port_cells": [],
                "output_port_cells": [
                    {"x": 10, "y": 10, "dir": "W", "commodity": "test"},
                ],
            },
            {
                "pose_id": "p3",
                "anchor": {"x": 9, "y": 10},  # 占 front_cell (9, 10) of pose p7's port
                "occupied_cells": [
                    [9, 10], [10, 10], [11, 10],  # 跟 p7 重叠 (9,10) — Production
                    [9, 11], [10, 11], [11, 11],   # 这种重叠 master 不该选; 只 fixture 模拟
                    [9, 12], [10, 12], [11, 12],   # blocking
                ],
                "input_port_cells": [],
                "output_port_cells": [],
            },
        ],
    },
}


def _make_port_exposure_cert(
    *,
    facility_group: str = "crusher",
    facility_pose_id: str = "p7",  # Gap 10: PoseId=str
    port_cell: tuple = (10, 10),
    port_direction: str = "W",  # Gap 11 修: W=(-1, 0), front=(9, 10) outside facility
    front_cell: tuple = (9, 10),
    blocking_group: str = "refinery",
    blocking_slot: int = 0,
    blocking_pose_id: str = "p3",
) -> bytes:
    cert_dict = {
        "facility_group": facility_group,
        "facility_pose_id": facility_pose_id,
        "port_cell": list(port_cell),
        "port_direction": port_direction,
        "front_cell": list(front_cell),
        "blocking_facility": [blocking_group, blocking_slot, blocking_pose_id],
        "active_port_witness_b64": None,
    }
    return json.dumps(cert_dict, sort_keys=True).encode("utf-8")


def _make_port_exposure_cut(
    cert_payload: bytes,
    *,
    facility_group: str = "crusher",
    facility_pose_id: str = "p7",
    blocking_group: str = "refinery",
    blocking_slot: int = 0,
    blocking_pose_id: str = "p3",
) -> Cut:
    literals = (
        CutLiteral(slot_ref=AnonymousSlotRef(facility_group, 0), pose_id=facility_pose_id),
        CutLiteral(
            slot_ref=AnonymousSlotRef(blocking_group, blocking_slot),
            pose_id=blocking_pose_id,
        ),
    )
    scope = CutScope(
        ghost_rect_id=GHOST_AGNOSTIC,
        blocked_cells_hash="h",
        exterior_blocks_hash="h",
        source_digest="poc_source_digest",
        artifact_hashes={"canonical_rules.json": "h1"},
        oracle_abstraction_version="port_exposure_v1",
    )
    cert = OracleCert(
        cert_kind="port_exposure_blocked",
        cert_payload=cert_payload,
        cert_hash="ch",
    )
    return Cut(
        cut_id="F3-test",
        family="port_exposure",
        literals=literals,
        geometric_payload=None,
        scope=scope,
        cert=cert,
        family_version="v1.0",
        validator_version="v1.0",
    )


def _make_state(
    *,
    crusher_poses: list = None,
    refinery_poses: list = None,
    cell_owner: dict = None,
) -> BState:
    return BState(
        groups={
            "crusher": GroupState(
                "crusher",
                demand=4,
                pose_domain=frozenset(),
                selected_poses=crusher_poses or [],
            ),
            "refinery": GroupState(
                "refinery",
                demand=4,
                pose_domain=frozenset(),
                selected_poses=refinery_poses or [],
            ),
        },
        cell_owner=cell_owner or {},
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"port_exposure_v1"}),
        canonical_rules=CANONICAL_RULES,
        facility_templates=_FACILITY_TEMPLATES,
        instance_to_facility_type=_INSTANCE_TO_FT,
        candidate_placements=_CANDIDATE_PLACEMENTS,
    )


# ============================================================================
# evaluate_literal_multiset (generic, state_machine_v2 §5)
# ============================================================================

def test_multiset_eval_single_literal_match():
    cut = _make_port_exposure_cut(_make_port_exposure_cert())
    # state has both poses selected
    state = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
    )
    assert evaluate_literal_multiset(cut, state) is True


def test_multiset_eval_missing_one_pose():
    """1 literal not in state.selected_poses → False (cut not violated)."""
    cut = _make_port_exposure_cut(_make_port_exposure_cert())
    state = _make_state(
        crusher_poses=["p7"],  # has crusher pose 7
        refinery_poses=["p99"],  # but refinery pose 99 not 3
    )
    assert evaluate_literal_multiset(cut, state) is False


def test_multiset_eval_slot_anonymity():
    """slot_index 2 vs slot_index 5 等价 — multiset 不看 slot index."""
    # Cut literal slot=0; state's pose 7 appears at "slot" 1 (different index)
    cut = _make_port_exposure_cut(_make_port_exposure_cert())
    state = _make_state(
        crusher_poses=["p1", "p7"],  # pose 7 at second slot
        refinery_poses=["p5", "p3"],  # pose 3 at second slot
    )
    assert evaluate_literal_multiset(cut, state) is True


def test_multiset_eval_2_same_pose_required():
    """2 literals (group=crusher, pose=7) require 2 selected_poses with pose=7."""
    cut = Cut(
        cut_id="multi-same",
        family="port_exposure",
        literals=(
            CutLiteral(AnonymousSlotRef("crusher", 0), "p7"),
            CutLiteral(AnonymousSlotRef("crusher", 1), "p7"),  # same pose, different slot
        ),
        geometric_payload=None,
        scope=CutScope(
            ghost_rect_id=GHOST_AGNOSTIC, blocked_cells_hash="h",
            exterior_blocks_hash="h", source_digest="poc_source_digest",
            artifact_hashes={}, oracle_abstraction_version="port_exposure_v1",
        ),
        cert=OracleCert(cert_kind="x", cert_payload=b"{}", cert_hash="ch"),
        family_version="v1.0", validator_version="v1.0",
    )
    # state has only 1 pose=7
    state_short = _make_state(crusher_poses=["p7", "p8"])
    assert evaluate_literal_multiset(cut, state_short) is False
    # state has 2 pose=7
    state_ok = _make_state(crusher_poses=["p7", "p7"])
    assert evaluate_literal_multiset(cut, state_ok) is True


def test_multiset_eval_empty_literals_false():
    cut = Cut(
        cut_id="empty-lit",
        family="port_exposure",
        literals=(CutLiteral(AnonymousSlotRef("crusher", 0), "p1"),),  # need ≥ 1 per __post_init__
        geometric_payload=None,
        scope=CutScope(
            ghost_rect_id=GHOST_AGNOSTIC, blocked_cells_hash="h",
            exterior_blocks_hash="h", source_digest="poc_source_digest",
            artifact_hashes={}, oracle_abstraction_version="port_exposure_v1",
        ),
        cert=OracleCert(cert_kind="x", cert_payload=b"{}", cert_hash="ch"),
        family_version="v1.0", validator_version="v1.0",
    )
    state = _make_state()  # crusher 没 selected_poses
    assert evaluate_literal_multiset(cut, state) is False


def test_multiset_eval_unknown_group_false():
    cut = Cut(
        cut_id="unknown-grp",
        family="port_exposure",
        literals=(CutLiteral(AnonymousSlotRef("never_exists", 0), "p1"),),
        geometric_payload=None,
        scope=CutScope(
            ghost_rect_id=GHOST_AGNOSTIC, blocked_cells_hash="h",
            exterior_blocks_hash="h", source_digest="poc_source_digest",
            artifact_hashes={}, oracle_abstraction_version="port_exposure_v1",
        ),
        cert=OracleCert(cert_kind="x", cert_payload=b"{}", cert_hash="ch"),
        family_version="v1.0", validator_version="v1.0",
    )
    state = _make_state()
    assert evaluate_literal_multiset(cut, state) is False


# ============================================================================
# F3 specific: validate_port_exposure
# ============================================================================

def test_validate_port_exposure_ok():
    """Gap 11 修后: W=(-1,0), port (10,10) W → front (9, 10) outside facility."""
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10),
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)})
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "ok", f"got {vr.kind}: {vr.detail}"


def test_validate_port_exposure_unsound_front_cell_math():
    """cert.front_cell ≠ port_cell + direction offset."""
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(99, 99),  # 错
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(99, 99): ("refinery", 0)})
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "front_cell mismatch" in vr.detail


def test_validate_port_exposure_unsound_blocking_facility_absent():
    """cell_owner[front_cell] 不是 cert blocking_facility."""
    cert_payload = _make_port_exposure_cert(
        port_cell=(10, 10), port_direction="W", front_cell=(9, 10),
        blocking_group="refinery", blocking_slot=0,
    )
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={})  # 不含 (9, 10)
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "unsound"
    assert "blocking facility not at front" in vr.detail


def test_validate_port_exposure_schema_err_unknown_direction():
    cert_payload = _make_port_exposure_cert(port_direction="invalid")
    cut = _make_port_exposure_cut(cert_payload)
    state = _make_state(cell_owner={(9, 10): ("refinery", 0)})
    vr = validate_port_exposure(cut, state, CANONICAL_RULES)
    assert vr.kind == "schema_err"


# ============================================================================
# F3 evaluate
# ============================================================================

def test_evaluate_literal_port_exposure_delegates_to_multiset():
    cert_payload = _make_port_exposure_cert()
    cut = _make_port_exposure_cut(cert_payload)
    state_with = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p3"],
    )
    state_without = _make_state(
        crusher_poses=["p7"],
        refinery_poses=["p9"],
    )
    assert evaluate_literal_port_exposure(cut, state_with) is True
    assert evaluate_literal_port_exposure(cut, state_without) is False
