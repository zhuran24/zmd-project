from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import _check, _display_path, _mapping
from src.search.phase3b_grouped_block_xy_candidate import DEFAULT_GROUPED_ORACLE_PATH

GROUPED_BLOCK_XY_IMPLEMENTATION_PREFLIGHT_SOURCE = (
    "phase3b_grouped_block_xy_implementation_preflight_v1"
)
DEFAULT_GROUPED_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_grouped_block_xy_candidate_20260423/"
    "grouped_block_xy_candidate.json"
)
DEFAULT_GROUPED_ORACLE_WITH_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_grouped_block_xy_equivalence_oracle_20260423_with_candidate/"
    "grouped_block_xy_equivalence_oracle.json"
)
DEFAULT_SCALE_EQUIVALENCE_PATH = Path(
    ".artifacts/phase3b_active_guard_block_xy_scale_equivalence_20260423/"
    "active_guard_block_xy_scale_equivalence.json"
)


def build_phase3b_grouped_block_xy_implementation_preflight(
    project_root: Path,
    *,
    grouped_candidate_path: Optional[Path] = None,
    grouped_oracle_path: Optional[Path] = None,
    scale_equivalence_path: Optional[Path] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    candidate_path = _resolve(project_root, grouped_candidate_path or DEFAULT_GROUPED_CANDIDATE_PATH)
    oracle_path = _resolve(
        project_root,
        grouped_oracle_path or DEFAULT_GROUPED_ORACLE_WITH_CANDIDATE_PATH,
    )
    scale_path = _resolve(project_root, scale_equivalence_path or DEFAULT_SCALE_EQUIVALENCE_PATH)
    candidate = _load_json(candidate_path)
    oracle = _load_json(oracle_path)
    scale = _load_json(scale_path)
    counts = _expected_counts(candidate, scale)
    ready = bool(
        candidate
        and oracle
        and scale
        and _mapping(candidate.get("status")).get("outcome")
        == "grouped_block_xy_candidate_built"
        and bool(
            _mapping(oracle.get("status")).get(
                "oracle_ready_for_default_off_implementation", False
            )
        )
    )
    report: dict[str, Any] = {
        "metadata": {
            "source": GROUPED_BLOCK_XY_IMPLEMENTATION_PREFLIGHT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_implementation_preflight_spec",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": _display_path(project_root, project_root),
            "grouped_candidate": _display_path(project_root, candidate_path),
            "grouped_oracle": _display_path(project_root, oracle_path),
            "scale_equivalence": _display_path(project_root, scale_path),
        },
        "status": {
            "completed": True,
            "evaluated": bool(candidate and oracle and scale),
            "outcome": (
                "grouped_block_xy_implementation_preflight_ready"
                if ready
                else "grouped_block_xy_implementation_preflight_blocked"
            ),
            "ready_for_default_off_model_edit": bool(ready),
            "recommendation": (
                "implement_default_off_selected_block_active_guard_grouped_xy"
                if ready
                else "refresh_grouped_candidate_or_oracle_before_model_edit"
            ),
        },
        "proposed_mode": {
            "env": "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY",
            "value": "selected_block_active_guard_grouped_xy",
            "default_off": True,
            "base_mode": "selected_block_active_guard",
            "proof_semantics": "diagnostic/formulation-only until equivalence and bounded probes pass",
        },
        "implementation_recipe": _implementation_recipe(),
        "expected_no_solve_stats": counts,
        "non_degeneration_rules": _non_degeneration_rules(counts),
        "required_tests": _required_tests(),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, candidate, oracle, scale)
    return report


def render_phase3b_grouped_block_xy_implementation_preflight_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    mode = _mapping(report.get("proposed_mode"))
    counts = _mapping(report.get("expected_no_solve_stats"))
    lines = [
        "# Phase 3B Grouped Block X/Y Implementation Preflight",
        "",
        "- Diagnostic semantics: no_solve_implementation_preflight_spec",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Ready for model edit: {status.get('ready_for_default_off_model_edit')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Proposed Mode",
        "",
        f"- Env: {mode.get('env')}",
        f"- Value: {mode.get('value')}",
        f"- Default-off: {mode.get('default_off')}",
        f"- Base mode: {mode.get('base_mode')}",
        "",
        "## Expected Stats",
        "",
        f"- Current block x/y targets: {counts.get('current_block_xy_target_variables')}",
        f"- Proposed grouped x/y targets: {counts.get('proposed_grouped_xy_target_variables')}",
        f"- Current block x/y Elements: {counts.get('current_block_xy_element_constraints')}",
        f"- Proposed grouped x/y Elements: {counts.get('proposed_grouped_xy_element_constraints')}",
        f"- Current selected geometry constraints: {counts.get('current_selected_geometry_constraints')}",
        f"- Proposed selected geometry constraints: {counts.get('proposed_selected_geometry_constraints')}",
        f"- Active guard BoolOr clauses unchanged: {counts.get('active_guard_bool_or_clauses_unchanged')}",
        "",
        "## Recipe",
        "",
    ]
    for item in list(report.get("implementation_recipe", [])):
        lines.append(f"- {item}")
    lines.extend(["", "## Non-Degeneration Rules", ""])
    for item in list(report.get("non_degeneration_rules", [])):
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


def render_phase3b_grouped_block_xy_implementation_preflight_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    mode = _mapping(report.get("proposed_mode"))
    counts = _mapping(report.get("expected_no_solve_stats"))
    return "\n".join(
        [
            "phase3b grouped block x/y implementation preflight",
            "diagnostic_semantics=no_solve_implementation_preflight_spec",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"ready_for_default_off_model_edit={status.get('ready_for_default_off_model_edit')}",
            f"mode={mode.get('value')}",
            f"current_block_xy_target_variables={counts.get('current_block_xy_target_variables')}",
            f"proposed_grouped_xy_target_variables={counts.get('proposed_grouped_xy_target_variables')}",
            f"current_block_xy_element_constraints={counts.get('current_block_xy_element_constraints')}",
            f"proposed_grouped_xy_element_constraints={counts.get('proposed_grouped_xy_element_constraints')}",
            f"active_guard_bool_or_clauses_unchanged={counts.get('active_guard_bool_or_clauses_unchanged')}",
        ]
    ) + "\n"


def _implementation_recipe() -> list[str]:
    return [
        "Add default-off block geometry value selected_block_active_guard_grouped_xy.",
        "Keep selected_block_active_guard as the base semantics and leave production defaults unchanged.",
        "Flatten padded pole slots per powered slot and create one padded-pole selector tied to block/local selectors.",
        "Use two x/y AddElement targets over the flattened padded pole-slot arrays, not per-block x/y targets.",
        "Apply selected geometry once per powered slot from the grouped x/y targets.",
        "Keep block/local selected literals and active-guard BoolOr clauses unchanged for pole activity semantics.",
        "Do not add row-wise guarded geometry constraints or powered/pole pairwise cover literals.",
        "After implementation, run a no-solve profile audit comparing selected_block_active_guard vs grouped_xy.",
    ]


def _non_degeneration_rules(counts: Mapping[str, Any]) -> list[str]:
    rows = counts.get("relation_row_count")
    return [
        f"Do not add O(relation_rows) geometry constraints; relation_rows={rows}.",
        "Do not add powered_slot x pole_slot cover literals.",
        "Do not change family lookup, family count, family-bound constraints, or hash truth sources.",
        "Do not claim proof or candidate elimination from this diagnostic formulation path.",
        "Block implementation if grouped x/y Elements exceed current per-block x/y Elements.",
    ]


def _required_tests() -> list[str]:
    return [
        "Default block geometry remains final_target.",
        "New mode is accepted only by explicit environment value.",
        "Fixture profile shows grouped x/y target and Element counts shrink versus selected_block_active_guard.",
        "No cover_choice_block_x__/cover_choice_block_y__ per-block target variables remain in grouped mode.",
        "No pairwise cover literal family appears.",
        "Small feasibility equivalence tests match selected_block_active_guard for covered/uncovered fixtures.",
    ]


def _expected_counts(candidate: Mapping[str, Any], scale: Mapping[str, Any]) -> dict[str, Any]:
    baseline = _mapping(scale.get("baseline"))
    relation = _mapping(candidate.get("grouped_relation"))
    powered = _int(relation.get("powered_slot_count") or baseline.get("powered_slot_count"))
    relation_rows = _int(relation.get("relation_row_count") or baseline.get("relation_row_count"))
    return {
        "powered_slot_count": powered,
        "relation_row_count": relation_rows,
        "current_block_xy_target_variables": _int(
            baseline.get("current_block_xy_target_variables")
        ),
        "proposed_grouped_xy_target_variables": int(powered * 2),
        "current_block_xy_element_constraints": _int(
            baseline.get("current_block_xy_element_constraints")
        ),
        "proposed_grouped_xy_element_constraints": int(powered * 2),
        "current_selected_geometry_constraints": _int(
            baseline.get("current_selected_geometry_constraints")
        ),
        "proposed_selected_geometry_constraints": int(powered * 4),
        "proposed_padded_index_link_constraints": int(powered),
        "active_guard_bool_or_clauses_unchanged": _int(
            baseline.get("current_active_guard_bool_or_clauses")
        ),
        "block_selected_literals_unchanged": _int(
            baseline.get("current_block_selected_literals")
        ),
        "local_selected_literals_unchanged": _int(
            baseline.get("current_local_selected_literals")
        ),
    }


def _checks(
    report: Mapping[str, Any],
    candidate: Mapping[str, Any],
    oracle: Mapping[str, Any],
    scale: Mapping[str, Any],
) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    counts = _mapping(report.get("expected_no_solve_stats"))
    return [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("candidate_present", "pass" if bool(candidate) else "fail", f"present={bool(candidate)}"),
        _check("oracle_present", "pass" if bool(oracle) else "fail", f"present={bool(oracle)}"),
        _check("scale_present", "pass" if bool(scale) else "fail", f"present={bool(scale)}"),
        _check("candidate_built", "pass" if _mapping(candidate.get("status")).get("outcome") == "grouped_block_xy_candidate_built" else "fail", str(_mapping(candidate.get("status")).get("outcome"))),
        _check("oracle_ready", "pass" if bool(_mapping(oracle.get("status")).get("oracle_ready_for_default_off_implementation", False)) else "fail", str(_mapping(oracle.get("status")).get("outcome"))),
        _check("target_count_reduction_expected", "pass" if _int(counts.get("proposed_grouped_xy_target_variables")) < _int(counts.get("current_block_xy_target_variables")) else "fail", f"{counts.get('proposed_grouped_xy_target_variables')} < {counts.get('current_block_xy_target_variables')}"),
        _check("element_count_reduction_expected", "pass" if _int(counts.get("proposed_grouped_xy_element_constraints")) < _int(counts.get("current_block_xy_element_constraints")) else "fail", f"{counts.get('proposed_grouped_xy_element_constraints')} < {counts.get('current_block_xy_element_constraints')}"),
        _check("ready_matches_inputs", "pass" if bool(status.get("ready_for_default_off_model_edit", False)) == bool(candidate and oracle and scale and _mapping(candidate.get("status")).get("outcome") == "grouped_block_xy_candidate_built" and bool(_mapping(oracle.get("status")).get("oracle_ready_for_default_off_implementation", False))) else "fail", f"ready={status.get('ready_for_default_off_model_edit')}"),
    ]


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


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
