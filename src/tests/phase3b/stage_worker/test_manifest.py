from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.phase3b.stage_worker.build_manifest import (
    build_stage_worker_manifest,
    write_stage_worker_manifest,
)


def test_stage_worker_manifest_contains_w0_to_w8_and_exact_env(tmp_path: Path) -> None:
    scorecard_path = tmp_path / "baseline_scorecard.json"
    config_path = tmp_path / "matrix_manifest.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")
    config_path.write_text(json.dumps({"profiles": [{"profile_id": "B0_prod_4x4"}]}), encoding="utf-8")

    manifest = build_stage_worker_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        config_matrix_manifest_path=config_path,
    )

    by_id = {profile["profile_id"]: profile for profile in manifest["profiles"]}
    assert len(by_id) == 9
    w0 = by_id["W0_prod_4x4_stage_4_4_4_4"]
    assert w0["stage_workers"] == {
        "master": 4,
        "local_capacity": 4,
        "binding": 4,
        "routing": 4,
    }
    assert w0["env"] == {
        "EXACT_MASTER_CP_SAT_WORKERS": "4",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "4",
        "EXACT_BINDING_CP_SAT_WORKERS": "4",
        "EXACT_ROUTING_CP_SAT_WORKERS": "4",
    }
    w4 = by_id["W4_stage_4x_master8_local6_binding2_routing6"]
    assert w4["env"]["EXACT_MASTER_CP_SAT_WORKERS"] == "8"
    assert w4["env"]["EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS"] == "6"
    assert w4["env"]["EXACT_BINDING_CP_SAT_WORKERS"] == "2"
    assert w4["env"]["EXACT_ROUTING_CP_SAT_WORKERS"] == "6"
    assert manifest["worker_env_precedence"][0] == "stage-specific env"
    assert manifest["safety"]["proof_source"] is False


def test_stage_worker_manifest_risk_and_estimates(tmp_path: Path) -> None:
    scorecard_path = tmp_path / "baseline_scorecard.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")

    manifest = build_stage_worker_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        config_matrix_manifest_path=tmp_path / "missing.json",
    )
    by_id = {profile["profile_id"]: profile for profile in manifest["profiles"]}

    assert by_id["W0_prod_4x4_stage_4_4_4_4"]["estimated_peak_rss_gib"] == 28.0
    assert by_id["W2_stage_4x_master8_local4_binding2_routing4"]["risk"]["level"] == "high"
    assert "max_stage_worker_slots_gt_24" in by_id["W2_stage_4x_master8_local4_binding2_routing4"]["risk"]["reasons"]
    assert by_id["W5_stage_3x_master8_local8_binding2_routing8"]["risk"]["level"] == "medium"
    assert by_id["W8_stage_2x_master16_local8_binding2_routing8"]["risk"]["level"] == "high"
    assert "max_stage_workers_ge_16" in by_id["W8_stage_2x_master16_local8_binding2_routing8"]["risk"]["reasons"]


def test_stage_worker_manifest_write_preserves_sensitive_paths(tmp_path: Path) -> None:
    scorecard_path = tmp_path / "baseline_scorecard.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")
    sensitive_file = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    sensitive_file.parent.mkdir(parents=True)
    sensitive_file.write_text('{"existing": true}', encoding="utf-8")
    before = _fingerprint(sensitive_file)

    manifest = build_stage_worker_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        config_matrix_manifest_path=tmp_path / "missing.json",
    )
    output_dir = tmp_path / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "05_stage_workers"
    paths = write_stage_worker_manifest(manifest, output_dir)

    assert _fingerprint(sensitive_file) == before
    assert Path(paths["json"]).is_file()
    assert Path(paths["md"]).is_file()
    for path in paths.values():
        assert str(path).startswith(str(output_dir))
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["checkpoint_written"] is False
    assert payload["sensitive_path_audit"]["canonical_checkpoint_exists"] is True


def test_stage_worker_manifest_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "stage_worker" / "build_manifest.py"
    scorecard_path = tmp_path / "baseline_scorecard.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")
    output_dir = tmp_path / "stage"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--baseline-scorecard",
            str(scorecard_path),
            "--config-matrix-manifest",
            str(tmp_path / "missing.json"),
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
            str(tmp_path / "missing.json"),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0
    assert (output_dir / "stage_worker_manifest.json").exists()
    assert (output_dir / "stage_worker_manifest.md").exists()


def _scorecard_fixture() -> dict[str, object]:
    return {
        "baseline": {"profile_id": "prod_4x4"},
        "profiles": [
            {
                "profile_id": "prod_4x4",
                "process_count": 4,
                "worker_count_per_process": 4,
                "metrics": {
                    "peak_rss_gib": 28.0,
                    "candidate_results_per_hour": 154.0,
                },
            }
        ],
    }


def _fingerprint(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    return (True, path.stat().st_size, path.stat().st_mtime_ns, path.read_text(encoding="utf-8"))
