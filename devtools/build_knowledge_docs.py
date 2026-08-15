#!/usr/bin/env python3
"""Build and validate the repository's thin documentation knowledge spine.

The dated research tree remains evidence.  Structured ledgers under
``data/knowledge`` provide stable identities for current claims, owner decisions,
and top-level evidence dossiers.  This tool validates those ledgers and renders
human-facing projections without copying volatile machine state by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import jsonschema  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]

CURRENT_STATE_RELPATH = "data/knowledge/current_state.json"
CLAIMS_RELPATH = "data/knowledge/claims.jsonl"
DECISIONS_RELPATH = "data/knowledge/decisions.jsonl"
DOSSIERS_RELPATH = "data/knowledge/dossiers.json"
BACKFILL_REVIEWS_RELPATH = "data/knowledge/backfill_reviews.jsonl"
BACKFILL_TRIAGE_RELPATH = "data/knowledge/backfill_triage.json"
TERMINOLOGY_RELPATH = "data/knowledge/terminology.json"
TOPICS_RELPATH = "data/knowledge/topics.json"
KNOWLEDGE_CENSUS_RELPATH = "data/knowledge/knowledge_census.json"
GENERATOR_RELPATH = "devtools/build_knowledge_docs.py"
START_HERE_RELPATH = "docs/START_HERE.md"

SCHEMA_RELPATHS = {
    "current_state": "data/knowledge/schemas/current_state.schema.json",
    "claim": "data/knowledge/schemas/claim.schema.json",
    "decision": "data/knowledge/schemas/decision.schema.json",
    "dossiers": "data/knowledge/schemas/dossiers.schema.json",
    "backfill_review": "data/knowledge/schemas/backfill_review.schema.json",
    "backfill_triage": "data/knowledge/schemas/backfill_triage.schema.json",
    "terminology": "data/knowledge/schemas/terminology.schema.json",
    "topics": "data/knowledge/schemas/topics.schema.json",
    "knowledge_census": "data/knowledge/schemas/knowledge_census.schema.json",
}

ACTIVE_CLAIM_STATUSES = frozenset({"current", "open"})
GENERATOR_VERSION = "10"

AUTHORITY_BASIS_BY_AUTHORITY = {
    "descriptive": "descriptive",
    "machine": "machine_verified",
    "owner_decision": "owner_decision",
    "research_authority": "research_authority",
    "research_only": "research_only",
    "rules_authority": "rules_source",
}

REPRESENTATION_CLASS_MAPPING = {
    "AUTHORITATIVE_CURRENT": (
        "governance_control",
        "locked_authority",
        "normative",
        "structured_knowledge",
    ),
    "GENERATED_PROJECTION": ("generated_projection",),
    "IMMUTABLE_HISTORICAL_SNAPSHOT": (
        "historical_evidence",
        "vendored_snapshot",
    ),
    "QUOTATION_FOR_EVIDENCE": ("historical_evidence",),
}

TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "p1_2-proof-chain",
        (
            "p1_2",
            "phase1_2",
            "close_kernel",
            "proof_obligation",
            "certified_surface",
            "terminal_evidence",
        ),
    ),
    (
        "cut-framework",
        ("cut", "benders", "rab_sep", "sac_hull", "noncert", "pattern_nogood"),
    ),
    (
        "upper-bound",
        ("upper_bound", "membrane", "band22", "area_bound", "r3_upper", "r4_"),
    ),
    (
        "witness-lower-bound",
        ("witness", "w0_", "domino", "layout_invariant"),
    ),
    (
        "rules-semantics",
        ("rule", "canonical", "front_offset", "cleanroom_rederivation", "axiom"),
    ),
    (
        "formal-verification",
        ("formal", "proof_logging", "veripb", "roundingsat", "smt", "pb_"),
    ),
    (
        "solver-experiment",
        ("phase0", "poc", "profile", "spike", "paradigm", "column_generation", "sizing"),
    ),
    (
        "documentation-governance",
        ("doc_tree", "history_toolchain", "project_bottleneck", "cleanup", "frontdoor"),
    ),
    (
        "industrial-delivery",
        ("industrial", "delivery", "viewer", "release"),
    ),
    (
        "p2-throughput",
        ("p2_0", "throughput", "flowbound", "mixflow"),
    ),
)


class KnowledgeError(RuntimeError):
    """Raised when the structured knowledge layer is malformed or stale."""


@dataclass(frozen=True)
class KnowledgeModel:
    root: Path
    current_state: Mapping[str, Any]
    claims: tuple[Mapping[str, Any], ...]
    decisions: tuple[Mapping[str, Any], ...]
    dossiers: Mapping[str, Any]
    backfill_reviews: tuple[Mapping[str, Any], ...]
    backfill_triage: Mapping[str, Any]
    terminology: Mapping[str, Any]
    topics: Mapping[str, Any]
    knowledge_census: Mapping[str, Any]
    machine_sources: Mapping[str, Any]
    tracked_paths: frozenset[str]

    @property
    def claim_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {str(record["id"]): record for record in self.claims}

    @property
    def decision_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {str(record["id"]): record for record in self.decisions}

    @property
    def dossier_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {str(record["id"]): record for record in self.dossiers["records"]}

    @property
    def backfill_review_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {str(record["id"]): record for record in self.backfill_reviews}

    @property
    def term_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {str(record["id"]): record for record in self.terminology["records"]}

    @property
    def topic_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {str(record["id"]): record for record in self.topics["records"]}

    @property
    def current_review_by_dossier(self) -> dict[str, Mapping[str, Any]]:
        return {
            str(record["dossier_id"]): record
            for record in self.backfill_reviews
            if record["status"] == "current"
        }

    @property
    def triage_by_dossier(self) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for group in self.backfill_triage["groups"]:
            for dossier_id in group["dossier_ids"]:
                result[str(dossier_id)] = group
        return result


@dataclass(frozen=True)
class RenderedKnowledgeDocs:
    current: str
    catalog: str
    reasoning_ledger: str
    validity_ledger: str
    backfill_ledger: str
    topic_index: str
    terminology: str
    open_questions: str
    source_digest: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise KnowledgeError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise KnowledgeError(f"non-finite JSON constant: {value}")


def _parse_json(text: str, label: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise KnowledgeError(f"invalid JSON in {label}: {exc}") from exc


def _read_json(root: Path, relpath: str) -> Any:
    path = root / relpath
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, OSError) as exc:
        raise KnowledgeError(f"cannot read knowledge source {relpath}: {exc}") from exc
    return _parse_json(text, relpath)


def _read_jsonl(root: Path, relpath: str) -> tuple[Mapping[str, Any], ...]:
    path = root / relpath
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, UnicodeDecodeError, OSError) as exc:
        raise KnowledgeError(f"cannot read knowledge source {relpath}: {exc}") from exc

    records: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        value = _parse_json(line, f"{relpath}:{line_number}")
        if not isinstance(value, dict):
            raise KnowledgeError(f"{relpath}:{line_number} must contain one JSON object")
        records.append(value)
    return tuple(records)


def _compile_schema_validator(
    root: Path,
    schema_relpath: str,
) -> jsonschema.Draft202012Validator:
    """Compile one durable validator for a schema file.

    A model validates many JSONL records against the same schema. Re-reading and
    re-checking that schema for every record multiplies filesystem work and can
    make a focused knowledge-test process stall on shared or throttled workspaces.
    Callers that validate a batch should compile once and reuse the immutable
    validator for the duration of that batch.
    """

    schema = _read_json(root, schema_relpath)
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        return jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        )
    except jsonschema.SchemaError as exc:
        raise KnowledgeError(f"invalid schema {schema_relpath}: {exc.message}") from exc


def _validate_with_validator(
    validator: jsonschema.Draft202012Validator,
    value: Any,
    label: str,
) -> None:
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise KnowledgeError(f"{label} schema validation failed at {location}: {error.message}")


def _validate_with_schema(root: Path, value: Any, schema_relpath: str, label: str) -> None:
    _validate_with_validator(_compile_schema_validator(root, schema_relpath), value, label)


def _normalise_relpath(raw: str, *, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise KnowledgeError(f"{label} must be a non-empty repository-relative path")
    if "\\" in raw:
        raise KnowledgeError(f"{label} must use '/' separators: {raw!r}")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts or str(pure) != raw:
        raise KnowledgeError(f"unsafe or non-normalised {label}: {raw!r}")
    return raw


def _validate_path(
    root: Path,
    raw: str,
    *,
    label: str,
    optional: bool = False,
    require_file: bool | None = None,
) -> str:
    relpath = _normalise_relpath(raw, label=label)
    path = root / relpath
    if not path.exists():
        if optional:
            return relpath
        raise KnowledgeError(f"{label} does not exist: {relpath}")
    if require_file is True and not path.is_file():
        raise KnowledgeError(f"{label} must be a file: {relpath}")
    if require_file is False and not path.is_dir():
        raise KnowledgeError(f"{label} must be a directory: {relpath}")
    return relpath


def _ensure_unique(records: Iterable[Mapping[str, Any]], key: str, label: str) -> None:
    seen: dict[str, int] = {}
    for index, record in enumerate(records):
        value = str(record[key])
        if value in seen:
            raise KnowledgeError(f"duplicate {label} {value!r} at records {seen[value]} and {index}")
        seen[value] = index


def _load_git_tracked_paths(root: Path) -> frozenset[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "-z", "--"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise KnowledgeError(f"cannot enumerate Git-tracked knowledge inputs: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise KnowledgeError(f"cannot enumerate Git-tracked knowledge inputs: {detail}")
    return frozenset(
        raw.decode("utf-8", errors="surrogateescape")
        for raw in completed.stdout.split(b"\0")
        if raw
    )


def _validate_evidence(
    root: Path,
    evidence: Sequence[Mapping[str, Any]],
    label: str,
    tracked_paths: frozenset[str],
) -> None:
    for index, item in enumerate(evidence):
        optional = bool(item.get("optional", False))
        raw_path = str(item["path"])
        storage = str(item["storage"])
        item_label = f"{label}.evidence[{index}]"

        if storage == "external_root":
            if not optional:
                raise KnowledgeError(f"{item_label} storage=external_root must be optional")
            if not str(item.get("note", "")).strip():
                raise KnowledgeError(
                    f"{item_label} storage=external_root requires a recovery/locator note"
                )
            continue

        relpath = _normalise_relpath(raw_path, label=f"{item_label}.path")
        is_tracked = relpath in tracked_paths
        if storage == "git_tracked":
            if not is_tracked:
                raise KnowledgeError(
                    f"{item_label} declares git_tracked but Git does not track {relpath}"
                )
            if optional:
                raise KnowledgeError(f"{item_label} git_tracked evidence cannot be optional")
            _validate_path(root, relpath, label=f"{item_label}.path")
        elif storage == "workspace_untracked":
            if is_tracked:
                raise KnowledgeError(
                    f"{item_label} declares workspace_untracked but Git tracks {relpath}"
                )
            if not optional:
                raise KnowledgeError(f"{item_label} workspace_untracked evidence must be optional")
            _validate_path(root, relpath, label=f"{item_label}.path", optional=True)
        else:  # Schema validation should make this unreachable; stay fail-closed.
            raise KnowledgeError(f"{item_label} has unsupported storage state {storage!r}")


def _json_pointer(document: Any, pointer: str, *, label: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KnowledgeError(f"{label} must be an RFC 6901 JSON pointer")
    value = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            if token not in value:
                raise KnowledgeError(f"{label} does not resolve: missing object key {token!r}")
            value = value[token]
        elif isinstance(value, list):
            if not token.isdigit():
                raise KnowledgeError(
                    f"{label} does not resolve: array token {token!r} is not an index"
                )
            index = int(token)
            if index >= len(value):
                raise KnowledgeError(
                    f"{label} does not resolve: array index {index} is out of range"
                )
            value = value[index]
        else:
            raise KnowledgeError(f"{label} does not resolve through scalar value")
    return value


def _validate_decision_authority_source(
    model: KnowledgeModel,
    decision: Mapping[str, Any],
) -> None:
    decision_id = str(decision["id"])
    source = _require_mapping(
        decision["authority_source"],
        f"{decision_id}.authority_source",
    )
    relpath = _normalise_relpath(
        str(source["path"]),
        label=f"{decision_id}.authority_source.path",
    )
    if relpath not in model.tracked_paths:
        raise KnowledgeError(
            f"{decision_id}.authority_source must point to a Git-tracked external "
            f"authority: {relpath}"
        )
    _validate_path(
        model.root,
        relpath,
        label=f"{decision_id}.authority_source.path",
        require_file=True,
    )
    matching_evidence = [
        item
        for item in decision["evidence"]
        if str(item["path"]) == relpath and item["storage"] == "git_tracked"
    ]
    if not matching_evidence:
        raise KnowledgeError(
            f"{decision_id}.authority_source must also be declared as git_tracked evidence"
        )

    source_format = str(source["format"])
    if source_format == "json":
        payload: Any = _read_json(model.root, relpath)
    elif source_format == "text":
        try:
            payload = (model.root / relpath).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise KnowledgeError(f"cannot read {decision_id}.authority_source: {exc}") from exc
    else:
        raise KnowledgeError(
            f"{decision_id}.authority_source has unsupported format {source_format!r}"
        )

    for index, raw_assertion in enumerate(source["assertions"]):
        assertion = _require_mapping(
            raw_assertion,
            f"{decision_id}.authority_source.assertions[{index}]",
        )
        assertion_label = f"{decision_id}.authority_source.assertions[{index}]"
        pointer = assertion.get("pointer")
        if source_format == "json":
            if not isinstance(pointer, str):
                raise KnowledgeError(f"{assertion_label}.pointer is required for JSON authority")
            actual = _json_pointer(payload, pointer, label=f"{assertion_label}.pointer")
        else:
            if pointer is not None:
                raise KnowledgeError(f"{assertion_label}.pointer is forbidden for text authority")
            actual = payload

        expected = assertion["expected"]
        record_field = assertion.get("record_field")
        if record_field is not None:
            field = str(record_field)
            if field not in decision:
                raise KnowledgeError(
                    f"{assertion_label}.record_field names missing field {field!r}"
                )
            if decision[field] != expected:
                raise KnowledgeError(
                    f"{assertion_label}.expected disagrees with decision.{field}: "
                    f"{expected!r} != {decision[field]!r}"
                )

        operator = str(assertion["operator"])
        if operator == "equals":
            passed = actual == expected
        elif operator == "contains":
            passed = isinstance(actual, str) and isinstance(expected, str) and expected in actual
        else:
            raise KnowledgeError(f"{assertion_label} has unsupported operator {operator!r}")
        if not passed:
            raise KnowledgeError(
                f"{assertion_label} failed against {relpath}: operator={operator}, "
                f"expected={expected!r}, actual={actual!r}"
            )


def _validate_representation_mapping(current_state: Mapping[str, Any]) -> None:
    raw_mapping = _require_mapping(
        current_state["representation_class_mapping"],
        "current_state.representation_class_mapping",
    )
    observed = {
        str(key): tuple(str(value) for value in values)
        for key, values in raw_mapping.items()
    }
    if observed != REPRESENTATION_CLASS_MAPPING:
        raise KnowledgeError(
            "current_state.representation_class_mapping must equal the canonical "
            "representation-to-DOC_POLICY document_class bridge"
        )


def _computed_knowledge_census(model: KnowledgeModel) -> dict[str, int]:
    current_reviews = [
        review for review in model.backfill_reviews if review["status"] == "current"
    ]
    semantic_reviews = [
        review
        for review in current_reviews
        if review["review_scope"] != "availability_and_provenance"
    ]
    availability_reviews = [
        review
        for review in current_reviews
        if review["review_scope"] == "availability_and_provenance"
    ]
    triaged_ids = [
        str(dossier_id)
        for group in model.backfill_triage["groups"]
        for dossier_id in group["dossier_ids"]
    ]
    validity_reviews = [
        review
        for review in current_reviews
        if any(
            isinstance(model.claim_by_id[str(claim_id)].get("validity_profile"), dict)
            for claim_id in review["claim_ids"]
        )
    ]
    return {
        "claims_total": len(model.claims),
        "decisions_total": len(model.decisions),
        "backfill_reviews_total": len(model.backfill_reviews),
        "current_reviews": len(current_reviews),
        "current_evidence_dossiers": sum(
            record["relevance"] == "current_evidence"
            for record in model.dossiers["records"]
        ),
        "reasoning_profiles": sum(bool(claim.get("reasoning_profile")) for claim in model.claims),
        "derivation_profiles": sum(bool(claim.get("derivation_profile")) for claim in model.claims),
        "separation_profiles": sum(bool(claim.get("separation_profile")) for claim in model.claims),
        "validity_profiles": sum(bool(claim.get("validity_profile")) for claim in model.claims),
        "supersession_edges": sum(len(claim["supersedes"]) for claim in model.claims),
        "refuted_claims": sum(claim["status"] == "refuted" for claim in model.claims),
        "superseded_claims": sum(claim["status"] == "superseded" for claim in model.claims),
        "dossiers_total": len(model.dossiers["records"]),
        "semantic_review_dossiers": len(semantic_reviews),
        "availability_review_dossiers": len(availability_reviews),
        "triaged_dossiers": len(triaged_ids),
        "topics_total": len(model.topics["records"]),
        "terms_total": len(model.terminology["records"]),
        "current_validity_review_dossiers": len(validity_reviews),
    }


def _validate_knowledge_census(model: KnowledgeModel) -> None:
    expected = {
        str(key): int(value)
        for key, value in _require_mapping(
            model.knowledge_census["counts"],
            "knowledge_census.counts",
        ).items()
    }
    actual = _computed_knowledge_census(model)
    if expected != actual:
        differences = [
            f"{key}: expected={expected.get(key)!r}, actual={actual.get(key)!r}"
            for key in sorted(set(expected) | set(actual))
            if expected.get(key) != actual.get(key)
        ]
        raise KnowledgeError(
            "knowledge census drift; update the sole maintained fixture after "
            "reviewing the semantic change: " + "; ".join(differences)
        )


def _validate_claim_authority(model: KnowledgeModel, claim: Mapping[str, Any]) -> None:
    claim_id = str(claim["id"])
    authority = str(claim["authority"])
    basis = _require_mapping(claim["authority_basis"], f"{claim_id}.authority_basis")
    expected_basis = AUTHORITY_BASIS_BY_AUTHORITY[authority]
    if basis["basis_type"] != expected_basis:
        raise KnowledgeError(
            f"{claim_id}.authority_basis.basis_type must be {expected_basis!r} "
            f"for authority={authority!r}"
        )
    if claim["representation_class"] != "AUTHORITATIVE_CURRENT":
        raise KnowledgeError(
            f"{claim_id} is a claims.jsonl source record and must use "
            "AUTHORITATIVE_CURRENT"
        )

    evidence_by_path = {str(item["path"]): item for item in claim["evidence"]}
    for index, raw_path in enumerate(basis["source_paths"]):
        relpath = _normalise_relpath(
            str(raw_path),
            label=f"{claim_id}.authority_basis.source_paths[{index}]",
        )
        if relpath not in evidence_by_path:
            raise KnowledgeError(
                f"{claim_id}.authority_basis source is not present in evidence: {relpath}"
            )

    verification_id = basis.get("verification_id")
    if authority == "machine":
        if not isinstance(verification_id, str):
            raise KnowledgeError(f"{claim_id} authority=machine requires verification_id")
        untracked = sorted(
            str(source_path)
            for source_path in basis["source_paths"]
            if str(source_path) not in model.tracked_paths
        )
        if untracked:
            raise KnowledgeError(
                f"{claim_id} authority=machine uses non-tracked authority sources: "
                f"{untracked}"
            )
        _verify_machine_claim(model, claim, verification_id)
    elif verification_id is not None:
        raise KnowledgeError(
            f"{claim_id} non-machine authority cannot advertise machine verification_id"
        )

    for decision_id in claim["decision_ids"]:
        if decision_id not in model.decision_by_id:
            raise KnowledgeError(f"{claim_id} references missing decision {decision_id}")

def _validate_separation_profile(claim: Mapping[str, Any]) -> None:
    profile = claim.get("separation_profile")
    if not isinstance(profile, dict):
        return

    claim_id = str(claim["id"])
    selection_modes = tuple(str(item) for item in profile["selection_modes"])
    validation_modes = tuple(str(item) for item in profile["validation_modes"])
    consumption_modes = tuple(str(item) for item in profile["consumption_modes"])

    if "not_applicable" in selection_modes and len(selection_modes) != 1:
        raise KnowledgeError(
            f"{claim_id}.separation_profile.selection_modes cannot mix not_applicable with active modes"
        )
    if "none" in validation_modes and len(validation_modes) != 1:
        raise KnowledgeError(
            f"{claim_id}.separation_profile.validation_modes cannot mix none with positive validation"
        )
    if profile["completeness"] == "disproved" and "counterexample" not in validation_modes:
        raise KnowledgeError(
            f"{claim_id}.separation_profile completeness=disproved requires counterexample validation"
        )
    if profile["completeness"] == "proved_for_declared_domain" and validation_modes == ("none",):
        raise KnowledgeError(
            f"{claim_id}.separation_profile proved completeness requires positive validation"
        )
    if "model_omission" in consumption_modes and profile["target_stage"] != "pre_model":
        raise KnowledgeError(
            f"{claim_id}.separation_profile model_omission must target pre_model"
        )


def _validate_validity_profile(claim: Mapping[str, Any]) -> None:
    profile = claim.get("validity_profile")
    claim_id = str(claim["id"])
    status = str(claim["status"])

    if status in {"refuted", "superseded"} and not isinstance(profile, dict):
        raise KnowledgeError(f"{claim_id} status={status} requires validity_profile")
    if claim["supersedes"] and not isinstance(profile, dict):
        raise KnowledgeError(f"{claim_id} with supersedes edges requires validity_profile")
    if not isinstance(profile, dict):
        return

    event_type = str(profile["event_type"])
    reuse_policy = str(profile["reuse_policy"])
    repair_state = str(profile["repair_state"])
    basis = {str(item) for item in profile["basis"]}

    if event_type == "refutation" and status != "refuted":
        raise KnowledgeError(f"{claim_id}.validity_profile event_type=refutation requires status=refuted")
    if status == "refuted" and reuse_policy not in {"do_not_reuse", "historical_only"}:
        raise KnowledgeError(f"{claim_id} refuted claim cannot use reuse_policy={reuse_policy}")
    if status == "superseded" and reuse_policy not in {
        "historical_only",
        "revalidate_before_use",
        "method_only",
    }:
        raise KnowledgeError(f"{claim_id} superseded claim cannot use reuse_policy={reuse_policy}")
    if reuse_policy == "current_after_repair" and repair_state != "revalidated":
        raise KnowledgeError(
            f"{claim_id}.validity_profile current_after_repair requires repair_state=revalidated"
        )
    if reuse_policy == "revalidate_before_use" and repair_state not in {
        "pending",
        "repaired_unverified",
    }:
        raise KnowledgeError(
            f"{claim_id}.validity_profile revalidate_before_use requires pending or repaired_unverified"
        )
    if reuse_policy == "unaffected_under_premises" and repair_state != "revalidated":
        raise KnowledgeError(
            f"{claim_id}.validity_profile unaffected_under_premises requires repair_state=revalidated"
        )
    if event_type == "revalidation":
        if repair_state != "revalidated":
            raise KnowledgeError(f"{claim_id}.validity_profile revalidation requires repair_state=revalidated")
        if not basis.intersection({
            "controlled_experiment",
            "differential_test",
            "independent_recomputation",
            "proof_replay",
        }):
            raise KnowledgeError(f"{claim_id}.validity_profile revalidation lacks positive replay basis")


def _assert_acyclic(
    records: Sequence[Mapping[str, Any]],
    edge_key: str,
    label: str,
) -> None:
    graph = {str(record["id"]): tuple(str(item) for item in record[edge_key]) for record in records}
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> None:
        mark = state.get(node, 0)
        if mark == 2:
            return
        if mark == 1:
            try:
                start = stack.index(node)
            except ValueError:
                start = 0
            cycle = " -> ".join([*stack[start:], node])
            raise KnowledgeError(f"{label} contains a cycle: {cycle}")
        state[node] = 1
        stack.append(node)
        for target in graph[node]:
            visit(target)
        stack.pop()
        state[node] = 2

    for node in graph:
        visit(node)


def _inventory_root_specs(current_state: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    specs = tuple(current_state["inventory"]["roots"])
    seen: set[str] = set()
    for index, spec in enumerate(specs):
        path = _normalise_relpath(str(spec["path"]), label=f"inventory.roots[{index}].path")
        if path in seen:
            raise KnowledgeError(f"duplicate inventory root: {path}")
        seen.add(path)
    return specs


def _inventory_children(
    root: Path,
    current_state: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    excluded = {str(path) for path in current_state["inventory"]["exclude_paths"]}
    observed: dict[str, Mapping[str, Any]] = {}
    missing_optional_roots: set[str] = set()

    for index, spec in enumerate(_inventory_root_specs(current_state)):
        relpath = _normalise_relpath(str(spec["path"]), label=f"inventory.roots[{index}].path")
        directory = root / relpath
        if not directory.exists():
            if spec["availability"] == "optional":
                missing_optional_roots.add(relpath)
                continue
            raise KnowledgeError(f"required inventory root does not exist: {relpath}")
        if not directory.is_dir():
            raise KnowledgeError(f"inventory root must be a directory: {relpath}")

        include_markdown = spec["include"] == "directories_and_markdown"
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            child_relpath = child.relative_to(root).as_posix()
            if child_relpath in excluded:
                continue
            if child.is_dir() or (include_markdown and child.is_file() and child.suffix.lower() == ".md"):
                if child_relpath in observed:
                    raise KnowledgeError(f"inventory roots overlap at {child_relpath}")
                observed[child_relpath] = spec
    return observed, missing_optional_roots


def _root_spec_for_record(
    path: str,
    current_state: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    pure = PurePosixPath(path)
    for spec in _inventory_root_specs(current_state):
        root_path = PurePosixPath(str(spec["path"]))
        if pure.parent == root_path:
            return spec
    return None


def _inventory_child_for_path(
    path: str,
    current_state: Mapping[str, Any],
) -> str | None:
    """Return the registered first-level package containing *path*, if any."""

    pure = PurePosixPath(path)
    for spec in _inventory_root_specs(current_state):
        root_path = PurePosixPath(str(spec["path"]))
        try:
            relative = pure.relative_to(root_path)
        except ValueError:
            continue
        if not relative.parts:
            return None
        return (root_path / relative.parts[0]).as_posix()
    return None


def _validate_record_dossier_links(
    model: KnowledgeModel,
    record: Mapping[str, Any],
    *,
    label: str,
) -> None:
    """Require exact two-way links between package evidence and dossier IDs."""

    dossier_by_path = {str(dossier["path"]): str(dossier["id"]) for dossier in model.dossiers["records"]}
    expected_ids: set[str] = set()
    for evidence in record["evidence"]:
        package_path = _inventory_child_for_path(
            str(evidence["path"]),
            model.current_state,
        )
        if package_path is None:
            continue
        dossier_id = dossier_by_path.get(package_path)
        if dossier_id is None:
            raise KnowledgeError(f"{label} evidence belongs to unregistered package {package_path}")
        expected_ids.add(dossier_id)

    actual_ids = {str(item) for item in record["dossier_ids"]}
    missing = sorted(expected_ids - actual_ids)
    ungrounded = sorted(actual_ids - expected_ids)
    if missing or ungrounded:
        details: list[str] = []
        if missing:
            details.append("missing dossier_ids=" + ", ".join(missing))
        if ungrounded:
            details.append("dossier_ids without package evidence=" + ", ".join(ungrounded))
        raise KnowledgeError(f"{label} dossier/evidence drift: " + "; ".join(details))


def _path_belongs_to_dossier(
    root: Path,
    reviewed_path: str,
    dossier_path: str,
) -> bool:
    del root  # existence is validated separately, with local_optional awareness
    return reviewed_path == dossier_path or reviewed_path.startswith(f"{dossier_path}/")


def _validate_backfill_review(
    model: KnowledgeModel,
    review: Mapping[str, Any],
) -> None:
    review_id = str(review["id"])
    dossier_id = str(review["dossier_id"])
    dossier = model.dossier_by_id.get(dossier_id)
    if dossier is None:
        raise KnowledgeError(f"{review_id} references missing dossier {dossier_id}")

    dossier_path = str(dossier["path"])
    optional = dossier["tracked_state"] == "local_optional"
    for index, raw_path in enumerate(review["reviewed_paths"]):
        reviewed_path = _normalise_relpath(
            str(raw_path),
            label=f"{review_id}.reviewed_paths[{index}]",
        )
        if not _path_belongs_to_dossier(model.root, reviewed_path, dossier_path):
            raise KnowledgeError(
                f"{review_id}.reviewed_paths[{index}] is outside dossier {dossier_path}: {reviewed_path}"
            )
        _validate_path(
            model.root,
            reviewed_path,
            label=f"{review_id}.reviewed_paths[{index}]",
            optional=optional,
        )

    claim_by_id = model.claim_by_id
    for claim_id in review["claim_ids"]:
        claim = claim_by_id.get(str(claim_id))
        if claim is None:
            raise KnowledgeError(f"{review_id} references missing claim {claim_id}")
        if dossier_id not in claim["dossier_ids"]:
            raise KnowledgeError(f"{review_id} links {claim_id}, but that claim does not cite dossier {dossier_id}")

    outcome = str(review["outcome"])
    review_scope = str(review["review_scope"])
    claim_ids = tuple(str(item) for item in review["claim_ids"])
    unresolved = tuple(str(item) for item in review["unresolved"])
    if review_scope == "availability_and_provenance":
        if dossier["tracked_state"] != "local_optional":
            raise KnowledgeError(
                f"{review_id} availability_and_provenance is only valid for local_optional dossiers"
            )
        if outcome != "deferred" or not unresolved:
            raise KnowledgeError(
                f"{review_id} availability_and_provenance must remain deferred with an unresolved reason"
            )
    if outcome in {"claims_promoted", "existing_claims_confirmed", "inconclusive"} and not claim_ids:
        raise KnowledgeError(f"{review_id} outcome={outcome} requires at least one claim_id")
    if outcome == "no_reusable_claim" and claim_ids:
        raise KnowledgeError(f"{review_id} outcome=no_reusable_claim must not list claim_ids")
    if outcome == "deferred" and not unresolved:
        raise KnowledgeError(f"{review_id} outcome=deferred requires an unresolved reason")



def _validate_dossier_portability(model: KnowledgeModel, dossier: Mapping[str, Any]) -> None:
    portability = dossier.get("portability")
    dossier_id = str(dossier["id"])
    if portability is None:
        if dossier["tracked_state"] == "local_optional" and dossier.get("workflow") is not None:
            raise KnowledgeError(f"{dossier_id} workflow-managed local_optional dossier requires portability")
        return

    dossier_path = str(dossier["path"])
    if dossier["tracked_state"] != "local_optional":
        raise KnowledgeError(f"{dossier_id}.portability is only valid for local_optional dossiers")

    manifest_path = _normalise_relpath(
        str(portability["manifest_path"]),
        label=f"{dossier_id}.portability.manifest_path",
    )
    if not _path_belongs_to_dossier(model.root, manifest_path, dossier_path):
        raise KnowledgeError(
            f"{dossier_id}.portability.manifest_path is outside dossier {dossier_path}: {manifest_path}"
        )
    manifest = model.root / manifest_path
    if manifest.exists():
        if not manifest.is_file():
            raise KnowledgeError(f"{dossier_id}.portability.manifest_path must name a file")
        actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
        expected = str(portability["manifest_sha256"])
        if actual != expected:
            raise KnowledgeError(
                f"{dossier_id}.portability manifest digest mismatch: expected {expected}, got {actual}"
            )

    recovery_path = _normalise_relpath(
        str(portability["recovery_instructions"]),
        label=f"{dossier_id}.portability.recovery_instructions",
    )
    if _path_belongs_to_dossier(model.root, recovery_path, dossier_path):
        raise KnowledgeError(
            f"{dossier_id}.portability.recovery_instructions must live outside local evidence: {recovery_path}"
        )
    _validate_path(
        model.root,
        recovery_path,
        label=f"{dossier_id}.portability.recovery_instructions",
        require_file=True,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", recovery_path],
        cwd=model.root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked.returncode != 0:
        raise KnowledgeError(
            f"{dossier_id}.portability.recovery_instructions must be Git-tracked: {recovery_path}"
        )


def _validate_dossier_workflow(model: KnowledgeModel, dossier: Mapping[str, Any]) -> None:
    workflow = dossier.get("workflow")
    if workflow is None:
        return

    dossier_id = str(dossier["id"])
    lifecycle = str(dossier["lifecycle"])
    closure = workflow["closure"]
    opened_at = date.fromisoformat(str(workflow["opened_at"]))
    if lifecycle == "active":
        if closure is not None:
            raise KnowledgeError(f"{dossier_id} lifecycle=active requires workflow.closure=null")
        return
    if closure is None:
        raise KnowledgeError(f"{dossier_id} closed lifecycle requires a typed workflow.closure")

    closed_at = date.fromisoformat(str(closure["closed_at"]))
    if closed_at < opened_at:
        raise KnowledgeError(f"{dossier_id}.workflow closure predates opened_at")

    review_id = str(closure["review_id"])
    review = model.backfill_review_by_id.get(review_id)
    if review is None:
        raise KnowledgeError(f"{dossier_id}.workflow references missing review {review_id}")
    if review["status"] != "current" or str(review["dossier_id"]) != dossier_id:
        raise KnowledgeError(f"{dossier_id}.workflow review must be the current review for this dossier: {review_id}")

    claim_ids = tuple(str(value) for value in closure["claim_ids"])
    decision_ids = tuple(str(value) for value in closure["decision_ids"])
    successor_ids = tuple(str(value) for value in closure["successor_dossier_ids"])
    reason = closure["no_reusable_claim_reason"]
    for claim_id in claim_ids:
        claim = model.claim_by_id.get(claim_id)
        if claim is None:
            raise KnowledgeError(f"{dossier_id}.workflow references missing claim {claim_id}")
        if dossier_id not in claim["dossier_ids"]:
            raise KnowledgeError(f"{dossier_id}.workflow claim {claim_id} does not cite this dossier")
    for decision_id in decision_ids:
        decision = model.decision_by_id.get(decision_id)
        if decision is None:
            raise KnowledgeError(f"{dossier_id}.workflow references missing decision {decision_id}")
        if dossier_id not in decision["dossier_ids"]:
            raise KnowledgeError(f"{dossier_id}.workflow decision {decision_id} does not cite this dossier")
    for successor_id in successor_ids:
        if successor_id == dossier_id or successor_id not in model.dossier_by_id:
            raise KnowledgeError(f"{dossier_id}.workflow references invalid successor dossier {successor_id}")

    outcome = str(closure["outcome"])
    review_claim_ids = {str(value) for value in review["claim_ids"]}
    if outcome == "knowledge_promoted":
        if not claim_ids or successor_ids or reason is not None:
            raise KnowledgeError(
                f"{dossier_id} outcome=knowledge_promoted requires claims and forbids successors/reason"
            )
        if not set(claim_ids) <= review_claim_ids:
            raise KnowledgeError(f"{dossier_id}.workflow promoted claims must be listed by review {review_id}")
        if review["outcome"] not in {"claims_promoted", "existing_claims_confirmed", "inconclusive"}:
            raise KnowledgeError(f"{dossier_id} knowledge_promoted conflicts with review outcome={review['outcome']}")
    elif outcome == "negative_results_promoted":
        if not claim_ids or decision_ids or successor_ids or reason is not None:
            raise KnowledgeError(
                f"{dossier_id} outcome=negative_results_promoted requires only negative-result claims"
            )
        if any(model.claim_by_id[claim_id]["kind"] != "negative_result" for claim_id in claim_ids):
            raise KnowledgeError(f"{dossier_id} negative_results_promoted includes a non-negative-result claim")
        if not set(claim_ids) <= review_claim_ids or review["outcome"] != "claims_promoted":
            raise KnowledgeError(f"{dossier_id} negative results must be promoted by review {review_id}")
    elif outcome == "decision_recorded":
        if claim_ids or not decision_ids or successor_ids or reason is not None:
            raise KnowledgeError(f"{dossier_id} outcome=decision_recorded requires only decision_ids")
    elif outcome == "no_reusable_claim":
        if claim_ids or decision_ids or successor_ids or not isinstance(reason, str) or not reason.strip():
            raise KnowledgeError(f"{dossier_id} outcome=no_reusable_claim requires only a non-empty reason")
        if review["outcome"] != "no_reusable_claim":
            raise KnowledgeError(f"{dossier_id} no_reusable_claim conflicts with review outcome={review['outcome']}")
    elif outcome == "superseded_by_dossier":
        if lifecycle != "superseded" or not successor_ids or reason is not None:
            raise KnowledgeError(
                f"{dossier_id} outcome=superseded_by_dossier requires lifecycle=superseded and successors"
            )
    else:  # pragma: no cover - schema validation owns the enum
        raise KnowledgeError(f"{dossier_id} has unsupported workflow outcome {outcome}")

    if lifecycle == "superseded" and outcome != "superseded_by_dossier":
        raise KnowledgeError(f"{dossier_id} lifecycle=superseded requires outcome=superseded_by_dossier")

def _normalise_term_label(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", value.strip().casefold())


def _validate_backfill_triage(model: KnowledgeModel) -> None:
    claim_by_id = model.claim_by_id
    review_by_id = model.backfill_review_by_id
    dossier_by_id = model.dossier_by_id
    current_reviewed = set(model.current_review_by_dossier)
    seen: dict[str, str] = {}

    for group in model.backfill_triage["groups"]:
        group_id = str(group["id"])
        for claim_id in group["related_claim_ids"]:
            if claim_id not in claim_by_id:
                raise KnowledgeError(f"{group_id} references missing claim {claim_id}")
        for review_id in group["representative_review_ids"]:
            review = review_by_id.get(str(review_id))
            if review is None:
                raise KnowledgeError(f"{group_id} references missing review {review_id}")
            if review["status"] != "current":
                raise KnowledgeError(f"{group_id} representative review is not current: {review_id}")
        if group["disposition"] == "family_context_only" and not (
            group["related_claim_ids"] or group["representative_review_ids"]
        ):
            raise KnowledgeError(f"{group_id} family_context_only requires a current knowledge coordinate")
        for dossier_id in group["dossier_ids"]:
            dossier_id = str(dossier_id)
            dossier = dossier_by_id.get(dossier_id)
            if dossier is None:
                raise KnowledgeError(f"{group_id} references missing dossier {dossier_id}")
            if dossier_id in current_reviewed:
                raise KnowledgeError(f"{group_id} includes current-reviewed dossier {dossier_id}")
            previous = seen.get(dossier_id)
            if previous is not None:
                raise KnowledgeError(f"dossier {dossier_id} appears in two triage groups: {previous}, {group_id}")
            if group["disposition"] == "local_optional_queue" and dossier["tracked_state"] != "local_optional":
                raise KnowledgeError(f"{group_id} local_optional_queue contains tracked dossier {dossier_id}")
            if group["disposition"] != "local_optional_queue" and dossier["tracked_state"] == "local_optional":
                raise KnowledgeError(f"{group_id} contains local_optional dossier under a tracked disposition: {dossier_id}")
            seen[dossier_id] = group_id

    open_workflow_dossiers = {
        dossier_id
        for dossier_id, dossier in dossier_by_id.items()
        if dossier.get("lifecycle") == "active"
        and isinstance(dossier.get("workflow"), dict)
        and dossier["workflow"].get("closure") is None
    }
    expected = set(dossier_by_id) - current_reviewed - open_workflow_dossiers
    actual = set(seen)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing=" + ", ".join(missing))
        if extra:
            details.append("extra=" + ", ".join(extra))
        raise KnowledgeError("backfill triage must cover every non-current-reviewed dossier exactly once: " + "; ".join(details))


def _validate_terminology(model: KnowledgeModel) -> None:
    claim_by_id = model.claim_by_id
    labels: dict[str, str] = {}
    for term in model.terminology["records"]:
        term_id = str(term["id"])
        for raw_label in (term["canonical_label"], *term["aliases"]):
            normalised = _normalise_term_label(str(raw_label))
            previous = labels.get(normalised)
            if previous is not None and previous != term_id:
                raise KnowledgeError(f"terminology label {raw_label!r} is shared by {previous} and {term_id}")
            labels[normalised] = term_id
        for claim_id in term["related_claim_ids"]:
            if claim_id not in claim_by_id:
                raise KnowledgeError(f"{term_id} references missing claim {claim_id}")
        generated_paths = {str(value) for value in model.current_state["generated_outputs"].values()}
        for index, raw_path in enumerate(term["source_paths"]):
            relpath = _normalise_relpath(str(raw_path), label=f"{term_id}.source_paths[{index}]")
            _validate_path(
                model.root,
                relpath,
                label=f"{term_id}.source_paths[{index}]",
                optional=relpath in generated_paths,
            )


def _validate_topics(model: KnowledgeModel) -> None:
    claim_by_id = model.claim_by_id
    term_by_id = model.term_by_id
    dossier_labels = {str(label) for dossier in model.dossiers["records"] for label in dossier["topics"]}
    covered_claims: set[str] = set()
    covered_labels: set[str] = set()
    used_terms: set[str] = set()

    for topic in model.topics["records"]:
        topic_id = str(topic["id"])
        topic_claims = {str(item) for item in topic["claim_ids"]}
        for claim_id in topic_claims:
            if claim_id not in claim_by_id:
                raise KnowledgeError(f"{topic_id} references missing claim {claim_id}")
        for claim_id in topic["open_question_claim_ids"]:
            if claim_id not in topic_claims:
                raise KnowledgeError(f"{topic_id} open question is not in claim_ids: {claim_id}")
            if claim_by_id[str(claim_id)]["status"] != "open":
                raise KnowledgeError(f"{topic_id} open question is not status=open: {claim_id}")
        for label in topic["dossier_topic_labels"]:
            if label not in dossier_labels:
                raise KnowledgeError(f"{topic_id} references unknown dossier topic label {label}")
        for term_id in topic["term_ids"]:
            if term_id not in term_by_id:
                raise KnowledgeError(f"{topic_id} references missing term {term_id}")
        generated_paths = {str(value) for value in model.current_state["generated_outputs"].values()}
        for index, raw_path in enumerate(topic["entry_paths"]):
            relpath = _normalise_relpath(str(raw_path), label=f"{topic_id}.entry_paths[{index}]")
            _validate_path(
                model.root,
                relpath,
                label=f"{topic_id}.entry_paths[{index}]",
                optional=relpath in generated_paths,
            )
        covered_claims.update(topic_claims)
        covered_labels.update(str(item) for item in topic["dossier_topic_labels"])
        used_terms.update(str(item) for item in topic["term_ids"])

    open_claim_ids = {
        str(claim["id"]) for claim in model.claims if claim["status"] == "open"
    }
    indexed_open_claim_ids = {
        str(claim_id)
        for topic in model.topics["records"]
        for claim_id in topic["open_question_claim_ids"]
    }
    missing_open_claims = sorted(open_claim_ids - indexed_open_claim_ids)
    extra_open_claims = sorted(indexed_open_claim_ids - open_claim_ids)
    if missing_open_claims or extra_open_claims:
        details: list[str] = []
        if missing_open_claims:
            details.append("missing=" + ", ".join(missing_open_claims))
        if extra_open_claims:
            details.append("non_open=" + ", ".join(extra_open_claims))
        raise KnowledgeError(
            "topic registry open-question coverage is not exact: " + "; ".join(details)
        )

    missing_claims = sorted(set(claim_by_id) - covered_claims)
    missing_labels = sorted(dossier_labels - covered_labels)
    missing_terms = sorted(set(term_by_id) - used_terms)
    if missing_claims:
        raise KnowledgeError("topic registry leaves claims unindexed: " + ", ".join(missing_claims))
    if missing_labels:
        raise KnowledgeError("topic registry leaves dossier labels unindexed: " + ", ".join(missing_labels))
    if missing_terms:
        raise KnowledgeError("topic registry leaves terminology unindexed: " + ", ".join(missing_terms))


def _load_machine_sources(root: Path, current_state: Mapping[str, Any]) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for key, raw_path in current_state["sources"].items():
        relpath = _validate_path(root, str(raw_path), label=f"sources.{key}", require_file=True)
        if key == "project_lock":
            sources[key] = {"path": relpath}
        else:
            sources[key] = _read_json(root, relpath)
    return sources


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise KnowledgeError(f"{label} must be an object")
    return value


def _require_sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise KnowledgeError(f"{label} must be an array")
    return value


def _require_text_fragments(text: str, fragments: Sequence[str], *, label: str) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise KnowledgeError(f"{label} is missing machine-verification fragments: {missing}")


def _require_claim_fragments(
    claim: Mapping[str, Any],
    fragments: Sequence[str],
    *,
    label: str,
) -> None:
    statement = str(claim["statement"])
    missing = [fragment for fragment in fragments if fragment not in statement]
    if missing:
        raise KnowledgeError(f"{label} statement is missing load-bearing fragments: {missing}")


def _verify_machine_claim(
    model: KnowledgeModel,
    claim: Mapping[str, Any],
    verification_id: str,
) -> None:
    claim_id = str(claim["id"])
    expected_claim_by_verifier = {
        "project_lock_active_scope": "CLAIM-ACTIVE-SCOPE-SINGLE-BASE",
        "project_lock_certified_scope": "CLAIM-CERTIFIED-THEOREM-SCOPE",
        "project_lock_cut_framework_status": "CLAIM-CUT-FRAMEWORK-PRODUCTION-STATUS",
        "exact_full_scale_durable_certified_absent": "CLAIM-DURABLE-CERTIFIED-RESULT-ABSENT",
        "typed_cut_pipeline_contract": (
            "CLAIM-TYPED-CUT-PIPELINE-CONSUMES-KNOWN-CUTS-NOT-DISCOVERS-THEM"
        ),
    }
    expected_claim_id = expected_claim_by_verifier.get(verification_id)
    if expected_claim_id is None:
        raise KnowledgeError(f"{claim_id} names unknown machine verification_id {verification_id!r}")
    if claim_id != expected_claim_id:
        raise KnowledgeError(
            f"machine verification_id {verification_id!r} is reserved for {expected_claim_id}, "
            f"not {claim_id}"
        )

    project_lock = (model.root / str(model.current_state["sources"]["project_lock"])).read_text(
        encoding="utf-8"
    )
    if verification_id == "project_lock_active_scope":
        _require_text_fragments(
            project_lock,
            (
                "The current certified IndustrialPlanner support contract targets "
                "`valley4_protocol_core` (70×70) exclusively.",
                "are preserved as `future_scope`",
            ),
            label="PROJECT_LOCK.md active scope",
        )
        _require_claim_fragments(
            claim,
            ("70×70", "valley4_protocol_core", "future_scope"),
            label=claim_id,
        )
        required_scope = {"certified_exact", "valley4_protocol_core", "70x70"}
        if not required_scope <= set(str(value) for value in claim["scope"]):
            raise KnowledgeError(f"{claim_id} scope no longer matches the active-scope verifier")
        return

    if verification_id == "project_lock_certified_scope":
        _require_text_fragments(
            project_lock,
            (
                "π* 满足下列全部 **gating 谓词**",
                "`max_lex(area, min_side)`",
                "### B. EXPLICITLY OUT-OF-SCOPE",
                "物料离散吞吐 / belt 带宽容量未证",
            ),
            label="PROJECT_LOCK.md certified theorem scope",
        )
        _require_claim_fragments(
            claim,
            ("六个 gating 谓词", "max_lex(area, min_side)", "吞吐"),
            label=claim_id,
        )
        return

    if verification_id == "project_lock_cut_framework_status":
        _require_text_fragments(
            project_lock,
            (
                "EXACT_CUT_FRAMEWORK_ATTACH=1",
                "F5 is shadow-only",
                "F2/F3/F4/F9 are LEGACY_DIAGNOSTIC",
                "Until owner promotion",
            ),
            label="PROJECT_LOCK.md cut-framework status",
        )
        typed_platform = (model.root / "src/cuts/typed_platform.py").read_text(encoding="utf-8")
        lifecycle = (model.root / "src/cuts/lifecycle.py").read_text(encoding="utf-8")
        _require_text_fragments(
            typed_platform,
            ("class CompiledCut:", "class ShadowValidated:", 'LEGACY_DIAGNOSTIC = "LEGACY_DIAGNOSTIC"'),
            label="src/cuts/typed_platform.py",
        )
        _require_text_fragments(
            lifecycle,
            ("def step_6_attach_scope_check(", "def step_8_apply_to_master("),
            label="src/cuts/lifecycle.py",
        )
        _require_claim_fragments(
            claim,
            ("default-off", "B6 owner promotion 未执行", "F5 仍为 shadow-only"),
            label=claim_id,
        )
        return

    if verification_id == "exact_full_scale_durable_certified_absent":
        exact = _require_mapping(
            model.machine_sources["exact_full_scale_status"],
            "exact_full_scale_status",
        )
        if str(exact.get("status", "")).lower() != "open":
            raise KnowledgeError(f"{claim_id} requires exact_full_scale_status.status=open")
        if exact.get("best_certified_result") is not None:
            raise KnowledgeError(f"{claim_id} requires best_certified_result=null")
        blockers = _require_sequence(
            exact.get("blocking_check_ids"),
            "exact_full_scale_status.blocking_check_ids",
        )
        if not blockers:
            raise KnowledgeError(f"{claim_id} requires at least one blocking check")
        tracked_blueprints = sorted(
            path for path in model.tracked_paths if path.startswith("data/blueprints/")
        )
        if tracked_blueprints:
            raise KnowledgeError(
                f"{claim_id} requires the current tracked tree to omit data/blueprints/: "
                f"{tracked_blueprints}"
            )
        _require_claim_fragments(
            claim,
            (
                "OPEN",
                "best_certified_result 为 null",
                "durable CERTIFIED",
                "tracked tree 未包含 data/blueprints/",
            ),
            label=claim_id,
        )
        return

    if verification_id == "typed_cut_pipeline_contract":
        typed_platform = (model.root / "src/cuts/typed_platform.py").read_text(encoding="utf-8")
        lifecycle = (model.root / "src/cuts/lifecycle.py").read_text(encoding="utf-8")
        _require_text_fragments(
            typed_platform,
            (
                "class CompiledCut:",
                "def validate_and_compile_cut(",
                "class FamilyCapabilityRegistry:",
            ),
            label="src/cuts/typed_platform.py typed consumer contract",
        )
        _require_text_fragments(
            lifecycle,
            ("def step_6_attach_scope_check(", "def step_8_apply_to_master("),
            label="src/cuts/lifecycle.py typed consumer contract",
        )
        _require_claim_fragments(
            claim,
            ("消费 cut", "不从候选空间自主生成有用 cut", "不改变 certified default-off"),
            label=claim_id,
        )
        return

    raise KnowledgeError(f"unhandled machine verification_id {verification_id!r}")


def _validate_machine_sources(model: KnowledgeModel) -> None:
    sources = model.machine_sources

    canonical = _require_mapping(sources["canonical_rules"], "canonical_rules")
    metadata = _require_mapping(canonical.get("metadata"), "canonical_rules.metadata")
    if not isinstance(metadata.get("version"), str):
        raise KnowledgeError("canonical_rules.metadata.version must be a string")
    globals_block = _require_mapping(canonical.get("globals"), "canonical_rules.globals")
    grid = _require_mapping(globals_block.get("grid"), "canonical_rules.globals.grid")
    for key in ("width", "height"):
        if not isinstance(grid.get(key), int) or int(grid[key]) <= 0:
            raise KnowledgeError(f"canonical_rules.globals.grid.{key} must be a positive integer")
    empty = _require_mapping(
        globals_block.get("empty_rectangle"),
        "canonical_rules.globals.empty_rectangle",
    )
    for key in ("objective", "min_side_admissibility", "emptiness"):
        if key not in empty:
            raise KnowledgeError(f"canonical_rules.globals.empty_rectangle is missing {key}")
    if not isinstance(empty["min_side_admissibility"], int):
        raise KnowledgeError("canonical min_side_admissibility must be an integer")

    mandatory = _require_sequence(sources["mandatory_instances"], "mandatory_instances")
    if not mandatory:
        raise KnowledgeError("mandatory_instances must not be empty")
    for index, record in enumerate(mandatory):
        if not isinstance(record, dict) or record.get("is_mandatory") is not True:
            raise KnowledgeError(f"mandatory_instances[{index}] is not an explicit mandatory record")

    obligations = _require_mapping(sources["proof_obligations"], "proof_obligations")
    for key in ("status", "updated_at", "review_anchor", "obligations"):
        if key not in obligations:
            raise KnowledgeError(f"proof_obligations is missing {key}")
    _require_sequence(obligations["obligations"], "proof_obligations.obligations")

    gate = _require_mapping(sources["phase_gate"], "phase_gate")
    for key in (
        "status",
        "updated_at",
        "current_review_anchor",
        "owner_manual_state",
        "owner_manual_decision",
        "next_phase_entry",
        "receipt_policy",
    ):
        if key not in gate:
            raise KnowledgeError(f"phase_gate is missing {key}")
    owner_state = _require_mapping(gate["owner_manual_state"], "phase_gate.owner_manual_state")
    owner_decision = _require_mapping(
        gate["owner_manual_decision"],
        "phase_gate.owner_manual_decision",
    )
    next_phase = _require_mapping(gate["next_phase_entry"], "phase_gate.next_phase_entry")
    receipt_policy = _require_mapping(gate["receipt_policy"], "phase_gate.receipt_policy")
    for key in ("decision_id", "decided_at", "decided_by"):
        if key not in owner_decision:
            raise KnowledgeError(f"phase_gate.owner_manual_decision is missing {key}")
    for key in ("phase", "allowed"):
        if key not in next_phase:
            raise KnowledgeError(f"phase_gate.next_phase_entry is missing {key}")
    if owner_state.get("repo_derives_clean_count_from_receipts") is not False:
        raise KnowledgeError("phase gate must explicitly deny repository-derived clean counting")
    if receipt_policy.get("can_open_p1_3b") is not False:
        raise KnowledgeError("phase gate receipts must not be able to open P1.3")

    matching_decisions = [
        decision
        for decision in model.decisions
        if decision.get("external_decision_id") == owner_decision["decision_id"]
    ]
    if len(matching_decisions) != 1:
        raise KnowledgeError("exactly one decision ledger record must match the current phase-gate decision id")
    matching = matching_decisions[0]
    if matching["status"] != "current" or matching["decided_at"] != owner_decision["decided_at"]:
        raise KnowledgeError("current phase-gate decision ledger record disagrees with the gate")

    exact = _require_mapping(sources["exact_full_scale_status"], "exact_full_scale_status")
    for key in (
        "status",
        "best_certified_result",
        "resume_compatible_with_current_hashes",
        "blocking_check_ids",
        "checks",
    ):
        if key not in exact:
            raise KnowledgeError(f"exact_full_scale_status is missing {key}")
    blockers = _require_sequence(exact["blocking_check_ids"], "exact_full_scale_status.blocking_check_ids")
    checks = _require_sequence(exact["checks"], "exact_full_scale_status.checks")
    check_ids = {str(check.get("check_id")) for check in checks if isinstance(check, dict)}
    missing_checks = sorted(str(blocker) for blocker in blockers if str(blocker) not in check_ids)
    if missing_checks:
        raise KnowledgeError(f"exact_full_scale_status blockers lack check records: {missing_checks}")


def _validate_decision_supersession(decisions: Sequence[Mapping[str, Any]]) -> None:
    """Validate the inverse meaning of the one-way decision supersedes edge."""

    decision_by_id = {str(record["id"]): record for record in decisions}
    successors_by_decision: dict[str, list[str]] = {}
    for decision in decisions:
        successor_id = str(decision["id"])
        for raw_target_id in decision["supersedes"]:
            target_id = str(raw_target_id)
            target = decision_by_id.get(target_id)
            if target is None:
                raise KnowledgeError(f"{successor_id} supersedes missing decision {target_id}")
            if target_id == successor_id:
                raise KnowledgeError(f"{successor_id} cannot supersede itself")
            if target["status"] == "current":
                raise KnowledgeError(
                    f"{successor_id} cannot supersede active decision {target_id}"
                )
            successors_by_decision.setdefault(target_id, []).append(successor_id)

    for decision in decisions:
        decision_id = str(decision["id"])
        if decision["status"] == "superseded" and decision_id not in successors_by_decision:
            raise KnowledgeError(
                f"{decision_id} status=superseded has no inverse supersedes edge"
            )

def _validate_model(model: KnowledgeModel) -> None:
    root = model.root
    validators = {
        name: _compile_schema_validator(root, relpath)
        for name, relpath in SCHEMA_RELPATHS.items()
    }
    _validate_with_validator(
        validators["current_state"],
        model.current_state,
        CURRENT_STATE_RELPATH,
    )
    _validate_with_validator(validators["dossiers"], model.dossiers, DOSSIERS_RELPATH)
    _validate_with_validator(
        validators["backfill_triage"],
        model.backfill_triage,
        BACKFILL_TRIAGE_RELPATH,
    )
    _validate_with_validator(validators["terminology"], model.terminology, TERMINOLOGY_RELPATH)
    _validate_with_validator(validators["topics"], model.topics, TOPICS_RELPATH)
    _validate_with_validator(
        validators["knowledge_census"],
        model.knowledge_census,
        KNOWLEDGE_CENSUS_RELPATH,
    )
    for index, claim in enumerate(model.claims, start=1):
        _validate_with_validator(validators["claim"], claim, f"{CLAIMS_RELPATH}:{index}")
    for index, decision in enumerate(model.decisions, start=1):
        _validate_with_validator(
            validators["decision"],
            decision,
            f"{DECISIONS_RELPATH}:{index}",
        )
    for index, review in enumerate(model.backfill_reviews, start=1):
        _validate_with_validator(
            validators["backfill_review"],
            review,
            f"{BACKFILL_REVIEWS_RELPATH}:{index}",
        )

    _ensure_unique(model.claims, "id", "claim id")
    _ensure_unique(model.decisions, "id", "decision id")
    _ensure_unique(model.decisions, "external_decision_id", "external decision id")
    _ensure_unique(model.dossiers["records"], "id", "dossier id")
    _ensure_unique(model.dossiers["records"], "path", "dossier path")
    _ensure_unique(model.backfill_reviews, "id", "backfill review id")
    _ensure_unique(model.backfill_triage["groups"], "id", "backfill triage group id")
    _ensure_unique(model.terminology["records"], "id", "term id")
    _ensure_unique(model.topics["records"], "id", "topic id")

    claim_by_id = model.claim_by_id
    decision_by_id = model.decision_by_id
    dossier_by_id = model.dossier_by_id

    _validate_representation_mapping(model.current_state)
    decision_register = _require_mapping(
        model.current_state["decision_register"],
        "current_state.decision_register",
    )
    if decision_register["path"] != DECISIONS_RELPATH:
        raise KnowledgeError(
            f"current_state.decision_register.path must be {DECISIONS_RELPATH!r}"
        )
    if decision_register["non_authorizing"] is not True:
        raise KnowledgeError("current_state decision register must remain non-authorizing")

    for claim in model.claims:
        claim_id = str(claim["id"])
        for dependency in claim["dependencies"]:
            if dependency not in claim_by_id:
                raise KnowledgeError(f"{claim_id} references missing dependency {dependency}")
            if dependency == claim_id:
                raise KnowledgeError(f"{claim_id} cannot depend on itself")
        for superseded in claim["supersedes"]:
            if superseded not in claim_by_id:
                raise KnowledgeError(f"{claim_id} supersedes missing claim {superseded}")
            if superseded == claim_id:
                raise KnowledgeError(f"{claim_id} cannot supersede itself")
        for dossier_id in claim["dossier_ids"]:
            if dossier_id not in dossier_by_id:
                raise KnowledgeError(f"{claim_id} references missing dossier {dossier_id}")
        _validate_evidence(root, claim["evidence"], claim_id, model.tracked_paths)
        _validate_claim_authority(model, claim)
        _validate_record_dossier_links(model, claim, label=claim_id)
        _validate_separation_profile(claim)
        _validate_validity_profile(claim)

    _validate_decision_supersession(model.decisions)
    for decision in model.decisions:
        decision_id = str(decision["id"])
        for dossier_id in decision["dossier_ids"]:
            if dossier_id not in dossier_by_id:
                raise KnowledgeError(f"{decision_id} references missing dossier {dossier_id}")
        _validate_evidence(root, decision["evidence"], decision_id, model.tracked_paths)
        _validate_decision_authority_source(model, decision)
        _validate_record_dossier_links(model, decision, label=decision_id)

    review_by_id = model.backfill_review_by_id
    current_review_by_dossier: dict[str, str] = {}
    for review in model.backfill_reviews:
        review_id = str(review["id"])
        dossier_id = str(review["dossier_id"])
        for superseded in review["supersedes"]:
            target = review_by_id.get(str(superseded))
            if target is None:
                raise KnowledgeError(f"{review_id} supersedes missing review {superseded}")
            if superseded == review_id:
                raise KnowledgeError(f"{review_id} cannot supersede itself")
            if str(target["dossier_id"]) != dossier_id:
                raise KnowledgeError(f"{review_id} cannot supersede review {superseded} from another dossier")
        if review["status"] == "current":
            previous = current_review_by_dossier.get(dossier_id)
            if previous is not None:
                raise KnowledgeError(f"dossier {dossier_id} has two current backfill reviews: {previous}, {review_id}")
            current_review_by_dossier[dossier_id] = review_id
        _validate_backfill_review(model, review)

    successors_by_claim: dict[str, list[str]] = {}
    for claim in model.claims:
        successor_id = str(claim["id"])
        for target_id in claim["supersedes"]:
            target = claim_by_id[str(target_id)]
            if target["status"] not in {"historical", "refuted", "superseded"}:
                raise KnowledgeError(
                    f"{successor_id} cannot supersede active claim {target_id} with status={target['status']}"
                )
            successors_by_claim.setdefault(str(target_id), []).append(successor_id)
    for claim in model.claims:
        claim_id = str(claim["id"])
        if claim["status"] == "superseded" and claim_id not in successors_by_claim:
            raise KnowledgeError(f"{claim_id} status=superseded has no inverse supersedes edge")
        for successor_id in successors_by_claim.get(claim_id, []):
            if claim_by_id[successor_id]["status"] in {"refuted", "superseded"}:
                raise KnowledgeError(
                    f"{claim_id} is replaced by non-reusable successor {successor_id}"
                )

    _assert_acyclic(model.claims, "dependencies", "claim dependency graph")
    _assert_acyclic(model.claims, "supersedes", "claim supersession graph")
    _assert_acyclic(model.decisions, "supersedes", "decision supersession graph")
    _assert_acyclic(model.backfill_reviews, "supersedes", "backfill review supersession graph")

    active_slots: dict[str, str] = {}
    for claim in model.claims:
        if claim["status"] not in ACTIVE_CLAIM_STATUSES or not claim.get("slot"):
            continue
        slot = str(claim["slot"])
        if slot in active_slots:
            raise KnowledgeError(
                f"active singleton slot {slot!r} is occupied by both {active_slots[slot]} and {claim['id']}"
            )
        active_slots[slot] = str(claim["id"])
    missing_slots = sorted(set(model.current_state["required_active_slots"]) - set(active_slots))
    if missing_slots:
        raise KnowledgeError(f"required active claim slots are missing: {missing_slots}")

    selected_claim_ids: list[str] = []
    section_ids: set[str] = set()
    for section in model.current_state["sections"]:
        section_id = str(section["id"])
        if section_id in section_ids:
            raise KnowledgeError(f"duplicate CURRENT section id: {section_id}")
        section_ids.add(section_id)
        for claim_id in section["claim_ids"]:
            if claim_id not in claim_by_id:
                raise KnowledgeError(f"CURRENT section references missing claim {claim_id}")
            claim = claim_by_id[claim_id]
            if claim["status"] not in ACTIVE_CLAIM_STATUSES:
                raise KnowledgeError(f"CURRENT selects non-active claim {claim_id} with status {claim['status']}")
            selected_claim_ids.append(claim_id)
    if len(selected_claim_ids) != len(set(selected_claim_ids)):
        raise KnowledgeError("the same claim is selected by more than one CURRENT section")

    for decision_id in model.current_state["featured_decision_ids"]:
        if decision_id not in decision_by_id:
            raise KnowledgeError(f"CURRENT references missing decision {decision_id}")
        if decision_by_id[decision_id]["status"] != "current":
            raise KnowledgeError(f"CURRENT features non-current decision {decision_id}")

    for index, authority in enumerate(model.current_state["authority_sources"]):
        _validate_path(
            root,
            str(authority["path"]),
            label=f"authority_sources[{index}].path",
        )

    for key, relpath in model.current_state["generated_outputs"].items():
        _normalise_relpath(str(relpath), label=f"generated_outputs.{key}")

    observed, _missing_optional_roots = _inventory_children(root, model.current_state)
    registry_paths: set[str] = set()
    tracked_registry_paths: set[str] = set()
    for record in model.dossiers["records"]:
        dossier_id = str(record["id"])
        path = _normalise_relpath(str(record["path"]), label=f"{dossier_id}.path")
        spec = _root_spec_for_record(path, model.current_state)
        if spec is None:
            raise KnowledgeError(f"{dossier_id}.path is not a direct child of an inventory root: {path}")
        expected_tracked_state = str(spec["tracked_state"])
        if record["tracked_state"] != expected_tracked_state:
            raise KnowledgeError(f"{dossier_id}.tracked_state must be {expected_tracked_state!r} for {path}")
        optional = record["tracked_state"] == "local_optional"
        _validate_path(root, path, label=f"{dossier_id}.path", optional=optional)

        entry = record["entry_file"]
        if entry is not None:
            entry_path = _validate_path(
                root,
                str(entry),
                label=f"{dossier_id}.entry_file",
                optional=optional,
                require_file=True,
            )
            path_obj = root / path
            if path_obj.exists() and path_obj.is_dir() and (root / entry_path).exists():
                try:
                    (root / entry_path).relative_to(path_obj)
                except ValueError as exc:
                    raise KnowledgeError(f"{dossier_id}.entry_file must be inside its dossier directory") from exc
            elif (root / path).exists() and (root / path).is_file() and entry_path != path:
                raise KnowledgeError(f"note dossier {dossier_id} must use path as entry_file")
        elif record["kind"] != "directory":
            raise KnowledgeError(f"note dossier {dossier_id} requires an entry_file")

        _validate_dossier_portability(model, record)
        _validate_dossier_workflow(model, record)
        registry_paths.add(path)
        if spec["availability"] == "required":
            tracked_registry_paths.add(path)

    observed_paths = set(observed)
    missing = sorted(observed_paths - registry_paths)
    stale_required = sorted(tracked_registry_paths - observed_paths)
    if missing or stale_required:
        details: list[str] = []
        if missing:
            details.append("unregistered=" + ", ".join(missing))
        if stale_required:
            details.append("stale_required=" + ", ".join(stale_required))
        raise KnowledgeError(
            "dossier inventory drift; run build_knowledge_docs.py --refresh-dossiers --write: " + "; ".join(details)
        )

    _validate_backfill_triage(model)
    _validate_terminology(model)
    _validate_topics(model)
    _validate_knowledge_census(model)
    _validate_machine_sources(model)


def load_model(root: Path = ROOT) -> KnowledgeModel:
    current_state = _read_json(root, CURRENT_STATE_RELPATH)
    if not isinstance(current_state, dict):
        raise KnowledgeError(f"{CURRENT_STATE_RELPATH} root must be an object")
    claims = _read_jsonl(root, CLAIMS_RELPATH)
    decisions = _read_jsonl(root, DECISIONS_RELPATH)
    backfill_reviews = _read_jsonl(root, BACKFILL_REVIEWS_RELPATH)
    dossiers = _read_json(root, DOSSIERS_RELPATH)
    backfill_triage = _read_json(root, BACKFILL_TRIAGE_RELPATH)
    terminology = _read_json(root, TERMINOLOGY_RELPATH)
    topics = _read_json(root, TOPICS_RELPATH)
    knowledge_census = _read_json(root, KNOWLEDGE_CENSUS_RELPATH)
    for relpath, payload in (
        (DOSSIERS_RELPATH, dossiers),
        (BACKFILL_TRIAGE_RELPATH, backfill_triage),
        (TERMINOLOGY_RELPATH, terminology),
        (TOPICS_RELPATH, topics),
        (KNOWLEDGE_CENSUS_RELPATH, knowledge_census),
    ):
        if not isinstance(payload, dict):
            raise KnowledgeError(f"{relpath} root must be an object")
    machine_sources = _load_machine_sources(root, current_state)
    tracked_paths = _load_git_tracked_paths(root)
    model = KnowledgeModel(
        root=root,
        current_state=current_state,
        claims=claims,
        decisions=decisions,
        dossiers=dossiers,
        backfill_reviews=backfill_reviews,
        backfill_triage=backfill_triage,
        terminology=terminology,
        topics=topics,
        knowledge_census=knowledge_census,
        machine_sources=machine_sources,
        tracked_paths=tracked_paths,
    )
    _validate_model(model)
    return model


def _source_digest(model: KnowledgeModel) -> str:
    relpaths = [
        CURRENT_STATE_RELPATH,
        CLAIMS_RELPATH,
        DECISIONS_RELPATH,
        DOSSIERS_RELPATH,
        BACKFILL_REVIEWS_RELPATH,
        BACKFILL_TRIAGE_RELPATH,
        TERMINOLOGY_RELPATH,
        TOPICS_RELPATH,
        KNOWLEDGE_CENSUS_RELPATH,
        GENERATOR_RELPATH,
        *SCHEMA_RELPATHS.values(),
        *model.current_state["sources"].values(),
    ]
    digest = hashlib.sha256()
    digest.update(f"generator-version:{GENERATOR_VERSION}\n".encode())
    for relpath in sorted(set(str(item) for item in relpaths)):
        digest.update(relpath.encode("utf-8"))
        digest.update(b"\0")
        digest.update((model.root / relpath).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _md_link(root: Path, target_relpath: str, from_relpath: str, label: str | None = None) -> str:
    start = (root / from_relpath).parent
    target = root / target_relpath
    relative = os.path.relpath(target, start=start).replace(os.sep, "/")
    text = label if label is not None else target_relpath
    return f"[{text}](<{relative}>)"


def _join_values(values: Sequence[str]) -> str:
    return "；".join(str(value) for value in values)


def _truncate(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _render_evidence(
    root: Path,
    evidence: Sequence[Mapping[str, Any]],
    from_relpath: str,
) -> str:
    rendered: list[str] = []
    for item in evidence:
        path = str(item["path"])
        role = str(item["role"])
        storage = str(item.get("storage", "git_tracked"))
        suffix_by_storage = {
            "git_tracked": "",
            "workspace_untracked": "（工作区可选工件）",
            "external_root": "（仓外可选证据）",
        }
        suffix = suffix_by_storage.get(storage, "（未知存储状态）")
        rendered.append(f"{_md_link(root, path, from_relpath, path)}〔{role}〕{suffix}")
    return "；".join(rendered)


def _render_claim(
    model: KnowledgeModel,
    claim: Mapping[str, Any],
    from_relpath: str,
    *,
    heading_level: int = 3,
) -> list[str]:
    heading = "#" * heading_level
    lines = [
        f"{heading} {claim['title']}",
        "",
        f"- **Claim ID：** `{claim['id']}`",
        f"- **状态：** `{claim['status']}`",
        f"- **权威层：** `{claim['authority']}`",
        f"- **权威依据：** `{claim['authority_basis']['basis_type']}`",
        f"- **表示角色：** `{claim['representation_class']}`",
        f"- **权威作用：** `{claim['authority_effect']}`",
        f"- **更新时间：** `{claim['updated_at']}`",
        "",
        str(claim["statement"]),
    ]
    fields = (
        ("适用范围", claim["scope"]),
        ("成立前提", claim["premises"]),
        ("直接后果", claim["consequences"]),
        ("明确不推出", claim["does_not_imply"]),
        ("依赖 claim", claim["dependencies"]),
        ("取代 claim", claim["supersedes"]),
    )
    for title, values in fields:
        if values:
            lines.extend(("", f"- **{title}：** {_join_values(values)}"))
    basis = claim["authority_basis"]
    lines.extend(("", f"- **权威源：** {_join_values(basis['source_paths'])}"))
    if basis.get("verification_id"):
        lines.append(f"- **机器验收器：** `{basis['verification_id']}`")
    if claim["decision_ids"]:
        lines.append(f"- **关联决定：** {_join_values(claim['decision_ids'])}")
    profile = claim.get("reasoning_profile")
    if isinstance(profile, dict):
        lines.extend(
            (
                "",
                f"- **条件处置：** `{profile['condition_disposition']}`",
                f"- **操作效果：** {_join_values(profile['operational_effects'])}",
                f"- **一般性：** `{profile['generality']}`",
                f"- **solver 关系：** `{profile['solver_relation']}`",
                f"- **通用传播不能完成分离的证据：** `{profile['generic_propagation_evidence']}`",
                f"- **发现方式：** {_join_values(profile['discovery_modes'])}",
            )
        )
        if profile.get("note"):
            lines.append(f"- **分类注：** {profile['note']}")
    derivation = claim.get("derivation_profile")
    if isinstance(derivation, dict):
        lines.extend(
            (
                "",
                f"- **推导角色：** `{derivation['role']}`",
                f"- **数学推导族：** {_join_values(derivation['families'])}",
                f"- **验证方式：** {_join_values(derivation['verification_modes'])}",
            )
        )
        if derivation.get("note"):
            lines.append(f"- **推导注：** {derivation['note']}")
    separation = claim.get("separation_profile")
    if isinstance(separation, dict):
        lines.extend(
            (
                "",
                f"- **目标阶段：** `{separation['target_stage']}`",
                f"- **候选来源：** `{separation['candidate_source']}`",
                f"- **选择方式：** {_join_values(separation['selection_modes'])}",
                f"- **验证方式：** {_join_values(separation['validation_modes'])}",
                f"- **完备性：** `{separation['completeness']}`",
                f"- **消费方式：** {_join_values(separation['consumption_modes'])}",
                f"- **基线比较：** `{separation['baseline_comparison']}`",
            )
        )
        if separation.get("note"):
            lines.append(f"- **分离注：** {separation['note']}")
    validity = claim.get("validity_profile")
    if isinstance(validity, dict):
        lines.extend(
            (
                "",
                f"- **有效性事件：** `{validity['event_type']}`",
                f"- **受影响层：** {_join_values(validity['affected_layers'])}",
                f"- **判定依据：** {_join_values(validity['basis'])}",
                f"- **复用策略：** `{validity['reuse_policy']}`",
                f"- **修复状态：** `{validity['repair_state']}`",
                f"- **时间作用域：** `{validity['temporal_scope']}`",
            )
        )
        if validity.get("note"):
            lines.append(f"- **有效性注：** {validity['note']}")
    lines.extend(("", "- **证据：** " + _render_evidence(model.root, claim["evidence"], from_relpath), ""))
    return lines


def _render_decision(
    model: KnowledgeModel,
    decision: Mapping[str, Any],
    from_relpath: str,
    *,
    heading_level: int = 3,
) -> list[str]:
    heading = "#" * heading_level
    external = decision.get("external_decision_id")
    lines = [
        f"{heading} {decision['title']}",
        "",
        f"- **Decision ID：** `{decision['id']}`",
        f"- **状态：** `{decision['status']}`",
        f"- **登记角色：** `non_authorizing={str(decision['non_authorizing']).lower()}`",
        f"- **权威作用：** `{decision['authority_effect']}`",
        f"- **决定人：** `{decision['decided_by']}`",
        f"- **决定日期：** `{decision['decided_at']}`",
    ]
    if external:
        lines.append(f"- **外部决定 ID：** `{external}`")
    lines.append(f"- **外部权威源：** `{decision['authority_source']['path']}`")
    lines.extend(("", str(decision["statement"])))
    fields = (
        ("适用范围", decision["scope"]),
        ("直接后果", decision["consequences"]),
        ("明确不推出", decision["does_not_imply"]),
        ("取代决定", decision["supersedes"]),
    )
    for title, values in fields:
        if values:
            lines.extend(("", f"- **{title}：** {_join_values(values)}"))
    lines.extend(("", "- **证据：** " + _render_evidence(model.root, decision["evidence"], from_relpath), ""))
    return lines


def _canonical_summary(model: KnowledgeModel) -> dict[str, Any]:
    canonical = model.machine_sources["canonical_rules"]
    globals_block = canonical["globals"]
    return {
        "version": canonical["metadata"]["version"],
        "width": globals_block["grid"]["width"],
        "height": globals_block["grid"]["height"],
        "objective": globals_block["empty_rectangle"]["objective"],
        "min_side": globals_block["empty_rectangle"]["min_side_admissibility"],
        "emptiness": globals_block["empty_rectangle"]["emptiness"],
        "mandatory_count": len(model.machine_sources["mandatory_instances"]),
    }


def render_current(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["current"])
    gate = model.machine_sources["phase_gate"]
    owner_state = gate["owner_manual_state"]
    owner_decision = gate["owner_manual_decision"]
    next_phase = gate["next_phase_entry"]
    obligations = model.machine_sources["proof_obligations"]
    exact = model.machine_sources["exact_full_scale_status"]
    canonical = _canonical_summary(model)

    lines: list[str] = [
        f"# {model.current_state['title']}",
        "",
        "> 本页由 `devtools/build_knowledge_docs.py` 自动生成，禁止手工修改。",
        "> 机器状态从冻结规则、义务、gate 与 exact-status 文件直接读取；研究结论从稳定 ID 账本投影。",
        f"> 账本人工审阅日：`{model.current_state['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "## 权威边界",
        "",
        "本页只是查询入口，不会高于它引用的源。不同源各自管辖不同问题，发生冲突时回到对应源文件：",
        "",
    ]
    for index, authority in enumerate(model.current_state["authority_sources"], start=1):
        lines.append(f"{index}. {_md_link(model.root, str(authority['path']), relpath)}：{authority['role']}")

    lines.extend(
        (
            "",
            "## 认证问题面",
            "",
            "| 项目 | 当前机器值 |",
            "|---|---|",
            f"| canonical rules 版本 | `{canonical['version']}` |",
            f"| 网格 | `{canonical['width']}×{canonical['height']}` |",
            f"| 目标 | `{canonical['objective']}` |",
            f"| 候选最短边门槛 | `{canonical['min_side']}` |",
            f"| 空矩形语义 | `{canonical['emptiness']}` |",
            f"| mandatory 实例数 | `{canonical['mandatory_count']}` |",
            f"| 机器源 | {_md_link(model.root, model.current_state['sources']['canonical_rules'], relpath)}；"
            f"{_md_link(model.root, model.current_state['sources']['mandatory_instances'], relpath)} |",
            "",
            "## 阶段门与证明义务",
            "",
            f"- **P1.2 gate：** `{gate['status']}`，机器更新时间 `{gate['updated_at']}`，"
            f"review anchor `{gate['current_review_anchor']}`。",
            f"- **当前 owner 决定：** `{owner_decision['decision_id']}`，"
            f"由 `{owner_decision['decided_by']}` 于 `{owner_decision['decided_at']}` 作出。",
            f"- **下一阶段入口：** `{next_phase['phase']}`，`allowed={str(next_phase['allowed']).lower()}`。",
            f"- **clean-review 计数：** `{owner_state['owner_clean_count_status']}`；仓库不从 receipt 推导计数，"
            "receipt 也不能打开下一阶段。",
            f"- **P1.2 义务集：** `{obligations['status']}`，更新时间 `{obligations['updated_at']}`，"
            f"共 `{len(obligations['obligations'])}` 条，anchor `{obligations['review_anchor']}`。",
            f"- **机器源：** {_md_link(model.root, model.current_state['sources']['phase_gate'], relpath)}；"
            f"{_md_link(model.root, model.current_state['sources']['proof_obligations'], relpath)}。",
            "",
            "## Checked-in durable exact 状态快照",
            "",
            "本段逐字读取仓内 resolver 输出，不表示生成知识页时重新运行过 resolver；必须连同它自己的生成时间阅读。",
            "",
            f"- **状态：** `{exact['status']}`。",
            f"- **best_certified_result：** `{json.dumps(exact['best_certified_result'], ensure_ascii=False)}`。",
            f"- **当前 hash 可续跑：** `{str(exact['resume_compatible_with_current_hashes']).lower()}`。",
            f"- **阻断检查：** `{len(exact['blocking_check_ids'])}` 项。",
            f"- **checked-in resolver 时间：** `{exact.get('metadata', {}).get('generated_at', 'unknown')}`。",
            f"- **机器源：** {_md_link(model.root, model.current_state['sources']['exact_full_scale_status'], relpath)}。",
            "",
        )
    )

    claim_by_id = model.claim_by_id
    for section in model.current_state["sections"]:
        lines.extend((f"## {section['title']}", ""))
        for claim_id in section["claim_ids"]:
            lines.extend(_render_claim(model, claim_by_id[claim_id], relpath))

    if model.current_state["featured_decision_ids"]:
        lines.extend(("## 当前 owner / 治理决定", ""))
        decision_by_id = model.decision_by_id
        for decision_id in model.current_state["featured_decision_ids"]:
            lines.extend(_render_decision(model, decision_by_id[decision_id], relpath))

    coverage = model.current_state["coverage"]
    lines.extend(
        (
            "## 覆盖范围与欠账",
            "",
            f"- **dossier 目录覆盖：** {coverage['dossiers']}",
            f"- **claim 覆盖：** {coverage['claims']}",
            f"- **历史 claim 回填：** {coverage['historical_claim_backfill']}",
            "",
            "完整 claim、decision 与 evidence package 目录见 "
            + _md_link(
                model.root,
                str(model.current_state["generated_outputs"]["catalog"]),
                relpath,
                "CATALOG",
            )
            + "；推理分类与历史回填进度见 "
            + _md_link(
                model.root,
                str(model.current_state["generated_outputs"]["reasoning"]),
                relpath,
                "REASONING_LEDGER",
            )
            + "；历史反例、语义更正、实现失效与重验谱系见 "
            + _md_link(
                model.root,
                str(model.current_state["generated_outputs"]["validity"]),
                relpath,
                "VALIDITY_LEDGER",
            )
            + "；语义审阅、可用性核对与长尾分诊闭包见 "
            + _md_link(
                model.root,
                str(model.current_state["generated_outputs"]["backfill"]),
                relpath,
                "BACKFILL_LEDGER",
            )
            + "；按稳定主题坐标查询见 "
            + _md_link(
                model.root,
                str(model.current_state["generated_outputs"]["topics"]),
                relpath,
                "TOPIC_INDEX",
            )
            + "；规范术语与别名见 "
            + _md_link(
                model.root,
                str(model.current_state["generated_outputs"]["terminology"]),
                relpath,
                "TERMINOLOGY",
            )
            + "；当前开放问题见 "
            + _md_link(
                model.root,
                str(model.current_state["generated_outputs"]["open_questions"]),
                relpath,
                "OPEN_QUESTIONS",
            )
            + "；按问题进入项目见 "
            + _md_link(model.root, "docs/START_HERE.md", relpath, "START_HERE")
            + "。",
            "",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _dossier_sort_key(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("date") or "0000-00-00"),
        str(record["title"]).casefold(),
        str(record["path"]),
    )


def _dossier_entry_cell(model: KnowledgeModel, record: Mapping[str, Any], relpath: str) -> str:
    title = str(record["title"]).replace("|", "\\|")
    entry_file = record["entry_file"]
    if entry_file is None:
        entry = f"{title}<br><code>{record['path']}</code>"
    else:
        entry = _md_link(model.root, str(entry_file), relpath, title)
    summary = _truncate(str(record["summary"]), 160).replace("|", "\\|")
    return entry if not summary else f"{entry}<br>{summary}"


def _render_dossier_table(
    model: KnowledgeModel,
    records: Sequence[Mapping[str, Any]],
    relpath: str,
) -> list[str]:
    lines = [
        "| Dossier ID | 日期 | 标题 / 入口 | topics | lifecycle | relevance |",
        "|---|---|---|---|---|---|",
    ]
    for record in sorted(records, key=_dossier_sort_key, reverse=True):
        date_value = record["date"] or "未标日期"
        topics = ", ".join(f"`{topic}`" for topic in record["topics"])
        lines.append(
            f"| `{record['id']}` | `{date_value}` | {_dossier_entry_cell(model, record, relpath)} | "
            f"{topics} | `{record['lifecycle']}` | `{record['relevance']}` |"
        )
    return lines


def _dossier_backlinks(
    model: KnowledgeModel,
) -> dict[str, dict[str, list[str]]]:
    links: dict[str, dict[str, list[str]]] = {
        str(record["id"]): {"claims": [], "decisions": [], "reviews": []} for record in model.dossiers["records"]
    }
    for claim in model.claims:
        for dossier_id in claim["dossier_ids"]:
            links[str(dossier_id)]["claims"].append(str(claim["id"]))
    for decision in model.decisions:
        for dossier_id in decision["dossier_ids"]:
            links[str(dossier_id)]["decisions"].append(str(decision["id"]))
    for review in model.backfill_reviews:
        links[str(review["dossier_id"])]["reviews"].append(str(review["id"]))
    for relation in links.values():
        relation["claims"].sort()
        relation["decisions"].sort()
        relation["reviews"].sort()
    return links


def _catalog_record_links(ids: Sequence[str]) -> str:
    if not ids:
        return "—"
    return "<br>".join(f"[`{item}`](#{item.lower()})" for item in ids)


def render_catalog(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["catalog"])
    records = list(model.dossiers["records"])
    curated_count = sum(record["curation"] == "curated" for record in records)
    current_evidence_count = sum(record["relevance"] == "current_evidence" for record in records)
    tracked_records = [record for record in records if record["tracked_state"] == "tracked"]
    optional_records = [record for record in records if record["tracked_state"] == "local_optional"]
    curated_records = [record for record in records if record["curation"] == "curated"]

    lines: list[str] = [
        "# 项目知识目录",
        "",
        "> 本页由 `devtools/build_knowledge_docs.py` 自动生成，禁止手工修改。",
        f"> 账本人工审阅日：`{model.current_state['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "这里登记稳定 ID。claim 回答“我们知道什么”，decision 回答“谁改变了什么规则或门”，",
        "dossier 回答“原始证据包在哪里”，validity profile 回答“旧结论为何失效、怎样换代、能否复用”。目录不把历史材料自动升级为当前权威。",
        "",
        "## 覆盖概览",
        "",
        f"- claim：`{len(model.claims)}` 条，其中当前 / 开放 "
        f"`{sum(claim['status'] in ACTIVE_CLAIM_STATUSES for claim in model.claims)}` 条，带 validity profile "
        f"`{sum(bool(claim.get('validity_profile')) for claim in model.claims)}` 条。",
        f"- decision：`{len(model.decisions)}` 条。",
        f"- backfill review：`{len(model.backfill_reviews)}` 条，其中 current "
        f"`{sum(review['status'] == 'current' for review in model.backfill_reviews)}` 条。",
        f"- dossier：`{len(records)}` 个，其中 tracked `{len(tracked_records)}` 个、"
        f"local optional `{len(optional_records)}` 个、当前证据标记 `{current_evidence_count}` 个、"
        f"人工精编 `{curated_count}` 个。",
        "- `docs/research/` 的一级目录和一级 Markdown 已全登记；`.artifacts/` 只登记一级目录，"
        "其路径允许在轻量 checkout 中缺失。",
        "",
        "## Claim 索引",
        "",
        "| Claim ID | 标题 | 状态 | 权威层 | 权威作用 |",
        "|---|---|---|---|---|",
    ]
    for claim in sorted(model.claims, key=lambda item: str(item["id"])):
        title = str(claim["title"]).replace("|", "\\|")
        lines.append(
            f"| [`{claim['id']}`](#{str(claim['id']).lower()}) | {title} | `{claim['status']}` | "
            f"`{claim['authority']}` | `{claim['authority_effect']}` |"
        )

    lines.extend(
        (
            "",
            "## Decision 索引",
            "",
            "| Decision ID | 标题 | 状态 | 日期 | 权威作用 |",
            "|---|---|---|---|---|",
        )
    )
    for decision in sorted(model.decisions, key=lambda item: str(item["id"])):
        title = str(decision["title"]).replace("|", "\\|")
        lines.append(
            f"| [`{decision['id']}`](#{str(decision['id']).lower()}) | {title} | "
            f"`{decision['status']}` | `{decision['decided_at']}` | `{decision['authority_effect']}` |"
        )

    topic_counts: dict[str, int] = {}
    for record in records:
        for topic in record["topics"]:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    lines.extend(("", "## Topic 索引", ""))
    for topic, count in sorted(topic_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{topic}`：{count} 个 dossier。")

    backlinks = _dossier_backlinks(model)
    referenced_records = [
        record
        for record in records
        if (
            backlinks[str(record["id"])]["claims"]
            or backlinks[str(record["id"])]["decisions"]
            or backlinks[str(record["id"])]["reviews"]
        )
    ]
    lines.extend(
        (
            "",
            "## Dossier 反向索引",
            "",
            "这里把证据包反向连回使用它的 claim 与 decision，避免目录只有单向指针。",
            "",
            "| Dossier ID | 标题 / 入口 | Claims | Decisions | Backfill reviews |",
            "|---|---|---|---|---|",
        )
    )
    for record in sorted(referenced_records, key=_dossier_sort_key, reverse=True):
        relation = backlinks[str(record["id"])]
        lines.append(
            f"| `{record['id']}` | {_dossier_entry_cell(model, record, relpath)} | "
            f"{_catalog_record_links(relation['claims'])} | "
            f"{_catalog_record_links(relation['decisions'])} | "
            f"{_catalog_record_links(relation['reviews'])} |"
        )

    lines.extend(("", "## 人工精编 dossier", ""))
    lines.extend(_render_dossier_table(model, curated_records, relpath))

    lines.extend(("", "## tracked research dossier 全表", ""))
    lines.extend(_render_dossier_table(model, tracked_records, relpath))

    lines.extend(("", "## local optional artifact root 全表", ""))
    lines.append("这些目录是本机证据入口。缺失不使 checker 失败，但本机一旦出现新的一级目录，就必须登记。")
    lines.append("")
    lines.extend(_render_dossier_table(model, optional_records, relpath))

    lines.extend(("", "## Claim 详情", ""))
    for claim in sorted(model.claims, key=lambda item: str(item["id"])):
        lines.append(f'<a id="{str(claim["id"]).lower()}"></a>')
        lines.append("")
        lines.extend(_render_claim(model, claim, relpath, heading_level=3))

    lines.extend(("", "## Decision 详情", ""))
    for decision in sorted(model.decisions, key=lambda item: str(item["id"])):
        lines.append(f'<a id="{str(decision["id"]).lower()}"></a>')
        lines.append("")
        lines.extend(_render_decision(model, decision, relpath, heading_level=3))

    lines.extend(("", "## Backfill review 详情", ""))
    for review in sorted(model.backfill_reviews, key=lambda item: str(item["id"])):
        lines.append(f'<a id="{str(review["id"]).lower()}"></a>')
        lines.extend(
            (
                "",
                f"### {review['id']}",
                "",
                f"- **Dossier：** `{review['dossier_id']}`",
                f"- **状态 / 结果：** `{review['status']}` / `{review['outcome']}`",
                f"- **审阅日 / 范围：** `{review['reviewed_at']}` / `{review['review_scope']}`",
                f"- **提炼 claim：** {_join_values(review['claim_ids']) or '—'}",
                f"- **未决项：** {_join_values(review['unresolved']) or '—'}",
                "",
                str(review["summary"]),
                "",
            )
        )

    lines.extend(
        (
            "## 维护命令",
            "",
            "```bash",
            ".venv/bin/python devtools/build_knowledge_docs.py --refresh-dossiers --write",
            ".venv/bin/python devtools/check_knowledge_docs.py",
            "```",
            "",
            "refresh 只自动补目录和更新 `auto_indexed` 元数据，不会删除缺失的 local artifact 记录，",
            "也不会覆盖 `curated` 条目的人工字段。",
            "",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _count_profile_values(
    claims: Sequence[Mapping[str, Any]],
    field: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        profile = claim.get("reasoning_profile")
        if not isinstance(profile, dict):
            continue
        raw = profile[field]
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _count_derivation_values(
    claims: Sequence[Mapping[str, Any]],
    field: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        profile = claim.get("derivation_profile")
        if not isinstance(profile, dict):
            continue
        raw = profile[field]
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _count_separation_values(
    claims: Sequence[Mapping[str, Any]],
    field: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        profile = claim.get("separation_profile")
        if not isinstance(profile, dict):
            continue
        raw = profile[field]
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _count_validity_values(
    claims: Sequence[Mapping[str, Any]],
    field: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        profile = claim.get("validity_profile")
        if not isinstance(profile, dict):
            continue
        value = profile[field]
        values = value if isinstance(value, list) else [value]
        for item in values:
            key = str(item)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _render_count_line(label: str, counts: Mapping[str, int]) -> str:
    values = "；".join(f"`{key}`={value}" for key, value in sorted(counts.items()))
    return f"- **{label}：** {values or '—'}"


def _catalog_claim_links(model: KnowledgeModel, claim_ids: Sequence[str]) -> str:
    if not claim_ids:
        return "—"
    return "<br>".join(f"[`{claim_id}`](<{_md_link_target_for_anchor(model, claim_id)}>)" for claim_id in claim_ids)


def render_reasoning_ledger(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["reasoning"])
    profiled = [claim for claim in model.claims if isinstance(claim.get("reasoning_profile"), dict)]
    derived = [claim for claim in model.claims if isinstance(claim.get("derivation_profile"), dict)]
    separated = [claim for claim in model.claims if isinstance(claim.get("separation_profile"), dict)]
    current_reviews = [review for review in model.backfill_reviews if review["status"] == "current"]
    current_review_by_dossier = {str(review["dossier_id"]): review for review in current_reviews}
    tracked_current = [
        record
        for record in model.dossiers["records"]
        if record["tracked_state"] == "tracked" and record["relevance"] == "current_evidence"
    ]
    reviewed_tracked_current = [record for record in tracked_current if str(record["id"]) in current_review_by_dossier]
    formal_generic = [
        claim for claim in profiled if claim["reasoning_profile"]["generic_propagation_evidence"] == "formal"
    ]
    experimental_generic = [
        claim for claim in profiled if claim["reasoning_profile"]["generic_propagation_evidence"] == "experimental_only"
    ]

    lines: list[str] = [
        "# 推理结论与知识回填账本",
        "",
        "> 本页由 `devtools/build_knowledge_docs.py` 自动生成，禁止手工修改。",
        f"> 账本人工审阅日：`{model.current_state['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "本页把推理条件、操作效果、数学推导、选择/验证/消费机制与通用传播证据分开；历史结论为何失效、怎样换代和何时可复用则单列到 VALIDITY_LEDGER。",
        "`reasoning_profile` 描述操作效果，`derivation_profile` 描述证明角色、数学族和验证方式，`separation_profile` 描述候选来源、选择、验证、完备性和消费落点，`validity_profile` 描述反例、语义更正、实现失效、归因修正与重验；真正的关系图由 claim 的 `dependencies` 与 `supersedes` 连接。分类字段不会把 research-only 结论提升为规则、owner 决定或 production authority。",
        "",
        "## 当前可回答的问题",
        "",
        f"- 带 `reasoning_profile` 的 claim：`{len(profiled)}` 条。",
        f"- 带 `derivation_profile` 的 claim：`{len(derived)}` 条。",
        f"- 带 `separation_profile` 的 claim：`{len(separated)}` 条。",
        f"- 带 `validity_profile` 的 claim：`{sum(bool(claim.get('validity_profile')) for claim in model.claims)}` 条；完整谱系见 [VALIDITY_LEDGER](VALIDITY_LEDGER.md)。",
        f"- 已正式证明“通用传播不能完成分离”的 claim：`{len(formal_generic)}` 条。",
        f"- 只有实验性通用传播对照证据的 claim：`{len(experimental_generic)}` 条。",
        "- 因此，在本批已审材料中，尚不能把“领域策略有效”直接改写成“CP-SAT 通用传播原则上不能做到”。前者已有多种实例，后者仍需要明确的传播系统、搜索预算和不可分离证明。",
        "",
        "## 回填覆盖",
        "",
        f"- current backfill review：`{len(current_reviews)}` 个 dossier。",
        f"- tracked current-evidence dossier：`{len(reviewed_tracked_current)}/{len(tracked_current)}` 已有 current review。",
        f"- 全 dossier inventory：`{len(current_reviews)}/{len(model.dossiers['records'])}` 已有 current review。此分母只表示目录规模，不表示未审包都含有可复用 claim。",
        "- 当前优先覆盖承重 current-evidence、高价值数学推导链、选择/分离机制，以及历史反例、语义更正、实现失效和重验边界；术语归一与长尾材料仍待后续批次。",
        "",
        "## 操作分类分布",
        "",
        _render_count_line("条件处置", _count_profile_values(profiled, "condition_disposition")),
        _render_count_line("操作效果", _count_profile_values(profiled, "operational_effects")),
        _render_count_line("一般性", _count_profile_values(profiled, "generality")),
        _render_count_line("solver 关系", _count_profile_values(profiled, "solver_relation")),
        _render_count_line(
            "通用传播不可替代证据",
            _count_profile_values(profiled, "generic_propagation_evidence"),
        ),
        _render_count_line("发现方式", _count_profile_values(profiled, "discovery_modes")),
        "",
        "## 推导结构分布",
        "",
        _render_count_line("推导角色", _count_derivation_values(derived, "role")),
        _render_count_line("数学推导族", _count_derivation_values(derived, "families")),
        _render_count_line("验证方式", _count_derivation_values(derived, "verification_modes")),
        "",
        "## 选择、分离与消费结构分布",
        "",
        _render_count_line("目标阶段", _count_separation_values(separated, "target_stage")),
        _render_count_line("候选来源", _count_separation_values(separated, "candidate_source")),
        _render_count_line("选择方式", _count_separation_values(separated, "selection_modes")),
        _render_count_line("候选验证", _count_separation_values(separated, "validation_modes")),
        _render_count_line("完备性", _count_separation_values(separated, "completeness")),
        _render_count_line("消费方式", _count_separation_values(separated, "consumption_modes")),
        _render_count_line("基线比较", _count_separation_values(separated, "baseline_comparison")),
        "",
        "## 已分类 claim",
        "",
        "| Claim | 状态 | 条件处置 | 操作效果 | 一般性 | Solver 关系 | 通用传播证据 |",
        "|---|---|---|---|---|---|---|",
    ]
    for claim in sorted(profiled, key=lambda item: str(item["id"])):
        profile = claim["reasoning_profile"]
        effects = "<br>".join(f"`{value}`" for value in profile["operational_effects"])
        lines.append(
            f"| [`{claim['id']}`](<{_md_link_target_for_anchor(model, claim['id'])}>) | "
            f"`{claim['status']}` | `{profile['condition_disposition']}` | {effects} | "
            f"`{profile['generality']}` | `{profile['solver_relation']}` | "
            f"`{profile['generic_propagation_evidence']}` |"
        )

    lines.extend(
        (
            "",
            "## 选择、分离与消费机制",
            "",
            "这张表刻意把候选发现、候选验证、覆盖完备性和最终消费分开。能够验证 supplied candidate，不等于拥有 autonomous separator；领域策略能排除实例，也不自动证明通用 CP-SAT 传播原则上无法得到相同分离。",
            "",
            "| Claim | 阶段 | 候选来源 | 选择方式 | 验证方式 | 完备性 | 消费方式 | 基线 |",
            "|---|---|---|---|---|---|---|---|",
        )
    )
    for claim in sorted(separated, key=lambda item: str(item["id"])):
        profile = claim["separation_profile"]
        selection = "<br>".join(f"`{value}`" for value in profile["selection_modes"])
        validation = "<br>".join(f"`{value}`" for value in profile["validation_modes"])
        consumption = "<br>".join(f"`{value}`" for value in profile["consumption_modes"])
        lines.append(
            f"| [`{claim['id']}`](<{_md_link_target_for_anchor(model, claim['id'])}>) | "
            f"`{profile['target_stage']}` | `{profile['candidate_source']}` | {selection} | "
            f"{validation} | `{profile['completeness']}` | {consumption} | "
            f"`{profile['baseline_comparison']}` |"
        )

    lines.extend(
        (
            "",
            "## 数学推导关系",
            "",
            "下表只列直接边。`dependencies` 表示当前 claim 明示依赖的前件，`supersedes` 表示语义换代；数学证明正文仍留在 evidence dossier。",
            "",
            "| Claim | 角色 | 推导族 | 直接依赖 | 取代 | 验证方式 |",
            "|---|---|---|---|---|---|",
        )
    )
    for claim in sorted(derived, key=lambda item: str(item["id"])):
        profile = claim["derivation_profile"]
        families = "<br>".join(f"`{value}`" for value in profile["families"])
        verification = "<br>".join(f"`{value}`" for value in profile["verification_modes"])
        lines.append(
            f"| [`{claim['id']}`](<{_md_link_target_for_anchor(model, claim['id'])}>) | "
            f"`{profile['role']}` | {families} | "
            f"{_catalog_claim_links(model, claim['dependencies'])} | "
            f"{_catalog_claim_links(model, claim['supersedes'])} | {verification} |"
        )

    dossier_by_id = model.dossier_by_id
    lines.extend(
        (
            "",
            "## Dossier 回填审阅记录",
            "",
            "| Review | Dossier | 审阅范围 | 结果 | 提炼 claim | 未决项 |",
            "|---|---|---|---|---|---|",
        )
    )
    for review in sorted(current_reviews, key=lambda item: (str(item["reviewed_at"]), str(item["id"])), reverse=True):
        dossier = dossier_by_id[str(review["dossier_id"])]
        dossier_link = _md_link(model.root, str(dossier["entry_file"] or dossier["path"]), relpath, str(dossier["id"]))
        claims = "<br>".join(f"[`{item}`](<CATALOG.md#{str(item).lower()}>)" for item in review["claim_ids"]) or "—"
        unresolved = "<br>".join(_truncate(str(item), 90).replace("|", "\\|") for item in review["unresolved"]) or "—"
        lines.append(
            f"| `{review['id']}` | {dossier_link} | `{review['review_scope']}` | "
            f"`{review['outcome']}` | {claims} | {unresolved} |"
        )

    lines.extend(
        (
            "",
            "## 字段口径",
            "",
            "- `pre_model_reduction`：在建模或候选枚举前排除一族对象。",
            "- `candidate_filter`：对已定义候选做领域筛选，但不声称已作为 solver constraint 安装。",
            "- `model_constraint`：约束表达进入模型域；它可能正确，也可能只是显式 certification scope。",
            "- `experimental_cut`：只在研究实验中作为 cut 或分离器观察，不能由此推出 production 授权。",
            "- `derivation_profile.role`：区分定义、原子引理、复合定理、账本投影、方法、反例与开放义务；它不替代 claim 的 status 或 authority。",
            "- `derivation_profile.families`：给数学构件稳定主题坐标，不把完整证明复制进账本。",
            "- `derivation_profile.verification_modes`：记录纸面推导、源重算、枚举、证书、对抗复核或 authority admission 等验证路径，不把验证方式误写成命题内容。",
            "- `separation_profile.candidate_source` 与 `selection_modes`：分别回答候选从哪里来、怎样挑选；validator 接受 supplied candidate 不构成候选空间覆盖。",
            "- `separation_profile.validation_modes` 与 `completeness`：分别回答怎样检查候选、检查覆盖到哪里；预算耗尽、未到达或零激活必须保持 `open` / `not_applicable`，不能冒充固定点。",
            "- `separation_profile.consumption_modes`：区分 model omission、pre-model filter、candidate filter、model constraint、objective bound、diagnostic 与 knowledge-only，防止研究结论静默越权进入 production。",
            "- `separation_profile.baseline_comparison`：区分无对照、非识别性观测、受控比较和 formal comparison；它不替代 claim 的 authority 或 evidence。",
            "- `generic_propagation_evidence=formal` 的门槛是：明确指定通用传播系统，并证明它在所述输入族上不能得到目标分离；运行慢、零激活或一次 UNKNOWN 都不够。",
            "",
            "完整 statement、premises、does-not-imply 与 evidence 见 "
            + _md_link(model.root, str(model.current_state["generated_outputs"]["catalog"]), relpath, "CATALOG")
            + "。",
            "",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def render_validity_ledger(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["validity"])
    profiled = [claim for claim in model.claims if isinstance(claim.get("validity_profile"), dict)]
    successor_edges = [
        (str(claim["id"]), str(target))
        for claim in model.claims
        for target in claim["supersedes"]
    ]
    validity_reviews = [
        review
        for review in model.backfill_reviews
        if review["status"] == "current"
        and any(
            isinstance(model.claim_by_id[str(claim_id)].get("validity_profile"), dict)
            for claim_id in review["claim_ids"]
        )
    ]

    lines: list[str] = [
        "# 结论有效性与换代账本",
        "",
        "> 本页由 `devtools/build_knowledge_docs.py` 自动生成，禁止手工修改。",
        f"> 账本人工审阅日：`{model.current_state['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "本页不把所有失败混成一个标签。它区分直接反例、语义替代、作用域修正、实现失效、实验装置失效、归因更正、路线撤回与修复后重验。",
        "`validity_profile` 回答的是一条 claim 在认知历史中的位置；claim 的数学内容、authority 和证据仍以 CATALOG 详情为准。",
        "",
        "## 当前覆盖",
        "",
        f"- 带 `validity_profile` 的 claim：`{len(profiled)}` 条。",
        f"- 显式 `supersedes` 边：`{len(successor_edges)}` 条。",
        f"- `refuted` claim：`{sum(claim['status'] == 'refuted' for claim in model.claims)}` 条。",
        f"- `superseded` claim：`{sum(claim['status'] == 'superseded' for claim in model.claims)}` 条，均必须有反向 successor。",
        f"- current validity review：`{len(validity_reviews)}` 个 dossier。",
        "",
        "## 有效性事件分布",
        "",
        _render_count_line("事件类型", _count_validity_values(profiled, "event_type")),
        _render_count_line("受影响层", _count_validity_values(profiled, "affected_layers")),
        _render_count_line("判定依据", _count_validity_values(profiled, "basis")),
        _render_count_line("复用策略", _count_validity_values(profiled, "reuse_policy")),
        _render_count_line("修复状态", _count_validity_values(profiled, "repair_state")),
        _render_count_line("时间作用域", _count_validity_values(profiled, "temporal_scope")),
        "",
        "## 已分类 claim",
        "",
        "| Claim | 状态 | 事件 | 时间作用域 | 受影响层 | 复用策略 | 修复状态 | 判定依据 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for claim in sorted(profiled, key=lambda item: str(item["id"])):
        profile = claim["validity_profile"]
        layers = "<br>".join(f"`{value}`" for value in profile["affected_layers"])
        basis = "<br>".join(f"`{value}`" for value in profile["basis"])
        lines.append(
            f"| [`{claim['id']}`](<{_md_link_target_for_anchor(model, str(claim['id']), relpath)}>) | "
            f"`{claim['status']}` | `{profile['event_type']}` | `{profile['temporal_scope']}` | "
            f"{layers} | `{profile['reuse_policy']}` | `{profile['repair_state']}` | {basis} |"
        )

    lines.extend(
        (
            "",
            "## 显式换代图",
            "",
            "`supersedes` 只表示语义替代，不表示证明依赖。被标为 `superseded` 的 claim 必须由这里至少一条 successor 边接走；被 `refuted` 的 claim 可以保留为纯反例记录，也可以由收窄后的新命题替代。",
            "",
            "| 新 claim | 被替代 claim | 旧状态 | 新状态 |",
            "|---|---|---|---|",
        )
    )
    claim_by_id = model.claim_by_id
    for successor_id, target_id in sorted(successor_edges):
        successor = claim_by_id[successor_id]
        target = claim_by_id[target_id]
        lines.append(
            f"| [`{successor_id}`](<{_md_link_target_for_anchor(model, successor_id, relpath)}>) | "
            f"[`{target_id}`](<{_md_link_target_for_anchor(model, target_id, relpath)}>) | "
            f"`{target['status']}` | `{successor['status']}` |"
        )

    lines.extend(
        (
            "",
            "## 当前相关语义审阅",
            "",
            "| Review | Dossier | 结果 | 提炼 claim | 未决项 |",
            "|---|---|---|---|---|",
        )
    )
    for review in sorted(validity_reviews, key=lambda item: str(item["id"])):
        claims = "<br>".join(
            f"[`{claim_id}`](<{_md_link_target_for_anchor(model, str(claim_id), relpath)}>)"
            for claim_id in review["claim_ids"]
        ) or "—"
        unresolved = "<br>".join(
            _truncate(str(item), 100).replace("|", "\\|") for item in review["unresolved"]
        ) or "—"
        lines.append(
            f"| [`{review['id']}`](<CATALOG.md#{str(review['id']).lower()}>) | "
            f"`{review['dossier_id']}` | `{review['outcome']}` | {claims} | {unresolved} |"
        )

    lines.extend(
        (
            "",
            "## 复用纪律",
            "",
            "- `refutation`：旧命题本身被反例击穿；不能把被反驳的结论继续当规则，只能引用反例和失效边界。",
            "- `semantic_replacement`：旧解释由 authority 或事故取证替代；历史负结果是否方向安全、正向见证是否需重验要另行判断。",
            "- `scope_correction`：旧结论只在更窄的对象、前提或时间域内安全；复用时必须携带这些前提，不能恢复原全称口径。",
            "- `implementation_invalidation`：实现或 validator 破坏了观测可信度；修复后只恢复声明组件，不自动恢复整条路线。",
            "- `experiment_invalidation`：fixture、预算或对照设计使旧观察失去识别性；TIMEOUT、零激活和预算耗尽不能冒充反证。",
            "- `attribution_correction`：现象仍可能存在，但死因被重新拆分；后续实验必须保持单变量与阶段 telemetry。",
            "- `route_retirement`：只撤回登记设计或证据版本，不把局部 NO-GO 外推为整个方法家族不可能。",
            "- `revalidation`：修复后的证据链已经重新闭合；其复用范围仍由 `temporal_scope`、premises 和 `does_not_imply` 限定。",
            "- `reuse_policy` 描述 claim 本身如何安全引用，不授予新的 owner、rules 或 production authority。",
            "",
            "完整 statement、premises、does-not-imply、successor 关系和 evidence 见 "
            + _md_link(model.root, str(model.current_state["generated_outputs"]["catalog"]), relpath, "CATALOG")
            + "；数学与分离机制坐标见 "
            + _md_link(model.root, str(model.current_state["generated_outputs"]["reasoning"]), relpath, "REASONING_LEDGER")
            + "。",
            "",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _review_is_semantic(review: Mapping[str, Any]) -> bool:
    return review["review_scope"] != "availability_and_provenance"


def _generated_anchor_target(
    model: KnowledgeModel,
    target_relpath: str,
    anchor: str,
    from_relpath: str,
) -> str:
    start = (model.root / from_relpath).parent
    target = model.root / target_relpath
    relative = os.path.relpath(target, start=start).replace(os.sep, "/")
    return f"{relative}#{anchor.lower()}"


def render_backfill_ledger(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["backfill"])
    current_reviews = sorted(
        (review for review in model.backfill_reviews if review["status"] == "current"),
        key=lambda item: (str(item["reviewed_at"]), str(item["id"])),
    )
    semantic_reviews = [review for review in current_reviews if _review_is_semantic(review)]
    availability_reviews = [review for review in current_reviews if not _review_is_semantic(review)]
    triaged_count = sum(len(group["dossier_ids"]) for group in model.backfill_triage["groups"])
    open_workflows = sorted(
        (
            dossier
            for dossier in model.dossiers["records"]
            if dossier.get("lifecycle") == "active"
            and isinstance(dossier.get("workflow"), dict)
            and dossier["workflow"].get("closure") is None
        ),
        key=lambda item: str(item["id"]),
    )
    dossier_count = len(model.dossiers["records"])
    reviewed_dossier_ids = {str(review["dossier_id"]) for review in current_reviews}
    triaged_dossier_ids = {
        str(dossier_id)
        for group in model.backfill_triage["groups"]
        for dossier_id in group["dossier_ids"]
    }
    open_workflow_dossier_ids = {str(dossier["id"]) for dossier in open_workflows}
    covered_count = len(reviewed_dossier_ids | triaged_dossier_ids | open_workflow_dossier_ids)
    reviewed_open_workflow_count = len(reviewed_dossier_ids & open_workflow_dossier_ids)

    lines = [
        "# 历史知识回填与长尾覆盖",
        "",
        "> 本页由 `data/knowledge/backfill_reviews.jsonl`、`backfill_triage.json` 与 dossier registry 自动生成；禁止手工修改。",
        f"> 账本审阅日：`{model.backfill_triage['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "这里把两件经常被混写的事情分开：**semantic review** 表示实际读取了声明路径并提炼知识；**inventory triage** 只保证尚未审阅的 dossier 仍可发现、只落入一个队列，并带有重开条件。分诊从不等价于 `no_reusable_claim`。",
        "",
        "## 收口概览",
        "",
        f"- dossier 总数：`{dossier_count}`。",
        f"- current review：`{len(current_reviews)}`，其中语义审阅 `{len(semantic_reviews)}`，availability/provenance-only `{len(availability_reviews)}`。",
        f"- 尚无 current review、但已进入唯一 triage group：`{triaged_count}`。",
        f"- 新写入流程中尚未关闭的 active dossier：`{len(open_workflows)}`；其中已有 current review `{reviewed_open_workflow_count}`；open workflow 不进入历史 triage。",
        f"- inventory coverage：`{covered_count}/{dossier_count}`。",
        f"- semantic review coverage：`{len(semantic_reviews)}/{dossier_count}`。这个比例不会被 triage 人为抬高。",
        "",
        "## Current review",
        "",
        "| Review | Dossier | 范围 | 结果 | Claim | 未决项 |",
        "|---|---|---|---|---|---|",
    ]
    for review in current_reviews:
        claim_links = "<br>".join(
            f"[`{claim_id}`](<{_md_link_target_for_anchor(model, str(claim_id), relpath)}>)"
            for claim_id in review["claim_ids"]
        ) or "—"
        unresolved = "<br>".join(
            _truncate(str(item), 90).replace("|", "\\|") for item in review["unresolved"]
        ) or "—"
        review_target = _md_link_target_for_anchor(model, str(review["id"]), relpath)
        lines.append(
            f"| [`{review['id']}`](<{review_target}>) | `{review['dossier_id']}` | "
            f"`{review['review_scope']}` | `{review['outcome']}` | {claim_links} | {unresolved} |"
        )

    if open_workflows:
        lines.extend((
            "",
            "## Open intake workflow",
            "",
            "| Dossier | 路径 | 打开日 | 生命周期 |",
            "|---|---|---|---|",
        ))
        for dossier in open_workflows:
            workflow = dossier["workflow"]
            lines.append(
                f"| `{dossier['id']}` | `{dossier['path']}` | `{workflow['opened_at']}` | `{dossier['lifecycle']}` |"
            )

    lines.extend((
        "",
        "## Triage group",
        "",
        "| Group | 处置 | 优先级 | Dossier 数 | 相关知识 |",
        "|---|---|---:|---:|---|",
    ))
    for group in sorted(model.backfill_triage["groups"], key=lambda item: str(item["id"])):
        coordinates = [
            f"[`{claim_id}`](<{_md_link_target_for_anchor(model, str(claim_id), relpath)}>)"
            for claim_id in group["related_claim_ids"]
        ]
        coordinates.extend(
            f"[`{review_id}`](<{_md_link_target_for_anchor(model, str(review_id), relpath)}>)"
            for review_id in group["representative_review_ids"]
        )
        lines.append(
            f"| [`{group['id']}`](#{str(group['id']).lower()}) | `{group['disposition']}` | "
            f"`{group['priority']}` | {len(group['dossier_ids'])} | {'<br>'.join(coordinates) or '—'} |"
        )

    for group in sorted(model.backfill_triage["groups"], key=lambda item: str(item["id"])):
        lines.extend((
            "",
            f'<a id="{str(group["id"]).lower()}"></a>',
            f"### {group['id']}",
            "",
            f"- **处置 / 优先级：** `{group['disposition']}` / `{group['priority']}`",
            f"- **理由：** {group['rationale']}",
            f"- **重开触发：** {_join_values(group['reopen_triggers'])}",
            f"- **Dossier：** `{_join_values(group['dossier_ids'])}`",
        ))

    lines.extend((
        "",
        "## 维护纪律",
        "",
        "- legacy dossier 获得真实语义审阅后，新增 current review，并把它从 triage group 中移除；两步必须在同一变更中完成。",
        "- 新 dossier 以 open workflow 登记；open workflow 可以已经拥有 current review，但仍保持 active 且不进入 triage。关闭时必须在同一 Git-visible transaction 中新增或更新 current review，并写入 typed closure。",
        "- `availability_and_provenance` 只允许用于缺失的 local-optional 根，结果必须保持 `deferred`，不得计入 semantic review coverage。",
        "- 要断言一个 dossier 没有可复用结论，必须写 `outcome=no_reusable_claim` 的语义 review；不能从 triage disposition 推断。",
        "- 完整 claim、review 与 evidence 详情见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["catalog"]), relpath, "CATALOG")
        + "；按主题下钻见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["topics"]), relpath, "TOPIC_INDEX")
        + "。",
        "",
    ))
    return "\n".join(lines).rstrip() + "\n"


def render_topic_index(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["topics"])
    terminology_relpath = str(model.current_state["generated_outputs"]["terminology"])
    lines = [
        "# 稳定主题索引",
        "",
        "> 本页由 `data/knowledge/topics.json` 自动生成；禁止手工修改。",
        f"> 账本审阅日：`{model.topics['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "主题是读取路径，不是新的 authority。一个 claim 可以出现在多个主题中；topic membership 只表示相关性，不改变 statement、scope 或 status。",
        "",
        "## 总览",
        "",
        "| Topic | 摘要 | Claims | Dossier labels | Open |",
        "|---|---|---:|---|---:|",
    ]
    for topic in model.topics["records"]:
        lines.append(
            f"| [`{topic['id']}`](#{str(topic['id']).lower()}) | "
            f"{_truncate(str(topic['summary']), 120).replace('|', '\\|')} | "
            f"{len(topic['claim_ids'])} | {_join_values(topic['dossier_topic_labels']) or '—'} | "
            f"{len(topic['open_question_claim_ids'])} |"
        )

    for topic in model.topics["records"]:
        lines.extend((
            "",
            f'<a id="{str(topic["id"]).lower()}"></a>',
            f"## {topic['title']}",
            "",
            f"- **Topic ID：** `{topic['id']}`",
            f"- **摘要：** {topic['summary']}",
            f"- **Dossier topic labels：** {_join_values(topic['dossier_topic_labels']) or '—'}",
            "- **术语坐标：** " + ("；".join(
                f"[`{term_id}`](<{_generated_anchor_target(model, terminology_relpath, str(term_id), relpath)}>)"
                for term_id in topic["term_ids"]
            ) or "—"),
            "- **入口：** " + "；".join(
                _md_link(model.root, str(path), relpath, str(path)) for path in topic["entry_paths"]
            ),
            "",
            "### Claims",
            "",
        ))
        if topic["claim_ids"]:
            lines.extend(("| Claim | 状态 | 标题 |", "|---|---|---|"))
            for claim_id in topic["claim_ids"]:
                claim = model.claim_by_id[str(claim_id)]
                lines.append(
                    f"| [`{claim_id}`](<{_md_link_target_for_anchor(model, str(claim_id), relpath)}>) | "
                    f"`{claim['status']}` | {str(claim['title']).replace('|', '\\|')} |"
                )
        else:
            lines.append("该主题当前只提供文档/dossier 导航，没有单独登记 claim。")
        if topic["open_question_claim_ids"]:
            lines.extend((
                "",
                "### Open questions",
                "",
                *[
                    f"- [`{claim_id}`](<{_md_link_target_for_anchor(model, str(claim_id), relpath)}>)"
                    for claim_id in topic["open_question_claim_ids"]
                ],
            ))

    lines.extend((
        "",
        "完整 claim 详情见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["catalog"]), relpath, "CATALOG")
        + "；历史有效性见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["validity"]), relpath, "VALIDITY_LEDGER")
        + "；长尾覆盖见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["backfill"]), relpath, "BACKFILL_LEDGER")
        + "。",
        "",
    ))
    return "\n".join(lines).rstrip() + "\n"


def render_open_questions(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["open_questions"])
    open_claims = sorted(
        (claim for claim in model.claims if claim["status"] == "open"),
        key=lambda claim: str(claim["id"]),
    )
    topics_by_claim: dict[str, list[Mapping[str, Any]]] = {}
    for topic in model.topics["records"]:
        for claim_id in topic["open_question_claim_ids"]:
            topics_by_claim.setdefault(str(claim_id), []).append(topic)

    lines = [
        "# 当前开放问题",
        "",
        "> 本页由 claim ledger 与 `data/knowledge/topics.json` 自动生成；禁止手工修改。",
        f"> 账本审阅日：`{model.current_state['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "本页只列 `status=open` 的稳定 claim。它不是全部未来工作，也不把“尚未证明”解释成“不可能”；阶段顺序见手工维护的 ROADMAP，当前事实仍以 CURRENT 和各自机器 authority 为准。",
        "",
        "## 总览",
        "",
        "| Claim | 标题 | Scope | 相关主题 |",
        "|---|---|---|---|",
    ]
    for claim in open_claims:
        claim_id = str(claim["id"])
        topics = topics_by_claim.get(claim_id, [])
        topic_links = "<br>".join(
            f"[`{topic['id']}`](<{_generated_anchor_target(model, str(model.current_state['generated_outputs']['topics']), str(topic['id']), relpath)}>)"
            for topic in topics
        ) or "—"
        lines.append(
            f"| [`{claim_id}`](#{claim_id.lower()}) | "
            f"{str(claim['title']).replace('|', '\\|')} | "
            f"{_join_values(claim['scope']) or '—'} | {topic_links} |"
        )

    for claim in open_claims:
        claim_id = str(claim["id"])
        lines.extend(("", f'<a id="{claim_id.lower()}"></a>'))
        lines.extend(_render_claim(model, claim, relpath, heading_level=2))
        topics = topics_by_claim.get(claim_id, [])
        if topics:
            lines.append(
                "- **相关主题：** "
                + "；".join(
                    f"[`{topic['id']}`](<{_generated_anchor_target(model, str(model.current_state['generated_outputs']['topics']), str(topic['id']), relpath)}>)"
                    for topic in topics
                )
            )
            lines.append("")

    if not open_claims:
        lines.append("当前 claim ledger 没有 `status=open` 的记录。")

    lines.extend((
        "",
        "完整 claim 结构见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["catalog"]), relpath, "CATALOG")
        + "；按主题浏览见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["topics"]), relpath, "TOPIC_INDEX")
        + "；阶段安排见 "
        + _md_link(model.root, "docs/项目说明/ROADMAP.md", relpath, "ROADMAP")
        + "；唯一现态见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["current"]), relpath, "CURRENT")
        + "。",
        "",
    ))
    return "\n".join(lines).rstrip() + "\n"


def render_terminology(model: KnowledgeModel, source_digest: str) -> str:
    relpath = str(model.current_state["generated_outputs"]["terminology"])
    lines = [
        "# 核心术语与禁止混同边界",
        "",
        "> 本页由 `data/knowledge/terminology.json` 自动生成；禁止手工修改。",
        f"> 账本审阅日：`{model.terminology['ledger_reviewed_at']}`；源摘要：`sha256:{source_digest}`。",
        "",
        "术语表统一名称和类推边界，但不覆盖 canonical rules、claim statement 或 owner decision。别名只帮助检索，不表示两个更细概念在所有上下文中等价。",
        "",
        "## 快速索引",
        "",
        "| Term ID | 规范名称 | 别名 | 一句话定义 |",
        "|---|---|---|---|",
    ]
    for term in model.terminology["records"]:
        aliases = "<br>".join(str(item).replace("|", "\\|") for item in term["aliases"]) or "—"
        lines.append(
            f"| [`{term['id']}`](#{str(term['id']).lower()}) | `{term['canonical_label']}` | "
            f"{aliases} | {_truncate(str(term['definition']), 120).replace('|', '\\|')} |"
        )

    for term in model.terminology["records"]:
        lines.extend((
            "",
            f'<a id="{str(term["id"]).lower()}"></a>',
            f"## {term['canonical_label']}",
            "",
            f"- **Term ID：** `{term['id']}`",
            f"- **别名：** {_join_values(term['aliases']) or '—'}",
            f"- **定义：** {term['definition']}",
            f"- **不要混同：** {_join_values(term['distinctions'])}",
            "- **相关 claim：** " + ("；".join(
                f"[`{claim_id}`](<{_md_link_target_for_anchor(model, str(claim_id), relpath)}>)"
                for claim_id in term["related_claim_ids"]
            ) or "—"),
            "- **解释来源：** " + "；".join(
                _md_link(model.root, str(path), relpath, str(path)) for path in term["source_paths"]
            ),
        ))

    lines.extend((
        "",
        "按主题组合这些术语见 "
        + _md_link(model.root, str(model.current_state["generated_outputs"]["topics"]), relpath, "TOPIC_INDEX")
        + "；文档框架的完整原因与维护协议见 "
        + _md_link(model.root, "docs/governance/document-system/ARCHITECTURE.md", relpath, "ARCHITECTURE")
        + " 和 "
        + _md_link(model.root, "docs/governance/document-system/MAINTAINING.md", relpath, "MAINTAINING")
        + "。",
        "",
    ))
    return "\n".join(lines).rstrip() + "\n"


def _md_link_target_for_anchor(
    model: KnowledgeModel,
    claim_id: str,
    from_relpath: str | None = None,
) -> str:
    catalog_relpath = str(model.current_state["generated_outputs"]["catalog"])
    source_relpath = from_relpath or str(model.current_state["generated_outputs"]["reasoning"])
    start = (model.root / source_relpath).parent
    target = model.root / catalog_relpath
    relative = os.path.relpath(target, start=start).replace(os.sep, "/")
    return f"{relative}#{str(claim_id).lower()}"


def render(model: KnowledgeModel) -> RenderedKnowledgeDocs:
    digest = _source_digest(model)
    return RenderedKnowledgeDocs(
        current=render_current(model, digest),
        catalog=render_catalog(model, digest),
        reasoning_ledger=render_reasoning_ledger(model, digest),
        validity_ledger=render_validity_ledger(model, digest),
        backfill_ledger=render_backfill_ledger(model, digest),
        topic_index=render_topic_index(model, digest),
        terminology=render_terminology(model, digest),
        open_questions=render_open_questions(model, digest),
        source_digest=digest,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o644)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_generated_docs(model: KnowledgeModel) -> RenderedKnowledgeDocs:
    rendered = render(model)
    current_path = model.root / str(model.current_state["generated_outputs"]["current"])
    catalog_path = model.root / str(model.current_state["generated_outputs"]["catalog"])
    reasoning_path = model.root / str(model.current_state["generated_outputs"]["reasoning"])
    validity_path = model.root / str(model.current_state["generated_outputs"]["validity"])
    backfill_path = model.root / str(model.current_state["generated_outputs"]["backfill"])
    topics_path = model.root / str(model.current_state["generated_outputs"]["topics"])
    terminology_path = model.root / str(model.current_state["generated_outputs"]["terminology"])
    open_questions_path = model.root / str(model.current_state["generated_outputs"]["open_questions"])
    _atomic_write(current_path, rendered.current)
    _atomic_write(catalog_path, rendered.catalog)
    _atomic_write(reasoning_path, rendered.reasoning_ledger)
    _atomic_write(validity_path, rendered.validity_ledger)
    _atomic_write(backfill_path, rendered.backfill_ledger)
    _atomic_write(topics_path, rendered.topic_index)
    _atomic_write(terminology_path, rendered.terminology)
    _atomic_write(open_questions_path, rendered.open_questions)
    return rendered


def check_generated_docs(model: KnowledgeModel) -> tuple[str, ...]:
    rendered = render(model)
    expected = {
        str(model.current_state["generated_outputs"]["current"]): rendered.current,
        str(model.current_state["generated_outputs"]["catalog"]): rendered.catalog,
        str(model.current_state["generated_outputs"]["reasoning"]): rendered.reasoning_ledger,
        str(model.current_state["generated_outputs"]["validity"]): rendered.validity_ledger,
        str(model.current_state["generated_outputs"]["backfill"]): rendered.backfill_ledger,
        str(model.current_state["generated_outputs"]["topics"]): rendered.topic_index,
        str(model.current_state["generated_outputs"]["terminology"]): rendered.terminology,
        str(model.current_state["generated_outputs"]["open_questions"]): rendered.open_questions,
    }
    errors: list[str] = []
    for relpath, content in expected.items():
        path = model.root / relpath
        if not path.is_file():
            errors.append(f"missing generated document: {relpath}")
            continue
        try:
            actual = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            errors.append(f"cannot read generated document {relpath}: {exc}")
            continue
        if actual != content:
            errors.append(f"generated document drift: {relpath}; run devtools/build_knowledge_docs.py --write")
    return tuple(errors)


def _check_markdown_links(root: Path, relpath: str) -> tuple[str, ...]:
    """Validate repository-local links in one stable knowledge-navigation page."""

    source = root / relpath
    if not source.is_file():
        return (f"missing stable knowledge-navigation page: {relpath}",)
    try:
        text = source.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return (f"cannot read stable knowledge-navigation page {relpath}: {exc}",)

    errors: list[str] = []
    # START_HERE deliberately uses ordinary inline links. Historical
    # snapshots and generated evidence catalogs are not swept here because a
    # dated citation may intentionally point at material absent from a light
    # checkout.
    for match in re.finditer(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", text):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<"):
            close = raw_target.find(">")
            if close < 0:
                errors.append(f"malformed angle-bracket link in {relpath}: {raw_target}")
                continue
            target = raw_target[1:close]
        else:
            target = raw_target.split(maxsplit=1)[0]
        if not target or target.startswith("#") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        candidate = (source.parent / path_part).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"link escapes repository in {relpath}: {target}")
            continue
        if not candidate.exists():
            errors.append(f"broken local link in {relpath}: {target}")
    return tuple(errors)


def check_front_door_links(model: KnowledgeModel) -> tuple[str, ...]:
    """Validate the stable task router; front-door policy lives in docctl.

    Canonical entrypoint roles, volatile-copy guards and generated compatibility
    redirects are document-framework concerns and are validated by
    ``devtools/docctl.py doctor``.  The knowledge checker retains only this
    narrow link check because START_HERE is also the knowledge spine's stable
    human navigation surface.
    """

    return _check_markdown_links(model.root, START_HERE_RELPATH)


def check_repository(root: Path = ROOT) -> tuple[str, ...]:
    """Load all ledgers and return projection-freshness or navigation failures."""

    model = load_model(root)
    return (
        *check_generated_docs(model),
        *check_front_door_links(model),
    )


def _slug_for_dossier(path: str) -> str:
    stem = PurePosixPath(path).name
    stem = re.sub(r"\.[^.]+$", "", stem)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
    if not slug:
        slug = "UNTITLED"
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:10].upper()
    return f"DOSSIER-{slug[:56]}-{digest}"


def _date_from_path(path: str) -> str | None:
    matches = re.findall(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", path)
    if not matches:
        return None
    year, month, day = matches[-1]
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _entry_priority(path: Path) -> tuple[int, int, str]:
    names = {
        "README.md": 0,
        "SUMMARY.md": 1,
        "RESULT.md": 2,
        "REPORT.md": 3,
        "VERDICT.md": 4,
        "EVAL.md": 5,
        "INDEX.md": 6,
    }
    return (names.get(path.name, 20), len(path.parts), path.as_posix())


def _entry_for_path(root: Path, relpath: str) -> str | None:
    path = root / relpath
    if path.is_file():
        return relpath
    candidates = sorted(path.rglob("*.md"), key=_entry_priority)
    if not candidates:
        return None
    return candidates[0].relative_to(root).as_posix()


def _read_text_prefix(path: Path, limit: int = 262_144) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
    except OSError as exc:
        raise KnowledgeError(f"cannot read dossier entry {path}: {exc}") from exc
    return raw.decode("utf-8", errors="replace")


def _title_from_path(relpath: str) -> str:
    stem = PurePosixPath(relpath).name
    stem = re.sub(r"\.[^.]+$", "", stem)
    return re.sub(r"[_-]+", " ", stem).strip() or "untitled dossier"


def _extract_title_and_summary(path: Path | None, relpath: str) -> tuple[str, str]:
    if path is None:
        return (
            _title_from_path(relpath),
            "本目录未提供 Markdown 入口；请从目录内的结构化收据、日志或脚本下钻。",
        )
    text = _read_text_prefix(path)
    lines = text.splitlines()
    title = _title_from_path(relpath)
    title_index = -1
    for index, line in enumerate(lines):
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            title = re.sub(r"[`*_]", "", match.group(1)).strip()
            title_index = index
            break

    paragraph: list[str] = []
    in_fence = False
    for line in lines[title_index + 1 :]:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", "|", "- ", "* ", ">", "<")):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
        if sum(len(part) for part in paragraph) >= 240:
            break
    summary = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", " ".join(paragraph))
    summary = re.sub(r"[`*_]", "", summary)
    return title or _title_from_path(relpath), _truncate(summary, 260)


def _topics_for_path(path: str, title: str) -> list[str]:
    haystack = f"{path} {title}".casefold()
    topics = [topic for topic, needles in TOPIC_RULES if any(needle in haystack for needle in needles)]
    return topics or ["other"]


def _new_dossier_record(
    root: Path,
    relpath: str,
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    entry_file = _entry_for_path(root, relpath)
    entry_path = root / entry_file if entry_file is not None else None
    title, summary = _extract_title_and_summary(entry_path, relpath)
    kind = "directory" if (root / relpath).is_dir() else "note"
    return {
        "id": _slug_for_dossier(relpath),
        "path": relpath,
        "entry_file": entry_file,
        "title": title,
        "kind": kind,
        "lifecycle": spec["default_lifecycle"],
        "relevance": spec["default_relevance"],
        "curation": "auto_indexed",
        "tracked_state": spec["tracked_state"],
        "date": _date_from_path(relpath),
        "topics": _topics_for_path(relpath, title),
        "summary": summary,
    }


def _refresh_auto_record(
    root: Path,
    record: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    relpath = str(record["path"])
    fresh = _new_dossier_record(root, relpath, spec)
    updated = dict(record)
    for key in ("entry_file", "title", "kind", "tracked_state", "date", "topics", "summary"):
        updated[key] = fresh[key]
    return updated


def refresh_dossiers(root: Path = ROOT) -> tuple[int, int, int]:
    current_state = _read_json(root, CURRENT_STATE_RELPATH)
    if not isinstance(current_state, dict):
        raise KnowledgeError(f"{CURRENT_STATE_RELPATH} root must be an object")
    _validate_with_schema(
        root,
        current_state,
        SCHEMA_RELPATHS["current_state"],
        CURRENT_STATE_RELPATH,
    )

    dossier_path = root / DOSSIERS_RELPATH
    if dossier_path.exists():
        dossiers = _read_json(root, DOSSIERS_RELPATH)
        if not isinstance(dossiers, dict):
            raise KnowledgeError(f"{DOSSIERS_RELPATH} root must be an object")
        records = list(dossiers.get("records", []))
    else:
        dossiers = {"schema_version": "zmd_dossiers_v1"}
        records = []

    observed, _missing_optional_roots = _inventory_children(root, current_state)
    existing = {str(record["path"]): record for record in records}
    if len(existing) != len(records):
        raise KnowledgeError("dossier registry has duplicate paths; resolve before refresh")

    added = 0
    refreshed = 0
    for relpath, spec in sorted(observed.items()):
        record = existing.get(relpath)
        if record is None:
            if spec["tracked_state"] == "local_optional":
                raise KnowledgeError(
                    f"new local_optional dossier {relpath} requires explicit portability metadata; "
                    "use docctl register-local-evidence instead of auto-refresh"
                )
            record = _new_dossier_record(root, relpath, spec)
            record["lifecycle"] = "active"
            record["workflow"] = {
                "opened_at": date.today().isoformat(),
                "closure": None,
            }
            records.append(record)
            existing[relpath] = record
            added += 1
        elif record.get("curation") == "auto_indexed":
            updated = _refresh_auto_record(root, record, spec)
            records[records.index(record)] = updated
            existing[relpath] = updated
            refreshed += 1

    stale_required: list[str] = []
    observed_paths = set(observed)
    for relpath, record in existing.items():
        configured_root = _root_spec_for_record(relpath, current_state)
        if configured_root is None:
            raise KnowledgeError(f"dossier registry path is outside configured roots: {relpath}")
        if configured_root["availability"] == "required" and relpath not in observed_paths:
            stale_required.append(relpath)
        expected_state = configured_root["tracked_state"]
        if record.get("tracked_state") != expected_state:
            raise KnowledgeError(f"dossier {relpath} tracked_state must be {expected_state!r}; resolve explicitly")
    if stale_required:
        raise KnowledgeError(
            "tracked dossier paths disappeared; resolve explicitly: " + ", ".join(sorted(stale_required))
        )

    records.sort(key=lambda record: str(record["path"]))
    dossiers["schema_version"] = "zmd_dossiers_v1"
    dossiers["ledger_reviewed_at"] = current_state["ledger_reviewed_at"]
    dossiers["records"] = records
    content = json.dumps(dossiers, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    _atomic_write(dossier_path, content)
    return added, refreshed, len(records)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--refresh-dossiers",
        action="store_true",
        help="append missing top-level evidence packages and refresh auto-indexed metadata",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "write CURRENT, CATALOG, REASONING_LEDGER, VALIDITY_LEDGER, "
            "BACKFILL_LEDGER, TOPIC_INDEX and TERMINOLOGY projections"
        ),
    )
    parser.add_argument("--check", action="store_true", help="verify generated files match their sources")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = args.repo_root.resolve()
    try:
        if args.refresh_dossiers:
            added, refreshed, total = refresh_dossiers(root)
            print(f"dossier registry refreshed: added={added} auto_refreshed={refreshed} total={total}")
        model = load_model(root)
        if args.write:
            rendered = write_generated_docs(model)
            print(f"knowledge docs written: source_digest={rendered.source_digest}")
        if args.check or (not args.write and not args.refresh_dossiers):
            errors = (
                *check_generated_docs(model),
                *check_front_door_links(model),
            )
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("knowledge docs: PASS")
    except KnowledgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
