from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from ortools.sat.python import cp_model

import src.search.phase3b_anchor_constraint_inventory as inventory_module
from src.search.phase3b_anchor_constraint_inventory import (
    build_phase3b_anchor_constraint_inventory,
    render_phase3b_anchor_constraint_inventory_markdown,
    render_phase3b_anchor_constraint_inventory_text,
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
                        "failed_anchor_samples": [{"anchor_idx": 56}],
                    }
                },
            }
        },
    }


def _patch_overlay(monkeypatch) -> None:
    model = cp_model.CpModel()
    u = model.NewBoolVar("u_56")
    other = model.NewBoolVar("other")
    x = model.NewIntVar(0, 10, "x")
    model.Add(x + 3 * u <= 7)
    model.AddExactlyOne([u, other])
    model.NewOptionalIntervalVar(0, 1, 1, u, "ghost_interval")
    fake_model = SimpleNamespace(
        u_vars={56: u},
        _ghost_domains=[
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            {
                "anchor": {"x": 1, "y": 4},
                "cells": [[1, 4], [2, 4]],
                "conditioned_power_pole_family_upper_bounds": {"family_001": 6},
            },
        ],
    )
    monkeypatch.setattr(
        inventory_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, model.Proto()),
    )


def test_anchor_constraint_inventory_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_anchor_constraint_inventory(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_anchor_constraint_inventory_scans_u_references(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch)

    report = build_phase3b_anchor_constraint_inventory(
        project_root,
        campaign_state_path=campaign_path,
        anchor_indices=[56],
    )

    anchor = report["anchors"][0]
    assert anchor["direct_u_reference_counts"] == {
        "exactly_one": 1,
        "interval": 1,
        "linear": 1,
    }
    assert anchor["domain_summary"]["conditioned_power_pole_family_upper_bound_count"] == 1

    markdown = render_phase3b_anchor_constraint_inventory_markdown(report)
    text = render_phase3b_anchor_constraint_inventory_text(report)
    assert "Anchor Constraint Inventory" in markdown
    assert "direct_refs=3" in text


def test_anchor_constraint_inventory_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    output_dir = tmp_path / "out"
    _write_json(campaign_path, _campaign_state_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_anchor_constraint_inventory.py"

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

    assert "phase3b anchor constraint inventory" in no_write.stdout
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

    assert "anchor_constraint_inventory_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor_constraint_inventory_69x19.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_anchor_constraint_inventory_v1"
    assert (output_dir / "anchor_constraint_inventory_69x19.md").exists()
    assert (output_dir / "anchor_constraint_inventory_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
