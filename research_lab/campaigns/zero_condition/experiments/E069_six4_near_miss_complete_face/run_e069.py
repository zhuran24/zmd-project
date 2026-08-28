#!/usr/bin/env python3
"""E069: complete directional face of the distinct E062 6x4 near miss."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
PARENT_SOLUTION_PATH = OUT / "PARENT_SOLUTION.json"
FACE_CONTEXT_PATH = OUT / "FACE_CONTEXT.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E065_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E065_source_stable_replay_materialization/run-001/RESULT.json"
)
E065_E062_RESULT = E065_RESULT.parent / "e062-source/RESULT.json"
E068_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E068_final_cached_fourth_action/run-002/RESULT.json"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e069_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "295000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E065_RESULT: "c5ced5b70bc70cd3c881741b7703a4cee80ba6a625fe78350db3663e9ef38c06",
    E065_E062_RESULT: "8ddff564f9359da582bbb212d77a736c2651294c8d335d35c4104b73c0b7d361",
    E068_RESULT: "5d45ee5027229c66be7a921376c592c572fbf31d0be34f2bfeacc209a5ad548d",
}

SOURCE_INSTANCE_ID = "grinder_dense_source_002"
CURRENT_POSE_IDX = 7006
PARENT_POSE_IDX = 6878
PARENT_POSE_ID = "p_x52_y60_o0_m_TB"
EXPECTED_OBJECTIVE = 1
EXPECTED_REPRESENTATIVE_SOURCE_ONLY = (40,)
EXPECTED_REPRESENTATIVE_QIAOYU_SINK = 29
SIX4 = "manufacturing_6x4"


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
        raise RuntimeError(f"run E069 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E069 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E069 requires a clean tracked worktree: {tracked_status}")
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
    e065 = load_json(E065_RESULT)
    if e065.get("verdict") != "SOURCE_STABLE_REPLAY_SET_MATERIALIZED":
        raise RuntimeError("E069 E065 verdict drift")
    e068 = load_json(E068_RESULT)
    if e068.get("verdict") != "POLE_LINEAGE_EXHAUSTED_WITHOUT_TWO_ZERO":
        raise RuntimeError("E069 E068 stop verdict drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": tracked_status,
    }


def frozen_near_miss() -> dict[str, Any]:
    payload = load_json(E065_E062_RESULT)
    rows = [
        dict(row)
        for row in payload["strict_improvements"]
        if str(row["source_instance_id"]) == SOURCE_INSTANCE_ID
        and str(row["facility_type"]) == SIX4
        and int(row["current_pose_idx"]) == CURRENT_POSE_IDX
        and int(row["replacement_pose_idx"]) == PARENT_POSE_IDX
    ]
    if len(rows) != 1:
        raise RuntimeError(f"E069 frozen near-miss identity drift: {len(rows)}")
    row = rows[0]
    tradeoff = row["tradeoff"]
    if (
        tradeoff.get("status") != "OPTIMAL"
        or int(tradeoff.get("objective", -1)) != EXPECTED_OBJECTIVE
        or tuple(tradeoff["presence"]["source_only_components"])
        != EXPECTED_REPRESENTATIVE_SOURCE_ONLY
        or int(tradeoff["presence"]["qiaoyu_sink_component"])
        != EXPECTED_REPRESENTATIVE_QIAOYU_SINK
    ):
        raise RuntimeError(f"E069 frozen near-miss payload drift: {row}")
    return row


def reconstruct_parent(e061: Any, e062: Any, e063: Any) -> dict[str, Any]:
    base = e061.reconstruct()
    alternatives = [
        row
        for row in e061.enumerate_alternatives(
            base=base,
            instance_id=SOURCE_INSTANCE_ID,
        )
        if int(row["pose_idx"]) == PARENT_POSE_IDX
    ]
    if len(alternatives) != 1:
        raise RuntimeError(f"E069 parent alternative drift: {len(alternatives)}")
    alternative = alternatives[0]
    if str(alternative["pose_id"]) != PARENT_POSE_ID:
        raise RuntimeError(f"E069 parent pose-id drift: {alternative['pose_id']}")
    solution = {str(key): dict(value) for key, value in alternative["solution"].items()}
    row = solution[SOURCE_INSTANCE_ID]
    if int(row["pose_idx"]) != PARENT_POSE_IDX:
        raise RuntimeError("E069 parent solution pose drift")

    occupied, _owners = base["e014"].base_occupancy(
        solution,
        base["inputs"]["pools"],
    )
    selected_poles = {
        int(item["pose_idx"])
        for item in solution.values()
        if str(item["facility_type"]) == "power_pole"
    }
    parent_base = dict(base)
    parent_base.update(
        {
            "solution": solution,
            "occupied": occupied,
            "selected_poles": selected_poles,
        }
    )
    mode_map = e061.modes_by_footprint(base["inputs"]["pools"])
    descriptors = e061.dynamic_descriptors(
        candidate=solution,
        base=base,
        mode_map=mode_map,
    )
    routing_context = base["build_routing_context"](
        solution,
        base["inputs"]["pools"],
        70,
        70,
    )
    options = e061.map_descriptors(
        descriptors=descriptors,
        routing_context=routing_context,
    )
    sink_space = e061.generic_sink_space(
        candidate=solution,
        routing_context=routing_context,
        inputs=base["inputs"],
        is_port_front_usable=base["is_port_front_usable"],
    )
    calibration = e062.solve_qiaoyu_hard(
        options=options,
        sink_space=sink_space,
        random_seed=69001,
    )
    if (
        calibration.get("status") != "OPTIMAL"
        or int(calibration.get("objective", -1)) != EXPECTED_OBJECTIVE
    ):
        raise RuntimeError(f"E069 parent calibration drift: {calibration}")
    face = e063.enumerate_directional_face(
        operation_counts=e061.OPERATION_COUNTS,
        e062=e062,
        options=options,
        sink_space=sink_space,
        optimum=EXPECTED_OBJECTIVE,
        random_seed=69002,
    )
    if not bool(face.get("complete")):
        raise RuntimeError(f"E069 complete face nonterminal: {face}")
    return {
        "base": base,
        "parent_base": parent_base,
        "solution": solution,
        "routing_context": routing_context,
        "mode_map": mode_map,
        "descriptors": descriptors,
        "options": options,
        "sink_space": sink_space,
        "calibration": calibration,
        "face": face,
        "alternative": alternative,
    }


def face_summary(face: Mapping[str, Any]) -> dict[str, Any]:
    patterns = [dict(row) for row in face["patterns"]]
    unmatched_sets = [
        set(int(value) for value in row["source_only_components"])
        | set(int(value) for value in row["sink_only_components"])
        for row in patterns
    ]
    unmatched_union = sorted(set().union(*unmatched_sets)) if unmatched_sets else []
    unmatched_intersection = (
        sorted(set.intersection(*unmatched_sets)) if unmatched_sets else []
    )
    sink_components = sorted(
        {int(row["qiaoyu_sink_component"]) for row in patterns}
    )
    direction_counts = Counter(
        (
            len(row["source_only_components"]),
            len(row["sink_only_components"]),
        )
        for row in patterns
    )
    return {
        "complete": bool(face["complete"]),
        "pattern_count": int(face["pattern_count"]),
        "unmatched_components": unmatched_union,
        "stable_unmatched_components": unmatched_intersection,
        "qiaoyu_sink_components": sink_components,
        "direction_shape_counts": [
            {
                "source_only_count": key[0],
                "sink_only_count": key[1],
                "pattern_count": int(count),
            }
            for key, count in sorted(direction_counts.items())
        ],
        "patterns": patterns,
        "face_digest": stable_digest(patterns),
    }


def causal_selection(context: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    base = context["base"]
    solution = context["solution"]
    routing_context = context["routing_context"]
    targets = [int(value) for value in summary["unmatched_components"]]
    boundary_edges: dict[str, dict[int, set[tuple[int, int]]]] = {}
    component_sizes: dict[str, int] = {}
    for target in targets:
        cells = set(routing_context.cells_by_component[target])
        component_sizes[str(target)] = len(cells)
        for x, y in cells:
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                owner = routing_context.occupied_owner_by_cell.get(neighbor)
                if owner is None:
                    continue
                boundary_edges.setdefault(str(owner), {}).setdefault(
                    target,
                    set(),
                ).add(neighbor)

    owner_rows: list[dict[str, Any]] = []
    separators: set[str] = set()
    for owner, edge_map in sorted(boundary_edges.items()):
        row = solution[owner]
        facility_type = str(row["facility_type"])
        pose_idx = int(row["pose_idx"])
        touched: set[int] = set()
        for x, y in base["e014"].pose_cells(
            base["inputs"]["pools"],
            facility_type,
            pose_idx,
        ):
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                component = routing_context.component_by_cell.get(neighbor)
                if component is not None:
                    touched.add(int(component))
        is_separator = len(touched) > 1
        if is_separator:
            separators.add(owner)
        owner_rows.append(
            {
                "owner": owner,
                "facility_type": facility_type,
                "operation_type": str(row.get("operation_type", "")),
                "pose_idx": pose_idx,
                "boundary_edge_count": sum(len(edges) for edges in edge_map.values()),
                "boundary_edge_count_by_component": {
                    str(component): len(edges)
                    for component, edges in sorted(edge_map.items())
                },
                "touched_components": sorted(touched),
                "is_separator": is_separator,
            }
        )

    six4_ids = {
        str(instance_id)
        for instance_id, row in solution.items()
        if str(row["facility_type"]) == SIX4
    }
    capacity_map = base["inputs"]["plan"]["generic_input_slots_by_operation"]
    generic_provider_ids = {
        str(instance_id)
        for instance_id, row in solution.items()
        if int(capacity_map.get(str(row.get("operation_type", "")), 0)) > 0
    }
    selected_ids = (
        separators | six4_ids | generic_provider_ids
    ) - {SOURCE_INSTANCE_ID}
    return {
        "mismatch_components": targets,
        "component_sizes": component_sizes,
        "boundary_owner_count": len(boundary_edges),
        "separator_owner_count": len(separators),
        "six4_body_count": len(six4_ids),
        "generic_provider_count": len(generic_provider_ids),
        "selected_object_count": len(selected_ids),
        "selected_ids": sorted(selected_ids),
        "owner_rows": owner_rows,
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    frozen = frozen_near_miss()
    e061 = import_module("zmd_e069_e061", E061_RUNNER)
    e062 = import_module("zmd_e069_e062", E062_RUNNER)
    e063 = import_module("zmd_e069_e063", E063_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
    ]
    context = reconstruct_parent(e061, e062, e063)
    nested_origins = audit_nested_modules(
        (
            "zmd_e069_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
        )
    )
    summary = face_summary(context["face"])
    selection = causal_selection(context, summary)

    parent_payload = {
        "schema": "zmd_zero_condition_e069_parent_solution_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "parent_action": {
            "source_instance_id": SOURCE_INSTANCE_ID,
            "current_pose_idx": CURRENT_POSE_IDX,
            "replacement_pose_idx": PARENT_POSE_IDX,
            "replacement_pose_id": PARENT_POSE_ID,
        },
        "solution_digest": stable_digest(context["solution"]),
        "solution": context["solution"],
        "ledger_effect": "none",
    }
    dump_exclusive(PARENT_SOLUTION_PATH, parent_payload)
    face_payload = {
        "schema": "zmd_zero_condition_e069_face_context_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "parent_action": parent_payload["parent_action"],
        "calibration": context["calibration"],
        "generic_sink_space": context["sink_space"],
        "face": summary,
        "selection": selection,
        "ledger_effect": "none",
    }
    dump_exclusive(FACE_CONTEXT_PATH, face_payload)

    if summary["stable_unmatched_components"]:
        verdict = "SIX4_PARENT_FACE_HAS_STABLE_UNMATCHED_COMPONENT"
        decision = "BUILD_TARGETED_SECOND_OBJECT_FRONTIER"
    elif summary["pattern_count"] < 6:
        verdict = "SIX4_PARENT_COMPLETE_FACE_NARROW"
        decision = "BUILD_COMPLETE_FACE_SECOND_OBJECT_FRONTIER"
    else:
        verdict = "SIX4_PARENT_COMPLETE_FACE_BROAD"
        decision = "DERIVE_NARROWER_RELATION_BEFORE_SECOND_OBJECT_SCAN"
    return {
        "schema": "zmd_zero_condition_e069_six4_near_miss_complete_face_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "frozen_near_miss": frozen,
        "parent_solution_path": str(PARENT_SOLUTION_PATH.relative_to(ROOT)),
        "parent_solution_sha256": sha256_file(PARENT_SOLUTION_PATH),
        "face_context_path": str(FACE_CONTEXT_PATH.relative_to(ROOT)),
        "face_context_sha256": sha256_file(FACE_CONTEXT_PATH),
        "calibration": context["calibration"],
        "face": summary,
        "selection": selection,
        "decision": decision,
        "truth_boundary": (
            "E055 first-zero state with only grinder_dense_source_002 moved from "
            "pose 7006 to 6878; corrected target-signature relaxation and complete "
            "qiaoyu-hard objective-one presence face."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E069 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "patterns": result["face"]["pattern_count"],
                    "unmatched": result["face"]["unmatched_components"],
                    "stable": result["face"]["stable_unmatched_components"],
                    "qiaoyu_sinks": result["face"]["qiaoyu_sink_components"],
                    "selected_objects": result["selection"]["selected_object_count"],
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
            "schema": "zmd_zero_condition_e069_six4_near_miss_complete_face_failure_v1",
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
