"""Tests for the inventory-driven IndustrialPlanner outer-base bundle suite."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts.audit_industrial_planner_outer_base_bundle_suite import (
    build_outer_base_bundle_suite_result,
    load_outer_base_bundle_inventory,
    main,
    write_outer_base_bundle_suite_outputs,
)
from src.search.exact_campaign import atomic_write_json


_BLUEPRINT_RELATIVE_PATH = "data/examples/industrial_planner/full_demand_recipe_capacity_canonical_blueprint.json"


def _write_inventory(
    tmp_path: Path,
    output_dir: Path | None = None,
    *,
    bundle_id: str = "wuling_outer",
    entries: list[dict[str, object]] | None = None,
) -> Path:
    inventory_path = tmp_path / "outer_base_bundle_inventory.json"
    resolved_entries = entries or [
        {
            "bundle_id": bundle_id,
            "base_id": "wuling_protocol_core",
            "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
            "output_dir": str(output_dir),
            "notes": ["test inventory entry"],
        }
    ]
    atomic_write_json(
        inventory_path,
        {
            "inventory_version": 1,
            "entries": resolved_entries,
        },
    )
    return inventory_path


def test_outer_base_bundle_inventory_loader_resolves_repo_relative_blueprint(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated_outer_base_bundle"
    inventory_path = _write_inventory(tmp_path, output_dir)

    entries = load_outer_base_bundle_inventory(inventory_path)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.bundle_id == "wuling_outer"
    assert entry.base_id == "wuling_protocol_core"
    assert entry.output_dir == output_dir
    assert entry.blueprint_path.name == "full_demand_recipe_capacity_canonical_blueprint.json"
    assert entry.notes == ("test inventory entry",)


def test_outer_base_bundle_suite_writer_and_check_roundtrip(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated_outer_base_bundle"
    inventory_path = _write_inventory(tmp_path, output_dir)

    output_paths = write_outer_base_bundle_suite_outputs(inventory_path=inventory_path)

    assert set(output_paths.keys()) == {"wuling_outer"}
    assert (output_dir / "industrial_planner.blueprint.json").exists()
    assert (output_dir / "throughput_report.json").exists()

    result = build_outer_base_bundle_suite_result(inventory_path=inventory_path)

    assert result.is_clean is True
    assert result.checked_bundle_count == 1
    assert result.clean_bundle_count == 1
    assert result.checked_file_count == 11
    assert result.drift_entry_count == 0
    assert result.validator_clean_bundle_count == 1
    assert result.proven_equivalent_bundle_count == 1
    payload = result.to_dict()
    assert payload["summary"] == {
        "checked_bundle_count": 1,
        "clean_bundle_count": 1,
        "drift_bundle_count": 0,
        "checked_file_count": 11,
        "drift_entry_count": 0,
        "validator_clean_bundle_count": 1,
        "proven_equivalent_bundle_count": 1,
        "translated_outer_bundle_count": 1,
        "identity_outer_bundle_count": 0,
        "is_clean": True,
    }
    markdown = result.to_markdown()
    assert "IndustrialPlanner Outer Base Bundle Suite" in markdown
    assert "wuling_outer" in markdown
    assert "Overall status: `clean`" in markdown
    assert "in sync" in result.to_console_text()


def test_outer_base_bundle_suite_cli_detects_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "generated_outer_base_bundle"
    inventory_path = _write_inventory(tmp_path, output_dir)
    write_outer_base_bundle_suite_outputs(inventory_path=inventory_path)

    check_json_path = tmp_path / "outer_bundle_suite_check.json"
    check_markdown_path = tmp_path / "outer_bundle_suite_check.md"
    check_console_path = tmp_path / "outer_bundle_suite_check.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_outer_base_bundle_suite.py",
            "--inventory",
            str(inventory_path),
            "--check",
            "--check-json-output",
            str(check_json_path),
            "--check-markdown-output",
            str(check_markdown_path),
            "--check-console-output",
            str(check_console_path),
        ],
    )
    main()
    clean_output = capsys.readouterr().out
    assert "in sync" in clean_output
    assert json.loads(check_json_path.read_text(encoding="utf-8"))["summary"]["is_clean"] is True
    assert "IndustrialPlanner Outer Base Bundle Suite" in check_markdown_path.read_text(encoding="utf-8")
    assert check_console_path.read_text(encoding="utf-8").endswith("\n")

    (output_dir / "outer_export_probe.md").write_text("stale probe", encoding="utf-8")
    (output_dir / "throughput_report.json").unlink()

    result = build_outer_base_bundle_suite_result(inventory_path=inventory_path)
    assert result.is_clean is False
    assert result.drift_entry_count == 2
    entry_result = result.entries[0]
    assert {(entry.filename, entry.drift_kind) for entry in entry_result.check_result.drift_entries} == {
        ("outer_export_probe.md", "content_mismatch"),
        ("throughput_report.json", "missing"),
    }

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_outer_base_bundle_suite.py",
            "--inventory",
            str(inventory_path),
            "--check",
            "--check-json-output",
            str(check_json_path),
            "--check-markdown-output",
            str(check_markdown_path),
            "--check-console-output",
            str(check_console_path),
        ],
    )
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
    drift_output = capsys.readouterr().out
    assert "drift detected" in drift_output
    summary_payload = json.loads(check_json_path.read_text(encoding="utf-8"))
    assert summary_payload["summary"]["is_clean"] is False
    assert summary_payload["summary"]["drift_entry_count"] == 2
    markdown_text = check_markdown_path.read_text(encoding="utf-8")
    assert "Drift details" in markdown_text
    assert "throughput_report.json" in markdown_text
    console_text = check_console_path.read_text(encoding="utf-8")
    assert "drift detected" in console_text
    assert console_text.endswith("\n")


def test_outer_base_bundle_suite_tracks_translated_and_identity_cases(tmp_path: Path) -> None:
    wuling_dir = tmp_path / "generated_outer_base_bundle"
    valley4_dir = tmp_path / "generated_outer_base_bundle_valley4"
    inventory_path = _write_inventory(
        tmp_path,
        entries=[
            {
                "bundle_id": "wuling_outer",
                "base_id": "wuling_protocol_core",
                "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
                "output_dir": str(wuling_dir),
                "notes": ["translated larger-base example"],
            },
            {
                "bundle_id": "valley4_identity_outer",
                "base_id": "valley4_protocol_core",
                "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
                "output_dir": str(valley4_dir),
                "notes": ["degenerate identity example"],
            },
        ],
    )

    output_paths = write_outer_base_bundle_suite_outputs(inventory_path=inventory_path)

    assert set(output_paths.keys()) == {"wuling_outer", "valley4_identity_outer"}
    assert (wuling_dir / "industrial_planner.blueprint.json").exists()
    assert (valley4_dir / "industrial_planner.blueprint.json").exists()

    result = build_outer_base_bundle_suite_result(inventory_path=inventory_path)

    assert result.is_clean is True
    assert result.checked_bundle_count == 2
    assert result.clean_bundle_count == 2
    assert result.checked_file_count == 22
    assert result.drift_entry_count == 0
    assert result.validator_clean_bundle_count == 2
    assert result.proven_equivalent_bundle_count == 2
    assert result.translated_outer_bundle_count == 1
    assert result.identity_outer_bundle_count == 1
    markdown = result.to_markdown()
    assert "translated_outer_deployment" in markdown
    assert "identity_outer_deployment" in markdown
    assert "Translated outer bundles: 1" in markdown
    assert "Identity outer bundles: 1" in markdown
