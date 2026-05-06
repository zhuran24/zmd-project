from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate import (
    build_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate,
    render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _payload_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_row_domain_count_witness_payload_v1"
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "payload_ready": True,
            "anchored_bridge_ready": False,
            "runtime_promotion_ready": False,
            "recommended_next_step": "extract_anchor119_row_domain_bridge",
        },
        "deterministic_payload": {
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "shared_safe_strip_lower_bound": 16,
            "total_row_count": 640,
            "rows": [
                {"group_id": "group::manufacturing_5x5::planter_buckwheat::9", "slot_index": 8},
                {"group_id": "group::manufacturing_5x5::planter_buckwheat::9", "slot_index": 10},
                {"group_id": "group::protocol_core::protocol_core::18", "slot_index": 0},
            ],
        },
        "count_boundaries": {
            "non_trigger_max_slot_count": 13,
            "anchored_trigger_min_slot_count": 14,
            "free_ghost_trigger_min_slot_count": 15,
        },
    }


def _spec_json() -> dict:
    return {
        "metadata": {"source": "phase3b_anchor119_guarded_precheck_spec_v1"},
        "candidate": {"key": "67x13", "anchor_idx": 119},
        "proposed_guard": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "default_state": "disabled",
        },
        "status": {
            "outcome": "guarded_precheck_spec_ready_for_review",
            "all_gates_pass": True,
        },
    }


def _advisory_json(*, would_trigger: bool = True, triggered: bool = False) -> dict:
    return {
        "metadata": {"source": "phase3b_anchor119_guarded_precheck_runtime_v1"},
        "would_trigger": would_trigger,
        "triggered": triggered,
        "reason": "advisory_guard_would_reject_anchor119",
        "proof_summary": {
            "master_candidate_precheck": {
                "first_infeasible_anchor_idx": 119,
                "supported": True,
            },
            "anchor119_mixed_lane_guarded_precheck": {
                "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
                "runtime_precheck_enabled": False,
                "advisory_only": True,
            },
        },
    }


def test_anchor119_row_domain_bridge_candidate_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    payload_path = project_root / "payload.json"
    spec_path = project_root / "spec.json"
    advisory_path = project_root / "advisory.json"
    _write_json(payload_path, _payload_json())
    _write_json(spec_path, _spec_json())
    _write_json(advisory_path, _advisory_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate(
        project_root,
        row_domain_count_witness_payload_path=payload_path,
        guarded_precheck_spec_path=spec_path,
        guarded_precheck_advisory_enabled_path=advisory_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_v1"
    )
    assert report["status"]["bridge_ready_for_review"] is True
    assert report["status"]["non_trigger_controls_ready"] is True
    assert report["status"]["runtime_promotion_ready"] is False
    assert report["status"]["recommended_next_step"] == (
        "draft_default_off_anchor119_row_domain_guard_spec"
    )
    assert report["bridge"]["payload_id"] == (
        "anchor119_three_label_overlap_above_strip_count_guard_v0"
    )
    assert report["non_trigger_controls"]["non_trigger_max_slot_count"] == 13
    assert report["non_trigger_controls"]["anchored_trigger_min_slot_count"] == 14
    markdown = render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_markdown(
        report
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_text(
        report
    )
    assert "Anchor119 Row-Domain Bridge Candidate" in markdown
    assert "bridge_ready_for_review=True" in text


def test_anchor119_row_domain_bridge_candidate_fails_if_advisory_not_would_trigger(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    payload_path = project_root / "payload.json"
    spec_path = project_root / "spec.json"
    advisory_path = project_root / "advisory.json"
    _write_json(payload_path, _payload_json())
    _write_json(spec_path, _spec_json())
    _write_json(advisory_path, _advisory_json(would_trigger=False))

    report = build_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate(
        project_root,
        row_domain_count_witness_payload_path=payload_path,
        guarded_precheck_spec_path=spec_path,
        guarded_precheck_advisory_enabled_path=advisory_path,
    )

    assert report["status"]["bridge_ready_for_review"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "advisory_would_trigger_anchor119" in failed


def test_anchor119_row_domain_bridge_candidate_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    payload_path = project_root / "payload.json"
    spec_path = project_root / "spec.json"
    advisory_path = project_root / "advisory.json"
    output_dir = tmp_path / "out"
    _write_json(payload_path, _payload_json())
    _write_json(spec_path, _spec_json())
    _write_json(advisory_path, _advisory_json())
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--row-domain-count-witness-payload",
            str(payload_path),
            "--guarded-precheck-spec",
            str(spec_path),
            "--guarded-precheck-advisory-enabled",
            str(advisory_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b coordinate-validation anchor119 row-domain bridge candidate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--row-domain-count-witness-payload",
            str(payload_path),
            "--guarded-precheck-spec",
            str(spec_path),
            "--guarded-precheck-advisory-enabled",
            str(advisory_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_bridge_candidate_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_bridge_candidate.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["bridge_ready_for_review"] is True
    assert (output_dir / "anchor119_row_domain_bridge_candidate.md").exists()
    assert (output_dir / "anchor119_row_domain_bridge_candidate.txt").exists()
