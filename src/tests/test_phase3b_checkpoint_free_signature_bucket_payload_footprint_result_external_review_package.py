from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_payload_footprint_result_external_review_package import (
    build_payload_footprint_result_external_review_package,
    build_payload_footprint_result_strategy,
)


def test_s91_strategy_classifies_payload_footprint_effective(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)

    strategy = build_payload_footprint_result_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s87_review_path=paths["s87_review"],
        s89_probe_path=paths["s89_probe"],
        s90_summary_path=paths["s90_summary"],
        no_write=True,
    )

    assert strategy["status"] == "completed"
    assert (
        strategy["classification"]
        == "payload_footprint_effective_residual_overlay_strategy_required"
    )
    assert strategy["conclusion"]["runtime_or_source_patch_allowed_now"] is False


def test_s91_strategy_manual_review_when_s87_not_effective(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)
    s87 = _load(paths["s87_review"])
    s87["interpretation"]["classification"] = "payload_footprint_probe_inconclusive"
    paths["s87_review"].write_text(json.dumps(s87) + "\n", encoding="utf-8")

    strategy = build_payload_footprint_result_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s87_review_path=paths["s87_review"],
        s89_probe_path=paths["s89_probe"],
        s90_summary_path=paths["s90_summary"],
        no_write=True,
    )

    assert strategy["status"] == "manual_review_required"
    assert strategy["classification"] == "manual_review_required"


def test_s92_package_contains_review_wording_and_clean_extracts(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)
    build_payload_footprint_result_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s87_review_path=paths["s87_review"],
        s89_probe_path=paths["s89_probe"],
        s90_summary_path=paths["s90_summary"],
    )
    inputs = {
        "s87_review": paths["s87_review"],
        "s89_probe": paths["s89_probe"],
        "s90_summary": paths["s90_summary"],
        "agents_gate": paths["agents"],
        "builder": paths["builder"],
        "tests": paths["tests"],
    }

    package = build_payload_footprint_result_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s91_review_001",
        inputs=inputs,
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"]
    assert package["clean_extraction_validation"]["validated"] is True
    request = Path(package["run_dir"]) / "review_request.md"
    request_text = request.read_text(encoding="utf-8")
    assert "unit_s91_review_001.zip" in request_text
    assert package["zip_sha256"] in request_text
    assert "needs review first" in request_text
    assert "review is not authorization" in request_text
    assert "if review passes request user/project-owner authorization" in request_text


def test_s91_s92_namespace_guards(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)
    with pytest.raises(ValueError, match="S91 strategy namespace"):
        build_payload_footprint_result_strategy(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            s87_review_path=paths["s87_review"],
            s89_probe_path=paths["s89_probe"],
            s90_summary_path=paths["s90_summary"],
            no_write=True,
        )
    with pytest.raises(ValueError, match="S92 package namespace"):
        build_payload_footprint_result_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs={"s87_review": paths["s87_review"]},
            no_write=True,
        )


def _write_fixtures(root: Path) -> dict[str, Path]:
    for directory in (
        root / "src" / "tests",
        root / "scripts",
        _strategy_dir(root),
    ):
        directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "s87_review": root / "s87_review.json",
        "s89_probe": root / "s89_probe.json",
        "s90_summary": root / "s90_summary.json",
        "agents": root / "AGENTS.md",
        "builder": root / "scripts" / "builder.py",
        "tests": root / "src" / "tests" / "tests.py",
    }
    paths["s87_review"].write_text(json.dumps(_s87_review()) + "\n", encoding="utf-8")
    paths["s89_probe"].write_text(json.dumps(_s89_probe()) + "\n", encoding="utf-8")
    paths["s90_summary"].write_text(json.dumps({"status": "implemented_and_verified"}) + "\n", encoding="utf-8")
    paths["agents"].write_text("gate excerpt\n", encoding="utf-8")
    paths["builder"].write_text("print('builder')\n", encoding="utf-8")
    paths["tests"].write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return paths


def _s87_review() -> dict[str, object]:
    return {
        "status": "completed",
        "interpretation": {
            "classification": "payload_footprint_stability_effective",
            "baseline_mandatory_scan_seconds": 26.631,
            "current_mandatory_scan_seconds": 0.124,
            "mandatory_scan_reduction_ratio": 0.995,
            "baseline_unstable_footprint_bounds_fallbacks": 6786,
            "current_unstable_footprint_bounds_fallbacks": 0,
            "payload_footprint_stability_used": 6786,
            "payload_footprint_stability_fallbacks": 0,
        },
        "probe_safety": {
            "status_completed": True,
            "execute_no_solve": True,
            "sensitive_path_clean": True,
        },
        "signature_instrumentation": {
            "phase_seconds": {"mandatory_payload_build": 2.9}
        },
    }


def _s89_probe() -> dict[str, object]:
    return {
        "status": "completed",
        "cp_solver_solve_called": False,
        "runtime_execution_performed": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "checkpoint_written": False,
        "proof_source": False,
        "sensitive_path_comparison": {
            "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "changed": False,
            "changed_paths": [],
            "changed_entries": [],
        },
        "inventory": {
            "model_build_seconds": 12.287,
            "build_stats_summary": {
                "exact_core_reuse": {"ghost_constraint_seconds": 5.507}
            },
        },
        "timing": {
            "from_exact_core_total_seconds": 12.287,
            "phases": [
                {
                    "phase": "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening",
                    "total_seconds": 3.092,
                },
                {
                    "phase": "CoordinateExactMasterDelegate._apply_ghost_anchor_residual_signature_bucket_tightening",
                    "total_seconds": 1.696,
                },
            ],
        },
    }


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strategy_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "91_signature_bucket_payload_footprint_result_strategy"
    )


def _package_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "92_signature_bucket_payload_footprint_result_external_review_package"
    )
