from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_candidate_shape_inventory_comparison import (
    build_candidate_shape_inventory_comparison,
)


def test_candidate_shape_inventory_comparison_plan_only_does_not_construct(tmp_path: Path) -> None:
    patch_spec = tmp_path / "patch_spec.json"
    baseline = tmp_path / "baseline.json"
    reduced_plan = tmp_path / "run_plan.json"
    output_dir = _output_dir(tmp_path)
    _write_patch_spec(patch_spec)
    _write_inventory(baseline, candidate_key="42x32", candidate_tuple=[1344, 42, 32])
    _write_reduced_plan(reduced_plan)

    def fail_session_factory(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("session factory should not be called in plan-only mode")

    payload = build_candidate_shape_inventory_comparison(
        project_root=tmp_path,
        patch_spec_path=patch_spec,
        baseline_inventory_path=baseline,
        reduced_frontier_plan_path=reduced_plan,
        output_dir=output_dir,
        run_id="plan_only",
        execute_no_solve=False,
        session_factory=fail_session_factory,
    )

    assert payload["status"] == "planned_only"
    assert payload["cp_solver_solve_called"] is False
    assert payload["source_mutation_performed"] is False
    assert [row["candidate_key"] for row in payload["rows"]] == ["42x32", "70x12", "70x19"]
    assert payload["rows"][1]["status"] == "planned_not_executed"
    assert payload["recommendation"]["action"] == "run_candidate_shape_inventory_comparison_no_solve"


def test_candidate_shape_inventory_comparison_execute_no_solve_with_fakes(tmp_path: Path) -> None:
    patch_spec = tmp_path / "patch_spec.json"
    baseline = tmp_path / "baseline.json"
    reduced_plan = tmp_path / "run_plan.json"
    output_dir = _output_dir(tmp_path)
    _write_patch_spec(patch_spec)
    _write_inventory(
        baseline,
        candidate_key="42x32",
        candidate_tuple=[1344, 42, 32],
        constraints=1000,
        ghost_seconds=10.0,
    )
    _write_reduced_plan(reduced_plan)
    calls: list[tuple[int, int]] = []

    def fake_session_factory(*args, **kwargs):
        return FakeSession()

    def fake_precheck_factory(**kwargs):
        return {"triggered": False, "boundary_port_precheck": {"evaluated": True}}

    def fake_model_factory(*args, **kwargs):
        calls.append(tuple(kwargs["ghost_rect"]))
        w, h = kwargs["ghost_rect"]
        return FakeMasterModel(constraints=700 if (w, h) == (70, 12) else 900)

    payload = build_candidate_shape_inventory_comparison(
        project_root=tmp_path,
        patch_spec_path=patch_spec,
        baseline_inventory_path=baseline,
        reduced_frontier_plan_path=reduced_plan,
        output_dir=output_dir,
        run_id="exec",
        execute_no_solve=True,
        session_factory=fake_session_factory,
        precheck_factory=fake_precheck_factory,
        model_factory=fake_model_factory,
    )

    assert calls == [(70, 12), (70, 19)]
    assert payload["status"] == "completed"
    assert payload["interpretation"]["classification"] == "candidate_shape_inventory_comparison_ready"
    assert payload["recommendation"]["action"] == "review_no_source_shape_scaling_before_runtime"
    rows = {row["candidate_key"]: row for row in payload["rows"]}
    assert rows["70x12"]["constraint_ratio_vs_baseline"] == pytest.approx(0.7)
    assert rows["70x19"]["constraint_ratio_vs_baseline"] == pytest.approx(0.9)
    assert payload["sensitive_path_comparison"]["changed"] is False


def test_candidate_shape_inventory_comparison_rejects_bad_namespace(tmp_path: Path) -> None:
    patch_spec = tmp_path / "patch_spec.json"
    baseline = tmp_path / "baseline.json"
    reduced_plan = tmp_path / "run_plan.json"
    _write_patch_spec(patch_spec)
    _write_inventory(baseline, candidate_key="42x32", candidate_tuple=[1344, 42, 32])
    _write_reduced_plan(reduced_plan)

    with pytest.raises(ValueError, match="outside candidate shape comparison namespace"):
        build_candidate_shape_inventory_comparison(
            project_root=tmp_path,
            patch_spec_path=patch_spec,
            baseline_inventory_path=baseline,
            reduced_frontier_plan_path=reduced_plan,
            output_dir=tmp_path / "bad",
        )


def test_candidate_shape_inventory_comparison_requires_spec_only_patch(tmp_path: Path) -> None:
    patch_spec = tmp_path / "patch_spec.json"
    baseline = tmp_path / "baseline.json"
    reduced_plan = tmp_path / "run_plan.json"
    output_dir = _output_dir(tmp_path)
    _write_patch_spec(patch_spec, source_mutation_performed=True)
    _write_inventory(baseline, candidate_key="42x32", candidate_tuple=[1344, 42, 32])
    _write_reduced_plan(reduced_plan)

    with pytest.raises(ValueError, match="no source mutation performed"):
        build_candidate_shape_inventory_comparison(
            project_root=tmp_path,
            patch_spec_path=patch_spec,
            baseline_inventory_path=baseline,
            reduced_frontier_plan_path=reduced_plan,
            output_dir=output_dir,
        )


class FakeSession:
    master_search_profile = "exact_coordinate_guided_branching_v4"
    core_build_seconds = 1.0
    core = object()


class FakeVariable:
    domain = [0, 1]


class FakeConstraint:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def WhichOneof(self, _name: str) -> str:
        return self.kind


class FakeProto:
    def __init__(self, constraints: int) -> None:
        self.variables = [FakeVariable() for _ in range(10)]
        self.constraints = [FakeConstraint("linear") for _ in range(constraints)]
        self.objective = None


class FakeCpModel:
    def __init__(self, constraints: int) -> None:
        self.constraints = constraints

    def Proto(self) -> FakeProto:
        return FakeProto(self.constraints)


class FakeMasterModel:
    def __init__(self, constraints: int) -> None:
        self.model = FakeCpModel(constraints)
        self.build_stats = {
            "exact_core_reuse": {"ghost_constraint_seconds": 2.0},
            "global_valid_inequalities": {
                "ghost_aware_via_pole_feasibility": {
                    "conditioned_family_bound_formulation": "big_m",
                    "conditioned_family_upper_bound_constraints": 50,
                    "disabled_placements": 0,
                    "surviving_placements": 3,
                    "family_reduction_anchor_count": 3,
                }
            },
        }


def _write_patch_spec(path: Path, *, source_mutation_performed: bool = False) -> None:
    path.write_text(
        json.dumps(
            {
                "source_mutation_performed": source_mutation_performed,
                "interpretation": {
                    "source_mutation_authorized_by_this_artifact": False,
                },
                "recommendation": {
                    "action": "prepare_no_source_candidate_shape_inventory_comparison",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_inventory(
    path: Path,
    *,
    candidate_key: str,
    candidate_tuple: list[int],
    constraints: int = 1000,
    ghost_seconds: float = 10.0,
) -> None:
    path.write_text(
        json.dumps(
            {
                "run_id": "baseline",
                "status": "completed",
                "execute_no_solve": True,
                "target": {
                    "candidate_key": candidate_key,
                    "candidate_tuple": candidate_tuple,
                    "ghost_rect": {
                        "area": candidate_tuple[0],
                        "w": candidate_tuple[1],
                        "h": candidate_tuple[2],
                    },
                },
                "elapsed_seconds": 20.0,
                "inventory": {
                    "model_build_seconds": 12.0,
                    "session_core_build_seconds": 1.0,
                    "proto": {
                        "variable_count": 100,
                        "boolean_variable_count": 90,
                        "constraint_count": constraints,
                        "constraints_by_type": {"linear": constraints},
                    },
                    "build_stats_summary": {
                        "exact_core_reuse": {"ghost_constraint_seconds": ghost_seconds},
                        "global_valid_inequalities": {
                            "ghost_aware_via_pole_feasibility": {
                                "conditioned_family_bound_formulation": "big_m",
                                "conditioned_family_upper_bound_constraints": 700,
                                "disabled_placements": 0,
                                "surviving_placements": 3,
                                "family_reduction_anchor_count": 3,
                            }
                        },
                    },
                },
                "sensitive_path_comparison": {"changed": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_reduced_plan(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "wave": {
                    "selection_kind": "deterministic_frontier_bounded_wave_excluding_keys_v0",
                    "excluded_candidate_keys": ["42x32", "67x20"],
                    "entries": [
                        {
                            "candidate_key": "70x12",
                            "candidate": [840, 70, 12],
                            "selection_reason": "probe_head",
                        },
                        {
                            "candidate_key": "70x19",
                            "candidate": [1330, 70, 19],
                            "selection_reason": "prune_head",
                        },
                    ],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "29_candidate_shape_inventory_comparison"
    )
