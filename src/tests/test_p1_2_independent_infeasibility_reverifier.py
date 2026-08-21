"""Contracts for the closed-world whole-layout binding re-verifier."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

import pytest

from scripts import check_p1_2_proof_obligations
from src.models.binding_subproblem import PortBindingModel
from src.search import benders_loop
from src.search.benders_loop import LBBDController
from src.search.independent_binding_reverify import transport
from src.search.independent_binding_reverify.artifacts import load_authority_artifacts
from src.search.independent_binding_reverify.certificate import verify_binding_certificate
from src.search.independent_binding_reverify.protocol import (
    STATUS_CONFIRMED_INFEASIBLE,
    STATUS_DIVERGED_FEASIBLE,
    STATUS_TIMEOUT,
    STATUS_UNKNOWN,
    canonical_digest,
)
from src.search.independent_binding_reverify.semantics import build_semantic_model
from src.search.independent_binding_reverify.theorem import build_binding_certificate
from src.search.independent_infeasibility_reverifier import (
    INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
    INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
    REVERIFY_STATUS_CONFIRMED_INFEASIBLE,
    REVERIFY_STATUS_DIVERGED_FEASIBLE,
    REVERIFY_STATUS_TIMEOUT,
    REVERIFY_STATUS_UNKNOWN,
    IndependentInfeasibilityReverificationVerdict,
    reverify_whole_layout_infeasibility,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = PROJECT_ROOT / "src" / "search" / "independent_binding_reverify"
_ARTIFACT_RELPATHS = {
    "canonical_rules": "rules/canonical_rules.json",
    "preprocess_plan": "rules/preprocess_plan.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _port_cells(count: int, *, y: int, direction: str) -> list[dict[str, Any]]:
    return [{"x": index, "y": y, "dir": direction} for index in range(count)]


def _artifact_hashes(root: Path) -> dict[str, str]:
    return {
        key: hashlib.sha256((root / relpath).read_bytes()).hexdigest()
        for key, relpath in _ARTIFACT_RELPATHS.items()
    }


def _semantics_contract(
    *,
    input_slots: Mapping[str, int],
    output_slots: Mapping[str, int],
    utility_operations: Mapping[str, str],
    source_rejected_selection_count: int = 0,
    routing_context_enabled: bool = False,
    overload_separation_enabled: bool = False,
    reverification_selection_nogood_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema": "binding_semantics_contract_v1",
        "constructor_parameters": sorted(
            name
            for name in inspect.signature(PortBindingModel.__init__).parameters
            if name != "self"
        ),
        "build_parameters": sorted(
            name
            for name in inspect.signature(PortBindingModel.build).parameters
            if name != "self"
        ),
        "constraint_families": [
            "fixed_pose_side_injection",
            "generic_input_exact_cardinality",
            "generic_output_exact_cardinality",
        ],
        "routing_context_enabled": routing_context_enabled,
        "overload_separation_enabled": overload_separation_enabled,
        "reverification_selection_nogood_count": (
            reverification_selection_nogood_count
        ),
        "source_rejected_selection_count": source_rejected_selection_count,
        "generic_input_slot_policy": "plan_derived_physical_exact_count",
        "generic_output_slot_policy": "plan_derived_physical_exact_count",
        "plan_generic_input_slots_by_operation": dict(input_slots),
        "plan_generic_output_slots_by_operation": dict(output_slots),
        "plan_utility_operation_by_template": dict(
            utility_operations
        ),
    }


def _binding_fixture(
    tmp_path: Path,
    *,
    required_output_slots: int = 1,
    required_input_slots: int = 1,
    boundary_output_ports: int = 1,
    box_input_ports: int = 3,
) -> dict[str, Any]:
    rules = {
        "globals": {"logistics": {"belt_capacity_per_tick": 1}},
        "facility_templates": {
            "factory": {},
            "boundary_storage_port": {},
            "protocol_core": {},
            "protocol_storage_box": {},
            "power_pole": {},
        },
        "recipes": {
            "make_product": {
                "template": "factory",
                "ticks_per_cycle": 1,
                "inputs": {"ore": 1},
                "outputs": {"product": 1},
            }
        },
        "commodity_metadata": {
            "ore": {"source_kind": "external_boundary", "sink_kind": "none"},
            "product": {
                "source_kind": "internal_only",
                "sink_kind": "generic_input",
            },
        },
    }
    plan = {
        "utility_operations": {
            "boundary_io": {
                "facility_type": "boundary_storage_port",
                "generic_input_slots": 0,
                "generic_output_slots": 1,
            },
            "protocol_core": {
                "facility_type": "protocol_core",
                "generic_input_slots": 14,
                "generic_output_slots": 6,
            },
            "box_sink": {
                "facility_type": "protocol_storage_box",
                "generic_input_slots": 3,
                "generic_output_slots": 0,
            },
            "power_supply": {
                "facility_type": "power_pole",
                "generic_input_slots": 0,
                "generic_output_slots": 0,
            },
        }
    }
    requirements = {
        "required_generic_outputs": {"ore": required_output_slots},
        "required_generic_inputs": {"product": required_input_slots},
    }
    instances = [
        {
            "instance_id": "factory_0",
            "facility_type": "factory",
            "operation_type": "make_product",
            "is_mandatory": True,
        },
        {
            "instance_id": "source_0",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
        },
    ]
    solution = {
        "factory_0": {"facility_type": "factory", "pose_idx": 0},
        "source_0": {
            "facility_type": "boundary_storage_port",
            "pose_idx": 0,
        },
        "pose_optional::protocol_storage_box::0": {
            "facility_type": "protocol_storage_box",
            "pose_idx": 0,
        },
    }
    facility_pools = {
        "factory": [
            {
                "pose_id": "factory_pose",
                "input_port_cells": _port_cells(1, y=2, direction="N"),
                "output_port_cells": _port_cells(1, y=0, direction="S"),
            }
        ],
        "boundary_storage_port": [
            {
                "pose_id": "source_pose",
                "input_port_cells": [],
                "output_port_cells": _port_cells(
                    boundary_output_ports,
                    y=4,
                    direction="N",
                ),
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_pose",
                "input_port_cells": _port_cells(
                    box_input_ports,
                    y=8,
                    direction="S",
                ),
                "output_port_cells": [],
            }
        ],
    }
    _write_json(tmp_path / "rules/canonical_rules.json", rules)
    _write_json(tmp_path / "rules/preprocess_plan.json", plan)
    _write_json(
        tmp_path / "data/preprocessed/generic_io_requirements.json",
        requirements,
    )
    _write_json(
        tmp_path / "data/preprocessed/mandatory_exact_instances.json",
        instances,
    )
    _write_json(
        tmp_path / "data/preprocessed/candidate_placements.json",
        {"facility_pools": facility_pools},
    )
    input_map = {"box_sink": 3, "protocol_core": 14}
    output_map = {"boundary_io": 1, "protocol_core": 6}
    utility_operation_map = {
        "boundary_storage_port": "boundary_io",
        "power_pole": "power_supply",
        "protocol_core": "protocol_core",
        "protocol_storage_box": "box_sink",
    }
    binding_kwargs = {
        "required_generic_outputs": requirements["required_generic_outputs"],
        "required_generic_inputs": requirements["required_generic_inputs"],
        "generic_input_slots_by_operation": input_map,
        "generic_output_slots_by_operation": output_map,
        "utility_operation_by_template": utility_operation_map,
        "canonical_rules_payload": rules,
    }
    return {
        "solution": solution,
        "facility_pools": facility_pools,
        "instances": instances,
        "project_root": tmp_path,
        "proof_stage": "binding",
        "binding_exhausted": True,
        "routing_exhausted": False,
        "binding_kwargs": binding_kwargs,
        "artifact_hashes": _artifact_hashes(tmp_path),
        "binding_semantics_contract": _semantics_contract(
            input_slots=input_map,
            output_slots=output_map,
            utility_operations=utility_operation_map,
        ),
        "time_limit_seconds": 5.0,
    }


def _run_fixture(fixture: Mapping[str, Any]) -> IndependentInfeasibilityReverificationVerdict:
    return reverify_whole_layout_infeasibility(**dict(fixture))


def _capsule_request(fixture: Mapping[str, Any]) -> dict[str, Any]:
    solution = fixture["solution"]
    facility_pools = fixture["facility_pools"]
    selected = {
        instance_id: facility_pools[entry["facility_type"]][entry["pose_idx"]]
        for instance_id, entry in solution.items()
        if instance_id != "ghost_pick"
    }
    return {
        "schema": "independent_binding_reverify_request_v1",
        "authority": "independent_binding_reverify_capsule_v1",
        "nonce": "unit-nonce",
        "project_root": str(Path(fixture["project_root"]).resolve()),
        "proof_stage": str(fixture["proof_stage"]),
        "binding_exhausted": bool(fixture["binding_exhausted"]),
        "routing_exhausted": bool(fixture["routing_exhausted"]),
        "artifact_hashes": dict(fixture["artifact_hashes"]),
        "solution": json.loads(json.dumps(solution)),
        "caller_instances": json.loads(json.dumps(fixture["instances"])),
        "caller_selected_poses": json.loads(json.dumps(selected)),
        "binding_inputs": json.loads(json.dumps(fixture["binding_kwargs"])),
        "semantics_contract": json.loads(
            json.dumps(fixture["binding_semantics_contract"])
        ),
    }


class _FakeMaster:
    def __init__(self) -> None:
        self.facility_pools = {"factory": [{"occupied_cells": [[0, 0]]}]}
        self.source_instances = [{"instance_id": "a", "facility_type": "factory"}]
        self.generic_io_requirements = {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        }
        self.generic_input_slots_by_operation: dict[str, int] = {}
        self.generic_output_slots_by_operation: dict[str, int] = {}
        self.utility_operation_by_template: dict[str, str] = {
            "boundary_storage_port": "boundary_io",
            "power_pole": "power_supply",
            "protocol_core": "protocol_core",
            "protocol_storage_box": "box_sink",
        }
        self.rules = {"commodity_metadata": {}}
        self.cuts: list[dict[str, int]] = []

    def add_benders_cut(
        self,
        conflict_set: Mapping[str, int],
        *,
        condition_lits: tuple[Any, ...] = (),
    ) -> bool:
        del condition_lits
        self.cuts.append({str(key): int(value) for key, value in conflict_set.items()})
        return True


class _ObservedBindingModel:
    def __init__(
        self,
        *,
        routing_context_enabled: bool = False,
        overload_separation_enabled: bool = False,
        selection_nogood_count: int = 0,
    ) -> None:
        self.routing_context = {} if routing_context_enabled else None
        self._summary = {
            "routing_context_enabled": routing_context_enabled,
            "overload_separation_enabled": overload_separation_enabled,
            "selection_nogood_count": selection_nogood_count,
        }

    def extract_conflict_summary(self) -> dict[str, Any]:
        return dict(self._summary)


class _FakeCutManager:
    def __init__(self) -> None:
        self.registered: list[Any] = []

    def has_structured_cut(self, cut: Any) -> bool:
        del cut
        return False

    def register_structured_cut(self, cut: Any) -> bool:
        self.registered.append(cut)
        return True


def _controller() -> tuple[LBBDController, _FakeMaster, _FakeCutManager, list[dict[str, Any]]]:
    master = _FakeMaster()
    cut_manager = _FakeCutManager()
    heartbeats: list[dict[str, Any]] = []
    controller = LBBDController(
        master=master,  # type: ignore[arg-type]
        cut_manager=cut_manager,  # type: ignore[arg-type]
        project_root=PROJECT_ROOT,
        solve_mode="certified_exact",
        heartbeat_callback=heartbeats.append,
        artifact_hashes={"unit": "hash"},
    )
    return controller, master, cut_manager, heartbeats


def _verdict(
    *,
    confirmed: bool,
    status: str,
    reason: str,
    independent_status: str | None = None,
) -> IndependentInfeasibilityReverificationVerdict:
    return IndependentInfeasibilityReverificationVerdict(
        schema_version=INDEPENDENT_INFEASIBILITY_REVERIFIER_SCHEMA_VERSION,
        authority=INDEPENDENT_INFEASIBILITY_REVERIFIER_AUTHORITY,
        confirmed=confirmed,
        status=status,
        stage="binding",
        reason=reason,
        independent_status=independent_status,
        details={"unit": True},
    )


def _try_add_whole_layout_nogood(
    controller: LBBDController,
    proof_summary: dict[str, Any],
) -> bool:
    return controller._add_exact_whole_layout_nogood(
        solution={"a": {"facility_type": "factory", "pose_idx": 0}},
        iteration=7,
        cut_type="binding_infeasible_nogood",
        proof_stage="binding",
        binding_exhausted=True,
        routing_exhausted=False,
        proof_summary=proof_summary,
        binding_model=_ObservedBindingModel(),  # type: ignore[arg-type]
        source_rejected_selection_count=0,
    )


def test_independent_infeasibility_reverify_confirms_binding_infeasible_allows_cut(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}
    monkeypatch.setattr(
        benders_loop,
        "reverify_whole_layout_infeasibility",
        lambda **_kwargs: _verdict(
            confirmed=True,
            status=REVERIFY_STATUS_CONFIRMED_INFEASIBLE,
            reason="independent_binding_certificate_confirmed",
            independent_status="ARITHMETIC_INFEASIBLE",
        ),
    )

    assert _try_add_whole_layout_nogood(controller, proof_summary) is True
    assert master.cuts == [{"a": 0}]
    assert len(cut_manager.registered) == 1
    assert proof_summary["independent_infeasibility_reverifier"]["status"] == (
        REVERIFY_STATUS_CONFIRMED_INFEASIBLE
    )
    assert heartbeats == []


def test_independent_infeasibility_reverify_divergent_feasible_blocks_cut_unknown(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}
    monkeypatch.setattr(
        benders_loop,
        "reverify_whole_layout_infeasibility",
        lambda **_kwargs: _verdict(
            confirmed=False,
            status=REVERIFY_STATUS_DIVERGED_FEASIBLE,
            reason="explicit_binding_witness_constructed",
            independent_status="CONSTRUCTIVE_FEASIBLE",
        ),
    )

    assert _try_add_whole_layout_nogood(controller, proof_summary) is False
    assert master.cuts == []
    assert cut_manager.registered == []
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert heartbeats[-1]["event"] == (
        "whole_layout_nogood_independent_reverify_divergence"
    )


def test_independent_infeasibility_reverify_timeout_blocks_cut_unknown(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}
    monkeypatch.setattr(
        benders_loop,
        "reverify_whole_layout_infeasibility",
        lambda **_kwargs: _verdict(
            confirmed=False,
            status=REVERIFY_STATUS_TIMEOUT,
            reason="capsule_timeout",
            independent_status="UNKNOWN",
        ),
    )

    assert _try_add_whole_layout_nogood(controller, proof_summary) is False
    assert master.cuts == []
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert heartbeats[-1]["reverify_status"] == REVERIFY_STATUS_TIMEOUT


def test_independent_infeasibility_reverify_exception_blocks_cut_unknown(
    monkeypatch: Any,
) -> None:
    controller, master, cut_manager, heartbeats = _controller()
    proof_summary: dict[str, Any] = {"mode": "certified_exact"}

    def _boom(**_kwargs: Any) -> IndependentInfeasibilityReverificationVerdict:
        raise RuntimeError("unit divergence")

    monkeypatch.setattr(benders_loop, "reverify_whole_layout_infeasibility", _boom)
    assert _try_add_whole_layout_nogood(controller, proof_summary) is False
    assert master.cuts == []
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert proof_summary["independent_infeasibility_reverifier"]["reason"] == (
        "independent_infeasibility_reverify_uncaught_exception"
    )
    assert heartbeats[-1]["event"] == (
        "whole_layout_nogood_independent_reverify_unknown"
    )


def test_independent_infeasibility_reverify_routing_exhaustion_without_binding_confirmation_unknown(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["proof_stage"] = "routing"
    fixture["routing_exhausted"] = True

    verdict = _run_fixture(fixture)

    assert verdict.confirmed is False
    assert verdict.status == REVERIFY_STATUS_UNKNOWN
    assert verdict.reason == "routing_exhaustion_phase1_conservative_unknown"
    assert verdict.details["binding_reverification"]["independent_status"] == (
        "CONSTRUCTIVE_FEASIBLE"
    )


def test_independent_binding_arithmetic_confirms_generic_output_deficit(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(
        tmp_path,
        required_output_slots=2,
        boundary_output_ports=1,
    )
    verdict = _run_fixture(fixture)

    assert verdict.confirmed is True
    assert verdict.status == STATUS_CONFIRMED_INFEASIBLE
    assert verdict.independent_status == "ARITHMETIC_INFEASIBLE"
    assert verdict.details["certificate"]["deficits"] == [
        {
            "side": "generic_output",
            "required_positive_slots": 2,
            "physical_slots": 1,
            "deficit": 1,
        }
    ]
    assert verdict.details["certificate_check"]["ok"] is True


def test_independent_binding_arithmetic_confirms_generic_input_deficit(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(
        tmp_path,
        required_input_slots=4,
        box_input_ports=3,
    )
    verdict = _run_fixture(fixture)

    assert verdict.confirmed is True
    assert verdict.independent_status == "ARITHMETIC_INFEASIBLE"
    assert verdict.details["certificate"]["deficits"][0]["side"] == "generic_input"


def test_independent_binding_arithmetic_constructs_feasible_assignment(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    verdict = _run_fixture(fixture)

    assert verdict.confirmed is False
    assert verdict.status == STATUS_DIVERGED_FEASIBLE
    assert verdict.independent_status == "CONSTRUCTIVE_FEASIBLE"
    certificate = verdict.details["certificate"]
    assert certificate["deficits"] == []
    assert certificate["capacity_accounts"]["generic_output"]["slack"] == 0
    assert certificate["capacity_accounts"]["generic_input"]["slack"] == 2
    assert certificate["witness"]["fixed_assignments"]
    assert certificate["witness"]["generic_input_assignments"]
    assert verdict.details["certificate_check"]["ok"] is True


def test_explicit_witness_checker_rejects_tampered_assignment(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    request = _capsule_request(fixture)
    artifacts = load_authority_artifacts(
        tmp_path,
        expected_hashes=fixture["artifact_hashes"],
    )
    model = build_semantic_model(artifacts, request)
    certificate = build_binding_certificate(model)
    certificate["witness"]["generic_input_assignments"][0]["commodity"] = "wrong"
    certificate["witness_digest"] = "0" * 64
    certificate["certificate_digest"] = "0" * 64

    check = verify_binding_certificate(model, certificate)

    assert check.ok is False
    assert any("unsupported commodity" in failure for failure in check.failures)
    assert any("witness_digest mismatch" in failure for failure in check.failures)


def test_explicit_witness_checker_rejects_bool_integer_alias(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    request = _capsule_request(fixture)
    artifacts = load_authority_artifacts(
        tmp_path,
        expected_hashes=fixture["artifact_hashes"],
    )
    model = build_semantic_model(artifacts, request)
    certificate = build_binding_certificate(model)
    assignment = next(
        item
        for item in certificate["witness"]["generic_input_assignments"]
        if item["x"] == 1
    )
    assignment["x"] = True
    certificate["witness_digest"] = canonical_digest(certificate["witness"])
    certificate["certificate_digest"] = canonical_digest(
        {
            key: value
            for key, value in certificate.items()
            if key != "certificate_digest"
        }
    )

    check = verify_binding_certificate(model, certificate)

    assert check.ok is False
    assert any("metadata mismatch" in failure for failure in check.failures)


def test_independent_binding_arithmetic_rejects_generic_input_port_count_drift(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path, box_input_ports=4)
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == (
        "GENERIC_INPUT_PHYSICAL_PORT_COUNT_DRIFT"
    )


def test_independent_binding_arithmetic_rejects_selected_pose_drift(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["facility_pools"]["boundary_storage_port"][0]["output_port_cells"][0][
        "x"
    ] = 99
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"].startswith("CALLER_SELECTED_POSE_DRIFT:")


def test_independent_binding_arithmetic_rejects_missing_mandatory_placement(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["solution"].pop("source_0")
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "MANDATORY_PLACEMENT_MISSING"
    assert verdict.details["input_error_detail"] == "source_0"


def test_independent_binding_arithmetic_rejects_generic_role_overlap(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    rules = fixture["binding_kwargs"]["canonical_rules_payload"]
    rules["commodity_metadata"]["ore"]["sink_kind"] = "generic_input"
    requirements = {
        "required_generic_outputs": {"ore": 1},
        "required_generic_inputs": {"ore": 1, "product": 1},
    }
    fixture["binding_kwargs"]["required_generic_outputs"] = requirements[
        "required_generic_outputs"
    ]
    fixture["binding_kwargs"]["required_generic_inputs"] = requirements[
        "required_generic_inputs"
    ]
    _write_json(tmp_path / "rules/canonical_rules.json", rules)
    _write_json(
        tmp_path / "data/preprocessed/generic_io_requirements.json",
        requirements,
    )
    fixture["artifact_hashes"] = _artifact_hashes(tmp_path)
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "GENERIC_OUTPUT_INPUT_ROLE_OVERLAP"


def test_independent_binding_arithmetic_rejects_authority_snapshot_drift(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_kwargs"]["canonical_rules_payload"] = {
        **fixture["binding_kwargs"]["canonical_rules_payload"],
        "recipes": {},
    }
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "CALLER_CANONICAL_RULES_DRIFT"


def test_independent_binding_arithmetic_rejects_unmodeled_binding_semantics(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_kwargs"]["future_constraint_family"] = True
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "UNSUPPORTED_BINDING_SEMANTICS"


def test_constructor_surface_drift_fails_closed(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_semantics_contract"]["constructor_parameters"].append(
        "future_cross_instance_constraint"
    )
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "BINDING_CONSTRUCTOR_SURFACE_DRIFT"


def test_runtime_contract_observes_real_model_nogood_and_routing_state(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    from src.models.routing_binding_context import build_routing_binding_context

    production_solution = {
        key: value
        for key, value in fixture["solution"].items()
        if key != "factory_0"
    }
    production_instances = [
        instance
        for instance in fixture["instances"]
        if instance["instance_id"] != "factory_0"
    ]
    routing_context = build_routing_binding_context(
        production_solution,
        fixture["facility_pools"],
        grid_w=20,
        grid_h=20,
    )
    model = PortBindingModel(
        placement_solution=production_solution,
        facility_pools=fixture["facility_pools"],
        instances=production_instances,
        project_root=tmp_path,
        routing_context=routing_context,
        **fixture["binding_kwargs"],
    )
    model.build(use_overload_separation=False)
    assert model.solve(time_limit_seconds=2.0) == "FEASIBLE"
    model.add_nogood_cut(model.extract_selection())

    controller = LBBDController.__new__(LBBDController)
    controller.solve_mode = "certified_exact"
    controller.master = type(
        "MasterSnapshot",
        (),
        {
            "generic_io_requirements": {
                "required_generic_outputs": fixture["binding_kwargs"][
                    "required_generic_outputs"
                ],
                "required_generic_inputs": fixture["binding_kwargs"][
                    "required_generic_inputs"
                ],
            },
            "generic_input_slots_by_operation": fixture["binding_kwargs"][
                "generic_input_slots_by_operation"
            ],
            "generic_output_slots_by_operation": fixture["binding_kwargs"][
                "generic_output_slots_by_operation"
            ],
            "utility_operation_by_template": fixture["binding_kwargs"][
                "utility_operation_by_template"
            ],
            "rules": fixture["binding_kwargs"]["canonical_rules_payload"],
        },
    )()

    contract = controller._binding_reverify_semantics_contract(
        binding_model=model,
        source_rejected_selection_count=1,
    )

    assert contract["routing_context_enabled"] is True
    assert contract["overload_separation_enabled"] is False
    assert contract["reverification_selection_nogood_count"] == 1


def test_runtime_contract_observes_real_overload_separation(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    production_solution = {
        key: value
        for key, value in fixture["solution"].items()
        if key != "factory_0"
    }
    production_instances = [
        instance
        for instance in fixture["instances"]
        if instance["instance_id"] != "factory_0"
    ]
    model = PortBindingModel(
        placement_solution=production_solution,
        facility_pools=fixture["facility_pools"],
        instances=production_instances,
        project_root=tmp_path,
        **fixture["binding_kwargs"],
    )
    model.build(use_overload_separation=True)

    controller = LBBDController.__new__(LBBDController)
    controller.solve_mode = "certified_exact"
    controller.master = type(
        "MasterSnapshot",
        (),
        {
            "generic_io_requirements": {
                "required_generic_outputs": fixture["binding_kwargs"][
                    "required_generic_outputs"
                ],
                "required_generic_inputs": fixture["binding_kwargs"][
                    "required_generic_inputs"
                ],
            },
            "generic_input_slots_by_operation": fixture["binding_kwargs"][
                "generic_input_slots_by_operation"
            ],
            "generic_output_slots_by_operation": fixture["binding_kwargs"][
                "generic_output_slots_by_operation"
            ],
            "utility_operation_by_template": fixture["binding_kwargs"][
                "utility_operation_by_template"
            ],
            "rules": fixture["binding_kwargs"]["canonical_rules_payload"],
        },
    )()

    contract = controller._binding_reverify_semantics_contract(
        binding_model=model,
        source_rejected_selection_count=0,
    )

    assert contract["overload_separation_enabled"] is True


def test_runtime_contract_fields_are_observed_from_binding_model() -> None:
    controller, _master, _cut_manager, _heartbeats = _controller()
    observed = _ObservedBindingModel(
        routing_context_enabled=True,
        overload_separation_enabled=True,
        selection_nogood_count=3,
    )

    contract = controller._binding_reverify_semantics_contract(
        binding_model=observed,  # type: ignore[arg-type]
        source_rejected_selection_count=3,
    )

    assert contract["routing_context_enabled"] is True
    assert contract["overload_separation_enabled"] is True
    assert contract["reverification_selection_nogood_count"] == 3
    assert contract["source_rejected_selection_count"] == 3


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("overload_separation_enabled", True, "OVERLOAD_SEPARATION_UNSUPPORTED"),
        ("reverification_selection_nogood_count", 1, "SELECTION_NOGOOD_UNSUPPORTED"),
    ],
)
def test_runtime_capability_guards_are_reachable(
    tmp_path: Path,
    field: str,
    value: Any,
    expected_code: str,
) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_semantics_contract"][field] = value

    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == expected_code


def test_utility_operation_map_drift_fails_closed(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_kwargs"]["utility_operation_by_template"] = {
        **fixture["binding_kwargs"]["utility_operation_by_template"],
        "protocol_storage_box": "power_supply",
    }

    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "UTILITY_OPERATION_MAP_DRIFT"


def test_plan_provider_drift_fails_closed(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    plan_path = tmp_path / "rules/preprocess_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["utility_operations"]["future_provider"] = {
        "facility_type": "future_provider",
        "generic_input_slots": 0,
        "generic_output_slots": 2,
    }
    _write_json(plan_path, plan)
    fixture["artifact_hashes"] = _artifact_hashes(tmp_path)
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == (
        "SEMANTICS_CONTRACT_OUTPUT_PLAN_DRIFT"
    )


def test_capsule_enforces_real_wall_timeout(tmp_path: Path, monkeypatch: Any) -> None:
    fixture = _binding_fixture(tmp_path)
    monkeypatch.setattr(
        transport,
        "_BOOTSTRAP",
        "import time; time.sleep(10)",
    )
    fixture["time_limit_seconds"] = 0.05
    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_TIMEOUT
    assert verdict.reason == "independent_binding_capsule_timeout"


def _copy_package(tmp_path: Path) -> Path:
    destination = tmp_path / "independent_binding_reverify"
    shutil.copytree(PACKAGE_PATH, destination)
    return destination


def test_p1_2_checker_rejects_production_model_import_in_reverifier(
    tmp_path: Path,
) -> None:
    package = _copy_package(tmp_path)
    semantics = package / "semantics.py"
    semantics.write_text(
        semantics.read_text(encoding="utf-8")
        + "\nfrom src.models.binding_subproblem import PortBindingModel\n",
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=package,
    )

    assert any("imports forbidden module src.models.binding_subproblem" in error for error in errors)


def test_p1_2_checker_rejects_arithmetic_analyzer_bypass(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    capsule = package / "capsule.py"
    capsule.write_text(
        capsule.read_text(encoding="utf-8").replace(
            "certificate = build_binding_certificate(model)",
            "certificate = unchecked_common_mode_binding_builder(model)",
            1,
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=package,
    )

    assert "capsule child executor must call build_binding_certificate" in errors


def test_p1_2_checker_rejects_whole_layout_reverify_gate_removal(tmp_path: Path) -> None:
    benders_path = tmp_path / "benders_loop.py"
    benders_path.write_text(
        check_p1_2_proof_obligations.BENDERS_LOOP_PATH.read_text(
            encoding="utf-8"
        ).replace(
            "reverify_verdict = reverify_whole_layout_infeasibility(",
            "reverify_verdict = unchecked_whole_layout(",
            1,
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=benders_path,
    )

    assert "whole-layout nogood funnel must call the independent capsule" in errors


def test_p1_2_checker_rejects_inflight_cache_read_in_infeasibility_reverifier(
    tmp_path: Path,
) -> None:
    package = _copy_package(tmp_path)
    semantics = package / "semantics.py"
    semantics.write_text(
        semantics.read_text(encoding="utf-8")
        + "\n\ndef _unit_bad_cache_read(self):\n    return self._solver\n",
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=package,
    )

    assert any("self._solver" in error for error in errors)


def test_p1_2_checker_rejects_env_reader_in_infeasibility_reverifier(
    tmp_path: Path,
) -> None:
    package = _copy_package(tmp_path)
    semantics = package / "semantics.py"
    semantics.write_text(
        semantics.read_text(encoding="utf-8")
        + '\n\nimport os\n\ndef _unit_bad_env_read():\n    return os.getenv("EXACT_FAKE")\n',
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=package,
    )

    assert any("imports forbidden module os" in error for error in errors)


@pytest.mark.parametrize(
    "payload, expected_fragment",
    [
        (
            "\nimport importlib\n\ndef bad():\n    return importlib.import_module('ortools')\n",
            "imports forbidden module importlib",
        ),
        (
            "\ndef bad():\n    return __import__('ortools')\n",
            "dynamic execution/import primitive forbidden: __import__",
        ),
        (
            "\nimport builtins\n\ndef bad():\n    return builtins.__import__('ortools')\n",
            "imports forbidden module builtins",
        ),
        (
            "\ndef bad():\n    return getattr(__builtins__, '__import__')('ortools')\n",
            "dynamic attribute import bypass forbidden: getattr('__import__')",
        ),
    ],
)
def test_package_checker_rejects_dynamic_import_bypasses(
    tmp_path: Path,
    payload: str,
    expected_fragment: str,
) -> None:
    package = _copy_package(tmp_path)
    semantics = package / "semantics.py"
    semantics.write_text(
        semantics.read_text(encoding="utf-8") + payload,
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=package,
    )

    assert any(expected_fragment in error for error in errors)


@pytest.mark.parametrize(
    ("field", "literal"),
    [
        ("routing_context_enabled", "False"),
        ("overload_separation_enabled", "False"),
        ("reverification_selection_nogood_count", "0"),
    ],
)
def test_package_checker_rejects_constant_runtime_contract_fields(
    tmp_path: Path,
    field: str,
    literal: str,
) -> None:
    benders_path = tmp_path / "benders_loop.py"
    source = check_p1_2_proof_obligations.BENDERS_LOOP_PATH.read_text(
        encoding="utf-8"
    )
    observed_expression = (
        "int(raw_nogood_count)"
        if field == "reverification_selection_nogood_count"
        else field
    )
    source = source.replace(
        f'"{field}": {observed_expression},',
        f'"{field}": {literal},',
        1,
    )
    benders_path.write_text(source, encoding="utf-8")

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=benders_path,
    )

    assert any(
        f"field must not be a constant: {field}" in error
        for error in errors
    )


def test_package_checker_rejects_production_provider_hardcode(tmp_path: Path) -> None:
    binding_path = tmp_path / "binding_subproblem.py"
    binding_path.write_text(
        check_p1_2_proof_obligations.BINDING_SUBPROBLEM_PATH.read_text(
            encoding="utf-8"
        ).replace(
            "capacity_map = self._generic_output_slot_capacity_map()",
            'capacity_map = {"boundary_io": 1, "protocol_core": 6}',
            1,
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        binding_subproblem_path=binding_path,
    )

    assert "production generic-output provider admission must be plan-derived" in errors


def test_package_checker_rejects_production_input_provider_hardcode(
    tmp_path: Path,
) -> None:
    binding_path = tmp_path / "binding_subproblem.py"
    binding_path.write_text(
        check_p1_2_proof_obligations.BINDING_SUBPROBLEM_PATH.read_text(
            encoding="utf-8"
        ).replace(
            "capacity_map = self._generic_input_slot_capacity_map()",
            'capacity_map = {"box_sink": 3, "protocol_core": 14}',
            1,
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        binding_subproblem_path=binding_path,
    )

    assert "production generic-input provider admission must be plan-derived" in errors


def test_package_checker_rejects_pr2_output_map_drop(tmp_path: Path) -> None:
    pr2_path = tmp_path / "pr2_l0_fixed_witness_core.py"
    pr2_path.write_text(
        check_p1_2_proof_obligations.PR2_L0_FIXED_WITNESS_CORE_PATH.read_text(
            encoding="utf-8"
        ).replace(
            "generic_output_slots_by_operation=generic_output_slots_by_operation,",
            "",
            1,
        ),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        pr2_fixed_witness_path=pr2_path,
    )

    assert any(
        "missing plan-derived keyword: generic_output_slots_by_operation" in error
        for error in errors
    )


def test_capability_contract_uses_observed_production_runtime_state() -> None:
    controller, _master, _cut_manager, _heartbeats = _controller()
    observed = _ObservedBindingModel(
        routing_context_enabled=True,
        overload_separation_enabled=True,
        selection_nogood_count=7,
    )

    contract = controller._binding_reverify_semantics_contract(
        binding_model=observed,  # type: ignore[arg-type]
        source_rejected_selection_count=7,
    )

    assert contract["routing_context_enabled"] is True
    assert contract["overload_separation_enabled"] is True
    assert contract["reverification_selection_nogood_count"] == 7
    assert contract["plan_utility_operation_by_template"]["protocol_storage_box"] == "box_sink"


def test_routing_context_is_certificate_bound_monotone_relaxation(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    request = _capsule_request(fixture)
    request["semantics_contract"]["routing_context_enabled"] = True
    artifacts = load_authority_artifacts(
        tmp_path,
        expected_hashes=fixture["artifact_hashes"],
    )

    model = build_semantic_model(artifacts, request)
    certificate = build_binding_certificate(model)
    check = verify_binding_certificate(model, certificate)

    assert model.routing_context_relaxation_active is True
    assert certificate["runtime_relaxations"] == [
        "routing_context_domain_filter_omitted_monotone_superset"
    ]
    assert check.ok is True


def test_capsule_accepts_observed_routing_context_as_monotone_relaxation(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_semantics_contract"]["routing_context_enabled"] = True

    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_DIVERGED_FEASIBLE
    assert verdict.details["certificate_check"]["ok"] is True
    assert verdict.details["certificate"]["runtime_relaxations"] == [
        "routing_context_domain_filter_omitted_monotone_superset"
    ]


def test_certificate_checker_rejects_runtime_relaxation_tamper(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    request = _capsule_request(fixture)
    request["semantics_contract"]["routing_context_enabled"] = True
    artifacts = load_authority_artifacts(
        tmp_path,
        expected_hashes=fixture["artifact_hashes"],
    )
    model = build_semantic_model(artifacts, request)
    certificate = build_binding_certificate(model)
    certificate["runtime_relaxations"] = []
    certificate["certificate_digest"] = canonical_digest(
        {
            key: value
            for key, value in certificate.items()
            if key != "certificate_digest"
        }
    )

    check = verify_binding_certificate(model, certificate)

    assert check.ok is False
    assert "runtime_relaxations do not match" in "\n".join(check.failures)


def test_observed_overload_separation_fails_closed(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_semantics_contract"]["overload_separation_enabled"] = True

    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "OVERLOAD_SEPARATION_UNSUPPORTED"


def test_observed_selection_nogoods_fail_closed(tmp_path: Path) -> None:
    fixture = _binding_fixture(tmp_path)
    fixture["binding_semantics_contract"]["reverification_selection_nogood_count"] = 1

    verdict = _run_fixture(fixture)

    assert verdict.status == STATUS_UNKNOWN
    assert verdict.details["input_error_code"] == "SELECTION_NOGOOD_UNSUPPORTED"


def test_package_checker_rejects_hardcoded_runtime_capability_field(
    tmp_path: Path,
) -> None:
    benders_path = tmp_path / "benders_loop.py"
    source = check_p1_2_proof_obligations.BENDERS_LOOP_PATH.read_text(encoding="utf-8")
    source = source.replace(
        '"routing_context_enabled": routing_context_enabled',
        '"routing_context_enabled": False',
        1,
    )
    benders_path.write_text(source, encoding="utf-8")

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=benders_path,
    )

    assert any(
        "binding capability contract field must not be a constant" in error
        for error in errors
    )


def test_package_checker_seals_primary_and_retry_binding_snapshot_wiring(
    tmp_path: Path,
) -> None:
    benders_path = tmp_path / "benders_loop.py"
    source = check_p1_2_proof_obligations.BENDERS_LOOP_PATH.read_text(encoding="utf-8")
    token = "**LBBDController._binding_snapshot_kwargs(self),"
    assert source.count(token) >= 2
    first = source.find(token)
    second = source.find(token, first + len(token))
    source = source[:second] + source[second:].replace(token, "", 1)
    benders_path.write_text(source, encoding="utf-8")

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=benders_path,
    )

    assert any("every certified PortBindingModel construction" in error for error in errors)


def test_package_checker_seals_pr2_utility_snapshot_wiring(tmp_path: Path) -> None:
    pr2_path = tmp_path / "pr2_l0_fixed_witness_core.py"
    source = check_p1_2_proof_obligations.PR2_L0_FIXED_WITNESS_CORE_PATH.read_text(
        encoding="utf-8"
    )
    source = source.replace(
        "utility_operation_by_template=utility_operation_by_template,",
        "",
        1,
    )
    pr2_path.write_text(source, encoding="utf-8")

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        pr2_fixed_witness_path=pr2_path,
    )

    assert any(
        "missing plan-derived keyword: utility_operation_by_template" in error
        for error in errors
    )


def test_package_checker_seals_heuristic_nonauthority_boundary(
    tmp_path: Path,
) -> None:
    heuristic_path = tmp_path / "heuristic_feasible_finder.py"
    source = check_p1_2_proof_obligations.HEURISTIC_FEASIBLE_FINDER_PATH.read_text(
        encoding="utf-8"
    )
    source += "\n\ndef _unit_bad_authority_bridge(self):\n    return self._add_exact_persisted_nogood()\n"
    heuristic_path.write_text(source, encoding="utf-8")

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        heuristic_finder_path=heuristic_path,
    )

    assert any("heuristic PortBindingModel path must not enter" in error for error in errors)


def test_package_checker_requires_plan_derived_generic_input_admission(
    tmp_path: Path,
) -> None:
    binding_path = tmp_path / "binding_subproblem.py"
    source = check_p1_2_proof_obligations.BINDING_SUBPROBLEM_PATH.read_text(
        encoding="utf-8"
    )
    source = source.replace(
        "capacity_map = self._generic_input_slot_capacity_map()",
        "capacity_map = dict(self._generic_input_slots_by_operation or {})",
        1,
    )
    binding_path.write_text(source, encoding="utf-8")

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        binding_subproblem_path=binding_path,
    )

    assert "production generic-input provider admission must be plan-derived" in errors


def test_round3_certificate_checker_rejects_runtime_relaxation_tamper(
    tmp_path: Path,
) -> None:
    fixture = _binding_fixture(tmp_path)
    request = _capsule_request(fixture)
    artifacts = load_authority_artifacts(
        tmp_path,
        expected_hashes=fixture["artifact_hashes"],
    )
    model = build_semantic_model(artifacts, request)
    certificate = build_binding_certificate(model)
    assert verify_binding_certificate(model, certificate).ok is True

    certificate["runtime_relaxations"] = [
        "routing_context_domain_filter_omitted_monotone_superset"
    ]
    certificate["certificate_digest"] = canonical_digest(
        {
            key: value
            for key, value in certificate.items()
            if key != "certificate_digest"
        }
    )

    check = verify_binding_certificate(model, certificate)

    assert check.ok is False
    assert any(
        "runtime_relaxations do not match reconstructed production relaxation state"
        in failure
        for failure in check.failures
    )


def test_round3_checker_enumerates_non_controller_binding_constructors(
    tmp_path: Path,
) -> None:
    diagnostic = (
        "heuristic feasible finder must contain exactly one enumerated "
        "PortBindingModel constructor; found 2"
    )
    baseline_errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        heuristic_finder_path=(
            check_p1_2_proof_obligations.HEURISTIC_FEASIBLE_FINDER_PATH
        ),
    )
    assert diagnostic not in baseline_errors

    heuristic_path = tmp_path / "heuristic_feasible_finder.py"
    source = check_p1_2_proof_obligations.HEURISTIC_FEASIBLE_FINDER_PATH.read_text(
        encoding="utf-8"
    )
    heuristic_path.write_text(source + "\nPortBindingModel()\n", encoding="utf-8")

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        heuristic_finder_path=heuristic_path,
    )

    assert diagnostic in errors
    assert not any(
        "heuristic non-authority path must retain exactly one explicit "
        "PortBindingModel construction" in error
        for error in errors
    )


def test_round3_checker_requires_runtime_relaxation_validation(
    tmp_path: Path,
) -> None:
    field_diagnostic = (
        "independent certificate checker must validate theorem runtime_relaxations"
    )
    comparison_diagnostic = (
        "independent certificate checker must compare runtime_relaxations "
        "to the reconstructed semantic model"
    )
    baseline_errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=PACKAGE_PATH,
    )
    assert field_diagnostic not in baseline_errors
    assert comparison_diagnostic not in baseline_errors

    field_package = _copy_package(tmp_path / "field_read")
    field_certificate = field_package / "certificate.py"
    field_source = field_certificate.read_text(encoding="utf-8")
    assert '"runtime_relaxations"' in field_source
    field_certificate.write_text(
        field_source.replace('"runtime_relaxations"', '"runtime_relaxationz"'),
        encoding="utf-8",
    )

    field_errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=field_package,
    )
    assert field_diagnostic in field_errors

    comparison_package = _copy_package(tmp_path / "semantic_comparison")
    comparison_certificate = comparison_package / "certificate.py"
    comparison_source = comparison_certificate.read_text(encoding="utf-8")
    comparison_block = '''        if tuple(normalized_runtime_relaxations) != tuple(model.runtime_relaxations):
            failures.append(
                "runtime_relaxations do not match reconstructed production relaxation state"
            )
'''
    assert comparison_block in comparison_source
    comparison_certificate.write_text(
        comparison_source.replace(comparison_block, "", 1),
        encoding="utf-8",
    )

    comparison_errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        package_path=comparison_package,
    )
    assert comparison_diagnostic in comparison_errors


@pytest.mark.parametrize(
    ("field", "source_expression", "mutated_expression", "observation_name"),
    [
        (
            "routing_context_enabled",
            '"routing_context_enabled": routing_context_enabled,',
            '"routing_context_enabled": bool(overload_separation_enabled),',
            "routing_context_enabled",
        ),
        (
            "overload_separation_enabled",
            '"overload_separation_enabled": overload_separation_enabled,',
            '"overload_separation_enabled": bool(routing_context_enabled),',
            "overload_separation_enabled",
        ),
        (
            "reverification_selection_nogood_count",
            '"reverification_selection_nogood_count": int(raw_nogood_count),',
            '"reverification_selection_nogood_count": int(source_rejected_selection_count),',
            "raw_nogood_count",
        ),
        (
            "source_rejected_selection_count",
            '"source_rejected_selection_count": int(\n                source_rejected_selection_count\n            ),',
            '"source_rejected_selection_count": int(\n                raw_nogood_count\n            ),',
            "source_rejected_selection_count",
        ),
    ],
)
def test_round3_checker_rejects_constant_runtime_observation(
    tmp_path: Path,
    field: str,
    source_expression: str,
    mutated_expression: str,
    observation_name: str,
) -> None:
    diagnostic = (
        "binding capability contract field is not wired to its runtime observation: "
        f"{field}->{observation_name}"
    )
    baseline_errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=check_p1_2_proof_obligations.BENDERS_LOOP_PATH,
    )
    assert diagnostic not in baseline_errors

    benders_path = tmp_path / "benders_loop.py"
    source = check_p1_2_proof_obligations.BENDERS_LOOP_PATH.read_text(encoding="utf-8")
    assert source.count(source_expression) == 1
    benders_path.write_text(
        source.replace(source_expression, mutated_expression, 1),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        benders_loop_path=benders_path,
    )

    assert diagnostic in errors


def test_round3_checker_rejects_generic_input_plan_bypass(
    tmp_path: Path,
) -> None:
    diagnostic = "production generic-input provider admission must be plan-derived"
    baseline_errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        binding_subproblem_path=(
            check_p1_2_proof_obligations.BINDING_SUBPROBLEM_PATH
        ),
    )
    assert diagnostic not in baseline_errors

    binding_path = tmp_path / "binding_subproblem.py"
    source = check_p1_2_proof_obligations.BINDING_SUBPROBLEM_PATH.read_text(
        encoding="utf-8"
    )
    source_expression = "capacity_map = self._generic_input_slot_capacity_map()"
    mutated_expression = "capacity_map = self._generic_output_slot_capacity_map()"
    assert source.count(source_expression) == 1
    binding_path.write_text(
        source.replace(source_expression, mutated_expression, 1),
        encoding="utf-8",
    )

    errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        binding_subproblem_path=binding_path,
    )

    assert errors.count(diagnostic) == 2


def test_round3_checker_requires_evaluator_non_authority_exemption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exemption_diagnostic = (
        "P2 #14 evaluator PortBindingModel constructor must retain its explicit "
        "exploratory/evaluation non-authority exemption and reason"
    )
    funnel_diagnostic = (
        "P2 #14 evaluator exemption is invalid if the script enters a proof-bearing "
        "cut or independent reverify funnel"
    )
    baseline_errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
        p2_14_evaluator_path=check_p1_2_proof_obligations.P2_14_EVALUATOR_PATH,
    )
    assert exemption_diagnostic not in baseline_errors
    assert funnel_diagnostic not in baseline_errors

    exemption_path = "scripts/p2_14_evaluator/run_eval_v1_baseline.py"
    original_exemptions = (
        check_p1_2_proof_obligations.PORT_BINDING_CONSTRUCTOR_NON_AUTHORITY_EXEMPTIONS
    )
    classification, reason = original_exemptions[exemption_path]
    for mutated_exemption in (
        ("wrong_non_authority_classification", reason),
        (classification, "wrong exemption reason"),
    ):
        monkeypatch.setattr(
            check_p1_2_proof_obligations,
            "PORT_BINDING_CONSTRUCTOR_NON_AUTHORITY_EXEMPTIONS",
            {exemption_path: mutated_exemption},
        )
        errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
            p2_14_evaluator_path=(
                check_p1_2_proof_obligations.P2_14_EVALUATOR_PATH
            ),
        )
        assert exemption_diagnostic in errors

    monkeypatch.setattr(
        check_p1_2_proof_obligations,
        "PORT_BINDING_CONSTRUCTOR_NON_AUTHORITY_EXEMPTIONS",
        original_exemptions,
    )
    evaluator_source = check_p1_2_proof_obligations.P2_14_EVALUATOR_PATH.read_text(
        encoding="utf-8"
    )
    for index, proof_bearing_call in enumerate(
        (
            "reverify_whole_layout_infeasibility()",
            "controller._add_exact_persisted_nogood()",
        )
    ):
        evaluator_path = tmp_path / f"run_eval_v1_baseline_{index}.py"
        evaluator_path.write_text(
            evaluator_source + f"\n{proof_bearing_call}\n",
            encoding="utf-8",
        )
        errors = check_p1_2_proof_obligations._check_independent_infeasibility_reverifier_contract(
            p2_14_evaluator_path=evaluator_path,
        )
        assert funnel_diagnostic in errors
