from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.acceptance_authorization_operator_handoff_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_text,
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


def _locked_execution_target() -> dict:
    return {
        "production_profile_id": "prod_4x4_normal",
        "production_profile_locked": True,
        "default_production_runner": _default_runner(),
        "default_production_runner_locked": True,
        "exact_future_acceptance_command": _locked_acceptance_command(),
        "exact_future_acceptance_command_locked": True,
        "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
        "exact_future_acceptance_result_path_locked": True,
        "command_matches_result_path": True,
    }


def _scaffold_json() -> dict:
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
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_review_record_scaffold": {
            "locked_execution_target": _locked_execution_target(),
            "required_record_fields": [
                {
                    "field": "reviewer_id",
                    "required": True,
                    "template_value": "",
                    "detail": "Human reviewer identity must be provided later.",
                },
                {
                    "field": "reviewed_at",
                    "required": True,
                    "template_value": "",
                    "detail": "Human review timestamp must be provided later.",
                },
                {
                    "field": "authorization_granted",
                    "required": True,
                    "template_value": False,
                    "detail": "Future human review must make an explicit boolean decision.",
                },
            ],
            "required_review_conclusions": [
                {
                    "conclusion_id": "locked_prod_4x4_normal_target_confirmed",
                    "required": True,
                    "currently_satisfied": True,
                    "detail": "Locked target must remain unchanged.",
                },
                {
                    "conclusion_id": "reviewed_runtime_patch_exists",
                    "required": True,
                    "currently_satisfied": False,
                    "detail": "Reviewed runtime patch signoff record must exist first.",
                },
            ],
            "required_runtime_patch_statement_ids": [
                "default_off_retained",
                "acceptance_refresh_required_before_enablement",
            ],
            "future_validation_checklist": [
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "detail": "runtime_enablement_allowed must remain false.",
                }
            ],
            "scaffolded_authorization_review_record_payload": {
                "record_type": "acceptance_execution_authorization_review_record_v0"
            },
        },
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
    }


def _validator_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_record_validator_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_authorization_review_record_validator_ready": True,
            "future_manual_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "authorization_review_completed": False,
            "authorization_review_record_provided": False,
            "authorization_review_record_validated": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_review_record_validator": {
            "validator_target": (
                "future_acceptance_execution_authorization_review_record_payload"
            ),
            "target_record_type": "acceptance_execution_authorization_review_record_v0",
            "locked_execution_target": _locked_execution_target(),
            "required_record_fields": [
                {
                    "field": "reviewer_id",
                    "required": True,
                    "template_value": "",
                    "detail": "Human reviewer identity must be present and non-empty.",
                },
                {
                    "field": "reviewed_at",
                    "required": True,
                    "template_value": "",
                    "detail": "Human review timestamp must be present and non-empty.",
                },
                {
                    "field": "authorization_granted",
                    "required": True,
                    "template_value": False,
                    "detail": "Future human review must make an explicit boolean decision.",
                },
            ],
            "required_review_conclusions": [
                {
                    "conclusion_id": "locked_prod_4x4_normal_target_confirmed",
                    "required": True,
                    "currently_satisfied": True,
                    "detail": "Locked target must remain unchanged.",
                },
                {
                    "conclusion_id": "reviewed_runtime_patch_exists",
                    "required": True,
                    "currently_satisfied": False,
                    "detail": "Reviewed runtime patch signoff record must exist first.",
                },
            ],
            "required_runtime_patch_statement_ids": [
                "default_off_retained",
                "acceptance_refresh_required_before_enablement",
            ],
            "future_validation_checklist": [
                {
                    "checklist_id": "keep_runtime_enablement_forbidden",
                    "detail": "runtime_enablement_allowed must remain false.",
                }
            ],
            "validator_notice": (
                "Validate only a future real human authorization-review record."
            ),
            "missing_prerequisites": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "required_state": True,
                    "current_value": False,
                    "detail": "Reviewed runtime patch signoff record is still absent.",
                }
            ],
        },
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
    }


