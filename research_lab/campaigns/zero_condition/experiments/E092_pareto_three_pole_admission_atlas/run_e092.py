#!/usr/bin/env python3
"""E092: exact three-pole body/power admission sweep over E081's Pareto beam."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001"
)
POWER_SOURCE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E084_integrated_power_setpacking_probe.py"
)
CALIBRATION_HINT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E084_integrated_power_setpacking_total.json"
)
E091_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E091_next_pareto_three_pole_control/run-001/RESULT.json"
)
E091_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E091_next_pareto_three_pole_control/RESULT.txt"
)
E081_FRONTIER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E081_axis_seam_recolor_frontier/run-001/AXIS_SEAM_FRONTIER.json"
)
E069_PARENT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
E079_MACRO = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E079_k47_boundary_macro/run-001/BOUNDARY_MACRO_V1.json"
)
CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"
STRICT = (
    ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/"
    "problem_instance.json"
)

EXPECTED_HASHES = {
    POWER_SOURCE: "5ce50e3a450006461b023ddea4373cf21011eb746c927ca602cb5dc37cae5655",
    CALIBRATION_HINT: "2fd3826610845b80ba19e5e78e0435e56d0685447e678679da3c5845ffbd677e",
    E091_RESULT: "c7e06307c81b72cd12fa3dd7070cd7b9c5586863d0c369651ad4d5ac9b30d3f1",
    E091_DURABLE: "8051ae7a13d84d354f44d07b7d96c56d3d5307df54b9d96d8c5aa7ee0014f564",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
}

CALIBRATION_POSITIVE = "partition_90abd29523f2a0dc"
CALIBRATION_NEGATIVE = "partition_97f9ba7e7ad710dc"
MAX_RELOCATED_POLES = 3


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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
    raw = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"E092 patch {label} matched {count} times")
    return source.replace(old, new, 1)


def process_memory_snapshot() -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "ru_maxrss_kib": int(usage.ru_maxrss),
        "minor_page_faults": int(usage.ru_minflt),
        "major_page_faults": int(usage.ru_majflt),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E092 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E092 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E092 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}
    e091 = load_json(E091_RESULT)
    if e091.get("verdict") != "CONTROL_PARTITION_THREE_POLE_BODY_POWER_INFEASIBLE":
        raise RuntimeError("E092 trigger E091 verdict drift")
    frontier = load_json(E081_FRONTIER)
    pareto = list(map(str, frontier["pareto_partition_ids"]))
    if len(pareto) != 7 or pareto[0] != CALIBRATION_POSITIVE or pareto[1] != CALIBRATION_NEGATIVE:
        raise RuntimeError(f"E092 Pareto identity drift: {pareto}")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "pareto_partition_ids": pareto,
    }


def state_specs() -> list[dict[str, Any]]:
    frontier = load_json(E081_FRONTIER)
    by_id = {
        str(row["partition"]["partition_id"]): row
        for row in frontier["detailed_candidates"]
    }
    output: list[dict[str, Any]] = []
    for rank, partition_id in enumerate(frontier["pareto_partition_ids"]):
        row = by_id[str(partition_id)]
        evaluation = row["best_reference_preserving"]
        corridor = dict(evaluation["corridor"])
        reference_rows = list(evaluation["reference_rewrite_rows"])
        modules = {str(item["target_module"]) for item in reference_rows}
        if len(reference_rows) != 2 or len(modules) != 1:
            raise RuntimeError(f"E092 stable module drift: {partition_id}")
        stable_module = next(iter(modules))
        axis = str(corridor["axis"])
        coordinate = int(corridor["start"])
        if int(corridor["end"]) != coordinate or int(corridor["width"]) != 1:
            raise RuntimeError(f"E092 corridor width drift: {partition_id}")
        if axis not in {"x", "y"}:
            raise RuntimeError(f"E092 corridor axis drift: {partition_id}")
        output.append(
            {
                "rank": rank,
                "partition_id": str(partition_id),
                "axis": axis,
                "coordinate": coordinate,
                "module_low": str(corridor["module_low"]),
                "module_high": str(corridor["module_high"]),
                "stable_module": stable_module,
                "quotient_moved_manufacturing": int(evaluation["moved_manufacturing_count"]),
                "quotient_pole_moves": int(evaluation["pole_move_count"]),
                "seam_commodities": list(row["partition"]["seam"]["commodities"]),
            }
        )
    return output


def derive_source() -> tuple[str, list[dict[str, Any]]]:
    source = POWER_SOURCE.read_text(encoding="utf-8")
    patches: list[dict[str, Any]] = []

    def patch(label: str, old: str, new: str) -> None:
        nonlocal source
        source = replace_once(source, old, new, label)
        patches.append(
            {
                "label": label,
                "old_sha256": sha256_bytes(old.encode("utf-8")),
                "new_sha256": sha256_bytes(new.encode("utf-8")),
            }
        )

    patch(
        "os_import",
        "import hashlib\nimport json\nfrom pathlib import Path",
        "import hashlib\nimport json\nimport os\nfrom pathlib import Path",
    )
    patch(
        "runtime_controls",
        'OUTPUT_ROOT = ROOT / "research_lab/local/zero_condition"',
        '''OUTPUT = Path(os.environ["E092_STATE_OUTPUT"])
SOLVE_SECONDS = float(os.environ.get("E092_STATE_SECONDS", "35"))
TARGET_PARTITION_ID = os.environ["E092_PARTITION_ID"]
CORRIDOR_AXIS = os.environ["E092_CORRIDOR_AXIS"]
CORRIDOR_COORDINATE = int(os.environ["E092_CORRIDOR_COORDINATE"])
MODULE_LOW = os.environ["E092_MODULE_LOW"]
MODULE_HIGH = os.environ["E092_MODULE_HIGH"]
STABLE_MODULE = os.environ["E092_STABLE_MODULE"]
HINT_GEOMETRY_RAW = os.environ.get("E092_HINT_GEOMETRY", "")
HINT_GEOMETRY = Path(HINT_GEOMETRY_RAW) if HINT_GEOMETRY_RAW else None
MAX_RELOCATED_POLES = 3''',
    )
    patch(
        "first_solution_solver",
        "    solver.parameters.random_seed = seed\n    solver.parameters.symmetry_level = 3\n    solver.parameters.cp_model_probing_level = 3\n    started = time.monotonic()",
        "    solver.parameters.random_seed = seed\n    solver.parameters.symmetry_level = 3\n    solver.parameters.cp_model_probing_level = 3\n    solver.parameters.randomize_search = True\n    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH\n    solver.parameters.repair_hint = True\n    solver.parameters.hint_conflict_limit = 2000\n    solver.parameters.stop_after_first_solution = True\n    started = time.monotonic()",
    )
    patch(
        "fixed_main",
        '''    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--objective",
        choices=("manufacturing", "total", "area"),
        default="manufacturing",
    )
    args = parser.parse_args()
    objective_mode = str(args.objective)
    output = OUTPUT_ROOT / f"E084_integrated_power_setpacking_{objective_mode}.json"
''',
        '''    objective_mode = "pure_feasibility"
    output = OUTPUT
''',
    )
    patch(
        "partition_selection",
        '    context = detailed[frontier["geometry_winner_partition_id"]]',
        '    context = detailed[TARGET_PARTITION_ID]',
    )
    patch(
        "corridor_identity",
        '''    if corridor != {
        "axis": "y",
        "start": 41,
        "end": 41,
        "width": 1,
        "module_low": "A",
        "module_high": "B",
        "interior_cell_count": 68,
        "interior_cells_digest": corridor["interior_cells_digest"],
    }:
        raise RuntimeError(f"E084 corridor drift: {corridor}")''',
        '''    if corridor != {
        "axis": CORRIDOR_AXIS,
        "start": CORRIDOR_COORDINATE,
        "end": CORRIDOR_COORDINATE,
        "width": 1,
        "module_low": MODULE_LOW,
        "module_high": MODULE_HIGH,
        "interior_cell_count": 68,
        "interior_cells_digest": corridor["interior_cells_digest"],
    }:
        raise RuntimeError(f"E092 corridor drift: {corridor}")''',
    )
    patch(
        "corridor_cells",
        "    corridor_cells = {(x, 41) for x in range(1, 69)}",
        '''    corridor_cells = (
        {(x, CORRIDOR_COORDINATE) for x in range(1, 69)}
        if CORRIDOR_AXIS == "y"
        else {(CORRIDOR_COORDINATE, y) for y in range(1, 69)}
    )''',
    )
    patch(
        "generic_side_assignment",
        '''                ys = [y for _x, y in body]
                if module == "A" and max(ys) >= 41:
                    continue
                if module == "B" and min(ys) <= 41:
                    continue''',
        '''                coordinate_values = [
                    (y if CORRIDOR_AXIS == "y" else x)
                    for x, y in body
                ]
                if module == MODULE_LOW and max(coordinate_values) >= CORRIDOR_COORDINATE:
                    continue
                if module == MODULE_HIGH and min(coordinate_values) <= CORRIDOR_COORDINATE:
                    continue''',
    )
    patch(
        "pole_budget",
        "    model.Add(sum(pole_vars) == EXPECTED_POLE_COUNT)\n\n    for variables, rows in ((body_vars, body_rows), (pole_vars, pole_rows)):",
        '''    model.Add(sum(pole_vars) == EXPECTED_POLE_COUNT)
    current_pole_vars = [
        pole_vars[index]
        for index, row in enumerate(pole_rows)
        if row["is_current"]
    ]
    model.Add(
        sum(current_pole_vars)
        >= EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES
    )

    for variables, rows in ((body_vars, body_rows), (pole_vars, pole_rows)):''',
    )
    patch(
        "stable_module",
        '            if row["module"] == "B"\n            and row["template"] == "manufacturing_6x4"',
        '            if row["module"] == STABLE_MODULE\n            and row["template"] == "manufacturing_6x4"',
    )

    marker = "    retained_body_terms = ["
    prefix, separator, old_tail = source.partition(marker)
    if not separator:
        raise RuntimeError("E092 tail marker missing")
    new_tail = r'''    retained_body_terms = [
        body_vars[index] for index, row in enumerate(body_rows) if row["is_current"]
    ]
    retained_pole_terms = [
        pole_vars[index] for index, row in enumerate(pole_rows) if row["is_current"]
    ]
    hint_kind = "CURRENT_GEOMETRY"
    if HINT_GEOMETRY is not None:
        hint = load(HINT_GEOMETRY)
        hint_bodies = {
            tuple(sorted(cell(value) for value in row["body"]))
            for row in hint["selected_manufacturing"]
        }
        hint_poles = {int(row["pose_index"]) for row in hint["selected_poles"]}
        hint_boundary = int(hint["selected_boundary_state_index"])
        hint_kind = "EXACT_CALIBRATION_WITNESS"
        matched_bodies = 0
        for index, row in enumerate(body_rows):
            selected = row["body"] in hint_bodies
            model.AddHint(body_vars[index], int(selected))
            matched_bodies += int(selected)
        if matched_bodies != EXPECTED_MANUFACTURING_COUNT:
            raise RuntimeError(f"E092 calibration body remap drift: {matched_bodies}")
        matched_poles = 0
        for index, row in enumerate(pole_rows):
            selected = int(row["pose_index"]) in hint_poles
            model.AddHint(pole_vars[index], int(selected))
            matched_poles += int(selected)
        if matched_poles != EXPECTED_POLE_COUNT:
            raise RuntimeError(f"E092 calibration pole remap drift: {matched_poles}")
        for index, variable in enumerate(boundary_vars):
            model.AddHint(variable, int(index == hint_boundary))
    else:
        for index, row in enumerate(body_rows):
            model.AddHint(body_vars[index], int(bool(row["is_current"])))
        for index, row in enumerate(pole_rows):
            model.AddHint(pole_vars[index], int(bool(row["is_current"])))
        current_boundary_pose_set = {
            int(row["pose_idx"])
            for row in parent.values()
            if str(row["facility_type"]) == "boundary_storage_port"
        }
        state_pose_sets = [set(map(int, state["pose_indices"])) for state in macro["states"]]
        matches = [
            index for index, pose_set in enumerate(state_pose_sets)
            if pose_set == current_boundary_pose_set
        ]
        if len(matches) == 1:
            for index, variable in enumerate(boundary_vars):
                model.AddHint(variable, int(index == matches[0]))

    validation_error = model.Validate()
    if validation_error:
        raise RuntimeError(f"E092 model invalid: {validation_error}")
    seed = 92000 + int(os.environ.get("E092_STATE_RANK", "0"))
    solver, status, elapsed = solve(model, seed=seed, seconds=SOLVE_SECONDS)
    solver_status = solver.StatusName(status)
    result: dict[str, Any] = {
        "schema": "zmd_e092_pareto_state_admission_v1",
        "status": solver_status,
        "solver_status": solver_status,
        "elapsed_seconds": elapsed,
        "partition_id": TARGET_PARTITION_ID,
        "corridor_axis": CORRIDOR_AXIS,
        "corridor_coordinate": CORRIDOR_COORDINATE,
        "module_low": MODULE_LOW,
        "module_high": MODULE_HIGH,
        "stable_module": STABLE_MODULE,
        "max_relocated_poles": MAX_RELOCATED_POLES,
        "minimum_retained_current_poles": EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES,
        "hint_kind": hint_kind,
        "body_candidate_count": len(body_rows),
        "pole_candidate_count": len(pole_rows),
        "body_domain_counts": body_domains,
        "unpowerable_body_candidate_count": disabled_unpowerable,
        "stable_reference_candidate_indices": stable_indices,
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
    }
    if status == cp_model.INFEASIBLE:
        result["status"] = "MASTER_INFEASIBLE"
    elif status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected_bodies = [
            row | {"candidate_index": index}
            for index, row in enumerate(body_rows)
            if solver.Value(body_vars[index])
        ]
        selected_poles = [
            row | {"candidate_index": index}
            for index, row in enumerate(pole_rows)
            if solver.Value(pole_vars[index])
        ]
        if len(selected_bodies) != EXPECTED_MANUFACTURING_COUNT:
            raise RuntimeError("E092 witness lacks 219 bodies")
        if len(selected_poles) != EXPECTED_POLE_COUNT:
            raise RuntimeError("E092 witness lacks 53 poles")
        state_index = next(
            index for index, variable in enumerate(boundary_vars)
            if solver.Value(variable)
        )
        selected_pole_pose_indices = {
            int(row["pose_index"]) for row in selected_poles
        }
        retained_poles = len(selected_pole_pose_indices & current_poles)
        relocated_poles = EXPECTED_POLE_COUNT - retained_poles
        if relocated_poles > MAX_RELOCATED_POLES:
            raise RuntimeError("E092 witness exceeds pole budget")
        retained_bodies = sum(bool(row["is_current"]) for row in selected_bodies)
        result.update(
            {
                "status": "BODY_POWER_FEASIBLE",
                "retained_manufacturing_count": retained_bodies,
                "moved_manufacturing_count": EXPECTED_MANUFACTURING_COUNT - retained_bodies,
                "retained_current_pole_count": retained_poles,
                "relocated_pole_count": relocated_poles,
                "selected_boundary_state_index": state_index,
                "selected_boundary_state_id": str(macro["states"][state_index]["state_id"]),
                "selected_manufacturing": [
                    {
                        "candidate_index": int(row["candidate_index"]),
                        "module": str(row["module"]),
                        "template": str(row["template"]),
                        "body": [list(value) for value in row["body"]],
                        "body_digest": str(row["body_digest"]),
                        "representative_pose_index": int(row["representative_pose_index"]),
                        "is_current": bool(row["is_current"]),
                        "current_owner": row["current_owner"],
                    }
                    for row in selected_bodies
                ],
                "selected_poles": [
                    {
                        "candidate_index": int(row["candidate_index"]),
                        "pose_index": int(row["pose_index"]),
                        "pose_id": str(row["pose_id"]),
                        "anchor": dict(row["anchor"]),
                        "body": [list(value) for value in row["body"]],
                        "is_current": bool(row["is_current"]),
                    }
                    for row in selected_poles
                ],
            }
        )
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"partition_id": TARGET_PARTITION_ID, "status": result["status"], "elapsed_seconds": elapsed}, sort_keys=True))
    return 0
'''
    source = prefix + new_tail + '\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'
    patches.append(
        {
            "label": "pure_feasibility_tail",
            "old_sha256": sha256_bytes(old_tail.encode("utf-8")),
            "new_sha256": sha256_bytes(new_tail.encode("utf-8")),
        }
    )
    return source, patches


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import E092 derived producer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(*, run_dir: Path, seconds_per_state: float) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E092 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    derived_path = run_dir / "DERIVED_PRODUCER.py"
    derivation_path = run_dir / "DERIVATION.json"
    atlas_path = run_dir / "ADMISSION_ATLAS.json"

    source, patches = derive_source()
    with derived_path.open("xb") as handle:
        handle.write(source.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    specs = state_specs()
    dump_exclusive(
        derivation_path,
        {
            "schema": "zmd_e092_sweep_derivation_v1",
            "source_path": display(POWER_SOURCE),
            "source_sha256": EXPECTED_HASHES[POWER_SOURCE],
            "derived_path": display(derived_path),
            "derived_sha256": sha256_file(derived_path),
            "patches": patches,
            "common_semantics": {
                "exact_manufacturing_count": 219,
                "exact_pole_count": 53,
                "maximum_relocated_poles": MAX_RELOCATED_POLES,
                "complete_boundary_disjunction": True,
                "power_and_nonoverlap": True,
                "pure_feasibility": True,
                "stop_after_first_solution": True,
            },
            "states": specs,
        },
    )

    records: list[dict[str, Any]] = []
    sweep_started = time.monotonic()
    process_before = process_memory_snapshot()
    for spec in specs:
        state_dir = run_dir / f"state-{spec['rank']:02d}-{spec['partition_id']}"
        state_dir.mkdir(parents=False, exist_ok=False)
        output = state_dir / "RESULT.json"
        hint = CALIBRATION_HINT if spec["partition_id"] == CALIBRATION_POSITIVE else None
        env_values = {
            "E092_STATE_OUTPUT": str(output),
            "E092_STATE_SECONDS": str(float(seconds_per_state)),
            "E092_STATE_RANK": str(spec["rank"]),
            "E092_PARTITION_ID": spec["partition_id"],
            "E092_CORRIDOR_AXIS": spec["axis"],
            "E092_CORRIDOR_COORDINATE": str(spec["coordinate"]),
            "E092_MODULE_LOW": spec["module_low"],
            "E092_MODULE_HIGH": spec["module_high"],
            "E092_STABLE_MODULE": spec["stable_module"],
            "E092_HINT_GEOMETRY": "" if hint is None else str(hint),
        }
        prior = {key: os.environ.get(key) for key in env_values}
        os.environ.update(env_values)
        state_started = time.monotonic()
        try:
            module = import_module(
                derived_path,
                f"zmd_e092_state_{spec['rank']:02d}",
            )
            exit_code = int(module.main())
        finally:
            for key, value in prior.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        wrapper_elapsed = time.monotonic() - state_started
        if exit_code != 0 or not output.is_file():
            raise RuntimeError(f"E092 state did not publish: {spec['partition_id']}")
        result = load_json(output)
        for key in (
            "partition_id",
            "corridor_axis",
            "corridor_coordinate",
            "module_low",
            "module_high",
            "stable_module",
        ):
            expected = spec[
                {
                    "corridor_axis": "axis",
                    "corridor_coordinate": "coordinate",
                }.get(key, key)
            ]
            if result.get(key) != expected:
                raise RuntimeError(f"E092 state identity drift {spec['partition_id']}:{key}")
        records.append(
            {
                **spec,
                "status": str(result.get("status", "MISSING")),
                "solver_status": str(result.get("solver_status", "MISSING")),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "wrapper_elapsed_seconds": wrapper_elapsed,
                "branches": result.get("branches"),
                "conflicts": result.get("conflicts"),
                "body_candidate_count": result.get("body_candidate_count"),
                "pole_candidate_count": result.get("pole_candidate_count"),
                "hint_kind": result.get("hint_kind"),
                "retained_manufacturing_count": result.get("retained_manufacturing_count"),
                "moved_manufacturing_count": result.get("moved_manufacturing_count"),
                "retained_current_pole_count": result.get("retained_current_pole_count"),
                "relocated_pole_count": result.get("relocated_pole_count"),
                "selected_boundary_state_id": result.get("selected_boundary_state_id"),
                "selected_manufacturing_count": len(result.get("selected_manufacturing", [])),
                "selected_pole_count": len(result.get("selected_poles", [])),
                "result_path": display(output),
                "result_sha256": sha256_file(output),
            }
        )

    process_after = process_memory_snapshot()
    by_id = {row["partition_id"]: row for row in records}
    calibration = {
        "positive_status": by_id[CALIBRATION_POSITIVE]["status"],
        "negative_status": by_id[CALIBRATION_NEGATIVE]["status"],
        "pass": (
            by_id[CALIBRATION_POSITIVE]["status"] == "BODY_POWER_FEASIBLE"
            and by_id[CALIBRATION_NEGATIVE]["status"] == "MASTER_INFEASIBLE"
        ),
    }
    admitted = [row["partition_id"] for row in records if row["status"] == "BODY_POWER_FEASIBLE"]
    infeasible = [row["partition_id"] for row in records if row["status"] == "MASTER_INFEASIBLE"]
    unknown = [row["partition_id"] for row in records if row["status"] not in {"BODY_POWER_FEASIBLE", "MASTER_INFEASIBLE"}]
    additional = [value for value in admitted if value != CALIBRATION_POSITIVE]
    if not calibration["pass"]:
        verdict = "PARETO_ADMISSION_SWEEP_CALIBRATION_FAILED"
        decision = "REPAIR_ADMISSION_INSTRUMENT_WITHOUT_INTERPRETING_BEAM"
    elif additional:
        verdict = "ADDITIONAL_THREE_POLE_PARETO_SKELETONS_ADMITTED"
        decision = "RUN_COMPLETE_FRONT_CONSUMER_ON_EARLIEST_ADDITIONAL_SURVIVOR"
    elif unknown:
        verdict = "Y41_ONLY_OBSERVED_SURVIVOR_WITH_CENSORED_ADMISSION_STATES"
        decision = "RESOLVE_UNKNOWN_ADMISSION_STATES_BEFORE_SELECTING_CARRIER"
    else:
        verdict = "Y41_IS_SOLE_THREE_POLE_BODY_POWER_PARETO_SURVIVOR"
        decision = "CHOOSE_WIDER_POLE_BUDGET_OR_DECOMPOSE_Y41_FRONT_CONSUMER"

    atlas = {
        "schema": "zmd_e092_pareto_three_pole_admission_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "calibration": calibration,
        "admitted_partition_ids": admitted,
        "additional_admitted_partition_ids": additional,
        "infeasible_partition_ids": infeasible,
        "unknown_partition_ids": unknown,
        "records": records,
        "truth_boundary": "Exact body/pole/power admission statuses only; no native-front or downstream claim.",
    }
    dump_exclusive(atlas_path, atlas)
    return {
        "schema": "zmd_e092_pareto_three_pole_admission_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "state_count": len(specs),
            "seconds_per_state": float(seconds_per_state),
            "maximum_relocated_poles": MAX_RELOCATED_POLES,
            "minimum_retained_current_poles": 53 - MAX_RELOCATED_POLES,
            "calibration_positive_partition": CALIBRATION_POSITIVE,
            "calibration_negative_partition": CALIBRATION_NEGATIVE,
        },
        "calibration": calibration,
        "admitted_partition_ids": admitted,
        "additional_admitted_partition_ids": additional,
        "infeasible_partition_ids": infeasible,
        "unknown_partition_ids": unknown,
        "records": records,
        "atlas_path": display(atlas_path),
        "atlas_sha256": sha256_file(atlas_path),
        "derivation_path": display(derivation_path),
        "derivation_sha256": sha256_file(derivation_path),
        "derived_source_path": display(derived_path),
        "derived_source_sha256": sha256_file(derived_path),
        "telemetry": {
            "wrapper_elapsed_seconds": time.monotonic() - sweep_started,
            "process_before": process_before,
            "process_after": process_after,
        },
        "truth_boundary": (
            "Complete finite body/pole/power admission sweep over the E081 Pareto "
            "beam at the three-pole budget. FEASIBLE does not imply native-front or "
            "downstream feasibility; UNKNOWN is censored."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--seconds-per-state", type=float, default=35.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    result_path = run_dir / "RESULT.json"
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir=run_dir, seconds_per_state=float(args.seconds_per_state))
        dump_exclusive(result_path, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "calibration": result["calibration"],
                    "admitted_partition_ids": result["admitted_partition_ids"],
                    "infeasible_partition_ids": result["infeasible_partition_ids"],
                    "unknown_partition_ids": result["unknown_partition_ids"],
                    "elapsed_seconds": result["telemetry"]["wrapper_elapsed_seconds"],
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except FileExistsError as exc:
        print(json.dumps({"status": "NO_OVERWRITE_REJECTION", "detail": str(exc)}, sort_keys=True))
        return 2
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e092_pareto_three_pole_admission_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
