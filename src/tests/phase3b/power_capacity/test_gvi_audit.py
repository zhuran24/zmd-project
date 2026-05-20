from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.power_capacity.gvi_audit import (
    build_phase3b_power_capacity_gvi_audit,
    render_phase3b_power_capacity_gvi_audit_markdown,
    render_phase3b_power_capacity_gvi_audit_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _residual_payload(*, include_applied: bool = True) -> dict:
    gvi = {
        "powered_template_demands": {
            "manufacturing_3x3": 132,
            "protocol_storage_box": 1,
        },
        "aggregated_power_capacity_terms": {
            "applied": True,
            "raw_nonzero_terms": 100,
            "aggregated_nonzero_terms": 12,
        },
        "power_capacity_summary": {
            "applied": True,
            "family_count": 3,
            "raw_pole_count": 30,
            "shell_pair_count": 6,
            "compact_signature_class_count": 10,
        },
        "power_capacity_families": {
            "applied": True,
            "family_count": 3,
            "families": [
                {
                    "family_id": "family_001",
                    "size": 10,
                    "count_var_upper_bound": 5,
                    "coefficients": {"manufacturing_3x3": 2},
                }
            ],
        },
    }
    if include_applied:
        gvi["applied"] = [
            {
                "type": "power_capacity_lower_bound",
                "template": "manufacturing_3x3",
                "demand": 132,
                "nonzero_poles": 80,
            },
            {
                "type": "power_capacity_lower_bound",
                "template": "protocol_storage_box",
                "demand": 1,
                "nonzero_poles": 20,
            },
        ]
    return {
        "metadata": {"source": "phase3b_residual_optional_encoding_inventory_v1"},
        "candidate": {"key": "67x13"},
        "encoding": {"global_valid_inequalities": gvi},
    }


def _witness_payload(
    classification: str = "power_coverage_full_skip_only_primary_blocker",
) -> dict:
    return {
        "metadata": {"source": "phase3b_power_coverage_witness_audit_v1"},
        "candidate": {"key": "67x13"},
        "classification": classification,
        "domain_pressure": {
            "skip_power_coverage_core_status": "OPTIMAL",
            "power_coverage_active_and_geometry_relaxed_status": "INFEASIBLE",
        },
    }


def _relax_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "slice_matrix": {
            "entries": [
                {
                    "variant": "power_capacity_gvi_protocol_storage_box_relaxed",
                    "status": "INFEASIBLE",
                    "relaxed_power_capacity_gvi_constraint_count": 1,
                },
                {
                    "variant": "power_capacity_gvi_mandatory_templates_relaxed",
                    "status": "INFEASIBLE",
                    "relaxed_power_capacity_gvi_constraint_count": 3,
                },
                {
                    "variant": "power_capacity_gvi_all_relaxed",
                    "status": "INFEASIBLE",
                    "relaxed_power_capacity_gvi_constraint_count": 4,
                },
            ]
        },
    }


def test_power_capacity_gvi_audit_classifies_full_skip_suspect(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    witness_path = project_root / "witness.json"
    _write_json(residual_path, _residual_payload())
    _write_json(witness_path, _witness_payload())

    report = build_phase3b_power_capacity_gvi_audit(
        project_root,
        residual_optional_encoding_path=residual_path,
        power_coverage_witness_audit_path=witness_path,
    )

    assert report["metadata"]["source"] == "phase3b_power_capacity_gvi_audit_v1"
    assert report["classification"] == "power_capacity_gvi_full_skip_primary_suspect"
    assert report["power_capacity_gvi"]["lower_bound_count"] == 2
    assert report["power_capacity_gvi"]["aggregated_nonzero_terms"] == 12
    assert report["power_capacity_gvi"]["family_rows_present"] is True
    assert _check_status(report, "classification_actionable") == "pass"

    markdown = render_phase3b_power_capacity_gvi_audit_markdown(report)
    text = render_phase3b_power_capacity_gvi_audit_text(report)
    assert "Power Capacity GVI Audit" in markdown
    assert "lower_bound template=manufacturing_3x3" in text


def test_power_capacity_gvi_audit_classifies_lower_bounds_not_sufficient(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    witness_path = project_root / "witness.json"
    relax_path = project_root / "relax.json"
    _write_json(residual_path, _residual_payload())
    _write_json(witness_path, _witness_payload())
    _write_json(relax_path, _relax_payload())

    report = build_phase3b_power_capacity_gvi_audit(
        project_root,
        residual_optional_encoding_path=residual_path,
        power_coverage_witness_audit_path=witness_path,
        power_capacity_gvi_relax_slice_path=relax_path,
    )

    assert report["classification"] == "power_capacity_gvi_lower_bounds_not_sufficient"
    assert _check_status(report, "all_lower_bound_rows_relaxed_but_infeasible") == "pass"
    assert "family-membership" in report["recommendation"]


def test_power_capacity_gvi_audit_requests_refresh_without_applied_rows(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    witness_path = project_root / "witness.json"
    _write_json(residual_path, _residual_payload(include_applied=False))
    _write_json(witness_path, _witness_payload())

    report = build_phase3b_power_capacity_gvi_audit(
        project_root,
        residual_optional_encoding_path=residual_path,
        power_coverage_witness_audit_path=witness_path,
    )

    assert report["classification"] == "power_capacity_gvi_artifact_needs_refresh"
    assert _check_status(report, "power_capacity_lower_bounds_present") == "fail"


def test_power_capacity_gvi_audit_reports_missing_inputs(tmp_path: Path) -> None:
    report = build_phase3b_power_capacity_gvi_audit(tmp_path / "project")

    assert report["classification"] == "power_capacity_gvi_missing_residual_encoding"
    assert _check_status(report, "residual_encoding_present") == "fail"
    assert _check_status(report, "witness_audit_present") == "fail"


def test_power_capacity_gvi_audit_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    residual_path = project_root / "residual.json"
    witness_path = project_root / "witness.json"
    output_dir = tmp_path / "out"
    _write_json(residual_path, _residual_payload())
    _write_json(witness_path, _witness_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "power_capacity" / "build_gvi_audit.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--residual-optional-encoding",
            str(residual_path),
            "--power-coverage-witness-audit",
            str(witness_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b power-capacity GVI audit" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--residual-optional-encoding",
            str(residual_path),
            "--power-coverage-witness-audit",
            str(witness_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "power_capacity_gvi_audit_json=" in write.stdout
    payload = json.loads(
        (output_dir / "power_capacity_gvi_audit.json").read_text(encoding="utf-8")
    )
    assert payload["classification"] == "power_capacity_gvi_full_skip_primary_suspect"
    assert (output_dir / "power_capacity_gvi_audit.md").exists()
    assert (output_dir / "power_capacity_gvi_audit.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
