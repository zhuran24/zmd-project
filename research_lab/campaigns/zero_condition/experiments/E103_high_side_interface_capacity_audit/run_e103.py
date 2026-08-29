#!/usr/bin/env python3
"""E103: exact no-solver interface/capacity audit inside E101's high side."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback
import types
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_RUN_DIR = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E103_high_side_interface_capacity_audit/run-003"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E095_y41_module_product_decomposition/run_e095.py"
E100_RUNNER = ROOT / "research_lab/campaigns/zero_condition/experiments/E100_source_stable_reserved_x42_hybrid/run_e100.py"
E101_DIR = ROOT / "research_lab/campaigns/zero_condition/experiments/E101_x42_allocation_handshake"
E101_DURABLE = E101_DIR / "RESULT.txt"
E101_RESULT = ROOT / "research_lab/local/zero_condition/E101_x42_allocation_handshake/run-001/RESULT.json"
E101_CHECK = E101_RESULT.with_name("ARTIFACT_CHECK.json")
E101_BODY = E101_RESULT.with_name("BODY_ONLY_RESULT.json")
E102_DIR = ROOT / "research_lab/campaigns/zero_condition/experiments/E102_high_side_solver_diverse_replay"
E102_DURABLE = E102_DIR / "RESULT.txt"
E102_RESULT = ROOT / "research_lab/local/zero_condition/E102_high_side_solver_diverse_replay/run-001/RESULT.json"
E102_CHECK = E102_RESULT.with_name("ARTIFACT_CHECK.json")

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E101_DURABLE: "5395b9a852c9883b9662390740164ef2222710f83edd468985c3056030354f34",
    E101_RESULT: "b6b088f214fcbb3be01b26180ce9d211b647ede4038e7542531077548bfd9e9d",
    E101_CHECK: "35eb5580acf84a9b25e7569403ac5aa5814285fa29dd225c9bd5e9bd28eb0055",
    E101_BODY: "3e5a801f2bc41d709eb5dea4bebd4e1d29a9ad121525294b351170a44400f060",
    E102_DURABLE: "1d24471e2c304c3f9b2276b1073befeb4ebd30d4268368a12b852e094219cca9",
    E102_RESULT: "853dfba41a1cd017cb010a1255b07f077d24fb2e6221c1fdc9130d2ac6f30d90",
    E102_CHECK: "6ab9a259389c6e6cbeea77b936af8e43f5c9c0850cb1cb8aaa7c8901c2a56710",
}

EXPECTED_RAW_HIGH = 1324
EXPECTED_HIGH_BODY_COUNT = 26
EXPECTED_HIGH_TEMPLATE_COUNTS = {
    "manufacturing_3x3": 10,
    "manufacturing_5x5": 6,
    "manufacturing_6x4": 10,
}
MIN_ANCHOR_SIDE_COUNT = 5
MAX_ANCHOR_SEPARATOR_COUNT = 6
MIN_SIDE_CANDIDATE_FRACTION = 0.15
MAX_SEPARATOR_FRACTION_FOR_HYBRID = 0.15
FULL_CAPABILITY_FRACTION_THRESHOLD = 0.95


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)
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
        json.dumps(json_safe(value), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
    exec(
        compile(raw, f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>", "exec", dont_inherit=True),
        module.__dict__,
    )
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E103 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E103 requires PYTHONHASHSEED=0")
    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E103 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {"sha256": actual, "size_bytes": path.stat().st_size}
    e101 = load_json(E101_RESULT)
    e102 = load_json(E102_RESULT)
    if e101.get("verdict") != "X42_HIGH_SIDE_ALLOCATION_PROPOSER_CENSORED":
        raise RuntimeError("E103 E101 verdict drift")
    if e102.get("verdict") != "SOLVER_DIVERSE_HIGH_SIDE_STILL_CENSORED":
        raise RuntimeError("E103 E102 verdict drift")
    if load_json(E101_CHECK).get("status") != "PASS":
        raise RuntimeError("E103 E101 check is not PASS")
    if load_json(E102_CHECK).get("status") != "PASS":
        raise RuntimeError("E103 E102 check is not PASS")
    body = load_json(E101_BODY)
    if body.get("status") != "OPTIMAL":
        raise RuntimeError("E103 body witness drift")
    if body.get("side_body_counts") != {"high": 26, "low": 65}:
        raise RuntimeError("E103 high body count drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
    }


def valid_mode_data(
    *, e095: types.ModuleType, context: Mapping[str, Any], row: Mapping[str, Any]
) -> tuple[set[tuple[int, int]], set[tuple[str, str, int, int]]]:
    template = str(row["template"])
    fixed_solid = set(context["fixed_solid"])
    relevant = [
        key for key in context["class_counts"]
        if key[0] == "B" and key[1] == template
    ]
    forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
    fronts: set[tuple[int, int]] = set()
    supported: set[tuple[str, str, int, int]] = set()
    for pose_index in row["mode_pose_indices"]:
        pose = context["pools"][template][int(pose_index)]
        inputs = tuple(e095.cell(value) for value in pose["input_port_cells"])
        outputs = tuple(e095.cell(value) for value in pose["output_port_cells"])
        possible_inputs = {
            value for value in inputs if e095.in_grid(value) and value not in fixed_solid
        }
        possible_outputs = {
            value for value in outputs if e095.in_grid(value) and value not in fixed_solid
        }
        for class_key in relevant:
            _module, _template, need_in, need_out = class_key
            if forced is not None and (need_in, need_out) != forced:
                continue
            if len(possible_inputs) >= need_in and len(possible_outputs) >= need_out:
                supported.add(class_key)
                fronts |= possible_inputs | possible_outputs
    return fronts, supported


def candidate_records(
    e095: types.ModuleType, restricted: Mapping[str, Any], body: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    context = restricted["base"]
    selected_indices = set(map(int, body["selected_body_indices"]))
    raw: list[dict[str, Any]] = []
    for global_index, source in enumerate(restricted["rows"]):
        if str(source["side"]) != "high":
            continue
        row = dict(source)
        fronts, supported = valid_mode_data(e095=e095, context=context, row=row)
        body_cells = tuple(row["body"])
        powered = bool(set(body_cells) & set(context["fixed_coverage"]))
        raw.append(
            {
                "raw_high_index": len(raw),
                "global_row_index": global_index,
                "template": str(row["template"]),
                "body": body_cells,
                "body_digest": str(row["body_digest"]),
                "front_cells": frozenset(fronts),
                "supported_classes": frozenset(supported),
                "fixed_powered": powered,
                "static_mode_live": bool(supported),
                "is_anchor": global_index in selected_indices,
                "bbox": {
                    "min_x": min(x for x, _y in body_cells),
                    "max_x": max(x for x, _y in body_cells),
                    "min_y": min(y for _x, y in body_cells),
                    "max_y": max(y for _x, y in body_cells),
                },
            }
        )
    if len(raw) != EXPECTED_RAW_HIGH:
        raise RuntimeError(f"E103 raw high count drift: {len(raw)}")
    if sum(bool(row["is_anchor"]) for row in raw) != EXPECTED_HIGH_BODY_COUNT:
        raise RuntimeError("E103 raw high anchor count drift")
    live = [row for row in raw if row["fixed_powered"] and row["static_mode_live"]]
    raw_anchor_count = sum(bool(row["is_anchor"]) for row in raw)
    live_anchor_count = sum(bool(row["is_anchor"]) for row in live)
    anchor_unpowered_count = sum(
        bool(row["is_anchor"]) and not bool(row["fixed_powered"]) for row in raw
    )
    anchor_static_dead_count = sum(
        bool(row["is_anchor"]) and not bool(row["static_mode_live"]) for row in raw
    )
    summary = {
        "raw_candidate_count": len(raw),
        "raw_template_counts": dict(sorted(Counter(row["template"] for row in raw).items())),
        "unpowered_candidate_count": sum(not row["fixed_powered"] for row in raw),
        "static_mode_dead_candidate_count": sum(not row["static_mode_live"] for row in raw),
        "unpowered_and_static_dead_count": sum(
            (not row["fixed_powered"]) and (not row["static_mode_live"]) for row in raw
        ),
        "live_candidate_count": len(live),
        "live_template_counts": dict(sorted(Counter(row["template"] for row in live).items())),
        "raw_anchor_count": raw_anchor_count,
        "live_anchor_count": live_anchor_count,
        "removed_anchor_count": raw_anchor_count - live_anchor_count,
        "anchor_unpowered_count": anchor_unpowered_count,
        "anchor_static_dead_count": anchor_static_dead_count,
    }
    return live, summary


def interface_for_groups(
    records: Sequence[Mapping[str, Any]], groups: Mapping[int, str]
) -> dict[str, Any]:
    body_coverers: dict[tuple[int, int], list[int]] = defaultdict(list)
    group_counts: Counter[str] = Counter()
    anchor_counts: Counter[str] = Counter()
    for index, row in enumerate(records):
        group = groups[index]
        group_counts[group] += 1
        anchor_counts[group] += int(bool(row["is_anchor"]))
        for value in row["body"]:
            body_coverers[value].append(index)

    shared_body: set[tuple[int, int]] = set()
    cross_front: set[tuple[int, int]] = set()
    participating: set[int] = set()
    body_edges: Counter[tuple[str, str]] = Counter()
    front_edges: Counter[tuple[str, str]] = Counter()
    for value, indices in body_coverers.items():
        present = sorted({groups[index] for index in indices})
        if len(present) > 1:
            shared_body.add(value)
            participating.update(indices)
            for left, right in combinations(present, 2):
                body_edges[(left, right)] += 1
    for index, row in enumerate(records):
        source = groups[index]
        for value in row["front_cells"]:
            targets = [
                target for target in body_coverers.get(value, [])
                if groups[target] != source
            ]
            if targets:
                cross_front.add(value)
                participating.add(index)
                participating.update(targets)
                for target_group in {groups[target] for target in targets}:
                    front_edges[(source, target_group)] += 1
    cells = shared_body | cross_front
    return {
        "group_candidate_counts": dict(sorted(group_counts.items())),
        "group_anchor_counts": dict(sorted(anchor_counts.items())),
        "shared_body_cell_count": len(shared_body),
        "cross_front_body_cell_count": len(cross_front),
        "interface_occupancy_cell_count": len(cells),
        "interface_candidate_count": len(participating),
        "largest_group_candidate_count": max(group_counts.values()),
        "body_interaction_edges": {
            f"{left}<->{right}": count
            for (left, right), count in sorted(body_edges.items())
        },
        "front_body_interaction_edges": {
            f"{left}->{right}": count
            for (left, right), count in sorted(front_edges.items())
        },
        "interface_cell_digest": stable_digest(sorted(cells)),
        "interface_candidate_digest": stable_digest(
            sorted(str(records[index]["body_digest"]) for index in participating)
        ),
    }


def allocation_interface(
    records: Sequence[Mapping[str, Any]],
    groups: Mapping[int, str],
    class_counts: Mapping[tuple[str, str, int, int], int],
) -> dict[str, Any]:
    support_groups: dict[tuple[str, str, int, int], set[str]] = defaultdict(set)
    for index, row in enumerate(records):
        for class_key in row["supported_classes"]:
            support_groups[class_key].add(groups[index])
    dimensions: list[dict[str, Any]] = []
    coordinate_count = 0
    box_size = 1
    log2_box = 0.0
    for class_key, count in sorted(class_counts.items()):
        members = sorted(support_groups.get(class_key, set()))
        if len(members) <= 1:
            continue
        compositions = math.comb(int(count) + len(members) - 1, len(members) - 1)
        dimensions.append(
            {
                "class_key": list(class_key),
                "required_count": int(count),
                "support_groups": members,
                "composition_upper_bound": compositions,
            }
        )
        coordinate_count += len(members) - 1
        box_size *= compositions
        log2_box += math.log2(compositions)
    return {
        "class_allocation_dimension_count": len(dimensions),
        "allocation_coordinate_count": coordinate_count,
        "class_allocation_dimensions": dimensions,
        "allocation_composition_upper_bound": box_size,
        "allocation_log2_upper_bound": log2_box,
    }


def template_interface(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups = {index: str(row["template"]) for index, row in enumerate(records)}
    output = interface_for_groups(records, groups)
    output.update(
        {
            "schema": "zmd_e103_template_interface_v1",
            "grouping": "manufacturing_template",
            "class_allocation_dimension_count": 0,
            "allocation_coordinate_count": 0,
            "truth_boundary": "Exact live-candidate occupancy interface; no runtime claim.",
        }
    )
    return output


def classify_cut(row: Mapping[str, Any], axis: str, coordinate: int) -> str:
    bbox = row["bbox"]
    low = int(bbox[f"min_{axis}"])
    high = int(bbox[f"max_{axis}"])
    if high <= coordinate:
        return "low"
    if low > coordinate:
        return "high"
    return "separator"


def spatial_frontier(
    records: Sequence[Mapping[str, Any]],
    class_counts: Mapping[tuple[str, str, int, int], int],
) -> list[dict[str, Any]]:
    min_x = min(int(row["bbox"]["min_x"]) for row in records)
    max_x = max(int(row["bbox"]["max_x"]) for row in records)
    min_y = min(int(row["bbox"]["min_y"]) for row in records)
    max_y = max(int(row["bbox"]["max_y"]) for row in records)
    cuts = [
        *(("x", coordinate) for coordinate in range(min_x, max_x)),
        *(("y", coordinate) for coordinate in range(min_y, max_y)),
    ]
    output: list[dict[str, Any]] = []
    for axis, coordinate in cuts:
        groups = {
            index: classify_cut(row, axis, coordinate)
            for index, row in enumerate(records)
        }
        interface = interface_for_groups(records, groups)
        allocation = allocation_interface(records, groups, class_counts)
        counts = interface["group_candidate_counts"]
        anchors = interface["group_anchor_counts"]
        nonseparator = int(counts.get("low", 0)) + int(counts.get("high", 0))
        fraction = (
            min(int(counts.get("low", 0)), int(counts.get("high", 0))) / nonseparator
            if nonseparator
            else 0.0
        )
        guard = (
            int(anchors.get("low", 0)) >= MIN_ANCHOR_SIDE_COUNT
            and int(anchors.get("high", 0)) >= MIN_ANCHOR_SIDE_COUNT
            and int(anchors.get("separator", 0)) <= MAX_ANCHOR_SEPARATOR_COUNT
            and fraction >= MIN_SIDE_CANDIDATE_FRACTION
        )
        output.append(
            {
                "cut_id": f"{axis}_after_{coordinate}",
                "axis": axis,
                "coordinate": coordinate,
                "balance_guard_pass": guard,
                "minimum_side_candidate_fraction": fraction,
                "separator_candidate_fraction": int(counts.get("separator", 0))
                / len(records),
                **interface,
                **allocation,
            }
        )
    output.sort(
        key=lambda row: (
            not bool(row["balance_guard_pass"]),
            int(row["interface_occupancy_cell_count"]),
            int(row["group_candidate_counts"].get("separator", 0)),
            float(row["allocation_log2_upper_bound"]),
            int(row["largest_group_candidate_count"]),
            str(row["axis"]),
            int(row["coordinate"]),
        )
    )
    return output


def capability_atlas(
    records: Sequence[Mapping[str, Any]],
    class_counts: Mapping[tuple[str, str, int, int], int],
    template_counts: Mapping[str, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    signatures: dict[str, list[int]] = defaultdict(list)
    signature_payloads: dict[str, Any] = {}
    all_classes_by_template: dict[str, tuple[tuple[str, str, int, int], ...]] = {}
    for template in sorted(template_counts):
        all_classes_by_template[template] = tuple(
            sorted(key for key in class_counts if key[1] == template)
        )
    full_count = 0
    for index, row in enumerate(records):
        supported = tuple(sorted(row["supported_classes"]))
        payload = {
            "template": str(row["template"]),
            "supported_classes": [list(value) for value in supported],
        }
        signature_id = stable_digest(payload)
        signatures[signature_id].append(index)
        signature_payloads[signature_id] = payload
        if supported == all_classes_by_template[str(row["template"])]:
            full_count += 1
    groups = {
        index: next(signature_id for signature_id, members in signatures.items() if index in members)
        for index in range(len(records))
    }
    interface = interface_for_groups(records, groups)
    per_template_signature_counts = Counter(
        str(signature_payloads[signature_id]["template"])
        for signature_id in signatures
    )
    signature_coordinate_count = sum(
        max(0, int(count) - 1) for count in per_template_signature_counts.values()
    )
    atlas = {
        "schema": "zmd_e103_capability_atlas_v1",
        "signature_count": len(signatures),
        "per_template_signature_counts": dict(sorted(per_template_signature_counts.items())),
        "signature_coordinate_count": signature_coordinate_count,
        "full_capability_candidate_count": full_count,
        "full_capability_fraction": full_count / len(records),
        "signatures": [
            {
                "signature_id": signature_id,
                **signature_payloads[signature_id],
                "candidate_count": len(members),
                "anchor_count": sum(bool(records[index]["is_anchor"]) for index in members),
                "candidate_digest": stable_digest(
                    sorted(str(records[index]["body_digest"]) for index in members)
                ),
            }
            for signature_id, members in sorted(signatures.items())
        ],
        "interface": interface,
        "truth_boundary": (
            "Fixed-obstacle capability signatures only; dynamic body occupancy is absent."
        ),
    }

    hall_rows: list[dict[str, Any]] = []
    nontrivial = 0
    for template, classes in sorted(all_classes_by_template.items()):
        template_records = [row for row in records if row["template"] == template]
        template_required = int(template_counts[template])
        for subset_size in range(1, len(classes) + 1):
            for subset in combinations(classes, subset_size):
                subset_set = set(subset)
                complement = set(classes) - subset_set
                union_support = sum(
                    bool(set(row["supported_classes"]) & subset_set)
                    for row in template_records
                )
                complement_support = sum(
                    bool(set(row["supported_classes"]) & complement)
                    for row in template_records
                ) if complement else 0
                upper = min(template_required, union_support)
                lower = max(0, template_required - complement_support)
                proper_subset = subset_size < len(classes)
                is_nontrivial = proper_subset and (
                    upper < template_required or lower > 0
                )
                if is_nontrivial:
                    nontrivial += 1
                hall_rows.append(
                    {
                        "template": template,
                        "classes": [list(value) for value in subset],
                        "template_required_count": template_required,
                        "union_support_candidate_count": union_support,
                        "complement_support_candidate_count": complement_support,
                        "optimistic_allocation_lower_bound": lower,
                        "optimistic_allocation_upper_bound": upper,
                        "proper_subset": proper_subset,
                        "template_total_identity": not proper_subset,
                        "nontrivial": is_nontrivial,
                    }
                )
    hall = {
        "schema": "zmd_e103_hall_support_bounds_v1",
        "bound_count": len(hall_rows),
        "nontrivial_bound_count": nontrivial,
        "bounds": hall_rows,
        "truth_boundary": (
            "Necessary optimistic candidate-support bounds; dynamic packing is ignored."
        ),
    }
    return atlas, hall


def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    fields = (
        "interface_occupancy_cell_count",
        "interface_candidate_count",
        "largest_group_candidate_count",
        "allocation_coordinate_count",
    )
    return all(int(left[field]) <= int(right[field]) for field in fields) and any(
        int(left[field]) < int(right[field]) for field in fields
    )


def run(run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E103 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(OPERATION_PROFILES, "src.preprocess.operation_profiles", package="src.preprocess")
    e095 = source_module(E095_RUNNER, "zmd_e103_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e103_source_e100")
    restricted = e100.build_restricted_context(e095)
    body = load_json(E101_BODY)
    records, unary = candidate_records(e095, restricted, body)
    class_counts = {
        key: int(count)
        for key, count in restricted["base"]["class_counts"].items()
        if key[0] == "B"
    }
    high_template_counts = {
        template: int(body["side_template_counts"].get(f"high:{template}", 0))
        for template in EXPECTED_HIGH_TEMPLATE_COUNTS
    }
    if high_template_counts != EXPECTED_HIGH_TEMPLATE_COUNTS:
        raise RuntimeError("E103 high template count drift")

    template = template_interface(records)
    spatial = spatial_frontier(records, class_counts)
    guarded = [row for row in spatial if row["balance_guard_pass"]]
    if not guarded:
        raise RuntimeError("E103 has no guarded spatial cut")
    best_spatial = guarded[0]
    capability, hall = capability_atlas(
        records, class_counts, high_template_counts
    )
    capability_summary = {
        "interface_occupancy_cell_count": int(
            capability["interface"]["interface_occupancy_cell_count"]
        ),
        "interface_candidate_count": int(
            capability["interface"]["interface_candidate_count"]
        ),
        "largest_group_candidate_count": int(
            capability["interface"]["largest_group_candidate_count"]
        ),
        "allocation_coordinate_count": int(
            capability["signature_coordinate_count"]
        ),
    }
    template_comparison = {
        "interface_occupancy_cell_count": int(template["interface_occupancy_cell_count"]),
        "interface_candidate_count": int(template["interface_candidate_count"]),
        "largest_group_candidate_count": int(template["largest_group_candidate_count"]),
        "allocation_coordinate_count": 0,
    }
    spatial_comparison = {
        "interface_occupancy_cell_count": int(best_spatial["interface_occupancy_cell_count"]),
        "interface_candidate_count": int(best_spatial["interface_candidate_count"]),
        "largest_group_candidate_count": int(best_spatial["largest_group_candidate_count"]),
        "allocation_coordinate_count": int(best_spatial["allocation_coordinate_count"]),
    }
    pure_dominance = {
        "template_over_spatial": dominates(template_comparison, spatial_comparison),
        "spatial_over_template": dominates(spatial_comparison, template_comparison),
        "capability_over_template": dominates(capability_summary, template_comparison),
        "capability_over_spatial": dominates(capability_summary, spatial_comparison),
    }
    capability_degenerate = (
        float(capability["full_capability_fraction"])
        >= FULL_CAPABILITY_FRACTION_THRESHOLD
        and int(hall["nontrivial_bound_count"]) == 0
    )
    hybrid_guard = (
        int(best_spatial["interface_occupancy_cell_count"]) * 3
        <= int(template["interface_occupancy_cell_count"])
        and int(best_spatial["interface_candidate_count"]) * 2
        <= int(template["interface_candidate_count"])
        and float(best_spatial["separator_candidate_fraction"])
        <= MAX_SEPARATOR_FRACTION_FOR_HYBRID
    )
    if pure_dominance["spatial_over_template"] and capability_degenerate:
        verdict = "HIGH_SIDE_SPATIAL_INTERFACE_STRICTLY_DOMINATES"
        decision = "DECOMPOSE_HIGH_SIDE_BY_SELECTED_SPATIAL_CUT"
    elif pure_dominance["template_over_spatial"] and capability_degenerate:
        verdict = "HIGH_SIDE_TEMPLATE_INTERFACE_STRICTLY_DOMINATES"
        decision = "DECOMPOSE_HIGH_SIDE_BY_TEMPLATE"
    elif hybrid_guard and capability_degenerate:
        verdict = "HIGH_SIDE_SPATIAL_TEMPLATE_HYBRID_SELECTED"
        decision = "RESERVE_SELECTED_SPATIAL_ROW_WITH_TEMPLATE_CLASS_BRIDGE"
    else:
        verdict = "HIGH_SIDE_INTERFACES_REMAIN_INCOMPARABLE"
        decision = "REDESIGN_HIGH_BAY_BEFORE_MORE_SOLVER_WORK"

    candidates_path = run_dir / "LIVE_HIGH_CANDIDATES.json"
    template_path = run_dir / "TEMPLATE_INTERFACE.json"
    spatial_path = run_dir / "SPATIAL_FRONTIER.json"
    capability_path = run_dir / "CAPABILITY_ATLAS.json"
    hall_path = run_dir / "HALL_BOUNDS.json"
    result_path = run_dir / "RESULT.json"
    dump_exclusive(
        candidates_path,
        {
            "schema": "zmd_e103_live_high_candidates_v1",
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "unary_filter_summary": unary,
            "candidate_count": len(records),
            "candidates": [
                {
                    **{
                        key: row[key]
                        for key in (
                            "raw_high_index",
                            "global_row_index",
                            "template",
                            "body_digest",
                            "fixed_powered",
                            "static_mode_live",
                            "is_anchor",
                            "bbox",
                        )
                    },
                    "body": [list(value) for value in row["body"]],
                    "front_cells": [list(value) for value in sorted(row["front_cells"])],
                    "supported_classes": [
                        list(value) for value in sorted(row["supported_classes"])
                    ],
                }
                for row in records
            ],
        },
    )
    dump_exclusive(template_path, template)
    dump_exclusive(
        spatial_path,
        {
            "schema": "zmd_e103_spatial_frontier_v1",
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "cut_count": len(spatial),
            "guarded_cut_count": len(guarded),
            "cuts": spatial,
        },
    )
    dump_exclusive(capability_path, capability)
    dump_exclusive(hall_path, hall)

    result = {
        "schema": "zmd_e103_high_side_interface_capacity_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "unary_filter_summary": unary,
        "high_template_counts": high_template_counts,
        "template_interface": template_comparison,
        "selected_spatial_cut": best_spatial,
        "capability_summary": {
            **capability_summary,
            "signature_count": capability["signature_count"],
            "per_template_signature_counts": capability[
                "per_template_signature_counts"
            ],
            "full_capability_candidate_count": capability[
                "full_capability_candidate_count"
            ],
            "full_capability_fraction": capability["full_capability_fraction"],
            "nontrivial_hall_bound_count": hall["nontrivial_bound_count"],
        },
        "pure_dominance": pure_dominance,
        "hybrid_guard_pass": hybrid_guard,
        "capability_degenerate": capability_degenerate,
        "artifacts": {
            "candidates": {"path": display(candidates_path), "sha256": sha256_file(candidates_path)},
            "template": {"path": display(template_path), "sha256": sha256_file(template_path)},
            "spatial": {"path": display(spatial_path), "sha256": sha256_file(spatial_path)},
            "capability": {"path": display(capability_path), "sha256": sha256_file(capability_path)},
            "hall": {"path": display(hall_path), "sha256": sha256_file(hall_path)},
        },
        "truth_boundary": (
            "Exact live-candidate interface census after unary forced-zero removal. "
            "Hall bounds ignore dynamic packing; metrics do not prove runtime or feasibility."
        ),
    }
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    run_dir = DEFAULT_RUN_DIR
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir)
        result_path = run_dir / "RESULT.json"
        selected = result["selected_spatial_cut"]
        print(json.dumps({
            "verdict": result["verdict"],
            "decision": result["decision"],
            "raw_high_candidates": result["unary_filter_summary"]["raw_candidate_count"],
            "live_high_candidates": result["unary_filter_summary"]["live_candidate_count"],
            "selected_cut_id": selected["cut_id"],
            "selected_interface_cells": selected["interface_occupancy_cell_count"],
            "selected_interface_candidates": selected["interface_candidate_count"],
            "selected_separator_candidates": selected["group_candidate_counts"].get("separator", 0),
            "capability_signature_count": result["capability_summary"]["signature_count"],
            "nontrivial_hall_bounds": result["capability_summary"]["nontrivial_hall_bound_count"],
            "result_path": display(result_path),
            "result_sha256": sha256_file(result_path),
        }, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "zmd_e103_execution_failure_v1",
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
