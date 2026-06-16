from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.outer_overlay.build_subphase_probe_external_review_package import (
    build_outer_overlay_subphase_probe_external_review_package,
)


def test_s105_package_contains_review_wording_clean_extract_and_expanded_bundle(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)

    package = build_outer_overlay_subphase_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s103_s104_review_001",
        inputs=inputs,
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"]
    assert package["expanded_review_bundle_sha256"]
    assert package["clean_extraction_validation"]["validated"] is True
    request = Path(package["run_dir"]) / "review_request.md"
    request_text = request.read_text(encoding="utf-8")
    assert "unit_s103_s104_review_001.zip" in request_text
    assert package["zip_sha256"] in request_text
    assert "needs review first" in request_text
    assert "review is not authorization" in request_text
    assert "if review passes request user/project-owner authorization" in request_text
    expanded = Path(package["expanded_review_bundle_path"]).read_text(encoding="utf-8")
    assert "Expanded Review Bundle" in expanded
    assert "unit_s103_s104_review_001.zip" in expanded
    assert package["zip_sha256"] in expanded


def test_s105_package_no_write_and_namespace_guard(tmp_path: Path) -> None:
    package = build_outer_overlay_subphase_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s103_s104_review_001",
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )
    assert package["status"] == "completed"
    assert not Path(package["run_dir"]).exists()
    with pytest.raises(ValueError, match="S105 package namespace"):
        build_outer_overlay_subphase_probe_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            run_id="unit_s103_s104_review_001",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def test_s105_package_manifest_includes_key_context(tmp_path: Path) -> None:
    package = build_outer_overlay_subphase_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s103_s104_review_001",
        inputs=_write_inputs(tmp_path),
    )

    keys = {entry["key"] for entry in package["manifest"]["entries"]}
    assert "s103_readiness" in keys
    assert "s104_review_builder" in keys
    assert "s103_readiness_tests" in keys
    assert "master_model_source" in keys
    assert "agents_gate" in keys


def _write_inputs(root: Path) -> dict[str, Path]:
    paths = {
        "s99_execution_summary": root / "evidence" / "s99.json",
        "s100_strategy": root / "evidence" / "s100.json",
        "s101_review_summary": root / "evidence" / "s101.json",
        "s102_implementation": root / "evidence" / "s102.json",
        "s103_readiness": root / "evidence" / "s103.json",
        "s103_future_command": root / "evidence" / "future_command.json",
        "agents_gate": root / "AGENTS.md",
        "master_model_source": root / "src" / "models" / "master_model.py",
        "exact_coordinate_master_source": root / "src" / "models" / "exact_coordinate_master.py",
        "test_master": root / "src" / "tests" / "test_master.py",
        "exact_contract_tests": root / "src" / "tests" / "test_exact_contract.py",
        "s103_readiness_builder": root / "scripts" / "s103.py",
        "s104_review_builder": root / "scripts" / "s104.py",
        "s103_readiness_tests": root / "src" / "tests" / "test_s103.py",
        "s104_review_tests": root / "src" / "tests" / "test_s104.py",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    json_payloads = {
        "s99_execution_summary": {"status": "completed"},
        "s100_strategy": {"status": "completed", "classification": "outer_exact_core_overlay_residual_subphase_strategy_required"},
        "s101_review_summary": {"status": "completed", "review_verdict": "pass"},
        "s102_implementation": {"status": "implemented_and_verified"},
        "s103_readiness": {"status": "completed", "readiness": {"classification": "ready_for_outer_overlay_subphase_probe_review"}},
        "s103_future_command": {"command": ["python"], "environment": {}},
    }
    for key, payload in json_payloads.items():
        paths[key].write_text(json.dumps(payload) + "\n", encoding="utf-8")
    for key, path in paths.items():
        if key not in json_payloads:
            path.write_text(f"{key} content\n", encoding="utf-8")
    return paths


def _package_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "105_signature_bucket_outer_overlay_subphase_probe_external_review_package"
    )
