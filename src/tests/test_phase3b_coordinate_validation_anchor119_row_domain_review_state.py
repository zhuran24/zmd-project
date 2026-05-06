from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_review_state import (
    build_phase3b_coordinate_validation_anchor119_row_domain_review_state,
    render_phase3b_coordinate_validation_anchor119_row_domain_review_state_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_review_state_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _candidate() -> dict:
    return {
        "key": "67x13",
        "anchor_idx": 119,
        "formulation_profile": "joined_xy_block64_all_templates",
    }


def _scope() -> str:
    return (
        "candidate=67x13, anchor_idx=119, joined_xy_block64_all_templates, "
        "anchor119 fixed-anchor row-domain/count bridge"
    )


def _statements() -> list[str]:
    return [
        "default_off_retained",
        "reserved_runtime_request_downgrades_to_advisory",
        "no_proof_source_promotion",
        "acceptance_refresh_required_before_enablement",
    ]


def _conclusions() -> list[str]:
    return [
        "reviewer_signed_record_supplied_for_review",
        "reviewer_signed_record_validates_against_locked_contract",
        "separate_manual_ingest_review_approved",
        "repo_side_review_state_may_mark_reviewed_runtime_patch",
        "runtime_enablement_remains_blocked_after_review",
        "post_ingest_still_blocked_gate_ids_preserved",
    ]


def _metadata(source: str, *, proof_source: bool = False) -> dict:
    return {
        "source": source,
        "spec_only": True,
        "review_only": True,
        "default_off": True,
        "runtime_precheck_enabled": False,
        "runtime_semantics_changed": False,
        "proof_source": proof_source,
        "candidate_elimination_claim": False,
        "solver_invoked": False,
        "repo_side_review_state_updated": False,
    }


def _signoff_validator_payload(*, validated: bool = True, proof_source: bool = False) -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1",
            proof_source=proof_source,
        ),
        "candidate": _candidate(),
        "status": {
            "signoff_record_payload_provided": True,
            "signoff_record_payload_validated": validated,
            "signoff_record_payload_validation_status": "passed" if validated else "failed",
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_record_validator": {
            "actual_record_validation": {
                "record_payload_provided": True,
                "record_payload_validated": validated,
                "validation_status": "passed" if validated else "failed",
                "rule_results": [
                    {
                        "rule_id": "required_field:reviewer_id",
                        "field": "reviewer_id",
                        "observed_value": "gpt55pro",
                    },
                    {
                        "rule_id": "required_field:scope",
                        "field": "scope",
                        "observed_value": _scope(),
                    },
                    {
                        "rule_id": "agreed_statement_ids",
                        "field": "agreed_statement_ids",
                        "observed_value": _statements(),
                    },
                ],
            }
        },
    }


def _ingest_validator_payload(
    *,
    validated: bool = True,
    runtime_enablement_allowed: bool = False,
    scope: str | None = None,
) -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "manual_ingest_review_record_provided": True,
            "manual_ingest_review_record_validated": validated,
            "manual_ingest_review_record_validation_status": "passed"
            if validated
            else "failed",
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": runtime_enablement_allowed,
        },
        "ingest_review_record_validator": {
            "actual_record_validation": {
                "record_payload_provided": True,
                "record_payload_validated": validated,
                "validation_status": "passed" if validated else "failed",
                "rule_results": [
                    {
                        "rule_id": "required_field:ingest_reviewer_id",
                        "field": "ingest_reviewer_id",
                        "actual": "codex_main_coordinator",
                    },
                    {
                        "rule_id": "required_field:target_record_identity",
                        "field": "target_record_identity",
                        "actual": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                    },
                    {
                        "rule_id": "required_field:scope",
                        "field": "scope",
                        "actual": scope or _scope(),
                    },
                    {
                        "rule_id": "required_reviewer_statement_ids",
                        "field": "required_reviewer_statement_ids",
                        "actual": _statements(),
                    },
                    {
                        "rule_id": "required_review_conclusion_ids",
                        "field": "required_review_conclusion_ids",
                        "actual": _conclusions(),
                    },
                    {
                        "rule_id": "current_still_blocked_gate_ids",
                        "field": "current_still_blocked_gate_ids",
                        "actual": [
                            "reviewed_runtime_patch_exists",
                            "production_acceptance_refresh_completed",
                        ],
                    },
                    {
                        "rule_id": "post_ingest_still_blocked_gate_ids",
                        "field": "post_ingest_still_blocked_gate_ids",
                        "actual": ["production_acceptance_refresh_completed"],
                    },
                ],
            }
        },
    }


