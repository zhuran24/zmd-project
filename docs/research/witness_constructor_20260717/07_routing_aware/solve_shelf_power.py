"""Restricted group-by-pose CP-SAT for the first shelf witness geometry.

The model searches only current candidate-pool poses whose bodies avoid the
fixed directed shelf network and whose operation-required fronts lie on that
network.  Power poles are selected jointly with manufacturing poses.  This is
research search machinery; its output is re-materialized and independently
checked by :mod:`shelf_constructor` before use.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import importlib
from itertools import product
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from ortools.sat.python import cp_model


_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

geometry = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.geometry"
)
shelf = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.shelf_constructor"
)
cgroup_telemetry = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.cgroup_telemetry"
)

Cell = tuple[int, int]
Anchor = tuple[int, int]
DirectedEdge = tuple[Cell, Cell]

PROTECTED_RECT = shelf.SHELF_PROTECTED_RECT
PHASE_BY_BODY_Y = {
    2: "north_to_south",
    6: "south_to_north",
    11: "north_to_south",
    15: "south_to_north",
    21: "north_to_south",
    25: "south_to_north",
    30: "north_to_south",
    34: "south_to_north",
    40: "north_to_south",
    44: "south_to_north",
    49: "north_to_south",
    53: "south_to_north",
    59: "north_to_south",
    64: "south_to_north",
}
MIN_POLES = 9
MAX_POLES_FROM_FREE_AREA = 38
POLE_DOMAIN_MODE = "full"
POLE_DOMAIN_ROWS = frozenset({6, 15, 25, 34, 44, 53, 59, 64})
MINI_EW_MODE_BY_ANCHOR: Mapping[Anchor, str] = {}
_DIRECTIONS = ("N", "E", "S", "W")
_DIRECTION_DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
_OPPOSITE = {"N": "S", "E": "W", "S": "N", "W": "E"}


@dataclass(frozen=True)
class PoseCandidate:
    template: str
    mode: str
    anchor: Anchor
    pose_idx: int
    body_cells: frozenset[Cell]
    input_front_cells: tuple[Cell, ...]
    output_front_cells: tuple[Cell, ...]


@dataclass(frozen=True)
class ModelStats:
    network_edges: int
    network_cells: int
    protected_cells: int
    fixed_body_cells: int
    geometry_pose_count: int
    group_pose_var_count: int
    pole_var_count: int
    cell_constraint_count: int
    power_constraint_count: int
    fixed_power_constraint_count: int
    component_presence_var_count: int
    component_table_constraint_count: int
    component_static_audit_cell_count: int
    component_static_audit_state_count: int
    component_allowed_row_count: int
    fixed_terminal_count: int
    pole_domain_mode: str
    group_domain_sizes: Mapping[str, int]


@dataclass(frozen=True)
class ShelfPowerSolveResult:
    status: str
    manufacturing_slots: tuple[Any, ...]
    pole_anchors: tuple[Anchor, ...]
    pole_bay_anchors: tuple[Anchor, ...]
    protected_rect: Any
    network_edges: frozenset[DirectedEdge]
    stats: Mapping[str, Any]


@dataclass
class ShelfPowerModel:
    model: Any
    candidates: tuple[PoseCandidate, ...]
    groups: tuple[Mapping[str, Any], ...]
    group_vars: dict[tuple[str, int], Any]
    occupancy_vars: dict[int, Any]
    pole_anchors: tuple[Anchor, ...]
    pole_vars: dict[int, Any]
    network_edges: frozenset[DirectedEdge]
    bundle: Any
    stats: ModelStats
    operation_expansion: Mapping[str, tuple[str, ...]]


def exact_network_edges() -> frozenset[DirectedEdge]:
    return shelf.routing_aware_network_edges()


def _fixed_body_cells(instance: Mapping[str, Any]) -> set[Cell]:
    boundary_ids = [
        str(required["id"])
        for required in instance["required_instances"]
        if required["template"] == "boundary_storage_port"
    ]
    boundary = geometry.place_boundary_instances(boundary_ids, shelf.FIXED_BOUNDARY_PATTERN)
    return set().union(*(placement.body_cells for placement in boundary)) | geometry.Rect(
        shelf.FIXED_CORE_ANCHOR[0], shelf.FIXED_CORE_ANCHOR[1], 9, 9
    ).cells


def _fixed_power_bodies(instance: Mapping[str, Any]) -> tuple[frozenset[Cell], ...]:
    """Materialize every fixed required body whose strict template needs power."""

    bodies: list[frozenset[Cell]] = []
    if instance["facility_templates"]["protocol_core"]["requires_power"]:
        mode = _strict_mode(instance, "protocol_core", "inputs_north_south")
        bodies.append(geometry.strict_mode_geometry(mode, shelf.FIXED_CORE_ANCHOR).body_cells)
    if instance["facility_templates"]["boundary_storage_port"]["requires_power"]:
        for slot in shelf._boundary_slots(instance):
            mode = _strict_mode(instance, slot.template, slot.mode)
            bodies.append(geometry.strict_mode_geometry(mode, slot.anchor).body_cells)
    return tuple(bodies)


def _pose_phase_is_legal(candidate: PoseCandidate) -> bool:
    if candidate.mode in {"east_to_west", "west_to_east"}:
        return (
            candidate.template == "manufacturing_3x3"
            and MINI_EW_MODE_BY_ANCHOR.get(candidate.anchor) == candidate.mode
        )
    body_y = min(y for _x, y in candidate.body_cells)
    return PHASE_BY_BODY_Y.get(body_y) == candidate.mode


def _enumerate_candidates(
    *,
    bundle: Any,
    instance: Mapping[str, Any],
    groups: Sequence[Mapping[str, Any]],
    network_cells: set[Cell],
    fixed_body: set[Cell],
) -> tuple[tuple[PoseCandidate, ...], dict[str, tuple[int, ...]], dict[str, int]]:
    pools = bundle.candidate_poses.value["facility_pools"]
    candidates: list[PoseCandidate] = []
    indices_by_template: dict[str, list[int]] = defaultdict(list)
    blocked = network_cells | fixed_body | set(PROTECTED_RECT.cells)
    for template in ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4"):
        for pose_idx, pose in enumerate(pools[template]):
            pose_geometry = geometry.candidate_pose_geometry(pose)
            if pose_geometry.body_cells & blocked:
                continue
            mode = shelf.strict_contract.CANDIDATE_MODE_TO_STRICT[
                str(pose["pose_params"]["port_mode"])
            ]
            candidate = PoseCandidate(
                template=template,
                mode=mode,
                anchor=(int(pose["anchor"]["x"]), int(pose["anchor"]["y"])),
                pose_idx=pose_idx,
                body_cells=pose_geometry.body_cells,
                input_front_cells=pose_geometry.input_front_cells,
                output_front_cells=pose_geometry.output_front_cells,
            )
            if not _pose_phase_is_legal(candidate):
                continue
            index = len(candidates)
            candidates.append(candidate)
            indices_by_template[template].append(index)

    group_domains: dict[str, tuple[int, ...]] = {}
    domain_sizes: dict[str, int] = {}
    for group in groups:
        operation = str(group["id"])
        need_inputs = sum(int(value) for value in group["port_needs"]["inputs"].values())
        need_outputs = sum(int(value) for value in group["port_needs"]["outputs"].values())
        domain = tuple(
            index
            for index in indices_by_template[str(group["template"])]
            if sum(cell in network_cells for cell in candidates[index].input_front_cells) >= need_inputs
            and sum(cell in network_cells for cell in candidates[index].output_front_cells) >= need_outputs
        )
        if len(domain) < int(group["count"]):
            raise shelf.ShelfConstructionError(
                "GROUP_DOMAIN_TOO_SMALL",
                f"{operation}: domain {len(domain)} < count {group['count']}",
            )
        group_domains[operation] = domain
        domain_sizes[operation] = len(domain)
    return tuple(candidates), group_domains, domain_sizes


def _aggregate_operation_signatures(
    instance: Mapping[str, Any],
) -> tuple[tuple[Mapping[str, Any], ...], Mapping[str, tuple[str, ...]]]:
    """Collapse operation labels that have identical geometry-side demands.

    Commodities do not affect body occupancy or the all-commodity shelf bus.
    Keeping one CP family per ``(template, input-count, output-count)`` removes
    label symmetry while preserving the exact strict operation multiplicities.
    Selected poses are expanded back to original operation IDs before the
    worker result is serialized and replayed.
    """

    counts: dict[tuple[str, int, int], int] = defaultdict(int)
    operations: dict[tuple[str, int, int], list[str]] = defaultdict(list)
    for group in instance["operation_groups"]:
        template = str(group["template"])
        input_count = sum(int(value) for value in group["port_needs"]["inputs"].values())
        output_count = sum(int(value) for value in group["port_needs"]["outputs"].values())
        key = (template, input_count, output_count)
        count = int(group["count"])
        counts[key] += count
        operations[key].extend([str(group["id"])] * count)

    groups: list[Mapping[str, Any]] = []
    expansion: dict[str, tuple[str, ...]] = {}
    for template, input_count, output_count in sorted(counts):
        signature = f"{template}__i{input_count}__o{output_count}"
        groups.append(
            {
                "id": signature,
                "template": template,
                "count": counts[(template, input_count, output_count)],
                "port_needs": {
                    "inputs": {"signature_input": input_count},
                    "outputs": {"signature_output": output_count},
                },
            }
        )
        expansion[signature] = tuple(operations[(template, input_count, output_count)])
    if len(groups) != 9 or sum(int(group["count"]) for group in groups) != 219:
        raise shelf.ShelfConstructionError(
            "OPERATION_SIGNATURE_SENTINEL",
            f"expected 9 signatures/219 bodies, observed {len(groups)}/{sum(int(group['count']) for group in groups)}",
        )
    return tuple(groups), expansion


def _collapse_template_domains(
    groups: Sequence[Mapping[str, Any]],
    group_domains: Mapping[str, tuple[int, ...]],
) -> tuple[dict[str, tuple[int, ...]], dict[str, int]]:
    """Prove and collapse geometry-equivalent signature domains.

    Operation signatures retain different active-port multiplicities, but the
    audited shelf exposes every physical port on every admitted pose.  The
    resulting candidate domain must therefore be byte-for-byte identical for
    all signatures of one manufacturing template.  Geometry and power depend
    only on the selected pose, so one Boolean family per template is exact for
    this layer; signatures are deterministically expanded after a geometry is
    found and the full component/commodity validator remains mandatory.
    """

    domains_by_template: dict[str, list[tuple[int, ...]]] = defaultdict(list)
    counts_by_template: dict[str, int] = defaultdict(int)
    for group in groups:
        operation = str(group["id"])
        template = str(group["template"])
        domains_by_template[template].append(group_domains[operation])
        counts_by_template[template] += int(group["count"])

    collapsed: dict[str, tuple[int, ...]] = {}
    for template, domains in sorted(domains_by_template.items()):
        reference = domains[0]
        if any(domain != reference for domain in domains[1:]):
            raise shelf.ShelfConstructionError(
                "SIGNATURE_DOMAIN_MISMATCH",
                f"{template}: operation signatures do not share one exact geometry domain",
            )
        collapsed[template] = reference
    if counts_by_template != {
        "manufacturing_3x3": 132,
        "manufacturing_5x5": 49,
        "manufacturing_6x4": 38,
    }:
        raise shelf.ShelfConstructionError(
            "TEMPLATE_COUNT_SENTINEL", repr(dict(sorted(counts_by_template.items())))
        )
    return collapsed, dict(counts_by_template)


def _enumerate_poles(
    *, bundle: Any, network_cells: set[Cell], fixed_body: set[Cell]
) -> tuple[Anchor, ...]:
    blocked = network_cells | fixed_body | set(PROTECTED_RECT.cells)
    anchors: list[Anchor] = []
    for pose in bundle.candidate_poses.value["facility_pools"]["power_pole"]:
        pose_geometry = geometry.candidate_pose_geometry(pose)
        anchor = (int(pose["anchor"]["x"]), int(pose["anchor"]["y"]))
        if pose_geometry.body_cells & blocked:
            continue
        if POLE_DOMAIN_MODE == "primary_even_rows" and (
            anchor[1] not in POLE_DOMAIN_ROWS or anchor[0] % 2 != 0
        ):
            continue
        if POLE_DOMAIN_MODE == "fallback_rows" and anchor[1] not in POLE_DOMAIN_ROWS:
            continue
        if POLE_DOMAIN_MODE not in {"primary_even_rows", "fallback_rows", "full"}:
            raise shelf.ShelfConstructionError("POLE_DOMAIN_MODE", repr(POLE_DOMAIN_MODE))
        anchors.append(anchor)
    return tuple(anchors)


def _pole_covers_body(anchor: Anchor, body: frozenset[Cell]) -> bool:
    min_x = min(x for x, _y in body)
    max_x = max(x for x, _y in body)
    min_y = min(y for _x, y in body)
    max_y = max(y for _x, y in body)
    return not (
        max_x < anchor[0] - 5
        or min_x > anchor[0] + 6
        or max_y < anchor[1] - 5
        or min_y > anchor[1] + 6
    )


def _edge_direction(source: Cell, target: Cell) -> str:
    delta = (target[0] - source[0], target[1] - source[1])
    for direction, expected in _DIRECTION_DELTA.items():
        if delta == expected:
            return direction
    raise shelf.ShelfConstructionError("NON_UNIT_NETWORK_EDGE", f"{source!r}->{target!r}")


def _port_access(anchor: Anchor, port: Mapping[str, Any]) -> Cell:
    body_cell = port["body_cell"]
    direction = str(port["direction"])
    dx, dy = _DIRECTION_DELTA[direction]
    return (
        anchor[0] + int(body_cell["x"]) + dx,
        anchor[1] + int(body_cell["y"]) + dy,
    )


def _strict_mode(
    instance: Mapping[str, Any], template: str, mode_id: str
) -> Mapping[str, Any]:
    matches = [
        mode
        for mode in instance["facility_templates"][template]["modes"]
        if mode["id"] == mode_id
    ]
    if len(matches) != 1:
        raise shelf.ShelfConstructionError(
            "STRICT_MODE_LOOKUP", f"{template}/{mode_id}: observed {len(matches)} modes"
        )
    return matches[0]


def _terminal_attachment(
    *, anchor: Anchor, port: Mapping[str, Any]
) -> tuple[Cell, str, str]:
    outward = str(port["direction"])
    component_side = _OPPOSITE[outward]
    component_kind = "input" if port["kind"] == "output" else "output"
    return (_port_access(anchor, port), component_kind, component_side)


def _manufacturing_attachments(
    *,
    instance: Mapping[str, Any],
    candidate: PoseCandidate,
    group: Mapping[str, Any],
    network_cells: set[Cell],
) -> tuple[tuple[Cell, str, str], ...]:
    """Mirror automatic binding's physical-port order for one group/pose."""

    mode = _strict_mode(instance, candidate.template, candidate.mode)
    needs = group["port_needs"]
    selected: list[Mapping[str, Any]] = []
    for kind in ("input", "output"):
        count = sum(int(value) for value in needs[f"{kind}s"].values())
        eligible = sorted(
            (
                port
                for port in mode["ports"]
                if port["kind"] == kind and _port_access(candidate.anchor, port) in network_cells
            ),
            key=lambda port: str(port["id"]),
        )
        if len(eligible) < count:
            raise shelf.ShelfConstructionError(
                "ACTIVE_PORT_DOMAIN",
                f"{group['id']} at {candidate.anchor}: {len(eligible)} {kind} ports for {count}",
            )
        selected.extend(eligible[:count])
    return tuple(_terminal_attachment(anchor=candidate.anchor, port=port) for port in selected)


