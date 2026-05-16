import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.anchor_inventory.dynamic_coupling_audit as audit_module
from src.search.phase3b.anchor_inventory.dynamic_coupling_audit import (
    build_phase3b_anchor_dynamic_coupling_audit,
    render_phase3b_anchor_dynamic_coupling_audit_markdown,
    render_phase3b_anchor_dynamic_coupling_audit_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "candidates": {
            "67x13": {
                "ghost_rect": {"w": 67, "h": 13, "area": 871},
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_samples": [
                            {"anchor_idx": 118},
                            {"anchor_idx": 125},
                        ]
                    }
                },
            }
        }
    }


def _slot(
    key: str,
    *,
    template: str = "manufacturing_3x3",
    slot_kind: str = "mandatory",
    pose_idx: int = 0,
    position: tuple[int, int] = (0, 5),
) -> SimpleNamespace:
    return SimpleNamespace(
        key=key,
        template=template,
        slot_kind=slot_kind,
        slot_index=0,
        dims=(1, 1),
        tuple_to_pose_idx={(int(position[0]), int(position[1]), 0): int(pose_idx)},
    )


class _FakeDelegate:
    _power_coverage_witness_encoding = "block_element"
    _power_coverage_witness_block_geometry = "selected_block"
    _power_coverage_witness_block_size = 64
    _power_coverage_selected_interval_encoding = "delta"
    _power_family_lookup_encoding = "linear_shell_guards"

    def __init__(self) -> None:
        self._slots = [
            _slot("required_powered"),
            _slot(
                "residual_protocol",
                template="protocol_storage_box",
                slot_kind="residual_optional",
            ),
        ]
        self._template_pose_tuple_by_idx = {
            "power_pole": {
                0: (0, 5, 0),
                1: (9, 9, 0),
            }
        }
        self._power_pole_family_id_by_pose_idx = {0: 0, 1: 1}
        self._power_pole_family_name_by_int = {0: "family_near", 1: "family_far"}
        self._power_pole_family_coefficients = {
            "family_near": {"manufacturing_3x3": 1, "protocol_storage_box": 1},
            "family_far": {"manufacturing_3x3": 99, "protocol_storage_box": 1},
        }
        self._power_pole_family_pose_counts = {"family_near": 1, "family_far": 99}

    def _power_coverage_radius(self) -> int:
        return 1

    def _all_powered_slots(self):
        return list(self._slots)

    def _power_pole_family_count_upper_bound(self, family_name: str) -> int:
        return int(self._power_pole_family_pose_counts[str(family_name)])


class _FakeModel:
    grid_w = 20
    grid_h = 20

    def __init__(self) -> None:
        self._coordinate_delegate = _FakeDelegate()
        self._ghost_domains = [{"anchor": {"x": idx, "y": 0}, "cells": []} for idx in range(126)]
        self._ghost_domains[118]["conditioned_power_pole_family_upper_bounds"] = {
            "family_near": 0,
            "family_far": 99,
        }
        self._ghost_domains[125]["conditioned_power_pole_family_upper_bounds"] = {
            "family_near": 1,
            "family_far": 99,
        }
        self.build_stats = {
            "global_valid_inequalities": {
                "powered_template_demands": {
                    "manufacturing_3x3": 1,
                    "protocol_storage_box": 1,
                }
            }
        }

    def _pose_cells(self, template: str, pose_idx: int):
        return set()


def _patch_overlay(monkeypatch) -> None:
    fake_model = _FakeModel()
    monkeypatch.setattr(
        audit_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )


def test_coverer_family_cut_detects_deficit_after_static_support_passes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch)

    report = build_phase3b_anchor_dynamic_coupling_audit(
        project_root,
        candidate="67x13",
        anchor_indices=[118, 125],
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["profile"]["tuple_order"] == "x_y_mode"
    assert report["status"]["outcome"] == "anchor118_coverer_family_cut_deficit_control_pass"
    assert report["summary"]["deficit_anchor_indices"] == [118]
    anchor118 = report["anchors"][0]
    cut118 = anchor118["template_coverer_family_cuts"][0]
    assert cut118["deficit"] is True
    assert cut118["max_coverer_family_capacity"] == 0
    anchor125 = report["anchors"][1]
    assert anchor125["template_coverer_family_cuts"][0]["deficit"] is False
    protocol_cut = [
        cut
        for cut in anchor125["template_coverer_family_cuts"]
        if cut["template"] == "protocol_storage_box"
    ][0]
    assert protocol_cut["deficit"] is False
    assert protocol_cut["coverer_family_count"] == 1
    block_profile = anchor125["block64_witness_profile"]["by_template"]["manufacturing_3x3"]
    assert block_profile["union_block_count"] == 1
    assert block_profile["union_family_count"] == 1
    assert block_profile["top_blocks"][0]["block_index"] == "0"
    assert "Anchor Dynamic Coupling Audit" in render_phase3b_anchor_dynamic_coupling_audit_markdown(report)
    assert "outcome=anchor118_coverer_family_cut_deficit_control_pass" in render_phase3b_anchor_dynamic_coupling_audit_text(report)


def test_tuple_order_uses_x_y_mode_not_mode_x_y(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch)

    report = build_phase3b_anchor_dynamic_coupling_audit(
        project_root,
        candidate="67x13",
        anchor_indices=[125],
    )

    tightest = report["anchors"][0]["tightest_slots"][0]
    assert tightest["coverer_family_ids"] == ["family_near"]
    assert tightest["coverer_pole_pose_count"] == 1


def test_cli_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "anchor_inventory" / "build_dynamic_coupling_audit.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor dynamic coupling audit" in no_write.stdout
    assert not output_dir.exists()


def test_cli_default_mode_writes_json_md_txt(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "anchor_inventory" / "build_dynamic_coupling_audit.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor_dynamic_coupling_json=" in result.stdout
    payload = json.loads((output_dir / "anchor_dynamic_coupling_audit.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_anchor_dynamic_coupling_audit_v1"
    assert payload["metadata"]["solver_invoked"] is False
    assert (output_dir / "anchor_dynamic_coupling_audit.md").exists()
    assert (output_dir / "anchor_dynamic_coupling_audit.txt").exists()
