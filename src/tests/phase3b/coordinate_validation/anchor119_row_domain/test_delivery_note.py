from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.delivery_note import (
    build_phase3b_coordinate_validation_anchor119_row_domain_delivery_note,
    render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_text,
)

CANDIDATE_KEY = "67x13"
ANCHOR_IDX = 119
FORMULATION_PROFILE = "joined_xy_block64_all_templates"
BLOCKER_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
    "reviewer_signed_record_supplied_for_review",
    "reviewer_signed_record_validates_against_locked_contract",
    "separate_manual_ingest_review_approved",
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _package_index_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "manual_review_package_index_v1"
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
            "repo_side_review_state_updated": False,
        },
        "status": {
            "manual_review_package_index_ready": True,
            "contract_compatible": True,
            "global_blocker_gate_ids": list(BLOCKER_IDS),
        },
        "package_target": {
            "package_id": (
                "anchor119_manual_review_package_across_ingest_and_acceptance_branches"
            ),
            "candidate_key": CANDIDATE_KEY,
            "anchor_idx": ANCHOR_IDX,
            "formulation_profile": FORMULATION_PROFILE,
            "branches": ["ingest-review", "acceptance-authorization"],
            "package_notice": (
                "Review-only/spec-only/default-off/no-solve package index only."
            ),
        },
        "short_package_summary": (
            "Unified anchor119 manual-review package index for the ingest-review "
            "and acceptance-authorization branches."
        ),
        "global_blockers": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "branches": ["ingest-review", "acceptance-authorization"],
                "current_value": False,
                "details": [
                    "The reviewed runtime patch record does not exist yet."
                ],
            },
            {
                "gate_id": "production_acceptance_refresh_completed",
                "branches": ["ingest-review"],
                "current_value": False,
                "details": ["Production acceptance refresh is still pending."],
            },
            {
                "gate_id": "reviewer_signed_record_supplied_for_review",
                "branches": ["ingest-review"],
                "current_value": False,
                "details": ["No reviewer-signed record has been supplied yet."],
            },
            {
                "gate_id": "reviewer_signed_record_validates_against_locked_contract",
                "branches": ["ingest-review"],
                "current_value": False,
                "details": ["No reviewer-signed record has been validated yet."],
            },
            {
                "gate_id": "separate_manual_ingest_review_approved",
                "branches": ["ingest-review"],
                "current_value": False,
                "details": ["No separate manual ingest approval exists yet."],
            },
        ],
        "preserved_false_states": {
            "repo_side_review_state_updated": {
                "state_id": "repo_side_review_state_updated",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review"],
                "detail": "Repo-side review state must remain unchanged.",
            },
            "reviewed_runtime_patch_exists": {
                "state_id": "reviewed_runtime_patch_exists",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review", "acceptance-authorization"],
                "detail": "The reviewed runtime patch record still does not exist.",
            },
            "runtime_enablement_allowed": {
                "state_id": "runtime_enablement_allowed",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review", "acceptance-authorization"],
                "detail": "Runtime enablement remains blocked.",
            },
            "proof_source": {
                "state_id": "proof_source",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review", "acceptance-authorization"],
                "detail": "This package remains non-proof.",
            },
            "candidate_elimination_claim": {
                "state_id": "candidate_elimination_claim",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review", "acceptance-authorization"],
                "detail": "This package must not claim candidate elimination.",
            },
            "solver_invoked": {
                "state_id": "solver_invoked",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review", "acceptance-authorization"],
                "detail": "This package remains no-solve.",
            },
            "actual_human_review_has_happened": {
                "state_id": "actual_human_review_has_happened",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review"],
                "detail": "No actual human ingest review has happened.",
            },
            "execution_authorized": {
                "state_id": "execution_authorized",
                "current_value": False,
                "locked_false": True,
                "branches": ["ingest-review"],
                "detail": "Execution is not authorized.",
            },
            "future_manual_acceptance_authorization_review_prerequisites_met": {
                "state_id": "future_manual_acceptance_authorization_review_prerequisites_met",
                "current_value": False,
                "locked_false": True,
                "branches": ["acceptance-authorization"],
                "detail": "Acceptance-authorization prerequisites remain blocked.",
            },
            "acceptance_execution_authorized": {
                "state_id": "acceptance_execution_authorized",
                "current_value": False,
                "locked_false": True,
                "branches": ["acceptance-authorization"],
                "detail": "Acceptance execution is not authorized.",
            },
            "acceptance_executed": {
                "state_id": "acceptance_executed",
                "current_value": False,
                "locked_false": True,
                "branches": ["acceptance-authorization"],
                "detail": "Acceptance has not been executed.",
            },
            "actual_human_authorization_review_happened": {
                "state_id": "actual_human_authorization_review_happened",
                "current_value": False,
                "locked_false": True,
                "branches": ["acceptance-authorization"],
                "detail": "No actual human authorization review has happened.",
            },
        },
        "primary_entrypoints": [
            {
                "artifact_id": "ingest_review_cover_note",
                "branch_id": "ingest-review",
                "path": ".artifacts/example/ingest_review_cover_note.json",
                "reason": "Ingest-review entrypoint.",
            },
            {
                "artifact_id": "acceptance_authorization_cover_note",
                "branch_id": "acceptance-authorization",
                "path": ".artifacts/example/acceptance_authorization_cover_note.json",
                "reason": "Acceptance-authorization entrypoint.",
            },
        ],
    }


