"""Fixed-witness terminal verifier for public certified_exact evidence.

This verifier rechecks the exact stored terminal witness ``(R*, pi*)``.  It is
additive evidence only: callers must not rewrite the durable candidate solution
or its candidate_proof digest with any witness found by another solve.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import secrets
from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence, Tuple

from src.io.strict_json import loads_strict_json
from src.models.binding_subproblem import (
    PortBindingModel,
    load_generic_io_requirements,
    load_wireless_sink_generic_input_slots,
)
from src.models.routing_subproblem import (
    RoutingPlacementCore,
    RoutingSubproblem,
    run_exact_routing_precheck,
)
from src.search.candidate_proof_replay import CANDIDATE_PROOF_FIELD, canonical_digest
from src.search.certified_artifact_contract import LOCKED_EXACT_ARTIFACT_PATHS


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

_PROJECTED_CERTIFIED = "CERTIFIED"
_PROJECTED_UNPROVEN = "UNPROVEN"
_BINDING_SECONDS = 600.0
_ROUTING_SECONDS = 600.0

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


def verify_terminal_fixed_witness(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Path | None = None,
    serialized_state_bytes: bytes | None = None,
    candidate_records_override: Mapping[str, dict[str, Any]] | None = None,
) -> TerminalFixedWitnessVerdict:
    """Re-solve binding and routing for the serialized terminal witness."""

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
        wireless_sink_slots = None
        if io_requirements.get("required_generic_inputs", {}):
            wireless_sink_slots = load_wireless_sink_generic_input_slots(
                project_root=project_root,
            )

        occupied_owner_by_cell, occupied_cells = _extract_pose_resolved_occupancy(
            solution=solution,
            facility_pools=facility_pools,
        )

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
                wireless_sink_generic_input_slots=wireless_sink_slots,
            )
            binding_model.build()
            binding_status = str(
                binding_model.solve(time_limit_seconds=_BINDING_SECONDS)
            )

        if binding_status != "FEASIBLE":
            return _reject(
                base,
                "terminal_fixed_witness_binding_not_feasible",
                binding_status=binding_status,
                details={"binding_status": binding_status},
            )

        selection = binding_model.extract_selection()
        port_specs = binding_model.extract_port_specs()
        binding_assignment_digest = canonical_digest(selection)
        port_specs_digest = canonical_digest(_normalize_port_specs(port_specs))
        base.update(
            {
                "binding_status": binding_status,
                "binding_assignment_digest": binding_assignment_digest,
                "port_specs_digest": port_specs_digest,
            }
        )

        f3_reason = _connector_body_exclusion_violation(
            port_specs=port_specs,
            occupied_owner_by_cell=occupied_owner_by_cell,
            grid_dimensions=(grid_w, grid_h),
        )
        if f3_reason is not None:
            return _reject(
                base,
                f3_reason,
                binding_status=binding_status,
                details={"port_specs_digest": port_specs_digest},
            )

        placement_core = RoutingPlacementCore.from_occupied_cells(
            occupied_cells,
            occupied_owner_by_cell=occupied_owner_by_cell,
        )
        routing_occupancy_digest = _routing_occupancy_digest(occupied_owner_by_cell)
        base["routing_occupancy_digest"] = routing_occupancy_digest
        commodities = sorted({str(port["commodity"]) for port in port_specs})

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
                binding_status=binding_status,
                details={"exception_type": type(exc).__name__},
            )
        precheck_status = str(precheck.get("status", "MISSING_STATUS"))
        if precheck_status != "feasible":
            return _reject(
                base,
                "terminal_fixed_witness_routing_precheck_not_feasible",
                binding_status=binding_status,
                routing_status=precheck_status,
                details={"routing_precheck_status": precheck_status},
            )

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
                binding_status=binding_status,
                details={"exception_type": type(exc).__name__},
            )

        routing_grid = getattr(routing_model, "grid", None)
        if routing_grid is None:
            return _reject(
                base,
                "terminal_fixed_witness_routing_grid_missing",
                binding_status=binding_status,
            )
        if canonical_digest(_normalize_port_specs(getattr(routing_grid, "port_specs", []))) != port_specs_digest:
            return _reject(
                base,
                "terminal_fixed_witness_routing_port_specs_mismatch",
                binding_status=binding_status,
                details={"expected_port_specs_digest": port_specs_digest},
            )
        routing_owner_digest = _routing_occupancy_digest(
            getattr(routing_grid, "occupied_owner_by_cell", {})
        )
        if routing_owner_digest != routing_occupancy_digest:
            return _reject(
                base,
                "terminal_fixed_witness_routing_occupancy_mismatch",
                binding_status=binding_status,
                details={"expected_routing_occupancy_digest": routing_occupancy_digest},
            )

        build_rejection = _routing_build_rejection(routing_model.build_stats)
        if build_rejection is not None:
            return _reject(
                base,
                build_rejection,
                binding_status=binding_status,
                details={"routing_build_stats": dict(routing_model.build_stats)},
            )

        with _fixed_solver_environment():
            routing_status = str(routing_model.solve(time_limit=_ROUTING_SECONDS))
        if routing_status != "FEASIBLE":
            return _reject(
                base,
                "terminal_fixed_witness_routing_not_feasible",
                binding_status=binding_status,
                routing_status=routing_status,
                details={"routing_status": routing_status},
            )

        return _accept(
            base,
            binding_status=binding_status,
            routing_status=routing_status,
            details={
                "port_count": int(len(port_specs)),
                "commodity_count": int(len(commodities)),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return _reject(
            base,
            "terminal_fixed_witness_exception",
            details={"exception_type": type(exc).__name__, "message": str(exc)},
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
        summary[TERMINAL_FIXED_WITNESS_AUDIT_FIELD] = verdict.to_dict()
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
