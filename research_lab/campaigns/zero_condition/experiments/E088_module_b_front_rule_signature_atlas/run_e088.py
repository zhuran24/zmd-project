#!/usr/bin/env python3
"""E088: complete module-B front-rule signature atlas."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HISTORY = Path("/home/zhuran24/zmd-pj")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.preprocess.operation_profiles import get_operation_port_profile  # noqa: E402

DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E088_module_b_front_rule_signature_atlas/run-002"
)
E087_CHECKPOINT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E087_feasibility_first_front_continuation/run-001/CHECKPOINT.json"
)
E087_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E087_feasibility_first_front_continuation/run-001/ARTIFACT_CHECK.json"
)
E087_RESULT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E087_feasibility_first_front_continuation/run-001/RESULT.json"
)
E087_DURABLE = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E087_feasibility_first_front_continuation/RESULT.txt"
)
E086_DERIVED = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E086_feasibility_first_front_proposer/run-001/DERIVED_PRODUCER.py"
)
E081_FRONTIER = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E081_axis_seam_recolor_frontier/run-001/AXIS_SEAM_FRONTIER.json"
)
E069_PARENT = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E069_six4_near_miss_complete_face/run-001/PARENT_SOLUTION.json"
)
E079_MACRO = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E079_k47_boundary_macro/run-001/BOUNDARY_MACRO_V1.json"
)
CANDIDATES = HISTORY / "data/preprocessed/candidate_placements.json"
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"

EXPECTED_HASHES = {
    E087_CHECKPOINT: "09c0c31d5874fe9689ecea7295be48edb3a765f0a605a475e44e5ef1a107d4e9",
    E087_CHECK: "10463e14fc0fe736ba2350803f21cb27314f8eb3a28f3fc6164f35d2a62ae899",
    E087_RESULT: "ff53ddd8311dd6c23d1785cee095d9611fd270f307d33d5b1323245d74b88460",
    E087_DURABLE: "0712042f7b0c21b22ac14a833f7a18d8a02070e2fd834fbc66f59808467c5212",
    E086_DERIVED: "f78d6d6a1cffdb4d5f9e695c18ea60711befc3ad2129628845167ef2b3b8a8c7",
    E081_FRONTIER: "e8dbf00d61bcf01f9a0cb11ab9b16a918597d8a2552f932d1977a9c57b4d75b1",
    E069_PARENT: "b8e4d61d2a5e2befcedcb815b558d07ae84b3620b0bcab82644610154301b49a",
    E079_MACRO: "bb92c5fde00971fecade62e67a9af3e01e1892aad7a67c2c67d370004d877f36",
    CANDIDATES: "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
}

TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
EXPECTED_REGISTERED_B = 178
EXPECTED_REGISTERED_A = 3


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


def dump_exclusive(path: Path, payload: Any) -> None:
    encoded = (
        json.dumps(
            json_safe(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def cell(value: Any) -> tuple[int, int]:
    if isinstance(value, Mapping):
        return int(value["x"]), int(value["y"])
    return int(value[0]), int(value[1])


def in_grid(value: tuple[int, int]) -> bool:
    return 0 <= value[0] < 70 and 0 <= value[1] < 70


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E088 must run on research/main")
    tracked_status = git_output(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if tracked_status:
        raise RuntimeError(f"tracked research worktree is not clean: {tracked_status}")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(
                f"frozen identity drift: {path}: {observed} != {expected}"
            )
        checked[display(path)] = {
            "sha256": observed,
            "size_bytes": path.stat().st_size,
        }

    e087_check = load_json(E087_CHECK)
    checkpoint = load_json(E087_CHECKPOINT)
    if e087_check.get("decision") != (
        "STOP_BLIND_LAZY_CONTINUATION_AND_BUILD_MODULE_B_RULE_SIGNATURE_ATLAS"
    ):
        raise RuntimeError("E088 trigger E087 decision drift")
    if int(checkpoint.get("registered_front_candidate_count", -1)) != 181:
        raise RuntimeError("E088 checkpoint rule count drift")
    if int(checkpoint.get("operation_nogood_count", -1)) != 0:
        raise RuntimeError("E088 checkpoint operation-nogood drift")

    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked_status,
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "trigger_rule_count": 181,
        "trigger_registered_b_rule_count": 178,
    }


def demand_payload(
    demand_classes: Sequence[tuple[str, str, int, int]],
) -> list[dict[str, Any]]:
    return [
        {
            "module": module,
            "template": template,
            "input_need": int(input_need),
            "output_need": int(output_need),
        }
        for module, template, input_need, output_need in demand_classes
    ]


def reconstruct() -> dict[str, Any]:
    frontier = load_json(E081_FRONTIER)
    detailed = {
        row["partition"]["partition_id"]: row
        for row in frontier["detailed_candidates"]
    }
    partition_row = detailed[frontier["geometry_winner_partition_id"]]
    evaluation = partition_row["best_reference_preserving"]
    partition = partition_row["partition"]
    corridor = evaluation["corridor"]
    if (
        corridor["axis"] != "y"
        or int(corridor["start"]) != 41
        or int(corridor["end"]) != 41
        or corridor["module_low"] != "A"
        or corridor["module_high"] != "B"
    ):
        raise RuntimeError(f"E088 corridor drift: {corridor}")

    parent = load_json(E069_PARENT)["solution"]
    pools = load_json(CANDIDATES)["facility_pools"]
    macro = load_json(E079_MACRO)
    checkpoint = load_json(E087_CHECKPOINT)
    module_operations = {
        "A": set(map(str, partition["module_a_operations"])),
        "B": set(map(str, partition["module_b_operations"])),
    }
    operation_counts = Counter(
        str(row["operation_type"])
        for row in parent.values()
        if str(row["facility_type"]).startswith("manufacturing_")
    )
    if set(operation_counts) != module_operations["A"] | module_operations["B"]:
        raise RuntimeError("E088 operation universe drift")

    demand_class_counts: Counter[tuple[str, str, int, int]] = Counter()
    for module, operations in module_operations.items():
        for operation in sorted(operations):
            profile = get_operation_port_profile(operation)
            key = (
                module,
                str(profile.facility_type),
                sum(int(value) for value in profile.input_slots.values()),
                sum(int(value) for value in profile.output_slots.values()),
            )
            demand_class_counts[key] += int(operation_counts[operation])

    def minimal_demand_classes(
        module: str,
        template: str,
    ) -> tuple[tuple[str, str, int, int], ...]:
        classes = sorted(
            key
            for key in demand_class_counts
            if key[0] == module and key[1] == template
        )
        return tuple(
            current
            for current in classes
            if not any(
                other != current
                and other[2] <= current[2]
                and other[3] <= current[3]
                for other in classes
            )
        )

    fixed_occupied: set[tuple[int, int]] = set()
    fixed_forbidden: set[tuple[int, int]] = set()
    fixed_pole_indices: set[int] = set()
    current_manufacturing: set[tuple[tuple[int, int], ...]] = set()
    removed_poles = set(map(str, evaluation["pole_move_ids"]))
    for instance_id, row in parent.items():
        facility_type = str(row["facility_type"])
        pose_index = int(row["pose_idx"])
        pose = pools[facility_type][pose_index]
        body = tuple(sorted(cell(value) for value in pose["occupied_cells"]))
        if facility_type.startswith("manufacturing_"):
            current_manufacturing.add(body)
            continue
        if facility_type == "power_pole":
            if instance_id in removed_poles:
                continue
            fixed_pole_indices.add(pose_index)
            fixed_occupied.update(body)
            fixed_forbidden.update(body)
            continue
        if facility_type == "protocol_core":
            fixed_occupied.update(body)
            fixed_forbidden.update(body)
            fixed_forbidden.update(
                cell(value)
                for field in ("input_port_cells", "output_port_cells")
                for value in pose[field]
            )
    if len(fixed_pole_indices) != 52 or len(removed_poles) != 1:
        raise RuntimeError("E088 fixed-pole context drift")
    fixed_forbidden |= {(x, 41) for x in range(1, 69)}

    boundary_body_states: list[set[tuple[int, int]]] = []
    boundary_forbidden_states: list[set[tuple[int, int]]] = []
    for state in macro["states"]:
        body = {cell(value) for value in state["body_cells"]}
        fronts = {cell(value) for value in state["front_cells"]}
        boundary_body_states.append(body)
        boundary_forbidden_states.append(body | fronts)
    if len(boundary_body_states) != 47:
        raise RuntimeError("E088 boundary state count drift")

    modes_by_template_footprint: dict[
        str, dict[tuple[tuple[int, int], ...], tuple[int, ...]]
    ] = {}
    for template in TEMPLATES:
        grouped: dict[tuple[tuple[int, int], ...], list[int]] = defaultdict(list)
        for pose_index, pose in enumerate(pools[template]):
            body = tuple(sorted(cell(value) for value in pose["occupied_cells"]))
            grouped[body].append(int(pose_index))
        modes_by_template_footprint[template] = {
            body: tuple(indices) for body, indices in grouped.items()
        }

    manufacturing_rows: list[dict[str, Any]] = []
    domain_counts: Counter[tuple[str, str]] = Counter()
    for module, side in (("A", "low"), ("B", "high")):
        for template in TEMPLATES:
            for body, mode_indices in modes_by_template_footprint[template].items():
                ys = [y for _x, y in body]
                if side == "low" and max(ys) >= 41:
                    continue
                if side == "high" and min(ys) <= 41:
                    continue
                body_set = set(body)
                if body_set & fixed_forbidden:
                    continue
                allowed_states = tuple(
                    state_index
                    for state_index, reserved in enumerate(boundary_forbidden_states)
                    if not body_set & reserved
                )
                if not allowed_states:
                    continue
                manufacturing_rows.append(
                    {
                        "module": module,
                        "template": template,
                        "body": body,
                        "mode_indices": mode_indices,
                        "allowed_boundary_states": allowed_states,
                        "is_current_footprint": body in current_manufacturing,
                    }
                )
                domain_counts[(module, template)] += 1

    b_indices = [
        index
        for index, row in enumerate(manufacturing_rows)
        if row["module"] == "B"
    ]
    if not b_indices:
        raise RuntimeError("E088 reconstructed an empty module-B candidate universe")

    pole_rows: list[dict[str, Any]] = []
    for pose_index, pose in enumerate(pools["power_pole"]):
        if pose_index in fixed_pole_indices:
            continue
        body = tuple(sorted(cell(value) for value in pose["occupied_cells"]))
        body_set = set(body)
        if body_set & fixed_forbidden:
            continue
        allowed_states = tuple(
            state_index
            for state_index, reserved in enumerate(boundary_forbidden_states)
            if not body_set & reserved
        )
        if not allowed_states:
            continue
        pole_rows.append({"pose_index": pose_index, "body": body})

    support_by_cell: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    for row in manufacturing_rows:
        for value in row["body"]:
            support_by_cell[value]["manufacturing"] += 1
    for row in pole_rows:
        for value in row["body"]:
            support_by_cell[value]["pole"] += 1
    for body in boundary_body_states:
        for value in body:
            support_by_cell[value]["boundary_state"] += 1

    checkpoint_stats = checkpoint["front_rule_stats"]
    registered_indices = set(map(int, checkpoint_stats))
    registered_b_indices = {
        index
        for index in registered_indices
        if manufacturing_rows[index]["module"] == "B"
    }
    registered_a_indices = registered_indices - registered_b_indices
    if len(registered_b_indices) != EXPECTED_REGISTERED_B:
        raise RuntimeError("E088 registered B rule count drift")
    if len(registered_a_indices) != EXPECTED_REGISTERED_A:
        raise RuntimeError("E088 registered A rule count drift")

    stable_override_demands: dict[int, tuple[tuple[str, str, int, int], ...]] = {}
    for raw_index, stats in checkpoint_stats.items():
        index = int(raw_index)
        if str(stats.get("reason", "")).startswith("stable_operation:"):
            stable_override_demands[index] = tuple(
                (
                    str(stats["module"]),
                    str(stats["template"]),
                    int(item["input_need"]),
                    int(item["output_need"]),
                )
                for item in stats["demand_classes"]
            )
    if len(stable_override_demands) != 2:
        raise RuntimeError(
            f"E088 stable override count drift: {stable_override_demands}"
        )

    def demand_for(index: int) -> tuple[tuple[str, str, int, int], ...]:
        if index in stable_override_demands:
            return stable_override_demands[index]
        row = manufacturing_rows[index]
        return minimal_demand_classes(str(row["module"]), str(row["template"]))

    def signature_for(
        index: int,
        demand_classes: Sequence[tuple[str, str, int, int]],
    ) -> dict[str, Any]:
        row = manufacturing_rows[index]
        template = str(row["template"])
        body = tuple(row["body"])
        min_x = min(x for x, _y in body)
        min_y = min(y for _x, y in body)
        stencil_modes: list[dict[str, Any]] = []
        support_modes: list[dict[str, Any]] = []
        option_count = 0
        for demand_class in sorted(demand_classes):
            _module, _template, input_need, output_need = demand_class
            for pose_index in row["mode_indices"]:
                pose = pools[template][int(pose_index)]
                input_cells = tuple(
                    cell(value)
                    for value in pose.get("input_port_cells", [])
                    if in_grid(cell(value))
                )
                output_cells = tuple(
                    cell(value)
                    for value in pose.get("output_port_cells", [])
                    if in_grid(cell(value))
                )
                possible_inputs = tuple(
                    value for value in input_cells if value not in fixed_occupied
                )
                possible_outputs = tuple(
                    value for value in output_cells if value not in fixed_occupied
                )
                if len(possible_inputs) < input_need or len(possible_outputs) < output_need:
                    continue
                option_count += 1
                pose_params = dict(pose.get("pose_params", {}))

                def normalized(values: Iterable[tuple[int, int]]) -> list[list[int]]:
                    return [
                        [int(x - min_x), int(y - min_y)]
                        for x, y in sorted(values)
                    ]

                def supported(values: Iterable[tuple[int, int]]) -> list[dict[str, Any]]:
                    output: list[dict[str, Any]] = []
                    for x, y in sorted(values):
                        counts = support_by_cell.get((x, y), Counter())
                        output.append(
                            {
                                "cell": [int(x - min_x), int(y - min_y)],
                                "manufacturing_coverers": int(
                                    counts.get("manufacturing", 0)
                                ),
                                "pole_coverers": int(counts.get("pole", 0)),
                                "boundary_state_coverers": int(
                                    counts.get("boundary_state", 0)
                                ),
                            }
                        )
                    return output

                stencil_modes.append(
                    {
                        "input_need": int(input_need),
                        "output_need": int(output_need),
                        "orientation": str(pose_params.get("orientation", "")),
                        "port_mode": str(pose_params.get("port_mode", "")),
                        "input_cells": normalized(possible_inputs),
                        "output_cells": normalized(possible_outputs),
                    }
                )
                support_modes.append(
                    {
                        "input_need": int(input_need),
                        "output_need": int(output_need),
                        "orientation": str(pose_params.get("orientation", "")),
                        "port_mode": str(pose_params.get("port_mode", "")),
                        "input_cells": supported(possible_inputs),
                        "output_cells": supported(possible_outputs),
                    }
                )
        stencil_modes.sort(key=stable_digest)
        support_modes.sort(key=stable_digest)
        base = {
            "module": str(row["module"]),
            "template": template,
            "demand_classes": demand_payload(tuple(sorted(demand_classes))),
            "option_count": option_count,
        }
        stencil_payload = {**base, "modes": stencil_modes}
        support_payload = {**base, "modes": support_modes}
        return {
            "option_count": option_count,
            "stencil_signature": stable_digest(stencil_payload),
            "support_signature": stable_digest(support_payload),
            "stencil_payload": stencil_payload,
            "support_payload": support_payload,
        }

    candidate_rows: list[dict[str, Any]] = []
    signature_payloads: dict[str, dict[str, Any]] = {}
    stencil_counts: Counter[str] = Counter()
    support_counts: Counter[str] = Counter()
    stencil_registered: Counter[str] = Counter()
    support_registered: Counter[str] = Counter()
    current_by_stencil: Counter[str] = Counter()
    current_by_support: Counter[str] = Counter()

    for index in b_indices:
        row = manufacturing_rows[index]
        demands = demand_for(index)
        signature = signature_for(index, demands)
        stencil_id = signature["stencil_signature"]
        support_id = signature["support_signature"]
        signature_payloads.setdefault(
            f"stencil:{stencil_id}", signature["stencil_payload"]
        )
        signature_payloads.setdefault(
            f"support:{support_id}", signature["support_payload"]
        )
        stencil_counts[stencil_id] += 1
        support_counts[support_id] += 1
        registered = index in registered_b_indices
        if registered:
            stencil_registered[stencil_id] += 1
            support_registered[support_id] += 1
            stats = checkpoint_stats[str(index)]
            recorded_demands = tuple(
                (
                    str(stats["module"]),
                    str(stats["template"]),
                    int(item["input_need"]),
                    int(item["output_need"]),
                )
                for item in stats["demand_classes"]
            )
            if tuple(sorted(recorded_demands)) != tuple(sorted(demands)):
                raise RuntimeError(f"E088 registered demand remap drift: {index}")
            if tuple(cell(entry) for entry in stats["body"]) != tuple(row["body"]):
                raise RuntimeError(f"E088 registered body remap drift: {index}")
            if str(stats["module"]) != "B" or str(stats["template"]) != str(row["template"]):
                raise RuntimeError(f"E088 registered row identity drift: {index}")
            if int(stats["option_count"]) != int(signature["option_count"]):
                raise RuntimeError(
                    f"E088 option-count drift for {index}: "
                    f"{stats['option_count']} != {signature['option_count']}"
                )
        if row["is_current_footprint"]:
            current_by_stencil[stencil_id] += 1
            current_by_support[support_id] += 1
        body = tuple(row["body"])
        candidate_rows.append(
            {
                "candidate_index": index,
                "template": str(row["template"]),
                "body_digest": stable_digest(body),
                "body_min": [
                    min(x for x, _y in body),
                    min(y for _x, y in body),
                ],
                "body_max": [
                    max(x for x, _y in body),
                    max(y for _x, y in body),
                ],
                "is_current_footprint": bool(row["is_current_footprint"]),
                "registered": registered,
                "stable_override": index in stable_override_demands,
                "demand_classes": demand_payload(demands),
                "option_count": int(signature["option_count"]),
                "stencil_signature": stencil_id,
                "support_signature": support_id,
            }
        )

    if sum(stencil_registered.values()) != EXPECTED_REGISTERED_B:
        raise RuntimeError("E088 registered stencil count drift")
    if sum(support_registered.values()) != EXPECTED_REGISTERED_B:
        raise RuntimeError("E088 registered support count drift")

    def summaries(
        universe: Counter[str],
        registered: Counter[str],
        current: Counter[str],
        prefix: str,
    ) -> list[dict[str, Any]]:
        rows = []
        for signature_id in sorted(universe):
            rows.append(
                {
                    "signature_id": signature_id,
                    "payload_key": f"{prefix}:{signature_id}",
                    "universe_count": int(universe[signature_id]),
                    "registered_count": int(registered[signature_id]),
                    "unregistered_count": int(
                        universe[signature_id] - registered[signature_id]
                    ),
                    "current_footprint_count": int(current[signature_id]),
                    "registered_fraction": (
                        float(registered[signature_id] / universe[signature_id])
                        if universe[signature_id]
                        else 0.0
                    ),
                }
            )
        rows.sort(
            key=lambda row: (
                -int(row["registered_count"]),
                int(row["universe_count"]),
                str(row["signature_id"]),
            )
        )
        return rows

    stencil_summaries = summaries(
        stencil_counts, stencil_registered, current_by_stencil, "stencil"
    )
    support_summaries = summaries(
        support_counts, support_registered, current_by_support, "support"
    )

    def concentration(
        rows: Sequence[Mapping[str, Any]],
        threshold: float,
    ) -> dict[str, Any]:
        target = int((EXPECTED_REGISTERED_B * threshold) + 0.999999999)
        covered = 0
        universe_expansion = 0
        selected: list[str] = []
        for row in rows:
            registered_count = int(row["registered_count"])
            if registered_count <= 0:
                continue
            covered += registered_count
            universe_expansion += int(row["universe_count"])
            selected.append(str(row["signature_id"]))
            if covered >= target:
                break
        return {
            "threshold": threshold,
            "target_registered_count": target,
            "covered_registered_count": covered,
            "signature_count": len(selected),
            "bulk_candidate_count": universe_expansion,
            "signature_ids": selected,
        }

    thresholds = (0.5, 0.8, 0.9, 0.95)
    stencil_concentration = {
        str(threshold): concentration(stencil_summaries, threshold)
        for threshold in thresholds
    }
    support_concentration = {
        str(threshold): concentration(support_summaries, threshold)
        for threshold in thresholds
    }

    atlas = {
        "schema": "zmd_e088_module_b_front_rule_signature_atlas_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "candidate_universe": {
            "module": "B",
            "candidate_count": len(candidate_rows),
            "domain_counts": {
                template: int(domain_counts[("B", template)])
                for template in TEMPLATES
            },
            "registered_rule_count": EXPECTED_REGISTERED_B,
            "registered_fraction": EXPECTED_REGISTERED_B / len(candidate_rows),
        },
        "signature_definitions": {
            "stencil_signature": (
                "template+demand+translation-normalized same-footprint mode front "
                "cells after in-grid/fixed-occupied clipping"
            ),
            "support_signature": (
                "stencil signature plus manufacturing/pole/boundary-state dynamic "
                "occupier counts on every normalized front cell"
            ),
            "consumer_boundary": (
                "grouping is proposer-only; bulk consumption must instantiate the "
                "existing exact candidate-specific rule for each candidate"
            ),
        },
        "stencil_signature_count": len(stencil_counts),
        "support_signature_count": len(support_counts),
        "registered_stencil_signature_count": sum(
            int(row["registered_count"] > 0) for row in stencil_summaries
        ),
        "registered_support_signature_count": sum(
            int(row["registered_count"] > 0) for row in support_summaries
        ),
        "stencil_concentration": stencil_concentration,
        "support_concentration": support_concentration,
        "stencil_signatures": stencil_summaries,
        "support_signatures": support_summaries,
        "signature_payloads": signature_payloads,
        "truth_boundary": (
            "Finite proposer-signature census only. Signatures do not merge model "
            "variables and do not prove every member fails or succeeds."
        ),
    }

    support80 = support_concentration["0.8"]
    stencil90 = stencil_concentration["0.9"]
    if (
        int(support80["signature_count"]) <= 8
        and int(support80["bulk_candidate_count"]) <= 2500
    ):
        verdict = "REGISTERED_B_FAILURES_CONCENTRATE_IN_HOT_SUPPORT_SIGNATURES"
        decision = "BULK_COMPILE_HOT_SUPPORT_SIGNATURES"
        selected_family = support80
    elif (
        int(stencil90["signature_count"]) <= 4
        and int(stencil90["bulk_candidate_count"]) <= 3500
    ):
        verdict = "REGISTERED_B_FAILURES_CONCENTRATE_IN_HOT_STENCIL_SIGNATURES"
        decision = "BULK_COMPILE_HOT_STENCIL_SIGNATURES_WITH_EXACT_PER_CANDIDATE_RULES"
        selected_family = stencil90
    else:
        verdict = "REGISTERED_B_FAILURES_ARE_TOO_DIFFUSE_FOR_BOUNDED_BULK_COMPILATION"
        decision = "RULE_FAILURES_DIFFUSE_REVISE_MODULE_B_GEOMETRY_OR_DECOMPOSE"
        selected_family = None

    return {
        "context": {
            "manufacturing_rows": manufacturing_rows,
            "domain_counts": domain_counts,
            "registered_indices": registered_indices,
            "registered_b_indices": registered_b_indices,
        },
        "candidate_rows": candidate_rows,
        "atlas": atlas,
        "result": {
            "schema": "zmd_e088_module_b_front_rule_signature_result_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "verdict": verdict,
            "decision": decision,
            "candidate_count": len(candidate_rows),
            "registered_b_rule_count": EXPECTED_REGISTERED_B,
            "registered_b_fraction": EXPECTED_REGISTERED_B / len(candidate_rows),
            "stencil_signature_count": len(stencil_counts),
            "support_signature_count": len(support_counts),
            "registered_stencil_signature_count": sum(
                int(row["registered_count"] > 0) for row in stencil_summaries
            ),
            "registered_support_signature_count": sum(
                int(row["registered_count"] > 0) for row in support_summaries
            ),
            "stencil_concentration": stencil_concentration,
            "support_concentration": support_concentration,
            "selected_bulk_family": selected_family,
            "stable_override_candidate_count": len(stable_override_demands),
            "all_registered_rows_exactly_remapped": True,
            "truth_boundary": (
                "No-solver finite signature census. Concentration chooses only which "
                "candidate-specific exact rules to instantiate next; it grants no "
                "shared-rule quotient, feasibility, infeasibility or pruning effect."
            ),
        },
    }


def run(run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E088 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    rebuilt = reconstruct()
    candidate_path = run_dir / "CANDIDATE_SIGNATURES.json"
    atlas_path = run_dir / "SIGNATURE_ATLAS.json"
    result_path = run_dir / "RESULT.json"

    dump_exclusive(
        candidate_path,
        {
            "schema": "zmd_e088_module_b_candidate_signatures_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "candidate_count": len(rebuilt["candidate_rows"]),
            "candidates": rebuilt["candidate_rows"],
            "ledger_effect": "none",
        },
    )
    dump_exclusive(atlas_path, rebuilt["atlas"])
    result = {
        **rebuilt["result"],
        "identity": identity,
        "candidate_signatures_path": display(candidate_path),
        "candidate_signatures_sha256": sha256_file(candidate_path),
        "signature_atlas_path": display(atlas_path),
        "signature_atlas_sha256": sha256_file(atlas_path),
    }
    dump_exclusive(result_path, result)
    return result


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
                    "candidate_count": result["candidate_count"],
                    "registered_b_rule_count": result["registered_b_rule_count"],
                    "stencil_signature_count": result["stencil_signature_count"],
                    "support_signature_count": result["support_signature_count"],
                    "support_80": result["support_concentration"]["0.8"],
                    "stencil_90": result["stencil_concentration"]["0.9"],
                    "result_path": display(result_path),
                    "result_sha256": sha256_file(result_path),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except FileExistsError as exc:
        print(
            json.dumps(
                {"status": "NO_OVERWRITE_REJECTION", "detail": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e088_module_b_front_rule_signature_failure_v1",
            "created_at_utc": utc_now(),
            "status": "EXECUTION_FAILURE",
            "error": type(exc).__name__,
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "ledger_effect": "none",
        }
        if not failure_path.exists():
            dump_exclusive(failure_path, failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
