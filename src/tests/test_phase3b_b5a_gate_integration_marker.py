from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.search.phase3b_b5a_certified_anchor_promotion_review_packet import (
    B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE,
    EXPECTED_COVERED_ANCHORS,
    EXPECTED_CANDIDATE,
    EXPECTED_SCOPE,
    build_phase3b_b5a_certified_anchor_promotion_review_packet,
)
from src.tests.test_phase3b_b5a_certified_anchor_promotion_review_packet import (
    _valid_promotion_payload,
    _write_valid_chain,
)
from src.search.phase3b_b5a_certification_contracts import chain_fingerprint, sha256_file
from src.search.phase3b_b5a_gate_integration_marker import (
    B5A_GATE_INTEGRATION_MARKER_SOURCE,
    build_phase3b_b5a_gate_integration_marker,
    render_phase3b_b5a_gate_integration_marker_markdown,
    render_phase3b_b5a_gate_integration_marker_text,
    validate_phase3b_b5a_gate_integration_marker_for_preflight,
)


def test_b5a_gate_integration_marker_ready_for_valid_promotion_packet(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/promotion_packet.json")
    _write_valid_full_promotion_packet(tmp_path, packet_path)

    report = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=packet_path,
    )

    assert report["metadata"]["source"] == B5A_GATE_INTEGRATION_MARKER_SOURCE
    status = report["status"]
    assert status["gate_integration_marker_ready"] is True
    assert status["repo_side_b5a_gate_state_updated"] is True
    assert status["b5a_anchor_found"] is True
    assert status["certified_anchor_found"] is True
    assert status["proof_source"] is False
    assert status["runtime_semantics_changed"] is False
    assert status["checkpoint_written"] is False
    assert status["runtime_elimination_authorized"] is False
    assert status["final_168h_authorized"] is False
    assert report["chain_fingerprint"]
    assert len(report["chain_input_hashes"]) == 7
    assert "chain_input_hashes_recorded" not in _failed_check_ids(report)
    preflight_validation = validate_phase3b_b5a_gate_integration_marker_for_preflight(
        project_root,
        report,
    )
    assert preflight_validation["accepted"] is True
    assert "B5A Gate Integration Marker" in (
        render_phase3b_b5a_gate_integration_marker_markdown(report)
    )
    assert "gate_integration_marker_ready=True" in (
        render_phase3b_b5a_gate_integration_marker_text(report)
    )


@pytest.mark.parametrize(
    ("mutator", "failed_check"),
    [
        (
            lambda payload: payload["metadata"].update({"source": "wrong_source"}),
            "promotion_review_packet_source_supported",
        ),
        (
            lambda payload: payload["status"].update(
                {"promotion_review_payload_validated": False}
            ),
            "promotion_review_payload_validated",
        ),
        (
            lambda payload: payload["status"].update(
                {"certified_anchor_promotion_review_accepted": False}
            ),
            "promotion_review_payload_validated",
        ),
        (
            lambda payload: payload["candidate"].update({"candidate_key": "68x13"}),
            "candidate_scope_locked",
        ),
        (
            lambda payload: payload["candidate"].update({"covered_anchors": [118]}),
            "candidate_scope_locked",
        ),
        (
            lambda payload: payload["metadata"].update({"proof_source": True}),
            "promotion_packet_safety_flags_off",
        ),
        (
            lambda payload: payload["status"].update(
                {"runtime_elimination_authorized": True}
            ),
            "no_runtime_or_final_authorization",
        ),
    ],
)
def test_b5a_gate_integration_marker_rejects_invalid_promotion_packet(
    tmp_path: Path,
    mutator,
    failed_check: str,
) -> None:
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/promotion_packet.json")
    _write_valid_full_promotion_packet(tmp_path, packet_path)
    payload = json.loads((project_root / packet_path).read_text(encoding="utf-8"))
    mutator(payload)
    _write_json(project_root / packet_path, payload)

    report = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=packet_path,
    )

    assert report["status"]["gate_integration_marker_ready"] is False
    assert report["status"]["b5a_anchor_found"] is False
    assert report["status"]["certified_anchor_found"] is False
    assert failed_check in _failed_check_ids(report)


