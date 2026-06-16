from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.overlay_timing.build_strategy import (
    build_overlay_timing_strategy,
)


def test_overlay_timing_strategy_marks_broader_timing_required(tmp_path: Path) -> None:
    proto_review = tmp_path / "proto_review.json"
    instrumentation_review = tmp_path / "instrumentation_review.json"
    output_dir = _output_dir(tmp_path)
    _write_proto_review(proto_review)
    _write_instrumentation_review(instrumentation_review)

    payload = build_overlay_timing_strategy(
        proto_review_path=proto_review,
        instrumentation_review_path=instrumentation_review,
        output_dir=output_dir,
    )

    assert payload["status"] == "completed"
    assert payload["interpretation"]["classification"] == "broader_overlay_timing_required"
    assert payload["recommendation"]["action"] == "run_single_42x32_wrapper_no_solve_overlay_timing_probe"
    assert payload["cp_solver_solve_called"] is False
    assert payload["checkpoint_written"] is False
    assert payload["source_model_mutation"] is False
    assert (output_dir / "overlay_timing_strategy.json").exists()
    assert (output_dir / "overlay_timing_strategy.md").exists()


def test_overlay_timing_strategy_no_write_does_not_create_output(tmp_path: Path) -> None:
    proto_review = tmp_path / "proto_review.json"
    instrumentation_review = tmp_path / "instrumentation_review.json"
    output_dir = _output_dir(tmp_path)
    _write_proto_review(proto_review)
    _write_instrumentation_review(instrumentation_review)

    payload = build_overlay_timing_strategy(
        proto_review_path=proto_review,
        instrumentation_review_path=instrumentation_review,
        output_dir=output_dir,
        no_write=True,
    )

    assert payload["interpretation"]["classification"] == "broader_overlay_timing_required"
    assert not output_dir.exists()


def test_overlay_timing_strategy_accepts_legacy_proto_review_without_top_status(tmp_path: Path) -> None:
    proto_review = tmp_path / "proto_review.json"
    instrumentation_review = tmp_path / "instrumentation_review.json"
    _write_proto_review(proto_review, include_status=False)
    _write_instrumentation_review(instrumentation_review)

    payload = build_overlay_timing_strategy(
        proto_review_path=proto_review,
        instrumentation_review_path=instrumentation_review,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert payload["interpretation"]["classification"] == "broader_overlay_timing_required"


def test_overlay_timing_strategy_holds_when_instrumentation_ratio_too_large(tmp_path: Path) -> None:
    proto_review = tmp_path / "proto_review.json"
    instrumentation_review = tmp_path / "instrumentation_review.json"
    _write_proto_review(proto_review)
    _write_instrumentation_review(instrumentation_review, ratio=0.25)

    payload = build_overlay_timing_strategy(
        proto_review_path=proto_review,
        instrumentation_review_path=instrumentation_review,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert payload["interpretation"]["classification"] == "manual_review_required"
    assert payload["recommendation"]["action"] == "hold_for_manual_overlay_timing_review"


def test_overlay_timing_strategy_rejects_bad_namespace(tmp_path: Path) -> None:
    proto_review = tmp_path / "proto_review.json"
    instrumentation_review = tmp_path / "instrumentation_review.json"
    _write_proto_review(proto_review)
    _write_instrumentation_review(instrumentation_review)

    with pytest.raises(ValueError, match="outside overlay timing strategy namespace"):
        build_overlay_timing_strategy(
            proto_review_path=proto_review,
            instrumentation_review_path=instrumentation_review,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_proto_review(path: Path, *, include_status: bool = True) -> None:
    payload = {
        "cp_solver_solve_called": False,
        "checkpoint_written": False,
        "proof_source": False,
        "interpretation": {"classification": "ghost_overlay_constraint_build_dominates"},
        "target": {
            "candidate_key": "42x32",
            "candidate_tuple": [1344, 42, 32],
            "ghost_rect": {"w": 42, "h": 32, "area": 1344},
        },
        "evidence": {
            "model_build_seconds": 60.0,
            "timing_hotspots": {
                "ghost_constraint_seconds": 53.4,
                "ghost_constraint_fraction_of_model_build": 0.89,
            },
        },
    }
    if include_status:
        payload["status"] = "completed"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_instrumentation_review(path: Path, *, ratio: float = 0.008) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "proof_source": False,
                "sensitive_path_comparison": {"changed": False},
                "interpretation": {
                    "classification": "instrumentation_patch_safe_but_target_loop_not_primary_wall_clock_hotspot"
                },
                "target": {
                    "candidate_key": "42x32",
                    "candidate_tuple": [1344, 42, 32],
                    "ghost_rect": {"w": 42, "h": 32, "area": 1344},
                },
                "model_build_seconds": 61.0,
                "shape_instrumentation": {
                    "phase_seconds_sum": 0.5,
                    "model_build_seconds_ratio": ratio,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _output_dir(root: Path) -> Path:
    return root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "35_overlay_timing_strategy"
