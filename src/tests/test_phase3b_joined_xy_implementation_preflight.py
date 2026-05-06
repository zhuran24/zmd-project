from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_joined_xy_implementation_preflight import (
    build_phase3b_joined_xy_implementation_preflight,
    render_phase3b_joined_xy_implementation_preflight_markdown,
    render_phase3b_joined_xy_implementation_preflight_text,
)


def test_joined_xy_implementation_preflight_ready(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, blowup=True, profile_valid=True, grouped_ready=True)

    report = build_phase3b_joined_xy_implementation_preflight(
        tmp_path,
        sat_expansion_audit_path=paths["sat"],
        grouped_profile_audit_path=paths["profile"],
        grouped_implementation_preflight_path=paths["grouped_preflight"],
    )

    status = report["status"]
    counts = report["expected_no_solve_stats"]
    assert status["outcome"] == "joined_xy_implementation_preflight_ready"
    assert status["ready_for_default_off_model_edit"] is True
    assert report["metadata"]["solver_invoked"] is False
    assert report["proposed_mode"]["value"] == "selected_block_active_guard_joined_xy"
    assert counts["cover_choice_padded_idx_variables"] == 0
    assert counts["grouped_xy_current_padded_idx_variables"] == 2
    assert counts["retained_per_block_xy_target_variables"] == 8
    assert counts["joined_xy_target_channel_count"] == 4
    assert counts["total_block_element_constraints"] == 12
    assert counts["joined_xy_selected_geometry_constraint_count"] == 8
    assert "Joined-XY Implementation Preflight" in (
        render_phase3b_joined_xy_implementation_preflight_markdown(report)
    )
    assert "ready_for_default_off_model_edit=True" in (
        render_phase3b_joined_xy_implementation_preflight_text(report)
    )


def test_joined_xy_implementation_preflight_blocks_without_blowup(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, blowup=False, profile_valid=True, grouped_ready=True)

    report = build_phase3b_joined_xy_implementation_preflight(
        tmp_path,
        sat_expansion_audit_path=paths["sat"],
        grouped_profile_audit_path=paths["profile"],
        grouped_implementation_preflight_path=paths["grouped_preflight"],
    )

    assert report["status"]["outcome"] == "joined_xy_implementation_preflight_blocked"
    assert report["status"]["ready_for_default_off_model_edit"] is False
    assert any(
        check["check_id"] == "grouped_xy_blowup_recorded"
        and check["status"] == "fail"
        for check in report["checks"]
    )


def test_joined_xy_implementation_preflight_blocks_if_grouped_preflight_not_ready(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, blowup=True, profile_valid=True, grouped_ready=False)

    report = build_phase3b_joined_xy_implementation_preflight(
        tmp_path,
        sat_expansion_audit_path=paths["sat"],
        grouped_profile_audit_path=paths["profile"],
        grouped_implementation_preflight_path=paths["grouped_preflight"],
    )

    assert report["status"]["ready_for_default_off_model_edit"] is False
    assert report["semantic_gates"]["prior_grouped_preflight_was_ready"] is False


def test_joined_xy_implementation_preflight_blocks_if_profile_invalid(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, blowup=True, profile_valid=False, grouped_ready=True)

    report = build_phase3b_joined_xy_implementation_preflight(
        tmp_path,
        sat_expansion_audit_path=paths["sat"],
        grouped_profile_audit_path=paths["profile"],
        grouped_implementation_preflight_path=paths["grouped_preflight"],
    )

    assert report["status"]["ready_for_default_off_model_edit"] is False
    assert any(
        check["check_id"] == "grouped_profile_valid" and check["status"] == "fail"
        for check in report["checks"]
    )


