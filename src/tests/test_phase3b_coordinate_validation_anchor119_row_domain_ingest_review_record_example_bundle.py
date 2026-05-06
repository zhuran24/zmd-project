from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_text,
)
from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator,
)

STATEMENT_IDS = [
    "default_off_retained",
    "reserved_runtime_request_downgrades_to_advisory",
    "no_proof_source_promotion",
    "acceptance_refresh_required_before_enablement",
]
CURRENT_STILL_BLOCKED_GATE_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
]
POST_INGEST_STILL_BLOCKED_GATE_IDS = [
    "production_acceptance_refresh_completed",
]
REQUIRED_REVIEW_CONCLUSION_IDS = [
    "reviewer_signed_record_supplied_for_review",
    "reviewer_signed_record_validates_against_locked_contract",
    "separate_manual_ingest_review_approved",
    "repo_side_review_state_may_mark_reviewed_runtime_patch",
    "runtime_enablement_remains_blocked_after_review",
    "post_ingest_still_blocked_gate_ids_preserved",
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _ingest_review_record_scaffold_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1",
            "default_off": True,
            "review_only": True,
            "spec_only": True,
            "proof_source": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "ingest_review_record_scaffold_ready": True,
            "manual_ingest_review_record_completed": False,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "ingest_review_record_scaffold": {
            "record_type": "reviewed_runtime_patch_ingest_review_record_v0",
            "locked_target_review_state": {
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
                "current_field_value": False,
                "proposed_field_value_if_approved": True,
            },
            "locked_reviewer_record_handoff": {
                "handoff_format": "json",
                "handoff_dir": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff",
                "handoff_path_shape": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff/anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119__reviewer_<reviewer_id>__reviewed_at_<reviewed_at_utc>.json",
                "handoff_filename_tokens": [
                    "record_type_reviewed_runtime_patch_signoff_record_v0",
                    "candidate_67x13",
                    "anchor_119",
                    "reviewer_<reviewer_id>",
                    "reviewed_at_<reviewed_at_utc>",
                ],
            },
            "validator_contract_reference": {
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "required_record_fields": [
                    {"field": "record_type", "required": True},
                    {"field": "reviewer_id", "required": True},
                    {"field": "reviewed_at", "required": True},
                ],
            },
            "required_review_conclusions": [
                {
                    "conclusion_id": conclusion_id,
                    "required": True,
                    "template_value": "pending",
                    "detail": f"Resolve {conclusion_id} during future manual ingest review.",
                }
                for conclusion_id in REQUIRED_REVIEW_CONCLUSION_IDS
            ],
            "preserved_blocked_gates": {
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
                "runtime_enablement_allowed_after_review": False,
            },
            "ingest_review_record_template": {
                "record_type": "reviewed_runtime_patch_ingest_review_record_v0",
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "target_record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "target_record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
                "proposed_field_value_if_approved": True,
                "ingest_reviewer_id": "",
                "ingest_reviewed_at": "",
                "review_decision": "pending",
                "decision_notes": "",
                "reviewer_record_handoff_path": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff/anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119__reviewer_<reviewer_id>__reviewed_at_<reviewed_at_utc>.json",
                "reviewer_record_validation_status": "pending_manual_validation",
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "required_review_conclusion_ids": list(REQUIRED_REVIEW_CONCLUSION_IDS),
                "review_conclusions": [
                    {
                        "conclusion_id": conclusion_id,
                        "decision": "pending",
                        "notes": "",
                    }
                    for conclusion_id in REQUIRED_REVIEW_CONCLUSION_IDS
                ],
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
        },
        "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch record does not exist yet.",
            },
            {
                "gate_id": "production_acceptance_refresh_completed",
                "satisfied": False,
                "blocking": True,
                "detail": "Acceptance refresh still has not been run.",
            },
        ],
    }


def _reviewed_runtime_patch_ingest_gate_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_reviewed_runtime_patch_ingest_gate_v1",
            "default_off": True,
            "review_only": True,
            "spec_only": True,
            "proof_source": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "reviewed_runtime_patch_ingest_gate_ready": True,
            "future_review_state_marking_prerequisites_met": False,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "missing_prerequisite_gate_ids": list(REQUIRED_REVIEW_CONCLUSION_IDS[:3]),
        },
        "reviewed_runtime_patch_ingest_gate": {
            "repo_side_review_state_target": {
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119",
                "record_type": "reviewed_runtime_patch_signoff_record_v0",
                "scope": "candidate=67x13, anchor_idx=119",
            },
            "locked_reviewer_record_handoff": {
                "handoff_format": "json",
                "handoff_dir": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff",
                "handoff_path_shape": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/reviewer_record_handoff/anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119__reviewer_<reviewer_id>__reviewed_at_<reviewed_at_utc>.json",
                "handoff_filename_tokens": [
                    "record_type_reviewed_runtime_patch_signoff_record_v0",
                    "candidate_67x13",
                    "anchor_119",
                    "reviewer_<reviewer_id>",
                    "reviewed_at_<reviewed_at_utc>",
                ],
            },
            "ingest_review_contract": {
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
                "required_reviewer_statement_ids": list(STATEMENT_IDS),
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
            },
        },
        "gates": [
            {
                "gate_id": "reviewer_signed_record_supplied_for_review",
                "satisfied": False,
                "blocking": True,
                "detail": "A future reviewer-signed record must be supplied before manual ingest review can mark the patch as reviewed.",
            },
            {
                "gate_id": "reviewer_signed_record_validates_against_locked_contract",
                "satisfied": False,
                "blocking": True,
                "detail": "A future reviewer-signed record must validate against the locked contract before manual ingest review can mark the patch as reviewed.",
            },
            {
                "gate_id": "separate_manual_ingest_review_approved",
                "satisfied": False,
                "blocking": True,
                "detail": "A separate future review must explicitly approve the repo-side review-state update.",
            },
        ],
    }


