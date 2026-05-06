from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_text,
)

CANDIDATE_KEY = "67x13"
ANCHOR_IDX = 119
FORMULATION_PROFILE = "joined_xy_block64_all_templates"
RECORD_IDENTITY = "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119"
TARGET_RECORD_TYPE = "reviewed_runtime_patch_signoff_record_v0"
INGEST_REVIEW_RECORD_TYPE = "reviewed_runtime_patch_ingest_review_record_v0"
SCOPE = (
    "candidate=67x13, anchor_idx=119, joined_xy_block64_all_templates, "
    "anchor119 fixed-anchor row-domain/count bridge"
)
HANDOFF_DIR = (
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/"
    "reviewer_record_handoff"
)
HANDOFF_PATH_SHAPE = (
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/"
    "reviewer_record_handoff/"
    "anchor119_row_domain_reviewed_runtime_patch_signoff_record_v0__candidate_67x13__anchor_119__"
    "reviewer_<reviewer_id>__reviewed_at_<reviewed_at_utc>.json"
)
HANDOFF_FILENAME_TOKENS = [
    "record_type_reviewed_runtime_patch_signoff_record_v0",
    "candidate_67x13",
    "anchor_119",
    "reviewer_<reviewer_id>",
    "reviewed_at_<reviewed_at_utc>",
]
CURRENT_STILL_BLOCKED_GATE_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
]
PACKET_STILL_BLOCKED_GATE_IDS = [
    "upstream_handoff_bundle_ready",
    "upstream_handoff_bundle_contract_compatible",
    "instruction_packet_contract_compatible",
    "instruction_packet_review_only_default_off_retained",
]
FUTURE_REMAINING_GATE_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
    "reviewer_signed_record_supplied_for_review",
    "reviewer_signed_record_validates_against_locked_contract",
    "separate_manual_ingest_review_approved",
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _candidate_json() -> dict:
    return {
        "key": CANDIDATE_KEY,
        "anchor_idx": ANCHOR_IDX,
        "formulation_profile": FORMULATION_PROFILE,
    }


def _contract_metadata(source: str) -> dict:
    return {
        "source": source,
        "review_only": True,
        "spec_only": True,
        "default_off": True,
        "runtime_precheck_enabled": False,
        "runtime_semantics_changed": False,
        "proof_source": False,
        "candidate_elimination_claim": False,
        "solver_invoked": False,
        "repo_side_review_state_updated": False,
    }


def _locked_target_review_state_json() -> dict:
    return {
        "review_state_kind": "repo_side_review_state",
        "tracked_field": "reviewed_runtime_patch_exists",
        "record_identity": RECORD_IDENTITY,
        "record_type": TARGET_RECORD_TYPE,
        "scope": SCOPE,
        "current_field_value": False,
        "proposed_field_value_if_approved": True,
    }


def _locked_handoff_json() -> dict:
    return {
        "handoff_format": "json",
        "handoff_dir": HANDOFF_DIR,
        "handoff_path_shape": HANDOFF_PATH_SHAPE,
        "handoff_filename_tokens": list(HANDOFF_FILENAME_TOKENS),
    }


def _expected_template_payload() -> dict:
    return {
        "record_type": INGEST_REVIEW_RECORD_TYPE,
        "review_state_kind": "repo_side_review_state",
        "tracked_field": "reviewed_runtime_patch_exists",
        "target_record_identity": RECORD_IDENTITY,
        "target_record_type": TARGET_RECORD_TYPE,
        "scope": SCOPE,
        "proposed_field_value_if_approved": True,
        "ingest_reviewer_id": "",
        "ingest_reviewed_at": "",
        "review_decision": "pending",
        "decision_notes": "",
        "reviewer_record_handoff_path": HANDOFF_PATH_SHAPE,
        "reviewer_record_validation_status": "pending_manual_validation",
        "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
        "required_reviewer_statement_ids": [
            "default_off_retained",
            "reserved_runtime_request_downgrades_to_advisory",
            "no_proof_source_promotion",
            "acceptance_refresh_required_before_enablement",
        ],
        "required_review_conclusion_ids": [
            "reviewer_signed_record_supplied_for_review",
            "reviewer_signed_record_validates_against_locked_contract",
            "separate_manual_ingest_review_approved",
            "repo_side_review_state_may_mark_reviewed_runtime_patch",
            "runtime_enablement_remains_blocked_after_review",
            "post_ingest_still_blocked_gate_ids_preserved",
        ],
        "review_conclusions": [
            {
                "conclusion_id": "reviewer_signed_record_supplied_for_review",
                "decision": "pending",
                "notes": "",
            },
            {
                "conclusion_id": "reviewer_signed_record_validates_against_locked_contract",
                "decision": "pending",
                "notes": "",
            },
            {
                "conclusion_id": "separate_manual_ingest_review_approved",
                "decision": "pending",
                "notes": "",
            },
            {
                "conclusion_id": "repo_side_review_state_may_mark_reviewed_runtime_patch",
                "decision": "pending",
                "notes": "",
            },
            {
                "conclusion_id": "runtime_enablement_remains_blocked_after_review",
                "decision": "pending",
                "notes": "",
            },
            {
                "conclusion_id": "post_ingest_still_blocked_gate_ids_preserved",
                "decision": "pending",
                "notes": "",
            },
        ],
        "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
        "post_ingest_still_blocked_gate_ids": [
            "production_acceptance_refresh_completed"
        ],
        "repo_side_review_state_updated": False,
        "reviewed_runtime_patch_exists": False,
        "runtime_enablement_allowed": False,
    }


