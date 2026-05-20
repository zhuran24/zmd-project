from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_group.precheck_candidate import (
    build_phase3b_coordinate_group_precheck_candidate,
    render_phase3b_coordinate_group_precheck_candidate_markdown,
    render_phase3b_coordinate_group_precheck_candidate_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _group_delta_payload(status: str = "INFEASIBLE") -> dict:
    return {
        "metadata": {"source": "phase3b_coordinate_validation_group_delta_v1"},
        "candidate": {
            "key": "67x13",
            "anchor_idx": 159,
            "ghost_rect": {"w": 67, "h": 13, "area": 871},
        },
        "delta": {
            "entries": [
                {
                    "case_id": (
                        "ghost_plus_each_group:"
                        "group::manufacturing_5x5::planter_buckwheat::9"
                    ),
                    "variant": "ghost_plus_each_group",
                    "include_ghost": True,
                    "included_group_ids": [
                        "group::manufacturing_5x5::planter_buckwheat::9"
                    ],
                    "validation": {
                        "status": status,
                        "reason": status.lower(),
                        "forced_slot_field_count": 33,
                        "wall_time": 1.5,
                        "branches": 0,
                        "conflicts": 0,
                    },
                }
            ]
        },
    }


def _field_delta_payload(target_status: str = "INFEASIBLE") -> dict:
    group_id = "group::manufacturing_5x5::planter_buckwheat::9"
    entries = [
        {
            "case_id": f"{group_id}:x",
            "group_id": group_id,
            "field_variant": "x",
            "include_ghost": True,
            "validation": {
                "status": "UNKNOWN",
                "reason": "unknown",
                "forced_slot_field_count": 11,
                "wall_time": 10.0,
                "branches": 0,
                "conflicts": 0,
            },
        },
        {
            "case_id": f"{group_id}:y",
            "group_id": group_id,
            "field_variant": "y",
            "include_ghost": True,
            "validation": {
                "status": "UNKNOWN",
                "reason": "unknown",
                "forced_slot_field_count": 11,
                "wall_time": 10.0,
                "branches": 0,
                "conflicts": 0,
            },
        },
        {
            "case_id": f"{group_id}:mode",
            "group_id": group_id,
            "field_variant": "mode",
            "include_ghost": True,
            "validation": {
                "status": "UNKNOWN",
                "reason": "unknown",
                "forced_slot_field_count": 11,
                "wall_time": 10.0,
                "branches": 0,
                "conflicts": 0,
            },
        },
        {
            "case_id": f"{group_id}:x_y",
            "group_id": group_id,
            "field_variant": "x_y",
            "include_ghost": True,
            "validation": {
                "status": target_status,
                "reason": target_status.lower(),
                "forced_slot_field_count": 22,
                "wall_time": 2.0,
                "branches": 0,
                "conflicts": 0,
            },
        },
    ]
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_field_channel_delta_v1"
        },
        "candidate": {"key": "67x13", "anchor_idx": 159},
        "field_channel_delta": {"entries": entries},
    }


def test_coordinate_group_precheck_candidate_passes_design_but_blocks_runtime(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    group_path = project_root / "group.json"
    field_path = project_root / "field.json"
    _write_json(group_path, _group_delta_payload())
    _write_json(field_path, _field_delta_payload())

    summary = build_phase3b_coordinate_group_precheck_candidate(
        project_root,
        group_delta_path=group_path,
        field_channel_delta_path=field_path,
    )

    assert summary["metadata"]["source"] == "phase3b_coordinate_group_precheck_candidate_v1"
    assert summary["candidate"]["key"] == "67x13"
    assert summary["candidate"]["anchor_idx"] == 159
    assert summary["target"]["group_entry"]["status"] == "INFEASIBLE"
    assert summary["target"]["field_entry"]["status"] == "INFEASIBLE"
    assert summary["gate"]["design_gate_passed"] is True
    assert summary["gate"]["runtime_promotion_ready"] is False
    assert [
        check["check_id"]
        for check in summary["checks"]
        if check["status"] == "fail"
    ] == ["runtime_promotion_guard"]

    markdown = render_phase3b_coordinate_group_precheck_candidate_markdown(summary)
    text = render_phase3b_coordinate_group_precheck_candidate_text(summary)
    assert "Coordinate Group Precheck Candidate" in markdown
    assert "design_gate_passed=True" in text
    assert "runtime_promotion_ready=False" in text


def test_coordinate_group_precheck_candidate_fails_without_ghost_field_delta(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    group_path = project_root / "group.json"
    field_path = project_root / "field.json"
    field_payload = _field_delta_payload()
    field_payload["field_channel_delta"]["entries"][-1]["include_ghost"] = False
    _write_json(group_path, _group_delta_payload())
    _write_json(field_path, field_payload)

    summary = build_phase3b_coordinate_group_precheck_candidate(
        project_root,
        group_delta_path=group_path,
        field_channel_delta_path=field_path,
    )

    assert summary["gate"]["design_gate_passed"] is False
    failed = {check["check_id"] for check in summary["checks"] if check["status"] == "fail"}
    assert "target_field_uses_ghost" in failed


def test_coordinate_group_precheck_candidate_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    group_path = project_root / "group.json"
    field_path = project_root / "field.json"
    output_dir = tmp_path / "out"
    _write_json(group_path, _group_delta_payload())
    _write_json(field_path, _field_delta_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "coordinate_group" / "build_precheck_candidate.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--group-delta",
            str(group_path),
            "--field-channel-delta",
            str(field_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate group precheck candidate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--group-delta",
            str(group_path),
            "--field-channel-delta",
            str(field_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "coordinate_group_precheck_candidate_json=" in write.stdout
    payload = json.loads(
        (output_dir / "coordinate_group_precheck_candidate.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["gate"]["design_gate_passed"] is True
    assert (output_dir / "coordinate_group_precheck_candidate.md").exists()
    assert (output_dir / "coordinate_group_precheck_candidate.txt").exists()
