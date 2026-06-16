from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.power_coverage.core_blocker import (
    build_phase3b_power_coverage_core_blocker_report,
    render_phase3b_power_coverage_core_blocker_markdown,
    render_phase3b_power_coverage_core_blocker_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _slice_payload(entries: list[dict], findings: list[str] | None = None) -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "candidate": {"key": "67x13"},
        "slice_matrix": {
            "entries": entries,
            "diagnostic_findings": findings or [],
            "status_counts_by_variant": {
                str(entry["variant"]): {str(entry["status"]): 1} for entry in entries
            },
        },
    }


def _entry(variant: str, status: str) -> dict:
    return {"anchor_idx": 119, "variant": variant, "status": status}


def _residual_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_residual_optional_encoding_inventory_v1"},
        "candidate": {"key": "67x13"},
        "encoding": {
            "residual_optional_slots": {
                "by_template": {"power_pole": 763, "protocol_storage_box": 544},
                "total": 1307,
            },
            "power_coverage": {
                "representation": "coordinate_geometric",
                "encoding": "geometric_element_witness_v1",
                "powered_slots": 763,
                "pole_slots": 763,
                "witness_indices": 763,
                "element_constraints": 2289,
                "radius": 5,
            },
        },
    }


def _power_delta_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_coverage_anchor_delta_v1"},
        "candidate": {"key": "67x13"},
        "delta": {
            "power_family_changed_count": 13,
            "top_power_family_deltas": [
                {"family": "family_009", "baseline": 480, "comparison": 526, "delta": 46}
            ],
            "optional_template_deltas": [
                {
                    "template": "protocol_storage_box",
                    "baseline_surviving_count": 14068,
                    "comparison_surviving_count": 13932,
                    "surviving_delta": -136,
                }
            ],
        },
    }


def test_power_coverage_core_blocker_classifies_primary_core(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    core_path = project_root / "core.json"
    custom_path = project_root / "custom.json"
    residual_path = project_root / "residual.json"
    power_delta_path = project_root / "power_delta.json"
    _write_json(
        core_path,
        _slice_payload(
            [
                _entry("base", "UNKNOWN"),
                _entry("residual_all_inactive", "INFEASIBLE"),
                _entry("protocol_boxes_inactive", "INFEASIBLE"),
                _entry("power_poles_inactive", "INFEASIBLE"),
                _entry("skip_power_coverage_core", "OPTIMAL"),
            ],
            ["anchor_119:power_coverage_core_required_for_blocker"],
        ),
    )
    _write_json(
        custom_path,
        _slice_payload(
            [
                _entry("base", "UNKNOWN"),
                _entry("no_protocol_lower_bound_core", "UNKNOWN"),
                _entry("skip_power_coverage_no_protocol_lower_bound_core", "OPTIMAL"),
            ],
            [
                "anchor_119:protocol_lower_bound_not_primary",
                "anchor_119:skip_power_coverage_unlocks_feasible_core",
            ],
        ),
    )
    _write_json(residual_path, _residual_payload())
    _write_json(power_delta_path, _power_delta_payload())

    report = build_phase3b_power_coverage_core_blocker_report(
        project_root,
        core_slice_path=core_path,
        custom_core_slice_path=custom_path,
        residual_optional_encoding_path=residual_path,
        power_coverage_anchor_delta_path=power_delta_path,
    )

    assert report["metadata"]["source"] == "phase3b_power_coverage_core_blocker_v1"
    assert report["classification"] == (
        "power_coverage_core_primary_protocol_lower_bound_not_primary"
    )
    assert report["combined_matrix"]["skip_power_coverage_core_status"] == "OPTIMAL"
    assert report["combined_matrix"]["no_protocol_lower_bound_core_status"] == "UNKNOWN"
    assert _check_status(report, "skip_power_coverage_terminal") == "pass"
    assert _check_status(report, "protocol_lower_bound_not_primary") == "pass"
    assert "geometric power coverage" in report["recommendation"]

    markdown = render_phase3b_power_coverage_core_blocker_markdown(report)
    text = render_phase3b_power_coverage_core_blocker_text(report)
    assert "Power Coverage Core Blocker" in markdown
    assert "classification=power_coverage_core_primary" in text


def test_power_coverage_core_blocker_reports_missing_slices(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    report = build_phase3b_power_coverage_core_blocker_report(project_root)

    assert report["classification"] == "power_coverage_core_blocker_inconclusive"
    assert _check_status(report, "core_slice_present") == "fail"
    assert _check_status(report, "custom_core_slice_present") == "fail"


def test_power_coverage_core_blocker_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    core_path = project_root / "core.json"
    custom_path = project_root / "custom.json"
    residual_path = project_root / "residual.json"
    power_delta_path = project_root / "power_delta.json"
    _write_json(
        core_path,
        _slice_payload(
            [_entry("base", "UNKNOWN"), _entry("skip_power_coverage_core", "OPTIMAL")]
        ),
    )
    _write_json(
        custom_path,
        _slice_payload([_entry("no_protocol_lower_bound_core", "UNKNOWN")]),
    )
    _write_json(residual_path, _residual_payload())
    _write_json(power_delta_path, _power_delta_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "power_coverage" / "build_core_blocker.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--core-slice",
            str(core_path),
            "--custom-core-slice",
            str(custom_path),
            "--residual-optional-encoding",
            str(residual_path),
            "--power-coverage-anchor-delta",
            str(power_delta_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b power-coverage core blocker" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--core-slice",
            str(core_path),
            "--custom-core-slice",
            str(custom_path),
            "--residual-optional-encoding",
            str(residual_path),
            "--power-coverage-anchor-delta",
            str(power_delta_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "power_coverage_core_blocker_json=" in write.stdout
    payload = json.loads(
        (output_dir / "power_coverage_core_blocker.json").read_text(encoding="utf-8")
    )
    assert payload["classification"].startswith("power_coverage_core_primary")
    assert (output_dir / "power_coverage_core_blocker.md").exists()
    assert (output_dir / "power_coverage_core_blocker.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
