from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.coordinate_validation.anchor119_row_domain.guard_spec import (
    build_phase3b_coordinate_validation_anchor119_row_domain_guard_spec,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_spec_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_guard_spec_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _bridge_candidate_json(*, default_state: str = "disabled") -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_v1"
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
        },
        "status": {
            "bridge_ready_for_review": True,
            "non_trigger_controls_ready": True,
            "runtime_promotion_ready": False,
            "recommended_next_step": "draft_default_off_anchor119_row_domain_guard_spec",
            "recommendation": "ready",
        },
        "bridge": {
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "advisory_reason": "advisory_guard_would_reject_anchor119",
            "advisory_would_trigger": True,
            "advisory_triggered": False,
            "first_infeasible_anchor_idx": 119,
            "shared_safe_strip_lower_bound": 16,
            "total_row_count": 640,
        },
        "non_trigger_controls": {
            "default_state": default_state,
            "advisory_only": True,
            "candidate_key_required": "67x13",
            "anchor_idx_required": 119,
            "non_trigger_max_slot_count": 13,
            "anchored_trigger_min_slot_count": 14,
            "free_ghost_trigger_min_slot_count": 15,
            "same_three_label_payload_required": True,
            "runtime_short_circuit_disabled": True,
        },
    }


def test_anchor119_row_domain_guard_spec_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    bridge_path = project_root / "bridge.json"
    _write_json(bridge_path, _bridge_candidate_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_spec(
        project_root,
        bridge_candidate_path=bridge_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_guard_spec_v1"
    )
    assert report["metadata"]["spec_only"] is True
    assert report["metadata"]["default_off"] is True
    assert report["status"]["outcome"] == "anchor119_row_domain_guard_spec_ready_for_review"
    assert report["status"]["all_gates_pass"] is True
    assert report["status"]["runtime_precheck_enabled"] is False
    assert report["status"]["runtime_promotion_ready"] is False
    assert report["status"]["recommended_next_step"] == (
        "prepare_anchor119_row_domain_guard_patch_review"
    )
    assert report["proposed_guard"]["default_state"] == "disabled"
    assert report["proposed_guard"]["advisory_only"] is True
    assert report["evidence"]["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    markdown = render_phase3b_coordinate_validation_anchor119_row_domain_guard_spec_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_guard_spec_text(
        report
    )
    assert "Spec only: true" in markdown
    assert "default_off=true" in text


def test_anchor119_row_domain_guard_spec_fails_if_not_default_off(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    bridge_path = project_root / "bridge.json"
    _write_json(bridge_path, _bridge_candidate_json(default_state="enabled"))

    report = build_phase3b_coordinate_validation_anchor119_row_domain_guard_spec(
        project_root,
        bridge_candidate_path=bridge_path,
    )

    assert report["status"]["all_gates_pass"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "default_off_state_retained" in failed


def test_anchor119_row_domain_guard_spec_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    bridge_path = project_root / "bridge.json"
    output_dir = tmp_path / "out"
    _write_json(bridge_path, _bridge_candidate_json())
    repo_root = Path(__file__).resolve().parents[5]
    script = (
        repo_root
        / "scripts" / "phase3b" / "coordinate_validation" / "anchor119_row_domain" / "build_guard_spec.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--bridge-candidate",
            str(bridge_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain guard spec" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--bridge-candidate",
            str(bridge_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_guard_spec_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_guard_spec.json").read_text(encoding="utf-8")
    )
    assert payload["status"]["all_gates_pass"] is True
    assert (output_dir / "anchor119_row_domain_guard_spec.md").exists()
    assert (output_dir / "anchor119_row_domain_guard_spec.txt").exists()