def _fixed_terminal_attachments(
    instance: Mapping[str, Any], network_cells: set[Cell]
) -> tuple[tuple[Cell, str, str], ...]:
    """Return the deterministic 46 boundary + 8 protocol-core attachments."""

    attachments: list[tuple[Cell, str, str]] = []
    for slot in shelf._boundary_slots(instance):
        mode = _strict_mode(instance, slot.template, slot.mode)
        ports = [port for port in mode["ports"] if port["kind"] == "output"]
        if len(ports) != 1:
            raise shelf.ShelfConstructionError("BOUNDARY_PORT_CONTRACT", repr(slot))
        attachments.append(_terminal_attachment(anchor=slot.anchor, port=ports[0]))

    core_mode = _strict_mode(instance, "protocol_core", "inputs_north_south")
    core_outputs = sorted(
        (port for port in core_mode["ports"] if port["kind"] == "output"),
        key=lambda port: str(port["id"]),
    )
    core_south_inputs = sorted(
        (
            port
            for port in core_mode["ports"]
            if port["kind"] == "input" and port["direction"] == "S"
        ),
        key=lambda port: str(port["id"]),
    )
    for port in [*core_outputs, *core_south_inputs[:2]]:
        attachments.append(_terminal_attachment(anchor=shelf.FIXED_CORE_ANCHOR, port=port))
    if len(attachments) != 54:
        raise shelf.ShelfConstructionError(
            "FIXED_TERMINAL_SENTINEL", f"expected 54, observed {len(attachments)}"
        )
    off_network = [attachment for attachment in attachments if attachment[0] not in network_cells]
    if off_network:
        raise shelf.ShelfConstructionError("FIXED_TERMINAL_OFF_NETWORK", repr(off_network[:4]))
    return tuple(attachments)


