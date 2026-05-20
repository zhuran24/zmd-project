from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.enabled_no_solve.build_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_enabled_no_solve_probe_review,
)


def test_signature_bucket_enabled_no_solve_probe_review_classifies_mandatory_scan(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, dominant_phase="per_anchor_mandatory_scan")
    output_dir = _output_dir(tmp_path)

    review = build_signature_bucket_enabled_no_solve_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=output_dir,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "mandatory_scan_hotspot"
    assert review["signature_instrumentation"]["present"] is True
    assert review["signature_instrumentation"]["dominant_phase"] == "per_anchor_mandatory_scan"
    assert review["cp_solver_solve_called"] is False
    assert review["checkpoint_written"] is False
    assert review["proof_source"] is False
    assert review["probe_safety"]["cp_solver_solve_not_called"] is True
    assert review["probe_safety"]["actual_flags"]["cp_solver_solve_called"] is False
    assert (output_dir / "signature_bucket_enabled_no_solve_probe_review.json").exists()
    assert (output_dir / "signature_bucket_enabled_no_solve_probe_review.md").exists()


def test_signature_bucket_enabled_no_solve_probe_review_classifies_payload_and_constraint(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, dominant_phase="mandatory_payload_build")
    payload_review = build_signature_bucket_enabled_no_solve_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )
    assert payload_review["interpretation"]["classification"] == "payload_build_hotspot"

    readiness_path, probe_path = _write_inputs(tmp_path / "constraint", dominant_phase="constraint_add")
    constraint_review = build_signature_bucket_enabled_no_solve_probe_review(
        project_root=tmp_path / "constraint",
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path / "constraint"),
        no_write=True,
    )
    assert constraint_review["interpretation"]["classification"] == "constraint_add_hotspot"


def test_signature_bucket_enabled_no_solve_probe_review_missing_instrumentation_is_inconclusive(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path, include_instrumentation=False)

    review = build_signature_bucket_enabled_no_solve_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "instrumentation_inconclusive"
    assert review["signature_instrumentation"]["present"] is False


def test_signature_bucket_enabled_no_solve_probe_review_safety_failure_requires_manual_review(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe["cp_solver_solve_called"] = True
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_enabled_no_solve_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "manual_review_required"
    assert review["interpretation"]["classification"] == "manual_review_required"


def test_signature_bucket_enabled_no_solve_probe_review_sensitive_change_disqualifies(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe["sensitive_path_comparison"] = {"changed": True, "changed_paths": ["data/checkpoints"]}
    probe_path.write_text(json.dumps(probe) + "\n", encoding="utf-8")

    review = build_signature_bucket_enabled_no_solve_probe_review(
        project_root=tmp_path,
        readiness_path=readiness_path,
        probe_path=probe_path,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )

    assert review["status"] == "disqualified_sensitive_path_mutation"
    assert review["interpretation"]["classification"] == "disqualified_sensitive_path_mutation"


def test_signature_bucket_enabled_no_solve_probe_review_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    readiness_path, probe_path = _write_inputs(tmp_path)

    with pytest.raises(ValueError, match="S43 probe review namespace"):
        build_signature_bucket_enabled_no_solve_probe_review(
            project_root=tmp_path,
            readiness_path=readiness_path,
            probe_path=probe_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_inputs(
    root: Path,
    *,
    dominant_phase: str = "per_anchor_mandatory_scan",
    include_instrumentation: bool = True,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    readiness_path = root / "s42_readiness.json"
    probe_path = root / "probe.json"
    readiness_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "readiness": {"classification": "ready_for_readiness_review"},
                "probe_execution_enabled": False,
                "next_probe_allowed_only_after_readiness_review": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    phase_seconds = {
        "mandatory_payload_build": 1.0,
        "required_optional_payload_build": 0.1,
        "per_anchor_mandatory_scan": 5.0,
        "per_anchor_required_optional_scan": 0.0,
        "constraint_add": 0.5,
        "stats_finalize": 0.01,
    }
    phase_seconds[dominant_phase] = 10.0
    signature_stats = {}
    if include_instrumentation:
        signature_stats["signature_tightening_instrumentation"] = {
            "enabled": True,
            "phase_seconds": phase_seconds,
            "totals": {
                "evaluated_placements": 1131,
                "mandatory_constraints_added": 68,
                "required_optional_constraints_added": 0,
                "constraints_added": 68,
                "mandatory_cells_scanned": 123,
            },
            "top_slow_entries": [
                {
                    "kind": "mandatory",
                    "rect_idx": 1,
                    "anchor": {"x": 1, "y": 2},
                    "group_id_or_template": "group::x",
                    "bucket_id": "bucket::0",
                    "scan_count": 123,
                    "reduction_count": 1,
                    "elapsed_seconds": 9.0,
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
                "production_profile_changed": False,
                "inventory": {
                    "model_build_seconds": 70.0,
                    "build_stats_summary": {
                        "global_valid_inequalities": {
                            "signature_bucket_capacity_bounds": signature_stats
                        }
                    },
                },
                "timing": {
                    "from_exact_core_total_seconds": 70.0,
                    "recorded_phase_seconds_sum": 80.0,
                    "phases": [
                        {
                            "phase": "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening",
                            "total_seconds": 65.0,
                        },
                        {
                            "phase": "CoordinateExactMasterDelegate._add_ghost_constraints",
                            "total_seconds": 66.0,
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
        / "43_signature_bucket_enabled_no_solve_probe_review"
    )
