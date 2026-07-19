"""Targeted non-solving regressions for the rebuilt Round 4/5 prototype.

These tests may construct CP-SAT models, but they must never call ``Solve``.
Set ``ROUND45_PROJECT_ROOT`` when the pinned live inputs are outside this
checkout (for example, ``/home/zhuran24/zmd-pj`` during the reconstruction).
"""

from __future__ import annotations

import copy
import os
import signal
import sys
from pathlib import Path
from typing import Any

import pytest


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import compact_model  # noqa: E402
import independent_oracle  # noqa: E402
import run_campaign  # noqa: E402


EXPECTED_POOL_COUNTS = {
    "boundary_storage_port": 136,
    "manufacturing_3x3": 17_952,
    "manufacturing_5x5": 16_896,
    "manufacturing_6x4": 16_900,
    "power_pole": 4_761,
    "protocol_core": 7_688,
    "protocol_storage_box": 18_496,
}


@pytest.fixture(scope="session")
def project_root() -> Path:
    default_root = Path(__file__).resolve().parents[4]
    root = Path(os.environ.get("ROUND45_PROJECT_ROOT", default_root)).resolve()
    required = root / "data/preprocessed/candidate_placements.json"
    assert required.is_file(), f"missing pinned candidate pool: {required}"
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(1, root_text)
    return root


@pytest.fixture(scope="session")
def oracle_result(project_root: Path) -> dict[str, Any]:
    result = independent_oracle.run_independent_oracle(project_root)
    assert result["status"] == "PASS", result.get("errors")
    assert result["ok"] is True
    assert result["certificate_eligible"] is True
    return result


def test_independent_oracle_passes_pinned_counts(oracle_result: dict[str, Any]) -> None:
    contract = oracle_result["oracle_contract"]
    assert contract["pool_total"] == 82_829
    assert contract["mode_total"] == 21
    assert contract["pool_counts"] == EXPECTED_POOL_COUNTS
    assert contract["mandatory_instances"] == 266
    assert contract["mandatory_groups"] == 19
    assert contract["mandatory_powered"] == 219
    assert contract["mandatory_area"] == 3_544
    assert contract["routing_in"] == 312
    assert contract["routing_out"] == 316
    assert contract["routing_total"] == 628
    assert len(contract["operation_front_ledger"]) == 19
    assert contract["operation_front_ledger"]["protocol_core"] == {
        "facility_type": "protocol_core",
        "concrete_inputs": 0,
        "concrete_outputs": 0,
        "generic_input_capacity": 14,
        "generic_output_capacity": 6,
        "modeled_input_witnesses": 0,
        "modeled_output_witnesses": 6,
    }
    assert contract["generic_route_contract"]["mandatory_outputs_saturate"] is True
    assert contract["max_box_slots"] == 2
    assert contract["max_pole_slots"] == 221
    assert contract["max_body_slots"] == 489
    assert contract["front_body_reference_count"] == 307_092
    assert len(contract["mode_domains"]) == 21
    assert oracle_result["errors"] == []
    assert all(check["ok"] is True for check in oracle_result["checks"])


@pytest.mark.parametrize(
    ("ghost_w", "ghost_h", "expected_anchor_count"),
    ((7, 7, 4_096), (6, 8, 4_095), (8, 6, 4_095)),
)
def test_anchor_build_validates_and_matches_oracle(
    project_root: Path,
    oracle_result: dict[str, Any],
    ghost_w: int,
    ghost_h: int,
    expected_anchor_count: int,
) -> None:
    build = compact_model.build_compact_model(project_root, ghost_w, ghost_h)

    assert build.model.Validate() == ""
    assert build.audit["vars"] > 0
    assert build.audit["constraints"] > 0
    assert build.audit["oracle_contract"]["ghost_anchor_count"] == expected_anchor_count

    comparison = independent_oracle.compare_oracle_to_build(
        oracle_result,
        build.audit,
        ghost_w,
        ghost_h,
        model=build.model,
    )
    assert comparison["status"] == "PASS", comparison["errors"]
    assert comparison["ok"] is True
    assert comparison["certificate_eligible"] is True
    assert comparison["errors"] == []
    assert all(item["ok"] is True for item in comparison["comparisons"])


def test_mode_token_canonicalizes_integer_and_string_orientation_equally(
    project_root: Path,
) -> None:
    from src.models.exact_coordinate_master import CoordinateExactMasterDelegate

    integer_pose = {
        "pose_id": "synthetic_int_orientation",
        "anchor": {"x": 10, "y": 20},
        "pose_params": {"orientation": 0, "port_mode": "TB"},
        "occupied_cells": [{"x": 10, "y": 20}],
    }
    string_pose = {
        **integer_pose,
        "pose_id": "synthetic_string_orientation",
        "pose_params": {"orientation": "0", "port_mode": "TB"},
    }

    delegate = object.__new__(CoordinateExactMasterDelegate)
    compact_integer = compact_model._mode_token(integer_pose)
    compact_string = compact_model._mode_token(string_pose)
    production_integer = delegate._pose_mode_token(integer_pose)
    production_string = delegate._pose_mode_token(string_pose)

    expected = ("0", "TB", "footprint::0:0:0:0::0:0")
    assert compact_integer == compact_string == expected
    assert production_integer == production_string == expected
    assert compact_integer == production_integer


