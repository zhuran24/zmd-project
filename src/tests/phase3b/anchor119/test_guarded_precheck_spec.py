from __future__ import annotations

from pathlib import Path

import pytest

from src.search.phase3b.anchor119.guarded_precheck_spec import (
    build_phase3b_anchor119_guarded_precheck_spec,
    render_phase3b_anchor119_guarded_precheck_spec_markdown,
    render_phase3b_anchor119_guarded_precheck_spec_text,
)


def test_current_artifacts_build_ready_for_review_spec() -> None:
    project_root = Path(__file__).resolve().parents[4]
    required = [
        project_root
        / ".artifacts/phase3b_anchor119_pair_x_global_context_synthesis_20260423/global_context_synthesis.json",
        project_root
        / ".artifacts/phase3b_anchor119_mixed_lane_tiling_verifier_module_20260423/mixed_lane_tiling_verifier.json",
        project_root
        / ".artifacts/phase3b_anchor119_mixed_lane_dp_crosscheck_20260423/mixed_lane_dp_crosscheck.json",
    ]
    if not all(path.exists() for path in required):
        pytest.skip("current guarded precheck input artifacts are not present")

    report = build_phase3b_anchor119_guarded_precheck_spec(project_root)

    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["runtime_precheck_enabled"] is False
    assert report["metadata"]["runtime_semantics_changed"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["candidate_elimination_claim"] is False
    assert report["status"]["outcome"] == "guarded_precheck_spec_ready_for_review"
    assert report["status"]["all_gates_pass"] is True
    assert report["status"]["runtime_precheck_enabled"] is False
    assert report["evidence"]["domain_hash_match"] is True
    assert report["evidence"]["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert report["evidence"]["non_trigger_max_slot_count"] == 13
    assert report["evidence"]["anchored_trigger_min_slot_count"] == 14
    assert report["proposed_guard"]["default_state"] == "disabled"
    assert report["proposed_guard"]["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert report["proposed_guard"]["runtime_hook"] == "none_in_this_patch"
    assert {check["status"] for check in report["checks"]} == {"pass"}


def test_renderers_keep_spec_only_boundaries() -> None:
    report = {
        "status": {
            "outcome": "guarded_precheck_spec_ready_for_review",
            "all_gates_pass": True,
            "recommendation": "review only",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
        },
        "proposed_guard": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "scope": "candidate=67x13",
            "default_state": "disabled",
            "runtime_hook": "none_in_this_patch",
        },
        "evidence": {
            "tiling_outcome": "exact_tiling_exhaustive_no_witness",
            "dp_outcome": "dp_crosscheck_exhaustive_no_witness",
            "domain_hash_match": True,
            "tiling_total_patterns": 4608,
            "dp_final_cover_states": 9,
            "dp_p9p10_pairs_checked": 0,
            "payload_id": "payload-v0",
            "non_trigger_max_slot_count": 13,
            "anchored_trigger_min_slot_count": 14,
        },
        "checks": [
            {"check_id": "spec_only", "status": "pass", "detail": "report layer"}
        ],
    }

    markdown = render_phase3b_anchor119_guarded_precheck_spec_markdown(report)
    text = render_phase3b_anchor119_guarded_precheck_spec_text(report)

    assert "Spec only: true" in markdown
    assert "Runtime precheck enabled: false" in markdown
    assert "Runtime semantics changed: false" in markdown
    assert "Proof source: false" in markdown
    assert "spec_only=true" in text
    assert "runtime_precheck_enabled=false" in text
    assert "runtime_semantics_changed=false" in text
    assert "proof_source=false" in text
    assert "payload_id=payload-v0" in text
