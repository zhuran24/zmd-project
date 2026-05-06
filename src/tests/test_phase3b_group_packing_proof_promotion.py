from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_group_packing_proof_promotion import (
    build_phase3b_group_packing_proof_promotion_blockers,
    render_phase3b_group_packing_proof_promotion_markdown,
    render_phase3b_group_packing_proof_promotion_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _promotion_spec_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_group_packing_precheck_promotion_spec_v1"},
        "candidate": {"key": "69x19"},
        "promotion_status": {
            "spec_ready_for_runtime_slice": True,
            "design_gate_passed": True,
            "runtime_promotion_ready": False,
            "runtime_promotion_guarded": True,
        },
        "evidence_summary": {
            "sample_count": 51,
            "infeasible_count": 51,
            "feasible_count": 0,
            "unknown_count": 0,
            "skipped_count": 0,
            "blocker_count": 3,
        },
    }


def _runtime_diagnostic_payload(*, sample_count: int = 8) -> dict:
    return {
        "metadata": {"source": "phase3b_runtime_group_packing_diagnostic_v1"},
        "candidate": {"key": "69x19"},
        "input_evidence": {
            "failed_anchor_count": 51,
            "failed_anchor_sample_count": sample_count,
        },
        "status": {
            "evaluated": True,
            "outcome": "diagnostic_group_packing_infeasible",
        },
        "diagnostics": {
            "group_packing_probe": {
                "sample_count": sample_count,
                "infeasible_count": sample_count,
                "feasible_count": 0,
                "unknown_count": 0,
                "skipped_count": 0,
            },
            "group_packing_blockers": {
                "blocker_count": 3,
                "precheck_design_candidate": True,
            },
        },
        "campaign_state_unchanged": True,
    }


def _soundness_gate_payload(
    *,
    sample_count: int = 8,
    terminal_sound: bool = False,
) -> dict:
    blockers = []
    terminal_safe_count = sample_count
    prefix_conditioned_count = 0
    if not terminal_sound:
        blockers = [
            "prefix_conditioned_evidence_not_terminal_safe",
            "terminal_safe_coverage_incomplete",
        ]
        terminal_safe_count = 0
        prefix_conditioned_count = sample_count
    return {
        "metadata": {"source": "phase3b_group_packing_soundness_gate_v1"},
        "candidate": {"key": "69x19"},
        "soundness": {
            "runtime_diagnostic_present": True,
            "all_samples_infeasible": True,
            "sample_count": sample_count,
            "terminal_safe_sample_count": terminal_safe_count,
            "prefix_conditioned_sample_count": prefix_conditioned_count,
            "terminal_elimination_sound": terminal_sound,
            "blocked_by": blockers,
        },
    }


def _ghost_only_payload(
    *,
    sample_count: int = 8,
    feasible_count: int = 8,
) -> dict:
    outcome = (
        "ghost_only_feasible_counterexample_found"
        if feasible_count > 0
        else "ghost_only_uniformly_infeasible"
    )
    return {
        "metadata": {"source": "phase3b_group_packing_ghost_only_verifier_v1"},
        "candidate": {"key": "69x19"},
        "status": {
            "evaluated": True,
            "outcome": outcome,
        },
        "ghost_only_verifier": {
            "sample_count": sample_count,
            "feasible_count": feasible_count,
            "infeasible_count": sample_count - feasible_count,
            "unknown_count": 0,
            "skipped_count": 0,
        },
        "campaign_state_unchanged": True,
    }


def _pre_master_profile_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_pre_master_precheck_profiler_v1"},
        "candidate": {"key": "69x19"},
        "status": {
            "completed": True,
            "outcome": "not_eliminated_by_bounded_pre_master",
        },
        "stages": {
            "boundary_port_precheck": {
                "summary": {
                    "supported": True,
                    "considered_anchor_count": 104,
                    "screen_pass_anchor_count": 51,
                }
            },
            "mandatory_rectangle_precheck": {
                "status": "skipped",
                "skip_reason": "pre_master_anchor_cap_exceeded",
                "anchor_count": 51,
                "pre_master_anchor_cap": 32,
            },
        },
    }


