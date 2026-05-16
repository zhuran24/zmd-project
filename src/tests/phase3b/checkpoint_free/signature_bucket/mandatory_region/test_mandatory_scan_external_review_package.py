from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.mandatory_region.build_mandatory_scan_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_mandatory_scan_external_review_package,
)


def test_mandatory_scan_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_scan_external_review_package(
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


def test_mandatory_scan_external_review_package_manifest_contains_required_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_scan_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="custom_s50_review_package",
        inputs=inputs,
    )

    zip_path = Path(package["zip_path"])
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s49 = json.loads(
            archive.read("evidence/s49_signature_bucket_mandatory_scan_strategy.json").decode(
                "utf-8"
            )
        )
        source_snippet = archive.read(
            "source_context/src/models/exact_coordinate_master_mandatory_scan_snippets.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s48_signature_bucket_visibility_probe_review.json" in names
    assert "evidence/s49_signature_bucket_mandatory_scan_strategy.json" in names
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/mandatory_region/test_mandatory_scan_strategy.py"
        in names
    )
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/mandatory_region/test_mandatory_scan_external_review_package.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert (
        s49["interpretation"]["classification"]
        == "mandatory_signature_bucket_region_counting_strategy_required"
    )
    assert "class SignatureRegion" in source_snippet
    assert "def _build_bucket_regions" in source_snippet
    assert "def _apply_ghost_anchor_signature_bucket_tightening" in source_snippet


def test_mandatory_scan_external_review_package_no_write_does_not_create_run_dir(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_mandatory_scan_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_mandatory_scan_external_review_package_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S50 external review package namespace"):
        build_signature_bucket_mandatory_scan_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s46_implementation": inputs_dir / "s46.json",
        "s48_probe": inputs_dir / "s48_probe.json",
        "s48_review": inputs_dir / "s48_review.json",
        "s49_strategy": inputs_dir / "s49_strategy.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "s49_builder": inputs_dir / "s49_builder.py",
        "s50_package_builder": inputs_dir / "s50_package_builder.py",
        "s48_review_builder": inputs_dir / "s48_review_builder.py",
        "s49_tests": inputs_dir / "test_s49.py",
        "s50_tests": inputs_dir / "test_s50.py",
        "focused_master_tests": inputs_dir / "test_master.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
    }
    paths["s46_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
        encoding="utf-8",
    )
    paths["s48_probe"].write_text(
        json.dumps(
            {
                "status": "completed",
                "execute_no_solve": True,
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s48_review"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {"classification": "mandatory_scan_hotspot"},
                "signature_instrumentation": {
                    "present": True,
                    "dominant_phase": "per_anchor_mandatory_scan",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s49_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "mandatory_signature_bucket_region_counting_strategy_required",
                    "implementation_allowed_now": False,
                },
                "future_patch_spec": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
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
                "- Current S46 visibility-path source patch state: implemented.",
                "- Current S48 signature-bucket visibility probe result: mandatory scan hotspot.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["exact_coordinate_master_source"].write_text(
        "\n".join(
            [
                "class SignatureRegion:",
                "    pass",
                "",
                "def _build_bucket_regions(self):",
                "    return []",
                "",
                "class CoordinateExactMasterDelegate:",
                "    def _apply_ghost_anchor_signature_bucket_tightening(self):",
                "        for cell in domain.get(\"cells\", []):",
                "            blocked_pose_indices = set()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["focused_master_tests"].write_text(
        "\n".join(
            [
                "def test_exact_core_overlay_signature_bucket_tightening_instrumentation_records_mandatory_without_model_delta():",
                "    assert True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "s49_builder",
        "s50_package_builder",
        "s48_review_builder",
        "s49_tests",
        "s50_tests",
        "exact_contract_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "50_signature_bucket_mandatory_scan_region_count_external_review_package"
    )
