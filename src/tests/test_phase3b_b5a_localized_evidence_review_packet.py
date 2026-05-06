from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b_b5a_localized_evidence_review_packet import (
    B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE,
    EXPECTED_FORBIDDEN_CONCLUSIONS,
    EXPECTED_REQUIRED_ACCEPTANCE_IDS,
    EXPECTED_REVIEW_RECORD_TYPE,
    EXPECTED_SCOPE,
    EXPECTED_STILL_BLOCKED_GATE_IDS,
    build_phase3b_b5a_localized_evidence_review_packet,
    render_phase3b_b5a_localized_evidence_review_packet_markdown,
    render_phase3b_b5a_localized_evidence_review_packet_text,
)
from src.search.phase3b_b5a_localized_evidence_validator import (
    B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
)
from src.search.phase3b_b5a_localized_evidence_readiness import (
    B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
)


def test_b5a_localized_evidence_review_packet_ready_without_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    validator_path = Path(".artifacts/validator/b5a_localized_evidence_validator.json")
    _write_json(project_root / validator_path, _valid_validator())

    report = build_phase3b_b5a_localized_evidence_review_packet(
        project_root,
        localized_evidence_validator_path=validator_path,
    )

    assert report["metadata"]["source"] == B5A_LOCALIZED_EVIDENCE_REVIEW_PACKET_SOURCE
    assert report["metadata"]["solver_invoked"] is False
    status = report["status"]
    assert status["review_packet_ready"] is True
    assert status["review_record_validator_ready"] is True
    assert status["review_record_payload_provided"] is False
    assert status["review_record_payload_validated"] is False
    assert status["review_record_payload_validation_status"] == "not_run"
    assert status["certified_anchor_found"] is False
    assert status["b5a_anchor_found"] is False
    assert status["proof_source"] is False
    assert status["runtime_semantics_changed"] is False
    assert status["still_blocked_gate_ids"] == ["b5a_anchor_found"]
    contract = report["review_packet"]["record_contract"]
    assert contract["record_type"] == EXPECTED_REVIEW_RECORD_TYPE
    assert contract["scope"] == EXPECTED_SCOPE
    assert contract["required_acceptance_ids"] == EXPECTED_REQUIRED_ACCEPTANCE_IDS
    assert contract["forbidden_conclusions"] == EXPECTED_FORBIDDEN_CONCLUSIONS
    assert contract["still_blocked_gate_ids"] == EXPECTED_STILL_BLOCKED_GATE_IDS
    assert "External Reviewer Request Text" in (
        render_phase3b_b5a_localized_evidence_review_packet_markdown(report)
    )
    assert "review_packet_ready=True" in (
        render_phase3b_b5a_localized_evidence_review_packet_text(report)
    )


