#!/usr/bin/env python3
"""Research-only exporter: band22 witness layout -> IndustrialPlanner blueprint.

Reads two read-only inputs, assembles the canonical ``optimal_blueprint.json``
shape in memory, and hands it to the repository's own one-way exporter
(``src.adapters.industrial_planner.export_blueprint``).  Nothing under
``data/`` is written; the canonical intermediate is written to the caller's
artifact directory only.

Inputs
  1. registration_placement_solution.json -- 291 official poses
     (266 mandatory facilities + 25 power poles), each carrying the
     ``pose_idx`` into the frozen candidate pool.
  2. band22_repaired_design_witness_not_checker_schema.json -- the design
     witness that supplies the 628 active ports and the 1,143 routing cells.

Geometry authority is the frozen pool (``data/preprocessed/candidate_placements.json``,
sha256 f05b1291...), not the witness: every facility footprint and port cell is
read from ``pose["occupied_cells"]`` / ``pose["*_port_cells"]``.  The witness is
used only for the things the pool cannot carry -- which ports are active, their
commodities, and the routing network.

Every mapping decision is fail-closed: an unresolvable facility type, routing
kind, port kind or footprint mismatch raises instead of being dropped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.adapters.industrial_planner.blueprint_validator import (  # noqa: E402
    load_static_registries,
    validate_industrial_planner_blueprint,
)
from src.adapters.industrial_planner.export_blueprint import (  # noqa: E402
    build_industrial_planner_export_bundle,
)
from src.adapters.industrial_planner.mapping_registry import (  # noqa: E402
    DEFAULT_BASE_ID,
    is_liquid_like_commodity,
)

DEFAULT_REGISTRATION = (
    REPO_ROOT
    / ".artifacts/w0_fixrerun_20260804/band22_alignment/registration_placement_solution.json"
)
DEFAULT_WITNESS = (
    REPO_ROOT
    / "docs/research/cleanroom_rederivation_20260718/27_band22_witness_delivery_20260804"
    / "band22_repaired_design_witness_not_checker_schema.json"
)
FROZEN_POOL = REPO_ROOT / "data/preprocessed/candidate_placements.json"
FROZEN_POOL_SHA256 = "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"

GRID_SIZE = 70
HOLE_X_RANGE = (1, 6)
HOLE_Y_RANGE = (51, 57)

# Witness routing kind -> canonical routing component type.  ``straight`` and
# ``turn`` are both plain belts in the canonical schema; the exporter recovers
# the straight/turn distinction from flow_in|flow_out.
ROUTING_KIND_TO_CANONICAL_TYPE = {
    "straight": "belt",
    "turn": "belt",
    "merger": "merger",
    "splitter": "splitter",
}

# The witness carries no per-cell commodity.  The only routing decision the
# exporter derives from a commodity is solid (belt family) vs liquid-like (pipe
# family); ``assert_all_commodities_are_solid`` machine-checks that every
# commodity in this design is solid, so this sentinel cannot change any emitted
# device.  It is the canonical schema's own unknown-commodity marker.
ROUTING_COMMODITY_SENTINEL = "[TBD]"

# IndustrialPlanner device footprint expected for each canonical facility type,
# as (width, height) BEFORE rotation, plus the exporter's fixed rotation offset.
# Used only to fail loudly if the exported footprint ever stops matching the
# frozen pose footprint.
EXPECTED_TARGET_FOOTPRINT = {
    "manufacturing_3x3": ((3, 3), 0),
    "manufacturing_5x5": ((5, 5), 0),
    "manufacturing_6x4": ((6, 4), 0),
    "power_pole": ((2, 2), 0),
    "boundary_storage_port": ((3, 1), 90),
    "protocol_core": (None, 0),  # intentionally not emitted as a device
}


# Canonical direction names and IndustrialPlanner edge names use opposite y
# axes.  Canonical/witness is y-up (``src/models/routing_subproblem.py:27``
# DIR_DELTA N=(0,+1)); the IndustrialPlanner side is y-down -- the validator's
# ``_boundary_key`` pairs cell (x,y)'s N edge with cell (x,y-1)'s S edge.
# Coordinates are passed through unchanged (that is what keeps the boundary
# ports adjacent to the base's foundation bus band), so the direction NAMES are
# what must flip.
CANONICAL_DIR_TO_IP_EDGE = {"N": "S", "S": "N", "E": "E", "W": "W"}

# Candidate target devices per canonical routing type, in preference order.
# The flow-direction correction pass picks the (typeId, rotation) whose rotated
# ports reproduce the design's flow; the stock exporter picks a rotation from
# the direction name alone, which loses flow orientation.
ROUTING_DEVICE_CANDIDATES = {
    "belt": ("belt_straight_1x1", "belt_turn_ccw_1x1", "belt_turn_cw_1x1"),
    "merger": ("item_log_converger",),
    "splitter": ("item_log_splitter",),
}
EDGE_ORDER = ("N", "E", "S", "W")


class ConversionError(RuntimeError):
    """Raised for any mapping gap; never swallowed, never silently skipped."""


def rotate_edge(edge: str, rotation: int) -> str:
    """Mirror of ``blueprint_validator._rotate_edge``."""
    return EDGE_ORDER[(EDGE_ORDER.index(edge) + rotation // 90) % 4]


@dataclass
class ConversionStats:
    facility_count: int = 0
    active_port_count: int = 0
    routing_cell_count: int = 0
    body_cells: int = 0
    routing_kind_counts: dict[str, int] = field(default_factory=dict)
    facility_type_counts: dict[str, int] = field(default_factory=dict)
    routing_cells_in_hole: int = 0
    notes: list[str] = field(default_factory=list)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def rotated_size(size: tuple[int, int], rotation: int) -> tuple[int, int]:
    width, height = size
    return (height, width) if rotation % 360 in (90, 270) else (width, height)


def assert_all_commodities_are_solid(witness: dict[str, Any]) -> list[str]:
    """Fail closed if any witness commodity would route into the pipe family."""
    commodities = sorted({str(port["commodity"]) for port in witness["active_ports"]})
    liquid = [name for name in commodities if is_liquid_like_commodity(name)]
    if liquid:
        raise ConversionError(
            "witness carries liquid-like commodities, so the routing commodity "
            f"sentinel would change device selection: {liquid}"
        )
    return commodities


def collect_witness_active_ports(witness: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group the witness's 628 active ports by owning instance."""
    by_instance: dict[str, list[dict[str, Any]]] = {}
    for port in witness["active_ports"]:
        kind = str(port["kind"])
        if kind not in ("input", "output"):
            raise ConversionError(f"unmapped active-port kind {kind!r} on {port['instance_id']!r}")
        direction = str(port["direction"])
        if direction not in ("N", "S", "E", "W"):
            raise ConversionError(f"unmapped port direction {direction!r} on {port['instance_id']!r}")
        front = port["front"]
        by_instance.setdefault(str(port["instance_id"]), []).append(
            {
                "type": kind,
                "x": int(front[0]),
                "y": int(front[1]),
                "dir": direction,
                "commodity": str(port["commodity"]),
            }
        )
    return by_instance


