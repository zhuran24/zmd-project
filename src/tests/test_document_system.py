"""Focused contracts for the self-describing document framework."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools.docctl import (  # noqa: E402
    DocSystemError,
    DocumentSystem,
    _render_card,
)
from devtools.build_knowledge_docs import _path_belongs_to_dossier  # noqa: E402


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stage_paths(root: Path, *relpaths: str) -> None:
    """Expose fixture paths through the fixture repository's Git index."""

    if not relpaths:
        return
    subprocess.run(["git", "add", "--", *relpaths], cwd=root, check=True)


def _copy_framework_fixture(tmp_path: Path) -> Path:
    """Copy only the machine sources needed for policy resolution."""

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
    shutil.copy2(PROJECT_ROOT / "CLAUDE.md", root / "CLAUDE.md")
    manifest_payload = json.loads(
        (PROJECT_ROOT / ".docsystem/manifest.json").read_text(encoding="utf-8")
    )
    gate_payload = json.loads(
        (
            PROJECT_ROOT
            / str(manifest_payload["governance_gate"]["source"])
        ).read_text(encoding="utf-8")
    )
    gate_paths = {
        str(value) for value in manifest_payload["governance_gate"].values()
    }
    for lane in gate_payload["lanes"]:
        gate_paths.update(str(value) for value in lane["required_paths"])
    gate_paths.update(
        str(record["path"])
        for record in manifest_payload["test_timing_receipt"]["measured_inputs"]
    )
    for relpath in sorted(gate_paths):
        source = PROJECT_ROOT / relpath
        if not source.is_file():
            continue
        destination = root / relpath
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
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
    # Isolate Git visibility from the parent repository that owns pytest's
    # basetemp directory.  Policies are authoritative only when visible to the
    # target repository, not merely present on disk.
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "add", "-A", "--", ".", ":(exclude)CLAUDE.md", ":(exclude)AGENTS.md"],
        cwd=root,
        check=True,
    )
    return root


def _copy_entrypoint_fixture(tmp_path: Path) -> Path:
    """Copy the front-door graph, its targets and all effective local policies."""

    root = _copy_framework_fixture(tmp_path)
    registry = json.loads(
        (PROJECT_ROOT / "data/repository_governance/document_system/entrypoints.json").read_text(encoding="utf-8")
    )
    sections = json.loads(
        (PROJECT_ROOT / "data/repository_governance/document_system/sections.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((PROJECT_ROOT / ".docsystem/manifest.json").read_text(encoding="utf-8"))
    paths: set[str] = {
        str(manifest["section_projection"]["output"]),
        str(manifest["convergence_projection"]["output"]),
    }
    for record in registry["surfaces"]:
        paths.add(str(record["path"]))
        paths.update(str(value) for value in record["required_targets"])
    for record in registry["guarded_documents"]:
        paths.add(str(record["path"]))
        paths.update(str(value) for value in record["required_targets"])
    for record in registry["generated_redirects"]:
        paths.add(str(record["path"]))
        paths.update(str(target["path"]) for target in record["targets"])
        if record.get("archive_path") is not None:
            paths.add(str(record["archive_path"]))
    for record in sections["records"]:
        paths.add(str(record["entry_path"]))
        paths.update(str(value) for value in record["required_targets"])

    for policy_relpath in DocumentSystem(PROJECT_ROOT).policy_paths():
        policy_path = Path(policy_relpath)
        source = PROJECT_ROOT / policy_path
        destination = root / policy_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    for configured_path in sorted(paths):
        source = PROJECT_ROOT / configured_path
        if not source.is_file():
            continue
        destination = root / configured_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    subprocess.run(
        ["git", "add", "-A", "--", ".", ":(exclude)CLAUDE.md", ":(exclude)AGENTS.md"],
        cwd=root,
        check=True,
    )
    return root


def _init_git_repository(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "add", "-A", "--", ".", ":(exclude)CLAUDE.md", ":(exclude)AGENTS.md"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Document System Test",
            "-c",
            "user.email=docsystem-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture baseline",
        ],
        cwd=root,
        check=True,
    )


def _append_decision(root: Path, record: dict[str, Any]) -> None:
    path = root / "data/knowledge/decisions.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _policy(
    policy_id: str,
    *,
    defaults: dict[str, Any] | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "zmd_doc_policy_v1",
        "policy_id": policy_id,
        "description": f"fixture policy {policy_id}",
        "defaults": defaults or {},
        "rules": rules or [],
        "legacy_projection": {"rules": [], "out_of_scope_notes": []},
    }


def test_real_repository_document_system_is_self_consistent() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    failures = system.doctor()
    tracked_overlays = {
        path for path in ("CLAUDE.md", "AGENTS.md") if path in system.tracked_paths()
    }
    if tracked_overlays:
        assert set(failures) == {
            (
                f"workspace overlay is tracked in this checkout: {path}; "
                "real-repository landing must preserve it as optional workspace_untracked"
            )
            for path in tracked_overlays
        }
    else:
        assert failures == ()


def test_governance_gate_is_manifest_owned_and_framework_core() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    descriptor = system.manifest["governance_gate"]

    assert system.guide()["governance_default_profile"] == "changed"
    assert descriptor == {
        "source": "data/repository_governance/document_system/governance_gate.json",
        "schema": "data/repository_governance/document_system/governance_gate.schema.json",
        "runner": "devtools/document_governance_gate.py",
        "ci_workflow": ".github/workflows/document-governance.yml",
    }
    for relpath in (*descriptor.values(), "devtools/tests/test_document_governance_gate.py"):
        resolution = system.resolve(str(relpath), "edit")
        assert resolution.contract["document_class"] == "framework_core"
        assert resolution.contract["mutation"] == "governed"
        assert resolution.contract["context_level"] == "L3"
        assert "DOC-INV-017" in resolution.contract["invariant_refs"]
        assert "DOC-ADR-013" in resolution.contract["adr_refs"]
        assert "docsystem.gate" in resolution.contract["after_change"]

    changed = system.explain("changed")
    assert changed["kind"] == "governance_profile"
    assert "code_assets_current" in changed["lane_ids"]
    assert "code_assets_history" not in changed["lane_ids"]
    assert system._check_governance_gate() == []


def test_steady_state_handoff_is_manifest_owned_reachable_and_non_authorizing() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    relpath = "docs/governance/document-system/STEADY_STATE.md"

    assert system.manifest["steady_state_guide"] == relpath
    assert system.guide()["steady_state"] == relpath
    resolution = system.resolve(relpath, "edit")
    assert resolution.contract["document_class"] == "framework_core"
    assert resolution.contract["mutation"] == "governed"
    assert "DOC-INV-023" in resolution.contract["invariant_refs"]
    assert "DOC-ADR-020" in resolution.contract["adr_refs"]

    text = (PROJECT_ROOT / relpath).read_text(encoding="utf-8")
    for needle in (
        "devtools/docctl.py context",
        "devtools/docctl.py intake --changed",
        "devtools/docctl.py audit --profile weekly",
        "devtools/docctl.py gate --profile changed",
        "devtools/document_patch_landing.py",
        "scripts/preflight_gate.py",
        "DOC-INV-023",
        "DOC-ADR-020",
    ):
        assert needle in text
    assert "不再因为普通积压自动产生新的 Phase 或 Batch" in text
    assert system._check_guides() == []


