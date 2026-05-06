from __future__ import annotations

import json
from pathlib import Path

from src.search.phase3b_signature_monotonic_forced_label_audit import (
    SIGNATURE_MONOTONIC_FORCED_LABEL_AUDIT_SOURCE,
)
from src.search.phase3b_signature_monotonic_precheck_candidate import (
    SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE,
    build_phase3b_signature_monotonic_precheck_candidate_summary,
    render_phase3b_signature_monotonic_precheck_candidate_markdown,
    render_phase3b_signature_monotonic_precheck_candidate_text,
)


def _audit(path: Path, *, outcome: str) -> Path:
    payload = {
        "metadata": {
            "source": SIGNATURE_MONOTONIC_FORCED_LABEL_AUDIT_SOURCE,
            "solver_invoked": False,
            "proof_source": False,
        },
        "candidate": {"key": "67x13"},
        "monotonicity": {
            "outcome": outcome,
            "label_count": 3,
            "constrained_slot_count": 2,
            "failure": {
                "slot_index": 16,
                "previous_possible_signature_ids": [3],
                "current_allowed_signature_ids": [2],
            }
            if outcome == "monotonic_infeasible"
            else None,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_signature_monotonic_precheck_candidate_passes_with_control(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audits"
    audit_dir.mkdir()
    for name in ["source_earlier", "source_sweep", "combo_006"]:
        _audit(audit_dir / f"signature_monotonic_{name}.json", outcome="monotonic_infeasible")
    control = _audit(tmp_path / "signature_monotonic_control.json", outcome="monotonic_feasible")

    summary = build_phase3b_signature_monotonic_precheck_candidate_summary(
        tmp_path,
        audit_dir=audit_dir,
        control_audit_path=control,
    )

    assert summary["metadata"]["source"] == SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE
    assert summary["gate"]["design_gate_passed"] is True
    assert summary["gate"]["runtime_promotion_ready"] is False
    assert summary["evidence"]["monotonic_infeasible_count"] == 3
    assert summary["evidence"]["monotonic_feasible_control_count"] == 1
    failed = [check["check_id"] for check in summary["checks"] if check["status"] == "fail"]
    assert failed == ["runtime_promotion_guard"]
    assert "Signature-Monotonic" in render_phase3b_signature_monotonic_precheck_candidate_markdown(summary)
    assert "runtime_promotion_ready=False" in render_phase3b_signature_monotonic_precheck_candidate_text(summary)


def test_signature_monotonic_precheck_candidate_requires_control(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audits"
    audit_dir.mkdir()
    for name in ["source_earlier", "source_sweep", "combo_006"]:
        _audit(audit_dir / f"signature_monotonic_{name}.json", outcome="monotonic_infeasible")

    summary = build_phase3b_signature_monotonic_precheck_candidate_summary(
        tmp_path,
        audit_dir=audit_dir,
    )

    assert summary["gate"]["design_gate_passed"] is False
    failed = {check["check_id"] for check in summary["checks"] if check["status"] == "fail"}
    assert "monotonic_feasible_control_present" in failed


def test_signature_monotonic_precheck_candidate_rejects_non_infeasible_evidence(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audits"
    audit_dir.mkdir()
    _audit(audit_dir / "signature_monotonic_source_earlier.json", outcome="monotonic_infeasible")
    _audit(audit_dir / "signature_monotonic_source_sweep.json", outcome="monotonic_feasible")
    _audit(audit_dir / "signature_monotonic_combo_006.json", outcome="monotonic_infeasible")
    control = _audit(tmp_path / "signature_monotonic_control.json", outcome="monotonic_feasible")

    summary = build_phase3b_signature_monotonic_precheck_candidate_summary(
        tmp_path,
        audit_dir=audit_dir,
        control_audit_path=control,
        min_infeasible_count=2,
    )

    assert summary["gate"]["design_gate_passed"] is False
    failed = {check["check_id"] for check in summary["checks"] if check["status"] == "fail"}
    assert "no_non_infeasible_evidence_cases" in failed
