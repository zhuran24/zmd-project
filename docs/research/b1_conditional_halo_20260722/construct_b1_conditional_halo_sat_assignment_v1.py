#!/usr/bin/env python3
"""Construct one dense assignment for a paired B1 conditional-halo case.

This research-only constructor does not establish SAT by itself.  A successful
output is deliberately shaped for the separate
``check_b1_conditional_halo_sat_assignment_v1.py`` checker, which must replay
the model semantics before a CHECKED_SAT result may be recorded.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ASSIGNMENT_SCHEMA = "b1_conditional_halo_full_assignment_v1"
CONSTRUCTION_SCHEMA = "b1_conditional_halo_sat_construction_v1"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
ADMISSION_SCHEMA = "b1_conditional_halo_geometry_admission_v1"
STENCIL_SCHEMA = "b1_conditional_halo_stencil_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
VAR_MAP_SCHEMA = "b1_conditional_halo_fixed_rectangle_var_map_v1"
STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
GRID = 70
VARIABLE_COUNT = 4_841
POLE_COUNT = 9
HALO_RHS2 = 6_650
UNKNOWN_EXIT = 3


class ConstructionError(ValueError):
    """An input or construction invariant failed closed."""


@dataclass(frozen=True, slots=True)
class Candidate:
    capacity2: int
    x: int
    y: int
    variable_id: int

    @property
    def anchor(self) -> tuple[int, int]:
        return self.x, self.y


def _reject(value: str) -> Any:
    raise ConstructionError(f"non-finite JSON number forbidden: {value}")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ConstructionError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load(path: Path, field: str) -> tuple[Mapping[str, Any], bytes]:
    raw = path.resolve(strict=True).read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConstructionError(f"{field} parse failure: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ConstructionError(f"{field} root must be an object")
    return value, raw


def _obj(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConstructionError(f"{field} must be an object")
    return value


def _arr(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConstructionError(f"{field} must be an array")
    return value


def _int(value: Any, field: str) -> int:
    if type(value) is not int:
        raise ConstructionError(f"{field} must be an exact integer")
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
        raise ConstructionError(f"not a regular file: {resolved}")
    raw = resolved.read_bytes()
    return {
        "path": _display(resolved, root),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _check_record(value: Any, path: Path, root: Path, field: str) -> None:
    if dict(_obj(value, field)) != _record(path, root):
        raise ConstructionError(f"{field} byte record is stale")


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)


def _anchors(gap: int) -> tuple[int, ...]:
    if gap not in range(0, GRID, 3):
        raise ConstructionError("boundary gap is outside the 47-pattern family")
    cells = [value for value in range(GRID) if value != gap]
    chunks = tuple(tuple(cells[index : index + 3]) for index in range(0, 69, 3))
    if any(chunk != tuple(range(chunk[0], chunk[0] + 3)) for chunk in chunks):
        raise ConstructionError("boundary chunk is not contiguous")
    return tuple(chunk[0] for chunk in chunks)


def _patterns() -> tuple[dict[str, Any], ...]:
    gaps = tuple(range(0, GRID, 3))
    gap_pairs = tuple((0, gap) for gap in gaps) + tuple((gap, 0) for gap in gaps[1:])
    result = []
    for delta, (left_gap, bottom_gap) in enumerate(gap_pairs):
        left, bottom = _anchors(left_gap), _anchors(bottom_gap)
        body = {(0, anchor + offset) for anchor in left for offset in range(3)} | {
            (anchor + offset, 0) for anchor in bottom for offset in range(3)
        }
        q_cells = {(1, anchor + 1) for anchor in left} | {(anchor + 1, 1) for anchor in bottom}
        if len(body) != 138 or len(q_cells) != 46 or body & q_cells:
            raise ConstructionError("boundary-pattern geometry drifted")
        result.append({"delta": delta, "body": body, "q": q_cells})
    if len(result) != 47:
        raise ConstructionError("boundary-pattern count drifted")
    return tuple(result)


def _contact(pattern: Mapping[str, Any], rectangle: set[tuple[int, int]]) -> tuple[int, int]:
    hit = pattern["q"] & rectangle
    xs = {cell[0] for cell in rectangle}
    ys = {cell[1] for cell in rectangle}
    x_min, x_max, y_min, y_max = min(xs), max(xs), min(ys), max(ys)
    endpoints = sum((qx in {x_min, x_max} if qy == 1 else qy in {y_min, y_max}) for qx, qy in hit)
    return len(hit), endpoints


def _expanded_stencil(data: Mapping[str, Any]) -> dict[tuple[int, int], int]:
    if data.get("schema") != STENCIL_SCHEMA or data.get("weight_units") != "doubled_integer":
        raise ConstructionError("stencil schema or units drifted")
    if data.get("pole_anchor") != {
        "body_offsets": [[0, 0], [0, 1], [1, 0], [1, 1]],
        "x_domain": [0, 68],
        "y_domain": [0, 68],
    }:
        raise ConstructionError("stencil pole-anchor semantics drifted")
    conditional = _obj(data.get("conditional_halo"), "stencil.conditional_halo")
    if conditional.get("pole_quantifier") != "all_selected_poles" or conditional.get("rhs_doubled") != HALO_RHS2:
        raise ConstructionError("stencil conditional-halo statement drifted")
    expected = _obj(data.get("expected"), "stencil.expected")
    if (
        expected.get("orbit_count") != 14
        or expected.get("support_cell_count") != 96
        or expected.get("total_weight2") != 792
        or expected.get("minimum_selected_poles") != POLE_COUNT
    ):
        raise ConstructionError("stencil expected totals drifted")
    orbit_weights: dict[tuple[int, int], int] = {}
    for index, raw in enumerate(_arr(data.get("orbits"), "stencil.orbits")):
        item = _obj(raw, f"stencil.orbits[{index}]")
        key = (_int(item.get("major_odd"), "major_odd"), _int(item.get("minor_odd"), "minor_odd"))
        weight = _int(item.get("weight2"), "weight2")
        if key in orbit_weights or key[0] < key[1] or min(key[1], weight) <= 0:
            raise ConstructionError("malformed or duplicate stencil orbit")
        orbit_weights[key] = weight
    expanded: dict[tuple[int, int], int] = {}
    for dx in range(-8, 10):
        for dy in range(-8, 10):
            first, second = abs(2 * dx - 1), abs(2 * dy - 1)
            weight = orbit_weights.get((max(first, second), min(first, second)), 0)
            if weight:
                expanded[(dx, dy)] = weight
    if len(orbit_weights) != 14 or len(expanded) != 96 or sum(expanded.values()) != 792:
        raise ConstructionError("expanded stencil totals drifted")
    return expanded


def _canonical_corpus(data: Mapping[str, Any], root: Path) -> Sequence[Any]:
    if (
        data.get("schema_version") != CORPUS_SCHEMA
        or data.get("status") != "PASS"
        or data.get("corpus_errors") != []
        or data.get("case_count") != 512
        or data.get("solver_results_included") is not False
        or data.get("manifest_state") != "BUILT_BEFORE_RESULTS"
    ):
        raise ConstructionError("diagnostic corpus is not the admitted 512-case pre-result corpus")
    selection = _obj(data.get("selection"), "corpus.selection")
    if selection.get("control_treatment_pairs") != 512 or selection.get("transpose_symmetry_groups") != 256:
        raise ConstructionError("diagnostic corpus completion counts drifted")
    strict_path = root / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    if _record(strict_path, root)["sha256"] != STRICT_SHA256:
        raise ConstructionError("strict instance SHA drifted")
    _check_record(data.get("strict_instance"), strict_path, root, "corpus.strict_instance")
    cases = _arr(data.get("cases"), "corpus.cases")
    if len(cases) != 512:
        raise ConstructionError("diagnostic corpus case array is incomplete")
    transpose_groups: dict[str, list[str]] = {}
    for index, raw in enumerate(cases):
        case = _obj(raw, f"corpus.cases[{index}]")
        pair_id = case.get("pair_id")
        group_id = case.get("transpose_group_id")
        if case.get("case_index") != index or pair_id != f"pair_{index:03d}":
            raise ConstructionError("diagnostic corpus pair identities are not canonical and unique")
        if type(group_id) is not str:
            raise ConstructionError("diagnostic transpose-group identity is malformed")
        transpose_groups.setdefault(group_id, []).append(str(case.get("variant")))
    expected_groups = {f"transpose_group_{index:03d}" for index in range(256)}
    if set(transpose_groups) != expected_groups or any(
        variants != ["original", "transpose"] for variants in transpose_groups.values()
    ):
        raise ConstructionError("diagnostic transpose groups are not complete ordered pairs")
    return cases


def _model_inputs(
    args: argparse.Namespace,
    root: Path,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], dict[tuple[int, int], int]]:
    admission, _ = _load(args.geometry_admission, "geometry admission")
    stencil_data, _ = _load(args.stencil, "stencil")
    corpus, _ = _load(args.corpus, "diagnostic corpus")
    metadata, _ = _load(args.metadata, "metadata")
    var_map, _ = _load(args.var_map, "variable map")
    if (
        admission.get("schema_version") != ADMISSION_SCHEMA
        or admission.get("status") != "PASS"
        or admission.get("scope") != "geometry_only_pre_encoder"
        or admission.get("corpus_errors") != []
    ):
        raise ConstructionError("geometry admission is absent or not PASS")
    halo = _obj(admission.get("conditional_halo"), "admission.conditional_halo")
    if halo.get("quantifier") != "all_selected_poles" or halo.get("rhs_doubled") != HALO_RHS2:
        raise ConstructionError("admitted conditional-halo statement drifted")
    inputs = _obj(admission.get("inputs"), "admission.inputs")
    _check_record(inputs.get("stencil"), args.stencil, root, "admission.inputs.stencil")
    expanded = _expanded_stencil(stencil_data)
    cases = _canonical_corpus(corpus, root)
    if not 0 <= args.case_index < len(cases):
        raise ConstructionError("case index outside canonical corpus")
    case = _obj(cases[args.case_index], f"corpus.cases[{args.case_index}]")
    if (
        metadata.get("schema_version") != META_SCHEMA
        or metadata.get("status") != "PASS"
        or metadata.get("arm") != args.arm
        or metadata.get("model_scope") != "diagnostic_fixed_pattern"
    ):
        raise ConstructionError("metadata schema, arm, status, or scope drifted")
    if (
        var_map.get("schema_version") != VAR_MAP_SCHEMA
        or var_map.get("status") != "PASS"
        or var_map.get("model_scope") != "diagnostic_fixed_pattern"
        or var_map.get("variable_count") != VARIABLE_COUNT
    ):
        raise ConstructionError("variable-map schema, status, scope, or size drifted")
    if metadata.get("case") != case or var_map.get("case") != case:
        raise ConstructionError("metadata/variable-map case is not the selected corpus case")
    if metadata.get("paired_generation_sha256") != var_map.get("paired_generation_sha256"):
        raise ConstructionError("paired-generation identity drifted")
    _check_record(metadata.get("geometry_admission"), args.geometry_admission, root, "metadata.geometry_admission")
    _check_record(metadata.get("stencil"), args.stencil, root, "metadata.stencil")
    _check_record(metadata.get("corpus_manifest"), args.corpus, root, "metadata.corpus_manifest")
    outputs = _obj(metadata.get("outputs"), "metadata.outputs")
    _check_record(outputs.get("opb"), args.opb, root, "metadata.outputs.opb")
    _check_record(outputs.get("var_map"), args.var_map, root, "metadata.outputs.var_map")
    return case, metadata, var_map, expanded


def _variables(var_map: Mapping[str, Any]) -> tuple[dict[int, Mapping[str, Any]], dict[tuple[int, int], int], int]:
    variables_raw = _arr(var_map.get("variables"), "var_map.variables")
    if len(variables_raw) != VARIABLE_COUNT:
        raise ConstructionError("variable map is not a full 4841-variable map")
    variables: dict[int, Mapping[str, Any]] = {}
    pole_ids: dict[tuple[int, int], int] = {}
    pole_domain = {(x, y) for x in range(69) for y in range(69)}
    count_nine = 0
    kind_counts: dict[str, int] = {}
    for expected_id, raw in enumerate(variables_raw, 1):
        item = _obj(raw, f"variables[{expected_id - 1}]")
        variable_id = _int(item.get("id"), "variable id")
        kind = item.get("kind")
        if variable_id != expected_id or type(kind) is not str:
            raise ConstructionError("variable map is not dense, ordered, and typed")
        variables[variable_id] = item
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        if kind == "boundary_pattern":
            if item.get("delta") != expected_id - 1 or not 1 <= variable_id <= 47:
                raise ConstructionError("boundary-pattern variable mapping drifted")
        elif kind == "pole_anchor":
            anchor = (_int(item.get("x"), "pole x"), _int(item.get("y"), "pole y"))
            if anchor in pole_ids or anchor not in pole_domain:
                raise ConstructionError("pole-anchor variable mapping drifted")
            pole_ids[anchor] = variable_id
        elif kind == "pole_count":
            count = _int(item.get("count"), "pole count")
            if count == POLE_COUNT:
                count_nine = variable_id
        else:
            raise ConstructionError(f"unsupported variable kind: {kind!r}")
    if kind_counts != {"boundary_pattern": 47, "pole_anchor": 4_761, "pole_count": 33}:
        raise ConstructionError("variable kind counts drifted")
    if set(pole_ids) != pole_domain or count_nine == 0:
        raise ConstructionError("pole or count-nine variable domain is incomplete")
    return variables, pole_ids, count_nine


def _compatible(first: Candidate, second: Candidate) -> bool:
    return abs(first.x - second.x) > 1 or abs(first.y - second.y) > 1


def _greedy(candidates: Sequence[Candidate]) -> list[Candidate]:
    selected: list[Candidate] = []
    for candidate in candidates:
        if all(_compatible(candidate, previous) for previous in selected):
            selected.append(candidate)
            if len(selected) == POLE_COUNT:
                return selected
    return selected


def _bounded_search(candidates: Sequence[Candidate], node_limit: int) -> tuple[list[Candidate] | None, int, bool]:
    selected: list[Candidate] = []
    nodes = 0
    exhausted = False

    def visit(start: int, score: int) -> list[Candidate] | None:
        nonlocal nodes, exhausted
        nodes += 1
        if nodes > node_limit:
            exhausted = True
            return None
        needed = POLE_COUNT - len(selected)
        if needed == 0:
            return list(selected) if score >= HALO_RHS2 else None
        if len(candidates) - start < needed:
            return None
        optimistic = score + sum(candidate.capacity2 for candidate in candidates[start : start + needed])
        if optimistic < HALO_RHS2:
            return None
        last = len(candidates) - needed
        for index in range(start, last + 1):
            candidate = candidates[index]
            remaining_best = sum(item.capacity2 for item in candidates[index + 1 : index + needed])
            if score + candidate.capacity2 + remaining_best < HALO_RHS2:
                break
            if not all(_compatible(candidate, previous) for previous in selected):
                continue
            selected.append(candidate)
            result = visit(index + 1, score + candidate.capacity2)
            selected.pop()
            if result is not None or exhausted:
                return result
        return None

    return visit(0, 0), min(nodes, node_limit), exhausted


def _construct(
    case: Mapping[str, Any],
    var_map: Mapping[str, Any],
    stencil: Mapping[tuple[int, int], int],
    node_limit: int,
) -> tuple[list[int] | None, dict[str, Any]]:
    _, pole_ids, count_nine = _variables(var_map)
    w, h, x, y, delta = (_int(case.get(key), f"case.{key}") for key in ("w", "h", "x", "y", "delta"))
    if (w, h) not in {(34, 35), (35, 34)} or w * h != 1_190:
        raise ConstructionError("case is outside the locked ceiling dimensions")
    if not (1 <= x <= GRID - w and 1 <= y <= GRID - h and 0 <= delta < 47):
        raise ConstructionError("fixed rectangle or selected delta is outside its domain")
    rectangle = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
    pattern = _patterns()[delta]
    if _contact(pattern, rectangle) != (case.get("a_delta"), case.get("e_delta")):
        raise ConstructionError("case contact counts disagree with rebuilt boundary geometry")
    base = w * h + -(
        -(580 - w - h + _int(case.get("a_delta"), "a_delta") // 2 + _int(case.get("e_delta"), "e_delta")) // 4
    )
    if base > 1_320:
        raise ConstructionError("count-nine assignment violates the R1 eligibility condition")
    forbidden = pattern["body"] | pattern["q"]
    candidates = []
    for (qx, qy), variable_id in pole_ids.items():
        body = {(qx + dx, qy + dy) for dx in range(2) for dy in range(2)}
        if body & rectangle or body & forbidden:
            continue
        capacity2 = sum(
            weight
            for (dx, dy), weight in stencil.items()
            if 0 <= qx + dx < GRID and 0 <= qy + dy < GRID and (qx + dx, qy + dy) not in rectangle
        )
        candidates.append(Candidate(capacity2, qx, qy, variable_id))
    ordered = sorted(candidates, key=lambda item: (-item.capacity2, item.x, item.y))
    selected = _greedy(ordered)
    method = "capacity_descending_greedy"
    nodes = 0
    exhausted = False
    if len(selected) != POLE_COUNT or sum(item.capacity2 for item in selected) < HALO_RHS2:
        parity_attempts = []
        for x_parity in range(2):
            for y_parity in range(2):
                attempt = _greedy([item for item in ordered if item.x % 2 == x_parity and item.y % 2 == y_parity])
                if len(attempt) == POLE_COUNT:
                    parity_attempts.append(attempt)
        if parity_attempts:
            selected = max(
                parity_attempts,
                key=lambda attempt: (sum(item.capacity2 for item in attempt), tuple((-x.x, -x.y) for x in attempt)),
            )
            method = "best_fixed_parity_greedy"
    if len(selected) != POLE_COUNT or sum(item.capacity2 for item in selected) < HALO_RHS2:
        result, nodes, exhausted = _bounded_search(ordered, node_limit)
        selected = [] if result is None else result
        method = "bounded_depth_first_search"
    diagnostics = {
        "candidate_count": len(ordered),
        "search_method": method,
        "bounded_search_node_limit": node_limit,
        "bounded_search_nodes": nodes,
        "bounded_search_limit_reached": exhausted,
        "required_poles": POLE_COUNT,
        "halo_rhs2": HALO_RHS2,
    }
    if len(selected) != POLE_COUNT or sum(item.capacity2 for item in selected) < HALO_RHS2:
        diagnostics.update({"selected_poles": len(selected), "halo_lhs2": sum(item.capacity2 for item in selected)})
        return None, diagnostics
    selected_sorted = sorted(selected, key=lambda item: (item.x, item.y))
    if any(
        not _compatible(first, second)
        for index, first in enumerate(selected_sorted)
        for second in selected_sorted[index + 1 :]
    ):
        raise ConstructionError("internal selection overlap invariant failed")
    values = [0] * VARIABLE_COUNT
    values[delta] = 1
    for candidate in selected_sorted:
        values[candidate.variable_id - 1] = 1
    values[count_nine - 1] = 1
    diagnostics.update(
        {
            "selected_poles": len(selected_sorted),
            "selected_anchors": [[item.x, item.y] for item in selected_sorted],
            "selected_capacity2": [item.capacity2 for item in selected_sorted],
            "halo_lhs2": sum(item.capacity2 for item in selected_sorted),
            "r1_count_lhs": base,
        }
    )
    return values, diagnostics


def _run(args: argparse.Namespace, argv: Sequence[str] | None) -> int:
    root = args.project_root.resolve(strict=True)
    expected_root = Path(__file__).resolve().parents[3]
    if root != expected_root:
        raise ConstructionError("--project-root must identify this isolated worktree")
    output = args.output.resolve(strict=False)
    if output.exists():
        raise FileExistsError("output already exists; construction is no-overwrite")
    if args.node_limit <= 0:
        raise ConstructionError("--node-limit must be positive")
    case, metadata, var_map, stencil = _model_inputs(args, root)
    values, diagnostics = _construct(case, var_map, stencil, args.node_limit)
    common = {
        "construction_schema_version": CONSTRUCTION_SCHEMA,
        "case_index": args.case_index,
        "case_id": case.get("case_id"),
        "pair_id": case.get("pair_id"),
        "arm": args.arm,
        "paired_generation_sha256": metadata.get("paired_generation_sha256"),
        "diagnostics": diagnostics,
        "inputs": {
            "geometry_admission": _record(args.geometry_admission, root),
            "stencil": _record(args.stencil, root),
            "corpus": _record(args.corpus, root),
            "opb": _record(args.opb, root),
            "metadata": _record(args.metadata, root),
            "var_map": _record(args.var_map, root),
        },
        "constructor_source": _record(Path(__file__), root),
        "argv": [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)],
        "claim_boundary": [
            "construction candidate only; independent assignment checking is required for CHECKED_SAT",
            "relaxed fixed-geometry diagnostic model only; not a factory-layout witness or attainability claim",
            "does not establish a new upper bound or global optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
    }
    if values is None:
        payload = {
            "schema_version": CONSTRUCTION_SCHEMA,
            "status": "UNKNOWN",
            "values": None,
            **common,
        }
        _write(output, payload)
        print(json.dumps({"status": "UNKNOWN", "case_index": args.case_index}, sort_keys=True))
        return UNKNOWN_EXIT
    payload = {
        "schema_version": ASSIGNMENT_SCHEMA,
        "construction_status": "CONSTRUCTED_REQUIRES_INDEPENDENT_CHECK",
        "opb_sha256": _record(args.opb, root)["sha256"],
        "values": values,
        **common,
    }
    _write(output, payload)
    print(
        json.dumps(
            {
                "status": "CONSTRUCTED_REQUIRES_INDEPENDENT_CHECK",
                "case_index": args.case_index,
                "arm": args.arm,
                "halo_lhs2": diagnostics["halo_lhs2"],
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--stencil", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--case-index", type=int, required=True)
    parser.add_argument("--arm", choices=("control", "treatment"), required=True)
    parser.add_argument("--opb", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--var-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node-limit", type=int, default=250_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args, argv)
    except (ConstructionError, FileExistsError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