def test_event_intake_is_manifest_owned_and_framework_core() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    descriptor = system.manifest["intake_protocol"]

    assert descriptor == {
        "source": "data/repository_governance/document_system/intake.json",
        "schema": "data/repository_governance/document_system/intake.schema.json",
    }
    assert system.guide()["intake_protocol"] == descriptor["source"]
    assert system.guide()["intake_schema"] == descriptor["schema"]
    assert system.explain("DOC-EVENT-DOSSIER-CLOSED")["kind"] == "intake_event"
    ephemeral = system.intake_payload["ephemeral_documents"]
    for relpath in (*descriptor.values(), *ephemeral.values()):
        resolution = system.resolve(str(relpath), "edit")
        assert resolution.contract["document_class"] == "framework_core"
        assert resolution.contract["mutation"] == "governed"
        assert "DOC-INV-018" in resolution.contract["invariant_refs"]
        assert "DOC-ADR-014" in resolution.contract["adr_refs"]
        assert "docsystem.intake" in resolution.contract["after_change"]
    assert system._check_intake_protocol() == []


def test_governance_ci_delegates_to_the_shared_runner() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/document-governance.yml").read_text(
        encoding="utf-8"
    )
    assert "devtools/document_governance_gate.py" in workflow
    assert "fetch-depth: 0" in workflow
    assert "profile=changed" in workflow
    assert "profile=weekly" in workflow
    for duplicated in (
        "devtools/docctl.py doctor",
        "devtools/check_knowledge_docs.py",
        "devtools/check_repository_code_assets.py check-current",
    ):
        assert duplicated not in workflow


def test_phase3_section_framework_decision_is_registered() -> None:
    manifest = json.loads((PROJECT_ROOT / ".docsystem/manifest.json").read_text(encoding="utf-8"))
    invariants = json.loads(
        (PROJECT_ROOT / "data/repository_governance/document_system/invariants.json").read_text(encoding="utf-8")
    )

    assert manifest["system_version"] == "2.6.0"
    assert invariants["system_version"] == "2.6.0"
    expected_adrs = {
        "DOC-ADR-006": ("docs/governance/document-system/ADR/006-selection-separation-and-consumption-profile.md"),
        "DOC-ADR-007": ("docs/governance/document-system/ADR/007-validity-events-and-explicit-supersession.md"),
        "DOC-ADR-008": ("docs/governance/document-system/ADR/008-semantic-review-and-inventory-triage.md"),
        "DOC-ADR-009": ("docs/governance/document-system/ADR/009-explicit-current-guidance-surface.md"),
        "DOC-ADR-010": ("docs/governance/document-system/ADR/010-bounded-entrypoints-and-on-demand-agent-guide.md"),
        "DOC-ADR-011": ("docs/governance/document-system/ADR/011-explicit-sections-and-retired-local-indexes.md"),
        "DOC-ADR-012": ("docs/governance/document-system/ADR/012-current-graph-convergence-audit.md"),
        "DOC-ADR-013": ("docs/governance/document-system/ADR/013-non-mutating-governance-gate.md"),
        "DOC-ADR-014": ("docs/governance/document-system/ADR/014-event-driven-document-intake.md"),
        "DOC-ADR-015": ("docs/governance/document-system/ADR/015-periodic-semantic-maintenance-audit.md"),
        "DOC-ADR-016": ("docs/governance/document-system/ADR/016-real-repository-topology-and-workspace-overlays.md"),
        "DOC-ADR-017": ("docs/governance/document-system/ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md"),
        "DOC-ADR-018": ("docs/governance/document-system/ADR/018-nondestructive-real-repository-landing.md"),
        "DOC-ADR-019": ("docs/governance/document-system/ADR/019-bounded-governance-concurrency-and-slow-test-evidence.md"),
        "DOC-ADR-020": ("docs/governance/document-system/ADR/020-steady-state-transition-and-maintenance-handoff.md"),
    }
    for adr_id, relpath in expected_adrs.items():
        assert manifest["adrs"][adr_id] == relpath
        assert (PROJECT_ROOT / relpath).is_file()

    invariant_ids = {str(record["id"]) for record in invariants["records"]}
    assert {
        "DOC-INV-010",
        "DOC-INV-011",
        "DOC-INV-012",
        "DOC-INV-013",
        "DOC-INV-014",
        "DOC-INV-015",
        "DOC-INV-016",
        "DOC-INV-017",
        "DOC-INV-018",
        "DOC-INV-019",
        "DOC-INV-020",
        "DOC-INV-021",
        "DOC-INV-022",
        "DOC-INV-023",
    } <= invariant_ids



def test_real_repository_landing_protocol_is_manifest_owned_and_fail_closed() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    descriptor = system.manifest["landing_protocol"]

    assert descriptor == {
        "source": "data/repository_governance/document_system/landing.json",
        "schema": "data/repository_governance/document_system/landing.schema.json",
        "ack_schema": "data/repository_governance/document_system/landing_ack.schema.json",
        "runner": "devtools/document_patch_landing.py",
        "guide": "docs/governance/document-system/REAL_REPOSITORY_LANDING.md",
    }
    assert system.landing_payload["system_version"] == system.manifest["system_version"]
    assert system._check_landing_protocol() == []
    assert {record["source_path"] for record in system.landing_payload["known_migrations"]} == {
        "CLAUDE.md",
        "docs/项目说明/00_master_roadmap.md",
        "docs/项目说明/27_status_dashboard.md",
    }
    assert set(system.landing_payload["forbidden_operations"]) >= {
        "git reset --hard",
        "git clean",
        "git add -A",
        "git commit",
        "git commit --amend",
    }
    for relpath in descriptor.values():
        resolution = system.resolve(relpath, "edit")
        assert resolution.contract["document_class"] == "framework_core"
        assert resolution.contract["mutation"] == "governed"
        assert "DOC-INV-022" in resolution.contract["invariant_refs"]
        assert "DOC-ADR-018" in resolution.contract["adr_refs"]
    for profile_id in ("changed", "full", "weekly", "framework"):
        assert "document_landing_regressions" in system.governance_gate_profiles[profile_id]["lane_ids"]

    receipt = system.test_timing_receipt
    assert receipt["schema_version"] == "zmd_document_test_timing_receipt_v1"
    assert receipt["threshold_call_seconds"] == 8.0
    assert receipt["execution_mode"] == "serial_no_concurrent_pytest"
    assert receipt["nodes_at_or_above_threshold"] == []
    assert receipt["slow_registry_action"] == "no_new_entries_required"
    assert system._check_test_timing_receipt() == []


