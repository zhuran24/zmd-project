from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b_b5a_localized_evidence_readiness import (
    B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
)
from src.search.phase3b_b5a_localized_evidence_validator import (
    B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE,
    build_phase3b_b5a_localized_evidence_validator,
    render_phase3b_b5a_localized_evidence_validator_markdown,
    render_phase3b_b5a_localized_evidence_validator_text,
)


def test_b5a_localized_evidence_validator_accepts_valid_readiness_contract(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    readiness_path = Path(".artifacts/readiness/b5a_localized_evidence_readiness.json")
    _write_json(project_root / readiness_path, _valid_readiness())

    report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=readiness_path,
    )

    assert report["metadata"]["source"] == B5A_LOCALIZED_EVIDENCE_VALIDATOR_SOURCE
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["checkpoint_written"] is False
    status = report["status"]
    assert status["localized_evidence_validator_ready"] is True
    assert status["current_localized_evidence_validated"] is True
    assert status["reviewer_acceptance_required"] is True
    assert status["certified_anchor_found"] is False
    assert status["b5a_anchor_found"] is False
    assert status["proof_source"] is False
    assert status["runtime_semantics_changed"] is False
    assert status["checkpoint_written"] is False
    assert (
        status["recommended_next_step"]
        == "external_or_manual_review_of_b5a_localized_evidence_validator"
    )
    accepted_lanes = {
        lane["lane_id"]: lane
        for lane in report["localized_evidence_validator"]["accepted_lanes"]
    }
    assert accepted_lanes["anchor118_ghost_overlap_forced_domain"]["role"] == (
        "auxiliary_cross_evidence"
    )
    assert accepted_lanes[
        "anchors119_125_signature_monotonic_forced_label"
    ]["role"] == "primary_coverage_evidence"
    assert "Review Intake" in render_phase3b_b5a_localized_evidence_validator_markdown(report)
    assert "localized_evidence_validator_ready=True" in (
        render_phase3b_b5a_localized_evidence_validator_text(report)
    )


def test_b5a_localized_evidence_validator_rejects_missing_wrong_source_and_wrong_candidate(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    missing_report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=Path(".artifacts/missing.json"),
    )
    assert missing_report["status"]["localized_evidence_validator_ready"] is False
    assert _failed_check_ids(missing_report) >= {"readiness_present"}

    wrong_source = _valid_readiness()
    wrong_source["metadata"]["source"] = "wrong_source"
    wrong_source_path = Path(".artifacts/wrong_source.json")
    _write_json(project_root / wrong_source_path, wrong_source)
    wrong_source_report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=wrong_source_path,
    )
    assert wrong_source_report["status"]["localized_evidence_validator_ready"] is False
    assert "readiness_source_supported" in _failed_check_ids(wrong_source_report)

    wrong_candidate = _valid_readiness()
    wrong_candidate["candidate"]["localized_key"] = "68x13"
    wrong_candidate["candidate"]["matches"] = False
    wrong_candidate_path = Path(".artifacts/wrong_candidate.json")
    _write_json(project_root / wrong_candidate_path, wrong_candidate)
    wrong_candidate_report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=wrong_candidate_path,
    )
    assert wrong_candidate_report["status"]["localized_evidence_validator_ready"] is False
    assert "candidate_locked_67x13" in _failed_check_ids(wrong_candidate_report)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("metadata", "solver_invoked"),
        ("metadata", "checkpoint_written"),
        ("metadata", "proof_source"),
        ("metadata", "runtime_semantics_changed"),
        ("metadata", "candidate_elimination_claim"),
        ("status", "certified_anchor_found"),
        ("status", "b5a_anchor_found"),
        ("status", "proof_source"),
        ("status", "runtime_semantics_changed"),
        ("status", "candidate_elimination_claim"),
    ],
)
def test_b5a_localized_evidence_validator_rejects_unsafe_flags(
    tmp_path: Path,
    section: str,
    field: str,
) -> None:
    project_root = tmp_path / "project"
    readiness = _valid_readiness()
    readiness[section][field] = True
    readiness_path = Path(f".artifacts/unsafe_{section}_{field}.json")
    _write_json(project_root / readiness_path, readiness)

    report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=readiness_path,
    )

    assert report["status"]["localized_evidence_validator_ready"] is False
    failed = _failed_check_ids(report)
    assert {"metadata_safe_flags", "status_safe_flags"} & failed


