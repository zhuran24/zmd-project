from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.ingest_review_operator_handoff_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_text,
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
POST_INGEST_STILL_BLOCKED_GATE_IDS = [
    "production_acceptance_refresh_completed",
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


def _ingest_review_record_scaffold_json() -> dict:
    return {
        "metadata": _contract_metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_record_scaffold_ready": True,
            "manual_ingest_review_record_completed": False,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "ingest_review_record_scaffold": {
            "record_type": INGEST_REVIEW_RECORD_TYPE,
            "locked_target_review_state": _locked_target_review_state_json(),
            "locked_reviewer_record_handoff": _locked_handoff_json(),
            "validator_contract_reference": {
                "validator_target": "future_reviewed_runtime_patch_signoff_record_payload",
            },
            "preserved_blocked_gates": {
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
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


def _ingest_review_record_validator_json() -> dict:
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
            "locked_reviewer_record_validator_target": (
                "future_reviewed_runtime_patch_signoff_record_payload"
            ),
            "blocked_gate_contract": {
                "current_still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
                "post_ingest_still_blocked_gate_ids": list(
                    POST_INGEST_STILL_BLOCKED_GATE_IDS
                ),
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


def _ingest_review_record_example_bundle_json() -> dict:
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
            "synthetic_completed_ingest_review_record_payload": {
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
    }


def _reviewer_record_collection_json() -> dict:
    return {
        "metadata": _contract_metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "reviewer_record_collection_ready": True,
            "actual_reviewer_record_collected": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "reviewer_record_collection": {
            "target_record_identity": {
                "record_identity": RECORD_IDENTITY,
                "record_type": TARGET_RECORD_TYPE,
                "scope": SCOPE,
                "candidate_key": CANDIDATE_KEY,
                "anchor_idx": ANCHOR_IDX,
            },
            "expected_handoff": _locked_handoff_json(),
            "preserved_contract": {
                "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
            },
            "collection_state": {
                "actual_record_collected": False,
                "reviewer_signed_record_present": False,
                "reviewed_runtime_patch_exists": False,
                "runtime_enablement_allowed": False,
            },
        },
        "still_blocked_gate_ids": list(CURRENT_STILL_BLOCKED_GATE_IDS),
    }


def _write_upstream_fixtures(project_root: Path) -> dict[str, Path]:
    scaffold_path = (
        project_root
        / ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_scaffold_20260424/"
        / "anchor119_row_domain_ingest_review_record_scaffold.json"
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
    reviewer_record_collection_path = (
        project_root
        / ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_reviewer_record_collection_20260424/"
        / "anchor119_row_domain_reviewer_record_collection.json"
    )
    _write_json(scaffold_path, _ingest_review_record_scaffold_json())
    _write_json(validator_path, _ingest_review_record_validator_json())
    _write_json(example_bundle_path, _ingest_review_record_example_bundle_json())
    _write_json(reviewer_record_collection_path, _reviewer_record_collection_json())
    return {
        "scaffold": scaffold_path,
        "validator": validator_path,
        "example_bundle": example_bundle_path,
        "reviewer_record_collection": reviewer_record_collection_path,
    }


def test_anchor119_row_domain_ingest_review_operator_handoff_bundle_ready(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle(
            project_root,
            ingest_review_record_scaffold_path=paths["scaffold"],
            ingest_review_record_validator_path=paths["validator"],
            ingest_review_record_example_bundle_path=paths["example_bundle"],
            reviewer_record_collection_path=paths["reviewer_record_collection"],
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["ingest_review_operator_handoff_bundle_ready"] is True
    assert report["status"]["upstream_inputs_ready"] is True
    assert report["status"]["contract_compatible"] is True
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["missing_ready_gate_ids"] == []
    bundle = report["ingest_review_operator_handoff_bundle"]
    operator_target = bundle["operator_target"]
    assert operator_target["record_identity"] == RECORD_IDENTITY
    assert operator_target["review_step_kind"] == "manual_ingest_review_handoff"
    assert operator_target["actual_human_review_has_happened"] is False
    authoritative_inputs = bundle["authoritative_inputs"]
    assert len(authoritative_inputs) == 4
    assert all(entry["ready"] for entry in authoritative_inputs)
    assert authoritative_inputs[2]["reference_only"] is True
    locked_handoff_path_shape = bundle["locked_handoff_path_shape"]
    assert locked_handoff_path_shape["path_shape"] == HANDOFF_PATH_SHAPE
    validator_reference = bundle["validator_script_or_artifact_reference"]
    assert validator_reference["validator_target"] == (
        "future_completed_ingest_review_record_payload"
    )
    example_reference = bundle["example_bundle_reference"]
    assert example_reference["synthetic_example_is_reference_only"] is True
    preserved_state = bundle["preserved_state_assertions"]
    assert preserved_state["repo_side_review_state_updated"] is False
    assert preserved_state["reviewed_runtime_patch_exists"] is False
    assert preserved_state["runtime_enablement_allowed"] is False
    assert preserved_state["execution_authorized"] is False
    assert report["still_blocked_gate_ids"] == CURRENT_STILL_BLOCKED_GATE_IDS
    failed_checks = [check for check in report["checks"] if check["status"] == "fail"]
    assert failed_checks == []
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_text(
            report
        )
    )
    assert "Ingest Review Operator Handoff Bundle" in markdown
    assert "Synthetic example is reference only" in markdown
    assert "ingest_review_operator_handoff_bundle_ready=True" in text


def test_anchor119_row_domain_ingest_review_operator_handoff_bundle_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)
    paths["example_bundle"].unlink()

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle(
            project_root,
            ingest_review_record_scaffold_path=paths["scaffold"],
            ingest_review_record_validator_path=paths["validator"],
            ingest_review_record_example_bundle_path=paths["example_bundle"],
            reviewer_record_collection_path=paths["reviewer_record_collection"],
        )
    )

    assert report["status"]["ingest_review_operator_handoff_bundle_ready"] is False
    assert report["status"]["upstream_inputs_ready"] is False
    assert report["status"]["contract_compatible"] is False
    assert "ingest_review_record_example_bundle_present" in report["status"][
        "missing_ready_gate_ids"
    ]
    check_by_id = {check["check_id"]: check for check in report["checks"]}
    assert check_by_id["ingest_review_record_example_bundle_present"]["status"] == "fail"
    assert check_by_id["ingest_review_record_example_bundle_ready"]["status"] == "fail"


def test_anchor119_row_domain_ingest_review_operator_handoff_bundle_cli_write_and_no_write(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)
    output_dir = tmp_path / "out"
    script_path = (
        Path(__file__).resolve().parents[5]
        / "scripts/phase3b/coordinate_validation/anchor119_row_domain/build_ingest_review_operator_handoff_bundle.py"
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
            "--ingest-review-record-scaffold",
            str(paths["scaffold"]),
            "--ingest-review-record-validator",
            str(paths["validator"]),
            "--ingest-review-record-example-bundle",
            str(paths["example_bundle"]),
            "--reviewer-record-collection",
            str(paths["reviewer_record_collection"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "ingest_review_operator_handoff_bundle_ready=True" in no_write.stdout
    assert "contract_compatible=True" in no_write.stdout
    assert "locked_handoff_path_shape=" + HANDOFF_PATH_SHAPE in no_write.stdout
    assert not output_dir.exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--ingest-review-record-scaffold",
            str(paths["scaffold"]),
            "--ingest-review-record-validator",
            str(paths["validator"]),
            "--ingest-review-record-example-bundle",
            str(paths["example_bundle"]),
            "--reviewer-record-collection",
            str(paths["reviewer_record_collection"]),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "anchor119_row_domain_ingest_review_operator_handoff_bundle_json=" in write_run.stdout
    json_path = output_dir / "anchor119_row_domain_ingest_review_operator_handoff_bundle.json"
    md_path = output_dir / "anchor119_row_domain_ingest_review_operator_handoff_bundle.md"
    txt_path = output_dir / "anchor119_row_domain_ingest_review_operator_handoff_bundle.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()
    written_report = json.loads(json_path.read_text(encoding="utf-8"))
    assert (
        written_report["status"]["ingest_review_operator_handoff_bundle_ready"] is True
    )
