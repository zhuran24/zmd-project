from __future__ import annotations

import json
from pathlib import Path

from scripts.phase3b.checkpoint_free.master.build_presolve_parameter_result_summary import (
    build_master_presolve_parameter_result_summary,
    write_master_presolve_parameter_result_summary,
)


def test_parameter_result_summary_exhausts_clean_variants_without_search(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    sym0 = tmp_path / "sym0.json"
    probe0 = tmp_path / "probe0.json"
    sym0_probe0 = tmp_path / "sym0_probe0.json"
    _write_review(baseline, "baseline", symmetry_nodes=7_218_285, sat_vars=1_151_270)
    _write_review(sym0, "sym0", symmetry_nodes=0, sat_vars=1_151_270)
    _write_review(probe0, "probe0", symmetry_nodes=7_223_452, sat_vars=1_153_314)
    _write_review(sym0_probe0, "sym0_probe0", symmetry_nodes=0, sat_vars=1_153_314)

    summary = build_master_presolve_parameter_result_summary(
        baseline_review_path=baseline,
        variant_review_paths={
            "sym0": sym0,
            "probe0": probe0,
            "sym0_probe0": sym0_probe0,
        },
    )

    assert summary["interpretation"]["classification"] == (
        "parameter_micro_matrix_exhausted_without_search_start"
    )
    assert summary["interpretation"]["symmetry_disabled_removed_symmetry_graph"] is True
    assert summary["interpretation"]["any_search_started"] is False
    assert summary["recommendation"]["action"] == "prepare_master_model_size_reduction_strategy"
    assert summary["safety"]["checkpoint_written"] is False
    assert summary["safety"]["proof_source"] is False


def test_parameter_result_summary_write_mode(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    sym0 = tmp_path / "sym0.json"
    probe0 = tmp_path / "probe0.json"
    sym0_probe0 = tmp_path / "sym0_probe0.json"
    output_dir = tmp_path / "out"
    _write_review(baseline, "baseline", symmetry_nodes=7_218_285, sat_vars=1_151_270)
    _write_review(sym0, "sym0", symmetry_nodes=0, sat_vars=1_151_270)
    _write_review(probe0, "probe0", symmetry_nodes=7_223_452, sat_vars=1_153_314)
    _write_review(sym0_probe0, "sym0_probe0", symmetry_nodes=0, sat_vars=1_153_314)

    paths = write_master_presolve_parameter_result_summary(
        build_master_presolve_parameter_result_summary(
            baseline_review_path=baseline,
            variant_review_paths={
                "sym0": sym0,
                "probe0": probe0,
                "sym0_probe0": sym0_probe0,
            },
        ),
        output_dir,
    )

    assert paths["json"] == output_dir / "master_presolve_parameter_result_summary.json"
    assert paths["md"] == output_dir / "master_presolve_parameter_result_summary.md"
    assert "Proof source: `false`" in paths["md"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == "prepare_master_model_size_reduction_strategy"


def _write_review(path: Path, variant_id: str, *, symmetry_nodes: int, sat_vars: int) -> None:
    path.write_text(
        json.dumps(
            {
                "run": {
                    "candidate_id": f"candidate_{variant_id}",
                    "run_id": f"run_{variant_id}",
                    "status": "timeout",
                    "resource_stop_triggered": False,
                    "sensitive_path_changed": False,
                },
                "interpretation": {
                    "classification": "presolve_bottleneck_before_search",
                    "search_started": False,
                    "symmetry_time_limit_reached": bool(symmetry_nodes),
                },
                "extracted_metrics": {
                    "max_symmetry_nodes": symmetry_nodes,
                    "max_symmetry_arcs": symmetry_nodes * 2,
                    "max_sat_presolve_vars": sat_vars,
                },
                "checkpoint_written": False,
                "proof_source": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
