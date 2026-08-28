#!/usr/bin/env python3
"""E067: compose the twelve E066 face-narrowing actions in pairs."""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import importlib.util
import inspect
from itertools import combinations
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
    "E067_complementary_narrow_face_pairs/run-001"
)
RESULT_PATH = OUT / "RESULT.json"
FAILURE_PATH = OUT / "FAILURE.json"
PAIR_RECORDS_PATH = OUT / "PAIR_RECORDS.json"

EXPERIMENT_ROOT = ROOT / "research_lab/campaigns/zero_condition/experiments"
E061_RUNNER = (
    EXPERIMENT_ROOT
    / "E061_all_one_object_signature_frontier/run_e061.py"
)
E062_RUNNER = (
    EXPERIMENT_ROOT
    / "E062_one_object_tradeoff_atlas/run_e062.py"
)
E063_RUNNER = (
    EXPERIMENT_ROOT
    / "E063_pole_conditioned_second_object_frontier/run_e063.py"
)
E066_RUNNER = EXPERIMENT_ROOT / "E066_pair_face_atlas/run_e066.py"
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

EXPECTED_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONPYCACHEPREFIX": "/tmp/zmd_e067_source_cache_v1",
    "EXACT_USE_POSE_BOOL_MASTER": "1",
    "EXACT_USE_PORT_ACTIVE": "1",
    "EXACT_MASTER_HINT_PERSISTENCE": "0",
    "EXACT_MASTER_SEARCH_BRANCHING": "automatic",
    "EXACT_MASTER_RANDOM_SEED": "293000",
    "EXACT_MASTER_CP_SAT_WORKERS": "8",
    "EXACT_BINDING_CP_SAT_WORKERS": "4",
}
EXPECTED_HASHES = {
    E061_RUNNER: "45a9a95eedb22062a7052dc40b81cb32fe39a1e0f6a5d71457b518fd95cda3d5",
    E062_RUNNER: "91770f3ba9a96a3c79bd95c42a4e40b9a540ab537e97079b02f7c57c6fedb67e",
    E063_RUNNER: "e925b4470ecb002701b262c5d8bcfbe88177eb8da373502354174f178f39caf9",
    E066_RUNNER: "a1780e08b09968ee0f25d6ac865a22d9b467637cc9831bb88290242eefd19371",
    E063_RESULT: "1dff594f92d2475ae7202735e3f65b442fda884eaa479496808c9cfb4b6b5d1b",
    E063_MANIFEST: "76da60b106d30382381adefa7617f249ed4b6def5cb8118b9fd0d31a9c98db3c",
    E066_RESULT: "e0051e92c4b40515c759cb52779dee7287b24bd8c1c4e2a32017ae69d55425d8",
    E066_ATLAS: "5be751c9a02bfd117cb9fb98e63d6d95ec17cc75c895333a4a8549c02294383e",
}

EXPECTED_SELECTED_ACTION_COUNT = 12
PARENT_FACE_WIDTH = 5
MAX_MATERIALIZED_ZERO = 5
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