def test_timing_receipt_fails_closed_when_a_measured_input_drifts(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    measured = root / "src/tests/test_knowledge_docs.py"
    measured.write_text(measured.read_text(encoding="utf-8") + "\n# timing drift\n", encoding="utf-8")

    failures = DocumentSystem(root)._check_test_timing_receipt()

    assert any("test timing receipt input drifted: src/tests/test_knowledge_docs.py" in value for value in failures)


def test_maintenance_audit_regression_clock_covers_latest_active_dossier() -> None:
    helper_text = (PROJECT_ROOT / "devtools/tests/test_document_maintenance_audit.py").read_text(encoding="utf-8")
    marker = 'as_of: str = "'
    assert helper_text.count(marker) == 1
    regression_as_of = helper_text.split(marker, 1)[1].split('"', 1)[0]

    dossier_payload = json.loads((PROJECT_ROOT / "data/knowledge/dossiers.json").read_text(encoding="utf-8"))
    ledger_reviewed_at = str(dossier_payload["ledger_reviewed_at"])
    assert regression_as_of == ledger_reviewed_at
    active_opened_dates: list[str] = []
    for record in dossier_payload["records"]:
        if record.get("lifecycle") != "active":
            continue
        workflow = record.get("workflow")
        opened_at = workflow.get("opened_at") if isinstance(workflow, dict) else None
        candidate = opened_at or record.get("date")
        if isinstance(candidate, str) and candidate:
            active_opened_dates.append(candidate)

    assert active_opened_dates
    latest_active_opened_at = max(active_opened_dates)
    assert regression_as_of == latest_active_opened_at, (
        f"maintenance regression clock {regression_as_of} does not equal "
        f"latest active dossier {latest_active_opened_at}"
    )


def test_entrypoint_registry_is_the_structural_source_for_frontdoor_contracts() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    registry = system.entrypoints_payload
    current_state = json.loads((PROJECT_ROOT / "data/knowledge/current_state.json").read_text(encoding="utf-8"))

    assert registry["schema_version"] == "zmd_document_entrypoints_v1"
    assert registry["system_version"] == "2.6.0"
    assert len(registry["surfaces"]) == 9
    assert len(registry["guarded_documents"]) == 12
    assert len(registry["generated_redirects"]) == 14
    assert "entrypoint_contracts" not in system.manifest
    assert system.manifest["entrypoint_registry"]["source"] == (
        "data/repository_governance/document_system/entrypoints.json"
    )
    operations = next(record for record in registry["surfaces"] if record["id"] == "agent_operations")
    assert operations["path"] == "docs/AGENT_OPERATIONS.md"
    assert "scripts/preflight_gate.py" in operations["required_targets"]
    assert "agent_bootstrap" not in {record["id"] for record in registry["surfaces"]}
    assert "volatile_copy_guards" not in current_state
    assert "compatibility_entrypoints" not in current_state
    assert system._check_entrypoints() == []


def test_section_registry_is_the_structural_source_for_local_frontdoors() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    registry = system.sections_payload

    assert registry["schema_version"] == "zmd_document_sections_v1"
    assert registry["system_version"] == "2.6.0"
    assert len(registry["records"]) == 14
    assert system.manifest["section_registry"]["source"] == ("data/repository_governance/document_system/sections.json")
    assert system.manifest["section_registry"]["schema"] == (
        "data/repository_governance/document_system/sections.schema.json"
    )
    assert system.manifest["section_projection"]["output"] == "docs/SECTION_INDEX.md"
    assert {record["id"] for record in registry["records"]} >= {
        "repository-navigation",
        "knowledge",
        "specifications",
        "operations",
        "research-archive",
        "history-archive",
        "formal-verification",
        "compatibility-adapters",
    }
    certification = next(record for record in registry["records"] if record["id"] == "certification")
    assert certification["entry_path"] == "docs/CERTIFICATION.md"
    assert certification["entry_kind"] == "manual"
    assert "PROJECT_LOCK.md" in certification["required_targets"]
    assert system._check_sections() == []


def test_section_context_exposes_local_entrypoint_without_loading_global_map() -> None:
    system = DocumentSystem(PROJECT_ROOT)

    spec = system.resolve("specs/11_pipeline_orchestration.md", "read")
    assert [record["id"] for record in spec.sections] == ["specifications"]
    assert spec.sections[0]["entry_path"] == "specs/README.md"
    assert "SECTIONS:" in _render_card(spec)
    assert "specifications -> specs/README.md" in _render_card(spec)

    compatibility = system.resolve("docs/compatibility_matrix.md", "read")
    assert {record["id"] for record in compatibility.sections} == {"compatibility-adapters"}
    assert compatibility.sections[0]["entry_path"] == "docs/compatibility_matrix.md"


def test_generated_section_projection_is_exact_write_through() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    resolution = system.resolve("docs/SECTION_INDEX.md", "edit")

    assert resolution.allowed is False
    assert resolution.contract["document_class"] == "generated_projection"
    assert resolution.contract["mutation"] == "generator_only"
    assert resolution.contract["generator_action"] == "docsystem.render_sections"
    assert "data/repository_governance/document_system/sections.json" in resolution.contract["source_paths"]
    assert (PROJECT_ROOT / "docs/SECTION_INDEX.md").read_text(encoding="utf-8") == system.render_section_projection()


def test_generated_convergence_projection_is_exact_write_through() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    resolution = system.resolve("docs/CONVERGENCE_REPORT.md", "edit")

    assert resolution.allowed is False
    assert resolution.contract["document_class"] == "generated_projection"
    assert resolution.contract["mutation"] == "generator_only"
    assert resolution.contract["generator_action"] == "docsystem.render_convergence"
    assert "data/repository_governance/document_system/sections.json" in resolution.contract["source_paths"]
    assert "**/DOC_POLICY.json" in resolution.contract["source_paths"]
    assert "**/*.md" in resolution.contract["source_paths"]
    assert "DOC-INV-015" in resolution.contract["invariant_refs"]
    assert "DOC-INV-016" in resolution.contract["invariant_refs"]
    assert (PROJECT_ROOT / "docs/CONVERGENCE_REPORT.md").read_text(encoding="utf-8") == (
        system.render_convergence_projection()
    )
    assert system.convergence_audit()["failures"] == ()
    assert system._check_convergence_projection() == []


def test_artifact_boundary_projection_and_frozen_consumer_are_self_describing() -> None:
    system = DocumentSystem(PROJECT_ROOT)

    projection = system.resolve("data/artifact_boundaries.json", "edit")
    assert projection.allowed is False
    assert projection.contract["document_class"] == "generated_projection"
    assert projection.contract["mutation"] == "generator_only"
    assert projection.contract["generator_action"] == "artifact_evidence.render"
    assert "data/knowledge/dossiers.json" in projection.contract["source_paths"]
    assert (
        "data/repository_governance/artifact_evidence_inputs.json"
        in projection.contract["source_paths"]
    )

    helper = system.resolve("devtools/artifact_evidence.py", "edit")
    assert helper.allowed is True
    assert helper.contract["document_class"] == "governance_control"
    assert helper.contract["context_level"] == "L2"
    assert "artifact_evidence.check" in helper.contract["after_change"]

    frozen = system.resolve("scripts/check_artifact_boundaries.py", "edit")
    assert frozen.allowed is False
    assert frozen.contract["document_class"] == "locked_authority"
    assert frozen.contract["mutation"] == "owner_only"
    assert "PROJECT_LOCK.md" in frozen.contract["required_reads"]

    assert system.actions["artifact_evidence.render"]["command"].endswith(
        "devtools/artifact_evidence.py render --write"
    )
    assert system.actions["artifact_evidence.check"]["command"].endswith(
        "devtools/artifact_evidence.py check"
    )


def _add_fixture_current_document(
    root: Path,
    *,
    relpath: str,
    rule_id: str,
    purpose: str,
    content: str,
    volatile_facts: str = "forbidden",
) -> None:
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    policy_path = root / "docs/DOC_POLICY.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    local_path = Path(relpath).relative_to("docs").as_posix()
    policy["rules"].append(
        {
            "id": rule_id,
            "match": {"path": local_path},
            "set": {
                "document_class": "living",
                "authority_role": "current_guidance",
                "mutation": "direct",
                "purpose": purpose,
                "volatile_facts": volatile_facts,
                "section_refs": ["repository-navigation"],
            },
            "rationale": "fixture",
        }
    )
    _write_json(policy_path, policy)
    _stage_paths(root, relpath)


def test_convergence_audit_rejects_locally_unreachable_current_document(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    _add_fixture_current_document(
        root,
        relpath="docs/unlinked_current.md",
        rule_id="fixture_unlinked_current",
        purpose="fixture unlinked current responsibility",
        content="# Unlinked current\n",
    )

    failures = DocumentSystem(root).convergence_audit()["failures"]

    assert any(
        "section repository-navigation current member is unreachable from README.md: docs/unlinked_current.md"
        in failure
        for failure in failures
    )


def test_convergence_audit_rejects_duplicate_mutable_responsibilities(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    for suffix in ("a", "b"):
        _add_fixture_current_document(
            root,
            relpath=f"docs/duplicate_{suffix}.md",
            rule_id=f"fixture_duplicate_{suffix}",
            purpose="one duplicated fixture responsibility",
            content=f"# Duplicate {suffix}\n",
        )

    failures = DocumentSystem(root).convergence_audit()["failures"]

    assert any(
        "current mutable documents share one responsibility: docs/duplicate_a.md, docs/duplicate_b.md"
        in failure
        for failure in failures
    )


def test_convergence_audit_rejects_volatile_copy_outside_guard_registry(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    _add_fixture_current_document(
        root,
        relpath="docs/volatile_current.md",
        rule_id="fixture_volatile_current",
        purpose="fixture volatile-copy responsibility",
        content="# Volatile\n\nowner-p1-2-reclose-20990101\n",
        volatile_facts="reference_only",
    )

    failures = DocumentSystem(root).convergence_audit()["failures"]

    assert any(
        "current document docs/volatile_current.md copies volatile state" in failure
        for failure in failures
    )


def test_convergence_audit_rejects_current_links_to_retired_redirects(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    front_door = root / "README.md"
    front_door.write_text(
        front_door.read_text(encoding="utf-8") + "\n[legacy status](FILE_STATUS.md)\n",
        encoding="utf-8",
    )

    failures = DocumentSystem(root).convergence_audit()["failures"]

    assert any(
        "current document README.md routes through retired compatibility entrypoint FILE_STATUS.md"
        in failure
        for failure in failures
    )


def test_current_markdown_without_section_fails_closed(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    target = root / "docs/orphan_current.md"
    target.write_text("# Orphan current document\n", encoding="utf-8")
    policy_path = root / "docs/DOC_POLICY.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["rules"].append(
        {
            "id": "fixture_orphan_current",
            "match": {"path": "orphan_current.md"},
            "set": {
                "document_class": "living",
                "authority_role": "current_guidance",
                "mutation": "direct",
                "purpose": "fixture current document without a section",
                "section_refs": [],
            },
            "rationale": "fixture",
        }
    )
    _write_json(policy_path, policy)
    _stage_paths(root, "docs/orphan_current.md")

    failures = DocumentSystem(root)._check_sections()

    assert "current document has no explicit section: docs/orphan_current.md" in failures


def test_section_entry_required_link_fails_closed(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    specs = root / "specs/README.md"
    specs.write_text("# Specs\n\nThis intentionally drops all required links.\n", encoding="utf-8")

    failures = DocumentSystem(root)._check_sections()

    assert any("section entry specs/README.md does not link required target" in failure for failure in failures)


def test_retired_local_indexes_preserve_payloads_and_have_current_successors() -> None:
    expected_archives = {
        "docs/history/navigation/research_phase3c_agent_transcript_index_20260507_08.md": (
            "1b5368beb04b537a4b0cc732a5b713582ec9b721d1b4c48757603a5d1252b793"
        ),
        "docs/history/navigation/docs_specs_index_pre_phase3_batch3_20260812.md": (
            "beca42b269521ed271cc233a342733f3d726883c43ab31ab0b542eb7fcb8c049"
        ),
        "docs/history/navigation/subjects_doc_tree_architecture_pre_phase3_batch3_20260812.md": (
            "a4dd7b6dded0269525bf6a75c73f940205e2418fe79ecdea5554c99ec2a45b4f"
        ),
        "docs/history/navigation/subjects_doc_tree_completeness_pre_phase3_batch3_20260812.md": (
            "f1cc3ac8d14224ee7022a2d97e5fc1dc1d2afc0f6d7e1041fd831794208ecef2"
        ),
        "docs/history/navigation/subjects_project_knowledge_tree_pre_phase3_batch3_20260812.md": (
            "3256dba8de47fdab15343d7ecf8a0eeab46a0274a15abea9ba068869a69ce399"
        ),
        "docs/history/formal/formal_readme_pre_phase3_batch3_20260812.md": (
            "c5e6593a79ea4dd32dc3951fa5a59bc91e4bcd7ba269131e4746f0eaa950f6ee"
        ),
        "docs/history/convergence/exact_campaign_operations_pre_phase3_batch4_20260812.md": (
            "69b09b693352ad1df59fd80db83e33bb70c7b8ee559abb00b43f940c02ccb82a"
        ),
        "docs/history/convergence/parallel_configuration_pre_phase3_batch4_20260812.md": (
            "c76d46045ec960619fc020bbd84b817e192fa8eac3295342788632ab795d55ed"
        ),
        "docs/history/convergence/scripts_readme_pre_phase3_batch4_20260812.md": (
            "c6b9ad852a155e5d765ca70a2105a9e60a631d25d199a7c253aaf4004000101b"
        ),
        "docs/history/convergence/workflow_testing_pre_phase3_batch4_20260812.md": (
            "d3a68ab66e104d2f03f7802068d52910e4cc1acd7bdb615d936f4dba286fb38f"
        ),
        "docs/history/convergence/spec06_candidate_placement_pre_phase3_batch4_20260812.md": (
            "deafab837d4d261701b9fa17e5b010fa7c81e26462021cd962bfe4d6a9f51e66"
        ),
        "docs/history/convergence/23_rule_cut_evolution_protocol_pre_phase3_batch4_20260812.md": (
            "6b04f678a26744348da67e7c3433683f3d9e12c9e65f9f6c939eb1b2aab1a176"
        ),
        "docs/history/convergence/24_repository_asset_governance_pre_phase3_batch4_20260812.md": (
            "bc7e35d91f6a92f5309d9ce3d701d6e4acda62085956d6daecc1f0eae058dbfa"
        ),
    }
    for relpath, expected_sha256 in expected_archives.items():
        payload = (PROJECT_ROOT / relpath).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected_sha256

    system = DocumentSystem(PROJECT_ROOT)
    for relpath in (
        "docs/research/INDEX.md",
        "docs/specs_index.md",
        "docs/subjects/doc_tree_architecture.md",
        "docs/subjects/doc_tree_completeness.md",
        "docs/subjects/project_knowledge_tree.md",
    ):
        resolution = system.resolve(relpath, "edit")
        assert resolution.allowed is False
        assert resolution.contract["document_class"] == "generated_projection"
        assert resolution.contract["mutation"] == "generator_only"
        assert resolution.contract["generator_action"] == "docsystem.render_entrypoints"

    formal_current = system.resolve("formal/README.md", "edit")
    formal_archive = system.resolve(
        "docs/history/formal/formal_readme_pre_phase3_batch3_20260812.md",
        "edit",
    )
    assert formal_current.contract["document_class"] == "living"
    assert formal_current.contract["mutation"] == "governed"
    assert formal_archive.allowed is False
    assert formal_archive.contract["document_class"] == "historical_evidence"
    assert formal_archive.contract["mutation"] == "immutable"


def test_unregistered_research_root_file_still_requires_dossier_registration(
    tmp_path: Path,
) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    _init_git_repository(root)
    orphan = root / "docs/research/unregistered_payload.md"
    orphan.write_text("# Unregistered payload\n", encoding="utf-8")

    result = DocumentSystem(root).check_changed()

    assert any(
        "docs/research/unregistered_payload.md: research/evidence package is not registered as a dossier" in value
        for value in result.failures
    )


def test_entrypoint_context_exposes_role_budget_and_write_through() -> None:
    system = DocumentSystem(PROJECT_ROOT)

    overlay = system.resolve("CLAUDE.md", "read")
    assert overlay.entrypoint is None
    assert overlay.contract["document_class"] == "living"
    assert "docs/AGENT_OPERATIONS.md" in overlay.contract["required_reads"]
    assert "CLAUDE.md" not in system.projection_paths()

    operations = system.resolve("docs/AGENT_OPERATIONS.md", "read")
    assert operations.entrypoint is not None
    assert operations.entrypoint["kind"] == "surface"
    assert operations.entrypoint["id"] == "agent_operations"
    operations_card = _render_card(operations)
    assert "ENTRYPOINT: surface agent_operations mode=manual" in operations_card
    assert "ATTENTION BUDGET: 240 lines / 42000 bytes" in operations_card

    guarded = system.resolve("NAV_MAP.md", "read")
    assert guarded.entrypoint is not None
    assert guarded.entrypoint["kind"] == "guard"
    assert guarded.entrypoint["id"] == "code_map"

    redirect = system.resolve("FILE_STATUS.md", "edit")
    assert redirect.allowed is False
    assert redirect.entrypoint is not None
    assert redirect.entrypoint["kind"] == "redirect"
    assert redirect.contract["generator_action"] == "docsystem.render_entrypoints"
    assert "WRITE THROUGH: docsystem.render_entrypoints" in _render_card(redirect)


def test_generated_compatibility_entrypoints_are_exact_write_through_projections() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    expected = system.render_entrypoint_redirects()

    assert set(expected) == {str(record["path"]) for record in system.entrypoint_redirects.values()}
    for relpath, content in expected.items():
        assert (PROJECT_ROOT / relpath).read_text(encoding="utf-8") == content
        resolution = system.resolve(relpath, "edit")
        assert resolution.allowed is False
        assert resolution.contract["document_class"] == "generated_projection"
        assert resolution.contract["mutation"] == "generator_only"
        assert resolution.contract["generator_action"] == "docsystem.render_entrypoints"
        assert "data/repository_governance/document_system/entrypoints.json" in resolution.contract["source_paths"]


def test_manual_entrypoint_attention_budget_fails_closed(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    operations = root / "docs/AGENT_OPERATIONS.md"
    operations.write_text(
        operations.read_text(encoding="utf-8") + "\n" + "overflow\n" * 260,
        encoding="utf-8",
    )

    failures = DocumentSystem(root)._check_entrypoints()

    assert any(
        "manual entrypoint attention budget exceeded: docs/AGENT_OPERATIONS.md" in failure
        for failure in failures
    )


def test_generated_compatibility_entrypoint_drift_fails_closed(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    redirect = root / "FILE_STATUS.md"
    redirect.write_text(
        redirect.read_text(encoding="utf-8") + "\nmanual drift\n",
        encoding="utf-8",
    )

    failures = DocumentSystem(root)._check_entrypoints()

    assert any("compatibility redirect is stale: FILE_STATUS.md" in failure for failure in failures)


def test_guarded_document_rejects_copied_volatile_state(tmp_path: Path) -> None:
    root = _copy_entrypoint_fixture(tmp_path)
    code_map = root / "NAV_MAP.md"
    code_map.write_text(
        code_map.read_text(encoding="utf-8") + "\nowner-p1-2-reclose-20990101\n",
        encoding="utf-8",
    )

    failures = DocumentSystem(root)._check_entrypoints()

    assert any("guarded document NAV_MAP.md copies volatile state" in failure for failure in failures)


def test_local_optional_dossier_review_uses_syntactic_containment_before_existence(tmp_path: Path) -> None:
    missing_root = tmp_path / ".artifacts/not-restored-fixture"

    assert _path_belongs_to_dossier(
        tmp_path,
        ".artifacts/not-restored-fixture/REPORT.md",
        ".artifacts/not-restored-fixture",
    )
    assert not _path_belongs_to_dossier(
        tmp_path,
        ".artifacts/other-package/REPORT.md",
        ".artifacts/not-restored-fixture",
    )
    assert not missing_root.exists()


def test_generated_current_projection_is_write_through_only() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve("docs/CURRENT.md", "edit")

    assert resolution.allowed is False
    assert resolution.contract["document_class"] == "generated_projection"
    assert resolution.contract["mutation"] == "generator_only"
    assert resolution.contract["generator_action"] == "knowledge.build"
    assert "data/knowledge/current_state.json" in resolution.contract["source_paths"]
    assert "DOC-INV-001" in resolution.contract["invariant_refs"]
    assert resolution.action_commands[0]["id"] == "knowledge.build"
    assert "build_knowledge_docs.py --write" in resolution.action_commands[0]["command"]


def test_generated_reasoning_projection_is_write_through_only() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "docs/REASONING_LEDGER.md",
        "edit",
    )

    assert resolution.allowed is False
    assert resolution.contract["document_class"] == "generated_projection"
    assert resolution.contract["mutation"] == "generator_only"
    assert resolution.contract["generator_action"] == "knowledge.build"
    assert "data/knowledge/backfill_reviews.jsonl" in resolution.contract["source_paths"]
    assert "DOC-ADR-004" in resolution.contract["adr_refs"]
    assert "DOC-ADR-005" in resolution.contract["adr_refs"]
    assert "DOC-ADR-006" in resolution.contract["adr_refs"]


def test_generated_knowledge_projections_are_write_through_only() -> None:
    expected = {
        "docs/BACKFILL_LEDGER.md": (
            "data/knowledge/backfill_triage.json",
            "DOC-INV-011",
        ),
        "docs/TOPIC_INDEX.md": ("data/knowledge/topics.json", "DOC-ADR-008"),
        "docs/TERMINOLOGY.md": ("data/knowledge/terminology.json", "DOC-ADR-008"),
        "docs/OPEN_QUESTIONS.md": ("data/knowledge/topics.json", "DOC-INV-012"),
    }

    for path, (source, marker) in expected.items():
        resolution = DocumentSystem(PROJECT_ROOT).resolve(path, "edit")
        assert resolution.allowed is False
        assert resolution.contract["document_class"] == "generated_projection"
        assert resolution.contract["mutation"] == "generator_only"
        assert resolution.contract["generator_action"] == "knowledge.build"
        assert source in resolution.contract["source_paths"]
        assert marker in resolution.contract["invariant_refs"] or marker in resolution.contract["adr_refs"]


def test_global_knowledge_digest_dependencies_are_declared_write_through_sources() -> None:
    for path in (
        "docs/CURRENT.md",
        "docs/OPEN_QUESTIONS.md",
        "docs/TERMINOLOGY.md",
    ):
        resolution = DocumentSystem(PROJECT_ROOT).resolve(path, "edit")
        assert "data/knowledge/dossiers.json" in resolution.contract["source_paths"]
        assert "devtools/build_knowledge_docs.py" in resolution.contract["source_paths"]


def test_triaged_dossier_card_never_claims_semantic_review() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "docs/research/b1_pose_bool_phase0_20260517/README.md",
        "read",
    )

    assert resolution.reviews == ()
    assert resolution.triage is not None
    assert resolution.triage["id"] == "TRIAGE-CUT-SOLVER-TRACKED-LONGTAIL"
    card = _render_card(resolution)
    assert "BACKFILL TRIAGE:" in card
    assert "semantic coverage: no (inventory triage only)" in card
    assert "TOPIC-SOLVER-EXPERIMENTS-AND-NO-GO" in card


def test_availability_review_is_exposed_without_semantic_uplift() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        ".artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/"
        "run-20260726T211018Z-SMM4-14a491b/README.md",
        "read",
    )

    assert resolution.triage is None
    assert len(resolution.reviews) == 1
    review = resolution.reviews[0]
    assert review["review_scope"] == "availability_and_provenance"
    assert review["outcome"] == "deferred"
    card = _render_card(resolution)
    assert "semantic coverage: no (availability/provenance only)" in card


def test_docctl_explains_term_topic_triage_and_review_ids() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    assert system.explain("TERM-CURRENT")["kind"] == "term"
    assert system.explain("TOPIC-AUTHORITY-AND-CURRENT-STATE")["kind"] == "topic"
    assert system.explain("TRIAGE-CUT-SOLVER-TRACKED-LONGTAIL")["kind"] == "backfill_triage"
    assert system.explain("REVIEW-20260812-P2-REFRESH-BATCH5")["kind"] == "backfill_review"


def test_closed_dossier_is_immutable_and_exposes_registered_knowledge() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "docs/research/b1_conditional_halo_20260722/README.md",
        "edit",
    )

    assert resolution.dossier is not None
    assert resolution.dossier["lifecycle"] == "historical"
    assert resolution.contract["document_class"] == "historical_evidence"
    assert resolution.contract["mutation"] == "immutable"
    assert resolution.allowed is False
    assert "DOC-INV-002" in resolution.contract["invariant_refs"]


def test_reviewed_dossier_operation_card_exposes_current_curation_review() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    resolution = system.resolve(
        "docs/research/noncert_cuts_ab16_20260724/README.md",
        "read",
    )

    assert resolution.dossier is not None
    assert len(resolution.reviews) == 1
    review = resolution.reviews[0]
    assert review["id"] == "REVIEW-20260811-NONCERT-CUTS-AB16"
    assert review["outcome"] == "claims_promoted"
    assert "CLAIM-AB16-NO-SCIENTIFIC-CUT-RESULT" in review["claim_ids"]
    card = _render_card(resolution)
    assert "CURATION REVIEW:" in card
    assert review["id"] in card


def test_dossier_operation_card_exposes_compact_separation_coordinates() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "docs/research/rule_system_redesign_20260807/FINAL_DESIGN.md",
        "read",
    )

    pairwise = next(record for record in resolution.knowledge if record["id"] == "CLAIM-PAIRWISE-CLOSURE-INCOMPLETE")
    assert pairwise["separation_profile"]["selection_modes"] == ("pairwise_closure",)
    card = _render_card(resolution)
    assert "select=pairwise_closure" in card
    assert "complete=disproved" in card


def test_framework_core_automatically_loads_full_maintenance_coordinates() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve("devtools/docctl.py", "edit")

    assert resolution.contract["document_class"] == "framework_core"
    assert resolution.contract["context_level"] == "L3"
    assert "docs/governance/document-system/ARCHITECTURE.md" in resolution.contract["required_reads"]
    assert "docs/governance/document-system/MAINTAINING.md" in resolution.contract["required_reads"]
    assert "docsystem.tests" in resolution.contract["after_change"]


def test_framework_core_is_the_final_authority_overlay_inside_closed_dossier() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "docs/research/b1_conditional_halo_20260722/DOC_POLICY.json",
        "create",
    )

    assert resolution.dossier is not None
    assert resolution.dossier["lifecycle"] == "historical"
    assert resolution.contract["document_class"] == "framework_core"
    assert resolution.contract["authority_role"] == "framework_definition"
    assert resolution.contract["mutation"] == "immutable"
    assert resolution.contract["context_level"] in {"L2", "L3"}


def test_knowledge_schema_change_enters_full_framework_context() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "data/knowledge/schemas/claim.schema.json",
        "edit",
    )

    assert resolution.contract["document_class"] == "framework_core"
    assert resolution.contract["context_level"] == "L3"
    assert "DOC-ADR-005" in resolution.contract["adr_refs"]
    assert "DOC-ADR-006" in resolution.contract["adr_refs"]
    assert "docs/governance/document-system/ARCHITECTURE.md" in resolution.contract["required_reads"]
    assert "docs/governance/document-system/MAINTAINING.md" in resolution.contract["required_reads"]


def test_non_markdown_knowledge_source_receives_knowledge_write_protocol() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "data/knowledge/claims.jsonl",
        "edit",
    )

    assert resolution.contract["document_class"] == "structured_knowledge"
    assert resolution.contract["mutation"] == "governed"
    assert "knowledge.build" in resolution.contract["after_change"]
    assert "knowledge.check" in resolution.contract["after_change"]


