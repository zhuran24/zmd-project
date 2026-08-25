#!/usr/bin/env python3
"""Run E004: minimize per-commodity free-component mismatch on E001 replacement.

Research-only. This script does not attach a cut, run exact routing, update U/L,
or grant certification. It uses a differently shaped objective formulation and
then compares the optimum witness with the production routing precheck.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
E001_RUN = ROOT / "research_lab/local/zero_condition/E001_pocket_cut_replay/run-002"
E002_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/E002_component_commodity_core/run-004/RESULT.json"
)
OUT = ROOT / "research_lab/local/zero_condition/E004_component_mismatch_atlas/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"

LAYOUT_PATH = E001_RUN / "REPLACEMENT_LAYOUT.json"
ASSIGNMENT_PATH = E001_RUN / "REPLACEMENT_ASSIGNMENT.json"
E001_RESULT_PATH = E001_RUN / "RESULT.json"

EXPECTED_HASHES: dict[Path, str] = {
    LAYOUT_PATH: "752fb1706dba76ded658775750eaa6ac9f6816500e678a07ad18c3fce7d69f97",
    ASSIGNMENT_PATH: "ac80efdf293b12d852b62355815eaaeec7df5ae53b5078a4db9af24a41b55e91",
    E001_RESULT_PATH: "aaf85e0b214c9253ee76240b57afcd7762a30fb368debaa1c88da483f9e3cf67",
    E002_RESULT: "af7dbc207dec54d9e86f8e8ee37481cc2677bfc253967d87494870605f493154",
    HISTORY_ROOT / "data/preprocessed/candidate_placements.json": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    HISTORY_ROOT / "data/preprocessed/mandatory_exact_instances.json": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    HISTORY_ROOT / "data/preprocessed/generic_io_requirements.json": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    HISTORY_ROOT / "rules/canonical_rules.json": "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0",
    HISTORY_ROOT / "rules/preprocess_plan.json": "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
    ROOT / "src/models/binding_subproblem.py": "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba",
    ROOT / "src/models/port_binding.py": "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53",
    ROOT / "src/models/routing_binding_context.py": "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2",
    ROOT / "src/models/routing_subproblem.py": "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718",
    ROOT / "src/search/pr2_l0_fixed_witness_core.py": "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1",
}

EXPECTED_ENV: dict[str, str | None] = {
    "PYTHONHASHSEED": "0",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
SOLVE_CAP_SECONDS = 30.0
GRID_W = 70
GRID_H = 70


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


def verify_environment() -> dict[str, Any]:
    actual = {key: os.environ.get(key) for key in EXPECTED_ENV}
    mismatches = {
        key: {"expected": expected, "actual": actual[key]}
        for key, expected in EXPECTED_ENV.items()
        if actual[key] != expected
    }
    unexpected = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if mismatches or unexpected:
        raise RuntimeError(
            f"environment mismatch: mismatches={mismatches}, unexpected={unexpected}"
        )
    return {"actual": actual, "unexpected_exact_variables": unexpected}


def verify_identity() -> dict[str, Any]:
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift for {path}: {actual} != {expected}")

    consumed_tracked_paths = {
        str(path.relative_to(ROOT))
        for path in EXPECTED_HASHES
        if path.is_relative_to(ROOT)
    }
    dirty_lines = git_output("status", "--porcelain=v1", "--untracked-files=no").splitlines()
    dirty_consumed: list[str] = []
    for line in dirty_lines:
        relative = line[3:].strip()
        if " -> " in relative:
            relative = relative.split(" -> ", 1)[1]
        if relative in consumed_tracked_paths:
            dirty_consumed.append(relative)
    if dirty_consumed:
        raise RuntimeError(f"consumed tracked sources are dirty: {dirty_consumed}")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "tracked_dirty_nonconsumed": dirty_lines,
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def reconstruct_solution() -> dict[str, dict[str, Any]]:
    layout = load_json(LAYOUT_PATH)
    assignment = load_json(ASSIGNMENT_PATH)
    placements = layout.get("placements")
    if not isinstance(placements, list):
        raise RuntimeError("replacement layout lacks placements")
    solution = {
        str(record["instance_id"]): dict(record)
        for record in placements
        if isinstance(record, Mapping)
    }
    if len(solution) != len(placements):
        raise RuntimeError("replacement layout has invalid or duplicate instance ids")
    assignment_solution = assignment.get("solution")
    if not isinstance(assignment_solution, Mapping):
        raise RuntimeError("replacement assignment lacks solution")
    if json_safe(assignment_solution) != json_safe(solution):
        raise RuntimeError("replacement layout and assignment disagree")
    mandatory = sum(bool(record.get("is_mandatory")) for record in solution.values())
    if mandatory != 266:
        raise RuntimeError(f"mandatory count drift: {mandatory}")
    return solution


def exact_or(
    model: cp_model.CpModel,
    *,
    name: str,
    literals: Sequence[Any],
    fixed: bool,
) -> Any:
    variable = model.NewBoolVar(name)
    unique = {int(literal.Index()): literal for literal in literals}
    ordered = [unique[index] for index in sorted(unique)]
    if fixed:
        model.Add(variable == 1)
    elif not ordered:
        model.Add(variable == 0)
    else:
        for literal in ordered:
            model.AddImplication(literal, variable)
        model.AddBoolOr(ordered).OnlyEnforceIf(variable)
    return variable


def add_duplicate_contribution(
    table: dict[tuple[int, int, str, str, str], dict[str, Any]],
    *,
    key: tuple[int, int, str, str, str],
    literal: Any | None,
) -> None:
    row = table[key]
    if literal is None:
        row["fixed_count"] += 1
        return
    index = int(literal.Index())
    literal_row = row["literals"].setdefault(
        index,
        {"literal": literal, "count": 0},
    )
    literal_row["count"] += 1


def boundary_profile(
    *,
    component: int,
    routing_context: Any,
    solution: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    cells = set(routing_context.cells_by_component.get(int(component), set()))
    owner_edges: Counter[str] = Counter()
    grid_edges = 0
    for x, y in cells:
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
                grid_edges += 1
                continue
            owner = routing_context.occupied_owner_by_cell.get((nx, ny))
            if owner is not None:
                owner_edges[str(owner)] += 1

    owner_records: list[dict[str, Any]] = []
    for owner, edges in sorted(owner_edges.items(), key=lambda item: (-item[1], item[0])):
        record = dict(solution.get(owner, {}))
        owner_records.append(
            {
                "instance_id": owner,
                "boundary_edge_count": int(edges),
                "facility_type": str(record.get("facility_type", "")),
                "operation_type": str(record.get("operation_type", "")),
                "pose_idx": int(record.get("pose_idx", -1)),
                "pose_id": str(record.get("pose_id", "")),
                "anchor": json_safe(record.get("anchor", {})),
            }
        )
    return {
        "component_id": int(component),
        "component_size": len(cells),
        "occupied_boundary_edge_count": int(sum(owner_edges.values())),
        "grid_boundary_edge_count": int(grid_edges),
        "boundary_owner_count": len(owner_edges),
        "boundary_owners": owner_records,
    }


def selected_component_sets(
    *,
    commodity: str,
    port_specs: Sequence[Mapping[str, Any]],
    routing_context: Any,
) -> dict[str, Any]:
    source_fronts: dict[int, set[tuple[int, int]]] = defaultdict(set)
    sink_fronts: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for spec in port_specs:
        if str(spec.get("commodity", "")) != commodity:
            continue
        cell = (int(spec["x"]), int(spec["y"]))
        component = routing_context.component_by_cell.get(cell)
        if component is None:
            raise RuntimeError(f"selected {commodity} terminal lacks free component: {cell}")
        target = source_fronts if str(spec.get("type", "")) == "out" else sink_fronts
        target[int(component)].add(cell)

    source_components = set(source_fronts)
    sink_components = set(sink_fronts)
    mismatch = source_components ^ sink_components
    return {
        "source_components": sorted(source_components),
        "sink_components": sorted(sink_components),
        "mismatch_components": sorted(mismatch),
        "source_only_components": sorted(source_components - sink_components),
        "sink_only_components": sorted(sink_components - source_components),
        "source_fronts_by_component": {
            str(component): [[x, y] for x, y in sorted(cells)]
            for component, cells in sorted(source_fronts.items())
        },
        "sink_fronts_by_component": {
            str(component): [[x, y] for x, y in sorted(cells)]
            for component, cells in sorted(sink_fronts.items())
        },
    }


def add_duplicate_constraints_and_target_objective(
    *,
    binding_model: Any,
    routing_context: Any,
    required_generic_inputs: Mapping[str, Any],
    target_commodity: str,
) -> dict[str, Any]:
    from src.models.port_binding import (
        is_routing_visible_output_commodity,
        routing_free_sink_commodities_from_generic_inputs,
    )
    from src.models.routing_subproblem import DIR_OPP

    routing_free = routing_free_sink_commodities_from_generic_inputs(
        required_generic_inputs
    )
    contributions: dict[tuple[str, int], dict[str, Any]] = defaultdict(
        lambda: {"fixed": False, "literals": {}, "front_cells": set(), "owners": set()}
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
        duplicate_key = (
            cell[0],
            cell[1],
            str(DIR_OPP[str(port["dir"])]),
            commodity,
            side,
        )
        add_duplicate_contribution(
            duplicate_rows,
            key=duplicate_key,
            literal=literal,
        )
        if commodity != target_commodity:
            return
        row = contributions[(side, int(component))]
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
                record_port(port=port, side="in", literal=literal, owner=instance_id)
            for port in option.get("output_ports", []):
                record_port(port=port, side="out", literal=literal, owner=instance_id)

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
    duplicate_constraint_count = 0
    duplicate_forbidden_literal_count = 0
    duplicate_fixed_contradictions = 0
    for key, row in sorted(duplicate_rows.items()):
        fixed_count = int(row["fixed_count"])
        literal_rows = row["literals"]
        if fixed_count > 1:
            suffix = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]
            contradiction = model.NewBoolVar(f"e004_dup_fixed_contradiction_{suffix}")
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

    components = sorted({component for _side, component in contributions})
    if not components:
        raise RuntimeError(f"target commodity has no component contributions: {target_commodity}")

    source_presence: dict[int, Any] = {}
    sink_presence: dict[int, Any] = {}
    mismatch_vars: dict[int, Any] = {}
    support_summary: dict[str, dict[str, Any]] = {"out": {}, "in": {}}
    for component in components:
        source_row = contributions[("out", component)]
        sink_row = contributions[("in", component)]
        source = exact_or(
            model,
            name=f"e004_src_{target_commodity}_{component}",
            literals=list(source_row["literals"].values()),
            fixed=bool(source_row["fixed"]),
        )
        sink = exact_or(
            model,
            name=f"e004_sink_{target_commodity}_{component}",
            literals=list(sink_row["literals"].values()),
            fixed=bool(sink_row["fixed"]),
        )
        mismatch = model.NewBoolVar(f"e004_mismatch_{target_commodity}_{component}")
        model.Add(mismatch >= source - sink)
        model.Add(mismatch >= sink - source)
        model.Add(mismatch <= source + sink)
        model.Add(mismatch <= 2 - source - sink)
        source_presence[component] = source
        sink_presence[component] = sink
        mismatch_vars[component] = mismatch
        for side, row in (("out", source_row), ("in", sink_row)):
            if row["fixed"] or row["literals"]:
                support_summary[side][str(component)] = {
                    "fixed": bool(row["fixed"]),
                    "literal_count": len(row["literals"]),
                    "front_cells": [[x, y] for x, y in sorted(row["front_cells"])],
                    "owners": sorted(row["owners"]),
                }

    source_global = exact_or(
        model,
        name=f"e004_global_src_{target_commodity}",
        literals=list(source_presence.values()),
        fixed=False,
    )
    sink_global = exact_or(
        model,
        name=f"e004_global_sink_{target_commodity}",
        literals=list(sink_presence.values()),
        fixed=False,
    )
    model.Minimize(sum(mismatch_vars.values()))

    return {
        "duplicate_key_count": len(duplicate_rows),
        "duplicate_constraint_count": duplicate_constraint_count,
        "duplicate_forbidden_literal_count": duplicate_forbidden_literal_count,
        "duplicate_fixed_contradictions": duplicate_fixed_contradictions,
        "components": components,
        "source_presence": source_presence,
        "sink_presence": sink_presence,
        "source_global": source_global,
        "sink_global": sink_global,
        "mismatch_vars": mismatch_vars,
        "support_summary": support_summary,
    }


def solve_commodity(
    *,
    commodity: str,
    solution: Mapping[str, Mapping[str, Any]],
    instances: Sequence[Mapping[str, Any]],
    pools: Mapping[str, list[dict[str, Any]]],
    rules: Mapping[str, Any],
    generic: Mapping[str, Any],
    plan: Mapping[str, Any],
    routing_context: Any,
    placement_core: Any,
) -> dict[str, Any]:
    from src.models.binding_subproblem import PortBindingModel
    from src.models.routing_subproblem import run_exact_routing_precheck

    build_started = time.monotonic()
    binding_model = PortBindingModel(
        placement_solution=solution,
        facility_pools=pools,
        instances=instances,
        project_root=HISTORY_ROOT,
        required_generic_outputs=generic.get("required_generic_outputs", {}),
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        generic_input_slots_by_operation=plan["generic_input_slots_by_operation"],
        generic_output_slots_by_operation=plan["generic_output_slots_by_operation"],
        utility_operation_by_template=plan["utility_operation_by_template"],
        canonical_rules_payload=rules,
        routing_context=routing_context,
    )
    binding_model.build()
    if binding_model.empty_binding_domain_instances:
        raise RuntimeError(
            f"{commodity}: front-domain compiler produced empty owner domains"
        )
    compiled = add_duplicate_constraints_and_target_objective(
        binding_model=binding_model,
        routing_context=routing_context,
        required_generic_inputs=generic.get("required_generic_inputs", {}),
        target_commodity=commodity,
    )
    if compiled["duplicate_fixed_contradictions"]:
        raise RuntimeError(f"{commodity}: fixed duplicate terminal contradiction")
    build_seconds = time.monotonic() - build_started

    solve_started = time.monotonic()
    coarse_status = binding_model.solve(time_limit_seconds=SOLVE_CAP_SECONDS)
    solve_seconds = time.monotonic() - solve_started
    solver = binding_model._solver
    status_code = binding_model._status
    status_name = solver.StatusName(status_code) if solver is not None else coarse_status
    record: dict[str, Any] = {
        "commodity": commodity,
        "status": status_name,
        "coarse_status": coarse_status,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "wall_time": float(solver.WallTime()) if solver is not None else 0.0,
        "branches": int(solver.NumBranches()) if solver is not None else None,
        "conflicts": int(solver.NumConflicts()) if solver is not None else None,
        "duplicate_key_count": compiled["duplicate_key_count"],
        "duplicate_constraint_count": compiled["duplicate_constraint_count"],
        "component_candidate_count": len(compiled["components"]),
        "support_summary": compiled["support_summary"],
    }
    if status_name != "OPTIMAL" or solver is None:
        record["truth_boundary"] = "Minimum mismatch not established."
        return record

    objective = int(round(float(solver.ObjectiveValue())))
    source_global_value = int(solver.Value(compiled["source_global"]))
    sink_global_value = int(solver.Value(compiled["sink_global"]))
    if source_global_value != 1 or sink_global_value != 1:
        raise RuntimeError(
            f"{commodity}: optimum lacks source or sink: "
            f"source={source_global_value} sink={sink_global_value}"
        )

    selection = binding_model.extract_selection()
    port_specs = binding_model.extract_port_specs()
    selected = selected_component_sets(
        commodity=commodity,
        port_specs=port_specs,
        routing_context=routing_context,
    )
    observed_mismatch = len(selected["mismatch_components"])
    if objective != observed_mismatch:
        raise RuntimeError(
            f"{commodity}: objective/precheck-set mismatch: {objective} != {observed_mismatch}"
        )

    precheck = run_exact_routing_precheck(
        placement_core=placement_core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    if str(precheck.get("status")) == "front_blocked":
        raise RuntimeError(f"{commodity}: optimum witness failed earlier front/duplicate stage")
    disconnected_names = {
        str(row.get("commodity", ""))
        for row in precheck.get("disconnected_commodities", [])
    }
    production_reports_target = commodity in disconnected_names
    if (objective > 0) != production_reports_target:
        raise RuntimeError(
            f"{commodity}: objective/precheck disagreement: objective={objective}, "
            f"production_reports_target={production_reports_target}"
        )

    boundaries = [
        boundary_profile(
            component=component,
            routing_context=routing_context,
            solution=solution,
        )
        for component in selected["mismatch_components"]
    ]
    record.update(
        {
            "minimum_mismatch_count": objective,
            "source_global": source_global_value,
            "sink_global": sink_global_value,
            "selection_digest": hashlib.sha256(
                json.dumps(
                    json_safe(selection),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "port_count": len(port_specs),
            "selected_components": selected,
            "mismatch_boundaries": boundaries,
            "production_precheck_status": str(precheck.get("status", "MISSING")),
            "production_precheck_reports_target": production_reports_target,
            "production_disconnected_commodity_count": len(disconnected_names),
            "truth_boundary": (
                "Exact minimum mismatch for this commodity inside the fixed E001 "
                "replacement binding model; boundary profile is for one optimum witness."
            ),
        }
    )
    return record


def run() -> dict[str, Any]:
    identity = verify_identity()
    environment = verify_environment()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from src.models.binding_subproblem import load_binding_plan_semantics
    from src.models.master_model import (
        load_generic_io_requirements_artifact,
        load_project_data,
    )
    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import RoutingPlacementCore

    solution = reconstruct_solution()
    instances, pools, rules = load_project_data(
        HISTORY_ROOT,
        solve_mode="certified_exact",
    )
    generic = load_generic_io_requirements_artifact(HISTORY_ROOT)
    plan = load_binding_plan_semantics(project_root=HISTORY_ROOT)
    routing_context = build_routing_binding_context(
        solution,
        pools,
        GRID_W,
        GRID_H,
    )
    placement_core = RoutingPlacementCore.from_occupied_cells(
        set(routing_context.occupied_cells),
        occupied_owner_by_cell=dict(routing_context.occupied_owner_by_cell),
    )
    component_sizes = sorted(
        (len(cells) for cells in routing_context.cells_by_component.values()),
        reverse=True,
    )

    e002 = load_json(E002_RESULT)
    commodities = [str(value) for value in e002.get("singleton_cores", [])]
    if len(commodities) != 19 or len(set(commodities)) != 19:
        raise RuntimeError(f"E002 singleton set drift: {commodities}")

    started = time.monotonic()
    commodity_results: list[dict[str, Any]] = []
    for index, commodity in enumerate(sorted(commodities), 1):
        print(
            json.dumps(
                {
                    "event": "E004_COMMODITY_START",
                    "index": index,
                    "total": len(commodities),
                    "commodity": commodity,
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        result = solve_commodity(
            commodity=commodity,
            solution=solution,
            instances=instances,
            pools=pools,
            rules=rules,
            generic=generic,
            plan=plan,
            routing_context=routing_context,
            placement_core=placement_core,
        )
        commodity_results.append(result)
        print(
            json.dumps(
                {
                    "event": "E004_COMMODITY_DONE",
                    "commodity": commodity,
                    "status": result["status"],
                    "minimum_mismatch_count": result.get("minimum_mismatch_count"),
                    "seconds": result["solve_seconds"],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    optimal = [row for row in commodity_results if row["status"] == "OPTIMAL"]
    zero = [
        row["commodity"]
        for row in optimal
        if int(row.get("minimum_mismatch_count", -1)) == 0
    ]
    positive = [
        row["commodity"]
        for row in optimal
        if int(row.get("minimum_mismatch_count", -1)) > 0
    ]
    unknown = [row["commodity"] for row in commodity_results if row["status"] != "OPTIMAL"]

    owner_frequency: Counter[str] = Counter()
    boundary_owner_counts: list[int] = []
    component_sizes_at_mismatch: list[int] = []
    mismatch_count_distribution: Counter[int] = Counter()
    for row in optimal:
        minimum = int(row["minimum_mismatch_count"])
        mismatch_count_distribution[minimum] += 1
        for boundary in row.get("mismatch_boundaries", []):
            boundary_owner_counts.append(int(boundary["boundary_owner_count"]))
            component_sizes_at_mismatch.append(int(boundary["component_size"]))
            for owner in boundary["boundary_owners"]:
                owner_frequency[str(owner["instance_id"])] += 1

    if zero:
        verdict = "COMPONENT_COMPILER_COUNTEREXAMPLE"
    elif unknown:
        verdict = "PARTIAL_FRAGMENTATION_UNKNOWN"
    else:
        verdict = "GLOBAL_FRAGMENTATION_REPRODUCED"

    return {
        "schema": "zmd_zero_condition_e004_component_mismatch_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "environment": environment,
        "fixed_occupancy": {
            "occupied_cell_count": len(routing_context.occupied_cells),
            "free_cell_count": GRID_W * GRID_H - len(routing_context.occupied_cells),
            "free_component_count": len(routing_context.cells_by_component),
            "largest_free_component": component_sizes[0] if component_sizes else 0,
            "component_sizes": component_sizes,
        },
        "commodity_count": len(commodities),
        "optimal_count": len(optimal),
        "positive_minimum_count": len(positive),
        "zero_minimum_commodities": zero,
        "unknown_commodities": unknown,
        "minimum_mismatch_distribution": {
            str(key): value for key, value in sorted(mismatch_count_distribution.items())
        },
        "boundary_summary": {
            "mismatch_component_observation_count": len(boundary_owner_counts),
            "boundary_owner_count_min": min(boundary_owner_counts) if boundary_owner_counts else None,
            "boundary_owner_count_max": max(boundary_owner_counts) if boundary_owner_counts else None,
            "boundary_owner_count_median": (
                sorted(boundary_owner_counts)[len(boundary_owner_counts) // 2]
                if boundary_owner_counts
                else None
            ),
            "mismatch_component_size_min": min(component_sizes_at_mismatch)
            if component_sizes_at_mismatch
            else None,
            "mismatch_component_size_max": max(component_sizes_at_mismatch)
            if component_sizes_at_mismatch
            else None,
            "shared_boundary_owners": [
                {"instance_id": owner, "mismatch_boundary_occurrences": count}
                for owner, count in owner_frequency.most_common()
                if count >= 2
            ],
        },
        "commodity_results": commodity_results,
        "production_comparison": (
            "For every OPTIMAL row, the extracted selection was evaluated by "
            "run_exact_routing_precheck and target disconnection agreed with whether "
            "the minimum mismatch objective was positive."
        ),
        "truth_boundary": (
            "Exact per-commodity minimum mismatch only for the fixed E001 replacement "
            "binding model when status is OPTIMAL. Boundary profiles describe selected "
            "optimum witnesses, not unavoidable named obstacle cores."
        ),
        "routing_solver_run": False,
        "ledger_effect": "none",
        "elapsed_seconds": time.monotonic() - started,
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite E004 output under {OUT}")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "optimal_count": result["optimal_count"],
                    "positive_minimum_count": result["positive_minimum_count"],
                    "zero_minimum_commodities": result["zero_minimum_commodities"],
                    "unknown_commodities": result["unknown_commodities"],
                    "result_path": str(RESULT_PATH),
                    "result_sha256": sha256_file(RESULT_PATH),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0 if result["verdict"] != "COMPONENT_COMPILER_COUNTEREXAMPLE" else 31
    except Exception as exc:
        import traceback

        failure = {
            "schema": "zmd_zero_condition_e004_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
