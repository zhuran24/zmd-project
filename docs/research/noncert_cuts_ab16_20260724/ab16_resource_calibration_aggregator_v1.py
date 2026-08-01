#!/usr/bin/env python3
"""Independent, package-pinned aggregation for three AB16 calibration samples."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import NoReturn, cast


AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
AGGREGATE_SCHEMA = "noncert-cuts-ab16-resource-calibration-aggregate-v1"
SAMPLE_COUNT = 3
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
FALSE_AUTHORIZATIONS = {
    "formal_campaign_creation_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_run_authorized": False,
}


class CalibrationAggregatorError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise CalibrationAggregatorError(code, detail)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        _fail("CALIBRATION_AGGREGATE_IDENTITY_INVALID", label)
    record = cast(dict[str, object], value)
    if (
        type(record["path"]) is not str
        or not Path(cast(str, record["path"])).is_absolute()
        or type(record["sha256"]) is not str
        or SHA_RE.fullmatch(cast(str, record["sha256"])) is None
        or type(record["size_bytes"]) is not int
        or cast(int, record["size_bytes"]) < 0
    ):
        _fail("CALIBRATION_AGGREGATE_IDENTITY_INVALID", label)
    return dict(record)


def _require_canonical_content_identity(
    value: object,
    identity: Mapping[str, object],
    label: str,
) -> None:
    if type(value) is not dict:
        _fail(
            "CALIBRATION_AGGREGATE_CONTENT_IDENTITY_MISMATCH",
            f"{label} content is not a strict JSON object",
        )
    try:
        raw = _canonical(value)
    except (TypeError, ValueError) as exc:
        _fail(
            "CALIBRATION_AGGREGATE_CONTENT_IDENTITY_MISMATCH",
            f"{label} content is not canonical JSON: {exc}",
        )
    if (
        identity["sha256"] != hashlib.sha256(raw).hexdigest()
        or identity["size_bytes"] != len(raw)
    ):
        _fail(
            "CALIBRATION_AGGREGATE_CONTENT_IDENTITY_MISMATCH",
            f"{label} canonical content does not match its identity",
        )


def aggregate_validations_independently(
    *,
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
    accepted: Sequence[
        tuple[
            Mapping[str, object],
            Mapping[str, object],
            Mapping[str, object],
            Mapping[str, object],
        ]
    ],
    aggregator_identity: Mapping[str, object],
) -> dict[str, object]:
    """Reconstruct one protocol-compatible aggregate without protocol imports."""

    checked_declaration_identity = _identity(
        declaration_identity,
        "declaration identity",
    )
    _require_canonical_content_identity(
        declaration,
        checked_declaration_identity,
        "declaration",
    )
    if (
        declaration.get("authority_scope") != AUTHORITY_SCOPE
        or declaration.get("authorizations") != FALSE_AUTHORIZATIONS
        or declaration.get("schema_version")
        != "noncert-cuts-ab16-resource-calibration-declaration-v1"
        or declaration.get("status") != "DECLARED_NO_AUTHORITY"
        or len(accepted) != SAMPLE_COUNT
    ):
        _fail(
            "CALIBRATION_AGGREGATE_INPUT_INVALID",
            "declaration or accepted sample count drifted",
        )
    surface = declaration.get("execution_surface")
    if type(surface) is not dict:
        _fail(
            "CALIBRATION_AGGREGATE_INPUT_INVALID",
            "declaration execution surface is absent",
        )
    checked_aggregator = _identity(aggregator_identity, "aggregator identity")
    member_identities = surface.get("execution_member_identities")
    if (
        type(member_identities) is not dict
        or member_identities.get("calibration_aggregator")
        != checked_aggregator
    ):
        _fail(
            "CALIBRATION_AGGREGATOR_IDENTITY_DRIFT",
            "execution surface does not bind the executing aggregator",
        )
    source = Path(__file__).read_bytes()
    if (
        checked_aggregator["sha256"] != hashlib.sha256(source).hexdigest()
        or checked_aggregator["size_bytes"] != len(source)
    ):
        _fail(
            "CALIBRATION_AGGREGATOR_IDENTITY_DRIFT",
            "aggregator identity does not name the executing package role",
        )
    sample_ids: set[str] = set()
    sample_shas: set[str] = set()
    cgroups: set[str] = set()
    validator_shas: set[str] = set()
    rows: list[dict[str, object]] = []
    maxima = {
        "disk_growth_peak_bytes": 0,
        "disk_peak_bytes": 0,
        "memory_peak_bytes": 0,
        "swap_peak_bytes": 0,
    }
    for index, (sample, sample_identity, validation, validation_identity) in enumerate(
        accepted,
        start=1,
    ):
        checked_sample_identity = _identity(
            sample_identity,
            f"sample {index} identity",
        )
        checked_validation_identity = _identity(
            validation_identity,
            f"validation {index} identity",
        )
        _require_canonical_content_identity(
            sample,
            checked_sample_identity,
            f"sample {index}",
        )
        _require_canonical_content_identity(
            validation,
            checked_validation_identity,
            f"validation {index}",
        )
        validator_identity = _identity(
            validation.get("validator_identity"),
            f"validator {index} identity",
        )
        measurements = validation.get("sample_measurements")
        cgroup = sample.get("cgroup")
        sample_id = sample.get("sample_id")
        if (
            sample.get("authority_scope") != AUTHORITY_SCOPE
            or sample.get("authorizations") != FALSE_AUTHORIZATIONS
            or sample.get("schema_version")
            != "noncert-cuts-ab16-resource-calibration-sample-v1"
            or sample.get("status") != "MEASURED_SUCCESS"
            or sample.get("declaration_identity") != checked_declaration_identity
            or validation.get("authority_scope") != AUTHORITY_SCOPE
            or validation.get("authorizations") != FALSE_AUTHORIZATIONS
            or validation.get("schema_version")
            != "noncert-cuts-ab16-resource-calibration-validation-v1"
            or validation.get("conclusion") != "ACCEPTED_COMPARABLE_SAMPLE"
            or validation.get("declaration_identity")
            != checked_declaration_identity
            or validation.get("sample_identity") != checked_sample_identity
            or validation.get("stage") != declaration.get("stage")
            or validation.get("execution_surface_sha256")
            != surface.get("execution_surface_sha256")
            or type(measurements) is not dict
            or set(measurements)
            != {
                "disk_after_bytes",
                "disk_before_bytes",
                "disk_growth_peak_bytes",
                "disk_peak_bytes",
                "memory_peak_bytes",
                "swap_peak_bytes",
            }
            or any(type(value) is not int or value < 0 for value in measurements.values())
            or type(cgroup) is not dict
            or type(cgroup.get("path")) is not str
            or type(sample_id) is not str
            or not sample_id
        ):
            _fail(
                "CALIBRATION_AGGREGATE_INPUT_INVALID",
                f"sample/validation {index} join drifted",
            )
        sample_sha = cast(str, checked_sample_identity["sha256"])
        cgroup_path = cast(str, cgroup["path"])
        validator_sha = cast(str, validator_identity["sha256"])
        if (
            sample_id in sample_ids
            or sample_sha in sample_shas
            or cgroup_path in cgroups
        ):
            _fail(
                "CALIBRATION_AGGREGATE_INPUT_INVALID",
                "sample ID, bytes, or cgroup was reused",
            )
        sample_ids.add(sample_id)
        sample_shas.add(sample_sha)
        cgroups.add(cgroup_path)
        validator_shas.add(validator_sha)
        for field in maxima:
            maxima[field] = max(maxima[field], cast(int, measurements[field]))
        rows.append(
            {
                "sample_id": sample_id,
                "sample_identity": checked_sample_identity,
                "validation_identity": checked_validation_identity,
                "validator_identity": validator_identity,
            }
        )
    if (
        checked_aggregator["sha256"] in validator_shas
        or checked_aggregator == declaration.get("harness_identity")
        or checked_aggregator == declaration.get("observer_identity")
    ):
        _fail(
            "CALIBRATION_AGGREGATOR_NOT_INDEPENDENT",
            "aggregator collapsed into the sampler or validator",
        )
    aggregate: dict[str, object] = {
        "aggregator_identity": checked_aggregator,
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "cohort": rows,
        "declaration_identity": checked_declaration_identity,
        "execution_surface_sha256": surface["execution_surface_sha256"],
        "maxima": maxima,
        "sample_count": SAMPLE_COUNT,
        "schema_version": AGGREGATE_SCHEMA,
        "stage": declaration["stage"],
        "status": "AGGREGATED_NO_SELF_AUTHORITY",
    }
    aggregate["aggregate_sha256"] = hashlib.sha256(_canonical(aggregate)).hexdigest()
    return aggregate
