#!/usr/bin/env python3
"""E090: exact native-front feasibility with at most three pole relocations."""

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
    "E090_three_pole_front_discriminator/run-001"
)

SOURCE_PRODUCER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E084_integrated_front_setpacking_probe.py"
)
HINT_GEOMETRY = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E084_integrated_power_setpacking_total.json"
)
E089_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E089_module_b_spatial_hazard_holdout/run-002/RESULT.json"
)
E089_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E089_module_b_spatial_hazard_holdout/RESULT.txt"
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

EXPECTED_HASHES = {
    SOURCE_PRODUCER: "163edbe631c091dae35f655bee4826576174b05fa94390542ecfb3ccbcec48ad",
    HINT_GEOMETRY: "2fd3826610845b80ba19e5e78e0435e56d0685447e678679da3c5845ffbd677e",
    E089_RESULT: "0a4b17f12a74edd644d53d31c6a445faba04b12544888b5ffcff10bfa077d7ef",
    E089_DURABLE: "c74a92ce57d3f450cdd632158385c552bfde5e5f820273fe17fcee6cfc0ab0bd",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    MANDATORY: "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}

MAX_RELOCATED_POLES = 3
DEFAULT_SOLVE_SECONDS = 240.0


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


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E090 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"tracked research worktree is not clean: {tracked_status}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E090 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(
                f"frozen identity drift: {path}: {observed} != {expected}"
            )
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e089 = load_json(E089_RESULT)
    if e089.get("verdict") != "SPATIAL_ROLES_TOO_DIFFUSE":
        raise RuntimeError("E090 trigger E089 verdict drift")
    if e089.get("decision") != (
        "RETIRE_FIXED_52_PLUS_ONE_B_GEOMETRY_WIDEN_POLES_OR_PARTITION"
    ):
        raise RuntimeError("E090 trigger E089 decision drift")

    hint = load_json(HINT_GEOMETRY)
    if hint.get("primary_status") != "OPTIMAL" or hint.get(
        "secondary_status"
    ) != "OPTIMAL":
        raise RuntimeError("E090 hint geometry is not exact")
    if int(hint.get("relocated_pole_count", -1)) != MAX_RELOCATED_POLES:
        raise RuntimeError("E090 hint pole-move count drift")
    if len(hint.get("selected_manufacturing", [])) != 219:
        raise RuntimeError("E090 hint lacks 219 manufacturing bodies")
    if len(hint.get("selected_poles", [])) != 53:
        raise RuntimeError("E090 hint lacks 53 poles")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "hint_relocated_pole_count": MAX_RELOCATED_POLES,
        "hint_retained_manufacturing_count": int(
            hint["retained_manufacturing_count"]
        ),
    }


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"derived-source patch {label} matched {count} times")
    return source.replace(old, new, 1)


