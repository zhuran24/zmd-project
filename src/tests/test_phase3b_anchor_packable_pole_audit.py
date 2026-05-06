import json
import subprocess
import sys
from pathlib import Path

import src.search.phase3b_anchor_packable_pole_audit as audit_module
from src.search.phase3b_anchor_packable_pole_audit import (
    _weighted_interval_upper_bound,
    build_phase3b_anchor_packable_pole_audit,
    render_phase3b_anchor_packable_pole_audit_markdown,
    render_phase3b_anchor_packable_pole_audit_text,
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


class _FakeDelegate:
    def __init__(self) -> None:
        self._template_pose_tuple_by_idx = {
            "power_pole": {
                0: (0, 0, 0),
                1: (2, 0, 0),
            }
        }
        self._power_pole_family_id_by_pose_idx = {0: 0, 1: 0}
        self._power_pole_family_name_by_int = {0: "family_near"}
        self._power_pole_family_coefficients = {
            "family_near": {"manufacturing_3x3": 1}
        }
        self._power_pole_family_pose_counts = {"family_near": 2}

    def _power_pole_family_count_upper_bound(self, family_name: str) -> int:
        return int(self._power_pole_family_pose_counts[str(family_name)])


class _FakeModel:
    def __init__(self) -> None:
        self._coordinate_delegate = _FakeDelegate()
        self._ghost_domains = [{"anchor": {"x": idx, "y": 0}, "cells": []} for idx in range(126)]
        self._ghost_domains[118]["conditioned_power_pole_family_upper_bounds"] = {
            "family_near": 1,
        }
        self._ghost_domains[125]["conditioned_power_pole_family_upper_bounds"] = {
            "family_near": 2,
        }
        self.build_stats = {
            "global_valid_inequalities": {
                "powered_template_demands": {"manufacturing_3x3": 2}
            }
        }

    def _pose_cells(self, template: str, pose_idx: int):
        cells = {
            ("power_pole", 0): {(0, 0)},
            ("power_pole", 1): {(2, 0)},
        }
        return set(cells.get((str(template), int(pose_idx)), set()))


def _patch_overlay(monkeypatch) -> None:
    fake_model = _FakeModel()
    monkeypatch.setattr(
        audit_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )


def test_weighted_interval_upper_bound_handles_inclusive_overlap() -> None:
    intervals = [(0, 1, 5), (1, 2, 5), (3, 3, 4)]

    assert _weighted_interval_upper_bound(intervals) == 9


def test_packable_pole_bound_detects_anchor118_control_deficit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch)

    report = build_phase3b_anchor_packable_pole_audit(
        project_root,
        candidate="67x13",
        anchor_indices=[118, 125],
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["status"]["outcome"] == "anchor118_packable_bound_control_pass"
    assert report["summary"]["deficit_anchor_indices"] == [118]
    anchor118 = report["anchors"][0]
    assert anchor118["packable_pole_upper_bounds"][0]["binding_method"] == "family_cap"
    assert anchor118["packable_pole_upper_bounds"][0]["upper_bound"] == 1
    anchor125 = report["anchors"][1]
    assert anchor125["packable_pole_upper_bounds"][0]["deficit"] is False
    assert "Anchor Packable-Pole Audit" in render_phase3b_anchor_packable_pole_audit_markdown(report)
    assert "outcome=anchor118_packable_bound_control_pass" in render_phase3b_anchor_packable_pole_audit_text(report)


def test_cli_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_anchor_packable_pole_audit.py"

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

    assert "phase3b anchor packable-pole audit" in no_write.stdout
    assert not output_dir.exists()


def test_cli_default_mode_writes_json_md_txt(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_anchor_packable_pole_audit.py"

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

    assert "anchor_packable_pole_json=" in result.stdout
    payload = json.loads((output_dir / "anchor_packable_pole_audit.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_anchor_packable_pole_audit_v1"
    assert payload["metadata"]["solver_invoked"] is False
    assert (output_dir / "anchor_packable_pole_audit.md").exists()
    assert (output_dir / "anchor_packable_pole_audit.txt").exists()
