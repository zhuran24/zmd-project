from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle import (
    build_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _guard_spec_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_guard_spec_v1",
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
        },
        "candidate": {"key": "67x13", "anchor_idx": 119},
        "proposed_guard": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "scope": "candidate=67x13",
            "default_state": "disabled",
            "advisory_only": True,
            "patch_review_targets": [
                "src/search/phase3b_anchor119_guarded_precheck_spec.py",
                "src/search/phase3b_anchor119_guarded_precheck_runtime.py",
            ],
            "non_goals": ["No runtime semantics change."],
        },
        "status": {
            "outcome": "anchor119_row_domain_guard_spec_ready_for_review",
            "all_gates_pass": True,
        },
        "evidence": {
            "non_trigger_max_slot_count": 13,
            "anchored_trigger_min_slot_count": 14,
            "free_ghost_trigger_min_slot_count": 15,
            "advisory_would_trigger": True,
            "advisory_triggered": False,
        },
    }


def test_anchor119_row_domain_guard_patch_review_bundle_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "src/search").mkdir(parents=True, exist_ok=True)
    (project_root / "src/search/phase3b_anchor119_guarded_precheck_spec.py").write_text(
        "# spec\n", encoding="utf-8"
    )
    (project_root / "src/search/phase3b_anchor119_guarded_precheck_runtime.py").write_text(
        "# runtime\n", encoding="utf-8"
    )
    spec_path = project_root / "guard.json"
    _write_json(spec_path, _guard_spec_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle(
        project_root,
        guard_spec_path=spec_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_v1"
    )
    assert report["status"]["bundle_ready_for_review"] is True
    assert report["status"]["runtime_patch_ready"] is False
    assert report["status"]["recommended_next_step"] == "author_default_off_guard_patch"
    assert report["review_bundle"]["guard_id"] == "anchor119_mixed_lane_no_witness_guard_v0"
    assert report["evidence"]["non_trigger_max_slot_count"] == 13
    markdown = render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle_text(
        report
    )
    assert "Patch Review Bundle" in markdown
    assert "bundle_ready_for_review=True" in text


def test_anchor119_row_domain_guard_patch_review_bundle_fails_if_target_missing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    (project_root / "src/search").mkdir(parents=True, exist_ok=True)
    (project_root / "src/search/phase3b_anchor119_guarded_precheck_spec.py").write_text(
        "# spec\n", encoding="utf-8"
    )
    spec_path = project_root / "guard.json"
    _write_json(spec_path, _guard_spec_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle(
        project_root,
        guard_spec_path=spec_path,
    )

    assert report["status"]["bundle_ready_for_review"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "patch_review_targets_exist" in failed


def test_anchor119_row_domain_guard_patch_review_bundle_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    (project_root / "src/search").mkdir(parents=True, exist_ok=True)
    (project_root / "src/search/phase3b_anchor119_guarded_precheck_spec.py").write_text(
        "# spec\n", encoding="utf-8"
    )
    (project_root / "src/search/phase3b_anchor119_guarded_precheck_runtime.py").write_text(
        "# runtime\n", encoding="utf-8"
    )
    spec_path = project_root / "guard.json"
    output_dir = tmp_path / "out"
    _write_json(spec_path, _guard_spec_json())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_guard_patch_review_bundle.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--guard-spec",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain guard patch review bundle" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--guard-spec",
            str(spec_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_guard_patch_review_bundle_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_guard_patch_review_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["bundle_ready_for_review"] is True
    assert (output_dir / "anchor119_row_domain_guard_patch_review_bundle.md").exists()
    assert (output_dir / "anchor119_row_domain_guard_patch_review_bundle.txt").exists()
