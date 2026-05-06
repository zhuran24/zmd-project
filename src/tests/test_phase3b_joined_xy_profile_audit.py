from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_joined_xy_profile_audit as audit_module
from src.search.phase3b_joined_xy_profile_audit import (
    build_phase3b_joined_xy_profile_audit,
    render_phase3b_joined_xy_profile_audit_markdown,
    render_phase3b_joined_xy_profile_audit_text,
)


class _FakeProto:
    def __init__(self, names: list[str]) -> None:
        self.variables = [SimpleNamespace(name=name) for name in names]


class _FakeModel:
    def __init__(self, geometry: str) -> None:
        joined = geometry == "selected_block_active_guard_joined_xy"
        self.build_stats = {
            "power_coverage": {
                "cover_literals": 0,
                "witness_encoding": {
                    "block_geometry_mode": geometry,
                    "final_target_channel_count": 0,
                    "block_final_join_element_constraint_count": 4 if joined else 0,
                    "block_intermediate_target_channel_count": 8,
                    "block_element_constraint_count": 12 if joined else 8,
                    "block_selected_geometry_constraint_count": 0 if joined else 16,
                    "joined_xy_target_channel_count": 4 if joined else 0,
                    "joined_xy_element_constraint_count": 4 if joined else 0,
                    "joined_xy_selected_geometry_constraint_count": 8 if joined else 0,
                    "block_active_guard_clause_count": 32,
                    "block_selected_literal_count": 4,
                    "local_selected_literal_count": 8,
                    "block_selector_count": 2,
                    "local_selector_count": 2,
                },
            }
        }


def test_joined_xy_profile_audit_detects_expected_shape(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_build_exact_overlay(project_root: Path, *, ghost_rect, master_search_profile):
        geometry = audit_module.os.environ[
            audit_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV
        ]
        joined = geometry == "selected_block_active_guard_joined_xy"
        names = [
            "cover_choice_block_x__slot__block::000",
            "cover_choice_block_y__slot__block::000",
            "cover_choice_joined_x__slot",
            "cover_choice_joined_y__slot",
        ] if joined else [
            "cover_choice_block_x__slot__block::000",
            "cover_choice_block_y__slot__block::000",
        ]
        return _FakeModel(geometry), _FakeProto(names)

    def fake_proto_profile(proto):
        return {"variable_count": len(proto.variables), "constraint_count": 10}

    monkeypatch.setattr(audit_module, "_build_exact_overlay", fake_build_exact_overlay)
    monkeypatch.setattr(audit_module, "_proto_profile", fake_proto_profile)

    report = build_phase3b_joined_xy_profile_audit(tmp_path)

    assert report["status"]["outcome"] == "joined_xy_profile_audit_passed"
    assert report["metadata"]["solver_invoked"] is False
    assert report["comparison"]["joined_xy_profile_valid"] is True
    assert report["comparison"]["padded_selector_removed"] is True
    assert report["comparison"]["per_block_xy_variables_retained"] is True
    assert report["comparison"]["block_element_constraint_delta"] == 4
    assert report["comparison"]["selected_geometry_constraint_delta"] == -8
    assert "Joined-XY Profile Audit" in render_phase3b_joined_xy_profile_audit_markdown(report)
    assert "joined_xy_profile_valid=True" in render_phase3b_joined_xy_profile_audit_text(report)


def test_joined_xy_profile_audit_cli_surface_mentions_outputs() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_joined_xy_profile_audit.py"
    text = script.read_text(encoding="utf-8")

    assert "joined_xy_profile_audit.json" in text
    assert "--no-write" in text
