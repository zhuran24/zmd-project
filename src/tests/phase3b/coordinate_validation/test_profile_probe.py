from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import src.search.phase3b.coordinate_validation.profile_probe as probe_module
from src.search.phase3b.coordinate_validation.profile_probe import (
    build_phase3b_coordinate_validation_profile_probe,
    render_phase3b_coordinate_validation_profile_probe_markdown,
    render_phase3b_coordinate_validation_profile_probe_text,
)


class _FakeModel:
    def __init__(self, statuses: dict[str, dict[str, Any]], *, greedy_complete: bool = True) -> None:
        self.statuses = statuses
        self.greedy_complete = bool(greedy_complete)
        self.validation_calls: list[dict[str, Any]] = []

    def _run_mandatory_greedy_pass(self, **kwargs: Any) -> dict[str, Any]:
        if not self.greedy_complete:
            return {
                "complete": False,
                "reason": "forced_test_incomplete",
                "hinted_instances": 0,
                "hinted_groups": 0,
                "solution_hint": {},
            }
        return {
            "complete": True,
            "reason": "forced_test_complete",
            "hinted_instances": 1,
            "hinted_groups": 1,
            "solution_hint": {"miner_001": 7},
        }

    def _validate_coordinate_forced_hint(self, **kwargs: Any) -> dict[str, Any]:
        profile = dict(kwargs["solver_parameter_profile"])
        self.validation_calls.append(
            {
                "anchor": kwargs["ghost_anchor_hint_idx"],
                "time_limit_seconds": kwargs["time_limit_seconds"],
                "profile": profile,
                "solution_hint": dict(kwargs["solution_hint"]),
            }
        )
        payload = dict(self.statuses[str(profile["profile_id"])])
        payload.setdefault("attempted", True)
        payload.setdefault("accepted", False)
        payload.setdefault("reason", str(payload.get("status", "UNKNOWN")).lower())
        payload.setdefault("wall_time", 0.25)
        payload.setdefault("user_time", 0.2)
        payload.setdefault("deterministic_time", 0.01)
        payload.setdefault("conflicts", 0)
        payload.setdefault("binary_propagations", 0)
        payload.setdefault("integer_propagations", 0)
        payload.setdefault("missing_hint_count", 0)
        payload.setdefault("missing_pose_tuple_count", 0)
        payload.setdefault("forced_slot_field_count", 3)
        payload.setdefault("forced_ghost_anchor", True)
        payload.setdefault("require_complete", True)
        payload["solver_parameters"] = {
            "profile_id": profile["profile_id"],
            "max_time_in_seconds": kwargs["time_limit_seconds"],
            "num_search_workers": profile.get("worker_count", 1),
            "cp_model_presolve": profile.get("cp_model_presolve", True),
        }
        return payload


def test_coordinate_validation_profile_probe_aggregates_zero_and_progress_unknown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel(
        {
            "zero": {"status": "UNKNOWN", "branches": 0},
            "progress": {"status": "UNKNOWN", "branches": 19},
        }
    )

    monkeypatch.setattr(
        probe_module,
        "_build_coordinate_validation_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": ["group"],
            "candidates_by_group": {"group": [7]},
            "blocked_cells": {(1, 2)},
            "ghost_anchor_count": 120,
            "blocked_cell_count": 871,
            "ordered_group_count": 1,
        },
    )
    monkeypatch.setattr(
        probe_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_profile_probe(
        tmp_path / "project",
        candidate="67x13",
        anchor_idx=119,
        profiles=[
            {
                "profile_id": "zero",
                "time_limit_seconds": 2,
                "worker_count": 1,
                "cp_model_presolve": True,
            },
            {
                "profile_id": "progress",
                "time_limit_seconds": 30,
                "worker_count": 1,
                "cp_model_presolve": False,
            },
        ],
    )

    assert report["metadata"]["source"] == "phase3b_coordinate_validation_profile_probe_v1"
    assert report["status"]["outcome"] == "coordinate_validation_progress_without_terminal"
    assert report["probe"]["status_counts"] == {"UNKNOWN": 2}
    assert report["probe"]["unknown_diagnostics"]["zero_branch_unknown_count"] == 1
    assert report["probe"]["unknown_diagnostics"]["search_progress_unknown_count"] == 1
    assert [call["profile"]["profile_id"] for call in fake_model.validation_calls] == [
        "zero",
        "progress",
    ]
    assert fake_model.validation_calls[0]["anchor"] == 119
    assert fake_model.validation_calls[0]["solution_hint"] == {"miner_001": 7}

    markdown = render_phase3b_coordinate_validation_profile_probe_markdown(report)
    text = render_phase3b_coordinate_validation_profile_probe_text(report)
    assert "Coordinate Validation Profile Probe" in markdown
    assert "profile=progress" in text
    assert "deterministic=" in text


def test_coordinate_validation_profile_probe_reports_terminal_infeasible(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel({"terminal": {"status": "INFEASIBLE", "branches": 0}})
    monkeypatch.setattr(
        probe_module,
        "_build_coordinate_validation_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": [],
            "candidates_by_group": {},
            "blocked_cells": set(),
            "ghost_anchor_count": 1,
            "blocked_cell_count": 1,
            "ordered_group_count": 0,
        },
    )

    report = build_phase3b_coordinate_validation_profile_probe(
        tmp_path / "project",
        profiles=[{"profile_id": "terminal", "time_limit_seconds": 5}],
    )

    assert report["status"]["outcome"] == "coordinate_validation_infeasible"
    assert report["probe"]["best_terminal_entry"]["status"] == "INFEASIBLE"


def test_coordinate_validation_profile_probe_marks_skipped_when_greedy_incomplete(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake_model = _FakeModel({}, greedy_complete=False)
    monkeypatch.setattr(
        probe_module,
        "_build_coordinate_validation_context",
        lambda *args, **kwargs: {
            "model": fake_model,
            "ordered_groups": [],
            "candidates_by_group": {},
            "blocked_cells": set(),
            "ghost_anchor_count": 1,
            "blocked_cell_count": 1,
            "ordered_group_count": 0,
        },
    )

    report = build_phase3b_coordinate_validation_profile_probe(
        tmp_path / "project",
        profiles=[{"profile_id": "skipped", "time_limit_seconds": 5}],
    )

    assert report["status"]["evaluated"] is False
    assert report["status"]["outcome"] == "coordinate_validation_not_evaluated"
    assert report["probe"]["entries"][0]["status"] == "SKIPPED"
    assert report["probe"]["entries"][0]["reason"] == "mandatory_greedy_incomplete"
    assert fake_model.validation_calls == []


def test_coordinate_validation_profile_probe_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_profile_probe.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--profiles-json",
            json.dumps([{"profile_id": "p0", "time_limit_seconds": 0}]),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate validation profile probe" in no_write.stdout
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
            json.dumps([{"profile_id": "p0", "time_limit_seconds": 0}]),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_profile_probe_json=" in write.stdout
    payload = json.loads(
        (output_dir / "coordinate_validation_profile_probe.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_coordinate_validation_profile_probe_v1"
    assert (output_dir / "coordinate_validation_profile_probe.md").exists()
    assert (output_dir / "coordinate_validation_profile_probe.txt").exists()
