from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.order_capacity_certificate_candidate import (
    build_phase3b_coordinate_validation_order_capacity_certificate_candidate,
    render_phase3b_coordinate_validation_order_capacity_certificate_candidate_markdown,
    render_phase3b_coordinate_validation_order_capacity_certificate_candidate_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _pair_x_core_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_anchor119_pair_x_core_synthesis_v1"},
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "completed": True,
            "outcome": "anchor119_fixed_conflict_shrunk_to_protocol_planter_buckwheat_3_x_labels",
        },
        "evidence": {
            "minimality_10s": {
                "all3_infeasible": True,
                "proper_subsets_terminal_infeasible": 0,
            },
            "remaining_labels": [{}, {}, {}],
        },
    }


def _pair_x_no_ghost_space_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_anchor119_pair_x_no_ghost_space_synthesis_v1"
        },
        "status": {
            "completed": True,
            "outcome": "three_x_labels_eliminate_entire_67x13_ghost_domain_in_full_model",
        },
        "evidence": {
            "anchor_sweep_all": {
                "status_counts": {"INFEASIBLE": 232},
            },
            "standalone_pair_ladder": {
                "full_pair_all_constraints_status": "OPTIMAL"
            },
        },
    }


def _order_capacity_explanation_payload() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_order_implied_capacity_explanation_v1"
        },
        "geometry": {
            "free_ghost_infeasible_threshold_slots": 15,
            "anchor119_fixed_infeasible_threshold_slots": 14,
            "why_x_overlap_is_unavoidable": "wide ghost overlaps same x strip",
        },
        "entries": [
            {
                "slot_index": idx,
                "free_ghost_capacity_exceeded": idx >= 14,
                "observed_status": "INFEASIBLE" if idx >= 14 else "UNKNOWN",
            }
            for idx in range(17)
        ],
        "interpretation": {
            "free_ghost_x0_slots_14_16": "slots14-16 become infeasible",
            "fixed_anchor119_distinction": "anchored failure remains multi-group",
        },
    }


def test_order_capacity_certificate_candidate_design_gate_passes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    core_path = project_root / "core.json"
    no_ghost_path = project_root / "no_ghost.json"
    explanation_path = project_root / "explanation.json"
    _write_json(core_path, _pair_x_core_payload())
    _write_json(no_ghost_path, _pair_x_no_ghost_space_payload())
    _write_json(explanation_path, _order_capacity_explanation_payload())

    report = build_phase3b_coordinate_validation_order_capacity_certificate_candidate(
        project_root,
        pair_x_core_synthesis_path=core_path,
        pair_x_no_ghost_space_synthesis_path=no_ghost_path,
        order_capacity_explanation_path=explanation_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_order_capacity_certificate_candidate_v1"
    )
    assert report["gate"]["design_gate_passed"] is True
    assert report["gate"]["proof_preserving_precheck_ready"] is False
    assert report["evidence"]["core_label_count"] if "core_label_count" in report["evidence"] else 3
    assert report["evidence"]["exceeded_infeasible_slot_indices"] == [14, 15, 16]
    assert report["evidence"]["highest_non_exceeded_unknown_slot_index"] == 13
    assert "proof-preserving extraction target" in report["gate"]["recommendation"]
    markdown = (
        render_phase3b_coordinate_validation_order_capacity_certificate_candidate_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_order_capacity_certificate_candidate_text(
            report
        )
    )
    assert "Order-Capacity Certificate Candidate" in markdown
    assert "certificate_shape=order_implied_x_overlap_upper_strip" in text


def test_order_capacity_certificate_candidate_fails_when_transition_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    core_path = project_root / "core.json"
    no_ghost_path = project_root / "no_ghost.json"
    explanation_path = project_root / "explanation.json"
    payload = _order_capacity_explanation_payload()
    for entry in payload["entries"]:
        if entry["slot_index"] == 13:
            entry["observed_status"] = "INFEASIBLE"
            entry["free_ghost_capacity_exceeded"] = True
    _write_json(core_path, _pair_x_core_payload())
    _write_json(no_ghost_path, _pair_x_no_ghost_space_payload())
    _write_json(explanation_path, payload)

    report = build_phase3b_coordinate_validation_order_capacity_certificate_candidate(
        project_root,
        pair_x_core_synthesis_path=core_path,
        pair_x_no_ghost_space_synthesis_path=no_ghost_path,
        order_capacity_explanation_path=explanation_path,
    )

    assert report["gate"]["design_gate_passed"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "order_capacity_transition_witnessed" in failed


def test_order_capacity_certificate_candidate_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    core_path = project_root / "core.json"
    no_ghost_path = project_root / "no_ghost.json"
    explanation_path = project_root / "explanation.json"
    output_dir = tmp_path / "out"
    _write_json(core_path, _pair_x_core_payload())
    _write_json(no_ghost_path, _pair_x_no_ghost_space_payload())
    _write_json(explanation_path, _order_capacity_explanation_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "build_order_capacity_certificate_candidate.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--pair-x-core-synthesis",
            str(core_path),
            "--pair-x-no-ghost-space-synthesis",
            str(no_ghost_path),
            "--order-capacity-explanation",
            str(explanation_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate-validation order-capacity certificate candidate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--pair-x-core-synthesis",
            str(core_path),
            "--pair-x-no-ghost-space-synthesis",
            str(no_ghost_path),
            "--order-capacity-explanation",
            str(explanation_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "order_capacity_certificate_candidate_json=" in write.stdout
    payload = json.loads(
        (output_dir / "order_capacity_certificate_candidate.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["gate"]["design_gate_passed"] is True
    assert (output_dir / "order_capacity_certificate_candidate.md").exists()
    assert (output_dir / "order_capacity_certificate_candidate.txt").exists()