def test_b5a_localized_evidence_validator_rejects_lane_mismatches_and_precedent_only(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"

    wrong_ghost = _valid_readiness()
    wrong_ghost["lanes"][0]["covered_anchors"] = [119]
    wrong_ghost_path = Path(".artifacts/wrong_ghost.json")
    _write_json(project_root / wrong_ghost_path, wrong_ghost)
    wrong_ghost_report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=wrong_ghost_path,
    )
    assert wrong_ghost_report["status"]["localized_evidence_validator_ready"] is False
    assert "anchor118_ghost_lane_valid" in _failed_check_ids(wrong_ghost_report)

    incomplete_signature = _valid_readiness()
    incomplete_signature["lanes"][1]["covered_anchors"] = [119, 120]
    incomplete_signature_path = Path(".artifacts/incomplete_signature.json")
    _write_json(project_root / incomplete_signature_path, incomplete_signature)
    signature_report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=incomplete_signature_path,
    )
    assert signature_report["status"]["localized_evidence_validator_ready"] is False
    assert "anchors119_125_signature_lane_valid" in _failed_check_ids(signature_report)

    precedent_only = _valid_readiness()
    precedent_only["lanes"][1]["current_source_complete"] = False
    precedent_only["lanes"][1]["covered_anchors"] = []
    precedent_only["old_signature_precedent_policy"][
        "old_m6x4_signature_artifact_used_as_current_b5a_evidence"
    ] = True
    precedent_only_path = Path(".artifacts/precedent_only.json")
    _write_json(project_root / precedent_only_path, precedent_only)
    precedent_report = build_phase3b_b5a_localized_evidence_validator(
        project_root,
        readiness_path=precedent_only_path,
    )
    assert precedent_report["status"]["localized_evidence_validator_ready"] is False
    failed = _failed_check_ids(precedent_report)
    assert "anchors119_125_signature_lane_valid" in failed
    assert "old_signature_precedent_not_current_evidence" in failed


def test_b5a_localized_evidence_validator_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    project_root = tmp_path / "project"
    readiness_path = Path(".artifacts/readiness/b5a_localized_evidence_readiness.json")
    output_dir = tmp_path / "out"
    _write_json(project_root / readiness_path, _valid_readiness())
    script = repo_root / "scripts" / "build_phase3b_b5a_localized_evidence_validator.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--localized-evidence-readiness",
            str(readiness_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "validator ready: True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--localized-evidence-readiness",
            str(readiness_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "b5a_localized_evidence_validator_json=" in write.stdout
    payload = json.loads(
        (output_dir / "b5a_localized_evidence_validator.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["localized_evidence_validator_ready"] is True
    assert (output_dir / "b5a_localized_evidence_validator.md").exists()
    assert (output_dir / "b5a_localized_evidence_validator.txt").exists()


def _valid_readiness() -> dict[str, object]:
    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            **_authorization_safety_false_fields(),
        },
        "inputs": {
            "post_acceptance_preflight": {
                "ready_for_final_long_run": False,
                "failed_checks": ["b5a_anchor_found"],
                "only_b5a_anchor_found_failed": True,
            }
        },
        "status": {
            "readiness_ready": True,
            "certified_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "checkpoint_written": False,
            "b5a_anchor_found": False,
            **_authorization_safety_false_fields(),
        },
        "candidate": {
            "expected_key": "67x13",
            "localized_key": "67x13",
            "matches": True,
        },
        "lanes": [
            {
                "lane_id": "anchor118_ghost_overlap_forced_domain",
                "category": "ghost_overlap_forced_domain",
                "required_anchors": [118],
                "covered_anchors": [118],
                "current_source_complete": True,
                "probe_supports_lane": True,
                "solver_free_inputs": True,
                "proof_safe": True,
            },
            {
                "lane_id": "anchors119_125_signature_monotonic_forced_label",
                "category": "signature_monotonic_forced_label",
                "required_anchors": [119, 120, 121, 122, 123, 124, 125],
                "covered_anchors": [119, 120, 121, 122, 123, 124, 125],
                "current_source_complete": True,
                "probe_supports_lane": True,
                "solver_free_inputs": True,
                "proof_safe": True,
                "precedent": {
                    "used_as_current_b5a_evidence": False,
                },
            },
        ],
        "old_signature_precedent_policy": {
            "old_m6x4_signature_artifact_used_as_current_b5a_evidence": False,
            "required_current_source": (
                "2026-04-25 B5A reason-localization anchors 119-125"
            ),
            "policy": (
                "The older signature promotion spec may guide implementation, but it "
                "cannot satisfy B5A localized evidence without current-source anchor rows."
            ),
        },
    }


def _authorization_safety_false_fields() -> dict[str, bool]:
    return {
        "runtime_elimination_authorized": False,
        "final_168h_authorized": False,
        "checkpoint_write_or_import_back_authorized": False,
        "release_viewer_frontdoor_status_promoted": False,
        "preflight_gate_mutated": False,
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _failed_check_ids(report: dict[str, object]) -> set[str]:
    return {
        str(check["check_id"])
        for check in report["checks"]
        if isinstance(check, dict) and check.get("status") == "fail"
    }
