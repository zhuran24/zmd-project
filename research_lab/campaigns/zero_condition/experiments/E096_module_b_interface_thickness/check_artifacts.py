#!/usr/bin/env python3
"""Independent finite replay of E096's template and selected spatial interfaces."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[5]
RUN = (
    ROOT
    / "research_lab/local/zero_condition/"
    "E096_module_b_interface_thickness/run-001"
)
RUNNER = Path(__file__).with_name("run_e096.py")
RESULT = RUN / "RESULT.json"
TEMPLATE = RUN / "TEMPLATE_INTERFACE.json"
SPATIAL = RUN / "SPATIAL_INTERFACE_FRONTIER.json"
CANDIDATES = RUN / "B_CANDIDATE_INTERFACE_RECORDS.json"
OUTPUT = RUN / "ARTIFACT_CHECK.json"

EXPECTED = {
    RUNNER: "3d4825e2f1820f176a9dd97d5a167fa51171e38d612ff9ca53e268eb5f15697d",
    RESULT: "b16062ce71a9bf40943bd9adcb788249b68099906ab4bb360d48800230dc10f2",
    TEMPLATE: "1f566e2cce5682e51da52cc9f0b69792781e54b42033564d8b548c10dd972c11",
    SPATIAL: "949a39da7261804d383b99b4f61b78813032b9816d129178e5995add2f41448e",
    CANDIDATES: "c94b4d2fca806984904146706ff0dddc8e79bc675cedade4a700b7b59f029843",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cell(value: Any) -> tuple[int, int]:
    return int(value[0]), int(value[1])


def dump_exclusive(path: Path, value: Any) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def replay_interface(
    records: Sequence[Mapping[str, Any]],
    groups: Mapping[int, str],
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

    shared_body: set[tuple[int, int]] = set()
    cross_front: set[tuple[int, int]] = set()
    participants: set[int] = set()
    for value, indices in body_coverers.items():
        if len({groups[index] for index in indices}) > 1:
            shared_body.add(value)
            participants.update(indices)
    for index, row in enumerate(records):
        group = groups[index]
        for value in map(cell, row["front_cells"]):
            other = [
                target
                for target in body_coverers.get(value, [])
                if groups[target] != group
            ]
            if other:
                cross_front.add(value)
                participants.add(index)
                participants.update(other)
    return {
        "group_candidate_counts": dict(sorted(group_counts.items())),
        "group_anchor_counts": dict(sorted(anchor_counts.items())),
        "shared_body_cell_count": len(shared_body),
        "cross_front_body_cell_count": len(cross_front),
        "interface_occupancy_cell_count": len(shared_body | cross_front),
        "interface_candidate_count": len(participants),
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite E096 check: {OUTPUT}")
    records_by_path: dict[str, Any] = {}
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing E096 artifact: {path}")
        actual = sha256(path)
        require(actual == expected, f"E096 artifact identity drift: {path}")
        records_by_path[str(path)] = {
            "sha256": actual,
            "size_bytes": path.stat().st_size,
        }

    result = load(RESULT)
    template = load(TEMPLATE)
    spatial = load(SPATIAL)
    records = load(CANDIDATES)["candidates"]
    require(len(records) == 4378, "E096 candidate count drift")
    require(sum(bool(row["is_anchor"]) for row in records) == 91, "anchor count drift")
    require(
        result["verdict"]
        == "SPATIAL_SEPARATOR_INTERFACE_DOMINATES_TEMPLATE_INTERFACE",
        "E096 verdict drift",
    )
    require(
        result["decision"] == "SELECT_SPATIAL_SEPARATOR_DECOMPOSITION",
        "E096 decision drift",
    )

    template_groups = {
        index: str(row["template"]) for index, row in enumerate(records)
    }
    template_replay = replay_interface(records, template_groups)
    for key in (
        "group_candidate_counts",
        "shared_body_cell_count",
        "cross_front_body_cell_count",
        "interface_occupancy_cell_count",
        "interface_candidate_count",
    ):
        require(template_replay[key] == template[key], f"template replay drift: {key}")

    selected = result["selected_spatial_cut"]
    require(selected["cut_id"] == "x_after_34", "selected cut drift")
    groups: dict[int, str] = {}
    for index, row in enumerate(records):
        low = int(row["bbox"]["min_x"])
        high = int(row["bbox"]["max_x"])
        if high <= 34:
            groups[index] = "low"
        elif low > 34:
            groups[index] = "high"
        else:
            groups[index] = "separator"
    spatial_replay = replay_interface(records, groups)
    for key in (
        "group_candidate_counts",
        "group_anchor_counts",
        "shared_body_cell_count",
        "cross_front_body_cell_count",
        "interface_occupancy_cell_count",
        "interface_candidate_count",
    ):
        require(spatial_replay[key] == selected[key], f"spatial replay drift: {key}")
    require(selected["class_allocation_dimension_count"] == 8, "allocation dimension drift")
    require(selected["balance_guard_pass"] is True, "selected cut guard is not PASS")
    require(
        int(selected["interface_occupancy_cell_count"]) * 2
        <= int(template["interface_occupancy_cell_count"]),
        "spatial cut does not satisfy frozen cell dominance",
    )
    require(
        int(selected["group_candidate_counts"]["separator"]) <= int(4378 * 0.20),
        "spatial separator exceeds frozen fraction",
    )
    require(
        int(selected["largest_side_candidate_count"])
        < int(template["largest_group_candidate_count"]),
        "spatial largest side does not dominate template group",
    )

    payload = {
        "schema": "zmd_e096_artifact_check_v1",
        "authority": "research_only_noncertified",
        "ledger_effect": "none",
        "status": "PASS",
        "artifact_records": records_by_path,
        "template_replay": template_replay,
        "selected_spatial_replay": spatial_replay,
        "selected_cut_id": selected["cut_id"],
        "class_allocation_dimension_count": selected[
            "class_allocation_dimension_count"
        ],
        "verdict": result["verdict"],
        "decision": result["decision"],
        "truth_boundary": (
            "Independent finite interaction replay only; interface counts are not "
            "runtime or feasibility claims."
        ),
    }
    dump_exclusive(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "decision": payload["decision"],
                "template_interface_cells": template_replay[
                    "interface_occupancy_cell_count"
                ],
                "spatial_interface_cells": spatial_replay[
                    "interface_occupancy_cell_count"
                ],
                "spatial_separator_candidates": spatial_replay[
                    "group_candidate_counts"
                ]["separator"],
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
