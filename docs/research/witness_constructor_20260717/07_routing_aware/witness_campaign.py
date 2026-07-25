"""Unique acceptance path from shelf geometry to an independently checked witness.

The geometry search is deliberately outside this module.  Once it returns an
exact :class:`ShelfCandidate`, this pipeline has no routing alternatives: it
binds strict physical ports only on the candidate's directed SCC, compiles that
same SCC to strict component types, independently maximizes the body-empty
rectangle, and assembles the benchmark witness bytes.

Nothing in this module asserts global optimality.  The computed rectangle is
the exact score of one feasible layout and therefore only a feasible lower
bound for the benchmark objective.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from . import (
    fixed_geometry_router,
    network_router,
    objective_audit,
    shelf_constructor,
    strict_contract,
    witness_io,
)


Cell = tuple[int, int]

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_ROUTER_FEASIBLE_KEYS = {
    "schema_version",
    "status",
    "classification",
    "claim_boundary",
    "required_placements",
    "optional_placements",
    "port_specs",
    "route_components",
    "route_components_digest",
    "telemetry",
}


class WitnessCampaignError(RuntimeError):
    """The deterministic build or acceptance path failed closed."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class BuiltWitness:
    """In-memory result before the independent checker is invoked."""

    witness: Mapping[str, Any]
    objective: objective_audit.ObjectiveAudit
    route_component_count: int
    route_cell_count: int
    terminal_count: int
    source_count: int
    sink_count: int
    pole_count: int
    box_count: int

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "WITNESS_BUILT",
            "claim_boundary": "feasible_layout_lower_bound_only",
            "route_component_count": self.route_component_count,
            "route_cell_count": self.route_cell_count,
            "terminal_count": self.terminal_count,
            "source_count": self.source_count,
            "sink_count": self.sink_count,
            "pole_count": self.pole_count,
            "box_count": self.box_count,
            "objective": self.objective.as_dict(),
        }


def _fail(code: str, message: str) -> None:
    raise WitnessCampaignError(code, message)


def _instance_payload(bundle: strict_contract.InputBundle) -> bytes:
    try:
        payload = bundle.strict_instance.path.read_bytes()
    except OSError as exc:
        _fail("INSTANCE_READ_FAILED", str(exc))
    digest = hashlib.sha256(payload).hexdigest()
    if digest != bundle.strict_instance.sha256:
        _fail(
            "INSTANCE_CHANGED_AFTER_RECONCILIATION",
            f"expected {bundle.strict_instance.sha256}, observed {digest}",
        )
    return payload


def _core_south_input_cells(
    instance: Mapping[str, Any], required: Sequence[Mapping[str, Any]]
) -> frozenset[Cell]:
    core_records = [record for record in required if record["template"] == "protocol_core"]
    if len(core_records) != 1:
        _fail("CORE_PLACEMENT_COUNT", f"expected one core, observed {len(core_records)}")
    core = core_records[0]
    template = instance["facility_templates"]["protocol_core"]
    modes = [mode for mode in template["modes"] if mode["id"] == core["mode"]]
    if len(modes) != 1:
        _fail("CORE_MODE", f"unknown or duplicate core mode {core['mode']!r}")
    anchor = core["anchor"]
    result: set[Cell] = set()
    for port in modes[0]["ports"]:
        if port["kind"] != "input" or port["direction"] != "S":
            continue
        body_cell = port["body_cell"]
        result.add((int(anchor["x"]) + int(body_cell["x"]), int(anchor["y"]) - 1))
    if len(result) != 7:
        _fail("CORE_SOUTH_INPUT_COUNT", f"expected seven physical south inputs, observed {len(result)}")
    return frozenset(result)


def _objective_claim(rectangle: objective_audit.EmptyRectangle) -> dict[str, Any]:
    return {
        "rectangle": {
            "x": rectangle.x,
            "y": rectangle.y,
            "width": rectangle.width,
            "height": rectangle.height,
        },
        "area": rectangle.area,
        "min_side": rectangle.min_side,
    }