def test_review_state_marks_reviewed_runtime_patch_after_validated_inputs(
    tmp_path: Path,
) -> None:
    signoff = tmp_path / "signoff.json"
    ingest = tmp_path / "ingest.json"
    _write_json(signoff, _signoff_validator_payload())
    _write_json(ingest, _ingest_validator_payload())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_review_state(
        tmp_path,
        signoff_record_validator_path=signoff,
        ingest_review_record_validator_path=ingest,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1"
    )
    assert report["status"]["review_state_ready"] is True
    assert report["status"]["repo_side_review_state_updated"] is True
    assert report["status"]["reviewed_runtime_patch_exists"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["production_acceptance_refresh_completed"] is False
    assert report["status"]["remaining_blocker_gate_ids"] == [
        "production_acceptance_refresh_completed"
    ]
    assert report["review_state"]["proof_source"] is False
    assert report["review_state"]["candidate_elimination_claim"] is False
    assert "Review State" in render_phase3b_coordinate_validation_anchor119_row_domain_review_state_markdown(report)
    assert "reviewed_runtime_patch_exists=True" in render_phase3b_coordinate_validation_anchor119_row_domain_review_state_text(report)


def test_review_state_rejects_unvalidated_signoff(tmp_path: Path) -> None:
    signoff = tmp_path / "signoff.json"
    ingest = tmp_path / "ingest.json"
    _write_json(signoff, _signoff_validator_payload(validated=False))
    _write_json(ingest, _ingest_validator_payload())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_review_state(
        tmp_path,
        signoff_record_validator_path=signoff,
        ingest_review_record_validator_path=ingest,
    )

    assert report["status"]["review_state_ready"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "signoff_payload_validated" in failed


def test_review_state_rejects_unvalidated_ingest_review(tmp_path: Path) -> None:
    signoff = tmp_path / "signoff.json"
    ingest = tmp_path / "ingest.json"
    _write_json(signoff, _signoff_validator_payload())
    _write_json(ingest, _ingest_validator_payload(validated=False))

    report = build_phase3b_coordinate_validation_anchor119_row_domain_review_state(
        tmp_path,
        signoff_record_validator_path=signoff,
        ingest_review_record_validator_path=ingest,
    )

    assert report["status"]["review_state_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "ingest_review_payload_validated" in failed


def test_review_state_rejects_scope_runtime_or_proof_drift(tmp_path: Path) -> None:
    signoff = tmp_path / "signoff.json"
    ingest = tmp_path / "ingest.json"
    _write_json(signoff, _signoff_validator_payload(proof_source=True))
    _write_json(
        ingest,
        _ingest_validator_payload(
            runtime_enablement_allowed=True,
            scope="candidate=67x13, anchor_idx=118, joined_xy_block64_all_templates",
        ),
    )

    report = build_phase3b_coordinate_validation_anchor119_row_domain_review_state(
        tmp_path,
        signoff_record_validator_path=signoff,
        ingest_review_record_validator_path=ingest,
    )

    assert report["status"]["review_state_ready"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "ingest_scope_matches_locked_contract" in failed
    assert "signoff_safety_flags_default_off" in failed
    assert "ingest_safety_flags_default_off" in failed


def test_review_state_cli_writes_and_no_write_skips(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    signoff = tmp_path / "signoff.json"
    ingest = tmp_path / "ingest.json"
    output_dir = tmp_path / "out"
    _write_json(signoff, _signoff_validator_payload())
    _write_json(ingest, _ingest_validator_payload())
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_review_state.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--signoff-record-validator",
            str(signoff),
            "--ingest-review-record-validator",
            str(ingest),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "review_state_ready=True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--signoff-record-validator",
            str(signoff),
            "--ingest-review-record-validator",
            str(ingest),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "anchor119_row_domain_review_state_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_review_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["review_state_ready"] is True
    assert (output_dir / "anchor119_row_domain_review_state.md").exists()
    assert (output_dir / "anchor119_row_domain_review_state.txt").exists()
