"""Hand-verified samples lock the rotation -> (orientation, port_mode) mapping.

If anyone changes blueprint_to_master_hint.py rotation rules, this fails — and
that's intentional: the mapping is non-obvious and was hand-derived from IP v2
source + project pose data on 2026-05-16.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from blueprint_to_master_hint import (  # noqa: E402
    TYPE_ID_TO_FACILITY,
    build_pose_lookup,
    rotation_to_orient_mode,
)

CANDIDATE_PLACEMENTS_PATH = PROJECT_ROOT / "data" / "preprocessed" / "candidate_placements.json"


# Each row: (typeId, rotation, origin, expected_orientation, expected_port_mode, expected_pose_id)
# Hand-derived 2026-05-16 from IP v2 registry.ts ports0 + project pose data.
HAND_VERIFIED_SAMPLES = [
    (
        "item_port_unloader_1",
        180,
        (1, 0),
        1,
        "bottom_base",
        "p_x01_y00_o1_m_bottom_base",
    ),
    (
        "item_port_unloader_1",
        90,
        (0, 10),
        0,
        "left_base",
        "p_x00_y10_o0_m_left_base",
    ),
    (
        "item_port_grinder_1",
        0,
        (39, 10),
        0,
        "TB",
        "p_x39_y10_o0_m_TB",
    ),
    (
        "item_port_grinder_1",
        90,
        (2, 9),
        0,
        "LR",
        "p_x02_y09_o0_m_LR",
    ),
    (
        "item_port_grinder_1",
        180,
        (1, 2),
        0,
        "BT",
        "p_x01_y02_o0_m_BT",
    ),
    (
        "item_port_grinder_1",
        270,
        (11, 28),
        0,
        "RL",
        "p_x11_y28_o0_m_RL",
    ),
    (
        "item_port_thickener_1",
        90,
        (6, 11),
        1,
        "LR",
        "p_x06_y11_o1_m_LR",
    ),
    (
        "item_port_thickener_1",
        270,
        (30, 40),
        1,
        "RL",
        "p_x30_y40_o1_m_RL",
    ),
    (
        "item_port_planter_1",
        0,
        (40, 14),
        0,
        "TB",
        "p_x40_y14_o0_m_TB",
    ),
    (
        "item_port_planter_1",
        270,
        (35, 15),
        0,
        "RL",
        "p_x35_y15_o0_m_RL",
    ),
    (
        "item_port_storager_1",
        270,
        (10, 10),
        0,
        "omni",
        "p_x10_y10_o0_m_omni",
    ),
]


@pytest.fixture(scope="module")
def candidate_placements() -> dict:
    if not CANDIDATE_PLACEMENTS_PATH.exists():
        pytest.skip("candidate_placements.json not present")
    return json.loads(CANDIDATE_PLACEMENTS_PATH.read_text())


@pytest.fixture(scope="module")
def pose_lookup(candidate_placements: dict) -> dict:
    return build_pose_lookup(candidate_placements["facility_pools"])


@pytest.mark.parametrize(
    "type_id,rotation,origin,expected_orient,expected_port_mode,expected_pose_id",
    HAND_VERIFIED_SAMPLES,
)
def test_rotation_mapping_matches_hand_derivation(
    candidate_placements: dict,
    pose_lookup: dict,
    type_id: str,
    rotation: int,
    origin: tuple,
    expected_orient: int,
    expected_port_mode: str,
    expected_pose_id: str,
) -> None:
    facility_type = TYPE_ID_TO_FACILITY[type_id]

    orient_mode = rotation_to_orient_mode(facility_type, rotation)
    assert orient_mode is not None, (
        f"rotation_to_orient_mode returned None for {type_id} rot={rotation}"
    )
    orient, port_mode = orient_mode
    assert orient == expected_orient, (
        f"{type_id} rot={rotation}: orientation script={orient} expected={expected_orient}"
    )
    assert port_mode == expected_port_mode, (
        f"{type_id} rot={rotation}: port_mode script={port_mode} expected={expected_port_mode}"
    )

    key = (origin[0], origin[1], orient, port_mode)
    idx = pose_lookup[facility_type].get(key)
    assert idx is not None, (
        f"{type_id} at {origin} rot={rotation}: no pose match in {facility_type}"
    )
    pose = candidate_placements["facility_pools"][facility_type][idx]
    assert pose["pose_id"] == expected_pose_id, (
        f"{type_id} at {origin} rot={rotation}: pose_id script={pose['pose_id']} "
        f"expected={expected_pose_id}"
    )


def test_protocol_storage_box_rotation_is_omni_for_all_blueprint_rotations() -> None:
    assert TYPE_ID_TO_FACILITY["item_port_storager_1"] == "protocol_storage_box"
    assert {
        rotation_to_orient_mode("protocol_storage_box", rotation)
        for rotation in (0, 90, 180, 270, 13)
    } == {(0, "omni")}