def test_joined_xy_implementation_preflight_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, blowup=True, profile_valid=True, grouped_ready=True)
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_joined_xy_implementation_preflight.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--sat-expansion-audit",
            str(paths["sat"]),
            "--grouped-profile-audit",
            str(paths["profile"]),
            "--grouped-implementation-preflight",
            str(paths["grouped_preflight"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "phase3b joined-xy implementation preflight" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--sat-expansion-audit",
            str(paths["sat"]),
            "--grouped-profile-audit",
            str(paths["profile"]),
            "--grouped-implementation-preflight",
            str(paths["grouped_preflight"]),
            "--output-dir",
            str(output_dir),
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "joined_xy_implementation_preflight_json=" in write.stdout
    payload = json.loads(
        (output_dir / "joined_xy_implementation_preflight.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_joined_xy_implementation_preflight_v1"
    assert (output_dir / "joined_xy_implementation_preflight.md").exists()
    assert (output_dir / "joined_xy_implementation_preflight.txt").exists()


def _write_inputs(
    tmp_path: Path,
    *,
    blowup: bool,
    profile_valid: bool,
    grouped_ready: bool,
) -> dict[str, Path]:
    paths = {
        "sat": tmp_path / "sat.json",
        "profile": tmp_path / "profile.json",
        "grouped_preflight": tmp_path / "grouped_preflight.json",
    }
    atomic_write_json(
        paths["sat"],
        {
            "metadata": {
                "source": "phase3b_grouped_xy_sat_expansion_audit_v1",
                "solver_invoked": False,
                "proof_source": False,
            },
            "status": {
                "outcome": (
                    "grouped_xy_sat_expansion_blowup_detected"
                    if blowup
                    else "grouped_xy_sat_expansion_no_blowup_detected"
                ),
                "evaluated": True,
            },
            "comparison": {
                "integer_encoding_blowup_detected": blowup,
                "grouped_to_active_integer_encoding_ratio": 193.0 if blowup else 1.0,
                "grouped_to_active_sat_boolean_ratio": 6.6 if blowup else 1.0,
                "anchor118_terminal_not_reproduced": True,
                "recommended_next_action": "inspect_grouped_xy_padded_index_integer_encoding",
            },
        },
    )
    atomic_write_json(
        paths["profile"],
        {
            "metadata": {
                "source": "phase3b_grouped_block_xy_profile_audit_v1",
                "solver_invoked": False,
                "proof_source": False,
            },
            "status": {
                "outcome": (
                    "grouped_block_xy_profile_audit_passed"
                    if profile_valid
                    else "grouped_block_xy_profile_audit_blocked"
                )
            },
            "comparison": {"grouped_xy_profile_valid": profile_valid},
            "cases": [
                _profile_case(
                    "selected_block_active_guard",
                    "selected_block_active_guard",
                    padded_idx=0,
                    block_x=4,
                    block_y=4,
                    grouped_x=0,
                    grouped_y=0,
                    block_element_constraints=8,
                    block_intermediate_targets=8,
                    selected_geometry=16,
                    grouped_selected_geometry=0,
                ),
                _profile_case(
                    "selected_block_active_guard_grouped_xy",
                    "selected_block_active_guard_grouped_xy",
                    padded_idx=2,
                    block_x=0,
                    block_y=0,
                    grouped_x=2,
                    grouped_y=2,
                    block_element_constraints=4,
                    block_intermediate_targets=4,
                    selected_geometry=0,
                    grouped_selected_geometry=8,
                ),
            ],
        },
    )
    atomic_write_json(
        paths["grouped_preflight"],
        {
            "metadata": {
                "source": "phase3b_grouped_block_xy_implementation_preflight_v1",
                "solver_invoked": False,
                "proof_source": False,
            },
            "status": {"ready_for_default_off_model_edit": grouped_ready},
        },
    )
    return paths


def _profile_case(
    case_id: str,
    block_geometry: str,
    *,
    padded_idx: int,
    block_x: int,
    block_y: int,
    grouped_x: int,
    grouped_y: int,
    block_element_constraints: int,
    block_intermediate_targets: int,
    selected_geometry: int,
    grouped_selected_geometry: int,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "block_geometry": block_geometry,
        "witness_stats": {
            "block_geometry_mode": block_geometry,
            "block_size": 64,
            "block_witness_count": 2,
            "block_element_constraint_count": block_element_constraints,
            "block_intermediate_target_channel_count": block_intermediate_targets,
            "block_selected_literal_count": 4,
            "local_selected_literal_count": 8,
            "block_active_guard_clause_count": 32,
            "block_selector_count": 2,
            "local_selector_count": 2,
            "block_selected_geometry_constraint_count": selected_geometry,
            "grouped_xy_selected_geometry_constraint_count": grouped_selected_geometry,
        },
        "variable_prefix_counts": {
            "cover_choice_block_x__": block_x,
            "cover_choice_block_y__": block_y,
            "cover_choice_grouped_x__": grouped_x,
            "cover_choice_grouped_y__": grouped_y,
            "cover_choice_padded_idx__": padded_idx,
            "cover_literal__": 0,
            "covers__": 0,
        },
    }
