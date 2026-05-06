from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import src.search.phase3b_direct_equality_core_exchange as exchange_module
from src.search.phase3b_direct_equality_core_exchange import (
    build_phase3b_direct_equality_core_exchange,
    render_phase3b_direct_equality_core_exchange_markdown,
    render_phase3b_direct_equality_core_exchange_text,
)


class _FakeModel:
    def _run_mandatory_greedy_pass(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "complete": True,
            "hinted_groups": 1,
            "hinted_instances": 3,
            "solution_hint": {"a": 1, "b": 2, "c": 3},
        }

    def _validate_coordinate_forced_hint(self, **kwargs: Any) -> dict[str, Any]:
        keys = set(str(key) for key in kwargs["force_equality_keys"])
        status = "INFEASIBLE" if {"k1", "k2", "k3"}.issubset(keys) else "UNKNOWN"
        return {
            "attempted": True,
            "attempted_solver": True,
            "status": status,
            "accepted": False,
            "reason": "infeasible" if status == "INFEASIBLE" else "time_budget_exhausted",
            "forced_slot_field_count": len(keys),
            "wall_time": 0.1,
            "branches": 0,
            "conflicts": 0,
        }


def _fake_context() -> dict[str, Any]:
    return {
        "model": _FakeModel(),
        "ordered_groups": [{"group_id": "group::t::op::0", "facility_type": "t"}],
        "candidates_by_group": {"group::t::op::0": [1, 2, 3]},
    }


def _write_core(path: Path, keys: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"direct_equality_core": {"final_keys": keys}}),
        encoding="utf-8",
    )


def test_direct_equality_core_exchange_evaluates_union_subsets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    core_a = tmp_path / "a.json"
    core_b = tmp_path / "b.json"
    _write_core(core_a, ["k1", "k2", "k3"])
    _write_core(core_b, ["k1", "k4", "k5"])
    monkeypatch.setattr(exchange_module, "_build_delta_context", lambda *args, **kwargs: _fake_context())
    monkeypatch.setattr(exchange_module, "compute_exact_artifact_hashes", lambda project_root: {})

    report = build_phase3b_direct_equality_core_exchange(
        tmp_path / "project",
        core_paths=[core_a, core_b],
        group_id="group::t::op::0",
        subset_size=3,
        max_subsets=10,
        time_limit_seconds=0.1,
    )

    assert report["metadata"]["source"] == "phase3b_direct_equality_core_exchange_v1"
    assert report["metadata"]["proof_source"] is False
    assert report["summary"]["union_key_count"] == 5
    assert report["summary"]["evaluated_subset_count"] == 10
    assert report["summary"]["status_counts"]["INFEASIBLE"] == 1
    assert report["status"]["outcome"] == "mixed_exchange_subsets"
    markdown = render_phase3b_direct_equality_core_exchange_markdown(report)
    text = render_phase3b_direct_equality_core_exchange_text(report)
    assert "Proof source: false" in markdown
    assert "solver_invoked=true" in text


def test_direct_equality_core_exchange_cli_writes_and_no_write_skips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_direct_equality_core_exchange.py"
    spec = importlib.util.spec_from_file_location("core_exchange_cli", script)
    assert spec is not None and spec.loader is not None
    cli_module = importlib.util.module_from_spec(spec)
    sys.modules["core_exchange_cli"] = cli_module
    spec.loader.exec_module(cli_module)

    fake_report = {
        "metadata": {"source": "phase3b_direct_equality_core_exchange_v1"},
        "candidate": {"key": "67x13", "anchor_idx": 119},
        "profile": {"group_id": "group::t::op::0"},
        "summary": {
            "union_key_count": 3,
            "evaluated_subset_count": 1,
            "status_counts": {"INFEASIBLE": 1},
        },
        "status": {"outcome": "mixed_exchange_subsets", "recommendation": "next"},
        "entries": [],
        "checks": [],
    }
    monkeypatch.setattr(
        cli_module,
        "build_phase3b_direct_equality_core_exchange",
        lambda *args, **kwargs: fake_report,
    )
    output_dir = tmp_path / "out"

    sys.argv = [
        str(script),
        "--project-root",
        str(tmp_path / "project"),
        "--core-json",
        str(tmp_path / "a.json"),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        "exchange",
        "--no-write",
    ]
    assert cli_module.main() == 0
    assert not output_dir.exists()

    sys.argv = [
        str(script),
        "--project-root",
        str(tmp_path / "project"),
        "--core-json",
        str(tmp_path / "a.json"),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        "exchange",
    ]
    assert cli_module.main() == 0
    assert (output_dir / "exchange.json").exists()
    assert (output_dir / "exchange.md").exists()
    assert (output_dir / "exchange.txt").exists()
