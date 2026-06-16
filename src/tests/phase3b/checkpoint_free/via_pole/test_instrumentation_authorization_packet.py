from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.via_pole.build_instrumentation_authorization_packet import (
    build_via_pole_instrumentation_authorization_packet,
)


def test_authorization_packet_collects_scope_and_auth_text(tmp_path: Path) -> None:
    spec = tmp_path / "via_pole_shape_instrumentation_patch_spec.json"
    decision = tmp_path / "checkpoint_free_next_decision.json"
    _write_spec(spec)
    _write_next_decision(decision)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "32_via_pole_instrumentation_authorization_packet"
    )

    packet = build_via_pole_instrumentation_authorization_packet(
        spec_path=spec,
        next_decision_path=decision,
        output_dir=output_dir,
    )

    assert packet["status"] == "completed"
    assert packet["authorization"]["authorization_required"] is True
    assert packet["authorization"]["implementation_allowed_now"] is False
    assert "I explicitly authorize Codex" in packet["authorization"]["proposed_authorization_text"]
    assert packet["patch_scope"]["env_var"] == "EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION"
    assert (output_dir / "via_pole_instrumentation_authorization_packet.json").exists()
    assert (output_dir / "via_pole_instrumentation_authorization_packet.md").exists()


def test_authorization_packet_no_write_does_not_create_output_dir(tmp_path: Path) -> None:
    spec = tmp_path / "via_pole_shape_instrumentation_patch_spec.json"
    decision = tmp_path / "checkpoint_free_next_decision.json"
    _write_spec(spec)
    _write_next_decision(decision)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "32_via_pole_instrumentation_authorization_packet"
    )

    packet = build_via_pole_instrumentation_authorization_packet(
        spec_path=spec,
        next_decision_path=decision,
        output_dir=output_dir,
        no_write=True,
    )

    assert packet["status"] == "completed"
    assert not output_dir.exists()


def test_authorization_packet_blocks_unready_spec(tmp_path: Path) -> None:
    spec = tmp_path / "via_pole_shape_instrumentation_patch_spec.json"
    decision = tmp_path / "checkpoint_free_next_decision.json"
    _write_spec(spec, classification="manual_review_required")
    _write_next_decision(decision)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "32_via_pole_instrumentation_authorization_packet"
    )

    packet = build_via_pole_instrumentation_authorization_packet(
        spec_path=spec,
        next_decision_path=decision,
        output_dir=output_dir,
        no_write=True,
    )

    assert packet["status"] == "blocked"


def test_authorization_packet_rejects_bad_namespace(tmp_path: Path) -> None:
    spec = tmp_path / "via_pole_shape_instrumentation_patch_spec.json"
    decision = tmp_path / "checkpoint_free_next_decision.json"
    _write_spec(spec)
    _write_next_decision(decision)

    with pytest.raises(ValueError, match="authorization packet namespace"):
        build_via_pole_instrumentation_authorization_packet(
            spec_path=spec,
            next_decision_path=decision,
            output_dir=tmp_path / "bad",
        )


def _write_spec(path: Path, *, classification: str = "patch_spec_ready_source_mutation_still_blocked") -> None:
    ready = classification == "patch_spec_ready_source_mutation_still_blocked"
    path.write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": classification,
                    "implementation_allowed_now": False,
                    "source_mutation_authorized_by_this_artifact": False,
                },
                "patch_spec": {
                    "target_file": "src/models/exact_coordinate_master.py",
                    "target_method": "CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen",
                    "env_var": "EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION",
                    "default_behavior": "disabled",
                    "diagnostic_behavior": "record extra counters without changing constraints",
                    "non_goals": ["do not change production defaults"],
                },
                "validation_plan": [{"id": "default_off_regression", "check": "tests pass"}],
                "recommendation": {
                    "action": (
                        "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
                        if ready
                        else "hold_for_manual_review"
                    ),
                    "blocked_actions": ["do_not_write_canonical_checkpoints"],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_next_decision(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "recommendation": {
                    "action": "hold_for_default_off_via_pole_shape_instrumentation_source_authorization",
                    "global_block_reason": "source_mutation_authorization_required",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
