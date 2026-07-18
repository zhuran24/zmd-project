"""Small terminal fixed-witness verifier core for the PR2 L0 verifier child."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import secrets
import time
from typing import AbstractSet, Any, Dict, Mapping, MutableMapping, Optional, Sequence, Tuple

from src.io.strict_json import loads_strict_json
from src.models.binding_subproblem import (
    PortBindingModel,
    load_generic_io_requirements,
    load_generic_input_slots_by_operation,
)
from src.models.routing_subproblem import (
    RoutingPlacementCore,
    RoutingSubproblem,
    run_exact_routing_precheck,
)
from src.search.certified_artifact_contract import LOCKED_EXACT_ARTIFACT_PATHS
from src.search.pr2_l0_replay_core import CANDIDATE_PROOF_FIELD, canonical_digest

TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION = 1
TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY = (
    "terminal_fixed_witness_binding_routing_v1"
)
TERMINAL_FIXED_WITNESS_AUDIT_FIELD = "terminal_fixed_witness_verifier"
TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD = "terminal_fixed_witness_publishable"
TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD = (
    "terminal_fixed_witness_projected_status"
)
TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD = (
    "terminal_fixed_witness_rejected_reason"
)
TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELD_ORDER = (
    "schema_version",
    "authority",
    "publishable",
    "projected_status",
    "candidate_key",
    "solution_digest",
    "ghost_rect_digest",
    "ghost_cells_digest",
    "witness_input_digest",
    "binding_assignment_digest",
    "port_specs_digest",
    "routing_occupancy_digest",
    "binding_status",
    "routing_status",
    "reason",
    "details",
)
TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELDS = frozenset(
    TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELD_ORDER
)
TERMINAL_FIXED_WITNESS_VERDICT_VOLATILE_DROPPABLE_FIELDS = frozenset(
    {"fresh_run_token"}
)

_PROJECTED_CERTIFIED = "CERTIFIED"
_PROJECTED_UNPROVEN = "UNPROVEN"
_BINDING_SECONDS = 600.0
_ROUTING_SECONDS = 600.0
_TOTAL_SOLVE_SECONDS = _BINDING_SECONDS + _ROUTING_SECONDS
_solver_budget_clock = time.monotonic

_FIXED_SOLVER_ENV = {
    "PYTHONHASHSEED": "0",
    "EXACT_CP_SAT_WORKERS": "1",
    "EXACT_MASTER_CP_SAT_WORKERS": "1",
    "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "1",
    "EXACT_BINDING_CP_SAT_WORKERS": "1",
    "EXACT_ROUTING_CP_SAT_WORKERS": "1",
    "EXACT_D2_CP_SAT_WORKERS": "1",
    "EXACT_PATCH_ROUTING_CP_SAT_WORKERS": "1",
    "EXACT_MASTER_RANDOM_SEED": "0",
    "EXACT_MASTER_RANDOM_SEED_BASE": "0",
}
_CLEARED_SOLVER_ENV = (
    "EXACT_BINDING_USE_OVERLOAD_SEPARATION",
    "EXACT_BINDING_DUMP_STATE",
)


@dataclass(frozen=True)
class TerminalFixedWitnessVerdict:
    schema_version: int
    authority: str
    fresh_run_token: str
    publishable: bool
    projected_status: str
    candidate_key: Optional[str]
    solution_digest: Optional[str]
    ghost_rect_digest: Optional[str]
    ghost_cells_digest: Optional[str]
    witness_input_digest: Optional[str]
    binding_assignment_digest: Optional[str] = None
    port_specs_digest: Optional[str] = None
    routing_occupancy_digest: Optional[str] = None
    binding_status: Optional[str] = None
    routing_status: Optional[str] = None
    reason: Optional[str] = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "schema_version": int(self.schema_version),
            "authority": str(self.authority),
            "fresh_run_token": str(self.fresh_run_token),
            "publishable": bool(self.publishable),
            "projected_status": str(self.projected_status),
            "candidate_key": self.candidate_key,
            "solution_digest": self.solution_digest,
            "ghost_rect_digest": self.ghost_rect_digest,
            "ghost_cells_digest": self.ghost_cells_digest,
            "witness_input_digest": self.witness_input_digest,
            "binding_assignment_digest": self.binding_assignment_digest,
            "port_specs_digest": self.port_specs_digest,
            "routing_occupancy_digest": self.routing_occupancy_digest,
            "binding_status": self.binding_status,
            "routing_status": self.routing_status,
            "reason": self.reason,
            "details": dict(self.details),
        }
        return _strict_json_copy(payload)


def stable_terminal_fixed_witness_verdict_payload(
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return the durable verdict projection or fail closed on unknown fields."""

    if not isinstance(payload, Mapping):
        raise ValueError("terminal fixed witness verdict payload must be a mapping")
    raw_fields = set(payload.keys())
    if any(not isinstance(field, str) for field in raw_fields):
        raise ValueError("terminal fixed witness verdict field must be a string")
    missing = sorted(TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELDS - raw_fields)
    if missing:
        raise ValueError(f"terminal fixed witness verdict missing stable field:{missing[0]}")
    unexpected = sorted(
        raw_fields
        - TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELDS
        - TERMINAL_FIXED_WITNESS_VERDICT_VOLATILE_DROPPABLE_FIELDS
    )
    if unexpected:
        raise ValueError(
            f"terminal fixed witness verdict unknown durable field:{unexpected[0]}"
        )
    return {
        field: _strict_json_copy(payload[field])
        for field in TERMINAL_FIXED_WITNESS_VERDICT_STABLE_FIELD_ORDER
    }


def stable_terminal_fixed_witness_verdict(
    verdict: TerminalFixedWitnessVerdict,
) -> Dict[str, Any]:
    return stable_terminal_fixed_witness_verdict_payload(verdict.to_dict())


@dataclass(frozen=True)
class TerminalFixedWitnessProjection:
    candidate_records: Dict[str, Dict[str, Any]]
    candidate_key: Optional[str]
    publishable: bool
    projected_status: str
    rejected_reason: Optional[str]


@dataclass(frozen=True)
class _WitnessIdentity:
    candidate_key: str
    solution_digest: str
    ghost_rect_digest: str
    ghost_cells_digest: str
    witness_input_digest: str
    ghost_rect: Dict[str, int]


@dataclass
class _FixedWitnessSolveBudget:
    """Share the fixed 600s + 600s envelope across all alternative solves."""

    started_at: float = field(default_factory=lambda: _solver_budget_clock())
    binding_seconds_used: float = 0.0
    routing_seconds_used: float = 0.0

    def remaining(self, stage: str) -> float:
        now = _solver_budget_clock()
        total_remaining = _TOTAL_SOLVE_SECONDS - max(0.0, now - self.started_at)
        if stage == "binding":
            stage_remaining = _BINDING_SECONDS - self.binding_seconds_used
        elif stage == "routing":
            stage_remaining = _ROUTING_SECONDS - self.routing_seconds_used
        else:
            raise ValueError(f"unknown fixed-witness solve stage: {stage}")
        return max(0.0, min(stage_remaining, total_remaining))

    def record(self, stage: str, started_at: float) -> None:
        elapsed = max(0.0, _solver_budget_clock() - started_at)
        if stage == "binding":
            self.binding_seconds_used += elapsed
        elif stage == "routing":
            self.routing_seconds_used += elapsed
        else:
            raise ValueError(f"unknown fixed-witness solve stage: {stage}")

    def audit_details(self, *, exhausted_stage: str) -> Dict[str, Any]:
        return {
            "exhausted_stage": str(exhausted_stage),
            "binding_seconds_budget": float(_BINDING_SECONDS),
            "binding_seconds_used": float(self.binding_seconds_used),
            "routing_seconds_budget": float(_ROUTING_SECONDS),
            "routing_seconds_used": float(self.routing_seconds_used),
            "total_solve_seconds_budget": float(_TOTAL_SOLVE_SECONDS),
            "total_wall_seconds_used": float(
                max(0.0, _solver_budget_clock() - self.started_at)
            ),
        }


_STORAGE_BOX_DOMINANCE_REJECT_REASON = (
    "terminal_fixed_witness_unbound_storage_box_violates_dominance_rule"
)


def _positive_generic_input_requirements(
    io_requirements: Mapping[str, Any],
) -> Dict[str, int]:
    raw_requirements = io_requirements.get("required_generic_inputs", {})
    if not isinstance(raw_requirements, Mapping):
        raise ValueError("required_generic_inputs must be a mapping")
    positive: Dict[str, int] = {}
    for raw_commodity, raw_required in raw_requirements.items():
        commodity = str(raw_commodity)
        required = _strict_int(
            raw_required,
            f"required_generic_inputs.{commodity}",
        )
        if required < 0:
            raise ValueError(
                f"required_generic_inputs.{commodity} must be non-negative"
            )
        if required > 0:
            positive[commodity] = int(required)
    return positive


