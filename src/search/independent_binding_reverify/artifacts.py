"""Strict, byte-bound authority artifact loading for the isolated capsule."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict

from .protocol import ProtocolError


ARTIFACT_PATHS = {
    "canonical_rules": "rules/canonical_rules.json",
    "preprocess_plan": "rules/preprocess_plan.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
}


@dataclass(frozen=True)
class AuthorityArtifacts:
    canonical_rules: Mapping[str, Any]
    preprocess_plan: Mapping[str, Any]
    generic_io_requirements: Mapping[str, Any]
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]]
    mandatory_instances: Sequence[Mapping[str, Any]]
    hashes: Mapping[str, str]


class ArtifactError(ProtocolError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = str(code)
        self.detail = str(detail)


def load_authority_artifacts(
    project_root: Path,
    *,
    expected_hashes: Mapping[str, Any],
) -> AuthorityArtifacts:
    root = Path(project_root).resolve()
    payloads: Dict[str, Any] = {}
    hashes: Dict[str, str] = {}
    for key, relative_path in ARTIFACT_PATHS.items():
        payload, digest = _load_strict_json(root / relative_path, key)
        expected = expected_hashes.get(key)
        if not isinstance(expected, str) or expected != digest:
            raise ArtifactError(
                "AUTHORITY_ARTIFACT_HASH_DRIFT",
                f"{key}: expected={expected!r};actual={digest}",
            )
        payloads[key] = payload
        hashes[key] = digest

    rules = _require_mapping(payloads["canonical_rules"], "canonical_rules")
    plan = _require_mapping(payloads["preprocess_plan"], "preprocess_plan")
    io_payload = _require_mapping(
        payloads["generic_io_requirements"],
        "generic_io_requirements",
    )
    candidate_payload = _require_mapping(
        payloads["candidate_placements"],
        "candidate_placements",
    )
    pools = _require_mapping(
        candidate_payload.get("facility_pools"),
        "candidate_placements.facility_pools",
    )
    mandatory = payloads["mandatory_exact_instances"]
    if isinstance(mandatory, (str, bytes, bytearray)) or not isinstance(
        mandatory, Sequence
    ):
        raise ArtifactError(
            "MANDATORY_INSTANCES_NOT_ARRAY",
            type(mandatory).__name__,
        )

    normalized_pools: Dict[str, Sequence[Mapping[str, Any]]] = {}
    for raw_facility_type, raw_pool in pools.items():
        facility_type = str(raw_facility_type)
        if isinstance(raw_pool, (str, bytes, bytearray)) or not isinstance(
            raw_pool,
            Sequence,
        ):
            raise ArtifactError(
                "FACILITY_POOL_NOT_ARRAY",
                facility_type,
            )
        normalized_pools[facility_type] = raw_pool

    normalized_mandatory: list[Mapping[str, Any]] = []
    for index, raw_instance in enumerate(mandatory):
        normalized_mandatory.append(
            _require_mapping(raw_instance, f"mandatory_exact_instances[{index}]")
        )

    return AuthorityArtifacts(
        canonical_rules=rules,
        preprocess_plan=plan,
        generic_io_requirements=io_payload,
        facility_pools=normalized_pools,
        mandatory_instances=tuple(normalized_mandatory),
        hashes=hashes,
    )


def _load_strict_json(path: Path, label: str) -> tuple[Any, str]:
    if _path_has_symlink_component(path) or not path.is_file():
        raise ArtifactError(
            "AUTHORITY_ARTIFACT_NOT_REGULAR_FILE",
            f"{label}:{path}",
        )
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactError(
            "AUTHORITY_ARTIFACT_NOT_UTF8",
            f"{label}:{exc}",
        ) from exc

    def _pairs(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ArtifactError("DUPLICATE_JSON_KEY", f"{label}:{key}")
            result[key] = value
        return result

    def _constant(value: str) -> None:
        raise ArtifactError("NONFINITE_JSON_CONSTANT", f"{label}:{value}")

    def _decimal(value: str) -> Decimal:
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ArtifactError("INVALID_JSON_NUMBER", f"{label}:{value}") from exc
        try:
            finite_float = float(parsed)
        except OverflowError as exc:
            raise ArtifactError("NONFINITE_JSON_NUMBER", f"{label}:{value}") from exc
        if not parsed.is_finite() or not math.isfinite(finite_float):
            raise ArtifactError("NONFINITE_JSON_NUMBER", f"{label}:{value}")
        return parsed

    try:
        payload = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_decimal,
        )
    except ArtifactError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ArtifactError(
            "AUTHORITY_ARTIFACT_JSON_INVALID",
            f"{label}:{type(exc).__name__}:{exc}",
        ) from exc
    return payload, hashlib.sha256(raw).hexdigest()


def _path_has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor) if path.is_absolute() else Path()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactError(
            "EXPECTED_MAPPING",
            f"{field}:{type(value).__name__}",
        )
    return value
