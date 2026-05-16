from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_review_record_scaffold import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _metadata(source: str, *, acceptance_executed: bool = False) -> dict:
    return {
        "source": source,
        "spec_only": True,
        "review_only": True,
        "default_off": True,
        "runtime_precheck_enabled": False,
        "runtime_semantics_changed": False,
        "proof_source": False,
        "candidate_elimination_claim": False,
        "solver_invoked": False,
        "acceptance_executed": acceptance_executed,
    }


def _candidate() -> dict:
    return {
        "key": "67x13",
        "anchor_idx": 119,
        "formulation_profile": "joined_xy_block64_all_templates",
    }


def _locked_acceptance_command() -> str:
    return (
        "python temp_scripts/benchmark_parallelism.py --suite-kind "
        "production-acceptance --suite-output "
        ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    )


def _locked_acceptance_result_path() -> str:
    return ".codex_test_logs/phase3b/production_acceptance_after_change.json"


def _default_runner() -> str:
    return "scripts/run_prod_4x4_normal.ps1"


def _acceptance_authorization_review_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_bundle_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_authorization_review_bundle_ready": True,
            "future_execution_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "reviewed_runtime_patch_exists": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_review_bundle": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "review_only": True,
            "default_off": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "production_profile_locked": True,
                "default_production_runner": _default_runner(),
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                "command_matches_result_path": True,
            },
            "reviewed_runtime_patch_state": {
                "required_reviewer_statement_ids": [
                    "default_off_retained",
                    "acceptance_refresh_required_before_enablement",
                ]
            },
            "required_review_conclusions_before_future_execution_authorization_review": [
                {
                    "conclusion_id": "locked_prod_4x4_normal_target_confirmed",
                    "required": True,
                    "currently_satisfied": True,
                    "detail": "Locked prod_4x4_normal target is explicit.",
                },
                {
                    "conclusion_id": "reviewed_runtime_patch_exists",
                    "required": True,
                    "currently_satisfied": False,
                    "detail": "Reviewed runtime patch signoff record is still absent.",
                },
            ],
            "current_missing_prerequisites_before_future_execution_authorization_review": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "required_state": True,
                    "current_value": False,
                    "detail": "Reviewed runtime patch signoff record is still absent.",
                }
            ],
            "future_authorization_review_record_template": {
                "record_type": "acceptance_execution_authorization_review_record_v0",
                "reviewer_id": "",
                "reviewed_at": "",
                "verdict": "pending",
                "authorization_granted": False,
                "runtime_enablement_allowed": False,
                "acceptance_executed": False,
                "locked_execution_target": {
                    "production_profile_id": "prod_4x4_normal",
                    "default_production_runner": _default_runner(),
                    "exact_future_acceptance_command": _locked_acceptance_command(),
                    "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                },
                "required_conclusion_ids": [
                    "locked_prod_4x4_normal_target_confirmed",
                    "reviewed_runtime_patch_exists",
                ],
                "required_runtime_patch_statement_ids": [
                    "default_off_retained",
                    "acceptance_refresh_required_before_enablement",
                ],
                "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
                "notes": "",
            },
        },
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch signoff record is still absent.",
            }
        ],
    }


def _acceptance_execution_gate_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_execution_gate_ready": True,
            "acceptance_execution_authorization_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "reviewed_runtime_patch_exists": False,
            "acceptance_executed": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_execution_gate": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "does_not_authorize_execution": True,
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "default_production_runner": _default_runner(),
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
            },
        },
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch signoff record is still absent.",
            }
        ],
    }


def _acceptance_result_validator_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_result_validator_ready": True,
            "runtime_enablement_allowed": False,
            "acceptance_result_validation_performed": False,
            "acceptance_result_validation_passed": False,
        },
        "acceptance_result_validator": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "expected_result_path": _locked_acceptance_result_path(),
            "future_validation_checklist": [
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "required": True,
                    "detail": "Keep runtime_enablement_allowed=false during any future validation.",
                },
                {
                    "checklist_id": "use_locked_acceptance_result_path",
                    "required": True,
                    "detail": "Validate only the locked future result path.",
                },
            ],
        },
        "result_validation": {
            "acceptance_result_provided": False,
            "validation_performed": False,
            "validation_passed": False,
            "summary": "No real acceptance result JSON was provided.",
        },
    }


