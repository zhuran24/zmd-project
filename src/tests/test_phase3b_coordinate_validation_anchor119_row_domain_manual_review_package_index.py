from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index import (
    build_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index,
    render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_text,
)

CANDIDATE_KEY = "67x13"
ANCHOR_IDX = 119
FORMULATION_PROFILE = "joined_xy_block64_all_templates"
INGEST_BLOCKERS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
    "reviewer_signed_record_supplied_for_review",
    "reviewer_signed_record_validates_against_locked_contract",
    "separate_manual_ingest_review_approved",
]
ACCEPTANCE_BLOCKERS = ["reviewed_runtime_patch_exists"]

INGEST_REVIEW_COVER_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_20260424/"
    "anchor119_row_domain_ingest_review_cover_note.json"
)
INGEST_REVIEW_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_20260424/"
    "anchor119_row_domain_ingest_review_instruction_packet.json"
)
INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_ingest_review_operator_handoff_bundle.json"
)
INGEST_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/"
    "anchor119_row_domain_ingest_review_record_validator.json"
)
INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/"
    "anchor119_row_domain_ingest_review_record_example_bundle.json"
)
ACCEPTANCE_AUTHORIZATION_COVER_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_20260424/"
    "anchor119_row_domain_acceptance_authorization_cover_note.json"
)
ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_20260424/"
    "anchor119_row_domain_acceptance_authorization_instruction_packet.json"
)
ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle.json"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_validator.json"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_example_bundle.json"
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _candidate_json() -> dict:
    return {
        "key": CANDIDATE_KEY,
        "anchor_idx": ANCHOR_IDX,
        "formulation_profile": FORMULATION_PROFILE,
    }


def _metadata(source: str, **extra: object) -> dict:
    payload = {
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
    payload.update(extra)
    return payload


def _ingest_preserved_false_states() -> dict:
    return {
        "repo_side_review_state_updated": False,
        "reviewed_runtime_patch_exists": False,
        "runtime_enablement_allowed": False,
        "proof_source": False,
        "candidate_elimination_claim": False,
        "solver_invoked": False,
        "actual_human_review_has_happened": False,
        "execution_authorized": False,
    }


def _acceptance_preserved_false_states() -> dict:
    return {
        "future_manual_acceptance_authorization_review_prerequisites_met": {
            "expected_value": False,
            "current_value": False,
        },
        "acceptance_execution_authorized": {
            "expected_value": False,
            "current_value": False,
        },
        "runtime_enablement_allowed": {
            "expected_value": False,
            "current_value": False,
        },
        "acceptance_executed": {
            "expected_value": False,
            "current_value": False,
        },
        "actual_human_authorization_review_happened": {
            "expected_value": False,
            "current_value": False,
        },
    }


def _ingest_cover_note_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_v1"
        ),
        "paths": {
            "ingest_review_instruction_packet": INGEST_REVIEW_INSTRUCTION_PACKET_PATH.as_posix(),
            "ingest_review_operator_handoff_bundle": INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
        },
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_cover_note_ready": True,
            "upstream_instruction_packet_ready": True,
            "upstream_operator_handoff_bundle_ready": True,
            "contract_compatible": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "missing_ready_gate_ids": [],
            "handoff_summary": "Ingest-review cover note summary.",
        },
        "ingest_review_cover_note": {
            "packet_target": {
                "package_summary": "Short ingest-review package summary.",
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "read_first": [
                {
                    "artifact_id": "ingest_review_operator_handoff_bundle",
                    "path": INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
                },
                {
                    "artifact_id": "ingest_review_record_validator",
                    "path": INGEST_REVIEW_RECORD_VALIDATOR_PATH.as_posix(),
                },
                {
                    "artifact_id": "ingest_review_record_example_bundle",
                    "path": INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH.as_posix(),
                },
            ],
            "current_blockers": [
                {"gate_id": gate_id, "detail": f"{gate_id} remains blocked."}
                for gate_id in INGEST_BLOCKERS
            ],
            "preserved_false_states": _ingest_preserved_false_states(),
            "cover_note_notice": "Review-only ingest-review cover note.",
        },
        "still_blocked_gate_ids": list(INGEST_BLOCKERS),
    }


