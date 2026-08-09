from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.b5a.blocker_pivot import build_phase3b_b5a_blocker_pivot


def test_b5a_blocker_pivot_recommends_power_protocol(tmp_path: Path) -> None:
    _write_standard_reports(tmp_path)

    report = build_phase3b_b5a_blocker_pivot(tmp_path)

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "pivot_to_power_protocol_global_blocker"
    assert report["status"]["runtime_promotion_ready"] is False
    assert report["open_branch"]["branch"] == "power_protocol_family_lookup_global_blocker"
    assert len(report["closed_branches"]) == 3


def test_b5a_blocker_pivot_cli_no_write(tmp_path: Path) -> None:
    _write_standard_reports(tmp_path)
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/b5a/build_blocker_pivot.py",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b b5a blocker pivot" in completed.stdout
    assert not output_dir.exists()


def test_b5a_blocker_pivot_cli_writes_outputs(tmp_path: Path) -> None:
    _write_standard_reports(tmp_path)
    output_dir = tmp_path / "out"

    subprocess.run(
        [
            sys.executable,
            "scripts/phase3b/b5a/build_blocker_pivot.py",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[4],
        text=True,
        capture_output=True,
        check=True,
    )

    assert (output_dir / "b5a_blocker_pivot.json").exists()
    assert (output_dir / "b5a_blocker_pivot.md").exists()
    assert (output_dir / "b5a_blocker_pivot.txt").exists()


def _write_standard_reports(root: Path) -> None:
    _write_json(
        root / ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json",
        {"status": {"anchor_found": False}},
    )
    _write_json(
        root / ".artifacts/phase3b_residual_pose_order_taxonomy/residual_pose_order_taxonomy.json",
        {"status": {"outcome": "stable_ordering_sensitive_class_observed"}},
    )
    _write_json(
        root / ".artifacts/phase3b_order_independent_predicate_scan/order_independent_predicate_scan.json",
        {"status": {"outcome": "no_order_independent_predicate_found"}},
    )
    _write_json(
        root / ".artifacts/phase3b_y_unique_local_hypothesis/y_unique_local_hypothesis.json",
        {
            "status": {
                "outcome": "class_local_clue_deprioritized_by_existing_negative_validation"
            }
        },
    )
    _write_json(
        root / ".artifacts/phase3b_power_protocol_interaction/power_protocol_interaction.json",
        {"recommendation": "global table blocker"},
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
