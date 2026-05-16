from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.fallback_reason.build_review import (
    EXPECTED_RUN_ID,
    SENSITIVE_PATH_COMPARISON_SCHEMA,
    build_signature_bucket_fallback_reason_probe_review,
    main as review_main,
)


def test_fallback_reason_probe_review_classifies_visible(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        fallback_reasons={
            "missing_compact_bucket_regions": 4,
            "unsupported_or_missing_template_footprint": 4,
        },
    )

    review = build_signature_bucket_fallback_reason_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "fallback_reason_instrumentation_visible"
    assert review["signature_instrumentation"]["fallback_reason_visibility"] == "fallback_reason_instrumentation_visible"
    assert Path(review["paths"]["review_json"]).exists()


@pytest.mark.parametrize(
    "reason,expected",
    [
        ("missing_compact_bucket_regions", "compact_region_metadata_missing_dominates"),
        ("missing_bucket_region_metadata", "compact_region_metadata_missing_dominates"),
        ("overlapping_same_bucket_regions", "overlapping_region_guard_dominates"),
        ("unsupported_or_missing_template_footprint", "unsupported_footprint_dominates"),
        ("region_counting_guard_rejected", "other_guard_failure_dominates"),
        ("legacy_scan_required_other", "other_guard_failure_dominates"),
    ],
)
def test_fallback_reason_probe_review_classifies_dominant_reason(
    tmp_path: Path,
    reason: str,
    expected: str,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, fallback_reasons={reason: 9, "legacy_scan_required_other": 1})

    review = build_signature_bucket_fallback_reason_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == expected
    assert review["interpretation"]["dominant_reason"] == reason


def test_fallback_reason_probe_review_missing_instrumentation_classifies_missing(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, include_fallback_fields=False)

    review = build_signature_bucket_fallback_reason_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "fallback_reason_instrumentation_missing"
    assert review["interpretation"]["classification"] == "fallback_reason_instrumentation_missing"


def test_fallback_reason_probe_review_missing_instrumentation_cli_is_nonzero(
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


def test_fallback_reason_probe_review_missing_timing_is_inconclusive(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, mandatory_scan_seconds=None)

    review = build_signature_bucket_fallback_reason_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "fallback_reason_inconclusive"
    assert review["interpretation"]["classification"] == "fallback_reason_inconclusive"


def test_fallback_reason_probe_review_missing_fallback_total_is_inconclusive(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, include_fallback_total=False)

    review = build_signature_bucket_fallback_reason_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "fallback_reason_inconclusive"
    assert review["interpretation"]["classification"] == "fallback_reason_inconclusive"


def test_fallback_reason_probe_review_sensitive_change_disqualifies(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe["sensitive_path_comparison"] = {"changed": True, "changed_paths": ["data/checkpoints"]}
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_fallback_reason_probe_review(
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
def test_fallback_reason_probe_review_hard_boundary_flags_fail_closed(
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

    review = build_signature_bucket_fallback_reason_probe_review(
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
            "changed_paths": "oops",
            "changed_entries": [],
        },
        {
            "schema": SENSITIVE_PATH_COMPARISON_SCHEMA,
            "changed": False,
            "changed_paths": [1],
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
            "changed_entries": "oops",
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
def test_fallback_reason_probe_review_malformed_sensitive_comparison_disqualifies(
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

    review = build_signature_bucket_fallback_reason_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_fallback_reason_probe_review_rejects_bad_namespace(tmp_path: Path) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)

    with pytest.raises(ValueError, match="S64 probe review namespace"):
        build_signature_bucket_fallback_reason_probe_review(
            project_root=tmp_path,
            readiness_path=readiness_path,
            probe_path=probe_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_inputs(
    root: Path,
    *,
    fallback_reasons: dict[str, int] | None = None,
    mandatory_scan_seconds: float | None = 32.0,
    include_fallback_fields: bool = True,
    include_fallback_total: bool = True,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    readiness_path = root / "s63_readiness.json"
    probe_path = root / "probe.json"
    readiness_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "readiness": {"classification": "ready_for_fallback_reason_probe_review"},
                "probe_execution_enabled": False,
                "next_probe_allowed_only_after_readiness_review": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    phase_seconds = {"mandatory_payload_build": 1.0}
    if mandatory_scan_seconds is not None:
        phase_seconds["per_anchor_mandatory_scan"] = mandatory_scan_seconds
    totals = {
        "mandatory_region_counting_attempts": 100,
        "mandatory_region_counting_used": 60,
    }
    if include_fallback_total:
        totals["mandatory_region_counting_fallbacks"] = 40
    instrumentation = {
        "enabled": True,
        "phase_seconds": phase_seconds,
        "totals": totals,
        "top_slow_entries": [],
    }
    if include_fallback_fields:
        instrumentation["fallback_reasons"] = fallback_reasons or {
            "missing_compact_bucket_regions": 8
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


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "64_signature_bucket_fallback_reason_probe_review"
    )