def _selected_optional_storage_box_instance_ids(
    *,
    solution: Mapping[str, Any],
    mandatory_instances: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Return the deletable pose-optional boxes governed by the dominance rule."""

    mandatory_ids = {
        str(instance.get("instance_id", ""))
        for instance in mandatory_instances
        if str(instance.get("instance_id", ""))
    }
    selected: list[str] = []
    for raw_instance_id, raw_entry in solution.items():
        instance_id = str(raw_instance_id)
        if instance_id == "ghost_pick" or instance_id in mandatory_ids:
            continue
        entry = _require_mapping(raw_entry, f"solution.{instance_id}")
        if str(entry.get("facility_type", "")) == "protocol_storage_box":
            selected.append(instance_id)
    return sorted(set(selected))


def _apply_storage_box_dominance_constraints(
    *,
    binding_model: PortBindingModel,
    selected_storage_box_instance_ids: Sequence[str],
    positive_generic_input_requirements: Mapping[str, int],
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Make the fresh binding solve search only dominance-compliant box use."""

    selected_box_ids = sorted(set(str(item) for item in selected_storage_box_instance_ids))
    required_total = sum(int(value) for value in positive_generic_input_requirements.values())
    details: Dict[str, Any] = {
        "selected_storage_box_instance_ids": selected_box_ids,
        "required_generic_input_slot_total": int(required_total),
    }
    if not selected_box_ids:
        details["dominance_literal_counts"] = {}
        return None, details

    # Each active generic-input assignment occupies one physical slot.  More
    # deletable boxes than positive assignments makes at least one unbound box
    # inevitable, independent of the CP-SAT search order.
    if len(selected_box_ids) > int(required_total):
        details["minimum_inevitable_unbound_storage_box_count"] = (
            len(selected_box_ids) - int(required_total)
        )
        details["dominance_failure"] = "selected_box_count_exceeds_bindable_sink_count"
        return _STORAGE_BOX_DOMINANCE_REJECT_REASON, details

    selected_box_set = set(selected_box_ids)
    literals_by_box: Dict[str, list[Any]] = {
        instance_id: [] for instance_id in selected_box_ids
    }
    for raw_slot in binding_model.generic_input_slots:
        if not isinstance(raw_slot, Mapping):
            raise ValueError("generic input slot metadata must be a mapping")
        instance_id = str(raw_slot.get("instance_id", ""))
        if instance_id not in selected_box_set:
            continue
        if str(raw_slot.get("operation_type", "")) != "box_sink":
            continue
        slot_id = _strict_nonempty_string(
            raw_slot.get("slot_id"),
            f"generic_input_slots.{instance_id}.slot_id",
        )
        commodity_vars = binding_model.generic_input_vars.get(slot_id)
        if not isinstance(commodity_vars, Mapping):
            raise ValueError(f"generic input vars missing for slot {slot_id}")
        for commodity in sorted(positive_generic_input_requirements):
            literal = commodity_vars.get(commodity)
            if literal is not None:
                literals_by_box[instance_id].append(literal)

    literal_counts = {
        instance_id: len(literals_by_box[instance_id])
        for instance_id in selected_box_ids
    }
    details["dominance_literal_counts"] = literal_counts
    missing_literal_boxes = sorted(
        instance_id
        for instance_id, literals in literals_by_box.items()
        if not literals
    )
    if missing_literal_boxes:
        details["unbound_storage_box_instance_ids"] = missing_literal_boxes
        details["dominance_failure"] = "physical_generic_input_literal_missing"
        return _STORAGE_BOX_DOMINANCE_REJECT_REASON, details

    for instance_id in selected_box_ids:
        binding_model.model.AddBoolOr(literals_by_box[instance_id])
    return None, details


def _collect_active_generic_input_slots(
    *,
    binding_model: PortBindingModel,
    selection: Mapping[str, Any],
    positive_generic_input_requirements: Mapping[str, int],
) -> Tuple[Optional[str], Dict[str, Any], list[Dict[str, Any]]]:
    """Normalize the live slot selection without parsing composite slot IDs."""

    raw_assignments = selection.get("generic_inputs")
    if not isinstance(raw_assignments, Mapping):
        return (
            "terminal_fixed_witness_generic_input_selection_invalid",
            {"selection_error": "generic_inputs_not_mapping"},
            [],
        )

    slot_by_id: Dict[str, Mapping[str, Any]] = {}
    for raw_slot in binding_model.generic_input_slots:
        if not isinstance(raw_slot, Mapping):
            return (
                "terminal_fixed_witness_generic_input_selection_invalid",
                {"selection_error": "slot_metadata_not_mapping"},
                [],
            )
        raw_slot_id = raw_slot.get("slot_id")
        if not isinstance(raw_slot_id, str) or not raw_slot_id:
            return (
                "terminal_fixed_witness_generic_input_selection_invalid",
                {"selection_error": "slot_id_invalid"},
                [],
            )
        if raw_slot_id in slot_by_id:
            return (
                "terminal_fixed_witness_generic_input_selection_invalid",
                {"selection_error": "duplicate_slot_id", "slot_id": raw_slot_id},
                [],
            )
        slot_by_id[raw_slot_id] = raw_slot

    assignment_keys: set[str] = set()
    for raw_slot_id in raw_assignments:
        if not isinstance(raw_slot_id, str) or not raw_slot_id:
            return (
                "terminal_fixed_witness_generic_input_selection_invalid",
                {"selection_error": "assignment_slot_id_invalid"},
                [],
            )
        assignment_keys.add(raw_slot_id)
    expected_keys = set(slot_by_id)
    if assignment_keys != expected_keys:
        return (
            "terminal_fixed_witness_generic_input_selection_invalid",
            {
                "selection_error": "assignment_slot_set_mismatch",
                "missing_slot_ids": sorted(expected_keys - assignment_keys),
                "unknown_slot_ids": sorted(assignment_keys - expected_keys),
            },
            [],
        )

    active_slots: list[Dict[str, Any]] = []
    for slot_id in sorted(slot_by_id):
        raw_commodity = raw_assignments[slot_id]
        if not isinstance(raw_commodity, str) or not raw_commodity:
            return (
                "terminal_fixed_witness_generic_input_selection_invalid",
                {"selection_error": "assignment_commodity_invalid", "slot_id": slot_id},
                [],
            )
        if raw_commodity == "__unused__":
            continue
        if raw_commodity not in positive_generic_input_requirements:
            return (
                "terminal_fixed_witness_generic_input_selection_invalid",
                {
                    "selection_error": "assignment_commodity_not_required",
                    "slot_id": slot_id,
                    "commodity": raw_commodity,
                },
                [],
            )
        slot = slot_by_id[slot_id]
        if str(slot.get("type", "")) != "in":
            return (
                "terminal_fixed_witness_generic_input_selection_invalid",
                {"selection_error": "slot_type_invalid", "slot_id": slot_id},
                [],
            )
        active_slots.append(
            {
                "slot_id": slot_id,
                "instance_id": str(slot.get("instance_id", "")),
                "operation_type": str(slot.get("operation_type", "")),
                "x": _strict_int(slot.get("x"), f"generic_input_slots.{slot_id}.x"),
                "y": _strict_int(slot.get("y"), f"generic_input_slots.{slot_id}.y"),
                "dir": str(slot.get("dir", "")),
                "type": "in",
                "commodity": raw_commodity,
            }
        )
    return None, {}, active_slots


def _storage_box_dominance_violation(
    *,
    selected_storage_box_instance_ids: Sequence[str],
    active_generic_input_slots: Sequence[Mapping[str, Any]],
) -> Tuple[Optional[str], Dict[str, Any]]:
    selected_box_ids = sorted(set(str(item) for item in selected_storage_box_instance_ids))
    bound_counts = {instance_id: 0 for instance_id in selected_box_ids}
    for slot in active_generic_input_slots:
        instance_id = str(slot.get("instance_id", ""))
        if (
            instance_id in bound_counts
            and str(slot.get("operation_type", "")) == "box_sink"
        ):
            bound_counts[instance_id] += 1
    unbound = sorted(
        instance_id for instance_id, count in bound_counts.items() if int(count) <= 0
    )
    details: Dict[str, Any] = {
        "selected_storage_box_bound_sink_counts": bound_counts,
    }
    if unbound:
        details["unbound_storage_box_instance_ids"] = unbound
        details["dominance_rule"] = (
            "every selected optional protocol storage box must bind at least one "
            "physical generic-input sink slot"
        )
        return _STORAGE_BOX_DOMINANCE_REJECT_REASON, details
    return None, details


def _required_generic_input_endpoint_violation(
    *,
    active_generic_input_slots: Sequence[Mapping[str, Any]],
    normalized_port_specs: Sequence[Mapping[str, Any]],
    positive_generic_input_requirements: Mapping[str, int],
) -> Tuple[Optional[str], Dict[str, Any]]:
    port_spec_key_counts: Dict[Tuple[str, int, int, str, str, str], int] = {}
    source_spec_counts: Dict[str, int] = {}
    for spec in normalized_port_specs:
        commodity = str(spec.get("commodity", ""))
        key = (
            str(spec.get("instance_id", "")),
            _strict_int(spec.get("x"), "port_spec.x"),
            _strict_int(spec.get("y"), "port_spec.y"),
            str(spec.get("dir", "")),
            str(spec.get("type", "")),
            commodity,
        )
        port_spec_key_counts[key] = port_spec_key_counts.get(key, 0) + 1
        if key[4] == "out":
            source_spec_counts[commodity] = source_spec_counts.get(commodity, 0) + 1

    bound_counts = {commodity: 0 for commodity in positive_generic_input_requirements}
    routed_sink_counts = {
        commodity: 0 for commodity in positive_generic_input_requirements
    }
    slot_route_mismatches: list[Dict[str, Any]] = []
    for slot in active_generic_input_slots:
        commodity = str(slot.get("commodity", ""))
        if commodity in bound_counts:
            bound_counts[commodity] += 1
        expected_key = (
            str(slot.get("instance_id", "")),
            _strict_int(slot.get("x"), "generic_input_slot.x"),
            _strict_int(slot.get("y"), "generic_input_slot.y"),
            str(slot.get("dir", "")),
            "in",
            commodity,
        )
        matched_count = int(port_spec_key_counts.get(expected_key, 0))
        if matched_count == 1 and commodity in routed_sink_counts:
            routed_sink_counts[commodity] += 1
        else:
            slot_route_mismatches.append(
                {
                    "slot_id": str(slot.get("slot_id", "")),
                    "instance_id": expected_key[0],
                    "commodity": commodity,
                    "matching_routed_sink_spec_count": matched_count,
                }
            )

    endpoint_counts: Dict[str, Dict[str, int]] = {}
    incomplete_commodities: list[str] = []
    for commodity, required in sorted(positive_generic_input_requirements.items()):
        bound_count = int(bound_counts.get(commodity, 0))
        routed_sink_count = int(routed_sink_counts.get(commodity, 0))
        source_spec_count = int(source_spec_counts.get(commodity, 0))
        endpoint_counts[commodity] = {
            "required_sink_count": int(required),
            "bound_sink_count": bound_count,
            "routed_sink_spec_count": routed_sink_count,
            "source_spec_count": source_spec_count,
        }
        if (
            bound_count != int(required)
            or routed_sink_count != int(required)
            or source_spec_count <= 0
        ):
            incomplete_commodities.append(commodity)

    if incomplete_commodities or slot_route_mismatches:
        return (
            "terminal_fixed_witness_required_generic_input_endpoint_incomplete",
            {
                **endpoint_counts,
                "_audit": {
                    "incomplete_commodities": incomplete_commodities,
                    "slot_route_mismatches": slot_route_mismatches,
                },
            },
        )
    return None, endpoint_counts


def _required_generic_input_front_violation(
    *,
    precheck: Mapping[str, Any],
    positive_generic_input_requirements: Mapping[str, int],
    endpoint_counts: Mapping[str, Mapping[str, int]],
) -> Tuple[Optional[str], Dict[str, Any]]:
    analysis = precheck.get("_analysis")
    metadata = analysis.get("commodity_front_metadata") if isinstance(analysis, Mapping) else None
    updated_counts: Dict[str, Any] = {
        str(commodity): {str(key): int(value) for key, value in counts.items()}
        for commodity, counts in endpoint_counts.items()
    }
    incomplete: list[str] = []
    for commodity in sorted(positive_generic_input_requirements):
        commodity_metadata = metadata.get(commodity) if isinstance(metadata, Mapping) else None
        source_fronts = (
            commodity_metadata.get("source_front_cells")
            if isinstance(commodity_metadata, Mapping)
            else None
        )
        sink_fronts = (
            commodity_metadata.get("sink_front_cells")
            if isinstance(commodity_metadata, Mapping)
            else None
        )
        source_front_count = len(source_fronts) if isinstance(source_fronts, list) else 0
        sink_front_count = len(sink_fronts) if isinstance(sink_fronts, list) else 0
        counts = updated_counts.setdefault(commodity, {})
        counts["precheck_source_front_count"] = int(source_front_count)
        counts["precheck_sink_front_count"] = int(sink_front_count)
        if source_front_count <= 0 or sink_front_count <= 0:
            incomplete.append(commodity)
    if incomplete:
        updated_counts["_audit"] = {"incomplete_commodities": incomplete}
        return (
            "terminal_fixed_witness_required_generic_input_routing_fronts_incomplete",
            updated_counts,
        )
    return None, updated_counts


def _binding_has_alternatives(binding_model: PortBindingModel) -> bool:
    """Match the main LBBD controller's structural alternative test."""

    return bool(
        getattr(binding_model, "binding_vars", {})
        or getattr(binding_model, "generic_input_vars", {})
        or getattr(binding_model, "generic_output_vars", {})
    )


def _routing_precheck_blocked_ports_well_formed(value: Any) -> bool:
    """Mirror the main LBBD evidence shape check without importing its controller."""

    if not isinstance(value, list) or not value:
        return False
    for blocked_port in value:
        if not isinstance(blocked_port, Mapping):
            return False
        conflict_set = blocked_port.get("placement_level_conflict_set", [])
        blocking_ids = blocked_port.get("blocking_instance_ids", [])
        if not isinstance(conflict_set, list) or any(
            not isinstance(instance_id, str) for instance_id in conflict_set
        ):
            return False
        if not isinstance(blocking_ids, list) or any(
            not isinstance(instance_id, str) for instance_id in blocking_ids
        ):
            return False
        instance_id = blocked_port.get("instance_id")
        if instance_id is not None and not isinstance(instance_id, str):
            return False
        for cell_key in ("port_cell", "front_cell"):
            if cell_key not in blocked_port:
                continue
            cell = blocked_port.get(cell_key)
            if (
                not isinstance(cell, list)
                or len(cell) != 2
                or any(
                    isinstance(coordinate, bool) or not isinstance(coordinate, int)
                    for coordinate in cell
                )
            ):
                return False
        if (
            "dir" in blocked_port
            and str(blocked_port.get("dir")) not in {"N", "S", "E", "W"}
        ):
            return False
    return True


def _routing_precheck_contract_violation(
    precheck: Mapping[str, Any],
) -> Tuple[Optional[str], str, bool]:
    """Validate the proof-bearing safe-reject fields used by the main LBBD loop."""

    if "status" not in precheck:
        return "routing_precheck_missing_status", "MISSING_STATUS", False
    status = str(precheck["status"])
    if status not in {"feasible", "front_blocked", "relaxed_disconnected"}:
        return "routing_precheck_unexpected_status", status, False

    safe_reject = precheck.get("binding_selection_safe_reject")
    if not isinstance(safe_reject, bool):
        return "routing_precheck_safe_reject_not_bool", status, False
    analysis = precheck.get("_analysis")
    if not isinstance(analysis, Mapping):
        return "routing_precheck_missing_domain_analysis", status, False
    if str(analysis.get("status", "MISSING_STATUS")) != status:
        return "routing_precheck_analysis_status_mismatch", status, False
    analysis_safe_reject = analysis.get("binding_selection_safe_reject")
    if analysis_safe_reject is not safe_reject:
        return "routing_precheck_analysis_safe_reject_mismatch", status, False

    if status == "feasible":
        if safe_reject:
            return "routing_precheck_feasible_marked_safe_reject", status, False
        return None, status, False
    if not safe_reject:
        return "routing_precheck_reject_not_binding_selection_safe", status, False

    evidence_field = (
        "blocked_ports" if status == "front_blocked" else "disconnected_commodities"
    )
    summary_evidence = precheck.get(evidence_field)
    analysis_evidence = analysis.get(evidence_field)
    if (
        not isinstance(summary_evidence, list)
        or not summary_evidence
        or not isinstance(analysis_evidence, list)
        or summary_evidence != analysis_evidence
        or any(not isinstance(item, Mapping) for item in summary_evidence)
    ):
        return f"routing_precheck_{evidence_field}_mismatch", status, False
    if status == "front_blocked" and not _routing_precheck_blocked_ports_well_formed(
        summary_evidence
    ):
        return "routing_precheck_blocked_ports_malformed", status, False
    return None, status, True


def _budget_exhausted_verdict(
    base: Mapping[str, Any],
    *,
    budget: _FixedWitnessSolveBudget,
    stage: str,
    binding_status: Optional[str],
    routing_status: Optional[str],
    enumerated_bindings: int,
    routing_attempts: int,
) -> TerminalFixedWitnessVerdict:
    return _reject(
        base,
        "terminal_fixed_witness_solve_budget_exhausted",
        binding_status=binding_status,
        routing_status=routing_status,
        details={
            **budget.audit_details(exhausted_stage=stage),
            "enumerated_bindings": int(enumerated_bindings),
            "routing_attempts": int(routing_attempts),
        },
    )


def _solve_binding_with_budget(
    *,
    binding_model: PortBindingModel,
    budget: _FixedWitnessSolveBudget,
) -> Optional[str]:
    time_limit = budget.remaining("binding")
    if time_limit <= 0.0:
        return None
    started_at = _solver_budget_clock()
    try:
        with _fixed_solver_environment():
            return str(binding_model.solve(time_limit_seconds=time_limit))
    finally:
        budget.record("binding", started_at)


def _solve_routing_with_budget(
    *,
    routing_model: RoutingSubproblem,
    budget: _FixedWitnessSolveBudget,
) -> Optional[str]:
    time_limit = budget.remaining("routing")
    if time_limit <= 0.0:
        return None
    started_at = _solver_budget_clock()
    try:
        with _fixed_solver_environment():
            return str(routing_model.solve(time_limit=time_limit))
    finally:
        budget.record("routing", started_at)


def _resolve_after_binding_rejection(
    *,
    base: Mapping[str, Any],
    binding_model: PortBindingModel,
    selection: Mapping[str, Any],
    budget: _FixedWitnessSolveBudget,
    rejection_reason: str,
    rejection_routing_status: str,
    rejection_details: Mapping[str, Any],
    enumerated_bindings: int,
    routing_attempts: int,
) -> Tuple[Optional[str], Optional[TerminalFixedWitnessVerdict]]:
    if not _binding_has_alternatives(binding_model):
        return None, _reject(
            base,
            rejection_reason,
            binding_status="FEASIBLE",
            routing_status=rejection_routing_status,
            details={
                **dict(rejection_details),
                "enumerated_bindings": int(enumerated_bindings),
                "routing_attempts": int(routing_attempts),
            },
        )

    try:
        binding_model.add_nogood_cut(selection)
    except Exception as exc:  # noqa: BLE001
        return None, _reject(
            base,
            "terminal_fixed_witness_binding_nogood_exception",
            binding_status="FEASIBLE",
            routing_status=rejection_routing_status,
            details={
                "exception_type": type(exc).__name__,
                "rejected_binding_reason": rejection_reason,
                "enumerated_bindings": int(enumerated_bindings),
                "routing_attempts": int(routing_attempts),
            },
        )

    next_status = _solve_binding_with_budget(
        binding_model=binding_model,
        budget=budget,
    )
    if next_status is None:
        return None, _budget_exhausted_verdict(
            base,
            budget=budget,
            stage="binding",
            binding_status="FEASIBLE",
            routing_status=rejection_routing_status,
            enumerated_bindings=enumerated_bindings,
            routing_attempts=routing_attempts,
        )
    if next_status == "FEASIBLE":
        return next_status, None
    if next_status == "TIMEOUT":
        return None, _reject(
            base,
            "terminal_fixed_witness_binding_not_feasible",
            binding_status=next_status,
            routing_status=rejection_routing_status,
            details={
                "binding_status": next_status,
                "rejected_binding_reason": rejection_reason,
                "enumerated_bindings": int(enumerated_bindings),
                "routing_attempts": int(routing_attempts),
            },
        )
    if next_status == "INFEASIBLE":
        return None, _reject(
            base,
            "terminal_fixed_witness_binding_alternatives_exhausted",
            binding_status=next_status,
            routing_status=rejection_routing_status,
            details={
                "rejected_binding_reason": rejection_reason,
                "enumerated_bindings": int(enumerated_bindings),
                "routing_attempts": int(routing_attempts),
                "exhaustion_interpretation": "UNPROVEN_NOT_INFEASIBLE",
            },
        )
    return None, _reject(
        base,
        "terminal_fixed_witness_binding_status_unexpected",
        binding_status=next_status,
        routing_status=rejection_routing_status,
        details={
            "binding_status": next_status,
            "rejected_binding_reason": rejection_reason,
            "enumerated_bindings": int(enumerated_bindings),
            "routing_attempts": int(routing_attempts),
        },
    )


def _verify_binding_routing_alternatives(
    *,
    base: MutableMapping[str, Any],
    binding_model: PortBindingModel,
    budget: _FixedWitnessSolveBudget,
    occupied_owner_by_cell: Dict[Tuple[int, int], str],
    occupied_cells: set[Tuple[int, int]],
    grid_dimensions: Tuple[int, int],
    positive_generic_input_requirements: Mapping[str, int],
    selected_storage_box_instance_ids: Sequence[str],
    dominance_setup_details: Mapping[str, Any],
) -> TerminalFixedWitnessVerdict:
    placement_core = RoutingPlacementCore.from_occupied_cells(
        occupied_cells,
        occupied_owner_by_cell=occupied_owner_by_cell,
    )
    routing_occupancy_digest = _routing_occupancy_digest(occupied_owner_by_cell)
    base["routing_occupancy_digest"] = routing_occupancy_digest

    enumerated_bindings = 0
    routing_attempts = 0
    rejected_binding_reasons: list[str] = []
    seen_selection_digests: set[str] = set()

    while True:
        selection = binding_model.extract_selection()
        port_specs = binding_model.extract_port_specs()
        normalized_port_specs = _normalize_port_specs(port_specs)
        binding_assignment_digest = canonical_digest(selection)
        if binding_assignment_digest in seen_selection_digests:
            return _reject(
                base,
                "terminal_fixed_witness_binding_nogood_no_progress",
                binding_status="FEASIBLE",
                details={
                    "repeated_binding_assignment_digest": binding_assignment_digest,
                    "enumerated_bindings": int(enumerated_bindings),
                    "routing_attempts": int(routing_attempts),
                },
            )
        seen_selection_digests.add(binding_assignment_digest)
        enumerated_bindings += 1

        port_specs_digest = canonical_digest(normalized_port_specs)
        base.update(
            {
                "binding_status": "FEASIBLE",
                "binding_assignment_digest": binding_assignment_digest,
                "port_specs_digest": port_specs_digest,
            }
        )

        if positive_generic_input_requirements or selected_storage_box_instance_ids:
            selection_reason, selection_details, active_generic_input_slots = (
                _collect_active_generic_input_slots(
                    binding_model=binding_model,
                    selection=selection,
                    positive_generic_input_requirements=(
                        positive_generic_input_requirements
                    ),
                )
            )
        else:
            selection_reason, selection_details, active_generic_input_slots = (
                None,
                {},
                [],
            )
        if selection_reason is not None:
            return _reject(
                base,
                selection_reason,
                binding_status="FEASIBLE",
                details=selection_details,
            )

        dominance_reason, dominance_evidence_details = (
            _storage_box_dominance_violation(
                selected_storage_box_instance_ids=(
                    selected_storage_box_instance_ids
                ),
                active_generic_input_slots=active_generic_input_slots,
            )
        )
        if dominance_reason is not None:
            return _reject(
                base,
                dominance_reason,
                binding_status="FEASIBLE",
                details=dominance_evidence_details,
            )

        endpoint_reason, endpoint_counts = (
            _required_generic_input_endpoint_violation(
                active_generic_input_slots=active_generic_input_slots,
                normalized_port_specs=normalized_port_specs,
                positive_generic_input_requirements=(
                    positive_generic_input_requirements
                ),
            )
        )
        if endpoint_reason is not None:
            return _reject(
                base,
                endpoint_reason,
                binding_status="FEASIBLE",
                details={
                    "required_generic_input_endpoint_counts": endpoint_counts,
                },
            )

        f3_reason = _connector_body_exclusion_violation(
            port_specs=port_specs,
            occupied_owner_by_cell=occupied_owner_by_cell,
            grid_dimensions=grid_dimensions,
        )
        if f3_reason is not None:
            return _reject(
                base,
                f3_reason,
                binding_status="FEASIBLE",
                details={"port_specs_digest": port_specs_digest},
            )

        try:
            precheck = run_exact_routing_precheck(
                placement_core=placement_core,
                port_specs=port_specs,
                occupied_owner_by_cell=occupied_owner_by_cell,
            )
        except Exception as exc:  # noqa: BLE001
            return _reject(
                base,
                "terminal_fixed_witness_routing_precheck_exception",
                binding_status="FEASIBLE",
                details={"exception_type": type(exc).__name__},
            )
        if not isinstance(precheck, Mapping):
            return _reject(
                base,
                "terminal_fixed_witness_routing_precheck_unsafe",
                binding_status="FEASIBLE",
                details={"precheck_contract_violation": "precheck_not_mapping"},
            )
        precheck_violation, precheck_status, safe_reject = (
            _routing_precheck_contract_violation(precheck)
        )
        if precheck_violation is not None:
            return _reject(
                base,
                "terminal_fixed_witness_routing_precheck_unsafe",
                binding_status="FEASIBLE",
                routing_status=precheck_status,
                details={
                    "precheck_contract_violation": precheck_violation,
                    "routing_precheck_status": precheck_status,
                    "enumerated_bindings": int(enumerated_bindings),
                    "routing_attempts": int(routing_attempts),
                },
            )
        if safe_reject:
            rejection_reason = (
                "terminal_fixed_witness_routing_precheck_not_feasible"
            )
            rejection_routing_status = precheck_status
            rejected_binding_reasons.append(f"PRECHECK_{precheck_status.upper()}")
            next_status, rejection = _resolve_after_binding_rejection(
                base=base,
                binding_model=binding_model,
                selection=selection,
                budget=budget,
                rejection_reason=rejection_reason,
                rejection_routing_status=rejection_routing_status,
                rejection_details={
                    "routing_precheck_status": precheck_status,
                    "binding_selection_safe_reject": True,
                },
                enumerated_bindings=enumerated_bindings,
                routing_attempts=routing_attempts,
            )
            if rejection is not None:
                return rejection
            if next_status != "FEASIBLE":
                raise AssertionError("binding alternative resolver returned no verdict")
            continue

        front_reason, endpoint_counts = _required_generic_input_front_violation(
            precheck=precheck,
            positive_generic_input_requirements=(
                positive_generic_input_requirements
            ),
            endpoint_counts=endpoint_counts,
        )
        if front_reason is not None:
            return _reject(
                base,
                front_reason,
                binding_status="FEASIBLE",
                routing_status=precheck_status,
                details={
                    "required_generic_input_endpoint_counts": endpoint_counts,
                },
            )

        commodities = sorted({str(port["commodity"]) for port in port_specs})
        try:
            routing_model = RoutingSubproblem.from_placement_core(
                placement_core,
                port_specs,
                commodities,
                domain_analysis=precheck.get("_analysis"),
            )
            routing_model.build()
        except Exception as exc:  # noqa: BLE001
            return _reject(
                base,
                "terminal_fixed_witness_routing_build_exception",
                binding_status="FEASIBLE",
                details={"exception_type": type(exc).__name__},
            )

        routing_grid = getattr(routing_model, "grid", None)
        if routing_grid is None:
            return _reject(
                base,
                "terminal_fixed_witness_routing_grid_missing",
                binding_status="FEASIBLE",
            )
        if (
            canonical_digest(
                _normalize_port_specs(getattr(routing_grid, "port_specs", []))
            )
            != port_specs_digest
        ):
            return _reject(
                base,
                "terminal_fixed_witness_routing_port_specs_mismatch",
                binding_status="FEASIBLE",
                details={"expected_port_specs_digest": port_specs_digest},
            )
        routing_owner_digest = _routing_occupancy_digest(
            getattr(routing_grid, "occupied_owner_by_cell", {})
        )
        if routing_owner_digest != routing_occupancy_digest:
            return _reject(
                base,
                "terminal_fixed_witness_routing_occupancy_mismatch",
                binding_status="FEASIBLE",
                details={
                    "expected_routing_occupancy_digest": routing_occupancy_digest
                },
            )

        build_rejection = _routing_build_rejection(routing_model.build_stats)
        if build_rejection is not None:
            return _reject(
                base,
                build_rejection,
                binding_status="FEASIBLE",
                details={"routing_build_stats": dict(routing_model.build_stats)},
            )

        routing_status = _solve_routing_with_budget(
            routing_model=routing_model,
            budget=budget,
        )
        if routing_status is None:
            return _budget_exhausted_verdict(
                base,
                budget=budget,
                stage="routing",
                binding_status="FEASIBLE",
                routing_status=precheck_status,
                enumerated_bindings=enumerated_bindings,
                routing_attempts=routing_attempts,
            )
        routing_attempts += 1
        if routing_status == "FEASIBLE":
            return _accept(
                base,
                binding_status="FEASIBLE",
                routing_status=routing_status,
                details={
                    # This is the durable, digest-bound source for certified
                    # blueprint active_ports.  A pose describes every
                    # available slot; only the binding witness identifies the
                    # slots that are actually active.
                    "port_specs": normalized_port_specs,
                    "port_count": int(len(port_specs)),
                    "commodity_count": int(len(commodities)),
                    "required_generic_input_endpoint_counts": endpoint_counts,
                    "storage_box_dominance": {
                        **dict(dominance_setup_details),
                        **dominance_evidence_details,
                    },
                    "enumerated_bindings": int(enumerated_bindings),
                    "routing_attempts": int(routing_attempts),
                    "rejected_binding_reasons": list(rejected_binding_reasons),
                },
            )
        if routing_status == "TIMEOUT":
            return _reject(
                base,
                "terminal_fixed_witness_routing_not_feasible",
                binding_status="FEASIBLE",
                routing_status=routing_status,
                details={
                    "routing_status": routing_status,
                    "enumerated_bindings": int(enumerated_bindings),
                    "routing_attempts": int(routing_attempts),
                },
            )
        if routing_status != "INFEASIBLE":
            return _reject(
                base,
                "terminal_fixed_witness_routing_status_unexpected",
                binding_status="FEASIBLE",
                routing_status=routing_status,
                details={
                    "routing_status": routing_status,
                    "enumerated_bindings": int(enumerated_bindings),
                    "routing_attempts": int(routing_attempts),
                },
            )

        rejected_binding_reasons.append("ROUTING_INFEASIBLE")
        next_status, rejection = _resolve_after_binding_rejection(
            base=base,
            binding_model=binding_model,
            selection=selection,
            budget=budget,
            rejection_reason="terminal_fixed_witness_routing_not_feasible",
            rejection_routing_status=routing_status,
            rejection_details={"routing_status": routing_status},
            enumerated_bindings=enumerated_bindings,
            routing_attempts=routing_attempts,
        )
        if rejection is not None:
            return rejection
        if next_status != "FEASIBLE":
            raise AssertionError("binding alternative resolver returned no verdict")


def verify_terminal_fixed_witness(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Path | None = None,
    serialized_state_bytes: bytes | None = None,
    candidate_records_override: Mapping[str, dict[str, Any]] | None = None,
) -> TerminalFixedWitnessVerdict:
    """Re-solve routed binding and routing for the serialized terminal witness."""

    base = _base_verdict()
    try:
        authority_state = _load_authority_state(
            state=state,
            campaign_path=campaign_path,
            serialized_state_bytes=serialized_state_bytes,
        )
        project_root = Path(project_root).resolve()
        final_result = _require_mapping(authority_state.get("final_result"), "final_result")
        grid_w, grid_h = _load_grid_dimensions(project_root)
        identity, record, solution = _resolve_terminal_witness_identity(
            authority_state=authority_state,
            final_result=final_result,
            grid_dimensions=(grid_w, grid_h),
            candidate_records_override=candidate_records_override,
        )
        base.update(
            {
                "candidate_key": identity.candidate_key,
                "solution_digest": identity.solution_digest,
                "ghost_rect_digest": identity.ghost_rect_digest,
                "ghost_cells_digest": identity.ghost_cells_digest,
                "witness_input_digest": identity.witness_input_digest,
            }
        )

        facility_pools = _load_facility_pools(project_root)
        instances = _load_mandatory_instances(project_root)
        io_requirements = load_generic_io_requirements(project_root=project_root)
        positive_generic_input_requirements = _positive_generic_input_requirements(
            io_requirements
        )
        selected_storage_box_instance_ids = (
            _selected_optional_storage_box_instance_ids(
                solution=solution,
                mandatory_instances=instances,
            )
        )
        generic_input_slots_by_operation = None
        if io_requirements.get("required_generic_inputs", {}):
            generic_input_slots_by_operation = load_generic_input_slots_by_operation(
                project_root=project_root,
            )

        occupied_owner_by_cell, occupied_cells = _extract_pose_resolved_occupancy(
            solution=solution,
            facility_pools=facility_pools,
        )

        budget = _FixedWitnessSolveBudget()
        with _fixed_solver_environment():
            binding_model = PortBindingModel(
                placement_solution=solution,
                facility_pools=facility_pools,
                instances=instances,
                project_root=project_root,
                required_generic_outputs=io_requirements.get(
                    "required_generic_outputs",
                    {},
                ),
                required_generic_inputs=io_requirements.get(
                    "required_generic_inputs",
                    {},
                ),
                generic_input_slots_by_operation=generic_input_slots_by_operation,
            )
            binding_model.build()
            dominance_setup_reason, dominance_setup_details = (
                _apply_storage_box_dominance_constraints(
                    binding_model=binding_model,
                    selected_storage_box_instance_ids=(
                        selected_storage_box_instance_ids
                    ),
                    positive_generic_input_requirements=(
                        positive_generic_input_requirements
                    ),
                )
            )
            if dominance_setup_reason is not None:
                return _reject(
                    base,
                    dominance_setup_reason,
                    details=dominance_setup_details,
                )
        binding_status = _solve_binding_with_budget(
            binding_model=binding_model,
            budget=budget,
        )

        if binding_status is None:
            return _budget_exhausted_verdict(
                base,
                budget=budget,
                stage="binding",
                binding_status=None,
                routing_status=None,
                enumerated_bindings=0,
                routing_attempts=0,
            )
        if binding_status != "FEASIBLE":
            return _reject(
                base,
                "terminal_fixed_witness_binding_not_feasible",
                binding_status=binding_status,
                details={"binding_status": binding_status},
            )
        return _verify_binding_routing_alternatives(
            base=base,
            binding_model=binding_model,
            budget=budget,
            occupied_owner_by_cell=occupied_owner_by_cell,
            occupied_cells=occupied_cells,
            grid_dimensions=(grid_w, grid_h),
            positive_generic_input_requirements=(
                positive_generic_input_requirements
            ),
            selected_storage_box_instance_ids=(
                selected_storage_box_instance_ids
            ),
            dominance_setup_details=dominance_setup_details,
        )
    except Exception as exc:  # noqa: BLE001
        return _reject(
            base,
            "terminal_fixed_witness_exception",
            details={"exception_type": type(exc).__name__, "message": str(exc)},
        )
def _project_terminal_fixed_witness_records_from_capsule(
    *,
    candidate_records: MutableMapping[str, dict[str, Any]],
    final_result: Mapping[str, Any],
    verdict: TerminalFixedWitnessVerdict | None,
    forced_rejected_reason: str | None = None,
) -> TerminalFixedWitnessProjection:
    """Project terminal records after a parent-validated capsule response."""

    try:
        projected = _copy_candidate_records(candidate_records)
    except (TypeError, ValueError, UnicodeError) as exc:
        return TerminalFixedWitnessProjection(
            candidate_records={},
            candidate_key=None,
            publishable=False,
            projected_status=_PROJECTED_UNPROVEN,
            rejected_reason=(
                "terminal_fixed_witness_projection_records_invalid:"
                f"{type(exc).__name__}"
            ),
        )
    try:
        identity = _identity_from_current_records(projected, final_result)
        candidate_key = identity.candidate_key
    except Exception as exc:  # noqa: BLE001
        return TerminalFixedWitnessProjection(
            candidate_records=projected,
            candidate_key=None,
            publishable=False,
            projected_status=_PROJECTED_UNPROVEN,
            rejected_reason=f"terminal_fixed_witness_projection_identity_invalid:{type(exc).__name__}",
        )

    reason = forced_rejected_reason or _projection_rejected_reason(identity, verdict)
    publishable = reason is None
    projected_status = _PROJECTED_CERTIFIED if publishable else _PROJECTED_UNPROVEN
    record = projected.get(candidate_key)
    if isinstance(record, dict):
        _apply_terminal_fixed_witness_audit_fields(
            record,
            verdict=verdict,
            publishable=publishable,
            projected_status=projected_status,
            rejected_reason=reason,
        )
        if not publishable:
            record["status"] = _PROJECTED_UNPROVEN
            record.pop("solution", None)
            record.pop(CANDIDATE_PROOF_FIELD, None)

    return TerminalFixedWitnessProjection(
        candidate_records=projected,
        candidate_key=candidate_key,
        publishable=publishable,
        projected_status=projected_status,
        rejected_reason=reason,
    )
def canonical_state_bytes_for_fixed_witness(state: Mapping[str, Any]) -> bytes:
    return json.dumps(
        state,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _base_verdict() -> Dict[str, Any]:
    return {
        "schema_version": TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
        "authority": TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
        "fresh_run_token": secrets.token_hex(16),
        "candidate_key": None,
        "solution_digest": None,
        "ghost_rect_digest": None,
        "ghost_cells_digest": None,
        "witness_input_digest": None,
        "binding_assignment_digest": None,
        "port_specs_digest": None,
        "routing_occupancy_digest": None,
        "binding_status": None,
        "routing_status": None,
    }


def _accept(
    base: Mapping[str, Any],
    *,
    binding_status: str,
    routing_status: str,
    details: Mapping[str, Any],
) -> TerminalFixedWitnessVerdict:
    return _verdict_from_base(
        base,
        publishable=True,
        projected_status=_PROJECTED_CERTIFIED,
        reason=None,
        binding_status=binding_status,
        routing_status=routing_status,
        details=details,
    )


def _reject(
    base: Mapping[str, Any],
    reason: str,
    *,
    binding_status: Optional[str] = None,
    routing_status: Optional[str] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> TerminalFixedWitnessVerdict:
    return _verdict_from_base(
        base,
        publishable=False,
        projected_status=_PROJECTED_UNPROVEN,
        reason=reason,
        binding_status=binding_status,
        routing_status=routing_status,
        details=details or {},
    )


def _verdict_from_base(
    base: Mapping[str, Any],
    *,
    publishable: bool,
    projected_status: str,
    reason: Optional[str],
    binding_status: Optional[str],
    routing_status: Optional[str],
    details: Mapping[str, Any],
) -> TerminalFixedWitnessVerdict:
    return TerminalFixedWitnessVerdict(
        schema_version=int(base["schema_version"]),
        authority=str(base["authority"]),
        fresh_run_token=str(base["fresh_run_token"]),
        publishable=bool(publishable),
        projected_status=str(projected_status),
        candidate_key=_optional_string(base.get("candidate_key")),
        solution_digest=_optional_string(base.get("solution_digest")),
        ghost_rect_digest=_optional_string(base.get("ghost_rect_digest")),
        ghost_cells_digest=_optional_string(base.get("ghost_cells_digest")),
        witness_input_digest=_optional_string(base.get("witness_input_digest")),
        binding_assignment_digest=_optional_string(
            base.get("binding_assignment_digest")
        ),
        port_specs_digest=_optional_string(base.get("port_specs_digest")),
        routing_occupancy_digest=_optional_string(base.get("routing_occupancy_digest")),
        binding_status=(
            str(binding_status)
            if binding_status is not None
            else _optional_string(base.get("binding_status"))
        ),
        routing_status=(
            str(routing_status)
            if routing_status is not None
            else _optional_string(base.get("routing_status"))
        ),
        reason=reason,
        details=dict(details),
    )


def _optional_string(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _load_authority_state(
    *,
    state: Mapping[str, Any],
    campaign_path: Path | None,
    serialized_state_bytes: bytes | None,
) -> Mapping[str, Any]:
    if serialized_state_bytes is not None:
        raw = bytes(serialized_state_bytes)
    elif campaign_path is not None and Path(campaign_path).exists():
        raw = Path(campaign_path).read_bytes()
    else:
        raw = canonical_state_bytes_for_fixed_witness(state)
    parsed = loads_strict_json(raw.decode("utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError("terminal fixed witness authority state must be an object")
    return parsed


def _resolve_terminal_witness_identity(
    *,
    authority_state: Mapping[str, Any],
    final_result: Mapping[str, Any],
    grid_dimensions: Tuple[int, int],
    candidate_records_override: Mapping[str, dict[str, Any]] | None,
) -> Tuple[_WitnessIdentity, Mapping[str, Any], Mapping[str, Any]]:
    authority_records = _require_mapping(authority_state.get("candidates"), "candidates")
    identity = _identity_from_current_records(authority_records, final_result)
    authority_record = _require_mapping(
        authority_records.get(identity.candidate_key),
        f"candidates.{identity.candidate_key}",
    )
    record = authority_record
    if candidate_records_override is not None:
        override_record = _require_mapping(
            candidate_records_override.get(identity.candidate_key),
            f"candidate_records_override.{identity.candidate_key}",
        )
        authority_solution = _require_mapping(
            authority_record.get("solution"),
            "authority_record.solution",
        )
        override_solution = _require_mapping(
            override_record.get("solution"),
            "override_record.solution",
        )
        if canonical_digest(authority_solution) != canonical_digest(override_solution):
            raise ValueError("candidate_records_override terminal solution mismatch")
        record = override_record

    if str(record.get("status", "")) != "CERTIFIED":
        raise ValueError("terminal record must be CERTIFIED before FIX-1 projection")
    solution = _require_mapping(record.get("solution"), "record.solution")
    final_solution = _require_mapping(
        final_result.get("placement_solution"),
        "final_result.placement_solution",
    )
    if canonical_digest(_solution_without_ghost(solution)) != canonical_digest(final_solution):
        raise ValueError("terminal record solution does not match final_result")

    proof = _require_mapping(record.get(CANDIDATE_PROOF_FIELD), CANDIDATE_PROOF_FIELD)
    if str(proof.get("solution_digest", "")) != identity.solution_digest:
        raise ValueError("candidate_proof solution_digest mismatch")
    _validate_ghost_pick(
        solution=solution,
        ghost_rect=identity.ghost_rect,
        grid_dimensions=grid_dimensions,
    )
    return identity, record, solution


def _identity_from_current_records(
    candidate_records: Mapping[str, Any],
    final_result: Mapping[str, Any],
) -> _WitnessIdentity:
    ghost_rect = _strict_ghost_rect(final_result.get("ghost_rect"))
    key = _candidate_key(int(ghost_rect["w"]), int(ghost_rect["h"]))
    record = _require_mapping(candidate_records.get(key), f"candidates.{key}")
    record_ghost_rect = _strict_record_ghost_rect(record.get("ghost_rect"))
    if (
        int(record_ghost_rect["w"]) != int(ghost_rect["w"])
        or int(record_ghost_rect["h"]) != int(ghost_rect["h"])
        or int(record_ghost_rect["area"]) != int(ghost_rect["area"])
    ):
        raise ValueError("terminal record ghost_rect mismatch")
    solution = _require_mapping(record.get("solution"), "record.solution")
    solution_digest = canonical_digest(solution)
    ghost_rect_digest = canonical_digest(ghost_rect)
    ghost_cells_digest = canonical_digest(_ghost_cells(ghost_rect))
    witness_input_digest = canonical_digest(
        {
            "candidate_key": key,
            "solution_digest": solution_digest,
            "ghost_rect_digest": ghost_rect_digest,
            "ghost_cells_digest": ghost_cells_digest,
        }
    )
    return _WitnessIdentity(
        candidate_key=key,
        solution_digest=solution_digest,
        ghost_rect_digest=ghost_rect_digest,
        ghost_cells_digest=ghost_cells_digest,
        witness_input_digest=witness_input_digest,
        ghost_rect=ghost_rect,
    )


def _projection_rejected_reason(
    identity: _WitnessIdentity,
    verdict: TerminalFixedWitnessVerdict | None,
) -> Optional[str]:
    if verdict is None:
        return "terminal_fixed_witness_fresh_verdict_missing"
    if not isinstance(verdict, TerminalFixedWitnessVerdict):
        return "terminal_fixed_witness_fresh_verdict_invalid"
    if str(verdict.authority) != TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY:
        return "terminal_fixed_witness_authority_invalid"
    if int(verdict.schema_version) != TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION:
        return "terminal_fixed_witness_schema_invalid"
    if not str(verdict.fresh_run_token):
        return "terminal_fixed_witness_fresh_run_token_missing"
    expected = {
        "candidate_key": identity.candidate_key,
        "solution_digest": identity.solution_digest,
        "ghost_rect_digest": identity.ghost_rect_digest,
        "ghost_cells_digest": identity.ghost_cells_digest,
        "witness_input_digest": identity.witness_input_digest,
    }
    for field_name, expected_value in expected.items():
        if str(getattr(verdict, field_name, "")) != str(expected_value):
            return f"terminal_fixed_witness_{field_name}_mismatch"
    if not bool(verdict.publishable):
        return str(verdict.reason or "terminal_fixed_witness_not_publishable")
    if str(verdict.projected_status) != _PROJECTED_CERTIFIED:
        return "terminal_fixed_witness_projected_status_invalid"
    if str(verdict.binding_status) != "FEASIBLE":
        return "terminal_fixed_witness_binding_status_invalid"
    if str(verdict.routing_status) != "FEASIBLE":
        return "terminal_fixed_witness_routing_status_invalid"
    return None


def _apply_terminal_fixed_witness_audit_fields(
    record: MutableMapping[str, Any],
    *,
    verdict: TerminalFixedWitnessVerdict | None,
    publishable: bool,
    projected_status: str,
    rejected_reason: Optional[str],
) -> None:
    proof_summary = record.get("proof_summary")
    summary = dict(proof_summary) if isinstance(proof_summary, Mapping) else {}
    if isinstance(verdict, TerminalFixedWitnessVerdict):
        summary[TERMINAL_FIXED_WITNESS_AUDIT_FIELD] = (
            stable_terminal_fixed_witness_verdict(verdict)
        )
    summary[TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD] = bool(publishable)
    summary[TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD] = str(projected_status)
    if publishable:
        summary.pop(TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD, None)
    else:
        summary[TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD] = str(
            rejected_reason or "terminal_fixed_witness_rejected"
        )
    record["proof_summary"] = summary


def _copy_candidate_records(
    candidate_records: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    copied: Dict[str, Dict[str, Any]] = {}
    for key, record in candidate_records.items():
        if isinstance(record, Mapping):
            copied[str(key)] = _strict_json_copy(record)
    return copied


def _strict_json_copy(payload: Any) -> Any:
    return loads_strict_json(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _strict_ghost_rect(raw_ghost_rect: Any) -> Dict[str, int]:
    ghost_rect = _require_mapping(raw_ghost_rect, "final_result.ghost_rect")
    allowed = {"w", "h", "area", "anchor_x", "anchor_y"}
    unknown = sorted(set(str(key) for key in ghost_rect).difference(allowed))
    if unknown:
        raise ValueError(f"unknown ghost_rect field: {unknown[0]}")
    result = {
        "w": _strict_int(ghost_rect.get("w"), "ghost_rect.w"),
        "h": _strict_int(ghost_rect.get("h"), "ghost_rect.h"),
        "area": _strict_int(ghost_rect.get("area"), "ghost_rect.area"),
        "anchor_x": _strict_int(ghost_rect.get("anchor_x"), "ghost_rect.anchor_x"),
        "anchor_y": _strict_int(ghost_rect.get("anchor_y"), "ghost_rect.anchor_y"),
    }
    if result["w"] <= 0 or result["h"] <= 0 or result["area"] != result["w"] * result["h"]:
        raise ValueError("ghost_rect dimensions are invalid")
    return result


def _strict_record_ghost_rect(raw_ghost_rect: Any) -> Dict[str, int]:
    ghost_rect = _require_mapping(raw_ghost_rect, "record.ghost_rect")
    result = {
        "w": _strict_int(ghost_rect.get("w"), "record.ghost_rect.w"),
        "h": _strict_int(ghost_rect.get("h"), "record.ghost_rect.h"),
        "area": _strict_int(ghost_rect.get("area"), "record.ghost_rect.area"),
    }
    if result["w"] <= 0 or result["h"] <= 0 or result["area"] != result["w"] * result["h"]:
        raise ValueError("record ghost_rect dimensions are invalid")
    return result


def _validate_ghost_pick(
    *,
    solution: Mapping[str, Any],
    ghost_rect: Mapping[str, int],
    grid_dimensions: Tuple[int, int],
) -> None:
    ghost_pick = _require_mapping(solution.get("ghost_pick"), "solution.ghost_pick")
    if str(ghost_pick.get("facility_type", "")) != "ghost_rect":
        raise ValueError("ghost_pick facility_type invalid")
    pose_idx = _strict_int(ghost_pick.get("pose_idx"), "ghost_pick.pose_idx")
    expected_pose_idx = _expected_unfiltered_ghost_anchor_index(
        grid_w=int(grid_dimensions[0]),
        grid_h=int(grid_dimensions[1]),
        ghost_w=int(ghost_rect["w"]),
        ghost_h=int(ghost_rect["h"]),
        anchor_x=int(ghost_rect["anchor_x"]),
        anchor_y=int(ghost_rect["anchor_y"]),
    )
    if expected_pose_idx is None or int(pose_idx) != int(expected_pose_idx):
        raise ValueError("ghost_pick pose_idx mismatch")
    anchor = _require_mapping(ghost_pick.get("anchor"), "ghost_pick.anchor")
    if _strict_int(anchor.get("x"), "ghost_pick.anchor.x") != int(ghost_rect["anchor_x"]):
        raise ValueError("ghost_pick anchor x mismatch")
    if _strict_int(anchor.get("y"), "ghost_pick.anchor.y") != int(ghost_rect["anchor_y"]):
        raise ValueError("ghost_pick anchor y mismatch")


def _extract_pose_resolved_occupancy(
    *,
    solution: Mapping[str, Any],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Tuple[Dict[Tuple[int, int], str], set[Tuple[int, int]]]:
    owner_by_cell: Dict[Tuple[int, int], str] = {}
    occupied_cells: set[Tuple[int, int]] = set()
    for instance_id, raw_entry in solution.items():
        if str(instance_id) == "ghost_pick":
            continue
        entry = _require_mapping(raw_entry, f"solution.{instance_id}")
        facility_type = _strict_nonempty_string(
            entry.get("facility_type"),
            f"solution.{instance_id}.facility_type",
        )
        pose_idx = _strict_int(entry.get("pose_idx"), f"solution.{instance_id}.pose_idx")
        pool = facility_pools.get(facility_type)
        if not isinstance(pool, Sequence) or pose_idx < 0 or pose_idx >= len(pool):
            raise ValueError(f"solution.{instance_id}.pose_idx out of range")
        pose = _require_mapping(pool[pose_idx], f"facility_pools.{facility_type}[{pose_idx}]")
        for cell in _pose_occupied_cells(pose, field=f"facility_pools.{facility_type}[{pose_idx}]"):
            existing_owner = owner_by_cell.get(cell)
            if existing_owner is not None and existing_owner != str(instance_id):
                raise ValueError("duplicate occupied cell in terminal witness")
            owner_by_cell[cell] = str(instance_id)
            occupied_cells.add(cell)
    return owner_by_cell, occupied_cells


def _connector_body_exclusion_violation(
    *,
    port_specs: Sequence[Mapping[str, Any]],
    occupied_owner_by_cell: Mapping[Tuple[int, int], str],
    grid_dimensions: Tuple[int, int],
) -> Optional[str]:
    """Reject a terminal witness whose stored port cell is body-occupied.

    Identity semantics (front-offset incident fix 2026-07-18): the stored
    port coordinate IS the front/belt cell, so "cell occupied by any body"
    is exactly the corrected front-usability predicate — this backstop was
    behaviourally correct throughout the incident and is the reason the
    fake-feasible direction never crossed the publication boundary. The
    legacy reject-code string keeps the historical "connector" wording
    (pinned by tests/history); do not read it as port+delta semantics.

    Obligation note (I1 scope, incident survey): I1's independent
    reverification rebuilds binding WITHOUT routing context (front-clean
    by construction) and does NOT re-verify routing front_blocked nogoods
    — an I1 green light is not an independent endorsement of front
    semantics. This backstop and the batch-1 identity fix are the
    front-semantics guards.
    """
    grid_w, grid_h = int(grid_dimensions[0]), int(grid_dimensions[1])
    for port_spec in port_specs:
        connector_cell = (
            _strict_int(port_spec.get("x"), "port_spec.x"),
            _strict_int(port_spec.get("y"), "port_spec.y"),
        )
        x, y = connector_cell
        if x < 0 or y < 0 or x >= grid_w or y >= grid_h:
            continue
        owner = occupied_owner_by_cell.get(connector_cell)
        if owner is not None:
            return "terminal_fixed_witness_connector_cell_occupied_by_other_body"
    return None


def _routing_build_rejection(build_stats: Mapping[str, Any]) -> Optional[str]:
    if build_stats.get("duplicate_terminal_front_keys"):
        return "terminal_fixed_witness_duplicate_terminal_front_keys"
    if build_stats.get("domain_status_contract_violation"):
        return "terminal_fixed_witness_routing_domain_status_contract_violation"
    domain_analysis = build_stats.get("domain_analysis")
    if isinstance(domain_analysis, Mapping):
        status = str(domain_analysis.get("status", "MISSING_STATUS"))
        if status != "feasible":
            return "terminal_fixed_witness_routing_build_domain_not_feasible"
    port_adherence = build_stats.get("port_adherence")
    if isinstance(port_adherence, Mapping):
        raw_blocked = port_adherence.get("blocked_ports", 0)
        if (
            isinstance(raw_blocked, bool)
            or not isinstance(raw_blocked, int)
            or raw_blocked < 0
        ):
            return "terminal_fixed_witness_port_adherence_blocked_ports_malformed"
        if raw_blocked > 0:
            return "terminal_fixed_witness_port_adherence_blocked_ports"
    return None


def _normalize_port_specs(port_specs: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    for port in port_specs:
        normalized.append(
            {
                "instance_id": str(port.get("instance_id", "")),
                "x": _strict_int(port.get("x"), "port_spec.x"),
                "y": _strict_int(port.get("y"), "port_spec.y"),
                "dir": str(port.get("dir", "")),
                "type": str(port.get("type", "")),
                "commodity": str(port.get("commodity", "")),
            }
        )
    normalized.sort(
        key=lambda item: (
            item["instance_id"],
            item["commodity"],
            item["type"],
            item["x"],
            item["y"],
            item["dir"],
        )
    )
    return normalized


def extract_verified_terminal_active_port_specs(
    *,
    campaign_state: Mapping[str, Any],
    final_result: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    """Return the digest-bound terminal binding ports or fail closed.

    Callers must first establish the project-bound terminal seal/replay contract.
    Within that validated campaign state, this re-establishes terminal identity
    against ``final_result`` and validates every relevant audit/status, schema,
    and digest field before exposing the binding witness to an output projection.
    """

    state = _require_mapping(campaign_state, "campaign_state")
    result = _require_mapping(final_result, "final_result")
    stored_result = _require_mapping(state.get("final_result"), "campaign_state.final_result")
    if canonical_digest(stored_result) != canonical_digest(result):
        raise ValueError("terminal active port final_result mismatch")

    candidate_records = _require_mapping(state.get("candidates"), "campaign_state.candidates")
    identity = _identity_from_current_records(candidate_records, result)
    record = _require_mapping(
        candidate_records.get(identity.candidate_key),
        f"campaign_state.candidates.{identity.candidate_key}",
    )
    if str(record.get("status", "")) != _PROJECTED_CERTIFIED:
        raise ValueError("terminal active port candidate is not CERTIFIED")
    record_solution = _require_mapping(record.get("solution"), "terminal candidate solution")
    result_solution = _require_mapping(
        result.get("placement_solution"),
        "final_result.placement_solution",
    )
    if canonical_digest(_solution_without_ghost(record_solution)) != canonical_digest(result_solution):
        raise ValueError("terminal active port solution does not match final_result")

    proof_summary = _require_mapping(record.get("proof_summary"), "terminal candidate proof_summary")
    if proof_summary.get(TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD) is not True:
        raise ValueError("terminal fixed-witness audit is not publishable")
    if str(proof_summary.get(TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD, "")) != _PROJECTED_CERTIFIED:
        raise ValueError("terminal fixed-witness audit projected status is invalid")
    if TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD in proof_summary:
        raise ValueError("terminal fixed-witness audit contains a rejection reason")

    raw_verdict = _require_mapping(
        proof_summary.get(TERMINAL_FIXED_WITNESS_AUDIT_FIELD),
        TERMINAL_FIXED_WITNESS_AUDIT_FIELD,
    )
    verdict = stable_terminal_fixed_witness_verdict_payload(raw_verdict)
    if int(verdict.get("schema_version", -1)) != TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION:
        raise ValueError("terminal fixed-witness audit schema is invalid")
    if str(verdict.get("authority", "")) != TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY:
        raise ValueError("terminal fixed-witness audit authority is invalid")
    if verdict.get("publishable") is not True:
        raise ValueError("terminal fixed-witness verdict is not publishable")
    if str(verdict.get("projected_status", "")) != _PROJECTED_CERTIFIED:
        raise ValueError("terminal fixed-witness verdict projected status is invalid")
    if str(verdict.get("binding_status", "")) != "FEASIBLE":
        raise ValueError("terminal fixed-witness binding status is invalid")
    if str(verdict.get("routing_status", "")) != "FEASIBLE":
        raise ValueError("terminal fixed-witness routing status is invalid")
    if verdict.get("reason") is not None:
        raise ValueError("terminal fixed-witness publishable verdict has a reason")

    expected_identity = {
        "candidate_key": identity.candidate_key,
        "solution_digest": identity.solution_digest,
        "ghost_rect_digest": identity.ghost_rect_digest,
        "ghost_cells_digest": identity.ghost_cells_digest,
        "witness_input_digest": identity.witness_input_digest,
    }
    for field_name, expected_value in expected_identity.items():
        if verdict.get(field_name) != expected_value:
            raise ValueError(f"terminal fixed-witness {field_name} mismatch")

    known_instances = {
        str(instance_id)
        for instance_id in result_solution
        if str(instance_id) != "ghost_pick"
    }
    normalized_specs = _validated_terminal_fixed_witness_port_carrier(
        details=verdict.get("details"),
        port_specs_digest=verdict.get("port_specs_digest"),
        known_instance_ids=known_instances,
    )
    return _strict_json_copy(normalized_specs)


def _validated_terminal_fixed_witness_port_carrier(
    *,
    details: Any,
    port_specs_digest: Any,
    known_instance_ids: AbstractSet[str],
) -> list[Dict[str, Any]]:
    """Validate the durable active-port carrier shared by mint and export."""

    carrier_details = _require_mapping(details, "terminal fixed-witness details")
    raw_specs = carrier_details.get("port_specs")
    if isinstance(raw_specs, (str, bytes)) or not isinstance(raw_specs, Sequence):
        raise ValueError("terminal fixed-witness port_specs must be a sequence")
    normalized_specs = _strict_normalized_port_specs(raw_specs)
    for index, spec in enumerate(normalized_specs):
        if str(spec["instance_id"]) not in known_instance_ids:
            raise ValueError(
                f"terminal fixed-witness port_specs[{index}] references an unknown instance"
            )
    if _strict_int(
        carrier_details.get("port_count"),
        "terminal fixed-witness port_count",
    ) != len(normalized_specs):
        raise ValueError("terminal fixed-witness port_count mismatch")
    if not isinstance(port_specs_digest, str) or len(port_specs_digest) != 64:
        raise ValueError("terminal fixed-witness port_specs_digest is invalid")
    if canonical_digest(normalized_specs) != port_specs_digest:
        raise ValueError("terminal fixed-witness port_specs_digest mismatch")
    return _strict_json_copy(normalized_specs)


def _strict_normalized_port_specs(raw_specs: Sequence[Any]) -> list[Dict[str, Any]]:
    required_fields = {"instance_id", "x", "y", "dir", "type", "commodity"}
    normalized: list[Dict[str, Any]] = []
    for index, raw_spec in enumerate(raw_specs):
        spec = _require_mapping(raw_spec, f"port_specs[{index}]")
        if set(spec) != required_fields:
            raise ValueError(f"port_specs[{index}] fields are invalid")
        instance_id = _strict_nonempty_string(spec.get("instance_id"), f"port_specs[{index}].instance_id")
        direction = _strict_nonempty_string(spec.get("dir"), f"port_specs[{index}].dir")
        port_type = _strict_nonempty_string(spec.get("type"), f"port_specs[{index}].type")
        commodity = _strict_nonempty_string(spec.get("commodity"), f"port_specs[{index}].commodity")
        if direction not in {"N", "S", "E", "W"}:
            raise ValueError(f"port_specs[{index}].dir is invalid")
        if port_type not in {"in", "out"}:
            raise ValueError(f"port_specs[{index}].type is invalid")
        normalized.append(
            {
                "instance_id": instance_id,
                "x": _strict_int(spec.get("x"), f"port_specs[{index}].x"),
                "y": _strict_int(spec.get("y"), f"port_specs[{index}].y"),
                "dir": direction,
                "type": port_type,
                "commodity": commodity,
            }
        )
    normalized.sort(
        key=lambda item: (
            item["instance_id"],
            item["commodity"],
            item["type"],
            item["x"],
            item["y"],
            item["dir"],
        )
    )
    if len({canonical_digest(spec) for spec in normalized}) != len(normalized):
        raise ValueError("terminal fixed-witness port_specs contain duplicates")
    return normalized


def _routing_occupancy_digest(
    occupied_owner_by_cell: Mapping[Tuple[int, int], str],
) -> str:
    entries = [
        {"cell": [int(cell[0]), int(cell[1])], "owner": str(owner)}
        for cell, owner in sorted(occupied_owner_by_cell.items())
    ]
    return canonical_digest({"occupied_owner_by_cell": entries})


def _ghost_cells(ghost_rect: Mapping[str, int]) -> list[list[int]]:
    anchor_x = int(ghost_rect["anchor_x"])
    anchor_y = int(ghost_rect["anchor_y"])
    return [
        [x, y]
        for x in range(anchor_x, anchor_x + int(ghost_rect["w"]))
        for y in range(anchor_y, anchor_y + int(ghost_rect["h"]))
    ]


def _solution_without_ghost(solution: Mapping[str, Any]) -> Dict[str, Any]:
    return {str(key): value for key, value in solution.items() if str(key) != "ghost_pick"}


def _load_grid_dimensions(project_root: Path) -> Tuple[int, int]:
    rules = _load_json_object(project_root / LOCKED_EXACT_ARTIFACT_PATHS["canonical_rules"])
    globals_payload = _require_mapping(rules.get("globals"), "canonical_rules.globals")
    grid = _require_mapping(globals_payload.get("grid"), "canonical_rules.globals.grid")
    grid_w = _strict_int(grid.get("width"), "canonical_rules.globals.grid.width")
    grid_h = _strict_int(grid.get("height"), "canonical_rules.globals.grid.height")
    if grid_w <= 0 or grid_h <= 0:
        raise ValueError("grid dimensions must be positive")
    return int(grid_w), int(grid_h)


def _load_mandatory_instances(project_root: Path) -> list[Dict[str, Any]]:
    payload = loads_strict_json(
        (
            project_root / LOCKED_EXACT_ARTIFACT_PATHS["mandatory_exact_instances"]
        ).read_text(encoding="utf-8")
    )
    if not isinstance(payload, list):
        raise ValueError("mandatory_exact_instances must be a JSON array")
    instances: list[Dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError(f"mandatory_exact_instances[{index}] must be a JSON object")
        instances.append(_strict_json_copy(item))
    return instances


def _load_facility_pools(project_root: Path) -> Dict[str, list[Dict[str, Any]]]:
    payload = _load_json_object(
        project_root / LOCKED_EXACT_ARTIFACT_PATHS["candidate_placements"]
    )
    raw_pools = _require_mapping(payload.get("facility_pools"), "facility_pools")
    pools: Dict[str, list[Dict[str, Any]]] = {}
    for facility_type, raw_pool in raw_pools.items():
        if not isinstance(raw_pool, list):
            raise ValueError(f"facility pool {facility_type!r} must be a list")
        pool: list[Dict[str, Any]] = []
        for index, pose in enumerate(raw_pool):
            if not isinstance(pose, Mapping):
                raise ValueError(f"facility pool {facility_type!r}[{index}] must be an object")
            pool.append(_strict_json_copy(pose))
        pools[str(facility_type)] = pool
    return pools


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = loads_strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _pose_occupied_cells(pose: Mapping[str, Any], *, field: str) -> list[Tuple[int, int]]:
    raw_cells = pose.get("occupied_cells")
    if not isinstance(raw_cells, list):
        raise ValueError(f"{field}.occupied_cells must be a JSON array")
    cells: list[Tuple[int, int]] = []
    for index, raw_cell in enumerate(raw_cells):
        if (
            isinstance(raw_cell, (str, bytes))
            or not isinstance(raw_cell, Sequence)
            or len(raw_cell) != 2
        ):
            raise ValueError(f"{field}.occupied_cells[{index}] must be [x,y]")
        cells.append(
            (
                _strict_int(raw_cell[0], f"{field}.occupied_cells[{index}][0]"),
                _strict_int(raw_cell[1], f"{field}.occupied_cells[{index}][1]"),
            )
        )
    return cells


def _expected_unfiltered_ghost_anchor_index(
    *,
    grid_w: int,
    grid_h: int,
    ghost_w: int,
    ghost_h: int,
    anchor_x: int,
    anchor_y: int,
) -> Optional[int]:
    if ghost_w <= 0 or ghost_h <= 0 or ghost_w > grid_w or ghost_h > grid_h:
        return None
    if anchor_x < 0 or anchor_y < 0:
        return None
    y_count = grid_h - ghost_h + 1
    if anchor_x > grid_w - ghost_w or anchor_y > grid_h - ghost_h:
        return None
    return int(anchor_x) * int(y_count) + int(anchor_y)


def _candidate_key(ghost_w: int, ghost_h: int) -> str:
    return f"{int(ghost_w)}x{int(ghost_h)}"


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return value


def _strict_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _strict_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


@contextmanager
def _fixed_solver_environment():
    saved = {key: os.environ.get(key) for key in (*_FIXED_SOLVER_ENV, *_CLEARED_SOLVER_ENV)}
    try:
        for key, value in _FIXED_SOLVER_ENV.items():
            os.environ[key] = value
        for key in _CLEARED_SOLVER_ENV:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
