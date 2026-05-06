from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package_v3 import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_mandatory_region_counting_probe_rereview_package_v3,
)


def test_mandatory_region_counting_probe_rereview_package_v3_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_region_counting_probe_rereview_package_v3(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
    )

    run_dir = output_dir / DEFAULT_RUN_ID
    zip_path = Path(package["zip_path"])
    assert package["status"] == "completed"
    assert zip_path.is_file()
    assert package["clean_extraction_validation"]["validated"] is True
    assert package["sensitive_path_comparison"]["changed"] is False
    request_text = (run_dir / "review_request.md").read_text(encoding="utf-8")
    assert zip_path.name in request_text
    assert package["zip_sha256"] in request_text
    for phrase in REVIEW_WORDING_REQUIREMENTS:
        assert phrase in request_text


def test_mandatory_region_counting_probe_rereview_package_v3_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    package = build_signature_bucket_mandatory_region_counting_probe_rereview_package_v3(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s58_rereview_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s57 = json.loads(
            archive.read(
                "evidence/s57_s53_fail_closed_hardening_implementation.json"
            ).decode("utf-8")
        )
        s56_raw = archive.read("evidence/s56_failed_review_reply_raw.md").decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s56_failed_review_reply_raw.md" in names
    assert "evidence/s57_s53_fail_closed_hardening_implementation.json" in names
    assert (
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py"
        in names
    )
    assert "code_context/scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py" in names
    assert (
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_execution_performed"] is False
    assert s57["status"] == "implemented_and_verified"
    assert s57["runtime_execution_performed"] is False
    assert "Review does not pass yet" in s56_raw


def test_mandatory_region_counting_probe_rereview_package_v3_no_write(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_region_counting_probe_rereview_package_v3(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_mandatory_region_counting_probe_rereview_package_v3_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S58 re-review package namespace"):
        build_signature_bucket_mandatory_region_counting_probe_rereview_package_v3(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s56_failed_review_raw": inputs_dir / "s56_failed_review_raw.md",
        "s56_package_summary": inputs_dir / "s56_package_summary.json",
        "s57_implementation": inputs_dir / "s57.json",
        "s52_readiness": inputs_dir / "s52.json",
        "s52_future_command": inputs_dir / "future_command.json",
        "agents": inputs_dir / "AGENTS.md",
        "s52_builder": inputs_dir / "s52_builder.py",
        "s53_builder": inputs_dir / "s53_builder.py",
        "overlay_timing_probe": inputs_dir / "run_phase3b_checkpoint_free_overlay_timing_probe.py",
        "s57_builder": inputs_dir / "s57_builder.py",
        "s58_package_builder": inputs_dir / "s58_package_builder.py",
        "s52_tests": inputs_dir / "test_s52.py",
        "s53_tests": inputs_dir / "test_s53.py",
        "overlay_timing_probe_tests": inputs_dir / "test_overlay_timing_probe.py",
        "s58_tests": inputs_dir / "test_s58.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
    }
    paths["s56_failed_review_raw"].write_text(
        "Review does not pass yet. Recommended minimal fix: strict fail-closed S53 schema.\n",
        encoding="utf-8",
    )
    paths["s56_package_summary"].write_text(
        json.dumps({"status": "completed", "zip_sha256": "abc"}) + "\n",
        encoding="utf-8",
    )
    paths["s57_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "probe_execution_performed": False,
                "runtime_execution_performed": False,
                "hardening": {
                    "s53_timing_numeric_gate_precedes_attempts_used_fallback_classification": True,
                    "s53_sensitive_path_comparison_requires_changed_paths_empty_list_of_strings": True,
                    "s53_hard_boundary_flags_require_literal_false": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s52_readiness"].write_text(
        json.dumps(
            {
                "status": "completed",
                "readiness": {
                    "classification": "ready_for_mandatory_region_counting_probe_review"
                },
                "probe_execution_enabled": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s52_future_command"].write_text(
        json.dumps(
            {
                "command": [
                    "python",
                    "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
                    "--execute-no-solve",
                    "--candidate-key",
                    "42x32",
                    "--run-id",
                    "local_hotspot_42x32_signature_bucket_region_counting_inst_no_solve_001",
                ],
                "environment": {
                    "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING": "1",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["agents"].write_text(
        "\n".join(
            [
                "## GPT Project Review Standing Authorization",
                "- Current S52/S53 mandatory-region-counting probe readiness state: ready.",
                "- Current S56 external review result: failed.",
                "- Current S57 S53 fail-closed hardening state: implemented.",
                "- Current S58 mandatory-region-counting probe re-review package: current entry.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "s52_builder",
        "s53_builder",
        "overlay_timing_probe",
        "s57_builder",
        "s58_package_builder",
        "s52_tests",
        "s53_tests",
        "overlay_timing_probe_tests",
        "s58_tests",
        "exact_contract_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "58_signature_bucket_mandatory_region_counting_probe_rereview_package_v3"
    )