def derive_source() -> tuple[str, list[dict[str, Any]]]:
    source = SOURCE_PRODUCER.read_text(encoding="utf-8")
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
        'OUTPUT = ROOT / "research_lab/local/zero_condition/E084_integrated_front_setpacking_probe_result.json"\nTEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")',
        'OUTPUT = Path(os.environ["E090_PRODUCER_OUTPUT"])\nHINT_GEOMETRY = Path(os.environ["E090_HINT_GEOMETRY"])\nMAX_RELOCATED_POLES = int(os.environ.get("E090_MAX_RELOCATED_POLES", "3"))\nSOLVE_SECONDS = float(os.environ.get("E090_SOLVE_SECONDS", "240"))\nTEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")',
    )
    patch(
        "first_solution_solver",
        "    solver.parameters.random_seed = seed\n    solver.parameters.symmetry_level = 3\n    solver.parameters.cp_model_probing_level = 3\n    started = time.monotonic()",
        "    solver.parameters.random_seed = seed\n    solver.parameters.symmetry_level = 3\n    solver.parameters.cp_model_probing_level = 3\n    solver.parameters.randomize_search = True\n    solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH\n    solver.parameters.repair_hint = True\n    solver.parameters.hint_conflict_limit = 2000\n    solver.parameters.stop_after_first_solution = True\n    started = time.monotonic()",
    )
    patch(
        "three_pole_budget",
        "    model.Add(sum(pole_vars) == EXPECTED_POLE_COUNT)\n\n    for variables, rows in ((body_vars, body_rows), (pole_vars, pole_rows)):",
        "    model.Add(sum(pole_vars) == EXPECTED_POLE_COUNT)\n    current_pole_vars = [\n        pole_vars[index]\n        for index, row in enumerate(pole_rows)\n        if row[\"is_current\"]\n    ]\n    model.Add(\n        sum(current_pole_vars)\n        >= EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES\n    )\n\n    for variables, rows in ((body_vars, body_rows), (pole_vars, pole_rows)):",
    )

    marker = "    retained_body_terms = ["
    prefix, separator, _old_tail = source.partition(marker)
    if not separator:
        raise RuntimeError("E090 tail marker not found")
    new_tail = r'''    retained_body_terms = [
        body_vars[index] for index, row in enumerate(body_rows) if row["is_current"]
    ]
    retained_pole_terms = [
        pole_vars[index] for index, row in enumerate(pole_rows) if row["is_current"]
    ]

    hint = load(HINT_GEOMETRY)
    hint_bodies = {
        tuple(sorted(cell(value) for value in row["body"]))
        for row in hint["selected_manufacturing"]
    }
    hint_poles = {int(row["pose_index"]) for row in hint["selected_poles"]}
    hint_boundary = int(hint["selected_boundary_state_index"])
    matched_hint_bodies = 0
    for index, row in enumerate(body_rows):
        selected = row["body"] in hint_bodies
        model.AddHint(body_vars[index], int(selected))
        matched_hint_bodies += int(selected)
    if matched_hint_bodies != EXPECTED_MANUFACTURING_COUNT:
        raise RuntimeError(f"E090 hint body remap drift: {matched_hint_bodies}")
    matched_hint_poles = 0
    for index, row in enumerate(pole_rows):
        selected = int(row["pose_index"]) in hint_poles
        model.AddHint(pole_vars[index], int(selected))
        matched_hint_poles += int(selected)
    if matched_hint_poles != EXPECTED_POLE_COUNT:
        raise RuntimeError(f"E090 hint pole remap drift: {matched_hint_poles}")
    for index, variable in enumerate(boundary_vars):
        model.AddHint(variable, int(index == hint_boundary))

    validation_error = model.Validate()
    if validation_error:
        raise RuntimeError(f"E090 derived model invalid: {validation_error}")
    solver, status, elapsed = solve(model, seed=90001, seconds=SOLVE_SECONDS)
    solver_status = solver.StatusName(status)
    result: dict[str, Any] = {
        "schema": "zmd_e090_three_pole_front_producer_v1",
        "status": solver_status,
        "solver_status": solver_status,
        "elapsed_seconds": elapsed,
        "max_relocated_poles": MAX_RELOCATED_POLES,
        "minimum_retained_current_poles": EXPECTED_POLE_COUNT - MAX_RELOCATED_POLES,
        "body_candidate_count": len(body_rows),
        "pole_candidate_count": len(pole_rows),
        "mode_class_variable_count": len(mode_class_rows),
        "model_variable_count": len(model.Proto().variables),
        "model_constraint_count": len(model.Proto().constraints),
        "body_domain_counts": body_domain_counts,
        "front_class_counts": {
            f"{module}:{template}:{need_in}:{need_out}": int(count)
            for (module, template, need_in, need_out), count in sorted(class_counts.items())
        },
        "front_class_operations": {
            f"{module}:{template}:{need_in}:{need_out}": sorted(operations)
            for (module, template, need_in, need_out), operations in sorted(class_operations.items())
        },
        "unpowerable_body_candidate_count": disabled_unpowerable,
        "stable_body_candidate_indices": stable_indices,
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "hint": {
            "source": str(HINT_GEOMETRY),
            "matched_body_count": matched_hint_bodies,
            "matched_pole_count": matched_hint_poles,
            "boundary_state_index": hint_boundary,
        },
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
        selected_mode_rows: list[dict[str, Any]] = []
        by_class: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
        for row in mode_class_rows:
            if not solver.Value(row["variable"]):
                continue
            body_index, pose_index, class_key = row["key"]
            selected = {
                "body_index": int(body_index),
                "pose_index": int(pose_index),
                "class_key": class_key,
            }
            selected_mode_rows.append(selected)
            by_class[class_key].append(selected)
        if len(selected_bodies) != EXPECTED_MANUFACTURING_COUNT:
            raise RuntimeError("E090 positive lacks 219 selected bodies")
        if len(selected_poles) != EXPECTED_POLE_COUNT:
            raise RuntimeError("E090 positive lacks 53 selected poles")
        if len(selected_mode_rows) != EXPECTED_MANUFACTURING_COUNT:
            raise RuntimeError("E090 positive lacks 219 selected mode classes")

        operation_by_body: dict[int, str] = {}
        remaining = {str(key): int(value) for key, value in operation_counts.items()}
        stable_operation_by_id = {
            "grinder_dense_source_001": "grinder_fine_buckwheat",
            "grinder_fine_buckwheat_002": "filling_capsule",
        }
        for instance_id, operation in stable_operation_by_id.items():
            body_index = int(stable_indices[instance_id])
            matching = [
                row for row in selected_mode_rows if int(row["body_index"]) == body_index
            ]
            if len(matching) != 1:
                raise RuntimeError(f"E090 stable mode row drift: {instance_id}")
            profile = get_operation_port_profile(operation)
            expected_class = (
                "B",
                str(profile.facility_type),
                sum(int(value) for value in profile.input_slots.values()),
                sum(int(value) for value in profile.output_slots.values()),
            )
            if tuple(matching[0]["class_key"]) != expected_class:
                raise RuntimeError(f"E090 stable class drift: {instance_id}")
            if remaining.get(operation, 0) <= 0:
                raise RuntimeError(f"E090 stable operation count exhausted: {operation}")
            operation_by_body[body_index] = operation
            remaining[operation] -= 1

        for class_key in sorted(by_class):
            rows = sorted(by_class[class_key], key=lambda row: int(row["body_index"]))
            unassigned = [
                row for row in rows if int(row["body_index"]) not in operation_by_body
            ]
            operations: list[str] = []
            for operation in sorted(class_operations[class_key]):
                operations.extend([operation] * int(remaining[operation]))
            if len(operations) != len(unassigned):
                raise RuntimeError(
                    f"E090 named-operation materialization drift {class_key}: "
                    f"{len(operations)} != {len(unassigned)}"
                )
            for row, operation in zip(unassigned, operations, strict=True):
                operation_by_body[int(row["body_index"])] = operation
                remaining[operation] -= 1
        if any(value != 0 for value in remaining.values()):
            raise RuntimeError(f"E090 named-operation residual counts: {remaining}")
        if len(operation_by_body) != EXPECTED_MANUFACTURING_COUNT:
            raise RuntimeError("E090 named-operation assignment cardinality drift")

        mode_by_body = {
            int(row["body_index"]): int(row["pose_index"])
            for row in selected_mode_rows
        }
        state_index = next(
            index for index, variable in enumerate(boundary_vars) if solver.Value(variable)
        )
        selected_pole_pose_indices = {
            int(row["pose_index"]) for row in selected_poles
        }
        retained_poles = len(selected_pole_pose_indices & current_poles)
        relocated_poles = EXPECTED_POLE_COUNT - retained_poles
        if relocated_poles > MAX_RELOCATED_POLES:
            raise RuntimeError("E090 pole budget violated by extracted witness")
        retained_bodies = sum(bool(row["is_current"]) for row in selected_bodies)

        result.update(
            {
                "status": "FRONT_OPERATION_FEASIBLE",
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
                        "is_current": bool(row["is_current"]),
                        "current_owner": row["current_owner"],
                        "operation": operation_by_body[int(row["candidate_index"])],
                        "pose_index": mode_by_body[int(row["candidate_index"])],
                        "pose_id": str(
                            pools[str(row["template"])][
                                mode_by_body[int(row["candidate_index"])]
                            ]["pose_id"]
                        ),
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
                "selected_mode_class_digest": stable_digest(
                    sorted(
                        (
                            int(row["body_index"]),
                            int(row["pose_index"]),
                            tuple(row["class_key"]),
                        )
                        for row in selected_mode_rows
                    )
                ),
            }
        )

    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "solver_status": solver_status,
                "elapsed_seconds": elapsed,
                "retained_manufacturing_count": result.get(
                    "retained_manufacturing_count"
                ),
                "relocated_pole_count": result.get("relocated_pole_count"),
                "selected_boundary_state_id": result.get(
                    "selected_boundary_state_id"
                ),
                "output_path": str(OUTPUT.relative_to(ROOT)),
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
            "label": "pure_feasibility_tail",
            "old_sha256": sha256_bytes(_old_tail.encode("utf-8")),
            "new_sha256": sha256_bytes(new_tail.encode("utf-8")),
        }
    )
    return source, patches


def import_derived(path: Path) -> ModuleType:
    name = "zmd_e090_three_pole_front_producer"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import derived E090 producer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def process_memory_snapshot() -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "ru_maxrss_kib": int(usage.ru_maxrss),
        "minor_page_faults": int(usage.ru_minflt),
        "major_page_faults": int(usage.ru_majflt),
        "voluntary_context_switches": int(usage.ru_nvcsw),
        "involuntary_context_switches": int(usage.ru_nivcsw),
    }


def classify(producer: dict[str, Any]) -> tuple[str, str]:
    status = str(producer.get("status", "MISSING"))
    if status == "FRONT_OPERATION_FEASIBLE":
        return (
            "THREE_POLE_FRONT_OPERATION_WITNESS_FOUND",
            "RUN_TERMINAL_UNIQUENESS_GENERIC_IO_AND_COMPONENT_BINDING",
        )
    if status == "MASTER_INFEASIBLE":
        return (
            "THREE_POLE_FRONT_LANGUAGE_INFEASIBLE",
            "MOVE_IDENTICAL_CONSUMER_TO_NEXT_E081_PARETO_PARTITION",
        )
    return (
        "THREE_POLE_FRONT_DISCRIMINATOR_CENSORED",
        "MOVE_IDENTICAL_THREE_POLE_CONSUMER_TO_NEXT_E081_PARETO_PARTITION_AS_CONTROL",
    )


def run(*, run_dir: Path, solve_seconds: float) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E090 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    derived_path = run_dir / "DERIVED_PRODUCER.py"
    derivation_path = run_dir / "DERIVATION.json"
    producer_result_path = run_dir / "PRODUCER_RESULT.json"

    derived_source, patches = derive_source()
    with derived_path.open("xb") as handle:
        handle.write(derived_source.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    dump_exclusive(
        derivation_path,
        {
            "schema": "zmd_e090_derived_producer_identity_v1",
            "source_path": display(SOURCE_PRODUCER),
            "source_sha256": EXPECTED_HASHES[SOURCE_PRODUCER],
            "derived_path": display(derived_path),
            "derived_sha256": sha256_file(derived_path),
            "patches": patches,
            "semantic_changes": {
                "same_y41_partition": True,
                "complete_boundary_disjunction": True,
                "same_body_front_class_semantics": True,
                "same_power_semantics": True,
                "pole_language": "exactly_53_at_least_50_current",
                "max_relocated_poles": MAX_RELOCATED_POLES,
                "objective_removed": True,
                "stop_after_first_solution": True,
                "hint_is_e084_exact_three_pole_power_geometry": True,
            },
        },
    )

    prior_output = os.environ.get("E090_PRODUCER_OUTPUT")
    prior_hint = os.environ.get("E090_HINT_GEOMETRY")
    prior_budget = os.environ.get("E090_MAX_RELOCATED_POLES")
    prior_seconds = os.environ.get("E090_SOLVE_SECONDS")
    os.environ["E090_PRODUCER_OUTPUT"] = str(producer_result_path)
    os.environ["E090_HINT_GEOMETRY"] = str(HINT_GEOMETRY)
    os.environ["E090_MAX_RELOCATED_POLES"] = str(MAX_RELOCATED_POLES)
    os.environ["E090_SOLVE_SECONDS"] = str(float(solve_seconds))

    before_process = process_memory_snapshot()
    before_cgroup = cgroup_snapshot()
    started = time.monotonic()
    try:
        producer = import_derived(derived_path)
        exit_code = int(producer.main())
    finally:
        for key, value in (
            ("E090_PRODUCER_OUTPUT", prior_output),
            ("E090_HINT_GEOMETRY", prior_hint),
            ("E090_MAX_RELOCATED_POLES", prior_budget),
            ("E090_SOLVE_SECONDS", prior_seconds),
        ):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    elapsed = time.monotonic() - started
    after_process = process_memory_snapshot()
    after_cgroup = cgroup_snapshot()

    if exit_code != 0:
        raise RuntimeError(f"derived E090 producer returned {exit_code}")
    if not producer_result_path.is_file():
        raise RuntimeError("derived E090 producer did not write result")
    producer_result = load_json(producer_result_path)
    verdict, decision = classify(producer_result)
    if producer_result.get("status") == "FRONT_OPERATION_FEASIBLE":
        if len(producer_result.get("selected_manufacturing", [])) != 219:
            raise RuntimeError("E090 positive lacks 219 manufacturing rows")
        if len(producer_result.get("selected_poles", [])) != 53:
            raise RuntimeError("E090 positive lacks 53 poles")
        if int(producer_result.get("relocated_pole_count", 99)) > MAX_RELOCATED_POLES:
            raise RuntimeError("E090 positive exceeds pole budget")

    return {
        "schema": "zmd_e090_three_pole_front_discriminator_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "controls": {
            "max_relocated_poles": MAX_RELOCATED_POLES,
            "minimum_retained_current_poles": 53 - MAX_RELOCATED_POLES,
            "solve_seconds": float(solve_seconds),
            "pure_feasibility": True,
            "stop_after_first_solution": True,
            "seed": 90001,
            "hint_source": display(HINT_GEOMETRY),
            "hint_source_sha256": EXPECTED_HASHES[HINT_GEOMETRY],
        },
        "derivation": {
            "path": display(derivation_path),
            "sha256": sha256_file(derivation_path),
            "derived_source_path": display(derived_path),
            "derived_source_sha256": sha256_file(derived_path),
            "patch_count": len(patches),
        },
        "producer": {
            "status": str(producer_result.get("status", "MISSING")),
            "solver_status": str(producer_result.get("solver_status", "MISSING")),
            "result_path": display(producer_result_path),
            "result_sha256": sha256_file(producer_result_path),
            "elapsed_seconds": producer_result.get("elapsed_seconds"),
            "branches": producer_result.get("branches"),
            "conflicts": producer_result.get("conflicts"),
            "body_candidate_count": producer_result.get("body_candidate_count"),
            "pole_candidate_count": producer_result.get("pole_candidate_count"),
            "mode_class_variable_count": producer_result.get(
                "mode_class_variable_count"
            ),
            "model_variable_count": producer_result.get("model_variable_count"),
            "model_constraint_count": producer_result.get(
                "model_constraint_count"
            ),
            "retained_manufacturing_count": producer_result.get(
                "retained_manufacturing_count"
            ),
            "moved_manufacturing_count": producer_result.get(
                "moved_manufacturing_count"
            ),
            "retained_current_pole_count": producer_result.get(
                "retained_current_pole_count"
            ),
            "relocated_pole_count": producer_result.get("relocated_pole_count"),
            "selected_boundary_state_id": producer_result.get(
                "selected_boundary_state_id"
            ),
            "selected_manufacturing_count": len(
                producer_result.get("selected_manufacturing", [])
            ),
            "selected_pole_count": len(producer_result.get("selected_poles", [])),
        },
        "telemetry": {
            "wrapper_elapsed_seconds": elapsed,
            "process_before": before_process,
            "process_after": after_process,
            "cgroup_before": before_cgroup,
            "cgroup_after": after_cgroup,
            "cgroup_scope_note": (
                "cgroup counters may include sibling processes; ru_maxrss is for "
                "the E090 Python process and its in-process native solver."
            ),
        },
        "truth_boundary": (
            "Exact complete native-front class model for y=41 with exactly 53 poles "
            "and at most three relocations. A positive includes deterministic exact "
            "named-operation materialization. No terminal uniqueness, generic I/O, "
            "component binding, routing, throughput or whole-layout claim. UNKNOWN "
            "remains censored."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument(
        "--solve-seconds", type=float, default=DEFAULT_SOLVE_SECONDS
    )
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    result_path = run_dir / "RESULT.json"
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(
            run_dir=run_dir,
            solve_seconds=float(args.solve_seconds),
        )
        dump_exclusive(result_path, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "producer_status": result["producer"]["status"],
                    "producer_solver_status": result["producer"]["solver_status"],
                    "producer_elapsed_seconds": result["producer"][
                        "elapsed_seconds"
                    ],
                    "relocated_pole_count": result["producer"][
                        "relocated_pole_count"
                    ],
                    "selected_manufacturing_count": result["producer"][
                        "selected_manufacturing_count"
                    ],
                    "ru_maxrss_kib": result["telemetry"]["process_after"][
                        "ru_maxrss_kib"
                    ],
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
            "schema": "zmd_e090_three_pole_front_discriminator_failure_v1",
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
