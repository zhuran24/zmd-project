#!/usr/bin/env python3
"""Independent compact identity-front coordinate relaxation for rounds 4/5.

This research-only builder deliberately does not instantiate the production master.
It reconstructs the current pinned placement domain and keeps only necessary
conditions for a live feasible layout: facility/pole packing, power coverage, the
movable ghost, and routing-visible identity-front availability.  It omits binding
labels, belt paths, connectivity, front/front exclusion, and front/ghost exclusion.

The certificate direction is therefore only::

    live feasible -> this model feasible
    this model INFEASIBLE -> live infeasible

A FEASIBLE result is merely a relaxation witness.  The caller is responsible for
running this file outside sealed paths and for applying an external cgroup limit.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


GRID_W = 70
GRID_H = 70
EXPECTED_POOL_SHA256 = (
    "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3"
)
EXPECTED_POOL_TOTAL = 82_829
EXPECTED_MODE_TOTAL = 21
EXPECTED_MANDATORY_INSTANCES = 266
EXPECTED_MANDATORY_GROUPS = 19
EXPECTED_MANDATORY_POWERED = 219
EXPECTED_MANDATORY_AREA = 3_544
GENERIC_INPUT_DEMAND = 2
GENERIC_INPUT_COMMODITIES = ("qiaoyu_capsule", "valley_battery")
GENERIC_OUTPUT_REQUIREMENTS = {"blue_iron_ore": 34, "source_ore": 18}
MAX_BOX_SLOTS = 2
MAX_POLE_SLOTS = EXPECTED_MANDATORY_POWERED + MAX_BOX_SLOTS
ALLOWED_DIRECTIONS = frozenset({"N", "S", "E", "W"})
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


# Independent literal ledger from the corrected identity-front audit.  The two
# generic inputs are modeled separately because they may bind to the core or to
# either retained protocol box.
MACHINE_DEMANDS: dict[str, tuple[int, int]] = {
    "crusher_blue_iron": (1, 1),
    "crusher_buckwheat": (1, 2),
    "crusher_sandleaf": (1, 3),
    "crusher_source": (1, 1),
    "filling_capsule": (4, 1),
    "grinder_dense_blue_iron": (3, 1),
    "grinder_dense_source": (3, 1),
    "grinder_fine_buckwheat": (3, 1),
    "molding_bottle": (2, 1),
    "packaging_battery": (5, 1),
    "parts_maker": (1, 1),
    "planter_buckwheat": (1, 1),
    "planter_sandleaf": (1, 1),
    "refinery_blue_iron": (1, 1),
    "refinery_steel": (1, 1),
    "seed_collector_buckwheat": (1, 2),
    "seed_collector_sandleaf": (1, 2),
}

EXPECTED_OPERATION_COUNTS: dict[str, int] = {
    "boundary_io": 46,
    "crusher_blue_iron": 34,
    "crusher_buckwheat": 6,
    "crusher_sandleaf": 11,
    "crusher_source": 18,
    "filling_capsule": 3,
    "grinder_dense_blue_iron": 17,
    "grinder_dense_source": 9,
    "grinder_fine_buckwheat": 6,
    "molding_bottle": 6,
    "packaging_battery": 3,
    "parts_maker": 6,
    "planter_buckwheat": 11,
    "planter_sandleaf": 21,
    "protocol_core": 1,
    "refinery_blue_iron": 34,
    "refinery_steel": 17,
    "seed_collector_buckwheat": 6,
    "seed_collector_sandleaf": 11,
}

EXPECTED_POOL_COUNTS: dict[str, int] = {
    "manufacturing_3x3": 17_952,
    "manufacturing_5x5": 16_896,
    "manufacturing_6x4": 16_900,
    "protocol_core": 7_688,
    "protocol_storage_box": 18_496,
    "power_pole": 4_761,
    "boundary_storage_port": 136,
}


@dataclass
class BuildResult:
    model: Any
    handles: dict[str, Any]
    audit: dict[str, Any]
    snapshot: dict[str, Any]


@dataclass
class _FacilitySlot:
    key: str
    template: str
    operation_type: str
    group_id: str | None
    slot_index: int
    active: Any | None
    x: Any
    y: Any
    mode: Any
    order: Any
    body_x_start: Any
    body_y_start: Any
    body_x_end: Any
    body_y_end: Any
    x_interval: Any
    y_interval: Any
    modes: dict[int, dict[str, Any]]
    tuple_to_pose: dict[tuple[int, int, int], int]
    needs_power: bool


@dataclass
class _PoleSlot:
    index: int
    active: Any
    x: Any
    y: Any
    order: Any
    x_interval: Any
    y_interval: Any


@dataclass
class _GenericFrontEncoding:
    witnesses: list[dict[str, Any]]
    keys: list[Any]
    owner_lits_by_provider: list[list[Any]]
    table_row_count: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cell_xy(cell: Any) -> tuple[int, int]:
    if isinstance(cell, Mapping):
        return int(cell["x"]), int(cell["y"])
    return int(cell[0]), int(cell[1])


def _relative_cells(pose: Mapping[str, Any], field: str) -> tuple[tuple[int, int], ...]:
    anchor_x = int(pose["anchor"]["x"])
    anchor_y = int(pose["anchor"]["y"])
    return tuple(
        sorted(
            (x - anchor_x, y - anchor_y)
            for x, y in (_cell_xy(cell) for cell in pose.get(field, []) or [])
        )
    )


def _is_full_rectangle(cells: Iterable[tuple[int, int]]) -> bool:
    values = set(cells)
    if not values:
        return False
    xs = [x for x, _ in values]
    ys = [y for _, y in values]
    return values == {
        (x, y)
        for x in range(min(xs), max(xs) + 1)
        for y in range(min(ys), max(ys) + 1)
    }


def _footprint_key(body: Sequence[tuple[int, int]]) -> str:
    if not body:
        return "footprint::missing"
    xs = [cell[0] for cell in body]
    ys = [cell[1] for cell in body]
    bounds = ":".join(str(value) for value in (min(xs), max(xs), min(ys), max(ys)))
    cells = ";".join(f"{x}:{y}" for x, y in sorted(body))
    return f"footprint::{bounds}::{cells}"


def _mode_token(pose: Mapping[str, Any]) -> tuple[str, str, str]:
    """Mirror the live master's canonical mode token exactly.

    The live delegate deliberately canonicalizes orientation and port mode with
    ``str``.  Keeping that coercion here avoids the historical int/string domain
    split that could make this relaxation stricter than production.
    """

    params = dict(pose.get("pose_params", {}))
    body = _relative_cells(pose, "occupied_cells")
    if not _is_full_rectangle(body):
        raise AssertionError(f"non-rectangular body: {pose.get('pose_id')}")
    return (
        str(params.get("orientation", "")),
        str(params.get("port_mode", "")),
        _footprint_key(body),
    )


def _relative_port_pattern(
    pose: Mapping[str, Any], field: str
) -> tuple[tuple[int, int, str], ...]:
    """Return identity-front access cells relative to the body anchor.

    Corrected core/box candidates intentionally retain inactive access cells at
    -1 or 70.  They remain in the relative pattern; the witness coordinate's
    [0,69] domain prevents selecting one when it is out of grid.
    """

    anchor_x = int(pose["anchor"]["x"])
    anchor_y = int(pose["anchor"]["y"])
    occupied = {_cell_xy(cell) for cell in pose.get("occupied_cells", []) or []}
    result: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int, str]] = set()
    for port in pose.get(field, []) or []:
        x = int(port["x"])
        y = int(port["y"])
        direction = str(port["dir"])
        if direction not in ALLOWED_DIRECTIONS:
            raise AssertionError(f"unknown direction {direction!r}")
        if (x, y) in occupied:
            raise AssertionError(f"stored access cell is in own body: {pose.get('pose_id')}")
        step_x, step_y = DIR_DELTA[direction]
        if (x - step_x, y - step_y) not in occupied:
            raise AssertionError(
                f"stored identity front is not first outside body: {pose.get('pose_id')}"
            )
        key = (x - anchor_x, y - anchor_y, direction)
        if key in seen:
            raise AssertionError(f"duplicate physical port key: {pose.get('pose_id')} {key}")
        seen.add(key)
        result.append(key)
    return tuple(sorted(result))


def _build_domains(
    pools: Mapping[str, Sequence[Mapping[str, Any]]]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    domains: dict[str, dict[str, Any]] = {}
    mode_domains: dict[str, dict[str, Any]] = {}
    total_poses = 0
    total_modes = 0

    for template, raw_pool in sorted(pools.items()):
        pool = list(raw_pool)
        total_poses += len(pool)
        tokens = sorted({_mode_token(pose) for pose in pool})
        mode_by_token = {token: index for index, token in enumerate(tokens)}
        accumulators: dict[int, dict[str, set[Any]]] = defaultdict(
            lambda: {"anchors": set(), "bodies": set(), "inputs": set(), "outputs": set()}
        )
        tuple_to_pose: dict[tuple[int, int, int], int] = {}
        pose_ids: set[str] = set()

        for pose_index, pose in enumerate(pool):
            pose_id = str(pose.get("pose_id", ""))
            if not pose_id or pose_id in pose_ids:
                raise AssertionError(f"missing/duplicate pose_id: {template} {pose_id!r}")
            pose_ids.add(pose_id)
            x = int(pose["anchor"]["x"])
            y = int(pose["anchor"]["y"])
            mode_id = int(mode_by_token[_mode_token(pose)])
            pose_tuple = (x, y, mode_id)
            if pose_tuple in tuple_to_pose:
                raise AssertionError(f"duplicate compact pose tuple: {template} {pose_tuple}")
            tuple_to_pose[pose_tuple] = pose_index
            acc = accumulators[mode_id]
            acc["anchors"].add((x, y))
            acc["bodies"].add(_relative_cells(pose, "occupied_cells"))
            acc["inputs"].add(_relative_port_pattern(pose, "input_port_cells"))
            acc["outputs"].add(_relative_port_pattern(pose, "output_port_cells"))

        modes: dict[int, dict[str, Any]] = {}
        for mode_id, token in enumerate(tokens):
            acc = accumulators[mode_id]
            if not acc["anchors"]:
                raise AssertionError(f"empty mode: {template}/{mode_id}")
            if any(len(acc[key]) != 1 for key in ("bodies", "inputs", "outputs")):
                raise AssertionError(f"unstable relative geometry: {template}/{mode_id}")
            anchors = set(acc["anchors"])
            xs = [x for x, _ in anchors]
            ys = [y for _, y in anchors]
            rectangle = {
                (x, y)
                for x in range(min(xs), max(xs) + 1)
                for y in range(min(ys), max(ys) + 1)
            }
            if anchors != rectangle:
                raise AssertionError(f"mode anchor domain has holes: {template}/{mode_id}")
            body = next(iter(acc["bodies"]))
            body_xs = [x for x, _ in body]
            body_ys = [y for _, y in body]
            payload = {
                "mode_id": mode_id,
                "token": token,
                "x_min": min(xs),
                "x_max": max(xs),
                "y_min": min(ys),
                "y_max": max(ys),
                "dx_min": min(body_xs),
                "dy_min": min(body_ys),
                "width": max(body_xs) - min(body_xs) + 1,
                "height": max(body_ys) - min(body_ys) + 1,
                "body": body,
                "input": next(iter(acc["inputs"])),
                "output": next(iter(acc["outputs"])),
                "pose_count": len(anchors),
            }
            modes[mode_id] = payload
            geometry = {
                "body": [[x, y] for x, y in sorted(payload["body"])],
                "input": [[x, y, direction] for x, y, direction in sorted(payload["input"])],
                "output": [[x, y, direction] for x, y, direction in sorted(payload["output"])],
            }
            mode_domains[f"{template}|{token[0]}|{token[1]}"] = {
                "mode_id": mode_id,
                "x_min": payload["x_min"],
                "x_max": payload["x_max"],
                "y_min": payload["y_min"],
                "y_max": payload["y_max"],
                "pose_count": payload["pose_count"],
                "full_rectangle": True,
                "geometry_sha256": _canonical_sha(geometry),
            }
        total_modes += len(modes)
        domains[template] = {"modes": modes, "tuple_to_pose": tuple_to_pose}

    pool_counts = {str(template): len(pool) for template, pool in sorted(pools.items())}
    if pool_counts != EXPECTED_POOL_COUNTS:
        raise AssertionError(f"pool count drift: {pool_counts} != {EXPECTED_POOL_COUNTS}")
    if total_poses != EXPECTED_POOL_TOTAL or total_modes != EXPECTED_MODE_TOTAL:
        raise AssertionError(
            f"pool/mode drift: poses={total_poses}, modes={total_modes}"
        )
    return domains, {
        "pool_total": total_poses,
        "mode_total": total_modes,
        "pool_counts": pool_counts,
        "mode_domains": mode_domains,
    }


def _edge_oob_pose_counts(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for template, pool in pools.items():
        for pose in pool:
            ports = [
                *list(pose.get("input_port_cells", []) or []),
                *list(pose.get("output_port_cells", []) or []),
            ]
            if any(
                not (0 <= int(port["x"]) < GRID_W and 0 <= int(port["y"]) < GRID_H)
                for port in ports
            ):
                counts[str(template)] += 1
    return dict(sorted(counts.items()))


def _mandatory_groups(instances: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    operation_counts = Counter(str(instance["operation_type"]) for instance in instances)
    if dict(sorted(operation_counts.items())) != EXPECTED_OPERATION_COUNTS:
        raise AssertionError(f"mandatory operation ledger drift: {dict(operation_counts)}")
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for instance in instances:
        grouped[(str(instance["facility_type"]), str(instance["operation_type"]))].append(instance)
    result: list[dict[str, Any]] = []
    for group_index, ((template, operation), members) in enumerate(sorted(grouped.items())):
        result.append(
            {
                "group_id": f"group::{template}::{operation}::{group_index}",
                "facility_type": template,
                "operation_type": operation,
                "count": len(members),
                "instance_ids": sorted(str(member["instance_id"]) for member in members),
            }
        )
    if len(instances) != EXPECTED_MANDATORY_INSTANCES or len(result) != EXPECTED_MANDATORY_GROUPS:
        raise AssertionError("mandatory instance/group census drift")
    return result


def _fixed_demand(operation: str) -> tuple[int, int]:
    if operation in MACHINE_DEMANDS:
        return MACHINE_DEMANDS[operation]
    if operation == "boundary_io":
        return 0, 1
    if operation == "protocol_core":
        # Generic input demand is a provider-choice constraint across core/boxes.
        return 0, 6
    raise AssertionError(f"unrecognized mandatory operation: {operation}")


def _operation_front_ledger(groups: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    ledger: dict[str, dict[str, Any]] = {}
    for group in groups:
        operation = str(group["operation_type"])
        template = str(group["facility_type"])
        modeled_inputs, modeled_outputs = _fixed_demand(operation)
        generic_input_capacity = 14 if operation == "protocol_core" else 0
        generic_output_capacity = 1 if operation == "boundary_io" else 6 if operation == "protocol_core" else 0
        concrete_inputs = 0 if operation in {"boundary_io", "protocol_core"} else modeled_inputs
        concrete_outputs = 0 if operation in {"boundary_io", "protocol_core"} else modeled_outputs
        ledger[operation] = {
            "facility_type": template,
            "concrete_inputs": concrete_inputs,
            "concrete_outputs": concrete_outputs,
            "generic_input_capacity": generic_input_capacity,
            "generic_output_capacity": generic_output_capacity,
            "modeled_input_witnesses": modeled_inputs,
            "modeled_output_witnesses": modeled_outputs,
        }
    return dict(sorted(ledger.items()))


def _create_facility_slot(
    model: Any,
    *,
    key: str,
    template: str,
    operation_type: str,
    group_id: str | None,
    slot_index: int,
    domain: Mapping[str, Any],
    needs_power: bool,
    active: Any | None = None,
) -> _FacilitySlot:
    modes = dict(domain["modes"])
    mode_count = len(modes)
    x = model.NewIntVar(
        min(int(payload["x_min"]) for payload in modes.values()),
        max(int(payload["x_max"]) for payload in modes.values()),
        f"x__{key}",
    )
    y = model.NewIntVar(
        min(int(payload["y_min"]) for payload in modes.values()),
        max(int(payload["y_max"]) for payload in modes.values()),
        f"y__{key}",
    )
    mode = model.NewIntVar(0, mode_count - 1, f"mode__{key}")
    mode_lits = []
    for mode_id, payload in sorted(modes.items()):
        lit = model.NewBoolVar(f"is_mode__{key}__{mode_id}")
        model.Add(mode == mode_id).OnlyEnforceIf(lit)
        model.Add(x >= int(payload["x_min"])).OnlyEnforceIf(lit)
        model.Add(x <= int(payload["x_max"])).OnlyEnforceIf(lit)
        model.Add(y >= int(payload["y_min"])).OnlyEnforceIf(lit)
        model.Add(y <= int(payload["y_max"])).OnlyEnforceIf(lit)
        mode_lits.append(lit)
    model.AddExactlyOne(mode_lits)

    dx_min = model.NewIntVar(
        min(int(payload["dx_min"]) for payload in modes.values()),
        max(int(payload["dx_min"]) for payload in modes.values()),
        f"body_dx__{key}",
    )
    dy_min = model.NewIntVar(
        min(int(payload["dy_min"]) for payload in modes.values()),
        max(int(payload["dy_min"]) for payload in modes.values()),
        f"body_dy__{key}",
    )
    width = model.NewIntVar(
        min(int(payload["width"]) for payload in modes.values()),
        max(int(payload["width"]) for payload in modes.values()),
        f"body_w__{key}",
    )
    height = model.NewIntVar(
        min(int(payload["height"]) for payload in modes.values()),
        max(int(payload["height"]) for payload in modes.values()),
        f"body_h__{key}",
    )
    model.AddAllowedAssignments(
        [mode, dx_min, dy_min, width, height],
        [
            [
                mode_id,
                int(payload["dx_min"]),
                int(payload["dy_min"]),
                int(payload["width"]),
                int(payload["height"]),
            ]
            for mode_id, payload in sorted(modes.items())
        ],
    )
    body_x_start = model.NewIntVar(0, GRID_W - 1, f"body_x_start__{key}")
    body_y_start = model.NewIntVar(0, GRID_H - 1, f"body_y_start__{key}")
    body_x_end = model.NewIntVar(1, GRID_W, f"body_x_end__{key}")
    body_y_end = model.NewIntVar(1, GRID_H, f"body_y_end__{key}")
    model.Add(body_x_start == x + dx_min)
    model.Add(body_y_start == y + dy_min)
    model.Add(body_x_end == body_x_start + width)
    model.Add(body_y_end == body_y_start + height)
    if active is None:
        x_interval = model.NewIntervalVar(body_x_start, width, body_x_end, f"x_iv__{key}")
        y_interval = model.NewIntervalVar(body_y_start, height, body_y_end, f"y_iv__{key}")
    else:
        x_interval = model.NewOptionalIntervalVar(
            body_x_start, width, body_x_end, active, f"x_iv__{key}"
        )
        y_interval = model.NewOptionalIntervalVar(
            body_y_start, height, body_y_end, active, f"y_iv__{key}"
        )
        # Box mode 0 has a complete 0..67 square anchor domain.
        model.Add(x == 0).OnlyEnforceIf(active.Not())
        model.Add(y == 0).OnlyEnforceIf(active.Not())
        model.Add(mode == 0).OnlyEnforceIf(active.Not())
    order = model.NewIntVar(0, GRID_W * GRID_H * mode_count - 1, f"order__{key}")
    model.Add(order == x * (GRID_H * mode_count) + y * mode_count + mode)
    return _FacilitySlot(
        key=key,
        template=template,
        operation_type=operation_type,
        group_id=group_id,
        slot_index=slot_index,
        active=active,
        x=x,
        y=y,
        mode=mode,
        order=order,
        body_x_start=body_x_start,
        body_y_start=body_y_start,
        body_x_end=body_x_end,
        body_y_end=body_y_end,
        x_interval=x_interval,
        y_interval=y_interval,
        modes=modes,
        tuple_to_pose=dict(domain["tuple_to_pose"]),
        needs_power=needs_power,
    )


def _add_active_prefix_strict_order(model: Any, slots: Sequence[Any]) -> int:
    """Canonicalize interchangeable optional slots without fixing their count."""

    constraints = 0
    for left, right in zip(slots, slots[1:]):
        model.Add(left.active >= right.active)
        model.Add(left.order < right.order).OnlyEnforceIf(right.active)
        constraints += 1
    return constraints


def _add_unconditional_strict_order(model: Any, orders: Sequence[Any]) -> int:
    """Order semantically identical mandatory slots by their injective order key."""

    constraints = 0
    for left, right in zip(orders, orders[1:]):
        model.Add(left < right)
        constraints += 1
    return constraints


def _add_point_no_overlap(
    model: Any,
    body_x_intervals: Sequence[Any],
    body_y_intervals: Sequence[Any],
    front_x: Any,
    front_y: Any,
    prefix: str,
) -> None:
    """Keep one selected identity front clear of bodies, but not other fronts/ghost."""

    front_x_end = model.NewIntVar(1, GRID_W, f"x_end__{prefix}")
    front_y_end = model.NewIntVar(1, GRID_H, f"y_end__{prefix}")
    model.Add(front_x_end == front_x + 1)
    model.Add(front_y_end == front_y + 1)
    point_x = model.NewIntervalVar(front_x, 1, front_x_end, f"x_iv__{prefix}")
    point_y = model.NewIntervalVar(front_y, 1, front_y_end, f"y_iv__{prefix}")
    # Intentionally one constraint per witness: no witness/front, ghost/front,
    # or global front-cell exclusion is introduced.
    model.AddNoOverlap2D([*body_x_intervals, point_x], [*body_y_intervals, point_y])


def _add_generic_input_witnesses(
    model: Any,
    *,
    providers: Sequence[_FacilitySlot],
    commodities: Sequence[str],
    body_x_intervals: Sequence[Any],
    body_y_intervals: Sequence[Any],
) -> _GenericFrontEncoding:
    """Encode labeled generic inputs against real provider ports.

    The physical key namespace is global across providers, modes, and port slots.
    Distinct keys therefore mean distinct physical ports even when two ports share
    one access cell.  Optional providers are active iff retained by normal form.
    """

    rows_by_provider: list[list[list[int]]] = []
    all_generic_rows: list[list[int]] = []
    generic_code = 0
    for provider in providers:
        provider_rows: list[list[int]] = []
        for mode_id, payload in sorted(provider.modes.items()):
            for dx, dy, _direction in payload["input"]:
                row = [mode_id, generic_code, int(dx), int(dy)]
                provider_rows.append(row)
                all_generic_rows.append(row)
                generic_code += 1
        if not provider_rows:
            raise AssertionError(f"generic provider has no physical input ports: {provider.key}")
        rows_by_provider.append(provider_rows)
    if not all_generic_rows:
        raise AssertionError("generic provider set is empty")

    witnesses: list[dict[str, Any]] = []
    keys: list[Any] = []
    owner_lits_by_provider: list[list[Any]] = [[] for _provider in providers]
    for ordinal, commodity in enumerate(commodities):
        prefix = f"front__generic_input__{commodity}"
        owner = model.NewIntVar(0, len(providers) - 1, f"owner__{prefix}")
        owner_lits = []
        key = model.NewIntVar(0, generic_code - 1, f"key__{prefix}")
        dx = model.NewIntVar(
            min(row[2] for row in all_generic_rows),
            max(row[2] for row in all_generic_rows),
            f"dx__{prefix}",
        )
        dy = model.NewIntVar(
            min(row[3] for row in all_generic_rows),
            max(row[3] for row in all_generic_rows),
            f"dy__{prefix}",
        )
        front_x = model.NewIntVar(0, GRID_W - 1, f"x__{prefix}")
        front_y = model.NewIntVar(0, GRID_H - 1, f"y__{prefix}")
        for provider_index, (provider, rows) in enumerate(zip(providers, rows_by_provider)):
            lit = model.NewBoolVar(f"is_owner__{prefix}__{provider_index}")
            model.Add(owner == provider_index).OnlyEnforceIf(lit)
            model.AddAllowedAssignments([provider.mode, key, dx, dy], rows).OnlyEnforceIf(lit)
            model.Add(front_x == provider.x + dx).OnlyEnforceIf(lit)
            model.Add(front_y == provider.y + dy).OnlyEnforceIf(lit)
            if provider.active is not None:
                model.Add(provider.active == 1).OnlyEnforceIf(lit)
            owner_lits.append(lit)
            owner_lits_by_provider[provider_index].append(lit)
        model.AddExactlyOne(owner_lits)
        _add_point_no_overlap(
            model,
            body_x_intervals,
            body_y_intervals,
            front_x,
            front_y,
            prefix,
        )
        keys.append(key)
        witnesses.append(
            {
                "kind": "generic_input",
                "slot": None,
                "providers": list(providers),
                "role": "input",
                "ordinal": ordinal,
                "commodity": str(commodity),
                "key": key,
                "x": front_x,
                "y": front_y,
                "owner": owner,
            }
        )

    for left, right in zip(keys, keys[1:]):
        model.Add(left != right)
    for provider_index, provider in enumerate(providers):
        if provider.active is not None:
            model.AddBoolOr(owner_lits_by_provider[provider_index]).OnlyEnforceIf(provider.active)

    return _GenericFrontEncoding(
        witnesses=witnesses,
        keys=keys,
        owner_lits_by_provider=owner_lits_by_provider,
        table_row_count=sum(len(rows) for rows in rows_by_provider),
    )


def _add_designated_power_witness(
    model: Any,
    *,
    slot: _FacilitySlot,
    pole_slots: Sequence[_PoleSlot],
) -> dict[str, Any]:
    """Select one active covering pole, conditionally for an optional body."""

    if not pole_slots:
        raise ValueError("at least one pole slot is required")
    index = model.NewIntVar(0, len(pole_slots) - 1, f"coverer_index__{slot.key}")
    selected_active = model.NewBoolVar(f"coverer_active__{slot.key}")
    selected_x = model.NewIntVar(0, GRID_W - 2, f"coverer_x__{slot.key}")
    selected_y = model.NewIntVar(0, GRID_H - 2, f"coverer_y__{slot.key}")
    model.AddElement(index, [pole.active for pole in pole_slots], selected_active)
    model.AddElement(index, [pole.x for pole in pole_slots], selected_x)
    model.AddElement(index, [pole.y for pole in pole_slots], selected_y)
    constraints = [
        model.Add(selected_active == 1),
        model.Add(selected_x + 6 >= slot.body_x_start),
        model.Add(selected_x <= slot.body_x_end + 4),
        model.Add(selected_y + 6 >= slot.body_y_start),
        model.Add(selected_y <= slot.body_y_end + 4),
    ]
    if slot.active is not None:
        for constraint in constraints:
            constraint.OnlyEnforceIf(slot.active)
    return {"slot": slot, "index": index}


def build_compact_model(project_root: Path, ghost_w: int, ghost_h: int) -> BuildResult:
    """Build the corrected standalone relaxation without touching project files."""

    from ortools.sat.python import cp_model

    project_root = Path(project_root).resolve()
    if not (1 <= int(ghost_w) <= GRID_W and 1 <= int(ghost_h) <= GRID_H):
        raise ValueError("ghost dimensions must be within the 70x70 grid")
    ghost_w = int(ghost_w)
    ghost_h = int(ghost_h)

    input_paths = {
        "data/preprocessed/candidate_placements.json": project_root
        / "data/preprocessed/candidate_placements.json",
        "data/preprocessed/mandatory_exact_instances.json": project_root
        / "data/preprocessed/mandatory_exact_instances.json",
        "rules/canonical_rules.json": project_root / "rules/canonical_rules.json",
        "data/preprocessed/generic_io_requirements.json": project_root
        / "data/preprocessed/generic_io_requirements.json",
        "rules/preprocess_plan.json": project_root / "rules/preprocess_plan.json",
    }
    missing = [str(path) for path in input_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing compact-model inputs: {missing}")
    input_hashes = {name: _sha256_file(path) for name, path in input_paths.items()}
    if input_hashes["data/preprocessed/candidate_placements.json"] != EXPECTED_POOL_SHA256:
        raise AssertionError(
            "candidate pool hash drift: "
            f"{input_hashes['data/preprocessed/candidate_placements.json']} "
            f"!= {EXPECTED_POOL_SHA256}"
        )

    placement_payload = _load_json(input_paths["data/preprocessed/candidate_placements.json"])
    pools = {
        str(template): list(pool)
        for template, pool in dict(placement_payload["facility_pools"]).items()
    }
    instance_payload = _load_json(
        input_paths["data/preprocessed/mandatory_exact_instances.json"]
    )
    instances = list(
        instance_payload if isinstance(instance_payload, list) else instance_payload["instances"]
    )
    rules = dict(_load_json(input_paths["rules/canonical_rules.json"]))
    generic_io = dict(
        _load_json(input_paths["data/preprocessed/generic_io_requirements.json"])
    )
    generic_input_requirements = {
        str(key): int(value)
        for key, value in dict(generic_io.get("required_generic_inputs", {})).items()
    }
    generic_output_requirements = {
        str(key): int(value)
        for key, value in dict(generic_io.get("required_generic_outputs", {})).items()
    }
    expected_generic_inputs = {commodity: 1 for commodity in GENERIC_INPUT_COMMODITIES}
    if generic_input_requirements != expected_generic_inputs:
        raise AssertionError(
            f"generic input requirement drift: {generic_input_requirements}"
        )
    if generic_output_requirements != GENERIC_OUTPUT_REQUIREMENTS:
        raise AssertionError(
            f"generic output requirement drift: {generic_output_requirements}"
        )
    domains, domain_audit = _build_domains(pools)
    groups = _mandatory_groups(instances)
    operation_front_ledger = _operation_front_ledger(groups)
    template_rules = dict(rules["facility_templates"])

    model = cp_model.CpModel()
    slots_by_group: dict[str, list[_FacilitySlot]] = {}
    mandatory_slots: list[_FacilitySlot] = []
    powered_mandatory_slots: list[_FacilitySlot] = []
    facility_strict_order_constraints = 0

    for group in groups:
        group_id = str(group["group_id"])
        template = str(group["facility_type"])
        operation = str(group["operation_type"])
        group_slots: list[_FacilitySlot] = []
        for slot_index in range(int(group["count"])):
            slot = _create_facility_slot(
                model,
                key=f"{group_id}::slot::{slot_index}",
                template=template,
                operation_type=operation,
                group_id=group_id,
                slot_index=slot_index,
                domain=domains[template],
                needs_power=bool(template_rules[template].get("needs_power", False)),
            )
            group_slots.append(slot)
            mandatory_slots.append(slot)
            if slot.needs_power:
                powered_mandatory_slots.append(slot)
        # Slots in one group have identical modeled semantics.  Equal order is
        # already impossible because equal (x,y,mode) means overlapping bodies.
        facility_strict_order_constraints += _add_unconditional_strict_order(
            model, [slot.order for slot in group_slots]
        )
        slots_by_group[group_id] = group_slots

    if len(mandatory_slots) != EXPECTED_MANDATORY_INSTANCES:
        raise AssertionError("mandatory slot count drift")
    if len(powered_mandatory_slots) != EXPECTED_MANDATORY_POWERED:
        raise AssertionError("mandatory powered count drift")

    # A live solution needs only the boxes actually carrying the two required
    # generic inputs.  Their union has size at most two; all other box uses are
    # routing structure omitted by this relaxation.
    box_slots: list[_FacilitySlot] = []
    for box_index in range(MAX_BOX_SLOTS):
        active = model.NewBoolVar(f"box_active__{box_index}")
        box_slots.append(
            _create_facility_slot(
                model,
                key=f"normalized_protocol_box::{box_index}",
                template="protocol_storage_box",
                operation_type="generic_input_provider",
                group_id=None,
                slot_index=box_index,
                domain=domains["protocol_storage_box"],
                needs_power=True,
                active=active,
            )
        )
    box_symmetry_constraints = _add_active_prefix_strict_order(model, box_slots)
    box_count = model.NewIntVar(0, MAX_BOX_SLOTS, "normalized_box_count")
    model.Add(box_count == sum(slot.active for slot in box_slots))

    pole_slots: list[_PoleSlot] = []
    for pole_index in range(MAX_POLE_SLOTS):
        active = model.NewBoolVar(f"pole_active__{pole_index}")
        x = model.NewIntVar(0, 68, f"pole_x__{pole_index}")
        y = model.NewIntVar(0, 68, f"pole_y__{pole_index}")
        model.Add(x == 0).OnlyEnforceIf(active.Not())
        model.Add(y == 0).OnlyEnforceIf(active.Not())
        x_end = model.NewIntVar(2, 70, f"pole_x_end__{pole_index}")
        y_end = model.NewIntVar(2, 70, f"pole_y_end__{pole_index}")
        model.Add(x_end == x + 2)
        model.Add(y_end == y + 2)
        x_interval = model.NewOptionalIntervalVar(x, 2, x_end, active, f"pole_x_iv__{pole_index}")
        y_interval = model.NewOptionalIntervalVar(y, 2, y_end, active, f"pole_y_iv__{pole_index}")
        order = model.NewIntVar(0, 68 * 69 + 68, f"pole_order__{pole_index}")
        model.Add(order == x * 69 + y)
        pole_slots.append(
            _PoleSlot(
                index=pole_index,
                active=active,
                x=x,
                y=y,
                order=order,
                x_interval=x_interval,
                y_interval=y_interval,
            )
        )
    pole_symmetry_constraints = _add_active_prefix_strict_order(model, pole_slots)
    pole_count = model.NewIntVar(0, MAX_POLE_SLOTS, "normalized_pole_count")
    model.Add(pole_count == sum(slot.active for slot in pole_slots))
    model.Add(pole_count <= EXPECTED_MANDATORY_POWERED + box_count)

    ghost_x = model.NewIntVar(0, GRID_W - ghost_w, "ghost_x")
    ghost_y = model.NewIntVar(0, GRID_H - ghost_h, "ghost_y")
    ghost_x_end = model.NewIntVar(ghost_w, GRID_W, "ghost_x_end")
    ghost_y_end = model.NewIntVar(ghost_h, GRID_H, "ghost_y_end")
    model.Add(ghost_x_end == ghost_x + ghost_w)
    model.Add(ghost_y_end == ghost_y + ghost_h)
    ghost_x_interval = model.NewIntervalVar(ghost_x, ghost_w, ghost_x_end, "ghost_x_iv")
    ghost_y_interval = model.NewIntervalVar(ghost_y, ghost_h, ghost_y_end, "ghost_y_iv")

    facility_body_slots = [*mandatory_slots, *box_slots]
    body_x_intervals = [slot.x_interval for slot in facility_body_slots] + [
        slot.x_interval for slot in pole_slots
    ]
    body_y_intervals = [slot.y_interval for slot in facility_body_slots] + [
        slot.y_interval for slot in pole_slots
    ]
    model.AddNoOverlap2D(
        [*body_x_intervals, ghost_x_interval],
        [*body_y_intervals, ghost_y_interval],
    )

    mandatory_area = sum(
        int(next(iter({int(m["width"]) * int(m["height"]) for m in slot.modes.values()})))
        for slot in mandatory_slots
    )
    if mandatory_area != EXPECTED_MANDATORY_AREA:
        raise AssertionError(f"mandatory area drift: {mandatory_area}")
    box_area = 9
    pole_area = 4
    model.Add(
        mandatory_area
        + box_area * box_count
        + pole_area * pole_count
        + ghost_w * ghost_h
        <= GRID_W * GRID_H
    )

    # Every powered body designates one selected active pole.  Optional box
    # witnesses are guarded by box activity.
    power_witnesses: list[dict[str, Any]] = []

    for powered_slot in powered_mandatory_slots:
        power_witnesses.append(
            _add_designated_power_witness(model, slot=powered_slot, pole_slots=pole_slots)
        )
    for box_slot in box_slots:
        power_witnesses.append(
            _add_designated_power_witness(model, slot=box_slot, pole_slots=pole_slots)
        )

    front_witnesses: list[dict[str, Any]] = []
    strict_front_order_roles = 0
    strict_front_order_constraints = 0
    front_table_rows = 0

    def add_fixed_role(slot: _FacilitySlot, role: str, demand: int) -> None:
        nonlocal strict_front_order_roles, strict_front_order_constraints, front_table_rows
        if demand <= 0:
            return
        rows: list[list[int]] = []
        code = 0
        for mode_id, payload in sorted(slot.modes.items()):
            candidates = list(payload[role])
            if len(candidates) < demand:
                raise AssertionError(f"candidate deficit: {slot.key}/{role}/{mode_id}")
            for dx, dy, _direction in candidates:
                rows.append([mode_id, code, int(dx), int(dy)])
                code += 1
        front_table_rows += len(rows)
        keys = []
        for ordinal in range(demand):
            prefix = f"front__{slot.key}__{role}__{ordinal}"
            key = model.NewIntVar(0, code - 1, f"key__{prefix}")
            dx = model.NewIntVar(min(row[2] for row in rows), max(row[2] for row in rows), f"dx__{prefix}")
            dy = model.NewIntVar(min(row[3] for row in rows), max(row[3] for row in rows), f"dy__{prefix}")
            model.AddAllowedAssignments([slot.mode, key, dx, dy], rows)
            front_x = model.NewIntVar(0, GRID_W - 1, f"x__{prefix}")
            front_y = model.NewIntVar(0, GRID_H - 1, f"y__{prefix}")
            model.Add(front_x == slot.x + dx)
            model.Add(front_y == slot.y + dy)
            _add_point_no_overlap(
                model,
                body_x_intervals,
                body_y_intervals,
                front_x,
                front_y,
                prefix,
            )
            keys.append(key)
            front_witnesses.append(
                {
                    "kind": "fixed",
                    "slot": slot,
                    "role": role,
                    "ordinal": ordinal,
                    "key": key,
                    "x": front_x,
                    "y": front_y,
                    "owner": None,
                }
            )
        if len(keys) > 1:
            strict_front_order_roles += 1
            for left, right in zip(keys, keys[1:]):
                model.Add(left < right)
                strict_front_order_constraints += 1

    fixed_input_total = 0
    fixed_output_total = 0
    core_slots: list[_FacilitySlot] = []
    for group in groups:
        group_id = str(group["group_id"])
        demand_in, demand_out = _fixed_demand(str(group["operation_type"]))
        fixed_input_total += int(group["count"]) * demand_in
        fixed_output_total += int(group["count"]) * demand_out
        for slot in slots_by_group[group_id]:
            add_fixed_role(slot, "input", demand_in)
            add_fixed_role(slot, "output", demand_out)
            if slot.template == "protocol_core":
                core_slots.append(slot)
    if len(core_slots) != 1:
        raise AssertionError("expected exactly one protocol core slot")

    # The two required generic commodities retain their live labels and select
    # distinct physical input ports from the core or either active box.  There is
    # deliberately no provider-order symmetry between the commodities.
    generic_providers = [core_slots[0], *box_slots]
    generic_encoding = _add_generic_input_witnesses(
        model,
        providers=generic_providers,
        commodities=GENERIC_INPUT_COMMODITIES,
        body_x_intervals=body_x_intervals,
        body_y_intervals=body_y_intervals,
    )
    front_table_rows += generic_encoding.table_row_count
    front_witnesses.extend(generic_encoding.witnesses)

    routing_in = fixed_input_total + GENERIC_INPUT_DEMAND
    routing_out = fixed_output_total
    routing_total = routing_in + routing_out
    if (fixed_input_total, routing_in, routing_out, routing_total) != (310, 312, 316, 628):
        raise AssertionError(
            f"routing ledger drift: fixed_in={fixed_input_total}, in={routing_in}, "
            f"out={routing_out}, total={routing_total}"
        )
    if len(front_witnesses) != routing_total:
        raise AssertionError("front witness count drift")

    max_body_slots = len(body_x_intervals)
    front_body_reference_count = len(front_witnesses) * max_body_slots
    generic_route_contract = {
        "input_requirements": generic_input_requirements,
        "output_requirements": generic_output_requirements,
        "input_provider_operations": {
            "box_sink": {
                "facility_type": "protocol_storage_box",
                "generic_input_capacity": 3,
            },
            "protocol_core": {
                "facility_type": "protocol_core",
                "generic_input_capacity": 14,
            },
        },
        "output_provider_operations": {
            "boundary_io": {
                "facility_type": "boundary_storage_port",
                "generic_output_capacity": 1,
            },
            "protocol_core": {
                "facility_type": "protocol_core",
                "generic_output_capacity": 6,
            },
        },
        "mandatory_output_capacity": 52,
        "mandatory_output_demand": sum(generic_output_requirements.values()),
        "mandatory_outputs_saturate": sum(generic_output_requirements.values()) == 52,
        "retained_optional_input_provider_templates": ["protocol_storage_box"],
        "retained_optional_output_provider_templates": [],
    }
    oracle_contract = {
        "input_hashes": input_hashes,
        "pool_total": domain_audit["pool_total"],
        "mode_total": domain_audit["mode_total"],
        "pool_counts": domain_audit["pool_counts"],
        "mode_domains": domain_audit["mode_domains"],
        "mandatory_instances": len(mandatory_slots),
        "mandatory_groups": len(groups),
        "mandatory_powered": len(powered_mandatory_slots),
        "mandatory_area": mandatory_area,
        "routing_in": routing_in,
        "routing_out": routing_out,
        "routing_total": routing_total,
        "operation_front_ledger": operation_front_ledger,
        "generic_route_contract": generic_route_contract,
        "max_box_slots": len(box_slots),
        "max_pole_slots": len(pole_slots),
        "max_body_slots": max_body_slots,
        "front_body_reference_count": front_body_reference_count,
        "front_semantics": "stored_port_identity",
        "identity_sentinel_pass": True,
        "edge_oob_pose_counts": _edge_oob_pose_counts(pools),
        "ghost_w": ghost_w,
        "ghost_h": ghost_h,
        "ghost_anchor_count": (GRID_W - ghost_w + 1) * (GRID_H - ghost_h + 1),
    }
    audit = {
        "encoding": "round45_identity_front_compact_coordinate_v1",
        "oracle_contract": oracle_contract,
        "vars": len(model.Proto().variables),
        "constraints": len(model.Proto().constraints),
        "facility_strict_order_constraints": facility_strict_order_constraints,
        "box_active_prefix_constraints": box_symmetry_constraints,
        "box_active_usage_constraints": len(box_slots),
        "box_strict_order_constraints": box_symmetry_constraints,
        "pole_active_prefix_constraints": pole_symmetry_constraints,
        "pole_strict_order_constraints": pole_symmetry_constraints,
        "strict_front_order_roles": strict_front_order_roles,
        "strict_front_order_constraints": strict_front_order_constraints,
        "front_table_rows": front_table_rows,
        "front_witness_count": len(front_witnesses),
        "front_no_overlap_count": len(front_witnesses),
        "power_designated_coverer_count": len(power_witnesses),
        "area_dominance": {
            "mandatory_area": mandatory_area,
            "box_area": box_area,
            "pole_area": pole_area,
            "ghost_area": ghost_w * ghost_h,
        },
        "sound_symmetry": {
            "mandatory_groups": (
                "identical modeled slots are relabeled by injective (x,y,mode) order; "
                "equality already violates body NoOverlap2D"
            ),
            "boxes": (
                "the at-most-two retained provider bodies are interchangeable even though the "
                "two commodity witnesses remain labeled; relabel bodies and their attached "
                "witnesses into active-prefix strict order"
            ),
            "poles": (
                "retained poles are interchangeable; relabel poles and designated coverer "
                "indices into active-prefix strict anchor order"
            ),
            "front_witnesses": (
                "only repeated fixed-slot role witnesses are sorted; the two generic commodity "
                "witnesses are labeled and have only a distinct physical-key constraint"
            ),
        },
        "normal_form": {
            "boxes": (
                "keep only boxes carrying either of the two required generic inputs; their union "
                "has cardinality at most two"
            ),
            "poles": (
                "keep one live covering pole per retained powered body and take their union; "
                "there are at most 219 + active_boxes retained poles"
            ),
        },
    }
    snapshot = {
        "project_root": project_root,
        "input_paths": input_paths,
        "input_hashes": input_hashes,
        "pools": pools,
        "instances": instances,
        "rules": rules,
        "domains": domains,
    }
    handles = {
        "groups": groups,
        "slots_by_group": slots_by_group,
        "mandatory_slots": mandatory_slots,
        "powered_mandatory_slots": powered_mandatory_slots,
        "core_slot": core_slots[0],
        "box_slots": box_slots,
        "box_count": box_count,
        "pole_slots": pole_slots,
        "pole_count": pole_count,
        "ghost_x": ghost_x,
        "ghost_y": ghost_y,
        "ghost_w": ghost_w,
        "ghost_h": ghost_h,
        "front_witnesses": front_witnesses,
        "power_witnesses": power_witnesses,
    }
    return BuildResult(model=model, handles=handles, audit=audit, snapshot=snapshot)


def configure_strict_lean(
    solver: Any, time_limit: float, seed: int, workers: int = 1
) -> dict[str, Any]:
    """Apply the exact historical one-worker strict/lean CP-SAT profile."""

    if not 0 < float(time_limit) <= 1200:
        raise ValueError("time_limit must be in (0,1200]")
    if int(workers) != 1:
        raise ValueError("strict_lean is a reproducible one-worker profile")
    values: dict[str, Any] = {
        "max_time_in_seconds": float(time_limit),
        "num_search_workers": int(workers),
        "random_seed": int(seed),
        "log_search_progress": True,
        "log_to_stdout": False,
        "max_memory_in_mb": 10_000,
        "cp_model_probing_level": 0,
        "probing_deterministic_time_limit": 0.05,
        "max_presolve_iterations": 1,
        "linearization_level": 0,
        "merge_no_overlap_work_limit": 0.0,
    }
    for name, value in values.items():
        if name == "max_memory_in_mb" and not hasattr(solver.parameters, name):
            continue
        setattr(solver.parameters, name, value)
    return values


def _slot_pose_index(slot: _FacilitySlot, solver: Any) -> int:
    pose_tuple = (
        int(solver.Value(slot.x)),
        int(solver.Value(slot.y)),
        int(solver.Value(slot.mode)),
    )
    try:
        return int(slot.tuple_to_pose[pose_tuple])
    except KeyError as exc:
        raise AssertionError(f"compact tuple absent from pinned pool: {slot.key} {pose_tuple}") from exc


def extract_solution(build: BuildResult, solver: Any) -> dict[str, Any]:
    """Extract a relaxation solution; call only after FEASIBLE/OPTIMAL."""

    pools = build.snapshot["pools"]
    mandatory: dict[str, Any] = {}
    for group in build.handles["groups"]:
        slots = build.handles["slots_by_group"][str(group["group_id"])]
        for instance_id, slot in zip(group["instance_ids"], slots):
            pose_index = _slot_pose_index(slot, solver)
            pose = pools[slot.template][pose_index]
            mandatory[str(instance_id)] = {
                "facility_type": slot.template,
                "operation_type": slot.operation_type,
                "slot_index": slot.slot_index,
                "pose_idx": pose_index,
                "pose_id": str(pose["pose_id"]),
                "anchor": {"x": int(solver.Value(slot.x)), "y": int(solver.Value(slot.y))},
                "mode": int(solver.Value(slot.mode)),
                "order": int(solver.Value(slot.order)),
            }

    boxes = []
    for slot in build.handles["box_slots"]:
        if int(solver.Value(slot.active)) != 1:
            continue
        pose_index = _slot_pose_index(slot, solver)
        pose = pools[slot.template][pose_index]
        boxes.append(
            {
                "slot_index": slot.slot_index,
                "pose_idx": pose_index,
                "pose_id": str(pose["pose_id"]),
                "anchor": {"x": int(solver.Value(slot.x)), "y": int(solver.Value(slot.y))},
                "mode": int(solver.Value(slot.mode)),
                "order": int(solver.Value(slot.order)),
            }
        )

    poles = [
        {
            "slot_index": slot.index,
            "x": int(solver.Value(slot.x)),
            "y": int(solver.Value(slot.y)),
            "order": int(solver.Value(slot.order)),
        }
        for slot in build.handles["pole_slots"]
        if int(solver.Value(slot.active)) == 1
    ]
    fronts = []
    for record in build.handles["front_witnesses"]:
        item = {
            "kind": record["kind"],
            "role": record["role"],
            "ordinal": int(record["ordinal"]),
            "candidate_key": int(solver.Value(record["key"])),
            "x": int(solver.Value(record["x"])),
            "y": int(solver.Value(record["y"])),
        }
        if record["slot"] is not None:
            item["slot_key"] = record["slot"].key
        if record["owner"] is not None:
            item["provider_index"] = int(solver.Value(record["owner"]))
        if "commodity" in record:
            item["commodity"] = str(record["commodity"])
        fronts.append(item)

    power = []
    for record in build.handles["power_witnesses"]:
        slot = record["slot"]
        if slot.active is not None and int(solver.Value(slot.active)) != 1:
            continue
        power.append(
            {
                "slot_key": slot.key,
                "pole_slot_index": int(solver.Value(record["index"])),
            }
        )
    return {
        "semantics": build.audit["oracle_contract"]["front_semantics"],
        "input_hashes": dict(build.snapshot["input_hashes"]),
        "mandatory": mandatory,
        "boxes": boxes,
        "poles": poles,
        "ghost": {
            "x": int(solver.Value(build.handles["ghost_x"])),
            "y": int(solver.Value(build.handles["ghost_y"])),
            "w": int(build.handles["ghost_w"]),
            "h": int(build.handles["ghost_h"]),
        },
        "front_witnesses": fronts,
        "power_witnesses": power,
    }


def validate_solution(build: BuildResult, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Re-evaluate every extracted predicate without consulting solver values."""

    violations: list[dict[str, Any]] = []
    pools = build.snapshot["pools"]
    instances = build.snapshot["instances"]
    instance_by_id = {str(item["instance_id"]): item for item in instances}
    if payload.get("semantics") != build.audit["oracle_contract"]["front_semantics"]:
        violations.append({"check": "front_semantics"})
    if dict(payload.get("input_hashes", {})) != dict(build.snapshot["input_hashes"]):
        violations.append({"check": "input_hashes"})

    slot_by_instance: dict[str, _FacilitySlot] = {}
    for group in build.handles["groups"]:
        slots = build.handles["slots_by_group"][str(group["group_id"])]
        slot_by_instance.update(zip(group["instance_ids"], slots))

    mandatory_payload = dict(payload.get("mandatory", {}))
    if set(mandatory_payload) != set(instance_by_id):
        violations.append(
            {
                "check": "mandatory_coverage",
                "missing": sorted(set(instance_by_id) - set(mandatory_payload)),
                "extra": sorted(set(mandatory_payload) - set(instance_by_id)),
            }
        )

    occupancy: dict[tuple[int, int], str] = {}
    selected_pose_by_slot: dict[str, Mapping[str, Any]] = {}
    selected_mode_by_slot: dict[str, int] = {}
    selected_anchor_by_slot: dict[str, tuple[int, int]] = {}
    selected_body_by_slot: dict[str, set[tuple[int, int]]] = {}

    def add_body(owner: str, slot_key: str, cells: Iterable[tuple[int, int]]) -> None:
        body = set(cells)
        selected_body_by_slot[slot_key] = body
        for cell in body:
            if not (0 <= cell[0] < GRID_W and 0 <= cell[1] < GRID_H):
                violations.append({"check": "body_in_grid", "owner": owner, "cell": list(cell)})
            previous = occupancy.get(cell)
            if previous is not None:
                violations.append(
                    {"check": "body_overlap", "cell": list(cell), "owners": [previous, owner]}
                )
            occupancy[cell] = owner

    def actual_mode(slot: _FacilitySlot, pose: Mapping[str, Any]) -> int | None:
        token = _mode_token(pose)
        matches = [mode_id for mode_id, mode in slot.modes.items() if mode["token"] == token]
        return matches[0] if len(matches) == 1 else None

    for instance_id, record in mandatory_payload.items():
        instance = instance_by_id.get(str(instance_id))
        slot = slot_by_instance.get(str(instance_id))
        if instance is None or slot is None:
            continue
        template = str(instance["facility_type"])
        if (
            str(record.get("facility_type")) != template
            or str(record.get("operation_type")) != str(instance["operation_type"])
        ):
            violations.append({"check": "mandatory_identity", "instance": instance_id})
        pose_index = int(record.get("pose_idx", -1))
        if not 0 <= pose_index < len(pools[template]):
            violations.append({"check": "pose_index", "instance": instance_id})
            continue
        pose = pools[template][pose_index]
        anchor = _cell_xy(pose["anchor"])
        mode_id = actual_mode(slot, pose)
        reported_anchor = dict(record.get("anchor", {}))
        if (
            str(record.get("pose_id")) != str(pose["pose_id"])
            or (int(reported_anchor.get("x", -1)), int(reported_anchor.get("y", -1))) != anchor
            or mode_id is None
            or int(record.get("mode", -1)) != mode_id
            or slot.tuple_to_pose.get((anchor[0], anchor[1], int(mode_id or 0))) != pose_index
            or int(record.get("order", -1))
            != anchor[0] * (GRID_H * len(slot.modes))
            + anchor[1] * len(slot.modes)
            + int(mode_id or 0)
        ):
            violations.append({"check": "mandatory_compact_tuple", "instance": instance_id})
        selected_pose_by_slot[slot.key] = pose
        selected_mode_by_slot[slot.key] = int(mode_id if mode_id is not None else -1)
        selected_anchor_by_slot[slot.key] = anchor
        add_body(str(instance_id), slot.key, (_cell_xy(cell) for cell in pose["occupied_cells"]))

    for group in build.handles["groups"]:
        records = [mandatory_payload.get(instance_id, {}) for instance_id in group["instance_ids"]]
        orders = [int(record.get("order", -1)) for record in records]
        if any(left >= right for left, right in zip(orders, orders[1:])):
            violations.append({"check": "mandatory_group_strict_order", "group": group["group_id"]})

    boxes = list(payload.get("boxes", []))
    if len(boxes) > MAX_BOX_SLOTS:
        violations.append({"check": "box_count", "count": len(boxes)})
    active_box_indices = [int(item.get("slot_index", -1)) for item in boxes]
    if active_box_indices != list(range(len(boxes))):
        violations.append({"check": "box_active_prefix"})
    box_orders: list[int] = []
    for item in boxes:
        slot_index = int(item.get("slot_index", -1))
        if not 0 <= slot_index < len(build.handles["box_slots"]):
            violations.append({"check": "box_slot_index", "slot_index": slot_index})
            continue
        slot = build.handles["box_slots"][slot_index]
        pose_index = int(item.get("pose_idx", -1))
        if not 0 <= pose_index < len(pools[slot.template]):
            violations.append({"check": "box_pose_index", "pose_idx": pose_index})
            continue
        pose = pools[slot.template][pose_index]
        anchor = _cell_xy(pose["anchor"])
        mode_id = actual_mode(slot, pose)
        reported_anchor = dict(item.get("anchor", {}))
        if (
            str(item.get("pose_id")) != str(pose["pose_id"])
            or (int(reported_anchor.get("x", -1)), int(reported_anchor.get("y", -1))) != anchor
            or mode_id is None
            or int(item.get("mode", -1)) != mode_id
            or slot.tuple_to_pose.get((anchor[0], anchor[1], int(mode_id or 0))) != pose_index
            or int(item.get("order", -1))
            != anchor[0] * (GRID_H * len(slot.modes))
            + anchor[1] * len(slot.modes)
            + int(mode_id or 0)
        ):
            violations.append({"check": "box_compact_tuple", "slot_index": slot_index})
        selected_pose_by_slot[slot.key] = pose
        selected_mode_by_slot[slot.key] = int(mode_id if mode_id is not None else -1)
        selected_anchor_by_slot[slot.key] = anchor
        add_body(
            f"box::{slot_index}",
            slot.key,
            (_cell_xy(cell) for cell in pose["occupied_cells"]),
        )
        box_orders.append(int(item.get("order", -1)))
    if any(left >= right for left, right in zip(box_orders, box_orders[1:])):
        violations.append({"check": "box_strict_order"})

    poles = list(payload.get("poles", []))
    if len(poles) > MAX_POLE_SLOTS or len(poles) > EXPECTED_MANDATORY_POWERED + len(boxes):
        violations.append({"check": "pole_count", "count": len(poles)})
    if [int(item.get("slot_index", -1)) for item in poles] != list(range(len(poles))):
        violations.append({"check": "pole_active_prefix"})
    pole_orders: list[int] = []
    pole_by_index: dict[int, tuple[int, int]] = {}
    for item in poles:
        slot_index = int(item.get("slot_index", -1))
        x = int(item.get("x", -1))
        y = int(item.get("y", -1))
        if not (0 <= x <= 68 and 0 <= y <= 68):
            violations.append({"check": "pole_anchor", "anchor": [x, y]})
            continue
        expected_order = x * 69 + y
        if int(item.get("order", -1)) != expected_order:
            violations.append({"check": "pole_order", "slot_index": slot_index})
        pole_by_index[slot_index] = (x, y)
        pole_orders.append(expected_order)
        add_body(
            f"pole::{slot_index}",
            f"pole::{slot_index}",
            ((px, py) for px in range(x, x + 2) for py in range(y, y + 2)),
        )
    if any(left >= right for left, right in zip(pole_orders, pole_orders[1:])):
        violations.append({"check": "pole_strict_order"})

    ghost = dict(payload.get("ghost", {}))
    gx = int(ghost.get("x", -1))
    gy = int(ghost.get("y", -1))
    gw = int(ghost.get("w", -1))
    gh = int(ghost.get("h", -1))
    if (gw, gh) != (build.handles["ghost_w"], build.handles["ghost_h"]):
        violations.append({"check": "ghost_shape", "shape": [gw, gh]})
    if not (0 <= gx <= GRID_W - gw and 0 <= gy <= GRID_H - gh):
        violations.append({"check": "ghost_bounds", "anchor": [gx, gy]})
    ghost_cells = {
        (x, y) for x in range(gx, gx + max(gw, 0)) for y in range(gy, gy + max(gh, 0))
    }
    ghost_hits = sorted(ghost_cells & set(occupancy))
    if ghost_hits:
        violations.append({"check": "ghost_body_overlap", "sample": ghost_hits[:5]})

    def candidate_rows(slot: _FacilitySlot, role: str) -> dict[int, tuple[int, int, int]]:
        result: dict[int, tuple[int, int, int]] = {}
        code = 0
        for mode_id, mode in sorted(slot.modes.items()):
            for dx, dy, _direction in mode[role]:
                result[code] = (mode_id, int(dx), int(dy))
                code += 1
        return result

    expected_fronts = list(build.handles["front_witnesses"])
    fronts = list(payload.get("front_witnesses", []))
    if len(fronts) != len(expected_fronts):
        violations.append({"check": "front_witness_count", "count": len(fronts)})
    fixed_keys: dict[tuple[str, str], list[int]] = defaultdict(list)
    generic_keys: list[int] = []
    used_box_indices: set[int] = set()
    generic_candidate_rows: dict[tuple[int, int], tuple[int, int, int]] = {}
    generic_code = 0
    generic_providers = expected_fronts[-1]["providers"]
    for provider_index, provider in enumerate(generic_providers):
        for mode_id, mode in sorted(provider.modes.items()):
            for dx, dy, _direction in mode["input"]:
                generic_candidate_rows[(provider_index, generic_code)] = (
                    mode_id,
                    int(dx),
                    int(dy),
                )
                generic_code += 1
    for index, (front, expected) in enumerate(zip(fronts, expected_fronts)):
        x = int(front.get("x", -1))
        y = int(front.get("y", -1))
        key = int(front.get("candidate_key", -1))
        if (
            str(front.get("kind")) != expected["kind"]
            or str(front.get("role")) != expected["role"]
            or int(front.get("ordinal", -1)) != int(expected["ordinal"])
        ):
            violations.append({"check": "front_identity", "index": index})

        if expected["kind"] == "fixed":
            slot = expected["slot"]
            if str(front.get("slot_key")) != slot.key:
                violations.append({"check": "front_slot_key", "index": index})
            rows = candidate_rows(slot, str(expected["role"]))
            row = rows.get(key)
            mode_id = selected_mode_by_slot.get(slot.key)
            anchor = selected_anchor_by_slot.get(slot.key)
            if row is None or anchor is None or mode_id != row[0]:
                violations.append({"check": "fixed_candidate_key", "index": index})
            elif (x, y) != (anchor[0] + row[1], anchor[1] + row[2]):
                violations.append({"check": "fixed_candidate_coordinate", "index": index})
            fixed_keys[(slot.key, str(expected["role"]))].append(key)
        else:
            commodity = str(expected["commodity"])
            provider_index = int(front.get("provider_index", -1))
            if str(front.get("commodity")) != commodity:
                violations.append({"check": "generic_commodity", "index": index})
            providers = expected["providers"]
            if not 0 <= provider_index < len(providers):
                violations.append({"check": "generic_provider_index", "index": index})
            else:
                provider = providers[provider_index]
                row = generic_candidate_rows.get((provider_index, key))
                anchor = selected_anchor_by_slot.get(provider.key)
                mode_id = selected_mode_by_slot.get(provider.key)
                if row is None or anchor is None or mode_id != row[0]:
                    violations.append({"check": "generic_candidate_key", "index": index})
                elif (x, y) != (anchor[0] + row[1], anchor[1] + row[2]):
                    violations.append({"check": "generic_candidate_coordinate", "index": index})
                if provider_index > 0:
                    used_box_indices.add(provider_index - 1)
            generic_keys.append(key)

        if not (0 <= x < GRID_W and 0 <= y < GRID_H) or (x, y) in occupancy:
            violations.append(
                {"check": "front_witness_body_clear", "index": index, "cell": [x, y]}
            )

    for (slot_key, role), keys in fixed_keys.items():
        if len(keys) != len(set(keys)) or any(
            left >= right for left, right in zip(keys, keys[1:])
        ):
            violations.append(
                {
                    "check": "fixed_candidate_keys_strict_order",
                    "slot_key": slot_key,
                    "role": role,
                }
            )
    if len(generic_keys) != GENERIC_INPUT_DEMAND or len(set(generic_keys)) != len(generic_keys):
        violations.append({"check": "generic_candidate_keys_distinct"})
    if used_box_indices != set(active_box_indices):
        violations.append(
            {
                "check": "box_active_iff_generic_use",
                "active": active_box_indices,
                "used": sorted(used_box_indices),
            }
        )

    expected_power_slots = {
        slot.key for slot in build.handles["powered_mandatory_slots"]
    } | {
        build.handles["box_slots"][index].key
        for index in active_box_indices
        if 0 <= index < len(build.handles["box_slots"])
    }
    power_payload = list(payload.get("power_witnesses", []))
    actual_power_slots = [str(item.get("slot_key")) for item in power_payload]
    if set(actual_power_slots) != expected_power_slots or len(actual_power_slots) != len(
        set(actual_power_slots)
    ):
        violations.append({"check": "power_witness_coverage"})
    for record in power_payload:
        slot_key = str(record.get("slot_key"))
        pole_index = int(record.get("pole_slot_index", -1))
        body = selected_body_by_slot.get(slot_key)
        pole = pole_by_index.get(pole_index)
        if body is None or pole is None or not any(
            pole[0] - 5 <= x <= pole[0] + 6 and pole[1] - 5 <= y <= pole[1] + 6
            for x, y in body
        ):
            violations.append(
                {"check": "designated_power_coverage", "slot_key": slot_key, "pole": pole_index}
            )

    occupied_area = EXPECTED_MANDATORY_AREA + 9 * len(boxes) + 4 * len(poles)
    if occupied_area + max(gw, 0) * max(gh, 0) > GRID_W * GRID_H:
        violations.append({"check": "area_dominance"})

    return {
        "ok": not violations,
        "violations": violations,
        "counts": {
            "mandatory": len(mandatory_payload),
            "boxes": len(boxes),
            "poles": len(pole_by_index),
            "front_witnesses": len(fronts),
            "power_witnesses": len(power_payload),
            "occupied_body_cells": len(occupancy),
        },
    }


__all__ = [
    "BuildResult",
    "build_compact_model",
    "configure_strict_lean",
    "extract_solution",
    "validate_solution",
]
