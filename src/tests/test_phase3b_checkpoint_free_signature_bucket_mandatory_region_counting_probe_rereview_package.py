from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_mandatory_region_counting_probe_rereview_package,
)


def test_mandatory_region_counting_probe_rereview_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_region_counting_probe_rereview_package(
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


def test_mandatory_region_counting_probe_rereview_package_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_region_counting_probe_rereview_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="custom_s56_rereview_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s52 = json.loads(
            archive.read(
                "evidence/s52_signature_bucket_mandatory_region_counting_probe_readiness.json"
            ).decode("utf-8")
        )
        source_snippet = archive.read(
            "source_context/src/models/exact_coordinate_master_region_counting_snippets.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s54_failed_review_reply_summary.json" in names
    assert "evidence/s54_failed_review_reply_raw.md" in names
    assert "evidence/s55_s52_s53_readiness_hardening_implementation.json" in names
    assert "evidence/s51_signature_bucket_mandatory_region_counting_implementation.json" in names
    assert "evidence/s52_future_command_template.json" in names
    assert (
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py"
        in names
    )
    assert (
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py"
        in names
    )
    assert (
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py"
        in names
    )
    assert (
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_execution_performed"] is False
    assert (
        s52["readiness"]["classification"]
        == "ready_for_mandatory_region_counting_probe_review"
    )
    assert "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV" in source_snippet
    assert "def _mandatory_region_counting_payload" in source_snippet
    assert "def _apply_ghost_anchor_signature_bucket_tightening" in source_snippet


def test_mandatory_region_counting_probe_rereview_package_no_write(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_region_counting_probe_rereview_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_mandatory_region_counting_probe_rereview_package_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S56 re-review package namespace"):
        build_signature_bucket_mandatory_region_counting_probe_rereview_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s54_failed_review_summary": inputs_dir / "s54_failed_review_summary.json",
        "s54_failed_review_raw": inputs_dir / "s54_failed_review_raw.md",
        "s55_implementation": inputs_dir / "s55.json",
        "s48_probe_review": inputs_dir / "s48_review.json",
        "s49_strategy": inputs_dir / "s49_strategy.json",
        "s50_review_summary": inputs_dir / "s50_review_summary.json",
        "s51_implementation": inputs_dir / "s51.json",
        "s52_readiness": inputs_dir / "s52.json",
        "s52_future_command": inputs_dir / "future_command.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "s52_builder": inputs_dir / "s52_builder.py",
        "s53_builder": inputs_dir / "s53_builder.py",
        "s54_package_builder": inputs_dir / "s54_package_builder.py",
        "s56_package_builder": inputs_dir / "s56_package_builder.py",
        "s52_tests": inputs_dir / "test_s52.py",
        "s53_tests": inputs_dir / "test_s53.py",
        "s56_tests": inputs_dir / "test_s56.py",
        "focused_master_tests": inputs_dir / "test_master.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
    }
    paths["s54_failed_review_summary"].write_text(
        json.dumps(
            {
                "status": "review_failed_blocked",
                "blockers": [
                    {"id": "s53_missing_timing_metrics_not_inconclusive"},
                    {"id": "s53_ignored_hard_boundary_flags"},
                    {"id": "s53_sensitive_path_comparison_shape"},
                ],
                "hardening_notes": [{"id": "s52_exact_command_vector"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s54_failed_review_raw"].write_text(
        "Reviewer did not pass S54 and requested S52/S53 hardening.\n",
        encoding="utf-8",
    )
    paths["s55_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "probe_execution_performed": False,
                "hardening": {
                    "s52_exact_command_vector": True,
                    "s53_missing_metrics_inconclusive": True,
                    "s53_hard_boundary_flags_fail_closed": True,
                    "s53_sensitive_path_shape_fail_closed": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s48_probe_review"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {"classification": "mandatory_scan_hotspot"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s49_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "mandatory_signature_bucket_region_counting_strategy_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s50_review_summary"].write_text(
        json.dumps(
            {
                "status": "review_passed_safe_to_request_authorization",
                "review_verdict": {"review_is_authorization": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s51_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
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
                "- Current S51 mandatory-region-counting source patch state: implemented.",
                "- Current S52/S53 mandatory-region-counting probe readiness state: ready.",
                "- Current S54 external review result: blocked pending hardening.",
                "- Current S55 S52/S53 readiness hardening state: implemented.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["exact_coordinate_master_source"].write_text(
        "\n".join(
            [
                "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV = \"EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING\"",
                "",
                "def resolve_ghost_signature_bucket_mandatory_region_counting_enabled():",
                "    return False",
                "",
                "class CoordinateExactMasterDelegate:",
                "    def _mandatory_region_counting_payload(self):",
                "        return {}",
                "",
                "    def _apply_ghost_anchor_signature_bucket_tightening(self):",
                "        return None",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["focused_master_tests"].write_text(
        "\n".join(
            [
                "def test_ghost_signature_bucket_mandatory_region_counting_enabled_matches_legacy_supported_fixture():",
                "    assert True",
                "",
                "def test_exact_core_overlay_signature_bucket_mandatory_region_counting_matches_legacy():",
                "    assert True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "s52_builder",
        "s53_builder",
        "s54_package_builder",
        "s56_package_builder",
        "s52_tests",
        "s53_tests",
        "s56_tests",
        "exact_contract_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "56_signature_bucket_mandatory_region_counting_probe_rereview_package"
    )
