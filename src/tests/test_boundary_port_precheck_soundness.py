from __future__ import annotations

from types import MethodType
from typing import Any

from src.models.master_model import (
    BOUNDARY_STORAGE_PORT_SCREEN_GROUP_ID,
    MasterPlacementModel,
)


def _left_boundary_port_pose(y: int) -> dict[str, Any]:
    return {
        "pose_id": f"left_boundary_port_{y}",
        "anchor": {"x": 0, "y": y},
        "pose_params": {"orientation": 0, "port_mode": "default"},
        "occupied_cells": [(0, y), (0, y + 1), (0, y + 2)],
        "input_port_cells": [{"x": 1, "y": y + 1, "dir": "E"}],
        "output_port_cells": [],
    }


def _bottom_boundary_port_pose(x: int) -> dict[str, Any]:
    return {
        "pose_id": f"bottom_boundary_port_{x}",
        "anchor": {"x": x, "y": 0},
        "pose_params": {"orientation": 90, "port_mode": "default"},
        "occupied_cells": [(x, 0), (x + 1, 0), (x + 2, 0)],
        "input_port_cells": [{"x": x + 1, "y": 1, "dir": "N"}],
        "output_port_cells": [],
    }


def _boundary_port_screen_probe_model() -> MasterPlacementModel:
    poses = [_left_boundary_port_pose(y) for y in range(1, 68)] + [
        _bottom_boundary_port_pose(x) for x in range(1, 68)
    ]
    model = MasterPlacementModel.__new__(MasterPlacementModel)
    model._boundary_storage_port_feasibility_screen_cache = None
    model._mandatory_groups = [
        {
            "group_id": BOUNDARY_STORAGE_PORT_SCREEN_GROUP_ID,
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "count": 46,
        }
    ]
    model.facility_pools = {"boundary_storage_port": poses}

    def _candidate_pose_indices_for_group(
        self: MasterPlacementModel, group: dict[str, Any]
    ) -> tuple[int, ...]:
        return tuple(range(len(poses)))

    def _pose_cells(
        self: MasterPlacementModel, template: str, pose_idx: int
    ) -> set[tuple[int, int]]:
        assert template == "boundary_storage_port"
        return {tuple(cell) for cell in poses[int(pose_idx)]["occupied_cells"]}

    model._candidate_pose_indices_for_group = MethodType(
        _candidate_pose_indices_for_group,
        model,
    )
    model._pose_cells = MethodType(_pose_cells, model)
    return model


def test_boundary_port_precheck_does_not_treat_connector_cells_as_ghost_blockers() -> None:
    model = _boundary_port_screen_probe_model()
    screen_spec = MasterPlacementModel._boundary_storage_port_feasibility_screen_spec(model)

    payload = MasterPlacementModel.evaluate_boundary_port_feasibility_from_screen_spec(
        rules={"globals": {"grid": {"width": 70, "height": 70}}},
        ghost_rect=(39, 69),
        screen_spec=screen_spec,
    )

    # The anchor order is x-major then y-minor.  For 39x69 on a 70x70 grid,
    # anchor (1, 1) is index 1 * 2 + 1 = 3.  It leaves all left-edge port
    # occupied cells at x=0 and all bottom-edge occupied cells at y=0 outside
    # the ghost, so the boundary ports can still pack the required 46 slots.
    #
    # Connector cells at x=1 / y=1 do lie in the ghost.  Under the strict
    # emptiness ruling (owner 2026-08-05) that is no longer legal — but this
    # screen keeps ignoring them on purpose.  It is an optimistic anchor-level
    # filter: letting through more anchors than are truly feasible only means
    # under-pruning, and the strict rejection happens downstream in the routing
    # domain.  Tightening it here would prune the anchor domain itself and needs
    # its own soundness argument, so the loose reading is frozen deliberately
    # and this assertion is the freeze.
    assert payload["screen_pass_anchor_count"] > 0
    assert 3 in payload["screen_pass_anchor_indices"]
    assert set(screen_spec["interval_records_by_family"]["left"][0]["blocking_cells"]) == set(
        screen_spec["interval_records_by_family"]["left"][0]["cells"]
    )
