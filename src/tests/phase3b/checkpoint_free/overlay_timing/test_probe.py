from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_phase3b_checkpoint_free_overlay_timing_probe import (
    OverlayTimingRecorder,
    _guard_forbidden_cli_args,
    _patch_runtime_timing_wrappers,
    build_or_run_overlay_timing_probe,
)


def test_overlay_timing_probe_plan_only_does_not_construct_model(tmp_path: Path) -> None:
    strategy = tmp_path / "strategy.json"
    output_dir = _output_dir(tmp_path)
    _write_strategy(strategy)

    def fail_session_factory(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("session factory should not be called in plan-only mode")

    payload = build_or_run_overlay_timing_probe(
        project_root=tmp_path,
        strategy_path=strategy,
        output_dir=output_dir,
        run_id="local_hotspot_42x32_overlay_timing_probe_plan_001",
        execute_no_solve=False,
        session_factory=fail_session_factory,
    )

    assert payload["status"] == "planned_only"
    assert payload["cp_solver_solve_called"] is False
    assert payload["checkpoint_written"] is False
    assert payload["runtime_execution_performed"] is False
    assert payload["target"]["candidate_key"] == "42x32"
    artifact_dir = output_dir / "local_hotspot_42x32_overlay_timing_probe_plan_001"
    assert (artifact_dir / "overlay_timing_probe_plan.json").exists()
    assert (artifact_dir / "overlay_timing_probe.json").exists()


def test_overlay_timing_probe_execute_no_solve_with_fakes(tmp_path: Path) -> None:
    strategy = tmp_path / "strategy.json"
    output_dir = _output_dir(tmp_path)
    _write_strategy(strategy)
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

    payload = build_or_run_overlay_timing_probe(
        project_root=tmp_path,
        strategy_path=strategy,
        output_dir=output_dir,
        run_id="local_hotspot_42x32_overlay_timing_probe_001",
        execute_no_solve=True,
        session_factory=fake_session_factory,
        precheck_factory=fake_precheck_factory,
        model_factory=fake_model_factory,
        use_runtime_wrappers=False,
    )

    assert calls == ["session", "precheck", "model"]
    assert payload["status"] == "completed"
    assert payload["no_solve"] is True
    assert payload["cp_solver_solve_called"] is False
    assert payload["checkpoint_written"] is False
    assert payload["source_model_mutation"] is False
    assert payload["runtime_execution_performed"] is False
    assert payload["sensitive_path_comparison"]["changed"] is False
    assert payload["inventory"]["proto"]["constraint_count"] == 3
    assert payload["timing"]["from_exact_core_total_seconds"] >= 0.0


def test_overlay_timing_probe_rejects_non_42x32(tmp_path: Path) -> None:
    strategy = tmp_path / "strategy.json"
    _write_strategy(strategy)

    with pytest.raises(ValueError, match="only allows candidate_key=42x32"):
        build_or_run_overlay_timing_probe(
            project_root=tmp_path,
            strategy_path=strategy,
            output_dir=_output_dir(tmp_path),
            candidate_key="67x20",
            execute_no_solve=False,
        )


def test_overlay_timing_probe_cli_guard_rejects_forbidden_args() -> None:
    for arg in ["--resume-campaign", "--import-checkpoint", "--proof-source", "168h"]:
        with pytest.raises(ValueError, match="forbidden"):
            _guard_forbidden_cli_args([arg])


def test_overlay_timing_probe_runtime_wrapper_records_and_restores_methods() -> None:
    calls: list[str] = []

    class FakeDelegate:
        def _add_ghost_constraints(self):
            calls.append("ghost")

        def _apply_ghost_anchor_power_capacity_screen(self):
            calls.append("via")

    class FakeCpModel:
        def AddExactlyOne(self, values):
            calls.append(f"exactly_one:{len(values)}")

    def fake_rebuild(model, add_search_guidance):
        calls.append("rebuild")
        add_search_guidance()
        return {"rebuilt_after_ghost_overlay": True}

    module = SimpleNamespace(_rebuild_exact_core_overlay_search_guidance=fake_rebuild)
    original_delegate = FakeDelegate._add_ghost_constraints
    recorder = OverlayTimingRecorder()

    with _patch_runtime_timing_wrappers(
        recorder,
        delegate_cls=FakeDelegate,
        master_module=module,
        cp_model_cls=FakeCpModel,
    ):
        delegate = FakeDelegate()
        delegate._add_ghost_constraints()
        delegate._apply_ghost_anchor_power_capacity_screen()
        FakeCpModel().AddExactlyOne([1, 2])
        module._rebuild_exact_core_overlay_search_guidance(object(), lambda: calls.append("guidance"))

    assert FakeDelegate._add_ghost_constraints is original_delegate
    phases = {row["phase"]: row for row in recorder.snapshot()}
    assert phases["CoordinateExactMasterDelegate._add_ghost_constraints"]["calls"] == 1
    assert phases["CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen"]["calls"] == 1
    assert phases["CpModel.AddExactlyOne"]["calls"] == 1
    assert phases["_rebuild_exact_core_overlay_search_guidance"]["calls"] == 1
    assert calls == ["ghost", "via", "exactly_one:2", "rebuild", "guidance"]


def test_overlay_timing_probe_disqualifies_sensitive_path_mutation(tmp_path: Path) -> None:
    strategy = tmp_path / "strategy.json"
    _write_strategy(strategy)

    def mutating_model_factory(*args, **kwargs):
        checkpoint_dir = tmp_path / "data" / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (checkpoint_dir / "exact_campaign_state.json").write_text("{}\n", encoding="utf-8")
        return FakeMasterModel()

    payload = build_or_run_overlay_timing_probe(
        project_root=tmp_path,
        strategy_path=strategy,
        output_dir=_output_dir(tmp_path),
        run_id="local_hotspot_42x32_signature_bucket_inst_no_solve_001",
        execute_no_solve=True,
        session_factory=lambda *args, **kwargs: FakeSession(),
        precheck_factory=lambda **kwargs: {"triggered": False, "boundary_port_precheck": {"evaluated": True}},
        model_factory=mutating_model_factory,
        use_runtime_wrappers=False,
    )

    assert payload["status"] == "disqualified_sensitive_path_mutation"
    assert payload["sensitive_path_comparison"]["changed"] is True


def test_overlay_timing_probe_rejects_bad_namespace(tmp_path: Path) -> None:
    strategy = tmp_path / "strategy.json"
    _write_strategy(strategy)

    with pytest.raises(ValueError, match="outside artifact namespace"):
        build_or_run_overlay_timing_probe(
            project_root=tmp_path,
            strategy_path=strategy,
            output_dir=tmp_path / "bad",
            execute_no_solve=False,
        )


def test_overlay_timing_probe_rejects_traversal_output_dir_before_write(tmp_path: Path) -> None:
    strategy = tmp_path / "strategy.json"
    _write_strategy(strategy)
    bad_output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "35_overlay_timing_strategy"
        / ".."
        / ".."
        / ".."
        / "data"
        / "checkpoints"
    )

    with pytest.raises(ValueError, match="outside artifact namespace"):
        build_or_run_overlay_timing_probe(
            project_root=tmp_path,
            strategy_path=strategy,
            output_dir=bad_output_dir,
            run_id="local_hotspot_42x32_overlay_timing_probe_plan_001",
            execute_no_solve=False,
        )

    assert not (tmp_path / "data" / "checkpoints").exists()


