from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.package_artifact_consistency_audit import (
    build_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit,
    render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_text,
)

CANDIDATE_KEY = "67x13"
ANCHOR_IDX = 119
FORMULATION_PROFILE = "joined_xy_block64_all_templates"
PACKAGE_ID = "anchor119_manual_review_package_across_ingest_and_acceptance_branches"
BLOCKER_SPECS = [
    (
        "reviewed_runtime_patch_exists",
        ["ingest_review", "acceptance_authorization"],
        "The reviewed runtime patch record does not exist yet.",
    ),
    (
        "production_acceptance_refresh_completed",
        ["ingest_review"],
        "Production acceptance refresh is still pending.",
    ),
    (
        "reviewer_signed_record_supplied_for_review",
        ["ingest_review"],
        "No reviewer-signed record has been supplied yet.",
    ),
    (
        "reviewer_signed_record_validates_against_locked_contract",
        ["ingest_review"],
        "No reviewer-signed record has been validated yet.",
    ),
    (
        "separate_manual_ingest_review_approved",
        ["ingest_review"],
        "No separate manual ingest approval exists yet.",
    ),
]
BLOCKER_IDS = [entry[0] for entry in BLOCKER_SPECS]
FALSE_STATE_SPECS = [
    (
        "repo_side_review_state_updated",
        ["ingest_review"],
        "Repo-side review state must remain unchanged.",
    ),
    (
        "reviewed_runtime_patch_exists",
        ["ingest_review", "acceptance_authorization"],
        "The reviewed runtime patch record still does not exist.",
    ),
    (
        "runtime_enablement_allowed",
        ["ingest_review", "acceptance_authorization"],
        "Runtime enablement remains blocked.",
    ),
    (
        "proof_source",
        ["ingest_review", "acceptance_authorization"],
        "This package remains non-proof.",
    ),
    (
        "candidate_elimination_claim",
        ["ingest_review", "acceptance_authorization"],
        "This package must not claim candidate elimination.",
    ),
    (
        "solver_invoked",
        ["ingest_review", "acceptance_authorization"],
        "This package remains no-solve.",
    ),
    (
        "actual_human_review_has_happened",
        ["ingest_review"],
        "No actual human ingest review has happened.",
    ),
    (
        "execution_authorized",
        ["ingest_review"],
        "Execution is not authorized.",
    ),
    (
        "future_manual_acceptance_authorization_review_prerequisites_met",
        ["acceptance_authorization"],
        "Acceptance-authorization prerequisites remain blocked.",
    ),
    (
        "acceptance_execution_authorized",
        ["acceptance_authorization"],
        "Acceptance execution is not authorized.",
    ),
    (
        "acceptance_executed",
        ["acceptance_authorization"],
        "Acceptance has not been executed.",
    ),
    (
        "actual_human_authorization_review_happened",
        ["acceptance_authorization"],
        "No actual human authorization review has happened.",
    ),
]
FALSE_STATE_IDS = [entry[0] for entry in FALSE_STATE_SPECS]
PACKAGE_ENTRYPOINTS = [
    (
        "ingest-review",
        "ingest_review_cover_note",
        ".artifacts/example/ingest_review_cover_note.json",
    ),
    (
        "ingest-review",
        "ingest_review_operator_handoff_bundle",
        ".artifacts/example/ingest_review_operator_handoff_bundle.json",
    ),
    (
        "acceptance-authorization",
        "acceptance_authorization_cover_note",
        ".artifacts/example/acceptance_authorization_cover_note.json",
    ),
    (
        "acceptance-authorization",
        "acceptance_authorization_operator_handoff_bundle",
        ".artifacts/example/acceptance_authorization_operator_handoff_bundle.json",
    ),
]
READ_FIRST_ENTRYPOINTS = [
    (
        "ingest_review",
        "Ingest Review",
        "ingest_review_cover_note",
        ".artifacts/example/ingest_review_cover_note.json",
    ),
    (
        "acceptance_authorization",
        "Acceptance Authorization",
        "acceptance_authorization_cover_note",
        ".artifacts/example/acceptance_authorization_cover_note.json",
    ),
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _metadata(source: str) -> dict[str, object]:
    return {
        "source": source,
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
    }


def _branches_for_package(branches: list[str]) -> list[str]:
    return [branch.replace("_", "-") for branch in branches]


def _blocker_entries(*, hyphenated_branches: bool) -> list[dict[str, object]]:
    entries = []
    for gate_id, branches, detail in BLOCKER_SPECS:
        branch_ids = (
            _branches_for_package(branches) if hyphenated_branches else list(branches)
        )
        entries.append(
            {
                "gate_id": gate_id,
                "branches": branch_ids,
                "current_value": False,
                "detail": detail,
            }
        )
    return entries


def _false_state_entries(
    *, hyphenated_branches: bool, include_locked_false: bool
) -> list[dict[str, object]]:
    entries = []
    for state_id, branches, detail in FALSE_STATE_SPECS:
        branch_ids = (
            _branches_for_package(branches) if hyphenated_branches else list(branches)
        )
        entry: dict[str, object] = {
            "state_id": state_id,
            "branches": branch_ids,
            "current_value": False,
            "detail": detail,
        }
        if include_locked_false:
            entry["locked_false"] = True
        entries.append(entry)
    return entries


def _package_index_json() -> dict[str, object]:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_v1"
        ),
        "status": {
            "manual_review_package_index_ready": True,
            "global_blocker_gate_ids": list(BLOCKER_IDS),
        },
        "package_target": {
            "package_id": PACKAGE_ID,
            "candidate_key": CANDIDATE_KEY,
            "anchor_idx": ANCHOR_IDX,
            "formulation_profile": FORMULATION_PROFILE,
            "branches": ["ingest-review", "acceptance-authorization"],
        },
        "primary_entrypoints": [
            {
                "branch_id": branch_id,
                "artifact_id": artifact_id,
                "path": artifact_path,
            }
            for branch_id, artifact_id, artifact_path in PACKAGE_ENTRYPOINTS
        ],
        "global_blockers": _blocker_entries(hyphenated_branches=True),
        "preserved_false_states": {
            entry["state_id"]: entry
            for entry in _false_state_entries(
                hyphenated_branches=True, include_locked_false=True
            )
        },
    }


