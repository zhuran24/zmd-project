#!/usr/bin/env python3
"""Independently rebuild and verify one paired conditional-halo translation."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "b1_conditional_halo_translation_gate_v1"
MODEL_SCHEMA = "b1_conditional_halo_fixed_rectangle_model_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
VAR_MAP_SCHEMA = "b1_conditional_halo_fixed_rectangle_var_map_v1"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
ADMISSION_SCHEMA = "b1_conditional_halo_geometry_admission_v1"
STENCIL_SCHEMA = "b1_conditional_halo_stencil_v1"
STRICT_PATH = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
STRICT_SHA = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
R1_GATE_SCHEMA = "b1_q_membrane_halo_band_translation_gate_v1"
LABEL = b"B1_R2_CONDITIONAL_HALO_DIAGNOSTIC_V1"
GRID = 70
HALO_RHS2 = 6_650


class GateError(ValueError):
    """Translation input or semantics failed closed."""


@dataclass(frozen=True, slots=True)
class PB:
    terms: tuple[tuple[int, int], ...]
    relation: str
    rhs: int
    category: str = ""

    def key(self) -> str:
        return json.dumps(
            {"terms": self.terms, "relation": self.relation, "rhs": self.rhs}, sort_keys=True, separators=(",", ":")
        )


def _reject(value: str) -> Any:
    raise GateError(f"non-finite JSON number forbidden: {value}")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise GateError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load(path: Path, field: str) -> tuple[Mapping[str, Any], bytes]:
    raw = path.resolve(strict=True).read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError(f"{field} parse failure: {exc}") from exc
    if not isinstance(value, Mapping):
        raise GateError(f"{field} root must be object")
    return value, raw


def _obj(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GateError(f"{field} must be object")
    return value


def _arr(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise GateError(f"{field} must be array")
    return value


def _int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise GateError(f"{field} must be exact integer")
    return int(value)


def _display(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    raw = resolved.read_bytes()
    return {"path": _display(resolved, root), "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _check_record(value: Any, root: Path, field: str) -> Path:
    record = _obj(value, field)
    if set(record) != {"path", "sha256", "size_bytes"} or type(record.get("path")) is not str:
        raise GateError(f"{field} snapshot malformed")
    path = (root / str(record["path"])).resolve(strict=True)
    if _record(path, root) != dict(record):
        raise GateError(f"{field} stale")
    return path


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)


def _patterns() -> tuple[dict[str, Any], ...]:
    gaps = tuple(range(0, GRID, 3))
    result = []
    for delta, (lg, bg) in enumerate(tuple((0, g) for g in gaps) + tuple((g, 0) for g in gaps[1:])):

        def anchors(gap: int) -> tuple[int, ...]:
            cells = [value for value in range(GRID) if value != gap]
            chunks = tuple(tuple(cells[i : i + 3]) for i in range(0, 69, 3))
            if any(chunk != tuple(range(chunk[0], chunk[0] + 3)) for chunk in chunks):
                raise GateError("noncontiguous boundary body")
            return tuple(chunk[0] for chunk in chunks)

        left, bottom = anchors(lg), anchors(bg)
        body = {(0, a + d) for a in left for d in range(3)} | {(a + d, 0) for a in bottom for d in range(3)}
        q = {(1, a + 1) for a in left} | {(a + 1, 1) for a in bottom}
        if len(body) != 138 or len(q) != 46 or body & q:
            raise GateError("invalid boundary pattern")
        result.append({"delta": delta, "left_gap": lg, "bottom_gap": bg, "body": body, "q": q})
    return tuple(result)


def _contact(pattern: Mapping[str, Any], w: int, h: int, x: int, y: int) -> tuple[int, int]:
    rectangle = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    hit = pattern["q"] & rectangle
    e = sum((qx in {x, x + w - 1} if qy == 1 else qy in {y, y + h - 1}) for qx, qy in hit)
    return len(hit), e


def _canonical(case: Mapping[str, Any]) -> str:
    return ",".join(str(case[key]) for key in ("w", "h", "x", "y", "delta", "a_delta", "e_delta"))


def _margin(value: int) -> str | None:
    if value == 1:
        return "1"
    if 2 <= value <= 5:
        return "2..5"
    if value >= 6:
        return ">=6"
    return None


def _ab(value: int) -> str:
    return "0" if value == 0 else "1..4" if value <= 4 else "5..12" if value <= 12 else ">=13"


def _eb(value: int) -> str:
    return "0" if value == 0 else "1" if value == 1 else ">=2"


def _rebuild_corpus(data: Mapping[str, Any], r1_sha: str) -> list[dict[str, Any]]:
    seed = hashlib.sha256(LABEL + bytes.fromhex(STRICT_SHA) + bytes.fromhex(r1_sha)).digest()
    patterns = _patterns()
    universe: list[dict[str, Any]] = []
    groups_delta: dict[int, list[dict[str, Any]]] = defaultdict(list)
    groups_margin: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    groups_contact: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for pattern in patterns:
        for x in range(1, 37):
            for y in range(1, 36):
                a, e = _contact(pattern, 34, 35, x, y)
                lhs = 1190 + -(-(580 - 34 - 35 + a // 2 + e) // 4)
                if lhs > 1320:
                    continue
                case = {"w": 34, "h": 35, "x": x, "y": y, "delta": pattern["delta"], "a_delta": a, "e_delta": e}
                canonical = _canonical(case)
                case.update(
                    {
                        "canonical_utf8": canonical,
                        "rank_hash_sha256": hashlib.sha256(seed + canonical.encode()).hexdigest(),
                    }
                )
                universe.append(case)
                groups_delta[pattern["delta"]].append(case)
                mx, my = _margin(min(x, 36 - x)), _margin(min(y, 35 - y))
                if mx is not None and my is not None:
                    groups_margin[(mx, my)].append(case)
                groups_contact[(_ab(a), _eb(e))].append(case)
    if len(universe) != 59_173:
        raise GateError("independent R1 universe count drifted")

    def rank(values: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            values,
            key=lambda candidate: (
                candidate["rank_hash_sha256"],
                candidate["canonical_utf8"],
            ),
        )

    selected: dict[str, dict[str, Any]] = {}
    for delta in range(47):
        case = rank(groups_delta[delta])[0]
        selected[case["canonical_utf8"]] = case
    for groups in (groups_margin, groups_contact):
        for key in sorted(groups):
            for case in rank(groups[key])[:2]:
                selected[case["canonical_utf8"]] = case
    for case in rank(universe):
        if len(selected) == 256:
            break
        selected.setdefault(case["canonical_utf8"], case)
    by_gap = {(p["left_gap"], p["bottom_gap"]): p for p in patterns}
    final: list[dict[str, Any]] = []
    for base_rank, original in enumerate(rank(list(selected.values()))):
        p = patterns[original["delta"]]
        transpose_p = by_gap[(p["bottom_gap"], p["left_gap"])]
        transpose = {
            "w": 35,
            "h": 34,
            "x": original["y"],
            "y": original["x"],
            "delta": transpose_p["delta"],
            "a_delta": original["a_delta"],
            "e_delta": original["e_delta"],
        }
        transpose["canonical_utf8"] = _canonical(transpose)
        transpose["rank_hash_sha256"] = hashlib.sha256(seed + transpose["canonical_utf8"].encode()).hexdigest()
        transpose_group_id = f"transpose_group_{base_rank:03d}"
        for variant, case in (("original", original), ("transpose", transpose)):
            case_index = len(final)
            record = dict(case)
            record.update(
                {
                    "case_index": case_index,
                    "case_id": f"case_{case_index:03d}",
                    "pair_id": f"pair_{case_index:03d}",
                    "transpose_group_id": transpose_group_id,
                    "base_rank": base_rank,
                    "variant": variant,
                }
            )
            final.append(record)
    actual = _arr(data.get("cases"), "corpus.cases")
    if len(actual) != 512:
        raise GateError("corpus case count drifted")
    compared = (
        "w",
        "h",
        "x",
        "y",
        "delta",
        "a_delta",
        "e_delta",
        "canonical_utf8",
        "rank_hash_sha256",
        "case_index",
        "case_id",
        "pair_id",
        "transpose_group_id",
        "base_rank",
        "variant",
    )
    for index, expected in enumerate(final):
        candidate = _obj(actual[index], f"cases[{index}]")
        if any(candidate.get(key) != expected[key] for key in compared):
            raise GateError(f"corpus selection/order mismatch at case {index}")
    if len({str(_obj(case, "case").get("pair_id")) for case in actual}) != 512:
        raise GateError("corpus control/treatment pair identities are not unique per case")
    if len({str(_obj(case, "case").get("transpose_group_id")) for case in actual}) != 256:
        raise GateError("corpus transpose symmetry-group count drifted")
    for base_rank in range(256):
        original = _obj(actual[2 * base_rank], "original case")
        transpose = _obj(actual[2 * base_rank + 1], "transpose case")
        if original.get("pair_id") == transpose.get("pair_id"):
            raise GateError("transpose pair reused a control/treatment pair identity")
        if original.get("transpose_group_id") != transpose.get("transpose_group_id"):
            raise GateError("transpose pair does not share its symmetry-group identity")
    return final


def _stencil(path: Path) -> dict[tuple[int, int], int]:
    data, _ = _load(path, "stencil")
    if data.get("schema") != STENCIL_SCHEMA or data.get("weight_units") != "doubled_integer":
        raise GateError("stencil schema drifted")
    orbits: dict[tuple[int, int], int] = {}
    for raw in _arr(data.get("orbits"), "stencil.orbits"):
        item = _obj(raw, "orbit")
        key = (_int(item.get("major_odd"), "major"), _int(item.get("minor_odd"), "minor"))
        if key in orbits:
            raise GateError("duplicate orbit")
        orbits[key] = _int(item.get("weight2"), "weight2")
    expanded = {}
    for dx in range(-8, 10):
        for dy in range(-8, 10):
            a, b = abs(2 * dx - 1), abs(2 * dy - 1)
            weight = orbits.get((max(a, b), min(a, b)), 0)
            if weight:
                expanded[(dx, dy)] = weight
    if len(orbits) != 14 or len(expanded) != 96 or sum(expanded.values()) != 792:
        raise GateError("stencil expansion drifted")
    return expanded


def _pb(terms: Iterable[tuple[int, int]], relation: str, rhs: int, category: str) -> PB:
    combined: Counter[int] = Counter()
    for variable, coefficient in terms:
        combined[variable] += coefficient
    return PB(tuple(sorted((v, c) for v, c in combined.items() if c)), relation, rhs, category)


def _expected(
    case: Mapping[str, Any],
    stencil: Mapping[tuple[int, int], int],
    model_scope: str,
) -> tuple[list[dict[str, Any]], list[PB], PB, dict[str, int]]:
    patterns = _patterns()
    w, h, x, y, selected = (_int(case[k], f"case.{k}") for k in ("w", "h", "x", "y", "delta"))
    contacts = {p["delta"]: _contact(p, w, h, x, y) for p in patterns}
    if contacts[selected] != (case.get("a_delta"), case.get("e_delta")):
        raise GateError("case q/e mismatch")
    variables = []
    for p in patterns:
        variables.append(
            {
                "id": len(variables) + 1,
                "name": f"b_delta_{p['delta']:02d}",
                "kind": "boundary_pattern",
                "delta": p["delta"],
                "left_gap": p["left_gap"],
                "bottom_gap": p["bottom_gap"],
            }
        )
    pole_ids = {}
    for qx in range(69):
        for qy in range(69):
            pole_ids[(qx, qy)] = len(variables) + 1
            variables.append(
                {"id": len(variables) + 1, "name": f"p_x_{qx:02d}_y_{qy:02d}", "kind": "pole_anchor", "x": qx, "y": qy}
            )
    count_ids = {}
    for k in range(9, 42):
        count_ids[k] = len(variables) + 1
        variables.append({"id": len(variables) + 1, "name": f"n_{k:02d}", "kind": "pole_count", "count": k})
    constraints = [
        _pb(((d + 1, 1) for d in range(47)), "=", 1, "pattern_exactly_one"),
        _pb(((v, 1) for v in count_ids.values()), "=", 1, "count_exactly_one"),
        _pb(
            [*((v, 1) for v in pole_ids.values()), *((v, -k) for k, v in count_ids.items())], "=", 0, "pole_count_link"
        ),
    ]
    if model_scope == "diagnostic_fixed_pattern":
        constraints.append(_pb(((selected + 1, 1),), "=", 1, "diagnostic_pattern_fix"))
    elif model_scope != "band_any_pattern":
        raise GateError("unsupported model scope")
    for delta, (a, e) in contacts.items():
        base = w * h + -(-(580 - w - h + a // 2 + e) // 4)
        for k, variable in count_ids.items():
            if base + 4 * (k - 9) > 1320:
                constraints.append(_pb(((delta + 1, -1), (variable, -1)), ">=", -1, "r1_count_exclusion"))
    rectangle = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    bodies = {(qx, qy): {(qx + dx, qy + dy) for dx in range(2) for dy in range(2)} for qx, qy in pole_ids}
    for anchor, body in bodies.items():
        if body & rectangle:
            constraints.append(_pb(((pole_ids[anchor], -1),), ">=", 0, "pole_rectangle_exclusion"))
    overlap = 0
    anchors = list(pole_ids)
    for index, first in enumerate(anchors):
        for second in anchors[index + 1 :]:
            if abs(first[0] - second[0]) <= 1 and abs(first[1] - second[1]) <= 1:
                overlap += 1
                constraints.append(_pb(((pole_ids[first], -1), (pole_ids[second], -1)), ">=", -1, "pole_pair_overlap"))
    if overlap != 18_632:
        raise GateError("overlap graph drifted")
    pattern_conflicts = 0
    for pattern in patterns:
        forbidden = pattern["body"] | pattern["q"]
        for anchor, body in bodies.items():
            if body & forbidden:
                pattern_conflicts += 1
                constraints.append(
                    _pb(((pattern["delta"] + 1, -1), (pole_ids[anchor], -1)), ">=", -1, "pattern_pole_conflict")
                )
    capacities = {}
    for anchor in anchors:
        capacities[anchor] = sum(
            weight
            for (dx, dy), weight in stencil.items()
            if 0 <= anchor[0] + dx < GRID
            and 0 <= anchor[1] + dy < GRID
            and (anchor[0] + dx, anchor[1] + dy) not in rectangle
        )
    halo = _pb(((pole_ids[a], capacities[a]) for a in anchors if capacities[a]), ">=", HALO_RHS2, "conditional_halo")
    counts = dict(Counter(item.category for item in constraints))
    counts.update(
        {
            "variables": 4_841,
            "control_constraints": len(constraints),
            "treatment_constraints": len(constraints) + 1,
            "pole_overlap_edges": overlap,
            "pattern_pole_conflicts": pattern_conflicts,
            "pole_count_min": 9,
            "pole_count_max": 41,
        }
    )
    return variables, constraints, halo, counts


HEADER = re.compile(r"^\* #variable= (\d+) #constraint= (\d+) #equal= (\d+) intsize= 64$")
TERM = re.compile(r"^([+-]\d+) x(\d+)$")


def _parse_opb(path: Path) -> tuple[Counter[str], dict[str, int]]:
    raw = path.resolve(strict=True).read_bytes()
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise GateError("OPB is not ASCII") from exc
    match = HEADER.fullmatch(lines[0]) if lines else None
    if match is None:
        raise GateError("OPB header malformed")
    parsed: list[PB] = []
    for line in lines[1:]:
        if line.startswith("*"):
            continue
        tokens = line.split()
        if len(tokens) < 5 or tokens[-1] != ";" or tokens[-3] not in {"=", ">="}:
            raise GateError("OPB constraint syntax malformed")
        relation, rhs = tokens[-3], int(tokens[-2])
        body = tokens[:-3]
        if len(body) % 2:
            raise GateError("OPB term token count malformed")
        terms = []
        for index in range(0, len(body), 2):
            term = TERM.fullmatch(f"{body[index]} {body[index + 1]}")
            if term is None:
                raise GateError("OPB term malformed")
            terms.append((int(term.group(2)), int(term.group(1))))
        parsed.append(PB(tuple(sorted(terms)), relation, rhs))
    header = {"variables": int(match.group(1)), "constraints": int(match.group(2)), "equal": int(match.group(3))}
    if header["constraints"] != len(parsed) or header["equal"] != sum(item.relation == "=" for item in parsed):
        raise GateError("OPB header counts do not match body")
    return Counter(item.key() for item in parsed), header


def _diff(expected: Counter[str], actual: Counter[str]) -> dict[str, Any]:
    missing, unexpected = expected - actual, actual - expected
    return {
        "missing": list(missing.elements())[:20],
        "missing_total": sum(missing.values()),
        "unexpected": list(unexpected.elements())[:20],
        "unexpected_total": sum(unexpected.values()),
    }


def _main(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    strict_record = _record(root / STRICT_PATH, root)
    if strict_record["sha256"] != STRICT_SHA:
        raise GateError("strict SHA drifted")
    admission, _ = _load(args.geometry_admission, "geometry admission")
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("status") != "PASS"
        or admission.get("corpus_errors") != []
    ):
        raise GateError("geometry admission not PASS")
    inputs = _obj(admission.get("inputs"), "admission.inputs")
    for key, value in inputs.items():
        _check_record(value, root, f"admission.inputs.{key}")
    stencil_path = _check_record(inputs.get("stencil"), root, "admission.inputs.stencil")
    stencil = _stencil(stencil_path)
    corpus, _ = _load(args.corpus, "corpus")
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA
        or corpus.get("status") != "PASS"
        or corpus.get("corpus_errors") != []
    ):
        raise GateError("corpus not PASS")
    r1_path = _check_record(corpus.get("r1_authoritative_translation_gate"), root, "corpus.r1_gate")
    r1, r1_raw = _load(r1_path, "R1 gate")
    if r1.get("schema_version") != R1_GATE_SCHEMA or r1.get("status") != "PASS" or r1.get("corpus_errors") != []:
        raise GateError("R1 gate not PASS")
    rebuilt_cases = _rebuild_corpus(corpus, hashlib.sha256(r1_raw).hexdigest())
    if not 0 <= args.case_index < 512:
        raise GateError("case index outside corpus")
    case = _obj(_arr(corpus.get("cases"), "cases")[args.case_index], "case")
    variables, control_expected, halo, counts = _expected(case, stencil, args.model_scope)
    treatment_expected = [*control_expected, halo]
    control_actual, control_header = _parse_opb(args.control_opb)
    treatment_actual, treatment_header = _parse_opb(args.treatment_opb)
    control_counter = Counter(item.key() for item in control_expected)
    treatment_counter = Counter(item.key() for item in treatment_expected)
    control_diff, treatment_diff = _diff(control_counter, control_actual), _diff(treatment_counter, treatment_actual)
    if any(control_diff[key] or treatment_diff[key] for key in ("missing_total", "unexpected_total")):
        raise GateError("OPB constraint multiset mismatch")
    if treatment_actual - control_actual != Counter({halo.key(): 1}) or control_actual - treatment_actual:
        raise GateError("paired arm diff is not exactly one halo constraint")
    expected_equal = 4 if args.model_scope == "diagnostic_fixed_pattern" else 3
    if control_header != {
        "variables": 4841,
        "constraints": len(control_expected),
        "equal": expected_equal,
    } or treatment_header != {"variables": 4841, "constraints": len(treatment_expected), "equal": expected_equal}:
        raise GateError("OPB headers drifted")
    control_map, control_map_raw = _load(args.control_var_map, "control var map")
    treatment_map, treatment_map_raw = _load(args.treatment_var_map, "treatment var map")
    expected_map_core = {
        "schema_version": VAR_MAP_SCHEMA,
        "status": "PASS",
        "model_schema_version": MODEL_SCHEMA,
        "model_scope": args.model_scope,
        "strict_instance_sha256": STRICT_SHA,
        "case": dict(case),
        "counts": counts,
        "variable_count": 4841,
        "variables": variables,
    }
    for name, varmap in (("control", control_map), ("treatment", treatment_map)):
        for key, value in expected_map_core.items():
            if varmap.get(key) != value:
                raise GateError(f"{name} var map mismatch: {key}")
    if control_map_raw != treatment_map_raw or control_map.get("paired_generation_sha256") != treatment_map.get(
        "paired_generation_sha256"
    ):
        raise GateError("paired variable maps are not byte-identical/bound")
    pair_id = control_map.get("paired_generation_sha256")
    for arm, meta_path, opb_path, map_path, expected_count in (
        ("control", args.control_meta, args.control_opb, args.control_var_map, len(control_expected)),
        ("treatment", args.treatment_meta, args.treatment_opb, args.treatment_var_map, len(treatment_expected)),
    ):
        meta, _ = _load(meta_path, f"{arm} metadata")
        if (
            meta.get("schema_version") != META_SCHEMA
            or meta.get("status") != "PASS"
            or meta.get("arm") != arm
            or meta.get("model_scope") != args.model_scope
            or meta.get("paired_generation_sha256") != pair_id
            or meta.get("counts") != counts
            or meta.get("constraint_count") != expected_count
        ):
            raise GateError(f"{arm} metadata scalar mismatch")
        if meta.get("proof_status") != "build_only_no_solver_or_proof_no_sat_or_unsat_claim":
            raise GateError(f"{arm} claim boundary drifted")
        outputs = _obj(meta.get("outputs"), f"{arm}.outputs")
        if dict(_obj(outputs.get("opb"), "opb record")) != _record(opb_path, root) or dict(
            _obj(outputs.get("var_map"), "map record")
        ) != _record(map_path, root):
            raise GateError(f"{arm} output hashes stale")
        if (
            dict(_obj(meta.get("strict_instance"), "meta.strict")) != strict_record
            or dict(_obj(meta.get("geometry_admission"), "meta.admission")) != _record(args.geometry_admission, root)
            or dict(_obj(meta.get("corpus_manifest"), "meta.corpus")) != _record(args.corpus, root)
        ):
            raise GateError(f"{arm} provenance mismatch")
    result = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "case_index": args.case_index,
        "model_scope": args.model_scope,
        "case": dict(rebuilt_cases[args.case_index]),
        "paired_generation_sha256": pair_id,
        "gate_source": _record(Path(__file__), root),
        "argv": [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)],
        "inputs": {
            "geometry_admission": _record(args.geometry_admission, root),
            "stencil": _record(stencil_path, root),
            "corpus_manifest": _record(args.corpus, root),
            "r1_translation_gate": _record(r1_path, root),
            "control_opb": _record(args.control_opb, root),
            "control_metadata": _record(args.control_meta, root),
            "control_var_map": _record(args.control_var_map, root),
            "treatment_opb": _record(args.treatment_opb, root),
            "treatment_metadata": _record(args.treatment_meta, root),
            "treatment_var_map": _record(args.treatment_var_map, root),
        },
        "counts": counts,
        "checks": {
            "strict_current": True,
            "geometry_admission_current_pass": True,
            "stencil_rebuilt": True,
            "r1_gate_current_pass": True,
            "corpus_512_rebuilt": True,
            "variable_maps_exact_and_identical": True,
            "control_constraint_multiset_exact": True,
            "treatment_constraint_multiset_exact": True,
            "paired_diff_exactly_one_halo": True,
            "metadata_hashes_current": True,
        },
        "constraint_diff": {"control": control_diff, "treatment": treatment_diff},
        "paired_diff": {"added": [halo.key()], "removed": [], "exactly_one_conditional_halo": True},
        "missing": [],
        "unexpected": [],
        "corpus_errors": [],
        "proof_status": "translation_gate_only_no_solver_or_proof_no_sat_or_unsat_claim",
    }
    _write(args.output.resolve(), result)
    print(
        json.dumps(
            {"status": "PASS", "case_index": args.case_index, "output": str(args.output.resolve())}, sort_keys=True
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
    for arm in ("control", "treatment"):
        parser.add_argument(f"--{arm}-opb", type=Path, required=True)
        parser.add_argument(f"--{arm}-meta", type=Path, required=True)
        parser.add_argument(f"--{arm}-var-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return _main(_parser().parse_args(argv), argv)


if __name__ == "__main__":
    raise SystemExit(main())
