from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.b5a.post_acceptance_blocker_summary import (
    SummaryPaths,
    build_post_acceptance_b5a_blocker_summary,
    classify_coordinate_validation_failure_reason,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _base_preflight(failed_checks: list[str] | None = None) -> dict:
    failed_checks = failed_checks or ["b5a_anchor_found"]
    checks = [
        {
            "check_id": "b5a_anchor_found",
            "status": "fail" if "b5a_anchor_found" in failed_checks else "pass",
        },
        {
            "check_id": "production_acceptance_present",
            "status": "fail"
            if "production_acceptance_present" in failed_checks
            else "pass",
        },
        {
            "check_id": "production_acceptance_prod_4x4_valid",
            "status": "fail"
            if "production_acceptance_prod_4x4_valid" in failed_checks
            else "pass",
        },
    ]
    return {"ready_for_final_long_run": False, "checks": checks}


def _base_b5a_summary(samples: list[dict] | None = None) -> dict:
    samples = samples or [
        {
            "anchor_idx": 118,
            "failure_reason": "coordinate_validation_infeasible",
            "blocked_cell_count": 871,
        },
        {
            "anchor_idx": 119,
            "failure_reason": "coordinate_validation_infeasible",
            "blocked_cell_count": 871,
        },
    ]
    counts: dict[str, int] = {}
    for sample in samples:
        counts[sample["failure_reason"]] = counts.get(sample["failure_reason"], 0) + 1
    return {
        "metadata": {"source": "phase3b_b5_anchor_sprint_summary_v1"},
        "status": {
            "anchor_found": False,
            "source_matches_coordinator": True,
            "attribution_trustworthy_with_current_source": True,
        },
        "triage": {
            "top_blockers": [
                {
                    "candidate_key": "67x13",
                    "status": "UNKNOWN",
                    "blocker_subtype": "master_start_incompatible_unknown",
                    "evidence_refs": {
                        "proof_fields": {
                            "master_status": "UNKNOWN",
                            "master_last_solve": {
                                "status": "UNKNOWN",
                                "branches": 12560,
                                "conflicts": 216,
                            },
                            "master_start_failure_attribution": {
                                "failed_anchor_count": len(samples),
                                "failure_reason_counts": counts,
                                "failed_anchor_samples": samples,
                            },
                        }
                    },
                }
            ]
        },
    }


def _base_acceptance_result() -> dict:
    return {
        "status": {
            "acceptance_result_validation_passed": True,
            "runtime_enablement_allowed": False,
        }
    }


def _base_acceptance_gate() -> dict:
    return {
        "status": {
            "reviewed_runtime_patch_exists": True,
            "production_acceptance_refresh_completed": True,
            "acceptance_result_validation_passed": True,
            "runtime_enablement_allowed": False,
            "acceptance_execution_authorized": False,
        }
    }


def _write_input_set(
    tmp_path: Path,
    *,
    preflight: dict | None = None,
    b5a: dict | None = None,
    acceptance_result: dict | None = None,
    acceptance_gate: dict | None = None,
) -> SummaryPaths:
    root = tmp_path / "inputs"
    preflight_path = _write_json(
        root / "preflight_summary.json", preflight or _base_preflight()
    )
    b5a_path = _write_json(
        root / "operator_summary.json", b5a or _base_b5a_summary()
    )
    result_path = _write_json(
        root / "acceptance_result.json",
        acceptance_result or _base_acceptance_result(),
    )
    gate_path = _write_json(
        root / "acceptance_gate.json", acceptance_gate or _base_acceptance_gate()
    )
    handoff_path = root / "handoff.md"
    handoff_path.write_text("production acceptance refresh completed\n", encoding="utf-8")
    return SummaryPaths(
        preflight_summary=preflight_path,
        b5a_operator_summary=b5a_path,
        acceptance_result_validator=result_path,
        acceptance_execution_gate=gate_path,
        production_acceptance_handoff=handoff_path,
    )


def test_post_acceptance_summary_marks_only_b5a_gate_remaining(tmp_path: Path) -> None:
    summary = build_post_acceptance_b5a_blocker_summary(
        _write_input_set(tmp_path)
    )

    assert summary["status"]["outcome"] == "post_acceptance_b5a_anchor_gate_remaining"
    assert summary["status"]["reviewed_runtime_patch_exists"] is True
    assert summary["status"]["production_acceptance_refresh_completed"] is True
    assert summary["status"]["failed_checks"] == ["b5a_anchor_found"]
    assert summary["b5a_blocker"]["candidate_key"] == "67x13"
    assert summary["reason_localization"]["failed_anchor_range"] == "118-119"
    assert summary["reason_localization"]["reason_taxonomy_complete"] is False
    assert summary["reason_localization"]["generic_residual_anchor_count"] == 2


def test_reason_taxonomy_can_represent_localized_failures(tmp_path: Path) -> None:
    samples = [
        {
            "anchor_idx": 118,
            "failure_reason": "signature_monotonic_forced_label",
        },
        {
            "anchor_idx": 119,
            "failure_reason": "ghost_overlap_forced_domain",
        },
        {
            "anchor_idx": 120,
            "failure_reason": "ghost_y_overlap_forced_label",
        },
    ]
    summary = build_post_acceptance_b5a_blocker_summary(
        _write_input_set(tmp_path, b5a=_base_b5a_summary(samples))
    )

    assert summary["reason_localization"]["reason_taxonomy_complete"] is True
    assert summary["reason_localization"]["reason_category_counts"] == {
        "signature_forced_label": 1,
        "ghost_overlap_forced_domain": 1,
        "ghost_y_overlap_forced_label": 1,
    }


def test_reason_taxonomy_uses_preserved_coordinate_validation_fields(
    tmp_path: Path,
) -> None:
    samples = [
        {
            "anchor_idx": 118,
            "failure_reason": "coordinate_validation_infeasible",
            "coordinate_validation_reason": (
                "signature_monotonic_forced_label_infeasible"
            ),
            "coordinate_validation_solver_profile_id": (
                "signature_monotonic_forced_label_precheck"
            ),
        },
        {
            "anchor_idx": 119,
            "failure_reason": "coordinate_validation_infeasible",
            "ghost_overlap_forced_domain_precheck": {
                "evaluated": True,
                "conflict": True,
            },
        },
    ]
    summary = build_post_acceptance_b5a_blocker_summary(
        _write_input_set(tmp_path, b5a=_base_b5a_summary(samples))
    )

    assert summary["reason_localization"]["reason_taxonomy_complete"] is True
    assert summary["reason_localization"]["reason_category_counts"] == {
        "signature_forced_label": 1,
        "ghost_overlap_forced_domain": 1,
    }
    assert summary["reason_localization"]["failed_anchor_samples"][0][
        "coordinate_validation_solver_profile_id"
    ] == "signature_monotonic_forced_label_precheck"


def test_summary_fails_closed_when_post_acceptance_state_is_stale(tmp_path: Path) -> None:
    gate = _base_acceptance_gate()
    gate["status"]["production_acceptance_refresh_completed"] = False
    summary = build_post_acceptance_b5a_blocker_summary(
        _write_input_set(tmp_path, acceptance_gate=gate)
    )

    assert summary["status"]["outcome"] == "post_acceptance_inputs_incomplete_or_stale"
    assert summary["status"]["summary_ready"] is False
    assert summary["metadata"]["proof_source"] is False
    assert summary["metadata"]["runtime_semantics_changed"] is False


def test_reason_classifier_known_tokens() -> None:
    assert (
        classify_coordinate_validation_failure_reason("coordinate_validation_infeasible")
        == "generic_residual"
    )
    assert (
        classify_coordinate_validation_failure_reason("attempt_limit_reached")
        == "attempt_limit"
    )
    assert (
        classify_coordinate_validation_failure_reason("signature_monotonic_forced_label")
        == "signature_forced_label"
    )


def test_cli_no_write_and_write_modes(tmp_path: Path) -> None:
    paths = _write_input_set(tmp_path)
    output_dir = tmp_path / "out"
    script = (
        Path(__file__).resolve().parents[4]
        / "scripts" / "phase3b" / "b5a" / "build_post_acceptance_blocker_summary.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--preflight-summary",
            str(paths.preflight_summary),
            "--b5a-operator-summary",
            str(paths.b5a_operator_summary),
            "--acceptance-result-validator",
            str(paths.acceptance_result_validator),
            "--acceptance-execution-gate",
            str(paths.acceptance_execution_gate),
            "--production-acceptance-handoff",
            str(paths.production_acceptance_handoff),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "post_acceptance_b5a_anchor_gate_remaining" in no_write.stdout
    assert not output_dir.exists()

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--preflight-summary",
            str(paths.preflight_summary),
            "--b5a-operator-summary",
            str(paths.b5a_operator_summary),
            "--acceptance-result-validator",
            str(paths.acceptance_result_validator),
            "--acceptance-execution-gate",
            str(paths.acceptance_execution_gate),
            "--production-acceptance-handoff",
            str(paths.production_acceptance_handoff),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "b5a_post_acceptance_blocker_summary.json").exists()
    assert (output_dir / "b5a_post_acceptance_blocker_summary.md").exists()
    assert (output_dir / "b5a_post_acceptance_blocker_summary.txt").exists()
