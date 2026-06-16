from __future__ import annotations

import json
from pathlib import Path

from src.search.phase3b.anchor119 import guarded_precheck_runtime as runtime_module
from src.search.phase3b.anchor119.guarded_precheck_runtime import (
    evaluate_phase3b_anchor119_guarded_precheck_advisory,
)


def _write_spec(path: Path, *, hashes: dict[str, str], all_gates_pass: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": {
                    "outcome": "guarded_precheck_spec_ready_for_review",
                    "all_gates_pass": all_gates_pass,
                    "runtime_precheck_enabled": False,
                },
                "candidate": {
                    "key": "67x13",
                    "anchor_idx": 119,
                    "ghost_rect": {"x": 2, "y": 3, "w": 67, "h": 13},
                },
                "artifact_hashes": {
                    "current_exact_artifact_hashes": hashes,
                },
                "evidence": {
                    "domain_hash": "domain-hash",
                    "tiling_outcome": "exact_tiling_exhaustive_no_witness",
                    "dp_outcome": "dp_crosscheck_exhaustive_no_witness",
                    "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
                    "non_trigger_max_slot_count": 13,
                    "anchored_trigger_min_slot_count": 14,
                    "free_ghost_trigger_min_slot_count": 15,
                },
                "proposed_guard": {
                    "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
                    "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
                    "non_trigger_controls": {
                        "non_trigger_max_slot_count": 13,
                        "anchored_trigger_min_slot_count": 14,
                        "free_ghost_trigger_min_slot_count": 15,
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_advisory_default_disabled_does_not_require_spec(tmp_path: Path) -> None:
    missing_spec = tmp_path / "missing.json"

    result = evaluate_phase3b_anchor119_guarded_precheck_advisory(
        project_root=tmp_path,
        ghost_w=67,
        ghost_h=13,
        anchor_idx=119,
        spec_path=missing_spec,
        enabled=False,
    )

    assert result["enabled"] is False
    assert result["triggered"] is False
    assert result["would_trigger"] is False
    assert result["reason"] == "disabled"
    assert result["proof_summary"] == {}
    assert result["metadata"]["runtime_precheck_enabled"] is False
    assert result["metadata"]["runtime_semantics_changed"] is False
    assert result["metadata"]["proof_source"] is False


def test_advisory_enabled_reports_would_trigger_but_never_triggers(tmp_path: Path) -> None:
    hashes = {
        "mandatory_exact_instances": "a",
        "candidate_placements": "b",
        "canonical_rules": "c",
        "generic_io_requirements": "d",
    }
    spec = tmp_path / "spec.json"
    _write_spec(spec, hashes=hashes)

    result = evaluate_phase3b_anchor119_guarded_precheck_advisory(
        project_root=tmp_path,
        ghost_w=67,
        ghost_h=13,
        anchor_idx=119,
        spec_path=spec,
        enabled=True,
        current_hashes=hashes,
    )

    assert result["enabled"] is True
    assert result["triggered"] is False
    assert result["would_trigger"] is True
    assert result["status"] == "INFEASIBLE"
    assert result["reason"] == "advisory_guard_would_reject_anchor119"
    assert result["proof_summary"]["master_candidate_precheck"]["triggered"] is False
    assert result["proof_summary"]["master_candidate_precheck"]["would_trigger"] is True
    advisory = result["proof_summary"]["anchor119_mixed_lane_guarded_precheck"]
    assert advisory["advisory_only"] is True
    assert advisory["requested_state"] == "advisory_enabled"
    assert advisory["effective_state"] == "advisory_enabled"
    assert advisory["runtime_precheck_enabled"] is False
    assert advisory["runtime_activation_allowed"] is False
    assert advisory["runtime_semantics_changed"] is False
    assert advisory["proof_source"] is False
    assert advisory["candidate_elimination_claim"] is False
    assert "reviewed_runtime_patch_missing" in advisory["runtime_enablement_blockers"]
    assert advisory["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert advisory["non_trigger_max_slot_count"] == 13
    assert advisory["anchored_trigger_min_slot_count"] == 14
    assert advisory["free_ghost_trigger_min_slot_count"] == 15


def test_advisory_enabled_blocks_wrong_candidate(tmp_path: Path) -> None:
    hashes = {"mandatory_exact_instances": "a"}
    spec = tmp_path / "spec.json"
    _write_spec(spec, hashes=hashes)

    result = evaluate_phase3b_anchor119_guarded_precheck_advisory(
        project_root=tmp_path,
        ghost_w=66,
        ghost_h=13,
        anchor_idx=119,
        spec_path=spec,
        enabled=True,
        current_hashes=hashes,
    )

    assert result["triggered"] is False
    assert result["would_trigger"] is False
    assert result["reason"] == "guard_checks_failed"
    checks = {check["check_id"]: check["status"] for check in result["checks"]}
    assert checks["candidate_matches"] == "fail"


def test_advisory_evaluation_reads_env_when_enabled_argument_is_omitted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    hashes = {
        "mandatory_exact_instances": "a",
        "candidate_placements": "b",
        "canonical_rules": "c",
        "generic_io_requirements": "d",
    }
    spec = tmp_path / "spec.json"
    _write_spec(spec, hashes=hashes)
    monkeypatch.setenv(runtime_module.ANCHOR119_GUARDED_PRECHECK_ENV, "true")

    result = evaluate_phase3b_anchor119_guarded_precheck_advisory(
        project_root=tmp_path,
        ghost_w=67,
        ghost_h=13,
        anchor_idx=119,
        spec_path=spec,
        current_hashes=hashes,
    )

    assert result["enabled"] is True
    assert result["would_trigger"] is True
    assert result["triggered"] is False
    assert result["reason"] == "advisory_guard_would_reject_anchor119"
    assert result["metadata"]["requested_state"] == "advisory_enabled"
    assert result["metadata"]["runtime_precheck_enabled"] is False
    assert result["metadata"]["runtime_semantics_changed"] is False
    assert result["metadata"]["proof_source"] is False

def test_runtime_patch_path_can_be_authored_but_stays_default_off_until_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    hashes = {
        "mandatory_exact_instances": "a",
        "candidate_placements": "b",
        "canonical_rules": "c",
        "generic_io_requirements": "d",
    }
    spec = tmp_path / "spec.json"
    _write_spec(spec, hashes=hashes)

    monkeypatch.setattr(
        runtime_module,
        "build_phase3b_anchor119_guard_runtime_state",
        lambda advisory_env_raw=None: {
            "env_name": "EXACT_PRE_MASTER_ANCHOR119_MIXED_LANE_GUARD_ADVISORY",
            "truthy_values": ["1", "true", "yes", "on"],
            "runtime_request_values": [
                "runtime",
                "apply",
                "reserved",
                "runtime_enabled_reserved",
            ],
            "requested_state": "runtime_enabled_reserved",
            "effective_state": "runtime_enabled_reserved",
            "default_state": "disabled",
            "advisory_enabled": True,
            "runtime_requested": True,
            "advisory_only": False,
            "default_off": True,
            "runtime_precheck_enabled": True,
            "runtime_activation_allowed": True,
            "runtime_enablement_blockers": [],
        },
    )

    result = evaluate_phase3b_anchor119_guarded_precheck_advisory(
        project_root=tmp_path,
        ghost_w=67,
        ghost_h=13,
        anchor_idx=119,
        spec_path=spec,
        current_hashes=hashes,
    )

    assert result["enabled"] is True
    assert result["would_trigger"] is True
    assert result["triggered"] is True
    assert result["status"] == "INFEASIBLE"
    assert result["reason"] == "runtime_guard_reject_anchor119"
    assert result["metadata"]["runtime_precheck_enabled"] is True
    assert result["metadata"]["runtime_semantics_changed"] is True
    assert result["metadata"]["proof_source"] is True
    precheck = result["proof_summary"]["master_candidate_precheck"]
    assert precheck["triggered"] is True
    assert precheck["precheck_reason"] == "anchor119_row_domain_runtime_guard"
    assert precheck["master_solve_skipped"] is True
    advisory = result["proof_summary"]["anchor119_mixed_lane_guarded_precheck"]
    assert advisory["advisory_only"] is False
    assert advisory["runtime_precheck_enabled"] is True
    assert advisory["proof_source"] is True
    assert advisory["candidate_elimination_claim"] is True