def _example_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_authorization_review_record_example_bundle_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_authorization_review_record_example_bundle_ready": True,
            "synthetic_example_payload_created": True,
            "synthetic_example_payload_validated": True,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
        },
        "acceptance_authorization_review_record_example_bundle": {
            "locked_execution_target": _locked_execution_target(),
            "example_only_notes": [
                "Synthetic example/demo payload only; not an actual human authorization review record.",
                "Synthetic example is reference only and does not authorize execution.",
            ],
            "required_review_conclusions": [
                {
                    "conclusion_id": "locked_prod_4x4_normal_target_confirmed",
                    "required": True,
                    "currently_satisfied": True,
                    "detail": "Locked target must remain unchanged.",
                }
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
                    "detail": "Reviewed runtime patch signoff record is still absent.",
                }
            ],
        },
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
    }


def _execution_gate_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_execution_gate_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_execution_gate_ready": True,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "missing_prerequisite_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_execution_gate": {
            "production_profile_id": "prod_4x4_normal",
            "locked_execution_target": {
                "production_profile_id": "prod_4x4_normal",
                "default_production_runner": _default_runner(),
                "exact_future_acceptance_command": _locked_acceptance_command(),
                "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
            },
            "missing_prerequisites_before_execution_authorization": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "required_state": True,
                    "current_value": False,
                    "detail": "Reviewed runtime patch signoff record is still absent.",
                }
            ],
        },
    }


def _execution_staging_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_"
            "acceptance_execution_staging_v1"
        ),
        "candidate": _candidate(),
        "status": {
            "acceptance_execution_staging_ready": True,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
        },
        "acceptance_execution_staging": {
            "production_profile_id": "prod_4x4_normal",
            "exact_command_to_run_later": _locked_acceptance_command(),
            "exact_future_output_path": _locked_acceptance_result_path(),
        },
    }


def _build_ready_upstream_artifacts(base_dir: Path) -> tuple[Path, Path, Path, Path, Path]:
    scaffold_path = base_dir / "acceptance_authorization_review_record_scaffold.json"
    validator_path = base_dir / "acceptance_authorization_review_record_validator.json"
    example_bundle_path = (
        base_dir / "acceptance_authorization_review_record_example_bundle.json"
    )
    execution_gate_path = base_dir / "acceptance_execution_gate.json"
    execution_staging_path = base_dir / "acceptance_execution_staging.json"

    _write_json(scaffold_path, _scaffold_json())
    _write_json(validator_path, _validator_json())
    _write_json(example_bundle_path, _example_bundle_json())
    _write_json(execution_gate_path, _execution_gate_json())
    _write_json(execution_staging_path, _execution_staging_json())
    return (
        scaffold_path,
        validator_path,
        example_bundle_path,
        execution_gate_path,
        execution_staging_path,
    )


def test_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    (
        scaffold_path,
        validator_path,
        example_bundle_path,
        execution_gate_path,
        execution_staging_path,
    ) = _build_ready_upstream_artifacts(tmp_path)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle(
            project_root,
            acceptance_authorization_review_record_scaffold_path=scaffold_path,
            acceptance_authorization_review_record_validator_path=validator_path,
            acceptance_authorization_review_record_example_bundle_path=(
                example_bundle_path
            ),
            acceptance_execution_gate_path=execution_gate_path,
            acceptance_execution_staging_path=execution_staging_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_operator_handoff_bundle_v1"
    )
    assert (
        report["status"]["acceptance_authorization_operator_handoff_bundle_ready"]
        is True
    )
    assert (
        report["status"]["future_manual_authorization_review_prerequisites_met"]
        is False
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    assert report["status"]["actual_human_authorization_review_happened"] is False
    assert report["still_blocked_gate_ids"] == ["reviewed_runtime_patch_exists"]

    bundle = report["acceptance_authorization_operator_handoff_bundle"]
    assert bundle["operator_target"]["role"] == (
        "future_manual_acceptance_authorization_review_operator"
    )
    assert bundle["locked_execution_target"]["production_profile_id"] == "prod_4x4_normal"
    assert (
        bundle["locked_execution_target"]["exact_future_acceptance_command"]
        == _locked_acceptance_command()
    )
    assert (
        bundle["validator_script_or_artifact_reference"][
            "validator_builder_script"
        ].endswith(
            "build_acceptance_authorization_review_record_validator.py"
        )
    )
    assert (
        bundle["example_bundle_reference"]["synthetic_example_reference_only"] is True
    )
    assert bundle["preserved_state_assertions"] == {
        "acceptance_execution_authorized": False,
        "runtime_enablement_allowed": False,
        "acceptance_executed": False,
        "actual_human_authorization_review_happened": False,
    }
    assert [
        entry["step_id"] for entry in bundle["ordered_steps"]
    ] == [
        "read_authoritative_artifacts",
        "confirm_locked_prod_4x4_target",
        "use_validator_contract_for_future_real_record",
        "use_synthetic_example_as_reference_only",
        "preserve_default_off_state",
        "stop_if_prerequisites_still_blocked",
    ]

    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_text(
            report
        )
    )
    assert "Synthetic example is reference only" in markdown
    assert "acceptance_authorization_operator_handoff_bundle_ready=True" in text


