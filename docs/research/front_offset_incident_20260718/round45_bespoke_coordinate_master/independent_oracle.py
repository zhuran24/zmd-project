"""Independent semantic oracle for the rebuilt Round 4/5 coordinate prototype.

The oracle deliberately does not import ``compact_model``.  It reads the five
canonical inputs as raw JSON, derives geometry and counts independently, and
then cross-checks two narrow production truth surfaces:

* ``CoordinateExactMasterDelegate._pose_mode_token`` for coordinate-mode
  normalization; and
* ``routing_visible_port_demands`` and
  ``routing_free_sink_commodities_from_generic_inputs`` for the production
  routing-visible demand/RFSC truth surface; and
* ``PROJECT_LOCK.md`` for the owner-approved Batch-5 authority that keeps
  generic-input finals routed end to end.

Every pinned value and structural premise is checked.  A missing dependency,
malformed input, hash drift, geometry drift, or incomplete build audit returns
``ok=False`` and is never eligible to support an INFEASIBLE claim.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "round45_bespoke_independent_oracle_v2"
GRID_W = 70
GRID_H = 70

EXPECTED_INPUTS: dict[str, tuple[int, str]] = {
    "rules/canonical_rules.json": (
        17_510,
        "5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05",
    ),
    "rules/preprocess_plan.json": (
        1_383,
        "5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee",
    ),
    "data/preprocessed/candidate_placements.json": (
        54_467_709,
        "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
    ),
    "data/preprocessed/mandatory_exact_instances.json": (
        88_261,
        "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6",
    ),
    "data/preprocessed/generic_io_requirements.json": (
        561,
        "ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e",
    ),
}

EXPECTED_POOL_COUNTS = {
    "boundary_storage_port": 136,
    "manufacturing_3x3": 17_952,
    "manufacturing_5x5": 16_896,
    "manufacturing_6x4": 16_900,
    "power_pole": 4_761,
    "protocol_core": 7_688,
    "protocol_storage_box": 18_496,
}

EXPECTED_TEMPLATE_COUNTS = {
    "boundary_storage_port": 46,
    "manufacturing_3x3": 132,
    "manufacturing_5x5": 49,
    "manufacturing_6x4": 38,
    "protocol_core": 1,
}

EXPECTED_OPERATION_COUNTS = {
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

EXPECTED_GENERIC_OUTPUTS = {"blue_iron_ore": 34, "source_ore": 18}
EXPECTED_GENERIC_INPUTS = {"qiaoyu_capsule": 1, "valley_battery": 1}

EXPECTED_COMPACT_VARIABLE_COUNT = 10_816
EXPECTED_COMPACT_CONSTRAINT_HISTOGRAM = {
    "bool_or": 2,
    "element": 663,
    "exactly_one": 270,
    "interval": 2_236,
    "linear": 11_813,
    "no_overlap_2d": 629,
    "table": 900,
}
EXPECTED_COMPACT_CONSTRAINT_COUNT = sum(EXPECTED_COMPACT_CONSTRAINT_HISTOGRAM.values())

# (x_min, x_max, y_min, y_max, pose_count)
EXPECTED_MODE_DOMAINS: dict[str, tuple[int, int, int, int, int]] = {
    "boundary_storage_port|0|left_base": (0, 0, 0, 67, 68),
    "boundary_storage_port|1|bottom_base": (0, 67, 0, 0, 68),
    "manufacturing_3x3|0|BT": (0, 67, 1, 66, 4_488),
    "manufacturing_3x3|0|LR": (1, 66, 0, 67, 4_488),
    "manufacturing_3x3|0|RL": (1, 66, 0, 67, 4_488),
    "manufacturing_3x3|0|TB": (0, 67, 1, 66, 4_488),
    "manufacturing_5x5|0|BT": (0, 65, 1, 64, 4_224),
    "manufacturing_5x5|0|LR": (1, 64, 0, 65, 4_224),
    "manufacturing_5x5|0|RL": (1, 64, 0, 65, 4_224),
    "manufacturing_5x5|0|TB": (0, 65, 1, 64, 4_224),
    "manufacturing_6x4|0|BT": (0, 64, 1, 65, 4_225),
    "manufacturing_6x4|0|TB": (0, 64, 1, 65, 4_225),
    "manufacturing_6x4|1|LR": (1, 65, 0, 64, 4_225),
    "manufacturing_6x4|1|RL": (1, 65, 0, 64, 4_225),
    "power_pole|0|omni": (0, 68, 0, 68, 4_761),
    "protocol_core|0|core_LR_out": (0, 61, 0, 61, 3_844),
    "protocol_core|1|core_TB_out": (0, 61, 0, 61, 3_844),
    "protocol_storage_box|0|BT": (0, 67, 0, 67, 4_624),
    "protocol_storage_box|0|LR": (0, 67, 0, 67, 4_624),
    "protocol_storage_box|0|RL": (0, 67, 0, 67, 4_624),
    "protocol_storage_box|0|TB": (0, 67, 0, 67, 4_624),
}

# SHA256 of canonical JSON {body:[[dx,dy]], input:[[dx,dy,dir]],
# output:[[dx,dy,dir]]}.  This pins the relative MFE geometry independently of
# the production mode token, whose footprint component alone does not include
# ports.
EXPECTED_GEOMETRY_SHA256 = {
    "boundary_storage_port|0|left_base": "3eff61f3321b3f0377ee437c47b7da58bfd187b6ab28c7172ea0bbd651ae71c4",
    "boundary_storage_port|1|bottom_base": "51f18ee5b54419fc47231d7c12db8ca68b35f8904cac76fc1804c34af7fc32cb",
    "manufacturing_3x3|0|BT": "2c84966c243ab7a2606ff65b534d73cd73a5e81e75418ae1729702817941a7e1",
    "manufacturing_3x3|0|LR": "c96f297628b0a4129b05622a67f6311b6ebcae6b3f9def8b10efc38c139d1626",
    "manufacturing_3x3|0|RL": "27d974a3e3c5fdd97fe98310a04daafc33dba53da18e3869a8bc6b896d20c052",
    "manufacturing_3x3|0|TB": "8b687d2d211352e24e3b5a696265c9c55c2c7eb93dc6e9881cecdaf35febbc87",
    "manufacturing_5x5|0|BT": "7c9c2093987cb5cacc8a4ce3616803355ab98f2d7c53e5c2d116862b30c7a6a7",
    "manufacturing_5x5|0|LR": "8459a42413a92d392e0f8b592a835f9d0b81768a56e02c41280c35c3a92ff0e8",
    "manufacturing_5x5|0|RL": "728f414e5fec9b54cf7198b5236bfd72bc2862d6b28eb8e3798df542d96f8601",
    "manufacturing_5x5|0|TB": "feefd318bdb70572559b1658efaf97771e9161d936fb990643104122312772ca",
    "manufacturing_6x4|0|BT": "02b79d1601d25605ea98a0285c226eb5a91f8e940247ff33e4b984128ae12894",
    "manufacturing_6x4|0|TB": "5192bbbbd6eaa2d85483c0dd21beface60b3a05e9d3b6388cb69a0ff2be986d3",
    "manufacturing_6x4|1|LR": "3bd89ad33d62ee84103ba744fe1ce4ebb2d5a6b60cc15193e1bcbeac4e543542",
    "manufacturing_6x4|1|RL": "5198ad5f83f5996c97f937e7fa849ffb1e5a9db90a85a5a6575788a362717caa",
    "power_pole|0|omni": "dc76c1540bc72df020238257b382b8465494c7318fc826b7a4918f7f231ddb2f",
    "protocol_core|0|core_LR_out": "47863ef37778b087051ba42bb212e29a0f4fc4b8e3c05022589da51bf83a3084",
    "protocol_core|1|core_TB_out": "d41d62ad5ede52e27e8f2e2fb7395cebc3bc2a6fedbe63fa79c315fd33a5f877",
    "protocol_storage_box|0|BT": "2c84966c243ab7a2606ff65b534d73cd73a5e81e75418ae1729702817941a7e1",
    "protocol_storage_box|0|LR": "c96f297628b0a4129b05622a67f6311b6ebcae6b3f9def8b10efc38c139d1626",
    "protocol_storage_box|0|RL": "27d974a3e3c5fdd97fe98310a04daafc33dba53da18e3869a8bc6b896d20c052",
    "protocol_storage_box|0|TB": "8b687d2d211352e24e3b5a696265c9c55c2c7eb93dc6e9881cecdaf35febbc87",
}

EXPECTED_TEMPLATE_GEOMETRY = {
    "boundary_storage_port": (3, 0, 1),
    "manufacturing_3x3": (9, 3, 3),
    "manufacturing_5x5": (25, 5, 5),
    "manufacturing_6x4": (24, 6, 6),
    "power_pole": (4, 0, 0),
    "protocol_core": (81, 14, 6),
    "protocol_storage_box": (9, 3, 3),
}

EXPECTED_TEMPLATE_RULES = {
    "boundary_storage_port": (1, 3, False),
    "manufacturing_3x3": (3, 3, True),
    "manufacturing_5x5": (5, 5, True),
    "manufacturing_6x4": (6, 4, True),
    "power_pole": (2, 2, False),
    "protocol_core": (9, 9, False),
    "protocol_storage_box": (3, 3, True),
}

DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}

PROJECT_LOCK_RFSC_FRAGMENTS = (
    "no generic-input-final producer output may be hidden by a routing-free or wireless classification",
    "`routing_free_sink_commodities_from_generic_inputs()` is empty by contract",
    "per-side demands come exclusively from `src/models/port_binding.py::routing_visible_port_demands`",
    "always returns `frozenset()`",
)


class IndependentOracleError(ValueError):
    """An input cannot be interpreted without weakening a fail-closed check."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IndependentOracleError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> tuple[Any, int, str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    return payload, len(raw), hashlib.sha256(raw).hexdigest()


def _strict_int(value: Any, *, label: str) -> int:
    if type(value) is not int:
        raise IndependentOracleError(f"{label} must be a strict JSON integer, got {value!r}")
    return value


