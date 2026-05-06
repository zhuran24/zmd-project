from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_family_bound_semantic_audit import (
    build_phase3b_family_bound_semantic_audit,
    render_phase3b_family_bound_semantic_audit_markdown,
    render_phase3b_family_bound_semantic_audit_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _family_audit_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_audit_v1"},
        "candidate": {"key": "67x13"},
        "summary": {"all_bounds_consistent": True},
        "audits": [
            {
                "anchor_idx": 119,
                "target_power_family": "family_009",
                "bounds_consistent": True,
                "derivation": {
                    "family_size": 612,
                    "blocked_family_pose_count": 86,
                    "global_upper_bound": 612,
                    "derived_conditioned_upper_bound": 526,
                },
            }
        ],
    }


def _slice_payload(count_value: int | None = 0) -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "candidate": {"key": "67x13"},
        "campaign_state_unchanged": True,
        "slice_matrix": {
            "diagnostic_findings": [
                "anchor_119:target_power_family_bound_relaxation_unlocks_feasible_core"
            ],
            "entries": [
                {"variant": "base", "status": "UNKNOWN"},
                {
                    "variant": "target_power_family_bound_relaxed",
                    "status": "OPTIMAL",
                    "relaxed_power_family": "family_009",
                    "relaxed_power_family_count_value": count_value,
                    "relaxed_conditioned_power_family_bound_constraints_removed": 1,
                },
            ],
        },
    }


def test_semantic_audit_classifies_solver_sensitivity_without_bound_violation(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    family_path = project_root / "family.json"
    slice_path = project_root / "slice.json"
    _write_json(family_path, _family_audit_payload())
    _write_json(slice_path, _slice_payload(count_value=0))

    report = build_phase3b_family_bound_semantic_audit(
        project_root,
        family_bound_audit_path=family_path,
        target_family_slice_path=slice_path,
    )

    assert report["metadata"]["source"] == "phase3b_family_bound_semantic_audit_v1"
    assert report["classification"] == "solver_sensitivity_without_bound_violation"
    assert report["target_family_slice"]["relaxed_family_bound_violation"] == -526
    assert "target_bound_is_solver_sensitivity_not_semantic_violation" in report[
        "findings"
    ]
    assert _check_status(report, "relaxed_solution_violates_bound") == "pass"
    assert "solver/propagation sensitivity" in report["recommendation"]

    markdown = render_phase3b_family_bound_semantic_audit_markdown(report)
    text = render_phase3b_family_bound_semantic_audit_text(report)
    assert "Family Bound Semantic Audit" in markdown
    assert "classification=solver_sensitivity_without_bound_violation" in text


def test_semantic_audit_detects_relaxed_solution_bound_violation(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    family_path = project_root / "family.json"
    slice_path = project_root / "slice.json"
    _write_json(family_path, _family_audit_payload())
    _write_json(slice_path, _slice_payload(count_value=527))

    report = build_phase3b_family_bound_semantic_audit(
        project_root,
        family_bound_audit_path=family_path,
        target_family_slice_path=slice_path,
    )

    assert report["classification"] == "relaxed_solution_violates_conditioned_bound"
    assert report["target_family_slice"]["relaxed_family_bound_violation"] == 1
    assert _check_status(report, "relaxed_solution_violates_bound") == "fail"


def test_semantic_audit_cli_writes_and_no_write_skips(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    family_path = project_root / "family.json"
    slice_path = project_root / "slice.json"
    output_dir = tmp_path / "out"
    _write_json(family_path, _family_audit_payload())
    _write_json(slice_path, _slice_payload(count_value=0))
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_family_bound_semantic_audit.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--family-bound-audit",
            str(family_path),
            "--target-family-slice",
            str(slice_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b family-bound semantic audit" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--family-bound-audit",
            str(family_path),
            "--target-family-slice",
            str(slice_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_bound_semantic_audit_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_bound_semantic_audit.json").read_text(encoding="utf-8")
    )
    assert payload["classification"] == "solver_sensitivity_without_bound_violation"
    assert (output_dir / "family_bound_semantic_audit.md").exists()
    assert (output_dir / "family_bound_semantic_audit.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
