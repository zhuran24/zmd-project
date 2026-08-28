#!/usr/bin/env python3
"""E068: final cached fourth-action discriminator for the pole lineage."""

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
import time
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E068_final_cached_fourth_action/run-002"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
ACTION_RECORDS_PATH = OUT / "ACTION_RECORDS.json"
CHUNK_DIR = OUT / "chunks"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = EXPERIMENT_ROOT / "E062_one_object_tradeoff_atlas/run_e062.py"
E063_RUNNER = (
    EXPERIMENT_ROOT / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E066_RUNNER = EXPERIMENT_ROOT / "E066_pair_face_atlas/run_e066.py"
E067_RUNNER = (
    EXPERIMENT_ROOT / "E067_complementary_narrow_face_pairs/run_e067.py"
)

E063_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E063_pole_conditioned_second_object_frontier/run-008"
)
E063_RESULT = E063_RUN / "RESULT.json"
E063_MANIFEST = E063_RUN / "CANDIDATE_MANIFEST.json"
E066_RUN = ROOT / "research_lab/local/zero_condition/E066_pair_face_atlas/run-001"
E066_RESULT = E066_RUN / "RESULT.json"
E066_ATLAS = E066_RUN / "PAIR_FACE_ATLAS.json"
E067_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E067_complementary_narrow_face_pairs/run-001"
)
E067_RESULT = E067_RUN / "RESULT.json"
E067_PAIR_RECORDS = E067_RUN / "PAIR_RECORDS.json"

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e068_source_cache_v2",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "294000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E066_RUNNER: "a1780e08b09968ee0f25d6ac865a22d9b467637cc9831bb88290242eefd19371",
    E067_RUNNER: "10116d0c2d38b877654f027c179039d59926abb980e6b4e88d31b37bbbac4ee3",
    E063_RESULT: "1dff594f92d2475ae7202735e3f65b442fda884eaa479496808c9cfb4b6b5d1b",
    E063_MANIFEST: "76da60b106d30382381adefa7617f249ed4b6def5cb8118b9fd0d31a9c98db3c",
    E066_RESULT: "e0051e92c4b40515c759cb52779dee7287b24bd8c1c4e2a32017ae69d55425d8",
    E066_ATLAS: "5be751c9a02bfd117cb9fb98e63d6d95ec17cc75c895333a4a8549c02294383e",
    E067_RESULT: "91ee4a043ca4000db37bbbd03792ac8fcb16ff4d31201e63b600597b423c9254",
    E067_PAIR_RECORDS: "fa8b8850ea5ed63f17cac12d07e1e732a2fcb09c2cf03051aebfe20c4d2f2de6",
}

EXPECTED_OBJECTIVE_ONE_ACTIONS = 780
EXPECTED_REPRESENTATIVE_PAIR = 27
EXPECTED_REPRESENTATIVE_LEFT = 596
EXPECTED_REPRESENTATIVE_RIGHT = 729
TARGET_UNMATCHED_COMPONENTS = (1, 4, 8, 12)
TARGET_QIAOYU_SINKS = (15,)
EXPECTED_TARGET_CLASS_FREQUENCY = 16
CHUNK_SIZE = 100
MAX_MATERIALIZED_ZERO = 5


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


