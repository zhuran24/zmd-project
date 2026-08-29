#!/usr/bin/env python3
"""Independent interface joins for E103."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_e103.py"
RUN = ROOT / "research_lab/local/zero_condition/E103_high_side_interface_capacity_audit/run-003"
RESULT = RUN / "RESULT.json"
CANDIDATES = RUN / "LIVE_HIGH_CANDIDATES.json"
TEMPLATE = RUN / "TEMPLATE_INTERFACE.json"
SPATIAL = RUN / "SPATIAL_FRONTIER.json"
CAPABILITY = RUN / "CAPABILITY_ATLAS.json"
HALL = RUN / "HALL_BOUNDS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "3185bc717e8c0438a47148972476d6176fee8643e23bcb7167a6b54f4be99f48",
    RESULT: "6fefd59e3b8c5551501a2504e9c620bb6cc5468ac5847b92baa20a8ec6e6a32c",
    CANDIDATES: "ebf0c34b174df7036cf6c4bf2f3283dd4ea303998f62520cbd0c74d70aebfd08",
    TEMPLATE: "a1b7cbe4b24a68f6cac280ca9825838f86160da849911b4c8017541adee6573f",
    SPATIAL: "7b742149075df693c3b5085c59e18f9a45c6fddfb3be73a13419b4565ab5d660",
    CAPABILITY: "62b1bebf8281d08c4ed917343aa5703b704d36f19acbe714fdf06f9864c2ec73",
    HALL: "31c82a8e67ebcb9696dacd922a84016322d09ca21e691b61a5e4c0a63ebaee70",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def cell(value: Sequence[int]) -> tuple[int, int]:
    return int(value[0]), int(value[1])


def interface(
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
    shared: set[tuple[int, int]] = set()
    cross: set[tuple[int, int]] = set()
    participants: set[int] = set()
    for value, indices in body_coverers.items():
        if len({groups[index] for index in indices}) > 1:
            shared.add(value)
            participants.update(indices)
    for index, row in enumerate(records):
        source = groups[index]
        for value in map(cell, row["front_cells"]):
            targets = [
                target
                for target in body_coverers.get(value, [])
                if groups[target] != source
            ]
            if targets:
                cross.add(value)
                participants.add(index)
                participants.update(targets)
    return {
        "group_candidate_counts": dict(sorted(group_counts.items())),
        "group_anchor_counts": dict(sorted(anchor_counts.items())),
        "shared_body_cell_count": len(shared),
        "cross_front_body_cell_count": len(cross),
        "interface_occupancy_cell_count": len(shared | cross),
        "interface_candidate_count": len(participants),
        "largest_group_candidate_count": max(group_counts.values()),
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


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E103 check: {OUTPUT}")
    records_by_path: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E103 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E103 artifact identity drift: {path}")
        records_by_path[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    candidate_payload = load(CANDIDATES)
    records = candidate_payload["candidates"]
    template = load(TEMPLATE)
    spatial = load(SPATIAL)
    capability = load(CAPABILITY)
    hall = load(HALL)
    require(len(records) == 1205, "E103 live candidate count drift")
    require(sum(bool(row["is_anchor"]) for row in records) == 25, "live anchor drift")
    require(candidate_payload["unary_filter_summary"] == result["unary_filter_summary"], "unary summary join drift")

    template_groups = {
        index: str(row["template"]) for index, row in enumerate(records)
    }
    template_replay = interface(records, template_groups)
    for key in (
        "group_candidate_counts",
        "shared_body_cell_count",
        "cross_front_body_cell_count",
        "interface_occupancy_cell_count",
        "interface_candidate_count",
        "largest_group_candidate_count",
    ):
        require(template_replay[key] == template[key], f"template replay drift: {key}")

    selected = result["selected_spatial_cut"]
    require(selected["cut_id"] == "y_after_59", "selected cut drift")
    selected_groups = {
        index: classify(row, "y", 59) for index, row in enumerate(records)
    }
    selected_replay = interface(records, selected_groups)
    for key in (
        "group_candidate_counts",
        "group_anchor_counts",
        "shared_body_cell_count",
        "cross_front_body_cell_count",
        "interface_occupancy_cell_count",
        "interface_candidate_count",
        "largest_group_candidate_count",
    ):
        require(selected_replay[key] == selected[key], f"spatial replay drift: {key}")
    guarded = [row for row in spatial["cuts"] if bool(row["balance_guard_pass"])]
    require(len(guarded) > 0, "no guarded cut")
    ordered = sorted(
        guarded,
        key=lambda row: (
            int(row["interface_occupancy_cell_count"]),
            int(row["group_candidate_counts"].get("separator", 0)),
            float(row["allocation_log2_upper_bound"]),
            int(row["largest_group_candidate_count"]),
            str(row["axis"]),
            int(row["coordinate"]),
        ),
    )
    require(ordered[0]["cut_id"] == "y_after_59", "frontier minimum drift")

    require(capability["signature_count"] == 5, "capability signature count drift")
    require(
        capability["per_template_signature_counts"]
        == {
            "manufacturing_3x3": 1,
            "manufacturing_5x5": 1,
            "manufacturing_6x4": 3,
        },
        "capability template signature drift",
    )
    require(capability["full_capability_candidate_count"] == 1203, "full capability count drift")
    require(hall["nontrivial_bound_count"] == 0, "proper-subset Hall count drift")
    require(
        all(
            row["template_total_identity"] is True and row["nontrivial"] is False
            for row in hall["bounds"]
            if row["proper_subset"] is False
        ),
        "full-set Hall identity drift",
    )
    require(
        not any(row["nontrivial"] for row in hall["bounds"] if row["proper_subset"]),
        "proper-subset Hall tightening drift",
    )

    require(result["capability_degenerate"] is True, "capability degeneracy drift")
    require(result["hybrid_guard_pass"] is True, "hybrid guard drift")
    require(
        result["verdict"] == "HIGH_SIDE_SPATIAL_TEMPLATE_HYBRID_SELECTED",
        "E103 verdict drift",
    )
    require(
        result["decision"]
        == "RESERVE_SELECTED_SPATIAL_ROW_WITH_TEMPLATE_CLASS_BRIDGE",
        "E103 decision drift",
    )
    require(
        int(selected["interface_occupancy_cell_count"]) * 3
        <= int(template["interface_occupancy_cell_count"]),
        "hybrid interface-cell guard drift",
    )
    require(
        int(selected["interface_candidate_count"]) * 2
        <= int(template["interface_candidate_count"]),
        "hybrid candidate guard drift",
    )
    require(
        float(selected["separator_candidate_fraction"]) <= 0.15,
        "hybrid separator guard drift",
    )

    payload = {
        "schema": "zmd_e103_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "classification": "HIGH_SIDE_HYBRID_SELECTION_REPLAYED",
        "artifact_records": records_by_path,
        "template_replay": template_replay,
        "selected_spatial_replay": selected_replay,
        "proper_subset_nontrivial_hall_bounds": 0,
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent live-candidate interface replay. Metrics select a "
            "representation only; no high-side feasibility claim follows."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(json.dumps({
        "status": "PASS",
        "classification": payload["classification"],
        "selected_cut_id": selected["cut_id"],
        "verdict": payload["verdict"],
        "decision": payload["decision"],
        "output_path": str(OUTPUT.relative_to(ROOT)),
        "output_sha256": sha256(OUTPUT),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
