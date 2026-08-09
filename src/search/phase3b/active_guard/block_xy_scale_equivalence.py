from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import _check, _display_path, _mapping

ACTIVE_GUARD_BLOCK_XY_SCALE_SOURCE = "phase3b_active_guard_block_xy_scale_equivalence_v1"
DEFAULT_PROTO_SHAPE_AUDIT_PATH = Path(
    ".artifacts/phase3b_active_guard_proto_shape_audit_20260423_r4/"
    "active_guard_proto_shape_audit.json"
)
DEFAULT_RESIDUAL_SURFACE_PATH = Path(
    ".artifacts/phase3b_active_guard_residual_surface_20260423_r3/"
    "active_guard_residual_surface.json"
)


def build_phase3b_active_guard_block_xy_scale_equivalence(
    project_root: Path,
    *,
    proto_shape_audit_path: Optional[Path] = None,
    residual_surface_path: Optional[Path] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    proto_path = _resolve(project_root, proto_shape_audit_path or DEFAULT_PROTO_SHAPE_AUDIT_PATH)
    residual_path = _resolve(project_root, residual_surface_path or DEFAULT_RESIDUAL_SURFACE_PATH)
    proto = _load_json(proto_path)
    residual = _load_json(residual_path)
    baseline = _baseline(proto, residual)
    candidates = _candidate_estimates(baseline)
    gates = _equivalence_gates()
    recommendation = _recommendation(candidates)
    status = {
        "completed": True,
        "evaluated": bool(proto and residual),
        "outcome": (
            "active_guard_block_xy_scale_equivalence_estimated"
            if proto and residual
            else "active_guard_block_xy_scale_equivalence_incomplete"
        ),
        "recommendation": recommendation.get("next_action"),
    }
    report: dict[str, Any] = {
        "metadata": {
            "source": ACTIVE_GUARD_BLOCK_XY_SCALE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_scale_and_equivalence_estimate",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": _display_path(project_root, project_root),
            "active_guard_proto_shape_audit": _display_path(project_root, proto_path),
            "active_guard_residual_surface": _display_path(project_root, residual_path),
        },
        "status": status,
        "baseline": baseline,
        "candidate_estimates": candidates,
        "equivalence_gates": gates,
        "recommendation": recommendation,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, proto, residual)
    return report


def render_phase3b_active_guard_block_xy_scale_equivalence_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    baseline = _mapping(report.get("baseline"))
    candidates = _mapping(report.get("candidate_estimates"))
    recommendation = _mapping(report.get("recommendation"))
    lines = [
        "# Phase 3B ActiveGuard Block XY Scale/Equivalence Estimate",
        "",
        "- Diagnostic semantics: no_solve_scale_and_equivalence_estimate",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- candidate_elimination_claim: {bool(_mapping(report.get('metadata')).get('candidate_elimination_claim', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Baseline",
        "",
        f"- Powered slots: {baseline.get('powered_slot_count')}",
        f"- Power-pole slots: {baseline.get('pole_slot_count')}",
        f"- Block size: {baseline.get('block_size')}",
        f"- Blocks per powered slot: {baseline.get('block_count_per_powered_slot')}",
        f"- Padded pole positions: {baseline.get('padded_pole_position_count')}",
        f"- Current block x/y target vars: {baseline.get('current_block_xy_target_variables')}",
        f"- Current block x/y Element constraints: {baseline.get('current_block_xy_element_constraints')}",
        f"- Current selected geometry constraints: {baseline.get('current_selected_geometry_constraints')}",
        f"- Current active-guard BoolOr clauses: {baseline.get('current_active_guard_bool_or_clauses')}",
        "",
        "## Candidate Estimates",
        "",
        "| Candidate | Risk | Vars Removed | Vars Added | Constraints Removed | Constraints Added | Net Constraint Delta |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, candidate in sorted(candidates.items()):
        item = _mapping(candidate)
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(name),
                    _cell(item.get("risk")),
                    _cell(item.get("variables_removed")),
                    _cell(item.get("variables_added")),
                    _cell(item.get("constraints_removed")),
                    _cell(item.get("constraints_added")),
                    _cell(item.get("net_constraint_delta")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Equivalence Gates",
            "",
        ]
    )
    for gate in list(report.get("equivalence_gates", [])):
        lines.append(f"- {gate}")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- Classification: {recommendation.get('classification')}",
            f"- Next action: {recommendation.get('next_action')}",
            f"- Reason: {recommendation.get('reason')}",
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


def render_phase3b_active_guard_block_xy_scale_equivalence_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    baseline = _mapping(report.get("baseline"))
    direct = _mapping(_mapping(report.get("candidate_estimates")).get("direct_guarded_geometry"))
    rec = _mapping(report.get("recommendation"))
    return "\n".join(
        [
            "phase3b active-guard block-xy scale/equivalence estimate",
            "diagnostic_semantics=no_solve_scale_and_equivalence_estimate",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"powered_slot_count={baseline.get('powered_slot_count')}",
            f"pole_slot_count={baseline.get('pole_slot_count')}",
            f"relation_row_count={baseline.get('relation_row_count')}",
            f"current_block_xy_target_variables={baseline.get('current_block_xy_target_variables')}",
            f"direct_guarded_geometry_constraints_added={direct.get('constraints_added')}",
            f"direct_guarded_geometry_net_constraint_delta={direct.get('net_constraint_delta')}",
            f"classification={rec.get('classification')}",
            f"next_action={rec.get('next_action')}",
        ]
    ) + "\n"


def _baseline(proto: Mapping[str, Any], residual: Mapping[str, Any]) -> dict[str, Any]:
    independent = _mapping(_mapping(proto.get("active_guard_shape")).get("independent_expected"))
    witness = _mapping(proto.get("witness_stats"))
    residual_protocol = _mapping(_mapping(residual.get("protocol_surface")).get("block_xy_surface"))
    powered = int(independent.get("powered_slot_count", 0) or 0)
    poles = int(independent.get("pole_slot_count", 0) or 0)
    block_size = int(independent.get("block_size", 0) or 0)
    padded_positions = int(independent.get("padded_pole_position_count", 0) or 0)
    block_targets = int(witness.get("block_intermediate_target_channel_count", 0) or 0)
    blocks = int(block_targets / (powered * 2)) if powered else 0
    selected_geometry = int(witness.get("block_selected_geometry_constraint_count", 0) or 0)
    element_constraints = int(witness.get("block_element_constraint_count", 0) or 0)
    guard_clauses = int(witness.get("block_active_guard_clause_count", 0) or 0)
    return {
        "powered_slot_count": powered,
        "pole_slot_count": poles,
        "block_size": block_size,
        "block_count_per_powered_slot": blocks,
        "padded_pole_position_count": padded_positions,
        "relation_row_count": int(powered * padded_positions),
        "template_powered_slot_counts": dict(_mapping(independent.get("powered_slot_counts"))),
        "template_relation_row_counts": dict(_mapping(independent.get("template_counts"))),
        "current_block_xy_target_variables": block_targets,
        "current_block_xy_element_constraints": element_constraints,
        "current_selected_geometry_constraints": selected_geometry,
        "current_active_guard_bool_or_clauses": guard_clauses,
        "current_local_selected_literals": int(witness.get("local_selected_literal_count", 0) or 0),
        "current_block_selected_literals": int(witness.get("block_selected_literal_count", 0) or 0),
        "protocol_block_xy_constraint_count": int(residual_protocol.get("block_xy_constraint_count", 0) or 0),
        "protocol_block_x_constraint_count": int(residual_protocol.get("block_x_constraint_count", 0) or 0),
        "protocol_block_y_constraint_count": int(residual_protocol.get("block_y_constraint_count", 0) or 0),
    }


def _candidate_estimates(baseline: Mapping[str, Any]) -> dict[str, Any]:
    rows = int(baseline.get("relation_row_count", 0) or 0)
    powered = int(baseline.get("powered_slot_count", 0) or 0)
    poles = int(baseline.get("pole_slot_count", 0) or 0)
    current_xy_targets = int(baseline.get("current_block_xy_target_variables", 0) or 0)
    current_elements = int(baseline.get("current_block_xy_element_constraints", 0) or 0)
    current_geometry = int(baseline.get("current_selected_geometry_constraints", 0) or 0)
    direct_added = int(rows * 4)
    direct_removed = int(current_elements + current_geometry)
    pairwise_rows = int(powered * poles)
    pairwise_added_constraints = int(pairwise_rows * 4 + powered)
    return {
        "direct_guarded_geometry": {
            "description": "Replace block x/y Element targets with guarded geometry for every powered/padded-pole row.",
            "risk": "too_large",
            "variables_removed": current_xy_targets,
            "variables_added": 0,
            "constraints_removed": direct_removed,
            "constraints_added": direct_added,
            "net_constraint_delta": int(direct_added - direct_removed),
        },
        "pairwise_cover_literals": {
            "description": "Replace selectors with explicit powered-slot/pole-slot cover literals.",
            "risk": "too_large_without_grouping",
            "variables_removed": int(current_xy_targets),
            "variables_added": pairwise_rows,
            "constraints_removed": direct_removed,
            "constraints_added": pairwise_added_constraints,
            "net_constraint_delta": int(pairwise_added_constraints - direct_removed),
        },
        "grouped_block_local_encoding": {
            "description": "Search for a grouped replacement that preserves block/local selector semantics.",
            "risk": "needs_new_equivalence_oracle",
            "variables_removed": 0,
            "variables_added": 0,
            "constraints_removed": 0,
            "constraints_added": 0,
            "net_constraint_delta": 0,
        },
    }


def _equivalence_gates() -> list[str]:
    return [
        "padding_identity_preserved",
        "optional_powered_slot_inactive_guard_preserved",
        "mandatory_powered_slot_behavior_preserved",
        "block_selector_partition_preserved",
        "local_selector_partition_preserved",
        "both_axis_interval_semantics_preserved_for_bounds_mode",
        "delta_interval_mode_requires_separate_gate",
        "all_template_coverage_preserved",
        "family_lookup_and_family_count_semantics_unchanged",
        "forced_anchor_diagnostic_results_not_promoted_to_proof",
    ]


def _recommendation(candidates: Mapping[str, Any]) -> dict[str, Any]:
    direct = _mapping(candidates.get("direct_guarded_geometry"))
    if str(direct.get("risk")) == "too_large":
        return {
            "classification": "direct_guarded_geometry_too_large",
            "next_action": "design_grouped_default_off_block_xy_equivalence_oracle",
            "reason": (
                "Direct guarded geometry removes the block x/y Element surface but adds "
                "millions of guarded linear constraints; build a grouped equivalence plan before implementation."
            ),
        }
    return {
        "classification": "needs_more_input",
        "next_action": "refresh_scale_inputs",
        "reason": "Input artifacts were incomplete.",
    }


def _checks(report: Mapping[str, Any], proto: Mapping[str, Any], residual: Mapping[str, Any]) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    candidates = _mapping(report.get("candidate_estimates"))
    direct = _mapping(candidates.get("direct_guarded_geometry"))
    rec = _mapping(report.get("recommendation"))
    return [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("proto_shape_audit_present", "pass" if bool(proto) else "fail", f"present={bool(proto)}"),
        _check("residual_surface_present", "pass" if bool(residual) else "fail", f"present={bool(residual)}"),
        _check("direct_guarded_geometry_marked_too_large", "pass" if str(direct.get("risk")) == "too_large" else "fail", f"risk={direct.get('risk')} net_delta={direct.get('net_constraint_delta')}"),
        _check("recommend_grouped_oracle_before_implementation", "pass" if str(rec.get("classification")) == "direct_guarded_geometry_too_large" else "fail", str(rec.get("classification"))),
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


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
