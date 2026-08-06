"""Strict research-only adapter for ``band22-witness/2`` coordinate witnesses."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from devtools.research_run_contract import read_stable_snapshot
from src.io.strict_json import loads_strict_json
from src.models.port_binding import enumerate_pose_level_port_bindings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GRID_W = GRID_H = 70
DIRS = frozenset({"N", "E", "S", "W"})
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
ROUTE_KINDS = frozenset({"straight", "turn", "merger", "splitter"})
SOURCE_PATHS = {"candidate_placements": "data/preprocessed/candidate_placements.json",
                "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
                "canonical_rules": "rules/canonical_rules.json", "generic_io_requirements": "data/preprocessed/generic_io_requirements.json"}


def _obj(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a JSON object")
    return value

def _array(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a JSON array")
    return value
def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a strict JSON integer")
    return value
def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value
def _xy(value: Any, field: str) -> tuple[int, int]:
    pair = _array(value, field)
    if len(pair) != 2:
        raise ValueError(f"{field} must contain two integers")
    return _integer(pair[0], f"{field}[0]"), _integer(pair[1], f"{field}[1]")
def official_pose_params_for_mode(facility_type: str, witness_mode: str) -> tuple[int, str]:
    table = {
        ("boundary_storage_port", "bottom_boundary"): (1, "bottom_base"), ("boundary_storage_port", "left_boundary"): (0, "left_base"),
        ("protocol_core", "inputs_east_west"): (1, "core_TB_out"),
        ("manufacturing_3x3", "north_to_south"): (0, "TB"), ("manufacturing_3x3", "south_to_north"): (0, "BT"),
        ("manufacturing_5x5", "north_to_south"): (0, "TB"), ("manufacturing_5x5", "south_to_north"): (0, "BT"),
        ("manufacturing_6x4", "north_to_south"): (0, "TB"), ("manufacturing_6x4", "south_to_north"): (0, "BT"),
        ("manufacturing_6x4", "west_to_east"): (1, "LR"),
    }
    try:
        return table[(facility_type, witness_mode)]
    except KeyError as exc:
        raise ValueError(f"unsupported band22 mode: {facility_type}/{witness_mode}") from exc
def _pose_key(facility_type: str, raw: Any, field: str) -> tuple[Any, ...]:
    pose = _obj(raw, field)
    anchor = _obj(pose.get("anchor"), f"{field}.anchor")
    params = _obj(pose.get("pose_params"), f"{field}.pose_params")
    return (facility_type, _integer(anchor.get("x"), f"{field}.x"), _integer(anchor.get("y"), f"{field}.y"),
            _integer(params.get("orientation"), f"{field}.orientation"), _text(params.get("port_mode"), f"{field}.port_mode"))
def build_pose_index(facility_pools: Mapping[str, Any]) -> dict[tuple[Any, ...], list[tuple[int, Mapping[str, Any]]]]:
    index: dict[tuple[Any, ...], list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for facility_type, raw_pool in facility_pools.items():
        for pose_idx, raw_pose in enumerate(_array(raw_pool, f"facility_pools.{facility_type}")):
            pose = _obj(raw_pose, f"facility_pools.{facility_type}[{pose_idx}]")
            index[_pose_key(str(facility_type), pose, f"facility_pools.{facility_type}[{pose_idx}]")].append((pose_idx, pose))
    return dict(index)
def match_unique_pose(pose_index: Mapping[tuple[Any, ...], Any], key: tuple[Any, ...]) -> tuple[int, Mapping[str, Any]]:
    matches = list(pose_index.get(key, ()))
    if len(matches) != 1:
        raise ValueError(f"official pose lookup must be unique for {key!r}; matches={len(matches)}")
    return matches[0]
def _port_geometry(raw: Any, field: str) -> tuple[str, int, int, str]:
    port = _obj(raw, field)
    kind = _text(port.get("kind"), f"{field}.kind")
    direction = _text(port.get("direction"), f"{field}.direction")
    x, y = _xy(port.get("front"), f"{field}.front")
    if kind not in {"input", "output"} or direction not in DIRS or not (0 <= x < 70 and 0 <= y < 70):
        raise ValueError(f"{field} has invalid kind/direction/front")
    return kind, x, y, direction
def _active_signature(raw: Any, field: str, iid: str | None = None) -> tuple[Any, ...]:
    port = _obj(raw, field)
    kind, x, y, direction = _port_geometry(port, field)
    signature = (kind, _text(port.get("commodity"), f"{field}.commodity"), x, y, direction)
    return signature if iid is None else (iid, *signature)
def _domain_signature(raw: Any, field: str) -> tuple[Any, ...]:
    port = _obj(raw, field)
    return (_text(port.get("type"), f"{field}.type"), _text(port.get("commodity"), f"{field}.commodity"), _integer(port.get("x"), f"{field}.x"),
            _integer(port.get("y"), f"{field}.y"), _text(port.get("dir"), f"{field}.dir"))
def project_unique_binding(operation_type: str, pose: Mapping[str, Any], witness_ports: Any) -> dict[str, Any]:
    target = Counter(_active_signature(port, "witness active port") for port in _array(witness_ports, "active_ports"))
    domain = enumerate_pose_level_port_bindings(operation_type, pose)
    matches: list[tuple[int, Mapping[str, Any]]] = []
    for domain_idx, raw_entry in enumerate(domain):
        entry = _obj(raw_entry, f"binding_domain[{domain_idx}]")
        ports = _array(entry.get("active_ports"), f"binding_domain[{domain_idx}].active_ports")
        if Counter(_domain_signature(port, "domain active port") for port in ports) == target:
            matches.append((domain_idx, entry))
    if len(matches) != 1:
        raise ValueError(f"official binding domain match must be unique; matches={len(matches)}")
    domain_idx, entry = matches[0]
    return {"domain_size": len(domain), "matching_domain_index": domain_idx,
            "input_ports": [dict(x) for x in _array(entry.get("input_ports"), "binding.input_ports")],
            "output_ports": [dict(x) for x in _array(entry.get("output_ports"), "binding.output_ports")]}
def audit_route_components(raw_routes: Any) -> tuple[list[list[int]], dict[str, Any]]:
    routes = _array(raw_routes, "route_components")
    seen: set[tuple[int, int]] = set()
    counts: Counter[str] = Counter()
    for idx, raw in enumerate(routes):
        route = _obj(raw, f"route_components[{idx}]")
        cell = (_integer(route.get("x"), f"route[{idx}].x"), _integer(route.get("y"), f"route[{idx}].y"))
        if cell in seen or not (0 <= cell[0] < 70 and 0 <= cell[1] < 70):
            raise ValueError(f"route[{idx}] coordinate is duplicate/out-of-grid")
        seen.add(cell)
        kind = _text(route.get("kind"), f"route[{idx}].kind")
        inputs = list(_array(route.get("inputs"), f"route[{idx}].inputs"))
        outputs = list(_array(route.get("outputs"), f"route[{idx}].outputs"))
        if kind not in ROUTE_KINDS or any(not isinstance(d, str) or d not in DIRS for d in inputs + outputs):
            raise ValueError(f"route[{idx}] has a forbidden kind/direction")
        if len(set(inputs)) != len(inputs) or len(set(outputs)) != len(outputs) or set(inputs) & set(outputs):
            raise ValueError(f"route[{idx}] has duplicate/shared direction sides")
        shape_ok = ((kind == "straight" and len(inputs) == len(outputs) == 1 and outputs[0] == OPPOSITE[inputs[0]]) or
                    (kind == "turn" and len(inputs) == len(outputs) == 1 and outputs[0] not in {inputs[0], OPPOSITE[inputs[0]]}) or
                    (kind == "merger" and len(inputs) >= 2 and len(outputs) == 1) or
                    (kind == "splitter" and len(inputs) == 1 and len(outputs) >= 2))
        if not shape_ok or (len(inputs) >= 2 and len(outputs) >= 2):
            raise ValueError(f"route[{idx}] violates no-cross/arity contract")
        counts[kind] += 1
    return [list(cell) for cell in sorted(seen)], {
        "ok": True, "route_component_count": len(routes), "component_counts": dict(sorted(counts.items())),
        "allowed_kinds": sorted(ROUTE_KINDS), "cross_count": 0, "authority": "provenance_structure_only_not_official_fixed_routes"}
def _requirements(raw: Any, field: str) -> Counter[str]:
    result: Counter[str] = Counter()
    for commodity, raw_count in _obj(raw, field).items():
        count = _integer(raw_count, f"{field}.{commodity}")
        if count <= 0:
            raise ValueError(f"{field}.{commodity} must be positive")
        result[_text(commodity, f"{field} key")] = count
    return result
def adapt_band22_v2_payload(
    payload: Mapping[str, Any], *, facility_pools: Mapping[str, Any], mandatory_instances: Sequence[Any], canonical_rules: Mapping[str, Any],
    generic_io_requirements: Mapping[str, Any] | None = None, source_audit: Mapping[str, Any] | None = None,
    witness_path: str | None = None, witness_sha256: str | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    witness = _obj(payload, "witness")
    if witness.get("witness_schema_version") != "band22-witness/2":
        raise ValueError("witness_schema_version must be band22-witness/2")
    grid = _obj(witness.get("grid"), "grid")
    if (_integer(grid.get("width"), "grid.width"), _integer(grid.get("height"), "grid.height")) != (70, 70):
        raise ValueError("band22 v2 grid must be 70x70")
    rules_global = _obj(canonical_rules.get("globals"), "rules.globals")
    empty_rule = _obj(rules_global.get("empty_rectangle"), "rules.empty_rectangle")
    canonical_min_side = _integer(empty_rule.get("min_side_admissibility"), "rules.min_side")
    hole = _obj(witness.get("hole"), "hole")
    x0, x1 = _xy(hole.get("x_range"), "hole.x_range")
    y0, y1 = _xy(hole.get("y_range"), "hole.y_range")
    width, height = x1 - x0 + 1, y1 - y0 + 1
    if (width, height, width * height, min(width, height), canonical_min_side) != (7, 6, 42, 6, 6):
        raise ValueError("hole must derive to 7x6/area42/min-side6")
    if x0 < 0 or y0 < 0 or x1 >= 70 or y1 >= 70:
        raise ValueError("hole is out of grid")
    for key, expected in (("width", width), ("height", height), ("area", width * height)):
        if _integer(hole.get(key), f"hole.{key}") != expected:
            raise ValueError(f"hole.{key} disagrees with inclusive ranges")

    facilities = _obj(witness.get("facilities"), "facilities")
    boundary = list(_array(facilities.get("boundary_ports"), "facilities.boundary_ports"))
    core = _obj(facilities.get("protocol_core"), "facilities.protocol_core")
    machines = list(_array(facilities.get("manufacturing"), "facilities.manufacturing"))
    poles = list(_array(facilities.get("power_poles"), "facilities.power_poles"))
    if list(_array(facilities.get("storage_boxes"), "facilities.storage_boxes")) or not poles:
        raise ValueError("storage_boxes must be empty and power_poles must be non-empty")
    flat = boundary + [core] + machines
    if (len(boundary), len(machines), len(flat)) != (46, 219, 266):
        raise ValueError("mandatory accounting must be 46 boundary + 1 core + 219 manufacturing")

    mandatory: dict[str, Mapping[str, Any]] = {}
    for idx, raw in enumerate(_array(mandatory_instances, "mandatory_instances")):
        inst = _obj(raw, f"mandatory[{idx}]")
        iid = _text(inst.get("instance_id"), f"mandatory[{idx}].instance_id")
        if iid in mandatory or inst.get("is_mandatory") is not True:
            raise ValueError(f"duplicate/non-mandatory artifact instance {iid}")
        mandatory[iid] = inst
    records: dict[str, Mapping[str, Any]] = {}
    for idx, raw in enumerate(flat):
        rec = _obj(raw, f"facilities.flattened[{idx}]")
        iid = _text(rec.get("instance_id"), f"facilities.flattened[{idx}].instance_id")
        if iid in records:
            raise ValueError(f"duplicate witness instance {iid}")
        records[iid] = rec
    if len(mandatory) != 266 or set(records) != set(mandatory):
        raise ValueError("witness IDs must exactly equal mandatory artifact IDs")

    index = build_pose_index(facility_pools)
    solution: dict[str, dict[str, Any]] = {}
    selected: dict[str, tuple[Mapping[str, Any], int, Mapping[str, Any], str]] = {}
    nested_active: Counter[tuple[Any, ...]] = Counter()
    core_rows: list[Mapping[str, Any]] = []
    boundary_ids = {str(_obj(x, "boundary").get("instance_id")) for x in boundary}
    machine_ids = {str(_obj(x, "machine").get("instance_id")) for x in machines}
    core_id = _text(core.get("instance_id"), "protocol_core.instance_id")
    for iid, rec in records.items():
        inst = mandatory[iid]
        facility_type = _text(inst.get("facility_type"), f"mandatory.{iid}.facility_type")
        expected_group = ((iid in boundary_ids and facility_type == "boundary_storage_port") or
                          (iid == core_id and facility_type == "protocol_core") or
                          (iid in machine_ids and facility_type.startswith("manufacturing_")))
        if not expected_group or _text(rec.get("template"), f"{iid}.template") != facility_type:
            raise ValueError(f"{iid} is in the wrong facility group/template")
        ax, ay = _xy(rec.get("anchor"), f"{iid}.anchor")
        orientation, port_mode = official_pose_params_for_mode(facility_type, _text(rec.get("mode"), f"{iid}.mode"))
        pose_idx, pose = match_unique_pose(index, (facility_type, ax, ay, orientation, port_mode))
        pose_id = _text(pose.get("pose_id"), f"{iid}.official.pose_id")
        operation_type = _text(inst.get("operation_type"), f"mandatory.{iid}.operation_type")
        solution[iid] = {"instance_id": iid, "facility_type": facility_type, "operation_type": operation_type,
                         "pose_idx": pose_idx, "pose_id": pose_id, "anchor": {"x": ax, "y": ay}}
        selected[iid] = rec, pose_idx, pose, operation_type
        if iid == core_id:
            core_rows = [_obj(row, f"{iid}.ports") for row in _array(rec.get("ports"), f"{iid}.ports")]
            active_rows = []
            for row_idx, row in enumerate(core_rows):
                if not isinstance(row.get("active"), bool):
                    raise ValueError(f"{iid}.ports[{row_idx}].active must be boolean")
                if row["active"]:
                    active_rows.append(row)
                elif row.get("commodity") is not None:
                    raise ValueError(f"inactive core port {row_idx} must have null commodity")
        else:
            active_rows = _array(rec.get("active_ports"), f"{iid}.active_ports")
        nested_active.update(_active_signature(row, f"{iid}.active", iid) for row in active_rows)

    flat_active: Counter[tuple[Any, ...]] = Counter()
    for idx, raw in enumerate(_array(witness.get("active_ports"), "active_ports")):
        row = _obj(raw, f"active_ports[{idx}]")
        iid = _text(row.get("instance_id"), f"active_ports[{idx}].instance_id")
        signature = _active_signature(row, f"active_ports[{idx}]", iid)
        if iid not in records or row.get("component_direction") != OPPOSITE[signature[-1]]:
            raise ValueError(f"active_ports[{idx}] has unknown owner/bad component direction")
        flat_active[signature] += 1
    if flat_active != nested_active or len(flat_active) != sum(flat_active.values()) or sum(flat_active.values()) != 628:
        raise ValueError("nested/top active_ports must be an exact duplicate-free 628-row multiset")

    pose_projection: dict[str, Any] = {}
    for iid in sorted(machine_ids):
        rec, pose_idx, pose, operation_type = selected[iid]
        projected = project_unique_binding(operation_type, pose, rec.get("active_ports"))
        pose_projection[iid] = {"operation_type": operation_type, "pose_idx": pose_idx, "pose_id": str(pose["pose_id"]), **projected}

    generic_inputs: dict[str, str] = {}
    generic_outputs: dict[str, str] = {}
    for raw in boundary:
        rec = _obj(raw, "boundary")
        iid = str(rec["instance_id"])
        rows = list(_array(rec.get("active_ports"), f"{iid}.active_ports"))
        for local_idx, raw_port in enumerate(_array(selected[iid][2].get("output_port_cells"), f"{iid}.outputs")):
            port = _obj(raw_port, f"{iid}.output[{local_idx}]")
            hits = [row for row in rows if _port_geometry(row, f"{iid}.active") == ("output", port.get("x"), port.get("y"), port.get("dir"))]
            if len(hits) != 1:
                raise ValueError(f"{iid}:out:{local_idx} must uniquely match")
            generic_outputs[f"{iid}:out:{local_idx}"] = str(_obj(hits[0], f"{iid}.active")["commodity"])

    core_geometry: dict[tuple[str, int, int, str], Mapping[str, Any]] = {}
    for idx, row in enumerate(core_rows):
        key = _port_geometry(row, f"{core_id}.ports[{idx}]")
        if key in core_geometry:
            raise ValueError(f"duplicate core physical port {key}")
        core_geometry[key] = row
    used: set[tuple[str, int, int, str]] = set()
    core_pose = selected[core_id][2]
    for side, output in (("input", generic_inputs), ("output", generic_outputs)):
        for local_idx, raw_port in enumerate(_array(core_pose.get(f"{side}_port_cells"), f"core.{side}_ports")):
            port = _obj(raw_port, f"core.{side}[{local_idx}]")
            key = (side, _integer(port.get("x"), "core.port.x"), _integer(port.get("y"), "core.port.y"), _text(port.get("dir"), "core.port.dir"))
            row = core_geometry.get(key)
            if row is None:
                raise ValueError(f"official core port missing from witness: {key}")
            used.add(key)
            slot_id = f"{core_id}:{'in' if side == 'input' else 'out'}:{local_idx}"
            output[slot_id] = str(row["commodity"]) if row.get("active") is True else "__unused__"
    if used != set(core_geometry):
        raise ValueError("witness core ports differ from official selected pose")

    input_counts, output_counts = Counter(generic_inputs.values()), Counter(generic_outputs.values())
    if (len(generic_inputs), input_counts["__unused__"], len(generic_outputs), output_counts["__unused__"]) != (14, 12, 52, 0):
        raise ValueError("generic accounting must be 2 active + 12 unused inputs and 52 active outputs")
    if generic_io_requirements is not None:
        expected_in = _requirements(generic_io_requirements.get("required_generic_inputs"), "generic.required_inputs")
        expected_out = _requirements(generic_io_requirements.get("required_generic_outputs"), "generic.required_outputs")
        if Counter({k: v for k, v in input_counts.items() if k != "__unused__"}) != expected_in or output_counts != expected_out:
            raise ValueError("generic projection disagrees with official requirements")

    pole_index: dict[tuple[int, int], list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for pose_idx, raw_pose in enumerate(_array(facility_pools.get("power_pole"), "facility_pools.power_pole")):
        pose = _obj(raw_pose, f"power_pole[{pose_idx}]")
        anchor = _obj(pose.get("anchor"), f"power_pole[{pose_idx}].anchor")
        pole_index[(_integer(anchor.get("x"), "pole.x"), _integer(anchor.get("y"), "pole.y"))].append((pose_idx, pose))
    pole_anchors: set[tuple[int, int]] = set()
    pole_names: set[str] = set()
    for idx, raw in enumerate(poles):
        pole = _obj(raw, f"facilities.power_poles[{idx}]")
        pole_name = _text(pole.get("id"), f"facilities.power_poles[{idx}].id")
        anchor = _xy(pole.get("anchor"), f"facilities.power_poles[{idx}].anchor")
        if pole_name in pole_names or anchor in pole_anchors or len(pole_index.get(anchor, ())) != 1:
            raise ValueError(f"power-pole id/anchor is duplicate or not uniquely official: {pole_name}/{anchor}")
        pole_names.add(pole_name)
        pole_anchors.add(anchor)
        pose_idx, pose = pole_index[anchor][0]
        pose_id = _text(pose.get("pose_id"), f"power pole {anchor}.pose_id")
        iid = f"pose_optional::power_pole::{pose_id}"
        if iid in solution:
            raise ValueError(f"duplicate synthesized power-pole ID {iid}")
        solution[iid] = {"instance_id": iid, "facility_type": "power_pole", "operation_type": "power_supply",
                         "pose_idx": pose_idx, "pose_id": pose_id, "anchor": {"x": anchor[0], "y": anchor[1]}}

    route_cells, route_audit = audit_route_components(witness.get("route_components"))
    active_cells = sorted({(sig[-3], sig[-2]) for sig in flat_active})
    hole_cells = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    if hole_cells & set(active_cells) or hole_cells & {tuple(cell) for cell in route_cells}:
        raise ValueError("hole intersects active terminal or route component")
    source_audit_dict = dict(source_audit or {})
    projection = {"pose_level_bindings": pose_projection, "generic_inputs": generic_inputs, "generic_outputs": generic_outputs,
                  "accounting": {"pose_level_unique_matches": len(pose_projection), "generic_input_slots": 14,
                                 "generic_input_active": 2, "generic_input_unused": 12, "generic_output_active": 52}}
    meta = {
        "witness_schema_version": "band22-witness/2", "schema_dispatch": "band22_v2_adapter", "path": witness_path,
        "sha256": witness_sha256, "loaded_instance_count": len(solution), "mandatory_instance_count": 266, "power_pole_count": len(poles),
        "ghost": {"w": width, "h": height, "anchor_x": x0, "anchor_y": y0, "area": 42, "min_side": 6,
                  "canonical_unfiltered_ghost_idx": x0 * (GRID_H - height + 1) + y0},
        "actual_source_hashes": dict(source_audit_dict.get("actual_hashes", {})), "source_audit": source_audit_dict,
        "witness_reported_source_hashes_untrusted": witness.get("source_hashes"), "binding_projection": projection,
        "active_terminal_cells": [list(cell) for cell in active_cells], "active_terminal_count": 628,
        "route_component_cells": route_cells, "route_schema_audit": route_audit,
        "boundary_statement": "The v2 projection is research provenance only. The official controller independently searches binding and routing; it does not replay witness-authored solutions verbatim.",
    }
    return solution, meta
def _source_snapshot(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for key, relative in SOURCE_PATHS.items():
        snap = read_stable_snapshot(project_root / relative)
        payloads[key] = loads_strict_json(snap.data.decode("utf-8"))
        hashes[key], sizes[key] = snap.sha256, snap.size_bytes
    return payloads, {"stable_snapshots": True, "actual_hashes": hashes, "sizes": sizes}
def load_band22_v2_witness(path: Path, *, project_root: Path = PROJECT_ROOT) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    witness = read_stable_snapshot(path, max_bytes=4 << 20)
    payload = _obj(loads_strict_json(witness.data.decode("utf-8")), "witness")
    sources, audit = _source_snapshot(Path(project_root))
    placements = _obj(sources["candidate_placements"], "candidate_placements")
    return adapt_band22_v2_payload(
        payload, facility_pools=_obj(placements.get("facility_pools"), "facility_pools"),
        mandatory_instances=_array(sources["mandatory_exact_instances"], "mandatory_instances"), canonical_rules=_obj(sources["canonical_rules"], "canonical_rules"),
        generic_io_requirements=_obj(sources["generic_io_requirements"], "generic_io_requirements"), source_audit=audit,
        witness_path=str(path), witness_sha256=witness.sha256)
def verify_against_session_pins(actual: Mapping[str, Any], session: Mapping[str, Any]) -> dict[str, Any]:
    checked: dict[str, str] = {}
    for key in SOURCE_PATHS:
        if not isinstance(actual.get(key), str) or actual[key] != session.get(key):
            raise ValueError(f"adapter/session source snapshot drift for {key}: {actual.get(key)!r} != {session.get(key)!r}")
        checked[key] = actual[key]
    return {"ok": True, "checked_hashes": checked}