def test_identity_front_edge_oob_pose_counts(oracle_result: dict[str, Any]) -> None:
    identity = oracle_result["identity_front"]
    expected = {"protocol_core": 488, "protocol_storage_box": 544}

    assert identity["semantics"] == "stored_port_identity"
    assert identity["identity_sentinel_pass"] is True
    assert identity["out_of_grid_pose_counts"] == expected
    assert oracle_result["oracle_contract"]["edge_oob_pose_counts"] == expected


def test_strict_lean_solver_profile_is_exact_and_single_worker() -> None:
    from ortools.sat.python import cp_model

    solver = cp_model.CpSolver()
    configured = compact_model.configure_strict_lean(
        solver,
        time_limit=600.0,
        seed=71,
        workers=1,
    )
    expected = {
        "max_time_in_seconds": 600.0,
        "num_search_workers": 1,
        "random_seed": 71,
        "log_search_progress": True,
        "log_to_stdout": False,
        "max_memory_in_mb": 10_000,
        "cp_model_probing_level": 0,
        "probing_deterministic_time_limit": 0.05,
        "max_presolve_iterations": 1,
        "linearization_level": 0,
        "merge_no_overlap_work_limit": 0.0,
    }
    assert configured == expected
    for name, value in expected.items():
        if hasattr(solver.parameters, name):
            assert getattr(solver.parameters, name) == value

    with pytest.raises(ValueError, match="one-worker"):
        compact_model.configure_strict_lean(solver, time_limit=600.0, seed=71, workers=2)


def test_oracle_comparison_requires_explicit_certificate_eligibility(
    oracle_result: dict[str, Any],
) -> None:
    rejected_oracle = copy.deepcopy(oracle_result)
    rejected_oracle["certificate_eligible"] = False
    build_contract = {
        **copy.deepcopy(oracle_result["oracle_contract"]),
        "ghost_w": 7,
        "ghost_h": 7,
        "ghost_anchor_count": 4_096,
    }

    comparison = independent_oracle.compare_oracle_to_build(
        rejected_oracle,
        {"oracle_contract": build_contract},
        7,
        7,
    )
    assert comparison["status"] == "MISMATCH"
    assert comparison["ok"] is False
    assert any(
        error["check"] == "oracle.certificate_eligible"
        for error in comparison["errors"]
    )


def test_oracle_comparison_requires_real_proto_topology(
    oracle_result: dict[str, Any],
) -> None:
    build_contract = {
        **copy.deepcopy(oracle_result["oracle_contract"]),
        "ghost_w": 7,
        "ghost_h": 7,
        "ghost_anchor_count": 4_096,
    }
    comparison = independent_oracle.compare_oracle_to_build(
        oracle_result,
        {"oracle_contract": build_contract},
        7,
        7,
        model=None,
    )
    assert comparison["status"] == "MISMATCH"
    assert comparison["certificate_eligible"] is False
    assert any(error["check"] == "model.proto_topology" for error in comparison["errors"])


def test_proto_topology_rejects_an_extra_overstrict_constraint(
    project_root: Path,
    oracle_result: dict[str, Any],
) -> None:
    build = compact_model.build_compact_model(project_root, 7, 7)
    build.model.Add(0 == 1)
    comparison = independent_oracle.compare_oracle_to_build(
        oracle_result,
        build.audit,
        7,
        7,
        model=build.model,
    )
    assert comparison["status"] == "MISMATCH"
    topology = comparison["proto_topology"]
    assert topology["certificate_eligible"] is False
    failed = {check["name"] for check in topology["checks"] if check["ok"] is False}
    assert "proto.constraint_count_exact" in failed
    assert "proto.constraint_histogram_exact" in failed


def test_proto_record_supports_runtime_pybind_proto() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    model.NewBoolVar("x")
    record = run_campaign._proto_record(model)

    assert record["proto_sha256"]
    assert record["proto_size_bytes"] > 0
    assert record["variable_count"] == 1
    assert record["constraint_count"] == 0
    assert record["validate_error"] == ""


def test_sigsegv_attempt_is_never_classified_clean() -> None:
    apparently_clean_result = {
        "worker_status": "SOLVER_RESULT",
        "solver": {"status": "INFEASIBLE"},
    }
    terminal, signal_name = run_campaign._classify_attempt(
        returncode=-signal.SIGSEGV,
        result=apparently_clean_result,
        events_delta={"oom_kill": 0},
    )

    assert terminal == "WORKER_SIGNAL_SIGSEGV"
    assert signal_name == "SIGSEGV"
    assert terminal not in run_campaign._CLEAN_TERMINALS


def test_campaign_digest_excludes_creation_timestamp() -> None:
    first = {
        "schema_version": run_campaign.SCHEMA_VERSION,
        "semantic_label": run_campaign.SEMANTIC_LABEL,
        "created_at_utc": "2026-07-19T00:00:00+00:00",
    }
    second = {
        **first,
        "created_at_utc": "2026-07-19T00:00:01+00:00",
    }

    first_sealed = run_campaign._seal_spec(first)
    second_sealed = run_campaign._seal_spec(second)
    assert "created_at_utc" not in run_campaign._spec_base(first_sealed)
    assert run_campaign._spec_base(first_sealed) == run_campaign._spec_base(second_sealed)
    assert first_sealed["campaign_spec_sha256"] == second_sealed["campaign_spec_sha256"]
    assert first_sealed["campaign_id"] == second_sealed["campaign_id"]
