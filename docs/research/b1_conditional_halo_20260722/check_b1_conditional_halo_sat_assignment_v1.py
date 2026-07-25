#!/usr/bin/env python3
"""Check a full original-variable SAT assignment for one R2 model arm."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


OUTPUT_SCHEMA = "b1_conditional_halo_sat_assignment_check_v1"
ASSIGNMENT_SCHEMA = "b1_conditional_halo_full_assignment_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
VAR_MAP_SCHEMA = "b1_conditional_halo_fixed_rectangle_var_map_v1"
ADMISSION_SCHEMA = "b1_conditional_halo_geometry_admission_v1"
STENCIL_SCHEMA = "b1_conditional_halo_stencil_v1"
GRID = 70


class AssignmentError(ValueError):
    """The assignment or its bound model failed closed."""


def _reject(value: str) -> Any:
    raise AssignmentError(f"non-finite JSON number forbidden: {value}")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise AssignmentError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load(path: Path, field: str) -> tuple[Mapping[str, Any], bytes]:
    raw = path.resolve(strict=True).read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssignmentError(f"{field} parse failure: {exc}") from exc
    if not isinstance(value, Mapping):
        raise AssignmentError(f"{field} root must be object")
    return value, raw


def _obj(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssignmentError(f"{field} must be object")
    return value


def _arr(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AssignmentError(f"{field} must be array")
    return value


def _int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise AssignmentError(f"{field} must be exact integer")
    return int(value)


def _display(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _record(path: Path, root: Path) -> dict[str, Any]:
    raw = path.resolve(strict=True).read_bytes()
    return {"path": _display(path, root), "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)


def _patterns() -> tuple[dict[str, Any], ...]:
    gaps = tuple(range(0, GRID, 3))
    patterns = []
    for delta, (left_gap, bottom_gap) in enumerate(tuple((0, g) for g in gaps) + tuple((g, 0) for g in gaps[1:])):

        def anchors(gap: int) -> tuple[int, ...]:
            cells = [value for value in range(GRID) if value != gap]
            chunks = tuple(tuple(cells[i : i + 3]) for i in range(0, 69, 3))
            if any(chunk != tuple(range(chunk[0], chunk[0] + 3)) for chunk in chunks):
                raise AssignmentError("boundary chunk malformed")
            return tuple(chunk[0] for chunk in chunks)

        left, bottom = anchors(left_gap), anchors(bottom_gap)
        body = {(0, a + d) for a in left for d in range(3)} | {(a + d, 0) for a in bottom for d in range(3)}
        q = {(1, a + 1) for a in left} | {(a + 1, 1) for a in bottom}
        if len(body) != 138 or len(q) != 46 or body & q:
            raise AssignmentError("boundary pattern malformed")
        patterns.append({"delta": delta, "body": body, "q": q})
    return tuple(patterns)


def _contact(pattern: Mapping[str, Any], w: int, h: int, x: int, y: int) -> tuple[int, int]:
    rectangle = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    hit = pattern["q"] & rectangle
    endpoints = sum((qx in {x, x + w - 1} if qy == 1 else qy in {y, y + h - 1}) for qx, qy in hit)
    return len(hit), endpoints


def _stencil(path: Path) -> dict[tuple[int, int], int]:
    data, _ = _load(path, "stencil")
    if data.get("schema") != STENCIL_SCHEMA or data.get("weight_units") != "doubled_integer":
        raise AssignmentError("stencil schema drifted")
    orbits = {}
    for raw in _arr(data.get("orbits"), "orbits"):
        item = _obj(raw, "orbit")
        key = (_int(item.get("major_odd"), "major"), _int(item.get("minor_odd"), "minor"))
        if key in orbits:
            raise AssignmentError("duplicate stencil orbit")
        orbits[key] = _int(item.get("weight2"), "weight2")
    expanded = {}
    for dx in range(-8, 10):
        for dy in range(-8, 10):
            first, second = abs(2 * dx - 1), abs(2 * dy - 1)
            weight = orbits.get((max(first, second), min(first, second)), 0)
            if weight:
                expanded[(dx, dy)] = weight
    if len(expanded) != 96 or sum(expanded.values()) != 792:
        raise AssignmentError("stencil expansion drifted")
    return expanded


def _main(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    meta, _ = _load(args.metadata, "metadata")
    varmap, _ = _load(args.var_map, "variable map")
    assignment, assignment_raw = _load(args.assignment, "assignment")
    admission, _ = _load(args.geometry_admission, "geometry admission")
    if meta.get("schema_version") != META_SCHEMA or meta.get("status") != "PASS" or meta.get("arm") != args.arm:
        raise AssignmentError("metadata arm/schema/status mismatch")
    model_scope = meta.get("model_scope")
    if model_scope not in {"diagnostic_fixed_pattern", "band_any_pattern"}:
        raise AssignmentError("metadata model scope malformed")
    if (
        varmap.get("schema_version") != VAR_MAP_SCHEMA
        or varmap.get("status") != "PASS"
        or varmap.get("model_scope") != model_scope
    ):
        raise AssignmentError("variable-map schema/status/scope mismatch")
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("status") != "PASS"
        or admission.get("corpus_errors") != []
    ):
        raise AssignmentError("geometry admission not PASS")
    outputs = _obj(meta.get("outputs"), "metadata.outputs")
    if dict(_obj(outputs.get("opb"), "metadata opb")) != _record(args.opb, root) or dict(
        _obj(outputs.get("var_map"), "metadata var map")
    ) != _record(args.var_map, root):
        raise AssignmentError("metadata output hashes stale")
    if (
        assignment.get("schema_version") != ASSIGNMENT_SCHEMA
        or assignment.get("opb_sha256") != _record(args.opb, root)["sha256"]
    ):
        raise AssignmentError("assignment schema/model hash mismatch")
    values_raw = _arr(assignment.get("values"), "assignment.values")
    if len(values_raw) != 4_841 or any(type(value) is not int or value not in {0, 1} for value in values_raw):
        raise AssignmentError("assignment is not a full 4841-bit original-variable vector")
    values = [0, *values_raw]
    variables = _arr(varmap.get("variables"), "varmap.variables")
    if len(variables) != 4_841:
        raise AssignmentError("variable map count drifted")
    for expected_id, raw in enumerate(variables, 1):
        if _obj(raw, f"variables[{expected_id}]").get("id") != expected_id:
            raise AssignmentError("variable map is not dense and ordered")
    case = _obj(meta.get("case"), "metadata.case")
    w, h, x, y, diagnostic_delta = (_int(case.get(key), f"case.{key}") for key in ("w", "h", "x", "y", "delta"))
    patterns = _patterns()
    selected_deltas = [delta for delta in range(47) if values[delta + 1]]
    if len(selected_deltas) != 1:
        raise AssignmentError("pattern exactly-one failed")
    selected_delta = selected_deltas[0]
    if model_scope == "diagnostic_fixed_pattern" and selected_delta != diagnostic_delta:
        raise AssignmentError("diagnostic fixed-pattern constraint failed")
    pole_records = [
        _obj(raw, "pole variable") for raw in variables if _obj(raw, "variable").get("kind") == "pole_anchor"
    ]
    selected_poles = {(record["x"], record["y"]) for record in pole_records if values[_int(record["id"], "pole id")]}
    count_records = [
        _obj(raw, "count variable") for raw in variables if _obj(raw, "variable").get("kind") == "pole_count"
    ]
    selected_counts = [
        _int(record["count"], "count") for record in count_records if values[_int(record["id"], "count id")]
    ]
    if len(selected_counts) != 1 or len(selected_poles) != selected_counts[0]:
        raise AssignmentError("pole count exactly-one/link failed")
    actual_p = len(selected_poles)
    if not 9 <= actual_p <= 41:
        raise AssignmentError("actual P outside selector range")
    a_delta, e_delta = _contact(patterns[selected_delta], w, h, x, y)
    lhs = w * h + -(-(580 - w - h + a_delta // 2 + e_delta) // 4) + 4 * (actual_p - 9)
    if lhs > 1_320:
        raise AssignmentError("selected pattern/count violates the R1-count condition")
    rectangle = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    pole_bodies = {
        anchor: {(anchor[0] + dx, anchor[1] + dy) for dx in range(2) for dy in range(2)} for anchor in selected_poles
    }
    if any(body & rectangle for body in pole_bodies.values()):
        raise AssignmentError("selected pole intersects fixed rectangle")
    selected_list = sorted(selected_poles)
    for index, first in enumerate(selected_list):
        for second in selected_list[index + 1 :]:
            if abs(first[0] - second[0]) <= 1 and abs(first[1] - second[1]) <= 1:
                raise AssignmentError("selected pole bodies overlap")
    forbidden = patterns[selected_delta]["body"] | patterns[selected_delta]["q"]
    if any(body & forbidden for body in pole_bodies.values()):
        raise AssignmentError("selected pole conflicts with selected boundary pattern/Q")
    inputs = _obj(admission.get("inputs"), "admission.inputs")
    stencil_record = _obj(inputs.get("stencil"), "admission.inputs.stencil")
    stencil_path = (root / str(stencil_record.get("path"))).resolve(strict=True)
    if _record(stencil_path, root) != dict(stencil_record):
        raise AssignmentError("admitted stencil bytes are stale")
    stencil = _stencil(stencil_path)
    halo_lhs2 = 0
    for anchor in selected_poles:
        halo_lhs2 += sum(
            weight
            for (dx, dy), weight in stencil.items()
            if 0 <= anchor[0] + dx < GRID
            and 0 <= anchor[1] + dy < GRID
            and (anchor[0] + dx, anchor[1] + dy) not in rectangle
        )
    if args.arm == "treatment" and halo_lhs2 < 6_650:
        raise AssignmentError("treatment conditional-halo constraint failed")
    payload = {
        "schema_version": OUTPUT_SCHEMA,
        "status": "PASS",
        "assignment_status": "CHECKED_SAT",
        "arm": args.arm,
        "model_scope": model_scope,
        "case_index": case.get("case_index"),
        "paired_generation_sha256": meta.get("paired_generation_sha256"),
        "assignment": _record(args.assignment, root),
        "assignment_sha256": hashlib.sha256(assignment_raw).hexdigest(),
        "model": {
            "opb": _record(args.opb, root),
            "metadata": _record(args.metadata, root),
            "var_map": _record(args.var_map, root),
        },
        "semantic_checks": {
            "full_original_variables": 4_841,
            "selected_delta": selected_delta,
            "selected_count": selected_counts[0],
            "actual_p": actual_p,
            "r1_count_lhs": lhs,
            "pole_rectangle_conflicts": 0,
            "pole_pair_overlaps": 0,
            "pattern_pole_conflicts": 0,
            "halo_lhs2": halo_lhs2,
            "halo_rhs2": 6_650 if args.arm == "treatment" else None,
        },
        "checker_source": _record(Path(__file__), root),
        "argv": [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)],
        "claim_boundary": [
            "checks only the supplied full assignment against the selected relaxed model arm",
            "CHECKED_SAT is not a factory-layout witness or attainability claim",
            "does not establish a new upper bound or global optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
    }
    _write(args.output.resolve(), payload)
    print(
        json.dumps(
            {"status": "PASS", "assignment_status": "CHECKED_SAT", "arm": args.arm, "actual_p": actual_p},
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--arm", choices=("control", "treatment"), required=True)
    parser.add_argument("--opb", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--var-map", type=Path, required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return _main(_parser().parse_args(argv), argv)


if __name__ == "__main__":
    raise SystemExit(main())