def _b5a_summary_payload(*, pose_order_rejected_count: int = 0) -> dict:
    return {
        "metadata": {"source": "phase3b_b5_anchor_sprint_summary_v1"},
        "status": {
            "anchor_found": False,
            "outcome": "triage_required",
        },
        "campaign": {
            "final_status": "UNKNOWN",
            "last_stop_reason": {"reason": "candidate_returned_unknown"},
        },
        "runtime_group_packing": {
            "present": True,
            "diagnostic_count": 1,
            "current_candidate_keys": ["69x19"],
            "relevant_diagnostic_count": 1,
            "stale_diagnostic_count": 0,
            "reports": [
                {
                    "candidate_key": "69x19",
                    "outcome": "diagnostic_group_packing_infeasible",
                    "blocker_count": 3,
                    "campaign_state_unchanged": True,
                }
            ],
            "relevant_reports": [
                {
                    "candidate_key": "69x19",
                    "outcome": "diagnostic_group_packing_infeasible",
                    "blocker_count": 3,
                    "campaign_state_unchanged": True,
                }
            ],
            "stale_reports": [],
        },
        "pose_order_validation": {
            "rejected_count": pose_order_rejected_count,
            "reason_counts": (
                {"infeasible": pose_order_rejected_count}
                if pose_order_rejected_count
                else {}
            ),
            "status_counts": (
                {"INFEASIBLE": pose_order_rejected_count}
                if pose_order_rejected_count
                else {}
            ),
        },
    }


def _write_inputs(project_root: Path, *, runtime_sample_count: int = 8) -> dict[str, Path]:
    paths = {
        "promotion": project_root / "promotion.json",
        "runtime": project_root / "runtime.json",
        "soundness": project_root / "soundness.json",
        "ghost_only": project_root / "ghost_only.json",
        "profile": project_root / "profile.json",
        "b5a": project_root / "b5a.json",
    }
    _write_json(paths["promotion"], _promotion_spec_payload())
    _write_json(paths["runtime"], _runtime_diagnostic_payload(sample_count=runtime_sample_count))
    _write_json(paths["soundness"], _soundness_gate_payload(sample_count=runtime_sample_count))
    _write_json(paths["ghost_only"], _ghost_only_payload(sample_count=runtime_sample_count))
    _write_json(paths["profile"], _pre_master_profile_payload())
    _write_json(paths["b5a"], _b5a_summary_payload())
    return paths


def test_proof_promotion_report_blocks_even_with_strong_diagnostics(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root)

    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=paths["promotion"],
        runtime_diagnostic_path=paths["runtime"],
        soundness_gate_path=paths["soundness"],
        ghost_only_verifier_path=paths["ghost_only"],
        pre_master_profile_path=paths["profile"],
        b5a_summary_path=paths["b5a"],
    )

    assert report["metadata"]["source"] == (
        "phase3b_group_packing_proof_promotion_blockers_v1"
    )
    assert report["promotion_readiness"]["diagnostic_evidence_ready"] is True
    assert report["promotion_readiness"]["proof_promotion_ready"] is False
    assert "prefix_conditioned_evidence_not_terminal_safe" in report["promotion_readiness"]["blocked_by"]
    assert "terminal_safe_coverage_incomplete" in report["promotion_readiness"]["blocked_by"]
    assert "ghost_only_feasible_counterexample_found" in report["promotion_readiness"]["blocked_by"]
    assert "proof_semantics_not_implemented" not in report["promotion_readiness"]["blocked_by"]
    assert "runtime_sample_coverage_below_full_diagnostic" in report["promotion_readiness"]["blocked_by"]
    assert report["evidence"]["runtime_group_packing"]["sample_count"] == 8
    assert report["evidence"]["soundness_gate"]["prefix_conditioned_sample_count"] == 8
    assert report["evidence"]["promotion_spec"]["sample_count"] == 51

    markdown = render_phase3b_group_packing_proof_promotion_markdown(report)
    text = render_phase3b_group_packing_proof_promotion_text(report)
    assert "Proof promotion ready: False" in markdown
    assert "runtime_sample_coverage_below_full_diagnostic" in markdown
    assert "proof_promotion_ready=False" in text


