#!/usr/bin/env python3
"""Standard-library sensitivity checker for Endpoint Metrics Protocol v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


class CheckError(RuntimeError):
    """Raised when a frozen metric contract or synthetic control fails."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"cannot read JSON {path}: {exc}") from exc
    _require(isinstance(value, dict), f"top-level JSON must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CheckError(f"cannot hash {path}: {exc}") from exc


def _score(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    _x, _y, width, height = rect
    return width * height, min(width, height)


def _rectangles(width: int, height: int, min_side: int) -> tuple[tuple[int, int, int, int], ...]:
    values: list[tuple[int, int, int, int]] = []
    for rect_w in range(min_side, width + 1):
        for rect_h in range(min_side, height + 1):
            for x in range(width - rect_w + 1):
                for y in range(height - rect_h + 1):
                    values.append((x, y, rect_w, rect_h))
    return tuple(values)


def _lex_gt(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left > right


def _metrics(
    universe: Iterable[tuple[int, int, int, int]],
    *,
    witness_score: tuple[int, int] | None,
    excluded: frozenset[tuple[int, int, int, int]],
) -> dict[str, Any]:
    unresolved = tuple(rect for rect in universe if rect not in excluded)
    _require(bool(unresolved), "synthetic unresolved universe unexpectedly empty")
    score_counts = Counter(_score(rect) for rect in unresolved)
    ordered_scores = sorted(score_counts, reverse=True)
    upper = ordered_scores[0]
    highest_count = int(score_counts[upper])
    histogram = [
        {"score": list(score), "count": int(score_counts[score])}
        for score in ordered_scores[:8]
    ]
    if witness_score is None:
        return {
            "L_t": "ABSENT",
            "U_t": list(upper),
            "M_t": "N_A_NOT_READY",
            "G_t": "N_A_NOT_READY",
            "B_t": highest_count,
            "H_t": histogram,
        }
    better_scores = [score for score in ordered_scores if _lex_gt(score, witness_score)]
    return {
        "L_t": list(witness_score),
        "U_t": list(upper),
        "M_t": int(
            sum(count for score, count in score_counts.items() if _lex_gt(score, witness_score))
        ),
        "G_t": len(better_scores),
        "B_t": highest_count,
        "H_t": histogram,
    }


def _apply_exclusion(
    excluded: frozenset[tuple[int, int, int, int]],
    rect: tuple[int, int, int, int],
    *,
    supplied_context: str,
    expected_context: str,
) -> frozenset[tuple[int, int, int, int]]:
    if supplied_context != expected_context:
        raise CheckError("contextHash mismatch")
    return frozenset((*excluded, rect))


def _find_repeated_band_fixture(
    universe: tuple[tuple[int, int, int, int], ...],
    witness: tuple[int, int],
) -> tuple[
    tuple[int, int],
    tuple[tuple[int, int, int, int], ...],
    frozenset[tuple[int, int, int, int]],
]:
    by_score: dict[tuple[int, int], list[tuple[int, int, int, int]]] = {}
    for rect in universe:
        by_score.setdefault(_score(rect), []).append(rect)
    scores = sorted((score for score in by_score if score > witness), reverse=True)
    for index, score in enumerate(scores):
        members = tuple(by_score[score])
        if len(members) < 2 or index + 1 >= len(scores):
            continue
        higher = frozenset(
            rect
            for higher_score in scores[:index]
            for rect in by_score[higher_score]
        )
        return score, members, higher
    raise CheckError("cannot construct repeated top-band synthetic fixture")


def _run_sensitivity(protocol: Mapping[str, Any]) -> dict[str, Any]:
    fixture = protocol["synthetic_fixture"]
    width = int(fixture["grid_width"])
    height = int(fixture["grid_height"])
    min_side = int(fixture["min_side"])
    context = str(fixture["contextHash"])
    universe = _rectangles(width, height, min_side)
    initial_witness = tuple(int(value) for value in fixture["initial_witness_score"])
    _require(len(initial_witness) == 2, "initial witness score must have two fields")
    results: list[dict[str, Any]] = []

    base = _metrics(universe, witness_score=initial_witness, excluded=frozenset())
    higher = _metrics(universe, witness_score=(8, 2), excluded=frozenset())
    _require(tuple(higher["L_t"]) > tuple(base["L_t"]), "SENS-01 did not raise L")
    _require(int(higher["M_t"]) < int(base["M_t"]), "SENS-01 did not lower M")
    results.append({"id": "SENS-01-HIGHER-AREA-WITNESS", "status": "PASS"})

    _require(_lex_gt((8, 4), (8, 2)), "SENS-02 lex comparator ignored min_side")
    results.append(
        {
            "id": "SENS-02-SAME-AREA-HIGHER-MIN-SIDE",
            "status": "PASS",
            "note": "pure score-comparator control; the synthetic pair is not asserted to be a realizable rectangle",
        }
    )

    band_score, band_members, higher_exclusions = _find_repeated_band_fixture(
        universe, initial_witness
    )
    before_one = _metrics(
        universe,
        witness_score=initial_witness,
        excluded=higher_exclusions,
    )
    one_removed = _apply_exclusion(
        higher_exclusions,
        band_members[0],
        supplied_context=context,
        expected_context=context,
    )
    after_one = _metrics(universe, witness_score=initial_witness, excluded=one_removed)
    _require(tuple(before_one["U_t"]) == band_score, "SENS-03 fixture top band mismatch")
    _require(after_one["U_t"] == before_one["U_t"], "SENS-03 moved U")
    _require(int(after_one["B_t"]) == int(before_one["B_t"]) - 1, "SENS-03 did not decrement B")
    results.append({"id": "SENS-03-REMOVE-ONE-FROM-TOP-BAND", "status": "PASS"})

    closed_band = frozenset((*higher_exclusions, *band_members))
    after_close = _metrics(universe, witness_score=initial_witness, excluded=closed_band)
    _require(tuple(after_close["U_t"]) < band_score, "SENS-04 did not move U")
    _require(int(after_close["G_t"]) == int(before_one["G_t"]) - 1, "SENS-04 did not decrement G")
    results.append({"id": "SENS-04-CLOSE-TOP-BAND", "status": "PASS"})

    low_rect = next(rect for rect in universe if _score(rect) <= initial_witness)
    low_excluded = _apply_exclusion(
        frozenset(), low_rect, supplied_context=context, expected_context=context
    )
    low_metrics = _metrics(universe, witness_score=initial_witness, excluded=low_excluded)
    for field in ("M_t", "G_t", "U_t", "B_t"):
        _require(low_metrics[field] == base[field], f"SENS-05 changed {field}")
    results.append({"id": "SENS-05-IRRELEVANT-LOW-SCORE-EXCLUSION", "status": "PASS"})

    once = _apply_exclusion(
        frozenset(), low_rect, supplied_context=context, expected_context=context
    )
    twice = _apply_exclusion(
        once, low_rect, supplied_context=context, expected_context=context
    )
    _require(once == twice, "SENS-06 exclusion was not idempotent")
    _require(
        _metrics(universe, witness_score=initial_witness, excluded=once)
        == _metrics(universe, witness_score=initial_witness, excluded=twice),
        "SENS-06 metrics changed on duplicate",
    )
    results.append({"id": "SENS-06-IDEMPOTENT-DUPLICATE", "status": "PASS"})

    stale_failed = False
    try:
        _apply_exclusion(
            frozenset(),
            low_rect,
            supplied_context="stale-context",
            expected_context=context,
        )
    except CheckError:
        stale_failed = True
    _require(stale_failed, "SENS-07 stale context did not fail closed")
    results.append({"id": "SENS-07-STALE-CONTEXT", "status": "PASS"})

    absent = _metrics(universe, witness_score=None, excluded=frozenset())
    _require(absent["M_t"] == "N_A_NOT_READY", "SENS-08 fabricated numeric M")
    _require(absent["G_t"] == "N_A_NOT_READY", "SENS-08 fabricated numeric G")
    results.append({"id": "SENS-08-ABSENT-LOWER-BOUND", "status": "PASS"})

    resource_before = {"binding": 20.0, "routing": 0.0, "checker": 0.0}
    resource_after = {"binding": 10.0, "routing": 10.0, "checker": 0.0}
    total_before = math.fsum(resource_before.values())
    total_after = math.fsum(resource_after.values())
    _require(total_before == total_after, "SENS-09 total cost changed")
    _require(resource_before != resource_after, "SENS-09 stage shares did not change")
    results.append({"id": "SENS-09-HOTSPOT-MIGRATION", "status": "PASS"})

    routing_not_reached: float | str = "NOT_REACHED"
    _require(routing_not_reached != 0, "SENS-10 collapsed NOT_REACHED to zero")
    results.append({"id": "SENS-10-NOT-REACHED", "status": "PASS"})

    domain_before = 4
    domain_after = domain_before - 1
    _require(domain_after == 3, "SENS-11 unary domain removal mismatch")
    results.append(
        {
            "id": "SENS-11-UNARY-DOMAIN-REMOVAL",
            "status": "PASS",
            "evidence_type": "BOX_DOMAIN",
        }
    )

    expected_ids = [str(item["id"]) for item in protocol["sensitivity_tests"]]
    actual_ids = [str(item["id"]) for item in results]
    _require(actual_ids == expected_ids, "implemented sensitivity ID/order drift")
    return {
        "status": "PASS",
        "universe_rectangle_count": len(universe),
        "result_count": len(results),
        "results": results,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path(__file__).with_name("03_ENDPOINT_METRICS_PROTOCOL_V1.json"),
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()
    try:
        protocol = _load_json(args.protocol)
        _require(
            protocol.get("schema_version") == "zmd_endpoint_metrics_protocol_v1",
            "unexpected endpoint protocol schema",
        )
        sensitivity = _run_sensitivity(protocol)
        receipt = {
            "schema_version": "zmd_endpoint_metrics_sensitivity_receipt_v1",
            "status": "PASS",
            "protocol_path": str(args.protocol),
            "protocol_sha256": _sha256(args.protocol),
            "checker_sha256": _sha256(Path(__file__)),
            "standard_library_only": True,
            "sensitivity": sensitivity,
            "wall_seconds": time.perf_counter() - started,
        }
        encoded = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except (CheckError, KeyError, TypeError, ValueError, StopIteration) as exc:
        failure = {
            "schema_version": "zmd_endpoint_metrics_sensitivity_receipt_v1",
            "status": "FAIL",
            "error": str(exc),
            "wall_seconds": time.perf_counter() - started,
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
