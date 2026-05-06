from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_mandatory_region_counting_probe_review,
)


def test_mandatory_region_counting_probe_review_classifies_effective(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        mandatory_scan_seconds=10.0,
        used=100,
        fallbacks=0,
        baseline_seconds=68.0,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "mandatory_region_counting_effective"
    assert review["signature_instrumentation"]["region_counting_status"] == "mandatory_region_counting_used"
    assert review["cp_solver_solve_called"] is False
    assert review["checkpoint_written"] is False
    assert review["proof_source"] is False
    assert Path(review["paths"]["review_json"]).exists()


def test_mandatory_region_counting_probe_review_classifies_not_used(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        attempts=0,
        used=0,
        fallbacks=0,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "mandatory_region_counting_not_used"


def test_mandatory_region_counting_probe_review_classifies_fallback_dominated(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        attempts=100,
        used=5,
        fallbacks=95,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "fallback_dominated"


def test_mandatory_region_counting_probe_review_classifies_scan_still_hot(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        mandatory_scan_seconds=60.0,
        used=100,
        fallbacks=0,
        baseline_seconds=68.0,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "mandatory_scan_still_hot"


def test_mandatory_region_counting_probe_review_missing_baseline_is_inconclusive(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        baseline_seconds=None,
        mandatory_scan_seconds=10.0,
        used=100,
        fallbacks=0,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "instrumentation_inconclusive"
    assert review["interpretation"]["classification"] == "instrumentation_inconclusive"


@pytest.mark.parametrize(
    "attempts,used,fallbacks",
    [
        (0, 0, 0),
        (100, 5, 95),
    ],
)
def test_mandatory_region_counting_probe_review_missing_baseline_fails_closed_before_region_status(
    tmp_path: Path,
    attempts: int,
    used: int,
    fallbacks: int,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        baseline_seconds=None,
        mandatory_scan_seconds=10.0,
        attempts=attempts,
        used=used,
        fallbacks=fallbacks,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "instrumentation_inconclusive"
    assert review["interpretation"]["classification"] == "instrumentation_inconclusive"


def test_mandatory_region_counting_probe_review_missing_mandatory_scan_is_inconclusive(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        baseline_seconds=68.0,
        mandatory_scan_seconds=None,
        used=100,
        fallbacks=0,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "instrumentation_inconclusive"
    assert review["interpretation"]["classification"] == "instrumentation_inconclusive"


@pytest.mark.parametrize(
    "attempts,used,fallbacks",
    [
        (0, 0, 0),
        (100, 5, 95),
    ],
)
def test_mandatory_region_counting_probe_review_missing_mandatory_scan_fails_closed_before_region_status(
    tmp_path: Path,
    attempts: int,
    used: int,
    fallbacks: int,
) -> None:
    readiness_path, probe_path = _write_inputs(
        tmp_path,
        baseline_seconds=68.0,
        mandatory_scan_seconds=None,
        attempts=attempts,
        used=used,
        fallbacks=fallbacks,
    )

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "instrumentation_inconclusive"
    assert review["interpretation"]["classification"] == "instrumentation_inconclusive"


def test_mandatory_region_counting_probe_review_classifies_missing_visibility(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, include_instrumentation=False)

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "visibility_missing"
    assert review["signature_instrumentation"]["present"] is False


def test_mandatory_region_counting_probe_review_safety_failure_disqualifies(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe["cp_solver_solve_called"] = True
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_mandatory_region_counting_probe_review_sensitive_change_disqualifies(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe["sensitive_path_comparison"] = {"changed": True, "changed_paths": ["data/checkpoints"]}
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_mandatory_region_counting_probe_review(
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
def test_mandatory_region_counting_probe_review_hard_boundary_flags_disqualify(
    tmp_path: Path,
    flag: str,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe[flag] = True
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"
    assert review["probe_safety"]["actual_flags"][flag] is True


@pytest.mark.parametrize(
    "flag",
    [
        "source_mutation_performed",
        "candidate_universe_changed",
        "scheduler_integration",
        "runtime_execution_performed",
    ],
)
@pytest.mark.parametrize("bad_value", [None, "true", 1, "false", 0])
def test_mandatory_region_counting_probe_review_hard_boundary_flags_require_literal_false(
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

    review = build_signature_bucket_mandatory_region_counting_probe_review(
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
        [],
        {},
        {"changed_paths": []},
        {"changed": None, "changed_paths": []},
        {"changed": "false", "changed_paths": []},
        {"changed": False},
        {"changed": False, "changed_paths": "oops"},
        {"changed": False, "changed_paths": None},
        {"changed": False, "changed_paths": [1]},
        {"changed": False, "changed_paths": ["data/checkpoints"]},
    ],
)
def test_mandatory_region_counting_probe_review_malformed_sensitive_comparison_disqualifies(
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

    review = build_signature_bucket_mandatory_region_counting_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_mandatory_region_counting_probe_review_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)

    with pytest.raises(ValueError, match="S53 probe review namespace"):
        build_signature_bucket_mandatory_region_counting_probe_review(
            project_root=tmp_path,
            readiness_path=readiness_path,
            probe_path=probe_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_inputs(
    root: Path,
    *,
    baseline_seconds: float | None = 68.0,
    mandatory_scan_seconds: float | None = 10.0,
    attempts: int = 100,
    used: int = 100,
    fallbacks: int = 0,
    include_instrumentation: bool = True,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    readiness_path = root / "s52_readiness.json"
    probe_path = root / "probe.json"
    readiness_payload = {
        "status": "completed",
        "readiness": {
            "classification": "ready_for_mandatory_region_counting_probe_review",
        },
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }
    if baseline_seconds is not None:
        readiness_payload["readiness"]["baseline_mandatory_scan_seconds"] = baseline_seconds
    readiness_path.write_text(json.dumps(readiness_payload) + "\n", encoding="utf-8")
    signature_stats = {}
    if include_instrumentation:
        phase_seconds = {
            "mandatory_payload_build": 0.1,
            "required_optional_payload_build": 0.0,
            "per_anchor_required_optional_scan": 0.0,
            "constraint_add": 0.1,
            "stats_finalize": 0.0,
        }
        if mandatory_scan_seconds is not None:
            phase_seconds["per_anchor_mandatory_scan"] = mandatory_scan_seconds
        signature_stats["signature_tightening_instrumentation"] = {
            "enabled": True,
            "phase_seconds": phase_seconds,
            "totals": {
                "evaluated_placements": 1131,
                "mandatory_payload_count": 19,
                "required_optional_payload_count": 0,
                "mandatory_region_counting_attempts": attempts,
                "mandatory_region_counting_used": used,
                "mandatory_region_counting_fallbacks": fallbacks,
                "mandatory_region_rectangles_evaluated": 120,
                "mandatory_region_overlap_counts": 80,
                "mandatory_region_counted_blocked_poses": 400,
                "mandatory_cells_scanned": 0 if used > 0 and fallbacks == 0 else 1000,
                "mandatory_pose_hits": 0 if used > 0 and fallbacks == 0 else 2000,
                "mandatory_unique_blocked_poses": 400,
                "mandatory_constraints_added": 68,
                "required_optional_constraints_added": 0,
                "constraints_added": 68,
            },
            "top_slow_entries": [
                {
                    "kind": "mandatory",
                    "rect_idx": 1,
                    "anchor": {"x": 1, "y": 2},
                    "group_id_or_template": "group::x",
                    "bucket_id": "bucket::0",
                    "scan_count": 2,
                    "reduction_count": 1,
                    "elapsed_seconds": 1.0,
                }
            ],
        }
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
                            "signature_bucket_capacity_bounds": signature_stats
                        }
                    },
                },
                "timing": {
                    "from_exact_core_total_seconds": 20.0,
                    "recorded_phase_seconds_sum": 21.0,
                    "phases": [
                        {
                            "phase": "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening",
                            "total_seconds": 12.0,
                        },
                        {
                            "phase": "CoordinateExactMasterDelegate._add_ghost_constraints",
                            "total_seconds": 15.0,
                        },
                    ],
                },
                "sensitive_path_comparison": {"changed": False, "changed_paths": []},
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
        / "53_signature_bucket_mandatory_region_counting_probe_review"
    )
