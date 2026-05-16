from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.enablement_gate_prep import (
    build_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep,
    render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _runtime_patch_status_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "patch_status_ready": True,
            "runtime_patch_authored_in_code": True,
            "runtime_patch_authoring_allowed": True,
            "runtime_enablement_allowed": False,
            "authored_but_not_enableable": True,
            "current_phase": "disabled_runtime_patch_authored",
        },
        "code_status": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
        },
    }


def test_anchor119_row_domain_enablement_gate_prep_ready(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    runtime_patch_status_path = tmp_path / "runtime_patch_status.json"
    _write_json(runtime_patch_status_path, _runtime_patch_status_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep(
        repo_root,
        runtime_patch_status_path=runtime_patch_status_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_v1"
    )
    assert report["status"]["prep_ready"] is True
    assert report["status"]["reviewed_enablement_gate_ready_for_review"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    assert (
        report["status"]["recommended_next_step"]
        == "review_runtime_patch_then_refresh_production_acceptance"
    )
    prep = report["enablement_prep"]
    assert prep["production_profile_id"] == "prod_4x4_normal"
    assert prep["production_profile_locked"] is True
    assert "production-acceptance" in prep["production_acceptance_command"]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_markdown(
            report
        )
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_text(
        report
    )
    assert "Enablement Gate Prep" in markdown
    assert "prep_ready=True" in text


def test_anchor119_row_domain_enablement_gate_prep_fails_if_status_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    report = build_phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep(
        repo_root,
        runtime_patch_status_path=tmp_path / "missing.json",
    )

    assert report["status"]["prep_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "runtime_patch_status_present" in failed


def test_anchor119_row_domain_enablement_gate_prep_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[5]
    runtime_patch_status_path = tmp_path / "runtime_patch_status.json"
    output_dir = tmp_path / "out"
    _write_json(runtime_patch_status_path, _runtime_patch_status_json())
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_enablement_gate_prep.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--runtime-patch-status",
            str(runtime_patch_status_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain enablement gate prep" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--runtime-patch-status",
            str(runtime_patch_status_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_enablement_gate_prep_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_enablement_gate_prep.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["prep_ready"] is True
    assert (output_dir / "anchor119_row_domain_enablement_gate_prep.md").exists()
    assert (output_dir / "anchor119_row_domain_enablement_gate_prep.txt").exists()
