from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.build_external_review_package_v2 import (
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_external_review_package_v2,
)


def test_signature_bucket_external_review_package_v2_builds_zip_and_validates(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_external_review_package_v2(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_002",
        inputs=inputs,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["validated"] is True
    assert package["source_mutation_performed"] is False
    assert package["review_required_before_authorization"] is True
    zip_path = Path(package["zip_path"])
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())
        request_text = archive.read("review_request.md").decode("utf-8")
    final_request_text = (output_dir / "pkg_002" / "review_request.md").read_text(encoding="utf-8")
    required = {
        "review_request.md",
        "manifest.json",
        "evidence/s35_overlay_timing_probe.json",
        "evidence/s36_signature_bucket_tightening_strategy.json",
        "evidence/s37_original_signature_bucket_tightening_instrumentation_patch_spec.json",
        "evidence/s38_signature_bucket_review_reply.md",
        "evidence/s39_signature_bucket_patch_spec_revision.json",
        "coordination/agents_signature_bucket_gate_excerpt.md",
        "source_context/src/models/exact_coordinate_master.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/build_external_review_package_v2.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/test_external_review_package_v2.py",
        "test_context/src/tests/test_master.py",
        "test_context/src/tests/test_exact_contract.py",
    }
    assert required.issubset(names)
    assert "Package filename: `pkg_002.zip`" in request_text
    assert "Package SHA256:" in request_text
    assert "S38 did not pass" in request_text
    assert all(text in request_text for text in REVIEW_WORDING_REQUIREMENTS)
    assert "Package filename: `pkg_002.zip`" in final_request_text
    assert str(package["zip_sha256"]) in final_request_text
    validation = package["clean_extraction_validation"]
    assert validation["semantic_checks"]["s39_revision_classification"] is True


def test_signature_bucket_external_review_package_v2_no_write_returns_payload(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_external_review_package_v2(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_002",
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert not (output_dir / "pkg_002" / "pkg_002.zip").exists()


def test_signature_bucket_external_review_package_v2_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)

    with pytest.raises(ValueError, match="signature bucket external re-review package namespace"):
        build_signature_bucket_external_review_package_v2(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=inputs,
        )


def test_signature_bucket_external_review_package_v2_fails_for_unrevised_s39(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)
    inputs["s39_revised_patch_spec"].write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {
                    "implementation_allowed_now": False,
                    "classification": "manual_review_required",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    package = build_signature_bucket_external_review_package_v2(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_002",
        inputs=inputs,
    )

    assert package["status"] == "failed"
    assert package["clean_extraction_validation"]["validated"] is False
    assert package["clean_extraction_validation"]["semantic_checks"]["s39_revision_classification"] is False


def _write_inputs(root: Path) -> dict[str, Path]:
    evidence = root / "evidence"
    source = root / "src" / "models"
    scripts = root / "scripts"
    tests = root / "src" / "tests"
    evidence.mkdir(parents=True)
    source.mkdir(parents=True)
    scripts.mkdir(parents=True)
    tests.mkdir(parents=True)
    agents = root.parent / "AGENTS.md"
    agents.write_text(
        "\n".join(
            [
                "When a proposed action has not yet completed the relevant external or human review, describe the next step as needs review first.",
                "- Current signature-bucket tightening gate: S37 source-patch spec still needs review first.",
                "- Current signature-bucket external review package: package 001 exists.",
                "- Current S38 external review result: reviewer did not pass and requested a revised spec.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths = {
        "s35_overlay_timing_probe": evidence / "s35.json",
        "s36_signature_bucket_strategy": evidence / "s36.json",
        "s37_original_patch_spec": evidence / "s37.json",
        "s38_review_reply": evidence / "s38_reply.md",
        "s39_revised_patch_spec": evidence / "s39.json",
        "agents": agents,
        "target_source": source / "exact_coordinate_master.py",
        "s36_strategy_builder": scripts / "build_phase3b_checkpoint_free_signature_bucket_tightening_strategy.py",
        "s37_patch_spec_builder": scripts
        / "build_phase3b_checkpoint_free_signature_bucket_tightening_instrumentation_patch_spec.py",
        "s38_package_builder": scripts / "build_phase3b_checkpoint_free_signature_bucket_external_review_package.py",
        "s39_revision_builder": scripts / "build_phase3b_checkpoint_free_signature_bucket_patch_spec_revision.py",
        "s40_package_builder": scripts / "build_phase3b_checkpoint_free_signature_bucket_external_review_package_v2.py",
        "s38_package_tests": tests / "test_phase3b_checkpoint_free_signature_bucket_external_review_package.py",
        "s39_revision_tests": tests / "test_phase3b_checkpoint_free_signature_bucket_patch_spec_revision.py",
        "s40_package_tests": tests / "test_phase3b_checkpoint_free_signature_bucket_external_review_package_v2.py",
        "focused_master_tests": tests / "test_master.py",
        "exact_contract_tests": tests / "test_exact_contract.py",
    }
    paths["s35_overlay_timing_probe"].write_text(
        json.dumps({"status": "completed", "cp_solver_solve_called": False}) + "\n",
        encoding="utf-8",
    )
    paths["s36_signature_bucket_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "signature_bucket_internal_loop_strategy_required"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s37_original_patch_spec"].write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {"implementation_allowed_now": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s38_review_reply"].write_text(
        "Review does not pass yet; output-path mismatch needs a revised spec.\n",
        encoding="utf-8",
    )
    paths["s39_revised_patch_spec"].write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {
                    "implementation_allowed_now": False,
                    "classification": "output_path_finalization_revision_required",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for key, path in paths.items():
        if key in {
            "s35_overlay_timing_probe",
            "s36_signature_bucket_strategy",
            "s37_original_patch_spec",
            "s38_review_reply",
            "s39_revised_patch_spec",
            "agents",
        }:
            continue
        path.write_text(f"# placeholder for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "40_signature_bucket_external_review_package_v2"
    )
