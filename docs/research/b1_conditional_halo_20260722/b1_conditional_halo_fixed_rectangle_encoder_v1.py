#!/usr/bin/env python3
"""Emit paired control/treatment OPBs for one fixed conditional-halo case."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


MODEL_SCHEMA = "b1_conditional_halo_fixed_rectangle_model_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
VAR_MAP_SCHEMA = "b1_conditional_halo_fixed_rectangle_var_map_v1"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
ADMISSION_SCHEMA = "b1_conditional_halo_geometry_admission_v1"
STENCIL_SCHEMA = "b1_conditional_halo_stencil_v1"
STRICT_PATH = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
STRICT_SHA = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
GRID = 70
AREA_LEDGER_BODY = 3_544
FREE_CAP = 1_320
HALO_RHS2 = 6_650
PAIR_OVERLAP_EDGES = 18_632


class EncoderError(ValueError):
    """A paired diagnostic model input or invariant failed closed."""


@dataclass(frozen=True, slots=True)
class Constraint:
    terms: tuple[tuple[int, int], ...]
    relation: str
    rhs: int
    category: str

    def render(self) -> str:
        return (
            " ".join(
                f"{'+' if coefficient >= 0 else ''}{coefficient} x{variable}" for variable, coefficient in self.terms
            )
            + f" {self.relation} {self.rhs} ;"
        )

    def key(self) -> str:
        return json.dumps(
            {"terms": self.terms, "relation": self.relation, "rhs": self.rhs},
            sort_keys=True,
            separators=(",", ":"),
        )


def _reject(value: str) -> Any:
    raise EncoderError(f"non-finite JSON number forbidden: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EncoderError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load(path: Path, field: str) -> tuple[Mapping[str, Any], bytes]:
    raw = path.resolve(strict=True).read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EncoderError(f"{field} parse failure: {exc}") from exc
    if not isinstance(value, Mapping):
        raise EncoderError(f"{field} root must be an object")
    return value, raw


def _obj(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EncoderError(f"{field} must be an object")
    return value


def _arr(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EncoderError(f"{field} must be an array")
    return value


def _int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise EncoderError(f"{field} must be an exact integer")
    return int(value)


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise EncoderError(f"not a regular file: {resolved}")
    raw = resolved.read_bytes()
    return {"path": _display(resolved, root), "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _check_record(value: Any, root: Path, field: str) -> Path:
    record = _obj(value, field)
    if set(record) != {"path", "sha256", "size_bytes"}:
        raise EncoderError(f"{field} snapshot key mismatch")
    path = record.get("path")
    if type(path) is not str or not path:
        raise EncoderError(f"{field}.path malformed")
    resolved = (root / path).resolve(strict=True)
    if _record(resolved, root) != dict(record):
        raise EncoderError(f"{field} is stale")
    return resolved


def _canonical_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)


def _validate_admission(path: Path, root: Path) -> tuple[Mapping[str, Any], dict[str, Any], Path]:
    admission, _ = _load(path, "geometry admission")
    if admission.get("schema_version") != ADMISSION_SCHEMA or admission.get("status") != "PASS":
        raise EncoderError("geometry admission is absent or not PASS")
    if admission.get("scope") != "geometry_only_pre_encoder" or admission.get("corpus_errors") != []:
        raise EncoderError("geometry admission scope/corpus_errors drifted")
    halo = _obj(admission.get("conditional_halo"), "admission.conditional_halo")
    if (
        halo.get("rhs_original") != 3_325
        or halo.get("rhs_doubled") != HALO_RHS2
        or halo.get("quantifier") != "all_selected_poles"
    ):
        raise EncoderError("geometry admission halo statement drifted")
    checks = _arr(admission.get("checks"), "admission.checks")
    if not checks or any(_obj(value, "admission check").get("status") != "PASS" for value in checks):
        raise EncoderError("geometry admission checks are not all PASS")
    inputs = _obj(admission.get("inputs"), "admission.inputs")
    required = {
        "stencil",
        "necessity_proof",
        "coordinate_report",
        "prefix_report",
        "agreement_report",
        "adversarial_verdict_json",
        "adversarial_verdict_doc",
    }
    if not required.issubset(inputs):
        raise EncoderError("geometry admission input roles are incomplete")
    for key, value in inputs.items():
        _check_record(value, root, f"admission.inputs.{key}")
    stencil_path = _check_record(inputs["stencil"], root, "admission.inputs.stencil")
    return admission, _record(path, root), stencil_path


def _stencil(path: Path) -> tuple[dict[tuple[int, int], int], Mapping[str, Any]]:
    data, _ = _load(path, "stencil")
    if data.get("schema") != STENCIL_SCHEMA or data.get("weight_units") != "doubled_integer":
        raise EncoderError("stencil schema/weight units drifted")
    expected = _obj(data.get("expected"), "stencil.expected")
    if expected.get("orbit_count") != 14 or expected.get("total_weight2") != 792 or expected.get("total_weight") != 396:
        raise EncoderError("stencil expected totals drifted")
    if expected.get("support_dx") != [-8, 9] or expected.get("support_dy") != [
        -8,
        9,
    ]:
        raise EncoderError("stencil support drifted")
    orbit_weights: dict[tuple[int, int], int] = {}
    for index, raw in enumerate(_arr(data.get("orbits"), "stencil.orbits")):
        record = _obj(raw, f"stencil.orbits[{index}]")
        major = _int(record.get("major_odd"), "major_odd")
        minor = _int(record.get("minor_odd"), "minor_odd")
        weight = _int(record.get("weight2"), "weight2")
        if major < minor or min(minor, weight) <= 0 or (major, minor) in orbit_weights:
            raise EncoderError("malformed stencil orbit")
        orbit_weights[(major, minor)] = weight
    if len(orbit_weights) != 14:
        raise EncoderError("stencil orbit count drifted")
    expanded: dict[tuple[int, int], int] = {}
    for dx in range(-8, 10):
        for dy in range(-8, 10):
            first, second = abs(2 * dx - 1), abs(2 * dy - 1)
            weight = orbit_weights.get((max(first, second), min(first, second)), 0)
            if weight:
                expanded[(dx, dy)] = weight
    if sum(expanded.values()) != 792 or len(expanded) != 96:
        raise EncoderError("expanded stencil totals drifted")
    return expanded, data


def _strict(root: Path) -> dict[str, Any]:
    record = _record(root / STRICT_PATH, root)
    if record["sha256"] != STRICT_SHA:
        raise EncoderError("strict SHA drifted")
    data, _ = _load(root / STRICT_PATH, "strict")
    grid = _obj(data.get("grid"), "strict.grid")
    if (grid.get("width"), grid.get("height")) != (GRID, GRID):
        raise EncoderError("strict grid drifted")
    return record


def _corpus(path: Path, root: Path, case_index: int) -> tuple[Mapping[str, Any], dict[str, Any], Mapping[str, Any]]:
    data, _ = _load(path, "diagnostic corpus")
    if data.get("schema_version") != CORPUS_SCHEMA or data.get("status") != "PASS" or data.get("corpus_errors") != []:
        raise EncoderError("diagnostic corpus is not PASS")
    if data.get("case_count") != 512 or data.get("solver_results_included") is not False:
        raise EncoderError("diagnostic corpus size/result boundary drifted")
    _check_record(data.get("strict_instance"), root, "corpus.strict_instance")
    _check_record(data.get("r1_authoritative_translation_gate"), root, "corpus.r1_gate")
    cases = _arr(data.get("cases"), "corpus.cases")
    if len(cases) != 512:
        raise EncoderError("diagnostic corpus does not contain exactly 512 cases")
    pair_ids: set[str] = set()
    transpose_groups: dict[str, list[Mapping[str, Any]]] = {}
    for expected_index, raw_case in enumerate(cases):
        candidate = _obj(raw_case, f"corpus.cases[{expected_index}]")
        pair_id = candidate.get("pair_id")
        transpose_group_id = candidate.get("transpose_group_id")
        if candidate.get("case_index") != expected_index:
            raise EncoderError("corpus case indices are not canonical")
        if type(pair_id) is not str or pair_id != f"pair_{expected_index:03d}" or pair_id in pair_ids:
            raise EncoderError("corpus pair identity is not unique and canonical per case")
        if type(transpose_group_id) is not str:
            raise EncoderError("corpus transpose symmetry-group identity is malformed")
        pair_ids.add(pair_id)
        transpose_groups.setdefault(transpose_group_id, []).append(candidate)
    if set(transpose_groups) != {f"transpose_group_{rank:03d}" for rank in range(256)}:
        raise EncoderError("corpus transpose symmetry-group identities drifted")
    for rank in range(256):
        group = transpose_groups[f"transpose_group_{rank:03d}"]
        if len(group) != 2 or [case.get("variant") for case in group] != ["original", "transpose"]:
            raise EncoderError("corpus transpose symmetry group is not an ordered original/transpose pair")
    if not 0 <= case_index < len(cases):
        raise EncoderError("case index outside corpus")
    case = _obj(cases[case_index], f"corpus.cases[{case_index}]")
    if case.get("case_index") != case_index:
        raise EncoderError("corpus case index is not canonical")
    return data, _record(path, root), case


def _anchors(gap: int) -> tuple[int, ...]:
    cells = [value for value in range(GRID) if value != gap]
    chunks = tuple(tuple(cells[index : index + 3]) for index in range(0, 69, 3))
    if gap not in range(0, GRID, 3) or any(chunk != tuple(range(chunk[0], chunk[0] + 3)) for chunk in chunks):
        raise EncoderError("illegal boundary gap")
    return tuple(chunk[0] for chunk in chunks)


def _patterns() -> tuple[dict[str, Any], ...]:
    gaps = tuple(range(0, GRID, 3))
    pairs = tuple((0, gap) for gap in gaps) + tuple((gap, 0) for gap in gaps[1:])
    result = []
    for delta, (left_gap, bottom_gap) in enumerate(pairs):
        left, bottom = _anchors(left_gap), _anchors(bottom_gap)
        bodies = {(0, a + d) for a in left for d in range(3)} | {(a + d, 0) for a in bottom for d in range(3)}
        q = {(1, a + 1) for a in left} | {(a + 1, 1) for a in bottom}
        if len(bodies) != 138 or len(q) != 46 or bodies & q:
            raise EncoderError("boundary pattern geometry drifted")
        result.append({"delta": delta, "left_gap": left_gap, "bottom_gap": bottom_gap, "body": bodies, "q": q})
    return tuple(result)


def _contact(pattern: Mapping[str, Any], case: Mapping[str, Any]) -> tuple[int, int]:
    x, y, w, h = (_int(case[key], f"case.{key}") for key in ("x", "y", "w", "h"))
    cells = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    intersection = pattern["q"] & cells
    endpoints = sum((qx in {x, x + w - 1} if qy == 1 else qy in {y, y + h - 1}) for qx, qy in intersection)
    return len(intersection), endpoints


def _constraint(terms: Iterable[tuple[int, int]], relation: str, rhs: int, category: str) -> Constraint:
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        combined[variable] += coefficient
    canonical = tuple(sorted((variable, coefficient) for variable, coefficient in combined.items() if coefficient))
    if relation not in {"=", ">="} or not canonical:
        raise EncoderError("malformed constraint")
    return Constraint(canonical, relation, rhs, category)


def _build(
    case: Mapping[str, Any],
    stencil: Mapping[tuple[int, int], int],
    model_scope: str,
) -> tuple[list[dict[str, Any]], list[Constraint], Constraint, dict[str, Any]]:
    patterns = _patterns()
    w, h, x, y, selected_delta = (_int(case[key], f"case.{key}") for key in ("w", "h", "x", "y", "delta"))
    if (w, h) not in {(34, 35), (35, 34)} or not (1 <= x <= GRID - w and 1 <= y <= GRID - h):
        raise EncoderError("fixed rectangle is outside the admitted ceiling corpus")
    contacts = {pattern["delta"]: _contact(pattern, case) for pattern in patterns}
    if contacts[selected_delta] != (case.get("a_delta"), case.get("e_delta")):
        raise EncoderError("corpus q/e values disagree with rebuilt geometry")
    kmax = (GRID * GRID - AREA_LEDGER_BODY - w * h) // 4
    if kmax != 41:
        raise EncoderError("pole-count selector range ceiling drifted")

    variables: list[dict[str, Any]] = []
    for pattern in patterns:
        variables.append(
            {
                "id": len(variables) + 1,
                "name": f"b_delta_{pattern['delta']:02d}",
                "kind": "boundary_pattern",
                "delta": pattern["delta"],
                "left_gap": pattern["left_gap"],
                "bottom_gap": pattern["bottom_gap"],
            }
        )
    pole_ids: dict[tuple[int, int], int] = {}
    for qx in range(69):
        for qy in range(69):
            variable_id = len(variables) + 1
            pole_ids[(qx, qy)] = variable_id
            variables.append(
                {"id": variable_id, "name": f"p_x_{qx:02d}_y_{qy:02d}", "kind": "pole_anchor", "x": qx, "y": qy}
            )
    count_ids: dict[int, int] = {}
    for count in range(9, kmax + 1):
        variable_id = len(variables) + 1
        count_ids[count] = variable_id
        variables.append({"id": variable_id, "name": f"n_{count:02d}", "kind": "pole_count", "count": count})
    if len(variables) != 4_841:
        raise EncoderError("variable count drifted")

    constraints: list[Constraint] = [
        _constraint(((delta + 1, 1) for delta in range(47)), "=", 1, "pattern_exactly_one"),
        _constraint(((variable, 1) for variable in count_ids.values()), "=", 1, "count_exactly_one"),
        _constraint(
            [
                *((variable, 1) for variable in pole_ids.values()),
                *((variable, -count) for count, variable in count_ids.items()),
            ],
            "=",
            0,
            "pole_count_link",
        ),
    ]
    if model_scope == "diagnostic_fixed_pattern":
        constraints.append(
            _constraint(
                ((selected_delta + 1, 1),),
                "=",
                1,
                "diagnostic_pattern_fix",
            )
        )
    elif model_scope != "band_any_pattern":
        raise EncoderError("unsupported model scope")
    for delta in range(47):
        a_delta, e_delta = contacts[delta]
        base = w * h + -(-(580 - w - h + a_delta // 2 + e_delta) // 4)
        for count, count_id in count_ids.items():
            if base + 4 * (count - 9) > FREE_CAP:
                constraints.append(_constraint(((delta + 1, -1), (count_id, -1)), ">=", -1, "r1_count_exclusion"))

    rectangle = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    pole_bodies = {(qx, qy): {(qx + dx, qy + dy) for dx in range(2) for dy in range(2)} for qx, qy in pole_ids}
    for anchor, body in pole_bodies.items():
        if body & rectangle:
            constraints.append(_constraint(((pole_ids[anchor], -1),), ">=", 0, "pole_rectangle_exclusion"))
    overlap_edges = 0
    anchors = list(pole_ids)
    for index, first in enumerate(anchors):
        for second in anchors[index + 1 :]:
            if abs(first[0] - second[0]) <= 1 and abs(first[1] - second[1]) <= 1:
                overlap_edges += 1
                constraints.append(
                    _constraint(((pole_ids[first], -1), (pole_ids[second], -1)), ">=", -1, "pole_pair_overlap")
                )
    if overlap_edges != PAIR_OVERLAP_EDGES:
        raise EncoderError("full pole-overlap graph edge count drifted")

    pattern_pole_conflicts = 0
    for pattern in patterns:
        forbidden = pattern["body"] | pattern["q"]
        for anchor, body in pole_bodies.items():
            if body & forbidden:
                pattern_pole_conflicts += 1
                constraints.append(
                    _constraint(((pattern["delta"] + 1, -1), (pole_ids[anchor], -1)), ">=", -1, "pattern_pole_conflict")
                )

    capacities: dict[tuple[int, int], int] = {}
    for anchor in anchors:
        capacity = 0
        for (dx, dy), weight in stencil.items():
            cell = (anchor[0] + dx, anchor[1] + dy)
            if 0 <= cell[0] < GRID and 0 <= cell[1] < GRID and cell not in rectangle:
                capacity += weight
        capacities[anchor] = capacity
    halo = _constraint(
        ((pole_ids[anchor], capacities[anchor]) for anchor in anchors if capacities[anchor]),
        ">=",
        HALO_RHS2,
        "conditional_halo",
    )
    counts = dict(Counter(constraint.category for constraint in constraints))
    counts.update(
        {
            "variables": len(variables),
            "control_constraints": len(constraints),
            "treatment_constraints": len(constraints) + 1,
            "pole_overlap_edges": overlap_edges,
            "pattern_pole_conflicts": pattern_pole_conflicts,
            "pole_count_min": 9,
            "pole_count_max": kmax,
        }
    )
    return variables, constraints, halo, counts


def _render(constraints: Sequence[Constraint], variable_count: int) -> bytes:
    equal = sum(constraint.relation == "=" for constraint in constraints)
    lines = [
        f"* #variable= {variable_count} #constraint= {len(constraints)} #equal= {equal} intsize= 64",
        f"* model={MODEL_SCHEMA} paired_diagnostic=control_vs_one_conditional_halo_constraint",
        *(constraint.render() for constraint in constraints),
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _write_pair(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    output_paths = [
        args.control_opb,
        args.control_meta,
        args.control_var_map,
        args.treatment_opb,
        args.treatment_meta,
        args.treatment_var_map,
    ]
    resolved = [path.resolve() for path in output_paths]
    if len(set(resolved)) != len(resolved) or any(path.exists() for path in resolved):
        raise FileExistsError("paired outputs must be distinct and absent")
    strict_record = _strict(root)
    _, admission_record, stencil_path = _validate_admission(args.geometry_admission, root)
    stencil, _ = _stencil(stencil_path)
    _, corpus_record, case = _corpus(args.corpus, root, args.case_index)
    variables, control_constraints, halo, counts = _build(case, stencil, args.model_scope)
    treatment_constraints = [*control_constraints, halo]
    control_opb, treatment_opb = (
        _render(control_constraints, len(variables)),
        _render(treatment_constraints, len(variables)),
    )
    pair_material = json.dumps(
        {
            "admission": admission_record["sha256"],
            "corpus": corpus_record["sha256"],
            "case_index": args.case_index,
            "model_scope": args.model_scope,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    pair_id = hashlib.sha256(pair_material).hexdigest()
    var_map = {
        "schema_version": VAR_MAP_SCHEMA,
        "status": "PASS",
        "model_schema_version": MODEL_SCHEMA,
        "model_scope": args.model_scope,
        "strict_instance_sha256": STRICT_SHA,
        "paired_generation_sha256": pair_id,
        "case": dict(case),
        "counts": counts,
        "variable_count": len(variables),
        "variables": variables,
    }
    for path in (args.control_var_map, args.treatment_var_map):
        _canonical_write(path.resolve(), var_map)
    for path, raw in ((args.control_opb, control_opb), (args.treatment_opb, treatment_opb)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)
    argv_record = [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]
    for arm, opb_path, meta_path, map_path, constraints in (
        ("control", args.control_opb, args.control_meta, args.control_var_map, control_constraints),
        ("treatment", args.treatment_opb, args.treatment_meta, args.treatment_var_map, treatment_constraints),
    ):
        metadata = {
            "schema_version": META_SCHEMA,
            "status": "PASS",
            "model_schema_version": MODEL_SCHEMA,
            "variable_map_schema_version": VAR_MAP_SCHEMA,
            "arm": arm,
            "model_scope": args.model_scope,
            "paired_generation_sha256": pair_id,
            "argv": argv_record,
            "encoder_source": _record(Path(__file__), root),
            "strict_instance": strict_record,
            "geometry_admission": admission_record,
            "stencil": _record(stencil_path, root),
            "corpus_manifest": corpus_record,
            "case": dict(case),
            "counts": counts,
            "constraint_count": len(constraints),
            "constraint_multiset_sha256": hashlib.sha256(
                "\n".join(sorted(constraint.key() for constraint in constraints)).encode()
            ).hexdigest(),
            "paired_diff": {
                "control_to_treatment": "append exactly one conditional_halo constraint",
                "conditional_halo_rhs2": HALO_RHS2,
                "prepruning_by_halo": False,
            },
            "outputs": {
                "opb": _record(opb_path, root),
                "var_map": _record(map_path, root),
                "metadata": {"path": _display(meta_path, root)},
            },
            "proof_status": "build_only_no_solver_or_proof_no_sat_or_unsat_claim",
            "claim_boundary": [
                "unknown manufacturing/core/body coverage is omitted as a safe relaxation",
                "control and treatment differ by exactly one halo constraint",
                "diagnostic model only; no new upper bound, witness, attainability, or optimality claim",
                "research artifact; not production CERTIFIED evidence",
            ],
        }
        _canonical_write(meta_path.resolve(), metadata)
    print(
        json.dumps(
            {
                "status": "PASS",
                "case_index": args.case_index,
                "variables": len(variables),
                "control_constraints": len(control_constraints),
                "treatment_constraints": len(treatment_constraints),
                "paired_generation_sha256": pair_id,
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--case-index", type=int, required=True)
    parser.add_argument(
        "--model-scope",
        choices=("diagnostic_fixed_pattern", "band_any_pattern"),
        default="diagnostic_fixed_pattern",
    )
    parser.add_argument("--control-opb", type=Path, required=True)
    parser.add_argument("--control-meta", type=Path, required=True)
    parser.add_argument("--control-var-map", type=Path, required=True)
    parser.add_argument("--treatment-opb", type=Path, required=True)
    parser.add_argument("--treatment-meta", type=Path, required=True)
    parser.add_argument("--treatment-var-map", type=Path, required=True)
    parser.set_defaults(func=_write_pair)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args, argv))


if __name__ == "__main__":
    raise SystemExit(main())
