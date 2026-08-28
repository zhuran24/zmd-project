#!/usr/bin/env python3
"""Resolve, explain and validate the repository's self-describing document system.

The bootstrap convention is deliberately tiny: locate ``.docsystem/manifest.json``
from the repository root, then let this module resolve inherited ``DOC_POLICY.json``
files for the target path.  Ordinary operations receive a compact effective card;
framework-core changes receive the architecture, maintenance and ADR coordinates
needed to change the system itself.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import jsonschema  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devtools.artifact_evidence import (  # noqa: E402
    ArtifactEvidenceError,
    load_semantic_boundary as load_artifact_evidence_semantic_boundary,
)
from devtools.document_governance_gate import (  # noqa: E402
    GovernanceGateError,
    load_gate_configuration,
)
from devtools.document_maintenance_audit import (  # noqa: E402
    MaintenanceAuditError,
    parse_audit_date,
    run_maintenance_audit,
)

BOOTSTRAP_RELPATH = ".docsystem/manifest.json"
MANIFEST_SCHEMA_RELPATH = "data/repository_governance/document_system/manifest.schema.json"
POLICY_SCHEMA_VERSION = "zmd_doc_policy_v1"

LIST_FIELDS = frozenset(
    {
        "section_refs",
        "invariant_refs",
        "knowledge_refs",
        "adr_refs",
        "source_paths",
        "required_reads",
        "after_change",
    }
)
COMPLETE_CONTRACT_FIELDS = frozenset(
    {
        "document_class",
        "authority_role",
        "mutation",
        "context_level",
        "purpose",
        "volatile_facts",
        *LIST_FIELDS,
        "generator_action",
        "review_policy",
        "relaxation_decision_id",
    }
)
MUTATION_RANK = {
    "direct": 0,
    "governed": 1,
    "append_only": 2,
    "generator_only": 3,
    "owner_only": 4,
    "immutable": 5,
}
CONTEXT_RANK = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}
BASE_CONTRACT: dict[str, Any] = {
    "document_class": "unmanaged",
    "authority_role": "none",
    "mutation": "direct",
    "context_level": "L0",
    "purpose": "No effective document policy has declared this path.",
    "volatile_facts": "not_applicable",
    "section_refs": [],
    "invariant_refs": [],
    "knowledge_refs": [],
    "adr_refs": [],
    "source_paths": [],
    "required_reads": [],
    "after_change": [],
    "generator_action": None,
    "review_policy": {"at_phase_boundary": False, "max_interval_days": None},
    "relaxation_decision_id": None,
}
FRAMEWORK_ACTIONS = (
    "docsystem.render_legacy",
    "docsystem.render_guidance",
    "docsystem.render_entrypoints",
    "docsystem.render_sections",
    "docsystem.render_convergence",
    "docsystem.render_maintenance",
    "docsystem.audit",
    "docsystem.intake",
    "docsystem.doctor",
    "docsystem.gate",
    "docsystem.tests",
    "docs.reference.validate",
)

DECISION_V1_TO_V2_MIGRATION_ID = "decision_v1_to_v2_nonauthorizing_register"
DECISION_V1_TO_V2_REWRITE_FIELDS = frozenset(
    {
        "schema_version",
        "external_decision_id",
        "non_authorizing",
        "ruling_event_id",
        "authority_source",
        "evidence",
    }
)


class DocSystemError(RuntimeError):
    """Fail-closed document-system error."""


@dataclass(frozen=True)
class LoadedPolicy:
    relpath: str
    base_relpath: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class Relaxation:
    field: str
    previous: str
    requested: str
    source: str
    decision_id: str | None


@dataclass(frozen=True)
class Resolution:
    target: str
    intent: str
    exists: bool
    contract: Mapping[str, Any]
    policies: tuple[str, ...]
    matched_rules: tuple[str, ...]
    rationale_chain: tuple[str, ...]
    field_sources: Mapping[str, tuple[str, ...]]
    framework_matches: tuple[str, ...]
    entrypoint: Mapping[str, Any] | None
    sections: tuple[Mapping[str, Any], ...]
    dossier: Mapping[str, Any] | None
    reviews: tuple[Mapping[str, Any], ...]
    triage: Mapping[str, Any] | None
    ephemeral: Mapping[str, Any] | None
    topics: tuple[Mapping[str, Any], ...]
    knowledge: tuple[Mapping[str, Any], ...]
    invariant_summaries: tuple[Mapping[str, Any], ...]
    adr_paths: tuple[str, ...]
    allowed: bool
    operation_guidance: str
    action_commands: tuple[Mapping[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "intent": self.intent,
            "exists": self.exists,
            "allowed": self.allowed,
            "operation_guidance": self.operation_guidance,
            "contract": dict(self.contract),
            "policies": list(self.policies),
            "matched_rules": list(self.matched_rules),
            "rationale_chain": list(self.rationale_chain),
            "field_sources": {key: list(value) for key, value in self.field_sources.items()},
            "framework_matches": list(self.framework_matches),
            "entrypoint": dict(self.entrypoint) if self.entrypoint is not None else None,
            "sections": [dict(item) for item in self.sections],
            "dossier": dict(self.dossier) if self.dossier is not None else None,
            "backfill_reviews": [dict(item) for item in self.reviews],
            "backfill_triage": dict(self.triage) if self.triage is not None else None,
            "ephemeral": dict(self.ephemeral) if self.ephemeral is not None else None,
            "topics": [dict(item) for item in self.topics],
            "knowledge": [dict(item) for item in self.knowledge],
            "invariants": [dict(item) for item in self.invariant_summaries],
            "adr_paths": list(self.adr_paths),
            "actions": [dict(item) for item in self.action_commands],
        }


@dataclass(frozen=True)
class CheckResult:
    paths: tuple[str, ...]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    actions: tuple[Mapping[str, str], ...]


@dataclass(frozen=True)
class IntakeEvent:
    id: str
    title: str
    description: str
    paths: tuple[str, ...]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    action_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "paths": list(self.paths),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "action_ids": list(self.action_ids),
        }


@dataclass(frozen=True)
class IntakeResult:
    paths: tuple[str, ...]
    comparison_revision: str
    events: tuple[IntakeEvent, ...]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    actions: tuple[Mapping[str, str], ...]
    authority_companion_matched_paths: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "paths": list(self.paths),
            "comparison_revision": self.comparison_revision,
            "events": [event.as_dict() for event in self.events],
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "actions": [dict(action) for action in self.actions],
            "authority_companion_matched_paths": list(self.authority_companion_matched_paths),
        }


class DocumentSystem:
    """Loaded document-system model with cached policies and knowledge ledgers."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root.resolve()
        self.manifest = self._load_manifest()
        overlay_payload = self.manifest["workspace_overlays"]
        self.workspace_overlays = self._index_records(
            overlay_payload["records"], "id", "workspace overlays"
        )
        self.workspace_overlay_by_path = {
            str(record["path"]): record for record in self.workspace_overlays.values()
        }
        self.policy_schema = self._load_schema(str(self.manifest["policy_schema"]))
        self.invariants_payload = self._load_validated(
            str(self.manifest["invariants"]),
            str(self.manifest["invariants_schema"]),
        )
        self.invariants = self._index_records(self.invariants_payload["records"], "id", "document invariants")
        entrypoint_config = self.manifest["entrypoint_registry"]
        self.entrypoints_payload = self._load_validated(
            str(entrypoint_config["source"]),
            str(entrypoint_config["schema"]),
        )
        self.entrypoint_surfaces = self._index_records(
            self.entrypoints_payload["surfaces"], "id", "entrypoint surfaces"
        )
        self.entrypoint_redirects = self._index_records(
            self.entrypoints_payload["generated_redirects"],
            "id",
            "entrypoint redirects",
        )
        self.entrypoint_guards = self._index_records(
            self.entrypoints_payload["guarded_documents"],
            "id",
            "guarded documents",
        )
        self.entrypoint_by_path: dict[str, Mapping[str, Any]] = {}
        for kind, records in (
            ("surface", self.entrypoint_surfaces.values()),
            ("guard", self.entrypoint_guards.values()),
            ("redirect", self.entrypoint_redirects.values()),
        ):
            for record in records:
                path = str(record["path"])
                if path in self.entrypoint_by_path:
                    raise DocSystemError(f"duplicate entrypoint path: {path}")
                self.entrypoint_by_path[path] = {"kind": kind, **dict(record)}
        section_config = self.manifest["section_registry"]
        self.sections_payload = self._load_validated(
            str(section_config["source"]),
            str(section_config["schema"]),
        )
        self.sections = self._index_records(
            self.sections_payload["records"], "id", "document sections"
        )
        self.section_by_entry_path: dict[str, Mapping[str, Any]] = {}
        for record in self.sections.values():
            path = str(record["entry_path"])
            if path in self.section_by_entry_path:
                raise DocSystemError(f"duplicate section entry path: {path}")
            self.section_by_entry_path[path] = record
        intake_config = self.manifest["intake_protocol"]
        self.intake_payload = self._load_validated(
            str(intake_config["source"]),
            str(intake_config["schema"]),
        )
        self.intake_events = self._index_records(
            self.intake_payload["events"], "id", "document intake events"
        )
        ephemeral_config = self.intake_payload["ephemeral_documents"]
        self.ephemeral_payload = self._load_validated(
            str(ephemeral_config["source"]),
            str(ephemeral_config["schema"]),
        )
        self.ephemeral_by_path = self._index_records(
            self.ephemeral_payload["records"], "path", "ephemeral documents"
        )
        maintenance_config = self.manifest["maintenance_audit"]
        self.maintenance_audit_payload = self._load_validated(
            str(maintenance_config["source"]),
            str(maintenance_config["schema"]),
        )
        self.maintenance_audit_checks = self._index_records(
            self.maintenance_audit_payload["checks"],
            "id",
            "maintenance audit checks",
        )
        self.maintenance_audit_profiles = {
            str(key): dict(value)
            for key, value in self.maintenance_audit_payload["profiles"].items()
        }
        landing_config = self.manifest["landing_protocol"]
        self.landing_payload = self._load_validated(
            str(landing_config["source"]),
            str(landing_config["schema"]),
        )
        self.landing_ack_schema = self._load_schema(str(landing_config["ack_schema"]))
        gate_config = self.manifest["governance_gate"]
        self.governance_gate_payload = self._load_validated(
            str(gate_config["source"]),
            str(gate_config["schema"]),
        )
        self.governance_gate_lanes = self._index_records(
            self.governance_gate_payload["lanes"], "id", "document governance lanes"
        )
        self.governance_gate_profiles = {
            str(key): dict(value)
            for key, value in self.governance_gate_payload["profiles"].items()
        }
        self.test_timing_receipt = dict(self.manifest["test_timing_receipt"])
        self.actions = {str(key): dict(value) for key, value in self.manifest["actions"].items()}
        self.adrs = {str(key): str(value) for key, value in self.manifest["adrs"].items()}
        self._policy_cache: dict[str, LoadedPolicy] = {}
        self._claims: dict[str, Mapping[str, Any]] | None = None
        self._decisions: dict[str, Mapping[str, Any]] | None = None
        self._dossiers: tuple[Mapping[str, Any], ...] | None = None
        self._backfill_reviews: dict[str, Mapping[str, Any]] | None = None
        self._triage_groups: dict[str, Mapping[str, Any]] | None = None
        self._triage_by_dossier: Mapping[str, Mapping[str, Any]] | None = None
        self._terms: dict[str, Mapping[str, Any]] | None = None
        self._topics: dict[str, Mapping[str, Any]] | None = None
        self._topics_by_claim: Mapping[str, tuple[str, ...]] | None = None
        self._topics_by_dossier_label: Mapping[str, tuple[str, ...]] | None = None
        self._dossier_claims: Mapping[str, tuple[str, ...]] | None = None
        self._dossier_decisions: Mapping[str, tuple[str, ...]] | None = None
        self._dossier_reviews: Mapping[str, tuple[Mapping[str, Any], ...]] | None = None
        self._tracked_paths_cache: tuple[str, ...] | None = None
        self._visible_paths_cache: tuple[str, ...] | None = None
        self._projection_paths_cache: tuple[str, ...] | None = None
        self._policy_paths_cache: tuple[str, ...] | None = None

    # ------------------------------------------------------------------
    # strict loading
    # ------------------------------------------------------------------

    def _load_manifest(self) -> Mapping[str, Any]:
        manifest = _read_json_object(self.root / BOOTSTRAP_RELPATH, self.root)
        declared = manifest.get("manifest_schema")
        if declared != MANIFEST_SCHEMA_RELPATH:
            raise DocSystemError(
                "bootstrap manifest_schema is not the code-pinned schema path: "
                f"{declared!r} != {MANIFEST_SCHEMA_RELPATH!r}"
            )
        schema = _read_json_object(self.root / MANIFEST_SCHEMA_RELPATH, self.root)
        _validate_schema_and_value(schema, manifest, BOOTSTRAP_RELPATH)
        return manifest

    def _load_schema(self, relpath: str) -> Mapping[str, Any]:
        return _read_json_object(self.root / _normalise_relpath(relpath), self.root)

    def _load_validated(self, relpath: str, schema_relpath: str) -> Mapping[str, Any]:
        payload = _read_json_object(self.root / _normalise_relpath(relpath), self.root)
        schema = self._load_schema(schema_relpath)
        _validate_schema_and_value(schema, payload, relpath)
        return payload

    @staticmethod
    def _index_records(records: Iterable[Mapping[str, Any]], key: str, label: str) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for record in records:
            value = str(record[key])
            if value in result:
                raise DocSystemError(f"duplicate {label} {key}: {value}")
            result[value] = record
        return result

    def _load_policy(self, relpath: str) -> LoadedPolicy:
        relpath = _normalise_relpath(relpath)
        cached = self._policy_cache.get(relpath)
        if cached is not None:
            return cached
        payload = _read_json_object(self.root / relpath, self.root)
        _validate_schema_and_value(self.policy_schema, payload, relpath)
        if payload.get("schema_version") != POLICY_SCHEMA_VERSION:
            raise DocSystemError(f"{relpath}: unsupported policy schema_version")
        base = PurePosixPath(relpath).parent.as_posix()
        if base == ".":
            base = ""
        loaded = LoadedPolicy(relpath=relpath, base_relpath=base, payload=payload)
        self._policy_cache[relpath] = loaded
        return loaded

    # ------------------------------------------------------------------
    # knowledge and dossier overlay
    # ------------------------------------------------------------------

    def _ensure_knowledge(self) -> None:
        if self._claims is not None:
            return
        sources = self.manifest["knowledge_sources"]
        claims = _read_jsonl(self.root / str(sources["claims"]), self.root)
        decisions = _read_jsonl(self.root / str(sources["decisions"]), self.root)
        backfill_reviews = _read_jsonl(self.root / str(sources["backfill_reviews"]), self.root)
        triage_payload = _read_json_object(self.root / str(sources["backfill_triage"]), self.root)
        terminology_payload = _read_json_object(self.root / str(sources["terminology"]), self.root)
        topics_payload = _read_json_object(self.root / str(sources["topics"]), self.root)
        dossier_payload = _read_json_object(self.root / str(sources["dossiers"]), self.root)
        dossier_records = dossier_payload.get("records")
        if not isinstance(dossier_records, list):
            raise DocSystemError("dossier registry records must be a list")
        self._claims = self._index_records(claims, "id", "claim")
        self._decisions = self._index_records(decisions, "id", "decision")
        self._backfill_reviews = self._index_records(backfill_reviews, "id", "backfill review")
        triage_records = triage_payload.get("groups")
        term_records = terminology_payload.get("records")
        topic_records = topics_payload.get("records")
        if not isinstance(triage_records, list):
            raise DocSystemError("backfill triage groups must be a list")
        if not isinstance(term_records, list):
            raise DocSystemError("terminology records must be a list")
        if not isinstance(topic_records, list):
            raise DocSystemError("topic records must be a list")
        self._triage_groups = self._index_records(triage_records, "id", "triage group")
        self._terms = self._index_records(term_records, "id", "term")
        self._topics = self._index_records(topic_records, "id", "topic")
        self._dossiers = tuple(dossier_records)

        triage_by_dossier: dict[str, Mapping[str, Any]] = {}
        for group in triage_records:
            for dossier_id in group.get("dossier_ids", []):
                key = str(dossier_id)
                if key in triage_by_dossier:
                    raise DocSystemError(f"dossier appears in multiple triage groups: {key}")
                triage_by_dossier[key] = group
        self._triage_by_dossier = triage_by_dossier

        topics_by_claim: dict[str, list[str]] = defaultdict(list)
        topics_by_dossier_label: dict[str, list[str]] = defaultdict(list)
        for topic in topic_records:
            topic_id = str(topic["id"])
            for claim_id in topic.get("claim_ids", []):
                topics_by_claim[str(claim_id)].append(topic_id)
            for label in topic.get("dossier_topic_labels", []):
                topics_by_dossier_label[str(label)].append(topic_id)
        self._topics_by_claim = {key: tuple(sorted(values)) for key, values in topics_by_claim.items()}
        self._topics_by_dossier_label = {key: tuple(sorted(values)) for key, values in topics_by_dossier_label.items()}

        claim_backlinks: dict[str, list[str]] = defaultdict(list)
        for record in claims:
            for dossier_id in record.get("dossier_ids", []):
                claim_backlinks[str(dossier_id)].append(str(record["id"]))
        decision_backlinks: dict[str, list[str]] = defaultdict(list)
        for record in decisions:
            for dossier_id in record.get("dossier_ids", []):
                decision_backlinks[str(dossier_id)].append(str(record["id"]))
        self._dossier_claims = {key: tuple(sorted(values)) for key, values in claim_backlinks.items()}
        self._dossier_decisions = {key: tuple(sorted(values)) for key, values in decision_backlinks.items()}
        review_backlinks: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in backfill_reviews:
            review_backlinks[str(record["dossier_id"])].append(record)
        self._dossier_reviews = {
            key: tuple(
                sorted(
                    values,
                    key=lambda item: (
                        str(item.get("reviewed_at", "")),
                        str(item["id"]),
                    ),
                )
            )
            for key, values in review_backlinks.items()
        }

    def _entrypoint_for(self, target: str) -> Mapping[str, Any] | None:
        record = self.entrypoint_by_path.get(target)
        return dict(record) if record is not None else None

    def _sections_for_refs(self, section_refs: Iterable[str]) -> tuple[Mapping[str, Any], ...]:
        result: list[Mapping[str, Any]] = []
        for section_id in _dedupe(str(value) for value in section_refs):
            record = self.sections.get(section_id)
            if record is None:
                raise DocSystemError(f"unknown document section reference: {section_id}")
            result.append(record)
        return tuple(result)

    def _decision_is_current(self, decision_id: str) -> bool:
        self._ensure_knowledge()
        assert self._decisions is not None
        record = self._decisions.get(decision_id)
        return record is not None and record.get("status") == "current"

    def _decision_authorizes_policy_relaxation(self, decision_id: str) -> bool:
        """Require an explicit current decision scoped to the document framework."""

        self._ensure_knowledge()
        assert self._decisions is not None
        record = self._decisions.get(decision_id)
        if record is None or record.get("status") != "current":
            return False
        scope = {str(value) for value in record.get("scope", [])}
        return record.get("authority_effect") == "scope_boundary" and bool(
            scope & {"document-system", "document-policy"}
        )

    def _dossier_for(self, target: str) -> Mapping[str, Any] | None:
        self._ensure_knowledge()
        assert self._dossiers is not None
        candidates = [
            record
            for record in self._dossiers
            if target == str(record["path"]) or target.startswith(f"{record['path']}/")
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda record: len(str(record["path"])))

    def _knowledge_records(
        self, ids: Iterable[str], dossier: Mapping[str, Any] | None
    ) -> tuple[Mapping[str, Any], ...]:
        self._ensure_knowledge()
        assert self._claims is not None
        assert self._decisions is not None
        all_ids = list(ids)
        if dossier is not None:
            dossier_id = str(dossier["id"])
            assert self._dossier_claims is not None
            assert self._dossier_decisions is not None
            all_ids.extend(self._dossier_claims.get(dossier_id, ()))
            all_ids.extend(self._dossier_decisions.get(dossier_id, ()))
        result: list[Mapping[str, Any]] = []
        for knowledge_id in _dedupe(all_ids):
            source = self._claims.get(knowledge_id) or self._decisions.get(knowledge_id)
            if source is None:
                raise DocSystemError(f"unknown knowledge reference: {knowledge_id}")
            summary = {
                "id": knowledge_id,
                "title": source.get("title", ""),
                "status": source.get("status", ""),
                "statement": source.get("statement", ""),
                "authority": source.get("authority", source.get("decided_by", "")),
                "authority_effect": source.get("authority_effect", ""),
            }
            separation = source.get("separation_profile")
            if isinstance(separation, Mapping):
                summary["separation_profile"] = {
                    "target_stage": separation.get("target_stage", ""),
                    "candidate_source": separation.get("candidate_source", ""),
                    "selection_modes": tuple(separation.get("selection_modes", ())),
                    "validation_modes": tuple(separation.get("validation_modes", ())),
                    "completeness": separation.get("completeness", ""),
                    "consumption_modes": tuple(separation.get("consumption_modes", ())),
                    "baseline_comparison": separation.get("baseline_comparison", ""),
                }
            validity = source.get("validity_profile")
            if isinstance(validity, Mapping):
                summary["validity_profile"] = {
                    "event_type": validity.get("event_type", ""),
                    "affected_layers": tuple(validity.get("affected_layers", ())),
                    "basis": tuple(validity.get("basis", ())),
                    "reuse_policy": validity.get("reuse_policy", ""),
                    "repair_state": validity.get("repair_state", ""),
                    "temporal_scope": validity.get("temporal_scope", ""),
                }
            result.append(summary)
        return tuple(result)

    def _reviews_for_dossier(self, dossier: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
        if dossier is None:
            return ()
        self._ensure_knowledge()
        assert self._dossier_reviews is not None
        records = self._dossier_reviews.get(str(dossier["id"]), ())
        current = [record for record in records if record.get("status") == "current"]
        if len(current) > 1:
            raise DocSystemError(f"dossier {dossier['id']} has multiple current backfill reviews")
        return tuple(
            {
                "id": str(record["id"]),
                "status": str(record["status"]),
                "reviewed_at": str(record["reviewed_at"]),
                "review_scope": str(record["review_scope"]),
                "outcome": str(record["outcome"]),
                "claim_ids": tuple(str(value) for value in record.get("claim_ids", [])),
                "summary": str(record["summary"]),
                "unresolved": tuple(str(value) for value in record.get("unresolved", [])),
                "next_review_trigger": str(record["next_review_trigger"]),
            }
            for record in current
        )

    def _triage_for_dossier(
        self,
        dossier: Mapping[str, Any] | None,
        reviews: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any] | None:
        if dossier is None or reviews:
            return None
        workflow = dossier.get("workflow")
        if (
            dossier.get("lifecycle") == "active"
            and isinstance(workflow, Mapping)
            and workflow.get("closure") is None
        ):
            # A newly opened dossier is an active workflow, not an unreviewed
            # historical backlog item.  It becomes review/triage eligible only
            # when the typed closure transaction is written.
            return None
        self._ensure_knowledge()
        assert self._triage_by_dossier is not None
        record = self._triage_by_dossier.get(str(dossier["id"]))
        if record is None:
            raise DocSystemError(f"dossier has neither a current review nor a triage group: {dossier['id']}")
        return {
            "id": str(record["id"]),
            "disposition": str(record["disposition"]),
            "priority": str(record["priority"]),
            "rationale": str(record["rationale"]),
            "related_claim_ids": tuple(str(value) for value in record.get("related_claim_ids", [])),
            "representative_review_ids": tuple(str(value) for value in record.get("representative_review_ids", [])),
            "reopen_triggers": tuple(str(value) for value in record.get("reopen_triggers", [])),
        }

    def _topics_for_dossier(
        self,
        dossier: Mapping[str, Any] | None,
        knowledge: Sequence[Mapping[str, Any]],
    ) -> tuple[Mapping[str, Any], ...]:
        if dossier is None:
            return ()
        self._ensure_knowledge()
        assert self._topics is not None
        assert self._topics_by_claim is not None
        assert self._topics_by_dossier_label is not None
        topic_ids: list[str] = []
        for label in dossier.get("topics", []):
            topic_ids.extend(self._topics_by_dossier_label.get(str(label), ()))
        for record in knowledge:
            topic_ids.extend(self._topics_by_claim.get(str(record["id"]), ()))
        return tuple(
            {
                "id": topic_id,
                "title": str(self._topics[topic_id]["title"]),
                "summary": str(self._topics[topic_id]["summary"]),
            }
            for topic_id in _dedupe(topic_ids)
        )

    # ------------------------------------------------------------------
    # policy discovery and resolution
    # ------------------------------------------------------------------

    def policy_paths_for_target(self, target: str) -> tuple[str, ...]:
        target = _normalise_relpath(target)
        filename = str(self.manifest["policy_filename"])
        root_policy = _normalise_relpath(str(self.manifest["root_policy"]))
        visible_policies = set(self.policy_paths())
        target_parent = PurePosixPath(target).parent
        directories: list[PurePosixPath] = [PurePosixPath(".")]
        current = PurePosixPath(".")
        if target_parent.as_posix() != ".":
            for part in target_parent.parts:
                current = current / part
                directories.append(current)

        result: list[str] = []
        for directory in directories:
            candidate = root_policy if directory.as_posix() == "." else (directory / filename).as_posix()
            if candidate == target:
                # A policy never authorizes its own mutation.  Its ancestors and
                # the bootstrap framework-core overlay govern it.
                continue
            if candidate in visible_policies:
                result.append(candidate)
        return tuple(_dedupe(result))

    def resolve(self, target: str | Path, intent: str = "edit") -> Resolution:
        target_relpath = _target_relpath(self.root, target)
        contract: dict[str, Any] = _deepcopy_json(BASE_CONTRACT)
        field_sources: dict[str, list[str]] = {key: ["bootstrap:BASE_CONTRACT"] for key in COMPLETE_CONTRACT_FIELDS}
        rationale_chain: list[str] = []
        matched_rules: list[str] = []
        relaxations: list[Relaxation] = []
        policy_paths = self.policy_paths_for_target(target_relpath)

        for policy_path in policy_paths:
            policy = self._load_policy(policy_path)
            default_source = f"{policy.relpath}#defaults"
            self._merge_contract(
                contract,
                policy.payload["defaults"],
                default_source,
                field_sources,
                relaxations,
            )
            local_target = _relative_to_policy(target_relpath, policy.base_relpath)
            matches = _ordered_matching_rules(
                local_target,
                policy.payload["rules"],
                policy.relpath,
            )
            for rule in matches:
                source = f"{policy.relpath}#{rule['id']}"
                self._merge_contract(
                    contract,
                    rule["set"],
                    source,
                    field_sources,
                    relaxations,
                )
                matched_rules.append(source)
                rationale_chain.append(f"{source}: {rule['rationale']}")

        dossier = self._dossier_for(target_relpath)
        if dossier is not None:
            source = f"{self.manifest['knowledge_sources']['dossiers']}#{dossier['id']}"
            lifecycle = str(dossier["lifecycle"])
            if lifecycle in {"historical", "superseded"}:
                _set_scalar(
                    contract,
                    field_sources,
                    "document_class",
                    "historical_evidence",
                    source,
                )
                _set_scalar(contract, field_sources, "authority_role", "evidence_only", source)
                _set_scalar(contract, field_sources, "mutation", "immutable", source)
                _append_values(
                    contract,
                    field_sources,
                    "invariant_refs",
                    ["DOC-INV-002", "DOC-INV-009"],
                    source,
                )
                rationale_chain.append(f"{source}: dossier lifecycle={lifecycle}; retained evidence is immutable.")
            else:
                rationale_chain.append(
                    f"{source}: dossier lifecycle={lifecycle}; evidence may be corrected while active."
                )

        # The bootstrap manifest is the final, non-relaxable framework boundary.
        # A dossier may tighten a framework file to immutable, but it cannot
        # demote that file's framework authority or context requirements.
        framework_matches: list[str] = []
        for record in self.manifest["framework_core"]:
            if not _matches(target_relpath, record["match"]):
                continue
            source = f"{BOOTSTRAP_RELPATH}#framework_core.{record['id']}"
            framework_matches.append(str(record["id"]))
            _set_scalar(contract, field_sources, "document_class", "framework_core", source)
            _set_scalar(contract, field_sources, "authority_role", "framework_definition", source)
            if MUTATION_RANK[str(contract["mutation"])] < MUTATION_RANK["governed"]:
                _set_scalar(contract, field_sources, "mutation", "governed", source)
            if CONTEXT_RANK[str(contract["context_level"])] < CONTEXT_RANK[str(record["context_level"])]:
                _set_scalar(
                    contract,
                    field_sources,
                    "context_level",
                    str(record["context_level"]),
                    source,
                )
            _set_scalar(contract, field_sources, "volatile_facts", "forbidden", source)
            _append_values(contract, field_sources, "invariant_refs", record["invariant_refs"], source)
            _append_values(contract, field_sources, "adr_refs", record["adr_refs"], source)
            _append_values(
                contract,
                field_sources,
                "required_reads",
                [self.manifest["architecture_guide"], self.manifest["maintenance_guide"]],
                source,
            )
            _append_values(contract, field_sources, "after_change", FRAMEWORK_ACTIONS, source)
            rationale_chain.append(f"{source}: {record['rationale']}")

        self._validate_relaxations(relaxations)
        self._validate_effective_contract(target_relpath, contract)
        knowledge = self._knowledge_records(contract["knowledge_refs"], dossier)
        reviews = self._reviews_for_dossier(dossier)
        triage = self._triage_for_dossier(dossier, reviews)
        topics = self._topics_for_dossier(dossier, knowledge)
        invariant_summaries = self._invariant_summaries(contract["invariant_refs"])
        adr_paths = tuple(self.adrs[adr_id] for adr_id in contract["adr_refs"])
        action_ids = list(contract["after_change"])
        if contract["generator_action"] is not None:
            action_ids.insert(0, str(contract["generator_action"]))
        action_commands = self._action_records(_dedupe(action_ids))
        entrypoint = self._entrypoint_for(target_relpath)
        sections = self._sections_for_refs(contract["section_refs"])
        allowed, guidance = _operation_guidance(
            intent, str(contract["mutation"]), (self.root / target_relpath).exists()
        )

        return Resolution(
            target=target_relpath,
            intent=intent,
            exists=(self.root / target_relpath).exists(),
            contract=_deepcopy_json(contract),
            policies=policy_paths,
            matched_rules=tuple(matched_rules),
            rationale_chain=tuple(rationale_chain),
            field_sources={key: tuple(values) for key, values in field_sources.items()},
            framework_matches=tuple(framework_matches),
            entrypoint=entrypoint,
            sections=sections,
            dossier=dict(dossier) if dossier is not None else None,
            reviews=reviews,
            triage=triage,
            ephemeral=(
                dict(self.ephemeral_by_path[target_relpath])
                if target_relpath in self.ephemeral_by_path
                else None
            ),
            topics=topics,
            knowledge=knowledge,
            invariant_summaries=invariant_summaries,
            adr_paths=adr_paths,
            allowed=allowed,
            operation_guidance=guidance,
            action_commands=action_commands,
        )

    def _merge_contract(
        self,
        contract: MutableMapping[str, Any],
        update: Mapping[str, Any],
        source: str,
        field_sources: MutableMapping[str, list[str]],
        relaxations: list[Relaxation],
    ) -> None:
        if "mutation" in update:
            previous = str(contract["mutation"])
            requested = str(update["mutation"])
            if MUTATION_RANK[requested] < MUTATION_RANK[previous]:
                decision_id = update.get("relaxation_decision_id")
                relaxations.append(
                    Relaxation(
                        field="mutation",
                        previous=previous,
                        requested=requested,
                        source=source,
                        decision_id=str(decision_id) if decision_id else None,
                    )
                )
        for key, value in update.items():
            if key in LIST_FIELDS:
                _append_values(contract, field_sources, key, value, source)
            else:
                _set_scalar(contract, field_sources, key, _deepcopy_json(value), source)

    def _validate_relaxations(self, relaxations: Sequence[Relaxation]) -> None:
        for event in relaxations:
            if event.decision_id is None:
                raise DocSystemError(
                    f"{event.source}: mutation relaxation {event.previous} -> {event.requested} "
                    "requires relaxation_decision_id"
                )
            if not self._decision_is_current(event.decision_id):
                raise DocSystemError(
                    f"{event.source}: relaxation decision is absent or not current: {event.decision_id}"
                )
            if not self._decision_authorizes_policy_relaxation(event.decision_id):
                raise DocSystemError(
                    f"{event.source}: current decision does not authorize document-policy "
                    f"relaxation: {event.decision_id}"
                )

    def _validate_effective_contract(self, target: str, contract: Mapping[str, Any]) -> None:
        missing = sorted(COMPLETE_CONTRACT_FIELDS - set(contract))
        if missing:
            raise DocSystemError(f"{target}: effective contract is missing fields: {missing}")
        for section_id in contract["section_refs"]:
            if section_id not in self.sections:
                raise DocSystemError(f"{target}: unknown section reference {section_id}")
        for invariant_id in contract["invariant_refs"]:
            if invariant_id not in self.invariants:
                raise DocSystemError(f"{target}: unknown invariant reference {invariant_id}")
        for adr_id in contract["adr_refs"]:
            if adr_id not in self.adrs:
                raise DocSystemError(f"{target}: unknown ADR reference {adr_id}")
        for action_id in contract["after_change"]:
            if action_id not in self.actions:
                raise DocSystemError(f"{target}: unknown action reference {action_id}")
        generator = contract["generator_action"]
        if generator is not None and generator not in self.actions:
            raise DocSystemError(f"{target}: unknown generator action {generator}")
        if contract["mutation"] == "generator_only":
            if generator is None:
                raise DocSystemError(f"{target}: generator_only path has no generator_action")
            if not contract["source_paths"]:
                raise DocSystemError(f"{target}: generator_only path has no source_paths")
            if target in contract["source_paths"]:
                raise DocSystemError(f"{target}: generated path lists itself as a source")

    def _invariant_summaries(self, ids: Iterable[str]) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            {
                "id": invariant_id,
                "title": self.invariants[invariant_id]["title"],
                "statement": self.invariants[invariant_id]["statement"],
                "short_reason": self.invariants[invariant_id]["short_reason"],
            }
            for invariant_id in ids
        )

    def _action_records(self, ids: Iterable[str]) -> tuple[Mapping[str, str], ...]:
        return tuple(
            {
                "id": action_id,
                "description": str(self.actions[action_id]["description"]),
                "command": str(self.actions[action_id]["command"]),
            }
            for action_id in ids
        )

    # ------------------------------------------------------------------
    # framework inventory and compatibility projection
    # ------------------------------------------------------------------

    def tracked_paths(self) -> tuple[str, ...]:
        if self._tracked_paths_cache is not None:
            return self._tracked_paths_cache
        try:
            top_level = _git_toplevel(self.root)
        except DocSystemError:
            if (self.root / ".git").exists():
                raise
            result = tuple(
                sorted(
                    path.relative_to(self.root).as_posix()
                    for path in self.root.rglob("*")
                    if path.is_file() and ".git" not in path.parts
                )
            )
        else:
            if top_level != self.root:
                raise DocSystemError(f"repo root {self.root} is nested inside Git worktree {top_level}")
            result = tuple(
                sorted(_parse_nul_paths(_run_git(self.root, ["ls-files", "--cached", "-z"])))
            )
        self._tracked_paths_cache = result
        return result

    def visible_paths(self) -> tuple[str, ...]:
        """Tracked paths plus explicitly declared optional workspace overlays."""

        if self._visible_paths_cache is not None:
            return self._visible_paths_cache
        paths = set(self.tracked_paths())
        for relpath in self.workspace_overlay_by_path:
            if (self.root / relpath).is_file():
                paths.add(relpath)
        result = tuple(sorted(paths))
        self._visible_paths_cache = result
        return result

    def projection_paths(self) -> tuple[str, ...]:
        """Tracked inputs allowed to influence tracked generated documentation."""

        if self._projection_paths_cache is not None:
            return self._projection_paths_cache
        overlays = set(self.workspace_overlay_by_path)
        result = tuple(path for path in self.tracked_paths() if path not in overlays)
        self._projection_paths_cache = result
        return result

    def policy_paths(self) -> tuple[str, ...]:
        if self._policy_paths_cache is not None:
            return self._policy_paths_cache
        filename = str(self.manifest["policy_filename"])
        paths = [
            path
            for path in self.tracked_paths()
            if PurePosixPath(path).name == filename and (self.root / path).is_file()
        ]
        result = tuple(sorted(set(paths)))
        self._policy_paths_cache = result
        return result

    def _invalidate_path_inventory(self) -> None:
        self._tracked_paths_cache = None
        self._visible_paths_cache = None
        self._projection_paths_cache = None
        self._policy_paths_cache = None

    def render_legacy_projection(self) -> str:
        projection = self.manifest["legacy_projection"]
        base = self._load_validated(str(projection["base"]), str(projection["base_schema"]))
        rules: list[Mapping[str, Any]] = []
        notes: list[Mapping[str, Any]] = []
        for policy_path in self.policy_paths():
            payload = self._load_policy(policy_path).payload
            legacy = payload.get("legacy_projection")
            if not isinstance(legacy, dict):
                continue
            rules.extend(legacy["rules"])
            notes.extend(legacy["out_of_scope_notes"])

        _ensure_unique(rules, "id", "legacy projection rules")
        _ensure_unique(notes, "pattern", "legacy out-of-scope notes")
        markdown_paths = tuple(path for path in self.projection_paths() if path.endswith(".md"))
        # A typed workbench may intentionally be empty.  Do not emit an empty
        # compatibility-scan exemption, because the legacy scanner treats
        # no-match patterns as stale configuration.  The note appears
        # automatically as soon as a matching Markdown file is visible.
        active_notes = [
            note
            for note in notes
            if any(_glob_match(path, str(note["pattern"])) for path in markdown_paths)
        ]
        payload = {
            "schema_version": base["output_schema_version"],
            "authority": base["authority"],
            "document_classes": base["document_classes"],
            "scan_scope": {
                "include_globs": sorted(base["scan_scope"]["include_globs"]),
                "exclude_globs": sorted(base["scan_scope"]["exclude_globs"]),
                "out_of_scope_notes": sorted(active_notes, key=lambda item: str(item["pattern"])),
            },
            "rules": sorted(rules, key=lambda item: str(item["id"])),
            "reference_scan": base["reference_scan"],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    def write_legacy_projection(self) -> None:
        output = self.root / str(self.manifest["legacy_projection"]["output"])
        _atomic_write(output, self.render_legacy_projection())
        self._invalidate_path_inventory()

    def _guidance_records(self) -> tuple[Mapping[str, Any], ...]:
        projection = self.manifest["guidance_projection"]
        included = {str(value) for value in projection["include_document_classes"]}
        excluded = {str(value) for value in projection["exclude_paths"]}
        output = str(projection["output"])
        records: list[Mapping[str, Any]] = []
        for relpath in self.projection_paths():
            if not relpath.endswith(".md") or relpath == output or relpath in excluded:
                continue
            resolution = self.resolve(relpath, "read")
            contract = resolution.contract
            if str(contract["document_class"]) not in included:
                continue
            records.append(
                {
                    "path": relpath,
                    "document_class": str(contract["document_class"]),
                    "authority_role": str(contract["authority_role"]),
                    "mutation": str(contract["mutation"]),
                    "context_level": str(contract["context_level"]),
                    "section_refs": tuple(str(value) for value in contract["section_refs"]),
                    "purpose": str(contract["purpose"]),
                }
            )
        return tuple(sorted(records, key=lambda record: str(record["path"])))

    def render_guidance_projection(self) -> str:
        projection = self.manifest["guidance_projection"]
        output = str(projection["output"])
        output_parent = (self.root / output).parent
        records = self._guidance_records()
        digest_payload = json.dumps(
            {
                "guidance": records,
                "entrypoints": self.entrypoints_payload,
                "sections": self.sections_payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()

        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in records:
            grouped[str(record["document_class"])].append(record)

        class_order = [
            "locked_authority",
            "generated_projection",
            "normative",
            "living",
            "structured_knowledge",
            "governance_control",
            "framework_core",
        ]
        class_titles = {
            "locked_authority": "锁定权威入口",
            "generated_projection": "自动生成查询页",
            "normative": "现行规范与契约",
            "living": "活跃说明与操作入口",
            "structured_knowledge": "结构化知识入口",
            "governance_control": "治理控制面",
            "framework_core": "文档框架核心",
        }

        lines = [
            "# 当前文档职责索引",
            "",
            "> 本页由有效 `DOC_POLICY.json` 契约、前门注册表与 section registry 自动生成；禁止手工修改。",
            f"> 文档系统版本：`{self.manifest['system_version']}`；职责摘要：`sha256:{digest}`。",
            "",
            "本页回答“哪些文档仍承担当前职责、各自唯一负责什么”。它不授予新的 authority，也不列历史证据；历史 dossier 与快照分别从 CATALOG、BACKFILL_LEDGER 和 `docs/history/` 下钻。",
            "",
            "## 使用边界",
            "",
            "- `generated_projection` 只能修改结构化源后重建。",
            "- `locked_authority` 只按 owner / freeze 协议改变。",
            "- `normative` 保存稳定契约，不复制 CURRENT 中的易变状态。",
            "- `living` 解释怎样理解和怎样做，当前值仍回到 CURRENT 或机器源。",
            "- 修改任一路径前先运行 `docctl context <path> --intent edit`。",
            "- 按局部问题域进入时先看 [SECTION_INDEX](SECTION_INDEX.md)；本页是全量职责投影。",
            "",
            "## 固定入口图",
            "",
            "这些入口的职责、注意力预算和兼容跳转来自机器可读前门注册表。",
            "",
            "| ID | 类型 | 路径 | 预算 | 唯一职责 |",
            "|---|---|---|---:|---|",
        ]
        for record in sorted(self.entrypoint_surfaces.values(), key=lambda value: str(value["id"])):
            path = str(record["path"])
            target = os.path.relpath(self.root / path, start=output_parent).replace(os.sep, "/")
            budget = "—"
            if record.get("max_lines") is not None:
                budget = f"{record['max_lines']} 行"
            purpose = str(record["purpose"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{record['id']}` | `{record['mode']}` | [`{path}`](<{target}>) | {budget} | {purpose} |")
        for record in sorted(self.entrypoint_guards.values(), key=lambda value: str(value["id"])):
            path = str(record["path"])
            target = os.path.relpath(self.root / path, start=output_parent).replace(os.sep, "/")
            purpose = str(record["purpose"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{record['id']}` | `guarded_document` | [`{path}`](<{target}>) | — | {purpose} |")
        for record in sorted(self.entrypoint_redirects.values(), key=lambda value: str(value["id"])):
            path = str(record["path"])
            target = os.path.relpath(self.root / path, start=output_parent).replace(os.sep, "/")
            summary = str(record["summary"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{record['id']}` | `generated_redirect` | [`{path}`](<{target}>) | — | {summary} |")

        lines.extend(
            (
                "",
                "## 当前分区",
                "",
                "分区是真正按问题组织的局部入口；完整成员清单见 [SECTION_INDEX](SECTION_INDEX.md)。",
                "",
                "| Section | 局部入口 | 类型 | 唯一职责 |",
                "|---|---|---|---|",
            )
        )
        for record in self.sections_payload["records"]:
            path = str(record["entry_path"])
            target = os.path.relpath(self.root / path, start=output_parent).replace(os.sep, "/")
            purpose = str(record["purpose"]).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| `{record['id']}` | [`{path}`](<{target}>) | `{record['entry_kind']}` | {purpose} |"
            )

        lines.extend(
            (
                "",
                "## 总览",
                "",
                "| 类别 | 数量 |",
                "|---|---:|",
            )
        )
        for document_class in class_order:
            if grouped.get(document_class):
                lines.append(f"| `{document_class}` | {len(grouped[document_class])} |")

        for document_class in class_order:
            class_records = grouped.get(document_class, [])
            if not class_records:
                continue
            lines.extend(
                (
                    "",
                    f"## {class_titles[document_class]}",
                    "",
                    "| 文档 | Section | Authority | Mutation | 唯一职责 |",
                    "|---|---|---|---|---|",
                )
            )
            for record in class_records:
                target = os.path.relpath(self.root / str(record["path"]), start=output_parent).replace(os.sep, "/")
                purpose = str(record["purpose"]).replace("|", "\\|").replace("\n", " ")
                sections = ", ".join(f"`{value}`" for value in record["section_refs"]) or "—"
                lines.append(
                    f"| [`{record['path']}`](<{target}>) | {sections} | `{record['authority_role']}` | "
                    f"`{record['mutation']}` | {purpose} |"
                )

        lines.extend(
            (
                "",
                "当前机器状态见 [CURRENT](CURRENT.md)，按分区进入见 [SECTION_INDEX](SECTION_INDEX.md)，开放问题见 [OPEN_QUESTIONS](OPEN_QUESTIONS.md)，按任务进入见 [START_HERE](START_HERE.md)，历史材料见 [CATALOG](CATALOG.md) 与 [history](history/README.md)。",
                "",
            )
        )
        return "\n".join(lines)

    def write_guidance_projection(self) -> None:
        output = self.root / str(self.manifest["guidance_projection"]["output"])
        _atomic_write(output, self.render_guidance_projection())
        self._invalidate_path_inventory()

    def render_section_projection(self) -> str:
        """Render the global map of explicit current-document sections."""

        output = str(self.manifest["section_projection"]["output"])
        output_parent = (self.root / output).parent
        records = self._guidance_records()
        members: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in records:
            for section_id in record["section_refs"]:
                members[str(section_id)].append(record)

        digest_payload = json.dumps(
            {"sections": self.sections_payload, "members": members},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
        source_relpath = str(self.manifest["section_registry"]["source"])
        source_href = os.path.relpath(self.root / source_relpath, start=output_parent).replace(os.sep, "/")

        lines = [
            "# 当前文档分区索引",
            "",
            "> 本页由 section registry 与有效 `DOC_POLICY.json` 自动生成；禁止手工修改。",
            f"> 文档系统版本：`{self.manifest['system_version']}`；分区摘要：`sha256:{digest}`。",
            f"> 真源：[`{source_relpath}`](<{source_href}>)。",
            "",
            "分区把当前文档按问题域组织起来。它不改变 authority，也不把历史 evidence 提升为现行说明。一个文档可以跨多个分区，但每个分区只有一个登记入口。",
            "",
            "按任务选择入口见 [START_HERE](START_HERE.md)；按职责类型查看完整 current surface 见 [GUIDANCE_INDEX](GUIDANCE_INDEX.md)。",
            "",
            "## 分区总览",
            "",
            "| Section | 入口 | 类型 | 当前成员 | 唯一职责 |",
            "|---|---|---|---:|---|",
        ]
        for section in self.sections_payload["records"]:
            section_id = str(section["id"])
            entry_path = str(section["entry_path"])
            href = os.path.relpath(self.root / entry_path, start=output_parent).replace(os.sep, "/")
            purpose = str(section["purpose"]).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| `{section_id}` | [`{entry_path}`](<{href}>) | `{section['entry_kind']}` | "
                f"{len(members.get(section_id, []))} | {purpose} |"
            )

        for section in self.sections_payload["records"]:
            section_id = str(section["id"])
            entry_path = str(section["entry_path"])
            entry_href = os.path.relpath(self.root / entry_path, start=output_parent).replace(os.sep, "/")
            related = ", ".join(f"`{value}`" for value in section["related_section_ids"]) or "无"
            lines.extend(
                (
                    "",
                    f"## {section['title']} (`{section_id}`)",
                    "",
                    f"入口：[`{entry_path}`](<{entry_href}>)；类型：`{section['entry_kind']}`；关联分区：{related}。",
                    "",
                    str(section["purpose"]),
                    "",
                    "| 文档 | Class | Mutation | 唯一职责 |",
                    "|---|---|---|---|",
                )
            )
            for record in members.get(section_id, []):
                path = str(record["path"])
                href = os.path.relpath(self.root / path, start=output_parent).replace(os.sep, "/")
                purpose = str(record["purpose"]).replace("|", "\\|").replace("\n", " ")
                marker = " **（入口）**" if path == entry_path else ""
                lines.append(
                    f"| [`{path}`](<{href}>){marker} | `{record['document_class']}` | "
                    f"`{record['mutation']}` | {purpose} |"
                )

        lines.extend(
            (
                "",
                "修改分区、入口或成员归属时，先改 section registry / local policy，再运行：",
                "",
                "```bash",
                str(self.actions["docsystem.render_sections"]["command"]),
                str(self.actions["docsystem.render_guidance"]["command"]),
                "```",
                "",
            )
        )
        return "\n".join(lines)

    def write_section_projection(self) -> None:
        output = self.root / str(self.manifest["section_projection"]["output"])
        _atomic_write(output, self.render_section_projection())
        self._invalidate_path_inventory()

    def _convergence_records(self) -> tuple[Mapping[str, Any], ...]:
        """Return every current Markdown contract, including generated index outputs."""

        projection = self.manifest["guidance_projection"]
        included = {str(value) for value in projection["include_document_classes"]}
        excluded = {str(value) for value in projection["exclude_paths"]}
        records: list[Mapping[str, Any]] = []
        for relpath in self.projection_paths():
            if not relpath.endswith(".md") or relpath in excluded:
                continue
            resolution = self.resolve(relpath, "read")
            contract = resolution.contract
            if str(contract["document_class"]) not in included:
                continue
            records.append(
                {
                    "path": relpath,
                    "document_class": str(contract["document_class"]),
                    "authority_role": str(contract["authority_role"]),
                    "mutation": str(contract["mutation"]),
                    "context_level": str(contract["context_level"]),
                    "volatile_facts": str(contract["volatile_facts"]),
                    "section_refs": tuple(str(value) for value in contract["section_refs"]),
                    "purpose": str(contract["purpose"]),
                }
            )
        return tuple(sorted(records, key=lambda record: str(record["path"])))

    def _effective_responsibility(self, record: Mapping[str, Any]) -> str:
        relpath = str(record["path"])
        entrypoint = self.entrypoint_by_path.get(relpath)
        if entrypoint is None:
            return str(record["purpose"])
        if entrypoint["kind"] == "redirect":
            return str(entrypoint["summary"])
        return str(entrypoint["purpose"])

    def convergence_audit(self) -> Mapping[str, Any]:
        """Audit the current document graph and responsibility boundaries."""

        records = self._convergence_records()
        record_by_path = {str(record["path"]): record for record in records}
        current_paths = set(record_by_path)
        redirect_paths = {str(record["path"]) for record in self.entrypoint_redirects.values()}
        failures: list[str] = []

        section_rows: list[Mapping[str, Any]] = []
        for section_id, section in self.sections.items():
            members = {
                path
                for path, record in record_by_path.items()
                if section_id in record["section_refs"] and path not in redirect_paths
            }
            entry_path = str(section["entry_path"])
            reachable: set[str] = set()
            pending = [entry_path]
            while pending:
                relpath = pending.pop()
                if relpath in reachable or relpath not in members:
                    continue
                reachable.add(relpath)
                try:
                    text = (self.root / relpath).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    failures.append(f"cannot read current section member {relpath}: {exc}")
                    continue
                for target in _markdown_link_targets(self.root, relpath, text):
                    if target in members and target not in reachable:
                        pending.append(target)
            missing = tuple(sorted(members - reachable))
            if entry_path not in members:
                failures.append(f"section {section_id} entry is not a current member: {entry_path}")
            for relpath in missing:
                failures.append(
                    f"section {section_id} current member is unreachable from {entry_path}: {relpath}"
                )
            section_rows.append(
                {
                    "id": section_id,
                    "entry_path": entry_path,
                    "member_count": len(members),
                    "reachable_count": len(reachable),
                    "unreachable": missing,
                }
            )

        purpose_owners: dict[str, list[str]] = defaultdict(list)
        for record in records:
            if str(record["document_class"]) == "generated_projection":
                continue
            if str(record["mutation"]) in {"immutable", "owner_only"}:
                continue
            purpose = " ".join(self._effective_responsibility(record).split()).casefold()
            purpose_owners[purpose].append(str(record["path"]))
        duplicate_purposes: list[Mapping[str, Any]] = []
        for purpose, paths in sorted(purpose_owners.items()):
            if len(paths) < 2:
                continue
            duplicate_purposes.append({"purpose": purpose, "paths": tuple(sorted(paths))})
            failures.append(
                "current mutable documents share one responsibility: " + ", ".join(sorted(paths))
            )

        compiled_patterns: list[tuple[str, re.Pattern[str]]] = []
        for pattern_value in self.entrypoints_payload["common_forbidden_patterns"]:
            pattern = str(pattern_value)
            try:
                compiled_patterns.append((pattern, re.compile(pattern, re.MULTILINE)))
            except re.error as exc:
                failures.append(f"entrypoint forbidden pattern is invalid {pattern!r}: {exc}")

        volatile_matches: list[Mapping[str, str]] = []
        redirect_links: list[Mapping[str, str]] = []
        for record in records:
            relpath = str(record["path"])
            if str(record["document_class"]) == "generated_projection":
                continue
            try:
                text = (self.root / relpath).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                failures.append(f"cannot read current document {relpath}: {exc}")
                continue

            if str(record["volatile_facts"]) in {"reference_only", "forbidden"}:
                for pattern, regex in compiled_patterns:
                    match = regex.search(text)
                    if match is None:
                        continue
                    volatile_matches.append(
                        {"path": relpath, "pattern": pattern, "match": match.group(0)}
                    )
                    failures.append(
                        f"current document {relpath} copies volatile state: "
                        f"pattern {pattern!r} matched {match.group(0)!r}"
                    )

            for target in sorted(_markdown_link_targets(self.root, relpath, text) & redirect_paths):
                redirect_links.append({"path": relpath, "target": target})
                failures.append(
                    f"current document {relpath} routes through retired compatibility entrypoint {target}"
                )

        return {
            "system_version": str(self.manifest["system_version"]),
            "current_document_count": len(records),
            "section_count": len(self.sections),
            "redirect_count": len(redirect_paths),
            "sections": tuple(section_rows),
            "duplicate_purposes": tuple(duplicate_purposes),
            "volatile_matches": tuple(volatile_matches),
            "redirect_links": tuple(redirect_links),
            "failures": tuple(_dedupe(failures)),
            "current_paths": tuple(sorted(current_paths)),
        }

    def render_convergence_projection(self) -> str:
        """Render the Phase 3 current-document convergence acceptance report."""

        audit = self.convergence_audit()
        status = "PASS" if not audit["failures"] else "BLOCKED"
        digest_payload = json.dumps(
            audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
        lines = [
            "# 文档职责收束验收报告",
            "",
            "> 本页由当前 `DOC_POLICY.json`、前门注册表、section registry 与 Markdown 链接图自动生成；禁止手工修改。",
            f"> 文档系统版本：`{audit['system_version']}`；验收状态：`{status}`；审计摘要：`sha256:{digest}`。",
            "",
            "本页回答第三阶段是否已经消除局部孤岛、重复职责、手写易变状态和经退役入口下钻。它不授予项目 authority，也不把历史证据提升为 current。",
            "",
            "## 验收总览",
            "",
            "| 项目 | 结果 |",
            "|---|---:|",
            f"| current Markdown | {audit['current_document_count']} |",
            f"| 显式 section | {audit['section_count']} |",
            f"| 生成式兼容入口 | {audit['redirect_count']} |",
            f"| 重复 current 职责组 | {len(audit['duplicate_purposes'])} |",
            f"| 手写易变状态命中 | {len(audit['volatile_matches'])} |",
            f"| current → retired redirect 链接 | {len(audit['redirect_links'])} |",
            f"| 阻断项 | {len(audit['failures'])} |",
            "",
            "## Section 局部可达性",
            "",
            "每个非兼容跳转的 current 成员都必须从它声明的局部入口，经同一 section 内的 current Markdown 链接可达。",
            "",
            "| Section | 入口 | 成员 | 可达 | 不可达 |",
            "|---|---|---:|---:|---:|",
        ]
        for row in audit["sections"]:
            lines.append(
                f"| `{row['id']}` | `{row['entry_path']}` | {row['member_count']} | "
                f"{row['reachable_count']} | {len(row['unreachable'])} |"
            )

        lines.extend(("", "## 阻断项", ""))
        if audit["failures"]:
            for failure in audit["failures"]:
                lines.append(f"- {failure}")
        else:
            lines.append("- 无。当前职责图满足登记的第三阶段收束不变量。")

        lines.extend(
            (
                "",
                "## 保留边界",
                "",
                "- `PASS` 只表示当前文档职责层通过本页列出的结构验收，不表示数学结论、phase gate、release 或 certification 通过。",
                "- 历史文档可以保留旧状态、哈希和收据；它们不进入 current 图。",
                "- 新 current 文档仍必须先获得精确 policy、section 归属和局部入口链接。",
                "- 改变检查语义时必须更新不变量、ADR、架构、维护指南、迁移与测试。",
                "",
                "重建并验收：",
                "",
                "```bash",
                str(self.actions["docsystem.render_convergence"]["command"]),
                str(self.actions["docsystem.doctor"]["command"]),
                "```",
                "",
            )
        )
        return "\n".join(lines)

    def write_convergence_projection(self) -> None:
        output = self.root / str(self.manifest["convergence_projection"]["output"])
        _atomic_write(output, self.render_convergence_projection())
        self._invalidate_path_inventory()

    def maintenance_queue_snapshot(self) -> Mapping[str, Any]:
        """Return the deterministic phase-close queue used by the generated projection."""

        as_of = parse_audit_date(str(self.maintenance_audit_payload["snapshot_as_of"]))
        return run_maintenance_audit(self, profile="phase_close", as_of=as_of).as_dict()

    def render_maintenance_projection(self) -> str:
        """Render the periodic maintenance queue from existing truth sources."""

        snapshot = self.maintenance_queue_snapshot()
        counts = snapshot["counts"]
        lines = [
            "# 文档维护队列",
            "",
            "> 本页由周期审计注册表、policy、知识账本和生命周期真源自动生成；禁止手工修改。",
            f"> 文档系统版本：`{self.manifest['system_version']}`；快照日期：`{snapshot['as_of']}`；profile：`{snapshot['profile']}`。",
            "",
            "本页只投影维护触发器。它不建立第二套 current 状态、claim、review、triage 或 owner authority。接受某条 finding 后，仍须通过原有 intake、knowledge 或 policy 写入路径完成修复。",
            "",
            "## 总览",
            "",
            "| 严重度 | 数量 |",
            "|---|---:|",
            f"| error | {counts['error']} |",
            f"| warning | {counts['warning']} |",
            f"| info | {counts['info']} |",
            "",
            "## Findings",
            "",
            "| 严重度 | 检查 | 对象 | 触发器 | 后续动作 |",
            "|---|---|---|---|---|",
        ]
        for finding in snapshot["findings"]:
            action_ids = "<br>".join(f"`{value}`" for value in finding["action_ids"]) or "—"
            lines.append(
                "| "
                + " | ".join(
                    (
                        f"`{finding['severity']}`",
                        f"`{finding['check_id']}`",
                        f"`{_markdown_cell(str(finding['subject']))}`",
                        _markdown_cell(str(finding["message"])),
                        action_ids,
                    )
                )
                + " |"
            )
        lines.extend(
            (
                "",
                "## 维护边界",
                "",
                "- `info` 是显式队列，不自动变成失败；`warning` 与 `error` 是否阻断由所选 profile 的 `fail_on` 决定。",
                "- Git 最近触达日期只是重审触发器，不证明语义已复核。",
                "- inventory coverage 不等于 semantic review；open claim 也不是机械故障。",
                "- 周期审计只发现遗漏、陈旧、碰撞和待办；所有修复都回到同一事件驱动写入管道。",
                "",
                "重建与复核：",
                "",
                "```bash",
                str(self.actions["docsystem.render_maintenance"]["command"]),
                str(self.actions["docsystem.audit"]["command"]),
                str(self.actions["docsystem.audit_deep"]["command"]),
                "```",
                "",
            )
        )
        return "\n".join(lines)

    def write_maintenance_projection(self) -> None:
        output = self.root / str(self.manifest["maintenance_audit"]["projection"])
        _atomic_write(output, self.render_maintenance_projection())
        self._invalidate_path_inventory()

    def _entrypoint_source_relpath(self) -> str:
        return str(self.manifest["entrypoint_registry"]["source"])

    def _render_entrypoint_redirect(self, record: Mapping[str, Any]) -> str:
        output_relpath = str(record["path"])
        output_parent = (self.root / output_relpath).parent
        source_relpath = self._entrypoint_source_relpath()
        source_target = os.path.relpath(
            self.root / source_relpath,
            start=output_parent,
        ).replace(os.sep, "/")

        lines = [
            f"# {record['title']}",
            "",
            "> 本页由文档系统的前门注册表自动生成；禁止手工修改。",
            f"> 真源：[`{source_relpath}`]({source_target})。",
            "",
            str(record["summary"]),
            "",
            "## 当前入口",
            "",
        ]
        for target in record["targets"]:
            target_relpath = str(target["path"])
            href = os.path.relpath(
                self.root / target_relpath,
                start=output_parent,
            ).replace(os.sep, "/")
            lines.append(f"- [{target['label']}]({href})：{target['description']}")

        lines.extend(("", "## 维护边界", ""))
        for note in record["boundary_notes"]:
            lines.append(f"- {note}")
        archive = record.get("archive_path")
        if archive is not None:
            archive_relpath = str(archive)
            archive_href = os.path.relpath(
                self.root / archive_relpath,
                start=output_parent,
            ).replace(os.sep, "/")
            lines.append(f"- 退出当前职责前的正文见 [历史快照]({archive_href})；它只保留当时叙述。")

        lines.extend(
            (
                "",
                "需要改变本页时，修改前门注册表后运行：",
                "",
                "```bash",
                str(self.actions["docsystem.render_entrypoints"]["command"]),
                "```",
                "",
            )
        )
        return "\n".join(lines)

    def render_entrypoint_redirects(self) -> Mapping[str, str]:
        return {
            str(record["path"]): self._render_entrypoint_redirect(record)
            for record in sorted(
                self.entrypoint_redirects.values(),
                key=lambda value: str(value["path"]),
            )
        }

    def write_entrypoint_redirects(self) -> None:
        for relpath, content in self.render_entrypoint_redirects().items():
            _atomic_write(self.root / relpath, content)
        self._invalidate_path_inventory()

    def _check_entrypoints(self) -> list[str]:
        failures: list[str] = []
        if self.entrypoints_payload["system_version"] != self.manifest["system_version"]:
            failures.append("manifest and entrypoint registry system_version differ")

        surface_records = tuple(self.entrypoint_surfaces.values())
        redirect_records = tuple(self.entrypoint_redirects.values())
        guard_records = tuple(self.entrypoint_guards.values())
        groups = {
            "canonical surface": surface_records,
            "compatibility redirect": redirect_records,
            "guarded document": guard_records,
        }

        id_owners: dict[str, str] = {}
        path_owners: dict[str, str] = {}
        for label, records in groups.items():
            for record in records:
                identifier = str(record["id"])
                relpath = str(record["path"])
                previous_id = id_owners.get(identifier)
                if previous_id is not None:
                    failures.append(f"entrypoint registry reuses id {identifier}: {previous_id}, {label}")
                else:
                    id_owners[identifier] = label
                previous_path = path_owners.get(relpath)
                if previous_path is not None:
                    failures.append(f"entrypoint registry assigns path {relpath} twice: {previous_path}, {label}")
                else:
                    path_owners[relpath] = label

        required_surface_ids = {
            "repository_front_door",
            "agent_operations",
            "documentation_front_door",
            "task_router",
            "project_manual_front_door",
            "current_state",
            "current_guidance_surface",
            "document_sections",
            "certified_authority",
        }
        missing_surface_ids = sorted(required_surface_ids - set(self.entrypoint_surfaces))
        if missing_surface_ids:
            failures.append("entrypoint registry omits required canonical surfaces: " + ", ".join(missing_surface_ids))

        compiled_patterns: list[tuple[str, re.Pattern[str]]] = []
        for pattern in self.entrypoints_payload["common_forbidden_patterns"]:
            try:
                compiled_patterns.append((str(pattern), re.compile(str(pattern), re.MULTILINE)))
            except re.error as exc:
                failures.append(f"entrypoint forbidden pattern is invalid {pattern!r}: {exc}")

        def read_guarded_text(relpath: str, label: str) -> str | None:
            path = self.root / relpath
            if not path.is_file():
                failures.append(f"{label} is missing: {relpath}")
                return None
            try:
                return path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                failures.append(f"cannot read {label} {relpath}: {exc}")
                return None

        def check_required_targets(relpath: str, text: str, targets: Iterable[Any], label: str) -> None:
            linked_targets = _markdown_link_targets(self.root, relpath, text)
            for configured_target in targets:
                target = str(configured_target)
                if not (self.root / target).exists():
                    failures.append(f"{label} {relpath} requires missing target {target}")
                elif target not in linked_targets:
                    failures.append(f"{label} {relpath} does not link required target {target}")

        def check_forbidden_patterns(relpath: str, text: str, label: str) -> None:
            for pattern, regex in compiled_patterns:
                match = regex.search(text)
                if match is not None:
                    failures.append(
                        f"{label} {relpath} copies volatile state: pattern {pattern!r} matched {match.group(0)!r}"
                    )

        for record in surface_records:
            relpath = str(record["path"])
            text = read_guarded_text(relpath, "canonical entrypoint surface")
            if text is None:
                continue
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue

            mode = str(record["mode"])
            contract = resolution.contract
            if mode == "manual":
                if contract["document_class"] not in {"living", "normative", "framework_core"}:
                    failures.append(f"manual entrypoint {relpath} has incompatible class {contract['document_class']}")
                if contract["mutation"] in {"generator_only", "owner_only", "immutable"}:
                    failures.append(f"manual entrypoint {relpath} has incompatible mutation {contract['mutation']}")
                line_count = len(text.splitlines())
                byte_count = len(text.encode("utf-8"))
                max_lines = int(record["max_lines"])
                max_bytes = int(record["max_bytes"])
                if line_count > max_lines:
                    failures.append(
                        f"manual entrypoint attention budget exceeded: {relpath} has "
                        f"{line_count} lines, limit {max_lines}"
                    )
                if byte_count > max_bytes:
                    failures.append(
                        f"manual entrypoint attention budget exceeded: {relpath} has "
                        f"{byte_count} bytes, limit {max_bytes}"
                    )
            elif mode == "generated":
                if contract["document_class"] != "generated_projection":
                    failures.append(f"generated entrypoint lost projection class: {relpath}")
                if contract["mutation"] != "generator_only":
                    failures.append(f"generated entrypoint lost generator-only mutation: {relpath}")
            elif mode == "authority":
                if contract["document_class"] != "locked_authority":
                    failures.append(f"authority entrypoint lost locked class: {relpath}")
                if contract["mutation"] != "owner_only":
                    failures.append(f"authority entrypoint lost owner-only mutation: {relpath}")

            check_required_targets(relpath, text, record["required_targets"], "canonical entrypoint")
            if bool(record["enforce_common_forbidden_patterns"]):
                check_forbidden_patterns(relpath, text, "canonical entrypoint")

        for record in guard_records:
            relpath = str(record["path"])
            text = read_guarded_text(relpath, "guarded document")
            if text is None:
                continue
            check_required_targets(relpath, text, record["required_targets"], "guarded document")
            if bool(record["enforce_common_forbidden_patterns"]):
                check_forbidden_patterns(relpath, text, "guarded document")

        source_relpath = self._entrypoint_source_relpath()
        expected_redirects = self.render_entrypoint_redirects()
        for record in redirect_records:
            relpath = str(record["path"])
            for target in record["targets"]:
                target_relpath = str(target["path"])
                if not (self.root / target_relpath).exists():
                    failures.append(f"entrypoint redirect {relpath} targets missing path: {target_relpath}")
            archive = record.get("archive_path")
            if archive is not None and not (self.root / str(archive)).is_file():
                failures.append(f"entrypoint redirect {relpath} archive is missing: {archive}")
            try:
                resolution = self.resolve(relpath, "edit")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            contract = resolution.contract
            if contract["document_class"] != "generated_projection":
                failures.append(f"compatibility redirect is not generated_projection: {relpath}")
            if contract["mutation"] != "generator_only":
                failures.append(f"compatibility redirect is not generator_only: {relpath}")
            if contract["generator_action"] != "docsystem.render_entrypoints":
                failures.append(f"compatibility redirect uses wrong generator action: {relpath}")
            if source_relpath not in contract["source_paths"]:
                failures.append(f"compatibility redirect omits entrypoint registry source: {relpath}")
            try:
                actual = (self.root / relpath).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                failures.append(f"cannot read compatibility redirect {relpath}: {exc}")
                continue
            check_forbidden_patterns(relpath, actual, "compatibility redirect")
            if actual != expected_redirects[relpath]:
                failures.append(
                    "compatibility redirect is stale: "
                    f"{relpath}; run {self.actions['docsystem.render_entrypoints']['command']}"
                )

        return failures

    # ------------------------------------------------------------------
    # doctor and diff-aware checking
    # ------------------------------------------------------------------

    def doctor(self) -> tuple[str, ...]:
        failures: list[str] = []
        failures.extend(self._check_manifest_references())
        failures.extend(self._check_adr_registry())
        failures.extend(self._check_invariants())
        failures.extend(self._check_policies())
        failures.extend(self._check_markdown_coverage())
        failures.extend(self._check_workspace_overlays())
        failures.extend(self._check_framework_core())
        failures.extend(self._check_sections())
        failures.extend(self._check_legacy_projection())
        failures.extend(self._check_guidance_projection())
        failures.extend(self._check_section_projection())
        failures.extend(self._check_entrypoints())
        failures.extend(self._check_convergence_projection())
        failures.extend(self._check_governance_gate())
        failures.extend(self._check_test_timing_receipt())
        failures.extend(self._check_intake_protocol())
        failures.extend(self._check_maintenance_audit())
        failures.extend(self._check_landing_protocol())
        failures.extend(self._check_guides())
        return tuple(_dedupe(failures))

    def _check_manifest_references(self) -> list[str]:
        failures: list[str] = []
        path_fields = (
            "root_policy",
            "architecture_guide",
            "maintenance_guide",
            "steady_state_guide",
            "recovery_guide",
            "decision_directory",
            "manifest_schema",
            "policy_schema",
            "invariants",
            "invariants_schema",
        )
        for field in path_fields:
            path = self.root / str(self.manifest[field])
            if not path.exists():
                failures.append(f"manifest.{field} does not exist: {self.manifest[field]}")
        for field, relpath in self.manifest["legacy_projection"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.legacy_projection.{field} is missing: {relpath}")
        for field, relpath in self.manifest["entrypoint_registry"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.entrypoint_registry.{field} is missing: {relpath}")
        for field, relpath in self.manifest["section_registry"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.section_registry.{field} is missing: {relpath}")
        guidance_output = str(self.manifest["guidance_projection"]["output"])
        if not (self.root / guidance_output).is_file():
            failures.append(f"manifest.guidance_projection.output is missing: {guidance_output}")
        section_output = str(self.manifest["section_projection"]["output"])
        if not (self.root / section_output).is_file():
            failures.append(f"manifest.section_projection.output is missing: {section_output}")
        convergence_output = str(self.manifest["convergence_projection"]["output"])
        if not (self.root / convergence_output).is_file():
            failures.append(f"manifest.convergence_projection.output is missing: {convergence_output}")
        for field, relpath in self.manifest["governance_gate"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.governance_gate.{field} is missing: {relpath}")
        for field, relpath in self.manifest["intake_protocol"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.intake_protocol.{field} is missing: {relpath}")
        for field, relpath in self.manifest["maintenance_audit"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.maintenance_audit.{field} is missing: {relpath}")
        for field, relpath in self.manifest["landing_protocol"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.landing_protocol.{field} is missing: {relpath}")
        for field, relpath in self.intake_payload["ephemeral_documents"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"intake.ephemeral_documents.{field} is missing: {relpath}")
        for field, relpath in self.manifest["knowledge_sources"].items():
            if not (self.root / str(relpath)).is_file():
                failures.append(f"manifest.knowledge_sources.{field} is missing: {relpath}")
        for adr_id, relpath in self.adrs.items():
            path = self.root / relpath
            if not path.is_file():
                failures.append(f"{adr_id} path is missing: {relpath}")
        return failures

    def _check_adr_registry(self) -> list[str]:
        failures: list[str] = []
        directory = _normalise_relpath(str(self.manifest["decision_directory"]))
        registered_paths = list(self.adrs.values())
        if len(registered_paths) != len(set(registered_paths)):
            failures.append("manifest.adrs maps multiple IDs to the same path")

        visible_adr_paths = {
            relpath
            for relpath in self.tracked_paths()
            if PurePosixPath(relpath).parent.as_posix() == directory
            and PurePosixPath(relpath).suffix == ".md"
            and PurePosixPath(relpath).name != "README.md"
        }
        registered_set = set(registered_paths)
        for relpath in sorted(visible_adr_paths):
            if not re.fullmatch(r"[0-9]{3}-.+\.md", PurePosixPath(relpath).name):
                failures.append(f"framework ADR has invalid filename: {relpath}")
            if relpath not in registered_set:
                failures.append(f"unregistered framework ADR: {relpath}")

        for adr_id, relpath in self.adrs.items():
            path = PurePosixPath(relpath)
            number = adr_id.rsplit("-", 1)[-1]
            if path.parent.as_posix() != directory:
                failures.append(f"{adr_id} lies outside decision_directory: {relpath}")
            if not path.name.startswith(f"{number}-"):
                failures.append(f"{adr_id} path number does not match its ID: {relpath}")
            absolute = self.root / relpath
            if not absolute.is_file():
                continue
            try:
                text = absolute.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                failures.append(f"cannot read {adr_id} at {relpath}: {exc}")
                continue
            if adr_id not in text:
                failures.append(f"{adr_id} body does not name its stable ID: {relpath}")
            if "状态：Accepted" not in text:
                failures.append(f"{adr_id} is registered but not marked Accepted: {relpath}")
        return failures

    def _check_invariants(self) -> list[str]:
        failures: list[str] = []
        if self.invariants_payload["system_version"] != self.manifest["system_version"]:
            failures.append("manifest and invariant registry system_version differ")
        for invariant_id, record in self.invariants.items():
            for relpath in record["enforced_by"]:
                if not (self.root / str(relpath)).exists():
                    failures.append(f"{invariant_id}.enforced_by is missing: {relpath}")
            for adr_id in record["adr_refs"]:
                if adr_id not in self.adrs:
                    failures.append(f"{invariant_id} references unknown ADR {adr_id}")
        return failures

    def _check_sections(self) -> list[str]:
        failures: list[str] = []
        if self.sections_payload["system_version"] != self.manifest["system_version"]:
            failures.append("manifest and section registry system_version differ")

        section_ids = set(self.sections)
        entry_owners: dict[str, str] = {}
        covered_classes = {str(value) for value in self.sections_payload["covered_document_classes"]}
        exempt_paths = {str(value) for value in self.sections_payload["exempt_paths"]}
        member_counts = {section_id: 0 for section_id in section_ids}

        for section_id, record in self.sections.items():
            entry_path = str(record["entry_path"])
            previous = entry_owners.get(entry_path)
            if previous is not None:
                failures.append(
                    f"section registry assigns entry path {entry_path} twice: {previous}, {section_id}"
                )
            else:
                entry_owners[entry_path] = section_id

            for related_id in record["related_section_ids"]:
                related = str(related_id)
                if related == section_id:
                    failures.append(f"section {section_id} relates to itself")
                elif related not in section_ids:
                    failures.append(f"section {section_id} references unknown related section {related}")

            entry = self.root / entry_path
            if not entry.is_file():
                failures.append(f"section {section_id} entry is missing: {entry_path}")
                continue
            try:
                text = entry.read_text(encoding="utf-8")
                resolution = self.resolve(entry_path, "read")
            except (OSError, UnicodeDecodeError, DocSystemError) as exc:
                failures.append(f"cannot inspect section {section_id} entry {entry_path}: {exc}")
                continue

            if section_id not in resolution.contract["section_refs"]:
                failures.append(f"section entry {entry_path} does not declare its own section {section_id}")

            kind = str(record["entry_kind"])
            document_class = str(resolution.contract["document_class"])
            mutation = str(resolution.contract["mutation"])
            if kind == "manual":
                if document_class not in {
                    "living",
                    "normative",
                    "structured_knowledge",
                    "governance_control",
                    "framework_core",
                }:
                    failures.append(
                        f"manual section entry {entry_path} has incompatible class {document_class}"
                    )
                if mutation in {"generator_only", "owner_only", "immutable"}:
                    failures.append(
                        f"manual section entry {entry_path} has incompatible mutation {mutation}"
                    )
            elif kind == "generated":
                if document_class != "generated_projection" or mutation != "generator_only":
                    failures.append(
                        f"generated section entry {entry_path} must be generated_projection/generator_only"
                    )
            elif kind == "authority":
                if document_class != "locked_authority" or mutation != "owner_only":
                    failures.append(
                        f"authority section entry {entry_path} must be locked_authority/owner_only"
                    )

            if record.get("max_lines") is not None:
                line_count = len(text.splitlines())
                byte_count = len(text.encode("utf-8"))
                max_lines = int(record["max_lines"])
                max_bytes = int(record["max_bytes"])
                if line_count > max_lines:
                    failures.append(
                        f"section entry attention budget exceeded: {entry_path} has "
                        f"{line_count} lines, limit {max_lines}"
                    )
                if byte_count > max_bytes:
                    failures.append(
                        f"section entry attention budget exceeded: {entry_path} has "
                        f"{byte_count} bytes, limit {max_bytes}"
                    )

            linked_targets = _markdown_link_targets(self.root, entry_path, text)
            for configured_target in record["required_targets"]:
                target = str(configured_target)
                if not (self.root / target).exists():
                    failures.append(f"section entry {entry_path} requires missing target {target}")
                elif target not in linked_targets:
                    failures.append(f"section entry {entry_path} does not link required target {target}")

        for relpath in self.projection_paths():
            if not relpath.endswith(".md"):
                continue
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            contract = resolution.contract
            refs = tuple(str(value) for value in contract["section_refs"])
            for section_id in refs:
                if section_id in member_counts and str(contract["document_class"]) in covered_classes:
                    member_counts[section_id] += 1
            if (
                str(contract["document_class"]) in covered_classes
                and relpath not in exempt_paths
                and not refs
            ):
                failures.append(f"current document has no explicit section: {relpath}")

        for section_id, count in sorted(member_counts.items()):
            if count == 0:
                failures.append(f"section has no current members: {section_id}")
        return failures

    def _check_policies(self) -> list[str]:
        failures: list[str] = []
        seen_ids: dict[str, str] = {}
        policy_paths = self.policy_paths()
        root_policy = _normalise_relpath(str(self.manifest["root_policy"]))
        if root_policy not in policy_paths:
            failures.append(f"root policy is not Git-visible: {root_policy}")
        for relpath in policy_paths:
            try:
                policy = self._load_policy(relpath)
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            policy_id = str(policy.payload["policy_id"])
            previous = seen_ids.get(policy_id)
            if previous is not None:
                failures.append(f"duplicate policy_id {policy_id}: {previous}, {relpath}")
            seen_ids[policy_id] = relpath
            rule_ids = [str(rule["id"]) for rule in policy.payload["rules"]]
            if len(rule_ids) != len(set(rule_ids)):
                failures.append(f"{relpath}: duplicate rule id")
            for contract, label in _policy_contracts(policy):
                failures.extend(self._check_contract_refs(contract, label))
            try:
                resolution = self.resolve(relpath, "edit")
            except DocSystemError as exc:
                failures.append(str(exc))
            else:
                if resolution.contract["document_class"] != "framework_core":
                    failures.append(f"policy file is not framework_core: {relpath}")
                if CONTEXT_RANK[str(resolution.contract["context_level"])] < CONTEXT_RANK["L2"]:
                    failures.append(f"policy file is below L2: {relpath}")
        return failures

    def _check_contract_refs(self, contract: Mapping[str, Any], label: str) -> list[str]:
        failures: list[str] = []
        for section_id in contract.get("section_refs", []):
            if section_id not in self.sections:
                failures.append(f"{label}: unknown section {section_id}")
        for invariant_id in contract.get("invariant_refs", []):
            if invariant_id not in self.invariants:
                failures.append(f"{label}: unknown invariant {invariant_id}")
        for adr_id in contract.get("adr_refs", []):
            if adr_id not in self.adrs:
                failures.append(f"{label}: unknown ADR {adr_id}")
        for action_id in contract.get("after_change", []):
            if action_id not in self.actions:
                failures.append(f"{label}: unknown action {action_id}")
        generator = contract.get("generator_action")
        if generator is not None and generator not in self.actions:
            failures.append(f"{label}: unknown generator action {generator}")
        for knowledge_id in contract.get("knowledge_refs", []):
            try:
                self._knowledge_records([knowledge_id], None)
            except DocSystemError as exc:
                failures.append(f"{label}: {exc}")
        return failures

    def _check_markdown_coverage(self) -> list[str]:
        failures: list[str] = []
        globs = tuple(str(value) for value in self.manifest["governed_markdown_globs"])
        exclude_globs = tuple(
            str(value) for value in self.manifest["governed_markdown_exclude_globs"]
        )
        for relpath in self.visible_paths():
            if not relpath.endswith(".md"):
                continue
            if not any(_glob_match(relpath, pattern) for pattern in globs):
                continue
            if any(_glob_match(relpath, pattern) for pattern in exclude_globs):
                continue
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if resolution.contract["document_class"] == "unmanaged":
                failures.append(f"governed markdown has no effective policy: {relpath}")
        return failures

    def _check_workspace_overlays(self) -> list[str]:
        failures: list[str] = []
        if self.manifest["workspace_overlays"]["projection_input_policy"] != "excluded":
            failures.append("workspace overlays must remain excluded from tracked projections")
        tracked = set(self.tracked_paths())
        projection = set(self.projection_paths())
        for overlay_id, record in self.workspace_overlays.items():
            relpath = str(record["path"])
            target = str(record["canonical_target"])
            if target not in tracked or not (self.root / target).is_file():
                failures.append(
                    f"workspace overlay {overlay_id} has missing tracked canonical target: {target}"
                )
            if relpath in projection:
                failures.append(f"workspace overlay leaked into tracked projection inputs: {relpath}")
            if relpath in tracked:
                failures.append(
                    f"workspace overlay is tracked in this checkout: {relpath}; "
                    "real-repository landing must preserve it as optional workspace_untracked"
                )
            absolute = self.root / relpath
            if not absolute.exists():
                continue
            if not absolute.is_file():
                failures.append(f"workspace overlay is not a regular file: {relpath}")
                continue
            if bool(record["validate_policy_when_present"]):
                try:
                    resolution = self.resolve(relpath, "read")
                except DocSystemError as exc:
                    failures.append(str(exc))
                    continue
                if resolution.contract["document_class"] == "unmanaged":
                    failures.append(f"workspace overlay lacks an effective policy: {relpath}")
                if target not in resolution.contract["required_reads"]:
                    failures.append(
                        f"workspace overlay {relpath} does not point to canonical target {target}"
                    )
        return failures

    def _check_framework_core(self) -> list[str]:
        failures: list[str] = []
        visible = self.tracked_paths()
        for record in self.manifest["framework_core"]:
            matches = [path for path in visible if _matches(path, record["match"])]
            if not matches:
                failures.append(f"framework_core.{record['id']} matches no visible path")
                continue
            for path in matches:
                try:
                    resolution = self.resolve(path, "read")
                except DocSystemError as exc:
                    failures.append(str(exc))
                    continue
                if resolution.contract["document_class"] != "framework_core":
                    failures.append(f"framework core path lost its class: {path}")
                if CONTEXT_RANK[str(resolution.contract["context_level"])] < CONTEXT_RANK[str(record["context_level"])]:
                    failures.append(f"framework core path {path} is below {record['context_level']}")
        return failures

    def _check_legacy_projection(self) -> list[str]:
        failures: list[str] = []
        expected = self.render_legacy_projection()
        output_relpath = str(self.manifest["legacy_projection"]["output"])
        output = self.root / output_relpath
        try:
            actual = output.read_text(encoding="utf-8")
        except OSError as exc:
            return [f"cannot read legacy projection {output_relpath}: {exc}"]
        if actual != expected:
            failures.append(f"legacy projection is stale: run {self.actions['docsystem.render_legacy']['command']}")
            return failures
        try:
            from devtools import docs_reference_scan as legacy_scan
        except (ImportError, OSError) as exc:
            failures.append(f"cannot import legacy docs scanner: {exc}")
            return failures
        try:
            payload = _parse_json(expected, output_relpath)
            legacy_scan._validate_registry_shape(payload)
            registry = legacy_scan.Registry(
                path=output,
                relpath=output_relpath,
                sha256="0" * 64,
                payload=payload,
            )
            scope = legacy_scan.resolve_scope(registry, self.projection_paths())
            if scope.unregistered:
                failures.append(
                    "legacy projection leaves visible markdown unregistered: " + ", ".join(scope.unregistered[:10])
                )
        except (DocSystemError, legacy_scan.DocScanError) as exc:
            failures.append(f"legacy projection invalid: {exc}")
        return failures

    def _check_guidance_projection(self) -> list[str]:
        output_relpath = str(self.manifest["guidance_projection"]["output"])
        output = self.root / output_relpath
        expected = self.render_guidance_projection()
        try:
            actual = output.read_text(encoding="utf-8")
        except OSError as exc:
            return [f"cannot read guidance projection {output_relpath}: {exc}"]
        if actual != expected:
            return ["guidance projection is stale: run " + self.actions["docsystem.render_guidance"]["command"]]
        return []

    def _check_section_projection(self) -> list[str]:
        output_relpath = str(self.manifest["section_projection"]["output"])
        output = self.root / output_relpath
        expected = self.render_section_projection()
        try:
            actual = output.read_text(encoding="utf-8")
        except OSError as exc:
            return [f"cannot read section projection {output_relpath}: {exc}"]
        if actual != expected:
            return ["section projection is stale: run " + self.actions["docsystem.render_sections"]["command"]]
        return []

    def _check_convergence_projection(self) -> list[str]:
        output_relpath = str(self.manifest["convergence_projection"]["output"])
        output = self.root / output_relpath
        expected = self.render_convergence_projection()
        failures: list[str] = []
        try:
            actual = output.read_text(encoding="utf-8")
        except OSError as exc:
            return [f"cannot read convergence projection {output_relpath}: {exc}"]
        if actual != expected:
            failures.append(
                "convergence projection is stale: run "
                + self.actions["docsystem.render_convergence"]["command"]
            )
        for failure in self.convergence_audit()["failures"]:
            failures.append(f"document convergence: {failure}")
        return failures

    def _check_landing_protocol(self) -> list[str]:
        failures: list[str] = []
        descriptor = self.manifest["landing_protocol"]
        if self.landing_payload["system_version"] != self.manifest["system_version"]:
            failures.append("manifest and landing protocol system_version differ")
        expected_paths = (
            str(descriptor["source"]),
            str(descriptor["schema"]),
            str(descriptor["ack_schema"]),
            str(descriptor["runner"]),
            str(descriptor["guide"]),
        )
        for relpath in expected_paths:
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if resolution.contract["document_class"] != "framework_core":
                failures.append(f"landing framework path lost framework_core class: {relpath}")
            if resolution.contract["mutation"] != "governed":
                failures.append(f"landing framework path is not governed: {relpath}")
        migrations = list(self.landing_payload["known_migrations"])
        sources = [str(record["source_path"]) for record in migrations]
        if len(sources) != len(set(sources)):
            failures.append("landing protocol contains duplicate migration source paths")
        workspace_overlays = {str(value) for value in self.landing_payload["workspace_overlays"]}
        for migration in migrations:
            source = str(migration["source_path"])
            replacement_mode = str(migration["replacement_mode"])
            if source in workspace_overlays and replacement_mode != "manual_overlay":
                failures.append(f"workspace overlay landing source is not manual_overlay: {source}")
            obligation_ids = [str(value["id"]) for value in migration["obligations"]]
            if len(obligation_ids) != len(set(obligation_ids)):
                failures.append(f"landing migration contains duplicate obligation IDs: {source}")
            for obligation in migration["obligations"]:
                obligation_id = str(obligation["id"])
                allowed_targets = {str(value) for value in obligation["allowed_targets"]}
                target_formats = {str(key) for key in obligation["target_formats"]}
                if target_formats != allowed_targets:
                    missing = sorted(allowed_targets - target_formats)
                    extra = sorted(target_formats - allowed_targets)
                    failures.append(
                        f"landing obligation target format coverage differs for {source}:{obligation_id}; "
                        f"missing={missing}, extra={extra}"
                    )
        required_forbidden = {
            "git reset --hard",
            "git clean",
            "git add -A",
            "git commit",
            "git commit --amend",
        }
        declared_forbidden = {str(value) for value in self.landing_payload["forbidden_operations"]}
        missing_forbidden = sorted(required_forbidden - declared_forbidden)
        if missing_forbidden:
            failures.append("landing protocol omits forbidden operations: " + ", ".join(missing_forbidden))
        for relpath in self.landing_payload["append_only_targets"]:
            try:
                contract = self.resolve(str(relpath), "read").contract
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if contract["mutation"] != "append_only":
                failures.append(f"landing append-only target is not append_only: {relpath}")
        archive_probe = PurePosixPath(str(self.landing_payload["archive_root"]), "2099-01-01", "probe.md").as_posix()
        try:
            archive_contract = self.resolve(archive_probe, "read").contract
        except DocSystemError as exc:
            failures.append(str(exc))
        else:
            if archive_contract["document_class"] != "historical_evidence":
                failures.append("landing archive root is not historical_evidence")
            if archive_contract["mutation"] != "immutable":
                failures.append("landing archive root is not immutable")
        lane_id = "document_landing_regressions"
        if lane_id not in self.governance_gate_lanes:
            failures.append(f"governance gate omits landing lane {lane_id}")
        else:
            for profile_id in ("changed", "full", "weekly", "framework"):
                selected = set(self.governance_gate_profiles.get(profile_id, {}).get("lane_ids", []))
                if lane_id not in selected:
                    failures.append(f"{profile_id} profile omits landing regression coverage")
        return failures

    def _check_governance_gate(self) -> list[str]:
        failures: list[str] = []
        try:
            _manifest, loaded = load_gate_configuration(self.root)
        except GovernanceGateError as exc:
            return [f"document governance gate is invalid: {exc}"]
        if loaded != self.governance_gate_payload:
            failures.append("docctl governance gate payload differs from the canonical loader")
        if loaded["system_version"] != self.manifest["system_version"]:
            failures.append("manifest and governance gate system_version differ")

        descriptor = self.manifest["governance_gate"]
        runner_path = str(descriptor["runner"])
        workflow_path = str(descriptor["ci_workflow"])
        for relpath in (runner_path, workflow_path, str(descriptor["source"]), str(descriptor["schema"])):
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if resolution.contract["document_class"] != "framework_core":
                failures.append(f"governance gate core path lost framework_core class: {relpath}")
            if resolution.contract["mutation"] != "governed":
                failures.append(f"governance gate core path is not governed: {relpath}")

        try:
            workflow = (self.root / workflow_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(f"cannot read governance CI workflow {workflow_path}: {exc}")
        else:
            for needle in (
                runner_path,
                "pull_request:",
                "push:",
                "schedule:",
                "workflow_dispatch:",
                "fetch-depth: 0",
                "profile=changed",
                "profile=weekly",
            ):
                if needle not in workflow:
                    failures.append(f"governance CI workflow omits shared-gate coordinate: {needle}")
            duplicated_tools: set[str] = set()
            for lane in self.governance_gate_lanes.values():
                for token in lane["command"]:
                    value = str(token)
                    if value.endswith(".py") and value != runner_path and value in workflow:
                        duplicated_tools.add(value)
            if duplicated_tools:
                failures.append(
                    "governance CI workflow duplicates lane commands outside the registry: "
                    + ", ".join(sorted(duplicated_tools))
                )

        lane_ids = set(self.governance_gate_lanes)
        used: set[str] = set()
        for profile_id, record in self.governance_gate_profiles.items():
            ids = [str(value) for value in record["lane_ids"]]
            unknown = sorted(set(ids) - lane_ids)
            if unknown:
                failures.append(
                    f"governance profile {profile_id} references unknown lanes: {', '.join(unknown)}"
                )
            used.update(ids)
        unused = sorted(lane_ids - used)
        if unused:
            failures.append("governance lanes are unused: " + ", ".join(unused))

        required_profiles = {"changed", "full", "weekly", "framework", "historical_replay"}
        missing_profiles = sorted(required_profiles - set(self.governance_gate_profiles))
        if missing_profiles:
            failures.append("governance profiles are missing: " + ", ".join(missing_profiles))
        else:
            changed = set(self.governance_gate_profiles["changed"]["lane_ids"])
            full = set(self.governance_gate_profiles["full"]["lane_ids"])
            weekly = set(self.governance_gate_profiles["weekly"]["lane_ids"])
            framework = set(self.governance_gate_profiles["framework"]["lane_ids"])
            historical = set(self.governance_gate_profiles["historical_replay"]["lane_ids"])
            current_profiles = {
                "changed": changed,
                "full": full,
                "weekly": weekly,
                "framework": framework,
            }
            for profile_id, selected in current_profiles.items():
                if "code_assets_history" in selected:
                    failures.append(
                        f"{profile_id} profile must not run historical code-assets replay"
                    )
            if "code_assets_current" not in changed:
                failures.append("changed profile omits the current code-assets check")
            for profile_id, selected in (("full", full), ("weekly", weekly)):
                if "code_assets_current" not in selected:
                    failures.append(f"{profile_id} profile omits the current code-assets check")
            if historical != {"code_assets_history"}:
                failures.append(
                    "historical_replay must contain only code_assets_history and remain manual-only"
                )
            if "docsystem_changed" not in changed or "docsystem_changed" in weekly:
                failures.append("diff-aware document checking is assigned to the wrong profiles")
            if "document_intake" not in changed or "document_intake" not in full or "document_intake" in weekly:
                failures.append("diff-aware document intake is assigned to the wrong profiles")
            for profile_id, selected in current_profiles.items():
                if "document_intake_regressions" not in selected:
                    failures.append(
                        f"{profile_id} profile omits event-intake regression coverage"
                    )
        return failures

    def _check_maintenance_audit(self) -> list[str]:
        failures: list[str] = []
        payload = self.maintenance_audit_payload
        if payload["system_version"] != self.manifest["system_version"]:
            failures.append("manifest and maintenance audit system_version differ")
        if payload["projection"]["output"] != self.manifest["maintenance_audit"]["projection"]:
            failures.append("manifest and maintenance audit projection paths differ")
        if payload["projection"]["generator_action"] != "docsystem.render_maintenance":
            failures.append("maintenance audit projection has the wrong generator action")

        check_ids = set(self.maintenance_audit_checks)
        referenced: set[str] = set()
        for profile_id, profile in self.maintenance_audit_profiles.items():
            unknown = sorted(set(str(value) for value in profile["check_ids"]) - check_ids)
            if unknown:
                failures.append(
                    f"maintenance profile {profile_id} references unknown checks: " + ", ".join(unknown)
                )
            referenced.update(str(value) for value in profile["check_ids"])
        unused = sorted(check_ids - referenced)
        if unused:
            failures.append("maintenance checks are unused by every profile: " + ", ".join(unused))
        required_profiles = {"weekly", "deep", "phase_close"}
        missing_profiles = sorted(required_profiles - set(self.maintenance_audit_profiles))
        if missing_profiles:
            failures.append("maintenance profiles are missing: " + ", ".join(missing_profiles))

        kinds: dict[str, str] = {}
        for check_id, record in self.maintenance_audit_checks.items():
            kind = str(record["kind"])
            previous = kinds.get(kind)
            if previous is not None:
                failures.append(f"maintenance check kind {kind} is assigned twice: {previous}, {check_id}")
            else:
                kinds[kind] = check_id
            for action_id in record.get("action_ids", []):
                if action_id not in self.actions:
                    failures.append(f"maintenance check {check_id} references unknown action {action_id}")

        output_relpath = str(self.manifest["maintenance_audit"]["projection"])
        output = self.root / output_relpath
        try:
            actual = output.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"cannot read maintenance projection {output_relpath}: {exc}")
        else:
            expected = self.render_maintenance_projection()
            if actual != expected:
                failures.append(
                    "maintenance projection is stale: run "
                    + self.actions["docsystem.render_maintenance"]["command"]
                )

        lane_ids = set(self.governance_gate_lanes)
        for lane_id in ("maintenance_audit", "maintenance_audit_regressions"):
            if lane_id not in lane_ids:
                failures.append(f"governance gate omits maintenance lane {lane_id}")
        if {"weekly", "deep", "phase_close"} <= set(self.maintenance_audit_profiles):
            weekly = set(self.governance_gate_profiles.get("weekly", {}).get("lane_ids", []))
            changed = set(self.governance_gate_profiles.get("changed", {}).get("lane_ids", []))
            full = set(self.governance_gate_profiles.get("full", {}).get("lane_ids", []))
            framework = set(self.governance_gate_profiles.get("framework", {}).get("lane_ids", []))
            if "maintenance_audit" not in weekly or "maintenance_audit" not in changed or "maintenance_audit" not in full:
                failures.append("maintenance_audit lane is assigned to the wrong governance profiles")
            for profile_id, selected in (
                ("changed", changed),
                ("full", full),
                ("weekly", weekly),
                ("framework", framework),
            ):
                if "maintenance_audit_regressions" not in selected:
                    failures.append(
                        f"{profile_id} profile omits maintenance-audit regression coverage"
                    )
        return failures

    def _check_guides(self) -> list[str]:
        failures: list[str] = []
        guide_paths = (
            str(self.manifest["architecture_guide"]),
            str(self.manifest["maintenance_guide"]),
            str(self.manifest["steady_state_guide"]),
            str(self.manifest["recovery_guide"]),
        )
        texts: dict[str, str] = {}
        for relpath in guide_paths:
            try:
                texts[relpath] = (self.root / relpath).read_text(encoding="utf-8")
            except OSError as exc:
                failures.append(f"cannot read guide {relpath}: {exc}")
        architecture = texts.get(str(self.manifest["architecture_guide"]), "")
        maintaining = texts.get(str(self.manifest["maintenance_guide"]), "")
        steady_state = texts.get(str(self.manifest["steady_state_guide"]), "")
        recovery = texts.get(str(self.manifest["recovery_guide"]), "")
        for invariant_id in self.invariants:
            if invariant_id not in architecture:
                failures.append(f"architecture guide omits invariant {invariant_id}")
        for adr_id in self.adrs:
            if adr_id not in architecture and adr_id not in maintaining and adr_id not in steady_state:
                failures.append(f"framework guides omit ADR coordinate {adr_id}")
        if str(self.manifest["system_version"]) not in architecture:
            failures.append("architecture guide omits document-system version")
        if "STEADY_STATE.md" not in architecture or "STEADY_STATE.md" not in maintaining:
            failures.append("framework guides omit the manifest-owned steady-state handoff")
        for needle in (
            "DOC-INV-023",
            "DOC-ADR-020",
            "devtools/docctl.py context",
            "devtools/docctl.py intake --changed",
            "devtools/docctl.py audit --profile weekly",
            "devtools/docctl.py gate --profile changed",
            "devtools/document_patch_landing.py",
            "scripts/preflight_gate.py",
            str(self.manifest["architecture_guide"]),
            str(self.manifest["maintenance_guide"]),
            str(self.manifest["recovery_guide"]),
        ):
            if needle not in steady_state:
                failures.append(f"steady-state guide omits maintenance coordinate: {needle}")
        for needle in (
            "devtools/docctl.py context",
            "devtools/docctl.py intake --changed",
            "devtools/docctl.py check --changed",
            "devtools/docctl.py doctor",
            "devtools/docctl.py render-entrypoints",
            "devtools/docctl.py render-convergence",
            "devtools/docctl.py render-maintenance",
            "devtools/docctl.py audit",
            "devtools/docctl.py gate",
            "devtools/document_governance_gate.py",
            str(self.manifest["governance_gate"]["source"]),
            "devtools/document_patch_landing.py",
            "devtools/docctl.py landing",
            str(self.manifest["landing_protocol"]["guide"]),
            "DOC_POLICY.json",
        ):
            if needle not in maintaining:
                failures.append(f"maintenance guide omits framework operation: {needle}")
        for needle in (
            BOOTSTRAP_RELPATH,
            "devtools/docctl.py",
            str(self.manifest["architecture_guide"]),
            str(self.manifest["maintenance_guide"]),
            str(self.manifest["steady_state_guide"]),
            str(self.manifest["entrypoint_registry"]["source"]),
            str(self.manifest["entrypoint_registry"]["schema"]),
            str(self.manifest["section_registry"]["source"]),
            str(self.manifest["section_registry"]["schema"]),
            "devtools/docctl.py render-entrypoints",
            "devtools/docctl.py render-sections",
            "devtools/docctl.py render-convergence",
            "devtools/docctl.py render-maintenance",
            "devtools/docctl.py audit",
            str(self.manifest["convergence_projection"]["output"]),
            str(self.manifest["governance_gate"]["source"]),
            str(self.manifest["governance_gate"]["schema"]),
            str(self.manifest["governance_gate"]["runner"]),
            str(self.manifest["governance_gate"]["ci_workflow"]),
            str(self.manifest["intake_protocol"]["source"]),
            str(self.manifest["intake_protocol"]["schema"]),
            str(self.manifest["maintenance_audit"]["source"]),
            str(self.manifest["maintenance_audit"]["schema"]),
            str(self.manifest["maintenance_audit"]["projection"]),
            str(self.manifest["landing_protocol"]["source"]),
            str(self.manifest["landing_protocol"]["schema"]),
            str(self.manifest["landing_protocol"]["ack_schema"]),
            str(self.manifest["landing_protocol"]["runner"]),
            str(self.manifest["landing_protocol"]["guide"]),
            "devtools/tests/test_document_patch_landing.py",
            str(self.intake_payload["ephemeral_documents"]["source"]),
            str(self.intake_payload["ephemeral_documents"]["schema"]),
            "devtools/docctl.py intake --changed",
            "devtools/docctl.py gate",
        ):
            if needle not in recovery:
                failures.append(f"recovery guide omits bootstrap coordinate: {needle}")
        claude = self.root / "CLAUDE.md"
        if claude.is_file():
            try:
                claude_text = claude.read_text(encoding="utf-8")
            except OSError as exc:
                failures.append(f"cannot read optional CLAUDE.md overlay: {exc}")
            else:
                for needle in (
                    "devtools/docctl.py context",
                    "docs/AGENT_OPERATIONS.md",
                    "PROJECT_LOCK.md",
                ):
                    if needle not in claude_text:
                        failures.append(f"optional CLAUDE.md overlay omits bootstrap coordinate: {needle}")
        operations_path = self.root / "docs/AGENT_OPERATIONS.md"
        try:
            operations_text = operations_path.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"cannot read docs/AGENT_OPERATIONS.md: {exc}")
        else:
            for needle in (
                "CURRENT.md",
                "../PROJECT_LOCK.md",
                "scripts/preflight_gate.py",
                "devtools/docctl.py intake --changed",
                "devtools/docctl.py close-dossier",
                "devtools/docctl.py exit-ephemeral",
                "devtools/docctl.py register-local-evidence",
                "devtools/docctl.py audit",
                "devtools/docctl.py gate",
                "devtools/document_governance_gate.py",
            ):
                if needle not in operations_text:
                    failures.append(f"docs/AGENT_OPERATIONS.md omits operating coordinate: {needle}")
        return failures

    def _check_test_timing_receipt(self) -> list[str]:
        """Validate the manifest-owned serial call-phase timing receipt."""

        failures: list[str] = []
        receipt = self.test_timing_receipt
        threshold = float(receipt["threshold_call_seconds"])
        if threshold != 8.0:
            failures.append("test timing receipt threshold must remain the central 8-second call-phase boundary")
        if receipt["execution_mode"] != "serial_no_concurrent_pytest":
            failures.append("test timing receipt was not measured in serial no-concurrency mode")

        command = tuple(str(value) for value in receipt["command"])
        for required in (
            "src/tests/test_document_system.py",
            "src/tests/test_knowledge_docs.py",
            "no:randomly",
            "no:cacheprovider",
            "--basetemp={temp}/pytest",
            "--durations=0",
            "--durations-min=0",
        ):
            if required not in command:
                failures.append(f"test timing receipt command omits {required}")

        measured_paths: set[str] = set()
        for record in receipt["measured_inputs"]:
            relpath = _normalise_relpath(str(record["path"]))
            if relpath in measured_paths:
                failures.append(f"test timing receipt repeats measured input: {relpath}")
                continue
            measured_paths.add(relpath)
            path = self.root / relpath
            if not path.is_file():
                failures.append(f"test timing receipt input is missing: {relpath}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != str(record["sha256"]):
                failures.append(
                    f"test timing receipt input drifted: {relpath}; rerun the serial call-phase duration sweep"
                )

        required_inputs = {
            "src/tests/test_document_system.py",
            "src/tests/test_knowledge_docs.py",
            "src/tests/conftest.py",
        }
        for relpath in sorted(required_inputs - measured_paths):
            failures.append(f"test timing receipt omits measured input: {relpath}")

        maximum = receipt["maximum_call"]
        maximum_nodeid = str(maximum["nodeid"])
        maximum_seconds = float(maximum["seconds"])
        slow_nodes = tuple(str(value) for value in receipt["nodes_at_or_above_threshold"])
        if maximum_seconds >= threshold and maximum_nodeid not in slow_nodes:
            failures.append("test timing receipt maximum call crosses the threshold but is absent from slow nodes")
        if maximum_seconds < threshold and slow_nodes:
            failures.append("test timing receipt lists threshold-crossing nodes above a sub-threshold maximum")

        raw_output_sha256 = str(receipt["raw_output_sha256"])
        if raw_output_sha256 == "0" * 64:
            failures.append("test timing receipt raw output hash is an unsealed placeholder")

        action = str(receipt["slow_registry_action"])
        if action == "no_new_entries_required" and slow_nodes:
            failures.append("test timing receipt says no slow entries are required but lists slow nodes")
        if action == "entries_registered" and not slow_nodes:
            failures.append("test timing receipt says slow entries were registered but lists no slow nodes")

        slow_registry = self.root / "src/tests/conftest.py"
        if slow_nodes and slow_registry.is_file():
            text = slow_registry.read_text(encoding="utf-8")
            for nodeid in slow_nodes:
                suffix = nodeid.removeprefix("src/tests/")
                if f'"{suffix}"' not in text:
                    failures.append(f"threshold-crossing test is absent from _SLOW_TEST_NODEIDS: {nodeid}")
        return failures

    def _check_intake_protocol(self) -> list[str]:
        failures: list[str] = []
        if self.intake_payload["system_version"] != self.manifest["system_version"]:
            failures.append(
                "intake protocol system_version does not match bootstrap manifest: "
                f"{self.intake_payload['system_version']} != {self.manifest['system_version']}"
            )
        for event in self.intake_events.values():
            for action_id in event["action_ids"]:
                if action_id not in self.actions:
                    failures.append(f"{event['id']} references unknown action: {action_id}")

        sources = self.manifest["knowledge_sources"]
        for ledger_name, config in self.intake_payload["semantic_identity"].items():
            if config["source"] != sources[ledger_name]:
                failures.append(
                    f"intake semantic_identity.{ledger_name}.source differs from manifest knowledge source"
                )
            semantic_fields = set(str(value) for value in config["semantic_fields"])
            migration_pairs: set[tuple[str, str]] = set()
            migration_ids: set[str] = set()
            for migration in config.get("allowed_schema_migrations", []):
                from_version = str(migration["from_schema_version"])
                to_version = str(migration["to_schema_version"])
                migration_id = str(migration["migration_id"])
                pair = (from_version, to_version)
                if from_version == to_version:
                    failures.append(
                        f"intake semantic_identity.{ledger_name} schema migration must change version: "
                        f"{from_version}"
                    )
                if pair in migration_pairs:
                    failures.append(
                        f"intake semantic_identity.{ledger_name} repeats schema migration: "
                        f"{from_version} -> {to_version}"
                    )
                migration_pairs.add(pair)
                if migration_id in migration_ids:
                    failures.append(
                        f"intake semantic_identity.{ledger_name} repeats schema migration id: "
                        f"{migration_id}"
                    )
                migration_ids.add(migration_id)
                unknown_fields = sorted(
                    set(str(value) for value in migration["allow_added_semantic_fields"])
                    - semantic_fields
                )
                if unknown_fields:
                    failures.append(
                        f"intake semantic_identity.{ledger_name} migration names non-semantic fields: "
                        + ", ".join(unknown_fields)
                    )
                rewrite_fields = {
                    str(value) for value in migration["allow_record_rewrite_fields"]
                }
                if migration_id == DECISION_V1_TO_V2_MIGRATION_ID:
                    if ledger_name != "decisions":
                        failures.append(
                            f"{migration_id} is reserved for the decisions ledger"
                        )
                    if pair != ("zmd_decision_v1", "zmd_decision_v2"):
                        failures.append(
                            f"{migration_id} must declare zmd_decision_v1 -> zmd_decision_v2"
                        )
                    if rewrite_fields != DECISION_V1_TO_V2_REWRITE_FIELDS:
                        failures.append(
                            f"{migration_id} must name the exact rewrite field set: "
                            + ", ".join(sorted(DECISION_V1_TO_V2_REWRITE_FIELDS))
                        )
                else:
                    failures.append(
                        f"intake semantic_identity.{ledger_name} names unsupported schema "
                        f"migration id: {migration_id}"
                    )
        if self.intake_payload["dossier_workflow"]["source"] != sources["dossiers"]:
            failures.append("intake dossier_workflow.source differs from manifest dossier source")
        if self.intake_payload["dossier_workflow"]["triage_source"] != sources["backfill_triage"]:
            failures.append("intake dossier_workflow.triage_source differs from manifest triage source")
        if self.intake_payload["authority_changes"]["decision_source"] != sources["decisions"]:
            failures.append("intake authority decision source differs from manifest decision source")

        owner_config = self.intake_payload["authority_changes"]
        companion_check = owner_config["companion_check"]
        if companion_check["enabled"] is not True:
            failures.append("authority companion detection must remain enabled")
        if companion_check["missing_companion_severity"] != "warning":
            failures.append("authority companion missing severity must remain warning")
        owner_roles = set(str(value) for value in owner_config["authority_roles"])
        owner_mutations = set(str(value) for value in owner_config["mutations"])
        for relpath in self.visible_paths():
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if (
                resolution.contract["authority_role"] not in owner_roles
                or resolution.contract["mutation"] not in owner_mutations
            ):
                continue
            matches = [rule for rule in owner_config["path_rules"] if _matches(relpath, rule["match"])]
            if len(matches) != 1:
                failures.append(
                    f"owner authority path must match exactly one intake rule: {relpath} (matches={len(matches)})"
                )

        today = date.today()
        for relpath, record in self.ephemeral_by_path.items():
            created_at = date.fromisoformat(str(record["created_at"]))
            expires_at = date.fromisoformat(str(record["expires_at"]))
            if expires_at < created_at:
                failures.append(f"ephemeral document expires before creation: {relpath}")
            if expires_at < today:
                failures.append(
                    f"ephemeral document expired on {expires_at.isoformat()}: {relpath}; "
                    f"perform exit_action={record['exit_action']} through docctl exit-ephemeral"
                )
            successor = record.get("successor_path")
            if record["exit_action"] == "delete" and successor is not None:
                failures.append(f"ephemeral delete record must keep successor_path=null: {relpath}")
            if record["exit_action"] in {"archive", "promote"}:
                if not isinstance(successor, str) or successor == relpath:
                    failures.append(f"ephemeral {record['exit_action']} record requires a distinct successor_path: {relpath}")
            if not (self.root / relpath).is_file():
                failures.append(f"ephemeral registry path is missing: {relpath}")
                continue
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if resolution.contract["document_class"] != "ephemeral":
                failures.append(f"ephemeral registry path is not governed as ephemeral: {relpath}")

        for relpath in self.visible_paths():
            if not relpath.endswith(".md") or not (self.root / relpath).is_file():
                continue
            try:
                resolution = self.resolve(relpath, "read")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if resolution.contract["document_class"] == "ephemeral" and relpath not in self.ephemeral_by_path:
                failures.append(f"ephemeral Markdown lacks an intake registry record: {relpath}")
        return failures

    def _comparison_revision(self, base: str | None) -> str:
        if base is None:
            return "HEAD"
        revision = _run_git(self.root, ["merge-base", base, "HEAD"]).decode("ascii", "strict").strip()
        if not revision:
            raise DocSystemError(f"git merge-base {base} HEAD returned no revision")
        return revision

    def _records_at_revision(
        self,
        revision: str,
        relpath: str,
        *,
        jsonl: bool,
    ) -> tuple[Mapping[str, Any], ...]:
        raw = _path_bytes_at_revision(self.root, revision, relpath)
        if raw is None:
            return ()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocSystemError(f"cannot decode {revision}:{relpath}: {exc}") from exc
        if jsonl:
            records: list[Mapping[str, Any]] = []
            for index, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                value = _parse_json(line, f"{revision}:{relpath}:{index}")
                if not isinstance(value, dict):
                    raise DocSystemError(f"{revision}:{relpath}:{index} must be an object")
                records.append(value)
            return tuple(records)
        value = _parse_json(text, f"{revision}:{relpath}")
        if not isinstance(value, dict) or not isinstance(value.get("records"), list):
            raise DocSystemError(f"{revision}:{relpath} must contain a records array")
        return tuple(value["records"])

    @staticmethod
    def _decision_v1_to_v2_record_migration_allowed(
        previous: Mapping[str, Any],
        current: Mapping[str, Any],
    ) -> bool:
        """Recognize the one owner-ratified rewrite of the decision register.

        The migration preserves every v1 field except the schema tag and the
        evidence items' added storage classification.  It adds the explicit
        non-authorizing pointer contract without permitting prose, scope,
        consequence, supersession, or attribution edits to ride along.
        """

        if previous.get("schema_version") != "zmd_decision_v1":
            return False
        if current.get("schema_version") != "zmd_decision_v2":
            return False
        if previous.get("id") != current.get("id"):
            return False

        changed_fields = {
            key
            for key in set(previous) | set(current)
            if previous.get(key) != current.get(key)
        }
        if not changed_fields <= DECISION_V1_TO_V2_REWRITE_FIELDS:
            return False

        for key, value in previous.items():
            if key in {"schema_version", "external_decision_id", "evidence"}:
                continue
            if current.get(key) != value:
                return False

        previous_external = previous.get("external_decision_id")
        current_external = current.get("external_decision_id")
        if previous_external is None:
            if not isinstance(current_external, str) or not current_external.strip():
                return False
        elif current_external != previous_external:
            return False

        if current.get("non_authorizing") is not True:
            return False
        if current.get("ruling_event_id") is not None:
            return False
        authority_source = current.get("authority_source")
        if not isinstance(authority_source, dict) or not authority_source:
            return False

        previous_evidence = previous.get("evidence")
        current_evidence = current.get("evidence")
        if not isinstance(previous_evidence, list) or not isinstance(current_evidence, list):
            return False
        if len(previous_evidence) != len(current_evidence):
            return False
        for old_item, new_item in zip(previous_evidence, current_evidence, strict=True):
            if not isinstance(old_item, dict) or not isinstance(new_item, dict):
                return False
            stripped = {key: value for key, value in new_item.items() if key != "storage"}
            if stripped != old_item:
                return False
            if new_item.get("storage") not in {
                "git_tracked",
                "workspace_untracked",
                "external_root",
            }:
                return False
        return True

    def _append_only_schema_migration_allowed(
        self,
        relpath: str,
        comparison_revision: str,
    ) -> bool:
        """Allow only a registry-declared, structurally checked ledger migration."""

        ledger_config = next(
            (
                config
                for config in self.intake_payload["semantic_identity"].values()
                if str(config["source"]) == relpath
            ),
            None,
        )
        if ledger_config is None:
            return False
        previous_records = self._records_at_revision(
            comparison_revision,
            relpath,
            jsonl=True,
        )
        current_records = _read_jsonl(self.root / relpath, self.root)
        if not previous_records or len(current_records) < len(previous_records):
            return False

        id_field = str(ledger_config["id_field"])
        migrated = False
        for previous, current in zip(previous_records, current_records, strict=False):
            if previous.get(id_field) != current.get(id_field):
                return False
            if previous == current:
                continue
            matching = [
                migration
                for migration in ledger_config.get("allowed_schema_migrations", [])
                if previous.get("schema_version") == migration["from_schema_version"]
                and current.get("schema_version") == migration["to_schema_version"]
            ]
            if len(matching) != 1:
                return False
            migration = matching[0]
            changed_fields = {
                key
                for key in set(previous) | set(current)
                if previous.get(key) != current.get(key)
            }
            allowed_fields = {
                str(value) for value in migration["allow_record_rewrite_fields"]
            }
            if not changed_fields <= allowed_fields:
                return False
            if migration["migration_id"] != DECISION_V1_TO_V2_MIGRATION_ID:
                return False
            if not self._decision_v1_to_v2_record_migration_allowed(previous, current):
                return False
            migrated = True
        return migrated

    def intake_changed(self, base: str | None = None) -> IntakeResult:
        paths = self.changed_paths(base)
        comparison_revision = self._comparison_revision(base)
        changed_set = set(paths)
        failures: list[str] = []
        warnings: list[str] = []
        authority_companion_matched_paths: set[str] = set()
        event_paths: dict[str, set[str]] = defaultdict(set)
        event_failures: dict[str, list[str]] = defaultdict(list)
        event_warnings: dict[str, list[str]] = defaultdict(list)

        def note(
            event_id: str,
            *event_members: str,
            failure: str | None = None,
            warning: str | None = None,
        ) -> None:
            if event_id not in self.intake_events:
                raise DocSystemError(f"unknown intake event: {event_id}")
            if failure is not None and warning is not None:
                raise DocSystemError("an intake finding cannot be both failure and warning")
            event_paths[event_id].update(event_members)
            if failure is not None:
                failures.append(failure)
                event_failures[event_id].append(failure)
            if warning is not None:
                warnings.append(warning)
                event_warnings[event_id].append(warning)

        current_classes = set(self.manifest["guidance_projection"]["include_document_classes"])
        for relpath in paths:
            current_path = self.root / relpath
            if (
                relpath.endswith(".md")
                and current_path.is_file()
                and not _path_at_revision(self.root, comparison_revision, relpath)
            ):
                try:
                    resolution = self.resolve(relpath, "create")
                except DocSystemError as exc:
                    note("DOC-EVENT-DOCUMENT-CREATED", relpath, failure=str(exc))
                    continue
                note("DOC-EVENT-DOCUMENT-CREATED", relpath)
                doc_class = str(resolution.contract["document_class"])
                if doc_class == "unmanaged":
                    note(
                        "DOC-EVENT-DOCUMENT-CREATED",
                        relpath,
                        failure=f"{relpath}: new Markdown has no effective document policy",
                    )
                elif (
                    relpath not in self.workspace_overlay_by_path
                    and doc_class in current_classes
                    and not resolution.contract["section_refs"]
                ):
                    note(
                        "DOC-EVENT-DOCUMENT-CREATED",
                        relpath,
                        failure=f"{relpath}: new current Markdown has no explicit section_refs",
                    )

            if not current_path.exists():
                continue
            try:
                resolution = self.resolve(relpath, "edit")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            if resolution.contract["mutation"] == "generator_only":
                note("DOC-EVENT-GENERATED-WRITE-THROUGH", relpath)
            if resolution.contract["document_class"] == "ephemeral":
                note("DOC-EVENT-EPHEMERAL-LIFECYCLE", relpath)
                if relpath not in self.ephemeral_by_path:
                    note(
                        "DOC-EVENT-EPHEMERAL-LIFECYCLE",
                        relpath,
                        failure=f"{relpath}: ephemeral document lacks an intake registry record",
                    )

        ephemeral_config = self.intake_payload["ephemeral_documents"]
        ephemeral_source = str(ephemeral_config["source"])
        previous_ephemeral_records = self._records_at_revision(
            comparison_revision, ephemeral_source, jsonl=False
        )
        previous_ephemeral = self._index_records(
            previous_ephemeral_records, "path", "baseline ephemeral documents"
        )
        current_ephemeral = self.ephemeral_by_path
        for relpath in sorted(set(current_ephemeral) - set(previous_ephemeral)):
            note("DOC-EVENT-EPHEMERAL-LIFECYCLE", ephemeral_source, relpath)
            if relpath not in changed_set:
                note(
                    "DOC-EVENT-EPHEMERAL-LIFECYCLE",
                    relpath,
                    failure=f"{relpath}: ephemeral registry entry was added without creating/changing the document",
                )
        for relpath in sorted(set(previous_ephemeral) - set(current_ephemeral)):
            record = previous_ephemeral[relpath]
            note("DOC-EVENT-EPHEMERAL-LIFECYCLE", ephemeral_source, relpath)
            if (self.root / relpath).exists():
                note(
                    "DOC-EVENT-EPHEMERAL-LIFECYCLE",
                    relpath,
                    failure=f"{relpath}: ephemeral registry entry was removed while the source still exists",
                )
                continue
            action = str(record["exit_action"])
            successor = record.get("successor_path")
            if action in {"archive", "promote"}:
                if not isinstance(successor, str) or not (self.root / successor).is_file():
                    note(
                        "DOC-EVENT-EPHEMERAL-LIFECYCLE",
                        relpath,
                        failure=f"{relpath}: {action} exit requires its registered successor_path to exist",
                    )
                elif successor not in changed_set:
                    note(
                        "DOC-EVENT-EPHEMERAL-LIFECYCLE",
                        relpath,
                        failure=f"{relpath}: {action} successor was not created or changed in the same transaction: {successor}",
                    )
                else:
                    try:
                        successor_resolution = self.resolve(successor, "create")
                    except DocSystemError as exc:
                        note("DOC-EVENT-EPHEMERAL-LIFECYCLE", successor, failure=str(exc))
                    else:
                        if successor_resolution.contract["document_class"] == "ephemeral":
                            note(
                                "DOC-EVENT-EPHEMERAL-LIFECYCLE",
                                successor,
                                failure=f"{successor}: ephemeral exit successor must leave the ephemeral class",
                            )
            elif successor is not None:
                note(
                    "DOC-EVENT-EPHEMERAL-LIFECYCLE",
                    relpath,
                    failure=f"{relpath}: delete exit must keep successor_path=null",
                )

        sources = self.manifest["knowledge_sources"]
        dossier_source = str(sources["dossiers"])
        current_dossier_payload = _read_json_object(self.root / dossier_source, self.root)
        current_dossier_records = tuple(current_dossier_payload["records"])
        previous_dossier_records = self._records_at_revision(
            comparison_revision, dossier_source, jsonl=False
        )
        current_dossiers = self._index_records(current_dossier_records, "id", "current intake dossiers")
        previous_dossiers = self._index_records(previous_dossier_records, "id", "baseline intake dossiers")
        review_source = str(sources["backfill_reviews"])
        current_reviews = _read_jsonl(self.root / review_source, self.root)
        current_review_by_id = self._index_records(current_reviews, "id", "current intake reviews")
        previous_review_by_id = self._index_records(
            self._records_at_revision(comparison_revision, review_source, jsonl=True),
            "id",
            "baseline intake reviews",
        )
        reviewed_dossiers = {str(record["dossier_id"]) for record in current_reviews if record["status"] == "current"}
        triage_payload = _read_json_object(self.root / str(sources["backfill_triage"]), self.root)
        triaged_dossiers = {
            str(dossier_id)
            for group in triage_payload["groups"]
            for dossier_id in group["dossier_ids"]
        }
        for dossier_id in sorted(set(previous_dossiers) - set(current_dossiers)):
            note(
                "DOC-EVENT-DOSSIER-REGISTERED",
                dossier_source,
                failure=f"{dossier_source}: stable dossier ID was deleted: {dossier_id}",
            )
        for dossier_id in sorted(set(previous_dossiers) & set(current_dossiers)):
            previous = previous_dossiers[dossier_id]
            current = current_dossiers[dossier_id]
            changed_identity = [
                field
                for field in ("path", "kind", "tracked_state")
                if previous.get(field) != current.get(field)
            ]
            if changed_identity:
                note(
                    "DOC-EVENT-DOSSIER-REGISTERED",
                    dossier_source,
                    str(current.get("path", previous.get("path"))),
                    failure=(
                        f"{dossier_id}: stable dossier identity fields changed in place: "
                        + ", ".join(changed_identity)
                    ),
                )
            previous_workflow = previous.get("workflow")
            current_workflow = current.get("workflow")
            previous_closure = previous_workflow.get("closure") if isinstance(previous_workflow, dict) else None
            current_closure = current_workflow.get("closure") if isinstance(current_workflow, dict) else None
            if previous_closure is not None and previous_closure != current_closure:
                note(
                    "DOC-EVENT-DOSSIER-CLOSED",
                    dossier_source,
                    str(current["path"]),
                    failure=f"{dossier_id}: typed closure receipt is immutable; add a successor dossier or erratum",
                )

        for dossier_id in sorted(set(current_dossiers) - set(previous_dossiers)):
            record = current_dossiers[dossier_id]
            dossier_path = str(record["path"])
            note("DOC-EVENT-DOSSIER-REGISTERED", dossier_source, dossier_path)
            workflow = record.get("workflow")
            if (
                dossier_path.startswith("docs/research/")
                and record["tracked_state"] == "tracked"
                and (
                    record["lifecycle"] != self.intake_payload["dossier_workflow"]["new_tracked_research_lifecycle"]
                    or not isinstance(workflow, dict)
                    or workflow.get("closure") is not None
                )
            ):
                note(
                    "DOC-EVENT-DOSSIER-REGISTERED",
                    dossier_path,
                    failure=(
                        f"{dossier_id}: new tracked research dossier must open as lifecycle=active "
                        "with workflow.closure=null"
                    ),
                )
            if record["lifecycle"] != "active" and dossier_id not in reviewed_dossiers | triaged_dossiers:
                note(
                    "DOC-EVENT-DOSSIER-REGISTERED",
                    dossier_path,
                    failure=f"{dossier_id}: new closed dossier has no current review or inventory triage",
                )
            if record["tracked_state"] == "local_optional":
                note("DOC-EVENT-LOCAL-EVIDENCE-PORTABILITY", dossier_source, dossier_path)
                portability = record.get("portability")
                required = self.intake_payload["local_optional_evidence"]["required_fields"]
                if not isinstance(portability, dict) or any(not portability.get(field) for field in required):
                    note(
                        "DOC-EVENT-LOCAL-EVIDENCE-PORTABILITY",
                        dossier_path,
                        failure=(
                            f"{dossier_id}: new local_optional dossier must record "
                            + ", ".join(required)
                        ),
                    )

        for dossier_id in sorted(set(previous_dossiers) & set(current_dossiers)):
            previous = previous_dossiers[dossier_id]
            current = current_dossiers[dossier_id]
            if previous["lifecycle"] == "active" and current["lifecycle"] != "active":
                note("DOC-EVENT-DOSSIER-CLOSED", dossier_source, str(current["path"]))
                workflow = current.get("workflow")
                closure = workflow.get("closure") if isinstance(workflow, dict) else None
                if not isinstance(closure, dict):
                    note(
                        "DOC-EVENT-DOSSIER-CLOSED",
                        str(current["path"]),
                        failure=f"{dossier_id}: active dossier closed without typed workflow.closure",
                    )
                else:
                    review_id = str(closure["review_id"])
                    review = current_review_by_id.get(review_id)
                    previous_review = previous_review_by_id.get(review_id)
                    if review is None:
                        note(
                            "DOC-EVENT-DOSSIER-CLOSED",
                            review_source,
                            failure=f"{dossier_id}: closure references missing review {review_id}",
                        )
                    elif previous_review is not None and previous_review == review:
                        note(
                            "DOC-EVENT-DOSSIER-CLOSED",
                            review_source,
                            failure=(
                                f"{dossier_id}: closure review {review_id} was not added or updated "
                                "in the same Git-visible transaction"
                            ),
                        )
                    if review_source not in changed_set:
                        note(
                            "DOC-EVENT-DOSSIER-CLOSED",
                            review_source,
                            failure=f"{dossier_id}: dossier closure requires the review ledger in the same transaction",
                        )

        # Stable claim/decision IDs are semantic identities, not editable labels.
        for ledger_name, config in self.intake_payload["semantic_identity"].items():
            source = str(config["source"])
            current_records = _read_jsonl(self.root / source, self.root)
            previous_records = self._records_at_revision(comparison_revision, source, jsonl=True)
            current_by_id = self._index_records(current_records, str(config["id_field"]), f"current {ledger_name}")
            previous_by_id = self._index_records(previous_records, str(config["id_field"]), f"baseline {ledger_name}")
            if source in changed_set:
                note("DOC-EVENT-KNOWLEDGE-IDENTITY", source)
            for record_id, previous in previous_by_id.items():
                current_record = current_by_id.get(record_id)
                if current_record is None:
                    note(
                        "DOC-EVENT-KNOWLEDGE-IDENTITY",
                        source,
                        failure=f"{source}: stable {ledger_name} ID was deleted: {record_id}",
                    )
                    continue
                changed_fields = [
                    field
                    for field in config["semantic_fields"]
                    if previous.get(field) != current_record.get(field)
                ]
                migration_allows_change = False
                if changed_fields:
                    previous_schema = previous.get("schema_version")
                    current_schema = current_record.get("schema_version")
                    for migration in config.get("allowed_schema_migrations", []):
                        if (
                            previous_schema == migration["from_schema_version"]
                            and current_schema == migration["to_schema_version"]
                        ):
                            allowed_fields = set(
                                str(value) for value in migration["allow_added_semantic_fields"]
                            )
                            migration_allows_change = all(
                                field in allowed_fields
                                and field not in previous
                                and field in current_record
                                for field in changed_fields
                            )
                            break
                if changed_fields and not migration_allows_change:
                    note(
                        "DOC-EVENT-KNOWLEDGE-IDENTITY",
                        source,
                        failure=(
                            f"{source}: {record_id} rewrites semantic identity fields in place: "
                            + ", ".join(changed_fields)
                            + "; create a new ID and explicit supersession instead"
                        ),
                    )

        decision_config = self.intake_payload["semantic_identity"]["decisions"]
        decision_source = str(decision_config["source"])
        current_decisions = self._index_records(
            _read_jsonl(self.root / decision_source, self.root), "id", "current owner decisions"
        )
        previous_decisions = self._index_records(
            self._records_at_revision(comparison_revision, decision_source, jsonl=True),
            "id",
            "baseline owner decisions",
        )
        new_decisions = [
            record for record_id, record in current_decisions.items() if record_id not in previous_decisions
        ]
        owner_config = self.intake_payload["authority_changes"]
        companion_check = owner_config["companion_check"]
        owner_identities = set(str(value) for value in self.intake_payload["owner_identities"])
        for relpath in paths:
            try:
                resolution = self.resolve(relpath, "edit")
            except DocSystemError:
                continue
            if (
                resolution.contract["mutation"] not in owner_config["mutations"]
                or resolution.contract["authority_role"] not in owner_config["authority_roles"]
            ):
                continue
            note("DOC-EVENT-AUTHORITY-CHANGED", relpath, decision_source)
            rules = [rule for rule in owner_config["path_rules"] if _matches(relpath, rule["match"])]
            if len(rules) != 1:
                note(
                    "DOC-EVENT-AUTHORITY-CHANGED",
                    relpath,
                    failure=f"{relpath}: owner authority path must match exactly one intake path rule",
                )
                continue
            rule = rules[0]
            companions: list[Mapping[str, Any]] = []
            required_evidence_role = str(owner_config["required_evidence_role"])
            for decision in new_decisions:
                evidence_paths = {
                    str(item["path"])
                    for item in decision["evidence"]
                    if str(item.get("role")) == required_evidence_role
                }
                scope = set(str(item) for item in decision["scope"])
                if (
                    decision["status"] == owner_config["required_decision_status"]
                    and str(decision["decided_by"]) in owner_identities
                    and str(decision["authority_effect"]) in rule["allowed_authority_effects"]
                    and scope.intersection(str(item) for item in rule["required_scope_any"])
                    and relpath in evidence_paths
                ):
                    companions.append(decision)
            if not companions:
                message = (
                    f"{relpath}: owner-governed authority changed without a newly added current "
                    f"non-authorizing decision-register companion satisfying intake rule "
                    f"{rule['id']} and citing the exact path with evidence "
                    f"role={required_evidence_role}"
                )
                if companion_check["blocking"]:
                    note(
                        "DOC-EVENT-AUTHORITY-CHANGED",
                        relpath,
                        failure=message,
                    )
                else:
                    note(
                        "DOC-EVENT-AUTHORITY-CHANGED",
                        relpath,
                        warning=message,
                    )
            else:
                authority_companion_matched_paths.add(relpath)

        events: list[IntakeEvent] = []
        action_ids: list[str] = []
        configured_event_ids = [str(event["id"]) for event in self.intake_payload["events"]]
        for event_id in configured_event_ids:
            if (
                event_id not in event_paths
                and event_id not in event_failures
                and event_id not in event_warnings
            ):
                continue
            config = self.intake_events[event_id]
            ids = tuple(str(value) for value in config["action_ids"])
            action_ids.extend(ids)
            events.append(
                IntakeEvent(
                    id=event_id,
                    title=str(config["title"]),
                    description=str(config["description"]),
                    paths=tuple(sorted(event_paths[event_id])),
                    failures=tuple(_dedupe(event_failures[event_id])),
                    warnings=tuple(_dedupe(event_warnings[event_id])),
                    action_ids=ids,
                )
            )
        return IntakeResult(
            paths=paths,
            comparison_revision=comparison_revision,
            events=tuple(events),
            failures=tuple(_dedupe(failures)),
            warnings=tuple(_dedupe(warnings)),
            actions=self._action_records(_dedupe(action_ids)),
            authority_companion_matched_paths=tuple(sorted(authority_companion_matched_paths)),
        )

    def changed_paths(self, base: str | None = None) -> tuple[str, ...]:
        top_level = _git_toplevel(self.root)
        if top_level != self.root:
            raise DocSystemError(f"repo root {self.root} is nested inside Git worktree {top_level}")
        paths: set[str] = set()
        if base:
            raw = _run_git(
                self.root,
                ["diff", "--no-renames", "--name-only", "-z", f"{base}...HEAD"],
            )
            paths.update(_parse_nul_paths(raw))
        for args in (
            ["diff", "--no-renames", "--name-only", "-z"],
            ["diff", "--cached", "--no-renames", "--name-only", "-z"],
        ):
            paths.update(_parse_nul_paths(_run_git(self.root, args)))
        untracked = _parse_nul_paths(_run_git(self.root, ["ls-files", "--others", "--exclude-standard", "-z"]))
        self._ensure_knowledge()
        assert self._dossiers is not None
        registered_artifact_roots = {
            str(record["path"]) for record in self._dossiers if str(record["path"]).startswith(".artifacts/")
        }
        artifact_boundary = None
        artifact_boundary_inputs = (
            "data/repository_governance/artifact_evidence_inputs.json",
            "data/repository_governance/artifact_evidence_inputs.schema.json",
        )
        if all((self.root / relpath).is_file() for relpath in artifact_boundary_inputs):
            try:
                artifact_boundary = load_artifact_evidence_semantic_boundary(self.root)
            except ArtifactEvidenceError as exc:
                raise DocSystemError(
                    f"cannot resolve artifact evidence storage classes: {exc}"
                ) from exc
        for path in untracked:
            if path in self.workspace_overlay_by_path:
                # Optional agent overlays are validated by doctor when present,
                # but they are not part of a Git-deliverable change set.
                continue
            if artifact_boundary is not None and artifact_boundary.covers_workspace(path):
                # Declared local evidence is a workspace input, not a Git
                # transaction.  Its durable metadata enters through the dossier
                # ledger, portability record or explicit registration command.
                # Enumerating every pre-existing receipt here would make every
                # PR in a shared worktree look like a multi-gigabyte document
                # change and would recreate the topology error fixed by ADR-016.
                continue
            # Existing local evidence roots are intentionally outside Git.  Keep
            # them quiet, but collapse a genuinely new top-level artifact package
            # to one synthetic changed path so dossier registration cannot vanish
            # in a multi-gigabyte payload listing.
            if path.startswith(".artifacts/") and path not in {
                ".artifacts/README.md",
                ".artifacts/DOC_POLICY.json",
            }:
                parts = PurePosixPath(path).parts
                artifact_root = "/".join(parts[:2])
                if artifact_root not in registered_artifact_roots:
                    paths.add(artifact_root)
                continue
            paths.add(path)
        return tuple(sorted(paths))

    def check_changed(self, base: str | None = None) -> CheckResult:
        intake = self.intake_changed(base)
        paths = intake.paths
        failures: list[str] = [*self.doctor(), *intake.failures]
        warnings: list[str] = [*intake.warnings]
        action_ids: list[str] = [str(value["id"]) for value in intake.actions]
        changed_set = set(paths)
        comparison_revision = intake.comparison_revision
        authority_companion_matched_paths = set(intake.authority_companion_matched_paths)

        self._ensure_knowledge()
        assert self._dossiers is not None
        registered_dossier_paths = {str(record["path"]) for record in self._dossiers}

        for path in paths:
            try:
                resolution = self.resolve(path, "edit")
            except DocSystemError as exc:
                failures.append(str(exc))
                continue
            contract = resolution.contract
            if contract["document_class"] == "unmanaged":
                continue
            existed_before = _path_at_revision(self.root, comparison_revision, path)
            mutation = str(contract["mutation"])
            if (
                mutation == "owner_only"
                and path not in authority_companion_matched_paths
                and self.intake_payload["authority_changes"]["companion_check"]["blocking"]
            ):
                failures.append(
                    f"{path}: changed path is owner_only; add the exact companion owner decision required by intake"
                )
            elif existed_before and mutation == "immutable":
                failures.append(f"{path}: changed path is immutable; use an erratum or superseding record")
            elif existed_before and mutation == "append_only":
                current_path = self.root / path
                if not current_path.is_file():
                    failures.append(f"{path}: append_only path was removed or moved; append a successor instead")
                else:
                    previous = _path_bytes_at_revision(self.root, comparison_revision, path)
                    current = current_path.read_bytes()
                    if previous is None:
                        failures.append(f"{path}: cannot read append_only baseline at {comparison_revision}")
                    elif not current.startswith(previous) and not self._append_only_schema_migration_allowed(
                        path,
                        comparison_revision,
                    ):
                        failures.append(f"{path}: append_only content rewrites existing bytes instead of appending")
            if mutation == "generator_only":
                if not any(_pattern_touches_changed(source, changed_set) for source in contract["source_paths"]):
                    failures.append(f"{path}: generated projection changed without any declared source path")
            action_ids.extend(str(value["id"]) for value in resolution.action_commands)

            dossier_root = _dossier_root_for_path(path)
            if dossier_root is not None and dossier_root not in registered_dossier_paths:
                failures.append(
                    f"{dossier_root}: research/evidence package is not registered as a dossier; "
                    f"run {self.actions['knowledge.refresh_dossiers']['command']}"
                )

        policy_filename = str(self.manifest["policy_filename"])
        changed_policy_paths = {path for path in changed_set if PurePosixPath(path).name == policy_filename}
        for policy_path in sorted(changed_policy_paths):
            if (
                _path_at_revision(self.root, comparison_revision, policy_path)
                and not (self.root / policy_path).is_file()
            ):
                failures.append(
                    f"{policy_path}: policy anchor was removed or moved; document-system v1 "
                    "keeps policy paths stable because deleting the guard can silently weaken "
                    "all unchanged descendants"
                )

        invariant_path = str(self.manifest["invariants"])
        framework_semantics = {
            BOOTSTRAP_RELPATH,
            str(self.manifest["manifest_schema"]),
            str(self.manifest["policy_schema"]),
            str(self.manifest["invariants_schema"]),
            str(self.manifest["entrypoint_registry"]["source"]),
            str(self.manifest["entrypoint_registry"]["schema"]),
            str(self.manifest["section_registry"]["source"]),
            str(self.manifest["section_registry"]["schema"]),
            str(self.manifest["legacy_projection"]["base"]),
            str(self.manifest["legacy_projection"]["base_schema"]),
            str(self.manifest["governance_gate"]["source"]),
            str(self.manifest["governance_gate"]["schema"]),
            str(self.manifest["governance_gate"]["runner"]),
            str(self.manifest["governance_gate"]["ci_workflow"]),
            str(self.manifest["intake_protocol"]["source"]),
            str(self.manifest["intake_protocol"]["schema"]),
            str(self.intake_payload["ephemeral_documents"]["source"]),
            str(self.intake_payload["ephemeral_documents"]["schema"]),
            str(self.manifest["landing_protocol"]["source"]),
            str(self.manifest["landing_protocol"]["schema"]),
            str(self.manifest["landing_protocol"]["ack_schema"]),
            str(self.manifest["landing_protocol"]["runner"]),
            str(self.manifest["landing_protocol"]["guide"]),
            "devtools/tests/test_document_patch_landing.py",
            "devtools/docctl.py",
            "devtools/build_knowledge_docs.py",
            "devtools/check_knowledge_docs.py",
            "devtools/tests/test_document_governance_gate.py",
            "devtools/tests/test_document_intake.py",
            "devtools/document_maintenance_audit.py",
            "devtools/tests/test_document_maintenance_audit.py",
        }
        if invariant_path in changed_set:
            required = {
                str(self.manifest["architecture_guide"]),
                str(self.manifest["maintenance_guide"]),
                "src/tests/test_document_system.py",
            }
            missing = sorted(required - changed_set)
            if missing:
                failures.append("invariant change lacks atomic framework companions: " + ", ".join(missing))
            if not any(path.startswith(f"{self.manifest['decision_directory']}/") for path in changed_set):
                failures.append("invariant change requires a new or updated framework ADR")
        policy_change_classes = {
            policy_path: _classify_policy_change(
                self.root,
                comparison_revision,
                policy_path,
            )
            for policy_path in changed_policy_paths
        }
        framework_semantic_change = bool(framework_semantics & changed_set)
        # Local DOC_POLICY coverage and contract edits are validated by policy
        # resolution, doctor and intake. They do not change the resolver/schema
        # semantics and therefore must not automatically escalate to L3.
        if framework_semantic_change:
            if "src/tests/test_document_system.py" not in changed_set:
                failures.append("framework semantic change lacks src/tests/test_document_system.py")
            if not (
                str(self.manifest["maintenance_guide"]) in changed_set
                or any(path.startswith(f"{self.manifest['decision_directory']}/") for path in changed_set)
            ):
                failures.append("framework semantic change lacks maintenance-guide or ADR update")
        for policy_path, change_class in sorted(policy_change_classes.items()):
            if change_class not in {"coverage_update", "contract_change"}:
                failures.append(f"{policy_path}: unknown policy change class {change_class}")

        return CheckResult(
            paths=paths,
            failures=tuple(_dedupe(failures)),
            warnings=tuple(_dedupe(warnings)),
            actions=self._action_records(_dedupe(action_ids)),
        )

    # ------------------------------------------------------------------
    # explanatory lookups and scaffolding
    # ------------------------------------------------------------------

    def explain(self, identifier: str) -> Mapping[str, Any]:
        if identifier in self.invariants:
            return {"kind": "invariant", **dict(self.invariants[identifier])}
        if identifier in self.intake_events:
            return {"kind": "intake_event", **dict(self.intake_events[identifier])}
        if identifier in self.maintenance_audit_checks:
            return {
                **dict(self.maintenance_audit_checks[identifier]),
                "check_kind": self.maintenance_audit_checks[identifier]["kind"],
                "kind": "maintenance_audit_check",
            }
        if identifier.startswith("audit:"):
            profile_id = identifier.split(":", 1)[1]
            if profile_id in self.maintenance_audit_profiles:
                return {
                    "kind": "maintenance_audit_profile",
                    "id": profile_id,
                    **dict(self.maintenance_audit_profiles[profile_id]),
                }
        if identifier in self.sections:
            return {"kind": "section", **dict(self.sections[identifier])}
        if identifier in self.entrypoint_surfaces:
            return {
                "kind": "entrypoint_surface",
                **dict(self.entrypoint_surfaces[identifier]),
            }
        if identifier in self.entrypoint_redirects:
            return {
                "kind": "entrypoint_redirect",
                **dict(self.entrypoint_redirects[identifier]),
            }
        if identifier in self.entrypoint_guards:
            return {
                "kind": "entrypoint_guard",
                **dict(self.entrypoint_guards[identifier]),
            }
        self._ensure_knowledge()
        assert self._terms is not None
        assert self._topics is not None
        assert self._triage_groups is not None
        assert self._backfill_reviews is not None
        if identifier in self._terms:
            return {"kind": "term", **dict(self._terms[identifier])}
        if identifier in self._topics:
            return {"kind": "topic", **dict(self._topics[identifier])}
        if identifier in self._triage_groups:
            return {"kind": "backfill_triage", **dict(self._triage_groups[identifier])}
        if identifier in self._backfill_reviews:
            return {"kind": "backfill_review", **dict(self._backfill_reviews[identifier])}
        if identifier in self.adrs:
            return {"kind": "adr", "id": identifier, "path": self.adrs[identifier]}
        if identifier in self.actions:
            return {"kind": "action", "id": identifier, **dict(self.actions[identifier])}
        if identifier in self.governance_gate_profiles:
            return {
                "kind": "governance_profile",
                "id": identifier,
                **dict(self.governance_gate_profiles[identifier]),
            }
        if identifier in self.governance_gate_lanes:
            return {
                "kind": "governance_lane",
                **dict(self.governance_gate_lanes[identifier]),
            }
        for relpath in self.policy_paths():
            policy = self._load_policy(relpath)
            if policy.payload["policy_id"] == identifier:
                return {"kind": "policy", "path": relpath, **dict(policy.payload)}
            for rule in policy.payload["rules"]:
                if rule["id"] == identifier:
                    return {
                        "kind": "policy_rule",
                        "policy": relpath,
                        **dict(rule),
                    }
        raise DocSystemError(f"unknown document-system identifier: {identifier}")

    def guide(self) -> Mapping[str, Any]:
        return {
            "system_version": self.manifest["system_version"],
            "bootstrap": BOOTSTRAP_RELPATH,
            "architecture": self.manifest["architecture_guide"],
            "maintenance": self.manifest["maintenance_guide"],
            "steady_state": self.manifest["steady_state_guide"],
            "recovery": self.manifest["recovery_guide"],
            "adr_directory": self.manifest["decision_directory"],
            "entrypoints": self.manifest["entrypoint_registry"]["source"],
            "sections": self.manifest["section_registry"]["source"],
            "section_index": self.manifest["section_projection"]["output"],
            "convergence_report": self.manifest["convergence_projection"]["output"],
            "governance_gate": self.manifest["governance_gate"]["source"],
            "governance_gate_schema": self.manifest["governance_gate"]["schema"],
            "governance_runner": self.manifest["governance_gate"]["runner"],
            "governance_ci": self.manifest["governance_gate"]["ci_workflow"],
            "governance_default_profile": self.governance_gate_payload["runner"]["default_profile"],
            "intake_protocol": self.manifest["intake_protocol"]["source"],
            "intake_schema": self.manifest["intake_protocol"]["schema"],
            "maintenance_audit": self.manifest["maintenance_audit"]["source"],
            "maintenance_audit_schema": self.manifest["maintenance_audit"]["schema"],
            "maintenance_queue": self.manifest["maintenance_audit"]["projection"],
            "landing_protocol": self.manifest["landing_protocol"]["source"],
            "landing_schema": self.manifest["landing_protocol"]["schema"],
            "landing_ack_schema": self.manifest["landing_protocol"]["ack_schema"],
            "landing_runner": self.manifest["landing_protocol"]["runner"],
            "landing_guide": self.manifest["landing_protocol"]["guide"],
        }

    def new_document(
        self,
        kind: str,
        path: str,
        title: str,
        *,
        created_at: str | None = None,
        topics: Sequence[str] = (),
        expires_at: str | None = None,
        exit_action: str | None = None,
        successor_path: str | None = None,
        rationale: str | None = None,
    ) -> tuple[str, ...]:
        opened_at = _iso_date(created_at or date.today().isoformat(), "creation date")
        if kind == "research-dossier":
            if any(value is not None for value in (expires_at, exit_action, successor_path, rationale)):
                raise DocSystemError("research-dossier does not accept ephemeral lifecycle arguments")
            relpath = _normalise_relpath(path.rstrip("/"))
            if not relpath.startswith("docs/research/") or relpath.count("/") != 2:
                raise DocSystemError("research-dossier path must be a direct child of docs/research/")
            directory = self.root / relpath
            if directory.exists():
                raise DocSystemError(f"target already exists: {relpath}")
            readme_relpath = f"{relpath}/README.md"
            resolution = self.resolve(readme_relpath, "create")
            if not resolution.allowed or resolution.contract["document_class"] == "unmanaged":
                raise DocSystemError(f"research dossier cannot be created under the effective policy: {readme_relpath}")

            topic_values = tuple(_dedupe(str(value).strip() for value in topics if str(value).strip())) or ("other",)
            invalid_topics = [
                value for value in topic_values if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value) is None
            ]
            if invalid_topics:
                raise DocSystemError("invalid dossier topic labels: " + ", ".join(invalid_topics))

            dossier_source = str(self.manifest["knowledge_sources"]["dossiers"])
            dossier_path = self.root / dossier_source
            payload: MutableMapping[str, Any] = dict(_read_json_object(dossier_path, self.root))
            records = [dict(record) for record in payload["records"]]
            if any(str(record["path"]) == relpath for record in records):
                raise DocSystemError(f"dossier path is already registered: {relpath}")
            from devtools.build_knowledge_docs import _slug_for_dossier

            dossier_id = _slug_for_dossier(relpath)
            if any(str(record["id"]) == dossier_id for record in records):
                raise DocSystemError(f"generated dossier ID is already registered: {dossier_id}")
            record = {
                "id": dossier_id,
                "path": relpath,
                "entry_file": readme_relpath,
                "title": title,
                "kind": "directory",
                "lifecycle": "active",
                "relevance": "unreviewed",
                "curation": "curated",
                "tracked_state": "tracked",
                "date": opened_at,
                "topics": list(topic_values),
                "summary": "Active research dossier opened through docctl; semantic outcome is pending closure review.",
                "workflow": {"opened_at": opened_at, "closure": None},
            }
            records.append(record)
            records.sort(key=lambda item: str(item["path"]))
            payload["ledger_reviewed_at"] = opened_at
            payload["records"] = records

            try:
                directory.mkdir(parents=True)
                readme = directory / "README.md"
                readme.write_text(
                    f"# {title}\n\n"
                    "## 问题与作用域\n\n待填写。\n\n"
                    "## 方法与证据\n\n待填写。\n\n"
                    "## 结果与边界\n\n本 dossier 处于 `active`。关闭前必须建立 current semantic review，"
                    "并通过 `docctl close-dossier` 登记可复用 claim、negative result、decision、"
                    "明确的 no-result 原因或 successor。\n",
                    encoding="utf-8",
                )
                _write_json_object_atomic(dossier_path, payload)
            except Exception:
                if directory.exists():
                    import shutil

                    shutil.rmtree(directory)
                raise
            self._invalidate_path_inventory()
            return (
                readme_relpath,
                dossier_source,
                f"DOSSIER: {dossier_id}",
                str(self.actions["knowledge.build"]["command"]),
                str(self.actions["docsystem.intake"]["command"]),
                str(self.actions["knowledge.check"]["command"]),
            )

        relpath = _normalise_relpath(path)
        if not relpath.endswith(".md"):
            raise DocSystemError("document path must end in .md")
        destination = self.root / relpath
        if destination.exists():
            raise DocSystemError(f"target already exists: {relpath}")
        resolution = self.resolve(relpath, "create")
        if resolution.contract["document_class"] == "unmanaged":
            raise DocSystemError(f"new document has no effective policy: {relpath}")
        if resolution.contract["mutation"] in {"generator_only", "owner_only", "immutable"}:
            raise DocSystemError(
                f"new document kind cannot be created directly under mutation={resolution.contract['mutation']}"
            )
        current_classes = set(self.manifest["guidance_projection"]["include_document_classes"])
        if resolution.contract["document_class"] in current_classes and not resolution.contract["section_refs"]:
            raise DocSystemError(f"new current document has no explicit section_refs: {relpath}")

        is_ephemeral = resolution.contract["document_class"] == "ephemeral"
        lifecycle_values = (expires_at, exit_action, rationale)
        if is_ephemeral and any(value is None or not str(value).strip() for value in lifecycle_values):
            raise DocSystemError(
                "ephemeral document creation requires --expires-at, --exit-action and --rationale"
            )
        if not is_ephemeral and any(value is not None for value in (*lifecycle_values, successor_path)):
            raise DocSystemError("ephemeral lifecycle arguments are only valid for document_class=ephemeral")

        registry_path: Path | None = None
        registry_payload: MutableMapping[str, Any] | None = None
        if is_ephemeral:
            assert expires_at is not None
            assert exit_action is not None
            assert rationale is not None
            expiry = _iso_date(expires_at, "expiry date")
            if date.fromisoformat(expiry) < date.fromisoformat(opened_at):
                raise DocSystemError("ephemeral expiry date cannot precede creation date")
            successor: str | None = None
            if exit_action == "delete":
                if successor_path is not None:
                    raise DocSystemError("ephemeral exit_action=delete forbids --successor-path")
            else:
                if successor_path is None or not successor_path.strip():
                    raise DocSystemError(
                        f"ephemeral exit_action={exit_action} requires a planned --successor-path"
                    )
                successor = _normalise_relpath(successor_path.strip())
                if successor == relpath:
                    raise DocSystemError("ephemeral successor_path must differ from the source path")
            ephemeral_config = self.intake_payload["ephemeral_documents"]
            registry_path = self.root / str(ephemeral_config["source"])
            registry_payload = dict(_read_json_object(registry_path, self.root))
            records = list(registry_payload["records"])
            if any(str(record["path"]) == relpath for record in records):
                raise DocSystemError(f"ephemeral path is already registered: {relpath}")
            records.append(
                {
                    "path": relpath,
                    "created_at": opened_at,
                    "expires_at": expiry,
                    "exit_action": exit_action,
                    "successor_path": successor,
                    "rationale": rationale.strip(),
                }
            )
            records.sort(key=lambda item: str(item["path"]))
            registry_payload["ledger_reviewed_at"] = opened_at
            registry_payload["records"] = records

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(f"# {title}\n", encoding="utf-8")
            if registry_path is not None and registry_payload is not None:
                _write_json_object_atomic(registry_path, registry_payload)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        self._invalidate_path_inventory()
        outputs = [relpath]
        if registry_path is not None:
            outputs.append(registry_path.relative_to(self.root).as_posix())
        outputs.extend((
            str(self.actions["docsystem.intake"]["command"]),
            str(self.actions["docsystem.check_changed"]["command"]),
        ))
        return tuple(outputs)

    def exit_ephemeral(self, path: str, *, exited_at: str | None = None) -> tuple[str, ...]:
        relpath = _normalise_relpath(path)
        when = _iso_date(exited_at or date.today().isoformat(), "ephemeral exit date")
        config = self.intake_payload["ephemeral_documents"]
        registry_relpath = str(config["source"])
        registry_path = self.root / registry_relpath
        payload: MutableMapping[str, Any] = dict(_read_json_object(registry_path, self.root))
        records = list(payload["records"])
        target = next((record for record in records if str(record["path"]) == relpath), None)
        if target is None:
            raise DocSystemError(f"ephemeral path is not registered: {relpath}")
        source_path = self.root / relpath
        if not source_path.is_file():
            raise DocSystemError(f"ephemeral source is missing: {relpath}")
        created = date.fromisoformat(str(target["created_at"]))
        if date.fromisoformat(when) < created:
            raise DocSystemError("ephemeral exit date cannot precede creation date")

        action = str(target["exit_action"])
        successor_raw = target.get("successor_path")
        successor = str(successor_raw) if isinstance(successor_raw, str) else None
        destination: Path | None = None
        if action in {"archive", "promote"}:
            if successor is None:
                raise DocSystemError(f"ephemeral {action} record has no successor_path")
            destination = self.root / successor
            if destination.exists():
                raise DocSystemError(f"ephemeral successor already exists: {successor}")
            resolution = self.resolve(successor, "create")
            if resolution.contract["document_class"] in {"unmanaged", "ephemeral"}:
                raise DocSystemError(
                    f"ephemeral successor must resolve to a durable non-ephemeral class: {successor}"
                )
            if resolution.contract["mutation"] in {"generator_only", "owner_only", "immutable"}:
                raise DocSystemError(
                    f"ephemeral successor cannot be created under mutation={resolution.contract['mutation']}"
                )
            current_classes = set(self.manifest["guidance_projection"]["include_document_classes"])
            if (
                resolution.contract["document_class"] in current_classes
                and not resolution.contract["section_refs"]
            ):
                raise DocSystemError(
                    f"ephemeral successor is current but has no explicit section_refs: {successor}"
                )

        remaining = [record for record in records if str(record["path"]) != relpath]
        payload["ledger_reviewed_at"] = when
        payload["records"] = remaining
        original = source_path.read_bytes()
        mode = source_path.stat().st_mode
        try:
            if destination is None:
                source_path.unlink()
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source_path, destination)
            _write_json_object_atomic(registry_path, payload)
        except Exception:
            if destination is not None and destination.exists() and not source_path.exists():
                source_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, source_path)
            elif destination is None and not source_path.exists():
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_bytes(original)
                os.chmod(source_path, mode & 0o7777)
            raise
        self._invalidate_path_inventory()
        outputs = [registry_relpath, f"EXITED: {relpath} action={action}"]
        if successor is not None:
            outputs.append(successor)
        outputs.extend((
            str(self.actions["docsystem.intake"]["command"]),
            str(self.actions["docsystem.doctor"]["command"]),
        ))
        return tuple(outputs)

    def register_local_evidence(
        self,
        path: str,
        *,
        title: str,
        manifest_path: str,
        recovery_instructions: str,
        opened_at: str | None = None,
        topics: Sequence[str] = (),
        source_locator: str | None = None,
    ) -> tuple[str, ...]:
        relpath = _normalise_relpath(path.rstrip("/"))
        parts = PurePosixPath(relpath).parts
        if len(parts) != 2 or parts[0] != ".artifacts":
            raise DocSystemError("local evidence path must be a direct child of .artifacts/")
        directory = self.root / relpath
        if not directory.is_dir():
            raise DocSystemError(f"local evidence directory is missing: {relpath}")
        manifest_relpath = _normalise_relpath(manifest_path)
        if not (manifest_relpath == relpath or manifest_relpath.startswith(f"{relpath}/")):
            raise DocSystemError("local evidence manifest_path must remain inside the evidence package")
        manifest_file = self.root / manifest_relpath
        if not manifest_file.is_file():
            raise DocSystemError(f"local evidence manifest is missing: {manifest_relpath}")
        recovery_relpath = _normalise_relpath(recovery_instructions)
        if recovery_relpath == relpath or recovery_relpath.startswith(f"{relpath}/"):
            raise DocSystemError(
                "recovery instructions must live outside the local evidence package so they survive payload loss"
            )
        if not (self.root / recovery_relpath).is_file():
            raise DocSystemError(f"recovery instructions are missing: {recovery_relpath}")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", recovery_relpath],
            cwd=self.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if tracked.returncode != 0:
            raise DocSystemError(
                f"recovery instructions must be Git-tracked independently of local evidence: {recovery_relpath}"
            )
        opened = _iso_date(opened_at or date.today().isoformat(), "evidence open date")
        topic_values = tuple(_dedupe(str(value).strip() for value in topics if str(value).strip())) or ("other",)
        invalid_topics = [
            value for value in topic_values if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value) is None
        ]
        if invalid_topics:
            raise DocSystemError("invalid dossier topic labels: " + ", ".join(invalid_topics))

        source = str(self.manifest["knowledge_sources"]["dossiers"])
        source_path = self.root / source
        payload: MutableMapping[str, Any] = dict(_read_json_object(source_path, self.root))
        records = list(payload["records"])
        if any(str(record["path"]) == relpath for record in records):
            raise DocSystemError(f"dossier path is already registered: {relpath}")
        from devtools.build_knowledge_docs import _entry_for_path, _slug_for_dossier

        dossier_id = _slug_for_dossier(relpath)
        if any(str(record["id"]) == dossier_id for record in records):
            raise DocSystemError(f"generated dossier ID is already registered: {dossier_id}")
        entry_file = _entry_for_path(self.root, relpath)
        record: dict[str, Any] = {
            "id": dossier_id,
            "path": relpath,
            "entry_file": entry_file,
            "title": title,
            "kind": "directory",
            "lifecycle": "active",
            "relevance": "unreviewed",
            "curation": "curated",
            "tracked_state": "local_optional",
            "date": opened,
            "topics": list(topic_values),
            "summary": "Local-optional evidence registered through docctl; semantic outcome is pending closure review.",
            "workflow": {"opened_at": opened, "closure": None},
            "portability": {
                "manifest_path": manifest_relpath,
                "manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
                "recovery_instructions": recovery_relpath,
            },
        }
        if source_locator is not None and source_locator.strip():
            record["portability"]["source_locator"] = source_locator.strip()
        records.append(record)
        records.sort(key=lambda item: str(item["path"]))
        payload["ledger_reviewed_at"] = opened
        payload["records"] = records
        _write_json_object_atomic(source_path, payload)
        return (
            source,
            f"DOSSIER: {dossier_id}",
            str(self.actions["knowledge.build"]["command"]),
            str(self.actions["docsystem.intake"]["command"]),
            str(self.actions["knowledge.check"]["command"]),
        )

    def close_dossier(
        self,
        dossier: str,
        *,
        outcome: str,
        closed_at: str,
        review_id: str,
        claim_ids: Sequence[str] = (),
        decision_ids: Sequence[str] = (),
        successor_dossier_ids: Sequence[str] = (),
        no_reusable_claim_reason: str | None = None,
    ) -> tuple[str, ...]:
        closed = _iso_date(closed_at, "dossier close date")
        source = str(self.manifest["knowledge_sources"]["dossiers"])
        source_path = self.root / source
        payload: MutableMapping[str, Any] = dict(_read_json_object(source_path, self.root))
        records = [dict(record) for record in payload["records"]]
        target: MutableMapping[str, Any] | None = None
        normalised_path: str | None = None
        if not dossier.startswith("DOSSIER-"):
            normalised_path = _normalise_relpath(dossier.rstrip("/"))
        for record in records:
            if str(record["id"]) == dossier or (normalised_path is not None and str(record["path"]) == normalised_path):
                target = record
                break
        if target is None:
            raise DocSystemError(f"unknown dossier: {dossier}")
        dossier_id = str(target["id"])
        if target["lifecycle"] != "active":
            raise DocSystemError(f"{dossier_id} is not active: lifecycle={target['lifecycle']}")

        self._ensure_knowledge()
        assert self._claims is not None
        assert self._decisions is not None
        assert self._backfill_reviews is not None
        review = self._backfill_reviews.get(review_id)
        if review is None or review["status"] != "current" or str(review["dossier_id"]) != dossier_id:
            raise DocSystemError(f"{review_id} is not the current semantic review for {dossier_id}")

        claim_values = tuple(_dedupe(str(value) for value in claim_ids))
        decision_values = tuple(_dedupe(str(value) for value in decision_ids))
        successor_values = tuple(_dedupe(str(value) for value in successor_dossier_ids))
        dossier_ids = {str(record["id"]) for record in records}
        for claim_id in claim_values:
            claim = self._claims.get(claim_id)
            if claim is None or dossier_id not in claim["dossier_ids"]:
                raise DocSystemError(f"closure claim must exist and cite {dossier_id}: {claim_id}")
        for decision_id in decision_values:
            decision = self._decisions.get(decision_id)
            if decision is None or dossier_id not in decision["dossier_ids"]:
                raise DocSystemError(f"closure decision must exist and cite {dossier_id}: {decision_id}")
        for successor_id in successor_values:
            if successor_id == dossier_id or successor_id not in dossier_ids:
                raise DocSystemError(f"invalid successor dossier: {successor_id}")

        reason = no_reusable_claim_reason.strip() if no_reusable_claim_reason else None
        review_claim_ids = {str(value) for value in review["claim_ids"]}
        review_outcome = str(review["outcome"])
        if outcome == "knowledge_promoted":
            if not claim_values or decision_values or successor_values or reason is not None:
                raise DocSystemError(
                    "knowledge_promoted requires claim IDs and forbids decisions, successors and a no-result reason"
                )
            if not set(claim_values) <= review_claim_ids:
                raise DocSystemError("knowledge_promoted claim IDs must be listed by the closure review")
            if review_outcome not in {"claims_promoted", "existing_claims_confirmed", "inconclusive"}:
                raise DocSystemError(
                    f"knowledge_promoted conflicts with review outcome={review_outcome}"
                )
        elif outcome == "negative_results_promoted":
            if decision_values or successor_values or reason is not None:
                raise DocSystemError(
                    "negative_results_promoted forbids decisions, successors and a no-result reason"
                )
            if not claim_values or any(self._claims[claim_id]["kind"] != "negative_result" for claim_id in claim_values):
                raise DocSystemError("negative_results_promoted requires only negative-result --claim-id values")
            if not set(claim_values) <= review_claim_ids or review_outcome != "claims_promoted":
                raise DocSystemError("negative_results_promoted claims must be promoted by the closure review")
        elif outcome == "decision_recorded":
            if claim_values or not decision_values or successor_values or reason is not None:
                raise DocSystemError(
                    "decision_recorded requires decision IDs and forbids claims, successors and a no-result reason"
                )
        elif outcome == "no_reusable_claim":
            if claim_values or decision_values or successor_values or not reason:
                raise DocSystemError(
                    "no_reusable_claim requires only --no-reusable-claim-reason"
                )
            if review_outcome != "no_reusable_claim":
                raise DocSystemError(
                    f"no_reusable_claim conflicts with review outcome={review_outcome}"
                )
        elif outcome == "superseded_by_dossier":
            if not successor_values or reason is not None:
                raise DocSystemError(
                    "superseded_by_dossier requires successor dossiers and forbids a no-result reason"
                )
        else:
            raise DocSystemError(f"unsupported dossier closure outcome: {outcome}")

        workflow = target.get("workflow")
        opened_at = str(target.get("date") or closed)
        if isinstance(workflow, dict):
            opened_at = str(workflow["opened_at"])
        if date.fromisoformat(closed) < date.fromisoformat(_iso_date(opened_at, "dossier open date")):
            raise DocSystemError("dossier close date cannot precede its open date")
        target["lifecycle"] = "superseded" if outcome == "superseded_by_dossier" else "historical"
        target["workflow"] = {
            "opened_at": opened_at,
            "closure": {
                "closed_at": closed,
                "outcome": outcome,
                "review_id": review_id,
                "claim_ids": list(claim_values),
                "decision_ids": list(decision_values),
                "successor_dossier_ids": list(successor_values),
                "no_reusable_claim_reason": reason,
            },
        }
        payload["ledger_reviewed_at"] = closed
        payload["records"] = records
        _write_json_object_atomic(source_path, payload)
        return (
            source,
            f"CLOSED: {dossier_id} outcome={outcome}",
            str(self.actions["knowledge.build"]["command"]),
            str(self.actions["docsystem.intake"]["command"]),
            str(self.actions["knowledge.check"]["command"]),
        )


# ----------------------------------------------------------------------
# pure helpers
# ----------------------------------------------------------------------


def _iso_date(value: str, label: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise DocSystemError(f"{label} must use YYYY-MM-DD: {value!r}") from exc


def _write_json_object_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DocSystemError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise DocSystemError(f"non-finite JSON constant: {value}")


def _parse_json(text: str, label: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise DocSystemError(f"cannot parse strict JSON {label}: {exc}") from exc


def _markdown_link_targets(root: Path, source_relpath: str, text: str) -> set[str]:
    """Resolve repository-local Markdown links to canonical relative paths."""

    source = root / source_relpath
    targets: set[str] = set()
    for match in re.finditer(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", text):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<"):
            close = raw_target.find(">")
            if close < 0:
                continue
            target = raw_target[1:close]
        else:
            target = raw_target.split(maxsplit=1)[0]
        if not target or target.startswith("#"):
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        candidate = (source.parent / path_part).resolve()
        try:
            relpath = candidate.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        targets.add(relpath)
    return targets


def _read_json_object(path: Path, root: Path) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        label = _display_path(path, root)
        raise DocSystemError(f"cannot read {label}: {exc}") from exc
    value = _parse_json(text, _display_path(path, root))
    if not isinstance(value, dict):
        raise DocSystemError(f"{_display_path(path, root)} root must be an object")
    return value


def _read_jsonl(path: Path, root: Path) -> tuple[Mapping[str, Any], ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise DocSystemError(f"cannot read {_display_path(path, root)}: {exc}") from exc
    records: list[Mapping[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        value = _parse_json(line, f"{_display_path(path, root)}:{index}")
        if not isinstance(value, dict):
            raise DocSystemError(f"{_display_path(path, root)}:{index} must be an object")
        records.append(value)
    return tuple(records)


def _validate_schema_and_value(schema: Mapping[str, Any], value: Mapping[str, Any], label: str) -> None:
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
    except jsonschema.SchemaError as exc:
        raise DocSystemError(f"schema for {label} is invalid: {exc.message}") from exc
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise DocSystemError(f"{label} schema error at {location}: {error.message}")


def _normalise_relpath(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocSystemError("repository-relative path must be a non-empty string")
    pure = PurePosixPath(value)
    if value.startswith("/") or ".." in pure.parts or "\\" in value or "\0" in value:
        raise DocSystemError(f"unsafe repository-relative path: {value!r}")
    normalised = pure.as_posix()
    if normalised in {"", "."}:
        raise DocSystemError(f"path must name a repository member: {value!r}")
    return normalised


def _target_relpath(root: Path, target: str | Path) -> str:
    path = Path(target)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root)
        except ValueError as exc:
            raise DocSystemError(f"target lies outside repository: {target}") from exc
        return _normalise_relpath(path.as_posix())
    return _normalise_relpath(PurePosixPath(os.fspath(target)).as_posix())


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _relative_to_policy(target: str, base: str) -> str:
    if not base:
        return target
    prefix = f"{base}/"
    if target == base:
        return "."
    if not target.startswith(prefix):
        raise DocSystemError(f"target {target} is outside policy base {base}")
    return target[len(prefix) :]


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    out = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if pattern.startswith("**/", index):
                out.append("(?:[^/]+/)*")
                index += 3
                continue
            if pattern.startswith("**", index):
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
            index += 1
            continue
        if char == "?":
            out.append("[^/]")
            index += 1
            continue
        out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


def _glob_match(path: str, pattern: str) -> bool:
    return _glob_to_regex(pattern).match(path) is not None


def _matches(path: str, matcher: Mapping[str, Any]) -> bool:
    if len(matcher) != 1:
        raise DocSystemError(f"match object must have exactly one selector: {matcher!r}")
    selector, value = next(iter(matcher.items()))
    if selector == "path":
        return path == value
    if selector == "paths":
        return path in value
    if selector == "prefix":
        prefix = str(value)
        if not prefix.endswith("/"):
            raise DocSystemError(f"prefix selector must end in '/': {prefix!r}")
        return path.startswith(prefix)
    if selector == "glob":
        return _glob_match(path, str(value))
    raise DocSystemError(f"unsupported match selector: {selector}")


def _matcher_specificity(matcher: Mapping[str, Any]) -> tuple[int, int]:
    """Return deterministic rule precedence; larger tuples are more specific.

    Prefix and glob rules provide directory-wide defaults.  Exact path selectors
    may refine those defaults without duplicating a whole policy.  Two matching
    rules at the same specificity may not disagree on a scalar, because their
    winner would otherwise depend on declaration order.
    """

    selector, value = next(iter(matcher.items()))
    if selector == "prefix":
        return (10, len(str(value)))
    if selector == "glob":
        pattern = str(value)
        literal_count = sum(character not in "*?" for character in pattern)
        return (20, literal_count)
    if selector == "paths":
        # Every member is an exact path.  Unrelated longer members in the same
        # selector must not manufacture a higher precedence for this target.
        return (30, 0)
    if selector == "path":
        return (40, len(str(value)))
    raise DocSystemError(f"unsupported match selector: {selector}")


def _ordered_matching_rules(
    path: str,
    rules: Sequence[Mapping[str, Any]],
    policy_relpath: str,
) -> list[Mapping[str, Any]]:
    matched = [rule for rule in rules if _matches(path, rule["match"])]
    by_specificity: dict[tuple[int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for rule in matched:
        by_specificity[_matcher_specificity(rule["match"])].append(rule)

    for specificity, group in by_specificity.items():
        values: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for rule in group:
            for key, value in rule["set"].items():
                if key in LIST_FIELDS:
                    continue
                serialised = json.dumps(value, ensure_ascii=False, sort_keys=True)
                values[key][serialised].append(str(rule["id"]))
        conflicts = {key: entries for key, entries in values.items() if len(entries) > 1}
        if conflicts:
            descriptions = []
            for key, entries in sorted(conflicts.items()):
                descriptions.append(
                    f"{key}: " + "; ".join(f"{value} by {','.join(rule_ids)}" for value, rule_ids in entries.items())
                )
            raise DocSystemError(
                f"{policy_relpath}: equal-specificity rules {specificity} set "
                "conflicting scalars: " + " | ".join(descriptions)
            )
    return sorted(matched, key=lambda rule: _matcher_specificity(rule["match"]))


def _append_values(
    contract: MutableMapping[str, Any],
    field_sources: MutableMapping[str, list[str]],
    key: str,
    values: Iterable[Any],
    source: str,
) -> None:
    current = list(contract.get(key, []))
    for value in values:
        if value not in current:
            current.append(_deepcopy_json(value))
    contract[key] = current
    field_sources.setdefault(key, []).append(source)


def _set_scalar(
    contract: MutableMapping[str, Any],
    field_sources: MutableMapping[str, list[str]],
    key: str,
    value: Any,
    source: str,
) -> None:
    contract[key] = value
    field_sources.setdefault(key, []).append(source)


def _deepcopy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _dedupe(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _ensure_unique(records: Iterable[Mapping[str, Any]], key: str, label: str) -> None:
    seen: set[str] = set()
    for record in records:
        value = str(record[key])
        if value in seen:
            raise DocSystemError(f"duplicate {label} {key}: {value}")
        seen.add(value)


def _policy_contracts(
    policy: LoadedPolicy,
) -> Iterable[tuple[Mapping[str, Any], str]]:
    yield policy.payload["defaults"], f"{policy.relpath}#defaults"
    for rule in policy.payload["rules"]:
        yield rule["set"], f"{policy.relpath}#{rule['id']}"


def _operation_guidance(intent: str, mutation: str, exists: bool) -> tuple[bool, str]:
    if intent == "read":
        return True, "Read is allowed; preserve authority and lifecycle boundaries when citing it."
    if intent == "create" and not exists:
        if mutation in {"generator_only", "owner_only"}:
            return False, f"Create through the declared authority/generator; mutation={mutation}."
        if mutation == "immutable":
            return True, "The new evidence record may be created once; after creation it is immutable."
        return True, "Creation is allowed under the resolved parent policy; run the listed checks."
    if mutation == "direct":
        return True, "Direct edit is allowed within the stated purpose and authority boundary."
    if mutation == "append_only":
        if intent in {"move", "delete"}:
            return False, "Append-only material cannot be moved or deleted; append a successor/correction."
        return True, "Only append a new dated entry or explicit correction; do not rewrite prior text."
    if mutation == "governed":
        return (
            True,
            "Use the governed change packet: read required guides/ADRs and update tests/projections atomically.",
        )
    if mutation == "generator_only":
        return False, "Do not edit this projection. Change its declared source paths and run the generator action."
    if mutation == "owner_only":
        return False, "Only an explicit owner action may change this authority surface."
    if mutation == "immutable":
        return False, "Preserve the body. Add an erratum, superseding claim/decision, or successor document instead."
    raise DocSystemError(f"unsupported mutation mode: {mutation}")


def _run_git(root: Path, args: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise DocSystemError(f"cannot execute git {' '.join(args)}: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise DocSystemError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout


def _git_toplevel(root: Path) -> Path:
    raw = _run_git(root, ["rev-parse", "--show-toplevel"])
    try:
        value = raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise DocSystemError("git worktree root is not valid UTF-8") from exc
    if not value:
        raise DocSystemError("git rev-parse returned an empty worktree root")
    return Path(value).resolve()


def _parse_nul_paths(raw: bytes) -> tuple[str, ...]:
    return tuple(os.fsdecode(item) for item in raw.split(b"\0") if item)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _path_at_revision(root: Path, revision: str, relpath: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}:{relpath}"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _path_bytes_at_revision(root: Path, revision: str, relpath: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{relpath}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _policy_rule_is_exact_coverage(rule: Mapping[str, Any]) -> bool:
    match = rule.get("match")
    if not isinstance(match, Mapping):
        return False
    if set(match) == {"path"}:
        values = [match.get("path")]
    elif set(match) == {"paths"} and isinstance(match.get("paths"), list):
        values = list(match["paths"])
    else:
        return False
    if not values:
        return False
    return all(
        isinstance(value, str)
        and value
        and not any(character in value for character in "*?[]")
        for value in values
    )


def _classify_policy_change(
    root: Path,
    revision: str,
    relpath: str,
) -> str:
    """Classify a local policy diff without conflating coverage with framework semantics.

    ``coverage_update`` adds exact-path rules while preserving every existing
    policy field and rule. ``contract_change`` changes a local contract or
    inheritance anchor. Schema/resolver/default-semantics changes are classified
    separately by the framework-core path set in ``check_changed``.
    """

    current_path = root / relpath
    previous_raw = _path_bytes_at_revision(root, revision, relpath)
    if previous_raw is None or not current_path.is_file():
        return "contract_change"
    try:
        previous_value = _parse_json(previous_raw.decode("utf-8"), f"{revision}:{relpath}")
        current_value = _parse_json(current_path.read_text(encoding="utf-8"), relpath)
    except (UnicodeDecodeError, OSError, DocSystemError):
        return "contract_change"
    if not isinstance(previous_value, Mapping) or not isinstance(current_value, Mapping):
        return "contract_change"
    previous = dict(previous_value)
    current = dict(current_value)
    previous_rules = previous.pop("rules", None)
    current_rules = current.pop("rules", None)
    if previous != current or not isinstance(previous_rules, list) or not isinstance(current_rules, list):
        return "contract_change"
    previous_by_id = {
        str(rule.get("id")): rule
        for rule in previous_rules
        if isinstance(rule, Mapping) and isinstance(rule.get("id"), str)
    }
    current_by_id = {
        str(rule.get("id")): rule
        for rule in current_rules
        if isinstance(rule, Mapping) and isinstance(rule.get("id"), str)
    }
    if len(previous_by_id) != len(previous_rules) or len(current_by_id) != len(current_rules):
        return "contract_change"
    if any(current_by_id.get(rule_id) != rule for rule_id, rule in previous_by_id.items()):
        return "contract_change"
    added = [current_by_id[rule_id] for rule_id in current_by_id.keys() - previous_by_id.keys()]
    if added and all(_policy_rule_is_exact_coverage(rule) for rule in added):
        return "coverage_update"
    return "contract_change"


def _pattern_touches_changed(pattern: str, changed: set[str]) -> bool:
    if any(character in pattern for character in "*?"):
        return any(_glob_match(path, pattern) for path in changed)
    path = pattern.rstrip("/")
    return any(item == path or item.startswith(f"{path}/") for item in changed)


def _dossier_root_for_path(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if len(parts) >= 3 and parts[:2] == ("docs", "research"):
        if len(parts) == 3 and parts[2] in {"README.md", "INDEX.md", "DOC_POLICY.json"}:
            return None
        return "/".join(parts[:3])
    if len(parts) >= 2 and parts[0] == ".artifacts":
        if parts[1] in {"README.md", "DOC_POLICY.json"}:
            return None
        return "/".join(parts[:2])
    return None


def _render_card(resolution: Resolution) -> str:
    contract = resolution.contract
    lines = [
        f"TARGET: {resolution.target}",
        f"INTENT: {resolution.intent}",
        f"EXISTS: {'yes' if resolution.exists else 'no'}",
        f"ALLOWED: {'yes' if resolution.allowed else 'no'}",
        f"LEVEL: {contract['context_level']}",
        f"CLASS: {contract['document_class']}",
        f"AUTHORITY: {contract['authority_role']}",
        f"MUTATION: {contract['mutation']}",
        f"VOLATILE FACTS: {contract['volatile_facts']}",
        f"PURPOSE: {contract['purpose']}",
    ]
    if resolution.entrypoint is not None:
        entrypoint = resolution.entrypoint
        lines.append(
            f"ENTRYPOINT: {entrypoint['kind']} {entrypoint['id']}"
            + (f" mode={entrypoint['mode']}" if entrypoint["kind"] == "surface" else "")
        )
        if entrypoint.get("max_lines") is not None:
            lines.append(f"ATTENTION BUDGET: {entrypoint['max_lines']} lines / {entrypoint['max_bytes']} bytes")
        if entrypoint["kind"] == "redirect":
            lines.append("WRITE THROUGH: " + str(resolution.contract.get("generator_action") or "registry generator"))
    if resolution.sections:
        lines.append("SECTIONS:")
        for section in resolution.sections:
            lines.append(
                f"  {section['id']} -> {section['entry_path']}: {section['purpose']}"
            )
    lines.extend(("", f"OPERATION: {resolution.operation_guidance}"))
    if resolution.dossier is not None:
        lines.extend(
            [
                "",
                "DOSSIER:",
                f"  {resolution.dossier['id']} lifecycle={resolution.dossier['lifecycle']} "
                f"relevance={resolution.dossier['relevance']}",
            ]
        )
        workflow = resolution.dossier.get("workflow")
        if (
            resolution.dossier.get("lifecycle") == "active"
            and isinstance(workflow, Mapping)
            and workflow.get("closure") is None
        ):
            lines.append(f"  workflow=open opened={workflow['opened_at']}")
            lines.append("  semantic coverage: pending typed closure review")
    if resolution.ephemeral is not None:
        record = resolution.ephemeral
        lines.extend(
            [
                "",
                "EPHEMERAL LIFECYCLE:",
                f"  created={record['created_at']} expires={record['expires_at']} "
                f"exit={record['exit_action']}",
                f"  rationale: {record['rationale']}",
            ]
        )
    if resolution.reviews:
        lines.extend(["", "CURATION REVIEW:"])
        for review in resolution.reviews:
            lines.append(
                f"  {review['id']} reviewed={review['reviewed_at']} "
                f"scope={review['review_scope']} outcome={review['outcome']}"
            )
            lines.append(f"  summary: {review['summary']}")
            if review["claim_ids"]:
                lines.append(f"  claims: {', '.join(review['claim_ids'])}")
            if review["unresolved"]:
                lines.append(f"  unresolved: {'; '.join(review['unresolved'])}")
            semantic = (
                "no (availability/provenance only)"
                if review["review_scope"] == "availability_and_provenance"
                else "yes"
            )
            lines.append(f"  semantic coverage: {semantic}")
            lines.append(f"  next trigger: {review['next_review_trigger']}")
    if resolution.triage is not None:
        triage = resolution.triage
        lines.extend(
            [
                "",
                "BACKFILL TRIAGE:",
                f"  {triage['id']} disposition={triage['disposition']} priority={triage['priority']}",
                "  semantic coverage: no (inventory triage only)",
                f"  rationale: {triage['rationale']}",
            ]
        )
        if triage["related_claim_ids"]:
            lines.append(f"  related claims: {', '.join(triage['related_claim_ids'])}")
        lines.append(f"  reopen when: {'; '.join(triage['reopen_triggers'])}")
    if resolution.topics:
        lines.extend(["", "TOPIC COORDINATES:"])
        for topic in resolution.topics:
            lines.append(f"  {topic['id']} {topic['title']}: {topic['summary']}")
    if resolution.invariant_summaries:
        lines.extend(["", "WHY:"])
        for item in resolution.invariant_summaries:
            lines.append(f"  {item['id']} {item['title']}: {item['short_reason']}")
    if contract["source_paths"]:
        lines.extend(["", "WRITE THROUGH:"])
        for path in contract["source_paths"]:
            lines.append(f"  {path}")
        if contract["generator_action"]:
            lines.append(f"  generator action: {contract['generator_action']}")
    if resolution.knowledge:
        lines.extend(["", "RELATED KNOWLEDGE:"])
        for record in resolution.knowledge:
            lines.append(f"  {record['id']} [{record['status']}] {record['title']}: {record['statement']}")
            separation = record.get("separation_profile")
            if isinstance(separation, Mapping):
                lines.append(
                    "  mechanism: "
                    f"stage={separation['target_stage']} "
                    f"source={separation['candidate_source']} "
                    f"select={','.join(str(item) for item in separation['selection_modes'])} "
                    f"validate={','.join(str(item) for item in separation['validation_modes'])} "
                    f"complete={separation['completeness']} "
                    f"consume={','.join(str(item) for item in separation['consumption_modes'])} "
                    f"baseline={separation['baseline_comparison']}"
                )
            validity = record.get("validity_profile")
            if isinstance(validity, Mapping):
                lines.append(
                    "  validity: "
                    f"event={validity['event_type']} "
                    f"layers={','.join(str(item) for item in validity['affected_layers'])} "
                    f"reuse={validity['reuse_policy']} "
                    f"repair={validity['repair_state']} "
                    f"time={validity['temporal_scope']} "
                    f"basis={','.join(str(item) for item in validity['basis'])}"
                )
    if contract["required_reads"] or resolution.adr_paths:
        lines.extend(["", "LOAD WHEN OPERATING:"])
        for path in contract["required_reads"]:
            lines.append(f"  {path}")
        for path in resolution.adr_paths:
            lines.append(f"  {path}")
    if resolution.action_commands:
        lines.extend(["", "AFTER CHANGE:"])
        for action in resolution.action_commands:
            lines.append(f"  {action['command']}")
    lines.extend(
        [
            "",
            f"FRAMEWORK: {BOOTSTRAP_RELPATH}",
            "  Use `docctl guide` for the complete architecture and maintenance coordinates.",
        ]
    )
    return "\n".join(lines) + "\n"


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def _add_repo_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="repository root (default: inferred from this script)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    context = subparsers.add_parser("context", help="resolve a compact operation card")
    _add_repo_root(context)
    context.add_argument("path")
    context.add_argument(
        "--intent",
        choices=("read", "edit", "create", "move", "delete", "framework-change"),
        default="edit",
    )
    context.add_argument("--json", action="store_true", help="emit machine-readable context")

    explain = subparsers.add_parser("explain", help="explain an invariant, ADR, action or policy id")
    _add_repo_root(explain)
    explain.add_argument("identifier")
    explain.add_argument("--full", action="store_true", help="print ADR contents as well as its path")
    explain.add_argument("--json", action="store_true")

    guide = subparsers.add_parser("guide", help="show complete framework guide coordinates")
    _add_repo_root(guide)
    guide.add_argument("--json", action="store_true")

    doctor = subparsers.add_parser("doctor", help="validate the document framework")
    _add_repo_root(doctor)

    render = subparsers.add_parser("render-legacy", help="render the legacy doc_classes compatibility projection")
    _add_repo_root(render)
    mode = render.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")

    guidance = subparsers.add_parser("render-guidance", help="render the current document-responsibility projection")
    _add_repo_root(guidance)
    guidance_mode = guidance.add_mutually_exclusive_group()
    guidance_mode.add_argument("--write", action="store_true")
    guidance_mode.add_argument("--check", action="store_true")

    entrypoints = subparsers.add_parser("render-entrypoints", help="render generated compatibility entrypoints")
    _add_repo_root(entrypoints)
    entrypoint_mode = entrypoints.add_mutually_exclusive_group()
    entrypoint_mode.add_argument("--write", action="store_true")
    entrypoint_mode.add_argument("--check", action="store_true")

    sections = subparsers.add_parser("render-sections", help="render the current document-section projection")
    _add_repo_root(sections)
    section_mode = sections.add_mutually_exclusive_group()
    section_mode.add_argument("--write", action="store_true")
    section_mode.add_argument("--check", action="store_true")

    convergence = subparsers.add_parser(
        "render-convergence",
        help="render the current-document convergence acceptance report",
    )
    _add_repo_root(convergence)
    convergence_mode = convergence.add_mutually_exclusive_group()
    convergence_mode.add_argument("--write", action="store_true")
    convergence_mode.add_argument("--check", action="store_true")

    maintenance = subparsers.add_parser(
        "render-maintenance",
        help="render the periodic maintenance queue projection",
    )
    _add_repo_root(maintenance)
    maintenance_mode = maintenance.add_mutually_exclusive_group()
    maintenance_mode.add_argument("--write", action="store_true")
    maintenance_mode.add_argument("--check", action="store_true")

    audit = subparsers.add_parser("audit", help="run a read-only periodic maintenance audit")
    _add_repo_root(audit)
    audit.add_argument("--profile", default="weekly")
    audit.add_argument("--as-of", help="audit clock in YYYY-MM-DD (default: today)")
    audit.add_argument("--json", action="store_true")

    intake = subparsers.add_parser("intake", help="derive and validate event-driven document intake")
    _add_repo_root(intake)
    intake.add_argument("--changed", action="store_true", help="inspect current Git-visible changes")
    intake.add_argument("--base", help="also include base...HEAD committed diff")
    intake.add_argument("--json", action="store_true")

    check = subparsers.add_parser("check", help="diff-aware document/framework validation")
    _add_repo_root(check)
    check.add_argument("--changed", action="store_true", help="check current Git changes")
    check.add_argument("--base", help="also include base...HEAD committed diff")
    check.add_argument("--json", action="store_true")

    gate = subparsers.add_parser("gate", help="run the manifest-owned non-mutating governance gate")
    _add_repo_root(gate)
    gate.add_argument("--profile")
    gate.add_argument("--base")
    gate.add_argument("--lane", action="append", default=[])
    gate.add_argument("--json", action="store_true")

    landing = subparsers.add_parser("landing", help="delegate to the non-destructive real-repository landing runner")
    _add_repo_root(landing)
    landing.add_argument("landing_args", nargs=argparse.REMAINDER)

    new = subparsers.add_parser("new", help="create a policy-aware document scaffold")
    _add_repo_root(new)
    new.add_argument("kind", choices=("document", "research-dossier"))
    new.add_argument("path")
    new.add_argument("--title", required=True)
    new.add_argument("--date", help="creation/open date in YYYY-MM-DD")
    new.add_argument("--topic", action="append", default=[], help="dossier topic label; repeatable")
    new.add_argument("--expires-at", help="required when the target resolves as ephemeral")
    new.add_argument("--exit-action", choices=("archive", "delete", "promote"))
    new.add_argument("--successor-path", help="planned durable destination for archive/promote exit")
    new.add_argument("--rationale", help="why the temporary document exists")

    exit_ephemeral = subparsers.add_parser("exit-ephemeral", help="execute a registered ephemeral exit")
    _add_repo_root(exit_ephemeral)
    exit_ephemeral.add_argument("path")
    exit_ephemeral.add_argument("--exited-at", help="exit date in YYYY-MM-DD")

    register_local = subparsers.add_parser(
        "register-local-evidence", help="register a local-optional evidence package with portability metadata"
    )
    _add_repo_root(register_local)
    register_local.add_argument("path")
    register_local.add_argument("--title", required=True)
    register_local.add_argument("--manifest-path", required=True)
    register_local.add_argument("--recovery-instructions", required=True)
    register_local.add_argument("--opened-at")
    register_local.add_argument("--topic", action="append", default=[])
    register_local.add_argument("--source-locator")

    close = subparsers.add_parser("close-dossier", help="close an active dossier with a typed outcome")
    _add_repo_root(close)
    close.add_argument("dossier")
    close.add_argument("--outcome", required=True, choices=(
        "knowledge_promoted",
        "negative_results_promoted",
        "decision_recorded",
        "no_reusable_claim",
        "superseded_by_dossier",
    ))
    close.add_argument("--closed-at", required=True)
    close.add_argument("--review-id", required=True)
    close.add_argument("--claim-id", action="append", default=[])
    close.add_argument("--decision-id", action="append", default=[])
    close.add_argument("--successor-dossier-id", action="append", default=[])
    close.add_argument("--no-reusable-claim-reason")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        system = DocumentSystem(args.repo_root)
        if args.command == "context":
            resolution = system.resolve(args.path, args.intent)
            if args.json:
                print(json.dumps(resolution.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(_render_card(resolution), end="")
            return 0 if resolution.allowed else 2

        if args.command == "explain":
            record = dict(system.explain(args.identifier))
            if args.full and record.get("kind") == "adr":
                record["content"] = (system.root / str(record["path"])).read_text(encoding="utf-8")
            if args.json:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            elif record.get("kind") == "adr":
                print(f"{record['id']}: {record['path']}")
                if args.full:
                    print(record["content"])
            else:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0

        if args.command == "guide":
            guide = system.guide()
            if args.json:
                print(json.dumps(guide, ensure_ascii=False, indent=2))
            else:
                print(f"document system {guide['system_version']}")
                for key in (
                    "bootstrap",
                    "architecture",
                    "maintenance",
                    "steady_state",
                    "recovery",
                    "adr_directory",
                    "entrypoints",
                    "sections",
                    "section_index",
                    "convergence_report",
                    "governance_gate",
                    "governance_gate_schema",
                    "governance_runner",
                    "governance_ci",
                    "governance_default_profile",
                    "intake_protocol",
                    "intake_schema",
                    "maintenance_audit",
                    "maintenance_audit_schema",
                    "maintenance_queue",
                    "landing_protocol",
                    "landing_schema",
                    "landing_ack_schema",
                    "landing_runner",
                    "landing_guide",
                ):
                    print(f"{key}: {guide[key]}")
            return 0

        if args.command == "doctor":
            failures = system.doctor()
            if failures:
                for failure in failures:
                    print(f"BLOCK: {failure}")
                return 1
            print("PASS: document system is self-consistent and compatibility projections are fresh")
            return 0

        if args.command == "render-legacy":
            expected = system.render_legacy_projection()
            output = system.root / str(system.manifest["legacy_projection"]["output"])
            if args.write:
                system.write_legacy_projection()
                print(f"wrote {output.relative_to(system.root).as_posix()}")
                return 0
            try:
                actual = output.read_text(encoding="utf-8")
            except OSError as exc:
                raise DocSystemError(f"cannot read {output}: {exc}") from exc
            if actual != expected:
                print("BLOCK: legacy projection is stale")
                return 1
            print("PASS: legacy projection is fresh")
            return 0

        if args.command == "render-guidance":
            expected = system.render_guidance_projection()
            output = system.root / str(system.manifest["guidance_projection"]["output"])
            if args.write:
                system.write_guidance_projection()
                print(f"wrote {output.relative_to(system.root).as_posix()}")
                return 0
            try:
                actual = output.read_text(encoding="utf-8")
            except OSError as exc:
                raise DocSystemError(f"cannot read {output}: {exc}") from exc
            if actual != expected:
                print("BLOCK: guidance projection is stale")
                return 1
            print("PASS: guidance projection is fresh")
            return 0

        if args.command == "render-entrypoints":
            entrypoint_outputs = system.render_entrypoint_redirects()
            if args.write:
                system.write_entrypoint_redirects()
                print(f"wrote {len(entrypoint_outputs)} generated compatibility entrypoints")
                return 0
            stale: list[str] = []
            for relpath, content in entrypoint_outputs.items():
                try:
                    actual = (system.root / relpath).read_text(encoding="utf-8")
                except OSError:
                    stale.append(relpath)
                    continue
                if actual != content:
                    stale.append(relpath)
            if stale:
                print("BLOCK: generated compatibility entrypoints are stale: " + ", ".join(stale))
                return 1
            print("PASS: generated compatibility entrypoints are fresh")
            return 0

        if args.command == "render-sections":
            expected = system.render_section_projection()
            output = system.root / str(system.manifest["section_projection"]["output"])
            if args.write:
                system.write_section_projection()
                print(f"wrote {output.relative_to(system.root).as_posix()}")
                return 0
            try:
                actual = output.read_text(encoding="utf-8")
            except OSError as exc:
                raise DocSystemError(f"cannot read {output}: {exc}") from exc
            if actual != expected:
                print("BLOCK: section projection is stale")
                return 1
            print("PASS: section projection is fresh")
            return 0

        if args.command == "render-convergence":
            expected = system.render_convergence_projection()
            output = system.root / str(system.manifest["convergence_projection"]["output"])
            if args.write:
                system.write_convergence_projection()
                print(f"wrote {output.relative_to(system.root).as_posix()}")
                return 0
            try:
                actual = output.read_text(encoding="utf-8")
            except OSError as exc:
                raise DocSystemError(f"cannot read {output}: {exc}") from exc
            if actual != expected:
                print("BLOCK: convergence projection is stale")
                return 1
            failures = system.convergence_audit()["failures"]
            if failures:
                for failure in failures:
                    print(f"BLOCK: {failure}")
                return 1
            print("PASS: convergence projection is fresh and the current document graph is closed")
            return 0

        if args.command == "render-maintenance":
            expected = system.render_maintenance_projection()
            output = system.root / str(system.manifest["maintenance_audit"]["projection"])
            if args.write:
                system.write_maintenance_projection()
                print(f"wrote {output.relative_to(system.root).as_posix()}")
                return 0
            try:
                actual = output.read_text(encoding="utf-8")
            except OSError as exc:
                raise DocSystemError(f"cannot read {output}: {exc}") from exc
            if actual != expected:
                print("BLOCK: maintenance projection is stale")
                return 1
            print("PASS: maintenance projection is fresh")
            return 0

        if args.command == "audit":
            result = run_maintenance_audit(
                system,
                profile=args.profile,
                as_of=parse_audit_date(args.as_of),
            )
            if args.json:
                print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            else:
                counts = result.counts
                print(
                    f"maintenance audit {result.profile} as_of={result.as_of} "
                    f"errors={counts['error']} warnings={counts['warning']} info={counts['info']}"
                )
                for finding in result.findings:
                    print(
                        f"[{finding.severity.upper()}] {finding.check_id} "
                        f"{finding.subject}: {finding.message}"
                    )
                action_ids = _dedupe(
                    action_id
                    for finding in result.findings
                    for action_id in finding.action_ids
                )
                if action_ids:
                    print("available actions:")
                    for action in system._action_records(action_ids):
                        print(f"  {action['command']}")
            return 0 if result.passed else 1

        if args.command == "intake":
            if not args.changed and args.base is None:
                raise DocSystemError("intake requires --changed or --base")
            intake_result = system.intake_changed(args.base)
            if args.json:
                print(json.dumps(intake_result.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(f"comparison revision: {intake_result.comparison_revision}")
                print(f"changed paths: {len(intake_result.paths)}")
                for event in intake_result.events:
                    print(f"{event.id}: {event.title} ({len(event.paths)} paths)")
                    for relpath in event.paths:
                        print(f"  {relpath}")
                    for failure in event.failures:
                        print(f"  BLOCK: {failure}")
                    for warning in event.warnings:
                        print(f"  WARN: {warning}")
                if intake_result.actions:
                    print("required checks:")
                    for action in intake_result.actions:
                        print(f"  {action['command']}")
            return 1 if intake_result.failures else 0

        if args.command == "check":
            if not args.changed and args.base is None:
                raise DocSystemError("check requires --changed or --base")
            check_result = system.check_changed(args.base)
            payload = {
                "paths": list(check_result.paths),
                "failures": list(check_result.failures),
                "warnings": list(check_result.warnings),
                "actions": [dict(value) for value in check_result.actions],
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"changed paths: {len(check_result.paths)}")
                for failure in check_result.failures:
                    print(f"BLOCK: {failure}")
                for warning in check_result.warnings:
                    print(f"WARN: {warning}")
                if check_result.actions:
                    print("required checks:")
                    for action in check_result.actions:
                        print(f"  {action['command']}")
            return 1 if check_result.failures else 0

        if args.command == "gate":
            command = [
                sys.executable,
                str(system.root / str(system.manifest["governance_gate"]["runner"])),
                "run",
                "--repo-root",
                str(system.root),
            ]
            if args.profile is not None:
                command.extend(["--profile", args.profile])
            if args.base is not None:
                command.extend(["--base", args.base])
            for lane_id in args.lane:
                command.extend(["--lane", lane_id])
            if args.json:
                command.append("--json")
            completed = subprocess.run(command, cwd=system.root, check=False)
            return completed.returncode

        if args.command == "landing":
            delegated = list(args.landing_args)
            if delegated and delegated[0] == "--":
                delegated = delegated[1:]
            if not delegated:
                raise DocSystemError("landing requires a runner subcommand")
            if "--repo-root" not in delegated:
                delegated = [delegated[0], "--repo-root", str(system.root), *delegated[1:]]
            command = [
                sys.executable,
                str(system.root / str(system.manifest["landing_protocol"]["runner"])),
                *delegated,
            ]
            completed = subprocess.run(command, cwd=system.root, check=False)
            return completed.returncode

        if args.command == "new":
            created = system.new_document(
                args.kind,
                args.path,
                args.title,
                created_at=args.date,
                topics=args.topic,
                expires_at=args.expires_at,
                exit_action=args.exit_action,
                successor_path=args.successor_path,
                rationale=args.rationale,
            )
            for item in created:
                print(item)
            return 0

        if args.command == "exit-ephemeral":
            updated = system.exit_ephemeral(args.path, exited_at=args.exited_at)
            for item in updated:
                print(item)
            return 0

        if args.command == "register-local-evidence":
            updated = system.register_local_evidence(
                args.path,
                title=args.title,
                manifest_path=args.manifest_path,
                recovery_instructions=args.recovery_instructions,
                opened_at=args.opened_at,
                topics=args.topic,
                source_locator=args.source_locator,
            )
            for item in updated:
                print(item)
            return 0

        if args.command == "close-dossier":
            updated = system.close_dossier(
                args.dossier,
                outcome=args.outcome,
                closed_at=args.closed_at,
                review_id=args.review_id,
                claim_ids=args.claim_id,
                decision_ids=args.decision_id,
                successor_dossier_ids=args.successor_dossier_id,
                no_reusable_claim_reason=args.no_reusable_claim_reason,
            )
            for item in updated:
                print(item)
            return 0

        raise DocSystemError(f"unsupported command: {args.command}")
    except (DocSystemError, MaintenanceAuditError, OSError, UnicodeDecodeError) as exc:
        print(f"BLOCK: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
