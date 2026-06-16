from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.forced_anchor.solver_matrix as matrix_module
from src.search.phase3b.forced_anchor.solver_matrix import (
    build_phase3b_forced_anchor_solver_matrix,
    render_phase3b_forced_anchor_solver_matrix_markdown,
    render_phase3b_forced_anchor_solver_matrix_text,
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
                        "failed_anchor_samples": [
                            {"anchor_idx": 55},
                            {"anchor_idx": 56},
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


def _patch_matrix(monkeypatch, statuses: dict[tuple[int, str], str]) -> None:
    anchors = {anchor for anchor, _branching in statuses}
    fake_model = SimpleNamespace(u_vars={idx: _FakeVar(idx + 1000) for idx in anchors})
    monkeypatch.setattr(
        matrix_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )

    def fake_solve(base_proto, *, anchor_idx, search_branching, **kwargs):
        status = statuses[(int(anchor_idx), str(search_branching))]
        return {
            "anchor_idx": int(anchor_idx),
            "search_branching": str(search_branching),
            "evaluated": True,
            "status": status,
            "wall_time": 0.1,
            "user_time": 0.1,
            "branches": 0 if status == "UNKNOWN" else 3,
            "conflicts": 0 if status == "UNKNOWN" else 1,
            "response_summary": "fake",
        }

    monkeypatch.setattr(matrix_module, "_solve_forced_anchor_clone", fake_solve)


def test_solver_matrix_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_forced_anchor_solver_matrix(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_solver_matrix_counts_by_branching_and_anchor(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")
    _patch_matrix(
        monkeypatch,
        {
            (55, "fixed"): "UNKNOWN",
            (55, "automatic"): "INFEASIBLE",
            (55, "portfolio"): "UNKNOWN",
        },
    )

    report = build_phase3b_forced_anchor_solver_matrix(
        project_root,
        anchor_indices=[55],
        search_branchings=["fixed", "automatic", "portfolio"],
    )

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["status"]["outcome"] == "matrix_unknown_remaining"
    assert report["matrix"]["status_counts"] == {"UNKNOWN": 2, "INFEASIBLE": 1}
    assert report["matrix"]["status_counts_by_branching"]["automatic"] == {
        "INFEASIBLE": 1
    }
    assert report["matrix"]["status_counts_by_anchor"]["55"] == {
        "UNKNOWN": 2,
        "INFEASIBLE": 1,
    }
    assert report["matrix"]["unknown_diagnostics"] == {
        "unknown_count": 2,
        "zero_branch_unknown_count": 2,
        "zero_branch_unknown_by_anchor": {"55": 2},
        "zero_branch_unknown_by_branching": {"fixed": 1, "portfolio": 1},
        "zero_branch_unknown_samples": [
            {
                "anchor_idx": 55,
                "search_branching": "fixed",
                "wall_time": 0.1,
                "branches": 0,
                "conflicts": 0,
            },
            {
                "anchor_idx": 55,
                "search_branching": "portfolio",
                "wall_time": 0.1,
                "branches": 0,
                "conflicts": 0,
            },
        ],
    }
    assert "zero-branch" in report["status"]["recommendation"]

    markdown = render_phase3b_forced_anchor_solver_matrix_markdown(report)
    text = render_phase3b_forced_anchor_solver_matrix_text(report)
    assert "Forced-Anchor Solver Matrix" in markdown
    assert "Zero-branch UNKNOWN entries: 2" in markdown
    assert "outcome=matrix_unknown_remaining" in text
    assert "zero_branch_unknown_count=2" in text


def test_solver_matrix_reports_feasible_found(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_matrix(
        monkeypatch,
        {
            (55, "fixed"): "UNKNOWN",
            (55, "portfolio"): "FEASIBLE",
        },
    )

    report = build_phase3b_forced_anchor_solver_matrix(
        project_root,
        anchor_indices=[55],
        search_branchings=["fixed", "portfolio"],
    )

    assert report["status"]["outcome"] == "matrix_feasible_found"


def test_solver_matrix_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "profile_phase3b_forced_anchor_solver_matrix.py"

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

    assert "phase3b forced-anchor solver matrix" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--search-branchings",
            "fixed,portfolio",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "forced_anchor_solver_matrix_json=" in write.stdout
    payload = json.loads(
        (output_dir / "forced_anchor_solver_matrix_69x19.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_forced_anchor_solver_matrix_v1"
    assert (output_dir / "forced_anchor_solver_matrix_69x19.md").exists()
    assert (output_dir / "forced_anchor_solver_matrix_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