def _strict_xy(raw: Any, *, label: str) -> tuple[int, int]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise IndependentOracleError(f"{label} must be a two-item JSON array")
    return (
        _strict_int(raw[0], label=f"{label}[0]"),
        _strict_int(raw[1], label=f"{label}[1]"),
    )


def _strict_anchor(raw: Any, *, label: str) -> tuple[int, int]:
    if not isinstance(raw, Mapping) or set(raw) != {"x", "y"}:
        raise IndependentOracleError(f"{label} must be exactly an x/y object")
    return (
        _strict_int(raw["x"], label=f"{label}.x"),
        _strict_int(raw["y"], label=f"{label}.y"),
    )


def _strict_port(raw: Any, *, label: str) -> tuple[int, int, str]:
    if not isinstance(raw, Mapping):
        raise IndependentOracleError(f"{label} must be an object")
    if not {"x", "y", "dir"}.issubset(raw):
        raise IndependentOracleError(f"{label} is missing x/y/dir")
    direction = raw["dir"]
    if not isinstance(direction, str) or direction not in DIR_DELTA:
        raise IndependentOracleError(f"{label}.dir is invalid: {direction!r}")
    return (
        _strict_int(raw["x"], label=f"{label}.x"),
        _strict_int(raw["y"], label=f"{label}.y"),
        direction,
    )


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_footprint_key(relative_body: Sequence[tuple[int, int]]) -> str:
    if not relative_body:
        return "footprint::missing"
    xs = [cell[0] for cell in relative_body]
    ys = [cell[1] for cell in relative_body]
    bounds_token = ":".join(
        str(value) for value in (min(xs), max(xs), min(ys), max(ys))
    )
    cell_token = ";".join(f"{x}:{y}" for x, y in sorted(relative_body))
    return f"footprint::{bounds_token}::{cell_token}"


def _record_equal(
    checks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    name: str,
    actual: Any,
    expected: Any,
) -> None:
    ok = actual == expected
    checks.append({"name": name, "ok": ok})
    if not ok:
        errors.append(
            {
                "check": name,
                "expected": expected,
                "actual": actual,
            }
        )


