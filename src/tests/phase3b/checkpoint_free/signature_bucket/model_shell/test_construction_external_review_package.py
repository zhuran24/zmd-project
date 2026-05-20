from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.model_shell.build_construction_external_review_package import (
    build_model_shell_construction_external_review_package,
    build_model_shell_construction_strategy,
)


def test_s107_strategy_classifies_model_shell_construction_hotspot(tmp_path: Path) -> None:
    inputs = _write_strategy_inputs(tmp_path)

    strategy = build_model_shell_construction_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s104_review_path=inputs["s104"],
        s106_summary_path=inputs["s106"],
        s105_review_summary_path=inputs["s105"],
        no_write=True,
    )

    assert strategy["status"] == "completed"
    assert strategy["classification"] == "model_shell_construction_subphase_strategy_required"
    assert strategy["future_patch_spec_for_review"]["implementation_allowed_now"] is False
    assert strategy["future_patch_spec_for_review"]["proposed_env_gate"] == (
        "EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION"
    )


def test_s107_strategy_manual_review_when_safety_or_classification_dirty(tmp_path: Path) -> None:
    inputs = _write_strategy_inputs(tmp_path, s104_classification="ghost_constraint_add_hotspot")

    strategy = build_model_shell_construction_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s104_review_path=inputs["s104"],
        s106_summary_path=inputs["s106"],
        s105_review_summary_path=inputs["s105"],
        no_write=True,
    )

    assert strategy["status"] == "manual_review_required"
    assert strategy["classification"] == "manual_review_required"


def test_s107_strategy_namespace_guard(tmp_path: Path) -> None:
    inputs = _write_strategy_inputs(tmp_path)

    with pytest.raises(ValueError, match="S107 strategy namespace"):
        build_model_shell_construction_strategy(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            s104_review_path=inputs["s104"],
            s106_summary_path=inputs["s106"],
            s105_review_summary_path=inputs["s105"],
            no_write=True,
        )


def test_s108_package_contains_review_wording_clean_extract_and_expanded_bundle(
    tmp_path: Path,
) -> None:
    package = build_model_shell_construction_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s107_model_shell_review_001",
        inputs=_write_package_inputs(tmp_path),
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"]
    assert package["expanded_review_bundle_sha256"]
    assert package["clean_extraction_validation"]["validated"] is True
    request = Path(package["run_dir"]) / "review_request.md"
    request_text = request.read_text(encoding="utf-8")
    assert "unit_s107_model_shell_review_001.zip" in request_text
    assert package["zip_sha256"] in request_text
    assert "needs review first" in request_text
    assert "review is not authorization" in request_text
    assert "if review passes request user/project-owner authorization" in request_text
    expanded = Path(package["expanded_review_bundle_path"]).read_text(encoding="utf-8")
    assert "Expanded Review Bundle" in expanded
    assert "unit_s107_model_shell_review_001.zip" in expanded
    assert package["zip_sha256"] in expanded


def test_s108_package_manifest_includes_strategy_source_tests_and_gate(tmp_path: Path) -> None:
    package = build_model_shell_construction_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s107_model_shell_review_001",
        inputs=_write_package_inputs(tmp_path),
    )

    keys = {entry["key"] for entry in package["manifest"]["entries"]}
    assert "s107_strategy" in keys
    assert "s104_probe_review" in keys
    assert "s106_execution_summary" in keys
    assert "master_model_source" in keys
    assert "exact_coordinate_master_source" in keys
    assert "s107_s108_builder" in keys
    assert "s107_s108_tests" in keys
    assert "agents_gate" in keys


def test_s108_package_no_write_and_namespace_guard(tmp_path: Path) -> None:
    package = build_model_shell_construction_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s107_model_shell_review_001",
        inputs=_write_package_inputs(tmp_path),
        no_write=True,
    )

    assert package["status"] == "completed"
    assert not Path(package["run_dir"]).exists()
    with pytest.raises(ValueError, match="S108 package namespace"):
        build_model_shell_construction_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            run_id="unit_s107_model_shell_review_001",
            inputs=_write_package_inputs(tmp_path),
            no_write=True,
        )


def _write_strategy_inputs(
    root: Path,
    *,
    s104_classification: str = "model_shell_construction_hotspot",
) -> dict[str, Path]:
    paths = {
        "s104": root / "evidence" / "s104.json",
        "s106": root / "evidence" / "s106.json",
        "s105": root / "evidence" / "s105.json",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        paths["s104"],
        {
            "status": "completed",
            "interpretation": {
                "classification": s104_classification,
                "phase_seconds": {
                    "model_shell_construction": 7.0,
                    "ghost_constraint_add": 5.9,
                    "coordinate_delegate_bind_from_core": 0.1,
                    "model_proto_clone_bind": 0.09,
                },
            },
            "model_build_seconds": 13.2,
            "probe_safety": {"sensitive_path_clean": True},
            "checkpoint_written": False,
            "proof_source": False,
        },
    )
    _write_json(paths["s106"], {"status": "completed"})
    _write_json(paths["s105"], {"review_verdict": "pass"})
    return paths


def _write_package_inputs(root: Path) -> dict[str, Path]:
    paths = {
        "s105_review_summary": root / "evidence" / "s105.json",
        "s106_execution_summary": root / "evidence" / "s106.json",
        "s104_probe_review": root / "evidence" / "s104.json",
        "s102_implementation": root / "evidence" / "s102.json",
        "s107_strategy": root / "evidence" / "s107.json",
        "agents_gate": root / "AGENTS.md",
        "master_model_source": root / "src" / "models" / "master_model.py",
        "exact_coordinate_master_source": root / "src" / "models" / "exact_coordinate_master.py",
        "test_master": root / "src" / "tests" / "test_master.py",
        "exact_contract_tests": root / "src" / "tests" / "test_exact_contract.py",
        "s103_readiness_builder": root / "scripts" / "s103.py",
        "s104_review_builder": root / "scripts" / "s104.py",
        "s107_s108_builder": root / "scripts" / "s107_s108.py",
        "s107_s108_tests": root / "src" / "tests" / "test_s107_s108.py",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    json_payloads = {
        "s105_review_summary": {"review_verdict": "pass"},
        "s106_execution_summary": {"status": "completed"},
        "s104_probe_review": {"status": "completed"},
        "s102_implementation": {"status": "implemented_and_verified"},
        "s107_strategy": {
            "status": "completed",
            "classification": "model_shell_construction_subphase_strategy_required",
        },
    }
    for key, payload in json_payloads.items():
        _write_json(paths[key], payload)
    for key, path in paths.items():
        if key not in json_payloads:
            path.write_text(f"{key} content\n", encoding="utf-8")
    return paths


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _strategy_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "107_signature_bucket_model_shell_construction_strategy"
    )


def _package_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "108_signature_bucket_model_shell_construction_external_review_package"
    )