def _ingest_instruction_packet_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_v1"
        ),
        "paths": {
            "ingest_review_operator_handoff_bundle": INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
            "ingest_review_record_validator": INGEST_REVIEW_RECORD_VALIDATOR_PATH.as_posix(),
            "ingest_review_record_example_bundle": INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH.as_posix(),
        },
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_instruction_packet_ready": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "handoff_recommendation": "Ingest-review packet recommendation.",
        },
        "ingest_review_instruction_packet": {
            "packet_target": {
                "review_step_summary": "Ingest-review packet summary.",
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "open_these_first": [
                {
                    "artifact_id": "ingest_review_operator_handoff_bundle",
                    "path": INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
                },
                {
                    "artifact_id": "ingest_review_record_validator",
                    "path": INGEST_REVIEW_RECORD_VALIDATOR_PATH.as_posix(),
                },
                {
                    "artifact_id": "ingest_review_record_example_bundle",
                    "path": INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH.as_posix(),
                },
            ],
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
            "packet_notice": "Review-only ingest-review instruction packet.",
        },
        "still_blocked_gate_ids": list(INGEST_BLOCKERS),
    }


def _ingest_operator_handoff_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_operator_handoff_bundle_ready": True,
            "contract_compatible": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "handoff_recommendation": "Ingest-review operator handoff bundle recommendation.",
        },
        "ingest_review_operator_handoff_bundle": {
            "handoff_notice": "Ingest-review operator handoff bundle.",
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
        },
        "still_blocked_gate_ids": [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
        ],
    }


def _ingest_validator_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_record_validator_ready": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "handoff_recommendation": "Ingest-review validator recommendation.",
        },
        "ingest_review_record_validator": {
            "validator_notice": "Ingest-review validator contract only."
        },
        "still_blocked_gate_ids": list(INGEST_BLOCKERS),
    }


def _ingest_example_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_record_example_bundle_ready": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "handoff_recommendation": "Ingest-review example bundle recommendation.",
        },
        "ingest_review_record_example_bundle": {
            "bundle_notice": "Synthetic ingest-review example only.",
            "actual_human_review_record": False,
            "applied_repo_state_update": False,
            "preserved_state_assertions": {
                "repo_side_review_state_updated": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
        },
        "still_blocked_gate_ids": list(INGEST_BLOCKERS),
    }


def _acceptance_cover_note_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_v1",
            no_solve=True,
            acceptance_executed=False,
        ),
        "paths": {
            "acceptance_authorization_instruction_packet": ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH.as_posix(),
            "acceptance_authorization_operator_handoff_bundle": ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
        },
        "candidate": _candidate_json(),
        "status": {
            "acceptance_authorization_cover_note_ready": True,
            "future_manual_acceptance_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "actual_human_authorization_review_happened": False,
            "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
            "handoff_summary": "Acceptance-authorization cover note summary.",
        },
        "acceptance_authorization_cover_note": {
            "packet_target": {"detail": "Acceptance cover note target."},
            "read_first": [
                {
                    "artifact_id": "acceptance_authorization_operator_handoff_bundle",
                    "artifact_path": ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
                },
                {
                    "artifact_id": "acceptance_authorization_instruction_packet",
                    "artifact_path": ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH.as_posix(),
                },
            ],
            "current_blockers": [
                {
                    "gate_id": "reviewed_runtime_patch_exists",
                    "current_value": False,
                    "detail": "reviewed_runtime_patch_exists remains blocked.",
                }
            ],
            "preserved_false_states": _acceptance_preserved_false_states(),
            "handoff_summary": "Acceptance-authorization cover note summary.",
        },
        "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
    }


def _acceptance_instruction_packet_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_v1",
            no_solve=True,
            acceptance_executed=False,
        ),
        "paths": {
            "acceptance_authorization_operator_handoff_bundle": ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
            "acceptance_authorization_review_record_validator": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH.as_posix(),
            "acceptance_authorization_review_record_example_bundle": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH.as_posix(),
        },
        "candidate": _candidate_json(),
        "status": {
            "acceptance_authorization_instruction_packet_ready": True,
            "future_manual_acceptance_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "actual_human_authorization_review_happened": False,
            "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
            "handoff_recommendation": "Acceptance instruction packet recommendation.",
        },
        "acceptance_authorization_instruction_packet": {
            "packet_target": {"detail": "Acceptance instruction packet target."},
            "open_these_first": [
                {
                    "artifact_id": "acceptance_authorization_operator_handoff_bundle",
                    "artifact_path": ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH.as_posix(),
                },
                {
                    "artifact_id": "acceptance_authorization_review_record_validator",
                    "artifact_path": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH.as_posix(),
                },
                {
                    "artifact_id": "acceptance_authorization_review_record_example_bundle",
                    "artifact_path": ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH.as_posix(),
                },
            ],
            "preserved_state_assertions": {
                "acceptance_execution_authorized": {
                    "expected_value": False,
                    "current_value": False,
                },
                "runtime_enablement_allowed": {
                    "expected_value": False,
                    "current_value": False,
                },
                "acceptance_executed": {
                    "expected_value": False,
                    "current_value": False,
                },
                "actual_human_authorization_review_happened": {
                    "expected_value": False,
                    "current_value": False,
                },
            },
            "handoff_recommendation": "Acceptance instruction packet recommendation.",
        },
        "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
    }


