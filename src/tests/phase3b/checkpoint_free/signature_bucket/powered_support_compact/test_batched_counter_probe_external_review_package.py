from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.powered_support_compact.build_batched_counter_probe_external_review_package import (
    build_powered_support_compact_item_batched_counter_probe_external_review_package,
)


def test_s141_package_contains_review_wording_clean_extract_and_expanded_bundle(
    tmp_path: Path,
) -> None:
    package = build_powered_support_compact_item_batched_counter_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s139_s140_review_001",
        inputs=_write_inputs(tmp_path),
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"]
    assert package["expanded_review_bundle_sha256"]
    assert package["clean_extraction_validation"]["validated"] is True
    request = Path(package["run_dir"]) / "review_request.md"
    request_text = request.read_text(encoding="utf-8")
    assert "unit_s139_s140_review_001.zip" in request_text
    assert package["zip_sha256"] in request_text
    assert "needs review first" in request_text
    assert "review is not authorization" in request_text
    assert "if review passes request user/project-owner authorization" in request_text
    assert "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION=1" in request_text
    expanded = Path(package["expanded_review_bundle_path"]).read_text(encoding="utf-8")
    assert "Expanded Review Bundle" in expanded
    assert "unit_s139_s140_review_001.zip" in expanded
    assert package["zip_sha256"] in expanded
    with zipfile.ZipFile(package["zip_path"]) as zf:
        names = zf.namelist()
        assert names
        assert all("\\" not in name for name in names)
        assert len(names) == 1 + len(package["manifest"]["entries"])
        extract_dir = tmp_path / "stdlib_extract"
        zf.extractall(extract_dir)
    assert (extract_dir / "manifest.json").exists()


def test_s141_package_manifest_includes_key_context(tmp_path: Path) -> None:
    package = build_powered_support_compact_item_batched_counter_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s139_s140_review_001",
        inputs=_write_inputs(tmp_path),
    )

    keys = {entry["key"] for entry in package["manifest"]["entries"]}
    assert "s139_readiness" in keys
    assert "s140_review_builder" in keys
    assert "s139_readiness_tests" in keys
    assert "s140_review_tests" in keys
    assert "s138_implementation" in keys
    assert "s137_review_summary" in keys
    assert "s133_probe_review" in keys
    assert "master_model_source" in keys
    assert "agents_gate" in keys


def test_s141_package_no_write_and_namespace_guard(tmp_path: Path) -> None:
    package = build_powered_support_compact_item_batched_counter_probe_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s139_s140_review_001",
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert package["status"] == "dry_run"
    assert package["zip_sha256"] is None
    assert package["expanded_review_bundle_sha256"] is None
    assert package["clean_extraction_validation"]["validated"] is False
    assert not Path(package["run_dir"]).exists()
    with pytest.raises(ValueError, match="outside artifact namespace"):
        build_powered_support_compact_item_batched_counter_probe_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            run_id="unit_s139_s140_review_001",
            inputs=_write_inputs(tmp_path),
            no_write=True,
        )


def test_s141_package_rejects_bad_namespace_and_run_id_before_write(tmp_path: Path) -> None:
    bad_output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "141_signature_bucket_powered_support_compact_item_batched_counter_probe_external_review_package"
        / ".."
        / ".."
        / ".."
        / "data"
        / "checkpoints"
    )

    with pytest.raises(ValueError, match="outside artifact namespace"):
        build_powered_support_compact_item_batched_counter_probe_external_review_package(
            project_root=tmp_path,
            output_dir=bad_output_dir,
            run_id="unit_s139_s140_review_001",
            inputs=_write_inputs(tmp_path),
        )
    with pytest.raises(ValueError, match="Invalid artifact run_id"):
        build_powered_support_compact_item_batched_counter_probe_external_review_package(
            project_root=tmp_path,
            output_dir=_package_dir(tmp_path),
            run_id="../../../data/checkpoints/pwn",
            inputs=_write_inputs(tmp_path),
        )

    assert not (tmp_path / "data" / "checkpoints").exists()


def _write_inputs(root: Path) -> dict[str, Path]:
    paths = {
        "s133_probe_review": root / "evidence" / "s133.json",
        "s137_review_summary": root / "evidence" / "s137.json",
        "s138_implementation": root / "evidence" / "s138.json",
        "s139_readiness": root / "evidence" / "s139.json",
        "s139_future_command": root / "evidence" / "future_command.json",
        "agents_gate": root / "AGENTS.md",
        "master_model_source": root / "src" / "models" / "master_model.py",
        "exact_coordinate_master_source": root / "src" / "models" / "exact_coordinate_master.py",
        "test_master": root / "src" / "tests" / "test_master.py",
        "exact_contract_tests": root / "src" / "tests" / "test_exact_contract.py",
        "s139_readiness_builder": root / "scripts" / "s139.py",
        "s140_review_builder": root / "scripts" / "s140.py",
        "s141_package_builder": root / "scripts" / "s141.py",
        "s139_readiness_tests": root / "src" / "tests" / "test_s139.py",
        "s140_review_tests": root / "src" / "tests" / "test_s140.py",
        "s141_package_tests": root / "src" / "tests" / "test_s141.py",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    json_payloads = {
        "s133_probe_review": {
            "status": "completed",
            "interpretation": {"classification": "compact_item_accumulation_still_hot"},
        },
        "s137_review_summary": {"review_verdict": "pass"},
        "s138_implementation": {"status": "implemented_and_verified"},
        "s139_readiness": {
            "status": "completed",
            "readiness": {"classification": "ready_for_powered_support_compact_item_batched_counter_probe_review"},
        },
        "s139_future_command": {"command": ["python"], "environment": {}},
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
        / "141_signature_bucket_powered_support_compact_item_batched_counter_probe_external_review_package"
    )

