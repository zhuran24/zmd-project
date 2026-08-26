#!/usr/bin/env python3
"""E033: exact common and branch-specific action replay on two objective-161 states."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E033_tied_state_action_replay/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

E032_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E032_assignment_tie_surface/run-001/RESULT.json"
)
E031_BEST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/BEST_ASSIGNMENT.json"
)
E031_BEST_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E031_bounded_assignment_neighborhood/run-001/BEST_ENDPOINT.json"
)
E032_SECOND_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E032_assignment_tie_surface/run-001/SECOND_ASSIGNMENT.json"
)
E032_SECOND_ENDPOINT = (
    ROOT
    / "research_lab/local/zero_condition/E032_assignment_tie_surface/run-001/SECOND_ENDPOINT.json"
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
E030_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E030_operation_swap_portfolio/run_e030.py"
)
E032_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E032_assignment_tie_surface/run_e032.py"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "263300",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES: dict[Path, str] = {
    E032_RESULT: "d67de72f3b971e8d5fb9bea5546392f789d367918de9ad9b0a26ebacd7a9db8c",
    E031_BEST_ASSIGNMENT: "f34bcc394835730ac3a6925fcb7ac415d2cc57f79680af0372e4f4ab394b4dcf",
    E031_BEST_ENDPOINT: "f300d618089f92fad5b55044204c4946a911702db32334714f49a0a952703087",
    E032_SECOND_ASSIGNMENT: "4780e4a269900d422494a6abe0f265ebdf8744ab24982dcab19ebdef00453de5",
    E032_SECOND_ENDPOINT: "5553653fc1182429400aacba3241d6fbc1e06db6e12cd7e10a8953cb46e37dfd",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
    E027_RUNNER: "9adf39e7817873b5f3909fe784b80f6213d6134ef9bb7d2e09bef3146c0f2704",
    E030_RUNNER: "c2d2347b349addc4388fb6668ec6ac82180c90448fc834db6bf399f84f014c4a",
    E032_RUNNER: "85969a8813401065d8fb070c6c52852c3dc84aaaf66fa38f8c491c6bede50cd2",
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

PARENT_OBJECTIVE = 161
MATERIAL_IMPROVEMENT = 2
COMMON_PAIR = (
    "mandatory::group::manufacturing_6x4::grinder_fine_buckwheat::16::7754"
    " <-> mandatory::group::manufacturing_6x4::packaging_battery::17::6018"
)
BEST_BRANCH_PAIR = (
    "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2119"
    " <-> mandatory::group::manufacturing_3x3::refinery_blue_iron::7::2963"
)
SECOND_BRANCH_PAIR = (
    "mandatory::group::manufacturing_3x3::crusher_sandleaf::3::2119"
    " <-> mandatory::group::manufacturing_3x3::crusher_source::4::2963"
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
        raise RuntimeError("E033 must run on research/main")
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
    result = load_json(E032_RESULT)
    if result.get("verdict") != "OBJECTIVE_161_SHARED_LEADER_DISTINCT_SURFACES":
        raise RuntimeError("E032 trigger verdict drift")
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


def find_action(surface: Mapping[str, Any], pair_key: str) -> dict[str, Any]:
    matches = [
        dict(row)
        for row in surface["top_raw_pairs"]
        if str(row["pair_key"]) == pair_key
    ]
    if len(matches) != 1:
        raise RuntimeError(f"E033 action lookup drift: {pair_key} count={len(matches)}")
    return matches[0]


def load_state(
    assignment_path: Path,
    endpoint_path: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    assignment = load_json(assignment_path)
    raw = assignment.get("solution")
    if not isinstance(raw, Mapping):
        raise RuntimeError(f"E033 assignment drift: {assignment_path}")
    solution = {
        str(instance_id): dict(row)
        for instance_id, row in raw.items()
        if isinstance(row, Mapping)
    }
    endpoint = load_json(endpoint_path)
    if endpoint.get("status") != "OPTIMAL" or int(endpoint["objective"]) != 161:
        raise RuntimeError(f"E033 endpoint drift: {endpoint_path}")
    return solution, endpoint


def compact_endpoint(endpoint: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": endpoint.get("status"),
        "objective": endpoint.get("objective"),
        "selection_digest": endpoint.get("selection_digest"),
        "port_specs_digest": endpoint.get("port_specs_digest"),
        "per_commodity": json_safe(endpoint.get("per_commodity", {})),
        "selected_components": json_safe(endpoint.get("selected_components", {})),
        "positive_commodity_count": endpoint.get("positive_commodity_count"),
        "zero_mismatch_commodities": json_safe(
            endpoint.get("zero_mismatch_commodities", [])
        ),
        "morphology": json_safe(endpoint.get("morphology", {})),
        "filtered_binding_option_count": endpoint.get(
            "filtered_binding_option_count"
        ),
    }


def output_stem(state_name: str, action_name: str) -> str:
    return f"{state_name.upper()}_{action_name.upper()}"


def run() -> dict[str, Any]:
    identity = verify_identity()
    e001 = import_module("zmd_e033_e001", E001_RUNNER)
    e002 = import_module("zmd_e033_e002", E002_RUNNER)
    e004 = import_module("zmd_e033_e004", E004_RUNNER)
    e014 = import_module("zmd_e033_e014", E014_RUNNER)
    e015 = import_module("zmd_e033_e015", E015_RUNNER)
    e027 = import_module("zmd_e033_e027", E027_RUNNER)
    e030 = import_module("zmd_e033_e030", E030_RUNNER)

    first_solution, first_endpoint = load_state(
        E031_BEST_ASSIGNMENT,
        E031_BEST_ENDPOINT,
    )
    second_solution, second_endpoint = load_state(
        E032_SECOND_ASSIGNMENT,
        E032_SECOND_ENDPOINT,
    )
    e032 = load_json(E032_RESULT)
    first_surface = e032["swap_surfaces"]["best_materialized_state"]
    second_surface = e032["swap_surfaces"]["second_tied_state"]
    actions = [
        {
            "state_name": "first",
            "action_name": "common",
            "parent_solution": first_solution,
            "parent_endpoint": first_endpoint,
            "action": find_action(first_surface, COMMON_PAIR),
        },
        {
            "state_name": "second",
            "action_name": "common",
            "parent_solution": second_solution,
            "parent_endpoint": second_endpoint,
            "action": find_action(second_surface, COMMON_PAIR),
        },
        {
            "state_name": "first",
            "action_name": "branch",
            "parent_solution": first_solution,
            "parent_endpoint": first_endpoint,
            "action": find_action(first_surface, BEST_BRANCH_PAIR),
        },
        {
            "state_name": "second",
            "action_name": "branch",
            "parent_solution": second_solution,
            "parent_endpoint": second_endpoint,
            "action": find_action(second_surface, SECOND_BRANCH_PAIR),
        },
    ]

    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    power = e014.build_power_semantics(e001, stack, inputs)
    records: list[dict[str, Any]] = []
    retained_solutions: dict[str, dict[str, dict[str, Any]]] = {}
    for index, row in enumerate(actions, 1):
        state_name = str(row["state_name"])
        action_name = str(row["action_name"])
        parent_solution = row["parent_solution"]
        parent_endpoint = row["parent_endpoint"]
        action = row["action"]
        child = e030.swap_solution(
            parent=parent_solution,
            action=action,
            inputs=inputs,
            e014=e014,
        )
        parent_occupied, _ = e014.base_occupancy(parent_solution, inputs["pools"])
        child_occupied, _ = e014.base_occupancy(child, inputs["pools"])
        if child_occupied != parent_occupied:
            raise RuntimeError("E033 operation swap changed occupied geometry")
        selected_poles = {
            int(item["pose_idx"])
            for item in child.values()
            if str(item["facility_type"]) == "power_pole"
        }
        if not e014.all_powered_facilities_covered(
            solution=child,
            selected_poles=selected_poles,
            powered_templates=power["powered_templates"],
            coverers=power["coverers"],
        ):
            raise RuntimeError("E033 operation swap broke power")
        try:
            shared = e015.solve_shared_mismatch(
                solution=child,
                inputs=inputs,
                e004=e004,
                random_seed=273000 + index,
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
                    "E033 empty-domain exception was not reproduced: "
                    f"{diagnostic.get('status')}"
                )
            shared = {
                "status": "PORT_DOMAIN_EMPTY",
                "objective": None,
                "empty_filtered_domains": diagnostic.get(
                    "empty_filtered_domains", []
                ),
                "filtered_binding_option_count": diagnostic.get(
                    "filtered_binding_option_count"
                ),
                "morphology": diagnostic.get("morphology"),
            }
        record: dict[str, Any] = {
            "state_name": state_name,
            "action_name": action_name,
            "parent_objective": int(parent_endpoint["objective"]),
            "pair_key": action["pair_key"],
            "union_coverage": action["union_coverage"],
            "candidate_solution_digest": stable_digest(child),
            "shared_binding": e030.compact_shared(shared),
        }
        if shared.get("status") == "OPTIMAL":
            endpoint = e027.materialize_shared_endpoint(
                solution=child,
                inputs=inputs,
                e004=e004,
                e015=e015,
                random_seed=273500 + index,
            )
            if int(endpoint["objective"]) != int(shared["objective"]):
                raise RuntimeError("E033 endpoint materialization objective drift")
            stem = output_stem(state_name, action_name)
            assignment_path = OUT / f"{stem}_ASSIGNMENT.json"
            layout_path = OUT / f"{stem}_LAYOUT.json"
            endpoint_path = OUT / f"{stem}_ENDPOINT.json"
            dump_exclusive(
                assignment_path,
                {
                    "schema": "zmd_zero_condition_e033_action_assignment_v1",
                    "created_at_utc": utc_now(),
                    "authority": "research_only_noncertified",
                    "state_name": state_name,
                    "action_name": action_name,
                    "pair_key": action["pair_key"],
                    "objective": int(endpoint["objective"]),
                    "solution": child,
                },
            )
            dump_exclusive(layout_path, e001.solution_layout(child))
            dump_exclusive(endpoint_path, endpoint)
            record["materialized"] = {
                "assignment_path": str(assignment_path.relative_to(ROOT)),
                "assignment_sha256": sha256_file(assignment_path),
                "layout_path": str(layout_path.relative_to(ROOT)),
                "layout_sha256": sha256_file(layout_path),
                "endpoint_path": str(endpoint_path.relative_to(ROOT)),
                "endpoint_sha256": sha256_file(endpoint_path),
                "endpoint": compact_endpoint(endpoint),
            }
            retained_solutions[f"{state_name}:{action_name}"] = child
        records.append(record)

    by_key = {
        (str(row["state_name"]), str(row["action_name"])): row for row in records
    }
    common_values = [
        by_key[(state, "common")]["shared_binding"].get("objective")
        for state in ("first", "second")
    ]
    branch_values = [
        by_key[(state, "branch")]["shared_binding"].get("objective")
        for state in ("first", "second")
    ]
    common_equal = common_values[0] == common_values[1]
    branch_equal = branch_values[0] == branch_values[1]
    optimal_records = [
        row for row in records if row["shared_binding"]["status"] == "OPTIMAL"
    ]
    best_objective = min(
        int(row["shared_binding"]["objective"]) for row in optimal_records
    ) if optimal_records else None
    zero_records = [
        row
        for row in optimal_records
        if int(row["shared_binding"]["objective"]) == 0
    ]
    routing: dict[str, Any] = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}
    if zero_records:
        zero = zero_records[0]
        child = retained_solutions[
            f"{zero['state_name']}:{zero['action_name']}"
        ]
        routing = e014.screen_component_interface(
            solution=child,
            inputs=inputs,
            e001=e001,
            e002=e002,
        )
        verdict = "TIED_STATE_ACTION_COMPONENT_CANDIDATE"
        decision = "ENTER_EXACT_ROUTING"
    elif best_objective is None:
        verdict = "TIED_STATE_ACTIONS_STATIC_REJECTED"
        decision = "COHABIT_OPERATION_ASSIGNMENT_AND_BINDING"
    elif best_objective <= PARENT_OBJECTIVE - MATERIAL_IMPROVEMENT:
        if common_equal and branch_equal:
            verdict = "TIED_STATE_ACTION_FAMILY_VALUE_EQUIVALENT_WITH_GAIN"
            decision = "QUOTIENT_FOR_ACTION_FAMILY_AND_RETAIN_BEST_CHILD"
        elif common_equal:
            verdict = "COMMON_VALUE_SHARED_BRANCH_VALUE_DIVERGES_WITH_GAIN"
            decision = "RETAIN_BRANCH_BEAM_AND_BEST_CHILDREN"
        else:
            verdict = "TIED_STATE_CONTINUATION_DIVERGES_WITH_GAIN"
            decision = "RETAIN_BRANCH_BEAM_AND_BEST_CHILDREN"
    else:
        verdict = "TIED_STATE_ACTION_FAMILY_SATURATION_SIGNAL"
        decision = "COHABIT_OPERATION_ASSIGNMENT_AND_BINDING"

    response = {
        "common_values": common_values,
        "branch_values": branch_values,
        "common_equal": common_equal,
        "branch_equal": branch_equal,
        "best_objective": best_objective,
        "best_delta": (
            best_objective - PARENT_OBJECTIVE
            if best_objective is not None
            else None
        ),
    }
    distribution = Counter(
        int(row["shared_binding"]["objective"]) for row in optimal_records
    )
    return {
        "schema": "zmd_zero_condition_e033_tied_state_action_replay_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "power_semantics": power["summary"],
        "parent_objective": PARENT_OBJECTIVE,
        "action_records": records,
        "status_counts": dict(
            sorted(Counter(row["shared_binding"]["status"] for row in records).items())
        ),
        "objective_distribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "response_comparison": response,
        "routing": routing,
        "decision": decision,
        "truth_boundary": (
            "Four exact occupancy-preserving two-footprint action responses under "
            "two frozen objective-161 assignment/binding parents."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E033 outputs")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "response_comparison": result["response_comparison"],
                    "status_counts": result["status_counts"],
                    "objective_distribution": result["objective_distribution"],
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
            "schema": "zmd_zero_condition_e033_tied_state_action_replay_failure_v1",
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