def build_facilities(
    registration: dict[str, Any],
    pool: dict[str, Any],
    ports_by_instance: dict[str, list[dict[str, Any]]],
    stats: ConversionStats,
    offset: tuple[int, int],
) -> list[dict[str, Any]]:
    facilities: list[dict[str, Any]] = []
    occupied: dict[tuple[int, int], str] = {}
    off_x, off_y = offset

    for instance_id, entry in sorted(registration.items()):
        facility_type = str(entry["facility_type"])
        if facility_type not in EXPECTED_TARGET_FOOTPRINT:
            raise ConversionError(
                f"facility {instance_id!r} has facility_type {facility_type!r} with no "
                "IndustrialPlanner mapping decision on record"
            )
        poses = pool.get(facility_type)
        if poses is None:
            raise ConversionError(f"frozen pool has no template {facility_type!r}")
        pose = poses[int(entry["pose_idx"])]
        if str(pose["pose_id"]) != str(entry["pose_id"]):
            raise ConversionError(
                f"pose_idx drift for {instance_id!r}: pool says {pose['pose_id']!r}, "
                f"registration says {entry['pose_id']!r}"
            )
        if pose["anchor"] != entry["anchor"]:
            raise ConversionError(
                f"anchor drift for {instance_id!r}: pool {pose['anchor']} vs registration {entry['anchor']}"
            )

        cells = [(int(cell[0]), int(cell[1])) for cell in pose["occupied_cells"]]
        min_x = min(cell[0] for cell in cells)
        min_y = min(cell[1] for cell in cells)
        width = max(cell[0] for cell in cells) - min_x + 1
        height = max(cell[1] for cell in cells) - min_y + 1
        if len(cells) != width * height:
            raise ConversionError(f"{instance_id!r} pose footprint is not a solid rectangle")
        if (min_x, min_y) != (int(entry["anchor"]["x"]), int(entry["anchor"]["y"])):
            raise ConversionError(f"{instance_id!r} anchor is not the min corner of its footprint")

        orientation = int(pose["pose_params"]["orientation"])
        expected_size, rotation_offset = EXPECTED_TARGET_FOOTPRINT[facility_type]
        if expected_size is not None:
            rotation = (orientation % 4) * 90 + rotation_offset
            exported = rotated_size(expected_size, rotation)
            if exported != (width, height):
                raise ConversionError(
                    f"{instance_id!r} ({facility_type}) would export as a "
                    f"{exported[0]}x{exported[1]} device but occupies {width}x{height} cells"
                )

        for cell in cells:
            moved = (cell[0] + off_x, cell[1] + off_y)
            if moved in occupied:
                raise ConversionError(
                    f"body overlap at {moved} between {occupied[moved]!r} and {instance_id!r}"
                )
            occupied[moved] = instance_id

        active_ports = [
            {**port, "x": port["x"] + off_x, "y": port["y"] + off_y}
            for port in ports_by_instance.get(instance_id, [])
        ]
        facilities.append(
            {
                "instance_id": instance_id,
                "facility_type": facility_type,
                "anchor": {"x": min_x + off_x, "y": min_y + off_y},
                "orientation": orientation,
                "port_mode": str(pose["pose_params"]["port_mode"]),
                "active_ports": active_ports,
            }
        )
        stats.facility_type_counts[facility_type] = stats.facility_type_counts.get(facility_type, 0) + 1
        stats.active_port_count += len(active_ports)

    stats.facility_count = len(facilities)
    stats.body_cells = len(occupied)

    hole_cells = {
        (x, y)
        for x in range(HOLE_X_RANGE[0], HOLE_X_RANGE[1] + 1)
        for y in range(HOLE_Y_RANGE[0], HOLE_Y_RANGE[1] + 1)
    }
    bodies_in_hole = sorted(
        cell for cell in hole_cells if (cell[0] + off_x, cell[1] + off_y) in occupied
    )
    if bodies_in_hole:
        raise ConversionError(f"ghost rectangle is not free of facility bodies: {bodies_in_hole[:8]}")
    return facilities


