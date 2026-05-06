from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Set, Tuple

import pytest

import src.search.phase3b_greedy_pose_order_comparison as comparison_module
from src.search.phase3b_greedy_pose_order_comparison import (
    build_phase3b_greedy_pose_order_comparison,
    render_phase3b_greedy_pose_order_comparison_markdown,
    render_phase3b_greedy_pose_order_comparison_text,
)


class _FakeDelegate:
    def __init__(self) -> None:
        self._template_pose_tuple_by_idx = {
            "template": {
                1: (0, 1, 0),
                2: (2, 11, 0),
                3: (4, 21, 0),
            }
        }


class _FakeModel:
    def __init__(self) -> None:
        self._coordinate_delegate = _FakeDelegate()

    def _run_mandatory_greedy_pass(
        self,
        *,
        ordered_groups: Sequence[Mapping[str, Any]],
        candidates_by_group: Mapping[str, Sequence[int]],
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
        initial_solution_hint: Optional[Mapping[str, int]] = None,
        initial_committed_cells: Optional[Set[Tuple[int, int]]] = None,
        initial_hinted_occupied_cells: Optional[Set[Tuple[int, int]]] = None,
        custom_group_orders: Optional[Mapping[str, Sequence[int]]] = None,
        stop_on_first_failure: bool = False,
    ) -> dict[str, Any]:
        del initial_solution_hint, initial_committed_cells
        del initial_hinted_occupied_cells, stop_on_first_failure
        blocked = set(blocked_cells or set())
        solution_hint: dict[str, int] = {}
        for group in ordered_groups:
            group_id = str(group["group_id"])
            candidate_order = list(
                (custom_group_orders or {}).get(
                    group_id,
                    candidates_by_group[group_id],
                )
            )
            if len(ordered_groups) > 1 and blocked:
                candidate_order = [2, 3, 1]
            chosen = candidate_order[: int(group["count"])]
            for instance_id, pose_idx in zip(group["instance_ids"], chosen):
                solution_hint[str(instance_id)] = int(pose_idx)
        return {
            "complete": True,
            "reason": None,
            "hinted_groups": len(ordered_groups),
            "hinted_instances": len(solution_hint),
            "solution_hint": solution_hint,
        }

    def _validate_coordinate_forced_hint(self, **kwargs: Any) -> dict[str, Any]:
        poses = tuple(dict(kwargs["solution_hint"]).values())
        status = "INFEASIBLE" if poses and min(poses) == 1 else "UNKNOWN"
        labels = []
        for slot_index, (solution_id, pose_idx) in enumerate(
            dict(kwargs["solution_hint"]).items()
        ):
            x_val, y_val, mode_id = self._coordinate_delegate._template_pose_tuple_by_idx[
                "template"
            ][int(pose_idx)]
            del mode_id
            for field, value in [("x", x_val), ("y", y_val)]:
                labels.append(
                    {
                        "stable_key": f"mandatory|group::target|{slot_index}|{solution_id}|{pose_idx}|{field}",
                        "solution_id": solution_id,
                        "pose_index": int(pose_idx),
                        "field": field,
                        "forced_value": int(value),
                    }
                )
        return {
            "attempted": True,
            "status": status,
            "accepted": False,
            "reason": status.lower(),
            "missing_hint_count": 0,
            "missing_pose_tuple_count": 0,
            "forced_slot_field_count": len(labels),
            "forced_ghost_anchor": kwargs["ghost_anchor_hint_idx"] is not None,
            "forced_fields": list(kwargs["force_fields"]),
            "require_complete": bool(kwargs["require_complete"]),
            "force_equality_labels": labels
            if kwargs.get("collect_force_equality_labels")
            else [],
            "wall_time": 0.1,
            "user_time": 0.1,
            "deterministic_time": 0.01,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
            "solver_parameters": {"profile_id": "fake"},
        }

    def _y_then_x_pose_order(self, tpl: str, candidate_indices: Sequence[int]) -> list[int]:
        del tpl
        return sorted(candidate_indices, reverse=True)


def _fake_context() -> dict[str, Any]:
    group = {
        "group_id": "group::target",
        "facility_type": "template",
        "operation_type": "op",
        "count": 1,
        "instance_ids": ["target_001"],
    }
    other = {
        "group_id": "group::other",
        "facility_type": "template",
        "operation_type": "other",
        "count": 1,
        "instance_ids": ["other_001"],
    }
    return {
        "model": _FakeModel(),
        "ordered_groups": [group, other],
        "candidates_by_group": {
            "group::target": [1, 2, 3],
            "group::other": [1, 2, 3],
        },
        "blocked_cells": {(0, 0)},
        "ghost_anchor_count": 3,
        "blocked_cell_count": 1,
        "ordered_group_count": 2,
    }


def test_greedy_pose_order_comparison_records_ordering_sensitive_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        comparison_module,
        "_build_delta_context",
        lambda *args, **kwargs: _fake_context(),
    )
    monkeypatch.setattr(
        comparison_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_greedy_pose_order_comparison(
        tmp_path / "project",
        group_id="group::target",
        strategies=["single_group_blocked", "full_blocked"],
        time_limit_seconds=0.5,
    )

    assert report["metadata"]["source"] == "phase3b_greedy_pose_order_comparison_v1"
    assert report["status"]["outcome"] == "ordering_sensitive_infeasible"
    entries = report["comparison"]["entries"]
    assert entries[0]["target_pose_indices"] == [1]
    assert entries[0]["target_validation"]["status"] == "INFEASIBLE"
    assert entries[1]["target_pose_indices"] == [2]
    assert entries[1]["target_validation"]["status"] == "UNKNOWN"
    assert report["comparison"]["single_group_blocked_vs_full_blocked"][
        "pose_intersection_count"
    ] == 0

    markdown = render_phase3b_greedy_pose_order_comparison_markdown(report)
    text = render_phase3b_greedy_pose_order_comparison_text(report)
    assert "Greedy Pose Order Comparison" in markdown
    assert "ordering_sensitive_infeasible" in text


def test_greedy_pose_order_comparison_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_greedy_pose_order_comparison.py"

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
    assert "phase3b greedy pose order comparison" in no_write.stdout
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
    assert "greedy_pose_order_comparison_json=" in write.stdout
    payload = json.loads(
        (output_dir / "greedy_pose_order_comparison.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_greedy_pose_order_comparison_v1"
    assert (output_dir / "greedy_pose_order_comparison.md").exists()
    assert (output_dir / "greedy_pose_order_comparison.txt").exists()
