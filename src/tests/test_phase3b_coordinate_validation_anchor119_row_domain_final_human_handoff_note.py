from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note import (
    build_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note,
    render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _candidate() -> dict[str, object]:
    return {
        "key": "67x13",
        "anchor_idx": 119,
        "formulation_profile": "joined_xy_block64_all_templates",
    }


def _ingest_review_cover_note_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "ingest_review_cover_note_v1"
            ),
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "candidate": _candidate(),
        "status": {
            "ingest_review_cover_note_ready": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "handoff_summary": (
                "Use this branch only for future manual ingest review."
            ),
        },
        "still_blocked_gate_ids": [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
            "reviewer_signed_record_supplied_for_review",
            "reviewer_signed_record_validates_against_locked_contract",
            "separate_manual_ingest_review_approved",
        ],
        "ingest_review_cover_note": {
            "packet_target": {
                "package_summary": (
                    "Short entrypoint for the future manual ingest-review branch."
                ),
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "read_first": [
                {
                    "order": 1,
                    "artifact_id": "ingest_review_operator_handoff_bundle",
                    "path": ".artifacts/example/ingest_review_operator_handoff_bundle.json",
                    "why": "Primary detailed ingest-review entrypoint.",
                }
            ],
            "current_blockers": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "required_state": True,
                    "current_value": False,
                    "detail": "A reviewed runtime patch record still does not exist.",
                },
                {
                    "gate_id": "production_acceptance_refresh_completed",
                    "required_state": True,
                    "current_value": False,
                    "detail": "Production acceptance refresh is still pending.",
                },
                {
                    "gate_id": "reviewer_signed_record_supplied_for_review",
                    "required_state": True,
                    "current_value": False,
                    "detail": "No reviewer-signed record has been supplied yet.",
                },
                {
                    "gate_id": "reviewer_signed_record_validates_against_locked_contract",
                    "required_state": True,
                    "current_value": False,
                    "detail": "No reviewer-signed record has been validated yet.",
                },
                {
                    "gate_id": "separate_manual_ingest_review_approved",
                    "required_state": True,
                    "current_value": False,
                    "detail": "No separate manual ingest review approval exists yet.",
                },
            ],
            "preserved_false_states": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "proof_source": False,
                "candidate_elimination_claim": False,
                "solver_invoked": False,
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "forbidden_claims": [
                "Do not update repo-side review state from this branch.",
                "Do not imply reviewed_runtime_patch_exists=true.",
                "Do not authorize execution.",
            ],
            "handoff_summary": (
                "Read the operator handoff bundle first and keep the branch review-only."
            ),
        },
    }


def _ingest_review_instruction_packet_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "ingest_review_instruction_packet_v1"
            ),
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
            "repo_side_review_state_updated": False,
        },
        "candidate": _candidate(),
        "status": {
            "ingest_review_instruction_packet_ready": True,
        },
        "still_blocked_gate_ids": [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
            "reviewer_signed_record_supplied_for_review",
            "reviewer_signed_record_validates_against_locked_contract",
            "separate_manual_ingest_review_approved",
        ],
        "ingest_review_instruction_packet": {
            "packet_target": {
                "review_step_summary": (
                    "Bounded instruction packet for the future manual ingest-review branch."
                )
            },
            "open_these_first": [
                {
                    "order": 1,
                    "artifact_id": "ingest_review_operator_handoff_bundle",
                    "path": ".artifacts/example/ingest_review_operator_handoff_bundle.json",
                    "why": "Primary detailed ingest-review entrypoint.",
                },
                {
                    "order": 2,
                    "artifact_id": "ingest_review_record_validator",
                    "path": ".artifacts/example/ingest_review_record_validator.json",
                    "why": "Validator contract for the future ingest-review record.",
                },
                {
                    "order": 3,
                    "artifact_id": "ingest_review_record_example_bundle",
                    "path": ".artifacts/example/ingest_review_record_example_bundle.json",
                    "why": "Reference-only example bundle.",
                },
            ],
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
                "proof_source": False,
                "candidate_elimination_claim": False,
                "solver_invoked": False,
                "execution_authorized": False,
            },
            "forbidden_claims_or_actions": [
                "Do not imply reviewed_runtime_patch_exists=true.",
                "Do not update repo-side review state from this packet.",
            ],
        },
    }


