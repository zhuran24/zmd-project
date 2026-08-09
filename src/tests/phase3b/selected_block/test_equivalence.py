from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.selected_block.equivalence as audit_module
from src.search.phase3b.selected_block.equivalence import (
    build_active_guard_witness_relation_equivalence,
    build_phase3b_selected_block_equivalence_audit,
    build_selected_block_witness_relation_equivalence,
    render_phase3b_selected_block_equivalence_markdown,
    render_phase3b_selected_block_equivalence_text,
)


class _FakeSlot:
    def __init__(self, key: str, template: str, slot_kind: str = "residual_optional") -> None:
        self.key = key
        self.template = template
        self.slot_kind = slot_kind


class _FakeDelegate:
    def __init__(self) -> None:
        self.residual_optional_slots = {
            "power_pole": [
                _FakeSlot(f"pole_{idx}", "power_pole") for idx in range(5)
            ],
            "protocol_storage_box": [
                _FakeSlot("box_0", "protocol_storage_box"),
                _FakeSlot("box_1", "protocol_storage_box"),
            ],
        }

    def _all_powered_slots(self) -> list[_FakeSlot]:
        return list(self.residual_optional_slots["protocol_storage_box"])

    def _use_block_element_power_coverage_for_template(self, template: str) -> bool:
        return str(template) == "protocol_storage_box"


class _FakeProto:
    pass


class _FakeModel:
    def __init__(self, *, geometry: str) -> None:
        selected_block = geometry in {"selected_block", "selected_block_active_guard"}
        active_guard = geometry == "selected_block_active_guard"
        self._coordinate_delegate = _FakeDelegate()
        self.model = SimpleNamespace(Proto=lambda: _FakeProto())
        self.build_stats = {
            "power_coverage": {
                "witness_encoding": {
                    "block_geometry_mode": geometry,
                    "block_witness_count": 2,
                    "block_size": 4,
                    "final_target_channel_count": 0 if selected_block else 6,
                    "block_intermediate_target_channel_count": 4
                    if active_guard
                    else 6,
                    "local_selected_literal_count": 8 if active_guard else 0,
                    "block_selected_literal_count": 4 if selected_block else 0,
                    "padded_block_value_count": 6,
                }
            }
        }


def test_selected_block_relation_equivalence_handles_padding_and_multiblock() -> None:
    report = build_selected_block_witness_relation_equivalence(
        pole_slot_count=5,
        block_size=4,
    )

    assert report["equivalent"] is True
    assert report["block_count"] == 2
    assert report["relation_row_count"] == 8
    assert report["padded_block_value_count"] == 3
    assert report["block_selection_partition"]["status"] == "pass"
    assert report["inactive_powered_slot_guard_equivalent"] is True
    assert any(row["is_padding_duplicate"] for row in report["padding_relation_samples"])


def test_selected_block_relation_equivalence_handles_exact_block_boundary() -> None:
    report = build_selected_block_witness_relation_equivalence(
        pole_slot_count=8,
        block_size=4,
    )

    assert report["equivalent"] is True
    assert report["block_count"] == 2
    assert report["relation_row_count"] == 8
    assert report["padded_block_value_count"] == 0


def test_active_guard_relation_equivalence_handles_padding_and_inactive_guard() -> None:
    report = build_active_guard_witness_relation_equivalence(
        pole_slot_count=5,
        block_size=4,
    )

    assert report["equivalent"] is True
    assert report["block_count"] == 2
    assert report["relation_row_count"] == 8
    assert report["padded_block_value_count"] == 3
    assert report["inactive_powered_slot_guard_equivalent"] is True
    assert "powered_slot.active" in report["inactive_powered_slot_guard"]
    assert any(row["is_padding_duplicate"] for row in report["padding_relation_samples"])


def test_selected_block_equivalence_builder_is_no_solve_and_default_off(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_build_exact_overlay(project_root: Path, *, ghost_rect, master_search_profile):
        geometry = audit_module.os.environ[
            audit_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV
        ]
        return (
            _FakeModel(geometry=geometry),
            SimpleNamespace(),
        )

    def fake_proto_profile(proto):
        geometry = audit_module.os.environ[
            audit_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV
        ]
        selected_block = geometry in {"selected_block", "selected_block_active_guard"}
        active_guard = geometry == "selected_block_active_guard"
        return {
            "variable_count": 30 if active_guard else (22 if selected_block else 18),
            "constraint_kind_counts": {
                "element": 6 if active_guard else (9 if selected_block else 12),
                "bool_or": 8 if active_guard else 0,
            },
            "cover_choice_profile": {
                "target_channel_profile": {
                    "final_target_channel_variables": 0 if selected_block else 6,
                    "block_intermediate_target_channel_variables": 4
                    if active_guard
                    else 6,
                    "local_selected_literal_variables": 8 if active_guard else 0,
                    "block_selected_literal_variables": 4 if selected_block else 0,
                }
            },
        }

    monkeypatch.setattr(audit_module, "_build_exact_overlay", fake_build_exact_overlay)
    monkeypatch.setattr(audit_module, "_proto_profile", fake_proto_profile)

    report = build_phase3b_selected_block_equivalence_audit(
        tmp_path / "project",
        candidate="67x13",
        block_size=4,
        block_templates="",
    )

    assert report["metadata"]["source"] == "phase3b_selected_block_equivalence_v1"
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["status"]["outcome"] == "relations_equivalent"
    assert report["relation_equivalence"]["real_witness_relation"]["equivalent"] is True
    assert report["relation_equivalence"]["edge_cases_equivalent"] is True
    assert report["relation_equivalence"]["target_channel_delta"] == {
        "final_target_channel_delta": -6,
        "block_selected_literal_delta": 4,
        "final_target_channels_removed": True,
    }
    assert report["relation_equivalence"]["active_guard_relation"]["equivalent"] is True
    assert report["relation_equivalence"]["active_guard_channel_delta"] == {
        "block_intermediate_target_channel_delta": -2,
        "local_selected_literal_delta": 8,
        "element_delta": -3,
        "bool_or_delta": 8,
        "active_block_channels_removed": True,
    }
    assert _check_status(report, "solver_not_invoked") == "pass"
    assert _check_status(report, "real_witness_relation_equivalent") == "pass"
    assert _check_status(report, "active_guard_relation_equivalent") == "pass"
    assert _check_status(report, "active_block_channels_removed") == "pass"
    assert "Selected-Block Equivalence Audit" in (
        render_phase3b_selected_block_equivalence_markdown(report)
    )
    assert "solver_invoked=False" in render_phase3b_selected_block_equivalence_text(
        report
    )


def test_selected_block_equivalence_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "selected_block" / "build_equivalence.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b selected-block equivalence" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--output-dir",
            str(output_dir),
            "--block-size",
            "4",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "selected_block_equivalence_json=" in write.stdout
    payload = json.loads(
        (output_dir / "selected_block_equivalence.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_selected_block_equivalence_v1"
    assert payload["metadata"]["solver_invoked"] is False
    assert (output_dir / "selected_block_equivalence.md").exists()
    assert (output_dir / "selected_block_equivalence.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks", []):
        if check.get("check_id") == check_id:
            return check.get("status")
    raise AssertionError(f"check not found: {check_id}")
