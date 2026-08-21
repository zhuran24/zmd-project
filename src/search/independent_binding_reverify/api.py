"""Stable parent API for whole-layout binding re-verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import secrets
from typing import Any, Dict, Optional

from .protocol import (
    CAPSULE_AUTHORITY,
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    STATUS_CONFIRMED_INFEASIBLE,
    STATUS_DIVERGED_FEASIBLE,
    STATUS_EXCEPTION,
    STATUS_TIMEOUT,
    STATUS_UNKNOWN,
    VERIFIER_AUTHORITY,
    VERIFIER_SCHEMA_VERSION,
    IndependentInfeasibilityReverificationVerdict,
    ProtocolError,
    canonical_digest,
    json_copy,
    strict_int,
    strict_nonempty_string,
    unknown_verdict,
)
from .transport import CapsuleTimeout, CapsuleTransportError, invoke_capsule


_DEFAULT_REVERIFY_SECONDS = 600.0
_REQUIRED_ARTIFACT_HASH_KEYS = (
    "canonical_rules",
    "preprocess_plan",
    "generic_io_requirements",
    "candidate_placements",
    "mandatory_exact_instances",
)
_RESPONSE_KEYS = frozenset(
    {
        "schema",
        "authority",
        "nonce",
        "project_root",
        "request_digest",
        "artifact_hashes",
        "certificate_check",
        "verdict",
    }
)


def reverify_whole_layout_infeasibility(
    *,
    solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    instances: Sequence[Mapping[str, Any]],
    project_root: Path,
    proof_stage: str,
    binding_exhausted: bool,
    routing_exhausted: bool,
    binding_kwargs: Optional[Mapping[str, Any]] = None,
    artifact_hashes: Optional[Mapping[str, Any]] = None,
    binding_semantics_contract: Optional[Mapping[str, Any]] = None,
    time_limit_seconds: float = _DEFAULT_REVERIFY_SECONDS,
) -> IndependentInfeasibilityReverificationVerdict:
    """Run the data-only verifier in a fresh isolated interpreter.

    The subprocess boundary returns the roughly 54 MiB candidate-pool parse and
    its transient memory to the operating system after every rare whole-layout
    cut admission attempt.  ``timeout_seconds`` is a real wall-clock limit.
    """

    stage = str(proof_stage)
    if not binding_exhausted:
        return unknown_verdict(
            stage=stage,
            reason="binding_exhaustion_required_for_whole_layout_reverify",
        )
    try:
        timeout = _positive_timeout(time_limit_seconds)
        normalized_hashes = _required_artifact_hashes(artifact_hashes)
        selected_poses = _selected_pose_snapshots(solution, facility_pools)
        if binding_semantics_contract is None or not isinstance(
            binding_semantics_contract,
            Mapping,
        ):
            raise ProtocolError("binding_semantics_contract is required")
        nonce = secrets.token_hex(32)
        request: Dict[str, Any] = {
            "schema": REQUEST_SCHEMA,
            "authority": CAPSULE_AUTHORITY,
            "nonce": nonce,
            "project_root": str(Path(project_root).resolve()),
            "proof_stage": stage,
            "binding_exhausted": bool(binding_exhausted),
            "routing_exhausted": bool(routing_exhausted),
            "artifact_hashes": normalized_hashes,
            "solution": json_copy(solution),
            "caller_instances": json_copy(list(instances)),
            "caller_selected_poses": selected_poses,
            "binding_inputs": json_copy(dict(binding_kwargs or {})),
            "semantics_contract": json_copy(binding_semantics_contract),
        }
        response = invoke_capsule(
            request,
            source_root=Path(__file__).resolve().parents[3],
            timeout_seconds=timeout,
        )
        return _validated_response_verdict(
            request=request,
            response=response,
        )
    except CapsuleTimeout as exc:
        return IndependentInfeasibilityReverificationVerdict(
            schema_version=VERIFIER_SCHEMA_VERSION,
            authority=VERIFIER_AUTHORITY,
            confirmed=False,
            status=STATUS_TIMEOUT,
            stage=stage,
            reason="independent_binding_capsule_timeout",
            independent_status="UNKNOWN",
            details={"message": str(exc)},
        )
    except (ProtocolError, CapsuleTransportError) as exc:
        return unknown_verdict(
            stage=stage,
            reason="independent_binding_capsule_invalid_or_unavailable",
            details={"exception_type": type(exc).__name__, "message": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001
        return IndependentInfeasibilityReverificationVerdict(
            schema_version=VERIFIER_SCHEMA_VERSION,
            authority=VERIFIER_AUTHORITY,
            confirmed=False,
            status=STATUS_EXCEPTION,
            stage=stage,
            reason="independent_binding_api_exception",
            details={"exception_type": type(exc).__name__, "message": str(exc)},
        )


def _selected_pose_snapshots(
    solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Dict[str, Any]:
    if not isinstance(solution, Mapping):
        raise ProtocolError("solution must be an object")
    if not isinstance(facility_pools, Mapping):
        raise ProtocolError("facility_pools must be an object")
    snapshots: Dict[str, Any] = {}
    for raw_instance_id in sorted(solution, key=str):
        instance_id = strict_nonempty_string(raw_instance_id, "solution.instance_id")
        if instance_id == "ghost_pick":
            continue
        entry = solution[raw_instance_id]
        if not isinstance(entry, Mapping):
            raise ProtocolError(f"solution.{instance_id} must be an object")
        facility_type = strict_nonempty_string(
            entry.get("facility_type"),
            f"solution.{instance_id}.facility_type",
        )
        pose_index = strict_int(
            entry.get("pose_idx"),
            f"solution.{instance_id}.pose_idx",
        )
        pool = facility_pools.get(facility_type)
        if isinstance(pool, (str, bytes, bytearray)) or not isinstance(pool, Sequence):
            raise ProtocolError(f"facility pool missing: {facility_type}")
        if pose_index < 0 or pose_index >= len(pool):
            raise ProtocolError(
                f"pose index out of range: {instance_id}:{facility_type}[{pose_index}]"
            )
        pose = pool[pose_index]
        if not isinstance(pose, Mapping):
            raise ProtocolError(
                f"selected pose is not an object: {instance_id}:{facility_type}[{pose_index}]"
            )
        snapshots[instance_id] = json_copy(pose)
    return snapshots


def _required_artifact_hashes(raw: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    if not isinstance(raw, Mapping):
        raise ProtocolError("artifact_hashes are required")
    result: Dict[str, str] = {}
    for key in _REQUIRED_ARTIFACT_HASH_KEYS:
        value = raw.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ProtocolError(f"artifact hash missing or malformed: {key}")
        result[key] = value
    return result


def _positive_timeout(value: Any) -> float:
    if isinstance(value, bool):
        raise ProtocolError("time_limit_seconds must be a positive finite number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("time_limit_seconds must be numeric") from exc
    if not (parsed > 0.0 and parsed < float("inf")):
        raise ProtocolError("time_limit_seconds must be a positive finite number")
    return parsed


def _validated_response_verdict(
    *,
    request: Mapping[str, Any],
    response: Mapping[str, Any],
) -> IndependentInfeasibilityReverificationVerdict:
    if set(response) != _RESPONSE_KEYS:
        raise ProtocolError(
            f"response keys mismatch: missing={sorted(_RESPONSE_KEYS - set(response))};"
            f"extra={sorted(set(response) - _RESPONSE_KEYS)}"
        )
    if response.get("schema") != RESPONSE_SCHEMA:
        raise ProtocolError(f"unexpected response schema: {response.get('schema')!r}")
    if response.get("authority") != CAPSULE_AUTHORITY:
        raise ProtocolError(f"unexpected capsule authority: {response.get('authority')!r}")
    if response.get("nonce") != request.get("nonce"):
        raise ProtocolError("capsule nonce mismatch")
    if response.get("project_root") != request.get("project_root"):
        raise ProtocolError("capsule project_root mismatch")
    if response.get("request_digest") != canonical_digest(request):
        raise ProtocolError("capsule request_digest mismatch")
    if response.get("artifact_hashes") != request.get("artifact_hashes"):
        raise ProtocolError("capsule artifact hash echo mismatch")
    verdict_raw = response.get("verdict")
    if not isinstance(verdict_raw, Mapping):
        raise ProtocolError("capsule verdict must be an object")
    verdict = IndependentInfeasibilityReverificationVerdict.from_dict(verdict_raw)
    if verdict.confirmed:
        certificate_check = response.get("certificate_check")
        if not isinstance(certificate_check, Mapping) or certificate_check.get("ok") is not True:
            raise ProtocolError("confirmed verdict lacks a passing independent certificate check")
    return verdict


__all__ = [
    "IndependentInfeasibilityReverificationVerdict",
    "STATUS_CONFIRMED_INFEASIBLE",
    "STATUS_DIVERGED_FEASIBLE",
    "STATUS_EXCEPTION",
    "STATUS_TIMEOUT",
    "STATUS_UNKNOWN",
    "VERIFIER_AUTHORITY",
    "VERIFIER_SCHEMA_VERSION",
    "reverify_whole_layout_infeasibility",
]