def build_routing_layer(
    witness: dict[str, Any],
    body_cells: set[tuple[int, int]],
    stats: ConversionStats,
    offset: tuple[int, int],
) -> dict[str, dict[str, Any]]:
    off_x, off_y = offset
    layer: dict[str, dict[str, Any]] = {}
    hole_cells = {
        (x, y)
        for x in range(HOLE_X_RANGE[0], HOLE_X_RANGE[1] + 1)
        for y in range(HOLE_Y_RANGE[0], HOLE_Y_RANGE[1] + 1)
    }

    for component in witness["route_components"]:
        kind = str(component["kind"])
        canonical_type = ROUTING_KIND_TO_CANONICAL_TYPE.get(kind)
        if canonical_type is None:
            raise ConversionError(f"unmapped routing kind {kind!r} at {component['x']},{component['y']}")
        raw_x = int(component["x"])
        raw_y = int(component["y"])
        x = raw_x + off_x
        y = raw_y + off_y
        key = f"{x},{y}"
        if key in layer:
            raise ConversionError(f"duplicate routing component at {key}")
        if (x, y) in body_cells:
            raise ConversionError(f"routing component at {key} collides with a facility body")

        flow_in = sorted({str(value) for value in component["inputs"]})
        flow_out = sorted({str(value) for value in component["outputs"]})
        for direction in flow_in + flow_out:
            if direction not in ("N", "S", "E", "W"):
                raise ConversionError(f"unmapped routing direction {direction!r} at {key}")
        if not flow_in or not flow_out:
            raise ConversionError(f"routing component at {key} has an empty flow side")

        layer[key] = {
            "type": canonical_type,
            "commodity": ROUTING_COMMODITY_SENTINEL,
            "flow_in": flow_in,
            "flow_out": flow_out,
        }
        stats.routing_kind_counts[kind] = stats.routing_kind_counts.get(kind, 0) + 1
        if (raw_x, raw_y) in hole_cells:
            stats.routing_cells_in_hole += 1

    stats.routing_cell_count = len(layer)
    return layer


