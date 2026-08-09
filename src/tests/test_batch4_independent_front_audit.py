from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from docs.research.front_offset_incident_20260718.batch4_harness.independent_front_audit import (
    IndependentFrontAuditError,
    audit_files,
    audit_payloads,
    deterministic_json,
    main,
    run_canaries,
)


def _pose(
    body: list[list[int]],
    *,
    input_ports: list[dict[str, Any]] | None = None,
    output_ports: list[dict[str, Any]] | None = None,
    pose_id: str | None = None,
    anchor: dict[str, int] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "occupied_cells": body,
        "input_port_cells": input_ports or [],
        "output_port_cells": output_ports or [],
    }
    if pose_id is not None:
        result["pose_id"] = pose_id
    if anchor is not None:
        result["anchor"] = anchor
    return result


def _instance(report: dict[str, Any], instance_id: str) -> dict[str, Any]:
    return next(entry for entry in report["instances"] if entry["instance_id"] == instance_id)


def test_first_cell_blocked_second_cell_free_uses_stored_coordinate() -> None:
    report = audit_payloads(
        {
            "facility_pools": {
                "maker": [
                    _pose(
                        [[0, 0]],
                        output_ports=[{"x": 1, "y": 1, "dir": "E"}],
                    )
                ],
                "blocker": [_pose([[1, 1]])],
            }
        },
        {
            "solution": {
                "maker_001": {"facility_type": "maker", "pose_idx": 0},
                "blocker_001": {"facility_type": "blocker", "pose_idx": 0},
            }
        },
        grid_width=4,
        grid_height=4,
    )

    maker = _instance(report, "maker_001")
    assert maker["ports"][0]["front"] == [1, 1]
    assert maker["ports"][0]["classification"] == "occupied_by_other_body"
    assert maker["counts"]["occupied_by_other_body"] == 1
    assert maker["counts"]["free_of_body"] == 0


def test_first_cell_free_second_cell_blocked_does_not_apply_delta() -> None:
    report = audit_payloads(
        {
            "facility_pools": {
                "maker": [
                    _pose(
                        [[0, 0]],
                        output_ports=[{"x": 1, "y": 1, "dir": "E"}],
                    )
                ],
                "blocker": [_pose([[2, 1]])],
            }
        },
        {
            "solution": {
                "maker_001": {"facility_type": "maker", "pose_idx": 0},
                "blocker_001": {"facility_type": "blocker", "pose_idx": 0},
            }
        },
        grid_width=4,
        grid_height=4,
    )

    maker = _instance(report, "maker_001")
    assert maker["ports"][0]["front"] == [1, 1]
    assert maker["ports"][0]["classification"] == "free_of_body"
    assert maker["counts"]["occupied_by_other_body"] == 0
    assert maker["counts"]["free_of_body"] == 1


def test_opposite_ports_can_share_middle_cell_without_becoming_body_blockers() -> None:
    report = audit_payloads(
        {
            "facility_pools": {
                "left": [
                    _pose(
                        [[0, 1]],
                        output_ports=[{"x": 1, "y": 1, "dir": "E"}],
                    )
                ],
                "right": [
                    _pose(
                        [[2, 1]],
                        input_ports=[{"x": 1, "y": 1, "dir": "W"}],
                    )
                ],
            }
        },
        {
            "solution": {
                "left_001": {"facility_type": "left", "pose_idx": 0},
                "right_001": {"facility_type": "right", "pose_idx": 0},
            }
        },
        grid_width=4,
        grid_height=4,
    )

    assert report["totals"]["total_ports"] == 2
    assert report["totals"]["free_of_body"] == 2
    assert report["totals"]["occupied_by_other_body"] == 0
    assert all(entry["ports"][0]["body_owners"] == [] for entry in report["instances"])


def test_self_body_and_out_of_grid_are_reported_separately() -> None:
    report = audit_payloads(
        {
            "facility_pools": {
                "maker": [
                    _pose(
                        [[1, 1]],
                        input_ports=[{"x": 1, "y": 1, "dir": "N"}],
                        output_ports=[{"x": 4, "y": 0, "dir": "E"}],
                    )
                ]
            }
        },
        {
            "solution": {
                "maker_001": {"facility_type": "maker", "pose_idx": 0},
            }
        },
        grid_width=4,
        grid_height=4,
    )

    counts = _instance(report, "maker_001")["counts"]
    assert counts == {
        "free_of_body": 0,
        "in_grid": 1,
        "occupied_by_other_body": 0,
        "out_of_grid": 1,
        "self_body": 1,
        "total_ports": 2,
    }