def _synthetic_payload() -> dict:
    payload = _expected_template_payload()
    payload.update(
        {
            "ingest_reviewer_id": "synthetic_demo_reviewer_anchor119",
            "ingest_reviewed_at": "2026-04-24T12:00:00Z",
            "review_decision": "approved_for_repo_side_review_state_marking",
            "decision_notes": "Synthetic example only.",
            "reviewer_record_handoff_path": HANDOFF_PATH_SHAPE.replace(
                "<reviewer_id>", "synthetic_demo_reviewer_anchor119"
            ).replace("<reviewed_at_utc>", "2026-04-24T12-00-00Z"),
            "reviewer_record_validation_status": "validated_against_locked_contract",
            "review_conclusions": [
                {
                    "conclusion_id": conclusion_id,
                    "decision": "confirmed",
                    "notes": f"Synthetic reference only for {conclusion_id}.",
                }
                for conclusion_id in _expected_template_payload()[
                    "required_review_conclusion_ids"
                ]
            ],
        }
    )
    return payload


def _gate(gate_id: str, *, satisfied: bool, blocking: bool, detail: str) -> dict:
    return {
        "gate_id": gate_id,
        "satisfied": satisfied,
        "blocking": blocking,
        "detail": detail,
    }


def _operator_handoff_bundle_json() -> dict:
    return {
        "metadata": _contract_metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_operator_handoff_bundle_ready": True,
            "upstream_inputs_ready": True,
            "contract_compatible": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "ingest_review_operator_handoff_bundle": {
            "operator_target": {
                "operator_role": "future_manual_ingest_review_operator",
                "review_step_kind": "manual_ingest_review_handoff",
                "record_identity": RECORD_IDENTITY,
                "target_record_type": TARGET_RECORD_TYPE,
                "scope": SCOPE,
                "tracked_field": "reviewed_runtime_patch_exists",
                "review_state_kind": "repo_side_review_state",
                "proposed_field_value_if_approved": True,
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "authoritative_inputs": [
                {
                    "artifact_id": "ingest_review_operator_handoff_bundle",
                    "path": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_20260424/anchor119_row_domain_ingest_review_operator_handoff_bundle.json",
                    "ready": True,
                },
                {
                    "artifact_id": "ingest_review_record_validator",
                    "path": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/anchor119_row_domain_ingest_review_record_validator.json",
                    "ready": True,
                },
                {
                    "artifact_id": "ingest_review_record_example_bundle",
                    "path": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/anchor119_row_domain_ingest_review_record_example_bundle.json",
                    "ready": True,
                    "reference_only": True,
                },
            ],
            "locked_handoff_path_shape": {
                "handoff_format": "json",
                "handoff_dir": HANDOFF_DIR,
                "path_shape": HANDOFF_PATH_SHAPE,
                "handoff_filename_tokens": list(HANDOFF_FILENAME_TOKENS),
            },
            "validator_script_or_artifact_reference": {
                "artifact_path": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/anchor119_row_domain_ingest_review_record_validator.json",
                "builder_script_path": "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator.py",
                "validator_target": "future_completed_ingest_review_record_payload",
                "future_reviewer_record_validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
            },
            "example_bundle_reference": {
                "artifact_path": ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/anchor119_row_domain_ingest_review_record_example_bundle.json",
                "builder_script_path": "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle.py",
                "synthetic_example_is_reference_only": True,
            },
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "proof_source": False,
                "candidate_elimination_claim": False,
                "solver_invoked": False,
                "execution_authorized": False,
            },
            "disallowed_actions": [
                "Do not update repo-side review state.",
                "Do not claim candidate elimination.",
            ],
        },
        "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
        "gates": [
            _gate(
                "reviewed_runtime_patch_exists",
                satisfied=False,
                blocking=True,
                detail="Reviewed runtime patch does not exist yet.",
            ),
            _gate(
                "production_acceptance_refresh_completed",
                satisfied=False,
                blocking=True,
                detail="Production acceptance refresh remains incomplete.",
            ),
            _gate(
                "reviewer_signed_record_supplied_for_review",
                satisfied=False,
                blocking=True,
                detail="Reviewer-signed record has not been supplied yet.",
            ),
            _gate(
                "reviewer_signed_record_validates_against_locked_contract",
                satisfied=False,
                blocking=True,
                detail="Reviewer-signed record has not been manually validated yet.",
            ),
            _gate(
                "separate_manual_ingest_review_approved",
                satisfied=False,
                blocking=True,
                detail="Separate manual ingest review approval has not happened yet.",
            ),
        ],
    }