def test_proof_promotion_report_fails_when_runtime_diagnostic_missing(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root)
    paths["runtime"].unlink()

    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=paths["promotion"],
        runtime_diagnostic_path=paths["runtime"],
        soundness_gate_path=paths["soundness"],
        ghost_only_verifier_path=paths["ghost_only"],
        pre_master_profile_path=paths["profile"],
        b5a_summary_path=paths["b5a"],
    )

    assert report["promotion_readiness"]["diagnostic_evidence_ready"] is False
    assert "runtime_group_packing_missing" in report["promotion_readiness"]["blocked_by"]
    assert _check_status(report, "runtime_group_packing_infeasible") == "fail"


def test_proof_promotion_report_clears_sample_blocker_at_full_runtime_coverage(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root, runtime_sample_count=51)

    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=paths["promotion"],
        runtime_diagnostic_path=paths["runtime"],
        soundness_gate_path=paths["soundness"],
        ghost_only_verifier_path=paths["ghost_only"],
        pre_master_profile_path=paths["profile"],
        b5a_summary_path=paths["b5a"],
    )

    blocked_by = report["promotion_readiness"]["blocked_by"]
    assert "runtime_sample_coverage_below_full_diagnostic" not in blocked_by
    assert blocked_by == [
        "prefix_conditioned_evidence_not_terminal_safe",
        "terminal_safe_coverage_incomplete",
        "ghost_only_feasible_counterexample_found",
        "terminal_proof_integration_missing",
        "post_promotion_b5a_rerun_missing",
    ]
    assert _check_status(report, "runtime_sample_coverage_matches_full_diagnostic") == "pass"
    assert _check_status(report, "soundness_gate_terminal_safe") == "fail"
    assert _check_status(report, "coordinate_pose_order_validation_clear") == "pass"
    assert _check_status(report, "proof_semantics_implemented") == "skipped"


def test_proof_promotion_report_blocks_coordinate_rejected_pose_order(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root, runtime_sample_count=51)
    _write_json(paths["b5a"], _b5a_summary_payload(pose_order_rejected_count=1))

    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=paths["promotion"],
        runtime_diagnostic_path=paths["runtime"],
        soundness_gate_path=paths["soundness"],
        ghost_only_verifier_path=paths["ghost_only"],
        pre_master_profile_path=paths["profile"],
        b5a_summary_path=paths["b5a"],
    )

    assert "coordinate_pose_order_validation_infeasible" in report[
        "promotion_readiness"
    ]["blocked_by"]
    assert _check_status(report, "coordinate_pose_order_validation_clear") == "fail"


def test_proof_promotion_report_requires_b5a_relevant_group_packing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root, runtime_sample_count=51)
    b5a = _b5a_summary_payload()
    b5a["runtime_group_packing"]["current_candidate_keys"] = ["67x13"]
    b5a["runtime_group_packing"]["relevant_diagnostic_count"] = 0
    b5a["runtime_group_packing"]["stale_diagnostic_count"] = 1
    b5a["runtime_group_packing"]["relevant_reports"] = []
    b5a["runtime_group_packing"]["stale_reports"] = list(
        b5a["runtime_group_packing"]["reports"]
    )
    _write_json(paths["b5a"], b5a)

    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=paths["promotion"],
        runtime_diagnostic_path=paths["runtime"],
        soundness_gate_path=paths["soundness"],
        ghost_only_verifier_path=paths["ghost_only"],
        pre_master_profile_path=paths["profile"],
        b5a_summary_path=paths["b5a"],
    )

    assert "b5a_summary_missing_runtime_group_packing" in report[
        "promotion_readiness"
    ]["blocked_by"]
    assert "b5a_current_candidate_mismatch_for_promotion" in report[
        "promotion_readiness"
    ]["blocked_by"]
    assert _check_status(report, "b5a_summary_links_runtime_group_packing") == "fail"
    assert _check_status(report, "b5a_current_candidate_matches_promotion_candidate") == "fail"


