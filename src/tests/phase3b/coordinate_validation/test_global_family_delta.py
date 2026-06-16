from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from ortools.sat.python import cp_model

import src.search.phase3b.coordinate_validation.global_family_delta as delta_module
from src.models.master_model import _clone_model_proto
from src.search.phase3b.coordinate_validation.global_family_delta import (
    _apply_global_family_variant_selector,
    build_phase3b_coordinate_validation_global_family_delta,
    render_phase3b_coordinate_validation_global_family_delta_markdown,
    render_phase3b_coordinate_validation_global_family_delta_text,
)


class _Slot:
    def __init__(self, *, x: Any, y: Any, mode: Any) -> None:
        self.x = x
        self.y = y
        self.mode = mode


class _Delegate:
    def __init__(self, model: cp_model.CpModel) -> None:
        x = model.NewIntVar(0, 1, "x__group::alpha::op::0::slot::0")
        y = model.NewIntVar(0, 1, "y__group::alpha::op::0::slot::0")
        mode = model.NewIntVar(0, 0, "mode__group::alpha::op::0::slot::0")
        cover = model.NewBoolVar("cover_choice_active__group::alpha::op::0::slot::0")
        model.Add(x + cover == 2)
        self.mandatory_slots = {"group::alpha::op::0": [_Slot(x=x, y=y, mode=mode)]}


class _Model:
    def __init__(self) -> None:
        self.model = cp_model.CpModel()
        self._coordinate_delegate = _Delegate(self.model)


def _fake_context() -> dict[str, Any]:
    group = {
        "group_id": "group::alpha::op::0",
        "facility_type": "alpha",
        "operation_type": "op",
        "count": 1,
        "instance_ids": ["alpha_001"],
    }
    return {
        "model": _Model(),
        "ordered_groups": [group],
        "candidates_by_group": {"group::alpha::op::0": [1]},
        "ghost_anchor_count": 1,
        "blocked_cell_count": 0,
        "ordered_group_count": 1,
    }


