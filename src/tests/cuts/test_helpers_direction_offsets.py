"""M2 batch-C regressions — DIRECTION_OFFSETS vs canonical DIR_DELTA.

Pre-M2 the cut-helper direction table had N/S INVERTED relative to the
canonical convention (placement_generator.DIR_DELTA / master_model DIR_DELTA).
Against the real frozen artifact that inversion put every N/S port's computed
front cell INSIDE its own facility body (verified across all 599,384 ports,
2026-07-08) — yet the whole suite stayed green because every F3 direction
fixture used W/E, where both tables agree. These tests are the N/S pins that
did not exist; do not delete them when refactoring. See memory card
``p1-3-m2-coverage-stencil-ruling`` (batch C).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import pytest

from src.cuts.helpers.candidate_placements import DIRECTION_OFFSETS, direction_offset


def test_direction_offsets_match_canonical_dir_delta() -> None:
    """The cut-helper table must be item-for-item the canonical DIR_DELTA."""
    from src.placement.placement_generator import DIR_DELTA

    assert set(DIRECTION_OFFSETS) == set(DIR_DELTA)
    for direction, delta in DIR_DELTA.items():
        assert DIRECTION_OFFSETS[direction] == tuple(delta), direction


def test_north_south_semantics_pinned() -> None:
    """N means +y, S means -y (canonical). The retired table said the opposite.

    Real-artifact shape this pins: a facility occupying y∈[2..4] with an
    outside-adjacent N port at y=5 must have its front at y=6 (further out),
    NOT y=4 (inside the body — the pre-M2 bug).
    """
    assert DIRECTION_OFFSETS["N"] == (0, 1)
    assert DIRECTION_OFFSETS["S"] == (0, -1)
    port = (0, 5)
    front = (port[0] + direction_offset("N")[0], port[1] + direction_offset("N")[1])
    assert front == (0, 6)
    assert front != (0, 4)


def test_f3_north_port_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """N-direction port blocked by another facility: oracle emits, validator ok.

    The first F3 case ever to exercise a direction where the two historical
    tables disagree. Crusher occupies x∈[10..12] y∈[10..12] with an N port on
    its top edge at (11,12); canonical front is (11,13) — outside the body.
    A refinery row at y=13 occupies that front cell.
    """
    from src.cuts.families.port_exposure import validate_port_exposure
    from src.cuts.lifecycle import BState, Cell, GroupState
    from src.cuts.oracles.port_exposure_oracle import (
        ORACLE_NAME,
        generate_port_exposure_cuts,
    )

    monkeypatch.setenv("EXACT_F3_GENERATOR_ENABLED", "1")

    candidate_placements: Dict[str, Any] = {
        "facility_pools": {
            "manufacturing_3x3": [
                {
                    "pose_id": "pn",
                    "anchor": {"x": 10, "y": 10},
                    "occupied_cells": [
                        [10, 10], [11, 10], [12, 10],
                        [10, 11], [11, 11], [12, 11],
                        [10, 12], [11, 12], [12, 12],
                    ],
                    "input_port_cells": [],
                    "output_port_cells": [
                        {"x": 11, "y": 12, "dir": "N", "commodity": "test"},
                    ],
                },
                {
                    "pose_id": "p_above",
                    "anchor": {"x": 10, "y": 13},
                    "occupied_cells": [
                        [10, 13], [11, 13], [12, 13],
                        [10, 14], [11, 14], [12, 14],
                        [10, 15], [11, 15], [12, 15],
                    ],
                    "input_port_cells": [],
                    "output_port_cells": [],
                },
            ],
        },
    }
    cell_owner: Dict[Cell, Tuple[str, int]] = {}
    for c in [(10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11),
              (10, 12), (11, 12), (12, 12)]:
        cell_owner[c] = ("crusher", 0)
    for c in [(10, 13), (11, 13), (12, 13)]:
        cell_owner[c] = ("refinery", 0)

    state = BState(
        groups={
            "crusher": GroupState(
                "crusher", demand=1, pose_domain=frozenset(), selected_poses=["pn"],
            ),
            "refinery": GroupState(
                "refinery", demand=1, pose_domain=frozenset(),
                selected_poses=["p_above"],
            ),
        },
        cell_owner=cell_owner,
        ghost_rect=(40, 40, 5, 5),
        ghost_cells=frozenset(),
        exterior_blocks=frozenset(),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({ORACLE_NAME}),
        canonical_rules={
            "crusher": {"placement_rule": "free", "cells_per_pose": 9},
            "refinery": {"placement_rule": "free", "cells_per_pose": 9},
        },
        facility_templates={"manufacturing_3x3": {"dimensions": {"w": 3, "h": 3}}},
        instance_to_facility_type={
            "crusher": "manufacturing_3x3",
            "refinery": "manufacturing_3x3",
        },
        candidate_placements=candidate_placements,
    )

    cuts = generate_port_exposure_cuts(state, iter_index=1)
    assert len(cuts) == 1
    cert = json.loads(cuts[0].cert.cert_payload)
    assert cert["port_cell"] == [11, 12]
    assert cert["port_direction"] == "N"
    assert cert["front_cell"] == [11, 13]
    assert cert["blocking_facility"] == ["refinery", 0, "p_above"]

    result = validate_port_exposure(
        cuts[0],
        state,
        {
            "crusher": {"placement_rule": "free", "cells_per_pose": 9},
            "refinery": {"placement_rule": "free", "cells_per_pose": 9},
        },
    )
    assert result.kind == "ok", result.reason
