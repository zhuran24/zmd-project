#!/usr/bin/env python3
"""Independent translation/composition gate for the two-selector OPB."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any


HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
AUTHORITY_SCHEMA = "b1_sidewise_pb_pre_run_authority_v1"
SEMANTICS = (
    "given_geometry_admission_no_body_empty_22x54_or_54x22_"
    "satisfies_smm209_cell_cap_v1"
)
HEADER = re.compile(
    r"^\* #variable= (\d+) #constraint= (\d+) #equal= (\d+) intsize= (\d+)$"
)
CONSTRAINT = re.compile(r"^(.*?) (>=|=) (-?\d+) ;$")
TERM = re.compile(r"([+-]\d+) x([1-9]\d*)")


class TranslationError(RuntimeError):
    """Raised when translation, authority, or corpus replay fails."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def snapshot(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    fd = os.open(
        path.absolute(),
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise TranslationError(f"{label}: not regular")
        parts: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            parts.append(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise TranslationError(f"{label}: changed during read")
    raw = b"".join(parts)
    if len(raw) != before.st_size:
        raise TranslationError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def parse_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TranslationError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise TranslationError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TranslationError(f"{label}: malformed JSON: {exc}") from exc


def require(ok: bool, message: str) -> None:
    if not ok:
        raise TranslationError(message)


def identity_match(
    actual: dict[str, Any],
    expected: dict[str, Any],
    label: str,
) -> None:
    require(
        all(
            actual.get(field) == expected.get(field)
            for field in ("size_bytes", "sha256", "mode_octal")
        ),
        f"{label}: byte identity drifted",
    )


def integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise TranslationError(f"{label}: expected exact integer")
    return value


def object_(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TranslationError(f"{label}: expected object")
    return value


def list_(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TranslationError(f"{label}: expected array")
    return value


def side_span(mode: dict[str, Any], port: dict[str, Any]) -> int:
    body = object_(mode.get("body"), "body")
    direction = port.get("direction")
    key = "width" if direction in ("N", "S") else "height"
    if direction not in ("N", "S", "E", "W"):
        raise TranslationError("bad direction")
    return integer(body.get(key), key)


def is_corner(mode: dict[str, Any], port: dict[str, Any]) -> bool:
    body = object_(mode.get("body"), "body")
    cell = object_(port.get("body_cell"), "body cell")
    x, y = integer(cell.get("x"), "x"), integer(cell.get("y"), "y")
    width = integer(body.get("width"), "width")
    height = integer(body.get("height"), "height")
    return x in (0, width - 1) and y in (0, height - 1)


def need(group: dict[str, Any], plural: str) -> int:
    demands = object_(
        object_(group.get("port_needs"), "port needs").get(plural),
        plural,
    )
    return sum(integer(value, f"{plural}.{key}") for key, value in demands.items())


def invariant_face(
    template: dict[str, Any],
    kind: str,
    active: int,
) -> tuple[int, int]:
    spans: set[int] = set()
    corners: set[int] = set()
    capacities: set[int] = set()
    for raw_mode in list_(template.get("modes"), "modes"):
        mode = object_(raw_mode, "mode")
        ports = [
            object_(raw_port, "port")
            for raw_port in list_(mode.get("ports"), "ports")
            if object_(raw_port, "port").get("kind") == kind
        ]
        require(
            len({port.get("direction") for port in ports}) == 1,
            f"{kind} is not one face",
        )
        spans.update(side_span(mode, port) for port in ports)
        corners.add(sum(is_corner(mode, port) for port in ports))
        capacities.add(len(ports))
    require(
        len(spans) == 1 and corners == {2} and min(capacities) >= active,
        f"{kind} face invariant drifted",
    )
    return next(iter(spans)), max(0, active - 2)


def derive_strict(problem: dict[str, Any]) -> dict[str, Any]:
    templates = object_(problem.get("facility_templates"), "templates")
    required = [
        object_(row, "required")
        for row in list_(problem.get("required_instances"), "required")
    ]
    required_ids = {str(row.get("id")): row for row in required}
    require(len(required_ids) == len(required) == 266, "required ids drifted")
    template_counts = Counter(str(row.get("template")) for row in required)
    groups = [
        object_(row, "group")
        for row in list_(problem.get("operation_groups"), "groups")
    ]
    entity_maxima: list[int] = []
    manufacturing_marks = inputs = outputs = instances = 0
    ordinary: Counter[tuple[int, int]] = Counter()
    for group in groups:
        count = integer(group.get("count"), "group count")
        ids = list_(group.get("instance_ids"), "instance ids")
        require(len(ids) == count == len(set(ids)), "group ids drifted")
        for item_id in ids:
            row = required_ids.get(str(item_id))
            require(
                row is not None
                and row.get("operation") == group.get("id")
                and row.get("template") == group.get("template"),
                "group-required join failed",
            )
        template = object_(templates.get(str(group.get("template"))), "template")
        active_in, active_out = need(group, "inputs"), need(group, "outputs")
        span_in, marks_in = invariant_face(template, "input", active_in)
        span_out, marks_out = invariant_face(template, "output", active_out)
        require(span_in == span_out, "manufacturing span drifted")
        ordinary[(span_in, max(active_in, active_out))] += count
        entity_maxima.extend([max(marks_in, marks_out)] * count)
        manufacturing_marks += count * (marks_in + marks_out)
        inputs += count * active_in
        outputs += count * active_out
        instances += count
    require(instances == 219, "manufacturing count drifted")

    boundary_count = template_counts["boundary_storage_port"]
    core_count = template_counts["protocol_core"]
    require((boundary_count, core_count) == (46, 1), "raw provider count drifted")
    boundary = object_(templates.get("boundary_storage_port"), "boundary")
    boundary_profiles: set[tuple[int, bool]] = set()
    for raw_mode in list_(boundary.get("modes"), "boundary modes"):
        mode = object_(raw_mode, "boundary mode")
        ports = [object_(p, "port") for p in list_(mode.get("ports"), "ports")]
        require(len(ports) == 1, "boundary physical slot count drifted")
        boundary_profiles.add((side_span(mode, ports[0]), is_corner(mode, ports[0])))
    require(boundary_profiles == {(3, False)}, "boundary geometry drifted")
    ordinary[(3, 1)] += boundary_count
    entity_maxima.extend([1] * boundary_count)

    core = object_(templates.get("protocol_core"), "core")
    core_faces: set[tuple[int, int, tuple[int, ...]]] = set()
    core_slots: set[int] = set()
    for raw_mode in list_(core.get("modes"), "core modes"):
        mode = object_(raw_mode, "core mode")
        faces: dict[str, list[dict[str, Any]]] = {}
        for raw_port in list_(mode.get("ports"), "core ports"):
            port = object_(raw_port, "core port")
            if port.get("kind") == "output":
                faces.setdefault(str(port.get("direction")), []).append(port)
        require(sorted(map(len, faces.values())) == [3, 3], "core 3+3 drifted")
        core_slots.add(sum(map(len, faces.values())))
        for direction, ports in faces.items():
            tangent = "x" if direction in ("N", "S") else "y"
            offsets = tuple(
                sorted(
                    integer(
                        object_(port.get("body_cell"), "core cell").get(tangent),
                        "core offset",
                    )
                    for port in ports
                )
            )
            require(not any(is_corner(mode, port) for port in ports), "core corner output")
            core_faces.add((side_span(mode, ports[0]), len(ports), offsets))
    require(
        core_slots == {6} and core_faces == {(9, 3, (1, 4, 7))},
        "core geometry drifted",
    )
    entity_maxima.append(3)

    generic = object_(problem.get("generic_requirements"), "generic")
    raw = sum(
        integer(value, f"raw.{key}")
        for key, value in object_(
            generic.get("raw_outputs"), "raw outputs"
        ).items()
    )
    final = sum(
        integer(value, f"final.{key}")
        for key, value in object_(
            generic.get("final_inputs"), "final inputs"
        ).items()
    )
    require((raw, final) == (52, 2), "generic demand drifted")
    total_marks = manufacturing_marks + raw
    terminals = inputs + outputs + raw + final
    census = Counter(entity_maxima)
    top = sorted(entity_maxima, reverse=True)[:8]
    require(
        (
            manufacturing_marks,
            total_marks,
            terminals,
            census,
            top,
            sum(top),
        )
        == (
            58,
            110,
            628,
            Counter({0: 170, 1: 89, 2: 3, 3: 4}),
            [3, 3, 3, 3, 2, 2, 2, 1],
            19,
        ),
        "marked entity arithmetic drifted",
    )
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
    require(
        ordinary == expected_ordinary and (excess, endpoint) == (63, 3),
        "ordinary membrane drifted",
    )
    body_area = 0
    for row in required:
        template = object_(templates.get(str(row.get("template"))), "template")
        areas = {
            integer(object_(mode, "mode").get("body", {}).get("width"), "width")
            * integer(object_(mode, "mode").get("body", {}).get("height"), "height")
            for mode in list_(template.get("modes"), "modes")
        }
        require(len(areas) == 1, "body area changes by mode")
        body_area += next(iter(areas))
    require(body_area == 3544, "required body area drifted")
    side_sum = 76
    m_in = (2 * side_sum + sum(top)) // 2
    t_in = side_sum + 48
    combined = m_in + t_in
    outside = terminals + total_marks - combined
    outside_cells = (outside + 3) // 4
    require(
        (m_in, t_in, combined, outside, outside_cells, 1188 + outside_cells)
        == (85, 124, 209, 529, 133, 1321),
        "ceiling arithmetic drifted",
    )
    universe = {
        (width, height)
        for width in range(6, 71)
        for height in range(6, 71)
    }
    old = {
        pair
        for pair in universe
        if (pair[0] * pair[1], min(pair)) > (1188, 22)
    }
    candidate = {
        pair
        for pair in universe
        if (pair[0] * pair[1], min(pair)) > (1188, 18)
    }
    delta = candidate - old
    require(
        (len(old), len(candidate), delta)
        == (2084, 2086, {(22, 54), (54, 22)}),
        "band composition drifted",
    )
    return {
        "required_instances": len(required),
        "required_body_area": body_area,
        "active_terminals": terminals,
        "total_marks": total_marks,
        "entity_max_census": {
            str(key): census[key] for key in sorted(census)
        },
        "top_eight": top,
        "top_eight_sum": sum(top),
        "ordinary_full_excess": excess,
        "ordinary_endpoint_extra": endpoint,
        "combined_inside_cap": combined,
        "outside_incidence_floor": outside,
        "outside_cell_floor": outside_cells,
        "total_required_cells": 1188 + outside_cells,
        "available_cell_cap_given_halo": 1320,
        "old_band_count": len(old),
        "candidate_band_count": len(candidate),
        "band_delta": [list(pair) for pair in sorted(delta)],
    }


def expected_map() -> dict[str, Any]:
    variables = []
    for variable_id, (width, height) in enumerate(((22, 54), (54, 22)), 1):
        variables.append(
            {
                "id": variable_id,
                "name": f"ceiling__w_{width:02d}__h_{height:02d}",
                "kind": "oriented_ceiling_selector",
                "width": width,
                "height": height,
                "area": 1188,
                "side_sum": 76,
                "entity_endpoint_budget": 19,
                "marked_inside_cap": 85,
                "ordinary_inside_cap": 124,
                "combined_inside_cap": 209,
                "outside_incidence_floor": 529,
                "outside_cell_floor": 133,
                "total_required_cells": 1321,
                "free_cell_cap": 1320,
                "coefficient": -1,
            }
        )
    return {
        "schema_version": "b1_sidewise_ceiling_variable_map_v1",
        "semantics": SEMANTICS,
        "variables": variables,
    }


def parse_formula(raw: bytes) -> dict[str, Any]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise TranslationError("formula is not ASCII") from exc
    require(len(lines) == 5, "formula line count drifted")
    header = HEADER.fullmatch(lines[0])
    require(header is not None, "formula header malformed")
    parsed_header = tuple(map(int, header.groups()))
    expected_comment = (
        "* model=b1_sidewise_ceiling_exclusion_pb_v1 "
        f"semantics={SEMANTICS} target=1188,18 old_upper=1188,22 "
        "given_smm209=true"
    )
    require(lines[1] == expected_comment, "formula provenance comment drifted")
    constraints: Counter[tuple[str, int, tuple[tuple[int, int], ...]]] = Counter()
    for line in lines[2:]:
        match = CONSTRAINT.fullmatch(line)
        require(match is not None, f"malformed constraint: {line!r}")
        body, relation, rhs_raw = match.groups()
        position = 0
        terms: list[tuple[int, int]] = []
        for term in TERM.finditer(body):
            require(
                body[position : term.start()].strip() == "",
                "unparsed OPB term bytes",
            )
            coefficient, variable = map(int, term.groups())
            terms.append((variable, coefficient))
            position = term.end()
        require(body[position:].strip() == "" and terms, "OPB term parse gap")
        constraints[(relation, int(rhs_raw), tuple(sorted(terms)))] += 1
    expected = Counter(
        {
            ("=", 1, ((1, 1), (2, 1))): 1,
            (">=", 0, ((1, -1),)): 1,
            (">=", 0, ((2, -1),)): 1,
        }
    )
    require(
        parsed_header == (2, 3, 1, 0) and constraints == expected,
        "OPB header/constraint multiset mismatch",
    )
    return {
        "header": {
            "variables": 2,
            "constraints": 3,
            "equalities": 1,
            "intsize": 0,
        },
        "constraint_multiset_exact": True,
    }


def manifest_entries(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise TranslationError("manifest not ASCII") from exc
    entries: dict[str, str] = {}
    for line in lines:
        parts = line.split("  ")
        require(
            len(parts) == 2
            and re.fullmatch(r"[0-9a-f]{64}", parts[0]) is not None,
            "manifest line malformed",
        )
        require(parts[1] not in entries, "duplicate manifest member")
        entries[parts[1]] = parts[0]
    return entries


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
                raise TranslationError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pb-authority", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        authority_raw, authority_identity = snapshot(
            args.pb_authority, "PB authority"
        )
        authority = parse_json(authority_raw, "PB authority")
        require(
            isinstance(authority, dict)
            and authority.get("schema_version") == AUTHORITY_SCHEMA
            and authority.get("status") == "PB_PRE_RUN_AUTHORITY_PASS"
            and authority.get("head") == HEAD,
            "PB authority failed",
        )
        _, tool_identity = snapshot(Path(__file__), "translation gate")
        tools = authority.get("tools")
        require(isinstance(tools, dict), "authority tools missing")
        identity_match(tool_identity, tools.get("translation_gate", {}), "translation gate")
        geometry_raw, geometry_identity = snapshot(
            args.geometry_admission, "geometry admission"
        )
        identity_match(
            geometry_identity,
            authority.get("geometry_admission", {}),
            "geometry admission",
        )
        geometry = parse_json(geometry_raw, "geometry admission")
        require(
            isinstance(geometry, dict)
            and geometry.get("status") == "PASS"
            and geometry.get("decision") == "ADMITTED_FOR_PB_ENCODER",
            "geometry admission semantics failed",
        )
        strict_raw, strict_identity = snapshot(args.instance, "strict instance")
        identity_match(
            strict_identity,
            authority.get("strict_instance", {}),
            "strict instance",
        )
        facts = derive_strict(
            object_(parse_json(strict_raw, "strict instance"), "strict instance")
        )
        files: dict[str, tuple[bytes, dict[str, Any]]] = {}
        for name in (
            "formula.opb",
            "variable_map.json",
            "encoder.meta.json",
            "build_record.json",
            "estimate.json",
            "SHA256SUMS",
        ):
            files[name] = snapshot(args.build_dir / name, name)
        parsed_formula = parse_formula(files["formula.opb"][0])
        var_map = parse_json(files["variable_map.json"][0], "variable map")
        require(var_map == expected_map(), "variable map semantic mismatch")
        estimate = parse_json(files["estimate.json"][0], "estimate")
        meta = parse_json(files["encoder.meta.json"][0], "metadata")
        build_record = parse_json(files["build_record.json"][0], "build record")
        require(
            isinstance(estimate, dict)
            and estimate.get("schema_version")
            == "b1_sidewise_ceiling_estimate_v1"
            and estimate.get("status") == "PASS"
            and estimate.get("formal_run_authorized") is False
            and estimate.get("counts")
            == {
                "variables": 2,
                "constraints": 3,
                "equalities": 1,
                "oriented_ceiling_dimensions": 2,
            },
            "estimate semantic mismatch",
        )
        encoder = tools.get("encoder")
        identity_match(
            estimate.get("tool", {}),
            encoder if isinstance(encoder, dict) else {},
            "estimate encoder",
        )
        require(
            isinstance(meta, dict)
            and meta.get("schema_version")
            == "b1_sidewise_ceiling_encoder_metadata_v1"
            and meta.get("status") == "BUILD_ONLY"
            and meta.get("semantics") == SEMANTICS
            and meta.get("formal_run_authorized") is False
            and meta.get("formula", {}).get("sha256")
            == files["formula.opb"][1]["sha256"]
            and meta.get("variable_map", {}).get("sha256")
            == files["variable_map.json"][1]["sha256"]
            and meta.get("band_composition")
            == {
                "old_verified_band_count": 2084,
                "new_ceiling_pair_count": 2,
                "candidate_band_count": 2086,
                "candidate_upper": [1188, 18],
            },
            "metadata semantic/hash mismatch",
        )
        require(
            isinstance(build_record, dict)
            and build_record.get("schema_version")
            == "b1_sidewise_ceiling_build_record_v1"
            and build_record.get("status") == "BUILD_ONLY_PASS"
            and build_record.get("formal_run_authorized") is False,
            "build record semantic mismatch",
        )
        entries = manifest_entries(files["SHA256SUMS"][0])
        expected_names = {
            "formula.opb",
            "variable_map.json",
            "encoder.meta.json",
            "build_record.json",
            "estimate.json",
        }
        require(set(entries) == expected_names, "build manifest member set mismatch")
        require(
            all(entries[name] == files[name][1]["sha256"] for name in expected_names),
            "build manifest digest mismatch",
        )
        checks = {
            "pb_authority_replay": True,
            "geometry_admission_replay": True,
            "strict_instance_identity": True,
            "strict_entity_census_rederived": True,
            "smm209_arithmetic_rederived": True,
            "old_band_count_2084": facts["old_band_count"] == 2084,
            "candidate_band_count_2086": facts["candidate_band_count"] == 2086,
            "band_delta_exact_two_orientations": facts["band_delta"]
            == [[22, 54], [54, 22]],
            "variable_map_exact": True,
            "opb_header_exact": parsed_formula["header"]
            == {
                "variables": 2,
                "constraints": 3,
                "equalities": 1,
                "intsize": 0,
            },
            "constraint_multiset_exact": parsed_formula[
                "constraint_multiset_exact"
            ],
            "manifest_reseal_exact": True,
            "build_metadata_fail_closed": True,
        }
        require(all(checks.values()), "translation check failed")
        report = {
            "schema_version": "b1_sidewise_ceiling_translation_gate_v1",
            "status": "PASS",
            "decision": "FORMAL_RUN_AUTHORIZED",
            "pb_authority": authority_identity,
            "geometry_admission": geometry_identity,
            "strict_instance": strict_identity,
            "tool": tool_identity,
            "build_inputs": {
                name: identity for name, (_, identity) in files.items()
            },
            "independent_facts": facts,
            "checks": checks,
            "corpus_errors": [],
            "formal_run_authorized": True,
            "claim_boundary": {
                "translation_only": True,
                "unsat_or_proof_not_yet_established": True,
                "upper": [1188, 22],
                "lower": "absent",
                "production_certified": False,
            },
        }
        raw = (
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n"
        ).encode()
        require(not args.output.exists() and not args.output.is_symlink(), "output exists")
        require(
            args.output.parent.is_dir() and not args.output.parent.is_symlink(),
            "output parent is not a real directory",
        )
        write_once(args.output, raw)
    except (OSError, TranslationError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "decision": report["decision"],
                "output": str(args.output),
                "size_bytes": len(raw),
                "sha256": sha(raw),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
