from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.failed_anchor.inventory import (
    build_phase3b_failed_anchor_inventory,
    render_phase3b_failed_anchor_inventory_markdown,
    render_phase3b_failed_anchor_inventory_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "69x19": {
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 2,
                        "failed_anchor_samples": [
                            {
                                "anchor_idx": 52,
                                "failure_reason": "coordinate_validation_infeasible",
                                "first_failed_group_id": None,
                                "first_failed_group_template": None,
                                "first_failed_group_position": None,
                                "first_failed_group_required_count": 0,
                                "first_failed_group_surviving_after_blocked_count": 0,
                                "first_failed_group_surviving_at_failure_count": 0,
                            },
                            {
                                "anchor_idx": 53,
                                "failure_reason": "committed_cells_exhausted",
                                "first_failed_group_id": "group_steel",
                                "first_failed_group_template": "manufacturing_3x3",
                                "first_failed_group_position": 18,
                                "first_failed_group_required_count": 17,
                                "first_failed_group_surviving_after_blocked_count": 100,
                                "first_failed_group_surviving_at_failure_count": 14,
                            },
                            {
                                "anchor_idx": 56,
                                "failure_reason": "intra_group_greedy_exhausted",
                                "first_failed_group_id": "group_steel",
                                "first_failed_group_template": "manufacturing_3x3",
                                "first_failed_group_position": 18,
                                "first_failed_group_required_count": 17,
                                "first_failed_group_surviving_after_blocked_count": 100,
                                "first_failed_group_surviving_at_failure_count": 68,
                            },
                        ],
                    }
                },
            }
        },
    }


def test_failed_anchor_inventory_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_failed_anchor_inventory(tmp_path / "project")

    assert report["summary"]["sample_count"] == 0
    assert _check_status(report, "campaign_state_present") == "fail"


def test_failed_anchor_inventory_classifies_samples_and_forced_status(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    forced_dir = project_root / "forced"
    matrix_dir = project_root / "matrix"
    _write_json(campaign_path, _campaign_state_payload())
    _write_json(
        forced_dir / "forced.json",
        {
            "forced_anchors": [
                {"anchor_idx": 52, "status": "INFEASIBLE", "wall_time": 1.5},
                {"anchor_idx": 53, "status": "INFEASIBLE", "wall_time": 1.0},
            ]
        },
    )
    _write_json(
        matrix_dir / "matrix.json",
        {
            "matrix": {
                "entries": [
                    {
                        "anchor_idx": 56,
                        "search_branching": "portfolio",
                        "status": "UNKNOWN",
                        "wall_time": 20.0,
                    }
                ]
            }
        },
    )

    report = build_phase3b_failed_anchor_inventory(
        project_root,
        campaign_state_path=campaign_path,
        forced_anchor_dir=forced_dir,
        solver_matrix_dir=matrix_dir,
    )

    assert report["summary"]["classification_counts"] == {
        "coordinate_validation_rejected": 1,
        "prefix_count_below_required": 1,
        "prefix_packing_or_greedy_hard": 1,
    }
    assert report["summary"]["forced_status_counts"] == {
        "INFEASIBLE": 2,
        "UNKNOWN": 1,
    }
    assert report["summary"]["forced_zero_branch_unknown_count"] == 1
    assert report["samples"][0]["forced_anchor_evidence"]["status_counts"] == {
        "INFEASIBLE": 1
    }
    assert report["samples"][2]["forced_anchor_evidence"][
        "zero_branch_unknown_count"
    ] == 1
    assert report["samples"][2]["forced_anchor_evidence"]["status_counts"] == {
        "UNKNOWN": 1
    }
    assert "zero-branch UNKNOWN entries" in report["summary"]["recommendation"]

    markdown = render_phase3b_failed_anchor_inventory_markdown(report)
    text = render_phase3b_failed_anchor_inventory_text(report)
    assert "Failed-Anchor Inventory" in markdown
    assert "Forced zero-branch UNKNOWN count: 1" in markdown
    assert "coordinate_validation_rejected" in text
    assert "forced_zero_branch_unknown_count=1" in text
    assert "prefix_packing_or_greedy_hard" in text


def test_failed_anchor_inventory_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    output_dir = tmp_path / "out"
    _write_json(campaign_path, _campaign_state_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "failed_anchor" / "build_inventory.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b failed-anchor inventory" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "failed_anchor_inventory_json=" in write.stdout
    payload = json.loads((output_dir / "failed_anchor_inventory.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_failed_anchor_inventory_v1"
    assert (output_dir / "failed_anchor_inventory.md").exists()
    assert (output_dir / "failed_anchor_inventory.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
