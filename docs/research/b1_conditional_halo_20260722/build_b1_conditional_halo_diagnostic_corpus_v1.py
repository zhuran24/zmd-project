#!/usr/bin/env python3
"""Build the deterministic 512-case B1 conditional-halo diagnostic corpus."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
LABEL = b"B1_R2_CONDITIONAL_HALO_DIAGNOSTIC_V1"
STRICT_RELATIVE_PATH = Path("docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json")
STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
R1_GATE_SCHEMA = "b1_q_membrane_halo_band_translation_gate_v1"
GRID = 70
BASE_WIDTH = 34
BASE_HEIGHT = 35
EXPECTED_UNIVERSE = 59_173
BASE_CASES = 256
FINAL_CASES = 512


class CorpusError(ValueError):
    """The bound evidence or deterministic corpus failed closed."""


def _reject_constant(value: str) -> Any:
    raise CorpusError(f"non-finite JSON number is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json(raw: bytes, field: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusError(f"{field} JSON parse failure: {exc}") from exc


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CorpusError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CorpusError(f"{field} must be an array")
    return value


def _integer(value: Any, field: str) -> int:
    if type(value) is not int:
        raise CorpusError(f"{field} must be an exact integer")
    return int(value)


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _snapshot(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise CorpusError(f"not a regular file: {resolved}")
    raw = resolved.read_bytes()
    return {
        "path": _display(resolved, root),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _verify_record(record: Any, root: Path, field: str) -> None:
    value = _object(record, field)
    if set(value) != {"path", "sha256", "size_bytes"}:
        raise CorpusError(f"{field} snapshot key set mismatch")
    path = value.get("path")
    digest = value.get("sha256")
    size = value.get("size_bytes")
    if type(path) is not str or not path:
        raise CorpusError(f"{field}.path must be a nonempty string")
    if type(digest) is not str or len(digest) != 64:
        raise CorpusError(f"{field}.sha256 is malformed")
    if type(size) is not int or size < 0:
        raise CorpusError(f"{field}.size_bytes is malformed")
    actual = _snapshot(root / path, root)
    if actual != dict(value):
        raise CorpusError(f"{field} is stale or does not match current bytes")


def _validate_strict(root: Path) -> dict[str, Any]:
    record = _snapshot(root / STRICT_RELATIVE_PATH, root)
    if record["sha256"] != STRICT_SHA256:
        raise CorpusError("strict instance SHA256 drifted")
    payload = _object(_load_json((root / STRICT_RELATIVE_PATH).read_bytes(), "strict"), "strict")
    grid = _object(payload.get("grid"), "strict.grid")
    if (_integer(grid.get("width"), "grid.width"), _integer(grid.get("height"), "grid.height")) != (
        GRID,
        GRID,
    ):
        raise CorpusError("strict grid is not 70x70")
    return record


def _validate_r1_gate(path: Path, root: Path) -> tuple[dict[str, Any], str]:
    record = _snapshot(path, root)
    raw = path.resolve(strict=True).read_bytes()
    gate = _object(_load_json(raw, "R1 translation gate"), "R1 translation gate")
    if gate.get("schema_version") != R1_GATE_SCHEMA or gate.get("status") != "PASS":
        raise CorpusError("R1 authoritative translation gate is not PASS")
    if gate.get("corpus_errors") != []:
        raise CorpusError("R1 translation gate corpus_errors is not empty")
    strict = _object(gate.get("strict_instance"), "R1.strict_instance")
    if strict.get("sha256") != STRICT_SHA256:
        raise CorpusError("R1 translation gate strict SHA mismatch")
    counts = _object(gate.get("counts"), "R1.counts")
    if _integer(counts.get("surviving_pairs"), "R1 surviving_pairs") != 118_346:
        raise CorpusError("R1 surviving-pair total drifted")
    band = _object(gate.get("band_scan"), "R1.band_scan")
    per_orientation = _object(band.get("surviving_pairs_by_orientation"), "R1 surviving pairs by orientation")
    if dict(per_orientation) != {"34x35": EXPECTED_UNIVERSE, "35x34": EXPECTED_UNIVERSE}:
        raise CorpusError("R1 ceiling orientation survivor counts drifted")
    if gate.get("proof_status") != "translation_gate_only_no_solver_or_proof_run_no_unsat_claim":
        raise CorpusError("R1 gate proof-status boundary drifted")
    for key, snapshot in _object(gate.get("translation_inputs"), "R1.translation_inputs").items():
        _verify_record(snapshot, root, f"R1.translation_inputs.{key}")
    return record, hashlib.sha256(raw).hexdigest()


def _edge_anchors(gap: int) -> tuple[int, ...]:
    if gap not in range(0, GRID, 3):
        raise CorpusError(f"illegal boundary gap: {gap}")
    cells = [coordinate for coordinate in range(GRID) if coordinate != gap]
    chunks = tuple(tuple(cells[index : index + 3]) for index in range(0, len(cells), 3))
    if len(chunks) != 23 or any(chunk != tuple(range(chunk[0], chunk[0] + 3)) for chunk in chunks):
        raise CorpusError(f"gap {gap} does not form 23 contiguous boundary bodies")
    return tuple(chunk[0] for chunk in chunks)


def _patterns() -> tuple[dict[str, Any], ...]:
    gaps = tuple(range(0, GRID, 3))
    pairs = tuple((0, gap) for gap in gaps) + tuple((gap, 0) for gap in gaps[1:])
    result: list[dict[str, Any]] = []
    for delta, (left_gap, bottom_gap) in enumerate(pairs):
        left = _edge_anchors(left_gap)
        bottom = _edge_anchors(bottom_gap)
        left_body = {(0, anchor + offset) for anchor in left for offset in range(3)}
        bottom_body = {(anchor + offset, 0) for anchor in bottom for offset in range(3)}
        left_access = tuple(anchor + 1 for anchor in left)
        bottom_access = tuple(anchor + 1 for anchor in bottom)
        q_cells = {(1, value) for value in left_access} | {(value, 1) for value in bottom_access}
        if left_body & bottom_body or len(q_cells) != 46:
            raise CorpusError(f"boundary pattern {delta} is not a legal 46-Q-cell pattern")
        result.append(
            {
                "delta": delta,
                "left_gap": left_gap,
                "bottom_gap": bottom_gap,
                "left_access": left_access,
                "bottom_access": bottom_access,
            }
        )
    if len(result) != 47:
        raise CorpusError("boundary pattern count is not 47")
    return tuple(result)


def _contact(pattern: Mapping[str, Any], w: int, h: int, x: int, y: int) -> tuple[int, int]:
    count = 0
    endpoints = 0
    if x == 1:
        low, high = y, y + h - 1
        for coordinate in pattern["left_access"]:
            if low <= coordinate <= high:
                count += 1
                endpoints += coordinate in {low, high}
    if y == 1:
        low, high = x, x + w - 1
        for coordinate in pattern["bottom_access"]:
            if low <= coordinate <= high:
                count += 1
                endpoints += coordinate in {low, high}
    return count, endpoints


def _eligible(w: int, h: int, a_delta: int, e_delta: int) -> bool:
    numerator = 580 - w - h + a_delta // 2 + e_delta
    return w * h + -(-numerator // 4) <= 1_320


def _canonical(case: Mapping[str, Any]) -> str:
    return ",".join(str(case[key]) for key in ("w", "h", "x", "y", "delta", "a_delta", "e_delta"))


def _margin_bin(value: int) -> str | None:
    if value == 1:
        return "1"
    if 2 <= value <= 5:
        return "2..5"
    if value >= 6:
        return ">=6"
    return None


def _a_bin(value: int) -> str:
    if value == 0:
        return "0"
    if value <= 4:
        return "1..4"
    if value <= 12:
        return "5..12"
    return ">=13"


def _e_bin(value: int) -> str:
    if value == 0:
        return "0"
    if value == 1:
        return "1"
    return ">=2"


def _ranked(cases: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(cases, key=lambda case: (case["rank_hash_sha256"], case["canonical_utf8"]))


def _build_cases(seed_digest: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    patterns = _patterns()
    universe: list[dict[str, Any]] = []
    by_delta: dict[int, list[dict[str, Any]]] = defaultdict(list)
    by_margin: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_contact: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for pattern in patterns:
        for x in range(1, GRID - BASE_WIDTH + 1):
            for y in range(1, GRID - BASE_HEIGHT + 1):
                a_delta, e_delta = _contact(pattern, BASE_WIDTH, BASE_HEIGHT, x, y)
                if not _eligible(BASE_WIDTH, BASE_HEIGHT, a_delta, e_delta):
                    continue
                case: dict[str, Any] = {
                    "w": BASE_WIDTH,
                    "h": BASE_HEIGHT,
                    "x": x,
                    "y": y,
                    "delta": pattern["delta"],
                    "a_delta": a_delta,
                    "e_delta": e_delta,
                }
                canonical = _canonical(case)
                case["canonical_utf8"] = canonical
                case["rank_hash_sha256"] = hashlib.sha256(seed_digest + canonical.encode("utf-8")).hexdigest()
                universe.append(case)
                by_delta[pattern["delta"]].append(case)
                margin_x = _margin_bin(min(x, GRID - BASE_WIDTH - x))
                margin_y = _margin_bin(min(y, GRID - BASE_HEIGHT - y))
                if margin_x is not None and margin_y is not None:
                    by_margin[(margin_x, margin_y)].append(case)
                by_contact[(_a_bin(a_delta), _e_bin(e_delta))].append(case)
    if len(universe) != EXPECTED_UNIVERSE or set(by_delta) != set(range(47)):
        raise CorpusError(f"R1-eligible canonical universe drifted: {len(universe)}")

    selected: dict[str, dict[str, Any]] = {}
    reasons: dict[str, set[str]] = defaultdict(set)

    def take(group: Sequence[dict[str, Any]], count: int, reason: str) -> None:
        if not group:
            raise CorpusError(f"selection stratum unexpectedly empty: {reason}")
        for case in _ranked(group)[:count]:
            selected[case["canonical_utf8"]] = case
            reasons[case["canonical_utf8"]].add(reason)

    for delta in range(47):
        take(by_delta[delta], 1, f"delta:{delta}")
    for key in sorted(by_margin):
        take(by_margin[key], 2, f"margin:{key[0]}:{key[1]}")
    for key in sorted(by_contact):
        take(by_contact[key], 2, f"contact:{key[0]}:{key[1]}")
    for case in _ranked(universe):
        if len(selected) >= BASE_CASES:
            break
        canonical = case["canonical_utf8"]
        if canonical not in selected:
            selected[canonical] = case
            reasons[canonical].add("global_hash_fill")
    if len(selected) != BASE_CASES:
        raise CorpusError(f"base corpus size is {len(selected)}, expected {BASE_CASES}")

    pattern_by_delta = {pattern["delta"]: pattern for pattern in patterns}
    delta_by_gaps = {(pattern["left_gap"], pattern["bottom_gap"]): pattern["delta"] for pattern in patterns}
    final: list[dict[str, Any]] = []
    for base_rank, original in enumerate(_ranked(list(selected.values()))):
        original_pattern = pattern_by_delta[original["delta"]]
        transpose_delta = delta_by_gaps[(original_pattern["bottom_gap"], original_pattern["left_gap"])]
        transpose_pattern = pattern_by_delta[transpose_delta]
        transposed: dict[str, Any] = {
            "w": original["h"],
            "h": original["w"],
            "x": original["y"],
            "y": original["x"],
            "delta": transpose_delta,
        }
        transposed["a_delta"], transposed["e_delta"] = _contact(
            transpose_pattern,
            transposed["w"],
            transposed["h"],
            transposed["x"],
            transposed["y"],
        )
        if (transposed["a_delta"], transposed["e_delta"]) != (
            original["a_delta"],
            original["e_delta"],
        ) or not _eligible(transposed["w"], transposed["h"], transposed["a_delta"], transposed["e_delta"]):
            raise CorpusError("transpose did not preserve q/e eligibility")
        transposed["canonical_utf8"] = _canonical(transposed)
        transposed["rank_hash_sha256"] = hashlib.sha256(
            seed_digest + transposed["canonical_utf8"].encode("utf-8")
        ).hexdigest()
        transpose_group_id = f"transpose_group_{base_rank:03d}"
        for variant, case in (("original", original), ("transpose", transposed)):
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
                    "selection_reasons": (
                        sorted(reasons[original["canonical_utf8"]])
                        if variant == "original"
                        else [f"transpose_of:case_{case_index - 1:03d}"]
                    ),
                }
            )
            final.append(record)
    if len(final) != FINAL_CASES:
        raise CorpusError("final original/transpose corpus is not exactly 512")
    for rank in range(BASE_CASES):
        original, transpose = final[2 * rank : 2 * rank + 2]
        if original["variant"] != "original" or transpose["variant"] != "transpose":
            raise CorpusError("final corpus ordering is not base-rank/original/transpose")
        if original["pair_id"] == transpose["pair_id"]:
            raise CorpusError("original and transpose reused a control/treatment pair identity")
        if original["transpose_group_id"] != transpose["transpose_group_id"]:
            raise CorpusError("original and transpose do not share a symmetry-group identity")
    if len({case["pair_id"] for case in final}) != FINAL_CASES:
        raise CorpusError("control/treatment pair identities are not unique per diagnostic case")
    if len({case["transpose_group_id"] for case in final}) != BASE_CASES:
        raise CorpusError("transpose symmetry-group identities are not exactly 256")
    return final, {
        "r1_eligible_34x35_universe": len(universe),
        "delta_strata": len(by_delta),
        "nonempty_margin_bin_pairs": len(by_margin),
        "nonempty_contact_bin_pairs": len(by_contact),
        "deduplicated_base_cases": len(selected),
        "final_cases": len(final),
        "control_treatment_pairs": len({case["pair_id"] for case in final}),
        "transpose_symmetry_groups": len({case["transpose_group_id"] for case in final}),
    }


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--r1-translation-gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.project_root.resolve(strict=True)
    strict = _validate_strict(root)
    r1_record, r1_sha = _validate_r1_gate(args.r1_translation_gate, root)
    seed_material = LABEL + bytes.fromhex(STRICT_SHA256) + bytes.fromhex(r1_sha)
    seed_digest = hashlib.sha256(seed_material).digest()
    cases, selection = _build_cases(seed_digest)
    payload = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "manifest_state": "BUILT_BEFORE_RESULTS",
        "solver_results_included": False,
        "project_root": str(root),
        "argv": [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)],
        "builder_source": _snapshot(Path(__file__), root),
        "strict_instance": strict,
        "r1_authoritative_translation_gate": r1_record,
        "seed": {
            "label_utf8": LABEL.decode("ascii"),
            "strict_sha256_bytes_hex": STRICT_SHA256,
            "r1_translation_gate_sha256_bytes_hex": r1_sha,
            "material_encoding": "label_utf8 || raw_sha256(strict) || raw_sha256(r1_gate)",
            "seed_sha256": seed_digest.hex(),
            "case_rank_hash": "sha256(raw_seed_sha256 || canonical_tuple_utf8)",
        },
        "canonical_tuple_fields": ["w", "h", "x", "y", "delta", "a_delta", "e_delta"],
        "selection": selection,
        "case_count": len(cases),
        "cases": cases,
        "corpus_errors": [],
        "claim_boundary": [
            "deterministic diagnostic sampling manifest only",
            "contains no solver result and makes no SAT or UNSAT claim",
            "does not establish a new upper bound, witness, attainability, or optimality",
            "research artifact; not sealed and not production CERTIFIED evidence",
        ],
    }
    _exclusive_json(args.output.resolve(), payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "case_count": len(cases),
                "output": str(args.output.resolve()),
                "seed_sha256": seed_digest.hex(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
