from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_power_coverage_witness_audit import (
    build_phase3b_power_coverage_witness_audit,
    render_phase3b_power_coverage_witness_audit_markdown,
    render_phase3b_power_coverage_witness_audit_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _residual_payload(*, powered_slots: int = 3, bad_vars: bool = False) -> dict:
    cover_count = powered_slots - 1 if bad_vars else powered_slots
    return {
        "metadata": {"source": "phase3b_residual_optional_encoding_inventory_v1"},
        "candidate": {"key": "67x13"},
        "encoding": {
            "master_slot_counts": {
                "mandatory": 2,
                "residual_optionals": {"power_pole": 3, "protocol_storage_box": 1},
            },
            "residual_optional_slots": {
                "by_template": {"power_pole": 3, "protocol_storage_box": 1},
                "total": 4,
            },
            "power_coverage": {
                "representation": "coordinate_geometric",
                "encoding": "geometric_element_witness_v1",
                "powered_slots": powered_slots,
                "pole_slots": 3,
                "cover_literals": 0,
                "witness_indices": powered_slots,
                "element_constraints": powered_slots * 3,
                "radius": 5,
            },
            "global_valid_inequalities": {
                "optional_cardinality_bounds": {
                    "power_pole": {"slot_pool_upper_bound": 3},
                    "protocol_storage_box": {"lower": 1},
                },
                "power_capacity_summary": {"family_count": 2, "raw_pole_count": 6},
            },
            "proto": {
                "variable_count": 100,
                "constraint_count": 200,
                "constraint_kind_counts": {
                    "element": powered_slots * 3 + 2,
                    "linear": 50,
                },
                "variable_prefix_counts": {
                    "cover_choice_idx": cover_count,
                    "cover_choice_active": powered_slots,
                    "cover_choice_x": powered_slots,
                    "cover_choice_y": powered_slots,
                },
            },
        },
    }


def _core_blocker_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_coverage_core_blocker_v1"},
        "candidate": {"key": "67x13"},
        "classification": "power_coverage_core_primary_protocol_lower_bound_not_primary",
        "combined_matrix": {
            "anchor_idx": 119,
            "base_status": "UNKNOWN",
            "skip_power_coverage_core_status": "OPTIMAL",
            "no_protocol_lower_bound_core_status": "UNKNOWN",
            "variant_statuses": {
                "base": "UNKNOWN",
                "skip_power_coverage_core": "OPTIMAL",
                "no_protocol_lower_bound_core": "UNKNOWN",
            },
        },
    }


def _relax_slice_payload() -> dict:
    entries = [
        {
            "variant": "base",
            "status": "UNKNOWN",
            "relaxed_power_coverage_linear_constraint_count": 0,
        },
        {
            "variant": "power_coverage_active_requirement_relaxed",
            "status": "INFEASIBLE",
            "relaxed_power_coverage_linear_constraint_count": 3,
        },
        {
            "variant": "power_coverage_geometry_bounds_relaxed",
            "status": "INFEASIBLE",
            "relaxed_power_coverage_linear_constraint_count": 12,
        },
        {
            "variant": "power_coverage_active_and_geometry_relaxed",
            "status": "INFEASIBLE",
            "relaxed_power_coverage_linear_constraint_count": 15,
        },
    ]
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "slice_matrix": {"entries": entries},
    }


def test_power_coverage_witness_audit_classifies_primary_blocker(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    core_path = project_root / "core.json"
    _write_json(residual_path, _residual_payload())
    _write_json(core_path, _core_blocker_payload())

    report = build_phase3b_power_coverage_witness_audit(
        project_root,
        residual_optional_encoding_path=residual_path,
        power_coverage_core_blocker_path=core_path,
    )

    assert report["metadata"]["source"] == "phase3b_power_coverage_witness_audit_v1"
    assert report["classification"] == "geometric_power_coverage_witness_primary_blocker"
    assert report["witness_encoding"]["element_constraints_per_powered_slot"] == 3.0
    assert report["witness_encoding"]["cover_choice_vars_complete"] is True
    assert report["witness_encoding"]["non_power_coverage_element_constraints"] == 2
    assert _check_status(report, "element_constraint_triplet_per_powered_slot") == "pass"
    assert _check_status(report, "protocol_lower_bound_not_primary") == "pass"
    assert "witness-domain feasibility" in report["recommendation"]

    markdown = render_phase3b_power_coverage_witness_audit_markdown(report)
    text = render_phase3b_power_coverage_witness_audit_text(report)
    assert "Power Coverage Witness Audit" in markdown
    assert "classification=geometric_power_coverage_witness_primary_blocker" in text


def test_power_coverage_witness_audit_classifies_full_skip_only(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    core_path = project_root / "core.json"
    relax_path = project_root / "relax.json"
    _write_json(residual_path, _residual_payload())
    _write_json(core_path, _core_blocker_payload())
    _write_json(relax_path, _relax_slice_payload())

    report = build_phase3b_power_coverage_witness_audit(
        project_root,
        residual_optional_encoding_path=residual_path,
        power_coverage_core_blocker_path=core_path,
        power_coverage_relax_slice_path=relax_path,
    )

    assert report["classification"] == "power_coverage_full_skip_only_primary_blocker"
    assert _check_status(report, "partial_power_coverage_linear_relaxations_infeasible") == "pass"
    assert report["domain_pressure"][
        "power_coverage_active_and_geometry_relaxed_status"
    ] == "INFEASIBLE"
    assert "global-valid-inequality" in report["recommendation"]


def test_power_coverage_witness_audit_flags_variable_count_mismatch(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    core_path = project_root / "core.json"
    _write_json(residual_path, _residual_payload(bad_vars=True))
    _write_json(core_path, _core_blocker_payload())

    report = build_phase3b_power_coverage_witness_audit(
        project_root,
        residual_optional_encoding_path=residual_path,
        power_coverage_core_blocker_path=core_path,
    )

    assert report["classification"] == "power_coverage_witness_encoding_invariant_mismatch"
    assert _check_status(report, "cover_choice_variables_match_powered_slots") == "fail"


def test_power_coverage_witness_audit_reports_missing_inputs(tmp_path: Path) -> None:
    report = build_phase3b_power_coverage_witness_audit(tmp_path / "project")

    assert report["classification"] == "power_coverage_witness_encoding_invariant_mismatch"
    assert _check_status(report, "residual_encoding_present") == "fail"
    assert _check_status(report, "core_blocker_present") == "fail"


def test_power_coverage_witness_audit_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    core_path = project_root / "core.json"
    output_dir = tmp_path / "out"
    _write_json(residual_path, _residual_payload())
    _write_json(core_path, _core_blocker_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_power_coverage_witness_audit.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--residual-optional-encoding",
            str(residual_path),
            "--power-coverage-core-blocker",
            str(core_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b power-coverage witness audit" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--residual-optional-encoding",
            str(residual_path),
            "--power-coverage-core-blocker",
            str(core_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "power_coverage_witness_audit_json=" in write.stdout
    payload = json.loads(
        (output_dir / "power_coverage_witness_audit.json").read_text(encoding="utf-8")
    )
    assert payload["classification"] == "geometric_power_coverage_witness_primary_blocker"
    assert (output_dir / "power_coverage_witness_audit.md").exists()
    assert (output_dir / "power_coverage_witness_audit.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