def _allowed_component_rows() -> tuple[tuple[int, ...], ...]:
    """Enumerate all 48 strict component side patterns from the router itself."""

    rows: list[tuple[int, ...]] = []
    for row in product((0, 1), repeat=8):
        inputs = {direction for direction, present in zip(_DIRECTIONS, row[:4], strict=True) if present}
        outputs = {direction for direction, present in zip(_DIRECTIONS, row[4:], strict=True) if present}
        try:
            shelf.network_router._component_for_cell((0, 0), inputs, outputs, ("sentinel",))
        except shelf.network_router.NetworkRoutingError:
            continue
        rows.append(tuple(row))
    if len(rows) != 48:
        raise shelf.ShelfConstructionError(
            "COMPONENT_ROW_SENTINEL", f"expected 48 rows, observed {len(rows)}"
        )
    return tuple(rows)


def _audit_component_legality_static(
    *,
    instance: Mapping[str, Any],
    candidates: Sequence[PoseCandidate],
    groups: Sequence[Mapping[str, Any]],
    group_domains: Mapping[str, tuple[int, ...]],
    network_edges: frozenset[DirectedEdge],
) -> tuple[int, int, int, int]:
    """Fail closed unless every possible local attachment subset is legal.

    The shelf domains make component legality a static property: a route cell
    has at most two distinct conditional terminal side-keys.  Enumerating the
    full power set of those keys is an over-approximation of simultaneous
    non-overlapping placements.  If every such state is one of the 48 strict
    component variants, thousands of redundant table variables can be omitted
    without weakening the local vocabulary contract.  Directed commodity
    reachability remains a mandatory post-solve lane-level check.
    """

    network_cells = set(shelf.network_router.network_cells(network_edges))
    present: set[tuple[Cell, str, str]] = set()
    for source, target in network_edges:
        direction = _edge_direction(source, target)
        present.add((source, "output", direction))
        present.add((target, "input", _OPPOSITE[direction]))
    fixed = _fixed_terminal_attachments(instance, network_cells)
    present.update(fixed)

    # Validate the fixed edge/core/boundary state before adding conditional terminals.
    fixed_cells = {cell for cell, _kind, _direction in present}
    for cell in fixed_cells:
        inputs = {direction for here, kind, direction in present if here == cell and kind == "input"}
        outputs = {direction for here, kind, direction in present if here == cell and kind == "output"}
        try:
            shelf.network_router._component_for_cell(cell, inputs, outputs, ("sentinel",))
        except shelf.network_router.NetworkRoutingError as exc:
            raise shelf.ShelfConstructionError("FIXED_COMPONENT_ILLEGAL", str(exc)) from exc

    contributors: dict[Cell, set[tuple[str, str]]] = defaultdict(set)
    for group in groups:
        operation = str(group["id"])
        domain = set(group_domains[operation])
        for candidate_index, candidate in enumerate(candidates):
            if candidate_index not in domain:
                continue
            for attachment in _manufacturing_attachments(
                instance=instance,
                candidate=candidate,
                group=group,
                network_cells=network_cells,
            ):
                cell, kind, direction = attachment
                contributors[cell].add((kind, direction))

    rows = _allowed_component_rows()
    present_by_cell: dict[Cell, set[tuple[str, str]]] = defaultdict(set)
    for cell, kind, direction in present:
        present_by_cell[cell].add((kind, direction))
    affected_cells = sorted(contributors, key=lambda cell: (cell[1], cell[0]))
    state_count = 0
    for cell in affected_cells:
        optional = sorted(contributors[cell])
        if len(optional) > 2:
            raise shelf.ShelfConstructionError(
                "COMPONENT_STATIC_FANIN",
                f"{cell}: expected at most two conditional side-keys, observed {optional!r}",
            )
        for enabled in product((False, True), repeat=len(optional)):
            state = set(present_by_cell[cell])
            state.update(key for key, include in zip(optional, enabled, strict=True) if include)
            inputs = {direction for kind, direction in state if kind == "input"}
            outputs = {direction for kind, direction in state if kind == "output"}
            try:
                shelf.network_router._component_for_cell(cell, inputs, outputs, ("sentinel",))
            except shelf.network_router.NetworkRoutingError as exc:
                raise shelf.ShelfConstructionError(
                    "COMPONENT_STATIC_ILLEGAL",
                    f"{cell}: optional={optional!r}, enabled={enabled!r}: {exc}",
                ) from exc
            state_count += 1
    return len(affected_cells), state_count, len(rows), len(fixed)


