#!/usr/bin/env python3
"""Independent flat-instance check of the sidewise entity endpoint budget.

Unlike the primary recomputation, this checker first joins every required
manufacturing instance to its operation group, derives a record per physical
entity, and only then sorts entity maxima.  It imports neither the primary
tool nor the future encoder/gates.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


STRICT_SHA = (
    "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
)
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
RESUME_ID = (3_993, "24a896999cdea34e3fcde84a1f14be8516f321bbbe3654dd856b1116994b3ca8")


class IndependentError(RuntimeError):
    """Raised when an independent authority or derivation check fails."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_bytes(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        fd = os.open(path.absolute(), flags)
    except OSError as exc:
        raise IndependentError(f"{label}: open failed: {exc}") from exc
    try:
        first = os.fstat(fd)
        if not stat.S_ISREG(first.st_mode):
            raise IndependentError(f"{label}: not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        last = os.fstat(fd)
    finally:
        os.close(fd)
    identity_tuple = (
        first.st_dev,
        first.st_ino,
        first.st_mode,
        first.st_size,
        first.st_mtime_ns,
        first.st_ctime_ns,
    )
    final_tuple = (
        last.st_dev,
        last.st_ino,
        last.st_mode,
        last.st_size,
        last.st_mtime_ns,
        last.st_ctime_ns,
    )
    if identity_tuple != final_tuple:
        raise IndependentError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != first.st_size:
        raise IndependentError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": digest(raw),
        "mode_octal": f"{stat.S_IMODE(first.st_mode):04o}",
    }


