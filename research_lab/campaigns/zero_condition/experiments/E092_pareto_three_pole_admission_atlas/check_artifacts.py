#!/usr/bin/env python3
"""Independent aggregation and positive-witness replay for E092."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e092.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001"
)
RESULT = RUN / "RESULT.json"
ATLAS = RUN / "ADMISSION_ATLAS.json"
DERIVATION = RUN / "DERIVATION.json"
DERIVED = RUN / "DERIVED_PRODUCER.py"
FRONTIER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E081_axis_seam_recolor_frontier/run-001/AXIS_SEAM_FRONTIER.json"
)
PARENT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
MACRO = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E079_k47_boundary_macro/run-001/BOUNDARY_MACRO_V1.json"
)
CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "96ae1d44a8af043c190cd8d2cc942e91aff172359bf9fd660bfd8562e7e13790",
    RESULT: "e60aaf29ff4b2db9e965c1d7c1932797099b3bd9a91759067821f49b8063e909",
    ATLAS: "d2f9db1ff9828f6a13a6278922fc02ddd722a57c36e5497009cb4705c0ad4464",
    DERIVATION: "2069f4b9fc479f98b42a80ce000f480728e8621dce31750cd406cb6d77255e93",
    DERIVED: "306ccf5da973b97710ee6cf13c3190cc32c4c0ce3236fd581a75a756020b2e1c",
    FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cell(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def cells(values: Iterable[Any]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(cell(value) for value in values))


def dump_exclusive(path: Path, payload: Any) -> None:
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def no_overlap(named: Sequence[tuple[str, set[tuple[int, int]]]]) -> int:
    owner: dict[tuple[int, int], str] = {}
    for name, body in named:
        require(bool(body), f"empty solid body: {name}")
        for value in body:
            prior = owner.get(value)
            require(prior is None, f"solid overlap at {value}: {prior}/{name}")
            owner[value] = name
    return len(owner)


def replay_positive(record: Mapping[str, Any]) -> dict[str, Any]:
    state_result = load(ROOT / str(record["result_path"]))
    require(state_result["status"] == "BODY_POWER_FEASIBLE", "positive status drift")
    bodies = [dict(row) for row in state_result["selected_manufacturing"]]
    poles = [dict(row) for row in state_result["selected_poles"]]
    require(len(bodies) == 219, "positive body count drift")
    require(len(poles) == 53, "positive pole count drift")

    frontier = load(FRONTIER)
    rows = [
        row
        for row in frontier["detailed_candidates"]
        if row["partition"]["partition_id"] == record["partition_id"]
    ]
    require(len(rows) == 1, "positive partition multiplicity drift")
    partition_row = rows[0]
    partition = partition_row["partition"]
    evaluation = partition_row["best_reference_preserving"]
    corridor = evaluation["corridor"]
    axis = str(corridor["axis"])
    coordinate = int(corridor["start"])
    module_low = str(corridor["module_low"])
    module_high = str(corridor["module_high"])

    expected_counts = {
        ("A", template): int(count)
        for template, count in partition["module_a_template_counts"].items()
    } | {
        ("B", template): int(count)
        for template, count in partition["module_b_template_counts"].items()
    }
    observed_counts = Counter(
        (str(row["module"]), str(row["template"])) for row in bodies
    )
    require(dict(observed_counts) == expected_counts, "module/template count drift")

    for index, row in enumerate(bodies):
        body = cells(row["body"])
        values = [y if axis == "y" else x for x, y in body]
        module = str(row["module"])
        require(module in {module_low, module_high}, f"invalid module: {module}")
        if module == module_low:
            require(max(values) < coordinate, f"low-side violation: {index}")
        else:
            require(min(values) > coordinate, f"high-side violation: {index}")

    pools = load(CANDIDATES)["facility_pools"]
    parent = load(PARENT)["solution"]
    core_rows = [
        row for row in parent.values() if str(row["facility_type"]) == "protocol_core"
    ]
    require(len(core_rows) == 1, "protocol core count drift")
    core_pose = pools["protocol_core"][int(core_rows[0]["pose_idx"])]
    core_body = set(cells(core_pose["occupied_cells"]))
    core_fronts = {
        cell(value)
        for field in ("input_port_cells", "output_port_cells")
        for value in core_pose[field]
    }
    corridor_cells = (
        {(x, coordinate) for x in range(1, 69)}
        if axis == "y"
        else {(coordinate, y) for y in range(1, 69)}
    )

    macro = load(MACRO)
    state_index = int(state_result["selected_boundary_state_index"])
    state = macro["states"][state_index]
    require(
        str(state["state_id"]) == str(state_result["selected_boundary_state_id"]),
        "boundary state identity drift",
    )
    boundary_body = {cell(value) for value in state["body_cells"]}
    boundary_fronts = {cell(value) for value in state["front_cells"]}
    reserved_free = core_fronts | corridor_cells | boundary_fronts

    solids: list[tuple[str, set[tuple[int, int]]]] = [
        ("protocol_core", core_body),
        ("boundary_body", boundary_body),
    ]
    solids.extend(
        (f"manufacturing::{index}", set(cells(row["body"])))
        for index, row in enumerate(bodies)
    )

    current_poles = {
        int(row["pose_idx"])
        for row in parent.values()
        if str(row["facility_type"]) == "power_pole"
    }
    selected_pole_indices: set[int] = set()
    coverage: set[tuple[int, int]] = set()
    for index, row in enumerate(poles):
        pose_index = int(row["pose_index"])
        require(pose_index not in selected_pole_indices, "duplicate selected pole")
        selected_pole_indices.add(pose_index)
        pose = pools["power_pole"][pose_index]
        pole_body = set(cells(pose["occupied_cells"]))
        require(pole_body == set(cells(row["body"])), "pole body drift")
        solids.append((f"pole::{index}", pole_body))
        coverage.update(cell(value) for value in pose["power_coverage_cells"])
    retained_poles = len(selected_pole_indices & current_poles)
    require(retained_poles >= 50, "three-pole budget violated")
    require(53 - retained_poles == int(state_result["relocated_pole_count"]), "pole count report drift")

    occupied_count = no_overlap(solids)
    for name, body in solids:
        overlap = body & reserved_free
        require(not overlap, f"solid intersects reserved-free cells: {name}:{sorted(overlap)}")

    unpowered = [
        index
        for index, row in enumerate(bodies)
        if not set(cells(row["body"])) & coverage
    ]
    require(not unpowered, f"unpowered manufacturing bodies: {unpowered}")

    stable_parent = {}
    for instance_id in ("grinder_dense_source_001", "grinder_fine_buckwheat_002"):
        row = parent[instance_id]
        pose = pools[str(row["facility_type"])][int(row["pose_idx"])]
        stable_parent[instance_id] = cells(pose["occupied_cells"])
    selected = {
        (str(row["module"]), str(row["template"]), cells(row["body"]))
        for row in bodies
    }
    stable_modules = {
        str(item["target_module"])
        for item in evaluation["reference_rewrite_rows"]
    }
    require(len(stable_modules) == 1, "stable target module drift")
    stable_module = next(iter(stable_modules))
    for instance_id, footprint in stable_parent.items():
        require(
            (stable_module, "manufacturing_6x4", footprint) in selected,
            f"stable body missing: {instance_id}",
        )

    retained_bodies = sum(bool(row["is_current"]) for row in bodies)
    require(retained_bodies == int(state_result["retained_manufacturing_count"]), "retained body report drift")
    return {
        "status": "PASS",
        "partition_id": record["partition_id"],
        "selected_boundary_state_id": state_result["selected_boundary_state_id"],
        "retained_manufacturing_count": retained_bodies,
        "retained_current_pole_count": retained_poles,
        "relocated_pole_count": 53 - retained_poles,
        "occupied_solid_cell_count": occupied_count,
        "reserved_free_cell_count": len(reserved_free),
    }


def main() -> int:
    require(not OUTPUT.exists(), "refusing to overwrite E092 artifact check")
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E092 artifact: {path}")
        require(sha256(path) == expected, f"E092 artifact identity drift: {path}")
    result = load(RESULT)
    atlas = load(ATLAS)
    require(result["verdict"] == "Y41_ONLY_OBSERVED_SURVIVOR_WITH_CENSORED_ADMISSION_STATES", "verdict drift")
    require(result["decision"] == "RESOLVE_UNKNOWN_ADMISSION_STATES_BEFORE_SELECTING_CARRIER", "decision drift")
    require(result["calibration"]["pass"] is True, "calibration drift")
    require(atlas["records"] == result["records"], "atlas/result record drift")
    require(len(result["records"]) == 7, "state count drift")

    for record in result["records"]:
        path = ROOT / str(record["result_path"])
        require(path.is_file(), f"missing state result: {path}")
        require(sha256(path) == str(record["result_sha256"]), "state result hash drift")
        state_result = load(path)
        require(state_result["status"] == record["status"], "state status drift")
        if record["status"] == "BODY_POWER_FEASIBLE":
            require(len(state_result.get("selected_manufacturing", [])) == 219, "positive body count drift")
            require(len(state_result.get("selected_poles", [])) == 53, "positive pole count drift")
        else:
            require(not state_result.get("selected_manufacturing"), "nonpositive body witness")
            require(not state_result.get("selected_poles"), "nonpositive pole witness")

    require(result["admitted_partition_ids"] == ["partition_90abd29523f2a0dc"], "admitted set drift")
    require(result["unknown_partition_ids"] == ["partition_5a72220e0268a3c1"], "unknown set drift")
    require(len(result["infeasible_partition_ids"]) == 5, "infeasible set drift")

    positive_record = next(
        row for row in result["records"] if row["status"] == "BODY_POWER_FEASIBLE"
    )
    positive_replay = replay_positive(positive_record)
    source = DERIVED.read_text(encoding="utf-8")
    compile(source, str(DERIVED), "exec")
    require("CORRIDOR_AXIS" in source and "MODULE_LOW" in source, "generic state controls absent")
    require("sum(current_pole_vars)" in source, "pole floor absent")
    require("solver.parameters.stop_after_first_solution = True" in source, "first-solution control absent")
    require("model.Maximize(" not in source, "objective unexpectedly remains")

    payload = {
        "schema": "zmd_e092_pareto_three_pole_admission_artifact_check_v1",
        "status": "PASS",
        "classification": "CALIBRATED_FINITE_ADMISSION_ATLAS_WITH_ONE_CENSORED_STATE",
        "verdict": result["verdict"],
        "decision": result["decision"],
        "calibration": result["calibration"],
        "positive_replay": positive_replay,
        "admitted_partition_ids": result["admitted_partition_ids"],
        "infeasible_partition_ids": result["infeasible_partition_ids"],
        "unknown_partition_ids": result["unknown_partition_ids"],
        "truth_boundary": (
            "The positive body/pole/power witness is independently replayed without "
            "optimization. Negative and UNKNOWN statuses remain frozen producer "
            "records; no native-front or downstream claim is made."
        ),
        "ledger_effect": "none",
    }
    dump_exclusive(OUTPUT, payload)
    print(json.dumps({"status": payload["status"], "classification": payload["classification"], "positive_partition": positive_replay["partition_id"], "unknown_partition_ids": payload["unknown_partition_ids"], "output_path": str(OUTPUT.relative_to(ROOT)), "output_sha256": sha256(OUTPUT)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
