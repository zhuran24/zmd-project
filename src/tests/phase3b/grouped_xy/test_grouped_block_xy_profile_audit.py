from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.grouped_xy.grouped_block_xy_profile_audit as audit_module
from src.search.phase3b.grouped_xy.grouped_block_xy_profile_audit import (
    build_phase3b_grouped_block_xy_profile_audit,
    render_phase3b_grouped_block_xy_profile_audit_markdown,
    render_phase3b_grouped_block_xy_profile_audit_text,
)


class _FakeProto:
    def __init__(self, names: list[str]) -> None:
        self.variables = [SimpleNamespace(name=name) for name in names]


class _FakeModel:
    def __init__(self, geometry: str) -> None:
        grouped = geometry == "selected_block_active_guard_grouped_xy"
        self.build_stats = {
            "power_coverage": {
                "witness_encoding": {
                    "block_geometry_mode": geometry,
                    "final_target_channel_count": 0,
                    "block_final_join_element_constraint_count": 0,
                    "block_intermediate_target_channel_count": 4 if grouped else 8,
                    "block_element_constraint_count": 4 if grouped else 8,
                    "block_selected_geometry_constraint_count": 0 if grouped else 16,
                    "grouped_xy_target_channel_count": 4 if grouped else 0,
                    "grouped_xy_element_constraint_count": 4 if grouped else 0,
                    "block_active_guard_clause_count": 32,
                    "block_selected_literal_count": 4,
                    "local_selected_literal_count": 8,
                }
            }
        }


def test_grouped_block_xy_profile_audit_detects_target_reduction(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_build_exact_overlay(project_root: Path, *, ghost_rect, master_search_profile):
        geometry = audit_module.os.environ[
            audit_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV
        ]
        grouped = geometry == "selected_block_active_guard_grouped_xy"
        names = [
            "cover_choice_grouped_x__slot",
            "cover_choice_grouped_y__slot",
            "cover_choice_padded_idx__slot",
        ] if grouped else [
            "cover_choice_block_x__slot__block::000",
            "cover_choice_block_y__slot__block::000",
        ]
        return _FakeModel(geometry), _FakeProto(names)

    def fake_proto_profile(proto):
        return {"variable_count": len(proto.variables), "constraint_count": 10}

    monkeypatch.setattr(audit_module, "_build_exact_overlay", fake_build_exact_overlay)
    monkeypatch.setattr(audit_module, "_proto_profile", fake_proto_profile)

    report = build_phase3b_grouped_block_xy_profile_audit(tmp_path)

    assert report["status"]["outcome"] == "grouped_block_xy_profile_audit_passed"
    assert report["metadata"]["solver_invoked"] is False
    assert report["comparison"]["block_xy_target_delta"] == -4
    assert report["comparison"]["block_element_constraint_delta"] == -4
    assert report["comparison"]["per_block_xy_variables_removed"] is True
    assert report["comparison"]["target_delta_negative"] is True
    assert report["comparison"]["element_delta_negative"] is True
    assert report["comparison"]["no_pairwise_cover_literals"] is True
    assert "Grouped Block X/Y Profile Audit" in render_phase3b_grouped_block_xy_profile_audit_markdown(report)
    assert "grouped_xy_profile_valid=True" in render_phase3b_grouped_block_xy_profile_audit_text(report)


def test_grouped_block_xy_profile_audit_cli_surface_mentions_outputs() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "grouped_xy" / "build_grouped_block_xy_profile_audit.py"
    text = script.read_text(encoding="utf-8")

    assert "grouped_block_xy_profile_audit.json" in text
    assert "--no-write" in text