def _acceptance_operator_handoff_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_v1",
            no_solve=True,
            acceptance_executed=False,
        ),
        "candidate": _candidate_json(),
        "status": {
            "acceptance_authorization_operator_handoff_bundle_ready": True,
            "future_manual_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "actual_human_authorization_review_happened": False,
            "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
            "handoff_recommendation": "Acceptance operator handoff bundle recommendation.",
        },
        "acceptance_authorization_operator_handoff_bundle": {
            "handoff_recommendation": "Acceptance operator handoff bundle recommendation.",
            "reference_only_notice": "Acceptance operator handoff bundle is review-only.",
            "preserved_state_assertions": {
                "acceptance_execution_authorized": False,
                "runtime_enablement_allowed": False,
                "acceptance_executed": False,
                "actual_human_authorization_review_happened": False,
            },
        },
        "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
    }


def _acceptance_validator_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_v1",
            no_solve=True,
            acceptance_executed=False,
        ),
        "candidate": _candidate_json(),
        "status": {
            "acceptance_authorization_review_record_validator_ready": True,
            "future_manual_authorization_review_prerequisites_met": False,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "missing_prerequisite_gate_ids": list(ACCEPTANCE_BLOCKERS),
            "handoff_recommendation": "Acceptance validator recommendation.",
        },
        "acceptance_authorization_review_record_validator": {
            "validator_notice": "Acceptance validator contract only."
        },
        "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
    }


def _acceptance_example_bundle_json() -> dict:
    return {
        "metadata": _metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_v1",
            no_solve=True,
            acceptance_executed=False,
        ),
        "candidate": _candidate_json(),
        "status": {
            "acceptance_authorization_review_record_example_bundle_ready": True,
            "acceptance_execution_authorized": False,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
            "handoff_recommendation": "Acceptance example bundle recommendation.",
        },
        "acceptance_authorization_review_record_example_bundle": {
            "validator_notice": "Acceptance synthetic example only.",
            "example_only_notes": [
                "Synthetic example/demo payload only; not an actual human authorization review record."
            ],
        },
        "still_blocked_gate_ids": list(ACCEPTANCE_BLOCKERS),
    }


def _write_default_fixture_tree(project_root: Path) -> None:
    _write_json(project_root / INGEST_REVIEW_COVER_NOTE_PATH, _ingest_cover_note_json())
    _write_json(
        project_root / INGEST_REVIEW_INSTRUCTION_PACKET_PATH,
        _ingest_instruction_packet_json(),
    )
    _write_json(
        project_root / INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH,
        _ingest_operator_handoff_bundle_json(),
    )
    _write_json(
        project_root / INGEST_REVIEW_RECORD_VALIDATOR_PATH, _ingest_validator_json()
    )
    _write_json(
        project_root / INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH,
        _ingest_example_bundle_json(),
    )
    _write_json(
        project_root / ACCEPTANCE_AUTHORIZATION_COVER_NOTE_PATH,
        _acceptance_cover_note_json(),
    )
    _write_json(
        project_root / ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH,
        _acceptance_instruction_packet_json(),
    )
    _write_json(
        project_root / ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH,
        _acceptance_operator_handoff_bundle_json(),
    )
    _write_json(
        project_root / ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH,
        _acceptance_validator_json(),
    )
    _write_json(
        project_root / ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH,
        _acceptance_example_bundle_json(),
    )