def _final_handoff_note_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": (
                "phase3b_coordinate_validation_anchor119_row_domain_"
                "final_human_handoff_note_v1"
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
            "repo_side_review_state_updated": False,
        },
        "candidate": {
            "key": CANDIDATE_KEY,
            "anchor_idx": ANCHOR_IDX,
            "formulation_profile": FORMULATION_PROFILE,
        },
        "status": {
            "final_human_handoff_note_ready": True,
            "still_blocked_gate_ids": list(BLOCKER_IDS),
            "recommended_next_step": (
                "keep_final_human_handoff_note_review_only_and_wait_for_blockers"
            ),
            "final_handoff_summary": (
                "Start with the two cover notes and carry the blocked gates forward."
            ),
        },
        "final_human_handoff_note": {
            "note_target": {
                "target_reader": "future_human_operator_or_reviewer",
                "candidate_key": CANDIDATE_KEY,
                "anchor_idx": ANCHOR_IDX,
                "formulation_profile": FORMULATION_PROFILE,
                "branch_ids": ["ingest_review", "acceptance_authorization"],
                "branch_count": 2,
            },
            "what_this_package_is": (
                "One bounded, artifact-backed final human handoff note for the "
                "anchor119 manual-review package."
            ),
            "read_this_first": [
                {
                    "branch_id": "ingest_review",
                    "branch_label": "Ingest Review",
                    "artifact_id": "ingest_review_cover_note",
                    "artifact_path": ".artifacts/example/ingest_review_cover_note.json",
                    "why": "Fastest review-only entrypoint for the ingest-review branch.",
                },
                {
                    "branch_id": "acceptance_authorization",
                    "branch_label": "Acceptance Authorization",
                    "artifact_id": "acceptance_authorization_cover_note",
                    "artifact_path": ".artifacts/example/acceptance_authorization_cover_note.json",
                    "why": "Fastest review-only entrypoint for the acceptance-authorization branch.",
                },
            ],
            "branch_summaries": [
                {
                    "branch_id": "ingest_review",
                    "branch_label": "Ingest Review",
                    "what_branch_is_for": (
                        "Future manual ingest-review path for repo-side reviewed-runtime-patch state handling."
                    ),
                    "entrypoint_artifact": {
                        "artifact_id": "ingest_review_cover_note",
                        "artifact_path": ".artifacts/example/ingest_review_cover_note.json",
                    },
                },
                {
                    "branch_id": "acceptance_authorization",
                    "branch_label": "Acceptance Authorization",
                    "what_branch_is_for": (
                        "Future manual acceptance-authorization path for the locked prod_4x4_normal target."
                    ),
                    "entrypoint_artifact": {
                        "artifact_id": "acceptance_authorization_cover_note",
                        "artifact_path": ".artifacts/example/acceptance_authorization_cover_note.json",
                    },
                },
            ],
            "still_blocked": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "branches": ["ingest_review", "acceptance_authorization"],
                    "current_value": False,
                    "detail": "The reviewed runtime patch record does not exist yet.",
                },
                {
                    "gate_id": "production_acceptance_refresh_completed",
                    "branches": ["ingest_review"],
                    "current_value": False,
                    "detail": "Production acceptance refresh is still pending.",
                },
                {
                    "gate_id": "reviewer_signed_record_supplied_for_review",
                    "branches": ["ingest_review"],
                    "current_value": False,
                    "detail": "No reviewer-signed record has been supplied yet.",
                },
                {
                    "gate_id": "reviewer_signed_record_validates_against_locked_contract",
                    "branches": ["ingest_review"],
                    "current_value": False,
                    "detail": "No reviewer-signed record has been validated yet.",
                },
                {
                    "gate_id": "separate_manual_ingest_review_approved",
                    "branches": ["ingest_review"],
                    "current_value": False,
                    "detail": "No separate manual ingest approval exists yet.",
                },
            ],
            "still_false": [
                {
                    "state_id": "repo_side_review_state_updated",
                    "branches": ["ingest_review"],
                    "current_value": False,
                    "detail": "Repo-side review state must remain unchanged.",
                },
                {
                    "state_id": "reviewed_runtime_patch_exists",
                    "branches": ["ingest_review", "acceptance_authorization"],
                    "current_value": False,
                    "detail": "The reviewed runtime patch record still does not exist.",
                },
                {
                    "state_id": "runtime_enablement_allowed",
                    "branches": ["ingest_review", "acceptance_authorization"],
                    "current_value": False,
                    "detail": "Runtime enablement remains blocked.",
                },
                {
                    "state_id": "proof_source",
                    "branches": ["ingest_review", "acceptance_authorization"],
                    "current_value": False,
                    "detail": "This package remains non-proof.",
                },
                {
                    "state_id": "candidate_elimination_claim",
                    "branches": ["ingest_review", "acceptance_authorization"],
                    "current_value": False,
                    "detail": "This package must not claim candidate elimination.",
                },
                {
                    "state_id": "solver_invoked",
                    "branches": ["ingest_review", "acceptance_authorization"],
                    "current_value": False,
                    "detail": "This package remains no-solve.",
                },
                {
                    "state_id": "actual_human_review_has_happened",
                    "branches": ["ingest_review"],
                    "current_value": False,
                    "detail": "No actual human ingest review has happened.",
                },
                {
                    "state_id": "execution_authorized",
                    "branches": ["ingest_review"],
                    "current_value": False,
                    "detail": "Execution is not authorized.",
                },
                {
                    "state_id": "future_manual_acceptance_authorization_review_prerequisites_met",
                    "branches": ["acceptance_authorization"],
                    "current_value": False,
                    "detail": "Acceptance-authorization prerequisites remain blocked.",
                },
                {
                    "state_id": "acceptance_execution_authorized",
                    "branches": ["acceptance_authorization"],
                    "current_value": False,
                    "detail": "Acceptance execution is not authorized.",
                },
                {
                    "state_id": "acceptance_executed",
                    "branches": ["acceptance_authorization"],
                    "current_value": False,
                    "detail": "Acceptance has not been executed.",
                },
                {
                    "state_id": "actual_human_authorization_review_happened",
                    "branches": ["acceptance_authorization"],
                    "current_value": False,
                    "detail": "No actual human authorization review has happened.",
                },
            ],
            "what_this_package_still_does_not_do": [
                "It does not update repo-side review state or review-status artifacts.",
                "It does not authorize execution, runtime enablement, or acceptance execution.",
            ],
        },
    }


