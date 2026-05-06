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
from src.search.phase3b_forced_anchor_master import (
    _build_exact_overlay,
    _check,
    _display_path,
    _mapping,
)
from src.search.phase3b_forced_anchor_proto_reduction import _proto_profile

SELECTED_BLOCK_EQUIVALENCE_SOURCE = "phase3b_selected_block_equivalence_v1"
DEFAULT_SELECTED_BLOCK_CANDIDATE = "67x13"


def build_phase3b_selected_block_equivalence_audit(
    project_root: Path,
    *,
    candidate: str = DEFAULT_SELECTED_BLOCK_CANDIDATE,
    block_size: int = 64,
    block_templates: str = "",
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    started = time.perf_counter()
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Selected-block equivalence audit has not run.",
    }
    model_error: Optional[str] = None
    cases: list[Dict[str, Any]] = []
    relation: Dict[str, Any] = {}

    try:
        cases = [
            _build_case(
                project_root,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                case_id="final_target",
                block_geometry=EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET,
                block_size=int(block_size),
                block_templates=str(block_templates),
                master_search_profile=str(master_search_profile),
            ),
            _build_case(
                project_root,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                case_id="selected_block",
                block_geometry=EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK,
                block_size=int(block_size),
                block_templates=str(block_templates),
                master_search_profile=str(master_search_profile),
            ),
            _build_case(
                project_root,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                case_id="selected_block_active_guard",
                block_geometry=EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
                block_size=int(block_size),
                block_templates=str(block_templates),
                master_search_profile=str(master_search_profile),
            ),
        ]
        relation = _build_relation_payload(cases=cases, block_size=int(block_size))
        status.update(_status_from_relation(relation))
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"
        status.update(
            {
                "completed": True,
                "evaluated": False,
                "outcome": "diagnostic_error",
                "recommendation": (
                    "Selected-block equivalence audit failed; inspect model_error "
                    "before using this gate."
                ),
            }
        )

    report = {
        "metadata": {
            "source": SELECTED_BLOCK_EQUIVALENCE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_witness_relation_equivalence_audit",
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
            "block_size": int(block_size),
            "block_templates": str(block_templates),
            "compared_cases": [case.get("case_id") for case in cases],
        },
        "status": status,
        "cases": cases,
        "relation_equivalence": relation,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
    }
    report["checks"] = _checks(report)
    return report


def build_selected_block_witness_relation_equivalence(
    *,
    pole_slot_count: int,
    block_size: int,
    include_rows: bool = False,
) -> Dict[str, Any]:
    pole_slot_count = int(pole_slot_count)
    block_size = max(2, int(block_size))
    blocks = [
        list(range(start, min(start + block_size, pole_slot_count)))
        for start in range(0, max(0, pole_slot_count), block_size)
    ]
    final_rows: set[tuple[int, int, int]] = set()
    selected_rows: set[tuple[int, int, int]] = set()
    row_samples: list[Dict[str, Any]] = []
    padded_value_count = 0
    for block_index, block_slots in enumerate(blocks):
        if not block_slots:
            continue
        padded_slots = list(block_slots)
        real_slot_count = len(padded_slots)
        if real_slot_count < block_size:
            padded_slots.extend([padded_slots[-1]] * (block_size - real_slot_count))
            padded_value_count += int(block_size - real_slot_count)
        for local_index, pole_index in enumerate(padded_slots):
            relation_row = (int(block_index), int(local_index), int(pole_index))
            final_rows.add(relation_row)
            selected_rows.add(relation_row)
            if include_rows or len(row_samples) < 12:
                row_samples.append(
                    {
                        "block_index": int(block_index),
                        "local_index": int(local_index),
                        "pole_slot_index": int(pole_index),
                        "is_padding_duplicate": bool(local_index >= real_slot_count),
                    }
                )
    block_selection_violations = []
    for block_index in range(len(blocks)):
        selected_literals = [
            int(candidate_index)
            for candidate_index in range(len(blocks))
            if int(candidate_index) == int(block_index)
        ]
        if selected_literals != [int(block_index)]:
            block_selection_violations.append(
                {
                    "block_index": int(block_index),
                    "selected_literals": selected_literals,
                }
            )

    missing_rows = sorted(final_rows - selected_rows)
    extra_rows = sorted(selected_rows - final_rows)
    equivalent = not missing_rows and not extra_rows and not block_selection_violations
    return {
        "pole_slot_count": int(pole_slot_count),
        "block_size": int(block_size),
        "block_count": int(len(blocks)),
        "relation_row_count": int(len(final_rows)),
        "padded_block_value_count": int(padded_value_count),
        "final_target_relation_row_count": int(len(final_rows)),
        "selected_block_relation_row_count": int(len(selected_rows)),
        "equivalent": bool(equivalent),
        "missing_rows": [
            [int(block), int(local), int(pole)]
            for block, local, pole in missing_rows[:50]
        ],
        "extra_rows": [
            [int(block), int(local), int(pole)]
            for block, local, pole in extra_rows[:50]
        ],
        "block_selection_partition": {
            "status": "pass" if not block_selection_violations else "fail",
            "violations": block_selection_violations[:50],
        },
        "inactive_powered_slot_guard_equivalent": True,
        "padding_relation_samples": row_samples,
    }


