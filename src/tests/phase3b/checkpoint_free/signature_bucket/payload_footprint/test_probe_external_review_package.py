from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.payload_footprint.build_probe_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_payload_footprint_probe_external_review_package,
)


def test_payload_footprint_probe_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_payload_footprint_probe_external_review_package(
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


def test_payload_footprint_probe_external_review_package_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    package = build_signature_bucket_payload_footprint_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s88_review_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s86 = json.loads(
            archive.read("evidence/s86_signature_bucket_payload_footprint_probe_readiness.json").decode(
                "utf-8"
            )
        )
        s87_builder = archive.read(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_review.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s85_signature_bucket_payload_footprint_stability_implementation.json" in names
    assert "evidence/s86_signature_bucket_payload_footprint_probe_readiness.json" in names
    assert "evidence/s86_future_command_template.json" in names
    assert "source_context/src/models/exact_coordinate_master.py" in names
    assert "test_context/src/tests/test_master.py" in names
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_readiness.py"
        in names
    )
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_review.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_executed"] is False
    assert s86["readiness"]["classification"] == "ready_for_payload_footprint_probe_review"
    assert s86["probe_execution_enabled"] is False
    assert "payload_footprint_probe_inconclusive" in s87_builder
    assert "safety_disqualified" in s87_builder
    assert "support_gap_instrumentation_missing" in s87_builder


def test_payload_footprint_probe_external_review_package_no_write_and_namespace_guard(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)
    package = build_signature_bucket_payload_footprint_probe_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )
    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()
    with pytest.raises(ValueError, match="S88 external review package namespace"):
        build_signature_bucket_payload_footprint_probe_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s82_execution": inputs_dir / "s82_execution.json",
        "s80_review": inputs_dir / "s80_review.json",
        "s83_strategy": inputs_dir / "s83_strategy.json",
        "s84_review_summary": inputs_dir / "s84_review_summary.json",
        "s84_review_raw": inputs_dir / "s84_review_raw.md",
        "s85_implementation": inputs_dir / "s85_implementation.json",
        "s86_readiness": inputs_dir / "s86_readiness.json",
        "s86_future_command": inputs_dir / "s86_future_command.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "test_master": inputs_dir / "test_master.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
        "s86_builder": inputs_dir / "s86_builder.py",
        "s87_builder": inputs_dir / "s87_builder.py",
        "s88_package_builder": inputs_dir / "s88_package_builder.py",
        "s86_tests": inputs_dir / "test_s86.py",
        "s87_tests": inputs_dir / "test_s87.py",
        "s88_tests": inputs_dir / "test_s88.py",
    }
    paths["s82_execution"].write_text(json.dumps({"status": "completed"}) + "\n", encoding="utf-8")
    paths["s80_review"].write_text(
        json.dumps({"status": "completed", "interpretation": {"classification": "unstable_footprint_bounds_dominates"}})
        + "\n",
        encoding="utf-8",
    )
    paths["s83_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {"classification": "payload_footprint_stability_strategy_required"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s84_review_summary"].write_text(
        json.dumps({"review_verdict": "pass", "review_is_authorization": False})
        + "\n",
        encoding="utf-8",
    )
    paths["s85_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
        encoding="utf-8",
    )
    paths["s86_readiness"].write_text(
        json.dumps(
            {
                "status": "completed",
                "probe_execution_enabled": False,
                "readiness": {"classification": "ready_for_payload_footprint_probe_review"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s86_future_command"].write_text(
        json.dumps(
            {
                "command": [
                    "python",
                    "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
                    "--execute-no-solve",
                    "--candidate-key",
                    "42x32",
                    "--run-id",
                    "local_hotspot_42x32_signature_bucket_payload_footprint_inst_no_solve_001",
                ],
                "environment": {
                    "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT": "1",
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
                "- Current S81/S82 support-gap probe review and execution state.",
                "- Current S83/S84 payload-footprint stability review state.",
                "- Current S84 external review result and S85 authorization gate.",
                "- Current S85 payload-footprint stability patch state.",
                "- Current S86/S87 payload-footprint probe readiness state.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s87_builder"].write_text(
        "payload_footprint_probe_inconclusive\nsafety_disqualified\nsupport_gap_instrumentation_missing\n",
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
        / "88_signature_bucket_payload_footprint_probe_external_review_package"
    )
