from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from ortools.sat.python import cp_model

import src.search.phase3b.family_bound.audit as audit_module
from src.search.phase3b.family_bound.audit import (
    build_phase3b_family_bound_audit,
    render_phase3b_family_bound_audit_markdown,
    render_phase3b_family_bound_audit_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "67x13": {
                "ghost_rect": {"w": 67, "h": 13, "area": 871},
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


class _FakeVar:
    def __init__(self, index: int) -> None:
        self._index = int(index)

    def Index(self) -> int:
        return int(self._index)


class _FakeDelegate:
    def __init__(self) -> None:
        self.residual_optional_slots = {"power_pole": [object(), object(), object()]}
        self._power_pole_family_id_by_pose_idx = {0: 0, 1: 0, 2: 1}
        self._power_pole_family_name_by_int = {0: "family_009", 1: "family_010"}
        self._power_pole_family_pose_counts = {"family_009": 2, "family_010": 1}
        self._power_pole_family_coefficients = {
            "family_009": {"protocol_storage_box": 1}
        }
        self.power_pole_family_count_vars = {"family_009": _FakeVar(0)}

    def _power_pole_family_count_upper_bound(self, family_name: str) -> int:
        return 2 if str(family_name) == "family_009" else 1


class _FakeModel:
    def __init__(self) -> None:
        cp = cp_model.CpModel()
        self._count = cp.NewIntVar(0, 2, "power_pole_family_count__family_009")
        self._ghost = cp.NewBoolVar("ghost__0_0_67_13")
        cp.Add(self._count <= 1 + 2 * (1 - self._ghost))
        self.model = cp
        self.u_vars = {0: self._ghost}
        self._coordinate_delegate = _FakeDelegate()
        self._coordinate_delegate.power_pole_family_count_vars = {
            "family_009": self._count
        }
        self._power_pole_family_count_vars = {"family_009": self._count}
        self._pose_cells_by_template_pose = {
            "power_pole": {
                0: {(0, 0)},
                1: {(2, 0)},
                2: {(4, 0)},
            }
        }
        self._ghost_domains = [
            {
                "anchor": {"x": 0, "y": 0},
                "cells": [[0, 0]],
                "conditioned_power_pole_family_upper_bounds": {"family_009": 1},
            }
        ]


def _patch_overlay(monkeypatch) -> None:
    monkeypatch.setattr(
        audit_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (_FakeModel(), object()),
    )


def test_family_bound_audit_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_family_bound_audit(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_family_bound_audit_cross_checks_derived_domain_and_proto_bounds(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch)

    report = build_phase3b_family_bound_audit(
        project_root,
        campaign_state_path=campaign_path,
        candidate="67x13",
        anchor_indices=[0],
        target_power_family="family_009",
    )

    assert report["metadata"]["source"] == "phase3b_family_bound_audit_v1"
    assert report["status"]["outcome"] == "family_bound_derivation_consistent"
    audit = report["audits"][0]
    derivation = audit["derivation"]
    proto = audit["proto_constraint"]
    assert derivation["family_size"] == 2
    assert derivation["blocked_family_pose_count"] == 1
    assert derivation["global_upper_bound"] == 2
    assert derivation["derived_conditioned_upper_bound"] == 1
    assert derivation["domain_conditioned_upper_bound"] == 1
    assert proto["implied_conditioned_upper_bound"] == 1
    assert audit["bounds_consistent"] is True
    assert _check_status(report, "family_bound_derivation_consistent") == "pass"

    markdown = render_phase3b_family_bound_audit_markdown(report)
    text = render_phase3b_family_bound_audit_text(report)
    assert "Family Bound Audit" in markdown
    assert "derived_ub=1" in text


def test_family_bound_audit_cli_writes_and_no_write_skips(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    output_dir = tmp_path / "out"
    _write_json(campaign_path, _campaign_state_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "family_bound" / "build_audit.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--candidate",
            "67x13",
            "--anchor-indices",
            "0",
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b family bound audit" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(campaign_path),
            "--candidate",
            "67x13",
            "--anchor-indices",
            "0",
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_bound_audit_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_bound_audit_67x13_family_009.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_family_bound_audit_v1"
    assert (output_dir / "family_bound_audit_67x13_family_009.md").exists()
    assert (output_dir / "family_bound_audit_67x13_family_009.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
