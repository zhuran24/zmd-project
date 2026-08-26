#!/usr/bin/env python3
"""E031: exact bounded multi-footprint operation-assignment neighborhoods."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
RECORDS_PATH = OUT / "ASSIGNMENT_RECORDS.json"

E030_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E030_operation_swap_portfolio/run-001/RESULT.json"
)
E030_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E030_operation_swap_portfolio/run-001/BEST_SWAP_ASSIGNMENT.json"
)
E030_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E030_operation_swap_portfolio/run-001/BEST_SWAP_LAYOUT.json"
)
E030_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E030_operation_swap_portfolio/run-001/BEST_SWAP_ENDPOINT.json"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
)
E002_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py"
)
E004_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E004_component_mismatch_atlas/run_e004.py"
)
E013_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E013_residual_boundary_coverage/run_e013.py"
)
E014_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E014_fixed_outside_mobility/run_e014.py"
)
E015_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E015_shared_binding_gradient/run_e015.py"
)
E027_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E027_final_unary_discriminator/run_e027.py"
)
E029_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E029_operation_assignment_surface/run_e029.py"
)
E030_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E030_operation_swap_portfolio/run_e030.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "263100",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E030_RESULT: "2a5c71bd0f6f15a27730c51fd19059efcb14b6aaf63948cc932e7390ccff6b57",
    E030_ASSIGNMENT: "a6370b2d5fb51416ea9c0825e19c5a526c6b33fa50ccb3a4c52ed3e570d1cd7f",
    E030_LAYOUT: "0116b2ecf8c709fd43e8cb5d8ccb3730c5447634a138c1486410b71ab4da396c",
    E030_ENDPOINT: "6f0bcec132a08159bffb5bb655f4378cb70b71f6398280941d835305022f1b23",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E029_RUNNER: "08672e533d4d73e50a411703c41017b058521ff2a9d4e6f53c2235343cef46bf",
    E030_RUNNER: "c2d2347b349addc4388fb6668ec6ac82180c90448fc834db6bf399f84f014c4a",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
    HISTORY_ROOT / "rules/canonical_rules.json": (
        "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0"
    ),
    HISTORY_ROOT / "rules/preprocess_plan.json": (
        "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee"
    ),
}

PARENT_OBJECTIVE = 163
NEIGHBORHOOD_SIZE = 5
MATERIAL_IMPROVEMENT = 2
FACILITY_TYPES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
    )


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E031 must run on research/main")
    mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    unexpected_exact = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, "
            f"unexpected_exact={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(
                f"frozen identity drift for {path}: {actual} != {expected}"
            )
    result = load_json(E030_RESULT)
    if result.get("verdict") != "OPERATION_SWAP_PORTFOLIO_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E030 trigger verdict drift")
    if int(result["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E030 objective drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output(
            "status", "--porcelain=v1", "--untracked-files=no"
        ),
    }


def load_parent() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, Any],
    Mapping[str, Sequence[Mapping[str, Any]]],
    list[Mapping[str, Any]],
    dict[str, Any],
]:
    assignment = load_json(E030_ASSIGNMENT)
    layout = load_json(E030_LAYOUT)
    endpoint = load_json(E030_ENDPOINT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E030 assignment/layout structure drift")
    solution = {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }
    layout_solution = {
        str(row["instance_id"]): dict(row)
        for row in placements
        if isinstance(row, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E030 assignment/layout content drift")
    result = load_json(E030_RESULT)
    if stable_digest(solution) != str(result["best_child"]["placement_digest"]):
        raise RuntimeError("E030 placement digest drift")
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != 163:
        raise RuntimeError("E030 endpoint objective drift")
    if str(endpoint["selection_digest"]) != str(
        result["best_child"]["binding_selection_digest"]
    ):
        raise RuntimeError("E030 endpoint selection digest drift")
    candidate_payload = load_json(
        HISTORY_ROOT / "data/preprocessed/candidate_placements.json"
    )
    pools = candidate_payload.get("facility_pools")
    if not isinstance(pools, Mapping):
        raise RuntimeError("candidate placement pools drift")
    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    if not isinstance(mandatory, list):
        raise RuntimeError("mandatory instances drift")
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(generic, Mapping):
        raise RuntimeError("generic I/O payload drift")
    return solution, endpoint, pools, mandatory, dict(generic)


def exact_neighborhood(
    *,
    facility_type: str,
    observations: Sequence[Mapping[str, Any]],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
) -> dict[str, Any]:
    keys = sorted(
        key
        for key, payload in literals.items()
        if str(payload.get("kind")) == "mandatory_group_pose"
        and str(payload.get("facility_type")) == facility_type
        and len(payload.get("source_instance_ids", [])) == 1
    )
    if len(keys) < NEIGHBORHOOD_SIZE:
        raise RuntimeError(f"E031 insufficient literals for {facility_type}")
    operations = sorted({str(literals[key]["operation_type"]) for key in keys})

    def build_model() -> tuple[
        cp_model.CpModel,
        dict[str, cp_model.IntVar],
        list[cp_model.IntVar],
        dict[str, cp_model.IntVar],
    ]:
        model = cp_model.CpModel()
        select = {
            key: model.NewBoolVar(f"select_{index}")
            for index, key in enumerate(keys)
        }
        cover: list[cp_model.IntVar] = []
        for observation_id in range(len(observations)):
            candidates = [
                select[key]
                for key in keys
                if observation_id in observation_ids_by_literal.get(key, set())
            ]
            variable = model.NewBoolVar(f"cover_{observation_id}")
            if candidates:
                model.AddMaxEquality(variable, candidates)
            else:
                model.Add(variable == 0)
            cover.append(variable)
        op_present: dict[str, cp_model.IntVar] = {}
        for op_index, operation in enumerate(operations):
            candidates = [
                select[key]
                for key in keys
                if str(literals[key]["operation_type"]) == operation
            ]
            variable = model.NewBoolVar(f"operation_{op_index}")
            model.AddMaxEquality(variable, candidates)
            op_present[operation] = variable
        model.Add(sum(select.values()) == NEIGHBORHOOD_SIZE)
        return model, select, cover, op_present

    stage1, select1, cover1, _ops1 = build_model()
    stage1.Maximize(sum(cover1))
    solver1 = cp_model.CpSolver()
    solver1.parameters.num_search_workers = 1
    solver1.parameters.max_time_in_seconds = 30
    solver1.parameters.random_seed = 31001
    status1 = solver1.Solve(stage1)
    if status1 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E031 {facility_type} coverage not OPTIMAL: {solver1.StatusName(status1)}"
        )
    optimum_coverage = int(round(solver1.ObjectiveValue()))

    stage2, select2, cover2, op_present2 = build_model()
    stage2.Add(sum(cover2) == optimum_coverage)
    stage2.Maximize(sum(op_present2.values()))
    solver2 = cp_model.CpSolver()
    solver2.parameters.num_search_workers = 1
    solver2.parameters.max_time_in_seconds = 30
    solver2.parameters.random_seed = 31002
    status2 = solver2.Solve(stage2)
    if status2 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E031 {facility_type} diversity not OPTIMAL: {solver2.StatusName(status2)}"
        )
    optimum_diversity = int(round(solver2.ObjectiveValue()))

    stage3, select3, cover3, op_present3 = build_model()
    stage3.Add(sum(cover3) == optimum_coverage)
    stage3.Add(sum(op_present3.values()) == optimum_diversity)
    stage3.Minimize(
        sum((index + 1) * select3[key] for index, key in enumerate(keys))
    )
    solver3 = cp_model.CpSolver()
    solver3.parameters.num_search_workers = 1
    solver3.parameters.max_time_in_seconds = 30
    solver3.parameters.random_seed = 31003
    status3 = solver3.Solve(stage3)
    if status3 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E031 {facility_type} tie-break not OPTIMAL: {solver3.StatusName(status3)}"
        )
    selected = [key for key in keys if solver3.Value(select3[key]) == 1]
    selected_payloads = [json_safe(literals[key]) for key in selected]
    current_operations = [str(literals[key]["operation_type"]) for key in selected]
    counts = Counter(current_operations)
    semantic_permutation_count = math.factorial(len(current_operations))
    for count in counts.values():
        semantic_permutation_count //= math.factorial(count)
    return {
        "facility_type": facility_type,
        "eligible_literal_count": len(keys),
        "selected_literal_count": len(selected),
        "covered_observation_count": optimum_coverage,
        "coverage_fraction": optimum_coverage / len(observations),
        "operation_diversity": optimum_diversity,
        "operation_multiset": dict(sorted(counts.items())),
        "semantic_permutation_count_including_identity": semantic_permutation_count,
        "selected_literals": selected,
        "selected_literal_payloads": selected_payloads,
        "selection_digest": stable_digest(selected_payloads),
    }


def exchangeability_audit(
    *,
    neighborhoods: Sequence[Mapping[str, Any]],
    mandatory: Sequence[Mapping[str, Any]],
    generic: Mapping[str, Any],
) -> dict[str, Any]:
    mandatory_by_id = {str(row["instance_id"]): dict(row) for row in mandatory}
    generic_inputs = dict(generic.get("required_generic_inputs", {}))
    generic_outputs = dict(generic.get("required_generic_outputs", {}))
    operation_rows: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in mandatory:
        operation_rows[(str(row["facility_type"]), str(row["operation_type"]))].append(
            str(row["instance_id"])
        )
    audited: list[dict[str, Any]] = []
    for neighborhood in neighborhoods:
        for operation in sorted(neighborhood["operation_multiset"]):
            key = (str(neighborhood["facility_type"]), operation)
            instance_ids = sorted(operation_rows[key])
            signatures: dict[str, str] = {}
            for instance_id in instance_ids:
                row = mandatory_by_id[instance_id]
                signature = {
                    "mandatory": {
                        field: value
                        for field, value in row.items()
                        if field != "instance_id"
                    },
                    "generic_inputs": generic_inputs.get(instance_id, {}),
                    "generic_outputs": generic_outputs.get(instance_id, {}),
                }
                signatures[instance_id] = stable_digest(signature)
            distinct = sorted(set(signatures.values()))
            if len(distinct) != 1:
                raise RuntimeError(
                    f"E031 non-exchangeable mandatory group: {key} {distinct}"
                )
            audited.append(
                {
                    "facility_type": key[0],
                    "operation_type": key[1],
                    "global_instance_count": len(instance_ids),
                    "semantic_signature": distinct[0],
                }
            )
    unique_rows = {
        (row["facility_type"], row["operation_type"]): row for row in audited
    }
    return {
        "status": "PASS",
        "audited_operation_group_count": len(unique_rows),
        "groups": [unique_rows[key] for key in sorted(unique_rows)],
        "statement": (
            "Named instances are quotiented only within mandatory operation groups "
            "whose metadata and generic-I/O obligations are byte-equivalent."
        ),
    }


def semantic_permutations(
    neighborhood: Mapping[str, Any],
) -> list[tuple[str, ...]]:
    operations = [
        str(payload["operation_type"])
        for payload in neighborhood["selected_literal_payloads"]
    ]
    identity = tuple(operations)
    permutations = sorted(set(itertools.permutations(operations)))
    return [permutation for permutation in permutations if permutation != identity]


def realize_assignment(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    neighborhood: Mapping[str, Any],
    operation_by_destination: Sequence[str],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    payloads = [dict(row) for row in neighborhood["selected_literal_payloads"]]
    if len(payloads) != len(operation_by_destination):
        raise RuntimeError("E031 permutation width drift")
    source_ids_by_operation: dict[str, list[str]] = defaultdict(list)
    destination_indices_by_operation: dict[str, list[int]] = defaultdict(list)
    for index, payload in enumerate(payloads):
        source_ids = [str(value) for value in payload["source_instance_ids"]]
        if len(source_ids) != 1:
            raise RuntimeError("E031 selected literal lacks one concrete source")
        source_id = source_ids[0]
        source_row = parent.get(source_id)
        if source_row is None:
            raise RuntimeError(f"E031 source missing from parent: {source_id}")
        if int(source_row["pose_idx"]) != int(payload["pose_idx"]):
            raise RuntimeError(f"E031 source pose drift: {source_id}")
        source_ids_by_operation[str(source_row["operation_type"])].append(source_id)
        destination_indices_by_operation[str(operation_by_destination[index])].append(index)
    if {
        key: len(value) for key, value in source_ids_by_operation.items()
    } != {
        key: len(value) for key, value in destination_indices_by_operation.items()
    }:
        raise RuntimeError("E031 operation multiset drift")

    child = {str(key): dict(value) for key, value in parent.items()}
    facility_type = str(neighborhood["facility_type"])
    assigned_sources: set[str] = set()
    for operation in sorted(source_ids_by_operation):
        sources = sorted(source_ids_by_operation[operation])
        destinations = sorted(destination_indices_by_operation[operation])
        for source_id, destination_index in zip(sources, destinations, strict=True):
            payload = payloads[destination_index]
            pose_idx = int(payload["pose_idx"])
            pose = pools[facility_type][pose_idx]
            source_row = parent[source_id]
            child[source_id] = e014.replacement_row(
                source=source_row,
                pose=pose,
                pose_idx=pose_idx,
                instance_id=source_id,
            )
            assigned_sources.add(source_id)
    expected_sources = {
        str(value)
        for payload in payloads
        for value in payload["source_instance_ids"]
    }
    if assigned_sources != expected_sources:
        raise RuntimeError("E031 source assignment coverage drift")
    return child


def compact_shared(shared: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": shared.get("status"),
        "objective": shared.get("objective"),
        "selection_digest": shared.get("selection_digest"),
        "port_specs_digest": shared.get("port_specs_digest"),
        "per_commodity": json_safe(shared.get("per_commodity", {})),
        "selected_components": json_safe(shared.get("selected_components", {})),
        "positive_commodity_count": shared.get("positive_commodity_count"),
        "zero_mismatch_commodities": json_safe(
            shared.get("zero_mismatch_commodities", [])
        ),
        "morphology": json_safe(shared.get("morphology", {})),
        "filtered_binding_option_count": shared.get(
            "filtered_binding_option_count"
        ),
        "empty_filtered_domains": json_safe(
            shared.get("empty_filtered_domains", [])
        ),
    }


def arm_path(facility_type: str) -> Path:
    suffix = facility_type.removeprefix("manufacturing_")
    return OUT / f"ARM_{suffix}.json"


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e031_e001", E001_RUNNER)
    e002 = import_module("zmd_e031_e002", E002_RUNNER)
    e004 = import_module("zmd_e031_e004", E004_RUNNER)
    e013 = import_module("zmd_e031_e013", E013_RUNNER)
    e014 = import_module("zmd_e031_e014", E014_RUNNER)
    e015 = import_module("zmd_e031_e015", E015_RUNNER)
    e027 = import_module("zmd_e031_e027", E027_RUNNER)
    e029 = import_module("zmd_e031_e029", E029_RUNNER)

    parent, endpoint, pools, mandatory, generic = load_parent()
    e029.OBJECTIVE = PARENT_OBJECTIVE
    group_by_instance = e013.group_mapping(mandatory)
    observations, literals, observation_ids_by_literal = e029.build_incidence(
        solution=parent,
        endpoint=endpoint,
        pools=pools,
        group_by_instance=group_by_instance,
        e013=e013,
    )
    neighborhoods = [
        exact_neighborhood(
            facility_type=facility_type,
            observations=observations,
            literals=literals,
            observation_ids_by_literal=observation_ids_by_literal,
        )
        for facility_type in FACILITY_TYPES
    ]
    exchangeability = exchangeability_audit(
        neighborhoods=neighborhoods,
        mandatory=mandatory,
        generic=generic,
    )

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    power = e014.build_power_semantics(e001, stack, inputs)
    parent_occupied, _owner_by_cell = e014.base_occupancy(parent, pools)
    parent_free_digest = str(endpoint["morphology"]["free_cell_set_digest"])
    selected_poles = {
        int(row["pose_idx"])
        for row in parent.values()
        if str(row["facility_type"]) == "power_pole"
    }

    all_records: list[dict[str, Any]] = []
    child_by_digest: dict[str, dict[str, Any]] = {}
    arm_summaries: list[dict[str, Any]] = []
    for arm_index, neighborhood in enumerate(neighborhoods, 1):
        facility_type = str(neighborhood["facility_type"])
        path = arm_path(facility_type)
        permutations = semantic_permutations(neighborhood)
        expected_count = (
            int(neighborhood["semantic_permutation_count_including_identity"]) - 1
        )
        if len(permutations) != expected_count:
            raise RuntimeError(f"E031 permutation count drift: {facility_type}")
        records: list[dict[str, Any]] = []
        local_children: dict[str, dict[str, Any]] = {}
        for candidate_index, permutation in enumerate(permutations, 1):
            child = realize_assignment(
                parent=parent,
                neighborhood=neighborhood,
                operation_by_destination=permutation,
                pools=pools,
                e014=e014,
            )
            occupied, _ = e014.base_occupancy(child, pools)
            if occupied != parent_occupied:
                raise RuntimeError(
                    f"E031 assignment changed occupancy: {facility_type}"
                )
            if not e014.all_powered_facilities_covered(
                solution=child,
                selected_poles=selected_poles,
                powered_templates=power["powered_templates"],
                coverers=power["coverers"],
            ):
                raise RuntimeError(f"E031 assignment broke power: {facility_type}")
            digest = stable_digest(child)
            local_children[digest] = child
            try:
                shared = e015.solve_shared_mismatch(
                    solution=child,
                    inputs=inputs,
                    e004=e004,
                    random_seed=271000 + 1000 * arm_index + candidate_index,
                    include_boundaries=False,
                )
            except RuntimeError as exc:
                if "empty binding domain" not in str(exc):
                    raise
                diagnostic = e014.screen_component_interface(
                    solution=child,
                    inputs=inputs,
                    e001=e001,
                    e002=e002,
                )
                if diagnostic.get("status") != "PORT_DOMAIN_EMPTY":
                    raise RuntimeError(
                        "E031 empty-domain exception was not reproduced: "
                        f"{diagnostic.get('status')}"
                    )
                shared = {
                    "status": "PORT_DOMAIN_EMPTY",
                    "objective": None,
                    "detail": str(exc),
                    "empty_filtered_domains": diagnostic.get(
                        "empty_filtered_domains", []
                    ),
                    "filtered_binding_option_count": diagnostic.get(
                        "filtered_binding_option_count"
                    ),
                    "front_blocked_patterns_pruned": diagnostic.get(
                        "front_blocked_patterns_pruned"
                    ),
                    "morphology": diagnostic.get("morphology"),
                }
            record = {
                "facility_type": facility_type,
                "candidate_index": candidate_index,
                "operation_by_destination": list(permutation),
                "candidate_solution_digest": digest,
                "shared_binding": compact_shared(shared),
            }
            records.append(record)
            child_by_digest[digest] = child
            if candidate_index % 20 == 0 or candidate_index == len(permutations):
                print(
                    json.dumps(
                        {
                            "event": "E031_ASSIGNMENT_PROGRESS",
                            "facility_type": facility_type,
                            "candidate": candidate_index,
                            "candidate_total": len(permutations),
                            "status": shared.get("status"),
                            "objective": shared.get("objective"),
                            "at_utc": utc_now(),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        checkpoint = {
            "schema": "zmd_zero_condition_e031_assignment_arm_v1",
            "created_at_utc": utc_now(),
            "runner_sha256": runner_sha256,
            "neighborhood": json_safe(neighborhood),
            "exchangeability_status": exchangeability["status"],
            "candidate_count": len(records),
            "records": records,
            "status_counts": dict(
                sorted(Counter(row["shared_binding"]["status"] for row in records).items())
            ),
        }
        dump_exclusive(path, checkpoint)
        optimal = [
            row for row in records if row["shared_binding"]["status"] == "OPTIMAL"
        ]
        objectives = Counter(
            int(row["shared_binding"]["objective"]) for row in optimal
        )
        best_objective = min(objectives) if objectives else None
        arm_summaries.append(
            {
                "facility_type": facility_type,
                "candidate_count": len(records),
                "status_counts": checkpoint["status_counts"],
                "objective_distribution": {
                    str(key): value for key, value in sorted(objectives.items())
                },
                "best_objective": best_objective,
                "delta_from_parent": (
                    best_objective - PARENT_OBJECTIVE
                    if best_objective is not None
                    else None
                ),
                "checkpoint_path": str(path.relative_to(ROOT)),
                "checkpoint_sha256": sha256_file(path),
            }
        )
        all_records.extend(records)

    records_payload = {
        "schema": "zmd_zero_condition_e031_assignment_records_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "parent_objective": PARENT_OBJECTIVE,
        "parent_free_cell_set_digest": parent_free_digest,
        "neighborhoods": json_safe(neighborhoods),
        "exchangeability_audit": exchangeability,
        "record_count": len(all_records),
        "records": all_records,
        "ledger_effect": "none",
    }
    dump_exclusive(RECORDS_PATH, records_payload)

    status_counts = Counter(
        str(record["shared_binding"]["status"]) for record in all_records
    )
    optimal = [
        record
        for record in all_records
        if record["shared_binding"]["status"] == "OPTIMAL"
    ]
    common = {
        "schema": "zmd_zero_condition_e031_bounded_assignment_neighborhood_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "power_semantics": power["summary"],
        "parent_objective": PARENT_OBJECTIVE,
        "parent_free_cell_set_digest": parent_free_digest,
        "observation_count": len(observations),
        "literal_count": len(literals),
        "neighborhood_size": NEIGHBORHOOD_SIZE,
        "neighborhoods": json_safe(neighborhoods),
        "exchangeability_audit": exchangeability,
        "arm_summaries": arm_summaries,
        "total_candidate_count": len(all_records),
        "status_counts": dict(sorted(status_counts.items())),
        "records_path": str(RECORDS_PATH.relative_to(ROOT)),
        "records_sha256": sha256_file(RECORDS_PATH),
        "truth_boundary": (
            "Exact non-identity operation-label permutations in three selected "
            "five-footprint same-size neighborhoods under one fixed objective-163 "
            "occupied geometry."
        ),
        "ledger_effect": "none",
    }
    if not optimal:
        return {
            **common,
            "verdict": "BOUNDED_ASSIGNMENT_NEIGHBORHOODS_STATIC_REJECTED",
            "optimal_candidate_count": 0,
            "objective_distribution": {},
            "best_child": None,
            "retained_assignment_beam": [],
            "routing": {"status": "NOT_REACHED_NO_OPTIMAL_CHILD"},
            "decision": "COHABIT_OPERATION_ASSIGNMENT_AND_BINDING",
        }

    ranked = sorted(
        optimal,
        key=lambda row: (
            int(row["shared_binding"]["objective"]),
            -int(row["shared_binding"]["filtered_binding_option_count"]),
            str(row["facility_type"]),
            int(row["candidate_index"]),
        ),
    )
    best = ranked[0]
    best_digest = str(best["candidate_solution_digest"])
    best_solution = child_by_digest[best_digest]
    endpoint = e027.materialize_shared_endpoint(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=271999,
    )
    if int(endpoint["objective"]) != int(best["shared_binding"]["objective"]):
        raise RuntimeError("E031 materialized endpoint objective drift")
    if str(endpoint["morphology"]["free_cell_set_digest"]) != parent_free_digest:
        raise RuntimeError("E031 materialized child changed free-cell set")

    assignment_path = OUT / "BEST_ASSIGNMENT.json"
    layout_path = OUT / "BEST_LAYOUT.json"
    endpoint_path = OUT / "BEST_ENDPOINT.json"
    dump_exclusive(
        assignment_path,
        {
            "schema": "zmd_zero_condition_e031_best_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "facility_type": best["facility_type"],
            "operation_by_destination": best["operation_by_destination"],
            "solution": best_solution,
        },
    )
    dump_exclusive(layout_path, e001.solution_layout(best_solution))
    dump_exclusive(endpoint_path, endpoint)

    objective = int(endpoint["objective"])
    delta = objective - PARENT_OBJECTIVE
    best_ties = [
        row for row in ranked if int(row["shared_binding"]["objective"]) == objective
    ]
    retained: list[dict[str, Any]] = []
    seen_facility_types: set[str] = set()
    for row in ranked:
        if int(row["shared_binding"]["objective"]) > objective + 1:
            break
        facility_type = str(row["facility_type"])
        if facility_type in seen_facility_types:
            continue
        retained.append(
            {
                "facility_type": facility_type,
                "objective": int(row["shared_binding"]["objective"]),
                "candidate_solution_digest": row["candidate_solution_digest"],
                "selection_digest": row["shared_binding"]["selection_digest"],
                "operation_by_destination": row["operation_by_destination"],
            }
        )
        seen_facility_types.add(facility_type)

    if objective == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "BOUNDED_ASSIGNMENT_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif delta <= -MATERIAL_IMPROVEMENT:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        if len({str(row["facility_type"]) for row in best_ties}) > 1:
            verdict = "BOUNDED_ASSIGNMENT_MULTI_CLASS_TIE"
            decision = "RETAIN_ASSIGNMENT_BEAM_AND_RECOMPUTE_SURFACES"
        else:
            verdict = "BOUNDED_ASSIGNMENT_MATERIAL_IMPROVEMENT"
            decision = "RETAIN_ASSIGNMENT_CHILD_AND_RECOMPUTE_SURFACE"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "BOUNDED_ASSIGNMENT_SATURATION_SIGNAL"
        decision = "COHABIT_OPERATION_ASSIGNMENT_AND_BINDING"

    distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    return {
        **common,
        "verdict": verdict,
        "optimal_candidate_count": len(optimal),
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "top_candidates": ranked[:30],
        "best_tie_count": len(best_ties),
        "best_tie_facility_types": sorted(
            {str(row["facility_type"]) for row in best_ties}
        ),
        "retained_assignment_beam": retained,
        "best_child": {
            "objective": objective,
            "delta_from_parent": delta,
            "facility_type": best["facility_type"],
            "candidate_index": best["candidate_index"],
            "operation_by_destination": best["operation_by_destination"],
            "placement_digest": stable_digest(best_solution),
            "binding_selection_digest": endpoint["selection_digest"],
            "per_commodity": endpoint["per_commodity"],
            "positive_commodity_count": endpoint["positive_commodity_count"],
            "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
            "morphology": endpoint["morphology"],
            "filtered_binding_option_count": endpoint[
                "filtered_binding_option_count"
            ],
            "assignment_path": str(assignment_path.relative_to(ROOT)),
            "assignment_sha256": sha256_file(assignment_path),
            "layout_path": str(layout_path.relative_to(ROOT)),
            "layout_sha256": sha256_file(layout_path),
            "endpoint_path": str(endpoint_path.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(endpoint_path),
        },
        "routing": routing,
        "decision": decision,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists() or RECORDS_PATH.exists():
        raise FileExistsError("refusing to overwrite E031 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "total_candidate_count": result["total_candidate_count"],
                    "status_counts": result["status_counts"],
                    "arm_summaries": result["arm_summaries"],
                    "best_child": result.get("best_child"),
                    "decision": result["decision"],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e031_bounded_assignment_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