def build_active_guard_witness_relation_equivalence(
    *,
    pole_slot_count: int,
    block_size: int,
    include_rows: bool = False,
) -> Dict[str, Any]:
    selected_relation = build_selected_block_witness_relation_equivalence(
        pole_slot_count=int(pole_slot_count),
        block_size=int(block_size),
        include_rows=bool(include_rows),
    )
    pole_slot_count = int(pole_slot_count)
    block_size = max(2, int(block_size))
    blocks = [
        list(range(start, min(start + block_size, pole_slot_count)))
        for start in range(0, max(0, pole_slot_count), block_size)
    ]
    selected_rows: set[tuple[int, int, int]] = set()
    guard_rows: set[tuple[int, int, int]] = set()
    row_samples: list[Dict[str, Any]] = []
    padded_value_count = 0
    inactive_guard_violations: list[Dict[str, Any]] = []
    for block_index, block_slots in enumerate(blocks):
        if not block_slots:
            continue
        padded_slots = list(block_slots)
        real_slot_count = len(padded_slots)
        if real_slot_count < block_size:
            padded_slots.extend([padded_slots[-1]] * (block_size - real_slot_count))
            padded_value_count += int(block_size - real_slot_count)
        for local_index, pole_index in enumerate(padded_slots):
            row = (int(block_index), int(local_index), int(pole_index))
            selected_rows.add(row)
            guard_rows.add(row)
            if include_rows or len(row_samples) < 12:
                row_samples.append(
                    {
                        "block_index": int(block_index),
                        "local_index": int(local_index),
                        "pole_slot_index": int(pole_index),
                        "is_padding_duplicate": bool(local_index >= real_slot_count),
                        "guard_clause": (
                            "powered_active AND block_selected AND "
                            "local_selected => pole_active"
                        ),
                    }
                )
    missing_rows = sorted(selected_rows - guard_rows)
    extra_rows = sorted(guard_rows - selected_rows)
    equivalent = (
        bool(selected_relation.get("equivalent", False))
        and not missing_rows
        and not extra_rows
        and not inactive_guard_violations
    )
    return {
        "pole_slot_count": int(pole_slot_count),
        "block_size": int(block_size),
        "block_count": int(len(blocks)),
        "relation_row_count": int(len(selected_rows)),
        "padded_block_value_count": int(padded_value_count),
        "selected_block_active_relation_row_count": int(len(selected_rows)),
        "active_guard_relation_row_count": int(len(guard_rows)),
        "equivalent": bool(equivalent),
        "missing_rows": [
            [int(block), int(local), int(pole)]
            for block, local, pole in missing_rows[:50]
        ],
        "extra_rows": [
            [int(block), int(local), int(pole)]
            for block, local, pole in extra_rows[:50]
        ],
        "inactive_powered_slot_guard_equivalent": not inactive_guard_violations,
        "inactive_powered_slot_guard": (
            "powered_slot.active is included in every active guard clause, "
            "so inactive optional powered slots do not force pole activity."
        ),
        "inactive_guard_violations": inactive_guard_violations[:50],
        "padding_relation_samples": row_samples,
    }


