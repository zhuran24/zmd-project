"""Tests for the repo-level IndustrialPlanner checked-artifact suite."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts.audit_industrial_planner_checked_artifact_suite import (
    build_checked_artifact_suite_result,
    load_checked_artifact_family_inventory,
    main,
)
from scripts.audit_industrial_planner_full_demand_support_suite_inventory import (
    write_full_demand_support_suite_inventory_outputs,
)
from src.search.exact_campaign import atomic_write_json


_BLUEPRINT_RELATIVE_PATH = "data/examples/industrial_planner/full_demand_recipe_capacity_canonical_blueprint.json"


def _write_support_inventory(tmp_path: Path, output_dir: Path) -> Path:
    inventory_path = tmp_path / "full_demand_support_suite_inventory.json"
    atomic_write_json(
        inventory_path,
        {
            "inventory_version": 1,
            "entries": [
                {
                    "report_set_id": "default_full_demand_support_suite",
                    "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
                    "output_dir": str(output_dir),
                }
            ],
        },
    )
    return inventory_path


def _write_family_inventory(
    tmp_path: Path,
    *,
    support_inventory_path: Path,
    support_result_builder: str = (
        "scripts.audit_industrial_planner_full_demand_support_suite_inventory:"
        "build_full_demand_support_suite_inventory_result"
    ),
) -> Path:
    inventory_path = tmp_path / "checked_artifact_family_inventory.json"
    atomic_write_json(
        inventory_path,
        {
            "inventory_version": 1,
            "entries": [
                {
                    "family_id": "full_demand_support_suite",
                    "family_label": "IndustrialPlanner full-demand support report sets",
                    "inventory_path": str(support_inventory_path),
                    "result_builder": support_result_builder,
                    "scope_label_singular": "report set",
                    "checked_scope_count_attr": "checked_report_set_count",
                    "clean_scope_count_attr": "clean_report_set_count",
                }
            ],
        },
    )
    return inventory_path



def test_checked_artifact_suite_reports_clean_when_component_outputs_match(tmp_path: Path) -> None:
    support_dir = tmp_path / "industrial_planner"
    support_inventory_path = _write_support_inventory(tmp_path, support_dir)
    family_inventory_path = _write_family_inventory(
        tmp_path,
        support_inventory_path=support_inventory_path,
    )

    write_full_demand_support_suite_inventory_outputs(inventory_path=support_inventory_path)

    loaded_entries = load_checked_artifact_family_inventory(family_inventory_path)
    assert [entry.family_id for entry in loaded_entries] == [
        "full_demand_support_suite",
    ]

    result = build_checked_artifact_suite_result(family_inventory_path=family_inventory_path)

    assert result.is_clean is True
    assert result.family_inventory_path == family_inventory_path
    assert result.checked_family_count == 1
    assert result.clean_family_count == 1
    assert result.checked_file_count == 6
    assert result.drift_entry_count == 0
    payload = result.to_dict()
    assert payload["summary"] == {
        "checked_family_count": 1,
        "clean_family_count": 1,
        "drift_family_count": 0,
        "checked_suite_count": 1,
        "clean_suite_count": 1,
        "drift_suite_count": 0,
        "checked_file_count": 6,
        "drift_entry_count": 0,
        "is_clean": True,
    }
    assert payload["support_suite"]["summary"]["is_clean"] is True
    assert payload["support_suite"]["summary"]["checked_report_set_count"] == 1
    assert len(payload["families"]) == 1
    assert payload["families"][0]["inventory_entry"]["family_id"] == "full_demand_support_suite"

    markdown = result.to_markdown()
    assert "IndustrialPlanner Checked Artifact Suite" in markdown
    assert "checked-artifact family inventory" in markdown
    assert "full_demand_support_suite" in markdown
    assert "Overall status: `clean`" in markdown
    assert "current active inventory is intentionally minimal" in markdown



def test_checked_artifact_suite_cli_exits_nonzero_on_component_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    support_dir = tmp_path / "industrial_planner"
    support_inventory_path = _write_support_inventory(tmp_path, support_dir)
    family_inventory_path = _write_family_inventory(
        tmp_path,
        support_inventory_path=support_inventory_path,
    )

    write_full_demand_support_suite_inventory_outputs(inventory_path=support_inventory_path)

    (support_dir / "full_demand_support_overview.md").write_text("stale support overview", encoding="utf-8")

    result = build_checked_artifact_suite_result(family_inventory_path=family_inventory_path)
    assert result.is_clean is False
    assert result.clean_family_count == 0
    assert result.drift_entry_count == 1
    support_entry = result.support_suite_result.entries[0]
    assert {(entry.filename, entry.drift_kind) for entry in support_entry.check_result.drift_entries} == {
        ("full_demand_support_overview.md", "content_mismatch"),
    }

    json_output = tmp_path / "checked_artifact_suite.json"
    markdown_output = tmp_path / "checked_artifact_suite.md"
    console_output = tmp_path / "checked_artifact_suite.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_checked_artifact_suite.py",
            "--family-inventory",
            str(family_inventory_path),
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
            "--console-output",
            str(console_output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    output = capsys.readouterr().out
    assert "drift detected" in output
    assert "full_demand_support_suite" in output

    summary_payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert summary_payload["summary"]["is_clean"] is False
    assert summary_payload["summary"]["drift_entry_count"] == 1
    markdown_text = markdown_output.read_text(encoding="utf-8")
    assert "Drift details" in markdown_text
    assert "full_demand_support_overview.md" in markdown_text
    console_text = console_output.read_text(encoding="utf-8")
    assert "drift detected" in console_text
    assert console_text.endswith("\n")



def test_checked_artifact_suite_rejects_unresolvable_family_builder(tmp_path: Path) -> None:
    support_dir = tmp_path / "industrial_planner"
    support_inventory_path = _write_support_inventory(tmp_path, support_dir)
    family_inventory_path = _write_family_inventory(
        tmp_path,
        support_inventory_path=support_inventory_path,
        support_result_builder=(
            "scripts.audit_industrial_planner_full_demand_support_suite_inventory:not_a_real_builder"
        ),
    )

    with pytest.raises(ValueError) as excinfo:
        build_checked_artifact_suite_result(family_inventory_path=family_inventory_path)

    assert "did not resolve to a callable" in str(excinfo.value)
