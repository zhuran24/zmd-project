"""Focused regressions for event-driven document and knowledge intake."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools.build_knowledge_docs import _validate_dossier_portability  # noqa: E402
from devtools.docctl import (  # noqa: E402
    DocSystemError,
    DocumentSystem,
    _classify_policy_change,
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def _copy_file(root: Path, relpath: str) -> None:
    source = PROJECT_ROOT / relpath
    destination = root / relpath
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_framework_fixture(tmp_path: Path) -> Path:
    """Copy the framework and its small set of declared test dependencies."""

    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(PROJECT_ROOT / ".docsystem", root / ".docsystem")
    shutil.copy2(PROJECT_ROOT / "DOC_POLICY.json", root / "DOC_POLICY.json")
    shutil.copytree(
        PROJECT_ROOT / "data/repository_governance/document_system",
        root / "data/repository_governance/document_system",
    )
    shutil.copytree(
        PROJECT_ROOT / "docs/governance/document-system",
        root / "docs/governance/document-system",
    )
    # The real repository deliberately keeps this as an optional, untracked
    # workspace overlay.  A clean clone must therefore be able to build the
    # fixture without borrowing a machine-local root file.
    (root / "CLAUDE.md").write_text(
        "# Fixture workspace overlay\n",
        encoding="utf-8",
    )

    manifest = json.loads((PROJECT_ROOT / ".docsystem/manifest.json").read_text(encoding="utf-8"))
    gate = json.loads(
        (PROJECT_ROOT / str(manifest["governance_gate"]["source"])).read_text(encoding="utf-8")
    )
    declared_paths = {str(value) for value in manifest["governance_gate"].values()}
    for lane in gate["lanes"]:
        declared_paths.update(str(value) for value in lane["required_paths"])
    for relpath in sorted(declared_paths):
        if (PROJECT_ROOT / relpath).is_file():
            _copy_file(root, relpath)

    knowledge = root / "data/knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)
    for name in (
        "claims.jsonl",
        "decisions.jsonl",
        "dossiers.json",
        "backfill_reviews.jsonl",
        "backfill_triage.json",
        "terminology.json",
        "topics.json",
    ):
        shutil.copy2(PROJECT_ROOT / "data/knowledge" / name, knowledge / name)

    for relpath in (
        "data/artifact_boundaries.json",
        "data/repository_governance/artifact_boundaries.schema.json",
        "data/repository_governance/artifact_evidence_inputs.json",
        "data/repository_governance/artifact_evidence_inputs.schema.json",
    ):
        _copy_file(root, relpath)

    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def _copy_policy(root: Path, relpath: str) -> None:
    _copy_file(root, relpath)


def _policy(
    policy_id: str,
    *,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "zmd_doc_policy_v1",
        "policy_id": policy_id,
        "description": f"fixture policy {policy_id}",
        "defaults": defaults or {},
        "rules": [],
        "legacy_projection": {"rules": [], "out_of_scope_notes": []},
    }


def _commit(root: Path, message: str = "fixture baseline") -> None:
    subprocess.run(
        ["git", "add", "-A", "--", ".", ":(exclude)CLAUDE.md", ":(exclude)AGENTS.md"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Document Intake Test",
            "-c",
            "user.email=document-intake@example.invalid",
            "commit",
            "-q",
            "-m",
            message,
        ],
        cwd=root,
        check=True,
    )


def _append_decision(root: Path, record: dict[str, Any]) -> None:
    path = root / "data/knowledge/decisions.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def test_real_intake_registry_is_framework_owned_and_assigned_to_gate_profiles() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    descriptor = system.manifest["intake_protocol"]

    assert descriptor == {
        "source": "data/repository_governance/document_system/intake.json",
        "schema": "data/repository_governance/document_system/intake.schema.json",
    }
    assert system.manifest["system_version"] == "2.6.0"
    assert system.explain("DOC-EVENT-DOSSIER-CLOSED")["kind"] == "intake_event"
    assert system._check_intake_protocol() == []

    ephemeral = system.intake_payload["ephemeral_documents"]
    for relpath in (*descriptor.values(), *ephemeral.values(), "devtools/tests/test_document_intake.py"):
        resolution = system.resolve(str(relpath), "edit")
        assert resolution.contract["document_class"] == "framework_core"
        assert resolution.contract["mutation"] == "governed"
        assert "DOC-INV-018" in resolution.contract["invariant_refs"]
        assert "DOC-ADR-014" in resolution.contract["adr_refs"]

    profiles = system.governance_gate_profiles
    assert "document_intake" in profiles["changed"]["lane_ids"]
    assert "document_intake" in profiles["full"]["lane_ids"]
    assert "document_intake" not in profiles["weekly"]["lane_ids"]
    for profile_id in ("changed", "full", "weekly", "framework"):
        assert "document_intake_regressions" in profiles[profile_id]["lane_ids"]


def test_exact_path_policy_addition_is_coverage_not_framework_semantics(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    policy_path = root / "DOC_POLICY.json"
    baseline = _policy("fixture-root", defaults={"document_class": "unmanaged"})
    _write_json(policy_path, baseline)
    _commit(root)

    current = json.loads(policy_path.read_text(encoding="utf-8"))
    current["rules"].append(
        {
            "id": "new_living_page",
            "match": {"path": "docs/new_page.md"},
            "set": {"document_class": "living"},
            "rationale": "Fixture exact-path coverage.",
        }
    )
    _write_json(policy_path, current)

    assert _classify_policy_change(root, "HEAD", "DOC_POLICY.json") == "coverage_update"


def test_existing_policy_contract_edit_is_not_misclassified_as_coverage(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    policy_path = root / "DOC_POLICY.json"
    baseline = _policy("fixture-root", defaults={"document_class": "unmanaged"})
    baseline["rules"].append(
        {
            "id": "existing_page",
            "match": {"path": "docs/page.md"},
            "set": {"document_class": "living"},
            "rationale": "Fixture baseline contract.",
        }
    )
    _write_json(policy_path, baseline)
    _commit(root)

    current = json.loads(policy_path.read_text(encoding="utf-8"))
    current["rules"][0]["set"]["document_class"] = "historical_evidence"
    _write_json(policy_path, current)

    assert _classify_policy_change(root, "HEAD", "DOC_POLICY.json") == "contract_change"


def test_optional_workspace_overlay_is_not_a_git_delivery_change(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _commit(root)

    system = DocumentSystem(root)
    assert (root / "CLAUDE.md").is_file()
    assert "CLAUDE.md" not in system.tracked_paths()
    assert "CLAUDE.md" in system.visible_paths()
    assert "CLAUDE.md" not in system.projection_paths()
    assert "CLAUDE.md" not in system.changed_paths()


def test_declared_workspace_artifact_root_file_is_not_a_git_delivery_change(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    for relpath in (
        "data/artifact_boundaries.json",
        "data/external_artifacts.json",
        "data/repository_governance/artifact_boundaries.schema.json",
        "data/repository_governance/artifact_evidence_inputs.json",
        "data/repository_governance/artifact_evidence_inputs.schema.json",
    ):
        _copy_file(root, relpath)
    _commit(root)
    receipt = root / ".artifacts/canonical_merge_gate_20260807.DONE"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text("done\n", encoding="utf-8")

    system = DocumentSystem(root)
    assert ".artifacts/canonical_merge_gate_20260807.DONE" not in system.changed_paths()


def test_new_unclassified_markdown_is_blocked(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _commit(root)
    target = root / "unknown/new_note.md"
    target.parent.mkdir(parents=True)
    target.write_text("# New\n", encoding="utf-8")

    result = DocumentSystem(root).intake_changed()

    assert any(event.id == "DOC-EVENT-DOCUMENT-CREATED" for event in result.events)
    assert any("new Markdown has no effective document policy" in failure for failure in result.failures)


def test_stable_claim_identity_blocks_rewrite_and_deletion(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _commit(root)
    path = root / "data/knowledge/claims.jsonl"
    records = _read_jsonl(path)
    claim_id = str(records[0]["id"])

    records[0]["statement"] = str(records[0]["statement"]) + " changed"
    _write_jsonl(path, records)
    rewritten = DocumentSystem(root).intake_changed()
    assert any(claim_id in failure and "rewrites semantic identity fields" in failure for failure in rewritten.failures)

    subprocess.run(["git", "checkout", "--", "data/knowledge/claims.jsonl"], cwd=root, check=True)
    records = _read_jsonl(path)
    _write_jsonl(path, records[1:])
    deleted = DocumentSystem(root).intake_changed()
    assert any(f"stable claims ID was deleted: {claim_id}" in failure for failure in deleted.failures)


def test_declared_schema_migration_allows_only_exact_decision_register_upgrade(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    path = root / "data/knowledge/decisions.jsonl"
    current_records = _read_jsonl(path)
    decision_id = str(current_records[0]["id"])
    migrated_record = deepcopy(current_records[0])

    previous_record = deepcopy(migrated_record)
    previous_record["schema_version"] = "zmd_decision_v1"
    previous_record.pop("external_decision_id")
    previous_record.pop("non_authorizing")
    previous_record.pop("ruling_event_id")
    previous_record.pop("authority_source")
    for item in previous_record["evidence"]:
        item.pop("storage")
    previous_records = [previous_record, *deepcopy(current_records[1:])]
    _write_jsonl(path, previous_records)
    _commit(root)

    _write_jsonl(path, current_records)
    migrated = DocumentSystem(root).intake_changed()
    assert not any(
        decision_id in failure and "rewrites semantic identity fields" in failure
        for failure in migrated.failures
    )
    system = DocumentSystem(root)
    assert system._append_only_schema_migration_allowed(
        "data/knowledge/decisions.jsonl",
        "HEAD",
    ) is True

    rewritten_records = deepcopy(current_records)
    rewritten_records[0]["statement"] = str(rewritten_records[0]["statement"]) + " changed"
    _write_jsonl(path, rewritten_records)
    rewritten = DocumentSystem(root).intake_changed()
    assert any(
        decision_id in failure and "statement" in failure and "rewrites semantic identity fields" in failure
        for failure in rewritten.failures
    )
    rewritten_system = DocumentSystem(root)
    assert rewritten_system._append_only_schema_migration_allowed(
        "data/knowledge/decisions.jsonl",
        "HEAD",
    ) is False


def test_owner_authority_companion_is_default_off_warning_and_exact_match(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    _copy_file(root, "rules/canonical_rules.json")
    authority = root / "rules/canonical_rules.json"
    assert authority.is_file()
    canonical = json.loads(authority.read_text(encoding="utf-8"))
    canonical_version = str(canonical["metadata"]["version"])
    _commit(root)
    authority.write_text(authority.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    warned = DocumentSystem(root).intake_changed()
    assert not any("owner-governed authority changed without" in failure for failure in warned.failures)
    assert any("owner-governed authority changed without" in warning for warning in warned.warnings)
    assert "rules/canonical_rules.json" not in warned.authority_companion_matched_paths

    _append_decision(
        root,
        {
            "schema_version": "zmd_decision_v2",
            "id": "DECISION-INTAKE-FIXTURE-20260813",
            "title": "Fixture authority companion",
            "status": "current",
            "authority_effect": "project_semantics",
            "decided_at": "2026-08-13",
            "decided_by": "zhuran24",
            "statement": "Fixture records the exact canonical rule path change without authorizing it.",
            "scope": ["canonical-rules"],
            "consequences": ["The register exposes this exact fixture path change for review."],
            "does_not_imply": ["The register grants owner authority or authorizes any other path."],
            "supersedes": [],
            "evidence": [
                {
                    "path": "rules/canonical_rules.json",
                    "role": "authority_change",
                    "storage": "git_tracked",
                }
            ],
            "dossier_ids": [],
            "tags": ["fixture", "authority-change"],
            "non_authorizing": True,
            "external_decision_id": "owner-intake-fixture-20260813",
            "ruling_event_id": None,
            "authority_source": {
                "path": "rules/canonical_rules.json",
                "format": "json",
                "assertions": [
                    {
                        "operator": "equals",
                        "pointer": "/metadata/version",
                        "expected": canonical_version,
                    }
                ],
            },
        },
    )
    matched = DocumentSystem(root).intake_changed()
    assert "rules/canonical_rules.json" in matched.authority_companion_matched_paths
    assert not any("owner-governed authority changed without" in warning for warning in matched.warnings)
    assert not any("owner-governed authority changed without" in failure for failure in matched.failures)


def test_owner_authority_companion_switch_can_promote_warning_to_blocker(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    _copy_file(root, "rules/canonical_rules.json")
    intake_path = root / "data/repository_governance/document_system/intake.json"
    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    intake["authority_changes"]["companion_check"]["blocking"] = True
    _write_json(intake_path, intake)
    _commit(root)

    authority = root / "rules/canonical_rules.json"
    authority.write_text(authority.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    blocked = DocumentSystem(root).intake_changed()

    assert any("owner-governed authority changed without" in failure for failure in blocked.failures)
    assert not any("owner-governed authority changed without" in warning for warning in blocked.warnings)


def test_research_dossier_open_and_typed_close_are_atomic(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _copy_policy(root, "docs/DOC_POLICY.json")
    _copy_policy(root, "docs/research/DOC_POLICY.json")
    dossier_path = root / "data/knowledge/dossiers.json"
    dossier_payload = json.loads(dossier_path.read_text(encoding="utf-8"))
    dossier_id = "DOSSIER-AB16-ARMS-20260802-DC229C4539"
    existing = next(record for record in dossier_payload["records"] if record["id"] == dossier_id)
    existing["lifecycle"] = "active"
    existing["workflow"] = {"opened_at": "2026-08-01", "closure": None}
    _write_json(dossier_path, dossier_payload)
    _commit(root)

    system = DocumentSystem(root)
    outputs = system.new_document(
        "research-dossier",
        "docs/research/intake_fixture_20260813",
        "Intake fixture",
        created_at="2026-08-13",
        topics=("document-system",),
    )
    opened_payload = json.loads(dossier_path.read_text(encoding="utf-8"))
    opened = next(
        record for record in opened_payload["records"] if record["path"] == "docs/research/intake_fixture_20260813"
    )
    assert opened["lifecycle"] == "active"
    assert opened["workflow"] == {"opened_at": "2026-08-13", "closure": None}
    assert "data/knowledge/dossiers.json" in outputs
    opened_intake = DocumentSystem(root).intake_changed()
    assert any(event.id == "DOC-EVENT-DOSSIER-REGISTERED" for event in opened_intake.events)
    assert opened_intake.failures == ()

    # Return to the committed baseline, then close a workflow with a current
    # semantic review changed in the same transaction.
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=root, check=True, stdout=subprocess.DEVNULL)
    reviews_path = root / "data/knowledge/backfill_reviews.jsonl"
    reviews = _read_jsonl(reviews_path)
    review = next(record for record in reviews if record["id"] == "REVIEW-20260811-AB16-ARMS-BATCH3")
    review["summary"] = str(review["summary"]) + " Fixture closure review update."
    _write_jsonl(reviews_path, reviews)
    claim_id = str(review["claim_ids"][0])
    DocumentSystem(root).close_dossier(
        dossier_id,
        outcome="knowledge_promoted",
        closed_at="2026-08-13",
        review_id=str(review["id"]),
        claim_ids=(claim_id,),
    )
    closed_payload = json.loads(dossier_path.read_text(encoding="utf-8"))
    closed = next(record for record in closed_payload["records"] if record["id"] == dossier_id)
    assert closed["lifecycle"] == "historical"
    assert closed["workflow"]["closure"]["claim_ids"] == [claim_id]
    assert DocumentSystem(root).intake_changed().failures == ()


def test_ephemeral_creation_and_archive_exit_are_atomic(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _copy_policy(root, "docs/DOC_POLICY.json")
    _copy_policy(root, "docs/drafts/DOC_POLICY.json")
    _write_json(
        root / "docs/archive/DOC_POLICY.json",
        _policy(
            "docs.archive.fixture",
            defaults={
                "document_class": "historical_evidence",
                "authority_role": "evidence_only",
                "mutation": "direct",
                "context_level": "L0",
                "purpose": "Durable fixture archive.",
                "volatile_facts": "forbidden",
            },
        ),
    )
    _commit(root)

    created = DocumentSystem(root).new_document(
        "document",
        "docs/drafts/intake_note.md",
        "Temporary intake note",
        created_at="2026-08-13",
        expires_at="2099-08-13",
        exit_action="archive",
        successor_path="docs/archive/intake_note.md",
        rationale="Exercise typed ephemeral exit.",
    )
    assert "data/repository_governance/document_system/ephemeral_documents.json" in created
    assert DocumentSystem(root).intake_changed().failures == ()
    _commit(root, "ephemeral")

    DocumentSystem(root).exit_ephemeral("docs/drafts/intake_note.md", exited_at="2026-08-14")

    assert not (root / "docs/drafts/intake_note.md").exists()
    assert (root / "docs/archive/intake_note.md").is_file()
    registry = json.loads(
        (root / "data/repository_governance/document_system/ephemeral_documents.json").read_text(encoding="utf-8")
    )
    assert registry["records"] == []
    assert DocumentSystem(root).intake_changed().failures == ()


def test_local_evidence_requires_external_tracked_recovery_and_round_trips(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _copy_policy(root, ".artifacts/DOC_POLICY.json")
    _copy_file(root, ".artifacts/README.md")
    _commit(root)

    package = root / ".artifacts/local_intake_fixture"
    package.mkdir(parents=True)
    (package / "MANIFEST.json").write_text('{"fixture":true}\n', encoding="utf-8")
    (package / "RECOVER.md").write_text("# Local recovery\n", encoding="utf-8")
    system = DocumentSystem(root)
    with pytest.raises(DocSystemError, match="outside the local evidence package"):
        system.register_local_evidence(
            ".artifacts/local_intake_fixture",
            title="Local intake fixture",
            manifest_path=".artifacts/local_intake_fixture/MANIFEST.json",
            recovery_instructions=".artifacts/local_intake_fixture/RECOVER.md",
            opened_at="2026-08-13",
            topics=("document-system",),
        )

    untracked_recovery = root / "docs/local_intake_recovery.md"
    untracked_recovery.parent.mkdir(parents=True, exist_ok=True)
    untracked_recovery.write_text("# Recovery\n", encoding="utf-8")
    with pytest.raises(DocSystemError, match="must be Git-tracked"):
        system.register_local_evidence(
            ".artifacts/local_intake_fixture",
            title="Local intake fixture",
            manifest_path=".artifacts/local_intake_fixture/MANIFEST.json",
            recovery_instructions="docs/local_intake_recovery.md",
            opened_at="2026-08-13",
            topics=("document-system",),
        )

    untracked_recovery.unlink()
    _copy_file(root, "docs/AGENT_OPERATIONS.md")
    subprocess.run(["git", "add", "--", "docs/AGENT_OPERATIONS.md"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Document Intake Test",
            "-c",
            "user.email=document-intake@example.invalid",
            "commit",
            "-q",
            "-m",
            "track recovery instructions",
        ],
        cwd=root,
        check=True,
    )
    outputs = DocumentSystem(root).register_local_evidence(
        ".artifacts/local_intake_fixture",
        title="Local intake fixture",
        manifest_path=".artifacts/local_intake_fixture/MANIFEST.json",
        recovery_instructions="docs/AGENT_OPERATIONS.md",
        opened_at="2026-08-13",
        topics=("document-system",),
    )
    assert "data/knowledge/dossiers.json" in outputs
    payload = json.loads((root / "data/knowledge/dossiers.json").read_text(encoding="utf-8"))
    record = next(item for item in payload["records"] if item["path"] == ".artifacts/local_intake_fixture")
    assert record["tracked_state"] == "local_optional"
    assert record["portability"]["recovery_instructions"] == "docs/AGENT_OPERATIONS.md"
    _validate_dossier_portability(SimpleNamespace(root=root), record)
    assert DocumentSystem(root).intake_changed().failures == ()
