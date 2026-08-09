from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import src.search.phase3b.forced_anchor.presolve_profile_probe as probe_module
from src.search.phase3b.forced_anchor.presolve_profile_probe import (
    build_phase3b_forced_anchor_presolve_profile_probe,
    render_phase3b_forced_anchor_presolve_profile_probe_markdown,
    render_phase3b_forced_anchor_presolve_profile_probe_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def test_forced_anchor_presolve_profile_probe_reports_missing_campaign(
    tmp_path: Path,
) -> None:
    report = build_phase3b_forced_anchor_presolve_profile_probe(tmp_path / "project")

    assert report["metadata"]["source"] == (
        "phase3b_forced_anchor_presolve_profile_probe_v1"
    )
    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_forced_anchor_presolve_profile_probe_builds_overlay_once_and_aggregates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    build_calls: list[dict[str, Any]] = []
    solve_calls: list[str] = []

    class FakeModel:
        u_vars = {119: _FakeVar(1000)}

    def fake_build(*args: Any, **kwargs: Any) -> tuple[FakeModel, object]:
        build_calls.append({"args": args, "kwargs": kwargs})
        return FakeModel(), object()

    def fake_solve(base_proto: object, **kwargs: Any) -> dict[str, Any]:
        profile = dict(kwargs["solver_parameter_profile"])
        profile_id = str(profile["profile_id"])
        solve_calls.append(profile_id)
        branches = 12 if profile.get("cp_model_presolve") is False else 0
        return {
            "anchor_idx": kwargs["anchor_idx"],
            "u_var_index": kwargs["u_var_index"],
            "variant": kwargs["variant"],
            "evaluated": True,
            "status": "UNKNOWN",
            "wall_time": 0.2,
            "branches": branches,
            "conflicts": 0,
            "search_branching": profile["search_branching"],
            "solver_worker_count": profile["worker_count"],
            "solver_parameter_profile": profile,
            "response_stats_parsed": {"deterministic_time": 0.01},
        }

    monkeypatch.setattr(probe_module, "_build_exact_overlay", fake_build)
    monkeypatch.setattr(probe_module, "_clone_model_proto", lambda proto: proto)
    monkeypatch.setattr(probe_module, "_solve_slice_clone", fake_solve)

    report = build_phase3b_forced_anchor_presolve_profile_probe(
        project_root,
        candidate="67x13",
        anchor_indices=[119],
        profiles=[
            {
                "profile_id": "on",
                "search_branching": "fixed",
                "cp_model_probing_level": 0,
                "symmetry_level": 0,
                "worker_count": 1,
                "cp_model_presolve": True,
            },
            {
                "profile_id": "off",
                "search_branching": "fixed",
                "cp_model_probing_level": 0,
                "symmetry_level": 0,
                "worker_count": 1,
                "cp_model_presolve": False,
            },
        ],
    )

    assert len(build_calls) == 1
    assert solve_calls == ["on", "off"]
    assert report["overlay_built_once"] is True
    assert report["status"]["outcome"] == "presolve_profile_progress_without_terminal"
    assert report["probe"]["unknown_diagnostics"]["zero_branch_unknown_count"] == 1
    assert report["probe"]["unknown_diagnostics"]["search_progress_unknown_count"] == 1
    assert report["campaign_state_unchanged"] is True

    markdown = render_phase3b_forced_anchor_presolve_profile_probe_markdown(report)
    text = render_phase3b_forced_anchor_presolve_profile_probe_text(report)
    assert "Presolve Profile Probe" in markdown
    assert "profile=off" in text


def test_forced_anchor_presolve_profile_probe_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "forced_anchor" / "build_presolve_profile_probe.py"

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

    assert "phase3b forced-anchor presolve profile probe" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--profiles-json",
            json.dumps(
                [
                    {
                        "profile_id": "p0",
                        "search_branching": "fixed",
                        "cp_model_probing_level": 0,
                        "symmetry_level": 0,
                        "worker_count": 1,
                        "cp_model_presolve": False,
                    }
                ]
            ),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "forced_anchor_presolve_profile_probe_json=" in write.stdout
    payload = json.loads(
        (output_dir / "forced_anchor_presolve_profile_probe.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == (
        "phase3b_forced_anchor_presolve_profile_probe_v1"
    )
    assert (output_dir / "forced_anchor_presolve_profile_probe.md").exists()
    assert (output_dir / "forced_anchor_presolve_profile_probe.txt").exists()


def _check_status(report: Mapping[str, Any], check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
