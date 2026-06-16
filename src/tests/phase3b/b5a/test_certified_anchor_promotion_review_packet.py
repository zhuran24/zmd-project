from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b.b5a.certified_anchor_promotion_review_packet import (
    B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE,
    EXPECTED_COVERED_ANCHORS,
    EXPECTED_FORBIDDEN_CONCLUSIONS,
    EXPECTED_PROMOTION_REVIEW_RECORD_TYPE,
    EXPECTED_REQUIRED_ACCEPTANCE_IDS,
    EXPECTED_SCOPE,
    EXPECTED_STILL_BLOCKED_GATE_IDS,
    build_phase3b_b5a_certified_anchor_promotion_review_packet,
    render_phase3b_b5a_certified_anchor_promotion_review_packet_markdown,
    render_phase3b_b5a_certified_anchor_promotion_review_packet_text,
)
from src.search.phase3b.b5a.coordinate_validation_reason_localization import (
    B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
)
from src.search.phase3b.b5a.localized_evidence.readiness import (
    B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
)
from src.search.phase3b.b5a.localized_evidence.review_state import (
    B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE,
)
from src.search.phase3b.b5a.localized_evidence.validator import (
    B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
)


def test_b5a_certified_anchor_promotion_packet_ready_without_payload(
    tmp_path: Path,
) -> None:
    project_root, paths = _write_valid_chain(tmp_path)

    report = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=paths["validator"],
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
    )

    assert report["metadata"]["source"] == (
        B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE
    )
    assert report["metadata"]["solver_invoked"] is False
    status = report["status"]
    assert status["promotion_review_packet_ready"] is True
    assert status["promotion_review_record_validator_ready"] is True
    assert status["promotion_review_payload_provided"] is False
    assert status["promotion_review_payload_validated"] is False
    assert status["promotion_review_payload_validation_status"] == "not_run"
    assert status["certified_anchor_promotion_review_accepted"] is False
    assert status["b5a_anchor_found"] is False
    assert status["certified_anchor_found"] is False
    assert status["proof_source"] is False
    assert status["runtime_semantics_changed"] is False
    assert status["preflight_gate_mutated"] is False
    assert status["still_blocked_gate_ids"] == ["b5a_anchor_found"]
    contract = report["promotion_review_packet"]["record_contract"]
    assert contract["record_type"] == EXPECTED_PROMOTION_REVIEW_RECORD_TYPE
    assert contract["scope"] == EXPECTED_SCOPE
    assert contract["covered_anchors"] == EXPECTED_COVERED_ANCHORS
    assert contract["required_acceptance_ids"] == EXPECTED_REQUIRED_ACCEPTANCE_IDS
    assert contract["forbidden_conclusions"] == EXPECTED_FORBIDDEN_CONCLUSIONS
    assert contract["still_blocked_gate_ids"] == EXPECTED_STILL_BLOCKED_GATE_IDS
    assert "candidate_elimination_claim" in contract["required_fields"]
    assert (
        report["promotion_review_packet"]["reviewer_payload_template"][
            "candidate_elimination_claim"
        ]
        is False
    )
    assert "Certified-Anchor Promotion" in (
        render_phase3b_b5a_certified_anchor_promotion_review_packet_markdown(report)
    )
    assert "promotion_review_packet_ready=True" in (
        render_phase3b_b5a_certified_anchor_promotion_review_packet_text(report)
    )