def test_b5a_gate_integration_marker_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/promotion_packet.json")
    output_dir = tmp_path / "out"
    _write_valid_full_promotion_packet(tmp_path, packet_path)
    script = repo_root / "scripts" / "build_phase3b_b5a_gate_integration_marker.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--promotion-review-packet",
            str(packet_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "marker ready: True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--promotion-review-packet",
            str(packet_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "b5a_gate_integration_marker_json=" in write.stdout
    payload = json.loads(
        (output_dir / "b5a_gate_integration_marker.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["gate_integration_marker_ready"] is True
    assert payload["status"]["b5a_anchor_found"] is True
    assert (output_dir / "b5a_gate_integration_marker.md").exists()
    assert (output_dir / "b5a_gate_integration_marker.txt").exists()


def test_b5a_gate_integration_marker_rejects_minimal_synthetic_packet(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/promotion_packet.json")
    _write_json(project_root / packet_path, _valid_promotion_packet())

    report = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=packet_path,
    )

    assert report["status"]["gate_integration_marker_ready"] is False
    assert "promotion_review_source_chain_reverified" in _failed_check_ids(report)


def test_b5a_gate_integration_marker_preflight_validation_rejects_tampered_hash(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/promotion_packet.json")
    _write_valid_full_promotion_packet(tmp_path, packet_path)
    report = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=packet_path,
    )
    report["chain_input_hashes"][0]["sha256"] = "0" * 64

    validation = validate_phase3b_b5a_gate_integration_marker_for_preflight(
        project_root,
        report,
    )

    assert validation["accepted"] is False
    assert "chain_input_hashes_match" in validation["failed_rule_ids"]


@pytest.mark.parametrize("mutation", ["exists_false", "exists_missing"])
def test_b5a_gate_integration_marker_preflight_validation_rejects_tampered_exists(
    tmp_path: Path,
    mutation: str,
) -> None:
    project_root = tmp_path / "project"
    packet_path = Path(".artifacts/promotion_packet.json")
    _write_valid_full_promotion_packet(tmp_path, packet_path)
    report = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=packet_path,
    )
    if mutation == "exists_false":
        report["chain_input_hashes"][0]["exists"] = False
    elif mutation == "exists_missing":
        report["chain_input_hashes"][0].pop("exists")
    else:
        raise AssertionError(mutation)

    validation = validate_phase3b_b5a_gate_integration_marker_for_preflight(
        project_root,
        report,
    )

    assert validation["accepted"] is False
    assert "chain_input_hashes_match" in validation["failed_rule_ids"]


def test_b5a_gate_integration_marker_preflight_validation_rejects_forged_self_consistent_marker(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    fake_chain_input = project_root / ".artifacts" / "fake_chain_input.json"
    _write_json(fake_chain_input, {"fake": "but hash-consistent"})
    chain_records = [
        {
            "input_id": "fake_chain_input",
            "path": ".artifacts/fake_chain_input.json",
            "exists": True,
            "sha256": sha256_file(fake_chain_input),
        }
    ]
    forged = {
        "metadata": {
            "source": B5A_GATE_INTEGRATION_MARKER_SOURCE,
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
        },
        "paths": {"project_root": str(project_root)},
        "chain_input_hashes": chain_records,
        "chain_fingerprint": chain_fingerprint(chain_records),
        "candidate": {
            "candidate_key": EXPECTED_CANDIDATE,
            "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
            "scope": EXPECTED_SCOPE,
        },
        "status": {
            "gate_integration_marker_ready": True,
            "repo_side_b5a_gate_state_updated": True,
            "b5a_anchor_found": True,
            "certified_anchor_found": True,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "candidate_elimination_claim": False,
        },
        "gate_integration_marker": {
            "gate_integration_marker_ready": True,
            "b5a_anchor_found": True,
            "certified_anchor_found": True,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "candidate_elimination_claim": False,
        },
        "checks": [{"check_id": "fake_check", "status": "pass", "detail": "forged"}],
    }

    validation = validate_phase3b_b5a_gate_integration_marker_for_preflight(
        project_root,
        forged,
    )

    assert validation["accepted"] is False
    assert "required_chain_inputs_exact" in validation["failed_rule_ids"]
    assert "required_marker_check_ids_exact" in validation["failed_rule_ids"]
    assert (
        "promotion_review_source_chain_reverified_for_preflight"
        in validation["failed_rule_ids"]
    )


def _write_valid_full_promotion_packet(tmp_path: Path, packet_path: Path) -> None:
    project_root, paths = _write_valid_chain(tmp_path)
    payload_path = Path(".artifacts/promotion_payload.json")
    _write_json(project_root / payload_path, _valid_promotion_payload())
    report = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=paths["review_state"],
        localized_evidence_validator_path=paths["validator"],
        localized_evidence_readiness_path=paths["readiness"],
        reason_localization_path=paths["reason"],
        post_acceptance_blocker_summary_path=paths["post"],
        promotion_review_payload_path=payload_path,
    )
    assert report["status"]["promotion_review_packet_ready"] is True
    assert report["status"]["promotion_review_payload_validated"] is True
    _write_json(project_root / packet_path, report)


def _valid_promotion_packet() -> dict[str, object]:
    return {
        "metadata": {
            "source": B5A_CERTIFIED_ANCHOR_PROMOTION_REVIEW_PACKET_SOURCE,
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "preflight_gate_mutated": False,
        },
        "candidate": {
            "candidate_key": EXPECTED_CANDIDATE,
            "covered_anchors": list(EXPECTED_COVERED_ANCHORS),
            "scope": EXPECTED_SCOPE,
        },
        "status": {
            "promotion_review_packet_ready": True,
            "promotion_review_payload_provided": True,
            "promotion_review_payload_validated": True,
            "promotion_review_payload_validation_status": "passed",
            "certified_anchor_promotion_review_accepted": True,
            "b5a_anchor_found": False,
            "certified_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            "preflight_gate_mutated": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "still_blocked_gate_ids": ["b5a_anchor_found"],
        },
        "promotion_review_record_validator": {
            "actual_record_validation": {
                "record_payload_provided": True,
                "record_payload_validated": True,
                "certified_anchor_promotion_review_accepted": True,
                "validation_status": "passed",
                "failed_rule_ids": [],
            }
        },
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _failed_check_ids(report: dict[str, object]) -> list[str]:
    return [
        str(check.get("check_id"))
        for check in list(report.get("checks", []))
        if isinstance(check, dict) and check.get("status") == "fail"
    ]
