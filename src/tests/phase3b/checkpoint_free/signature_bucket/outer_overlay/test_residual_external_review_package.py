from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.outer_overlay.build_residual_external_review_package import (
    build_outer_overlay_residual_external_review_package,
    build_outer_overlay_residual_strategy,
)


def test_s100_strategy_classifies_outer_overlay_residual_hotspot(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)

    strategy = build_outer_overlay_residual_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s97_review_path=paths["s97_review"],
        s99_probe_path=paths["s99_probe"],
        s99_summary_path=paths["s99_summary"],
        s98_review_summary_path=paths["s98_summary"],
        no_write=True,
    )

    assert strategy["status"] == "completed"
    assert (
        strategy["classification"]
        == "outer_exact_core_overlay_residual_subphase_strategy_required"
    )
    assert strategy["future_patch_spec_for_review"]["implementation_allowed_now"] is False
    assert (
        strategy["future_patch_spec_for_review"]["env_gate"]
        == "EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION"
    )


def test_s100_strategy_manual_review_when_probe_not_outer_residual(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)
    s97 = _load(paths["s97_review"])
    s97["interpretation"]["classification"] = "residual_signature_scan_hotspot"
    paths["s97_review"].write_text(json.dumps(s97) + "\n", encoding="utf-8")

    strategy = build_outer_overlay_residual_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s97_review_path=paths["s97_review"],
        s99_probe_path=paths["s99_probe"],
        s99_summary_path=paths["s99_summary"],
        s98_review_summary_path=paths["s98_summary"],
        no_write=True,
    )

    assert strategy["status"] == "manual_review_required"
    assert strategy["classification"] == "manual_review_required"


def test_s101_package_contains_review_wording_and_clean_extracts(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)
    build_outer_overlay_residual_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        s97_review_path=paths["s97_review"],
        s99_probe_path=paths["s99_probe"],
        s99_summary_path=paths["s99_summary"],
        s98_review_summary_path=paths["s98_summary"],
    )
    inputs = {
        "s98_review_summary": paths["s98_summary"],
        "s99_probe": paths["s99_probe"],
        "s97_probe_review": paths["s97_review"],
        "s99_execution_summary": paths["s99_summary"],
        "agents_gate": paths["agents"],
        "builder": paths["builder"],
        "tests": paths["tests"],
    }

    package = build_outer_overlay_residual_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="unit_s100_outer_residual_review_001",
        inputs=inputs,
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"]
    assert package["clean_extraction_validation"]["validated"] is True
    request = Path(package["run_dir"]) / "review_request.md"
    request_text = request.read_text(encoding="utf-8")
    assert "unit_s100_outer_residual_review_001.zip" in request_text
    assert package["zip_sha256"] in request_text
    assert "needs review first" in request_text
    assert "review is not authorization" in request_text
    assert "if review passes request user/project-owner authorization" in request_text


def test_s100_s101_namespace_guards(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path)
    with pytest.raises(ValueError, match="S100 strategy namespace"):
        build_outer_overlay_residual_strategy(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            s97_review_path=paths["s97_review"],
            s99_probe_path=paths["s99_probe"],
            s99_summary_path=paths["s99_summary"],
            s98_review_summary_path=paths["s98_summary"],
            no_write=True,
        )
    with pytest.raises(ValueError, match="S101 package namespace"):
        build_outer_overlay_residual_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs={"s97_probe_review": paths["s97_review"]},
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
        "s98_summary": root / "s98_summary.json",
        "s97_review": root / "s97_review.json",
        "s99_probe": root / "s99_probe.json",
        "s99_summary": root / "s99_summary.json",
        "agents": root / "AGENTS.md",
        "builder": root / "scripts" / "builder.py",
        "tests": root / "src" / "tests" / "tests.py",
    }
    paths["s98_summary"].write_text(
        json.dumps({"status": "completed", "review_verdict": "pass"}) + "\n",
        encoding="utf-8",
    )
    paths["s97_review"].write_text(json.dumps(_s97_review()) + "\n", encoding="utf-8")
    paths["s99_probe"].write_text(json.dumps(_s99_probe()) + "\n", encoding="utf-8")
    paths["s99_summary"].write_text(
        json.dumps({"status": "completed", "classification": "outer_exact_core_overlay_residual_hotspot"})
        + "\n",
        encoding="utf-8",
    )
    paths["agents"].write_text("gate excerpt\n", encoding="utf-8")
    paths["builder"].write_text("print('builder')\n", encoding="utf-8")
    paths["tests"].write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return paths


def _s97_review() -> dict[str, object]:
    return {
        "status": "completed",
        "model_build_seconds": 12.865,
        "interpretation": {
            "classification": "outer_exact_core_overlay_residual_hotspot",
            "dominant_phase": "outer_exact_core_overlay_residual_seconds",
            "dominant_seconds": 6.824,
        },
        "residual_overlay_summary": {
            "phase_seconds": {
                "outer_exact_core_overlay_residual_seconds": 6.824,
                "payload_footprint_cohort_build_seconds": 2.596,
                "residual_signature_scan_seconds": 2.157,
            }
        },
        "probe_safety": {"sensitive_path_clean": True},
    }


def _s99_probe() -> dict[str, object]:
    return {
        "status": "completed",
        "execute_no_solve": True,
        "no_solve": True,
        "cp_solver_solve_called": False,
        "runtime_execution_performed": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "checkpoint_written": False,
        "proof_source": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "sensitive_path_comparison": {
            "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "changed": False,
            "changed_paths": [],
            "changed_entries": [],
        },
        "inventory": {
            "build_stats_summary": {
                "exact_core_reuse": {
                    "overlay_build_seconds": 12.865,
                    "ghost_constraint_seconds": 6.040,
                    "search_guidance_rebuilt_after_ghost_overlay": True,
                    "cleared_existing_search_strategy_count": 6046,
                    "rebuilt_search_strategy_count": 6047,
                }
            }
        },
    }


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strategy_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "100_signature_bucket_outer_exact_core_overlay_residual_strategy"
    )


def _package_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "101_signature_bucket_outer_exact_core_overlay_residual_external_review_package"
    )
