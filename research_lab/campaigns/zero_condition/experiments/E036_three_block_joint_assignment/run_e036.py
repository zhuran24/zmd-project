#!/usr/bin/env python3
"""E036: add a residual-selected 5x5 block to the live 3x3+6x4 joint model."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
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
OUT = ROOT / "research_lab/local/zero_condition/E036_three_block_joint_assignment/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
JOINT_WITNESS_PATH = OUT / "JOINT_WITNESS.json"
BEST_ASSIGNMENT_PATH = OUT / "BEST_ASSIGNMENT.json"
BEST_LAYOUT_PATH = OUT / "BEST_LAYOUT.json"
BEST_ENDPOINT_PATH = OUT / "BEST_ENDPOINT.json"

E035_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E035_cross_block_joint_assignment/run-001/RESULT.json"
)
FIRST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E035_cross_block_joint_assignment/run-001/BEST_ASSIGNMENT.json"
)
FIRST_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E035_cross_block_joint_assignment/run-001/BEST_ENDPOINT.json"
)
SECOND_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001/SECOND_COMMON_ASSIGNMENT.json"
)
SECOND_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001/SECOND_COMMON_ENDPOINT.json"
)
E035_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E035_cross_block_joint_assignment/run_e035.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "266000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E035_RESULT: "f2f0939b4fcdcc1b1be8896ad7406b22251a87e807c8b496ef6adf5c4c044b02",
    FIRST_ASSIGNMENT: "1255029fce0320edd0ddb736ba5100bfbc6f5ac19a75c3d27181ba157d0e8efb",
    FIRST_ENDPOINT: "d21066373c9553e9f80e80cc3642cb1ac559facde8a483a2dfc4085b56b3ecdb",
    SECOND_ASSIGNMENT: "aaa21b02f772a955921e0e8e7fefa467ae5a84c9cb834d2b31de9278320cbeaa",
    SECOND_ENDPOINT: "ab184e28e69326b40f1e5d973d64096ec3436b83fe890390b1804a22ee0f7e30",
    E035_RUNNER: "01bee53fb2e90e80a2cad6eaf363b865473bd9c92dfe5800b9475287af2b4bcf",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
}

PARENT_OBJECTIVE = 159
BLOCK_SIZE = 5
CALIBRATION_SECONDS = 45.0
FREE_SOLVE_SECONDS = 180.0


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
        raise RuntimeError("E036 must run on research/main")
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
    result = load_json(E035_RESULT)
    if result.get("verdict") != "CROSS_BLOCK_JOINT_MATERIAL_IMPROVEMENT":
        raise RuntimeError("E035 trigger verdict drift")
    if int(result["best_child"]["objective"]) != PARENT_OBJECTIVE:
        raise RuntimeError("E035 objective drift")
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


def select_5x5_block(
    *,
    live_blocks: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    literals: Mapping[str, Mapping[str, Any]],
    observation_ids_by_literal: Mapping[str, set[int]],
) -> dict[str, Any]:
    current_pose_indices: dict[str, set[int]] = {}
    base_keys: list[str] = []
    for block in live_blocks:
        facility_type = str(block["facility_type"])
        pose_indices = {
            int(payload["pose_idx"])
            for payload in block["selected_literal_payloads"]
        }
        current_pose_indices.setdefault(facility_type, set()).update(pose_indices)
        keys = [
            key
            for key, payload in literals.items()
            if str(payload.get("facility_type")) == facility_type
            and int(payload.get("pose_idx", -1)) in pose_indices
        ]
        if len(keys) != len(pose_indices):
            raise RuntimeError(
                f"E036 current block literal count drift {block['block_id']}: "
                f"{len(keys)} != {len(pose_indices)}"
            )
        base_keys.extend(keys)
    base_covered: set[int] = set()
    for key in base_keys:
        base_covered |= set(observation_ids_by_literal.get(key, set()))

    facility_type = "manufacturing_5x5"
    keys = sorted(
        key
        for key, payload in literals.items()
        if str(payload.get("kind")) == "mandatory_group_pose"
        and str(payload.get("facility_type")) == facility_type
        and len(payload.get("source_instance_ids", [])) == 1
        and int(payload.get("pose_idx", -1))
        not in current_pose_indices.get(facility_type, set())
    )
    if len(keys) < BLOCK_SIZE:
        raise RuntimeError("E036 insufficient 5x5 residual literals")
    operations = sorted({str(literals[key]["operation_type"]) for key in keys})

    def build_model() -> tuple[
        cp_model.CpModel,
        dict[str, cp_model.IntVar],
        list[cp_model.IntVar],
        dict[str, cp_model.IntVar],
    ]:
        model = cp_model.CpModel()
        select = {
            key: model.NewBoolVar(f"e036_select_{index}")
            for index, key in enumerate(keys)
        }
        cover: list[cp_model.IntVar] = []
        for observation_id in range(len(observations)):
            variable = model.NewBoolVar(f"e036_cover_{observation_id}")
            if observation_id in base_covered:
                model.Add(variable == 1)
            else:
                candidates = [
                    select[key]
                    for key in keys
                    if observation_id in observation_ids_by_literal.get(key, set())
                ]
                if candidates:
                    model.AddMaxEquality(variable, candidates)
                else:
                    model.Add(variable == 0)
            cover.append(variable)
        op_present: dict[str, cp_model.IntVar] = {}
        for operation_index, operation in enumerate(operations):
            candidates = [
                select[key]
                for key in keys
                if str(literals[key]["operation_type"]) == operation
            ]
            variable = model.NewBoolVar(f"e036_operation_{operation_index}")
            model.AddMaxEquality(variable, candidates)
            op_present[operation] = variable
        model.Add(sum(select.values()) == BLOCK_SIZE)
        return model, select, cover, op_present

    stage1, select1, cover1, _ops1 = build_model()
    stage1.Maximize(sum(cover1))
    solver1 = cp_model.CpSolver()
    solver1.parameters.max_time_in_seconds = 30
    solver1.parameters.num_search_workers = 1
    solver1.parameters.random_seed = 36001
    status1 = solver1.Solve(stage1)
    if status1 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E036 5x5 marginal coverage not OPTIMAL: {solver1.StatusName(status1)}"
        )
    optimum_union = int(round(solver1.ObjectiveValue()))

    stage2, select2, cover2, op_present2 = build_model()
    stage2.Add(sum(cover2) == optimum_union)
    stage2.Maximize(sum(op_present2.values()))
    solver2 = cp_model.CpSolver()
    solver2.parameters.max_time_in_seconds = 30
    solver2.parameters.num_search_workers = 1
    solver2.parameters.random_seed = 36002
    status2 = solver2.Solve(stage2)
    if status2 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E036 5x5 diversity not OPTIMAL: {solver2.StatusName(status2)}"
        )
    optimum_diversity = int(round(solver2.ObjectiveValue()))

    stage3, select3, cover3, op_present3 = build_model()
    stage3.Add(sum(cover3) == optimum_union)
    stage3.Add(sum(op_present3.values()) == optimum_diversity)
    stage3.Minimize(
        sum((index + 1) * select3[key] for index, key in enumerate(keys))
    )
    solver3 = cp_model.CpSolver()
    solver3.parameters.max_time_in_seconds = 30
    solver3.parameters.num_search_workers = 1
    solver3.parameters.random_seed = 36003
    status3 = solver3.Solve(stage3)
    if status3 != cp_model.OPTIMAL:
        raise RuntimeError(
            f"E036 5x5 tie-break not OPTIMAL: {solver3.StatusName(status3)}"
        )
    selected = [key for key in keys if solver3.Value(select3[key]) == 1]
    payloads = [json_safe(literals[key]) for key in selected]
    current_operations = [str(payload["operation_type"]) for payload in payloads]
    counts = Counter(current_operations)
    semantic_permutations = math.factorial(BLOCK_SIZE)
    for count in counts.values():
        semantic_permutations //= math.factorial(count)
    return {
        "block_id": "5x5",
        "facility_type": facility_type,
        "eligible_literal_count": len(keys),
        "selected_literal_count": len(selected),
        "base_covered_observation_count": len(base_covered),
        "covered_observation_count_with_base": optimum_union,
        "marginal_observation_count": optimum_union - len(base_covered),
        "coverage_fraction_with_base": optimum_union / len(observations),
        "operation_diversity": optimum_diversity,
        "operation_multiset": dict(sorted(counts.items())),
        "semantic_permutation_count_including_identity": semantic_permutations,
        "selected_literals": selected,
        "selected_literal_payloads": payloads,
        "selection_digest": stable_digest(payloads),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e035 = import_module("zmd_e036_e035", E035_RUNNER)
    e001 = import_module("zmd_e036_e001", e035.E001_RUNNER)
    e002 = import_module("zmd_e036_e002", e035.E002_RUNNER)
    e004 = import_module("zmd_e036_e004", e035.E004_RUNNER)
    e013 = import_module("zmd_e036_e013", e035.E013_RUNNER)
    e014 = import_module("zmd_e036_e014", e035.E014_RUNNER)
    e015 = import_module("zmd_e036_e015", e035.E015_RUNNER)
    e027 = import_module("zmd_e036_e027", e035.E027_RUNNER)
    e031 = import_module("zmd_e036_e031", e035.E031_RUNNER)

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    first_solution = e035.solution_from_assignment(FIRST_ASSIGNMENT)
    second_solution = e035.solution_from_assignment(SECOND_ASSIGNMENT)
    first_endpoint = load_json(FIRST_ENDPOINT)
    second_endpoint = load_json(SECOND_ENDPOINT)
    if first_endpoint.get("status") != "OPTIMAL" or int(first_endpoint["objective"]) != 159:
        raise RuntimeError("E036 first warm endpoint drift")
    if second_endpoint.get("status") != "OPTIMAL" or int(second_endpoint["objective"]) != 160:
        raise RuntimeError("E036 second regression endpoint drift")

    mandatory = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    generic = load_json(
        HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json"
    )
    if not isinstance(mandatory, list) or not isinstance(generic, Mapping):
        raise RuntimeError("E036 frozen instance/generic payload drift")

    observations, literals, observation_ids_by_literal = e035.build_incidence(
        solution=first_solution,
        endpoint=first_endpoint,
        pools=inputs["pools"],
        mandatory=mandatory,
        e013=e013,
    )
    e035_result = load_json(E035_RESULT)
    base_block = dict(e035_result["base_block"])
    expansion_block = dict(e035_result["expansion_block"])
    new_block = select_5x5_block(
        live_blocks=[base_block, expansion_block],
        observations=observations,
        literals=literals,
        observation_ids_by_literal=observation_ids_by_literal,
    )
    blocks = [base_block, expansion_block, new_block]
    exchangeability = e031.exchangeability_audit(
        neighborhoods=blocks,
        mandatory=mandatory,
        generic=generic,
    )
    if exchangeability.get("status") != "PASS":
        raise RuntimeError("E036 exchangeability audit failed")

    selected_ids_by_block = {
        str(block["block_id"]): set(e035.selected_instance_ids(block))
        for block in blocks
    }
    if len(set().union(*selected_ids_by_block.values())) != sum(
        len(value) for value in selected_ids_by_block.values()
    ):
        raise RuntimeError("E036 cross-block selected instance overlap")

    calibrations: list[dict[str, Any]] = []
    for index, (label, solution, endpoint, expected_objective) in enumerate(
        (
            ("first", first_solution, first_endpoint, 159),
            ("second_regression", second_solution, second_endpoint, 160),
        ),
        1,
    ):
        fixed = {
            str(block["block_id"]): e035.operation_assignment_for_solution(
                solution=solution,
                block=block,
                selected_ids=selected_ids_by_block[str(block["block_id"])],
            )
            for block in blocks
        }
        built = e035.build_joint_model(
            full_solution=solution,
            warm_endpoint=endpoint,
            fixed_assignments=fixed,
            inputs=inputs,
            blocks=blocks,
            selected_ids_by_block=selected_ids_by_block,
            e004=e004,
            e015=e015,
        )
        solved = e035.solve_joint(
            built,
            time_limit_seconds=CALIBRATION_SECONDS,
            random_seed=36010 + index,
        )
        calibrations.append(
            {
                "label": label,
                "expected_objective": expected_objective,
                "fixed_assignments": {
                    key: list(value) for key, value in fixed.items()
                },
                "solve": {
                    key: value
                    for key, value in solved.items()
                    if key not in {"joint_selection", "joint_port_specs"}
                },
                "model_size": built["model_size"],
                "hint_stats": built["hint_stats"],
            }
        )
        if solved["status"] != "OPTIMAL" or int(solved["objective"]) != expected_objective:
            raise RuntimeError(
                f"E036 calibration failed {label}: {solved['status']} "
                f"objective={solved.get('objective')} expected={expected_objective}"
            )

    free_built = e035.build_joint_model(
        full_solution=first_solution,
        warm_endpoint=first_endpoint,
        fixed_assignments=None,
        inputs=inputs,
        blocks=blocks,
        selected_ids_by_block=selected_ids_by_block,
        e004=e004,
        e015=e015,
    )
    free_solve = e035.solve_joint(
        free_built,
        time_limit_seconds=FREE_SOLVE_SECONDS,
        random_seed=36999,
    )
    common = {
        "schema": "zmd_zero_condition_e036_three_block_joint_assignment_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "parent_objective": PARENT_OBJECTIVE,
        "observation_count": len(observations),
        "live_blocks": json_safe([base_block, expansion_block]),
        "new_block": json_safe(new_block),
        "exchangeability_audit": exchangeability,
        "selected_instance_ids_by_block": {
            key: sorted(value) for key, value in selected_ids_by_block.items()
        },
        "calibrations": calibrations,
        "model_size": free_built["model_size"],
        "domain_stats": free_built["domain_stats"],
        "hint_stats": free_built["hint_stats"],
        "free_solve": {
            key: value
            for key, value in free_solve.items()
            if key not in {"joint_selection", "joint_port_specs"}
        },
        "truth_boundary": (
            "One fixed occupied geometry; assignment and binding cohabit on "
            "five 3x3, five 6x4, and five residual-selected 5x5 footprints."
        ),
        "ledger_effect": "none",
    }
    if free_solve["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return {
            **common,
            "verdict": "THREE_BLOCK_JOINT_NONTERMINAL",
            "best_child": None,
            "routing": {"status": "NOT_REACHED_NO_FEASIBLE_JOINT_STATE"},
            "decision": "INSPECT_OR_REFORMULATE_THREE_BLOCK_MODEL",
        }

    child = e035.realize_blocks(
        parent=first_solution,
        blocks=blocks,
        operation_by_block=free_solve["operation_by_block"],
        selected_ids_by_block=selected_ids_by_block,
        pools=inputs["pools"],
        e014=e014,
    )
    first_occupied, _ = e014.base_occupancy(first_solution, inputs["pools"])
    child_occupied, _ = e014.base_occupancy(child, inputs["pools"])
    if child_occupied != first_occupied:
        raise RuntimeError("E036 concrete realization changed occupied geometry")
    selected_poles = {
        int(row["pose_idx"])
        for row in child.values()
        if str(row["facility_type"]) == "power_pole"
    }
    power = e014.build_power_semantics(e001, stack, inputs)
    if not e014.all_powered_facilities_covered(
        solution=child,
        selected_poles=selected_poles,
        powered_templates=power["powered_templates"],
        coverers=power["coverers"],
    ):
        raise RuntimeError("E036 concrete realization broke power")

    endpoint = e027.materialize_shared_endpoint(
        solution=child,
        inputs=inputs,
        e004=e004,
        e015=e015,
        random_seed=37001,
    )
    if int(endpoint["objective"]) != int(free_solve["objective"]):
        raise RuntimeError(
            "E036 joint/fixed materialization objective drift: "
            f"{free_solve['objective']} != {endpoint['objective']}"
        )

    joint_witness = {
        "schema": "zmd_zero_condition_e036_joint_witness_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "status": free_solve["status"],
        "objective": int(free_solve["objective"]),
        "operation_by_block": free_solve["operation_by_block"],
        "selected_pattern_by_block": free_solve["selected_pattern_by_block"],
        "joint_selection": free_solve["joint_selection"],
        "joint_port_specs": free_solve["joint_port_specs"],
        "per_commodity": free_solve["per_commodity"],
        "ledger_effect": "none",
    }
    dump_exclusive(JOINT_WITNESS_PATH, joint_witness)
    dump_exclusive(
        BEST_ASSIGNMENT_PATH,
        {
            "schema": "zmd_zero_condition_e036_best_assignment_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL"
            if free_solve["status"] == "OPTIMAL"
            else "FIXED_LAYOUT_SHARED_BINDING_FEASIBLE_NONTERMINAL",
            "parent_objective": PARENT_OBJECTIVE,
            "shared_mismatch_objective": int(endpoint["objective"]),
            "operation_by_block": free_solve["operation_by_block"],
            "solution": child,
        },
    )
    dump_exclusive(BEST_LAYOUT_PATH, e001.solution_layout(child))
    dump_exclusive(BEST_ENDPOINT_PATH, endpoint)

    objective = int(endpoint["objective"])
    if objective == 0:
        routing = e014.screen_component_interface(
            solution=child,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "THREE_BLOCK_JOINT_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif free_solve["status"] == "OPTIMAL" and objective < PARENT_OBJECTIVE:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "THREE_BLOCK_JOINT_MATERIAL_IMPROVEMENT"
        decision = "RECOMPUTE_RESIDUAL_FROM_THREE_BLOCK_ENDPOINT"
    elif free_solve["status"] == "OPTIMAL":
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "THREE_BLOCK_JOINT_SATURATED"
        decision = "SELECT_NEXT_CONTEXT_OR_RELEASE_GEOMETRY"
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
        verdict = "THREE_BLOCK_JOINT_FEASIBLE_NONTERMINAL"
        decision = "CONTINUE_OR_REFORMULATE_THREE_BLOCK_SOLVE"

    return {
        **common,
        "verdict": verdict,
        "best_child": {
            "objective": objective,
            "delta_from_parent": objective - PARENT_OBJECTIVE,
            "operation_by_block": free_solve["operation_by_block"],
            "placement_digest": stable_digest(child),
            "binding_selection_digest": endpoint["selection_digest"],
            "per_commodity": endpoint["per_commodity"],
            "positive_commodity_count": endpoint["positive_commodity_count"],
            "zero_mismatch_commodities": endpoint["zero_mismatch_commodities"],
            "morphology": endpoint["morphology"],
            "filtered_binding_option_count": endpoint[
                "filtered_binding_option_count"
            ],
            "joint_witness_path": str(JOINT_WITNESS_PATH.relative_to(ROOT)),
            "joint_witness_sha256": sha256_file(JOINT_WITNESS_PATH),
            "assignment_path": str(BEST_ASSIGNMENT_PATH.relative_to(ROOT)),
            "assignment_sha256": sha256_file(BEST_ASSIGNMENT_PATH),
            "layout_path": str(BEST_LAYOUT_PATH.relative_to(ROOT)),
            "layout_sha256": sha256_file(BEST_LAYOUT_PATH),
            "endpoint_path": str(BEST_ENDPOINT_PATH.relative_to(ROOT)),
            "endpoint_sha256": sha256_file(BEST_ENDPOINT_PATH),
        },
        "power_semantics": power["summary"],
        "routing": routing,
        "decision": decision,
    }


def main() -> int:
    outputs = (
        RESULT_PATH,
        FAILURE_PATH,
        JOINT_WITNESS_PATH,
        BEST_ASSIGNMENT_PATH,
        BEST_LAYOUT_PATH,
        BEST_ENDPOINT_PATH,
    )
    if any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite E036 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "parent_objective": result["parent_objective"],
                    "new_block": {
                        "marginal_observation_count": result["new_block"][
                            "marginal_observation_count"
                        ],
                        "operation_multiset": result["new_block"][
                            "operation_multiset"
                        ],
                        "selected_literals": result["new_block"][
                            "selected_literals"
                        ],
                    },
                    "calibrations": [
                        {
                            "label": row["label"],
                            "status": row["solve"]["status"],
                            "objective": row["solve"]["objective"],
                        }
                        for row in result["calibrations"]
                    ],
                    "free_status": result["free_solve"]["status"],
                    "free_objective": result["free_solve"]["objective"],
                    "model_size": result["model_size"],
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
            "schema": "zmd_zero_condition_e036_three_block_joint_assignment_failure_v1",
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
