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

from scripts.phase3b.checkpoint_free.signature_bucket.powered_support_coverer.build_compact_item_external_review_package import (
    build_compact_item_accumulation_external_review_package,
    build_compact_item_accumulation_strategy,
)


def test_compact_item_strategy_classifies_s128_hotspot(tmp_path: Path) -> None:
    paths = _write_fixture_tree(tmp_path)

    strategy = build_compact_item_accumulation_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        no_write=True,
        s126_review_path=paths["s126"],
        s127_review_summary_path=paths["s127"],
        s128_execution_path=paths["s128"],
        s124_implementation_path=paths["s124"],
    )

    assert strategy["status"] == "completed"
    assert (
        strategy["classification"]
        == "powered_support_coverer_compact_item_accumulation_strategy_required"
    )
    assert (
        strategy["future_patch_spec_for_review"]["suggested_env_var"]
        == "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION"
    )
    assert "do_not_rerun_s128_probe" in strategy["blocked_actions"]


def test_compact_item_strategy_requires_clean_classification(tmp_path: Path) -> None:
    paths = _write_fixture_tree(tmp_path)
    s126 = json.loads(paths["s126"].read_text(encoding="utf-8"))
    s126["interpretation"]["classification"] = "disjoint_filtering_hotspot"
    paths["s126"].write_text(json.dumps(s126) + "\n", encoding="utf-8")

    strategy = build_compact_item_accumulation_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        no_write=True,
        s126_review_path=paths["s126"],
        s127_review_summary_path=paths["s127"],
        s128_execution_path=paths["s128"],
        s124_implementation_path=paths["s124"],
    )

    assert strategy["status"] == "manual_review_required"


def test_compact_item_package_contains_context_and_wording(tmp_path: Path) -> None:
    _write_fixture_tree(tmp_path)
    strategy_path = (
        _strategy_dir(tmp_path)
        / "signature_bucket_powered_support_coverer_compact_item_strategy.json"
    )
    build_compact_item_accumulation_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
    )

    package = build_compact_item_accumulation_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="s130_001",
    )

    assert package["status"] == "completed"
    assert Path(package["zip_path"]).exists()
    assert Path(package["expanded_review_bundle_path"]).exists()
    assert package["clean_extraction_validation"]["validated"] is True
    assert package["clean_extraction_validation"]["request_text_contains_required_wording"] is True
    manifest_keys = {entry["key"] for entry in package["manifest"]["entries"]}
    assert {
        "s126_probe_review",
        "s127_review_summary",
        "s128_probe_execution",
        "s129_strategy",
        "master_model_source",
        "s126_review_builder",
        "s130_builder",
    }.issubset(manifest_keys)
    assert strategy_path.exists()
    request = package["review_request"]
    assert "s130_001.zip" in request
    assert "needs review first" in request
    assert "review is not authorization" in request
    assert "if review passes request user/project-owner authorization" in request


def test_compact_item_package_namespace_guard(tmp_path: Path) -> None:
    _write_fixture_tree(tmp_path)
    build_compact_item_accumulation_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
    )

    with pytest.raises(ValueError, match="S130 package namespace"):
        build_compact_item_accumulation_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_fixture_tree(root: Path) -> dict[str, Path]:
    artifact_root = root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
    paths = {
        "s126": artifact_root
        / "126_signature_bucket_powered_support_coverer_probe_review"
        / "signature_bucket_powered_support_coverer_probe_review.json",
        "s127": artifact_root
        / "127_signature_bucket_powered_support_coverer_probe_external_review_package"
        / "s125_s126_powered_support_coverer_probe_review_001"
        / "external_review_reply_summary.json",
        "s128": artifact_root
        / "128_signature_bucket_powered_support_coverer_probe_execution"
        / "signature_bucket_powered_support_coverer_probe_execution.json",
        "s124": artifact_root
        / "124_signature_bucket_powered_support_coverer_instrumentation_implementation"
        / "signature_bucket_powered_support_coverer_instrumentation_implementation.json",
    }
    payloads = {
        "s126": _s126_payload(),
        "s127": {"review_verdict": "pass"},
        "s128": {"status": "completed"},
        "s124": {"status": "implemented_and_verified"},
    }
    for key, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payloads[key]) + "\n", encoding="utf-8")
    _write_context_file(root / "AGENTS.md")
    _write_context_file(root / "src" / "models" / "master_model.py")
    _write_context_file(root / "src" / "models" / "exact_coordinate_master.py")
    _write_context_file(root / "src" / "tests" / "test_master.py")
    _write_context_file(root / "src" / "tests" / "test_exact_contract.py")
    _write_context_file(
        root
        / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_probe_review.py"
    )
    _write_context_file(
        root
        / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_compact_item_external_review_package.py"
    )
    _write_context_file(
        root
        / "src"
        / "tests"
        / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_probe_review.py"
    )
    _write_context_file(
        root
        / "src"
        / "tests"
        / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_compact_item_external_review_package.py"
    )
    return paths


def _s126_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "model_build_seconds": 13.55,
        "interpretation": {
            "classification": "compact_item_accumulation_hotspot",
            "dominant_phase": "compact_item_accumulation",
            "dominant_seconds": 1.22,
        },
        "subphase_summary": {
            "phase_seconds": {
                "compact_item_accumulation": 1.22,
                "coverer_union_collection": 0.41,
                "disjoint_filtering": 0.61,
                "power_index_expansion": 0.04,
                "stats_finalize": 0.01,
            },
            "totals": {
                "candidate_coverer_count": 4692554,
                "filtered_coverer_count": 4097240,
                "compact_item_update_count": 4097240,
                "group_count": 22042,
                "pose_count": 69700,
                "representative_cell_count": 394760,
            },
        },
        "probe_safety": {"sensitive_path_clean": True},
        "checkpoint_written": False,
        "proof_source": False,
    }


def _write_context_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("context\n", encoding="utf-8")


def _strategy_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "129_signature_bucket_powered_support_coverer_compact_item_strategy"
    )


def _package_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "130_signature_bucket_powered_support_coverer_compact_item_external_review_package"
    )
