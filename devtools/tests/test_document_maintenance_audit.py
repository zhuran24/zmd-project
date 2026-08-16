"""Focused contracts for the read-only periodic document maintenance audit."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devtools import document_maintenance_audit as maintenance  # noqa: E402
from devtools.docctl import DocumentSystem  # noqa: E402
from devtools.document_governance_gate import capture_git_visible_state  # noqa: E402
from devtools.document_maintenance_audit import run_maintenance_audit  # noqa: E402


def _run(system: DocumentSystem, profile: str = "weekly", as_of: str = "2026-08-16"):
    return run_maintenance_audit(system, profile=profile, as_of=date.fromisoformat(as_of))


def test_real_maintenance_audit_is_manifest_owned_and_governed() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    descriptor = system.manifest["maintenance_audit"]

    assert system.manifest["system_version"] == "2.6.0"
    assert descriptor == {
        "source": "data/repository_governance/document_system/maintenance_audit.json",
        "schema": "data/repository_governance/document_system/maintenance_audit.schema.json",
        "projection": "docs/MAINTENANCE_QUEUE.md",
    }
    assert system.guide()["maintenance_audit"] == descriptor["source"]
    assert system.guide()["maintenance_queue"] == descriptor["projection"]
    assert system.explain("DOC-AUDIT-TOPIC-COVERAGE")["kind"] == "maintenance_audit_check"
    assert system.explain("audit:phase_close")["kind"] == "maintenance_audit_profile"

    framework_paths = (
        *descriptor.values(),
        "devtools/document_maintenance_audit.py",
        "devtools/tests/test_document_maintenance_audit.py",
    )
    for relpath in framework_paths:
        resolution = system.resolve(str(relpath), "edit")
        if relpath == descriptor["projection"]:
            assert resolution.contract["document_class"] == "generated_projection"
            assert resolution.contract["mutation"] == "generator_only"
        else:
            assert resolution.contract["document_class"] == "framework_core"
            assert resolution.contract["mutation"] == "governed"
            assert resolution.contract["context_level"] == "L3"
        assert "DOC-INV-019" in resolution.contract["invariant_refs"]
        assert "DOC-ADR-015" in resolution.contract["adr_refs"]

    profiles = system.governance_gate_profiles
    for profile_id in ("changed", "full", "weekly"):
        assert "maintenance_audit" in profiles[profile_id]["lane_ids"]
    assert "maintenance_audit" not in profiles["framework"]["lane_ids"]
    for profile_id in ("changed", "full", "weekly", "framework"):
        assert "maintenance_audit_regressions" in profiles[profile_id]["lane_ids"]


def test_weekly_audit_is_read_only_and_has_no_blocking_findings() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    before = capture_git_visible_state(PROJECT_ROOT)
    result = _run(system)
    after = capture_git_visible_state(PROJECT_ROOT)

    assert result.passed
    assert result.counts["error"] == 0
    assert result.counts["warning"] == 0
    assert result.counts["info"] >= 1
    assert before.digest == after.digest


def test_phase_close_projection_is_fresh_and_keeps_authority_boundary_explicit() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    expected = system.render_maintenance_projection()
    actual = (PROJECT_ROOT / "docs/MAINTENANCE_QUEUE.md").read_text(encoding="utf-8")

    assert actual == expected
    assert "100% inventory coverage" not in actual
    assert "不建立第二套 current 状态、claim、review、triage 或 owner authority" in actual
    assert "清单不自动授予 close" in actual
    assert "DOC-AUDIT-PHASE-BOUNDARY-SURFACE" in actual


def test_active_dossier_after_audit_clock_reports_stale_snapshot() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    system.maintenance_audit_payload = {
        **system.maintenance_audit_payload,
        "snapshot_as_of": "2026-08-14",
    }

    result = _run(system, as_of="2026-08-14")
    finding = next(
        item
        for item in result.findings
        if item.check_id == "DOC-AUDIT-ACTIVE-DOSSIER-AGE"
        and item.subject == "DOSSIER-SOLVER-REASONING-OUTER-LOOP-REVIEWS-20260815-D26B592E99"
    )

    assert finding.severity == "error"
    assert "记录晚于维护快照，快照陈旧" in finding.message
    assert "已打开 -" not in finding.message
    assert "age_days" not in finding.details


def test_expired_ephemeral_document_is_a_mechanical_error() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    system.ephemeral_payload = {
        **system.ephemeral_payload,
        "records": [
            {
                "path": "docs/ephemeral/expired.md",
                "created_at": "2026-08-01",
                "expires_at": "2026-08-10",
                "exit_action": "delete",
                "successor_path": None,
                "reason": "fixture",
            }
        ],
    }

    result = _run(system)

    assert not result.passed
    assert any(
        finding.check_id == "DOC-AUDIT-EPHEMERAL-EXPIRY"
        and finding.severity == "error"
        and finding.subject == "docs/ephemeral/expired.md"
        for finding in result.findings
    )


def test_term_alias_collision_is_a_mechanical_error() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    system._ensure_knowledge()
    terms = deepcopy(system._terms)
    assert terms
    first = next(iter(terms.values()))
    duplicate = deepcopy(first)
    duplicate["id"] = "TERM-MAINTENANCE-COLLISION-FIXTURE"
    duplicate["canonical_label"] = str(first["canonical_label"])
    duplicate["aliases"] = []
    terms[duplicate["id"]] = duplicate
    system._terms = terms

    result = _run(system)

    assert not result.passed
    assert any(
        finding.check_id == "DOC-AUDIT-TERMINOLOGY-COLLISION"
        and finding.severity == "error"
        for finding in result.findings
    )


def test_open_claim_missing_from_topics_is_a_mechanical_error() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    system._ensure_knowledge()
    topics = deepcopy(system._topics)
    assert topics
    for topic in topics.values():
        topic["open_question_claim_ids"] = []
    system._topics = topics

    result = _run(system)

    assert not result.passed
    assert any(
        finding.check_id == "DOC-AUDIT-TOPIC-COVERAGE"
        and finding.severity == "error"
        and "open claim" in finding.message
        for finding in result.findings
    )


def test_git_visible_change_is_a_fresh_touch_before_commit(monkeypatch) -> None:
    system = DocumentSystem(PROJECT_ROOT)
    target = "docs/governance/document-system/ADR/015-periodic-semantic-maintenance-audit.md"
    resolution = system.resolve(target, "read")
    assert resolution.contract["review_policy"]["max_interval_days"] > 0

    monkeypatch.setattr(maintenance, "_last_touch_dates", lambda _root, _paths: {})
    monkeypatch.setattr(maintenance, "_git_changed_paths", lambda _root: {target})

    result = _run(system)

    assert not any(
        finding.check_id == "DOC-AUDIT-LIVING-FRESHNESS"
        and finding.subject == target
        and "没有该文档的已提交触达日期" in finding.message
        for finding in result.findings
    )



def test_stale_snapshot_escalates_without_rewriting_any_source() -> None:
    system = DocumentSystem(PROJECT_ROOT)
    before = capture_git_visible_state(PROJECT_ROOT)

    result = _run(system, profile="deep", as_of="2026-10-20")

    after = capture_git_visible_state(PROJECT_ROOT)
    assert not result.passed
    assert any(
        finding.check_id == "DOC-AUDIT-SNAPSHOT-AGE" and finding.severity == "error"
        for finding in result.findings
    )
    assert before.digest == after.digest
