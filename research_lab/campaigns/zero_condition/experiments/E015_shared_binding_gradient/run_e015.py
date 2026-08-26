#!/usr/bin/env python3
"""E015: exact shared-binding mismatch gradient over E014 unary repairs."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
OUT = ROOT / "research_lab/local/zero_condition/E015_shared_binding_gradient/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
BASELINE_PATH = OUT / "BASELINE.json"

E009_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/RESULT.json"
)
E009_ASSIGNMENT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/PATTERN_EXPOSED_ASSIGNMENT.json"
)
E009_LAYOUT = (
    ROOT
    / "research_lab/local/zero_condition/E009_selected_pattern_linearization/run-001/PATTERN_EXPOSED_LAYOUT.json"
)
E010_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E010_pattern_exposed_mismatch_delta/run-001/RESULT.json"
)
E013_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E013_residual_boundary_coverage/run-004/RESULT.json"
)
E014_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E014_fixed_outside_mobility/run-001/RESULT.json"
)
E001_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/run_experiment.py"
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

EXPECTED_HASHES: dict[Path, str] = {
    E009_RESULT: "c0bce86fd9d2871621a28c883b57f51c3e3e7b5f5efbba9b96c23ea6c55dccec",
    E009_ASSIGNMENT: "7a4a2a21cc13621e935fc6672bfa9f691e2d340ec120ec0947b3b62b3d648924",
    E009_LAYOUT: "3b23f3f801d5b06f5cde90beb7ceb5074101d2be543b141e68ab432940e70d33",
    E010_RESULT: "6e0965a159c52c6e49a5e0c8afc2a57472f8df0669d5631ed04c73749770d4fe",
    E013_RESULT: "99c029fe71c2835bd5d2f5cd16d00f324856d70ce305278e2bb3aa944cbf6fd1",
    E014_RESULT: "193a114047e3e7d5d69df2d47cc5136fc1f4f4934dd47180256f4b7b17ba287c",
    E001_RUNNER: "a7efabb0e1e4032143c29304ada17e246f17829da088e69e361b4845aafee4bf",
    E004_RUNNER: "60c67c024785fd470f4bb532c5b1a5c175b21b1a756e7174e41e0f14d595e8fc",
    E013_RUNNER: "db40603fb4d8fae64d4882a5b0100e18f9e44a0e83c259d03dd85643b248e200",
    E014_RUNNER: "9183c684f952f3b986a47d49094f8bbed923e1262c017d8216d8fbda9d5a1e51",
    ROOT / "src/models/binding_subproblem.py": "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/models/routing_subproblem.py": "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718",
    ROOT / "src/models/port_binding.py": "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53",
    ROOT / "src/search/pr2_l0_fixed_witness_core.py": "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1",
    ROOT / "src/search/exact_campaign.py": "d893e59a9f1bd573208a39905bdb7d677046f97367543958cc201a90b21d1a04",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
}

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}

GRID_W = 70
GRID_H = 70
SOLVE_CAP_SECONDS = 20.0
ROUTING_CAP_SECONDS = 180.0


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
        raise RuntimeError("E015 must run on research/main")
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

    e009 = load_json(E009_RESULT)
    e010 = load_json(E010_RESULT)
    e013 = load_json(E013_RESULT)
    e014 = load_json(E014_RESULT)
    if e009.get("verdict") != "PATTERN_EXPOSED_CANDIDATE":
        raise RuntimeError("E009 trigger drift")
    if e010.get("verdict") != "ALTERNATING_CONSTRUCTOR_SECOND_BROAD_IMPROVEMENT":
        raise RuntimeError("E010 trigger drift")
    if e013.get("verdict") != "DISPERSED_GROUP_POSE_NEIGHBORHOOD_PLAUSIBLE":
        raise RuntimeError("E013 trigger drift")
    if e014.get("verdict") != "PARTIAL_MOBILITY_COMPONENT_WALL_PERSISTS":
        raise RuntimeError("E014 trigger drift")
    if int(e014.get("aggregate_status_counts", {}).get("COMPONENT_INFEASIBLE", -1)) != 138:
        raise RuntimeError("E014 domain-valid candidate count drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": git_output("status", "--porcelain=v1", "--untracked-files=no"),
    }


def reconstruct_base_solution() -> dict[str, dict[str, Any]]:
    assignment = load_json(E009_ASSIGNMENT)
    layout = load_json(E009_LAYOUT)
    raw = assignment.get("solution")
    placements = layout.get("placements")
    if not isinstance(raw, Mapping) or not isinstance(placements, list):
        raise RuntimeError("E009 assignment/layout structure is invalid")
    solution = {
        str(instance_id): dict(record)
        for instance_id, record in raw.items()
        if isinstance(record, Mapping)
    }
    layout_solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if json_safe(solution) != json_safe(layout_solution):
        raise RuntimeError("E009 assignment and layout disagree")
    return solution


def load_arm_surface(e014: Any, inputs: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    result = load_json(E014_RESULT)
    arms: list[dict[str, Any]] = []
    arm_hashes: dict[str, str] = {}
    component_candidate_count = 0
    base_solution = reconstruct_base_solution()
    for relative in result["arm_checkpoint_paths"]:
        path = ROOT / str(relative)
        if not path.is_file():
            raise FileNotFoundError(path)
        arm = load_json(path)
        if str(arm.get("runner_sha256")) != EXPECTED_HASHES[E014_RUNNER]:
            raise RuntimeError(f"E014 arm runner drift: {path}")
        arm_hashes[str(path.relative_to(ROOT))] = sha256_file(path)
        target = arm["target"]
        source_ids = [str(value) for value in target["source_instance_ids"]]
        if not source_ids:
            raise RuntimeError(f"E014 target lacks source instance: {path}")
        target_instance_id = source_ids[0]
        target_row = base_solution.get(target_instance_id)
        if target_row is None:
            raise RuntimeError(f"E014 target absent from E009: {target_instance_id}")
        for candidate in arm["candidate_results"]:
            if candidate["interface"]["status"] != "COMPONENT_INFEASIBLE":
                continue
            pose_idx = int(candidate["pose_idx"])
            facility_type = str(target_row["facility_type"])
            pose = inputs["pools"][facility_type][pose_idx]
            solution = e014.make_candidate_solution(
                base_solution=base_solution,
                target_instance_id=target_instance_id,
                target_row=target_row,
                facility_type=facility_type,
                pose_idx=pose_idx,
                pose=pose,
            )
            digest = stable_digest(solution)
            if digest != str(candidate["candidate_solution_digest"]):
                raise RuntimeError(
                    f"E014 candidate reconstruction drift: arm={arm['arm_index']} "
                    f"pose={pose_idx}"
                )
            component_candidate_count += 1
        arms.append(arm)
    if component_candidate_count != 138:
        raise RuntimeError(
            f"reconstructed E014 candidate count drift: {component_candidate_count}"
        )
    return arms, arm_hashes


def add_duplicate_constraints(
    *,
    model: cp_model.CpModel,
    duplicate_rows: Mapping[tuple[int, int, str, str, str], Mapping[str, Any]],
) -> dict[str, int]:
    duplicate_constraint_count = 0
    duplicate_forbidden_literal_count = 0
    duplicate_fixed_contradictions = 0
    for key, row in sorted(duplicate_rows.items()):
        fixed_count = int(row["fixed_count"])
        literal_rows = row["literals"]
        if fixed_count > 1:
            suffix = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]
            contradiction = model.NewBoolVar(f"e015_dup_fixed_{suffix}")
            model.Add(contradiction == 0)
            model.Add(contradiction == 1)
            duplicate_constraint_count += 2
            duplicate_fixed_contradictions += 1
            continue
        allowed: list[Any] = []
        for index in sorted(literal_rows):
            literal = literal_rows[index]["literal"]
            multiplicity = int(literal_rows[index]["count"])
            if fixed_count == 1 or multiplicity > 1:
                model.Add(literal == 0)
                duplicate_constraint_count += 1
                duplicate_forbidden_literal_count += 1
            else:
                allowed.append(literal)
        if fixed_count == 0 and len(allowed) > 1:
            model.AddAtMostOne(allowed)
            duplicate_constraint_count += 1
    return {
        "duplicate_constraint_count": duplicate_constraint_count,
        "duplicate_forbidden_literal_count": duplicate_forbidden_literal_count,
        "duplicate_fixed_contradictions": duplicate_fixed_contradictions,
    }


def compile_shared_objective(
    *,
    binding_model: Any,
    routing_context: Any,
    required_generic_inputs: Mapping[str, Any],
    e004: Any,
) -> dict[str, Any]:
    from src.models.port_binding import (
        is_routing_visible_output_commodity,
        routing_free_sink_commodities_from_generic_inputs,
    )
    from src.models.routing_subproblem import DIR_OPP

    routing_free = routing_free_sink_commodities_from_generic_inputs(
        required_generic_inputs
    )
    contributions: dict[tuple[str, str, int], dict[str, Any]] = defaultdict(
        lambda: {
            "fixed": False,
            "literals": {},
            "front_cells": set(),
            "owners": set(),
        }
    )
    duplicate_rows: dict[
        tuple[int, int, str, str, str], dict[str, Any]
    ] = defaultdict(lambda: {"fixed_count": 0, "literals": {}})

    def record_port(
        *,
        port: Mapping[str, Any],
        side: str,
        literal: Any | None,
        owner: str,
    ) -> None:
        commodity = str(port["commodity"])
        if side == "out" and not is_routing_visible_output_commodity(
            commodity,
            routing_free,
        ):
            return
        cell = (int(port["x"]), int(port["y"]))
        component = routing_context.component_by_cell.get(cell)
        if component is None or cell in routing_context.occupied_cells:
            raise RuntimeError(f"front-filtered model retained unusable terminal: {cell}")
        e004.add_duplicate_contribution(
            duplicate_rows,
            key=(
                cell[0],
                cell[1],
                str(DIR_OPP[str(port["dir"])]),
                commodity,
                side,
            ),
            literal=literal,
        )
        row = contributions[(commodity, side, int(component))]
        row["front_cells"].add(cell)
        row["owners"].add(str(owner))
        if literal is None:
            row["fixed"] = True
        else:
            row["literals"][int(literal.Index())] = literal

    for instance_id, domain in sorted(binding_model.binding_domains.items()):
        variables = binding_model.binding_vars.get(instance_id)
        if variables is None:
            selected = int(binding_model.fixed_binding_choice[instance_id])
            option = domain[selected]
            for port in option.get("input_ports", []):
                record_port(port=port, side="in", literal=None, owner=instance_id)
            for port in option.get("output_ports", []):
                record_port(port=port, side="out", literal=None, owner=instance_id)
            continue
        for option_index, option in enumerate(domain):
            literal = variables[option_index]
            for port in option.get("input_ports", []):
                record_port(
                    port=port,
                    side="in",
                    literal=literal,
                    owner=instance_id,
                )
            for port in option.get("output_ports", []):
                record_port(
                    port=port,
                    side="out",
                    literal=literal,
                    owner=instance_id,
                )

    for slots, variables_by_slot, side in (
        (binding_model.generic_input_slots, binding_model.generic_input_vars, "in"),
        (binding_model.generic_output_slots, binding_model.generic_output_vars, "out"),
    ):
        for slot in slots:
            slot_id = str(slot["slot_id"])
            for commodity, literal in variables_by_slot[slot_id].items():
                if str(commodity) == "__unused__":
                    continue
                record_port(
                    port={
                        "x": int(slot["x"]),
                        "y": int(slot["y"]),
                        "dir": str(slot["dir"]),
                        "commodity": str(commodity),
                    },
                    side=side,
                    literal=literal,
                    owner=str(slot["instance_id"]),
                )

    model = binding_model.model
    duplicate_stats = add_duplicate_constraints(
        model=model,
        duplicate_rows=duplicate_rows,
    )
    commodities = sorted({commodity for commodity, _side, _component in contributions})
    mismatch_vars: dict[str, dict[int, Any]] = {}
    source_presence: dict[str, dict[int, Any]] = {}
    sink_presence: dict[str, dict[int, Any]] = {}
    source_global: dict[str, Any] = {}
    sink_global: dict[str, Any] = {}
    all_mismatch: list[Any] = []
    support_summary: dict[str, Any] = {}

    for commodity in commodities:
        components = sorted(
            {
                component
                for row_commodity, _side, component in contributions
                if row_commodity == commodity
            }
        )
        commodity_sources: dict[int, Any] = {}
        commodity_sinks: dict[int, Any] = {}
        commodity_mismatch: dict[int, Any] = {}
        commodity_support: dict[str, Any] = {"out": {}, "in": {}}
        for component in components:
            source_row = contributions[(commodity, "out", component)]
            sink_row = contributions[(commodity, "in", component)]
            source = e004.exact_or(
                model,
                name=f"e015_src_{commodity}_{component}",
                literals=list(source_row["literals"].values()),
                fixed=bool(source_row["fixed"]),
            )
            sink = e004.exact_or(
                model,
                name=f"e015_sink_{commodity}_{component}",
                literals=list(sink_row["literals"].values()),
                fixed=bool(sink_row["fixed"]),
            )
            mismatch = model.NewBoolVar(
                f"e015_mismatch_{commodity}_{component}"
            )
            model.Add(mismatch >= source - sink)
            model.Add(mismatch >= sink - source)
            model.Add(mismatch <= source + sink)
            model.Add(mismatch <= 2 - source - sink)
            commodity_sources[component] = source
            commodity_sinks[component] = sink
            commodity_mismatch[component] = mismatch
            all_mismatch.append(mismatch)
            for side, row in (("out", source_row), ("in", sink_row)):
                if row["fixed"] or row["literals"]:
                    commodity_support[side][str(component)] = {
                        "fixed": bool(row["fixed"]),
                        "literal_count": len(row["literals"]),
                        "front_cells": [
                            [x, y] for x, y in sorted(row["front_cells"])
                        ],
                        "owners": sorted(row["owners"]),
                    }
        global_source = e004.exact_or(
            model,
            name=f"e015_global_src_{commodity}",
            literals=list(commodity_sources.values()),
            fixed=False,
        )
        global_sink = e004.exact_or(
            model,
            name=f"e015_global_sink_{commodity}",
            literals=list(commodity_sinks.values()),
            fixed=False,
        )
        model.Add(global_source == 1)
        model.Add(global_sink == 1)
        source_presence[commodity] = commodity_sources
        sink_presence[commodity] = commodity_sinks
        mismatch_vars[commodity] = commodity_mismatch
        source_global[commodity] = global_source
        sink_global[commodity] = global_sink
        support_summary[commodity] = commodity_support

    model.Minimize(sum(all_mismatch))
    return {
        "commodities": commodities,
        "contribution_key_count": len(contributions),
        "duplicate_key_count": len(duplicate_rows),
        **duplicate_stats,
        "mismatch_variable_count": len(all_mismatch),
        "mismatch_vars": mismatch_vars,
        "source_presence": source_presence,
        "sink_presence": sink_presence,
        "source_global": source_global,
        "sink_global": sink_global,
        "support_summary": support_summary,
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
    }


def fixed_occupancy_summary(routing_context: Any) -> dict[str, Any]:
    free_cells = set(routing_context.component_by_cell)
    adjacency = 0
    for x, y in free_cells:
        adjacency += int((x + 1, y) in free_cells)
        adjacency += int((x, y + 1) in free_cells)
    sizes = sorted(
        (len(cells) for cells in routing_context.cells_by_component.values()),
        reverse=True,
    )
    return {
        "occupied_cell_count": len(routing_context.occupied_cells),
        "free_cell_count": len(free_cells),
        "free_adjacency_score": adjacency,
        "free_component_count": len(sizes),
        "largest_free_component": sizes[0] if sizes else 0,
        "component_sizes": sizes,
        "free_cell_set_digest": stable_digest(sorted(free_cells)),
    }


def solve_shared_mismatch(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e004: Any,
    random_seed: int,
    include_boundaries: bool,
) -> dict[str, Any]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import (
        RoutingPlacementCore,
        run_exact_routing_precheck,
    )

    routing_context = build_routing_binding_context(
        solution,
        inputs["pools"],
        GRID_W,
        GRID_H,
    )
    morphology = fixed_occupancy_summary(routing_context)
    build_started = time.monotonic()
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
        raise RuntimeError("E015 received a candidate with an empty binding domain")
    compiled = compile_shared_objective(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        e004=e004,
    )
    if compiled["duplicate_fixed_contradictions"]:
        raise RuntimeError("E015 candidate has a fixed terminal-key contradiction")
    build_seconds = time.monotonic() - build_started

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_CAP_SECONDS
    solver.parameters.num_search_workers = 8
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(random_seed)
    solve_started = time.monotonic()
    status = solver.Solve(binding_model.model)
    solve_seconds = time.monotonic() - solve_started
    status_name = solver.StatusName(status)
    record: dict[str, Any] = {
        "status": status_name,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "objective": (
            int(round(solver.ObjectiveValue()))
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None
        ),
        "best_bound": float(solver.BestObjectiveBound()),
        "morphology": morphology,
        "routing_aware_filter_stats": json_safe(
            binding_model.routing_aware_filter_stats
        ),
        "filtered_binding_option_count": sum(
            len(domain) for domain in binding_model.binding_domains.values()
        ),
        "generic_input_slot_count": len(binding_model.generic_input_slots),
        "generic_output_slot_count": len(binding_model.generic_output_slots),
        "compile": {
            key: value
            for key, value in compiled.items()
            if key
            not in {
                "mismatch_vars",
                "source_presence",
                "sink_presence",
                "source_global",
                "sink_global",
                "support_summary",
            }
        },
    }
    if status_name != "OPTIMAL":
        record["truth_boundary"] = "Shared mismatch optimum not established."
        return record

    binding_model._solver = solver
    binding_model._status = status
    per_commodity: dict[str, int] = {}
    global_presence: dict[str, dict[str, int]] = {}
    for commodity in compiled["commodities"]:
        mismatch_count = sum(
            int(solver.Value(variable))
            for variable in compiled["mismatch_vars"][commodity].values()
        )
        per_commodity[commodity] = mismatch_count
        global_presence[commodity] = {
            "source": int(solver.Value(compiled["source_global"][commodity])),
            "sink": int(solver.Value(compiled["sink_global"][commodity])),
        }
    objective = int(record["objective"])
    if objective != sum(per_commodity.values()):
        raise RuntimeError("shared objective/per-commodity sum mismatch")
    if any(value != {"source": 1, "sink": 1} for value in global_presence.values()):
        raise RuntimeError("shared optimum lacks a required source or sink")

    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    selected_components: dict[str, Any] = {}
    observed_per_commodity: dict[str, int] = {}
    for commodity in compiled["commodities"]:
        selected = e004.selected_component_sets(
            commodity=commodity,
            port_specs=port_specs,
            routing_context=routing_context,
        )
        observed = len(selected["mismatch_components"])
        if observed != per_commodity[commodity]:
            raise RuntimeError(
                f"shared objective/selected-port mismatch for {commodity}: "
                f"{per_commodity[commodity]} != {observed}"
            )
        observed_per_commodity[commodity] = observed
        selected_components[commodity] = selected

    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    disconnected = {
        str(row.get("commodity", ""))
        for row in precheck.get("disconnected_commodities", [])
    }
    positive = {
        commodity
        for commodity, value in per_commodity.items()
        if int(value) > 0
    }
    if disconnected != positive:
        raise RuntimeError(
            f"shared objective/production precheck mismatch: "
            f"positive={sorted(positive)} disconnected={sorted(disconnected)}"
        )
    precheck_public = {
        key: value for key, value in precheck.items() if key != "_analysis"
    }
    record.update(
        {
            "per_commodity": per_commodity,
            "positive_commodity_count": len(positive),
            "zero_mismatch_commodities": sorted(set(per_commodity) - positive),
            "global_presence": global_presence,
            "selection_digest": stable_digest(selection),
            "port_specs_digest": stable_digest(port_specs),
            "port_count": len(port_specs),
            "selected_components": selected_components,
            "ordinary_precheck": json_safe(precheck_public),
            "truth_boundary": (
                "Exact minimum all-commodity component mismatch under one shared "
                "binding selection for this fixed placement."
            ),
        }
    )
    if include_boundaries:
        record["mismatch_boundaries"] = {
            commodity: [
                e004.boundary_profile(
                    component=int(component),
                    routing_context=routing_context,
                    solution=solution,
                )
                for component in selected_components[commodity][
                    "mismatch_components"
                ]
            ]
            for commodity in compiled["commodities"]
        }
    return record


def candidate_solution(
    *,
    arm: Mapping[str, Any],
    candidate: Mapping[str, Any],
    base_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e014: Any,
) -> dict[str, dict[str, Any]]:
    target = arm["target"]
    source_ids = [str(value) for value in target["source_instance_ids"]]
    target_instance_id = source_ids[0]
    target_row = base_solution[target_instance_id]
    facility_type = str(target_row["facility_type"])
    pose_idx = int(candidate["pose_idx"])
    pose = inputs["pools"][facility_type][pose_idx]
    solution = e014.make_candidate_solution(
        base_solution=base_solution,
        target_instance_id=target_instance_id,
        target_row=target_row,
        facility_type=facility_type,
        pose_idx=pose_idx,
        pose=pose,
    )
    if stable_digest(solution) != str(candidate["candidate_solution_digest"]):
        raise RuntimeError(
            f"E014 candidate digest drift: arm={arm['arm_index']} pose={pose_idx}"
        )
    return solution


def arm_output_path(index: int) -> Path:
    return OUT / f"ARM_{index:02d}.json"


def evaluate_arm(
    *,
    arm: Mapping[str, Any],
    base_solution: Mapping[str, Mapping[str, Any]],
    inputs: Mapping[str, Any],
    e004: Any,
    e014: Any,
    runner_sha256: str,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    candidates = [
        candidate
        for candidate in arm["candidate_results"]
        if candidate["interface"]["status"] == "COMPONENT_INFEASIBLE"
    ]
    for index, candidate in enumerate(candidates, 1):
        solution = candidate_solution(
            arm=arm,
            candidate=candidate,
            base_solution=base_solution,
            inputs=inputs,
            e014=e014,
        )
        shared = solve_shared_mismatch(
            solution=solution,
            inputs=inputs,
            e004=e004,
            random_seed=261500 + 100 * int(arm["arm_index"]) + index,
            include_boundaries=False,
        )
        if shared["status"] == "OPTIMAL":
            if int(shared["filtered_binding_option_count"]) != int(
                candidate["interface"]["filtered_binding_option_count"]
            ):
                raise RuntimeError("E014/E015 filtered-domain count drift")
            if str(shared["morphology"]["free_cell_set_digest"]) != str(
                candidate["interface"]["morphology"]["free_cell_set_digest"]
            ):
                raise RuntimeError("E014/E015 morphology drift")
        records.append(
            {
                "pose_idx": int(candidate["pose_idx"]),
                "pose_id": str(candidate["pose_id"]),
                "anchor": json_safe(candidate["anchor"]),
                "same_footprint": bool(candidate["same_footprint"]),
                "candidate_solution_digest": str(
                    candidate["candidate_solution_digest"]
                ),
                "shared_binding": shared,
            }
        )
        if index % 20 == 0:
            print(
                json.dumps(
                    {
                        "event": "E015_ARM_PROGRESS",
                        "arm": int(arm["arm_index"]),
                        "candidate": index,
                        "candidate_total": len(candidates),
                        "objective": shared.get("objective"),
                        "status": shared["status"],
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            gc.collect()
    return {
        "schema": "zmd_zero_condition_e015_arm_v1",
        "created_at_utc": utc_now(),
        "runner_sha256": runner_sha256,
        "arm_index": int(arm["arm_index"]),
        "target": json_safe(arm["target"]),
        "candidate_count": len(records),
        "candidate_records": records,
        "status_counts": dict(
            sorted(Counter(row["shared_binding"]["status"] for row in records).items())
        ),
    }


def independent_minima() -> dict[str, int]:
    payload = load_json(E010_RESULT)
    minima = {
        str(commodity): int(row["e009"])
        for commodity, row in payload["per_commodity"].items()
    }
    if len(minima) != 19 or sum(minima.values()) != 196:
        raise RuntimeError(f"E010 independent minima drift: {minima}")
    return minima


def residual_partner_ranking(
    *,
    best_solution: Mapping[str, Mapping[str, Any]],
    best_record: Mapping[str, Any],
    moved_literal: str,
    inputs: Mapping[str, Any],
    e013: Any,
) -> dict[str, Any]:
    mandatory_instances = load_json(
        HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json"
    )
    group_by_instance = e013.group_mapping(mandatory_instances)
    e013_payload = load_json(E013_RESULT)
    portfolio = next(
        row
        for row in e013_payload["max_coverage_by_literal_budget"]
        if int(row["budget"]) == 16
    )["selected_literals"]
    eligible = set(str(value) for value in portfolio) - {str(moved_literal)}
    observation_ids_by_literal: dict[str, set[int]] = defaultdict(set)
    observations: list[dict[str, Any]] = []
    for commodity, boundaries in best_record["mismatch_boundaries"].items():
        selected = best_record["selected_components"][commodity]
        source_only = {int(value) for value in selected["source_only_components"]}
        sink_only = {int(value) for value in selected["sink_only_components"]}
        for boundary in boundaries:
            component_id = int(boundary["component_id"])
            role = (
                "source_only"
                if component_id in source_only
                else "sink_only"
                if component_id in sink_only
                else "INVALID"
            )
            if role == "INVALID":
                raise RuntimeError(
                    f"best-candidate residual boundary lacks role: "
                    f"{commodity}:{component_id}"
                )
            observation_id = len(observations)
            keys: set[str] = set()
            for owner in boundary["boundary_owners"]:
                key, _payload = e013.literal_identity(
                    owner=owner,
                    solution=best_solution,
                    group_by_instance=group_by_instance,
                    facility_pools=inputs["pools"],
                )
                if key in eligible:
                    keys.add(key)
            observations.append(
                {
                    "observation_id": observation_id,
                    "commodity": commodity,
                    "component_id": component_id,
                    "role": role,
                    "eligible_portfolio_literals": sorted(keys),
                }
            )
            for key in keys:
                observation_ids_by_literal[key].add(observation_id)
    ranked = sorted(
        (
            {
                "literal_key": key,
                "covered_residual_observation_count": len(
                    observation_ids_by_literal.get(key, set())
                ),
                "covered_residual_observation_fraction": len(
                    observation_ids_by_literal.get(key, set())
                )
                / len(observations),
            }
            for key in sorted(eligible)
        ),
        key=lambda row: (
            -int(row["covered_residual_observation_count"]),
            str(row["literal_key"]),
        ),
    )
    return {
        "residual_observation_count": len(observations),
        "eligible_portfolio_literal_count": len(eligible),
        "partner_ranking": ranked,
        "suggested_partner": ranked[0] if ranked else None,
        "observation_manifest_digest": stable_digest(observations),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    runner_sha256 = str(identity["runner_sha256"])
    e001 = import_module("zmd_e015_e001", E001_RUNNER)
    e004 = import_module("zmd_e015_e004", E004_RUNNER)
    e013 = import_module("zmd_e015_e013", E013_RUNNER)
    e014 = import_module("zmd_e015_e014", E014_RUNNER)
    stack = e001.import_stack()
    inputs = e001.load_model_inputs(stack)
    base_solution = reconstruct_base_solution()
    arms, arm_hashes = load_arm_surface(e014, inputs)
    minima = independent_minima()
    OUT.mkdir(parents=True, exist_ok=True)

    if BASELINE_PATH.exists():
        baseline = load_json(BASELINE_PATH)
        if str(baseline.get("runner_sha256")) != runner_sha256:
            raise RuntimeError("stale E015 baseline checkpoint")
    else:
        baseline_shared = solve_shared_mismatch(
            solution=base_solution,
            inputs=inputs,
            e004=e004,
            random_seed=261499,
            include_boundaries=True,
        )
        if baseline_shared["status"] != "OPTIMAL":
            raise RuntimeError(
                f"E009 shared baseline not OPTIMAL: {baseline_shared['status']}"
            )
        baseline = {
            "schema": "zmd_zero_condition_e015_baseline_v1",
            "created_at_utc": utc_now(),
            "runner_sha256": runner_sha256,
            "solution_digest": stable_digest(base_solution),
            "independent_minima": minima,
            "independent_minima_total": sum(minima.values()),
            "shared_binding": baseline_shared,
        }
        dump_exclusive(BASELINE_PATH, baseline)
    baseline_objective = int(baseline["shared_binding"]["objective"])
    if baseline_objective != 200:
        raise RuntimeError(f"E009 shared optimum drift: {baseline_objective} != 200")

    evaluated_arms: list[dict[str, Any]] = []
    for arm in arms:
        candidates = [
            candidate
            for candidate in arm["candidate_results"]
            if candidate["interface"]["status"] == "COMPONENT_INFEASIBLE"
        ]
        if not candidates:
            continue
        path = arm_output_path(int(arm["arm_index"]))
        if path.exists():
            evaluated = load_json(path)
            if str(evaluated.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E015 arm checkpoint: {path}")
        else:
            print(
                json.dumps(
                    {
                        "event": "E015_ARM_START",
                        "arm": int(arm["arm_index"]),
                        "candidate_count": len(candidates),
                        "literal": arm["target"]["literal_key"],
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            evaluated = evaluate_arm(
                arm=arm,
                base_solution=base_solution,
                inputs=inputs,
                e004=e004,
                e014=e014,
                runner_sha256=runner_sha256,
            )
            dump_exclusive(path, evaluated)
        evaluated_arms.append(evaluated)
        objectives = [
            int(row["shared_binding"]["objective"])
            for row in evaluated["candidate_records"]
            if row["shared_binding"]["status"] == "OPTIMAL"
        ]
        print(
            json.dumps(
                {
                    "event": "E015_ARM_DONE",
                    "arm": int(evaluated["arm_index"]),
                    "candidate_count": int(evaluated["candidate_count"]),
                    "best_objective": min(objectives) if objectives else None,
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    all_records = [
        {
            "arm_index": int(arm["arm_index"]),
            "target": arm["target"],
            **record,
        }
        for arm in evaluated_arms
        for record in arm["candidate_records"]
    ]
    if len(all_records) != 138:
        raise RuntimeError(f"E015 candidate count drift: {len(all_records)}")
    nonoptimal = [
        record for record in all_records if record["shared_binding"]["status"] != "OPTIMAL"
    ]
    optimal = [
        record for record in all_records if record["shared_binding"]["status"] == "OPTIMAL"
    ]
    ranked = sorted(
        optimal,
        key=lambda record: (
            int(record["shared_binding"]["objective"]),
            -len(record["shared_binding"]["zero_mismatch_commodities"]),
            -int(record["shared_binding"]["filtered_binding_option_count"]),
            int(record["shared_binding"]["morphology"]["free_component_count"]),
            int(record["arm_index"]),
            int(record["pose_idx"]),
        ),
    )
    if not ranked:
        raise RuntimeError("E015 established no exact candidate gradient")
    best_objective = int(ranked[0]["shared_binding"]["objective"])
    best_records = [
        record
        for record in ranked
        if int(record["shared_binding"]["objective"]) == best_objective
    ]

    best = best_records[0]
    source_ids = [str(value) for value in best["target"]["source_instance_ids"]]
    best_arm = next(
        arm for arm in arms if int(arm["arm_index"]) == int(best["arm_index"])
    )
    best_candidate_source = next(
        candidate
        for candidate in best_arm["candidate_results"]
        if int(candidate["pose_idx"]) == int(best["pose_idx"])
        and str(candidate["candidate_solution_digest"])
        == str(best["candidate_solution_digest"])
    )
    best_solution = candidate_solution(
        arm=best_arm,
        candidate=best_candidate_source,
        base_solution=base_solution,
        inputs=inputs,
        e014=e014,
    )
    best_detailed = solve_shared_mismatch(
        solution=best_solution,
        inputs=inputs,
        e004=e004,
        random_seed=262999,
        include_boundaries=True,
    )
    if (
        best_detailed["status"] != "OPTIMAL"
        or int(best_detailed["objective"]) != best_objective
    ):
        raise RuntimeError("E015 best-candidate detailed replay drift")
    partner = residual_partner_ranking(
        best_solution=best_solution,
        best_record=best_detailed,
        moved_literal=str(best["target"]["literal_key"]),
        inputs=inputs,
        e013=e013,
    )

    best_assignment_path = OUT / "BEST_ASSIGNMENT.json"
    best_layout_path = OUT / "BEST_LAYOUT.json"
    if not best_assignment_path.exists():
        dump_exclusive(
            best_assignment_path,
            {
                "schema": "zmd_zero_condition_e015_best_assignment_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "status": "FIXED_LAYOUT_SHARED_BINDING_OPTIMAL",
                "shared_mismatch_objective": best_objective,
                "solution": best_solution,
            },
        )
    if not best_layout_path.exists():
        dump_exclusive(best_layout_path, e001.solution_layout(best_solution))

    if best_objective == 0:
        routing = e014.screen_component_interface(
            solution=best_solution,
            inputs=inputs,
            e001=e001,
            e002=import_module(
                "zmd_e015_e002",
                ROOT
                / "research_lab/campaigns/zero_condition/experiments/E002_component_commodity_core/run_component_core.py",
            ),
        )
    else:
        routing = {"status": "NOT_REACHED_POSITIVE_SHARED_MISMATCH"}

    baseline_per = baseline["shared_binding"]["per_commodity"]
    best_per = best_detailed["per_commodity"]
    gradient = {
        commodity: int(best_per[commodity]) - int(baseline_per[commodity])
        for commodity in sorted(baseline_per)
    }
    if best_objective == 0:
        verdict = "SHARED_COMPONENT_FEASIBLE_CANDIDATE"
    elif best_objective < baseline_objective:
        verdict = "UNARY_SHARED_MISMATCH_IMPROVEMENT"
    else:
        verdict = "UNARY_SHARED_MISMATCH_FLOOR_UNCHANGED"

    objective_distribution = Counter(
        int(record["shared_binding"]["objective"]) for record in optimal
    )
    return {
        "schema": "zmd_zero_condition_e015_shared_binding_gradient_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "arm_checkpoint_hashes": arm_hashes,
        "baseline": baseline,
        "candidate_count": len(all_records),
        "optimal_candidate_count": len(optimal),
        "nonoptimal_candidate_count": len(nonoptimal),
        "nonoptimal_candidates": nonoptimal,
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "best_objective": best_objective,
        "baseline_objective": baseline_objective,
        "best_delta": best_objective - baseline_objective,
        "best_tie_count": len(best_records),
        "best_candidate": {
            key: value
            for key, value in best.items()
            if key != "shared_binding"
        },
        "best_shared_binding": best_detailed,
        "best_per_commodity_gradient": gradient,
        "best_assignment_path": str(best_assignment_path.relative_to(ROOT)),
        "best_assignment_sha256": sha256_file(best_assignment_path),
        "best_layout_path": str(best_layout_path.relative_to(ROOT)),
        "best_layout_sha256": sha256_file(best_layout_path),
        "residual_partner_analysis": partner,
        "suggested_pair": {
            "first_literal": str(best["target"]["literal_key"]),
            "first_source_instance_id": source_ids[0],
            "first_replacement_pose_idx": int(best["pose_idx"]),
            "first_replacement_pose_id": str(best["pose_id"]),
            "second_literal": (
                None
                if partner["suggested_partner"] is None
                else partner["suggested_partner"]["literal_key"]
            ),
            "second_literal_residual_coverage": partner["suggested_partner"],
        },
        "routing": routing,
        "top_candidates": ranked[:25],
        "truth_boundary": (
            "Exact all-commodity component mismatch under one shared binding for "
            "E009 and E014 fixed-layout candidates. Pair sufficiency and exact "
            "routing remain unproved unless explicitly reached."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E015 outputs under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "baseline_objective": result["baseline_objective"],
                    "best_objective": result["best_objective"],
                    "best_delta": result["best_delta"],
                    "best_tie_count": result["best_tie_count"],
                    "suggested_pair": result["suggested_pair"],
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
            "schema": "zmd_zero_condition_e015_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        OUT.mkdir(parents=True, exist_ok=True)
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
