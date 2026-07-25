#!/usr/bin/env python3
"""Primary strict recomputation of the 24-to-19 endpoint budget.

This tool reads only the byte-locked strict instance and the pre-run geometry
authority.  It groups port-bearing faces by physical facility instance before
selecting the eight largest possible partial-contact mark counts.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


EXPECTED_STRICT_SHA = (
    "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
)
EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
EXPECTED_RESUME_SHA = (
    "24a896999cdea34e3fcde84a1f14be8516f321bbbe3654dd856b1116994b3ca8"
)
EXPECTED_RESUME_SIZE = 3_993
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
TARGET_WIDTH = 22
TARGET_HEIGHT = 54
OLD_UPPER = (1_188, 22)
NEW_CANDIDATE = (1_188, 18)


class RecomputeError(RuntimeError):
    """Raised for authority, strict-data, or arithmetic drift."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw: bytes, label: str) -> Any:
    def reject_constant(value: str) -> Any:
        raise RecomputeError(f"{label}: non-finite JSON {value!r}")

    def reject_float(value: str) -> Any:
        raise RecomputeError(f"{label}: floating-point JSON {value!r}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RecomputeError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecomputeError(f"{label}: invalid JSON: {exc}") from exc


def _read_same_fd(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        descriptor = os.open(path.absolute(), flags)
    except OSError as exc:
        raise RecomputeError(f"{label}: open failed: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RecomputeError(f"{label}: not regular")
        blocks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            blocks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise RecomputeError(f"{label}: changed during read")
    raw = b"".join(blocks)
    if len(raw) != before.st_size:
        raise RecomputeError(f"{label}: size changed during read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": _sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecomputeError(f"{label}: expected object")
    return value


def _array(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RecomputeError(f"{label}: expected array")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise RecomputeError(f"{label}: expected exact integer")
    return int(value)


def _one(values: set[Any], label: str) -> Any:
    if len(values) != 1:
        raise RecomputeError(f"{label}: expected one invariant value")
    return next(iter(values))


def _is_corner(mode: Mapping[str, Any], port: Mapping[str, Any]) -> bool:
    body = _mapping(mode.get("body"), "mode.body")
    cell = _mapping(port.get("body_cell"), "port.body_cell")
    x = _integer(cell.get("x"), "port.x")
    y = _integer(cell.get("y"), "port.y")
    width = _integer(body.get("width"), "body.width")
    height = _integer(body.get("height"), "body.height")
    return x in {0, width - 1} and y in {0, height - 1}


def _side_span(mode: Mapping[str, Any], port: Mapping[str, Any]) -> int:
    body = _mapping(mode.get("body"), "mode.body")
    direction = port.get("direction")
    if direction not in OPPOSITE:
        raise RecomputeError("unknown port direction")
    key = "width" if direction in {"N", "S"} else "height"
    return _integer(body.get(key), f"body.{key}")


def _need(group: Mapping[str, Any], plural: str) -> int:
    needs = _mapping(group.get("port_needs"), "group.port_needs")
    values = _mapping(needs.get(plural), f"group.{plural}")
    return sum(_integer(value, f"group.{plural}.{key}") for key, value in values.items())


def _body_area(template: Mapping[str, Any]) -> int:
    areas = {
        _integer(_mapping(mode, "mode").get("body", {}).get("width"), "width")
        * _integer(_mapping(mode, "mode").get("body", {}).get("height"), "height")
        for mode in _array(template.get("modes"), "template.modes")
    }
    return _integer(_one(areas, "body area"), "body area")


def _validate_geometry_authority(
    authority_path: Path,
    self_identity: dict[str, Any],
    strict_identity: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    raw, identity = _read_same_fd(authority_path, "geometry authority")
    payload = _strict_json(raw, "geometry authority")
    if not isinstance(payload, dict):
        raise RecomputeError("geometry authority must be an object")
    if (
        payload.get("schema_version")
        != "b1_sidewise_geometry_pre_run_authority_v1"
        or payload.get("status") != "GEOMETRY_PRE_RUN_AUTHORITY_PASS"
        or payload.get("head") != EXPECTED_HEAD
    ):
        raise RecomputeError("geometry authority status/head mismatch")
    resume = payload.get("resume_authority")
    if not isinstance(resume, dict) or (
        resume.get("size_bytes"),
        resume.get("sha256"),
    ) != (EXPECTED_RESUME_SIZE, EXPECTED_RESUME_SHA):
        raise RecomputeError("resume authority identity mismatch")
    pinned_strict = payload.get("strict_instance")
    if not isinstance(pinned_strict, dict) or any(
        pinned_strict.get(key) != strict_identity.get(key)
        for key in ("size_bytes", "sha256", "mode_octal")
    ):
        raise RecomputeError("strict instance differs from pre-run authority")
    tools = payload.get("tools")
    key = "primary_recomputation"
    if not isinstance(tools, dict) or not isinstance(tools.get(key), dict):
        raise RecomputeError("primary tool missing from pre-run authority")
    if any(
        tools[key].get(field) != self_identity.get(field)
        for field in ("size_bytes", "sha256", "mode_octal")
    ):
        raise RecomputeError("primary tool differs from pre-run authority")
    return payload, identity


def _face_profile(
    template: Mapping[str, Any],
    kind: str,
    active: int,
) -> tuple[int, int]:
    spans: set[int] = set()
    directions_per_mode: list[set[str]] = []
    corner_counts: set[int] = set()
    capacities: set[int] = set()
    for raw_mode in _array(template.get("modes"), "template.modes"):
        mode = _mapping(raw_mode, "mode")
        ports = [
            _mapping(port, "port")
            for port in _array(mode.get("ports"), "mode.ports")
            if _mapping(port, "port").get("kind") == kind
        ]
        if not ports:
            raise RecomputeError(f"missing {kind} face")
        directions = {str(port.get("direction")) for port in ports}
        if len(directions) != 1:
            raise RecomputeError(f"{kind} ports are not on one face")
        directions_per_mode.append(directions)
        spans.update(_side_span(mode, port) for port in ports)
        corner_counts.add(sum(_is_corner(mode, port) for port in ports))
        capacities.add(len(ports))
    if min(capacities) < active or corner_counts != {2}:
        raise RecomputeError(f"{kind} capacity/corner invariant drifted")
    span = _integer(_one(spans, f"{kind} side span"), "side span")
    marks = max(0, active - 2)
    if 2 * marks > span:
        raise RecomputeError("full-contact marked half-density failed")
    return span, marks


def _derive(problem: Mapping[str, Any]) -> dict[str, Any]:
    grid = _mapping(problem.get("grid"), "grid")
    if (
        _integer(grid.get("width"), "grid.width"),
        _integer(grid.get("height"), "grid.height"),
    ) != (70, 70):
        raise RecomputeError("grid drifted")
    templates = _mapping(problem.get("facility_templates"), "templates")
    required_raw = _array(problem.get("required_instances"), "required")
    required: dict[str, Mapping[str, Any]] = {}
    template_counts: Counter[str] = Counter()
    for raw in required_raw:
        item = _mapping(raw, "required item")
        item_id = item.get("id")
        template_name = item.get("template")
        if (
            type(item_id) is not str
            or item_id in required
            or type(template_name) is not str
            or template_name not in templates
        ):
            raise RecomputeError("required instance identity/template drifted")
        required[item_id] = item
        template_counts[template_name] += 1
    groups = [
        _mapping(group, "operation group")
        for group in _array(problem.get("operation_groups"), "groups")
    ]

    entity_maxima: list[int] = []
    manufacturing_marks = 0
    ordinary_classes: Counter[tuple[int, int]] = Counter()
    manufacturing_instances = 0
    manufacturing_inputs = 0
    manufacturing_outputs = 0
    face_profiles: Counter[tuple[int, int]] = Counter()
    for group in groups:
        group_id = group.get("id")
        template_name = group.get("template")
        count = _integer(group.get("count"), f"{group_id}.count")
        ids = list(_array(group.get("instance_ids"), f"{group_id}.ids"))
        if len(ids) != count or len(set(ids)) != count:
            raise RecomputeError(f"{group_id}: instance list mismatch")
        for item_id in ids:
            item = required.get(str(item_id))
            if (
                item is None
                or item.get("operation") != group_id
                or item.get("template") != template_name
            ):
                raise RecomputeError(f"{group_id}: required-instance join failed")
        template = _mapping(templates.get(str(template_name)), "group template")
        active_input = _need(group, "inputs")
        active_output = _need(group, "outputs")
        input_span, input_marks = _face_profile(
            template, "input", active_input
        )
        output_span, output_marks = _face_profile(
            template, "output", active_output
        )
        if input_span != output_span:
            raise RecomputeError("opposite manufacturing side spans differ")
        for raw_mode in _array(template.get("modes"), "manufacturing modes"):
            mode = _mapping(raw_mode, "manufacturing mode")
            ins = {
                str(_mapping(port, "port").get("direction"))
                for port in _array(mode.get("ports"), "ports")
                if _mapping(port, "port").get("kind") == "input"
            }
            outs = {
                str(_mapping(port, "port").get("direction"))
                for port in _array(mode.get("ports"), "ports")
                if _mapping(port, "port").get("kind") == "output"
            }
            if (
                len(ins) != 1
                or len(outs) != 1
                or OPPOSITE[next(iter(ins))] != next(iter(outs))
            ):
                raise RecomputeError("manufacturing faces are not opposite")
        ordinary_classes[(input_span, max(active_input, active_output))] += count
        face_profiles[(input_span, input_marks)] += count
        face_profiles[(output_span, output_marks)] += count
        manufacturing_marks += count * (input_marks + output_marks)
        entity_maxima.extend([max(input_marks, output_marks)] * count)
        manufacturing_instances += count
        manufacturing_inputs += count * active_input
        manufacturing_outputs += count * active_output

    boundary_count = template_counts["boundary_storage_port"]
    boundary = _mapping(templates.get("boundary_storage_port"), "boundary")
    boundary_profiles = {
        (
            _side_span(
                _mapping(mode, "boundary mode"),
                _mapping(
                    _array(_mapping(mode, "boundary mode").get("ports"), "ports")[0],
                    "boundary port",
                ),
            ),
            _is_corner(
                _mapping(mode, "boundary mode"),
                _mapping(
                    _array(_mapping(mode, "boundary mode").get("ports"), "ports")[0],
                    "boundary port",
                ),
            ),
        )
        for mode in _array(boundary.get("modes"), "boundary modes")
    }
    if boundary_profiles != {(3, False)} or boundary_count != 46:
        raise RecomputeError("boundary raw-provider geometry drifted")
    ordinary_classes[(3, 1)] += boundary_count
    face_profiles[(3, 1)] += boundary_count
    entity_maxima.extend([1] * boundary_count)

    core_count = template_counts["protocol_core"]
    core = _mapping(templates.get("protocol_core"), "protocol core")
    core_faces: set[tuple[int, int, tuple[int, ...]]] = set()
    core_output_slots: set[int] = set()
    for raw_mode in _array(core.get("modes"), "core modes"):
        mode = _mapping(raw_mode, "core mode")
        by_direction: dict[str, list[Mapping[str, Any]]] = {}
        for raw_port in _array(mode.get("ports"), "core ports"):
            port = _mapping(raw_port, "core port")
            if port.get("kind") == "output":
                by_direction.setdefault(str(port.get("direction")), []).append(port)
        if sorted(len(ports) for ports in by_direction.values()) != [3, 3]:
            raise RecomputeError("core output faces are not 3+3")
        core_output_slots.add(sum(len(ports) for ports in by_direction.values()))
        for ports in by_direction.values():
            if any(_is_corner(mode, port) for port in ports):
                raise RecomputeError("core raw output at body corner")
            offsets = tuple(
                sorted(
                    _integer(
                        _mapping(port.get("body_cell"), "core cell").get(
                            "x"
                            if str(port.get("direction")) in {"N", "S"}
                            else "y"
                        ),
                        "core tangent offset",
                    )
                    for port in ports
                )
            )
            core_faces.add((_side_span(mode, ports[0]), len(ports), offsets))
    if core_count != 1 or core_output_slots != {6} or core_faces != {(9, 3, (1, 4, 7))}:
        raise RecomputeError("protocol-core entity/face identity drifted")
    face_profiles[(9, 3)] += 2
    entity_maxima.append(3)

    generic = _mapping(problem.get("generic_requirements"), "generic")
    raw_demand = sum(
        _integer(value, f"raw demand {key}")
        for key, value in _mapping(
            generic.get("raw_outputs"), "raw outputs"
        ).items()
    )
    final_inputs = sum(
        _integer(value, f"final input {key}")
        for key, value in _mapping(
            generic.get("final_inputs"), "final inputs"
        ).items()
    )
    provider_slots = {
        "boundary_storage_port": boundary_count,
        "protocol_core": _one(core_output_slots, "core slots"),
    }
    if (
        list(_array(generic.get("raw_output_providers"), "raw providers"))
        != ["boundary_storage_port", "protocol_core"]
        or sum(provider_slots.values()) != raw_demand
        or raw_demand != 52
        or final_inputs != 2
    ):
        raise RecomputeError("generic terminal/provider accounting drifted")

    total_marks = manufacturing_marks + raw_demand
    active_terminals = (
        manufacturing_inputs + manufacturing_outputs + raw_demand + final_inputs
    )
    entity_census = Counter(entity_maxima)
    top_eight = sorted(entity_maxima, reverse=True)[:8]
    if (
        manufacturing_instances,
        manufacturing_marks,
        total_marks,
        active_terminals,
        entity_census,
        top_eight,
        sum(top_eight),
    ) != (
        219,
        58,
        110,
        628,
        Counter({0: 170, 1: 89, 2: 3, 3: 4}),
        [3, 3, 3, 3, 2, 2, 2, 1],
        19,
    ):
        raise RecomputeError("entity-max marked census drifted")
    if any(2 * marks > span for span, marks in face_profiles):
        raise RecomputeError("marked full-contact inequality drifted")

    expected_ordinary = Counter(
        {
            (3, 1): 155,
            (3, 2): 12,
            (3, 3): 11,
            (5, 1): 32,
            (5, 2): 17,
            (6, 3): 32,
            (6, 4): 3,
            (6, 5): 3,
        }
    )
    ordinary_excess = sum(
        count * max(0, 2 * active - span)
        for (span, active), count in ordinary_classes.items()
    )
    ordinary_endpoint = max(
        active - max(0, 2 * active - span)
        for span, active in ordinary_classes
    )
    if (
        ordinary_classes != expected_ordinary
        or ordinary_excess != 63
        or ordinary_endpoint != 3
    ):
        raise RecomputeError("ordinary membrane reconstruction drifted")

    partial_checks = 0
    for span, marks in face_profiles:
        for overlap in range(1, span):
            for exposed in range(0, min(marks, overlap) + 1):
                if 2 * exposed > overlap + marks:
                    raise RecomputeError("partial-contact inequality failed")
                partial_checks += 1

    side_sum = TARGET_WIDTH + TARGET_HEIGHT
    perimeter = 2 * side_sum
    marked_inside = (perimeter + sum(top_eight)) // 2
    ordinary_inside = side_sum + 48
    combined_inside = marked_inside + ordinary_inside
    outside_incidence = active_terminals + total_marks - combined_inside
    outside_cells = -(-outside_incidence // 4)
    used_cells = TARGET_WIDTH * TARGET_HEIGHT + outside_cells
    if (
        side_sum,
        perimeter,
        marked_inside,
        ordinary_inside,
        combined_inside,
        outside_incidence,
        outside_cells,
        used_cells,
    ) != (76, 152, 85, 124, 209, 529, 133, 1321):
        raise RecomputeError("SMM-209 arithmetic drifted")

    dimensions = {
        (width, height)
        for width in range(6, 71)
        for height in range(6, 71)
    }
    old_band = {
        pair
        for pair in dimensions
        if (pair[0] * pair[1], min(pair)) > OLD_UPPER
    }
    new_band = {
        pair
        for pair in dimensions
        if (pair[0] * pair[1], min(pair)) > NEW_CANDIDATE
    }
    ceiling = {(22, 54), (54, 22)}
    if (
        len(old_band),
        len(new_band),
        new_band - old_band,
        old_band & ceiling,
    ) != (2_084, 2_086, ceiling, set()):
        raise RecomputeError("band composition drifted")

    body_area = sum(
        _body_area(_mapping(templates[str(item["template"])], "required template"))
        for item in required.values()
    )
    if (
        len(required),
        body_area,
        template_counts["protocol_core"],
    ) != (266, 3_544, 1):
        raise RecomputeError("required body census drifted")

    return {
        "strict_counts": {
            "required_instances": len(required),
            "manufacturing_instances": manufacturing_instances,
            "required_body_cells": body_area,
            "active_terminals": active_terminals,
            "manufacturing_marks": manufacturing_marks,
            "raw_noncorner_marks": raw_demand,
            "total_marks": total_marks,
            "final_inputs_not_marked": final_inputs,
        },
        "ordinary_membrane": {
            "class_table": [
                {
                    "side_span": span,
                    "active_side_cap": active,
                    "multiplicity": count,
                }
                for (span, active), count in sorted(ordinary_classes.items())
            ],
            "full_contact_excess": ordinary_excess,
            "directed_endpoints": 8,
            "maximum_endpoint_extra": ordinary_endpoint,
            "inside_bound_at_side_sum_76": ordinary_inside,
        },
        "marked_entity_budget": {
            "entity_census": {
                str(key): entity_census[key] for key in sorted(entity_census)
            },
            "core_is_one_entity": True,
            "core_output_faces": 2,
            "core_marks_per_contact_face": 3,
            "top_eight": top_eight,
            "top_eight_sum": sum(top_eight),
            "full_face_profile_count": sum(face_profiles.values()),
            "partial_arithmetic_checks": partial_checks,
            "inequality": "2*M_in <= 2*(w+h) + 19",
            "inside_bound_at_side_sum_76": marked_inside,
        },
        "ceiling_exclusion": {
            "dimensions": [[22, 54], [54, 22]],
            "combined_inside_cap": combined_inside,
            "outside_incidence_floor": outside_incidence,
            "outside_access_cell_floor": outside_cells,
            "rectangle_plus_outside_cells": used_cells,
            "available_cell_cap": 1_320,
            "excluded": used_cells > 1_320,
        },
        "band_composition": {
            "old_upper": list(OLD_UPPER),
            "candidate_upper": list(NEW_CANDIDATE),
            "old_band_count": len(old_band),
            "candidate_band_count": len(new_band),
            "new_ceiling_orientations": [
                list(pair) for pair in sorted(new_band - old_band)
            ],
            "union_exact": old_band | ceiling == new_band,
        },
    }


def _write_exclusive(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(
        os, "O_NOFOLLOW", 0
    )
    descriptor = os.open(path, flags, 0o644)
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(descriptor, raw[offset:])
            if count <= 0:
                raise RecomputeError("short output write")
            offset += count
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--geometry-authority", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        instance_raw, instance_identity = _read_same_fd(
            args.instance,
            "strict instance",
        )
        if instance_identity["sha256"] != EXPECTED_STRICT_SHA:
            raise RecomputeError("strict instance SHA-256 mismatch")
        self_raw, self_identity = _read_same_fd(Path(__file__), "primary tool")
        del self_raw
        _, authority_identity = _validate_geometry_authority(
            args.geometry_authority,
            self_identity,
            instance_identity,
        )
        problem = _mapping(
            _strict_json(instance_raw, "strict instance"),
            "strict instance",
        )
        results = _derive(problem)
        report = {
            "schema_version": "b1_sidewise_primary_recomputation_v1",
            "status": "PASS",
            "tool": self_identity,
            "geometry_authority": authority_identity,
            "strict_instance": instance_identity,
            "results": results,
            "claim_boundary": {
                "geometry_recomputation_only": True,
                "pb_or_formal_proof": False,
                "upper_updated": False,
                "witness_or_attainability": False,
                "production_certified": False,
            },
        }
        raw = (
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n"
        ).encode()
        if args.output.exists() or args.output.is_symlink():
            raise RecomputeError("output already exists")
        if (
            not args.output.parent.is_dir()
            or args.output.parent.is_symlink()
        ):
            raise RecomputeError("output parent must be a real directory")
        _write_exclusive(args.output, raw)
    except (OSError, RecomputeError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "size_bytes": len(raw),
                "sha256": _sha(raw),
                "combined_inside_cap": results["ceiling_exclusion"][
                    "combined_inside_cap"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
