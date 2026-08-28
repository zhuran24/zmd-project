#!/usr/bin/env python3
"""E079: compile the exact K=47 boundary-body packing quotient."""

from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model

ROOT = Path("/home/zhuran24/zmd-research")
DEFAULT_RUN_DIR = ROOT / "research_lab/local/zero_condition/E079_k47_boundary_macro/run-001"
EXPECTED_FULL_POOL_SHA256 = "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
BOUNDARY_TEMPLATE = "boundary_storage_port"
EXPECTED_BOUNDARY_POSES = 136
EXPECTED_INSTANCE_COUNT = 46
EXPECTED_PACKING_COUNT = 47
EXPECTED_SIDE_COUNT = 23
EXPECTED_BODY_CELLS = 138
EXPECTED_ALLOWED_L_CELLS = 139

CANDIDATE_PATHS = (
    ROOT / "data/preprocessed/candidate_placements.json",
    Path("/home/zhuran24/zmd-pj/data/preprocessed/candidate_placements.json"),
    Path("/home/zhuran24/zmd-certification/data/preprocessed/candidate_placements.json"),
)
MANDATORY_PATHS = (
    ROOT / "data/preprocessed/mandatory_exact_instances.json",
    Path("/home/zhuran24/zmd-pj/data/preprocessed/mandatory_exact_instances.json"),
    Path("/home/zhuran24/zmd-certification/data/preprocessed/mandatory_exact_instances.json"),
)
RULES_PATH = ROOT / "rules/canonical_rules.json"
RECHECK_REPORT = ROOT / "research_lab/local/reviews/20260828_k47_boundary_packing_recheck.md"
RECHECK_SCRIPT = ROOT / "research_lab/local/reviews/k47_recheck/recheck_k47.py"
RECHECK_RESULT = ROOT / "research_lab/local/reviews/k47_recheck/recheck_result.json"
BLIND_PACKINGS = Path("/home/zhuran24/zmd-blind/blind_lab/local/u9/boundary_packings.json")

LICENSE_CONDITIONS = (
    "frozen canonical rules, 46-instance count, and candidate-pool identity remain unchanged",
    "all 46 boundary instances remain homogeneous except for stable instance_id",
    "the consumer is instance-permutation equivariant or uses the canonical sorted-ID-to-sorted-pose recovery",
    "the consumer retains the complete 47-state disjunction unless a separate proof removes states",
    "the full-layout consumer reapplies all omitted body, front, binding, routing, throughput, export, and game constraints",
)
RANK_GUARD = "rank 1 is a deterministic construction choice, never WLOG"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def first_existing(paths: Sequence[Path], *, label: str) -> Path:
    existing = [path.resolve() for path in paths if path.is_file()]
    if not existing:
        raise FileNotFoundError(f"E079 missing {label}: {list(map(str, paths))}")
    return existing[0]


