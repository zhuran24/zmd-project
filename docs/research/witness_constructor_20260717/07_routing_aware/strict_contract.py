"""Read-only input contract for the routing-aware research witness.

This module deliberately uses only the Python standard library.  It pins the
released inputs byte-for-byte, then independently reconciles the canonical
rules, mandatory instances, generic I/O requirements, candidate poses, and the
clean-room strict instance.  It never writes to any of those inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[4]

STRICT_INSTANCE_RELATIVE_PATH = Path(
    "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
)
CANONICAL_RULES_RELATIVE_PATH = Path("rules/canonical_rules.json")
MANDATORY_INSTANCES_RELATIVE_PATH = Path("data/preprocessed/mandatory_exact_instances.json")
GENERIC_IO_RELATIVE_PATH = Path("data/preprocessed/generic_io_requirements.json")
CANDIDATE_POSES_RELATIVE_PATH = Path("data/preprocessed/candidate_placements.json")

EXPECTED_SHA256 = {
    "strict_instance": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    # 2026-08-05 freeze-ritual: globals.empty_rectangle gained the owner-adjudicated
    # emptiness definition.  Purely additive metadata — grid, templates, recipes and
    # targets are byte-identical, so every count/geometry below is unaffected.
    "canonical_rules": "c3666d78d5dd1329514c7813be9f91f09cb3ce7b94907ef5b6ce746c9bcbbbd5",
    "mandatory_instances": "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    "generic_io": "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    "candidate_poses": "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
}

EXPECTED_CANDIDATE_COUNTS = {
    "boundary_storage_port": 136,
    "manufacturing_3x3": 17_952,
    "manufacturing_5x5": 16_896,
    "manufacturing_6x4": 16_900,
    "power_pole": 4_761,
    "protocol_core": 7_688,
    "protocol_storage_box": 18_496,
}

EXPECTED_RECONCILIATION = {
    "mandatory_instances": 266,
    "required_body_area": 3_544,
    "manufacturing_instances": 219,
    "commodities": 19,
    "operation_groups": 17,
    "manufacturing_sources": 264,
    "manufacturing_sinks": 310,
    "generic_sources": 52,
    "generic_sinks": 2,
    "sources": 316,
    "sinks": 312,
    "active_terminals": 628,
    "physical_ports_no_box": 1_804,
    "null_ports_no_box": 1_176,
}

DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}

CANDIDATE_TEMPLATE_TO_STRICT = {
    "manufacturing_3x3": "manufacturing_3x3",
    "manufacturing_5x5": "manufacturing_5x5",
    "manufacturing_6x4": "manufacturing_6x4",
    "protocol_core": "protocol_core",
    "protocol_storage_box": "storage_box",
    "power_pole": "power_pole",
    "boundary_storage_port": "boundary_storage_port",
}

CANDIDATE_MODE_TO_STRICT = {
    "TB": "north_to_south",
    "BT": "south_to_north",
    "RL": "east_to_west",
    "LR": "west_to_east",
    "core_LR_out": "inputs_north_south",
    "core_TB_out": "inputs_east_west",
    "omni": "fixed",
    "left_base": "left_boundary",
    "bottom_base": "bottom_boundary",
}

class InputContractError(ValueError):
    """The released inputs or their cross-file reconciliation are invalid."""


@dataclass(frozen=True)
class LoadedDocument:
    path: Path
    sha256: str
    value: Any


@dataclass(frozen=True)
class InputBundle:
    strict_instance: LoadedDocument
    canonical_rules: LoadedDocument
    mandatory_instances: LoadedDocument
    generic_io: LoadedDocument
    candidate_poses: LoadedDocument

    @property
    def hashes(self) -> dict[str, str]:
        return {
            "strict_instance": self.strict_instance.sha256,
            "canonical_rules": self.canonical_rules.sha256,
            "mandatory_instances": self.mandatory_instances.sha256,
            "generic_io": self.generic_io.sha256,
            "candidate_poses": self.candidate_poses.sha256,
        }


@dataclass(frozen=True)
class Reconciliation:
    mandatory_instances: int
    required_body_area: int
    manufacturing_instances: int
    commodities: int
    operation_groups: int
    manufacturing_sources: int
    manufacturing_sinks: int
    generic_sources: int
    generic_sinks: int
    sources: int
    sinks: int
    active_terminals: int
    physical_ports_no_box: int
    null_ports_no_box: int
    candidate_counts: Mapping[str, int]
    hashes: Mapping[str, str]

    def counts(self) -> dict[str, int]:
        return {
            name: int(getattr(self, name))
            for name in EXPECTED_RECONCILIATION
        }


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputContractError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def strict_json_loads(payload: bytes, *, label: str) -> Any:
    """Parse strict UTF-8 JSON, rejecting duplicate keys and non-finite numbers."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputContractError(f"{label}: not UTF-8: {exc}") from exc

    def reject_constant(token: str) -> None:
        raise InputContractError(f"{label}: non-finite JSON number {token!r}")

    try:
        return json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=reject_constant,
        )
    except InputContractError:
        raise
    except json.JSONDecodeError as exc:
        raise InputContractError(
            f"{label}: JSON syntax error at line {exc.lineno}, column {exc.colno}"
        ) from exc


