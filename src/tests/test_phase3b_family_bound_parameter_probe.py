from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_family_bound_parameter_probe as probe_module
from src.search.phase3b_family_bound_parameter_probe import (
    build_phase3b_family_bound_parameter_probe,
    render_phase3b_family_bound_parameter_probe_markdown,
    render_phase3b_family_bound_parameter_probe_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "67x13": {
                "ghost_rect": {"w": 67, "h": 13, "area": 871},
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 1,
                        "failed_anchor_samples": [{"anchor_idx": 119}],
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


def _patch_probe(monkeypatch, statuses: dict[str, str]) -> None:
    fake_model = SimpleNamespace(u_vars={119: _FakeVar(777)})
    monkeypatch.setattr(
        probe_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )

    def fake_solve(base_proto, *, anchor_idx, profile, time_limit_seconds, **kwargs):
        profile_id = str(profile["profile_id"])
        status = statuses[profile_id]
        return {
            "anchor_idx": int(anchor_idx),
            "profile_id": profile_id,
            "evaluated": True,
            "status": status,
            "wall_time": 0.2 if status == "UNKNOWN" else 0.05,
            "deterministic_time": 0.1 if status == "UNKNOWN" else 0.01,
            "branches": 0 if status == "UNKNOWN" else 2,
            "conflicts": 0 if status == "UNKNOWN" else 1,
            "search_branching": profile["search_branching"],
            "cp_model_probing_level": profile["cp_model_probing_level"],
            "symmetry_level": profile["symmetry_level"],
            "worker_count": profile["worker_count"],
        }

    monkeypatch.setattr(probe_module, "_solve_parameter_profile", fake_solve)


def test_parameter_probe_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_family_bound_parameter_probe(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_parameter_probe_finds_terminal_profile(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_probe(
        monkeypatch,
        {
            "portfolio_p3_s3_w4": "UNKNOWN",
            "fixed_p3_s3_w1": "OPTIMAL",
        },
    )

    report = build_phase3b_family_bound_parameter_probe(
        project_root,
        campaign_state_path=campaign_path,
        candidate="67x13",
        anchor_indices=[119],
        profiles=[
            {
                "profile_id": "portfolio_p3_s3_w4",
                "search_branching": "portfolio",
                "cp_model_probing_level": 3,
                "symmetry_level": 3,
                "worker_count": 4,
            },
            {
                "profile_id": "fixed_p3_s3_w1",
                "search_branching": "fixed",
                "cp_model_probing_level": 3,
                "symmetry_level": 3,
                "worker_count": 1,
            },
        ],
    )

    assert report["status"]["outcome"] == "parameter_probe_terminal_found"
    assert report["probe"]["status_counts"] == {"UNKNOWN": 1, "OPTIMAL": 1}
    assert report["probe"]["best_terminal_entry"]["profile_id"] == "fixed_p3_s3_w1"

    markdown = render_phase3b_family_bound_parameter_probe_markdown(report)
    text = render_phase3b_family_bound_parameter_probe_text(report)
    assert "Family Bound Parameter Probe" in markdown
    assert "outcome=parameter_probe_terminal_found" in text


def test_parameter_probe_cli_writes_and_no_write_skips(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_family_bound_parameter_probe.py"

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

    assert "phase3b family-bound parameter probe" in no_write.stdout
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

    assert "family_bound_parameter_probe_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_bound_parameter_probe.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_family_bound_parameter_probe_v1"
    assert (output_dir / "family_bound_parameter_probe.md").exists()
    assert (output_dir / "family_bound_parameter_probe.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
