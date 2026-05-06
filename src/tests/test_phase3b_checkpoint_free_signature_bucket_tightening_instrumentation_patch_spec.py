from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_tightening_instrumentation_patch_spec import (
    build_signature_bucket_tightening_instrumentation_patch_spec,
    write_signature_bucket_tightening_instrumentation_patch_spec,
)


def test_signature_bucket_instrumentation_spec_requires_explicit_source_authorization(
    tmp_path: Path,
) -> None:
    strategy = tmp_path / "signature_bucket_tightening_strategy.json"
    _write_strategy(strategy)

    spec = build_signature_bucket_tightening_instrumentation_patch_spec(strategy_path=strategy)

    assert spec["interpretation"]["classification"] == "patch_spec_ready_source_mutation_still_blocked"
    assert spec["interpretation"]["implementation_allowed_now"] is False
    assert spec["interpretation"]["source_mutation_authorized_by_this_artifact"] is False
    assert spec["source_mutation_performed"] is False
    assert spec["source_model_mutation"] is False
    assert spec["patch_spec"]["env_var"] == "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
    assert spec["patch_spec"]["target_method"].endswith("_apply_ghost_anchor_signature_bucket_tightening")
    assert "phase_seconds.payload_build_mandatory" in spec["patch_spec"]["instrumentation_fields"]
    assert "totals.cells_scanned" in spec["patch_spec"]["instrumentation_fields"]
    assert "top_slow_anchors" in spec["patch_spec"]["instrumentation_fields"]
    assert spec["recommendation"]["action"] == (
        "hold_for_default_off_signature_bucket_tightening_source_authorization"
    )


def test_signature_bucket_instrumentation_spec_holds_for_unready_strategy(tmp_path: Path) -> None:
    strategy = tmp_path / "signature_bucket_tightening_strategy.json"
    _write_strategy(strategy, classification="manual_review_required")

    spec = build_signature_bucket_tightening_instrumentation_patch_spec(strategy_path=strategy)

    assert spec["interpretation"]["classification"] == "manual_review_required"
    assert spec["patch_spec"] == {}
    assert spec["recommendation"]["action"] == "hold_for_manual_review"


def test_signature_bucket_instrumentation_spec_write_mode_is_namespaced(tmp_path: Path) -> None:
    strategy = tmp_path / "signature_bucket_tightening_strategy.json"
    _write_strategy(strategy)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "37_signature_bucket_tightening_instrumentation_patch_spec"
    )
    spec = build_signature_bucket_tightening_instrumentation_patch_spec(strategy_path=strategy)

    paths = write_signature_bucket_tightening_instrumentation_patch_spec(spec, output_dir)

    assert paths["json"] == output_dir / "signature_bucket_tightening_instrumentation_patch_spec.json"
    assert paths["md"] == output_dir / "signature_bucket_tightening_instrumentation_patch_spec.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["recommendation"]["action"] == (
        "hold_for_default_off_signature_bucket_tightening_source_authorization"
    )


def test_signature_bucket_instrumentation_spec_rejects_bad_namespace(tmp_path: Path) -> None:
    strategy = tmp_path / "signature_bucket_tightening_strategy.json"
    _write_strategy(strategy)
    spec = build_signature_bucket_tightening_instrumentation_patch_spec(strategy_path=strategy)

    with pytest.raises(ValueError, match="signature bucket tightening instrumentation patch spec namespace"):
        write_signature_bucket_tightening_instrumentation_patch_spec(spec, tmp_path / "bad")


def _write_strategy(
    path: Path,
    *,
    classification: str = "signature_bucket_internal_loop_strategy_required",
) -> None:
    action = (
        "prepare_default_off_signature_bucket_tightening_instrumentation_patch_spec"
        if classification == "signature_bucket_internal_loop_strategy_required"
        else "hold_for_manual_signature_bucket_tightening_review"
    )
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "no_solve": True,
                "source_model_mutation": False,
                "source_mutation_performed": False,
                "hotspot_method": (
                    "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
                ),
                "interpretation": {"classification": classification},
                "recommendation": {
                    "action": action,
                    "next_engineering_step": "prepare spec-only instrumentation patch",
                },
                "evidence": {
                    "signature_bucket_tightening_seconds": 66.0,
                    "ghost_conditioned_mandatory_bucket_constraints": 68,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