def _final_handoff_note_json() -> dict[str, object]:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_final_human_handoff_note_v1"
        ),
        "candidate": {
            "key": CANDIDATE_KEY,
            "anchor_idx": ANCHOR_IDX,
            "formulation_profile": FORMULATION_PROFILE,
        },
        "status": {
            "final_human_handoff_note_ready": True,
            "still_blocked_gate_ids": list(BLOCKER_IDS),
        },
        "final_human_handoff_note": {
            "note_target": {
                "candidate_key": CANDIDATE_KEY,
                "anchor_idx": ANCHOR_IDX,
                "formulation_profile": FORMULATION_PROFILE,
                "branch_ids": ["ingest_review", "acceptance_authorization"],
            },
            "read_this_first": [
                {
                    "branch_id": branch_id,
                    "branch_label": branch_label,
                    "artifact_id": artifact_id,
                    "artifact_path": artifact_path,
                    "why": "Review-only entrypoint.",
                }
                for branch_id, branch_label, artifact_id, artifact_path in READ_FIRST_ENTRYPOINTS
            ],
            "still_blocked": _blocker_entries(hyphenated_branches=False),
            "still_false": _false_state_entries(
                hyphenated_branches=False, include_locked_false=False
            ),
        },
    }


def _delivery_note_json() -> dict[str, object]:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_delivery_note_v1"
        ),
        "status": {
            "delivery_note_ready": True,
            "top_blocker_gate_ids": list(BLOCKER_IDS),
            "required_false_state_ids": list(FALSE_STATE_IDS),
        },
        "delivery_note": {
            "note_target": {
                "package_id": PACKAGE_ID,
                "candidate_key": CANDIDATE_KEY,
                "anchor_idx": ANCHOR_IDX,
                "formulation_profile": FORMULATION_PROFILE,
                "branch_ids": ["ingest_review", "acceptance_authorization"],
            },
            "read_first": [
                {
                    "order": index,
                    "branch_id": branch_id,
                    "branch_label": branch_label,
                    "artifact_id": artifact_id,
                    "artifact_path": artifact_path,
                    "why": "Review-only entrypoint.",
                }
                for index, (
                    branch_id,
                    branch_label,
                    artifact_id,
                    artifact_path,
                ) in enumerate(READ_FIRST_ENTRYPOINTS, start=1)
            ],
            "top_blockers": _blocker_entries(hyphenated_branches=False),
            "states_that_remain_false": _false_state_entries(
                hyphenated_branches=False, include_locked_false=True
            ),
        },
    }


