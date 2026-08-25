#!/usr/bin/env python3
"""E002: isolate the commodity core of the E001 component failure.

Research-only.  Static front-domain filtering and duplicate terminal-key
constraints remain always on.  Every commodity component-support rule is guarded
by one assumption literal so the fixed-layout semantic core can be measured
without changing placement.
"""

from __future__ import annotations

from collections import defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
HISTORY_ROOT = Path("/home/zhuran24/zmd-pj")
E001_DIR = HERE.parent / "E001_pocket_cut_replay"
LOCAL_ROOT = ROOT / "research_lab/local/zero_condition/E002_component_commodity_core"
LAYOUT_PATH = (
    ROOT
    / "research_lab/local/zero_condition/E001_pocket_cut_replay/run-002/REPLACEMENT_LAYOUT.json"
)
ASSIGNMENT_PATH = (
    ROOT
    / "research_lab/local/zero_condition/E001_pocket_cut_replay/run-002/REPLACEMENT_ASSIGNMENT.json"
)
E001_RESULT_PATH = (
    ROOT
    / "research_lab/local/zero_condition/E001_pocket_cut_replay/run-002/RESULT.json"
)

EXPECTED_BRANCH = "research/main"
EXPECTED_LAYOUT_SHA256 = "752fb1706dba76ded658775750eaa6ac9f6816500e678a07ad18c3fce7d69f97"
EXPECTED_ASSIGNMENT_SHA256 = "ac80efdf293b12d852b62355815eaaeec7df5ae53b5078a4db9af24a41b55e91"
EXPECTED_E001_RESULT_SHA256 = "aaf85e0b214c9253ee76240b57afcd7762a30fb368debaa1c88da483f9e3cf67"
EXPECTED_MANDATORY_COUNT = 266
SOLVE_CAP_SECONDS = 30.0

EXPECTED_INPUT_HASHES: dict[str, str] = {
    "data/preprocessed/mandatory_exact_instances.json": (
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
    ),
    "data/preprocessed/candidate_placements.json": (
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
    ),
    "data/preprocessed/generic_io_requirements.json": (
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e"
    ),
    "rules/canonical_rules.json": (
        "c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0"
    ),
    "rules/preprocess_plan.json": (
        "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee"
    ),
}
EXPECTED_SOURCE_HASHES: dict[str, str] = {
    "research_lab/campaigns/zero_condition/experiments/E001_pocket_cut_replay/interface_compiler.py": (
        "a85ea192283c9501dfcc4a45baae6e750361c02f43ab872436c80858fe33900c"
    ),
    "src/models/binding_subproblem.py": (
        "b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba"
    ),
    "src/models/routing_binding_context.py": (
        "9f9e4d058a561ca570f3c4fd7f5d5095a1bcff558e0608408b0760fc7609f7c2"
    ),
    "src/models/routing_subproblem.py": (
        "7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718"
    ),
    "src/models/port_binding.py": (
        "9ed6c34873c5d8e3f7640a8507021e48ca2d850de2edc429482f3699700adc53"
    ),
    "src/search/pr2_l0_fixed_witness_core.py": (
        "eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1"
    ),
}
EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


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


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def dump_json_exclusive(path: Path, payload: Any) -> None:
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


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError("E002 must run on research/main")
    tracked_status = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked_status:
        raise RuntimeError(f"research worktree is not clean: {tracked_status}")

    environment_mismatches = {
        key: {"expected": expected, "actual": os.environ.get(key)}
        for key, expected in EXPECTED_ENV.items()
        if os.environ.get(key) != expected
    }
    unexpected_exact = sorted(
        key
        for key in os.environ
        if key.startswith("EXACT_") and key not in EXPECTED_ENV
    )
    if environment_mismatches or unexpected_exact:
        raise RuntimeError(
            f"environment mismatch: mismatches={environment_mismatches}, "
            f"unexpected_exact={unexpected_exact}"
        )

    checked: dict[str, str] = {}
    local_expected = {
        LAYOUT_PATH: EXPECTED_LAYOUT_SHA256,
        ASSIGNMENT_PATH: EXPECTED_ASSIGNMENT_SHA256,
        E001_RESULT_PATH: EXPECTED_E001_RESULT_SHA256,
    }
    for path, expected in local_expected.items():
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"E001 local input drift for {path}: {actual}")
    for relative, expected in sorted(EXPECTED_INPUT_HASHES.items()):
        path = HISTORY_ROOT / relative
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen project input drift for {relative}: {actual}")
    for relative, expected in sorted(EXPECTED_SOURCE_HASHES.items()):
        path = ROOT / relative
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"research source drift for {relative}: {actual}")

    e001 = load_json(E001_RESULT_PATH)
    if e001.get("verdict") != "COMPONENT_SUPPORT_INFEASIBLE":
        raise RuntimeError("E001 result is not the expected component-support failure")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": EXPECTED_BRANCH,
        "tracked_status": tracked_status,
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
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
        str(row["instance_id"]): dict(row)
        for row in placements
        if isinstance(row, Mapping)
    }
    if len(solution) != len(placements) or "ghost_pick" in solution:
        raise RuntimeError("replacement layout has invalid placement identities")
    if sum(bool(row.get("is_mandatory")) for row in solution.values()) != EXPECTED_MANDATORY_COUNT:
        raise RuntimeError("replacement mandatory count drift")
    assignment_solution = assignment.get("solution")
    if not isinstance(assignment_solution, Mapping):
        raise RuntimeError("replacement assignment lacks solution")
    if json_safe(assignment_solution) != json_safe(solution):
        raise RuntimeError("replacement layout and assignment disagree")
    if layout.get("ghost_rect") is not None:
        raise RuntimeError("E002 replacement unexpectedly has a ghost")
    return solution


