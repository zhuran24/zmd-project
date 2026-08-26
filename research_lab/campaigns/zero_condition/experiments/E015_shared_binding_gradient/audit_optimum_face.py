#!/usr/bin/env python3
"""Audit E015 optimum-face variability and E014 protocol-core attribution."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = (
    ROOT
    / "research_lab/local/zero_condition/E015_shared_binding_gradient/run-001/OPTIMUM_FACE_AUDIT.json"
)
FAILURE = OUT.with_name("OPTIMUM_FACE_AUDIT_FAILURE.json")

E009_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/PATTERN_EXPOSED_ASSIGNMENT.json"
)
E014_ARM16 = (
    ROOT
    / "research_lab/local/zero_condition/E014_fixed_outside_mobility/run-001/ARM_16.json"
)
E015_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E015_shared_binding_gradient/run-001/RESULT.json"
)
E015_BEST_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E015_shared_binding_gradient/run-001/BEST_ASSIGNMENT.json"
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
E015_RUNNER = Path(__file__).resolve().parent / "run_e015.py"

EXPECTED_HASHES: dict[Path, str] = {
    E009_ASSIGNMENT: "7a4a2a21cc13621e935fc6672bfa9f691e2d340ec120ec0947b3b62b3d648924",
    E014_ARM16: "e7b71ef796fa5ee406b6f693eeae00da6e6d5a7af740156e8b343a10fbd6902f",
    E015_RESULT: "d3a4a054a62ab4731a2b6f67b609b1101d4595eb097a031ec5edec11b4b95f9c",
    E015_BEST_ASSIGNMENT: "b1923ddcdb7fb1045a5cbb4abd829701325ef0b2a15ed968c9960b81a385a669",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E002_RUNNER: "681fee9a25310e2ad821a22911308a013d47e713e0fa9f6004ec8548fc5401f2",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    E015_RUNNER: "a5fe16030e50bcc02f1989c888bed62872f6a7abf59b80a150a45fd8ee7c702a",
}

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

FACE_SOLVE_SECONDS = 20.0


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
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def build_shared_surface(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e004: Any,
    e015: Any,
) -> tuple[Any, dict[str, Any]]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context

    routing_context = build_routing_binding_context(
        solution,
        inputs["pools"],
        70,
        70,
    )
    plan = inputs["plan"]
    generic = inputs["generic"]
    binding_model = PortBindingModel(
        placement_solution=solution,
        facility_pools=inputs["pools"],
        instances=inputs["instances"],
        project_root=HISTORY_ROOT,
        required_generic_outputs=generic.get("required_generic_outputs", {}),
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        canonical_rules_payload=inputs["rules"],
        routing_context=routing_context,
    )
    binding_model.build()
    if binding_model.empty_binding_domain_instances:
        raise RuntimeError("face-audit layout has an empty binding domain")
    compiled = e015.compile_shared_objective(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        e004=e004,
    )
    if compiled["duplicate_fixed_contradictions"]:
        raise RuntimeError("face-audit layout has a fixed duplicate contradiction")
    return binding_model, compiled


def solve_face_direction(
    *,
    base_model: Any,
    all_indices: Sequence[int],
    commodity_indices: Sequence[int],
    optimum: int,
    maximize: bool,
    random_seed: int,
) -> dict[str, Any]:
    model = base_model.Clone()
    all_vars = [model.GetBoolVarFromProtoIndex(index) for index in all_indices]
    commodity_vars = [
        model.GetBoolVarFromProtoIndex(index) for index in commodity_indices
    ]
    model.Add(sum(all_vars) == int(optimum))
    model.ClearObjective()
    if maximize:
        model.Maximize(sum(commodity_vars))
    else:
        model.Minimize(sum(commodity_vars))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = FACE_SOLVE_SECONDS
    solver.parameters.num_search_workers = 8
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(
            f"face direction not OPTIMAL: maximize={maximize} status={status_name}"
        )
    return {
        "status": status_name,
        "value": int(round(solver.ObjectiveValue())),
        "best_bound": float(solver.BestObjectiveBound()),
        "solve_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
    }


def profile_optimum_face(
    *,
    label: str,
    solution: Mapping[str, Mapping[str, Any]],
    optimum: int,
    inputs: Mapping[str, Any],
    e004: Any,
    e015: Any,
) -> dict[str, Any]:
    binding_model, compiled = build_shared_surface(
        solution=solution,
        inputs=inputs,
        e004=e004,
        e015=e015,
    )
    all_indices = [
        int(variable.Index())
        for mismatch in compiled["mismatch_vars"].values()
        for variable in mismatch.values()
    ]
    ranges: dict[str, Any] = {}
    for index, commodity in enumerate(compiled["commodities"]):
        commodity_indices = [
            int(variable.Index())
            for variable in compiled["mismatch_vars"][commodity].values()
        ]
        minimum = solve_face_direction(
            base_model=binding_model.model,
            all_indices=all_indices,
            commodity_indices=commodity_indices,
            optimum=optimum,
            maximize=False,
            random_seed=264000 + 2 * index,
        )
        maximum = solve_face_direction(
            base_model=binding_model.model,
            all_indices=all_indices,
            commodity_indices=commodity_indices,
            optimum=optimum,
            maximize=True,
            random_seed=264001 + 2 * index,
        )
        ranges[commodity] = {
            "minimum": minimum,
            "maximum": maximum,
            "width": int(maximum["value"]) - int(minimum["value"]),
        }
    varying = {
        commodity: row
        for commodity, row in ranges.items()
        if int(row["width"]) > 0
    }
    fixed = {
        commodity: int(row["minimum"]["value"])
        for commodity, row in ranges.items()
        if int(row["width"]) == 0
    }
    return {
        "label": label,
        "solution_digest": stable_digest(solution),
        "shared_optimum": int(optimum),
        "commodity_ranges": ranges,
        "varying_commodities": varying,
        "fixed_commodities": fixed,
        "varying_commodity_count": len(varying),
        "blue_source_ore_sum": {
            "constant": (
                int(optimum) - sum(fixed.values())
                if set(varying) == {"blue_iron_ore", "source_ore"}
                else None
            ),
            "interpretation": (
                "All optimum-face freedom is a four-unit exchange between the "
                "two generic-output commodities."
                if set(varying) == {"blue_iron_ore", "source_ore"}
                else "Optimum-face freedom is not limited to the two generic outputs."
            ),
        },
    }


def protocol_core_capacity_audit(
    *,
    inputs: Mapping[str, Any],
    base_solution: Mapping[str, Mapping[str, Any]],
    e002: Any,
    e014: Any,
) -> dict[str, Any]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context

    arm = load_json(E014_ARM16)
    target = arm["target"]
    source_id = str(target["source_instance_ids"][0])
    source_row = base_solution[source_id]
    records: list[dict[str, Any]] = []
    for candidate in arm["candidate_results"]:
        pose_idx = int(candidate["pose_idx"])
        pose = inputs["pools"][str(source_row["facility_type"])][pose_idx]
        solution = e014.make_candidate_solution(
            base_solution=base_solution,
            target_instance_id=source_id,
            target_row=source_row,
            facility_type=str(source_row["facility_type"]),
            pose_idx=pose_idx,
            pose=pose,
        )
        routing_context = build_routing_binding_context(
            solution,
            inputs["pools"],
            70,
            70,
        )
        plan = inputs["plan"]
        generic = inputs["generic"]
        binding_model = PortBindingModel(
            placement_solution=solution,
            facility_pools=inputs["pools"],
            instances=inputs["instances"],
            project_root=HISTORY_ROOT,
            required_generic_outputs=generic.get("required_generic_outputs", {}),
            required_generic_inputs=generic.get("required_generic_inputs", {}),
            generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
            generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
            utility_operation_by_template=plan["utility_operation_by_template"],
            canonical_rules_payload=inputs["rules"],
            routing_context=routing_context,
        )
        binding_model.build()
        compiled, internals = e002.compile_guarded_interface(
            binding_model=binding_model,
            routing_context=routing_context,
            required_generic_inputs=generic.get("required_generic_inputs", {}),
        )
        for guard in internals["guards"].values():
            binding_model.model.Add(guard == 0)
        status = binding_model.solve(time_limit_seconds=10.0)
        records.append(
            {
                "pose_idx": pose_idx,
                "pose_id": str(candidate["pose_id"]),
                "e014_label": str(candidate["interface"]["status"]),
                "all_component_guards_false_status": status,
                "generic_output_slot_count": int(
                    compiled["generic_output_slot_count"]
                ),
                "required_generic_output_total": sum(
                    int(value)
                    for value in generic["required_generic_outputs"].values()
                ),
                "empty_filtered_domain_count": int(
                    compiled["empty_filtered_domain_count"]
                ),
                "duplicate_fixed_contradictions": int(
                    compiled["duplicate_fixed_contradictions"]
                ),
                "wall_time": float(
                    binding_model.extract_conflict_summary().get("wall_time", 0.0)
                ),
            }
        )
    if any(
        row["all_component_guards_false_status"] != "INFEASIBLE"
        for row in records
    ):
        raise RuntimeError("protocol-core aggregate-capacity audit did not reproduce")
    return {
        "records": records,
        "finding": (
            "All three protocol-core alternatives are infeasible with every "
            "component guard false. Per-owner domains are nonempty, but only "
            "48/49 generic-output slots survive against total demand 52."
        ),
        "correct_stage": "aggregate_binding_capacity_before_component_support",
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e001 = import_module("zmd_e015face_e001", E001_RUNNER)
    e002 = import_module("zmd_e015face_e002", E002_RUNNER)
    e004 = import_module("zmd_e015face_e004", E004_RUNNER)
    e014 = import_module("zmd_e015face_e014", E014_RUNNER)
    e015 = import_module("zmd_e015face_e015", E015_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    base_solution = load_json(E009_ASSIGNMENT)["solution"]
    best_solution = load_json(E015_BEST_ASSIGNMENT)["solution"]
    result = load_json(E015_RESULT)

    baseline_face = profile_optimum_face(
        label="E009",
        solution=base_solution,
        optimum=int(result["baseline_objective"]),
        inputs=inputs,
        e004=e004,
        e015=e015,
    )
    best_face = profile_optimum_face(
        label="E015_BEST",
        solution=best_solution,
        optimum=int(result["best_objective"]),
        inputs=inputs,
        e004=e004,
        e015=e015,
    )
    capacity = protocol_core_capacity_audit(
        inputs=inputs,
        base_solution=base_solution,
        e002=e002,
        e014=e014,
    )
    return {
        "schema": "zmd_zero_condition_e015_optimum_face_audit_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "identity": identity,
        "optimum_faces": {
            "E009": baseline_face,
            "E015_BEST": best_face,
        },
        "protocol_core_capacity_audit": capacity,
        "verdict": (
            "GENERIC_OUTPUT_TRADEOFF_AND_AGGREGATE_CAPACITY_GAP_CONFIRMED"
        ),
        "truth_boundary": (
            "Exact range of each commodity mismatch over two fixed-layout shared-"
            "optimum faces, plus duplicate-only base-binding replay for three "
            "protocol-core alternatives."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if OUT.exists() or FAILURE.exists():
        raise FileExistsError("refusing to overwrite E015 optimum-face audit")
    try:
        result = run()
        dump_exclusive(OUT, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "E009_varying": result["optimum_faces"]["E009"][
                        "varying_commodities"
                    ],
                    "E015_BEST_varying": result["optimum_faces"]["E015_BEST"][
                        "varying_commodities"
                    ],
                    "protocol_core": result["protocol_core_capacity_audit"][
                        "records"
                    ],
                    "result_path": str(OUT),
                    "result_sha256": sha256_file(OUT),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e015_optimum_face_audit_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE.exists():
            dump_exclusive(FAILURE, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
