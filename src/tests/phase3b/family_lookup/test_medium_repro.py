from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import src.search.phase3b.family_lookup.medium_repro as medium_module
from src.search.phase3b.family_lookup.medium_repro import (
    build_phase3b_family_lookup_medium_repro,
    render_phase3b_family_lookup_medium_repro_markdown,
    render_phase3b_family_lookup_medium_repro_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "67x13": {
                "ghost_rect": {"w": 67, "h": 13, "area": 871},
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 1,
                        "failed_anchor_samples": [{"anchor_idx": 119}],
                    }
                },
            }
        },
    }


def _small_extraction() -> dict:
    return {
        "selected_slot_count": 2,
        "selected_slots": [
            {
                "slot_key": "power_pole_slot_a",
                "family_ids": [0, 1],
                "active_domain": [0, 1],
                "family_domain": [0, 2],
                "d_lo_domain": [0, 1],
                "d_hi_domain": [0, 1],
                "x_domain": [0, 2],
                "y_domain": [0, 2],
            },
            {
                "slot_key": "power_pole_slot_b",
                "family_ids": [0, 1],
                "active_domain": [0, 1],
                "family_domain": [0, 2],
                "d_lo_domain": [0, 1],
                "d_hi_domain": [0, 1],
                "x_domain": [0, 2],
                "y_domain": [0, 2],
            },
        ],
        "available_powered_slot_count": 3,
        "available_powered_template_counts": {
            "manufacturing_3x3": 1,
            "protocol_storage_box": 2,
        },
        "powered_template_filter": "protocol_storage_box",
        "selected_powered_slot_count": 2,
        "selected_powered_slots": [
            {
                "slot_key": "powered_a",
                "template": "protocol_storage_box",
                "dims": [1, 1],
                "x_domain": [0, 2],
                "y_domain": [0, 2],
            },
            {
                "slot_key": "powered_b",
                "template": "protocol_storage_box",
                "dims": [1, 1],
                "x_domain": [0, 2],
                "y_domain": [0, 2],
            },
        ],
        "selected_powered_template_counts": {"protocol_storage_box": 2},
        "scale_checks": {
            "requested_power_pole_slot_limit": 2,
            "requested_powered_slot_limit": 2,
            "selected_power_pole_slots_match_763": False,
            "protocol_storage_box_powered_slots_match_544": False,
        },
        "selected_family_ids": [0, 1],
        "selected_family_count": 2,
        "selected_rows_by_family_id": {
            "0": [[0, 0], [0, 1]],
            "1": [[0, 1], [1, 1]],
        },
        "selected_row_count": 4,
        "shell_value_min": 0,
        "shell_value_max": 1,
        "grid_width": 3,
        "grid_height": 3,
        "power_coverage_radius": 1,
    }


