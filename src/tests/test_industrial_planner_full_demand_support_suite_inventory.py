"""Tests for the inventory-driven IndustrialPlanner full-demand support-suite wrapper."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts.audit_industrial_planner_full_demand_support_suite_inventory import (
    build_full_demand_support_suite_inventory_result,
    load_full_demand_support_suite_inventory,
    main,
    write_full_demand_support_suite_inventory_outputs,
)
from src.search.exact_campaign import atomic_write_json


_BLUEPRINT_RELATIVE_PATH = "data/examples/industrial_planner/full_demand_recipe_capacity_canonical_blueprint.json"


def _write_inventory(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    inventory_path = tmp_path / "full_demand_support_suite_inventory.json"
    atomic_write_json(
        inventory_path,
        {
            "inventory_version": 1,
            "entries": entries,
        },
    )
    return inventory_path


def test_support_suite_inventory_loader_resolves_repo_relative_blueprint(tmp_path: Path) -> None:
    output_dir = tmp_path / "industrial_planner"
    inventory_path = _write_inventory(
        tmp_path,
        [
            {
                "report_set_id": "protocol_core_transition_support_suite",
                "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
                "output_dir": str(output_dir),
                "base_ids": ["valley4_protocol_core", "wuling_protocol_core"],
                "notes": ["test support inventory entry"],
            }
        ],
    )

    entries = load_full_demand_support_suite_inventory(inventory_path)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.report_set_id == "protocol_core_transition_support_suite"
    assert entry.output_dir == output_dir
    assert entry.blueprint_path.name == "full_demand_recipe_capacity_canonical_blueprint.json"
    assert entry.base_ids == ("valley4_protocol_core", "wuling_protocol_core")
    assert entry.notes == ("test support inventory entry",)



def test_support_suite_inventory_writer_and_check_roundtrip_with_single_active_report_set(
    tmp_path: Path,
) -> None:
    default_output_dir = tmp_path / "industrial_planner"
    inventory_path = _write_inventory(
        tmp_path,
        [
            {
                "report_set_id": "default_full_demand_support_suite",
                "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
                "output_dir": str(default_output_dir),
                "notes": ["active single-base report set"],
            }
        ],
    )

    output_paths = write_full_demand_support_suite_inventory_outputs(inventory_path=inventory_path)

    assert set(output_paths.keys()) == {
        "default_full_demand_support_suite",
    }
    assert (default_output_dir / "full_demand_base_support_matrix.json").exists()
    assert (default_output_dir / "full_demand_support_overview.md").exists()

    result = build_full_demand_support_suite_inventory_result(inventory_path=inventory_path)

    assert result.is_clean is True
    assert result.checked_report_set_count == 1
    assert result.clean_report_set_count == 1
    assert result.checked_file_count == 6
    assert result.drift_entry_count == 0
    assert result.default_contract_scope_report_set_count == 1
    assert result.explicit_subset_report_set_count == 0
    assert result.summed_audited_base_membership_count == 1
    assert result.unique_audited_base_count == 1
    assert result.audited_base_ids == (
        "valley4_protocol_core",
    )
    assert result.future_scope_base_count == 5
    assert result.future_scope_base_ids == (
        "valley4_infra_outpost",
        "valley4_rebuilt_command",
        "valley4_refugee_shelter",
        "wuling_protocol_core",
        "wuling_tianwangping_aid",
    )
    assert result.repeated_audited_base_count == 0
    assert result.repeated_audited_base_ids == ()
    assert result.status_transition_report_set_count == 0
    assert result.unique_status_transition_base_count == 0
    assert result.status_transition_base_ids == ()
    assert result.unlocked_base_count == 0
    assert result.unlocked_base_ids == ()
    assert result.best_available_proven_equivalent_base_count == 1
    assert result.unique_best_available_proven_equivalent_base_count == 1
    assert result.best_available_proven_equivalent_base_ids == (
        "valley4_protocol_core",
    )

    payload = result.to_dict()
    assert payload["summary"] == {
        "checked_report_set_count": 1,
        "clean_report_set_count": 1,
        "drift_report_set_count": 0,
        "checked_file_count": 6,
        "drift_entry_count": 0,
        "default_contract_scope_report_set_count": 1,
        "explicit_subset_report_set_count": 0,
        "summed_audited_base_membership_count": 1,
        "unique_audited_base_count": 1,
        "audited_base_ids": ["valley4_protocol_core"],
        "future_scope_base_count": 5,
        "future_scope_base_ids": [
            "valley4_infra_outpost",
            "valley4_rebuilt_command",
            "valley4_refugee_shelter",
            "wuling_protocol_core",
            "wuling_tianwangping_aid",
        ],
        "repeated_audited_base_count": 0,
        "repeated_audited_base_ids": [],
        "status_transition_report_set_count": 0,
        "unique_status_transition_base_count": 0,
        "status_transition_base_ids": [],
        "unlocked_base_count": 0,
        "unlocked_base_ids": [],
        "best_available_proven_equivalent_base_count": 1,
        "unique_best_available_proven_equivalent_base_count": 1,
        "best_available_proven_equivalent_base_ids": [
            "valley4_protocol_core",
        ],
        "is_clean": True,
    }
    markdown = result.to_markdown()
    assert "IndustrialPlanner Full-Demand Support Suite Inventory" in markdown
    assert "default_contract_scope" in markdown
    assert "Preserved future-scope bases referenced by listed report sets: 5" in markdown
    assert "Unique best-available `proven_equivalent` bases across listed report sets: 1" in markdown
    assert "in sync" in result.to_console_text()



def test_support_suite_inventory_cli_detects_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "industrial_planner"
    inventory_path = _write_inventory(
        tmp_path,
        [
            {
                "report_set_id": "default_full_demand_support_suite",
                "blueprint_path": _BLUEPRINT_RELATIVE_PATH,
                "output_dir": str(output_dir),
            }
        ],
    )
    write_full_demand_support_suite_inventory_outputs(inventory_path=inventory_path)

    check_json_path = tmp_path / "support_inventory_check.json"
    check_markdown_path = tmp_path / "support_inventory_check.md"
    check_console_path = tmp_path / "support_inventory_check.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_full_demand_support_suite_inventory.py",
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
    assert "IndustrialPlanner Full-Demand Support Suite Inventory" in check_markdown_path.read_text(
        encoding="utf-8"
    )
    assert check_console_path.read_text(encoding="utf-8").endswith("\n")

    (output_dir / "full_demand_support_overview.md").write_text("stale support overview", encoding="utf-8")
    (output_dir / "full_demand_base_support_matrix.json").unlink()

    result = build_full_demand_support_suite_inventory_result(inventory_path=inventory_path)
    assert result.is_clean is False
    assert result.drift_entry_count == 2
    entry_result = result.entries[0]
    assert {(entry.filename, entry.drift_kind) for entry in entry_result.check_result.drift_entries} == {
        ("full_demand_base_support_matrix.json", "missing"),
        ("full_demand_support_overview.md", "content_mismatch"),
    }

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_industrial_planner_full_demand_support_suite_inventory.py",
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
    assert "full_demand_base_support_matrix.json" in markdown_text
    console_text = check_console_path.read_text(encoding="utf-8")
    assert "drift detected" in console_text
    assert console_text.endswith("\n")
