from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_text,
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


def _locked_acceptance_command() -> str:
    return (
        "python temp_scripts/benchmark_parallelism.py --suite-kind "
        "production-acceptance --suite-output "
        ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    )


def _locked_acceptance_result_path() -> str:
    return ".codex_test_logs/phase3b/production_acceptance_after_change.json"


def _locked_execution_target() -> dict:
    return {
        "production_profile_id": "prod_4x4_normal",
        "production_profile_locked": True,
        "default_production_runner": "scripts/run_prod_4x4_normal.ps1",
        "default_production_runner_locked": True,
        "exact_future_acceptance_command": _locked_acceptance_command(),
        "exact_future_acceptance_command_locked": True,
        "exact_future_acceptance_result_path": _locked_acceptance_result_path(),
        "exact_future_acceptance_result_path_locked": True,
        "command_matches_result_path": True,
    }


def _operator_handoff_bundle_json() -> dict:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "acceptance_authorization_operator_handoff_bundle_v1"
            ),
            "spec_only": True,
            "review_only": True,
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
            "acceptance_authorization_operator_handoff_bundle_ready": True,
            "future_manual_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "actual_human_authorization_review_happened": False,
            "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_operator_handoff_bundle": {
            "operator_target": {
                "role": "future_manual_acceptance_authorization_review_operator",
                "scope": (
                    "candidate=67x13, anchor_idx=119, "
                    "formulation_profile=joined_xy_block64_all_templates"
                ),
                "review_phase": "manual_acceptance_authorization_review",
                "detail": (
                    "Read-only/operator-facing handoff for a future manual "
                    "acceptance-authorization review on anchor119."
                ),
            },
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "locked_execution_target": _locked_execution_target(),
            "blocked_prerequisites": [
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


def _instruction_packet_json() -> dict:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "acceptance_authorization_instruction_packet_v1"
            ),
            "spec_only": True,
            "review_only": True,
            "default_off": True,
            "no_solve": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "acceptance_executed": False,
        },
        "candidate": _candidate(),
        "status": {
            "acceptance_authorization_instruction_packet_ready": True,
            "future_manual_acceptance_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "actual_human_authorization_review_happened": False,
            "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
        },
        "acceptance_authorization_instruction_packet": {
            "packet_target": {
                "role": "future_manual_acceptance_authorization_review_operator",
                "scope": (
                    "candidate=67x13, anchor_idx=119, "
                    "formulation_profile=joined_xy_block64_all_templates"
                ),
                "review_phase": "manual_acceptance_authorization_review",
                "detail": (
                    "Bounded, review-only instruction packet for a future manual "
                    "acceptance-authorization review on anchor119."
                ),
            },
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "no_solve": True,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "does_not_authorize_execution": True,
            "locked_execution_target": _locked_execution_target(),
            "preserved_state_assertions": {
                "future_manual_acceptance_authorization_review_prerequisites_met": {
                    "expected_value": False,
                    "current_value": False,
                    "detail": "Blocked prerequisite gates still prevent future review.",
                },
                "acceptance_execution_authorized": {
                    "expected_value": False,
                    "current_value": False,
                    "detail": "Execution authorization must remain false.",
                },
                "runtime_enablement_allowed": {
                    "expected_value": False,
                    "current_value": False,
                    "detail": "Runtime enablement must remain false.",
                },
                "acceptance_executed": {
                    "expected_value": False,
                    "current_value": False,
                    "detail": "Acceptance execution must remain false.",
                },
                "actual_human_authorization_review_happened": {
                    "expected_value": False,
                    "current_value": False,
                    "detail": "No actual human authorization review has happened.",
                },
            },
            "forbidden_claims_or_actions": [
                "Do not authorize execution from this packet.",
                "Do not enable runtime from this packet.",
                "Do not execute acceptance from this packet.",
            ],
        },
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
    }


def _build_ready_upstream_artifacts(base_dir: Path) -> tuple[Path, Path]:
    instruction_packet_path = base_dir / "acceptance_authorization_instruction_packet.json"
    operator_handoff_path = (
        base_dir / "acceptance_authorization_operator_handoff_bundle.json"
    )

    _write_json(instruction_packet_path, _instruction_packet_json())
    _write_json(operator_handoff_path, _operator_handoff_bundle_json())
    return instruction_packet_path, operator_handoff_path