def _signoff_record_validator_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_signoff_record_validator_v1",
            "default_off": True,
            "spec_only": True,
            "proof_source": False,
            "solver_invoked": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "signoff_record_validator_ready": True,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "signoff_record_validator": {
            "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
            "target_record_type": "reviewed_runtime_patch_signoff_record_v0",
            "scope": "candidate=67x13, anchor_idx=119",
            "required_reviewer_statement_ids": list(STATEMENT_IDS),
            "validator_rules": {
                "required_fields": [
                    {"field": "record_type", "required": True},
                    {"field": "reviewer_id", "required": True},
                    {"field": "reviewed_at", "required": True},
                ],
                "agreed_statement_ids": {
                    "field": "agreed_statement_ids",
                    "required": True,
                    "required_ids": list(STATEMENT_IDS),
                },
                "still_blocked_gate_ids": {
                    "field": "still_blocked_gate_ids",
                    "required": True,
                    "required_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                },
            },
            "actual_record_validation": {
                "record_payload_provided": False,
                "record_payload_validated": False,
                "validation_status": "not_run",
            },
        },
        "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch record does not exist yet.",
            },
            {
                "gate_id": "production_acceptance_refresh_completed",
                "satisfied": False,
                "blocking": True,
                "detail": "Acceptance refresh still has not been run.",
            },
        ],
    }


def _build_validator_artifact(
    project_root: Path,
    *,
    ingest_review_record_scaffold_path: Path,
    reviewed_runtime_patch_ingest_gate_path: Path,
    signoff_record_validator_path: Path,
) -> dict:
    return (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator(
            project_root,
            ingest_review_record_scaffold_path=ingest_review_record_scaffold_path,
            reviewed_runtime_patch_ingest_gate_path=(
                reviewed_runtime_patch_ingest_gate_path
            ),
            signoff_record_validator_path=signoff_record_validator_path,
        )
    )


def _build_example_bundle_fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    project_root = tmp_path / "project"
    scaffold_path = tmp_path / "ingest_review_record_scaffold.json"
    ingest_gate_path = tmp_path / "reviewed_runtime_patch_ingest_gate.json"
    signoff_path = tmp_path / "signoff_record_validator.json"
    validator_path = tmp_path / "ingest_review_record_validator.json"

    _write_json(scaffold_path, _ingest_review_record_scaffold_json())
    _write_json(ingest_gate_path, _reviewed_runtime_patch_ingest_gate_json())
    _write_json(signoff_path, _signoff_record_validator_json())
    _write_json(
        validator_path,
        _build_validator_artifact(
            project_root,
            ingest_review_record_scaffold_path=scaffold_path,
            reviewed_runtime_patch_ingest_gate_path=ingest_gate_path,
            signoff_record_validator_path=signoff_path,
        ),
    )
    return project_root, scaffold_path, ingest_gate_path, signoff_path, validator_path


