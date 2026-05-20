from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.y_unique_local.hypothesis import (
    build_phase3b_y_unique_local_hypothesis,
    render_phase3b_y_unique_local_hypothesis_markdown,
)


def test_y_unique_local_hypothesis_deprioritizes_with_existing_negative_validation(
    tmp_path: Path,
) -> None:
    predicate = tmp_path / "predicate.json"
    geometry = tmp_path / "geometry.json"
    no_overlap = tmp_path / "no_overlap.json"
    capacity = tmp_path / "capacity.json"
    _write_json(predicate, _predicate_report(["y_unique:11"]))
    _write_json(geometry, {"class_summary": {"planter_buckwheat_xy_ordering_sensitive_diagnostic": {}}})
    _write_json(no_overlap, {"status": {"outcome": "base_not_infeasible", "recommendation": "base unknown"}})
    _write_json(capacity, {"status": {"outcome": "minimal_subset_not_found", "recommendation": "no k"}})

    report = build_phase3b_y_unique_local_hypothesis(
        tmp_path,
        predicate_scan_path=predicate,
        geometry_signature_path=geometry,
        no_overlap_anchor159_path=no_overlap,
        capacity_anchor159_path=capacity,
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == (
        "class_local_clue_deprioritized_by_existing_negative_validation"
    )
    assert report["hypothesis"]["runtime_promotion_ready"] is False


def test_y_unique_local_hypothesis_needs_validation_without_prior_negative(
    tmp_path: Path,
) -> None:
    predicate = tmp_path / "predicate.json"
    geometry = tmp_path / "geometry.json"
    _write_json(predicate, _predicate_report(["y_unique:11"]))
    _write_json(geometry, {"class_summary": {}})

    report = build_phase3b_y_unique_local_hypothesis(
        tmp_path,
        predicate_scan_path=predicate,
        geometry_signature_path=geometry,
        no_overlap_anchor159_path=tmp_path / "missing_no_overlap.json",
        capacity_anchor159_path=tmp_path / "missing_capacity.json",
    )

    assert report["status"]["outcome"] == "class_local_clue_needs_bounded_validation"


def test_y_unique_local_hypothesis_cli_no_write(tmp_path: Path) -> None:
    predicate = tmp_path / "predicate.json"
    geometry = tmp_path / "geometry.json"
    _write_json(predicate, _predicate_report(["y_unique:11"]))
    _write_json(geometry, {"class_summary": {}})
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/y_unique_local/build_hypothesis.py",
            "--project-root",
            str(tmp_path),
            "--predicate-scan-path",
            str(predicate),
            "--geometry-signature-path",
            str(geometry),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b y_unique local hypothesis" in completed.stdout
    assert not output_dir.exists()


def test_y_unique_local_hypothesis_cli_writes_outputs(tmp_path: Path) -> None:
    predicate = tmp_path / "predicate.json"
    geometry = tmp_path / "geometry.json"
    _write_json(predicate, _predicate_report(["y_unique:11"]))
    _write_json(geometry, {"class_summary": {}})
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/y_unique_local/build_hypothesis.py",
            "--project-root",
            str(tmp_path),
            "--predicate-scan-path",
            str(predicate),
            "--geometry-signature-path",
            str(geometry),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "y_unique_local_hypothesis.json").exists()
    assert (output_dir / "y_unique_local_hypothesis.md").exists()
    assert (output_dir / "y_unique_local_hypothesis.txt").exists()


def test_y_unique_local_hypothesis_renders_markdown(tmp_path: Path) -> None:
    predicate = tmp_path / "predicate.json"
    geometry = tmp_path / "geometry.json"
    _write_json(predicate, _predicate_report(["y_unique:11"]))
    _write_json(geometry, {"class_summary": {}})
    report = build_phase3b_y_unique_local_hypothesis(
        tmp_path,
        predicate_scan_path=predicate,
        geometry_signature_path=geometry,
    )

    markdown = render_phase3b_y_unique_local_hypothesis_markdown(report)

    assert "Runtime promotion ready" in markdown
    assert "Validation Plan" in markdown


def _predicate_report(features: list[str]) -> dict:
    return {
        "status": {"outcome": "no_order_independent_predicate_found"},
        "global_scan": {
            "candidate_features": [],
            "class_local_candidate_features": features,
        },
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
