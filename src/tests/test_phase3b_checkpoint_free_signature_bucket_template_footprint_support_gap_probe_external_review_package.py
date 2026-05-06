from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_template_footprint_support_gap_probe_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_template_footprint_support_gap_probe_external_review_package,
)


def test_support_gap_probe_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_template_footprint_support_gap_probe_external_review_package(
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


def test_support_gap_probe_external_review_package_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    package = build_signature_bucket_template_footprint_support_gap_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s81_review_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s79 = json.loads(
            archive.read(
                "evidence/s79_signature_bucket_template_footprint_support_gap_probe_readiness.json"
            ).decode("utf-8")
        )
        s80_builder = archive.read(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_template_footprint_support_gap_probe_review.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s78_signature_bucket_template_footprint_support_gap_instrumentation_implementation.json" in names
    assert "evidence/s79_signature_bucket_template_footprint_support_gap_probe_readiness.json" in names
    assert "evidence/s79_future_command_template.json" in names
    assert "source_context/src/models/exact_coordinate_master.py" in names
    assert "test_context/src/tests/test_master.py" in names
    assert (
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_template_footprint_support_gap_probe_readiness.py"
        in names
    )
    assert (
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_template_footprint_support_gap_probe_review.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_executed"] is False
    assert s79["readiness"]["classification"] == "ready_for_support_gap_probe_review"
    assert s79["probe_execution_enabled"] is False
    assert "support_gap_probe_inconclusive" in s80_builder
    assert "safety_disqualified" in s80_builder
    assert "support_gap_instrumentation_missing" in s80_builder


def test_support_gap_probe_external_review_package_no_write_and_namespace_guard(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)
    package = build_signature_bucket_template_footprint_support_gap_probe_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )
    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()
    with pytest.raises(ValueError, match="S81 external review package namespace"):
        build_signature_bucket_template_footprint_support_gap_probe_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s75_execution": inputs_dir / "s75_execution.json",
        "s73_review": inputs_dir / "s73_review.json",
        "s76_strategy": inputs_dir / "s76_strategy.json",
        "s77_review_summary": inputs_dir / "s77_review_summary.json",
        "s77_review_raw": inputs_dir / "s77_review_raw.md",
        "s78_implementation": inputs_dir / "s78_implementation.json",
        "s79_readiness": inputs_dir / "s79_readiness.json",
        "s79_future_command": inputs_dir / "s79_future_command.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "test_master": inputs_dir / "test_master.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
        "s79_builder": inputs_dir / "s79_builder.py",
        "s80_builder": inputs_dir / "s80_builder.py",
        "s81_package_builder": inputs_dir / "s81_package_builder.py",
        "s79_tests": inputs_dir / "test_s79.py",
        "s80_tests": inputs_dir / "test_s80.py",
        "s81_tests": inputs_dir / "test_s81.py",
    }
    paths["s75_execution"].write_text(json.dumps({"status": "completed"}) + "\n", encoding="utf-8")
    paths["s73_review"].write_text(
        json.dumps({"status": "completed", "interpretation": {"classification": "template_footprint_support_not_used"}})
        + "\n",
        encoding="utf-8",
    )
    paths["s76_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {"classification": "template_footprint_support_not_used_strategy_required"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s77_review_summary"].write_text(
        json.dumps({"review_verdict": "pass", "review_is_authorization": False})
        + "\n",
        encoding="utf-8",
    )
    paths["s78_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
        encoding="utf-8",
    )
    paths["s79_readiness"].write_text(
        json.dumps(
            {
                "status": "completed",
                "probe_execution_enabled": False,
                "readiness": {"classification": "ready_for_support_gap_probe_review"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s79_future_command"].write_text(
        json.dumps(
            {
                "command": [
                    "python",
                    "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
                    "--execute-no-solve",
                    "--candidate-key",
                    "42x32",
                    "--run-id",
                    "local_hotspot_42x32_signature_bucket_template_footprint_support_gap_inst_no_solve_001",
                ],
                "environment": {
                    "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION": "1",
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
                "- Current S74 external review result and S75 no-solve probe state.",
                "- Current S76/S77 template-footprint support-gap review state.",
                "- Current S77 external review result and S78 support-gap instrumentation patch state.",
                "- Current S79/S80 support-gap probe readiness state.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s80_builder"].write_text(
        "support_gap_probe_inconclusive\nsafety_disqualified\nsupport_gap_instrumentation_missing\n",
        encoding="utf-8",
    )
    for key, path in paths.items():
        if not path.exists():
            path.write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "81_signature_bucket_template_footprint_support_gap_probe_external_review_package"
    )