def test_builtin_canaries_cover_all_three_incident_shapes() -> None:
    canaries = run_canaries()
    assert canaries["all_passed"] is True
    assert [case["id"] for case in canaries["cases"]] == [
        "first_cell_blocked_second_cell_free",
        "first_cell_free_second_cell_blocked",
        "opposite_ports_share_middle_cell",
    ]


def test_raw_and_wrapped_solution_shapes_and_input_hashes(tmp_path: Path) -> None:
    candidate_payload = {
        "facility_pools": {
            "maker": [_pose([[0, 0]], output_ports=[{"x": 0, "y": 1, "dir": "N"}])],
            "power_pole": [_pose([[2, 2]], anchor={"x": 2, "y": 2})],
            "box": [_pose([[3, 3]], pose_id="p_x03_y03")],
        }
    }
    instances_payload = [
        {"instance_id": "maker_001", "facility_type": "maker"},
    ]
    raw_solution = {
        "maker_001": 0,
        "ghost_pick": 4,
        "__c1_active_poles__": [{"pose_idx": 0, "anchor": {"x": 2, "y": 2}}],
        "pose_optional::box::p_x03_y03": 0,
    }

    raw_report = audit_payloads(candidate_payload, raw_solution, instances_payload)
    assert raw_report["selected_pose_count"] == 3
    assert raw_report["pose_index_mapping"] == {
        "entries_with_identity": 2,
        "selected_pose_count": 3,
        "status": "unverified_index_mapping",
        "uniquely_verified_entries": 2,
        "unverified_entries": 1,
    }
    assert raw_report["skipped_entries"] == [
        {"entry": "ghost_pick", "reason": "non_facility_marker"}
    ]

    wrapped_report = audit_payloads(
        candidate_payload,
        {
            "harness": "micro",
            "solution": {"maker_001": {"facility_type": "maker", "pose_idx": 0}},
        },
        instances_payload,
    )
    assert wrapped_report["selected_pose_count"] == 1

    candidate_path = tmp_path / "candidate.json"
    solution_path = tmp_path / "solution.json"
    instances_path = tmp_path / "instances.json"
    candidate_raw = json.dumps(candidate_payload, separators=(",", ":")).encode()
    solution_raw = json.dumps(raw_solution, separators=(",", ":")).encode()
    instances_raw = json.dumps(instances_payload, separators=(",", ":")).encode()
    candidate_path.write_bytes(candidate_raw)
    solution_path.write_bytes(solution_raw)
    instances_path.write_bytes(instances_raw)

    file_report = audit_files(candidate_path, solution_path, instances_path)
    assert file_report["inputs"]["candidate_pool"]["sha256"] == hashlib.sha256(
        candidate_raw
    ).hexdigest()
    assert file_report["inputs"]["solution"]["sha256"] == hashlib.sha256(
        solution_raw
    ).hexdigest()
    assert file_report["inputs"]["instances"]["sha256"] == hashlib.sha256(
        instances_raw
    ).hexdigest()
    assert deterministic_json(file_report) == deterministic_json(file_report)