def test_anchor119_row_domain_acceptance_authorization_cover_note_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    instruction_packet_path, operator_handoff_path = _build_ready_upstream_artifacts(
        tmp_path
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note(
            project_root,
            acceptance_authorization_instruction_packet_path=instruction_packet_path,
            acceptance_authorization_operator_handoff_bundle_path=operator_handoff_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_cover_note_v1"
    )
    assert report["status"]["acceptance_authorization_cover_note_ready"] is True
    assert (
        report["status"][
            "future_manual_acceptance_authorization_review_prerequisites_met"
        ]
        is False
    )
    assert report["status"]["acceptance_execution_authorized"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_executed"] is False
    assert report["status"]["actual_human_authorization_review_happened"] is False
    assert report["still_blocked_gate_ids"] == ["reviewed_runtime_patch_exists"]

    cover_note = report["acceptance_authorization_cover_note"]
    assert cover_note["packet_target"]["review_phase"] == (
        "manual_acceptance_authorization_review"
    )
    assert [entry["artifact_id"] for entry in cover_note["read_first"]] == [
        "acceptance_authorization_operator_handoff_bundle",
        "acceptance_authorization_instruction_packet",
    ]
    assert cover_note["locked_execution_target"]["production_profile_id"] == (
        "prod_4x4_normal"
    )
    assert (
        cover_note["locked_execution_target"]["exact_future_acceptance_command"]
        == _locked_acceptance_command()
    )
    assert cover_note["current_blockers"][0]["gate_id"] == "reviewed_runtime_patch_exists"
    assert (
        cover_note["preserved_false_states"]["actual_human_authorization_review_happened"][
            "locked_false"
        ]
        is True
    )
    assert any(
        "Do not treat this cover note as authorization" in entry
        for entry in cover_note["forbidden_claims"]
    )

    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_text(
            report
        )
    )
    assert "Acceptance Authorization Cover Note" in markdown
    assert "acceptance_authorization_cover_note_ready=True" in text


def test_anchor119_row_domain_acceptance_authorization_cover_note_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note(
            project_root,
            acceptance_authorization_instruction_packet_path=(
                tmp_path / "missing_instruction_packet.json"
            ),
            acceptance_authorization_operator_handoff_bundle_path=(
                tmp_path / "missing_operator_handoff.json"
            ),
        )
    )

    assert report["status"]["acceptance_authorization_cover_note_ready"] is False
    assert (
        report["status"][
            "future_manual_acceptance_authorization_review_prerequisites_met"
        ]
        is False
    )
    checks = {entry["check_id"]: entry for entry in report["checks"]}
    assert (
        checks["acceptance_authorization_instruction_packet_present"]["status"]
        == "fail"
    )
    assert (
        checks["acceptance_authorization_operator_handoff_bundle_present"]["status"]
        == "fail"
    )
    assert (
        report["status"]["recommended_next_step"]
        == "repair_acceptance_authorization_cover_note_inputs"
    )


def test_anchor119_row_domain_acceptance_authorization_cover_note_cli(
    tmp_path: Path,
) -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_cover_note.py"
    )
    project_root = tmp_path / "project"
    instruction_packet_path, operator_handoff_path = _build_ready_upstream_artifacts(
        tmp_path
    )
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
            "--acceptance-authorization-instruction-packet",
            str(instruction_packet_path),
            "--acceptance-authorization-operator-handoff-bundle",
            str(operator_handoff_path),
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
    assert "acceptance_authorization_cover_note_ready=True" in no_write.stdout
    assert not no_write_output_dir.exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--acceptance-authorization-instruction-packet",
            str(instruction_packet_path),
            "--acceptance-authorization-operator-handoff-bundle",
            str(operator_handoff_path),
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
        "anchor119_row_domain_acceptance_authorization_cover_note_json="
        in write_run.stdout
    )
    json_path = write_output_dir / "anchor119_row_domain_acceptance_authorization_cover_note.json"
    md_path = write_output_dir / "anchor119_row_domain_acceptance_authorization_cover_note.md"
    txt_path = write_output_dir / "anchor119_row_domain_acceptance_authorization_cover_note.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()

    written_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "acceptance_authorization_cover_note_v1"
    )