def _production_sources(
    project_root: Path,
) -> tuple[Any, Mapping[str, Any], Any, dict[str, str]]:
    root_text = str(project_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    mode_module = importlib.import_module("src.models.exact_coordinate_master")
    profile_module = importlib.import_module("src.preprocess.operation_profiles")
    port_binding_module = importlib.import_module("src.models.port_binding")
    expected_mode_path = (project_root / "src/models/exact_coordinate_master.py").resolve()
    expected_profile_path = (project_root / "src/preprocess/operation_profiles.py").resolve()
    expected_port_binding_path = (project_root / "src/models/port_binding.py").resolve()
    actual_mode_path = Path(mode_module.__file__).resolve()
    actual_profile_path = Path(profile_module.__file__).resolve()
    actual_port_binding_path = Path(port_binding_module.__file__).resolve()
    if (
        actual_mode_path != expected_mode_path
        or actual_profile_path != expected_profile_path
        or actual_port_binding_path != expected_port_binding_path
    ):
        raise IndependentOracleError(
            "production imports resolved outside project_root: "
            f"mode={actual_mode_path}, profiles={actual_profile_path}, "
            f"port_binding={actual_port_binding_path}"
        )

    delegate_type = mode_module.CoordinateExactMasterDelegate
    token_delegate = object.__new__(delegate_type)
    profiles = profile_module.OPERATION_PORT_PROFILES
    if not isinstance(profiles, Mapping):
        raise IndependentOracleError("OPERATION_PORT_PROFILES is not a mapping")
    for function_name in (
        "routing_free_sink_commodities_from_generic_inputs",
        "routing_visible_port_demands",
    ):
        if not callable(getattr(port_binding_module, function_name, None)):
            raise IndependentOracleError(
                f"src.models.port_binding.{function_name} is not callable"
            )
    project_lock_path = (project_root / "PROJECT_LOCK.md").resolve()
    project_lock_raw = project_lock_path.read_bytes()
    return token_delegate, profiles, port_binding_module, {
        "mode_token_module": str(actual_mode_path),
        "operation_profiles_module": str(actual_profile_path),
        "port_binding_module": str(actual_port_binding_path),
        "project_lock": str(project_lock_path),
        "project_lock_sha256": hashlib.sha256(project_lock_raw).hexdigest(),
    }


def _audit_project_lock_rfsc(
    project_root: Path,
    checks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    path = (project_root / "PROJECT_LOCK.md").resolve()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fragment_lines: dict[str, int | None] = {}
    for fragment in PROJECT_LOCK_RFSC_FRAGMENTS:
        line_number = next(
            (index for index, line in enumerate(lines, start=1) if fragment in line),
            None,
        )
        fragment_lines[fragment] = line_number
        _record_equal(
            checks,
            errors,
            f"project_lock.rfsc_authority.{len(fragment_lines) - 1}",
            line_number is not None,
            True,
        )
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "required_fragment_lines": fragment_lines,
        "batch5_contract": (
            "generic-input finals are normal routed commodities; RFSC is empty; "
            "routing-visible pose demand comes from port_binding SSOT"
        ),
    }


def _extract_pools(payload: Any) -> dict[str, list[Mapping[str, Any]]]:
    if not isinstance(payload, Mapping) or set(payload) != {"facility_pools"}:
        raise IndependentOracleError("candidate placements must be {facility_pools: {...}}")
    raw_pools = payload["facility_pools"]
    if not isinstance(raw_pools, Mapping):
        raise IndependentOracleError("facility_pools must be an object")
    pools: dict[str, list[Mapping[str, Any]]] = {}
    for template, raw_pool in raw_pools.items():
        if not isinstance(raw_pool, list) or not all(
            isinstance(pose, Mapping) for pose in raw_pool
        ):
            raise IndependentOracleError(f"pool {template!r} must be a list of objects")
        pools[str(template)] = list(raw_pool)
    return pools


def _audit_pools(
    pools: Mapping[str, list[Mapping[str, Any]]],
    token_delegate: Any,
    checks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _record_equal(checks, errors, "pool.keys", sorted(pools), sorted(EXPECTED_POOL_COUNTS))
    pool_counts = {template: len(pool) for template, pool in sorted(pools.items())}
    _record_equal(checks, errors, "pool.counts", pool_counts, EXPECTED_POOL_COUNTS)
    _record_equal(checks, errors, "pool.total", sum(pool_counts.values()), 82_829)

    grouped: dict[
        tuple[str, tuple[str, str, str]],
        list[tuple[tuple[int, int], str, dict[str, Any]]],
    ] = defaultdict(list)
    oob_pose_counts: Counter[str] = Counter()
    oob_port_counts: Counter[str] = Counter()
    orientation_types: Counter[str] = Counter()
    total_ports = 0
    identity_adjacencies = 0

    for template, pool in sorted(pools.items()):
        pose_ids: set[str] = set()
        for pose_idx, pose in enumerate(pool):
            label = f"{template}[{pose_idx}]"
            pose_id = pose.get("pose_id")
            if not isinstance(pose_id, str) or not pose_id:
                raise IndependentOracleError(f"{label}.pose_id must be non-empty")
            if pose_id in pose_ids:
                raise IndependentOracleError(f"{label}: duplicate pose_id {pose_id!r}")
            pose_ids.add(pose_id)
            anchor_x, anchor_y = _strict_anchor(pose.get("anchor"), label=f"{label}.anchor")
            params = pose.get("pose_params")
            if not isinstance(params, Mapping):
                raise IndependentOracleError(f"{label}.pose_params must be an object")
            orientation = params.get("orientation")
            if type(orientation) is not int:
                raise IndependentOracleError(
                    f"{label}.pose_params.orientation must remain a raw integer"
                )
            port_mode = params.get("port_mode")
            if not isinstance(port_mode, str) or not port_mode:
                raise IndependentOracleError(f"{label}.pose_params.port_mode is invalid")
            orientation_types[type(orientation).__name__] += 1

            raw_body = pose.get("occupied_cells")
            if not isinstance(raw_body, list) or not raw_body:
                raise IndependentOracleError(f"{label}.occupied_cells must be non-empty")
            body = [_strict_xy(cell, label=f"{label}.occupied_cells") for cell in raw_body]
            if len(set(body)) != len(body):
                raise IndependentOracleError(f"{label}: duplicate occupied cell")
            if any(not (0 <= x < GRID_W and 0 <= y < GRID_H) for x, y in body):
                raise IndependentOracleError(f"{label}: body cell is out of grid")
            relative_body = sorted((x - anchor_x, y - anchor_y) for x, y in body)
            body_set = set(body)

            side_ports: dict[str, list[tuple[int, int, str]]] = {}
            pose_has_oob = False
            for field in ("input_port_cells", "output_port_cells"):
                raw_ports = pose.get(field)
                if not isinstance(raw_ports, list):
                    raise IndependentOracleError(f"{label}.{field} must be a list")
                ports = [
                    _strict_port(port, label=f"{label}.{field}[{index}]")
                    for index, port in enumerate(raw_ports)
                ]
                if len(set(ports)) != len(ports):
                    raise IndependentOracleError(f"{label}.{field}: duplicate physical port")
                side_ports[field] = ports
                for port_x, port_y, direction in ports:
                    total_ports += 1
                    dx, dy = DIR_DELTA[direction]
                    if (port_x, port_y) in body_set:
                        raise IndependentOracleError(
                            f"{label}: stored identity front {(port_x, port_y)} lies in own body"
                        )
                    if (port_x - dx, port_y - dy) not in body_set:
                        raise IndependentOracleError(
                            f"{label}: port {(port_x, port_y, direction)} is not first outside body"
                        )
                    identity_adjacencies += 1
                    if not (0 <= port_x < GRID_W and 0 <= port_y < GRID_H):
                        pose_has_oob = True
                        oob_port_counts[template] += 1
            if pose_has_oob:
                oob_pose_counts[template] += 1

            relative_inputs = sorted(
                (x - anchor_x, y - anchor_y, direction)
                for x, y, direction in side_ports["input_port_cells"]
            )
            relative_outputs = sorted(
                (x - anchor_x, y - anchor_y, direction)
                for x, y, direction in side_ports["output_port_cells"]
            )
            raw_token = (
                str(orientation),
                port_mode,
                _raw_footprint_key(relative_body),
            )
            production_token = token_delegate._pose_mode_token(pose)
            if tuple(production_token) != raw_token:
                raise IndependentOracleError(
                    f"{label}: raw mode token {raw_token!r} != production {production_token!r}"
                )

            geometry = {
                "body": [[x, y] for x, y in relative_body],
                "input": [[x, y, direction] for x, y, direction in relative_inputs],
                "output": [[x, y, direction] for x, y, direction in relative_outputs],
            }
            grouped[(template, raw_token)].append(
                ((anchor_x, anchor_y), _canonical_sha(geometry), geometry)
            )

            raw_coverage = pose.get("power_coverage_cells")
            if template == "power_pole":
                if not isinstance(raw_coverage, list):
                    raise IndependentOracleError(f"{label}.power_coverage_cells must be a list")
                actual_coverage = {
                    _strict_xy(cell, label=f"{label}.power_coverage_cells")
                    for cell in raw_coverage
                }
                if len(actual_coverage) != len(raw_coverage):
                    raise IndependentOracleError(f"{label}: duplicate power coverage cell")
                expected_coverage = {
                    (x, y)
                    for x in range(max(0, anchor_x - 5), min(GRID_W, anchor_x + 7))
                    for y in range(max(0, anchor_y - 5), min(GRID_H, anchor_y + 7))
                }
                if actual_coverage != expected_coverage:
                    raise IndependentOracleError(f"{label}: radius-5 coverage stencil drift")
            elif raw_coverage is not None:
                raise IndependentOracleError(f"{label}: non-pole power coverage must remain null")

    _record_equal(checks, errors, "pool.orientation_raw_types", dict(orientation_types), {"int": 82_829})
    _record_equal(checks, errors, "identity.port_adjacencies", identity_adjacencies, total_ports)

    mode_domains: dict[str, dict[str, Any]] = {}
    modes_by_template: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for template, token in grouped:
        modes_by_template[template].append(token)
    for template in modes_by_template:
        modes_by_template[template].sort()

    tuple_key_count = 0
    for (template, token), records in sorted(grouped.items()):
        mode_id = modes_by_template[template].index(token)
        key = f"{template}|{token[0]}|{token[1]}"
        anchors = [anchor for anchor, _digest, _geometry in records]
        anchor_set = set(anchors)
        if len(anchor_set) != len(anchors):
            raise IndependentOracleError(f"{key}: duplicate (anchor,mode) coordinate key")
        xs = [anchor[0] for anchor in anchors]
        ys = [anchor[1] for anchor in anchors]
        actual_rect = {
            (x, y)
            for x in range(min(xs), max(xs) + 1)
            for y in range(min(ys), max(ys) + 1)
        }
        geometry_digests = {digest for _anchor, digest, _geometry in records}
        if len(geometry_digests) != 1:
            raise IndependentOracleError(f"{key}: relative body/port geometry is not stable")
        geometry = records[0][2]
        actual_domain = (
            min(xs),
            max(xs),
            min(ys),
            max(ys),
            len(anchors),
        )
        full_rectangle = anchor_set == actual_rect
        _record_equal(checks, errors, f"mode.{key}.domain", actual_domain, EXPECTED_MODE_DOMAINS.get(key))
        _record_equal(checks, errors, f"mode.{key}.full_rectangle", full_rectangle, True)
        geometry_sha = next(iter(geometry_digests))
        _record_equal(
            checks,
            errors,
            f"mode.{key}.geometry_sha256",
            geometry_sha,
            EXPECTED_GEOMETRY_SHA256.get(key),
        )
        expected_geometry = EXPECTED_TEMPLATE_GEOMETRY.get(template)
        actual_geometry = (
            len(geometry["body"]),
            len(geometry["input"]),
            len(geometry["output"]),
        )
        _record_equal(
            checks,
            errors,
            f"mode.{key}.cell_counts",
            actual_geometry,
            expected_geometry,
        )
        mode_domains[key] = {
            "mode_id": mode_id,
            "x_min": actual_domain[0],
            "x_max": actual_domain[1],
            "y_min": actual_domain[2],
            "y_max": actual_domain[3],
            "pose_count": actual_domain[4],
            "full_rectangle": full_rectangle,
            "geometry_sha256": geometry_sha,
        }
        tuple_key_count += len(anchors)

    _record_equal(
        checks,
        errors,
        "mode.keys",
        sorted(mode_domains),
        sorted(EXPECTED_MODE_DOMAINS),
    )
    _record_equal(checks, errors, "mode.total", len(mode_domains), 21)
    _record_equal(checks, errors, "mode.coordinate_tuple_keys", tuple_key_count, 82_829)

    expected_oob_pose_counts = {"protocol_core": 488, "protocol_storage_box": 544}
    actual_oob_pose_counts = dict(sorted(oob_pose_counts.items()))
    _record_equal(
        checks,
        errors,
        "identity.oob_pose_counts",
        actual_oob_pose_counts,
        expected_oob_pose_counts,
    )

    corner_samples: dict[str, dict[str, int]] = {}
    for template in ("protocol_core", "protocol_storage_box"):
        for pose in pools[template]:
            anchor = pose["anchor"]
            if anchor["x"] != 0 or anchor["y"] != 0:
                continue
            params = pose["pose_params"]
            sample_key = f"{template}|{params['orientation']}|{params['port_mode']}"
            corner_samples[sample_key] = {
                "input_oob": sum(
                    not (0 <= port["x"] < GRID_W and 0 <= port["y"] < GRID_H)
                    for port in pose["input_port_cells"]
                ),
                "output_oob": sum(
                    not (0 <= port["x"] < GRID_W and 0 <= port["y"] < GRID_H)
                    for port in pose["output_port_cells"]
                ),
            }
    expected_corner_samples = {
        "protocol_core|0|core_LR_out": {"input_oob": 7, "output_oob": 3},
        "protocol_core|1|core_TB_out": {"input_oob": 7, "output_oob": 3},
        "protocol_storage_box|0|BT": {"input_oob": 3, "output_oob": 0},
        "protocol_storage_box|0|LR": {"input_oob": 3, "output_oob": 0},
        "protocol_storage_box|0|RL": {"input_oob": 0, "output_oob": 3},
        "protocol_storage_box|0|TB": {"input_oob": 0, "output_oob": 3},
    }
    _record_equal(
        checks,
        errors,
        "identity.corner_oob_samples",
        corner_samples,
        expected_corner_samples,
    )

    return {
        "total_poses": sum(pool_counts.values()),
        "pool_counts": pool_counts,
        "mode_count": len(mode_domains),
        "mode_domains": mode_domains,
    }, {
        "semantics": "stored_port_identity",
        "identity_sentinel_pass": identity_adjacencies == total_ports,
        "total_raw_ports": total_ports,
        "out_of_grid_port_counts": dict(sorted(oob_port_counts.items())),
        "out_of_grid_pose_counts": actual_oob_pose_counts,
        "corner_out_of_grid_samples": corner_samples,
        "inactive_oob_domain_preserved": actual_oob_pose_counts
        == expected_oob_pose_counts,
    }


def _audit_rules(
    rules: Any,
    plan: Any,
    checks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(rules, Mapping) or not isinstance(plan, Mapping):
        raise IndependentOracleError("rules and preprocess plan must be objects")
    grid = rules.get("globals", {}).get("grid", {})
    grid_pair = (
        _strict_int(grid.get("width"), label="rules.globals.grid.width"),
        _strict_int(grid.get("height"), label="rules.globals.grid.height"),
    )
    _record_equal(checks, errors, "rules.grid", grid_pair, (GRID_W, GRID_H))
    templates = rules.get("facility_templates")
    if not isinstance(templates, Mapping):
        raise IndependentOracleError("rules.facility_templates must be an object")
    actual_template_rules: dict[str, tuple[int, int, bool]] = {}
    for template in EXPECTED_TEMPLATE_RULES:
        spec = templates.get(template)
        if not isinstance(spec, Mapping):
            raise IndependentOracleError(f"missing facility template {template!r}")
        dimensions = spec.get("dimensions")
        if not isinstance(dimensions, Mapping):
            raise IndependentOracleError(f"{template}.dimensions must be an object")
        needs_power = spec.get("needs_power")
        if type(needs_power) is not bool:
            raise IndependentOracleError(f"{template}.needs_power must be boolean")
        actual_template_rules[template] = (
            _strict_int(dimensions.get("w"), label=f"{template}.dimensions.w"),
            _strict_int(dimensions.get("h"), label=f"{template}.dimensions.h"),
            needs_power,
        )
    _record_equal(
        checks,
        errors,
        "rules.template_geometry_and_power",
        actual_template_rules,
        EXPECTED_TEMPLATE_RULES,
    )

    utility = plan.get("utility_operations")
    if not isinstance(utility, Mapping):
        raise IndependentOracleError("preprocess_plan.utility_operations must be an object")
    utility_contract = {
        operation: (
            str(spec.get("facility_type")),
            _strict_int(spec.get("generic_input_slots"), label=f"{operation}.generic_input_slots"),
            _strict_int(spec.get("generic_output_slots"), label=f"{operation}.generic_output_slots"),
        )
        for operation, spec in utility.items()
        if isinstance(spec, Mapping)
    }
    expected_utility = {
        "boundary_io": ("boundary_storage_port", 0, 1),
        "box_sink": ("protocol_storage_box", 3, 0),
        "power_supply": ("power_pole", 0, 0),
        "protocol_core": ("protocol_core", 14, 6),
    }
    _record_equal(checks, errors, "plan.utility_contract", utility_contract, expected_utility)
    return {"template_rules": actual_template_rules, "utility_contract": utility_contract}


def _audit_mandatory_and_ports(
    instances: Any,
    generic_io: Any,
    profiles: Mapping[str, Any],
    port_binding: Any,
    template_rules: Mapping[str, tuple[int, int, bool]],
    pools: Mapping[str, list[Mapping[str, Any]]],
    checks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(instances, list):
        raise IndependentOracleError("mandatory_exact_instances must be a JSON array")
    if not isinstance(generic_io, Mapping):
        raise IndependentOracleError("generic_io_requirements must be an object")

    instance_ids: set[str] = set()
    template_counts: Counter[str] = Counter()
    operation_counts: Counter[str] = Counter()
    powered_count = 0
    mandatory_area = 0
    fixed_inputs = 0
    fixed_outputs = 0
    operation_front_ledger: dict[str, dict[str, Any]] = {}

    for index, instance in enumerate(instances):
        if not isinstance(instance, Mapping):
            raise IndependentOracleError(f"instances[{index}] must be an object")
        instance_id = instance.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise IndependentOracleError(f"instances[{index}].instance_id is invalid")
        if instance_id in instance_ids:
            raise IndependentOracleError(f"duplicate mandatory instance id {instance_id!r}")
        instance_ids.add(instance_id)
        if instance.get("is_mandatory") is not True or instance.get("bound_type") != "exact":
            raise IndependentOracleError(f"{instance_id}: mandatory/exact contract drift")
        template = instance.get("facility_type")
        operation = instance.get("operation_type")
        if not isinstance(template, str) or not isinstance(operation, str):
            raise IndependentOracleError(f"{instance_id}: facility/operation type is invalid")
        if template not in template_rules:
            raise IndependentOracleError(f"{instance_id}: unknown template {template!r}")
        profile = profiles.get(operation)
        if profile is None:
            raise IndependentOracleError(f"{instance_id}: unprofiled operation {operation!r}")
        if str(profile.facility_type) != template:
            raise IndependentOracleError(
                f"{instance_id}: profile template {profile.facility_type!r} != {template!r}"
            )
        input_slots = profile.input_slots
        output_slots = profile.output_slots
        if not isinstance(input_slots, Mapping) or not isinstance(output_slots, Mapping):
            raise IndependentOracleError(f"{instance_id}: production profile slots are malformed")
        if any(type(value) is not int or value < 0 for value in input_slots.values()):
            raise IndependentOracleError(f"{instance_id}: invalid production input slot count")
        if any(type(value) is not int or value < 0 for value in output_slots.values()):
            raise IndependentOracleError(f"{instance_id}: invalid production output slot count")
        fixed_inputs += sum(input_slots.values())
        fixed_outputs += sum(output_slots.values())
        ledger_entry = {
            "facility_type": template,
            "concrete_inputs": sum(input_slots.values()),
            "concrete_outputs": sum(output_slots.values()),
            "generic_input_capacity": _strict_int(
                profile.generic_input_slots,
                label=f"profile.{operation}.generic_input_slots",
            ),
            "generic_output_capacity": _strict_int(
                profile.generic_output_slots,
                label=f"profile.{operation}.generic_output_slots",
            ),
            "modeled_input_witnesses": sum(input_slots.values()),
            "modeled_output_witnesses": sum(output_slots.values())
            + int(profile.generic_output_slots),
        }
        previous_ledger = operation_front_ledger.setdefault(operation, ledger_entry)
        if previous_ledger != ledger_entry:
            raise IndependentOracleError(
                f"{operation}: inconsistent production port profile across instances"
            )
        template_counts[template] += 1
        operation_counts[operation] += 1
        width, height, needs_power = template_rules[template]
        mandatory_area += width * height
        powered_count += int(needs_power)

    actual_template_counts = dict(sorted(template_counts.items()))
    actual_operation_counts = dict(sorted(operation_counts.items()))
    _record_equal(checks, errors, "mandatory.count", len(instances), 266)
    _record_equal(checks, errors, "mandatory.template_counts", actual_template_counts, EXPECTED_TEMPLATE_COUNTS)
    _record_equal(checks, errors, "mandatory.operation_counts", actual_operation_counts, EXPECTED_OPERATION_COUNTS)
    _record_equal(checks, errors, "mandatory.group_count", len(operation_counts), 19)
    _record_equal(checks, errors, "mandatory.powered", powered_count, 219)
    _record_equal(checks, errors, "mandatory.area", mandatory_area, 3_544)
    _record_equal(checks, errors, "ports.fixed_inputs", fixed_inputs, 310)
    _record_equal(checks, errors, "ports.fixed_outputs", fixed_outputs, 264)

    required_outputs = generic_io.get("required_generic_outputs")
    required_inputs = generic_io.get("required_generic_inputs")
    if not isinstance(required_outputs, Mapping) or not isinstance(required_inputs, Mapping):
        raise IndependentOracleError("generic I/O requirement sections must be objects")
    normalized_outputs = {
        str(key): _strict_int(value, label=f"required_generic_outputs.{key}")
        for key, value in required_outputs.items()
    }
    normalized_inputs = {
        str(key): _strict_int(value, label=f"required_generic_inputs.{key}")
        for key, value in required_inputs.items()
    }
    _record_equal(checks, errors, "generic.outputs", normalized_outputs, EXPECTED_GENERIC_OUTPUTS)
    _record_equal(checks, errors, "generic.inputs", normalized_inputs, EXPECTED_GENERIC_INPUTS)

    rfsc_function = getattr(
        port_binding,
        "routing_free_sink_commodities_from_generic_inputs",
        None,
    )
    demand_function = getattr(port_binding, "routing_visible_port_demands", None)
    if not callable(rfsc_function) or not callable(demand_function):
        raise IndependentOracleError("port_binding routing demand SSOT is unavailable")
    routing_free_sink_commodities = rfsc_function(normalized_inputs)
    if type(routing_free_sink_commodities) is not frozenset or any(
        not isinstance(commodity, str) for commodity in routing_free_sink_commodities
    ):
        raise IndependentOracleError(
            "routing_free_sink_commodities_from_generic_inputs returned a malformed set"
        )
    normalized_rfsc = sorted(routing_free_sink_commodities)
    _record_equal(checks, errors, "routing_ssot.rfsc", normalized_rfsc, [])

    direct_demands: dict[str, dict[str, Any]] = {}
    out_of_scope_operations: dict[str, dict[str, Any]] = {}
    direct_input_total = 0
    direct_output_total = 0
    for operation, count in sorted(operation_counts.items()):
        profile = profiles[operation]
        generic_input_slots = int(profile.generic_input_slots)
        generic_output_slots = int(profile.generic_output_slots)
        if generic_input_slots or generic_output_slots:
            try:
                unexpected = demand_function(operation, routing_free_sink_commodities)
            except ValueError as exc:
                out_of_scope_operations[operation] = {
                    "instance_count": int(count),
                    "generic_input_slots": generic_input_slots,
                    "generic_output_slots": generic_output_slots,
                    "rejection_type": type(exc).__name__,
                }
            else:
                _record_equal(
                    checks,
                    errors,
                    f"routing_ssot.{operation}.generic_scope_rejected",
                    unexpected,
                    "ValueError",
                )
            continue

        independent_demand = (
            sum(value for value in profile.input_slots.values() if value > 0),
            sum(
                value
                for commodity, value in profile.output_slots.items()
                if value > 0 and str(commodity) not in routing_free_sink_commodities
            ),
        )
        production_demand = demand_function(operation, routing_free_sink_commodities)
        if (
            not isinstance(production_demand, tuple)
            or len(production_demand) != 2
            or any(type(value) is not int or value < 0 for value in production_demand)
        ):
            raise IndependentOracleError(
                f"routing_visible_port_demands({operation!r}) returned malformed demand "
                f"{production_demand!r}"
            )
        _record_equal(
            checks,
            errors,
            f"routing_ssot.{operation}.differential",
            production_demand,
            independent_demand,
        )
        direct_demands[operation] = {
            "instance_count": int(count),
            "independent": list(independent_demand),
            "production": list(production_demand),
        }
        direct_input_total += int(count) * production_demand[0]
        direct_output_total += int(count) * production_demand[1]

    _record_equal(
        checks,
        errors,
        "routing_ssot.out_of_scope_operations",
        sorted(out_of_scope_operations),
        ["boundary_io", "protocol_core"],
    )
    _record_equal(checks, errors, "routing_ssot.fixed_inputs", direct_input_total, fixed_inputs)
    _record_equal(checks, errors, "routing_ssot.fixed_outputs", direct_output_total, fixed_outputs)

    generic_input_providers = {
        str(operation): {
            "facility_type": str(profile.facility_type),
            "generic_input_capacity": _strict_int(
                profile.generic_input_slots,
                label=f"profile.{operation}.generic_input_slots",
            ),
        }
        for operation, profile in sorted(profiles.items())
        if int(profile.generic_input_slots) > 0
    }
    generic_output_providers = {
        str(operation): {
            "facility_type": str(profile.facility_type),
            "generic_output_capacity": _strict_int(
                profile.generic_output_slots,
                label=f"profile.{operation}.generic_output_slots",
            ),
        }
        for operation, profile in sorted(profiles.items())
        if int(profile.generic_output_slots) > 0
    }

    profile_contract: dict[str, tuple[str, int, int]] = {}
    for operation in ("boundary_io", "box_sink", "protocol_core"):
        profile = profiles.get(operation)
        if profile is None:
            raise IndependentOracleError(f"missing production profile {operation!r}")
        profile_contract[operation] = (
            str(profile.facility_type),
            _strict_int(profile.generic_input_slots, label=f"profile.{operation}.generic_input_slots"),
            _strict_int(profile.generic_output_slots, label=f"profile.{operation}.generic_output_slots"),
        )
    expected_profile_contract = {
        "boundary_io": ("boundary_storage_port", 0, 1),
        "box_sink": ("protocol_storage_box", 3, 0),
        "protocol_core": ("protocol_core", 14, 6),
    }
    _record_equal(
        checks,
        errors,
        "profiles.generic_provider_contract",
        profile_contract,
        expected_profile_contract,
    )

    boundary_physical_outputs = {len(pose["output_port_cells"]) for pose in pools["boundary_storage_port"]}
    core_physical_inputs = {len(pose["input_port_cells"]) for pose in pools["protocol_core"]}
    core_physical_outputs = {len(pose["output_port_cells"]) for pose in pools["protocol_core"]}
    box_physical_inputs = {len(pose["input_port_cells"]) for pose in pools["protocol_storage_box"]}
    box_physical_outputs = {len(pose["output_port_cells"]) for pose in pools["protocol_storage_box"]}
    physical_contract = {
        "boundary_output_ports_per_pose": sorted(boundary_physical_outputs),
        "core_input_ports_per_pose": sorted(core_physical_inputs),
        "core_output_ports_per_pose": sorted(core_physical_outputs),
        "box_input_ports_per_pose": sorted(box_physical_inputs),
        "box_output_ports_per_pose": sorted(box_physical_outputs),
    }
    expected_physical_contract = {
        "boundary_output_ports_per_pose": [1],
        "core_input_ports_per_pose": [14],
        "core_output_ports_per_pose": [6],
        "box_input_ports_per_pose": [3],
        "box_output_ports_per_pose": [3],
    }
    _record_equal(
        checks,
        errors,
        "ports.core_box_boundary_physical_contract",
        physical_contract,
        expected_physical_contract,
    )

    generic_output_total = sum(normalized_outputs.values())
    generic_input_total = sum(normalized_inputs.values())
    mandatory_generic_output_capacity = (
        operation_counts["boundary_io"] * profile_contract["boundary_io"][2]
        + operation_counts["protocol_core"] * profile_contract["protocol_core"][2]
    )
    _record_equal(
        checks,
        errors,
        "generic.output_saturation",
        mandatory_generic_output_capacity,
        generic_output_total,
    )
    routing_inputs = fixed_inputs + generic_input_total
    routing_outputs = fixed_outputs + generic_output_total
    routing_total = routing_inputs + routing_outputs
    _record_equal(checks, errors, "routing.inputs", routing_inputs, 312)
    _record_equal(checks, errors, "routing.outputs", routing_outputs, 316)
    _record_equal(checks, errors, "routing.total", routing_total, 628)

    mandatory = {
        "instance_count": len(instances),
        "group_count": len(operation_counts),
        "template_counts": actual_template_counts,
        "operation_counts": actual_operation_counts,
        "powered_count": powered_count,
        "body_area": mandatory_area,
    }
    routing = {
        "fixed_inputs": fixed_inputs,
        "fixed_outputs": fixed_outputs,
        "generic_inputs": generic_input_total,
        "generic_outputs": generic_output_total,
        "inputs": routing_inputs,
        "outputs": routing_outputs,
        "total": routing_total,
        "generic_requirements": {
            "inputs": normalized_inputs,
            "outputs": normalized_outputs,
        },
        "provider_profiles": profile_contract,
        "physical_port_contract": physical_contract,
        "generic_outputs_globally_saturated": mandatory_generic_output_capacity
        == generic_output_total,
        "operation_front_ledger": dict(sorted(operation_front_ledger.items())),
        "routing_visible_ssot": {
            "rfsc": normalized_rfsc,
            "direct_demands": direct_demands,
            "out_of_scope_operations": out_of_scope_operations,
            "fixed_inputs": direct_input_total,
            "fixed_outputs": direct_output_total,
        },
        "generic_route_contract": {
            "input_requirements": normalized_inputs,
            "output_requirements": normalized_outputs,
            "input_provider_operations": generic_input_providers,
            "output_provider_operations": generic_output_providers,
            "mandatory_output_capacity": mandatory_generic_output_capacity,
            "mandatory_output_demand": generic_output_total,
            "mandatory_outputs_saturate": mandatory_generic_output_capacity
            == generic_output_total,
            "retained_optional_input_provider_templates": ["protocol_storage_box"],
            "retained_optional_output_provider_templates": [],
        },
    }
    return mandatory, routing


def _invalid_result(project_root: Path, exc: BaseException) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "INVALID",
        "ok": False,
        "certificate_eligible": False,
        "project_root": str(project_root),
        "checks": [],
        "errors": [
            {
                "check": "oracle_execution",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        ],
    }


def run_independent_oracle(project_root: Path) -> dict[str, Any]:
    """Recompute the Round 4/5 semantic contract from pinned inputs.

    The result is JSON-serializable.  Callers must require both ``ok`` and
    ``certificate_eligible`` to be literal ``True``; any other shape is a
    fail-closed rejection.
    """

    root = Path(project_root).resolve()
    checks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        payloads: dict[str, Any] = {}
        input_hashes: dict[str, str] = {}
        input_sizes: dict[str, int] = {}
        for relative_path, (expected_size, expected_sha) in EXPECTED_INPUTS.items():
            path = root / relative_path
            payload, size, digest = _load_json(path)
            payloads[relative_path] = payload
            input_sizes[relative_path] = size
            input_hashes[relative_path] = digest
            _record_equal(checks, errors, f"input.{relative_path}.size", size, expected_size)
            _record_equal(checks, errors, f"input.{relative_path}.sha256", digest, expected_sha)

        token_delegate, profiles, port_binding, production_sources = _production_sources(root)
        project_lock_audit = _audit_project_lock_rfsc(root, checks, errors)
        pools = _extract_pools(payloads["data/preprocessed/candidate_placements.json"])
        pool_audit, identity_audit = _audit_pools(
            pools,
            token_delegate,
            checks,
            errors,
        )
        rule_audit = _audit_rules(
            payloads["rules/canonical_rules.json"],
            payloads["rules/preprocess_plan.json"],
            checks,
            errors,
        )
        mandatory_audit, routing_audit = _audit_mandatory_and_ports(
            payloads["data/preprocessed/mandatory_exact_instances.json"],
            payloads["data/preprocessed/generic_io_requirements.json"],
            profiles,
            port_binding,
            rule_audit["template_rules"],
            pools,
            checks,
            errors,
        )

        max_box_slots = 2
        max_pole_slots = mandatory_audit["powered_count"] + max_box_slots
        max_body_slots = mandatory_audit["instance_count"] + max_box_slots + max_pole_slots
        front_body_reference_count = routing_audit["total"] * max_body_slots
        _record_equal(checks, errors, "compact.max_box_slots", max_box_slots, 2)
        _record_equal(checks, errors, "compact.max_pole_slots", max_pole_slots, 221)
        _record_equal(checks, errors, "compact.max_body_slots", max_body_slots, 489)
        _record_equal(
            checks,
            errors,
            "compact.front_body_reference_count",
            front_body_reference_count,
            307_092,
        )

        ghost_anchor_counts = {
            "7x7": (GRID_W - 7 + 1) * (GRID_H - 7 + 1),
            "6x8": (GRID_W - 6 + 1) * (GRID_H - 8 + 1),
            "8x6": (GRID_W - 8 + 1) * (GRID_H - 6 + 1),
        }
        _record_equal(
            checks,
            errors,
            "ghost.target_anchor_counts",
            ghost_anchor_counts,
            {"7x7": 4_096, "6x8": 4_095, "8x6": 4_095},
        )

        oracle_contract = {
            "input_hashes": input_hashes,
            "pool_total": pool_audit["total_poses"],
            "mode_total": pool_audit["mode_count"],
            "pool_counts": pool_audit["pool_counts"],
            "mode_domains": pool_audit["mode_domains"],
            "mandatory_instances": mandatory_audit["instance_count"],
            "mandatory_groups": mandatory_audit["group_count"],
            "mandatory_powered": mandatory_audit["powered_count"],
            "mandatory_area": mandatory_audit["body_area"],
            "routing_in": routing_audit["inputs"],
            "routing_out": routing_audit["outputs"],
            "routing_total": routing_audit["total"],
            "operation_front_ledger": routing_audit["operation_front_ledger"],
            "generic_route_contract": routing_audit["generic_route_contract"],
            "max_box_slots": max_box_slots,
            "max_pole_slots": max_pole_slots,
            "max_body_slots": max_body_slots,
            "front_body_reference_count": front_body_reference_count,
            "front_semantics": identity_audit["semantics"],
            "identity_sentinel_pass": identity_audit["identity_sentinel_pass"],
            "edge_oob_pose_counts": identity_audit["out_of_grid_pose_counts"],
        }
        ok = not errors
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS" if ok else "INVALID",
            "ok": ok,
            "certificate_eligible": ok,
            "project_root": str(root),
            "production_sources": production_sources,
            "project_lock_authority": project_lock_audit,
            "input_hashes": input_hashes,
            "input_sizes": input_sizes,
            "pool": pool_audit,
            "identity_front": identity_audit,
            "rules": rule_audit,
            "mandatory": mandatory_audit,
            "routing_visible": routing_audit,
            "ghost": {
                "grid_width": GRID_W,
                "grid_height": GRID_H,
                "target_anchor_counts": ghost_anchor_counts,
                "anchor_formula": "(70 - width + 1) * (70 - height + 1)",
            },
            "compact_closed_forms": {
                "max_box_slots": max_box_slots,
                "max_pole_slots": max_pole_slots,
                "max_body_slots": max_body_slots,
                "front_witness_count": routing_audit["total"],
                "front_body_reference_count": front_body_reference_count,
                "mandatory_area": mandatory_audit["body_area"],
                "area_formula": "3544 + 9 * active_boxes + 4 * active_poles + ghost_area <= 4900",
                "pole_dominance": "active_poles <= 219 + active_boxes <= 221",
            },
            "oracle_contract": oracle_contract,
            "checks": checks,
            "errors": errors,
        }
    except BaseException as exc:  # fail closed, including import/dependency failures
        result = _invalid_result(root, exc)
        result["checks"] = checks
        if errors:
            result["errors"] = errors + result["errors"]
        return result


def _json_normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_normalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, tuple):
        return [_json_normalize(item) for item in value]
    if isinstance(value, list):
        return [_json_normalize(item) for item in value]
    return value


def _portable_cp_model_proto(model: Any) -> Any:
    proto_method = getattr(model, "Proto", None)
    if not callable(proto_method):
        raise IndependentOracleError("model does not expose callable Proto()")
    raw_proto = proto_method()
    constraints = getattr(raw_proto, "constraints", None)
    if constraints is None:
        raise IndependentOracleError("model Proto() has no constraints collection")
    if not constraints or callable(getattr(constraints[0], "WhichOneof", None)):
        return raw_proto

    # OR-Tools 9.14+ exposes a pybind proto view.  Parse its canonical protobuf
    # text into the generated message so this audit never relies on builder
    # counters or Python wrapper objects.
    from google.protobuf import text_format
    from ortools.sat import cp_model_pb2

    portable = cp_model_pb2.CpModelProto()
    text_format.Parse(str(raw_proto), portable)
    return portable


def _literal_token(raw_literal: Any, variable_names: Sequence[str]) -> str:
    literal = int(raw_literal)
    variable_index = literal if literal >= 0 else -literal - 1
    if not (0 <= variable_index < len(variable_names)):
        raise IndependentOracleError(f"literal references missing variable {literal}")
    name = variable_names[variable_index]
    return name if literal >= 0 else f"NOT({name})"


def audit_compact_model_proto(
    model: Any,
    oracle: Mapping[str, Any],
    ghost_w: int,
    ghost_h: int,
) -> dict[str, Any]:
    """Independently inspect the compact CpModel protobuf topology.

    This audit intentionally consumes only ``model.Proto()`` plus the passing
    oracle's closed forms.  In particular, it does not trust the compact
    builder's ``front_no_overlap_count`` or optional-guard counters.
    """

    checks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    examples: dict[str, list[Any]] = defaultdict(list)
    try:
        if not isinstance(oracle, Mapping) or oracle.get("ok") is not True:
            raise IndependentOracleError("passing oracle is required for Proto audit")
        contract = oracle.get("oracle_contract")
        if not isinstance(contract, Mapping):
            raise IndependentOracleError("oracle_contract is missing for Proto audit")
        if type(ghost_w) is not int or type(ghost_h) is not int:
            raise IndependentOracleError("ghost dimensions must be strict integers")

        expected_mandatory = int(contract["mandatory_instances"])
        expected_boxes = int(contract["max_box_slots"])
        expected_poles = int(contract["max_pole_slots"])
        expected_bodies = int(contract["max_body_slots"])
        expected_fronts = int(contract["routing_total"])
        proto = _portable_cp_model_proto(model)
        variables = list(proto.variables)
        constraints = list(proto.constraints)
        variable_names = [str(variable.name) for variable in variables]
        _record_equal(
            checks,
            errors,
            "proto.variable_names_unique",
            len(variable_names),
            len(set(variable_names)),
        )
        if any(not name for name in variable_names):
            raise IndependentOracleError("Proto contains an unnamed variable")
        variable_index = {name: index for index, name in enumerate(variable_names)}

        constraint_kinds: Counter[str] = Counter()
        interval_by_name: dict[str, tuple[int, Any]] = {}
        duplicate_interval_names: list[str] = []
        for constraint_index, constraint in enumerate(constraints):
            kind = str(constraint.WhichOneof("constraint") or "unknown")
            constraint_kinds[kind] += 1
            if kind == "interval":
                name = str(constraint.name)
                if not name:
                    raise IndependentOracleError("Proto contains an unnamed interval")
                if name in interval_by_name:
                    duplicate_interval_names.append(name)
                interval_by_name[name] = (constraint_index, constraint)
        _record_equal(
            checks,
            errors,
            "proto.interval_names_unique",
            duplicate_interval_names,
            [],
        )
        audited_kinds = {
            "bool_or",
            "element",
            "exactly_one",
            "interval",
            "linear",
            "no_overlap_2d",
            "table",
        }
        _record_equal(
            checks,
            errors,
            "proto.constraint_kinds_audited",
            sorted(constraint_kinds),
            sorted(audited_kinds),
        )
        _record_equal(checks, errors, "proto.all_different_absent", constraint_kinds["all_diff"], 0)
        _record_equal(
            checks,
            errors,
            "proto.variable_count_exact",
            len(variables),
            EXPECTED_COMPACT_VARIABLE_COUNT,
        )
        _record_equal(
            checks,
            errors,
            "proto.constraint_count_exact",
            len(constraints),
            EXPECTED_COMPACT_CONSTRAINT_COUNT,
        )
        _record_equal(
            checks,
            errors,
            "proto.constraint_histogram_exact",
            dict(sorted(constraint_kinds.items())),
            EXPECTED_COMPACT_CONSTRAINT_HISTOGRAM,
        )

        interval_names = set(interval_by_name)

        def prefixed(prefix: str) -> set[str]:
            return {name for name in interval_names if name.startswith(prefix)}

        mandatory_x = prefixed("x_iv__group::")
        mandatory_y = prefixed("y_iv__group::")
        box_x = prefixed("x_iv__normalized_protocol_box::")
        box_y = prefixed("y_iv__normalized_protocol_box::")
        pole_x = prefixed("pole_x_iv__")
        pole_y = prefixed("pole_y_iv__")
        front_x = prefixed("x_iv__front__")
        front_y = prefixed("y_iv__front__")
        ghost_x = {"ghost_x_iv"} & interval_names
        ghost_y = {"ghost_y_iv"} & interval_names

        interval_census = {
            "mandatory_x": len(mandatory_x),
            "mandatory_y": len(mandatory_y),
            "box_x": len(box_x),
            "box_y": len(box_y),
            "pole_x": len(pole_x),
            "pole_y": len(pole_y),
            "front_x": len(front_x),
            "front_y": len(front_y),
            "ghost_x": len(ghost_x),
            "ghost_y": len(ghost_y),
        }
        _record_equal(
            checks,
            errors,
            "proto.interval_census",
            interval_census,
            {
                "mandatory_x": expected_mandatory,
                "mandatory_y": expected_mandatory,
                "box_x": expected_boxes,
                "box_y": expected_boxes,
                "pole_x": expected_poles,
                "pole_y": expected_poles,
                "front_x": expected_fronts,
                "front_y": expected_fronts,
                "ghost_x": 1,
                "ghost_y": 1,
            },
        )

        axis_pairs = (
            (mandatory_x, mandatory_y, "x_iv__", "y_iv__", "mandatory"),
            (box_x, box_y, "x_iv__", "y_iv__", "box"),
            (pole_x, pole_y, "pole_x_iv__", "pole_y_iv__", "pole"),
            (front_x, front_y, "x_iv__", "y_iv__", "front"),
        )
        for x_names, y_names, x_prefix, y_prefix, label in axis_pairs:
            x_suffixes = {name.removeprefix(x_prefix) for name in x_names}
            y_suffixes = {name.removeprefix(y_prefix) for name in y_names}
            _record_equal(
                checks,
                errors,
                f"proto.interval_axis_pairing.{label}",
                sorted(x_suffixes),
                sorted(y_suffixes),
            )

        def guards(interval_name: str) -> tuple[str, ...]:
            constraint = interval_by_name[interval_name][1]
            return tuple(
                _literal_token(literal, variable_names)
                for literal in constraint.enforcement_literal
            )

        guard_violations: list[dict[str, Any]] = []
        for name in sorted(mandatory_x | mandatory_y | front_x | front_y | ghost_x | ghost_y):
            if guards(name):
                guard_violations.append({"interval": name, "guards": guards(name)})
        for box_index in range(expected_boxes):
            for name in (
                f"x_iv__normalized_protocol_box::{box_index}",
                f"y_iv__normalized_protocol_box::{box_index}",
            ):
                if name in interval_by_name and guards(name) != (f"box_active__{box_index}",):
                    guard_violations.append({"interval": name, "guards": guards(name)})
        for pole_index in range(expected_poles):
            for name in (f"pole_x_iv__{pole_index}", f"pole_y_iv__{pole_index}"):
                if name in interval_by_name and guards(name) != (f"pole_active__{pole_index}",):
                    guard_violations.append({"interval": name, "guards": guards(name)})
        _record_equal(
            checks,
            errors,
            "proto.interval_optional_guards",
            len(guard_violations),
            0,
        )
        examples["interval_guard_violations"].extend(guard_violations[:10])

        body_x = mandatory_x | box_x | pole_x
        body_y = mandatory_y | box_y | pole_y
        _record_equal(checks, errors, "proto.body_x_interval_count", len(body_x), expected_bodies)
        _record_equal(checks, errors, "proto.body_y_interval_count", len(body_y), expected_bodies)

        def referenced_intervals(raw_indices: Sequence[Any]) -> list[str]:
            names: list[str] = []
            for raw_index in raw_indices:
                index = int(raw_index)
                if not (0 <= index < len(constraints)):
                    raise IndependentOracleError(
                        f"NoOverlap2D references missing constraint {index}"
                    )
                target = constraints[index]
                if target.WhichOneof("constraint") != "interval":
                    raise IndependentOracleError(
                        f"NoOverlap2D reference {index} is not an interval"
                    )
                names.append(str(target.name))
            return names

        main_no_overlap_count = 0
        front_no_overlap_count = 0
        malformed_no_overlap_count = 0
        ghost_front_mix_count = 0
        front_front_mix_count = 0
        seen_front_suffixes: set[str] = set()
        no_overlap_guarded_count = 0
        for constraint in constraints:
            if constraint.WhichOneof("constraint") != "no_overlap_2d":
                continue
            if constraint.enforcement_literal:
                no_overlap_guarded_count += 1
            x_names = referenced_intervals(constraint.no_overlap_2d.x_intervals)
            y_names = referenced_intervals(constraint.no_overlap_2d.y_intervals)
            x_set = set(x_names)
            y_set = set(y_names)
            x_fronts = x_set & front_x
            y_fronts = y_set & front_y
            has_ghost = "ghost_x_iv" in x_set or "ghost_y_iv" in y_set
            if has_ghost and (x_fronts or y_fronts):
                ghost_front_mix_count += 1
            if len(x_fronts) > 1 or len(y_fronts) > 1:
                front_front_mix_count += 1
            if len(x_names) != len(x_set) or len(y_names) != len(y_set):
                malformed_no_overlap_count += 1
                examples["malformed_no_overlap"].append("duplicate interval reference")
                continue
            if x_set == body_x | {"ghost_x_iv"} and y_set == body_y | {"ghost_y_iv"}:
                main_no_overlap_count += 1
                continue
            if len(x_fronts) == 1 and len(y_fronts) == 1:
                x_front = next(iter(x_fronts))
                y_front = next(iter(y_fronts))
                x_suffix = x_front.removeprefix("x_iv__front__")
                y_suffix = y_front.removeprefix("y_iv__front__")
                if (
                    x_set == body_x | {x_front}
                    and y_set == body_y | {y_front}
                    and x_suffix == y_suffix
                ):
                    front_no_overlap_count += 1
                    if x_suffix in seen_front_suffixes:
                        malformed_no_overlap_count += 1
                        examples["malformed_no_overlap"].append(
                            f"duplicate front witness {x_suffix}"
                        )
                    seen_front_suffixes.add(x_suffix)
                    continue
            malformed_no_overlap_count += 1
            if len(examples["malformed_no_overlap"]) < 10:
                examples["malformed_no_overlap"].append(
                    {
                        "x_count": len(x_names),
                        "y_count": len(y_names),
                        "front_x": sorted(x_fronts),
                        "front_y": sorted(y_fronts),
                        "has_ghost": has_ghost,
                    }
                )

        no_overlap_summary = {
            "total": constraint_kinds["no_overlap_2d"],
            "body_plus_ghost": main_no_overlap_count,
            "per_front_body_clear": front_no_overlap_count,
            "malformed": malformed_no_overlap_count,
            "guarded": no_overlap_guarded_count,
            "ghost_front_mixed": ghost_front_mix_count,
            "front_front_mixed": front_front_mix_count,
            "fronts_seen_once": len(seen_front_suffixes),
        }
        _record_equal(
            checks,
            errors,
            "proto.no_overlap_topology",
            no_overlap_summary,
            {
                "total": expected_fronts + 1,
                "body_plus_ghost": 1,
                "per_front_body_clear": expected_fronts,
                "malformed": 0,
                "guarded": 0,
                "ghost_front_mixed": 0,
                "front_front_mixed": 0,
                "fronts_seen_once": expected_fronts,
            },
        )
        _record_equal(
            checks,
            errors,
            "proto.no_overlap_front_coverage",
            sorted(seen_front_suffixes),
            sorted(name.removeprefix("x_iv__front__") for name in front_x),
        )

        def enforcement_tokens(constraint: Any) -> tuple[str, ...]:
            return tuple(
                _literal_token(literal, variable_names)
                for literal in constraint.enforcement_literal
            )

        def linear_coefficients(constraint: Any) -> dict[str, int]:
            return {
                variable_names[int(index)]: int(coefficient)
                for index, coefficient in zip(constraint.linear.vars, constraint.linear.coeffs)
            }

        def linear_matches(
            constraint: Any,
            coefficients: Mapping[str, int],
            *,
            lower: int | None = None,
            upper: int | None = None,
            enforcement: tuple[str, ...] = (),
        ) -> bool:
            if constraint.WhichOneof("constraint") != "linear":
                return False
            domain = list(constraint.linear.domain)
            if len(domain) != 2 or enforcement_tokens(constraint) != enforcement:
                return False
            if linear_coefficients(constraint) != dict(coefficients):
                return False
            return (lower is None or int(domain[0]) == lower) and (
                upper is None or int(domain[1]) == upper
            )

        # Fronts may share a belt cell.  The only cross-witness linear links are
        # therefore key-order/distinctness symmetries; no x/y/dx/dy relation may
        # connect different witnesses, and no constraint may connect a ghost
        # coordinate to any front variable.
        front_fields = (
            "key__front__",
            "dx__front__",
            "dy__front__",
            "x__front__",
            "y__front__",
            "x_end__front__",
            "y_end__front__",
        )

        def front_owner(name: str) -> str | None:
            for prefix in front_fields:
                if name.startswith(prefix):
                    return name.removeprefix(prefix)
            return None

        cross_front_coordinate_constraints = 0
        ghost_front_linear_constraints = 0
        cross_front_key_constraints = 0
        for constraint in constraints:
            if constraint.WhichOneof("constraint") != "linear":
                continue
            names = [variable_names[int(index)] for index in constraint.linear.vars]
            owners = {owner for name in names if (owner := front_owner(name)) is not None}
            if len(owners) > 1:
                front_names = [name for name in names if front_owner(name) is not None]
                if all(name.startswith("key__front__") for name in front_names):
                    cross_front_key_constraints += 1
                else:
                    cross_front_coordinate_constraints += 1
                    if len(examples["cross_front_coordinate_constraints"]) < 10:
                        examples["cross_front_coordinate_constraints"].append(front_names)
            if any(name.startswith("ghost_") for name in names) and owners:
                ghost_front_linear_constraints += 1
        _record_equal(
            checks,
            errors,
            "proto.cross_front_coordinate_constraints_absent",
            cross_front_coordinate_constraints,
            0,
        )
        _record_equal(
            checks,
            errors,
            "proto.ghost_front_linear_constraints_absent",
            ghost_front_linear_constraints,
            0,
        )

        owner_prefix = "is_owner__front__generic_input__"
        owner_names: dict[tuple[str, int], str] = {}
        for name in variable_names:
            if not name.startswith(owner_prefix):
                continue
            raw = name.removeprefix(owner_prefix)
            commodity, separator, provider_text = raw.rpartition("__")
            if not separator or not provider_text.isdigit():
                raise IndependentOracleError(f"malformed generic owner literal {name!r}")
            owner_names[(commodity, int(provider_text))] = name
        expected_commodities = sorted(EXPECTED_GENERIC_INPUTS)
        expected_owner_keys = {
            (commodity, provider_index)
            for commodity in expected_commodities
            for provider_index in range(3)
        }
        _record_equal(
            checks,
            errors,
            "proto.generic_owner_literals",
            sorted(owner_names),
            sorted(expected_owner_keys),
        )

        exactly_one_sets = [
            {
                _literal_token(literal, variable_names)
                for literal in constraint.exactly_one.literals
            }
            for constraint in constraints
            if constraint.WhichOneof("constraint") == "exactly_one"
            and not constraint.enforcement_literal
        ]
        owner_exactly_one_counts: dict[str, int] = {}
        for commodity in expected_commodities:
            expected_set = {
                owner_names[(commodity, provider_index)]
                for provider_index in range(3)
                if (commodity, provider_index) in owner_names
            }
            owner_exactly_one_counts[commodity] = sum(
                literal_set == expected_set for literal_set in exactly_one_sets
            )
        _record_equal(
            checks,
            errors,
            "proto.generic_owner_exactly_one",
            owner_exactly_one_counts,
            {commodity: 1 for commodity in expected_commodities},
        )

        box_optional_summary: dict[str, Any] = {}
        for box_index in range(expected_boxes):
            active_name = f"box_active__{box_index}"
            active_index = variable_index.get(active_name, -1)
            positive_guard_count = sum(
                active_name in enforcement_tokens(constraint)
                for constraint in constraints
            )
            negative_guard_count = sum(
                f"NOT({active_name})" in enforcement_tokens(constraint)
                for constraint in constraints
            )
            provider_index = box_index + 1
            provider_owner_names = {
                owner_names[(commodity, provider_index)]
                for commodity in expected_commodities
                if (commodity, provider_index) in owner_names
            }
            reverse_usage_count = sum(
                constraint.WhichOneof("constraint") == "bool_or"
                and enforcement_tokens(constraint) == (active_name,)
                and {
                    _literal_token(literal, variable_names)
                    for literal in constraint.bool_or.literals
                }
                == provider_owner_names
                for constraint in constraints
            )
            owner_activates_count = 0
            for owner_name in provider_owner_names:
                owner_activates_count += sum(
                    linear_matches(
                        constraint,
                        {active_name: 1},
                        lower=1,
                        upper=1,
                        enforcement=(owner_name,),
                    )
                    for constraint in constraints
                )
            inactive_fix_names = {
                f"x__normalized_protocol_box::{box_index}",
                f"y__normalized_protocol_box::{box_index}",
                f"mode__normalized_protocol_box::{box_index}",
            }
            inactive_fixed = {
                name
                for name in inactive_fix_names
                if any(
                    linear_matches(
                        constraint,
                        {name: 1},
                        lower=0,
                        upper=0,
                        enforcement=(f"NOT({active_name})",),
                    )
                    for constraint in constraints
                )
            }
            coverer_fragment = f"__normalized_protocol_box::{box_index}"
            guarded_power_count = sum(
                constraint.WhichOneof("constraint") == "linear"
                and enforcement_tokens(constraint) == (active_name,)
                and any(
                    name.startswith("coverer_") and name.endswith(coverer_fragment)
                    for name in linear_coefficients(constraint)
                )
                for constraint in constraints
            )
            box_optional_summary[str(box_index)] = {
                "positive_guard_count": positive_guard_count,
                "negative_guard_count": negative_guard_count,
                "reverse_usage_bool_or": reverse_usage_count,
                "owner_activates": owner_activates_count,
                "inactive_zero_fields": sorted(inactive_fixed),
                "guarded_power_constraints": guarded_power_count,
                "active_variable_present": active_index >= 0,
            }
        expected_box_optional_summary = {
            "0": {
                "positive_guard_count": 8,
                "negative_guard_count": 3,
                "reverse_usage_bool_or": 1,
                "owner_activates": 2,
                "inactive_zero_fields": [
                    "mode__normalized_protocol_box::0",
                    "x__normalized_protocol_box::0",
                    "y__normalized_protocol_box::0",
                ],
                "guarded_power_constraints": 5,
                "active_variable_present": True,
            },
            "1": {
                "positive_guard_count": 9,
                "negative_guard_count": 3,
                "reverse_usage_bool_or": 1,
                "owner_activates": 2,
                "inactive_zero_fields": [
                    "mode__normalized_protocol_box::1",
                    "x__normalized_protocol_box::1",
                    "y__normalized_protocol_box::1",
                ],
                "guarded_power_constraints": 5,
                "active_variable_present": True,
            },
        }
        _record_equal(
            checks,
            errors,
            "proto.box_optional_topology",
            box_optional_summary,
            expected_box_optional_summary,
        )

        box_prefix_count = sum(
            linear_matches(
                constraint,
                {"box_active__0": 1, "box_active__1": -1},
                lower=0,
            )
            for constraint in constraints
        )
        box_order_count = sum(
            linear_matches(
                constraint,
                {
                    "order__normalized_protocol_box::0": 1,
                    "order__normalized_protocol_box::1": -1,
                },
                upper=-1,
                enforcement=("box_active__1",),
            )
            for constraint in constraints
        )
        _record_equal(checks, errors, "proto.box_active_prefix", box_prefix_count, 1)
        _record_equal(checks, errors, "proto.box_strict_order", box_order_count, 1)

        pole_guard_violations = 0
        pole_prefix_count = 0
        pole_order_count = 0
        for pole_index in range(expected_poles):
            active_name = f"pole_active__{pole_index}"
            positive_guard_count = sum(
                active_name in enforcement_tokens(constraint)
                for constraint in constraints
            )
            negative_guard_count = sum(
                f"NOT({active_name})" in enforcement_tokens(constraint)
                for constraint in constraints
            )
            if positive_guard_count != (2 if pole_index == 0 else 3):
                pole_guard_violations += 1
            if negative_guard_count != 2:
                pole_guard_violations += 1
            if pole_index == 0:
                continue
            pole_prefix_count += sum(
                linear_matches(
                    constraint,
                    {
                        f"pole_active__{pole_index - 1}": 1,
                        active_name: -1,
                    },
                    lower=0,
                )
                for constraint in constraints
            )
            pole_order_count += sum(
                linear_matches(
                    constraint,
                    {
                        f"pole_order__{pole_index - 1}": 1,
                        f"pole_order__{pole_index}": -1,
                    },
                    upper=-1,
                    enforcement=(active_name,),
                )
                for constraint in constraints
            )
        _record_equal(checks, errors, "proto.pole_optional_guard_violations", pole_guard_violations, 0)
        _record_equal(checks, errors, "proto.pole_active_prefix", pole_prefix_count, expected_poles - 1)
        _record_equal(checks, errors, "proto.pole_strict_order", pole_order_count, expected_poles - 1)

        coverer_census = {
            "index_vars": sum(name.startswith("coverer_index__") for name in variable_names),
            "active_vars": sum(name.startswith("coverer_active__") for name in variable_names),
            "x_vars": sum(name.startswith("coverer_x__") for name in variable_names),
            "y_vars": sum(name.startswith("coverer_y__") for name in variable_names),
            "element_constraints": constraint_kinds["element"],
            "guarded_element_constraints": sum(
                bool(constraint.enforcement_literal)
                for constraint in constraints
                if constraint.WhichOneof("constraint") == "element"
            ),
        }
        expected_coverers = int(contract["mandatory_powered"]) + expected_boxes
        _record_equal(
            checks,
            errors,
            "proto.designated_power_coverers",
            coverer_census,
            {
                "index_vars": expected_coverers,
                "active_vars": expected_coverers,
                "x_vars": expected_coverers,
                "y_vars": expected_coverers,
                "element_constraints": 3 * expected_coverers,
                "guarded_element_constraints": 0,
            },
        )

        ok = not errors
        return {
            "schema_version": f"{SCHEMA_VERSION}.proto_topology_v1",
            "status": "PASS" if ok else "INVALID",
            "ok": ok,
            "certificate_eligible": ok,
            "ghost": {"width": ghost_w, "height": ghost_h},
            "constraint_histogram": dict(sorted(constraint_kinds.items())),
            "interval_census": interval_census,
            "no_overlap": no_overlap_summary,
            "cross_front_key_constraints": cross_front_key_constraints,
            "box_optional": box_optional_summary,
            "power_coverers": coverer_census,
            "checks": checks,
            "errors": errors,
            "examples": {key: value for key, value in sorted(examples.items()) if value},
        }
    except BaseException as exc:
        return {
            "schema_version": f"{SCHEMA_VERSION}.proto_topology_v1",
            "status": "INVALID",
            "ok": False,
            "certificate_eligible": False,
            "ghost": {"width": ghost_w, "height": ghost_h},
            "checks": checks,
            "errors": [
                *errors,
                {
                    "check": "proto_topology_execution",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
            ],
            "examples": {key: value for key, value in sorted(examples.items()) if value},
        }


def compare_oracle_to_build(
    oracle: Mapping[str, Any],
    build_audit: Mapping[str, Any],
    ghost_w: int,
    ghost_h: int,
    model: Any | None = None,
) -> dict[str, Any]:
    """Compare a compact-model build audit against the independent contract.

    The builder should expose the canonical fields in an ``oracle_contract``
    submapping.  For convenience, the same exact field names are also accepted
    at the audit top level.  ``model`` is mandatory for certificate eligibility:
    its raw CpModel Proto is audited independently of builder counters.  Missing
    fields or a missing model are mismatches, not defaults.
    """

    comparisons: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    def fail(check: str, message: str, *, expected: Any = None, actual: Any = None) -> None:
        entry: dict[str, Any] = {"check": check, "message": message}
        if expected is not None:
            entry["expected"] = expected
        if actual is not None:
            entry["actual"] = actual
        errors.append(entry)

    if not isinstance(oracle, Mapping) or oracle.get("ok") is not True:
        fail("oracle.ok", "oracle is absent or not a passing fail-closed result")
    if not isinstance(oracle, Mapping) or oracle.get("certificate_eligible") is not True:
        fail(
            "oracle.certificate_eligible",
            "oracle did not explicitly mark the contract certificate-eligible",
        )
    if not isinstance(oracle, Mapping) or oracle.get("status") != "PASS":
        fail("oracle.status", "oracle status must be literal PASS")
    if not isinstance(build_audit, Mapping):
        fail("build_audit", "build audit must be a mapping")
        build_audit = {}
    if type(ghost_w) is not int or type(ghost_h) is not int:
        fail("ghost.dimensions", "ghost dimensions must be strict integers")
        ghost_w = -1
        ghost_h = -1
    elif not (1 <= ghost_w <= GRID_W and 1 <= ghost_h <= GRID_H):
        fail("ghost.dimensions", "ghost dimensions are outside the 70x70 grid")

    oracle_contract = oracle.get("oracle_contract", {}) if isinstance(oracle, Mapping) else {}
    if not isinstance(oracle_contract, Mapping):
        fail("oracle.contract", "oracle_contract must be a mapping")
        oracle_contract = {}
    build_contract = build_audit.get("oracle_contract", build_audit)
    if not isinstance(build_contract, Mapping):
        fail("build.contract", "build oracle_contract must be a mapping")
        build_contract = {}

    required_fields = (
        "input_hashes",
        "pool_total",
        "mode_total",
        "pool_counts",
        "mode_domains",
        "mandatory_instances",
        "mandatory_groups",
        "mandatory_powered",
        "mandatory_area",
        "routing_in",
        "routing_out",
        "routing_total",
        "operation_front_ledger",
        "generic_route_contract",
        "max_box_slots",
        "max_pole_slots",
        "max_body_slots",
        "front_body_reference_count",
        "front_semantics",
        "identity_sentinel_pass",
        "edge_oob_pose_counts",
    )
    for field in required_fields:
        if field not in oracle_contract:
            fail(f"oracle.{field}", "passing oracle omitted required contract field")
            continue
        if field in build_contract:
            actual = build_contract[field]
        elif field in build_audit:
            actual = build_audit[field]
        else:
            fail(f"build.{field}", "build audit omitted required contract field")
            continue
        expected = oracle_contract[field]
        ok = _json_normalize(actual) == _json_normalize(expected)
        comparisons.append({"field": field, "ok": ok})
        if not ok:
            fail(
                f"build.{field}",
                "build/oracle mismatch",
                expected=expected,
                actual=actual,
            )

    ghost_anchor_count = (
        (GRID_W - ghost_w + 1) * (GRID_H - ghost_h + 1)
        if 1 <= ghost_w <= GRID_W and 1 <= ghost_h <= GRID_H
        else 0
    )
    ghost_expected = {
        "ghost_w": ghost_w,
        "ghost_h": ghost_h,
        "ghost_anchor_count": ghost_anchor_count,
    }
    for field, expected in ghost_expected.items():
        if field in build_contract:
            actual = build_contract[field]
        elif field in build_audit:
            actual = build_audit[field]
        else:
            fail(f"build.{field}", "build audit omitted required ghost field")
            continue
        ok = type(actual) is int and actual == expected
        comparisons.append({"field": field, "ok": ok})
        if not ok:
            fail(
                f"build.{field}",
                "build/oracle ghost mismatch",
                expected=expected,
                actual=actual,
            )

    if "ok" in build_audit and build_audit.get("ok") is not True:
        fail("build.ok", "builder marked its own audit non-passing", actual=build_audit.get("ok"))

    proto_topology = audit_compact_model_proto(model, oracle, ghost_w, ghost_h)
    if proto_topology.get("ok") is not True or proto_topology.get("certificate_eligible") is not True:
        fail(
            "model.proto_topology",
            "independent CpModel Proto topology audit did not pass",
            actual=proto_topology.get("errors"),
        )

    ok = not errors
    return {
        "schema_version": f"{SCHEMA_VERSION}.comparison_v1",
        "status": "PASS" if ok else "MISMATCH",
        "ok": ok,
        "certificate_eligible": ok,
        "ghost": {
            "width": ghost_w,
            "height": ghost_h,
            "anchor_count": ghost_anchor_count,
        },
        "proto_topology": proto_topology,
        "comparisons": comparisons,
        "errors": errors,
    }


if __name__ == "__main__":
    default_root = Path(__file__).resolve().parents[4]
    print(json.dumps(run_independent_oracle(default_root), ensure_ascii=False, indent=2))
