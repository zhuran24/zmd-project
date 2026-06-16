from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.start.compatibility import (
    build_phase3b_start_compatibility_diagnostics,
    render_phase3b_start_compatibility_markdown,
    render_phase3b_start_compatibility_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_toy_exact_project(project_root: Path) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 2, "height": 1}},
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
            },
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                ]
            }
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "operation_type": "tiny",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def test_start_compatibility_diagnostics_builds_candidate_report(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "project")

    diagnostics = build_phase3b_start_compatibility_diagnostics(
        project_root,
        candidate="1x1",
    )

    assert diagnostics["metadata"]["source"] == "phase3b_start_compatibility_diagnostics_v1"
    assert diagnostics["candidate"]["key"] == "1x1"
    assert diagnostics["candidate"]["ghost_rect"] == {"w": 1, "h": 1, "area": 1}
    assert "compatible_start_found" in diagnostics["status"]
    assert "diagnostic_portfolio_start_found" in diagnostics["status"]
    assert "diagnostic_group_packing_infeasible_found" in diagnostics["status"]
    assert "coordinate_pose_order_validation_rejected_count" in diagnostics["status"]
    assert "boundary_port_precheck" in diagnostics["diagnostics"]
    assert "warm_start" in diagnostics["diagnostics"]
    assert (
        "ghost_aware_pose_order_validation_rejected_count"
        in diagnostics["diagnostics"]["warm_start"]
    )
    assert diagnostics["diagnostics"]["portfolio_probe"]["enabled"] is False
    assert diagnostics["diagnostics"]["group_packing_probe"]["enabled"] is False
    assert diagnostics["profile"]["precheck_caps"]["failed_anchor_sample_limit"] == 8

    markdown = render_phase3b_start_compatibility_markdown(diagnostics)
    text = render_phase3b_start_compatibility_text(diagnostics)
    assert "Phase 3B Start Compatibility Diagnostics" in markdown
    assert "candidate=1x1" in text
    assert "coordinate_pose_order_validation_rejected_count=0" in text


def test_start_compatibility_cli_no_write_and_default_write(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "project")
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "start" / "build_compatibility.py"
    output_dir = tmp_path / "out"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--candidate",
            "1x1",
            "--output-dir",
            str(output_dir),
            "--no-write",
            "--portfolio-probe-sample-limit",
            "0",
            "--group-packing-probe-sample-limit",
            "0",
            "--failed-anchor-sample-limit",
            "16",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b start compatibility diagnostics" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--candidate",
            "1x1",
            "--output-dir",
            str(output_dir),
            "--portfolio-probe-sample-limit",
            "0",
            "--group-packing-probe-sample-limit",
            "0",
            "--failed-anchor-sample-limit",
            "16",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "start_compatibility_json=" in write.stdout
    payload = json.loads((output_dir / "start_compatibility_1x1.json").read_text(encoding="utf-8"))
    assert payload["candidate"]["key"] == "1x1"
    assert payload["profile"]["precheck_caps"]["failed_anchor_sample_limit"] == 16
    assert (output_dir / "start_compatibility_1x1.md").exists()
    assert (output_dir / "start_compatibility_1x1.txt").exists()