def load_document(path: Path, *, label: str, expected_sha256: str) -> LoadedDocument:
    """Read and hash one pinned JSON document without mutating it."""

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise InputContractError(f"{label}: cannot read {path}: {exc}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise InputContractError(
            f"{label}: SHA-256 mismatch: expected {expected_sha256}, got {digest}"
        )
    return LoadedDocument(path=path, sha256=digest, value=strict_json_loads(payload, label=label))


def load_input_bundle(project_root: Path = PROJECT_ROOT) -> InputBundle:
    """Load all five released inputs under their pinned byte digests."""

    root = project_root.resolve()
    return InputBundle(
        strict_instance=load_document(
            root / STRICT_INSTANCE_RELATIVE_PATH,
            label="strict_instance",
            expected_sha256=EXPECTED_SHA256["strict_instance"],
        ),
        canonical_rules=load_document(
            root / CANONICAL_RULES_RELATIVE_PATH,
            label="canonical_rules",
            expected_sha256=EXPECTED_SHA256["canonical_rules"],
        ),
        mandatory_instances=load_document(
            root / MANDATORY_INSTANCES_RELATIVE_PATH,
            label="mandatory_instances",
            expected_sha256=EXPECTED_SHA256["mandatory_instances"],
        ),
        generic_io=load_document(
            root / GENERIC_IO_RELATIVE_PATH,
            label="generic_io",
            expected_sha256=EXPECTED_SHA256["generic_io"],
        ),
        candidate_poses=load_document(
            root / CANDIDATE_POSES_RELATIVE_PATH,
            label="candidate_poses",
            expected_sha256=EXPECTED_SHA256["candidate_poses"],
        ),
    )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise InputContractError(f"{label}: expected object")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise InputContractError(f"{label}: expected array")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise InputContractError(f"{label}: expected non-empty string")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputContractError(f"{label}: expected integer")
    if minimum is not None and value < minimum:
        raise InputContractError(f"{label}: expected integer >= {minimum}")
    return value


