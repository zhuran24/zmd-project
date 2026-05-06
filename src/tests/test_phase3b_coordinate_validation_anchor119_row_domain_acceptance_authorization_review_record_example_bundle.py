from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_text,
)
from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _metadata(source: str) -> dict:
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
        "acceptance_executed": False,
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


def _acceptance_authorization_review_record_scaffold_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_record_scaffold_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_authorization_review_record_scaffold_ready": True,
            "future_manual_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "authorization_review_completed": False,
            "reviewed_runtime_patch_exists": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_review_record_scaffold": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "review_only": True,
            "default_off": True,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "authorization_review_completed": False,
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "production_profile_locked": True,
                "default_production_runner": _default_runner(),
                "default_production_runner_locked": True,
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_command_locked": True,
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                "exact_future_acceptance_result_path_locked": True,
                "command_matches_result_path": True,
            },
            "required_record_fields": [
                {
                    "field": "record_type",
                    "required": True,
                    "template_value": "acceptance_execution_authorization_review_record_v0",
                },
                {
                    "field": "reviewer_id",
                    "required": True,
                    "template_value": "",
                },
                {
                    "field": "reviewed_at",
                    "required": True,
                    "template_value": "",
                },
                {
                    "field": "verdict",
                    "required": True,
                    "template_value": "pending",
                },
                {
                    "field": "authorization_granted",
                    "required": True,
                    "template_value": False,
                },
                {
                    "field": "runtime_enablement_allowed",
                    "required": True,
                    "template_value": False,
                },
                {
                    "field": "acceptance_executed",
                    "required": True,
                    "template_value": False,
                },
                {
                    "field": "locked_execution_target",
                    "required": True,
                    "template_value": {
                        "production_profile_id": "prod_4x4_normal",
                        "default_production_runner": _default_runner(),
                        "exact_future_acceptance_command": _locked_acceptance_command(),
                        "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
                    },
                },
                {
                    "field": "required_conclusion_ids",
                    "required": True,
                    "template_value": [
                        "locked_prod_4x4_normal_target_confirmed",
                        "reviewed_runtime_patch_exists",
                    ],
                },
                {
                    "field": "required_runtime_patch_statement_ids",
                    "required": True,
                    "template_value": [
                        "default_off_retained",
                        "acceptance_refresh_required_before_enablement",
                    ],
                },
                {
                    "field": "missing_prerequisite_gate_ids",
                    "required": True,
                    "template_value": ["reviewed_runtime_patch_exists"],
                },
                {
                    "field": "notes",
                    "required": True,
                    "template_value": "",
                },
            ],
            "required_review_conclusions": [
                {
                    "conclusion_id": "locked_prod_4x4_normal_target_confirmed",
                    "required": True,
                    "currently_satisfied": True,
                },
                {
                    "conclusion_id": "reviewed_runtime_patch_exists",
                    "required": True,
                    "currently_satisfied": False,
                },
            ],
            "required_runtime_patch_statement_ids": [
                "default_off_retained",
                "acceptance_refresh_required_before_enablement",
            ],
            "missing_prerequisites": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "required_state": True,
                    "current_value": False,
                }
            ],
            "future_validation_checklist": [
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "required": True,
                }
            ],
            "scaffolded_authorization_review_record_payload": {
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
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch signoff record is still absent.",
            }
        ],
    }


def _acceptance_authorization_review_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_bundle_v1"
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
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_execution_gate_v1"
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
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_result_validator_v1",
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "acceptance_executed": False,
        },
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
        },
        "result_validation": {
            "acceptance_result_provided": False,
            "validation_performed": False,
            "validation_passed": False,
            "summary": "No real acceptance result JSON was provided.",
        },
    }


def _build_ready_upstream_artifacts(base_dir: Path) -> tuple[Path, Path]:
    project_root = base_dir / "project"
    scaffold_path = base_dir / "acceptance_authorization_review_record_scaffold.json"
    bundle_path = base_dir / "acceptance_authorization_review_bundle.json"
    gate_path = base_dir / "acceptance_execution_gate.json"
    result_validator_path = base_dir / "acceptance_result_validator.json"
    validator_path = base_dir / "acceptance_authorization_review_record_validator.json"

    _write_json(scaffold_path, _acceptance_authorization_review_record_scaffold_json())
    _write_json(bundle_path, _acceptance_authorization_review_bundle_json())
    _write_json(gate_path, _acceptance_execution_gate_json())
    _write_json(result_validator_path, _acceptance_result_validator_json())

    validator_report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator(
            project_root,
            acceptance_authorization_review_record_scaffold_path=scaffold_path,
            acceptance_authorization_review_bundle_path=bundle_path,
            acceptance_execution_gate_path=gate_path,
            acceptance_result_validator_path=result_validator_path,
        )
    )
    _write_json(validator_path, validator_report)
    return scaffold_path, validator_path


