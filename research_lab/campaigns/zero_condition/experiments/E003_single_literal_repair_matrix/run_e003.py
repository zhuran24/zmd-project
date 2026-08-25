#!/usr/bin/env python3
"""Run E003 single-literal repair arms after an E002 bounded UNKNOWN."""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

EXPERIMENT_DIR = Path(__file__).resolve().parent
RESEARCH_ROOT = Path(__file__).resolve().parents[5]
E001_DIR = EXPERIMENT_DIR.parent / "E001_pocket_cut_replay"
E002_DIR = EXPERIMENT_DIR.parent / "E002_minimal_pocket_repair"
for path in (RESEARCH_ROOT, E001_DIR, E002_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from interface_compiler import build_routing_context, component_profile  # noqa: E402
from pocket_diagnostics import diagnose_forced_source_pockets  # noqa: E402
from run_e001 import (  # noqa: E402
    EXPECTED_INPUTS,
    atomic_write_json,
    atomic_write_text,
    build_binding_model,
    build_master,
    compare_solutions,
    load_json,
    load_project_inputs,
    materialize_layout,
    minimize_commodity_core,
    parse_solution_payload,
    pocket_cut_survives,
    run_exact_routing,
    solve_binding_variant,
    solver_stats,
    status_name,
    utc_now,
    verify_input,
)
from run_e002 import add_minimal_repair_fixes, delegate  # noqa: E402
from transport_checker import (  # noqa: E402
    POCKET_CONFLICT_SET,
    check_named_to_group_transport,
)


class MatrixError(RuntimeError):
    pass


def cut_variables(master: Any, transport: Mapping[str, Any]) -> dict[str, Any]:
    target = delegate(master)
    variables: dict[str, Any] = {}
    for row in transport.get("lowered_literals", []):
        owner = str(row["canonical_owner"])
        pose_idx = int(row["pose_idx"])
        source_id = str(row["source_id"])
        if owner.startswith("pose_optional::"):
            variable = target.pole_vars.get(pose_idx)
        else:
            variable = target.x_vars.get((owner, pose_idx))
        if variable is None:
            raise MatrixError(f"missing lowered cut variable {owner}@{pose_idx}")
        variables[source_id] = variable
    if set(variables) != set(POCKET_CONFLICT_SET):
        raise MatrixError("cut variable lookup does not match source conflict set")
    return variables


def solve_arm(
    *,
    moved_source_id: str,
    a1_solution: Mapping[str, int],
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    plan: Mapping[str, Any],
    seconds: float,
    random_seed: int,
) -> tuple[dict[str, Any], Mapping[str, int] | None]:
    started = time.perf_counter()
    master, build_stats = build_master(
        instances=instances,
        facility_pools=facility_pools,
        rules=rules,
        plan=plan,
    )
    transport = check_named_to_group_transport(
        master=master,
        instances=instances,
        facility_pools=facility_pools,
        conflict_set=POCKET_CONFLICT_SET,
    )
    if transport["verdict"] != "PASS":
        raise MatrixError(f"transport failed in arm {moved_source_id}")
    before = len(master.model.Proto().constraints)
    if not master.add_benders_cut(dict(POCKET_CONFLICT_SET)):
        raise MatrixError("four-pose cut did not attach")
    neighborhood = add_minimal_repair_fixes(
        master=master,
        a1_solution=a1_solution,
        transport=transport,
    )
    variables = cut_variables(master, transport)
    for source_id, variable in variables.items():
        master.model.Add(variable == (0 if source_id == moved_source_id else 1))
    after = len(master.model.Proto().constraints)
    solve_started = time.perf_counter()
    status, solver = master.solve(
        time_limit=float(seconds),
        num_workers=8,
        random_seed=int(random_seed),
        search_branching="FIXED_SEARCH",
        solution_hint=a1_solution,
        known_feasible_hint=False,
        hint_inactive_residual_optionals=False,
        log_search_progress=False,
    )
    solve_elapsed = time.perf_counter() - solve_started
    arm: dict[str, Any] = {
        "moved_source_id": moved_source_id,
        "forced_pose_idx": int(POCKET_CONFLICT_SET[moved_source_id]),
        "status": status_name(status),
        "build_and_setup_elapsed_seconds": solve_started - started,
        "solve_elapsed_seconds": solve_elapsed,
        "constraint_count_before_cut": before,
        "constraint_count_after_arm": after,
        "build_stats": build_stats,
        "neighborhood": neighborhood,
        "solver_stats": solver_stats(solver, solve_elapsed),
    }
    if arm["status"] not in {"FEASIBLE", "OPTIMAL"}:
        return arm, None
    solution = master.extract_solution(solver)
    arm["cut_literal_evaluation"] = pocket_cut_survives(solution, instances)
    arm["comparison_to_a1"] = compare_solutions(a1_solution, solution, instances)
    return arm, solution


def downstream(
    *,
    solution: Mapping[str, int],
    instances: Sequence[Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    rules: Mapping[str, Any],
    binding_seconds: float,
    core_seconds: float,
    routing_seconds: float,
    random_seed: int,
    pocket_max_component_size: int,
    output_dir: Path,
) -> dict[str, Any]:
    occupied, owner_by_cell, routing_core, routing_context = build_routing_context(
        solution,
        facility_pools,
    )
    profile = component_profile(routing_context)
    profile["occupied_cell_count"] = len(occupied)
    base_result, _, _ = solve_binding_variant(
        solution=solution,
        facility_pools=facility_pools,
        rules=rules,
        routing_context=routing_context,
        time_limit=binding_seconds,
        random_seed=random_seed,
        variant="base",
    )
    component_result, component_model, component_solver = solve_binding_variant(
        solution=solution,
        facility_pools=facility_pools,
        rules=rules,
        routing_context=routing_context,
        time_limit=binding_seconds,
        random_seed=random_seed,
        variant="component",
    )
    payload: dict[str, Any] = {
        "component_profile": profile,
        "base_binding": base_result,
        "component_binding": component_result,
    }
    if component_result["status"] == "INFEASIBLE":
        commodities = component_result.get("interface_stats", {}).get(
            "component_support", {}
        ).get("compiled_commodities", [])
        core = minimize_commodity_core(
            solution=solution,
            facility_pools=facility_pools,
            rules=rules,
            routing_context=routing_context,
            commodities=commodities,
            seconds_per_solve=core_seconds,
            random_seed=random_seed,
        )
        payload["commodity_core"] = core
        diagnostic_model, _ = build_binding_model(
            solution=solution,
            facility_pools=facility_pools,
            rules=rules,
            routing_context=routing_context,
        )
        payload["pocket_diagnostics"] = diagnose_forced_source_pockets(
            binding_model=diagnostic_model,
            context=routing_context,
            owner_by_cell=owner_by_cell,
            commodities=core.get("inclusion_minimal_candidate") or commodities,
            max_component_size=pocket_max_component_size,
        )
        payload["exact_routing"] = {
            "status": "NOT_REACHED_COMPONENT_INFEASIBLE"
        }
        return payload
    if component_result["status"] not in {"FEASIBLE", "OPTIMAL"}:
        payload["exact_routing"] = {
            "status": "NOT_REACHED_COMPONENT_BINDING_NONTERMINAL"
        }
        return payload

    assert component_solver is not None
    selected_bindings = component_model.extract_selected_bindings(component_solver)
    port_specs = component_model.extract_port_specs(component_solver)
    commodities = component_model.extract_commodities(component_solver)
    atomic_write_json(output_dir / "SELECTED_BINDINGS.json", selected_bindings)
    atomic_write_json(output_dir / "PORT_SPECS.json", port_specs)
    atomic_write_json(output_dir / "COMMODITIES.json", commodities)
    routing, routes = run_exact_routing(
        routing_core=routing_core,
        port_specs=port_specs,
        commodities=commodities,
        time_limit=routing_seconds,
        random_seed=random_seed,
    )
    payload["exact_routing"] = routing
    if routes is not None:
        atomic_write_json(output_dir / "ROUTES.json", routes)
    return payload


def render(result: Mapping[str, Any]) -> str:
    lines = [
        "E003 LOCAL RESULT DRAFT",
        "=======================",
        "",
        f"terminal_verdict: {result.get('terminal_verdict')}",
    ]
    for arm in result.get("arms", []):
        lines.append(
            f"{arm.get('moved_source_id')}: {arm.get('status')} "
            f"({arm.get('solver_stats', {}).get('wall_time_seconds')}s)"
        )
    winner = result.get("winning_arm")
    if winner:
        lines.extend(
            [
                f"winning_arm: {winner}",
                f"component_binding: {result.get('interface', {}).get('component_binding', {}).get('status')}",
                f"exact_routing: {result.get('interface', {}).get('exact_routing', {}).get('status')}",
            ]
        )
    lines.extend(
        [
            "",
            "Each arm fixes all A1 selected literals outside the cut, forces one",
            "cut literal off, and forces the other three on. No arm result has",
            "global or certified effect.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    e002 = load_json(Path(args.e002_result))
    if e002.get("terminal_verdict") != "MINIMAL_REPAIR_BOUNDED_NONTERMINAL":
        raise MatrixError(
            "E003 trigger not satisfied: "
            f"E002 terminal is {e002.get('terminal_verdict')!r}"
        )
    run_id = args.run_id or datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else RESEARCH_ROOT
        / "research_lab/local/E003_single_literal_repair_matrix"
        / run_id
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    result: dict[str, Any] = {
        "schema": "zmd_zero_condition_e003_result_v1",
        "run_id": run_id,
        "started_at": utc_now(),
        "output_dir": str(output_dir),
        "parameters": vars(args),
        "claim_effect": "research_only_fixed_single_literal_arms",
    }
    result_path = output_dir / "RUN_RESULT.json"
    try:
        result["admitted_external_inputs"] = {
            name: verify_input(name, spec) for name, spec in EXPECTED_INPUTS.items()
        }
        instances, facility_pools, rules, plan, identities = load_project_inputs()
        result["tracked_input_identities"] = identities
        a1_solution = parse_solution_payload(
            load_json(Path(EXPECTED_INPUTS["a1_assignment"]["path"]))
        )
        arms: list[dict[str, Any]] = []
        winning_solution: Mapping[str, int] | None = None
        winning_source: str | None = None
        for index, source_id in enumerate(POCKET_CONFLICT_SET):
            arm, solution = solve_arm(
                moved_source_id=source_id,
                a1_solution=a1_solution,
                instances=instances,
                facility_pools=facility_pools,
                rules=rules,
                plan=plan,
                seconds=float(args.arm_seconds),
                random_seed=int(args.random_seed) + index,
            )
            arms.append(arm)
            atomic_write_json(
                output_dir / f"ARM_{index + 1}_{source_id.replace(':', '_')}.json",
                arm,
            )
            if solution is not None:
                winning_solution = solution
                winning_source = source_id
                break
        result["arms"] = arms
        result["winning_arm"] = winning_source
        if winning_solution is None:
            statuses = {str(arm["status"]) for arm in arms}
            if statuses == {"INFEASIBLE"} and len(arms) == len(POCKET_CONFLICT_SET):
                result["terminal_verdict"] = "ALL_SINGLE_LITERAL_REPAIRS_INFEASIBLE"
            else:
                result["terminal_verdict"] = "NO_SINGLE_LITERAL_REPAIR_FOUND_UNDER_BOUNDS"
        else:
            atomic_write_json(output_dir / "REPAIRED_ASSIGNMENT.json", winning_solution)
            atomic_write_json(
                output_dir / "REPAIRED_LAYOUT.json",
                materialize_layout(winning_solution, instances, facility_pools),
            )
            result["interface"] = downstream(
                solution=winning_solution,
                instances=instances,
                facility_pools=facility_pools,
                rules=rules,
                binding_seconds=float(args.binding_seconds),
                core_seconds=float(args.core_seconds),
                routing_seconds=float(args.routing_seconds),
                random_seed=int(args.random_seed),
                pocket_max_component_size=int(args.pocket_max_component_size),
                output_dir=output_dir,
            )
            routing_status = result["interface"].get("exact_routing", {}).get("status")
            component_status = result["interface"].get("component_binding", {}).get("status")
            if routing_status in {"FEASIBLE", "OPTIMAL"}:
                result["terminal_verdict"] = "SINGLE_LITERAL_REPAIR_ROUTING_FEASIBLE"
            elif component_status == "INFEASIBLE":
                result["terminal_verdict"] = "SINGLE_LITERAL_REPAIR_COMPONENT_INFEASIBLE"
            else:
                result["terminal_verdict"] = "SINGLE_LITERAL_REPAIR_DOWNSTREAM_NONTERMINAL"
        result["completed_at"] = utc_now()
        atomic_write_json(result_path, result)
        atomic_write_text(output_dir / "DURABLE_RESULT_DRAFT.txt", render(result))
        return result
    except Exception as exc:
        result["terminal_verdict"] = "EXPERIMENT_ERROR"
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        result["completed_at"] = utc_now()
        atomic_write_json(result_path, result)
        atomic_write_text(output_dir / "DURABLE_RESULT_DRAFT.txt", render(result))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--e002-result",
        default=(
            RESEARCH_ROOT
            / "research_lab/local/E002_minimal_pocket_repair/minimal_repair_20260825/RUN_RESULT.json"
        ),
    )
    parser.add_argument("--run-id")
    parser.add_argument("--output-dir")
    parser.add_argument("--arm-seconds", type=float, default=120.0)
    parser.add_argument("--binding-seconds", type=float, default=120.0)
    parser.add_argument("--core-seconds", type=float, default=10.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--pocket-max-component-size", type=int, default=64)
    parser.add_argument("--random-seed", type=int, default=23)
    args = parser.parse_args()
    result = run(args)
    print(
        json.dumps(
            {
                "run_id": result.get("run_id"),
                "terminal_verdict": result.get("terminal_verdict"),
                "winning_arm": result.get("winning_arm"),
                "output_dir": result.get("output_dir"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result.get("terminal_verdict") != "EXPERIMENT_ERROR" else 2


if __name__ == "__main__":
    raise SystemExit(main())