def exact_or(model: Any, name: str, literals: Sequence[Any], *, fixed: bool) -> Any:
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


def compile_guarded_interface(
    *,
    binding_model: Any,
    routing_context: Any,
    required_generic_inputs: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from src.models.port_binding import (
        is_routing_visible_output_commodity,
        routing_free_sink_commodities_from_generic_inputs,
    )
    from src.models.routing_subproblem import DIR_OPP

    routing_free = routing_free_sink_commodities_from_generic_inputs(
        required_generic_inputs
    )
    contributions: dict[tuple[str, str, int], dict[str, Any]] = defaultdict(
        lambda: {"fixed": False, "literals": {}, "occurrences": 0}
    )
    support_rows: dict[tuple[str, str, int], dict[str, Any]] = defaultdict(
        lambda: {
            "fixed": False,
            "literal_indices": set(),
            "front_cells": set(),
            "owners": set(),
            "occurrences": 0,
        }
    )
    duplicate_rows: dict[tuple[int, int, str, str, str], dict[str, Any]] = defaultdict(
        lambda: {"fixed_count": 0, "literals": {}}
    )
    literal_details: dict[int, dict[str, Any]] = {}

    def record_port(
        *,
        port: Mapping[str, Any],
        side: str,
        literal: Any | None,
        owner: str,
        selector_kind: str,
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
            raise RuntimeError(f"front-filtered model retained unusable port {cell}")
        component = int(component)
        contribution = contributions[(commodity, side, component)]
        support = support_rows[(commodity, side, component)]
        contribution["occurrences"] += 1
        support["occurrences"] += 1
        support["front_cells"].add(cell)
        support["owners"].add(str(owner))
        if literal is None:
            contribution["fixed"] = True
            support["fixed"] = True
        else:
            index = int(literal.Index())
            contribution["literals"][index] = literal
            support["literal_indices"].add(index)
            detail = literal_details.setdefault(
                index,
                {
                    "literal_index": index,
                    "literal_name": str(literal.Name()),
                    "owner": str(owner),
                    "selector_kind": selector_kind,
                    "contributions": set(),
                },
            )
            detail["contributions"].add((commodity, side, component, cell))

        duplicate_key = (
            cell[0],
            cell[1],
            str(DIR_OPP[str(port["dir"])]),
            commodity,
            side,
        )
        duplicate = duplicate_rows[duplicate_key]
        if literal is None:
            duplicate["fixed_count"] += 1
        else:
            index = int(literal.Index())
            literal_row = duplicate["literals"].setdefault(
                index,
                {"literal": literal, "count": 0},
            )
            literal_row["count"] += 1

    for instance_id, domain in sorted(binding_model.binding_domains.items()):
        variables = binding_model.binding_vars.get(instance_id)
        if variables is None:
            option = domain[int(binding_model.fixed_binding_choice[instance_id])]
            for port in option.get("input_ports", []):
                record_port(
                    port=port,
                    side="in",
                    literal=None,
                    owner=instance_id,
                    selector_kind="fixed_binding_option",
                )
            for port in option.get("output_ports", []):
                record_port(
                    port=port,
                    side="out",
                    literal=None,
                    owner=instance_id,
                    selector_kind="fixed_binding_option",
                )
            continue
        for option_index, option in enumerate(domain):
            literal = variables[option_index]
            for port in option.get("input_ports", []):
                record_port(
                    port=port,
                    side="in",
                    literal=literal,
                    owner=instance_id,
                    selector_kind="binding_option",
                )
            for port in option.get("output_ports", []):
                record_port(
                    port=port,
                    side="out",
                    literal=literal,
                    owner=instance_id,
                    selector_kind="binding_option",
                )

    for slots, variables_by_slot, side, selector_kind in (
        (
            binding_model.generic_input_slots,
            binding_model.generic_input_vars,
            "in",
            "generic_input_slot",
        ),
        (
            binding_model.generic_output_slots,
            binding_model.generic_output_vars,
            "out",
            "generic_output_slot",
        ),
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
                    selector_kind=selector_kind,
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
            contradiction = model.NewBoolVar(f"dup_fixed_contradiction_{suffix}")
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

    components_by_commodity: dict[str, set[int]] = defaultdict(set)
    for commodity, _side, component in contributions:
        components_by_commodity[commodity].add(int(component))

    guards: dict[str, Any] = {}
    component_constraint_count = 0
    for commodity in sorted(components_by_commodity):
        guard = model.NewBoolVar(f"component_guard_{commodity}")
        guards[commodity] = guard
        source_presence: list[Any] = []
        sink_presence: list[Any] = []
        union_presence: list[Any] = []
        for component in sorted(components_by_commodity[commodity]):
            source_row = contributions[(commodity, "out", component)]
            sink_row = contributions[(commodity, "in", component)]
            source = exact_or(
                model,
                f"component_source_{commodity}_{component}",
                list(source_row["literals"].values()),
                fixed=bool(source_row["fixed"]),
            )
            sink = exact_or(
                model,
                f"component_sink_{commodity}_{component}",
                list(sink_row["literals"].values()),
                fixed=bool(sink_row["fixed"]),
            )
            union = exact_or(
                model,
                f"component_union_{commodity}_{component}",
                [source, sink],
                fixed=False,
            )
            source_presence.append(source)
            sink_presence.append(sink)
            union_presence.append(union)

        source_global = exact_or(
            model,
            f"global_source_{commodity}",
            source_presence,
            fixed=False,
        )
        sink_global = exact_or(
            model,
            f"global_sink_{commodity}",
            sink_presence,
            fixed=False,
        )
        both = model.NewBoolVar(f"global_both_{commodity}")
        model.Add(both <= source_global)
        model.Add(both <= sink_global)
        model.Add(both >= source_global + sink_global - 1)
        component_constraint_count += 3
        for source, sink in zip(source_presence, sink_presence, strict=True):
            model.Add(source == sink).OnlyEnforceIf([guard, both])
            component_constraint_count += 1
        model.Add(sum(union_presence) <= 1).OnlyEnforceIf([guard, both.Not()])
        component_constraint_count += 1

    support_summary: dict[str, Any] = {}
    for commodity in sorted(components_by_commodity):
        commodity_rows: dict[str, Any] = {"out": {}, "in": {}}
        for side in ("out", "in"):
            for component in sorted(components_by_commodity[commodity]):
                row = support_rows[(commodity, side, component)]
                if not row["fixed"] and not row["literal_indices"]:
                    continue
                commodity_rows[side][str(component)] = {
                    "fixed": bool(row["fixed"]),
                    "literal_count": len(row["literal_indices"]),
                    "occurrence_count": int(row["occurrences"]),
                    "front_cells": [
                        [int(x), int(y)] for x, y in sorted(row["front_cells"])
                    ],
                    "owners": sorted(row["owners"]),
                }
        support_summary[commodity] = commodity_rows

    literal_summary = {
        str(index): {
            **{key: value for key, value in detail.items() if key != "contributions"},
            "contributions": [
                {
                    "commodity": commodity,
                    "side": side,
                    "component": int(component),
                    "front_cell": [int(cell[0]), int(cell[1])],
                }
                for commodity, side, component, cell in sorted(
                    detail["contributions"],
                    key=lambda item: (item[0], item[1], item[2], item[3]),
                )
            ],
        }
        for index, detail in sorted(literal_details.items())
    }
    return (
        {
            "routing_aware_filter_stats": json_safe(
                binding_model.routing_aware_filter_stats
            ),
            "empty_filtered_domain_count": len(
                binding_model.empty_binding_domain_instances
            ),
            "filtered_binding_instance_count": len(binding_model.binding_domains),
            "filtered_binding_option_count": sum(
                len(domain) for domain in binding_model.binding_domains.values()
            ),
            "generic_input_slot_count": len(binding_model.generic_input_slots),
            "generic_output_slot_count": len(binding_model.generic_output_slots),
            "commodity_count": len(guards),
            "commodities": sorted(guards),
            "duplicate_key_count": len(duplicate_rows),
            "duplicate_constraint_count": duplicate_constraint_count,
            "duplicate_forbidden_literal_count": duplicate_forbidden_literal_count,
            "duplicate_fixed_contradictions": duplicate_fixed_contradictions,
            "component_constraint_count": component_constraint_count,
            "model_variable_count": len(model.Proto().variables),
            "model_constraint_count": len(model.Proto().constraints),
            "support_summary": support_summary,
            "literal_summary": literal_summary,
        },
        {"guards": guards},
    )


def solve_with_enabled(
    *,
    binding_model: Any,
    guards: Mapping[str, Any],
    enabled: set[str],
    label: str,
) -> dict[str, Any]:
    all_commodities = sorted(guards)
    unknown = sorted(enabled - set(all_commodities))
    if unknown:
        raise RuntimeError(f"unknown component guards: {unknown}")
    model = binding_model.model
    model.ClearAssumptions()
    assumptions = [
        guards[commodity]
        if commodity in enabled
        else guards[commodity].Not()
        for commodity in all_commodities
    ]
    expected_assumption_indices = [int(literal.Index()) for literal in assumptions]
    model.AddAssumptions(assumptions)
    actual_assumption_indices = [int(value) for value in model.Proto().assumptions]
    if actual_assumption_indices != expected_assumption_indices:
        raise RuntimeError(
            "CP-SAT assumption surface drift: "
            f"actual={actual_assumption_indices}, expected={expected_assumption_indices}"
        )
    assumption_records = [
        {
            "commodity": commodity,
            "enabled": commodity in enabled,
            "guard_index": int(guards[commodity].Index()),
            "assumption_literal_index": int(literal.Index()),
        }
        for commodity, literal in zip(all_commodities, assumptions, strict=True)
    ]
    started = time.monotonic()
    status = binding_model.solve(time_limit_seconds=SOLVE_CAP_SECONDS)
    elapsed = time.monotonic() - started
    solver = binding_model._solver
    result: dict[str, Any] = {
        "label": label,
        "enabled": sorted(enabled),
        "disabled": sorted(set(all_commodities) - enabled),
        "status": status,
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()) if solver is not None else 0.0,
        "branches": int(solver.NumBranches()) if solver is not None else None,
        "conflicts": int(solver.NumConflicts()) if solver is not None else None,
        "assumption_literals": assumption_records,
        "model_assumption_indices": actual_assumption_indices,
    }
    if status == "FEASIBLE":
        selection = binding_model.extract_selection()
        result["selection_digest"] = canonical_digest(selection)
    if status == "INFEASIBLE" and solver is not None:
        sufficient = [
            int(value) for value in solver.SufficientAssumptionsForInfeasibility()
        ]
        unknown_core_literals = sorted(set(sufficient) - set(actual_assumption_indices))
        if unknown_core_literals:
            raise RuntimeError(
                "solver returned sufficient literals outside the active assumptions: "
                f"{unknown_core_literals}"
            )
        result["sufficient_assumptions"] = sufficient
    return result


def summarize_precheck(precheck: Mapping[str, Any]) -> dict[str, Any]:
    blocked = list(precheck.get("blocked_ports", []))
    return {
        "status": str(precheck.get("status", "MISSING")),
        "blocked_port_count": len(blocked),
        "duplicate_terminal_key_count": sum(
            str(row.get("reason", "")) == "duplicate_terminal_front_key"
            for row in blocked
        ),
        "physical_blocked_port_count": sum(
            str(row.get("reason", "")) != "duplicate_terminal_front_key"
            for row in blocked
        ),
        "disconnected_commodities": json_safe(
            precheck.get("disconnected_commodities", [])
        ),
        "domain_stats": json_safe(precheck.get("domain_stats", {})),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if str(E001_DIR) not in sys.path:
        sys.path.insert(0, str(E001_DIR))

    from interface_compiler import build_routing_context
    from src.models.binding_subproblem import (
        PortBindingModel,
        load_binding_plan_semantics,
    )
    from src.models.master_model import (
        load_generic_io_requirements_artifact,
        load_project_data,
    )
    from src.models.routing_subproblem import run_exact_routing_precheck

    solution = reconstruct_solution()
    instances, pools, rules = load_project_data(
        HISTORY_ROOT,
        solve_mode="certified_exact",
    )
    generic = load_generic_io_requirements_artifact(HISTORY_ROOT)
    plan = load_binding_plan_semantics(project_root=HISTORY_ROOT)
    routing_bundle = build_routing_context(
        solution=solution,
        facility_pools=pools,
    )

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
        routing_context=routing_bundle["routing_context"],
    )
    binding_model.build()
    compiled, internals = compile_guarded_interface(
        binding_model=binding_model,
        routing_context=routing_bundle["routing_context"],
        required_generic_inputs=generic.get("required_generic_inputs", {}),
    )
    build_seconds = time.monotonic() - build_started
    guards = internals["guards"]
    if compiled["empty_filtered_domain_count"] != 0:
        raise RuntimeError("front-domain compilation produced an empty owner domain")
    if compiled["duplicate_fixed_contradictions"] != 0:
        raise RuntimeError("terminal uniqueness contains a fixed contradiction")

    base = solve_with_enabled(
        binding_model=binding_model,
        guards=guards,
        enabled=set(),
        label="BASE_ALL_COMPONENT_GUARDS_FALSE",
    )
    if base["status"] != "FEASIBLE":
        return {
            "verdict": "BASE_INVALID",
            "identity": identity,
            "fixed_occupancy": routing_bundle["summary"],
            "compiled": compiled,
            "base": base,
            "build_seconds": build_seconds,
        }
    base_ports = binding_model.extract_port_specs()
    base_precheck = run_exact_routing_precheck(
        placement_core=routing_bundle["placement_core"],
        port_specs=base_ports,
        occupied_owner_by_cell=routing_bundle["occupied_owner_by_cell"],
    )
    base_precheck_summary = summarize_precheck(base_precheck)
    if base_precheck_summary["physical_blocked_port_count"] != 0:
        raise RuntimeError("all-false base has a physical blocked front")
    if base_precheck_summary["duplicate_terminal_key_count"] != 0:
        raise RuntimeError("all-false base has a duplicate terminal key")

    all_commodities = set(guards)
    full = solve_with_enabled(
        binding_model=binding_model,
        guards=guards,
        enabled=all_commodities,
        label="FULL_ALL_COMPONENT_GUARDS_TRUE",
    )
    if full["status"] != "INFEASIBLE":
        return {
            "verdict": "FULL_NOT_REPRODUCED",
            "identity": identity,
            "fixed_occupancy": routing_bundle["summary"],
            "compiled": compiled,
            "base": base,
            "base_precheck": base_precheck_summary,
            "full": full,
            "build_seconds": build_seconds,
        }

    singleton_results: list[dict[str, Any]] = []
    singleton_cores: list[str] = []
    censored = False
    for commodity in sorted(all_commodities):
        result = solve_with_enabled(
            binding_model=binding_model,
            guards=guards,
            enabled={commodity},
            label=f"SINGLETON_{commodity}",
        )
        singleton_results.append(result)
        if result["status"] == "INFEASIBLE":
            singleton_cores.append(commodity)
        elif result["status"] == "TIMEOUT":
            censored = True
        elif result["status"] != "FEASIBLE":
            raise RuntimeError(
                f"unexpected singleton status for {commodity}: {result['status']}"
            )

    minimized_core: list[str] = []
    deletion_trace: list[dict[str, Any]] = []
    if not singleton_cores and not censored:
        positive_index_to_commodity = {
            int(guard.Index()): commodity for commodity, guard in guards.items()
        }
        raw_indices = list(full.get("sufficient_assumptions", []))
        raw_core: set[str] = set()
        for literal_index in raw_indices:
            commodity = positive_index_to_commodity.get(int(literal_index))
            if commodity is None:
                raise RuntimeError(
                    f"full assumption core contains unknown literal {literal_index}"
                )
            raw_core.add(commodity)
        if not raw_core:
            raw_core = set(all_commodities)
        current = set(raw_core)
        for commodity in sorted(list(current)):
            candidate = set(current)
            candidate.remove(commodity)
            result = solve_with_enabled(
                binding_model=binding_model,
                guards=guards,
                enabled=candidate,
                label=f"DELETE_{commodity}",
            )
            removed = result["status"] == "INFEASIBLE"
            if removed:
                current = candidate
            elif result["status"] == "TIMEOUT":
                censored = True
            elif result["status"] != "FEASIBLE":
                raise RuntimeError(
                    f"unexpected deletion status for {commodity}: {result['status']}"
                )
            deletion_trace.append(
                {
                    "commodity": commodity,
                    "removed": removed,
                    "core_after": sorted(current),
                    "solve": result,
                }
            )
        minimized_core = sorted(current)

    if censored:
        verdict = "CORE_UNKNOWN"
        core_commodities = sorted(set(singleton_cores) | set(minimized_core))
    elif singleton_cores:
        verdict = "SINGLETON_COMMODITY_CORE"
        core_commodities = sorted(singleton_cores)
    else:
        verdict = "MULTI_COMMODITY_CORE"
        core_commodities = minimized_core

    return {
        "schema": "zmd_zero_condition_e002_component_commodity_core_v1",
        "created_at_utc": now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "identity": identity,
        "fixed_occupancy": routing_bundle["summary"],
        "build_seconds": build_seconds,
        "compiled": compiled,
        "base_all_false": base,
        "base_ordinary_precheck": base_precheck_summary,
        "full_all_true": full,
        "singleton_results": singleton_results,
        "singleton_cores": sorted(singleton_cores),
        "minimized_multi_commodity_core": minimized_core,
        "deletion_trace": deletion_trace,
        "core_commodities": core_commodities,
        "core_support_summary": {
            commodity: compiled["support_summary"][commodity]
            for commodity in core_commodities
        },
        "truth_boundary": (
            "Inclusion-minimal commodity component-rule core inside the frozen "
            "E001 replacement binding model only; not a pose core, placement cut, "
            "routing proof, or certified result."
        ),
        "routing_solver_run": False,
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_component_core.py <output-name>")
    output_name = sys.argv[1]
    if not output_name or "/" in output_name or output_name in {".", ".."}:
        raise SystemExit("output-name must be one safe path component")
    output_dir = LOCAL_ROOT / output_name
    output_dir.mkdir(parents=True, exist_ok=False)
    result_path = output_dir / "RESULT.json"
    failure_path = output_dir / "FAILURE.json"
    try:
        started = time.monotonic()
        result = run()
        result["elapsed_seconds"] = time.monotonic() - started
        dump_json_exclusive(result_path, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "core_commodities": result.get("core_commodities", []),
                    "result_path": str(result_path.relative_to(ROOT)),
                    "result_sha256": sha256_file(result_path),
                    "elapsed_seconds": result["elapsed_seconds"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        failure = {
            "schema": "zmd_zero_condition_e002_failure_v1",
            "created_at_utc": now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        dump_json_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
