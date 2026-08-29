#!/usr/bin/env python3
"""E113: compile and compare exact separator/side interaction hypergraphs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
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
    "E113_separator_side_interaction_compiler/run-001"
)
OPERATION_PROFILES = ROOT / "src/preprocess/operation_profiles.py"
E095_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E095_y41_module_product_decomposition/run_e095.py"
)
E100_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E100_source_stable_reserved_x42_hybrid/run_e100.py"
)
E110_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E110_explicit_separator_template_duty_atlas/run_e110.py"
)
E112_RUNNER = (
    ROOT
    / "research_lab/campaigns/zero_condition/experiments/"
    "E112_fixed_separator_class_state_closure/run_e112.py"
)
E112_DURABLE = E112_RUNNER.with_name("RESULT.txt")
E112_SNAPSHOT = E112_RUNNER.with_name("MACHINE_SNAPSHOT.json")
E112_RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E112_fixed_separator_class_state_closure/run-001"
)
E112_RESULT = E112_RUN / "RESULT.json"
E112_MANIFEST = E112_RUN / "SEPARATOR_CLASS_ATLAS_MANIFEST.json"
E112_CHECK = E112_RUN / "ARTIFACT_CHECK.json"

EXPECTED_HASHES = {
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E110_RUNNER: "30b2fc298ef56ba68053d47977ef139890e862568b53bba70bdf541f677a1fea",
    E112_RUNNER: "125d79f51cd3c030eafc4fdbc2da61c76ca91fef1a11dfdcba9813243371460a",
    E112_DURABLE: "0a18902b61be72a29ad5fea2efc319cc02c02b2bcc4bd1581cfd9f318618e354",
    E112_SNAPSHOT: "52621b1a436ee2f4c79990b4261315030d8590ea64dea2a59821f21cd29f63a3",
    E112_RESULT: "da64e4a66ff0826c1b9aa56b69fda4fe7855739acc60e853522241dc5bd9fa0e",
    E112_MANIFEST: "45767f5f1a00d051701e1bd6787a77a813e23d1958652c632dbfea336113db2a",
    E112_CHECK: "cdbae6428ba1514646e12836de069b26104e1872f7356b63fb1bdeb4c34e5e03",
}

GROUPS = ("low", "separator", "high")
EXPECTED_GROUP_COUNTS = {"low": 812, "separator": 154, "high": 239}
EXPECTED_CLASS_COUNT = 8
PARTITIONS = (
    {
        "partition_id": "low__separator_plus_high",
        "left_groups": ("low",),
        "right_groups": ("separator", "high"),
    },
    {
        "partition_id": "low_plus_separator__high",
        "left_groups": ("low", "separator"),
        "right_groups": ("high",),
    },
    {
        "partition_id": "low_plus_high__separator",
        "left_groups": ("low", "high"),
        "right_groups": ("separator",),
    },
)
SELECTION_METRICS = (
    "body_conflict_edge_count",
    "total_unique_directional_front_signatures",
    "total_nonempty_directional_rows",
    "maximum_side_candidate_count",
)


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
    exec(
        compile(
            raw,
            f"<source-isolated:{path}:{hashlib.sha256(raw).hexdigest()}>",
            "exec",
            dont_inherit=True,
        ),
        module.__dict__,
    )
    return module


def verify_identity() -> dict[str, Any]:
    if git_output("branch", "--show-current") != "research/main":
        raise RuntimeError("E113 must run on research/main")
    tracked = git_output("status", "--porcelain=v1", "--untracked-files=no")
    if tracked:
        raise RuntimeError(f"tracked research worktree is dirty: {tracked}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("E113 requires PYTHONHASHSEED=0")

    checked: dict[str, Any] = {}
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"E113 input drift: {path}: {actual} != {expected}")
        checked[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load_json(E112_RESULT)
    if result.get("verdict") != "SEPARATOR_NATIVE_FRONT_RELAXATION_ATLAS_COMPLETE":
        raise RuntimeError("E113 E112 verdict drift")
    if result.get("decision") != "BUILD_SIDE_CONDITIONED_SEPARATOR_INTERFACE":
        raise RuntimeError("E113 E112 decision drift")
    manifest = load_json(E112_MANIFEST)
    summary = manifest.get("summary", {})
    if manifest.get("complete") is not True:
        raise RuntimeError("E113 E112 manifest is not complete")
    if (
        int(summary.get("positive_state_count", -1)) != 350
        or int(summary.get("negative_state_count", -1)) != 3
        or int(summary.get("unknown_state_count", -1)) != 0
    ):
        raise RuntimeError("E113 E112 terminal partition drift")
    check = load_json(E112_CHECK)
    if check.get("status") != "PASS" or check.get("classification") != (
        "COMPLETE_SEPARATOR_RELAXATION_ATLAS_350_POSITIVE_3_NEGATIVE"
    ):
        raise RuntimeError("E113 E112 check drift")
    return {
        "research_head": git_output("rev-parse", "HEAD"),
        "research_branch": "research/main",
        "tracked_status": tracked,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "checked_files": checked,
        "compact_negative_rule": check["compact_negative_rule"],
    }


def group_rows(prepared: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    output = {
        group: [
            dict(row)
            for row in prepared["rows"]
            if str(row["separator_group"]) == group
        ]
        for group in GROUPS
    }
    observed = {group: len(rows) for group, rows in output.items()}
    if observed != EXPECTED_GROUP_COUNTS:
        raise RuntimeError(f"E113 group count drift: {observed}")
    all_indices = [
        int(row["global_row_index"])
        for rows in output.values()
        for row in rows
    ]
    if len(all_indices) != len(set(all_indices)):
        raise RuntimeError("E113 global row identity collision")
    return output


def rows_for_groups(
    groups: Sequence[str],
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    return [dict(row) for group in groups for row in grouped[group]]


def body_coverers(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[int, int], tuple[int, ...]]:
    raw: dict[tuple[int, int], list[int]] = defaultdict(list)
    for row in rows:
        global_index = int(row["global_row_index"])
        for cell in row["body"]:
            raw[cell].append(global_index)
    return {
        cell: tuple(sorted(set(indices)))
        for cell, indices in raw.items()
    }


def candidate_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "global_row_index": int(row["global_row_index"]),
        "body_digest": str(row["body_digest"]),
        "template": str(row["template"]),
        "source_group": str(row["separator_group"]),
        "body_cell_count": len(row["body"]),
    }


def mode_class_rows(
    *,
    e095: types.ModuleType,
    context: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    class_keys: Sequence[tuple[str, str, int, int]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    pools = context["pools"]
    for row in rows:
        template = str(row["template"])
        forced = e095.STABLE_CLASS_BY_BODY.get(str(row["body_digest"]))
        relevant = [key for key in class_keys if key[1] == template]
        for pose_index in row["mode_pose_indices"]:
            pose = pools[template][int(pose_index)]
            inputs = tuple(e095.cell(value) for value in pose["input_port_cells"])
            outputs = tuple(e095.cell(value) for value in pose["output_port_cells"])
            for class_key in relevant:
                _module, _template, need_in, need_out = class_key
                if forced is not None and (need_in, need_out) != forced:
                    continue
                if need_in > len(inputs) or need_out > len(outputs):
                    continue
                identity = {
                    "global_row_index": int(row["global_row_index"]),
                    "body_digest": str(row["body_digest"]),
                    "template": template,
                    "source_group": str(row["separator_group"]),
                    "pose_index": int(pose_index),
                    "class_key": list(class_key),
                    "need_in": int(need_in),
                    "need_out": int(need_out),
                }
                output.append(
                    {
                        **identity,
                        "member_id": stable_digest(identity),
                        "input_cells": inputs,
                        "output_cells": outputs,
                    }
                )
    member_ids = [str(row["member_id"]) for row in output]
    if len(member_ids) != len(set(member_ids)):
        raise RuntimeError("E113 mode/class member identity collision")
    return output


def body_conflict_payload(
    *,
    left_rows: Sequence[Mapping[str, Any]],
    right_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    right_coverers = body_coverers(right_rows)
    edges: set[tuple[int, int]] = set()
    left_neighbors: dict[int, set[int]] = defaultdict(set)
    right_neighbors: dict[int, set[int]] = defaultdict(set)
    for row in left_rows:
        left_index = int(row["global_row_index"])
        for cell in row["body"]:
            for right_index in right_coverers.get(cell, ()):
                edges.add((left_index, int(right_index)))
                left_neighbors[left_index].add(int(right_index))
                right_neighbors[int(right_index)].add(left_index)

    left_signatures = {
        tuple(sorted(values)) for values in left_neighbors.values() if values
    }
    right_signatures = {
        tuple(sorted(values)) for values in right_neighbors.values() if values
    }
    left_support = [len(values) for values in left_neighbors.values() if values]
    right_support = [len(values) for values in right_neighbors.values() if values]
    return {
        "edge_count": len(edges),
        "edges": [list(edge) for edge in sorted(edges)],
        "left_participating_candidate_count": len(left_neighbors),
        "right_participating_candidate_count": len(right_neighbors),
        "left_unique_neighbor_signature_count": len(left_signatures),
        "right_unique_neighbor_signature_count": len(right_signatures),
        "left_neighbor_support_min": min(left_support) if left_support else 0,
        "left_neighbor_support_max": max(left_support) if left_support else 0,
        "right_neighbor_support_min": min(right_support) if right_support else 0,
        "right_neighbor_support_max": max(right_support) if right_support else 0,
    }


def coefficient_signature(
    *,
    cells: Sequence[tuple[int, int]],
    target_coverers: Mapping[tuple[int, int], Sequence[int]],
) -> tuple[tuple[int, int], ...]:
    coefficients: Counter[int] = Counter()
    for cell in cells:
        for target_index in target_coverers.get(cell, ()):
            coefficients[int(target_index)] += 1
    return tuple(sorted((index, int(value)) for index, value in coefficients.items()))


def compile_front_buckets(
    *,
    source_mode_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    source_label: str,
    target_label: str,
) -> dict[str, Any]:
    target_coverers = body_coverers(target_rows)
    all_signatures: set[tuple[str, int, tuple[tuple[int, int], ...]]] = set()
    buckets: dict[
        tuple[str, int, tuple[tuple[int, int], ...]],
        list[dict[str, Any]],
    ] = defaultdict(list)
    nonempty_source_candidates: set[int] = set()
    support_sizes: list[int] = []
    max_coefficient = 0
    empty_directional_row_count = 0
    raw_directional_row_count = 0

    for mode_row in source_mode_rows:
        for direction, cells, need in (
            ("input", mode_row["input_cells"], int(mode_row["need_in"])),
            ("output", mode_row["output_cells"], int(mode_row["need_out"])),
        ):
            raw_directional_row_count += 1
            coefficients = coefficient_signature(
                cells=cells,
                target_coverers=target_coverers,
            )
            signature = (direction, need, coefficients)
            all_signatures.add(signature)
            if not coefficients:
                empty_directional_row_count += 1
                continue
            nonempty_source_candidates.add(int(mode_row["global_row_index"]))
            support_sizes.append(len(coefficients))
            max_coefficient = max(
                max_coefficient,
                max(value for _index, value in coefficients),
            )
            buckets[signature].append(
                {
                    "member_id": str(mode_row["member_id"]),
                    "global_row_index": int(mode_row["global_row_index"]),
                    "body_digest": str(mode_row["body_digest"]),
                    "template": str(mode_row["template"]),
                    "source_group": str(mode_row["source_group"]),
                    "pose_index": int(mode_row["pose_index"]),
                    "class_key": list(mode_row["class_key"]),
                    "direction": direction,
                }
            )

    bucket_payload: list[dict[str, Any]] = []
    for signature, members in sorted(
        buckets.items(),
        key=lambda item: (
            item[0][0],
            item[0][1],
            item[0][2],
        ),
    ):
        direction, need, coefficients = signature
        signature_payload = {
            "source_label": source_label,
            "target_label": target_label,
            "direction": direction,
            "required_free_count": int(need),
            "target_coefficients": [list(value) for value in coefficients],
        }
        bucket_payload.append(
            {
                "bucket_id": stable_digest(signature_payload),
                **signature_payload,
                "member_count": len(members),
                "members": sorted(
                    members,
                    key=lambda row: (
                        row["global_row_index"],
                        row["pose_index"],
                        row["class_key"],
                        row["direction"],
                    ),
                ),
            }
        )

    nonempty_directional_row_count = sum(
        int(bucket["member_count"]) for bucket in bucket_payload
    )
    if (
        nonempty_directional_row_count + empty_directional_row_count
        != raw_directional_row_count
    ):
        raise RuntimeError("E113 directional row accounting drift")
    return {
        "source_label": source_label,
        "target_label": target_label,
        "raw_mode_class_row_count": len(source_mode_rows),
        "raw_directional_row_count": raw_directional_row_count,
        "nonempty_directional_row_count": nonempty_directional_row_count,
        "empty_directional_row_count": empty_directional_row_count,
        "participating_source_candidate_count": len(nonempty_source_candidates),
        "unique_directional_signature_count_including_empty": len(all_signatures),
        "unique_nonempty_signature_count": len(bucket_payload),
        "nonempty_support_min": min(support_sizes) if support_sizes else 0,
        "nonempty_support_max": max(support_sizes) if support_sizes else 0,
        "nonempty_support_average": (
            sum(support_sizes) / len(support_sizes) if support_sizes else 0.0
        ),
        "maximum_target_coefficient": max_coefficient,
        "buckets": bucket_payload,
    }


def compile_partition(
    *,
    e095: types.ModuleType,
    prepared: Mapping[str, Any],
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    class_keys: Sequence[tuple[str, str, int, int]],
    partition: Mapping[str, Any],
) -> dict[str, Any]:
    left_groups = tuple(map(str, partition["left_groups"]))
    right_groups = tuple(map(str, partition["right_groups"]))
    left_rows = rows_for_groups(left_groups, grouped)
    right_rows = rows_for_groups(right_groups, grouped)
    left_label = "+".join(left_groups)
    right_label = "+".join(right_groups)
    left_modes = mode_class_rows(
        e095=e095,
        context=prepared["context"],
        rows=left_rows,
        class_keys=class_keys,
    )
    right_modes = mode_class_rows(
        e095=e095,
        context=prepared["context"],
        rows=right_rows,
        class_keys=class_keys,
    )
    body = body_conflict_payload(
        left_rows=left_rows,
        right_rows=right_rows,
    )
    left_front = compile_front_buckets(
        source_mode_rows=left_modes,
        target_rows=right_rows,
        source_label=left_label,
        target_label=right_label,
    )
    right_front = compile_front_buckets(
        source_mode_rows=right_modes,
        target_rows=left_rows,
        source_label=right_label,
        target_label=left_label,
    )
    metrics = {
        "body_conflict_edge_count": int(body["edge_count"]),
        "total_unique_directional_front_signatures": int(
            left_front["unique_directional_signature_count_including_empty"]
            + right_front["unique_directional_signature_count_including_empty"]
        ),
        "total_nonempty_directional_rows": int(
            left_front["nonempty_directional_row_count"]
            + right_front["nonempty_directional_row_count"]
        ),
        "maximum_side_candidate_count": max(len(left_rows), len(right_rows)),
    }
    payload = {
        "partition_id": str(partition["partition_id"]),
        "left_groups": list(left_groups),
        "right_groups": list(right_groups),
        "left_label": left_label,
        "right_label": right_label,
        "left_candidate_count": len(left_rows),
        "right_candidate_count": len(right_rows),
        "left_mode_class_row_count": len(left_modes),
        "right_mode_class_row_count": len(right_modes),
        "metrics": metrics,
        "candidate_identities": {
            "left": [
                candidate_identity(row)
                for row in sorted(
                    left_rows,
                    key=lambda value: int(value["global_row_index"]),
                )
            ],
            "right": [
                candidate_identity(row)
                for row in sorted(
                    right_rows,
                    key=lambda value: int(value["global_row_index"]),
                )
            ],
        },
        "body_conflicts": body,
        "left_front_by_right_body": left_front,
        "right_front_by_left_body": right_front,
    }
    payload["interface_digest"] = stable_digest(payload)
    return payload


def comparison_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "partition_id": str(payload["partition_id"]),
        "left_groups": list(payload["left_groups"]),
        "right_groups": list(payload["right_groups"]),
        "left_candidate_count": int(payload["left_candidate_count"]),
        "right_candidate_count": int(payload["right_candidate_count"]),
        "left_mode_class_row_count": int(payload["left_mode_class_row_count"]),
        "right_mode_class_row_count": int(payload["right_mode_class_row_count"]),
        "metrics": dict(payload["metrics"]),
        "body_participation": {
            "left": int(
                payload["body_conflicts"]["left_participating_candidate_count"]
            ),
            "right": int(
                payload["body_conflicts"]["right_participating_candidate_count"]
            ),
        },
        "front_participation": {
            "left": int(
                payload["left_front_by_right_body"][
                    "participating_source_candidate_count"
                ]
            ),
            "right": int(
                payload["right_front_by_left_body"][
                    "participating_source_candidate_count"
                ]
            ),
        },
        "interface_digest": str(payload["interface_digest"]),
    }


def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_metrics = left["metrics"]
    right_metrics = right["metrics"]
    no_worse = all(
        int(left_metrics[key]) <= int(right_metrics[key])
        for key in SELECTION_METRICS
    )
    strictly_better = any(
        int(left_metrics[key]) < int(right_metrics[key])
        for key in SELECTION_METRICS
    )
    return bool(no_worse and strictly_better)


def run(*, run_dir: Path) -> dict[str, Any]:
    identity = verify_identity()
    if run_dir.exists():
        raise FileExistsError(f"refusing to reuse E113 run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e113_source_e095")
    e100 = source_module(E100_RUNNER, "zmd_e113_source_e100")
    e110 = source_module(E110_RUNNER, "zmd_e113_source_e110")
    prepared = e110.restore_three_groups(e095=e095, e100=e100)
    grouped = group_rows(prepared)
    class_keys = tuple(
        sorted(
            key
            for key in prepared["context"]["class_counts"]
            if key[0] == "B"
        )
    )
    if len(class_keys) != EXPECTED_CLASS_COUNT:
        raise RuntimeError("E113 class dimension drift")

    compiled = [
        compile_partition(
            e095=e095,
            prepared=prepared,
            grouped=grouped,
            class_keys=class_keys,
            partition=partition,
        )
        for partition in PARTITIONS
    ]
    by_id = {str(payload["partition_id"]): payload for payload in compiled}
    dominant = [
        payload
        for payload in compiled
        if all(
            payload is other or dominates(payload, other)
            for other in compiled
        )
    ]
    selected = dominant[0] if len(dominant) == 1 else None
    comparison = {
        "schema": "zmd_e113_partition_comparison_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "selection_metrics": list(SELECTION_METRICS),
        "partitions": [comparison_record(payload) for payload in compiled],
        "dominance": {
            left_id: {
                right_id: bool(
                    left_id != right_id
                    and dominates(by_id[left_id], by_id[right_id])
                )
                for right_id in sorted(by_id)
            }
            for left_id in sorted(by_id)
        },
        "dominant_partition_ids": [
            str(payload["partition_id"]) for payload in dominant
        ],
        "selected_partition_id": (
            str(selected["partition_id"]) if selected is not None else None
        ),
        "truth_boundary": (
            "Static exact interface comparison only. Dominance concerns interface "
            "size metrics, not feasibility or runtime."
        ),
    }
    comparison_path = run_dir / "PARTITION_COMPARISON.json"
    dump_exclusive(comparison_path, comparison)

    selected_path = run_dir / "SELECTED_INTERFACE.json"
    if selected is not None:
        selected_payload = {
            "schema": "zmd_e113_selected_interaction_hypergraph_v1",
            "created_at_utc": utc_now(),
            "authority": "research_only_noncertified",
            "ledger_effect": "none",
            "class_order": [list(key) for key in class_keys],
            "selected_partition": selected,
            "transport_guard": (
                "global_row_index is a frozen-context handle and must be joined to "
                "body_digest/template/source_group before reuse"
            ),
            "truth_boundary": (
                "Complete static body-conflict and native-front coefficient interface "
                "for the selected partition. No witness or feasibility claim."
            ),
        }
        dump_exclusive(selected_path, selected_payload)

    if selected is not None and selected["partition_id"] == (
        "low__separator_plus_high"
    ):
        verdict = "LOW_VS_SEPARATOR_HIGH_CAP_INTERFACE_SELECTED"
        decision = "BUILD_SEPARATOR_HIGH_CAP_PROPOSER_WITH_LOW_CONSUMER"
    elif selected is not None:
        verdict = "ALTERNATE_TWO_WAY_INTERFACE_SELECTED"
        decision = "BUILD_SELECTED_PARTITION_PROPOSER_CONSUMER"
    else:
        verdict = "INTERACTION_PARTITIONS_INCOMPARABLE"
        decision = "PRESERVE_NONDOMINATED_PARTITION_FRONTIER"

    result = {
        "schema": "zmd_e113_separator_side_interaction_compiler_result_v1",
        "created_at_utc": utc_now(),
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "verdict": verdict,
        "decision": decision,
        "identity": identity,
        "restored_language": {
            "candidate_count": sum(EXPECTED_GROUP_COUNTS.values()),
            "group_candidate_counts": dict(EXPECTED_GROUP_COUNTS),
            "class_coordinate_count": len(class_keys),
            "separator_class_positive_state_count": 350,
            "separator_class_negative_state_count": 3,
        },
        "comparison": {
            "path": display(comparison_path),
            "sha256": sha256_file(comparison_path),
            "selected_partition_id": comparison["selected_partition_id"],
            "dominant_partition_ids": comparison["dominant_partition_ids"],
        },
        "selected_interface": (
            {
                "path": display(selected_path),
                "sha256": sha256_file(selected_path),
                "partition_id": selected["partition_id"],
                "metrics": selected["metrics"],
                "left_candidate_count": selected["left_candidate_count"],
                "right_candidate_count": selected["right_candidate_count"],
                "body_conflict_edge_count": selected["body_conflicts"]["edge_count"],
                "left_front_bucket_count": selected[
                    "left_front_by_right_body"
                ]["unique_nonempty_signature_count"],
                "right_front_bucket_count": selected[
                    "right_front_by_left_body"
                ]["unique_nonempty_signature_count"],
                "interface_digest": selected["interface_digest"],
            }
            if selected is not None
            else None
        ),
        "truth_boundary": (
            "E113 compiles exact static cross-module constraints and selects only "
            "by preregistered interface dominance. It proves no constructor feasible."
        ),
    }
    result_path = run_dir / "RESULT.json"
    dump_exclusive(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    failure_path = run_dir / "FAILURE.json"
    try:
        result = run(run_dir=run_dir)
        result_path = run_dir / "RESULT.json"
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "decision": result["decision"],
                    "selected_interface": result["selected_interface"],
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
            "schema": "zmd_e113_execution_failure_v1",
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