def test_anchor119_row_domain_acceptance_authorization_review_record_scaffold_ready(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    validator_path = tmp_path / "acceptance_result_validator.json"
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(validator_path, _acceptance_result_validator_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold(
            repo_root,
            acceptance_authorization_review_bundle_path=bundle_path,
            acceptance_execution_gate_path=gate_path,
            acceptance_result_validator_path=validator_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_v1"
    )
    assert report["status"]["acceptance_authorization_review_record_scaffold_ready"] is True
    assert (
        report["status"]["future_manual_authorization_review_prerequisites_met"] is False
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    assert report["status"]["authorization_review_completed"] is False
    assert report["status"]["missing_prerequisite_gate_ids"] == [
        "reviewed_runtime_patch_exists"
    ]
    scaffold = report["acceptance_authorization_review_record_scaffold"]
    payload = scaffold["scaffolded_authorization_review_record_payload"]
    assert (
        scaffold["locked_execution_target"]["production_profile_id"] == "prod_4x4_normal"
    )
    assert (
        scaffold["locked_execution_target"]["exact_future_acceptance_command"]
        == _locked_acceptance_command()
    )
    assert (
        scaffold["locked_execution_target"]["exact_future_acceptance_result_path"]
        == _locked_acceptance_result_path()
    )
    assert payload["record_type"] == "acceptance_execution_authorization_review_record_v0"
    assert payload["verdict"] == "pending"
    assert payload["authorization_granted"] is False
    assert payload["runtime_enablement_allowed"] is False
    assert payload["acceptance_executed"] is False
    assert payload["missing_prerequisite_gate_ids"] == [
        "reviewed_runtime_patch_exists"
    ]
    assert [entry["conclusion_id"] for entry in scaffold["required_review_conclusions"]] == [
        "locked_prod_4x4_normal_target_confirmed",
        "reviewed_runtime_patch_exists",
    ]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold_text(
            report
        )
    )
    assert "Acceptance Authorization Review Record Scaffold" in markdown
    assert "not an actual acceptance-authorization review record" in markdown
    assert (
        "acceptance_authorization_review_record_scaffold_ready=True" in text
    )


def test_anchor119_row_domain_acceptance_authorization_review_record_scaffold_fails_if_upstream_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_scaffold(
            repo_root,
            acceptance_authorization_review_bundle_path=bundle_path,
            acceptance_execution_gate_path=gate_path,
            acceptance_result_validator_path=tmp_path
            / "missing_acceptance_result_validator.json",
        )
    )

    assert report["status"]["acceptance_authorization_review_record_scaffold_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "acceptance_result_validator_present" in failed


def test_anchor119_row_domain_acceptance_authorization_review_record_scaffold_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    bundle_path = tmp_path / "acceptance_authorization_review_bundle.json"
    gate_path = tmp_path / "acceptance_execution_gate.json"
    validator_path = tmp_path / "acceptance_result_validator.json"
    output_dir = tmp_path / "out"
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(validator_path, _acceptance_result_validator_json())

    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_acceptance_authorization_review_record_scaffold.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-authorization-review-bundle",
            str(bundle_path),
            "--acceptance-execution-gate",
            str(gate_path),
            "--acceptance-result-validator",
            str(validator_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert (
        "phase3b anchor119 row-domain acceptance authorization review record scaffold"
        in no_write.stdout
    )
    assert "authorization_review_completed=False" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-authorization-review-bundle",
            str(bundle_path),
            "--acceptance-execution-gate",
            str(gate_path),
            "--acceptance-result-validator",
            str(validator_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert (
        "anchor119_row_domain_acceptance_authorization_review_record_scaffold_json="
        in write.stdout
    )
    payload = json.loads(
        (
            output_dir
            / "anchor119_row_domain_acceptance_authorization_review_record_scaffold.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        payload["status"]["acceptance_authorization_review_record_scaffold_ready"] is True
    )
    assert payload["status"]["acceptance_execution_authorized"] is False
    assert (
        output_dir
        / "anchor119_row_domain_acceptance_authorization_review_record_scaffold.md"
    ).exists()
    assert (
        output_dir
        / "anchor119_row_domain_acceptance_authorization_review_record_scaffold.txt"
    ).exists()
