#!/usr/bin/env python3
"""Independent no-solver replay for E095's decomposition and module-A witness."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E095_y41_module_product_decomposition/run-001"
)
RUNNER = Path(__file__).with_name("run_e095.py")
AUDIT = RUN / "DECOMPOSITION_AUDIT.json"
MODULE_A = RUN / "MODULE_A_RESULT.json"
MODULE_B = RUN / "MODULE_B_RESULT.json"
RESULT = RUN / "RESULT.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
ANCHOR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E092_pareto_three_pole_admission_atlas/run-001/"
    "state-00-partition_90abd29523f2a0dc/RESULT.json"
)
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
MANDATORY = HISTORY / "data/preprocessed/mandatory_exact_instances.json"

EXPECTED = {
    RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    AUDIT: "7db4313765c04a08999672803204f08df1207031ebafb7cb8d937202a9b57b71",
    MODULE_A: "a8ced4827348ed6151157f7de58ff9ffefb50ad88005a1191f359ba9f2da4148",
    MODULE_B: "c97697a1240754d60519ee2815e0b6b87274ce43f73a39877b15614872416a14",
    RESULT: "78de6850a02e66d1018a6f3f3ec545d624e16bdc0cf7e4ef1b455ea2eb25e609",
    ANCHOR: "7bc3cc6ccd48f919e08561c7b32262da56f9f3853d5fbca313413add4bd87a78",
    FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    MANDATORY: "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
}
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)
SEAM_Y = 41
BOUNDARY_INDEX = 8


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


def in_grid(value: tuple[int, int]) -> bool:
    return 0 <= value[0] < 70 and 0 <= value[1] < 70


def collect_instances(value: Any) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}

    def visit(current: Any) -> None:
        if isinstance(current, Mapping):
            if "instance_id" in current and "facility_type" in current:
                output[str(current["instance_id"])] = dict(current)
            for member in current.values():
                visit(member)
        elif isinstance(current, Sequence) and not isinstance(
            current, (str, bytes, bytearray)
        ):
            for member in current:
                visit(member)

    visit(value)
    return output


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def geometry() -> dict[str, Any]:
    pools = load(CANDIDATES)["facility_pools"]
    parent = load(PARENT)["solution"]
    macro = load(MACRO)
    anchor = load(ANCHOR)
    frontier = load(FRONTIER)
    partition = {
        row["partition"]["partition_id"]: row
        for row in frontier["detailed_candidates"]
    }["partition_90abd29523f2a0dc"]["partition"]
    module_operations = {
        "A": set(map(str, partition["module_a_operations"])),
        "B": set(map(str, partition["module_b_operations"])),
    }

    core_body: set[tuple[int, int]] = set()
    core_fronts: set[tuple[int, int]] = set()
    for row in parent.values():
        template = str(row["facility_type"])
        if template != "protocol_core":
            continue
        pose = pools[template][int(row["pose_idx"])]
        core_body = {cell(value) for value in pose["occupied_cells"]}
        core_fronts = {
            cell(value)
            for field in ("input_port_cells", "output_port_cells")
            for value in pose[field]
        }
    require(bool(core_body) and bool(core_fronts), "protocol-core geometry missing")

    pole_body: set[tuple[int, int]] = set()
    coverage: set[tuple[int, int]] = set()
    for row in anchor["selected_poles"]:
        pose = pools["power_pole"][int(row["pose_index"])]
        body = {cell(value) for value in pose["occupied_cells"]}
        require(not pole_body & body, "fixed poles overlap")
        pole_body |= body
        coverage |= {cell(value) for value in pose["power_coverage_cells"]}

    state = macro["states"][BOUNDARY_INDEX]
    require(state["state_id"] == "boundary_macro_09", "boundary identity drift")
    boundary_body = {cell(value) for value in state["body_cells"]}
    boundary_fronts = {cell(value) for value in state["front_cells"]}
    seam = {(x, SEAM_Y) for x in range(1, 69)}
    fixed_solid = core_body | pole_body | boundary_body
    forbidden = (
        core_body
        | core_fronts
        | pole_body
        | boundary_body
        | boundary_fronts
        | seam
    )

    modes: dict[str, dict[tuple[tuple[int, int], ...], tuple[int, ...]]] = {}
    for template in TEMPLATES:
        grouped: dict[tuple[tuple[int, int], ...], list[int]] = defaultdict(list)
        for pose_index, pose in enumerate(pools[template]):
            body = tuple(sorted(cell(value) for value in pose["occupied_cells"]))
            grouped[body].append(int(pose_index))
        modes[template] = {
            body: tuple(indices) for body, indices in grouped.items()
        }

    rows: dict[str, list[dict[str, Any]]] = {"A": [], "B": []}
    for module, side in (("A", "low"), ("B", "high")):
        for template in TEMPLATES:
            for body, pose_indices in modes[template].items():
                ys = [value[1] for value in body]
                if side == "low" and max(ys) >= SEAM_Y:
                    continue
                if side == "high" and min(ys) <= SEAM_Y:
                    continue
                if set(body) & forbidden:
                    continue
                rows[module].append(
                    {
                        "template": template,
                        "body": body,
                        "pose_indices": pose_indices,
                    }
                )
    return {
        "pools": pools,
        "rows": rows,
        "fixed_solid": fixed_solid,
        "forbidden": forbidden,
        "coverage": coverage,
        "module_operations": module_operations,
    }


def product_replay(ctx: Mapping[str, Any], audit: Mapping[str, Any]) -> dict[str, Any]:
    body_unions: dict[str, set[tuple[int, int]]] = {}
    front_unions: dict[str, set[tuple[int, int]]] = {}
    for module in ("A", "B"):
        body_unions[module] = {
            value for row in ctx["rows"][module] for value in row["body"]
        }
        fronts: set[tuple[int, int]] = set()
        for row in ctx["rows"][module]:
            for pose_index in row["pose_indices"]:
                pose = ctx["pools"][row["template"]][pose_index]
                for field in ("input_port_cells", "output_port_cells"):
                    fronts.update(
                        value
                        for raw in pose[field]
                        for value in [cell(raw)]
                        if in_grid(value)
                    )
        front_unions[module] = fronts
    observed = {
        "module_candidate_counts": {
            module: len(ctx["rows"][module]) for module in ("A", "B")
        },
        "cross_body_cell_count": len(body_unions["A"] & body_unions["B"]),
        "a_front_b_body_intersection_count": len(
            front_unions["A"] & body_unions["B"]
        ),
        "b_front_a_body_intersection_count": len(
            front_unions["B"] & body_unions["A"]
        ),
        "cross_front_front_intersection_count": len(
            front_unions["A"] & front_unions["B"]
        ),
    }
    require(
        observed["module_candidate_counts"] == audit["module_candidate_counts"],
        "module candidate count replay drift",
    )
    for key in (
        "cross_body_cell_count",
        "a_front_b_body_intersection_count",
        "b_front_a_body_intersection_count",
        "cross_front_front_intersection_count",
    ):
        require(int(observed[key]) == int(audit[key]), f"product replay drift: {key}")
    require(
        not observed["cross_body_cell_count"]
        and not observed["a_front_b_body_intersection_count"]
        and not observed["b_front_a_body_intersection_count"],
        "product decomposition is not exact",
    )
    return observed


def replay_a_witness(ctx: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    require(result["status"] == "OPTIMAL", "module A is not OPTIMAL")
    selected = [dict(row) for row in result["selected_manufacturing"]]
    require(len(selected) == 128, "module A selected count drift")
    occupied = set(ctx["fixed_solid"])
    for index, row in enumerate(selected):
        body = {cell(value) for value in row["body"]}
        require(not body & ctx["forbidden"], f"A body hits forbidden cells: {index}")
        require(not body & occupied, f"A body overlap: {index}")
        occupied |= body

    mandatory = collect_instances(load(MANDATORY))
    expected_operations = Counter(
        str(row["operation_type"])
        for row in mandatory.values()
        if str(row.get("operation_type", "")) in ctx["module_operations"]["A"]
    )
    observed_operations = Counter(str(row["operation"]) for row in selected)
    require(observed_operations == expected_operations, "A operation multiset drift")

    unpowered = 0
    front_failures = 0
    for row in selected:
        body = {cell(value) for value in row["body"]}
        unpowered += int(not bool(body & ctx["coverage"]))
        pose = ctx["pools"][str(row["template"])][int(row["pose_index"])]
        free_in = [
            value
            for raw in pose["input_port_cells"]
            for value in [cell(raw)]
            if in_grid(value) and value not in occupied
        ]
        free_out = [
            value
            for raw in pose["output_port_cells"]
            for value in [cell(raw)]
            if in_grid(value) and value not in occupied
        ]
        front_failures += int(
            len(free_in) < int(row["need_in"])
            or len(free_out) < int(row["need_out"])
        )
    require(unpowered == 0, "A witness has unpowered bodies")
    require(front_failures == 0, "A witness has front failures")
    return {
        "selected_body_count": len(selected),
        "operation_count": sum(observed_operations.values()),
        "unpowered_count": unpowered,
        "front_failure_count": front_failures,
        "occupied_cell_count": len(occupied),
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E095 artifact check: {OUTPUT}")
    records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"artifact identity drift: {path}")
        records[str(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}

    audit = load(AUDIT)
    module_a = load(MODULE_A)
    module_b = load(MODULE_B)
    result = load(RESULT)
    require(audit["status"] == "PASS", "decomposition audit is not PASS")
    require(
        audit["exact_product_for_native_front_layer"] is True,
        "product audit did not establish exactness",
    )
    require(module_b["status"] == "UNKNOWN", "module B status drift")
    require("selected_manufacturing" not in module_b, "UNKNOWN B carries a witness")
    require(
        result["verdict"] == "MODULE_B_FRONT_SUBMODEL_CENSORED",
        "E095 verdict drift",
    )
    require(
        result["decision"] == "DECOMPOSE_MODULE_B_BY_TEMPLATE_OR_BAY",
        "E095 decision drift",
    )
    require(result["combined_witness"] is None, "censored E095 carries combined witness")

    ctx = geometry()
    product = product_replay(ctx, audit)
    a_replay = replay_a_witness(ctx, module_a)
    payload = {
        "schema": "zmd_e095_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "artifact_records": records,
        "decomposition_replay": product,
        "module_a_witness_replay": a_replay,
        "module_b": {
            "status": module_b["status"],
            "elapsed_seconds": module_b["elapsed_seconds"],
            "branches": module_b["branches"],
            "conflicts": module_b["conflicts"],
            "selected_body_count": 0,
        },
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent no-solver replay of product geometry and the positive A "
            "native-front witness. B remains solver UNKNOWN; no combined witness exists."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "verdict": payload["verdict"],
                "decision": payload["decision"],
                "a_selected": a_replay["selected_body_count"],
                "b_status": payload["module_b"]["status"],
                "output_path": str(OUTPUT.relative_to(ROOT)),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
