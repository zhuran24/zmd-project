from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.precheck_promotion_spec import (
    build_phase3b_coordinate_validation_precheck_promotion_spec,
    render_phase3b_coordinate_validation_precheck_promotion_spec_markdown,
    render_phase3b_coordinate_validation_precheck_promotion_spec_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _precheck_candidate_payload(
    *,
    rejected_count: int = 8,
    matrix_count: int = 3,
    proof_ready: bool = False,
) -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_precheck_candidate_v2"
        },
        "candidate": {"key": "67x13"},
        "gate": {
            "design_gate_passed": True,
            "runtime_promotion_ready": False,
        },
        "coordinate_validation": {
            "rejected_count": rejected_count,
            "rejected_samples": [
                {
                    "anchor_idx": 118 + index,
                    "reason": "infeasible",
                    "status": "INFEASIBLE",
                    "forced_slot_field_count": 798,
                }
                for index in range(rejected_count)
            ],
        },
        "forced_anchor_solver_matrix": {
            "matrix_all_infeasible": matrix_count > 0,
            "infeasible_count": matrix_count,
            "entries": [
                {
                    "anchor_idx": 118,
                    "search_branching": branching,
                    "status": "INFEASIBLE",
                    "wall_time": 15.0 + index,
                    "branches": 0,
                    "conflicts": 0,
                }
                for index, branching in enumerate(["fixed", "automatic", "portfolio"][:matrix_count])
            ],
        },
        "joined_xy_proof_preserving_candidate": {
            "design_ready": True,
            "proof_preserving_precheck_ready": bool(proof_ready),
            "core_label_count": 3,
            "row_domain_runtime_patch_ready": bool(proof_ready),
            "runtime_patch_authored_in_code": bool(proof_ready),
            "authored_but_not_enableable": bool(proof_ready),
            "runtime_enablement_allowed": False,
        },
        "checks": [
            {
                "check_id": "runtime_promotion_guard",
                "status": "fail",
                "detail": "diagnostic evidence is not terminal proof",
            }
        ],
    }


def test_coordinate_promotion_spec_freezes_contract_without_promoting(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    input_path = (
        project_root
        / ".artifacts"
        / "phase3b_coordinate_validation_precheck_candidate"
        / "precheck_candidate.json"
    )
    _write_json(input_path, _precheck_candidate_payload())

    spec = build_phase3b_coordinate_validation_precheck_promotion_spec(project_root)

    assert spec["metadata"]["source"] == (
        "phase3b_coordinate_validation_precheck_promotion_spec_v1"
    )
    assert spec["candidate"]["key"] == "67x13"
    assert spec["promotion_status"]["spec_ready_for_runtime_slice"] is True
    assert spec["promotion_status"]["runtime_slice_implemented"] is True
    assert spec["promotion_status"]["runtime_promotion_ready"] is False
    assert spec["promotion_status"]["runtime_promotion_guarded"] is True
    assert spec["promotion_status"]["promotion_blocked_by"] == [
        "runtime_promotion_guard"
    ]
    assert "joined-XY proof-preserving extraction" in spec["promotion_status"][
        "recommendation"
    ]
    assert spec["proposed_precheck_contract"]["precheck_reason"] == (
        "coordinate_validation_infeasible"
    )
    assert (
        "coordinate_validation_precheck.rejected_anchors[]"
        in spec["proposed_precheck_contract"]["required_proof_summary_fields"]
    )
    assert spec["proposed_precheck_contract"]["runtime_env"] == {
        "max_anchors_env": "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS",
        "seconds_env": "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS",
        "default_max_anchors": 0,
        "default_seconds": 2.0,
    }
    assert spec["evidence_summary"]["joined_xy_proof_candidate_design_ready"] is True
    assert spec["evidence_summary"]["joined_xy_proof_candidate_ready"] is False
    assert spec["evidence_summary"]["joined_xy_proof_candidate_core_label_count"] == 3
    assert [check["check_id"] for check in spec["checks"] if check["status"] == "fail"] == []

    markdown = render_phase3b_coordinate_validation_precheck_promotion_spec_markdown(spec)
    text = render_phase3b_coordinate_validation_precheck_promotion_spec_text(spec)
    assert "Runtime slice implemented: True" in markdown
    assert "Runtime promotion ready: False" in markdown
    assert "coordinate_validation_infeasible" in markdown
    assert "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS" in markdown
    assert "spec_ready_for_runtime_slice=True" in text
    assert "runtime_slice_implemented=True" in text


def test_coordinate_promotion_spec_points_to_review_gate_after_runtime_patch(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    input_path = project_root / "candidate.json"
    _write_json(input_path, _precheck_candidate_payload(proof_ready=True))

    spec = build_phase3b_coordinate_validation_precheck_promotion_spec(
        project_root,
        precheck_candidate_path=input_path,
    )

    status = spec["promotion_status"]
    evidence = spec["evidence_summary"]
    assert status["spec_ready_for_runtime_slice"] is True
    assert status["runtime_promotion_ready"] is False
    assert evidence["joined_xy_proof_candidate_ready"] is True
    assert evidence["joined_xy_row_domain_runtime_patch_ready"] is True
    assert evidence["joined_xy_runtime_patch_authored_in_code"] is True
    assert evidence["joined_xy_authored_but_not_enableable"] is True
    assert "reviewed_runtime_patch_exists" in status["recommendation"]
    assert "before any B5A workspace rerun" in status["recommendation"]


def test_coordinate_promotion_spec_requires_coverage(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    input_path = project_root / "candidate.json"
    _write_json(input_path, _precheck_candidate_payload(rejected_count=2))

    spec = build_phase3b_coordinate_validation_precheck_promotion_spec(
        project_root,
        precheck_candidate_path=input_path,
        min_rejected_anchor_count=8,
    )

    assert spec["promotion_status"]["spec_ready_for_runtime_slice"] is False
    assert "rejected_anchor_coverage_gate" in spec["promotion_status"][
        "promotion_blocked_by"
    ]
    failed = {check["check_id"] for check in spec["checks"] if check["status"] == "fail"}
    assert "rejected_anchor_coverage_present" in failed


def test_coordinate_promotion_spec_cli_no_write_and_default_write(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    input_path = project_root / "candidate.json"
    output_dir = tmp_path / "out"
    _write_json(input_path, _precheck_candidate_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_precheck_promotion_spec.py"

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

    assert "phase3b coordinate-validation precheck promotion spec" in no_write.stdout
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

    assert "coordinate_promotion_spec_json=" in write.stdout
    payload = json.loads((output_dir / "promotion_spec.json").read_text(encoding="utf-8"))
    assert payload["promotion_status"]["spec_ready_for_runtime_slice"] is True
    assert (output_dir / "promotion_spec.md").exists()
    assert (output_dir / "promotion_spec.txt").exists()