def _guarded_precheck_spec_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": "phase3b_anchor119_guarded_precheck_spec_v1",
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
        },
        "status": {
            "completed": True,
            "outcome": "guarded_precheck_spec_ready_for_review",
            "all_gates_pass": True,
        },
    }


def _startline_manifest_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": "phase3b_startline_manifest_v1",
            "project_root": "/synthetic/project",
        },
        "exact_source_of_truth_hashes": {},
    }


def _b5a_operator_summary_json() -> dict[str, object]:
    return {
        "metadata": {
            "source": "phase3b_b5_anchor_sprint_summary_v1",
            "project_root": "E:\\synthetic_phase3b_b5a",
        },
        "status": {
            "campaign_present": True,
            "telemetry_present": True,
            "anchor_found": False,
            "outcome": "triage_required",
        },
    }


def _build_ready_upstream_artifacts(base_dir: Path) -> tuple[Path, Path, Path]:
    package_index_path = base_dir / "manual_review_package_index.json"
    final_handoff_path = base_dir / "final_human_handoff_note.json"
    delivery_note_path = base_dir / "delivery_note.json"
    _write_json(package_index_path, _package_index_json())
    _write_json(final_handoff_path, _final_handoff_note_json())
    _write_json(delivery_note_path, _delivery_note_json())
    return package_index_path, final_handoff_path, delivery_note_path


def _build_ready_dynamic_review_artifacts(base_dir: Path) -> tuple[Path, Path, Path]:
    guarded_precheck_spec_path = base_dir / "guarded_precheck_spec.json"
    startline_manifest_path = base_dir / "startline_manifest.json"
    b5a_operator_summary_path = base_dir / "operator_summary.json"
    _write_json(guarded_precheck_spec_path, _guarded_precheck_spec_json())
    _write_json(startline_manifest_path, _startline_manifest_json())
    _write_json(b5a_operator_summary_path, _b5a_operator_summary_json())
    return guarded_precheck_spec_path, startline_manifest_path, b5a_operator_summary_path


