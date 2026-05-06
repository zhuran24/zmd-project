from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_joined_xy_probe_synthesis import (
    build_phase3b_joined_xy_probe_synthesis,
    render_phase3b_joined_xy_probe_synthesis_markdown,
    render_phase3b_joined_xy_probe_synthesis_text,
)


def test_joined_xy_probe_synthesis_rolls_up_targeted_anchor_set(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".artifacts/phase3b_joined_xy_profile_audit_20260423/joined_xy_profile_audit.json",
        _profile_audit(),
    )
    _write_json(
        tmp_path / ".artifacts/phase3b_joined_xy_sat_expansion_audit_20260423/joined_xy_sat_expansion_audit.json",
        _sat_expansion_audit(),
    )
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor118_60s_20260423", [118], "INFEASIBLE")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor118_60s_seed2_20260423", [118], "INFEASIBLE")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor119_120s_20260423", [119], "UNKNOWN")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor119_300s_20260423", [119], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor120_300s_20260423", [120], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor122_300s_20260423", [122], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor123_300s_20260423", [123], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor124_300s_20260423", [124], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor125_60s_20260423", [125], "UNKNOWN")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor125_300s_20260423", [125], "UNKNOWN", time_limit=300.0)
    _write_probe(
        tmp_path,
        "phase3b_joined_xy_probe_anchor120_124_60s_20260423",
        [120, 121, 122, 123, 124],
        "UNKNOWN",
    )

    report = build_phase3b_joined_xy_probe_synthesis(tmp_path)

    assert report["status"]["outcome"] == "joined_xy_targeted_anchor_set_completed"
    assert report["status"]["completed"] is True
    assert report["aggregate"]["terminal_anchor_indices"] == [118]
    assert report["aggregate"]["anchor120_124_all_search_progress"] is True
    assert report["aggregate"]["focus300_unknown_anchor_indices"] == [119, 120, 122, 123, 124, 125]
    assert report["aggregate"]["zero_branch_unknown_count"] == 0
    assert report["aggregate"]["campaign_states_unchanged"] is True
    assert all(check["status"] == "pass" for check in report["checks"])
    assert "anchor120_124_seed1" in render_phase3b_joined_xy_probe_synthesis_markdown(report)
    assert "proof_source=false" in render_phase3b_joined_xy_probe_synthesis_text(report)


def test_joined_xy_probe_synthesis_blocks_missing_targeted_probe(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".artifacts/phase3b_joined_xy_profile_audit_20260423/joined_xy_profile_audit.json",
        _profile_audit(),
    )
    _write_json(
        tmp_path / ".artifacts/phase3b_joined_xy_sat_expansion_audit_20260423/joined_xy_sat_expansion_audit.json",
        _sat_expansion_audit(),
    )
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor118_60s_20260423", [118], "INFEASIBLE")

    report = build_phase3b_joined_xy_probe_synthesis(tmp_path)

    assert report["status"]["outcome"] == "joined_xy_probe_synthesis_incomplete"
    assert report["status"]["completed"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "all_probe_inputs_present" in failed
    assert "anchor120_124_search_progress" in failed


def test_joined_xy_probe_synthesis_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / ".artifacts/phase3b_joined_xy_profile_audit_20260423/joined_xy_profile_audit.json",
        _profile_audit(),
    )
    _write_json(
        tmp_path / ".artifacts/phase3b_joined_xy_sat_expansion_audit_20260423/joined_xy_sat_expansion_audit.json",
        _sat_expansion_audit(),
    )
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor118_60s_20260423", [118], "INFEASIBLE")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor118_60s_seed2_20260423", [118], "INFEASIBLE")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor119_120s_20260423", [119], "UNKNOWN")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor119_300s_20260423", [119], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor120_300s_20260423", [120], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor122_300s_20260423", [122], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor123_300s_20260423", [123], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor124_300s_20260423", [124], "UNKNOWN", time_limit=300.0)
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor125_60s_20260423", [125], "UNKNOWN")
    _write_probe(tmp_path, "phase3b_joined_xy_probe_anchor125_300s_20260423", [125], "UNKNOWN", time_limit=300.0)
    _write_probe(
        tmp_path,
        "phase3b_joined_xy_probe_anchor120_124_60s_20260423",
        [120, 121, 122, 123, 124],
        "UNKNOWN",
    )
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_phase3b_joined_xy_probe_synthesis.py"
    output_dir = tmp_path / "out"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "joined_xy_targeted_anchor_set_completed" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "joined_xy_probe_synthesis_json=" in write.stdout
    assert (output_dir / "joined_xy_probe_synthesis.json").exists()
    assert (output_dir / "joined_xy_probe_synthesis.md").exists()
    assert (output_dir / "joined_xy_probe_synthesis.txt").exists()


def _write_probe(
    tmp_path: Path,
    artifact_dir: str,
    anchors: list[int],
    status: str,
    *,
    time_limit: float = 60.0,
) -> None:
    entries = []
    for anchor in anchors:
        branches = 2 if status == "INFEASIBLE" else 30000 + anchor
        conflicts = 1 if status == "INFEASIBLE" else 3000 + anchor
        entries.append(
            {
                "anchor_idx": anchor,
                "variant": "base",
                "status": status,
                "branches": branches,
                "conflicts": conflicts,
                "wall_time": time_limit,
                "deterministic_time": 10.0 if time_limit < 300.0 else 55.0,
            }
        )
    counts = {status: len(entries)}
    _write_json(
        tmp_path / f".artifacts/{artifact_dir}/forced_anchor_proto_reduction.json",
        {
            "status": {
                "outcome": (
                    "proto_reduction_terminal_found"
                    if status == "INFEASIBLE"
                    else "proto_reduction_search_progress_without_terminal"
                ),
                "status_counts": counts,
            },
            "profile": {
                "time_limit_seconds": time_limit,
                "selected_anchor_indices": anchors,
            },
            "proto_profile": {
                "variable_count": 134200,
                "constraint_count": 945686,
                "constraint_kind_counts": {"element": 19838, "bool_or": 585984},
                "cover_choice_profile": {
                    "prefix_counts": {
                        "cover_choice_joined_x": 763,
                        "cover_choice_joined_y": 763,
                    }
                },
            },
            "campaign_state_unchanged": True,
            "reduction": {
                "entries": entries,
                "status_counts": counts,
                "unknown_diagnostics": {
                    "zero_branch_unknown_count": 0,
                    "search_progress_unknown_count": 0 if status == "INFEASIBLE" else len(entries),
                },
            },
        },
    )


def _profile_audit() -> dict:
    return {
        "comparison": {
            "joined_xy_profile_valid": True,
            "padded_selector_removed": True,
            "no_pairwise_cover_literals": True,
            "selected_geometry_constraint_delta": -33572,
        }
    }


def _sat_expansion_audit() -> dict:
    return {
        "status": {"outcome": "joined_xy_sat_expansion_recovered_active_guard_scale"},
        "comparison": {
            "joined_xy_recovered_active_guard_scale": True,
            "joined_to_grouped_integer_encoding_ratio": 0.005,
            "joined_to_grouped_sat_boolean_ratio": 0.151,
            "joined_anchor119_conflicts_per_1k_branches": 151.0,
            "grouped_anchor119_conflicts_per_1k_branches": 0.37,
        },
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