def verify_identity() -> dict[str, Any]:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError(f"run E067 from research root: {Path.cwd()}")
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E067 must run on research/main")
    tracked_status = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked_status:
        raise RuntimeError(f"E067 requires a clean tracked worktree: {tracked_status}")
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
    e066 = load_json(E066_RESULT)
    if (
        e066.get("verdict") != "PAIR_FACES_NARROW_BUT_NOT_SINGLETON"
        or int(e066.get("narrowing_candidate_count", -1))
        != EXPECTED_SELECTED_ACTION_COUNT
        or int(e066.get("stable_single_component_candidate_count", -1)) != 0
    ):
        raise RuntimeError("E067 E066 trigger drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "environment": {key: os.environ.get(key) for key in sorted(EXPECTED_ENV)},
        "checked_hashes": checked,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
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
        raise RuntimeError("E067 reconstructed parent face drift")
    return context


def selected_specs() -> list[dict[str, Any]]:
    result = load_json(E066_RESULT)
    selected = list(result["selected_candidates"])
    if len(selected) != EXPECTED_SELECTED_ACTION_COUNT:
        raise RuntimeError("E067 selected-candidate count drift")
    manifest = load_json(E063_MANIFEST)
    by_index = {
        int(row["candidate_index"]): dict(row) for row in manifest["candidates"]
    }
    specs: list[dict[str, Any]] = []
    for row in selected:
        index = int(row["candidate_index"])
        spec = by_index[index]
        if (
            int(row["pattern_count"]) != PARENT_FACE_WIDTH
            or int(row["unmatched_component_count"]) != PARENT_FACE_WIDTH
            or str(row["source_instance_id"]) != str(spec["source_instance_id"])
            or int(row["replacement_pose_idx"])
            != int(spec["replacement_pose_idx"])
        ):
            raise RuntimeError(f"E067 selected candidate drift: {index}")
        specs.append(spec)
    specs.sort(key=lambda row: int(row["candidate_index"]))
    return specs


def delta_from_parent(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    child: Mapping[str, Mapping[str, Any]],
    candidate_index: int,
) -> dict[str, Any]:
    keys = sorted(set(parent) | set(child))
    changes: dict[str, dict[str, Any]] = {}
    for key in keys:
        before = parent.get(key)
        after = child.get(key)
        if json_safe(before) == json_safe(after):
            continue
        changes[str(key)] = {
            "before": json_safe(before),
            "after": json_safe(after),
        }
    if not changes:
        raise RuntimeError(f"E067 empty action delta: {candidate_index}")
    return {
        "candidate_index": int(candidate_index),
        "changes": changes,
        "change_keys": sorted(changes),
        "delta_digest": stable_digest(changes),
    }


def merge_deltas(
    *,
    parent: Mapping[str, Mapping[str, Any]],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    merged_changes: dict[str, dict[str, Any]] = {}
    for delta in (left, right):
        for key, change in delta["changes"].items():
            expected_before = json_safe(parent.get(key))
            if json_safe(change["before"]) != expected_before:
                return {
                    "status": "PARENT_IDENTITY_MISMATCH",
                    "detail": key,
                }
            existing = merged_changes.get(key)
            if existing is None:
                merged_changes[key] = dict(change)
            elif json_safe(existing["after"]) != json_safe(change["after"]):
                return {
                    "status": "CONFLICTING_WRITE",
                    "detail": key,
                }

    solution = {str(key): dict(value) for key, value in parent.items()}
    for key, change in merged_changes.items():
        after = change["after"]
        if after is None:
            solution.pop(key, None)
        else:
            solution[key] = dict(after)

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

    base = context["base"]
    try:
        occupied, _owners = base["e014"].base_occupancy(
            solution,
            base["inputs"]["pools"],
        )
    except RuntimeError as exc:
        return {"status": "OVERLAP_INVALID", "detail": str(exc)}
    selected_poles = {
        int(row["pose_idx"])
        for row in solution.values()
        if str(row["facility_type"]) == "power_pole"
    }
    if not base["e014"].all_powered_facilities_covered(
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
        "selected_poles": sorted(selected_poles),
        "merged_change_digest": stable_digest(merged_changes),
        "solution_digest": stable_digest(solution),
    }


def evaluate_solution(
    *,
    e063: Any,
    e061: Any,
    e062: Any,
    e066: Any,
    context: Mapping[str, Any],
    solution: Mapping[str, Mapping[str, Any]],
    pair_index: int,
    has_six4_body_change: bool,
) -> dict[str, Any]:
    base = context["base"]
    routing_context = base["build_routing_context"](
        solution,
        base["inputs"]["pools"],
        70,
        70,
    )
    if has_six4_body_change:
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
    directional = e062.solve_qiaoyu_hard(
        options=options,
        sink_space=sink_space,
        random_seed=670000 + pair_index,
    )
    objective = directional.get("objective")
    face = None
    joint_replay = None
    if directional.get("status") in {"OPTIMAL", "FEASIBLE"} and objective == 0:
        joint_replay = e061.solve_signature(
            options=options,
            sink_space=sink_space,
            random_seed=671000 + pair_index,
        )
        if joint_replay.get("status") not in {"OPTIMAL", "FEASIBLE"}:
            raise RuntimeError(
                f"E067 zero did not replay in joint signature model: {pair_index}"
            )
    elif directional.get("status") == "OPTIMAL" and objective == 1:
        complete = e063.enumerate_directional_face(
            operation_counts=e061.OPERATION_COUNTS,
            e062=e062,
            options=options,
            sink_space=sink_space,
            optimum=1,
            random_seed=672000 + pair_index,
        )
        face = e066.face_summary(complete)
    return {
        "directional": json_safe(directional),
        "joint_replay": json_safe(joint_replay),
        "complete_objective_one_face": json_safe(face),
    }


def materialize_zero(
    *,
    records: Sequence[Mapping[str, Any]],
    solutions: Mapping[int, Mapping[str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    selected = sorted(
        records,
        key=lambda row: (
            int(row["occupied_symmetric_difference"]),
            int(row["left_candidate_index"]),
            int(row["right_candidate_index"]),
        ),
    )[:MAX_MATERIALIZED_ZERO]
    output: list[dict[str, Any]] = []
    for rank, row in enumerate(selected, 1):
        pair_index = int(row["pair_index"])
        path = OUT / f"ZERO_TRIPLE_CANDIDATE_{rank:02d}.json"
        payload = {
            "schema": "zmd_zero_condition_e067_zero_triple_candidate_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "rank": rank,
            "pair_record": row,
            "solution": solutions[pair_index],
            "ledger_effect": "none",
        }
        dump_exclusive(path, payload)
        output.append(
            {
                "rank": rank,
                "pair_index": pair_index,
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
    return output


def run() -> dict[str, Any]:
    identity = verify_identity()
    e063 = import_module("zmd_e067_e063", E063_RUNNER)
    e061 = import_module("zmd_e067_e061", E061_RUNNER)
    e062 = import_module("zmd_e067_e062", E062_RUNNER)
    e066 = import_module("zmd_e067_e066", E066_RUNNER)
    source_origins = [
        audit_module(e063, E063_RUNNER),
        audit_module(e061, E061_RUNNER),
        audit_module(e062, E062_RUNNER),
        audit_module(e066, E066_RUNNER),
    ]
    context = reconstruct_context(e063, e061, e062)
    specs = selected_specs()
    parent = context["solution"]

    children: dict[int, Mapping[str, Mapping[str, Any]]] = {}
    deltas: dict[int, dict[str, Any]] = {}
    for spec in specs:
        index = int(spec["candidate_index"])
        alternative = e063.reconstruct_candidate(
            e061=e061,
            parent_base=context["parent_base"],
            spec=spec,
        )
        child = alternative["solution"]
        children[index] = child
        deltas[index] = delta_from_parent(
            parent=parent,
            child=child,
            candidate_index=index,
        )

    pair_records: list[dict[str, Any]] = []
    zero_solutions: dict[int, Mapping[str, Mapping[str, Any]]] = {}
    started = time.monotonic()
    for pair_index, (left, right) in enumerate(combinations(specs, 2), 1):
        left_index = int(left["candidate_index"])
        right_index = int(right["candidate_index"])
        base_record: dict[str, Any] = {
            "pair_index": pair_index,
            "left_candidate_index": left_index,
            "right_candidate_index": right_index,
            "left_source_instance_id": str(left["source_instance_id"]),
            "right_source_instance_id": str(right["source_instance_id"]),
            "left_replacement_pose_idx": int(left["replacement_pose_idx"]),
            "right_replacement_pose_idx": int(right["replacement_pose_idx"]),
        }
        if str(left["source_instance_id"]) == str(right["source_instance_id"]):
            pair_records.append({**base_record, "admission_status": "SAME_SOURCE"})
            continue
        merged = merge_deltas(
            parent=parent,
            left=deltas[left_index],
            right=deltas[right_index],
            context=context,
        )
        if merged["status"] != "ADMITTED":
            pair_records.append(
                {
                    **base_record,
                    "admission_status": str(merged["status"]),
                    "admission_detail": merged.get("detail"),
                }
            )
            continue
        solution = merged["solution"]
        evaluation = evaluate_solution(
            e063=e063,
            e061=e061,
            e062=e062,
            e066=e066,
            context=context,
            solution=solution,
            pair_index=pair_index,
            has_six4_body_change=any(
                str(spec["facility_type"]) == SIX4
                and not bool(spec["same_footprint"])
                for spec in (left, right)
            ),
        )
        old_cells = set(context["routing_context"].occupied_cells)
        new_context = context["base"]["build_routing_context"](
            solution,
            context["base"]["inputs"]["pools"],
            70,
            70,
        )
        new_cells = set(new_context.occupied_cells)
        record = {
            **base_record,
            "admission_status": "ADMITTED",
            "solution_digest": str(merged["solution_digest"]),
            "merged_change_digest": str(merged["merged_change_digest"]),
            "occupied_symmetric_difference": len(old_cells ^ new_cells),
            **evaluation,
        }
        pair_records.append(record)
        if evaluation["directional"].get("objective") == 0:
            zero_solutions[pair_index] = solution
        if pair_index % 10 == 0:
            print(
                json.dumps(
                    {
                        "event": "E067_PROGRESS",
                        "pair": pair_index,
                        "pair_total": 66,
                        "admission": record["admission_status"],
                        "objective": evaluation["directional"].get("objective"),
                        "at_utc": utc_now(),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    dump_exclusive(
        PAIR_RECORDS_PATH,
        {
            "schema": "zmd_zero_condition_e067_pair_records_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "selected_action_count": len(specs),
            "unordered_pair_count": len(pair_records),
            "elapsed_seconds": time.monotonic() - started,
            "records": pair_records,
            "ledger_effect": "none",
        },
    )

    admission_counts = Counter(str(row["admission_status"]) for row in pair_records)
    objective_counts: Counter[int] = Counter()
    nonterminal: list[dict[str, Any]] = []
    zero: list[dict[str, Any]] = []
    stable: list[dict[str, Any]] = []
    narrower: list[dict[str, Any]] = []
    for row in pair_records:
        if row.get("admission_status") != "ADMITTED":
            continue
        directional = row["directional"]
        objective = directional.get("objective")
        if objective is not None:
            objective_counts[int(objective)] += 1
            if int(objective) == 0:
                zero.append(row)
            elif int(objective) == 1:
                face = row["complete_objective_one_face"]
                if face.get("stable_unmatched_component") is not None:
                    stable.append(row)
                if (
                    int(face["pattern_count"]) < PARENT_FACE_WIDTH
                    or int(face["unmatched_component_count"]) < PARENT_FACE_WIDTH
                ):
                    narrower.append(row)
        elif directional.get("status") not in {"INFEASIBLE", "STRUCTURAL_EMPTY"}:
            nonterminal.append(row)

    materialized = materialize_zero(records=zero, solutions=zero_solutions)
    if nonterminal:
        verdict = "NARROW_FACE_COMPOSITION_NONTERMINAL"
        decision = "CONTINUE_ONLY_NONTERMINAL_COMPOSITIONS"
    elif zero:
        verdict = "NARROW_FACE_COMPOSITION_REACHES_TWO_ZERO_SIGNATURE"
        decision = "VALIDATE_TRIPLE_IN_FULL_CONDITIONAL_BINDING"
    elif stable:
        verdict = "TRIPLE_FACE_HAS_STABLE_SINGLE_COMPONENT"
        decision = "BUILD_FINAL_RELATION_FROM_STABLE_TRIPLE_FACE"
    elif narrower:
        verdict = "TRIPLE_FACE_NARROWS_BELOW_FIVE"
        decision = "CONTINUE_ONLY_STRICT_NARROWEST_TRIPLE_FACE"
    else:
        verdict = "NARROW_FACE_COMPOSITIONS_DO_NOT_PROGRESS"
        decision = "SWITCH_TO_DISTINCT_SIX4_NEAR_MISS_PARENT"

    def compact(row: Mapping[str, Any]) -> dict[str, Any]:
        face = row.get("complete_objective_one_face")
        return {
            "pair_index": int(row["pair_index"]),
            "left_candidate_index": int(row["left_candidate_index"]),
            "right_candidate_index": int(row["right_candidate_index"]),
            "left_source_instance_id": str(row["left_source_instance_id"]),
            "right_source_instance_id": str(row["right_source_instance_id"]),
            "occupied_symmetric_difference": int(
                row["occupied_symmetric_difference"]
            ),
            "objective": row["directional"].get("objective"),
            "status": str(row["directional"]["status"]),
            "pattern_count": None if face is None else int(face["pattern_count"]),
            "unmatched_components": None
            if face is None
            else face["unmatched_components"],
            "stable_unmatched_component": None
            if face is None
            else face["stable_unmatched_component"],
            "qiaoyu_sink_components": None
            if face is None
            else face["qiaoyu_sink_components"],
        }

    ranked = sorted(
        zero or stable or narrower,
        key=lambda row: (
            0 if row["directional"].get("objective") == 0 else 1,
            99
            if row.get("complete_objective_one_face") is None
            else int(row["complete_objective_one_face"]["unmatched_component_count"]),
            99
            if row.get("complete_objective_one_face") is None
            else int(row["complete_objective_one_face"]["pattern_count"]),
            int(row["occupied_symmetric_difference"]),
            int(row["pair_index"]),
        ),
    )[:12]

    return {
        "schema": "zmd_zero_condition_e067_complementary_narrow_face_pairs_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "source_origins": source_origins,
        "selected_action_count": len(specs),
        "unordered_pair_count": len(pair_records),
        "admission_status_counts": dict(sorted(admission_counts.items())),
        "objective_distribution": {
            str(key): value for key, value in sorted(objective_counts.items())
        },
        "zero_candidate_count": len(zero),
        "stable_single_component_count": len(stable),
        "strictly_narrower_face_count": len(narrower),
        "nonterminal_count": len(nonterminal),
        "selected_candidates": [compact(row) for row in ranked],
        "materialized_zero_candidates": materialized,
        "pair_records_path": str(PAIR_RECORDS_PATH.relative_to(ROOT)),
        "pair_records_sha256": sha256_file(PAIR_RECORDS_PATH),
        "truth_boundary": (
            "E063 pole parent plus two distinct E066-selected actions, with direct "
            "order-free delta merge, placement/power validation, and corrected "
            "terminal-signature evaluation. No full binding or routing claim."
        ),
        "ledger_effect": "none",
    }


def main() -> int:
    if RESULT_PATH.exists() or FAILURE_PATH.exists():
        raise FileExistsError("refusing to overwrite E067 terminal output")
    try:
        result = run()
        dump_exclusive(RESULT_PATH, result)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "pairs": result["unordered_pair_count"],
                    "admission": result["admission_status_counts"],
                    "objective_distribution": result["objective_distribution"],
                    "zero": result["zero_candidate_count"],
                    "stable": result["stable_single_component_count"],
                    "narrower": result["strictly_narrower_face_count"],
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
            "schema": "zmd_zero_condition_e067_complementary_narrow_face_pairs_failure_v1",
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
