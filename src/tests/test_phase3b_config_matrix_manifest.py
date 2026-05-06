from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_phase3b_config_matrix_manifest import (
    build_config_matrix_manifest,
    write_config_matrix_manifest,
)


def test_config_matrix_manifest_contains_expected_profiles(tmp_path: Path) -> None:
    scorecard_path = tmp_path / "baseline_scorecard.json"
    ai_summary_path = tmp_path / "dataset_summary.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")
    ai_summary_path.write_text(json.dumps({"sample_count": 26}), encoding="utf-8")

    manifest = build_config_matrix_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        ai_dataset_summary_path=ai_summary_path,
    )

    profile_ids = [profile["profile_id"] for profile in manifest["profiles"]]
    assert profile_ids[0] == "B0_prod_4x4"
    assert "experimental_13900ks_htoff_3x8_global_normal" in profile_ids
    assert "experimental_13900ks_htoff_5x4_global_normal" in profile_ids
    assert len(profile_ids) == 11
    assert manifest["execution"]["status"] == "not_executed_manifest_only"
    assert manifest["safety"]["proof_source"] is False
    assert manifest["readiness"]["ai_dataset_sample_count"] == 26


def test_config_matrix_manifest_risk_and_estimates(tmp_path: Path) -> None:
    scorecard_path = tmp_path / "baseline_scorecard.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")

    manifest = build_config_matrix_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        ai_dataset_summary_path=tmp_path / "missing.json",
    )
    by_id = {profile["profile_id"]: profile for profile in manifest["profiles"]}

    assert by_id["B0_prod_4x4"]["estimated_peak_rss_gib"] == 28.0
    assert by_id["experimental_13900ks_htoff_3x6_global_normal"]["total_worker_slots"] == 18
    assert by_id["experimental_13900ks_htoff_3x8_global_normal"]["risk"]["level"] == "medium"
    assert "global_workers_ge_16" in by_id["experimental_13900ks_htoff_1x24_global_normal"]["risk"]["reasons"]
    assert by_id["experimental_13900ks_htoff_5x4_global_normal"]["risk"]["level"] == "medium"


def test_config_matrix_manifest_write_preserves_sensitive_paths(tmp_path: Path) -> None:
    scorecard_path = tmp_path / "baseline_scorecard.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")
    sensitive_file = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    sensitive_file.parent.mkdir(parents=True)
    sensitive_file.write_text('{"existing": true}', encoding="utf-8")
    before = _fingerprint(sensitive_file)

    manifest = build_config_matrix_manifest(
        project_root=tmp_path,
        baseline_scorecard_path=scorecard_path,
        ai_dataset_summary_path=tmp_path / "missing.json",
    )
    output_dir = tmp_path / ".artifacts" / "phase3b_local_13900ks_tuning_20260430" / "04_config_matrix"
    paths = write_config_matrix_manifest(manifest, output_dir)

    assert _fingerprint(sensitive_file) == before
    assert Path(paths["json"]).is_file()
    assert Path(paths["md"]).is_file()
    for path in paths.values():
        assert str(path).startswith(str(output_dir))
    payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert payload["safety"]["checkpoint_written"] is False
    assert payload["sensitive_path_audit"]["canonical_checkpoint_exists"] is True


def test_config_matrix_manifest_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_config_matrix_manifest.py"
    scorecard_path = tmp_path / "baseline_scorecard.json"
    scorecard_path.write_text(json.dumps(_scorecard_fixture()), encoding="utf-8")
    output_dir = tmp_path / "matrix"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--baseline-scorecard",
            str(scorecard_path),
            "--ai-dataset-summary",
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
            "--ai-dataset-summary",
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
    assert (output_dir / "matrix_manifest.json").exists()
    assert (output_dir / "matrix_manifest.md").exists()


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
