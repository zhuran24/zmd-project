from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

from ortools.sat.python import cp_model
import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724"


def _load(name: str, module_name: str | None = None):
    path = RESEARCH / f"{name}.py"
    spec = importlib.util.spec_from_file_location(module_name or name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE_CONTRACT = _load("baseline_admission_v1")
REPLAY = _load("cut_free_incumbent_replay_v1")
REBUILD = _load("baseline_rebuild_v1")


def _tiny_inputs() -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    candidate = {
        "facility_pools": {
            "fixture": [
                {
                    "pose_id": "fixture-pose",
                    "anchor": {"x": 0, "y": 0},
                }
            ]
        }
    }
    mandatory = [
        {
            "instance_id": "fixture-001",
            "facility_type": "fixture",
            "operation_type": "op",
        }
    ]
    incumbent = {
        "fixture-001": {
            "instance_id": "fixture-001",
            "facility_type": "fixture",
            "operation_type": "op",
            "bound_type": "exact",
            "pose_idx": 0,
            "pose_id": "fixture-pose",
            "anchor": {"x": 0, "y": 0},
        }
    }
    return candidate, mandatory, incumbent


def test_fixed_assignment_replay_accepts_tiny_feasible_model(tmp_path: Path) -> None:
    model = cp_model.CpModel()
    x = model.new_bool_var("z__group::fixture::op::0__0")
    model.add(x == 1)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    result = REPLAY.replay_fixed_assignment(
        model_path.read_bytes(),
        incumbent=_tiny_inputs()[2],
        mandatory_instances=_tiny_inputs()[1],
        candidate_placements=_tiny_inputs()[0],
        max_time_seconds=2.0,
    )

    assert result["status"] == "PASS"
    assert result["variable_count"] == 1
    assert result["fixed_assignment_count"] == 1


def test_fixed_assignment_replay_rejects_unmapped_assignment(
    tmp_path: Path,
) -> None:
    model = cp_model.CpModel()
    x = model.new_bool_var("z__group::fixture::op::0__0")
    model.add(x == 1)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    candidate, mandatory, incumbent = _tiny_inputs()
    incumbent["fixture-001"]["pose_idx"] = 1
    with pytest.raises(REPLAY.ReplayError, match="absent or duplicated"):
        REPLAY.replay_fixed_assignment(
            model_path.read_bytes(),
            incumbent=incumbent,
            mandatory_instances=mandatory,
            candidate_placements=candidate,
            max_time_seconds=2.0,
        )


def test_fixed_assignment_replay_allows_unnamed_nonselector(
    tmp_path: Path,
) -> None:
    model = cp_model.CpModel()
    x = model.new_bool_var("z__group::fixture::op::0__0")
    unnamed = model.new_bool_var("")
    model.add(x == 1)
    model.add(unnamed == 0)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    result = REPLAY.replay_fixed_assignment(
        model_path.read_bytes(),
        incumbent=_tiny_inputs()[2],
        mandatory_instances=_tiny_inputs()[1],
        candidate_placements=_tiny_inputs()[0],
        max_time_seconds=2.0,
    )

    assert result["status"] == "PASS"
    assert result["fixed_assignment_count"] == 1


def test_fixed_assignment_replay_rejects_nonboolean_selector(
    tmp_path: Path,
) -> None:
    model = cp_model.CpModel()
    x = model.new_int_var(0, 2, "z__group::fixture::op::0__0")
    model.add(x == 1)
    model_path = tmp_path / "model.bin"
    assert model.export_to_file(str(model_path))

    with pytest.raises(REPLAY.ReplayError, match="exact boolean"):
        REPLAY.replay_fixed_assignment(
            model_path.read_bytes(),
            incumbent=_tiny_inputs()[2],
            mandatory_instances=_tiny_inputs()[1],
            candidate_placements=_tiny_inputs()[0],
            max_time_seconds=2.0,
        )


def test_strict_json_requires_canonical_authority_bytes() -> None:
    assert REPLAY._strict_json(b'{"a":1}\n', "fixture") == {"a": 1}
    with pytest.raises(REPLAY.ReplayError, match="not canonical"):
        REPLAY._strict_json(b'{"a": 1}\n', "fixture")


def _fixed_args(**changes: object) -> argparse.Namespace:
    value = {
        "master_seconds": 900.0,
        "binding_seconds": 600.0,
        "routing_seconds": 600.0,
        "max_iterations": 30,
        "binding_alt_cap": 200,
        "workers": 1,
        "seed": 2026072301,
        "ghost_w": 6,
        "ghost_h": 6,
        "run_nonce": "fixture-run",
        "campaign_provenance": ROOT / ".artifacts/fixture-campaign/campaign-provenance.json",
        "candidate_placements": (ROOT / "data/preprocessed/candidate_placements.json"),
        "canonical_rules": (ROOT / "rules/canonical_rules.json"),
        "mandatory_instances": (ROOT / "data/preprocessed/mandatory_exact_instances.json"),
    }
    value.update(changes)
    return argparse.Namespace(**value)


def test_baseline_rebuild_rejects_parameter_drift() -> None:
    REBUILD._validate_fixed_parameters(_fixed_args())
    with pytest.raises(REBUILD.BaselineRebuildError, match="parameters drifted"):
        REBUILD._validate_fixed_parameters(_fixed_args(seed=7))
    with pytest.raises(REBUILD.BaselineRebuildError, match="nonce"):
        REBUILD._validate_fixed_parameters(_fixed_args(run_nonce=""))
    with pytest.raises(REBUILD.BaselineRebuildError, match="campaign provenance"):
        REBUILD._validate_fixed_parameters(_fixed_args(campaign_provenance=Path("relative-provenance.json")))
    with pytest.raises(REBUILD.BaselineRebuildError, match="not absolute"):
        REBUILD._validate_fixed_parameters(_fixed_args(candidate_placements=Path("relative.json")))


def test_baseline_builder_declares_non_authorizing_output() -> None:
    source = (RESEARCH / "baseline_rebuild_v1.py").read_text(encoding="utf-8")
    assert '"authorizing": False' in source
    assert "EXACT_CUT_FRAMEWORK_ATTACH" in source
    assert "enabled_cut_families=()" in source
    assert "EXPECTED_REPOSITORY_ROOT" not in source
    assert "EXPECTED_HEAD" not in source
    assert "sys.meta_path" not in source
    assert "importlib" not in source
    assert "baseline_contract.campaign_provenance" in source
    assert BASELINE_CONTRACT.CHECKOUT_IMPORT_MODE == "tracked_clean_pinned_checkout"
