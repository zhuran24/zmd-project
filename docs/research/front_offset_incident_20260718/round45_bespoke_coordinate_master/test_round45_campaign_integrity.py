"""Fail-closed campaign lifecycle and readback tests for Round 4/5."""

from __future__ import annotations

import copy
import json
import platform
import signal
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import run_campaign  # noqa: E402


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _model_identity(tag: str = "a") -> dict[str, Any]:
    return {
        "proto_sha256": tag * 64,
        "proto_size_bytes": 123,
        "variable_count": 10,
        "constraint_count": 20,
    }


def _valid_result_fixture(
    project_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    arm = dict(run_campaign.ARM_MATRIX[0])
    closure = run_campaign._closure_records(project_root)
    parameters = run_campaign._expected_solver_parameters(
        seed=int(arm["seed"]),
        time_limit_seconds=float(arm["time_limit_seconds"]),
    )
    environment = {
        "python_executable": run_campaign._python_executable(),
        "python_version": platform.python_version(),
        "ortools_version": __import__("ortools").__version__,
        "pythonhashseed": "0",
        "profile": run_campaign.PROFILE_NAME,
        "workers": 1,
        "seed": int(arm["seed"]),
    }
    prepared = {
        **_model_identity(),
        "oracle": {"passed": True, "status": "PASS"},
        "worker_environment": environment,
    }
    spec = {
        "campaign_id": "r45-" + "b" * 16,
        "campaign_spec_sha256": "b" * 64,
        "closure": closure,
        "workers": 1,
        "profile": run_campaign.PROFILE_NAME,
        "pythonhashseed": 0,
        "solver_contract": run_campaign._expected_solver_contract(),
        "launcher_environment": {
            "python_executable": run_campaign._python_executable(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    run_spec_sha256 = "c" * 64
    response_stats = "CpSolverResponse summary: status: UNKNOWN"
    result = {
        "schema_version": run_campaign.WORKER_SCHEMA_VERSION,
        "operation": "solve-arm",
        "worker_status": "SOLVER_RESULT",
        "ghost": {"w": int(arm["ghost_w"]), "h": int(arm["ghost_h"])},
        "seed": int(arm["seed"]),
        "workers": 1,
        "profile": run_campaign.PROFILE_NAME,
        "time_limit_seconds": float(arm["time_limit_seconds"]),
        "campaign_context": {
            "campaign_id": spec["campaign_id"],
            "campaign_spec_sha256": spec["campaign_spec_sha256"],
            "closure_sha256": closure["closure_sha256"],
            "run_key": arm["run_key"],
            "run_spec_sha256": run_spec_sha256,
            "closure": closure,
        },
        "model": {**_model_identity(), "validate_error": ""},
        "oracle": prepared["oracle"],
        "hard_tombstone": {"passed": True},
        "solve_gate": {"passed": True},
        "environment": dict(environment),
        "build_seconds": 1.0,
        "total_wall_seconds": 2.0,
        "solver": {
            "status": "UNKNOWN",
            "raw_status": 0,
            "process_wall_seconds": 1.0,
            "wall_time": 1.0,
            "user_time": 0.5,
            "deterministic_time": 0.25,
            "branches": 10,
            "conflicts": 1,
            "binary_propagations": 20,
            "integer_propagations": 30,
            "best_bound": 0.0,
            "response_stats": response_stats,
            "response_stats_sha256": run_campaign._sha256_bytes(response_stats.encode("utf-8")),
            "parameters": parameters,
            "strict_lean_configuration": {
                "profile": run_campaign.PROFILE_NAME,
                "expected_parameters": parameters,
                "requested_parameters": parameters,
                "actual_parameters": parameters,
                "unsupported_parameters": [],
            },
        },
        "solution": None,
        "solution_validation": None,
    }
    return spec, arm, prepared, run_spec_sha256, result


def test_complete_synthetic_unknown_result_passes_integrity(project_root: Path) -> None:
    spec, arm, prepared, run_spec_sha256, result = _valid_result_fixture(project_root)
    integrity = run_campaign._validate_solve_result(
        result=result,
        spec=spec,
        arm=arm,
        prepared=prepared,
        run_spec_sha256=run_spec_sha256,
        observed_closure=spec["closure"],
    )
    assert integrity["passed"] is True, integrity["errors"]


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    (
        (lambda result: result["campaign_context"].__setitem__("run_key", "wrong"), "campaign.context"),
        (lambda result: result["model"].__setitem__("proto_sha256", "d" * 64), "model.prepared_identity"),
        (lambda result: result.__setitem__("oracle", {"passed": False}), "oracle.passed"),
        (lambda result: result["environment"].__setitem__("pythonhashseed", "1"), "runtime.prepared_environment"),
        (
            lambda result: result["solver"]["strict_lean_configuration"].__setitem__(
                "unsupported_parameters", ["missing"]
            ),
            "solver.strict_configuration",
        ),
        (lambda result: result.__setitem__("solution", {}), "solver.solution_contract"),
    ),
)
def test_result_integrity_rejects_context_model_or_runtime_drift(
    project_root: Path,
    mutation: Callable[[dict[str, Any]], None],
    failed_check: str,
) -> None:
    spec, arm, prepared, run_spec_sha256, result = _valid_result_fixture(project_root)
    mutation(result)
    integrity = run_campaign._validate_solve_result(
        result=result,
        spec=spec,
        arm=arm,
        prepared=prepared,
        run_spec_sha256=run_spec_sha256,
        observed_closure=spec["closure"],
    )
    assert integrity["passed"] is False
    assert failed_check in integrity["errors"]


@pytest.mark.parametrize(
    ("returncode", "result", "events", "integrity", "expected"),
    (
        (0, {"schema_version": "x"}, {"oom_kill": 1}, {"passed": True}, "CGROUP_OOM_KILL"),
        (0, {"schema_version": "x"}, {"oom_kill": 0, "oom": 1}, {"passed": True}, "CGROUP_OOM_EVENT"),
        (-signal.SIGTERM, None, {"oom_kill": 0, "oom": 0}, None, "WORKER_SIGNAL_SIGTERM"),
        (7, None, {"oom_kill": 0, "oom": 0}, None, "PROCESS_NONZERO_EXIT"),
        (0, None, {"oom_kill": 0, "oom": 0}, None, "RESULT_MISSING_OR_INVALID"),
        (0, {"schema_version": "wrong"}, {"oom_kill": 0, "oom": 0}, {"passed": True}, "RESULT_SCHEMA_INVALID"),
        (
            0,
            {
                "schema_version": run_campaign.WORKER_SCHEMA_VERSION,
                "operation": "solve-arm",
                "worker_status": "SOLVER_RESULT",
                "solver": {"status": "INFEASIBLE"},
            },
            {"oom_kill": 0, "oom": 0},
            {"passed": False},
            "RESULT_INTEGRITY_INVALID",
        ),
    ),
)
def test_attempt_classification_is_fail_closed(
    returncode: int,
    result: dict[str, Any] | None,
    events: dict[str, int],
    integrity: dict[str, Any] | None,
    expected: str,
) -> None:
    terminal, _signal_name = run_campaign._classify_attempt(
        returncode=returncode,
        result=result,
        events_delta=events,
        result_integrity=integrity,
    )
    assert terminal == expected
    assert terminal not in run_campaign._CLEAN_TERMINALS


def test_unsupported_solver_parameter_is_a_hard_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Parameters:
        random_seed = 0
        num_search_workers = 0
        max_time_in_seconds = 0.0
        linearization_level = 0

    solver = SimpleNamespace(parameters=Parameters())

    def configure(**_kwargs: Any) -> dict[str, Any]:
        return run_campaign._expected_solver_parameters(seed=71, time_limit_seconds=600.0)

    monkeypatch.setattr(
        run_campaign,
        "_load_worker_apis",
        lambda: (None, configure, None, None, None, None),
    )
    with pytest.raises(run_campaign.CampaignError, match="does not support"):
        run_campaign._configure_solver(solver=solver, seed=71, time_limit_seconds=600.0)


def test_cgroup_contract_matches_owner_selected_hot_widening() -> None:
    contract = run_campaign._expected_cgroup_contract()
    assert contract["memory_high"] == "34G"
    assert contract["memory_high_bytes"] == 34 * 1024**3
    assert contract["memory_max"] == "38G"
    assert contract["memory_max_bytes"] == 38 * 1024**3
    assert contract["memory_swap_max"] == "16G"
    assert contract["memory_swap_max_bytes"] == 16 * 1024**3


def _summary_spec() -> dict[str, Any]:
    prepare_builds: dict[str, Any] = {}
    for anchor in run_campaign.PREPARE_ANCHORS:
        prepare_builds[str(anchor["anchor_key"])] = {
            **_model_identity(str(anchor["seed"])[-1]),
            "ghost_w": int(anchor["ghost_w"]),
            "ghost_h": int(anchor["ghost_h"]),
            "seed": int(anchor["seed"]),
        }
    return {
        "arms": [dict(arm) for arm in run_campaign.ARM_MATRIX],
        "prepare_builds": prepare_builds,
        "closure": {"closure_sha256": "e" * 64},
        "campaign_id": "r45-" + "f" * 16,
        "campaign_spec_sha256": "f" * 64,
        "semantic_label": run_campaign.SEMANTIC_LABEL,
        "git": {},
        "cgroup_contract": run_campaign._expected_cgroup_contract(),
    }


def _complete_attempt_for_arm(spec: dict[str, Any], arm: dict[str, Any]) -> dict[str, Any]:
    prepare_key = run_campaign._prepare_key(
        int(arm["ghost_w"]), int(arm["ghost_h"]), int(arm["seed"])
    )
    return {
        "attempt_id": "a01",
        "state": "COMPLETE",
        "terminal": {"clean": True},
        "integrity": {"passed": True},
        "result_model": run_campaign._model_identity(spec["prepare_builds"][prepare_key]),
        "result_closure_sha256": spec["closure"]["closure_sha256"],
    }


def test_summary_requires_all_six_identity_and_closure_gates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec = _summary_spec()
    attempts = {
        str(arm["run_key"]): [_complete_attempt_for_arm(spec, dict(arm))]
        for arm in run_campaign.ARM_MATRIX
    }
    monkeypatch.setattr(
        run_campaign,
        "_attempts_for_arm",
        lambda _root, arm, _spec: copy.deepcopy(attempts[str(arm["run_key"])]),
    )
    summary = run_campaign._campaign_summary(tmp_path, spec)
    assert summary["overall"]["status"] == "COMPLETE"
    assert summary["cross_checks"]["campaign_integrity_valid"] is True

    attempts[str(run_campaign.ARM_MATRIX[-1]["run_key"])][0]["result_closure_sha256"] = "0" * 64
    summary = run_campaign._campaign_summary(tmp_path, spec)
    assert summary["overall"]["status"] == "BLOCKED_RETRYABLE"
    assert summary["cross_checks"]["closure_same_all_arms"] is False

    attempts[str(run_campaign.ARM_MATRIX[-1]["run_key"])][0] = _complete_attempt_for_arm(
        spec, dict(run_campaign.ARM_MATRIX[-1])
    )
    attempts[str(run_campaign.ARM_MATRIX[-1]["run_key"])][0]["result_model"] = _model_identity("0")
    summary = run_campaign._campaign_summary(tmp_path, spec)
    assert summary["overall"]["status"] == "BLOCKED_RETRYABLE"
    assert summary["cross_checks"]["model_same_by_anchor"] is False


def test_orphan_resume_and_exclusive_write_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec = _summary_spec()
    arm = dict(run_campaign.ARM_MATRIX[0])
    attempt_dir = run_campaign._attempt_dir(tmp_path, arm, 1)
    attempt_dir.mkdir(parents=True)
    run_spec = {"unit_name": "fake.service", "run_spec_sha256": "a" * 64}
    (attempt_dir / "run_spec.json").write_text(json.dumps(run_spec), encoding="utf-8")
    (attempt_dir / "run_record.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run_campaign, "_active_units", lambda: [])
    attempts = run_campaign._attempts_for_arm(tmp_path, arm, spec)
    assert attempts[0]["state"] == "ORPHANED"
    assert run_campaign._next_attempt_number(attempts) == 2

    exclusive = tmp_path / "exclusive.json"
    run_campaign._write_json_exclusive(exclusive, {"first": True})
    with pytest.raises(run_campaign.CampaignError, match="refusing to overwrite"):
        run_campaign._write_json_exclusive(exclusive, {"second": True})
    assert json.loads(exclusive.read_text(encoding="utf-8")) == {"first": True}


def test_launch_retry_requires_explicit_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec = {
        **_summary_spec(),
        "project_root": str(tmp_path),
    }
    first_arm = dict(run_campaign.ARM_MATRIX[0])
    failed_attempt = {"attempt_id": "a01", "state": "FAILED"}
    summary = {
        "overall": {
            "status": "BLOCKED_RETRYABLE",
            "next_run_key": first_arm["run_key"],
        },
        "arms": [
            {
                **first_arm,
                "attempts": [failed_attempt],
            }
        ],
    }
    monkeypatch.setattr(run_campaign, "_load_spec", lambda _root: spec)
    monkeypatch.setattr(run_campaign, "_active_units", lambda: [])
    monkeypatch.setattr(run_campaign, "_active_solver_processes", lambda: [])
    monkeypatch.setattr(run_campaign, "_campaign_summary", lambda _root, _spec: summary)
    args = SimpleNamespace(
        campaign_root=tmp_path,
        retry_failed=False,
        dry_run=True,
    )
    with pytest.raises(run_campaign.CampaignError, match="--retry-failed"):
        run_campaign.command_launch_next(args)

    args.retry_failed = True
    assert run_campaign.command_launch_next(args) == run_campaign.EXIT_OK


def test_incomplete_summarize_preserves_exit_11(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(run_campaign, "_load_spec", lambda _root: _summary_spec())
    monkeypatch.setattr(
        run_campaign,
        "_campaign_summary",
        lambda _root, _spec: {"overall": {"status": "READY"}},
    )
    monkeypatch.setattr(run_campaign, "_write_json_atomic", lambda *_args, **_kwargs: None)
    args = SimpleNamespace(campaign_root=tmp_path)
    assert run_campaign.command_summarize(args) == run_campaign.EXIT_ACTIVE == 11