def build_canonical_blueprint(
    registration_path: Path,
    witness_path: Path,
    export_timestamp: str,
    offset: tuple[int, int],
) -> tuple[dict[str, Any], ConversionStats]:
    stats = ConversionStats()

    pool_sha = sha256_of(FROZEN_POOL)
    if pool_sha != FROZEN_POOL_SHA256:
        raise ConversionError(
            f"frozen candidate pool hash mismatch: expected {FROZEN_POOL_SHA256}, got {pool_sha}"
        )
    pool = load_json(FROZEN_POOL)["facility_pools"]
    registration = load_json(registration_path)["solution"]
    witness = load_json(witness_path)

    commodities = assert_all_commodities_are_solid(witness)
    stats.notes.append(f"witness commodities (all solid, none pipe-family): {len(commodities)}")

    ports_by_instance = collect_witness_active_ports(witness)
    unknown_owners = sorted(set(ports_by_instance) - set(registration))
    if unknown_owners:
        raise ConversionError(f"witness active ports reference unknown instances: {unknown_owners[:5]}")

    facilities = build_facilities(registration, pool, ports_by_instance, stats, offset)
    declared_active = int(witness["validation"]["active_terminal_counts"]["all"])
    if stats.active_port_count != declared_active:
        raise ConversionError(
            f"active port count drift: carried {stats.active_port_count}, witness declares {declared_active}"
        )

    body_cells: set[tuple[int, int]] = set()
    for facility in facilities:
        anchor = facility["anchor"]
        poses = pool[facility["facility_type"]]
        pose = next(
            pose
            for pose in poses
            if pose["anchor"]["x"] == anchor["x"] - offset[0]
            and pose["anchor"]["y"] == anchor["y"] - offset[1]
            and str(pose["pose_params"]["orientation"]) == str(facility["orientation"])
            and str(pose["pose_params"]["port_mode"]) == facility["port_mode"]
        )
        for cell in pose["occupied_cells"]:
            body_cells.add((int(cell[0]) + offset[0], int(cell[1]) + offset[1]))

    routing_layer = build_routing_layer(witness, body_cells, stats, offset)
    declared_routes = int(witness["validation"]["route_cells"])
    if stats.routing_cell_count != declared_routes:
        raise ConversionError(
            f"routing cell count drift: carried {stats.routing_cell_count}, witness declares {declared_routes}"
        )

    payload = {
        "metadata": {
            "version": "1.1.0",
            "solve_time_seconds": 0.0,
            "benders_iterations": 0,
            "export_timestamp": export_timestamp,
        },
        "objective_achieved": {
            "empty_rect": {
                "w": HOLE_X_RANGE[1] - HOLE_X_RANGE[0] + 1,
                "h": HOLE_Y_RANGE[1] - HOLE_Y_RANGE[0] + 1,
                "anchor_x": HOLE_X_RANGE[0] + offset[0],
                "anchor_y": HOLE_Y_RANGE[0] + offset[1],
                "score": float(
                    (HOLE_X_RANGE[1] - HOLE_X_RANGE[0] + 1) * (HOLE_Y_RANGE[1] - HOLE_Y_RANGE[0] + 1)
                ),
            }
        },
        "facilities": facilities,
        "routing_network": {"L0_ground": routing_layer, "L1_elevated": {}},
    }
    return payload, stats


def device_port_edges(type_id: str, rotation: int, registries: Any) -> tuple[set[str], set[str]]:
    """Rotated (input_edges, output_edges) for a 1x1 logistics device."""
    definition = registries.device_types_by_id[type_id]
    inputs: set[str] = set()
    outputs: set[str] = set()
    for port in definition.get("ports0", []):
        edge = rotate_edge(str(port["edge"]), rotation)
        if str(port["direction"]) == "Input":
            inputs.add(edge)
        else:
            outputs.add(edge)
    return inputs, outputs


