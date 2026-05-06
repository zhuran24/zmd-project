from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_forced_anchor_master as forced_module
from src.search.phase3b_forced_anchor_master import (
    build_phase3b_forced_anchor_master_profile,
    render_phase3b_forced_anchor_master_markdown,
    render_phase3b_forced_anchor_master_text,
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
                        "failed_anchor_count": 3,
                        "failed_anchor_samples": [
                            {"anchor_idx": 53},
                            {"anchor_idx": 54},
                            {"anchor_idx": 55},
                        ],
                    }
                },
            }
        },
    }


class _FakeVar:
    def __init__(self, index: int) -> None:
        self._index = int(index)

    def Index(self) -> int:
        return int(self._index)


def _patch_overlay(monkeypatch, statuses: dict[int, str]) -> None:
    fake_model = SimpleNamespace(u_vars={idx: _FakeVar(idx + 1000) for idx in statuses})
    monkeypatch.setattr(
        forced_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )

    def fake_solve(base_proto, *, u_var_index, anchor_idx, **kwargs):
        return {
            "anchor_idx": int(anchor_idx),
            "evaluated": True,
            "status": statuses[int(anchor_idx)],
            "wall_time": 0.1,
            "user_time": 0.1,
            "branches": 0,
            "conflicts": 0,
            "response_summary": "fake",
        }

    monkeypatch.setattr(forced_module, "_solve_forced_anchor_clone", fake_solve)


def test_forced_anchor_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_forced_anchor_master_profile(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_forced_anchor_reports_all_infeasible_without_mutating_campaign(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")
    _patch_overlay(monkeypatch, {53: "INFEASIBLE", 54: "INFEASIBLE"})

    report = build_phase3b_forced_anchor_master_profile(project_root, sample_limit=2)

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["status"]["outcome"] == "forced_anchor_all_infeasible"
    assert report["status"]["status_counts"] == {"INFEASIBLE": 2}

    markdown = render_phase3b_forced_anchor_master_markdown(report)
    text = render_phase3b_forced_anchor_master_text(report)
    assert "Forced-Anchor Master Profile" in markdown
    assert "outcome=forced_anchor_all_infeasible" in text


def test_forced_anchor_reports_unknown_remaining(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch, {53: "INFEASIBLE", 54: "UNKNOWN"})

    report = build_phase3b_forced_anchor_master_profile(project_root, sample_limit=2)

    assert report["status"]["outcome"] == "forced_anchor_unknown_remaining"
    assert report["status"]["status_counts"] == {"INFEASIBLE": 1, "UNKNOWN": 1}


def test_forced_anchor_can_select_explicit_anchor_indices(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch, {55: "UNKNOWN"})

    report = build_phase3b_forced_anchor_master_profile(
        project_root,
        sample_limit=1,
        anchor_indices=[55],
    )

    assert report["input_evidence"]["selected_anchor_indices"] == [55]
    assert [entry["anchor_idx"] for entry in report["forced_anchors"]] == [55]
    assert report["status"]["status_counts"] == {"UNKNOWN": 1}


def test_forced_anchor_reports_feasible_found(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch, {53: "INFEASIBLE", 54: "FEASIBLE"})

    report = build_phase3b_forced_anchor_master_profile(project_root, sample_limit=2)

    assert report["status"]["outcome"] == "forced_anchor_feasible_found"


def test_forced_anchor_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "profile_phase3b_forced_anchor_master.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--anchor-indices",
            "53,54",
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b forced-anchor master profile" in no_write.stdout
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

    assert "forced_anchor_master_json=" in write.stdout
    payload = json.loads(
        (output_dir / "forced_anchor_master_69x19.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_forced_anchor_master_profiler_v1"
    assert (output_dir / "forced_anchor_master_69x19.md").exists()
    assert (output_dir / "forced_anchor_master_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
