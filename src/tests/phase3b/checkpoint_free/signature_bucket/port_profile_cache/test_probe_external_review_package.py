from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.port_profile_cache.build_probe_external_review_package import (
    build_port_profile_cache_probe_external_review_package,
)


def test_s119_package_contains_review_wording_clean_extract_and_expanded_bundle(tmp_path: Path) -> None:
    package = build_port_profile_cache_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s117_s118_review_001",
        inputs=_write_inputs(tmp_path),
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"]
    assert package["expanded_review_bundle_sha256"]
    assert package["clean_extraction_validation"]["validated"] is True
    request = Path(package["run_dir"]) / "review_request.md"
    request_text = request.read_text(encoding="utf-8")
    assert "unit_s117_s118_review_001.zip" in request_text
    assert package["zip_sha256"] in request_text
    assert "needs review first" in request_text
    assert "review is not authorization" in request_text
    assert "if review passes request user/project-owner authorization" in request_text
    assert "EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION=1" in request_text
    expanded = Path(package["expanded_review_bundle_path"]).read_text(encoding="utf-8")
    assert "Expanded Review Bundle" in expanded
    assert "unit_s117_s118_review_001.zip" in expanded
    assert package["zip_sha256"] in expanded


def test_s119_package_manifest_includes_key_context(tmp_path: Path) -> None:
    package = build_port_profile_cache_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s117_s118_review_001",
        inputs=_write_inputs(tmp_path),
    )

    keys = {entry["key"] for entry in package["manifest"]["entries"]}
    assert "s117_readiness" in keys
    assert "s118_review_builder" in keys
    assert "s117_readiness_tests" in keys
    assert "s118_review_tests" in keys
    assert "s116_implementation" in keys
    assert "s115_review_summary" in keys
    assert "master_model_source" in keys
    assert "agents_gate" in keys


def test_s119_package_no_write_and_namespace_guard(tmp_path: Path) -> None:
    package = build_port_profile_cache_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s117_s118_review_001",
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert package["status"] == "completed"
    assert not Path(package["run_dir"]).exists()
    with pytest.raises(ValueError, match="S119 package namespace"):
        build_port_profile_cache_probe_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            run_id="unit_s117_s118_review_001",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def _write_inputs(root: Path) -> dict[str, Path]:
    paths = {
        "s111_probe_review": root / "evidence" / "s111.json",
        "s113_probe_execution": root / "evidence" / "s113.json",
        "s114_strategy": root / "evidence" / "s114.json",
        "s115_review_summary": root / "evidence" / "s115.json",
        "s116_implementation": root / "evidence" / "s116.json",
        "s117_readiness": root / "evidence" / "s117.json",
        "s117_future_command": root / "evidence" / "future_command.json",
        "agents_gate": root / "AGENTS.md",
        "master_model_source": root / "src" / "models" / "master_model.py",
        "exact_coordinate_master_source": root / "src" / "models" / "exact_coordinate_master.py",
        "test_master": root / "src" / "tests" / "test_master.py",
        "exact_contract_tests": root / "src" / "tests" / "test_exact_contract.py",
        "s117_readiness_builder": root / "scripts" / "s117.py",
        "s118_review_builder": root / "scripts" / "s118.py",
        "s119_package_builder": root / "scripts" / "s119.py",
        "s117_readiness_tests": root / "src" / "tests" / "test_s117.py",
        "s118_review_tests": root / "src" / "tests" / "test_s118.py",
        "s119_package_tests": root / "src" / "tests" / "test_s119.py",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    json_payloads = {
        "s111_probe_review": {
            "status": "completed",
            "interpretation": {"classification": "port_profile_and_boundary_cache_initialization_hotspot"},
        },
        "s113_probe_execution": {
            "status": "completed",
            "classification": "port_profile_and_boundary_cache_initialization_hotspot",
        },
        "s114_strategy": {
            "status": "completed",
            "classification": "port_profile_boundary_cache_subphase_strategy_required",
        },
        "s115_review_summary": {"review_verdict": "pass"},
        "s116_implementation": {"status": "implemented_and_verified"},
        "s117_readiness": {
            "status": "completed",
            "readiness": {"classification": "ready_for_port_profile_cache_probe_review"},
        },
        "s117_future_command": {"command": ["python"], "environment": {}},
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
        / "119_signature_bucket_port_profile_cache_probe_external_review_package"
    )
