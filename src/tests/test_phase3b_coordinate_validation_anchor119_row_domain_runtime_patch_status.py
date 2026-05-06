from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status import (
    build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _control_surface_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "control_surface_ready": True,
            "runtime_activation_allowed": False,
        },
    }


def _runtime_patch_proposal_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "proposal_ready_for_review": True,
            "runtime_patch_authoring_allowed": True,
            "runtime_enablement_allowed": False,
            "recommended_next_step": "keep_disabled_and_require_reviewed_runtime_patch",
        },
    }


def test_anchor119_row_domain_runtime_patch_status_ready(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    control_surface_path = tmp_path / "control.json"
    runtime_patch_proposal_path = tmp_path / "proposal.json"
    _write_json(control_surface_path, _control_surface_json())
    _write_json(runtime_patch_proposal_path, _runtime_patch_proposal_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status(
        repo_root,
        control_surface_path=control_surface_path,
        runtime_patch_proposal_path=runtime_patch_proposal_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_v1"
    )
    assert report["status"]["patch_status_ready"] is True
    assert report["status"]["runtime_patch_authored_in_code"] is True
    assert report["status"]["runtime_patch_authoring_allowed"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["authored_but_not_enableable"] is True
    request_shape = report["code_status"]["reserved_runtime_request_shape"]
    assert request_shape["requested_state"] == "runtime_enabled_reserved"
    assert request_shape["effective_state"] == "advisory_enabled"
    assert request_shape["runtime_requested"] is True
    assert request_shape["runtime_precheck_enabled"] is False
    assert request_shape["runtime_activation_allowed"] is False
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_markdown(
            report
        )
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status_text(
        report
    )
    assert "Runtime Patch Status" in markdown
    assert "runtime_patch_authored_in_code=True" in text


def test_anchor119_row_domain_runtime_patch_status_fails_if_proposal_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    control_surface_path = tmp_path / "control.json"
    _write_json(control_surface_path, _control_surface_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status(
        repo_root,
        control_surface_path=control_surface_path,
        runtime_patch_proposal_path=tmp_path / "missing.json",
    )

    assert report["status"]["patch_status_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "runtime_patch_proposal_present" in failed


def test_anchor119_row_domain_runtime_patch_status_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    control_surface_path = tmp_path / "control.json"
    runtime_patch_proposal_path = tmp_path / "proposal.json"
    output_dir = tmp_path / "out"
    _write_json(control_surface_path, _control_surface_json())
    _write_json(runtime_patch_proposal_path, _runtime_patch_proposal_json())
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_status.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--control-surface",
            str(control_surface_path),
            "--runtime-patch-proposal",
            str(runtime_patch_proposal_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain runtime patch status" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--control-surface",
            str(control_surface_path),
            "--runtime-patch-proposal",
            str(runtime_patch_proposal_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_runtime_patch_status_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_runtime_patch_status.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["patch_status_ready"] is True
    assert (output_dir / "anchor119_row_domain_runtime_patch_status.md").exists()
    assert (output_dir / "anchor119_row_domain_runtime_patch_status.txt").exists()
