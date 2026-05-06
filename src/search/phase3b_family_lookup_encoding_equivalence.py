from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from src.models.exact_coordinate_master import family_shell_guard_shape
from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import (
    _build_exact_overlay,
    _check,
    _display_path,
    _mapping,
)

FAMILY_LOOKUP_ENCODING_EQUIVALENCE_SOURCE = (
    "phase3b_family_lookup_encoding_equivalence_v1"
)
DEFAULT_CANDIDATE = "67x13"


def build_phase3b_family_lookup_encoding_equivalence(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    started = time.perf_counter()
    status: Dict[str, Any] = {
        "completed": False,
        "outcome": "not_started",
        "recommendation": "Family lookup encoding equivalence audit has not run.",
    }
    model_error: Optional[str] = None
    overlay_seconds: Optional[float] = None
    relation_report: Dict[str, Any] = {}
    build_stats: Dict[str, Any] = {}

    try:
        overlay_started = time.perf_counter()
        model, _base_proto = _build_exact_overlay(
            project_root,
            ghost_rect=(int(ghost_w), int(ghost_h)),
            master_search_profile=master_search_profile,
        )
        overlay_seconds = float(time.perf_counter() - overlay_started)
        delegate = getattr(model, "_coordinate_delegate", None)
        relation_report = build_family_lookup_relation_equivalence_report(
            shell_lookup_rows=getattr(delegate, "_power_pole_shell_lookup_rows", []),
            family_name_by_int=getattr(delegate, "_power_pole_family_name_by_int", {}),
            use_shell_lookup=bool(getattr(delegate, "_power_pole_use_shell_lookup", False)),
            family_tuple_rows=getattr(delegate, "_power_pole_family_tuple_rows", []),
        )
        build_stats = {
            "power_family_lookup_encoding": dict(
                _mapping(model.build_stats.get("power_family_lookup_encoding"))
            ),
            "power_pole_shell_distance_encoding": dict(
                _mapping(model.build_stats.get("power_pole_shell_distance_encoding"))
            ),
            "power_pole_shell_lookup_pairs": dict(
                _mapping(model.build_stats.get("power_pole_shell_lookup_pairs"))
            ),
            "master_domain_table_rows": int(
                model.build_stats.get("master_domain_table_rows", 0)
            ),
            "power_coverage_witness_encoding": dict(
                _mapping(
                    _mapping(model.build_stats.get("power_coverage")).get(
                        "witness_encoding"
                    )
                )
            ),
        }
        status.update(_status_from_relation_report(relation_report))
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"
        status.update(
            {
                "completed": True,
                "outcome": "diagnostic_error",
                "recommendation": (
                    "Family lookup equivalence audit failed; inspect model_error "
                    "before using this gate."
                ),
            }
        )

    report = {
        "metadata": {
            "source": FAMILY_LOOKUP_ENCODING_EQUIVALENCE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_row_language_equivalence_audit",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {"project_root": _display_path(project_root, project_root)},
        "candidate": {
            "key": f"{ghost_w}x{ghost_h}",
            "ghost_rect": {
                "w": int(ghost_w),
                "h": int(ghost_h),
                "area": int(ghost_w * ghost_h),
            },
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "encoding_candidates": [
                "linear_shell_guards",
                "shell_pair_index",
            ],
        },
        "status": status,
        "build_stats": build_stats,
        "relation_equivalence": relation_report,
        "timing": {
            "overlay_build_seconds": overlay_seconds,
            "total_seconds": float(time.perf_counter() - started),
        },
        "model_error": model_error,
    }
    report["checks"] = _checks(report)
    return report


def build_family_lookup_relation_equivalence_report(
    *,
    shell_lookup_rows: Sequence[Sequence[int]],
    family_name_by_int: Mapping[int, str],
    use_shell_lookup: bool = True,
    family_tuple_rows: Sequence[Sequence[int]] = (),
) -> Dict[str, Any]:
    family_name_by_int = {
        int(family_id): str(family_name)
        for family_id, family_name in dict(family_name_by_int or {}).items()
    }
    rows = _normalize_shell_lookup_rows(shell_lookup_rows)
    sentinel_family = int(len(family_name_by_int))
    if not bool(use_shell_lookup):
        return {
            "use_shell_lookup": False,
            "status": "skipped",
            "skip_reason": "full_pose_tuple_fallback",
            "family_count": int(len(family_name_by_int)),
            "family_tuple_row_count": int(len(list(family_tuple_rows or []))),
            "shell_lookup_row_count": int(len(rows)),
            "linear_shell_guards": {"equivalent": None, "status": "skipped"},
            "shell_pair_index": {"equivalent": None, "status": "skipped"},
            "sentinel": {
                "sentinel_family": int(sentinel_family),
                "active_relation_excludes_sentinel": True,
                "inactive_relation": {"active": False, "family": int(sentinel_family)},
            },
        }

    rows_by_family: Dict[int, list[Tuple[int, int]]] = defaultdict(list)
    for d_lo, d_hi, family_id in rows:
        rows_by_family[int(family_id)].append((int(d_lo), int(d_hi)))

    shape_reports = []
    shape_counts: Dict[str, int] = {}
    linear_equivalent = True
    for family_id in sorted(rows_by_family):
        original_pairs = set(rows_by_family[int(family_id)])
        shape = family_shell_guard_shape(sorted(original_pairs))
        shape_kind = str(shape.get("kind"))
        shape_counts[shape_kind] = int(shape_counts.get(shape_kind, 0)) + 1
        shape_pairs = _pairs_from_family_shell_guard_shape(shape)
        equivalent = shape_pairs == original_pairs
        if not equivalent:
            linear_equivalent = False
        shape_reports.append(
            {
                "family_id": int(family_id),
                "family_name": family_name_by_int.get(int(family_id)),
                "row_count": int(len(original_pairs)),
                "shape": shape,
                "equivalent": bool(equivalent),
                "missing_pairs": [
                    [int(d_lo), int(d_hi)]
                    for d_lo, d_hi in sorted(original_pairs - shape_pairs)
                ],
                "extra_pairs": [
                    [int(d_lo), int(d_hi)]
                    for d_lo, d_hi in sorted(shape_pairs - original_pairs)
                ],
            }
        )

    pair_to_family: Dict[Tuple[int, int], int] = {}
    pair_conflicts: list[Dict[str, Any]] = []
    for d_lo, d_hi, family_id in rows:
        pair = (int(d_lo), int(d_hi))
        existing = pair_to_family.get(pair)
        if existing is not None and existing != int(family_id):
            pair_conflicts.append(
                {
                    "d_lo": int(d_lo),
                    "d_hi": int(d_hi),
                    "family_ids": sorted({int(existing), int(family_id)}),
                }
            )
        pair_to_family[pair] = int(family_id)
    shell_pair_index_rows = [
        {
            "pair_index": int(pair_index),
            "d_lo": int(pair[0]),
            "d_hi": int(pair[1]),
            "family_id": int(family_id),
            "family_name": family_name_by_int.get(int(family_id)),
        }
        for pair_index, (pair, family_id) in enumerate(sorted(pair_to_family.items()))
    ]
    shell_pair_relation = {
        (int(row["d_lo"]), int(row["d_hi"]), int(row["family_id"]))
        for row in shell_pair_index_rows
    }
    table_relation = set(rows)
    shell_pair_equivalent = not pair_conflicts and shell_pair_relation == table_relation
    active_family_ids = {int(row[2]) for row in rows}

    return {
        "use_shell_lookup": True,
        "status": "evaluated",
        "family_count": int(len(family_name_by_int)),
        "sentinel_family": int(sentinel_family),
        "shell_lookup_row_count": int(len(rows)),
        "family_ids_in_rows": sorted(active_family_ids),
        "linear_shell_guards": {
            "status": "evaluated",
            "equivalent": bool(linear_equivalent),
            "shape_counts": dict(sorted(shape_counts.items())),
            "families": shape_reports,
        },
        "shell_pair_index": {
            "status": "evaluated",
            "equivalent": bool(shell_pair_equivalent),
            "pair_count": int(len(pair_to_family)),
            "pair_conflict_count": int(len(pair_conflicts)),
            "pair_conflicts": pair_conflicts,
            "rows": shell_pair_index_rows,
            "missing_relation_rows": [
                [int(d_lo), int(d_hi), int(family_id)]
                for d_lo, d_hi, family_id in sorted(table_relation - shell_pair_relation)
            ],
            "extra_relation_rows": [
                [int(d_lo), int(d_hi), int(family_id)]
                for d_lo, d_hi, family_id in sorted(shell_pair_relation - table_relation)
            ],
        },
        "sentinel": {
            "sentinel_family": int(sentinel_family),
            "active_relation_excludes_sentinel": sentinel_family not in active_family_ids,
            "inactive_relation": {"active": False, "family": int(sentinel_family)},
        },
    }


def render_phase3b_family_lookup_encoding_equivalence_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("relation_equivalence"))
    linear = _mapping(relation.get("linear_shell_guards"))
    shell_pair = _mapping(relation.get("shell_pair_index"))
    sentinel = _mapping(relation.get("sentinel"))
    lines = [
        "# Phase 3B Family Lookup Encoding Equivalence",
        "",
        "- Diagnostic semantics: no_solve_row_language_equivalence_audit",
        "- Solver invoked: false",
        "- Proof source: false",
        "- Candidate elimination claim: false",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Use shell lookup | {_markdown_cell(relation.get('use_shell_lookup'))} |",
        f"| Shell lookup rows | {_markdown_cell(relation.get('shell_lookup_row_count'))} |",
        f"| Family count | {_markdown_cell(relation.get('family_count'))} |",
        f"| Sentinel family | {_markdown_cell(sentinel.get('sentinel_family'))} |",
        f"| Linear shell guards equivalent | {_markdown_cell(linear.get('equivalent'))} |",
        f"| Shell pair index equivalent | {_markdown_cell(shell_pair.get('equivalent'))} |",
        f"| Shape counts | {_markdown_cell(linear.get('shape_counts'))} |",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_family_lookup_encoding_equivalence_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("relation_equivalence"))
    linear = _mapping(relation.get("linear_shell_guards"))
    shell_pair = _mapping(relation.get("shell_pair_index"))
    lines = [
        "Phase 3B family lookup encoding equivalence",
        "diagnostic_semantics=no_solve_row_language_equivalence_audit",
        "solver_invoked=false",
        "proof_source=false",
        "candidate_elimination_claim=false",
        f"outcome={status.get('outcome')}",
        f"use_shell_lookup={relation.get('use_shell_lookup')}",
        f"shell_lookup_row_count={relation.get('shell_lookup_row_count')}",
        f"linear_shell_guards_equivalent={linear.get('equivalent')}",
        f"shell_pair_index_equivalent={shell_pair.get('equivalent')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _status_from_relation_report(relation_report: Mapping[str, Any]) -> Dict[str, Any]:
    if not bool(relation_report.get("use_shell_lookup", False)):
        return {
            "completed": True,
            "outcome": "shell_lookup_fallback_path",
            "recommendation": (
                "Shell lookup is not active; keep the full tuple fallback unchanged "
                "and do not apply shell-pair factorization."
            ),
        }
    linear = _mapping(relation_report.get("linear_shell_guards"))
    shell_pair = _mapping(relation_report.get("shell_pair_index"))
    sentinel = _mapping(relation_report.get("sentinel"))
    if (
        linear.get("equivalent") is True
        and shell_pair.get("equivalent") is True
        and sentinel.get("active_relation_excludes_sentinel") is True
    ):
        return {
            "completed": True,
            "outcome": "relations_equivalent",
            "recommendation": (
                "No-solve row-language gate passed. It is safe to proceed to a "
                "default-off encoding implementation or build-stat comparison, "
                "but not to proof promotion or production long-run."
            ),
        }
    return {
        "completed": True,
        "outcome": "relation_mismatch",
        "recommendation": (
            "Do not implement the alternate encoding until relation mismatches "
            "are understood."
        ),
    }


def _checks(report: Mapping[str, Any]) -> list[Dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("relation_equivalence"))
    linear = _mapping(relation.get("linear_shell_guards"))
    shell_pair = _mapping(relation.get("shell_pair_index"))
    sentinel = _mapping(relation.get("sentinel"))
    use_shell_lookup = relation.get("use_shell_lookup")
    checks = [
        _check(
            "audit_completed",
            "pass" if bool(status.get("completed", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "solver_not_invoked",
            "pass" if metadata.get("solver_invoked") is False else "fail",
            str(metadata.get("solver_invoked")),
        ),
        _check(
            "proof_source_false",
            "pass" if metadata.get("proof_source") is False else "fail",
            str(metadata.get("proof_source")),
        ),
        _check(
            "candidate_elimination_claim_false",
            "pass"
            if metadata.get("candidate_elimination_claim") is False
            else "fail",
            str(metadata.get("candidate_elimination_claim")),
        ),
        _check(
            "shell_lookup_available",
            "pass" if use_shell_lookup is True else "skipped",
            str(use_shell_lookup),
        ),
    ]
    if use_shell_lookup is True:
        checks.extend(
            [
                _check(
                    "linear_shell_guards_relation_equivalent",
                    "pass" if linear.get("equivalent") is True else "fail",
                    str(linear.get("equivalent")),
                ),
                _check(
                    "shell_pair_index_relation_equivalent",
                    "pass" if shell_pair.get("equivalent") is True else "fail",
                    str(shell_pair.get("equivalent")),
                ),
                _check(
                    "active_relation_excludes_sentinel",
                    "pass"
                    if sentinel.get("active_relation_excludes_sentinel") is True
                    else "fail",
                    str(sentinel.get("sentinel_family")),
                ),
            ]
        )
    return checks


def _normalize_shell_lookup_rows(
    shell_lookup_rows: Sequence[Sequence[int]],
) -> list[Tuple[int, int, int]]:
    return sorted(
        {
            (int(row[0]), int(row[1]), int(row[2]))
            for row in list(shell_lookup_rows or [])
            if isinstance(row, (list, tuple)) and len(row) == 3
        }
    )


def _pairs_from_family_shell_guard_shape(shape: Mapping[str, Any]) -> set[Tuple[int, int]]:
    kind = str(shape.get("kind"))
    if kind == "empty":
        return set()
    if kind == "single":
        return {(int(shape["d_lo"]), int(shape["d_hi"]))}
    if kind == "fallback_table":
        return {
            (int(row[0]), int(row[1]))
            for row in list(shape.get("rows", []))
            if isinstance(row, (list, tuple)) and len(row) == 2
        }
    if kind in {"rectangle", "upper_triangle"}:
        d_lo_min = int(shape["d_lo_min"])
        d_lo_max = int(shape["d_lo_max"])
        d_hi_min = int(shape["d_hi_min"])
        d_hi_max = int(shape["d_hi_max"])
        pairs = {
            (int(d_lo), int(d_hi))
            for d_lo in range(d_lo_min, d_lo_max + 1)
            for d_hi in range(d_hi_min, d_hi_max + 1)
        }
        if kind == "upper_triangle":
            pairs = {(d_lo, d_hi) for d_lo, d_hi in pairs if d_lo <= d_hi}
        return pairs
    return set()


def _parse_candidate(candidate: str) -> Tuple[int, int]:
    raw = str(candidate).lower().strip()
    if "x" not in raw:
        raise ValueError(f"Unsupported candidate {candidate!r}; expected <w>x<h>.")
    w_text, h_text = raw.split("x", 1)
    ghost_w = int(w_text)
    ghost_h = int(h_text)
    if ghost_w <= 0 or ghost_h <= 0:
        raise ValueError(f"Unsupported candidate {candidate!r}; dimensions must be positive.")
    return ghost_w, ghost_h


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