def build_shelf_power_model(
    *, project_root: Path = shelf.strict_contract.PROJECT_ROOT
) -> ShelfPowerModel:
    bundle, _reconciliation = shelf.strict_contract.load_and_reconcile(project_root)
    instance = bundle.strict_instance.value
    edges = exact_network_edges()
    network_cells = set(shelf.network_router.network_cells(edges))
    fixed_body = _fixed_body_cells(instance)
    groups, operation_expansion = _aggregate_operation_signatures(instance)
    candidates, group_domains, domain_sizes = _enumerate_candidates(
        bundle=bundle,
        instance=instance,
        groups=groups,
        network_cells=network_cells,
        fixed_body=fixed_body,
    )
    template_domains, template_counts = _collapse_template_domains(groups, group_domains)
    pole_anchors = _enumerate_poles(
        bundle=bundle, network_cells=network_cells, fixed_body=fixed_body
    )

    model: Any = cp_model.CpModel()
    group_vars: dict[tuple[str, int], Any] = {}
    occupancy_vars: dict[int, Any] = {}
    for template, domain in sorted(template_domains.items()):
        variables: list[Any] = []
        for candidate_index in domain:
            variable = model.NewBoolVar(f"place__{template}__p{candidate_index}")
            group_vars[(template, candidate_index)] = variable
            occupancy_vars[candidate_index] = variable
            variables.append(variable)
        model.Add(sum(variables) == template_counts[template])

    (
        component_static_audit_cell_count,
        component_static_audit_state_count,
        component_allowed_row_count,
        fixed_terminal_count,
    ) = _audit_component_legality_static(
        instance=instance,
        candidates=candidates,
        groups=groups,
        group_domains=group_domains,
        network_edges=edges,
    )

    pole_vars = {
        index: model.NewBoolVar(f"pole__x{anchor[0]:02d}_y{anchor[1]:02d}")
        for index, anchor in enumerate(pole_anchors)
    }

    cell_terms: dict[Cell, list[Any]] = defaultdict(list)
    for candidate_index, variable in occupancy_vars.items():
        for cell in candidates[candidate_index].body_cells:
            cell_terms[cell].append(variable)
    for pole_index, anchor in enumerate(pole_anchors):
        for cell in geometry.pole_footprint(anchor):
            cell_terms[cell].append(pole_vars[pole_index])
    cell_constraint_count = 0
    for terms in cell_terms.values():
        if len(terms) > 1:
            model.Add(sum(terms) <= 1)
            cell_constraint_count += 1

    power_constraint_count = 0
    served_by_pole: dict[int, list[Any]] = defaultdict(list)
    for candidate_index, occupancy in occupancy_vars.items():
        coverers: list[Any] = []
        for pole_index, anchor in enumerate(pole_anchors):
            if not _pole_covers_body(anchor, candidates[candidate_index].body_cells):
                continue
            if set(geometry.pole_footprint(anchor)) & candidates[candidate_index].body_cells:
                continue
            coverers.append(pole_vars[pole_index])
            served_by_pole[pole_index].append(occupancy)
        if not coverers:
            model.Add(occupancy == 0)
        else:
            model.Add(occupancy <= sum(coverers))
        power_constraint_count += 1

    fixed_power_constraint_count = 0
    for fixed_index, body in enumerate(_fixed_power_bodies(instance)):
        coverers = [
            pole_vars[pole_index]
            for pole_index, anchor in enumerate(pole_anchors)
            if _pole_covers_body(anchor, body)
        ]
        if not coverers:
            raise shelf.ShelfConstructionError(
                "FIXED_POWER_DOMAIN_EMPTY", f"fixed powered body {fixed_index} has no pole anchor"
            )
        model.Add(sum(coverers) >= 1)
        fixed_power_constraint_count += 1

    pole_total = sum(pole_vars.values())
    model.Add(pole_total >= MIN_POLES)
    model.Add(pole_total <= MAX_POLES_FROM_FREE_AREA)
    for pole_index, pole in pole_vars.items():
        unique_occupancies = list(
            {variable.Index(): variable for variable in served_by_pole.get(pole_index, ())}.values()
        )
        if not unique_occupancies:
            model.Add(pole == 0)
        else:
            model.Add(pole <= sum(unique_occupancies))

    stats = ModelStats(
        network_edges=len(edges),
        network_cells=len(network_cells),
        protected_cells=len(PROTECTED_RECT.cells),
        fixed_body_cells=len(fixed_body),
        geometry_pose_count=len(occupancy_vars),
        group_pose_var_count=len(group_vars),
        pole_var_count=len(pole_vars),
        cell_constraint_count=cell_constraint_count,
        power_constraint_count=power_constraint_count,
        fixed_power_constraint_count=fixed_power_constraint_count,
        component_presence_var_count=0,
        component_table_constraint_count=0,
        component_static_audit_cell_count=component_static_audit_cell_count,
        component_static_audit_state_count=component_static_audit_state_count,
        component_allowed_row_count=component_allowed_row_count,
        fixed_terminal_count=fixed_terminal_count,
        pole_domain_mode=POLE_DOMAIN_MODE,
        group_domain_sizes=domain_sizes,
    )
    return ShelfPowerModel(
        model=model,
        candidates=candidates,
        groups=groups,
        group_vars=group_vars,
        occupancy_vars=occupancy_vars,
        pole_anchors=pole_anchors,
        pole_vars=pole_vars,
        network_edges=edges,
        bundle=bundle,
        stats=stats,
        operation_expansion=operation_expansion,
    )