def test_restored_artifact_payload_is_tightened_by_dossier_lifecycle() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        ".artifacts/ab16_arms_20260802/report.md",
        "create",
    )

    assert resolution.dossier is not None
    assert resolution.dossier["lifecycle"] == "historical"
    assert resolution.contract["document_class"] == "historical_evidence"
    assert resolution.contract["mutation"] == "immutable"
    assert "new evidence record may be created once" in resolution.operation_guidance
    assert ".artifacts/README.md" in resolution.contract["required_reads"]


def test_operation_card_contains_rule_reason_without_loading_the_whole_archive() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    card = _render_card(system.resolve("docs/CURRENT.md", "edit"))

    assert "MUTATION: generator_only" in card
    assert "DOC-INV-001" in card
    assert "WRITE THROUGH:" in card
    assert "FRAMEWORK: .docsystem/manifest.json" in card
    assert len(card.splitlines()) < 80


def test_exact_path_rule_refines_broader_prefix_rule(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    policy = _policy(
        "notes",
        rules=[
            {
                "id": "notes_family",
                "match": {"prefix": "notes/"},
                "set": {
                    "document_class": "living",
                    "authority_role": "explanatory",
                    "mutation": "direct",
                    "purpose": "broad purpose",
                },
                "rationale": "broad directory rule",
            },
            {
                "id": "special_note",
                "match": {"path": "notes/special.md"},
                "set": {
                    "purpose": "exact purpose",
                    "volatile_facts": "forbidden",
                },
                "rationale": "one exact exception",
            },
        ],
    )
    _write_json(root / "sandbox/DOC_POLICY.json", policy)
    target = root / "sandbox/notes/special.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Special\n", encoding="utf-8")
    _stage_paths(root, "sandbox/DOC_POLICY.json", "sandbox/notes/special.md")

    resolution = DocumentSystem(root).resolve("sandbox/notes/special.md", "edit")

    assert resolution.contract["purpose"] == "exact purpose"
    assert resolution.contract["volatile_facts"] == "forbidden"
    assert resolution.matched_rules[-1].endswith("#special_note")


