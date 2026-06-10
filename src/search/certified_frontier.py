"""Replayable terminal-frontier evidence for certified exact campaigns.

A terminal CERTIFIED checkpoint must not rely on a stop-reason string alone.  This
module keeps the candidate-domain projection small, deterministic, and
recomputable from the checkpoint plus the candidate-generation parameters used by
outer_search.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE

TERMINAL_FRONTIER_EVIDENCE_SCHEMA_VERSION = 1
TERMINAL_FRONTIER_EVIDENCE_SOURCE = "certified_terminal_frontier_evidence_v1"
TERMINAL_FRONTIER_EXHAUSTED_REASON = "search_exhausted_all_candidates"
TERMINAL_FRONTIER_DOMAIN_AUTHORITY = "outer_search_static_area_bound_v1"
# PROJECT_LOCK: min_side >= 6 is admissibility, so the certified target domain is
# exactly the min_side=6 domain.  A terminal full-frontier claim generated with a
# larger min_side searched a strict sub-domain and must be rejected; a smaller
# min_side searched a superset and stays safe.
TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY = 6
_MISSING_STATUS = "MISSING"
_GENERATION_PARAM_KEYS = {
    "max_w",
    "max_h",
    "min_side",
    "max_aspect_ratio",
    "area_upper_bound",
    "start_area",
}

Candidate = Tuple[int, int, int]


def generate_candidate_sizes(
    *,
    max_w: int = 70,
    max_h: int = 70,
    min_side: int = 6,
    max_aspect_ratio: Optional[float] = None,
    area_upper_bound: Optional[int] = None,
    start_area: Optional[int] = None,
) -> list[Candidate]:
    params = normalize_candidate_generation_params(
        {
            "max_w": max_w,
            "max_h": max_h,
            "min_side": min_side,
            "max_aspect_ratio": max_aspect_ratio,
            "area_upper_bound": area_upper_bound,
            "start_area": start_area,
        }
    )
    candidates: list[Candidate] = []
    for w in range(int(params["min_side"]), int(params["max_w"]) + 1):
        for h in range(int(params["min_side"]), min(int(params["max_h"]), w) + 1):
            area = w * h
            area_upper_bound = params["area_upper_bound"]
            if area_upper_bound is not None and area > int(area_upper_bound):
                continue
            start_area = params["start_area"]
            if start_area is not None and area > int(start_area):
                continue
            aspect_limit = params["max_aspect_ratio"]
            if aspect_limit is not None:
                longer = max(w, h)
                shorter = max(1, min(w, h))
                if longer / shorter > float(aspect_limit):
                    continue
            candidates.append((area, w, h))
    candidates.sort(key=candidate_sort_key)
    return candidates


def normalize_candidate_generation_params(raw_params: Mapping[str, Any]) -> Dict[str, Any]:
    max_w = _strict_positive_int(raw_params.get("max_w"), "candidate_generation.max_w")
    max_h = _strict_positive_int(raw_params.get("max_h"), "candidate_generation.max_h")
    min_side = _strict_positive_int(raw_params.get("min_side"), "candidate_generation.min_side")
    if min_side > max_w or min_side > max_h:
        raise ValueError("candidate_generation.min_side exceeds grid dimensions")
    return {
        "max_w": max_w,
        "max_h": max_h,
        "min_side": min_side,
        "max_aspect_ratio": _optional_positive_finite_float(
            raw_params.get("max_aspect_ratio"),
            "candidate_generation.max_aspect_ratio",
        ),
        "area_upper_bound": _optional_nonnegative_int(
            raw_params.get("area_upper_bound"),
            "candidate_generation.area_upper_bound",
        ),
        "start_area": _optional_nonnegative_int(
            raw_params.get("start_area"),
            "candidate_generation.start_area",
        ),
    }


def normalize_terminal_frontier_domain_contract(raw_params: Mapping[str, Any]) -> Dict[str, Any]:
    params = normalize_candidate_generation_params(raw_params)
    params["domain_authority"] = str(raw_params.get("domain_authority", ""))
    params["safe_area_upper_bound"] = _optional_nonnegative_int(
        raw_params.get("safe_area_upper_bound"),
        "candidate_generation.safe_area_upper_bound",
    )
    return params


def candidate_generation_kwargs(raw_params: Mapping[str, Any]) -> Dict[str, Any]:
    params = normalize_candidate_generation_params(raw_params)
    return {key: params[key] for key in sorted(_GENERATION_PARAM_KEYS)}


def candidate_key(candidate: Candidate) -> str:
    return f"{int(candidate[1])}x{int(candidate[2])}"


def candidate_key_from_dimensions(ghost_w: int, ghost_h: int) -> str:
    return f"{int(ghost_w)}x{int(ghost_h)}"


def candidate_objective(candidate: Candidate) -> tuple[int, int]:
    area, ghost_w, ghost_h = candidate
    return (int(area), int(min(int(ghost_w), int(ghost_h))))


def candidate_sort_key(candidate: Candidate) -> tuple[int, int, int, int]:
    area, ghost_w, ghost_h = candidate
    min_side = min(int(ghost_w), int(ghost_h))
    max_side = max(int(ghost_w), int(ghost_h))
    return (-int(area), -int(min_side), -int(max_side), -int(ghost_w))


def compute_terminal_frontier_projection(
    *,
    candidates: Sequence[Candidate],
    candidate_records: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized_candidates = [_normalize_candidate(candidate) for candidate in candidates]
    explicit_certified: list[Candidate] = []
    explicit_infeasible: list[Candidate] = []
    best_certified_candidate: Optional[Candidate] = None
    best_certified_record: Optional[Dict[str, Any]] = None

    for candidate in normalized_candidates:
        _area, ghost_w, ghost_h = candidate
        record = candidate_records.get(candidate_key(candidate))
        if not isinstance(record, Mapping):
            continue
        status = str(record.get("status", ""))
        if status == RUN_STATUS_CERTIFIED:
            explicit_certified.append(candidate)
            if best_certified_candidate is None or candidate_objective(candidate) > candidate_objective(
                best_certified_candidate
            ):
                best_certified_candidate = candidate
                best_certified_record = dict(record)
        elif status == RUN_STATUS_INFEASIBLE:
            explicit_infeasible.append(candidate)

    potential_domain: list[Candidate] = []
    derived_pruned_candidates = 0
    for candidate in normalized_candidates:
        _area, ghost_w, ghost_h = candidate
        record = candidate_records.get(candidate_key(candidate))
        status = None if not isinstance(record, Mapping) else str(record.get("status", ""))
        if status in {RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE}:
            continue
        if any(ghost_w <= cert_w and ghost_h <= cert_h for _a, cert_w, cert_h in explicit_certified):
            derived_pruned_candidates += 1
            continue
        if any(ghost_w >= inf_w and ghost_h >= inf_h for _a, inf_w, inf_h in explicit_infeasible):
            derived_pruned_candidates += 1
            continue
        if best_certified_candidate is not None and candidate_objective(candidate) <= candidate_objective(
            best_certified_candidate
        ):
            derived_pruned_candidates += 1
            continue
        potential_domain.append(candidate)

    frontier: list[Candidate] = []
    for candidate in potential_domain:
        _area, ghost_w, ghost_h = candidate
        dominated = False
        for other in potential_domain:
            if other == candidate:
                continue
            _other_area, other_w, other_h = other
            if (other_w >= ghost_w and other_h >= ghost_h) and (
                other_w > ghost_w or other_h > ghost_h
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    frontier.sort(key=candidate_objective, reverse=True)

    return {
        "potential_domain": potential_domain,
        "frontier": frontier,
        "derived_pruned_candidates": int(derived_pruned_candidates),
        "best_certified_candidate": best_certified_candidate,
        "best_certified_record": best_certified_record,
    }


def build_terminal_frontier_evidence(
    *,
    candidates: Sequence[Candidate],
    candidate_records: Mapping[str, Any],
    final_result: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
) -> Dict[str, Any]:
    evidence_params = normalize_terminal_frontier_domain_contract(candidate_generation)
    params = candidate_generation_kwargs(evidence_params)
    normalized_candidates = [_normalize_candidate(candidate) for candidate in candidates]
    projection = compute_terminal_frontier_projection(
        candidates=normalized_candidates,
        candidate_records=candidate_records,
    )
    best_certified_candidate = projection.get("best_certified_candidate")
    final_key = _final_result_candidate_key(final_result)
    evidence = {
        "schema_version": TERMINAL_FRONTIER_EVIDENCE_SCHEMA_VERSION,
        "source": TERMINAL_FRONTIER_EVIDENCE_SOURCE,
        "reason": TERMINAL_FRONTIER_EXHAUSTED_REASON,
        "candidate_generation": evidence_params,
        "candidate_domain_size": len(normalized_candidates),
        "candidate_status_counts": _candidate_status_counts(
            candidates=normalized_candidates,
            candidate_records=candidate_records,
        ),
        "candidate_status_digest": _candidate_status_digest(
            candidates=normalized_candidates,
            candidate_records=candidate_records,
        ),
        "potential_domain_size": len(projection["potential_domain"]),
        "potential_domain_keys": [candidate_key(candidate) for candidate in projection["potential_domain"]],
        "frontier_size": len(projection["frontier"]),
        "frontier_keys": [candidate_key(candidate) for candidate in projection["frontier"]],
        "derived_pruned_candidates": int(projection["derived_pruned_candidates"]),
        "best_certified_candidate_key": (
            None if best_certified_candidate is None else candidate_key(best_certified_candidate)
        ),
        "final_result_candidate_key": final_key,
    }
    return evidence


def terminal_frontier_evidence_violation(
    *,
    evidence: Any,
    candidate_records: Mapping[str, Any],
    final_result: Mapping[str, Any],
    grid_dimensions: Optional[tuple[int, int]] = None,
    safe_area_upper_bound: Optional[int] = None,
) -> Optional[str]:
    if not isinstance(evidence, Mapping):
        return "terminal_frontier_evidence_missing"
    try:
        schema_version = _strict_int(evidence.get("schema_version"), "terminal_frontier_evidence.schema_version")
    except Exception:
        return "terminal_frontier_evidence_schema_invalid"
    if schema_version != TERMINAL_FRONTIER_EVIDENCE_SCHEMA_VERSION:
        return "terminal_frontier_evidence_schema_invalid"
    if str(evidence.get("source", "")) != TERMINAL_FRONTIER_EVIDENCE_SOURCE:
        return "terminal_frontier_evidence_source_invalid"
    if str(evidence.get("reason", "")) != TERMINAL_FRONTIER_EXHAUSTED_REASON:
        return "terminal_frontier_evidence_reason_invalid"
    try:
        evidence_params = normalize_terminal_frontier_domain_contract(
            _require_mapping(evidence.get("candidate_generation"))
        )
        params = candidate_generation_kwargs(evidence_params)
    except Exception:
        return "terminal_frontier_candidate_generation_invalid"
    if grid_dimensions is not None:
        grid_w, grid_h = grid_dimensions
        if int(params["max_w"]) != int(grid_w) or int(params["max_h"]) != int(grid_h):
            return "terminal_frontier_candidate_generation_grid_mismatch"
    if str(evidence_params.get("domain_authority", "")) != TERMINAL_FRONTIER_DOMAIN_AUTHORITY:
        return "terminal_frontier_domain_authority_invalid"
    if evidence_params.get("start_area") is not None:
        return "terminal_frontier_start_area_not_full_domain"
    # V79: max_aspect_ratio and an above-admissibility min_side slice the candidate
    # domain exactly like start_area does; an exhausted sliced domain must not
    # masquerade as authoritative full-frontier exhaustion.
    if evidence_params.get("max_aspect_ratio") is not None:
        return "terminal_frontier_aspect_ratio_sliced_domain"
    if int(params["min_side"]) > TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY:
        return "terminal_frontier_min_side_sliced_domain"
    if evidence_params.get("safe_area_upper_bound") is None:
        return "terminal_frontier_safe_area_upper_bound_missing"
    if evidence_params.get("area_upper_bound") != evidence_params.get("safe_area_upper_bound"):
        return "terminal_frontier_area_upper_bound_not_authoritative"
    if safe_area_upper_bound is not None:
        if int(evidence_params["safe_area_upper_bound"]) != int(safe_area_upper_bound):
            return "terminal_frontier_safe_area_upper_bound_mismatch"

    candidates = generate_candidate_sizes(**params)
    projection = compute_terminal_frontier_projection(
        candidates=candidates,
        candidate_records=candidate_records,
    )
    final_key = _final_result_candidate_key(final_result)
    best_certified_candidate = projection.get("best_certified_candidate")
    best_key = None if best_certified_candidate is None else candidate_key(best_certified_candidate)

    try:
        if _strict_int(evidence.get("candidate_domain_size"), "candidate_domain_size") != len(candidates):
            return "terminal_frontier_candidate_domain_size_mismatch"
        if _strict_int(evidence.get("potential_domain_size"), "potential_domain_size") != len(
            projection["potential_domain"]
        ):
            return "terminal_frontier_potential_domain_size_mismatch"
        if _strict_int(evidence.get("frontier_size"), "frontier_size") != len(projection["frontier"]):
            return "terminal_frontier_size_mismatch"
        if _strict_int(evidence.get("derived_pruned_candidates"), "derived_pruned_candidates") != int(
            projection["derived_pruned_candidates"]
        ):
            return "terminal_frontier_derived_pruned_count_mismatch"
    except Exception:
        return "terminal_frontier_evidence_count_invalid"

    if dict(evidence.get("candidate_status_counts", {})) != _candidate_status_counts(
        candidates=candidates,
        candidate_records=candidate_records,
    ):
        return "terminal_frontier_candidate_status_counts_mismatch"
    if str(evidence.get("candidate_status_digest", "")) != _candidate_status_digest(
        candidates=candidates,
        candidate_records=candidate_records,
    ):
        return "terminal_frontier_candidate_status_digest_mismatch"
    if _string_list(evidence.get("potential_domain_keys")) != [
        candidate_key(candidate) for candidate in projection["potential_domain"]
    ]:
        return "terminal_frontier_potential_domain_keys_mismatch"
    if _string_list(evidence.get("frontier_keys")) != [
        candidate_key(candidate) for candidate in projection["frontier"]
    ]:
        return "terminal_frontier_keys_mismatch"
    if evidence.get("best_certified_candidate_key") != best_key:
        return "terminal_frontier_best_candidate_mismatch"
    if evidence.get("final_result_candidate_key") != final_key:
        return "terminal_frontier_final_result_key_mismatch"
    if best_key != final_key:
        return "terminal_frontier_final_result_not_best_candidate"
    if projection["potential_domain"]:
        return "terminal_frontier_potential_domain_not_exhausted"
    if projection["frontier"]:
        return "terminal_frontier_not_exhausted"
    return None


def _candidate_status_counts(
    *,
    candidates: Sequence[Candidate],
    candidate_records: Mapping[str, Any],
) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for candidate in candidates:
        record = candidate_records.get(candidate_key(candidate))
        status = _MISSING_STATUS if not isinstance(record, Mapping) else str(record.get("status", ""))
        counts[status] += 1
    return {key: int(counts[key]) for key in sorted(counts)}


def _candidate_status_digest(
    *,
    candidates: Sequence[Candidate],
    candidate_records: Mapping[str, Any],
) -> str:
    entries: list[dict[str, Any]] = []
    for candidate in candidates:
        area, ghost_w, ghost_h = candidate
        key = candidate_key(candidate)
        record = candidate_records.get(key)
        status = _MISSING_STATUS if not isinstance(record, Mapping) else str(record.get("status", ""))
        entry: dict[str, Any] = {
            "key": key,
            "w": int(ghost_w),
            "h": int(ghost_h),
            "area": int(area),
            "status": status,
        }
        if isinstance(record, Mapping) and status == RUN_STATUS_CERTIFIED:
            entry["solution_digest"] = _canonical_digest(record.get("solution"))
        entries.append(entry)
    return _canonical_digest({"entries": entries})


def _canonical_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _normalize_candidate(candidate: Sequence[Any]) -> Candidate:
    if len(candidate) != 3:
        raise ValueError("candidate must have area,w,h")
    area = _strict_int(candidate[0], "candidate.area")
    ghost_w = _strict_int(candidate[1], "candidate.w")
    ghost_h = _strict_int(candidate[2], "candidate.h")
    if ghost_w <= 0 or ghost_h <= 0 or area != ghost_w * ghost_h:
        raise ValueError("candidate dimensions must be positive and area-consistent")
    return (area, ghost_w, ghost_h)


def _final_result_candidate_key(final_result: Mapping[str, Any]) -> Optional[str]:
    ghost_rect = final_result.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return None
    try:
        return candidate_key_from_dimensions(
            _strict_int(ghost_rect.get("w"), "final_result.ghost_rect.w"),
            _strict_int(ghost_rect.get("h"), "final_result.ghost_rect.h"),
        )
    except Exception:
        return None


def _require_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("expected mapping")
    return value


def _strict_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _strict_positive_int(value: Any, field: str) -> int:
    result = _strict_int(value, field)
    if result <= 0:
        raise ValueError(f"{field} must be positive")
    return result


def _optional_nonnegative_int(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    result = _strict_int(value, field)
    if result < 0:
        raise ValueError(f"{field} must be non-negative")
    return result


def _optional_positive_finite_float(value: Any, field: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{field} must be positive finite")
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