def _solve_shelf_geometry(
    state: ShelfPowerModel, *, time_limit_seconds: float, workers: int
) -> ShelfPowerSolveResult:
    """Solve one already-built state; only the worker entry point calls this."""

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = int(workers)
    solver.parameters.random_seed = 20260720
    solver.parameters.log_search_progress = True
    status_code = solver.Solve(state.model)
    status = solver.StatusName(status_code)
    stats: dict[str, Any] = {
        **asdict(state.stats),
        "solver_status": status,
        "wall_time_seconds": solver.WallTime(),
        "branches": solver.NumBranches(),
        "conflicts": solver.NumConflicts(),
        "workers": workers,
        "time_limit_seconds": time_limit_seconds,
        "random_seed": 20260720,
    }
    if status_code not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return ShelfPowerSolveResult(
            status=status,
            manufacturing_slots=(),
            pole_anchors=(),
            pole_bay_anchors=state.pole_anchors,
            protected_rect=PROTECTED_RECT,
            network_edges=state.network_edges,
            stats=stats,
        )

    slots: list[Any] = []
    groups_by_template: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for group in state.groups:
        groups_by_template[str(group["template"])].append(group)
    for template, groups in sorted(groups_by_template.items()):
        selected = [
            (candidate_index, candidate)
            for candidate_index, candidate in enumerate(state.candidates)
            if (variable := state.group_vars.get((template, candidate_index))) is not None
            and solver.Value(variable)
        ]
        selected.sort(key=lambda item: (item[1].anchor[1], item[1].anchor[0], item[1].mode, item[0]))
        cursor = 0
        for group in sorted(groups, key=lambda item: str(item["id"])):
            signature = str(group["id"])
            strict_operations = state.operation_expansion[signature]
            chosen = selected[cursor : cursor + len(strict_operations)]
            cursor += len(strict_operations)
            if len(chosen) != len(strict_operations):
                raise shelf.ShelfConstructionError(
                    "SIGNATURE_EXPANSION_COUNT",
                    f"{signature}: selected {len(chosen)}, expected {len(strict_operations)}",
                )
            for (_candidate_index, candidate), operation in zip(
                chosen, strict_operations, strict=True
            ):
                slots.append(
                    shelf.GeometrySlot(
                        candidate.template,
                        candidate.mode,
                        candidate.anchor,
                        operation,
                    )
                )
        if cursor != len(selected):
            raise shelf.ShelfConstructionError(
                "TEMPLATE_EXPANSION_COUNT",
                f"{template}: consumed {cursor}, selected {len(selected)}",
            )
    selected_poles = tuple(
        state.pole_anchors[index]
        for index, variable in state.pole_vars.items()
        if solver.Value(variable)
    )
    stats["selected_manufacturing"] = len(slots)
    stats["selected_poles"] = len(selected_poles)
    return ShelfPowerSolveResult(
        status=status,
        manufacturing_slots=tuple(slots),
        pole_anchors=selected_poles,
        pole_bay_anchors=state.pole_anchors,
        protected_rect=PROTECTED_RECT,
        network_edges=state.network_edges,
        stats=stats,
    )