def test_overlay_timing_probe_rejects_bad_run_ids_before_write(tmp_path: Path) -> None:
    strategy = tmp_path / "strategy.json"
    output_dir = _output_dir(tmp_path)
    _write_strategy(strategy)

    for run_id, expected in [
        ("../../../data/checkpoints/pwn", "Invalid artifact run_id"),
        ("local_hotspot_42x32_unapproved_no_solve_999", "ALLOWED_OVERLAY_TIMING_RUN_IDS"),
    ]:
        with pytest.raises(ValueError, match=expected):
            build_or_run_overlay_timing_probe(
                project_root=tmp_path,
                strategy_path=strategy,
                output_dir=output_dir,
                run_id=run_id,
                execute_no_solve=False,
            )

    assert not output_dir.exists()
    assert not (tmp_path / "data" / "checkpoints").exists()


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


class FakeCpModel:
    def Proto(self) -> FakeProto:
        return FakeProto()


class FakeMasterModel:
    model = FakeCpModel()
    build_stats = {
        "exact_core_reuse": {
            "overlay_build_seconds": 2.0,
            "ghost_constraint_seconds": 1.5,
            "rebuilt_search_strategy_count": 4,
        },
        "ghost_rect": {"enabled": True},
    }


def _write_strategy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "target": {
                    "candidate_key": "42x32",
                    "candidate_tuple": [1344, 42, 32],
                    "ghost_rect": {"w": 42, "h": 32, "area": 1344},
                },
                "interpretation": {"classification": "broader_overlay_timing_required"},
                "recommendation": {"action": "run_single_42x32_wrapper_no_solve_overlay_timing_probe"},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _output_dir(root: Path) -> Path:
    return root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "35_overlay_timing_strategy"
