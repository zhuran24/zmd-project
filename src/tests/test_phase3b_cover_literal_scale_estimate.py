import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_cover_literal_scale_estimate as scale_module
from src.search.phase3b_cover_literal_scale_estimate import (
    build_phase3b_cover_literal_scale_estimate,
    render_phase3b_cover_literal_scale_estimate_markdown,
    render_phase3b_cover_literal_scale_estimate_text,
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
                        "failed_anchor_samples": [{"anchor_idx": 1}]
                    }
                },
            }
        }
    }


def _slot(
    key: str,
    *,
    template: str,
    slot_kind: str,
    dims: tuple[int, int] = (1, 1),
    pose_idx: int = 0,
    position: tuple[int, int] = (0, 0),
    active: object = object(),
) -> SimpleNamespace:
    return SimpleNamespace(
        key=key,
        template=template,
        slot_kind=slot_kind,
        dims=dims,
        active=active,
        tuple_to_pose_idx={(int(position[0]), int(position[1]), 0): int(pose_idx)},
    )


class _FakeDelegate:
    def __init__(self, powered_slots):
        self.residual_optional_slots = {
            "power_pole": [
                _slot("pole_near", template="power_pole", slot_kind="residual_optional", position=(0, 0)),
                _slot("pole_far", template="power_pole", slot_kind="residual_optional", pose_idx=1, position=(9, 9)),
            ]
        }
        self._powered_slots = list(powered_slots)

    def _power_coverage_radius(self) -> int:
        return 1

    def _all_powered_slots(self):
        return list(self._powered_slots)


class _FakeModel:
    grid_w = 10
    grid_h = 10

    def __init__(self, powered_slots):
        self._ghost_domains = [
            {"anchor": {"x": 0, "y": 0}, "cells": []},
            {"anchor": {"x": 1, "y": 0}, "cells": []},
        ]
        self._coordinate_delegate = _FakeDelegate(powered_slots)
        self.build_stats = {
            "power_coverage": {
                "encoding": "geometric_element_witness_v1",
                "element_constraints": 6,
                "witness_indices": 2,
            }
        }
        self._pose_cells_by_key = {
            ("power_pole", 0): {(0, 0)},
            ("power_pole", 1): {(9, 9)},
            ("manufacturing_3x3", 0): {(0, 0)},
            ("manufacturing_3x3", 2): {(9, 9)},
        }

    def _pose_cells(self, template: str, pose_idx: int):
        return set(self._pose_cells_by_key.get((str(template), int(pose_idx)), set()))


def _patch_overlay(monkeypatch, powered_slots) -> None:
    fake_model = _FakeModel(powered_slots)
    monkeypatch.setattr(
        scale_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )


def test_cover_literal_scale_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_cover_literal_scale_estimate(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_cover_literal_scale_estimates_pruned_pairs(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(
        monkeypatch,
        [
            _slot("powered_near", template="manufacturing_3x3", slot_kind="mandatory", position=(0, 0), active=None),
            _slot("powered_far", template="manufacturing_3x3", slot_kind="residual_optional", pose_idx=2, position=(9, 9)),
        ],
    )

    report = build_phase3b_cover_literal_scale_estimate(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    anchor = report["anchors"][0]
    assert report["status"]["evaluated"] is True
    assert anchor["naive_pair_count"] == 4
    assert anchor["static_pruned_pair_count"] == 2
    assert anchor["static_pair_reduction_ratio"] == 0.5
    assert anchor["current_element_constraints"] == 6
    assert anchor["literal_replacement_estimates"]["direct_pairwise"]["cover_literals"] == 2
    assert anchor["literal_replacement_estimates"]["selected_coord_channel"]["total_constraints_estimate"] == 17
    assert _check_status(report, "all_powered_slots_have_static_cover_candidate") == "pass"
    assert "Cover Literal Scale Estimate" in render_phase3b_cover_literal_scale_estimate_markdown(report)
    assert "static_pruned_pairs=2" in render_phase3b_cover_literal_scale_estimate_text(report)


def test_cover_literal_scale_reports_protocol_all_pairs_candidate(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(
        monkeypatch,
        [
            _slot(
                "protocol_full_support",
                template="protocol_storage_box",
                slot_kind="residual_optional",
                dims=(10, 10),
                position=(0, 0),
            ),
        ],
    )

    report = build_phase3b_cover_literal_scale_estimate(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    anchor = report["anchors"][0]
    protocol = anchor["protocol_geometry_redundancy_candidate"]
    assert protocol["present"] is True
    assert protocol["all_pairs_static_cover_valid"] is True
    assert protocol["all_pairs_position_universal_valid"] is True
    assert protocol["candidate_formulation"] == "protocol_xy_geometry_can_be_conditionally_redundant"
    assert anchor["pairs_by_powered_template"]["protocol_storage_box"]["all_pairs_static_cover_valid"] is True
    assert (
        anchor["pairs_by_powered_template"]["protocol_storage_box"][
            "all_pairs_position_universal_valid"
        ]
        is True
    )
    assert _check_status(report, "protocol_storage_box_all_pairs_static_cover_valid") == "pass"
    assert _check_status(report, "protocol_storage_box_all_pairs_position_universal_valid") == "pass"
    assert "protocol_all_pairs=True" in render_phase3b_cover_literal_scale_estimate_text(report)
    assert "protocol_position_universal=True" in render_phase3b_cover_literal_scale_estimate_text(report)


def test_cover_literal_scale_flags_missing_static_candidate(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(
        monkeypatch,
        [
            _slot("powered_outside", template="manufacturing_3x3", slot_kind="mandatory", position=(5, 5), active=None),
        ],
    )

    report = build_phase3b_cover_literal_scale_estimate(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    anchor = report["anchors"][0]
    assert anchor["powered_without_static_cover_candidate_count"] == 1
    assert _check_status(report, "all_powered_slots_have_static_cover_candidate") == "fail"
    assert any(
        "some powered slots have no static cover candidate" in reason
        for reason in anchor["risk"]["reasons"]
    )


def test_cover_literal_scale_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_cover_literal_scale_estimate.py"

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

    assert "phase3b cover-literal scale estimate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
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

    assert "cover_literal_scale_json=" in write.stdout
    payload = json.loads((output_dir / "cover_literal_scale_estimate.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_cover_literal_scale_estimate_v1"
    assert (output_dir / "cover_literal_scale_estimate.md").exists()
    assert (output_dir / "cover_literal_scale_estimate.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks", []):
        if check.get("check_id") == check_id:
            return check.get("status")
    raise AssertionError(f"check not found: {check_id}")
