#!/usr/bin/env python3
"""Pure-stdlib count and geometry reconnaissance for the restart recovery run.

This script deliberately imports neither OR-Tools nor any router module.  It
only replays pinned JSON, exact integer arithmetic, grid connectivity, power
coverage, and candidate-pool incidence.  All outputs use exclusive creation.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
RECOVERY = HERE.parent
ROOT = HERE.parents[6]
BASELINE_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
BASELINE = RECOVERY / "inputs/reduced_targeted_allocation_p7_36_final.json"
CANDIDATE = ROOT / "data/preprocessed/candidate_placements.json"
STRICT = ROOT / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
EXPECTED_CORE_SHA256 = {
    BASELINE: "6c51a1ee5bef15e555242896a0a11da24c8f18746a215db53c277deee537ee80",
    CANDIDATE: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}
CATALOG_OUTPUT = HERE / "observed_target_catalog.json"
PAIR_OUTPUT = HERE / "pair_candidate_catalog.json"
REPORT_OUTPUT = HERE / "static_closure_report.json"
GLOBAL_TARGET = (132, 49, 38)
TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
BODY_AREAS = (9, 25, 24)
ACTIVE_INCIDENCE = (2, 2, 4)
REQUIREMENTS = {
    "manufacturing_3x3": (1, 1),
    "manufacturing_5x5": (1, 1),
    "manufacturing_6x4": (3, 1),
}
GRID_SIZE = 70
GRID = {(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)}
VERTICAL_LANES = (1, 12, 24, 36, 48, 59)
HORIZONTAL_LANES = (1, 36, 59)
POLE_AXES = (5, 17, 29, 41, 53, 65)
CORE_ANCHOR = (60, 60)
PROTECTED = (7, 36, 6, 7)
Cell = tuple[int, int]
Triple = tuple[int, int, int]


class StaticAuditError(RuntimeError):
    """Fail-closed input or replay error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StaticAuditError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def write_exclusive(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def triple(value: Sequence[object]) -> Triple:
    require(len(value) == 3, f"not a triple: {value!r}")
    result = tuple(int(item) for item in value)
    require(all(item >= 0 for item in result), f"negative count: {result!r}")
    return result  # type: ignore[return-value]


def add(left: Triple, right: Triple) -> Triple:
    return tuple(left[index] + right[index] for index in range(3))  # type: ignore[return-value]


def sub(left: Triple, right: Triple) -> Triple:
    return tuple(left[index] - right[index] for index in range(3))  # type: ignore[return-value]


def sum_triples(values: Iterable[Triple]) -> Triple:
    total = (0, 0, 0)
    for value in values:
        total = add(total, value)
    return total


def body_area(value: Triple) -> int:
    return sum(value[index] * BODY_AREAS[index] for index in range(3))


def active_incidence(value: Triple) -> int:
    return sum(value[index] * ACTIVE_INCIDENCE[index] for index in range(3))


def rect(anchor: Cell, width: int, height: int) -> set[Cell]:
    return {
        (x, y)
        for x in range(anchor[0], anchor[0] + width)
        for y in range(anchor[1], anchor[1] + height)
    }


def neighbours(cell: Cell) -> tuple[Cell, Cell, Cell, Cell]:
    x, y = cell
    return ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))


def connected_component(seed: Cell, free: set[Cell]) -> set[Cell]:
    require(seed in free, f"component seed blocked: {seed}")
    seen = {seed}
    queue = deque(seen)
    while queue:
        cell = queue.popleft()
        for adjacent in neighbours(cell):
            if adjacent in free and adjacent not in seen:
                seen.add(adjacent)
                queue.append(adjacent)
    return seen


