from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_group_packing_precheck_candidate import (
    build_phase3b_group_packing_precheck_candidate_summary,
    render_phase3b_group_packing_precheck_candidate_markdown,
    render_phase3b_group_packing_precheck_candidate_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _start_compatibility_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_start_compatibility_diagnostics_v1"},
        "candidate": {"key": "69x19"},
        "status": {
            "outcome": "diagnostic_group_packing_infeasible",
            "diagnostic_group_packing_precheck_design_candidate": True,
        },
        "diagnostics": {
            "group_packing_probe": {
                "enabled": True,
                "sample_count": 3,
                "feasible_count": 0,
                "infeasible_count": 3,
                "unknown_count": 0,
                "skipped_count": 0,
            },
            "group_packing_blockers": {
                "enabled": True,
                "blocker_count": 2,
                "sample_count": 3,
                "precheck_design_candidate": True,
                "blockers": [
                    {
                        "group_id": "group::manufacturing_3x3::refinery_steel::8",
                        "facility_type": "manufacturing_3x3",
                        "solver_status": "CANDIDATE_COUNT_BELOW_REQUIRED",
                        "sample_count": 2,
                        "anchor_indices": [53, 54],
                        "required_count_min": 17,
                        "required_count_max": 17,
                        "surviving_at_failure_min": 14,
                        "surviving_at_failure_max": 14,
                        "greedy_selected_min": 3,
                        "greedy_selected_max": 3,
                    },
                    {
                        "group_id": "group::manufacturing_3x3::refinery_blue_iron::7",
                        "facility_type": "manufacturing_3x3",
                        "solver_status": "INFEASIBLE",
                        "sample_count": 1,
                        "anchor_indices": [55],
                        "required_count_min": 34,
                        "required_count_max": 34,
                        "surviving_at_failure_min": 654,
                        "surviving_at_failure_max": 654,
                        "greedy_selected_min": 32,
                        "greedy_selected_max": 32,
                    },
                ],
            },
        },
    }


def test_precheck_candidate_gate_passes_design_but_blocks_runtime_promotion(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    input_path = project_root / ".artifacts" / "phase3b_start_compatibility" / "start_compatibility_69x19.json"
    _write_json(input_path, _start_compatibility_payload())

    summary = build_phase3b_group_packing_precheck_candidate_summary(project_root)

    assert summary["metadata"]["source"] == "phase3b_group_packing_precheck_candidate_v1"
    assert summary["candidate"]["key"] == "69x19"
    assert summary["gate"]["design_gate_passed"] is True
    assert summary["gate"]["runtime_promotion_ready"] is False
    assert summary["group_packing_blockers"]["blocker_count"] == 2
    assert [check["check_id"] for check in summary["checks"] if check["status"] == "fail"] == [
        "runtime_promotion_guard"
    ]

    markdown = render_phase3b_group_packing_precheck_candidate_markdown(summary)
    text = render_phase3b_group_packing_precheck_candidate_text(summary)
    assert "Runtime promotion ready: False" in markdown
    assert "refinery_blue_iron" in markdown
    assert "runtime_promotion_ready=False" in text


def test_precheck_candidate_gate_fails_with_missing_input(tmp_path: Path) -> None:
    summary = build_phase3b_group_packing_precheck_candidate_summary(tmp_path / "project")

    assert summary["gate"]["design_gate_passed"] is False
    failed = {check["check_id"] for check in summary["checks"] if check["status"] == "fail"}
    assert "start_compatibility_present" in failed
    assert "group_packing_probe_enabled" in failed


def test_precheck_candidate_cli_no_write_and_default_write(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    input_path = project_root / "input.json"
    output_dir = tmp_path / "out"
    _write_json(input_path, _start_compatibility_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_group_packing_precheck_candidate.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--start-compatibility",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b group packing precheck candidate gate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--start-compatibility",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "precheck_candidate_json=" in write.stdout
    payload = json.loads((output_dir / "precheck_candidate.json").read_text(encoding="utf-8"))
    assert payload["gate"]["design_gate_passed"] is True
    assert (output_dir / "precheck_candidate.md").exists()
    assert (output_dir / "precheck_candidate.txt").exists()