def build_witness(
    candidate: shelf_constructor.ShelfCandidate,
    *,
    bundle: strict_contract.InputBundle,
    extra_optional_placements: Sequence[Mapping[str, Any]] = (),
) -> BuiltWitness:
    """Build one strict witness through the sole accepted deterministic route."""

    instance = bundle.strict_instance.value
    if not isinstance(instance, Mapping):
        _fail("INSTANCE_SHAPE", "strict instance is not an object")
    instance_payload = _instance_payload(bundle)
    required_geometry = [placement.strict_record() for placement in candidate.placements]
    pole_geometry = [placement.strict_record() for placement in candidate.pole_placements]
    optional_geometry = [*pole_geometry, *(dict(record) for record in extra_optional_placements)]
    box_count = sum(record.get("template") == "storage_box" for record in optional_geometry)
    if box_count > 2:
        _fail("BOX_POLICY", f"at most two storage boxes are permitted, observed {box_count}")

    exact_network_cells = network_router.network_cells(candidate.network_edges)
    if exact_network_cells != candidate.reserved_network_cells:
        _fail("NETWORK_RESERVATION_DRIFT", "candidate cells differ from its exact directed edges")
    core_south = _core_south_input_cells(instance, required_geometry)
    bound = witness_io.bind_placements(
        instance,
        required_placements=required_geometry,
        optional_placements=optional_geometry,
        allowed_access_cells=exact_network_cells,
        core_final_input_access_cells=core_south if box_count == 0 else None,
        require_all_core_raw_outputs=True,
    )
    all_bound = [*bound["required_placements"], *bound["optional_placements"]]
    terminals = network_router.terminals_from_witness(instance, all_bound)
    source_count = sum(terminal.kind == "output" for terminal in terminals)
    sink_count = sum(terminal.kind == "input" for terminal in terminals)
    if (len(terminals), source_count, sink_count) != (628, 316, 312):
        _fail(
            "TERMINAL_SENTINEL",
            f"expected (628,316,312), observed {(len(terminals), source_count, sink_count)}",
        )

    occupied = network_router.occupied_body_cells(instance, all_bound)
    if occupied & exact_network_cells:
        _fail("BODY_NETWORK_COLLISION", repr(sorted(occupied & exact_network_cells)[:8]))
    protected = candidate.protected_rect
    if sorted((int(protected.width), int(protected.height))) != [6, 7]:
        _fail("PROTECTED_RECT_CONTRACT", "the construction must reserve one exact 6x7 body-empty rectangle")
    if occupied & protected.cells:
        _fail("PROTECTED_RECT_BLOCKED", repr(sorted(occupied & protected.cells)[:8]))

    routes = network_router.build_route_components(
        edges=candidate.network_edges,
        terminals=terminals,
        commodities=instance["commodities"],
        occupied_cells=occupied,
        require_strong_connectivity=True,
    )
    width = int(instance["grid"]["width"])
    height = int(instance["grid"]["height"])
    minimum_side = int(instance["objective"]["minimum_side"])
    rectangle = objective_audit.maximum_empty_rectangle(width, height, occupied, minimum_side)
    if rectangle.score < (42, 6):
        _fail("LOWER_BOUND_BASELINE", f"protected 6x7 baseline was lost: {rectangle.score}")
    witness = witness_io.assemble_strict_witness(
        instance_payload=instance_payload,
        required_placements=bound["required_placements"],
        optional_placements=bound["optional_placements"],
        route_components=routes,
        claimed_objective=_objective_claim(rectangle),
    )
    audited = objective_audit.audit_witness_objective(instance, witness)
    pole_count = sum(record["template"] == "power_pole" for record in bound["optional_placements"])
    shelf_constructor.assert_full_witness_pole_lower_bound(
        required_count=len(bound["required_placements"]), pole_count=pole_count
    )
    return BuiltWitness(
        witness=witness,
        objective=audited,
        route_component_count=len(routes),
        route_cell_count=len(exact_network_cells),
        terminal_count=len(terminals),
        source_count=source_count,
        sink_count=sink_count,
        pole_count=pole_count,
        box_count=box_count,
    )


