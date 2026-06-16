from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.runtime_group.packing as runtime_gp_module
from src.search.phase3b.runtime_group.packing import (
    build_phase3b_runtime_group_packing_diagnostic,
    render_phase3b_runtime_group_packing_markdown,
    render_phase3b_runtime_group_packing_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "solve_mode": "certified_exact",
        "campaign_hours": 1.0,
        "created_at": "2026-04-17T00:00:00Z",
        "updated_at": "2026-04-17T00:00:00Z",
        "artifact_hashes": {},
        "proof_summary_schema_version": 1,
        "reset_reason": None,
        "final_result": None,
        "final_status": "UNKNOWN",
        "last_stop_reason": {"reason": "candidate_returned_unknown"},
        "candidates": {
            "69x19": {
                "ghost_rect": {"w": 69, "h": 19, "area": 1311},
                "attempts": 1,
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_status": "UNKNOWN",
                    "master_start_feasibility": {
                        "ghost_anchor_compatible_count": 0,
                        "ghost_anchor_hint_status": "none_compatible",
                    },
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 2,
                        "failure_reason_counts": {"committed_cells_exhausted": 2},
                        "first_failed_group_id": "group_a",
                        "first_failed_group_template": "manufacturing_3x3",
                        "failed_anchor_samples": [
                            {
                                "anchor_idx": 53,
                                "failure_reason": "committed_cells_exhausted",
                                "first_failed_group_id": "group_a",
                                "first_failed_group_template": "manufacturing_3x3",
                                "first_failed_group_position": 10,
                                "first_failed_group_required_count": 17,
                                "first_failed_group_candidate_count": 100,
                                "first_failed_group_surviving_after_blocked_count": 50,
                                "first_failed_group_surviving_at_failure_count": 14,
                            },
                            {
                                "anchor_idx": 54,
                                "failure_reason": "committed_cells_exhausted",
                                "first_failed_group_id": "group_a",
                                "first_failed_group_template": "manufacturing_3x3",
                                "first_failed_group_position": 10,
                                "first_failed_group_required_count": 17,
                                "first_failed_group_candidate_count": 100,
                                "first_failed_group_surviving_after_blocked_count": 50,
                                "first_failed_group_surviving_at_failure_count": 14,
                            },
                        ],
                    },
                },
                "exact_safe_cuts": [],
                "loaded_exact_safe_cut_count": 0,
                "generated_exact_safe_cut_count": 0,
            }
        },
    }


def test_runtime_group_packing_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_runtime_group_packing_diagnostic(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "campaign_state_present" in failed
    assert "candidate_present" in failed


def test_runtime_group_packing_diagnostic_does_not_mutate_campaign(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")

    monkeypatch.setattr(
        runtime_gp_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        runtime_gp_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: object()),
    )
    monkeypatch.setattr(
        runtime_gp_module,
        "_build_group_packing_probe",
        lambda *args, **kwargs: {
            "enabled": True,
            "sample_limit": 2,
            "time_limit_seconds": 0.5,
            "max_candidates": 2500,
            "sample_count": 2,
            "feasible_count": 0,
            "infeasible_count": 2,
            "unknown_count": 0,
            "skipped_count": 0,
            "feasible_found": False,
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
        },
    )

    report = build_phase3b_runtime_group_packing_diagnostic(
        project_root,
        candidate="69x19",
        sample_limit=2,
    )

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["status"]["evaluated"] is True
    assert report["status"]["outcome"] == "diagnostic_group_packing_infeasible"
    assert report["diagnostics"]["group_packing_blockers"]["blocker_count"] == 1
    assert report["checks"][-2]["status"] == "pass"
    markdown = render_phase3b_runtime_group_packing_markdown(report)
    text = render_phase3b_runtime_group_packing_text(report)
    assert "group_a" in markdown
    assert "outcome=diagnostic_group_packing_infeasible" in text


def test_runtime_group_packing_reports_missing_samples(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    payload = _campaign_state_payload()
    payload["candidates"]["69x19"]["proof_summary"]["master_start_failure_attribution"][
        "failed_anchor_samples"
    ] = []
    _write_json(
        project_root / "data" / "checkpoints" / "exact_campaign_state.json",
        payload,
    )

    report = build_phase3b_runtime_group_packing_diagnostic(project_root)

    assert report["status"]["outcome"] == "start_failure_samples_missing"
    assert report["checks"][2]["status"] == "fail"
    assert report["campaign_state_unchanged"] is True


def test_runtime_group_packing_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "runtime_group" / "build_packing.py"

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
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b runtime group-packing diagnostic" in no_write.stdout
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
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "runtime_group_packing_json=" in write.stdout
    payload = json.loads((output_dir / "runtime_group_packing_1x1.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_runtime_group_packing_diagnostic_v1"
    assert payload["status"]["outcome"] == "candidate_missing"
    assert (output_dir / "runtime_group_packing_1x1.md").exists()
    assert (output_dir / "runtime_group_packing_1x1.txt").exists()
