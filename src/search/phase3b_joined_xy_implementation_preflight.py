from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import _check, _display_path, _mapping

JOINED_XY_IMPLEMENTATION_PREFLIGHT_SOURCE = (
    "phase3b_joined_xy_implementation_preflight_v1"
)
DEFAULT_GROUPED_XY_SAT_EXPANSION_AUDIT_PATH = Path(
    ".artifacts/phase3b_grouped_xy_sat_expansion_audit_20260423/"
    "grouped_xy_sat_expansion_audit.json"
)
DEFAULT_GROUPED_BLOCK_XY_PROFILE_AUDIT_PATH = Path(
    ".artifacts/phase3b_grouped_block_xy_profile_audit_20260423/"
    "grouped_block_xy_profile_audit.json"
)
DEFAULT_GROUPED_BLOCK_XY_IMPLEMENTATION_PREFLIGHT_PATH = Path(
    ".artifacts/phase3b_grouped_block_xy_implementation_preflight_20260423/"
    "grouped_block_xy_implementation_preflight.json"
)


def build_phase3b_joined_xy_implementation_preflight(
    project_root: Path,
    *,
    sat_expansion_audit_path: Optional[Path] = None,
    grouped_profile_audit_path: Optional[Path] = None,
    grouped_implementation_preflight_path: Optional[Path] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    sat_path = _resolve(
        project_root,
        sat_expansion_audit_path or DEFAULT_GROUPED_XY_SAT_EXPANSION_AUDIT_PATH,
    )
    profile_path = _resolve(
        project_root,
        grouped_profile_audit_path or DEFAULT_GROUPED_BLOCK_XY_PROFILE_AUDIT_PATH,
    )
    grouped_preflight_path = _resolve(
        project_root,
        grouped_implementation_preflight_path
        or DEFAULT_GROUPED_BLOCK_XY_IMPLEMENTATION_PREFLIGHT_PATH,
    )
    sat_audit = _load_json(sat_path)
    profile_audit = _load_json(profile_path)
    grouped_preflight = _load_json(grouped_preflight_path)
    expected = _expected_joined_xy_stats(profile_audit)
    gates = _gate_state(sat_audit, profile_audit, grouped_preflight, expected)
    ready = all(bool(value) for value in gates.values())
    report: dict[str, Any] = {
        "metadata": {
            "source": JOINED_XY_IMPLEMENTATION_PREFLIGHT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_joined_xy_implementation_preflight",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": _display_path(project_root, project_root),
            "grouped_xy_sat_expansion_audit": _display_path(project_root, sat_path),
            "grouped_block_xy_profile_audit": _display_path(project_root, profile_path),
            "grouped_block_xy_implementation_preflight": _display_path(
                project_root,
                grouped_preflight_path,
            ),
        },
        "status": {
            "completed": True,
            "evaluated": bool(sat_audit and profile_audit and grouped_preflight),
            "outcome": (
                "joined_xy_implementation_preflight_ready"
                if ready
                else "joined_xy_implementation_preflight_blocked"
            ),
            "ready_for_default_off_model_edit": bool(ready),
            "recommendation": (
                "implement_default_off_selected_block_active_guard_joined_xy_then_run_no_solve_profile_audit"
                if ready
                else "refresh_grouped_xy_blowup_and_profile_evidence_before_joined_xy_model_edit"
            ),
        },
        "proposed_mode": {
            "env": "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY",
            "value": "selected_block_active_guard_joined_xy",
            "default_off": True,
            "base_mode": "selected_block_active_guard",
            "proof_semantics": "diagnostic/formulation-only until equivalence, no-solve audits, and bounded probes pass",
        },
        "problem_statement": _problem_statement(sat_audit),
        "implementation_recipe": _implementation_recipe(),
        "expected_no_solve_stats": expected,
        "semantic_gates": gates,
        "required_followup": _required_followup(),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, sat_audit, profile_audit, grouped_preflight)
    return report


def render_phase3b_joined_xy_implementation_preflight_markdown(
    report: Mapping[str, Any],
) -> str:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    mode = _mapping(report.get("proposed_mode"))
    problem = _mapping(report.get("problem_statement"))
    counts = _mapping(report.get("expected_no_solve_stats"))
    lines = [
        "# Phase 3B Joined-XY Implementation Preflight",
        "",
        "- Diagnostic semantics: no_solve_joined_xy_implementation_preflight",
        f"- solver_invoked: {bool(metadata.get('solver_invoked', True))}",
        f"- proof_source: {bool(metadata.get('proof_source', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Ready for model edit: {status.get('ready_for_default_off_model_edit')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Why This Exists",
        "",
        f"- Grouped-XY outcome: {problem.get('grouped_xy_sat_outcome')}",
        f"- Integer encoding blow-up: {problem.get('integer_encoding_blowup_detected')}",
        f"- Grouped/active integer encoding ratio: {problem.get('grouped_to_active_integer_encoding_ratio')}",
        f"- Suspect selector: {problem.get('suspect_selector')}",
        "",
        "## Proposed Mode",
        "",
        f"- Env: {mode.get('env')}",
        f"- Value: {mode.get('value')}",
        f"- Default-off: {mode.get('default_off')}",
        f"- Base mode: {mode.get('base_mode')}",
        "",
        "## Expected No-Solve Stats",
        "",
        f"- Powered slots: {counts.get('powered_slot_count')}",
        f"- Blocks per powered slot: {counts.get('blocks_per_powered_slot')}",
        f"- Active guard BoolOr clauses unchanged: {counts.get('active_guard_bool_or_clauses_unchanged')}",
        f"- Cover-choice padded idx variables: {counts.get('cover_choice_padded_idx_variables')}",
        f"- Retained per-block x/y target variables: {counts.get('retained_per_block_xy_target_variables')}",
        f"- Joined final x/y target variables: {counts.get('joined_xy_target_channel_count')}",
        f"- Local block x/y Elements: {counts.get('local_block_xy_element_constraints')}",
        f"- Final joined x/y Elements: {counts.get('joined_xy_element_constraint_count')}",
        f"- Total block Element constraints: {counts.get('total_block_element_constraints')}",
        f"- Selected geometry constraints: {counts.get('joined_xy_selected_geometry_constraint_count')}",
        "",
        "## Recipe",
        "",
    ]
    for item in list(report.get("implementation_recipe", [])):
        lines.append(f"- {item}")
    lines.extend(["", "## Required Follow-Up", ""])
    for item in list(report.get("required_followup", [])):
        lines.append(f"- {item}")
    lines.extend(
        [
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


def render_phase3b_joined_xy_implementation_preflight_text(
    report: Mapping[str, Any],
) -> str:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    mode = _mapping(report.get("proposed_mode"))
    problem = _mapping(report.get("problem_statement"))
    counts = _mapping(report.get("expected_no_solve_stats"))
    return "\n".join(
        [
            "phase3b joined-xy implementation preflight",
            "diagnostic_semantics=no_solve_joined_xy_implementation_preflight",
            f"solver_invoked={bool(metadata.get('solver_invoked', True))}",
            f"proof_source={bool(metadata.get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"ready_for_default_off_model_edit={status.get('ready_for_default_off_model_edit')}",
            f"mode={mode.get('value')}",
            f"grouped_integer_encoding_blowup={problem.get('integer_encoding_blowup_detected')}",
            f"cover_choice_padded_idx_variables={counts.get('cover_choice_padded_idx_variables')}",
            f"retained_per_block_xy_target_variables={counts.get('retained_per_block_xy_target_variables')}",
            f"joined_xy_target_channel_count={counts.get('joined_xy_target_channel_count')}",
            f"total_block_element_constraints={counts.get('total_block_element_constraints')}",
            f"active_guard_bool_or_clauses_unchanged={counts.get('active_guard_bool_or_clauses_unchanged')}",
        ]
    ) + "\n"


def _problem_statement(sat_audit: Mapping[str, Any]) -> dict[str, Any]:
    status = _mapping(sat_audit.get("status"))
    comparison = _mapping(sat_audit.get("comparison"))
    return {
        "grouped_xy_sat_outcome": status.get("outcome"),
        "integer_encoding_blowup_detected": bool(
            comparison.get("integer_encoding_blowup_detected", False)
        ),
        "grouped_to_active_integer_encoding_ratio": comparison.get(
            "grouped_to_active_integer_encoding_ratio"
        ),
        "grouped_to_active_sat_boolean_ratio": comparison.get(
            "grouped_to_active_sat_boolean_ratio"
        ),
        "anchor118_terminal_not_reproduced": bool(
            comparison.get("anchor118_terminal_not_reproduced", False)
        ),
        "suspect_selector": "cover_choice_padded_idx__",
        "recommended_next_action": comparison.get("recommended_next_action"),
    }


def _implementation_recipe() -> list[str]:
    return [
        "Add default-off block geometry value selected_block_active_guard_joined_xy.",
        "Keep selected_block_active_guard as the base semantics and leave production defaults unchanged.",
        "Keep cover_choice_block_idx and cover_choice_local_idx selectors.",
        "Keep per-block local x/y AddElement targets from cover_choice_local_idx.",
        "Keep block/local selected literals and active-guard BoolOr clauses unchanged.",
        "Remove per-block selected geometry constraints.",
        "Do not create cover_choice_padded_idx__ or flatten block/local selectors into one integer selector.",
        "Join per-block x/y targets with cover_choice_block_idx into one final x/y pair.",
        "Apply selected geometry once per powered slot from the joined final x/y pair.",
        "Do not add powered-slot by pole-slot cover literals or O(relation_rows) guarded geometry constraints.",
    ]


def _required_followup() -> list[str]:
    return [
        "After implementation, run a no-solve profile audit comparing selected_block_active_guard and selected_block_active_guard_joined_xy.",
        "The no-solve audit must confirm cover_choice_padded_idx__ remains zero and active guard clauses remain unchanged.",
        "Only after no-solve audit passes, run one bounded presolve/probe to check SAT expansion before any larger solver time.",
        "Do not treat joined-XY diagnostics as proof-source campaign evidence.",
    ]


def _expected_joined_xy_stats(profile_audit: Mapping[str, Any]) -> dict[str, Any]:
    active = _find_case(profile_audit, "selected_block_active_guard")
    grouped = _find_case(profile_audit, "selected_block_active_guard_grouped_xy")
    active_w = _mapping(active.get("witness_stats"))
    grouped_w = _mapping(grouped.get("witness_stats"))
    active_prefix = _mapping(active.get("variable_prefix_counts"))
    grouped_prefix = _mapping(grouped.get("variable_prefix_counts"))
    powered = _int(active_w.get("block_witness_count"))
    block_selected = _int(active_w.get("block_selected_literal_count"))
    local_selected = _int(active_w.get("local_selected_literal_count"))
    blocks_per_powered = _ratio_int(block_selected, powered)
    per_block_x = _int(active_prefix.get("cover_choice_block_x__"))
    per_block_y = _int(active_prefix.get("cover_choice_block_y__"))
    per_block_xy = per_block_x + per_block_y
    joined_xy_targets = int(powered * 2)
    local_block_xy_elements = _int(active_w.get("block_element_constraint_count"))
    final_join_elements = int(powered * 2)
    selected_geometry = int(powered * 4)
    return {
        "source_profile_present": bool(active and grouped),
        "powered_slot_count": powered,
        "block_size": _int(active_w.get("block_size")),
        "blocks_per_powered_slot": blocks_per_powered,
        "relation_row_count": _int(active_w.get("block_active_guard_clause_count")),
        "active_guard_bool_or_clauses_unchanged": _int(
            active_w.get("block_active_guard_clause_count")
        ),
        "block_selected_literals_unchanged": block_selected,
        "local_selected_literals_unchanged": local_selected,
        "block_selector_count_unchanged": _int(active_w.get("block_selector_count")),
        "local_selector_count_unchanged": _int(active_w.get("local_selector_count")),
        "cover_choice_padded_idx_variables": 0,
        "grouped_xy_current_padded_idx_variables": _int(
            grouped_prefix.get("cover_choice_padded_idx__")
        ),
        "retained_per_block_x_target_variables": per_block_x,
        "retained_per_block_y_target_variables": per_block_y,
        "retained_per_block_xy_target_variables": per_block_xy,
        "joined_xy_target_channel_count": joined_xy_targets,
        "final_active_channel_count": 0,
        "local_block_xy_element_constraints": local_block_xy_elements,
        "joined_xy_element_constraint_count": final_join_elements,
        "total_block_element_constraints": int(local_block_xy_elements + final_join_elements),
        "joined_xy_selected_geometry_constraint_count": selected_geometry,
        "block_selected_geometry_constraint_count": 0,
        "pairwise_cover_literal_count": 0,
        "active_guard_block_element_constraints": _int(
            active_w.get("block_element_constraint_count")
        ),
        "grouped_xy_block_element_constraints": _int(
            grouped_w.get("block_element_constraint_count")
        ),
        "active_guard_selected_geometry_constraints": _int(
            active_w.get("block_selected_geometry_constraint_count")
        ),
        "grouped_xy_selected_geometry_constraints": _int(
            grouped_w.get("grouped_xy_selected_geometry_constraint_count")
        ),
    }


def _gate_state(
    sat_audit: Mapping[str, Any],
    profile_audit: Mapping[str, Any],
    grouped_preflight: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, bool]:
    sat_metadata = _mapping(sat_audit.get("metadata"))
    profile_metadata = _mapping(profile_audit.get("metadata"))
    grouped_metadata = _mapping(grouped_preflight.get("metadata"))
    sat_status = _mapping(sat_audit.get("status"))
    sat_comparison = _mapping(sat_audit.get("comparison"))
    profile_status = _mapping(profile_audit.get("status"))
    profile_comparison = _mapping(profile_audit.get("comparison"))
    grouped_status = _mapping(grouped_preflight.get("status"))
    return {
        "sat_expansion_audit_present": bool(sat_audit),
        "grouped_profile_audit_present": bool(profile_audit),
        "grouped_implementation_preflight_present": bool(grouped_preflight),
        "input_artifacts_no_solve": (
            not bool(sat_metadata.get("solver_invoked", True))
            and not bool(profile_metadata.get("solver_invoked", True))
            and not bool(grouped_metadata.get("solver_invoked", True))
        ),
        "input_artifacts_not_proof_source": (
            not bool(sat_metadata.get("proof_source", True))
            and not bool(profile_metadata.get("proof_source", True))
            and not bool(grouped_metadata.get("proof_source", True))
        ),
        "grouped_xy_blowup_recorded": (
            sat_status.get("outcome") == "grouped_xy_sat_expansion_blowup_detected"
            and bool(sat_comparison.get("integer_encoding_blowup_detected", False))
        ),
        "grouped_profile_valid": (
            profile_status.get("outcome") == "grouped_block_xy_profile_audit_passed"
            and bool(profile_comparison.get("grouped_xy_profile_valid", False))
        ),
        "prior_grouped_preflight_was_ready": bool(
            grouped_status.get("ready_for_default_off_model_edit", False)
        ),
        "flattened_selector_problem_identified": (
            _int(expected.get("grouped_xy_current_padded_idx_variables")) > 0
            and _as_float(
                sat_comparison.get("grouped_to_active_integer_encoding_ratio")
            )
            > 10.0
        ),
        "joined_xy_removes_flattened_selector": _int(
            expected.get("cover_choice_padded_idx_variables")
        )
        == 0,
        "active_guard_semantics_preserved_spec": (
            _int(expected.get("active_guard_bool_or_clauses_unchanged")) > 0
            and _int(expected.get("block_selected_literals_unchanged")) > 0
            and _int(expected.get("local_selected_literals_unchanged")) > 0
            and _int(expected.get("block_selector_count_unchanged"))
            == _int(expected.get("powered_slot_count"))
            and _int(expected.get("local_selector_count_unchanged"))
            == _int(expected.get("powered_slot_count"))
        ),
        "final_active_channel_removed_spec": _int(
            expected.get("final_active_channel_count")
        )
        == 0,
        "block_selected_geometry_removed_spec": _int(
            expected.get("block_selected_geometry_constraint_count")
        )
        == 0,
        "joined_xy_element_count_matches_powered_slots": (
            _int(expected.get("joined_xy_element_constraint_count"))
            == _int(expected.get("powered_slot_count")) * 2
        ),
        "joined_xy_selected_geometry_count_matches_powered_slots": (
            _int(expected.get("joined_xy_selected_geometry_constraint_count"))
            == _int(expected.get("powered_slot_count")) * 4
        ),
        "retained_per_block_xy_matches_active_profile": (
            _int(expected.get("retained_per_block_xy_target_variables"))
            == _int(expected.get("active_guard_block_element_constraints"))
        ),
        "no_pairwise_or_relation_sized_geometry_spec": (
            _int(expected.get("pairwise_cover_literal_count")) == 0
            and _int(expected.get("total_block_element_constraints"))
            < _int(expected.get("relation_row_count"))
        ),
        "default_off_spec": True,
    }


def _checks(
    report: Mapping[str, Any],
    sat_audit: Mapping[str, Any],
    profile_audit: Mapping[str, Any],
    grouped_preflight: Mapping[str, Any],
) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    expected = _mapping(report.get("expected_no_solve_stats"))
    gates = _mapping(report.get("semantic_gates"))
    checks = [
        _check(
            "solver_not_invoked",
            "pass" if not bool(metadata.get("solver_invoked", True)) else "fail",
            "solver_invoked=false",
        ),
        _check(
            "proof_source_false",
            "pass" if not bool(metadata.get("proof_source", True)) else "fail",
            "proof_source=false",
        ),
        _check(
            "sat_expansion_audit_present",
            "pass" if bool(sat_audit) else "fail",
            f"present={bool(sat_audit)}",
        ),
        _check(
            "grouped_profile_audit_present",
            "pass" if bool(profile_audit) else "fail",
            f"present={bool(profile_audit)}",
        ),
        _check(
            "grouped_implementation_preflight_present",
            "pass" if bool(grouped_preflight) else "fail",
            f"present={bool(grouped_preflight)}",
        ),
        _check(
            "input_artifacts_no_solve",
            "pass" if bool(gates.get("input_artifacts_no_solve", False)) else "fail",
            str(gates.get("input_artifacts_no_solve")),
        ),
        _check(
            "input_artifacts_not_proof_source",
            "pass"
            if bool(gates.get("input_artifacts_not_proof_source", False))
            else "fail",
            str(gates.get("input_artifacts_not_proof_source")),
        ),
        _check(
            "grouped_xy_blowup_recorded",
            "pass" if bool(gates.get("grouped_xy_blowup_recorded", False)) else "fail",
            str(gates.get("grouped_xy_blowup_recorded")),
        ),
        _check(
            "grouped_profile_valid",
            "pass" if bool(gates.get("grouped_profile_valid", False)) else "fail",
            str(gates.get("grouped_profile_valid")),
        ),
        _check(
            "flattened_selector_problem_identified",
            "pass"
            if bool(gates.get("flattened_selector_problem_identified", False))
            else "fail",
            f"grouped_padded_idx={expected.get('grouped_xy_current_padded_idx_variables')}",
        ),
        _check(
            "joined_xy_removes_flattened_selector",
            "pass"
            if bool(gates.get("joined_xy_removes_flattened_selector", False))
            else "fail",
            f"expected_padded_idx={expected.get('cover_choice_padded_idx_variables')}",
        ),
        _check(
            "active_guard_semantics_preserved_spec",
            "pass"
            if bool(gates.get("active_guard_semantics_preserved_spec", False))
            else "fail",
            f"active_guard_clauses={expected.get('active_guard_bool_or_clauses_unchanged')}",
        ),
        _check(
            "final_active_channel_removed_spec",
            "pass"
            if bool(gates.get("final_active_channel_removed_spec", False))
            else "fail",
            f"final_active_channel_count={expected.get('final_active_channel_count')}",
        ),
        _check(
            "block_selected_geometry_removed_spec",
            "pass"
            if bool(gates.get("block_selected_geometry_removed_spec", False))
            else "fail",
            f"block_selected_geometry_constraint_count={expected.get('block_selected_geometry_constraint_count')}",
        ),
        _check(
            "joined_xy_element_count_matches_powered_slots",
            "pass"
            if bool(gates.get("joined_xy_element_count_matches_powered_slots", False))
            else "fail",
            f"joined_elements={expected.get('joined_xy_element_constraint_count')} powered={expected.get('powered_slot_count')}",
        ),
        _check(
            "joined_xy_selected_geometry_count_matches_powered_slots",
            "pass"
            if bool(
                gates.get(
                    "joined_xy_selected_geometry_count_matches_powered_slots",
                    False,
                )
            )
            else "fail",
            f"selected_geometry={expected.get('joined_xy_selected_geometry_constraint_count')} powered={expected.get('powered_slot_count')}",
        ),
        _check(
            "retained_per_block_xy_matches_active_profile",
            "pass"
            if bool(gates.get("retained_per_block_xy_matches_active_profile", False))
            else "fail",
            f"retained={expected.get('retained_per_block_xy_target_variables')} active_elements={expected.get('active_guard_block_element_constraints')}",
        ),
        _check(
            "no_pairwise_or_relation_sized_geometry_spec",
            "pass"
            if bool(gates.get("no_pairwise_or_relation_sized_geometry_spec", False))
            else "fail",
            f"block_elements={expected.get('total_block_element_constraints')} relation_rows={expected.get('relation_row_count')}",
        ),
        _check(
            "default_off_spec",
            "pass" if bool(gates.get("default_off_spec", False)) else "fail",
            "mode is explicit opt-in",
        ),
        _check(
            "ready_matches_gates",
            "pass"
            if bool(status.get("ready_for_default_off_model_edit", False))
            == all(bool(value) for value in gates.values())
            else "fail",
            f"ready={status.get('ready_for_default_off_model_edit')}",
        ),
    ]
    return checks


def _find_case(report: Mapping[str, Any], case_id: str) -> Mapping[str, Any]:
    for case in list(report.get("cases", [])):
        if isinstance(case, Mapping) and str(case.get("case_id")) == case_id:
            return case
    return {}


def _resolve(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return project_root / path


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _ratio_int(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return int(numerator // denominator)


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
