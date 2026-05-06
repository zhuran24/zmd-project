from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _patch_review_bundle_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "bundle_ready_for_review": True,
        },
        "review_bundle": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "scope": "candidate=67x13, anchor_idx=119",
            "patch_review_targets": [
                {
                    "path": "src/search/phase3b_anchor119_guarded_precheck_runtime.py",
                    "exists": True,
                }
            ],
        },
    }


def _runtime_patch_proposal_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_proposal_v1",
        },
        "status": {
            "proposal_ready_for_review": True,
        },
        "proposal": {
            "scope": "candidate=67x13, anchor_idx=119",
        },
    }


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
            "authored_but_not_enableable": True,
        },
        "code_status": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
        },
    }


def _enablement_gate_prep_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_enablement_gate_prep_v1",
        },
        "status": {
            "reviewed_enablement_gate_ready_for_review": True,
        },
        "enablement_prep": {
            "production_acceptance_command": "python temp_scripts/benchmark_parallelism.py --suite-kind production-acceptance --suite-output .codex_test_logs/phase3b/production_acceptance_after_change.json",
        },
    }


def test_anchor119_row_domain_runtime_patch_signoff_bundle_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    patch_review_bundle_path = project_root / "bundle.json"
    runtime_patch_proposal_path = project_root / "proposal.json"
    runtime_patch_status_path = project_root / "status.json"
    enablement_gate_prep_path = project_root / "prep.json"
    _write_json(patch_review_bundle_path, _patch_review_bundle_json())
    _write_json(runtime_patch_proposal_path, _runtime_patch_proposal_json())
    _write_json(runtime_patch_status_path, _runtime_patch_status_json())
    _write_json(enablement_gate_prep_path, _enablement_gate_prep_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle(
        project_root,
        patch_review_bundle_path=patch_review_bundle_path,
        runtime_patch_proposal_path=runtime_patch_proposal_path,
        runtime_patch_status_path=runtime_patch_status_path,
        enablement_gate_prep_path=enablement_gate_prep_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1"
    )
    assert report["status"]["signoff_bundle_ready"] is True
    assert report["status"]["reviewed_runtime_patch_signoff_ready_for_review"] is True
    assert report["status"]["reviewed_runtime_patch_exists"] is False
    assert report["status"]["runtime_enablement_allowed"] is False
    bundle = report["signoff_bundle"]
    assert bundle["guard_id"] == "anchor119_mixed_lane_no_witness_guard_v0"
    assert bundle["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert "production-acceptance" in bundle["production_acceptance_command"]
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_markdown(
            report
        )
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_text(
        report
    )
    assert "Runtime Patch Signoff Bundle" in markdown
    assert "signoff_bundle_ready=True" in text


def test_anchor119_row_domain_runtime_patch_signoff_bundle_fails_if_status_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    patch_review_bundle_path = project_root / "bundle.json"
    runtime_patch_proposal_path = project_root / "proposal.json"
    enablement_gate_prep_path = project_root / "prep.json"
    _write_json(patch_review_bundle_path, _patch_review_bundle_json())
    _write_json(runtime_patch_proposal_path, _runtime_patch_proposal_json())
    _write_json(enablement_gate_prep_path, _enablement_gate_prep_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle(
        project_root,
        patch_review_bundle_path=patch_review_bundle_path,
        runtime_patch_proposal_path=runtime_patch_proposal_path,
        runtime_patch_status_path=project_root / "missing.json",
        enablement_gate_prep_path=enablement_gate_prep_path,
    )

    assert report["status"]["signoff_bundle_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "runtime_patch_status_present" in failed


def test_anchor119_row_domain_runtime_patch_signoff_bundle_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    patch_review_bundle_path = project_root / "bundle.json"
    runtime_patch_proposal_path = project_root / "proposal.json"
    runtime_patch_status_path = project_root / "status.json"
    enablement_gate_prep_path = project_root / "prep.json"
    output_dir = tmp_path / "out"
    _write_json(patch_review_bundle_path, _patch_review_bundle_json())
    _write_json(runtime_patch_proposal_path, _runtime_patch_proposal_json())
    _write_json(runtime_patch_status_path, _runtime_patch_status_json())
    _write_json(enablement_gate_prep_path, _enablement_gate_prep_json())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--patch-review-bundle",
            str(patch_review_bundle_path),
            "--runtime-patch-proposal",
            str(runtime_patch_proposal_path),
            "--runtime-patch-status",
            str(runtime_patch_status_path),
            "--enablement-gate-prep",
            str(enablement_gate_prep_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain runtime patch signoff bundle" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--patch-review-bundle",
            str(patch_review_bundle_path),
            "--runtime-patch-proposal",
            str(runtime_patch_proposal_path),
            "--runtime-patch-status",
            str(runtime_patch_status_path),
            "--enablement-gate-prep",
            str(enablement_gate_prep_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_runtime_patch_signoff_bundle_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_runtime_patch_signoff_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["signoff_bundle_ready"] is True
    assert (output_dir / "anchor119_row_domain_runtime_patch_signoff_bundle.md").exists()
    assert (output_dir / "anchor119_row_domain_runtime_patch_signoff_bundle.txt").exists()
