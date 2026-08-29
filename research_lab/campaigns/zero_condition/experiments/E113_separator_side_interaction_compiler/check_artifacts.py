#!/usr/bin/env python3
"""Independent integrity and semantic replay for E113."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
import types
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e113.py"
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E113_separator_side_interaction_compiler/run-001"
)
RESULT = RUN / "RESULT.json"
COMPARISON = RUN / "PARTITION_COMPARISON.json"
SELECTED = RUN / "SELECTED_INTERFACE.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"
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
E112_CHECK = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E112_fixed_separator_class_state_closure/run-001/ARTIFACT_CHECK.json"
)

EXPECTED = {
    RUNNER: "84e8cca03649d9da68c12d0ba747bd2a954b9b8d6529d6575b259cf1e6801c6e",
    RESULT: "511d5592142dcdce1832eca99e9d000ab439c2fee28d58b0f103aba96fb0108c",
    COMPARISON: "1c27fd5f77de1f3d9a588c4af43a2a17e29b543b15c7d376ac16f7886bc2d4d0",
    SELECTED: "1cd4674b1676a24f28fe39e2dec9d8286f700936fcc870b35fcc863fd47c7d98",
    OPERATION_PROFILES: "0dd774150011ec6adb2ccaff554e08aeeeb0a111d7b25de28de713d728d36a79",
    E095_RUNNER: "4f73c41eace3418af9015153989ba8b5863107723aac8a1f9f3e2141c02d392d",
    E100_RUNNER: "2360315f72aef7a7b8bc85cccd35a4e91061056d8b8e1539559fbe5a12ebb190",
    E110_RUNNER: "30b2fc298ef56ba68053d47977ef139890e862568b53bba70bdf541f677a1fea",
    E112_CHECK: "cdbae6428ba1514646e12836de069b26104e1872f7356b63fb1bdeb4c34e5e03",
}

GROUPS = ("low", "separator", "high")
PARTITIONS = {
    "low__separator_plus_high": (("low",), ("separator", "high")),
    "low_plus_separator__high": (("low", "separator"), ("high",)),
    "low_plus_high__separator": (("low", "high"), ("separator",)),
}
SELECTION_METRICS = (
    "body_conflict_edge_count",
    "total_unique_directional_front_signatures",
    "total_nonempty_directional_rows",
    "maximum_side_candidate_count",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
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
        compile(
            raw,
            f"<source-isolated-check:{path}:{hashlib.sha256(raw).hexdigest()}>",
            "exec",
            dont_inherit=True,
        ),
        module.__dict__,
    )
    return module


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def rows_for(
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    groups: Sequence[str],
) -> list[dict[str, Any]]:
    return [dict(row) for group in groups for row in grouped[group]]


def coverers(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[int, int], tuple[int, ...]]:
    raw: dict[tuple[int, int], set[int]] = defaultdict(set)
    for row in rows:
        global_index = int(row["global_row_index"])
        for cell in row["body"]:
            raw[cell].add(global_index)
    return {cell: tuple(sorted(values)) for cell, values in raw.items()}


def independent_mode_rows(
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
        for pose_index in row["mode_pose_indices"]:
            pose = pools[template][int(pose_index)]
            fronts = {
                "input": tuple(e095.cell(value) for value in pose["input_port_cells"]),
                "output": tuple(e095.cell(value) for value in pose["output_port_cells"]),
            }
            for class_key in class_keys:
                if class_key[1] != template:
                    continue
                need_in = int(class_key[2])
                need_out = int(class_key[3])
                if forced is not None and (need_in, need_out) != forced:
                    continue
                if need_in > len(fronts["input"]) or need_out > len(fronts["output"]):
                    continue
                identity = {
                    "global_row_index": int(row["global_row_index"]),
                    "body_digest": str(row["body_digest"]),
                    "template": template,
                    "source_group": str(row["separator_group"]),
                    "pose_index": int(pose_index),
                    "class_key": list(class_key),
                    "need_in": need_in,
                    "need_out": need_out,
                }
                output.append(
                    {
                        **identity,
                        "member_id": stable_digest(identity),
                        "fronts": fronts,
                    }
                )
    require(
        len({row["member_id"] for row in output}) == len(output),
        "independent mode/member identity collision",
    )
    return output


def coefficient_map(
    cells: Sequence[tuple[int, int]],
    target_coverers: Mapping[tuple[int, int], Sequence[int]],
) -> tuple[tuple[int, int], ...]:
    values: Counter[int] = Counter()
    for cell in cells:
        for target_index in target_coverers.get(cell, ()):
            values[int(target_index)] += 1
    return tuple(sorted((key, int(value)) for key, value in values.items()))


def independent_partition_metrics(
    *,
    e095: types.ModuleType,
    context: Mapping[str, Any],
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    class_keys: Sequence[tuple[str, str, int, int]],
    left_groups: Sequence[str],
    right_groups: Sequence[str],
) -> dict[str, Any]:
    left_rows = rows_for(grouped, left_groups)
    right_rows = rows_for(grouped, right_groups)
    left_coverers = coverers(left_rows)
    right_coverers = coverers(right_rows)

    edges: set[tuple[int, int]] = set()
    for row in left_rows:
        left_index = int(row["global_row_index"])
        for cell in row["body"]:
            for right_index in right_coverers.get(cell, ()):
                edges.add((left_index, int(right_index)))

    def directed(
        source_rows: Sequence[Mapping[str, Any]],
        target_coverers: Mapping[tuple[int, int], Sequence[int]],
    ) -> tuple[int, int]:
        signatures: set[tuple[str, int, tuple[tuple[int, int], ...]]] = set()
        nonempty = 0
        for mode_row in independent_mode_rows(
            e095=e095,
            context=context,
            rows=source_rows,
            class_keys=class_keys,
        ):
            for direction, need in (
                ("input", int(mode_row["need_in"])),
                ("output", int(mode_row["need_out"])),
            ):
                coefficients = coefficient_map(
                    mode_row["fronts"][direction],
                    target_coverers,
                )
                signatures.add((direction, need, coefficients))
                nonempty += int(bool(coefficients))
        return len(signatures), nonempty

    left_signatures, left_nonempty = directed(left_rows, right_coverers)
    right_signatures, right_nonempty = directed(right_rows, left_coverers)
    return {
        "body_conflict_edge_count": len(edges),
        "total_unique_directional_front_signatures": (
            left_signatures + right_signatures
        ),
        "total_nonempty_directional_rows": left_nonempty + right_nonempty,
        "maximum_side_candidate_count": max(len(left_rows), len(right_rows)),
        "edge_set": edges,
    }


def verify_selected_buckets(
    *,
    e095: types.ModuleType,
    context: Mapping[str, Any],
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    class_keys: Sequence[tuple[str, str, int, int]],
    selected_partition: Mapping[str, Any],
) -> dict[str, Any]:
    left_groups = tuple(map(str, selected_partition["left_groups"]))
    right_groups = tuple(map(str, selected_partition["right_groups"]))
    left_rows = rows_for(grouped, left_groups)
    right_rows = rows_for(grouped, right_groups)
    for side_name, expected_rows in (("left", left_rows), ("right", right_rows)):
        observed = selected_partition["candidate_identities"][side_name]
        require(len(observed) == len(expected_rows), f"{side_name} candidate count drift")
        observed_by_index = {
            int(row["global_row_index"]): row for row in observed
        }
        require(len(observed_by_index) == len(observed), f"{side_name} identity collision")
        for row in expected_rows:
            global_index = int(row["global_row_index"])
            require(global_index in observed_by_index, f"missing {side_name} candidate")
            identity = observed_by_index[global_index]
            require(str(identity["body_digest"]) == str(row["body_digest"]), "candidate digest drift")
            require(str(identity["template"]) == str(row["template"]), "candidate template drift")
            require(str(identity["source_group"]) == str(row["separator_group"]), "candidate group drift")

    expected_metrics = independent_partition_metrics(
        e095=e095,
        context=context,
        grouped=grouped,
        class_keys=class_keys,
        left_groups=left_groups,
        right_groups=right_groups,
    )
    observed_edges = {
        tuple(map(int, edge))
        for edge in selected_partition["body_conflicts"]["edges"]
    }
    require(observed_edges == expected_metrics["edge_set"], "selected body edge set drift")

    def check_direction(
        *,
        source_rows: Sequence[Mapping[str, Any]],
        target_rows: Sequence[Mapping[str, Any]],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        target_coverers = coverers(target_rows)
        modes = independent_mode_rows(
            e095=e095,
            context=context,
            rows=source_rows,
            class_keys=class_keys,
        )
        modes_by_member = {str(row["member_id"]): row for row in modes}
        expected_members: set[tuple[str, str]] = set()
        empty_count = 0
        unique_signatures: set[
            tuple[str, int, tuple[tuple[int, int], ...]]
        ] = set()
        for mode_row in modes:
            for direction, need in (
                ("input", int(mode_row["need_in"])),
                ("output", int(mode_row["need_out"])),
            ):
                coefficients = coefficient_map(
                    mode_row["fronts"][direction],
                    target_coverers,
                )
                unique_signatures.add((direction, need, coefficients))
                if coefficients:
                    expected_members.add((str(mode_row["member_id"]), direction))
                else:
                    empty_count += 1

        observed_members: set[tuple[str, str]] = set()
        bucket_ids: set[str] = set()
        for bucket in payload["buckets"]:
            bucket_id = str(bucket["bucket_id"])
            require(bucket_id not in bucket_ids, "duplicate front bucket id")
            bucket_ids.add(bucket_id)
            direction = str(bucket["direction"])
            need = int(bucket["required_free_count"])
            coefficients = tuple(
                (int(value[0]), int(value[1]))
                for value in bucket["target_coefficients"]
            )
            signature_payload = {
                "source_label": str(bucket["source_label"]),
                "target_label": str(bucket["target_label"]),
                "direction": direction,
                "required_free_count": need,
                "target_coefficients": [list(value) for value in coefficients],
            }
            require(stable_digest(signature_payload) == bucket_id, "bucket id digest drift")
            require(bool(coefficients), "selected interface stores empty bucket")
            require(len(bucket["members"]) == int(bucket["member_count"]), "bucket member count drift")
            for member in bucket["members"]:
                member_id = str(member["member_id"])
                member_key = (member_id, direction)
                require(member_key not in observed_members, "duplicate directional member")
                observed_members.add(member_key)
                require(member_id in modes_by_member, "unknown bucket member")
                mode_row = modes_by_member[member_id]
                require(int(member["global_row_index"]) == int(mode_row["global_row_index"]), "member row drift")
                require(str(member["body_digest"]) == str(mode_row["body_digest"]), "member digest drift")
                require(int(member["pose_index"]) == int(mode_row["pose_index"]), "member pose drift")
                require(list(member["class_key"]) == list(mode_row["class_key"]), "member class drift")
                expected_need = int(
                    mode_row["need_in"] if direction == "input" else mode_row["need_out"]
                )
                require(need == expected_need, "member need drift")
                expected_coefficients = coefficient_map(
                    mode_row["fronts"][direction],
                    target_coverers,
                )
                require(coefficients == expected_coefficients, "member coefficient drift")

        require(observed_members == expected_members, "front bucket member coverage drift")
        require(int(payload["empty_directional_row_count"]) == empty_count, "empty row count drift")
        require(
            int(payload["unique_directional_signature_count_including_empty"])
            == len(unique_signatures),
            "unique signature count drift",
        )
        require(
            int(payload["nonempty_directional_row_count"])
            == len(expected_members),
            "nonempty row count drift",
        )
        return {
            "raw_mode_class_row_count": len(modes),
            "nonempty_directional_row_count": len(expected_members),
            "empty_directional_row_count": empty_count,
            "unique_signature_count": len(unique_signatures),
            "bucket_count": len(bucket_ids),
        }

    left_replay = check_direction(
        source_rows=left_rows,
        target_rows=right_rows,
        payload=selected_partition["left_front_by_right_body"],
    )
    right_replay = check_direction(
        source_rows=right_rows,
        target_rows=left_rows,
        payload=selected_partition["right_front_by_left_body"],
    )
    return {
        "body_conflict_edge_count": len(observed_edges),
        "left_front_replay": left_replay,
        "right_front_replay": right_replay,
    }


def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return bool(
        all(int(left[key]) <= int(right[key]) for key in SELECTION_METRICS)
        and any(int(left[key]) < int(right[key]) for key in SELECTION_METRICS)
    )


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E113 check: {OUTPUT}")
    artifact_records: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E113 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E113 artifact identity drift: {path}")
        artifact_records[display(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    comparison = load(COMPARISON)
    selected_payload = load(SELECTED)
    selected = selected_payload["selected_partition"]
    require(result["verdict"] == "LOW_VS_SEPARATOR_HIGH_CAP_INTERFACE_SELECTED", "verdict drift")
    require(result["decision"] == "BUILD_SEPARATOR_HIGH_CAP_PROPOSER_WITH_LOW_CONSUMER", "decision drift")
    require(comparison["selected_partition_id"] == "low__separator_plus_high", "selected partition drift")
    require(comparison["dominant_partition_ids"] == ["low__separator_plus_high"], "dominant set drift")
    require(selected["partition_id"] == "low__separator_plus_high", "selected payload drift")
    digest_input = dict(selected)
    observed_digest = str(digest_input.pop("interface_digest"))
    require(stable_digest(digest_input) == observed_digest, "selected interface digest drift")

    e112_check = load(E112_CHECK)
    require(e112_check["status"] == "PASS", "E112 check drift")
    require(
        e112_check["compact_negative_rule"]
        == result["identity"]["compact_negative_rule"],
        "compact negative rule transport drift",
    )

    source_module(
        OPERATION_PROFILES,
        "src.preprocess.operation_profiles",
        package="src.preprocess",
    )
    e095 = source_module(E095_RUNNER, "zmd_e113_check_e095")
    e100 = source_module(E100_RUNNER, "zmd_e113_check_e100")
    e110 = source_module(E110_RUNNER, "zmd_e113_check_e110")
    prepared = e110.restore_three_groups(e095=e095, e100=e100)
    grouped = {
        group: [
            row
            for row in prepared["rows"]
            if str(row["separator_group"]) == group
        ]
        for group in GROUPS
    }
    class_keys = tuple(
        sorted(
            key
            for key in prepared["context"]["class_counts"]
            if key[0] == "B"
        )
    )
    require([list(key) for key in class_keys] == selected_payload["class_order"], "class order drift")

    comparison_by_id = {
        str(row["partition_id"]): row for row in comparison["partitions"]
    }
    independent_metrics: dict[str, dict[str, int]] = {}
    for partition_id, (left_groups, right_groups) in PARTITIONS.items():
        replay = independent_partition_metrics(
            e095=e095,
            context=prepared["context"],
            grouped=grouped,
            class_keys=class_keys,
            left_groups=left_groups,
            right_groups=right_groups,
        )
        metrics = {
            key: int(replay[key]) for key in SELECTION_METRICS
        }
        independent_metrics[partition_id] = metrics
        require(
            metrics == comparison_by_id[partition_id]["metrics"],
            f"partition metric drift: {partition_id}",
        )
    selected_metrics = independent_metrics["low__separator_plus_high"]
    require(
        all(
            partition_id == "low__separator_plus_high"
            or dominates(selected_metrics, metrics)
            for partition_id, metrics in independent_metrics.items()
        ),
        "selected partition does not dominate all alternatives",
    )

    selected_replay = verify_selected_buckets(
        e095=e095,
        context=prepared["context"],
        grouped=grouped,
        class_keys=class_keys,
        selected_partition=selected,
    )
    payload = {
        "schema": "zmd_e113_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "LOW_SEPARATOR_HIGH_CAP_DOMINATES_STATIC_INTERFACE_FRONTIER",
        "artifact_records": artifact_records,
        "independent_partition_metrics": independent_metrics,
        "selected_partition_id": "low__separator_plus_high",
        "selected_interface_replay": selected_replay,
        "selected_interface_digest": observed_digest,
        "compact_separator_negative_rule": e112_check["compact_negative_rule"],
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Every selected body edge and nonempty directional coefficient bucket "
            "is independently replayed. Dominance is static interface dominance, "
            "not a feasibility or runtime proof."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": payload["classification"],
                "selected_partition_id": payload["selected_partition_id"],
                "metrics": selected_metrics,
                "selected_interface_replay": selected_replay,
                "decision": payload["decision"],
                "output_path": display(OUTPUT),
                "output_sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
