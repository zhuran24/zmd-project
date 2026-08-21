"""Child-side isolated binding proof capsule."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import sys
from typing import Any, Dict

from .artifacts import ArtifactError, load_authority_artifacts
from .certificate import verify_binding_certificate
from .protocol import (
    CAPSULE_AUTHORITY,
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    STATUS_CONFIRMED_INFEASIBLE,
    STATUS_DIVERGED_FEASIBLE,
    STATUS_EXCEPTION,
    VERIFIER_AUTHORITY,
    VERIFIER_SCHEMA_VERSION,
    IndependentInfeasibilityReverificationVerdict,
    ProtocolError,
    canonical_digest,
    strict_nonempty_string,
    unknown_verdict,
)
from .semantics import SemanticError, build_semantic_model
from .theorem import (
    OUTCOME_FEASIBLE,
    OUTCOME_INFEASIBLE,
    build_binding_certificate,
)


_REQUEST_KEYS = frozenset(
    {
        "schema",
        "authority",
        "nonce",
        "project_root",
        "proof_stage",
        "binding_exhausted",
        "routing_exhausted",
        "artifact_hashes",
        "solution",
        "caller_instances",
        "caller_selected_poses",
        "binding_inputs",
        "semantics_contract",
    }
)


def execute_capsule_request(raw_request: Mapping[str, Any]) -> Dict[str, Any]:
    request = dict(raw_request)
    project_root_text = str(request.get("project_root", ""))
    request_digest = canonical_digest(request)
    try:
        _validate_request_envelope(request)
        proof_stage = strict_nonempty_string(
            request.get("proof_stage"),
            "request.proof_stage",
        )
        if request.get("binding_exhausted") is not True:
            verdict = unknown_verdict(
                stage=proof_stage,
                reason="binding_exhaustion_required_for_whole_layout_reverify",
            )
            return _response(
                request=request,
                request_digest=request_digest,
                verdict=verdict,
                artifact_hashes=request["artifact_hashes"],
                certificate_check=None,
            )

        artifacts = load_authority_artifacts(
            Path(project_root_text),
            expected_hashes=_mapping(request.get("artifact_hashes"), "artifact_hashes"),
        )
        model = build_semantic_model(artifacts, request)
        certificate = build_binding_certificate(model)
        certificate_check = verify_binding_certificate(model, certificate)
        if not certificate_check.ok:
            verdict = unknown_verdict(
                stage=proof_stage,
                reason="independent_binding_certificate_self_check_failed",
                details={
                    "certificate": certificate,
                    "certificate_check": certificate_check.to_dict(),
                },
            )
        elif certificate_check.outcome == OUTCOME_INFEASIBLE:
            verdict = IndependentInfeasibilityReverificationVerdict(
                schema_version=VERIFIER_SCHEMA_VERSION,
                authority=VERIFIER_AUTHORITY,
                confirmed=True,
                status=STATUS_CONFIRMED_INFEASIBLE,
                stage="binding" if request.get("routing_exhausted") is not True else proof_stage,
                reason=(
                    "independent_binding_arithmetic_certificate_confirmed_infeasible"
                    if request.get("routing_exhausted") is not True
                    else "routing_exhaustion_reverified_by_binding_infeasible"
                ),
                independent_status=OUTCOME_INFEASIBLE,
                details={
                    "algorithm": "independent_closed_form_binding_feasibility_v2",
                    "certificate": certificate,
                    "certificate_check": certificate_check.to_dict(),
                    "routing_phase1_policy": (
                        "confirmed_only_when_binding_is_independently_infeasible"
                        if request.get("routing_exhausted") is True
                        else "not_applicable"
                    ),
                },
            )
        elif certificate_check.outcome == OUTCOME_FEASIBLE:
            positive_verdict = IndependentInfeasibilityReverificationVerdict(
                schema_version=VERIFIER_SCHEMA_VERSION,
                authority=VERIFIER_AUTHORITY,
                confirmed=False,
                status=STATUS_DIVERGED_FEASIBLE,
                stage="binding",
                reason="independent_binding_explicit_witness_constructed",
                independent_status=OUTCOME_FEASIBLE,
                details={
                    "algorithm": "independent_closed_form_binding_feasibility_v2",
                    "certificate": certificate,
                    "certificate_check": certificate_check.to_dict(),
                },
            )
            if request.get("routing_exhausted") is True:
                verdict = unknown_verdict(
                    stage=proof_stage,
                    reason="routing_exhaustion_phase1_conservative_unknown",
                    independent_status=OUTCOME_FEASIBLE,
                    details={
                        "binding_reverification": positive_verdict.to_dict(),
                        "routing_phase1_policy": (
                            "no routing ALL-INFEASIBLE cut without an independent full "
                            "routing exhaustion proof"
                        ),
                    },
                )
            else:
                verdict = positive_verdict
        else:
            verdict = unknown_verdict(
                stage=proof_stage,
                reason="independent_binding_certificate_outcome_unsupported",
                details={"certificate_check": certificate_check.to_dict()},
            )
        return _response(
            request=request,
            request_digest=request_digest,
            verdict=verdict,
            artifact_hashes=artifacts.hashes,
            certificate_check=certificate_check.to_dict(),
        )
    except (ArtifactError, SemanticError, ProtocolError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        detail = getattr(exc, "detail", str(exc))
        verdict = unknown_verdict(
            stage=str(request.get("proof_stage", "binding")),
            reason="independent_binding_input_invalid",
            details={"input_error_code": str(code), "input_error_detail": str(detail)},
        )
        return _response(
            request=request,
            request_digest=request_digest,
            verdict=verdict,
            artifact_hashes=request.get("artifact_hashes", {}),
            certificate_check=None,
        )
    except Exception as exc:  # noqa: BLE001
        verdict = IndependentInfeasibilityReverificationVerdict(
            schema_version=VERIFIER_SCHEMA_VERSION,
            authority=VERIFIER_AUTHORITY,
            confirmed=False,
            status=STATUS_EXCEPTION,
            stage=str(request.get("proof_stage", "binding")),
            reason="independent_binding_capsule_exception",
            details={"exception_type": type(exc).__name__, "message": str(exc)},
        )
        return _response(
            request=request,
            request_digest=request_digest,
            verdict=verdict,
            artifact_hashes=request.get("artifact_hashes", {}),
            certificate_check=None,
        )


def isolated_capsule_main() -> int:
    try:
        request = _loads_strict_json(sys.stdin.read())
        if not isinstance(request, Mapping):
            raise ProtocolError("capsule request must be a JSON object")
        response = execute_capsule_request(request)
        sys.stdout.write(
            json.dumps(
                response,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 2


def _validate_request_envelope(request: Mapping[str, Any]) -> None:
    if set(request) != _REQUEST_KEYS:
        raise ProtocolError(
            f"request keys mismatch: missing={sorted(_REQUEST_KEYS - set(request))};"
            f"extra={sorted(set(request) - _REQUEST_KEYS)}"
        )
    if request.get("schema") != REQUEST_SCHEMA:
        raise ProtocolError(f"unexpected request schema: {request.get('schema')!r}")
    if request.get("authority") != CAPSULE_AUTHORITY:
        raise ProtocolError(f"unexpected request authority: {request.get('authority')!r}")
    strict_nonempty_string(request.get("nonce"), "request.nonce")
    strict_nonempty_string(request.get("project_root"), "request.project_root")
    if not isinstance(request.get("binding_exhausted"), bool):
        raise ProtocolError("request.binding_exhausted must be bool")
    if not isinstance(request.get("routing_exhausted"), bool):
        raise ProtocolError("request.routing_exhausted must be bool")
    for field in (
        "artifact_hashes",
        "solution",
        "caller_selected_poses",
        "binding_inputs",
        "semantics_contract",
    ):
        _mapping(request.get(field), field)
    caller_instances = request.get("caller_instances")
    if isinstance(caller_instances, (str, bytes, bytearray)) or not isinstance(
        caller_instances,
        list,
    ):
        raise ProtocolError("request.caller_instances must be an array")


def _response(
    *,
    request: Mapping[str, Any],
    request_digest: str,
    verdict: IndependentInfeasibilityReverificationVerdict,
    artifact_hashes: Any,
    certificate_check: Any,
) -> Dict[str, Any]:
    return {
        "schema": RESPONSE_SCHEMA,
        "authority": CAPSULE_AUTHORITY,
        "nonce": str(request.get("nonce", "")),
        "project_root": str(request.get("project_root", "")),
        "request_digest": request_digest,
        "artifact_hashes": dict(artifact_hashes) if isinstance(artifact_hashes, Mapping) else {},
        "certificate_check": certificate_check,
        "verdict": verdict.to_dict(),
    }


def _loads_strict_json(text: str) -> Any:
    def _pairs(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def _constant(value: str) -> None:
        raise ProtocolError(f"non-finite JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=_pairs,
        parse_constant=_constant,
    )


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProtocolError(f"{field} must be an object")
    return value


if __name__ == "__main__":
    raise SystemExit(isolated_capsule_main())
