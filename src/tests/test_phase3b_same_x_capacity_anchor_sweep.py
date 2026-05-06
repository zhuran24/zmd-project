from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import src.search.phase3b_same_x_capacity_anchor_sweep as sweep_module
from src.search.phase3b_same_x_capacity_anchor_sweep import (
    SAME_X_CAPACITY_CONFLICT_REASON,
    build_phase3b_same_x_capacity_anchor_sweep,
    render_phase3b_same_x_capacity_anchor_sweep_markdown,
    render_phase3b_same_x_capacity_anchor_sweep_text,
)


class _FakeModel:
    _ghost_domains = [
        {"anchor": {"x": 0, "y": 0}, "cells": [(0, 0)]},
        {"anchor": {"x": 1, "y": 0}, "cells": [(1, 0)]},
    ]

    def _run_mandatory_greedy_pass(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "complete": True,
            "hinted_groups": 1,
            "hinted_instances": 2,
            "solution_hint": {"a": 1, "b": 2},
        }

    def _validate_coordinate_forced_hint(self, **kwargs: Any) -> dict[str, Any]:
        anchor_idx = int(kwargs["ghost_anchor_hint_idx"])
        if anchor_idx == 0:
            return {
                "attempted": False,
                "attempted_solver": False,
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": SAME_X_CAPACITY_CONFLICT_REASON,
                "forced_slot_field_count": 11,
                "forced_ghost_anchor": True,
                "capacity_conflict": {
                    "anchor_idx": 0,
                    "forced_count": 11,
                    "capacity": 10,
                    "lower_capacity": 0,
                    "upper_capacity": 10,
                    "ghost_rect": {"x": 0, "y": 0, "w": 2, "h": 2},
                    "x_interval": {"start": 0, "end": 1},
                },
            }
        return {
            "attempted": True,
            "attempted_solver": True,
            "status": "UNKNOWN",
            "accepted": False,
            "reason": "time_budget_exhausted",
            "forced_slot_field_count": 6,
            "forced_ghost_anchor": True,
            "wall_time": 0.2,
            "branches": 9,
            "conflicts": 1,
        }


def _fake_context() -> dict[str, Any]:
    return {
        "model": _FakeModel(),
        "ordered_groups": [{"group_id": "g", "facility_type": "t", "count": 2}],
        "candidates_by_group": {"g": [1, 2]},
        "ghost_anchor_count": 2,
        "blocked_cell_count": 1,
        "ordered_group_count": 1,
    }


def test_same_x_capacity_anchor_sweep_aggregates_reasons(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sweep_module, "_build_delta_context", lambda *args, **kwargs: _fake_context())
    monkeypatch.setattr(
        sweep_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_same_x_capacity_anchor_sweep(
        tmp_path / "project",
        candidate="2x2",
        anchor_indices=(0, 1),
        time_limit_seconds=0.1,
    )

    summary = report["sweep"]["summary"]
    assert report["metadata"]["source"] == "phase3b_same_x_capacity_anchor_sweep_v1"
    assert summary["same_x_capacity_rejected_count"] == 1
    assert summary["solver_attempted_count"] == 1
    assert report["sweep"]["entries"][0]["validation"]["attempted_solver"] is False
    assert report["sweep"]["entries"][1]["validation"]["attempted_solver"] is True
    assert report["sweep"]["reason_counts"][SAME_X_CAPACITY_CONFLICT_REASON] == 1
    markdown = render_phase3b_same_x_capacity_anchor_sweep_markdown(report)
    text = render_phase3b_same_x_capacity_anchor_sweep_text(report)
    assert "Anchor Matrix" in markdown
    assert "solver_attempted_count=1" in text


def test_same_x_capacity_anchor_sweep_reports_non_triggering_anchor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sweep_module, "_build_delta_context", lambda *args, **kwargs: _fake_context())
    monkeypatch.setattr(sweep_module, "compute_exact_artifact_hashes", lambda project_root: {})

    report = build_phase3b_same_x_capacity_anchor_sweep(
        tmp_path / "project",
        candidate="2x2",
        anchor_indices=(1,),
        time_limit_seconds=0.1,
    )

    assert report["sweep"]["summary"]["same_x_capacity_rejected_count"] == 0
    assert report["sweep"]["summary"]["solver_attempted_count"] == 1
    assert report["status"]["outcome"] == "same_x_capacity_did_not_explain_sweep"


def test_same_x_capacity_anchor_sweep_cli_writes_and_no_write_skips_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_same_x_capacity_anchor_sweep.py"
    spec = importlib.util.spec_from_file_location("same_x_capacity_sweep_cli", script)
    assert spec is not None and spec.loader is not None
    cli_module = importlib.util.module_from_spec(spec)
    sys.modules["same_x_capacity_sweep_cli"] = cli_module
    spec.loader.exec_module(cli_module)

    fake_report = {
        "metadata": {"source": "phase3b_same_x_capacity_anchor_sweep_v1"},
        "candidate": {"key": "2x2"},
        "status": {"outcome": "mixed_precheck_and_solver_anchor_set", "recommendation": "ok"},
        "sweep": {
            "summary": {
                "anchor_count": 1,
                "same_x_capacity_rejected_count": 1,
                "solver_attempted_count": 0,
                "anchor119_explained": False,
            },
            "status_counts": {"INFEASIBLE": 1},
            "reason_counts": {SAME_X_CAPACITY_CONFLICT_REASON: 1},
            "entries": [],
        },
        "checks": [],
    }
    monkeypatch.setattr(
        cli_module,
        "build_phase3b_same_x_capacity_anchor_sweep",
        lambda *args, **kwargs: fake_report,
    )

    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--anchors",
            "0",
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "sweep_smoke",
            "--no-write",
        ],
    )
    assert cli_module.main() == 0
    assert not output_dir.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--anchors",
            "0",
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "sweep_smoke",
        ],
    )
    assert cli_module.main() == 0
    payload = json.loads((output_dir / "sweep_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_same_x_capacity_anchor_sweep_v1"
    assert (output_dir / "sweep_smoke.md").exists()
    assert (output_dir / "sweep_smoke.txt").exists()
