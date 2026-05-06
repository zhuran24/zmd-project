from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_template_footprint_probe_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_template_footprint_probe_external_review_package,
)


def test_template_footprint_probe_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_template_footprint_probe_external_review_package(
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


def test_template_footprint_probe_external_review_package_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    package = build_signature_bucket_template_footprint_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s74_review_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s72 = json.loads(
            archive.read(
                "evidence/s72_signature_bucket_template_footprint_probe_readiness.json"
            ).decode("utf-8")
        )
        s73_builder = archive.read(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_template_footprint_probe_review.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s68_signature_bucket_fallback_reason_probe_execution.json" in names
    assert "evidence/s70_external_review_reply_summary.json" in names
    assert "evidence/s71_signature_bucket_template_footprint_support_implementation.json" in names
    assert "evidence/s72_signature_bucket_template_footprint_probe_readiness.json" in names
    assert "evidence/s72_future_command_template.json" in names
    assert "source_context/src/models/exact_coordinate_master.py" in names
    assert "test_context/src/tests/test_master.py" in names
    assert (
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_template_footprint_probe_readiness.py"
        in names
    )
    assert (
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_template_footprint_probe_review.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_executed"] is False
    assert s72["readiness"]["classification"] == "ready_for_template_footprint_probe_review"
    assert s72["probe_execution_enabled"] is False
    assert "template_footprint_probe_inconclusive" in s73_builder
    assert "safety_disqualified" in s73_builder


def test_template_footprint_probe_external_review_package_no_write(tmp_path: Path) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_template_footprint_probe_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_template_footprint_probe_external_review_package_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S74 external review package namespace"):
        build_signature_bucket_template_footprint_probe_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s68_execution": inputs_dir / "s68_execution.json",
        "s64_review": inputs_dir / "s64_review.json",
        "s69_strategy": inputs_dir / "s69_strategy.json",
        "s70_review_summary": inputs_dir / "s70_review_summary.json",
        "s71_implementation": inputs_dir / "s71_implementation.json",
        "s72_readiness": inputs_dir / "s72_readiness.json",
        "s72_future_command": inputs_dir / "s72_future_command.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "test_master": inputs_dir / "test_master.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
        "s64_builder": inputs_dir / "s64_builder.py",
        "s69_builder": inputs_dir / "s69_builder.py",
        "s70_package_builder": inputs_dir / "s70_package_builder.py",
        "s72_builder": inputs_dir / "s72_builder.py",
        "s73_builder": inputs_dir / "s73_builder.py",
        "s64_tests": inputs_dir / "test_s64.py",
        "s69_tests": inputs_dir / "test_s69.py",
        "s70_tests": inputs_dir / "test_s70.py",
        "s72_tests": inputs_dir / "test_s72.py",
        "s73_tests": inputs_dir / "test_s73.py",
    }
    paths["s68_execution"].write_text(
        json.dumps({"status": "completed"}) + "\n",
        encoding="utf-8",
    )
    paths["s64_review"].write_text(
        json.dumps({"status": "completed", "interpretation": {"classification": "unsupported_footprint_dominates"}})
        + "\n",
        encoding="utf-8",
    )
    paths["s69_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "unsupported_template_footprint_support_strategy_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s70_review_summary"].write_text(
        json.dumps(
            {
                "review_verdict": "pass",
                "review_passed": True,
                "review_is_authorization": False,
                "authorization_required_next": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s71_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
        encoding="utf-8",
    )
    paths["s72_readiness"].write_text(
        json.dumps(
            {
                "status": "completed",
                "probe_execution_enabled": False,
                "readiness": {"classification": "ready_for_template_footprint_probe_review"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s72_future_command"].write_text(
        json.dumps(
            {
                "command": [
                    "python",
                    "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
                    "--execute-no-solve",
                    "--candidate-key",
                    "42x32",
                    "--run-id",
                    "local_hotspot_42x32_signature_bucket_template_footprint_inst_no_solve_001",
                ],
                "environment": {
                    "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT": "1",
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
                "- Current S68 fallback-reason no-solve probe result.",
                "- Current S69/S70 template-footprint support review state.",
                "- Current S70 external review result.",
                "- Current S71 template-footprint support patch state.",
                "- Current S72/S73 template-footprint probe readiness state.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["exact_coordinate_master_source"].write_text("# full source fixture\n", encoding="utf-8")
    paths["test_master"].write_text("# full test_master fixture\n", encoding="utf-8")
    paths["s73_builder"].write_text(
        "template_footprint_probe_inconclusive\nsafety_disqualified\nfallback_reason_instrumentation_missing\n",
        encoding="utf-8",
    )
    for key in (
        "exact_contract_tests",
        "s64_builder",
        "s69_builder",
        "s70_package_builder",
        "s72_builder",
        "s64_tests",
        "s69_tests",
        "s70_tests",
        "s72_tests",
        "s73_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "74_signature_bucket_template_footprint_probe_external_review_package"
    )