def test_equal_specificity_scalar_conflict_fails_closed(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    policy = _policy(
        "conflict",
        rules=[
            {
                "id": "first",
                "match": {"path": "same.md"},
                "set": {"purpose": "first purpose"},
                "rationale": "first",
            },
            {
                "id": "second",
                "match": {"path": "same.md"},
                "set": {"purpose": "second purpose"},
                "rationale": "second",
            },
        ],
    )
    _write_json(root / "sandbox/DOC_POLICY.json", policy)
    target = root / "sandbox/same.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Same\n", encoding="utf-8")
    _stage_paths(root, "sandbox/DOC_POLICY.json", "sandbox/same.md")

    with pytest.raises(DocSystemError, match="equal-specificity rules"):
        DocumentSystem(root).resolve("sandbox/same.md", "edit")


def test_paths_selector_cannot_gain_precedence_from_an_unrelated_long_member(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    policy = _policy(
        "paths.conflict",
        rules=[
            {
                "id": "short_group",
                "match": {"paths": ["same.md"]},
                "set": {"purpose": "first purpose"},
                "rationale": "first exact-path group",
            },
            {
                "id": "long_group",
                "match": {
                    "paths": [
                        "same.md",
                        "an/unrelated/member/whose/name/is/much/longer.md",
                    ]
                },
                "set": {"purpose": "second purpose"},
                "rationale": "second exact-path group",
            },
        ],
    )
    _write_json(root / "sandbox/DOC_POLICY.json", policy)
    target = root / "sandbox/same.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Same\n", encoding="utf-8")
    _stage_paths(root, "sandbox/DOC_POLICY.json", "sandbox/same.md")

    with pytest.raises(DocSystemError, match="equal-specificity rules"):
        DocumentSystem(root).resolve("sandbox/same.md", "edit")


