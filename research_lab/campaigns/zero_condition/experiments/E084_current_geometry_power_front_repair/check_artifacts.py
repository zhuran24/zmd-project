#!/usr/bin/env python3
"""No-solver checker for the landed E084 probe artifacts.

The checker preserves each producer status exactly, independently replays all
materialized positive geometry/power witnesses, and verifies the named empty
front domains.  It does not rerun any optimization or reinterpret UNKNOWN.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
LOCAL = ROOT / "research_lab/local/zero_condition"
OUT = (
    LOCAL
    / "E084_current_geometry_power_front_repair/run-001/ARTIFACT_CHECK.json"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.port_binding import (  # noqa: E402
    enumerate_pose_level_port_bindings_with_cache_info,
)
from src.preprocess.operation_profiles import get_operation_port_profile  # noqa: E402

E081_RESULT = (
    LOCAL / "E081_axis_seam_recolor_frontier/run-001/RESULT.json"
)
E081_FRONTIER = (
    LOCAL / "E081_axis_seam_recolor_frontier/run-001/AXIS_SEAM_FRONTIER.json"
)
E069_PARENT = (
    LOCAL / "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
E079_MACRO = LOCAL / "E079_k47_boundary_macro/run-001/BOUNDARY_MACRO_V1.json"
IDENTITY_AUDIT = (
    LOCAL / "E079_E080_identity_incident_20260828/AUDIT.json"
)
CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"
MANDATORY = HISTORY / "data/preprocessed/mandatory_exact_instances.json"
STRICT = (
    ROOT
    / "docs/research/cleanroom_rederivation_20260718/strict/external/"
    "problem_instance.json"
)

RESULT_FILES = {
    "body_only": LOCAL / "E084_full_setpacking_probe_result.json",
    "fixed_52_power_check": LOCAL / "E084_power_probe_result.json",
    "one_replacement_power": LOCAL / "E084_power_integrated_probe_result.json",
    "all_poles_manufacturing": (
        LOCAL / "E084_integrated_power_setpacking_manufacturing.json"
    ),
    "all_poles_total": LOCAL / "E084_integrated_power_setpacking_total.json",
    "all_poles_area": LOCAL / "E084_integrated_power_setpacking_area.json",
    "fixed_witness_front_domains": LOCAL / "E084_front_assignment_probe_result.json",
    "joint_front_model": LOCAL / "E084_integrated_front_setpacking_probe_result.json",
    "early_joint_front_model": LOCAL / "E084_front_integrated_probe_result.json",
    "front_benders_r31": LOCAL / "E084_front_benders_r31_result.json",
    "front_benders_r32": LOCAL / "E084_front_benders_r32_result.json",
    "front_benders_r33": LOCAL / "E084_front_benders_r33_result.json",
    "front_benders_r34": LOCAL / "E084_front_benders_r34_result.json",
    "front_benders_r40": LOCAL / "E084_front_benders_r40_result.json",
    "front_benders_checkpoint": LOCAL / "E084_front_benders_checkpoint.json",
}

SCRIPT_FILES = {
    "body_only": LOCAL / "E084_full_setpacking_probe.py",
    "fixed_52_power_check": LOCAL / "E084_power_probe.py",
    "one_replacement_power": LOCAL / "E084_power_integrated_probe.py",
    "all_poles": LOCAL / "E084_integrated_power_setpacking_probe.py",
    "fixed_witness_front_domains": LOCAL / "E084_front_assignment_probe.py",
    "joint_front_model": LOCAL / "E084_integrated_front_setpacking_probe.py",
    "front_benders": LOCAL / "E084_front_benders.py",
    "terminal_binding_unfinished": LOCAL / "E084_terminal_binding_probe.py",
    "global_binding_unfinished": LOCAL / "E084_global_binding_probe.py",
}

EXPECTED_HASHES = {
    E081_RESULT: "e9a53e0a14b34bfac96817f44e29142127007909f934ffabc9d1809572ab0547",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    IDENTITY_AUDIT: "354d58c3206e3e757bbec2bf236256bef7bb4ab2e9811d3534dd521437ba86ad",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    MANDATORY: "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    STRICT: "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    RESULT_FILES["body_only"]: "2cf5427cf61bea0e94575f3580fa94e86a4121af42e5c04fbab7f152463dd423",
    RESULT_FILES["fixed_52_power_check"]: "b48dfbe47a2c2f670856c0474faa87dad89930c630e3233774c2b1f67ff1a874",
    RESULT_FILES["one_replacement_power"]: "b7628db5b8db5337eb43b1378f1d81e5a731fc4e102faa3cc5b342af4f575d1f",
    RESULT_FILES["all_poles_manufacturing"]: "abbb45b2caaa20efd09e3eeda10194b96ac7d4df7366229370745a86af4a1b3b",
    RESULT_FILES["all_poles_total"]: "2fd3826610845b80ba19e5e78e0435e56d0685447e678679da3c5845ffbd677e",
    RESULT_FILES["all_poles_area"]: "39e527ca310955d32b418e48e5abe9c9a1f28d94db46f250c6f32e066b36ed29",
    RESULT_FILES["fixed_witness_front_domains"]: "fccae16daa4b297052ce194eb1c8c88c4bdc04f4664afbd0a215c35b4334ba21",
    RESULT_FILES["joint_front_model"]: "5fe598ff47122dd22f9f31b4bd78eab5d39c65d1bea3293172b5b90859173261",
    RESULT_FILES["early_joint_front_model"]: "b43e069beb86363feeaa7abf87bd417cd193b0ee25cf00c1b48a180f1a1b1276",
    RESULT_FILES["front_benders_r31"]: "b83a94d6a4d44e04a56c0137728b28aeab55b86f7ed563849990b3f015711894",
    RESULT_FILES["front_benders_r32"]: "85e8d03d541530528805c53ccfa44be9b6c6fe78156bdb910edf48e8f23c6330",
    RESULT_FILES["front_benders_r33"]: "56970e1dd178c0bbf5d886bc50b4b072178cf883a625e9adeb38fb6aa76220c3",
    RESULT_FILES["front_benders_r34"]: "394827325ff9f5c4e3e6dac022443032471af1e364874a9d92672dd3144f0e25",
    RESULT_FILES["front_benders_r40"]: "0facf5c2f02f3f8ce2ce3ed261b5838a0f5573c2cc8db3e6255d1252772bb784",
    RESULT_FILES["front_benders_checkpoint"]: "0648bf057670c454d1c55a73417d127867c597063362407fe732c4a1b4c6ad9d",
    SCRIPT_FILES["body_only"]: "d203c11e41883d9945c0477ac039789153af2c71c983d3ffd17bbf383c00583c",
    SCRIPT_FILES["fixed_52_power_check"]: "504becce8c1a7fe11dd90eff5c9c8a6f7ebe4211d24ad687e50567bd18387f09",
    SCRIPT_FILES["one_replacement_power"]: "aaa2704473f04f1efd63f8a3d7a748a8911a0e99bc380799c48269b5ad7b0596",
    SCRIPT_FILES["all_poles"]: "5ce50e3a450006461b023ddea4373cf21011eb746c927ca602cb5dc37cae5655",
    SCRIPT_FILES["fixed_witness_front_domains"]: "f70296a9e801ca74a19dcd296419dde4150e6257155445e0ce556a36a74ca5ce",
    SCRIPT_FILES["joint_front_model"]: "163edbe631c091dae35f655bee4826576174b05fa94390542ecfb3ccbcec48ad",
    SCRIPT_FILES["front_benders"]: "1248029a1dc94a3e33a4b51836142a5e189210071ab0f5bb6b40917396766d37",
    SCRIPT_FILES["terminal_binding_unfinished"]: "bd4c8d3e078a02fd72a0c8c7b91d778910af8975cabbbb29d76255f0ac33e473",
    SCRIPT_FILES["global_binding_unfinished"]: "f482ac60d7125530f54a5b600ae5ed424e8fd39594d26a8df502b8d44ec7e1e2",
}

STABLE_OPERATION_BY_DIGEST = {
    "da277903615efb73fbc9bb30716cae3b9b96654bed9905addebba0e27accf33d": (
        "grinder_fine_buckwheat"
    ),
    "ef71d17d5e4db7bb4c3baeeee913780c753409802365896a67988bfcb43176be": (
        "filling_capsule"
    ),
}
STABLE_REFERENCE_IDS = (
    "grinder_dense_source_001",
    "grinder_fine_buckwheat_002",
)
TEMPLATES = (
    "manufacturing_3x3",
    "manufacturing_5x5",
    "manufacturing_6x4",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cell(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def cells(values: Iterable[Any]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(cell(value) for value in values))


def body_digest(body: Sequence[tuple[int, int]]) -> str:
    payload = json.dumps(
        list(body),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def collect_instances(value: Any) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}

    def visit(current: Any) -> None:
        if isinstance(current, Mapping):
            if "instance_id" in current and "facility_type" in current:
                instance_id = str(current["instance_id"])
                row = dict(current)
                prior = output.get(instance_id)
                require(
                    prior is None or prior == row,
                    f"mandatory instance collision: {instance_id}",
                )
                output[instance_id] = row
            for member in current.values():
                visit(member)
        elif isinstance(current, Sequence) and not isinstance(
            current, (str, bytes, bytearray)
        ):
            for member in current:
                visit(member)

    visit(value)
    return output


def no_overlap(named_bodies: Sequence[tuple[str, set[tuple[int, int]]]]) -> int:
    owner_by_cell: dict[tuple[int, int], str] = {}
    for name, body in named_bodies:
        require(body, f"empty body: {name}")
        for value in body:
            prior = owner_by_cell.get(value)
            require(prior is None, f"body overlap at {value}: {prior} / {name}")
            owner_by_cell[value] = name
    return len(owner_by_cell)


def context() -> dict[str, Any]:
    frontier = load_json(E081_FRONTIER)
    detailed = {
        row["partition"]["partition_id"]: row
        for row in frontier["detailed_candidates"]
    }
    winner = detailed[frontier["geometry_winner_partition_id"]]
    evaluation = winner["best_reference_preserving"]
    corridor = evaluation["corridor"]
    require(
        corridor["axis"] == "y"
        and int(corridor["start"]) == 41
        and int(corridor["end"]) == 41
        and corridor["module_low"] == "A"
        and corridor["module_high"] == "B",
        f"E081 corridor drift: {corridor}",
    )
    partition = winner["partition"]
    require(
        partition["partition_id"] == "partition_90abd29523f2a0dc",
        "E081 geometry winner partition drift",
    )
    parent = load_json(E069_PARENT)["solution"]
    pools = load_json(CANDIDATES)["facility_pools"]
    macro = load_json(E079_MACRO)
    require(int(macro["state_count"]) == 47, "E079 state count drift")
    strict = load_json(STRICT)
    for template in TEMPLATES:
        require(
            strict["facility_templates"][template]["requires_power"] is True,
            f"power requirement drift: {template}",
        )
    require(
        strict["facility_templates"]["protocol_core"]["requires_power"] is False,
        "protocol core power requirement drift",
    )

    current_manufacturing: dict[
        tuple[tuple[int, int], ...], dict[str, Any]
    ] = {}
    current_poles: set[int] = set()
    fixed_52_poles: list[tuple[str, set[tuple[int, int]], set[tuple[int, int]]]] = []
    core_body: set[tuple[int, int]] | None = None
    core_fronts: set[tuple[int, int]] = set()
    removed_poles = set(map(str, evaluation["pole_move_ids"]))
    stable_footprints: dict[str, tuple[tuple[int, int], ...]] = {}
    for instance_id, row in parent.items():
        template = str(row["facility_type"])
        pose_index = int(row["pose_idx"])
        pose = pools[template][pose_index]
        body = cells(pose["occupied_cells"])
        if template.startswith("manufacturing_"):
            require(body not in current_manufacturing, f"duplicate footprint: {body}")
            current_manufacturing[body] = {
                "instance_id": str(instance_id),
                "facility_type": template,
            }
            if instance_id in STABLE_REFERENCE_IDS:
                stable_footprints[str(instance_id)] = body
        elif template == "power_pole":
            current_poles.add(pose_index)
            if instance_id not in removed_poles:
                fixed_52_poles.append(
                    (
                        str(instance_id),
                        set(body),
                        {cell(value) for value in pose["power_coverage_cells"]},
                    )
                )
        elif template == "protocol_core":
            require(core_body is None, "duplicate protocol core")
            core_body = set(body)
            core_fronts = {
                cell(value)
                for field in ("input_port_cells", "output_port_cells")
                for value in pose[field]
            }
    require(len(current_manufacturing) == 219, "current manufacturing count drift")
    require(len(current_poles) == 53, "current pole count drift")
    require(len(fixed_52_poles) == 52, "fixed pole count drift")
    require(core_body is not None, "protocol core missing")
    require(set(stable_footprints) == set(STABLE_REFERENCE_IDS), "stable body drift")

    requirements = {
        ("A", template): int(partition["module_a_template_counts"][template])
        for template in TEMPLATES
    } | {
        ("B", template): int(partition["module_b_template_counts"][template])
        for template in TEMPLATES
    }
    require(sum(requirements.values()) == 219, "partition template total drift")
    return {
        "frontier": frontier,
        "evaluation": evaluation,
        "partition": partition,
        "parent": parent,
        "pools": pools,
        "macro": macro,
        "current_manufacturing": current_manufacturing,
        "current_poles": current_poles,
        "fixed_52_poles": fixed_52_poles,
        "core_body": core_body,
        "core_fronts": core_fronts,
        "stable_footprints": stable_footprints,
        "requirements": requirements,
        "corridor": {(x, 41) for x in range(1, 69)},
    }


def boundary_state(ctx: Mapping[str, Any], result: Mapping[str, Any]) -> Mapping[str, Any]:
    index = int(result["selected_boundary_state_index"])
    state = ctx["macro"]["states"][index]
    require(str(state["state_id"]) == str(result["selected_boundary_state_id"]), "boundary state ID drift")
    return state


def selected_body_rows(
    result: Mapping[str, Any],
    field: str,
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in result[field]]
    require(len(rows) == 219, f"{field} cardinality drift: {len(rows)}")
    return rows


def verify_module_counts(
    rows: Sequence[Mapping[str, Any]],
    requirements: Mapping[tuple[str, str], int],
) -> None:
    observed = Counter(
        (str(row["module"]), str(row["template"])) for row in rows
    )
    require(dict(observed) == dict(requirements), f"module/template count drift: {observed}")


def verify_stable_bodies(
    rows: Sequence[Mapping[str, Any]],
    stable_footprints: Mapping[str, tuple[tuple[int, int], ...]],
) -> None:
    selected = {
        (str(row["module"]), str(row["template"]), cells(row["body"]))
        for row in rows
    }
    for instance_id, footprint in stable_footprints.items():
        require(
            ("B", "manufacturing_6x4", footprint) in selected,
            f"stable E078 body absent: {instance_id}",
        )


def fixed_context_geometry(
    ctx: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    include_fixed_poles: bool,
) -> tuple[
    list[tuple[str, set[tuple[int, int]]]],
    dict[str, set[tuple[int, int]]],
]:
    solids = [
        ("protocol_core", set(ctx["core_body"])),
        ("boundary_body", {cell(value) for value in state["body_cells"]}),
    ]
    if include_fixed_poles:
        solids.extend(
            (f"fixed_pole::{name}", body)
            for name, body, _coverage in ctx["fixed_52_poles"]
        )
    reservations = {
        "protocol_core_fronts": set(ctx["core_fronts"]),
        "corridor_y41": set(ctx["corridor"]),
        "boundary_fronts": {cell(value) for value in state["front_cells"]},
    }
    return solids, reservations


def verify_solids_and_reservations(
    solids: Sequence[tuple[str, set[tuple[int, int]]]],
    reservations: Mapping[str, set[tuple[int, int]]],
    *,
    allow_fixed_poles_on_core_fronts: bool,
) -> tuple[int, int]:
    occupied_count = no_overlap(solids)
    for name, body in solids:
        for reservation_name, reserved_cells in reservations.items():
            overlap = body & reserved_cells
            if (
                overlap
                and allow_fixed_poles_on_core_fronts
                and name.startswith("fixed_pole::")
                and reservation_name == "protocol_core_fronts"
            ):
                continue
            require(
                not overlap,
                "solid intersects a reserved-free cell: "
                f"{name} / {reservation_name}: {sorted(overlap)}",
            )
    reservation_union = set().union(*reservations.values())
    return occupied_count, len(reservation_union)


def verify_body_only(ctx: Mapping[str, Any]) -> dict[str, Any]:
    result = load_json(RESULT_FILES["body_only"])
    require(result["status"] == "OPTIMAL", "body-only status is not OPTIMAL")
    require(float(result["best_bound"]) == 189.0, "body-only bound drift")
    require(int(result["objective_retained_current_footprints"]) == 189, "body-only objective drift")
    require(int(result["retained_count"]) == 189, "body-only retained drift")
    require(int(result["moved_manufacturing_count"]) == 30, "body-only moved drift")
    rows = selected_body_rows(result, "selected")
    verify_module_counts(rows, ctx["requirements"])
    verify_stable_bodies(rows, ctx["stable_footprints"])
    state = boundary_state(ctx, result)
    solids, reservations = fixed_context_geometry(
        ctx,
        state,
        include_fixed_poles=True,
    )
    solids.extend(
        (f"manufacturing::{index}", set(cells(row["body"])))
        for index, row in enumerate(rows)
    )
    occupied_count, reserved_count = verify_solids_and_reservations(
        solids,
        reservations,
        allow_fixed_poles_on_core_fronts=True,
    )
    current = ctx["current_manufacturing"]
    retained = sum(cells(row["body"]) in current for row in rows)
    require(retained == 189, "body-only current-footprint recount drift")
    return {
        "status": "PASS",
        "retained_current_manufacturing": retained,
        "moved_manufacturing": 219 - retained,
        "selected_boundary_state_id": result["selected_boundary_state_id"],
        "occupied_solid_cell_count": occupied_count,
        "reserved_free_cell_count": reserved_count,
    }


def verify_one_replacement(ctx: Mapping[str, Any]) -> dict[str, Any]:
    result = load_json(RESULT_FILES["one_replacement_power"])
    require(result["status"] == "OPTIMAL", "one-replacement status is not OPTIMAL")
    require(float(result["best_bound"]) == 188.0, "one-replacement bound drift")
    require(int(result["objective_retained_current_footprints"]) == 188, "one-replacement objective drift")
    require(int(result["moved_manufacturing_count"]) == 31, "one-replacement moved drift")
    rows = selected_body_rows(result, "selected_manufacturing")
    verify_module_counts(rows, ctx["requirements"])
    verify_stable_bodies(rows, ctx["stable_footprints"])
    state = boundary_state(ctx, result)
    replacement = result["selected_replacement_pole"]
    replacement_pose = ctx["pools"]["power_pole"][int(replacement["pose_index"])]
    replacement_body = set(cells(replacement_pose["occupied_cells"]))
    require(
        replacement_body == set(cells(replacement["body"])),
        "replacement pole body drift",
    )
    solids, reservations = fixed_context_geometry(
        ctx,
        state,
        include_fixed_poles=True,
    )
    solids.append(("replacement_pole", replacement_body))
    solids.extend(
        (f"manufacturing::{index}", set(cells(row["body"])))
        for index, row in enumerate(rows)
    )
    verify_solids_and_reservations(
        solids,
        reservations,
        allow_fixed_poles_on_core_fronts=True,
    )
    coverage = set().union(
        *(coverage for _name, _body, coverage in ctx["fixed_52_poles"]),
        {cell(value) for value in replacement_pose["power_coverage_cells"]},
    )
    unpowered = [
        index
        for index, row in enumerate(rows)
        if not set(cells(row["body"])) & coverage
    ]
    require(not unpowered, f"one-replacement unpowered bodies: {unpowered}")
    retained = sum(cells(row["body"]) in ctx["current_manufacturing"] for row in rows)
    require(retained == 188, "one-replacement retained recount drift")
    return {
        "status": "PASS",
        "retained_current_manufacturing": retained,
        "moved_manufacturing": 219 - retained,
        "replacement_pole_pose_index": int(replacement["pose_index"]),
        "selected_boundary_state_id": result["selected_boundary_state_id"],
    }


def verify_all_poles(
    ctx: Mapping[str, Any],
    *,
    key: str,
    expected: Mapping[str, int],
) -> dict[str, Any]:
    result = load_json(RESULT_FILES[key])
    require(result["primary_status"] == "OPTIMAL", f"{key} primary status drift")
    require(result["secondary_status"] == "OPTIMAL", f"{key} secondary status drift")
    rows = selected_body_rows(result, "selected_manufacturing")
    poles = [dict(row) for row in result["selected_poles"]]
    require(len(poles) == 53, f"{key} pole count drift")
    verify_module_counts(rows, ctx["requirements"])
    verify_stable_bodies(rows, ctx["stable_footprints"])
    state = boundary_state(ctx, result)
    solids, reservations = fixed_context_geometry(
        ctx,
        state,
        include_fixed_poles=False,
    )
    solids.extend(
        (f"manufacturing::{index}", set(cells(row["body"])))
        for index, row in enumerate(rows)
    )
    coverage: set[tuple[int, int]] = set()
    selected_pose_indices: set[int] = set()
    for index, row in enumerate(poles):
        pose_index = int(row["pose_index"])
        require(pose_index not in selected_pose_indices, f"{key} duplicate pole pose")
        selected_pose_indices.add(pose_index)
        pose = ctx["pools"]["power_pole"][pose_index]
        pole_body = set(cells(pose["occupied_cells"]))
        require(pole_body == set(cells(row["body"])), f"{key} pole body drift")
        solids.append((f"pole::{index}", pole_body))
        coverage.update(cell(value) for value in pose["power_coverage_cells"])
    verify_solids_and_reservations(
        solids,
        reservations,
        allow_fixed_poles_on_core_fronts=False,
    )
    unpowered = [
        index
        for index, row in enumerate(rows)
        if not set(cells(row["body"])) & coverage
    ]
    require(not unpowered, f"{key} unpowered manufacturing: {unpowered}")

    retained_manufacturing = sum(
        cells(row["body"]) in ctx["current_manufacturing"] for row in rows
    )
    retained_poles = len(selected_pose_indices & ctx["current_poles"])
    retained_area = sum(
        len(cells(row["body"]))
        for row in rows
        if cells(row["body"]) in ctx["current_manufacturing"]
    ) + 4 * retained_poles
    require(
        retained_manufacturing == expected["retained_manufacturing"],
        f"{key} retained manufacturing drift",
    )
    require(
        retained_poles == expected["retained_poles"],
        f"{key} retained poles drift",
    )
    require(
        int(result["moved_manufacturing_count"]) == 219 - retained_manufacturing,
        f"{key} moved manufacturing report drift",
    )
    require(
        int(result["relocated_pole_count"]) == 53 - retained_poles,
        f"{key} moved pole report drift",
    )
    require(
        int(result["retained_total_body_count"])
        == retained_manufacturing + retained_poles,
        f"{key} retained total body count drift",
    )
    require(
        int(result["retained_total_body_area"]) == retained_area,
        f"{key} retained area drift",
    )
    require(
        int(result["primary_objective_value"]) == expected["primary"],
        f"{key} primary objective drift",
    )
    require(
        int(result["secondary_objective_value"]) == expected["secondary"],
        f"{key} secondary objective drift",
    )
    return {
        "status": "PASS",
        "objective_mode": result["objective_mode"],
        "retained_current_manufacturing": retained_manufacturing,
        "moved_manufacturing": 219 - retained_manufacturing,
        "retained_current_poles": retained_poles,
        "relocated_poles": 53 - retained_poles,
        "retained_total_body_area": retained_area,
        "selected_boundary_state_id": result["selected_boundary_state_id"],
    }


def geometry_occupied(
    ctx: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for row in geometry["selected_manufacturing"]:
        occupied.update(cells(row["body"]))
    for row in geometry["selected_poles"]:
        occupied.update(cells(row["body"]))
    state = boundary_state(ctx, geometry)
    occupied.update(cell(value) for value in state["body_cells"])
    occupied.update(ctx["core_body"])
    return occupied


def usable_pattern_exists(
    ctx: Mapping[str, Any],
    *,
    body: tuple[tuple[int, int], ...],
    module: str,
    template: str,
    digest_value: str,
    occupied: set[tuple[int, int]],
) -> bool:
    operations = [
        str(operation)
        for operation in (
            ctx["partition"]["module_a_operations"]
            if module == "A"
            else ctx["partition"]["module_b_operations"]
        )
        if str(get_operation_port_profile(str(operation)).facility_type) == template
    ]
    forced = STABLE_OPERATION_BY_DIGEST.get(digest_value)
    if forced is not None:
        operations = [operation for operation in operations if operation == forced]
    for pose in ctx["pools"][template]:
        if cells(pose["occupied_cells"]) != body:
            continue
        for operation in operations:
            patterns, _cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
                operation,
                pose,
            )
            for pattern in patterns:
                active = [cell(port) for port in pattern["active_ports"]]
                if all(
                    0 <= value[0] < 70
                    and 0 <= value[1] < 70
                    and value not in occupied
                    for value in active
                ):
                    return True
    return False


def verify_front_domains(ctx: Mapping[str, Any]) -> dict[str, Any]:
    result = load_json(RESULT_FILES["fixed_witness_front_domains"])
    require(
        result["partition_id"] == ctx["partition"]["partition_id"],
        "front assignment partition drift",
    )
    expected_empty = {"manufacturing": 18, "total": 35, "area": 26}
    replayed: dict[str, Any] = {}
    for objective, expected_count in expected_empty.items():
        record = result["records"][objective]
        require(record["status"] == "EMPTY_BODY_DOMAIN", f"{objective} front status drift")
        require(int(record["empty_body_count"]) == expected_count, f"{objective} empty count drift")
        geometry = load_json(
            LOCAL / f"E084_integrated_power_setpacking_{objective}.json"
        )
        selected = list(geometry["selected_manufacturing"])
        occupied = geometry_occupied(ctx, geometry)
        for empty in record["empty_bodies"]:
            index = int(empty["body_index"])
            require(0 <= index < len(selected), f"{objective} empty index drift")
            selected_row = selected[index]
            body = cells(empty["body"])
            require(body == cells(selected_row["body"]), f"{objective} empty body drift")
            require(
                not usable_pattern_exists(
                    ctx,
                    body=body,
                    module=str(empty["module"]),
                    template=str(empty["template"]),
                    digest_value=str(empty["body_digest"]),
                    occupied=occupied,
                ),
                f"{objective} named empty body has a usable pattern: {index}",
            )
        replayed[objective] = {
            "status": "PASS",
            "empty_body_count": expected_count,
            "named_empty_domains_replayed": expected_count,
            "total_raw_pattern_count": int(record["total_raw_pattern_count"]),
            "total_usable_pattern_count": int(record["total_usable_pattern_count"]),
        }
    return replayed


def verify_censored_and_negative_records() -> dict[str, Any]:
    joint = load_json(RESULT_FILES["joint_front_model"])
    early = load_json(RESULT_FILES["early_joint_front_model"])
    require(joint["primary_status"] == "UNKNOWN", "joint front status drift")
    require(early["status"] == "UNKNOWN", "early joint front status drift")

    rungs = {}
    expected = {
        "front_benders_r31": (188, "MASTER_INFEASIBLE"),
        "front_benders_r32": (187, "MASTER_INFEASIBLE"),
        "front_benders_r33": (186, "UNKNOWN"),
        "front_benders_r34": (185, "UNKNOWN"),
        "front_benders_r40": (179, "UNKNOWN"),
    }
    for key, (retained, status) in expected.items():
        row = load_json(RESULT_FILES[key])
        require(int(row["target_retained_current_footprints"]) == retained, f"{key} target drift")
        require(row["status"] == status, f"{key} status drift")
        rungs[key] = {
            "target_retained_current_footprints": retained,
            "target_moved_manufacturing_count": 219 - retained,
            "producer_status": status,
            "independent_solver_replay": False,
            "registered_front_candidate_count": int(
                row["registered_front_candidate_count"]
            ),
        }
    return {
        "joint_all_poles": {
            "producer_status": "UNKNOWN",
            "best_bound_total_retained": float(
                joint["primary_best_bound_total_retained"]
            ),
            "incumbent_present": False,
        },
        "early_one_replacement_joint": {
            "producer_status": "UNKNOWN",
            "best_bound": float(early["best_bound"]),
            "incumbent_present": False,
        },
        "one_replacement_front_benders_rungs": rungs,
    }


def main() -> int:
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        require(path.is_file(), f"missing frozen E084 input/artifact: {path}")
        observed = sha256_file(path)
        require(observed == expected, f"artifact drift: {path}: {observed} != {expected}")
        try:
            display = str(path.relative_to(ROOT))
        except ValueError:
            display = str(path)
        artifact_records[display] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    ctx = context()
    fixed_52 = load_json(RESULT_FILES["fixed_52_power_check"])
    require(
        fixed_52["status"] == "NO_ONE_POLE_REPLACEMENT"
        and int(fixed_52["uncovered_by_fixed_52_count"]) == 2
        and int(fixed_52["legal_one_pole_replacement_count"]) == 0,
        "fixed-geometry one-pole diagnostic drift",
    )

    positive_checks = {
        "body_only": verify_body_only(ctx),
        "one_replacement_power": verify_one_replacement(ctx),
        "all_poles_manufacturing": verify_all_poles(
            ctx,
            key="all_poles_manufacturing",
            expected={
                "retained_manufacturing": 196,
                "retained_poles": 36,
                "primary": 196,
                "secondary": 36,
            },
        ),
        "all_poles_total": verify_all_poles(
            ctx,
            key="all_poles_total",
            expected={
                "retained_manufacturing": 190,
                "retained_poles": 50,
                "primary": 240,
                "secondary": 190,
            },
        ),
        "all_poles_area": verify_all_poles(
            ctx,
            key="all_poles_area",
            expected={
                "retained_manufacturing": 194,
                "retained_poles": 39,
                "primary": 2995,
                "secondary": 233,
            },
        ),
    }
    front_checks = verify_front_domains(ctx)
    censored = verify_censored_and_negative_records()

    terminal_result = LOCAL / "E084_terminal_binding_probe_result.json"
    global_result = LOCAL / "E084_global_binding_probe_result.json"
    require(not terminal_result.exists(), "unexpected terminal-binding result appeared")
    require(not global_result.exists(), "unexpected global-binding result appeared")

    payload = {
        "schema": "zmd_e084_current_geometry_power_front_artifact_check_v1",
        "status": "PASS",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "artifact_records": artifact_records,
        "context": {
            "partition_id": ctx["partition"]["partition_id"],
            "corridor": {
                "axis": "y",
                "coordinate": 41,
                "module_low": "A",
                "module_high": "B",
            },
            "boundary_state_count": 47,
            "current_e079_rerun_identity": EXPECTED_HASHES[E079_MACRO],
            "e079_identity_incident_audit": EXPECTED_HASHES[IDENTITY_AUDIT],
            "stable_reference_ids": list(STABLE_REFERENCE_IDS),
        },
        "positive_witness_replays": positive_checks,
        "fixed_body_only_optimum_power_diagnostic": {
            "producer_status": fixed_52["status"],
            "uncovered_body_count": 2,
            "legal_one_pole_replacement_count": 0,
            "claim_scope": "one selected 30-move body-only optimum only",
        },
        "fixed_witness_front_domain_replays": front_checks,
        "censored_and_producer_negative_records": censored,
        "unfinished_consumers": {
            "terminal_binding_result_present": False,
            "global_binding_result_present": False,
            "effect": "no terminal-uniqueness, generic-I/O, component-aware binding, or routing conclusion",
        },
        "truth_boundary": (
            "Positive geometry and power witnesses are independently replayed from "
            "landed artifacts without optimization. Named empty front domains are "
            "recomputed. OPTIMAL/INFEASIBLE/UNKNOWN solver statuses remain the "
            "producer records; the two Benders INFEASIBLE rungs were not independently "
            "solver-replayed by this checker."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output_path": str(OUT.relative_to(ROOT)),
                "output_sha256": sha256_file(OUT),
                "body_only_moved": positive_checks["body_only"][
                    "moved_manufacturing"
                ],
                "one_replacement_moved": positive_checks[
                    "one_replacement_power"
                ]["moved_manufacturing"],
                "front_empty_counts": {
                    key: value["empty_body_count"]
                    for key, value in front_checks.items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