def build_routed_witness(
    router_result: Mapping[str, Any],
    *,
    bundle: strict_contract.InputBundle,
) -> BuiltWitness:
    """Assemble a strict witness from one independently checked router result.

    The fixed-geometry worker has already replayed candidate poses, performed
    exact port binding, adapted the production route states, and checked
    commodity reachability.  This boundary deliberately repeats the cheap
    structural and reachability checks before the result can become checker
    input.  Only a feasible, post-solve-revalidated result is accepted.
    """

    if not isinstance(router_result, Mapping):
        _fail("ROUTER_RESULT_SHAPE", "router result must be an object")
    if set(router_result) != _ROUTER_FEASIBLE_KEYS:
        _fail(
            "ROUTER_RESULT_FIELDS",
            (
                f"missing={sorted(_ROUTER_FEASIBLE_KEYS - set(router_result))}, "
                f"extra={sorted(set(router_result) - _ROUTER_FEASIBLE_KEYS)}"
            ),
        )
    if router_result.get("schema_version") != fixed_geometry_router.OUTPUT_SCHEMA_VERSION:
        _fail("ROUTER_RESULT_SCHEMA", "unexpected fixed-geometry router schema")
    if (
        router_result.get("status") != "FEASIBLE"
        or router_result.get("classification") != "STRICT_ROUTES_INDEPENDENTLY_REACHABLE"
    ):
        _fail("ROUTER_RESULT_NOT_FEASIBLE", repr(router_result.get("classification")))
    if router_result.get("claim_boundary") != "research_witness_candidate_only":
        _fail("ROUTER_CLAIM_BOUNDARY", repr(router_result.get("claim_boundary")))

    instance = bundle.strict_instance.value
    if not isinstance(instance, Mapping):
        _fail("INSTANCE_SHAPE", "strict instance is not an object")
    telemetry = router_result.get("telemetry")
    if not isinstance(telemetry, Mapping):
        _fail("ROUTER_TELEMETRY_SHAPE", "router telemetry must be an object")
    snapshot = telemetry.get("input_snapshot")
    if not isinstance(snapshot, Mapping) or snapshot.get("post_solve_revalidated") is not True:
        _fail("ROUTER_INPUT_NOT_REVALIDATED", "post-solve input snapshot gate did not pass")
    if snapshot.get("dependency_hashes") != dict(sorted(bundle.hashes.items())):
        _fail("ROUTER_DEPENDENCY_HASH_DRIFT", "router dependency hashes differ from reconciliation")
    geometry_sha256 = snapshot.get("geometry_sha256")
    if type(geometry_sha256) is not str or _SHA256_RE.fullmatch(geometry_sha256) is None:
        _fail("ROUTER_GEOMETRY_HASH", repr(geometry_sha256))
    cgroup = telemetry.get("cgroup")
    if not isinstance(cgroup, Mapping) or cgroup.get("oom_attribution") != "NO_CGROUP_OOM":
        _fail("ROUTER_CGROUP_GATE", repr(cgroup.get("oom_attribution") if isinstance(cgroup, Mapping) else None))

    required = router_result.get("required_placements")
    optional = router_result.get("optional_placements")
    routes = router_result.get("route_components")
    port_specs = router_result.get("port_specs")
    if not all(isinstance(value, list) for value in (required, optional, routes, port_specs)):
        _fail("ROUTER_RESULT_ARRAYS", "placements, port specs, and routes must be arrays")
    assert isinstance(required, list)
    assert isinstance(optional, list)
    assert isinstance(routes, list)
    assert isinstance(port_specs, list)
    route_digest = router_result.get("route_components_digest")
    if type(route_digest) is not str or _SHA256_RE.fullmatch(route_digest) is None:
        _fail("ROUTER_ROUTE_DIGEST", repr(route_digest))
    if route_digest != fixed_geometry_router.canonical_digest(routes):
        _fail("ROUTER_ROUTE_DIGEST_MISMATCH", "route_components differ from their worker digest")

    expected_required = {
        str(record["id"]): str(record["template"])
        for record in instance["required_instances"]
    }
    observed_required: dict[str, str] = {}
    for placement in required:
        if not isinstance(placement, Mapping):
            _fail("ROUTER_REQUIRED_PLACEMENT_SHAPE", "required placement is not an object")
        instance_id = str(placement.get("instance_id", ""))
        template = str(placement.get("template", ""))
        if not instance_id or instance_id in observed_required:
            _fail("ROUTER_REQUIRED_PLACEMENT_IDS", repr(instance_id))
        observed_required[instance_id] = template
    if observed_required != expected_required:
        _fail("ROUTER_REQUIRED_PLACEMENT_SET", "router result changed the 266 required IDs/templates")

    optional_ids: set[str] = set()
    for placement in optional:
        if not isinstance(placement, Mapping):
            _fail("ROUTER_OPTIONAL_PLACEMENT_SHAPE", "optional placement is not an object")
        instance_id = str(placement.get("instance_id", ""))
        if (
            not instance_id
            or instance_id in optional_ids
            or instance_id in observed_required
            or placement.get("template") != "power_pole"
        ):
            _fail("ROUTER_OPTIONAL_PLACEMENT_SET", repr(instance_id))
        optional_ids.add(instance_id)
    pole_count = len(optional)
    shelf_constructor.assert_full_witness_pole_lower_bound(
        required_count=len(required), pole_count=pole_count
    )

    if len(port_specs) != 628:
        _fail("ROUTER_PORT_SPEC_SENTINEL", f"expected 628, observed {len(port_specs)}")
    all_bound = [*required, *optional]
    recomputed_port_specs = witness_io.derive_production_port_specs(
        instance,
        required_placements=required,
        optional_placements=optional,
    )
    if port_specs != recomputed_port_specs:
        _fail("ROUTER_PORT_SPECS_MISMATCH", "router port specs differ from strict bound placements")
    if telemetry.get("port_specs_digest") != fixed_geometry_router.canonical_digest(port_specs):
        _fail("ROUTER_PORT_SPECS_DIGEST", "router port-spec digest is missing or inconsistent")
    terminals = network_router.terminals_from_witness(instance, all_bound)
    source_count = sum(terminal.kind == "output" for terminal in terminals)
    sink_count = sum(terminal.kind == "input" for terminal in terminals)
    if (len(terminals), source_count, sink_count) != (628, 316, 312):
        _fail(
            "TERMINAL_SENTINEL",
            f"expected (628,316,312), observed {(len(terminals), source_count, sink_count)}",
        )
    commodities = [str(value) for value in instance["commodities"]]
    network_router.assert_terminal_route_reachability(routes, terminals, commodities)

    occupied = network_router.occupied_body_cells(instance, all_bound)
    route_cells: set[Cell] = set()
    for component in routes:
        if not isinstance(component, Mapping) or not isinstance(component.get("cell"), Mapping):
            _fail("ROUTER_COMPONENT_SHAPE", "route component/cell must be an object")
        cell = component["cell"]
        route_cells.add((int(cell["x"]), int(cell["y"])))
    if len(route_cells) != len(routes):
        _fail("ROUTER_COMPONENT_DUPLICATE_CELL", "route components reuse a physical cell")
    if route_cells & occupied:
        _fail("BODY_NETWORK_COLLISION", repr(sorted(route_cells & occupied)[:8]))

    width = int(instance["grid"]["width"])
    height = int(instance["grid"]["height"])
    minimum_side = int(instance["objective"]["minimum_side"])
    rectangle = objective_audit.maximum_empty_rectangle(width, height, occupied, minimum_side)
    if rectangle.score < (42, 6):
        _fail("LOWER_BOUND_BASELINE", f"protected 6x7 baseline was lost: {rectangle.score}")
    witness = witness_io.assemble_strict_witness(
        instance_payload=_instance_payload(bundle),
        required_placements=required,
        optional_placements=optional,
        route_components=routes,
        claimed_objective=_objective_claim(rectangle),
    )
    audited = objective_audit.audit_witness_objective(instance, witness)
    return BuiltWitness(
        witness=witness,
        objective=audited,
        route_component_count=len(routes),
        route_cell_count=len(route_cells),
        terminal_count=len(terminals),
        source_count=source_count,
        sink_count=sink_count,
        pole_count=pole_count,
        box_count=0,
    )


