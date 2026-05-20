from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.phase3b.prod_4x4.build_normal_dry_run import (
    DRY_RUN_SOURCE,
    build_phase3b_prod_4x4_normal_dry_run,
)


def test_prod_4x4_normal_cross_platform_dry_run_ready() -> None:
    repo_root = Path(__file__).resolve().parents[4]

    report = build_phase3b_prod_4x4_normal_dry_run(repo_root)

    assert report["metadata"]["source"] == DRY_RUN_SOURCE
    assert report["status"]["dry_run_validation_ready"] is True
    assert report["status"]["would_start_final_168h"] is False
    assert report["status"]["final_168h_authorized"] is False
    assert report["status"]["runtime_elimination_authorized"] is False
    assert report["dry_run"]["python_script_invoked_runner"] is False
    assert all(check["status"] == "pass" for check in report["checks"])


def test_prod_4x4_normal_cross_platform_dry_run_cli(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "prod_4x4" / "build_normal_dry_run.py"
    output_dir = tmp_path / "dry_run"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "dry_run_validation_ready=True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "prod_4x4_normal_dry_run_json=" in write.stdout
    payload = json.loads(
        (output_dir / "prod_4x4_normal_dry_run.json").read_text(encoding="utf-8")
    )
    assert payload["status"]["dry_run_validation_ready"] is True
    assert payload["status"]["would_start_final_168h"] is False
    assert (output_dir / "prod_4x4_normal_dry_run.md").exists()
    assert (output_dir / "prod_4x4_normal_dry_run.txt").exists()
