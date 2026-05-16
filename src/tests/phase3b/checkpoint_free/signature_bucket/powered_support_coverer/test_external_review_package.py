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

from scripts.phase3b.checkpoint_free.signature_bucket.powered_support_coverer.build_external_review_package import (
    build_powered_support_coverer_external_review_package,
    build_powered_support_coverer_strategy,
)


def test_powered_support_coverer_strategy_classifies_hotspot(tmp_path: Path) -> None:
    paths = _write_fixture_tree(tmp_path)

    strategy = build_powered_support_coverer_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        no_write=True,
        s118_review_path=paths["s118"],
        s119_review_summary_path=paths["s119"],
        s120_execution_path=paths["s120"],
        s121_repair_path=paths["s121"],
    )

    assert strategy["status"] == "completed"
    assert (
        strategy["classification"]
        == "powered_support_coverer_detail_instrumentation_strategy_required"
    )
    assert (
        strategy["future_patch_spec_for_review"]["env_var"]
        == "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION"
    )


def test_powered_support_coverer_strategy_requires_clean_inputs(tmp_path: Path) -> None:
    paths = _write_fixture_tree(tmp_path)
    s118 = json.loads(paths["s118"].read_text(encoding="utf-8"))
    s118["interpretation"]["classification"] = "port_front_extraction_hotspot"
    paths["s118"].write_text(json.dumps(s118) + "\n", encoding="utf-8")

    strategy = build_powered_support_coverer_strategy(
        project_root=tmp_path,
        output_dir=_strategy_dir(tmp_path),
        no_write=True,
        s118_review_path=paths["s118"],
        s119_review_summary_path=paths["s119"],
        s120_execution_path=paths["s120"],
        s121_repair_path=paths["s121"],
    )

    assert strategy["status"] == "manual_review_required"


def test_powered_support_coverer_package_contains_review_context(tmp_path: Path) -> None:
    _write_fixture_tree(tmp_path)
    strategy = _strategy_dir(tmp_path) / "signature_bucket_powered_support_coverer_strategy.json"
    build_powered_support_coverer_strategy(project_root=tmp_path, output_dir=_strategy_dir(tmp_path))

    package = build_powered_support_coverer_external_review_package(
        project_root=tmp_path,
        output_dir=_package_dir(tmp_path),
        run_id="s122_powered_support_coverer_review_001",
    )

    assert package["status"] == "completed"
    assert Path(package["zip_path"]).exists()
    assert Path(package["expanded_review_bundle_path"]).exists()
    assert package["clean_extraction_validation"]["validated"] is True
    assert package["clean_extraction_validation"]["request_text_contains_required_wording"] is True
    manifest_keys = {entry["key"] for entry in package["manifest"]["entries"]}
    assert {
        "s118_probe_review",
        "s120_probe_execution",
        "s121_schema_repair",
        "s122_strategy",
        "master_model_source",
        "s118_review_builder",
        "s123_builder",
    }.issubset(manifest_keys)
    assert strategy.exists()


def test_powered_support_coverer_package_namespace_guard(tmp_path: Path) -> None:
    _write_fixture_tree(tmp_path)
    build_powered_support_coverer_strategy(project_root=tmp_path, output_dir=_strategy_dir(tmp_path))

    with pytest.raises(ValueError, match="S123 package namespace"):
        build_powered_support_coverer_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_fixture_tree(root: Path) -> dict[str, Path]:
    artifact_root = root / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
    paths = {
        "s118": artifact_root
        / "118_signature_bucket_port_profile_cache_probe_review"
        / "signature_bucket_port_profile_cache_probe_review.json",
        "s119": artifact_root
        / "119_signature_bucket_port_profile_cache_probe_external_review_package"
        / "s117_s118_port_profile_cache_probe_review_001"
        / "external_review_reply_summary.json",
        "s120": artifact_root
        / "120_signature_bucket_port_profile_cache_probe_execution"
        / "signature_bucket_port_profile_cache_probe_execution.json",
        "s121": artifact_root
        / "121_port_profile_cache_probe_review_schema_repair"
        / "port_profile_cache_probe_review_schema_repair.json",
    }
    payloads = {
        "s118": _s118_payload(),
        "s119": {"review_verdict": "pass"},
        "s120": {"status": "completed_review_initially_inconclusive_then_repaired"},
        "s121": {"status": "implemented_and_verified"},
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
        / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "port_profile_cache" / "build_probe_review.py"
    )
    _write_context_file(
        root
        / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_external_review_package.py"
    )
    _write_context_file(
        root
        / "src"
        / "tests"
        / "test_phase3b_checkpoint_free_signature_bucket_port_profile_cache_probe_review.py"
    )
    _write_context_file(
        root
        / "src"
        / "tests"
        / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_external_review_package.py"
    )
    return paths


def _s118_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "model_build_seconds": 13.4,
        "interpretation": {
            "classification": "powered_support_coverer_hotspot",
            "dominant_phase": "powered_support_coverer_build",
            "dominant_seconds": 3.18,
            "phase_seconds": {
                "powered_support_coverer_build": 3.18,
                "compact_capacity_signature_store": 1.1,
                "per_template_pose_cache_build": 0.7,
            },
        },
        "subphase_summary": {
            "required_numeric": {"index_pools_total_seconds": 5.7},
            "totals": {
                "support_coverer_scan_count": 394760,
                "support_coverer_candidate_count": 4692554,
                "anchor_shape_group_count": 22042,
                "powered_template_count": 4,
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
        / "122_signature_bucket_powered_support_coverer_strategy"
    )


def _package_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "123_signature_bucket_powered_support_coverer_external_review_package"
    )
