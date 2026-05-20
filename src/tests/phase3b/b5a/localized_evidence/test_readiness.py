from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.b5a.coordinate_validation_reason_localization import (
    B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
)
from src.search.phase3b.b5a.localized_evidence.readiness import (
    build_phase3b_b5a_localized_evidence_readiness,
    render_phase3b_b5a_localized_evidence_readiness_markdown,
    render_phase3b_b5a_localized_evidence_readiness_text,
)


def test_b5a_localized_evidence_readiness_splits_ghost_and_signature_lanes(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root)

    report = build_phase3b_b5a_localized_evidence_readiness(
        project_root,
        reason_localization_path=paths["reason"],
        post_acceptance_preflight_path=paths["preflight"],
        signature_runtime_probe_path=paths["signature_probe"],
        ghost_runtime_probe_path=paths["ghost_probe"],
        signature_precedent_path=paths["precedent"],
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["checkpoint_written"] is False
    assert report["status"]["readiness_ready"] is True
    assert report["status"]["certified_anchor_found"] is False
    assert report["status"]["proof_source"] is False
    lanes = {lane["lane_id"]: lane for lane in report["lanes"]}
    ghost = lanes["anchor118_ghost_overlap_forced_domain"]
    signature = lanes["anchors119_125_signature_monotonic_forced_label"]
    assert ghost["covered_anchors"] == [118]
    assert ghost["current_source_complete"] is True
    assert ghost["probe_supports_lane"] is True
    assert ghost["minimal_evidence"]["compatible_rows_all_overlap_fixed_ghost"] is True
    assert signature["covered_anchors"] == [119, 120, 121, 122, 123, 124, 125]
    assert signature["current_source_complete"] is True
    assert signature["probe_supports_lane"] is True
    assert signature["precedent"]["used_as_current_b5a_evidence"] is False
    assert "current_source_signature_validator_for_anchors119_125" in signature["missing_gates"]
    assert "Evidence Lanes" in render_phase3b_b5a_localized_evidence_readiness_markdown(report)
    assert "readiness_ready=True" in render_phase3b_b5a_localized_evidence_readiness_text(report)


def test_old_signature_precedent_alone_cannot_satisfy_current_b5a_evidence(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root, write_reason=False)

    report = build_phase3b_b5a_localized_evidence_readiness(
        project_root,
        reason_localization_path=paths["reason"],
        post_acceptance_preflight_path=paths["preflight"],
        signature_runtime_probe_path=paths["signature_probe"],
        ghost_runtime_probe_path=paths["ghost_probe"],
        signature_precedent_path=paths["precedent"],
    )

    assert report["status"]["readiness_ready"] is False
    signature = {
        lane["lane_id"]: lane for lane in report["lanes"]
    }["anchors119_125_signature_monotonic_forced_label"]
    assert signature["precedent"]["present"] is True
    assert signature["precedent"]["used_as_current_b5a_evidence"] is False
    assert signature["current_source_complete"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "reason_localization_present" in failed
    assert "signature_lane_anchors119_125_current_source" in failed


def test_b5a_localized_evidence_readiness_rejects_wrong_candidate_and_unsafe_flags(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(
        project_root,
        candidate_key="68x13",
        proof_source=True,
        runtime_semantics_changed=True,
    )

    report = build_phase3b_b5a_localized_evidence_readiness(
        project_root,
        reason_localization_path=paths["reason"],
        post_acceptance_preflight_path=paths["preflight"],
        signature_runtime_probe_path=paths["signature_probe"],
        ghost_runtime_probe_path=paths["ghost_probe"],
        signature_precedent_path=paths["precedent"],
    )

    assert report["status"]["readiness_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "candidate_matches_expected" in failed
    assert "reason_localization_safe_flags" in failed
    assert report["candidate"]["matches"] is False


def test_b5a_localized_evidence_readiness_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    paths = _write_inputs(project_root)
    script = repo_root / "scripts" / "phase3b" / "b5a" / "localized_evidence" / "build_readiness.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--reason-localization",
            str(paths["reason"]),
            "--post-acceptance-preflight",
            str(paths["preflight"]),
            "--signature-runtime-probe",
            str(paths["signature_probe"]),
            "--ghost-runtime-probe",
            str(paths["ghost_probe"]),
            "--signature-precedent",
            str(paths["precedent"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "readiness ready: True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--reason-localization",
            str(paths["reason"]),
            "--post-acceptance-preflight",
            str(paths["preflight"]),
            "--signature-runtime-probe",
            str(paths["signature_probe"]),
            "--ghost-runtime-probe",
            str(paths["ghost_probe"]),
            "--signature-precedent",
            str(paths["precedent"]),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "b5a_localized_evidence_readiness_json=" in write.stdout
    payload = json.loads(
        (output_dir / "b5a_localized_evidence_readiness.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["readiness_ready"] is True
    assert (output_dir / "b5a_localized_evidence_readiness.md").exists()
    assert (output_dir / "b5a_localized_evidence_readiness.txt").exists()


def _write_inputs(
    project_root: Path,
    *,
    write_reason: bool = True,
    candidate_key: str = "67x13",
    proof_source: bool = False,
    runtime_semantics_changed: bool = False,
) -> dict[str, Path]:
    paths = {
        "reason": Path(".artifacts/reason/b5a_coordinate_validation_reason_localization.json"),
        "preflight": Path(".artifacts/preflight/preflight_summary.json"),
        "signature_probe": Path(".artifacts/signature/signature_probe.json"),
        "ghost_probe": Path(".artifacts/ghost/ghost_probe.json"),
        "precedent": Path(".artifacts/precedent/promotion_spec.json"),
    }
    if write_reason:
        _write_json(
            project_root / paths["reason"],
            _reason_localization(
                candidate_key=candidate_key,
                proof_source=proof_source,
                runtime_semantics_changed=runtime_semantics_changed,
            ),
        )
    _write_json(
        project_root / paths["preflight"],
        {
            "ready_for_final_long_run": False,
            "checks": [
                {"check_id": "startline_manifest_present", "status": "pass"},
                {"check_id": "b5a_anchor_found", "status": "fail"},
                {"check_id": "production_acceptance_present", "status": "pass"},
            ],
        },
    )
    _write_json(project_root / paths["signature_probe"], _signature_probe())
    _write_json(project_root / paths["ghost_probe"], _ghost_probe())
    _write_json(
        project_root / paths["precedent"],
        {"promotion_status": {"spec_ready_for_runtime_slice": True}},
    )
    return paths


def _reason_localization(
    *,
    candidate_key: str,
    proof_source: bool,
    runtime_semantics_changed: bool,
) -> dict[str, object]:
    rows = [
        {
            "anchor_idx": 118,
            "failure_reason": "coordinate_validation_ghost_overlap_forced_domain_infeasible",
            "category": "ghost_overlap_forced_domain",
            "localized": True,
            "blocked_cell_count": 871,
            "forced_anchor_status_counts": {"INFEASIBLE": 3},
        },
        *[
            {
                "anchor_idx": idx,
                "failure_reason": "coordinate_validation_signature_monotonic_forced_label_infeasible",
                "category": "signature_monotonic_forced_label",
                "localized": True,
                "blocked_cell_count": 871,
                "forced_anchor_status_counts": {"UNKNOWN": 3},
            }
            for idx in range(119, 126)
        ],
    ]
    return {
        "metadata": {
            "source": B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
            "solver_invoked": False,
            "checkpoint_written": False,
        },
        "selected_surface": {"candidate_key": candidate_key},
        "status": {
            "reason_localization_ready": True,
            "proof_source": proof_source,
            "runtime_semantics_changed": runtime_semantics_changed,
        },
        "reason_localization": {"anchor_rows": rows},
    }


def _signature_probe() -> dict[str, object]:
    return {
        "metadata": {
            "source": "phase3b_signature_monotonic_runtime_probe_anchor119_v1",
            "diagnostic_semantics": "runtime_precheck_probe_not_proof_source",
        },
        "candidate": {"key": "67x13", "anchor_idx": 119},
        "validation": {
            "attempted_solver": False,
            "reason": "signature_monotonic_forced_label_infeasible",
            "signature_monotonic_precheck": {
                "reason": "signature_monotonic_forced_label_infeasible",
                "group_id": "group::manufacturing_3x3::crusher_blue_iron::1",
                "forced_label_count": 3,
                "constrained_slots": [
                    {"slot_index": 21, "allowed_signature_ids": [2]},
                    {"slot_index": 22, "allowed_signature_ids": [0, 1]},
                ],
                "failure": {
                    "slot_index": 22,
                    "previous_possible_signature_ids": [2],
                    "current_allowed_signature_ids": [0, 1],
                },
            },
        },
    }


def _ghost_probe() -> dict[str, object]:
    return {
        "metadata": {
            "source": "phase3b_ghost_overlap_forced_domain_runtime_probe_v1",
            "diagnostic_semantics": "runtime_precheck_probe_not_proof_source",
        },
        "candidate": {"key": "67x13", "anchor_idx": 118},
        "validation": {
            "attempted_solver": False,
            "reason": "ghost_overlap_forced_domain_infeasible",
            "ghost_overlap_forced_domain_precheck": {
                "reason": "ghost_overlap_forced_domain_infeasible",
                "ghost_rect": {"x": 2, "y": 2, "w": 67, "h": 13},
                "first_conflict": {
                    "reason": "all_compatible_rows_overlap_fixed_ghost",
                    "group_id": "group::boundary_storage_port::boundary_io::0",
                    "solution_id": "boundary_port_046",
                    "slot_index": 45,
                    "template": "boundary_storage_port",
                    "forced_fields": {"x": 67},
                    "selected_labels": [
                        {
                            "stable_key": "mandatory|boundary|45|x",
                            "field": "x",
                            "forced_value": 67,
                        }
                    ],
                    "compatible_tuple_count": 1,
                    "compatible_rows": [{"x": 67, "y": 0, "mode": 1}],
                },
            },
        },
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
