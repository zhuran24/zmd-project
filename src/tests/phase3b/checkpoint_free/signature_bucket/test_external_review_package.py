from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.build_external_review_package import (
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_external_review_package,
)


def test_signature_bucket_external_review_package_builds_zip_and_validates_clean_extraction(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_001",
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
    final_request_text = (output_dir / "pkg_001" / "review_request.md").read_text(encoding="utf-8")
    assert "review_request.md" in names
    assert "manifest.json" in names
    assert "evidence/s35_overlay_timing_probe.json" in names
    assert "evidence/s36_signature_bucket_tightening_strategy.json" in names
    assert "evidence/s37_signature_bucket_tightening_instrumentation_patch_spec.json" in names
    assert "coordination/agents_signature_bucket_gate_excerpt.md" in names
    assert "source_context/src/models/exact_coordinate_master.py" in names
    assert "code_context/scripts/phase3b/checkpoint_free/signature_bucket/tightening/build_strategy.py" in names
    assert (
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/tightening/build_instrumentation_patch_spec.py"
        in names
    )
    assert "code_context/scripts/phase3b/checkpoint_free/signature_bucket/build_external_review_package.py" in names
    assert "test_context/src/tests/test_master.py" in names
    assert "test_context/src/tests/test_exact_contract.py" in names
    assert "Package filename: `pkg_001.zip`" in request_text
    assert "Package SHA256:" in request_text
    assert all(text in request_text for text in REVIEW_WORDING_REQUIREMENTS)
    assert "fuller code context for caution" in request_text
    assert "Package filename: `pkg_001.zip`" in final_request_text
    assert str(package["zip_sha256"]) in final_request_text
    assert (output_dir / "pkg_001" / "clean_extraction_validation.json").exists()
    assert (output_dir / "pkg_001" / "zip_sha256.txt").exists()


def test_signature_bucket_external_review_package_no_write_returns_payload_without_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_001",
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert not (output_dir / "pkg_001" / "pkg_001.zip").exists()


def test_signature_bucket_external_review_package_rejects_bad_namespace(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)

    with pytest.raises(ValueError, match="signature bucket external review package namespace"):
        build_signature_bucket_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=inputs,
        )


def test_signature_bucket_external_review_package_fails_when_review_wording_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    monkeypatch.setattr(
        "scripts.phase3b.checkpoint_free.signature_bucket.build_external_review_package.REVIEW_WORDING_REQUIREMENTS",
        ["missing required phrase"],
    )
    package = build_signature_bucket_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_001",
        inputs=inputs,
    )

    assert package["status"] == "failed"
    assert package["clean_extraction_validation"]["validated"] is False
    assert package["clean_extraction_validation"]["semantic_checks"]["review_wording_requirements"] is False


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
                "When a proposed action has not yet completed the relevant external or human review, describe the next step as \"needs review\" or \"needs review first; if review passes, request user / project owner authorization.\"",
                "- Current signature-bucket tightening gate: S37 source-patch spec still needs review first; if review passes, request explicit default-off source-patch authorization.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths = {
        "s35_overlay_timing_probe": evidence / "s35.json",
        "s36_signature_bucket_strategy": evidence / "s36.json",
        "s37_patch_spec": evidence / "s37.json",
        "agents": agents,
        "target_source": source / "exact_coordinate_master.py",
        "s36_strategy_builder": scripts / "build_phase3b_checkpoint_free_signature_bucket_tightening_strategy.py",
        "s37_patch_spec_builder": scripts
        / "build_phase3b_checkpoint_free_signature_bucket_tightening_instrumentation_patch_spec.py",
        "s38_package_builder": scripts / "build_phase3b_checkpoint_free_signature_bucket_external_review_package.py",
        "focused_master_tests": tests / "test_master.py",
        "exact_contract_tests": tests / "test_exact_contract.py",
    }
    paths["s35_overlay_timing_probe"].write_text(
        json.dumps({"status": "completed", "cp_solver_solve_called": False}) + "\n",
        encoding="utf-8",
    )
    paths["s36_signature_bucket_strategy"].write_text(
        json.dumps({"status": "completed", "interpretation": {"classification": "signature_bucket_internal_loop_strategy_required"}})
        + "\n",
        encoding="utf-8",
    )
    paths["s37_patch_spec"].write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {"implementation_allowed_now": False},
                "patch_spec": {"env_var": "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["target_source"].write_text("def target():\n    return None\n", encoding="utf-8")
    paths["s36_strategy_builder"].write_text("def build_s36():\n    return 'strategy'\n", encoding="utf-8")
    paths["s37_patch_spec_builder"].write_text("def build_s37():\n    return 'spec'\n", encoding="utf-8")
    paths["s38_package_builder"].write_text("def build_s38():\n    return 'package'\n", encoding="utf-8")
    paths["focused_master_tests"].write_text("def test_master_placeholder():\n    assert True\n", encoding="utf-8")
    paths["exact_contract_tests"].write_text("def test_exact_contract_placeholder():\n    assert True\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "38_signature_bucket_external_review_package"
