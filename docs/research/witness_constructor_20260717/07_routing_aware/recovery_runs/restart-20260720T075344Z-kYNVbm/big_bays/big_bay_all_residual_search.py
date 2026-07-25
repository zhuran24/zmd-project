#!/usr/bin/env python3
"""Persistent all-residual-connected fallback for one periodic large bay.

This is a stronger local condition than optional-terminal connectivity: every
unoccupied cell in the bay must have a descending parent path to a backbone
gateway.  The stronger equality removes the optional connected-subset symmetry.
No production router is imported or run.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
HERE = RECOVERY / "big_bays"
GEOMETRY_SCRIPT = HERE / "big_bay_pole_phase_search.py"
EXPECTED_GEOMETRY_SHA256 = "a31c8e9935eb038191960b937b1950318bc4f3af40ff83b76543d772b7aa805b"
Cell = tuple[int, int]


class SearchError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SearchError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


require(sha256(GEOMETRY_SCRIPT) == EXPECTED_GEOMETRY_SHA256, "geometry helper hash drift")
sys.path.insert(0, str(HERE))
import big_bay_pole_phase_search as geometry  # noqa: E402


def solve_all_residual(
    poses: tuple[Any, ...],
    target: tuple[int, int, int],
    fixed: Mapping[str, Any],
    hint_modes: set[tuple[str, str, frozenset[Cell]]],
    seconds: float,
    workers: int,
    seed: int,
) -> dict[str, Any]:
    groups: dict[tuple[str, frozenset[Cell]], list[Any]] = defaultdict(list)
    for pose in poses:
        groups[(pose.template, pose.body)].append(pose)
    model = cp_model.CpModel()
    mode_vars: dict[tuple[Any, ...], Any] = {}
    by_cell: dict[Cell, list[Any]] = defaultdict(list)
    by_template: dict[str, list[Any]] = defaultdict(list)
    ordered = sorted(groups.items(), key=lambda item: (item[0][0], tuple(sorted(item[0][1]))))
    for body_index, ((template, body), body_modes) in enumerate(ordered):
        body_var = model.new_bool_var(f"b{body_index}")
        by_template[template].append(body_var)
        for cell in body:
            by_cell[cell].append(body_var)
        subordinate = []
        for mode_index, pose in enumerate(sorted(body_modes, key=lambda item: item.key)):
            mode_var = model.new_bool_var(f"b{body_index}_m{mode_index}")
            mode_vars[pose.key] = mode_var
            subordinate.append(mode_var)
        model.add(sum(subordinate) == body_var)
    for terms in by_cell.values():
        model.add(sum(terms) <= 1)
    for template, count in zip(geometry.TEMPLATES, target, strict=True):
        model.add(sum(by_template[template]) == count)

    component = set(fixed["c5"])
    gateways = set(fixed["gateways"])
    outside_main = set(fixed["backbone"]) | set(fixed["protected"])
    free_vars: dict[Cell, Any] = {}
    ranks: dict[Cell, Any] = {}
    size = len(component)
    for cell_index, cell in enumerate(sorted(component)):
        free = model.new_bool_var(f"f{cell_index}")
        rank = model.new_int_var(0, size, f"r{cell_index}")
        free_vars[cell] = free
        ranks[cell] = rank
        model.add(free + sum(by_cell.get(cell, ())) == 1)
        model.add(rank <= size * free)
    parent_arc_count = 0
    for cell_index, cell in enumerate(sorted(component)):
        parents = []
        if cell in gateways:
            root = model.new_bool_var(f"p{cell_index}_root")
            model.add(root <= free_vars[cell])
            model.add(ranks[cell] >= 1).only_enforce_if(root)
            parents.append(root)
            parent_arc_count += 1
        for direction_index, adjacent in enumerate(geometry.neighbours(cell)):
            if adjacent not in component:
                continue
            parent = model.new_bool_var(f"p{cell_index}_{direction_index}")
            model.add(parent <= free_vars[cell])
            model.add(parent <= free_vars[adjacent])
            model.add(ranks[cell] >= ranks[adjacent] + 1).only_enforce_if(parent)
            parents.append(parent)
            parent_arc_count += 1
        model.add(sum(parents) == free_vars[cell])

    active_vars: dict[tuple[tuple[Any, ...], str, int], Any] = {}
    for pose_index, pose in enumerate(poses):
        mode_var = mode_vars[pose.key]
        need_in, need_out = geometry.base.REQUIREMENTS[pose.template]
        for kind, cells, need in (("input", pose.inputs, need_in), ("output", pose.outputs, need_out)):
            choices = []
            for port_index, cell in enumerate(cells):
                active = model.new_bool_var(f"t{pose_index}_{kind}_{port_index}")
                active_vars[(pose.key, kind, port_index)] = active
                model.add(active <= mode_var)
                if cell in component:
                    model.add(active <= free_vars[cell])
                else:
                    require(cell in outside_main, "active outside-main domain")
                choices.append(active)
            model.add(sum(choices) == need * mode_var)

    hinted_occupied: set[Cell] = set()
    for pose in poses:
        hinted = (pose.template, pose.mode, pose.body) in hint_modes
        model.add_hint(mode_vars[pose.key], int(hinted))
        if hinted:
            hinted_occupied.update(pose.body)
    hinted_free = component - hinted_occupied
    for cell in component:
        model.add_hint(free_vars[cell], int(cell in hinted_free))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    status = solver.solve(model)
    result: dict[str, Any] = {
        "status": solver.status_name(status),
        "wall_time_seconds": solver.wall_time,
        "branches": solver.num_branches,
        "conflicts": solver.num_conflicts,
        "target": list(target),
        "component_cells": size,
        "gateway_cells": len(gateways),
        "body_choices": len(groups),
        "eligible_pose_modes": len(poses),
        "parent_arc_count": parent_arc_count,
        "workers": workers,
        "seed": seed,
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return result

    selected = [pose for pose in poses if solver.boolean_value(mode_vars[pose.key])]
    occupied: set[Cell] = set()
    for pose in selected:
        require(not occupied & pose.body, "selected overlap")
        occupied.update(pose.body)
    free = component - occupied
    main = geometry.reachable(gateways, free)
    require(main == free, "all-residual model/replay drift")
    selected_active = []
    for selected_index, pose in enumerate(selected):
        for kind, cells in (("input", pose.inputs), ("output", pose.outputs)):
            for port_index, cell in enumerate(cells):
                if solver.boolean_value(active_vars[(pose.key, kind, port_index)]):
                    require(cell in outside_main or cell in main, "selected active disconnected")
                    require(cell not in occupied, "selected active occupied")
                    selected_active.append(
                        {
                            "selected_index": selected_index,
                            "kind": kind,
                            "port_index": port_index,
                            "cell": list(cell),
                        }
                    )
    observed = tuple(Counter(pose.template for pose in selected)[template] for template in geometry.TEMPLATES)
    require(observed == target, "selected target mismatch")
    require(all(pose.body & fixed["power"] for pose in selected), "selected unpowered")
    result.update(
        {
            "body_cells": len(occupied),
            "residual_cells": len(free),
            "residual_main_cells": len(main),
            "all_residual_connected": True,
            "selected_weak_active_count": len(selected_active),
            "selected_weak_active": selected_active,
            "selected": [
                {
                    "template": pose.template,
                    "mode": pose.mode,
                    "pose_index": pose.pose_index,
                    "anchor": list(pose.anchor),
                    "body": [list(cell) for cell in sorted(pose.body)],
                    "inputs": [list(cell) for cell in pose.inputs],
                    "outputs": [list(cell) for cell in pose.outputs],
                }
                for pose in selected
            ],
            "independent_verification": {
                "no_body_overlap": True,
                "exact_template_totals": True,
                "all_selected_bodies_powered": True,
                "all_selected_weak_active_connected": True,
                "all_residual_connected": True,
            },
        }
    )
    return result


def output_path(bay_name: str, target: tuple[int, int, int], moved_x: int, y_shift: int, seconds: float) -> Path:
    target_text = "-".join(str(value) for value in target)
    shift_text = f"p{y_shift}" if y_shift >= 0 else f"m{-y_shift}"
    return HERE / "all_residual_attempts" / bay_name / f"t{target_text}_x{moved_x}_dy{shift_text}_s{int(seconds)}.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bay", choices=tuple(geometry.BAYS), default="c0")
    parser.add_argument("--target", type=int, nargs=3, default=(10, 5, 4))
    parser.add_argument("--moved-x", type=int)
    parser.add_argument("--uniform-y-shift", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=240.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    require(180.0 <= args.seconds <= 300.0, "seconds must be within [180,300]")
    require(args.workers == 8, "fallback is pinned to 8 workers")
    target = tuple(args.target)
    require(len(target) == 3 and all(value >= 0 for value in target), "target")
    bay = geometry.BAYS[args.bay]
    moved_x = int(args.moved_x) if args.moved_x is not None else int(bay["pole_x"]) + 1
    output = output_path(args.bay, target, moved_x, args.uniform_y_shift, args.seconds)
    require(not output.exists(), f"refusing overwrite: {output}")
    candidate = geometry.load_pinned(geometry.CANDIDATE_PATH)
    strict = geometry.load_pinned(geometry.STRICT_PATH)
    old = geometry.load_pinned(geometry.HINT_PATH)
    modes = geometry.base.strict_modes(strict)
    fixed = geometry.fixed_geometry(strict, args.bay, moved_x, args.uniform_y_shift)
    poses, domain_counts = geometry.base.build_domain(candidate, modes, fixed)
    hints = geometry.hint_body_modes(old, args.bay, fixed["origin"])
    result = solve_all_residual(
        poses,
        target,
        fixed,
        hints,
        args.seconds,
        args.workers,
        20260720 + int(bay["component"]),
    )
    moved = sorted((moved_x, y + args.uniform_y_shift) for y in geometry.POLE_ROWS)
    result.update(
        {
            "schema_version": "big_bay_all_residual_checkpoint.v1",
            "classification": "research_local_all_residual_parent_query_no_router",
            "claim_boundary": "One local large bay and pole phase only; no global layout or commodity-routing conclusion.",
            "bay": args.bay,
            "component": int(bay["component"]),
            "origin": list(fixed["origin"]),
            "target": list(target),
            "moved_x": moved_x,
            "uniform_y_shift": args.uniform_y_shift,
            "moved_pole_anchors": [list(anchor) for anchor in moved],
            "all_35_pole_anchors": [list(anchor) for anchor in sorted(fixed["pole_anchors"])],
            "domain_counts": domain_counts,
            "seconds_limit": args.seconds,
            "search_script_sha256": sha256(Path(__file__)),
            "geometry_script_sha256": EXPECTED_GEOMETRY_SHA256,
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "status": result["status"]}, sort_keys=True))
    return 0 if result["status"] in {"OPTIMAL", "FEASIBLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