def boundary_anchors(gap: int) -> list[int]:
    return list(range(0, gap, 3)) + [gap + 1 + 3 * index for index in range(23 - gap // 3)]


def status_class(statuses: set[str]) -> str:
    if statuses & {"OPTIMAL", "FEASIBLE", "FEASIBLE_REPLAY"}:
        return "FEASIBLE_EXISTS"
    if "UNKNOWN" in statuses:
        return "UNKNOWN_EXISTS"
    if statuses == {"INFEASIBLE"}:
        return "INFEASIBLE_ONLY"
    if not statuses:
        return "UNEXPLORED"
    return "OTHER_OBSERVED"


def normalized_status(value: object) -> str | None:
    if value in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"}:
        return str(value)
    return None


def observation(
    path: Path,
    component: int,
    target: Sequence[object],
    status: str,
    *,
    model: str,
    moved_x: object = None,
    y_shift: object = None,
    component_cells: object = None,
    residual_cells: object = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "component": component,
        "target": list(triple(target)),
        "status": status,
        "model": model,
        "source": str(path.relative_to(ROOT)),
        "source_sha256": sha256(path),
    }
    if moved_x is not None:
        row["moved_x"] = int(moved_x)
    if y_shift is not None:
        row["uniform_y_shift"] = int(y_shift)
    if component_cells is not None:
        row["component_cells"] = int(component_cells)
    if residual_cells is not None:
        row["residual_cells"] = int(residual_cells)
    return row


def collect_observations() -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    rows: list[dict[str, object]] = []
    sources: dict[Path, str] = {}

    def used(path: Path) -> Any:
        sources[path] = sha256(path)
        return load_json(path)

    for path in sorted((RECOVERY / "fixed_bays").glob("*.json")):
        data = used(path)
        for query in data.get("queries", ()) if isinstance(data, Mapping) else ():
            status = normalized_status(query.get("status"))
            target = query.get("target")
            component = query.get("component")
            if status is None or not isinstance(target, Sequence) or component is None:
                continue
            rows.append(
                observation(
                    path,
                    int(component),
                    target,
                    status,
                    model="weak_active_terminal_parent",
                    component_cells=query.get("component_cells"),
                    residual_cells=query.get("residual_cells"),
                )
            )

    for path in sorted((RECOVERY / "fixed_bays/final35_small_bay_closure").glob("c*_target_*.json")):
        data = used(path)
        status = normalized_status(data.get("status"))
        if status is None:
            continue
        component = data.get("requested_component", data.get("component"))
        require(component is not None, f"component missing: {path}")
        rows.append(
            observation(
                path,
                int(component),
                data["target"],
                status,
                model=str(data.get("locality", "final35_small_bay")),
                component_cells=data.get("component_cells"),
            )
        )

    c3_path = RECOVERY / "c3/c3_pole_phase_search.json"
    c3 = used(c3_path)
    for attempt in c3["attempts"]:
        status = normalized_status(attempt.get("status"))
        if status is None:
            continue
        rows.append(
            observation(
                c3_path,
                3,
                attempt["target"],
                status,
                model="c3_pole_phase_weak_active_terminal_parent",
                moved_x=attempt.get("moved_x"),
                y_shift=attempt.get("uniform_y_shift"),
                component_cells=attempt.get("component_cells"),
                residual_cells=attempt.get("residual_cells"),
            )
        )

    c5_direct_path = RECOVERY / "c5/c5_direct_winner_query.json"
    c5_direct = used(c5_direct_path)["query"]
    direct_status = normalized_status(c5_direct.get("status"))
    require(direct_status is not None, "c5 direct winner status")
    rows.append(
        observation(
            c5_direct_path,
            5,
            c5_direct["target"],
            direct_status,
            model="c5_custom_pole_all_residual_parent",
            moved_x=c5_direct.get("moved_x"),
            y_shift=c5_direct.get("uniform_y_shift"),
            component_cells=c5_direct.get("component_cells"),
            residual_cells=c5_direct.get("residual_cells"),
        )
    )

    for path in sorted((RECOVERY / "c5").glob("queries-*/attempt_*.json")):
        data = used(path)
        query = data.get("query", {})
        status = normalized_status(query.get("status"))
        if status is None:
            continue
        rows.append(
            observation(
                path,
                5,
                query["target"],
                status,
                model="c5_custom_pole_weak_active_terminal_parent",
                moved_x=query.get("moved_x"),
                y_shift=query.get("uniform_y_shift"),
                component_cells=query.get("component_cells"),
                residual_cells=query.get("residual_cells"),
            )
        )

    for path in sorted((RECOVERY / "c5").glob("count-closure-*/attempt_*target_*.json")):
        if path.name.endswith("_start.json"):
            continue
        data = used(path)
        result = data.get("result", {})
        status = normalized_status(result.get("status"))
        if status is None:
            continue
        phase = data.get("phase", {})
        rows.append(
            observation(
                path,
                5,
                result.get("target", data["target"]),
                status,
                model="c5_count_closure_weak_active_terminal_parent",
                moved_x=phase.get("moved_x"),
                y_shift=phase.get("uniform_y_shift"),
                component_cells=result.get("component_cells", data.get("static_capacity", {}).get("component_cells")),
                residual_cells=result.get("residual_cells"),
            )
        )

    for directory, model in (
        ("big_bays/attempts/c0", "big_optional_terminal_parent"),
        ("big_bays/all_residual_attempts/c0", "big_all_residual_parent"),
        ("big_bays/final35_attempts/c0", "big_final35_parent"),
    ):
        for path in sorted((RECOVERY / directory).glob("*.json")):
            data = used(path)
            query = data.get("query", data)
            status = normalized_status(query.get("status"))
            if status is None:
                continue
            rows.append(
                observation(
                    path,
                    int(query.get("component", 0)),
                    query["target"],
                    status,
                    model=model,
                    moved_x=query.get("moved_x"),
                    y_shift=query.get("uniform_y_shift"),
                    component_cells=query.get("component_cells"),
                    residual_cells=query.get("residual_cells"),
                )
            )

    periodic_path = RECOVERY / "big_bays/periodic_big_bay_selection.json"
    periodic = used(periodic_path)
    replay_path = RECOVERY / "big_bays/independent_periodic_big_bay_replay.json"
    replay = used(replay_path)
    require(periodic.get("status") == "THREE_PERIODIC_BIG_BAYS_REPLAYED", "periodic selection status")
    require(replay.get("status") == "PASS", "periodic independent replay status")
    for name, bay in sorted(periodic["bays"].items()):
        component = int(name.removeprefix("c"))
        rows.append(
            observation(
                periodic_path,
                component,
                bay["target"],
                "FEASIBLE_REPLAY",
                model="independent_periodic_big_bay_replay",
                moved_x=18 + 12 * component,
                y_shift=0,
                component_cells=bay.get("component_cells"),
                residual_cells=bay.get("residual_cells"),
            )
        )

    rows.sort(
        key=lambda row: (
            int(row["component"]),
            tuple(row["target"]),
            str(row["status"]),
            str(row["source"]),
            int(row.get("moved_x", -1)),
            int(row.get("uniform_y_shift", 0)),
        )
    )
    source_rows = [
        {"path": str(path.relative_to(ROOT)), "sha256": digest}
        for path, digest in sorted(sources.items(), key=lambda item: str(item[0]))
    ]
    return rows, source_rows


def aggregate_catalog(observations: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[int, Triple], list[Mapping[str, object]]] = {}
    for row in observations:
        key = (int(row["component"]), triple(row["target"]))  # type: ignore[arg-type]
        groups.setdefault(key, []).append(row)
    result = []
    for (component, target), rows in sorted(groups.items()):
        statuses = {str(row["status"]) for row in rows}
        phases = sorted(
            {
                (int(row["moved_x"]), int(row.get("uniform_y_shift", 0)), str(row["status"]))
                for row in rows
                if "moved_x" in row
            }
        )
        result.append(
            {
                "component": component,
                "target": list(target),
                "body_cells": body_area(target),
                "active_incidence": active_incidence(target),
                "catalog_status": status_class(statuses),
                "observed_statuses": sorted(statuses),
                "observations": len(rows),
                "observed_phases": [
                    {"moved_x": phase[0], "uniform_y_shift": phase[1], "status": phase[2]}
                    for phase in phases
                ],
            }
        )
    return result


def catalog_lookup(catalog: Sequence[Mapping[str, object]]) -> dict[tuple[int, Triple], str]:
    return {
        (int(row["component"]), triple(row["target"])): str(row["catalog_status"])  # type: ignore[arg-type]
        for row in catalog
    }


def feasible_options(catalog: Sequence[Mapping[str, object]]) -> dict[int, tuple[Triple, ...]]:
    options: dict[int, set[Triple]] = {}
    for row in catalog:
        if row["catalog_status"] == "FEASIBLE_EXISTS":
            options.setdefault(int(row["component"]), set()).add(triple(row["target"]))  # type: ignore[arg-type]
    require(set(options) == set(range(17)), f"missing feasible component options: {set(range(17)) - set(options)}")
    return {component: tuple(sorted(values)) for component, values in sorted(options.items())}


def enumerate_single_new(
    options: Mapping[int, Sequence[Triple]],
    sizes: Mapping[int, int],
    lookup: Mapping[tuple[int, Triple], str],
) -> list[dict[str, object]]:
    fixed_components = (0, 1, 2, 3)
    require(all(len(options[component]) == 1 for component in fixed_components), "fixed prefix option cardinality")
    fixed_sum = sum_triples(options[component][0] for component in fixed_components)
    variable = tuple(range(4, 17))
    rows: dict[tuple[object, ...], dict[str, object]] = {}
    for unresolved in variable:
        other = tuple(component for component in variable if component != unresolved)
        for selected in itertools.product(*(options[component] for component in other)):
            required = sub(GLOBAL_TARGET, add(fixed_sum, sum_triples(selected)))
            if min(required) < 0 or sum(required) == 0 or body_area(required) > sizes[unresolved]:
                continue
            if required in options[unresolved]:
                continue
            status = lookup.get((unresolved, required), "UNEXPLORED")
            assignment = tuple(zip(other, selected, strict=True))
            key = (unresolved, required, assignment)
            rows[key] = {
                "unresolved_component": unresolved,
                "required_target": list(required),
                "catalog_status": status,
                "passes_observed_infeasible_filter": status != "INFEASIBLE_ONLY",
                "component_cells": sizes[unresolved],
                "body_cells": body_area(required),
                "residual_cells": sizes[unresolved] - body_area(required),
                "active_incidence": active_incidence(required),
                "unexplored_target_count": int(status == "UNEXPLORED"),
                "attempted_unknown_target_count": int(status == "UNKNOWN_EXISTS"),
                "known_assignment": {str(component): list(target) for component, target in assignment},
            }
    return sorted(
        rows.values(),
        key=lambda row: (
            not bool(row["passes_observed_infeasible_filter"]),
            -int(row["residual_cells"]),
            int(row["active_incidence"]),
            int(row["unexplored_target_count"]),
            int(row["unresolved_component"]),
            tuple(row["required_target"]),
        ),
    )


def area_feasible_targets(size: int) -> tuple[Triple, ...]:
    values = []
    for count3 in range(size // BODY_AREAS[0] + 1):
        for count5 in range(size // BODY_AREAS[1] + 1):
            for count6 in range(size // BODY_AREAS[2] + 1):
                target = (count3, count5, count6)
                if sum(target) and body_area(target) <= size:
                    values.append(target)
    return tuple(values)


def enumerate_pair_fallbacks(
    references: Mapping[str, Mapping[int, Triple]],
    sizes: Mapping[int, int],
    lookup: Mapping[tuple[int, Triple], str],
) -> list[dict[str, object]]:
    all_targets = {component: area_feasible_targets(size) for component, size in sizes.items()}
    target_sets = {component: set(values) for component, values in all_targets.items()}
    rows: list[dict[str, object]] = []
    for reference_name, reference in references.items():
        require(sum_triples(reference.values()) != GLOBAL_TARGET, f"pair reference unexpectedly closed: {reference_name}")
        for first, second in itertools.combinations(range(4, 17), 2):
            fixed_sum = sum_triples(
                target for component, target in reference.items() if component not in {first, second}
            )
            required_pair = sub(GLOBAL_TARGET, fixed_sum)
            for first_target in all_targets[first]:
                second_target = sub(required_pair, first_target)
                if min(second_target) < 0 or second_target not in target_sets[second]:
                    continue
                if first_target == reference[first] or second_target == reference[second]:
                    continue
                first_status = lookup.get((first, first_target), "UNEXPLORED")
                second_status = lookup.get((second, second_target), "UNEXPLORED")
                if "FEASIBLE_EXISTS" in {first_status, second_status}:
                    continue
                statuses = (first_status, second_status)
                residuals = (sizes[first] - body_area(first_target), sizes[second] - body_area(second_target))
                incidences = (active_incidence(first_target), active_incidence(second_target))
                l1_change = sum(
                    abs(first_target[index] - reference[first][index])
                    + abs(second_target[index] - reference[second][index])
                    for index in range(3)
                )
                rows.append(
                    {
                        "reference": reference_name,
                        "components": [first, second],
                        "targets": [list(first_target), list(second_target)],
                        "catalog_statuses": list(statuses),
                        "passes_observed_infeasible_filter": "INFEASIBLE_ONLY" not in statuses,
                        "residual_cells": list(residuals),
                        "minimum_residual_cells": min(residuals),
                        "total_residual_cells": sum(residuals),
                        "active_incidence": list(incidences),
                        "maximum_active_incidence": max(incidences),
                        "unexplored_target_count": sum(status == "UNEXPLORED" for status in statuses),
                        "attempted_unknown_target_count": sum(status == "UNKNOWN_EXISTS" for status in statuses),
                        "l1_count_change": l1_change,
                    }
                )
    rows.sort(
        key=lambda row: (
            not bool(row["passes_observed_infeasible_filter"]),
            -int(row["minimum_residual_cells"]),
            int(row["maximum_active_incidence"]),
            int(row["unexplored_target_count"]),
            -int(row["total_residual_cells"]),
            int(row["l1_count_change"]),
            str(row["reference"]),
            tuple(row["components"]),
            tuple(tuple(value) for value in row["targets"]),
        )
    )
    return rows


def base_geometry() -> dict[str, set[Cell]]:
    core = rect(CORE_ANCHOR, 9, 9)
    backbone = (
        {(x, y) for x in VERTICAL_LANES for y in range(1, GRID_SIZE)}
        | {(x, y) for y in HORIZONTAL_LANES for x in range(1, GRID_SIZE)}
        | (rect((59, 59), 11, 11) - core)
    ) - core
    protected = rect((PROTECTED[0], PROTECTED[1]), PROTECTED[2], PROTECTED[3])
    boundary = (
        {(0, y) for anchor in boundary_anchors(69) for y in range(anchor, anchor + 3)}
        | {(x, 0) for anchor in boundary_anchors(0) for x in range(anchor, anchor + 3)}
    )
    return {"core": core, "backbone": backbone, "protected": protected, "boundary": boundary}


def combined_poles(c5_x: int = 66, c5_y_shift: int = 0) -> set[Cell]:
    baseline = {(x, y) for x in POLE_AXES for y in POLE_AXES} - {(65, 65)}
    big_old = {(x, y) for x in (17, 29, 41) for y in (5, 17, 29)}
    c5_old = {(65, y) for y in (5, 17, 29)}
    return (
        baseline
        - big_old
        - c5_old
        | {(x + 1, y) for x, y in big_old}
        | {(c5_x, y + c5_y_shift) for _x, y in c5_old}
    )


def audit_component_geometry(
    candidate: Mapping[str, object],
    strict: Mapping[str, object],
    poles: set[Cell],
    seed: Cell,
    target: Triple,
) -> dict[str, object]:
    fixed = base_geometry()
    pole_cells = set().union(*(rect(anchor, 2, 2) for anchor in poles))
    pole_pool = {
        (int(row["anchor"]["x"]), int(row["anchor"]["y"]))
        for row in candidate["facility_pools"]["power_pole"]  # type: ignore[index]
    }
    collisions = {
        key: len(pole_cells & fixed[key]) for key in ("core", "backbone", "protected", "boundary")
    }
    valid = (
        len(poles) == 35
        and len(pole_cells) == 140
        and pole_cells <= GRID
        and poles <= pole_pool
        and not any(collisions.values())
    )
    fixed_body = fixed["core"] | fixed["boundary"] | pole_cells
    free = GRID - (fixed_body | fixed["backbone"] | fixed["protected"])
    component = connected_component(seed, free)
    gateways = {
        cell for cell in component if any(adjacent in fixed["backbone"] for adjacent in neighbours(cell))
    }
    power_rule = strict["power"]["coverage_from_pole_anchor"]  # type: ignore[index]
    power = {
        (x, y)
        for anchor in poles
        for x in range(
            max(0, anchor[0] + int(power_rule["x_min_offset"])),
            min(GRID_SIZE - 1, anchor[0] + int(power_rule["x_max_offset"])) + 1,
        )
        for y in range(
            max(0, anchor[1] + int(power_rule["y_min_offset"])),
            min(GRID_SIZE - 1, anchor[1] + int(power_rule["y_max_offset"])) + 1,
        )
    }
    body_legal = Counter()
    powered = Counter()
    eligible = Counter()
    for template in TEMPLATES:
        need_in, need_out = REQUIREMENTS[template]
        for raw in candidate["facility_pools"][template]:  # type: ignore[index]
            body = {(int(cell[0]), int(cell[1])) for cell in raw["occupied_cells"]}
            if not body <= component:
                continue
            body_legal[template] += 1
            if not body & power:
                continue
            powered[template] += 1
            inputs = {
                (int(cell["x"]), int(cell["y"])) for cell in raw["input_port_cells"]
            } - fixed_body
            outputs = {
                (int(cell["x"]), int(cell["y"])) for cell in raw["output_port_cells"]
            } - fixed_body
            if len(inputs) >= need_in and len(outputs) >= need_out:
                eligible[template] += 1
    return {
        "valid_35_pole_candidate_geometry": valid,
        "pole_count": len(poles),
        "pole_body_cells": len(pole_cells),
        "missing_candidate_pole_anchors": [list(cell) for cell in sorted(poles - pole_pool)],
        "fixed_collision_cells": collisions,
        "component_cells": len(component),
        "gateway_cells": len(gateways),
        "power_covered_component_cells": len(component & power),
        "power_uncovered_component_cells": len(component - power),
        "target": list(target),
        "target_body_cells": body_area(target),
        "target_residual_cells": len(component) - body_area(target),
        "target_area_fits": body_area(target) <= len(component),
        "body_legal_pose_modes": {template: body_legal[template] for template in TEMPLATES},
        "powered_pose_modes": {template: powered[template] for template in TEMPLATES},
        "eligible_pose_modes": {template: eligible[template] for template in TEMPLATES},
        "target_has_nonempty_eligible_domain_per_template": all(
            not target[index] or eligible[template] > 0
            for index, template in enumerate(TEMPLATES)
        ),
    }


def phase_statuses(
    observations: Sequence[Mapping[str, object]],
    component: int,
    target: Triple,
    moved_x: int,
    y_shift: int,
) -> list[str]:
    return sorted(
        {
            str(row["status"])
            for row in observations
            if int(row["component"]) == component
            and triple(row["target"]) == target  # type: ignore[arg-type]
            and row.get("moved_x") == moved_x
            and int(row.get("uniform_y_shift", 0)) == y_shift
        }
    )


def c5_phase_audits(
    candidate: Mapping[str, object],
    strict: Mapping[str, object],
    observations: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    targets = ((13, 4, 4), (11, 5, 4), (10, 4, 4), (12, 3, 3))
    result = []
    for moved_x in (64, 65, 66, 67, 68):
        for y_shift in (-2, -1, 0, 1, 2):
            row = audit_component_geometry(
                candidate,
                strict,
                combined_poles(moved_x, y_shift),
                (60, 2),
                (10, 4, 4),
            )
            row.update(
                {
                    "moved_x": moved_x,
                    "uniform_y_shift": y_shift,
                    "component_expansion_vs_x66_dy0": int(row["component_cells"]) - 328,
                    "query_status_by_target": {
                        "-".join(str(value) for value in target): (
                            phase_statuses(observations, 5, target, moved_x, y_shift) or ["UNQUERIED"]
                        )
                        for target in targets
                    },
                }
            )
            result.append(row)
    return result


def shifted_c10_c11_audits(
    candidate: Mapping[str, object], strict: Mapping[str, object]
) -> list[dict[str, object]]:
    baseline = combined_poles(66, 0)
    cases = (
        ("c10_baseline", 10, set(), set(), (60, 37), (9, 2, 2), "INFEASIBLE under old fixed geometry"),
        (
            "c10_shift_65_to_66_y41_y53",
            10,
            {(65, 41), (65, 53)},
            {(66, 41), (66, 53)},
            (60, 37),
            (9, 2, 2),
            "UNQUERIED under shifted geometry",
        ),
        ("c11_baseline", 11, set(), set(), (2, 37), (9, 1, 2), "INFEASIBLE under old fixed geometry"),
        (
            "c11_shift_5_to_6_y41_y53",
            11,
            {(5, 41), (5, 53)},
            {(6, 41), (6, 53)},
            (2, 37),
            (9, 1, 2),
            "STATICALLY INVALID: pole body intersects protected cells",
        ),
        (
            "c11_control_shift_y53_only",
            11,
            {(5, 53)},
            {(6, 53)},
            (2, 37),
            (9, 1, 2),
            "UNQUERIED collision-free control; not a feasibility conclusion",
        ),
    )
    result = []
    for name, component, remove, add_cells, seed, target, query_status in cases:
        require(remove <= baseline, f"shift source missing: {name}")
        poles = (baseline - remove) | add_cells
        row = audit_component_geometry(candidate, strict, poles, seed, target)
        row.update(
            {
                "case": name,
                "component": component,
                "removed_pole_anchors": [list(cell) for cell in sorted(remove)],
                "added_pole_anchors": [list(cell) for cell in sorted(add_cells)],
                "query_status": query_status,
            }
        )
        result.append(row)
    return result


def main() -> int:
    require(HERE.parent == RECOVERY, "recovery parent drift")
    require(ROOT.name == "zmd-pj-codex", f"project root drift: {ROOT}")
    for path, expected in EXPECTED_CORE_SHA256.items():
        require(path.is_file() and not path.is_symlink(), f"core source not regular: {path}")
        require(sha256(path) == expected, f"core source hash drift: {path}")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    require(head == BASELINE_HEAD, f"baseline HEAD drift: {head}")

    baseline = load_json(BASELINE)
    candidate = load_json(CANDIDATE)
    strict = load_json(STRICT)
    baseline_counts = {int(component): triple(value) for component, value in baseline["allocation"].items()}
    sizes = {int(row["component"]): int(row["size"]) for row in baseline["components"]}
    require(set(baseline_counts) == set(range(17)) == set(sizes), "component ids")
    require(sum_triples(baseline_counts.values()) == GLOBAL_TARGET, "baseline count total")

    observations, observation_sources = collect_observations()
    catalog = aggregate_catalog(observations)
    lookup = catalog_lookup(catalog)
    options = feasible_options(catalog)
    single_new = enumerate_single_new(options, sizes, lookup)

    reference_a = {
        0: (10, 5, 4), 1: (10, 5, 4), 2: (10, 5, 4), 3: (12, 4, 3),
        4: (10, 4, 4), 5: (12, 3, 3), 6: (9, 3, 2), 7: (9, 3, 2),
        8: (9, 3, 2), 9: (7, 3, 2), 10: (7, 2, 2), 11: (8, 1, 2),
        12: (4, 1, 1), 13: (4, 1, 1), 14: (4, 1, 1), 15: (3, 2, 0), 16: (3, 2, 0),
    }
    reference_b = dict(reference_a)
    reference_b[9] = (9, 2, 2)
    references = {"A_c9_7_3_2": reference_a, "B_c9_9_2_2": reference_b}
    pair_rows = enumerate_pair_fallbacks(references, sizes, lookup)
    c5_phases = c5_phase_audits(candidate, strict, observations)
    neighbour_audits = shifted_c10_c11_audits(candidate, strict)

    clean_plan = dict(reference_a)
    clean_plan[5] = (10, 4, 4)
    clean_plan[10] = (9, 2, 2)
    clean_plan[11] = (9, 1, 2)
    require(sum_triples(clean_plan.values()) == GLOBAL_TARGET, "clean-plan integer closure")

    catalog_document = {
        "schema_version": "static_observed_target_catalog.v1",
        "status": "STATIC_CATALOG_COMPLETE_FOR_DISCOVERED_SOURCES",
        "classification": "research_pure_stdlib_count_catalog_no_solver_no_router",
        "claim_boundary": (
            "Observed statuses retain their local geometry and model scope. INFEASIBLE_ONLY means all discovered "
            "observations for that component/count target were exact infeasible results; it is not a theorem for "
            "unqueried pole geometries. Baseline allocation rows are placement-only and are not promoted here."
        ),
        "baseline_head": head,
        "global_target": list(GLOBAL_TARGET),
        "baseline_allocation": {str(component): list(value) for component, value in baseline_counts.items()},
        "component_cells": {str(component): size for component, size in sizes.items()},
        "source_artifacts": observation_sources,
        "observations": observations,
        "aggregated_targets": catalog,
        "known_feasible_options": {
            str(component): [list(value) for value in values] for component, values in options.items()
        },
        "single_new_target_candidates": single_new,
    }
    pair_document = {
        "schema_version": "static_two_new_local_target_catalog.v1",
        "status": "STATIC_INTEGER_ENUMERATION_COMPLETE",
        "classification": "research_exact_integer_enumeration_no_solver_no_router",
        "claim_boundary": (
            "Every row is count arithmetic plus body-area filtering only. A passing row still needs new local "
            "packing, strict replay, combined geometry replay, assembly, and routing. Observed exact infeasible "
            "targets are filtered only in their discovered geometry/model scope."
        ),
        "sort_order": [
            "passes_observed_infeasible_filter descending",
            "minimum_residual_cells descending",
            "maximum_active_incidence ascending",
            "unexplored_target_count ascending",
            "total_residual_cells descending",
            "l1_count_change ascending",
        ],
        "references": {
            name: {
                "counts": {str(component): list(target) for component, target in reference.items()},
                "subtotal": list(sum_triples(reference.values())),
                "deficit": list(sub(GLOBAL_TARGET, sum_triples(reference.values()))),
            }
            for name, reference in references.items()
        },
        "candidate_count": len(pair_rows),
        "passing_observed_infeasible_filter_count": sum(
            bool(row["passes_observed_infeasible_filter"]) for row in pair_rows
        ),
        "candidates": pair_rows,
    }
    write_exclusive(CATALOG_OUTPUT, catalog_document)
    write_exclusive(PAIR_OUTPUT, pair_document)

    focus_single = [
        row for row in single_new
        if tuple(row["required_target"]) in {(13, 4, 4), (11, 5, 4)}
    ]
    baseline_c5_status = {
        str(moved_x): next(
            row["query_status_by_target"]["10-4-4"]
            for row in c5_phases
            if row["moved_x"] == moved_x and row["uniform_y_shift"] == 0
        )
        for moved_x in (64, 65, 66)
    }
    report = {
        "schema_version": "static_count_closure_report.v1",
        "status": "STATIC_RECONNAISSANCE_COMPLETE",
        "classification": "research_pure_stdlib_static_reconnaissance_no_solver_no_router",
        "claim_boundary": (
            "This report establishes exact count identities, body-area necessary conditions, fixed-cell geometry, "
            "candidate incidence, and power incidence only. It does not establish any new local packing, full "
            "layout, commodity route, lower-bound artifact, or optimality statement."
        ),
        "baseline_head": head,
        "core_input_sha256": {str(path.relative_to(ROOT)): digest for path, digest in EXPECTED_CORE_SHA256.items()},
        "catalog_summary": {
            "observations": len(observations),
            "aggregated_component_target_rows": len(catalog),
            "single_new_assignment_rows": len(single_new),
            "single_new_passing_rows": sum(bool(row["passes_observed_infeasible_filter"]) for row in single_new),
            "pair_candidate_rows": len(pair_rows),
            "pair_passing_rows": sum(bool(row["passes_observed_infeasible_filter"]) for row in pair_rows),
        },
        "single_target_focus": focus_single,
        "single_target_conclusion": (
            "The two clean one-new-target identities are c5=(13,4,4) with c9=(7,3,2), and c5=(11,5,4) "
            "with c9=(9,2,2). Both are now exact INFEASIBLE results in every queried c5 phase recorded by the "
            "catalog, so neither queried-phase route remains a usable closure."
        ),
        "top_pair_fallbacks_after_filter": [
            row for row in pair_rows if row["passes_observed_infeasible_filter"]
        ][:50],
        "c5_phase_geometry": c5_phases,
        "c5_phase_conclusion": (
            "Moving c5 poles to x=67 or x=68 never expands the 328-cell component in the audited phases. It "
            "rearranges candidate domains; x=67 keeps every body-legal pose powered, while x=68 loses some "
            "3x3 powered poses. These are capacity observations, not packing results."
        ),
        "c5_baseline_target_10_4_4_query_status_dy0": baseline_c5_status,
        "c10_c11_neighbour_pole_audits": neighbour_audits,
        "neighbour_pole_conclusion": (
            "The c10 two-pole shift is collision-free, preserves 212 component cells and 40 gateways, and expands "
            "all three candidate domains; target (9,2,2) has 33 residual cells but is unqueried there. The requested "
            "c11 two-pole shift is invalid because the pole at (6,41) occupies protected cells (7,41) and (7,42)."
        ),
        "clean_plan": {
            "counts": {str(component): list(target) for component, target in clean_plan.items()},
            "subtotal": list(sum_triples(clean_plan.values())),
            "integer_closes_global_target": True,
            "required_new_or_reopened_local_results": {
                "c5_x64_target_10_4_4": baseline_c5_status["64"],
                "c10_shifted_target_9_2_2": "UNQUERIED_STATIC_AREA_AND_DOMAIN_FIT",
                "c11_requested_shift_target_9_1_2": "STATICALLY_INVALID_FIXED_COLLISION",
            },
            "usable": False,
            "reason": "The requested c11 pole geometry is invalid before any local packing query.",
        },
        "output_files": [str(CATALOG_OUTPUT.relative_to(ROOT)), str(PAIR_OUTPUT.relative_to(ROOT))],
    }
    write_exclusive(REPORT_OUTPUT, report)
    print(json.dumps({"status": report["status"], "report": str(REPORT_OUTPUT)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
