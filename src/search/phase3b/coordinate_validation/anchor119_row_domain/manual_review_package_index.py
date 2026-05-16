from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

MANUAL_REVIEW_PACKAGE_INDEX_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_v1"
)
INGEST_REVIEW_COVER_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_v1"
)
ACCEPTANCE_AUTHORIZATION_COVER_NOTE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_v1"
)
INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_v1"
)
ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_v1"
)
INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_v1"
)
INGEST_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_v1"
)
INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_v1"
)
ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_v1"
)
ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE = (
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_v1"
)

DEFAULT_INGEST_REVIEW_COVER_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_cover_note_20260424/"
    "anchor119_row_domain_ingest_review_cover_note.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_COVER_NOTE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_cover_note_20260424/"
    "anchor119_row_domain_acceptance_authorization_cover_note.json"
)
DEFAULT_INGEST_REVIEW_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_instruction_packet_20260424/"
    "anchor119_row_domain_ingest_review_instruction_packet.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_instruction_packet_20260424/"
    "anchor119_row_domain_acceptance_authorization_instruction_packet.json"
)
DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_ingest_review_operator_handoff_bundle.json"
)
DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_validator_20260424/"
    "anchor119_row_domain_ingest_review_record_validator.json"
)
DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_ingest_review_record_example_bundle_20260424/"
    "anchor119_row_domain_ingest_review_record_example_bundle.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_operator_handoff_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_operator_handoff_bundle.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_validator_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_validator.json"
)
DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_acceptance_authorization_review_record_example_bundle_20260424/"
    "anchor119_row_domain_acceptance_authorization_review_record_example_bundle.json"
)

SHORT_PACKAGE_SUMMARY = (
    "Unified anchor119 manual-review package index for the ingest-review and "
    "acceptance-authorization branches. It maps already-generated artifacts only, "
    "keeps the package review-only/spec-only/default-off/no-solve, and carries "
    "forward the still-false states and remaining blockers without implying any "
    "human review, repo-state mutation, runtime enablement, or execution authorization."
)
PACKAGE_NOTICE = (
    "Review-only/spec-only/default-off/no-solve package index only. This index "
    "catalogs anchor119 manual-review artifacts across both branches, but it does "
    "not update repo-side review state, does not imply reviewed_runtime_patch_exists=true, "
    "does not imply runtime_enablement_allowed=true, does not authorize execution, "
    "does not claim candidate elimination, and does not imply any actual human review "
    "or authorization review has already happened."
)


