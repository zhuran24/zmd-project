from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_zero_branch_unknown_triage import (
    build_phase3b_zero_branch_unknown_triage,
    render_phase3b_zero_branch_unknown_triage_markdown,
    render_phase3b_zero_branch_unknown_triage_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _matrix_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_solver_matrix_v1"},
        "candidate": {"key": "67x13"},
        "matrix": {
            "status_counts": {"INFEASIBLE": 3, "UNKNOWN": 21},
            "unknown_diagnostics": {
                "zero_branch_unknown_count": 21,
                "zero_branch_unknown_by_anchor": {"119": 3},
                "zero_branch_unknown_by_branching": {"fixed": 7},
                "zero_branch_unknown_samples": [
                    {
                        "anchor_idx": 119,
                        "search_branching": "fixed",
                        "branches": 0,
                        "conflicts": 0,
                    }
                ],
            },
        },
    }


def _inventory_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_failed_anchor_inventory_v1"},
        "candidate": {"key": "67x13"},
        "summary": {
            "classification_counts": {"coordinate_validation_rejected": 8},
            "forced_status_counts": {"INFEASIBLE": 3, "UNKNOWN": 24},
            "forced_zero_branch_unknown_count": 24,
        },
    }


def _power_delta_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_coverage_anchor_delta_v1"},
        "candidate": {"key": "67x13"},
        "delta": {
            "mandatory_surviving_delta": -3548,
            "optional_surviving_delta": -136,
            "power_family_changed_count": 13,
            "power_family_positive_delta_sum": 63,
            "power_family_negative_delta_sum": -14,
            "top_power_family_deltas": [
                {"family": "family_000", "left": 0, "right": 22, "delta": 22}
            ],
            "top_mandatory_group_deltas": [
                {
                    "group_id": "group::manufacturing_5x5::planter_sandleaf::10",
                    "facility_type": "manufacturing_5x5",
                    "baseline_surviving_count": 13128,
                    "comparison_surviving_count": 12868,
                    "surviving_delta": -260,
                }
            ],
            "optional_template_deltas": [
                {
                    "template": "power_pole",
                    "baseline_surviving_count": 3809,
                    "comparison_surviving_count": 3809,
                    "surviving_delta": 0,
                },
                {
                    "template": "protocol_storage_box",
                    "baseline_surviving_count": 14068,
                    "comparison_surviving_count": 13932,
                    "surviving_delta": -136,
                },
            ],
            "diagnostic_findings": [
                "power_family_bounds_shift",
                "power_pole_candidate_domain_stable_despite_family_bound_shift",
                "protocol_storage_box_domain_tightens",
            ],
        },
    }


def _slice_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_forced_anchor_model_slice_diagnostic_v1",
        },
        "slice_matrix": {
            "status_counts": {"UNKNOWN": 1, "OPTIMAL": 1},
            "diagnostic_findings": [
                "anchor_119:power_coverage_core_required_for_blocker",
                "anchor_119:residual_optionals_drive_unknown",
            ],
        },
    }


def test_zero_branch_unknown_triage_collects_matrix_inventory_and_slice(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    matrix_path = project_root / "matrix.json"
    inventory_path = project_root / "inventory.json"
    power_delta_path = project_root / "power_delta.json"
    slice_dir = project_root / "slices"
    _write_json(matrix_path, _matrix_payload())
    _write_json(inventory_path, _inventory_payload())
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(slice_dir / "slice.json", _slice_payload())

    report = build_phase3b_zero_branch_unknown_triage(
        project_root,
        solver_matrix_path=matrix_path,
        failed_anchor_inventory_path=inventory_path,
        power_coverage_anchor_delta_path=power_delta_path,
        model_slice_dir=slice_dir,
    )

    assert report["metadata"]["source"] == "phase3b_zero_branch_unknown_triage_v1"
    assert report["candidate"]["key"] == "67x13"
    assert report["matrix"]["zero_branch_unknown_count"] == 21
    assert report["power_coverage_anchor_delta"]["power_family_changed_count"] == 13
    assert "forced_anchor_matrix_has_zero_branch_unknown" in report["findings"]
    assert "adjacent_anchor_power_family_bounds_shift" in report["findings"]
    assert "comparison_anchor_has_looser_power_family_bounds" in report["findings"]
    assert "power_family_bounds_shift" in report["findings"]
    assert (
        "power_pole_candidate_domain_stable_despite_family_bound_shift"
        in report["findings"]
    )
    assert "power_coverage_core_is_primary_suspect" in report["findings"]
    assert "residual_optionals_are_involved" in report["findings"]
    assert "power coverage core/residual optional interactions" in report[
        "recommendation"
    ]

    markdown = render_phase3b_zero_branch_unknown_triage_markdown(report)
    text = render_phase3b_zero_branch_unknown_triage_text(report)
    assert "Zero-Branch UNKNOWN" in markdown
    assert "power_coverage_core_is_primary_suspect" in text


def test_zero_branch_unknown_triage_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    matrix_path = project_root / "matrix.json"
    inventory_path = project_root / "inventory.json"
    power_delta_path = project_root / "power_delta.json"
    slice_dir = project_root / "slices"
    output_dir = tmp_path / "out"
    _write_json(matrix_path, _matrix_payload())
    _write_json(inventory_path, _inventory_payload())
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(slice_dir / "slice.json", _slice_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_zero_branch_unknown_triage.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--solver-matrix",
            str(matrix_path),
            "--failed-anchor-inventory",
            str(inventory_path),
            "--power-coverage-anchor-delta",
            str(power_delta_path),
            "--model-slice-dir",
            str(slice_dir),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b zero-branch UNKNOWN triage" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--solver-matrix",
            str(matrix_path),
            "--failed-anchor-inventory",
            str(inventory_path),
            "--power-coverage-anchor-delta",
            str(power_delta_path),
            "--model-slice-dir",
            str(slice_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "zero_branch_unknown_triage_json=" in write.stdout
    payload = json.loads(
        (output_dir / "zero_branch_unknown_triage.json").read_text(encoding="utf-8")
    )
    assert payload["matrix"]["zero_branch_unknown_count"] == 21
    assert payload["power_coverage_anchor_delta"]["power_family_changed_count"] == 13
    assert (output_dir / "zero_branch_unknown_triage.md").exists()
    assert (output_dir / "zero_branch_unknown_triage.txt").exists()