def decode(raw: bytes, label: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise IndependentError(f"{label}: duplicate key {key!r}")
            out[key] = value
        return out

    def no_float(value: str) -> Any:
        raise IndependentError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_float=no_float,
            parse_constant=no_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentError(f"{label}: bad JSON: {exc}") from exc


def exact_int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise IndependentError(f"{label}: not an exact integer")
    return value


def object_(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IndependentError(f"{label}: not an object")
    return value


def list_(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise IndependentError(f"{label}: not an array")
    return value


def port_is_corner(mode: dict[str, Any], port: dict[str, Any]) -> bool:
    body = object_(mode.get("body"), "body")
    cell = object_(port.get("body_cell"), "body cell")
    x, y = exact_int(cell.get("x"), "x"), exact_int(cell.get("y"), "y")
    width = exact_int(body.get("width"), "width")
    height = exact_int(body.get("height"), "height")
    return x in (0, width - 1) and y in (0, height - 1)


def tangent_span(mode: dict[str, Any], port: dict[str, Any]) -> int:
    body = object_(mode.get("body"), "body")
    direction = port.get("direction")
    if direction in ("N", "S"):
        return exact_int(body.get("width"), "body width")
    if direction in ("E", "W"):
        return exact_int(body.get("height"), "body height")
    raise IndependentError("invalid direction")


def needs(group: dict[str, Any], plural: str) -> int:
    port_needs = object_(group.get("port_needs"), "port needs")
    demand = object_(port_needs.get(plural), plural)
    return sum(exact_int(value, f"{plural}.{name}") for name, value in demand.items())


def inspect_face(
    template: dict[str, Any],
    kind: str,
    active: int,
) -> dict[str, Any]:
    spans: set[int] = set()
    physical_capacities: set[int] = set()
    corners: set[int] = set()
    mode_directions: list[str] = []
    for raw_mode in list_(template.get("modes"), "modes"):
        mode = object_(raw_mode, "mode")
        ports = [
            object_(raw_port, "port")
            for raw_port in list_(mode.get("ports"), "ports")
            if object_(raw_port, "port").get("kind") == kind
        ]
        directions = {port.get("direction") for port in ports}
        if len(directions) != 1:
            raise IndependentError(f"{kind}: not a single face")
        direction = next(iter(directions))
        if type(direction) is not str:
            raise IndependentError(f"{kind}: bad direction")
        mode_directions.append(direction)
        physical_capacities.add(len(ports))
        corners.add(sum(port_is_corner(mode, port) for port in ports))
        spans.update(tangent_span(mode, port) for port in ports)
    if len(spans) != 1 or min(physical_capacities) < active or corners != {2}:
        raise IndependentError(f"{kind}: face invariant drift")
    return {
        "span": next(iter(spans)),
        "active": active,
        "marks": max(0, active - 2),
        "directions": mode_directions,
    }


def check_authority(
    authority_path: Path,
    tool_identity: dict[str, Any],
    strict_identity: dict[str, Any],
) -> dict[str, Any]:
    raw, authority_identity = load_bytes(authority_path, "geometry authority")
    authority = decode(raw, "geometry authority")
    if not isinstance(authority, dict):
        raise IndependentError("geometry authority not an object")
    if (
        authority.get("schema_version")
        != "b1_sidewise_geometry_pre_run_authority_v1"
        or authority.get("status") != "GEOMETRY_PRE_RUN_AUTHORITY_PASS"
        or authority.get("head") != HEAD
    ):
        raise IndependentError("geometry authority status/head mismatch")
    resume = authority.get("resume_authority")
    if not isinstance(resume, dict) or (
        resume.get("size_bytes"),
        resume.get("sha256"),
    ) != RESUME_ID:
        raise IndependentError("resume authority mismatch")
    strict = authority.get("strict_instance")
    if not isinstance(strict, dict) or any(
        strict.get(field) != strict_identity.get(field)
        for field in ("size_bytes", "sha256", "mode_octal")
    ):
        raise IndependentError("strict authority mismatch")
    tools = authority.get("tools")
    pinned = (
        tools.get("independent_recomputation")
        if isinstance(tools, dict)
        else None
    )
    if not isinstance(pinned, dict) or any(
        pinned.get(field) != tool_identity.get(field)
        for field in ("size_bytes", "sha256", "mode_octal")
    ):
        raise IndependentError("independent tool authority mismatch")
    return authority_identity


def derive_flat(data: dict[str, Any]) -> dict[str, Any]:
    grid = object_(data.get("grid"), "grid")
    if (
        exact_int(grid.get("width"), "width"),
        exact_int(grid.get("height"), "height"),
    ) != (70, 70):
        raise IndependentError("grid mismatch")
    templates = object_(data.get("facility_templates"), "templates")
    required_list = [
        object_(item, "required instance")
        for item in list_(data.get("required_instances"), "required")
    ]
    by_id: dict[str, dict[str, Any]] = {}
    for item in required_list:
        item_id = item.get("id")
        if type(item_id) is not str or item_id in by_id:
            raise IndependentError("bad required id")
        by_id[item_id] = item
    groups = [
        object_(group, "group")
        for group in list_(data.get("operation_groups"), "groups")
    ]
    groups_by_id = {str(group.get("id")): group for group in groups}
    if len(groups_by_id) != len(groups):
        raise IndependentError("duplicate group id")

    # The flat table is keyed by required instance id, not by a grouped count.
    entity_rows: list[dict[str, Any]] = []
    ordinary: Counter[tuple[int, int]] = Counter()
    all_face_profiles: Counter[tuple[int, int]] = Counter()
    manufacturing_marks = inputs = outputs = 0
    for item_id, item in by_id.items():
        operation = item.get("operation")
        if operation is None:
            continue
        group = groups_by_id.get(str(operation))
        if group is None or item_id not in list_(
            group.get("instance_ids"), "instance ids"
        ):
            raise IndependentError("flat operation-instance join mismatch")
        template_name = item.get("template")
        if template_name != group.get("template"):
            raise IndependentError("flat template join mismatch")
        template = object_(templates.get(str(template_name)), "template")
        input_need = needs(group, "inputs")
        output_need = needs(group, "outputs")
        in_face = inspect_face(template, "input", input_need)
        out_face = inspect_face(template, "output", output_need)
        opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
        if any(
            opposite[left] != right
            for left, right in zip(
                in_face["directions"], out_face["directions"]
            )
        ):
            raise IndependentError("input/output modes are not opposite")
        if in_face["span"] != out_face["span"]:
            raise IndependentError("input/output tangent spans differ")
        max_marks = max(in_face["marks"], out_face["marks"])
        entity_rows.append(
            {
                "id": item_id,
                "operation": operation,
                "input_marks": in_face["marks"],
                "output_marks": out_face["marks"],
                "entity_max_marks": max_marks,
            }
        )
        ordinary[(in_face["span"], max(input_need, output_need))] += 1
        all_face_profiles[(in_face["span"], in_face["marks"])] += 1
        all_face_profiles[(out_face["span"], out_face["marks"])] += 1
        manufacturing_marks += in_face["marks"] + out_face["marks"]
        inputs += input_need
        outputs += output_need

    boundary_entities = [
        item
        for item in required_list
        if item.get("template") == "boundary_storage_port"
    ]
    core_entities = [
        item for item in required_list if item.get("template") == "protocol_core"
    ]
    if len(boundary_entities) != 46 or len(core_entities) != 1:
        raise IndependentError("raw provider entity count mismatch")
    boundary = object_(templates.get("boundary_storage_port"), "boundary")
    boundary_shape: set[tuple[int, bool]] = set()
    for raw_mode in list_(boundary.get("modes"), "boundary modes"):
        mode = object_(raw_mode, "boundary mode")
        ports = [object_(p, "boundary port") for p in list_(mode.get("ports"), "ports")]
        if len(ports) != 1 or ports[0].get("kind") != "output":
            raise IndependentError("boundary output shape mismatch")
        boundary_shape.add(
            (tangent_span(mode, ports[0]), port_is_corner(mode, ports[0]))
        )
    if boundary_shape != {(3, False)}:
        raise IndependentError("boundary port not centered on span three")
    ordinary[(3, 1)] += 46
    all_face_profiles[(3, 1)] += 46
    entity_rows.extend(
        {
            "id": str(item["id"]),
            "operation": None,
            "input_marks": 0,
            "output_marks": 1,
            "entity_max_marks": 1,
        }
        for item in boundary_entities
    )

    core = object_(templates.get("protocol_core"), "core")
    core_mode_faces: list[list[tuple[str, int, int, tuple[int, ...]]]] = []
    for raw_mode in list_(core.get("modes"), "core modes"):
        mode = object_(raw_mode, "core mode")
        faces: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw_port in list_(mode.get("ports"), "core ports"):
            port = object_(raw_port, "core port")
            if port.get("kind") == "output":
                faces[str(port.get("direction"))].append(port)
        row: list[tuple[str, int, int, tuple[int, ...]]] = []
        for direction, ports in sorted(faces.items()):
            tangent = "x" if direction in ("N", "S") else "y"
            offsets = tuple(
                sorted(
                    exact_int(
                        object_(port.get("body_cell"), "core body cell").get(
                            tangent
                        ),
                        "core offset",
                    )
                    for port in ports
                )
            )
            if any(port_is_corner(mode, port) for port in ports):
                raise IndependentError("core output is a corner")
            row.append(
                (direction, tangent_span(mode, ports[0]), len(ports), offsets)
            )
        core_mode_faces.append(row)
    if any(
        sorted((span, count, offsets) for _, span, count, offsets in row)
        != [(9, 3, (1, 4, 7)), (9, 3, (1, 4, 7))]
        for row in core_mode_faces
    ):
        raise IndependentError("core 3+3 face geometry mismatch")
    all_face_profiles[(9, 3)] += 2
    entity_rows.append(
        {
            "id": str(core_entities[0]["id"]),
            "operation": None,
            "input_marks": 0,
            "output_marks": 3,
            "entity_max_marks": 3,
        }
    )

    generic = object_(data.get("generic_requirements"), "generic")
    raw_demand = sum(
        exact_int(value, f"raw {name}")
        for name, value in object_(
            generic.get("raw_outputs"), "raw outputs"
        ).items()
    )
    final_demand = sum(
        exact_int(value, f"final {name}")
        for name, value in object_(
            generic.get("final_inputs"), "final inputs"
        ).items()
    )
    if (
        raw_demand,
        final_demand,
        list_(generic.get("raw_output_providers"), "raw providers"),
    ) != (52, 2, ["boundary_storage_port", "protocol_core"]):
        raise IndependentError("generic demand/provider mismatch")

    maxima = [exact_int(row["entity_max_marks"], "entity max") for row in entity_rows]
    top = sorted(maxima, reverse=True)[:8]
    census = Counter(maxima)
    total_marks = manufacturing_marks + 46 + 6
    terminals = inputs + outputs + raw_demand + final_demand
    if (
        len(entity_rows),
        census,
        top,
        sum(top),
        manufacturing_marks,
        total_marks,
        terminals,
    ) != (
        266,
        Counter({0: 170, 1: 89, 2: 3, 3: 4}),
        [3, 3, 3, 3, 2, 2, 2, 1],
        19,
        58,
        110,
        628,
    ):
        raise IndependentError("flat entity/top-eight census mismatch")
    if any(2 * marks > span for span, marks in all_face_profiles):
        raise IndependentError("full-contact mark density mismatch")

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
    excess = sum(
        count * max(0, 2 * active - span)
        for (span, active), count in ordinary.items()
    )
    endpoint = max(
        active - max(0, 2 * active - span)
        for span, active in ordinary
    )
    if ordinary != expected_ordinary or (excess, endpoint) != (63, 3):
        raise IndependentError("ordinary membrane mismatch")

    # Enumerate all integer overlap/exposed pairs, independent of actual offsets.
    pair_count = 0
    worst_slack = None
    for span, marked in all_face_profiles:
        for overlap in range(1, span):
            for exposed in range(min(marked, overlap) + 1):
                slack = overlap + marked - 2 * exposed
                if slack < 0:
                    raise IndependentError("partial contact arithmetic counterexample")
                worst_slack = slack if worst_slack is None else min(worst_slack, slack)
                pair_count += 1

    perimeter = 2 * (22 + 54)
    m_in = (perimeter + sum(top)) // 2
    t_in = 22 + 54 + 48
    combined = t_in + m_in
    outside_weight = 628 + 110 - combined
    distinct_cells = (outside_weight + 3) // 4
    if (m_in, t_in, combined, outside_weight, distinct_cells) != (
        85,
        124,
        209,
        529,
        133,
    ):
        raise IndependentError("ceiling arithmetic mismatch")

    universe = [
        (width, height)
        for width in range(6, 71)
        for height in range(6, 71)
    ]
    old = {
        pair
        for pair in universe
        if (pair[0] * pair[1], min(pair[0], pair[1])) > (1188, 22)
    }
    candidate = {
        pair
        for pair in universe
        if (pair[0] * pair[1], min(pair[0], pair[1])) > (1188, 18)
    }
    delta = candidate.difference(old)
    if len(old) != 2084 or len(candidate) != 2086 or delta != {
        (22, 54),
        (54, 22),
    }:
        raise IndependentError("independent band partition mismatch")

    operations = Counter(
        (row["entity_max_marks"], row["operation"])
        for row in entity_rows
        if row["operation"] is not None
    )
    return {
        "flat_entity_count": len(entity_rows),
        "manufacturing_entity_count": sum(
            row["operation"] is not None for row in entity_rows
        ),
        "entity_max_census": {
            str(key): census[key] for key in sorted(census)
        },
        "top_eight": top,
        "top_eight_sum": sum(top),
        "manufacturing_marks": manufacturing_marks,
        "raw_marks": 52,
        "total_marks": total_marks,
        "active_terminals": terminals,
        "final_inputs_not_marked": final_demand,
        "core_entity_rows": sum(row["id"] == core_entities[0]["id"] for row in entity_rows),
        "partial_pair_checks": pair_count,
        "minimum_partial_slack": worst_slack,
        "ordinary_full_excess": excess,
        "ordinary_endpoint_extra": endpoint,
        "marked_inside_cap": m_in,
        "ordinary_inside_cap": t_in,
        "combined_inside_cap": combined,
        "outside_incidence_floor": outside_weight,
        "outside_cell_floor": distinct_cells,
        "rectangle_plus_outside_cells": 1188 + distinct_cells,
        "band_counts": {
            "old": len(old),
            "candidate": len(candidate),
            "delta": [list(pair) for pair in sorted(delta)],
        },
        "operation_entity_maxima": [
            {
                "entity_max_marks": key[0],
                "operation": key[1],
                "count": count,
            }
            for key, count in sorted(
                operations.items(),
                key=lambda item: (item[0][0], str(item[0][1])),
            )
        ],
    }


def write_once(path: Path, raw: bytes) -> None:
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(fd, raw[offset:])
            if count <= 0:
                raise IndependentError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--geometry-authority", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        strict_raw, strict_identity = load_bytes(args.instance, "strict instance")
        if strict_identity["sha256"] != STRICT_SHA:
            raise IndependentError("strict SHA-256 mismatch")
        _, tool_identity = load_bytes(Path(__file__), "independent tool")
        authority_identity = check_authority(
            args.geometry_authority,
            tool_identity,
            strict_identity,
        )
        results = derive_flat(
            object_(decode(strict_raw, "strict instance"), "strict instance")
        )
        report = {
            "schema_version": "b1_sidewise_independent_recomputation_v1",
            "status": "PASS",
            "tool": tool_identity,
            "geometry_authority": authority_identity,
            "strict_instance": strict_identity,
            "results": results,
            "claim_boundary": {
                "independent_geometry_recomputation_only": True,
                "pb_or_formal_proof": False,
                "upper_updated": False,
                "production_certified": False,
            },
        }
        raw = (
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n"
        ).encode()
        if args.output.exists() or args.output.is_symlink():
            raise IndependentError("output exists")
        if args.output.parent.is_symlink() or not args.output.parent.is_dir():
            raise IndependentError("output parent is not a real directory")
        write_once(args.output, raw)
    except (OSError, IndependentError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "size_bytes": len(raw),
                "sha256": digest(raw),
                "combined_inside_cap": results["combined_inside_cap"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
