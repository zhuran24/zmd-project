from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_visibility_path_strategy import (
    build_signature_bucket_visibility_path_strategy,
    write_signature_bucket_visibility_path_strategy,
)


def test_signature_bucket_visibility_path_strategy_classifies_s43_gap(tmp_path: Path) -> None:
    s41, s42, s43, agents = _write_inputs(tmp_path)

    strategy = build_signature_bucket_visibility_path_strategy(
        s41_path=s41,
        s42_path=s42,
        s43_path=s43,
        agents_path=agents,
    )

    assert strategy["status"] == "completed"
    assert (
        strategy["interpretation"]["classification"]
        == "exact_core_overlay_instrumentation_visibility_gap"
    )
    assert strategy["source_mutation_performed"] is False
    assert strategy["interpretation"]["implementation_allowed_now"] is False
    assert strategy["review_required_before_authorization"] is True


def test_signature_bucket_visibility_path_strategy_spec_contains_required_path_contract(
    tmp_path: Path,
) -> None:
    s41, s42, s43, agents = _write_inputs(tmp_path)

    strategy = build_signature_bucket_visibility_path_strategy(
        s41_path=s41,
        s42_path=s42,
        s43_path=s43,
        agents_path=agents,
    )

    spec = strategy["future_patch_spec"]
    assert "_apply_ghost_anchor_signature_bucket_tightening" in spec["target_method"]
    assert "_add_global_valid_inequalities" in spec["normal_finalization_method"]
    assert "MasterPlacementModel.from_exact_core" == spec["exact_core_overlay_factory"]
    assert "Do not call _add_global_valid_inequalities" in spec["rejected_approach"]
    assert any("Default-off ModelProto" in item for item in spec["default_off_contract"])
    assert any("Default-off final build_stats" in item for item in spec["default_off_contract"])
    assert "no _add_global_valid_inequalities call from from_exact_core" in spec["non_goals"]


def test_signature_bucket_visibility_path_strategy_manual_review_on_dirty_safety(
    tmp_path: Path,
) -> None:
    s41, s42, s43, agents = _write_inputs(tmp_path)
    payload = json.loads(s43.read_text(encoding="utf-8"))
    payload["probe_safety"]["actual_flags"]["cp_solver_solve_called"] = True
    s43.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    strategy = build_signature_bucket_visibility_path_strategy(
        s41_path=s41,
        s42_path=s42,
        s43_path=s43,
        agents_path=agents,
    )

    assert strategy["status"] == "manual_review_required"
    assert strategy["interpretation"]["classification"] == "manual_review_required"


def test_signature_bucket_visibility_path_strategy_writes_only_s44_namespace(
    tmp_path: Path,
) -> None:
    s41, s42, s43, agents = _write_inputs(tmp_path)
    strategy = build_signature_bucket_visibility_path_strategy(
        s41_path=s41,
        s42_path=s42,
        s43_path=s43,
        agents_path=agents,
    )
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "44_signature_bucket_visibility_path_strategy"
    )

    paths = write_signature_bucket_visibility_path_strategy(strategy, output_dir)

    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "44_signature_bucket_visibility_path_strategy" in str(paths["json"])
    with pytest.raises(ValueError, match="S44 visibility path strategy namespace"):
        write_signature_bucket_visibility_path_strategy(strategy, tmp_path / "bad")


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    s41 = tmp_path / "s41.json"
    s42 = tmp_path / "s42.json"
    s43 = tmp_path / "s43.json"
    agents = tmp_path / "AGENTS.md"
    s41.write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "implementation": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION",
                    "finalization_scope": "CoordinateExactMasterDelegate._add_global_valid_inequalities",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    s42.write_text(
        json.dumps(
            {
                "status": "completed",
                "readiness": {"classification": "ready_for_readiness_review"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    s43.write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {"classification": "instrumentation_inconclusive"},
                "signature_instrumentation": {
                    "present": False,
                    "classification": "instrumentation_missing",
                },
                "wrapper_timing": {
                    "from_exact_core_total_seconds": 95.7,
                    "ghost_signature_bucket_total_seconds": 84.2,
                },
                "probe_safety": {
                    "actual_flags": {
                        "fresh_solver_run_started": False,
                        "main_py_executed": False,
                        "exact_campaign_used": False,
                        "cp_solver_solve_called": False,
                        "checkpoint_written": False,
                        "proof_source": False,
                        "source_model_mutation": False,
                        "production_profile_changed": False,
                    },
                    "sensitive_path_comparison": {"changed": False},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agents.write_text(
        "## Current S43 signature-bucket enabled no-solve probe result\n",
        encoding="utf-8",
    )
    return s41, s42, s43, agents
