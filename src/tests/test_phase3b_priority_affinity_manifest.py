from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_phase3b_priority_affinity_manifest import (
    build_priority_affinity_manifest,
    write_priority_affinity_manifest,
)
from src.runtime.cpu_topology import (
    affinity_mask_hex,
    build_cpu_topology_snapshot,
    disjoint_process_groups,
    reserve_highest_logical_ids,
)


class _FakeProcess:
    pid = 123

    def cpu_affinity(self) -> list[int]:
        return [0, 1, 2, 3]


def test_cpu_topology_snapshot_defaults_to_unverified_pe_mapping(tmp_path: Path) -> None:
    snapshot = build_cpu_topology_snapshot(
        tmp_path,
        process=_FakeProcess(),  # type: ignore[arg-type]
        logical_count=6,
        physical_count=4,
        windows_processor_info={"Name": "fixture cpu", "NumberOfLogicalProcessors": 6},
    )

    assert snapshot["schema"] == "phase3b-cpu-topology-snapshot/v0"
    assert snapshot["cpu"]["logical_processor_count"] == 6
    assert snapshot["cpu"]["physical_core_count"] == 4
    assert len(snapshot["cpu"]["logical_processors"]) == 6
    assert snapshot["process"]["current_affinity"] == [0, 1, 2, 3]
    assert snapshot["pe_mapping"]["confidence"] == "unverified"
    assert snapshot["pe_mapping"]["can_drive_medium_confirmation"] is False
    assert snapshot["safety"]["proof_source"] is False


def test_affinity_helpers_are_stable() -> None:
    assert affinity_mask_hex([0, 2, 4]) == "0x15"
    reserved = reserve_highest_logical_ids(list(range(6)), 2)
    assert reserved["allowed_logical_ids"] == [0, 1, 2, 3]
    assert reserved["reserved_logical_ids"] == [4, 5]
    assert reserved["allowed_affinity_mask_hex"] == "0xf"

    groups = disjoint_process_groups(list(range(6)), 3)
    assert [group["logical_ids"] for group in groups] == [[0, 3], [1, 4], [2, 5]]
    assert [group["affinity_mask_hex"] for group in groups] == ["0x9", "0x12", "0x24"]


def test_priority_affinity_manifest_generates_variants_and_blocks_unverified_affinity(
    tmp_path: Path,
) -> None:
    scorecard_path, config_path, stage_path = _write_inputs(tmp_path)

    manifest = build_priority_affinity_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        config_matrix_manifest_path=config_path,
        stage_worker_manifest_path=stage_path,
        topology_snapshot=_topology_fixture(),
    )

    assert manifest["execution"]["status"] == "not_executed_manifest_only"
    assert manifest["topology"]["pe_mapping"]["confidence"] == "unverified"
    assert manifest["readiness"]["affinity_variants_can_enter_medium_confirmation"] is False
    assert len(manifest["base_profiles"]) == 4
    assert len(manifest["variants"]) == 20
    by_id = {variant["variant_id"]: variant for variant in manifest["variants"]}
    high = by_id["B0_prod_4x4__high_unpinned"]
    assert high["process_priority"] == "high"
    assert "high_priority_exploratory" in high["risk"]["reasons"]
    reserve = by_id["B0_prod_4x4__reserve_2_logical_ids"]
    assert reserve["affinity"]["reserved_logical_ids"] == [6, 7]
    assert reserve["medium_confirmation_status"] == "blocked_until_pe_mapping_verified"
    disjoint = by_id["W1_stage_4x_master6_local4_binding2_routing4__disjoint_process_groups"]
    assert len(disjoint["affinity"]["per_process_groups"]) == 4
    assert disjoint["proof_source"] is False


def test_priority_affinity_manifest_write_preserves_sensitive_paths(tmp_path: Path) -> None:
    scorecard_path, config_path, stage_path = _write_inputs(tmp_path)
    sensitive_file = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    sensitive_file.parent.mkdir(parents=True)
    sensitive_file.write_text('{"existing": true}', encoding="utf-8")
    before = _fingerprint(sensitive_file)

    manifest = build_priority_affinity_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        config_matrix_manifest_path=config_path,
        stage_worker_manifest_path=stage_path,
        topology_snapshot=_topology_fixture(),
    )
    output_dir = tmp_path / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "06_priority_affinity"
    paths = write_priority_affinity_manifest(manifest, output_dir)

    assert _fingerprint(sensitive_file) == before
    assert Path(paths["json"]).is_file()
    assert Path(paths["md"]).is_file()
    for path in paths.values():
        assert str(path).startswith(str(output_dir))
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["checkpoint_written"] is False
    assert payload["sensitive_path_audit"]["canonical_checkpoint_exists"] is True


