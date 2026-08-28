#!/usr/bin/env python3
"""E066: enumerate complete objective-one faces for E063 pair states."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "research_lab/local/zero_condition/E066_pair_face_atlas/run-001"
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ATLAS_PATH = OUT / "PAIR_FACE_ATLAS.json"
CHUNK_DIR = OUT / "chunks"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E063_RUNNER = (
    EXPERIMENT_ROOT
    / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E061_RUNNER = (
    EXPERIMENT_ROOT
    / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = (
    EXPERIMENT_ROOT
    / "E062_one_object_tradeoff_atlas/run_e062.py"
)
E063_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E063_pole_conditioned_second_object_frontier/run-008"
)
E063_RESULT = E063_RUN / "RESULT.json"
E063_MANIFEST = E063_RUN / "CANDIDATE_MANIFEST.json"
E065_E062_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E065_source_stable_replay_materialization/run-001/e062-source/RESULT.json"
)

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e066_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "292000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E063_RESULT: "1dff594f92d2475ae7202735e3f65b442fda884eaa479496808c9cfb4b6b5d1b",
    E063_MANIFEST: "76da60b106d30382381adefa7617f249ed4b6def5cb8118b9fd0d31a9c98db3c",
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E065_E062_RESULT: "8ddff564f9359da582bbb212d77a736c2651294c8d335d35c4104b73c0b7d361",
}

EXPECTED_E063_CANDIDATE_COUNT = 858
EXPECTED_OBJECTIVE_ONE_COUNT = 780
EXPECTED_PARENT_PATTERN_COUNT = 6
EXPECTED_PARENT_UNMATCHED_COMPONENT_COUNT = 6
CHUNK_SIZE = 50
MAX_SELECTED_CANDIDATES = 12
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


def dump_exclusive(path: Path, value: Any) -> None:
    encoded = (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
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
        raise RuntimeError(
            f"foreign functions loaded for {expected_path}: {foreign[:10]}"
        )
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
        if path.suffix == ".pyc":
            source = Path(importlib.util.source_from_cache(str(path))).resolve()
        else:
            source = path
        rows.append(audit_module(module, source))
    return rows


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E066 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E066 must run on research/main")
    tracked_status = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked_status:
        raise RuntimeError(f"E066 requires a clean tracked worktree: {tracked_status}")
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

    result = load_json(E063_RESULT)
    if result.get("verdict") != "POLE_CONDITIONED_SECOND_OBJECT_SATURATES_AT_ONE":
        raise RuntimeError("E066 E063 verdict drift")
    if (
        int(result.get("candidate_count", -1)) != EXPECTED_E063_CANDIDATE_COUNT
        or int(result.get("one_candidate_count", -1))
        != EXPECTED_OBJECTIVE_ONE_COUNT
        or int(result.get("zero_candidate_count", -1)) != 0
        or int(result.get("nonterminal_count", -1)) != 0
    ):
        raise RuntimeError("E066 E063 frontier count drift")
    if str(result["identity"]["runner_sha256"]) != EXPECTED_HASHES[E063_RUNNER]:
        raise RuntimeError("E066 E063 executable identity drift")
    if str(result["manifest_sha256"]) != EXPECTED_HASHES[E063_MANIFEST]:
        raise RuntimeError("E066 E063 manifest identity drift")

    replay = load_json(E065_E062_RESULT)
    if replay.get("verdict") != "ONE_OBJECT_TRADEOFF_NEAR_MISSES_FOUND":
        raise RuntimeError("E066 E065/E062 trigger drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
    }


def load_e063_records() -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    result = load_json(E063_RESULT)
    records: dict[int, dict[str, Any]] = {}
    chunk_rows: list[dict[str, Any]] = []
    for path in sorted((E063_RUN / "chunks").glob("CHUNK_*.json")):
        payload = load_json(path)
        if str(payload.get("runner_sha256")) != EXPECTED_HASHES[E063_RUNNER]:
            raise RuntimeError(f"E063 chunk runner drift: {path}")
        chunk_rows.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "candidate_count": int(payload["candidate_count"]),
                "spec_digest": str(payload["spec_digest"]),
            }
        )
        for row in payload["records"]:
            index = int(row["candidate_index"])
            if index in records:
                raise RuntimeError(f"duplicate E063 candidate record: {index}")
            records[index] = dict(row)
    if len(records) != EXPECTED_E063_CANDIDATE_COUNT:
        raise RuntimeError(f"E063 chunk coverage drift: {len(records)}")
    one = {
        index: row
        for index, row in records.items()
        if row["directional"].get("objective") == 1
        and row["directional"].get("status") == "OPTIMAL"
    }
    if len(one) != EXPECTED_OBJECTIVE_ONE_COUNT:
        raise RuntimeError(f"E063 objective-one record drift: {len(one)}")
    return one, {
        "result": {
            "path": str(E063_RESULT.relative_to(ROOT)),
            "sha256": sha256_file(E063_RESULT),
        },
        "manifest": {
            "path": str(E063_MANIFEST.relative_to(ROOT)),
            "sha256": sha256_file(E063_MANIFEST),
        },
        "chunks": chunk_rows,
        "objective_one_count": len(one),
        "parent_directional_face": result["parent_directional_face"],
    }


def reconstruct_context(e063: Any, e061: Any, e062: Any) -> dict[str, Any]:
    context = e063.parent_context(e061, e062)
    context["mode_map"] = e061.modes_by_footprint(
        context["base"]["inputs"]["pools"]
    )
    context["fixed_descriptors"] = e061.raw_descriptors(
        bodies=e061.body_rows(
            context["solution"],
            context["base"]["inputs"]["pools"],
            context["base"]["e014"],
        ),
        mode_map=context["mode_map"],
        pools=context["base"]["inputs"]["pools"],
        enumerate_patterns=context["base"]["enumerate_patterns"],
    )
    expected_face = load_json(E063_RESULT)["parent_directional_face"]
    if stable_digest(context["directional_face"]) != stable_digest(expected_face):
        raise RuntimeError("E066 reconstructed parent face drift")
    return context


def normalize_patterns(face: Mapping[str, Any]) -> list[dict[str, Any]]:
    patterns = [
        {
            "qiaoyu_sink_component": int(row["qiaoyu_sink_component"]),
            "fine_source_components": sorted(
                int(value) for value in row["fine_source_components"]
            ),
            "fine_sink_components": sorted(
                int(value) for value in row["fine_sink_components"]
            ),
            "source_only_components": sorted(
                int(value) for value in row["source_only_components"]
            ),
            "sink_only_components": sorted(
                int(value) for value in row["sink_only_components"]
            ),
        }
        for row in face["patterns"]
    ]
    patterns.sort(
        key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"))
    )
    invalid = [
        row
        for row in patterns
        if len(row["source_only_components"])
        + len(row["sink_only_components"])
        != 1
    ]
    if invalid:
        raise RuntimeError(
            "E066 objective-one face contains a non-unit mismatch pattern: "
            f"{invalid[:3]}"
        )
    return patterns


def face_summary(face: Mapping[str, Any]) -> dict[str, Any]:
    patterns = normalize_patterns(face)
    unmatched = sorted(
        {
            int(value)
            for row in patterns
            for key in ("source_only_components", "sink_only_components")
            for value in row[key]
        }
    )
    source_only = sorted(
        {
            int(value)
            for row in patterns
            for value in row["source_only_components"]
        }
    )
    sink_only = sorted(
        {
            int(value)
            for row in patterns
            for value in row["sink_only_components"]
        }
    )
    qiaoyu_sinks = sorted(
        {int(row["qiaoyu_sink_component"]) for row in patterns}
    )
    orientations = sorted(
        {
            "source_only" if row["source_only_components"] else "sink_only"
            for row in patterns
        }
    )
    stable_component = None
    stable_orientation = None
    if len(unmatched) == 1 and len(orientations) == 1:
        stable_component = unmatched[0]
        stable_orientation = orientations[0]
    return {
        "status": str(face["status"]),
        "complete": bool(face["complete"]),
        "pattern_count": len(patterns),
        "patterns": patterns,
        "face_digest": stable_digest(patterns),
        "unmatched_components": unmatched,
        "unmatched_component_count": len(unmatched),
        "source_only_component_union": source_only,
        "sink_only_component_union": sink_only,
        "qiaoyu_sink_components": qiaoyu_sinks,
        "qiaoyu_sink_component_count": len(qiaoyu_sinks),
        "orientations": orientations,
        "stable_unmatched_component": stable_component,
        "stable_unmatched_orientation": stable_orientation,
    }


def candidate_face(
    *,
    e063: Any,
    e061: Any,
    e062: Any,
    context: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    alternative = e063.reconstruct_candidate(
        e061=e061,
        parent_base=context["parent_base"],
        spec=spec,
    )
    solution = alternative["solution"]
    base = context["base"]
    routing_context = base["build_routing_context"](
        solution,
        base["inputs"]["pools"],
        70,
        70,
    )
    if str(spec["facility_type"]) == SIX4 and not bool(spec["same_footprint"]):
        descriptors = e061.dynamic_descriptors(
            candidate=solution,
            base=base,
            mode_map=context["mode_map"],
        )
    else:
        descriptors = context["fixed_descriptors"]
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
    face = e063.enumerate_directional_face(
        operation_counts=e061.OPERATION_COUNTS,
        e062=e062,
        options=options,
        sink_space=sink_space,
        optimum=1,
        random_seed=660000 + int(spec["candidate_index"]),
    )
    summary = face_summary(face)
    return {
        "candidate_index": int(spec["candidate_index"]),
        "source_instance_id": str(spec["source_instance_id"]),
        "facility_type": str(spec["facility_type"]),
        "operation_type": str(spec["operation_type"]),
        "current_pose_idx": int(spec["current_pose_idx"]),
        "replacement_pose_idx": int(spec["replacement_pose_idx"]),
        "replacement_pose_id": str(spec["replacement_pose_id"]),
        "same_footprint": bool(spec["same_footprint"]),
        "occupied_symmetric_difference": int(
            spec["occupied_symmetric_difference"]
        ),
        "selection_reasons": list(spec["selection_reasons"]),
        "face": summary,
    }


def chunk_path(index: int) -> Path:
    return CHUNK_DIR / f"FACE_CHUNK_{index:03d}.json"


def enumerate_faces(
    *,
    e063: Any,
    e061: Any,
    e062: Any,
    context: Mapping[str, Any],
    specs: Sequence[Mapping[str, Any]],
    runner_sha256: str,
) -> list[dict[str, Any]]:
    all_records: list[dict[str, Any]] = []
    for start in range(0, len(specs), CHUNK_SIZE):
        chunk_index = start // CHUNK_SIZE + 1
        rows = [dict(value) for value in specs[start : start + CHUNK_SIZE]]
        digest = stable_digest(rows)
        path = chunk_path(chunk_index)
        if path.exists():
            payload = load_json(path)
            if (
                str(payload.get("runner_sha256")) != runner_sha256
                or str(payload.get("spec_digest")) != digest
                or int(payload.get("candidate_count", -1)) != len(rows)
            ):
                raise RuntimeError(f"stale E066 face chunk: {path}")
        else:
            started = time.monotonic()
            records: list[dict[str, Any]] = []
            for spec in rows:
                record = candidate_face(
                    e063=e063,
                    e061=e061,
                    e062=e062,
                    context=context,
                    spec=spec,
                )
                records.append(record)
                processed = start + len(records)
                if processed % 25 == 0:
                    print(
                        json.dumps(
                            {
                                "event": "E066_FACE_PROGRESS",
                                "candidate": processed,
                                "candidate_total": len(specs),
                                "chunk": chunk_index,
                                "pattern_count": record["face"]["pattern_count"],
                                "unmatched_component_count": record["face"][
                                    "unmatched_component_count"
                                ],
                                "at_utc": utc_now(),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
            payload = {
                "schema": "zmd_zero_condition_e066_pair_face_chunk_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "runner_sha256": runner_sha256,
                "chunk_index": chunk_index,
                "candidate_start_index": start + 1,
                "candidate_count": len(rows),
                "spec_digest": digest,
                "elapsed_seconds": time.monotonic() - started,
                "records": records,
                "ledger_effect": "none",
            }
            dump_exclusive(path, payload)
        all_records.extend(payload["records"])
    if len(all_records) != len(specs):
        raise RuntimeError(f"E066 face coverage drift: {len(all_records)}")
    return all_records


def class_atlas(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[str(row["face"]["face_digest"])].append(row)
    classes: list[dict[str, Any]] = []
    for digest, rows in grouped.items():
        first = rows[0]
        facility_counts = Counter(str(row["facility_type"]) for row in rows)
        operation_counts = Counter(str(row["operation_type"]) for row in rows)
        reason_counts: Counter[str] = Counter()
        for row in rows:
            reason_counts.update(str(value) for value in row["selection_reasons"])
        classes.append(
            {
                "face_digest": digest,
                "candidate_count": len(rows),
                "candidate_indices": sorted(int(row["candidate_index"]) for row in rows),
                "pattern_count": int(first["face"]["pattern_count"]),
                "patterns": first["face"]["patterns"],
                "unmatched_components": first["face"]["unmatched_components"],
                "unmatched_component_count": int(
                    first["face"]["unmatched_component_count"]
                ),
                "qiaoyu_sink_components": first["face"]["qiaoyu_sink_components"],
                "qiaoyu_sink_component_count": int(
                    first["face"]["qiaoyu_sink_component_count"]
                ),
                "orientations": first["face"]["orientations"],
                "stable_unmatched_component": first["face"][
                    "stable_unmatched_component"
                ],
                "stable_unmatched_orientation": first["face"][
                    "stable_unmatched_orientation"
                ],
                "facility_type_counts": dict(sorted(facility_counts.items())),
                "operation_type_counts": dict(sorted(operation_counts.items())),
                "selection_reason_counts": dict(sorted(reason_counts.items())),
                "minimum_occupied_symmetric_difference": min(
                    int(row["occupied_symmetric_difference"]) for row in rows
                ),
            }
        )
    classes.sort(
        key=lambda row: (
            int(row["unmatched_component_count"]),
            int(row["pattern_count"]),
            int(row["qiaoyu_sink_component_count"]),
            -int(row["candidate_count"]),
            str(row["face_digest"]),
        )
    )
    return {
        "schema": "zmd_zero_condition_e066_pair_face_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "class_count": len(classes),
        "classes": classes,
        "ledger_effect": "none",
    }


def selected_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_index": int(row["candidate_index"]),
        "source_instance_id": str(row["source_instance_id"]),
        "facility_type": str(row["facility_type"]),
        "operation_type": str(row["operation_type"]),
        "current_pose_idx": int(row["current_pose_idx"]),
        "replacement_pose_idx": int(row["replacement_pose_idx"]),
        "replacement_pose_id": str(row["replacement_pose_id"]),
        "occupied_symmetric_difference": int(row["occupied_symmetric_difference"]),
        "selection_reasons": list(row["selection_reasons"]),
        "face_digest": str(row["face"]["face_digest"]),
        "pattern_count": int(row["face"]["pattern_count"]),
        "unmatched_components": row["face"]["unmatched_components"],
        "unmatched_component_count": int(
            row["face"]["unmatched_component_count"]
        ),
        "qiaoyu_sink_components": row["face"]["qiaoyu_sink_components"],
        "stable_unmatched_component": row["face"]["stable_unmatched_component"],
        "stable_unmatched_orientation": row["face"]["stable_unmatched_orientation"],
    }


def run() -> dict[str, Any]:
    identity = verify_identity()
    objective_one, e063_evidence = load_e063_records()
    manifest = load_json(E063_MANIFEST)
    specs_by_index = {
        int(row["candidate_index"]): dict(row) for row in manifest["candidates"]
    }
    specs = [specs_by_index[index] for index in sorted(objective_one)]

    e063 = import_module("zmd_e066_e063", E063_RUNNER)
    e061 = import_module("zmd_e066_e061", E061_RUNNER)
    e062 = import_module("zmd_e066_e062", E062_RUNNER)
    direct_origins = [
        audit_module(e063, E063_RUNNER),
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
    ]
    context = reconstruct_context(e063, e061, e062)
    nested_origins = audit_nested_modules(
        ("zmd_e066_", "zmd_e061_", "zmd_e062_", "zmd_e063_")
    )

    records = enumerate_faces(
        e063=e063,
        e061=e061,
        e062=e062,
        context=context,
        specs=specs,
        runner_sha256=str(identity["runner_sha256"]),
    )
    nonterminal = [row for row in records if not bool(row["face"]["complete"])]
    complete = [row for row in records if bool(row["face"]["complete"])]
    if len(complete) + len(nonterminal) != EXPECTED_OBJECTIVE_ONE_COUNT:
        raise RuntimeError("E066 result partition drift")

    atlas = class_atlas(complete)
    dump_exclusive(ATLAS_PATH, atlas)

    pattern_distribution = Counter(
        int(row["face"]["pattern_count"]) for row in complete
    )
    union_distribution = Counter(
        int(row["face"]["unmatched_component_count"]) for row in complete
    )
    stable = [
        row
        for row in complete
        if row["face"]["stable_unmatched_component"] is not None
    ]
    narrowing = [
        row
        for row in complete
        if int(row["face"]["pattern_count"]) < EXPECTED_PARENT_PATTERN_COUNT
        or int(row["face"]["unmatched_component_count"])
        < EXPECTED_PARENT_UNMATCHED_COMPONENT_COUNT
    ]
    representatives_unique = sum(
        int(row["face"]["pattern_count"]) == 1 for row in complete
    )

    ranked = sorted(
        stable or narrowing,
        key=lambda row: (
            int(row["face"]["unmatched_component_count"]),
            int(row["face"]["pattern_count"]),
            int(row["face"]["qiaoyu_sink_component_count"]),
            int(row["occupied_symmetric_difference"]),
            str(row["facility_type"]),
            int(row["candidate_index"]),
        ),
    )[:MAX_SELECTED_CANDIDATES]

    if nonterminal:
        verdict = "PAIR_FACE_ATLAS_NONTERMINAL"
        decision = "CONTINUE_NONTERMINAL_PAIR_FACE_ENUMERATION"
    elif stable:
        verdict = "STABLE_SINGLE_COMPONENT_PAIR_FACES_FOUND"
        decision = "BUILD_THIRD_RELATION_FROM_STABLE_COMPONENT"
    elif narrowing:
        verdict = "PAIR_FACES_NARROW_BUT_NOT_SINGLETON"
        decision = "BUILD_THIRD_RELATION_FROM_NARROWEST_FACE_CLASS"
    else:
        verdict = "POLE_PAIR_COMPLETE_FACES_DO_NOT_NARROW"
        decision = "SWITCH_TO_DISTINCT_SIX4_NEAR_MISS_PARENT"

    return {
        "schema": "zmd_zero_condition_e066_pair_face_atlas_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "source_origins": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "e063_evidence": e063_evidence,
        "parent_face": {
            "pattern_count": EXPECTED_PARENT_PATTERN_COUNT,
            "unmatched_components": [1, 4, 8, 12, 22, 26],
            "unmatched_component_count": EXPECTED_PARENT_UNMATCHED_COMPONENT_COUNT,
            "patterns": e063_evidence["parent_directional_face"]["patterns"],
        },
        "candidate_count": len(records),
        "complete_face_count": len(complete),
        "nonterminal_face_count": len(nonterminal),
        "face_class_count": int(atlas["class_count"]),
        "pattern_count_distribution": {
            str(key): value for key, value in sorted(pattern_distribution.items())
        },
        "unmatched_component_count_distribution": {
            str(key): value for key, value in sorted(union_distribution.items())
        },
        "stable_single_component_candidate_count": len(stable),
        "narrowing_candidate_count": len(narrowing),
        "single_pattern_face_count": representatives_unique,
        "selected_candidates": [selected_record(row) for row in ranked],
        "nonterminal_candidates": [
            selected_record(row) for row in nonterminal[:MAX_SELECTED_CANDIDATES]
        ],
        "atlas_path": str(ATLAS_PATH.relative_to(ROOT)),
        "atlas_sha256": sha256_file(ATLAS_PATH),
        "truth_boundary": (
            "Complete qiaoyu-hard fine-mismatch-one terminal-presence faces for "
            "E063's 780 objective-one pair geometries. This is a signature "
            "relaxation and does not establish full binding or routing."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E066 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "candidates": result["candidate_count"],
                    "classes": result["face_class_count"],
                    "stable": result["stable_single_component_candidate_count"],
                    "narrowing": result["narrowing_candidate_count"],
                    "pattern_distribution": result["pattern_count_distribution"],
                    "union_distribution": result[
                        "unmatched_component_count_distribution"
                    ],
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
            "schema": "zmd_zero_condition_e066_pair_face_atlas_failure_v1",
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
