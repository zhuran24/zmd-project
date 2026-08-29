#!/usr/bin/env python3
"""Independent replay for E108 finite template projections."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import types
from typing import Any, Mapping

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e108.py"
RUN = ROOT / "research_lab/local/zero_condition/E108_nested_template_projection_atlas/run-001"
RESULT = RUN / "RESULT.json"
BODY = RUN / "BODY_TEMPLATE_PROJECTION.json"
UPPER = RUN / "UPPER_FRONT_TEMPLATE_PROJECTION.json"
LOWER = RUN / "LOWER_FRONT_TEMPLATE_PROJECTION.json"
INTERSECTION = RUN / "TEMPLATE_PROJECTION_INTERSECTION.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E104_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E104_high_reserved_y60_constructor/run_e104.py"
E107_CHECK = ROOT / "research_lab/local/zero_condition/E107_reverse_nested_allocation_handshake/run-001/ARTIFACT_CHECK.json"
E101_BODY = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/BODY_ONLY_RESULT.json"

EXPECTED = {
    RUNNER: "b85cc525f001735fe818d9692387a9aceaa61cee4d82dbf1867ad0c920504e48",
    RESULT: "c53855a54af9ad79bb278d80a084b9c0d7b66f6242bbf75cdff408ca9991c8f9",
    BODY: "24fdc3943a341321a44ddf99197dc4daea82d71ff4bfd16d1f5469269ebdae80",
    UPPER: "0e937b030787010b165ebe5502b9f8b1aefb981b1ab6ccd46d874e83f1270bca",
    LOWER: "1ddd05196f841e606453b2d72659032b8d48c1d5b973c4dc7c7fccad2a5524af",
    INTERSECTION: "d5996fb018f361faa836f2dbebeef003d5d6e8a37cfe9353f55b38ef5bff801a",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E104_RUNNER: "1b2eae0a788e0f4be4cf4af857b8f5b4ceb16f17a215eed41c7d68d656a315fd",
    E107_CHECK: "9fc472de466d09e4d41d97ae221786fe19a72032294be82a576584c65b927235",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
}
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
TOTALS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
EXPECTED_BODY_VECTORS = {
    (6, 0, 3),
    (7, 0, 3),
    (3, 2, 2),
    (3, 1, 3),
    (6, 1, 2),
    (5, 2, 1),
    (3, 0, 4),
}
KNOWN_NOGOODS = {
    (7, 0, 3),
    (3, 2, 2),
    (3, 1, 3),
    (6, 1, 2),
    (5, 2, 1),
}
EXPECTED_REMAINING = {(6, 0, 3), (3, 0, 4)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def source_module(path: Path, name: str, package: str | None = None) -> types.ModuleType:
    raw = path.read_bytes()
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = package if package is not None else name.rpartition(".")[0]
    module.__loader__ = None
    sys.modules[name] = module
    exec(
        compile(raw, f"<source-isolated-check:{path}:{hashlib.sha256(raw).hexdigest()}>", "exec", dont_inherit=True),
        module.__dict__,
    )
    return module


def vector_set(payload: Mapping[str, Any]) -> set[tuple[int, int, int]]:
    return {tuple(map(int, row["vector"])) for row in payload["vectors"]}


def side_rows(prepared: Mapping[str, Any], side: str) -> dict[int, Mapping[str, Any]]:
    return {
        int(row["global_row_index"]): row
        for row in prepared["survivors"]
        if str(row["nested_side"]) == side
    }


def replay_witness(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
    payload: Mapping[str, Any],
    side: str | None,
) -> dict[str, Any]:
    if side is None:
        source = {int(row["global_row_index"]): row for row in prepared["survivors"]}
    else:
        source = side_rows(prepared, side)
    coverage = set(prepared["context"]["fixed_coverage"])
    fixed_solid = set(prepared["context"]["fixed_solid"])
    pools = prepared["context"]["pools"]
    class_keys = tuple(
        sorted(
            key
            for key in prepared["context"]["class_counts"]
            if key[0] == "B"
        )
    )
    records: list[dict[str, Any]] = []
    for record in payload["vectors"]:
        vector = tuple(map(int, record["vector"]))
        witness = record["witness"]
        global_indices = list(map(int, witness["selected_global_indices"]))
        require(len(global_indices) == len(set(global_indices)), "duplicate witness row")
        selected = [source[index] for index in global_indices]
        require(len(selected) == int(witness["selected_body_count"]), "selected count drift")
        occupied = set(fixed_solid)
        observed: Counter[str] = Counter()
        unpowered = 0
        for row in selected:
            body = set(row["body"])
            require(not occupied & body, "projection witness body overlap")
            occupied |= body
            observed[str(row["template"])] += 1
            unpowered += int(not bool(body & coverage))
        require(unpowered == 0, "projection witness has unpowered body")
        if side == "upper":
            require(tuple(observed[template] for template in TEMPLATES) == vector, "upper vector drift")
        elif side == "lower":
            require(tuple(observed[template] for template in TEMPLATES) == vector, "lower vector drift")
        else:
            upper_counts = Counter(
                str(row["template"])
                for row in selected
                if str(row["nested_side"]) == "upper"
            )
            require(tuple(upper_counts[template] for template in TEMPLATES) == vector, "body upper vector drift")
            require(observed == Counter(TOTALS), "body global template totals drift")
            require(len(selected) == 26, "body witness count drift")

        stable_footprints = prepared["context"]["stable_footprints"]
        if side in {None, "lower"}:
            for instance_id, footprint in stable_footprints.items():
                require(
                    any(tuple(row["body"]) == footprint for row in selected),
                    f"stable body missing from witness: {instance_id}",
                )

        if side is not None:
            modes = list(witness["selected_modes"])
            require(len(modes) == len(selected), "mode count drift")
            mode_by_global = {int(row["global_row_index"]): row for row in modes}
            require(set(mode_by_global) == set(global_indices), "mode/body identity drift")
            allocation = Counter()
            for row in selected:
                global_index = int(row["global_row_index"])
                mode = mode_by_global[global_index]
                pose_index = int(mode["pose_index"])
                require(pose_index in row["mode_pose_indices"], "pose not in body mode set")
                class_key = tuple(mode["class_key"])
                require(class_key in class_keys, "unknown class key")
                require(class_key[1] == row["template"], "class/template mismatch")
                forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
                if forced is not None:
                    require(
                        (int(class_key[2]), int(class_key[3])) == tuple(map(int, forced)),
                        "stable body class drift",
                    )
                pose = pools[str(row["template"])][pose_index]
                input_cells = [e095.cell(value) for value in pose["input_port_cells"]]
                output_cells = [e095.cell(value) for value in pose["output_port_cells"]]
                free_inputs = [
                    value
                    for value in input_cells
                    if e095.in_grid(value) and value not in occupied
                ]
                free_outputs = [
                    value
                    for value in output_cells
                    if e095.in_grid(value) and value not in occupied
                ]
                require(len(free_inputs) >= int(mode["need_in"]), "input-front witness drift")
                require(len(free_outputs) >= int(mode["need_out"]), "output-front witness drift")
                allocation[class_key] += 1
            require(
                [allocation[key] for key in class_keys] == list(map(int, witness["allocation_tuple"])),
                "allocation tuple drift",
            )
        records.append({"vector": list(vector), "selected_body_count": len(selected)})
    return {"vector_count": len(records), "records": records}


def replay_body_projection(e108: types.ModuleType, prepared: Mapping[str, Any]) -> dict[str, Any]:
    projection = e108.build_body_projection(prepared)
    model = projection["model"]
    found: set[tuple[int, int, int]] = set()
    solves: list[dict[str, Any]] = []
    for iteration in range(20):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 108900 + iteration
        solver.parameters.search_branching = cp_model.PSEUDO_COST_SEARCH
        solver.parameters.symmetry_level = 0
        solver.parameters.cp_model_probing_level = 0
        solver.parameters.stop_after_first_solution = True
        started = time.monotonic()
        status_code = solver.Solve(model)
        elapsed = time.monotonic() - started
        status = solver.StatusName(status_code)
        solves.append({
            "iteration": iteration,
            "status": status,
            "elapsed_seconds": elapsed,
            "branches": int(solver.NumBranches()),
            "conflicts": int(solver.NumConflicts()),
        })
        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            vector = tuple(int(solver.Value(projection["count_vars"][template])) for template in TEMPLATES)
            require(vector not in found, "independent body projection duplicate")
            found.add(vector)
            model.AddForbiddenAssignments(projection["ordered_count_vars"], [list(vector)])
            continue
        require(status == "INFEASIBLE", f"body projection replay censored: {status}")
        break
    require(found == EXPECTED_BODY_VECTORS, f"body projection set drift: {found}")
    require(solves[-1]["status"] == "INFEASIBLE", "body projection replay not complete")
    return {
        "status": "COMPLETE",
        "vector_count": len(found),
        "vectors": [list(value) for value in sorted(found)],
        "solves": solves,
        "workers": 1,
        "search_branching": "PSEUDO_COST_SEARCH",
        "symmetry_level": 0,
        "probing_level": 0,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E108 check: {OUTPUT}")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E108 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E108 artifact identity drift: {path}")
        artifact_records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    result = load(RESULT)
    body = load(BODY)
    upper = load(UPPER)
    lower = load(LOWER)
    intersection = load(INTERSECTION)
    require(result["verdict"] == "TEMPLATE_PROJECTION_ATLAS_CENSORED", "verdict drift")
    require(result["decision"] == "CONTINUE_ONLY_INCOMPLETE_PROJECTION_ENUMERATIONS", "decision drift")
    require(body["complete"] is True and body["status"] == "COMPLETE", "body projection incomplete")
    require(body["terminal_status"] == "INFEASIBLE", "body terminal drift")
    require(vector_set(body) == EXPECTED_BODY_VECTORS, "body vector set drift")
    require(upper["complete"] is False and upper["terminal_status"] == "UNKNOWN", "upper status drift")
    require(lower["complete"] is False and lower["terminal_status"] == "UNKNOWN", "lower status drift")
    require(intersection["complete"] is False, "partial intersection marked complete")
    require(set(intersection["survivor_upper_vectors"]) == set(), "partial intersection payload drift")
    require(EXPECTED_BODY_VECTORS - KNOWN_NOGOODS == EXPECTED_REMAINING, "remaining split arithmetic drift")
    e107 = load(E107_CHECK)
    require(e107["classification"] == "OPEN_SPLIT_CLOSED_BY_DIRECT_LOWER_INFEASIBILITY", "E107 check drift")

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "zmd_e108_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e108_check_e100")
    e104 = source_module(E104_RUNNER, "zmd_e108_check_e104")
    e108 = source_module(RUNNER, "zmd_e108_check_runner")
    prepared = e104.reconstruct(e095=e095, e100=e100)

    body_witness_replay = replay_witness(
        e095=e095, prepared=prepared, payload=body, side=None
    )
    upper_witness_replay = replay_witness(
        e095=e095, prepared=prepared, payload=upper, side="upper"
    )
    lower_witness_replay = replay_witness(
        e095=e095, prepared=prepared, payload=lower, side="lower"
    )
    independent_body = replay_body_projection(e108, prepared)

    payload = {
        "schema": "zmd_e108_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "SEVEN_VECTOR_BODY_PROJECTION_COMPLETE_SIDE_PROJECTIONS_CENSORED",
        "artifact_records": artifact_records,
        "body_witness_replay": body_witness_replay,
        "upper_partial_witness_replay": upper_witness_replay,
        "lower_partial_witness_replay": lower_witness_replay,
        "independent_body_projection": independent_body,
        "exact_body_vectors": [list(value) for value in sorted(EXPECTED_BODY_VECTORS)],
        "known_split_nogoods": [list(value) for value in sorted(KNOWN_NOGOODS)],
        "remaining_body_feasible_vectors": [list(value) for value in sorted(EXPECTED_REMAINING)],
        "verdict": result["verdict"],
        "decision": "TEST_ONLY_TWO_REMAINING_BODY_FEASIBLE_SPLITS",
        "truth_boundary": (
            "The body/power projection is exact and complete. Upper/lower native-front "
            "projection enumerations remain censored; their positive witnesses are replayed "
            "but their absent vectors carry no meaning. Prior exact split nogoods reduce the "
            "seven body-feasible vectors to two direct test targets."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(json.dumps({
        "status": "PASS",
        "classification": payload["classification"],
        "body_vector_count": 7,
        "remaining_vectors": payload["remaining_body_feasible_vectors"],
        "decision": payload["decision"],
        "output_path": str(OUTPUT.relative_to(ROOT)),
        "output_sha256": sha256(OUTPUT),
    }, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