def _core_json(path: Path) -> Path:
    payload = {
        "direct_equality_core": {
            "remaining_labels": [
                {
                    "stable_key": "k1",
                    "group_id": "group::alpha::op::0",
                    "solution_id": "alpha_001",
                    "slot_key": "0",
                    "slot_index": 0,
                    "template": "alpha",
                    "pose_index": 1,
                    "field": "x",
                    "forced_value": 0,
                }
            ]
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_global_family_delta_finds_power_coverage_unlocking_variant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        delta_module,
        "_build_delta_context",
        lambda *args, **kwargs: _fake_context(),
    )
    monkeypatch.setattr(
        delta_module,
        "compute_exact_artifact_hashes",
        lambda project_root: {"rules/canonical_rules.json": "hash"},
    )

    report = build_phase3b_coordinate_validation_global_family_delta(
        tmp_path / "project",
        group_id="group::alpha::op::0",
        core_json=_core_json(tmp_path / "core.json"),
        variants=("base_12_key_full_model", "remove_power_coverage"),
        time_limit_seconds=0.2,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_global_family_delta_v1"
    )
    assert report["status"]["base_status"] == "INFEASIBLE"
    assert report["status"]["outcome"] == "family_delta_unlocking_variant_found"
    first = report["delta"]["first_unlocking_variant"]
    assert first["variant"] == "remove_power_coverage"
    assert report["delta"]["entries"][1]["semantic_weakening"] is True
    assert report["delta"]["entries"][1]["proof_evidence"] is False
    markdown = render_phase3b_coordinate_validation_global_family_delta_markdown(report)
    text = render_phase3b_coordinate_validation_global_family_delta_text(report)
    assert "Variant Matrix" in markdown
    assert "base_status=INFEASIBLE" in text


def test_global_family_delta_selector_reports_skipped_reason() -> None:
    model = cp_model.CpModel()
    x = model.NewIntVar(0, 1, "x__group::alpha::op::0::slot::0")
    model.Add(x == 0)
    proto = _clone_model_proto(model.Proto())

    summary = _apply_global_family_variant_selector(
        proto,
        variant="remove_required_optional_signature_count",
        group_id="group::alpha::op::0",
    )

    assert summary["skipped"] is True
    assert summary["skip_reason"] == "selector_matched_no_constraints"
    assert summary["selector_confidence"] == "high"
    assert summary["semantic_weakening"] is True


def test_global_family_delta_selector_splits_target_signature_membership() -> None:
    model = cp_model.CpModel()
    target_signature = model.NewIntVar(0, 1, "signature__group::alpha::op::0::slot::0")
    target_is_sig = model.NewBoolVar("is_sig__group::alpha::op::0::slot::0__sig_000")
    target_region = model.NewBoolVar("region__group::alpha::op::0::slot::0__sig_000__0")
    other_signature = model.NewIntVar(0, 1, "signature__group::beta::op::0::slot::0")
    unrelated = model.NewIntVar(0, 1, "x__group::alpha::op::0::slot::0")
    model.Add(target_signature == 0)
    model.Add(target_is_sig == 1)
    model.Add(target_region == 1)
    model.Add(other_signature == 0)
    model.Add(unrelated == 0)

    def removed_count(variant: str) -> int:
        proto = _clone_model_proto(model.Proto())
        summary = _apply_global_family_variant_selector(
            proto,
            variant=variant,
            group_id="group::alpha::op::0",
        )
        assert summary["skipped"] is False
        return int(summary["removed_constraint_count"])

    assert removed_count("remove_target_mandatory_signature_membership_or_bucket") == 3
    assert removed_count("remove_other_mandatory_signature_membership_or_bucket") == 1
    assert removed_count("remove_target_mandatory_signature_var") == 1
    assert removed_count("remove_target_mandatory_is_sig_bucket") == 1
    assert removed_count("remove_target_mandatory_region") == 1


def test_global_family_delta_table_channel_rejects_out_of_bucket_tuple() -> None:
    model = cp_model.CpModel()
    group_id = "group::alpha::op::0"
    x = model.NewIntVar(0, 5, f"x__{group_id}::slot::0")
    y = model.NewIntVar(0, 7, f"y__{group_id}::slot::0")
    mode = model.NewIntVar(0, 1, f"mode__{group_id}::slot::0")
    signature = model.NewIntVar(0, 1, f"signature__{group_id}::slot::0")
    model.Add(x == 2)
    model.Add(y == 0)
    model.Add(mode == 0)
    model.Add(signature == 0)
    local_model = delta_module.cp_model_from_proto(_clone_model_proto(model.Proto()))
    slot = SimpleNamespace(
        x=x,
        y=y,
        mode=mode,
        signature=signature,
        template="alpha",
        signature_id_to_bucket_id={0: "sig_000", 1: "sig_001"},
    )
    delegate = SimpleNamespace(
        mandatory_slots={group_id: [slot]},
        _mandatory_group_bucket_pose_indices={group_id: {"sig_000": (0, 1), "sig_001": (2,)}},
        _template_pose_tuple_by_idx={"alpha": {0: (0, 0, 0), 1: (1, 0, 0), 2: (5, 7, 1)}},
    )

    summary = delta_module._add_target_mandatory_signature_table_channel(
        local_model,
        delegate=delegate,
        group_id=group_id,
    )
    solver = cp_model.CpSolver()
    status = solver.Solve(local_model)

    assert summary["added"] is True
    assert summary["added_table_constraint_count"] == 1
    assert summary["added_table_row_count"] == 3
    assert solver.StatusName(status) == "INFEASIBLE"


def test_global_family_delta_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_validation" / "build_global_family_delta.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--time-limit-seconds",
            "0",
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate validation global family delta" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--time-limit-seconds",
            "0",
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "global_delta_smoke",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_validation_global_family_delta_json=" in write.stdout
    payload = json.loads((output_dir / "global_delta_smoke.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_global_family_delta_v1"
    )
    assert (output_dir / "global_delta_smoke.md").exists()
    assert (output_dir / "global_delta_smoke.txt").exists()