@pytest.mark.parametrize(
    ("target", "mutator", "failed_check"),
    [
        (
            "review_state",
            lambda payload: payload["metadata"].update({"source": "wrong_source"}),
            "review_state_ready_and_safe",
        ),
        (
            "review_state",
            lambda payload: payload["status"].update({"review_state_ready": False}),
            "review_state_ready_and_safe",
        ),
        (
            "review_state",
            lambda payload: payload["status"].update({"proof_source": True}),
            "review_state_ready_and_safe",
        ),
        (
            "validator",
            lambda payload: payload["status"].update(
                {"localized_evidence_validator_ready": False}
            ),
            "localized_evidence_validator_ready_and_safe",
        ),
        (
            "validator",
            lambda payload: payload["localized_evidence_validator"][
                "accepted_lanes"
            ][0].update({"covered_anchors": [119]}),
            "localized_evidence_validator_ready_and_safe",
        ),
        (
            "readiness",
            lambda payload: payload["old_signature_precedent_policy"].update(
                {"old_m6x4_signature_artifact_used_as_current_b5a_evidence": True}
            ),
            "localized_evidence_readiness_current_source",
        ),
        (
            "readiness",
            lambda payload: payload["lanes"][1].update({"current_source_complete": False}),
            "localized_evidence_readiness_current_source",
        ),
        (
            "reason",
            lambda payload: payload["status"].update({"unknown_anchor_count": 1}),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].pop("key"),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].update({"key": ""}),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].update({"key": "wrong", "expected_key": "67x13"}),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].pop("expected_key"),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].update({"expected_key": "wrong"}),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].update({"matches_expected": False}),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].pop("matches_expected"),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["candidate"].update({"localized_key": ""}),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "reason",
            lambda payload: payload["reason_localization"]["anchor_rows"][0].update(
                {"category": "signature_monotonic_forced_label"}
            ),
            "reason_localization_complete_for_anchors118_125",
        ),
        (
            "post",
            lambda payload: payload["status"].update({"failed_checks": []}),
            "post_acceptance_only_b5a_anchor_blocked",
        ),
        (
            "post",
            lambda payload: payload["checks"].append(
                {
                    "check_id": "unexpected_blocking_failure",
                    "status": "fail",
                    "blocking": True,
                    "detail": "must block promotion",
                }
            ),
            "post_acceptance_only_b5a_anchor_blocked",
        ),
        (
            "post",
            lambda payload: payload["status"].update(
                {"production_acceptance_refresh_completed": False}
            ),
            "post_acceptance_only_b5a_anchor_blocked",
        ),
    ],
)
def test_b5a_certified_anchor_promotion_packet_rejects_bad_chain(
    tmp_path: Path,
    target: str,
    mutator,
    failed_check: str,
) -> None:
    project_root, paths = _write_valid_chain(tmp_path)
    payload = json.loads((project_root / paths[target]).read_text(encoding="utf-8"))
    mutator(payload)
    _write_json(project_root / paths[target], payload)

    report = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=paths["validator"],
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
    )

    assert report["status"]["promotion_review_packet_ready"] is False
    assert failed_check in _failed_check_ids(report)
    assert report["status"]["b5a_anchor_found"] is False
    assert report["status"]["certified_anchor_found"] is False


def test_b5a_certified_anchor_promotion_packet_rejects_missing_chain_file(
    tmp_path: Path,
) -> None:
    project_root, paths = _write_valid_chain(tmp_path)

    report = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=Path(".artifacts/missing.json"),
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
    )

    assert report["status"]["promotion_review_packet_ready"] is False
    assert "localized_evidence_validator_present" in _failed_check_ids(report)


def test_b5a_certified_anchor_promotion_packet_validates_supplied_payload(
    tmp_path: Path,
) -> None:
    project_root, paths = _write_valid_chain(tmp_path)
    payload_path = Path(".artifacts/promotion_payload.json")
    _write_json(project_root / payload_path, _valid_promotion_payload())

    report = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=paths["validator"],
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
        promotion_review_payload_path=payload_path,
    )

    status = report["status"]
    assert status["promotion_review_packet_ready"] is True
    assert status["promotion_review_payload_provided"] is True
    assert status["promotion_review_payload_validated"] is True
    assert status["promotion_review_payload_validation_status"] == "passed"
    assert status["certified_anchor_promotion_review_accepted"] is True
    assert status["b5a_anchor_found"] is False
    assert status["certified_anchor_found"] is False
    assert status["proof_source"] is False
    assert status["runtime_semantics_changed"] is False
    actual = report["promotion_review_record_validator"]["actual_record_validation"]
    assert actual["record_payload_validated"] is True
    assert actual["certified_anchor_promotion_review_accepted"] is True
    assert actual["failed_rule_ids"] == []


@pytest.mark.parametrize(
    ("mutator", "failed_rule"),
    [
        (
            lambda payload: payload.update({"record_type": "wrong"}),
            "record_type",
        ),
        (
            lambda payload: payload.update({"candidate_key": "68x13"}),
            "candidate_key",
        ),
        (
            lambda payload: payload.update({"covered_anchors": [118]}),
            "covered_anchors",
        ),
        (
            lambda payload: payload.update({"source_review_state_ready": False}),
            "source_review_state_ready",
        ),
        (
            lambda payload: payload.update({"verdict": "accepted"}),
            "verdict_accepts_certified_anchor_promotion_review",
        ),
        (
            lambda payload: payload.update(
                {"certified_anchor_promotion_review_accepted": False}
            ),
            "certified_anchor_promotion_review_accepted",
        ),
        (
            lambda payload: payload["accepted_statement_ids"].pop(),
            "accepted_statement_ids",
        ),
        (
            lambda payload: payload.update({"runtime_elimination_authorized": True}),
            "no_forbidden_positive_flags",
        ),
        (
            lambda payload: payload.pop("runtime_elimination_authorized"),
            "no_forbidden_positive_flags",
        ),
        (
            lambda payload: payload.update({"b5a_anchor_found": True}),
            "no_forbidden_positive_flags",
        ),
        (
            lambda payload: payload.update({"candidate_elimination_claim": True}),
            "no_forbidden_positive_flags",
        ),
        (
            lambda payload: payload.pop("candidate_elimination_claim"),
            "no_forbidden_positive_flags",
        ),
        (
            lambda payload: payload.update({"still_blocked_gate_ids": []}),
            "still_blocked_gate_ids",
        ),
    ],
)
def test_b5a_certified_anchor_promotion_packet_rejects_bad_payloads(
    tmp_path: Path,
    mutator,
    failed_rule: str,
) -> None:
    project_root, paths = _write_valid_chain(tmp_path)
    payload_path = Path(".artifacts/promotion_payload_bad.json")
    payload = _valid_promotion_payload()
    mutator(payload)
    _write_json(project_root / payload_path, payload)

    report = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=paths["validator"],
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
        promotion_review_payload_path=payload_path,
    )

    assert report["status"]["promotion_review_packet_ready"] is True
    assert report["status"]["promotion_review_payload_provided"] is True
    assert report["status"]["promotion_review_payload_validated"] is False
    actual = report["promotion_review_record_validator"]["actual_record_validation"]
    assert failed_rule in actual["failed_rule_ids"]
    assert report["status"]["b5a_anchor_found"] is False


