"""Data-only protocol for the independent binding re-verification capsule.

This module intentionally contains no production-model imports.  It defines the
stable request/response vocabulary, canonical data hashing, and the verdict
object consumed by the Benders admission funnel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from typing import Any, Dict, Optional


REQUEST_SCHEMA = "independent_binding_reverify_request_v1"
RESPONSE_SCHEMA = "independent_binding_reverify_response_v1"
SEMANTICS_CONTRACT_SCHEMA = "binding_semantics_contract_v1"
CERTIFICATE_SCHEMA = "independent_binding_certificate_v2"
CAPSULE_AUTHORITY = "independent_binding_reverify_capsule_v1"
VERIFIER_AUTHORITY = "independent_whole_layout_binding_reverifier_v3"
VERIFIER_SCHEMA_VERSION = 3

STATUS_CONFIRMED_INFEASIBLE = "CONFIRMED_INFEASIBLE"
STATUS_DIVERGED_FEASIBLE = "DIVERGED_FEASIBLE"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_EXCEPTION = "EXCEPTION"
STATUS_UNKNOWN = "UNKNOWN"


class ProtocolError(ValueError):
    """Malformed request, response, or canonical payload."""


@dataclass(frozen=True)
class IndependentInfeasibilityReverificationVerdict:
    schema_version: int
    authority: str
    confirmed: bool
    status: str
    stage: str
    reason: str
    independent_status: Optional[str] = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "authority": str(self.authority),
            "confirmed": bool(self.confirmed),
            "status": str(self.status),
            "stage": str(self.stage),
            "reason": str(self.reason),
            "independent_status": (
                None if self.independent_status is None else str(self.independent_status)
            ),
            "details": json_copy(self.details),
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, Any],
    ) -> "IndependentInfeasibilityReverificationVerdict":
        expected = {
            "schema_version",
            "authority",
            "confirmed",
            "status",
            "stage",
            "reason",
            "independent_status",
            "details",
        }
        if set(raw) != expected:
            raise ProtocolError(
                f"verdict keys mismatch: missing={sorted(expected - set(raw))};"
                f"extra={sorted(set(raw) - expected)}"
            )
        schema_version = strict_int(raw["schema_version"], "verdict.schema_version")
        if schema_version != VERIFIER_SCHEMA_VERSION:
            raise ProtocolError(
                f"verdict schema_version={schema_version} != {VERIFIER_SCHEMA_VERSION}"
            )
        authority = strict_nonempty_string(raw["authority"], "verdict.authority")
        if authority != VERIFIER_AUTHORITY:
            raise ProtocolError(f"unexpected verdict authority: {authority!r}")
        confirmed = raw["confirmed"]
        if not isinstance(confirmed, bool):
            raise ProtocolError("verdict.confirmed must be bool")
        details = raw["details"]
        if not isinstance(details, Mapping):
            raise ProtocolError("verdict.details must be an object")
        independent_status = raw["independent_status"]
        if independent_status is not None and not isinstance(independent_status, str):
            raise ProtocolError("verdict.independent_status must be string or null")
        return cls(
            schema_version=schema_version,
            authority=authority,
            confirmed=confirmed,
            status=strict_nonempty_string(raw["status"], "verdict.status"),
            stage=strict_nonempty_string(raw["stage"], "verdict.stage"),
            reason=strict_nonempty_string(raw["reason"], "verdict.reason"),
            independent_status=independent_status,
            details=json_copy(details),
        )


def unknown_verdict(
    *,
    stage: str,
    reason: str,
    independent_status: Optional[str] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> IndependentInfeasibilityReverificationVerdict:
    return IndependentInfeasibilityReverificationVerdict(
        schema_version=VERIFIER_SCHEMA_VERSION,
        authority=VERIFIER_AUTHORITY,
        confirmed=False,
        status=STATUS_UNKNOWN,
        stage=str(stage),
        reason=str(reason),
        independent_status=independent_status,
        details=json_copy(details or {}),
    )


def json_copy(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def canonical_digest(value: Any) -> str:
    raw = json.dumps(
        semantic_normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def semantic_normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return {"$number": [int(value), 1]}
    if isinstance(value, (Decimal, Fraction, float)):
        number = to_fraction(value, "canonical_number")
        return {"$number": [number.numerator, number.denominator]}
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise ProtocolError(f"non-string mapping key: {raw_key!r}")
            if raw_key in result:
                raise ProtocolError(f"duplicate mapping key: {raw_key!r}")
            result[raw_key] = semantic_normalize(raw_value)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [semantic_normalize(item) for item in value]
    raise ProtocolError(f"unsupported canonical value: {type(value).__name__}")


def to_fraction(value: Any, field: str) -> Fraction:
    if isinstance(value, bool):
        raise ProtocolError(f"{field} must not be boolean")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolError(f"{field} must be finite")
        return Fraction(str(value))
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ProtocolError(f"{field} is not an exact rational: {value!r}") from exc
    raise ProtocolError(f"{field} has unsupported numeric type {type(value).__name__}")


def strict_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(f"{field} must be an integer")
    return int(value)


def strict_nonnegative_int(value: Any, field: str) -> int:
    parsed = strict_int(value, field)
    if parsed < 0:
        raise ProtocolError(f"{field} must be non-negative")
    return parsed


def strict_positive_int(value: Any, field: str) -> int:
    parsed = strict_int(value, field)
    if parsed <= 0:
        raise ProtocolError(f"{field} must be positive")
    return parsed


def strict_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolError(f"{field} must be a non-empty string")
    return value
