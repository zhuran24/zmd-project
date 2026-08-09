from __future__ import annotations

import json
from pathlib import Path

from src.search.phase3b.signature_monotonic.precheck_candidate import (
    SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE,
)
from src.search.phase3b.signature_monotonic.precheck_promotion_spec import (
    SIGNATURE_MONOTONIC_PRECHECK_PROMOTION_SPEC_SOURCE,
    build_phase3b_signature_monotonic_precheck_promotion_spec,
    render_phase3b_signature_monotonic_precheck_promotion_spec_markdown,
    render_phase3b_signature_monotonic_precheck_promotion_spec_text,
)


def _candidate(path: Path, *, gate: bool = True) -> Path:
    payload = {
        "metadata": {"source": SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE},
        "candidate": {"key": "67x13"},
        "gate": {"design_gate_passed": gate, "runtime_promotion_ready": False},
        "evidence": {
            "monotonic_infeasible_count": 3,
            "monotonic_feasible_control_count": 1,
        },
        "checks": [
            {"check_id": "minimum_monotonic_infeasible_count", "status": "pass", "detail": "ok"},
            {"check_id": "monotonic_feasible_control_present", "status": "pass", "detail": "ok"},
            {"check_id": "runtime_promotion_guard", "status": "fail", "detail": "guarded"},
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_signature_monotonic_promotion_spec_ready_but_guarded(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path / "precheck_candidate.json")

    spec = build_phase3b_signature_monotonic_precheck_promotion_spec(
        tmp_path,
        precheck_candidate_path=candidate,
    )

    assert spec["metadata"]["source"] == SIGNATURE_MONOTONIC_PRECHECK_PROMOTION_SPEC_SOURCE
    assert spec["promotion_status"]["spec_ready_for_runtime_slice"] is True
    assert spec["promotion_status"]["runtime_slice_implemented"] is True
    assert spec["promotion_status"]["runtime_promotion_ready"] is False
    assert spec["promotion_status"]["promotion_blocked_by"] == []
    assert "guarded/default-off" in render_phase3b_signature_monotonic_precheck_promotion_spec_markdown(spec)
    assert "runtime_slice_implemented=True" in render_phase3b_signature_monotonic_precheck_promotion_spec_text(spec)


def test_signature_monotonic_promotion_spec_blocks_when_candidate_gate_fails(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path / "precheck_candidate.json", gate=False)

    spec = build_phase3b_signature_monotonic_precheck_promotion_spec(
        tmp_path,
        precheck_candidate_path=candidate,
    )

    assert spec["promotion_status"]["spec_ready_for_runtime_slice"] is False
    assert "design_gate_not_passed" in spec["promotion_status"]["promotion_blocked_by"]