def _validator_json() -> dict:
    expected_template = _expected_template_payload()
    return {
        "metadata": _contract_metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_record_validator_ready": True,
            "manual_ingest_review_record_provided": False,
            "manual_ingest_review_record_validated": False,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "ingest_review_record_validator": {
            "validator_target": "future_completed_ingest_review_record_payload",
            "locked_target_review_state": _locked_target_review_state_json(),
            "locked_reviewer_record_handoff": _locked_handoff_json(),
            "locked_reviewer_record_validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
            "expected_template_payload": expected_template,
            "required_review_conclusions": [
                {
                    "conclusion_id": conclusion_id,
                    "required": True,
                    "template_value": "pending",
                    "detail": f"Required conclusion {conclusion_id}.",
                }
                for conclusion_id in expected_template["required_review_conclusion_ids"]
            ],
            "blocked_gate_contract": {
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": [
                    "production_acceptance_refresh_completed"
                ],
            },
            "validator_rules": {
                "required_fields": [
                    {
                        "field": field,
                        "required": True,
                        "template_value": value,
                        "validation_rule": "must_be_present",
                    }
                    for field, value in expected_template.items()
                ],
                "required_reviewer_statement_ids": {
                    "field": "required_reviewer_statement_ids",
                    "required": True,
                    "required_ids": list(expected_template["required_reviewer_statement_ids"]),
                },
                "required_review_conclusion_ids": {
                    "field": "required_review_conclusion_ids",
                    "required": True,
                    "required_ids": list(expected_template["required_review_conclusion_ids"]),
                },
                "review_conclusions": {
                    "field": "review_conclusions",
                    "required": True,
                    "required_ids": list(expected_template["required_review_conclusion_ids"]),
                },
            },
        },
        "still_blocked_gate_ids": list(FUTURE_REMAINING_GATE_IDS),
        "gates": [
            _gate(
                gate_id,
                satisfied=False,
                blocking=True,
                detail=f"{gate_id} remains blocked.",
            )
            for gate_id in FUTURE_REMAINING_GATE_IDS
        ],
    }


def _example_bundle_json() -> dict:
    return {
        "metadata": _contract_metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_record_example_bundle_ready": True,
            "synthetic_ingest_review_record_example_generated": True,
            "synthetic_ingest_review_record_example_validated": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "ingest_review_record_example_bundle": {
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "example_kind": "synthetic_completed_ingest_review_record_payload_demo",
            "actual_human_review_record": False,
            "applied_repo_state_update": False,
            "locked_target_review_state": _locked_target_review_state_json(),
            "locked_reviewer_record_handoff": _locked_handoff_json(),
            "validator_target": "future_completed_ingest_review_record_payload",
            "synthetic_completed_ingest_review_record_payload": _synthetic_payload(),
            "replayed_validation_summary": {
                "manual_ingest_review_record_validation_status": "passed",
            },
            "replay_instructions": {
                "validator_script": "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator.py",
                "validator_target": "future_completed_ingest_review_record_payload",
            },
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
        },
        "still_blocked_gate_ids": list(FUTURE_REMAINING_GATE_IDS),
        "gates": [
            _gate(
                gate_id,
                satisfied=False,
                blocking=True,
                detail=f"{gate_id} remains blocked.",
            )
            for gate_id in FUTURE_REMAINING_GATE_IDS
        ],
    }


def _write_upstream_fixtures(project_root: Path) -> dict[str, Path]:
    operator_handoff_bundle_path = (
        project_root
        / ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_20260424/"
        / "anchor119_row_domain_ingest_review_operator_handoff_bundle.json"
    )
    validator_path = (
        project_root
        / ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/"
        / "anchor119_row_domain_ingest_review_record_validator.json"
    )
    example_bundle_path = (
        project_root
        / ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/"
        / "anchor119_row_domain_ingest_review_record_example_bundle.json"
    )
    _write_json(operator_handoff_bundle_path, _operator_handoff_bundle_json())
    _write_json(validator_path, _validator_json())
    _write_json(example_bundle_path, _example_bundle_json())
    return {
        "operator_handoff_bundle": operator_handoff_bundle_path,
        "validator": validator_path,
        "example_bundle": example_bundle_path,
    }


