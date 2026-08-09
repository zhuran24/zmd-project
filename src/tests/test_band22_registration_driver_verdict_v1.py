"""Regression guards for the band22 registration driver's verdict + containment.

The driver ingests an external witness layout into the official binding/routing
gates. Two classes of defect are guarded here, both caught in the 2026-08-05
adversarial review:

1. verdict laundering — the driver used to classify from the inner
   binding/routing statuses alone, so the official fail-closed ``UNKNOWN``
   returns of ``LBBDController._run_exact_binding_and_routing`` (power-pole
   normalization failure with both gates FEASIBLE; a whole-layout nogood
   refused because the independent re-verifier did not confirm) were reported
   as conclusive BOTH_GATES_FEASIBLE / BINDING_INFEASIBLE /
   ROUTING_REJECTED_ALL_BINDINGS verdicts.
2. output escape — an arbitrary ``--out-dir`` or a ``--tag`` containing ``..``
   could place writes (and unlinks) inside ``data/checkpoints`` /
   ``data/solutions``.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER_PATH = (
    ROOT / "docs/research/band22_registration_20260805/registration_driver.py"
)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver() -> ModuleType:
    assert DRIVER_PATH.exists(), DRIVER_PATH
    return _load("band22_registration_driver_under_test", DRIVER_PATH)


def _classify(driver: ModuleType, **overrides):
    kwargs = {
        "controller_status": "UNKNOWN",
        "gate_returned_solution": False,
        "proof_summary": {},
        "binding_seconds": 600.0,
        "routing_seconds": 600.0,
        "harness_exception": None,
        "wall_clock_censored_at": None,
        "master_validation": {"confirmed": True, "status": "FEASIBLE"},
    }
    kwargs.update(overrides)
    return driver.classify_verdict(**kwargs)


# --- the three review counterexamples --------------------------------------
def test_unknown_with_both_gates_feasible_is_not_a_positive(driver: ModuleType) -> None:
    """benders_loop returns UNKNOWN when power-pole normalization fails even
    though binding and routing both report FEASIBLE."""
    verdict = _classify(
        driver,
        controller_status="UNKNOWN",
        gate_returned_solution=False,
        proof_summary={
            "binding_status": "FEASIBLE",
            "routing_status": "FEASIBLE",
            "stage": "power_pole_dominance_normalization",
            "master_follow_up": "fail_closed_unknown",
        },
    )
    assert verdict["verdict"] != "BOTH_GATES_FEASIBLE"
    assert verdict["verdict"].startswith("UNKNOWN")


def test_unknown_with_binding_infeasible_is_not_a_negative(driver: ModuleType) -> None:
    """binding INFEASIBLE + refused whole-layout nogood returns UNKNOWN."""
    verdict = _classify(
        driver,
        controller_status="UNKNOWN",
        proof_summary={
            "binding_status": "INFEASIBLE",
            "master_follow_up": "fail_closed_unknown",
        },
    )
    assert verdict["verdict"] != "BINDING_INFEASIBLE"
    assert verdict["verdict"].startswith("UNKNOWN")


def test_unknown_with_routing_all_infeasible_is_not_a_negative(
    driver: ModuleType,
) -> None:
    verdict = _classify(
        driver,
        controller_status="UNKNOWN",
        proof_summary={
            "binding_status": "EXHAUSTED",
            "routing_status": "ALL_INFEASIBLE",
            "master_follow_up": "fail_closed_unknown",
        },
    )
    assert verdict["verdict"] != "ROUTING_REJECTED_ALL_BINDINGS"
    assert verdict["verdict"].startswith("UNKNOWN")


# --- the positive/negative paths that ARE allowed ---------------------------
def test_certified_with_returned_solution_is_the_only_positive(
    driver: ModuleType,
) -> None:
    proof = {"binding_status": "FEASIBLE", "routing_status": "FEASIBLE"}
    good = _classify(
        driver,
        controller_status="CERTIFIED",
        gate_returned_solution=True,
        proof_summary=proof,
    )
    assert good["verdict"] == "BOTH_GATES_FEASIBLE"
    assert good["censored"] is False

    no_solution = _classify(
        driver,
        controller_status="CERTIFIED",
        gate_returned_solution=False,
        proof_summary=proof,
    )
    assert no_solution["verdict"] == "UNKNOWN_OTHER"


def test_positive_requires_master_validation(driver: ModuleType) -> None:
    verdict = _classify(
        driver,
        controller_status="CERTIFIED",
        gate_returned_solution=True,
        proof_summary={"binding_status": "FEASIBLE", "routing_status": "FEASIBLE"},
        master_validation={"confirmed": False, "status": "SKIPPED_BY_FLAG"},
    )
    assert verdict["verdict"] == "UNKNOWN_LAYOUT_NOT_MASTER_VALIDATED"


def test_negative_requires_confirmed_independent_reverifier(
    driver: ModuleType,
) -> None:
    confirmed = _classify(
        driver,
        controller_status="master_cut_added_continue",
        proof_summary={
            "binding_status": "INFEASIBLE",
            "independent_infeasibility_reverifier": {"confirmed": True},
        },
    )
    assert confirmed["verdict"] == "BINDING_INFEASIBLE"

    unconfirmed = _classify(
        driver,
        controller_status="master_cut_added_continue",
        proof_summary={
            "binding_status": "INFEASIBLE",
            "independent_infeasibility_reverifier": {"confirmed": False},
        },
    )
    assert unconfirmed["verdict"] == "UNKNOWN_OTHER"


def test_status_contract_violation_blocks_every_conclusion(
    driver: ModuleType,
) -> None:
    verdict = _classify(
        driver,
        controller_status="CERTIFIED",
        gate_returned_solution=True,
        proof_summary={
            "binding_status": "FEASIBLE",
            "routing_status": "FEASIBLE",
            "subproblem_status_contract_violation": "binding_status_unexpected",
        },
    )
    assert verdict["verdict"] == "UNKNOWN_STATUS_CONTRACT_VIOLATION"


# --- censoring is only for real budget stops --------------------------------
def test_binding_timeout_with_model_invalid_is_not_a_budget_censor(
    driver: ModuleType,
) -> None:
    verdict = _classify(
        driver,
        proof_summary={
            "binding_status": "TIMEOUT",
            "binding_summary": {"solver_status": "MODEL_INVALID"},
        },
    )
    assert verdict["verdict"] == "UNKNOWN_STATUS_CONTRACT_VIOLATION"
    assert verdict["censored"] is False


def test_binding_timeout_with_unknown_solver_status_is_censored(
    driver: ModuleType,
) -> None:
    verdict = _classify(
        driver,
        proof_summary={
            "binding_status": "TIMEOUT",
            "binding_summary": {"solver_status": "UNKNOWN"},
        },
    )
    assert verdict["verdict"] == "UNKNOWN_CENSORED"
    assert verdict["censored"] is True
    assert verdict["censored_stage"] == "binding"


def test_harness_exception_and_wall_clock_dominate(driver: ModuleType) -> None:
    assert (
        _classify(driver, harness_exception="RuntimeError: boom")["verdict"]
        == "HARNESS_ERROR"
    )
    censored = _classify(driver, wall_clock_censored_at=120.0)
    assert censored["verdict"] == "UNKNOWN_CENSORED"
    assert censored["censored_stage"] == "driver_wall_clock"


# --- output containment -----------------------------------------------------
@pytest.mark.parametrize(
    "tag",
    ["../../data/checkpoints/a", "../x", "a/b", "", ".", "..", "a" * 100],
)
def test_tag_must_be_a_strict_leaf_name(driver: ModuleType, tag: str) -> None:
    run_dir, error = driver._resolve_run_dir(driver.OUT_ROOT, tag)
    assert run_dir is None
    assert error


def test_out_dir_outside_the_artifact_root_is_rejected(
    driver: ModuleType, tmp_path: Path
) -> None:
    for candidate in (
        ROOT / "data" / "checkpoints",
        ROOT / "data" / "solutions",
        tmp_path,
    ):
        run_dir, error = driver._resolve_run_dir(candidate, "run")
        assert run_dir is None, candidate
        assert error


def test_run_dir_is_fresh_and_contained(driver: ModuleType) -> None:
    run_dir, error = driver._resolve_run_dir(driver.OUT_ROOT, "pytest.containment")
    assert error is None and run_dir is not None
    try:
        assert run_dir.is_dir()
        assert not any(run_dir.iterdir())
        assert run_dir.resolve().is_relative_to(driver.OUT_ROOT.resolve())
    finally:
        run_dir.rmdir()


# --- truncation is recorded, never silent -----------------------------------
def test_list_truncation_is_explicit(driver: ModuleType) -> None:
    coerced = driver._jsonable({"xs": list(range(500))})
    assert coerced["xs"]["__truncated__"] == "max_list"
    assert coerced["xs"]["original_length"] == 500
    assert coerced["xs"]["kept"] == 200

    untruncated = driver._jsonable({"xs": list(range(500))}, max_list=None)
    assert untruncated["xs"] == list(range(500))