def _post_validate_result(
    result: ShelfPowerSolveResult,
    *,
    state: ShelfPowerModel,
    project_root: Path,
) -> dict[str, Any]:
    """Replay, bind, and compile components through the sole campaign path."""

    if result.status not in {"FEASIBLE", "OPTIMAL"}:
        raise shelf.ShelfConstructionError("SOLVER_NO_GEOMETRY", result.status)
    candidate = shelf.assemble_shelf_candidate(
        result.manufacturing_slots,
        pole_anchors=result.pole_anchors,
        pole_bay_anchors=result.pole_bay_anchors,
        protected_rect=result.protected_rect,
        network_edges=result.network_edges,
        project_root=project_root,
    )
    witness_campaign = importlib.import_module(
        "docs.research.witness_constructor_20260717.07_routing_aware.witness_campaign"
    )
    built = witness_campaign.build_witness(candidate, bundle=state.bundle)
    return built.diagnostics()


def _json_record(
    result: ShelfPowerSolveResult,
    *,
    input_hashes: Mapping[str, str],
    route_validation: Mapping[str, Any] | None,
    telemetry: Mapping[str, Any] | None,
    failure: Mapping[str, Any] | None,
    status_override: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": shelf.SHELF_RESULT_SCHEMA_VERSION,
        "status": status_override or result.status,
        "input_sha256": dict(sorted(input_hashes.items())),
        "manufacturing_slots": [
            {
                "template": slot.template,
                "mode": slot.mode,
                "anchor": [slot.anchor[0], slot.anchor[1]],
                "operation": slot.operation,
            }
            for slot in result.manufacturing_slots
        ],
        "pole_anchors": [list(anchor) for anchor in result.pole_anchors],
        "pole_bay_anchors": [list(anchor) for anchor in result.pole_bay_anchors],
        "protected_rect": [
            result.protected_rect.x,
            result.protected_rect.y,
            result.protected_rect.width,
            result.protected_rect.height,
        ],
        "network_edges": [[list(source), list(target)] for source, target in sorted(result.network_edges)],
        "stats": dict(result.stats),
        "route_validation": dict(route_validation) if route_validation is not None else None,
        "cgroup_telemetry": dict(telemetry) if telemetry is not None else None,
        "failure": dict(failure) if failure is not None else None,
    }


