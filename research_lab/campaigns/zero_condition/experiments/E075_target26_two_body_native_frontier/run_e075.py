#!/usr/bin/env python3
"""E075: exhaustive native two-body frontier for E074 target 26."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import inspect
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E075_target26_two_body_native_frontier/run-002"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ATLAS_PATH = OUT / "TWO_BODY_FRONTIER.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E069_RUNNER = EXPERIMENT_ROOT / "E069_six4_near_miss_complete_face/run_e069.py"
E074_RUNNER = (
    EXPERIMENT_ROOT / "E074_minimum_assignment_transport_core/run_e074.py"
)

E069_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001"
)
E069_RESULT = E069_RUN / "RESULT.json"
E069_PARENT = E069_RUN / "PARENT_SOLUTION.json"
E069_FACE = E069_RUN / "FACE_CONTEXT.json"
E070_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E070_dual_filling_signature_targets/run-004/RESULT.json"
)
E074_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E074_minimum_assignment_transport_core/run-001"
)
E074_RESULT = E074_RUN / "RESULT.json"
E074_TARGET26 = E074_RUN / "TARGET_026_TRANSPORT.json"
E075_RUN1 = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E075_target26_two_body_native_frontier/run-001"
)
E075_RUN1_RESULT = E075_RUN1 / "RESULT.json"
E075_RUN1_ATLAS = E075_RUN1 / "TWO_BODY_FRONTIER.json"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e075_source_cache_v2",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "298000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E069_RUNNER: "2061d59f2f1e0bf28ad27bca1730a90323f6efca38a266675115717e8969b598",
    E074_RUNNER: "74e2720cf4b7aaa56fb004864f54c99710b004ae15bb77c5582a205558c67b25",
    E069_RESULT: "cc16d6f308856201cfe06d85617290481ecde85815e5c83f1d9a4acbeb4efcaa",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E069_FACE: "c05a4e94ea370e8b674e44cd7206a9189ddd2102b824d36acd65975395c46c3e",
    E070_RESULT: "e15599c5c967cdc5ab74fb755b41d32cb476d68544a1f09b0b4c8be57a1829ed",
    E074_RESULT: "e3e59cc773b88f033d754a97ec16e28e9e18980c9f02b55ab8980851b95fa7c9",
    E074_TARGET26: "609e0be6613f27531e9a24bc757b3dbeb7574d6422e9eb55615cf117d74658f4",
    E075_RUN1_RESULT: "3757305872126272d766e19d3e2f929cab7b4775c2294a2a66ab5788df1bed46",
    E075_RUN1_ATLAS: "d041ad9b2672643ae86693260b1a3fe039ebafad8d15cc22e0b69f5992438eba",
}

SIX4 = "manufacturing_6x4"
OWNER_A = "grinder_dense_source_001"
OWNER_B = "grinder_fine_buckwheat_002"
OWNER_A_PARENT_DIGEST = (
    "da277903615efb73fbc9bb30716cae3b9b96654bed9905addebba0e27accf33d"
)
OWNER_B_PARENT_DIGEST = (
    "ef71d17d5e4db7bb4c3baeeee913780c753409802365896a67988bfcb43176be"
)
TARGET_COMPONENT = 26
TARGET_QIAOYU_COMPONENT = 29
FINE_GRINDER = "grinder_fine_buckwheat"
FILLING = "filling_capsule"
EXPECTED_FOOTPRINT_COUNT = 9
EXPECTED_RAW_MODE_COUNT = 18
EXPECTED_ORDERED_PAIR_COUNT = 12
ARMS = ("FREE", "CORE_OPERATIONS", "PAIR_COUPLED")
SOLVE_SECONDS = 30.0
SOLVE_WORKERS = 8
MAX_MATERIALIZED_PER_ARM = 5


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


def encoded(value: Any) -> bytes:
    return (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded(value))
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


def import_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_module(module: Any, expected_path: Path) -> dict[str, Any]:
    expected = expected_path.resolve()
    functions: list[dict[str, str]] = []
    foreign: list[dict[str, str]] = []
    for name, value in sorted(vars(module).items()):
        if not inspect.isfunction(value) or value.__module__ != module.__name__:
            continue
        actual = Path(value.__code__.co_filename).resolve()
        record = {"name": str(name), "code_filename": str(actual)}
        functions.append(record)
        if actual != expected:
            foreign.append(record)
    if foreign:
        raise RuntimeError(f"foreign functions loaded for {expected_path}: {foreign[:10]}")
    return {
        "module": str(module.__name__),
        "source": str(expected_path.relative_to(ROOT)),
        "source_sha256": sha256_file(expected_path),
        "function_count": len(functions),
        "foreign_function_count": 0,
    }


def audit_nested_modules(prefixes: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if module is None or not any(name.startswith(prefix) for prefix in prefixes):
            continue
        file_value = getattr(module, "__file__", None)
        if not isinstance(file_value, str):
            continue
        path = Path(file_value).resolve()
        source = (
            Path(importlib.util.source_from_cache(str(path))).resolve()
            if path.suffix == ".pyc"
            else path
        )
        rows.append(audit_module(module, source))
    return rows


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E075 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E075 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E075 requires a clean tracked worktree: {tracked_status}")
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
            f"environment mismatch: {mismatches}; unexpected={unexpected_exact}"
        )
    checked: dict[str, str] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        checked[str(path)] = actual
        if actual != expected:
            raise RuntimeError(f"frozen identity drift: {path}: {actual} != {expected}")

    e074 = load_json(E074_RESULT)
    if (
        e074.get("verdict") != "SMALL_ASSIGNMENT_TRANSPORT_CORES_FOUND"
        or int(e074.get("minimum_core_size", -1)) != 2
        or e074.get("decision") != "BUILD_BOUNDED_STABLE_BODY_JOINT_CONSUMER"
    ):
        raise RuntimeError("E075 E074 trigger drift")
    target = load_json(E074_TARGET26)
    if (
        target.get("schema") != "zmd_zero_condition_e074_target_transport_v1"
        or int(target.get("target_component", -1)) != TARGET_COMPONENT
        or int(target.get("minimum_changed_row_count", -1)) != 2
    ):
        raise RuntimeError("E075 target-26 witness drift")
    changed = {
        str(row["body"]["source_instance_id"]): str(row["body"]["body_digest"])
        for row in target["changed_rows"]
    }
    expected_changed = {
        OWNER_A: OWNER_A_PARENT_DIGEST,
        OWNER_B: OWNER_B_PARENT_DIGEST,
    }
    if changed != expected_changed:
        raise RuntimeError(f"E075 target-26 body identity drift: {changed}")
    run1 = load_json(E075_RUN1_RESULT)
    if (
        run1.get("verdict") != "TARGET26_TWO_BODY_NATIVE_FRONTIER_EXHAUSTED"
        or int(run1.get("ordered_pair_count", -1)) != EXPECTED_ORDERED_PAIR_COUNT
        or int(run1.get("nonterminal_count", -1)) != 0
        or str(run1["identity"].get("runner_sha256"))
        != "2e5d9b4b62b139f1badf827649e1f2779637059ea6405bd90fcfd49209c088f0"
    ):
        raise RuntimeError("E075 run-001 predecessor drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def anchor(cells: Sequence[tuple[int, int]]) -> tuple[int, int]:
    return min(x for x, _y in cells), min(y for _x, y in cells)


def footprint_record(
    *,
    cells: tuple[tuple[int, int], ...],
    modes: Sequence[int],
    owner_a_parent: set[tuple[int, int]],
    owner_b_parent: set[tuple[int, int]],
) -> dict[str, Any]:
    return {
        "footprint_digest": stable_digest(cells),
        "anchor": list(anchor(cells)),
        "occupied_cells": [list(cell) for cell in cells],
        "mode_pose_indices": [int(value) for value in sorted(modes)],
        "canonical_pose_idx": int(min(modes)),
        "owner_a_symmetric_difference": len(set(cells) ^ owner_a_parent),
        "owner_b_symmetric_difference": len(set(cells) ^ owner_b_parent),
    }


def build_pair_manifest(
    *,
    context: Mapping[str, Any],
    e061: Any,
) -> dict[str, Any]:
    solution = context["solution"]
    base = context["base"]
    pools = base["inputs"]["pools"]
    e014 = base["e014"]
    owner_a_parent = set(
        e014.pose_cells(pools, SIX4, int(solution[OWNER_A]["pose_idx"]))
    )
    owner_b_parent = set(
        e014.pose_cells(pools, SIX4, int(solution[OWNER_B]["pose_idx"]))
    )
    outside = set(context["parent_base"]["occupied"]) - owner_a_parent - owner_b_parent
    mode_map = e061.modes_by_footprint(pools)
    available: list[dict[str, Any]] = []
    for raw_cells, modes in mode_map.items():
        cells = tuple(sorted((int(x), int(y)) for x, y in raw_cells))
        if set(cells) & outside:
            continue
        available.append(
            footprint_record(
                cells=cells,
                modes=modes,
                owner_a_parent=owner_a_parent,
                owner_b_parent=owner_b_parent,
            )
        )
    available.sort(
        key=lambda row: (
            int(row["owner_a_symmetric_difference"]),
            int(row["owner_b_symmetric_difference"]),
            tuple(row["anchor"]),
            str(row["footprint_digest"]),
        )
    )
    if len(available) != EXPECTED_FOOTPRINT_COUNT:
        raise RuntimeError(f"E075 footprint count drift: {len(available)}")
    if sum(len(row["mode_pose_indices"]) for row in available) != EXPECTED_RAW_MODE_COUNT:
        raise RuntimeError("E075 raw mode count drift")

    pair_rows: list[dict[str, Any]] = []
    for left, right in product(available, repeat=2):
        left_cells = {tuple(cell) for cell in left["occupied_cells"]}
        right_cells = {tuple(cell) for cell in right["occupied_cells"]}
        if left_cells & right_cells:
            continue
        pair_rows.append(
            {
                "owner_a_footprint_digest": str(left["footprint_digest"]),
                "owner_b_footprint_digest": str(right["footprint_digest"]),
                "owner_a_anchor": list(left["anchor"]),
                "owner_b_anchor": list(right["anchor"]),
                "owner_a_canonical_pose_idx": int(left["canonical_pose_idx"]),
                "owner_b_canonical_pose_idx": int(right["canonical_pose_idx"]),
                "owner_a_mode_pose_indices": list(left["mode_pose_indices"]),
                "owner_b_mode_pose_indices": list(right["mode_pose_indices"]),
                "owner_a_occupied_cells": list(left["occupied_cells"]),
                "owner_b_occupied_cells": list(right["occupied_cells"]),
                "combined_parent_symmetric_difference": int(
                    left["owner_a_symmetric_difference"]
                    + right["owner_b_symmetric_difference"]
                ),
            }
        )
    pair_rows.sort(
        key=lambda row: (
            int(row["combined_parent_symmetric_difference"]),
            tuple(row["owner_a_anchor"]),
            tuple(row["owner_b_anchor"]),
            int(row["owner_a_canonical_pose_idx"]),
            int(row["owner_b_canonical_pose_idx"]),
        )
    )
    if len(pair_rows) != EXPECTED_ORDERED_PAIR_COUNT:
        raise RuntimeError(f"E075 ordered pair count drift: {len(pair_rows)}")
    for index, row in enumerate(pair_rows, 1):
        row["pair_index"] = index
    return {
        "schema": "zmd_zero_condition_e075_pair_manifest_v1",
        "available_footprint_count": len(available),
        "raw_mode_count": sum(len(row["mode_pose_indices"]) for row in available),
        "ordered_pair_count": len(pair_rows),
        "owner_a_parent_cells": [list(cell) for cell in sorted(owner_a_parent)],
        "owner_b_parent_cells": [list(cell) for cell in sorted(owner_b_parent)],
        "footprints": available,
        "pairs": pair_rows,
        "manifest_digest": stable_digest(pair_rows),
    }


def candidate_solution(
    *,
    context: Mapping[str, Any],
    pair: Mapping[str, Any],
) -> dict[str, Any]:
    base = context["base"]
    pools = base["inputs"]["pools"]
    e014 = base["e014"]
    solution = {str(key): dict(value) for key, value in context["solution"].items()}
    for owner, pose_idx in (
        (OWNER_A, int(pair["owner_a_canonical_pose_idx"])),
        (OWNER_B, int(pair["owner_b_canonical_pose_idx"])),
    ):
        solution[owner] = e014.replacement_row(
            source=solution[owner],
            pose=pools[SIX4][pose_idx],
            pose_idx=pose_idx,
            instance_id=owner,
        )
    mandatory_count = sum(bool(row.get("is_mandatory")) for row in solution.values())
    pole_count = sum(
        str(row.get("facility_type")) == "power_pole" for row in solution.values()
    )
    if mandatory_count != 266 or pole_count != 53:
        return {
            "status": "CARDINALITY_INVALID",
            "mandatory_count": mandatory_count,
            "pole_count": pole_count,
        }
    try:
        occupied, _owners = e014.base_occupancy(solution, pools)
    except RuntimeError as exc:
        return {"status": "OVERLAP_INVALID", "detail": str(exc)}
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row.get("facility_type")) == "power_pole"
    }
    if not e014.all_powered_facilities_covered(
        solution=solution,
        selected_poles=selected_poles,
        powered_templates=base["power"]["powered_templates"],
        coverers=base["power"]["coverers"],
    ):
        return {"status": "POWER_INVALID"}
    return {
        "status": "ADMITTED",
        "solution": solution,
        "occupied_cell_count": len(occupied),
        "solution_digest": stable_digest(solution),
        "selected_poles": sorted(selected_poles),
    }


def build_candidate_context(
    *,
    e061: Any,
    e074: Any,
    context: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    base = context["base"]
    pools = base["inputs"]["pools"]
    routing_context = base["build_routing_context"](solution, pools, 70, 70)
    mode_map = e061.modes_by_footprint(pools)
    descriptors = e061.dynamic_descriptors(
        candidate=solution,
        base=base,
        mode_map=mode_map,
    )
    options = e061.map_descriptors(
        descriptors=descriptors,
        routing_context=routing_context,
    )
    empty_destinations = sorted(
        int(destination) for destination, rows in options.items() if not rows
    )
    sink_space = e061.generic_sink_space(
        candidate=solution,
        routing_context=routing_context,
        inputs=base["inputs"],
        is_port_front_usable=base["is_port_front_usable"],
    )
    parent_sink_slot_ids = {
        str(row["slot_id"])
        for row in context["sink_space"]["slots"]
        if int(row["component"]) == TARGET_QIAOYU_COMPONENT
    }
    if not parent_sink_slot_ids:
        raise RuntimeError("E075 parent qiaoyu sink-slot identity is empty")
    transported_sink_slots = [
        dict(row)
        for row in sink_space["slots"]
        if str(row["slot_id"]) in parent_sink_slot_ids
    ]
    transported_sink_components = sorted(
        {int(row["component"]) for row in transported_sink_slots}
    )
    parent_target_cells = set(
        context["routing_context"].cells_by_component[TARGET_COMPONENT]
    )
    transported_target_components = sorted(
        {
            int(routing_context.component_by_cell[cell])
            for cell in parent_target_cells
            if cell in routing_context.component_by_cell
        }
    )
    bodies = e061.body_rows(solution, pools, base["e014"])
    destination_by_owner = {
        str(body["source_instance_id"]): int(destination)
        for destination, body in enumerate(bodies)
    }
    if OWNER_A not in destination_by_owner or OWNER_B not in destination_by_owner:
        raise RuntimeError("E075 stable owner missing after candidate body sort")
    actual_options = None
    if not empty_destinations:
        actual_options = e074.normalize_actual_options(options)
    return {
        "routing_context": routing_context,
        "descriptors": descriptors,
        "options": options,
        "actual_options": actual_options,
        "empty_destinations": empty_destinations,
        "sink_space": sink_space,
        "parent_sink_slot_ids": sorted(parent_sink_slot_ids),
        "transported_sink_slots": transported_sink_slots,
        "transported_sink_components": transported_sink_components,
        "transported_target_components": transported_target_components,
        "bodies": bodies,
        "destination_by_owner": destination_by_owner,
        "free_component_count": len(routing_context.cells_by_component),
        "free_component_sizes": sorted(
            (len(cells) for cells in routing_context.cells_by_component.values()),
            reverse=True,
        ),
    }


def add_assignment_copy_transported(
    *,
    e074: Any,
    model: cp_model.CpModel,
    prefix: str,
    rows_by_destination: Mapping[int, Sequence[Mapping[str, Any]]],
    operation_counts: Mapping[str, int],
    sink_components: Sequence[int],
    allowed_sink_components: Sequence[int],
) -> dict[str, Any]:
    x_vars: dict[tuple[int, int], Any] = {}
    for destination, rows in rows_by_destination.items():
        variables: list[Any] = []
        for option_index, _option in enumerate(rows):
            variable = model.NewBoolVar(f"{prefix}_x_{destination}_{option_index}")
            x_vars[(destination, option_index)] = variable
            variables.append(variable)
        model.AddExactlyOne(variables)
    for operation, expected in operation_counts.items():
        model.Add(
            cp_model.LinearExpr.Sum(
                [
                    x_vars[(destination, option_index)]
                    for destination, rows in rows_by_destination.items()
                    for option_index, option in enumerate(rows)
                    if str(option["operation"]) == str(operation)
                ]
            )
            == int(expected)
        )
    components = sorted(
        {
            int(component)
            for rows in rows_by_destination.values()
            for option in rows
            for part in option["signature"]
            for component in part
        }
        | {int(value) for value in sink_components}
    )
    fine_sources: dict[int, Any] = {}
    fine_sinks: dict[int, Any] = {}
    qiaoyu_sources: dict[int, Any] = {}
    for component in components:
        fine_sources[component] = e074.add_exact_or(
            model,
            name=f"{prefix}_fine_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in rows_by_destination.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][1])
            ],
        )
        fine_sinks[component] = e074.add_exact_or(
            model,
            name=f"{prefix}_fine_sink_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in rows_by_destination.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][0])
            ],
        )
        qiaoyu_sources[component] = e074.add_exact_or(
            model,
            name=f"{prefix}_qiaoyu_source_{component}",
            contributors=[
                x_vars[(destination, option_index)]
                for destination, rows in rows_by_destination.items()
                for option_index, option in enumerate(rows)
                if component in set(option["signature"][2])
            ],
        )
    qiaoyu_sink_vars = {
        int(component): model.NewBoolVar(f"{prefix}_qiaoyu_sink_{component}")
        for component in sorted({int(value) for value in sink_components})
    }
    model.AddExactlyOne(list(qiaoyu_sink_vars.values()))
    for component in components:
        model.Add(
            qiaoyu_sources[component]
            == qiaoyu_sink_vars.get(component, 0)
        )
    allowed = [
        qiaoyu_sink_vars[int(component)]
        for component in sorted({int(value) for value in allowed_sink_components})
        if int(component) in qiaoyu_sink_vars
    ]
    add_one_of(model=model, variables=allowed)
    model.Add(cp_model.LinearExpr.Sum(list(fine_sources.values())) >= 1)
    model.Add(cp_model.LinearExpr.Sum(list(fine_sinks.values())) >= 1)
    return {
        "x_vars": x_vars,
        "components": components,
        "fine_sources": fine_sources,
        "fine_sinks": fine_sinks,
        "qiaoyu_sources": qiaoyu_sources,
        "qiaoyu_sink_vars": qiaoyu_sink_vars,
    }


def add_zero_constraints(
    *,
    model: cp_model.CpModel,
    built: Mapping[str, Any],
) -> None:
    for component in built["components"]:
        model.Add(
            built["fine_sources"][component]
            == built["fine_sinks"][component]
        )


def add_one_of(
    *,
    model: cp_model.CpModel,
    variables: Sequence[Any],
) -> None:
    if variables:
        model.Add(cp_model.LinearExpr.Sum(list(variables)) == 1)
    else:
        model.Add(0 == 1)


def configure_solver(*, seed: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVE_SECONDS
    solver.parameters.num_search_workers = SOLVE_WORKERS
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.symmetry_level = 3
    solver.parameters.cp_model_probing_level = 3
    solver.parameters.random_seed = int(seed)
    return solver


def solve_arm(
    *,
    e061: Any,
    e074: Any,
    candidate: Mapping[str, Any],
    arm: str,
    random_seed: int,
) -> dict[str, Any]:
    if candidate["empty_destinations"]:
        return {
            "arm": arm,
            "status": "STRUCTURAL_EMPTY",
            "empty_destinations": list(candidate["empty_destinations"]),
            "transported_sink_components": list(
                candidate["transported_sink_components"]
            ),
            "transported_target_components": list(
                candidate["transported_target_components"]
            ),
            "elapsed_seconds": 0.0,
            "branches": 0,
            "conflicts": 0,
        }
    if not candidate["transported_sink_components"]:
        return {
            "arm": arm,
            "status": "STRUCTURAL_EMPTY",
            "detail": "all stable parent qiaoyu sink slots became unusable",
            "empty_destinations": [],
            "transported_sink_components": [],
            "transported_target_components": list(
                candidate["transported_target_components"]
            ),
            "elapsed_seconds": 0.0,
            "branches": 0,
            "conflicts": 0,
        }
    if arm == "PAIR_COUPLED" and not candidate["transported_target_components"]:
        return {
            "arm": arm,
            "status": "STRUCTURAL_EMPTY",
            "detail": "no surviving physical seed from parent target component 26",
            "empty_destinations": [],
            "transported_sink_components": list(
                candidate["transported_sink_components"]
            ),
            "transported_target_components": [],
            "elapsed_seconds": 0.0,
            "branches": 0,
            "conflicts": 0,
        }
    actual = candidate["actual_options"]
    if actual is None:
        raise RuntimeError("E075 actual options missing without structural empty")
    model = cp_model.CpModel()
    built = add_assignment_copy_transported(
        e074=e074,
        model=model,
        prefix=f"e075_{arm.lower()}_{random_seed}",
        rows_by_destination=actual,
        operation_counts=e061.OPERATION_COUNTS,
        sink_components=candidate["sink_space"]["components"],
        allowed_sink_components=candidate["transported_sink_components"],
    )
    add_zero_constraints(model=model, built=built)
    destination_a = int(candidate["destination_by_owner"][OWNER_A])
    destination_b = int(candidate["destination_by_owner"][OWNER_B])

    if arm in {"CORE_OPERATIONS", "PAIR_COUPLED"}:
        add_one_of(
            model=model,
            variables=[
                built["x_vars"][(destination_a, option_index)]
                for option_index, option in enumerate(actual[destination_a])
                if str(option["operation"]) == FINE_GRINDER
            ],
        )
        add_one_of(
            model=model,
            variables=[
                built["x_vars"][(destination_b, option_index)]
                for option_index, option in enumerate(actual[destination_b])
                if str(option["operation"]) == FILLING
            ],
        )
    compatible_pairs: list[dict[str, Any]] = []
    if arm == "PAIR_COUPLED":
        transported_targets = {
            int(value) for value in candidate["transported_target_components"]
        }
        transported_sinks = {
            int(value) for value in candidate["transported_sink_components"]
        }
        pair_vars: list[Any] = []
        for a_index, a_option in enumerate(actual[destination_a]):
            a_signature = tuple(a_option["signature"])
            if (
                str(a_option["operation"]) != FINE_GRINDER
                or tuple(a_signature[0])
                or tuple(a_signature[2])
                or len(tuple(a_signature[1])) != 1
                or int(tuple(a_signature[1])[0]) not in transported_targets
            ):
                continue
            for b_index, b_option in enumerate(actual[destination_b]):
                b_signature = tuple(b_option["signature"])
                if (
                    str(b_option["operation"]) != FILLING
                    or tuple(b_signature[1])
                    or tuple(b_signature[0]) != tuple(a_signature[1])
                    or len(tuple(b_signature[2])) != 1
                    or int(tuple(b_signature[2])[0]) not in transported_sinks
                ):
                    continue
                pair_var = model.NewBoolVar(
                    f"e075_pair_{random_seed}_{a_index}_{b_index}"
                )
                a_var = built["x_vars"][(destination_a, a_index)]
                b_var = built["x_vars"][(destination_b, b_index)]
                model.Add(pair_var <= a_var)
                model.Add(pair_var <= b_var)
                model.Add(pair_var >= a_var + b_var - 1)
                pair_vars.append(pair_var)
                compatible_pairs.append(
                    {
                        "owner_a_option_index": int(a_index),
                        "owner_b_option_index": int(b_index),
                        "fine_component": int(tuple(a_signature[1])[0]),
                        "qiaoyu_component": int(tuple(b_signature[2])[0]),
                        "owner_a_pose_idx": int(a_option["pose_idx"]),
                        "owner_b_pose_idx": int(b_option["pose_idx"]),
                    }
                )
        add_one_of(model=model, variables=pair_vars)

    deterministic_terms = [
        ((destination + 1) * 10_000 + option_index + 1)
        * built["x_vars"][(destination, option_index)]
        for destination, rows in actual.items()
        for option_index, _option in enumerate(rows)
    ]
    model.Minimize(cp_model.LinearExpr.Sum(deterministic_terms))
    solver = configure_solver(seed=random_seed)
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    status_name = solver.StatusName(status)
    result: dict[str, Any] = {
        "arm": arm,
        "status": status_name,
        "best_bound": float(solver.BestObjectiveBound()),
        "elapsed_seconds": elapsed,
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "destination_by_owner": dict(candidate["destination_by_owner"]),
        "parent_sink_slot_ids": list(candidate["parent_sink_slot_ids"]),
        "transported_sink_components": list(
            candidate["transported_sink_components"]
        ),
        "transported_target_components": list(
            candidate["transported_target_components"]
        ),
        "compatible_pair_count": len(compatible_pairs),
        "compatible_pairs": compatible_pairs,
        "selected_sink_component": None,
        "fine_components": None,
        "selected_core_rows": [],
        "assignment_digest": None,
        "selected_assignment": None,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignment = e074.selected_assignment(
            solver=solver,
            rows_by_destination=actual,
            x_vars=built["x_vars"],
            bodies=candidate["bodies"],
        )
        core_rows = [
            row
            for row in assignment
            if str(row["body"]["source_instance_id"]) in {OWNER_A, OWNER_B}
        ]
        if len(core_rows) != 2:
            raise RuntimeError(f"E075 selected core-row count drift: {core_rows}")
        selected_sink_components = [
            int(component)
            for component, variable in built["qiaoyu_sink_vars"].items()
            if solver.Value(variable) == 1
        ]
        if len(selected_sink_components) != 1:
            raise RuntimeError(
                f"E075 selected transported sink count drift: {selected_sink_components}"
            )
        result.update(
            {
                "selected_sink_component": selected_sink_components[0],
                "fine_components": [
                    int(component)
                    for component, variable in built["fine_sources"].items()
                    if solver.Value(variable) == 1
                ],
                "selected_core_rows": core_rows,
                "assignment_digest": stable_digest(assignment),
                "selected_assignment": assignment,
            }
        )
    return result


def materialize_positive(
    *,
    context: Mapping[str, Any],
    pair: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
    arm_result: Mapping[str, Any],
    rank: int,
) -> dict[str, Any]:
    arm = str(arm_result["arm"])
    selected_by_owner = {
        str(row["body"]["source_instance_id"]): row["selected_option"]
        for row in arm_result["selected_core_rows"]
    }
    if set(selected_by_owner) != {OWNER_A, OWNER_B}:
        raise RuntimeError("E075 positive endpoint lacks both core owners")
    placement = {str(key): dict(value) for key, value in solution.items()}
    base = context["base"]
    pools = base["inputs"]["pools"]
    e014 = base["e014"]
    for owner in (OWNER_A, OWNER_B):
        selected_pose_idx = int(selected_by_owner[owner]["pose_idx"])
        current = placement[owner]
        if str(current["facility_type"]) != SIX4:
            raise RuntimeError(f"E075 selected core row left 6x4 block: {owner}")
        placement[owner] = e014.replacement_row(
            source=current,
            pose=pools[SIX4][selected_pose_idx],
            pose_idx=selected_pose_idx,
            instance_id=owner,
        )
    for owner, allowed_key in (
        (OWNER_A, "owner_a_mode_pose_indices"),
        (OWNER_B, "owner_b_mode_pose_indices"),
    ):
        if int(placement[owner]["pose_idx"]) not in {
            int(value) for value in pair[allowed_key]
        }:
            raise RuntimeError(f"E075 selected core mode left pair footprint: {owner}")
    try:
        occupied, _owners = e014.base_occupancy(placement, pools)
    except RuntimeError as exc:
        raise RuntimeError(f"E075 positive placement overlap: {exc}") from exc
    selected_poles = {
        int(row["pose_idx"])
        for row in placement.values()
        if str(row.get("facility_type")) == "power_pole"
    }
    if not e014.all_powered_facilities_covered(
        solution=placement,
        selected_poles=selected_poles,
        powered_templates=base["power"]["powered_templates"],
        coverers=base["power"]["coverers"],
    ):
        raise RuntimeError("E075 positive selected-mode placement lost power")
    path = OUT / f"POSITIVE_{arm}_{rank:02d}.json"
    payload = {
        "schema": "zmd_zero_condition_e075_positive_endpoint_v2",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "rank": int(rank),
        "arm": arm,
        "pair": pair,
        "placement_solution_digest": stable_digest(placement),
        "placement_occupied_cell_count": len(occupied),
        "placement_solution": placement,
        "placement_mode_scope": (
            "only the two exact target-operation core owners are updated from the "
            "selected assignment; collapsed 'other' rows remain an abstract ledger"
        ),
        "selected_assignment_digest": str(arm_result["assignment_digest"]),
        "selected_assignment": arm_result["selected_assignment"],
        "selected_core_rows": arm_result["selected_core_rows"],
        "fine_components": arm_result["fine_components"],
        "selected_sink_component": arm_result["selected_sink_component"],
        "ledger_effect": "none",
    }
    dump_exclusive(path, payload)
    return {
        "rank": int(rank),
        "arm": arm,
        "pair_index": int(pair["pair_index"]),
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    e061 = import_module("zmd_e075_e061", E061_RUNNER)
    e062 = import_module("zmd_e075_e062", E062_RUNNER)
    e063 = import_module("zmd_e075_e063", E063_RUNNER)
    e069 = import_module("zmd_e075_e069", E069_RUNNER)
    e074 = import_module("zmd_e075_e074", E074_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
        audit_module(e069, E069_RUNNER),
        audit_module(e074, E074_RUNNER),
    ]
    context = e069.reconstruct_parent(e061, e062, e063)
    nested_origins = audit_nested_modules(
        (
            "zmd_e075_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
            "zmd_e069_",
            "zmd_e074_",
        )
    )
    parent_bodies = e061.body_rows(
        context["solution"],
        context["base"]["inputs"]["pools"],
        context["base"]["e014"],
    )
    parent_digest_by_owner = {
        str(row["source_instance_id"]): str(row["body_digest"])
        for row in parent_bodies
    }
    if parent_digest_by_owner.get(OWNER_A) != OWNER_A_PARENT_DIGEST:
        raise RuntimeError("E075 owner A parent body drift")
    if parent_digest_by_owner.get(OWNER_B) != OWNER_B_PARENT_DIGEST:
        raise RuntimeError("E075 owner B parent body drift")

    manifest = build_pair_manifest(context=context, e061=e061)
    pools = context["base"]["inputs"]["pools"]
    for pair in manifest["pairs"]:
        pair["owner_a_mode_pose_ids"] = {
            str(pose_idx): str(pools[SIX4][int(pose_idx)]["pose_id"])
            for pose_idx in pair["owner_a_mode_pose_indices"]
        }
        pair["owner_b_mode_pose_ids"] = {
            str(pose_idx): str(pools[SIX4][int(pose_idx)]["pose_id"])
            for pose_idx in pair["owner_b_mode_pose_indices"]
        }
    manifest["manifest_digest"] = stable_digest(manifest["pairs"])

    records: list[dict[str, Any]] = []
    positive_solutions: dict[tuple[int, str], Mapping[str, Mapping[str, Any]]] = {}
    started = time.monotonic()
    for pair in manifest["pairs"]:
        pair_index = int(pair["pair_index"])
        admitted = candidate_solution(context=context, pair=pair)
        record: dict[str, Any] = {
            "pair_index": pair_index,
            "pair": pair,
            "admission_status": str(admitted["status"]),
            "solution_digest": admitted.get("solution_digest"),
            "arms": [],
        }
        if admitted["status"] == "ADMITTED":
            solution = admitted["solution"]
            candidate = build_candidate_context(
                e061=e061,
                e074=e074,
                context=context,
                solution=solution,
            )
            record.update(
                {
                    "free_component_count": candidate["free_component_count"],
                    "free_component_sizes": candidate["free_component_sizes"],
                    "empty_destinations": candidate["empty_destinations"],
                    "sink_components": list(candidate["sink_space"]["components"]),
                    "parent_sink_slot_ids": list(candidate["parent_sink_slot_ids"]),
                    "transported_sink_slots": list(
                        candidate["transported_sink_slots"]
                    ),
                    "transported_sink_components": list(
                        candidate["transported_sink_components"]
                    ),
                    "transported_target_components": list(
                        candidate["transported_target_components"]
                    ),
                    "destination_by_owner": dict(candidate["destination_by_owner"]),
                }
            )
            for arm_index, arm in enumerate(ARMS, 1):
                arm_result = solve_arm(
                    e061=e061,
                    e074=e074,
                    candidate=candidate,
                    arm=arm,
                    random_seed=75000 + pair_index * 10 + arm_index,
                )
                record["arms"].append(arm_result)
                if arm_result["status"] in {"OPTIMAL", "FEASIBLE"}:
                    positive_solutions[(pair_index, arm)] = solution
        records.append(record)
        print(
            json.dumps(
                {
                    "event": "E075_PAIR",
                    "pair_index": pair_index,
                    "pair_count": len(manifest["pairs"]),
                    "admission": record["admission_status"],
                    "arms": [
                        {
                            "arm": arm_result["arm"],
                            "status": arm_result["status"],
                        }
                        for arm_result in record["arms"]
                    ],
                    "at_utc": utc_now(),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    status_counts_by_arm: dict[str, Counter[str]] = {
        arm: Counter() for arm in ARMS
    }
    admission_counts = Counter(str(row["admission_status"]) for row in records)
    positives_by_arm: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {
        arm: [] for arm in ARMS
    }
    nonterminal: list[dict[str, Any]] = []
    for row in records:
        for arm_result in row["arms"]:
            arm = str(arm_result["arm"])
            status = str(arm_result["status"])
            status_counts_by_arm[arm][status] += 1
            if status in {"OPTIMAL", "FEASIBLE"}:
                positives_by_arm[arm].append((row, arm_result))
            elif status not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
                nonterminal.append(
                    {
                        "pair_index": int(row["pair_index"]),
                        "arm": arm,
                        "status": status,
                    }
                )

    materialized: list[dict[str, Any]] = []
    rank = 0
    for arm in reversed(ARMS):
        ranked = sorted(
            positives_by_arm[arm],
            key=lambda item: (
                int(item[0]["pair"]["combined_parent_symmetric_difference"]),
                int(item[0]["pair_index"]),
            ),
        )[:MAX_MATERIALIZED_PER_ARM]
        for row, arm_result in ranked:
            rank += 1
            solution = positive_solutions[(int(row["pair_index"]), arm)]
            materialized.append(
                materialize_positive(
                    context=context,
                    pair=row["pair"],
                    solution=solution,
                    arm_result=arm_result,
                    rank=rank,
                )
            )

    pair_coupled_positive_count = len(positives_by_arm["PAIR_COUPLED"])
    core_positive_count = len(positives_by_arm["CORE_OPERATIONS"])
    free_positive_count = len(positives_by_arm["FREE"])
    if nonterminal:
        verdict = "TWO_BODY_NATIVE_FRONTIER_NONTERMINAL"
        decision = "CONTINUE_ONLY_NONTERMINAL_PAIR_ARMS"
    elif pair_coupled_positive_count:
        verdict = "TARGET26_NATIVE_TWO_BODY_REALIZATION_FOUND"
        decision = "ENTER_FULL_ASSIGNMENT_COMPONENT_BINDING_CONSUMER"
    elif core_positive_count or free_positive_count:
        verdict = "NATIVE_ZERO_FOUND_OUTSIDE_EXACT_TARGET26_SIGNATURE"
        decision = "DERIVE_EXACT_NATIVE_ASSIGNMENT_DIFFERENCE"
    else:
        verdict = "TARGET26_TWO_BODY_NATIVE_FRONTIER_EXHAUSTED"
        decision = "DERIVE_THIRD_STABLE_BODY_FROM_TERMINAL_OBSTRUCTION"

    atlas = {
        "schema": "zmd_zero_condition_e075_two_body_frontier_v2",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "manifest": manifest,
        "records": records,
        "admission_status_counts": dict(sorted(admission_counts.items())),
        "status_counts_by_arm": {
            arm: dict(sorted(counts.items()))
            for arm, counts in status_counts_by_arm.items()
        },
        "positive_count_by_arm": {
            arm: len(positives_by_arm[arm]) for arm in ARMS
        },
        "nonterminal": nonterminal,
        "elapsed_seconds": time.monotonic() - started,
        "ledger_effect": "none",
    }
    dump_exclusive(ATLAS_PATH, atlas)
    return {
        "schema": "zmd_zero_condition_e075_two_body_native_frontier_result_v2",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "owners": {
            "owner_a": {
                "source_instance_id": OWNER_A,
                "parent_body_digest": OWNER_A_PARENT_DIGEST,
            },
            "owner_b": {
                "source_instance_id": OWNER_B,
                "parent_body_digest": OWNER_B_PARENT_DIGEST,
            },
        },
        "available_footprint_count": manifest["available_footprint_count"],
        "raw_mode_count": manifest["raw_mode_count"],
        "ordered_pair_count": manifest["ordered_pair_count"],
        "admission_status_counts": atlas["admission_status_counts"],
        "status_counts_by_arm": atlas["status_counts_by_arm"],
        "positive_count_by_arm": atlas["positive_count_by_arm"],
        "pair_coupled_positive_count": pair_coupled_positive_count,
        "core_operation_positive_count": core_positive_count,
        "free_positive_count": free_positive_count,
        "nonterminal_count": len(nonterminal),
        "materialized_endpoints": materialized,
        "atlas_path": str(ATLAS_PATH.relative_to(ROOT)),
        "atlas_sha256": sha256_file(ATLAS_PATH),
        "decision": decision,
        "truth_boundary": (
            "E069 fixed-outside two-body geometry over stable owners A/B, all native "
            "same-footprint modes, collapsed 38-row operation classes, physical "
            "transport of E069's stable qiaoyu sink slots and target-26 seed cells, "
            "and terminal-signature equality only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E075 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "pairs": result["ordered_pair_count"],
                    "admission": result["admission_status_counts"],
                    "positive_by_arm": result["positive_count_by_arm"],
                    "nonterminal": result["nonterminal_count"],
                    "decision": result["decision"],
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
            "schema": "zmd_zero_condition_e075_two_body_native_frontier_failure_v2",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not FAILURE_PATH.exists():
            dump_exclusive(FAILURE_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