def test_anchor119_row_domain_package_artifact_consistency_audit_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    package_index_path, final_handoff_path, delivery_note_path = (
        _build_ready_upstream_artifacts(tmp_path)
    )
    guarded_precheck_spec_path, startline_manifest_path, b5a_operator_summary_path = (
        _build_ready_dynamic_review_artifacts(tmp_path)
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit(
            project_root,
            manual_review_package_index_path=package_index_path,
            final_human_handoff_note_path=final_handoff_path,
            delivery_note_path=delivery_note_path,
            guarded_precheck_spec_path=guarded_precheck_spec_path,
            startline_manifest_path=startline_manifest_path,
            b5a_operator_summary_path=b5a_operator_summary_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_v1"
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
    assert status["package_artifact_consistency_audit_ready"] is True
    assert status["all_consistency_checks_pass"] is True
    assert status["missing_ready_gate_ids"] == []
    assert (
        status["recommended_next_step"]
        == "carry_forward_review_only_package_artifacts_without_execution_authorization"
    )

    audit_target = report["audit_target"]
    assert audit_target["package_id"] == PACKAGE_ID
    assert audit_target["candidate_key"] == CANDIDATE_KEY
    assert audit_target["anchor_idx"] == ANCHOR_IDX
    assert audit_target["formulation_profile"] == FORMULATION_PROFILE
    assert audit_target["branch_ids"] == [
        "ingest_review",
        "acceptance_authorization",
    ]

    blocker_alignment = report["blocker_alignment"]
    assert blocker_alignment["all_blocker_ids_match"] is True
    assert blocker_alignment["package_index_global_blocker_ids"] == BLOCKER_IDS
    assert blocker_alignment["final_handoff_still_blocked_gate_ids"] == BLOCKER_IDS
    assert blocker_alignment["delivery_note_top_blocker_gate_ids"] == BLOCKER_IDS
    assert all(entry["all_consistent"] for entry in blocker_alignment["blockers"])

    false_state_alignment = report["false_state_alignment"]
    assert false_state_alignment["all_false_state_ids_match"] is True
    assert false_state_alignment["package_index_state_ids"] == FALSE_STATE_IDS
    assert false_state_alignment["final_handoff_state_ids"] == FALSE_STATE_IDS
    assert false_state_alignment["delivery_note_state_ids"] == FALSE_STATE_IDS
    assert all(entry["all_consistent"] for entry in false_state_alignment["states"])

    entrypoint_alignment = report["entrypoint_alignment"]
    assert entrypoint_alignment["all_entrypoints_match"] is True
    assert [entry["branch_id"] for entry in entrypoint_alignment["branches"]] == [
        "ingest_review",
        "acceptance_authorization",
    ]
    assert all(entry["all_consistent"] for entry in entrypoint_alignment["branches"])

    dynamic_artifacts = report["dynamic_review_artifacts"]
    assert dynamic_artifacts["guarded_precheck_spec"]["present"] is True
    assert dynamic_artifacts["guarded_precheck_spec"]["ready"] is True
    assert dynamic_artifacts["startline_manifest"]["present"] is True
    assert dynamic_artifacts["b5a_operator_summary"]["present"] is True

    failed_checks = [
        check for check in report["consistency_checks"] if check["status"] == "fail"
    ]
    assert failed_checks == []

    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit_text(
            report
        )
    )
    assert "Consistency Checks" in markdown
    assert "Dynamic Review Default Artifacts" in markdown
    assert "Blocker Alignment" in markdown
    assert "Entrypoint Alignment" in markdown
    assert "package_artifact_consistency_audit_ready=True" in text
    assert "all_consistency_checks_pass=True" in text
    assert "dynamic_review_default_artifacts_present=True" in text


def test_anchor119_row_domain_package_artifact_consistency_audit_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    package_index_path, final_handoff_path, _ = _build_ready_upstream_artifacts(tmp_path)
    guarded_precheck_spec_path, startline_manifest_path, b5a_operator_summary_path = (
        _build_ready_dynamic_review_artifacts(tmp_path)
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit(
            project_root,
            manual_review_package_index_path=package_index_path,
            final_human_handoff_note_path=final_handoff_path,
            delivery_note_path=tmp_path / "missing_delivery_note.json",
            guarded_precheck_spec_path=guarded_precheck_spec_path,
            startline_manifest_path=startline_manifest_path,
            b5a_operator_summary_path=b5a_operator_summary_path,
        )
    )

    assert report["status"]["package_artifact_consistency_audit_ready"] is False
    assert report["status"]["all_consistency_checks_pass"] is False
    assert report["status"]["recommended_next_step"] == (
        "repair_package_artifact_consistency_inputs"
    )
    assert "delivery_note_present" in report["status"]["missing_ready_gate_ids"]
    assert "delivery_note_ready" in report["status"]["missing_ready_gate_ids"]

    checks = {entry["check_id"]: entry for entry in report["consistency_checks"]}
    assert checks["manual_review_package_index_present"]["status"] == "pass"
    assert checks["final_human_handoff_note_present"]["status"] == "pass"
    assert checks["delivery_note_present"]["status"] == "fail"
    assert checks["delivery_note_ready"]["status"] == "fail"


def test_anchor119_row_domain_package_artifact_consistency_audit_missing_dynamic_artifact(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    package_index_path, final_handoff_path, delivery_note_path = (
        _build_ready_upstream_artifacts(tmp_path)
    )
    _, startline_manifest_path, b5a_operator_summary_path = (
        _build_ready_dynamic_review_artifacts(tmp_path)
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_package_artifact_consistency_audit(
            project_root,
            manual_review_package_index_path=package_index_path,
            final_human_handoff_note_path=final_handoff_path,
            delivery_note_path=delivery_note_path,
            guarded_precheck_spec_path=tmp_path / "missing_guarded_precheck_spec.json",
            startline_manifest_path=startline_manifest_path,
            b5a_operator_summary_path=b5a_operator_summary_path,
        )
    )

    assert report["status"]["package_artifact_consistency_audit_ready"] is False
    assert "guarded_precheck_spec_present" in report["status"]["missing_ready_gate_ids"]
    assert "guarded_precheck_spec_ready" in report["status"]["missing_ready_gate_ids"]
    assert (
        "dynamic_review_default_artifacts_present"
        in report["status"]["missing_ready_gate_ids"]
    )
    checks = {entry["check_id"]: entry for entry in report["consistency_checks"]}
    assert checks["guarded_precheck_spec_present"]["status"] == "fail"
    assert checks["dynamic_review_default_artifacts_present"]["status"] == "fail"


def test_anchor119_row_domain_package_artifact_consistency_audit_cli_write_and_no_write(
    tmp_path: Path,
) -> None:
    script_path = (
        Path(__file__).resolve().parents[5]
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_package_artifact_consistency_audit.py"
    )
    project_root = tmp_path / "project"
    package_index_path, final_handoff_path, delivery_note_path = (
        _build_ready_upstream_artifacts(tmp_path)
    )
    guarded_precheck_spec_path, startline_manifest_path, b5a_operator_summary_path = (
        _build_ready_dynamic_review_artifacts(tmp_path)
    )
    output_dir = tmp_path / "out"

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(tmp_path / "pycache")
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
            "--manual-review-package-index",
            str(package_index_path),
            "--final-human-handoff-note",
            str(final_handoff_path),
            "--delivery-note",
            str(delivery_note_path),
            "--guarded-precheck-spec",
            str(guarded_precheck_spec_path),
            "--startline-manifest",
            str(startline_manifest_path),
            "--b5a-operator-summary",
            str(b5a_operator_summary_path),
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
    assert "package_artifact_consistency_audit_ready=True" in no_write.stdout
    assert "all_consistency_checks_pass=True" in no_write.stdout
    assert "remaining_blocker_gate_ids=" in no_write.stdout
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
            "--delivery-note",
            str(delivery_note_path),
            "--guarded-precheck-spec",
            str(guarded_precheck_spec_path),
            "--startline-manifest",
            str(startline_manifest_path),
            "--b5a-operator-summary",
            str(b5a_operator_summary_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[5]),
    )
    assert (
        "anchor119_row_domain_package_artifact_consistency_audit_json="
        in write_run.stdout
    )

    json_path = output_dir / "anchor119_row_domain_package_artifact_consistency_audit.json"
    md_path = output_dir / "anchor119_row_domain_package_artifact_consistency_audit.md"
    txt_path = output_dir / "anchor119_row_domain_package_artifact_consistency_audit.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["status"]["package_artifact_consistency_audit_ready"] is True
    assert payload["status"]["all_consistency_checks_pass"] is True
