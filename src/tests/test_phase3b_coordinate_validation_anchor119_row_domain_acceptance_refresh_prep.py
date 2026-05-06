from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep import (
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _signoff_bundle_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_runtime_patch_signoff_bundle_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "signoff_bundle_ready": True,
        },
        "signoff_bundle": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_acceptance_command": "python temp_scripts/benchmark_parallelism.py --suite-kind production-acceptance --suite-output .codex_test_logs/phase3b/production_acceptance_after_change.json",
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
            "production_profile_id": "prod_4x4_normal",
            "production_profile_locked": True,
            "default_production_runner": "scripts/run_prod_4x4_normal.ps1",
            "production_acceptance_command": "python temp_scripts/benchmark_parallelism.py --suite-kind production-acceptance --suite-output .codex_test_logs/phase3b/production_acceptance_after_change.json",
        },
    }


def _review_state_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_review_state_v1",
            "spec_only": True,
            "default_off": True,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "solver_invoked": False,
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "review_state_ready": True,
            "repo_side_review_state_updated": True,
            "reviewed_runtime_patch_exists": True,
            "runtime_enablement_allowed": False,
            "production_acceptance_refresh_completed": False,
        },
    }


def test_anchor119_row_domain_acceptance_refresh_prep_ready(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    signoff_bundle_path = tmp_path / "signoff.json"
    enablement_gate_prep_path = tmp_path / "prep.json"
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(enablement_gate_prep_path, _enablement_gate_prep_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep(
        repo_root,
        signoff_bundle_path=signoff_bundle_path,
        enablement_gate_prep_path=enablement_gate_prep_path,
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_v1"
    )
    assert report["status"]["acceptance_refresh_prep_ready"] is True
    assert report["status"]["acceptance_refresh_ready_for_review"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    prep = report["acceptance_refresh_prep"]
    assert prep["production_profile_id"] == "prod_4x4_normal"
    assert prep["suite_output_path"] == ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    validity = prep["validity_criteria"]
    assert validity["label"] == "prod_4x4"
    assert validity["campaign_valid_after_run"] is True
    assert validity["duplicated_work"] is False
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_markdown(
            report
        )
    )
    text = render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep_text(
        report
    )
    assert "Acceptance Refresh Prep" in markdown
    assert "acceptance_refresh_prep_ready=True" in text


def test_anchor119_row_domain_acceptance_refresh_prep_uses_review_state_marker(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    signoff_bundle_path = tmp_path / "signoff.json"
    enablement_gate_prep_path = tmp_path / "prep.json"
    review_state_path = tmp_path / "review_state.json"
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(enablement_gate_prep_path, _enablement_gate_prep_json())
    _write_json(review_state_path, _review_state_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep(
        repo_root,
        signoff_bundle_path=signoff_bundle_path,
        enablement_gate_prep_path=enablement_gate_prep_path,
        review_state_path=review_state_path,
    )

    assert report["status"]["acceptance_refresh_prep_ready"] is True
    assert report["status"]["review_state_ready"] is True
    assert report["status"]["reviewed_runtime_patch_exists"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["recommended_next_step"] == "run_prod_4x4_acceptance_refresh"
    gates = {gate["gate_id"]: gate for gate in report["gates"]}
    assert gates["reviewed_runtime_patch_exists"]["satisfied"] is True
    assert gates["production_acceptance_refresh_completed"]["satisfied"] is False


def test_anchor119_row_domain_acceptance_refresh_prep_fails_if_signoff_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    enablement_gate_prep_path = tmp_path / "prep.json"
    _write_json(enablement_gate_prep_path, _enablement_gate_prep_json())

    report = build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep(
        repo_root,
        signoff_bundle_path=tmp_path / "missing.json",
        enablement_gate_prep_path=enablement_gate_prep_path,
    )

    assert report["status"]["acceptance_refresh_prep_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "signoff_bundle_present" in failed


def test_anchor119_row_domain_acceptance_refresh_prep_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    signoff_bundle_path = tmp_path / "signoff.json"
    enablement_gate_prep_path = tmp_path / "prep.json"
    output_dir = tmp_path / "out"
    _write_json(signoff_bundle_path, _signoff_bundle_json())
    _write_json(enablement_gate_prep_path, _enablement_gate_prep_json())
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_refresh_prep.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--signoff-bundle",
            str(signoff_bundle_path),
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

    assert "phase3b anchor119 row-domain acceptance refresh prep" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--signoff-bundle",
            str(signoff_bundle_path),
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

    assert "anchor119_row_domain_acceptance_refresh_prep_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor119_row_domain_acceptance_refresh_prep.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"]["acceptance_refresh_prep_ready"] is True
    assert (output_dir / "anchor119_row_domain_acceptance_refresh_prep.md").exists()
    assert (output_dir / "anchor119_row_domain_acceptance_refresh_prep.txt").exists()
