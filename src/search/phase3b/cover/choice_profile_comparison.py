from __future__ import annotations

import copy
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence

from src.models.exact_coordinate_master import (
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
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
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
)
from src.search.phase3b.forced_anchor.model_slice import (
    _build_exact_overlay,
    _candidate_ghost_rect,
)
from src.search.phase3b.forced_anchor.proto_reduction import _proto_profile


COVER_CHOICE_PROFILE_COMPARISON_SOURCE = "phase3b_cover_choice_profile_comparison_v1"
DEFAULT_COVER_CHOICE_CANDIDATE = "67x13"
DEFAULT_PROTOCOL_BLOCK_TEMPLATES = ("protocol_storage_box",)


def build_phase3b_cover_choice_profile_comparison(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_COVER_CHOICE_CANDIDATE,
    block_size: int = 64,
    protocol_block_templates: Sequence[str] = DEFAULT_PROTOCOL_BLOCK_TEMPLATES,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(str(candidate)))
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Cover-choice profile comparison has not run.",
    }
    cases: list[Dict[str, Any]] = []
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; no-solve profile comparison skipped.",
            }
        )
    elif not record:
        status.update(
            {
                "completed": True,
                "outcome": "candidate_missing",
                "recommendation": "Candidate is not present in campaign state; no-solve profile comparison skipped.",
            }
        )
    else:
        try:
            ghost_rect = _candidate_ghost_rect(str(candidate), record)
            case_defs = (
                {
                    "case_id": "protocol_storage_box_only",
                    "block_templates": ",".join(
                        str(template) for template in protocol_block_templates
                    ),
                    "block_geometry": EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET,
                },
                {
                    "case_id": "all_powered_templates",
                    "block_templates": "",
                    "block_geometry": EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET,
                },
                {
                    "case_id": "all_powered_templates_selected_block",
                    "block_templates": "",
                    "block_geometry": EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK,
                },
                {
                    "case_id": "all_powered_templates_selected_block_active_guard",
                    "block_templates": "",
                    "block_geometry": EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
                },
            )
            for case_def in case_defs:
                cases.append(
                    _build_cover_choice_profile_case(
                        project_root,
                        ghost_rect=ghost_rect,
                        case_id=str(case_def["case_id"]),
                        block_size=int(block_size),
                        block_templates=str(case_def["block_templates"]),
                        block_geometry=str(case_def["block_geometry"]),
                        master_search_profile=str(master_search_profile),
                    )
                )
            status.update(_status_from_cases(cases))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "no_solve_profile_error",
                    "recommendation": "No-solve cover-choice profile comparison failed; inspect model_error.",
                }
            )

    after_hash = _file_hash(campaign_path)
    report = {
        "metadata": {
            "source": COVER_CHOICE_PROFILE_COMPARISON_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "proto_build_profile_not_proof_source",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": str(candidate),
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "block_size": int(block_size),
            "protocol_block_templates": [str(template) for template in protocol_block_templates],
            "compared_cases": [case.get("case_id") for case in cases],
        },
        "solver_invoked": False,
        "status": status,
        "cases": cases,
        "comparison": _comparison_payload(cases),
        "final_target_channel_assessment": _final_target_channel_assessment(cases),
        "timing": {
            "total_seconds": float(time.perf_counter() - started),
        },
        "model_error": model_error,
        "campaign_state_unchanged": bool(before_hash == after_hash),
    }
    report["checks"] = _checks(
        state_present=state is not None and state_error is None,
        candidate_present=bool(record),
        status=status,
        solver_invoked=False,
        campaign_state_unchanged=bool(before_hash == after_hash),
        model_error=model_error,
    )
    return report