def test_child_policy_cannot_silently_relax_parent_mutation(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _write_json(
        root / "zone/DOC_POLICY.json",
        _policy(
            "zone",
            defaults={
                "document_class": "normative",
                "authority_role": "normative_input",
                "mutation": "governed",
                "purpose": "governed parent",
            },
        ),
    )
    _write_json(
        root / "zone/sub/DOC_POLICY.json",
        _policy(
            "zone.sub",
            defaults={"mutation": "direct", "purpose": "unsafe relaxation"},
        ),
    )
    target = root / "zone/sub/file.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# File\n", encoding="utf-8")
    _stage_paths(root, "zone/DOC_POLICY.json", "zone/sub/DOC_POLICY.json", "zone/sub/file.md")

    with pytest.raises(DocSystemError, match="requires relaxation_decision_id"):
        DocumentSystem(root).resolve("zone/sub/file.md", "edit")


def test_relaxation_requires_a_current_document_system_scoped_decision(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    _write_json(
        root / "zone/DOC_POLICY.json",
        _policy(
            "zone",
            defaults={
                "document_class": "normative",
                "authority_role": "normative_input",
                "mutation": "governed",
                "purpose": "governed parent",
            },
        ),
    )
    _write_json(
        root / "zone/sub/DOC_POLICY.json",
        _policy(
            "zone.sub",
            defaults={
                "mutation": "direct",
                "purpose": "unrelated decision must not authorize this",
                "relaxation_decision_id": "DECISION-B6-HOLD-20260803",
            },
        ),
    )
    target = root / "zone/sub/file.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# File\n", encoding="utf-8")
    _stage_paths(root, "zone/DOC_POLICY.json", "zone/sub/DOC_POLICY.json", "zone/sub/file.md")

    with pytest.raises(DocSystemError, match="does not authorize document-policy"):
        DocumentSystem(root).resolve("zone/sub/file.md", "edit")


