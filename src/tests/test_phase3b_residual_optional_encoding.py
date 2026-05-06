from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from ortools.sat.python import cp_model

import src.search.phase3b_residual_optional_encoding as encoding_module
from src.search.phase3b_residual_optional_encoding import (
    build_phase3b_residual_optional_encoding_inventory,
    render_phase3b_residual_optional_encoding_markdown,
    render_phase3b_residual_optional_encoding_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "69x19": {
                "ghost_rect": {"w": 69, "h": 19, "area": 1311},
                "status": "UNKNOWN",
                "proof_summary": {},
            }
        },
    }


def _patch_overlay(monkeypatch) -> None:
    proto_model = cp_model.CpModel()
    cover_choice_idx = proto_model.NewIntVar(0, 1, "cover_choice_idx__slot_a")
    cover_choice_active = proto_model.NewBoolVar("cover_choice_active__slot_a")
    x = proto_model.NewIntVar(0, 5, "cover_choice_x__slot_a")
    sig = proto_model.NewIntVar(0, 5, "residual_optional_signature_count__box__sig_0")
    fam = proto_model.NewIntVar(0, 5, "power_pole_family_count__family_001")
    proto_model.Add(cover_choice_idx + x >= 1)
    proto_model.Add(sig + fam >= cover_choice_active)
    fake_model = SimpleNamespace(
        build_stats={
            "master_slot_counts": {
                "residual_optionals": {"power_pole": 2, "protocol_storage_box": 1}
            },
            "domain_activation": {"residual_optional_slot_count": 3},
            "power_coverage": {
                "representation": "coordinate_geometric",
                "encoding": "geometric_element_witness_v1",
                "powered_slots": 3,
                "pole_slots": 2,
                "element_constraints": 9,
            },
            "global_valid_inequalities": {
                "applied": [
                    {
                        "type": "power_capacity_lower_bound",
                        "template": "protocol_storage_box",
                        "demand": 1,
                        "nonzero_poles": 2,
                    }
                ],
                "optional_cardinality_bounds": {
                    "protocol_storage_box": {"lower": 1}
                },
                "powered_template_demands": {"protocol_storage_box": 1},
                "aggregated_power_capacity_terms": {
                    "raw_nonzero_terms": 10,
                    "aggregated_nonzero_terms": 2,
                },
                "power_capacity_families": {
                    "applied": True,
                    "family_count": 1,
                    "raw_pole_count": 2,
                    "shell_pair_count": 1,
                    "compact_signature_class_count": 1,
                    "families": [
                        {
                            "family_id": "family_001",
                            "size": 2,
                            "count_var_upper_bound": 2,
                            "coefficients": {"protocol_storage_box": 1},
                        }
                    ],
                },
            },
        },
        _coordinate_delegate=SimpleNamespace(
            residual_optional_slots={
                "power_pole": [object(), object()],
                "protocol_storage_box": [object()],
            },
            required_optional_slots={},
        ),
    )
    monkeypatch.setattr(
        encoding_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, proto_model.Proto()),
    )


def test_residual_optional_encoding_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_residual_optional_encoding_inventory(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_residual_optional_encoding_summarizes_proto_and_build_stats(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch)

    report = build_phase3b_residual_optional_encoding_inventory(
        project_root,
        campaign_state_path=campaign_path,
    )

    assert report["status"]["outcome"] == "residual_optional_encoding_inventory_built"
    assert report["encoding"]["residual_optional_slots"]["total"] == 3
    assert report["encoding"]["power_coverage"]["element_constraints"] == 9
    gvi = report["encoding"]["global_valid_inequalities"]
    assert gvi["applied"][0]["type"] == "power_capacity_lower_bound"
    assert gvi["power_capacity_families"]["families"][0]["family_id"] == "family_001"
    assert report["encoding"]["proto"]["variable_prefix_counts"] == {
        "cover_choice_active": 1,
        "cover_choice_idx": 1,
        "cover_choice_x": 1,
        "power_pole_family_count": 1,
        "residual_optional_signature_count": 1,
    }

    markdown = render_phase3b_residual_optional_encoding_markdown(report)
    text = render_phase3b_residual_optional_encoding_text(report)
    assert "Residual Optional Encoding Inventory" in markdown
    assert "proto_variables=" in text


def test_residual_optional_encoding_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    output_dir = tmp_path / "out"
    _write_json(campaign_path, _campaign_state_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_residual_optional_encoding.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b residual optional encoding inventory" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "residual_optional_encoding_json=" in write.stdout
    payload = json.loads(
        (output_dir / "residual_optional_encoding.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == (
        "phase3b_residual_optional_encoding_inventory_v1"
    )
    assert (output_dir / "residual_optional_encoding.md").exists()
    assert (output_dir / "residual_optional_encoding.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
