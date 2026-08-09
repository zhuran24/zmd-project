"""Independent identity-front audit for Batch 4 research artifacts.

This module deliberately imports only the Python standard library.  In
particular, it does not import production front helpers, direction-delta
tables, FCL/RAB helpers, or historical witness audit code.  The rule applied
here is literal: each selected pose's stored port ``(x, y)`` is the front cell.
Only selected facility *body* cells can block it; another port at the same
coordinate is not a blocker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CANDIDATE_POOL = PROJECT_ROOT / "data/preprocessed/candidate_placements.json"
DEFAULT_INSTANCES = PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json"

COUNT_KEYS = (
    "total_ports",
    "in_grid",
    "out_of_grid",
    "occupied_by_other_body",
    "self_body",
    "free_of_body",
)


class IndependentFrontAuditError(ValueError):
    """Raised when an audit input cannot be interpreted without guessing."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json_with_sha(path: Path) -> tuple[Any, str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), _sha256_bytes(raw)


def _normalize_sha256(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise IndependentFrontAuditError(f"{label}: expected 64 hexadecimal characters")
    return normalized


def _as_pose_index(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise IndependentFrontAuditError(f"{label}: boolean is not a pose index")
    try:
        pose_idx = int(value)
    except (TypeError, ValueError) as exc:
        raise IndependentFrontAuditError(f"{label}: invalid pose index {value!r}") from exc
    if pose_idx < 0:
        raise IndependentFrontAuditError(f"{label}: negative pose index {pose_idx}")
    return pose_idx


def _extract_pools(candidate_payload: Any) -> dict[str, list[Mapping[str, Any]]]:
    if not isinstance(candidate_payload, Mapping):
        raise IndependentFrontAuditError("candidate pool payload must be an object")
    raw_pools = candidate_payload.get("facility_pools", candidate_payload)
    if not isinstance(raw_pools, Mapping):
        raise IndependentFrontAuditError("candidate pool payload has no facility_pools object")

    pools: dict[str, list[Mapping[str, Any]]] = {}
    for facility_type, raw_pool in raw_pools.items():
        if not isinstance(raw_pool, list):
            raise IndependentFrontAuditError(
                f"candidate pool {facility_type!r} must be a list"
            )
        if not all(isinstance(pose, Mapping) for pose in raw_pool):
            raise IndependentFrontAuditError(
                f"candidate pool {facility_type!r} contains a non-object pose"
            )
        pools[str(facility_type)] = list(raw_pool)
    return pools


def _extract_instance_templates(instances_payload: Any) -> dict[str, str]:
    if instances_payload is None:
        return {}
    raw_instances = instances_payload
    if isinstance(instances_payload, Mapping):
        raw_instances = instances_payload.get("instances")
    if not isinstance(raw_instances, list):
        raise IndependentFrontAuditError("instances payload must be a list or {instances: [...]}")

    result: dict[str, str] = {}
    for index, raw_instance in enumerate(raw_instances):
        if not isinstance(raw_instance, Mapping):
            raise IndependentFrontAuditError(f"instances[{index}] must be an object")
        instance_id = str(raw_instance.get("instance_id", "")).strip()
        facility_type = str(raw_instance.get("facility_type", "")).strip()
        if not instance_id or not facility_type:
            raise IndependentFrontAuditError(
                f"instances[{index}] must define instance_id and facility_type"
            )
        if instance_id in result and result[instance_id] != facility_type:
            raise IndependentFrontAuditError(
                f"instance {instance_id!r} has conflicting facility types"
            )
        result[instance_id] = facility_type
    return result


def _extract_solution_mapping(solution_payload: Any) -> Mapping[str, Any]:
    if not isinstance(solution_payload, Mapping):
        raise IndependentFrontAuditError("solution payload must be an object")
    if "solution" in solution_payload:
        solution = solution_payload["solution"]
        if not isinstance(solution, Mapping):
            raise IndependentFrontAuditError("solution field must be an object")
        return solution
    return solution_payload


def _optional_identity_from_instance_id(instance_id: str) -> tuple[str, str] | None:
    parts = instance_id.split("::", 2)
    if len(parts) == 3 and parts[0] == "pose_optional" and parts[1] and parts[2]:
        return parts[1], parts[2]
    return None


def _normalize_pose_id(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IndependentFrontAuditError(f"{label}: pose_id must be a non-empty string")
    return value.strip()


def _normalize_anchor(value: Any, *, label: str) -> list[int]:
    if not isinstance(value, Mapping):
        raise IndependentFrontAuditError(f"{label}: anchor must be an object with x/y")
    try:
        raw_x = value["x"]
        raw_y = value["y"]
    except KeyError as exc:
        raise IndependentFrontAuditError(f"{label}: anchor must define x and y") from exc
    if type(raw_x) is not int or type(raw_y) is not int:
        raise IndependentFrontAuditError(f"{label}: anchor x/y must be integers")
    return [raw_x, raw_y]


def _normal_entry(
    instance_id: str,
    raw_entry: Any,
    instance_templates: Mapping[str, str],
) -> dict[str, Any]:
    expected_pose_id: str | None = None
    expected_anchor: list[int] | None = None
    if isinstance(raw_entry, Mapping):
        if "pose_idx" not in raw_entry:
            raise IndependentFrontAuditError(
                f"solution entry {instance_id!r} is missing pose_idx"
            )
        pose_idx = _as_pose_index(raw_entry["pose_idx"], label=instance_id)
        facility_type = str(raw_entry.get("facility_type", "")).strip()
        if "pose_id" in raw_entry:
            expected_pose_id = _normalize_pose_id(
                raw_entry["pose_id"], label=f"solution entry {instance_id!r}"
            )
        if "anchor" in raw_entry:
            expected_anchor = _normalize_anchor(
                raw_entry["anchor"], label=f"solution entry {instance_id!r}"
            )
    else:
        pose_idx = _as_pose_index(raw_entry, label=instance_id)
        facility_type = ""

    optional_identity = _optional_identity_from_instance_id(instance_id)
    optional_type = optional_identity[0] if optional_identity is not None else None
    optional_pose_id = optional_identity[1] if optional_identity is not None else None
    inferred_type = instance_templates.get(instance_id) or optional_type
    if optional_pose_id is not None:
        if expected_pose_id is not None and expected_pose_id != optional_pose_id:
            raise IndependentFrontAuditError(
                f"solution entry {instance_id!r} carries pose_id {expected_pose_id!r}, "
                f"but its optional-instance key says {optional_pose_id!r}"
            )
        expected_pose_id = optional_pose_id
    if facility_type and inferred_type and facility_type != inferred_type:
        raise IndependentFrontAuditError(
            f"solution entry {instance_id!r} says {facility_type!r}, "
            f"but canonical instances say {inferred_type!r}"
        )
    facility_type = facility_type or str(inferred_type or "")
    if not facility_type:
        raise IndependentFrontAuditError(
            f"solution entry {instance_id!r} has no resolvable facility_type"
        )
    return {
        "instance_id": instance_id,
        "facility_type": facility_type,
        "pose_idx": pose_idx,
        "expected_anchor": expected_anchor,
        "expected_pose_id": expected_pose_id,
    }


def _normalize_selected_poses(
    solution_payload: Any,
    instance_templates: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    solution = _extract_solution_mapping(solution_payload)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for instance_id_raw, raw_entry in sorted(solution.items(), key=lambda item: str(item[0])):
        instance_id = str(instance_id_raw)
        if instance_id == "__c1_active_poles__":
            if not isinstance(raw_entry, list):
                raise IndependentFrontAuditError("__c1_active_poles__ must be a list")
            for index, pole_entry in enumerate(raw_entry):
                if not isinstance(pole_entry, Mapping) or "pose_idx" not in pole_entry:
                    raise IndependentFrontAuditError(
                        f"__c1_active_poles__[{index}] must define pose_idx"
                    )
                selected.append(
                    {
                        "instance_id": f"__c1_active_pole__{index:03d}",
                        "facility_type": "power_pole",
                        "pose_idx": _as_pose_index(
                            pole_entry["pose_idx"],
                            label=f"__c1_active_poles__[{index}]",
                        ),
                        "expected_anchor": (
                            _normalize_anchor(
                                pole_entry["anchor"],
                                label=f"__c1_active_poles__[{index}]",
                            )
                            if "anchor" in pole_entry
                            else None
                        ),
                        "expected_pose_id": (
                            _normalize_pose_id(
                                pole_entry["pose_id"],
                                label=f"__c1_active_poles__[{index}]",
                            )
                            if "pose_id" in pole_entry
                            else None
                        ),
                    }
                )
            continue
        if instance_id == "ghost_pick" or instance_id.startswith("__"):
            skipped.append({"entry": instance_id, "reason": "non_facility_marker"})
            continue
        selected.append(_normal_entry(instance_id, raw_entry, instance_templates))

    selected.sort(key=lambda item: item["instance_id"])
    return selected, skipped


def _body_cell(raw_cell: Any, *, label: str) -> tuple[int, int]:
    if not isinstance(raw_cell, Sequence) or isinstance(raw_cell, (str, bytes)):
        raise IndependentFrontAuditError(f"{label}: body cell must be [x, y]")
    if len(raw_cell) != 2:
        raise IndependentFrontAuditError(f"{label}: body cell must have two coordinates")
    return int(raw_cell[0]), int(raw_cell[1])


def _selected_pose_records(
    pools: Mapping[str, list[Mapping[str, Any]]],
    selected: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in selected:
        instance_id = str(entry["instance_id"])
        facility_type = str(entry["facility_type"])
        pose_idx = int(entry["pose_idx"])
        pool = pools.get(facility_type)
        if pool is None:
            raise IndependentFrontAuditError(
                f"solution entry {instance_id!r} names unknown pool {facility_type!r}"
            )
        if pose_idx >= len(pool):
            raise IndependentFrontAuditError(
                f"solution entry {instance_id!r} pose_idx {pose_idx} is outside "
                f"pool {facility_type!r} (size {len(pool)})"
            )
        pose = pool[pose_idx]
        expected_pose_id = entry.get("expected_pose_id")
        expected_anchor = entry.get("expected_anchor")
        identity_fields: list[str] = []
        if expected_pose_id is not None:
            identity_fields.append("pose_id")
            actual_pose_id = pose.get("pose_id")
            if actual_pose_id != expected_pose_id:
                raise IndependentFrontAuditError(
                    f"solution entry {instance_id!r} carries pose_id {expected_pose_id!r}, "
                    f"but {facility_type}[{pose_idx}] has {actual_pose_id!r}"
                )
        if expected_anchor is not None:
            identity_fields.append("anchor")
            if "anchor" not in pose:
                raise IndependentFrontAuditError(
                    f"solution entry {instance_id!r} carries anchor {expected_anchor!r}, "
                    f"but {facility_type}[{pose_idx}] has no anchor"
                )
            actual_anchor = _normalize_anchor(
                pose["anchor"], label=f"candidate {facility_type}[{pose_idx}]"
            )
            if actual_anchor != expected_anchor:
                raise IndependentFrontAuditError(
                    f"solution entry {instance_id!r} carries anchor {expected_anchor!r}, "
                    f"but {facility_type}[{pose_idx}] has {actual_anchor!r}"
                )

        matching_indices: list[int] = []
        if identity_fields:
            for candidate_index, candidate_pose in enumerate(pool):
                if expected_pose_id is not None and candidate_pose.get("pose_id") != expected_pose_id:
                    continue
                if expected_anchor is not None:
                    if "anchor" not in candidate_pose:
                        continue
                    candidate_anchor = _normalize_anchor(
                        candidate_pose["anchor"],
                        label=f"candidate {facility_type}[{candidate_index}]",
                    )
                    if candidate_anchor != expected_anchor:
                        continue
                matching_indices.append(candidate_index)
        uniquely_identifies_pose = matching_indices == [pose_idx]
        body = {
            _body_cell(cell, label=f"{instance_id}.occupied_cells")
            for cell in (pose.get("occupied_cells") or [])
        }
        records.append(
            {
                "instance_id": instance_id,
                "facility_type": facility_type,
                "pose_idx": pose_idx,
                "pose_id": str(pose.get("pose_id", "")),
                "pose_identity": {
                    "carried_anchor": expected_anchor,
                    "carried_pose_id": expected_pose_id,
                    "fields_present": identity_fields,
                    "matching_pool_pose_count": len(matching_indices),
                    "uniquely_identifies_selected_pose": uniquely_identifies_pose,
                },
                "pose": pose,
                "body": body,
            }
        )
    return records


def _empty_counts() -> dict[str, int]:
    return {key: 0 for key in COUNT_KEYS}


def _audit_core(
    candidate_payload: Any,
    solution_payload: Any,
    instances_payload: Any = None,
    *,
    grid_width: int,
    grid_height: int,
) -> dict[str, Any]:
    if grid_width <= 0 or grid_height <= 0:
        raise IndependentFrontAuditError("grid dimensions must be positive")

    pools = _extract_pools(candidate_payload)
    instance_templates = _extract_instance_templates(instances_payload)
    selected, skipped = _normalize_selected_poses(solution_payload, instance_templates)
    records = _selected_pose_records(pools, selected)

    owners_by_body_cell: dict[tuple[int, int], set[str]] = defaultdict(set)
    for record in records:
        for cell in record["body"]:
            owners_by_body_cell[cell].add(record["instance_id"])

    per_instance: list[dict[str, Any]] = []
    totals = _empty_counts()
    for record in records:
        instance_id = record["instance_id"]
        counts = _empty_counts()
        ports: list[dict[str, Any]] = []
        for side, field_name in (
            ("input", "input_port_cells"),
            ("output", "output_port_cells"),
        ):
            raw_ports = record["pose"].get(field_name) or []
            if not isinstance(raw_ports, list):
                raise IndependentFrontAuditError(
                    f"{instance_id}.{field_name} must be a list"
                )
            for port_index, raw_port in enumerate(raw_ports):
                if not isinstance(raw_port, Mapping):
                    raise IndependentFrontAuditError(
                        f"{instance_id}.{field_name}[{port_index}] must be an object"
                    )
                try:
                    front_x = int(raw_port["x"])
                    front_y = int(raw_port["y"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise IndependentFrontAuditError(
                        f"{instance_id}.{field_name}[{port_index}] has invalid x/y"
                    ) from exc

                counts["total_ports"] += 1
                front_cell = (front_x, front_y)
                in_grid = 0 <= front_x < grid_width and 0 <= front_y < grid_height
                body_owners = sorted(owners_by_body_cell.get(front_cell, set())) if in_grid else []
                self_body = instance_id in body_owners
                other_owners = [owner for owner in body_owners if owner != instance_id]
                if in_grid:
                    counts["in_grid"] += 1
                    if self_body:
                        counts["self_body"] += 1
                    if other_owners:
                        counts["occupied_by_other_body"] += 1
                    if not body_owners:
                        counts["free_of_body"] += 1
                else:
                    counts["out_of_grid"] += 1

                if not in_grid:
                    classification = "out_of_grid"
                elif self_body and other_owners:
                    classification = "self_and_other_body"
                elif self_body:
                    classification = "self_body"
                elif other_owners:
                    classification = "occupied_by_other_body"
                else:
                    classification = "free_of_body"
                ports.append(
                    {
                        "body_owners": body_owners,
                        "classification": classification,
                        "direction": str(raw_port.get("dir", "")),
                        "front": [front_x, front_y],
                        "port_index": port_index,
                        "side": side,
                    }
                )

        for key in COUNT_KEYS:
            totals[key] += counts[key]
        per_instance.append(
            {
                "counts": counts,
                "facility_type": record["facility_type"],
                "instance_id": instance_id,
                "ports": ports,
                "pose_id": record["pose_id"],
                "pose_identity": record["pose_identity"],
                "pose_idx": record["pose_idx"],
            }
        )

    overlap_cells = sum(1 for owners in owners_by_body_cell.values() if len(owners) > 1)
    entries_with_identity = sum(bool(record["pose_identity"]["fields_present"]) for record in records)
    uniquely_verified_entries = sum(
        bool(record["pose_identity"]["uniquely_identifies_selected_pose"]) for record in records
    )
    identity_verifies_all = bool(records) and uniquely_verified_entries == len(records)
    return {
        "body_cell_count": len(owners_by_body_cell),
        "body_overlap_cell_count": overlap_cells,
        "grid": {"height": grid_height, "width": grid_width},
        "instances": per_instance,
        "pose_index_mapping": {
            "entries_with_identity": entries_with_identity,
            "selected_pose_count": len(records),
            "status": "verified_by_pose_identity" if identity_verifies_all else "unverified_index_mapping",
            "uniquely_verified_entries": uniquely_verified_entries,
            "unverified_entries": len(records) - uniquely_verified_entries,
        },
        "selected_pose_count": len(records),
        "skipped_entries": skipped,
        "totals": totals,
    }


def run_canaries() -> dict[str, Any]:
    """Run three tiny, literal-rule canaries without any production imports."""

    def pose(
        body: list[list[int]],
        *,
        input_ports: list[dict[str, Any]] | None = None,
        output_ports: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "occupied_cells": body,
            "input_port_cells": input_ports or [],
            "output_port_cells": output_ports or [],
        }

    cases: list[dict[str, Any]] = []

    first_blocked = _audit_core(
        {
            "facility_pools": {
                "maker": [pose([[0, 0]], output_ports=[{"x": 1, "y": 1, "dir": "E"}])],
                "blocker": [pose([[1, 1]])],
            }
        },
        {
            "solution": {
                "maker_001": {"facility_type": "maker", "pose_idx": 0},
                "blocker_001": {"facility_type": "blocker", "pose_idx": 0},
            }
        },
        grid_width=4,
        grid_height=4,
    )
    maker_counts = next(
        entry["counts"] for entry in first_blocked["instances"] if entry["instance_id"] == "maker_001"
    )
    cases.append(
        {
            "id": "first_cell_blocked_second_cell_free",
            "observed": maker_counts,
            "passed": maker_counts["occupied_by_other_body"] == 1
            and maker_counts["free_of_body"] == 0,
        }
    )

    second_blocked = _audit_core(
        {
            "facility_pools": {
                "maker": [pose([[0, 0]], output_ports=[{"x": 1, "y": 1, "dir": "E"}])],
                "blocker": [pose([[2, 1]])],
            }
        },
        {
            "solution": {
                "maker_001": {"facility_type": "maker", "pose_idx": 0},
                "blocker_001": {"facility_type": "blocker", "pose_idx": 0},
            }
        },
        grid_width=4,
        grid_height=4,
    )
    maker_counts = next(
        entry["counts"] for entry in second_blocked["instances"] if entry["instance_id"] == "maker_001"
    )
    cases.append(
        {
            "id": "first_cell_free_second_cell_blocked",
            "observed": maker_counts,
            "passed": maker_counts["occupied_by_other_body"] == 0
            and maker_counts["free_of_body"] == 1,
        }
    )

    shared_port = _audit_core(
        {
            "facility_pools": {
                "left": [pose([[0, 1]], output_ports=[{"x": 1, "y": 1, "dir": "E"}])],
                "right": [pose([[2, 1]], input_ports=[{"x": 1, "y": 1, "dir": "W"}])],
            }
        },
        {
            "solution": {
                "left_001": {"facility_type": "left", "pose_idx": 0},
                "right_001": {"facility_type": "right", "pose_idx": 0},
            }
        },
        grid_width=4,
        grid_height=4,
    )
    cases.append(
        {
            "id": "opposite_ports_share_middle_cell",
            "observed": shared_port["totals"],
            "passed": shared_port["totals"]["total_ports"] == 2
            and shared_port["totals"]["free_of_body"] == 2
            and shared_port["totals"]["occupied_by_other_body"] == 0,
        }
    )

    return {"all_passed": all(case["passed"] for case in cases), "cases": cases}


def audit_payloads(
    candidate_payload: Any,
    solution_payload: Any,
    instances_payload: Any = None,
    *,
    grid_width: int = 70,
    grid_height: int = 70,
) -> dict[str, Any]:
    report = _audit_core(
        candidate_payload,
        solution_payload,
        instances_payload,
        grid_width=grid_width,
        grid_height=grid_height,
    )
    report.update(
        {
            "canaries": run_canaries(),
            "schema_version": "independent_front_audit_v2",
            "semantics": {
                "blockers": "selected facility body cells only",
                "front_cell": "stored_port_xy_identity",
                "production_front_helpers_imported": False,
            },
        }
    )
    return report


def audit_files(
    candidate_pool_path: Path,
    solution_path: Path,
    instances_path: Path | None = None,
    *,
    grid_width: int = 70,
    grid_height: int = 70,
    expected_candidate_sha256: str | None = None,
) -> dict[str, Any]:
    candidate_payload, candidate_sha = _load_json_with_sha(candidate_pool_path)
    normalized_expected_sha: str | None = None
    if expected_candidate_sha256 is not None:
        normalized_expected_sha = _normalize_sha256(
            expected_candidate_sha256,
            label="--expected-candidate-sha256",
        )
        if candidate_sha != normalized_expected_sha:
            raise IndependentFrontAuditError(
                "candidate pool SHA-256 mismatch: "
                f"expected {normalized_expected_sha}, got {candidate_sha}"
            )
    solution_payload, solution_sha = _load_json_with_sha(solution_path)
    instances_payload: Any = None
    instance_sha: str | None = None
    if instances_path is not None:
        instances_payload, instance_sha = _load_json_with_sha(instances_path)

    report = audit_payloads(
        candidate_payload,
        solution_payload,
        instances_payload,
        grid_width=grid_width,
        grid_height=grid_height,
    )
    inputs: dict[str, Any] = {
        "candidate_pool": {
            "path": str(candidate_pool_path),
            "sha256": candidate_sha,
        },
        "solution": {"path": str(solution_path), "sha256": solution_sha},
    }
    if instances_path is not None:
        inputs["instances"] = {
            "path": str(instances_path),
            "sha256": instance_sha,
        }
    source_path = Path(__file__).resolve()
    inputs["auditor_source"] = {
        "path": str(source_path),
        "sha256": _sha256_bytes(source_path.read_bytes()),
    }
    report["inputs"] = inputs
    if normalized_expected_sha is not None:
        selected_pose_count = int(report["pose_index_mapping"]["selected_pose_count"])
        report["pose_index_mapping"].update(
            {
                "actual_candidate_sha256": candidate_sha,
                "entries_verified_by_candidate_sha256": selected_pose_count,
                "expected_candidate_sha256": normalized_expected_sha,
                "status": "verified_against_expected_candidate_sha256",
                "unverified_entries": 0,
            }
        )
    return report


def deterministic_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("solution", type=Path, help="raw solution mapping or wrapper with a solution field")
    parser.add_argument("--candidate-pool", type=Path, default=DEFAULT_CANDIDATE_POOL)
    parser.add_argument("--instances", type=Path, default=DEFAULT_INSTANCES)
    parser.add_argument("--grid-width", type=int, default=70)
    parser.add_argument("--grid-height", type=int, default=70)
    parser.add_argument(
        "--expected-candidate-sha256",
        default=None,
        help="require the candidate-pool bytes to match this SHA-256",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.output is not None:
        output_path = args.output.resolve()
        input_paths = {
            args.candidate_pool.resolve(),
            args.solution.resolve(),
            args.instances.resolve(),
        }
        if output_path in input_paths:
            parser.error("--output must not overwrite an input file")
        if args.output.exists():
            parser.error("--output already exists; refusing to overwrite it")
    try:
        report = audit_files(
            args.candidate_pool,
            args.solution,
            args.instances,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            expected_candidate_sha256=args.expected_candidate_sha256,
        )
    except (IndependentFrontAuditError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    rendered = deterministic_json(report)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as output_file:
                output_file.write(rendered)
        except FileExistsError:
            parser.error("--output already exists; refusing to overwrite it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
