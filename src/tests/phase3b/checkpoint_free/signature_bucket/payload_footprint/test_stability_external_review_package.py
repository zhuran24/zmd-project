from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.payload_footprint.build_stability_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_payload_footprint_stability_external_review_package,
)


def test_payload_footprint_stability_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    package = build_signature_bucket_payload_footprint_stability_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_package_inputs(tmp_path),
    )

    run_dir = _output_dir(tmp_path) / DEFAULT_RUN_ID
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


def test_payload_footprint_stability_external_review_package_manifest_contains_full_context(
    tmp_path: Path,
) -> None:
    package = build_signature_bucket_payload_footprint_stability_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s84_review_package",
        inputs=_write_package_inputs(tmp_path),
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s83 = json.loads(
            archive.read(
                "evidence/s83_signature_bucket_payload_footprint_stability_strategy.json"
            ).decode("utf-8")
        )
        request_text = archive.read("review_request.md").decode("utf-8")
        s83_builder = archive.read(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_stability_strategy.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s81_external_review_reply_summary.json" in names
    assert "evidence/s82_signature_bucket_template_footprint_support_gap_probe_execution.json" in names
    assert "evidence/s80_signature_bucket_template_footprint_support_gap_probe_review.json" in names
    assert "evidence/s83_signature_bucket_payload_footprint_stability_strategy.json" in names
    assert "source_context/src/models/exact_coordinate_master.py" in names
    assert "test_context/src/tests/test_master.py" in names
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_stability_strategy.py"
        in names
    )
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_stability_external_review_package.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_executed"] is False
    assert s83["interpretation"]["classification"] == "payload_footprint_stability_strategy_required"
    assert "EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT" in s83_builder
    assert "unstable_footprint_bounds_within_payload" in request_text


def test_payload_footprint_stability_external_review_package_no_write_and_namespace_guard(
    tmp_path: Path,
) -> None:
    output_dir = _output_dir(tmp_path)
    package = build_signature_bucket_payload_footprint_stability_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_package_inputs(tmp_path),
        no_write=True,
    )
    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()

    with pytest.raises(ValueError, match="S84 external review package namespace"):
        build_signature_bucket_payload_footprint_stability_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs = tmp_path / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    paths = {
        "s81_review_summary": inputs / "s81_summary.json",
        "s81_review_raw": inputs / "s81_raw.md",
        "s82_execution": inputs / "s82_execution.json",
        "s80_review": inputs / "s80_review.json",
        "s79_readiness": inputs / "s79_readiness.json",
        "s78_implementation": inputs / "s78_implementation.json",
        "s83_strategy": inputs / "s83_strategy.json",
        "agents": inputs / "AGENTS.md",
        "exact_coordinate_master_source": inputs / "exact_coordinate_master.py",
        "test_master": inputs / "test_master.py",
        "exact_contract_tests": inputs / "test_exact_contract.py",
        "s79_builder": inputs / "s79_builder.py",
        "s80_builder": inputs / "s80_builder.py",
        "s81_package_builder": inputs / "s81_package_builder.py",
        "s83_strategy_builder": inputs / "s83_strategy_builder.py",
        "s84_package_builder": inputs / "s84_package_builder.py",
        "s79_tests": inputs / "test_s79.py",
        "s80_tests": inputs / "test_s80.py",
        "s81_tests": inputs / "test_s81.py",
        "s83_tests": inputs / "test_s83.py",
        "s84_tests": inputs / "test_s84.py",
    }
    paths["s81_review_summary"].write_text(
        json.dumps(
            {
                "review_verdict": "pass",
                "review_is_authorization": False,
                "authorization_required_next": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s81_review_raw"].write_text(
        "safe to request user/project-owner authorization; review is not authorization\n",
        encoding="utf-8",
    )
    paths["s82_execution"].write_text(
        json.dumps(
            {
                "status": "completed",
                "s80_classification": "unstable_footprint_bounds_dominates",
                "probe_status": "completed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s80_review"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "unstable_footprint_bounds_dominates",
                },
            }
        )
        + "\n",
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
    paths["s78_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
        encoding="utf-8",
    )
    paths["s83_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "payload_footprint_stability_strategy_required",
                },
                "future_patch_spec": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT",
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
                "- Current S81 support-gap probe external review package state.",
                "- Current S81/S82 support-gap probe review and execution state: "
                "unstable_footprint_bounds_dominates; next gate is S83 payload-footprint stability.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["exact_coordinate_master_source"].write_text(
        "\n".join(
            [
                "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION = '1'",
                "unstable_footprint_bounds_within_payload = True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s83_strategy_builder"].write_text(
        "EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT\n",
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
        / "84_signature_bucket_payload_footprint_stability_external_review_package"
    )
