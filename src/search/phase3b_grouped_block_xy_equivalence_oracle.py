from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import _check, _display_path, _mapping

GROUPED_BLOCK_XY_ORACLE_SOURCE = "phase3b_grouped_block_xy_equivalence_oracle_v1"
DEFAULT_SCALE_EQUIVALENCE_PATH = Path(
    ".artifacts/phase3b_active_guard_block_xy_scale_equivalence_20260423/"
    "active_guard_block_xy_scale_equivalence.json"
)
DEFAULT_PROTO_SHAPE_AUDIT_PATH = Path(
    ".artifacts/phase3b_active_guard_proto_shape_audit_20260423_r4/"
    "active_guard_proto_shape_audit.json"
)
DEFAULT_RESIDUAL_SURFACE_PATH = Path(
    ".artifacts/phase3b_active_guard_residual_surface_20260423_r3/"
    "active_guard_residual_surface.json"
)
DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH = Path(
    ".artifacts/phase3b_selected_block_active_guard_equivalence_20260423/"
    "selected_block_equivalence.json"
)


def build_phase3b_grouped_block_xy_equivalence_oracle(
    project_root: Path,
    *,
    scale_equivalence_path: Optional[Path] = None,
    proto_shape_audit_path: Optional[Path] = None,
    residual_surface_path: Optional[Path] = None,
    selected_block_equivalence_path: Optional[Path] = None,
    grouped_candidate_path: Optional[Path] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    scale_path = _resolve(project_root, scale_equivalence_path or DEFAULT_SCALE_EQUIVALENCE_PATH)
    proto_path = _resolve(project_root, proto_shape_audit_path or DEFAULT_PROTO_SHAPE_AUDIT_PATH)
    residual_path = _resolve(project_root, residual_surface_path or DEFAULT_RESIDUAL_SURFACE_PATH)
    selected_path = _resolve(
        project_root,
        selected_block_equivalence_path or DEFAULT_SELECTED_BLOCK_EQUIVALENCE_PATH,
    )
    candidate_path = _resolve(project_root, grouped_candidate_path) if grouped_candidate_path else None

    scale = _load_json(scale_path)
    proto = _load_json(proto_path)
    residual = _load_json(residual_path)
    selected = _load_json(selected_path)
    candidate = _load_json(candidate_path) if candidate_path else {}

    original = _original_relation_summary(scale, proto, residual, selected)
    proposed = _proposed_grouped_relation_summary(candidate, original)
    gates = _gates(scale, proto, residual, selected, candidate, original, proposed)
    blockers = _implementation_blockers(gates, candidate)
    ready = bool(gates) and all(
        str(gate.get("status")) == "pass"
        for gate in gates
        if bool(gate.get("blocking", False))
    )
    inputs_present = all(bool(item) for item in (scale, proto, residual, selected))
    outcome = (
        "grouped_block_xy_equivalence_oracle_ready"
        if ready
        else (
            "grouped_block_xy_equivalence_oracle_blocked"
            if inputs_present
            else "grouped_block_xy_equivalence_oracle_incomplete"
        )
    )
    recommendation = _recommendation(ready, inputs_present, candidate)

    report: dict[str, Any] = {
        "metadata": {
            "source": GROUPED_BLOCK_XY_ORACLE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_grouped_block_xy_equivalence_oracle",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": _display_path(project_root, project_root),
            "active_guard_block_xy_scale_equivalence": _display_path(project_root, scale_path),
            "active_guard_proto_shape_audit": _display_path(project_root, proto_path),
            "active_guard_residual_surface": _display_path(project_root, residual_path),
            "selected_block_equivalence": _display_path(project_root, selected_path),
            "grouped_candidate": _display_path(project_root, candidate_path)
            if candidate_path
            else None,
        },
        "status": {
            "completed": True,
            "evaluated": bool(inputs_present),
            "outcome": outcome,
            "oracle_ready_for_default_off_implementation": bool(ready),
            "recommendation": recommendation.get("next_action"),
        },
        "input_summary": _input_summary(scale, proto, residual, selected, candidate),
        "original_relation_summary": original,
        "proposed_grouped_relation_summary": proposed,
        "semantic_contract": _semantic_contract(),
        "gates": gates,
        "implementation_blockers": blockers,
        "recommendation": recommendation,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, scale, proto, residual, selected)
    return report


def render_phase3b_grouped_block_xy_equivalence_oracle_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    original = _mapping(report.get("original_relation_summary"))
    proposed = _mapping(report.get("proposed_grouped_relation_summary"))
    rec = _mapping(report.get("recommendation"))
    lines = [
        "# Phase 3B Grouped Block X/Y Equivalence Oracle",
        "",
        "- Diagnostic semantics: no_solve_grouped_block_xy_equivalence_oracle",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- candidate_elimination_claim: {bool(_mapping(report.get('metadata')).get('candidate_elimination_claim', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Ready for default-off implementation: {status.get('oracle_ready_for_default_off_implementation')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Original Relation",
        "",
        f"- Powered slots: {original.get('powered_slot_count')}",
        f"- Pole slots: {original.get('pole_slot_count')}",
        f"- Block size: {original.get('block_size')}",
        f"- Padded pole positions: {original.get('padded_pole_position_count')}",
        f"- Relation rows: {original.get('relation_row_count')}",
        f"- Signature bijection valid: {original.get('active_guard_signature_bijection_valid')}",
        f"- ActiveGuard relation equivalent: {original.get('active_guard_relation_equivalent')}",
        f"- Residual shared surface: {original.get('residual_shared_power_pole_slot_surface')}",
        "",
        "## Proposed Grouped Relation",
        "",
        f"- Present: {proposed.get('present')}",
        f"- Relation rows: {proposed.get('relation_row_count')}",
        f"- Same-pole x/y coupling: {proposed.get('same_pole_xy_coupling')}",
        f"- Default-off: {proposed.get('default_off')}",
        f"- Degenerates to direct guarded geometry: {proposed.get('degenerates_to_direct_guarded_geometry')}",
        f"- Degenerates to pairwise cover literals: {proposed.get('degenerates_to_pairwise_cover_literals')}",
        "",
        "## Semantic Contract",
        "",
    ]
    for item in list(report.get("semantic_contract", [])):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Status | Blocking | Detail |",
            "| --- | --- | --- | --- |",
        ]
    )
    for gate in list(report.get("gates", [])):
        if isinstance(gate, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(gate.get("gate_id")),
                        _cell(gate.get("status")),
                        _cell(gate.get("blocking")),
                        _cell(gate.get("detail")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Blockers", ""])
    blockers = list(report.get("implementation_blockers", []))
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- Classification: {rec.get('classification')}",
            f"- Next action: {rec.get('next_action')}",
            f"- Reason: {rec.get('reason')}",
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


def render_phase3b_grouped_block_xy_equivalence_oracle_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    original = _mapping(report.get("original_relation_summary"))
    proposed = _mapping(report.get("proposed_grouped_relation_summary"))
    rec = _mapping(report.get("recommendation"))
    failed_gates = [
        str(gate.get("gate_id"))
        for gate in list(report.get("gates", []))
        if isinstance(gate, Mapping)
        and bool(gate.get("blocking", False))
        and str(gate.get("status")) != "pass"
    ]
    return "\n".join(
        [
            "phase3b grouped block x/y equivalence oracle",
            "diagnostic_semantics=no_solve_grouped_block_xy_equivalence_oracle",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"oracle_ready_for_default_off_implementation={status.get('oracle_ready_for_default_off_implementation')}",
            f"relation_row_count={original.get('relation_row_count')}",
            f"active_guard_signature_bijection_valid={original.get('active_guard_signature_bijection_valid')}",
            f"grouped_candidate_present={proposed.get('present')}",
            f"same_pole_xy_coupling={proposed.get('same_pole_xy_coupling')}",
            f"default_off={proposed.get('default_off')}",
            f"blocking_gate_count={len(failed_gates)}",
            f"blocking_gates={','.join(failed_gates)}",
            f"classification={rec.get('classification')}",
            f"next_action={rec.get('next_action')}",
        ]
    ) + "\n"


def _input_summary(
    scale: Mapping[str, Any],
    proto: Mapping[str, Any],
    residual: Mapping[str, Any],
    selected: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "scale_equivalence_present": bool(scale),
        "proto_shape_audit_present": bool(proto),
        "residual_surface_present": bool(residual),
        "selected_block_equivalence_present": bool(selected),
        "grouped_candidate_present": bool(candidate),
        "input_outcomes": {
            "scale_equivalence": _mapping(scale.get("status")).get("outcome"),
            "proto_shape_audit": _mapping(proto.get("status")).get("outcome"),
            "residual_surface": _mapping(residual.get("status")).get("outcome"),
            "selected_block_equivalence": _mapping(selected.get("status")).get("outcome"),
        },
    }


def _original_relation_summary(
    scale: Mapping[str, Any],
    proto: Mapping[str, Any],
    residual: Mapping[str, Any],
    selected: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = _mapping(scale.get("baseline"))
    direct = _mapping(_mapping(scale.get("candidate_estimates")).get("direct_guarded_geometry"))
    shape = _mapping(proto.get("active_guard_shape"))
    witness = _mapping(proto.get("witness_stats"))
    relationship = _mapping(residual.get("relationship"))
    relation = _mapping(_mapping(selected.get("relation_equivalence")).get("active_guard_relation"))
    return {
        "powered_slot_count": _as_int(baseline.get("powered_slot_count")),
        "pole_slot_count": _as_int(baseline.get("pole_slot_count")),
        "block_size": _as_int(baseline.get("block_size")),
        "block_count_per_powered_slot": _as_int(baseline.get("block_count_per_powered_slot")),
        "padded_pole_position_count": _as_int(baseline.get("padded_pole_position_count")),
        "relation_row_count": _as_int(baseline.get("relation_row_count")),
        "current_block_xy_target_variables": _as_int(
            baseline.get("current_block_xy_target_variables")
        ),
        "current_block_xy_element_constraints": _as_int(
            baseline.get("current_block_xy_element_constraints")
        ),
        "current_selected_geometry_constraints": _as_int(
            baseline.get("current_selected_geometry_constraints")
        ),
        "current_active_guard_bool_or_clauses": _as_int(
            baseline.get("current_active_guard_bool_or_clauses")
        ),
        "direct_guarded_geometry_risk": direct.get("risk"),
        "direct_guarded_geometry_net_constraint_delta": direct.get("net_constraint_delta"),
        "active_guard_signature_bijection_valid": bool(
            shape.get("expected_signature_bijection_valid", False)
        ),
        "missing_expected_signature_count": _as_int(
            shape.get("missing_expected_signature_count")
        ),
        "unexpected_signature_count": _as_int(shape.get("unexpected_signature_count")),
        "duplicate_signature_count": _as_int(shape.get("duplicate_signature_count")),
        "pole_key_mismatch_count": _as_int(shape.get("pole_key_mismatch_count")),
        "witness_selected_interval_encoding": witness.get("selected_interval_encoding"),
        "active_guard_relation_equivalent": bool(relation.get("equivalent", False)),
        "active_guard_relation_row_count": _as_int(relation.get("relation_row_count")),
        "active_guard_inactive_powered_slot_guard_equivalent": bool(
            relation.get("inactive_powered_slot_guard_equivalent", False)
        ),
        "residual_shared_power_pole_slot_surface": bool(
            relationship.get("shared_power_pole_slot_surface", False)
        ),
        "residual_direct_proto_edge": bool(relationship.get("direct_proto_edge", True)),
        "missing_family_bound_anchors": list(
            relationship.get("missing_family_bound_anchors", [])
        ),
    }


def _proposed_grouped_relation_summary(
    candidate: Mapping[str, Any],
    original: Mapping[str, Any],
) -> dict[str, Any]:
    relation = _candidate_relation(candidate)
    return {
        "present": bool(relation),
        "relation_row_count": _as_int(relation.get("relation_row_count")),
        "powered_slot_count": _as_int(relation.get("powered_slot_count")),
        "pole_slot_count": _as_int(relation.get("pole_slot_count")),
        "block_size": _as_int(relation.get("block_size")),
        "padded_pole_position_count": _as_int(relation.get("padded_pole_position_count")),
        "same_pole_xy_coupling": relation.get("same_pole_xy_coupling"),
        "semantic_projection_equivalence": _mapping(
            relation.get("semantic_projection_equivalence")
        ),
        "source_artifact_count": len(_mapping(candidate.get("source_artifacts"))),
        "field_source_count": len(_mapping(candidate.get("field_sources"))),
        "padding_identity_preserved": relation.get("padding_identity_preserved"),
        "optional_inactive_guard_preserved": relation.get(
            "optional_inactive_guard_preserved"
        ),
        "mandatory_powered_behavior_preserved": relation.get(
            "mandatory_powered_behavior_preserved"
        ),
        "block_selector_partition_preserved": relation.get(
            "block_selector_partition_preserved"
        ),
        "local_selector_partition_preserved": relation.get(
            "local_selector_partition_preserved"
        ),
        "bounds_interval_semantics_preserved": relation.get(
            "bounds_interval_semantics_preserved"
        ),
        "delta_interval_semantics_gate": relation.get("delta_interval_semantics_gate"),
        "family_lookup_count_unchanged": relation.get("family_lookup_count_unchanged"),
        "default_off": relation.get("default_off")
        if "default_off" in relation
        else _mapping(candidate.get("metadata")).get("default_off"),
        "degenerates_to_direct_guarded_geometry": bool(
            relation.get("degenerates_to_direct_guarded_geometry", False)
        ),
        "degenerates_to_pairwise_cover_literals": bool(
            relation.get("degenerates_to_pairwise_cover_literals", False)
        ),
        "matches_original_relation_rows": bool(
            relation
            and _as_int(relation.get("relation_row_count"))
            == _as_int(original.get("relation_row_count"))
        ),
    }


def _gates(
    scale: Mapping[str, Any],
    proto: Mapping[str, Any],
    residual: Mapping[str, Any],
    selected: Mapping[str, Any],
    candidate: Mapping[str, Any],
    original: Mapping[str, Any],
    proposed: Mapping[str, Any],
) -> list[dict[str, Any]]:
    relation = _candidate_relation(candidate)
    gates = [
        _gate("scale_input_present", "pass" if bool(scale) else "fail", "scale artifact present", True),
        _gate("proto_shape_input_present", "pass" if bool(proto) else "fail", "proto-shape artifact present", True),
        _gate("residual_surface_input_present", "pass" if bool(residual) else "fail", "residual-surface artifact present", True),
        _gate("selected_block_equivalence_input_present", "pass" if bool(selected) else "fail", "selected-block equivalence artifact present", True),
        _gate(
            "direct_replacement_marked_too_large",
            "pass"
            if str(
                _mapping(_mapping(scale.get("candidate_estimates")).get("direct_guarded_geometry")).get("risk")
            )
            == "too_large"
            else "fail",
            f"risk={_mapping(_mapping(scale.get('candidate_estimates')).get('direct_guarded_geometry')).get('risk')}",
            True,
        ),
        _gate(
            "active_guard_signature_bijection_valid",
            "pass" if bool(original.get("active_guard_signature_bijection_valid")) else "fail",
            (
                f"missing={original.get('missing_expected_signature_count')} "
                f"unexpected={original.get('unexpected_signature_count')} "
                f"duplicates={original.get('duplicate_signature_count')} "
                f"pole_mismatch={original.get('pole_key_mismatch_count')}"
            ),
            True,
        ),
        _gate(
            "active_guard_relation_equivalent",
            "pass" if bool(original.get("active_guard_relation_equivalent")) else "fail",
            f"relation_rows={original.get('active_guard_relation_row_count')}",
            True,
        ),
        _gate(
            "residual_surface_indirect_coupling_recorded",
            "pass"
            if bool(original.get("residual_shared_power_pole_slot_surface"))
            and not bool(original.get("residual_direct_proto_edge"))
            else "fail",
            (
                f"shared={original.get('residual_shared_power_pole_slot_surface')} "
                f"direct_proto_edge={original.get('residual_direct_proto_edge')}"
            ),
            True,
        ),
        _gate(
            "family_bound_data_complete",
            "pass" if not list(original.get("missing_family_bound_anchors", [])) else "fail",
            f"missing_family_bound_anchors={original.get('missing_family_bound_anchors')}",
            True,
        ),
        _gate(
            "grouped_relation_candidate_present",
            "pass" if bool(relation) else "fail",
            "grouped_candidate grouped_relation/proposed_grouped_relation is required",
            True,
        ),
    ]
    if not relation:
        gates.extend(
            [
                _gate("same_pole_xy_coupling_gate", "skipped", "no grouped candidate", True),
                _gate("semantic_projection_equivalence_gate", "skipped", "no grouped candidate", True),
                _gate("source_backing_gate", "skipped", "no grouped candidate", True),
                _gate("padding_identity_gate", "skipped", "no grouped candidate", True),
                _gate("optional_inactive_guard_gate", "skipped", "no grouped candidate", True),
                _gate("mandatory_powered_behavior_gate", "skipped", "no grouped candidate", True),
                _gate("block_local_selector_partition_gate", "skipped", "no grouped candidate", True),
                _gate("bounds_interval_semantics_gate", "skipped", "no grouped candidate", True),
                _gate("family_lookup_count_unchanged_gate", "skipped", "no grouped candidate", True),
                _gate("default_off_gate", "skipped", "no grouped candidate", True),
                _gate("not_direct_guarded_geometry_gate", "skipped", "no grouped candidate", True),
                _gate("not_pairwise_cover_literals_gate", "skipped", "no grouped candidate", True),
            ]
        )
        return gates

    gates.extend(
        [
            _same_int_gate("grouped_powered_slot_count_matches", proposed, original, "powered_slot_count"),
            _same_int_gate("grouped_pole_slot_count_matches", proposed, original, "pole_slot_count"),
            _same_int_gate("grouped_block_size_matches", proposed, original, "block_size"),
            _same_int_gate(
                "grouped_padded_pole_position_count_matches",
                proposed,
                original,
                "padded_pole_position_count",
            ),
            _same_int_gate("grouped_relation_row_count_matches", proposed, original, "relation_row_count"),
            _source_backing_gate(candidate),
            _bool_gate(proposed, "same_pole_xy_coupling", "same_pole_xy_coupling_gate"),
            _semantic_projection_gate(proposed, original),
            _bool_gate(proposed, "padding_identity_preserved", "padding_identity_gate"),
            _bool_gate(
                proposed,
                "optional_inactive_guard_preserved",
                "optional_inactive_guard_gate",
            ),
            _bool_gate(
                proposed,
                "mandatory_powered_behavior_preserved",
                "mandatory_powered_behavior_gate",
            ),
            _gate(
                "block_local_selector_partition_gate",
                "pass"
                if bool(proposed.get("block_selector_partition_preserved"))
                and bool(proposed.get("local_selector_partition_preserved"))
                else "fail",
                (
                    f"block={proposed.get('block_selector_partition_preserved')} "
                    f"local={proposed.get('local_selector_partition_preserved')}"
                ),
                True,
            ),
            _bool_gate(
                proposed,
                "bounds_interval_semantics_preserved",
                "bounds_interval_semantics_gate",
            ),
            _gate(
                "delta_interval_semantics_gate",
                "pass"
                if str(proposed.get("delta_interval_semantics_gate"))
                in {"not_applicable", "separate_gate_required", "preserved"}
                else "fail",
                f"delta_interval_semantics_gate={proposed.get('delta_interval_semantics_gate')}",
                True,
            ),
            _bool_gate(
                proposed,
                "family_lookup_count_unchanged",
                "family_lookup_count_unchanged_gate",
            ),
            _bool_gate(proposed, "default_off", "default_off_gate"),
            _gate(
                "not_direct_guarded_geometry_gate",
                "pass"
                if not bool(proposed.get("degenerates_to_direct_guarded_geometry"))
                else "fail",
                f"degenerates_to_direct_guarded_geometry={proposed.get('degenerates_to_direct_guarded_geometry')}",
                True,
            ),
            _gate(
                "not_pairwise_cover_literals_gate",
                "pass"
                if not bool(proposed.get("degenerates_to_pairwise_cover_literals"))
                else "fail",
                f"degenerates_to_pairwise_cover_literals={proposed.get('degenerates_to_pairwise_cover_literals')}",
                True,
            ),
        ]
    )
    return gates


def _implementation_blockers(
    gates: list[Mapping[str, Any]],
    candidate: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not _candidate_relation(candidate):
        blockers.append(
            "No grouped block x/y relation candidate has been supplied; do not edit exact_coordinate_master.py yet."
        )
    for gate in gates:
        if bool(gate.get("blocking", False)) and str(gate.get("status")) != "pass":
            blockers.append(f"{gate.get('gate_id')}: {gate.get('detail')}")
    if not blockers:
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for blocker in blockers:
        if blocker not in seen:
            deduped.append(blocker)
            seen.add(blocker)
    return deduped


def _recommendation(
    ready: bool,
    inputs_present: bool,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if ready:
        return {
            "classification": "grouped_block_xy_oracle_ready",
            "next_action": "implement_default_off_grouped_block_xy_candidate_with_equivalence_tests",
            "reason": (
                "All blocking no-solve gates pass for the supplied grouped relation candidate."
            ),
        }
    if not inputs_present:
        return {
            "classification": "input_artifacts_incomplete",
            "next_action": "refresh_active_guard_scale_proto_residual_and_selected_block_artifacts",
            "reason": "One or more required no-solve input artifacts is missing or unreadable.",
        }
    if not _candidate_relation(candidate):
        return {
            "classification": "grouped_relation_candidate_missing",
            "next_action": "draft_grouped_relation_candidate_and_synthetic_oracle",
            "reason": (
                "The scale and equivalence evidence says direct replacement is too large; "
                "a grouped candidate must be specified before model code changes."
            ),
        }
    return {
        "classification": "grouped_relation_candidate_failed_gates",
        "next_action": "repair_grouped_relation_candidate_before_implementation",
        "reason": "The grouped candidate exists but does not satisfy every blocking semantic gate.",
    }


def _checks(
    report: Mapping[str, Any],
    scale: Mapping[str, Any],
    proto: Mapping[str, Any],
    residual: Mapping[str, Any],
    selected: Mapping[str, Any],
) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    status = _mapping(report.get("status"))
    checks = [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("candidate_elimination_claim_false", "pass" if not bool(metadata.get("candidate_elimination_claim", True)) else "fail", "candidate_elimination_claim=false"),
        _check("scale_equivalence_present", "pass" if bool(scale) else "fail", f"present={bool(scale)}"),
        _check("proto_shape_audit_present", "pass" if bool(proto) else "fail", f"present={bool(proto)}"),
        _check("residual_surface_present", "pass" if bool(residual) else "fail", f"present={bool(residual)}"),
        _check("selected_block_equivalence_present", "pass" if bool(selected) else "fail", f"present={bool(selected)}"),
        _check(
            "oracle_ready_matches_gates",
            "pass"
            if bool(status.get("oracle_ready_for_default_off_implementation"))
            == all(
                str(gate.get("status")) == "pass"
                for gate in list(report.get("gates", []))
                if isinstance(gate, Mapping) and bool(gate.get("blocking", False))
            )
            else "fail",
            f"ready={status.get('oracle_ready_for_default_off_implementation')}",
        ),
    ]
    for gate in list(report.get("gates", [])):
        if not isinstance(gate, Mapping):
            continue
        checks.append(
            _check(
                f"gate_{gate.get('gate_id')}",
                str(gate.get("status")),
                str(gate.get("detail")),
            )
        )
    return checks


def _semantic_contract() -> list[str]:
    return [
        "The grouped replacement must preserve the same existential witness relation as selected_block_active_guard.",
        "For each powered slot, x and y must be read from the same selected pole slot.",
        "Padding duplicates in the final block must preserve their original pole identity.",
        "Optional inactive powered slots and mandatory powered slots must keep the current guard behavior.",
        "Block and local selector partitions must stay exactly-one where the current encoding requires them.",
        "Bounds-mode selected interval semantics must be preserved; delta mode needs a separate explicit gate.",
        "Counts and hashes are not enough; the grouped candidate must include source-backed semantic projection equivalence evidence.",
        "Family lookup, family counts, family-bound constraints, and hash truth sources must be unchanged.",
        "The path must remain default-off diagnostic/formulation work until equivalence and bounded probes pass.",
        "A candidate that merely expands into direct guarded geometry or pairwise cover literals is blocked.",
    ]


def _candidate_relation(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    relation = _mapping(candidate.get("grouped_relation"))
    if relation:
        return relation
    return _mapping(candidate.get("proposed_grouped_relation"))


def _same_int_gate(
    gate_id: str,
    proposed: Mapping[str, Any],
    original: Mapping[str, Any],
    key: str,
) -> dict[str, Any]:
    proposed_value = _as_int(proposed.get(key))
    original_value = _as_int(original.get(key))
    return _gate(
        gate_id,
        "pass" if proposed_value == original_value and original_value > 0 else "fail",
        f"proposed={proposed_value} original={original_value}",
        True,
    )


def _bool_gate(proposed: Mapping[str, Any], key: str, gate_id: str) -> dict[str, Any]:
    return _gate(gate_id, "pass" if bool(proposed.get(key)) else "fail", f"{key}={proposed.get(key)}", True)


def _semantic_projection_gate(
    proposed: Mapping[str, Any],
    original: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _mapping(proposed.get("semantic_projection_equivalence"))
    evaluated = bool(evidence.get("evaluated", False))
    equivalent = bool(evidence.get("equivalent", False))
    row_count_matches = _as_int(evidence.get("relation_row_count")) == _as_int(
        original.get("relation_row_count")
    )
    same_pole_checked = bool(evidence.get("same_pole_xy_coupling_checked", False))
    padding_checked = bool(evidence.get("padding_identity_checked", False))
    refs = list(evidence.get("evidence_refs", []))
    original_hash = str(evidence.get("original_relation_hash") or "")
    candidate_hash = str(evidence.get("candidate_relation_hash") or "")
    hash_algorithm = str(evidence.get("relation_hash_algorithm") or "")
    hashes_match = bool(original_hash and candidate_hash and original_hash == candidate_hash)
    structured_refs = all(
        isinstance(ref, Mapping)
        and bool(ref.get("artifact"))
        and bool(ref.get("json_pointer"))
        for ref in refs
    )
    status = (
        "pass"
        if evaluated
        and equivalent
        and row_count_matches
        and same_pole_checked
        and padding_checked
        and bool(refs)
        and structured_refs
        and hashes_match
        and bool(hash_algorithm)
        else "fail"
    )
    detail = (
        f"evaluated={evaluated} equivalent={equivalent} "
        f"row_count={evidence.get('relation_row_count')} "
        f"same_pole_checked={same_pole_checked} padding_checked={padding_checked} "
        f"hashes_match={hashes_match} hash_algorithm={hash_algorithm} "
        f"structured_refs={structured_refs} evidence_refs={len(refs)}"
    )
    return _gate("semantic_projection_equivalence_gate", status, detail, True)


def _source_backing_gate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = _mapping(candidate.get("source_artifacts"))
    field_sources = _mapping(candidate.get("field_sources"))
    required_artifacts = {
        "scale_equivalence",
        "selected_block_equivalence",
        "proto_shape_audit",
        "grouped_oracle",
    }
    required_fields = {
        "grouped_relation.powered_slot_count",
        "grouped_relation.pole_slot_count",
        "grouped_relation.block_size",
        "grouped_relation.padded_pole_position_count",
        "grouped_relation.relation_row_count",
        "grouped_relation.same_pole_xy_coupling",
        "grouped_relation.semantic_projection_equivalence",
        "grouped_relation.family_lookup_count_unchanged",
        "grouped_relation.default_off",
    }
    missing_artifacts = sorted(
        required_artifacts - {str(key) for key in artifacts.keys()}
    )
    missing_fields = sorted(required_fields - {str(key) for key in field_sources.keys()})
    hashes_valid = all(
        isinstance(value, Mapping)
        and bool(value.get("path"))
        and len(str(value.get("sha256") or "")) == 64
        for value in artifacts.values()
    )
    refs_valid = all(
        isinstance(refs, list)
        and bool(refs)
        and all(
            isinstance(ref, Mapping)
            and bool(ref.get("artifact"))
            and bool(ref.get("json_pointer"))
            for ref in refs
        )
        for refs in field_sources.values()
    )
    status = (
        "pass"
        if not missing_artifacts
        and not missing_fields
        and hashes_valid
        and refs_valid
        else "fail"
    )
    return _gate(
        "source_backing_gate",
        status,
        (
            f"missing_artifacts={missing_artifacts} missing_fields={missing_fields} "
            f"hashes_valid={hashes_valid} refs_valid={refs_valid}"
        ),
        True,
    )


def _gate(gate_id: str, status: str, detail: str, blocking: bool) -> dict[str, Any]:
    allowed = {"pass", "fail", "skipped"}
    if status not in allowed:
        status = "fail"
    return {
        "gate_id": str(gate_id),
        "status": status,
        "detail": str(detail),
        "blocking": bool(blocking),
    }


def _resolve(project_root: Path, path: Optional[Path]) -> Path:
    if path is None:
        return project_root
    path = Path(path)
    if path.is_absolute():
        return path
    return project_root / path


def _load_json(path: Optional[Path]) -> Mapping[str, Any]:
    if path is None:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
