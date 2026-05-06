from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_group_packing_precheck_promotion_spec import (
    build_phase3b_group_packing_precheck_promotion_spec,
    render_phase3b_group_packing_precheck_promotion_spec_markdown,
    render_phase3b_group_packing_precheck_promotion_spec_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _precheck_candidate_payload(*, sample_count: int = 51) -> dict:
    return {
        "metadata": {"source": "phase3b_group_packing_precheck_candidate_v1"},
        "candidate": {
            "key": "69x19",
            "ghost_rect": {"w": 69, "h": 19, "area": 1311},
        },
        "gate": {
            "design_gate_passed": True,
            "runtime_promotion_ready": False,
        },
        "group_packing_probe": {
            "enabled": True,
            "sample_count": sample_count,
            "feasible_count": 0,
            "infeasible_count": sample_count,
            "unknown_count": 0,
            "skipped_count": 0,
        },
        "group_packing_blockers": {
            "blocker_count": 2,
            "precheck_design_candidate": True,
            "blockers": [
                {
                    "group_id": "group::manufacturing_3x3::refinery_steel::8",
                    "facility_type": "manufacturing_3x3",
                    "solver_status": "CANDIDATE_COUNT_BELOW_REQUIRED",
                    "sample_count": sample_count - 1,
                    "anchor_indices": [53, 54],
                    "required_count_min": 17,
                    "required_count_max": 17,
                    "surviving_at_failure_min": 2,
                    "surviving_at_failure_max": 16,
                    "greedy_selected_min": 1,
                    "greedy_selected_max": 4,
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
                    "surviving_at_failure_max": 744,
                    "greedy_selected_min": 32,
                    "greedy_selected_max": 33,
                },
            ],
        },
        "checks": [
            {
                "check_id": "diagnostic_precheck_design_candidate",
                "status": "pass",
                "detail": "diagnostic blocker evidence is internally consistent",
            },
            {
                "check_id": "runtime_promotion_guard",
                "status": "fail",
                "detail": "diagnostic evidence is not terminal proof",
            },
        ],
    }


def test_promotion_spec_freezes_runtime_contract_without_promoting(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    input_path = (
        project_root
        / ".artifacts"
        / "phase3b_group_packing_precheck_candidate"
        / "precheck_candidate.json"
    )
    _write_json(input_path, _precheck_candidate_payload())

    spec = build_phase3b_group_packing_precheck_promotion_spec(project_root)

    assert spec["metadata"]["source"] == (
        "phase3b_group_packing_precheck_promotion_spec_v1"
    )
    assert spec["candidate"]["key"] == "69x19"
    assert spec["promotion_status"]["spec_ready_for_runtime_slice"] is True
    assert spec["promotion_status"]["runtime_promotion_ready"] is False
    assert spec["promotion_status"]["runtime_promotion_guarded"] is True
    assert spec["promotion_status"]["promotion_blocked_by"] == [
        "runtime_promotion_guard"
    ]
    assert spec["proposed_precheck_contract"]["precheck_reason"] == (
        "group_packing_exact_infeasible"
    )
    assert (
        "group_packing_precheck.blockers[].solver_status"
        in spec["proposed_precheck_contract"]["required_proof_summary_fields"]
    )
    assert [check["check_id"] for check in spec["checks"] if check["status"] == "fail"] == []

    markdown = render_phase3b_group_packing_precheck_promotion_spec_markdown(spec)
    text = render_phase3b_group_packing_precheck_promotion_spec_text(spec)
    assert "Runtime promotion ready: False" in markdown
    assert "group_packing_exact_infeasible" in markdown
    assert "refinery_blue_iron" in markdown
    assert "spec_ready_for_runtime_slice=True" in text


def test_promotion_spec_reports_missing_precheck_candidate(tmp_path: Path) -> None:
    spec = build_phase3b_group_packing_precheck_promotion_spec(tmp_path / "project")

    assert spec["promotion_status"]["spec_ready_for_runtime_slice"] is False
    assert spec["promotion_status"]["promotion_blocked_by"] == [
        "precheck_candidate_missing",
        "runtime_promotion_guard_missing",
    ]
    failed = {check["check_id"] for check in spec["checks"] if check["status"] == "fail"}
    assert "precheck_candidate_present" in failed
    assert "runtime_promotion_guard_present" in failed


def test_promotion_spec_requires_full_sample_coverage(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    input_path = project_root / "candidate.json"
    _write_json(input_path, _precheck_candidate_payload(sample_count=3))

    spec = build_phase3b_group_packing_precheck_promotion_spec(
        project_root,
        precheck_candidate_path=input_path,
        min_sample_count=51,
    )

    assert spec["promotion_status"]["spec_ready_for_runtime_slice"] is False
    assert "full_sample_coverage_gate" in spec["promotion_status"]["promotion_blocked_by"]
    failed = {check["check_id"] for check in spec["checks"] if check["status"] == "fail"}
    assert "full_sample_coverage_present" in failed


def test_promotion_spec_cli_no_write_and_default_write(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    input_path = project_root / "candidate.json"
    output_dir = tmp_path / "out"
    _write_json(input_path, _precheck_candidate_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_group_packing_precheck_promotion_spec.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--precheck-candidate",
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

    assert "phase3b group packing precheck promotion spec" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--precheck-candidate",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "promotion_spec_json=" in write.stdout
    payload = json.loads((output_dir / "promotion_spec.json").read_text(encoding="utf-8"))
    assert payload["promotion_status"]["spec_ready_for_runtime_slice"] is True
    assert (output_dir / "promotion_spec.md").exists()
    assert (output_dir / "promotion_spec.txt").exists()