@pytest.mark.parametrize(
    ("mutator", "failed_check"),
    [
        (lambda payload: payload["metadata"].update({"source": "wrong_source"}), "localized_evidence_validator_source_supported"),
        (lambda payload: payload["status"].update({"localized_evidence_validator_ready": False}), "localized_evidence_validator_ready"),
        (lambda payload: payload["metadata"].update({"proof_source": True}), "localized_evidence_validator_safe_flags"),
        (lambda payload: payload["status"].update({"runtime_semantics_changed": True}), "localized_evidence_validator_safe_flags"),
        (lambda payload: payload["candidate"].update({"localized_key": "68x13"}), "candidate_scope_locked"),
    ],
)
def test_b5a_localized_evidence_review_packet_rejects_bad_validator_inputs(
    tmp_path: Path,
    mutator,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    validator = _valid_validator()
    mutator(validator)
    validator_path = Path(".artifacts/validator_bad.json")
    _write_json(project_root / validator_path, validator)

    report = build_phase3b_b5a_localized_evidence_review_packet(
        project_root,
        localized_evidence_validator_path=validator_path,
    )

    assert report["status"]["review_packet_ready"] is False
    assert failed_check in _failed_check_ids(report)


def test_b5a_localized_evidence_review_packet_rejects_missing_validator(
    tmp_path: Path,
) -> None:
    report = build_phase3b_b5a_localized_evidence_review_packet(
        tmp_path / "project",
        localized_evidence_validator_path=Path(".artifacts/missing.json"),
    )

    assert report["status"]["review_packet_ready"] is False
    assert "localized_evidence_validator_present" in _failed_check_ids(report)


@pytest.mark.parametrize(
    ("mutator", "failed_check"),
    [
        (
            lambda payload: payload["localized_evidence_validator"]["review_intake_scaffold"][
                "reviewer_must_accept"
            ].pop(),
            "required_acceptance_ids_locked",
        ),
        (
            lambda payload: payload["localized_evidence_validator"].update(
                {"forbidden_conclusions": ["runtime_elimination_authorized"]}
            ),
            "forbidden_conclusions_locked",
        ),
        (
            lambda payload: payload["localized_evidence_validator"]["accepted_lanes"][0].update(
                {"covered_anchors": [119]}
            ),
            "localized_evidence_lanes_locked",
        ),
    ],
)
def test_b5a_localized_evidence_review_packet_rejects_contract_mismatch(
    tmp_path: Path,
    mutator,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    validator = _valid_validator()
    mutator(validator)
    validator_path = Path(".artifacts/validator_contract_bad.json")
    _write_json(project_root / validator_path, validator)

    report = build_phase3b_b5a_localized_evidence_review_packet(
        project_root,
        localized_evidence_validator_path=validator_path,
    )

    assert report["status"]["review_packet_ready"] is False
    assert failed_check in _failed_check_ids(report)


def test_b5a_localized_evidence_review_packet_validates_supplied_payload(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    validator_path = Path(".artifacts/validator.json")
    payload_path = Path(".artifacts/reviewer_payload.json")
    _write_json(project_root / validator_path, _valid_validator())
    _write_json(project_root / payload_path, _valid_review_record_payload())

    report = build_phase3b_b5a_localized_evidence_review_packet(
        project_root,
        localized_evidence_validator_path=validator_path,
        review_record_payload_path=payload_path,
    )

    status = report["status"]
    assert status["review_packet_ready"] is True
    assert status["review_record_payload_provided"] is True
    assert status["review_record_payload_validated"] is True
    assert status["review_record_payload_validation_status"] == "passed"
    assert status["b5a_anchor_found"] is False
    assert status["certified_anchor_found"] is False
    assert status["proof_source"] is False
    actual = report["review_record_validator"]["actual_record_validation"]
    assert actual["record_payload_validated"] is True
    assert actual["failed_rule_ids"] == []


@pytest.mark.parametrize(
    ("mutator", "failed_rule"),
    [
        (
            lambda payload: payload["accepted_statement_ids"].pop(),
            "accepted_statement_ids",
        ),
        (
            lambda payload: payload.update({"runtime_elimination_authorized": True}),
            "no_forbidden_positive_flags",
        ),
        (
            lambda payload: payload.update({"still_blocked_gate_ids": []}),
            "still_blocked_gate_ids",
        ),
        (
            lambda payload: payload.update({"scope": "wrong_scope"}),
            "scope",
        ),
        (
            lambda payload: payload.update({"candidate_key": "68x13"}),
            "candidate_key",
        ),
        (
            lambda payload: payload.update({"certified_b5a_anchor_found": True}),
            "no_forbidden_positive_flags",
        ),
    ],
)
def test_b5a_localized_evidence_review_packet_rejects_bad_payloads(
    tmp_path: Path,
    mutator,
    failed_rule: str,
) -> None:
    project_root = tmp_path / "project"
    validator_path = Path(".artifacts/validator.json")
    payload_path = Path(".artifacts/reviewer_payload_bad.json")
    _write_json(project_root / validator_path, _valid_validator())
    payload = _valid_review_record_payload()
    mutator(payload)
    _write_json(project_root / payload_path, payload)

    report = build_phase3b_b5a_localized_evidence_review_packet(
        project_root,
        localized_evidence_validator_path=validator_path,
        review_record_payload_path=payload_path,
    )

    assert report["status"]["review_packet_ready"] is True
    assert report["status"]["review_record_payload_provided"] is True
    assert report["status"]["review_record_payload_validated"] is False
    assert report["status"]["review_record_payload_validation_status"] == "failed"
    actual = report["review_record_validator"]["actual_record_validation"]
    assert failed_rule in actual["failed_rule_ids"]


def test_b5a_localized_evidence_review_packet_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    project_root = tmp_path / "project"
    validator_path = Path(".artifacts/validator.json")
    payload_path = Path(".artifacts/reviewer_payload.json")
    output_dir = tmp_path / "out"
    _write_json(project_root / validator_path, _valid_validator())
    _write_json(project_root / payload_path, _valid_review_record_payload())
    script = repo_root / "scripts" / "build_phase3b_b5a_localized_evidence_review_packet.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--localized-evidence-validator",
            str(validator_path),
            "--review-record-payload",
            str(payload_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "review packet ready: True" in no_write.stdout
    assert "review record payload validated: True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--localized-evidence-validator",
            str(validator_path),
            "--review-record-payload",
            str(payload_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "b5a_localized_evidence_review_packet_json=" in write.stdout
    payload = json.loads(
        (output_dir / "b5a_localized_evidence_review_packet.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["review_packet_ready"] is True
    assert payload["status"]["review_record_payload_validated"] is True
    assert (output_dir / "b5a_localized_evidence_review_packet.md").exists()
    assert (output_dir / "b5a_localized_evidence_review_packet.txt").exists()


def _valid_validator() -> dict[str, object]:
    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
            "generated_at": "2026-04-25T11:55:16Z",
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
            "localized_evidence_validator_ready": True,
            "current_localized_evidence_validated": True,
            "reviewer_acceptance_required": True,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            **_authorization_safety_false_fields(),
        },
        "candidate": {
            "expected_key": "67x13",
            "localized_key": "67x13",
            "matches": True,
        },
        "localized_evidence_validator": {
            "validated_readiness_source": B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
            "accepted_lanes": [
                {
                    "lane_id": "anchor118_ghost_overlap_forced_domain",
                    "role": "auxiliary_cross_evidence",
                    "category": "ghost_overlap_forced_domain",
                    "covered_anchors": [118],
                    "reviewer_acceptance_required": True,
                    "accepted_by_validator": True,
                },
                {
                    "lane_id": "anchors119_125_signature_monotonic_forced_label",
                    "role": "primary_coverage_evidence",
                    "category": "signature_monotonic_forced_label",
                    "covered_anchors": [119, 120, 121, 122, 123, 124, 125],
                    "reviewer_acceptance_required": True,
                    "accepted_by_validator": True,
                },
            ],
            "review_intake_scaffold": {
                "reviewer_acceptance_required": True,
                "validator_ready_for_review": True,
                "reviewer_must_accept": [
                    {
                        "acceptance_id": (
                            "anchor118_ghost_overlap_auxiliary_evidence"
                        ),
                        "detail": "Accept auxiliary lane.",
                    },
                    {
                        "acceptance_id": (
                            "anchors119_125_signature_monotonic_primary_evidence"
                        ),
                        "detail": "Accept primary lane.",
                    },
                    {
                        "acceptance_id": "no_runtime_or_final_authorization",
                        "detail": "No authorization.",
                    },
                ],
            },
            "forbidden_conclusions": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        },
    }


def _valid_review_record_payload() -> dict[str, object]:
    return {
        "record_type": EXPECTED_REVIEW_RECORD_TYPE,
        "scope": EXPECTED_SCOPE,
        "candidate_key": "67x13",
        "covered_anchors": [118, 119, 120, 121, 122, 123, 124, 125],
        "reviewer_id": "gpt55pro",
        "reviewed_at": "2026-04-25T12:34:34Z",
        "verdict": "accepted",
        "accepted_statement_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
        "forbidden_conclusions_rejected": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "certified_b5a_anchor_found": False,
        "b5a_anchor_found": False,
        "proof_source": False,
        "runtime_semantics_changed": False,
        "checkpoint_written": False,
        "notes": "Accepted review-only evidence contract.",
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