def render_phase3b_cover_choice_profile_comparison_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    assessment = _mapping(report.get("final_target_channel_assessment"))
    lines = [
        "# Phase 3B Cover-Choice Profile Comparison",
        "",
        "- Diagnostic semantics: proto_build_profile_not_proof_source",
        f"- solver_invoked: {bool(report.get('solver_invoked', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Cases",
        "",
        "| Case | Proto vars | Elements | BoolOr | Cover vars | Wide idx | Final target | Block idx | Local idx | Local selected | Block target | Block selected |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in _case_mappings(report):
        profile = _mapping(case.get("proto_profile"))
        cover = _mapping(case.get("cover_choice_profile"))
        mode_counts = _mapping(cover.get("mode_counts"))
        target = _mapping(cover.get("target_channel_profile"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(case.get("case_id")),
                    _markdown_cell(profile.get("variable_count")),
                    _markdown_cell(case.get("element_count")),
                    _markdown_cell(_mapping(profile.get("constraint_kind_counts")).get("bool_or")),
                    _markdown_cell(cover.get("total_cover_choice_variables")),
                    _markdown_cell(mode_counts.get("wide_idx")),
                    _markdown_cell(target.get("final_target_channel_variables")),
                    _markdown_cell(mode_counts.get("block_idx")),
                    _markdown_cell(mode_counts.get("block_local_idx")),
                    _markdown_cell(mode_counts.get("block_local_selected")),
                    _markdown_cell(mode_counts.get("block_target")),
                    _markdown_cell(mode_counts.get("block_selected")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Cover-Choice Details", ""])
    for case in _case_mappings(report):
        cover = _mapping(case.get("cover_choice_profile"))
        lines.extend(
            [
                f"### {_markdown_cell(case.get('case_id'))}",
                "",
                f"- mode_counts: {_markdown_cell(_mapping(cover.get('mode_counts')))}",
                f"- role_counts: {_markdown_cell(_mapping(cover.get('role_counts')))}",
                f"- target_channel_profile: {_markdown_cell(_mapping(cover.get('target_channel_profile')))}",
                f"- template_counts: {_markdown_cell(_mapping(cover.get('template_counts')))}",
                "",
            ]
        )
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            f"- Proto variable delta: {comparison.get('proto_variable_delta_all_templates_minus_protocol_only')}",
            f"- Element delta: {comparison.get('element_delta_all_templates_minus_protocol_only')}",
            f"- Wide idx delta: {comparison.get('wide_idx_delta_all_templates_minus_protocol_only')}",
            f"- Final target delta: {comparison.get('final_target_delta_all_templates_minus_protocol_only')}",
            "",
            "## Final Target Channel Assessment",
            "",
            f"- Verdict: {assessment.get('verdict')}",
            f"- Safe patch available: {bool(assessment.get('safe_patch_available', False))}",
        ]
    )
    for reason in list(assessment.get("reasons", [])):
        lines.append(f"- {reason}")
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
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


def render_phase3b_cover_choice_profile_comparison_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    assessment = _mapping(report.get("final_target_channel_assessment"))
    lines = [
        "Phase 3B cover-choice profile comparison",
        "diagnostic_semantics=proto_build_profile_not_proof_source",
        f"solver_invoked={bool(report.get('solver_invoked', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for case in _case_mappings(report):
        profile = _mapping(case.get("proto_profile"))
        cover = _mapping(case.get("cover_choice_profile"))
        mode_counts = _mapping(cover.get("mode_counts"))
        role_counts = _mapping(cover.get("role_counts"))
        target = _mapping(cover.get("target_channel_profile"))
        lines.append(
            "case "
            f"id={case.get('case_id')} "
            f"proto_vars={profile.get('variable_count')} "
            f"elements={case.get('element_count')} "
            f"cover_vars={cover.get('total_cover_choice_variables')} "
            f"wide_idx={mode_counts.get('wide_idx')} "
            f"wide_target={mode_counts.get('wide_target')} "
            f"final_target={target.get('final_target_channel_variables')} "
            f"block_target={mode_counts.get('block_target')} "
            f"local_selected={mode_counts.get('block_local_selected')} "
            f"block_selected={mode_counts.get('block_selected')} "
            f"role_counts={dict(role_counts)}"
        )
        lines.append(
            "case_detail "
            f"id={case.get('case_id')} "
            f"mode_counts={dict(mode_counts)} "
            f"role_counts={dict(role_counts)} "
            f"target_channel_profile={dict(target)} "
            f"template_counts={dict(_mapping(cover.get('template_counts')))}"
        )
    lines.append(f"comparison={dict(comparison)}")
    lines.append(f"final_target_verdict={assessment.get('verdict')}")
    for reason in list(assessment.get("reasons", [])):
        lines.append(f"reason={reason}")
    return "\n".join(lines) + "\n"


def _build_cover_choice_profile_case(
    project_root: Path,
    *,
    ghost_rect: Mapping[str, Any],
    case_id: str,
    block_size: int,
    block_templates: str,
    block_geometry: str,
    master_search_profile: str,
) -> Dict[str, Any]:
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
        model, base_proto = _build_exact_overlay(
            project_root,
            ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
            master_search_profile=str(master_search_profile),
        )
        proto_profile = _proto_profile(base_proto)
    constraint_counts = _mapping(proto_profile.get("constraint_kind_counts"))
    cover_choice = _mapping(proto_profile.get("cover_choice_profile"))
    return {
        "case_id": str(case_id),
        "solver_invoked": False,
        "env": dict(env),
        "build_seconds": float(time.perf_counter() - started),
        "proto_profile": proto_profile,
        "cover_choice_profile": copy.deepcopy(cover_choice),
        "power_coverage_build_stats": copy.deepcopy(
            _mapping(getattr(model, "build_stats", {}).get("power_coverage"))
        ),
        "proto_variable_count": int(proto_profile.get("variable_count", 0)),
        "element_count": int(constraint_counts.get("element", 0)),
        "cover_choice_mode_counts": copy.deepcopy(_mapping(cover_choice.get("mode_counts"))),
        "cover_choice_role_counts": copy.deepcopy(_mapping(cover_choice.get("role_counts"))),
        "target_channel_profile": copy.deepcopy(
            _mapping(cover_choice.get("target_channel_profile"))
        ),
        "template_counts": copy.deepcopy(_mapping(cover_choice.get("template_counts"))),
    }


def _comparison_payload(cases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_id = {str(case.get("case_id")): case for case in cases if isinstance(case, Mapping)}
    protocol = _mapping(by_id.get("protocol_storage_box_only"))
    all_templates = _mapping(by_id.get("all_powered_templates"))
    selected_block = _mapping(by_id.get("all_powered_templates_selected_block"))
    active_guard = _mapping(
        by_id.get("all_powered_templates_selected_block_active_guard")
    )
    protocol_cover = _mapping(protocol.get("cover_choice_profile"))
    all_cover = _mapping(all_templates.get("cover_choice_profile"))
    selected_cover = _mapping(selected_block.get("cover_choice_profile"))
    active_guard_cover = _mapping(active_guard.get("cover_choice_profile"))
    protocol_modes = _mapping(protocol_cover.get("mode_counts"))
    all_modes = _mapping(all_cover.get("mode_counts"))
    selected_modes = _mapping(selected_cover.get("mode_counts"))
    active_guard_modes = _mapping(active_guard_cover.get("mode_counts"))
    protocol_target = _mapping(protocol_cover.get("target_channel_profile"))
    all_target = _mapping(all_cover.get("target_channel_profile"))
    selected_target = _mapping(selected_cover.get("target_channel_profile"))
    active_guard_target = _mapping(
        active_guard_cover.get("target_channel_profile")
    )
    selected_block_present = bool(selected_block)
    active_guard_present = bool(active_guard)
    return {
        "case_ids": sorted(by_id),
        "proto_variable_delta_all_templates_minus_protocol_only": _int_value(
            all_templates.get("proto_variable_count")
        )
        - _int_value(protocol.get("proto_variable_count")),
        "element_delta_all_templates_minus_protocol_only": _int_value(
            all_templates.get("element_count")
        )
        - _int_value(protocol.get("element_count")),
        "cover_choice_variable_delta_all_templates_minus_protocol_only": _int_value(
            all_cover.get("total_cover_choice_variables")
        )
        - _int_value(protocol_cover.get("total_cover_choice_variables")),
        "wide_idx_delta_all_templates_minus_protocol_only": _int_value(
            all_modes.get("wide_idx")
        )
        - _int_value(protocol_modes.get("wide_idx")),
        "wide_target_delta_all_templates_minus_protocol_only": _int_value(
            all_modes.get("wide_target")
        )
        - _int_value(protocol_modes.get("wide_target")),
        "final_target_delta_all_templates_minus_protocol_only": _int_value(
            all_target.get("final_target_channel_variables")
        )
        - _int_value(protocol_target.get("final_target_channel_variables")),
        "block_target_delta_all_templates_minus_protocol_only": _int_value(
            all_modes.get("block_target")
        )
        - _int_value(protocol_modes.get("block_target")),
        "proto_variable_delta_selected_block_minus_all_templates": _int_value(
            selected_block.get("proto_variable_count")
        )
        - _int_value(all_templates.get("proto_variable_count"))
        if selected_block_present
        else None,
        "element_delta_selected_block_minus_all_templates": _int_value(
            selected_block.get("element_count")
        )
        - _int_value(all_templates.get("element_count"))
        if selected_block_present
        else None,
        "final_target_delta_selected_block_minus_all_templates": _int_value(
            selected_target.get("final_target_channel_variables")
        )
        - _int_value(all_target.get("final_target_channel_variables"))
        if selected_block_present
        else None,
        "block_selected_literal_delta_selected_block_minus_all_templates": _int_value(
            selected_target.get("block_selected_literal_variables")
        )
        - _int_value(all_target.get("block_selected_literal_variables"))
        if selected_block_present
        else None,
        "block_selected_mode_delta_selected_block_minus_all_templates": _int_value(
            selected_modes.get("block_selected")
        )
        - _int_value(all_modes.get("block_selected"))
        if selected_block_present
        else None,
        "proto_variable_delta_active_guard_minus_selected_block": _int_value(
            active_guard.get("proto_variable_count")
        )
        - _int_value(selected_block.get("proto_variable_count"))
        if active_guard_present and selected_block_present
        else None,
        "element_delta_active_guard_minus_selected_block": _int_value(
            active_guard.get("element_count")
        )
        - _int_value(selected_block.get("element_count"))
        if active_guard_present and selected_block_present
        else None,
        "bool_or_delta_active_guard_minus_selected_block": _int_value(
            _mapping(active_guard.get("proto_profile"))
            .get("constraint_kind_counts", {})
            .get("bool_or")
        )
        - _int_value(
            _mapping(selected_block.get("proto_profile"))
            .get("constraint_kind_counts", {})
            .get("bool_or")
        )
        if active_guard_present and selected_block_present
        else None,
        "block_target_delta_active_guard_minus_selected_block": _int_value(
            active_guard_modes.get("block_target")
        )
        - _int_value(selected_modes.get("block_target"))
        if active_guard_present and selected_block_present
        else None,
        "local_selected_delta_active_guard_minus_selected_block": _int_value(
            active_guard_target.get("local_selected_literal_variables")
        )
        - _int_value(selected_target.get("local_selected_literal_variables"))
        if active_guard_present and selected_block_present
        else None,
    }


def _final_target_channel_assessment(
    cases: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    total_final_targets = 0
    cases_with_final_targets: list[str] = []
    selected_block_case: Mapping[str, Any] = {}
    active_guard_case: Mapping[str, Any] = {}
    all_templates_case: Mapping[str, Any] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            continue
        case_id = str(case.get("case_id"))
        if case_id == "all_powered_templates_selected_block":
            selected_block_case = case
        elif case_id == "all_powered_templates_selected_block_active_guard":
            active_guard_case = case
        elif case_id == "all_powered_templates":
            all_templates_case = case
        target = _mapping(case.get("target_channel_profile"))
        final_count = _int_value(target.get("final_target_channel_variables"))
        total_final_targets += int(final_count)
        if final_count:
            cases_with_final_targets.append(str(case.get("case_id")))
    selected_target = _mapping(selected_block_case.get("target_channel_profile"))
    active_guard_target = _mapping(active_guard_case.get("target_channel_profile"))
    selected_profile = _mapping(selected_block_case.get("proto_profile"))
    active_guard_profile = _mapping(active_guard_case.get("proto_profile"))
    selected_constraint_counts = _mapping(selected_profile.get("constraint_kind_counts"))
    active_guard_constraint_counts = _mapping(
        active_guard_profile.get("constraint_kind_counts")
    )
    all_target = _mapping(all_templates_case.get("target_channel_profile"))
    active_guard_reduces_block_targets = (
        bool(active_guard_case)
        and _int_value(active_guard_target.get("block_intermediate_target_channel_variables"))
        < _int_value(selected_target.get("block_intermediate_target_channel_variables"))
    )
    if selected_block_case and all_templates_case and _int_value(
        selected_target.get("final_target_channel_variables")
    ) == 0 and _int_value(all_target.get("final_target_channel_variables")) > 0:
        reasons = [
            "A default-off selected_block geometry profile removes final cover_choice_active/x/y target channels for all-template block-mode witnesses in the no-solve build.",
            "The selected_block profile preserves block/local witness selection and replaces the final target join with selected-block reified geometry constraints.",
            "This remains a formulation experiment, not proof evidence; it still needs focused equivalence tests and bounded diagnostic solver comparison before any production use.",
        ]
        verdict = "selected_block_default_off_candidate_identified"
        active_guard_payload: Dict[str, Any] = {}
        if active_guard_case:
            active_guard_payload = {
                "case_present": True,
                "block_intermediate_target_delta": _int_value(
                    active_guard_target.get("block_intermediate_target_channel_variables")
                )
                - _int_value(
                    selected_target.get("block_intermediate_target_channel_variables")
                ),
                "local_selected_literal_delta": _int_value(
                    active_guard_target.get("local_selected_literal_variables")
                )
                - _int_value(selected_target.get("local_selected_literal_variables")),
                "element_delta": _int_value(active_guard_case.get("element_count"))
                - _int_value(selected_block_case.get("element_count")),
                "bool_or_delta": _int_value(active_guard_constraint_counts.get("bool_or"))
                - _int_value(selected_constraint_counts.get("bool_or")),
                "reduces_block_intermediate_targets": active_guard_reduces_block_targets,
            }
            verdict = "active_guard_default_off_candidate_identified"
            reasons.append(
                "A default-off selected_block_active_guard profile also removes active block intermediate target channels, but it adds a large Boolean guard layer and must remain diagnostic until equivalence/probe gates pass."
            )
        return {
            "verdict": verdict,
            "safe_patch_available": True,
            "diagnostic_deletion_rejected": True,
            "cases_with_final_target_channels": cases_with_final_targets,
            "observed_final_target_channel_variables_total": int(total_final_targets),
            "active_guard_assessment": active_guard_payload,
            "reasons": reasons,
            "next_safe_probe": (
                "Review selected_block build stats, then run bounded diagnostic profiles "
                "only after focused tests pass."
            ),
        }
    return {
        "verdict": "no_safe_default_off_compact_encoding_identified",
        "safe_patch_available": False,
        "diagnostic_deletion_rejected": True,
        "cases_with_final_target_channels": cases_with_final_targets,
        "observed_final_target_channel_variables_total": int(total_final_targets),
        "reasons": [
            "cover_choice_active/x/y are consumed by shared geometry constraints after witness selection, so removing them would require duplicating or reifying the same geometry per block or per pole choice.",
            "The current block_element encoding already compresses wide selector arrays into block/local selectors; the final target channels are the join point that preserves one selected active/x/y tuple for downstream exact geometry constraints.",
            "A direct deletion of x/y target channels is diagnostic-only because prior evidence shows protocol position-universality fails; coordinate geometry cannot be dropped proof-safely.",
            "A compact equivalent encoding would need a new proof that block-level geometry decomposition preserves the same selected pole semantics without increasing a larger literal matrix; that proof and implementation are not established in this no-solve pass.",
        ],
        "next_safe_probe": (
            "Prototype a guarded block-level geometry decomposition only behind a new env var, "
            "then compare proto profile and equivalence tests before any solver claims."
        ),
    }


def _status_from_cases(cases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not cases:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_cases_built",
            "recommendation": "No profile cases were built.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "no_solve_profile_comparison_built",
        "recommendation": (
            "Use this no-solve comparison to track cover-choice formulation shape; "
            "do not treat it as proof or solver progress."
        ),
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    status: Mapping[str, Any],
    solver_invoked: bool,
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing",
        ),
        _check(
            "candidate_present",
            "pass" if candidate_present else "fail",
            "candidate loaded" if candidate_present else "candidate missing",
        ),
        _check(
            "no_solve_analysis",
            "pass" if not solver_invoked else "fail",
            "solver_invoked=false" if not solver_invoked else "solver was invoked",
        ),
        _check(
            "diagnostic_not_proof_source",
            "pass",
            "proof_source=false; candidate_elimination_claim=false",
        ),
        _check(
            "profile_comparison_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state hash unchanged"
            if campaign_state_unchanged
            else "campaign state changed during no-solve profile comparison",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


@contextmanager
def _temporary_env(overrides: Mapping[str, str]) -> Iterator[None]:
    saved = {str(key): os.environ.get(str(key)) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(str(key), None)
            else:
                os.environ[str(key)] = str(value)


def _case_mappings(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [case for case in list(report.get("cases", [])) if isinstance(case, Mapping)]


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")
