"""Tests for the checked-in IndustrialPlanner outer-base bundle audit workflow."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts.audit_industrial_planner_outer_base_bundle import (
    build_outer_base_bundle_artifacts,
    check_outer_base_bundle_outputs,
    main,
    write_outer_base_bundle_outputs,
)


def test_outer_base_bundle_writer_and_check_roundtrip(tmp_path: Path) -> None:
    artifacts = build_outer_base_bundle_artifacts()
    output_dir = tmp_path / "generated_outer_base_bundle"

    paths = write_outer_base_bundle_outputs(output_dir=output_dir, artifacts=artifacts)

    assert set(paths.keys()) == {
        "deployment_plan_json",
        "deployment_plan_markdown",
        "probe_json",
        "probe_markdown",
        "outer_export_blueprint_json",
        "target_blueprint_json",
        "compatibility_manifest_json",
        "validation_json",
        "validation_markdown",
        "throughput_json",
        "throughput_markdown",
    }
    for output_path in paths.values():
        assert output_path.exists()

    validation_payload = json.loads(paths["validation_json"].read_text(encoding="utf-8"))
    throughput_payload = json.loads(paths["throughput_json"].read_text(encoding="utf-8"))
    manifest_payload = json.loads(paths["compatibility_manifest_json"].read_text(encoding="utf-8"))

    assert validation_payload["is_import_compatible"] is True
    assert validation_payload["is_layout_healthy"] is True
    assert throughput_payload["status"] == "proven_equivalent"
    assert manifest_payload["metadata"]["extensions"]["has_outer_deployment_plan"] is True

    clean_result = check_outer_base_bundle_outputs(output_dir=output_dir, artifacts=artifacts)
    assert clean_result.is_clean is True
    assert clean_result.checked_file_count == 11
    assert clean_result.validator_import_compatible is True
    assert clean_result.validator_layout_healthy is True
    assert clean_result.throughput_status == "proven_equivalent"
    assert clean_result.deployment_kind == "translated_outer_deployment"
    assert clean_result.drift_entries == ()
    assert "is in sync" in clean_result.to_console_text()
    assert "IndustrialPlanner Outer Base Bundle Check" in clean_result.to_markdown()


def test_outer_base_bundle_identity_roundtrip_for_canonical_size_base(tmp_path: Path) -> None:
    artifacts = build_outer_base_bundle_artifacts(base_id="valley4_protocol_core")
    output_dir = tmp_path / "generated_outer_base_bundle_valley4"

    paths = write_outer_base_bundle_outputs(output_dir=output_dir, artifacts=artifacts)

    plan_payload = json.loads(paths["deployment_plan_json"].read_text(encoding="utf-8"))
    validation_payload = json.loads(paths["validation_json"].read_text(encoding="utf-8"))
    throughput_payload = json.loads(paths["throughput_json"].read_text(encoding="utf-8"))

    assert plan_payload["base_id"] == "valley4_protocol_core"
    assert plan_payload["inner_island_origin"] == {"x": 0, "y": 0}
    assert plan_payload["moat_thickness_by_edge"] == {
        "top": 0,
        "right": 0,
        "bottom": 0,
        "left": 0,
    }
    assert plan_payload["export_mapping_summary_by_mode"] == {"identity": 273}
    assert validation_payload["is_import_compatible"] is True
    assert validation_payload["is_layout_healthy"] is True
    assert throughput_payload["status"] == "proven_equivalent"

    clean_result = check_outer_base_bundle_outputs(output_dir=output_dir, artifacts=artifacts)
    assert clean_result.is_clean is True
    assert clean_result.checked_file_count == 11
    assert clean_result.deployment_kind == "identity_outer_deployment"
    assert clean_result.validator_import_compatible is True
    assert clean_result.validator_layout_healthy is True
    assert clean_result.throughput_status == "proven_equivalent"


def test_outer_base_bundle_check_and_cli_detect_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifacts = build_outer_base_bundle_artifacts()
    output_dir = tmp_path / "generated_outer_base_bundle"
    write_outer_base_bundle_outputs(output_dir=output_dir, artifacts=artifacts)

    check_json_path = tmp_path / "outer_bundle_check.json"
    check_markdown_path = tmp_path / "outer_bundle_check.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_outer_base_bundle.py",
            "--output-dir",
            str(output_dir),
            "--check",
            "--check-json-output",
            str(check_json_path),
            "--check-markdown-output",
            str(check_markdown_path),
        ],
    )
    main()
    clean_output = capsys.readouterr().out
    assert "in sync" in clean_output
    assert json.loads(check_json_path.read_text(encoding="utf-8"))["is_clean"] is True
    assert "IndustrialPlanner Outer Base Bundle Check" in check_markdown_path.read_text(encoding="utf-8")

    (output_dir / "outer_export_probe.md").write_text("stale probe", encoding="utf-8")
    (output_dir / "throughput_report.json").unlink()

    drift_result = check_outer_base_bundle_outputs(output_dir=output_dir, artifacts=artifacts)
    assert drift_result.is_clean is False
    assert {(entry.filename, entry.drift_kind) for entry in drift_result.drift_entries} == {
        ("outer_export_probe.md", "content_mismatch"),
        ("throughput_report.json", "missing"),
    }

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_outer_base_bundle.py",
            "--output-dir",
            str(output_dir),
            "--check",
            "--check-json-output",
            str(check_json_path),
            "--check-markdown-output",
            str(check_markdown_path),
        ],
    )
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
    drift_output = capsys.readouterr().out
    assert "drift detected" in drift_output
    assert json.loads(check_json_path.read_text(encoding="utf-8"))["is_clean"] is False
    assert "Drift entries" in check_markdown_path.read_text(encoding="utf-8")
