#!/usr/bin/env python3
"""Closed schema cohorts for the surviving research-only AB16 implementation.

The declaration is metadata, not execution or claim authority.  A consumer
must present every cohort with its exact ordered member sequence; omission,
duplication, an unknown version, or moving a schema between cohorts fails
closed.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import re


SCHEMA_LITERAL_RE = re.compile(
    r"(?:noncert-cuts-[a-z0-9-]+-v[1-9][0-9]*|cut-ledger-v[1-9][0-9]*|deterministic-protobuf-v[1-9][0-9]*)\Z"
)
COHORT_NAME_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
SCHEMA_STEM_RE = re.compile(r"(?P<stem>.+)-v(?P<version>[1-9][0-9]*)\Z")


BOOTSTRAP_RETRY_SCHEMAS = (
    "noncert-cuts-ab16-bootstrap-gate-a-receipt-v1",
    "noncert-cuts-ab16-bootstrap-gate-b-approval-v1",
    "noncert-cuts-ab16-bootstrap-manager-capture-v1",
    "noncert-cuts-ab16-bootstrap-offline-candidate-v1",
    "noncert-cuts-ab16-campaign-bootstrap-result-v1",
    "noncert-cuts-ab16-scientific-preregistration-v2",
    "noncert-cuts-ab16-scientific-input-set-v1",
    "noncert-cuts-ab16-attempt-input-set-v1",
    "noncert-cuts-ab16-attempt-open-v1",
    "noncert-cuts-ab16-attempt-selection-binding-v1",
    "noncert-cuts-ab16-attempt-result-envelope-v1",
    "noncert-cuts-ab16-retry-campaign-replay-v1",
    "noncert-cuts-ab16-consumption-state-v2",
)

BASELINE_SCHEMAS = (
    "deterministic-protobuf-v1",
    "noncert-cuts-ab16-experiment-contract-v1",
    "noncert-cuts-ab16-baseline-rebuild-v1",
    "noncert-cuts-ab16-rebuilt-model-metadata-v2",
    "noncert-cuts-ab16-repository-snapshot-materialization-v1",
    "noncert-cuts-ab16-campaign-snapshot-provenance-v1",
    "noncert-cuts-ab16-fixed-assignment-replay-v2",
    "noncert-cuts-ab16-baseline-admission-v1",
)

ORGANIC_EXECUTION_SCHEMAS = (
    "noncert-cuts-ab16-organic-manifest-v1",
    "noncert-cuts-ab16-organic-pre-run-authority-v1",
    "noncert-cuts-ab16-organic-arm-selection-v1",
    "noncert-cuts-ab16-compile-attach-journal-v1",
    "cut-ledger-v1",
    "noncert-cuts-ab16-controller-terminal-v1",
    "noncert-cuts-ab16-organic-arm-result-v1",
)

RESOURCE_LIFECYCLE_SCHEMAS = (
    "noncert-cuts-ab16-launch-environment-v1",
    "noncert-cuts-ab16-manager-epoch-observation-v1",
    "noncert-cuts-ab16-inner-lifecycle-v1",
    "noncert-cuts-ab16-preterminal-resource-v1",
    "noncert-cuts-ab16-resource-verification-v1",
    "noncert-cuts-ab16-release-token-v1",
    "noncert-cuts-ab16-terminal-envelope-v1",
    "noncert-cuts-ab16-cleanup-v1",
    "noncert-cuts-ab16-detached-resource-terminal-v1",
    "noncert-cuts-ab16-abort-cleanup-v1",
)

REPLAY_TERMINAL_SCHEMAS = (
    "noncert-cuts-ab16-fixed-assignment-replay-v1",
    "noncert-cuts-ab16-concrete-inequality-corpus-v1",
    "noncert-cuts-ab16-applied-assignment-v1",
    "noncert-cuts-ab16-independent-organic-arm-replay-v1",
    "noncert-cuts-ab16-arm-credibility-gate-v1",
    "noncert-cuts-ab16-terminal-classification-v1",
)

SCHEMA_COHORTS = (
    ("bootstrap_retry", BOOTSTRAP_RETRY_SCHEMAS),
    ("baseline", BASELINE_SCHEMAS),
    ("organic_execution", ORGANIC_EXECUTION_SCHEMAS),
    ("resource_lifecycle", RESOURCE_LIFECYCLE_SCHEMAS),
    ("replay_terminal", REPLAY_TERMINAL_SCHEMAS),
)

ORDERED_ACTIVE_SCHEMAS = tuple(schema for _name, schemas in SCHEMA_COHORTS for schema in schemas)
ACTIVE_SCHEMA_SET = frozenset(ORDERED_ACTIVE_SCHEMAS)
SCHEMA_COHORT_NAMES = tuple(name for name, _schemas in SCHEMA_COHORTS)


class SchemaDeclarationError(ValueError):
    """The supplied schema declaration or cohort projection is not exact."""


def _schema_stem(schema: str) -> str:
    match = SCHEMA_STEM_RE.fullmatch(schema)
    if match is None:
        raise SchemaDeclarationError(f"invalid schema discriminator: {schema!r}")
    return match.group("stem")


def _cohort_by_schema() -> dict[str, str]:
    return {schema: name for name, schemas in SCHEMA_COHORTS for schema in schemas}


def validate_schema_declaration() -> dict[str, object]:
    """Validate the built-in declaration and return its exact summary."""

    if type(SCHEMA_COHORTS) is not tuple or not SCHEMA_COHORTS:
        raise SchemaDeclarationError("schema cohorts must be one non-empty tuple")
    names: list[str] = []
    ordered: list[str] = []
    for item in SCHEMA_COHORTS:
        if type(item) is not tuple or len(item) != 2:
            raise SchemaDeclarationError("each schema cohort must be a name/member pair")
        name, schemas = item
        if type(name) is not str or COHORT_NAME_RE.fullmatch(name) is None:
            raise SchemaDeclarationError("schema cohort name is invalid")
        if name in names:
            raise SchemaDeclarationError(f"duplicate schema cohort: {name}")
        if type(schemas) is not tuple or not schemas:
            raise SchemaDeclarationError(f"schema cohort {name} must be a non-empty tuple")
        names.append(name)
        local: set[str] = set()
        for schema in schemas:
            if type(schema) is not str or SCHEMA_LITERAL_RE.fullmatch(schema) is None:
                raise SchemaDeclarationError(f"invalid schema in cohort {name}: {schema!r}")
            if schema in local or schema in ordered:
                raise SchemaDeclarationError(f"duplicate schema discriminator: {schema}")
            local.add(schema)
            ordered.append(schema)
    if tuple(names) != SCHEMA_COHORT_NAMES:
        raise SchemaDeclarationError("schema cohort-name projection drifted")
    if tuple(ordered) != ORDERED_ACTIVE_SCHEMAS or frozenset(ordered) != ACTIVE_SCHEMA_SET:
        raise SchemaDeclarationError("active schema projection drifted")
    return {
        "cohort_count": len(names),
        "cohort_names": tuple(names),
        "schema_count": len(ordered),
        "status": "PASS",
    }


def schema_cohort_for(schema: str) -> str:
    """Return the sole accepted cohort for one exact active discriminator."""

    validate_schema_declaration()
    if type(schema) is not str or SCHEMA_LITERAL_RE.fullmatch(schema) is None:
        raise SchemaDeclarationError(f"invalid schema discriminator: {schema!r}")
    cohort = _cohort_by_schema().get(schema)
    if cohort is not None:
        return cohort
    known_stems = {_schema_stem(active) for active in ACTIVE_SCHEMA_SET}
    if _schema_stem(schema) in known_stems:
        raise SchemaDeclarationError(f"unknown schema version: {schema}")
    raise SchemaDeclarationError(f"unknown schema discriminator: {schema}")


def validate_schema_projection(value: object) -> dict[str, tuple[str, ...]]:
    """Require an exact ordered copy of every declared schema cohort."""

    validate_schema_declaration()
    if type(value) is not dict or set(value) != set(SCHEMA_COHORT_NAMES):
        raise SchemaDeclarationError("schema projection must have the exact cohort key set")
    expected_by_name = dict(SCHEMA_COHORTS)
    owner_by_schema = _cohort_by_schema()
    normalized: dict[str, tuple[str, ...]] = {}
    for name in SCHEMA_COHORT_NAMES:
        raw = value[name]
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
            raise SchemaDeclarationError(f"schema cohort {name} must be an ordered sequence")
        schemas = tuple(raw)
        if any(type(schema) is not str for schema in schemas):
            raise SchemaDeclarationError(f"schema cohort {name} contains a non-string discriminator")
        if len(set(schemas)) != len(schemas):
            raise SchemaDeclarationError(f"schema cohort {name} contains a duplicate discriminator")
        for schema in schemas:
            if SCHEMA_LITERAL_RE.fullmatch(schema) is None:
                raise SchemaDeclarationError(f"invalid schema discriminator: {schema!r}")
            owner = owner_by_schema.get(schema)
            if owner is None:
                known_stems = {_schema_stem(active) for active in ACTIVE_SCHEMA_SET}
                if _schema_stem(schema) in known_stems:
                    raise SchemaDeclarationError(f"unknown schema version: {schema}")
                raise SchemaDeclarationError(f"unknown schema discriminator: {schema}")
            if owner != name:
                raise SchemaDeclarationError(f"cross-cohort schema mixing: {schema} belongs to {owner}, not {name}")
        if schemas != expected_by_name[name]:
            raise SchemaDeclarationError(f"schema cohort {name} has an omission or order drift")
        normalized[name] = schemas
    return normalized


def self_check() -> dict[str, object]:
    """Replay the declaration through the same closed projection validator."""

    summary = validate_schema_declaration()
    validate_schema_projection({name: list(schemas) for name, schemas in SCHEMA_COHORTS})
    return summary


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=__doc__)


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    print(json.dumps(self_check(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
