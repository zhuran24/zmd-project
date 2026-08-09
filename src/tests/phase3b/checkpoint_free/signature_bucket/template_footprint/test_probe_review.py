from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.template_footprint.build_probe_review import (
    EXPECTED_RUN_ID,
    SENSITIVE_PATH_COMPARISON_SCHEMA,
    build_signature_bucket_template_footprint_probe_review,
    main as review_main,
)


def test_template_footprint_probe_review_classifies_effective(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        current_scan_seconds=14.0,
        current_unsupported=1000,
        current_fallbacks=1200,
        support_used=5586,
    )

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "template_footprint_support_effective"
    assert review["interpretation"]["template_footprint_support_used"] == 5586
    assert review["interpretation"]["unsupported_footprint_reduction_ratio"] > 0.5
    assert Path(review["paths"]["review_json"]).exists()


def test_template_footprint_probe_review_classifies_not_used(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, support_used=0)

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "template_footprint_support_not_used"


def test_template_footprint_probe_review_classifies_unsupported_still_dominates(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        current_scan_seconds=21.0,
        current_unsupported=6000,
        current_fallbacks=6200,
        support_used=786,
        fallback_reasons={"unsupported_or_missing_template_footprint": 6000, "legacy_scan_required_other": 200},
    )

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "unsupported_footprint_still_dominates"


def test_template_footprint_probe_review_classifies_scan_still_hot(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        current_scan_seconds=24.0,
        current_unsupported=300,
        current_fallbacks=1200,
        support_used=5586,
        fallback_reasons={"unsupported_or_missing_template_footprint": 300, "legacy_scan_required_other": 900},
    )

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "mandatory_scan_still_hot"


def test_template_footprint_probe_review_missing_instrumentation_is_non_success(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, include_fallback_fields=False)

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "fallback_reason_instrumentation_missing"
    assert review["interpretation"]["classification"] == "fallback_reason_instrumentation_missing"


def test_template_footprint_probe_review_missing_instrumentation_cli_is_nonzero(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, include_fallback_fields=False)

    exit_code = review_main(
        [
            "--readiness",
            str(readiness_path),
            "--probe",
            str(probe_path),
            "--output-dir",
            str(_output_dir(tmp_path)),
            "--no-write",
        ]
    )

    assert exit_code == 1