def test_proof_promotion_report_blocks_b5a_candidate_mismatch_even_with_relevant_diagnostic(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root, runtime_sample_count=51)
    b5a = _b5a_summary_payload()
    b5a["runtime_group_packing"]["current_candidate_keys"] = ["67x13"]
    b5a["runtime_group_packing"]["relevant_diagnostic_count"] = 1
    b5a["runtime_group_packing"]["relevant_reports"] = [
        {
            "candidate_key": "67x13",
            "outcome": "diagnostic_group_packing_mixed_or_incomplete",
            "blocker_count": 0,
            "campaign_state_unchanged": True,
        }
    ]
    _write_json(paths["b5a"], b5a)

    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=paths["promotion"],
        runtime_diagnostic_path=paths["runtime"],
        soundness_gate_path=paths["soundness"],
        ghost_only_verifier_path=paths["ghost_only"],
        pre_master_profile_path=paths["profile"],
        b5a_summary_path=paths["b5a"],
    )

    assert "b5a_summary_missing_runtime_group_packing" not in report[
        "promotion_readiness"
    ]["blocked_by"]
    assert "b5a_current_candidate_mismatch_for_promotion" in report[
        "promotion_readiness"
    ]["blocked_by"]
    assert _check_status(report, "b5a_summary_links_runtime_group_packing") == "pass"
    assert _check_status(report, "b5a_current_candidate_matches_promotion_candidate") == "fail"


def test_proof_promotion_report_reaches_semantics_blocker_when_soundness_is_terminal_safe(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root, runtime_sample_count=51)
    _write_json(
        paths["soundness"],
        _soundness_gate_payload(sample_count=51, terminal_sound=True),
    )
    _write_json(paths["ghost_only"], _ghost_only_payload(sample_count=51, feasible_count=0))

    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=paths["promotion"],
        runtime_diagnostic_path=paths["runtime"],
        soundness_gate_path=paths["soundness"],
        ghost_only_verifier_path=paths["ghost_only"],
        pre_master_profile_path=paths["profile"],
        b5a_summary_path=paths["b5a"],
    )

    assert report["promotion_readiness"]["blocked_by"] == [
        "proof_semantics_not_implemented",
        "terminal_proof_integration_missing",
        "post_promotion_b5a_rerun_missing",
    ]
    assert _check_status(report, "soundness_gate_terminal_safe") == "pass"
    assert _check_status(report, "terminal_proof_integration") == "fail"
    assert _check_status(report, "proof_semantics_implemented") == "fail"


def test_proof_promotion_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    paths = _write_inputs(project_root)
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_group_packing_proof_promotion.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--promotion-spec",
            str(paths["promotion"]),
            "--runtime-diagnostic",
            str(paths["runtime"]),
            "--soundness-gate",
            str(paths["soundness"]),
            "--ghost-only-verifier",
            str(paths["ghost_only"]),
            "--pre-master-profile",
            str(paths["profile"]),
            "--b5a-summary",
            str(paths["b5a"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b group-packing proof-promotion blockers" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--promotion-spec",
            str(paths["promotion"]),
            "--runtime-diagnostic",
            str(paths["runtime"]),
            "--soundness-gate",
            str(paths["soundness"]),
            "--ghost-only-verifier",
            str(paths["ghost_only"]),
            "--pre-master-profile",
            str(paths["profile"]),
            "--b5a-summary",
            str(paths["b5a"]),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "proof_promotion_blockers_json=" in write.stdout
    payload = json.loads((output_dir / "proof_promotion_blockers.json").read_text(encoding="utf-8"))
    assert payload["promotion_readiness"]["diagnostic_evidence_ready"] is True
    assert (output_dir / "proof_promotion_blockers.md").exists()
    assert (output_dir / "proof_promotion_blockers.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
