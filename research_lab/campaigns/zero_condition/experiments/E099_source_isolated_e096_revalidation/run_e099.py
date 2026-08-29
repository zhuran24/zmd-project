#!/usr/bin/env python3
"""E099: source-isolated revalidation of E096 and explicit E097 chain decision."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import types
import traceback
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E099_source_isolated_e096_revalidation/run-002"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition"
)
E095_RUNNER = E095_DIR / "run_e095.py"
E095_DURABLE = E095_DIR / "RESULT.txt"
E095_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001/RESULT.json"
)
E095_CHECK = E095_RESULT.with_name("ARTIFACT_CHECK.json")
E096_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E096_module_b_interface_thickness"
)
E096_RUNNER = E096_DIR / "run_e096.py"
E096_SNAPSHOT = E096_DIR / "MACHINE_SNAPSHOT.json"
E098_DIR = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E098_e097_machine_packet_recovery"
)
E098_RUNNER = E098_DIR / "run_e098.py"
E098_DURABLE = E098_DIR / "RESULT.txt"
E098_FAILURE = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E098_e097_machine_packet_recovery/run-001/FAILURE.json"
)
E098_E096_RESULT = E098_FAILURE.parent / "e096-semantic-rerun/RESULT.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E095_DURABLE: "9d1411c0aac5c01b8d065051d26e204ddbe0e2751c45e81feb1b5002fe1cbe88",
    E095_RESULT: "78de6850a02e66d1018a6f3f3ec545d624e16bdc0cf7e4ef1b455ea2eb25e609",
    E095_CHECK: "6d75894d7a79cb9611fc20d1121a832777f9cf4eeb8e67bb4fef85066d0ee43f",
    E096_RUNNER: "5a46528e795fa7e866c1ba79eea20fb6b0ce770def46e30fbbd15311576463ec",
    E096_SNAPSHOT: "2fea85fa6d1b7d60454179dcea89d3aaf9191102ff28c870bbbce6409160c3d9",
    E098_RUNNER: "772d7a4376404cb091762f94094d0fb51dd5a2919b8151c1f14fbb67808fad5a",
    E098_DURABLE: "7bd368d8e57d491cfe4e11fe915f709d506d4efa0037710cd808e9c7f744bb52",
    E098_FAILURE: "377b05f578f0e339284c7e6ee3d1e1ff0146242b08dbb7f3e0275d464e53882f",
    E098_E096_RESULT: "bc53596f46c893e9587777636b1a95e28755f226d61cd3c396591650feb1c4dd",
}
STALE_E095_DURABLE_HASH = (
    "6794d794cbd512c5bc01379a2f29ace4080127dc8c4d98bd706b9a792e536b14"
)
EXPECTED_CANDIDATES = 4378
EXPECTED_ANCHOR_BODIES = 91
MIN_ANCHOR_SIDE_COUNT = 20
MAX_ANCHOR_SEPARATOR_COUNT = 15
MIN_SIDE_CANDIDATE_FRACTION = 0.15
MAX_SPATIAL_SEPARATOR_FRACTION = 0.20


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(
            json_safe(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
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


def source_module(path: Path, name: str, package: str | None = None) -> types.ModuleType:
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package if package is not None else name.rpartition(".")[0]
    module.__loader__ = None
    sys.modules[name] = module
    code = compile(
        raw,
        f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>",
        "exec",
        dont_inherit=True,
    )
    exec(code, module.__dict__)
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E099 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E099 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"E099 input drift: {path}: {observed} != {expected}")
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }
    if STALE_E095_DURABLE_HASH not in E096_RUNNER.read_text(encoding="utf-8"):
        raise RuntimeError("E099 stale E096 prose pin disappeared")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def cell(value: Sequence[int]) -> tuple[int, int]:
    return int(value[0]), int(value[1])


def replay_interface(
    records: Sequence[Mapping[str, Any]], groups: Mapping[int, str]
) -> dict[str, Any]:
    body_coverers: dict[tuple[int, int], list[int]] = defaultdict(list)
    group_counts: Counter[str] = Counter()
    anchor_counts: Counter[str] = Counter()
    for index, row in enumerate(records):
        group = groups[index]
        group_counts[group] += 1
        anchor_counts[group] += int(bool(row["is_anchor"]))
        for value in map(cell, row["body"]):
            body_coverers[value].append(index)

    shared_body: set[tuple[int, int]] = set()
    cross_front: set[tuple[int, int]] = set()
    participants: set[int] = set()
    for value, indices in body_coverers.items():
        if len({groups[index] for index in indices}) > 1:
            shared_body.add(value)
            participants.update(indices)
    for index, row in enumerate(records):
        group = groups[index]
        for value in map(cell, row["front_cells"]):
            others = [
                target
                for target in body_coverers.get(value, [])
                if groups[target] != group
            ]
            if others:
                cross_front.add(value)
                participants.add(index)
                participants.update(others)
    interface_cells = shared_body | cross_front
    return {
        "group_candidate_counts": dict(sorted(group_counts.items())),
        "group_anchor_counts": dict(sorted(anchor_counts.items())),
        "shared_body_cell_count": len(shared_body),
        "cross_front_body_cell_count": len(cross_front),
        "interface_occupancy_cell_count": len(interface_cells),
        "interface_candidate_count": len(participants),
        "interface_cell_digest": stable_digest(sorted(interface_cells)),
        "interface_candidate_digest": stable_digest(
            sorted(str(records[index]["body_digest"]) for index in participants)
        ),
    }


def classify(row: Mapping[str, Any], axis: str, coordinate: int) -> str:
    bbox = row["bbox"]
    low = int(bbox[f"min_{axis}"])
    high = int(bbox[f"max_{axis}"])
    if high <= coordinate:
        return "low"
    if low > coordinate:
        return "high"
    return "separator"


def allocation_replay(
    records: Sequence[Mapping[str, Any]],
    groups: Mapping[int, str],
    class_counts: Mapping[tuple[str, str, int, int], int],
) -> dict[str, Any]:
    support_groups: dict[tuple[str, str, int, int], set[str]] = defaultdict(set)
    for index, row in enumerate(records):
        for raw in row["supported_classes"]:
            support_groups[tuple(raw)].add(groups[index])
    dimensions: list[dict[str, Any]] = []
    box = 1
    log2_box = 0.0
    for class_key, count in sorted(class_counts.items()):
        members = sorted(support_groups.get(class_key, set()))
        if len(members) <= 1:
            continue
        dimensions.append(
            {
                "class_key": list(class_key),
                "required_count": int(count),
                "support_groups": members,
            }
        )
        box *= int(count) + 1
        log2_box += math.log2(int(count) + 1)
    return {
        "class_allocation_dimension_count": len(dimensions),
        "class_allocation_dimensions": dimensions,
        "class_allocation_box_upper_bound": box,
        "class_allocation_log2_box_upper_bound": log2_box,
    }


def independent_replay(
    result: Mapping[str, Any],
    template: Mapping[str, Any],
    spatial_payload: Mapping[str, Any],
    candidate_payload: Mapping[str, Any],
    class_counts: Mapping[tuple[str, str, int, int], int],
) -> dict[str, Any]:
    records = list(candidate_payload["candidates"])
    if len(records) != EXPECTED_CANDIDATES:
        raise RuntimeError("E099 candidate count drift")
    if sum(bool(row["is_anchor"]) for row in records) != EXPECTED_ANCHOR_BODIES:
        raise RuntimeError("E099 anchor count drift")

    template_groups = {
        index: str(row["template"]) for index, row in enumerate(records)
    }
    template_observed = replay_interface(records, template_groups)
    for key in (
        "group_candidate_counts",
        "shared_body_cell_count",
        "cross_front_body_cell_count",
        "interface_occupancy_cell_count",
        "interface_candidate_count",
        "interface_cell_digest",
        "interface_candidate_digest",
    ):
        if template_observed[key] != template[key]:
            raise RuntimeError(f"E099 template replay drift: {key}")

    selected = result["selected_spatial_cut"]
    axis = str(selected["axis"])
    coordinate = int(selected["coordinate"])
    selected_groups = {
        index: classify(row, axis, coordinate)
        for index, row in enumerate(records)
    }
    selected_observed = replay_interface(records, selected_groups)
    allocation_observed = allocation_replay(records, selected_groups, class_counts)
    for key in (
        "group_candidate_counts",
        "group_anchor_counts",
        "shared_body_cell_count",
        "cross_front_body_cell_count",
        "interface_occupancy_cell_count",
        "interface_candidate_count",
        "interface_cell_digest",
        "interface_candidate_digest",
    ):
        if selected_observed[key] != selected[key]:
            raise RuntimeError(f"E099 selected spatial replay drift: {key}")
    for key in (
        "class_allocation_dimension_count",
        "class_allocation_dimensions",
        "class_allocation_box_upper_bound",
    ):
        if allocation_observed[key] != selected[key]:
            raise RuntimeError(f"E099 allocation replay drift: {key}")
    if not math.isclose(
        float(allocation_observed["class_allocation_log2_box_upper_bound"]),
        float(selected["class_allocation_log2_box_upper_bound"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise RuntimeError("E099 allocation log2 replay drift")

    cuts = list(spatial_payload["cuts"])
    guarded = [row for row in cuts if bool(row["balance_guard_pass"])]
    if not guarded:
        raise RuntimeError("E099 no guarded cut")
    ordered = sorted(
        guarded,
        key=lambda row: (
            int(row["interface_occupancy_cell_count"]),
            int(row["group_candidate_counts"].get("separator", 0)),
            float(row["class_allocation_log2_box_upper_bound"]),
            int(row["largest_side_candidate_count"]),
            str(row["axis"]),
            int(row["coordinate"]),
        ),
    )
    best = ordered[0]
    if best["cut_id"] != selected["cut_id"]:
        raise RuntimeError("E099 selected cut is not frontier minimum")

    group_counts = selected_observed["group_candidate_counts"]
    anchor_counts = selected_observed["group_anchor_counts"]
    nonseparator = int(group_counts.get("low", 0)) + int(
        group_counts.get("high", 0)
    )
    min_fraction = min(
        int(group_counts.get("low", 0)), int(group_counts.get("high", 0))
    ) / nonseparator
    guard = (
        int(anchor_counts.get("low", 0)) >= MIN_ANCHOR_SIDE_COUNT
        and int(anchor_counts.get("high", 0)) >= MIN_ANCHOR_SIDE_COUNT
        and int(anchor_counts.get("separator", 0)) <= MAX_ANCHOR_SEPARATOR_COUNT
        and min_fraction >= MIN_SIDE_CANDIDATE_FRACTION
    )
    if guard is not True or selected["balance_guard_pass"] is not True:
        raise RuntimeError("E099 selected guard replay drift")

    spatial_dominates = (
        int(selected["interface_occupancy_cell_count"]) * 2
        <= int(template["interface_occupancy_cell_count"])
        and int(group_counts.get("separator", 0))
        <= int(EXPECTED_CANDIDATES * MAX_SPATIAL_SEPARATOR_FRACTION)
        and int(selected["largest_side_candidate_count"])
        < int(template["largest_group_candidate_count"])
    )
    template_dominates = all(
        int(template["interface_occupancy_cell_count"])
        <= int(row["interface_occupancy_cell_count"])
        and int(template["interface_candidate_count"])
        <= int(row["interface_candidate_count"])
        for row in guarded
    )
    if spatial_dominates:
        expected_verdict = "SPATIAL_SEPARATOR_INTERFACE_DOMINATES_TEMPLATE_INTERFACE"
        expected_decision = "SELECT_SPATIAL_SEPARATOR_DECOMPOSITION"
    elif template_dominates:
        expected_verdict = "TEMPLATE_INTERFACE_DOMINATES_GUARDED_SPATIAL_INTERFACES"
        expected_decision = "SELECT_TEMPLATE_DECOMPOSITION"
    else:
        expected_verdict = "TEMPLATE_AND_SPATIAL_INTERFACES_ARE_INCOMPARABLE"
        expected_decision = "KEEP_BOTH_AND_BUILD_HYBRID_INTERFACE"
    if result["verdict"] != expected_verdict or result["decision"] != expected_decision:
        raise RuntimeError("E099 verdict/decision replay drift")

    return {
        "status": "PASS",
        "candidate_count": len(records),
        "anchor_count": EXPECTED_ANCHOR_BODIES,
        "template_replay": template_observed,
        "selected_spatial_replay": selected_observed,
        "allocation_replay": allocation_observed,
        "selected_cut_id": selected["cut_id"],
        "guarded_cut_count": len(guarded),
        "spatial_dominates": spatial_dominates,
        "template_dominates": template_dominates,
        "verdict": expected_verdict,
        "decision": expected_decision,
    }


def semantic_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    selected = result["selected_spatial_cut"]
    return {
        "candidate_count": result["candidate_count"],
        "required_body_count": result["required_body_count"],
        "template": {
            key: result["template_interface"][key]
            for key in (
                "group_candidate_counts",
                "interface_occupancy_cell_count",
                "interface_candidate_count",
                "largest_group_candidate_count",
                "class_allocation_dimension_count",
            )
        },
        "selected": {
            key: selected[key]
            for key in (
                "cut_id",
                "axis",
                "coordinate",
                "balance_guard_pass",
                "group_candidate_counts",
                "group_anchor_counts",
                "interface_occupancy_cell_count",
                "interface_candidate_count",
                "separator_candidate_fraction",
                "largest_side_candidate_count",
                "class_allocation_dimension_count",
                "class_allocation_log2_box_upper_bound",
            )
        },
        "verdict": result["verdict"],
        "decision": result["decision"],
    }


def snapshot_projection(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_count": snapshot["candidate_count"],
        "required_body_count": snapshot["required_body_count"],
        "template": snapshot["template_interface"],
        "selected": snapshot["selected_spatial_cut"],
        "verdict": snapshot["terminal_result"]["verdict"],
        "decision": snapshot["terminal_result"]["decision"],
    }


def diff_values(left: Any, right: Any, prefix: str = "") -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left:
                output.append({"path": path, "left": None, "right": right[key]})
            elif key not in right:
                output.append({"path": path, "left": left[key], "right": None})
            else:
                output.extend(diff_values(left[key], right[key], path))
        return output
    if left != right:
        output.append({"path": prefix, "left": left, "right": right})
    return output


def run(run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E099 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e099_source_e095")
    e096 = source_module(E096_RUNNER, "zmd_e099_source_e096")
    e096.import_e095 = lambda: e095
    if e096.EXPECTED_HASHES[e096.E095_DURABLE] != STALE_E095_DURABLE_HASH:
        raise RuntimeError("E099 stale E096 prose pin value drift")
    e096.EXPECTED_HASHES[e096.E095_DURABLE] = EXPECTED_HASHES[E095_DURABLE]

    source_run_dir = run_dir / "source-isolated-e096"
    result = e096.run(source_run_dir)
    result_path = source_run_dir / "RESULT.json"
    template_path = source_run_dir / "TEMPLATE_INTERFACE.json"
    spatial_path = source_run_dir / "SPATIAL_INTERFACE_FRONTIER.json"
    candidates_path = source_run_dir / "B_CANDIDATE_INTERFACE_RECORDS.json"

    context = e095.build_context()
    class_counts = {
        key: int(count)
        for key, count in context["class_counts"].items()
        if key[0] == "B"
    }
    replay = independent_replay(
        result,
        load_json(template_path),
        load_json(spatial_path),
        load_json(candidates_path),
        class_counts,
    )
    replay_path = run_dir / "INDEPENDENT_REPLAY.json"
    dump_exclusive(replay_path, replay)

    source_projection = semantic_projection(result)
    e098_projection = semantic_projection(load_json(E098_E096_RESULT))
    committed_projection = snapshot_projection(load_json(E096_SNAPSHOT))
    source_matches_e098 = source_projection == e098_projection
    source_matches_committed = source_projection == committed_projection
    committed_differences = diff_values(committed_projection, source_projection)
    comparison = {
        "schema": "zmd_e099_e096_projection_comparison_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "source_matches_e098": source_matches_e098,
        "source_matches_committed_snapshot": source_matches_committed,
        "committed_difference_count": len(committed_differences),
        "committed_differences": committed_differences,
        "source_projection": source_projection,
        "e098_projection": e098_projection,
        "committed_projection": committed_projection,
    }
    comparison_path = run_dir / "PROJECTION_COMPARISON.json"
    dump_exclusive(comparison_path, comparison)

    if source_matches_committed:
        verdict = "SOURCE_ISOLATED_REPLAY_RESTORES_COMMITTED_E096_SELECTION"
        decision = "RECOVER_E097_BRANCH_IN_FRESH_PACKET"
    elif source_matches_e098:
        verdict = "SOURCE_ISOLATED_REPLAY_INVALIDATES_COMMITTED_E096_SELECTION"
        decision = "RETRACT_E096_E097_AND_BUILD_HYBRID_INTERFACE_FROM_E095"
    else:
        verdict = "SOURCE_ISOLATED_REPLAY_FINDS_THIRD_E096_SEMANTICS"
        decision = "STOP_AND_ISOLATE_LOWER_DEPENDENCY_IDENTITY"

    final = {
        "schema": "zmd_e099_source_isolated_e096_revalidation_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "source_execution": {
            "operation_profiles_source_sha256": sha256_file(OPERATION_PROFILES),
            "e095_source_sha256": sha256_file(E095_RUNNER),
            "e096_source_sha256": sha256_file(E096_RUNNER),
            "bytecode_cache_consumed_for_these_modules": False,
            "e096_result_path": display(result_path),
            "e096_result_sha256": sha256_file(result_path),
            "template_path": display(template_path),
            "template_sha256": sha256_file(template_path),
            "spatial_path": display(spatial_path),
            "spatial_sha256": sha256_file(spatial_path),
            "candidates_path": display(candidates_path),
            "candidates_sha256": sha256_file(candidates_path),
        },
        "independent_replay": {
            "path": display(replay_path),
            "sha256": sha256_file(replay_path),
            "status": replay["status"],
            "selected_cut_id": replay["selected_cut_id"],
            "verdict": replay["verdict"],
            "decision": replay["decision"],
        },
        "comparison": {
            "path": display(comparison_path),
            "sha256": sha256_file(comparison_path),
            "source_matches_e098": source_matches_e098,
            "source_matches_committed_snapshot": source_matches_committed,
            "committed_difference_count": len(committed_differences),
        },
        "source_stable_interface": source_projection,
        "truth_boundary": (
            "Source-isolated no-solver interface census and independent replay. "
            "It can retract a representation continuation, not decide module-B "
            "feasibility or any downstream terminal/binding/routing property."
        ),
    }
    final_path = run_dir / "RESULT.json"
    dump_exclusive(final_path, final)
    return final


def main() -> int:
    run_dir = DEFAULT_RUN_DIR
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir)
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "selected_cut_id": result["source_stable_interface"]["selected"][
                        "cut_id"
                    ],
                    "source_matches_e098": result["comparison"][
                        "source_matches_e098"
                    ],
                    "source_matches_committed_snapshot": result["comparison"][
                        "source_matches_committed_snapshot"
                    ],
                    "committed_difference_count": result["comparison"][
                        "committed_difference_count"
                    ],
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e099_execution_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