def test_anchor119_row_domain_ingest_review_instruction_packet_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet(
        project_root,
        ingest_review_operator_handoff_bundle_path=paths["operator_handoff_bundle"],
        ingest_review_record_validator_path=paths["validator"],
        ingest_review_record_example_bundle_path=paths["example_bundle"],
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["ingest_review_instruction_packet_ready"] is True
    assert report["status"]["upstream_handoff_bundle_ready"] is True
    assert report["status"]["contract_compatible"] is True
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["missing_ready_gate_ids"] == []
    packet = report["ingest_review_instruction_packet"]
    assert packet["packet_target"]["record_identity"] == RECORD_IDENTITY
    assert packet["packet_target"]["validator_target"] == (
        "future_completed_ingest_review_record_payload"
    )
    assert packet["packet_target"]["execution_authorized"] is False
    open_these_first = packet["open_these_first"]
    assert [entry["artifact_id"] for entry in open_these_first] == [
        "ingest_review_operator_handoff_bundle",
        "ingest_review_record_validator",
        "ingest_review_record_example_bundle",
    ]
    validator_reference = packet["validator_reference"]
    assert validator_reference["validator_target"] == (
        "future_completed_ingest_review_record_payload"
    )
    assert (
        validator_reference["expected_completed_ingest_review_record_shape"][
            "reviewer_record_handoff_path"
        ]
        == HANDOFF_PATH_SHAPE
    )
    example_reference = packet["example_reference"]
    assert example_reference["synthetic_example_is_reference_only"] is True
    locked_handoff_path_shape = packet["locked_handoff_path_shape"]
    assert locked_handoff_path_shape["path_shape"] == HANDOFF_PATH_SHAPE
    preserved_state = packet["preserved_state_assertions"]
    assert preserved_state["repo_side_review_state_updated"] is False
    assert preserved_state["reviewed_runtime_patch_exists"] is False
    assert preserved_state["runtime_enablement_allowed"] is False
    assert preserved_state["execution_authorized"] is False
    assert report["still_blocked_gate_ids"] == FUTURE_REMAINING_GATE_IDS
    failed_checks = [check for check in report["checks"] if check["status"] == "fail"]
    assert failed_checks == []
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_text(
            report
        )
    )
    assert "Ingest Review Instruction Packet" in markdown
    assert "Synthetic example is reference only" in markdown
    assert "ingest_review_instruction_packet_ready=True" in text


def test_anchor119_row_domain_ingest_review_instruction_packet_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)
    paths["example_bundle"].unlink()

    report = build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet(
        project_root,
        ingest_review_operator_handoff_bundle_path=paths["operator_handoff_bundle"],
        ingest_review_record_validator_path=paths["validator"],
        ingest_review_record_example_bundle_path=paths["example_bundle"],
    )

    assert report["status"]["ingest_review_instruction_packet_ready"] is False
    assert report["status"]["contract_compatible"] is False
    assert "ingest_review_record_example_bundle_present" in report["status"][
        "missing_ready_gate_ids"
    ]
    assert "ingest_review_record_example_bundle_ready" in report["status"][
        "missing_ready_gate_ids"
    ]
    check_by_id = {check["check_id"]: check for check in report["checks"]}
    assert check_by_id["ingest_review_record_example_bundle_present"]["status"] == "fail"
    assert check_by_id["ingest_review_record_example_bundle_ready"]["status"] == "fail"


def test_anchor119_row_domain_ingest_review_instruction_packet_cli_write_and_no_write(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)
    output_dir = tmp_path / "out"
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet.py"
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(tmp_path / "pycache")

    no_write = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--operator-handoff-bundle",
            str(paths["operator_handoff_bundle"]),
            "--ingest-review-record-validator",
            str(paths["validator"]),
            "--ingest-review-record-example-bundle",
            str(paths["example_bundle"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "ingest_review_instruction_packet_ready=True" in no_write.stdout
    assert "contract_compatible=True" in no_write.stdout
    assert "locked_handoff_path_shape=" + HANDOFF_PATH_SHAPE in no_write.stdout
    assert not output_dir.exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--operator-handoff-bundle",
            str(paths["operator_handoff_bundle"]),
            "--ingest-review-record-validator",
            str(paths["validator"]),
            "--ingest-review-record-example-bundle",
            str(paths["example_bundle"]),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "anchor119_row_domain_ingest_review_instruction_packet_json=" in write_run.stdout
    json_path = output_dir / "anchor119_row_domain_ingest_review_instruction_packet.json"
    md_path = output_dir / "anchor119_row_domain_ingest_review_instruction_packet.md"
    txt_path = output_dir / "anchor119_row_domain_ingest_review_instruction_packet.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()
    written_report = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_report["status"]["ingest_review_instruction_packet_ready"] is True