def test_anchor119_row_domain_ingest_review_record_example_bundle_ready(
    tmp_path: Path,
) -> None:
    (
        project_root,
        scaffold_path,
        _ingest_gate_path,
        _signoff_path,
        validator_path,
    ) = _build_example_bundle_fixture_paths(tmp_path)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle(
            project_root,
            ingest_review_record_scaffold_path=scaffold_path,
            ingest_review_record_validator_path=validator_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["repo_side_review_state_updated"] is False
    assert report["status"]["ingest_review_record_example_bundle_ready"] is True
    assert report["status"]["synthetic_ingest_review_record_example_generated"] is True
    assert report["status"]["synthetic_ingest_review_record_example_validated"] is True
    assert report["status"]["synthetic_ingest_review_record_validation_status"] == "passed"
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["recommended_next_step"] == (
        "review_example_bundle_only_keep_actual_manual_ingest_review_separate"
    )
    bundle = report["ingest_review_record_example_bundle"]
    assert bundle["review_only"] is True
    assert bundle["default_off"] is True
    assert bundle["actual_human_review_record"] is False
    assert bundle["applied_repo_state_update"] is False
    assert "Synthetic example/demo payload only" in bundle["bundle_notice"]
    payload = bundle["synthetic_completed_ingest_review_record_payload"]
    assert payload["ingest_reviewer_id"] == "synthetic_demo_reviewer_anchor119"
    assert payload["ingest_reviewed_at"] == "2026-04-24T12:00:00Z"
    assert payload["review_decision"] == "approved_for_repo_side_review_state_marking"
    assert (
        payload["reviewer_record_validation_status"]
        == "validated_against_locked_contract"
    )
    assert payload["repo_side_review_state_updated"] is False
    assert payload["reviewed_runtime_patch_exists"] is False
    assert payload["runtime_enablement_allowed"] is False
    replayed_validation = bundle["replayed_validation_summary"]
    assert replayed_validation["ingest_review_record_validator_ready"] is True
    assert replayed_validation["manual_ingest_review_record_provided"] is True
    assert replayed_validation["manual_ingest_review_record_validated"] is True
    assert replayed_validation["manual_ingest_review_record_validation_status"] == "passed"
    assert replayed_validation["record_payload_path"] == "synthetic_example_payload.json"
    assert replayed_validation["failed_rule_count"] == 0
    assert replayed_validation["passed_rule_count"] > 0
    assert "review-only/default-off" in replayed_validation["detail"]
    assert set(CURRENT_STILL_BLOCKED_GATE_IDS).issubset(
        set(report["still_blocked_gate_ids"])
    )
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_text(
            report
        )
    )
    assert "Ingest Review Record Example Bundle" in markdown
    assert "Synthetic Example Payload" in markdown
    assert "Replayed Validation Summary" in markdown
    assert (
        "ingest_review_record_example_bundle_ready=True" in text
    )
    assert (
        "synthetic_ingest_review_record_example_validated=True" in text
    )


def test_anchor119_row_domain_ingest_review_record_example_bundle_fails_if_replay_upstream_missing(
    tmp_path: Path,
) -> None:
    (
        project_root,
        scaffold_path,
        ingest_gate_path,
        _signoff_path,
        validator_path,
    ) = _build_example_bundle_fixture_paths(tmp_path)
    ingest_gate_path.unlink()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle(
            project_root,
            ingest_review_record_scaffold_path=scaffold_path,
            ingest_review_record_validator_path=validator_path,
        )
    )

    assert report["status"]["ingest_review_record_example_bundle_ready"] is False
    assert report["status"]["synthetic_ingest_review_record_example_generated"] is True
    assert report["status"]["synthetic_ingest_review_record_example_validated"] is False
    assert report["status"]["synthetic_ingest_review_record_validation_status"] in {
        "failed",
        "passed",
    }
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "replayed_validator_ready" in failed
    replayed_validation = report["ingest_review_record_example_bundle"][
        "replayed_validation_summary"
    ]
    assert replayed_validation["ingest_review_record_validator_ready"] is False
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False


def test_anchor119_row_domain_ingest_review_record_example_bundle_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    (
        project_root,
        scaffold_path,
        _ingest_gate_path,
        _signoff_path,
        validator_path,
    ) = _build_example_bundle_fixture_paths(tmp_path)
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle.py"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--ingest-review-record-scaffold",
            str(scaffold_path),
            "--ingest-review-record-validator",
            str(validator_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert (
        "phase3b anchor119 row-domain ingest review record example bundle"
        in no_write.stdout
    )
    assert "ingest_review_record_example_bundle_ready=True" in no_write.stdout
    assert "synthetic_ingest_review_record_example_generated=True" in no_write.stdout
    assert "synthetic_ingest_review_record_example_validated=True" in no_write.stdout
    assert "synthetic_ingest_review_record_validation_status=passed" in no_write.stdout
    assert "runtime_enablement_allowed=False" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--ingest-review-record-scaffold",
            str(scaffold_path),
            "--ingest-review-record-validator",
            str(validator_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_ingest_review_record_example_bundle_json=" in write.stdout
    payload = json.loads(
        (
            output_dir
            / "anchor119_row_domain_ingest_review_record_example_bundle.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["ingest_review_record_example_bundle_ready"] is True
    assert payload["status"]["synthetic_ingest_review_record_example_generated"] is True
    assert payload["status"]["synthetic_ingest_review_record_example_validated"] is True
    assert payload["status"]["synthetic_ingest_review_record_validation_status"] == "passed"
    assert payload["status"]["reviewed_runtime_patch_exists"] is False
    assert payload["status"]["runtime_enablement_allowed"] is False
    assert (
        output_dir / "anchor119_row_domain_ingest_review_record_example_bundle.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_ingest_review_record_example_bundle.txt"
    ).exists()