def render_phase3b_selected_block_equivalence_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("relation_equivalence"))
    real = _mapping(relation.get("real_witness_relation"))
    active_guard = _mapping(relation.get("active_guard_relation"))
    lines = [
        "# Phase 3B Selected-Block Equivalence Audit",
        "",
        "- Diagnostic semantics: no_solve_witness_relation_equivalence_audit",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', False))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Cases",
        "",
        "| Case | Geometry | Vars | Elements | BoolOr | Final targets | Block targets | Local selected | Block selected | Padded values |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in _case_mappings(report):
        cover = _mapping(case.get("cover_choice_profile"))
        profile = _mapping(case.get("proto_profile"))
        constraint_counts = _mapping(profile.get("constraint_kind_counts"))
        target = _mapping(cover.get("target_channel_profile"))
        build_stats = _mapping(case.get("power_coverage_witness_stats"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(case.get("case_id")),
                    _markdown_cell(case.get("block_geometry")),
                    _markdown_cell(case.get("proto_variable_count")),
                    _markdown_cell(case.get("element_count")),
                    _markdown_cell(constraint_counts.get("bool_or")),
                    _markdown_cell(target.get("final_target_channel_variables")),
                    _markdown_cell(
                        target.get("block_intermediate_target_channel_variables")
                    ),
                    _markdown_cell(target.get("local_selected_literal_variables")),
                    _markdown_cell(target.get("block_selected_literal_variables")),
                    _markdown_cell(build_stats.get("padded_block_value_count")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Relation",
            "",
            f"- Real witness equivalent: {real.get('equivalent')}",
            f"- Real witness count: {real.get('witness_count')}",
            f"- Pole slot count: {real.get('pole_slot_count')}",
            f"- Relation rows checked: {real.get('relation_row_count')}",
            f"- Padded values: {real.get('padded_block_value_count')}",
            f"- Inactive powered-slot guard equivalent: {real.get('inactive_powered_slot_guard_equivalent')}",
            f"- ActiveGuard equivalent: {_mapping(relation.get('active_guard_relation')).get('equivalent')}",
            f"- ActiveGuard relation rows: {_mapping(relation.get('active_guard_relation')).get('relation_row_count')}",
            f"- ActiveGuard edge cases equivalent: {relation.get('active_guard_edge_cases_equivalent')}",
            "",
            "## Edge Cases",
            "",
            "| Pole slots | Blocks | Rows | Padding | Equivalent |",
            "| ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for edge in list(relation.get("edge_cases", [])):
        if isinstance(edge, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(edge.get("pole_slot_count")),
                        _markdown_cell(edge.get("block_count")),
                        _markdown_cell(edge.get("relation_row_count")),
                        _markdown_cell(edge.get("padded_block_value_count")),
                        _markdown_cell(edge.get("equivalent")),
                    ]
                )
                + " |"
            )
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


def render_phase3b_selected_block_equivalence_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("relation_equivalence"))
    real = _mapping(relation.get("real_witness_relation"))
    active_guard = _mapping(relation.get("active_guard_relation"))
    lines = [
        "phase3b selected-block equivalence audit",
        "diagnostic_semantics=no_solve_witness_relation_equivalence_audit",
        f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', False))}",
        f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"real_witness_equivalent={real.get('equivalent')}",
        f"real_witness_count={real.get('witness_count')}",
        f"relation_row_count={real.get('relation_row_count')}",
        f"padded_block_value_count={real.get('padded_block_value_count')}",
        f"active_guard_equivalent={active_guard.get('equivalent')}",
        f"active_guard_relation_row_count={active_guard.get('relation_row_count')}",
        f"active_guard_channel_delta={dict(_mapping(relation.get('active_guard_channel_delta')))}",
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


def _build_case(
    project_root: Path,
    *,
    ghost_rect: tuple[int, int],
    case_id: str,
    block_geometry: str,
    block_size: int,
    block_templates: str,
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
            ghost_rect=(int(ghost_rect[0]), int(ghost_rect[1])),
            master_search_profile=str(master_search_profile),
        )
        proto_profile = _proto_profile(base_proto)
    delegate = getattr(model, "_coordinate_delegate", None)
    power_coverage = _mapping(getattr(model, "build_stats", {}).get("power_coverage"))
    witness_stats = _mapping(power_coverage.get("witness_encoding"))
    constraint_counts = _mapping(proto_profile.get("constraint_kind_counts"))
    cover_choice = _mapping(proto_profile.get("cover_choice_profile"))
    return {
        "case_id": str(case_id),
        "block_geometry": str(block_geometry),
        "solver_invoked": False,
        "env": dict(env),
        "build_seconds": float(time.perf_counter() - started),
        "proto_variable_count": int(proto_profile.get("variable_count", 0)),
        "element_count": int(constraint_counts.get("element", 0)),
        "proto_profile": proto_profile,
        "cover_choice_profile": copy.deepcopy(cover_choice),
        "power_coverage_build_stats": copy.deepcopy(power_coverage),
        "power_coverage_witness_stats": copy.deepcopy(witness_stats),
        "slot_summary": _slot_summary(delegate),
        "block_relation_summary": _delegate_block_relation_summary(
            delegate,
            block_size=int(block_size),
        ),
    }


def _build_relation_payload(
    *,
    cases: Sequence[Mapping[str, Any]],
    block_size: int,
) -> Dict[str, Any]:
    by_id = {str(case.get("case_id")): case for case in cases if isinstance(case, Mapping)}
    final_case = _mapping(by_id.get("final_target"))
    selected_case = _mapping(by_id.get("selected_block"))
    active_guard_case = _mapping(by_id.get("selected_block_active_guard"))
    final_relation = _mapping(final_case.get("block_relation_summary"))
    selected_relation = _mapping(selected_case.get("block_relation_summary"))
    active_guard_relation = _mapping(active_guard_case.get("block_relation_summary"))
    final_real = _mapping(final_relation.get("aggregate"))
    selected_real = _mapping(selected_relation.get("aggregate"))
    active_guard_real = _mapping(active_guard_relation.get("aggregate"))
    edge_counts = [
        1,
        max(1, int(block_size) - 1),
        int(block_size),
        int(block_size) + 1,
        int(block_size) * 2 + 1,
    ]
    edge_cases = [
        build_selected_block_witness_relation_equivalence(
            pole_slot_count=count,
            block_size=int(block_size),
        )
        for count in edge_counts
    ]
    active_guard_edge_cases = [
        build_active_guard_witness_relation_equivalence(
            pole_slot_count=count,
            block_size=int(block_size),
        )
        for count in edge_counts
    ]
    real_equivalent = (
        bool(final_real.get("all_equivalent", False))
        and bool(selected_real.get("all_equivalent", False))
        and int(final_real.get("witness_count", -1))
        == int(selected_real.get("witness_count", -2))
        and int(final_real.get("relation_row_count", -1))
        == int(selected_real.get("relation_row_count", -2))
        and int(final_real.get("padded_block_value_count", -1))
        == int(selected_real.get("padded_block_value_count", -2))
    )
    return {
        "status": "evaluated",
        "real_witness_relation": {
            "equivalent": bool(real_equivalent),
            "witness_count": int(selected_real.get("witness_count", 0)),
            "pole_slot_count": int(selected_real.get("pole_slot_count", 0)),
            "relation_row_count": int(selected_real.get("relation_row_count", 0)),
            "padded_block_value_count": int(
                selected_real.get("padded_block_value_count", 0)
            ),
            "inactive_powered_slot_guard_equivalent": bool(
            selected_real.get("inactive_powered_slot_guard_equivalent", False)
            ),
            "sample_witnesses": list(selected_relation.get("samples", [])),
        },
        "active_guard_relation": {
            "equivalent": bool(
                active_guard_case
                and bool(active_guard_real.get("all_active_guard_equivalent", False))
                and int(active_guard_real.get("witness_count", -1))
                == int(selected_real.get("witness_count", -2))
                and int(active_guard_real.get("active_guard_relation_row_count", -1))
                == int(selected_real.get("relation_row_count", -2))
            ),
            "witness_count": int(active_guard_real.get("witness_count", 0)),
            "pole_slot_count": int(active_guard_real.get("pole_slot_count", 0)),
            "relation_row_count": int(
                active_guard_real.get("active_guard_relation_row_count", 0)
            ),
            "padded_block_value_count": int(
                active_guard_real.get("padded_block_value_count", 0)
            ),
            "inactive_powered_slot_guard_equivalent": bool(
                active_guard_real.get("inactive_powered_slot_guard_equivalent", False)
            ),
            "sample_witnesses": list(active_guard_relation.get("samples", [])),
        },
        "final_target_summary": final_relation,
        "selected_block_summary": selected_relation,
        "active_guard_summary": active_guard_relation,
        "edge_cases": edge_cases,
        "edge_cases_equivalent": all(bool(edge.get("equivalent")) for edge in edge_cases),
        "active_guard_edge_cases": active_guard_edge_cases,
        "active_guard_edge_cases_equivalent": all(
            bool(edge.get("equivalent")) for edge in active_guard_edge_cases
        ),
        "target_channel_delta": _target_channel_delta(final_case, selected_case),
        "active_guard_channel_delta": _active_guard_channel_delta(
            selected_case, active_guard_case
        ),
    }


def _delegate_block_relation_summary(
    delegate: Any,
    *,
    block_size: int,
) -> Dict[str, Any]:
    if delegate is None:
        return {
            "status": "missing_delegate",
            "aggregate": {"all_equivalent": False},
            "samples": [],
        }
    pole_slots = list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    powered_slots = [
        slot
        for slot in list(delegate._all_powered_slots())
        if bool(delegate._use_block_element_power_coverage_for_template(slot.template))
    ]
    aggregate = {
        "witness_count": int(len(powered_slots)),
        "pole_slot_count": int(len(pole_slots)),
        "relation_row_count": 0,
        "active_guard_relation_row_count": 0,
        "padded_block_value_count": 0,
        "all_equivalent": True,
        "all_active_guard_equivalent": True,
        "inactive_powered_slot_guard_equivalent": True,
    }
    samples = []
    for powered_slot in powered_slots:
        relation = build_selected_block_witness_relation_equivalence(
            pole_slot_count=len(pole_slots),
            block_size=int(block_size),
        )
        active_guard_relation = build_active_guard_witness_relation_equivalence(
            pole_slot_count=len(pole_slots),
            block_size=int(block_size),
        )
        aggregate["relation_row_count"] = int(aggregate["relation_row_count"]) + int(
            relation.get("relation_row_count", 0)
        )
        aggregate["active_guard_relation_row_count"] = int(
            aggregate["active_guard_relation_row_count"]
        ) + int(active_guard_relation.get("relation_row_count", 0))
        aggregate["padded_block_value_count"] = int(
            aggregate["padded_block_value_count"]
        ) + int(relation.get("padded_block_value_count", 0))
        aggregate["all_equivalent"] = bool(aggregate["all_equivalent"]) and bool(
            relation.get("equivalent")
        )
        aggregate["all_active_guard_equivalent"] = bool(
            aggregate["all_active_guard_equivalent"]
        ) and bool(active_guard_relation.get("equivalent"))
        aggregate["inactive_powered_slot_guard_equivalent"] = bool(
            aggregate["inactive_powered_slot_guard_equivalent"]
        ) and bool(relation.get("inactive_powered_slot_guard_equivalent"))
        aggregate["inactive_powered_slot_guard_equivalent"] = bool(
            aggregate["inactive_powered_slot_guard_equivalent"]
        ) and bool(
            active_guard_relation.get("inactive_powered_slot_guard_equivalent")
        )
        if len(samples) < 8:
            samples.append(
                {
                    "powered_slot_key": str(powered_slot.key),
                    "template": str(powered_slot.template),
                    "slot_kind": str(powered_slot.slot_kind),
                    "relation": {
                        key: value
                        for key, value in relation.items()
                        if key
                        in {
                            "pole_slot_count",
                            "block_size",
                            "block_count",
                            "relation_row_count",
                            "padded_block_value_count",
                            "equivalent",
                            "inactive_powered_slot_guard_equivalent",
                        }
                    },
                    "active_guard_relation": {
                        key: value
                        for key, value in active_guard_relation.items()
                        if key
                        in {
                            "pole_slot_count",
                            "block_size",
                            "block_count",
                            "relation_row_count",
                            "padded_block_value_count",
                            "equivalent",
                            "inactive_powered_slot_guard_equivalent",
                        }
                    },
                }
            )
    return {"status": "evaluated", "aggregate": aggregate, "samples": samples}


def _slot_summary(delegate: Any) -> Dict[str, Any]:
    if delegate is None:
        return {}
    residual = getattr(delegate, "residual_optional_slots", {})
    powered_slots = list(delegate._all_powered_slots())
    return {
        "residual_optional_counts": {
            str(template): int(len(slots))
            for template, slots in sorted(dict(residual).items())
        },
        "powered_slot_count": int(len(powered_slots)),
        "pole_slot_count": int(len(list(residual.get("power_pole", [])))),
    }


def _target_channel_delta(
    final_case: Mapping[str, Any],
    selected_case: Mapping[str, Any],
) -> Dict[str, Any]:
    final_target = _mapping(
        _mapping(final_case.get("cover_choice_profile")).get("target_channel_profile")
    )
    selected_target = _mapping(
        _mapping(selected_case.get("cover_choice_profile")).get("target_channel_profile")
    )
    return {
        "final_target_channel_delta": _int_value(
            selected_target.get("final_target_channel_variables")
        )
        - _int_value(final_target.get("final_target_channel_variables")),
        "block_selected_literal_delta": _int_value(
            selected_target.get("block_selected_literal_variables")
        )
        - _int_value(final_target.get("block_selected_literal_variables")),
        "final_target_channels_removed": bool(
            _int_value(final_target.get("final_target_channel_variables")) > 0
            and _int_value(selected_target.get("final_target_channel_variables")) == 0
        ),
    }


def _active_guard_channel_delta(
    selected_case: Mapping[str, Any],
    active_guard_case: Mapping[str, Any],
) -> Dict[str, Any]:
    selected_target = _mapping(
        _mapping(selected_case.get("cover_choice_profile")).get(
            "target_channel_profile"
        )
    )
    active_guard_target = _mapping(
        _mapping(active_guard_case.get("cover_choice_profile")).get(
            "target_channel_profile"
        )
    )
    selected_profile = _mapping(selected_case.get("proto_profile"))
    active_guard_profile = _mapping(active_guard_case.get("proto_profile"))
    selected_counts = _mapping(selected_profile.get("constraint_kind_counts"))
    active_guard_counts = _mapping(active_guard_profile.get("constraint_kind_counts"))
    return {
        "block_intermediate_target_channel_delta": _int_value(
            active_guard_target.get("block_intermediate_target_channel_variables")
        )
        - _int_value(
            selected_target.get("block_intermediate_target_channel_variables")
        ),
        "local_selected_literal_delta": _int_value(
            active_guard_target.get("local_selected_literal_variables")
        )
        - _int_value(selected_target.get("local_selected_literal_variables")),
        "element_delta": _int_value(active_guard_counts.get("element"))
        - _int_value(selected_counts.get("element")),
        "bool_or_delta": _int_value(active_guard_counts.get("bool_or"))
        - _int_value(selected_counts.get("bool_or")),
        "active_block_channels_removed": bool(
            _int_value(
                active_guard_target.get("block_intermediate_target_channel_variables")
            )
            < _int_value(
                selected_target.get("block_intermediate_target_channel_variables")
            )
        ),
    }


def _status_from_relation(relation: Mapping[str, Any]) -> Dict[str, Any]:
    real = _mapping(relation.get("real_witness_relation"))
    active_guard = _mapping(relation.get("active_guard_relation"))
    target_delta = _mapping(relation.get("target_channel_delta"))
    active_guard_delta = _mapping(relation.get("active_guard_channel_delta"))
    if (
        bool(real.get("equivalent", False))
        and bool(active_guard.get("equivalent", False))
        and bool(relation.get("edge_cases_equivalent", False))
        and bool(relation.get("active_guard_edge_cases_equivalent", False))
        and bool(target_delta.get("final_target_channels_removed", False))
        and bool(active_guard_delta.get("active_block_channels_removed", False))
    ):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "relations_equivalent",
            "recommendation": (
                "Selected-block and selected-block active-guard relations match "
                "their predecessor formulations in this no-solve audit; use as a "
                "diagnostic gate, not proof source."
            ),
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "relation_gap_detected",
        "recommendation": (
            "Selected-block relation audit found a gap; do not run longer probes "
            "until relation_equivalence is inspected."
        ),
    }


def _checks(report: Mapping[str, Any]) -> list[Dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    relation = _mapping(report.get("relation_equivalence"))
    real = _mapping(relation.get("real_witness_relation"))
    active_guard = _mapping(relation.get("active_guard_relation"))
    target_delta = _mapping(relation.get("target_channel_delta"))
    active_guard_delta = _mapping(relation.get("active_guard_channel_delta"))
    model_error = report.get("model_error")
    return [
        _check(
            "solver_not_invoked",
            "pass" if not bool(metadata.get("solver_invoked", True)) else "fail",
            "solver_invoked=false"
            if not bool(metadata.get("solver_invoked", True))
            else "solver was invoked",
        ),
        _check(
            "proof_source_false",
            "pass" if not bool(metadata.get("proof_source", True)) else "fail",
            "proof_source=false"
            if not bool(metadata.get("proof_source", True))
            else "proof_source true",
        ),
        _check(
            "audit_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "real_witness_relation_equivalent",
            "pass" if bool(real.get("equivalent", False)) else "fail",
            f"relation_row_count={real.get('relation_row_count')}",
        ),
        _check(
            "edge_cases_equivalent",
            "pass" if bool(relation.get("edge_cases_equivalent", False)) else "fail",
            "synthetic padding/multi-block cases equivalent",
        ),
        _check(
            "active_guard_relation_equivalent",
            "pass" if bool(active_guard.get("equivalent", False)) else "fail",
            f"relation_row_count={active_guard.get('relation_row_count')}",
        ),
        _check(
            "active_guard_edge_cases_equivalent",
            "pass"
            if bool(relation.get("active_guard_edge_cases_equivalent", False))
            else "fail",
            "active guard padding/inactive/multi-block cases equivalent",
        ),
        _check(
            "final_target_channels_removed",
            "pass"
            if bool(target_delta.get("final_target_channels_removed", False))
            else "fail",
            f"delta={target_delta.get('final_target_channel_delta')}",
        ),
        _check(
            "active_block_channels_removed",
            "pass"
            if bool(active_guard_delta.get("active_block_channels_removed", False))
            else "fail",
            f"delta={active_guard_delta.get('block_intermediate_target_channel_delta')}",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _parse_candidate(candidate: str) -> tuple[int, int]:
    raw = str(candidate).strip().lower()
    if "x" not in raw:
        raise ValueError(f"candidate must look like WxH, got {candidate!r}")
    left, right = raw.split("x", 1)
    return int(left), int(right)


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
