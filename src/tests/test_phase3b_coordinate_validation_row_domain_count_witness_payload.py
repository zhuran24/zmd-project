from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_row_domain_count_witness_payload import (
    build_phase3b_coordinate_validation_row_domain_count_witness_payload,
    render_phase3b_coordinate_validation_row_domain_count_witness_payload_markdown,
    render_phase3b_coordinate_validation_row_domain_count_witness_payload_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _design_payload(*, shared_lower_bound: int | None = 16) -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_row_domain_count_witness_design_v1"
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "design_ready": True,
            "runtime_promotion_ready": False,
            "witness_shape": "three_label_overlap_above_strip_count_guard",
            "recommended_next_step": "implement_row_domain_count_witness",
            "recommendation": "design ready",
        },
        "witness_design": {
            "row_summaries": [
                {
                    "group_id": "group::manufacturing_5x5::planter_buckwheat::9",
                    "solution_id": "planter_buckwheat_009",
                    "slot_index": 8,
                    "template": "manufacturing_5x5",
                    "forced_x": 1,
                    "row_count": 260,
                    "avoiding_y_min": 16,
                    "avoiding_y_max": 65,
                    "avoiding_y_count": 50,
                    "below_y_count": 0,
                    "above_y_count": 50,
                },
                {
                    "group_id": "group::manufacturing_5x5::planter_buckwheat::9",
                    "solution_id": "planter_buckwheat_011",
                    "slot_index": 10,
                    "template": "manufacturing_5x5",
                    "forced_x": 5,
                    "row_count": 260,
                    "avoiding_y_min": 16,
                    "avoiding_y_max": 65,
                    "avoiding_y_count": 50,
                    "below_y_count": 0,
                    "above_y_count": 50,
                },
                {
                    "group_id": "group::protocol_core::protocol_core::18",
                    "solution_id": "protocol_core_001",
                    "slot_index": 0,
                    "template": "protocol_core",
                    "forced_x": 1,
                    "row_count": 120,
                    "avoiding_y_min": 16,
                    "avoiding_y_max": 60,
                    "avoiding_y_count": 45,
                    "below_y_count": 0,
                    "above_y_count": 45,
                },
            ],
            "shared_safe_strip_lower_bound": shared_lower_bound,
            "all_labels_overlap_all_anchors": True,
            "all_single_x_domain": True,
            "all_no_below_ghost_room": True,
            "implied_fixed_slots": [8, 10],
        },
        "count_witness": {
            "free_ghost_threshold": 15,
            "fixed_anchor_threshold": 14,
            "threshold_delta": 1,
            "highest_non_exceeded_unknown_slot_index": 13,
            "exceeded_infeasible_slot_indices": [14, 15, 16],
        },
    }


def test_row_domain_count_witness_payload_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    design_path = project_root / "design.json"
    _write_json(design_path, _design_payload())

    report = build_phase3b_coordinate_validation_row_domain_count_witness_payload(
        project_root,
        row_domain_count_witness_design_path=design_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_row_domain_count_witness_payload_v1"
    )
    assert report["status"]["payload_ready"] is True
    assert report["status"]["anchored_bridge_ready"] is False
    assert report["status"]["recommended_next_step"] == "extract_anchor119_row_domain_bridge"
    assert report["deterministic_payload"]["payload_id"] == (
        "anchor119_three_label_overlap_above_strip_count_guard_v0"
    )
    assert report["deterministic_payload"]["total_row_count"] == 640
    assert [row["slot_index"] for row in report["deterministic_payload"]["rows"]] == [
        8,
        10,
        0,
    ]
    assert report["count_boundaries"]["non_trigger_max_slot_count"] == 13
    assert report["count_boundaries"]["anchored_trigger_min_slot_count"] == 14
    assert report["count_boundaries"]["free_ghost_trigger_min_slot_count"] == 15
    markdown = render_phase3b_coordinate_validation_row_domain_count_witness_payload_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_row_domain_count_witness_payload_text(
        report
    )
    assert "Row-Domain Count Witness Payload" in markdown
    assert "recommended_next_step=extract_anchor119_row_domain_bridge" in text


def test_row_domain_count_witness_payload_fails_without_shared_lower_bound(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    design_path = project_root / "design.json"
    _write_json(design_path, _design_payload(shared_lower_bound=None))

    report = build_phase3b_coordinate_validation_row_domain_count_witness_payload(
        project_root,
        row_domain_count_witness_design_path=design_path,
    )

    assert report["status"]["payload_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "shared_safe_strip_lower_bound_present" in failed


def test_row_domain_count_witness_payload_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    design_path = project_root / "design.json"
    output_dir = tmp_path / "out"
    _write_json(design_path, _design_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_row_domain_count_witness_payload.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--row-domain-count-witness-design",
            str(design_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate-validation row-domain count witness payload" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--row-domain-count-witness-design",
            str(design_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "row_domain_count_witness_payload_json=" in write.stdout
    payload = json.loads(
        (output_dir / "row_domain_count_witness_payload.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["payload_ready"] is True
    assert (output_dir / "row_domain_count_witness_payload.md").exists()
    assert (output_dir / "row_domain_count_witness_payload.txt").exists()
