from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_anchor_domain_inventory as domain_module
from src.search.phase3b_anchor_domain_inventory import (
    build_phase3b_anchor_domain_inventory,
    render_phase3b_anchor_domain_inventory_markdown,
    render_phase3b_anchor_domain_inventory_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "69x19": {
                "ghost_rect": {"w": 69, "h": 19, "area": 1311},
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 1,
                        "failed_anchor_samples": [{"anchor_idx": 0}],
                    }
                },
            }
        },
    }


class _FakeModel:
    def __init__(self) -> None:
        self._ghost_domains = [
            {
                "anchor": {"x": 1, "y": 1},
                "cells": [[0, 0]],
                "conditioned_power_pole_family_upper_bounds": {"family_001": 2},
            }
        ]
        self._mandatory_groups = [
            {
                "group_id": "group_a",
                "facility_type": "tpl",
                "count": 2,
                "instance_ids": ["a", "b"],
            }
        ]
        self._exact_required_pose_optional_counts = {"opt": 1}
        self.facility_pools = {
            "tpl": [{}, {}, {}],
            "opt": [{}, {}],
            "power_pole": [{}, {}],
        }
        self._coordinate_delegate = SimpleNamespace(
            mandatory_slots={"group_a": [object(), object()]},
            _mandatory_group_mode_rect_domains={"group_a": {0: object()}},
            _mandatory_group_bucket_pose_counts={"group_a": {"sig_0": 3}},
            residual_optional_slots={"power_pole": [object()]},
        )

    def _candidate_pose_indices_for_group(self, group: dict) -> list[int]:
        return [0, 1, 2]

    def _pose_cells(self, tpl: str, pose_idx: int) -> set[tuple[int, int]]:
        cells = {
            "tpl": {
                0: {(0, 0)},
                1: {(1, 0)},
                2: {(2, 0)},
            },
            "opt": {
                0: {(0, 0)},
                1: {(3, 0)},
            },
            "power_pole": {
                0: {(0, 0)},
                1: {(4, 0)},
            },
        }
        return set(cells[str(tpl)][int(pose_idx)])


def _patch_overlay(monkeypatch) -> None:
    monkeypatch.setattr(
        domain_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (_FakeModel(), object()),
    )


def test_anchor_domain_inventory_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_anchor_domain_inventory(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_anchor_domain_inventory_summarizes_survivors(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch)

    report = build_phase3b_anchor_domain_inventory(
        project_root,
        campaign_state_path=campaign_path,
        anchor_indices=[0],
    )

    anchor = report["anchors"][0]
    assert anchor["summary"]["mandatory_surviving_total"] == 2
    assert anchor["summary"]["optional_surviving_total"] == 2
    assert anchor["tightest_mandatory_group"]["surviving_count"] == 2
    assert anchor["power_pole_family_bounds"]["count"] == 1

    markdown = render_phase3b_anchor_domain_inventory_markdown(report)
    text = render_phase3b_anchor_domain_inventory_text(report)
    assert "Anchor Domain Inventory" in markdown
    assert "mandatory_surviving_total=2" in text


def test_anchor_domain_inventory_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    output_dir = tmp_path / "out"
    _write_json(campaign_path, _campaign_state_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_anchor_domain_inventory.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor domain inventory" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor_domain_inventory_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor_domain_inventory_69x19.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_anchor_domain_inventory_v1"
    assert (output_dir / "anchor_domain_inventory_69x19.md").exists()
    assert (output_dir / "anchor_domain_inventory_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
