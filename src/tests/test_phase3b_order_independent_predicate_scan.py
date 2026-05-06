from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_order_independent_predicate_scan import (
    build_phase3b_order_independent_predicate_scan,
    render_phase3b_order_independent_predicate_scan_markdown,
)


def test_predicate_scan_blocks_when_unknown_shares_common_feature(tmp_path: Path) -> None:
    signature_path = tmp_path / "signature.json"
    _write_json(signature_path, _signature_report(shared_unknown_axis=True))

    report = build_phase3b_order_independent_predicate_scan(
        tmp_path,
        geometry_signature_path=signature_path,
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "no_order_independent_predicate_found"
    assert report["status"]["runtime_promotion_ready"] is False


def test_predicate_scan_reports_candidate_feature_for_validation(tmp_path: Path) -> None:
    signature_path = tmp_path / "signature.json"
    _write_json(signature_path, _signature_report(shared_unknown_axis=False))

    report = build_phase3b_order_independent_predicate_scan(
        tmp_path,
        geometry_signature_path=signature_path,
    )

    assert report["status"]["outcome"] == "candidate_features_need_solver_validation"
    assert "axis:vertical_or_few_x_strip" in report["global_scan"]["candidate_features"]


def test_predicate_scan_handles_missing_signature(tmp_path: Path) -> None:
    report = build_phase3b_order_independent_predicate_scan(
        tmp_path,
        geometry_signature_path=tmp_path / "missing.json",
    )

    assert report["status"]["outcome"] == "geometry_signature_missing_or_invalid"
    assert report["checks"][2]["status"] == "fail"


def test_predicate_scan_cli_no_write(tmp_path: Path) -> None:
    signature_path = tmp_path / "signature.json"
    _write_json(signature_path, _signature_report(shared_unknown_axis=True))
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_order_independent_predicate_scan.py",
            "--project-root",
            str(tmp_path),
            "--geometry-signature-path",
            str(signature_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b order-independent predicate scan" in completed.stdout
    assert not output_dir.exists()


def test_predicate_scan_cli_writes_outputs(tmp_path: Path) -> None:
    signature_path = tmp_path / "signature.json"
    _write_json(signature_path, _signature_report(shared_unknown_axis=True))
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_phase3b_order_independent_predicate_scan.py",
            "--project-root",
            str(tmp_path),
            "--geometry-signature-path",
            str(signature_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "order_independent_predicate_scan.json").exists()
    assert (output_dir / "order_independent_predicate_scan.md").exists()
    assert (output_dir / "order_independent_predicate_scan.txt").exists()


def test_predicate_scan_renders_markdown(tmp_path: Path) -> None:
    signature_path = tmp_path / "signature.json"
    _write_json(signature_path, _signature_report(shared_unknown_axis=True))
    report = build_phase3b_order_independent_predicate_scan(
        tmp_path,
        geometry_signature_path=signature_path,
    )

    markdown = render_phase3b_order_independent_predicate_scan_markdown(report)

    assert "Runtime promotion ready" in markdown
    assert "no_order_independent_predicate_found" in markdown


def _signature_report(*, shared_unknown_axis: bool) -> dict:
    unknown_axis = "vertical_or_few_x_strip" if shared_unknown_axis else "horizontal_or_few_y_strip"
    return {
        "anchors": [
            {
                "taxonomy_class": "demo",
                "anchor_idx": 1,
                "strategies": [
                    {
                        "strategy": "a",
                        "status": "INFEASIBLE",
                        "geometry": {
                            "dominant_axis": "vertical_or_few_x_strip",
                            "point_count": 3,
                            "x_unique_count": 1,
                            "y_unique_count": 3,
                            "x_span": 0,
                            "y_span": 10,
                            "sequence_fingerprint": "inf",
                            "x_step_counts": {},
                            "y_step_counts": {"5": 2},
                        },
                    },
                    {
                        "strategy": "b",
                        "status": "INFEASIBLE",
                        "geometry": {
                            "dominant_axis": "vertical_or_few_x_strip",
                            "point_count": 4,
                            "x_unique_count": 1,
                            "y_unique_count": 4,
                            "x_span": 0,
                            "y_span": 15,
                            "sequence_fingerprint": "inf2",
                            "x_step_counts": {},
                            "y_step_counts": {"5": 3},
                        },
                    },
                    {
                        "strategy": "c",
                        "status": "UNKNOWN",
                        "geometry": {
                            "dominant_axis": unknown_axis,
                            "point_count": 4,
                            "x_unique_count": 1,
                            "y_unique_count": 4,
                            "x_span": 0,
                            "y_span": 15,
                            "sequence_fingerprint": "unk",
                            "x_step_counts": {},
                            "y_step_counts": {"5": 3},
                        },
                    },
                ],
            }
        ]
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
