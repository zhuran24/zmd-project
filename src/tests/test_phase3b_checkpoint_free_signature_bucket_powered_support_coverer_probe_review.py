"""[Codex-era artifact dependent] 永远 skip (除非 artifact 再生).

这个测试导入 scripts/build_phase3b_*_probe_review (或类似), 后者读取 Codex
session (2026-04-30) 产生的 tuning artifact:
  .artifacts/phase3b_local_13900ks_tuning_20260430/126_signature_bucket_powered_support_coverer_probe_review/
    signature_bucket_powered_support_coverer_probe_review.json

该 artifact 是 GPT-Codex workspace 实验产物, 未迁移到当前 project. src/tests/conftest.py
的 fixture guard `_missing_phase3b_signature_bucket_powered_support_coverer_artifact`
检测缺失时自动 skip 整个文件, 不报错.

保留原因 (per memory `feedback_cleanup_preserve_clarify` — 不丢东西原则):
- 历史 reference: 看 Phase 3B signature bucket 调研当时的 verification 逻辑
- 万一未来重生 artifact (e.g. 复现 Codex 实验), 这测试可以直接 re-enable
- 删了会丢历史, 留着零运行成本 (conftest skip 一次)

如果将来要清理, 必须**先**确认 artifact 不会复现 + 没人需要历史参考, 再批量删.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_probe_review import (
    EXPECTED_RUN_ID,
    build_signature_bucket_powered_support_coverer_probe_review,
)


def test_powered_support_coverer_probe_review_classifies_union_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            coverer_phases={
                "coverer_union_collection": 4.0,
                "disjoint_filtering": 0.5,
                "power_index_expansion": 0.1,
                "compact_item_accumulation": 0.1,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "coverer_union_collection_hotspot"


def test_powered_support_coverer_probe_review_classifies_filter_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            coverer_phases={
                "coverer_union_collection": 0.4,
                "disjoint_filtering": 3.5,
                "power_index_expansion": 0.1,
                "compact_item_accumulation": 0.1,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "disjoint_filtering_hotspot"


def test_powered_support_coverer_probe_review_classifies_compact_hotspot(
    tmp_path: Path,
) -> None:
    review = _build_review(
        tmp_path,
        _probe_payload(
            coverer_phases={
                "coverer_union_collection": 0.3,
                "disjoint_filtering": 0.2,
                "power_index_expansion": 0.1,
                "compact_item_accumulation": 2.5,
                "stats_finalize": 0.0,
            }
        ),
    )

    assert review["status"] == "completed"
    assert review["interpretation"]["classification"] == "compact_item_accumulation_hotspot"


def test_powered_support_coverer_probe_review_reports_missing_instrumentation(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    port_profile = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]
    port_profile.pop("powered_support_coverer_instrumentation")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "powered_support_coverer_instrumentation_missing"
    assert (
        review["interpretation"]["classification"]
        == "powered_support_coverer_instrumentation_missing"
    )


def test_powered_support_coverer_probe_review_missing_phase_is_inconclusive(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    coverer = probe["inventory"]["build_stats_summary"]["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]
    coverer["phase_seconds"].pop("power_index_expansion")

    review = _build_review(tmp_path, probe)

    assert review["status"] == "powered_support_coverer_probe_inconclusive"
    assert (
        review["interpretation"]["classification"]
        == "powered_support_coverer_probe_inconclusive"
    )


def test_powered_support_coverer_probe_review_strict_safety_disqualifies(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["sensitive_path_comparison"] = {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": False,
        "changed_paths": [],
    }

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_coverer_probe_review_rejects_hard_boundary_truthy_flag(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["runtime_execution_performed"] = "false"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_coverer_probe_review_rejects_wrong_run_id(
    tmp_path: Path,
) -> None:
    probe = _probe_payload()
    probe["run_id"] = "wrong"

    review = _build_review(tmp_path, probe)

    assert review["status"] == "safety_disqualified"
    assert review["interpretation"]["classification"] == "safety_disqualified"


def test_powered_support_coverer_probe_review_namespace_guard(tmp_path: Path) -> None:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(_probe_payload()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="S126 probe review namespace"):
        build_signature_bucket_powered_support_coverer_probe_review(
            project_root=tmp_path,
            readiness_path=readiness,
            probe_path=probe,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _build_review(tmp_path: Path, probe_payload: dict[str, object]) -> dict[str, object]:
    readiness = tmp_path / "readiness.json"
    probe = tmp_path / "probe.json"
    readiness.write_text(json.dumps(_readiness_payload()) + "\n", encoding="utf-8")
    probe.write_text(json.dumps(probe_payload) + "\n", encoding="utf-8")
    return build_signature_bucket_powered_support_coverer_probe_review(
        project_root=tmp_path,
        readiness_path=readiness,
        probe_path=probe,
        output_dir=_output_dir(tmp_path),
        no_write=True,
    )


def _readiness_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "readiness": {"classification": "ready_for_powered_support_coverer_probe_review"},
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
    }


def _probe_payload(
    *,
    coverer_phases: dict[str, float] | None = None,
) -> dict[str, object]:
    if coverer_phases is None:
        coverer_phases = {
            "coverer_union_collection": 1.0,
            "disjoint_filtering": 0.5,
            "power_index_expansion": 0.25,
            "compact_item_accumulation": 0.75,
            "stats_finalize": 0.0,
        }
    return {
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
        "sensitive_path_comparison": {
            "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "changed": False,
            "changed_paths": [],
            "changed_entries": [],
        },
        "inventory": {
            "model_build_seconds": 12.0,
            "build_stats_summary": {
                "exact_core_reuse": {
                    "residual_overlay_instrumentation": {
                        "enabled": True,
                        "port_profile_cache_instrumentation": {
                            "enabled": True,
                            "phase_seconds": {"powered_support_coverer_build": 2.5},
                            "totals": {"template_count": 2, "pose_count": 3},
                            "top_slow_templates_or_groups": [],
                            "powered_support_coverer_instrumentation": {
                                "enabled": True,
                                "phase_seconds": coverer_phases,
                                "totals": {
                                    "template_count": 2,
                                    "group_count": 3,
                                    "pose_count": 5,
                                },
                                "top_slow_groups": [],
                            },
                        },
                    }
                }
            },
        },
    }


def _output_dir(tmp_path: Path) -> Path:
    return (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "126_signature_bucket_powered_support_coverer_probe_review"
    )