def _number_fraction(value: Any, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InputContractError(f"{label}: expected finite JSON number")
    result = Fraction(str(value))
    if result <= 0:
        raise InputContractError(f"{label}: expected positive number")
    return result


def _exact_keys(value: Mapping[str, Any], keys: Iterable[str], label: str) -> None:
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        raise InputContractError(
            f"{label}: field mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _coordinate(value: Any, label: str) -> tuple[int, int]:
    pair = _sequence(value, label)
    if len(pair) != 2:
        raise InputContractError(f"{label}: expected [x, y]")
    return _integer(pair[0], f"{label}[0]"), _integer(pair[1], f"{label}[1]")


def candidate_front_cell(port: Mapping[str, Any]) -> tuple[int, int]:
    """Return the candidate port's stored access/front cell (identity semantics)."""

    return _integer(port.get("x"), "candidate port x"), _integer(port.get("y"), "candidate port y")


def strict_port_access_cell(anchor: tuple[int, int], port: Mapping[str, Any]) -> tuple[int, int]:
    """Derive one strict access cell from its body cell and outward direction."""

    body_cell = _mapping(port.get("body_cell"), "strict port body_cell")
    x = _integer(body_cell.get("x"), "strict port body_cell.x")
    y = _integer(body_cell.get("y"), "strict port body_cell.y")
    direction = _string(port.get("direction"), "strict port direction")
    if direction not in DELTA:
        raise InputContractError(f"strict port direction: unknown direction {direction!r}")
    dx, dy = DELTA[direction]
    return anchor[0] + x + dx, anchor[1] + y + dy


def _strict_mode(
    strict_instance: Mapping[str, Any],
    candidate_template: str,
    candidate_mode: str,
) -> Mapping[str, Any]:
    try:
        strict_template = CANDIDATE_TEMPLATE_TO_STRICT[candidate_template]
        strict_mode_id = CANDIDATE_MODE_TO_STRICT[candidate_mode]
    except KeyError as exc:
        raise InputContractError(
            f"no strict mapping for candidate {candidate_template!r}/{candidate_mode!r}"
        ) from exc
    templates = _mapping(strict_instance.get("facility_templates"), "strict facility_templates")
    template = _mapping(templates.get(strict_template), f"strict template {strict_template}")
    modes = _sequence(template.get("modes"), f"strict template {strict_template}.modes")
    matches = [
        _mapping(mode, f"strict template {strict_template}.mode")
        for mode in modes
        if isinstance(mode, dict) and mode.get("id") == strict_mode_id
    ]
    if len(matches) != 1:
        raise InputContractError(
            f"strict mode lookup for {strict_template!r}/{strict_mode_id!r} returned {len(matches)} matches"
        )
    return matches[0]


def assert_mode_front_parity(
    candidate_template: str,
    pose: Mapping[str, Any],
    strict_instance: Mapping[str, Any],
) -> None:
    """Assert candidate identity-front geometry equals strict one-offset geometry.

    This is the double-offset canary: candidate coordinates already denote the
    access cell, whereas strict mode coordinates denote a body cell and require
    exactly one outward step.
    """

    anchor_obj = _mapping(pose.get("anchor"), "candidate anchor")
    anchor = (
        _integer(anchor_obj.get("x"), "candidate anchor.x"),
        _integer(anchor_obj.get("y"), "candidate anchor.y"),
    )
    params = _mapping(pose.get("pose_params"), "candidate pose_params")
    candidate_mode = _string(params.get("port_mode"), "candidate pose_params.port_mode")
    mode = _strict_mode(strict_instance, candidate_template, candidate_mode)
    body = _mapping(mode.get("body"), "strict mode body")
    width = _integer(body.get("width"), "strict mode body.width", minimum=1)
    height = _integer(body.get("height"), "strict mode body.height", minimum=1)

    actual_body = {
        _coordinate(cell, "candidate occupied cell")
        for cell in _sequence(pose.get("occupied_cells"), "candidate occupied_cells")
    }
    expected_body = {
        (x, y)
        for x in range(anchor[0], anchor[0] + width)
        for y in range(anchor[1], anchor[1] + height)
    }
    if actual_body != expected_body:
        raise InputContractError(
            f"candidate {candidate_template}/{candidate_mode} body differs from strict mode"
        )

    candidate_ports: dict[str, set[tuple[int, int, str]]] = {"input": set(), "output": set()}
    for kind, field in (("input", "input_port_cells"), ("output", "output_port_cells")):
        raw_ports = _sequence(pose.get(field), f"candidate {field}")
        for index, raw_port in enumerate(raw_ports):
            port = _mapping(raw_port, f"candidate {field}[{index}]")
            direction = _string(port.get("dir"), f"candidate {field}[{index}].dir")
            if direction not in DELTA:
                raise InputContractError(f"candidate {field}[{index}]: unknown direction {direction!r}")
            candidate_ports[kind].add((*candidate_front_cell(port), direction))
        if len(candidate_ports[kind]) != len(raw_ports):
            raise InputContractError(f"candidate {field}: duplicate physical front")

    strict_ports: dict[str, set[tuple[int, int, str]]] = {"input": set(), "output": set()}
    for index, raw_port in enumerate(_sequence(mode.get("ports"), "strict mode ports")):
        port = _mapping(raw_port, f"strict mode ports[{index}]")
        kind = _string(port.get("kind"), f"strict mode ports[{index}].kind")
        if kind not in strict_ports:
            raise InputContractError(f"strict mode ports[{index}]: unknown kind {kind!r}")
        direction = _string(port.get("direction"), f"strict mode ports[{index}].direction")
        strict_ports[kind].add((*strict_port_access_cell(anchor, port), direction))

    if candidate_ports != strict_ports:
        raise InputContractError(
            f"candidate {candidate_template}/{candidate_mode} fronts differ from strict access cells: "
            f"candidate={candidate_ports}, strict={strict_ports}"
        )


def _ceil_fraction(value: Fraction) -> int:
    return (value.numerator + value.denominator - 1) // value.denominator


def _expected_orientation(template_name: str, mode: str) -> int | None:
    if mode in {"TB", "BT"}:
        return 0
    if mode in {"RL", "LR"}:
        # Rectangular 6x4 machines rotate their body; square machines/boxes
        # encode the orthogonal side pair entirely in port_mode.
        return 1 if template_name == "manufacturing_6x4" else 0
    return {
        "core_LR_out": 0,
        "core_TB_out": 1,
        "omni": 0,
        "left_base": 0,
        "bottom_base": 1,
    }.get(mode)


def _validate_candidate_poses(
    candidate_document: Any,
    strict_instance: Mapping[str, Any],
) -> dict[str, int]:
    root = _mapping(candidate_document, "candidate_poses")
    _exact_keys(root, ("facility_pools",), "candidate_poses")
    pools = _mapping(root["facility_pools"], "candidate_poses.facility_pools")
    if set(pools) != set(EXPECTED_CANDIDATE_COUNTS):
        raise InputContractError(
            "candidate pool keys differ: "
            f"expected={sorted(EXPECTED_CANDIDATE_COUNTS)}, got={sorted(pools)}"
        )

    strict_power = _mapping(strict_instance.get("power"), "strict power")
    coverage = _mapping(strict_power.get("coverage_from_pole_anchor"), "strict power coverage")
    width = _integer(_mapping(strict_instance.get("grid"), "strict grid").get("width"), "strict grid.width")
    height = _integer(_mapping(strict_instance.get("grid"), "strict grid").get("height"), "strict grid.height")

    counts: dict[str, int] = {}
    for template_name in sorted(pools):
        pool = _sequence(pools[template_name], f"candidate pool {template_name}")
        counts[template_name] = len(pool)
        if len(pool) != EXPECTED_CANDIDATE_COUNTS[template_name]:
            raise InputContractError(
                f"candidate pool {template_name}: expected {EXPECTED_CANDIDATE_COUNTS[template_name]} poses, "
                f"got {len(pool)}"
            )
        seen_pose_ids: set[str] = set()
        for index, raw_pose in enumerate(pool):
            label = f"candidate pool {template_name}[{index}]"
            pose = _mapping(raw_pose, label)
            _exact_keys(
                pose,
                (
                    "pose_id",
                    "anchor",
                    "pose_params",
                    "occupied_cells",
                    "input_port_cells",
                    "output_port_cells",
                    "power_coverage_cells",
                ),
                label,
            )
            pose_id = _string(pose["pose_id"], f"{label}.pose_id")
            if pose_id in seen_pose_ids:
                raise InputContractError(f"{label}: duplicate pose_id {pose_id!r}")
            seen_pose_ids.add(pose_id)
            params = _mapping(pose["pose_params"], f"{label}.pose_params")
            _exact_keys(params, ("orientation", "port_mode"), f"{label}.pose_params")
            mode = _string(params["port_mode"], f"{label}.pose_params.port_mode")
            orientation = _integer(params["orientation"], f"{label}.pose_params.orientation")
            if orientation != _expected_orientation(template_name, mode):
                raise InputContractError(
                    f"{label}: orientation {orientation} disagrees with mode {mode!r}"
                )
            assert_mode_front_parity(template_name, pose, strict_instance)

            anchor_obj = _mapping(pose["anchor"], f"{label}.anchor")
            anchor = (
                _integer(anchor_obj.get("x"), f"{label}.anchor.x"),
                _integer(anchor_obj.get("y"), f"{label}.anchor.y"),
            )
            raw_coverage = pose["power_coverage_cells"]
            if template_name == "power_pole":
                coverage_cells = {
                    _coordinate(cell, f"{label}.power_coverage_cells")
                    for cell in _sequence(raw_coverage, f"{label}.power_coverage_cells")
                }
                expected_coverage = {
                    (x, y)
                    for x in range(
                        max(0, anchor[0] + _integer(coverage.get("x_min_offset"), "coverage.x_min_offset")),
                        min(width - 1, anchor[0] + _integer(coverage.get("x_max_offset"), "coverage.x_max_offset")) + 1,
                    )
                    for y in range(
                        max(0, anchor[1] + _integer(coverage.get("y_min_offset"), "coverage.y_min_offset")),
                        min(height - 1, anchor[1] + _integer(coverage.get("y_max_offset"), "coverage.y_max_offset")) + 1,
                    )
                }
                if coverage_cells != expected_coverage:
                    raise InputContractError(f"{label}: power coverage differs from strict contract")
            elif raw_coverage is not None:
                raise InputContractError(f"{label}: non-pole pose unexpectedly carries power coverage")
    return counts


def reconcile_inputs(bundle: InputBundle) -> Reconciliation:
    """Independently derive and cross-check all routing-witness sentinel counts."""

    strict = _mapping(bundle.strict_instance.value, "strict_instance")
    canonical = _mapping(bundle.canonical_rules.value, "canonical_rules")
    mandatory = _sequence(bundle.mandatory_instances.value, "mandatory_instances")
    generic = _mapping(bundle.generic_io.value, "generic_io")

    templates = _mapping(canonical.get("facility_templates"), "canonical facility_templates")
    recipes = _mapping(canonical.get("recipes"), "canonical recipes")
    commodity_metadata = _mapping(canonical.get("commodity_metadata"), "canonical commodity_metadata")
    logistics = _mapping(
        _mapping(canonical.get("globals"), "canonical globals").get("logistics"),
        "canonical globals.logistics",
    )
    port_capacity = _number_fraction(
        logistics.get("port_max_throughput_per_tick"),
        "canonical port_max_throughput_per_tick",
    )

    mandatory_by_id: dict[str, Mapping[str, Any]] = {}
    operation_ids: dict[str, list[str]] = {}
    manufacturing_count = 0
    body_area = 0
    for index, raw_record in enumerate(mandatory):
        label = f"mandatory_instances[{index}]"
        record = _mapping(raw_record, label)
        required_fields = {
            "instance_id",
            "facility_type",
            "operation_type",
            "is_mandatory",
            "bound_type",
            "solve_modes",
            "notes",
        }
        _exact_keys(record, required_fields, label)
        instance_id = _string(record["instance_id"], f"{label}.instance_id")
        if instance_id in mandatory_by_id:
            raise InputContractError(f"{label}: duplicate instance_id {instance_id!r}")
        if record["is_mandatory"] is not True:
            raise InputContractError(f"{label}: is_mandatory must be true")
        facility_type = _string(record["facility_type"], f"{label}.facility_type")
        operation_type = _string(record["operation_type"], f"{label}.operation_type")
        template = _mapping(templates.get(facility_type), f"canonical template {facility_type}")
        dimensions = _mapping(template.get("dimensions"), f"canonical template {facility_type}.dimensions")
        body_area += _integer(dimensions.get("w"), f"{label}.width", minimum=1) * _integer(
            dimensions.get("h"), f"{label}.height", minimum=1
        )
        mandatory_by_id[instance_id] = record
        if operation_type in recipes:
            manufacturing_count += 1
            operation_ids.setdefault(operation_type, []).append(instance_id)
        elif operation_type not in {"protocol_core", "boundary_io"}:
            raise InputContractError(f"{label}: unknown non-manufacturing operation {operation_type!r}")

    strict_groups = _sequence(strict.get("operation_groups"), "strict operation_groups")
    strict_group_by_id: dict[str, Mapping[str, Any]] = {}
    manufacturing_inputs = 0
    manufacturing_outputs = 0
    derived_commodities: set[str] = set()
    for index, raw_group in enumerate(strict_groups):
        label = f"strict operation_groups[{index}]"
        group = _mapping(raw_group, label)
        operation_id = _string(group.get("id"), f"{label}.id")
        if operation_id in strict_group_by_id:
            raise InputContractError(f"{label}: duplicate operation group {operation_id!r}")
        recipe = _mapping(recipes.get(operation_id), f"canonical recipe {operation_id}")
        count = len(operation_ids.get(operation_id, ()))
        if count == 0:
            raise InputContractError(f"{label}: operation has no mandatory instances")
        template_id = _string(recipe.get("template"), f"canonical recipe {operation_id}.template")
        if group.get("template") != template_id or group.get("count") != count:
            raise InputContractError(f"{label}: template/count differs from canonical mandatory derivation")
        actual_ids = _sequence(group.get("instance_ids"), f"{label}.instance_ids")
        if list(actual_ids) != operation_ids[operation_id]:
            raise InputContractError(f"{label}: instance_ids differ from mandatory derivation")
        ticks = _number_fraction(recipe.get("ticks_per_cycle"), f"canonical recipe {operation_id}.ticks_per_cycle")
        expected_needs: dict[str, dict[str, int]] = {"inputs": {}, "outputs": {}}
        for kind in ("inputs", "outputs"):
            flows = _mapping(recipe.get(kind), f"canonical recipe {operation_id}.{kind}")
            for commodity, raw_rate in flows.items():
                commodity_id = _string(commodity, f"canonical recipe {operation_id}.{kind} commodity")
                slots = _ceil_fraction(
                    _number_fraction(raw_rate, f"canonical recipe {operation_id}.{kind}.{commodity_id}")
                    / ticks
                    / port_capacity
                )
                expected_needs[kind][commodity_id] = slots
                derived_commodities.add(commodity_id)
        needs = _mapping(group.get("port_needs"), f"{label}.port_needs")
        if needs != expected_needs:
            raise InputContractError(
                f"{label}: port_needs differ from canonical rate/tick/capacity derivation: "
                f"expected={expected_needs}, got={needs}"
            )
        manufacturing_inputs += count * sum(expected_needs["inputs"].values())
        manufacturing_outputs += count * sum(expected_needs["outputs"].values())
        strict_group_by_id[operation_id] = group

    if set(strict_group_by_id) != set(recipes) or set(operation_ids) != set(recipes):
        raise InputContractError("canonical recipes, mandatory operation groups, and strict groups differ")
    if derived_commodities != set(commodity_metadata):
        raise InputContractError("recipe-derived commodities differ from canonical commodity_metadata")
    strict_commodities = _sequence(strict.get("commodities"), "strict commodities")
    if len(set(strict_commodities)) != len(strict_commodities) or set(strict_commodities) != derived_commodities:
        raise InputContractError("strict commodities differ from canonical recipe derivation")

    _exact_keys(
        generic,
        ("metadata", "required_generic_outputs", "required_generic_inputs"),
        "generic_io",
    )
    generic_outputs = _mapping(generic["required_generic_outputs"], "generic required outputs")
    generic_inputs = _mapping(generic["required_generic_inputs"], "generic required inputs")
    strict_generic = _mapping(strict.get("generic_requirements"), "strict generic_requirements")
    if strict_generic.get("raw_outputs") != generic_outputs:
        raise InputContractError("strict raw outputs differ from generic I/O input")
    if strict_generic.get("final_inputs") != generic_inputs:
        raise InputContractError("strict final inputs differ from generic I/O input")
    generic_source_count = sum(
        _integer(value, f"generic output {commodity}", minimum=1)
        for commodity, value in generic_outputs.items()
    )
    generic_sink_count = sum(
        _integer(value, f"generic input {commodity}", minimum=1)
        for commodity, value in generic_inputs.items()
    )

    strict_required = _sequence(strict.get("required_instances"), "strict required_instances")
    strict_required_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_record in enumerate(strict_required):
        label = f"strict required_instances[{index}]"
        record = _mapping(raw_record, label)
        instance_id = _string(record.get("id"), f"{label}.id")
        if instance_id in strict_required_by_id:
            raise InputContractError(f"{label}: duplicate required id {instance_id!r}")
        source = mandatory_by_id.get(instance_id)
        if source is None:
            raise InputContractError(f"{label}: id is absent from mandatory input")
        expected_operation = (
            source["operation_type"] if source["operation_type"] in recipes else "generic_io"
        )
        if record.get("template") != source["facility_type"] or record.get("operation") != expected_operation:
            raise InputContractError(f"{label}: differs from mandatory input")
        strict_required_by_id[instance_id] = record
    if set(strict_required_by_id) != set(mandatory_by_id):
        raise InputContractError("strict and mandatory required instance identifiers differ")

    strict_templates = _mapping(strict.get("facility_templates"), "strict facility_templates")
    physical_ports = 0
    for instance_id, record in strict_required_by_id.items():
        template_id = _string(record.get("template"), f"strict required {instance_id}.template")
        strict_template = _mapping(strict_templates.get(template_id), f"strict template {template_id}")
        port_counts: set[int] = set()
        areas: set[int] = set()
        for raw_mode in _sequence(strict_template.get("modes"), f"strict template {template_id}.modes"):
            mode = _mapping(raw_mode, f"strict template {template_id}.mode")
            ports = _sequence(mode.get("ports"), f"strict template {template_id}.ports")
            body = _mapping(mode.get("body"), f"strict template {template_id}.body")
            port_counts.add(len(ports))
            areas.add(
                _integer(body.get("width"), f"strict template {template_id}.width", minimum=1)
                * _integer(body.get("height"), f"strict template {template_id}.height", minimum=1)
            )
        if len(port_counts) != 1 or len(areas) != 1:
            raise InputContractError(f"strict template {template_id}: mode port count/body area drift")
        canonical_template = _mapping(templates.get(template_id), f"canonical template {template_id}")
        dims = _mapping(canonical_template.get("dimensions"), f"canonical template {template_id}.dimensions")
        canonical_area = _integer(dims.get("w"), "canonical width", minimum=1) * _integer(
            dims.get("h"), "canonical height", minimum=1
        )
        if areas != {canonical_area}:
            raise InputContractError(f"strict template {template_id}: body area differs from canonical")
        physical_ports += next(iter(port_counts))

    sources = manufacturing_outputs + generic_source_count
    sinks = manufacturing_inputs + generic_sink_count
    active = sources + sinks
    reconciliation_values = {
        "mandatory_instances": len(mandatory),
        "required_body_area": body_area,
        "manufacturing_instances": manufacturing_count,
        "commodities": len(derived_commodities),
        "operation_groups": len(strict_group_by_id),
        "manufacturing_sources": manufacturing_outputs,
        "manufacturing_sinks": manufacturing_inputs,
        "generic_sources": generic_source_count,
        "generic_sinks": generic_sink_count,
        "sources": sources,
        "sinks": sinks,
        "active_terminals": active,
        "physical_ports_no_box": physical_ports,
        "null_ports_no_box": physical_ports - active,
    }
    if reconciliation_values != EXPECTED_RECONCILIATION:
        raise InputContractError(
            f"independent reconciliation differs: expected={EXPECTED_RECONCILIATION}, "
            f"got={reconciliation_values}"
        )

    sentinel_expected = {
        "commodity_count": reconciliation_values["commodities"],
        "operation_group_count": reconciliation_values["operation_groups"],
        "manufacturing_instance_count": reconciliation_values["manufacturing_instances"],
        "required_instance_count": reconciliation_values["mandatory_instances"],
        "required_body_area": reconciliation_values["required_body_area"],
        "manufacturing_input_terminals": reconciliation_values["manufacturing_sinks"],
        "manufacturing_output_terminals": reconciliation_values["manufacturing_sources"],
        "generic_raw_output_terminals": reconciliation_values["generic_sources"],
        "generic_final_input_terminals": reconciliation_values["generic_sinks"],
        "total_active_terminals": reconciliation_values["active_terminals"],
    }
    if strict.get("sentinels") != sentinel_expected:
        raise InputContractError(
            f"strict sentinels differ from independent reconciliation: {strict.get('sentinels')!r}"
        )

    candidate_counts = _validate_candidate_poses(bundle.candidate_poses.value, strict)
    return Reconciliation(
        **reconciliation_values,
        candidate_counts=candidate_counts,
        hashes=bundle.hashes,
    )


def load_and_reconcile(project_root: Path = PROJECT_ROOT) -> tuple[InputBundle, Reconciliation]:
    """Convenience entry point used by the witness runner and focused tests."""

    bundle = load_input_bundle(project_root)
    return bundle, reconcile_inputs(bundle)
