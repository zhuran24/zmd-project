import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_power_coverage_witness_domain as domain_module
from src.search.phase3b_power_coverage_witness_domain import (
    _slot_witness_entry,
    build_phase3b_power_coverage_witness_domain,
    render_phase3b_power_coverage_witness_domain_markdown,
    render_phase3b_power_coverage_witness_domain_text,
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
) -> SimpleNamespace:
    return SimpleNamespace(
        key=key,
        template=template,
        slot_kind=slot_kind,
        dims=dims,
        tuple_to_pose_idx={(int(position[0]), int(position[1]), 0): int(pose_idx)},
    )


class _FakeDelegate:
    def __init__(self, slots):
        self.residual_optional_slots = {"power_pole": [_slot("pole_slot", template="power_pole", slot_kind="residual_optional")]}
        self._template_pose_tuple_by_idx = {"power_pole": {0: (0, 0, 0)}}
        self._slots = list(slots)

    def _power_coverage_radius(self) -> int:
        return 1

    def _all_powered_slots(self):
        return list(self._slots)


class _FakeModel:
    grid_w = 10
    grid_h = 10

    def __init__(self, slots):
        self._ghost_domains = [
            {"anchor": {"x": 0, "y": 0}, "cells": []},
            {"anchor": {"x": 1, "y": 0}, "cells": []},
        ]
        self._coordinate_delegate = _FakeDelegate(slots)
        self._pose_cells_by_key = {
            ("power_pole", 0): {(0, 0)},
            ("manufacturing_3x3", 0): {(0, 0)},
            ("manufacturing_3x3", 1): {(9, 9)},
            ("manufacturing_3x3", 3): {(0, 5)},
            ("protocol_storage_box", 2): {(9, 9)},
        }

    def _pose_cells(self, template: str, pose_idx: int):
        return set(self._pose_cells_by_key.get((str(template), int(pose_idx)), set()))


def _patch_overlay(monkeypatch, slots) -> None:
    fake_model = _FakeModel(slots)
    monkeypatch.setattr(
        domain_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )


def test_witness_domain_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_power_coverage_witness_domain(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_witness_domain_static_support_pass(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(
        monkeypatch,
        [_slot("powered", template="manufacturing_3x3", slot_kind="mandatory")],
    )

    report = build_phase3b_power_coverage_witness_domain(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    assert report["status"]["outcome"] == "witness_domain_static_support_pass"
    assert report["profile"]["tuple_order"] == "x_y_mode"
    assert report["summary"]["required_unsupported_slot_count"] == 0
    assert report["anchors"][0]["powered_slot_summary"]["min_witnessable_position_count"] == 1
    assert "static power-pole witness" in report["recommendation"]
    assert "Witness-Domain Probe" in render_phase3b_power_coverage_witness_domain_markdown(report)
    assert "required_unsupported_slot_count=0" in render_phase3b_power_coverage_witness_domain_text(report)


def test_witness_domain_uses_x_y_mode_tuple_order() -> None:
    model = _FakeModel([])
    slot = _slot(
        "non_symmetric_powered",
        template="manufacturing_3x3",
        slot_kind="mandatory",
        pose_idx=3,
        position=(0, 5),
    )

    entry = _slot_witness_entry(
        model,
        slot,
        blocked_cells=set(),
        pole_positions={(0, 5)},
        radius=1,
        cover_cache={},
    )

    assert entry["static_supported"] is True
    assert entry["witnessable_position_count"] == 1


def test_witness_domain_required_slot_without_support_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(
        monkeypatch,
        [
            _slot(
                "far_powered",
                template="manufacturing_3x3",
                slot_kind="mandatory",
                pose_idx=1,
                position=(9, 9),
            )
        ],
    )

    report = build_phase3b_power_coverage_witness_domain(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    assert report["status"]["outcome"] == "witness_domain_static_support_missing"
    assert report["summary"]["required_unsupported_slot_count"] == 1
    assert report["anchors"][0]["unsupported_required_slots"][0]["slot_key"] == "far_powered"
    assert _check_status(report, "required_slots_have_static_witness_support") == "fail"


def test_witness_domain_optional_gaps_are_separate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(
        monkeypatch,
        [
            _slot(
                "far_optional",
                template="protocol_storage_box",
                slot_kind="residual_optional",
                pose_idx=2,
                position=(9, 9),
            )
        ],
    )

    report = build_phase3b_power_coverage_witness_domain(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    assert report["status"]["outcome"] == "residual_optional_witness_domain_gaps_only"
    assert report["summary"]["required_unsupported_slot_count"] == 0
    assert report["summary"]["optional_unsupported_slot_count"] == 1


def test_witness_domain_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_power_coverage_witness_domain.py"

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

    assert "phase3b power-coverage witness-domain probe" in no_write.stdout
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

    assert "witness_domain_json=" in write.stdout
    payload = json.loads((output_dir / "witness_domain.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_power_coverage_witness_domain_v1"
    assert (output_dir / "witness_domain.md").exists()
    assert (output_dir / "witness_domain.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks", []):
        if check.get("check_id") == check_id:
            return check.get("status")
    raise AssertionError(f"check not found: {check_id}")
