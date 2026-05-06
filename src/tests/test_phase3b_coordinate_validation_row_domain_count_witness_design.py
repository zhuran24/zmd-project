from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_row_domain_count_witness_design import (
    build_phase3b_coordinate_validation_row_domain_count_witness_design,
    render_phase3b_coordinate_validation_row_domain_count_witness_design_markdown,
    render_phase3b_coordinate_validation_row_domain_count_witness_design_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _candidate_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_row_domain_extraction_candidate_v1"
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "design_gate_passed": True,
            "runtime_promotion_ready": False,
            "recommended_next_step": "implement_row_domain_extraction_witness",
            "recommendation": "candidate ready",
        },
        "evidence": {
            "free_ghost_threshold": 15,
            "fixed_anchor_threshold": 14,
            "highest_non_exceeded_unknown_slot_index": 13,
            "exceeded_infeasible_slot_indices": [14, 15, 16],
            "ghost_avoiding_y_counts": [50, 50, 45],
            "planter_order_implication_count": 11,
            "implied_fixed_slots": [8, 10],
        },
    }


def _order_payload(*, below_override: int = 0) -> dict:
    return {
        "metadata": {"source": "phase3b_anchor119_pair_x_order_domain_extraction_v1"},
        "forced_labels": [
            {
                "group_id": "group::manufacturing_5x5::planter_buckwheat::9",
                "solution_id": "planter_buckwheat_009",
                "slot_index": 8,
                "template": "manufacturing_5x5",
                "forced_value": 1,
            },
            {
                "group_id": "group::manufacturing_5x5::planter_buckwheat::9",
                "solution_id": "planter_buckwheat_011",
                "slot_index": 10,
                "template": "manufacturing_5x5",
                "forced_value": 5,
            },
            {
                "group_id": "group::protocol_core::protocol_core::18",
                "solution_id": "protocol_core_001",
                "slot_index": 0,
                "template": "protocol_core",
                "forced_value": 1,
            },
        ],
        "groups": [
            {
                "group_id": "group::manufacturing_5x5::planter_buckwheat::9",
                "entries": [
                    {
                        "slot_index": 8,
                        "order_filtered_row_count": 260,
                        "x_domain": {"count": 1},
                        "y_domain": {"count": 66},
                        "anchor119_avoiding_y": {"count": 50, "min": 16, "max": 65},
                        "anchor119_below_y": {"count": below_override, "min": None, "max": None},
                        "anchor119_above_y": {"count": 50, "min": 16, "max": 65},
                    },
                    {
                        "slot_index": 10,
                        "order_filtered_row_count": 260,
                        "x_domain": {"count": 1},
                        "y_domain": {"count": 66},
                        "anchor119_avoiding_y": {"count": 50, "min": 16, "max": 65},
                        "anchor119_below_y": {"count": 0, "min": None, "max": None},
                        "anchor119_above_y": {"count": 50, "min": 16, "max": 65},
                    },
                ],
            },
            {
                "group_id": "group::protocol_core::protocol_core::18",
                "entries": [
                    {
                        "slot_index": 0,
                        "order_filtered_row_count": 120,
                        "x_domain": {"count": 1},
                        "y_domain": {"count": 60},
                        "anchor119_avoiding_y": {"count": 45, "min": 16, "max": 60},
                        "anchor119_below_y": {"count": 0, "min": None, "max": None},
                        "anchor119_above_y": {"count": 45, "min": 16, "max": 60},
                    }
                ],
            },
        ],
    }


def _synthesis_payload(*, overlap_all_anchors: bool = True) -> dict:
    return {
        "metadata": {"source": "phase3b_anchor119_pair_x_global_context_synthesis_v1"},
        "status": {
            "outcome": "mixed_lane_guarded_precheck_advisory_ready_default_off",
            "runtime_promotion_ready": False,
            "recommendation": "A default-off advisory runtime helper keeps runtime unchanged.",
        },
        "evidence": {
            "order_domain_extraction": {
                "all_forced_labels_x_overlap_all_anchors": overlap_all_anchors
            }
        },
    }


def test_row_domain_count_witness_design_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    candidate_path = project_root / "candidate.json"
    order_path = project_root / "order.json"
    synthesis_path = project_root / "synthesis.json"
    _write_json(candidate_path, _candidate_payload())
    _write_json(order_path, _order_payload())
    _write_json(synthesis_path, _synthesis_payload())

    report = build_phase3b_coordinate_validation_row_domain_count_witness_design(
        project_root,
        row_domain_extraction_candidate_path=candidate_path,
        order_domain_extraction_path=order_path,
        global_context_synthesis_path=synthesis_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_row_domain_count_witness_design_v1"
    )
    assert report["status"]["design_ready"] is True
    assert report["status"]["runtime_promotion_ready"] is False
    assert report["status"]["recommended_next_step"] == "implement_row_domain_count_witness"
    assert report["witness_design"]["shared_safe_strip_lower_bound"] == 16
    assert [row["slot_index"] for row in report["witness_design"]["row_summaries"]] == [
        8,
        10,
        0,
    ]
    assert [row["row_count"] for row in report["witness_design"]["row_summaries"]] == [
        260,
        260,
        120,
    ]
    assert report["count_witness"]["threshold_delta"] == 1
    assert "Row-domain/count witness design is ready" in report["status"]["recommendation"]
    markdown = render_phase3b_coordinate_validation_row_domain_count_witness_design_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_row_domain_count_witness_design_text(
        report
    )
    assert "Row-Domain Count Witness Design" in markdown
    assert "recommended_next_step=implement_row_domain_count_witness" in text


def test_row_domain_count_witness_design_fails_with_below_ghost_room(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    candidate_path = project_root / "candidate.json"
    order_path = project_root / "order.json"
    synthesis_path = project_root / "synthesis.json"
    _write_json(candidate_path, _candidate_payload())
    _write_json(order_path, _order_payload(below_override=1))
    _write_json(synthesis_path, _synthesis_payload())

    report = build_phase3b_coordinate_validation_row_domain_count_witness_design(
        project_root,
        row_domain_extraction_candidate_path=candidate_path,
        order_domain_extraction_path=order_path,
        global_context_synthesis_path=synthesis_path,
    )

    assert report["status"]["design_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "all_core_labels_have_no_below_ghost_room" in failed


def test_row_domain_count_witness_design_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    candidate_path = project_root / "candidate.json"
    order_path = project_root / "order.json"
    synthesis_path = project_root / "synthesis.json"
    output_dir = tmp_path / "out"
    _write_json(candidate_path, _candidate_payload())
    _write_json(order_path, _order_payload())
    _write_json(synthesis_path, _synthesis_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_row_domain_count_witness_design.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--row-domain-extraction-candidate",
            str(candidate_path),
            "--order-domain-extraction",
            str(order_path),
            "--global-context-synthesis",
            str(synthesis_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate-validation row-domain count witness design" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--row-domain-extraction-candidate",
            str(candidate_path),
            "--order-domain-extraction",
            str(order_path),
            "--global-context-synthesis",
            str(synthesis_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "row_domain_count_witness_design_json=" in write.stdout
    payload = json.loads(
        (output_dir / "row_domain_count_witness_design.json").read_text(encoding="utf-8")
    )
    assert payload["status"]["design_ready"] is True
    assert (output_dir / "row_domain_count_witness_design.md").exists()
    assert (output_dir / "row_domain_count_witness_design.txt").exists()