def test_b5a_certified_anchor_promotion_packet_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    project_root, paths = _write_valid_chain(tmp_path)
    payload_path = Path(".artifacts/promotion_payload.json")
    output_dir = tmp_path / "out"
    _write_json(project_root / payload_path, _valid_promotion_payload())
    script = (
        repo_root
        / "scripts" / "phase3b" / "b5a" / "build_certified_anchor_promotion_review_packet.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--review-state",
            str(paths["review_state"]),
            "--localized-evidence-validator",
            str(paths["validator"]),
            "--localized-evidence-readiness",
            str(paths["readiness"]),
            "--reason-localization",
            str(paths["reason"]),
            "--post-acceptance-blocker-summary",
            str(paths["post"]),
            "--promotion-review-payload",
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
    assert "promotion review packet ready: True" in no_write.stdout
    assert "promotion review payload validated: True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--review-state",
            str(paths["review_state"]),
            "--localized-evidence-validator",
            str(paths["validator"]),
            "--localized-evidence-readiness",
            str(paths["readiness"]),
            "--reason-localization",
            str(paths["reason"]),
            "--post-acceptance-blocker-summary",
            str(paths["post"]),
            "--promotion-review-payload",
            str(payload_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "b5a_certified_anchor_promotion_review_packet_json=" in write.stdout
    payload = json.loads(
        (output_dir / "b5a_certified_anchor_promotion_review_packet.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["promotion_review_packet_ready"] is True
    assert payload["status"]["promotion_review_payload_validated"] is True
    assert payload["status"]["b5a_anchor_found"] is False
    assert (output_dir / "b5a_certified_anchor_promotion_review_packet.md").exists()
    assert (output_dir / "b5a_certified_anchor_promotion_review_packet.txt").exists()
    assert (output_dir / "reviewer_payload_template.json").exists()


def _write_valid_chain(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    project_root = tmp_path / "project"
    paths = {
        "review_state": Path(".artifacts/review_state.json"),
        "validator": Path(".artifacts/validator.json"),
        "readiness": Path(".artifacts/readiness.json"),
        "reason": Path(".artifacts/reason.json"),
        "post": Path(".artifacts/post_acceptance.json"),
    }
    _write_json(project_root / paths["review_state"], _valid_review_state())
    _write_json(project_root / paths["validator"], _valid_validator())
    _write_json(project_root / paths["readiness"], _valid_readiness())
    _write_json(project_root / paths["reason"], _valid_reason_localization())
    _write_json(project_root / paths["post"], _valid_post_acceptance_summary())
    return project_root, paths


def _authorization_safety_false_fields() -> dict[str, bool]:
    return {
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "preflight_gate_mutated": False,
    }


def _valid_review_state() -> dict[str, object]:
    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_REVIEW_STATE_SOURCE,
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            **_authorization_safety_false_fields(),
        },
        "candidate": {
            "key": "67x13",
            "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
            "scope": "candidate=67x13, anchors=118-125, b5a_localized_evidence_validator",
        },
        "status": {
            "review_state_ready": True,
            "repo_side_review_state_updated": True,
            "b5a_localized_evidence_reviewed": True,
            "review_record_payload_validated": True,
            "review_record_payload_validation_status": "passed",
            "b5a_anchor_found": False,
            "certified_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            **_authorization_safety_false_fields(),
            "still_blocked_gate_ids": ["b5a_anchor_found"],
        },
        "review_state": {
            "review_state_ready": True,
            "repo_side_review_state_updated": True,
            "b5a_localized_evidence_reviewed": True,
            "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
            "b5a_anchor_found": False,
            "certified_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            **_authorization_safety_false_fields(),
            "still_blocked_gate_ids": ["b5a_anchor_found"],
        },
    }


def _valid_validator() -> dict[str, object]:
    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
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
            ]
        },
    }