def _acceptance_authorization_cover_note_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "acceptance_authorization_cover_note_v1"
            ),
            "review_only": True,
            "spec_only": True,
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
            "acceptance_authorization_cover_note_ready": True,
            "future_manual_acceptance_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "actual_human_authorization_review_happened": False,
            "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
            "handoff_summary": (
                "Keep the locked prod_4x4_normal path review-only and blocked."
            ),
        },
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
        "acceptance_authorization_cover_note": {
            "packet_target": {
                "detail": (
                    "Bounded review-only summary for the future manual "
                    "acceptance-authorization branch."
                )
            },
            "read_first": [
                {
                    "order": 1,
                    "artifact_id": "acceptance_authorization_operator_handoff_bundle",
                    "artifact_path": ".artifacts/example/acceptance_authorization_operator_handoff_bundle.json",
                    "why_read_first": "Primary detailed acceptance entrypoint.",
                }
            ],
            "current_blockers": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "required_state": True,
                    "current_value": False,
                    "detail": (
                        "A reviewed runtime patch signoff record is still missing."
                    ),
                }
            ],
            "preserved_false_states": {
                "future_manual_acceptance_authorization_review_prerequisites_met": {
                    "current_value": False
                },
                "acceptance_execution_authorized": {"current_value": False},
                "runtime_enablement_allowed": {"current_value": False},
                "acceptance_executed": {"current_value": False},
                "actual_human_authorization_review_happened": {
                    "current_value": False
                },
            },
            "forbidden_claims": [
                "Do not authorize execution from this branch.",
                "Do not enable runtime from this branch.",
                "Do not imply reviewed_runtime_patch_exists=true.",
            ],
            "handoff_summary": (
                "Keep acceptance authorization blocked until reviewed_runtime_patch_exists becomes true elsewhere."
            ),
        },
    }


def _acceptance_authorization_instruction_packet_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "acceptance_authorization_instruction_packet_v1"
            ),
            "review_only": True,
            "spec_only": True,
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
        "still_blocked_gate_ids": ["reviewed_runtime_patch_exists"],
        "acceptance_authorization_instruction_packet": {
            "packet_target": {
                "detail": (
                    "Bounded instruction packet for the future manual acceptance-authorization branch."
                )
            },
            "open_these_first": [
                {
                    "order": 1,
                    "artifact_id": "acceptance_authorization_operator_handoff_bundle",
                    "artifact_path": ".artifacts/example/acceptance_authorization_operator_handoff_bundle.json",
                    "why_read_first": "Primary detailed acceptance entrypoint.",
                },
                {
                    "order": 2,
                    "artifact_id": "acceptance_authorization_review_record_validator",
                    "artifact_path": ".artifacts/example/acceptance_authorization_review_record_validator.json",
                    "why_read_first": (
                        "Validator contract for the future acceptance-authorization record."
                    ),
                },
                {
                    "order": 3,
                    "artifact_id": "acceptance_authorization_review_record_example_bundle",
                    "artifact_path": ".artifacts/example/acceptance_authorization_review_record_example_bundle.json",
                    "why_read_first": "Reference-only example bundle.",
                },
            ],
            "preserved_state_assertions": {
                "future_manual_acceptance_authorization_review_prerequisites_met": {
                    "current_value": False
                },
                "acceptance_execution_authorized": {"current_value": False},
                "runtime_enablement_allowed": {"current_value": False},
                "acceptance_executed": {"current_value": False},
                "actual_human_authorization_review_happened": {
                    "current_value": False
                },
            },
            "forbidden_claims_or_actions": [
                "Do not authorize execution from this packet.",
                "Do not imply reviewed_runtime_patch_exists=true.",
            ],
        },
    }


def _build_ready_upstream_artifacts(base_dir: Path) -> tuple[Path, Path, Path, Path]:
    ingest_cover_path = base_dir / "ingest_review_cover_note.json"
    ingest_packet_path = base_dir / "ingest_review_instruction_packet.json"
    acceptance_cover_path = base_dir / "acceptance_authorization_cover_note.json"
    acceptance_packet_path = (
        base_dir / "acceptance_authorization_instruction_packet.json"
    )

    _write_json(ingest_cover_path, _ingest_review_cover_note_json())
    _write_json(ingest_packet_path, _ingest_review_instruction_packet_json())
    _write_json(acceptance_cover_path, _acceptance_authorization_cover_note_json())
    _write_json(
        acceptance_packet_path, _acceptance_authorization_instruction_packet_json()
    )
    return (
        ingest_cover_path,
        ingest_packet_path,
        acceptance_cover_path,
        acceptance_packet_path,
    )