def build_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index(
    project_root: Path,
    *,
    ingest_review_cover_note_path: Optional[Path] = None,
    acceptance_authorization_cover_note_path: Optional[Path] = None,
    ingest_review_instruction_packet_path: Optional[Path] = None,
    acceptance_authorization_instruction_packet_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()

    ingest_review_cover_note_resolved = _resolve_path(
        project_root,
        ingest_review_cover_note_path
        if ingest_review_cover_note_path is not None
        else DEFAULT_INGEST_REVIEW_COVER_NOTE_PATH,
    )
    acceptance_authorization_cover_note_resolved = _resolve_path(
        project_root,
        acceptance_authorization_cover_note_path
        if acceptance_authorization_cover_note_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_COVER_NOTE_PATH,
    )
    ingest_review_instruction_packet_resolved = _resolve_path(
        project_root,
        ingest_review_instruction_packet_path
        if ingest_review_instruction_packet_path is not None
        else DEFAULT_INGEST_REVIEW_INSTRUCTION_PACKET_PATH,
    )
    acceptance_authorization_instruction_packet_resolved = _resolve_path(
        project_root,
        acceptance_authorization_instruction_packet_path
        if acceptance_authorization_instruction_packet_path is not None
        else DEFAULT_ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_PATH,
    )

    ingest_review_cover_note_report, ingest_review_cover_note_error = _load_json_mapping(
        ingest_review_cover_note_resolved
    )
    acceptance_authorization_cover_note_report, acceptance_authorization_cover_note_error = (
        _load_json_mapping(acceptance_authorization_cover_note_resolved)
    )
    ingest_review_instruction_packet_report, ingest_review_instruction_packet_error = (
        _load_json_mapping(ingest_review_instruction_packet_resolved)
    )
    acceptance_authorization_instruction_packet_report, acceptance_authorization_instruction_packet_error = (
        _load_json_mapping(acceptance_authorization_instruction_packet_resolved)
    )

    ingest_review_cover_note_meta = _mapping(
        _mapping(ingest_review_cover_note_report).get("metadata")
    )
    ingest_review_cover_note_paths = _mapping(
        _mapping(ingest_review_cover_note_report).get("paths")
    )
    ingest_review_cover_note_status = _mapping(
        _mapping(ingest_review_cover_note_report).get("status")
    )
    ingest_review_cover_note = _mapping(
        _mapping(ingest_review_cover_note_report).get("ingest_review_cover_note")
    )

    acceptance_authorization_cover_note_meta = _mapping(
        _mapping(acceptance_authorization_cover_note_report).get("metadata")
    )
    acceptance_authorization_cover_note_paths = _mapping(
        _mapping(acceptance_authorization_cover_note_report).get("paths")
    )
    acceptance_authorization_cover_note_status = _mapping(
        _mapping(acceptance_authorization_cover_note_report).get("status")
    )
    acceptance_authorization_cover_note = _mapping(
        _mapping(acceptance_authorization_cover_note_report).get(
            "acceptance_authorization_cover_note"
        )
    )

    ingest_review_instruction_packet_meta = _mapping(
        _mapping(ingest_review_instruction_packet_report).get("metadata")
    )
    ingest_review_instruction_packet_paths = _mapping(
        _mapping(ingest_review_instruction_packet_report).get("paths")
    )
    ingest_review_instruction_packet_status = _mapping(
        _mapping(ingest_review_instruction_packet_report).get("status")
    )
    ingest_review_instruction_packet = _mapping(
        _mapping(ingest_review_instruction_packet_report).get(
            "ingest_review_instruction_packet"
        )
    )

    acceptance_authorization_instruction_packet_meta = _mapping(
        _mapping(acceptance_authorization_instruction_packet_report).get("metadata")
    )
    acceptance_authorization_instruction_packet_paths = _mapping(
        _mapping(acceptance_authorization_instruction_packet_report).get("paths")
    )
    acceptance_authorization_instruction_packet_status = _mapping(
        _mapping(acceptance_authorization_instruction_packet_report).get("status")
    )
    acceptance_authorization_instruction_packet = _mapping(
        _mapping(acceptance_authorization_instruction_packet_report).get(
            "acceptance_authorization_instruction_packet"
        )
    )

    ingest_review_operator_handoff_bundle_resolved = _resolve_reference_path(
        project_root,
        [
            ingest_review_cover_note_paths.get("ingest_review_operator_handoff_bundle"),
            _artifact_path_from_entries(
                ingest_review_cover_note.get("read_first"),
                "ingest_review_operator_handoff_bundle",
            ),
            ingest_review_instruction_packet_paths.get(
                "ingest_review_operator_handoff_bundle"
            ),
            _artifact_path_from_entries(
                ingest_review_instruction_packet.get("open_these_first"),
                "ingest_review_operator_handoff_bundle",
            ),
        ],
        DEFAULT_INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_PATH,
    )
    ingest_review_record_validator_resolved = _resolve_reference_path(
        project_root,
        [
            _artifact_path_from_entries(
                ingest_review_cover_note.get("read_first"),
                "ingest_review_record_validator",
            ),
            ingest_review_instruction_packet_paths.get("ingest_review_record_validator"),
            _artifact_path_from_entries(
                ingest_review_instruction_packet.get("open_these_first"),
                "ingest_review_record_validator",
            ),
        ],
        DEFAULT_INGEST_REVIEW_RECORD_VALIDATOR_PATH,
    )
    ingest_review_record_example_bundle_resolved = _resolve_reference_path(
        project_root,
        [
            _artifact_path_from_entries(
                ingest_review_cover_note.get("read_first"),
                "ingest_review_record_example_bundle",
            ),
            ingest_review_instruction_packet_paths.get(
                "ingest_review_record_example_bundle"
            ),
            _artifact_path_from_entries(
                ingest_review_instruction_packet.get("open_these_first"),
                "ingest_review_record_example_bundle",
            ),
        ],
        DEFAULT_INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH,
    )
    acceptance_authorization_operator_handoff_bundle_resolved = _resolve_reference_path(
        project_root,
        [
            acceptance_authorization_cover_note_paths.get(
                "acceptance_authorization_operator_handoff_bundle"
            ),
            _artifact_path_from_entries(
                acceptance_authorization_cover_note.get("read_first"),
                "acceptance_authorization_operator_handoff_bundle",
            ),
            acceptance_authorization_instruction_packet_paths.get(
                "acceptance_authorization_operator_handoff_bundle"
            ),
            _artifact_path_from_entries(
                acceptance_authorization_instruction_packet.get("open_these_first"),
                "acceptance_authorization_operator_handoff_bundle",
            ),
        ],
        DEFAULT_ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_PATH,
    )
    acceptance_authorization_review_record_validator_resolved = (
        _resolve_reference_path(
            project_root,
            [
                acceptance_authorization_instruction_packet_paths.get(
                    "acceptance_authorization_review_record_validator"
                ),
                _artifact_path_from_entries(
                    acceptance_authorization_instruction_packet.get("open_these_first"),
                    "acceptance_authorization_review_record_validator",
                ),
            ],
            DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_PATH,
        )
    )
    acceptance_authorization_review_record_example_bundle_resolved = (
        _resolve_reference_path(
            project_root,
            [
                acceptance_authorization_instruction_packet_paths.get(
                    "acceptance_authorization_review_record_example_bundle"
                ),
                _artifact_path_from_entries(
                    acceptance_authorization_instruction_packet.get("open_these_first"),
                    "acceptance_authorization_review_record_example_bundle",
                ),
            ],
            DEFAULT_ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_PATH,
        )
    )

    ingest_review_operator_handoff_bundle_report, ingest_review_operator_handoff_bundle_error = (
        _load_json_mapping(ingest_review_operator_handoff_bundle_resolved)
    )
    ingest_review_record_validator_report, ingest_review_record_validator_error = (
        _load_json_mapping(ingest_review_record_validator_resolved)
    )
    ingest_review_record_example_bundle_report, ingest_review_record_example_bundle_error = (
        _load_json_mapping(ingest_review_record_example_bundle_resolved)
    )
    acceptance_authorization_operator_handoff_bundle_report, acceptance_authorization_operator_handoff_bundle_error = (
        _load_json_mapping(acceptance_authorization_operator_handoff_bundle_resolved)
    )
    acceptance_authorization_review_record_validator_report, acceptance_authorization_review_record_validator_error = (
        _load_json_mapping(acceptance_authorization_review_record_validator_resolved)
    )
    acceptance_authorization_review_record_example_bundle_report, acceptance_authorization_review_record_example_bundle_error = (
        _load_json_mapping(acceptance_authorization_review_record_example_bundle_resolved)
    )

    ingest_review_operator_handoff_bundle_meta = _mapping(
        _mapping(ingest_review_operator_handoff_bundle_report).get("metadata")
    )
    ingest_review_operator_handoff_bundle_status = _mapping(
        _mapping(ingest_review_operator_handoff_bundle_report).get("status")
    )
    ingest_review_operator_handoff_bundle = _mapping(
        _mapping(ingest_review_operator_handoff_bundle_report).get(
            "ingest_review_operator_handoff_bundle"
        )
    )

    ingest_review_record_validator_meta = _mapping(
        _mapping(ingest_review_record_validator_report).get("metadata")
    )
    ingest_review_record_validator_status = _mapping(
        _mapping(ingest_review_record_validator_report).get("status")
    )
    ingest_review_record_validator = _mapping(
        _mapping(ingest_review_record_validator_report).get(
            "ingest_review_record_validator"
        )
    )

    ingest_review_record_example_bundle_meta = _mapping(
        _mapping(ingest_review_record_example_bundle_report).get("metadata")
    )
    ingest_review_record_example_bundle_status = _mapping(
        _mapping(ingest_review_record_example_bundle_report).get("status")
    )
    ingest_review_record_example_bundle = _mapping(
        _mapping(ingest_review_record_example_bundle_report).get(
            "ingest_review_record_example_bundle"
        )
    )

    acceptance_authorization_operator_handoff_bundle_meta = _mapping(
        _mapping(acceptance_authorization_operator_handoff_bundle_report).get("metadata")
    )
    acceptance_authorization_operator_handoff_bundle_status = _mapping(
        _mapping(acceptance_authorization_operator_handoff_bundle_report).get("status")
    )
    acceptance_authorization_operator_handoff_bundle = _mapping(
        _mapping(acceptance_authorization_operator_handoff_bundle_report).get(
            "acceptance_authorization_operator_handoff_bundle"
        )
    )

    acceptance_authorization_review_record_validator_meta = _mapping(
        _mapping(acceptance_authorization_review_record_validator_report).get("metadata")
    )
    acceptance_authorization_review_record_validator_status = _mapping(
        _mapping(acceptance_authorization_review_record_validator_report).get("status")
    )
    acceptance_authorization_review_record_validator = _mapping(
        _mapping(acceptance_authorization_review_record_validator_report).get(
            "acceptance_authorization_review_record_validator"
        )
    )

    acceptance_authorization_review_record_example_bundle_meta = _mapping(
        _mapping(acceptance_authorization_review_record_example_bundle_report).get(
            "metadata"
        )
    )
    acceptance_authorization_review_record_example_bundle_status = _mapping(
        _mapping(acceptance_authorization_review_record_example_bundle_report).get(
            "status"
        )
    )
    acceptance_authorization_review_record_example_bundle = _mapping(
        _mapping(acceptance_authorization_review_record_example_bundle_report).get(
            "acceptance_authorization_review_record_example_bundle"
        )
    )

    artifact_infos: dict[str, Dict[str, Any]] = {
        "ingest_review_cover_note": _artifact_info(
            artifact_id="ingest_review_cover_note",
            branch_id="ingest-review",
            artifact_kind="cover_note",
            project_root=project_root,
            path=ingest_review_cover_note_resolved,
            report=ingest_review_cover_note_report,
            error=ingest_review_cover_note_error,
            metadata=ingest_review_cover_note_meta,
            expected_source=INGEST_REVIEW_COVER_NOTE_SOURCE,
            status=ingest_review_cover_note_status,
            ready_key="ingest_review_cover_note_ready",
            primary_entrypoint=True,
            operator_facing_summary=True,
            contract_artifact=False,
            synthetic_reference_only=False,
            detail=_first_text(
                ingest_review_cover_note.get("cover_note_notice"),
                ingest_review_cover_note_status.get("handoff_summary"),
            ),
        ),
        "ingest_review_instruction_packet": _artifact_info(
            artifact_id="ingest_review_instruction_packet",
            branch_id="ingest-review",
            artifact_kind="instruction_packet",
            project_root=project_root,
            path=ingest_review_instruction_packet_resolved,
            report=ingest_review_instruction_packet_report,
            error=ingest_review_instruction_packet_error,
            metadata=ingest_review_instruction_packet_meta,
            expected_source=INGEST_REVIEW_INSTRUCTION_PACKET_SOURCE,
            status=ingest_review_instruction_packet_status,
            ready_key="ingest_review_instruction_packet_ready",
            primary_entrypoint=False,
            operator_facing_summary=True,
            contract_artifact=True,
            synthetic_reference_only=False,
            detail=_first_text(
                ingest_review_instruction_packet.get("packet_notice"),
                ingest_review_instruction_packet_status.get("handoff_recommendation"),
            ),
        ),
        "ingest_review_operator_handoff_bundle": _artifact_info(
            artifact_id="ingest_review_operator_handoff_bundle",
            branch_id="ingest-review",
            artifact_kind="operator_handoff_bundle",
            project_root=project_root,
            path=ingest_review_operator_handoff_bundle_resolved,
            report=ingest_review_operator_handoff_bundle_report,
            error=ingest_review_operator_handoff_bundle_error,
            metadata=ingest_review_operator_handoff_bundle_meta,
            expected_source=INGEST_REVIEW_OPERATOR_HANDOFF_BUNDLE_SOURCE,
            status=ingest_review_operator_handoff_bundle_status,
            ready_key="ingest_review_operator_handoff_bundle_ready",
            primary_entrypoint=True,
            operator_facing_summary=True,
            contract_artifact=True,
            synthetic_reference_only=False,
            detail=_first_text(
                ingest_review_operator_handoff_bundle.get("handoff_notice"),
                ingest_review_operator_handoff_bundle_status.get("handoff_recommendation"),
            ),
        ),
        "ingest_review_record_validator": _artifact_info(
            artifact_id="ingest_review_record_validator",
            branch_id="ingest-review",
            artifact_kind="review_record_validator",
            project_root=project_root,
            path=ingest_review_record_validator_resolved,
            report=ingest_review_record_validator_report,
            error=ingest_review_record_validator_error,
            metadata=ingest_review_record_validator_meta,
            expected_source=INGEST_REVIEW_RECORD_VALIDATOR_SOURCE,
            status=ingest_review_record_validator_status,
            ready_key="ingest_review_record_validator_ready",
            primary_entrypoint=False,
            operator_facing_summary=False,
            contract_artifact=True,
            synthetic_reference_only=False,
            detail=_first_text(
                ingest_review_record_validator.get("validator_notice"),
                ingest_review_record_validator_status.get("handoff_recommendation"),
            ),
        ),
        "ingest_review_record_example_bundle": _artifact_info(
            artifact_id="ingest_review_record_example_bundle",
            branch_id="ingest-review",
            artifact_kind="review_record_example_bundle",
            project_root=project_root,
            path=ingest_review_record_example_bundle_resolved,
            report=ingest_review_record_example_bundle_report,
            error=ingest_review_record_example_bundle_error,
            metadata=ingest_review_record_example_bundle_meta,
            expected_source=INGEST_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
            status=ingest_review_record_example_bundle_status,
            ready_key="ingest_review_record_example_bundle_ready",
            primary_entrypoint=False,
            operator_facing_summary=False,
            contract_artifact=False,
            synthetic_reference_only=True,
            detail=_first_text(
                ingest_review_record_example_bundle.get("bundle_notice"),
                ingest_review_record_example_bundle_status.get("handoff_recommendation"),
            ),
        ),
        "acceptance_authorization_cover_note": _artifact_info(
            artifact_id="acceptance_authorization_cover_note",
            branch_id="acceptance-authorization",
            artifact_kind="cover_note",
            project_root=project_root,
            path=acceptance_authorization_cover_note_resolved,
            report=acceptance_authorization_cover_note_report,
            error=acceptance_authorization_cover_note_error,
            metadata=acceptance_authorization_cover_note_meta,
            expected_source=ACCEPTANCE_AUTHORIZATION_COVER_NOTE_SOURCE,
            status=acceptance_authorization_cover_note_status,
            ready_key="acceptance_authorization_cover_note_ready",
            primary_entrypoint=True,
            operator_facing_summary=True,
            contract_artifact=False,
            synthetic_reference_only=False,
            detail=_first_text(
                acceptance_authorization_cover_note.get("handoff_summary"),
                acceptance_authorization_cover_note_status.get("handoff_summary"),
            ),
        ),
        "acceptance_authorization_instruction_packet": _artifact_info(
            artifact_id="acceptance_authorization_instruction_packet",
            branch_id="acceptance-authorization",
            artifact_kind="instruction_packet",
            project_root=project_root,
            path=acceptance_authorization_instruction_packet_resolved,
            report=acceptance_authorization_instruction_packet_report,
            error=acceptance_authorization_instruction_packet_error,
            metadata=acceptance_authorization_instruction_packet_meta,
            expected_source=ACCEPTANCE_AUTHORIZATION_INSTRUCTION_PACKET_SOURCE,
            status=acceptance_authorization_instruction_packet_status,
            ready_key="acceptance_authorization_instruction_packet_ready",
            primary_entrypoint=False,
            operator_facing_summary=True,
            contract_artifact=True,
            synthetic_reference_only=False,
            detail=_first_text(
                acceptance_authorization_instruction_packet.get("handoff_recommendation"),
                acceptance_authorization_instruction_packet_status.get("handoff_recommendation"),
                acceptance_authorization_instruction_packet.get("reference_only_notice"),
            ),
        ),
        "acceptance_authorization_operator_handoff_bundle": _artifact_info(
            artifact_id="acceptance_authorization_operator_handoff_bundle",
            branch_id="acceptance-authorization",
            artifact_kind="operator_handoff_bundle",
            project_root=project_root,
            path=acceptance_authorization_operator_handoff_bundle_resolved,
            report=acceptance_authorization_operator_handoff_bundle_report,
            error=acceptance_authorization_operator_handoff_bundle_error,
            metadata=acceptance_authorization_operator_handoff_bundle_meta,
            expected_source=ACCEPTANCE_AUTHORIZATION_OPERATOR_HANDOFF_BUNDLE_SOURCE,
            status=acceptance_authorization_operator_handoff_bundle_status,
            ready_key="acceptance_authorization_operator_handoff_bundle_ready",
            primary_entrypoint=True,
            operator_facing_summary=True,
            contract_artifact=True,
            synthetic_reference_only=False,
            detail=_first_text(
                acceptance_authorization_operator_handoff_bundle.get(
                    "handoff_recommendation"
                ),
                acceptance_authorization_operator_handoff_bundle.get(
                    "reference_only_notice"
                ),
                acceptance_authorization_operator_handoff_bundle_status.get(
                    "handoff_recommendation"
                ),
            ),
        ),
        "acceptance_authorization_review_record_validator": _artifact_info(
            artifact_id="acceptance_authorization_review_record_validator",
            branch_id="acceptance-authorization",
            artifact_kind="review_record_validator",
            project_root=project_root,
            path=acceptance_authorization_review_record_validator_resolved,
            report=acceptance_authorization_review_record_validator_report,
            error=acceptance_authorization_review_record_validator_error,
            metadata=acceptance_authorization_review_record_validator_meta,
            expected_source=ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_VALIDATOR_SOURCE,
            status=acceptance_authorization_review_record_validator_status,
            ready_key="acceptance_authorization_review_record_validator_ready",
            primary_entrypoint=False,
            operator_facing_summary=False,
            contract_artifact=True,
            synthetic_reference_only=False,
            detail=_first_text(
                acceptance_authorization_review_record_validator.get("validator_notice"),
                acceptance_authorization_review_record_validator_status.get(
                    "handoff_recommendation"
                ),
            ),
        ),
        "acceptance_authorization_review_record_example_bundle": _artifact_info(
            artifact_id="acceptance_authorization_review_record_example_bundle",
            branch_id="acceptance-authorization",
            artifact_kind="review_record_example_bundle",
            project_root=project_root,
            path=acceptance_authorization_review_record_example_bundle_resolved,
            report=acceptance_authorization_review_record_example_bundle_report,
            error=acceptance_authorization_review_record_example_bundle_error,
            metadata=acceptance_authorization_review_record_example_bundle_meta,
            expected_source=ACCEPTANCE_AUTHORIZATION_REVIEW_RECORD_EXAMPLE_BUNDLE_SOURCE,
            status=acceptance_authorization_review_record_example_bundle_status,
            ready_key="acceptance_authorization_review_record_example_bundle_ready",
            primary_entrypoint=False,
            operator_facing_summary=False,
            contract_artifact=False,
            synthetic_reference_only=True,
            detail=_first_text(
                acceptance_authorization_review_record_example_bundle.get(
                    "validator_notice"
                ),
                acceptance_authorization_review_record_example_bundle.get(
                    "example_only_notes"
                ),
                acceptance_authorization_review_record_example_bundle_status.get(
                    "handoff_recommendation"
                ),
            ),
        ),
    }

    candidate_reports = [
        ingest_review_cover_note_report,
        ingest_review_instruction_packet_report,
        ingest_review_operator_handoff_bundle_report,
        ingest_review_record_validator_report,
        ingest_review_record_example_bundle_report,
        acceptance_authorization_cover_note_report,
        acceptance_authorization_instruction_packet_report,
        acceptance_authorization_operator_handoff_bundle_report,
        acceptance_authorization_review_record_validator_report,
        acceptance_authorization_review_record_example_bundle_report,
    ]
    candidate_key, candidate_key_locked = _locked_value(
        [_mapping(_mapping(report).get("candidate")).get("key") for report in candidate_reports],
        normalize=_normalize_text,
    )
    anchor_idx, anchor_idx_locked = _locked_value(
        [
            _mapping(_mapping(report).get("candidate")).get("anchor_idx")
            for report in candidate_reports
        ],
        normalize=_normalize_scalar,
    )
    formulation_profile, formulation_profile_locked = _locked_value(
        [
            _mapping(_mapping(report).get("candidate")).get("formulation_profile")
            for report in candidate_reports
        ],
        normalize=_normalize_text,
    )
    candidate_consistent = bool(
        candidate_key_locked and anchor_idx_locked and formulation_profile_locked
    )

    ingest_branch_reference_alignment = bool(
        _path_values_match(
            project_root,
            ingest_review_instruction_packet_resolved,
            [
                ingest_review_cover_note_paths.get("ingest_review_instruction_packet"),
            ],
        )
        and _path_values_match(
            project_root,
            ingest_review_operator_handoff_bundle_resolved,
            [
                ingest_review_cover_note_paths.get("ingest_review_operator_handoff_bundle"),
                _artifact_path_from_entries(
                    ingest_review_cover_note.get("read_first"),
                    "ingest_review_operator_handoff_bundle",
                ),
                ingest_review_instruction_packet_paths.get(
                    "ingest_review_operator_handoff_bundle"
                ),
                _artifact_path_from_entries(
                    ingest_review_instruction_packet.get("open_these_first"),
                    "ingest_review_operator_handoff_bundle",
                ),
            ],
        )
        and _path_values_match(
            project_root,
            ingest_review_record_validator_resolved,
            [
                _artifact_path_from_entries(
                    ingest_review_cover_note.get("read_first"),
                    "ingest_review_record_validator",
                ),
                ingest_review_instruction_packet_paths.get("ingest_review_record_validator"),
                _artifact_path_from_entries(
                    ingest_review_instruction_packet.get("open_these_first"),
                    "ingest_review_record_validator",
                ),
            ],
        )
        and _path_values_match(
            project_root,
            ingest_review_record_example_bundle_resolved,
            [
                _artifact_path_from_entries(
                    ingest_review_cover_note.get("read_first"),
                    "ingest_review_record_example_bundle",
                ),
                ingest_review_instruction_packet_paths.get(
                    "ingest_review_record_example_bundle"
                ),
                _artifact_path_from_entries(
                    ingest_review_instruction_packet.get("open_these_first"),
                    "ingest_review_record_example_bundle",
                ),
            ],
        )
    )
    acceptance_branch_reference_alignment = bool(
        _path_values_match(
            project_root,
            acceptance_authorization_instruction_packet_resolved,
            [
                acceptance_authorization_cover_note_paths.get(
                    "acceptance_authorization_instruction_packet"
                ),
                _artifact_path_from_entries(
                    acceptance_authorization_cover_note.get("read_first"),
                    "acceptance_authorization_instruction_packet",
                ),
            ],
        )
        and _path_values_match(
            project_root,
            acceptance_authorization_operator_handoff_bundle_resolved,
            [
                acceptance_authorization_cover_note_paths.get(
                    "acceptance_authorization_operator_handoff_bundle"
                ),
                _artifact_path_from_entries(
                    acceptance_authorization_cover_note.get("read_first"),
                    "acceptance_authorization_operator_handoff_bundle",
                ),
                acceptance_authorization_instruction_packet_paths.get(
                    "acceptance_authorization_operator_handoff_bundle"
                ),
                _artifact_path_from_entries(
                    acceptance_authorization_instruction_packet.get("open_these_first"),
                    "acceptance_authorization_operator_handoff_bundle",
                ),
            ],
        )
        and _path_values_match(
            project_root,
            acceptance_authorization_review_record_validator_resolved,
            [
                acceptance_authorization_instruction_packet_paths.get(
                    "acceptance_authorization_review_record_validator"
                ),
                _artifact_path_from_entries(
                    acceptance_authorization_instruction_packet.get("open_these_first"),
                    "acceptance_authorization_review_record_validator",
                ),
            ],
        )
        and _path_values_match(
            project_root,
            acceptance_authorization_review_record_example_bundle_resolved,
            [
                acceptance_authorization_instruction_packet_paths.get(
                    "acceptance_authorization_review_record_example_bundle"
                ),
                _artifact_path_from_entries(
                    acceptance_authorization_instruction_packet.get("open_these_first"),
                    "acceptance_authorization_review_record_example_bundle",
                ),
            ],
        )
    )

    review_only_contract_retained = all(
        _review_only_contract_retained(_mapping(_mapping(report).get("metadata")))
        for report in candidate_reports
    )

    preserved_false_states = {
        "repo_side_review_state_updated": _false_state_entry(
            state_id="repo_side_review_state_updated",
            current_false=_all_observed_false(
                [
                    ingest_review_cover_note_meta.get("repo_side_review_state_updated"),
                    ingest_review_cover_note_status.get("repo_side_review_state_updated"),
                    _mapping(
                        ingest_review_cover_note.get("preserved_false_states")
                    ).get("repo_side_review_state_updated"),
                    ingest_review_instruction_packet_meta.get(
                        "repo_side_review_state_updated"
                    ),
                    ingest_review_instruction_packet_status.get(
                        "repo_side_review_state_updated"
                    ),
                    _mapping(
                        ingest_review_instruction_packet.get("preserved_state_assertions")
                    ).get("repo_side_review_state_updated"),
                    ingest_review_operator_handoff_bundle_meta.get(
                        "repo_side_review_state_updated"
                    ),
                    ingest_review_operator_handoff_bundle_status.get(
                        "repo_side_review_state_updated"
                    ),
                    _mapping(
                        ingest_review_operator_handoff_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("repo_side_review_state_updated"),
                    ingest_review_record_validator_meta.get(
                        "repo_side_review_state_updated"
                    ),
                    ingest_review_record_validator_status.get(
                        "repo_side_review_state_updated"
                    ),
                    ingest_review_record_example_bundle_meta.get(
                        "repo_side_review_state_updated"
                    ),
                    ingest_review_record_example_bundle_status.get(
                        "repo_side_review_state_updated"
                    ),
                    _mapping(
                        ingest_review_record_example_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("repo_side_review_state_updated"),
                ]
            ),
            branches=["ingest-review"],
            artifact_ids=[
                "ingest_review_cover_note",
                "ingest_review_instruction_packet",
                "ingest_review_operator_handoff_bundle",
                "ingest_review_record_validator",
                "ingest_review_record_example_bundle",
            ],
            detail=(
                "Must remain false. No artifact in the ingest-review branch updates "
                "repo-side review state."
            ),
        ),
        "reviewed_runtime_patch_exists": _false_state_entry(
            state_id="reviewed_runtime_patch_exists",
            current_false=_all_observed_false(
                [
                    ingest_review_cover_note_status.get("reviewed_runtime_patch_exists"),
                    _mapping(
                        ingest_review_cover_note.get("preserved_false_states")
                    ).get("reviewed_runtime_patch_exists"),
                    ingest_review_instruction_packet_status.get(
                        "reviewed_runtime_patch_exists"
                    ),
                    _mapping(
                        ingest_review_instruction_packet.get("preserved_state_assertions")
                    ).get("reviewed_runtime_patch_exists"),
                    ingest_review_operator_handoff_bundle_status.get(
                        "reviewed_runtime_patch_exists"
                    ),
                    _mapping(
                        ingest_review_operator_handoff_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("reviewed_runtime_patch_exists"),
                    ingest_review_record_validator_status.get(
                        "reviewed_runtime_patch_exists"
                    ),
                    ingest_review_record_example_bundle_status.get(
                        "reviewed_runtime_patch_exists"
                    ),
                    _mapping(
                        ingest_review_record_example_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("reviewed_runtime_patch_exists"),
                    _current_blocker_value(
                        acceptance_authorization_cover_note.get("current_blockers"),
                        "reviewed_runtime_patch_exists",
                    ),
                    _blocked_gate_implies_false(
                        acceptance_authorization_cover_note_status.get(
                            "still_blocked_gate_ids"
                        ),
                        "reviewed_runtime_patch_exists",
                    ),
                    _blocked_gate_implies_false(
                        acceptance_authorization_instruction_packet_status.get(
                            "still_blocked_gate_ids"
                        ),
                        "reviewed_runtime_patch_exists",
                    ),
                    _blocked_gate_implies_false(
                        acceptance_authorization_operator_handoff_bundle_status.get(
                            "still_blocked_gate_ids"
                        ),
                        "reviewed_runtime_patch_exists",
                    ),
                    _blocked_gate_implies_false(
                        acceptance_authorization_review_record_validator_status.get(
                            "missing_prerequisite_gate_ids"
                        ),
                        "reviewed_runtime_patch_exists",
                    ),
                    _blocked_gate_implies_false(
                        _mapping(
                            acceptance_authorization_review_record_example_bundle_report
                        ).get("still_blocked_gate_ids"),
                        "reviewed_runtime_patch_exists",
                    ),
                ]
            ),
            branches=["ingest-review", "acceptance-authorization"],
            artifact_ids=list(artifact_infos.keys()),
            detail=(
                "Must remain false. Both branches still carry "
                "`reviewed_runtime_patch_exists` as a blocker or preserved false state."
            ),
        ),
        "runtime_enablement_allowed": _false_state_entry(
            state_id="runtime_enablement_allowed",
            current_false=_all_observed_false(
                [
                    ingest_review_cover_note_status.get("runtime_enablement_allowed"),
                    _mapping(
                        ingest_review_cover_note.get("preserved_false_states")
                    ).get("runtime_enablement_allowed"),
                    ingest_review_instruction_packet_status.get(
                        "runtime_enablement_allowed"
                    ),
                    _mapping(
                        ingest_review_instruction_packet.get("preserved_state_assertions")
                    ).get("runtime_enablement_allowed"),
                    ingest_review_operator_handoff_bundle_status.get(
                        "runtime_enablement_allowed"
                    ),
                    _mapping(
                        ingest_review_operator_handoff_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("runtime_enablement_allowed"),
                    ingest_review_record_validator_status.get(
                        "runtime_enablement_allowed"
                    ),
                    ingest_review_record_example_bundle_status.get(
                        "runtime_enablement_allowed"
                    ),
                    _mapping(
                        ingest_review_record_example_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("runtime_enablement_allowed"),
                    acceptance_authorization_cover_note_status.get(
                        "runtime_enablement_allowed"
                    ),
                    _mapping(
                        acceptance_authorization_cover_note.get("preserved_false_states")
                    ).get("runtime_enablement_allowed"),
                    acceptance_authorization_instruction_packet_status.get(
                        "runtime_enablement_allowed"
                    ),
                    _mapping(
                        acceptance_authorization_instruction_packet.get(
                            "preserved_state_assertions"
                        )
                    ).get("runtime_enablement_allowed"),
                    acceptance_authorization_operator_handoff_bundle_status.get(
                        "runtime_enablement_allowed"
                    ),
                    _mapping(
                        acceptance_authorization_operator_handoff_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("runtime_enablement_allowed"),
                    acceptance_authorization_review_record_validator_status.get(
                        "runtime_enablement_allowed"
                    ),
                    acceptance_authorization_review_record_example_bundle_status.get(
                        "runtime_enablement_allowed"
                    ),
                ]
            ),
            branches=["ingest-review", "acceptance-authorization"],
            artifact_ids=list(artifact_infos.keys()),
            detail=(
                "Must remain false. Neither branch enables runtime or allows runtime "
                "enablement from these review artifacts."
            ),
        ),
        "proof_source": _false_state_entry(
            state_id="proof_source",
            current_false=_all_observed_false(
                [
                    _mapping(_mapping(report).get("metadata")).get("proof_source")
                    for report in candidate_reports
                ]
            ),
            branches=["ingest-review", "acceptance-authorization"],
            artifact_ids=list(artifact_infos.keys()),
            detail=(
                "Must remain false. This package is review-only/spec-only and does "
                "not promote proof-backed semantics."
            ),
        ),
        "candidate_elimination_claim": _false_state_entry(
            state_id="candidate_elimination_claim",
            current_false=_all_observed_false(
                [
                    _mapping(_mapping(report).get("metadata")).get(
                        "candidate_elimination_claim"
                    )
                    for report in candidate_reports
                ]
            ),
            branches=["ingest-review", "acceptance-authorization"],
            artifact_ids=list(artifact_infos.keys()),
            detail=(
                "Must remain false. No artifact in this package claims candidate elimination."
            ),
        ),
        "solver_invoked": _false_state_entry(
            state_id="solver_invoked",
            current_false=_all_observed_false(
                [
                    _mapping(_mapping(report).get("metadata")).get("solver_invoked")
                    for report in candidate_reports
                ]
            ),
            branches=["ingest-review", "acceptance-authorization"],
            artifact_ids=list(artifact_infos.keys()),
            detail=(
                "Must remain false. This package is no-solve and keeps solver_invoked=false."
            ),
        ),
        "actual_human_review_has_happened": _false_state_entry(
            state_id="actual_human_review_has_happened",
            current_false=_all_observed_false(
                [
                    _mapping(ingest_review_cover_note.get("packet_target")).get(
                        "actual_human_review_has_happened"
                    ),
                    _mapping(
                        ingest_review_cover_note.get("preserved_false_states")
                    ).get("actual_human_review_has_happened"),
                    _mapping(
                        ingest_review_instruction_packet.get("packet_target")
                    ).get("actual_human_review_has_happened"),
                ]
            ),
            branches=["ingest-review"],
            artifact_ids=[
                "ingest_review_cover_note",
                "ingest_review_instruction_packet",
            ],
            detail=(
                "Must remain false. The ingest-review branch does not imply any actual "
                "human ingest review has already happened."
            ),
        ),
        "execution_authorized": _false_state_entry(
            state_id="execution_authorized",
            current_false=_all_observed_false(
                [
                    _mapping(ingest_review_cover_note.get("packet_target")).get(
                        "execution_authorized"
                    ),
                    _mapping(
                        ingest_review_cover_note.get("preserved_false_states")
                    ).get("execution_authorized"),
                    _mapping(
                        ingest_review_instruction_packet.get("packet_target")
                    ).get("execution_authorized"),
                ]
            ),
            branches=["ingest-review"],
            artifact_ids=[
                "ingest_review_cover_note",
                "ingest_review_instruction_packet",
            ],
            detail=(
                "Must remain false. The ingest-review branch does not authorize execution."
            ),
        ),
        "future_manual_acceptance_authorization_review_prerequisites_met": _false_state_entry(
            state_id="future_manual_acceptance_authorization_review_prerequisites_met",
            current_false=_all_observed_false(
                [
                    acceptance_authorization_cover_note_status.get(
                        "future_manual_acceptance_authorization_review_prerequisites_met"
                    ),
                    _mapping(
                        acceptance_authorization_cover_note.get(
                            "preserved_false_states"
                        )
                    ).get("future_manual_acceptance_authorization_review_prerequisites_met"),
                    acceptance_authorization_instruction_packet_status.get(
                        "future_manual_acceptance_authorization_review_prerequisites_met"
                    ),
                    acceptance_authorization_operator_handoff_bundle_status.get(
                        "future_manual_authorization_review_prerequisites_met"
                    ),
                    acceptance_authorization_review_record_validator_status.get(
                        "future_manual_authorization_review_prerequisites_met"
                    ),
                ]
            ),
            branches=["acceptance-authorization"],
            artifact_ids=[
                "acceptance_authorization_cover_note",
                "acceptance_authorization_instruction_packet",
                "acceptance_authorization_operator_handoff_bundle",
                "acceptance_authorization_review_record_validator",
            ],
            detail=(
                "Must remain false. Acceptance-authorization prerequisites are still blocked."
            ),
        ),
        "acceptance_execution_authorized": _false_state_entry(
            state_id="acceptance_execution_authorized",
            current_false=_all_observed_false(
                [
                    acceptance_authorization_cover_note_status.get(
                        "acceptance_execution_authorized"
                    ),
                    _mapping(
                        acceptance_authorization_cover_note.get(
                            "preserved_false_states"
                        )
                    ).get("acceptance_execution_authorized"),
                    acceptance_authorization_instruction_packet_status.get(
                        "acceptance_execution_authorized"
                    ),
                    acceptance_authorization_operator_handoff_bundle_status.get(
                        "acceptance_execution_authorized"
                    ),
                    _mapping(
                        acceptance_authorization_operator_handoff_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("acceptance_execution_authorized"),
                    acceptance_authorization_review_record_validator_status.get(
                        "acceptance_execution_authorized"
                    ),
                    acceptance_authorization_review_record_example_bundle_status.get(
                        "acceptance_execution_authorized"
                    ),
                ]
            ),
            branches=["acceptance-authorization"],
            artifact_ids=[
                "acceptance_authorization_cover_note",
                "acceptance_authorization_instruction_packet",
                "acceptance_authorization_operator_handoff_bundle",
                "acceptance_authorization_review_record_validator",
                "acceptance_authorization_review_record_example_bundle",
            ],
            detail=(
                "Must remain false. Acceptance-authorization artifacts do not authorize "
                "the locked production acceptance run."
            ),
        ),
        "acceptance_executed": _false_state_entry(
            state_id="acceptance_executed",
            current_false=_all_observed_false(
                [
                    acceptance_authorization_cover_note_status.get("acceptance_executed"),
                    _mapping(
                        acceptance_authorization_cover_note.get(
                            "preserved_false_states"
                        )
                    ).get("acceptance_executed"),
                    acceptance_authorization_instruction_packet_status.get(
                        "acceptance_executed"
                    ),
                    acceptance_authorization_operator_handoff_bundle_status.get(
                        "acceptance_executed"
                    ),
                    _mapping(
                        acceptance_authorization_operator_handoff_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("acceptance_executed"),
                    acceptance_authorization_review_record_validator_status.get(
                        "acceptance_executed"
                    ),
                    acceptance_authorization_review_record_example_bundle_status.get(
                        "acceptance_executed"
                    ),
                ]
            ),
            branches=["acceptance-authorization"],
            artifact_ids=[
                "acceptance_authorization_cover_note",
                "acceptance_authorization_instruction_packet",
                "acceptance_authorization_operator_handoff_bundle",
                "acceptance_authorization_review_record_validator",
                "acceptance_authorization_review_record_example_bundle",
            ],
            detail=(
                "Must remain false. No acceptance execution has happened in this package."
            ),
        ),
        "actual_human_authorization_review_happened": _false_state_entry(
            state_id="actual_human_authorization_review_happened",
            current_false=_all_observed_false(
                [
                    acceptance_authorization_cover_note_status.get(
                        "actual_human_authorization_review_happened"
                    ),
                    _mapping(
                        acceptance_authorization_cover_note.get(
                            "preserved_false_states"
                        )
                    ).get("actual_human_authorization_review_happened"),
                    acceptance_authorization_instruction_packet_status.get(
                        "actual_human_authorization_review_happened"
                    ),
                    acceptance_authorization_operator_handoff_bundle_status.get(
                        "actual_human_authorization_review_happened"
                    ),
                    _mapping(
                        acceptance_authorization_operator_handoff_bundle.get(
                            "preserved_state_assertions"
                        )
                    ).get("actual_human_authorization_review_happened"),
                ]
            ),
            branches=["acceptance-authorization"],
            artifact_ids=[
                "acceptance_authorization_cover_note",
                "acceptance_authorization_instruction_packet",
                "acceptance_authorization_operator_handoff_bundle",
            ],
            detail=(
                "Must remain false. Acceptance-authorization artifacts do not imply "
                "that any actual human authorization review has already happened."
            ),
        ),
    }
    preserved_false_states_retained = all(
        bool(entry.get("locked_false", False))
        for entry in preserved_false_states.values()
    )

    artifact_order = [
        "ingest_review_cover_note",
        "ingest_review_instruction_packet",
        "ingest_review_operator_handoff_bundle",
        "ingest_review_record_validator",
        "ingest_review_record_example_bundle",
        "acceptance_authorization_cover_note",
        "acceptance_authorization_instruction_packet",
        "acceptance_authorization_operator_handoff_bundle",
        "acceptance_authorization_review_record_validator",
        "acceptance_authorization_review_record_example_bundle",
    ]
    required_artifacts_ready = all(
        bool(artifact_infos[artifact_id].get("ready", False))
        for artifact_id in artifact_order
    )
    primary_entrypoints_available = all(
        bool(info.get("ready", False))
        for info in artifact_infos.values()
        if bool(info.get("primary_entrypoint", False))
    )

    global_blockers = _collect_global_blockers(
        [
            (
                "ingest-review",
                "ingest_review_cover_note",
                ingest_review_cover_note_report,
                ingest_review_cover_note,
            ),
            (
                "ingest-review",
                "ingest_review_instruction_packet",
                ingest_review_instruction_packet_report,
                ingest_review_instruction_packet,
            ),
            (
                "ingest-review",
                "ingest_review_operator_handoff_bundle",
                ingest_review_operator_handoff_bundle_report,
                ingest_review_operator_handoff_bundle,
            ),
            (
                "ingest-review",
                "ingest_review_record_validator",
                ingest_review_record_validator_report,
                ingest_review_record_validator,
            ),
            (
                "ingest-review",
                "ingest_review_record_example_bundle",
                ingest_review_record_example_bundle_report,
                ingest_review_record_example_bundle,
            ),
            (
                "acceptance-authorization",
                "acceptance_authorization_cover_note",
                acceptance_authorization_cover_note_report,
                acceptance_authorization_cover_note,
            ),
            (
                "acceptance-authorization",
                "acceptance_authorization_instruction_packet",
                acceptance_authorization_instruction_packet_report,
                acceptance_authorization_instruction_packet,
            ),
            (
                "acceptance-authorization",
                "acceptance_authorization_operator_handoff_bundle",
                acceptance_authorization_operator_handoff_bundle_report,
                acceptance_authorization_operator_handoff_bundle,
            ),
            (
                "acceptance-authorization",
                "acceptance_authorization_review_record_validator",
                acceptance_authorization_review_record_validator_report,
                acceptance_authorization_review_record_validator,
            ),
            (
                "acceptance-authorization",
                "acceptance_authorization_review_record_example_bundle",
                acceptance_authorization_review_record_example_bundle_report,
                acceptance_authorization_review_record_example_bundle,
            ),
        ]
    )

    primary_entrypoints = [
        _artifact_ref(
            artifact_infos["ingest_review_cover_note"],
            reason=(
                "Short operator-facing branch entrypoint for the ingest-review path."
            ),
        ),
        _artifact_ref(
            artifact_infos["ingest_review_operator_handoff_bundle"],
            reason=(
                "Authoritative ingest-review handoff/authority artifact named first by the branch packet."
            ),
        ),
        _artifact_ref(
            artifact_infos["acceptance_authorization_cover_note"],
            reason=(
                "Short operator-facing branch entrypoint for the acceptance-authorization path."
            ),
        ),
        _artifact_ref(
            artifact_infos["acceptance_authorization_operator_handoff_bundle"],
            reason=(
                "Authoritative acceptance-authorization handoff/authority artifact named first by the branch packet."
            ),
        ),
    ]

    branch_artifact_index = {
        "ingest-review": {
            "branch_id": "ingest-review",
            "branch_summary": _first_text(
                ingest_review_cover_note_status.get("handoff_summary"),
                ingest_review_instruction_packet_status.get("handoff_recommendation"),
            ),
            "primary_entrypoint_artifact_ids": [
                "ingest_review_cover_note",
                "ingest_review_operator_handoff_bundle",
            ],
            "artifacts": [
                dict(artifact_infos["ingest_review_cover_note"]),
                dict(artifact_infos["ingest_review_instruction_packet"]),
                dict(artifact_infos["ingest_review_operator_handoff_bundle"]),
                dict(artifact_infos["ingest_review_record_validator"]),
                dict(artifact_infos["ingest_review_record_example_bundle"]),
            ],
        },
        "acceptance-authorization": {
            "branch_id": "acceptance-authorization",
            "branch_summary": _first_text(
                acceptance_authorization_cover_note_status.get("handoff_summary"),
                acceptance_authorization_instruction_packet_status.get(
                    "handoff_recommendation"
                ),
                acceptance_authorization_instruction_packet_status.get("recommendation"),
            ),
            "primary_entrypoint_artifact_ids": [
                "acceptance_authorization_cover_note",
                "acceptance_authorization_operator_handoff_bundle",
            ],
            "artifacts": [
                dict(artifact_infos["acceptance_authorization_cover_note"]),
                dict(artifact_infos["acceptance_authorization_instruction_packet"]),
                dict(artifact_infos["acceptance_authorization_operator_handoff_bundle"]),
                dict(artifact_infos["acceptance_authorization_review_record_validator"]),
                dict(artifact_infos["acceptance_authorization_review_record_example_bundle"]),
            ],
        },
    }

    synthetic_reference_artifacts = [
        _artifact_ref(artifact_infos["ingest_review_record_example_bundle"]),
        _artifact_ref(artifact_infos["acceptance_authorization_review_record_example_bundle"]),
    ]
    contract_artifacts = [
        _artifact_ref(artifact_infos["ingest_review_instruction_packet"]),
        _artifact_ref(artifact_infos["ingest_review_operator_handoff_bundle"]),
        _artifact_ref(artifact_infos["ingest_review_record_validator"]),
        _artifact_ref(artifact_infos["acceptance_authorization_instruction_packet"]),
        _artifact_ref(artifact_infos["acceptance_authorization_operator_handoff_bundle"]),
        _artifact_ref(artifact_infos["acceptance_authorization_review_record_validator"]),
    ]
    operator_facing_artifacts = [
        _artifact_ref(artifact_infos["ingest_review_cover_note"]),
        _artifact_ref(artifact_infos["ingest_review_instruction_packet"]),
        _artifact_ref(artifact_infos["ingest_review_operator_handoff_bundle"]),
        _artifact_ref(artifact_infos["acceptance_authorization_cover_note"]),
        _artifact_ref(artifact_infos["acceptance_authorization_instruction_packet"]),
        _artifact_ref(artifact_infos["acceptance_authorization_operator_handoff_bundle"]),
    ]

    checks = []
    for artifact_id in artifact_order:
        info = artifact_infos[artifact_id]
        checks.append(
            _check(
                f"{artifact_id}_present",
                "pass" if info["present"] else "fail",
                _presence_detail(
                    report=info["report"],
                    error=info["error"],
                    metadata=_mapping(info["metadata"]),
                    expected_source=str(info["expected_source"]),
                    project_root=project_root,
                    path=Path(str(info["path"])),
                ),
            )
        )
        ready_key = str(info.get("ready_key") or "ready")
        checks.append(
            _check(
                f"{artifact_id}_ready",
                "pass" if info["ready"] else "fail",
                f"{ready_key}=true" if info["ready"] else f"{ready_key}=false",
            )
        )

    checks.extend(
        [
            _check(
                "review_only_contract_retained",
                "pass" if review_only_contract_retained else "fail",
                "All loaded artifacts retain review_only/spec_only/default_off with proof_source=false, candidate_elimination_claim=false, and solver_invoked=false."
                if review_only_contract_retained
                else "At least one loaded artifact drifted away from the review-only/default-off/no-solve contract.",
            ),
            _check(
                "candidate_consistent",
                "pass" if candidate_consistent else "fail",
                "Candidate key, anchor_idx=119, and formulation_profile remain locked across both branches."
                if candidate_consistent
                else "Candidate identity mismatch across the manual-review package artifacts.",
            ),
            _check(
                "ingest_branch_reference_alignment",
                "pass" if ingest_branch_reference_alignment else "fail",
                "Ingest-review cover note, instruction packet, and referenced upstream artifacts point at the same locked branch paths."
                if ingest_branch_reference_alignment
                else "Ingest-review root artifacts no longer agree on the locked upstream branch paths.",
            ),
            _check(
                "acceptance_branch_reference_alignment",
                "pass" if acceptance_branch_reference_alignment else "fail",
                "Acceptance-authorization cover note, instruction packet, and referenced upstream artifacts point at the same locked branch paths."
                if acceptance_branch_reference_alignment
                else "Acceptance-authorization root artifacts no longer agree on the locked upstream branch paths.",
            ),
            _check(
                "primary_entrypoints_available",
                "pass" if primary_entrypoints_available else "fail",
                "Both branches still expose ready primary entrypoints through the cover note and operator handoff bundle."
                if primary_entrypoints_available
                else "At least one branch lost a ready primary entrypoint.",
            ),
            _check(
                "preserved_false_states_retained",
                "pass" if preserved_false_states_retained else "fail",
                "All preserved package states remain false across the bounded manual-review package."
                if preserved_false_states_retained
                else "At least one preserved false state flipped or stopped being evidenced as false.",
            ),
        ]
    )

    ready_prerequisite_check_ids = {
        check["check_id"] for check in checks if check["check_id"].endswith("_present")
    }
    ready_prerequisite_check_ids.update(
        {check["check_id"] for check in checks if check["check_id"].endswith("_ready")}
    )
    ready_prerequisite_check_ids.update(
        {
            "review_only_contract_retained",
            "candidate_consistent",
            "ingest_branch_reference_alignment",
            "acceptance_branch_reference_alignment",
            "primary_entrypoints_available",
            "preserved_false_states_retained",
        }
    )

    contract_compatible = bool(
        required_artifacts_ready
        and review_only_contract_retained
        and candidate_consistent
        and ingest_branch_reference_alignment
        and acceptance_branch_reference_alignment
        and primary_entrypoints_available
        and preserved_false_states_retained
    )
    manual_review_package_index_ready = contract_compatible

    missing_ready_gate_ids = [
        check["check_id"]
        for check in checks
        if check["status"] == "fail" and check["check_id"] in ready_prerequisite_check_ids
    ]

    if manual_review_package_index_ready:
        recommended_next_step = (
            "future_manual_operator_may_use_package_index_as_review_only_branch_map"
        )
    else:
        recommended_next_step = (
            "repair_missing_or_incompatible_manual_review_package_artifacts"
        )

    return {
        "metadata": {
            "source": MANUAL_REVIEW_PACKAGE_INDEX_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "anchor119_manual_review_package_index_review_only_spec_only_"
                "default_off_no_solve_solver_invoked_false"
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
        "paths": {
            "project_root": str(project_root),
            "root_artifacts": {
                "ingest_review_cover_note": _display_path(
                    project_root, ingest_review_cover_note_resolved
                ),
                "acceptance_authorization_cover_note": _display_path(
                    project_root, acceptance_authorization_cover_note_resolved
                ),
                "ingest_review_instruction_packet": _display_path(
                    project_root, ingest_review_instruction_packet_resolved
                ),
                "acceptance_authorization_instruction_packet": _display_path(
                    project_root, acceptance_authorization_instruction_packet_resolved
                ),
            },
            "resolved_branch_artifacts": {
                "ingest-review": {
                    "operator_handoff_bundle": _display_path(
                        project_root, ingest_review_operator_handoff_bundle_resolved
                    ),
                    "review_record_validator": _display_path(
                        project_root, ingest_review_record_validator_resolved
                    ),
                    "review_record_example_bundle": _display_path(
                        project_root, ingest_review_record_example_bundle_resolved
                    ),
                },
                "acceptance-authorization": {
                    "operator_handoff_bundle": _display_path(
                        project_root,
                        acceptance_authorization_operator_handoff_bundle_resolved,
                    ),
                    "review_record_validator": _display_path(
                        project_root,
                        acceptance_authorization_review_record_validator_resolved,
                    ),
                    "review_record_example_bundle": _display_path(
                        project_root,
                        acceptance_authorization_review_record_example_bundle_resolved,
                    ),
                },
            },
        },
        "status": {
            "manual_review_package_index_ready": manual_review_package_index_ready,
            "contract_compatible": contract_compatible,
            "required_artifacts_ready": required_artifacts_ready,
            "primary_entrypoints_available": primary_entrypoints_available,
            "repo_side_review_state_updated": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "acceptance_execution_authorized": False,
            "acceptance_executed": False,
            "missing_ready_gate_ids": missing_ready_gate_ids,
            "recommended_next_step": recommended_next_step,
            "global_blocker_gate_ids": [
                blocker["gate_id"] for blocker in global_blockers
            ],
        },
        "package_target": {
            "package_kind": "bounded_review_only_manual_review_package_index",
            "package_id": "anchor119_manual_review_package_across_ingest_and_acceptance_branches",
            "candidate_key": candidate_key,
            "anchor_idx": anchor_idx,
            "formulation_profile": formulation_profile,
            "branches": ["ingest-review", "acceptance-authorization"],
            "review_only": True,
            "spec_only": True,
            "default_off": True,
            "no_solve": True,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "package_notice": PACKAGE_NOTICE,
        },
        "primary_entrypoints": primary_entrypoints,
        "branch_artifact_index": branch_artifact_index,
        "synthetic_reference_artifacts": synthetic_reference_artifacts,
        "contract_artifacts": contract_artifacts,
        "operator_facing_artifacts": operator_facing_artifacts,
        "global_blockers": global_blockers,
        "preserved_false_states": preserved_false_states,
        "short_package_summary": SHORT_PACKAGE_SUMMARY,
        "checks": checks,
    }


def render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_markdown(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    package_target = _mapping(report.get("package_target"))
    lines = [
        "# Phase 3B Anchor119 Manual Review Package Index",
        "",
        f"- manual_review_package_index_ready: `{status.get('manual_review_package_index_ready')}`",
        f"- contract_compatible: `{status.get('contract_compatible')}`",
        f"- required_artifacts_ready: `{status.get('required_artifacts_ready')}`",
        f"- primary_entrypoints_available: `{status.get('primary_entrypoints_available')}`",
        f"- repo_side_review_state_updated: `{status.get('repo_side_review_state_updated')}`",
        f"- reviewed_runtime_patch_exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- runtime_enablement_allowed: `{status.get('runtime_enablement_allowed')}`",
        f"- acceptance_execution_authorized: `{status.get('acceptance_execution_authorized')}`",
        f"- acceptance_executed: `{status.get('acceptance_executed')}`",
        f"- missing_ready_gate_ids: `{', '.join(_string_list(status.get('missing_ready_gate_ids'))) or '(none)'}`",
        f"- recommended_next_step: `{status.get('recommended_next_step')}`",
        f"- global_blocker_gate_ids: `{', '.join(_string_list(status.get('global_blocker_gate_ids'))) or '(none)'}`",
        "",
        "## Short Package Summary",
        "",
        str(report.get("short_package_summary") or ""),
        "",
        "## Package Target",
        "",
        f"- package_kind: `{package_target.get('package_kind')}`",
        f"- package_id: `{package_target.get('package_id')}`",
        f"- candidate_key: `{package_target.get('candidate_key')}`",
        f"- anchor_idx: `{package_target.get('anchor_idx')}`",
        f"- formulation_profile: `{package_target.get('formulation_profile')}`",
        f"- branches: `{', '.join(_string_list(package_target.get('branches')))}`",
        f"- review_only: `{package_target.get('review_only')}`",
        f"- spec_only: `{package_target.get('spec_only')}`",
        f"- default_off: `{package_target.get('default_off')}`",
        f"- no_solve: `{package_target.get('no_solve')}`",
        f"- solver_invoked: `{package_target.get('solver_invoked')}`",
        f"- proof_source: `{package_target.get('proof_source')}`",
        f"- candidate_elimination_claim: `{package_target.get('candidate_elimination_claim')}`",
        f"- package_notice: {package_target.get('package_notice')}",
        "",
        "## Primary Entrypoints",
        "",
        "| Artifact | Branch | Kind | Ready | Path | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in report.get("primary_entrypoints", []):
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(entry.get('artifact_id'))} | "
                f"{_markdown_cell(entry.get('branch_id'))} | "
                f"{_markdown_cell(entry.get('artifact_kind'))} | "
                f"{_markdown_cell(entry.get('ready'))} | "
                f"{_markdown_cell(entry.get('path'))} | "
                f"{_markdown_cell(entry.get('reason'))} |"
            )

    lines.extend(["", "## Branch Artifact Index", ""])
    branch_artifact_index = _mapping(report.get("branch_artifact_index"))
    for branch_id in ["ingest-review", "acceptance-authorization"]:
        branch = _mapping(branch_artifact_index.get(branch_id))
        lines.extend(
            [
                f"### {branch_id}",
                "",
                f"- branch_summary: {branch.get('branch_summary')}",
                f"- primary_entrypoint_artifact_ids: `{', '.join(_string_list(branch.get('primary_entrypoint_artifact_ids'))) or '(none)'}`",
                "",
                "| Artifact | Kind | Present | Ready | Primary | Operator Facing | Contract | Synthetic | Path |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for artifact in branch.get("artifacts", []):
            if isinstance(artifact, Mapping):
                lines.append(
                    f"| {_markdown_cell(artifact.get('artifact_id'))} | "
                    f"{_markdown_cell(artifact.get('artifact_kind'))} | "
                    f"{_markdown_cell(artifact.get('present'))} | "
                    f"{_markdown_cell(artifact.get('ready'))} | "
                    f"{_markdown_cell(artifact.get('primary_entrypoint'))} | "
                    f"{_markdown_cell(artifact.get('operator_facing_summary'))} | "
                    f"{_markdown_cell(artifact.get('contract_artifact'))} | "
                    f"{_markdown_cell(artifact.get('synthetic_reference_only'))} | "
                    f"{_markdown_cell(artifact.get('path'))} |"
                )
        lines.append("")

    for title, key in [
        ("Synthetic Reference Artifacts", "synthetic_reference_artifacts"),
        ("Contract Artifacts", "contract_artifacts"),
        ("Operator Facing Artifacts", "operator_facing_artifacts"),
    ]:
        lines.extend(
            [
                f"## {title}",
                "",
                "| Artifact | Branch | Kind | Ready | Path | Detail |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in report.get(key, []):
            if isinstance(entry, Mapping):
                lines.append(
                    f"| {_markdown_cell(entry.get('artifact_id'))} | "
                    f"{_markdown_cell(entry.get('branch_id'))} | "
                    f"{_markdown_cell(entry.get('artifact_kind'))} | "
                    f"{_markdown_cell(entry.get('ready'))} | "
                    f"{_markdown_cell(entry.get('path'))} | "
                    f"{_markdown_cell(entry.get('detail'))} |"
                )
        lines.append("")

    lines.extend(
        [
            "## Global Blockers",
            "",
            "| Gate | Branches | Artifacts | Current Value | Details |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for blocker in report.get("global_blockers", []):
        if isinstance(blocker, Mapping):
            lines.append(
                f"| {_markdown_cell(blocker.get('gate_id'))} | "
                f"{_markdown_cell(', '.join(_string_list(blocker.get('branches'))))} | "
                f"{_markdown_cell(', '.join(_string_list(blocker.get('artifact_ids'))))} | "
                f"{_markdown_cell(blocker.get('current_value'))} | "
                f"{_markdown_cell('; '.join(_string_list(blocker.get('details'))))} |"
            )

    lines.extend(
        [
            "",
            "## Preserved False States",
            "",
            "| State | Locked False | Branches | Artifacts | Detail |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for state_id, entry in _mapping(report.get("preserved_false_states")).items():
        if isinstance(entry, Mapping):
            lines.append(
                f"| {_markdown_cell(state_id)} | "
                f"{_markdown_cell(entry.get('locked_false'))} | "
                f"{_markdown_cell(', '.join(_string_list(entry.get('branches'))))} | "
                f"{_markdown_cell(', '.join(_string_list(entry.get('artifact_ids'))))} | "
                f"{_markdown_cell(entry.get('detail'))} |"
            )

    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in report.get("checks", []):
        if isinstance(check, Mapping):
            lines.append(
                f"| {_markdown_cell(check.get('check_id'))} | "
                f"{_markdown_cell(check.get('status'))} | "
                f"{_markdown_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_text(
    report: Mapping[str, Any]
) -> str:
    status = _mapping(report.get("status"))
    package_target = _mapping(report.get("package_target"))
    primary_entrypoints = [
        str(entry.get("artifact_id"))
        for entry in report.get("primary_entrypoints", [])
        if isinstance(entry, Mapping) and entry.get("artifact_id")
    ]
    preserved_false_states = [
        str(state_id)
        for state_id, entry in _mapping(report.get("preserved_false_states")).items()
        if isinstance(entry, Mapping) and bool(entry.get("locked_false", False))
    ]
    return "\n".join(
        [
            "Phase 3B anchor119 manual review package index",
            "manual_review_package_index_ready="
            + str(status.get("manual_review_package_index_ready")),
            "contract_compatible=" + str(status.get("contract_compatible")),
            "candidate_key=" + str(package_target.get("candidate_key")),
            "anchor_idx=" + str(package_target.get("anchor_idx")),
            "formulation_profile=" + str(package_target.get("formulation_profile")),
            "primary_entrypoints=" + ",".join(primary_entrypoints),
            "global_blocker_gate_ids="
            + ",".join(_string_list(status.get("global_blocker_gate_ids"))),
            "preserved_false_states=" + ",".join(preserved_false_states),
            "recommended_next_step=" + str(status.get("recommended_next_step")),
        ]
    ) + "\n"


def write_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "anchor119_row_domain_manual_review_package_index",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_manual_review_package_index_text(
            report
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _artifact_info(
    *,
    artifact_id: str,
    branch_id: str,
    artifact_kind: str,
    project_root: Path,
    path: Path,
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
    metadata: Mapping[str, Any],
    expected_source: str,
    status: Mapping[str, Any],
    ready_key: str,
    primary_entrypoint: bool,
    operator_facing_summary: bool,
    contract_artifact: bool,
    synthetic_reference_only: bool,
    detail: str,
) -> Dict[str, Any]:
    present = bool(
        report is not None and error is None and metadata.get("source") == expected_source
    )
    ready = bool(present and status.get(ready_key, False))
    return {
        "artifact_id": artifact_id,
        "branch_id": branch_id,
        "artifact_kind": artifact_kind,
        "path": _display_path(project_root, path),
        "present": present,
        "ready": ready,
        "primary_entrypoint": primary_entrypoint,
        "operator_facing_summary": operator_facing_summary,
        "contract_artifact": contract_artifact,
        "synthetic_reference_only": synthetic_reference_only,
        "detail": detail,
        "expected_source": expected_source,
        "ready_key": ready_key,
        "metadata": dict(metadata),
        "report": dict(report) if isinstance(report, Mapping) else None,
        "error": error,
    }


def _artifact_ref(info: Mapping[str, Any], *, reason: str = "") -> Dict[str, Any]:
    return {
        "artifact_id": str(info.get("artifact_id") or ""),
        "branch_id": str(info.get("branch_id") or ""),
        "artifact_kind": str(info.get("artifact_kind") or ""),
        "path": str(info.get("path") or ""),
        "ready": bool(info.get("ready", False)),
        "detail": str(info.get("detail") or ""),
        "reason": str(reason or ""),
    }


def _false_state_entry(
    *,
    state_id: str,
    current_false: bool,
    branches: list[str],
    artifact_ids: list[str],
    detail: str,
) -> Dict[str, Any]:
    current_value = False if current_false else True
    return {
        "state_id": state_id,
        "expected_value": False,
        "current_value": current_value,
        "locked_false": current_false,
        "branches": list(branches),
        "artifact_ids": list(artifact_ids),
        "detail": detail,
    }


def _collect_global_blockers(
    items: list[tuple[str, str, Mapping[str, Any], Mapping[str, Any]]]
) -> list[Dict[str, Any]]:
    collected: dict[str, Dict[str, Any]] = {}
    for branch_id, artifact_id, report, section in items:
        report_mapping = _mapping(report)
        for gate_id in _string_list(report_mapping.get("still_blocked_gate_ids")):
            _record_blocker(collected, gate_id, branch_id, artifact_id)
        for gate_id in _string_list(
            _mapping(report_mapping.get("status")).get("still_blocked_gate_ids")
        ):
            _record_blocker(collected, gate_id, branch_id, artifact_id)
        for gate_id in _string_list(
            _mapping(report_mapping.get("status")).get("missing_prerequisite_gate_ids")
        ):
            _record_blocker(collected, gate_id, branch_id, artifact_id)
        for entry in _mapping_list(section.get("current_blockers")):
            gate_id = str(entry.get("gate_id") or "").strip()
            if gate_id:
                _record_blocker(
                    collected,
                    gate_id,
                    branch_id,
                    artifact_id,
                    detail=str(entry.get("detail") or ""),
                )
        for entry in _mapping_list(section.get("blocked_prerequisites")):
            gate_id = str(entry.get("gate_id") or "").strip()
            if gate_id:
                _record_blocker(
                    collected,
                    gate_id,
                    branch_id,
                    artifact_id,
                    detail=str(entry.get("detail") or ""),
                )
        for entry in _mapping_list(report_mapping.get("gates")):
            gate_id = str(entry.get("gate_id") or "").strip()
            if gate_id and bool(entry.get("blocking", False)) and not bool(
                entry.get("satisfied", False)
            ):
                _record_blocker(
                    collected,
                    gate_id,
                    branch_id,
                    artifact_id,
                    detail=str(entry.get("detail") or ""),
                )
    return [
        {
            "gate_id": gate_id,
            "branches": sorted(value["branches"]),
            "artifact_ids": sorted(value["artifact_ids"]),
            "current_value": False,
            "details": value["details"],
        }
        for gate_id, value in sorted(collected.items())
    ]


def _record_blocker(
    collected: dict[str, Dict[str, Any]],
    gate_id: str,
    branch_id: str,
    artifact_id: str,
    *,
    detail: str = "",
) -> None:
    gate_id = str(gate_id).strip()
    if not gate_id:
        return
    entry = collected.setdefault(
        gate_id, {"branches": set(), "artifact_ids": set(), "details": []}
    )
    entry["branches"].add(branch_id)
    entry["artifact_ids"].add(artifact_id)
    text = str(detail or "").strip()
    if text and text not in entry["details"]:
        entry["details"].append(text)


def _presence_detail(
    *,
    report: Optional[Mapping[str, Any]],
    error: Optional[str],
    metadata: Mapping[str, Any],
    expected_source: str,
    project_root: Path,
    path: Path,
) -> str:
    if error:
        return str(error)
    if report is None:
        return f"missing:{_display_path(project_root, path)}"
    if metadata.get("source") == expected_source:
        return f"present:{_display_path(project_root, path)}"
    return f"unexpected_source:{metadata.get('source')} expected:{expected_source}"


def _review_only_contract_retained(metadata: Mapping[str, Any]) -> bool:
    if not metadata:
        return False
    return bool(
        metadata.get("review_only", False)
        and metadata.get("spec_only", False)
        and metadata.get("default_off", False)
        and not bool(metadata.get("runtime_precheck_enabled", False))
        and not bool(metadata.get("runtime_semantics_changed", False))
        and not bool(metadata.get("proof_source", False))
        and not bool(metadata.get("candidate_elimination_claim", False))
        and not bool(metadata.get("solver_invoked", False))
    )


def _resolve_reference_path(
    project_root: Path, candidates: list[Any], default_path: Path
) -> Path:
    for value in candidates:
        if _has_value(value):
            return _resolve_path(project_root, Path(str(value)))
    return _resolve_path(project_root, default_path)


def _artifact_path_from_entries(entries: Any, artifact_id: str) -> str:
    for entry in _mapping_list(entries):
        if str(entry.get("artifact_id") or "").strip() != artifact_id:
            continue
        for key in ("path", "artifact_path"):
            value = entry.get(key)
            if _has_value(value):
                return str(value)
    return ""


def _path_values_match(project_root: Path, resolved_path: Path, values: list[Any]) -> bool:
    actual = _normalized_compare_path(project_root, resolved_path)
    candidates = [
        _normalized_compare_path(project_root, value)
        for value in values
        if _has_value(value)
    ]
    return bool(candidates and all(candidate == actual for candidate in candidates))


def _normalized_compare_path(project_root: Path, value: Any) -> str:
    if isinstance(value, Path):
        return _normalize_path_text(_display_path(project_root, _resolve_path(project_root, value)))
    return _normalize_path_text(
        _display_path(project_root, _resolve_path(project_root, Path(str(value))))
    )


def _current_blocker_value(entries: Any, gate_id: str) -> Any:
    for entry in _mapping_list(entries):
        if str(entry.get("gate_id") or "").strip() == gate_id:
            if "current_value" in entry:
                return entry.get("current_value")
            return False
    return None


def _blocked_gate_implies_false(values: Any, gate_id: str) -> Any:
    if gate_id in _string_list(values):
        return False
    return None


def _all_observed_false(values: list[Any]) -> bool:
    observed: list[bool] = []
    for value in values:
        normalized = _boolish_value(value)
        if normalized is not None:
            observed.append(normalized)
    return bool(observed) and not any(observed)


def _boolish_value(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        if "current_value" in value:
            return bool(value.get("current_value"))
        if "expected_value" in value:
            return bool(value.get("expected_value"))
        return None
    return bool(value)


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _locked_value(values: list[Any], *, normalize) -> tuple[Any, bool]:
    non_empty = [value for value in values if _has_value(value)]
    if not non_empty:
        return "", False
    normalized = {normalize(value) for value in non_empty}
    return non_empty[0], bool(len(non_empty) >= 2 and len(normalized) == 1)


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if not path.exists():
            return None, f"missing:{path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None, "json root is not an object"
        return payload, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path.resolve())


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _normalize_path_text(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


def _normalize_scalar(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, list):
            text = "; ".join(_string_list(value))
            if text:
                return text
        elif _has_value(value):
            return str(value)
    return ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[Mapping[str, Any]] = []
    for entry in value:
        if isinstance(entry, Mapping):
            result.append(entry)
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        text = str(entry).strip()
        if text:
            result.append(text)
    return result


def _markdown_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False).replace("|", "\\|")
    return str(value).replace("|", "\\|").replace("\n", " ")