def test_anchor119_manual_review_package_index_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_default_fixture_tree(project_root)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index(
        project_root
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["no_solve"] is True
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["manual_review_package_index_ready"] is True
    assert report["status"]["contract_compatible"] is True
    assert report["status"]["required_artifacts_ready"] is True
    assert report["status"]["primary_entrypoints_available"] is True
    assert report["status"]["missing_ready_gate_ids"] == []
    assert report["package_target"]["candidate_key"] == CANDIDATE_KEY
    assert report["package_target"]["anchor_idx"] == ANCHOR_IDX
    assert report["package_target"]["formulation_profile"] == FORMULATION_PROFILE

    primary_entrypoints = report["primary_entrypoints"]
    assert [entry["artifact_id"] for entry in primary_entrypoints] == [
        "ingest_review_cover_note",
        "ingest_review_operator_handoff_bundle",
        "acceptance_authorization_cover_note",
        "acceptance_authorization_operator_handoff_bundle",
    ]

    branch_index = report["branch_artifact_index"]
    assert [
        artifact["artifact_id"]
        for artifact in branch_index["ingest-review"]["artifacts"]
    ] == [
        "ingest_review_cover_note",
        "ingest_review_instruction_packet",
        "ingest_review_operator_handoff_bundle",
        "ingest_review_record_validator",
        "ingest_review_record_example_bundle",
    ]
    assert [
        artifact["artifact_id"]
        for artifact in branch_index["acceptance-authorization"]["artifacts"]
    ] == [
        "acceptance_authorization_cover_note",
        "acceptance_authorization_instruction_packet",
        "acceptance_authorization_operator_handoff_bundle",
        "acceptance_authorization_review_record_validator",
        "acceptance_authorization_review_record_example_bundle",
    ]

    assert [entry["artifact_id"] for entry in report["synthetic_reference_artifacts"]] == [
        "ingest_review_record_example_bundle",
        "acceptance_authorization_review_record_example_bundle",
    ]
    contract_ids = {
        entry["artifact_id"] for entry in report["contract_artifacts"]
    }
    assert "ingest_review_record_validator" in contract_ids
    assert "acceptance_authorization_review_record_validator" in contract_ids

    blocker_ids = [entry["gate_id"] for entry in report["global_blockers"]]
    assert blocker_ids == sorted(
        [
            "reviewed_runtime_patch_exists",
            "production_acceptance_refresh_completed",
            "reviewer_signed_record_supplied_for_review",
            "reviewer_signed_record_validates_against_locked_contract",
            "separate_manual_ingest_review_approved",
        ]
    )

    preserved_false_states = report["preserved_false_states"]
    assert preserved_false_states["repo_side_review_state_updated"]["locked_false"] is True
    assert preserved_false_states["reviewed_runtime_patch_exists"]["locked_false"] is True
    assert preserved_false_states["runtime_enablement_allowed"]["locked_false"] is True
    assert (
        preserved_false_states[
            "future_manual_acceptance_authorization_review_prerequisites_met"
        ]["locked_false"]
        is True
    )
    assert preserved_false_states["acceptance_execution_authorized"]["locked_false"] is True
    assert preserved_false_states["acceptance_executed"]["locked_false"] is True

    failed_checks = [check for check in report["checks"] if check["status"] == "fail"]
    assert failed_checks == []

    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_text(
            report
        )
    )
    assert "Manual Review Package Index" in markdown
    assert "Primary Entrypoints" in markdown
    assert "manual_review_package_index_ready=True" in text
    assert "global_blocker_gate_ids=" in text


def test_anchor119_manual_review_package_index_missing_upstream(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_default_fixture_tree(project_root)
    (project_root / ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH).unlink()

    report = build_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index(
        project_root
    )

    assert report["status"]["manual_review_package_index_ready"] is False
    assert report["status"]["contract_compatible"] is False
    assert (
        "acceptance_authorization_review_record_validator_present"
        in report["status"]["missing_ready_gate_ids"]
    )
    assert (
        "acceptance_authorization_review_record_validator_ready"
        in report["status"]["missing_ready_gate_ids"]
    )
    check_by_id = {check["check_id"]: check for check in report["checks"]}
    assert (
        check_by_id["acceptance_authorization_review_record_validator_present"]["status"]
        == "fail"
    )
    assert (
        check_by_id["acceptance_authorization_review_record_validator_ready"]["status"]
        == "fail"
    )


def test_anchor119_manual_review_package_index_cli_write_and_no_write(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_default_fixture_tree(project_root)
    output_dir = tmp_path / "out"
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index.py"
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
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "manual_review_package_index_ready=True" in no_write.stdout
    assert "contract_compatible=True" in no_write.stdout
    assert "global_blocker_gate_ids=" in no_write.stdout
    assert not output_dir.exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "anchor119_row_domain_manual_review_package_index_json=" in write_run.stdout
    json_path = output_dir / "anchor119_row_domain_manual_review_package_index.json"
    md_path = output_dir / "anchor119_row_domain_manual_review_package_index.md"
    txt_path = output_dir / "anchor119_row_domain_manual_review_package_index.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()
    written_report = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_report["status"]["manual_review_package_index_ready"] is True
