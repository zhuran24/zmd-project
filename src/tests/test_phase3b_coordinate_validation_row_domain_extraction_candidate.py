from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_row_domain_extraction_candidate import (
    build_phase3b_coordinate_validation_row_domain_extraction_candidate,
    render_phase3b_coordinate_validation_row_domain_extraction_candidate_markdown,
    render_phase3b_coordinate_validation_row_domain_extraction_candidate_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _extraction_spec_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_proof_preserving_extraction_spec_v1"
        },
        "status": {
            "spec_ready_for_patch": True,
            "runtime_promotion_ready": False,
            "recommended_next_path": "row_domain_extraction",
        },
        "bridge_gap": {
            "anchored_case_bridge_missing": True,
            "required_outputs": [
                "Extract deterministic row-domain witness",
                "Map anchored case",
            ],
        },
    }


def _certificate_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_order_capacity_certificate_candidate_v1"
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "evidence": {
            "free_ghost_infeasible_threshold_slots": 15,
            "fixed_anchor_infeasible_threshold_slots": 14,
            "highest_non_exceeded_unknown_slot_index": 13,
            "exceeded_infeasible_slot_indices": [14, 15, 16],
        },
    }


def _domain_inspection_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_anchor119_pair_x_core_domain_inspection_v1"},
        "slot_details": [
            {
                "x_overlaps_ghost": True,
                "ghost_avoiding_y_values": list(range(16, 66)),
            },
            {
                "x_overlaps_ghost": True,
                "ghost_avoiding_y_values": list(range(16, 66)),
            },
            {
                "x_overlaps_ghost": True,
                "ghost_avoiding_y_values": list(range(16, 61)),
            },
        ],
        "planter_order_implications": [
            {
                "slot_index": idx,
                "all_allowed_x_overlap_ghost": True,
                "implied_x_fixed": 1 if idx in {8, 10} else None,
            }
            for idx in range(11)
        ],
        "notes": {
            "order_key_scale_x": 280,
            "order_key_scale_y": 4,
            "interpretation": "domain inspection note",
        },
    }


def test_row_domain_extraction_candidate_design_gate_passes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    extraction_path = project_root / "extraction.json"
    certificate_path = project_root / "certificate.json"
    domain_path = project_root / "domain.json"
    _write_json(extraction_path, _extraction_spec_payload())
    _write_json(certificate_path, _certificate_payload())
    _write_json(domain_path, _domain_inspection_payload())

    report = build_phase3b_coordinate_validation_row_domain_extraction_candidate(
        project_root,
        extraction_spec_path=extraction_path,
        order_capacity_certificate_candidate_path=certificate_path,
        pair_x_core_domain_inspection_path=domain_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_row_domain_extraction_candidate_v1"
    )
    assert report["status"]["design_gate_passed"] is True
    assert report["status"]["runtime_promotion_ready"] is False
    assert report["status"]["recommended_next_step"] == "implement_row_domain_extraction_witness"
    assert report["evidence"]["core_slot_count"] == 3
    assert report["evidence"]["ghost_avoiding_y_counts"] == [50, 50, 45]
    assert report["evidence"]["planter_order_implication_count"] == 11
    assert report["evidence"]["implied_fixed_slots"] == [8, 10]
    assert "Row-domain extraction candidate is ready" in report["status"]["recommendation"]
    markdown = render_phase3b_coordinate_validation_row_domain_extraction_candidate_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_row_domain_extraction_candidate_text(
        report
    )
    assert "Row-Domain Extraction Candidate" in markdown
    assert "recommended_next_step=implement_row_domain_extraction_witness" in text


def test_row_domain_extraction_candidate_fails_if_extraction_path_not_row_domain(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    payload = _extraction_spec_payload()
    payload["status"]["recommended_next_path"] = "no_solve_certificate"
    extraction_path = project_root / "extraction.json"
    certificate_path = project_root / "certificate.json"
    domain_path = project_root / "domain.json"
    _write_json(extraction_path, payload)
    _write_json(certificate_path, _certificate_payload())
    _write_json(domain_path, _domain_inspection_payload())

    report = build_phase3b_coordinate_validation_row_domain_extraction_candidate(
        project_root,
        extraction_spec_path=extraction_path,
        order_capacity_certificate_candidate_path=certificate_path,
        pair_x_core_domain_inspection_path=domain_path,
    )

    assert report["status"]["design_gate_passed"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "recommended_next_path_is_row_domain_extraction" in failed


def test_row_domain_extraction_candidate_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    extraction_path = project_root / "extraction.json"
    certificate_path = project_root / "certificate.json"
    domain_path = project_root / "domain.json"
    output_dir = tmp_path / "out"
    _write_json(extraction_path, _extraction_spec_payload())
    _write_json(certificate_path, _certificate_payload())
    _write_json(domain_path, _domain_inspection_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_row_domain_extraction_candidate.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--extraction-spec",
            str(extraction_path),
            "--order-capacity-certificate-candidate",
            str(certificate_path),
            "--pair-x-core-domain-inspection",
            str(domain_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate-validation row-domain extraction candidate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--extraction-spec",
            str(extraction_path),
            "--order-capacity-certificate-candidate",
            str(certificate_path),
            "--pair-x-core-domain-inspection",
            str(domain_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "row_domain_extraction_candidate_json=" in write.stdout
    payload = json.loads(
        (output_dir / "row_domain_extraction_candidate.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["design_gate_passed"] is True
    assert (output_dir / "row_domain_extraction_candidate.md").exists()
    assert (output_dir / "row_domain_extraction_candidate.txt").exists()
