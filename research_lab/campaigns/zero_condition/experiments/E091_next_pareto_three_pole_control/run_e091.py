#!/usr/bin/env python3
"""E091: run the E090 three-pole front consumer on the next E081 Pareto partition."""

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
    "E091_next_pareto_three_pole_control/run-001"
)

POWER_SOURCE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E084_integrated_power_setpacking_probe.py"
)
FRONT_SOURCE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E090_three_pole_front_discriminator/run-001/DERIVED_PRODUCER.py"
)
E090_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E090_three_pole_front_discriminator/run-001/RESULT.json"
)
E090_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E090_three_pole_front_discriminator/RESULT.txt"
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
MANDATORY = HISTORY / "data/preprocessed/mandatory_exact_instances.json"
STRICT = (
    ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/"
    "problem_instance.json"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"

TARGET_PARTITION_ID = "partition_97f9ba7e7ad710dc"
CORRIDOR_Y = 17
MODULE_LOW = "B"
MODULE_HIGH = "A"
STABLE_MODULE = "A"
MAX_RELOCATED_POLES = 3

EXPECTED_HASHES = {
    POWER_SOURCE: "5ce50e3a450006461b023ddea4373cf21011eb746c927ca602cb5dc37cae5655",
    FRONT_SOURCE: "93471f93743d15dc2835c7e1c5a0637a219942e2aab6c4e77c4dcf4828cde0fb",
    E090_RESULT: "ff5398ee4064f01ded8d4b91d2ddc832fe52dceb4197c63dcad081bf52d89496",
    E090_DURABLE: "594962f614fffc0d3cb98f6168fd24a3e256a45ae22ce8591e561c0612c309eb",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    MANDATORY: "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}


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
    encoded = (
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
        handle.write(encoded)
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
        raise RuntimeError(f"E091 patch {label} matched {count} times")
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


def _read_scalar(path: Path) -> int | str | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if raw.isdigit():
        return int(raw)
    return raw


def _read_events(path: Path) -> dict[str, int] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    result: dict[str, int] = {}
    for line in lines:
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            result[str(fields[0])] = int(fields[1])
        except ValueError:
            continue
    return result


def cgroup_snapshot() -> dict[str, Any]:
    relative: str | None = None
    try:
        for line in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
            fields = line.split(":", 2)
            if len(fields) == 3 and fields[0] == "0":
                relative = fields[2]
                break
    except OSError:
        pass
    if relative is None:
        return {"available": False}
    directory = Path("/sys/fs/cgroup") / relative.lstrip("/")
    return {
        "available": directory.is_dir(),
        "relative_path": relative,
        "memory_current_bytes": _read_scalar(directory / "memory.current"),
        "memory_peak_bytes": _read_scalar(directory / "memory.peak"),
        "memory_max": _read_scalar(directory / "memory.max"),
        "memory_swap_current_bytes": _read_scalar(directory / "memory.swap.current"),
        "memory_swap_peak_bytes": _read_scalar(directory / "memory.swap.peak"),
        "memory_events": _read_events(directory / "memory.events"),
    }


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E091 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked_status}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E091 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(
                f"E091 input identity drift: {path}: {observed} != {expected}"
            )
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e090 = load_json(E090_RESULT)
    if e090.get("verdict") != "THREE_POLE_FRONT_DISCRIMINATOR_CENSORED":
        raise RuntimeError("E091 trigger E090 verdict drift")
    if e090.get("decision") != (
        "MOVE_IDENTICAL_THREE_POLE_CONSUMER_TO_NEXT_E081_PARETO_PARTITION_AS_CONTROL"
    ):
        raise RuntimeError("E091 trigger E090 decision drift")

    frontier = load_json(E081_FRONTIER)
    pareto = list(map(str, frontier["pareto_partition_ids"]))
    if len(pareto) < 2 or pareto[1] != TARGET_PARTITION_ID:
        raise RuntimeError(f"E091 Pareto control identity drift: {pareto[:3]}")
    candidates = [
        row
        for row in frontier["detailed_candidates"]
        if row["partition"]["partition_id"] == TARGET_PARTITION_ID
    ]
    if len(candidates) != 1:
        raise RuntimeError("E091 target partition multiplicity drift")
    corridor = candidates[0]["best_reference_preserving"]["corridor"]
    if corridor != {
        "axis": "y",
        "start": CORRIDOR_Y,
        "end": CORRIDOR_Y,
        "width": 1,
        "module_low": MODULE_LOW,
        "module_high": MODULE_HIGH,
        "interior_cell_count": 68,
        "interior_cells_digest": corridor["interior_cells_digest"],
    }:
        raise RuntimeError(f"E091 corridor identity drift: {corridor}")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "target_partition_id": TARGET_PARTITION_ID,
        "pareto_rank_zero_based": 1,
        "corridor": json_safe(corridor),
    }


def derive_power_source() -> tuple[str, list[dict[str, Any]]]:
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
        "power_os_import",
        "import hashlib\nimport json\nfrom pathlib import Path",
        "import hashlib\nimport json\nimport os\nfrom pathlib import Path",
    )
    patch(
        "power_runtime_controls",
        'OUTPUT_ROOT = ROOT / "research_lab/local/zero_condition"',
        'OUTPUT = Path(os.environ["E091_POWER_OUTPUT"])\nPOWER_SECONDS = float(os.environ.get("E091_POWER_SECONDS", "55"))\nTARGET_PARTITION_ID = "partition_97f9ba7e7ad710dc"\nCORRIDOR_Y = 17\nMAX_RELOCATED_POLES = 3',
    )
    patch(
        "power_first_solution_solver",
        "    solver.parameters.random_seed = seed\n    solver.parameters.symmetry_level = 3\n    solver.parameters.cp_model_probing_level = 3\n    started = time.monotonic()",
        "    solver.parameters.random_seed = seed\n    solver.parameters.symmetry_level = 3\n    solver.parameters.cp_model_probing_level = 3\n    solver.parameters.randomize_search = True\n    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH\n    solver.parameters.repair_hint = True\n    solver.parameters.hint_conflict_limit = 2000\n    solver.parameters.stop_after_first_solution = True\n    started = time.monotonic()",
    )
    patch(
        "power_fixed_main",
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
        "power_partition_selection",
        '    context = detailed[frontier["geometry_winner_partition_id"]]',
        '    context = detailed[TARGET_PARTITION_ID]',
    )
    patch(
        "power_corridor_identity",
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
        "axis": "y",
        "start": CORRIDOR_Y,
        "end": CORRIDOR_Y,
        "width": 1,
        "module_low": "B",
        "module_high": "A",
        "interior_cell_count": 68,
        "interior_cells_digest": corridor["interior_cells_digest"],
    }:
        raise RuntimeError(f"E091 power corridor drift: {corridor}")''',
    )
    patch(
        "power_corridor_cells",
        "    corridor_cells = {(x, 41) for x in range(1, 69)}",
        "    corridor_cells = {(x, CORRIDOR_Y) for x in range(1, 69)}",
    )
    patch(
        "power_side_assignment",
        '''                if module == "A" and max(ys) >= 41:
                    continue
                if module == "B" and min(ys) <= 41:
                    continue''',
        '''                if module == "B" and max(ys) >= CORRIDOR_Y:
                    continue
                if module == "A" and min(ys) <= CORRIDOR_Y:
                    continue''',
    )
    patch(
        "power_pole_budget",
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
        "power_stable_module",
        '            if row["module"] == "B"\n            and row["template"] == "manufacturing_6x4"',
        '            if row["module"] == "A"\n            and row["template"] == "manufacturing_6x4"',
    )

    marker = "    retained_body_terms = ["
    prefix, separator, old_tail = source.partition(marker)
    if not separator:
        raise RuntimeError("E091 power tail marker missing")
    new_tail = r'''    retained_body_terms = [
        body_vars[index] for index, row in enumerate(body_rows) if row["is_current"]
    ]
    retained_pole_terms = [
        pole_vars[index] for index, row in enumerate(pole_rows) if row["is_current"]
    ]
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
    current_state_matches = [
        index
        for index, pose_set in enumerate(state_pose_sets)
        if pose_set == current_boundary_pose_set
    ]
    if len(current_state_matches) == 1:
        for index, variable in enumerate(boundary_vars):
            model.AddHint(variable, int(index == current_state_matches[0]))

    validation_error = model.Validate()
    if validation_error:
        raise RuntimeError(f"E091 power model invalid: {validation_error}")
    solver, status, elapsed = solve(model, seed=91001, seconds=POWER_SECONDS)
    solver_status = solver.StatusName(status)
    result: dict[str, Any] = {
        "schema": "zmd_e091_control_body_power_seed_v1",
        "status": solver_status,
        "solver_status": solver_status,
        "elapsed_seconds": elapsed,
        "partition_id": TARGET_PARTITION_ID,
        "corridor_y": CORRIDOR_Y,
        "max_relocated_poles": MAX_RELOCATED_POLES,
        "minimum_retained_current_poles": EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES,
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
            raise RuntimeError("E091 power witness lacks 219 bodies")
        if len(selected_poles) != EXPECTED_POLE_COUNT:
            raise RuntimeError("E091 power witness lacks 53 poles")
        state_index = next(
            index
            for index, variable in enumerate(boundary_vars)
            if solver.Value(variable)
        )
        selected_pole_pose_indices = {
            int(row["pose_index"]) for row in selected_poles
        }
        retained_poles = len(selected_pole_pose_indices & current_poles)
        relocated_poles = EXPECTED_POLE_COUNT - retained_poles
        if relocated_poles > MAX_RELOCATED_POLES:
            raise RuntimeError("E091 power witness exceeds pole budget")
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
    print(
        json.dumps(
            {
                "status": result["status"],
                "solver_status": solver_status,
                "elapsed_seconds": elapsed,
                "retained_manufacturing_count": result.get("retained_manufacturing_count"),
                "relocated_pole_count": result.get("relocated_pole_count"),
                "selected_boundary_state_id": result.get("selected_boundary_state_id"),
                "output_path": str(output.relative_to(ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0
'''
    source = prefix + new_tail + '\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'
    patches.append(
        {
            "label": "power_pure_feasibility_tail",
            "old_sha256": sha256_bytes(old_tail.encode("utf-8")),
            "new_sha256": sha256_bytes(new_tail.encode("utf-8")),
        }
    )
    return source, patches


def derive_front_source() -> tuple[str, list[dict[str, Any]]]:
    source = FRONT_SOURCE.read_text(encoding="utf-8")
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
        "front_runtime_controls",
        '''OUTPUT = Path(os.environ["E090_PRODUCER_OUTPUT"])
HINT_GEOMETRY = Path(os.environ["E090_HINT_GEOMETRY"])
MAX_RELOCATED_POLES = int(os.environ.get("E090_MAX_RELOCATED_POLES", "3"))
SOLVE_SECONDS = float(os.environ.get("E090_SOLVE_SECONDS", "240"))''',
        '''OUTPUT = Path(os.environ["E091_FRONT_OUTPUT"])
HINT_GEOMETRY = Path(os.environ["E091_FRONT_HINT"])
MAX_RELOCATED_POLES = int(os.environ.get("E091_MAX_RELOCATED_POLES", "3"))
SOLVE_SECONDS = float(os.environ.get("E091_FRONT_SECONDS", "210"))
TARGET_PARTITION_ID = "partition_97f9ba7e7ad710dc"
CORRIDOR_Y = 17''',
    )
    patch(
        "front_partition_selection",
        '    context = detailed[frontier["geometry_winner_partition_id"]]',
        '    context = detailed[TARGET_PARTITION_ID]',
    )
    patch(
        "front_corridor_identity",
        '    if str(corridor["axis"]) != "y" or int(corridor["start"]) != 41 or int(corridor["width"]) != 1:\n        raise RuntimeError(f"corridor drift: {corridor}")',
        '    if (str(corridor["axis"]) != "y" or int(corridor["start"]) != CORRIDOR_Y or int(corridor["width"]) != 1 or corridor["module_low"] != "B" or corridor["module_high"] != "A"):\n        raise RuntimeError(f"E091 front corridor drift: {corridor}")',
    )
    patch(
        "front_corridor_cells",
        "    fixed_cells |= {(x, 41) for x in range(1, 69)}",
        "    fixed_cells |= {(x, CORRIDOR_Y) for x in range(1, 69)}",
    )
    patch(
        "front_side_assignment",
        '''                if module == "A" and max(ys) >= 41:
                    continue
                if module == "B" and min(ys) <= 41:
                    continue''',
        '''                if module == "B" and max(ys) >= CORRIDOR_Y:
                    continue
                if module == "A" and min(ys) <= CORRIDOR_Y:
                    continue''',
    )
    patch(
        "front_stable_module",
        '            if row["module"] == "B"\n            and row["template"] == "manufacturing_6x4"',
        '            if row["module"] == "A"\n            and row["template"] == "manufacturing_6x4"',
    )
    patch(
        "front_stable_class_module",
        '''            expected_class = (
                "B",
                str(profile.facility_type),''',
        '''            expected_class = (
                "A",
                str(profile.facility_type),''',
    )
    source = source.replace("E090", "E091").replace("e090", "e091")
    patches.append(
        {
            "label": "front_schema_and_diagnostic_namespace",
            "old_sha256": sha256_bytes(FRONT_SOURCE.read_bytes()),
            "new_sha256": sha256_bytes(source.encode("utf-8")),
        }
    )
    return source, patches


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import derived E091 module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def classify(
    power: dict[str, Any],
    front: dict[str, Any] | None,
) -> tuple[str, str]:
    power_status = str(power.get("status", "MISSING"))
    if power_status == "MASTER_INFEASIBLE":
        return (
            "CONTROL_PARTITION_THREE_POLE_BODY_POWER_INFEASIBLE",
            "REASSESS_REMAINING_PARETO_BEAM_OR_POLE_BUDGET",
        )
    if power_status != "BODY_POWER_FEASIBLE":
        return (
            "CONTROL_PARTITION_BODY_POWER_SEED_CENSORED",
            "DO_NOT_COMPARE_FRONT_PARTITIONS_CHANGE_BODY_POWER_INSTRUMENT",
        )
    if front is None:
        raise RuntimeError("E091 front result absent after positive power seed")
    front_status = str(front.get("status", "MISSING"))
    if front_status == "FRONT_OPERATION_FEASIBLE":
        return (
            "CONTROL_PARTITION_FRONT_OPERATION_WITNESS_FOUND",
            "RETIRE_Y41_CARRIER_RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
        )
    if front_status == "MASTER_INFEASIBLE":
        return (
            "CONTROL_PARTITION_THREE_POLE_FRONT_INFEASIBLE",
            "REASSESS_REMAINING_PARETO_BEAM_OR_POLE_BUDGET",
        )
    return (
        "CONTROL_PARTITION_FRONT_DISCRIMINATOR_CENSORED",
        "DECOMPOSE_MONOLITHIC_FRONT_CONSUMER_BEFORE_MORE_PARTITION_VOTES",
    )


def run(
    *,
    run_dir: Path,
    power_seconds: float,
    front_seconds: float,
) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E091 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    power_derived_path = run_dir / "POWER_DERIVED.py"
    power_derivation_path = run_dir / "POWER_DERIVATION.json"
    power_result_path = run_dir / "POWER_RESULT.json"
    front_derived_path = run_dir / "FRONT_DERIVED.py"
    front_derivation_path = run_dir / "FRONT_DERIVATION.json"
    front_result_path = run_dir / "FRONT_RESULT.json"

    power_source, power_patches = derive_power_source()
    with power_derived_path.open("xb") as handle:
        handle.write(power_source.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    dump_exclusive(
        power_derivation_path,
        {
            "schema": "zmd_e091_power_derivation_v1",
            "source_path": display(POWER_SOURCE),
            "source_sha256": EXPECTED_HASHES[POWER_SOURCE],
            "derived_path": display(power_derived_path),
            "derived_sha256": sha256_file(power_derived_path),
            "patches": power_patches,
            "semantic_changes": {
                "partition_id": TARGET_PARTITION_ID,
                "corridor_y": CORRIDOR_Y,
                "module_low": MODULE_LOW,
                "module_high": MODULE_HIGH,
                "stable_module": STABLE_MODULE,
                "exact_pole_count": 53,
                "maximum_relocated_poles": MAX_RELOCATED_POLES,
                "pure_feasibility": True,
                "complete_boundary_disjunction": True,
                "same_power_and_nonoverlap_semantics": True,
            },
        },
    )

    prior_power_output = os.environ.get("E091_POWER_OUTPUT")
    prior_power_seconds = os.environ.get("E091_POWER_SECONDS")
    os.environ["E091_POWER_OUTPUT"] = str(power_result_path)
    os.environ["E091_POWER_SECONDS"] = str(float(power_seconds))
    power_before = process_memory_snapshot()
    power_cgroup_before = cgroup_snapshot()
    power_started = time.monotonic()
    try:
        power_module = import_module(
            power_derived_path,
            "zmd_e091_power_seed",
        )
        power_exit = int(power_module.main())
    finally:
        if prior_power_output is None:
            os.environ.pop("E091_POWER_OUTPUT", None)
        else:
            os.environ["E091_POWER_OUTPUT"] = prior_power_output
        if prior_power_seconds is None:
            os.environ.pop("E091_POWER_SECONDS", None)
        else:
            os.environ["E091_POWER_SECONDS"] = prior_power_seconds
    power_elapsed = time.monotonic() - power_started
    power_after = process_memory_snapshot()
    power_cgroup_after = cgroup_snapshot()
    if power_exit != 0 or not power_result_path.is_file():
        raise RuntimeError("E091 power stage did not publish a result")
    power_result = load_json(power_result_path)

    front_result: dict[str, Any] | None = None
    front_telemetry: dict[str, Any] | None = None
    front_derivation: dict[str, Any] | None = None
    if power_result.get("status") == "BODY_POWER_FEASIBLE":
        front_source, front_patches = derive_front_source()
        with front_derived_path.open("xb") as handle:
            handle.write(front_source.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        front_derivation = {
            "schema": "zmd_e091_front_derivation_v1",
            "source_path": display(FRONT_SOURCE),
            "source_sha256": EXPECTED_HASHES[FRONT_SOURCE],
            "derived_path": display(front_derived_path),
            "derived_sha256": sha256_file(front_derived_path),
            "patches": front_patches,
            "semantic_changes": {
                "partition_id": TARGET_PARTITION_ID,
                "corridor_y": CORRIDOR_Y,
                "module_low": MODULE_LOW,
                "module_high": MODULE_HIGH,
                "stable_module": STABLE_MODULE,
                "same_three_pole_budget_as_e090": True,
                "same_complete_front_class_semantics_as_e090": True,
                "same_pure_feasibility_and_first_incumbent_criterion": True,
                "hint_source": display(power_result_path),
            },
        }
        dump_exclusive(front_derivation_path, front_derivation)

        prior_values = {
            key: os.environ.get(key)
            for key in (
                "E091_FRONT_OUTPUT",
                "E091_FRONT_HINT",
                "E091_MAX_RELOCATED_POLES",
                "E091_FRONT_SECONDS",
            )
        }
        os.environ["E091_FRONT_OUTPUT"] = str(front_result_path)
        os.environ["E091_FRONT_HINT"] = str(power_result_path)
        os.environ["E091_MAX_RELOCATED_POLES"] = str(MAX_RELOCATED_POLES)
        os.environ["E091_FRONT_SECONDS"] = str(float(front_seconds))
        front_before = process_memory_snapshot()
        front_cgroup_before = cgroup_snapshot()
        front_started = time.monotonic()
        try:
            front_module = import_module(
                front_derived_path,
                "zmd_e091_front_control",
            )
            front_exit = int(front_module.main())
        finally:
            for key, value in prior_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        front_elapsed = time.monotonic() - front_started
        front_after = process_memory_snapshot()
        front_cgroup_after = cgroup_snapshot()
        if front_exit != 0 or not front_result_path.is_file():
            raise RuntimeError("E091 front stage did not publish a result")
        front_result = load_json(front_result_path)
        front_telemetry = {
            "wrapper_elapsed_seconds": front_elapsed,
            "process_before": front_before,
            "process_after": front_after,
            "cgroup_before": front_cgroup_before,
            "cgroup_after": front_cgroup_after,
        }

    verdict, decision = classify(power_result, front_result)
    return {
        "schema": "zmd_e091_next_pareto_three_pole_control_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "control": {
            "partition_id": TARGET_PARTITION_ID,
            "corridor_y": CORRIDOR_Y,
            "module_low": MODULE_LOW,
            "module_high": MODULE_HIGH,
            "stable_module": STABLE_MODULE,
            "maximum_relocated_poles": MAX_RELOCATED_POLES,
            "minimum_retained_current_poles": 53 - MAX_RELOCATED_POLES,
        },
        "power_stage": {
            "status": power_result.get("status"),
            "solver_status": power_result.get("solver_status"),
            "result_path": display(power_result_path),
            "result_sha256": sha256_file(power_result_path),
            "derived_source_path": display(power_derived_path),
            "derived_source_sha256": sha256_file(power_derived_path),
            "derivation_path": display(power_derivation_path),
            "derivation_sha256": sha256_file(power_derivation_path),
            "elapsed_seconds": power_result.get("elapsed_seconds"),
            "body_candidate_count": power_result.get("body_candidate_count"),
            "pole_candidate_count": power_result.get("pole_candidate_count"),
            "retained_manufacturing_count": power_result.get(
                "retained_manufacturing_count"
            ),
            "relocated_pole_count": power_result.get("relocated_pole_count"),
            "selected_boundary_state_id": power_result.get(
                "selected_boundary_state_id"
            ),
            "selected_manufacturing_count": len(
                power_result.get("selected_manufacturing", [])
            ),
            "selected_pole_count": len(power_result.get("selected_poles", [])),
            "telemetry": {
                "wrapper_elapsed_seconds": power_elapsed,
                "process_before": power_before,
                "process_after": power_after,
                "cgroup_before": power_cgroup_before,
                "cgroup_after": power_cgroup_after,
            },
        },
        "front_stage": (
            None
            if front_result is None
            else {
                "status": front_result.get("status"),
                "solver_status": front_result.get("solver_status"),
                "result_path": display(front_result_path),
                "result_sha256": sha256_file(front_result_path),
                "derived_source_path": display(front_derived_path),
                "derived_source_sha256": sha256_file(front_derived_path),
                "derivation_path": display(front_derivation_path),
                "derivation_sha256": sha256_file(front_derivation_path),
                "elapsed_seconds": front_result.get("elapsed_seconds"),
                "body_candidate_count": front_result.get("body_candidate_count"),
                "pole_candidate_count": front_result.get("pole_candidate_count"),
                "mode_class_variable_count": front_result.get(
                    "mode_class_variable_count"
                ),
                "model_variable_count": front_result.get("model_variable_count"),
                "model_constraint_count": front_result.get(
                    "model_constraint_count"
                ),
                "retained_manufacturing_count": front_result.get(
                    "retained_manufacturing_count"
                ),
                "relocated_pole_count": front_result.get("relocated_pole_count"),
                "selected_boundary_state_id": front_result.get(
                    "selected_boundary_state_id"
                ),
                "selected_manufacturing_count": len(
                    front_result.get("selected_manufacturing", [])
                ),
                "selected_pole_count": len(front_result.get("selected_poles", [])),
                "telemetry": front_telemetry,
            }
        ),
        "truth_boundary": (
            "Finite E081 Pareto control. Stage A is body/pole/power only. Stage B "
            "uses the E090 complete native-front class semantics and exact named "
            "operation materialization. UNKNOWN remains censored. No terminal "
            "uniqueness, generic I/O, component binding, routing, throughput or "
            "whole-layout conclusion."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--power-seconds", type=float, default=55.0)
    parser.add_argument("--front-seconds", type=float, default=210.0)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    result_path = run_dir / "RESULT.json"
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            power_seconds=float(args.power_seconds),
            front_seconds=float(args.front_seconds),
        )
        dump_exclusive(result_path, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "power_status": result["power_stage"]["status"],
                    "power_elapsed_seconds": result["power_stage"][
                        "elapsed_seconds"
                    ],
                    "front_status": (
                        None
                        if result["front_stage"] is None
                        else result["front_stage"]["status"]
                    ),
                    "front_elapsed_seconds": (
                        None
                        if result["front_stage"] is None
                        else result["front_stage"]["elapsed_seconds"]
                    ),
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except FileExistsError as exc:
        print(
            json.dumps(
                {"status": "NO_OVERWRITE_REJECTION", "detail": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e091_next_pareto_three_pole_control_failure_v1",
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