def test_priority_affinity_manifest_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_priority_affinity_manifest.py"
    scorecard_path, config_path, stage_path = _write_inputs(tmp_path)
    output_dir = tmp_path / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "06_priority_affinity"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--baseline-scorecard",
            str(scorecard_path),
            "--config-matrix-manifest",
            str(config_path),
            "--stage-worker-manifest",
            str(stage_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write.returncode == 0
    assert "execution_status=not_executed_manifest_only" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--baseline-scorecard",
            str(scorecard_path),
            "--config-matrix-manifest",
            str(config_path),
            "--stage-worker-manifest",
            str(stage_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0
    assert (output_dir / "affinity_priority_manifest.json").exists()
    assert (output_dir / "affinity_priority_manifest.md").exists()


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    scorecard_path = tmp_path / "baseline_scorecard.json"
    config_path = tmp_path / "matrix_manifest.json"
    stage_path = tmp_path / "stage_worker_manifest.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")
    config_path.write_text(json.dumps(_config_manifest_fixture()), encoding="utf-8")
    stage_path.write_text(json.dumps(_stage_manifest_fixture()), encoding="utf-8")
    return scorecard_path, config_path, stage_path


def _scorecard_fixture() -> dict[str, object]:
    return {
        "baseline": {"profile_id": "prod_4x4"},
        "profiles": [
            {
                "profile_id": "prod_4x4",
                "process_count": 4,
                "worker_count_per_process": 4,
                "metrics": {"peak_rss_gib": 28.0},
            }
        ],
    }


def _config_manifest_fixture() -> dict[str, object]:
    return {
        "readiness": {
            "recommended_first_profiles_when_authorized": [
                "B0_prod_4x4",
                "experimental_13900ks_htoff_3x6_global_normal",
            ]
        },
        "profiles": [
            {
                "profile_id": "B0_prod_4x4",
                "process_count": 4,
                "env": {"EXACT_CP_SAT_WORKERS": "4"},
                "risk": {"level": "low", "reasons": []},
                "execution_status": "not_executed_manifest_only",
            },
            {
                "profile_id": "experimental_13900ks_htoff_3x6_global_normal",
                "process_count": 3,
                "env": {"EXACT_CP_SAT_WORKERS": "6"},
                "risk": {"level": "medium", "reasons": ["worker_slots_gt_20"]},
                "execution_status": "not_executed_manifest_only",
            },
        ],
    }


def _stage_manifest_fixture() -> dict[str, object]:
    return {
        "readiness": {
            "recommended_first_profiles_when_authorized": [
                "W0_prod_4x4_stage_4_4_4_4",
                "W1_stage_4x_master6_local4_binding2_routing4",
            ]
        },
        "profiles": [
            {
                "profile_id": "W0_prod_4x4_stage_4_4_4_4",
                "process_count": 4,
                "env": {"EXACT_MASTER_CP_SAT_WORKERS": "4"},
                "risk": {"level": "low", "reasons": []},
                "execution_status": "not_executed_manifest_only",
            },
            {
                "profile_id": "W1_stage_4x_master6_local4_binding2_routing4",
                "process_count": 4,
                "env": {"EXACT_MASTER_CP_SAT_WORKERS": "6"},
                "risk": {"level": "medium", "reasons": ["max_stage_worker_slots_gt_20"]},
                "execution_status": "not_executed_manifest_only",
            },
        ],
    }


def _topology_fixture() -> dict[str, object]:
    return {
        "schema": "phase3b-cpu-topology-snapshot/v0",
        "cpu": {
            "logical_processor_count": 8,
            "physical_core_count": 8,
            "logical_processors": [{"logical_id": index} for index in range(8)],
        },
        "pe_mapping": {"confidence": "unverified"},
        "priority": {"supported": True, "supported_modes": ["normal", "high"]},
    }


def _fingerprint(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    return (True, path.stat().st_size, path.stat().st_mtime_ns, path.read_text(encoding="utf-8"))