def cell_xy(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def find_key_lists(value: Any, key: str) -> list[list[Any]]:
    output: list[list[Any]] = []
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            if str(child_key) == key and isinstance(child, list):
                output.append(child)
            output.extend(find_key_lists(child, key))
    elif isinstance(value, list):
        for child in value:
            output.extend(find_key_lists(child, key))
    return output


def load_boundary_pool(path: Path) -> tuple[Any, list[Mapping[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = [
        rows
        for rows in find_key_lists(payload, BOUNDARY_TEMPLATE)
        if len(rows) == EXPECTED_BOUNDARY_POSES
        and all(isinstance(row, Mapping) for row in rows)
    ]
    unique: dict[str, list[Mapping[str, Any]]] = {}
    for rows in candidates:
        digest = stable_digest(rows)
        unique[digest] = [dict(row) for row in rows]
    if len(unique) != 1:
        raise RuntimeError(
            f"E079 boundary pool lookup ambiguous: candidates={len(candidates)} unique={len(unique)}"
        )
    return payload, next(iter(unique.values()))


def collect_instance_rows(value: Any) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    if isinstance(value, Mapping):
        if str(value.get("facility_type", "")) == BOUNDARY_TEMPLATE and "instance_id" in value:
            output[str(value["instance_id"])] = dict(value)
        for child in value.values():
            output.update(collect_instance_rows(child))
    elif isinstance(value, list):
        for child in value:
            output.update(collect_instance_rows(child))
    return output


def pose_body(pose: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    cells = tuple(sorted(cell_xy(cell) for cell in pose.get("occupied_cells", []) or []))
    if len(cells) != 3:
        raise RuntimeError(f"E079 boundary pose body size drift: {cells}")
    return cells


def pose_fronts(pose: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    cells = tuple(sorted(cell_xy(cell) for cell in pose.get("output_port_cells", []) or []))
    if len(cells) != 1:
        raise RuntimeError(f"E079 boundary pose output-front drift: {cells}")
    return cells


def pose_side_and_anchor(pose: Mapping[str, Any]) -> tuple[str, int]:
    body = pose_body(pose)
    xs = {x for x, _y in body}
    ys = {y for _x, y in body}
    if xs == {0} and len(ys) == 3:
        return "left", min(ys)
    if ys == {0} and len(xs) == 3:
        return "bottom", min(xs)
    raise RuntimeError(f"E079 non-boundary body in boundary pool: {body}")


def model_stats(model: cp_model.CpModel) -> dict[str, Any]:
    proto = model.Proto()
    linear_terms = 0
    bool_terms = 0
    for constraint in proto.constraints:
        if constraint.has_linear():
            linear_terms += len(constraint.linear.vars)
        elif constraint.has_at_most_one():
            bool_terms += len(constraint.at_most_one.literals)
        elif constraint.has_exactly_one():
            bool_terms += len(constraint.exactly_one.literals)
    return {
        "text_proto_bytes": len(str(proto).encode("utf-8")),
        "variable_count": len(proto.variables),
        "constraint_count": len(proto.constraints),
        "linear_term_count": linear_terms,
        "boolean_literal_count": bool_terms,
    }


class SelectionCollector(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables: Sequence[Any]) -> None:
        super().__init__()
        self._variables = list(variables)
        self.selections: list[tuple[int, ...]] = []

    def on_solution_callback(self) -> None:
        self.selections.append(
            tuple(index for index, variable in enumerate(self._variables) if self.Value(variable))
        )


def enumerate_model(
    model: cp_model.CpModel,
    variables: Sequence[Any],
    *,
    seed: int,
    seconds: float,
) -> tuple[str, list[tuple[int, ...]], dict[str, Any]]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.random_seed = seed
    collector = SelectionCollector(variables)
    started = time.monotonic()
    status = solver.Solve(model, collector)
    elapsed = time.monotonic() - started
    return (
        solver.StatusName(status),
        collector.selections,
        {
            "elapsed_seconds": elapsed,
            "wall_time": float(solver.WallTime()),
            "branches": int(solver.NumBranches()),
            "conflicts": int(solver.NumConflicts()),
        },
    )


def build_baseline(
    pool: Sequence[Mapping[str, Any]],
) -> tuple[cp_model.CpModel, list[Any]]:
    model = cp_model.CpModel()
    variables = [model.NewBoolVar(f"e079_pose_{index}") for index in range(len(pool))]
    model.Add(sum(variables) == EXPECTED_INSTANCE_COUNT)
    by_cell: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for index, pose in enumerate(pool):
        for cell in pose_body(pose):
            by_cell[cell].append(variables[index])
    for cell_variables in by_cell.values():
        if len(cell_variables) > 1:
            model.AddAtMostOne(cell_variables)
    return model, variables


def validate_packing(
    pose_indices: Sequence[int],
    pool: Sequence[Mapping[str, Any]],
    allowed_l: set[tuple[int, int]],
) -> dict[str, Any]:
    if len(pose_indices) != EXPECTED_INSTANCE_COUNT or len(set(pose_indices)) != len(pose_indices):
        raise RuntimeError(f"E079 malformed packing indices: {pose_indices}")
    body_cells: set[tuple[int, int]] = set()
    front_cells: set[tuple[int, int]] = set()
    left_anchors: list[int] = []
    bottom_anchors: list[int] = []
    for pose_index in pose_indices:
        pose = pool[int(pose_index)]
        body = set(pose_body(pose))
        if body_cells & body:
            raise RuntimeError(f"E079 packing body overlap at pose {pose_index}")
        body_cells.update(body)
        fronts = set(pose_fronts(pose))
        if front_cells & fronts:
            raise RuntimeError(f"E079 packing front overlap at pose {pose_index}")
        front_cells.update(fronts)
        side, anchor = pose_side_and_anchor(pose)
        (left_anchors if side == "left" else bottom_anchors).append(anchor)
    omitted = sorted(allowed_l - body_cells)
    if len(left_anchors) != EXPECTED_SIDE_COUNT or len(bottom_anchors) != EXPECTED_SIDE_COUNT:
        raise RuntimeError(
            f"E079 side-count drift: left={len(left_anchors)} bottom={len(bottom_anchors)}"
        )
    if len(body_cells) != EXPECTED_BODY_CELLS or len(front_cells) != EXPECTED_INSTANCE_COUNT:
        raise RuntimeError(
            f"E079 packing cardinality drift: bodies={len(body_cells)} fronts={len(front_cells)}"
        )
    if len(omitted) != 1:
        raise RuntimeError(f"E079 omitted-cell drift: {omitted}")
    return {
        "pose_indices": list(map(int, sorted(pose_indices))),
        "left_anchors": sorted(left_anchors),
        "bottom_anchors": sorted(bottom_anchors),
        "body_cells": [list(cell) for cell in sorted(body_cells)],
        "body_cells_digest": stable_digest(sorted(body_cells)),
        "front_cells": [list(cell) for cell in sorted(front_cells)],
        "front_cells_digest": stable_digest(sorted(front_cells)),
        "omitted_allowed_l_cell": list(omitted[0]),
    }


def extract_external_packings(value: Any) -> set[tuple[int, ...]]:
    output: set[tuple[int, ...]] = set()
    if isinstance(value, Mapping):
        raw = value.get("pose_indices")
        if isinstance(raw, list) and len(raw) == EXPECTED_INSTANCE_COUNT:
            try:
                output.add(tuple(sorted(int(item) for item in raw)))
            except (TypeError, ValueError):
                pass
        for child in value.values():
            output.update(extract_external_packings(child))
    elif isinstance(value, list):
        for child in value:
            output.update(extract_external_packings(child))
    return output


def build_macro_model(state_count: int) -> tuple[cp_model.CpModel, list[Any]]:
    model = cp_model.CpModel()
    states = [model.NewBoolVar(f"e079_state_{index}") for index in range(state_count)]
    model.AddExactlyOne(states)
    return model, states


def build_channel_model(
    packings: Sequence[Sequence[int]],
    pose_count: int,
) -> tuple[cp_model.CpModel, list[Any], list[Any]]:
    model = cp_model.CpModel()
    states = [model.NewBoolVar(f"e079_channel_state_{index}") for index in range(len(packings))]
    poses = [model.NewBoolVar(f"e079_channel_pose_{index}") for index in range(pose_count)]
    model.AddExactlyOne(states)
    incidence: dict[int, list[Any]] = defaultdict(list)
    for state_index, packing in enumerate(packings):
        for pose_index in packing:
            incidence[int(pose_index)].append(states[state_index])
    for pose_index, pose_var in enumerate(poses):
        contributors = incidence.get(pose_index, [])
        if contributors:
            model.Add(pose_var == sum(contributors))
        else:
            model.Add(pose_var == 0)
    model.Add(sum(poses) == EXPECTED_INSTANCE_COUNT)
    return model, states, poses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate_path = first_existing(CANDIDATE_PATHS, label="candidate placements")
    mandatory_path = first_existing(MANDATORY_PATHS, label="mandatory exact instances")
    full_pool_sha256 = sha256_file(candidate_path)
    if full_pool_sha256 != EXPECTED_FULL_POOL_SHA256:
        raise RuntimeError(
            f"E079 full candidate-pool identity drift: expected={EXPECTED_FULL_POOL_SHA256} "
            f"actual={full_pool_sha256} path={candidate_path}"
        )
    _candidate_payload, boundary_pool = load_boundary_pool(candidate_path)
    if len(boundary_pool) != EXPECTED_BOUNDARY_POSES:
        raise RuntimeError(f"E079 boundary pool size drift: {len(boundary_pool)}")

    mandatory_payload = json.loads(mandatory_path.read_text(encoding="utf-8"))
    instance_rows = collect_instance_rows(mandatory_payload)
    if len(instance_rows) != EXPECTED_INSTANCE_COUNT:
        raise RuntimeError(f"E079 boundary instance count drift: {len(instance_rows)}")
    instance_ids = sorted(instance_rows)
    homogeneous_rows = {
        stable_digest({key: value for key, value in row.items() if key != "instance_id"})
        for row in instance_rows.values()
    }
    if len(homogeneous_rows) != 1:
        raise RuntimeError("E079 boundary instances are not homogeneous modulo instance_id")

    allowed_l = {(0, value) for value in range(70)} | {(value, 0) for value in range(70)}
    if len(allowed_l) != EXPECTED_ALLOWED_L_CELLS:
        raise RuntimeError("E079 allowed-L cardinality drift")
    legal_omitted_cells = (
        {(0, value) for value in range(0, 70, 3)}
        | {(value, 0) for value in range(0, 70, 3)}
    )
    if len(legal_omitted_cells) != EXPECTED_PACKING_COUNT:
        raise RuntimeError("E079 legal omitted-cell cardinality drift")

    baseline_model, baseline_vars = build_baseline(boundary_pool)
    baseline_status, baseline_solutions, baseline_runtime = enumerate_model(
        baseline_model,
        baseline_vars,
        seed=79001,
        seconds=60.0,
    )
    baseline_unique = sorted(set(tuple(sorted(row)) for row in baseline_solutions))
    if baseline_status != "OPTIMAL" or len(baseline_unique) != EXPECTED_PACKING_COUNT:
        raise RuntimeError(
            f"E079 baseline enumeration drift: status={baseline_status} "
            f"raw={len(baseline_solutions)} unique={len(baseline_unique)}"
        )

    states: list[dict[str, Any]] = []
    omitted_cells: set[tuple[int, int]] = set()
    pose_set_to_state: dict[tuple[int, ...], int] = {}
    for state_index, pose_indices in enumerate(baseline_unique, 1):
        validated = validate_packing(pose_indices, boundary_pool, allowed_l)
        omitted = tuple(validated["omitted_allowed_l_cell"])
        if omitted in omitted_cells:
            raise RuntimeError(f"E079 duplicate omitted cell: {omitted}")
        omitted_cells.add(omitted)
        canonical_label_recovery = [
            {"instance_id": instance_id, "pose_idx": int(pose_idx)}
            for instance_id, pose_idx in zip(instance_ids, pose_indices, strict=True)
        ]
        state = {
            "state_id": f"boundary_macro_{state_index:02d}",
            "rank": state_index,
            **validated,
            "canonical_label_recovery": canonical_label_recovery,
            "canonical_label_recovery_digest": stable_digest(canonical_label_recovery),
        }
        state["state_digest"] = stable_digest(state)
        states.append(state)
        pose_set_to_state[pose_indices] = state_index

    if omitted_cells != legal_omitted_cells:
        raise RuntimeError(
            "E079 omitted-cell coverage drift: "
            f"missing={sorted(legal_omitted_cells-omitted_cells)} "
            f"extra={sorted(omitted_cells-legal_omitted_cells)}"
        )
    if len(pose_set_to_state) != EXPECTED_PACKING_COUNT:
        raise RuntimeError("E079 macro reverse-map collision")

    for state in states:
        key = tuple(int(value) for value in state["pose_indices"])
        recovered = pose_set_to_state.get(key)
        if recovered != int(state["rank"]):
            raise RuntimeError(f"E079 macro roundtrip drift: {state['state_id']}/{recovered}")
        label_rows = state["canonical_label_recovery"]
        if [row["instance_id"] for row in label_rows] != instance_ids:
            raise RuntimeError(f"E079 canonical label order drift: {state['state_id']}")
        if [row["pose_idx"] for row in label_rows] != list(key):
            raise RuntimeError(f"E079 canonical pose recovery drift: {state['state_id']}")

    macro_model, macro_vars = build_macro_model(len(states))
    macro_status, macro_solutions, macro_runtime = enumerate_model(
        macro_model,
        macro_vars,
        seed=79002,
        seconds=30.0,
    )
    if macro_status != "OPTIMAL" or len(macro_solutions) != EXPECTED_PACKING_COUNT:
        raise RuntimeError(
            f"E079 macro enumeration drift: status={macro_status} count={len(macro_solutions)}"
        )
    if any(len(selection) != 1 for selection in macro_solutions):
        raise RuntimeError("E079 macro selected-state cardinality drift")

    packing_rows = [tuple(int(value) for value in state["pose_indices"]) for state in states]
    channel_model, channel_states, channel_poses = build_channel_model(
        packing_rows,
        len(boundary_pool),
    )
    channel_status, channel_solutions, channel_runtime = enumerate_model(
        channel_model,
        channel_states,
        seed=79003,
        seconds=30.0,
    )
    if channel_status != "OPTIMAL" or len(channel_solutions) != EXPECTED_PACKING_COUNT:
        raise RuntimeError(
            f"E079 channel enumeration drift: status={channel_status} count={len(channel_solutions)}"
        )
    channel_solver = cp_model.CpSolver()
    channel_solver.parameters.max_time_in_seconds = 10.0
    channel_solver.parameters.num_search_workers = 1
    for rank, state in enumerate(states):
        test_model = channel_model.Clone()
        test_state = test_model.get_bool_var_from_proto_index(channel_states[rank].Index())
        test_model.Add(test_state == 1)
        status = channel_solver.Solve(test_model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"E079 channel rank replay failed: {rank+1}")
        selected_pose_indices = tuple(
            index
            for index, variable in enumerate(channel_poses)
            if channel_solver.Value(
                test_model.get_bool_var_from_proto_index(variable.Index())
            )
        )
        if selected_pose_indices != tuple(state["pose_indices"]):
            raise RuntimeError(f"E079 channel pose roundtrip drift: {rank+1}")

    external_comparisons: dict[str, Any] = {}
    if RECHECK_RESULT.is_file():
        payload = json.loads(RECHECK_RESULT.read_text(encoding="utf-8"))
        recheck_packings = extract_external_packings(payload)
        expected_rank1 = tuple(baseline_unique[0])
        if (
            payload.get("status") != "PASS"
            or int(payload.get("K", -1)) != EXPECTED_PACKING_COUNT
            or payload.get("blind_packings_exact_equal") is not True
            or recheck_packings != {expected_rank1}
        ):
            raise RuntimeError("E079 main-tree recheck summary mismatch")
        external_comparisons["main_tree_recheck_result"] = {
            "available": True,
            "path": str(RECHECK_RESULT),
            "sha256": sha256_file(RECHECK_RESULT),
            "reported_packing_count": int(payload["K"]),
            "comparison_scope": "reported K plus canonical rank-1 packing",
            "rank1_exact_equal": True,
            "full_set_embedded": False,
            "blind_full_set_equality_reported": True,
        }
    else:
        external_comparisons["main_tree_recheck_result"] = {"available": False}

    if BLIND_PACKINGS.is_file():
        payload = json.loads(BLIND_PACKINGS.read_text(encoding="utf-8"))
        blind_packings = extract_external_packings(payload)
        if (
            payload.get("status") != "COMPLETE_ENUMERATION"
            or int(payload.get("packing_count_K", -1)) != EXPECTED_PACKING_COUNT
            or blind_packings != set(baseline_unique)
        ):
            raise RuntimeError("E079 blind-tree full packing set mismatch")
        external_comparisons["blind_tree_packings"] = {
            "available": True,
            "path": str(BLIND_PACKINGS),
            "sha256": sha256_file(BLIND_PACKINGS),
            "packing_count": len(blind_packings),
            "comparison_scope": "complete 47-packing pose-index set",
            "exact_set_equality": True,
        }
    else:
        external_comparisons["blind_tree_packings"] = {"available": False}

    pose_to_states: dict[str, list[str]] = defaultdict(list)
    for state in states:
        for pose_index in state["pose_indices"]:
            pose_to_states[str(pose_index)].append(str(state["state_id"]))

    macro = {
        "schema": "zmd_boundary_packing_macro_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "object_space": (
            "boundary_storage_port legal pose selection plus mutual body-cell exclusivity only"
        ),
        "identity": {
            "candidate_path": str(candidate_path),
            "candidate_sha256": full_pool_sha256,
            "mandatory_path": str(mandatory_path),
            "mandatory_sha256": sha256_file(mandatory_path),
            "canonical_rules_path": str(RULES_PATH),
            "canonical_rules_sha256": sha256_file(RULES_PATH),
            "boundary_pool_digest": stable_digest(boundary_pool),
            "homogeneous_instance_metadata_digest": next(iter(homogeneous_rows)),
            "boundary_pose_count": len(boundary_pool),
            "boundary_instance_count": len(instance_ids),
        },
        "state_count": len(states),
        "states": states,
        "pose_to_states": dict(sorted(pose_to_states.items(), key=lambda item: int(item[0]))),
        "license": {
            "conditions": list(LICENSE_CONDITIONS),
            "rank_guard": RANK_GUARD,
        },
        "encoding": {
            "recommended": "47 one-hot state variables with ExactlyOne",
            "optional_pose_channel": (
                "z_pose = sum(state variables whose packing contains the pose); no AddElement"
            ),
            "warning": (
                "materializing all 136 pose channels may erase part of the variable-count gain; "
                "consumers should read macro fields directly where possible"
            ),
        },
        "truth_boundary": (
            "The macro is exact only for the frozen boundary-body packing quotient. "
            "Every full-layout consumer must keep all 47 alternatives or separately prove "
            "a smaller disjunction complete, preserve instance permutation semantics, and "
            "reapply every omitted constraint."
        ),
    }
    macro["macro_digest"] = stable_digest(macro)
    macro_path = run_dir / "BOUNDARY_MACRO_V1.json"
    atomic_json(macro_path, macro)

    benchmark = {
        "schema": "zmd_e079_boundary_macro_benchmark_v1",
        "baseline": {
            "status": baseline_status,
            "solution_count": len(baseline_unique),
            "model": model_stats(baseline_model),
            "runtime": baseline_runtime,
        },
        "macro_one_hot": {
            "status": macro_status,
            "solution_count": len(macro_solutions),
            "model": model_stats(macro_model),
            "runtime": macro_runtime,
        },
        "macro_with_pose_channel": {
            "status": channel_status,
            "solution_count": len(channel_solutions),
            "model": model_stats(channel_model),
            "runtime": channel_runtime,
        },
        "decision_variable_ratio_baseline_to_macro": len(boundary_pool) / len(states),
        "external_comparisons": external_comparisons,
    }
    benchmark_path = run_dir / "ENCODING_BENCHMARK.json"
    atomic_json(benchmark_path, benchmark)

    result = {
        "schema": "zmd_e079_k47_boundary_macro_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": "K47_BOUNDARY_PACKING_EXACTLY_COMPILED_TO_47_STATE_MACRO",
        "decision": "USE_MACRO_IN_PARTITION_SEAM_PROTOTYPE_BEFORE_FULL_MASTER_INTEGRATION",
        "packing_count": len(states),
        "boundary_pose_count": len(boundary_pool),
        "boundary_instance_count": len(instance_ids),
        "left_count_per_state": EXPECTED_SIDE_COUNT,
        "bottom_count_per_state": EXPECTED_SIDE_COUNT,
        "omitted_allowed_l_cell_count": len(omitted_cells),
        "rank1_state_id": states[0]["state_id"],
        "rank1_is_wlog": False,
        "macro_path": str(macro_path.relative_to(ROOT)),
        "macro_sha256": sha256_file(macro_path),
        "benchmark_path": str(benchmark_path.relative_to(ROOT)),
        "benchmark_sha256": sha256_file(benchmark_path),
        "baseline_model_stats": benchmark["baseline"]["model"],
        "macro_model_stats": benchmark["macro_one_hot"]["model"],
        "channel_model_stats": benchmark["macro_with_pose_channel"]["model"],
        "decision_variable_ratio_baseline_to_macro": benchmark[
            "decision_variable_ratio_baseline_to_macro"
        ],
        "license": macro["license"],
        "external_comparisons": external_comparisons,
        "input_identity": macro["identity"],
        "review_evidence": {
            "report_path": str(RECHECK_REPORT.relative_to(ROOT)),
            "report_sha256": sha256_file(RECHECK_REPORT),
            "script_path": str(RECHECK_SCRIPT.relative_to(ROOT)),
            "script_sha256": sha256_file(RECHECK_SCRIPT),
            "result_path": str(RECHECK_RESULT.relative_to(ROOT)),
            "result_sha256": sha256_file(RECHECK_RESULT),
        },
        "runner": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "truth_boundary": macro["truth_boundary"],
    }
    result["result_digest"] = stable_digest(result)
    result_path = run_dir / "RESULT.json"
    atomic_json(result_path, result)
    receipt = {
        "schema": "zmd_e079_k47_boundary_macro_receipt_v1",
        "result_path": str(result_path.relative_to(ROOT)),
        "result_sha256": sha256_file(result_path),
        "macro_sha256": sha256_file(macro_path),
        "benchmark_sha256": sha256_file(benchmark_path),
        "verdict": result["verdict"],
        "decision": result["decision"],
    }
    atomic_json(run_dir / "RESULT_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