def test_family_lookup_medium_repro_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_family_lookup_medium_repro(tmp_path / "project")

    assert report["metadata"]["source"] == "phase3b_family_lookup_medium_repro_v1"
    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_family_lookup_medium_repro_builds_layered_standalone_models(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    monkeypatch.setattr(
        medium_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (SimpleNamespace(), object()),
    )
    monkeypatch.setattr(medium_module, "_clone_model_proto", lambda proto: proto)
    captured_extraction_kwargs = {}

    def fake_medium_repro_extraction(*args, **kwargs):
        captured_extraction_kwargs.update(kwargs)
        return _small_extraction()

    monkeypatch.setattr(
        medium_module,
        "_medium_repro_extraction",
        fake_medium_repro_extraction,
    )

    report = build_phase3b_family_lookup_medium_repro(
        project_root,
        candidate="67x13",
        anchor_indices=[119],
        variants=[
            "coverage_elements_only",
            "coverage_elements_family_table_geometry_x_min",
            "coverage_elements_family_table_geometry_y",
            "coverage_elements_family_table_geometry_x_min_y_max",
            "coverage_elements_family_table_geometry_x_delta",
            "coverage_literals_family_table",
            "coverage_literals_family_table_geometry_x",
            "coverage_pruned_literals_family_table_membership_geometry",
            "coverage_selected_coord_literals_family_table_membership_geometry",
            "coverage_elements_family_full",
            "coverage_elements_family_full_delta",
        ],
        slot_limit=2,
        powered_slot_limit=2,
        powered_template_filter="protocol_storage_box",
        family_limit_per_slot=2,
        worker_count=1,
        time_limit_seconds=2,
    )

    assert report["campaign_state_unchanged"] is True
    assert report["profile"]["powered_template_filter"] == "protocol_storage_box"
    assert captured_extraction_kwargs["powered_template_filter"] == "protocol_storage_box"
    assert report["extraction"]["selected_slot_count"] == 2
    assert report["extraction"]["selected_powered_slot_count"] == 2
    assert report["extraction"]["selected_powered_template_counts"] == {
        "protocol_storage_box": 2
    }
    assert report["status"]["outcome"] == "medium_repro_terminal_without_zero_branch"
    assert report["repro"]["status_counts"] == {"OPTIMAL": 11}

    entries = {entry["variant"]: entry for entry in report["repro"]["entries"]}
    assert entries["coverage_elements_only"]["element_constraint_count"] == 6
    assert entries["coverage_elements_only"]["family_table_constraint_count"] == 0
    assert entries["coverage_elements_only"]["membership_literal_count"] == 0
    assert (
        entries["coverage_elements_family_table_geometry_x_min"][
            "coverage_linear_constraint_count"
        ]
        == 4
    )
    assert (
        entries["coverage_elements_family_table_geometry_y"][
            "coverage_linear_constraint_count"
        ]
        == 6
    )
    assert (
        entries["coverage_elements_family_table_geometry_x_min_y_max"][
            "coverage_linear_constraint_count"
        ]
        == 6
    )
    assert (
        entries["coverage_elements_family_table_geometry_x_delta"][
            "coverage_linear_constraint_count"
        ]
        == 4
    )
    assert entries["coverage_literals_family_table"]["element_constraint_count"] == 0
    assert entries["coverage_literals_family_table"]["cover_literal_count"] == 4
    assert entries["coverage_literals_family_table"]["family_table_constraint_count"] == 2
    assert entries["coverage_literals_family_table"]["membership_literal_count"] == 0
    literal_x_entry = entries["coverage_literals_family_table_geometry_x"]
    assert literal_x_entry["element_constraint_count"] == 0
    assert literal_x_entry["cover_literal_count"] == 4
    assert literal_x_entry["coverage_linear_constraint_count"] == 14
    assert literal_x_entry["family_table_constraint_count"] == 2
    assert literal_x_entry["membership_literal_count"] == 0
    pruned_entry = entries["coverage_pruned_literals_family_table_membership_geometry"]
    assert pruned_entry["element_constraint_count"] == 0
    assert pruned_entry["cover_candidate_pair_count"] == 4
    assert pruned_entry["pruned_cover_candidate_pair_count"] == 4
    assert pruned_entry["powered_without_cover_candidate_count"] == 0
    selected_coord_entry = entries[
        "coverage_selected_coord_literals_family_table_membership_geometry"
    ]
    assert selected_coord_entry["cover_literal_count"] == 4
    assert selected_coord_entry["selected_coord_channel_constraint_count"] == 8
    assert entries["coverage_elements_family_full"]["element_constraint_count"] == 6
    assert entries["coverage_elements_family_full"]["family_table_constraint_count"] == 2
    assert entries["coverage_elements_family_full"]["membership_literal_count"] == 4
    assert entries["coverage_elements_family_full_delta"]["element_constraint_count"] == 6
    assert entries["coverage_elements_family_full_delta"]["coverage_linear_constraint_count"] == 6
    assert entries["coverage_elements_family_full_delta"]["family_table_constraint_count"] == 2
    assert entries["coverage_elements_family_full_delta"]["membership_literal_count"] == 4

    markdown = render_phase3b_family_lookup_medium_repro_markdown(report)
    text = render_phase3b_family_lookup_medium_repro_text(report)
    assert "Family Lookup Medium Repro" in markdown
    assert "Powered template filter" in markdown
    assert "outcome=medium_repro_terminal_without_zero_branch" in text
    assert "powered_template_filter=protocol_storage_box" in text


def test_family_lookup_medium_repro_domain_pruning_helper() -> None:
    powered = {"x_domain": [10, 12], "y_domain": [10, 12], "dims": [1, 1]}
    near_pole = {"x_domain": [15, 16], "y_domain": [15, 16]}
    far_pole = {"x_domain": [40, 41], "y_domain": [15, 16]}

    assert medium_module._cover_pair_domain_feasible(powered, near_pole, radius=5)
    assert not medium_module._cover_pair_domain_feasible(powered, far_pole, radius=5)


def test_family_lookup_medium_repro_filters_powered_slots_by_template() -> None:
    slots = [
        SimpleNamespace(key="m0", template="manufacturing_3x3", dims=(3, 3)),
        SimpleNamespace(key="p0", template="protocol_storage_box", dims=(3, 3)),
        SimpleNamespace(key="p1", template="protocol_storage_box", dims=(3, 3)),
        SimpleNamespace(key="m1", template="manufacturing_5x5", dims=(5, 5)),
    ]
    delegate = SimpleNamespace(
        grid_w=70,
        grid_h=70,
        _all_powered_slots=lambda: slots,
    )

    extracted = medium_module._extract_powered_slots(
        delegate,
        var_domains={},
        limit=10,
        template_filter="protocol_storage_box",
    )

    assert [slot["slot_key"] for slot in extracted] == ["p0", "p1"]
    assert medium_module._slot_template_counts(slots) == {
        "manufacturing_3x3": 1,
        "manufacturing_5x5": 1,
        "protocol_storage_box": 2,
    }
    assert medium_module._powered_slot_template_counts(extracted) == {
        "protocol_storage_box": 2
    }


def test_family_lookup_medium_repro_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "family_lookup" / "build_medium_repro.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b family lookup medium repro" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_lookup_medium_repro_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_lookup_medium_repro.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_family_lookup_medium_repro_v1"
    assert (output_dir / "family_lookup_medium_repro.md").exists()
    assert (output_dir / "family_lookup_medium_repro.txt").exists()


def _check_status(report: Mapping[str, Any], check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
