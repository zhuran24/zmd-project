from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_via_pole_shape_instrumentation_patch_spec import (
    build_via_pole_shape_instrumentation_patch_spec,
    write_via_pole_shape_instrumentation_patch_spec,
)


def test_via_pole_shape_instrumentation_spec_requires_explicit_source_authorization(
    tmp_path: Path,
) -> None:
    review = tmp_path / "candidate_shape_scaling_review.json"
    _write_shape_review(review)

    spec = build_via_pole_shape_instrumentation_patch_spec(shape_review_path=review)

    assert spec["interpretation"]["classification"] == "patch_spec_ready_source_mutation_still_blocked"
    assert spec["interpretation"]["implementation_allowed_now"] is False
    assert spec["interpretation"]["source_mutation_authorized_by_this_artifact"] is False
    assert spec["source_mutation_performed"] is False
    assert spec["patch_spec"]["env_var"] == "EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION"
    assert spec["recommendation"]["action"] == (
        "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
    )


def test_via_pole_shape_instrumentation_spec_holds_for_unready_review(tmp_path: Path) -> None:
    review = tmp_path / "candidate_shape_scaling_review.json"
    _write_shape_review(review, classification="shape_scaling_inconclusive")

    spec = build_via_pole_shape_instrumentation_patch_spec(shape_review_path=review)

    assert spec["interpretation"]["classification"] == "manual_review_required"
    assert spec["patch_spec"] == {}
    assert spec["recommendation"]["action"] == "hold_for_manual_review"


def test_via_pole_shape_instrumentation_spec_write_mode_is_namespaced(tmp_path: Path) -> None:
    review = tmp_path / "candidate_shape_scaling_review.json"
    _write_shape_review(review)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "31_via_pole_shape_instrumentation_patch_spec"
    )
    spec = build_via_pole_shape_instrumentation_patch_spec(shape_review_path=review)

    paths = write_via_pole_shape_instrumentation_patch_spec(spec, output_dir)

    assert paths["json"] == output_dir / "via_pole_shape_instrumentation_patch_spec.json"
    assert paths["md"] == output_dir / "via_pole_shape_instrumentation_patch_spec.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == (
        "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
    )


def test_via_pole_shape_instrumentation_spec_rejects_bad_namespace(tmp_path: Path) -> None:
    review = tmp_path / "candidate_shape_scaling_review.json"
    _write_shape_review(review)
    spec = build_via_pole_shape_instrumentation_patch_spec(shape_review_path=review)

    with pytest.raises(ValueError, match="via-pole shape instrumentation patch spec namespace"):
        write_via_pole_shape_instrumentation_patch_spec(spec, tmp_path / "bad")


def _write_shape_review(
    path: Path,
    *,
    classification: str = "shape_specific_via_pole_anchor_explosion",
) -> None:
    action = (
        "prepare_default_off_via_pole_shape_instrumentation_patch_spec"
        if classification == "shape_specific_via_pole_anchor_explosion"
        else "hold_for_manual_shape_scaling_review"
    )
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": classification,
                },
                "recommendation": {
                    "action": action,
                    "next_engineering_step": "prepare spec-only instrumentation patch",
                },
                "metrics": {
                    "median_non_baseline_anchor_count_ratio": 0.055,
                    "median_non_baseline_ghost_seconds_ratio": 0.044,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
