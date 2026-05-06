from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note import (
    build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_text,
)

CANDIDATE_KEY = "67x13"
ANCHOR_IDX = 119
FORMULATION_PROFILE = "joined_xy_block64_all_templates"
RECORD_IDENTITY = "reviewed_runtime_patch_signoff_record_v0::67x13::anchor_119"
TARGET_RECORD_TYPE = "reviewed_runtime_patch_signoff_record_v0"
SCOPE = (
    "candidate=67x13, anchor_idx=119, joined_xy_block64_all_templates, "
    "anchor119 fixed-anchor row-domain/count bridge"
)
INSTRUCTION_PACKET_PATH = (
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_20260424/"
    "anchor119_row_domain_ingest_review_instruction_packet.json"
)
OPERATOR_HANDOFF_BUNDLE_PATH = (
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_ingest_review_operator_handoff_bundle.json"
)
VALIDATOR_PATH = (
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/"
    "anchor119_row_domain_ingest_review_record_validator.json"
)
EXAMPLE_BUNDLE_PATH = (
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/"
    "anchor119_row_domain_ingest_review_record_example_bundle.json"
)
CURRENT_BLOCKER_IDS = [
    "reviewed_runtime_patch_exists",
    "production_acceptance_refresh_completed",
    "reviewer_signed_record_supplied_for_review",
    "reviewer_signed_record_validates_against_locked_contract",
    "separate_manual_ingest_review_approved",
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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


def _candidate_json() -> dict:
    return {
        "key": CANDIDATE_KEY,
        "anchor_idx": ANCHOR_IDX,
        "formulation_profile": FORMULATION_PROFILE,
    }


def _instruction_packet_json() -> dict:
    return {
        "metadata": _contract_metadata(
            "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_v1"
        ),
        "candidate": _candidate_json(),
        "status": {
            "ingest_review_instruction_packet_ready": True,
            "upstream_handoff_bundle_ready": True,
            "contract_compatible": True,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
        },
        "ingest_review_instruction_packet": {
            "packet_target": {
                "operator_role": "future_manual_ingest_review_operator",
                "candidate_key": CANDIDATE_KEY,
                "anchor_idx": ANCHOR_IDX,
                "formulation_profile": FORMULATION_PROFILE,
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": RECORD_IDENTITY,
                "target_record_type": TARGET_RECORD_TYPE,
                "scope": SCOPE,
                "proposed_field_value_if_approved": True,
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
            },
            "open_these_first": [
                {
                    "order": 1,
                    "artifact_id": "ingest_review_operator_handoff_bundle",
                    "path": OPERATOR_HANDOFF_BUNDLE_PATH,
                    "why": "Authoritative entrypoint for the future manual ingest-review path.",
                },
                {
                    "order": 2,
                    "artifact_id": "ingest_review_record_validator",
                    "path": VALIDATOR_PATH,
                    "why": "Read the exact future completed ingest-review record contract.",
                },
                {
                    "order": 3,
                    "artifact_id": "ingest_review_record_example_bundle",
                    "path": EXAMPLE_BUNDLE_PATH,
                    "why": "Synthetic reference only.",
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
                "Do not claim that any actual human ingest review has already happened.",
                "Do not claim candidate elimination or any solver-backed result from this packet.",
                "Do not update repo-side review state from this packet.",
                "Do not imply reviewed_runtime_patch_exists=true.",
                "Do not imply runtime_enablement_allowed=true.",
                "Do not authorize execution or runtime enablement.",
            ],
        },
        "still_blocked_gate_ids": list(CURRENT_BLOCKER_IDS),
        "gates": [
            {
                "gate_id": gate_id,
                "satisfied": False,
                "blocking": True,
                "detail": f"{gate_id} remains blocked.",
            }
            for gate_id in CURRENT_BLOCKER_IDS
        ],
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
                "review_state_kind": "repo_side_review_state",
                "tracked_field": "reviewed_runtime_patch_exists",
                "record_identity": RECORD_IDENTITY,
                "target_record_type": TARGET_RECORD_TYPE,
                "scope": SCOPE,
                "proposed_field_value_if_approved": True,
                "actual_human_review_has_happened": False,
                "execution_authorized": False,
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
            "explicit_non_goals": [
                "Do not treat this bundle as an actual completed ingest review.",
                "Do not imply any actual human review has happened.",
            ],
            "disallowed_actions": [
                "Do not run solver-backed search or claim candidate elimination from this bundle.",
                "Do not mutate repo-side review state or runtime enablement state here.",
            ],
        },
        "still_blocked_gate_ids": CURRENT_BLOCKER_IDS[:2],
        "gates": [
            {
                "gate_id": "reviewed_runtime_patch_exists",
                "satisfied": False,
                "blocking": True,
                "detail": "Reviewed runtime patch does not exist yet.",
            },
            {
                "gate_id": "production_acceptance_refresh_completed",
                "satisfied": False,
                "blocking": True,
                "detail": "Production acceptance refresh remains incomplete.",
            },
        ],
    }


def _write_upstream_fixtures(project_root: Path) -> dict[str, Path]:
    instruction_packet_path = project_root / INSTRUCTION_PACKET_PATH
    operator_handoff_bundle_path = project_root / OPERATOR_HANDOFF_BUNDLE_PATH
    _write_json(instruction_packet_path, _instruction_packet_json())
    _write_json(operator_handoff_bundle_path, _operator_handoff_bundle_json())
    return {
        "instruction_packet": instruction_packet_path,
        "operator_handoff_bundle": operator_handoff_bundle_path,
    }


def test_anchor119_row_domain_ingest_review_cover_note_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note(
        project_root,
        ingest_review_instruction_packet_path=paths["instruction_packet"],
        ingest_review_operator_handoff_bundle_path=paths["operator_handoff_bundle"],
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_v1"
    )
    assert report["metadata"]["review_only"] is True
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["ingest_review_cover_note_ready"] is True
    assert report["status"]["upstream_instruction_packet_ready"] is True
    assert report["status"]["upstream_operator_handoff_bundle_ready"] is True
    assert report["status"]["contract_compatible"] is True
    assert report["status"]["repo_side_review_state_updated"] is False
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["missing_ready_gate_ids"] == []
    cover_note = report["ingest_review_cover_note"]
    packet_target = cover_note["packet_target"]
    assert packet_target["candidate_key"] == CANDIDATE_KEY
    assert packet_target["anchor_idx"] == ANCHOR_IDX
    assert packet_target["record_identity"] == RECORD_IDENTITY
    assert packet_target["execution_authorized"] is False
    assert [entry["artifact_id"] for entry in cover_note["read_first"]] == [
        "ingest_review_operator_handoff_bundle",
        "ingest_review_record_validator",
        "ingest_review_record_example_bundle",
    ]
    assert [entry["gate_id"] for entry in cover_note["current_blockers"]] == CURRENT_BLOCKER_IDS
    preserved_false_states = cover_note["preserved_false_states"]
    assert preserved_false_states["repo_side_review_state_updated"] is False
    assert preserved_false_states["reviewed_runtime_patch_exists"] is False
    assert preserved_false_states["runtime_enablement_allowed"] is False
    assert preserved_false_states["proof_source"] is False
    assert preserved_false_states["solver_invoked"] is False
    assert preserved_false_states["actual_human_review_has_happened"] is False
    assert preserved_false_states["execution_authorized"] is False
    assert "Do not authorize execution." in cover_note["forbidden_claims"]
    assert "carry forward all listed blockers" in cover_note["handoff_summary"]
    failed_checks = [check for check in report["checks"] if check["status"] == "fail"]
    assert failed_checks == []
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_text(
            report
        )
    )
    assert "Ingest Review Cover Note" in markdown
    assert "Do not authorize execution." in markdown
    assert "ingest_review_cover_note_ready=True" in text


