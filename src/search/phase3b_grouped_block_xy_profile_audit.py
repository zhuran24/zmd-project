from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional

from src.models.exact_coordinate_master import (
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV,
    EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT,
    EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV,
    EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV,
    EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS,
    EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV,
    EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX,
)
from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import _build_exact_overlay, _check, _display_path, _mapping
from src.search.phase3b_forced_anchor_proto_reduction import _proto_profile

GROUPED_BLOCK_XY_PROFILE_AUDIT_SOURCE = "phase3b_grouped_block_xy_profile_audit_v1"
DEFAULT_GROUPED_BLOCK_XY_CANDIDATE = "67x13"


def build_phase3b_grouped_block_xy_profile_audit(
    project_root: Path,
    *,
    candidate: str = DEFAULT_GROUPED_BLOCK_XY_CANDIDATE,
    block_size: int = 64,
    block_templates: str = "",
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    ghost_w, ghost_h = _parse_candidate(candidate)
    model_error: Optional[str] = None
    cases: list[dict[str, Any]] = []
    comparison: dict[str, Any] = {}
    try:
        cases = [
            _build_case(
                project_root,
                case_id="selected_block_active_guard",
                block_geometry=EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
                ghost_rect=(ghost_w, ghost_h),
                block_size=block_size,
                block_templates=block_templates,
                master_search_profile=master_search_profile,
            ),
            _build_case(
                project_root,
                case_id="selected_block_active_guard_grouped_xy",
                block_geometry=EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY,
                ghost_rect=(ghost_w, ghost_h),
                block_size=block_size,
                block_templates=block_templates,
                master_search_profile=master_search_profile,
            ),
        ]
        comparison = _comparison(cases)
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"
    ready = bool(comparison.get("grouped_xy_profile_valid", False))
    report: dict[str, Any] = {
        "metadata": {
            "source": GROUPED_BLOCK_XY_PROFILE_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_grouped_xy_profile_audit",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {"project_root": _display_path(project_root, project_root)},
        "candidate": {
            "key": f"{ghost_w}x{ghost_h}",
            "ghost_rect": {"w": int(ghost_w), "h": int(ghost_h)},
        },
        "profile": {
            "block_size": int(block_size),
            "block_templates": str(block_templates),
            "master_search_profile": str(master_search_profile),
        },
        "status": {
            "completed": True,
            "evaluated": bool(cases and comparison and not model_error),
            "outcome": (
                "grouped_block_xy_profile_audit_passed"
                if ready
                else (
                    "grouped_block_xy_profile_audit_failed"
                    if cases and comparison
                    else "grouped_block_xy_profile_audit_incomplete"
                )
            ),
            "recommendation": (
                "run_bounded_grouped_xy_probe"
                if ready
                else "inspect_grouped_xy_profile_audit_failure"
            ),
        },
        "cases": cases,
        "comparison": comparison,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
    }
    report["checks"] = _checks(report)
    return report


def render_phase3b_grouped_block_xy_profile_audit_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "# Phase 3B Grouped Block X/Y Profile Audit",
        "",
        "- Diagnostic semantics: no_solve_grouped_xy_profile_audit",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Cases",
        "",
        "| Case | Vars | Constraints | Block x/y targets | Elements | Active Guards | Block Selected | Local Selected | Grouped x/y Targets |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in list(report.get("cases", [])):
        if not isinstance(case, Mapping):
            continue
        witness = _mapping(case.get("witness_stats"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(case.get("case_id")),
                    _cell(case.get("proto_variable_count")),
                    _cell(case.get("proto_constraint_count")),
                    _cell(witness.get("block_intermediate_target_channel_count")),
                    _cell(witness.get("block_element_constraint_count")),
                    _cell(witness.get("block_active_guard_clause_count")),
                    _cell(witness.get("block_selected_literal_count")),
                    _cell(witness.get("local_selected_literal_count")),
                    _cell(witness.get("grouped_xy_target_channel_count")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            f"- Grouped profile valid: {comparison.get('grouped_xy_profile_valid')}",
            f"- Block x/y target delta: {comparison.get('block_xy_target_delta')}",
            f"- Element delta: {comparison.get('block_element_constraint_delta')}",
            f"- Selected geometry delta: {comparison.get('selected_geometry_constraint_delta')}",
            f"- Active guard unchanged: {comparison.get('active_guard_clause_count_unchanged')}",
            f"- Block/local selector unchanged: {comparison.get('block_local_selector_counts_unchanged')}",
            f"- Per-block x/y removed: {comparison.get('per_block_xy_variables_removed')}",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.get("check_id")),
                        _cell(check.get("status")),
                        _cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_grouped_block_xy_profile_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    return "\n".join(
        [
            "phase3b grouped block x/y profile audit",
            "diagnostic_semantics=no_solve_grouped_xy_profile_audit",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"grouped_xy_profile_valid={comparison.get('grouped_xy_profile_valid')}",
            f"block_xy_target_delta={comparison.get('block_xy_target_delta')}",
            f"block_element_constraint_delta={comparison.get('block_element_constraint_delta')}",
            f"per_block_xy_variables_removed={comparison.get('per_block_xy_variables_removed')}",
        ]
    ) + "\n"


def _build_case(
    project_root: Path,
    *,
    case_id: str,
    block_geometry: str,
    ghost_rect: tuple[int, int],
    block_size: int,
    block_templates: str,
    master_search_profile: str,
) -> dict[str, Any]:
    env = {
        EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV: EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS,
        EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV: EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX,
        EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV: EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT,
        EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV: str(block_geometry),
        EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV: str(int(block_size)),
        EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV: str(block_templates),
    }
    started = time.perf_counter()
    with _temporary_env(env):
        model, proto = _build_exact_overlay(
            project_root,
            ghost_rect=(int(ghost_rect[0]), int(ghost_rect[1])),
            master_search_profile=str(master_search_profile),
        )
        profile = _proto_profile(proto)
    variables = [str(variable.name) for variable in proto.variables]
    witness_stats = dict(
        _mapping(_mapping(model.build_stats.get("power_coverage")).get("witness_encoding"))
    )
    power_coverage = _mapping(model.build_stats.get("power_coverage"))
    return {
        "case_id": str(case_id),
        "block_geometry": str(block_geometry),
        "env": env,
        "solver_invoked": False,
        "build_seconds": float(time.perf_counter() - started),
        "proto_variable_count": int(profile.get("variable_count", 0) or 0),
        "proto_constraint_count": int(profile.get("constraint_count", 0) or 0),
        "proto_profile": profile,
        "witness_stats": witness_stats,
        "power_coverage_cover_literals": int(power_coverage.get("cover_literals", 0) or 0),
        "variable_prefix_counts": {
            "cover_choice_block_x__": _prefix_count(variables, "cover_choice_block_x__"),
            "cover_choice_block_y__": _prefix_count(variables, "cover_choice_block_y__"),
            "cover_choice_block_active__": _prefix_count(variables, "cover_choice_block_active__"),
            "cover_choice_grouped_x__": _prefix_count(variables, "cover_choice_grouped_x__"),
            "cover_choice_grouped_y__": _prefix_count(variables, "cover_choice_grouped_y__"),
            "cover_choice_padded_idx__": _prefix_count(variables, "cover_choice_padded_idx__"),
            "cover_literal__": _prefix_count(variables, "cover_literal__"),
            "covers__": _prefix_count(variables, "covers__"),
        },
    }


def _comparison(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {str(case.get("case_id")): case for case in cases}
    old = _mapping(by_id.get("selected_block_active_guard"))
    new = _mapping(by_id.get("selected_block_active_guard_grouped_xy"))
    old_w = _mapping(old.get("witness_stats"))
    new_w = _mapping(new.get("witness_stats"))
    old_prefix = _mapping(old.get("variable_prefix_counts"))
    new_prefix = _mapping(new.get("variable_prefix_counts"))
    block_xy_delta = _int(new_w.get("block_intermediate_target_channel_count")) - _int(
        old_w.get("block_intermediate_target_channel_count")
    )
    element_delta = _int(new_w.get("block_element_constraint_count")) - _int(
        old_w.get("block_element_constraint_count")
    )
    selected_geometry_delta = _int(
        new_w.get("grouped_xy_selected_geometry_constraint_count")
    ) - _int(old_w.get("block_selected_geometry_constraint_count"))
    active_guard_unchanged = _int(new_w.get("block_active_guard_clause_count")) == _int(
        old_w.get("block_active_guard_clause_count")
    )
    selectors_unchanged = (
        _int(new_w.get("block_selected_literal_count"))
        == _int(old_w.get("block_selected_literal_count"))
        and _int(new_w.get("local_selected_literal_count"))
        == _int(old_w.get("local_selected_literal_count"))
    )
    per_block_removed = (
        _int(new_prefix.get("cover_choice_block_x__")) == 0
        and _int(new_prefix.get("cover_choice_block_y__")) == 0
        and _int(new_prefix.get("cover_choice_block_active__")) == 0
    )
    grouped_targets_present = (
        _int(new_prefix.get("cover_choice_grouped_x__")) > 0
        and _int(new_prefix.get("cover_choice_grouped_y__")) > 0
        and _int(new_prefix.get("cover_choice_padded_idx__")) > 0
    )
    no_pairwise_literals = (
        _int(new_prefix.get("cover_literal__")) == 0
        and _int(new_prefix.get("covers__")) == 0
        and _int(new.get("power_coverage_cover_literals")) == 0
    )
    target_delta_negative = block_xy_delta < 0
    element_delta_negative = element_delta < 0
    selected_geometry_delta_negative = selected_geometry_delta < 0
    valid = (
        bool(new)
        and bool(old)
        and str(new_w.get("block_geometry_mode"))
        == EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY
        and _int(new_w.get("final_target_channel_count")) == 0
        and _int(new_w.get("block_final_join_element_constraint_count")) == 0
        and _int(new_w.get("grouped_xy_target_channel_count")) > 0
        and _int(new_w.get("grouped_xy_element_constraint_count")) > 0
        and active_guard_unchanged
        and selectors_unchanged
        and per_block_removed
        and grouped_targets_present
        and no_pairwise_literals
        and target_delta_negative
        and element_delta_negative
        and selected_geometry_delta_negative
    )
    return {
        "grouped_xy_profile_valid": bool(valid),
        "block_xy_target_delta": int(block_xy_delta),
        "block_element_constraint_delta": int(element_delta),
        "selected_geometry_constraint_delta": int(selected_geometry_delta),
        "active_guard_clause_count_unchanged": bool(active_guard_unchanged),
        "block_local_selector_counts_unchanged": bool(selectors_unchanged),
        "per_block_xy_variables_removed": bool(per_block_removed),
        "grouped_xy_targets_present": bool(grouped_targets_present),
        "no_pairwise_cover_literals": bool(no_pairwise_literals),
        "target_delta_negative": bool(target_delta_negative),
        "element_delta_negative": bool(element_delta_negative),
        "selected_geometry_delta_negative": bool(selected_geometry_delta_negative),
    }


def _checks(report: Mapping[str, Any]) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    comparison = _mapping(report.get("comparison"))
    return [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("cases_built", "pass" if len(list(report.get("cases", []))) == 2 else "fail", f"case_count={len(list(report.get('cases', [])))}"),
        _check("grouped_xy_profile_valid", "pass" if bool(comparison.get("grouped_xy_profile_valid", False)) else "fail", str(comparison)),
        _check("active_guard_unchanged", "pass" if bool(comparison.get("active_guard_clause_count_unchanged", False)) else "fail", str(comparison.get("active_guard_clause_count_unchanged"))),
        _check("selectors_unchanged", "pass" if bool(comparison.get("block_local_selector_counts_unchanged", False)) else "fail", str(comparison.get("block_local_selector_counts_unchanged"))),
        _check("per_block_xy_removed", "pass" if bool(comparison.get("per_block_xy_variables_removed", False)) else "fail", str(comparison.get("per_block_xy_variables_removed"))),
        _check("no_pairwise_literals", "pass" if bool(comparison.get("no_pairwise_cover_literals", False)) else "fail", str(comparison.get("no_pairwise_cover_literals"))),
        _check("target_delta_negative", "pass" if bool(comparison.get("target_delta_negative", False)) else "fail", str(comparison.get("block_xy_target_delta"))),
        _check("element_delta_negative", "pass" if bool(comparison.get("element_delta_negative", False)) else "fail", str(comparison.get("block_element_constraint_delta"))),
        _check("selected_geometry_delta_negative", "pass" if bool(comparison.get("selected_geometry_delta_negative", False)) else "fail", str(comparison.get("selected_geometry_constraint_delta"))),
    ]


def _parse_candidate(candidate: str) -> tuple[int, int]:
    raw = str(candidate).lower().strip()
    if "x" not in raw:
        raise ValueError(f"candidate must be like 67x13: {candidate!r}")
    left, right = raw.split("x", 1)
    return int(left), int(right)


@contextmanager
def _temporary_env(values: Mapping[str, str]) -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _prefix_count(values: list[str], prefix: str) -> int:
    return sum(1 for value in values if str(value).startswith(prefix))


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
