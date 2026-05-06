from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_start_repair_profiler as profiler_module
from src.search.phase3b_start_repair_profiler import (
    build_phase3b_start_repair_profile,
    render_phase3b_start_repair_profile_markdown,
    render_phase3b_start_repair_profile_text,
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
                "ghost_rect": {"w": 69, "h": 19, "area": 1311},
                "attempts": 1,
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 2,
                        "failure_reason_counts": {"committed_cells_exhausted": 2},
                        "failed_anchor_samples": [
                            {
                                "anchor_idx": 53,
                                "first_failed_group_position": 10,
                                "first_failed_group_id": "group_a",
                                "first_failed_group_template": "tpl",
                                "first_failed_group_required_count": 2,
                            },
                            {
                                "anchor_idx": 54,
                                "first_failed_group_position": 10,
                                "first_failed_group_id": "group_a",
                                "first_failed_group_template": "tpl",
                                "first_failed_group_required_count": 2,
                            },
                        ],
                    }
                },
            }
        },
    }


def _patch_model_and_probe(monkeypatch, probe: dict) -> None:
    monkeypatch.setattr(
        profiler_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        profiler_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: object()),
    )
    monkeypatch.setattr(
        profiler_module,
        "_build_portfolio_probe",
        lambda *args, **kwargs: probe,
    )


def test_start_repair_profiler_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_start_repair_profile(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_start_repair_profiler_does_not_mutate_campaign_and_reports_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")
    _patch_model_and_probe(
        monkeypatch,
        {
            "enabled": True,
            "sample_limit": 2,
            "max_window_size": 3,
            "max_attempts_per_sample": 64,
            "sample_count": 2,
            "success_count": 1,
            "success_found": True,
            "samples": [
                {
                    "anchor_idx": 53,
                    "success": True,
                    "attempt_count": 9,
                    "window_size": 3,
                    "group_order": "reverse_group_order",
                    "pose_orderings": ["canonical", "overlap_degree_asc"],
                },
                {
                    "anchor_idx": 54,
                    "success": False,
                    "attempt_count": 64,
                    "max_attempts_reached": True,
                },
            ],
        },
    )

    report = build_phase3b_start_repair_profile(project_root, sample_limit=2)

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["status"]["outcome"] == "start_repair_candidate_found"
    assert report["portfolio_probe"]["success_count"] == 1

    markdown = render_phase3b_start_repair_profile_markdown(report)
    text = render_phase3b_start_repair_profile_text(report)
    assert "Start-Repair Profile" in markdown
    assert "outcome=start_repair_candidate_found" in text


def test_start_repair_profiler_reports_budget_miss(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_model_and_probe(
        monkeypatch,
        {
            "enabled": True,
            "sample_limit": 2,
            "max_window_size": 3,
            "max_attempts_per_sample": 64,
            "sample_count": 2,
            "success_count": 0,
            "success_found": False,
            "samples": [
                {"anchor_idx": 53, "success": False, "max_attempts_reached": True},
                {"anchor_idx": 54, "success": False, "max_attempts_reached": False},
            ],
        },
    )

    report = build_phase3b_start_repair_profile(project_root, sample_limit=2)

    assert report["status"]["outcome"] == "start_repair_not_found_in_budget"
    assert report["status"]["max_attempts_reached_sample_count"] == 1


def test_start_repair_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "profile_phase3b_start_repair.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b start-repair profile" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "start_repair_profile_json=" in write.stdout
    payload = json.loads((output_dir / "start_repair_69x19.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_start_repair_profiler_v1"
    assert (output_dir / "start_repair_69x19.md").exists()
    assert (output_dir / "start_repair_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