def _valid_readiness() -> dict[str, object]:
    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
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
            "readiness_ready": True,
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
        "lanes": [
            {
                "lane_id": "anchor118_ghost_overlap_forced_domain",
                "category": "ghost_overlap_forced_domain",
                "required_anchors": [118],
                "covered_anchors": [118],
                "current_source_complete": True,
                "probe_supports_lane": True,
                "solver_free_inputs": True,
                "proof_safe": True,
            },
            {
                "lane_id": "anchors119_125_signature_monotonic_forced_label",
                "category": "signature_monotonic_forced_label",
                "required_anchors": [119, 120, 121, 122, 123, 124, 125],
                "covered_anchors": [119, 120, 121, 122, 123, 124, 125],
                "current_source_complete": True,
                "probe_supports_lane": True,
                "solver_free_inputs": True,
                "proof_safe": True,
            },
        ],
        "old_signature_precedent_policy": {
            "old_m6x4_signature_artifact_used_as_current_b5a_evidence": False,
        },
    }


def _valid_reason_localization() -> dict[str, object]:
    rows = [
        {
            "anchor_idx": 118,
            "category": "ghost_overlap_forced_domain",
            "localized": True,
        }
    ]
    rows.extend(
        {
            "anchor_idx": anchor,
            "category": "signature_monotonic_forced_label",
            "localized": True,
        }
        for anchor in [119, 120, 121, 122, 123, 124, 125]
    )
    return {
        "metadata": {
            "source": B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            **_authorization_safety_false_fields(),
        },
        "candidate": {
            "key": "67x13",
            "expected_key": "67x13",
            "matches_expected": True,
        },
        "status": {
            "reason_localization_ready": True,
            "localized_anchor_count": 8,
            "requested_anchor_count": 8,
            "generic_anchor_count": 0,
            "unknown_anchor_count": 0,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            **_authorization_safety_false_fields(),
        },
        "reason_localization": {
            "anchor_range": "118-125",
            "category_counts": {
                "ghost_overlap_forced_domain": 1,
                "signature_monotonic_forced_label": 7,
            },
            "anchor_rows": rows,
        },
    }


def _valid_post_acceptance_summary() -> dict[str, object]:
    return {
        "metadata": {
            "source": "phase3b_b5a_post_acceptance_blocker_summary_v1",
            "proof_source": False,
            "solver_invoked": False,
            "checkpoint_written": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            **_authorization_safety_false_fields(),
        },
        "status": {
            "summary_ready": True,
            "reviewed_runtime_patch_exists": True,
            "production_acceptance_refresh_completed": True,
            "runtime_enablement_allowed": False,
            "preflight_ready": False,
            "failed_checks": ["b5a_anchor_found"],
            "only_b5a_anchor_found_failed": True,
            "b5a_anchor_found": False,
            "certified_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            **_authorization_safety_false_fields(),
        },
        "checks": [
            {
                "check_id": "post_acceptance_state_clean",
                "status": "pass",
                "blocking": True,
                "detail": "fixture",
            },
            {
                "check_id": "only_b5a_anchor_found_failed",
                "status": "pass",
                "blocking": True,
                "detail": "fixture",
            },
            {
                "check_id": "coordinate_validation_reason_taxonomy_complete",
                "status": "fail",
                "blocking": False,
                "detail": "covered by current reason localization fixture",
            },
        ],
    }


def _valid_promotion_payload() -> dict[str, object]:
    return {
        "record_type": EXPECTED_PROMOTION_REVIEW_RECORD_TYPE,
        "scope": EXPECTED_SCOPE,
        "candidate_key": "67x13",
        "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
        "source_review_state_ready": True,
        "reviewer_id": "gpt55pro",
        "reviewed_at": "2026-04-25T14:34:34Z",
        "verdict": "accepted_for_certified_anchor_promotion",
        "certified_anchor_promotion_review_accepted": True,
        "accepted_statement_ids": list(EXPECTED_REQUIRED_ACCEPTANCE_IDS),
        "forbidden_conclusions_rejected": list(EXPECTED_FORBIDDEN_CONCLUSIONS),
        "still_blocked_gate_ids": list(EXPECTED_STILL_BLOCKED_GATE_IDS),
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "preflight_gate_mutated": False,
        "b5a_anchor_found": False,
        "certified_anchor_found": False,
        "proof_source": False,
        "runtime_semantics_changed": False,
        "candidate_elimination_claim": False,
        "checkpoint_written": False,
        "notes": "Accepted certified-anchor promotion review contract only.",
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