def test_start_failure_summary_renders_group_reason_details() -> None:
    diagnostics = {
        "candidate": {"key": "69x19"},
        "status": {
            "compatible_start_found": False,
            "diagnostic_portfolio_start_found": True,
            "outcome": "start_incompatible",
            "recommendation": "Return to B2/B3 targeted shrink.",
        },
        "diagnostics": {
            "start_failure_summary": {
                "failed_anchor_count": 51,
                "failure_reason_counts": {
                    "committed_cells_exhausted": 29,
                    "intra_group_greedy_exhausted": 22,
                },
                "first_failed_group": {
                    "group_id": "group::manufacturing_3x3::refinery_steel::8",
                    "facility_type": "manufacturing_3x3",
                    "position": 18,
                    "required_count": 17,
                    "candidate_count": 17952,
                    "surviving_after_blocked_count": 12728,
                    "surviving_at_failure_count": 14,
                },
                "top_failed_group_failures": [
                    {
                        "group_id": "group::manufacturing_3x3::refinery_steel::8",
                        "facility_type": "manufacturing_3x3",
                        "failure_reason": "committed_cells_exhausted",
                        "count": 29,
                    }
                ],
                "failed_anchor_samples": [
                    {
                        "anchor_idx": 12,
                        "failure_reason": "committed_cells_exhausted",
                        "first_failed_group_id": "group::manufacturing_3x3::refinery_steel::8",
                        "first_failed_group_template": "manufacturing_3x3",
                        "first_failed_group_position": 18,
                        "first_failed_group_required_count": 17,
                        "first_failed_group_candidate_count": 17952,
                        "first_failed_group_surviving_after_blocked_count": 12728,
                        "first_failed_group_surviving_at_failure_count": 14,
                        "blocked_cell_count": 1311,
                        "blocked_bbox": {
                            "min_x": 1,
                            "min_y": 0,
                            "max_x": 69,
                            "max_y": 18,
                        },
                        "local_repair_attempted": True,
                        "local_repair_success": False,
                        "local_repair_attempt_count": 2,
                    }
                ],
            }
        },
    }
    diagnostics["diagnostics"]["portfolio_probe"] = {
        "enabled": True,
        "sample_count": 1,
        "success_count": 1,
        "success_found": True,
        "samples": [
            {
                "anchor_idx": 12,
                "success": True,
                "attempt_count": 7,
                "window_size": 3,
                "group_order": "reverse_group_order",
                "pose_orderings": ["overlap_degree_asc", "canonical", "canonical"],
            }
        ],
    }
    diagnostics["diagnostics"]["warm_start"] = {
        "ghost_aware_pose_order_validation_rejection_samples": [
            {
                "anchor_idx": 118,
                "ordering": "y_then_x",
                "status": "INFEASIBLE",
                "reason": "infeasible",
                "forced_slot_field_count": 798,
                "branches": 0,
                "conflicts": 0,
            }
        ],
        "ghost_aware_pose_order_portfolio_failure_samples": [
            {
                "anchor_idx": 130,
                "ordering": "y_then_x",
                "source": "coordinate_validation",
                "failure_reason": "coordinate_validation_unknown",
                "status": "UNKNOWN",
            }
        ],
    }
    diagnostics["diagnostics"]["group_packing_probe"] = {
        "enabled": True,
        "sample_count": 1,
        "feasible_count": 1,
        "infeasible_count": 0,
        "unknown_count": 0,
        "skipped_count": 0,
        "feasible_found": True,
        "samples": [
            {
                "anchor_idx": 12,
                "group_id": "group::manufacturing_3x3::refinery_steel::8",
                "facility_type": "manufacturing_3x3",
                "required_count": 17,
                "surviving_at_failure_count": 654,
                "greedy_selected_count": 12,
                "exact_feasible": True,
                "solver_status": "FEASIBLE",
            }
        ],
    }
    diagnostics["diagnostics"]["group_packing_blockers"] = {
        "enabled": True,
        "blocker_count": 1,
        "sample_count": 1,
        "precheck_design_candidate": True,
        "recommendation": "Use sampled exact-infeasible group packing evidence.",
        "blockers": [
            {
                "group_id": "group::manufacturing_3x3::refinery_steel::8",
                "facility_type": "manufacturing_3x3",
                "solver_status": "INFEASIBLE",
                "sample_count": 1,
                "anchor_indices": [12],
                "required_count_min": 17,
                "required_count_max": 17,
                "surviving_at_failure_min": 654,
                "surviving_at_failure_max": 654,
                "greedy_selected_min": 12,
                "greedy_selected_max": 12,
                "evidence_strength": "sampled_exact_infeasible",
            }
        ],
    }

    markdown = render_phase3b_start_compatibility_markdown(diagnostics)
    text = render_phase3b_start_compatibility_text(diagnostics)

    assert "refinery_steel" in markdown
    assert "committed_cells_exhausted" in markdown
    assert "Failed Anchor Samples" in markdown
    assert "Portfolio Probe" in markdown
    assert "Group Packing Probe" in markdown
    assert "Diagnostic Group Packing Blockers" in markdown
    assert "Pose-Order Validation Rejections" in markdown
    assert "Pose-Order Portfolio Failure Samples" in markdown
    assert "reverse_group_order" in markdown
    assert "FEASIBLE" in markdown
    assert "failed_anchor_count=51" in text
    assert "top_failed_group_failure=group::manufacturing_3x3::refinery_steel::8" in text
    assert "failed_anchor_sample=anchor=12" in text
    assert "portfolio_probe=success_found=True" in text
    assert "pose_order_validation_rejection_sample=anchor=118" in text
    assert "pose_order_portfolio_failure_sample=anchor=130" in text
    assert "group_packing_probe=feasible_found=True" in text
    assert "group_packing_blockers=count=1" in text


