"""Certified blueprint active-port projection regressions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from src.io.serializer import (
    build_blueprint_payload_from_certified_result,
    build_canonical_blueprint_payload,
)
from src.search.pr2_l0_fixed_witness_core import (
    TERMINAL_FIXED_WITNESS_AUDIT_FIELD,
    TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD,
    TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD,
    TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
    TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
    canonical_digest,
    extract_verified_terminal_active_port_specs,
)


def _placement_and_pools() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    placement = {
        "core_001": {
            "facility_type": "protocol_core",
            "pose_idx": 0,
            "anchor": {"x": 0, "y": 0},
        }
    }
    pools = {
        "protocol_core": [
            {
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                # Available pose slots are not necessarily active.  The first
                # slot is deliberately OOG to model an inactive edge slot.
                "input_port_cells": [
                    {"x": -1, "y": 0, "dir": "W", "commodity": "[TBD]"},
                    {"x": 0, "y": 1, "dir": "S", "commodity": "[TBD]"},
                ],
                "output_port_cells": [],
            }
        ]
    }
    return placement, pools


def _blueprint(*, active_port_specs: list[dict[str, Any]]) -> dict[str, Any]:
    placement, pools = _placement_and_pools()
    return build_canonical_blueprint_payload(
        placement_solution=placement,
        facility_pools=pools,
        ghost_rect={"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 1},
        export_timestamp="2026-07-18T00:00:00Z",
        active_port_specs=active_port_specs,
        grid_dimensions=(2, 2),
    )


def _certified_state(port_specs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    final_result = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "core_001": {
                "facility_type": "protocol_core",
                "pose_idx": 0,
                "anchor": {"x": 0, "y": 0},
            }
        },
        "search_status": "CERTIFIED",
        "search_stats": {},
    }
    solution = {
        "ghost_pick": {
            "facility_type": "ghost_rect",
            "pose_idx": 1,
            "anchor": {"x": 1, "y": 0},
        },
        **deepcopy(final_result["placement_solution"]),
    }
    ghost_rect = final_result["ghost_rect"]
    identity = {
        "candidate_key": "1x1",
        "solution_digest": canonical_digest(solution),
        "ghost_rect_digest": canonical_digest(ghost_rect),
        "ghost_cells_digest": canonical_digest([[1, 0]]),
    }
    identity["witness_input_digest"] = canonical_digest(identity)
    verdict = {
        "schema_version": TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
        "authority": TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
        "publishable": True,
        "projected_status": "CERTIFIED",
        **identity,
        "binding_assignment_digest": "1" * 64,
        "port_specs_digest": canonical_digest(port_specs),
        "routing_occupancy_digest": "2" * 64,
        "binding_status": "FEASIBLE",
        "routing_status": "FEASIBLE",
        "reason": None,
        "details": {"port_specs": deepcopy(port_specs), "port_count": len(port_specs)},
    }
    state = {
        "final_result": deepcopy(final_result),
        "candidates": {
            "1x1": {
                "status": "CERTIFIED",
                "ghost_rect": {"w": 1, "h": 1, "area": 1},
                "solution": solution,
                "proof_summary": {
                    TERMINAL_FIXED_WITNESS_AUDIT_FIELD: verdict,
                    TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD: True,
                    TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD: "CERTIFIED",
                },
            }
        },
    }
    return state, final_result


def test_explicit_empty_specs_do_not_export_inactive_oog_pose_slots() -> None:
    payload = _blueprint(active_port_specs=[])

    assert payload["facilities"][0]["active_ports"] == []


def test_certified_builder_rejects_none_active_port_specs() -> None:
    placement, pools = _placement_and_pools()
    with pytest.raises(ValueError, match="requires explicit active_port_specs"):
        build_blueprint_payload_from_certified_result(
            result={
                "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 1},
                "placement_solution": placement,
                "search_stats": {},
            },
            facility_pools=pools,
            active_port_specs=None,  # type: ignore[arg-type]
            grid_dimensions=(2, 2),
        )


def test_explicit_specs_export_actual_binding_ports() -> None:
    payload = _blueprint(
        active_port_specs=[
            {
                "instance_id": "core_001",
                "x": 0,
                "y": 1,
                "dir": "S",
                "type": "in",
                "commodity": "ore",
            }
        ]
    )

    assert payload["facilities"][0]["active_ports"] == [
        {"type": "input", "x": 0, "y": 1, "dir": "S", "commodity": "ore"}
    ]


def test_explicit_specs_cannot_relabel_a_concrete_pose_port() -> None:
    placement, pools = _placement_and_pools()
    pools["protocol_core"][0]["input_port_cells"][1]["commodity"] = "copper"

    with pytest.raises(ValueError, match="commodity does not match"):
        build_canonical_blueprint_payload(
            placement_solution=placement,
            facility_pools=pools,
            ghost_rect={"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 1},
            export_timestamp="2026-07-18T00:00:00Z",
            active_port_specs=[
                {
                    "instance_id": "core_001",
                    "x": 0,
                    "y": 1,
                    "dir": "S",
                    "type": "in",
                    "commodity": "ore",
                }
            ],
            grid_dimensions=(2, 2),
        )


@pytest.mark.parametrize(
    "specs,match",
    [
        (
            [
                {
                    "instance_id": "unknown_001",
                    "x": 0,
                    "y": 1,
                    "dir": "S",
                    "type": "in",
                    "commodity": "ore",
                }
            ],
            "unknown instance",
        ),
        (
            [
                {
                    "instance_id": "core_001",
                    "x": -1,
                    "y": 0,
                    "dir": "W",
                    "type": "in",
                    "commodity": "ore",
                }
            ],
            "out of grid bounds",
        ),
        (
            [
                {
                    "instance_id": "core_001",
                    "x": 1,
                    "y": 1,
                    "dir": "S",
                    "type": "in",
                    "commodity": "ore",
                }
            ],
            "does not match a selected pose slot",
        ),
        (
            [
                {
                    "instance_id": "core_001",
                    "x": 0,
                    "y": 1,
                    "dir": "S",
                    "type": "input",
                    "commodity": "ore",
                }
            ],
            "type is invalid",
        ),
        (
            [
                {
                    "instance_id": "core_001",
                    "x": 0,
                    "y": 1,
                    "dir": "S",
                    "type": "in",
                    "commodity": "ore",
                }
            ]
            * 2,
            "duplicates an active port",
        ),
    ],
)
def test_explicit_specs_reject_unknown_duplicate_and_oog_ports(
    specs: list[dict[str, Any]],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        _blueprint(active_port_specs=specs)


def test_verified_specs_helper_accepts_bound_specs_and_rejects_digest_tamper() -> None:
    specs = [
        {
            "instance_id": "core_001",
            "x": 0,
            "y": 1,
            "dir": "S",
            "type": "in",
            "commodity": "ore",
        }
    ]
    state, final_result = _certified_state(specs)

    assert extract_verified_terminal_active_port_specs(
        campaign_state=state,
        final_result=final_result,
    ) == specs

    state["candidates"]["1x1"]["proof_summary"][TERMINAL_FIXED_WITNESS_AUDIT_FIELD][
        "port_specs_digest"
    ] = "0" * 64
    with pytest.raises(ValueError, match="port_specs_digest mismatch"):
        extract_verified_terminal_active_port_specs(
            campaign_state=state,
            final_result=final_result,
        )


def test_verified_specs_helper_rejects_unknown_bound_instance() -> None:
    specs = [
        {
            "instance_id": "unknown_001",
            "x": 0,
            "y": 1,
            "dir": "S",
            "type": "in",
            "commodity": "ore",
        }
    ]
    state, final_result = _certified_state(specs)

    with pytest.raises(ValueError, match="references an unknown instance"):
        extract_verified_terminal_active_port_specs(
            campaign_state=state,
            final_result=final_result,
        )