def _build_ready_upstream_artifacts(base_dir: Path) -> tuple[Path, Path]:
    package_index_path = base_dir / "manual_review_package_index.json"
    final_handoff_path = base_dir / "final_human_handoff_note.json"
    _write_json(package_index_path, _package_index_json())
    _write_json(final_handoff_path, _final_handoff_note_json())
    return package_index_path, final_handoff_path


def test_anchor119_row_domain_delivery_note_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    package_index_path, final_handoff_path = _build_ready_upstream_artifacts(tmp_path)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_delivery_note(
        project_root,
        manual_review_package_index_path=package_index_path,
        final_human_handoff_note_path=final_handoff_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_delivery_note_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["no_solve"] is True
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["candidate_elimination_claim"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["repo_side_review_state_updated"] is False

    status = report["status"]
    assert status["delivery_note_ready"] is True
    assert status["package_index_ready"] is True
    assert status["final_human_handoff_note_ready"] is True
    assert status["contract_compatible"] is True
    assert status["missing_ready_gate_ids"] == []
    assert status["top_blocker_gate_ids"] == BLOCKER_IDS

    note = report["delivery_note"]
    assert note["note_target"]["candidate_key"] == CANDIDATE_KEY
    assert note["note_target"]["anchor_idx"] == ANCHOR_IDX
    assert note["note_target"]["formulation_profile"] == FORMULATION_PROFILE
    assert note["note_target"]["branch_ids"] == [
        "ingest_review",
        "acceptance_authorization",
    ]
    assert [entry["branch_id"] for entry in note["read_first"]] == [
        "ingest_review",
        "acceptance_authorization",
    ]
    assert [entry["gate_id"] for entry in note["top_blockers"]] == BLOCKER_IDS
    false_state_ids = [entry["state_id"] for entry in note["states_that_remain_false"]]
    assert "reviewed_runtime_patch_exists" in false_state_ids
    assert "runtime_enablement_allowed" in false_state_ids
    assert "proof_source" in false_state_ids
    assert "solver_invoked" in false_state_ids
    assert "actual_human_review_has_happened" in false_state_ids
    assert "actual_human_authorization_review_happened" in false_state_ids
    assert any(
        "repo-side review state" in entry
        for entry in note["what_this_package_does_not_do"]
    )
    assert "do not treat this note as human review completion" in note[
        "delivery_summary"
    ]

    failed_checks = [check for check in report["checks"] if check["status"] == "fail"]
    assert failed_checks == []

    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_delivery_note_text(
            report
        )
    )
    assert "Delivery Note" in markdown
    assert "States That Remain False" in markdown
    assert "delivery_note_ready=True" in text


def test_anchor119_row_domain_delivery_note_missing_upstream(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _, final_handoff_path = _build_ready_upstream_artifacts(tmp_path)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_delivery_note(
        project_root,
        manual_review_package_index_path=tmp_path / "missing_package_index.json",
        final_human_handoff_note_path=final_handoff_path,
    )

    assert report["status"]["delivery_note_ready"] is False
    assert report["status"]["recommended_next_step"] == "repair_delivery_note_inputs"
    assert "manual_review_package_index_present" in report["status"][
        "missing_ready_gate_ids"
    ]
    assert "manual_review_package_index_ready" in report["status"][
        "missing_ready_gate_ids"
    ]
    checks = {entry["check_id"]: entry for entry in report["checks"]}
    assert checks["manual_review_package_index_present"]["status"] == "fail"
    assert checks["manual_review_package_index_ready"]["status"] == "fail"
    assert checks["final_human_handoff_note_present"]["status"] == "pass"


def test_anchor119_row_domain_delivery_note_cli_write_and_no_write(
    tmp_path: Path,
) -> None:
    script_path = (
        Path(__file__).resolve().parents[5]
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_delivery_note.py"
    )
    project_root = tmp_path / "project"
    package_index_path, final_handoff_path = _build_ready_upstream_artifacts(tmp_path)
    output_dir = tmp_path / "out"

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(tmp_path / "pycache")
    existing_pythonpath = env.get("PYTHONPATH")
    repo_root = str(Path(__file__).resolve().parents[5])
    env["PYTHONPATH"] = (
        repo_root if not existing_pythonpath else repo_root + os.pathsep + existing_pythonpath
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--manual-review-package-index",
            str(package_index_path),
            "--final-human-handoff-note",
            str(final_handoff_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[5]),
    )
    assert "delivery_note_ready=True" in no_write.stdout
    assert "top_blocker_gate_ids=" in no_write.stdout
    assert not output_dir.exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--manual-review-package-index",
            str(package_index_path),
            "--final-human-handoff-note",
            str(final_handoff_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[5]),
    )
    assert "anchor119_row_domain_delivery_note_json=" in write_run.stdout

    json_path = output_dir / "anchor119_row_domain_delivery_note.json"
    md_path = output_dir / "anchor119_row_domain_delivery_note.md"
    txt_path = output_dir / "anchor119_row_domain_delivery_note.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["status"]["delivery_note_ready"] is True
