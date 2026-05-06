from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_proof_preserving_extraction_spec import (
    build_phase3b_coordinate_validation_proof_preserving_extraction_spec,
    render_phase3b_coordinate_validation_proof_preserving_extraction_spec_markdown,
    render_phase3b_coordinate_validation_proof_preserving_extraction_spec_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _precheck_candidate_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_coordinate_validation_precheck_candidate_v2"},
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "gate": {
            "design_gate_passed": True,
            "runtime_promotion_ready": False,
        },
        "joined_xy_current_blocker": {
            "active": True,
            "blocker_subtype": "master_start_incompatible_unknown",
            "workspace_master_branches": 12560,
            "workspace_master_conflicts": 216,
            "coordinate_validation_infeasible_count": 8,
        },
        "joined_xy_proof_preserving_candidate": {
            "design_ready": True,
            "core_label_count": 3,
            "anchor_sweep_all_infeasible": True,
            "standalone_pair_optimal": True,
            "recommendation": "proof candidate ready",
        },
    }


def _order_capacity_certificate_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_order_capacity_certificate_candidate_v1"
        },
        "gate": {
            "design_gate_passed": True,
            "proof_preserving_precheck_ready": False,
            "certificate_shape": "order_implied_x_overlap_upper_strip",
        },
        "evidence": {
            "free_ghost_infeasible_threshold_slots": 15,
            "fixed_anchor_infeasible_threshold_slots": 14,
            "standalone_pair_full_status": "OPTIMAL",
            "highest_non_exceeded_unknown_slot_index": 13,
            "exceeded_infeasible_slot_indices": [14, 15, 16],
        },
    }


def test_proof_preserving_extraction_spec_prefers_row_domain_bridge(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    precheck_path = project_root / "precheck.json"
    certificate_path = project_root / "certificate.json"
    _write_json(precheck_path, _precheck_candidate_payload())
    _write_json(certificate_path, _order_capacity_certificate_payload())

    report = build_phase3b_coordinate_validation_proof_preserving_extraction_spec(
        project_root,
        precheck_candidate_path=precheck_path,
        order_capacity_certificate_candidate_path=certificate_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_proof_preserving_extraction_spec_v1"
    )
    assert report["status"]["spec_ready_for_patch"] is True
    assert report["status"]["runtime_promotion_ready"] is False
    assert report["status"]["recommended_next_path"] == "row_domain_extraction"
    assert report["bridge_gap"]["anchored_case_bridge_missing"] is True
    assert "row-domain extraction" in report["status"]["recommendation"]
    markdown = render_phase3b_coordinate_validation_proof_preserving_extraction_spec_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_proof_preserving_extraction_spec_text(
        report
    )
    assert "Proof-Preserving Extraction Spec" in markdown
    assert "recommended_next_path=row_domain_extraction" in text


def test_proof_preserving_extraction_spec_fails_when_certificate_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    precheck_path = project_root / "precheck.json"
    _write_json(precheck_path, _precheck_candidate_payload())

    report = build_phase3b_coordinate_validation_proof_preserving_extraction_spec(
        project_root,
        precheck_candidate_path=precheck_path,
        order_capacity_certificate_candidate_path=project_root / "missing.json",
    )

    assert report["status"]["spec_ready_for_patch"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "order_capacity_certificate_present" in failed


def test_proof_preserving_extraction_spec_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    precheck_path = project_root / "precheck.json"
    certificate_path = project_root / "certificate.json"
    output_dir = tmp_path / "out"
    _write_json(precheck_path, _precheck_candidate_payload())
    _write_json(certificate_path, _order_capacity_certificate_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_proof_preserving_extraction_spec.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--precheck-candidate",
            str(precheck_path),
            "--order-capacity-certificate-candidate",
            str(certificate_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate-validation proof-preserving extraction spec" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--precheck-candidate",
            str(precheck_path),
            "--order-capacity-certificate-candidate",
            str(certificate_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "proof_preserving_extraction_spec_json=" in write.stdout
    payload = json.loads(
        (output_dir / "proof_preserving_extraction_spec.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["recommended_next_path"] == "row_domain_extraction"
    assert (output_dir / "proof_preserving_extraction_spec.md").exists()
    assert (output_dir / "proof_preserving_extraction_spec.txt").exists()
