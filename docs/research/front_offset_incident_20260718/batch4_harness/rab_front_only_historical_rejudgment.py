"""Pinned Batch 4 rejudgment of historical RAB front filtering.

This is deliberately a front-only reconstruction, not a full replay of the
historical PortBindingModel.  It compares three geometry arms on the six pinned
2026-07-16 layouts:

* current production binding enumeration plus corrected port_front_status;
* an independent oracle that treats stored port (x, y) as the front cell and
  checks it directly against independently rebuilt facility-body occupancy.
* a comparison-only reconstruction of the incident-era stored-coordinate plus
  literal direction-delta rule, including its self-occupied-cell exemption.

The old candidate pool, every layout, and the historical RFSC interpretation
are pinned.  A layout is counted only after pose_idx has been proven to name
the same pose_id and anchor in the old pool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.port_binding import (  # noqa: E402
    clear_pose_level_binding_domain_cache,
    enumerate_pose_level_port_bindings_with_cache_info,
    is_routing_visible_output_commodity,
    routing_visible_port_demands,
    supports_exact_pose_level_binding,
)
from src.models.routing_binding_context import (  # noqa: E402
    RoutingBindingContext,
    build_routing_binding_context,
    port_front_status,
)


SCHEMA_VERSION = "rab_front_only_historical_rejudgment_v2"
RESULT_LABEL = (
    "front_only_historical_rejudgment / reconstructed_new_baseline / "
    "historical_plus_delta_comparison"
)
GRID_WIDTH = 70
GRID_HEIGHT = 70

OLD_CANDIDATE_SHA256 = (
    "a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b"
)
OLD_CANDIDATE_POSE_COUNT = 66_405
PINNED_RFSC = frozenset({"qiaoyu_capsule", "valley_battery"})
HISTORICAL_DIR_DELTA = {
    "N": (0, 1),
    "S": (0, -1),
    "E": (1, 0),
    "W": (-1, 0),
}
HISTORICAL_FRONT_SOURCE_REVISION = "f82843d00ea4bc5824b5ec95ddd563ef01c0a322"
HISTORICAL_FRONT_SOURCE_PATH = "src/models/routing_binding_context.py"
HISTORICAL_FRONT_SOURCE_SHA256 = (
    "da219d9e2a95d59cdc9389df3ca08e9b329f0a2b2ed72c07e835937b677c1665"
)

PINNED_LAYOUT_SHA256 = {
    "layout_000_2011ebcc2cff.json": (
        "2011ebcc2cff308f9afe7b87d62d1b619a4bccdd9a055b2b5ca4448e8cdddbc2"
    ),
    "layout_001_5e6a95d0d2db.json": (
        "5e6a95d0d2db224cc10eff967eda14bd419581e846c58591177e339c048e628b"
    ),
    "layout_002_b3b6be0a8d69.json": (
        "b3b6be0a8d69b7c1375f8894691487bc8bcd6717e797a17e520f7bc8edf7e33c"
    ),
    "layout_003_5a1e599faf39.json": (
        "5a1e599faf391e900bbceae0a99c2e98acc1ad8fa8c218622e5fc0d3471b8f55"
    ),
    "layout_004_63831c3cb587.json": (
        "63831c3cb587f158960b99f3a57c588264cb435ebcaf1fffdb6cddb5aa874814"
    ),
    "layout_005_ddfc4a823f41.json": (
        "ddfc4a823f41dbc38c02f579a9ee94fe8de107e61812bae9f5439e35856b1020"
    ),
}

# This is a canary, not an input to the calculation.  Drift in either current
# production behavior or the independent oracle must be reviewed explicitly.
EXPECTED_RECONSTRUCTED_BASELINE = {
    "layout_000_2011ebcc2cff.json": {
        "checked": 219,
        "empty": 215,
        "old_empty": 216,
        "old_empty_to_corrected_nonempty": 1,
        "old_nonempty": 3,
        "old_nonempty_to_corrected_empty": 0,
        "identity_checks": 293,
        "nonempty": 4,
    },
    "layout_001_5e6a95d0d2db.json": {
        "checked": 219,
        "empty": 208,
        "old_empty": 218,
        "old_empty_to_corrected_nonempty": 10,
        "old_nonempty": 1,
        "old_nonempty_to_corrected_empty": 0,
        "identity_checks": 291,
        "nonempty": 11,
    },
    "layout_002_b3b6be0a8d69.json": {
        "checked": 219,
        "empty": 194,
        "old_empty": 214,
        "old_empty_to_corrected_nonempty": 20,
        "old_nonempty": 5,
        "old_nonempty_to_corrected_empty": 0,
        "identity_checks": 292,
        "nonempty": 25,
    },
    "layout_003_5a1e599faf39.json": {
        "checked": 219,
        "empty": 200,
        "old_empty": 217,
        "old_empty_to_corrected_nonempty": 17,
        "old_nonempty": 2,
        "old_nonempty_to_corrected_empty": 0,
        "identity_checks": 293,
        "nonempty": 19,
    },
    "layout_004_63831c3cb587.json": {
        "checked": 219,
        "empty": 199,
        "old_empty": 216,
        "old_empty_to_corrected_nonempty": 17,
        "old_nonempty": 3,
        "old_nonempty_to_corrected_empty": 0,
        "identity_checks": 294,
        "nonempty": 20,
    },
    "layout_005_ddfc4a823f41.json": {
        "checked": 219,
        "empty": 198,
        "old_empty": 213,
        "old_empty_to_corrected_nonempty": 15,
        "old_nonempty": 6,
        "old_nonempty_to_corrected_empty": 0,
        "identity_checks": 294,
        "nonempty": 21,
    },
}

EXPECTED_TOTALS = {
    "eligible_mandatory_owners_checked": 1_314,
    "independent_empty": 1_214,
    "independent_nonempty": 100,
    "mismatches": 0,
    "old_empty": 1_294,
    "old_empty_to_corrected_nonempty": 80,
    "old_nonempty": 20,
    "old_nonempty_to_corrected_empty": 0,
    "pose_identity_checks": 1_757,
    "production_empty": 1_214,
    "production_nonempty": 100,
}


class HistoricalRejudgmentError(ValueError):
    """Raised when pinned provenance or a rejudgment invariant is violated."""


@dataclass(frozen=True)
class VerifiedPlacement:
    instance_id: str
    facility_type: str
    operation_type: str
    is_mandatory: bool
    pose_idx: int
    pose: Mapping[str, Any]


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _path_provenance(path: Path) -> dict[str, str | None]:
    resolved = path.resolve(strict=True)
    try:
        project_relative = resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        project_relative = None
    return {
        "absolute_path": str(resolved),
        "project_relative_path": project_relative,
    }


def _git_stdout(args: Sequence[str], *, binary: bool = False) -> str | bytes:
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").rstrip("\n")


def _git_revision_snapshot() -> dict[str, Any]:
    status_text = str(
        _git_stdout(
            ["status", "--porcelain=v1", "--untracked-files=normal"],
        )
    )
    tracked_diff = _git_stdout(
        ["diff", "--binary", "--no-ext-diff", "HEAD", "--"],
        binary=True,
    )
    assert isinstance(tracked_diff, bytes)
    return {
        "branch": str(_git_stdout(["branch", "--show-current"])),
        "dirty": bool(status_text),
        "head": str(_git_stdout(["rev-parse", "HEAD"])),
        "status_porcelain_v1": status_text.splitlines(),
        "tracked_diff_sha256": _sha256(tracked_diff),
    }


def _source_provenance() -> dict[str, dict[str, str | None]]:
    source_paths = {
        "harness": Path(__file__).resolve(),
        "port_binding": PROJECT_ROOT / "src/models/port_binding.py",
        "routing_binding_context": (
            PROJECT_ROOT / "src/models/routing_binding_context.py"
        ),
    }
    result: dict[str, dict[str, str | None]] = {}
    for name, path in source_paths.items():
        item = _path_provenance(path)
        item["sha256"] = _sha256(path.read_bytes())
        result[name] = item
    return result


def _historical_front_source_audit() -> dict[str, Any]:
    raw_source = _git_stdout(
        ["show", f"{HISTORICAL_FRONT_SOURCE_REVISION}:{HISTORICAL_FRONT_SOURCE_PATH}"],
        binary=True,
    )
    assert isinstance(raw_source, bytes)
    actual_sha256 = _sha256(raw_source)
    if actual_sha256 != HISTORICAL_FRONT_SOURCE_SHA256:
        raise HistoricalRejudgmentError(
            "historical front source drift: expected "
            f"{HISTORICAL_FRONT_SOURCE_SHA256}, observed {actual_sha256}"
        )
    return {
        "behavior_confirmed_from_source": {
            "front_coordinate": "stored (x,y) plus literal direction delta",
            "self_occupied_cell_exemption": True,
            "unknown_direction_fallback_delta": [0, 0],
        },
        "git_revision": HISTORICAL_FRONT_SOURCE_REVISION,
        "path": HISTORICAL_FRONT_SOURCE_PATH,
        "sha256": actual_sha256,
    }


def _strict_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HistoricalRejudgmentError(f"{label} must be an integer")
    return value


def _xy(value: Any, *, label: str) -> tuple[int, int]:
    if not isinstance(value, Mapping):
        raise HistoricalRejudgmentError(f"{label} must be an object")
    try:
        x_raw = value["x"]
        y_raw = value["y"]
    except KeyError as exc:
        raise HistoricalRejudgmentError(f"{label} must define x and y") from exc
    return (
        _strict_int(x_raw, label=f"{label}.x"),
        _strict_int(y_raw, label=f"{label}.y"),
    )


def _cell(value: Any, *, label: str) -> tuple[int, int]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 2
    ):
        raise HistoricalRejudgmentError(f"{label} must be [x, y]")
    return (
        _strict_int(value[0], label=f"{label}[0]"),
        _strict_int(value[1], label=f"{label}[1]"),
    )


def _load_pinned_json(
    path: Path,
    *,
    expected_sha256: str,
    label: str,
) -> tuple[Any, str]:
    if not path.is_file():
        raise HistoricalRejudgmentError(f"{label} is not a file: {path}")
    raw = path.read_bytes()
    actual_sha256 = _sha256(raw)
    if actual_sha256 != expected_sha256:
        raise HistoricalRejudgmentError(
            f"{label} SHA-256 mismatch: expected {expected_sha256}, "
            f"observed {actual_sha256}"
        )
    try:
        return json.loads(raw.decode("utf-8")), actual_sha256
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalRejudgmentError(f"{label} is not valid UTF-8 JSON") from exc


def _extract_pools(
    candidate_payload: Any,
) -> dict[str, list[Mapping[str, Any]]]:
    if not isinstance(candidate_payload, Mapping):
        raise HistoricalRejudgmentError("candidate payload must be an object")
    raw_pools = candidate_payload.get("facility_pools")
    if not isinstance(raw_pools, Mapping):
        raise HistoricalRejudgmentError("candidate payload has no facility_pools object")

    pools: dict[str, list[Mapping[str, Any]]] = {}
    for facility_type, raw_pool in raw_pools.items():
        if not isinstance(raw_pool, list) or not all(
            isinstance(pose, Mapping) for pose in raw_pool
        ):
            raise HistoricalRejudgmentError(
                f"candidate pool {facility_type!r} must be a list of objects"
            )
        pools[str(facility_type)] = list(raw_pool)

    pose_count = sum(len(pool) for pool in pools.values())
    if pose_count != OLD_CANDIDATE_POSE_COUNT:
        raise HistoricalRejudgmentError(
            f"old candidate pose count drifted: expected "
            f"{OLD_CANDIDATE_POSE_COUNT}, observed {pose_count}"
        )
    return pools


def _verify_layout_pose_identity(
    layout_payload: Any,
    pools: Mapping[str, list[Mapping[str, Any]]],
) -> tuple[list[VerifiedPlacement], int]:
    """Resolve every facility entry only after pose_id and anchor agree."""

    if not isinstance(layout_payload, Mapping):
        raise HistoricalRejudgmentError("layout payload must be an object")

    verified: list[VerifiedPlacement] = []
    non_facility_markers = 0
    for outer_instance_id, raw_entry in sorted(
        layout_payload.items(), key=lambda item: str(item[0])
    ):
        instance_id = str(outer_instance_id)
        if not isinstance(raw_entry, Mapping):
            raise HistoricalRejudgmentError(
                f"layout entry {instance_id!r} must be an object"
            )
        if str(raw_entry.get("instance_id", "")) != instance_id:
            raise HistoricalRejudgmentError(
                f"layout entry key/instance_id mismatch for {instance_id!r}"
            )

        facility_type = str(raw_entry.get("facility_type", ""))
        if facility_type == "ghost_rect":
            if instance_id != "ghost_pick":
                raise HistoricalRejudgmentError(
                    f"unexpected ghost_rect entry {instance_id!r}"
                )
            non_facility_markers += 1
            continue

        pool = pools.get(facility_type)
        if pool is None:
            raise HistoricalRejudgmentError(
                f"{instance_id}: unknown facility pool {facility_type!r}"
            )
        pose_idx = _strict_int(
            raw_entry.get("pose_idx"), label=f"{instance_id}.pose_idx"
        )
        if not 0 <= pose_idx < len(pool):
            raise HistoricalRejudgmentError(
                f"{instance_id}: pose_idx {pose_idx} outside "
                f"{facility_type!r} pool of size {len(pool)}"
            )
        pose = pool[pose_idx]

        layout_pose_id = str(raw_entry.get("pose_id", ""))
        pool_pose_id = str(pose.get("pose_id", ""))
        if not layout_pose_id or layout_pose_id != pool_pose_id:
            raise HistoricalRejudgmentError(
                f"{instance_id}: pose_idx {pose_idx} resolves to pose_id "
                f"{pool_pose_id!r}, not layout pose_id {layout_pose_id!r}"
            )
        layout_anchor = _xy(
            raw_entry.get("anchor"), label=f"{instance_id}.layout_anchor"
        )
        pool_anchor = _xy(pose.get("anchor"), label=f"{instance_id}.pool_anchor")
        if layout_anchor != pool_anchor:
            raise HistoricalRejudgmentError(
                f"{instance_id}: pose_idx {pose_idx} resolves to anchor "
                f"{pool_anchor}, not layout anchor {layout_anchor}"
            )

        mandatory_raw = raw_entry.get("is_mandatory")
        if not isinstance(mandatory_raw, bool):
            raise HistoricalRejudgmentError(
                f"{instance_id}.is_mandatory must be a boolean"
            )
        operation_type = str(raw_entry.get("operation_type", ""))
        if not operation_type:
            raise HistoricalRejudgmentError(
                f"{instance_id}.operation_type must be non-empty"
            )
        verified.append(
            VerifiedPlacement(
                instance_id=instance_id,
                facility_type=facility_type,
                operation_type=operation_type,
                is_mandatory=mandatory_raw,
                pose_idx=pose_idx,
                pose=pose,
            )
        )

    if non_facility_markers != 1:
        raise HistoricalRejudgmentError(
            f"expected exactly one ghost_pick marker, observed {non_facility_markers}"
        )
    return verified, non_facility_markers


def _independent_body_occupancy(
    placements: Sequence[VerifiedPlacement],
) -> tuple[frozenset[tuple[int, int]], int]:
    owners_by_cell: dict[tuple[int, int], set[str]] = defaultdict(set)
    for placement in placements:
        raw_cells = placement.pose.get("occupied_cells")
        if not isinstance(raw_cells, list) or not raw_cells:
            raise HistoricalRejudgmentError(
                f"{placement.instance_id}.occupied_cells must be a non-empty list"
            )
        for index, raw_cell in enumerate(raw_cells):
            cell = _cell(
                raw_cell,
                label=f"{placement.instance_id}.occupied_cells[{index}]",
            )
            if not (0 <= cell[0] < GRID_WIDTH and 0 <= cell[1] < GRID_HEIGHT):
                raise HistoricalRejudgmentError(
                    f"{placement.instance_id}: body cell {cell} is out of grid"
                )
            owners_by_cell[cell].add(placement.instance_id)
    overlap_count = sum(1 for owners in owners_by_cell.values() if len(owners) > 1)
    return frozenset(owners_by_cell), overlap_count


def _port_list(pose: Mapping[str, Any], field_name: str) -> list[Mapping[str, Any]]:
    raw_ports = pose.get(field_name)
    if not isinstance(raw_ports, list) or not all(
        isinstance(port, Mapping) for port in raw_ports
    ):
        raise HistoricalRejudgmentError(f"{field_name} must be a list of objects")
    return list(raw_ports)


def _independent_front_is_free(
    port: Mapping[str, Any],
    occupied_cells: frozenset[tuple[int, int]],
) -> bool:
    """Literal independent rule: stored (x, y) is the front cell."""

    x = _strict_int(port.get("x"), label="port.x")
    y = _strict_int(port.get("y"), label="port.y")
    return (
        0 <= x < GRID_WIDTH
        and 0 <= y < GRID_HEIGHT
        and (x, y) not in occupied_cells
    )


def _independent_domain_is_empty(
    operation_type: str,
    pose: Mapping[str, Any],
    occupied_cells: frozenset[tuple[int, int]],
) -> tuple[bool, dict[str, int]]:
    required_inputs, visible_outputs = routing_visible_port_demands(
        operation_type, PINNED_RFSC
    )
    free_inputs = sum(
        _independent_front_is_free(port, occupied_cells)
        for port in _port_list(pose, "input_port_cells")
    )
    free_outputs = sum(
        _independent_front_is_free(port, occupied_cells)
        for port in _port_list(pose, "output_port_cells")
    )
    return (
        free_inputs < required_inputs or free_outputs < visible_outputs,
        {
            "free_inputs": free_inputs,
            "free_outputs": free_outputs,
            "required_inputs": required_inputs,
            "visible_outputs": visible_outputs,
        },
    )


def _historical_plus_delta_front_is_free(
    port: Mapping[str, Any],
    context: RoutingBindingContext,
    owner_instance_id: str,
) -> bool:
    """Reconstruct the incident-era front rule for comparison only."""

    x = _strict_int(port.get("x"), label="port.x")
    y = _strict_int(port.get("y"), label="port.y")
    direction = str(port.get("dir", ""))
    dx, dy = HISTORICAL_DIR_DELTA.get(direction, (0, 0))
    front_cell = (x + dx, y + dy)
    if not (
        0 <= front_cell[0] < context.grid_width
        and 0 <= front_cell[1] < context.grid_height
    ):
        return False
    if front_cell not in context.occupied_cells:
        return True
    return context.occupied_owner_by_cell.get(front_cell) == owner_instance_id


def _historical_plus_delta_domain_is_empty(
    operation_type: str,
    pose: Mapping[str, Any],
    context: RoutingBindingContext,
    owner_instance_id: str,
) -> bool:
    """Replay historical front filtering without treating it as an oracle."""

    raw_patterns, _cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
        operation_type, pose
    )
    for pattern in raw_patterns:
        visible_ports = list(pattern.get("input_ports", []))
        visible_ports.extend(
            port
            for port in pattern.get("output_ports", [])
            if is_routing_visible_output_commodity(
                port["commodity"], PINNED_RFSC
            )
        )
        if all(
            _historical_plus_delta_front_is_free(
                port, context, owner_instance_id
            )
            for port in visible_ports
        ):
            return False
    return True


def _production_domain_is_empty(
    operation_type: str,
    pose: Mapping[str, Any],
    context: RoutingBindingContext,
    owner_instance_id: str,
) -> bool:
    raw_patterns, _cache_hit = enumerate_pose_level_port_bindings_with_cache_info(
        operation_type, pose
    )
    for pattern in raw_patterns:
        visible_ports = list(pattern.get("input_ports", []))
        visible_ports.extend(
            port
            for port in pattern.get("output_ports", [])
            if is_routing_visible_output_commodity(
                port["commodity"], PINNED_RFSC
            )
        )
        if all(
            (
                status := port_front_status(port, context, owner_instance_id)
            ).in_grid
            and status.is_free
            for port in visible_ports
        ):
            return False
    return True


def _rejudge_layout(
    *,
    filename: str,
    layout_path: Path,
    layout_sha256: str,
    layout_payload: Any,
    pools: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any]:
    placements, marker_count = _verify_layout_pose_identity(layout_payload, pools)
    occupied_cells, overlap_count = _independent_body_occupancy(placements)

    assert isinstance(layout_payload, Mapping)
    production_context = build_routing_binding_context(
        layout_payload,
        pools,
        GRID_WIDTH,
        GRID_HEIGHT,
    )
    if production_context.occupied_cells != occupied_cells:
        raise HistoricalRejudgmentError(
            f"{filename}: production and independent body occupancy disagree"
        )

    checked = 0
    production_empty = 0
    oracle_empty = 0
    old_empty = 0
    old_empty_to_corrected_nonempty = 0
    old_nonempty_to_corrected_empty = 0
    mismatches: list[dict[str, Any]] = []
    operation_counts: Counter[str] = Counter()
    for placement in placements:
        if not placement.is_mandatory:
            continue
        if not supports_exact_pose_level_binding(placement.operation_type):
            continue

        checked += 1
        operation_counts[placement.operation_type] += 1
        actual_is_empty = _production_domain_is_empty(
            placement.operation_type,
            placement.pose,
            production_context,
            placement.instance_id,
        )
        oracle_is_empty, oracle_detail = _independent_domain_is_empty(
            placement.operation_type,
            placement.pose,
            occupied_cells,
        )
        old_is_empty = _historical_plus_delta_domain_is_empty(
            placement.operation_type,
            placement.pose,
            production_context,
            placement.instance_id,
        )
        production_empty += int(actual_is_empty)
        oracle_empty += int(oracle_is_empty)
        old_empty += int(old_is_empty)
        old_empty_to_corrected_nonempty += int(
            old_is_empty and not actual_is_empty
        )
        old_nonempty_to_corrected_empty += int(
            not old_is_empty and actual_is_empty
        )
        if actual_is_empty != oracle_is_empty:
            mismatches.append(
                {
                    "instance_id": placement.instance_id,
                    "operation_type": placement.operation_type,
                    "oracle": oracle_detail,
                    "oracle_is_empty": oracle_is_empty,
                    "production_is_empty": actual_is_empty,
                }
            )

    if mismatches:
        raise HistoricalRejudgmentError(
            f"{filename}: production/oracle mismatches: "
            f"{json.dumps(mismatches, ensure_ascii=False, sort_keys=True)}"
        )

    observed_baseline = {
        "checked": checked,
        "empty": production_empty,
        "identity_checks": len(placements),
        "nonempty": checked - production_empty,
        "old_empty": old_empty,
        "old_empty_to_corrected_nonempty": old_empty_to_corrected_nonempty,
        "old_nonempty": checked - old_empty,
        "old_nonempty_to_corrected_empty": old_nonempty_to_corrected_empty,
    }
    expected_baseline = EXPECTED_RECONSTRUCTED_BASELINE[filename]
    if observed_baseline != expected_baseline:
        raise HistoricalRejudgmentError(
            f"{filename}: reconstructed baseline drift: expected "
            f"{expected_baseline}, observed {observed_baseline}"
        )
    if oracle_empty != production_empty:
        raise HistoricalRejudgmentError(
            f"{filename}: aggregate production/oracle counts disagree"
        )

    return {
        "body_occupancy": {
            "occupied_cells": len(occupied_cells),
            "overlap_cells": overlap_count,
        },
        "eligible_mandatory_owners_checked": checked,
        "filename": filename,
        "independent_stored_xy_oracle": {
            "empty": oracle_empty,
            "nonempty": checked - oracle_empty,
        },
        "historical_plus_delta_comparison_arm": {
            "old_empty": old_empty,
            "old_empty_to_corrected_nonempty": old_empty_to_corrected_nonempty,
            "old_nonempty": checked - old_empty,
            "old_nonempty_to_corrected_empty": old_nonempty_to_corrected_empty,
            "role": "comparison_only_not_correctness_oracle",
        },
        "mismatch_count": 0,
        "non_facility_markers_skipped": marker_count,
        "operation_counts": dict(sorted(operation_counts.items())),
        "path": _path_provenance(layout_path),
        "pose_identity_checks": len(placements),
        "production_corrected_front_arm": {
            "empty": production_empty,
            "nonempty": checked - production_empty,
        },
        "sha256": layout_sha256,
    }


def run_rejudgment(
    candidate_path: Path,
    layouts_dir: Path,
    *,
    invocation_argv: Sequence[str] = (),
) -> dict[str, Any]:
    if not layouts_dir.is_dir():
        raise HistoricalRejudgmentError(
            f"layouts directory does not exist: {layouts_dir}"
        )
    observed_names = sorted(
        path.name for path in layouts_dir.glob("layout_*.json") if path.is_file()
    )
    expected_names = sorted(PINNED_LAYOUT_SHA256)
    if observed_names != expected_names:
        raise HistoricalRejudgmentError(
            f"layout corpus mismatch: expected {expected_names}, "
            f"observed {observed_names}"
        )

    candidate_payload, candidate_sha256 = _load_pinned_json(
        candidate_path,
        expected_sha256=OLD_CANDIDATE_SHA256,
        label="old candidate pool",
    )
    pools = _extract_pools(candidate_payload)
    clear_pose_level_binding_domain_cache()

    layouts: list[dict[str, Any]] = []
    for filename, expected_sha256 in PINNED_LAYOUT_SHA256.items():
        layout_payload, layout_sha256 = _load_pinned_json(
            layouts_dir / filename,
            expected_sha256=expected_sha256,
            label=filename,
        )
        layouts.append(
            _rejudge_layout(
                filename=filename,
                layout_path=layouts_dir / filename,
                layout_sha256=layout_sha256,
                layout_payload=layout_payload,
                pools=pools,
            )
        )

    totals = {
        "eligible_mandatory_owners_checked": sum(
            item["eligible_mandatory_owners_checked"] for item in layouts
        ),
        "independent_empty": sum(
            item["independent_stored_xy_oracle"]["empty"] for item in layouts
        ),
        "independent_nonempty": sum(
            item["independent_stored_xy_oracle"]["nonempty"] for item in layouts
        ),
        "mismatches": sum(item["mismatch_count"] for item in layouts),
        "old_empty": sum(
            item["historical_plus_delta_comparison_arm"]["old_empty"]
            for item in layouts
        ),
        "old_empty_to_corrected_nonempty": sum(
            item["historical_plus_delta_comparison_arm"][
                "old_empty_to_corrected_nonempty"
            ]
            for item in layouts
        ),
        "old_nonempty": sum(
            item["historical_plus_delta_comparison_arm"]["old_nonempty"]
            for item in layouts
        ),
        "old_nonempty_to_corrected_empty": sum(
            item["historical_plus_delta_comparison_arm"][
                "old_nonempty_to_corrected_empty"
            ]
            for item in layouts
        ),
        "pose_identity_checks": sum(item["pose_identity_checks"] for item in layouts),
        "production_empty": sum(
            item["production_corrected_front_arm"]["empty"] for item in layouts
        ),
        "production_nonempty": sum(
            item["production_corrected_front_arm"]["nonempty"] for item in layouts
        ),
    }
    if totals != EXPECTED_TOTALS:
        raise HistoricalRejudgmentError(
            f"aggregate baseline drift: expected {EXPECTED_TOTALS}, observed {totals}"
        )

    return {
        "baseline_status": "reconstructed_new_baseline",
        "candidate_pool": {
            "filename": candidate_path.name,
            "path": _path_provenance(candidate_path),
            "pose_count": OLD_CANDIDATE_POSE_COUNT,
            "sha256": candidate_sha256,
        },
        "classification": "front_only_historical_rejudgment",
        "grid": {"height": GRID_HEIGHT, "width": GRID_WIDTH},
        "layouts": layouts,
        "limitations": [
            "Not a full historical or current PortBindingModel replay.",
            "Replays only layout-local mandatory exact-owner front filtering.",
            "Uses current production binding enumeration and demand SSOT with the old RFSC pinned explicitly.",
            "The historical plus-delta arm is comparison-only, not a correctness oracle.",
            "The historical comparison reconstructs only incident-era front filtering and self-occupied-cell exemption; it is not a byte-for-byte old-model replay.",
            "old_empty_to_corrected_nonempty records a front-domain transition on this pinned corpus, not placement, routing, or certified feasibility.",
            "Does not rerun placement, master optimization, routing, or certification.",
        ],
        "method": {
            "historical_comparison_arm": {
                "direction_delta": {
                    direction: list(delta)
                    for direction, delta in sorted(HISTORICAL_DIR_DELTA.items())
                },
                "front_rule": "stored port (x,y) plus literal direction delta",
                "role": "comparison_only_not_correctness_oracle",
                "self_occupied_cell_exemption": True,
                "source_audit": _historical_front_source_audit(),
                "unknown_direction_fallback_delta": [0, 0],
            },
            "independent_oracle": (
                "stored port (x,y) identity plus independently rebuilt selected "
                "facility-body occupancy, compared by free-cell demand counts"
            ),
            "pose_identity_gate": "pose_idx resolves to exact layout pose_id and anchor",
            "production_arm": (
                "current enumerate_pose_level_port_bindings_with_cache_info plus "
                "corrected port_front_status"
            ),
        },
        "result_label": RESULT_LABEL,
        "routing_free_sink_commodities": sorted(PINNED_RFSC),
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "invocation": {
                "argv": list(invocation_argv),
                "cwd": str(Path.cwd().resolve()),
                "python_executable": str(Path(sys.executable).resolve()),
            },
            "revision": _git_revision_snapshot(),
            "sources": _source_provenance(),
        },
        "totals": totals,
    }


def deterministic_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def write_json_exclusive(output_path: Path, payload: Mapping[str, Any]) -> str:
    """Write deterministic UTF-8 JSON once; an existing path is never replaced."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw = deterministic_json(payload).encode("utf-8")
    with output_path.open("xb") as handle:
        handle.write(raw)
    return _sha256(raw)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        required=True,
        type=Path,
        help="Path to the pinned old candidate_placements.json.",
    )
    parser.add_argument(
        "--layouts-dir",
        required=True,
        type=Path,
        help="Directory containing exactly the six pinned historical layouts.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New result path; existing paths are refused.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    invocation_argv = [
        str(Path(sys.executable).resolve()),
        *(
            list(sys.argv)
            if argv is None
            else [str(Path(__file__).resolve()), *list(argv)]
        ),
    ]
    if args.output.exists():
        parser.error(f"refusing to overwrite existing output: {args.output}")
    try:
        report = run_rejudgment(
            args.candidate,
            args.layouts_dir,
            invocation_argv=invocation_argv,
        )
        output_sha256 = write_json_exclusive(args.output, report)
    except (HistoricalRejudgmentError, OSError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": output_sha256,
                "totals": report["totals"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
