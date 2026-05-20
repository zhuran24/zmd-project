from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.family_bound.solver_profile import (
    build_phase3b_family_bound_solver_profile,
    render_phase3b_family_bound_solver_profile_markdown,
    render_phase3b_family_bound_solver_profile_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _slice_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "candidate": {"key": "67x13"},
        "campaign_state_unchanged": True,
        "slice_matrix": {
            "entries": [
                {
                    "variant": "base",
                    "status": "UNKNOWN",
                    "wall_time": 20.0,
                    "branches": 0,
                    "conflicts": 0,
                    "response_stats_parsed": {
                        "status": "UNKNOWN",
                        "deterministic_time": 5.0,
                    },
                },
                {
                    "variant": "target_power_family_bound_relaxed",
                    "status": "OPTIMAL",
                    "wall_time": 0.1,
                    "branches": 0,
                    "conflicts": 0,
                    "relaxed_power_family": "family_009",
                    "relaxed_power_family_count_value": 0,
                    "relaxed_conditioned_power_family_bound_constraints_removed": 1,
                    "response_stats_parsed": {
                        "status": "OPTIMAL",
                        "deterministic_time": 0.01,
                    },
                },
            ]
        },
    }


def _semantic_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_semantic_audit_v1"},
        "classification": "solver_sensitivity_without_bound_violation",
        "target_family_slice": {"relaxed_family_bound_violation": -526},
    }


def test_family_bound_solver_profile_classifies_bound_sensitivity(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    slice_path = project_root / "slice.json"
    semantic_path = project_root / "semantic.json"
    _write_json(slice_path, _slice_payload())
    _write_json(semantic_path, _semantic_payload())

    report = build_phase3b_family_bound_solver_profile(
        project_root,
        target_family_slice_path=slice_path,
        family_bound_semantic_audit_path=semantic_path,
    )

    assert report["metadata"]["source"] == "phase3b_family_bound_solver_profile_v1"
    assert report["classification"] == (
        "bound_present_unknown_bound_absent_terminal_without_violation"
    )
    assert report["comparison"]["wall_time_speedup"] == 200.0
    assert report["comparison"]["deterministic_time_speedup"] == 500.0
    assert _check_status(report, "relaxed_solution_does_not_violate_bound") == "pass"
    assert "presolve/search sensitivity" in report["recommendation"]

    markdown = render_phase3b_family_bound_solver_profile_markdown(report)
    text = render_phase3b_family_bound_solver_profile_text(report)
    assert "Family Bound Solver Profile" in markdown
    assert "classification=bound_present_unknown" in text


def test_family_bound_solver_profile_cli_writes_and_no_write_skips(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    slice_path = project_root / "slice.json"
    semantic_path = project_root / "semantic.json"
    output_dir = tmp_path / "out"
    _write_json(slice_path, _slice_payload())
    _write_json(semantic_path, _semantic_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "family_bound" / "build_solver_profile.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--target-family-slice",
            str(slice_path),
            "--family-bound-semantic-audit",
            str(semantic_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b family-bound solver profile" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--target-family-slice",
            str(slice_path),
            "--family-bound-semantic-audit",
            str(semantic_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_bound_solver_profile_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_bound_solver_profile.json").read_text(encoding="utf-8")
    )
    assert payload["comparison"]["wall_time_speedup"] == 200.0
    assert (output_dir / "family_bound_solver_profile.md").exists()
    assert (output_dir / "family_bound_solver_profile.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
