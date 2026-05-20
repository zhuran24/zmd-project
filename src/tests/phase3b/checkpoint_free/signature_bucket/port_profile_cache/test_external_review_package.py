from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.port_profile_cache.build_external_review_package import (
    build_port_profile_cache_external_review_package,
    build_port_profile_cache_strategy,
)


def test_s114_strategy_classifies_port_profile_cache_hotspot(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)

    strategy = build_port_profile_cache_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s111_review_path=inputs["s111_probe_review"],
        s112_review_summary_path=inputs["s112_review_summary"],
        s113_execution_path=inputs["s113_probe_execution"],
        s109_implementation_path=inputs["s109_implementation"],
    )

    assert strategy["status"] == "completed"
    assert strategy["classification"] == "port_profile_boundary_cache_subphase_strategy_required"
    spec = strategy["future_patch_spec_for_review"]
    assert spec["implementation_allowed_now"] is False
    assert spec["review_required_before_authorization"] is True
    assert spec["target_method"] == "MasterPlacementModel._index_pools"
    assert "EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION" == spec["proposed_env_gate"]


def test_s114_strategy_manual_review_when_safety_dirty(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    s111 = json.loads(inputs["s111_probe_review"].read_text(encoding="utf-8"))
    s111["probe_safety"]["sensitive_path_clean"] = False
    inputs["s111_probe_review"].write_text(json.dumps(s111), encoding="utf-8")

    strategy = build_port_profile_cache_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s111_review_path=inputs["s111_probe_review"],
        s112_review_summary_path=inputs["s112_review_summary"],
        s113_execution_path=inputs["s113_probe_execution"],
        s109_implementation_path=inputs["s109_implementation"],
    )

    assert strategy["status"] == "manual_review_required"
    assert strategy["classification"] == "manual_review_required"


def test_s115_package_contains_review_wording_clean_extract_and_expanded_bundle(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    _build_strategy_for_package(tmp_path, inputs)

    package = build_port_profile_cache_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s114_review_001",
        inputs=inputs,
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"]
    assert package["expanded_review_bundle_sha256"]
    assert package["clean_extraction_validation"]["validated"] is True
    request_text = (Path(package["run_dir"]) / "review_request.md").read_text(encoding="utf-8")
    assert "unit_s114_review_001.zip" in request_text
    assert package["zip_sha256"] in request_text
    assert "needs review first" in request_text
    assert "review is not authorization" in request_text
    assert "if review passes request user/project-owner authorization" in request_text
    assert "MasterPlacementModel._index_pools" in request_text
    expanded = Path(package["expanded_review_bundle_path"]).read_text(encoding="utf-8")
    assert "Expanded Review Bundle" in expanded
    assert "unit_s114_review_001.zip" in expanded
    assert package["zip_sha256"] in expanded


def test_s115_package_manifest_includes_key_context(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    _build_strategy_for_package(tmp_path, inputs)

    package = build_port_profile_cache_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s114_review_001",
        inputs=inputs,
    )

    keys = {entry["key"] for entry in package["manifest"]["entries"]}
    assert "s114_strategy" in keys
    assert "s113_probe_execution" in keys
    assert "s111_probe_review" in keys
    assert "s112_review_summary" in keys
    assert "master_model_source" in keys
    assert "exact_coordinate_master_source" in keys
    assert "test_master" in keys
    assert "agents_gate" in keys
    assert "s114_s115_builder" in keys
    assert "s114_s115_tests" in keys


def test_s115_package_no_write_and_namespace_guards(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    _build_strategy_for_package(tmp_path, inputs)

    package = build_port_profile_cache_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s114_review_001",
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert not Path(package["run_dir"]).exists()
    with pytest.raises(ValueError, match="S115 package namespace"):
        build_port_profile_cache_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            run_id="unit_s114_review_001",
            inputs=inputs,
            no_write=True,
        )
    with pytest.raises(ValueError, match="S114 strategy namespace"):
        build_port_profile_cache_strategy(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            s111_review_path=inputs["s111_probe_review"],
            s112_review_summary_path=inputs["s112_review_summary"],
            s113_execution_path=inputs["s113_probe_execution"],
            s109_implementation_path=inputs["s109_implementation"],
            no_write=True,
        )


def _build_strategy_for_package(root: Path, inputs: dict[str, Path]) -> None:
    strategy = build_port_profile_cache_strategy(
        project_root=root,
        output_dir=_strategy_dir(root),
        s111_review_path=inputs["s111_probe_review"],
        s112_review_summary_path=inputs["s112_review_summary"],
        s113_execution_path=inputs["s113_probe_execution"],
        s109_implementation_path=inputs["s109_implementation"],
    )
    inputs["s114_strategy"] = Path(
        strategy["project_root"]
    ) / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "114_signature_bucket_port_profile_cache_strategy" / "signature_bucket_port_profile_cache_strategy.json"


def _write_inputs(root: Path) -> dict[str, Path]:
    paths = {
        "s109_implementation": root / "evidence" / "s109.json",
        "s111_probe_review": root / "evidence" / "s111.json",
        "s112_review_summary": root / "evidence" / "s112.json",
        "s113_probe_execution": root / "evidence" / "s113.json",
        "s114_strategy": root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "114_signature_bucket_port_profile_cache_strategy"
        / "signature_bucket_port_profile_cache_strategy.json",
        "agents_gate": root / "AGENTS.md",
        "master_model_source": root / "src" / "models" / "master_model.py",
        "exact_coordinate_master_source": root / "src" / "models" / "exact_coordinate_master.py",
        "test_master": root / "src" / "tests" / "test_master.py",
        "exact_contract_tests": root / "src" / "tests" / "test_exact_contract.py",
        "s110_readiness_builder": root / "scripts" / "s110.py",
        "s111_review_builder": root / "scripts" / "s111.py",
        "s114_s115_builder": root / "scripts" / "s114_s115.py",
        "s110_readiness_tests": root / "src" / "tests" / "test_s110.py",
        "s111_review_tests": root / "src" / "tests" / "test_s111.py",
        "s114_s115_tests": root / "src" / "tests" / "test_s114_s115.py",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    json_payloads = {
        "s109_implementation": {"status": "implemented_and_verified"},
        "s112_review_summary": {"review_verdict": "pass"},
        "s113_probe_execution": {
            "status": "completed",
            "classification": "port_profile_and_boundary_cache_initialization_hotspot",
        },
        "s111_probe_review": {
            "status": "completed",
            "model_build_seconds": 13.1,
            "checkpoint_written": False,
            "proof_source": False,
            "interpretation": {
                "classification": "port_profile_and_boundary_cache_initialization_hotspot",
                "dominant_phase": "port_profile_and_boundary_cache_initialization",
                "dominant_seconds": 5.57,
                "phase_seconds": {
                    "port_profile_and_boundary_cache_initialization": 5.57,
                    "constructor_finalize": 1.21,
                    "signature_bucket_seed_build": 0.08,
                },
            },
            "probe_safety": {"sensitive_path_clean": True},
        },
    }
    for key, payload in json_payloads.items():
        paths[key].write_text(json.dumps(payload) + "\n", encoding="utf-8")
    for key, path in paths.items():
        if key not in json_payloads and not path.exists():
            path.write_text(f"{key} content\n", encoding="utf-8")
    return paths


def _strategy_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "114_signature_bucket_port_profile_cache_strategy"
    )


def _package_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "115_signature_bucket_port_profile_cache_external_review_package"
    )
