from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b.b5a.localized_evidence.review_packet import (
    B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE,
    EXPECTED_FORBIDDEN_CONCLUSIONS,
    EXPECTED_REQUIRED_ACCEPTANCE_IDS,
    EXPECTED_REVIEW_RECORD_TYPE,
    EXPECTED_SCOPE,
    EXPECTED_STILL_BLOCKED_GATE_IDS,
)
from src.search.phase3b.b5a.localized_evidence.review_state import (
    B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE,
    build_phase3b_b5a_localized_evidence_review_state,
    render_phase3b_b5a_localized_evidence_review_state_markdown,
    render_phase3b_b5a_localized_evidence_review_state_text,
)


def test_b5a_localized_evidence_review_state_marks_review_acceptance(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/review_packet.json")
    _write_json(project_root / packet_path, _valid_review_packet())

    report = build_phase3b_b5a_localized_evidence_review_state(
        project_root,
        review_packet_path=packet_path,
    )

    assert report["metadata"]["source"] == B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE
    assert report["metadata"]["proof_source"] is False
    status = report["status"]
    assert status["review_state_ready"] is True
    assert status["repo_side_review_state_updated"] is True
    assert status["b5a_localized_evidence_reviewed"] is True
    assert status["review_record_payload_validated"] is True
    assert status["b5a_anchor_found"] is False
    assert status["certified_anchor_found"] is False
    assert status["proof_source"] is False
    assert status["runtime_semantics_changed"] is False
    assert status["checkpoint_written"] is False
    assert status["still_blocked_gate_ids"] == ["b5a_anchor_found"]
    assert status["remaining_blocker_gate_ids"] == ["b5a_anchor_found"]
    review_state = report["review_state"]
    assert review_state["review_state_kind"] == (
        "repo_side_b5a_localized_evidence_review_state"
    )
    assert review_state["covered_anchors"] == [118, 119, 120, 121, 122, 123, 124, 125]
    assert "Review State" in render_phase3b_b5a_localized_evidence_review_state_markdown(report)
    assert "b5a_localized_evidence_reviewed=True" in (
        render_phase3b_b5a_localized_evidence_review_state_text(report)
    )


@pytest.mark.parametrize(
    ("mutator", "failed_check"),
    [
        (
            lambda payload: payload["metadata"].update({"source": "wrong_source"}),
            "review_packet_source_supported",
        ),
        (
            lambda payload: payload["status"].update({"review_packet_ready": False}),
            "review_packet_ready",
        ),
        (
            lambda payload: payload["status"].update(
                {"review_record_payload_validated": False}
            ),
            "review_record_payload_validated",
        ),
        (
            lambda payload: payload["status"].update(
                {"review_record_payload_validation_status": "failed"}
            ),
            "review_record_payload_validated",
        ),
        (
            lambda payload: payload["review_record_validator"][
                "actual_record_validation"
            ].update({"record_payload_validated": False}),
            "review_record_payload_validated",
        ),
    ],
)
def test_b5a_localized_evidence_review_state_rejects_unready_packet_or_payload(
    tmp_path: Path,
    mutator,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    packet = _valid_review_packet()
    mutator(packet)
    packet_path = Path(".artifacts/review_packet_bad.json")
    _write_json(project_root / packet_path, packet)

    report = build_phase3b_b5a_localized_evidence_review_state(
        project_root,
        review_packet_path=packet_path,
    )

    assert report["status"]["review_state_ready"] is False
    assert report["status"]["b5a_localized_evidence_reviewed"] is False
    assert failed_check in _failed_check_ids(report)


@pytest.mark.parametrize(
    ("mutator", "failed_check"),
    [
        (
            lambda payload: payload["review_packet"]["record_contract"].update(
                {"candidate_key": "68x13"}
            ),
            "review_packet_contract_locked",
        ),
        (
            lambda payload: payload["review_packet"]["record_contract"].update(
                {"covered_anchors": [119, 120]}
            ),
            "review_packet_contract_locked",
        ),
        (
            lambda payload: payload["review_packet"]["record_contract"].update(
                {"still_blocked_gate_ids": []}
            ),
            "review_packet_contract_locked",
        ),
        (
            lambda payload: payload["status"].update({"still_blocked_gate_ids": []}),
            "still_blocked_gate_ids_locked",
        ),
    ],
)
def test_b5a_localized_evidence_review_state_rejects_contract_or_gate_drift(
    tmp_path: Path,
    mutator,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    packet = _valid_review_packet()
    mutator(packet)
    packet_path = Path(".artifacts/review_packet_contract_bad.json")
    _write_json(project_root / packet_path, packet)

    report = build_phase3b_b5a_localized_evidence_review_state(
        project_root,
        review_packet_path=packet_path,
    )

    assert report["status"]["review_state_ready"] is False
    assert failed_check in _failed_check_ids(report)


@pytest.mark.parametrize(
    "flag_path",
    [
        ("metadata", "proof_source"),
        ("metadata", "checkpoint_written"),
        ("status", "certified_anchor_found"),
        ("status", "b5a_anchor_found"),
        ("status", "runtime_semantics_changed"),
    ],
)
def test_b5a_localized_evidence_review_state_rejects_safety_flag_drift(
    tmp_path: Path,
    flag_path: tuple[str, str],
) -> None:
    project_root = tmp_path / "project"
    packet = _valid_review_packet()
    section, flag = flag_path
    packet[section][flag] = True
    packet_path = Path(".artifacts/review_packet_unsafe.json")
    _write_json(project_root / packet_path, packet)

    report = build_phase3b_b5a_localized_evidence_review_state(
        project_root,
        review_packet_path=packet_path,
    )

    assert report["status"]["review_state_ready"] is False
    assert report["status"]["b5a_anchor_found"] is False
    assert "review_packet_safety_flags_off" in _failed_check_ids(report)


def test_b5a_localized_evidence_review_state_rejects_missing_packet(
    tmp_path: Path,
) -> None:
    report = build_phase3b_b5a_localized_evidence_review_state(
        tmp_path / "project",
        review_packet_path=Path(".artifacts/missing.json"),
    )

    assert report["status"]["review_state_ready"] is False
    assert "review_packet_present" in _failed_check_ids(report)


def test_b5a_localized_evidence_review_state_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/review_packet.json")
    output_dir = tmp_path / "out"
    _write_json(project_root / packet_path, _valid_review_packet())
    script = repo_root / "scripts" / "phase3b" / "b5a" / "localized_evidence" / "build_review_state.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--review-packet",
            str(packet_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "review state ready: True" in no_write.stdout
    assert "b5a localized evidence reviewed: True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--review-packet",
            str(packet_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "b5a_localized_evidence_review_state_json=" in write.stdout
    payload = json.loads(
        (output_dir / "b5a_localized_evidence_review_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["review_state_ready"] is True
    assert payload["status"]["b5a_anchor_found"] is False
    assert (output_dir / "b5a_localized_evidence_review_state.md").exists()
    assert (output_dir / "b5a_localized_evidence_review_state.txt").exists()


def _valid_review_packet() -> dict[str, object]:
    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE,
            "generated_at": "2026-04-25T12:49:15Z",
            "diagnostic_semantics": (
                "b5a_localized_evidence_reviewer_intake_contract_not_gate_promotion"
            ),
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            **_authorization_safety_false_fields(),
        },
        "status": {
            "review_packet_ready": True,
            "review_record_validator_ready": True,
            "review_record_payload_provided": True,
            "review_record_payload_validated": True,
            "review_record_payload_validation_status": "passed",
            "reviewer_acceptance_required": True,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            **_authorization_safety_false_fields(),
            "still_blocked_gate_ids": ["b5a_anchor_found"],
        },
        "review_packet": {
            "record_contract": {
                "record_type": EXPECTED_REVIEW_RECORD_TYPE,
                "scope": EXPECTED_SCOPE,
                "candidate_key": "67x13",
                "covered_anchors": [118, 119, 120, 121, 122, 123, 124, 125],
                "required_acceptance_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
                "forbidden_conclusions": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
                "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
            }
        },
        "review_record_validator": {
            "actual_record_validation": {
                "record_payload_provided": True,
                "record_payload_validated": True,
                "validation_status": "passed",
                "failed_rule_count": 0,
                "failed_rule_ids": [],
            }
        },
    }


def _authorization_safety_false_fields() -> dict[str, bool]:
    return {
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "preflight_gate_mutated": False,
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _failed_check_ids(report: dict[str, object]) -> set[str]:
    return {
        str(check["check_id"])
        for check in report["checks"]
        if isinstance(check, dict) and check.get("status") == "fail"
    }
