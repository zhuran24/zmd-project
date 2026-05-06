from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import src.search.phase3b_full_forced_hint_field_family_delta as delta_module
from src.search.phase3b_full_forced_hint_field_family_delta import (
    build_phase3b_full_forced_hint_field_family_delta,
    render_phase3b_full_forced_hint_field_family_delta_markdown,
    render_phase3b_full_forced_hint_field_family_delta_text,
)


class _FakeModel:
    _ghost_domains = [
        {"anchor": {"x": 0, "y": 0}, "cells": [(0, 0)]},
    ]

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def _run_mandatory_greedy_pass(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "complete": True,
            "hinted_groups": 1,
            "hinted_instances": 2,
            "solution_hint": {"a": 1, "b": 2},
        }

    def _validate_coordinate_forced_hint(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        fields = tuple(kwargs.get("force_fields", ()))
        keys = kwargs.get("force_equality_keys")
        collect = bool(kwargs.get("collect_force_equality_labels", False))
        labels = _labels()
        if collect:
            return _payload(
                status="INFEASIBLE",
                reason="infeasible",
                forced_count=6,
                labels=labels,
            )
        if keys is not None:
            active = {str(key) for key in keys}
            status = "INFEASIBLE" if "k2" in active else "OPTIMAL"
            return _payload(status=status, reason=status.lower(), forced_count=len(active))
        if fields == ("x",):
            return _payload(status="UNKNOWN", reason="time_budget_exhausted", forced_count=2)
        if fields == ("y",):
            return _payload(status="OPTIMAL", reason="accepted", accepted=True, forced_count=2)
        return _payload(status="INFEASIBLE", reason="infeasible", forced_count=6)


def _payload(
    *,
    status: str,
    reason: str,
    forced_count: int,
    accepted: bool = False,
    labels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "attempted": True,
        "attempted_solver": True,
        "status": status,
        "accepted": accepted,
        "reason": reason,
        "forced_slot_field_count": forced_count,
        "forced_ghost_anchor": True,
        "wall_time": 0.01,
        "branches": 0,
        "conflicts": 0,
    }
    if labels:
        payload["force_equality_labels"] = labels
    return payload


def _labels() -> list[dict[str, Any]]:
    return [
        {
            "stable_key": "k1",
            "field": "x",
            "group_id": "group::alpha::op::0",
            "template": "manufacturing_5x5",
            "forced_value": 0,
        },
        {
            "stable_key": "k2",
            "field": "y",
            "group_id": "group::alpha::op::0",
            "template": "manufacturing_5x5",
            "forced_value": 5,
        },
        {
            "stable_key": "k3",
            "field": "mode",
            "group_id": "group::beta::op::0",
            "template": "manufacturing_3x3",
            "forced_value": 1,
        },
    ]


def _fake_context() -> dict[str, Any]:
    return {
        "model": _FakeModel(),
        "ordered_groups": [{"group_id": "g", "facility_type": "t", "count": 2}],
        "candidates_by_group": {"g": [1, 2]},
        "ghost_anchor_count": 1,
        "blocked_cell_count": 1,
        "ordered_group_count": 1,
    }


def test_full_forced_hint_delta_aggregates_fields_and_labels(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(delta_module, "_build_delta_context", lambda *args, **kwargs: _fake_context())
    monkeypatch.setattr(delta_module, "compute_exact_artifact_hashes", lambda project_root: {})

    report = build_phase3b_full_forced_hint_field_family_delta(
        tmp_path / "project",
        candidate="2x2",
        anchor_indices=(0,),
        focus_anchor_idx=0,
        field_variants=("x", "y", "x_y_mode"),
        template_filters=("manufacturing_5x5",),
        time_limit_seconds=0.1,
    )

    assert report["metadata"]["source"] == "phase3b_full_forced_hint_field_family_delta_v1"
    assert report["label_summary"]["field_counts"] == {"mode": 1, "x": 1, "y": 1}
    assert report["label_summary"]["template_counts"]["manufacturing_5x5"] == 2
    assert report["field_delta"]["status_counts_by_field_variant"]["x"]["UNKNOWN"] == 1
    assert report["field_delta"]["status_counts_by_field_variant"]["y"]["OPTIMAL"] == 1
    assert report["template_delta"]["status_counts_by_template"]["manufacturing_5x5"]["INFEASIBLE"] == 1
    markdown = render_phase3b_full_forced_hint_field_family_delta_markdown(report)
    text = render_phase3b_full_forced_hint_field_family_delta_text(report)
    assert "Field Variant Matrix" in markdown
    assert "field_entry_count=3" in text


def test_force_equality_keys_filtering_reaches_fake_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_context = _fake_context()
    fake_model = fake_context["model"]
    monkeypatch.setattr(delta_module, "_build_delta_context", lambda *args, **kwargs: fake_context)
    monkeypatch.setattr(delta_module, "compute_exact_artifact_hashes", lambda project_root: {})

    build_phase3b_full_forced_hint_field_family_delta(
        tmp_path / "project",
        candidate="2x2",
        anchor_indices=(0,),
        focus_anchor_idx=0,
        field_variants=("x_y_mode",),
        template_filters=("manufacturing_5x5",),
        time_limit_seconds=0.1,
    )

    filtered_calls = [
        call
        for call in fake_model.calls
        if call.get("force_equality_keys") is not None
    ]
    assert filtered_calls
    assert any(set(call["force_equality_keys"]) == {"k1", "k2"} for call in filtered_calls)


def test_full_forced_hint_delta_cli_writes_and_no_write_skips_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_full_forced_hint_field_family_delta.py"
    spec = importlib.util.spec_from_file_location("full_forced_hint_delta_cli", script)
    assert spec is not None and spec.loader is not None
    cli_module = importlib.util.module_from_spec(spec)
    sys.modules["full_forced_hint_delta_cli"] = cli_module
    spec.loader.exec_module(cli_module)

    fake_report = {
        "metadata": {"source": "phase3b_full_forced_hint_field_family_delta_v1"},
        "candidate": {"key": "2x2"},
        "status": {"outcome": "filtered_cases_remain_infeasible", "recommendation": "ok"},
        "summary": {"field_entry_count": 1, "template_entry_count": 0, "same_x_precheck_count": 0},
        "label_summary": {"label_count": 0},
        "field_delta": {"entries": [], "status_counts": {}},
        "template_delta": {"entries": [], "status_counts": {}},
        "checks": [],
    }
    monkeypatch.setattr(
        cli_module,
        "build_phase3b_full_forced_hint_field_family_delta",
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
            "delta_smoke",
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
            "delta_smoke",
        ],
    )
    assert cli_module.main() == 0
    payload = json.loads((output_dir / "delta_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_full_forced_hint_field_family_delta_v1"
    assert (output_dir / "delta_smoke.md").exists()
    assert (output_dir / "delta_smoke.txt").exists()