def accept_independent_checker(
    built: BuiltWitness,
    checker: witness_io.CheckerProcessResult,
) -> dict[str, Any]:
    """Require pinned-checker green and exact agreement with the other audit."""

    if not checker.accepted or checker.report is None:
        _fail("INDEPENDENT_CHECKER_REJECTED", checker.classification)
    expected = asdict(built.objective.computed)
    observed = checker.report.get("recomputed_objective")
    if observed != expected:
        _fail("OBJECTIVE_AUDIT_DISAGREEMENT", f"independent={observed!r}, exhaustive={expected!r}")
    return {
        "status": "INDEPENDENT_ACCEPTANCE_OK",
        "checker_sha256": checker.checker_sha256,
        "checker_status": checker.status,
        "recomputed_objective": expected,
        "claim_boundary": "feasible_layout_lower_bound_only",
    }


def build_current_witness(
    *,
    geometry_result: Path,
    project_root: Path = strict_contract.PROJECT_ROOT,
) -> tuple[BuiltWitness, strict_contract.InputBundle, strict_contract.Reconciliation]:
    """Replay one explicit worker result and build the in-memory witness."""

    bundle, reconciliation = strict_contract.load_and_reconcile(project_root)
    candidate = shelf_constructor.construct_shelf_candidate(
        result_path=geometry_result,
        project_root=project_root,
    )
    return build_witness(candidate, bundle=bundle), bundle, reconciliation


__all__ = [
    "BuiltWitness",
    "WitnessCampaignError",
    "accept_independent_checker",
    "build_current_witness",
    "build_routed_witness",
    "build_witness",
]
