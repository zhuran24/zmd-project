"""Real 70x70 differential parity for production binding and isolated I1.

The 54 MiB candidate pool is an optional external artifact in lightweight
checkouts.  Set ``ZMD_REAL_EXACT_PROJECT_ROOT`` to a checkout carrying the
locked artifact to run these evidence tests.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any

import pytest

from src.models.binding_subproblem import (
    PortBindingModel,
    load_generic_input_slots_by_operation,
    load_generic_io_requirements,
    load_generic_output_slots_by_operation,
    load_utility_operation_by_template,
)
from src.search.benders_loop import LBBDController
from src.search.independent_infeasibility_reverifier import (
    REVERIFY_STATUS_DIVERGED_FEASIBLE,
    reverify_whole_layout_infeasibility,
)


_ARTIFACT_RELPATHS = {
    "canonical_rules": "rules/canonical_rules.json",
    "preprocess_plan": "rules/preprocess_plan.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
}


@pytest.fixture(scope="module")
def real_binding_context() -> dict[str, Any]:
    raw_root = os.environ.get("ZMD_REAL_EXACT_PROJECT_ROOT", "").strip()
    if not raw_root:
        pytest.skip("set ZMD_REAL_EXACT_PROJECT_ROOT to run real artifact parity")
    root = Path(raw_root).resolve()
    candidate_path = root / _ARTIFACT_RELPATHS["candidate_placements"]
    if not candidate_path.is_file():
        pytest.skip(f"real candidate artifact is absent: {candidate_path}")

    external_manifest = json.loads(
        (root / "data/external_artifacts.json").read_text(encoding="utf-8")
    )
    candidate_entry = next(
        entry
        for entry in external_manifest["artifacts"]
        if entry["id"] == "candidate_placements"
    )
    actual_candidate_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    assert actual_candidate_hash == candidate_entry["sha256"]
    assert candidate_path.stat().st_size == candidate_entry["size_bytes"]

    rules = json.loads((root / "rules/canonical_rules.json").read_text(encoding="utf-8"))
    instances = json.loads(
        (root / "data/preprocessed/mandatory_exact_instances.json").read_text(
            encoding="utf-8"
        )
    )
    facility_pools = json.loads(candidate_path.read_text(encoding="utf-8"))[
        "facility_pools"
    ]
    requirements = load_generic_io_requirements(project_root=root)
    input_map = load_generic_input_slots_by_operation(project_root=root)
    output_map = load_generic_output_slots_by_operation(project_root=root)
    utility_operation_map = load_utility_operation_by_template(project_root=root)
    artifact_hashes = {
        key: hashlib.sha256((root / relpath).read_bytes()).hexdigest()
        for key, relpath in _ARTIFACT_RELPATHS.items()
    }
    base_solution = {
        instance["instance_id"]: {
            "facility_type": instance["facility_type"],
            "pose_idx": 0,
        }
        for instance in instances
    }
    return {
        "root": root,
        "rules": rules,
        "instances": instances,
        "facility_pools": facility_pools,
        "requirements": requirements,
        "input_map": input_map,
        "output_map": output_map,
        "utility_operation_map": utility_operation_map,
        "artifact_hashes": artifact_hashes,
        "base_solution": base_solution,
    }


def _observed_semantics_contract(
    context: dict[str, Any],
    binding_model: PortBindingModel,
    *,
    source_rejected_selection_count: int = 0,
) -> dict[str, Any]:
    controller = LBBDController.__new__(LBBDController)
    controller.solve_mode = "certified_exact"
    controller.master = SimpleNamespace(
        generic_io_requirements=context["requirements"],
        generic_input_slots_by_operation=context["input_map"],
        generic_output_slots_by_operation=context["output_map"],
        utility_operation_by_template=context["utility_operation_map"],
        rules=context["rules"],
    )
    return controller._binding_reverify_semantics_contract(
        binding_model=binding_model,
        source_rejected_selection_count=source_rejected_selection_count,
    )


@pytest.mark.evidence
@pytest.mark.parametrize("include_pose_optional_box", [False, True])
def test_real_protocol_core_and_pose_optional_box_match_production_cp_sat(
    real_binding_context: dict[str, Any],
    include_pose_optional_box: bool,
) -> None:
    context = real_binding_context
    solution = dict(context["base_solution"])
    optional_box_id = "pose_optional::protocol_storage_box::real_parity"
    if include_pose_optional_box:
        solution[optional_box_id] = {
            "facility_type": "protocol_storage_box",
            "pose_idx": 0,
        }

    production = PortBindingModel(
        placement_solution=solution,
        facility_pools=context["facility_pools"],
        instances=context["instances"],
        project_root=context["root"],
        required_generic_outputs=context["requirements"]["required_generic_outputs"],
        required_generic_inputs=context["requirements"]["required_generic_inputs"],
        generic_input_slots_by_operation=context["input_map"],
        generic_output_slots_by_operation=context["output_map"],
        utility_operation_by_template=context["utility_operation_map"],
        canonical_rules_payload=context["rules"],
    )
    production.build(use_overload_separation=False)
    production_status = production.solve(time_limit_seconds=30.0)
    semantics_contract = _observed_semantics_contract(context, production)

    assert semantics_contract["routing_context_enabled"] is False
    assert semantics_contract["overload_separation_enabled"] is False
    assert semantics_contract["reverification_selection_nogood_count"] == 0

    verdict = reverify_whole_layout_infeasibility(
        solution=solution,
        facility_pools=context["facility_pools"],
        instances=context["instances"],
        project_root=context["root"],
        proof_stage="binding",
        binding_exhausted=True,
        routing_exhausted=False,
        binding_kwargs={
            "required_generic_outputs": context["requirements"][
                "required_generic_outputs"
            ],
            "required_generic_inputs": context["requirements"][
                "required_generic_inputs"
            ],
            "generic_input_slots_by_operation": context["input_map"],
            "generic_output_slots_by_operation": context["output_map"],
            "utility_operation_by_template": context["utility_operation_map"],
            "canonical_rules_payload": context["rules"],
        },
        artifact_hashes=context["artifact_hashes"],
        binding_semantics_contract=semantics_contract,
        time_limit_seconds=30.0,
    )

    assert production_status == "FEASIBLE"
    assert verdict.status == REVERIFY_STATUS_DIVERGED_FEASIBLE
    assert verdict.independent_status == "CONSTRUCTIVE_FEASIBLE"
    assert verdict.details["certificate_check"]["ok"] is True

    certificate = verdict.details["certificate"]
    input_account = certificate["capacity_accounts"]["generic_input"]
    output_account = certificate["capacity_accounts"]["generic_output"]
    assert output_account == {
        "requirements": {"blue_iron_ore": 34, "source_ore": 18},
        "required_positive_slots": 52,
        "physical_slots": 52,
        "slack": 0,
    }
    assert input_account["requirements"] == {
        "qiaoyu_capsule": 1,
        "valley_battery": 1,
    }
    assert input_account["physical_slots"] == (17 if include_pose_optional_box else 14)
    assert input_account["slack"] == (15 if include_pose_optional_box else 12)

    witness = certificate["witness"]
    output_operations = Counter(
        assignment["operation_type"]
        for assignment in witness["generic_output_assignments"]
    )
    assert output_operations == Counter({"boundary_io": 46, "protocol_core": 6})
    input_operations = Counter(
        assignment["operation_type"]
        for assignment in witness["generic_input_assignments"]
    )
    assert input_operations["protocol_core"] == 14
    assert input_operations["box_sink"] == (3 if include_pose_optional_box else 0)

    if include_pose_optional_box:
        assert production.instances_by_id[optional_box_id]["operation_type"] == "box_sink"
        assert sum(
            assignment["instance_id"] == optional_box_id
            for assignment in witness["generic_input_assignments"]
        ) == 3
    else:
        assert optional_box_id not in production.instances_by_id


@pytest.mark.evidence
def test_real_artifact_output_deficit_matches_production_cp_sat(
    real_binding_context: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Real pose pool, controlled authority mutation: 53 outputs into 52 slots."""

    source = real_binding_context
    root = tmp_path / "real_negative_project"
    (root / "rules").mkdir(parents=True)
    (root / "data" / "preprocessed").mkdir(parents=True)
    for relpath in (
        "rules/canonical_rules.json",
        "rules/preprocess_plan.json",
        "data/preprocessed/mandatory_exact_instances.json",
    ):
        destination = root / relpath
        shutil.copyfile(source["root"] / relpath, destination)
    shutil.copyfile(
        source["root"] / _ARTIFACT_RELPATHS["candidate_placements"],
        root / _ARTIFACT_RELPATHS["candidate_placements"],
    )
    requirements = json.loads(json.dumps(source["requirements"]))
    requirements["required_generic_outputs"]["blue_iron_ore"] = 35
    requirements_path = root / _ARTIFACT_RELPATHS["generic_io_requirements"]
    requirements_path.write_text(
        json.dumps(requirements, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifact_hashes = {
        key: hashlib.sha256((root / relpath).read_bytes()).hexdigest()
        for key, relpath in _ARTIFACT_RELPATHS.items()
    }
    local_context = {
        **source,
        "root": root,
        "requirements": requirements,
        "artifact_hashes": artifact_hashes,
    }
    solution = dict(source["base_solution"])
    production = PortBindingModel(
        placement_solution=solution,
        facility_pools=source["facility_pools"],
        instances=source["instances"],
        project_root=root,
        required_generic_outputs=requirements["required_generic_outputs"],
        required_generic_inputs=requirements["required_generic_inputs"],
        generic_input_slots_by_operation=source["input_map"],
        generic_output_slots_by_operation=source["output_map"],
        utility_operation_by_template=source["utility_operation_map"],
        canonical_rules_payload=source["rules"],
    )
    production.build(use_overload_separation=False)
    assert production.solve(time_limit_seconds=30.0) == "INFEASIBLE"
    semantics_contract = _observed_semantics_contract(local_context, production)

    verdict = reverify_whole_layout_infeasibility(
        solution=solution,
        facility_pools=source["facility_pools"],
        instances=source["instances"],
        project_root=root,
        proof_stage="binding",
        binding_exhausted=True,
        routing_exhausted=False,
        binding_kwargs={
            "required_generic_outputs": requirements["required_generic_outputs"],
            "required_generic_inputs": requirements["required_generic_inputs"],
            "generic_input_slots_by_operation": source["input_map"],
            "generic_output_slots_by_operation": source["output_map"],
            "utility_operation_by_template": source["utility_operation_map"],
            "canonical_rules_payload": source["rules"],
        },
        artifact_hashes=artifact_hashes,
        binding_semantics_contract=semantics_contract,
        time_limit_seconds=30.0,
    )

    assert verdict.confirmed is True
    assert verdict.status == "CONFIRMED_INFEASIBLE"
    assert verdict.independent_status == "ARITHMETIC_INFEASIBLE"
    assert verdict.details["certificate_check"]["ok"] is True
    assert verdict.details["certificate"]["deficits"] == [
        {
            "side": "generic_output",
            "required_positive_slots": 53,
            "physical_slots": 52,
            "deficit": 1,
        }
    ]