def correct_routing_flow_rotations(
    blueprint: dict[str, Any],
    routing_layer: dict[str, dict[str, Any]],
    registries: Any,
) -> dict[str, int]:
    """Re-derive each routing device's typeId/rotation from the design's flow.

    The stock exporter maps a canonical direction name straight onto an
    IndustrialPlanner rotation, which (a) ignores the y-axis flip between the
    two conventions and (b) drops flow orientation entirely for straight belts
    (rotation is chosen from the axis only).  This pass replaces those two
    fields -- and nothing else -- with the unique choice whose rotated ports
    reproduce the design's flow_in/flow_out.  Fail-closed: a routing cell with
    no satisfying device raises.
    """
    devices_by_origin: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for device in blueprint["devices"]:
        devices_by_origin.setdefault(
            (int(device["origin"]["x"]), int(device["origin"]["y"])), []
        ).append(device)

    stats = {"rotation_changed": 0, "type_changed": 0, "unchanged": 0}
    for coord_key, cell in routing_layer.items():
        x_text, y_text = coord_key.split(",", 1)
        origin = (int(x_text), int(y_text))
        want_in = {CANONICAL_DIR_TO_IP_EDGE[d] for d in cell["flow_in"]}
        want_out = {CANONICAL_DIR_TO_IP_EDGE[d] for d in cell["flow_out"]}
        candidates = ROUTING_DEVICE_CANDIDATES[cell["type"]]

        matches = [
            (type_id, rotation)
            for type_id in candidates
            for rotation in (0, 90, 180, 270)
            if (lambda edges: want_in <= edges[0] and want_out <= edges[1])(
                device_port_edges(type_id, rotation, registries)
            )
        ]
        if not matches:
            raise ConversionError(
                f"no IndustrialPlanner device reproduces the design flow at {coord_key}: "
                f"type={cell['type']} flow_in={cell['flow_in']} flow_out={cell['flow_out']}"
            )

        target = None
        for device in devices_by_origin.get(origin, []):
            if str(device["typeId"]) in candidates:
                target = device
                break
        if target is None:
            raise ConversionError(f"no exported routing device at {coord_key}")

        type_id, rotation = next(
            (entry for entry in matches if entry[0] == str(target["typeId"])), matches[0]
        )
        if str(target["typeId"]) != type_id:
            stats["type_changed"] += 1
            target["typeId"] = type_id
        if int(target["rotation"]) != rotation:
            stats["rotation_changed"] += 1
            target["rotation"] = rotation
        else:
            stats["unchanged"] += 1

    blueprint["devices"].sort(
        key=lambda entry: (
            int(entry["origin"]["x"]),
            int(entry["origin"]["y"]),
            str(entry["typeId"]),
            int(entry["rotation"]),
        )
    )
    return stats


def audit_routing_link_fidelity(
    blueprint: dict[str, Any], routing_layer: dict[str, dict[str, Any]]
) -> dict[str, int]:
    """How many design routing connections survive as legal IP links."""
    from src.adapters.industrial_planner.blueprint_validator import (
        _links_from_layout,
        _normalize_user_device,
        load_static_registries,
    )

    registries = load_static_registries()
    schema_errors: list[str] = []
    registry_errors: list[str] = []
    placements = []
    for index, raw_device in enumerate(blueprint["devices"]):
        placement = _normalize_user_device(
            raw_device,
            index=index,
            registries=registries,
            schema_errors=schema_errors,
            registry_errors=registry_errors,
        )
        if placement is not None:
            placements.append(placement)

    origin_by_instance = {
        placement.instance_id: (placement.origin_x, placement.origin_y) for placement in placements
    }
    exported_links = {
        (origin_by_instance[out_port.instance_id], origin_by_instance[in_port.instance_id])
        for out_port, in_port in _links_from_layout(placements, registries)
    }

    delta = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    cells = {}
    for coord_key, cell in routing_layer.items():
        x_text, y_text = coord_key.split(",", 1)
        cells[(int(x_text), int(y_text))] = cell

    intended = set()
    for (x, y), cell in cells.items():
        for direction in cell["flow_out"]:
            dx, dy = delta[direction]
            neighbour = (x + dx, y + dy)
            if neighbour in cells and opposite[direction] in cells[neighbour]["flow_in"]:
                intended.add(((x, y), neighbour))

    forward = sum(1 for pair in intended if pair in exported_links)
    reversed_count = sum(1 for pair in intended if (pair[1], pair[0]) in exported_links)
    return {
        "design_routing_connections": len(intended),
        "exported_with_correct_direction": forward,
        "exported_but_reversed": reversed_count,
        "not_linked": len(intended) - forward - reversed_count,
    }


