import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_family_lookup_assignment_audit as audit_module
from src.search.phase3b_family_lookup_assignment_audit import (
    build_phase3b_family_lookup_assignment_audit,
    render_phase3b_family_lookup_assignment_audit_markdown,
    render_phase3b_family_lookup_assignment_audit_text,
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


class _FakeDelegate:
    def __init__(self, *, include_second_shell_row: bool = True) -> None:
        self._power_pole_use_shell_lookup = True
        self._power_pole_family_name_by_int = {0: "family_000", 1: "family_001"}
        self._power_pole_family_id_by_pose_idx = {0: 0, 1: 1}
        self._power_pole_family_pose_counts = {"family_000": 1, "family_001": 1}
        self._template_pose_tuple_by_idx = {
            "power_pole": {
                0: (0, 0, 0),
                1: (1, 0, 0),
            }
        }
        self._template_full_mode_rect_domains = {
            "power_pole": {
                0: SimpleNamespace(x_min=0, x_max=2, y_min=0, y_max=2)
            }
        }
        self._power_pole_shell_lookup_rows = [(0, 0, 0)]
        if include_second_shell_row:
            self._power_pole_shell_lookup_rows.append((0, 1, 1))
        self._power_pole_family_tuple_rows = []
        self.residual_optional_slots = {
            "power_pole": [SimpleNamespace(), SimpleNamespace()]
        }

    def _power_pole_shell_distance(self, domain, x_val: int, y_val: int):
        dx = min(int(x_val - domain.x_min), int(domain.x_max - x_val))
        dy = min(int(y_val - domain.y_min), int(domain.y_max - y_val))
        return int(dx), int(dy)


class _FakeModel:
    def __init__(self, *, include_second_shell_row: bool = True) -> None:
        self._coordinate_delegate = _FakeDelegate(
            include_second_shell_row=include_second_shell_row
        )
        self._ghost_domains = [
            {"anchor": {"x": 0, "y": 0}, "cells": []},
            {"anchor": {"x": 1, "y": 0}, "cells": []},
        ]
        self._pose_cells_by_key = {
            ("power_pole", 0): {(0, 0)},
            ("power_pole", 1): {(1, 0)},
        }

    def _pose_cells(self, template: str, pose_idx: int):
        return set(self._pose_cells_by_key.get((str(template), int(pose_idx)), set()))


def _fake_proto() -> SimpleNamespace:
    return SimpleNamespace(
        variables=[
            SimpleNamespace(name="family__residual_optional::power_pole::slot::0", domain=[0, 2]),
            SimpleNamespace(name="family__residual_optional::power_pole::slot::1", domain=[0, 2]),
            SimpleNamespace(name="other", domain=[0, 1]),
        ],
        constraints=[],
    )


def _patch_overlay(monkeypatch, *, include_second_shell_row: bool = True) -> None:
    fake_model = _FakeModel(include_second_shell_row=include_second_shell_row)
    fake_proto = _fake_proto()
    monkeypatch.setattr(
        audit_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, fake_proto),
    )


def test_family_lookup_assignment_audit_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_family_lookup_assignment_audit(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_family_lookup_assignment_audit_reports_consistent_shell_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch, include_second_shell_row=True)

    report = build_phase3b_family_lookup_assignment_audit(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    assert report["status"]["outcome"] == "shell_lookup_survivor_rows_consistent"
    assert report["family_lookup_encoding"]["family_variable_count"] == 2
    assert report["anchors"][0]["missing_lookup_row_count"] == 0
    assert _check_status(report, "surviving_shell_rows_present") == "pass"
    assert "Family Lookup Assignment Audit" in render_phase3b_family_lookup_assignment_audit_markdown(report)
    assert "outcome=shell_lookup_survivor_rows_consistent" in render_phase3b_family_lookup_assignment_audit_text(report)


def test_family_lookup_assignment_audit_reports_missing_shell_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_overlay(monkeypatch, include_second_shell_row=False)

    report = build_phase3b_family_lookup_assignment_audit(
        project_root,
        candidate="67x13",
        anchor_indices=[1],
    )

    assert report["status"]["outcome"] == "shell_lookup_missing_survivor_rows"
    assert report["anchors"][0]["missing_lookup_row_count"] == 1
    assert report["anchors"][0]["missing_lookup_rows"][0]["family_name"] == "family_001"
    assert _check_status(report, "surviving_shell_rows_present") == "fail"


def test_family_lookup_assignment_audit_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_family_lookup_assignment_audit.py"

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

    assert "phase3b family lookup assignment audit" in no_write.stdout
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

    assert "family_lookup_assignment_audit_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_lookup_assignment_audit.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_family_lookup_assignment_audit_v1"
    assert (output_dir / "family_lookup_assignment_audit.md").exists()
    assert (output_dir / "family_lookup_assignment_audit.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks", []):
        if check.get("check_id") == check_id:
            return check.get("status")
    raise AssertionError(f"check not found: {check_id}")