def test_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle(
            project_root,
            acceptance_authorization_review_record_scaffold_path=(
                tmp_path / "missing_scaffold.json"
            ),
            acceptance_authorization_review_record_validator_path=(
                tmp_path / "missing_validator.json"
            ),
            acceptance_authorization_review_record_example_bundle_path=(
                tmp_path / "missing_example.json"
            ),
            acceptance_execution_gate_path=tmp_path / "missing_gate.json",
            acceptance_execution_staging_path=tmp_path / "missing_staging.json",
        )
    )

    assert (
        report["status"]["acceptance_authorization_operator_handoff_bundle_ready"]
        is False
    )
    assert (
        report["status"]["future_manual_authorization_review_prerequisites_met"]
        is False
    )
    assert report["acceptance_authorization_operator_handoff_bundle"]["authoritative_inputs"][
        0
    ]["present"] is False
    checks = {entry["check_id"]: entry for entry in report["checks"]}
    assert (
        checks["acceptance_authorization_review_record_scaffold_present"]["status"]
        == "fail"
    )
    assert checks["acceptance_execution_gate_present"]["status"] == "fail"
    assert (
        report["status"]["recommended_next_step"]
        == "repair_acceptance_authorization_operator_handoff_bundle_inputs"
    )


def test_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_cli(
    tmp_path: Path,
) -> None:
    script_path = (
        Path(__file__).resolve().parents[5]
        / "scripts"
        / "phase3b"
        / "coordinate_validation"
        / "anchor119_row_domain"
        / "build_acceptance_authorization_operator_handoff_bundle.py"
    )
    project_root = tmp_path / "project"
    (
        scaffold_path,
        validator_path,
        example_bundle_path,
        execution_gate_path,
        execution_staging_path,
    ) = _build_ready_upstream_artifacts(tmp_path)
    no_write_output_dir = tmp_path / "no_write_output"
    write_output_dir = tmp_path / "written_output"

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    repo_root = str(Path(__file__).resolve().parents[5])
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
            "--acceptance-authorization-review-record-example-bundle",
            str(example_bundle_path),
            "--acceptance-execution-gate",
            str(execution_gate_path),
            "--acceptance-execution-staging",
            str(execution_staging_path),
            "--output-dir",
            str(no_write_output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[5]),
    )
    assert (
        "acceptance_authorization_operator_handoff_bundle_ready=True"
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
            "--acceptance-authorization-review-record-example-bundle",
            str(example_bundle_path),
            "--acceptance-execution-gate",
            str(execution_gate_path),
            "--acceptance-execution-staging",
            str(execution_staging_path),
            "--output-dir",
            str(write_output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[5]),
    )
    assert (
        "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_json="
        in write.stdout
    )
    json_path = (
        write_output_dir
        / "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle.json"
    )
    md_path = (
        write_output_dir
        / "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle.md"
    )
    txt_path = (
        write_output_dir
        / "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle.txt"
    )
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()

    written_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_operator_handoff_bundle_v1"
    )
