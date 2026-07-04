"""Terminal fixed-witness verifier facade."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from src.search.pr2_l0_fixed_witness_core import (
    CANDIDATE_PROOF_FIELD,
    LOCKED_EXACT_ARTIFACT_PATHS,
    PortBindingModel,
    RoutingPlacementCore,
    RoutingSubproblem,
    TERMINAL_FIXED_WITNESS_AUDIT_FIELD,
    TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD,
    TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD,
    TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD,
    TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELD_ORDER,
    TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELDS,
    TERMINAL_FIXED_WITNESS_VERDICT_VOLATILE_DROPPABLE_FIELDS,
    TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
    TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
    TerminalFixedWitnessProjection,
    TerminalFixedWitnessVerdict,
    _BINDING_SECONDS,
    _CLEARED_SOLVER_ENV,
    _FIXED_SOLVER_ENV,
    _PROJECTED_CERTIFIED,
    _PROJECTED_UNPROVEN,
    _ROUTING_SECONDS,
    _WitnessIdentity,
    _accept,
    _apply_terminal_fixed_witness_audit_fields,
    _base_verdict,
    _candidate_key,
    _connector_body_exclusion_violation,
    _copy_candidate_records,
    _expected_unfiltered_ghost_anchor_index,
    _extract_pose_resolved_occupancy,
    _fixed_solver_environment,
    _ghost_cells,
    _identity_from_current_records,
    _load_authority_state,
    _load_facility_pools,
    _load_grid_dimensions,
    _load_json_object,
    _load_mandatory_instances,
    _normalize_port_specs,
    _optional_string,
    _pose_occupied_cells,
    _project_terminal_fixed_witness_records_from_capsule,
    _projection_rejected_reason,
    _reject,
    _require_mapping,
    _resolve_terminal_witness_identity,
    _routing_build_rejection,
    _routing_occupancy_digest,
    _solution_without_ghost,
    _strict_ghost_rect,
    _strict_int,
    _strict_json_copy,
    _strict_nonempty_string,
    _strict_record_ghost_rect,
    _validate_ghost_pick,
    _verdict_from_base,
    canonical_digest,
    canonical_state_bytes_for_fixed_witness,
    load_generic_io_requirements,
    load_wireless_sink_generic_input_slots,
    loads_strict_json,
    run_exact_routing_precheck,
    stable_terminal_fixed_witness_verdict,
    stable_terminal_fixed_witness_verdict_payload,
    verify_terminal_fixed_witness,
)

__all__ = (
    "CANDIDATE_PROOF_FIELD",
    "LOCKED_EXACT_ARTIFACT_PATHS",
    "PortBindingModel",
    "RoutingPlacementCore",
    "RoutingSubproblem",
    "TERMINAL_FIXED_WITNESS_AUDIT_FIELD",
    "TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD",
    "TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD",
    "TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD",
    "TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELD_ORDER",
    "TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELDS",
    "TERMINAL_FIXED_WITNESS_VERDICT_VOLATILE_DROPPABLE_FIELDS",
    "TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY",
    "TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION",
    "TerminalFixedWitnessProjection",
    "TerminalFixedWitnessVerdict",
    "_BINDING_SECONDS",
    "_CLEARED_SOLVER_ENV",
    "_FIXED_SOLVER_ENV",
    "_PROJECTED_CERTIFIED",
    "_PROJECTED_UNPROVEN",
    "_ROUTING_SECONDS",
    "_WitnessIdentity",
    "_accept",
    "_apply_terminal_fixed_witness_audit_fields",
    "_base_verdict",
    "_candidate_key",
    "_connector_body_exclusion_violation",
    "_copy_candidate_records",
    "_expected_unfiltered_ghost_anchor_index",
    "_extract_pose_resolved_occupancy",
    "_fixed_solver_environment",
    "_ghost_cells",
    "_identity_from_current_records",
    "_load_authority_state",
    "_load_facility_pools",
    "_load_grid_dimensions",
    "_load_json_object",
    "_load_mandatory_instances",
    "_normalize_port_specs",
    "_optional_string",
    "_pose_occupied_cells",
    "_project_terminal_fixed_witness_records_for_unverified_verdict",
    "_project_terminal_fixed_witness_records_from_capsule",
    "_projection_rejected_reason",
    "_reject",
    "_require_mapping",
    "_resolve_terminal_witness_identity",
    "_routing_build_rejection",
    "_routing_occupancy_digest",
    "_solution_without_ghost",
    "_strict_ghost_rect",
    "_strict_int",
    "_strict_json_copy",
    "_strict_nonempty_string",
    "_strict_record_ghost_rect",
    "_validate_ghost_pick",
    "_verdict_from_base",
    "attach_terminal_fixed_witness_audit_fields",
    "canonical_digest",
    "canonical_state_bytes_for_fixed_witness",
    "load_generic_io_requirements",
    "load_wireless_sink_generic_input_slots",
    "loads_strict_json",
    "project_terminal_fixed_witness_records_for_sink",
    "run_exact_routing_precheck",
    "stable_terminal_fixed_witness_verdict",
    "stable_terminal_fixed_witness_verdict_payload",
    "verify_terminal_fixed_witness",
)


def project_terminal_fixed_witness_records_for_sink(
    *,
    candidate_records: MutableMapping[str, dict[str, Any]],
    final_result: Mapping[str, Any],
    verdict: TerminalFixedWitnessVerdict | None,
) -> TerminalFixedWitnessProjection:
    """Fail-closed public compatibility wrapper.

    A process-local ``TerminalFixedWitnessVerdict`` is diagnostic data only.  The
    public proof path must call the isolated capsule sink, which invokes the
    private verified projection helper only after nonce/source/artifact/identity
    checks have accepted the child response.
    """

    return _project_terminal_fixed_witness_records_for_unverified_verdict(
        candidate_records=candidate_records,
        final_result=final_result,
        verdict=verdict,
    )


def _project_terminal_fixed_witness_records_for_unverified_verdict(
    *,
    candidate_records: MutableMapping[str, dict[str, Any]],
    final_result: Mapping[str, Any],
    verdict: TerminalFixedWitnessVerdict | None,
) -> TerminalFixedWitnessProjection:
    return _project_terminal_fixed_witness_records_from_capsule(
        candidate_records=candidate_records,
        final_result=final_result,
        verdict=verdict,
        forced_rejected_reason=(
            "terminal_fixed_witness_capsule_required"
            if verdict is not None
            else "terminal_fixed_witness_fresh_verdict_missing"
        ),
    )
def attach_terminal_fixed_witness_audit_fields(
    *,
    candidate_records: MutableMapping[str, dict[str, Any]],
    final_result: Mapping[str, Any],
    verdict: TerminalFixedWitnessVerdict,
) -> None:
    """Attach non-authoritative FIX-1 audit fields to the durable terminal record."""

    identity = _identity_from_current_records(candidate_records, final_result)
    record = candidate_records.get(identity.candidate_key)
    if isinstance(record, dict):
        reason = None if verdict.publishable else verdict.reason
        _apply_terminal_fixed_witness_audit_fields(
            record,
            verdict=verdict,
            publishable=bool(verdict.publishable),
            projected_status=(
                _PROJECTED_CERTIFIED if verdict.publishable else _PROJECTED_UNPROVEN
            ),
            rejected_reason=reason or "terminal_fixed_witness_not_publishable",
        )