def report_target_footprints(blueprint: dict[str, Any]) -> dict[str, int]:
    registries = load_static_registries()
    counts: dict[str, int] = {}
    for device in blueprint["devices"]:
        counts[str(device["typeId"])] = counts.get(str(device["typeId"]), 0) + 1
    unknown = sorted(name for name in counts if name not in registries.device_types_by_id)
    if unknown:
        raise ConversionError(f"exported device types missing from the static registry: {unknown}")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, default=DEFAULT_REGISTRATION)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base-id", default=DEFAULT_BASE_ID)
    parser.add_argument("--offset-x", type=int, default=0)
    parser.add_argument("--offset-y", type=int, default=0)
    parser.add_argument("--export-name", default="band22 witness (42,6) -- research export")
    parser.add_argument("--export-timestamp", default="2026-08-05T00:00:00Z")
    parser.add_argument("--blueprint-filename", default="band22_industrial_planner_blueprint.json")
    parser.add_argument(
        "--no-correct-routing-flow",
        dest="correct_routing_flow",
        action="store_false",
        help="emit the stock exporter's routing rotations verbatim (loses flow orientation)",
    )
    parser.set_defaults(correct_routing_flow=True)
    args = parser.parse_args()

    offset = (args.offset_x, args.offset_y)
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    payload, stats = build_canonical_blueprint(
        args.registration, args.witness, args.export_timestamp, offset
    )
    canonical_path = out_dir / "band22_canonical_blueprint.intermediate.json"
    canonical_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    bundle = build_industrial_planner_export_bundle(
        blueprint_payload=payload,
        export_name=args.export_name,
        base_id=args.base_id,
    )
    blueprint = bundle["blueprint"]
    routing_layer = payload["routing_network"]["L0_ground"]
    fidelity_before = audit_routing_link_fidelity(blueprint, routing_layer)
    if args.correct_routing_flow:
        registries = load_static_registries()
        flow_correction = correct_routing_flow_rotations(blueprint, routing_layer, registries)
        fidelity_after = audit_routing_link_fidelity(blueprint, routing_layer)
        revalidated = validate_industrial_planner_blueprint(blueprint)
        report_payload = revalidated.to_dict()
        bundle["validation_report"] = report_payload
        bundle["validation_report_markdown"] = revalidated.to_markdown()
    else:
        flow_correction = {}
        fidelity_after = fidelity_before
        report_payload = bundle["validation_report"]
    device_counts = report_target_footprints(blueprint)

    blueprint_path = out_dir / args.blueprint_filename
    blueprint_text = json.dumps(blueprint, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    blueprint_path.write_text(blueprint_text, encoding="utf-8")
    (out_dir / "validation_report.json").write_text(
        json.dumps(bundle["validation_report"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "validation_report.md").write_text(
        str(bundle["validation_report_markdown"]), encoding="utf-8"
    )
    (out_dir / "compatibility_manifest.json").write_text(
        json.dumps(bundle["compatibility_manifest"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = report_payload
    error_buckets = (
        "schema_errors",
        "registry_errors",
        "lot_boundary_errors",
        "placement_constraint_errors",
        "unsupported_rule_errors",
        "overlap_errors",
        "port_mismatch_errors",
    )
    errors_by_bucket = {name: list(report[name]) for name in error_buckets if report[name]}
    error_count = sum(len(values) for values in errors_by_bucket.values())
    summary = {
        "blueprint_path": str(blueprint_path),
        "blueprint_sha256": hashlib.sha256(blueprint_text.encode("utf-8")).hexdigest(),
        "base_id": args.base_id,
        "offset": {"x": offset[0], "y": offset[1]},
        "source_facility_count": stats.facility_count,
        "source_body_cells": stats.body_cells,
        "source_active_ports": stats.active_port_count,
        "source_routing_cells": stats.routing_cell_count,
        "source_routing_kind_counts": stats.routing_kind_counts,
        "source_facility_type_counts": stats.facility_type_counts,
        "routing_cells_inside_ghost_rect": stats.routing_cells_in_hole,
        "routing_flow_correction_applied": bool(args.correct_routing_flow),
        "routing_flow_correction": flow_correction,
        "routing_link_fidelity_before_correction": fidelity_before,
        "routing_link_fidelity_after_correction": fidelity_after,
        "exported_device_count": len(blueprint["devices"]),
        "exported_device_type_counts": device_counts,
        "validation_error_count": error_count,
        "validation_error_counts_by_bucket": {
            name: len(values) for name, values in errors_by_bucket.items()
        },
        "validation_error_samples": {
            name: values[:6] for name, values in errors_by_bucket.items()
        },
        "validation_port_warning_count": len(report["port_warnings"]),
        "is_import_compatible": report["is_import_compatible"],
        "is_layout_healthy": report["is_layout_healthy"],
        "exporter_warning_count": len(bundle["warnings"]),
        "exporter_warnings_sample": list(bundle["warnings"])[:20],
        "notes": stats.notes,
    }
    (out_dir / "validation_errors_full.json").write_text(
        json.dumps(errors_by_bucket, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "exporter_warnings_full.json").write_text(
        json.dumps(list(bundle["warnings"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "export_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
