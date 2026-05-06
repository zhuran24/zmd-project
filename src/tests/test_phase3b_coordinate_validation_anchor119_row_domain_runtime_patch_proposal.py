from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal import (
    build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_text,
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
        "control_surface": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
        },
        "activation_gates": [
            {"gate_id": "reviewed_runtime_patch_exists", "satisfied": False, "blocking": True}
        ],
    }


def _patch_review_bundle_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1",
        },
        "status": {
            "bundle_ready_for_review": True,
        },
        "review_bundle": {
            "scope": "candidate=67x13, anchor_idx=119",
            "patch_review_targets": [
                {
                    "path": "src/search/phase3b_anchor119_guarded_precheck_spec.py",
                    "exists": True,
                }
            ],
        },
    }


def test_anchor119_row_domain_runtime_patch_proposal_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    control_surface_path = project_root / "control.json"
    patch_review_bundle_path = project_root / "bundle.json"
    _write_json(control_surface_path, _control_surface_json())
    _write_json(patch_review_bundle_path, _patch_review_bundle_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal(
        project_root,
        control_surface_path=control_surface_path,
        patch_review_bundle_path=patch_review_bundle_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_v1"
    )
    assert report["status"]["proposal_ready_for_review"] is True
    assert report["status"]["runtime_patch_authoring_allowed"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["proposal"]["proposal_id"] == "anchor119_row_domain_runtime_patch_proposal_v0"
    markdown = render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_text(
        report
    )
    assert "Runtime Patch Proposal" in markdown
    assert "runtime_enablement_allowed=False" in text


def test_anchor119_row_domain_runtime_patch_proposal_fails_if_control_surface_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    patch_review_bundle_path = project_root / "bundle.json"
    _write_json(patch_review_bundle_path, _patch_review_bundle_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal(
        project_root,
        control_surface_path=project_root / "missing.json",
        patch_review_bundle_path=patch_review_bundle_path,
    )

    assert report["status"]["proposal_ready_for_review"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "control_surface_present" in failed


def test_anchor119_row_domain_runtime_patch_proposal_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    control_surface_path = project_root / "control.json"
    patch_review_bundle_path = project_root / "bundle.json"
    output_dir = tmp_path / "out"
    _write_json(control_surface_path, _control_surface_json())
    _write_json(patch_review_bundle_path, _patch_review_bundle_json())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--control-surface",
            str(control_surface_path),
            "--patch-review-bundle",
            str(patch_review_bundle_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain runtime patch proposal" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--control-surface",
            str(control_surface_path),
            "--patch-review-bundle",
            str(patch_review_bundle_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_runtime_patch_proposal_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_runtime_patch_proposal.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["proposal_ready_for_review"] is True
    assert (output_dir / "anchor119_row_domain_runtime_patch_proposal.md").exists()
    assert (output_dir / "anchor119_row_domain_runtime_patch_proposal.txt").exists()