def test_relaxation_decision_must_be_explicit_on_the_relaxing_overlay(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    decision_id = "DECISION-DOCUMENT-POLICY-RELAX-TEST"
    _append_decision(
        root,
        {
            "id": decision_id,
            "title": "fixture policy relaxation",
            "status": "current",
            "statement": "fixture",
            "scope": ["document-system"],
            "authority_effect": "scope_boundary",
        },
    )
    _write_json(
        root / "zone/DOC_POLICY.json",
        _policy(
            "zone",
            defaults={
                "document_class": "normative",
                "authority_role": "normative_input",
                "mutation": "governed",
                "purpose": "governed parent",
                "relaxation_decision_id": decision_id,
            },
        ),
    )
    _write_json(
        root / "zone/sub/DOC_POLICY.json",
        _policy(
            "zone.sub",
            defaults={"mutation": "direct", "purpose": "missing local decision"},
        ),
    )
    target = root / "zone/sub/file.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# File\n", encoding="utf-8")
    _stage_paths(root, "zone/DOC_POLICY.json", "zone/sub/DOC_POLICY.json", "zone/sub/file.md")

    with pytest.raises(DocSystemError, match="requires relaxation_decision_id"):
        DocumentSystem(root).resolve("zone/sub/file.md", "edit")


def test_document_system_scoped_decision_can_authorize_explicit_relaxation(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    decision_id = "DECISION-DOCUMENT-POLICY-RELAX-TEST"
    _append_decision(
        root,
        {
            "id": decision_id,
            "title": "fixture policy relaxation",
            "status": "current",
            "statement": "fixture",
            "scope": ["document-system"],
            "authority_effect": "scope_boundary",
        },
    )
    _write_json(
        root / "zone/DOC_POLICY.json",
        _policy(
            "zone",
            defaults={
                "document_class": "normative",
                "authority_role": "normative_input",
                "mutation": "governed",
                "purpose": "governed parent",
            },
        ),
    )
    _write_json(
        root / "zone/sub/DOC_POLICY.json",
        _policy(
            "zone.sub",
            defaults={
                "mutation": "direct",
                "purpose": "explicitly authorized relaxation",
                "relaxation_decision_id": decision_id,
            },
        ),
    )
    target = root / "zone/sub/file.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# File\n", encoding="utf-8")
    _stage_paths(root, "zone/DOC_POLICY.json", "zone/sub/DOC_POLICY.json", "zone/sub/file.md")

    resolution = DocumentSystem(root).resolve("zone/sub/file.md", "edit")
    assert resolution.contract["mutation"] == "direct"


def test_ignored_local_policy_cannot_change_effective_repository_rules(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    (root / ".gitignore").write_text("sandbox/DOC_POLICY.json\n", encoding="utf-8")
    target = root / "sandbox/file.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# File\n", encoding="utf-8")
    _init_git_repository(root)
    _write_json(
        root / "sandbox/DOC_POLICY.json",
        _policy(
            "ignored",
            defaults={
                "document_class": "locked_authority",
                "authority_role": "machine_authority",
                "mutation": "owner_only",
                "purpose": "ignored policy must have no authority",
            },
        ),
    )

    resolution = DocumentSystem(root).resolve("sandbox/file.md", "edit")

    assert "sandbox/DOC_POLICY.json" not in resolution.policies
    assert resolution.contract["document_class"] == "unmanaged"


