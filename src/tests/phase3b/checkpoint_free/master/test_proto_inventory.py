from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.master.build_proto_inventory import (
    build_or_run_master_proto_inventory,
)


def test_master_proto_inventory_plan_only_does_not_construct_model(tmp_path: Path) -> None:
    strategy_path = tmp_path / "strategy.json"
    output_dir = _output_dir(tmp_path)
    _write_strategy(strategy_path)

    def fail_session_factory(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("session factory should not be called in plan-only mode")

    payload = build_or_run_master_proto_inventory(
        project_root=tmp_path,
        strategy_path=strategy_path,
        output_dir=output_dir,
        run_id="plan_only",
        execute_no_solve=False,
        session_factory=fail_session_factory,
    )

    assert payload["status"] == "planned_only"
    assert payload["cp_solver_solve_called"] is False
    assert payload["target"]["candidate_key"] == "42x32"
    assert (output_dir / "plan_only" / "master_proto_inventory_plan.json").exists()
    assert (output_dir / "plan_only" / "master_proto_inventory.json").exists()


def test_master_proto_inventory_execute_no_solve_with_fakes(tmp_path: Path) -> None:
    strategy_path = tmp_path / "strategy.json"
    output_dir = _output_dir(tmp_path)
    _write_strategy(strategy_path)
    calls: list[str] = []

    def fake_session_factory(*args, **kwargs):
        calls.append("session")
        return FakeSession()

    def fake_precheck_factory(**kwargs):
        calls.append("precheck")
        assert kwargs["ghost_w"] == 42
        assert kwargs["ghost_h"] == 32
        return {"triggered": False, "boundary_port_precheck": {"evaluated": True}}

    def fake_model_factory(*args, **kwargs):
        calls.append("model")
        assert kwargs["ghost_rect"] == (42, 32)
        return FakeMasterModel()

    payload = build_or_run_master_proto_inventory(
        project_root=tmp_path,
        strategy_path=strategy_path,
        output_dir=output_dir,
        run_id="fake_exec",
        execute_no_solve=True,
        session_factory=fake_session_factory,
        precheck_factory=fake_precheck_factory,
        model_factory=fake_model_factory,
    )

    assert calls == ["session", "precheck", "model"]
    assert payload["status"] == "completed"
    assert payload["cp_solver_solve_called"] is False
    assert payload["checkpoint_written"] is False
    proto = payload["inventory"]["proto"]
    assert proto["variable_count"] == 3
    assert proto["boolean_variable_count"] == 2
    assert proto["constraint_count"] == 3
    assert proto["constraints_by_type"] == {"bool_or": 1, "linear": 2}
    assert payload["sensitive_path_comparison"]["changed"] is False


def test_master_proto_inventory_rejects_bad_namespace(tmp_path: Path) -> None:
    strategy_path = tmp_path / "strategy.json"
    _write_strategy(strategy_path)

    with pytest.raises(ValueError, match="outside master proto inventory namespace"):
        build_or_run_master_proto_inventory(
            project_root=tmp_path,
            strategy_path=strategy_path,
            output_dir=tmp_path / "bad",
            execute_no_solve=False,
        )


def test_master_proto_inventory_classifies_ortools_style_has_methods(tmp_path: Path) -> None:
    strategy_path = tmp_path / "strategy.json"
    output_dir = _output_dir(tmp_path)
    _write_strategy(strategy_path)

    class HasMethodMasterModel(FakeMasterModel):
        model = FakeHasMethodCpModel()

    payload = build_or_run_master_proto_inventory(
        project_root=tmp_path,
        strategy_path=strategy_path,
        output_dir=output_dir,
        run_id="has_method_exec",
        execute_no_solve=True,
        session_factory=lambda *args, **kwargs: FakeSession(),
        precheck_factory=lambda **kwargs: {"triggered": False, "boundary_port_precheck": {"evaluated": True}},
        model_factory=lambda *args, **kwargs: HasMethodMasterModel(),
    )

    assert payload["status"] == "completed"
    assert payload["inventory"]["proto"]["constraints_by_type"] == {
        "bool_or": 1,
        "linear": 2,
        "at_most_one": 1,
    }


class FakeSession:
    project_root = Path(".")
    master_search_profile = "default"
    core_build_seconds = 1.25
    core = object()


class FakeVariable:
    def __init__(self, domain: list[int]) -> None:
        self.domain = domain


class FakeConstraint:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def WhichOneof(self, _name: str) -> str:
        return self.kind


class FakeProto:
    variables = [FakeVariable([0, 1]), FakeVariable([0, 100]), FakeVariable([0, 1])]
    constraints = [FakeConstraint("linear"), FakeConstraint("bool_or"), FakeConstraint("linear")]
    objective = None


class FakeHasMethodConstraint:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def __getattr__(self, name: str):
        if name.startswith("has_"):
            return lambda: name == f"has_{self.kind}"
        raise AttributeError(name)


class FakeHasMethodProto:
    variables = [FakeVariable([0, 1])]
    constraints = [
        FakeHasMethodConstraint("linear"),
        FakeHasMethodConstraint("bool_or"),
        FakeHasMethodConstraint("at_most_one"),
        FakeHasMethodConstraint("linear"),
    ]
    objective = None


class FakeCpModel:
    def Proto(self) -> FakeProto:
        return FakeProto()


class FakeHasMethodCpModel:
    def Proto(self) -> FakeHasMethodProto:
        return FakeHasMethodProto()


class FakeMasterModel:
    model = FakeCpModel()
    build_stats = {
        "exact_core_reuse": {"overlay_build_seconds": 2.0},
        "ghost_rect": {"enabled": True},
        "greedy_hint": {"hinted_literals": 8},
    }


def _write_strategy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "target": {
                    "candidate_key": "42x32",
                    "candidate_tuple": [1344, 42, 32],
                    "ghost_rect": {"w": 42, "h": 32, "area": 1344},
                    "run_id": "source_run",
                },
                "interpretation": {
                    "classification": "master_model_size_reduction_required_before_more_42x32_runtime",
                },
                "recommendation": {
                    "action": "prepare_no_solve_master_proto_inventory",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _output_dir(root: Path) -> Path:
    return root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "24_master_proto_inventory"