def test_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    scaffold_path, validator_path = _build_ready_upstream_artifacts(tmp_path)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle(
            project_root,
            acceptance_authorization_review_record_scaffold_path=scaffold_path,
            acceptance_authorization_review_record_validator_path=validator_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_review_record_example_bundle_v1"
    )
    assert (
        report["status"][
            "acceptance_authorization_review_record_example_bundle_ready"
        ]
        is True
    )
    assert report["status"]["synthetic_example_payload_created"] is True
    assert report["status"]["synthetic_example_payload_validated"] is True
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False

    bundle = report["acceptance_authorization_review_record_example_bundle"]
    synthetic_payload = bundle[
        "synthetic_completed_authorization_review_record_payload"
    ]
    assert synthetic_payload["reviewer_id"] == "synthetic_example_reviewer_anchor119"
    assert synthetic_payload["authorization_review_completed"] is True
    assert synthetic_payload["authorization_granted"] is False
    assert synthetic_payload["runtime_enablement_allowed"] is False
    assert synthetic_payload["acceptance_executed"] is False
    replay = bundle["replayed_validation"]
    assert replay["replay_mode"] == "in_memory_reuse_of_existing_validator_rules"
    assert replay["validation_status"] == "passed"
    assert replay["record_payload_validated"] is True
    assert replay["failed_rule_count"] == 0
    rule_results = {entry["rule_id"]: entry for entry in replay["per_rule_results"]}
    assert rule_results["completed_review_state"]["status"] == "pass"
    assert (
        rule_results[
            "authorization_grant_consistency_with_missing_prerequisites"
        ]["status"]
        == "pass"
    )
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_text(
            report
        )
    )
    assert "Synthetic example/demo payload only" in markdown
    assert (
        "acceptance_authorization_review_record_example_bundle_ready=True" in text
    )


def test_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    missing_scaffold = tmp_path / "missing_scaffold.json"
    missing_validator = tmp_path / "missing_validator.json"

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle(
            project_root,
            acceptance_authorization_review_record_scaffold_path=missing_scaffold,
            acceptance_authorization_review_record_validator_path=missing_validator,
        )
    )

    assert (
        report["status"][
            "acceptance_authorization_review_record_example_bundle_ready"
        ]
        is False
    )
    assert report["status"]["synthetic_example_payload_created"] is False
    assert report["status"]["synthetic_example_payload_validated"] is False
    bundle = report["acceptance_authorization_review_record_example_bundle"]
    assert bundle["synthetic_completed_authorization_review_record_payload"] == {}
    assert bundle["replayed_validation"]["validation_status"] == "not_run"
    checks = {entry["check_id"]: entry for entry in report["checks"]}
    assert (
        checks["acceptance_authorization_review_record_scaffold_present"]["status"]
        == "fail"
    )
    assert (
        checks["acceptance_authorization_review_record_validator_present"]["status"]
        == "fail"
    )


def test_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_cli(
    tmp_path: Path,
) -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle.py"
    )
    project_root = tmp_path / "project"
    scaffold_path, validator_path = _build_ready_upstream_artifacts(tmp_path)
    no_write_output_dir = tmp_path / "no_write_output"
    write_output_dir = tmp_path / "written_output"

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    repo_root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = (
        repo_root
        if not existing_pythonpath
        else repo_root + os.pathsep + existing_pythonpath
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--acceptance-authorization-review-record-scaffold",
            str(scaffold_path),
            "--acceptance-authorization-review-record-validator",
            str(validator_path),
            "--output-dir",
            str(no_write_output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert (
        "acceptance_authorization_review_record_example_bundle_ready=True"
        in no_write.stdout
    )
    assert not no_write_output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--acceptance-authorization-review-record-scaffold",
            str(scaffold_path),
            "--acceptance-authorization-review-record-validator",
            str(validator_path),
            "--output-dir",
            str(write_output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert (
        "anchor119_row_domain_acceptance_authorization_review_record_example_bundle_json="
        in write.stdout
    )
    json_path = (
        write_output_dir
        / "anchor119_row_domain_acceptance_authorization_review_record_example_bundle.json"
    )
    md_path = (
        write_output_dir
        / "anchor119_row_domain_acceptance_authorization_review_record_example_bundle.md"
    )
    txt_path = (
        write_output_dir
        / "anchor119_row_domain_acceptance_authorization_review_record_example_bundle.txt"
    )
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()
    written_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_review_record_example_bundle_v1"
    )
