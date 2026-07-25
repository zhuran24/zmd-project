"""Research-only fixed-geometry exact routing worker blueprint.

The worker deliberately composes the released strict witness helpers with the
production routing model.  It does not implement a second routing semantics:

``geometry -> candidate-pose replay -> free-front binding -> production port
specs -> production RoutingGrid/RoutingSubproblem -> strict route adapter ->
independent lane reachability``.

The public runner is dependency-injected so its state machine and fail-closed
classification can be tested on tiny fixtures without starting a production
CP-SAT solve.  :func:`production_dependencies` is the only place that imports
the production/research modules.

This is a worker, not a launcher.  A production-sized call must be wrapped by
the existing :mod:`run_supervisor` contract: hold ``acquire_prod_scale_lock``
for the whole attempt, snapshot an explicitly hash-pinned geometry input, and
start the worker in the validated systemd cgroup leaf.  The worker revalidates
that leaf immediately around ``solve``; it never starts a second solver or
silently acquires/reuses a run directory on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import stat
import time
from typing import Any, Callable, Mapping, Sequence


INPUT_SCHEMA_VERSION = "fixed_geometry_router_input.v2"
OUTPUT_SCHEMA_VERSION = "fixed_geometry_router_result.v1"
_RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class FixedGeometryRouterError(RuntimeError):
    """Stable fail-closed worker error."""

    def __init__(self, code: str, message: str, *, phase: str) -> None:
        self.code = code
        self.phase = phase
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class GeometryInput:
    required_placements: tuple[dict[str, Any], ...]
    pole_anchors: tuple[tuple[int, int], ...]
    manufacturing_port_bindings: dict[str, dict[str, str]]


@dataclass(frozen=True)
class ProductionInputSnapshot:
    """Hash-reconciled production inputs supplied to one supervised worker."""

    instance: Mapping[str, Any]
    facility_pools: Mapping[str, Any]
    hashes: Mapping[str, str]


@dataclass(frozen=True)
class WorkerConfig:
    """Attempt-local controls; production defaults enforce the run contract."""

    time_limit_seconds: float
    minimum_poles: int = 9
    required_grid: tuple[int, int] = (70, 70)
    require_cgroup: bool = True
    expected_unit_name: str | None = None

    def validate(self) -> None:
        if isinstance(self.time_limit_seconds, bool) or not isinstance(
            self.time_limit_seconds, (int, float)
        ):
            raise FixedGeometryRouterError(
                "INVALID_TIME_LIMIT", "time limit must be a finite positive number", phase="input"
            )
        if not math.isfinite(float(self.time_limit_seconds)) or float(self.time_limit_seconds) <= 0.0:
            raise FixedGeometryRouterError(
                "INVALID_TIME_LIMIT", "time limit must be a finite positive number", phase="input"
            )
        if isinstance(self.minimum_poles, bool) or not isinstance(self.minimum_poles, int):
            raise FixedGeometryRouterError(
                "INVALID_POLE_FLOOR", "minimum_poles must be an integer", phase="input"
            )
        if self.minimum_poles < 0:
            raise FixedGeometryRouterError(
                "INVALID_POLE_FLOOR", "minimum_poles must be nonnegative", phase="input"
            )
        if (
            len(self.required_grid) != 2
            or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in self.required_grid)
        ):
            raise FixedGeometryRouterError(
                "INVALID_GRID_CONTRACT", "required_grid must contain two positive integers", phase="input"
            )
        if self.require_cgroup and not self.expected_unit_name:
            raise FixedGeometryRouterError(
                "CGROUP_UNIT_REQUIRED", "production routing requires an expected service unit", phase="input"
            )


@dataclass(frozen=True)
class WorkerDependencies:
    """All semantic boundaries used by :func:`run_fixed_geometry_router`."""

    resolve_placement_solution: Callable[..., Mapping[str, Mapping[str, Any]]]
    build_routing_context: Callable[..., Any]
    choose_port_bindings: Callable[..., Mapping[str, Mapping[str, str]]]
    bind_placements: Callable[..., Mapping[str, Any]]
    derive_port_specs: Callable[..., Sequence[Mapping[str, Any]]]
    occupied_body_cells: Callable[..., Sequence[tuple[int, int]]]
    make_placement_core: Callable[..., Any]
    routing_precheck: Callable[..., Mapping[str, Any]]
    make_routing_grid: Callable[..., Any]
    make_routing_subproblem: Callable[..., Any]
    add_l1_support_constraints: Callable[..., Sequence[Any]]
    adapt_extracted_routes: Callable[..., Sequence[Mapping[str, Any]]]
    terminals_from_witness: Callable[..., Sequence[Any]]
    assert_terminal_route_reachability: Callable[..., None]
    begin_cgroup_telemetry: Callable[[str], Any]
    finish_cgroup_telemetry: Callable[[Any], Any]


def _fail(code: str, message: str, *, phase: str) -> None:
    raise FixedGeometryRouterError(code, message, phase=phase)


def _strict_int(value: object, *, name: str, phase: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("MALFORMED_INTEGER", f"{name} must be a literal integer", phase=phase)
    return int(value)


def _strict_mapping(value: object, *, name: str, phase: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail("MALFORMED_OBJECT", f"{name} must be an object with string keys", phase=phase)
    return value


def _strict_sequence(value: object, *, name: str, phase: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail("MALFORMED_ARRAY", f"{name} must be an array", phase=phase)
    return value


def _strict_string(value: object, *, name: str, phase: str) -> str:
    if type(value) is not str or not value:
        _fail("MALFORMED_STRING", f"{name} must be a nonempty string", phase=phase)
    return value


def _json_copy(value: object, *, name: str, phase: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        _fail("NON_JSON_VALUE", f"{name} is not strict JSON data: {exc}", phase=phase)


def canonical_digest(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        _fail("NON_JSON_VALUE", f"digest input is not strict JSON data: {exc}", phase="output")
    return hashlib.sha256(payload).hexdigest()


def parse_geometry_payload(payload: object, *, minimum_poles: int = 9) -> GeometryInput:
    """Parse the deliberately small geometry handoff schema exactly."""

    root = _strict_mapping(payload, name="geometry", phase="input")
    expected = {
        "schema_version",
        "required_placements",
        "pole_anchors",
        "manufacturing_port_bindings",
    }
    if set(root) != expected:
        _fail(
            "GEOMETRY_FIELDS",
            f"geometry fields differ from {sorted(expected)}",
            phase="input",
        )
    if root.get("schema_version") != INPUT_SCHEMA_VERSION:
        _fail("GEOMETRY_SCHEMA", "unsupported geometry schema version", phase="input")

    required: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(
        _strict_sequence(root.get("required_placements"), name="required_placements", phase="input")
    ):
        record = _strict_mapping(raw, name=f"required_placements[{index}]", phase="input")
        fields = {"instance_id", "template", "mode", "anchor"}
        if set(record) != fields:
            _fail(
                "PLACEMENT_FIELDS",
                f"required_placements[{index}] fields differ from {sorted(fields)}",
                phase="input",
            )
        instance_id = _strict_string(
            record.get("instance_id"), name=f"required_placements[{index}].instance_id", phase="input"
        )
        if instance_id in seen_ids:
            _fail("DUPLICATE_PLACEMENT_ID", instance_id, phase="input")
        seen_ids.add(instance_id)
        anchor = _strict_mapping(
            record.get("anchor"), name=f"required_placements[{index}].anchor", phase="input"
        )
        if set(anchor) != {"x", "y"}:
            _fail("ANCHOR_FIELDS", f"required_placements[{index}].anchor fields are invalid", phase="input")
        required.append(
            {
                "instance_id": instance_id,
                "template": _strict_string(
                    record.get("template"), name=f"required_placements[{index}].template", phase="input"
                ),
                "mode": _strict_string(
                    record.get("mode"), name=f"required_placements[{index}].mode", phase="input"
                ),
                "anchor": {
                    "x": _strict_int(anchor.get("x"), name=f"required_placements[{index}].anchor.x", phase="input"),
                    "y": _strict_int(anchor.get("y"), name=f"required_placements[{index}].anchor.y", phase="input"),
                },
            }
        )

    poles: list[tuple[int, int]] = []
    for index, raw in enumerate(_strict_sequence(root.get("pole_anchors"), name="pole_anchors", phase="input")):
        pair = _strict_sequence(raw, name=f"pole_anchors[{index}]", phase="input")
        if len(pair) != 2:
            _fail("POLE_ANCHOR_SHAPE", f"pole_anchors[{index}] must have length two", phase="input")
        poles.append(
            (
                _strict_int(pair[0], name=f"pole_anchors[{index}][0]", phase="input"),
                _strict_int(pair[1], name=f"pole_anchors[{index}][1]", phase="input"),
            )
        )
    if len(poles) != len(set(poles)):
        _fail("DUPLICATE_POLE_ANCHOR", "pole anchors must be unique", phase="input")
    if len(poles) < minimum_poles:
        _fail(
            "POLE_LOWER_BOUND",
            f"geometry has {len(poles)} poles, below the required floor {minimum_poles}",
            phase="input",
        )

    raw_manufacturing_bindings = _strict_mapping(
        root.get("manufacturing_port_bindings"),
        name="manufacturing_port_bindings",
        phase="input",
    )
    manufacturing_bindings: dict[str, dict[str, str]] = {}
    for raw_instance_id in sorted(raw_manufacturing_bindings):
        instance_id = _strict_string(
            raw_instance_id,
            name="manufacturing_port_bindings instance ID",
            phase="input",
        )
        raw_bindings = _strict_mapping(
            raw_manufacturing_bindings[raw_instance_id],
            name=f"manufacturing_port_bindings.{instance_id}",
            phase="input",
        )
        if not raw_bindings:
            _fail(
                "EMPTY_MANUFACTURING_BINDING",
                f"{instance_id} must select at least one physical port",
                phase="input",
            )
        bindings: dict[str, str] = {}
        for raw_port_id in sorted(raw_bindings):
            port_id = _strict_string(
                raw_port_id,
                name=f"manufacturing_port_bindings.{instance_id} port ID",
                phase="input",
            )
            bindings[port_id] = _strict_string(
                raw_bindings[raw_port_id],
                name=f"manufacturing_port_bindings.{instance_id}.{port_id}",
                phase="input",
            )
        manufacturing_bindings[instance_id] = bindings
    unknown_binding_ids = sorted(set(manufacturing_bindings) - seen_ids)
    if unknown_binding_ids:
        _fail(
            "UNKNOWN_MANUFACTURING_BINDING_INSTANCE",
            f"manufacturing bindings reference unknown placements {unknown_binding_ids}",
            phase="input",
        )
    required.sort(key=lambda record: str(record["instance_id"]))
    poles.sort(key=lambda anchor: (anchor[1], anchor[0]))
    return GeometryInput(tuple(required), tuple(poles), manufacturing_bindings)


def load_geometry_payload(path: Path, *, expected_sha256: str | None = None) -> object:
    """Load strict JSON and optionally require its supervisor-pinned raw hash.

    Production callers must pass ``expected_sha256`` from the explicit input
    snapshot.  The optional form exists only for in-memory/tiny test fixtures;
    it must not be used as the production launch path.
    """

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number {value!r}")

    def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    source = Path(path)
    if expected_sha256 is not None and (
        type(expected_sha256) is not str or _SHA256_RE.fullmatch(expected_sha256) is None
    ):
        _fail("GEOMETRY_HASH_INVALID", "expected geometry SHA-256 is malformed", phase="input")
    try:
        metadata = source.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            _fail("GEOMETRY_FILE_TYPE", "geometry input must be a regular non-symlink file", phase="input")
        raw = source.read_bytes()
        observed_sha256 = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and observed_sha256 != expected_sha256:
            _fail(
                "GEOMETRY_HASH_MISMATCH",
                f"expected {expected_sha256}, observed {observed_sha256}",
                phase="input",
            )
        return json.loads(
            raw.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_pairs,
        )
    except FixedGeometryRouterError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        _fail("GEOMETRY_READ_FAILED", str(exc), phase="input")


def load_production_input_snapshot(project_root: Path) -> ProductionInputSnapshot:
    """Load and independently reconcile every hash-pinned router dependency."""

    try:
        strict_contract = importlib.import_module(
            "docs.research.witness_constructor_20260717.07_routing_aware.strict_contract"
        )
        bundle, _reconciliation = strict_contract.load_and_reconcile(Path(project_root))
    except Exception as exc:  # noqa: BLE001 - dependency authority boundary
        _fail("DEPENDENCY_RECONCILIATION_FAILED", type(exc).__name__, phase="dependency_load")
    observed = dict(bundle.hashes)
    expected = dict(strict_contract.EXPECTED_SHA256)
    if observed != expected:
        _fail(
            "DEPENDENCY_HASH_MISMATCH",
            f"expected={expected!r}, observed={observed!r}",
            phase="dependency_load",
        )
    instance = bundle.strict_instance.value
    candidate_root = bundle.candidate_poses.value
    if not isinstance(instance, Mapping) or not isinstance(candidate_root, Mapping):
        _fail("DEPENDENCY_SHAPE", "strict instance/candidate root is not an object", phase="dependency_load")
    facility_pools = candidate_root.get("facility_pools")
    if not isinstance(facility_pools, Mapping):
        _fail("DEPENDENCY_SHAPE", "candidate facility_pools is not an object", phase="dependency_load")
    return ProductionInputSnapshot(
        instance=instance,
        facility_pools=facility_pools,
        hashes=observed,
    )


def _pole_records(anchors: Sequence[tuple[int, int]]) -> list[dict[str, Any]]:
    return [
        {
            "instance_id": f"research_power_pole_{index:03d}",
            "template": "power_pole",
            "mode": "fixed",
            "anchor": {"x": x, "y": y},
        }
        for index, (x, y) in enumerate(anchors)
    ]


def _grid_dimensions(instance: Mapping[str, Any], required_grid: tuple[int, int]) -> tuple[int, int]:
    grid = _strict_mapping(instance.get("grid"), name="instance.grid", phase="input")
    if set(grid) != {"width", "height"}:
        _fail("INSTANCE_GRID_FIELDS", "instance.grid must contain exactly width/height", phase="input")
    width = _strict_int(grid.get("width"), name="instance.grid.width", phase="input")
    height = _strict_int(grid.get("height"), name="instance.grid.height", phase="input")
    if (width, height) != required_grid:
        _fail(
            "GRID_CONTRACT_MISMATCH",
            f"expected {required_grid}, observed {(width, height)}",
            phase="input",
        )
    return width, height


def _manufacturing_instance_ids(
    instance: Mapping[str, Any],
    *,
    placement_ids: frozenset[str],
    phase: str,
) -> frozenset[str]:
    manufacturing_ids: set[str] = set()
    seen_groups: set[str] = set()
    groups = _strict_sequence(
        instance.get("operation_groups"), name="instance.operation_groups", phase=phase
    )
    for index, raw_group in enumerate(groups):
        group = _strict_mapping(raw_group, name=f"instance.operation_groups[{index}]", phase=phase)
        group_id = _strict_string(
            group.get("id"), name=f"instance.operation_groups[{index}].id", phase=phase
        )
        if group_id in seen_groups:
            _fail("DUPLICATE_OPERATION_GROUP", group_id, phase=phase)
        seen_groups.add(group_id)
        raw_instance_ids = _strict_sequence(
            group.get("instance_ids"),
            name=f"instance.operation_groups[{index}].instance_ids",
            phase=phase,
        )
        group_instance_ids = [
            _strict_string(
                value,
                name=f"instance.operation_groups[{index}].instance_ids[{item_index}]",
                phase=phase,
            )
            for item_index, value in enumerate(raw_instance_ids)
        ]
        if len(group_instance_ids) != len(set(group_instance_ids)):
            _fail("DUPLICATE_MANUFACTURING_INSTANCE", group_id, phase=phase)
        count = _strict_int(
            group.get("count"), name=f"instance.operation_groups[{index}].count", phase=phase
        )
        if count <= 0 or count != len(group_instance_ids):
            _fail(
                "OPERATION_GROUP_INSTANCE_COUNT",
                f"{group_id} declares {count} instances but lists {len(group_instance_ids)}",
                phase=phase,
            )
        duplicate_across_groups = sorted(set(group_instance_ids) & manufacturing_ids)
        if duplicate_across_groups:
            _fail(
                "DUPLICATE_MANUFACTURING_INSTANCE",
                repr(duplicate_across_groups),
                phase=phase,
            )
        manufacturing_ids.update(group_instance_ids)
    missing_geometry = sorted(manufacturing_ids - placement_ids)
    if missing_geometry:
        _fail(
            "MANUFACTURING_GEOMETRY_MISSING",
            f"manufacturing instances are absent from geometry {missing_geometry}",
            phase=phase,
        )
    return frozenset(manufacturing_ids)


def _normalize_selected_port_bindings(
    value: object,
    *,
    name: str,
    placement_ids: frozenset[str],
    commodities: frozenset[str],
    phase: str,
) -> dict[str, dict[str, str]]:
    root = _strict_mapping(value, name=name, phase=phase)
    normalized: dict[str, dict[str, str]] = {}
    for raw_instance_id in sorted(root):
        instance_id = _strict_string(raw_instance_id, name=f"{name} instance ID", phase=phase)
        if instance_id not in placement_ids:
            _fail(
                "UNKNOWN_BINDING_INSTANCE",
                f"{name} references unknown placement {instance_id!r}",
                phase=phase,
            )
        raw_bindings = _strict_mapping(root[raw_instance_id], name=f"{name}.{instance_id}", phase=phase)
        bindings: dict[str, str] = {}
        for raw_port_id in sorted(raw_bindings):
            port_id = _strict_string(raw_port_id, name=f"{name}.{instance_id} port ID", phase=phase)
            commodity = _strict_string(
                raw_bindings[raw_port_id], name=f"{name}.{instance_id}.{port_id}", phase=phase
            )
            if commodity not in commodities:
                _fail(
                    "UNKNOWN_BINDING_COMMODITY",
                    f"{name}.{instance_id}.{port_id} names {commodity!r}",
                    phase=phase,
                )
            bindings[port_id] = commodity
        normalized[instance_id] = bindings
    return normalized


def select_port_bindings_for_geometry(
    geometry: GeometryInput,
    *,
    instance: Mapping[str, Any],
    required_placements: Sequence[Mapping[str, Any]],
    optional_placements: Sequence[Mapping[str, Any]],
    allowed_access_cells: frozenset[tuple[int, int]],
    choose_port_bindings: Callable[..., Mapping[str, Mapping[str, str]]],
    phase: str = "binding",
) -> tuple[dict[str, dict[str, str]], frozenset[str]]:
    """Merge automatic generic bindings with the hash-bound manufacturing map."""

    placement_ids = frozenset(
        _strict_string(record.get("instance_id"), name="placement.instance_id", phase=phase)
        for record in (*required_placements, *optional_placements)
    )
    if len(placement_ids) != len(required_placements) + len(optional_placements):
        _fail("DUPLICATE_PLACEMENT_ID", "binding geometry repeats an instance ID", phase=phase)
    manufacturing_ids = _manufacturing_instance_ids(
        instance, placement_ids=placement_ids, phase=phase
    )
    explicit_ids = set(geometry.manufacturing_port_bindings)
    if explicit_ids != set(manufacturing_ids):
        _fail(
            "MANUFACTURING_BINDING_ID_SET",
            (
                f"missing={sorted(set(manufacturing_ids) - explicit_ids)}, "
                f"extra={sorted(explicit_ids - set(manufacturing_ids))}"
            ),
            phase=phase,
        )
    commodities = frozenset(_instance_commodities(instance))
    explicit = _normalize_selected_port_bindings(
        geometry.manufacturing_port_bindings,
        name="geometry.manufacturing_port_bindings",
        placement_ids=placement_ids,
        commodities=commodities,
        phase=phase,
    )
    automatic_value = choose_port_bindings(
        instance,
        required_placements=required_placements,
        optional_placements=optional_placements,
        allowed_access_cells=allowed_access_cells,
    )
    automatic = _normalize_selected_port_bindings(
        automatic_value,
        name="automatic_port_bindings",
        placement_ids=placement_ids,
        commodities=commodities,
        phase=phase,
    )
    generic = {
        instance_id: bindings
        for instance_id, bindings in automatic.items()
        if instance_id not in manufacturing_ids
    }
    return {**generic, **explicit}, manufacturing_ids


def assert_manufacturing_bindings_preserved(
    bound_required: Sequence[Mapping[str, Any]],
    *,
    expected: Mapping[str, Mapping[str, str]],
    manufacturing_ids: frozenset[str],
    phase: str = "binding",
) -> None:
    """Read back every non-null manufacturing binding after strict binding."""

    observed: dict[str, dict[str, str]] = {}
    for index, raw_placement in enumerate(bound_required):
        placement = _strict_mapping(raw_placement, name=f"bound.required[{index}]", phase=phase)
        instance_id = _strict_string(
            placement.get("instance_id"), name=f"bound.required[{index}].instance_id", phase=phase
        )
        if instance_id not in manufacturing_ids:
            continue
        if instance_id in observed:
            _fail("DUPLICATE_BOUND_MANUFACTURING_ID", instance_id, phase=phase)
        raw_bindings = _strict_mapping(
            placement.get("port_bindings"),
            name=f"bound.required[{index}].port_bindings",
            phase=phase,
        )
        active: dict[str, str] = {}
        for raw_port_id, raw_commodity in raw_bindings.items():
            port_id = _strict_string(
                raw_port_id,
                name=f"bound.required[{index}].port_bindings port ID",
                phase=phase,
            )
            if raw_commodity is None:
                continue
            active[port_id] = _strict_string(
                raw_commodity,
                name=f"bound.required[{index}].port_bindings.{port_id}",
                phase=phase,
            )
        observed[instance_id] = dict(sorted(active.items()))
    expected_normalized = {
        instance_id: dict(sorted(bindings.items()))
        for instance_id, bindings in sorted(expected.items())
    }
    if observed != expected_normalized or set(observed) != set(manufacturing_ids):
        _fail(
            "MANUFACTURING_BINDING_OVERRIDE_DRIFT",
            "bound manufacturing ports differ from the hash-bound geometry map",
            phase=phase,
        )


def _instance_commodities(instance: Mapping[str, Any]) -> list[str]:
    values = _strict_sequence(instance.get("commodities"), name="instance.commodities", phase="binding")
    commodities = [_strict_string(v, name="instance commodity", phase="binding") for v in values]
    if not commodities or len(commodities) != len(set(commodities)):
        _fail("INSTANCE_COMMODITIES", "commodity list must be nonempty and unique", phase="binding")
    return sorted(commodities)


def _as_cgroup_dict(record: object) -> dict[str, Any]:
    value = record.as_dict() if callable(getattr(record, "as_dict", None)) else record
    result = _json_copy(value, name="cgroup telemetry", phase="telemetry")
    if not isinstance(result, dict):
        _fail("CGROUP_TELEMETRY_SHAPE", "cgroup telemetry must serialize as an object", phase="telemetry")
    return result


def _reject(
    *,
    classification: str,
    phase: str,
    message: str,
    telemetry: Mapping[str, Any],
    error_code: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "status": "REJECTED",
        "classification": classification,
        "phase": phase,
        "message": message,
        "route_components": [],
        "telemetry": _json_copy(dict(telemetry), name="rejection telemetry", phase="output"),
    }
    if error_code is not None:
        result["error_code"] = error_code
    return result


def run_fixed_geometry_router(
    payload: object,
    *,
    instance: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
    dependencies: WorkerDependencies,
    config: WorkerConfig,
) -> dict[str, Any]:
    """Run one exact fixed-geometry attempt and return strict JSON data.

    Only ``status == FEASIBLE`` carries route components.  Every timeout,
    unknown status, adapter/checker failure, cgroup contract failure, or Python
    exception returns ``REJECTED`` with an empty route list.
    """

    phase = "input"
    started = time.perf_counter()
    stage_started = started
    telemetry: dict[str, Any] = {"stage_seconds": {}}

    def finish_stage(name: str) -> None:
        nonlocal stage_started
        now = time.perf_counter()
        telemetry["stage_seconds"][name] = max(0.0, now - stage_started)
        stage_started = now

    try:
        config.validate()
        geometry = parse_geometry_payload(payload, minimum_poles=config.minimum_poles)
        width, height = _grid_dimensions(instance, config.required_grid)
        required_geometry = [dict(record) for record in geometry.required_placements]
        optional_geometry = _pole_records(geometry.pole_anchors)
        telemetry.update(
            {
                "required_placement_count": len(required_geometry),
                "pole_count": len(optional_geometry),
                "grid": {"width": width, "height": height},
                "geometry_digest": canonical_digest(payload),
            }
        )
        finish_stage("input")

        phase = "pose_replay"
        placement_solution = dependencies.resolve_placement_solution(
            instance=instance,
            required_placements=required_geometry,
            optional_placements=optional_geometry,
            facility_pools=facility_pools,
        )
        if not isinstance(placement_solution, Mapping):
            _fail("PLACEMENT_SOLUTION_SHAPE", "pose replay did not return a mapping", phase=phase)
        expected_ids = {
            str(record["instance_id"]) for record in (*required_geometry, *optional_geometry)
        }
        if set(placement_solution) != expected_ids:
            _fail("PLACEMENT_SOLUTION_IDS", "pose replay changed the placement ID set", phase=phase)
        finish_stage(phase)

        phase = "routing_context"
        context = dependencies.build_routing_context(
            placement_solution, facility_pools, width, height
        )
        occupied_cells = frozenset(getattr(context, "occupied_cells", ()))
        occupied_owner_by_cell = dict(getattr(context, "occupied_owner_by_cell", {}))
        component_by_cell = dict(getattr(context, "component_by_cell", {}))
        if set(occupied_owner_by_cell) != set(occupied_cells):
            _fail("OCCUPANCY_OWNER_MISMATCH", "every occupied cell needs exactly one owner", phase=phase)
        allowed_access_cells = frozenset(component_by_cell)
        finish_stage(phase)

        phase = "binding"
        selected_port_bindings, manufacturing_ids = select_port_bindings_for_geometry(
            geometry,
            instance=instance,
            required_placements=required_geometry,
            optional_placements=optional_geometry,
            allowed_access_cells=allowed_access_cells,
            choose_port_bindings=dependencies.choose_port_bindings,
            phase=phase,
        )
        bound = dependencies.bind_placements(
            instance,
            required_placements=required_geometry,
            optional_placements=optional_geometry,
            selected_port_bindings=selected_port_bindings,
            allowed_access_cells=allowed_access_cells,
        )
        if not isinstance(bound, Mapping):
            _fail("BOUND_PLACEMENT_SHAPE", "binding result is not an object", phase=phase)
        bound_required = list(
            _strict_sequence(bound.get("required_placements"), name="bound.required_placements", phase=phase)
        )
        bound_optional = list(
            _strict_sequence(bound.get("optional_placements"), name="bound.optional_placements", phase=phase)
        )
        if len(bound_required) != len(required_geometry) or len(bound_optional) != len(optional_geometry):
            _fail("BOUND_PLACEMENT_COUNT", "binding changed the placement counts", phase=phase)
        assert_manufacturing_bindings_preserved(
            bound_required,
            expected=geometry.manufacturing_port_bindings,
            manufacturing_ids=manufacturing_ids,
            phase=phase,
        )
        all_bound = [*bound_required, *bound_optional]
        port_specs = [
            dict(spec)
            for spec in dependencies.derive_port_specs(
                instance,
                required_placements=bound_required,
                optional_placements=bound_optional,
            )
        ]
        commodities = _instance_commodities(instance)
        active_commodities = sorted({str(spec.get("commodity", "")) for spec in port_specs})
        if active_commodities != commodities:
            _fail(
                "ACTIVE_COMMODITY_SET_MISMATCH",
                "active production port specs do not cover the strict commodity set",
                phase=phase,
            )
        strict_occupied = frozenset(dependencies.occupied_body_cells(instance, all_bound))
        if strict_occupied != occupied_cells:
            _fail(
                "STRICT_PRODUCTION_OCCUPANCY_MISMATCH",
                "strict body occupancy disagrees with production candidate-pose occupancy",
                phase=phase,
            )
        terminal_cells = frozenset((int(spec["x"]), int(spec["y"])) for spec in port_specs)
        telemetry.update(
            {
                "port_spec_count": len(port_specs),
                "terminal_cell_count": len(terminal_cells),
                "commodity_count": len(commodities),
                "occupied_cell_count": len(occupied_cells),
                "port_specs_digest": canonical_digest(port_specs),
                "manufacturing_binding_instance_count": len(manufacturing_ids),
                "manufacturing_binding_port_count": sum(
                    len(bindings) for bindings in geometry.manufacturing_port_bindings.values()
                ),
                "manufacturing_port_bindings_digest": canonical_digest(
                    geometry.manufacturing_port_bindings
                ),
            }
        )
        finish_stage(phase)

        phase = "routing_precheck"
        placement_core = dependencies.make_placement_core(
            occupied_cells, occupied_owner_by_cell=occupied_owner_by_cell
        )
        precheck = dependencies.routing_precheck(
            placement_core=placement_core,
            port_specs=port_specs,
            occupied_owner_by_cell=occupied_owner_by_cell,
        )
        if not isinstance(precheck, Mapping):
            _fail("PRECHECK_SHAPE", "routing precheck did not return an object", phase=phase)
        precheck_status = precheck.get("status")
        safe_reject = precheck.get("binding_selection_safe_reject")
        if type(precheck_status) is not str or type(safe_reject) is not bool:
            _fail("PRECHECK_CONTRACT", "routing precheck status contract is malformed", phase=phase)
        telemetry["routing_precheck"] = {
            "status": precheck_status,
            "binding_selection_safe_reject": safe_reject,
            "domain_stats": _json_copy(precheck.get("domain_stats", {}), name="domain_stats", phase=phase),
        }
        if precheck_status != "feasible":
            if safe_reject and precheck_status in {"front_blocked", "relaxed_disconnected"}:
                telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
                return _reject(
                    classification="ROUTING_PRECHECK_REJECTED",
                    phase=phase,
                    message=str(precheck_status),
                    telemetry=telemetry,
                )
            _fail("PRECHECK_UNVERIFIED_STATUS", repr(precheck_status), phase=phase)
        analysis = precheck.get("_analysis")
        if not isinstance(analysis, Mapping):
            _fail("PRECHECK_ANALYSIS_MISSING", "feasible precheck lacks its exact analysis", phase=phase)
        finish_stage(phase)

        phase = "routing_build"
        routing_grid = dependencies.make_routing_grid(placement_core, port_specs)
        router = dependencies.make_routing_subproblem(
            routing_grid, commodities, domain_analysis=analysis
        )
        router.build()
        build_stats = getattr(router, "build_stats", None)
        if not isinstance(build_stats, Mapping):
            _fail("ROUTING_BUILD_STATS", "router build_stats is missing", phase=phase)
        if build_stats.get("domain_status_contract_violation") is not None:
            _fail("ROUTING_BUILD_DOMAIN_CONTRACT", "router rejected the precheck status contract", phase=phase)
        physical_vars = getattr(router, "phys_vars", None)
        model = getattr(router, "model", None)
        if not isinstance(physical_vars, Mapping) or model is None:
            _fail("ROUTING_BUILD_SURFACE", "router model/phys_vars is missing", phase=phase)
        l1_requirements = tuple(
            dependencies.add_l1_support_constraints(
                model, physical_vars, terminal_cells=terminal_cells
            )
        )
        telemetry["routing_build"] = {
            "stats": _json_copy(dict(build_stats), name="routing build stats", phase=phase),
            "physical_state_count": len(physical_vars),
            "l1_state_count": len(l1_requirements),
            "l1_forbidden_terminal_count": sum(
                bool(getattr(requirement, "forbidden_at_terminal", False))
                for requirement in l1_requirements
            ),
        }
        finish_stage(phase)

        phase = "routing_solve"
        cgroup_start: Any = None
        cgroup_record: dict[str, Any]
        if config.require_cgroup:
            assert config.expected_unit_name is not None
            try:
                cgroup_start = dependencies.begin_cgroup_telemetry(config.expected_unit_name)
            except Exception as exc:  # noqa: BLE001 - cgroup contract is an acceptance gate
                telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
                return _reject(
                    classification="CGROUP_TELEMETRY_FAILED",
                    phase="telemetry",
                    message=type(exc).__name__,
                    telemetry=telemetry,
                    error_code=getattr(exc, "code", None),
                )
        solve_exception: Exception | None = None
        routing_status: object = None
        try:
            routing_status = router.solve(time_limit=float(config.time_limit_seconds))
        except Exception as exc:  # noqa: BLE001 - classification boundary
            solve_exception = exc
        try:
            if config.require_cgroup:
                cgroup_record = _as_cgroup_dict(dependencies.finish_cgroup_telemetry(cgroup_start))
            else:
                cgroup_record = {"required": False, "oom_attribution": "NO_CGROUP_OOM"}
        except Exception as exc:  # noqa: BLE001 - telemetry is an acceptance gate
            telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
            return _reject(
                classification="CGROUP_TELEMETRY_FAILED",
                phase="telemetry",
                message=type(exc).__name__,
                telemetry=telemetry,
                error_code=getattr(exc, "code", None),
            )
        telemetry["cgroup"] = cgroup_record
        oom_attribution = cgroup_record.get("oom_attribution")
        if oom_attribution not in {"NO_CGROUP_OOM", "CGROUP_OOM_EVENT", "CGROUP_OOM_KILL"}:
            _fail("CGROUP_OOM_ATTRIBUTION", repr(oom_attribution), phase="telemetry")
        if oom_attribution != "NO_CGROUP_OOM":
            telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
            return _reject(
                classification="CGROUP_OOM",
                phase="telemetry",
                message=str(cgroup_record.get("oom_attribution")),
                telemetry=telemetry,
            )
        if solve_exception is not None:
            raise solve_exception
        telemetry["routing_status"] = routing_status
        finish_stage(phase)
        if routing_status == "INFEASIBLE":
            telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
            return _reject(
                classification="ROUTING_INFEASIBLE",
                phase=phase,
                message="production router proved the fixed binding infeasible",
                telemetry=telemetry,
            )
        if routing_status == "TIMEOUT":
            telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
            return _reject(
                classification="ROUTING_TIMEOUT_UNPROVEN",
                phase=phase,
                message="production router did not produce an accepted incumbent",
                telemetry=telemetry,
            )
        if routing_status != "FEASIBLE":
            _fail("ROUTING_STATUS_UNKNOWN", repr(routing_status), phase=phase)

        phase = "route_extract"
        production_routes = router.extract_routes()
        if not isinstance(production_routes, Sequence):
            _fail("ROUTE_EXTRACTION_SHAPE", "extract_routes did not return an array", phase=phase)
        strict_components = [
            dict(component)
            for component in dependencies.adapt_extracted_routes(
                production_routes, terminal_cells=terminal_cells
            )
        ]
        telemetry.update(
            {
                "production_route_state_count": len(production_routes),
                "strict_route_component_count": len(strict_components),
            }
        )
        finish_stage(phase)

        phase = "independent_reachability"
        terminals = list(dependencies.terminals_from_witness(instance, all_bound))
        if len(terminals) != len(port_specs):
            _fail(
                "TERMINAL_PORT_SPEC_COUNT_MISMATCH",
                "strict terminals and production port specs have different cardinality",
                phase=phase,
            )
        terminal_role_counts = {
            commodity: {
                "source": sum(
                    getattr(terminal, "kind", None) == "output"
                    and getattr(terminal, "commodity", None) == commodity
                    for terminal in terminals
                ),
                "sink": sum(
                    getattr(terminal, "kind", None) == "input"
                    and getattr(terminal, "commodity", None) == commodity
                    for terminal in terminals
                ),
            }
            for commodity in commodities
        }
        incomplete_roles = {
            commodity: counts
            for commodity, counts in terminal_role_counts.items()
            if counts["source"] <= 0 or counts["sink"] <= 0
        }
        if incomplete_roles:
            _fail(
                "INCOMPLETE_COMMODITY_TERMINALS",
                repr(incomplete_roles),
                phase=phase,
            )
        dependencies.assert_terminal_route_reachability(
            strict_components, terminals, commodities
        )
        component_cells = {
            (int(component["cell"]["x"]), int(component["cell"]["y"]))
            for component in strict_components
        }
        if component_cells & occupied_cells:
            _fail("ROUTE_BODY_COLLISION", "adapted routes cross a strict facility body", phase=phase)
        telemetry["independent_reachability"] = {
            "status": "PASS",
            "terminal_count": len(terminals),
            "source_count": sum(counts["source"] for counts in terminal_role_counts.values()),
            "sink_count": sum(counts["sink"] for counts in terminal_role_counts.values()),
            "terminal_role_counts": terminal_role_counts,
            "component_cell_count": len(component_cells),
        }
        finish_stage(phase)

        phase = "output"
        strict_components = _json_copy(strict_components, name="strict route components", phase=phase)
        result = {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "status": "FEASIBLE",
            "classification": "STRICT_ROUTES_INDEPENDENTLY_REACHABLE",
            "claim_boundary": "research_witness_candidate_only",
            "required_placements": _json_copy(bound_required, name="bound required placements", phase=phase),
            "optional_placements": _json_copy(bound_optional, name="bound optional placements", phase=phase),
            "port_specs": _json_copy(port_specs, name="port specs", phase=phase),
            "route_components": strict_components,
            "telemetry": telemetry,
        }
        result["route_components_digest"] = canonical_digest(strict_components)
        telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
        return _json_copy(result, name="worker result", phase=phase)
    except FixedGeometryRouterError as exc:
        telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
        return _reject(
            classification="FAIL_CLOSED_CONTRACT_ERROR",
            phase=exc.phase,
            message=str(exc),
            telemetry=telemetry,
            error_code=exc.code,
        )
    except Exception as exc:  # noqa: BLE001 - worker crash classification boundary
        telemetry["total_seconds"] = max(0.0, time.perf_counter() - started)
        return _reject(
            classification="FAIL_CLOSED_EXCEPTION",
            phase=phase,
            message=type(exc).__name__,
            telemetry=telemetry,
            error_code=getattr(exc, "code", None),
        )


def _production_pose_resolver(
    *,
    strict_contract: Any,
    geometry_module: Any,
) -> Callable[..., Mapping[str, Mapping[str, Any]]]:
    """Return exact strict/candidate pose replay used by the production deps."""

    candidate_to_strict_template = dict(strict_contract.CANDIDATE_TEMPLATE_TO_STRICT)
    candidate_to_strict_mode = dict(strict_contract.CANDIDATE_MODE_TO_STRICT)
    strict_to_candidate_template = {value: key for key, value in candidate_to_strict_template.items()}
    strict_to_candidate_mode = {value: key for key, value in candidate_to_strict_mode.items()}
    if len(strict_to_candidate_template) != len(candidate_to_strict_template):
        raise RuntimeError("candidate-to-strict template map is not injective")
    if len(strict_to_candidate_mode) != len(candidate_to_strict_mode):
        raise RuntimeError("candidate-to-strict mode map is not injective")

    def resolve(
        *,
        instance: Mapping[str, Any],
        required_placements: Sequence[Mapping[str, Any]],
        optional_placements: Sequence[Mapping[str, Any]],
        facility_pools: Mapping[str, Any],
    ) -> Mapping[str, Mapping[str, Any]]:
        required_rows = {
            str(row["id"]): row
            for row in _strict_sequence(instance.get("required_instances"), name="required_instances", phase="pose_replay")
        }
        strict_modes = {
            (str(template_id), str(mode["id"])): mode
            for template_id, template in _strict_mapping(
                instance.get("facility_templates"), name="facility_templates", phase="pose_replay"
            ).items()
            for mode in _strict_sequence(template.get("modes"), name="template.modes", phase="pose_replay")
        }
        solution: dict[str, dict[str, Any]] = {}
        for is_required, placement in (
            *((True, p) for p in required_placements),
            *((False, p) for p in optional_placements),
        ):
            instance_id = str(placement["instance_id"])
            strict_template = str(placement["template"])
            strict_mode = str(placement["mode"])
            anchor = placement["anchor"]
            candidate_template = strict_to_candidate_template.get(strict_template)
            candidate_mode = strict_to_candidate_mode.get(strict_mode)
            if candidate_template is None or candidate_mode is None:
                _fail("POSE_MAPPING_MISSING", f"{strict_template}/{strict_mode}", phase="pose_replay")
            pool = facility_pools.get(candidate_template)
            if not isinstance(pool, Sequence):
                _fail("POSE_POOL_MISSING", candidate_template, phase="pose_replay")
            matches: list[tuple[int, Mapping[str, Any]]] = []
            for pose_idx, raw_pose in enumerate(pool):
                if not isinstance(raw_pose, Mapping):
                    continue
                pose_anchor = raw_pose.get("anchor")
                params = raw_pose.get("pose_params")
                if not isinstance(pose_anchor, Mapping) or not isinstance(params, Mapping):
                    continue
                if (
                    pose_anchor.get("x") == anchor["x"]
                    and pose_anchor.get("y") == anchor["y"]
                    and params.get("port_mode") == candidate_mode
                ):
                    matches.append((pose_idx, raw_pose))
            if len(matches) != 1:
                _fail(
                    "POSE_MATCH_COUNT",
                    f"{instance_id} matched {len(matches)} candidate poses",
                    phase="pose_replay",
                )
            pose_idx, pose = matches[0]
            strict_mode_record = strict_modes.get((strict_template, strict_mode))
            if strict_mode_record is None:
                _fail("STRICT_MODE_MISSING", f"{strict_template}/{strict_mode}", phase="pose_replay")
            strict_geometry = geometry_module.strict_mode_geometry(
                strict_mode_record, (int(anchor["x"]), int(anchor["y"]))
            )
            candidate_geometry = geometry_module.candidate_pose_geometry(pose)
            if (
                strict_geometry.body_cells != candidate_geometry.body_cells
                or set(strict_geometry.input_front_cells) != set(candidate_geometry.input_front_cells)
                or set(strict_geometry.output_front_cells) != set(candidate_geometry.output_front_cells)
            ):
                _fail("STRICT_CANDIDATE_GEOMETRY_MISMATCH", instance_id, phase="pose_replay")
            if is_required:
                required = required_rows.get(instance_id)
                if not isinstance(required, Mapping):
                    _fail("REQUIRED_INSTANCE_MISSING", instance_id, phase="pose_replay")
                operation = str(required.get("operation", ""))
            else:
                operation = "power_supply" if strict_template == "power_pole" else "box_sink"
            solution[instance_id] = {
                "instance_id": instance_id,
                "facility_type": candidate_template,
                "operation_type": operation,
                "pose_idx": pose_idx,
                "pose_id": str(pose.get("pose_id", "")),
                "anchor": {"x": int(anchor["x"]), "y": int(anchor["y"])},
                "is_mandatory": bool(is_required),
                "bound_type": "research_fixed_geometry",
                "solve_mode": "research_witness",
            }
        return solution

    return resolve


def production_dependencies() -> WorkerDependencies:
    """Bind to real APIs without launching or bypassing the supervisor mutex."""

    base = "docs.research.witness_constructor_20260717.07_routing_aware"
    witness_io = importlib.import_module(f"{base}.witness_io")
    network_router = importlib.import_module(f"{base}.network_router")
    route_adapter = importlib.import_module(f"{base}.route_adapter")
    strict_contract = importlib.import_module(f"{base}.strict_contract")
    geometry_module = importlib.import_module(f"{base}.geometry")
    cgroup_telemetry = importlib.import_module(f"{base}.cgroup_telemetry")

    from src.models.routing_binding_context import build_routing_binding_context
    from src.models.routing_subproblem import (
        RoutingGrid,
        RoutingPlacementCore,
        RoutingSubproblem,
        run_exact_routing_precheck,
    )

    return WorkerDependencies(
        resolve_placement_solution=_production_pose_resolver(
            strict_contract=strict_contract, geometry_module=geometry_module
        ),
        build_routing_context=build_routing_binding_context,
        choose_port_bindings=witness_io.choose_port_bindings,
        bind_placements=witness_io.bind_placements,
        derive_port_specs=witness_io.derive_production_port_specs,
        occupied_body_cells=network_router.occupied_body_cells,
        make_placement_core=RoutingPlacementCore.from_occupied_cells,
        routing_precheck=run_exact_routing_precheck,
        make_routing_grid=RoutingGrid.from_placement_core,
        make_routing_subproblem=RoutingSubproblem,
        add_l1_support_constraints=route_adapter.add_l1_support_constraints,
        adapt_extracted_routes=route_adapter.adapt_extracted_routes,
        terminals_from_witness=network_router.terminals_from_witness,
        assert_terminal_route_reachability=network_router.assert_terminal_route_reachability,
        begin_cgroup_telemetry=lambda unit: cgroup_telemetry.begin_worker_cgroup_telemetry(
            expected_unit_name=unit
        ),
        finish_cgroup_telemetry=cgroup_telemetry.finish_worker_cgroup_telemetry,
    )


def run_supervised_fixed_geometry_router(
    geometry_path: Path,
    *,
    expected_geometry_sha256: str,
    project_root: Path,
    config: WorkerConfig,
) -> dict[str, Any]:
    """Hash-pinned production entry to call while ``run_supervisor`` holds its lock.

    This function does not acquire the global mutex itself.  That ownership
    must span process launch and result publication in the supervisor.  Here we
    pin the explicit geometry bytes, reconcile every production dependency,
    run the exact worker, and then repeat both snapshots so any mid-attempt
    drift discards even an otherwise feasible incumbent.
    """

    telemetry: dict[str, Any] = {}
    try:
        payload = load_geometry_payload(
            Path(geometry_path), expected_sha256=expected_geometry_sha256
        )
        snapshot_before = load_production_input_snapshot(Path(project_root))
        dependencies = production_dependencies()
    except FixedGeometryRouterError as exc:
        return _reject(
            classification="INPUT_SNAPSHOT_REJECTED",
            phase=exc.phase,
            message=str(exc),
            telemetry=telemetry,
            error_code=exc.code,
        )
    except Exception as exc:  # noqa: BLE001 - production dependency boundary
        return _reject(
            classification="INPUT_SNAPSHOT_REJECTED",
            phase="dependency_load",
            message=type(exc).__name__,
            telemetry=telemetry,
            error_code=getattr(exc, "code", None),
        )

    result = run_fixed_geometry_router(
        payload,
        instance=snapshot_before.instance,
        facility_pools=snapshot_before.facility_pools,
        dependencies=dependencies,
        config=config,
    )
    try:
        # Re-read, rather than trusting a path or a pre-solve object identity.
        load_geometry_payload(
            Path(geometry_path), expected_sha256=expected_geometry_sha256
        )
        snapshot_after = load_production_input_snapshot(Path(project_root))
        if dict(snapshot_after.hashes) != dict(snapshot_before.hashes):
            _fail(
                "DEPENDENCY_HASH_DRIFT",
                "production dependency hashes changed during the attempt",
                phase="post_solve_snapshot",
            )
    except FixedGeometryRouterError as exc:
        return _reject(
            classification="POST_SOLVE_SNAPSHOT_REJECTED",
            phase=exc.phase,
            message=str(exc),
            telemetry={"input_hashes_before": dict(snapshot_before.hashes)},
            error_code=exc.code,
        )
    except Exception as exc:  # noqa: BLE001 - post-solve acceptance boundary
        return _reject(
            classification="POST_SOLVE_SNAPSHOT_REJECTED",
            phase="post_solve_snapshot",
            message=type(exc).__name__,
            telemetry={"input_hashes_before": dict(snapshot_before.hashes)},
            error_code=getattr(exc, "code", None),
        )

    normalized = _json_copy(result, name="supervised worker result", phase="output")
    normalized_telemetry = normalized.get("telemetry")
    if not isinstance(normalized_telemetry, dict):
        return _reject(
            classification="RESULT_TELEMETRY_REJECTED",
            phase="output",
            message="worker result telemetry is not an object",
            telemetry={},
        )
    normalized_telemetry["input_snapshot"] = {
        "geometry_sha256": expected_geometry_sha256,
        "dependency_hashes": dict(sorted(snapshot_before.hashes.items())),
        "post_solve_revalidated": True,
    }
    return normalized


def create_unique_run_directory(parent: Path, run_id: str) -> Path:
    """Create one explicit attempt directory; never discover or reuse latest."""

    if _RUN_ID_RE.fullmatch(run_id) is None:
        _fail("RUN_ID_INVALID", repr(run_id), phase="output")
    base = Path(parent).resolve(strict=True)
    if not base.is_dir():
        _fail("RUN_PARENT_INVALID", str(base), phase="output")
    target = base / run_id
    try:
        target.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError:
        _fail("RUN_DIRECTORY_EXISTS", str(target), phase="output")
    except OSError as exc:
        _fail("RUN_DIRECTORY_CREATE_FAILED", str(exc), phase="output")
    return target


def write_result_exclusive(path: Path, result: Mapping[str, Any]) -> None:
    """Serialize strict JSON to a new path only (no overwrite or latest link)."""

    try:
        payload = (
            json.dumps(
                result,
                ensure_ascii=True,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        _fail("RESULT_NOT_JSON", str(exc), phase="output")
    target = Path(path)
    try:
        with target.open("xb") as handle:
            handle.write(payload)
            handle.flush()
    except FileExistsError:
        _fail("RESULT_ALREADY_EXISTS", str(target), phase="output")
    except OSError as exc:
        _fail("RESULT_WRITE_FAILED", str(exc), phase="output")


__all__ = [
    "FixedGeometryRouterError",
    "GeometryInput",
    "INPUT_SCHEMA_VERSION",
    "OUTPUT_SCHEMA_VERSION",
    "ProductionInputSnapshot",
    "WorkerConfig",
    "WorkerDependencies",
    "assert_manufacturing_bindings_preserved",
    "canonical_digest",
    "create_unique_run_directory",
    "load_geometry_payload",
    "load_production_input_snapshot",
    "parse_geometry_payload",
    "production_dependencies",
    "run_fixed_geometry_router",
    "run_supervised_fixed_geometry_router",
    "select_port_bindings_for_geometry",
    "write_result_exclusive",
]