def test_anchor119_row_domain_ingest_review_cover_note_missing_upstream(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)
    paths["operator_handoff_bundle"].unlink()

    report = build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note(
        project_root,
        ingest_review_instruction_packet_path=paths["instruction_packet"],
        ingest_review_operator_handoff_bundle_path=paths["operator_handoff_bundle"],
    )

    assert report["status"]["ingest_review_cover_note_ready"] is False
    assert report["status"]["contract_compatible"] is False
    assert "operator_handoff_bundle_present" in report["status"]["missing_ready_gate_ids"]
    assert "operator_handoff_bundle_ready" in report["status"]["missing_ready_gate_ids"]
    assert "operator_handoff_bundle_contract_compatible" in report["status"][
        "missing_ready_gate_ids"
    ]
    check_by_id = {check["check_id"]: check for check in report["checks"]}
    assert check_by_id["operator_handoff_bundle_present"]["status"] == "fail"
    assert check_by_id["operator_handoff_bundle_ready"]["status"] == "fail"
    assert check_by_id["operator_handoff_bundle_contract_compatible"]["status"] == "fail"


def test_anchor119_row_domain_ingest_review_cover_note_cli_write_and_no_write(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_upstream_fixtures(project_root)
    output_dir = tmp_path / "out"
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts/build_phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note.py"
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
            "--instruction-packet",
            str(paths["instruction_packet"]),
            "--operator-handoff-bundle",
            str(paths["operator_handoff_bundle"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "ingest_review_cover_note_ready=True" in no_write.stdout
    assert "contract_compatible=True" in no_write.stdout
    assert "operator_handoff_bundle_path=" + OPERATOR_HANDOFF_BUNDLE_PATH in no_write.stdout
    assert not output_dir.exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--instruction-packet",
            str(paths["instruction_packet"]),
            "--operator-handoff-bundle",
            str(paths["operator_handoff_bundle"]),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "anchor119_row_domain_ingest_review_cover_note_json=" in write_run.stdout
    json_path = output_dir / "anchor119_row_domain_ingest_review_cover_note.json"
    md_path = output_dir / "anchor119_row_domain_ingest_review_cover_note.md"
    txt_path = output_dir / "anchor119_row_domain_ingest_review_cover_note.txt"
    assert json_path.exists()
    assert md_path.exists()
    assert txt_path.exists()
    written_report = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_report["status"]["ingest_review_cover_note_ready"] is True
