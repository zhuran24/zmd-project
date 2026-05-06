from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_power_coverage_anchor_delta import (
    build_phase3b_power_coverage_anchor_delta,
    render_phase3b_power_coverage_anchor_delta_markdown,
    render_phase3b_power_coverage_anchor_delta_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _inventory_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_anchor_domain_inventory_v1"},
        "candidate": {"key": "67x13"},
        "anchors": [
            {
                "anchor_idx": 118,
                "summary": {
                    "mandatory_surviving_total": 1000,
                    "optional_surviving_total": 200,
                },
                "tightest_mandatory_group": {"group_id": "group_a"},
                "mandatory_groups": [
                    {
                        "group_id": "group_a",
                        "facility_type": "manufacturing_3x3",
                        "required_count": 10,
                        "surviving_count": 100,
                    },
                    {
                        "group_id": "group_b",
                        "facility_type": "manufacturing_5x5",
                        "required_count": 5,
                        "surviving_count": 50,
                    },
                ],
                "optional_templates": [
                    {
                        "template": "power_pole",
                        "residual_slot_count": 20,
                        "surviving_count": 40,
                    },
                    {
                        "template": "protocol_storage_box",
                        "residual_slot_count": 20,
                        "surviving_count": 160,
                    },
                ],
                "power_pole_family_bounds": {
                    "bounds": {"family_000": 10, "family_001": 20}
                },
            },
            {
                "anchor_idx": 119,
                "summary": {
                    "mandatory_surviving_total": 900,
                    "optional_surviving_total": 180,
                },
                "tightest_mandatory_group": {"group_id": "group_a"},
                "mandatory_groups": [
                    {
                        "group_id": "group_a",
                        "facility_type": "manufacturing_3x3",
                        "required_count": 10,
                        "surviving_count": 80,
                    },
                    {
                        "group_id": "group_b",
                        "facility_type": "manufacturing_5x5",
                        "required_count": 5,
                        "surviving_count": 55,
                    },
                ],
                "optional_templates": [
                    {
                        "template": "power_pole",
                        "residual_slot_count": 20,
                        "surviving_count": 40,
                    },
                    {
                        "template": "protocol_storage_box",
                        "residual_slot_count": 20,
                        "surviving_count": 140,
                    },
                ],
                "power_pole_family_bounds": {
                    "bounds": {"family_000": 12, "family_001": 15}
                },
            },
        ],
    }


def test_power_coverage_anchor_delta_compares_family_bounds(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    inventory_path = project_root / "inventory.json"
    _write_json(inventory_path, _inventory_payload())

    report = build_phase3b_power_coverage_anchor_delta(
        project_root,
        anchor_domain_inventory_path=inventory_path,
    )

    assert report["metadata"]["source"] == "phase3b_power_coverage_anchor_delta_v1"
    assert report["candidate"]["key"] == "67x13"
    assert report["delta"]["mandatory_surviving_delta"] == -100
    assert report["delta"]["optional_surviving_delta"] == -20
    assert report["delta"]["power_family_changed_count"] == 2
    assert report["delta"]["power_family_positive_delta_sum"] == 2
    assert report["delta"]["power_family_negative_delta_sum"] == -5
    assert report["delta"]["top_power_family_deltas"][0]["family"] == "family_001"
    assert report["delta"]["top_mandatory_group_deltas"][0]["group_id"] == "group_a"
    assert report["delta"]["top_mandatory_group_deltas"][0]["surviving_delta"] == -20
    optional_by_template = {
        entry["template"]: entry for entry in report["delta"]["optional_template_deltas"]
    }
    assert optional_by_template["power_pole"]["surviving_delta"] == 0
    assert optional_by_template["protocol_storage_box"]["surviving_delta"] == -20
    assert "power_family_bounds_shift" in report["delta"]["diagnostic_findings"]
    assert (
        "power_pole_candidate_domain_stable_despite_family_bound_shift"
        in report["delta"]["diagnostic_findings"]
    )
    assert "protocol_storage_box_domain_tightens" in report["delta"]["diagnostic_findings"]

    markdown = render_phase3b_power_coverage_anchor_delta_markdown(report)
    text = render_phase3b_power_coverage_anchor_delta_text(report)
    assert "Power-Coverage Anchor Delta" in markdown
    assert "Top Mandatory Group Deltas" in markdown
    assert "power_family_changed_count=2" in text
    assert "diagnostic_finding=power_family_bounds_shift" in text


def test_power_coverage_anchor_delta_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    inventory_path = project_root / "inventory.json"
    output_dir = tmp_path / "out"
    _write_json(inventory_path, _inventory_payload())
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_power_coverage_anchor_delta.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--anchor-domain-inventory",
            str(inventory_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b power-coverage anchor delta" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--anchor-domain-inventory",
            str(inventory_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "power_coverage_anchor_delta_json=" in write.stdout
    payload = json.loads(
        (output_dir / "power_coverage_anchor_delta.json").read_text(encoding="utf-8")
    )
    assert payload["delta"]["power_family_changed_count"] == 2
    assert payload["delta"]["top_mandatory_group_deltas"][0]["surviving_delta"] == -20
    assert (output_dir / "power_coverage_anchor_delta.md").exists()
    assert (output_dir / "power_coverage_anchor_delta.txt").exists()