@pytest.mark.parametrize(
    "field",
    [
        "baseline_mandatory_scan_seconds",
        "baseline_unsupported_footprint_fallbacks",
        "baseline_mandatory_region_counting_fallbacks",
    ],
)
def test_template_footprint_probe_review_missing_baseline_is_inconclusive(
    tmp_path: Path,
    field: str,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    readiness["readiness"].pop(field)
    readiness_path.write_text(json.dumps(readiness) + "\n", encoding="utf-8")

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "template_footprint_probe_inconclusive"
    assert review["interpretation"]["classification"] == "template_footprint_probe_inconclusive"


@pytest.mark.parametrize(
    "total_key",
    [
        "mandatory_region_counting_fallbacks",
        "mandatory_template_footprint_support_attempts",
        "mandatory_template_footprint_support_used",
        "mandatory_template_footprint_support_fallbacks",
    ],
)
def test_template_footprint_probe_review_missing_totals_are_inconclusive(
    tmp_path: Path,
    total_key: str,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    instr = _instrumentation(probe)
    instr["totals"].pop(total_key)
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "template_footprint_probe_inconclusive"
    assert review["interpretation"]["classification"] == "template_footprint_probe_inconclusive"


def test_template_footprint_probe_review_run_id_mismatch_disqualifies(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe["run_id"] = "wrong_run"
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


@pytest.mark.parametrize(
    "flag",
    [
        "source_mutation_performed",
        "candidate_universe_changed",
        "scheduler_integration",
        "runtime_execution_performed",
    ],
)
@pytest.mark.parametrize("bad_value", [None, True, "true", 1, "false", 0])
def test_template_footprint_probe_review_hard_boundary_flags_fail_closed(
    tmp_path: Path,
    flag: str,
    bad_value: object,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    if bad_value is None:
        probe.pop(flag, None)
    else:
        probe[flag] = bad_value
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


@pytest.mark.parametrize(
    "comparison",
    [
        None,
        {},
        {"changed": False, "changed_paths": [], "changed_entries": []},
        {
            "schema": "phase3b-sensitive-path-fingerprint-comparison/v99",
            "changed": False,
            "changed_paths": [],
            "changed_entries": [],
        },
        {"schema": SENSITIVE_PATH_COMPARISON_SCHEMA, "changed": False},
        {
            "schema": SENSITIVE_PATH_COMPARISON_SCHEMA,
            "changed": "false",
            "changed_paths": [],
            "changed_entries": [],
        },
        {
            "schema": SENSITIVE_PATH_COMPARISON_SCHEMA,
            "changed": False,
            "changed_paths": ["data/checkpoints"],
            "changed_entries": [],
        },
        {
            "schema": SENSITIVE_PATH_COMPARISON_SCHEMA,
            "changed": False,
            "changed_paths": [],
            "changed_entries": [
                {"relative_path": "data/checkpoints/exact_campaign_state.json"}
            ],
        },
    ],
)
def test_template_footprint_probe_review_malformed_sensitive_comparison_disqualifies(
    tmp_path: Path,
    comparison: object,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    if comparison is None:
        probe.pop("sensitive_path_comparison", None)
    else:
        probe["sensitive_path_comparison"] = comparison
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_template_footprint_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_template_footprint_probe_review_rejects_bad_namespace(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)

    with pytest.raises(ValueError, match="S73 probe review namespace"):
        build_signature_bucket_template_footprint_probe_review(
            project_root=tmp_path,
            readiness_path=readiness_path,
            probe_path=probe_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_inputs(
    tmp_path: Path,
    *,
    current_scan_seconds: float | None = 14.0,
    current_unsupported: int = 1000,
    current_fallbacks: int = 1200,
    support_attempts: int = 6786,
    support_used: int = 5586,
    support_fallbacks: int = 1200,
    fallback_reasons: dict[str, int] | None = None,
    include_fallback_fields: bool = True,
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    readiness_path = tmp_path / "s72_readiness.json"
    probe_path = tmp_path / "probe.json"
    readiness_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "readiness": {
                    "classification": "ready_for_template_footprint_probe_review",
                    "baseline_mandatory_scan_seconds": 27.0,
                    "baseline_unsupported_footprint_fallbacks": 6786,
                    "baseline_mandatory_region_counting_fallbacks": 6786,
                },
                "probe_execution_enabled": False,
                "next_probe_allowed_only_after_readiness_review": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    phase_seconds = {"mandatory_payload_build": 1.0}
    if current_scan_seconds is not None:
        phase_seconds["per_anchor_mandatory_scan"] = current_scan_seconds
    instrumentation = {
        "enabled": True,
        "phase_seconds": phase_seconds,
        "totals": {
            "mandatory_region_counting_attempts": 21489,
            "mandatory_region_counting_used": 21489 - current_fallbacks,
            "mandatory_region_counting_fallbacks": current_fallbacks,
            "mandatory_template_footprint_support_attempts": support_attempts,
            "mandatory_template_footprint_support_used": support_used,
            "mandatory_template_footprint_support_fallbacks": support_fallbacks,
        },
        "top_slow_entries": [],
    }
    if include_fallback_fields:
        instrumentation["fallback_reasons"] = fallback_reasons or {
            "unsupported_or_missing_template_footprint": current_unsupported,
            "legacy_scan_required_other": max(0, current_fallbacks - current_unsupported),
        }
        instrumentation["top_fallback_entries"] = [
            {
                "rect_idx": 1,
                "anchor": {"x": 1, "y": 2},
                "group_id_or_template": "group::x",
                "bucket_id": "__all__",
                "reason": next(iter(instrumentation["fallback_reasons"])),
                "legacy_scan_count": 100,
                "legacy_pose_hits": 200,
                "elapsed_seconds": 0.1,
            }
        ]
    probe_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": EXPECTED_RUN_ID,
                "target": {"candidate_key": "42x32"},
                "execute_no_solve": True,
                "no_solve": True,
                "fresh_solver_run_started": False,
                "main_py_executed": False,
                "exact_campaign_used": False,
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "proof_source": False,
                "source_model_mutation": False,
                "source_mutation_performed": False,
                "candidate_universe_changed": False,
                "scheduler_integration": False,
                "runtime_execution_performed": False,
                "production_profile_changed": False,
                "inventory": {
                    "model_build_seconds": 20.0,
                    "build_stats_summary": {
                        "global_valid_inequalities": {
                            "signature_bucket_capacity_bounds": {
                                "signature_tightening_instrumentation": instrumentation
                            }
                        }
                    },
                },
                "sensitive_path_comparison": {
                    "schema": SENSITIVE_PATH_COMPARISON_SCHEMA,
                    "changed": False,
                    "changed_paths": [],
                    "changed_entries": [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return readiness_path, probe_path


def _instrumentation(probe: dict[str, object]) -> dict[str, object]:
    return probe["inventory"]["build_stats_summary"]["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "73_signature_bucket_template_footprint_probe_review"
    )
