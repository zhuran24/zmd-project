#!/usr/bin/env python3
"""Independent CP-SAT replay for E081's winner and E080-selected lower bounds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ortools.sat.python import cp_model

ROOT = Path("/home/zhuran24/zmd-research")
RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/E081_axis_seam_recolor_frontier/run-001"
)
RESULT_PATH = RUN_DIR / "RESULT.json"
OUTPUT_PATH = RUN_DIR / "INDEPENDENT_CHECK.json"
PARENT_PATH = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
CANDIDATE_PATH = Path(
    "/home/zhuran24/zmd-pj/data/preprocessed/candidate_placements.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cell_xy(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def side_of(
    cells: tuple[tuple[int, int], ...],
    *,
    axis: str,
    start: int,
    end: int,
) -> str:
    values = [x if axis == "x" else y for x, y in cells]
    if max(values) < start:
        return "low"
    if min(values) > end:
        return "high"
    return "corridor"


def check_candidate(
    label: str,
    record: Mapping[str, Any],
    bodies: list[dict[str, Any]],
    reference_targets: Mapping[str, str],
) -> dict[str, Any]:
    partition = record["partition"]
    expected = record["best_reference_preserving"]
    corridor = expected["corridor"]
    axis = str(corridor["axis"])
    start = int(corridor["start"])
    end = int(corridor["end"])
    module_side = {
        str(corridor["module_low"]): "low",
        str(corridor["module_high"]): "high",
    }
    operation_module = {
        str(operation): "A" for operation in partition["module_a_operations"]
    } | {
        str(operation): "B" for operation in partition["module_b_operations"]
    }
    requirements = {
        "A": {
            str(key): int(value)
            for key, value in partition["module_a_template_counts"].items()
        },
        "B": {
            str(key): int(value)
            for key, value in partition["module_b_template_counts"].items()
        },
    }

    model = cp_model.CpModel()
    keep: dict[str, Any] = {}
    module_by_id: dict[str, str] = {}
    for body in bodies:
        instance_id = str(body["instance_id"])
        observed_side = side_of(
            body["occupied_cells"],
            axis=axis,
            start=start,
            end=end,
        )
        if observed_side == "corridor":
            continue
        module = next(
            name for name, side in module_side.items() if side == observed_side
        )
        variable = model.NewBoolVar(f"keep_{label}_{instance_id}")
        keep[instance_id] = variable
        module_by_id[instance_id] = module

    for module in ("A", "B"):
        for template, limit in requirements[module].items():
            model.Add(
                cp_model.LinearExpr.Sum(
                    [
                        keep[str(body["instance_id"])]
                        for body in bodies
                        if str(body["instance_id"]) in keep
                        and module_by_id[str(body["instance_id"])] == module
                        and str(body["facility_type"]) == template
                    ]
                )
                <= limit
            )

    for instance_id, target_operation in reference_targets.items():
        expected_module = operation_module[target_operation]
        if instance_id not in keep or module_by_id[instance_id] != expected_module:
            raise RuntimeError(
                f"{label}: reference body cannot be retained on target module: {instance_id}"
            )
        model.Add(keep[instance_id] == 1)

    model.Maximize(cp_model.LinearExpr.Sum(list(keep.values())))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.random_seed = 81081
    status = solver.Solve(model)
    if status != cp_model.OPTIMAL:
        raise RuntimeError(f"{label}: independent replay is {solver.StatusName(status)}")
    retained = int(round(solver.ObjectiveValue()))
    moved = len(bodies) - retained
    expected_moved = int(expected["moved_manufacturing_count"])
    if moved != expected_moved:
        raise RuntimeError(
            f"{label}: moved count mismatch: replay={moved} expected={expected_moved}"
        )
    return {
        "label": label,
        "status": solver.StatusName(status),
        "retained_manufacturing_count": retained,
        "moved_manufacturing_count": moved,
        "expected_moved_manufacturing_count": expected_moved,
        "objective_best_bound": float(solver.BestObjectiveBound()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "corridor": corridor,
        "partition_id": str(partition["partition_id"]),
    }


def main() -> int:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    parent = json.loads(PARENT_PATH.read_text(encoding="utf-8"))["solution"]
    pools = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))["facility_pools"]
    bodies: list[dict[str, Any]] = []
    for instance_id, row in sorted(parent.items()):
        template = str(row["facility_type"])
        if not template.startswith("manufacturing_"):
            continue
        pose = pools[template][int(row["pose_idx"])]
        cells = tuple(sorted(cell_xy(value) for value in pose["occupied_cells"]))
        bodies.append(
            {
                "instance_id": str(instance_id),
                "facility_type": template,
                "occupied_cells": cells,
            }
        )
    if len(bodies) != 219:
        raise RuntimeError(f"independent body count drift: {len(bodies)}")
    reference_targets = {
        str(key): str(value)
        for key, value in result["reference_target_operations"].items()
    }
    checks = [
        check_candidate("geometry_winner", result["geometry_winner"], bodies, reference_targets),
        check_candidate(
            "e080_selected_partition",
            result["e080_selected_partition"],
            bodies,
            reference_targets,
        ),
    ]
    payload = {
        "schema": "zmd_e081_axis_seam_independent_check_v1",
        "status": "PASS",
        "result_path": str(RESULT_PATH.relative_to(ROOT)),
        "result_sha256": sha256_file(RESULT_PATH),
        "candidate_path": str(CANDIDATE_PATH),
        "candidate_sha256": sha256_file(CANDIDATE_PATH),
        "parent_path": str(PARENT_PATH.relative_to(ROOT)),
        "parent_sha256": sha256_file(PARENT_PATH),
        "checks": checks,
        "truth_boundary": (
            "Independent CP-SAT replay of the maximum retained-footprint objective "
            "for two frozen E081 corridors only; no moved-body embedding or full-layout "
            "feasibility is checked."
        ),
    }
    with OUTPUT_PATH.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                "status": "PASS",
                "output_path": str(OUTPUT_PATH.relative_to(ROOT)),
                "output_sha256": sha256_file(OUTPUT_PATH),
                "checks": checks,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