def test_anchor119_row_domain_final_human_handoff_note_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (
        ingest_cover_path,
        ingest_packet_path,
        acceptance_cover_path,
        acceptance_packet_path,
    ) = _build_ready_upstream_artifacts(tmp_path)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note(
            project_root,
            ingest_review_cover_note_path=ingest_cover_path,
            ingest_review_instruction_packet_path=ingest_packet_path,
            acceptance_authorization_cover_note_path=acceptance_cover_path,
            acceptance_authorization_instruction_packet_path=acceptance_packet_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "final_human_handoff_note_v1"
    )
    assert report["status"]["final_human_handoff_note_ready"] is True
    assert report["candidate"] == _candidate()
    assert report["status"]["recommended_next_step"] == (
        "keep_final_human_handoff_note_review_only_and_wait_for_blockers"
    )

    note = report["final_human_handoff_note"]
    assert note["note_target"]["branch_ids"] == [
        "ingest_review",
        "acceptance_authorization",
    ]
    assert [entry["branch_id"] for entry in note["read_this_first"]] == [
        "ingest_review",
        "acceptance_authorization",
    ]
    assert {entry["gate_id"] for entry in note["still_blocked"]} == {
        "reviewed_runtime_patch_exists",
        "production_acceptance_refresh_completed",
        "reviewer_signed_record_supplied_for_review",
        "reviewer_signed_record_validates_against_locked_contract",
        "separate_manual_ingest_review_approved",
    }
    assert {entry["state_id"] for entry in note["still_false"]} >= {
        "reviewed_runtime_patch_exists",
        "runtime_enablement_allowed",
        "proof_source",
        "candidate_elimination_claim",
        "solver_invoked",
        "acceptance_execution_authorized",
        "acceptance_executed",
    }
    assert any(
        "Do not authorize execution" in entry for entry in note["do_not_claim"]
    )
    assert any(
        "It does not update repo-side review state" in entry
        for entry in note["what_this_package_still_does_not_do"]
    )

    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_text(
            report
        )
    )
    assert "Final Human Handoff Note" in markdown
    assert "Still False" in markdown
    assert "final_human_handoff_note_ready=True" in text


def test_anchor119_row_domain_final_human_handoff_note_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note(
            project_root,
            ingest_review_cover_note_path=tmp_path / "missing_ingest_cover.json",
            ingest_review_instruction_packet_path=tmp_path / "missing_ingest_packet.json",
            acceptance_authorization_cover_note_path=tmp_path
            / "missing_acceptance_cover.json",
            acceptance_authorization_instruction_packet_path=tmp_path
            / "missing_acceptance_packet.json",
        )
    )

    assert report["status"]["final_human_handoff_note_ready"] is False
    assert report["status"]["recommended_next_step"] == (
        "repair_final_human_handoff_note_inputs"
    )
    checks = {entry["check_id"]: entry for entry in report["checks"]}
    assert checks["ingest_review_cover_note_present"]["status"] == "fail"
    assert checks["ingest_review_instruction_packet_present"]["status"] == "fail"
    assert (
        checks["acceptance_authorization_cover_note_present"]["status"] == "fail"
    )
    assert (
        checks["acceptance_authorization_instruction_packet_present"]["status"]
        == "fail"
    )


def test_anchor119_row_domain_final_human_handoff_note_cli(tmp_path: Path) -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_"
        "final_human_handoff_note.py"
    )
    project_root = tmp_path / "project"
    (
        ingest_cover_path,
        ingest_packet_path,
        acceptance_cover_path,
        acceptance_packet_path,
    ) = _build_ready_upstream_artifacts(tmp_path)
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
            "--ingest-review-cover-note",
            str(ingest_cover_path),
            "--ingest-review-instruction-packet",
            str(ingest_packet_path),
            "--acceptance-authorization-cover-note",
            str(acceptance_cover_path),
            "--acceptance-authorization-instruction-packet",
            str(acceptance_packet_path),
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
    assert "final_human_handoff_note_ready=True" in no_write.stdout
    assert not no_write_output_dir.exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--ingest-review-cover-note",
            str(ingest_cover_path),
            "--ingest-review-instruction-packet",
            str(ingest_packet_path),
            "--acceptance-authorization-cover-note",
            str(acceptance_cover_path),
            "--acceptance-authorization-instruction-packet",
            str(acceptance_packet_path),
            "--output-dir",
            str(write_output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert "anchor119_row_domain_final_human_handoff_note_json=" in write_run.stdout

    json_path = write_output_dir / "anchor119_row_domain_final_human_handoff_note.json"
    md_path = write_output_dir / "anchor119_row_domain_final_human_handoff_note.md"
    txt_path = write_output_dir / "anchor119_row_domain_final_human_handoff_note.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()

    written_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_payload["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_"
        "final_human_handoff_note_v1"
    )