def dump_or_validate(path: Path, value: Any) -> None:
    payload = encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"checkpoint byte drift: {path}")
        return
    with path.open("xb") as handle:
        handle.write(payload)
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
        raise RuntimeError(f"run E068 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E068 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"E068 requires a clean tracked worktree: {tracked_status}")
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
    if load_json(E063_RESULT).get("verdict") != (
        "POLE_CONDITIONED_SECOND_OBJECT_SATURATES_AT_ONE"
    ):
        raise RuntimeError("E068 E063 verdict drift")
    if load_json(E066_RESULT).get("verdict") != "PAIR_FACES_NARROW_BUT_NOT_SINGLETON":
        raise RuntimeError("E068 E066 verdict drift")
    if load_json(E067_RESULT).get("verdict") != "TRIPLE_FACE_NARROWS_BELOW_FIVE":
        raise RuntimeError("E068 E067 verdict drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": git_output("branch", "--show-current"),
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "tracked_status": tracked_status,
    }


def representative_pair() -> dict[str, Any]:
    payload = load_json(E067_PAIR_RECORDS)
    records = [
        dict(row)
        for row in payload["records"]
        if row.get("admission_status") == "ADMITTED"
        and row.get("complete_objective_one_face") is not None
        and int(row["complete_objective_one_face"]["pattern_count"]) == 4
    ]
    class_counts: Counter[tuple[tuple[int, ...], tuple[int, ...]]] = Counter()
    for row in records:
        face = row["complete_objective_one_face"]
        key = (
            tuple(int(value) for value in face["unmatched_components"]),
            tuple(int(value) for value in face["qiaoyu_sink_components"]),
        )
        class_counts[key] += 1
    target = (TARGET_UNMATCHED_COMPONENTS, TARGET_QIAOYU_SINKS)
    if class_counts[target] != EXPECTED_TARGET_CLASS_FREQUENCY:
        raise RuntimeError(f"E068 target class frequency drift: {class_counts[target]}")
    maximum = max(class_counts.values())
    maxima = [key for key, count in class_counts.items() if count == maximum]
    if maxima != [target]:
        raise RuntimeError(f"E068 target class is not unique maximum: {maxima}")
    candidates = [
        row
        for row in records
        if (
            tuple(row["complete_objective_one_face"]["unmatched_components"]),
            tuple(row["complete_objective_one_face"]["qiaoyu_sink_components"]),
        )
        == target
    ]
    selected = min(
        candidates,
        key=lambda row: (
            int(row["occupied_symmetric_difference"]),
            int(row["pair_index"]),
        ),
    )
    if (
        int(selected["pair_index"]) != EXPECTED_REPRESENTATIVE_PAIR
        or int(selected["left_candidate_index"]) != EXPECTED_REPRESENTATIVE_LEFT
        or int(selected["right_candidate_index"]) != EXPECTED_REPRESENTATIVE_RIGHT
    ):
        raise RuntimeError(f"E068 representative selection drift: {selected}")
    return {
        "selection_rule": (
            "unique most frequent four-pattern class, then minimum occupied "
            "symmetric difference and lowest pair index"
        ),
        "class_frequency": int(class_counts[target]),
        "class_counts": [
            {
                "unmatched_components": list(key[0]),
                "qiaoyu_sink_components": list(key[1]),
                "count": int(count),
            }
            for key, count in sorted(class_counts.items())
        ],
        "record": selected,
    }


def load_objective_one_specs(e066: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    objective_one, evidence = e066.load_e063_records()
    if len(objective_one) != EXPECTED_OBJECTIVE_ONE_ACTIONS:
        raise RuntimeError(f"E068 objective-one action drift: {len(objective_one)}")
    manifest = load_json(E063_MANIFEST)
    by_index = {
        int(row["candidate_index"]): dict(row) for row in manifest["candidates"]
    }
    specs = [by_index[index] for index in sorted(objective_one)]
    return specs, evidence


def action_delta(
    *,
    e063: Any,
    e061: Any,
    e067: Any,
    context: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    child = e063.reconstruct_candidate(
        e061=e061,
        parent_base=context["parent_base"],
        spec=spec,
    )["solution"]
    return e067.delta_from_parent(
        parent=context["solution"],
        child=child,
        candidate_index=int(spec["candidate_index"]),
    )


def merge_many(
    *,
    context: Mapping[str, Any],
    deltas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    parent = context["solution"]
    combined: dict[str, dict[str, Any]] = {}
    for delta in deltas:
        for key, change_value in delta["changes"].items():
            change = dict(change_value)
            if json_safe(change["before"]) != json_safe(parent.get(key)):
                return {
                    "status": "PARENT_IDENTITY_MISMATCH",
                    "conflict_key": str(key),
                    "solution": None,
                    "change_keys": sorted(combined),
                }
            existing = combined.get(str(key))
            if existing is None:
                combined[str(key)] = change
            elif json_safe(existing) != json_safe(change):
                return {
                    "status": "CONFLICTING_WRITE",
                    "conflict_key": str(key),
                    "solution": None,
                    "change_keys": sorted(combined),
                }
    solution = {str(key): dict(value) for key, value in parent.items()}
    for key, change in sorted(combined.items()):
        after = change["after"]
        if after is None:
            solution.pop(key, None)
        else:
            solution[key] = dict(after)
    mandatory_count = sum(
        bool(row.get("is_mandatory")) for row in solution.values()
    )
    pole_count = sum(
        str(row.get("facility_type")) == "power_pole"
        for row in solution.values()
    )
    if mandatory_count != 266 or pole_count != 53:
        return {
            "status": "CARDINALITY_INVALID",
            "mandatory_count": mandatory_count,
            "pole_count": pole_count,
            "solution": None,
            "change_keys": sorted(combined),
            "delta_digest": stable_digest(combined),
        }
    base = context["base"]
    try:
        occupied, _owners = base["e014"].base_occupancy(
            solution,
            base["inputs"]["pools"],
        )
    except RuntimeError as exc:
        return {
            "status": "OVERLAP_INVALID",
            "detail": str(exc),
            "solution": None,
            "change_keys": sorted(combined),
            "delta_digest": stable_digest(combined),
        }
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row.get("facility_type")) == "power_pole"
    }
    if not base["e014"].all_powered_facilities_covered(
        solution=solution,
        selected_poles=selected_poles,
        powered_templates=base["power"]["powered_templates"],
        coverers=base["power"]["coverers"],
    ):
        return {
            "status": "POWER_INVALID",
            "solution": None,
            "change_keys": sorted(combined),
            "delta_digest": stable_digest(combined),
        }
    return {
        "status": "ADMITTED",
        "solution": solution,
        "occupied_cell_count": len(occupied),
        "selected_poles": sorted(selected_poles),
        "change_keys": sorted(combined),
        "delta_digest": stable_digest(combined),
        "solution_digest": stable_digest(solution),
    }


def reconstruct_representative(
    *,
    e063: Any,
    e061: Any,
    e062: Any,
    e066: Any,
    e067: Any,
    context: Mapping[str, Any],
    specs_by_index: Mapping[int, Mapping[str, Any]],
    representative: Mapping[str, Any],
) -> dict[str, Any]:
    record = representative["record"]
    left_spec = specs_by_index[int(record["left_candidate_index"])]
    right_spec = specs_by_index[int(record["right_candidate_index"])]
    left_delta = action_delta(
        e063=e063,
        e061=e061,
        e067=e067,
        context=context,
        spec=left_spec,
    )
    right_delta = action_delta(
        e063=e063,
        e061=e061,
        e067=e067,
        context=context,
        spec=right_spec,
    )
    merged = merge_many(
        context=context,
        deltas=(left_delta, right_delta),
    )
    if merged["status"] != "ADMITTED" or merged["solution"] is None:
        raise RuntimeError(f"E068 representative merge rejected: {merged}")
    evaluation = e067.evaluate_solution(
        e063=e063,
        e061=e061,
        e062=e062,
        e066=e066,
        context=context,
        solution=merged["solution"],
        pair_index=EXPECTED_REPRESENTATIVE_PAIR,
        has_six4_body_change=True,
    )
    expected_face = record["complete_objective_one_face"]
    if (
        evaluation["directional"].get("status") != "OPTIMAL"
        or int(evaluation["directional"].get("objective", -1)) != 1
        or stable_digest(evaluation["complete_objective_one_face"])
        != stable_digest(expected_face)
    ):
        raise RuntimeError(
            f"E068 representative face calibration drift: {evaluation}"
        )
    return {
        "left_spec": left_spec,
        "right_spec": right_spec,
        "left_delta": left_delta,
        "right_delta": right_delta,
        "merged": merged,
        "evaluation": evaluation,
        "source_ids": {
            str(left_spec["source_instance_id"]),
            str(right_spec["source_instance_id"]),
        },
    }


def chunk_path(index: int) -> Path:
    return CHUNK_DIR / f"CHUNK_{index:03d}.json"


def compact_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_index": int(spec["candidate_index"]),
        "source_instance_id": str(spec["source_instance_id"]),
        "facility_type": str(spec["facility_type"]),
        "operation_type": str(spec.get("operation_type", "")),
        "current_pose_idx": int(spec["current_pose_idx"]),
        "replacement_pose_idx": int(spec["replacement_pose_idx"]),
        "replacement_pose_id": str(spec["replacement_pose_id"]),
        "same_footprint": bool(spec["same_footprint"]),
        "occupied_symmetric_difference": int(
            spec["occupied_symmetric_difference"]
        ),
    }


def scan_actions(
    *,
    e063: Any,
    e061: Any,
    e062: Any,
    e066: Any,
    e067: Any,
    context: Mapping[str, Any],
    representative_state: Mapping[str, Any],
    candidate_specs: Sequence[Mapping[str, Any]],
    runner_sha256: str,
) -> list[dict[str, Any]]:
    left_delta = representative_state["left_delta"]
    right_delta = representative_state["right_delta"]
    used_sources = set(representative_state["source_ids"])
    representative_digest = stable_digest(
        {
            "left": int(representative_state["left_spec"]["candidate_index"]),
            "right": int(representative_state["right_spec"]["candidate_index"]),
            "face": representative_state["evaluation"][
                "complete_objective_one_face"
            ],
        }
    )
    all_records: list[dict[str, Any]] = []
    for chunk_index, start in enumerate(
        range(0, len(candidate_specs), CHUNK_SIZE), 1
    ):
        specs = [dict(row) for row in candidate_specs[start : start + CHUNK_SIZE]]
        path = chunk_path(chunk_index)
        spec_digest = stable_digest([compact_spec(row) for row in specs])
        if path.exists():
            payload = load_json(path)
            if str(payload.get("runner_sha256")) != runner_sha256:
                raise RuntimeError(f"stale E068 chunk runner: {path}")
            if str(payload.get("spec_digest")) != spec_digest:
                raise RuntimeError(f"stale E068 chunk specs: {path}")
            if str(payload.get("representative_digest")) != representative_digest:
                raise RuntimeError(f"stale E068 representative: {path}")
        else:
            records: list[dict[str, Any]] = []
            started = time.monotonic()
            for local_index, spec in enumerate(specs, 1):
                candidate_index = int(spec["candidate_index"])
                source_id = str(spec["source_instance_id"])
                record: dict[str, Any] = {
                    **compact_spec(spec),
                    "scan_index": start + local_index,
                }
                if candidate_index in {
                    EXPECTED_REPRESENTATIVE_LEFT,
                    EXPECTED_REPRESENTATIVE_RIGHT,
                }:
                    record["admission_status"] = "REPRESENTATIVE_ACTION"
                    records.append(record)
                    continue
                if source_id in used_sources:
                    record["admission_status"] = "SAME_SOURCE"
                    records.append(record)
                    continue
                delta = action_delta(
                    e063=e063,
                    e061=e061,
                    e067=e067,
                    context=context,
                    spec=spec,
                )
                merged = merge_many(
                    context=context,
                    deltas=(left_delta, right_delta, delta),
                )
                record["admission_status"] = str(merged["status"])
                record["delta_digest"] = str(merged.get("delta_digest", ""))
                record["change_keys"] = list(merged.get("change_keys", []))
                if merged["status"] == "ADMITTED" and merged["solution"] is not None:
                    evaluation = e067.evaluate_solution(
                        e063=e063,
                        e061=e061,
                        e062=e062,
                        e066=e066,
                        context=context,
                        solution=merged["solution"],
                        pair_index=680000 + candidate_index,
                        has_six4_body_change=True,
                    )
                    record.update(evaluation)
                records.append(record)
                if (
                    local_index % 20 == 0
                    or record.get("directional", {}).get("objective") == 0
                ):
                    print(
                        json.dumps(
                            {
                                "event": "E068_PROGRESS",
                                "chunk": chunk_index,
                                "action": start + local_index,
                                "action_total": len(candidate_specs),
                                "candidate_index": candidate_index,
                                "admission": record["admission_status"],
                                "status": record.get("directional", {}).get(
                                    "status"
                                ),
                                "objective": record.get("directional", {}).get(
                                    "objective"
                                ),
                                "face_width": (
                                    record.get("complete_objective_one_face") or {}
                                ).get("unmatched_component_count"),
                                "at_utc": utc_now(),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
            payload = {
                "schema": "zmd_zero_condition_e068_chunk_v1",
                "created_at_utc": utc_now(),
                "authority": "research_only_noncertified",
                "runner_sha256": runner_sha256,
                "representative_digest": representative_digest,
                "chunk_index": chunk_index,
                "candidate_start_index": start + 1,
                "candidate_count": len(specs),
                "spec_digest": spec_digest,
                "elapsed_seconds": time.monotonic() - started,
                "records": records,
                "ledger_effect": "none",
            }
            dump_exclusive(path, payload)
        all_records.extend(payload["records"])
    if len(all_records) != len(candidate_specs):
        raise RuntimeError(
            f"E068 record coverage drift: {len(all_records)} != {len(candidate_specs)}"
        )
    return all_records


def materialize_zero_states(
    *,
    e063: Any,
    e061: Any,
    e067: Any,
    context: Mapping[str, Any],
    representative_state: Mapping[str, Any],
    specs_by_index: Mapping[int, Mapping[str, Any]],
    zero_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    selected = sorted(
        zero_records,
        key=lambda row: (
            int(row["occupied_symmetric_difference"]),
            str(row["facility_type"]),
            int(row["candidate_index"]),
        ),
    )[:MAX_MATERIALIZED_ZERO]
    for rank, record in enumerate(selected, 1):
        spec = specs_by_index[int(record["candidate_index"])]
        delta = action_delta(
            e063=e063,
            e061=e061,
            e067=e067,
            context=context,
            spec=spec,
        )
        merged = merge_many(
            context=context,
            deltas=(
                representative_state["left_delta"],
                representative_state["right_delta"],
                delta,
            ),
        )
        if merged["status"] != "ADMITTED" or merged["solution"] is None:
            raise RuntimeError(f"E068 zero rematerialization drift: {record}")
        path = OUT / f"ZERO_CANDIDATE_{rank:02d}.json"
        payload = {
            "schema": "zmd_zero_condition_e068_zero_candidate_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "rank": rank,
            "representative_pair": {
                "left_candidate_index": EXPECTED_REPRESENTATIVE_LEFT,
                "right_candidate_index": EXPECTED_REPRESENTATIVE_RIGHT,
            },
            "fourth_action": compact_spec(spec),
            "signature_result": record,
            "solution": merged["solution"],
            "ledger_effect": "none",
        }
        dump_exclusive(path, payload)
        output.append(
            {
                "rank": rank,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "candidate_index": int(spec["candidate_index"]),
            }
        )
    return output


def run() -> dict[str, Any]:
    identity = verify_identity()
    e061 = import_module("zmd_e068_e061", E061_RUNNER)
    e062 = import_module("zmd_e068_e062", E062_RUNNER)
    e063 = import_module("zmd_e068_e063", E063_RUNNER)
    e066 = import_module("zmd_e068_e066", E066_RUNNER)
    e067 = import_module("zmd_e068_e067", E067_RUNNER)
    direct_origins = [
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e063, E063_RUNNER),
        audit_module(e066, E066_RUNNER),
        audit_module(e067, E067_RUNNER),
    ]
    context = e067.reconstruct_context(e063, e061, e062)
    nested_origins = audit_nested_modules(
        (
            "zmd_e068_",
            "zmd_e061_",
            "zmd_e062_",
            "zmd_e063_",
            "zmd_e066_",
            "zmd_e067_",
        )
    )
    specs, e063_evidence = load_objective_one_specs(e066)
    specs_by_index = {
        int(row["candidate_index"]): dict(row) for row in specs
    }
    representative = representative_pair()
    representative_state = reconstruct_representative(
        e063=e063,
        e061=e061,
        e062=e062,
        e066=e066,
        e067=e067,
        context=context,
        specs_by_index=specs_by_index,
        representative=representative,
    )
    records = scan_actions(
        e063=e063,
        e061=e061,
        e062=e062,
        e066=e066,
        e067=e067,
        context=context,
        representative_state=representative_state,
        candidate_specs=specs,
        runner_sha256=str(identity["runner_sha256"]),
    )
    records_payload = {
        "schema": "zmd_zero_condition_e068_action_records_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "representative": representative,
        "record_count": len(records),
        "records": records,
        "ledger_effect": "none",
    }
    dump_exclusive(ACTION_RECORDS_PATH, records_payload)

    admitted = [row for row in records if row["admission_status"] == "ADMITTED"]
    status_counts = Counter(str(row["admission_status"]) for row in records)
    objective_distribution: Counter[int] = Counter()
    face_width_distribution: Counter[int] = Counter()
    zero_records: list[dict[str, Any]] = []
    one_records: list[dict[str, Any]] = []
    nonterminal: list[dict[str, Any]] = []
    stable: list[dict[str, Any]] = []
    for row in admitted:
        directional = row.get("directional", {})
        objective = directional.get("objective")
        if objective is not None:
            objective_distribution[int(objective)] += 1
            if int(objective) == 0:
                zero_records.append(row)
            elif int(objective) == 1:
                one_records.append(row)
                face = row.get("complete_objective_one_face") or {}
                if face:
                    face_width_distribution[
                        int(face["unmatched_component_count"])
                    ] += 1
                    if face.get("stable_unmatched_component") is not None:
                        stable.append(row)
        elif directional.get("status") not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
            nonterminal.append(row)

    materialized_zero = materialize_zero_states(
        e063=e063,
        e061=e061,
        e067=e067,
        context=context,
        representative_state=representative_state,
        specs_by_index=specs_by_index,
        zero_records=zero_records,
    )
    if zero_records:
        verdict = "FINAL_CACHED_FOURTH_ACTION_ZERO_CANDIDATES"
        decision = "VALIDATE_ZERO_IN_FULL_CONDITIONAL_BINDING"
    elif nonterminal:
        verdict = "FINAL_CACHED_FOURTH_ACTION_NONTERMINAL"
        decision = "CONTINUE_ONLY_NONTERMINAL_FOURTH_ACTIONS"
    else:
        verdict = "POLE_LINEAGE_EXHAUSTED_WITHOUT_TWO_ZERO"
        decision = "SWITCH_TO_DISTINCT_SIX4_NEAR_MISS_PARENT"

    ranked_pool = zero_records or stable or one_records
    ranked = sorted(
        ranked_pool,
        key=lambda row: (
            int(
                (row.get("complete_objective_one_face") or {}).get(
                    "unmatched_component_count", 10**9
                )
            ),
            int(
                (row.get("complete_objective_one_face") or {}).get(
                    "pattern_count", 10**9
                )
            ),
            int(row["occupied_symmetric_difference"]),
            str(row["facility_type"]),
            int(row["candidate_index"]),
        ),
    )[:50]
    return {
        "schema": "zmd_zero_condition_e068_final_cached_fourth_action_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "identity": identity,
        "module_origin_audit": {
            "direct": direct_origins,
            "nested": nested_origins,
        },
        "e063_evidence": e063_evidence,
        "representative": representative,
        "representative_face": representative_state["evaluation"][
            "complete_objective_one_face"
        ],
        "objective_one_action_count": len(specs),
        "action_records_path": str(ACTION_RECORDS_PATH.relative_to(ROOT)),
        "action_records_sha256": sha256_file(ACTION_RECORDS_PATH),
        "admission_status_counts": dict(sorted(status_counts.items())),
        "admitted_count": len(admitted),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_distribution.items())
        },
        "face_width_distribution": {
            str(key): value for key, value in sorted(face_width_distribution.items())
        },
        "zero_candidate_count": len(zero_records),
        "stable_single_component_count": len(stable),
        "nonterminal_count": len(nonterminal),
        "selected_candidates": ranked,
        "nonterminal_candidates": nonterminal,
        "materialized_zero_candidates": materialized_zero,
        "decision": decision,
        "truth_boundary": (
            "E055 first-zero state plus E063 pole move, deterministic E067 pair "
            "27, and at most one additional cached E063 objective-one action; "
            "corrected target-signature relaxation only."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E068 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "representative_pair": result["representative"]["record"][
                        "pair_index"
                    ],
                    "admitted": result["admitted_count"],
                    "distribution": result["objective_distribution"],
                    "face_widths": result["face_width_distribution"],
                    "zero": result["zero_candidate_count"],
                    "stable": result["stable_single_component_count"],
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
            "schema": "zmd_zero_condition_e068_final_cached_fourth_action_failure_v1",
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