def test_expected_candidate_sha256_is_enforced_and_marks_mapping_verified(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    solution_path = tmp_path / "solution.json"
    candidate_raw = json.dumps(
        {"facility_pools": {"maker": [_pose([[0, 0]])]}},
        separators=(",", ":"),
    ).encode()
    candidate_path.write_bytes(candidate_raw)
    solution_path.write_text(
        json.dumps({"maker_001": {"facility_type": "maker", "pose_idx": 0}}),
        encoding="utf-8",
    )
    candidate_sha = hashlib.sha256(candidate_raw).hexdigest()

    report = audit_files(
        candidate_path,
        solution_path,
        expected_candidate_sha256=candidate_sha.upper(),
    )
    assert report["pose_index_mapping"]["status"] == "verified_against_expected_candidate_sha256"
    assert report["pose_index_mapping"]["expected_candidate_sha256"] == candidate_sha
    assert report["pose_index_mapping"]["actual_candidate_sha256"] == candidate_sha
    assert report["pose_index_mapping"]["entries_verified_by_candidate_sha256"] == 1
    assert report["pose_index_mapping"]["unverified_entries"] == 0

    with pytest.raises(IndependentFrontAuditError, match="candidate pool SHA-256 mismatch"):
        audit_files(
            candidate_path,
            solution_path,
            expected_candidate_sha256="0" * 64,
        )


def test_pose_identity_can_independently_verify_index_mapping() -> None:
    report = audit_payloads(
        {
            "facility_pools": {
                "maker": [
                    _pose([[0, 0]], pose_id="pose-a", anchor={"x": 0, "y": 0}),
                    _pose([[1, 1]], pose_id="pose-b", anchor={"x": 1, "y": 1}),
                ]
            }
        },
        {
            "maker_001": {
                "facility_type": "maker",
                "pose_idx": 1,
                "pose_id": "pose-b",
                "anchor": {"x": 1, "y": 1},
            }
        },
    )

    assert report["pose_index_mapping"]["status"] == "verified_by_pose_identity"
    assert report["pose_index_mapping"]["uniquely_verified_entries"] == 1
    assert _instance(report, "maker_001")["pose_identity"] == {
        "carried_anchor": [1, 1],
        "carried_pose_id": "pose-b",
        "fields_present": ["pose_id", "anchor"],
        "matching_pool_pose_count": 1,
        "uniquely_identifies_selected_pose": True,
    }


@pytest.mark.parametrize(
    ("solution_identity", "error_fragment"),
    [
        ({"pose_id": "wrong-pose"}, "carries pose_id"),
        ({"anchor": {"x": 9, "y": 9}}, "carries anchor"),
    ],
)
def test_solution_carried_identity_must_match_selected_pose(
    solution_identity: dict[str, Any],
    error_fragment: str,
) -> None:
    with pytest.raises(IndependentFrontAuditError, match=error_fragment):
        audit_payloads(
            {
                "facility_pools": {
                    "maker": [
                        _pose([[0, 0]], pose_id="pose-a", anchor={"x": 0, "y": 0})
                    ]
                }
            },
            {
                "maker_001": {
                    "facility_type": "maker",
                    "pose_idx": 0,
                    **solution_identity,
                }
            },
        )


def test_optional_key_pose_id_and_c1_pole_anchor_are_validated() -> None:
    candidate_payload = {
        "facility_pools": {
            "box": [_pose([[0, 0]], pose_id="actual-box")],
            "power_pole": [_pose([[1, 1]], anchor={"x": 1, "y": 1})],
        }
    }
    with pytest.raises(IndependentFrontAuditError, match="carries pose_id"):
        audit_payloads(candidate_payload, {"pose_optional::box::wrong-box": 0})
    with pytest.raises(IndependentFrontAuditError, match="carries anchor"):
        audit_payloads(
            candidate_payload,
            {"__c1_active_poles__": [{"pose_idx": 0, "anchor": {"x": 2, "y": 2}}]},
        )


def test_cli_refuses_to_overwrite_existing_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    candidate_path = tmp_path / "candidate.json"
    solution_path = tmp_path / "solution.json"
    instances_path = tmp_path / "instances.json"
    output_path = tmp_path / "report.json"
    candidate_path.write_text(
        json.dumps({"facility_pools": {"maker": [_pose([[0, 0]])]}}),
        encoding="utf-8",
    )
    solution_path.write_text(
        json.dumps({"maker_001": {"facility_type": "maker", "pose_idx": 0}}),
        encoding="utf-8",
    )
    instances_path.write_text(
        json.dumps([{"instance_id": "maker_001", "facility_type": "maker"}]),
        encoding="utf-8",
    )
    output_path.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        main(
            [
                str(solution_path),
                "--candidate-pool",
                str(candidate_path),
                "--instances",
                str(instances_path),
                "--output",
                str(output_path),
            ]
        )

    assert "refusing to overwrite" in capsys.readouterr().err
    assert output_path.read_text(encoding="utf-8") == "sentinel\n"
