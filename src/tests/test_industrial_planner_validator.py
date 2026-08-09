"""Tests for the offline IndustrialPlanner blueprint validator."""

from __future__ import annotations

import json
from pathlib import Path

from src.adapters.industrial_planner.blueprint_validator import (
    validate_industrial_planner_blueprint,
    write_validation_reports,
)

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "industrial_planner"


def _load_json(name: str) -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_minimal_valid_fixture_passes_cleanly() -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("minimal.valid.industrial_planner.blueprint.json")
    )

    assert report.is_import_compatible is True
    assert report.is_layout_healthy is True
    assert report.is_clean is True
    assert report.schema_errors == []
    assert report.registry_errors == []
    assert report.lot_boundary_errors == []
    assert report.placement_constraint_errors == []
    assert report.overlap_errors == []
    assert report.port_mismatch_errors == []
    assert report.port_warnings == []


def test_benchmark_full70x70_fixture_passes_smoke_validation() -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("benchmark.full70x70.blueprint.json")
    )

    assert report.is_import_compatible is True
    assert report.is_layout_healthy is True
    assert report.is_clean is True
    assert report.device_count > 3000
    assert report.lot_utilization_percent > 70.0
    assert report.port_warnings == []


def test_foundation_conflict_fixture_fails_overlap_audit() -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("minimal.foundation_conflict.industrial_planner.blueprint.json")
    )

    assert report.is_import_compatible is True
    assert report.is_layout_healthy is False
    assert report.overlap_errors


def test_loader_without_bus_fixture_fails_placement_constraints() -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("minimal.loader_without_bus.blueprint.json")
    )

    assert report.is_import_compatible is False
    assert report.placement_constraint_errors
    assert any("bus" in error for error in report.placement_constraint_errors)


def test_belt_pipe_layering_fixture_allows_legal_cooccupancy() -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("minimal.belt_pipe_layering.blueprint.json")
    )

    assert report.is_import_compatible is True
    assert report.overlap_errors == []
    assert report.port_warnings


def test_port_mismatch_fixture_reports_error() -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("minimal.port_mismatch.blueprint.json")
    )

    assert report.is_layout_healthy is False
    assert report.port_mismatch_errors


def test_out_of_bounds_fixture_fails_lot_boundary_checks() -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("minimal.out_of_bounds.blueprint.json")
    )

    assert report.is_import_compatible is False
    assert report.lot_boundary_errors


def test_tier0_rejects_unknown_schema_type_rotation_and_item_ids() -> None:
    payload = {
        "schema": "wrong-blueprint-schema",
        "id": "bad-fixture",
        "version": "1.0",
        "name": "bad-fixture",
        "createdAt": "2026-03-28T00:00:00Z",
        "baseId": "valley4_protocol_core",
        "devices": [
            {
                "typeId": "unknown_type_id",
                "rotation": 45,
                "origin": {"x": 1.5, "y": 2},
                "config": {"pickupItemId": "blue_iron_ore"},
            }
        ],
    }

    report = validate_industrial_planner_blueprint(payload)

    assert report.is_import_compatible is False
    assert report.schema_errors
    assert report.registry_errors


def test_validator_reports_nonfatal_orphan_track_warning() -> None:
    payload = {
        "schema": "industrial-planner-blueprint",
        "id": "warning-fixture",
        "version": "1.0",
        "blueprintVersion": "1",
        "name": "warning-fixture",
        "createdAt": "2026-03-28T00:00:00Z",
        "baseId": "valley4_protocol_core",
        "devices": [
            {"typeId": "belt_straight_1x1", "rotation": 0, "origin": {"x": 25, "y": 25}},
        ],
    }

    report = validate_industrial_planner_blueprint(payload)

    assert report.is_import_compatible is True
    assert report.is_layout_healthy is True
    assert report.is_clean is False
    assert report.port_warnings


def test_validator_emits_json_and_markdown_reports_from_one_run(tmp_path: Path) -> None:
    report = validate_industrial_planner_blueprint(
        _load_json("minimal.valid.industrial_planner.blueprint.json")
    )
    json_path = tmp_path / "validation_report.json"
    markdown_path = tmp_path / "validation_report.md"

    write_validation_reports(report, json_output_path=json_path, markdown_output_path=markdown_path)

    written_json = json.loads(json_path.read_text(encoding="utf-8"))
    written_markdown = markdown_path.read_text(encoding="utf-8")

    assert written_json["is_clean"] is True
    assert "# IndustrialPlanner Validation Report" in written_markdown