def test_portfolio_probe_status_recommendation() -> None:
    from src.search.phase3b.start.compatibility import _status_from_warm_start

    status = _status_from_warm_start(
        {"ghost_anchor_compatible_count": 0},
        {"failed_anchor_count": 1},
        {"enabled": True, "success_found": True},
        {"enabled": False},
    )

    assert status["compatible_start_found"] is False
    assert status["diagnostic_portfolio_start_found"] is True
    assert status["outcome"] == "diagnostic_portfolio_start_found"
    assert "runtime patch" in status["recommendation"]


def test_group_packing_status_recommendation() -> None:
    from src.search.phase3b.start.compatibility import _status_from_warm_start

    status = _status_from_warm_start(
        {"ghost_anchor_compatible_count": 0},
        {"failed_anchor_count": 1},
        {"enabled": True, "success_found": False},
        {"enabled": True, "feasible_found": True},
        {"enabled": True, "precheck_design_candidate": False},
    )

    assert status["diagnostic_portfolio_start_found"] is False
    assert status["diagnostic_group_packing_feasible"] is True
    assert status["outcome"] == "diagnostic_group_packing_feasible"
    assert "greedy/order repair" in status["recommendation"]


def test_group_packing_infeasible_status_and_blocker_summary() -> None:
    from src.search.phase3b.start.compatibility import (
        _build_group_packing_blockers,
        _status_from_warm_start,
    )

    probe = {
        "enabled": True,
        "sample_count": 2,
        "feasible_count": 0,
        "infeasible_count": 2,
        "unknown_count": 0,
        "skipped_count": 0,
        "samples": [
            {
                "anchor_idx": 53,
                "group_id": "group_a",
                "facility_type": "manufacturing_3x3",
                "required_count": 17,
                "surviving_at_failure_count": 14,
                "greedy_selected_count": 3,
                "exact_feasible": False,
                "solver_status": "CANDIDATE_COUNT_BELOW_REQUIRED",
                "skipped": False,
            },
            {
                "anchor_idx": 54,
                "group_id": "group_a",
                "facility_type": "manufacturing_3x3",
                "required_count": 17,
                "surviving_at_failure_count": 14,
                "greedy_selected_count": 3,
                "exact_feasible": False,
                "solver_status": "CANDIDATE_COUNT_BELOW_REQUIRED",
                "skipped": False,
            },
        ],
    }

    blockers = _build_group_packing_blockers(probe)
    status = _status_from_warm_start(
        {"ghost_anchor_compatible_count": 0},
        {"failed_anchor_count": 2},
        {"enabled": True, "success_found": False},
        probe,
        blockers,
    )

    assert blockers["precheck_design_candidate"] is True
    assert blockers["blockers"][0]["anchor_indices"] == [53, 54]
    assert blockers["blockers"][0]["sample_count"] == 2
    assert status["diagnostic_group_packing_infeasible_found"] is True
    assert status["diagnostic_group_packing_precheck_design_candidate"] is True
    assert status["outcome"] == "diagnostic_group_packing_infeasible"
    assert "precheck design input" in status["recommendation"]


def test_coordinate_validation_rejected_start_is_incompatible_status() -> None:
    from src.search.phase3b.start.compatibility import _status_from_warm_start

    status = _status_from_warm_start(
        {
            "ghost_anchor_compatible_count": 0,
            "ghost_anchor_hint_status": "none_compatible",
            "ghost_anchor_compatibility_skipped": False,
            "ghost_aware_coordinate_validation_rejected_count": 8,
            "ghost_aware_coordinate_validation_last_status": "INFEASIBLE",
            "ghost_aware_coordinate_validation_last_reason": "infeasible",
            "ghost_aware_coordinate_validation_limit_reached": True,
        },
        {
            "failed_anchor_count": 8,
            "failure_reason_counts": {
                "coordinate_validation_infeasible": 8,
                "coordinate_validation_attempt_limit_reached": 1,
            },
        },
        {"enabled": False, "success_found": False},
        {"enabled": False, "feasible_found": False},
        {"enabled": False, "blocker_count": 0},
    )

    assert status["compatible_start_found"] is False
    assert status["compatibility_skipped"] is False
    assert status["outcome"] == "start_incompatible"
    assert "targeted shrink" in status["recommendation"]