def test_changed_path_scan_disables_rename_detection_to_keep_both_policy_sides(
    tmp_path: Path,
) -> None:
    root = _copy_framework_fixture(tmp_path)
    old = root / "archive/old.md"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text("# Old\n", encoding="utf-8")
    _init_git_repository(root)
    new = root / "elsewhere/new.md"
    new.parent.mkdir(parents=True, exist_ok=True)
    old.rename(new)

    paths = DocumentSystem(root).changed_paths()

    assert "archive/old.md" in paths
    assert "elsewhere/new.md" in paths


def test_new_owner_only_path_uses_default_off_companion_warning(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    _init_git_repository(root)
    target = root / "rules/new_authority.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")

    result = DocumentSystem(root).check_changed()

    assert not any(
        "rules/new_authority.json: changed path is owner_only" in value
        for value in result.failures
    )
    assert any(
        "rules/new_authority.json: owner-governed authority changed without" in value
        for value in result.warnings
    )


def test_append_only_context_rejects_move_and_delete() -> None:
    system = DocumentSystem(PROJECT_ROOT)

    assert system.resolve("CHANGELOG.md", "move").allowed is False
    assert system.resolve("CHANGELOG.md", "delete").allowed is False


def test_append_only_diff_accepts_suffix_and_rejects_rewrite(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    changelog = root / "CHANGELOG.md"
    changelog.write_text("# Log\n\nfirst\n", encoding="utf-8")
    _init_git_repository(root)

    changelog.write_text("# Log\n\nfirst\nsecond\n", encoding="utf-8")
    appended = DocumentSystem(root).check_changed()
    assert not any("CHANGELOG.md: append_only" in value for value in appended.failures)

    changelog.write_text("# Rewritten\n", encoding="utf-8")
    rewritten = DocumentSystem(root).check_changed()
    assert any("CHANGELOG.md: append_only content rewrites existing bytes" in value for value in rewritten.failures)


def test_existing_policy_anchor_cannot_be_removed_or_moved(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    policy_path = root / "docs/governance/document-system/DOC_POLICY.json"
    _init_git_repository(root)
    policy_path.unlink()
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)

    result = DocumentSystem(root).check_changed()

    assert any(
        "docs/governance/document-system/DOC_POLICY.json: policy anchor was removed or moved" in value
        for value in result.failures
    )


def test_unregistered_framework_adr_is_reported(tmp_path: Path) -> None:
    root = _copy_framework_fixture(tmp_path)
    extra = root / "docs/governance/document-system/ADR/999-unregistered.md"
    extra.write_text(
        "# DOC-ADR-999：fixture\n\n状态：Accepted\n",
        encoding="utf-8",
    )
    _stage_paths(root, "docs/governance/document-system/ADR/999-unregistered.md")

    failures = DocumentSystem(root)._check_adr_registry()

    assert "unregistered framework ADR: docs/governance/document-system/ADR/999-unregistered.md" in failures


def test_legacy_doc_classes_is_exactly_the_distributed_policy_projection() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    actual = (PROJECT_ROOT / "data/repository_governance/doc_classes.json").read_text(encoding="utf-8")
    assert actual == system.render_legacy_projection()


def test_generated_guidance_projection_is_write_through_only() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    resolution = system.resolve("docs/GUIDANCE_INDEX.md", "edit")

    assert resolution.allowed is False
    assert resolution.contract["document_class"] == "generated_projection"
    assert resolution.contract["mutation"] == "generator_only"
    assert resolution.contract["generator_action"] == "docsystem.render_guidance"
    assert ".docsystem/manifest.json" in resolution.contract["source_paths"]
    assert "data/repository_governance/document_system/entrypoints.json" in resolution.contract["source_paths"]
    assert "DOC-INV-012" in resolution.contract["invariant_refs"]
    assert "DOC-INV-013" in resolution.contract["invariant_refs"]
    assert any("docctl.py render-guidance --write" in action["command"] for action in resolution.action_commands)


def test_current_guidance_surface_is_explicit_and_fresh() -> None:
    docs_policy = json.loads((PROJECT_ROOT / "docs/DOC_POLICY.json").read_text(encoding="utf-8"))
    manual_policy = json.loads((PROJECT_ROOT / "docs/项目说明/DOC_POLICY.json").read_text(encoding="utf-8"))
    assert docs_policy["defaults"]["document_class"] == "unmanaged"
    assert manual_policy["defaults"]["document_class"] == "unmanaged"

    system = DocumentSystem(PROJECT_ROOT)
    historical = system.resolve("docs/项目说明/08_phase_1_2_plan.md", "read")
    roadmap = system.resolve("docs/项目说明/ROADMAP.md", "read")
    recovery = system.resolve(".docsystem/RECOVERY.md", "read")
    history_index = system.resolve("docs/history/README.md", "read")
    history_payload = system.resolve(
        "docs/history/status/00_master_roadmap_pre_phase3_20260812.md",
        "read",
    )
    assert historical.contract["document_class"] == "historical_evidence"
    assert historical.contract["mutation"] == "immutable"
    assert roadmap.contract["document_class"] == "living"
    assert roadmap.contract["purpose"].startswith("Future-only roadmap")
    assert recovery.contract["document_class"] == "framework_core"
    assert recovery.contract["purpose"].startswith("Fail-closed bootstrap recovery")
    assert history_index.contract["document_class"] == "living"
    assert history_index.contract["mutation"] == "direct"
    assert history_payload.contract["document_class"] == "historical_evidence"
    assert history_payload.contract["mutation"] == "immutable"

    actual = (PROJECT_ROOT / "docs/GUIDANCE_INDEX.md").read_text(encoding="utf-8")
    assert actual == system.render_guidance_projection()
    assert "docs/项目说明/ROADMAP.md" in actual
    assert "docs/OPEN_QUESTIONS.md" in actual
    assert "agent_bootstrap" not in actual
    assert "agent_operations" in actual
    assert "code_map" in actual
    assert "legacy_file_status" in actual
    assert "docs/项目说明/08_phase_1_2_plan.md" not in actual
    assert "00_master_roadmap_pre_phase3_20260812.md" not in actual
    assert "尚未由文档系统声明用途" not in actual


def test_generated_validity_projection_is_write_through_only() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "docs/VALIDITY_LEDGER.md",
        "edit",
    )

    assert resolution.allowed is False
    assert resolution.contract["document_class"] == "generated_projection"
    assert resolution.contract["mutation"] == "generator_only"
    assert resolution.contract["generator_action"] == "knowledge.build"
    assert "data/knowledge/claims.jsonl" in resolution.contract["source_paths"]
    assert "DOC-ADR-007" in resolution.contract["adr_refs"]
    assert "DOC-INV-010" in resolution.contract["invariant_refs"]


def test_dossier_operation_card_exposes_compact_validity_coordinates() -> None:
    resolution = DocumentSystem(PROJECT_ROOT).resolve(
        "docs/research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md",
        "read",
    )

    refuted = next(
        record for record in resolution.knowledge if record["id"] == "CLAIM-W0-ADJACENT-4X4-POWER-IMPOSSIBILITY-REFUTED"
    )
    assert refuted["validity_profile"]["event_type"] == "refutation"
    assert refuted["validity_profile"]["reuse_policy"] == "do_not_reuse"
    card = _render_card(resolution)
    assert "validity: event=refutation" in card
    assert "reuse=do_not_reuse" in card
    assert "repair=not_applicable" in card