def _failure_record(exc: BaseException, *, phase: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "phase": phase,
        "type": type(exc).__name__,
        "message": str(exc),
    }
    code = getattr(exc, "code", None)
    if isinstance(code, str):
        record["code"] = code
    return record


def _empty_result(state: ShelfPowerModel, *, status: str, failure: Mapping[str, Any]) -> ShelfPowerSolveResult:
    return ShelfPowerSolveResult(
        status=status,
        manufacturing_slots=(),
        pole_anchors=(),
        pole_bay_anchors=state.pole_anchors,
        protected_rect=PROTECTED_RECT,
        network_edges=state.network_edges,
        stats={**asdict(state.stats), "failure": dict(failure)},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-root", type=Path, default=shelf.strict_contract.PROJECT_ROOT)
    parser.add_argument("--time-limit-seconds", type=float, default=600.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--expected-unit")
    args = parser.parse_args()
    if args.dry_run:
        state = build_shelf_power_model(project_root=args.project_root)
        print(json.dumps(asdict(state.stats), ensure_ascii=False, sort_keys=True))
        return 0
    if args.out is None or args.expected_unit is None:
        parser.error("solve mode requires both --out and --expected-unit")
    if args.workers < 1 or args.time_limit_seconds <= 0:
        parser.error("--workers and --time-limit-seconds must be positive")
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("--out must name a new file inside an existing run directory")

    start: Any | None = None
    state: ShelfPowerModel | None = None
    telemetry_record: Mapping[str, Any] | None = None
    route_validation: Mapping[str, Any] | None = None
    failure: Mapping[str, Any] | None = None
    status_override: str | None = None
    input_hashes: Mapping[str, str] = {}
    phase = "telemetry_begin"
    result = ShelfPowerSolveResult(
        status="WORKER_ERROR",
        manufacturing_slots=(),
        pole_anchors=(),
        pole_bay_anchors=(),
        protected_rect=PROTECTED_RECT,
        network_edges=frozenset(),
        stats={"failure": {"phase": "not_started"}},
    )
    try:
        start = cgroup_telemetry.begin_worker_cgroup_telemetry(
            expected_unit_name=args.expected_unit
        )
        phase = "model_build"
        state = build_shelf_power_model(project_root=args.project_root)
        input_hashes = state.bundle.hashes
        result = _empty_result(state, status="WORKER_ERROR", failure={"phase": "not_started"})
        phase = "solve"
        result = _solve_shelf_geometry(
            state,
            time_limit_seconds=args.time_limit_seconds,
            workers=args.workers,
        )
        if result.status not in {"FEASIBLE", "OPTIMAL"}:
            failure = {
                "phase": "solve",
                "type": "SolverNoSolution",
                "message": f"solver terminated with {result.status}",
            }
        else:
            phase = "post_validate"
            route_validation = _post_validate_result(
                result,
                state=state,
                project_root=args.project_root,
            )
    except BaseException as exc:
        failure = _failure_record(exc, phase=phase)
        status_override = "WORKER_ERROR"
    finally:
        if start is not None:
            try:
                finished = cgroup_telemetry.finish_worker_cgroup_telemetry(start)
                telemetry_record = finished.as_dict()
                if finished.oom_attribution != cgroup_telemetry.NO_CGROUP_OOM:
                    failure = {
                        "phase": "telemetry_finish",
                        "type": "CgroupOomAttributed",
                        "message": finished.oom_attribution,
                    }
                    status_override = "CGROUP_OOM"
            except BaseException as exc:
                failure = _failure_record(exc, phase="telemetry_finish")
                status_override = "WORKER_ERROR"

    accepted = (
        result.status in {"FEASIBLE", "OPTIMAL"}
        and state is not None
        and status_override is None
        and failure is None
        and route_validation is not None
        and telemetry_record is not None
    )
    if not accepted and failure is None:
        failure = {
            "phase": "worker_terminal",
            "type": "IncompleteWorkerResult",
            "message": "worker did not produce every accepted result field",
        }
        status_override = "WORKER_ERROR"
    record = _json_record(
        result,
        input_hashes=input_hashes,
        route_validation=route_validation,
        telemetry=telemetry_record,
        failure=failure,
        status_override=status_override,
    )
    payload = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    # Exit zero means the terminal record was emitted completely.  Acceptance
    # remains an explicit function of status, failure, route validation, and
    # cgroup telemetry; launchers must classify those recorded fields.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
