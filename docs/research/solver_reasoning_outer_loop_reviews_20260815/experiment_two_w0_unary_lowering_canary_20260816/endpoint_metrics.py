#!/usr/bin/env python3
"""Pure evaluators for Endpoint Metrics Protocol v1."""

from __future__ import annotations

from collections import Counter
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


class EndpointMetricError(RuntimeError):
    """An endpoint metric is undefined, stale, or malformed."""


Rectangle = tuple[int, int, int, int]
Score = tuple[int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EndpointMetricError(message)


def rectangle_score(rectangle: Rectangle) -> Score:
    _x, _y, width, height = rectangle
    return width * height, min(width, height)


def enumerate_rectangles(width: int, height: int, min_side: int) -> tuple[Rectangle, ...]:
    require(width > 0 and height > 0 and min_side > 0, "invalid rectangle universe")
    values: list[Rectangle] = []
    for rect_width in range(min_side, width + 1):
        for rect_height in range(min_side, height + 1):
            for x in range(width - rect_width + 1):
                for y in range(height - rect_height + 1):
                    values.append((x, y, rect_width, rect_height))
    return tuple(values)


def score_to_list(score: Score | None) -> list[int] | None:
    return None if score is None else [int(score[0]), int(score[1])]


def evaluate_endpoint_state(
    *,
    rectangles: Sequence[Rectangle],
    witness_scores: Iterable[Score],
    excluded_rectangles: Iterable[Rectangle],
    context_hash: str,
    expected_context_hash: str,
    histogram_band_limit: int = 8,
) -> dict[str, Any]:
    require(context_hash == expected_context_hash, "contextHash mismatch")
    universe = tuple(rectangles)
    require(len(set(universe)) == len(universe), "rectangle universe contains duplicates")
    universe_set = set(universe)
    excluded = set(excluded_rectangles)
    require(excluded <= universe_set, "exclusion references a rectangle outside the universe")

    witness_values = tuple((int(area), int(min_side)) for area, min_side in witness_scores)
    lower_bound = max(witness_values) if witness_values else None
    unresolved = [rectangle for rectangle in universe if rectangle not in excluded]
    unresolved_scores = [rectangle_score(rectangle) for rectangle in unresolved]
    upper_bound = max(unresolved_scores) if unresolved_scores else None
    histogram = Counter(unresolved_scores)
    top_histogram = [
        {"score": score_to_list(score), "count": int(histogram[score])}
        for score in sorted(histogram, reverse=True)[:histogram_band_limit]
    ]

    if lower_bound is None:
        m_value: int | str = "N_A_NOT_READY"
        g_value: int | str = "N_A_NOT_READY"
        m_type = "N_A_NOT_READY"
        g_type = "N_A_NOT_READY"
    else:
        better = [score for score in unresolved_scores if score > lower_bound]
        m_value = len(better)
        g_value = len(set(better))
        m_type = "MEASURED"
        g_type = "MEASURED"

    b_value = 0 if upper_bound is None else int(histogram[upper_bound])
    return {
        "L_t": {
            "value": "ABSENT" if lower_bound is None else score_to_list(lower_bound),
            "type": "N_A_NOT_READY" if lower_bound is None else "MEASURED",
        },
        "U_t": {
            "value": score_to_list(upper_bound),
            "type": "MEASURED" if upper_bound is not None else "N_A_NOT_READY",
        },
        "M_t": {"value": m_value, "type": m_type},
        "G_t": {"value": g_value, "type": g_type},
        "B_t": {"value": b_value, "type": "MEASURED"},
        "H_t": {"value": top_histogram, "type": "MEASURED"},
        "universe_count": len(universe),
        "excluded_count": len(excluded),
        "unresolved_count": len(unresolved),
    }


def marginal_domain_envelope(domain_sizes: Sequence[int]) -> dict[str, Any]:
    sizes = [int(value) for value in domain_sizes]
    require(all(value > 0 for value in sizes), "domain sizes must be positive")
    return {
        "evidence_type": "BOX_DOMAIN",
        "variable_count": len(sizes),
        "domain_cardinality_sum": sum(sizes),
        "box_bits": sum(math.log2(value) for value in sizes),
        "exact_joint_cardinality_claimed": False,
    }


def resource_snapshot(
    *,
    stage_costs: Mapping[str, float | int | str],
    total_cost: float,
) -> dict[str, Any]:
    require(total_cost >= 0.0, "total cost cannot be negative")
    numeric_sum = 0.0
    stages: dict[str, Any] = {}
    for stage, raw_value in stage_costs.items():
        if isinstance(raw_value, str):
            require(raw_value == "NOT_REACHED", f"unsupported typed stage value: {raw_value}")
            stages[str(stage)] = {"value": "NOT_REACHED", "type": "NOT_REACHED"}
            continue
        value = float(raw_value)
        require(value >= 0.0, f"negative stage cost: {stage}")
        numeric_sum += value
        stages[str(stage)] = {
            "value": value,
            "type": "MEASURED",
            "share_of_total": 0.0 if total_cost == 0.0 else value / total_cost,
        }
    require(numeric_sum <= total_cost + 1e-9, "stage costs exceed total cost")
    return {"total_cost": float(total_cost), "stages": stages}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def capture_identity_snapshot(root: Path, records: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for record in records:
        relative = str(record["path"])
        path = root / relative
        require(path.is_file(), f"identity source is missing: {relative}")
        actual = sha256_file(path)
        expected = str(record["sha256"])
        require(actual == expected, f"identity source hash drift: {relative}")
        snapshot[relative] = actual
    return snapshot


def endpoint_neutral_transaction(
    *,
    before_sources: Mapping[str, str],
    after_sources: Mapping[str, str],
    lower_bound_absent: bool,
) -> dict[str, Any]:
    require(dict(before_sources) == dict(after_sources), "endpoint/protected source changed")
    return {
        "delta_L": "ZERO_BY_SCOPE",
        "delta_U": "ZERO_BY_SCOPE",
        "delta_M": (
            "ZERO_BY_SCOPE_WITH_M_T_N_A_NOT_READY"
            if lower_bound_absent
            else "ZERO_BY_SCOPE"
        ),
        "delta_M_bottom": "ZERO_BY_SCOPE",
        "delta_G": "ZERO_BY_SCOPE",
        "delta_B": "ZERO_BY_SCOPE",
        "source_identity_unchanged": True,
    }
