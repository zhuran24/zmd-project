from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.guard_control_surface import (
    build_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _patch_review_bundle_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1",
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
        },
        "candidate": {"key": "67x13", "anchor_idx": 119},
        "status": {
            "bundle_ready_for_review": True,
            "runtime_patch_ready": False,
            "recommended_next_step": "author_default_off_guard_patch",
        },
        "review_bundle": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "patch_review_targets": [
                {
                    "path": "src/search/phase3b/anchor119/guarded_precheck_spec.py",
                    "exists": True,
                },
                {
                    "path": "src/search/phase3b/anchor119/guarded_precheck_runtime.py",
                    "exists": True,
                },
            ],
        },
        "evidence": {
            "non_trigger_max_slot_count": 13,
            "anchored_trigger_min_slot_count": 14,
            "free_ghost_trigger_min_slot_count": 15,
            "advisory_would_trigger": True,
            "advisory_triggered": False,
        },
    }


def test_anchor119_row_domain_guard_control_surface_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    bundle_path = project_root / "bundle.json"
    _write_json(bundle_path, _patch_review_bundle_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface(
        project_root,
        patch_review_bundle_path=bundle_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_v1"
    )
    assert report["status"]["control_surface_ready"] is True
    assert report["status"]["current_mode"] == "default_off_advisory_only"
    assert report["status"]["runtime_activation_allowed"] is False
    assert report["control_surface"]["advisory_env"]["name"] == (
        "EXACT_PRE_MASTER_ANCHOR119_MIXED_LANE_GUARD_ADVISORY"
    )
    assert report["control_surface"]["locked_boundaries"]["non_trigger_max_slot_count"] == 13
    markdown = render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface_text(
        report
    )
    assert "Control Surface" in markdown
    assert "runtime_activation_allowed=False" in text


def test_anchor119_row_domain_guard_control_surface_fails_if_bundle_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    missing_bundle = project_root / "missing.json"

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_control_surface(
        project_root,
        patch_review_bundle_path=missing_bundle,
    )

    assert report["status"]["control_surface_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "patch_review_bundle_present" in failed


def test_anchor119_row_domain_guard_control_surface_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    bundle_path = project_root / "bundle.json"
    output_dir = tmp_path / "out"
    _write_json(bundle_path, _patch_review_bundle_json())
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_guard_control_surface.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--patch-review-bundle",
            str(bundle_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain guard control surface" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--patch-review-bundle",
            str(bundle_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_guard_control_surface_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_guard_control_surface.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["control_surface_ready"] is True
    assert (output_dir / "anchor119_row_domain_guard_control_surface.md").exists()
    assert (output_dir / "anchor119_row_domain_guard_control_surface.txt").exists()
